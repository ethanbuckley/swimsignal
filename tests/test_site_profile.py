"""scripts/site_profile.py: the joins and the page, on a made-up trace (the river network is not
needed). A real run is checked by hand against data/upstream/<id>.json (docs/MARKETS-2026-10.md, T8)."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import site_profile as sp


def up():
    return pd.DataFrame({"site_id": ["A1", "B2"], "site_name": ["GRASSINGTON/STW", "Bridge Lane/CSO"],
                         "company": ["Yorkshire Water"] * 2, "distance_m": [500.0, 21_800.0],
                         "travel_h": [0.3, 12.1], "weight": [0.98, 0.21], "has_live": [True, False]})


def returns():
    rows = []
    for y in sp.YEARS:
        rows.append({"site_id": "A1", "year": y, "spills": 10, "spill_hours": 20.0, "edm_operational_pct": 100.0})
        if y >= 2023:
            rows.append({"site_id": "B2", "year": y, "spills": 2, "spill_hours": 5.0, "edm_operational_pct": 67.0})
    rows.append({"site_id": "ZZ", "year": 2025, "spills": 99, "spill_hours": 99.0, "edm_operational_pct": 100.0})
    return pd.DataFrame(rows)


def test_each_overflow_gets_its_own_returns_and_the_years_add_up():
    t = sp.with_returns(up(), returns())
    assert t.loc[t.site_id == "A1", "spills_2021"].item() == 10 and pd.isna(t.loc[t.site_id == "B2", "spills_2021"].item())
    s = {r["year"]: r for r in sp.summary(t)}
    assert s[2021] == {"year": 2021, "with_return": 1, "spills": 10, "hours": 20.0, "reach_hours": 20.0 * 0.98}
    assert s[2025]["spills"] == 12 and s[2025]["reach_hours"] == 20.0 * 0.98 + 5.0 * 0.21   # ZZ is not upstream


def test_the_page_puts_the_caveat_first_and_never_calls_the_water_safe():
    t = sp.with_returns(up(), returns())
    md, page = sp.render("Test spot", 53.9, -1.8, {"mode": "river", "watercourse": "River Wharfe"}, t, sp.summary(t))
    assert md.index(sp.CAVEAT) < md.index("## In short") and sp.CREDITS in md
    assert "Grassington sewage works overflow · Grassington/STW (A1)" in md and "Bridge Lane storm overflow · " in md and "| under 1 |" in md and "| 67% |" in md
    assert "safe" not in md.lower().replace("not say whether the water is fit", "")
    assert page.startswith("<!doctype html>") and "<table>" in page and "<p class='caveat'>" in page


def test_a_point_with_nothing_upstream_says_so():
    md, _ = sp.render("Tarn", 54.5, -3.1, {"mode": "isolated", "watercourse": None}, pd.DataFrame(), [])
    assert "no river flowing into it" in md and sp.CAVEAT in md
