"""The regional shadow's check before its window opens (docs/REGIONAL-ROUTING-2026-11.md, section 4), read only:

    uv run python scripts/regional_shadow_check.py <state dipcast.duckdb>

On the shadow table (shadow_regional_v1) it checks that every row routed to production carries production's own
raw chance, that every row of the eight companies was routed to v2 and no other row was, and that every row has the
frozen rule and model stamp. It prints the first logged build and the window it implies: 28 UK days from the first
full day after it. It reads a copy of the state database and writes nothing.
"""

from __future__ import annotations

import sys
from datetime import timedelta

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from dipcast.shadow_regional import EIGHT, RULE, TABLE, V2_SHA256  # noqa: E402

WINDOW_DAYS = 28


def check(rows: pd.DataFrame) -> list[str]:
    err = []
    prod = rows["route"] == "production"
    same = np.isclose(rows.loc[prod, "p_regional"], rows.loc[prod, "p_raw"], equal_nan=True)
    if not same.all():
        err.append(f"{int((~same).sum())} production-routed rows differ from production's raw chance")
    eight = rows["company"].isin(EIGHT)
    if (eight != (rows["route"] == "v2_offsets")).any():
        err.append("a row of the eight companies was not routed to v2, or another row was")
    if set(rows["rule"]) != {RULE} or set(rows["v2_sha"]) != {V2_SHA256[:16]}:
        err.append(f"rules {set(rows['rule'])} or model stamps {set(rows['v2_sha'])} are not the frozen ones")
    return err


def window(rows: pd.DataFrame) -> tuple[str, str, str]:
    first = pd.Timestamp(rows["issued_at"].min()).tz_convert("Europe/London")
    start = first.date() + timedelta(days=1)
    end = start + timedelta(days=WINDOW_DAYS - 1)
    return first.isoformat(timespec="minutes"), start.isoformat(), end.isoformat()


def main(db: str) -> None:
    con = duckdb.connect(db, read_only=True)
    try:
        rows = con.execute(f"SELECT * FROM {TABLE}").df()
    finally:
        con.close()
    if rows.empty:
        raise SystemExit("no shadow rows yet")
    err = check(rows)
    first, start, end = window(rows)
    print(f"{len(rows)} rows; by route {rows['route'].value_counts().to_dict()}")
    print(f"first logged build {first}; window {start} to {end}; read on {(pd.Timestamp(end) + pd.Timedelta(days=1)).date()}")
    print("\n".join(err) or "checks hold")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main(sys.argv[1])
