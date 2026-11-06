"""scripts/lake_line_candidates.py (docs/LAKE-LINE-CANDIDATES-2026-11.md): the lake-slope model, the recalibration, the
folds' separation, the frozen file for the 2027 read and the recorded verdict. The full run needs the scratch rows
(cached forecast rain), so it is not repeated here; the committed inputs' hashes are checked instead."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lake_line_candidates as m  # noqa: E402

SCORES = Path(f"{m.DOC}-scores.json")


def _sim(n_sites=12, per=60, tau_v=0.4, seed=0):
    """Lake rows only: a site level, a shared response to x, and a site-specific extra slope on lake_x_wet."""
    rng = np.random.default_rng(seed)
    site = np.repeat([f"s{i}" for i in range(n_sites)], per)
    u, v = rng.normal(0, 0.5, n_sites), rng.normal(0, tau_v, n_sites)
    x, w = rng.normal(size=len(site)), rng.normal(size=len(site))
    y = 2.0 + 0.3 * x + 0.2 * w + np.repeat(u, per) + np.repeat(v, per) * w + rng.normal(0, 0.6, len(site))
    cens = np.where(y < 1.0, -1, 0)
    d = pd.DataFrame({"x": x, "lake": 1.0, "lake_x_wet": w, "site": site, "y": np.maximum(y, 1.0), "cens": cens})
    return d, v


def test_lake_slope_model_recovers_the_slope_spread_and_ranks_the_slopes():
    d, v = _sim()
    fit = m.LakeSlopeRI(cols=["x", "lake_x_wet"]).fit(d, d["y"].to_numpy(), d["cens"].to_numpy(), d["site"].to_numpy())
    assert fit.converged
    assert 0.2 < fit.tau_v < 0.7
    est = fit.slope_means()
    from scipy.stats import spearmanr
    assert spearmanr([est[f"s{i}"] for i in range(len(v))], v).statistic > 0.6
    X = d.iloc[:2].copy()
    p = fit.p_over(X, np.array(["never seen", "never seen"]), 3.0)   # an unseen site uses the prior
    assert np.all((p > 0) & (p < 1))


def test_recalibration_is_near_identity_when_calibrated_and_held_by_its_prior():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.01, 0.3, 4000)
    y = (rng.uniform(size=len(p)) < p).astype(int)
    a, b = m.fit_map(p, y)
    assert abs(b - 1) < 0.15 and abs(a) < 0.3
    a1, b1 = m.fit_map(np.array([0.2, 0.2, 0.2]), np.array([0, 0, 0]))   # three rows: the prior holds the slope near 1
    assert 0.5 < b1 < 1.5 and a1 < 0
    assert np.allclose(m.apply_map(np.array([0.1, 0.5]), None), [0.1, 0.5])


def test_folds_hold_out_what_they_say():
    df = pd.DataFrame([(y, g, 1.0 if g != "River" else 0.0) for y in (2024, 2025, 2026) for g in ("Windermere", "Derwent Water", "River")
                       for _ in range(3)], columns=["year", "catchment", "lake"])
    for name, tr, te in m.folds(df, "cxy"):
        g, y = name.split("|")
        assert not ((df["catchment"][tr] == g) | (df["year"][tr] == int(y))).any()
        assert (df["lake"][te] == 1).all()
    for name, tr, te in m.folds(df, "fwd"):
        assert (df["year"][tr] < int(name)).all() and (df["year"][te] == int(name)).all()
    assert len(list(m.folds(df, "cxy"))) == 6 and len(list(m.folds(df, "loyo"))) == 3


def test_frozen_file_reproduces_the_fitted_models_from_numpy_alone():
    f = json.loads(m.FROZEN.read_text())
    assert f["rule"] == "lake-line-frozen-v1" and f["guardrails_met"] == [] and "not loaded by the site" in f["status"]
    assert len(f["sites"]) == 12 and f["fitted_on"]["rows"] == 1537
    for ck in f["checks"]:
        when = pd.Series(pd.Timestamp(f"{ck['day']} 12:00", tz="Europe/London"), index=range(1))
        bw = None if ck["site"] == "unsampled" else ck["site"]
        got = m.frozen_probs(f, [ck["rain_48h"]], [ck["rain_24h"]], [ck["risk"]], when, bw)
        for k in ("plain_900", "B_900", "A_900", "C_900", "plain_500", "B_500", "A_500", "C_500", "B_median"):
            assert got[k][0] == pytest.approx(ck[k], rel=1e-5), (ck["site"], k)


def test_the_site_does_not_load_the_frozen_file():
    src = "\n".join(p.read_text() for p in (ROOT / "src").rglob("*.py"))
    assert "lake_line_frozen" not in src and "shadow_lake_line" not in src


def test_the_recorded_verdict_and_inputs():
    rec = json.loads(SCORES.read_text())
    assert rec["protocol_commit"] == "3717a7aa" and rec["logged"] == []
    c = rec["checks"]
    assert c["B: B1 log score above plain, interval above zero"] and not c["B: B2 mean within-site rho above plain (point)"]
    assert not any(v for k, v in c.items() if "A1" in k or "A2" in k)
    assert not any(v for k, v in c.items() if "N1" in k)
    for path in (m.ATLAS, *m.PRED.values(), ROOT / "data" / "research" / "ecoli_evidence.v1.json"):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == rec["inputs_sha256"][path.name], path.name
    main = rec["schemes"]["loyo"]["line"]["900"]
    assert main["n"] == 637 and main["events"] == 16 and main["clusters"] == 18
