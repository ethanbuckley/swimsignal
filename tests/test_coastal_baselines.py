"""The coastal explorer's rules and the baseline scorer's arithmetic (docs/COASTAL-BASELINES-2026-11.md), on made-up
data: no sample result is read here."""

import importlib.util
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parents[1] / "scripts" / "coastal_baselines"


def _load(name):
    """Load by path under a unique name: other tests import modules called `score` and `build`."""
    spec = importlib.util.spec_from_file_location(f"coastal_baselines_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


build = _load("build")
score = _load("score")


def made_up(n_sites=60, seed=1) -> pd.DataFrame:
    """Five seasons at n_sites sites, 18 samples a season. Exceedance depends on the site and on r24, not on spills."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_sites):
        base = rng.normal(-3.5, 0.8)
        for year in range(2022, 2027):
            prev = np.nan
            for k in range(18):
                month = 5 + k * 5 // 18
                r24 = rng.exponential(2.0)
                p = 1 / (1 + np.exp(-(base + 0.9 * np.log1p(r24))))
                e = float(rng.choice([10, 40, 120])) if rng.random() > p else float(rng.choice([600, 1500]))
                rows.append({"site_id": f"uk{s:05d}-{s:05d}", "year": year, "month": month, "prev_ecoli": prev,
                             "exceeds_500": e > 500, "exceeds_250": e > 250, "r24": r24, "r72": r24 + rng.exponential(3.0),
                             "rain_ok": year >= 2025, "near_h": rng.exponential(1.0) if year in (2024, 2025) else np.nan,
                             "ring_h": 0.0, "river_h": 0.0, "prf_level": "increased" if rng.random() < 0.1 else "normal",
                             "ea_own_forecast": s % 2 == 0, "site_group": s % 5})
                prev = e
    return pd.DataFrame(rows)


def test_a_result_below_detection_is_never_over_a_line():
    v, q = pd.Series([10.0, 500.0, 501.0, 500.0, 499.0, 2000.0]), pd.Series(["<", "=", "=", ">", ">", "<"])
    assert build.over(v, q, 500).tolist() == [False, False, True, True, False, False]


def test_count_reads_the_archives_result_text():
    assert build.count("<10") == (10.0, "<") and build.count("620") == (620.0, "=") and build.count(None)[0] is None


def test_two_results_in_one_minute_keep_the_higher():
    t = pd.Timestamp("2025-06-01 10:00", tz="Europe/London")
    df = pd.DataFrame({"site_id": ["a", "a", "b", "b", "c"], "time": [t] * 5, "value": [10.0, 300.0, 20.0, 20.0, 5.0]})
    out, info = build.one_per_minute(df)
    assert dict(zip(out["site_id"], out["value"])) == {"a": 300.0, "b": 20.0, "c": 5.0}
    assert info == {"minutes_with_equal_results": 1, "minutes_with_different_results": 1}


def test_gaps_count_the_ends_of_the_season_and_empty_weeks():
    longest, weeks = build.gaps([date(2025, 5, 20), date(2025, 5, 27), date(2025, 9, 1)], 2025)
    assert longest == (date(2025, 9, 1) - date(2025, 5, 27)).days - 1
    none, all_weeks = build.gaps([], 2025)
    assert none == 139 and weeks == all_weeks - 3


def test_rolling_rain_sums_the_hours_at_or_before_the_label():
    hours = pd.date_range("2025-05-01", periods=6, freq="h", tz="UTC")
    df = pd.DataFrame({"s": [1.0, 2.0, np.nan, 4.0, 5.0, 6.0]}, index=hours)
    out = build.rolling(df, 3, "sum")["s"]
    assert np.isnan(out.iloc[1]) and out.iloc[2:].tolist() == [3.0, 6.0, 9.0, 15.0]


def test_weighted_auc_matches_scikit_learn_and_counts_a_resampled_site_twice():
    rng = np.random.default_rng(0)
    s, y = np.round(rng.random(500), 1), rng.integers(0, 2, 500)
    parts = score.auc_parts(s)
    assert abs(score.auc_weighted(*parts, y, np.ones(500)) - roc_auc_score(y, s)) < 1e-12
    w = rng.integers(0, 3, 500).astype(float)
    assert abs(score.auc_weighted(*parts, y, w) - roc_auc_score(np.repeat(y, w.astype(int)), np.repeat(s, w.astype(int)))) < 1e-12


def test_site_rate_leaves_out_the_rows_own_year_and_a_held_out_site_gets_the_pooled_rate():
    d = score.table(made_up(), "over_500")
    hist, test = d["year"] != 2026, d["year"] == 2026
    fold = score.Fold(d, hist, test)
    i = int(np.flatnonzero(hist)[0])
    same_site = hist & (d["site"] == d["site"][i])
    other_years = same_site & (d["year"] != d["year"][i])
    want = (d["y"][other_years].sum() + fold.m * fold.p0) / (other_years.sum() + fold.m)
    assert abs(fold.site_rate[i] - want) < 1e-12
    j = int(np.flatnonzero(test & (d["site"] == d["site"][i]))[0])
    assert abs(fold.site_rate[j] - (d["y"][same_site].sum() + fold.m * fold.p0) / (same_site.sum() + fold.m)) < 1e-12
    held = score.Fold(d, d["group"] != 0, d["group"] == 0)
    assert np.allclose(held.site_rate[d["group"] == 0], held.p0)


def test_a_planted_rain_effect_is_found_and_an_empty_input_is_not(monkeypatch):
    monkeypatch.setattr(score, "RESAMPLES", 200)
    d = score.table(made_up(n_sites=150), "over_500")
    pred, _ = score.held_out(d, "Y")
    assert set(pred["fold"]) == {"2022", "2023", "2024", "2025", "2026"}
    assert pred.loc[d["year"][pred.index] < 2025, "rain"].isna().all()       # no radar before 2025
    assert pred.loc[d["year"][pred.index] == 2026, "spills"].isna().all()    # no spill files for 2026
    r = score.evaluate(pred, d, ["B0", "R", "rain", "spills"], [("R+rain", "R|rain"), ("R+spills", "R|spills")])
    rain, spills = r["pairs"]["R+rain vs R|rain"], r["pairs"]["R+spills vs R|spills"]
    assert rain["d_brier_ci"][1] < 0 and rain["d_auc"] > 0.03
    assert spills["d_brier_ci"][0] < 0 < spills["d_brier_ci"][1] or abs(spills["d_brier"]) < 1e-3
    # B0 is one number a fold, so pooled over folds its AUC is not exactly 0.5; its skill against itself is zero.
    assert abs(r["models"]["B0"]["auc"] - 0.5) < 0.05 and abs(r["models"]["B0"]["bss_b0"]) < 1e-12
