"""The combined-v1 shadow (docs/COMBINED-SHADOW-2026-11.md, stated before any row was logged): for every overflow-day
of the nine English companies that a spot's forecast computes, at leads 0 to 4, the chance the frozen candidate
`combined-v1` would give, logged beside production's raw and lead-calibrated chance in its own table,
`shadow_combined_v1`, in the state database.

combined-v1 (docs/COMBINED-CANDIDATE-BACKTEST-2026-11.md, frozen at 4d66d7c7, nothing fitted):
  base      regional-v1's raw chance (shadow_regional.routed): v2 arm (b) at the eight companies other than United
            Utilities, production's raw chance at United Utilities;
  uplift    where the overflow's status is known at issue (model.live_status.status_known, the 8-hour stale rule), the
            base's log-odds plus logit(candidate of the lead) - logit(D2);
  fallback  where the status is not known, the base alone. The fallback is part of the candidate and is logged.

Every input is one the forecast has already read: production's own site-day frame (so no rain request), the build's
poll and the poll files. Nothing here changes a forecast: it returns new arrays, never alters its inputs, and is
called only inside guards that log and carry on if it fails. No page, alert, level or published score reads the
table, and it is not the issued-forecast history (forecast_overflows). It neither reads nor writes
shadow_regional_v1 or the live-status columns. Without every frozen file at its stated hash it is off.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from dipcast import config, shadow_regional
from dipcast.model import live_status
from dipcast.model.features import ALL_FEATURES

log = logging.getLogger(__name__)

RULE = "combined-v1"
TABLE = "shadow_combined_v1"
D2_FILE = config.PROCESSED / "combined" / "spill_model_nine_2024.pkl"
D2_SHA256 = "1603678923ccdd1553830fa67c2069714c0a836c9df7e8c52578aabd729b5bcc"
# The five live-status candidates, leads 0 to 4: the full hashes of #666's table. model.live_status checks a prefix.
CANDIDATE_SHA256 = {0: "deb5e1e5ee64df0e48e789b9b8eba9bb0be76fba4a23e6745f6a259cec436d00",
                    1: "e0756b1e97485d458bafb868480d73b8c95c502f4136aa05937cb166d3909c3e",
                    2: "ed5bb2b9a39ee222303e3c923b824deffde00e1c63eca89371a3800e51c894da",
                    3: "5180de7086c682fcfebcc9b02e12e197bbd7fb09d5aeb7dfeb940350d8a1360f",
                    4: "ecc835c96d707534d88dbecf6f286c59adb90839f31985926110b85ec4824066"}
# One stamp for the seven frozen files, on every row: v2, D2, then the candidates by lead.
MODELS = hashlib.sha256("".join([shadow_regional.V2_SHA256, D2_SHA256,
                                 *(CANDIDATE_SHA256[k] for k in sorted(CANDIDATE_SHA256))]).encode()).hexdigest()[:16]
CLIP = 1e-6                    # probabilities clipped to [CLIP, 1 - CLIP] before a logit (#666's stated setting)
LEADS = tuple(live_status.LEADS)
NINE = live_status.ENGLISH_NINE
# The read takes the latest forecast issued by this hour, local, on the issue day (forecast_log.DECISION_HOUR). A
# forecast issued later can never be that one, so it is not logged.
LOG_BY_HOUR = 8
# The stop rule: nothing is logged for an issue day after this. Extending or removing it is its own change.
LAST_ISSUE_DAY = date(2027, 1, 31)
COLUMNS = ("issued_at", "issue_day", "lat", "lon", "site_id", "company", "target_day", "lead", "p_combined", "applied",
           "p_base", "route", "p_candidate", "p_d2", "status_known", "spilling_at_issue", "spill_hours_24h",
           "spill_days_7d", "status_read_at", "rain_issued_at", "p_raw", "p_cal", "p_shown", "rule", "models", "version")


# ------------------------------------------------------------------ the frozen formula
def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, CLIP, 1 - CLIP)
    return np.log(p / (1 - p))


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def combine(base: np.ndarray, cand: np.ndarray, d2: np.ndarray, unknown: np.ndarray) -> np.ndarray:
    """combined-v1: the base's log-odds plus the status uplift where the status is known, the base where it is not.
    scripts/combined_candidate_backtest_2026.py's `combine`, kept here so a build does not import the harness; a
    test runs the two on the same numbers."""
    return np.where(unknown, base, sigmoid(logit(base) + logit(cand) - logit(d2)))


# ------------------------------------------------------------------ the frozen files
def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def parts() -> dict | None:
    """{"v2", "d2", "candidates"}: the seven frozen models, or None (the shadow is off) when any file is missing or
    is not the frozen one."""
    from dipcast.model.spill_model import SpillModel
    if not D2_FILE.exists():
        log.info("combined shadow off: %s missing", D2_FILE.name)
        return None
    got = _sha(D2_FILE)
    if got != D2_SHA256:
        log.warning("combined shadow off: %s is %s, not %s", D2_FILE.name, got[:12], D2_SHA256[:12])
        return None
    for k, want in CANDIDATE_SHA256.items():
        p = live_status.CANDIDATE_DIR / f"candidate_lead{k}.pkl"
        if not p.exists() or _sha(p) != want:
            log.warning("combined shadow off: %s is missing or is not the frozen file", p.name)
            return None
    v2, cands = shadow_regional.v2_model(), live_status.candidates()
    if v2 is None or sorted(cands) != list(LEADS):
        log.warning("combined shadow off: the regional or the live-status shadow is off")
        return None
    d2 = SpillModel.load(D2_FILE)
    if list(d2.features) != list(ALL_FEATURES):
        log.warning("combined shadow off: %s has inputs %s", D2_FILE.name, d2.features)
        return None
    return {"v2": v2, "d2": d2, "candidates": cands}


def clear_cache() -> None:
    parts.cache_clear()


# ------------------------------------------------------------------ the shadow forecast
def rain_issue_times(rain: pd.DataFrame | None, ov: pd.DataFrame) -> np.ndarray:
    """When the rain forecast at each overflow's cell was fetched (fetch_forecast's `issued_at`, the oldest where a
    cell has several), as UTC timestamps; NaT where the rain carries no issue time."""
    out = pd.Series(pd.NaT, index=range(len(ov)), dtype="datetime64[ns, UTC]")
    if rain is None or not len(rain) or "issued_at" not in rain or ov.empty:
        return out.to_numpy()
    from dipcast.ingest.rainfall import grid_cell
    cells = (rain.assign(issued_at=pd.to_datetime(rain["issued_at"], utc=True))
             .groupby(["cell_lat", "cell_lon"])["issued_at"].min())
    cl, cn = grid_cell(ov["lat"].to_numpy(), ov["lon"].to_numpy())
    keys = pd.MultiIndex.from_arrays([np.asarray(cl, float), np.asarray(cn, float)])
    return pd.Series(cells.reindex(keys).to_numpy(), dtype="datetime64[ns, UTC]").to_numpy()


def combined(sd: pd.DataFrame, ov: pd.DataFrame, days: pd.DatetimeIndex, today_idx: int, now: pd.Timestamp,
             p_raw: np.ndarray, rain: pd.DataFrame | None = None, routed: dict | None = None,
             models: dict | None = None, status_table: pd.DataFrame | None = None) -> dict | None:
    """combined-v1 for each of ov's overflows and days, from production's site-day frame `sd`, or None with the
    shadow off. Arrays are (n_overflows, n_days) unless said:
      "p"       combined-v1: the uplift where it applies, else the base; NaN where the day had no rain
      "uplift"  bool: the uplift was applied (an English overflow, status known, day today_idx + k for a lead k)
      "base"    regional-v1's raw chance; "v2" (n_overflows,) which rows took v2
      "cand"    the lead's live-status candidate, NaN where the status is not known or the day is not a lead 0 to 4
      "d2"      D2 on the same rows
      "known", "inputs", "read_at", "rain_at", "english"   (n_overflows,[3]): the status, its time, the rain's time
    `routed` is shadow_regional.routed's result for the same frame where the forecast has already computed it (the
    same frozen v2 file, so the same numbers; it saves a model pass); without it the base is computed here.
    `models` and `status_table` are for tests; a build reads the frozen files and the state directory's poll files."""
    models = models if models is not None else parts()
    if models is None or sd is None or ov.empty:
        return None
    if routed is None:
        routed = shadow_regional.routed(sd, ov, days, p_raw, model=models["v2"])
    if routed is None:
        return None
    base = routed["p"]
    table = status_table if status_table is not None else live_status._status_for(now.tz_convert(live_status.LOCAL_TZ).date())
    status = live_status.status_known(ov, now, table)
    known = status["status_known"].to_numpy(dtype=bool)
    cand = live_status.candidate_matrix(sd, ov, days, today_idx, status, models["candidates"])
    filled = sd.fillna({f: 0.0 for f in ALL_FEATURES})
    d2 = pd.Series(np.asarray(models["d2"].predict(filled), dtype=float), index=sd.index).where(sd["ok"].to_numpy())
    # Pivoted from the frame itself, as production and the regional shadow do, so the days keep their zone.
    d2 = (sd[["site_id", "day"]].assign(p=d2).pivot(index="site_id", columns="day", values="p")
          .reindex(index=ov["site_id"], columns=days).to_numpy(dtype=float))
    english = ov["company"].isin(NINE).to_numpy() if "company" in ov else np.zeros(len(ov), bool)
    uplift = english[:, None] & known[:, None] & np.isfinite(cand) & np.isfinite(d2) & np.isfinite(base)
    with np.errstate(invalid="ignore"):
        p = combine(base, cand, d2, ~uplift)
    read_at = pd.to_datetime(table["last_reading"].reindex(ov["site_id"].astype(str).to_numpy()), utc=True).to_numpy()
    return {"p": p, "uplift": uplift, "base": base, "v2": routed["v2"], "cand": cand, "d2": d2, "known": known,
            "inputs": status[live_status.STATUS].to_numpy(dtype=float), "read_at": read_at,
            "rain_at": rain_issue_times(rain, ov), "english": english}


# ------------------------------------------------------------------ the log
def logs(issued_at: pd.Timestamp) -> bool:
    """Whether a forecast issued at `issued_at` is logged: by LOG_BY_HOUR local on its issue day (so it can be the
    read's decision forecast), and not after LAST_ISSUE_DAY (the stop rule)."""
    from dipcast.forecast_log import LOCAL_TZ
    t = issued_at.tz_convert(LOCAL_TZ)
    by_cutoff = (t.hour, t.minute, t.second, t.microsecond) <= (LOG_BY_HOUR, 0, 0, 0)
    return by_cutoff and t.date() <= LAST_ISSUE_DAY


def log_shadow(issued_at: pd.Timestamp, lat: float, lon: float, days: pd.DatetimeIndex, ov: pd.DataFrame,
               p_raw: np.ndarray, p_cal: np.ndarray, p_shown: np.ndarray, shadow: dict, version: str | None,
               path=None) -> int:
    """Append one spot's shadow rows to TABLE: overflows of the nine English companies, leads 0 to 4, when `logs`
    says the forecast counts. `p_cal` is production after the lead map (the comparator); `p_shown` what the site
    published for the row (the same unless the live-status switch is on). Returns the rows written."""
    from dipcast.forecast_log import LOCAL_TZ, _LOCK, _conn, append_rows
    if not logs(issued_at):
        return 0
    issue_day = issued_at.tz_convert(LOCAL_TZ).date()

    def _f(x):
        return None if x is None or np.isnan(x) else float(x)

    def _t(x):
        return None if pd.isna(x) else pd.Timestamp(x)
    rows = []
    sites, comps = ov["site_id"].to_numpy(), ov["company"].to_numpy()
    for j, d in enumerate(days):
        lead = (d.date() - issue_day).days
        if lead not in LEADS:
            continue
        for i, sid in enumerate(sites):
            if not shadow["english"][i]:
                continue
            p = shadow["p"][i, j]
            applied = "no_rain" if np.isnan(p) else "uplift" if shadow["uplift"][i, j] else "fallback"
            known = bool(shadow["known"][i])
            rows.append((issued_at, issue_day, lat, lon, str(sid), str(comps[i]), d.date(), lead, _f(p), applied,
                         _f(shadow["base"][i, j]), "v2_offsets" if shadow["v2"][i] else "production",
                         _f(shadow["cand"][i, j]), _f(shadow["d2"][i, j]), known, *(_f(v) for v in shadow["inputs"][i]),
                         _t(shadow["read_at"][i]), _t(shadow["rain_at"][i]), _f(p_raw[i, j]), _f(p_cal[i, j]),
                         _f(p_shown[i, j]), RULE, MODELS, version))
    if not rows:
        return 0
    with _LOCK:
        con = _conn(path)
        try:
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    issued_at TIMESTAMPTZ, issue_day DATE, lat DOUBLE, lon DOUBLE, site_id VARCHAR, company VARCHAR,
                    target_day DATE, lead INTEGER, p_combined DOUBLE, applied VARCHAR, p_base DOUBLE, route VARCHAR,
                    p_candidate DOUBLE, p_d2 DOUBLE, status_known BOOLEAN, spilling_at_issue DOUBLE,
                    spill_hours_24h DOUBLE, spill_days_7d DOUBLE, status_read_at TIMESTAMPTZ,
                    rain_issued_at TIMESTAMPTZ, p_raw DOUBLE, p_cal DOUBLE, p_shown DOUBLE, rule VARCHAR,
                    models VARCHAR, version VARCHAR)""")
            append_rows(con, TABLE, COLUMNS, rows)
        finally:
            con.close()
    return len(rows)
