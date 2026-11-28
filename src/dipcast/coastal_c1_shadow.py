"""C1 at issue time on English beaches (docs/COASTAL-C1-SHADOW-2027.md): one logged row per coastal bathing water per
local day, May to September, with C1's over-500 chance from the forecast service's rain, C0's and R's, and every input.
A shadow: nothing here reaches the site. Written by the site's builds (build_site.py, after the coastal directory)."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config

log = logging.getLogger(__name__)

TABLE = "shadow_coastal_c1_v1"
RULE = "coastal-c1-shadow-2027"
FROZEN = Path(__file__).resolve().parents[2] / "data" / "research" / "coastal" / "c1_frozen.v1.json"
FROZEN_SHA256 = "90b390ba251c5ddb48ac9783902dfa1480cf822261f0edfd7e4736c3d99515e6"
MONTHS = (5, 6, 7, 8, 9)
FIRST_HOUR = 6           # the first build of the day at or after 06:00 local writes the day's row
MAX_AGE_H, MIN_COVER = 30.0, 0.9
CELLS_PER_BUILD = 20     # English beaches' own budget in the directory fetch, May to September
TZ = "Europe/London"
COLUMNS = ("issued_at", "issue_day", "site_id", "lat", "lon", "month", "rain_24h", "rain_72h", "rain_cell_lat",
           "rain_cell_lon", "rain_km", "rain_fetched_at", "last_ecoli", "last_taken_at", "site_rate", "p_c1",
           "p_c0", "p_r", "fallback", "rule", "model_sha", "version")


def frozen() -> dict | None:
    try:
        raw = FROZEN.read_bytes()
    except OSError:
        return None
    if hashlib.sha256(raw).hexdigest() != FROZEN_SHA256:
        log.warning("C1 shadow off: %s is not the frozen file", FROZEN.name)
        return None
    return json.loads(raw)


def in_season(now: pd.Timestamp) -> bool:
    return pd.Timestamp(now).tz_convert(TZ).month in MONTHS


def _window(cache_dir: Path, a: float, b: float, noon: pd.Timestamp, now: pd.Timestamp):
    """(rain 24 h, rain 72 h, fetched_at) at one cell to `noon`, or None: file missing, older than MAX_AGE_H by its own
    fetch time, or a window under MIN_COVER covered."""
    f = Path(cache_dir) / f"forecast_{a:.3f}_{b:.3f}.parquet"
    if not f.exists():
        return None
    try:
        d = pd.read_parquet(f, columns=["time", "precip_mm", "issued_at"])
    except Exception:  # noqa: BLE001 - a torn or older cache file counts as none
        return None
    fetched = pd.Timestamp(d["issued_at"].max())
    if now - fetched.tz_convert(TZ) > pd.Timedelta(hours=MAX_AGE_H):
        return None
    t = pd.to_datetime(d["time"], utc=True).dt.tz_convert(TZ)
    out = []
    for h in (24, 72):
        w = d.loc[(t > noon - pd.Timedelta(hours=h)) & (t <= noon), "precip_mm"]
        if w.notna().sum() < MIN_COVER * h:
            return None
        out.append(float(np.nansum(w)))
    return out[0], out[1], fetched


def rain_at(cache_dir: Path, lat: float, lon: float, noon: pd.Timestamp, now: pd.Timestamp):
    """(r24, r72, cell_lat, cell_lon, km, fetched_at): the site's own 0.1 degree cell first, else the nearest covered
    cell of the eight around it; None when none is covered."""
    a0, b0 = round(round(lat / 0.1) * 0.1, 1), round(round(lon / 0.1) * 0.1, 1)
    own = _window(cache_dir, a0 + 0.0, b0 + 0.0, noon, now)
    if own:
        return own[0], own[1], a0, b0, 0.0, own[2]
    best = None
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            if (i, j) == (0, 0):
                continue
            a, b = round(a0 + i / 10, 1) + 0.0, round(b0 + j / 10, 1) + 0.0
            got = _window(cache_dir, a, b, noon, now)
            if got:
                km = math.hypot((a - lat) * 111.2, (b - lon) * 111.2 * math.cos(math.radians(lat)))
                if best is None or km < best[4]:
                    best = (got[0], got[1], a, b, km, got[2])
    return best


def figures(doc: dict, site_id: str, month: int, last: float | None, r24: float | None, r72: float | None) -> dict:
    """C1, C0 and R's over-500 chance for one row, as C1's code (scripts/coastal_c1/c1.py, design and predict)."""
    tab, mods = doc["site_tables"]["over_500"], doc["models"]["over_500"]
    s = tab["sites"].get(site_id) or {"k": 0, "n": 0}
    rate = (s["k"] + tab["m"] * tab["p0"]) / (s["n"] + tab["m"])
    p = min(max(rate, 1e-6), 1 - 1e-6)
    base = [math.log(p / (1 - p))] + [1.0 if month == m else 0.0 for m in MONTHS[1:]]
    lastx = [0.0, 1.0] if last is None else [math.log10(max(float(last), 1.0)) - 1, 0.0]

    def pr(coef, x):
        z = coef[0] + float(np.dot(coef[1:], x))
        return 1 / (1 + math.exp(-z))
    out = {"site_rate": rate, "p_r": pr(mods["R"], base), "p_c0": pr(mods["C0"], base + lastx), "p_c1": None}
    if r24 is not None and r72 is not None:
        out["p_c1"] = pr(mods["C1"], base + lastx + [math.log1p(r24), math.log1p(r72)])
    return out


def rows_for(snapshot: dict, points: dict, now: pd.Timestamp, cache_dir: Path, done: set, version: str | None,
             doc: dict) -> list[tuple]:
    """The day's rows for sites with none yet today (`done`), or [] out of season or before FIRST_HOUR."""
    now = pd.Timestamp(now).tz_convert(TZ)
    if now.month not in MONTHS or now.hour < FIRST_HOUR:
        return []
    noon, day = now.normalize() + pd.Timedelta(hours=12), now.date()
    rows = []
    for site in snapshot.get("sites") or []:
        sid, p = site.get("id"), (points or {}).get(site.get("id"))
        if not sid or sid in done or not p:
            continue
        lat, lon = float(p[0]), float(p[1])
        smp = site.get("sample") or {}
        last, last_t = None, None
        if smp.get("state") == "ok" and smp.get("taken_at"):
            t = pd.Timestamp(smp["taken_at"]).tz_convert(TZ)
            v = (smp.get("ecoli") or {}).get("value")
            if t.year == now.year and t < now and v is not None:
                last, last_t = float(v), t
        rain = rain_at(cache_dir, lat, lon, noon, now)
        r24, r72, ca, cb, km, fetched = rain if rain else (None, None, None, None, None, None)
        f = figures(doc, sid, now.month, last, r24, r72)
        rows.append((now, day, sid, lat, lon, now.month, r24, r72, ca, cb, None if km is None else round(km, 2), fetched,
                     last, last_t, f["site_rate"], f["p_c1"], f["p_c0"], f["p_r"], None if f["p_c1"] is not None else "C0",
                     RULE, FROZEN_SHA256[:16], version))
    return rows


def log_day(snapshot: dict | None, points: dict | None, now, cache_dir: Path | None = None, version: str | None = None,
            path=None) -> dict:
    """Append today's rows to TABLE (the state database) for sites not yet logged today. Returns the build's health
    entry. Never raises."""
    from dipcast.forecast_log import _LOCK, _conn, append_rows
    out = {"rows": 0, "with_c1": 0}
    doc = frozen()
    if not snapshot or doc is None or not in_season(now):
        return {**out, "state": "off" if doc is None else "out of season" if snapshot else "no snapshot"}
    try:
        with _LOCK:
            con = _conn(path)
            try:
                con.execute(f"""
                    CREATE TABLE IF NOT EXISTS {TABLE} (
                        issued_at TIMESTAMPTZ, issue_day DATE, site_id VARCHAR, lat DOUBLE, lon DOUBLE, month INTEGER,
                        rain_24h DOUBLE, rain_72h DOUBLE, rain_cell_lat DOUBLE, rain_cell_lon DOUBLE, rain_km DOUBLE,
                        rain_fetched_at TIMESTAMPTZ, last_ecoli DOUBLE, last_taken_at TIMESTAMPTZ, site_rate DOUBLE,
                        p_c1 DOUBLE, p_c0 DOUBLE, p_r DOUBLE, fallback VARCHAR, rule VARCHAR, model_sha VARCHAR,
                        version VARCHAR)""")
                day = pd.Timestamp(now).tz_convert(TZ).date()
                done = {r[0] for r in con.execute(f"SELECT DISTINCT site_id FROM {TABLE} WHERE issue_day = ?", [day]).fetchall()}
                rows = rows_for(snapshot, points or {}, now, Path(cache_dir or config.CACHE / "rain"), done, version, doc)
                append_rows(con, TABLE, COLUMNS, rows)
            finally:
                con.close()
        return {"state": "ok", "rows": len(rows), "with_c1": sum(r[15] is not None for r in rows), "already": len(done)}
    except Exception as e:  # noqa: BLE001 - a shadow must never fail the build
        log.warning("C1 shadow log failed: %s", e)
        return {**out, "state": "error", "error": str(e) or type(e).__name__}
