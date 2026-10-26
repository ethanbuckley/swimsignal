"""scripts/river_rises_eval (docs/RIVER-RISES-SCOPE-2026-10.md, "Evaluation plan"), on synthetic series only: no
network, no EA file, no radar value. Leakage (no reading after t - d can reach an input), the site's word as the
site computes it, the label around the 0.2 threshold, folds by river system, the persistence inputs on a known
hydrograph, a world where the upstream gauge leads the spot by 2 h (the candidate beats persistence and the placebo)
and one where it does not, the gate, the conditions, the near-miss labels and the run statement."""

from __future__ import annotations

import json
import sys
from datetime import UTC
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from river_rises_eval import protocol as pr

from dipcast.ingest import flows

H = pd.Timedelta(hours=1)


def _series(start="2025-09-01", days=6, seed=0, gaps=True) -> pd.Series:
    """A random walk on a 15-minute grid, with missing readings and a few long gaps."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 96, freq="15min", tz="UTC")
    v = 0.5 + np.cumsum(rng.normal(0, 0.03, len(idx)))
    s = pd.Series(v, index=idx)
    if gaps:
        s[rng.random(len(s)) < 0.1] = np.nan
        s.iloc[100:140] = np.nan    # 10 h
        s.iloc[300:303] = np.nan
    return s


def _issues(s: pd.Series, every_h=1) -> pd.DatetimeIndex:
    return pd.date_range(s.index[0].ceil("h") + 30 * H, s.index[-1] - 7 * H, freq=f"{every_h}h")


# ------------------------------------------------------------------ leakage
@pytest.mark.parametrize("delay", [pr.DELAY_H, pr.DELAY_SENS_H])
def test_inputs_at_every_issue_time_equal_inputs_from_the_series_cut_at_t_minus_d(delay):
    """For every issue time t, every input and the site's word computed from the whole series equal those
    computed from the series with everything after t - d removed: no later reading can enter."""
    s = _series()
    issues = _issues(s)
    full = pr.Readings.of(s)
    whole = pd.DataFrame(pr.trend_inputs(full, issues, delay, 0.2, 1.3, pr.UP_RISES_H, "g"))
    view = pr.site_view(full, issues, delay, 0.2, 1.3)
    for i, t in enumerate(issues):
        cut = pr.Readings.of(s[s.index <= t - pd.Timedelta(hours=delay)])
        one = pd.DataFrame(pr.trend_inputs(cut, issues[i:i + 1], delay, 0.2, 1.3, pr.UP_RISES_H, "g"))
        pd.testing.assert_frame_equal(whole.iloc[[i]].reset_index(drop=True), one)
        v1 = pr.site_view(cut, issues[i:i + 1], delay, 0.2, 1.3)
        pd.testing.assert_frame_equal(view.iloc[[i]].reset_index(drop=True), v1)


def test_a_future_reading_changed_to_anything_moves_no_input():
    s = _series(gaps=False)
    t = s.index[0].ceil("h") + 40 * H
    g = pr.Gauge("S", "sys", 0.2, 1.4, s, same=pr.Upstream("U", 0.1, 0.9, s * 1.1))
    base = pr.gauge_rows(g, [t], pr.DELAY_H)
    s2 = s.copy()
    s2[(s2.index > t - H) & (s2.index <= t)] = -5.0   # published too late for t: the inputs may not see it ...
    s2[s2.index > t] = 99.0                            # ... nor anything after t
    moved = pr.gauge_rows(pr.Gauge("S", "sys", 0.2, 1.4, s2, same=pr.Upstream("U", 0.1, 0.9, s2 * 1.1)), [t], pr.DELAY_H)
    inputs = pr.LOGISTIC["C1"] + ["word", "site_rise", "in_P", "in_A"]
    pd.testing.assert_frame_equal(base[inputs], moved[inputs])
    assert moved.at[0, "y3"] == 1   # the label alone looks past t


def test_a_reading_exactly_at_the_cut_counts_and_one_just_after_does_not():
    idx = pd.DatetimeIndex(["2025-09-01T10:00", "2025-09-01T11:00", "2025-09-01T11:15"], tz="UTC")
    r = pr.Readings.of(pd.Series([1.0, 2.0, 3.0], index=idx))
    t = pd.DatetimeIndex(["2025-09-01T12:00"], tz="UTC")
    assert pr.trend_inputs(r, t, 1.0, 0.0, 1.0, (1,), "g")["g_rise1"][0] == pytest.approx(1.0)
    assert np.isnan(pr.Readings.of(pd.Series(dtype=float)).value(pr.ns(t), pr.ns(t))[0])


def test_radar_sums_use_only_whole_hours_ending_by_t_minus_1h():
    hours = pd.date_range("2025-09-01T01:00", periods=48, freq="1h", tz="UTC")   # hour-ending labels
    rain = pd.Series(np.arange(48, dtype=float), index=hours)
    t = pd.DatetimeIndex(["2025-09-01T13:00"], tz="UTC")
    got = pr.rain_inputs(rain, t)
    # hours ending 10:00, 11:00, 12:00 = values 9, 10, 11
    assert got["rain3"][0] == 30 and got["rain12"][0] == sum(range(0, 12))
    later = rain.copy()
    later[later.index > t[0] - H] = 1e6
    assert {k: v[0] for k, v in pr.rain_inputs(later, t).items()} == {k: v[0] for k, v in got.items()}
    gap = rain.drop(pd.Timestamp("2025-09-01T11:00", tz="UTC"))
    g2 = pr.rain_inputs(gap, t)
    assert np.isnan(g2["rain3"][0]) and np.isnan(g2["rain12"][0])
    assert np.isnan(pr.rain_inputs(rain, pd.DatetimeIndex(["2025-09-01T03:00"], tz="UTC"))["rain3"][0])


# ------------------------------------------------------------------ the site's word, as the site computes it
def _site_word_by_flows(s: pd.Series, t: pd.Timestamp, delay_h: float, low: float, high: float):
    """build_site.attach_flow_state on the readings published by t, using the flows functions themselves."""
    pub = s[s.index <= t - pd.Timedelta(hours=delay_h)].dropna()
    if pub.empty or (t - pub.index[-1]) > pd.Timedelta(hours=flows.MAX_READING_AGE_H):
        return "unknown"
    rng = high - low
    index = (pub.iloc[-1] - low) / rng
    rise = None
    if index <= flows.HIGH_INDEX:
        recent = [(ts.isoformat(), float(v)) for ts, v in pub.iloc[-flows.TREND_READINGS:][::-1].items()]
        rise = flows.rise_over_window(recent, t.to_pydatetime())
    return flows.flow_state(index, True, rise["rise_m"] / rng if rise else None) or "none"


@pytest.mark.parametrize("delay", [pr.DELAY_H, pr.DELAY_SENS_H])
def test_site_view_matches_the_sites_own_rule(delay):
    words = set()
    for seed in (1, 2, 3, 4):
        s = _series(seed=seed, days=5) * 3
        issues = _issues(s)
        view = pr.site_view(pr.Readings.of(s), issues, delay, 0.5, 1.6 - 0.5)
        want = [_site_word_by_flows(s, t, delay, 0.5, 1.6) for t in issues]
        assert list(view["word"]) == want
        words |= set(want)
    assert {"high", "rising fast", "none"} <= words


def test_populations_follow_the_word():
    s = _series(seed=4, days=5) * 3
    g = pr.Gauge("S", "sys", 0.5, 2.1, s)
    rows = pr.gauge_rows(g, _issues(s), pr.DELAY_H)
    assert (rows["in_P"] == (rows["word"] == "none")).all()
    assert (rows["in_A"] == (rows["word"] != "unknown")).all()


# ------------------------------------------------------------------ the label
def _step(at: str, jump: float, start="2025-09-01", hours=12):
    idx = pd.date_range(start, periods=hours * 4, freq="15min", tz="UTC")
    return pd.Series(np.where(idx >= pd.Timestamp(at, tz="UTC"), 1.0 + jump, 1.0), index=idx)


def test_label_around_the_threshold():
    t = pd.DatetimeIndex(["2025-09-01T04:00"], tz="UTC")
    rng = 2.0
    lab = lambda s, h=3: pr.labels(pr.Readings.of(s), t, h, rng)[0]  # noqa: E731
    assert lab(_step("2025-09-01T06:00", 0.4)) == 0                  # exactly 0.2 of the range: not more
    assert lab(_step("2025-09-01T06:00", 0.401)) == 1
    assert lab(_step("2025-09-01T07:00", 0.9)) == 1                  # at t + 3 h exactly: inside (t, t + 3 h]
    assert lab(_step("2025-09-01T07:15", 0.9)) == 0                  # just after the horizon ...
    assert lab(_step("2025-09-01T07:15", 0.9), h=6) == 1             # ... inside 6 h
    assert lab(_step("2025-09-01T04:00", 0.9)) == 0                  # a reading at t is "now", not ahead
    gone = _step("2025-09-01T06:00", 0.9)
    gone[gone.index > t[0]] = np.nan
    assert np.isnan(lab(gone))                                       # no reading ahead
    old = _step("2025-09-01T06:00", 0.9)
    old[(old.index > t[0] - pd.Timedelta(hours=2)) & (old.index <= t[0])] = np.nan
    assert np.isnan(lab(old))                                        # "now" over LABEL_NOW_MAX_H old


def test_periods_keep_the_label_window_inside():
    t = pd.DatetimeIndex(["2025-09-30T20:00", "2025-09-30T21:00", "2025-09-30T22:00", "2025-10-01T00:00",
                          "2026-10-24T21:00", "2026-10-24T22:00", "2024-11-20T23:00"], tz="UTC")
    assert list(pr.period(t, 3)) == ["train", "train", "", "test", "test", "", ""]
    assert list(pr.period(t, 6)) == ["", "", "", "test", "", "", ""]
    assert len(pr.issue_grid()) == (pr.TEST[1] - pr.TRAIN[0]) / H and (pr.issue_grid().minute == 0).all()


# ------------------------------------------------------------------ river systems and folds
def test_folds_keep_a_river_system_in_one_fold():
    systems = [f"outlet{i}" for i in range(13)]
    f1, f2 = pr.system_folds(systems), pr.system_folds(list(reversed(systems)) + systems)
    assert f1 == f2 and set(f1.values()) == set(range(pr.N_FOLDS))
    assert max(np.bincount(list(f1.values()))) - min(np.bincount(list(f1.values()))) <= 1
    gauges = [pr.Gauge(f"G{i}", systems[i % 13], 0, 1, _series(seed=i, days=2, gaps=False)) for i in range(26)]
    rows = pr.build_rows(gauges, pd.date_range("2025-09-01T12:00", periods=12, freq="1h", tz="UTC"), 1.0, f1)
    assert (rows.groupby("system")["fold"].nunique() == 1).all()


def test_cross_fold_trains_on_other_systems_in_the_training_period_only(monkeypatch):
    seen = []

    def spy(Xtr, ytr, Xte, cols):
        seen.append((set(Xtr["system"]), set(Xtr["period3"]), set(Xte["system"]), set(Xte["period3"])))
        return np.full(len(Xte), 0.5)
    monkeypatch.setattr(pr, "fit_predict", spy)
    rows = _world(lead_h=2.0, n=10)[1]
    p = pr.cross_fold(rows, pr.LOGISTIC["C1"], "y3", "period3", "in_P")
    assert len(seen) == pr.N_FOLDS
    for tr_sys, tr_per, te_sys, te_per in seen:
        assert not tr_sys & te_sys and tr_per == {"train"} and te_per == {"test"}
    te = (rows["period3"] == "test") & rows["in_P"]
    assert np.isfinite(p[te.to_numpy()]).all() and np.isnan(p[~te.to_numpy()]).all()


def test_outlet_follows_the_network_down():
    import networkx as nx
    g = nx.DiGraph([("a", "b"), ("b", "c"), ("t", "b"), ("c", "sea"), ("x", "y"), ("c", "side")])
    up = {"sea": 10.0, "side": 2.0}
    assert pr.outlet(g, "a", up) == "sea" and pr.outlet(g, "t", up) == "sea" and pr.outlet(g, "x", up) == "y"
    loop = nx.DiGraph([("p", "q"), ("q", "p")])
    assert pr.outlet(loop, "q") == "p"


# ------------------------------------------------------------------ persistence on a known hydrograph
def test_persistence_inputs_on_a_ramp():
    idx = pd.date_range("2025-09-01", periods=96, freq="15min", tz="UTC")
    hours = (idx - idx[0]) / H
    s = pd.Series(0.1 + 0.05 * hours, index=idx)       # 0.05 m an hour
    g = pr.Gauge("S", "sys", 0.0, 2.0, s)
    t = pd.Timestamp("2025-09-01T12:00", tz="UTC")
    r = pr.gauge_rows(g, [t], pr.DELAY_H).iloc[0]
    assert r["spot_index"] == pytest.approx((0.1 + 0.05 * 11) / 2.0)   # the reading at t - 1 h
    assert r["spot_rise1"] == pytest.approx(0.05 / 2.0) and r["spot_rise3"] == pytest.approx(0.15 / 2.0)
    assert r["spot_missing"] == 0 and r["same_missing"] == 1 and r["same_rise1"] == 0
    assert pr.LOGISTIC["R3"] == pr.SPOT_COLS and set(pr.SPOT_COLS) < set(pr.LOGISTIC["C1"]) < set(pr.LOGISTIC["C2"])
    s3 = pr.gauge_rows(g, [t], pr.DELAY_SENS_H).iloc[0]
    assert s3["spot_index"] == pytest.approx((0.1 + 0.05 * 9) / 2.0)


# ------------------------------------------------------------------ synthetic worlds
def _pulse(x: np.ndarray, height=0.8, rise_h=4.0, decay_h=8.0) -> np.ndarray:
    return np.where(x < 0, 0.0, np.where(x < rise_h, height * x / rise_h, height * np.exp(-(x - rise_h) / decay_h)))


def _world(lead_h: float | None, n=10, seed=7, events=26):
    """n spot gauges, each its own river system, with a same-river upstream gauge. With lead_h the spot gets the
    upstream gauge's pulses lead_h later; with None its pulses are independent of the upstream gauge's."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-08-20", "2025-11-10", freq="15min", tz="UTC", inclusive="left")
    hrs = ((idx - idx[0]) / H).to_numpy()
    gauges = []
    for i in range(n):
        up_ev = np.sort(rng.uniform(24, hrs[-1] - 24, events))
        sp_ev = up_ev + lead_h if lead_h is not None else np.sort(rng.uniform(24, hrs[-1] - 24, events))
        up = 0.3 + sum(_pulse(hrs - e) for e in up_ev) + rng.normal(0, 0.002, len(hrs))
        sp = 0.3 + sum(_pulse(hrs - e) for e in sp_ev) + rng.normal(0, 0.002, len(hrs))
        gauges.append(pr.Gauge(f"G{i}", f"S{i}", 0.0, 1.0, pd.Series(sp, index=idx),
                               same=pr.Upstream(f"U{i}", 0.0, 1.0, pd.Series(up, index=idx))))
    folds = pr.system_folds(g.system for g in gauges)
    issues = pd.date_range("2025-08-21", "2025-11-09", freq="1h", tz="UTC", inclusive="left")
    return gauges, pr.build_rows(gauges, issues, pr.DELAY_H, folds), folds, issues


def _score(rows):
    p3 = pr.cross_fold(rows, pr.LOGISTIC["R3"], "y3", "period3", "in_P")
    p1 = pr.cross_fold(rows, pr.LOGISTIC["C1"], "y3", "period3", "in_P")
    te = np.isfinite(p1)
    return rows[te].assign(R3=p3[te], C1=p1[te])


def test_upstream_two_hours_ahead_beats_persistence():
    gauges, rows, folds, issues = _world(lead_h=2.0)
    m = _score(rows)
    y = m["y3"].to_numpy(dtype=float)
    assert np.nansum(y) >= 50
    b = pr.cluster_skill(y, m["C1"], m["R3"], m["system"], n=300)
    assert b["d"] >= pr.SKILL_MIN and b["L"] > 0
    assert pr.auc(m["C1"], y) > pr.auc(m["R3"], y)
    # lead gained: the candidate's warning starts before the site's own "rising fast"
    full = rows[["gauge", "system", "issue", "word"]].merge(m[["gauge", "issue", "C1"]], on=["gauge", "issue"], how="left")
    leads = pr.lead_gained(full, "C1")
    assert len(leads) >= 50 and leads["caught"].mean() > 0.5 and leads.loc[leads["caught"], "lead_h"].median() >= 1
    # the placebo: the same upstream series moved by whole weeks loses the gain
    real = pr.brier(m["R3"], y) - pr.brier(m["C1"], y)
    refs = sorted(g.same.ref for g in gauges)
    gains = []
    for shift in pr.placebo_shifts(refs, n=8):
        r = pr.build_rows(gauges, issues, pr.DELAY_H, folds, shifts=shift)
        p = pr.cross_fold(r, pr.LOGISTIC["C1"], "y3", "period3", "in_P")
        ok = np.isfinite(p)
        mm = r[ok].assign(p=p[ok]).merge(m[["gauge", "issue", "R3"]], on=["gauge", "issue"])
        yy = mm["y3"].to_numpy(dtype=float)
        gains.append(pr.brier(mm["R3"], yy) - pr.brier(mm["p"], yy))
    pl = pr.placebo_holds(real, gains)
    assert pl["holds"] and max(gains) < real / 2


def test_upstream_unrelated_to_the_spot_does_not_beat_persistence():
    _, rows, _, _ = _world(lead_h=None)
    m = _score(rows)
    y = m["y3"].to_numpy(dtype=float)
    b = pr.cluster_skill(y, m["C1"], m["R3"], m["system"], n=300)
    assert b["d"] < 0.02 and not (b["d"] >= pr.SKILL_MIN and b["L"] > 0)


def test_placebo_shifts_and_roll():
    a, b = pr.placebo_shifts(["U2", "U1"], n=50), pr.placebo_shifts(["U1", "U2"], n=50)
    assert a == b and len(a) == 50
    w = [v for d in a for v in d.values()]
    assert set(map(abs, w)) <= set(pr.PLACEBO_WEEKS) and min(w) < 0 < max(w)
    s = _series(days=30, gaps=True)
    r = pr.roll_weeks(s, -2)
    assert r.isna().sum() == s.isna().sum() and r.index.equals(s.index)
    assert r.iloc[0] == s.iloc[2 * 7 * 96] or (np.isnan(r.iloc[0]) and np.isnan(s.iloc[2 * 7 * 96]))
    with pytest.raises(pr.StopRule):
        pr.roll_weeks(s.drop(s.index[5]), 1)


# ------------------------------------------------------------------ gate, conditions, labels, statement
def _gate_rows(n_ep: int, n_gauges: int, n_systems: int, labelled=1.0):
    rows = []
    for e in range(n_ep):
        g = e % n_gauges
        t0 = pd.Timestamp("2025-10-02", tz="UTC") + pd.Timedelta(hours=10 * (e // n_gauges))
        for k, y in enumerate([1, 1, 0]):           # one episode of two hours, then a 0
            rows.append({"gauge": f"G{g}", "system": f"S{g % n_systems}", "issue": t0 + k * H, "y3": float(y),
                         "in_P": True, "period3": "test"})
    df = pd.DataFrame(rows)
    tr = df.assign(period3="train", issue=df["issue"] - pd.Timedelta(days=60))
    df = pd.concat([df, tr], ignore_index=True)
    if labelled < 1:
        df.loc[df.index[: int(len(df) * (1 - labelled)) + 1], "y3"] = np.nan
    return df


def test_gate():
    ok = pr.gate(_gate_rows(150, 15, 6), 25)
    assert ok["judged"] and ok["episodes"] == 150 and ok["gauges_with_episode"] == 15 and ok["systems_with_episode"] == 6
    assert not pr.gate(_gate_rows(149, 15, 6), 25)["judged"]
    assert not pr.gate(_gate_rows(150, 14, 6), 25)["judged"]
    assert not pr.gate(_gate_rows(150, 15, 5), 25)["judged"]
    assert not pr.gate(_gate_rows(150, 15, 6), 24)["judged"]
    assert not pr.gate(_gate_rows(150, 15, 6, labelled=0.7), 25)["judged"]
    out = _gate_rows(150, 15, 6)
    out.loc[out.index[:2], "in_P"] = False            # an episode at hours outside P does not count
    assert pr.gate(out, 25)["episodes"] == 149


def test_conditions_and_verdict():
    rng = np.random.default_rng(3)
    systems = np.repeat([f"S{i}" for i in range(6)], 200)
    y = (rng.random(len(systems)) < 0.2).astype(float)
    good = np.clip(y * 0.8 + 0.1, 0, 1)
    ref = np.full(len(y), 0.2)
    leads = pd.DataFrame({"lead_h": [2.0, 1.0, 0.0, 3.0], "caught": [True, True, False, True]})
    eps = {f"S{i}": 6 for i in range(6)}
    c = pr.conditions(y, good, ref, systems, eps, leads, 0.3, pr.placebo_holds(0.1, np.linspace(-0.01, 0.01, 200)))
    assert all(v["holds"] for v in c.values()) and pr.verdict(True, c) == "Passes"
    assert pr.verdict(False, c).startswith("Too few")
    bad = pr.conditions(y, ref, good, systems, eps, leads.assign(caught=False), -0.1, pr.placebo_holds(0.0, [0.01] * 200))
    assert not any(v["holds"] for k, v in bad.items() if k != "3") and pr.verdict(True, bad) == "Fails"
    assert pr.systems_needed(6) == 4 and pr.systems_needed(5) == 4 and pr.systems_needed(0) == 0
    hf = pr.hit_far([0.5, 0.9, 0.1, 0.6], [1, 0, 1, 0])
    assert hf["hit_rate"] == 0.5 and hf["false_alarm_ratio"] == pytest.approx(2 / 3)


def test_cluster_skill_resamples_systems():
    y = np.array([1, 0, 1, 0, 1, 0], dtype=float)
    p = np.array([0.9, 0.1, 0.9, 0.1, 0.5, 0.5])
    ref = np.full(6, 0.5)
    b = pr.cluster_skill(y, p, ref, ["a", "a", "b", "b", "c", "c"], n=500)
    assert b["d"] == pytest.approx(1 - (4 * 0.01 + 2 * 0.25) / 1.5) and b["clusters"] == 3
    assert b["L"] <= b["d"] <= b["U"] and b["U"] <= 1 - 0.04 / 1.0 + 1e-12


def test_lead_gained_counts_hours_the_forecast_stayed_up():
    t = pd.date_range("2025-10-05", periods=12, freq="1h", tz="UTC")
    word = ["none"] * 8 + ["rising fast"] * 2 + ["none"] * 2
    p = [0.1, 0.1, 0.6, 0.2, 0.6, 0.7, 0.8, 0.9, np.nan, np.nan, 0.1, 0.1]
    rows = pd.DataFrame({"gauge": "G", "system": "S", "issue": t, "word": word, "C1": p})
    got = pr.lead_gained(rows, "C1")
    assert len(got) == 1 and got.at[0, "lead_h"] == 4.0 and got.at[0, "caught"]
    rows.loc[7, "C1"] = 0.4
    assert pr.lead_gained(rows, "C1").at[0, "lead_h"] == 0.0
    early = rows.assign(issue=t - pd.Timedelta(days=5))     # look-back before the test period: not counted
    assert pr.lead_gained(early, "C1").empty


@pytest.mark.parametrize("d,L,U,want", [
    (0.06, 0.01, 0.1, "Better"),
    (0.02, -0.005, 0.05, "Promising, not shown"),
    (-0.002, -0.008, 0.03, "No useful difference"),
    (-0.01, -0.03, 0.01, "Possible harm"),
    (-0.02, -0.03, -0.001, "Possible harm"),
    (0.01, -0.03, 0.06, "Too uncertain"),
])
def test_near_miss_labels(d, L, U, want):
    assert pr.nearmiss_label(d, L, U, B=0.05, H=0.01) == want


def test_near_miss_order_and_secondary_harm():
    assert pr.nearmiss_label(0.002, 0.001, 0.004, B=0.05, H=0.0) == "No useful difference"
    # In the addendum's order "Harm" (U < 0) is never reached: L > -H gives "No useful difference" first, and
    # L <= -H with d <= U < 0 gives "Possible harm" first. Asked of Ethan; the harness keeps the order as written.
    assert pr.nearmiss_label(-0.005, -0.008, -0.001, B=0.05, H=0.01) == "No useful difference"
    assert pr.nearmiss_label(-0.02, -0.03, -0.01, B=0.05, H=0.01) == "Possible harm"
    assert pr.nearmiss_label(0.02, -0.005, 0.04, B=0.05, H=0.01, secondary_harm=True) == "No useful difference"
    assert pr.SECONDARY_HARM == {"Harm", "Possible harm"}


def test_statement_must_name_the_predictions_and_sane_margins(tmp_path):
    pred = tmp_path / "predictions.parquet"
    pred.write_bytes(b"predictions")
    sha = pr.sha256(pred)
    st = tmp_path / "statement.json"
    good = {"predictions_sha256": sha, "working": "from the predictions alone: ...",
            "margins": {"C1": {"B": 0.02, "H": 0.01}, "C2": {"B": 0.02, "H": 0.02}}}
    st.write_text(json.dumps(good))
    assert pr.read_statement(st, sha)["margins"]["C1"]["B"] == 0.02
    with pytest.raises(pr.StopRule, match="no run statement"):
        pr.read_statement(tmp_path / "none.json", sha)
    for bad in ({**good, "predictions_sha256": "0" * 64}, {**good, "working": ""},
                {**good, "margins": {"C1": {"B": 0.01, "H": 0.02}, "C2": good["margins"]["C2"]}},
                {**good, "margins": {"C1": good["margins"]["C1"]}}):
        st.write_text(json.dumps(bad))
        with pytest.raises(pr.StopRule):
            pr.read_statement(st, sha)


def test_the_plans_numbers_are_the_sites_and_the_plans():
    assert pr.SHARE == flows.RISING_SHARE == 0.2 and pr.HIGH_INDEX == flows.HIGH_INDEX == 1.0
    assert pr.SITE_RISE_H == 6.0 and pr.MAX_AGE_H == 24.0
    assert (pr.PRIMARY_H, pr.HORIZONS_H, pr.DELAY_H, pr.DELAY_SENS_H, pr.RADAR_DELAY_H) == (3, (3, 6), 1.0, 3.0, 1.0)
    assert (pr.N_FOLDS, pr.SEED, pr.N_BOOT, pr.N_PLACEBO, pr.C) == (5, 20261026, 2000, 200, 1.0)
    assert (pr.GATE_PAIRED_GAUGES, pr.GATE_LABELLED, pr.GATE_EPISODES, pr.GATE_EP_GAUGES, pr.GATE_EP_SYSTEMS) == (25, 0.8, 150, 15, 6)
    assert (pr.SKILL_MIN, pr.SYSTEM_EPISODES, pr.LINE, pr.HIT_MIN, pr.FAR_MAX, pr.LEAD_MIN_H, pr.LEAD_LOOK_H) == (0.05, 5, 0.5, 0.5, 0.5, 1.0, 6)
    assert pr.TRAIN[0].tz == UTC or str(pr.TRAIN[0].tz) == "UTC"
    assert pr.NOT_BEFORE == pd.Timestamp("2026-11-02", tz="UTC")


# ------------------------------------------------------------------ the fetch's choice of upstream gauge (mocked)
def test_fetch_chooses_the_first_candidate_with_a_series_and_a_range(tmp_path):
    import httpx
    import river_rises_coverage as rr
    from river_rises_eval import fetch as rf
    asked = []

    def handler(req):
        asked.append(req.url.path)
        if req.url.path.endswith("/C/stageScale"):
            return httpx.Response(200, json={"items": {"typicalRangeLow": 0.2, "typicalRangeHigh": 1.0}})
        return httpx.Response(404)
    http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    client = rr.CappedClient(tmp_path / "cache", fetch=True, http=http, sleep=lambda s: None)
    fm = {r: {"stationReference": r, "lat": 54.0, "long": -2.0,
              "stageScale": f"{rr.FM}/id/stations/{r}/stageScale"} for r in "ABC"}
    hindex = rr.hydrology_index([{"stationReference": r, "measures": [{"@id": f"x/{r}-level-i-900-m-qualified"}]}
                                 for r in "BC"])
    cands = pd.DataFrame({"up": list("ABC"), "up_label": list("ABC"), "up_river": "R", "along_km": [4.0, 5.0, 6.0],
                          "area_ratio": [0.5, 0.5, 0.5]})
    got = rf.choose(cands, client, fm, hindex)
    assert got["up"] == "C" and (got["low"], got["high"]) == (0.2, 1.0) and got["measure"] == "C-level-i-900-m-qualified"
    assert asked == ["/flood-monitoring/id/stations/B/stageScale", "/flood-monitoring/id/stations/C/stageScale"]
    assert rf.choose(cands[cands["up"] == "A"], client, fm, hindex) is None and len(asked) == 2


# ------------------------------------------------------------------ the two stages, end to end on a synthetic fetch
def _fake_fetch(tmp_path: Path, gauges: list[pr.Gauge]) -> tuple[Path, Path]:
    data, radar = tmp_path / "data", tmp_path / "radar"
    (data / "series").mkdir(parents=True)
    radar.mkdir()
    rows, slots, cells = [], [], []
    rng = np.random.default_rng(0)
    hours = pd.date_range("2025-08-20T01:00", "2025-11-10", freq="1h", tz="UTC")
    for i, g in enumerate(gauges):
        u = g.same
        for ref, s in ((g.ref, g.series), (u.ref, u.series)):
            s.rename("value").rename_axis("time").reset_index().to_parquet(data / "series" / f"m{ref}.parquet")
        rows.append({"gauge": g.ref, "label": g.ref, "river": "R", "lat": 54.0, "lon": -2.0, "low": g.low, "high": g.high,
                     "measure": f"m{g.ref}", "system": g.system, "spots": "x", "paired": True, "why": ""})
        slots.append({"gauge": g.ref, "slot": "same", "up": u.ref, "low": u.low, "high": u.high, "measure": f"m{u.ref}"})
        cell = f"5{i}.000_-2.000"
        cells.append({"gauge": g.ref, "cell": cell, "cell_lat": 50 + i, "cell_lon": -2.0, "saved_months": 1})
        pd.DataFrame({"time": hours, "radar_mm": rng.gamma(0.3, 1.0, len(hours))}).to_parquet(radar / f"radar_{cell}_2025-08.parquet")
    pd.DataFrame(rows).to_csv(data / "gauges.csv", index=False)
    pd.DataFrame(slots).to_csv(data / "slots.csv", index=False)
    pd.DataFrame(cells).to_csv(data / "radar_cells.csv", index=False)
    return data, radar


def test_predict_then_score_end_to_end(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from river_rises_eval import score as sc
    monkeypatch.setattr(pr, "N_PLACEBO", 3)
    gauges = _world(lead_h=2.0, n=6)[0]
    data, radar = _fake_fetch(tmp_path, gauges)
    args = SimpleNamespace(data=data, out=tmp_path / "run", radar=radar, statement=None)
    summary = sc.stage_predict(args)
    pred = pd.read_parquet(args.out / "predictions.parquet")
    assert not [c for c in pred.columns if c.startswith("y")]           # no outcome in the predictions file
    assert set(pred["config"]) == set(sc.CONFIGS) and pred["C2"].notna().any() and pred["R2"].notna().any()
    assert not summary["gate"]["judged"] and summary["gate"]["paired_gauges"] == 6   # under 25: description only
    with pytest.raises(pr.StopRule):
        sc.stage_score(args)                                             # no statement yet
    st = tmp_path / "statement.json"
    st.write_text(json.dumps({"predictions_sha256": summary["predictions_sha256"], "working": "synthetic",
                              "margins": {"C1": {"B": 0.02, "H": 0.01}, "C2": {"B": 0.02, "H": 0.01}}}))
    args.statement = st
    res = sc.stage_score(args)
    assert res["judged"]["C1"]["verdict"].startswith("Too few") and res["judged"]["C2"]["against"] == "C1"
    assert res["judged"]["C1"]["conditions"]["1"]["d"] > pr.SKILL_MIN
    assert res["judged"]["C1"]["conditions"]["6"]["draws"] == 3
    report = (args.out / "report.md").read_text()
    assert "## Gate" in report and "description only" in report and "C1 against R3" in report
