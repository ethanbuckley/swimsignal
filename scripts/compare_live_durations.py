"""Compare one spill's recorded length in the live feed and in an imported event record, where both cover it.
A description only: nothing is fitted, scored or fed to a model. Off CI:

    uv run python scripts/compare_live_durations.py LIVE_HISTORY.parquet RECORD.parquet --company "Wessex Water" \
        [--from 2026-09-12] [--before 2026-10-18] [--live-offset 0] [--out matches.csv]

A live spill is one (overflow, latest_event_start, latest_event_end) the feed reported in the polls kept in
live_history.parquet (ingest.live.save_live): the company's own start and stop for its latest event, as seen at a
poll. Only spills that start on or after --from (polling began on 11 Sep 2026; the default leaves a day so the polls
were running) and end before --before are used. The default --before, 18 Oct 2026, is the first target day of the
earliest prospective window still open on 13 Nov 2026 (lead calibration B, 18 Oct to 14 Nov), so no outcome inside
an active window is compared. Rows after it are dropped on reading, before anything is counted.

The record is any parquet in the edm_events columns (company_events_<company>.parquet, ea_events_<company>.parquet,
api_events_thames_water.parquet). Each live spill is matched to the record's events at the same overflow that
overlap it, with TOLERANCE either side. Classes:

    same          one record event, start and stop each within TOLERANCE
    one, differs  one record event, start or stop further apart
    split         two or more record events overlap the one live spill
    record lacks  no record event overlaps it

and the other way, record events in the window at overflows the feed reported on, overlapping no live spill
("feed lacks"). Lengths are compared as record minus live, in minutes: for "split" the record length is the sum of
its events and its span (first start to last stop) is given beside it.

--live-offset adds minutes to the feed's times before matching, for a feed whose clock differs from the record's by
a fixed amount (Wessex Water's feed reads an hour earlier than its record in September 2026; the record doc says
how this was measured). Lengths do not depend on it; only which events are found to overlap does.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

TOLERANCE = pd.Timedelta(minutes=1)


def live_spills(hist: pd.DataFrame, company: str, start: pd.Timestamp, before: pd.Timestamp) -> pd.DataFrame:
    """Distinct (site_id, start, end) spills the feed reported for `company`, starting on or after `start` and
    ending before `before`."""
    h = hist[(hist["company"] == company) & hist["latest_event_start"].notna() & hist["latest_event_end"].notna()]
    h = h[(h["latest_event_start"] >= start) & (h["latest_event_end"] < before)
          & (h["latest_event_end"] >= h["latest_event_start"])]
    sp = (h.rename(columns={"latest_event_start": "start", "latest_event_end": "end"})
          .drop_duplicates(["site_id", "start", "end"])[["site_id", "start", "end"]])
    return sp.sort_values(["site_id", "start"]).reset_index(drop=True)


def match(live: pd.DataFrame, rec: pd.DataFrame, tol: pd.Timedelta = TOLERANCE) -> pd.DataFrame:
    """One row per live spill: its class, the record's events overlapping it, and the lengths in minutes."""
    r = rec[rec["site_id"].isin(set(live["site_id"]))][["site_id", "event_start", "event_end"]].dropna()
    m = live.reset_index(names="spill").merge(r, on="site_id", how="left")
    hit = (m["event_start"] <= m["end"] + tol) & (m["event_end"] >= m["start"] - tol)
    m = m[hit.fillna(False)]
    g = m.groupby("spill")
    out = live.copy()
    out["record_events"] = g.size().reindex(out.index).fillna(0).astype(int)
    out["record_start"] = g["event_start"].min().reindex(out.index)
    out["record_end"] = g["event_end"].max().reindex(out.index)
    dur = (m["event_end"] - m["event_start"]).dt.total_seconds() / 60
    out["record_min"] = dur.groupby(m["spill"]).sum().reindex(out.index)
    out["record_span_min"] = (out["record_end"] - out["record_start"]).dt.total_seconds() / 60
    out["live_min"] = (out["end"] - out["start"]).dt.total_seconds() / 60
    same = ((out["record_events"] == 1) & ((out["record_start"] - out["start"]).abs() <= tol)
            & ((out["record_end"] - out["end"]).abs() <= tol))
    out["class"] = np.select([out["record_events"] == 0, same, out["record_events"] == 1],
                             ["record lacks", "same", "one, differs"], "split")
    out["diff_min"] = out["record_min"] - out["live_min"]
    out["start_diff_min"] = (out["record_start"] - out["start"]).dt.total_seconds() / 60
    out["end_diff_min"] = (out["record_end"] - out["end"]).dt.total_seconds() / 60
    return out


def feed_lacks(live: pd.DataFrame, rec: pd.DataFrame, start: pd.Timestamp, before: pd.Timestamp,
               tol: pd.Timedelta = TOLERANCE) -> int:
    """Record events in [start, before) at overflows the feed reported a spill for, overlapping no live spill."""
    r = rec[rec["site_id"].isin(set(live["site_id"])) & (rec["event_start"] >= start)
            & (rec["event_end"] < before)][["site_id", "event_start", "event_end"]].reset_index(names="ev")
    m = r.merge(live, on="site_id")
    hit = (m["event_start"] <= m["end"] + tol) & (m["event_end"] >= m["start"] - tol)
    return int(len(r) - m.loc[hit, "ev"].nunique())


def summary(out: pd.DataFrame) -> dict:
    """Counts by class, and record-minus-live length in minutes where the record has the spill."""
    s = {"live_spills": len(out), **out["class"].value_counts().to_dict()}
    d = out.loc[out["record_events"] > 0, "diff_min"]
    if len(d):
        s.update({"median_diff_min": float(d.median()), "q10_diff_min": float(d.quantile(0.1)),
                  "q90_diff_min": float(d.quantile(0.9)), "within_1_min": float((d.abs() <= 1).mean()),
                  "within_15_min": float((d.abs() <= 15).mean()), "record_longer": float((d > 1).mean()),
                  "record_shorter": float((d < -1).mean()),
                  "median_live_min": float(out.loc[out["record_events"] > 0, "live_min"].median())})
    return s


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("live")
    p.add_argument("record")
    p.add_argument("--company", required=True)
    p.add_argument("--from", dest="start", default="2026-09-12")
    p.add_argument("--before", default="2026-10-18")
    p.add_argument("--record-before", default=None, help="the record's own end, if earlier than --before")
    p.add_argument("--live-offset", type=float, default=0, help="minutes added to the feed's times")
    p.add_argument("--out", default=None)
    a = p.parse_args()
    start = pd.Timestamp(a.start, tz="UTC")
    before = min(pd.Timestamp(a.before, tz="UTC"), pd.Timestamp(a.record_before or a.before, tz="UTC"))
    hist = pd.read_parquet(a.live, columns=["site_id", "company", "latest_event_start", "latest_event_end"])
    hist = hist[hist["latest_event_end"] < before]   # nothing at or after the cut-off is kept
    rec = pd.read_parquet(a.record, columns=["site_id", "event_start", "event_end"])
    live = live_spills(hist, a.company, start, before)
    shift = pd.Timedelta(minutes=a.live_offset)
    live[["start", "end"]] = live[["start", "end"]] + shift
    out = match(live, rec)
    s = summary(out)
    s["feed_lacks"] = feed_lacks(live, rec, start, before)
    s["window"] = f"{start.date()} to {before.date()} (exclusive)"
    s["live_offset_min"] = a.live_offset
    for k, v in s.items():
        print(f"{k}: {v:.3f}" if isinstance(v, float) else f"{k}: {v}")
    if a.out:
        out.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
