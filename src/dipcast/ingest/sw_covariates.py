"""The spill model's three overflow covariates for Scotland, from Scottish Water's event history
(Scotland plan task S2). Off CI; nothing here reaches the site.

The pooled spill model reads lta_spills, spill_hours and edm_operational_pct (model/features.py),
which in England come from the Environment Agency's annual returns. Scotland has no rows there, so
without this every Scottish overflow gets the defaults 20, 100 and 90. This module derives the
three per overflow and year from S1's events (ingest/sw_history.py, data/processed/sw_events.parquet
and sw_events_yearly.parquet). Contains Scottish Water data licensed under the Open Government
Licence v3.0.

The rule. Written here on 10 Oct 2026, before the first run, and not to be changed after the
results are seen; a different rule is a new, dated rule beside this one.

    Events. Every S1 event whose duration is over 15 min 30 s (SHORT_S), or unknown, in every year
    and both files. The reported file and every file before 2025 keep only events over 15 min 30 s
    (Scottish Water's guide, plan section 2.2), so the cut makes 2025 count like the earlier years
    and matches the plan's label rule (section 6). The duration is the published one where given,
    else the computed one, as S1's report tests it. A day record (no end) counts from midnight for
    its published duration, as in S1's yearly(). Rows of the same overflow with the same start and
    end in both files count once.

    spills (the year's counted spills). The EA's 12/24-hour block rule, sw_history.count_12_24, over
    the overflow's events of the sheet year; a run of blocks does not carry over 1 January. Both
    files and all measurement points of one Asset ID are pooled, as in S1.

    spill_hours. The total duration in hours of the counted events, before 12/24 counting, as the
    EA returns define total_spill_duration_hrs_calculated.

    edm_operational_pct. 100 x the published "No. of Days Data" / days in the year, at most 100 (the
    largest of the overflow's rows that year). Missing where none is published (the reported file
    has none for 2021 and 2022).

    Status. The best status of the overflow's rows that year across both files ("events", "no
    events", "no data", "not required", in that order). "events" and "no events" give a count (zero
    when no event survives the cut); "no data" and "not required" give spills and spill_hours
    missing, and do not count as a year of history.

    lta_spills. Wales's long-term average rule (wales_annual.long_term_average), from FIRST_YEAR =
    2021, the first year the Scottish files hold: for return year Y, the mean of spills over the
    overflow's years 2021..Y with a count and uptime of at least 90%; else over its years with a
    count, whatever the uptime; else missing. An unknown uptime is never at least 90%.

    The year before. A hindcast or forecast of year Y uses the covariates of return year Y - 1, as
    scripts/train.py does with the EA returns (covariates_for).

What this cannot match (inferred, not checked): the EA's own long-term average may span years
before 2021, and English returns count all events, short ones too, as far as this code knows. S3
should report the hindcast with these covariates and with the defaults, as the plan's arms say.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dipcast.ingest.sw_history import SHORT_S, STATUSES, count_12_24
from dipcast.ingest.wales_annual import long_term_average

FIRST_YEAR = 2021
COUNTED = ("events", "no events")
COLS = ["site_id", "year", "status", "spills", "spill_hours", "edm_operational_pct", "lta_spills",
        "lta_years", "lta_basis", "events", "short_dropped", "days_data"]


def counted_events(ev: pd.DataFrame) -> pd.DataFrame:
    """S1 events kept by the rule: over SHORT_S or of unknown duration, one row per overflow,
    start and end across both files. Adds `dur_h`, the duration used for spill_hours."""
    dur_h = ev["duration_published_h"].fillna(ev["duration_h"])
    keep = dur_h.isna() | ((dur_h * 3600).round() > SHORT_S)
    out = ev[keep].assign(dur_h=dur_h[keep])
    return out.drop_duplicates(["site_id", "event_start", "event_end"]).reset_index(drop=True)


def yearly_counts(ev: pd.DataFrame) -> pd.DataFrame:
    """site_id, year, events, spills, spill_hours, short_dropped from S1's events (rule above)."""
    kept = counted_events(ev)
    dropped = (ev.drop_duplicates(["site_id", "event_start", "event_end"])
               .groupby(["site_id", "year"]).size().sub(kept.groupby(["site_id", "year"]).size(), fill_value=0))
    rows = []
    for (sid, year), g in kept.groupby(["site_id", "year"]):
        ends = g["event_end"].fillna(g["event_start"] + pd.to_timedelta(g["dur_h"].fillna(0), unit="h"))
        rows.append({"site_id": sid, "year": int(year), "events": len(g),
                     "spills": count_12_24(g["event_start"], ends), "spill_hours": float(g["dur_h"].fillna(0).sum())})
    out = pd.DataFrame(rows, columns=["site_id", "year", "events", "spills", "spill_hours"])
    d = dropped.rename("short_dropped").reset_index()
    return d.merge(out, on=["site_id", "year"], how="outer")


def site_years(yearly: pd.DataFrame) -> pd.DataFrame:
    """One row per overflow and year from S1's yearly table (rows per file): the best status and
    the largest days of data across the files, and uptime from it."""
    y = yearly.assign(r=yearly["status"].map(STATUSES.index))
    g = y.groupby(["site_id", "year"])
    out = g.agg(r=("r", "min"), days_data=("days_data", "max")).reset_index()
    out["status"] = out["r"].map(dict(enumerate(STATUSES)))
    days_in_year = np.where(pd.to_datetime(out["year"].astype(str) + "-12-31").dt.dayofyear == 366, 366, 365)
    out["edm_operational_pct"] = (100 * out["days_data"] / days_in_year).clip(upper=100)
    return out.drop(columns="r")


def covariates(ev: pd.DataFrame, yearly: pd.DataFrame, first_year: int = FIRST_YEAR) -> pd.DataFrame:
    """The covariate table (COLS), one row per overflow and return year, by the module's rule."""
    sy = site_years(yearly).merge(yearly_counts(ev), on=["site_id", "year"], how="left")
    counted = sy["status"].isin(COUNTED)
    for c in ("events", "spills", "short_dropped"):
        sy[c] = sy[c].where(~counted, sy[c].fillna(0))
    sy["spill_hours"] = sy["spill_hours"].where(~counted, sy["spill_hours"].fillna(0.0))
    sy.loc[~counted, ["spills", "spill_hours", "events"]] = np.nan
    sy["short_dropped"] = sy["short_dropped"].fillna(0)
    lta = long_term_average(sy[["site_id", "year", "spills", "edm_operational_pct"]], first_year=first_year)
    out = sy.merge(lta[["site_id", "year", "lta_spills", "lta_years", "lta_basis"]], on=["site_id", "year"], how="left")
    for c in ("events", "spills", "short_dropped", "lta_years"):
        out[c] = out[c].astype("Int64")
    return out[COLS].sort_values(["site_id", "year"]).reset_index(drop=True)


def covariates_for(cov: pd.DataFrame, year: int) -> pd.DataFrame:
    """The covariates a model run for `year` uses: return year `year` - 1, keyed by `year` (as
    scripts/train.py's site_year_covariates). Overflows whose year before has no count are left
    out; site_static_features would give them the defaults."""
    prev = cov[(cov["year"] == year - 1) & cov["spills"].notna()]
    return prev.assign(year=year)[["site_id", "year", "lta_spills", "spill_hours", "edm_operational_pct",
                                   "lta_basis"]].reset_index(drop=True)
