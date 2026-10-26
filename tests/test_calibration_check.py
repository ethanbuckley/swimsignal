"""The calibration check's own arithmetic (scripts/calibration_check.py): the bands, the two logistic
fits, the Brier decomposition and the stated judgement rules. Network-free and data-free."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("calibration_check", ROOT / "scripts" / "calibration_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["calibration_check"] = mod
    spec.loader.exec_module(mod)
    return mod


cc = _load()


def test_bands_put_a_cut_in_the_band_above():
    p = np.array([0.0, 0.0099, 0.01, 0.03, 0.07, 0.15, 0.40, 0.70, 1.0])
    assert cc.bands(p).tolist() == [0, 0, 1, 2, 3, 4, 5, 6, 6]
    assert len(cc.BAND_NAMES) == len(cc.CUTS) + 1


def test_fits_recover_known_calibration():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.01, 0.6, 200_000)
    x = cc.logit(p)
    # Outcomes drawn from the forecast itself: intercept 0, slope 1.
    y = (rng.uniform(size=len(p)) < p).astype(float)
    w = np.ones(len(p))
    assert cc.fit_offset(y, x, w) == pytest.approx(0, abs=0.03)
    al, b = cc.fit_line(y, x, w)
    assert al == pytest.approx(0, abs=0.05) and b == pytest.approx(1, abs=0.03)
    # A forecast twice too extreme on the logit scale: the true chance has half the logit, so b is about 0.5.
    q = 1 / (1 + np.exp(-0.5 * x))
    y2 = (rng.uniform(size=len(p)) < q).astype(float)
    assert cc.fit_line(y2, x, w)[1] == pytest.approx(0.5, abs=0.03)
    # Everything a fixed amount too high on the logit scale: the offset finds it.
    q3 = 1 / (1 + np.exp(-(x - 0.7)))
    y3 = (rng.uniform(size=len(p)) < q3).astype(float)
    assert cc.fit_offset(y3, x, w) == pytest.approx(-0.7, abs=0.04)


def test_murphy_adds_up_and_is_zero_for_perfect_bands():
    rng = np.random.default_rng(2)
    p = rng.uniform(0, 1, 5000)
    y = (rng.uniform(size=len(p)) < p).astype(float)
    band = cc.bands(p)
    m = cc.murphy(y, p, band, np.ones(len(p)))
    assert m["brier"] == pytest.approx(m["reliability"] - m["resolution"] + m["uncertainty"] + m["within_band"])
    # A forecast equal to each band's observed rate has no reliability loss.
    pb = np.array([y[band == k].mean() for k in band])
    assert cc.murphy(y, pb, band, np.ones(len(p)))["reliability"] == pytest.approx(0, abs=1e-12)


def _stratum(oe_ci, b_ci, blocks_oe, upper):
    return {"spill_overflow_days": 200, "ci": {"o_over_e": {"lo": oe_ci[0], "hi": oe_ci[1]}, "b": {"lo": b_ci[0], "hi": b_ci[1]}},
            "blocks": [{"o_over_e": v} for v in blocks_oe],
            "bands": [{}] * 4 + [{"spill_overflow_days": n, "observed": o, "mean_forecast": f} for n, o, f in upper]}


def test_judgement_follows_the_stated_rules():
    high = [(40, 0.10, 0.25), (30, 0.30, 0.50), (5, 0.9, 0.8)]   # the last band is too small to count
    j = cc.judge(_stratum((0.6, 0.9), (0.6, 0.9), [0.7, 0.8, 0.9, 1.2], high))
    assert j["average"] == "too high on average" and j["range"] == "too extreme: high chances too high"
    assert j["upper_bands_used"] == 2
    # Interval below 1 but only two blocks below 1: the stability rule is not met.
    assert "not met" in cc.judge(_stratum((0.6, 0.9), (0.9, 1.2), [0.7, 1.1, 0.9, 1.2], high))["average"]
    # An interval containing 1 is no clear evidence, whatever the point.
    assert cc.judge(_stratum((0.5, 1.1), (0.9, 1.1), [0.5, 0.5, 0.5, 0.5], high))["average"] == "no clear evidence either way"
    # Too low and too timid contradict overprediction.
    j = cc.judge(_stratum((1.1, 1.5), (1.1, 1.4), [1.2] * 4, high))
    assert j["average"].startswith("too low") and j["range"].startswith("too timid")
    # A slope below 1 with one counted band whose observed rate is above its forecast: not met.
    assert "not met" in cc.judge(_stratum((0.6, 0.9), (0.6, 0.9), [0.7] * 4, [(40, 0.30, 0.25)]))["range"]
    # Too few spills: reported, not judged.
    small = _stratum((0.6, 0.9), (0.6, 0.9), [0.7] * 4, high)
    small["spill_overflow_days"] = 49
    assert cc.judge(small)["average"].startswith("not judged")


def test_inputs_must_be_the_scored_record(tmp_path):
    (tmp_path / "state").mkdir()
    for f in cc.EXPECTED:
        (tmp_path / "state" / f).write_text("x")
    (tmp_path / "scored.csv").write_text("x")
    with pytest.raises(SystemExit, match="not the record PR #338 scored"):
        cc.check_inputs(tmp_path / "scored.csv", tmp_path / "state")
