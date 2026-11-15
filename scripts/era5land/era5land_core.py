"""What scripts/era5land/{fetch,to_cells,match_check}.py share (docs/ERA5-LAND-BULK-RAIN-2026-11.md): the CDS request
for one month, the grid and cell rules, reading a downloaded file, turning ERA5-Land's running total into hourly rain,
and the comparison sums. Pure functions only: nothing here sends a request, and nothing imports dipcast, so no build
path or cache is touched.

ERA5-Land facts this relies on (ECMWF's "ERA5-Land: data documentation", read 15 Nov 2026):
  * total_precipitation (tp) is in metres of water.
  * Accumulations run from 00 UTC. The value at 00 UTC is the total over the 24 hours ending then.
  * The CDS serves a regular 0.1 x 0.1 degree latitude/longitude grid.
"""

from __future__ import annotations

import calendar
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

DATASET = "reanalysis-era5-land"
VARIABLE = "total_precipitation"
GRID_DEG = 0.1
# North, West, South, East. Great Britain and Northern Ireland with a margin: every cached rain cell (49.9 to 60.2 N,
# 6.5 W to 1.8 E, measured 15 Nov 2026), Shetland, and Northern Ireland's west edge (about 8.2 W).
DEFAULT_AREA = (61.0, -8.3, 49.8, 2.0)
FIRST_MONTH = "1990-01"
# ERA5-Land's final data come about two months after the month (ECMWF's page). The default last month is three
# months back, so a default run never takes a preliminary (ERA5-Land-T) month that the CDS later replaces.
FINAL_LAG_MONTHS = 3
MIN_HOURS_PER_DAY = 20   # the same rule as dipcast.model.features.MIN_HOURS_PER_DAY (a test keeps them equal)

# A downloaded file's first bytes, by format.
MAGIC = {b"\x89HDF\r\n\x1a\n": "netcdf4", b"CDF\x01": "netcdf3", b"CDF\x02": "netcdf3", b"PK\x03\x04": "zip",
         b"GRIB": "grib"}


# ------------------------------------------------------------------ months and requests
def month_list(start: str, end: str) -> list[str]:
    """Every month from `start` to `end` inclusive, as "YYYY-MM"."""
    y0, m0 = (int(x) for x in start.split("-"))
    y1, m1 = (int(x) for x in end.split("-"))
    out = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def default_end(today: date) -> str:
    """The latest month a default run asks for: FINAL_LAG_MONTHS before today's month."""
    k = today.year * 12 + (today.month - 1) - FINAL_LAG_MONTHS
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def month_request(month: str, area: tuple[float, float, float, float] = DEFAULT_AREA) -> dict:
    """The CDS request for one month of hourly total_precipitation over `area` (N, W, S, E), as NetCDF, not zipped."""
    y, m = (int(x) for x in month.split("-"))
    days = calendar.monthrange(y, m)[1]
    return {
        "variable": [VARIABLE],
        "year": f"{y:04d}",
        "month": f"{m:02d}",
        "day": [f"{d:02d}" for d in range(1, days + 1)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [float(a) for a in area],
    }


def area_points(area: tuple[float, float, float, float] = DEFAULT_AREA) -> tuple[int, int]:
    """Grid rows and columns in `area` on the 0.1 degree grid (edges included)."""
    n, w, s, e = area
    return int(round((n - s) / GRID_DEG)) + 1, int(round((e - w) / GRID_DEG)) + 1


def month_hours(month: str) -> int:
    y, m = (int(x) for x in month.split("-"))
    return calendar.monthrange(y, m)[1] * 24


def upper_bytes(months: list[str], area: tuple[float, float, float, float] = DEFAULT_AREA) -> int:
    """An upper bound on the download: every grid point, every hour, as uncompressed 4-byte floats. The CDS's NetCDF is
    compressed and ERA5-Land has no value over the sea, so the real files should be smaller; the first downloaded month
    gives the real figure (fetch.py --status projects from it)."""
    rows, cols = area_points(area)
    return rows * cols * sum(month_hours(m) for m in months) * 4


def raw_file(out: Path, month: str) -> Path:
    return out / "raw" / month[:4] / f"era5land_tp_{month}.nc"


def out_ok(out: Path) -> str | None:
    """None when `out` may be written, else why not: nothing here writes inside a data/cache folder, since the shared
    caches are read-only for this work."""
    parts = Path(out).expanduser().resolve().parts
    for k in range(len(parts) - 1):
        if parts[k] == "data" and parts[k + 1] == "cache":
            return f"{out} is inside a data/cache folder; the shared caches are read-only here. Use a scratch folder."
    return None


def file_kind(head: bytes) -> str | None:
    for magic, kind in MAGIC.items():
        if head.startswith(magic):
            return kind
    return None


# ------------------------------------------------------------------ grid and cells
def snap(x) -> np.ndarray:
    """The 0.1 degree cell centre, the same rule as dipcast.ingest.rainfall.grid_cell (a test keeps them equal):
    round to the grid, round to 3 decimals, and add 0.0 so -0.0 becomes 0.0."""
    return np.round(np.round(np.asarray(x, dtype=float) / GRID_DEG) * GRID_DEG, 3) + 0.0


def cell_key(lat: float, lon: float) -> str:
    return f"{lat + 0.0:.3f}_{lon + 0.0:.3f}"


CELL_IN_NAME = re.compile(r"(-?\d+\.\d{3})_(-?\d+\.\d{3})")


def cell_from_name(name: str) -> tuple[float, float] | None:
    """The cell in a cache file name: archive_<lat>_<lon>_<tag>.parquet, or <lat>_<lon>.parquet."""
    m = CELL_IN_NAME.search(name)
    return (float(m.group(1)) + 0.0, float(m.group(2)) + 0.0) if m else None


def year_from_name(name: str) -> int | None:
    """The year of a cache file's tag (2024, 2023dec, 2026a), or None for a name without one."""
    m = re.search(r"_(\d{4})[a-z]*\.parquet$", name)
    return int(m.group(1)) if m else None


def map_cells(cells: list[tuple[float, float]], grid_lat: np.ndarray, grid_lon: np.ndarray, valid: np.ndarray,
              max_step: int = 1) -> pd.DataFrame:
    """Which grid point serves each cell. The cell's own point when it has data ("centre"). ERA5-Land has no value over
    the sea, so a coastal cell whose own point is sea takes the nearest point with data within `max_step` grid steps
    ("nearest with data"; distance on a flat earth scaled by cos(latitude), ties to the first in row then column
    order). Otherwise "none" (the cell gets no file), or "outside area" when the cell is not on the grid at all."""
    glat, glon = snap(grid_lat), snap(grid_lon)
    row = {v: i for i, v in enumerate(glat.tolist())}
    col = {v: j for j, v in enumerate(glon.tolist())}
    out = []
    for cl, cn in cells:
        cl, cn = float(snap(cl)), float(snap(cn))
        i, j = row.get(cl), col.get(cn)
        rec = {"cell_lat": cl, "cell_lon": cn, "i": -1, "j": -1, "grid_lat": np.nan, "grid_lon": np.nan,
               "how": "outside area", "km": np.nan}
        if i is None or j is None:
            out.append(rec)
            continue
        best = None
        if valid[i, j]:
            best = (0.0, i, j)
        else:
            coslat = np.cos(np.radians(cl))
            for di in range(-max_step, max_step + 1):
                for dj in range(-max_step, max_step + 1):
                    a, b = i + di, j + dj
                    if (di or dj) and 0 <= a < len(glat) and 0 <= b < len(glon) and valid[a, b]:
                        d = float(np.hypot(glat[a] - cl, (glon[b] - cn) * coslat)) * 111.2
                        if best is None or d < best[0] - 1e-9:
                            best = (d, a, b)
        if best is None:
            rec.update(how="none")
        else:
            d, a, b = best
            rec.update(i=a, j=b, grid_lat=float(glat[a]), grid_lon=float(glon[b]),
                       how="centre" if (a, b) == (i, j) else "nearest with data", km=round(d, 2))
        out.append(rec)
    return pd.DataFrame(out)


# ------------------------------------------------------------------ hourly rain from the running total
def deaccumulate(acc_m: np.ndarray, times: pd.DatetimeIndex) -> tuple[np.ndarray, int]:
    """Hourly rain in mm for the hour ending at each time, from ERA5-Land's running total in metres.

    tp at valid time t holds the rain from 00 UTC to t; at 00 UTC it holds the whole previous day. So the hour ending
    at 01 UTC is tp(01), and every other hour is tp(t) - tp(t - 1 h), the hour ending at 00 UTC included (the day's
    total less its first 23 hours). An hour whose previous step is missing (the first step of a series, or a gap) is
    NaN unless it ends at 01 UTC. Small negative differences come from the stored precision and are set to 0; the
    count of differences below -0.05 mm is returned, since many of those would mean the times are wrong.

    `acc_m` has time on its first axis; `times` are its UTC valid times."""
    acc = np.asarray(acc_m, dtype=float)
    t = pd.DatetimeIndex(times)
    if len(t) != acc.shape[0]:
        raise ValueError(f"{len(t)} times for {acc.shape[0]} steps")
    if t.tz is None:
        raise ValueError("times must be UTC-aware")
    inc = np.full(acc.shape, np.nan)
    first = np.asarray(t.hour == 1)
    inc[first] = acc[first]
    step_ok = np.zeros(len(t), dtype=bool)
    step_ok[1:] = np.asarray((t[1:] - t[:-1]) == pd.Timedelta(hours=1))
    k = np.where(~first & step_ok)[0]
    inc[k] = acc[k] - acc[k - 1]
    mm = inc * 1000.0
    big_negative = int(np.sum(mm < -0.05))
    mm = np.where(mm < 0, 0.0, mm)   # NaN stays NaN
    return mm, big_negative


def round_to(mm: np.ndarray, step: float) -> np.ndarray:
    """Round to `step` mm (0 leaves the values as they are). Open-Meteo serves hourly rain in 0.1 mm steps (every one
    of 1,435,488 cached values sampled on 15 Nov 2026), so 0.1 makes a drop-in for the cached files."""
    if not step:
        return mm
    return np.round(np.round(mm / step) * step, 6)


# ------------------------------------------------------------------ reading a downloaded file
@dataclass
class TpField:
    times: pd.DatetimeIndex   # UTC valid times
    lat: np.ndarray
    lon: np.ndarray           # -180 to 180
    tp: np.ndarray            # (time, lat, lon), metres, NaN where there is no value


_UNITS = {"second": "s", "seconds": "s", "minute": "min", "minutes": "min", "hour": "h", "hours": "h",
          "day": "D", "days": "D"}


def decode_times(values, units: str) -> pd.DatetimeIndex:
    """CF times ("hours since 1900-01-01 00:00:00.0", "seconds since 1970-01-01") as UTC."""
    m = re.match(r"\s*(\w+)\s+since\s+(.+?)\s*$", units)
    if not m or m.group(1).lower() not in _UNITS:
        raise ValueError(f"time units not understood: {units!r}")
    base = pd.Timestamp(re.sub(r"\s*(UTC|Z)$", "", m.group(2)))
    base = base.tz_localize("UTC") if base.tz is None else base.tz_convert("UTC")
    v = np.asarray(values)
    if np.issubdtype(v.dtype, np.floating) and np.any(v != np.round(v)):
        raise ValueError("fractional time steps")
    return pd.DatetimeIndex(base + pd.to_timedelta(v.astype("int64"), unit=_UNITS[m.group(1).lower()]))


def _attr(attrs, name):
    v = attrs.get(name)
    if v is None:
        return None
    if isinstance(v, bytes):
        return v.decode()
    a = np.asarray(v)
    if a.dtype.kind in "SO":
        x = a.reshape(-1)[0]
        return x.decode() if isinstance(x, bytes) else str(x)
    return a.reshape(-1)[0].item() if a.size else None


_PACKING = ("_FillValue", "missing_value", "scale_factor", "add_offset")


def _unpack(raw: np.ndarray, attrs) -> np.ndarray:
    """Fill values to NaN, then scale_factor and add_offset, as CF says."""
    x = np.asarray(raw)
    bad = np.zeros(x.shape, dtype=bool)
    for name in ("_FillValue", "missing_value"):
        fv = _attr(attrs, name)
        if fv is not None:
            bad |= x == fv
    out = x.astype(float)
    if out.dtype.kind == "f":
        bad |= np.isnan(out)
    sf, ao = _attr(attrs, "scale_factor"), _attr(attrs, "add_offset")
    if sf is not None:
        out = out * float(sf)
    if ao is not None:
        out = out + float(ao)
    out[bad] = np.nan
    return out


def _arrange(tp: np.ndarray, dims: list[str]) -> np.ndarray:
    """tp as (time, lat, lon). An extra axis of length 1 is dropped. An extra axis longer than 1 (an `expver` axis
    mixing final and preliminary data) is merged by taking, at each point, the first value with data along it."""
    named = {"time": None, "lat": None, "lon": None}
    for k, d in enumerate(dims):
        if d in named and named[d] is None:
            named[d] = k
    if None in named.values():
        raise ValueError(f"tp axes not recognised: {dims}")
    extra = [k for k in range(tp.ndim) if k not in named.values()]
    x = np.moveaxis(tp, [named["time"], named["lat"], named["lon"]], [0, 1, 2])
    for _ in extra:   # after moveaxis the extras sit at the end
        if x.shape[-1] == 1:
            x = x[..., 0]
        else:
            merged = x[..., 0].copy()
            for e in range(1, x.shape[-1]):
                merged = np.where(np.isnan(merged), x[..., e], merged)
            x = merged
    return x


def _dim_role(name: str) -> str:
    n = name.strip("/").lower()
    if n in ("time", "valid_time"):
        return "time"
    if n in ("latitude", "lat"):
        return "lat"
    if n in ("longitude", "lon"):
        return "lon"
    return n


def _read_hdf5(buf) -> TpField:
    import h5py   # the era5 extra; only NetCDF4 files need it
    with h5py.File(buf, "r") as f:
        tname = "valid_time" if "valid_time" in f else "time"
        tvar = f[tname]
        times = decode_times(tvar[...], _attr(tvar.attrs, "units") or "")
        lat = np.asarray(f["latitude"][...], dtype=float)
        lon = np.asarray(f["longitude"][...], dtype=float)
        ds = f["tp"]
        dims = []
        for k in range(ds.ndim):
            scales = ds.dims[k]
            if len(scales):
                dims.append(_dim_role(scales[0].name))
            else:   # no dimension scale attached: match by length
                n = ds.shape[k]
                dims.append("time" if n == len(times) else "lat" if n == len(lat) else "lon" if n == len(lon)
                            else f"axis{k}")
        tp = _unpack(ds[...], {k: ds.attrs[k] for k in _PACKING if k in ds.attrs})
    return TpField(times, lat, lon, _arrange(tp, dims))


def _read_netcdf3(buf) -> TpField:
    from scipy.io import netcdf_file
    with netcdf_file(buf, "r", mmap=False, maskandscale=False) as f:
        v = f.variables
        tname = "valid_time" if "valid_time" in v else "time"
        tunits = v[tname]._attributes.get("units", b"")
        times = decode_times(v[tname].data.copy(), tunits.decode() if isinstance(tunits, bytes) else tunits)
        lat = np.asarray(v["latitude"].data, dtype=float).copy()
        lon = np.asarray(v["longitude"].data, dtype=float).copy()
        tp = _unpack(v["tp"].data.copy(), dict(v["tp"]._attributes))
        dims = [_dim_role(d) for d in v["tp"].dimensions]
    return TpField(times, lat, lon, _arrange(tp, dims))


def _combine(parts: list[TpField]) -> TpField:
    if len(parts) == 1:
        return parts[0]
    a = parts[0]
    for p in parts[1:]:
        if not (np.array_equal(p.lat, a.lat) and np.array_equal(p.lon, a.lon)):
            raise ValueError("files in one download on different grids")
    times = pd.DatetimeIndex(np.concatenate([p.times.tz_convert(None).to_numpy() for p in parts])).tz_localize("UTC")
    tp = np.concatenate([p.tp for p in parts], axis=0)
    order = np.argsort(times.to_numpy(), kind="stable")
    return TpField(times[order], a.lat, a.lon, tp[order])


def read_tp(path: Path | str | bytes) -> TpField:
    """One downloaded month as (time, lat, lon) in metres, latitude north to south or as stored, longitude -180 to 180.
    NetCDF4 (HDF5, needs h5py) and classic NetCDF are read; a zip of either is opened in memory; GRIB is refused."""
    data = path if isinstance(path, bytes) else Path(path).read_bytes()
    kind = file_kind(data[:8])
    if kind == "zip":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            parts = [read_tp(z.read(n)) for n in sorted(z.namelist()) if not n.endswith("/")]
        return _combine(parts)
    if kind == "netcdf4":
        f = _read_hdf5(io.BytesIO(data))
    elif kind == "netcdf3":
        f = _read_netcdf3(io.BytesIO(data))
    elif kind == "grib":
        raise ValueError("GRIB is not read here: ask for data_format netcdf")
    else:
        raise ValueError(f"not a NetCDF or zip file (starts {data[:8]!r})")
    lon = np.where(f.lon > 180, f.lon - 360, f.lon)
    return TpField(f.times, f.lat, lon, f.tp)


# ------------------------------------------------------------------ comparison sums
class Moments:
    """Running sums for a pooled Pearson correlation, mean difference and counts, so a comparison over millions of
    cell-hours never holds them all at once."""

    def __init__(self):
        self.n = 0
        self.sx = self.sy = self.sxx = self.syy = self.sxy = 0.0

    def add(self, x: np.ndarray, y: np.ndarray) -> None:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        ok = np.isfinite(x) & np.isfinite(y)
        x, y = x[ok], y[ok]
        self.n += len(x)
        self.sx += x.sum()
        self.sy += y.sum()
        self.sxx += (x * x).sum()
        self.syy += (y * y).sum()
        self.sxy += (x * y).sum()

    def r(self) -> float:
        if self.n < 2:
            return float("nan")
        cov = self.sxy - self.sx * self.sy / self.n
        vx = self.sxx - self.sx ** 2 / self.n
        vy = self.syy - self.sy ** 2 / self.n
        return float(cov / np.sqrt(vx * vy)) if vx > 0 and vy > 0 else float("nan")

    def mean_x(self) -> float:
        return self.sx / self.n if self.n else float("nan")

    def mean_y(self) -> float:
        return self.sy / self.n if self.n else float("nan")

    def bias(self) -> float:
        """Mean of x - y."""
        return (self.sx - self.sy) / self.n if self.n else float("nan")


def pearson(x, y) -> float:
    m = Moments()
    m.add(x, y)
    return m.r()


def daily_pairs(hourly: pd.DataFrame, min_hours: int = MIN_HOURS_PER_DAY) -> pd.DataFrame:
    """Daily totals of paired hours (columns time, era, ref), on UTC days of the hour-ending label, as the model's
    features take them (dipcast.model.features.daily_rain_features: time.dt.floor("D")). A day with fewer than
    `min_hours` paired hours is left out, as the features make it unknown."""
    d = hourly.assign(day=hourly["time"].dt.floor("D"))
    g = d.groupby("day", sort=True).agg(era=("era", "sum"), ref=("ref", "sum"), hours=("era", "size"))
    return g[g["hours"] >= min_hours].reset_index()
