"""Spills in dry weather: each overflow's dry spill-days in a year, by the rule stated in
docs/DRY-WEATHER-SPILLS-TEST-2026-10.md, and which overflows a spot's page notes for it.

A dry day at an overflow is a UTC day with under 0.25 mm of ERA5-Land rain in its cell on that day and on each of the
two before, all three known. A dry spill-day is a dry day on which an event that started on a dry day spilled. A dry
day with a spill only from events that started on wet days is a continuing day: drain-down or a long storm spill,
neither dry nor quiet, so it is left out of both counts. The functions are the test's harness
(scripts/dry_weather_spills_eval/score.py), which stays as the record of that run.

The note is a description of the EA's records, not a forecast: the spill model never reads these counts. The test
found that the history does not add to the model (Question 2 failed), and that the models already rank dry-day spills
better than the history does (Question 1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

THRESHOLD_MM = 0.25   # the EA's dry-day threshold ("What are dry day spills?", 28 Aug 2024), on three days, not two
MAX_SPAN = 60         # features.spill_days' cap on the days one event marks
# The page note's rule: at least this many dry spill-days in the year, on at least this share of its dry days. Ten
# keeps out an overflow with a few blips; a fifth keeps out a big overflow whose ten are a small share of its dry days.
NOTE_MIN_DAYS = 10
NOTE_MIN_RATE = 0.2


def dry_days(daily: pd.DataFrame, thr: float = THRESHOLD_MM) -> pd.Series:
    """Per row with rain_d, rain_d1 and rain_d2 (features.daily_rain_features, or a site-day frame built from it):
    under `thr` mm on the day and on each of the two before, all three known. A NaN compares False, so an unknown day
    is never dry."""
    return (daily["rain_d"] < thr) & (daily["rain_d1"] < thr) & (daily["rain_d2"] < thr)


def merge_overlaps(ev: pd.DataFrame) -> pd.DataFrame:
    """Each overflow's events with overlapping ones merged. Events that do not overlap stay apart, whatever the gap."""
    e = ev[["site_id", "event_start", "event_end"]].dropna(subset=["event_start"]).copy()
    e["event_end"] = e["event_end"].fillna(e["event_start"])
    e = e.sort_values(["site_id", "event_start"], kind="mergesort").reset_index(drop=True)
    prev = e.groupby("site_id")["event_end"].cummax().groupby(e["site_id"]).shift()
    group = (prev.isna() | (e["event_start"] > prev)).cumsum()
    return e.groupby(group).agg(site_id=("site_id", "first"), start=("event_start", "min"),
                                end=("event_end", "max")).reset_index(drop=True)


def dry_started_days(merged: pd.DataFrame, cell_of: pd.DataFrame, daily: pd.DataFrame,
                     thr: float = THRESHOLD_MM) -> pd.DataFrame:
    """(site_id, day) on which a dry-started event spilled: a merged event whose start's UTC day is a dry day at the
    overflow's cell, marking every day from its start's day to its stop's day (at most MAX_SPAN on), as spill_days
    marks them. `cell_of` maps site_id to cell_lat, cell_lon; events of other overflows are dropped."""
    m = merged.merge(cell_of, on="site_id", how="inner")
    m["start_day"] = m["start"].dt.floor("D")
    flags = daily[["cell_lat", "cell_lon", "day"]].assign(dry=dry_days(daily, thr).to_numpy())
    m = m.merge(flags.rename(columns={"day": "start_day"}), on=["cell_lat", "cell_lon", "start_day"], how="left")
    m = m[m["dry"].eq(True)]
    n = ((m["end"].dt.floor("D") - m["start_day"]).dt.days.clip(lower=0, upper=MAX_SPAN) + 1).to_numpy()
    base = np.repeat(m["start_day"].dt.tz_convert(None).to_numpy().astype("datetime64[D]"), n)
    offs = np.concatenate([np.arange(k) for k in n]) if len(n) else np.zeros(0, int)
    out = pd.DataFrame({"site_id": np.repeat(m["site_id"].to_numpy(), n),
                        "day": pd.to_datetime(base + offs.astype("timedelta64[D]")).tz_localize("UTC")})
    return out.drop_duplicates()


def classify(frame: pd.DataFrame, touched: pd.DataFrame, thr: float = THRESHOLD_MM) -> pd.DataFrame:
    """For each row of `frame` (site_id, day, y and the rain columns):
      dry        the day is a dry day at the overflow's cell
      continuing a dry day with a spill, but only from events started on days that were not dry
      kept       dry and not continuing: the dry days counted
      y_dry      a dry spill-day"""
    dry = dry_days(frame, thr).to_numpy()
    key = pd.MultiIndex.from_frame(frame[["site_id", "day"]])
    hit = key.isin(pd.MultiIndex.from_frame(touched[["site_id", "day"]]))
    y = frame["y"].to_numpy() == 1
    cont = dry & y & ~hit
    return pd.DataFrame({"dry": dry, "continuing": cont, "kept": dry & ~cont, "y_dry": dry & y & hit},
                        index=frame.index)


def overflow_counts(frame: pd.DataFrame, cls: pd.DataFrame) -> pd.DataFrame:
    """Per overflow of `frame` (one year): its days, spill-days, dry days, continuing days, n (dry days less
    continuing days), k (dry spill-days) and the rate k / n."""
    t = pd.DataFrame({"site_id": frame["site_id"].to_numpy(), "company": frame["company"].to_numpy(),
                      "y": frame["y"].to_numpy(), **{c: cls[c].to_numpy() for c in cls}})
    out = t.groupby(["site_id", "company"]).agg(
        days=("y", "size"), spill_days=("y", "sum"), dry_days=("dry", "sum"), continuing=("continuing", "sum"),
        n=("kept", "sum"), k=("y_dry", "sum")).reset_index()
    out["rate"] = out["k"] / out["n"].where(out["n"] > 0)
    return out


def noted(dry_spill_days: int, dry_days: int) -> bool:
    """Whether an overflow with `dry_spill_days` of its `dry_days` gets the page note."""
    return dry_days > 0 and dry_spill_days >= NOTE_MIN_DAYS and dry_spill_days / dry_days >= NOTE_MIN_RATE
