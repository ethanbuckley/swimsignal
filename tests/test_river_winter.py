"""RIVER-WINTER (docs/RIVER-WINTER-READ-2026-11.md, scripts/river_winter/): which rows are in the study, which half
they fall in, the month-removed figure and the outcome words. Made-up rows only."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "river_winter"))
import winter_read as wr


def test_a_winter_is_named_by_its_january():
    assert wr.winter_of(2013, 12) == 2014 and wr.winter_of(2014, 1) == 2014 and wr.winter_of(2014, 4) == 2014
    assert wr.winter_of(2014, 10) == 2015


def test_rows_kept_are_river_winter_kept_purpose_and_held_out():
    s = pd.DataFrame({"material": [wr.MATERIAL] * 5 + ["SEA WATER"], "purpose_code": ["MU", "MU", None, "MU", "PI", "MU"],
                      "month": [11, 7, 11, 2, 4, 11], "span": ["held_out"] * 3 + ["development", "held_out", "held_out"]})
    assert wr.winter_mask(s).tolist() == [True, False, False, False, True, False]


def _rows(rng, n_points=6, n=60, signal=0.0, calendar=0.0):
    out = []
    for p in range(n_points):
        month = rng.choice([10, 11, 12, 1, 2, 3, 4], n)
        cal = np.where(np.isin(month, [12, 1, 2]), 1.0, 0.0)
        x = rng.normal(size=n)
        out.append(pd.DataFrame({"bw_id": f"P{p}", "system": f"S{p % 3}", "season": rng.choice([2014, 2016], n),
                                 "month": month, "x": x + cal,
                                 "log_ecoli": signal * x + calendar * cal + rng.normal(size=n)}))
    return pd.concat(out, ignore_index=True)


def test_month_removed_keeps_a_day_to_day_signal_and_drops_a_calendar_one():
    rng = np.random.default_rng(1)
    day = _rows(rng, signal=1.0)
    cal = _rows(rng, calendar=3.0)
    assert wr.rho_month_removed(day, "x") > 0.5
    assert wr.rho_raw(cal, "x") > 0.3                    # the figure and the count share the calendar
    assert abs(wr.rho_month_removed(cal, "x")) < 0.12    # and nothing else


def test_point_months_with_too_few_rows_are_left_out():
    d = pd.DataFrame({"bw_id": "P", "system": "S", "season": 2014, "month": [1, 1, 1, 2, 2], "x": [1.0, 2, 3, 4, 5],
                      "log_ecoli": [1.0, 2, 3, 4, 5]})
    assert len(wr.month_removed(d, "x", "bw_id")) == 3


def test_outcome_words():
    base = {"points_15_or_more": 28, "rows": 2800, "condition_1_pass": True, "condition_2_pass": True}
    assert wr.outcome(base) == "both pass"
    assert wr.outcome({**base, "condition_2_pass": False}).startswith("order is the calendar")
    assert wr.outcome({**base, "condition_1_pass": False}) == "order fails"
    assert wr.outcome({**base, "points_15_or_more": 19}) == "too few rows"


def test_the_script_names_the_frozen_files_it_scores():
    prod = ROOT / "data" / "processed" / "ecoli_model.json"
    cand = json.loads((ROOT / "docs" / "river-unseen" / "river_range_v0e.json").read_text())
    assert wr.sha(prod) == wr.PRODUCTION_SHA and cand["name"] == "river-range-v0e"
    assert wr.sha(wr.CANDIDATE) == wr.CANDIDATE_SHA
    text = wr.STATEMENT.read_text()
    assert all(h[:8] in text for h in (wr.PRODUCTION_SHA, wr.CANDIDATE_SHA, wr.SEALED_SHA))
