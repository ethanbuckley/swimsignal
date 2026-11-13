"""The diagnosis's arithmetic (scripts/thames_same_day_diagnosis.py): each split adds back to the Brier score, the
alert-count comparison handles ties, and the reading rule follows the record."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import thames_same_day_diagnosis as T  # noqa: E402


def _rows(n=4000, seed=7):
    rng = np.random.default_rng(seed)
    f = rng.beta(0.5, 8, n)
    y = (rng.random(n) < np.clip(0.6 * f + 0.01, 0, 1)).astype(float)
    act = rng.random(n) < 0.05
    w = rng.integers(0, 3, n).astype(float)
    return f, y, act, w


def test_level_spread_and_association_add_to_the_brier_score():
    f, y, _, w = _rows()
    m = T.murphy(f, y, w)
    assert np.isclose(m["level"] + m["spread"] + m["association"], m["brier"])
    assert np.isclose(m["calibration"], m["level"] + m["spread"])


def test_a_constant_forecast_has_no_spread_and_all_association():
    y = np.array([0, 0, 1, 0, 1, 0, 0, 0], float)
    m = T.murphy(np.full(8, 0.25), y, np.ones(8))
    assert m["spread"] == 0 and np.isclose(m["association"], y.mean() * (1 - y.mean()))


def test_the_band_split_with_its_remainder_is_exact():
    f, y, _, w = _rows()
    band = np.searchsorted(np.asarray(T.CUTS), f, side="right")
    b = T.banded(f, y, w, band, len(T.CUTS) + 1)
    assert np.isclose(b["reliability"] - b["resolution"] + b["uncertainty"] + b["remainder"], b["brier"])


def test_two_valued_forecast_has_no_band_remainder():
    _, y, act, w = _rows()
    p = np.where(act, 0.3, 0.02)
    b = T.banded(p, y, w, act.astype(int), 2)
    assert abs(b["remainder"]) < 1e-12


def test_hits_at_an_alert_count_share_ties_pro_rata():
    f = np.array([0.9, 0.5, 0.5, 0.1])
    y = np.array([1, 1, 0, 1], float)
    assert T.hits_at(f, y, np.ones(4), 1) == 1
    assert T.hits_at(f, y, np.ones(4), 2) == 1.5        # one of the two tied rows, half a spill
    assert T.hits_at(f, y, np.ones(4), 3) == 2
    assert T.hits_at(f, y, np.ones(4), 9) == 3


def test_side_contributions_add_to_the_cell_difference():
    f, y, act, w = _rows()
    p = np.where(act, 0.3, 0.02)
    band = np.searchsorted(np.asarray(T.CUTS), f, side="right")
    s = T.cell_stats(f, p, y, act, band, w)
    assert np.isclose(s["starts_contribution"] + s["ends_contribution"], s["diff_brier"])
    for k in ("starts", "ends"):
        assert np.isclose(s[f"{k}_contribution_level"] + s[f"{k}_contribution_rest"], s[f"{k}_contribution"])


def _cell(**ci):
    keys = {"diff_calibration", "diff_auc", "diff_association", "diff_spread", "starts_contribution", "ends_contribution"}
    zero = {"lo": -1.0, "hi": 1.0}
    return {"judged": True, "ci_overflow_and_block": {k: ci.get(k, zero) for k in keys}}


def test_the_reading_rule():
    above, below = {"lo": 0.1, "hi": 0.2}, {"lo": -0.2, "hi": -0.1}
    assert T.reading({"judged": False})["applied"] is False
    assert T.reading(_cell(diff_calibration=above))["answer"] == "level (calibration)"
    assert T.reading(_cell(diff_auc=below))["answer"] == "ranking"
    assert T.reading(_cell(diff_association=above))["answer"] == "ranking"
    assert T.reading(_cell(diff_calibration=above, diff_auc=below))["answer"] == "both"
    r = T.reading(_cell(diff_auc=above, starts_contribution=above))
    assert r["answer"] == "not shown either way" and r["F_ranks_better"] and r["loss_sits_on"] == ["starts"]
