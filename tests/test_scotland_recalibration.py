"""The Scotland trial's calibration map (scripts/scotland_recalibration.py): the fit and the pass rule's parts."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scotland_recalibration as sr  # noqa: E402


def test_the_map_recovers_a_known_platt_shift():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.01, 0.6, 200_000)
    y = rng.random(p.size) < 1 / (1 + np.exp(-(0.6 + 1.1 * sr.logit(p))))
    m = sr.fit_map(p, y)
    assert abs(m["a"] - 0.6) < 0.05 and abs(m["b"] - 1.1) < 0.05


def test_an_identity_map_changes_nothing():
    p = np.array([1e-9, 0.02, 0.5, 0.97, 1.0])
    out = sr.apply_map({"a": 0.0, "b": 1.0}, p)
    assert np.allclose(out, np.clip(p, sr.EPS, 1 - sr.EPS))


def test_a_lead_passes_only_when_level_brier_and_history_all_hold():
    rng = np.random.default_rng(1)
    n_sites, n_days = 30, 120
    days = pd.date_range("2025-01-01", periods=n_days, freq="D", tz="UTC")
    dk = pd.DataFrame({"site_id": np.repeat([f"s{i}" for i in range(n_sites)], n_days),
                       "day": np.tile(days, n_sites)})
    truth = rng.uniform(0.02, 0.6, len(dk))
    dk["y"] = (rng.random(len(dk)) < truth).astype(int)
    dk[sr.hs.EARLIER] = np.full(len(dk), dk["y"].mean())
    dk["rain_d"], dk["rain_d1"] = 0.0, 0.0
    raw = 1 / (1 + np.exp(-(sr.logit(truth) - 0.7)))       # forecasts too low, as in Scotland
    m = sr.fit_map(raw, dk["y"].to_numpy())
    r = sr.check_lead(dk, raw, m, 0, n_boot=200)
    assert r["R1"] and r["R2"] and r["R3"]
    assert r["level_unmapped"] < 0.9 < r["level"] < 1.1
    bad = sr.check_lead(dk, raw, {"a": 0.0, "b": 1.0}, 0, n_boot=200)
    assert not bad["R1"] and not bad["R2"]
