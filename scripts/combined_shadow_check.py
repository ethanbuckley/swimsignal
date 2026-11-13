"""The combined-v1 shadow's check before its window opens (docs/COMBINED-SHADOW-2026-11.md), read only:

    uv run python scripts/combined_shadow_check.py <state dipcast.duckdb>

It reads the shadow's own table (shadow_combined_v1) and nothing else: no outcome, no label, no other shadow table.
It checks that every row has the frozen rule and model stamp; that the eight companies, and only they, are routed to
v2; that a row with no rain has no chance; that every fallback row carries the base alone and every uplift row the
frozen formula on its logged parts; that no row was issued after 08:00 local or holds an input later than its
issue. It prints the first logged build and the window it implies: 28 target days from four days after the first
issue day with a logged row. It reads a copy of the state database and writes nothing.
"""

from __future__ import annotations

import sys
from datetime import timedelta

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from dipcast.model.live_status import MAX_GAP_H  # noqa: E402
from dipcast.shadow_combined import LEADS, LOG_BY_HOUR, MODELS, NINE, RULE, TABLE, combine  # noqa: E402
from dipcast.shadow_regional import EIGHT  # noqa: E402

WINDOW_DAYS = 28
LEAD_IN_DAYS = max(LEADS)                 # the window opens on the first target day with every lead logged
SLOT = pd.Timedelta(minutes=15)           # status_read_at is the middle of the poll's half-hour slot
# A forecast stamps its issue time first, then waits up to 12 s for the river gauge and reads the rain. A cell the
# build's prefetch missed is fetched then, seconds after the stamp. Later than this is an input from after the issue.
RAIN_SLACK = pd.Timedelta(minutes=2)
LOCAL_TZ = "Europe/London"


def check(rows: pd.DataFrame) -> list[str]:
    err = []
    if set(rows["rule"]) != {RULE} or set(rows["models"]) != {MODELS}:
        err.append(f"rules {set(rows['rule'])} or model stamps {set(rows['models'])} are not the frozen ones")
    if not rows["company"].isin(NINE).all():
        err.append("a row is not one of the nine English companies")
    if (rows["company"].isin(EIGHT) != (rows["route"] == "v2_offsets")).any():
        err.append("a row of the eight companies was not routed to v2, or another row was")
    if not rows["lead"].isin(LEADS).all():
        err.append("a row has a lead outside 0 to 4")
    uu = rows["route"] == "production"
    if not np.isclose(rows.loc[uu, "p_base"], rows.loc[uu, "p_raw"], equal_nan=True).all():
        err.append("a production-routed row's base differs from production's raw chance")
    none = rows["applied"] == "no_rain"
    if rows.loc[none, "p_combined"].notna().any() or rows.loc[~none, "p_combined"].isna().any():
        err.append("a row with no rain has a chance, or a row with rain has none")
    fb = rows["applied"] == "fallback"
    if not np.isclose(rows.loc[fb, "p_combined"], rows.loc[fb, "p_base"]).all():
        err.append("a fallback row differs from its base")
    up = rows[rows["applied"] == "uplift"]
    if not up["status_known"].all() or up[["p_candidate", "p_d2", "spilling_at_issue"]].isna().any(axis=None):
        err.append("an uplift row has no known status or is missing a part")
    else:
        want = combine(up["p_base"].to_numpy(), up["p_candidate"].to_numpy(), up["p_d2"].to_numpy(), np.zeros(len(up), bool))
        if not np.allclose(up["p_combined"], want, atol=1e-12):
            err.append("an uplift row is not the frozen formula on its logged parts")
    if rows.loc[~rows["status_known"], "applied"].eq("uplift").any():
        err.append("a row whose status was not known took the uplift")
    issued = pd.to_datetime(rows["issued_at"], utc=True)
    local = issued.dt.tz_convert(LOCAL_TZ)
    late = (local - local.dt.normalize()) > pd.Timedelta(hours=LOG_BY_HOUR)
    if late.any():
        err.append(f"{int(late.sum())} rows were issued after {LOG_BY_HOUR}:00 local")
    read = pd.to_datetime(rows["status_read_at"], utc=True)
    known = rows["status_known"].to_numpy(dtype=bool)
    if (read[known] > issued[known] + SLOT).any():
        err.append("a known status was read after the forecast was issued")
    if ((issued[known] - read[known]) > pd.Timedelta(hours=MAX_GAP_H) + SLOT).any() or read[known].isna().any():
        err.append(f"a known status is older than {MAX_GAP_H:g} hours or has no reading time")
    rain = pd.to_datetime(rows["rain_issued_at"], utc=True)
    if (rain > issued + RAIN_SLACK).any():
        err.append(f"{int((rain > issued + RAIN_SLACK).sum())} rows have rain fetched after the forecast was issued")
    return err


def window(rows: pd.DataFrame) -> tuple[str, str, str, str]:
    """(first logged issue, the window's first and last target day, the earliest read day)."""
    first = pd.Timestamp(rows["issued_at"].min()).tz_convert(LOCAL_TZ)
    start = first.date() + timedelta(days=LEAD_IN_DAYS)
    end = start + timedelta(days=WINDOW_DAYS - 1)
    return first.isoformat(timespec="minutes"), start.isoformat(), end.isoformat(), (end + timedelta(days=2)).isoformat()


def main(db: str) -> None:
    con = duckdb.connect(db, read_only=True)
    try:
        rows = con.execute(f"SELECT * FROM {TABLE}").df()
    finally:
        con.close()
    if rows.empty:
        raise SystemExit("no shadow rows yet")
    err = check(rows)
    first, start, end, read = window(rows)
    print(f"{len(rows)} rows; applied {rows['applied'].value_counts().to_dict()}; by route {rows['route'].value_counts().to_dict()}")
    print(f"status known on {rows['status_known'].mean():.1%} of rows; rain time missing on {rows['rain_issued_at'].isna().mean():.1%}")
    issued, rain = pd.to_datetime(rows["issued_at"], utc=True), pd.to_datetime(rows["rain_issued_at"], utc=True)
    print(f"rows whose rain was fetched in the forecast's own call (up to {RAIN_SLACK.seconds // 60} min after its stamp): {int((rain > issued).sum())}")
    print("rows by issue day:", rows.groupby(rows["issue_day"].astype(str)).size().to_dict())
    print(f"first logged forecast {first}; window {start} to {end}; read on or after {read}")
    print("\n".join(err) or "checks hold")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main(sys.argv[1])
