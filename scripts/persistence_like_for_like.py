"""Exploratory, added after the calibration check's run (docs/CALIBRATION-CHECK-2026-10.md, "Exploratory:
the same rule, rebuilt and as logged"). Not part of that check's stated test.

The check's sensitivity compared two different rules: the shadow's logged status at issue (status 1, spilling
now) and #338's rebuilt "active" (spilling now or within RECENT_SPILL_HOURS before). This holds the rule fixed:
spilling now, rebuilt by #338's persistence_status (its spilling_now) against the shadow's logged
spilling_at_issue, on exactly the same rows, each turned into a chance the same way (fit_two_sided, by lead,
on those rows). The gap between the two is then what the rebuild's hindsight adds, for this window only.

    uv run python scripts/persistence_like_for_like.py --scored verification_live.csv --state /tmp/s
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibration_check import LEAD_GROUPS, check_inputs  # noqa: E402
from evaluate_2027 import read_published  # noqa: E402
from interim_usefulness import FIRST_DAY, SQL, decision_rows, fit_two_sided, persistence_status  # noqa: E402

from dipcast.forecast_log import LOCAL_TZ, load_coverage  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", required=True, type=Path)
    ap.add_argument("--state", required=True, type=Path)
    a = ap.parse_args()
    check_inputs(a.scored, a.state)
    # The rows as calibration_check.main builds them (the rain step is not needed here).
    sc = read_published(a.scored)
    sc = sc[sc["day"] >= str(FIRST_DAY)].reset_index(drop=True)
    first, last = sc["day"].min(), sc["day"].max()
    con = duckdb.connect(str(a.state / "dipcast.duckdb"), read_only=True)
    try:
        log = con.execute(SQL, [str(date.fromisoformat(first) - timedelta(days=1)), last]).df()
    finally:
        con.close()
    log["site_id"] = log["site_id"].astype(str)
    log["target_day"] = pd.to_datetime(log["target_day"])
    dec = decision_rows(log)
    dec = dec.assign(day=dec["target_day"].dt.strftime("%Y-%m-%d"))
    df = sc.merge(dec[["site_id", "day", "lead", "issued_ms", "target_day", "spilling_at_issue"]],
                  left_on=["overflow_id", "day", "lead"], right_on=["site_id", "day", "lead"], how="left")
    issued_min = pd.to_datetime(df["issued_ms"], unit="ms", utc=True).dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%dT%H:%M%:z")
    match = df["issued_ms"].notna() & (issued_min == df["issued_at"])
    j = df[match].copy()
    j = j.assign(site_id=j["site_id"].astype(str), issued_ms=j["issued_ms"].astype(np.int64))
    ps = persistence_status(j, pd.read_parquet(a.state / "live_history.parquet"),
                            load_coverage(a.state / "live_coverage.parquet"), pd.read_parquet(a.state / "poll_log.parquet"))
    for c in ps:
        df[c] = False
        df.loc[ps.index, c] = ps[c].to_numpy()

    y, p, lead = df["observed"].to_numpy(float), df["forecast_calibrated"].to_numpy(float), df["lead"].to_numpy()
    # The same rows for both: logged by the shadow, status known to the rebuild, issue time matched.
    same = df["spilling_at_issue"].notna().to_numpy() & df["known"].to_numpy(bool) & match.to_numpy()
    logged = df["spilling_at_issue"].fillna(0).to_numpy() > 0
    rebuilt = df["spilling_now"].to_numpy(bool)
    p_logged, fit_logged = fit_two_sided(y, logged, lead, same)
    p_rebuilt, fit_rebuilt = fit_two_sided(y, rebuilt, lead, same)
    out = {"rows_same": int(same.sum()), "first_day": df.loc[same, "day"].min(), "last_day": df.loc[same, "day"].max(),
           "agreement": {"both_on": int((same & logged & rebuilt).sum()), "logged_only": int((same & logged & ~rebuilt).sum()),
                         "rebuilt_only": int((same & ~logged & rebuilt).sum()), "both_off": int((same & ~logged & ~rebuilt).sum())},
           "fitted": {"logged": fit_logged, "rebuilt": fit_rebuilt}, "by_leads": []}
    for lg, leads in LEAD_GROUPS.items():
        m = same & np.isin(lead, leads)
        bf, bl, br = (float(np.mean((q[m] - y[m]) ** 2)) for q in (p, p_logged, p_rebuilt))
        out["by_leads"].append({"leads": lg, "rows": int(m.sum()), "spill_rows": int(y[m].sum()),
                                "brier_forecast": bf, "brier_now_logged": bl, "brier_now_rebuilt": br,
                                "skill_vs_logged": 1 - bf / bl, "skill_vs_rebuilt": 1 - bf / br})
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
