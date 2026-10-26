"""Keep hourly radar rain per SwimSignal rain cell from the Met Office's free UK radar archive.

The archive is the AWS Open Data bucket "Met Office UK Radar Observations" (no account): one UK
composite of surface rain rate every 15 minutes on a 1 km grid, kept for about two years and then
deleted. Its oldest file is from 21 Nov 2024, so this script keeps our own copy of the part we
use: for each day it downloads the day's composites one at a time, reduces each to the mean rate
over the radar pixels inside each rain cell, and writes hourly totals. The raw files are not kept.
What the files contain, and why this exists, is in docs/MET-OFFICE-DATA-2026-10.md. Nothing here
reaches the site or the model. Off CI, by hand, with h5py from the optional `radar` group:

    uv run --extra radar python scripts/fetch_met_office_radar.py 2026-02-06 2026-02-06
    uv run --extra radar python scripts/fetch_met_office_radar.py 2024-11-21 2026-10-23 --cells cells.csv
    uv run --extra radar python scripts/fetch_met_office_radar.py 2024-11-21 2026-10-25 --no-cells \
        --overflows data/processed/overflows.parquet --out ~/radar

Cells: by default every cell with a forecast_* or leads_* file in the rain cache (data/cache/rain,
or $DIPCAST_CACHE/rain), which is the listed spots' cells and the evaluation cells. Or --cells CSV
with columns cell_lat,cell_lon (or lat,lon, snapped with rainfall.grid_cell).

Output: data/raw/met_office_radar/radar_<cell>_<YYYY-MM>.parquet, one per cell and month, columns
cell_lat, cell_lon, time (UTC, hour-ending, as Open-Meteo labels its hourly rain), radar_mm (rain in
that hour, mm) and coverage (0 to 1: the share of the hour's pixel samples that had data). It goes
in data/raw, not data/cache, because once the bucket deletes a month it cannot be fetched again.

Overflows (--overflows overflows.parquet): also the rain at each storm overflow's own position, which a
0.1 degree cell averages away. For each overflow, the radar pixel that holds its lat/lon and the eight
around it (fewer at the grid's edge), pooled like a cell, plus the centre pixel alone. One file per UTC
day, <out>/overflows/radar_overflows_<YYYY-MM-DD>.parquet: site_id, time, radar_mm and coverage (the
3 x 3 block), centre_mm and centre_coverage (the one pixel). <out>/overflows/overflow_pixels.parquet
lists each overflow's pixel; it and every day file carry the overflow table's SHA-256, its
network_key and the pixel rule in their metadata. --no-cells writes the overflows only.

Resumable: a day is skipped for a cell whose month file already has all 24 of that day's hours, and
for the overflows when that day's file exists, so a stopped run starts again where it stopped. Polite: one request at a time, a pause between them,
and retries with a growing wait.

Contains Met Office data, British Crown copyright 2024-2025, the Met Office, licensed under
CC BY-SA 4.0. The files written here are Adapted Material: shared outside SwimSignal, they go out
under CC BY-SA 4.0 with this credit.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import logging
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import Transformer

from dipcast import config
from dipcast.ingest.rainfall import cell_key, grid_cell

log = logging.getLogger("met_office_radar")

BUCKET = "https://met-office-radar-obs-data.s3.amazonaws.com"
KEY_RE = re.compile(r"radar/\d{4}/\d{2}/\d{2}/(\d{12})_ODIM_ng_radar_rainrate_composite_1km_UK\.h5$")
OUT = config.RAW / "met_office_radar"
CREDIT = ("Contains Met Office data, British Crown copyright 2024-2025, the Met Office, licensed "
          "under CC BY-SA 4.0 (AWS Open Data: Met Office UK Radar Observations).")

# The grid, read from the files' `where` group on 24 Oct 2026 (one from 21 Nov 2024, two from 24 Oct
# 2026, all the same): 1725 x 2175 pixels of 1 km, first row at the top. The corner coordinates in
# the file put the outer edges at x -405,000 to 1,320,000 m and y -625,000 to 1,550,000 m.
NX, NY, PIXEL_M = 1725, 2175, 1000.0
X_LEFT, Y_TOP = -405_000.0, 1_550_000.0
PROJDEF = "+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.999601 +x_0=400000 +y_0=-100000 +ellps=airy +units=m"
# That projdef is British National Grid without its datum. EPSG:27700 adds the OSGB36 datum; the two
# put a point at 52 N 1 W about 115 m apart, an eighth of a pixel. The "ng" in the file name is
# National Grid, so EPSG:27700 it is.
GRID_CRS = "EPSG:27700"

# The 15-minute composites are snapshots of rain rate (mm/h), not totals: each file's scan window
# lasts about a minute, within a minute of the time in its name (00:14:07 to 00:15:09 for one 00:15
# file). The hour ending T is the trapezoid over the five snapshots T-60, T-45, T-30, T-15 and T.
STEP = pd.Timedelta(minutes=15)
WEIGHTS = np.array([0.5, 1.0, 1.0, 1.0, 0.5])

PAUSE_S = 0.2
TRIES = 5
WAIT_BASE_S = 2.0
TIMEOUT_S = 60.0

_sleep = time.sleep   # replaced in tests


# ------------------------------------------------------------------ cells and pixels
def default_cells(cache_dir: Path) -> list[tuple[float, float]]:
    """The cells named by forecast_<lat>_<lon>.parquet and leads_<lat>_<lon>_<year>.parquet."""
    cells = set()
    for p in cache_dir.glob("*.parquet"):
        m = re.match(r"(?:forecast|leads)_(-?\d+\.\d+)_(-?\d+\.\d+)(?:_\d{4})?\.parquet$", p.name)
        if m:
            cells.add((float(m[1]) + 0.0, float(m[2]) + 0.0))
    return sorted(cells)


def read_cells(path: Path) -> list[tuple[float, float]]:
    df = pd.read_csv(path)
    if {"cell_lat", "cell_lon"} <= set(df.columns):
        lat, lon = df.cell_lat.to_numpy(float), df.cell_lon.to_numpy(float)
    else:
        lat, lon = df.lat.to_numpy(float), df.lon.to_numpy(float)
    cl, cn = grid_cell(lat, lon)
    return sorted({(float(a), float(b)) for a, b in zip(cl, cn, strict=True)})


def cell_pixels(cells: list[tuple[float, float]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The radar pixels whose centre falls in each cell, by the same grid_cell the sites use.
    Returns (flat pixel index, cell number per index, pixels per cell)."""
    d = config.RAIN_GRID_DEG / 2
    fwd = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True)
    inv = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True)
    idx, lab = [], []
    n = np.zeros(len(cells), dtype=np.int64)
    for k, (cl, cn) in enumerate(cells):
        xs, ys = fwd.transform([cn - d, cn + d, cn - d, cn + d], [cl - d, cl - d, cl + d, cl + d])
        c0 = max(0, int((min(xs) - X_LEFT) // PIXEL_M) - 1)
        c1 = min(NX - 1, int((max(xs) - X_LEFT) // PIXEL_M) + 1)
        r0 = max(0, int((Y_TOP - max(ys)) // PIXEL_M) - 1)
        r1 = min(NY - 1, int((Y_TOP - min(ys)) // PIXEL_M) + 1)
        if c0 > c1 or r0 > r1:
            continue
        rr, cc = np.mgrid[r0:r1 + 1, c0:c1 + 1]
        lon, lat = inv.transform(X_LEFT + (cc + 0.5) * PIXEL_M, Y_TOP - (rr + 0.5) * PIXEL_M)
        gl, gn = grid_cell(lat, lon)
        inside = (gl == cl) & (gn == cn)
        flat = (rr * NX + cc)[inside]
        idx.append(flat)
        lab.append(np.full(flat.size, k))
        n[k] = flat.size
    if not idx:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), n
    return np.concatenate(idx), np.concatenate(lab), n


PIXEL_RULE = ("the 1 km radar pixel whose square holds the overflow's lat/lon (EPSG:4326 to "
              f"{GRID_CRS}), and for radar_mm the 3 x 3 block around it, clipped to the grid; "
              "centre_mm is that pixel alone")


def overflow_pixels(lat, lon) -> tuple[np.ndarray, np.ndarray]:
    """The (row, col) of the radar pixel whose square holds each point; -1 for a point off the grid."""
    x, y = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True).transform(
        np.asarray(lon, float), np.asarray(lat, float))
    col = np.floor((np.asarray(x) - X_LEFT) / PIXEL_M)
    row = np.floor((Y_TOP - np.asarray(y)) / PIXEL_M)
    off = ~((col >= 0) & (col < NX) & (row >= 0) & (row < NY))
    col[off], row[off] = -1, -1
    return row.astype(np.int64), col.astype(np.int64)


def block_pixels(row: np.ndarray, col: np.ndarray, half: int = 1
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each (row, col), the pixels of the (2 half + 1) square around it that lie on the grid, as
    cell_pixels returns them: (flat pixel index, point number per index, pixels per point). A point
    off the grid (row -1) has none."""
    d = np.arange(-half, half + 1)
    dr, dc = (a.ravel() for a in np.meshgrid(d, d, indexing="ij"))
    rr, cc = row[:, None] + dr, col[:, None] + dc
    ok = (row[:, None] >= 0) & (rr >= 0) & (rr < NY) & (cc >= 0) & (cc < NX)
    lab = np.broadcast_to(np.arange(len(row))[:, None], rr.shape)
    return (rr * NX + cc)[ok], lab[ok], ok.sum(axis=1)


def table_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_overflows(path: Path) -> tuple[pd.DataFrame, dict]:
    """site_id, lat, lon from an overflows table, and the metadata the output carries to say which."""
    df = pd.read_parquet(path)
    keys = sorted(df["network_key"].dropna().unique()) if "network_key" in df else []
    meta = {"overflows_sha256": table_sha256(path), "overflows_file": Path(path).name,
            "overflows_rows": len(df), "network_key": ",".join(keys) or "none",
            "pixel_rule": PIXEL_RULE}
    df = df[["site_id", "lat", "lon"]].dropna()
    if not df.site_id.is_unique:
        raise SystemExit(f"{path}: site_id is not unique")
    return df.reset_index(drop=True), meta


# ------------------------------------------------------------------ one composite
def read_composite(data: bytes) -> np.ndarray:
    """The rain rate in mm/h, NaN where the file says nodata, from one ODIM HDF5 composite. Raises
    ValueError if the grid or the quantity is not the one this script was written for."""
    import h5py   # the optional `radar` group; imported here so the rest runs and tests without it

    with h5py.File(io.BytesIO(data), "r") as f:
        where = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in f["where"].attrs.items()}
        what = {k: (v.decode() if isinstance(v, bytes) else v)
                for k, v in f["dataset1/data1/what"].attrs.items()}
        origin = f["dataset1/how"].attrs.get("origin", b"")
        origin = origin.decode() if isinstance(origin, bytes) else origin
        got = (int(where["xsize"]), int(where["ysize"]), float(where["xscale"]), float(where["yscale"]),
               where["projdef"].strip(), what["quantity"], origin)
        want = (NX, NY, PIXEL_M, PIXEL_M, PROJDEF, "RATE", "UPPER LEFT")
        if got != want:
            raise ValueError(f"radar grid changed: {got} != {want}")
        raw = f["dataset1/data1/data"][()]
    if raw.shape != (NY, NX):
        raise ValueError(f"radar array is {raw.shape}, not {(NY, NX)}")
    rate = raw.astype(np.float64) * float(what["gain"]) + float(what["offset"])
    rate[(raw == what["nodata"]) | ~np.isfinite(raw)] = np.nan
    return rate


def reduce_snapshot(rate: np.ndarray, idx: np.ndarray, lab: np.ndarray, n_cells: int
                    ) -> tuple[np.ndarray, np.ndarray]:
    """Per cell: the sum of the rate over pixels with data, and how many pixels had data."""
    v = rate.ravel()[idx]
    ok = np.isfinite(v)
    sums = np.bincount(lab[ok], weights=v[ok], minlength=n_cells)
    counts = np.bincount(lab[ok], minlength=n_cells).astype(np.float64)
    return sums, counts


def hourly(snaps: dict[pd.Timestamp, tuple[np.ndarray, np.ndarray]], hours: pd.DatetimeIndex,
           n_pix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rain (mm) and coverage per hour and cell, shape (hours, cells). Each hour pools its five
    snapshots' pixels with the trapezoid weights, so a snapshot with few pixels counts for little.
    A missing snapshot lowers coverage; an hour with no data is NaN with coverage 0."""
    mm = np.full((len(hours), len(n_pix)), np.nan)
    cov = np.zeros_like(mm)
    zero = (np.zeros(len(n_pix)), np.zeros(len(n_pix)))
    for h, t in enumerate(hours):
        s = sum(w * snaps.get(t - (4 - i) * STEP, zero)[0] for i, w in enumerate(WEIGHTS))
        c = sum(w * snaps.get(t - (4 - i) * STEP, zero)[1] for i, w in enumerate(WEIGHTS))
        ok = c > 0
        mm[h, ok] = s[ok] / c[ok]   # mean rate in mm/h over one hour = mm
        cov[h] = c / (WEIGHTS.sum() * np.maximum(n_pix, 1))
    return mm, cov


# ------------------------------------------------------------------ the bucket
def get(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response | None:
    """GET with retries on a 429, a 5xx or a transport error. None on a 404."""
    for k in range(TRIES):
        try:
            r = client.get(url, params=params)
        except httpx.TransportError as e:
            err = repr(e)
        else:
            if r.status_code == 404:
                return None
            if r.status_code < 400:
                return r
            if r.status_code != 429 and r.status_code < 500:
                r.raise_for_status()
            err = f"HTTP {r.status_code}"
        if k + 1 < TRIES:
            wait = WAIT_BASE_S * 2 ** k
            log.warning("%s: %s; retry in %.0f s", url, err, wait)
            _sleep(wait)
    raise RuntimeError(f"{url}: failed {TRIES} times ({err})")


def list_day(client: httpx.Client, day: pd.Timestamp) -> dict[pd.Timestamp, str]:
    """The composites under radar/YYYY/MM/DD/, by the UTC time in their name."""
    prefix = f"radar/{day:%Y/%m/%d}/"
    out, token = {}, None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        r = get(client, BUCKET + "/", params)
        if r is None:
            return out
        root = ET.fromstring(r.content)
        ns = {"s3": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
        q = (lambda tag: f"s3:{tag}") if ns else (lambda tag: tag)
        for el in root.iterfind(q("Contents"), ns):
            key = el.findtext(q("Key"), default="", namespaces=ns)
            m = KEY_RE.match(key)
            if m:
                out[pd.Timestamp(m[1], tz="UTC")] = key
        token = root.findtext(q("NextContinuationToken"), default=None, namespaces=ns)
        if not token:
            return out
        _sleep(PAUSE_S)


# ------------------------------------------------------------------ the month files
def month_path(out: Path, cell: tuple[float, float], month: pd.Timestamp) -> Path:
    return out / f"radar_{cell_key(*cell)}_{month:%Y-%m}.parquet"


def read_month(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_parquet(path)
    except (OSError, ValueError):
        return None


def write_month(path: Path, df: pd.DataFrame, meta: dict | None = None, compression: str = "snappy") -> None:
    """Write atomically, with the credit in the file's metadata (CC BY-SA needs it to travel), and
    any other metadata given."""
    table = pa.Table.from_pandas(df, preserve_index=False)
    extra = {k.encode(): str(v).encode() for k, v in (meta or {}).items()}
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), **extra,
                                           b"credit": CREDIT.encode()})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp, compression=compression)
    tmp.replace(path)


def overflow_day_path(out: Path, day: pd.Timestamp) -> Path:
    return out / "overflows" / f"radar_overflows_{day:%Y-%m-%d}.parquet"


def start_overflow_dir(out: Path, overflows: pd.DataFrame, row: np.ndarray, col: np.ndarray,
                       n_block: np.ndarray, meta: dict) -> None:
    """Write overflow_pixels.parquet, or refuse if the folder was begun from another overflow table:
    one folder's day files must all come from the same table."""
    path = out / "overflows" / "overflow_pixels.parquet"
    if path.exists():
        had = (pq.read_schema(path).metadata or {}).get(b"overflows_sha256", b"").decode()
        if had != meta["overflows_sha256"]:
            raise SystemExit(f"{path.parent} was begun from overflow table {had[:12] or '?'}, not "
                             f"{meta['overflows_sha256'][:12]}: use another --out")
        return
    write_month(path, pd.DataFrame({"site_id": overflows.site_id, "lat": overflows.lat, "lon": overflows.lon,
                                    "row": row, "col": col, "block_pixels": n_block}), meta)


def day_hours(day: pd.Timestamp) -> pd.DatetimeIndex:
    """Open-Meteo's hours for a UTC day: labels 00:00 to 23:00, each the hour ending then."""
    return pd.date_range(day, periods=24, freq="h", tz="UTC")


# ------------------------------------------------------------------ the run
def run(start: str, end: str, cells: list[tuple[float, float]], out: Path = OUT,
        client: httpx.Client | None = None, pause_s: float = PAUSE_S,
        overflows: pd.DataFrame | None = None, overflow_meta: dict | None = None) -> dict:
    """Fetch and reduce every day from start to end (UTC, inclusive), for the cells and, if given, the
    overflows (site_id, lat, lon; overflow_meta goes in their files). Returns counts for the log."""
    days = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")
    today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
    if len(days) and days[-1] >= today:
        raise SystemExit(f"end {end} is not before today ({today:%Y-%m-%d} UTC): its last hours are not out yet")
    idx, lab, n_pix = cell_pixels(cells)
    for c, n in zip(cells, n_pix, strict=True):
        if n == 0:
            log.warning("cell %s has no radar pixel; it is left out", cell_key(*c))
    use = [k for k in range(len(cells)) if n_pix[k] > 0]
    # The overflows ride along as more groups after the cells: their 3 x 3 blocks, then their
    # centre pixels, so one reduce and one hourly serve all three.
    nc = len(cells)
    if overflows is not None:
        orow, ocol = overflow_pixels(overflows.lat.to_numpy(), overflows.lon.to_numpy())
        bidx, blab, bn = block_pixels(orow, ocol)
        cidx, clab, cn = block_pixels(orow, ocol, half=0)
        no = len(overflows)
        idx, lab = np.concatenate([idx, bidx, cidx]), np.concatenate([lab, blab + nc, clab + nc + no])
        n_pix = np.concatenate([n_pix, bn, cn])
        ov_use = np.flatnonzero(bn > 0)
        if len(ov_use) < no:
            log.warning("%d overflows have no radar pixel; they are left out", no - len(ov_use))
        start_overflow_dir(out, overflows, orow, ocol, bn, overflow_meta or {})
        ov_ids = overflows.site_id.to_numpy()[ov_use]
    own = client is None
    client = client or httpx.Client(headers=config.EA_HEADERS, timeout=TIMEOUT_S, follow_redirects=True)
    stats = {"days": 0, "skipped": 0, "files": 0, "missing": 0, "bad": 0, "rows": 0, "overflow_rows": 0}
    have: dict[tuple[int, pd.Timestamp], set] = {}    # (cell, month) -> hour times on disk
    snaps: dict[pd.Timestamp, tuple[np.ndarray, np.ndarray]] = {}
    try:
        for day in days:
            t0 = time.monotonic()
            day = day.tz_localize("UTC")
            month = day.tz_localize(None).to_period("M").to_timestamp()
            hours = day_hours(day)
            todo = []
            for k in use:
                if (k, month) not in have:
                    df = read_month(month_path(out, cells[k], month))
                    have[(k, month)] = set() if df is None else set(pd.to_datetime(df.time, utc=True))
                if not set(hours) <= have[(k, month)]:
                    todo.append(k)
            ov_todo = overflows is not None and not overflow_day_path(out, day).exists()
            if not todo and not ov_todo:
                stats["skipped"] += 1
                continue
            need = pd.date_range(hours[0] - 4 * STEP, hours[-1], freq=STEP)
            listing = {}
            for d in sorted({t.normalize() for t in need if t not in snaps}):
                listing.update(list_day(client, d))
            snaps = {t: v for t, v in snaps.items() if t >= need[0]}
            got = missing = 0
            for t in need:
                if t in snaps:
                    continue
                if t not in listing:
                    missing += 1
                    continue
                _sleep(pause_s)
                r = get(client, f"{BUCKET}/{listing[t]}")
                if r is None:
                    missing += 1
                    continue
                try:
                    rate = read_composite(r.content)
                except (OSError, KeyError) as e:   # a cut or damaged file: count it, go on
                    log.warning("%s: unreadable (%r)", listing[t], e)
                    stats["bad"] += 1
                    continue
                snaps[t] = reduce_snapshot(rate, idx, lab, len(n_pix))
                got += 1
            mm, cov = hourly(snaps, hours, n_pix)
            for k in todo:
                path = month_path(out, cells[k], month)
                new = pd.DataFrame({"cell_lat": cells[k][0], "cell_lon": cells[k][1], "time": hours,
                                    "radar_mm": np.round(mm[:, k], 3), "coverage": np.round(cov[:, k], 3)})
                old = read_month(path)
                df = new if old is None else pd.concat([old[~pd.to_datetime(old.time, utc=True).isin(hours)], new])
                df = df.sort_values("time").reset_index(drop=True)
                df["time"] = pd.to_datetime(df.time, utc=True).astype("datetime64[us, UTC]")
                write_month(path, df)
                have[(k, month)] |= set(hours)
                stats["rows"] += len(new)
            if ov_todo:
                block, centre = slice(nc, nc + no), slice(nc + no, nc + 2 * no)

                def per_site(a):   # (hours, overflows) to one column, each overflow's 24 hours together
                    return np.round(a.T[ov_use].ravel(), 3).astype(np.float32)

                df = pd.DataFrame({
                    "site_id": np.repeat(ov_ids, len(hours)),
                    "time": pd.to_datetime(np.tile(hours.tz_convert(None).to_numpy(), len(ov_use)), utc=True).astype("datetime64[us, UTC]"),
                    "radar_mm": per_site(mm[:, block]), "coverage": per_site(cov[:, block]),
                    "centre_mm": per_site(mm[:, centre]), "centre_coverage": per_site(cov[:, centre])})
                write_month(overflow_day_path(out, day), df, overflow_meta, compression="zstd")
                stats["overflow_rows"] += len(df)
            stats["days"] += 1
            stats["files"] += got
            stats["missing"] += missing
            log.info("%s: %d composites read, %d missing, %d cells written%s (%.0f s)",
                     f"{day:%Y-%m-%d}", got, missing, len(todo),
                     f", {len(ov_use)} overflows" if ov_todo else "", time.monotonic() - t0)
    finally:
        if own:
            client.close()
    return stats


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("start", help="first UTC day, YYYY-MM-DD")
    ap.add_argument("end", help="last UTC day, YYYY-MM-DD (before today)")
    ap.add_argument("--cells", type=Path, help="CSV with cell_lat,cell_lon or lat,lon")
    ap.add_argument("--cache", type=Path, default=config.CACHE / "rain",
                    help="rain cache whose forecast_/leads_ files name the default cells")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--pause", type=float, default=PAUSE_S, help="seconds between requests")
    ap.add_argument("--overflows", type=Path, help="overflows table (site_id, lat, lon, network_key) for "
                                                   "the per-overflow output")
    ap.add_argument("--no-cells", action="store_true", help="the overflows only, no rain cells")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if a.no_cells and not a.overflows:
        sys.exit("--no-cells needs --overflows")
    cells = [] if a.no_cells else read_cells(a.cells) if a.cells else default_cells(a.cache)
    if not cells and not a.no_cells:
        sys.exit(f"no cells: none in {a.cache} and no --cells")
    overflows, meta = read_overflows(a.overflows) if a.overflows else (None, None)
    log.info("%d cells, %s overflows -> %s", len(cells), len(overflows) if overflows is not None else 0, a.out)
    if meta:
        log.info("overflow table %s, network %s", meta["overflows_sha256"][:12], meta["network_key"])
    stats = run(a.start, a.end, cells, a.out, pause_s=a.pause, overflows=overflows, overflow_meta=meta)
    print(stats)


if __name__ == "__main__":
    main()
