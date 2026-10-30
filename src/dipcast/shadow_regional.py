"""The regional routing shadow (docs/REGIONAL-ROUTING-2026-11.md, section 4): for every overflow-day a spot's
forecast computes, the chance the frozen rule `regional-v1` would give, logged beside production's raw and shown
(lead-calibrated) chance in its own table, `shadow_regional_v1`, in the state database.

regional-v1: the eight companies other than United Utilities take the nine-company v2 model, arm (b) (SHA-256
V2_SHA256, committed at data/processed/regional/); United Utilities, every other company and a row with no company
keep production's chance. Both models read the same site-day frame (forecast.spill_probabilities' own, with its fill
and its missing-rain rule), so the shadow costs no rain request.

Nothing here changes a forecast: it returns new arrays, never alters its inputs, and is called only inside guards
that log and carry on if it fails. No page, alert, level or published score reads the table, and it is not the
issued-forecast history (forecast_overflows). Without the model file, or with a file of another hash, it is off.
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.model.features import ALL_FEATURES

log = logging.getLogger(__name__)

RULE = "regional-v1"
TABLE = "shadow_regional_v1"
V2_FILE = config.PROCESSED / "regional" / "spill_model_v2_offsets.pkl"
V2_SHA256 = "9e0fc54a9356e4cea528606422dc569691453fc3ab98ea31986f19437ba501f2"
EIGHT = ("Anglian Water", "Northumbrian Water", "Severn Trent Water", "South West Water", "Southern Water",
         "Thames Water", "Wessex Water", "Yorkshire Water")
COLUMNS = ("issued_at", "issue_day", "lat", "lon", "site_id", "company", "target_day", "lead", "p_regional", "route",
           "p_raw", "p_cal", "rule", "v2_sha", "version")


@lru_cache(maxsize=1)
def v2_model():
    """The frozen v2 model, or None (the shadow is off) when the file is missing or is not the frozen one."""
    from dipcast.model.spill_model import SpillModel
    if not V2_FILE.exists():
        log.info("regional shadow off: %s missing", V2_FILE.name)
        return None
    got = hashlib.sha256(V2_FILE.read_bytes()).hexdigest()
    if got != V2_SHA256:
        log.warning("regional shadow off: %s is %s, not %s", V2_FILE.name, got[:12], V2_SHA256[:12])
        return None
    return SpillModel.load(V2_FILE)


def clear_cache() -> None:
    v2_model.cache_clear()


def routed(sd: pd.DataFrame, ov: pd.DataFrame, days: pd.DatetimeIndex, p_raw: np.ndarray, model=None) -> dict | None:
    """regional-v1's chance for each of ov's overflows and days, from production's site-day frame `sd`, or None with
    the shadow off. "p" (n_overflows, n_days): v2 where the overflow's company is one of the eight, else `p_raw`;
    NaN where the day had no rain, as production. "v2" (n_overflows,): which rows took v2."""
    model = model if model is not None else v2_model()
    if model is None or sd is None or ov.empty:
        return None
    filled = sd.fillna({f: 0.0 for f in ALL_FEATURES})
    p = pd.Series(np.asarray(model.predict(filled), dtype=float), index=sd.index).where(sd["ok"].to_numpy())
    # Pivoted from the frame itself, as production does, so the days keep their zone and match `days`.
    mat = (sd[["site_id", "day"]].assign(p=p).pivot(index="site_id", columns="day", values="p")
           .reindex(index=ov["site_id"], columns=days).to_numpy(dtype=float))
    use = ov["company"].isin(EIGHT).to_numpy()
    return {"p": np.where(use[:, None], mat, p_raw), "v2": use}


def log_shadow(issued_at: pd.Timestamp, lat: float, lon: float, days: pd.DatetimeIndex, ov: pd.DataFrame,
               p_raw: np.ndarray, p_cal: np.ndarray, shadow: dict, version: str | None, path=None) -> int:
    """Append one spot's shadow rows (leads 0 and later) to TABLE; returns the rows written."""
    from dipcast.forecast_log import LOCAL_TZ, _LOCK, _conn
    issue_day = issued_at.tz_convert(LOCAL_TZ).date()

    def _f(x):
        return None if x is None or np.isnan(x) else float(x)
    rows = []
    sites, comps = ov["site_id"].to_numpy(), ov["company"].to_numpy()
    for j, d in enumerate(days):
        lead = (d.date() - issue_day).days
        if lead < 0:
            continue
        for i, sid in enumerate(sites):
            rows.append((issued_at, issue_day, lat, lon, str(sid), None if pd.isna(comps[i]) else str(comps[i]),
                         d.date(), lead, _f(shadow["p"][i, j]), "v2_offsets" if shadow["v2"][i] else "production",
                         _f(p_raw[i, j]), _f(p_cal[i, j]), RULE, V2_SHA256[:16], version))
    if not rows:
        return 0
    with _LOCK:
        con = _conn(path)
        try:
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    issued_at TIMESTAMPTZ, issue_day DATE, lat DOUBLE, lon DOUBLE, site_id VARCHAR, company VARCHAR,
                    target_day DATE, lead INTEGER, p_regional DOUBLE, route VARCHAR, p_raw DOUBLE, p_cal DOUBLE,
                    rule VARCHAR, v2_sha VARCHAR, version VARCHAR)""")
            con.executemany(f"INSERT INTO {TABLE} ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})", rows)
        finally:
            con.close()
    return len(rows)
