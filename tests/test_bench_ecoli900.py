"""BENCH's first task (docs/BENCH-ECOLI900-2026-11.md): the committed evidence file reproduces the published baseline
scores to 4 decimals with one command, and the baselines are fitted without the season they score."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bench_ecoli900 as B  # noqa: E402


def test_the_published_scores_reproduce():
    r = B.run()
    a, h = r["all_rows"], r["rows_with_hindsight"]
    assert (a["rows"], a["over_900"], a["sites"]) == (2265, 230, 38)
    assert (h["rows"], h["over_900"], h["sites"]) == (1537, 208, 32)
    assert (a["month_rate"]["brier"], a["last_sample"]["brier"]) == (0.0931, 0.0852)
    assert (h["month_rate"]["brier"], h["last_sample"]["brier"], h["model_hindsight"]["brier"]) == (0.1204, 0.1099, 0.0824)
    assert (h["model_hindsight"]["skill_vs_month_rate"], h["model_hindsight"]["skill_95"]) == (0.3151, [0.1732, 0.4094])
    assert (h["model_hindsight"]["auc"], a["last_sample"]["auc"], a["month_rate"]["auc"]) == (0.8537, 0.6208, 0.4332)


def test_a_learned_baseline_never_sees_the_season_it_scores():
    rs = B.rows()
    p = B.baselines(rs)["month_rate"]
    # Every 2024 row's month rate comes from 2023, 2025 and 2026 alone.
    y24 = [i for i, r in enumerate(rs) if r["season"] == 2024 and r["month"] == 7]
    other = [r["over"] for r in rs if r["season"] != 2024 and r["month"] == 7]
    assert abs(p[y24[0]] - sum(other) / len(other)) < 1e-12
