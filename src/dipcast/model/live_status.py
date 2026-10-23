"""The overflow's own spill status as an input to the spill model, run in shadow
(docs/LIVE-STATUS-SHADOW-TEST-2026-10.md).

The feature test (docs/LIVE-STATUS-FEATURE-TEST-2026-10.md) fitted one candidate per lead 0 to 4:
the nine-company model with three status inputs added, fitted on the EA's 2024 start/stop events. On
2025 it beat the same model without the inputs at every lead. It is not deployed: it needs a confirmation on status read from SwimSignal's own polls, and a rule for an overflow whose
status is missing.

This module gives both, for the forecast log only:
- `status_table` reads the three inputs from the poller's files (live_history.parquet,
  live_coverage.parquet), as the feature test's statement said production would compute them;
- `status_known` says, per overflow, whether its status is current and its last seven days were
  watched closely enough to trust the counts (MAX_GAP_H, from the poller's cadence);
- `shadow_forecast` runs the candidate of each lead where the status is known, and gives the
  production forecast (the calibrated chance the site shows) where it is not.

Nothing here reaches a page, an alert, a score the site publishes or the headline. The candidates
are read from CANDIDATE_DIR; without them the shadow is off and the log's columns stay NULL.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.model.features import ALL_FEATURES
from dipcast.model.spill_model import SpillModel

log = logging.getLogger(__name__)

LOCAL_TZ = "Europe/London"
STATUS = ["spilling_at_issue", "spill_hours_24h", "spill_days_7d"]
LEADS = range(5)
CANDIDATE_DIR = config.PROCESSED / "live_status"
# The five candidates the feature test scored (its results, "Checks of the code"): SHA-256 prefixes, leads 0
# to 4. A file that does not match is not run: the shadow would test something other than what the test judged.
CANDIDATE_SHA = {0: "deb5e1e5ee64", 1: "e0756b1e9748", 2: "ed5bb2b9a39e", 3: "5180de7086c6", 4: "ecc835c96d70"}
WINDOW_DAYS = 7          # spill_days_7d reads the seven local days before the issue day
# The longest stretch without a current reading of an overflow, over its seven-day window and up to the
# issue time, for its status to count as known. From the poller's cadence: the poll runs inside the site
# build, and over 28 Sep to 20 Oct 2026 (266 gaps between polls, poll_log.parquet in the state release
# of 20 Oct 05:44 UTC) the gap was a median 1.05 h, 6.43 h at the 95th percentile, 7.30 h at the 99th
# and 7.71 h at most. 8 h is the first whole hour above every gap seen, so the poller's own timetable
# never makes a status stale; a feed that stops, a frozen record, an offline monitor or a poll that
# missed the overflow does. It is the scorer's MAX_GAP_H (forecast_log), set from the same cadence,
# so the inputs and the labels they are scored against trust the same polls.
MAX_GAP_H = 8.0
SLOT_H = 0.5             # live_coverage.parquet keeps one bit per half-hour slot of a local day


# ------------------------------------------------------------------ candidates
@lru_cache(maxsize=1)
def candidates() -> dict[int, SpillModel]:
    """The five candidates by lead, or {} (the shadow is off) if any is missing or not the tested file."""
    out = {}
    for k in LEADS:
        p = CANDIDATE_DIR / f"candidate_lead{k}.pkl"
        if not p.exists():
            log.info("live-status shadow off: %s missing", p.name)
            return {}
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if not sha.startswith(CANDIDATE_SHA[k]):
            log.warning("live-status shadow off: %s is %s, not PR #254's %s", p.name, sha[:12], CANDIDATE_SHA[k])
            return {}
        m = SpillModel.load(p)
        if list(m.features) != [*ALL_FEATURES, *STATUS]:
            log.warning("live-status shadow off: %s has inputs %s", p.name, m.features)
            return {}
        out[k] = m
    return out


# ------------------------------------------------------------------ status from the polls
def poll_events(history: pd.DataFrame) -> pd.DataFrame:
    """Spill intervals (site_id, start, end, UTC) from live_history.parquet, by the rule
    forecast_log.observed_spill_days uses for the labels: the latest event's start and end as a poll
    saw them; a spill still running at a poll ends at that poll; one discharging with no event times
    is a spill at that poll's moment. A later poll of a running spill extends it."""
    h = history
    start = pd.to_datetime(h["latest_event_start"], utc=True)
    end = pd.to_datetime(h["latest_event_end"], utc=True)
    fetched = pd.to_datetime(h["fetched_at"], utc=True)
    discharging = (h["status"] == 1).to_numpy()
    start = start.where(~(discharging & start.isna()), fetched)
    end = end.where(~(discharging & end.isna()), fetched)
    end = end.fillna(start)
    ok = start.notna().to_numpy()
    ev = pd.DataFrame({"site_id": h["site_id"].astype(str).to_numpy()[ok], "start": start[ok].to_numpy(),
                       "end": end[ok].to_numpy()})
    ev["end"] = ev[["start", "end"]].max(axis=1)   # 26 rows of 56,877 on 20 Oct 2026 end before they start
    return ev


def _merge(ev: pd.DataFrame) -> pd.DataFrame:
    """Each overflow's intervals with overlapping ones merged, so an hour seen by two polls counts once."""
    if ev.empty:
        return ev
    e = ev.sort_values(["site_id", "start"], kind="mergesort").reset_index(drop=True)
    prev = e.groupby("site_id")["end"].cummax().groupby(e["site_id"]).shift()
    group = (prev.isna() | (e["start"] > prev)).cumsum()
    return e.groupby(group).agg(site_id=("site_id", "first"), start=("start", "min"), end=("end", "max")).reset_index(drop=True)


def _midnight(d: date) -> pd.Timestamp:
    return pd.Timestamp(d).tz_localize(LOCAL_TZ).tz_convert("UTC")


def hours_on(ev: pd.DataFrame, day: date) -> pd.Series:
    """Hours each overflow spilled on local `day`, from merged poll intervals; at most 24."""
    a, b = _midnight(day), _midnight(day + timedelta(days=1))
    m = _merge(ev)
    if m.empty:
        return pd.Series(dtype=float)
    lo = m["start"].where(m["start"] > a, a)
    hi = m["end"].where(m["end"] < b, b)
    hrs = ((hi - lo).dt.total_seconds() / 3600).clip(lower=0)
    return hrs.groupby(m["site_id"]).sum().clip(upper=24.0)


def reading_times(cov: pd.DataFrame, first: date, last: date) -> pd.DataFrame:
    """(site_id, t) for every half-hour slot with a current known reading (live_coverage.parquet's
    `slots`, ingest.live.coverage_rows) on local days `first` to `last`; t is the slot's middle, UTC.
    On the day the clocks go back, 01:00-02:00 local happens twice and both map to the same slots, so
    a gap that day can read up to an hour short; the day they go forward, up to an hour long."""
    c = cov[(pd.to_datetime(cov["day"]).dt.date >= first) & (pd.to_datetime(cov["day"]).dt.date <= last)]
    if c.empty:
        return pd.DataFrame({"site_id": pd.Series(dtype=str), "t": pd.Series(dtype="datetime64[ns, UTC]")})
    bits = (c["slots"].to_numpy(dtype=np.int64)[:, None] >> np.arange(48, dtype=np.int64)) & 1
    r, s = np.nonzero(bits)
    wall = pd.to_datetime(c["day"].to_numpy()[r]) + pd.to_timedelta(s * SLOT_H + SLOT_H / 2, unit="h")
    t = pd.DatetimeIndex(wall).tz_localize(LOCAL_TZ, ambiguous=np.ones(len(wall), bool), nonexistent="shift_forward")
    return pd.DataFrame({"site_id": c["site_id"].astype(str).to_numpy()[r], "t": t.tz_convert("UTC")})


def status_table(issue_day: date, history: pd.DataFrame, cov: pd.DataFrame) -> pd.DataFrame:
    """Per overflow seen by the poller, indexed by site_id, for forecasts issued on local `issue_day`:
      spill_days_7d    spill-days among the seven local days before issue_day (observed_spill_days' rule)
      spill_hours_24h  hours spilled on the local day before issue_day, at most 24
      last_reading     the latest current reading (UTC), from the coverage slots
      window_gap_h     the longest stretch between current readings from 00:00 on the first of the seven
                       days to last_reading, the stretch before that midnight's first reading included;
                       inf where no reading precedes the window
    The status at issue (spilling_at_issue) comes from the overflow table at forecast time, as do the
    data state and the stretch from last_reading to the issue time (status_known).

    The feature test's statement fixed these. Its candidates were trained at 00:00 UTC of the issue day with EA
    events; here the days are local, the status is the build's poll, and hours an event that started
    and ended between two polls without being the latest at the second are lost. That difference is
    what the shadow test measures."""
    from dipcast.forecast_log import observed_spill_days
    d1 = issue_day - timedelta(days=1)
    d7 = issue_day - timedelta(days=WINDOW_DAYS)
    sd = observed_spill_days(history) if len(history) else pd.DataFrame({"site_id": [], "day": []})
    sd = sd[(sd["day"] >= d7) & (sd["day"] <= d1)]
    days7 = sd.groupby(sd["site_id"].astype(str)).size()
    hrs = hours_on(poll_events(history), d1) if len(history) else pd.Series(dtype=float)

    # Readings from the day before the window, so a stretch running over its first midnight is measured whole.
    rt = reading_times(cov, d7 - timedelta(days=1), issue_day).sort_values(["site_id", "t"], kind="mergesort")
    start = _midnight(d7)
    prev = rt.groupby("site_id")["t"].shift()
    gap = (rt["t"] - prev).dt.total_seconds() / 3600
    # An overflow's first reading has nothing before it to measure from: if it falls inside the window,
    # the window's start was not watched.
    gap = gap.where(prev.notna(), np.inf)
    inside = rt["t"] > start
    g = rt.assign(gap=np.where(inside, gap, 0.0))   # stretches ending before the window do not count
    agg = g.groupby("site_id").agg(last_reading=("t", "max"), window_gap_h=("gap", "max"))

    ids = agg.index.union(days7.index).union(hrs.index)
    out = pd.DataFrame(index=pd.Index(ids, name="site_id"))
    out["spill_days_7d"] = days7.reindex(ids).fillna(0).astype(float)
    out["spill_hours_24h"] = hrs.reindex(ids).fillna(0.0).astype(float)
    out["last_reading"] = agg["last_reading"].reindex(ids)
    out["window_gap_h"] = agg["window_gap_h"].reindex(ids).fillna(np.inf).astype(float)
    return out


@lru_cache(maxsize=2)
def _status_for(issue_day: date) -> pd.DataFrame:
    """status_table from the state directory's poll files, once per issue day in a build."""
    hp, cp = config.state_read("live_history.parquet"), config.state_read("live_coverage.parquet")
    if not hp.exists() or not cp.exists():
        return status_table(issue_day, pd.DataFrame(columns=["site_id", "status", "latest_event_start",
                                                             "latest_event_end", "fetched_at"]),
                            pd.DataFrame(columns=["site_id", "day", "slots"]))
    from dipcast.forecast_log import load_coverage
    return status_table(issue_day, pd.read_parquet(hp), load_coverage(cp))


def clear_cache() -> None:
    _status_for.cache_clear()
    candidates.cache_clear()


def status_known(ov: pd.DataFrame, now: pd.Timestamp, table: pd.DataFrame) -> pd.DataFrame:
    """For each row of `ov` (the upstream overflows, with ingest.live's `data_state`): the three inputs
    and `status_known`. Known needs all three of:
      - a current status now: data_state "live" (0 or 1, from a feed that updated within 6 h, record not
        frozen), which in the build is the build's own poll;
      - the latest current reading at most MAX_GAP_H before `now`;
      - no stretch longer than MAX_GAP_H without a current reading over the seven-day window.
    Where any fails the inputs are NaN and the overflow falls back to the production forecast."""
    sid = ov["site_id"].astype(str)
    t = table.reindex(sid.to_numpy())
    live = (ov["data_state"] == "live").to_numpy() if "data_state" in ov else np.zeros(len(ov), bool)
    age = ((now.tz_convert("UTC") - pd.to_datetime(t["last_reading"], utc=True)).dt.total_seconds() / 3600).to_numpy()
    known = live & (age <= MAX_GAP_H) & (t["window_gap_h"].to_numpy(dtype=float) <= MAX_GAP_H)
    out = pd.DataFrame(index=ov.index)
    out["spilling_at_issue"] = np.where(known, (pd.to_numeric(ov["status"], errors="coerce") == 1).astype(float), np.nan)
    out["spill_hours_24h"] = np.where(known, t["spill_hours_24h"].to_numpy(dtype=float), np.nan)
    out["spill_days_7d"] = np.where(known, t["spill_days_7d"].to_numpy(dtype=float), np.nan)
    out["status_known"] = known
    return out


# ------------------------------------------------------------------ the shadow forecast
def candidate_matrix(sd: pd.DataFrame, ov: pd.DataFrame, days: pd.DatetimeIndex, today_idx: int,
                     status: pd.DataFrame, models: dict[int, SpillModel]) -> np.ndarray:
    """(n_overflows, n_days): lead k's candidate on day today_idx + k, from the forecast's own site-day
    frame `sd` (forecast.spill_probabilities: the same rain, season and covariates as production) and the
    status inputs. NaN on other days, where the status is not known, and where the day has no rain."""
    out = np.full((len(ov), len(days)), np.nan)
    if ov.empty or not models:
        return out
    st = status.assign(site_id=ov["site_id"].to_numpy()).drop_duplicates("site_id").set_index("site_id")
    row = pd.Index(ov["site_id"])
    for k, m in models.items():
        j = today_idx + k
        if j >= len(days):
            continue
        f = sd[sd["day"] == days[j]]
        if f.empty:
            continue
        f = f.join(st[STATUS], on="site_id")
        known = f["site_id"].map(st["status_known"]).eq(True).to_numpy()
        p = m.predict(f.fillna({c: 0.0 for c in ALL_FEATURES}))
        p = np.where(known & f["ok"].to_numpy(dtype=bool), p, np.nan)
        vals = pd.Series(p, index=f["site_id"].to_numpy())
        out[:, j] = vals.reindex(row).to_numpy(dtype=float)
    return out


def shadow_forecast(sd: pd.DataFrame, ov: pd.DataFrame, days: pd.DatetimeIndex, today_idx: int,
                    now: pd.Timestamp, p_cal: np.ndarray) -> dict | None:
    """The shadow for one spot's forecast, or None with the shadow off (no candidates).

    `p` is the forecast as it would be published: lead k's candidate where the overflow's status is known
    and the day has rain, the production forecast `p_cal` (calibrated, what the site shows) everywhere
    else. `known` is (n_overflows,) and `inputs` (n_overflows, 3), NaN where not known. Never published:
    forecast.forecast_point writes it to the forecast log and nowhere else."""
    models = candidates()
    if not models:
        return None
    status = status_known(ov, now, _status_for(now.tz_convert(LOCAL_TZ).date()))
    cand = candidate_matrix(sd, ov, days, today_idx, status, models)
    known = status["status_known"].to_numpy(dtype=bool)
    p = np.where(known[:, None] & np.isfinite(cand), cand, p_cal)
    return {"p": p, "known": known, "inputs": status[STATUS].to_numpy(dtype=float)}
