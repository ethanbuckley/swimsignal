"""scripts/sonde_signal_eval (docs/SONDE-SIGNAL-TEST-2026-10.md), on synthetic data only: no network, no EA file, no
E. coli value. Matching by river name, distance, network rule and deployment; a lookup that cannot see past the cut;
the anomaly against the sonde's own 30-day median; the fallback; B and H from predictions; the near-miss labels in
their order; a placebo that stays in season and keeps a signal only when the day carries it; the request ledger."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

D = Path(__file__).resolve().parents[1] / "scripts" / "sonde_signal_eval"
sys.path.insert(0, str(D))
import feature as ft
import labels as lb
import placebo as pl
import sondes as so


def _load(name: str):
    """score.py and fetch.py share names with other harnesses' modules, so they load under their own names."""
    spec = importlib.util.spec_from_file_location(f"sonde_{name}", D / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


score = _load("score")
fetch = _load("fetch")


# --- matching -------------------------------------------------------------------------------------------------------
def _station(sid, label, lat, lon, opened="2024-01-01", closed=None, props=("turbidity", "ammonium")):
    code = {"turbidity": ("TURBIDITY", "turb", "ntu"), "ammonium": ("AMMONIUM", "amm", "mgL")}
    ms = [{"@id": f"http://x/measures/{sid}-{code[p][1]}-i-subdaily-{code[p][2]}", "parameter": code[p][0], "period": 900}
          for p in props]
    ms.append({"@id": f"http://x/measures/{sid}-do-i-subdaily-pct", "parameter": "DISSOLVED OXYGEN", "period": 900})
    return {"notation": sid, "label": label, "lat": lat, "long": lon, "dateOpened": opened, "dateClosed": closed,
            "measures": ms}


def test_parse_keeps_only_fifteen_minute_measures_in_the_stated_unit():
    st = _station("E1", "WHARFE_ILKLEY_E_202401", 53.9, -1.8)
    st["measures"].append({"@id": "http://x/measures/E1-turb-m-daily-ntu", "parameter": "TURBIDITY", "period": 86400})
    (s,) = so.parse_stations([st])
    assert s.measures == {"turbidity": "E1-turb-i-subdaily-ntu", "ammonium": "E1-amm-i-subdaily-mgL"}
    assert s.river == "Wharfe"
    (t,) = so.parse_stations([_station("E2", "NIDD_X_E_202401", 54.0, -1.4, props=("ammonium",))])
    assert "turbidity" not in t.measures


def test_candidates_need_the_same_river_and_the_distance():
    sondes = so.parse_stations([
        _station("A", "WHARFE_NEAR_E_202401", 53.93, -1.82),       # same river, ~0.5 km
        _station("B", "AIRE_NEAR_E_202401", 53.93, -1.82),         # another river, same place
        _station("C", "WHARFE_FAR_E_202401", 54.20, -1.82),        # same river, ~30 km
        _station("D", "WHARFE_MID_E_202401", 53.99, -1.82),        # same river, ~6.7 km
    ])
    got = so.candidates(sondes, 53.9319, -1.8162, "River Wharfe", "turbidity")
    assert [s.station_id for s, _ in got] == ["A", "D"]
    assert so.candidates(sondes, 53.9319, -1.8162, None, "turbidity") == []


def test_network_rule_and_order():
    assert so.network_ok(("upstream", 19.9)) and not so.network_ok(("upstream", 20.1))
    assert so.network_ok(("downstream", 2.0)) and not so.network_ok(("downstream", 2.1))
    assert not so.network_ok(None)
    a, b, c = (so.Sonde(i, i, "X", 0, 0, date(2024, 1, 1), None) for i in "abc")
    assert [s.station_id for s in so.order([(a, ("downstream", 0.5)), (b, ("upstream", 9.0)), (c, ("upstream", 3.0))])] \
        == ["c", "b", "a"]


def test_deployment_covers_and_a_placeholder_close_date():
    (s,) = so.parse_stations([_station("E", "AVON_X_E_202605", 50.9, -1.8, opened="2026-05-05", closed="1970-01-01")])
    assert s.closed is None and s.covers(date(2026, 7, 1)) and not s.covers(date(2026, 5, 4))
    (t,) = so.parse_stations([_station("F", "AVON_Y_E_202505", 50.9, -1.8, opened="2025-05-01", closed="2025-08-21")])
    assert t.covers(date(2025, 8, 21)) and not t.covers(date(2025, 8, 22))
    (u,) = so.parse_stations([_station("G", "AVON_Z", 50.9, -1.8, opened=None)])
    assert not u.covers(date(2025, 6, 1))


# --- the feature ----------------------------------------------------------------------------------------------------
def _series(start="2025-05-01", end="2025-07-31", base=10.0, spikes=()):
    idx = pd.date_range(start, end, freq="15min", tz="UTC")
    v = np.full(len(idx), base)
    s = pd.Series(v, index=idx)
    for t0, t1, val in spikes:
        s[(s.index >= pd.Timestamp(t0, tz="UTC")) & (s.index < pd.Timestamp(t1, tz="UTC"))] = val
    return s


def test_anomaly_is_log_ratio_to_the_own_30_day_median():
    s = _series(spikes=[("2025-07-10 02:00", "2025-07-10 04:00", 40.0)])
    a = ft.anomaly(s, pd.Timestamp("2025-07-10 04:00", tz="UTC"), "turbidity")
    assert a == pytest.approx(math.log(4.0))
    assert ft.anomaly(_series(), pd.Timestamp("2025-07-10 04:00", tz="UTC"), "turbidity") == pytest.approx(0.0)


def test_lookup_reads_nothing_after_the_cut():
    """A huge rise straight after the cut must not change the feature; one just before it must."""
    t_cut = pd.Timestamp("2025-07-10 06:00", tz="UTC")
    calm = ft.anomaly(_series(), t_cut, "turbidity")
    after = ft.anomaly(_series(spikes=[("2025-07-10 06:00:01", "2025-07-12", 4000.0)]), t_cut, "turbidity")
    at = ft.anomaly(_series(spikes=[("2025-07-10 06:00", "2025-07-10 06:00:01", 4000.0)]), t_cut, "turbidity")
    assert calm == after == 0.0 and at == 0.0          # one reading of 8 does not move the median
    before = ft.anomaly(_series(spikes=[("2025-07-10 04:00:01", "2025-07-10 06:00:01", 4000.0)]), t_cut, "turbidity")
    assert before == pytest.approx(ft.CLIP)


def test_the_cut_is_sample_time_minus_the_lag_in_utc():
    t = pd.Timestamp("2025-07-10 12:00", tz="Europe/London")      # 11:00 UTC in summer
    assert ft.cut_time(t) == pd.Timestamp("2025-07-10 05:00", tz="UTC")
    assert ft.cut_time(t, ft.ALT_LAG_H) == pd.Timestamp("2025-07-09 11:00", tz="UTC")
    # the sample's own rise, between the cut and the sample, is invisible
    s = _series(spikes=[("2025-07-10 05:15", "2025-07-10 12:00", 500.0)])
    v, sid = ft.sample_feature(t, ["E1"], {"E1": s}, "turbidity")
    assert sid == "E1" and v == 0.0


def test_quality_plausibility_and_floor():
    df = pd.DataFrame({"dateTime": ["2025-07-01T00:00:00", "2025-07-01T00:15:00", "2025-07-01T00:30:00",
                                    "2025-07-01T00:45:00", "2025-07-01T00:45:00"],
                       "value": [1.0, -2.0, 5000.0, "x", 3.0], "quality": ["Unchecked", "Good", "Good", "Good", "Suspect"]})
    s = ft.clean(df, "turbidity")
    assert list(s.values) == [1.0] and str(s.index.tz) == "UTC"
    zero = _series(base=0.0, spikes=[("2025-07-10 02:00", "2025-07-10 04:00", 0.5)])
    assert ft.anomaly(zero, pd.Timestamp("2025-07-10 04:00", tz="UTC"), "turbidity") == pytest.approx(math.log(5.0))


def test_too_few_readings_is_missing_and_the_fallback_is_zero():
    s = _series(start="2025-07-05", end="2025-07-10 04:00")       # ~5 days of baseline, under MIN_BASE
    assert math.isnan(ft.anomaly(s, pd.Timestamp("2025-07-10 04:00", tz="UTC"), "turbidity"))
    gap = _series()
    gap = gap[(gap.index < pd.Timestamp("2025-07-10 02:30", tz="UTC")) | (gap.index > pd.Timestamp("2025-07-10 04:00", tz="UTC"))]
    assert math.isnan(ft.anomaly(gap, pd.Timestamp("2025-07-10 04:00", tz="UTC"), "turbidity"))   # 2 of 8 now slots
    v, have = ft.with_fallback(np.array([0.5, np.nan, -1.0]))
    assert list(v) == [0.5, 0.0, -1.0] and list(have) == [True, False, True]


def test_first_valid_sonde_in_order_is_used():
    t = pd.Timestamp("2025-07-10 12:00", tz="Europe/London")
    good = _series(spikes=[("2025-07-10 03:00", "2025-07-10 05:00", 20.0)])
    v, sid = ft.sample_feature(t, ["EMPTY", "SHORT", "GOOD"], {"EMPTY": pd.Series(dtype=float),
                                                               "SHORT": _series(start="2025-07-09"), "GOOD": good},
                               "turbidity")
    assert sid == "GOOD" and v == pytest.approx(math.log(2.0))
    assert ft.sample_feature(t, [], {}, "turbidity")[1] is None


def test_build_feature_uses_deployment_and_skips_lakes():
    up = so.Sonde("UP", "x", "X", 0, 0, date(2025, 5, 1), date(2025, 12, 1))
    old = so.Sonde("OLD", "x", "X", 0, 0, date(2020, 1, 1), date(2020, 12, 1))
    matched = {("bw1", "turbidity"): [(old, ("upstream", 1.0)), (up, ("upstream", 5.0))]}
    series = {("UP", "turbidity"): _series(spikes=[("2025-07-10 03:00", "2025-07-10 05:00", 30.0)]),
              ("OLD", "turbidity"): _series(base=99.0)}
    t = pd.Timestamp("2025-07-10 12:00", tz="Europe/London")
    v, used = score.build_feature(["bw1", "bw1", "bw2"], [t, t, t], [True, False, True], matched, series, "turbidity")
    assert used == ["UP", None, None] and v[0] == pytest.approx(math.log(3.0)) and np.isnan(v[1:]).all()


# --- margins and labels -----------------------------------------------------------------------------------------------
def test_one_band_move_and_margin_b():
    p = np.array([0.02, 0.12, 0.20, 0.30, 0.45, 0.90])
    assert list(lb.one_band_move(p)) == pytest.approx([0.175, 0.05, 0.375, 0.175, 0.75, 0.375])
    m = lb.margin_b(np.array([0.20] * 10))
    assert m["B_raw"] == pytest.approx(0.05 * 0.175 ** 2) and m["B"] == m["H"] == pytest.approx(0.00153125)
    small = lb.margin_b(np.array([0.10, 0.11]))      # moves of 0.05 and 0.06: B_raw 0.00015, under the floor
    assert small["B_raw"] == pytest.approx(0.05 * (0.05 ** 2 + 0.06 ** 2) / 2) and small["B"] == lb.B_FLOOR
    assert small["floor_used"]


@pytest.mark.parametrize("d,lo,hi,sec,want", [
    (0.003, 0.0005, 0.006, False, "Better"),
    (0.0015, 0.0001, 0.003, False, "Better"),
    (0.0014, 0.0001, 0.0014, False, "No useful difference"),  # above zero, but wholly under B
    (0.0014, 0.0001, 0.003, False, "Unlabelled"),             # above zero, d under B, U over B: a gap, reported
    (0.001, -0.0005, 0.0025, False, "Promising, not shown"),
    (0.001, -0.0005, 0.0025, True, "Unlabelled"),             # promising, but a secondary check is harm
    (0.0002, -0.0005, 0.0012, False, "Promising, not shown"),
    (-0.0002, -0.0005, 0.0012, False, "No useful difference"),
    (-0.001, -0.002, 0.0005, False, "Possible harm"),
    (-0.003, -0.004, -0.001, False, "Possible harm"),            # the 26 Oct note: never "Harm" in this order
    (0.0005, -0.003, 0.004, False, "Too uncertain"),
    (0.0005, -0.003, 0.001, False, "Unlabelled"),                # the addendum's gap: reported as it is
])
def test_labels_in_the_addendum_order(d, lo, hi, sec, want):
    b = h = 0.0015
    assert lb.label(d, lo, hi, b, h, sec) == want


def test_label_rejects_h_above_b():
    with pytest.raises(AssertionError):
        lb.label(0.0, -0.1, 0.1, 0.001, 0.002)


def test_compare_on_synthetic_rows():
    rng = np.random.default_rng(3)
    n = 400
    y = rng.integers(0, 2, n)
    good = np.clip(y * 0.7 + 0.15, 0, 1)
    flat = np.full(n, 0.5)
    clusters = np.repeat(np.arange(40), 10)
    mask = np.ones(n, dtype=bool)
    r = score.compare(y, flat, good, clusters, mask, 0.0015, 0.0015)
    assert r["brier_gain"] > 0.1 and r["label"] == "Better"
    r2 = score.compare(y, good, flat, clusters, mask, 0.0015, 0.0015)
    assert r2["label"] == "Possible harm"


def test_warn_rates():
    w = score.warn_rates(np.array([1, 1, 0, 0]), np.array([0.3, 0.1, 0.3, 0.1]))
    assert w["miss_rate"] == 0.5 and w["false_alarm_rate"] == 0.5


# --- placebo --------------------------------------------------------------------------------------------------------
def test_placebo_shifts_whole_weeks_and_stays_in_season():
    times = list(pd.date_range("2025-05-02 12:00", "2025-09-29 12:00", freq="9D", tz="Europe/London"))
    sh = pl.shifted_times(times, np.random.default_rng(0))
    assert all(s is not None for s in sh)
    for t, s in zip(times, sh, strict=True):
        k = (s - t) / pd.Timedelta(weeks=1)
        assert abs(k) in pl.WEEKS and k == int(k)
        assert pl.in_season(s, 2025)


def test_placebo_keeps_level_but_loses_the_day():
    """A sonde whose anomaly marks the sample day: the real feature finds it, shifted lookups do not."""
    days = pd.date_range("2025-06-02", "2025-08-25", freq="7D")
    spikes = [(f"{d.date()} 01:00", f"{d.date()} 06:00", 80.0) for d in days[::3]]
    s = _series(start="2025-04-01", end="2025-09-30", spikes=spikes)
    marked = [pd.Timestamp(f"{d.date()} 12:00", tz="Europe/London") for d in days[::3]]
    real = [ft.sample_feature(t, ["S"], {"S": s}, "turbidity")[0] for t in marked]
    assert all(v == pytest.approx(math.log(8.0)) for v in real)
    sh = pl.shifted_times(marked, np.random.default_rng(1))
    fake = [ft.sample_feature(t, ["S"], {"S": s}, "turbidity", at=a)[0] for t, a in zip(marked, sh, strict=True)]
    assert np.mean(np.array(fake) > 1.0) < 0.5


def test_loso_gain_follows_a_day_signal_and_a_within_site_shuffle_does_not():
    """Synthetic rows at 8 sites: exceedance driven by a day anomaly. The candidate with the real feature beats the
    reference under leave-one-site-out; the same feature shuffled within each site (a placebo) does not."""
    score._paths()
    import train_ecoli as te
    rng = np.random.default_rng(7)
    site = np.repeat([f"s{i}" for i in range(8)], 60)
    a = rng.normal(0, 1, len(site))
    anom = rng.normal(0, 1, len(site))
    y = (rng.random(len(site)) < 1 / (1 + np.exp(-(-1.0 + 0.5 * a + 1.5 * anom)))).astype(int)
    X = pd.DataFrame({"a": a, "sonde": anom})
    lake = np.zeros(len(site))
    p_ref = te.leave_one_out(X, y, site, lake, ["a"])
    p_new = te.leave_one_out(X, y, site, lake, ["a", "sonde"])
    shuffled = X.assign(sonde=np.concatenate([rng.permutation(anom[site == s]) for s in np.unique(site)]))
    p_pl = te.leave_one_out(shuffled, y, site, lake, ["a", "sonde"])
    brier = lambda p: float(np.mean((p - y) ** 2))
    assert brier(p_ref) - brier(p_new) > 0.02
    assert brier(p_ref) - brier(p_pl) < 0.005
    m = lb.margin_b(p_ref)
    r = score.compare(y, p_ref, p_new, site, np.ones(len(y), bool), m["B"], m["H"])
    assert r["label"] == "Better"


def test_rank_p():
    assert pl.rank_p(1.0, np.zeros(199)) == pytest.approx(1 / 200)
    assert pl.rank_p(0.0, np.ones(199)) == 1.0


# --- the request ledger ---------------------------------------------------------------------------------------------
def _fake_get(statuses):
    it = iter(statuses)

    def get(url, params):
        return SimpleNamespace(status_code=next(it), content=b"{}", raise_for_status=lambda: None)
    return get


def test_ledger_paces_counts_retries_and_stops_at_the_cap(tmp_path):
    clock = {"t": 0.0}
    slept = []

    def sleep(s):
        slept.append(s); clock["t"] += s

    led = fetch.Ledger(tmp_path, cap=3, get=_fake_get([200, 503, 200, 200]), sleep=sleep, clock=lambda: clock["t"])
    led.request("u", {})
    led.request("u", {})                               # a 503, retried once after RETRY_S: two requests
    assert led.n == 3 and fetch.RETRY_S in slept
    assert all(s >= fetch.PACE_S - 1e-9 for s in slept if s != fetch.RETRY_S)
    with pytest.raises(SystemExit):
        led.request("u", {})
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    assert [json.loads(x)["status"] for x in lines] == [200, 503, 200]


def test_fetch_plan_from_matched(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("station_id,property,network_ok,samples_covered,years\n"
                 "E1,turbidity,True,20,[2025]\nE1,ammonium,True,20,[2025]\n"
                 "E2,turbidity,False,59,[2024]\nE3,turbidity,True,0,[]\n")
    assert fetch.plan(str(p)) == [("E1-amm-i-subdaily-mgL", "ammonium", 2025), ("E1-turb-i-subdaily-ntu", "turbidity", 2025)]
