"""The radar shadow's radar step (docs/RADAR-SHADOW-2026-11.md): once per build, the Met Office composites the
build's rain cells need for the hours from two local days before today up to now, reduced to hourly rain per cell
the way scripts/fetch_met_office_radar.py does it (dipcast.ingest.met_office_radar).

Each composite read is reduced to per-cell sums and kept in the state directory (SNAPSHOTS), so the next build
fetches only the composites published since. That file stays in the build's actions cache: the state release's
upload list does not name it, so no radar value is published. Every hour carries the time its last composite
reached the bucket (`published_at`, the listing's LastModified), so an hour counts as known at the issue time only
if the listing the build read held all of it.

Caps (the statement's): MAX_FILES composites and MAX_SECONDS seconds per build, one request at a time, PAUSE_S
apart, no retry. Over a cap, the build's radar is not used (`fallback`) and the counter in STATUS_FILE goes up;
STOP_AFTER builds over a cap in a row stop the step (`stopped`) until that file is deleted by hand.

Nothing here touches a forecast. h5py is needed only to read a composite (the optional `radar` group, which the
build installs only when DIPCAST_RADAR_SHADOW=1); without it the step returns `fallback` and logs why.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest import met_office_radar as mor

log = logging.getLogger(__name__)

SNAPSHOTS = "radar_snapshots_v1.parquet"   # in config.STATE; the actions cache keeps it, the release does not
STATUS_FILE = "radar_shadow_status.json"  # consecutive builds over a cap
MAX_FILES = 300          # composites per build: a cold start needs at most 289 (72 hours and the one before)
MAX_SECONDS = 240.0      # the whole step, listing included
MAX_LISTINGS = 5         # one per UTC day touched, and a continuation page if the bucket sends one
PAUSE_S = 0.2
TIMEOUT_S = 20.0
STALE_MIN = 90.0         # the newest composite listed older than this at listing time: the feed is down
MIN_COVERAGE = 0.9       # an hour counts only with this share of its pixel samples (as #694)
STOP_AFTER = 3

_sleep = time.sleep      # replaced in tests
_clock = time.monotonic  # replaced in tests


@dataclass
class RadarHours:
    """The radar a build holds. `hours`: cell_lat, cell_lon, time (UTC, hour-ending), radar_mm, coverage,
    published_at. `state`: ok, fallback or stopped (a build-wide state; an hour's own gaps are per hour)."""
    state: str
    listed_at: pd.Timestamp | None = None
    newest_scan: pd.Timestamp | None = None
    newest_modified: pd.Timestamp | None = None
    hours: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(
        columns=["cell_lat", "cell_lon", "time", "radar_mm", "coverage", "published_at"]))
    reason: str = ""
    stats: dict = field(default_factory=dict)

    def usable(self) -> bool:
        return self.state == "ok" and not self.hours.empty


def _h5py_ok() -> bool:
    """Whether a composite can be read (h5py, the optional `radar` group). Checked before any request."""
    try:
        import h5py  # noqa: F401
    except ImportError:
        return False
    return True


def window_start(now: pd.Timestamp) -> pd.Timestamp:
    """The first hour the shadow needs (UTC, hour-ending label): 00:00 local two days before now's local day, the
    label daily_rain_features puts first in that day."""
    local = now.tz_convert("Europe/London")
    d2 = (local.normalize() - pd.DateOffset(days=2))
    return d2.tz_convert("UTC")


def cells_key(cells: list[tuple[float, float]]) -> str:
    return hashlib.sha256(json.dumps(sorted([round(a, 3), round(b, 3)] for a, b in cells)).encode()).hexdigest()[:16]


# ------------------------------------------------------------------ the bucket
def list_day(client, day: pd.Timestamp, budget: list[int]) -> dict[pd.Timestamp, tuple[str, pd.Timestamp, int]]:
    """The composites under radar/YYYY/MM/DD/: scan time -> (key, LastModified, bytes). Raises on any failure; no
    retry (a build does not wait). `budget` is the listing requests left, decremented here."""
    prefix = f"radar/{day:%Y/%m/%d}/"
    out, token = {}, None
    while True:
        if budget[0] <= 0:
            raise RuntimeError("listing cap reached")
        budget[0] -= 1
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        r = client.get(mor.BUCKET + "/", params=params)
        if r.status_code == 404:
            return out
        r.raise_for_status()
        root = ET.fromstring(r.content)
        ns = {"s3": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
        q = (lambda tag: f"s3:{tag}") if ns else (lambda tag: tag)
        for el in root.iterfind(q("Contents"), ns):
            key = el.findtext(q("Key"), default="", namespaces=ns)
            m = mor.KEY_RE.match(key)
            if m:
                mod = pd.Timestamp(el.findtext(q("LastModified"), default="", namespaces=ns)).tz_convert("UTC")
                size = int(el.findtext(q("Size"), default="0", namespaces=ns) or 0)
                out[pd.Timestamp(m[1], tz="UTC")] = (key, mod, size)
        token = root.findtext(q("NextContinuationToken"), default=None, namespaces=ns)
        if not token:
            return out


# ------------------------------------------------------------------ the carried snapshots
def read_snapshots(path, key: str) -> pd.DataFrame:
    """The carried per-cell sums (time, last_modified, cell, sum, count), or an empty frame when there is none or it
    was made for another cell set."""
    empty = pd.DataFrame({"time": pd.Series(dtype="datetime64[ns, UTC]"),
                          "last_modified": pd.Series(dtype="datetime64[ns, UTC]"),
                          "cell": pd.Series(dtype="int64"), "sum": pd.Series(dtype=float),
                          "count": pd.Series(dtype=float)})
    if not path.exists():
        return empty
    try:
        import pyarrow.parquet as pq
        meta = pq.read_schema(path).metadata or {}
        if meta.get(b"cells_key", b"").decode() != key:
            log.info("radar shadow: carried snapshots are for another cell set; starting again")
            return empty
        df = pd.read_parquet(path)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df["last_modified"] = pd.to_datetime(df["last_modified"], utc=True)
        return df
    except Exception as e:  # noqa: BLE001 - a damaged carry is a cold start, never a failed build
        log.warning("radar shadow: carried snapshots unreadable (%s); starting again", e)
        return empty


def write_snapshots(path, df: pd.DataFrame, key: str) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    t = pa.Table.from_pandas(df.reset_index(drop=True), preserve_index=False)
    t = t.replace_schema_metadata({**(t.schema.metadata or {}), b"cells_key": key.encode(),
                                   b"credit": mor.CREDIT.encode()})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(t, tmp, compression="zstd")
    tmp.replace(path)


def _status(path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {"over_cap_in_a_row": 0}


def _set_status(path, st: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, indent=1, default=str))


# ------------------------------------------------------------------ the step
def to_hours(snaps: pd.DataFrame, cells: list[tuple[float, float]], n_pix: np.ndarray, first: pd.Timestamp,
             last: pd.Timestamp) -> pd.DataFrame:
    """Hourly rain per cell from the snapshots, hours labelled first to last (UTC, hour-ending), with each hour's
    coverage (met_office_radar.hourly) and published_at: the latest LastModified among its composites."""
    hours = pd.date_range(first, last, freq="h")
    if len(hours) == 0 or not len(cells):
        return RadarHours("fallback").hours
    nc = len(cells)
    by_t = {}
    for t, g in snaps[snaps["cell"] >= 0].groupby("time"):
        s = np.zeros(nc)
        c = np.zeros(nc)
        s[g["cell"].to_numpy()] = g["sum"].to_numpy()
        c[g["cell"].to_numpy()] = g["count"].to_numpy()
        by_t[pd.Timestamp(t)] = (s, c)
    mm, cov = mor.hourly(by_t, hours, n_pix)
    mod = snaps.groupby("time")["last_modified"].max()
    pub = pd.Series([max((mod.get(t - (4 - i) * mor.STEP, pd.NaT) for i in range(5)),
                         key=lambda x: pd.Timestamp.min.tz_localize("UTC") if pd.isna(x) else x) for t in hours],
                    index=hours)
    cl = np.array([c[0] for c in cells])
    cn = np.array([c[1] for c in cells])
    return pd.DataFrame({"cell_lat": np.tile(cl, len(hours)), "cell_lon": np.tile(cn, len(hours)),
                         "time": np.repeat(hours, nc), "radar_mm": mm.ravel(), "coverage": cov.ravel(),
                         "published_at": np.repeat(pd.to_datetime(pub.to_numpy(), utc=True), nc)})


def update(cells: list[tuple[float, float]], now: pd.Timestamp | None = None, client=None,
           state_dir=None) -> RadarHours:
    """The build's radar step. Never raises: any failure is a `fallback` with its reason."""
    t0 = _clock()
    clock_now = now is None    # a build reads the clock; a test gives the time
    now = pd.Timestamp.now(tz="UTC") if now is None else now.tz_convert("UTC")
    state_dir = config.STATE if state_dir is None else state_dir
    snap_path, status_path = state_dir / SNAPSHOTS, state_dir / STATUS_FILE
    st = _status(status_path)
    stats = {"files": 0, "bytes": 0, "listings": 0, "cells": len(cells), "seconds": 0.0}
    if st.get("over_cap_in_a_row", 0) >= STOP_AFTER:
        return RadarHours("stopped", reason=f"{STOP_AFTER} builds in a row over a cap; delete {STATUS_FILE} to restart",
                          stats=stats)
    cells = sorted({(round(float(a), 3), round(float(b), 3)) for a, b in cells})
    if not cells:
        return RadarHours("fallback", reason="no cells", stats=stats)
    if not _h5py_ok():
        return RadarHours("fallback", reason="h5py not installed (uv sync --extra radar)", stats=stats)
    over_cap = False
    own = client is None
    try:
        import httpx
        client = client or httpx.Client(headers={"User-Agent": config.USER_AGENT}, timeout=TIMEOUT_S,
                                        follow_redirects=True)
        key = cells_key(cells)
        idx, lab, n_pix = mor.cell_pixels(cells)
        first = window_start(now)
        need_from = first - 4 * mor.STEP
        snaps = read_snapshots(snap_path, key)
        snaps = snaps[snaps["time"] >= need_from]

        budget = [MAX_LISTINGS]
        listing: dict = {}
        for d in pd.date_range(need_from.floor("D"), now.floor("D"), freq="D"):
            listing.update(list_day(client, d, budget))
        stats["listings"] = MAX_LISTINGS - budget[0]
        listed_at = pd.Timestamp.now(tz="UTC") if clock_now else now
        now = listed_at
        listing = {t: v for t, v in listing.items() if need_from <= t <= now}
        if not listing:
            raise RuntimeError("the listing holds no composite for the window")
        newest = max(listing)
        newest_mod = max(v[1] for v in listing.values())
        if (now - newest) > pd.Timedelta(minutes=STALE_MIN):
            raise RuntimeError(f"newest composite {newest:%Y-%m-%d %H:%M} is over {STALE_MIN:.0f} min old")

        have = set(snaps["time"])
        todo = sorted(t for t in listing if t not in have)
        rows = []
        for t in todo:
            if stats["files"] >= MAX_FILES or _clock() - t0 > MAX_SECONDS:
                over_cap = True
                break
            _sleep(PAUSE_S)
            r = client.get(f"{mor.BUCKET}/{listing[t][0]}")
            r.raise_for_status()
            stats["files"] += 1
            stats["bytes"] += len(r.content)
            # A marker row (cell -1) records every composite read, so one with no data in any cell, or a damaged
            # one, is not fetched again by the next build.
            mark = pd.DataFrame({"time": [t], "last_modified": [listing[t][1]], "cell": [-1], "sum": [0.0],
                                 "count": [0.0]})
            try:
                rate = mor.read_composite(r.content)
            except (OSError, KeyError) as e:   # a damaged file: its hour loses coverage, the build goes on
                log.warning("radar shadow: %s unreadable (%r)", listing[t][0], e)
                rows.append(mark)
                continue
            s, c = mor.reduce_snapshot(rate, idx, lab, len(cells))
            k = np.flatnonzero(c > 0)
            rows.append(pd.concat([mark, pd.DataFrame({"time": t, "last_modified": listing[t][1], "cell": k,
                                                       "sum": s[k], "count": c[k]})], ignore_index=True))
        if rows:
            snaps = pd.concat([snaps, *rows], ignore_index=True)
        # A snapshot no longer listed (deleted or never there) is still a reading; keep what was read.
        write_snapshots(snap_path, snaps, key)
        stats["seconds"] = round(_clock() - t0, 1)
        st["over_cap_in_a_row"] = st.get("over_cap_in_a_row", 0) + 1 if over_cap else 0
        st["last"] = {"at": str(now), **stats, "over_cap": over_cap}
        _set_status(status_path, st)
        if over_cap:
            return RadarHours("fallback", listed_at, newest, newest_mod, reason="over a cap", stats=stats)
        hours = to_hours(snaps, cells, n_pix, first, now.floor("h"))
        return RadarHours("ok", listed_at, newest, newest_mod, hours=hours, stats=stats)
    except Exception as e:  # noqa: BLE001 - the radar step must never fail a build
        stats["seconds"] = round(_clock() - t0, 1)
        log.warning("radar shadow: radar not used this build: %s", e)
        return RadarHours("fallback", reason=str(e)[:200], stats=stats)
    finally:
        if own and client is not None:
            client.close()
