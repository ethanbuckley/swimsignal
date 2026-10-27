"""scripts/flow_dilution_eval (docs/FLOW-DILUTION-TEST-2026-10.md), on synthetic data only: no network, no E. coli, no
model. Gauge mapping (spot rule and the per-overflow rule), the no-leakage flow lookup, the fallback, the exposure
step against the replay's, the reference flow, the placebo shifts, the margins, the labels, the gate, and the capped
EA client."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "flow_dilution_eval"))
import flow_fetch as ff
import flow_protocol as fp


# ---- gauge mapping ----------------------------------------------------------------------------------------------
def cand(name, side, along, ratio, **kw):
    return {"station": name, "side": side, "along_km": along, "area_ratio": ratio, **kw}


def test_spot_gauge_is_the_nearest_along_the_river_up_or_down():
    c = [cand("far up", "upstream", 9.0, 0.9), cand("near down", "downstream", 3.1, 1.1),
         cand("near up", "upstream", 4.4, 0.95)]
    assert fp.choose_spot_gauge(c)["station"] == "near down"


def test_spot_gauge_skips_part_channels_other_catchments_and_far_gauges():
    c = [cand("side channel", "upstream", 0.5, 1.0, part=True), cand("tributary", "upstream", 1.0, 0.3),
         cand("estuary", "downstream", 2.0, 2.5), cand("too far", "downstream", 26.0, 1.0),
         cand("ok", "upstream", 12.0, 0.8)]
    assert fp.choose_spot_gauge(c)["station"] == "ok"
    assert fp.choose_spot_gauge(c[:4]) is None
    assert fp.choose_spot_gauge([]) is None


def test_spot_gauge_prefers_a_total_station_at_the_same_site():
    c = [cand("East Mills Flume", "upstream", 1.50, 0.99), cand("East Mills Combined", "upstream", 1.55, 0.99, total=True)]
    assert fp.choose_spot_gauge(c)["station"] == "East Mills Combined"


def test_overflow_gauge_must_be_below_the_overflow_and_above_the_spot():
    c = [cand("below spot", "downstream", 1.0, 1.0, below_overflow=True, same_river=True),
         cand("above overflow", "upstream", 2.0, 0.9, below_overflow=False, same_river=True),
         cand("between far", "upstream", 9.0, 0.7, below_overflow=True, same_river=True),
         cand("between near", "upstream", 4.0, 0.8, below_overflow=True, same_river=True),
         cand("tributary", "upstream", 3.0, 0.2, below_overflow=True, same_river=False)]
    assert fp.choose_overflow_gauge(c)["station"] == "between near"
    assert fp.choose_overflow_gauge(c[:2]) is None


def test_overflow_gauge_needs_half_the_spots_catchment_and_the_spots_river():
    c = [cand("small", "upstream", 1.0, 0.49, below_overflow=True, same_river=True),
         cand("other river", "upstream", 1.0, 0.9, below_overflow=True, same_river=False)]
    assert fp.choose_overflow_gauge(c) is None


# ---- timing: no leakage -----------------------------------------------------------------------------------------
def test_issue_time_is_nine_london_or_an_hour_before_the_sample():
    bst = pd.Timestamp("2025-07-10 12:30", tz="Europe/London")
    assert fp.issue_time(bst) == pd.Timestamp("2025-07-10 08:00", tz="UTC")
    early = pd.Timestamp("2025-07-10 09:20", tz="Europe/London")
    assert fp.issue_time(early) == pd.Timestamp("2025-07-10 07:20", tz="UTC")
    gmt = pd.Timestamp("2025-09-30 23:30", tz="UTC")   # 00:30 London on 1 Oct: the London date counts
    assert fp.issue_time(gmt) == pd.Timestamp("2025-09-30 23:30", tz="UTC") - pd.Timedelta(hours=1)
    with pytest.raises(ValueError):
        fp.issue_time(pd.Timestamp("2025-07-10 12:00"))


def series(start, end, value=10.0, freq="15min"):
    idx = pd.date_range(start, end, freq=freq, tz="UTC")
    return pd.Series(value, index=idx, dtype=float)


def test_flow_at_issue_reads_nothing_after_the_published_window():
    issue = pd.Timestamp("2025-07-10 08:00", tz="UTC")
    q = series("2025-07-08", "2025-07-11")
    base = fp.flow_at_issue(q, issue, fp.LAG_REALTIME_H)
    assert base == pytest.approx(10.0)
    q2 = q.copy()
    q2[q2.index > issue - pd.Timedelta(hours=fp.LAG_REALTIME_H)] = 1e6   # the flood after the cut
    assert fp.flow_at_issue(q2, issue, fp.LAG_REALTIME_H) == pytest.approx(10.0)
    q3 = q.copy()
    q3[q3.index == issue - pd.Timedelta(hours=fp.LAG_REALTIME_H)] = 970.0   # the last published reading counts
    assert fp.flow_at_issue(q3, issue, fp.LAG_REALTIME_H) > 10.0


def test_archive_gauges_wait_36_hours():
    issue = pd.Timestamp("2025-07-10 08:00", tz="UTC")
    q = series("2025-07-06", "2025-07-11")
    q[q.index > pd.Timestamp("2025-07-08 20:00", tz="UTC")] = 50.0     # rise inside the last 36 h only
    assert fp.lag_for(False) == 36.0 and fp.lag_for(True) == 1.0
    assert fp.flow_at_issue(q, issue, fp.lag_for(False)) == pytest.approx(10.0)
    assert fp.flow_at_issue(q, issue, fp.lag_for(True)) == pytest.approx(50.0)


def test_flow_at_issue_needs_ninety_percent_of_the_slots():
    issue = pd.Timestamp("2025-07-10 08:00", tz="UTC")
    q = series("2025-07-08", "2025-07-11")
    start, end = fp.window(issue, 1.0)
    inside = q[(q.index > start) & (q.index <= end)]
    assert len(inside) == 96
    gap9 = q.drop(inside.index[:9])     # 87 of 96 slots: 90.6%
    gap10 = q.drop(inside.index[:10])   # 86 of 96: 89.6%
    assert np.isfinite(fp.flow_at_issue(gap9, issue, 1.0))
    assert np.isnan(fp.flow_at_issue(gap10, issue, 1.0))
    hourly = series("2025-07-08", "2025-07-11", freq="1h")
    assert np.isnan(fp.flow_at_issue(hourly, issue, 1.0))   # 24 readings do not fill 96 slots


def test_clean_readings_drops_unusable_quality_and_duplicates():
    df = pd.DataFrame({"dateTime": ["2025-07-01T00:00:00Z", "2025-07-01T00:15:00Z", "2025-07-01T00:15:00Z",
                                    "2025-07-01T00:30:00Z", "2025-07-01T00:45:00Z"],
                       "value": [1.0, 2.0, 3.0, "x", 5.0], "quality": ["Good", "Unchecked", "Estimated", "Good", "Suspect"]})
    s = fp.clean_readings(df)
    assert list(s.to_numpy()) == [1.0, 3.0]
    assert str(s.index.tz) == "UTC"


# ---- reference flow, factor, fallback ---------------------------------------------------------------------------
def daily_seasons(years, value=lambda y: 4.0, drop_days=0):
    parts = []
    for y in years:
        idx = pd.date_range(f"{y}-05-01", f"{y}-09-30", freq="D")
        s = pd.Series(value(y), index=idx, dtype=float)
        parts.append(s.iloc[drop_days:])
    return pd.concat(parts)


def test_reference_flow_uses_only_full_enough_seasons_before_2024():
    s = pd.concat([daily_seasons(range(2014, 2019), lambda y: 2.0), daily_seasons(range(2019, 2024), lambda y: 8.0,
                                                                                   drop_days=20),
                   daily_seasons([2024, 2025], lambda y: 100.0)])
    assert fp.reference_flow(s) == pytest.approx(2.0)          # 2019-23 lack 20 days (87%); 2024-25 are not used
    assert np.isnan(fp.reference_flow(daily_seasons(range(2014, 2018))))   # four seasons
    winter = pd.Series(100.0, index=pd.date_range("2014-01-01", "2023-12-31", freq="D"))
    assert fp.reference_flow(winter) == pytest.approx(100.0)   # only May-September enter
    assert fp.reference_flow(pd.concat([winter[winter.index.month < 5], daily_seasons(range(2014, 2024))])) == 4.0


def test_flow_factor_is_clipped_and_missing_is_nan():
    assert fp.flow_factor(4.0, 4.0) == 1.0
    assert fp.flow_factor(1.0, 4.0, k=0.5) == pytest.approx(2.0)      # low flow: less dilution, more weight
    assert fp.flow_factor(16.0, 4.0, k=0.5) == pytest.approx(0.5)     # high flow
    assert fp.flow_factor(1e-6, 4.0) == fp.FACTOR_MAX
    assert fp.flow_factor(1e6, 4.0) == fp.FACTOR_MIN
    for q, r in ((np.nan, 4.0), (1.0, np.nan), (0.0, 4.0), (1.0, -1.0)):
        assert np.isnan(fp.flow_factor(q, r))


def test_fallback_and_identity_leave_production_weights_unchanged():
    w = np.array([0.3, 0.05, 0.0, 0.2])
    d = np.array([0.6, 0.1, 0.0, 1.0])
    assert np.array_equal(fp.flow_weights(w, d, np.full(4, np.nan)), w)
    assert np.allclose(fp.flow_weights(w, d, np.ones(4)), w, rtol=0, atol=1e-15)
    f = np.array([2.0, 0.5, 3.0, 2.0])
    got = fp.flow_weights(w, d, f)
    assert got == pytest.approx([0.3 * 1.0 / 0.6, 0.05 * 0.05 / 0.1, 0.0, 0.2])   # dilution capped at 1
    two = fp.flow_weights(w, d, np.array([[np.nan, 2.0], [0.5, 1.0], [1.0, 1.0], [0.5, np.nan]]))
    assert two[:, 0] == pytest.approx([0.3, 0.025, 0.0, 0.1]) and two[:, 1] == pytest.approx([0.5, 0.05, 0.0, 0.2])


def test_exposure_matches_the_replay_at_lead_zero():
    pytest.importorskip("dipcast")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from replay_ecoli_leads import combine_daily_leads
    rng = np.random.default_rng(5)
    P = rng.uniform(0, 0.6, size=(6, 20))
    w = rng.uniform(0, 0.5, size=6)
    tr = np.array([0.0, 5.0, 23.9, 24.0, 40.0, 100.0])
    want = combine_daily_leads({k: P for k in range(5)}, w, tr, 0)
    assert np.allclose(fp.exposure_lead0(P, w, tr), want, rtol=0, atol=1e-12)
    W = np.broadcast_to(w[:, None], P.shape).copy()
    W[:, 7] *= 0.5
    got = fp.exposure_lead0(P, W, tr)
    assert np.allclose(np.delete(got, 7), np.delete(want, 7), atol=1e-12) and got[7] < want[7]


# ---- placebo ----------------------------------------------------------------------------------------------------
def test_placebo_shift_wraps_inside_the_same_season():
    assert fp.shifted_day(pd.Timestamp("2025-09-25"), 10) == pd.Timestamp("2025-05-05")
    assert fp.shifted_day(pd.Timestamp("2025-05-01 12:00", tz="UTC"), 152) == pd.Timestamp("2025-09-30 12:00", tz="UTC")
    assert fp.shifted_day(pd.Timestamp("2024-06-01"), fp.SEASON_DAYS) == pd.Timestamp("2024-06-01")
    with pytest.raises(ValueError):
        fp.shifted_day(pd.Timestamp("2025-10-01"), 20)


def test_placebo_shifts_are_seeded_and_never_near_the_true_day():
    s = fp.placebo_shifts(["a", "b", "c"])
    assert s.shape == (200, 3)
    assert np.array_equal(s, fp.placebo_shifts(["a", "b", "c"]))
    assert s.min() >= 14 and s.max() <= 153 - 14
    for row in s[:20]:
        for g in row:
            d = pd.Timestamp("2025-07-01")
            gap = abs((fp.shifted_day(d, int(g)) - d).days)
            assert min(gap, 153 - gap) >= 14


def test_placebo_pass_needs_more_than_the_190th_of_200():
    placebo = np.arange(200) / 1000.0           # 0.000 ... 0.199; the 190th is 0.189
    assert not fp.placebo_passes(0.189, placebo)
    assert fp.placebo_passes(0.1891, placebo)


# ---- margins and labels -----------------------------------------------------------------------------------------
def test_margins_come_from_predictions_alone():
    ref = np.array([0.05, 0.20, 0.30, 0.60])
    cand_ = np.array([0.05, 0.28, 0.20, 0.60])
    m = fp.margins(ref, cand_)
    assert m["mean_sq_change"] == pytest.approx((0.08 ** 2 + 0.1 ** 2) / 4)
    assert m["B"] == pytest.approx(max(0.001, m["mean_sq_change"] / 2)) and m["H"] == pytest.approx(m["B"] / 2)
    assert m["moved_band_share"] == pytest.approx(0.5) and m["moved_warn_share"] == pytest.approx(0.5)
    same = fp.margins(ref, ref)
    assert same["B"] == fp.B_FLOOR and same["H"] == fp.B_FLOOR / 2
    import inspect
    assert list(inspect.signature(fp.margins).parameters) == ["p_ref", "p_cand"]   # no outcome goes in


@pytest.mark.parametrize("d,lo,hi,sec,want", [
    (0.004, 0.001, 0.007, False, "Better"),
    (0.002, 0.001, 0.0029, False, "No useful difference"),  # interval above 0 but d < B and hi < B
    (0.002, 0.001, 0.003, False, "Too uncertain"),          # lo > 0, d < B <= hi: no label fits
    (0.002, -0.0005, 0.005, False, "Promising, not shown"),
    (0.002, -0.0005, 0.005, True, "Too uncertain"),         # blocked by a secondary, hi >= B
    (0.001, -0.0005, 0.0025, True, "No useful difference"),
    (-0.0005, -0.0009, 0.0002, False, "No useful difference"),
    (-0.002, -0.004, -0.0005, False, "Possible harm"),      # "Harm" is never reached first
    (-0.0003, -0.0012, 0.004, False, "Possible harm"),
    (0.0005, -0.002, 0.0028, False, "Too uncertain"),       # d > 0, lo <= -H, hi < B: no label fits
    (0.0005, -0.002, 0.004, False, "Too uncertain"),
])
def test_labels_follow_the_framework_order(d, lo, hi, sec, want):
    assert fp.label(d, lo, hi, B=0.003, H=0.001, secondary_harm=sec) == want


def test_h_may_not_exceed_b():
    with pytest.raises(ValueError):
        fp.label(0.0, -0.1, 0.1, B=0.001, H=0.002)


def test_gate_counts_rows_sites_and_events_with_a_factor():
    has = np.array([True] * 70 + [False] * 30)
    site = np.array([f"s{i % 12}" for i in range(100)])
    ex = np.zeros(100, bool); ex[:30] = True
    g = fp.gate(has, site, ex)
    assert g["share"] == 0.7 and g["sites_with_factor"] == 12 and g["events_with_factor"] == 30 and g["passes"]
    ex[29] = False
    assert not fp.gate(has, site, ex)["passes"]
    assert not fp.gate(np.array([True] * 59 + [False] * 41), site, np.ones(100, bool))["passes"]


# ---- the capped EA client ---------------------------------------------------------------------------------------
def client(tmp_path, handler, fetch=True, cap=3):
    sleeps = []
    c = ff.CappedClient(tmp_path, fetch, max_requests=cap, transport=httpx.MockTransport(handler), sleep=sleeps.append)
    return c, sleeps


def test_client_caps_pauses_caches_and_logs(tmp_path):
    seen = []

    def ok(req):
        seen.append(str(req.url))
        return httpx.Response(200, json={"items": [len(seen)]})
    c, sleeps = client(tmp_path, ok)
    for i in range(3):
        c.get_json(f"{ff.HY}/id/stations.json", {"page": i})
    assert c.get_json(f"{ff.HY}/id/stations.json", {"page": 0}) == {"items": [1]}   # cached: not counted
    assert c.n == 3 and sleeps == [ff.PAUSE_S, ff.PAUSE_S]
    with pytest.raises(ff.CapReached):
        c.get_json(f"{ff.HY}/id/stations.json", {"page": 9})
    assert len((tmp_path / "requests.log").read_text().splitlines()) == 3


@pytest.mark.parametrize("status", [403, 429, 500, 503, 301])
def test_client_stops_at_refusals_errors_and_redirects(tmp_path, status):
    c, _ = client(tmp_path, lambda req: httpx.Response(status, headers={"location": "https://x.example/"}))
    with pytest.raises(SystemExit):
        c.get_json(f"{ff.HY}/id/stations.json")
    assert not [p for p in tmp_path.iterdir() if p.name != "requests.log"]


def test_client_refuses_other_hosts_and_misses_without_fetch(tmp_path):
    c, _ = client(tmp_path, lambda req: httpx.Response(200, json={}))
    for url in ("https://api.open-meteo.com/v1/forecast", "http://environment.data.gov.uk/hydrology/id/stations"):
        with pytest.raises(SystemExit):
            c.get_json(url)
    assert c.n == 0
    c2, _ = client(tmp_path, lambda req: httpx.Response(200, json={}), fetch=False)
    with pytest.raises(SystemExit):
        c2.get_json(f"{ff.HY}/id/stations.json")
    assert c2.n == 0


def test_measure_ids_from_station_metadata():
    st = {"measures": [{"@id": "http://environment.data.gov.uk/hydrology/id/measures/abc-flow-m-86400-m3s-qualified"},
                       {"@id": "http://environment.data.gov.uk/hydrology/id/measures/abc-flow-i-900-m3s-qualified"},
                       {"@id": "http://environment.data.gov.uk/hydrology/id/measures/abc-level-i-900-m-qualified"}]}
    assert ff.measure_ids(st) == {"daily": "abc-flow-m-86400-m3s-qualified", "q15": "abc-flow-i-900-m3s-qualified"}
    assert ff.measure_ids({}) == {"daily": None, "q15": None}
