"""Backtest bench (docs/BACKTEST-BENCH-2026-11.md): the scoring maths, the outcome blinding, the refusal to make a
final read of an uncommitted candidate, and the self-check candidate equal to its reference. Synthetic rows only:
the frozen rows live outside git, so nothing here needs them."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "backtest_bench"))
import bench as B  # noqa: E402


def rows(n_sites=6, per=30, seed=0) -> pd.DataFrame:
    from dipcast.model.ecoli import features
    rng = np.random.default_rng(seed)
    n = n_sites * per
    r48, r24 = rng.gamma(1.0, 5.0, n), rng.gamma(1.0, 2.5, n)
    risk = rng.uniform(0, 0.3, n)
    lake = np.repeat(rng.integers(0, 2, n_sites), per).astype(float)
    t = pd.Series(pd.date_range("2024-05-01 12:00", periods=per, freq="4D", tz="Europe/London").tolist() * n_sites)
    X = features(r48, r24, risk, lake, t)
    log_e = 2.0 + 0.5 * X["lrain48"] + 0.1 * X["logit_risk"] + rng.normal(0, 0.6, n)
    ecoli = np.round(10 ** log_e)
    names = [f"Site {i}" for i in range(n_sites)]
    names[0], names[1] = "Windermere, A", "Windermere, B"
    d = pd.DataFrame({"bw_id": np.repeat([f"bw{i}" for i in range(n_sites)], per),
                      "name": np.repeat(names, per), "kind": np.where(lake == 1, "lake", "river"),
                      "sample_time": t, "season": t.dt.year, "month": t.dt.month, "ecoli": ecoli,
                      "log_ecoli": np.log10(np.clip(ecoli, 1, None)), "over": (ecoli > 900).astype(int),
                      "ecoli_qual": "=", "sm": np.nan, "prior_reads": None, "rain_48h": r48, "rain_24h": r24,
                      "risk_model": risk})
    d = pd.concat([d, X.drop(columns=["lake"])], axis=1)
    d["lake"] = lake
    d["cluster"] = d["name"].map(B.water_body)
    return d


def test_auc_matches_sklearn_with_ties():
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(1)
    for _ in range(20):
        y = rng.integers(0, 2, 50)
        if 0 < y.sum() < 50:
            p = np.round(rng.uniform(size=50), 1)   # many ties
            assert B._auc(y, p) == pytest.approx(roc_auc_score(y, p))


def test_water_bodies_resample_together():
    assert B.water_body("Windermere, Fellfoot") == B.water_body("Windermere, Lakeside YMCA") == "Windermere"
    assert B.water_body("Hampstead Heath (Mens Pond)") == "Hampstead Heath"
    assert B.water_body("Frensham Great Pond") == "Frensham Great Pond"


def test_candidate_never_sees_outcomes():
    seen = {}

    class Spy:
        @staticmethod
        def fit(r):
            return None

        @staticmethod
        def predict(m, r):
            seen["cols"] = set(r.columns)
            return np.full(len(r), 0.1)

    d = rows()
    B.run_candidate(Spy, d, d)
    assert not seen["cols"] & set(B.OUTCOMES)


@pytest.mark.parametrize("bad", [np.full(3, 0.1), np.full(180, 1.5), np.r_[np.full(179, 0.1), np.nan]])
def test_bad_candidate_output_is_refused(bad):
    class C:
        fit = staticmethod(lambda r: None)
        predict = staticmethod(lambda m, r: bad)

    with pytest.raises(SystemExit):
        B.run_candidate(C, rows(), rows())


def test_self_check_candidate_equals_its_reference():
    sys.path.insert(0, str(ROOT / "scripts" / "backtest_bench" / "candidates"))
    import production_refit as cand
    tr, te = rows(seed=2), rows(seed=3)
    a = B.run_candidate(cand, tr, te)["p900"]
    b = B.production_refit(tr, te)["p900"]
    assert np.array_equal(a, b)


def test_site_rate_shrinks_toward_the_pooled_rate():
    tr = pd.DataFrame({"bw_id": ["a"] * 10 + ["b"] * 30, "ecoli": [1000] * 10 + [10] * 30})
    te = pd.DataFrame({"bw_id": ["a", "b", "new"]})
    p = B.site_rate(tr, te)["p900"]
    pooled = 10 / 40
    assert p[0] == pytest.approx((10 + B.SHRINK_M * pooled) / (10 + B.SHRINK_M))
    assert p[1] == pytest.approx((0 + B.SHRINK_M * pooled) / (30 + B.SHRINK_M))
    assert p[2] == pytest.approx(pooled)


def test_report_identical_figures_differ_by_zero():
    d = rows()
    f = B.production_refit(d, d)
    rep = B.report(d, {"candidate": f, **{n: f for n in B.REFERENCES}}, "candidate")
    for v in rep["differences"]["candidate-production_refit"].values():
        assert v["mean"] == 0 and v["ci95"] == [0.0, 0.0]


def test_final_read_refuses_an_uncommitted_candidate(tmp_path):
    p = ROOT / "scripts" / "backtest_bench" / "candidates" / "_untracked_test_candidate.py"
    p.write_text("def fit(r):\n    return None\n")
    try:
        with pytest.raises(SystemExit, match="not committed"):
            B.committed(p)
    finally:
        p.unlink()
