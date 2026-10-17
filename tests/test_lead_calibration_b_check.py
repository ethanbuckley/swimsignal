"""scripts/lead_calibration_b_check.py: both maps on the same logged probabilities, and the stated
pass rules (docs/LEAD-CALIBRATION-B-TEST-2026-10.md), on synthetic rows."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lead_calibration_b_check import apply_map, check, ece

IDENTITY = {"leads": {str(k): {"iso_x": [0.0, 1.0], "iso_y": [0.0, 1.0]} for k in range(5)}}
HALVE = {"leads": {str(k): {"iso_x": [0.0, 1.0], "iso_y": [0.0, 0.5]} for k in range(5)}}


def rows(p, y, company="Anglian Water", lead=1, calibrated=None):
    p = np.asarray(p, float)
    return pd.DataFrame({"overflow_id": "X", "company": company, "day": "2026-10-20", "lead": lead,
                         "forecast_raw": p, "forecast_calibrated": p if calibrated is None else calibrated,
                         "climatology": 0.05, "observed": np.asarray(y, int)})


def test_leads_outside_the_fitted_range_use_the_nearest():
    cal = {"leads": {"0": {"iso_x": [0, 1], "iso_y": [0, 1]}, "4": {"iso_x": [0, 1], "iso_y": [0, 0.5]},
                     "1": {"iso_x": [0, 1], "iso_y": [0, 1]}, "2": {"iso_x": [0, 1], "iso_y": [0, 1]},
                     "3": {"iso_x": [0, 1], "iso_y": [0, 1]}}}
    out = apply_map(cal, np.array([0.4, 0.4, 0.4]), np.array([-2, 4, 9]))
    assert out.tolist() == pytest.approx([0.4, 0.2, 0.2])


def test_a_map_that_halves_over_forecasts_passes():
    # Forecasts of 0.4 that verify 20% of the time: halving them is right.
    r = rows([0.4] * 1000, [1] * 200 + [0] * 800)
    res = check(r, IDENTITY, HALVE)
    assert res["sane"] and res["enough"]
    assert res["L1"] and res["L2"] and res["L3"] and res["pass"]
    assert res["brier_b"] == pytest.approx(0.16)


def test_the_same_map_fails_when_forecasts_were_right():
    r = rows([0.4] * 1000, [1] * 400 + [0] * 600)
    res = check(r, IDENTITY, HALVE)
    assert not res["L1"] and not res["pass"]


def test_too_few_spills_or_a_mismatched_log_cannot_pass():
    few = check(rows([0.4] * 100, [1] * 20 + [0] * 80), IDENTITY, HALVE)
    assert not few["enough"] and not few["pass"]
    off = check(rows([0.4] * 1000, [1] * 200 + [0] * 800, calibrated=np.full(1000, 0.3)), IDENTITY, HALVE)
    assert not off["sane"] and not off["pass"]


def test_one_company_made_worse_fails_l2_even_if_the_whole_improves():
    good = rows([0.4] * 2000, [1] * 400 + [0] * 1600, company="Anglian Water")
    bad = rows([0.4] * 500, [1] * 200 + [0] * 300, company="Thames Water")
    res = check(pd.concat([good, bad]), IDENTITY, HALVE)
    assert res["L1"] and res["L2_failing"] == ["Thames Water"] and not res["pass"]


def test_ece():
    assert ece(np.array([0, 1.0]), np.array([0.5, 0.5])) == pytest.approx(0.0)
    assert ece(np.array([0, 0.0]), np.array([0.25, 0.25])) == pytest.approx(0.25)
