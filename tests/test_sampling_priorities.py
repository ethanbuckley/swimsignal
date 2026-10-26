"""The sampling-priorities prototype: deterministic, prefers what the model does not know, keeps the high-risk list
apart, respects the budget, and never touches the network."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dipcast import sampling_priorities as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network attempt")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(scope="module")
def fitted():
    w = sp.synthetic_world(3)
    hist = sp.history_rows(w, 3)
    names = w.sites["site"].tolist()
    a = sp.fit_ensemble(hist, hist.y, hist.site, sp.COLS_A, "A", names, n_boot=8, seed=0)
    b = sp.fit_ensemble(hist, hist.y, hist.site, sp.COLS_B, "B", names, n_boot=8, seed=0)
    # In this world the fitted spread of site levels is well above zero (in some worlds it fits to the grid's floor,
    # and then a never-sampled site looks like any other).
    assert a.tau >= 0.5 and b.tau >= 0.5
    week = w.days[(w.days.season == 2) & (w.days.week == 3) & (w.days.dow < sp.WEEKDAYS)]
    cand = sp.forecast_view(week, np.random.default_rng(3)).reset_index(drop=True)
    return w, hist, a, b, cand


def test_deterministic(fitted):
    w, hist, a, b, cand = fitted
    names = w.sites["site"].tolist()
    a2 = sp.fit_ensemble(hist, hist.y, hist.site, sp.COLS_A, "A", names, n_boot=8, seed=0)
    b2 = sp.fit_ensemble(hist, hist.y, hist.site, sp.COLS_B, "B", names, n_boot=8, seed=0)
    s1, s2 = sp.score_candidates(cand, a, b), sp.score_candidates(cand, a2, b2)
    assert np.array_equal(s1.info_bits.to_numpy(), s2.info_bits.to_numpy())
    p1, _ = sp.plan(cand, a, b, budget=5)
    p2, _ = sp.plan(cand, a2, b2, budget=5)
    assert list(p1.index) == list(p2.index)
    w2 = sp.synthetic_world(3)
    pd.testing.assert_frame_equal(w.days, w2.days)


def test_prefers_unsampled_site_in_a_constructed_case(fitted):
    """Two river sites on identical wet days: the sampled river whose offset is nearest 0, and a river never sampled
    (offset 0, variance tau^2). The unsampled one scores higher on every day, and the first pick is there."""
    w, hist, a, b, cand = fitted
    rivers = hist.loc[hist.kind == "river", "site"].unique()
    sampled = min(rivers, key=lambda s: abs(a.u_mean[a.sites.index(s)]) + abs(b.u_mean[b.sites.index(s)]))
    unsampled = w.sites.loc[(w.sites.kind == "river") & ~w.sites.sampled, "site"].iloc[0]
    lr = np.log1p(np.array([8.0, 15.0, 25.0]))
    one = pd.DataFrame({"site": sampled, "day": [0, 1, 2], "rain_48h": [8.0, 15.0, 25.0], "lrain48": lr,
                        "logit_risk": -3.0 + (lr - 1.0), "lake": 0.0, "lake_x_lrain48": 0.0, "sm": 0.0})
    pair = pd.concat([one, one.assign(site=unsampled)], ignore_index=True)
    s = sp.score_candidates(pair, a, b)
    assert (s.loc[s.site == unsampled, "info_bits"].to_numpy() > s.loc[s.site == sampled, "info_bits"].to_numpy()).all()
    picks, _ = sp.plan(pair, a, b, budget=1)
    assert picks.site.iloc[0] == unsampled
    assert sp.reason(picks.iloc[0]).startswith("never sampled")


def test_prefers_high_variance_site(fitted):
    """Two sampled sites made alike (same days, offset mean 0) but for the offset's variance: the site whose level
    is less certain scores higher on every day."""
    w, hist, a, b, cand = fitted
    s1, s2 = hist.loc[hist.kind == "river", "site"].unique()[:2]
    one = cand[cand.site == s1].copy()
    pair = pd.concat([one, one.assign(site=s2)], ignore_index=True)
    state = {}
    for key, ens in (("a", a), ("b", b)):
        um, uv = (x.copy() for x in ens.offsets())
        i1, i2 = ens.sites.index(s1), ens.sites.index(s2)
        um[[i1, i2]] = 0.0
        uv[i1], uv[i2] = 0.05, 0.5
        state[key] = (um, uv)
    s = sp.score_candidates(pair, a, b, state=state)
    assert (s.loc[s.site == s2, "info_bits"].to_numpy() > s.loc[s.site == s1, "info_bits"].to_numpy()).all()


def test_greedy_spreads_after_a_pick(fitted):
    """After a pick, the same site's information falls (its offset variance shrinks), and nothing else changes."""
    w, hist, a, b, cand = fitted
    picks, state = sp.plan(cand, a, b, budget=1)
    after = sp.score_candidates(cand, a, b, state=state)
    before = sp.score_candidates(cand, a, b)
    same = cand.site == picks.site.iloc[0]
    assert (after.info_bits[same] < before.info_bits[same]).all()
    assert np.allclose(after.info_bits[~same], before.info_bits[~same])


def test_high_risk_list_is_distinct(fitted):
    w, hist, a, b, cand = fitted
    picks, _ = sp.plan(cand, a, b, budget=10)
    risk = sp.high_risk(cand, a, b, min_p=0.0, top=10)
    assert list(risk.p_mean) == sorted(risk.p_mean, reverse=True)
    assert set(zip(picks.site, picks.day)) != set(zip(risk.site, risk.day))
    # the highest-risk day is not the most informative one: near-certain days teach little
    s = sp.score_candidates(cand, a, b)
    assert s.p_mean.idxmax() != s.info_bits.idxmax()
    assert all(r.startswith("chance over the line") for r in risk.reason)


def test_budget_and_limits(fitted):
    w, hist, a, b, cand = fitted
    for budget, per_day in ((3, 2), (7, 2), (12, 3)):
        picks, _ = sp.plan(cand, a, b, budget=budget, per_day=per_day)
        assert len(picks) == budget
        assert picks.groupby("day").size().max() <= per_day
        assert not picks.duplicated(["site", "day"]).any()
    # a budget larger than the limits allow stops at what they allow
    picks, _ = sp.plan(cand, a, b, budget=50, per_day=1)
    assert len(picks) == cand.day.nunique()


def test_simulation_limits_and_one_replication():
    import sampling_priorities_sim as sim
    rows = pd.DataFrame({"site": ["a", "a", "b", "c", "d"], "day": [0, 1, 0, 0, 0]})
    assert sim.take(rows, rows.index, 5) == [0, 1, 2]      # at most 2 on day 0
    out = sim.run_rep(9001, tau=0.7, per_week=1)
    for s in sim.STRATEGIES:
        assert out[s]["n"] == sim.WEEKS
    assert out["RISK"]["expected_exceedances"] >= out["RANDOM"]["expected_exceedances"]
    assert sim.run_rep(9001, tau=0.7, per_week=1) == out
