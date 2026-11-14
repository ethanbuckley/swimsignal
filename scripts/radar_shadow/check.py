"""The radar shadow's checks before any read (docs/RADAR-SHADOW-2026-11.md, "The bar", checks run first), and the
window's first date. Reads only the table shadow_radar_v1, on a copy of the state database, and no label.

    uv run python scripts/radar_shadow/check.py <copy of dipcast.duckdb>

Prints the builds and rows by state and pair, and every failed check. Exit 1 if any check fails.
"""

from __future__ import annotations

import sys

import duckdb
import numpy as np
import pandas as pd

from dipcast import shadow_radar as sr


def check(t: pd.DataFrame) -> list[str]:
    """Each failed check, in words; [] when all hold."""
    bad = []
    if not (t["rule"] == sr.RULE).all() or not (t["models"] == sr.MODELS).all():
        bad.append("a row with another rule or model stamp")
    st = t["pair"] == "status"
    if not (np.isclose(t.loc[st, "p_candidate"], t.loc[st, "p_r0s"], equal_nan=True).all()
            and np.isclose(t.loc[~st, "p_candidate"], t.loc[~st, "p_c"], equal_nan=True).all()):
        bad.append("p_candidate is not the model its pair names")
    if not (np.isclose(t.loc[st, "p_reference"], t.loc[st, "p_ps"], equal_nan=True).all()
            and np.isclose(t.loc[~st, "p_reference"], t.loc[~st, "p_p"], equal_nan=True).all()):
        bad.append("p_reference is not the model its pair names")
    fb = t["radar_state"].isin(["fallback", "stopped"])
    if not np.isclose(t.loc[fb, "p_candidate"], t.loc[fb, "p_reference"], equal_nan=True).all():
        bad.append("a fallback row whose candidate is not its reference")
    issued = pd.to_datetime(t["issued_at"], utc=True)
    local = issued.dt.tz_convert("Europe/London")
    day0 = local.dt.normalize()
    hours = (local - day0).dt.total_seconds() / 3600
    want = np.minimum(21, 3 * np.floor(hours / 3 + 0.5)).astype(int)
    if not (want.to_numpy() == t["issue_hour"].to_numpy()).all():
        bad.append("issue_hour does not match issued_at")
    built = pd.to_datetime(t["build_at"], utc=True)
    mod = pd.to_datetime(t["radar_newest_modified"], utc=True)
    if (mod > built).any():
        bad.append("a composite that reached the bucket after the listing")
    if (built > issued).any():
        bad.append("a listing after the issue time")
    return bad


def main(db: str) -> int:
    con = duckdb.connect(db, read_only=True)
    try:
        t = con.execute(f"SELECT * FROM {sr.TABLE}").df()
    finally:
        con.close()
    if t.empty:
        print("no rows logged")
        return 0
    t["build_at"] = pd.to_datetime(t["build_at"], utc=True)
    builds = t.groupby("build_at")["radar_state"].agg(lambda s: s.mode().iloc[0])
    print(f"rows {len(t):,}; builds {t['build_at'].nunique()}; first issue day {t['issue_day'].min()}; "
          f"last {t['issue_day'].max()}")
    print("rows by radar_state:", t["radar_state"].value_counts().to_dict())
    print("rows by pair:", t["pair"].value_counts().to_dict())
    print("builds by their main state:", builds.value_counts().to_dict())
    bad = check(t)
    for b in bad:
        print("FAILED:", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
