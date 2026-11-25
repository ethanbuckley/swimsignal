"""The overflow ledger's season figure (LEDGER stage 2, docs/OVERFLOW-LEDGER-SEASON-CONTRACT-v1.md): CATCH-SIM's removal
rule counted per overflow on made-up rows, the usable-record rule, recorded days on UTC dates, the file's own sums, and
a script that holds no transport code."""
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import export_overflow_ledger_season as season  # noqa: E402
from dipcast.model.transport import combine_daily, risk_label  # noqa: E402

LEVEL = lambda r: season.LEVELS.index(risk_label(float(r)))   # noqa: E731


def _risk(w, t):
    """The forecast's rule as CATCH-SIM's Hindcast.risk applies it, for a made-up spot."""
    w, t = np.asarray(w, float), np.asarray(t, float)

    def risk(X, drop):
        p = np.nan_to_num(X).copy()
        if drop is not None:
            p[drop] = 0.0
        return combine_daily(p, w, t)
    return risk


def test_the_removal_rule_counts_days_per_overflow():
    """Three overflows, weights 0.5, 0.3 and 0.2, no travel. Day 0 is history, outside the season."""
    X = np.array([[1, 1, 1, 0, 1, 0],    # A
                  [0, 0, 1, 1, 1, 0],    # B
                  [0, 0, 0, 1, 1, 0]],   # C
                 dtype=float)
    keep = np.array([False, True, True, True, True, True])
    acc = season.account(X, _risk([0.5, 0.3, 0.2], [0, 0, 0]), LEVEL, keep)
    # day 1: A alone, 0.5 high; without A low. day 2: A and B, 0.65 high; without A 0.3 moderate, without B 0.5 high.
    # day 3: B and C, 0.44 high; without either it is moderate, so it counts at both. day 4: all three, 0.72 very
    # high; any one out leaves it high, so it counts at none. day 5: nothing.
    assert acc["high"].tolist() == [2, 1, 1]
    assert acc["moderate"].tolist() == [1, 0, 0]
    assert acc["lowered"].tolist() == [3, 2, 2]
    assert (acc["high_days"], acc["high_no_single"], acc["moderate_days"]) == (4, 1, 4)
    # not shares: 3 of the 4 high days depend on one overflow, yet the figures add to 4 (day 3 counts twice)
    assert acc["high_days"] - acc["high_no_single"] == 3 and acc["high"].sum() == 4


def test_travel_time_moves_a_spill_into_the_season():
    """A spill on the last history day reaches the spot a day later, inside the season."""
    X = np.array([[1, 0, 0]], dtype=float)
    acc = season.account(X, _risk([0.6], [24.0]), LEVEL, np.array([False, True, True]))
    assert acc["high"].tolist() == [1] and acc["high_days"] == 1


def test_a_removal_that_raises_a_level_stops_the_run():
    def risk(X, drop):
        return np.full(X.shape[1], 0.5 if drop is not None else 0.1)
    with pytest.raises(AssertionError, match="raised a level"):
        season.account(np.ones((1, 2)), risk, LEVEL, np.array([True, True]))


def test_the_usable_record_rule():
    ids = ["ok", "zero", "mismatch", "low_uptime", "not_held", "no_return", "zero_no_up"]
    company = ["A", "A", "A", "A", "B", "A", "A"]
    ret = pd.DataFrame({"edm_operational_pct": [95, 99, 92, 80, 99, 95], "spills": [10, 0, 4, 3, 2, 0]},
                       index=["ok", "zero", "mismatch", "low_uptime", "not_held", "zero_no_up"])
    ret.loc["zero_no_up", "edm_operational_pct"] = 50
    got = season.usable_records(ids, company, covered={"A"}, returns=ret, with_events={"ok", "low_uptime", "not_held"})
    # events and uptime: yes. No events but 0 spills in the return: recorded with no spill day. Spills in the return
    # but no event in the file: the ids disagree, so modelled. Low uptime, a company not held, no return: modelled.
    assert got.tolist() == [True, True, False, False, False, False, False]


def test_recorded_days_are_utc_dates_on_the_local_grid():
    grid, keep = season.season_grid(2025)
    assert grid[0].strftime("%Y-%m-%d %H:%M %Z") == "2025-05-01 00:00 BST" and int(keep.sum()) == 139
    days = pd.DataFrame({"site_id": ["X", "X", "Y", "Z"],
                         "day": pd.to_datetime(["2025-06-01", "2025-06-02", "2025-06-04", "2025-06-04"], utc=True)})
    R = season.recorded_states(days, ["X", "Y"], grid)
    j = {d.strftime("%m-%d"): i for i, d in enumerate(grid)}
    assert R[0, j["06-01"]] == R[0, j["06-02"]] == 1 and R[1, j["06-04"]] == 1   # Z is not a row
    assert R.sum() == 3


def _doc() -> dict:
    """A small valid season file: O1 reaches spots 0 and 1, O2 spot 0; spot 2 has no overflow."""
    links = [[[0, 1, 1, 1, 1, 2, 2], [1, 0, 0, 0, 0, 1, 1]], [[0, 1, 0, 0, 0, 1, 0]]]
    sea = {"usable": 1, "source": ["recorded", "modelled"], "spill_days": [12, None], "expected_days": [9.5, 3.1],
           "covariates_filled": [False, True], "links": links,
           "high": {"recorded": [1, 1], "modelled": [1, 0]}, "moderate": {"recorded": [1, 0], "modelled": [1, 0]},
           "lowered": {"recorded": [3, 1], "modelled": [3, 0]}}
    spot = lambda a, b: {r: dict(zip(("high_days", "high_no_single", "moderate_days"), v, strict=True))   # noqa: E731
                         for r, v in zip(season.RUNS, (a, b), strict=True)}
    return {"schema": season.SCHEMA, "version": season.VERSION, "claim": season.CLAIM,
            "checks": {"inputs_unchanged": True, "no_missing_day": True, "removal_never_raised": True},
            "overflows": {"site_id": ["O1", "O2"], "company": [0, 0]},
            "spots": [{"id": "s1", "overflows": 2, "2025": spot((2, 0, 3), (1, 0, 2))},
                      {"id": "s2", "overflows": 1, "2025": spot((0, 0, 1), (0, 0, 1))},
                      {"id": "s3", "overflows": 0, "2025": None}],
            "seasons": {"2025": sea}}


def test_check_holds_on_a_valid_file_and_catches_faults():
    assert season.check(_doc()) == []
    d = _doc()
    d["seasons"]["2025"]["high"]["recorded"][0] += 1
    assert any("does not match its links" in b for b in season.check(d))
    d = _doc()
    d["seasons"]["2025"]["spill_days"][1] = 0   # a modelled overflow has no recorded days, never 0
    assert any("source and spill days" in b for b in season.check(d))
    d = _doc()
    d["spots"][0]["2025"]["recorded"]["high_days"] = 5   # more one-overflow high days than the links count
    assert any("counted at none" in b for b in season.check(d))
    d = _doc()
    d["spots"][2]["2025"] = copy.deepcopy(d["spots"][1]["2025"])
    assert any("no overflow has figures" in b for b in season.check(d))
    d = _doc()
    d["checks"]["inputs_unchanged"] = False
    assert "checks.inputs_unchanged" in season.check(d)


def test_spearman_uses_overflows_with_a_figure():
    assert season.spearman([0, 0, 1, 2, 3], [0, 0, 1, 2, 3]) == 1.0
    assert season.spearman([0, 0, 1], [0, 0, 0]) is None   # fewer than 3 with a figure


def test_the_script_holds_no_transport_code():
    """Weights and travel times are ledger v1's; the daily chance, the spot's risk and the removal rule are CATCH-SIM's,
    called through lab_catch_sim.Hindcast. The script imports no transport code and copies none."""
    src = (ROOT / "scripts" / "export_overflow_ledger_season.py").read_text()
    code = src.split('"""', 2)[2]
    for name in ("upstream_overflows", "combine_daily", "shift_by_travel", "daily_effects", "dipcast.model.transport",
                 "import transport", "np.prod"):
        assert name not in code, name
    assert "lab_catch_sim" in code and "lcs.Hindcast" in code and "overflow_ledger.v1.json" in code


FILE = ROOT / "data" / "research" / "overflow_ledger_season.v1.json"
LEDGER = ROOT / "data" / "research" / "overflow_ledger.v1.json"


@pytest.fixture(scope="module")
def doc() -> dict:
    return __import__("json").loads(FILE.read_text())


def test_the_committed_file_holds_its_contract(doc):
    ledger = __import__("json").loads(LEDGER.read_text())
    assert season.check(doc, ledger) == []
    assert doc["schema"] == "swimsignal.overflow-ledger-season" and doc["version"] == "1.0.0"
    assert doc["ledger"]["sha256"] == season.sha256(LEDGER)   # built on ledger v1 as it is, and v1 is unchanged
    assert doc["inputs"]["unchanged_after"] and doc["inputs"]["fetches"] == 0 and len(doc["inputs"]["events"]) == 10
    assert sorted(doc["seasons"]) == ["2024", "2025"] and all(s["days"] == 139 for s in doc["seasons"].values())
    assert all(r["covers_season"] for s in doc["seasons"].values() for r in s["records"].values())
    assert doc["statement"]["commit"] == "c06bc356" and (ROOT / doc["statement"]["doc"]).is_file()


def test_the_failed_reproduction_is_kept_with_every_level_equal(doc):
    """Check 4 failed as stated (137 of 139 scores at Cromwheel 2025). The cause is the export's rounding; every level
    is equal. The record keeps the failure."""
    rep = doc["checks"]["reproduction"]
    assert rep["passed"] is False and len(rep["spots"]) == 4
    assert all(v["levels_equal"] == v["days"] == 139 and v["max_score_diff"] <= 1 for v in rep["spots"].values())
    assert rep["spots"]["bw-uke4100-08901 2025"]["scores_equal"] == 137
    record = (ROOT / season.STATEMENT).read_text()
    assert "**Failed as stated.**" in record and "the threshold\nis not changed" in record


def test_the_file_says_it_is_model_accounting(doc):
    claim = doc["claim"]
    assert "An account of SwimSignal's forecast model, not of measured bacteria" in claim["public_wording"]
    assert any("share of the bacteria" in t for t in claim["not_claimed"]) and any("permit" in t for t in claim["not_claimed"])
    assert any("ranking of companies" in t for t in claim["not_claimed"])
    record = (ROOT / claim["evidence"]["record"]).read_text()
    assert "| Production as deployed | 0.376 |" in record and "| Rain in the last 48 hours alone | 0.355 |" in record
    assert "development" in doc["stage"] and "not a measurement" in doc["stage"]


def test_the_build_leaves_the_season_file_out():
    import build_site
    assert "overflow_ledger_season.v1.json" not in build_site.LAB_DATA
    for f in [*(ROOT / "src" / "dipcast").rglob("*.html"), *(ROOT / "src" / "dipcast").rglob("*.js"),
              *(ROOT / "prototypes").rglob("*.html"), *(ROOT / "prototypes").rglob("*.js")]:
        assert "overflow_ledger_season" not in f.read_text(errors="ignore"), f
