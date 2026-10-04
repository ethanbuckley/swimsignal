"""scripts/hindcast_wales.py (Wales plan, task W4) on small made-up fixtures: the joins, the scores
and their bootstrap, the site and label rules, the yearly totals and Gate A's verdict."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import hindcast_wales as hw


class StubModel:
    """predict_pooled = a logistic of the day's rain, shifted by the overflow's log long-term
    average, so the arms can be told apart."""

    trained_on = "stub"

    def predict_pooled(self, df):
        z = 0.4 * (df["rain_d"].to_numpy() - 8) + (df["log_lta_spills"].to_numpy() - np.log1p(20))
        return np.clip(1 / (1 + np.exp(-z)), 1e-4, 1 - 1e-4)


def _hourly(cells, start="2024-12-01", end="2025-12-31 23:00", seed=0):
    rng = np.random.default_rng(seed)
    t = pd.date_range(start, end, freq="h", tz="UTC")
    frames = []
    for cl, cn in cells:
        wet_day = rng.random(len(t) // 24 + 1) < 0.3
        p = np.where(np.repeat(wet_day, 24)[: len(t)], rng.gamma(1.0, 1.0, len(t)), 0.0)
        frames.append(pd.DataFrame({"cell_lat": cl, "cell_lon": cn, "time": t, "precip_mm": p}))
    return pd.concat(frames, ignore_index=True)


def _sites(year=2025):
    return pd.DataFrame({
        "site_id": ["A", "B", "C", "D"], "year": year,
        "lat": [52.50, 52.51, 52.80, 52.81], "lon": [-3.30, -3.31, -3.10, -3.11],
        "company": "Test", "lta_spills": [40.0, 10.0, 30.0, 5.0], "spill_hours": [300.0, 50.0, 200.0, 20.0],
        "edm_operational_pct": [99.0, 95.0, 98.0, 97.0], "prev_spills": [40.0, 10.0, np.nan, 0.0],
        "spills": [35.0, 8.0, 0.0, 3.0], "same_year_uptime": [99.0, 95.0, 98.0, 30.0]})


def _events(daily, sites, model, seed=1):
    """Discharges drawn from the stub model's own probabilities, at site A and B only, under other ids
    and a few metres away (so they join by position)."""
    rng = np.random.default_rng(seed)
    days = pd.date_range("2025-01-01", "2025-12-31", freq="D", tz="UTC")
    sd = hw.build_site_days(sites[sites.site_id.isin(["A", "B"])], daily, days)
    sd = sd[sd["rain_d"].notna()]
    p = model.predict_pooled(hw.features(sd))
    hit = sd[rng.random(len(sd)) < p]
    off = {"A": ("hdA", 52.5003, -3.3002), "B": ("hdB", 52.5101, -3.3103)}
    return pd.DataFrame({
        "site_id": [off[s][0] for s in hit.site_id], "lat": [off[s][1] for s in hit.site_id],
        "lon": [off[s][2] for s in hit.site_id], "event_start": hit["day"] + pd.Timedelta(hours=6),
        "event_end": hit["day"] + pd.Timedelta(hours=8)})


# ---------------------------------------------------------------------------- joins

def test_match_by_position_nearest_first_one_to_one_and_cutoff():
    a = pd.DataFrame({"site_id": ["x", "y", "z"], "lat": [52.5, 52.5005, 53.0], "lon": [-3.3, -3.3, -3.0]})
    b = pd.DataFrame({"site_id": ["P", "Q"], "lat": [52.5004, 52.5100], "lon": [-3.3, -3.3]})
    m = hw.match_by_position(a, b, max_m=200).set_index("a_id")
    # y is about 11 m from P, x about 44 m: y takes P; x has no other row within 200 m (Q is ~1.1 km).
    assert m.loc["y", "b_id"] == "P"
    assert "x" not in m.index and "z" not in m.index
    assert m.loc["y", "dist_m"] < 20


def test_link_events_by_id_then_position_and_counts_unjoined():
    ov = pd.DataFrame({"site_id": ["E1", "E2"], "lat": [52.0, 52.2], "lon": [-2.7, -2.7]})
    ev = pd.DataFrame({"site_id": ["E1", "other", "far"], "lat": [52.0, 52.2001, 54.0], "lon": [-2.7, -2.7, -2.0],
                       "event_start": pd.to_datetime(["2025-01-02"] * 3, utc=True), "event_end": pd.NaT})
    out, info = hw.link_events(ev, ov)
    assert sorted(out.site_id) == ["E1", "E2"]
    assert info["joined_by_id"] == 1 and info["joined_by_position"] == 1 and info["unjoined_sites"] == 1


# ---------------------------------------------------------------------------- scores

def test_weighted_auc_matches_sklearn_with_ties_and_weights():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, 400)
    p = np.round(rng.random(400), 1)          # many ties
    w = rng.integers(0, 4, 400).astype(float)
    assert hw.weighted_auc(y, p) == pytest.approx(roc_auc_score(y, p))
    assert hw.weighted_auc(y, p, w) == pytest.approx(roc_auc_score(y, p, sample_weight=w))


def test_year_before_rate_converts_counts_clips_and_fills_with_median():
    r = hw.year_before_rate(pd.Series([36.5, 0.0, np.nan, 1000.0]), 1.0)
    assert r.iloc[0] == pytest.approx(0.1)
    assert r.iloc[1] == hw.BASE_CLIP[0]
    assert r.iloc[3] == hw.BASE_CLIP[1]
    assert r.iloc[2] == pytest.approx(min(np.median([36.5, 0.0, 1000.0]) / 365, 0.95))


def test_scorer_point_values_and_interval_cover_them():
    rng = np.random.default_rng(0)
    days = pd.date_range("2025-01-01", periods=200, freq="D", tz="UTC")
    df = pd.DataFrame({"site_id": np.repeat(list("abcdefghij"), len(days)), "day": np.tile(days, 10)})
    p = rng.random(len(df)) * 0.6
    df["y"] = (rng.random(len(df)) < p).astype(int)
    ref = np.full(len(df), df["y"].mean())
    s = hw.Scorer(df, n_boot=300).summary(p, {"flat": ref})
    brier = np.mean((p - df.y) ** 2)
    assert s["brier"] == pytest.approx(brier)
    assert s["bss_vs_flat"] == pytest.approx(1 - brier / np.mean((ref - df.y) ** 2))
    assert s["bss_vs_flat"] > 0                   # p carries the signal
    lo, hi = s["bss_vs_flat_ci"]
    assert lo < s["bss_vs_flat"] < hi
    assert s["auc_ci"][0] < s["auc"] < s["auc_ci"][1]


def test_boot_draws_resample_each_cluster_set_to_its_size():
    a, b = hw.boot_draws(7, 30, n_boot=50)
    assert a.shape == (50, 7) and b.shape == (50, 30)
    assert (a.sum(axis=1) == 7).all() and (b.sum(axis=1) == 30).all()


# ---------------------------------------------------------------------------- the event set

@pytest.fixture(scope="module")
def event_set():
    sites = _sites()
    daily = hw.daily_rain_features(_hourly(hw.cells_of(sites)))
    model = StubModel()
    ev = _events(daily, sites, model)
    df, info = hw.build_event_set(sites, ev, hw._same_year(sites), [2025], daily, 1.004, {"holdout": model})
    return sites, daily, ev, df, info


def test_event_set_site_rules(event_set):
    _, _, _, df, info = event_set
    # C has no discharges and a count of 0: kept with no spill-days. D has no discharges but counts 3
    # spills: left out (its discharges cannot be found). A and B join by position.
    assert set(df.site_id) == {"A", "B", "C"}
    assert df.loc[df.site_id == "C", "y"].sum() == 0
    assert info["no_events_but_spills"] == 1
    assert info["joined_by_position"] == 2 and info["unjoined_sites"] == 0


def test_event_set_low_uptime_site_year_is_dropped():
    sites = _sites()
    sites.loc[sites.site_id == "B", "same_year_uptime"] = 40.0
    daily = hw.daily_rain_features(_hourly(hw.cells_of(sites)))
    model = StubModel()
    df, info = hw.build_event_set(sites, _events(daily, sites, model), hw._same_year(sites), [2025], daily,
                                  1.004, {"holdout": model})
    assert "B" not in set(df.site_id) and info["low_uptime_site_years"] == 1


def test_event_set_arms_and_baselines(event_set):
    _, _, _, df, _ = event_set
    a = df[df.site_id == "A"]
    # Default arm: every overflow gets 20 spills, so the stub's shift is zero there.
    z = 0.4 * (a["rain_d"].to_numpy() - 8)
    assert np.allclose(a[hw.DEFAULT], np.clip(1 / (1 + np.exp(-z)), 1e-4, 1 - 1e-4), atol=1e-6)
    assert not np.allclose(a[hw.OWN], a[hw.DEFAULT])
    assert a[hw.BEFORE].iloc[0] == pytest.approx(40 * 1.004 / 365)
    # C has no count the year before: it takes the median of the others (40 and 10 -> 25).
    assert df.loc[df.site_id == "C", hw.BEFORE].iloc[0] == pytest.approx(25 * 1.004 / 365)
    assert df[hw.FLAT].nunique() == 1 and df[hw.FLAT].iloc[0] == pytest.approx(df.y.mean())


def test_score_set_on_the_small_set(event_set):
    _, _, _, df, _ = event_set
    sc = hw.score_set(df, n_boot=200)
    own = sc["forecasts"][hw.OWN]
    # Events were drawn from the stub's own probabilities, so it beats last year's flat rate. With
    # three overflows the interval is wide (a draw of C alone is all dry days), so only its order.
    assert own["bss_vs_year_before"] > 0
    assert own["bss_vs_year_before_ci"][0] < own["bss_vs_year_before"] < own["bss_vs_year_before_ci"][1]
    assert {"wet", "dry"} <= set(sc["wet_dry"])
    assert sum(r["n"] for r in sc["reliability_own"]) == len(df)


def test_score_set_and_gate_on_a_model_that_knows_the_answer():
    rng = np.random.default_rng(5)
    days = pd.date_range("2025-01-01", "2025-12-31", freq="D", tz="UTC")
    n = 30
    df = pd.DataFrame({"site_id": np.repeat([f"s{i}" for i in range(n)], len(days)), "day": np.tile(days, n)})
    rain = rng.gamma(0.5, 6.0, len(df))
    level = np.repeat(rng.normal(0, 1, n), len(days))
    df[hw.OWN] = 1 / (1 + np.exp(-(0.3 * (rain - 10) + level)))
    df["y"] = (rng.random(len(df)) < df[hw.OWN]).astype(int)
    df[hw.DEFAULT] = 1 / (1 + np.exp(-(0.3 * (rain - 10))))
    df[hw.BEFORE] = df.groupby("site_id")[hw.OWN].transform("mean")   # the right level, no weather
    df[hw.FLAT] = df["y"].mean()
    df["rain_d"], df["rain_d1"] = rain, 0.0
    df["wet"] = rain > hw.WET_MM
    sc = hw.score_set(df, n_boot=300)
    own = sc["forecasts"][hw.OWN]
    assert own["bss_vs_year_before_ci"][0] > 0
    assert own["bss_vs_year_before"] > sc["forecasts"][hw.DEFAULT]["bss_vs_year_before"]
    info = {"overflows": n, "spill_days": int(df.y.sum())}
    g = hw.gate({"A1": {"info": info, "scores": sc, "leads": {}}, "A2": {"untested": "missing"}})
    assert g["parts"]["A1 lead 0"]["passes"] is True
    assert g["verdict"] == "NOT COMPLETE"      # A2 and the leads untested: not a pass


def test_with_lead_takes_target_day_and_two_before_from_the_forecast(event_set):
    _, daily, _, df, _ = event_set
    lead = {k: daily.assign(rain_d=daily["rain_d"] + 100 * (k + 1)) for k in range(4)}
    d2 = hw.with_lead(df, lead, 2)
    row = d2.iloc[40]
    base = daily.set_index(["cell_lat", "cell_lon", "day"])["rain_d"]
    key = (row.cell_lat, row.cell_lon)
    assert row.rain_d == pytest.approx(base[(*key, row.day)] + 300)
    assert row.rain_d1 == pytest.approx(base[(*key, row.day - pd.Timedelta(days=1))] + 200)
    assert row.rain_d2 == pytest.approx(base[(*key, row.day - pd.Timedelta(days=2))] + 100)
    assert row.rain_7d == pytest.approx(df.iloc[40].rain_7d)       # longer windows stay reanalysis


def test_score_leads_untested_below_minimum(event_set):
    _, daily, _, df, _ = event_set
    lead = {k: daily for k in range(4)}
    r = hw.score_leads(df, lead, StubModel(), n_boot=50)
    assert r["1"]["tested"] is False          # 3 overflows < LEAD_MIN_SITES


# ---------------------------------------------------------------------------- A3 and the verdicts

def test_annual_totals_and_ratio():
    sites = _sites()
    daily = hw.daily_rain_features(_hourly(hw.cells_of(sites)))
    t = hw.annual_totals(sites, daily, 2025, StubModel())
    assert (t["rain_days"] == 365).all()
    sd = hw.build_site_days(sites[sites.site_id == "A"], daily,
                            pd.date_range("2025-01-01", "2025-12-31", freq="D", tz="UTC"))
    assert t.set_index("site_id").loc["A", hw.OWN] == pytest.approx(
        StubModel().predict_pooled(hw.features(sd)).mean() * 365)
    s = hw.score_annual(t, 1.004, n_boot=100)
    assert s["overflows"] == 4
    assert s[hw.OWN]["ratio"] == pytest.approx(t[hw.OWN].sum() / (1.004 * t["spills"].sum()))
    assert s["level_ok"] == (1 / 1.5 <= s[hw.OWN]["ratio"] <= 1.5)


def test_score_annual_leaves_out_overflows_short_of_rain():
    t = pd.DataFrame({"site_id": list("abcd"), "spills": [10.0, 20.0, 30.0, 40.0], "prev_spills": [9.0, 21, 28, 41],
                      hw.OWN: [10.0, 20, 30, 40], hw.DEFAULT: [20.0] * 4, "rain_days": [365, 365, 365, 100]})
    s = hw.score_annual(t, 1.0, n_boot=50)
    assert s["overflows"] == 3 and s[hw.OWN]["ratio"] == pytest.approx(1.0) and s["level_ok"] is True


def _part(lo):
    return {"forecasts": {hw.OWN: {"bss_vs_year_before": lo + 0.1, "bss_vs_year_before_ci": [lo, lo + 0.2]}}}


def _leads(lo, tested=True):
    return {str(k): ({"tested": True, "bss_vs_year_before": lo + 0.1, "bss_vs_year_before_ci": [lo, lo + 0.2],
                      "passes": lo > 0} if tested else {"tested": False, "why": "few"}) for k in (1, 2, 3)}


@pytest.mark.parametrize("a1, a2, l1, l2, verdict", [
    (0.05, 0.05, _leads(0.01), _leads(0.02), "PASS"),
    (0.05, -0.01, _leads(0.01), _leads(0.02), "FAIL"),
    (0.05, 0.05, _leads(-0.2), _leads(0.02), "FAIL"),
    (0.05, 0.05, _leads(0.01, tested=False), _leads(0.02), "NOT COMPLETE"),
    (0.0, 0.05, _leads(0.01, tested=False), _leads(0.02), "FAIL"),   # a lower end of exactly 0 is not above 0
])
def test_gate_verdicts(a1, a2, l1, l2, verdict):
    info = {"overflows": 40, "spill_days": 1000}
    res = {"A1": {"info": info, "scores": _part(a1), "leads": l1},
           "A2": {"info": info, "scores": _part(a2), "leads": l2},
           "A3": {"scores": {"level_ok": False, hw.OWN: {"ratio": 2.0}}}}
    g = hw.gate(res)
    assert g["verdict"] == verdict
    assert g["a3_level_ok"] is False          # reported beside the verdict, never changes it


def test_gate_small_set_is_untested():
    res = {"A1": {"info": {"overflows": 5, "spill_days": 1000}, "scores": _part(0.3), "leads": _leads(0.1)},
           "A2": {"info": {"overflows": 40, "spill_days": 1000}, "scores": _part(0.3), "leads": _leads(0.1)}}
    g = hw.gate(res)
    assert g["parts"]["A1 lead 0"]["tested"] is False and g["verdict"] == "NOT COMPLETE"


def test_gate_a_is_written_in_the_docstring():
    doc = hw.__doc__
    for phrase in ("GATE A", "before the first run", "G1.", "G2.", "G3.", "NOT COMPLETE", "1/1.5 to 1.5",
                   "2,000 draws", "spill_model_holdout_2025.pkl"):
        assert phrase in doc


def test_clean_makes_json_safe_values():
    out = hw.clean({"a": np.float64(np.nan), "b": np.int64(3), "c": [np.bool_(True), 0.123456789]})
    assert out == {"a": None, "b": 3, "c": [True, 0.12346]}
