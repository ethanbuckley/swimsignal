"""BENCH's first task (docs/BENCH-ECOLI900-2026-11.md): the committed evidence file reproduces the published baseline
scores to 4 decimals with one command, and the baselines are fitted without the season they score."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bench_ecoli900 as B  # noqa: E402
import numpy as np  # noqa: E402
from functools import lru_cache  # noqa: E402

RUN = lru_cache(maxsize=1)(B.run)   # one run (about 50 s) for every test below


def test_the_published_scores_reproduce():
    r = RUN()
    a, h = r["all_rows"], r["rows_with_hindsight"]
    assert (a["rows"], a["over_900"], a["sites"]) == (2265, 230, 38)
    assert (h["rows"], h["over_900"], h["sites"]) == (1537, 208, 32)
    assert (a["month_rate"]["brier"], a["last_sample"]["brier"]) == (0.0931, 0.0852)
    assert (h["month_rate"]["brier"], h["last_sample"]["brier"], h["model_hindsight"]["brier"]) == (0.1204, 0.1099, 0.0824)
    assert (h["model_hindsight"]["skill_vs_month_rate"], h["model_hindsight"]["skill_95"]) == (0.3151, [0.1732, 0.4094])
    assert (h["model_hindsight"]["auc_pooled"], a["last_sample"]["auc_pooled"], a["month_rate"]["auc_pooled"]) == (0.8537, 0.6208, 0.4332)


def test_a_learned_baseline_never_sees_the_season_it_scores():
    rs = B.rows()
    p = B.baselines(rs)["month_rate"]
    # Every 2024 row's month rate comes from 2023, 2025 and 2026 alone.
    y24 = [i for i, r in enumerate(rs) if r["season"] == 2024 and r["month"] == 7]
    other = [r["over"] for r in rs if r["season"] != 2024 and r["month"] == 7]
    assert abs(p[y24[0]] - sum(other) / len(other)) < 1e-12


def test_the_review_variants_are_forward_and_fair():
    """Review of 5 Nov 2026, after the first run: forward-only fitting and a previous result counted only when known."""
    r = RUN()
    f = r["review_forward_only"]["rows_with_model_forward"]
    assert (f["rows"], f["over_900"], f["sites"]) == (1023, 106, 32)
    assert (f["model_forward"]["brier"], f["model_forward"]["brier_95"], f["model_forward"]["skill_vs_month_rate"], f["model_forward"]["skill_95"]) == (0.0756, [0.0478, 0.1074], 0.184, [0.0679, 0.3189])
    assert f["model_forward"]["auc_pooled"] == 0.7853 and f["month_rate"]["auc_pooled"] == 0.512
    # The last sample, fitted forward and counted only when its result was 3 days old: no skill shown.
    k = r["review_forward_and_3_days"]["rows_with_model_forward"]["last_sample"]["skill_95"]
    assert k[0] < 0 < k[1]
    # The leave-one-year-out hindsight is never in a forward table.
    assert "model_hindsight" not in f


def test_forward_fits_see_only_earlier_seasons_and_the_join_is_whole():
    rs = B.rows()
    p = B.baselines(rs, forward=True)["month_rate"]
    i = next(i for i, r in enumerate(rs) if r["season"] == 2025 and r["month"] == 7)
    before = [r["over"] for r in rs if r["season"] < 2025 and r["month"] == 7]
    assert abs(p[i] - sum(before) / len(before)) < 1e-12
    assert all(np.isnan(p[j]) for j, r in enumerate(rs) if r["season"] == 2023)   # nothing before 2023
    # Every published hindsight joins to the study's rows, and is the same estimate (published to 3 decimals).
    h = [r for r in rs if r["hindsight"] is not None]
    assert all(r["loyo"] is not None and abs(r["hindsight"] - r["loyo"]) < 0.0006 for r in h)
    # A previous result counts only when its sample was at least 3 days older.
    assert sum(r["prev"] is not None for r in B.rows(gap_days=3.0)) < sum(r["prev"] is not None for r in rs)


def test_the_review_reports_within_season_auc_and_paired_differences():
    """Review of 5 Nov 2026: a pooled AUC across leave-one-season-out fits ranks one fit's numbers against another's;
    within each season every prediction comes from one fit. Differences are paired, from the same draws."""
    r = RUN()
    a = r["all_rows"]["month_rate"]
    assert (a["auc_pooled"], a["auc_within_season"], a["auc_within_season_95"]) == (0.4332, 0.5361, [0.4863, 0.6196])
    f = r["review_forward_only"]["rows_with_model_forward"]
    assert f["brier_differences"]["month_rate - model_forward"] == {"point": 0.0171, "ci_95": [0.0062, 0.0321]}
    assert f["brier_differences"]["last_sample - model_forward"] == {"point": 0.0192, "ci_95": [0.007, 0.0335]}
    s = r["review_turnaround_sensitivity"]
    assert s["0_days"]["month_rate_minus_last_sample"] == {"point": 0.0063, "ci_95": [0.0007, 0.0127]}
    assert s["7_days"]["month_rate_minus_last_sample"]["point"] == -0.0028
