"""The helpers of scripts/concentration_study.py (docs/CONCENTRATION-STUDY-2026-11.md), on simulated data."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import concentration_study as m  # noqa: E402


def _sim(n_sites=25, per=40, beta=0.6, sigma=0.5, tau=0.7, seed=0):
    rng = np.random.default_rng(seed)
    site = np.repeat([f"s{i}" for i in range(n_sites)], per)
    u = rng.normal(0, tau, n_sites)
    x = rng.normal(size=len(site))
    y_true = 2.0 + beta * x + np.repeat(u, per) + rng.normal(0, sigma, len(site))
    cens = np.select([y_true < 1.0, y_true > 4.0], [-1, 1], 0)
    y = np.clip(y_true, 1.0, 4.0)
    return pd.DataFrame({"x": x, "site": site, "y": y, "cens": cens}), u


def test_censored_ri_recovers_slope_noise_and_site_spread():
    d, _ = _sim()
    fit = m.CensoredRI(["x"]).fit(d, d["y"].to_numpy(), d["cens"].to_numpy(), d["site"].to_numpy())
    slope_per_unit = fit.theta[1] / d["x"].std(ddof=0)
    assert fit.converged
    assert abs(slope_per_unit - 0.6) < 0.06
    assert abs(fit.sigma - 0.5) < 0.05
    assert abs(fit.tau - 0.7) < 0.25


def test_seen_site_background_moves_the_forecast_and_new_site_uses_the_prior():
    d, u = _sim(seed=1)
    fit = m.CensoredRI(["x"]).fit(d, d["y"].to_numpy(), d["cens"].to_numpy(), d["site"].to_numpy())
    hi, lo = f"s{int(np.argmax(u))}", f"s{int(np.argmin(u))}"
    X = pd.DataFrame({"x": [0.0, 0.0, 0.0]})
    p = fit.p_over(X, np.array([hi, lo, "never seen"]), cut=3.0)
    assert p[0] > p[2] > p[1]


def test_pit_is_roughly_uniform_when_the_model_is_right():
    d, _ = _sim(seed=2)
    fit = m.CensoredRI(["x"]).fit(d, d["y"].to_numpy(), d["cens"].to_numpy(), d["site"].to_numpy())
    new, _ = _sim(seed=3)
    new["site"] = "unseen"
    pit = fit.pit(new, new["site"].to_numpy(), new["y"].to_numpy(), new["cens"].to_numpy(), np.random.default_rng(0))
    counts = np.histogram(pit, bins=5, range=(0, 1))[0] / len(pit)
    assert np.all(np.abs(counts - 0.2) < 0.06)


def test_row_loglik_uses_mass_for_censored_values():
    ll = m.row_loglik(np.array([1.0, 1.0, 1.0]), 1.0, np.array([1.0, 1.0, 1.0]), np.array([-1, 0, 1]))
    assert np.allclose(np.exp(ll[[0, 2]]), 0.5)
    assert np.isclose(ll[1], np.log(1 / np.sqrt(2 * np.pi)))


def _frame():
    return m.prepare(pd.DataFrame({
        "bw_id": ["uke4100-08901", "uke4200-08904", "ukd1203-45650", "ukd1203-45700"] * 3,
        "sample_time": pd.to_datetime(["2024-06-01 11:00"] * 4 + ["2025-06-01 11:00"] * 4 + ["2026-06-01 11:00"] * 4).tz_localize("Europe/London"),
        "ecoli": [10, 950, 10000, 50] * 3, "qual": ["<", "=", ">", "="] * 3, "rain_48h": [0, 12, 3, 30] * 3}))


def test_prepare_codes_censoring_and_the_900_line():
    d = _frame()
    assert d["cens"].tolist()[:4] == [-1, 0, 1, 0]
    assert d["over"].tolist()[:4] == [0, 1, 1, 0]
    assert d["wet"].tolist()[:4] == [False, True, False, True]
    assert d["catchment"].tolist()[:4] == ["Wharfe", "Wharfe", "Windermere", "Windermere"]


def test_catchment_year_folds_keep_group_and_year_out_of_training():
    d = _frame()
    for _, tr, te in m.folds(d, "cxy"):
        assert not set(d.loc[te, "catchment"]) & set(d.loc[tr, "catchment"])
        assert not set(d.loc[te, "year"]) & set(d.loc[tr, "year"])
    fwd = list(m.folds(d, "fwd"))
    assert [n for n, _, _ in fwd] == ["2025", "2026"]
    assert all(d.loc[tr, "year"].max() < d.loc[te, "year"].min() for _, tr, te in fwd)


def test_every_listed_bathing_water_has_a_group():
    import json
    sites = json.loads((ROOT / "data" / "raw" / "bathing_waters_inland.json").read_text())
    assert {s["id"] for s in sites} == set(m.CATCHMENT)


def test_brier_split_adds_up_and_boot_brackets_the_mean():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 200)
    p = rng.uniform(size=200)
    s = np.repeat(np.arange(10), 20)
    b = m.brier_split(y, p, s)
    assert np.isclose(b["between_site"] + b["within_site"], b["brier"])
    d = rng.normal(0.1, 1, 400)
    lo, hi = m.boot_diff(d, np.repeat(np.arange(40), 10))
    assert lo < d.mean() < hi


def test_warn_counts_split_the_four_cells():
    c = m.warn_counts(np.array([1, 1, 0, 0]), np.array([0.3, 0.1, 0.3, 0.1]))
    assert (c["hits"], c["false_reassurance"], c["false_alarms"], c["quiet_correct"]) == (1, 1, 1, 1)
