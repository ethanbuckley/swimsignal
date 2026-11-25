"""Counts-only readiness for the live-status shadow read (docs/LIVE-STATUS-SHADOW-TEST-2026-10.md, "Readiness check").
Off CI, by hand, at any time in the window:

    gh release download state -p dipcast.duckdb -p live_coverage.parquet -D /tmp/shadow-state
    curl -s https://swimsignal.co.uk/data/verification_live.csv -o /tmp/shadow-state/verification_live.csv
    uv run python scripts/live_status_shadow_readiness.py /tmp/shadow-state 2026-10-25 2026-11-21

It counts decision forecasts, how many carry a shadow, how many had a known status, the scored rows and spill rows so
far, and the stretches with no current reading at any overflow. It computes no score and never compares the shadow
with an outcome."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from dipcast.forecast_log import DECISION_HOUR, LOCAL_TZ, load_coverage
from dipcast.model import live_status

MIN_SPILLS = 200   # the test's minimum: spill rows with a known status, at each lead

SQL = f"""
    WITH f AS (
        SELECT site_id, issue_day, target_day, lead, p_status, status_known, issued_at,
               (issued_at AT TIME ZONE '{LOCAL_TZ}') <= (issue_day::TIMESTAMP + INTERVAL {int(DECISION_HOUR)} HOUR) AS before_cutoff
        FROM forecast_overflows
        WHERE has_live AND coalesce(rain_available, TRUE) AND target_day BETWEEN ? AND ?)
    SELECT site_id, issue_day, target_day, lead, (p_status IS NOT NULL) AS has_shadow,
           coalesce(status_known, FALSE) AS known
    FROM f WHERE before_cutoff
    QUALIFY row_number() OVER (PARTITION BY site_id, issue_day, target_day ORDER BY issued_at DESC) = 1
"""


def quiet_stretches(cov: pd.DataFrame, first: date, last: date, over_h: float = live_status.MAX_GAP_H) -> pd.Series:
    """Stretches longer than `over_h` hours with no current reading at any overflow, indexed by their end (UTC)."""
    t = np.sort(live_status.reading_times(cov, first, last)["t"].unique())
    gaps = pd.Series(np.diff(t) / np.timedelta64(1, "h"), index=pd.DatetimeIndex(t[1:]))
    return gaps[gaps > over_h].round(1)


def main(folder: Path, start: str, end: str) -> None:
    con = duckdb.connect(str(folder / "dipcast.duckdb"), read_only=True)
    f = con.execute(SQL, [start, end]).df()
    f["target_day"] = pd.to_datetime(f["target_day"]).dt.strftime("%Y-%m-%d")
    by_issue = f.groupby("issue_day").agg(rows=("known", "size"), known=("known", "mean")).round(3)
    print("Share of decision forecasts with a known status, by issue day:")
    print(by_issue.to_string())
    v = pd.read_csv(folder / "verification_live.csv", comment="#")
    v = v[(v["day"] >= start) & (v["day"] <= end)]
    m = v.merge(f, left_on=["overflow_id", "day", "lead"], right_on=["site_id", "target_day", "lead"], how="left")
    m[["known", "has_shadow"]] = m[["known", "has_shadow"]].fillna(False).astype(bool)
    t = m.groupby("lead").agg(scored=("observed", "size"), with_shadow=("has_shadow", "mean"),
                              spill_rows=("observed", "sum"),
                              spill_rows_status_known=("observed", lambda y: int(y[m.loc[y.index, "known"]].sum())))
    t["enough"] = t["spill_rows_status_known"] >= MIN_SPILLS
    print(f"\nScored rows in the window so far: {len(v)} on {v['day'].nunique()} days, the last {v['day'].max()}")
    print(t.round(4).to_string())
    cov = load_coverage(folder / "live_coverage.parquet")
    first = pd.Timestamp(start).date() - timedelta(days=12)
    q = quiet_stretches(cov, first, pd.Timestamp(end).date())
    print(f"\nStretches over {live_status.MAX_GAP_H:g} h with no current reading at any overflow, from {first}: {len(q)}")
    print(q.to_string())


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
