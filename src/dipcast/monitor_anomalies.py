"""Flags on the live overflow feeds for a person to check: monitors and feeds whose readings look broken in
ways the ingest rules (ingest/live.py) do not already catch. docs/MONITOR-ANOMALIES-2026-10.md has the rules,
what each adds to the existing checks, the evaluation on saved polls and what Ethan decided on 26 Oct 2026;
scripts/monitor_anomalies.py runs them offline.

Wired in (section 8 of that doc), display and warnings only: no rule changes a status, count, risk or level.
  long_run         a list on the data-quality page (quality.long_run_section), against each overflow's longest
                   spill in the EA's records (LONGEST_FILE, made by scripts/make_longest_events.py)
  feed_warnings    future_time, time_format, known_share_drop, company_freeze and id_turnover as build
                   warnings (build_site.monitor_feed_checks); never on the page, never a failed build
Not wired in: record_contradiction, quiet_monitor (held), cadence_change.

Every function reads frames and returns a new frame of flags (FLAG_COLS). It never changes its inputs and
never drops a row from them: a flag is a note beside a reading, not a correction of it. Each flag carries the
overflow (empty for a flag on a whole feed), its company, the rule, the values that set it off (`evidence`,
as JSON), when the rule first held (`first_seen`, UTC) and a severity, which is always "review".

The rules kept, each for a gap the existing checks leave:
  future_time              a record time later than the poll that read it (a clock or time zone slip)
  time_format              most of a company's records with a time before 2015 or a day ahead (a unit or format change)
  record_contradiction     a record whose status and event times disagree with each other
  long_run                 discharging for far longer than the overflow has ever spilled in its record
  quiet_monitor            no spill on any day most of its neighbours spilled, where its record says it would have
  company_freeze           a company's feed answers but no status changes on a day of rain over most of it
  known_share_drop         a company's share of monitors with a known status falls well below its usual
  cadence_change           a feed that stamps every record updating far less often than it did, short of stale
  id_turnover              a company's overflow ids changing between polls when its row count has not fallen
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from dipcast import config

REVIEW = "review"
FLAG_COLS = ["site_id", "company", "rule", "evidence", "first_seen", "severity"]
TIME_COLS = ["status_start", "latest_event_start", "latest_event_end", "last_updated"]

FUTURE_TOLERANCE_MIN = 15.0   # future_time: how far past the poll a record time may be before it is flagged
EARLIEST = pd.Timestamp("2015-01-01", tz="UTC")   # time_format: no live monitor record predates this
FORMAT_SHARE = 0.5            # time_format: share of a company's records with a time before EARLIEST or a day ahead
LONG_RUN_MIN_H = 168.0        # long_run: never flag a spill under a week old
LONG_RUN_FACTOR = 2.0         # long_run: ...nor one under twice the overflow's longest spill on record
STORM_MIN_SPILLING = 3        # a neighbour storm day: at least this many neighbours spilled...
STORM_SHARE = 0.5             # ...and at least this share of the neighbours with a known status
NEIGHBOUR_KM = 5.0
QUIET_MIN_DAYS = 4            # quiet_monitor: storm days seen, at the least
QUIET_MAX_P0 = 0.01           # quiet_monitor: chance of no spill on all of them, at its reference rate
WET_MM = 5.0                  # company_freeze: a wet overflow-day has this much rain or more
WET_SHARE = 0.5               # company_freeze: a wet company-day has this share of its overflows wet
FREEZE_MAX_CHANGES = 5        # company_freeze: fewer status changes than this on a wet day
SHARE_WINDOW = 10             # known_share_drop: the usual share is the median over this many polls before
SHARE_DROP = 0.10             # known_share_drop: a fall of this much or more
CADENCE_RECENT = 5            # cadence_change: median feed age over this many polls...
CADENCE_FACTOR = 4.0          # ...over this many times the median of all polls before them...
CADENCE_FLOOR_H = 1.0         # ...and over this many hours
CADENCE_MIN_HISTORY = 20      # polls before the recent ones, at the least
TURNOVER_SHARE = 0.05         # id_turnover: share of ids new, or gone without a short read
SHORT_SHARE = 0.9             # ingest.live.SHORT_READ_SHARE: below it the ids missing are a short read
# Each overflow's longest spill in the EA's start/stop records 2024-2025 (scripts/make_longest_events.py): the
# reference long_run needs. Small and committed; the build never reads the event files themselves.
LONGEST_FILE = config.PROCESSED / "longest_events.parquet"
FEED_RULES = ("future_time", "time_format", "known_share_drop", "company_freeze", "id_turnover")


def _evidence(**kv) -> str:
    """The values behind a flag, as JSON: times in ISO form, floats to 4 significant figures."""
    def plain(v):
        if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NaT:
            return None
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
        if isinstance(v, (np.floating, float)):
            return float(f"{float(v):.4g}")
        if isinstance(v, np.integer):
            return int(v)
        return v
    return json.dumps({k: plain(v) for k, v in kv.items()}, sort_keys=True)


def _frame(rows: list[dict]) -> pd.DataFrame:
    out = pd.DataFrame(rows, columns=FLAG_COLS[:-1])
    out["first_seen"] = pd.to_datetime(out["first_seen"], utc=True)
    out["severity"] = REVIEW
    return out[FLAG_COLS]


def _utc(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True)


def first_seen_only(flags: pd.DataFrame) -> pd.DataFrame:
    """The earliest flag of each (rule, company, site_id): one line per thing to check."""
    if flags.empty:
        return flags
    f = flags.assign(_site=flags["site_id"].fillna(""))
    return f.sort_values("first_seen", kind="stable").drop_duplicates(["rule", "company", "_site"]).drop(columns="_site")


# ------------------------------------------------------------------ record times
def implausible_times(snap: pd.DataFrame, tolerance_min: float = FUTURE_TOLERANCE_MIN) -> pd.DataFrame:
    """future_time on each record with a time more than `tolerance_min` after its poll (`fetched_at`), and
    time_format on each company with FORMAT_SHARE or more of its records holding a time before EARLIEST or
    more than a day after its poll (seconds read as milliseconds, say). A clock or time zone slip of an hour
    or so is future_time alone. `snap` is a snapshot or the history (one row per state, `fetched_at` the last poll that
    saw it). Rows carried through a feed outage (status -3) are left out: their times are an old poll's."""
    s = snap[pd.to_numeric(snap["status"], errors="coerce").ne(-3)] if "status" in snap else snap
    fetched = _utc(s["fetched_at"])
    cols = [c for c in TIME_COLS if c in s]
    rows = []
    times = pd.DataFrame({c: _utc(s[c]) for c in cols}, index=s.index)
    ahead = pd.DataFrame({c: (times[c] - fetched).dt.total_seconds() / 3600 for c in cols}, index=s.index)
    early = times.lt(EARLIEST)
    fut = ahead.gt(tolerance_min / 60)
    for i in s.index[fut.any(axis=1)]:
        r = s.loc[i]
        which = [c for c in cols if fut.at[i, c]]
        rows.append({"site_id": r["site_id"], "company": r["company"], "rule": "future_time",
                     "evidence": _evidence(fetched_at=fetched[i], **{c: times.at[i, c] for c in which},
                                           hours_ahead=float(ahead.loc[i, which].max())),
                     "first_seen": fetched[i]})
    bad = (early | ahead.gt(24)).any(axis=1)
    has_time = s[cols].notna().any(axis=1)
    for c, g in s[has_time].groupby("company"):
        share = float(bad[g.index].mean())
        if share >= FORMAT_SHARE:
            rows.append({"site_id": None, "company": c, "rule": "time_format",
                         "evidence": _evidence(records=len(g), share_implausible=share,
                                               before_2015=int(early.loc[g.index].any(axis=1).sum()),
                                               over_a_day_ahead=int(ahead.loc[g.index].gt(24).any(axis=1).sum())),
                         "first_seen": fetched[g.index].min()})
    return _frame(rows)


def record_contradictions(snap: pd.DataFrame, slack_h: float = 1.0) -> pd.DataFrame:
    """record_contradiction on each record whose status and event times disagree:
      event_start_after_end          its latest event ends before it starts
      discharging_with_closed_event  status 1, but its latest event has an end at or after its start
      stopped_with_open_event        status 0 since a time at or after its latest event's start, but that
                                     event has no end (the stop time is the status start)
      stopped_before_event_end       status 0 since a time more than `slack_h` before its latest event ended
    Each one is reported, not corrected: the readers already handle some (live_status.poll_events clips an
    end before its start; the page ignores such an end)."""
    st = pd.to_numeric(snap["status"], errors="coerce")
    a, b, since = _utc(snap["latest_event_start"]), _utc(snap["latest_event_end"]), _utc(snap["status_start"])
    kinds = {
        "event_start_after_end": a > b,
        "discharging_with_closed_event": st.eq(1) & (b >= a),
        "stopped_with_open_event": st.eq(0) & a.notna() & b.isna() & (since >= a),
        "stopped_before_event_end": st.eq(0) & (since < b - pd.Timedelta(hours=slack_h)),
    }
    fetched = _utc(snap["fetched_at"])
    rows = []
    for kind, m in kinds.items():
        for i in snap.index[m.fillna(False).to_numpy(dtype=bool)]:
            rows.append({"site_id": snap.at[i, "site_id"], "company": snap.at[i, "company"], "rule": "record_contradiction",
                         "evidence": _evidence(kind=kind, status=int(st[i]), status_start=since[i],
                                               latest_event_start=a[i], latest_event_end=b[i]),
                         "first_seen": fetched[i]})
    return _frame(rows)


# ------------------------------------------------------------------ long runs
def longest_event_hours(events: pd.DataFrame) -> pd.Series:
    """Per site_id, its longest event in hours, from an event record (event_start, event_end)."""
    d = (_utc(events["event_end"]) - _utc(events["event_start"])).dt.total_seconds() / 3600
    return d.groupby(events["site_id"]).max().rename("longest_h")


def longest_events_table(events: pd.DataFrame) -> pd.DataFrame:
    """One row per site_id: its longest event in hours (longest_event_hours) and its number of events, sorted by
    site_id. What LONGEST_FILE holds."""
    d = (_utc(events["event_end"]) - _utc(events["event_start"])).dt.total_seconds() / 3600
    g = d.groupby(events["site_id"])
    out = pd.DataFrame({"longest_h": g.max(), "n_events": g.size()}).reset_index()
    return out.astype({"site_id": str, "longest_h": "float64", "n_events": "int64"}).sort_values("site_id").reset_index(drop=True)


def load_longest(path=None) -> pd.Series:
    """LONGEST_FILE as a Series, longest_h by site_id. Raises if the file is missing or unreadable."""
    t = pd.read_parquet(path or LONGEST_FILE, columns=["site_id", "longest_h"])
    return t.set_index("site_id")["longest_h"]


def long_runs(snap: pd.DataFrame, longest_h: pd.Series | None = None, min_h: float = LONG_RUN_MIN_H,
              factor: float = LONG_RUN_FACTOR) -> pd.DataFrame:
    """long_run on each overflow discharging (status 1) for longer than `min_h`, and longer than `factor`
    times its longest event in a reference record (`longest_h`, longest_event_hours; an overflow without one
    has the floor alone). A long spill at an overflow that has spilled that long before is not flagged.
    `first_seen` is the moment the run passed its limit."""
    s = snap[pd.to_numeric(snap["status"], errors="coerce").eq(1)]
    start = _utc(s["status_start"]).fillna(_utc(s["latest_event_start"]))
    fetched = _utc(s["fetched_at"])
    stamp = _utc(s["last_updated"]) if "last_updated" in s else pd.Series(pd.NaT, index=s.index)
    run_h = (fetched - start).dt.total_seconds() / 3600
    ref = (s["site_id"].map(longest_h) if longest_h is not None else pd.Series(np.nan, index=s.index)).astype(float)
    limit = np.maximum(min_h, (factor * ref).fillna(0.0))
    rows = []
    for i in s.index[(run_h > limit).to_numpy()]:
        rows.append({"site_id": s.at[i, "site_id"], "company": s.at[i, "company"], "rule": "long_run",
                     "evidence": _evidence(status_start=start[i], fetched_at=fetched[i], run_h=run_h[i],
                                           longest_on_record_h=ref[i], limit_h=limit[i], last_updated=stamp[i]),
                     "first_seen": start[i] + pd.Timedelta(hours=float(limit[i]))})
    return _frame(rows)


# ------------------------------------------------------------------ quiet monitors
def neighbours_within(sites: pd.DataFrame, km: float = NEIGHBOUR_KM) -> pd.DataFrame:
    """(site_id, nb): every pair of overflows within `km` of each other (great circle), each way, not itself."""
    from sklearn.neighbors import BallTree
    s = sites.dropna(subset=["lat", "lon"]).drop_duplicates("site_id")
    xy = np.radians(s[["lat", "lon"]].to_numpy(dtype=float))
    ind = BallTree(xy, metric="haversine").query_radius(xy, r=km / 6371.0)
    ids = s["site_id"].to_numpy()
    out = pd.DataFrame({"site_id": np.repeat(ids, [len(i) for i in ind]),
                        "nb": ids[np.concatenate(ind)] if len(ind) else np.array([], dtype=object)})
    return out[out["site_id"] != out["nb"]].reset_index(drop=True)


def storm_days(known: pd.DataFrame, spills: pd.DataFrame, neighbours: pd.DataFrame,
               min_spilling: int = STORM_MIN_SPILLING, share: float = STORM_SHARE) -> pd.DataFrame:
    """Per (site_id, day) on which the overflow had a known status (`known`: site_id, day): its neighbours
    with a known status that day, how many of them spilled (`spills`: site_id, day), whether that makes a
    neighbour storm day for it (`storm`) and whether it spilled itself (`y`)."""
    key = ["site_id", "day"]
    k, s = known[key].drop_duplicates(), spills[key].drop_duplicates().assign(y=1)
    x = neighbours.merge(k.rename(columns={"site_id": "nb"}), on="nb")
    x = x.merge(s.rename(columns={"site_id": "nb"}), on=["nb", "day"], how="left")
    g = x.groupby(key).agg(n_known=("nb", "size"), n_spill=("y", "count")).reset_index()
    g = k.merge(g, on=key, how="left").fillna({"n_known": 0, "n_spill": 0})
    g = g.merge(s, on=key, how="left").fillna({"y": 0})
    g["storm"] = (g["n_spill"] >= min_spilling) & (g["n_spill"] >= share * g["n_known"])
    return g.astype({"n_known": int, "n_spill": int, "y": int})


def storm_rates(table: pd.DataFrame) -> pd.DataFrame:
    """Per site_id, from a reference storm_days table: storm days, those it spilled on, and its rate p, with
    half a spill added over one day so a short record never gives 0 or 1."""
    t = table[table["storm"]].groupby("site_id").agg(n_ref=("y", "size"), k_ref=("y", "sum"))
    return t.assign(p=(t["k_ref"] + 0.5) / (t["n_ref"] + 1))


def quiet_monitors(table: pd.DataFrame, rates: pd.DataFrame, company_of: pd.Series | None = None,
                   min_days: int = QUIET_MIN_DAYS, max_p0: float = QUIET_MAX_P0) -> pd.DataFrame:
    """quiet_monitor on each overflow that spilled on none of its neighbour storm days in `table` (storm_days
    over the window checked), where at least `min_days` of them, at its reference rate (storm_rates), had a
    chance of no spill on all of them of `max_p0` or less. `first_seen` is the storm day on which that first
    held. Days are not independent (one storm spans several), so the chance is a ranking, not a test."""
    t = table[table["storm"]].merge(rates[["p", "n_ref", "k_ref"]], left_on="site_id", right_index=True)
    rows = []
    for sid, g in t.sort_values("day", kind="stable").groupby("site_id", sort=False):
        if g["y"].sum() > 0 or len(g) < min_days:
            continue
        p = float(g["p"].iloc[0])
        p0 = (1 - p) ** np.arange(1, len(g) + 1)
        hit = np.nonzero((p0 <= max_p0) & (np.arange(1, len(g) + 1) >= min_days))[0]
        if not len(hit):
            continue
        rows.append({"site_id": sid, "company": None if company_of is None else company_of.get(sid),
                     "rule": "quiet_monitor",
                     "evidence": _evidence(storm_days=len(g), spilled_on=0, ref_storm_days=int(g["n_ref"].iloc[0]),
                                           ref_spilled_on=int(g["k_ref"].iloc[0]), ref_rate=p, chance_of_none=float(p0[-1]),
                                           first_storm_day=str(pd.Timestamp(g["day"].iloc[0]).date()),
                                           last_storm_day=str(pd.Timestamp(g["day"].iloc[-1]).date())),
                     "first_seen": pd.Timestamp(g["day"].iloc[hit[0]])})
    return _frame(rows)


# ------------------------------------------------------------------ company freezes
def change_times(history: pd.DataFrame) -> pd.DataFrame:
    """(site_id, company, time) of every status change the live history records: each distinct status
    start, event start and event end, up to the last poll. Wessex Water's history leaves many status starts
    empty, so the event times are needed as well."""
    parts = [history[["site_id", "company", c]].rename(columns={c: "time"}) for c in TIME_COLS[:3] if c in history]
    ch = pd.concat(parts, ignore_index=True).dropna(subset=["time"])
    ch["time"] = _utc(ch["time"])
    ch = ch[ch["time"] <= _utc(history["fetched_at"]).max()]
    return ch.drop_duplicates(["site_id", "time"]).reset_index(drop=True)


def wet_days(rain: pd.DataFrame, company_of: pd.Series, mm: float = WET_MM) -> pd.DataFrame:
    """Per (company, day), from rain per overflow and day (site_id, day, rain_mm): overflows with rain, and
    the share of them with `mm` or more."""
    r = rain.assign(company=rain["site_id"].map(company_of)).dropna(subset=["company", "rain_mm"])
    return (r.assign(wet=r["rain_mm"] >= mm).groupby(["company", "day"])
            .agg(n_overflows=("wet", "size"), wet_share=("wet", "mean")).reset_index())


def company_freezes(changes: pd.DataFrame, wet: pd.DataFrame, tz: str = "Europe/London",
                    wet_share: float = WET_SHARE, max_changes: int = FREEZE_MAX_CHANGES) -> pd.DataFrame:
    """company_freeze on each company and local day with rain over `wet_share` or more of its overflows
    (wet_days) and fewer than `max_changes` status changes in its feed (change_times). A feed whose job
    re-stamps every record while its statuses stop would pass every freshness check; on a dry day it cannot
    be told from a quiet one, so only wet days are judged."""
    ch = changes.assign(day=_utc(changes["time"]).dt.tz_convert(tz).dt.strftime("%Y-%m-%d"))
    n = ch.groupby(["company", "day"]).size().rename("changes").reset_index()
    w = wet.assign(day=pd.to_datetime(wet["day"]).dt.strftime("%Y-%m-%d"))
    m = w.merge(n, on=["company", "day"], how="left").fillna({"changes": 0})
    m = m[(m["wet_share"] >= wet_share) & (m["changes"] < max_changes)]
    rows = [{"site_id": None, "company": r.company, "rule": "company_freeze",
             "evidence": _evidence(day=r.day, wet_share=r.wet_share, overflows_with_rain=int(r.n_overflows),
                                   status_changes=int(r.changes)),
             "first_seen": pd.Timestamp(r.day, tz=tz).tz_convert("UTC")} for r in m.itertuples()]
    return _frame(rows)


# ------------------------------------------------------------------ poll log
def known_share_drops(poll_log: pd.DataFrame, window: int = SHARE_WINDOW, drop: float = SHARE_DROP) -> pd.DataFrame:
    """known_share_drop on each poll where a company's share of rows with a known status (n_known / n_rows)
    is `drop` or more below its median over the `window` polls before (at least half of them). A feed that
    renames or recodes its status field reads as every monitor offline (fetch_live sets an unreadable status
    to -1), which the site shows honestly but nothing reports. A poll with no rows is a feed outage, handled
    already, and left out."""
    pl = poll_log[poll_log["n_rows"] > 0].sort_values("fetched_at", kind="stable")
    rows = []
    for c, g in pl.groupby("company"):
        share = g["n_known"] / g["n_rows"]
        usual = share.shift().rolling(window, min_periods=max(1, window // 2)).median()
        for i in g.index[(usual - share >= drop).to_numpy()]:
            rows.append({"site_id": None, "company": c, "rule": "known_share_drop",
                         "evidence": _evidence(share_known=share[i], usual_share=usual[i], n_rows=int(g.at[i, "n_rows"]),
                                               n_known=int(g.at[i, "n_known"])),
                         "first_seen": g.at[i, "fetched_at"]})
    return _frame(rows)


def cadence_changes(poll_log: pd.DataFrame, every_record: set[str], recent: int = CADENCE_RECENT,
                    factor: float = CADENCE_FACTOR, floor_h: float = CADENCE_FLOOR_H,
                    min_history: int = CADENCE_MIN_HISTORY) -> pd.DataFrame:
    """cadence_change on each poll where a company that stamps every record (`every_record`,
    ingest.live.stamps_every_record) has a median feed age over its last `recent` polls above `floor_h` and
    `factor` times its median over all polls before those. FEED_CURRENT_H (6 h) already marks a feed stale;
    this sees a slower refresh before then. Companies that stamp a record only when it changes are left
    out: their feed age is the time since the last change anywhere."""
    pl = poll_log[poll_log["company"].isin(every_record) & poll_log["feed_age_h"].notna()].sort_values("fetched_at", kind="stable")
    rows = []
    for c, g in pl.groupby("company"):
        now = g["feed_age_h"].rolling(recent).median()
        usual = g["feed_age_h"].shift(recent).expanding(min_periods=min_history).median()
        for i in g.index[((now > floor_h) & (now > factor * usual)).to_numpy()]:
            rows.append({"site_id": None, "company": c, "rule": "cadence_change",
                         "evidence": _evidence(recent_median_age_h=now[i], usual_median_age_h=usual[i], polls=recent),
                         "first_seen": g.at[i, "fetched_at"]})
    return _frame(rows)


# ------------------------------------------------------------------ ids
def id_turnover(previous: pd.DataFrame, current: pd.DataFrame, share: float = TURNOVER_SHARE,
                short_share: float = SHORT_SHARE) -> pd.DataFrame:
    """id_turnover on each company whose overflow ids (site_id, company; one poll, or one day's polls, each)
    changed by `share` or more of the previous count: new ids, or ids gone while the count held at
    `short_share` or more of before. Fewer ids with a smaller count is a short read or an outage, handled
    already (carry_forward); the same count with other ids (a new id scheme) is not."""
    rows = []
    at = _utc(current["fetched_at"]).max() if "fetched_at" in current and len(current) else pd.NaT
    prev = previous.groupby("company")["site_id"].apply(set)
    cur = current.groupby("company")["site_id"].apply(set)
    for c in prev.index.intersection(cur.index):
        a, b = prev[c], cur[c]
        gone, new = len(a - b) / len(a), len(b - a) / len(a)
        if new >= share or (gone >= share and len(b) >= short_share * len(a)):
            rows.append({"site_id": None, "company": c, "rule": "id_turnover",
                         "evidence": _evidence(ids_before=len(a), ids_now=len(b), share_gone=gone, share_new=new,
                                               examples_new=sorted(b - a)[:5], examples_gone=sorted(a - b)[:5]),
                         "first_seen": at})
    return _frame(rows)


# ------------------------------------------------------------------ build warnings
def _ids(xs, n: int = 5) -> str:
    xs = sorted({str(x) for x in xs})
    return ", ".join(xs[:n]) + (f" and {len(xs) - n} more" if len(xs) > n else "")


def _company_of(*frames: pd.DataFrame | None) -> pd.Series:
    parts = [f[["site_id", "company"]] for f in frames if f is not None and {"site_id", "company"} <= set(f.columns)]
    if not parts:
        return pd.Series(dtype=object)
    return pd.concat(parts, ignore_index=True).dropna().drop_duplicates("site_id", keep="last").set_index("site_id")["company"]


def _missing(x) -> bool:
    return x is None or len(x) == 0


def feed_warnings(snapshot: pd.DataFrame | None, poll_log: pd.DataFrame | None = None,
                  history: pd.DataFrame | None = None, rain: pd.DataFrame | None = None,
                  coverage: pd.DataFrame | None = None, tz: str = "Europe/London") -> tuple[list[str], dict]:
    """The whole-feed rules (FEED_RULES) on what a build has now, as build warnings: (warnings, summary).
    Only what holds now is reported, so a fault warns on the builds that see it and stops when it clears:
      future_time, time_format  the live snapshot (live_latest.parquet)
      known_share_drop          the poll log, at its latest poll
      company_freeze            yesterday (local day), from the live history's status changes and the forecast
                                log's lead-0 rain per overflow (`rain`: site_id, day as YYYY-MM-DD, rain_mm)
      id_turnover               yesterday's ids (live_coverage.parquet: site_id, day) against the snapshot's
    A rule whose input is missing is skipped and named in summary["skipped"]. Nothing is changed or dropped."""
    warns: list[str] = []
    summary: dict = {"checked": [], "skipped": {}, "flags": {}}
    have = not _missing(snapshot) and "fetched_at" in snapshot
    now = _utc(snapshot["fetched_at"]).max() if have else pd.NaT
    yesterday = (now.tz_convert(tz).normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d") if have else None
    company_of = _company_of(history, snapshot)

    def done(rule: str, n: int) -> None:
        summary["checked"].append(rule)
        summary["flags"][rule] = n

    if have:
        f = implausible_times(snapshot)
        fut = f[f["rule"] == "future_time"]
        for c, g in fut.groupby("company"):
            ahead = max(json.loads(e)["hours_ahead"] for e in g["evidence"])
            one = len(g) == 1
            warns.append(f"monitor check (future_time): {len(g)} {c} record{'' if one else 's'} "
                         f"carr{'ies' if one else 'y'} a time up to {ahead * 60:.0f} minutes after the poll that read "
                         f"{'it' if one else 'them'} ({_ids(g['site_id'])}): a clock or time zone slip in the feed")
        done("future_time", len(fut))
        tf = f[f["rule"] == "time_format"]
        for r in tf.itertuples():
            e = json.loads(r.evidence)
            warns.append(f"monitor check (time_format): {e['share_implausible']:.0%} of {r.company}'s {e['records']} records "
                         f"carry a time before 2015 or over a day after the poll ({e['before_2015']} before 2015, "
                         f"{e['over_a_day_ahead']} ahead): the feed's time format may have changed")
        done("time_format", len(tf))
    else:
        summary["skipped"]["future_time"] = summary["skipped"]["time_format"] = "no live snapshot"

    if _missing(poll_log):
        summary["skipped"]["known_share_drop"] = "no poll log"
    else:
        last = _utc(poll_log["fetched_at"]).max()
        f = known_share_drops(poll_log)
        f = f[_utc(f["first_seen"]) == last]
        for r in f.itertuples():
            e = json.loads(r.evidence)
            warns.append(f"monitor check (known_share_drop): {r.company}'s share of monitors with a known status fell to "
                         f"{e['share_known']:.2f} at the poll of {last.strftime('%Y-%m-%d %H:%M')} UTC, from a usual "
                         f"{e['usual_share']:.2f}: its status field may have been renamed or recoded")
        done("known_share_drop", len(f))

    lacking = [n for n, x in (("live snapshot", snapshot if have else None), ("live history", history),
                              ("forecast rain", rain)) if _missing(x)]
    if lacking:
        summary["skipped"]["company_freeze"] = "no " + " or ".join(lacking)
    else:
        day_rain = rain[rain["day"].astype(str).str[:10] == yesterday].assign(day=yesterday)
        f = company_freezes(change_times(history), wet_days(day_rain, company_of), tz=tz) if len(day_rain) else _frame([])
        for r in f.itertuples():
            e = json.loads(r.evidence)
            n = e["status_changes"]
            warns.append(f"monitor check (company_freeze): {r.company}'s feed recorded {n} status change{'' if n == 1 else 's'} "
                         f"on {e['day']}, a day with {WET_MM:g} mm or more of forecast rain at {e['wet_share']:.0%} of its "
                         "overflows: its statuses may have stopped updating")
        done("company_freeze", len(f))

    if not have or _missing(coverage):
        summary["skipped"]["id_turnover"] = "no " + ("live snapshot" if not have else "coverage file")
    else:
        prev = coverage[pd.to_datetime(coverage["day"]).dt.strftime("%Y-%m-%d") == yesterday][["site_id"]]
        prev = prev.assign(company=prev["site_id"].map(company_of)).dropna(subset=["company"])
        f = id_turnover(prev, snapshot[["site_id", "company", "fetched_at"]]) if len(prev) else _frame([])
        for r in f.itertuples():
            e = json.loads(r.evidence)
            warns.append(f"monitor check (id_turnover): {r.company} has {e['ids_now']} overflow ids now and had "
                         f"{e['ids_before']} on {yesterday}; {e['share_new']:.0%} are new (such as {_ids(e['examples_new'])}) "
                         f"and {e['share_gone']:.0%} gone (such as {_ids(e['examples_gone'])}): the feed may have a new id scheme")
        done("id_turnover", len(f))
    return warns, summary
