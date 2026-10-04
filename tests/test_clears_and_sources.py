"""Right now's risk with travel time (transport.live_now_risk), when water still on its way arrives
(still_coming, forecast.arriving_of), when a spot should be back at low risk after a spill (clear_time),
and which overflows a risk comes from (risk_shares, spread_count, forecast.source_of): the fields behind
the page's "Where the risk comes from" (index.html, whereFrom)."""

import math

import numpy as np
import pandas as pd

from dipcast.model.transport import (
    LOW_CUT,
    clear_time,
    daily_effects,
    live_now_risk,
    risk_shares,
    spread_count,
    still_coming,
)

NOW = pd.Timestamp("2026-10-04 00:16", tz="Europe/London")


def _ov(weights, status, ended_h_ago, travel_h=None, started_h_ago=None) -> pd.DataFrame:
    """Upstream overflows as upstream_overflows gives them, with live status: `ended_h_ago` is the
    hours since each one's latest spill ended (None: never, or still running), `started_h_ago` since
    it started (None: not given)."""
    at = lambda hs: [pd.NaT if h is None else (NOW - pd.Timedelta(hours=h)).tz_convert("UTC") for h in hs]
    return pd.DataFrame({"weight": weights, "status": status, "latest_event_end": at(ended_h_ago),
                         "latest_event_start": at(started_h_ago or [None] * len(weights)),
                         "travel_h": [0.0] * len(weights) if travel_h is None else travel_h})


def _no_travel(ov: pd.DataFrame) -> pd.DataFrame:
    """The same spills as if each one's water passed the spot the moment it stopped: the rule before 4 Oct 2026."""
    return ov.assign(travel_h=0.0)


def test_a_spill_counts_in_full_until_its_water_has_passed():
    """Ended 10 h ago, 20 h upstream: its water is still passing, so it counts in full. Before 4 Oct 2026
    it had died off for 10 h already (10^(-10/30) of its weight)."""
    ov = _ov([0.6], [0], [10.0], travel_h=[20.0])
    assert live_now_risk(ov, NOW)[0] == 0.6
    assert abs(live_now_risk(_no_travel(ov), NOW)[0] - 0.6 * 10 ** (-10 / 30)) < 1e-12
    # Its water passed 5 h ago: dying off from then, not from its end.
    assert abs(live_now_risk(_ov([0.6], [0], [25.0], travel_h=[20.0]), NOW)[0] - 0.6 * 10 ** (-5 / 30)) < 1e-12
    # The 48 h run from when its water passed: ended 60 h ago, 30 h upstream, it still counts (30 h after),
    # and ended 79 h ago it does not (49 h after).
    assert abs(live_now_risk(_ov([1.0], [0], [60.0], travel_h=[30.0]), NOW)[0] - 0.1) < 1e-12
    assert live_now_risk(_ov([1.0], [0], [79.0], travel_h=[30.0]), NOW)[0] == 0.0


def test_a_spill_whose_water_has_not_arrived_counts_from_its_start():
    """Running for an hour, 5 h upstream: its water is 4 h off, but it counts in full now, as before:
    a level that waited for it read "Low risk for the next five days" with sewage on its way. still_coming
    gives the hours until it arrives, for the page to say."""
    ov = _ov([0.5, 0.4, 0.3, 0.2], [1, 1, 0, 0], [None, None, 2.0, 70.0], travel_h=[5.0, 0.5, 6.0, 1.0],
             started_h_ago=[1.0, 3.0, 3.0, 72.0])
    _, contrib = live_now_risk(ov, NOW)
    assert np.allclose(contrib, [0.5, 0.4, 0.3, 0.0])
    left = still_coming(ov, NOW, contrib)
    # 4 h for the first; the second has arrived; the third (stopped 2 h ago, 6 h away) is 3 h off; the
    # fourth does not count. No start time: taken to have arrived.
    assert np.allclose(left[[0, 2]], [4.0, 3.0]) and np.isnan(left[[1, 3]]).all()
    assert np.isnan(still_coming(ov.assign(latest_event_start=pd.NaT), NOW, contrib)).all()


def test_with_no_travel_time_the_rule_is_the_one_before():
    """Running, finished 3, 20, 47 and 60 h ago, never, and a feed that is down (its last finished
    spill still counts): with no travel time, the weights of the rule before 4 Oct 2026."""
    ov = _ov([0.9, 0.6, 0.8, 0.5, 0.5, 0.7, 0.4], [1, 0, 0, 0, 0, -3, 0], [None, 3.0, 20.0, 47.0, 60.0, 10.0, None])
    want = [0.9, 0.6 * 10 ** (-3 / 30), 0.8 * 10 ** (-20 / 30), 0.5 * 10 ** (-47 / 30), 0.0, 0.7 * 10 ** (-10 / 30), 0.0]
    assert np.allclose(live_now_risk(ov, NOW)[1], want)


def _risk_at(ov: pd.DataFrame, t: pd.Timestamp) -> float:
    """live_now_risk at a later time t, with every spill running at NOW stopped at NOW."""
    stopped = ov.copy()
    running = stopped["status"] == 1
    stopped.loc[running, "status"] = 0
    stopped.loc[running, "latest_event_end"] = NOW.tz_convert("UTC")
    return live_now_risk(stopped, t)[0]


def test_one_running_spill_falls_to_low_by_die_off():
    at, by, who = clear_time(_ov([1.0], [1], [None]), NOW)
    want = 30.0 * math.log10(1.0 / LOW_CUT)   # weight x 10^(-t / T90) = cut, with T90 = 30 h
    assert (by, who) == ("die-off", None)
    assert abs((at - NOW) / pd.Timedelta(hours=1) - want) < 1 / 600   # within six seconds


def test_the_clear_time_is_live_now_risk_run_forward():
    """The same computation as right now's risk, later: just before the time it is still moderate,
    just after it is low. Running, finished, long finished, never spilled and a feed that is down
    (its last finished spill still counts, as in live_now_risk); with no travel time and with some."""
    ov = _ov([0.9, 0.6, 0.8, 0.5, 0.7, 0.4], [1, 0, 0, 0, -3, 0], [None, 3.0, 20.0, 60.0, 10.0, None])
    minute = pd.Timedelta(minutes=1)
    for travel in ([0.0] * 6, [2.0, 30.0, 5.0, 20.0, 1.0, 9.0]):
        o = ov.assign(travel_h=travel)
        assert live_now_risk(o, NOW)[0] >= LOW_CUT
        at, _, _ = clear_time(o, NOW)
        assert _risk_at(o, at - minute) >= LOW_CUT > _risk_at(o, at + minute)
        assert NOW < at < NOW + pd.Timedelta(hours=100)
    assert clear_time(ov, NOW)[1] == "die-off"


def test_the_48_hour_window_can_set_the_time():
    """Ten full-weight spills that ended 47 h ago add up to moderate (each 10^(-47/30), about 0.027),
    and stop counting together an hour from now: the window, not die-off, brings it to low."""
    ov = _ov([1.0] * 10, [0] * 10, [47.0] * 10)
    assert live_now_risk(ov, NOW)[0] >= LOW_CUT
    at, by, _ = clear_time(ov, NOW)
    assert by == "window"
    assert abs((at - NOW) / pd.Timedelta(hours=1) - 1.0) < 1e-6
    assert _risk_at(ov, at - pd.Timedelta(minutes=1)) >= LOW_CUT > _risk_at(ov, at + pd.Timedelta(minutes=1))


def test_no_clear_time_when_already_low():
    assert clear_time(_ov([0.1], [1], [None]), NOW) == (None, None, None)       # running, but little reaches here
    assert clear_time(_ov([1.0], [0], [49.0]), NOW) == (None, None, None)       # past the window
    assert clear_time(_ov([], [], []), NOW) == (None, None, None)


def _held_risk(ov: pd.DataFrame, t: float, recent_h: float = 48.0, t90_h: float = 30.0) -> float:
    """clear_time's risk t hours from NOW, written out plainly: each spill live_now_risk counts at NOW
    at its full weight until its water has passed (its end, or NOW if running, plus its travel time),
    then dying off with T90, out of the count recent_h after its water passed."""
    risk_free = 1.0
    for _, r in ov.iterrows():
        ended = 0.0 if r["status"] == 1 else (NOW - r["latest_event_end"]) / pd.Timedelta(hours=1)
        if r["status"] != 1 and not (ended >= 0 and ended - r["travel_h"] <= recent_h):
            continue
        age = t + ended - r["travel_h"]   # hours since its water passed
        c = r["weight"] if age <= 0 else r["weight"] * 10 ** (-age / t90_h) if age <= recent_h else 0.0
        risk_free *= 1 - c
    return 1 - risk_free


def _hours(at: pd.Timestamp) -> float:
    return (at - NOW) / pd.Timedelta(hours=1)


def test_a_tiny_far_spill_barely_moves_the_time_and_is_not_named():
    """A near spill that ended an hour ago (weight 0.5) and a tiny far one running now (0.01, 30 h
    away). Held at its full weight until its water has passed, the far one adds 0.01: the risk is
    under low about an hour after it would be with no travel time, by die-off, long before the 30 h."""
    ov = _ov([0.5, 0.01], [0, 1], [1.0, None], travel_h=[0.5, 30.0])
    model, _, _ = clear_time(_no_travel(ov), NOW)
    at, by, who = clear_time(ov, NOW)
    assert (by, who) == ("die-off", None)
    want = 30 * math.log10(0.5 / (1 - (1 - LOW_CUT) / 0.99)) - 0.5   # near alone under 1 - 0.85 / 0.99
    assert abs(_hours(at) - want) < 1 / 600 and 0 < _hours(at) - _hours(model) < 1.5 and _hours(at) < 20
    assert _held_risk(ov, _hours(at) - 1 / 60) >= LOW_CUT > _held_risk(ov, _hours(at) + 1 / 60)


def test_a_big_far_spill_holds_the_time_up_and_is_named():
    """The same near spill and a big far one running now (0.3, 30 h away). With no travel time the
    risk is under low in about 21 h; with the far water still on its way, it is held at 0.3 until 30 h
    from now and dies off from there, under low about 41 h from now. Travel time holds nearly all of
    the risk as it clears, so 'travel', naming the far overflow."""
    ov = _ov([0.5, 0.3], [0, 1], [1.0, None], travel_h=[0.5, 30.0])
    model, by, _ = clear_time(_no_travel(ov), NOW)
    assert by == "die-off" and 20 < _hours(model) < 22
    at, by, who = clear_time(ov, NOW)
    assert (by, who) == ("travel", 1) and 40 < _hours(at) < 42
    assert _held_risk(ov, _hours(at) - 1 / 60) >= LOW_CUT > _held_risk(ov, _hours(at) + 1 / 60)
    # The headline's risk holds each spill until its water has passed too: the near one's passed half an hour ago.
    assert abs(live_now_risk(ov, NOW)[0] - (1 - (1 - 0.5 * 10 ** (-0.5 / 30)) * (1 - 0.3))) < 1e-12


def test_the_time_said_is_never_before_the_models():
    """Each spill's part with travel time is at least its part without at every moment, so the time
    can only be later; with no travel time, window or die-off and no one named. A finished far spill
    counts from when its water passed: it ended 10 h ago, 30 h away, so it is held until 20 h from now.
    One that ended 60 h ago, 40 h away, counts too: its water passed 20 h ago."""
    cases = [_ov([0.9, 0.6, 0.8, 0.5, 0.7, 0.4], [1, 0, 0, 0, -3, 0], [None, 3.0, 20.0, 60.0, 10.0, None]),
             _ov([1.0] * 10, [0] * 10, [47.0] * 10), _ov([1.0], [1], [None])]
    for ov in cases:
        model, by, who = clear_time(ov, NOW)
        assert by in ("window", "die-off") and who is None
        later, _, _ = clear_time(ov.assign(travel_h=np.linspace(1.0, 25.0, len(ov))), NOW)
        assert later > model
    ov = _ov([0.5, 0.4, 0.9], [0, 0, 0], [1.0, 10.0, 60.0], travel_h=[0.5, 30.0, 40.0])
    assert live_now_risk(ov, NOW)[1][2] > 0
    at, by, who = clear_time(ov, NOW)
    assert (by, who) == ("travel", 1) and _hours(at) > 20
    assert _held_risk(ov, _hours(at) - 1 / 60) >= LOW_CUT > _held_risk(ov, _hours(at) + 1 / 60)
    # Low now: nothing to say, however far away the spill.
    assert clear_time(_ov([0.1], [1], [None], travel_h=[30.0]), NOW) == (None, None, None)
    assert clear_time(_ov([], [], [], travel_h=[]), NOW) == (None, None, None)


def test_shares_split_the_combined_risk_exactly():
    assert np.allclose(risk_shares(np.array([0.5, 0.5])), [0.5, 0.5])
    s = risk_shares(np.array([0.9, 0.1]))
    assert abs(s.sum() - 1) < 1e-12 and s[0] > 0.9   # -ln(0.1) against -ln(0.9): 0.956
    small = np.array([0.002, 0.001, 0.001])
    assert np.allclose(risk_shares(small), small / small.sum(), atol=1e-3)   # small terms: their part of the sum
    # Per day, as combine_daily's terms: a day with no risk has no shares.
    eff = daily_effects(np.array([[1.0, 0.0, 0.0], [0.5, 0.0, 0.0]]), np.array([0.4, 0.4]), np.array([0.0, 24.0]))
    sh = risk_shares(eff)
    assert np.allclose(sh[:, 0], [1, 0]) and np.allclose(sh[:, 1], [0, 1]) and np.allclose(sh[:, 2], 0)


def test_spread_is_how_many_make_up_nine_tenths():
    assert spread_count(np.array([0.6, 0.3, 0.1])) == 2
    assert spread_count(np.array([0.25, 0.25, 0.25, 0.25])) == 4
    assert spread_count(np.array([0.45, 0.45] + [0.001] * 100)) == 2
    assert spread_count(np.array([0.3] + [0.007] * 100)) == 87   # 0.3 and 86 slivers make 0.902
    assert spread_count(np.zeros(3)) == 0


def _upstream() -> pd.DataFrame:
    """Two monitored overflows upstream of a river spot: the near one discharging now. Times are from
    the clock, as forecast_point's are."""
    return pd.DataFrame({
        "site_id": ["A1", "B2"], "company": "Yorkshire Water", "site_name": ["ILKLEY WwTW", "Burley CSO"],
        "receiving_watercourse": "River Wharfe", "lat": [53.93, 53.91], "lon": [-1.82, -1.75],
        "status": [1, 0], "has_live": True, "latest_event_start": pd.NaT,
        "latest_event_end": [pd.NaT, pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=6)],
        "lta_spills": [200.0, 120.0], "spill_hours": 100.0, "edm_operational_pct": 95.0, "snap_confidence": "high",
        "distance_m": [6000.0, 9000.0], "lake_distance_m": 0.0, "travel_h": [3.3, 5.0], "weight": [0.8, 0.6]})


class _Steady:
    """A spill model that gives each overflow the same chance every day."""
    trained_on = "test"

    def __init__(self, a1: float = 0.55, b2: float = 0.33):
        self.a1, self.b2 = a1, b2

    def predict(self, sd: pd.DataFrame) -> np.ndarray:
        return np.where(sd["site_id"] == "A1", self.a1, self.b2)


def _forecast(monkeypatch, ov: pd.DataFrame, model: _Steady) -> dict:
    """forecast_point for a river spot with `ov` upstream, offline: no network, rain or calibration."""
    from dipcast.model import forecast
    from dipcast.model.transport import PinLocation

    def rain(cells):
        t = pd.date_range(pd.Timestamp.now(tz="UTC").floor("D") - pd.Timedelta(days=4), periods=24 * 12, freq="h")
        return pd.concat([pd.DataFrame({"cell_lat": a, "cell_lon": b, "time": t, "precip_mm": 0.4}) for a, b in cells],
                         ignore_index=True)

    monkeypatch.setattr(forecast, "_net", lambda: None)
    monkeypatch.setattr(forecast, "_overflows", lambda: ov)
    monkeypatch.setattr(forecast, "_model", lambda: model)
    monkeypatch.setattr(forecast, "_lead_calibration", lambda: {})
    monkeypatch.setattr(forecast, "locate_pin", lambda *a, **k: PinLocation(mode="river", x=0.0, y=0.0, snap=None,
                                                                             watercourse="River Wharfe"))
    monkeypatch.setattr(forecast, "upstream_overflows", lambda *a, **k: ov.copy())
    monkeypatch.setattr(forecast, "fetch_forecast", rain)
    monkeypatch.setattr(forecast.ecoli, "load", lambda: None)
    return forecast.forecast_point(53.92, -1.70, days_ahead=4, gauge=False, log_to_store=False)


def test_forecast_point_writes_the_clear_time_and_the_sources(monkeypatch):
    out = _forecast(monkeypatch, _upstream(), _Steady())
    now = out["now"]
    assert now["label"] != "low" and now["clears_by"] == "die-off"
    issued = pd.Timestamp(out["query"]["issued_at"])
    assert issued < pd.Timestamp(now["clears_at"]) < issued + pd.Timedelta(hours=48)
    # Right now, the running spill at the nearer, bigger overflow holds most of the risk.
    src = now["source"]
    assert src["site_id"] == "A1" and src["status"] == 1 and src["share"] > 0.5 and src["spread_over"] == 2
    assert (src["distance_km"], src["travel_h"], src["site_name"], src["receiving_watercourse"]) == (6.0, 3.3, "ILKLEY WwTW", "River Wharfe")
    # 0.8 x 0.55 and 0.6 x 0.33 every day: 0.55 combined, and A1 holds about seven tenths of it.
    for k, d in enumerate(out["days"]):
        assert d["risk"] >= LOW_CUT and d["source"]["site_id"] == "A1" and d["source"]["spread_over"] == 2
        assert abs(d["source"]["share"] - math.log(1 - 0.44) / math.log((1 - 0.44) * (1 - 0.198))) < 0.002
        # Spills on the days after today alone: none reach today, and every later day has some.
        assert (d["risk_from_later_spills"] == 0) if k == 0 else (0 < d["risk_from_later_spills"] <= d["risk"])


def test_forecast_point_names_the_overflow_whose_travel_holds_the_time_up(monkeypatch):
    # The near overflow finished an hour ago; the far one, 30 h away and weight 0.6, is discharging now.
    ov = _upstream().assign(status=[0, 1], travel_h=[3.3, 30.0],
                            latest_event_end=[pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=1), pd.NaT])
    out = _forecast(monkeypatch, ov, _Steady())
    now = out["now"]
    assert now["clears_by"] == "travel" and now["clears_after"] == {"site_id": "B2", "site_name": "Burley CSO", "travel_h": 30.0}
    # Held at 0.6 until its water has passed at 30 h, then dying off: under 0.15 about 50 h from now.
    issued = pd.Timestamp(out["query"]["issued_at"])
    assert 48 < (pd.Timestamp(now["clears_at"]) - issued) / pd.Timedelta(hours=1) < 52


def test_forecast_point_says_when_water_still_on_its_way_arrives(monkeypatch):
    # The near overflow started discharging an hour ago, 3.3 h upstream: its water is 2.3 h off. It holds
    # about two thirds of right now's risk, which counts it in full already.
    start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=1)
    out = _forecast(monkeypatch, _upstream().assign(latest_event_start=[start, pd.NaT]), _Steady())
    a, issued = out["now"]["arriving"], pd.Timestamp(out["query"]["issued_at"])
    assert (a["site_id"], a["site_name"], a["status"], a["distance_km"], a["travel_h"]) == ("A1", "ILKLEY WwTW", 1, 6.0, 3.3)
    assert 0.6 < a["share"] < 0.7
    assert abs((pd.Timestamp(a["arrives_at"]) - issued) / pd.Timedelta(hours=1) - 2.3) < 0.02
    assert out["now"]["label"] != "low" and out["now"]["source"]["site_id"] == "A1"
    # Its water has arrived, or the spill on its way holds under half the risk: nothing to say.
    out = _forecast(monkeypatch, _upstream().assign(latest_event_start=[start - pd.Timedelta(hours=3), pd.NaT]), _Steady())
    assert "arriving" not in out["now"]
    far = _upstream().assign(weight=[0.1, 0.6], latest_event_start=[start, pd.NaT])
    assert "arriving" not in _forecast(monkeypatch, far, _Steady())["now"]


def test_a_quiet_low_spot_gets_no_clear_time_and_no_sources(monkeypatch):
    ov = _upstream().assign(status=0, latest_event_end=pd.NaT)
    out = _forecast(monkeypatch, ov, _Steady(0.01, 0.01))
    assert out["now"]["clears_at"] is None and out["now"]["clears_by"] is None and "source" not in out["now"]
    assert "clears_after" not in out["now"] and "arriving" not in out["now"]
    assert all(d["risk"] < LOW_CUT and "source" not in d for d in out["days"])
