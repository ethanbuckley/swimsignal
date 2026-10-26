"""The monitor anomaly flags (dipcast.monitor_anomalies) on saved live polls, and on copies of them with failures
put in by hand: the numbers behind docs/MONITOR-ANOMALIES-2026-10.md. Off CI, by hand; reads files only, fetches
nothing and writes only --out:

    uv run python scripts/monitor_anomalies.py --state DIR [--latest FILE] [--ea-events DIR] \\
        [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--ref-year 2025] [--out PREFIX] [--synthetic]

- --state: live_history.parquet, poll_log.parquet and live_coverage.parquet from the `state` release, and
  dipcast.duckdb (the forecast log) for the lead-0 forecast rain the company_freeze rule needs. Without the
  log that rule is skipped.
- --latest: a live_latest.parquet (default: the one in --state), for the snapshot rules.
- --ea-events: the folder of ea_events_<company>.parquet (scripts/import_ea_events.py; default
  data/processed): each overflow's longest spill (long_run) and its spill rate on neighbour storm days in
  --ref-year (quiet_monitor).
- --synthetic: also run each failure put into copies of the inputs, and print, per failure, which existing
  checks and which new flags it sets off that the clean copy does not.

Contains Environment Agency data (OGL v3.0) and the water companies' storm overflow feeds via the National Storm
Overflow Hub (CC BY 4.0).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from dipcast import config
from dipcast import monitor_anomalies as ma
from dipcast.ingest.live import (FEED_CURRENT_H, expected_rows, feed_age_hours, frozen_records, is_short,
                                 stamps_every_record)
from dipcast.model.features import spill_days
from dipcast.model.live_status import poll_events
from dipcast.overflows import duplicate_site_ids

KEY = ["rule", "company", "site_id"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def rain_by_overflow(db: Path) -> pd.DataFrame:
    """Lead-0 forecast rain per overflow and target day: the latest issue of each, from the forecast log."""
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute("""
            SELECT site_id, CAST(target_day AS VARCHAR) AS day, rain_mm FROM forecast_overflows
            WHERE lead = 0 AND rain_mm IS NOT NULL
            QUALIFY row_number() OVER (PARTITION BY site_id, target_day ORDER BY issued_at DESC) = 1""").fetchdf()
    finally:
        con.close()


def load(args) -> dict:
    st = Path(args.state)
    files = {n: st / n for n in ("live_history.parquet", "poll_log.parquet", "live_coverage.parquet", "dipcast.duckdb")}
    files["live_latest.parquet"] = Path(args.latest) if args.latest else st / "live_latest.parquet"
    lo, hi = pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC") + pd.Timedelta(days=1)
    hist = pd.read_parquet(files["live_history.parquet"])
    latest = pd.read_parquet(files["live_latest.parquet"])
    pl = pd.read_parquet(files["poll_log.parquet"])
    cov = pd.read_parquet(files["live_coverage.parquet"])
    company_of = pd.concat([hist[["site_id", "company"]], latest[["site_id", "company"]]]).drop_duplicates("site_id").set_index("site_id")["company"]
    ea_files = sorted(Path(args.ea_events).glob("ea_events_*.parquet"))
    ea = pd.concat([pd.read_parquet(p, columns=["site_id", "event_start", "event_end"]) for p in ea_files], ignore_index=True)
    fresh = latest[latest["status"].isin([0, 1, -1])]
    every = stamps_every_record(fresh)
    d = {"lo": lo, "hi": hi, "hist": hist, "latest": latest, "pl": pl, "cov": cov, "company_of": company_of,
         "longest": ma.longest_event_hours(ea), "every": set(every[every].index),
         "files": {n: {"path": str(p), "sha256_12": sha(p)} for n, p in files.items() if p.exists()}
         | {p.name: {"path": str(p), "sha256_12": sha(p)} for p in ea_files}}
    # Neighbour storm days: live, from the polls in the window; reference, from the EA's events in the year.
    nb = ma.neighbours_within(fresh)
    known = cov[cov["slots"] != 0][["site_id", "day"]].assign(day=lambda x: pd.to_datetime(x["day"]).dt.tz_localize("UTC"))
    known = known[(known["day"] >= lo) & (known["day"] < hi)]
    live_sd = spill_days(poll_events(hist).rename(columns={"start": "event_start", "end": "event_end"}))
    d["live_table"] = ma.storm_days(known, live_sd[(live_sd["day"] >= lo) & (live_sd["day"] < hi)], nb)
    ids = set(ea["site_id"]) & set(fresh["site_id"])
    ref_sd = spill_days(ea[ea["site_id"].isin(ids)])
    ref_sd = ref_sd[ref_sd["day"].dt.year == args.ref_year]
    days = pd.date_range(f"{args.ref_year}-01-01", f"{args.ref_year}-12-31", tz="UTC")
    ref_known = pd.DataFrame({"site_id": sorted(ids)}).merge(pd.DataFrame({"day": days}), how="cross")
    d["rates"] = ma.storm_rates(ma.storm_days(ref_known, ref_sd, nb[nb["site_id"].isin(ids) & nb["nb"].isin(ids)]))
    d["changes"] = ma.change_times(hist)
    if files["dipcast.duckdb"].exists():
        w = ma.wet_days(rain_by_overflow(files["dipcast.duckdb"]), company_of)
        d["wet"] = w[(w["day"] >= args.start) & (w["day"] <= args.end)].reset_index(drop=True)
    return d


# ------------------------------------------------------------------ the real polls
def real(d: dict) -> pd.DataFrame:
    lo, hi = d["lo"], d["hi"]
    hist = d["hist"][(d["hist"]["fetched_at"] >= lo) & (d["hist"]["fetched_at"] < hi)]
    pl = d["pl"][(d["pl"]["fetched_at"] >= lo) & (d["pl"]["fetched_at"] < hi)]
    parts = {
        "future_time/time_format (history)": ma.implausible_times(hist),
        "future_time/time_format (latest)": ma.implausible_times(d["latest"]),
        "record_contradiction (latest)": ma.record_contradictions(d["latest"]),
        "record_contradiction (history)": ma.record_contradictions(hist),
        "long_run (history)": ma.long_runs(hist, d["longest"]),
        "quiet_monitor": ma.quiet_monitors(d["live_table"], d["rates"], d["company_of"]),
        "known_share_drop": ma.known_share_drops(pl),
        "cadence_change": ma.cadence_changes(pl, d["every"]),
    }
    if "wet" in d:
        ch = d["changes"][(d["changes"]["time"] >= lo) & (d["changes"]["time"] < hi)]
        parts["company_freeze"] = ma.company_freezes(ch, d["wet"])
    cov = d["cov"].assign(company=d["cov"]["site_id"].map(d["company_of"]), day=pd.to_datetime(d["cov"]["day"]))
    cov = cov[(cov["day"] >= lo.tz_localize(None)) & (cov["day"] < hi.tz_localize(None))]
    days = sorted(cov["day"].unique())
    turn = [ma.id_turnover(cov[cov["day"] == a], cov[cov["day"] == b].assign(fetched_at=pd.Timestamp(b, tz="UTC")))
            for a, b in zip(days, days[1:])]
    parts["id_turnover (daily ids)"] = pd.concat(turn, ignore_index=True) if turn else ma._frame([])
    print(f"Window {lo.date()} to {(hi - pd.Timedelta(days=1)).date()}: {pl['fetched_at'].nunique()} polls, "
          f"{len(hist):,} history rows, {len(days)} coverage days, {int(d['live_table']['storm'].sum()):,} live and "
          f"{int(d['rates']['n_ref'].sum()):,} reference neighbour storm site-days, "
          f"{len(d.get('wet', [])):,} company-days with rain ({int((d.get('wet', pd.DataFrame({'wet_share': []}))['wet_share'] >= ma.WET_SHARE).sum())} wet)")
    out = []
    for name, f in parts.items():
        one = ma.first_seen_only(f)
        print(f"  {name:38s} flags {len(f):5d}  distinct {len(one):4d}  by company {one['company'].value_counts().to_dict()}")
        out.append(one.assign(source=name))
    return pd.concat(out, ignore_index=True)


def already_caught(flags: pd.DataFrame, latest: pd.DataFrame) -> pd.Series:
    """Per record-level flag, whether an existing rule marks the same overflow in the latest snapshot: a record
    that stopped updating (frozen_records) or a feed over FEED_CURRENT_H old."""
    fresh = latest[latest["status"].isin([0, 1, -1])]
    frozen = set(fresh.loc[frozen_records(fresh).to_numpy(), "site_id"])
    age = feed_age_hours(fresh)
    stale = set(age[~(age <= FEED_CURRENT_H)].index)
    return flags["site_id"].isin(frozen) | (flags["site_id"].notna() & flags["company"].isin(stale))


# ------------------------------------------------------------------ failures put in by hand
def poll_row(snap: pd.DataFrame, at: pd.Timestamp, companies) -> pd.DataFrame:
    """The poll log's row per company for one snapshot, as ingest.live.log_poll writes it."""
    ages = feed_age_hours(snap)
    g = snap.groupby("company")
    return pd.DataFrame([{"fetched_at": at, "company": c, "n_rows": len(g.get_group(c)) if c in g.groups else 0,
                          "n_known": int(g.get_group(c)["status"].isin([0, 1]).sum()) if c in g.groups else 0,
                          "feed_age_h": float(ages.get(c, np.nan))} for c in companies])


def existing(snap: pd.DataFrame, pl: pd.DataFrame) -> set[str]:
    """What the existing checks report on a snapshot and the poll log ending with its poll: build_health's
    feed down, short read and duplicate-id warnings, stale feeds (data_states, coverage) and the quality page's
    frozen records."""
    last = pl[pl["fetched_at"] == pl["fetched_at"].max()]
    usual = expected_rows(pl[pl["fetched_at"] < pl["fetched_at"].max()])
    out = {f"feed_down|{r.company}" for r in last.itertuples() if r.n_rows == 0}
    out |= {f"short_read|{r.company}" for r in last.itertuples() if is_short(r.n_rows, r.company, usual)}
    out |= {f"duplicate_id|{s}" for s in duplicate_site_ids(snap)}
    one = snap.drop_duplicates("site_id")
    age = feed_age_hours(one)
    out |= {f"feed_stale|{c}" for c in age[~(age <= FEED_CURRENT_H)].index}
    out |= {f"frozen_record|{s}" for s in one.loc[frozen_records(one).to_numpy(), "site_id"]}
    return out


def new(snap: pd.DataFrame, pl: pd.DataFrame, prev: pd.DataFrame, d: dict, live_table=None, changes=None) -> set[str]:
    parts = [ma.implausible_times(snap), ma.record_contradictions(snap), ma.long_runs(snap, d["longest"]),
             ma.known_share_drops(pl), ma.cadence_changes(pl, d["every"]),
             ma.id_turnover(prev, snap.drop_duplicates("site_id"))]
    if live_table is not None:
        parts.append(ma.quiet_monitors(live_table, d["rates"], d["company_of"]))
    if changes is not None and "wet" in d:
        parts.append(ma.company_freezes(changes, d["wet"]))
    f = pd.concat(parts, ignore_index=True)
    return {f"{r.rule}|{r.company if pd.isna(r.site_id) else r.site_id}" for r in f.itertuples()}


def synthetic(d: dict) -> list[dict]:
    clean = d["latest"][d["latest"]["status"].isin([0, 1, -1])].reset_index(drop=True)
    for c in ma.TIME_COLS + ["fetched_at"]:
        clean[c] = pd.to_datetime(clean[c], utc=True).dt.as_unit("ns")
    at = clean["fetched_at"].max()
    companies = sorted(clean["company"].unique())
    pl0 = d["pl"][d["pl"]["fetched_at"] < at]

    def run(snap, live_table=d["live_table"], changes=d["changes"]):
        pl = pd.concat([pl0, poll_row(snap.drop_duplicates("site_id"), at, companies)], ignore_index=True)
        return existing(snap, pl), new(snap, pl, clean, d, live_table, changes)

    base_old, base_new = run(clean)
    cases = {}
    uu = clean["company"] == "United Utilities"

    s = clean.copy()   # 1. one record stops updating in a feed that goes on
    i = s.index[uu & s["status"].eq(0)][0]
    s.loc[i, "last_updated"] = at - pd.Timedelta(days=3)
    cases["frozen record (UU, stamp 3 days old)"] = s

    s = clean.copy()   # 2. a company recodes Status: fetch_live's to_numeric(...).fillna(-1) reads every one as offline
    s.loc[s["company"] == "Thames Water", "status"] = -1
    cases["status field recoded (Thames, all read -1)"] = s

    s = clean.copy()   # 3. a repeated id with a conflicting status: a second row saying a spill started an hour ago
    rows = s[(s["company"] == "Anglian Water") & s["status"].eq(0)].sample(3, random_state=0)
    hour = at - pd.Timedelta(hours=1)
    rows = rows.assign(status=1, status_start=hour, latest_event_start=hour, latest_event_end=pd.NaT,
                       last_updated=rows["last_updated"] - pd.Timedelta(minutes=30))
    cases["duplicated ids (3 Anglian, second row discharging)"] = pd.concat([s, rows], ignore_index=True)

    s = clean.copy()   # 4. clock skew: one company's times written in BST but labelled UTC
    for c in ma.TIME_COLS:
        s.loc[s["company"] == "Wessex Water", c] += pd.Timedelta(hours=1)
    cases["clock skew (Wessex, +1 h)"] = s

    s = clean.copy()   # 5. epoch seconds read as milliseconds
    sv = s["company"] == "Severn Trent Water"
    for c in ma.TIME_COLS:
        s.loc[sv, c] = pd.to_datetime(s.loc[sv, c].astype("int64") // 10**9 // 1000, unit="ms", utc=True).where(s.loc[sv, c].notna())
    cases["time unit change (Severn Trent, s as ms)"] = s

    cases["company silent (Southern, no rows)"] = clean[clean["company"] != "Southern Water"].reset_index(drop=True)

    s = clean.copy()   # 7. a new id scheme: same count, other ids
    s.loc[s["company"] == "Wessex Water", "site_id"] = "NEW" + s.loc[s["company"] == "Wessex Water", "site_id"].str[3:]
    cases["id scheme change (Wessex)"] = s

    # 8. stuck discharging, at an overflow whose longest spill on record is under 2 h
    short = d["longest"][d["longest"] < 2]
    s = clean.copy()
    i = s.index[s["site_id"].isin(short.index) & s["status"].eq(0) & uu][0]
    s.loc[i, ["status", "status_start", "latest_event_start", "latest_event_end"]] = [1, at - pd.Timedelta(days=10), at - pd.Timedelta(days=10), pd.NaT]
    cases[f"stuck discharging ({s.at[i, 'site_id']}, 10 days, longest {short[s.at[i, 'site_id']]:.1f} h)"] = s

    # 9. a real long spill: 12 days at an overflow whose longest spill on record is over 25 days
    long_ = d["longest"][d["longest"] > 600]
    s = clean.copy()
    i = s.index[s["site_id"].isin(long_.index) & s["status"].eq(0)][0]
    s.loc[i, ["status", "status_start", "latest_event_start", "latest_event_end"]] = [1, at - pd.Timedelta(days=12), at - pd.Timedelta(days=12), pd.NaT]
    cases[f"REAL long spill ({s.at[i, 'site_id']}, 12 days, longest {long_[s.at[i, 'site_id']]:.0f} h)"] = s

    results = []
    for name, snap in cases.items():
        old, nw = run(snap)
        results.append({"case": name, "existing": sorted(old - base_old), "new": sorted(nw - base_new)})

    # 10. a monitor that stops reporting spills: the busiest of the window, its spills taken out
    t = d["live_table"]
    busy = t[t["storm"]].groupby("site_id")["y"].agg(["size", "sum"]).query("size >= 5").sort_values("sum").index[-1]
    old, nw = run(clean, live_table=t.assign(y=t["y"].where(t["site_id"] != busy, 0)))
    results.append({"case": f"monitor reads 0 through storms ({busy})", "existing": sorted(old - base_old), "new": sorted(nw - base_new)})

    # 11. a feed that answers, re-stamped, with no status change on its wettest day in the window
    if "wet" in d:
        w = d["wet"].sort_values("wet_share").iloc[-1]
        ch = d["changes"]
        day = ch["time"].dt.tz_convert("Europe/London").dt.strftime("%Y-%m-%d")
        old, nw = run(clean, changes=ch[~((ch["company"] == w["company"]) & (day == w["day"]))])
        results.append({"case": f"feed frozen, re-stamped ({w['company']}, {w['day']})", "existing": sorted(old - base_old),
                        "new": sorted(nw - base_new)})
    print(f"\nFailures put in by hand, on the snapshot of {at} (clean copy: {len(base_old)} existing, {len(base_new)} new flags)")
    for r in results:
        print(f"- {r['case']}\n    existing: {r['existing'][:6]}{' ...' if len(r['existing']) > 6 else ''} ({len(r['existing'])})"
              f"\n    new:      {r['new'][:6]}{' ...' if len(r['new']) > 6 else ''} ({len(r['new'])})")
    return results


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True)
    p.add_argument("--latest")
    p.add_argument("--ea-events", default=str(config.PROCESSED))
    p.add_argument("--start", default="2026-09-17")
    p.add_argument("--end", default="2026-10-25")
    p.add_argument("--ref-year", type=int, default=2025)
    p.add_argument("--out")
    p.add_argument("--synthetic", action="store_true")
    args = p.parse_args()
    d = load(args)
    flags = real(d)
    flags["also_existing"] = already_caught(flags, d["latest"])
    print("record-level flags also marked by an existing rule:", int(flags["also_existing"].sum()), "of",
          int(flags["site_id"].notna().sum()))
    res = synthetic(d) if args.synthetic else None
    if args.out:
        flags.to_csv(f"{args.out}-flags.csv", index=False)
        Path(f"{args.out}-summary.json").write_text(json.dumps({"files": d["files"], "synthetic": res}, indent=1, default=str))


if __name__ == "__main__":
    main()
