"""The EA gauge lookup behind the river level index. The station list links each stage
scale as http://, which answers 301 to https://; until 29 Sep 2026 that redirect made
every linked scale fail and the index went missing (seen near Pangbourne: station
2180TH, the Pang at Tidmarsh). Then the words beside the pollution level that come from
the gauges and the EA's flood alerts: "high", "rising fast" and the alerts in force."""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from dipcast.ingest import flows

EA = "environment.data.gov.uk"
REF = "2180TH"


def _fake_ea(monkeypatch, stage_scale: str) -> list[str]:
    """Route flows' httpx.get through a real httpx client on a mock transport, so
    redirects behave as they do live (not followed unless asked). Returns the URLs asked for."""
    asked = []

    def handler(req: httpx.Request) -> httpx.Response:
        asked.append(str(req.url))
        path = req.url.path
        if req.url.host != EA:
            return httpx.Response(404)
        if req.url.scheme == "http":   # what the live service does with every http:// link
            return httpx.Response(301, headers={"Location": str(req.url.copy_with(scheme="https"))})
        if path == "/flood-monitoring/id/stations":
            return httpx.Response(200, json={"items": [{
                "stationReference": REF, "label": "Tidmarsh", "riverName": "River Pang",
                "lat": 51.4856, "long": -1.0913, "stageScale": stage_scale}]})
        if path == f"/flood-monitoring/id/stations/{REF}/stageScale":
            return httpx.Response(200, json={"items": {"typicalRangeLow": 1.072, "typicalRangeHigh": 1.56}})
        if path == f"/flood-monitoring/id/stations/{REF}/readings":
            return httpx.Response(200, json={"items": [{
                "measure": f"https://{EA}/flood-monitoring/id/measures/{REF}-level-stage-i-15_min-mASD",
                "value": 1.316, "dateTime": "2026-09-29T09:00:00Z"}]})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(flows.httpx, "get", lambda url, **kw: client.get(url, **kw))
    return asked


def test_http_stage_scale_link_is_fetched_over_https(monkeypatch):
    asked = _fake_ea(monkeypatch, f"http://{EA}/flood-monitoring/id/stations/{REF}/stageScale")
    st = flows._nearest_level_station(51.4856, -1.0913)
    assert st is not None
    assert (st.typical_low, st.typical_high) == (1.072, 1.56)
    assert st.index == pytest.approx((1.316 - 1.072) / (1.56 - 1.072))
    assert st.label == "normal"
    assert any(u.startswith(f"https://{EA}/flood-monitoring/id/stations/{REF}/stageScale") for u in asked)


def test_stage_scale_link_off_the_ea_host_is_not_fetched(monkeypatch):
    asked = _fake_ea(monkeypatch, f"http://example.com/flood-monitoring/id/stations/{REF}/stageScale")
    st = flows._nearest_level_station(51.4856, -1.0913)
    assert st is not None and st.level_m == 1.316   # the reading still comes through
    assert st.typical_low is None and st.index is None
    assert not any("example.com" in u for u in asked)


def test_ea_link():
    path = f"/flood-monitoring/id/stations/{REF}/stageScale"
    assert flows._ea_link(f"http://{EA}{path}") == f"https://{EA}{path}"
    assert flows._ea_link(f"https://{EA}{path}") == f"https://{EA}{path}"
    assert flows._ea_link(f"http://{EA}.evil.example{path}") is None
    assert flows._ea_link(f"ftp://{EA}{path}") is None


def test_the_latest_reading_names_its_measure_for_the_trend(monkeypatch):
    _fake_ea(monkeypatch, f"https://{EA}/flood-monitoring/id/stations/{REF}/stageScale")
    st = flows._nearest_level_station(51.4856, -1.0913)
    assert st.measure == f"{REF}-level-stage-i-15_min-mASD"


# ------------------------------------------------------------------------------ too high to swim
# The words beside the pollution level (roadmap task 8): "high" above the gauge's usual range,
# "rising fast" up more than a fifth of that range in six hours, both only from a gauge on the
# spot's own river and a current reading; and the EA's flood alerts and warnings in force.
NOW = datetime(2026, 10, 3, 13, 30, tzinfo=UTC)


def _build_site():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_site
    return build_site


def test_flow_state_word_rules():
    assert flows.flow_state(1.01, True, None) == "high"
    assert flows.flow_state(1.0, True, None) is None            # at the top of the usual range, not above it
    assert flows.flow_state(0.5, True, 0.21) == "rising fast"
    assert flows.flow_state(0.5, True, 0.2) is None             # more than a fifth, not a fifth
    assert flows.flow_state(1.4, True, 0.5) == "high"           # above the range says more than rising
    assert flows.flow_state(0.5, True, -0.4) is None            # falling
    for other in (False, None):                                 # a tributary's gauge, or a lake's: not this river
        assert flows.flow_state(1.5, other, 0.5) is None
    assert flows.flow_state(None, True, None) is None           # a stale reading has no index
    assert flows.flow_state(None, True, 0.3) == "rising fast"   # no range position, but a rise in the last six hours


def _readings(start: datetime, values: list[float], step_min: int = 15) -> list[tuple[str, float]]:
    """Readings from `start`, `step_min` apart, newest first as the API sorts them."""
    pts = [((start + timedelta(minutes=step_min * i)).isoformat().replace("+00:00", "Z"), v) for i, v in enumerate(values)]
    return pts[::-1]


def test_the_rise_counts_only_the_last_six_hours():
    six = _readings(NOW - timedelta(hours=5, minutes=45), [0.30 + 0.02 * i for i in range(24)])   # 24 readings, 15 min apart
    assert flows.rise_over_window(six, NOW) == {"rise_m": 0.46, "from": "2026-10-03T07:45:00Z", "to": "2026-10-03T13:30:00Z"}
    # Readings from before the window do not count: a rise yesterday is not rising now.
    assert flows.rise_over_window(_readings(NOW - timedelta(hours=30), [0.3, 0.9, 1.5, 2.0]), NOW) is None
    # Two readings 15 minutes apart are too short a span to call a trend.
    assert flows.rise_over_window(_readings(NOW - timedelta(minutes=15), [0.3, 0.9]), NOW) is None
    assert flows.rise_over_window([], NOW) is None
    # A falling river rises by a negative amount; an unreadable time is skipped.
    fall = _readings(NOW - timedelta(hours=2), [1.0, 0.9, 0.8], step_min=60) + [("not a time", 5.0)]
    assert flows.rise_over_window(fall, NOW)["rise_m"] == -0.2


def _fake_ea_paths(monkeypatch, routes: dict) -> list[httpx.Request]:
    """The EA host over https only, answering the given paths; anything else is a 404."""
    asked = []

    def handler(req: httpx.Request) -> httpx.Response:
        asked.append(req)
        if req.url.host != EA or req.url.scheme != "https" or req.url.path not in routes:
            return httpx.Response(404)
        return httpx.Response(200, json=routes[req.url.path])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(flows.httpx, "get", lambda url, **kw: client.get(url, **kw))
    return asked


def test_recent_levels_reads_one_measure_newest_first(monkeypatch):
    m = "F1903-level-stage-i-15_min-m"
    asked = _fake_ea_paths(monkeypatch, {f"/flood-monitoring/id/measures/{m}/readings": {"items": [
        {"dateTime": "2026-10-03T13:15:00Z", "value": 0.339}, {"dateTime": "2026-10-03T13:00:00Z", "value": "bad"},
        {"dateTime": "2026-10-03T12:45:00Z", "value": 0.339}]}})
    assert flows.recent_levels(m) == [("2026-10-03T13:15:00Z", 0.339), ("2026-10-03T12:45:00Z", 0.339)]
    assert asked[0].url.params["_limit"] == "24" and "_sorted" in asked[0].url.params
    with pytest.raises(ValueError):
        flows.recent_levels("../stations/x")   # never a path out of the measures


# A response as the live service gives it (3 Oct 2026 it held one item, 011WAFED at severity 4).
FLOODS = {"items": [
    {"floodAreaID": "123WAF456", "description": "River Wharfe at Ilkley", "severityLevel": 3, "severity": "Flood alert",
     "timeRaised": "2026-10-03T09:20:22"},
    {"floodAreaID": "123FWF789", "description": "River Wharfe at Burley", "severityLevel": 2, "severity": "Flood warning"},
    {"floodAreaID": "011WAFED", "description": "Rivers Ehen, Calder, Irt and Esk", "severityLevel": 4,
     "severity": "Warning no longer in force"},
    {"floodAreaID": "bad id/../x", "description": "Odd", "severityLevel": 3},
    {"floodAreaID": "X", "severityLevel": None}]}


def test_flood_alerts_in_force_most_severe_first(monkeypatch):
    asked = _fake_ea_paths(monkeypatch, {"/flood-monitoring/id/floods": FLOODS})
    found = flows.flood_alerts(53.925, -1.82)
    assert [(a["severity_level"], a["severity"], a["area"]) for a in found] == [
        (2, "Flood warning", "River Wharfe at Burley"), (3, "Flood alert", "River Wharfe at Ilkley"), (3, "Flood alert", "Odd")]
    assert found[0]["url"] == "https://check-for-flooding.service.gov.uk/target-area/123FWF789"
    assert found[2]["url"] is None and found[2]["area_id"] is None   # an id that is not one makes no link
    assert dict(asked[0].url.params) == {"lat": "53.925", "long": "-1.82", "dist": "10"}
    assert "011WAFED" not in str(found)   # "no longer in force" is never shown as in force


def test_a_failed_flood_lookup_raises_so_none_and_unchecked_differ(monkeypatch):
    _fake_ea_paths(monkeypatch, {})
    with pytest.raises(httpx.HTTPError):
        flows.flood_alerts(53.9, -1.8)


def _state(level: float, observed: datetime, river: str = "River Wharfe") -> flows.RiverState:
    return flows.RiverState(station="Addingham", river=river, lat=53.94, lon=-1.88, level_m=level, typical_low=0.189,
                            typical_high=1.87, observed_at=observed.isoformat().replace("+00:00", "Z"), rloi="8001",
                            measure="F1903-level-stage-i-15_min-m")


class _Clock:
    """time.monotonic and time.sleep for the flood retries, without waiting: sleeping moves the clock."""

    def __init__(self, t: float = 1000.0):
        self.t, self.slept = t, []

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


def test_attach_flow_state_words_and_flood_alerts():
    """A river above its usual range, one rising fast, one high at a gauge on a tributary, a stale
    reading that was high, a lake under a live flood alert, and a spot where the EA did not answer."""
    bs = _build_site()
    states = {"high": _state(2.1, NOW - timedelta(minutes=20)),            # index 1.14
              "rising": _state(0.6, NOW - timedelta(minutes=15)),          # index 0.24, up 0.40 m in six hours
              "tributary": _state(2.1, NOW - timedelta(minutes=20), river="Town Beck"),
              "stale": _state(2.1, NOW - timedelta(hours=30)),
              "lake": None, "down": None}
    spots = [{"id": k, "name": k, "lat": 53.9 + i / 100, "lon": -1.8, "river": "River Wharfe"} for i, k in enumerate(states)]
    spots[4].update(river=None, kind="lake", location={"watercourse": "Windermere (N Basin)"})
    at = {s["lat"]: states[s["id"]] for s in spots}
    bs.attach_river_levels(spots, lookup=lambda lat, lon, dist, river: at[lat], workers=1, now=NOW)
    asked_trend = []

    def trend(measure):
        asked_trend.append(measure)
        return _readings(NOW - timedelta(hours=5, minutes=45), [0.2 + 0.4 * i / 23 for i in range(24)])   # 0.40 m of a 1.68 m range

    def alerts(lat, lon, timeout=None):
        if lat == spots[5]["lat"]:
            raise httpx.ConnectTimeout("EA timed out")   # and again when asked again
        if lat == spots[4]["lat"]:
            return [{"severity_level": 3, "severity": "Flood alert", "area": "Windermere and the Rothay", "area_id": "123WAF456",
                     "url": "https://check-for-flooding.service.gov.uk/target-area/123WAF456", "raised": None,
                     "waters": ["Windermere", "River Rothay"]}]
        return []

    clock = _Clock()
    counts = bs.attach_flow_state(spots, trend=trend, alerts=alerts, any_alerts=lambda: True, workers=1, now=NOW,
                                  sleep=clock.sleep, clock=clock)
    by = {s["id"]: s for s in spots}
    assert by["high"]["flow_state"] == "high"
    assert by["rising"]["flow_state"] == "rising fast"
    assert by["rising"]["river_state"]["rise_6h_m"] == 0.4
    assert (by["rising"]["river_state"]["rise_from"], by["rising"]["river_state"]["rise_to"]) == ("2026-10-03T07:45:00Z", "2026-10-03T13:30:00Z")
    assert by["tributary"]["flow_state"] is None   # its gauge is on Town Beck, not the Wharfe
    assert by["stale"]["river_state"]["stale"] is True and by["stale"]["flow_state"] is None   # never "high" from a stale reading
    assert by["lake"]["flow_state"] is None and by["lake"]["flood_alerts"][0]["severity"] == "Flood alert"
    assert by["down"]["flood_alerts"] is None and by["high"]["flood_alerts"] == []
    assert by["down"]["flood_alerts_other"] is None and by["high"]["flood_alerts_other"] == 0   # unchecked is never "none"
    assert counts == {"river_high": 1, "river_rising_fast": 1, "flood_alerts": 1, "flood_alerts_unchecked": 1,
                      "flood_alerts_other_water": 0, "flood_alerts_unmatched": 0}
    assert len(asked_trend) == 1   # asked only where it could set the word: current, own river, not already high
    assert all("days" not in s and "now" not in s for s in spots)   # nothing here touches the pollution level


def test_a_failed_trend_leaves_no_word_and_no_rise():
    bs = _build_site()
    spots = [{"id": "a", "name": "a", "lat": 53.9, "lon": -1.8, "river": "River Wharfe",
              "river_state": {**flows.reading_fields(_state(0.6, NOW), NOW), "same_river": True, "measure": "m"}}]

    def broken(measure):
        raise httpx.ReadTimeout("slow")

    bs.attach_flow_state(spots, trend=broken, alerts=lambda lat, lon: [], any_alerts=lambda: True, workers=1, now=NOW)
    assert spots[0]["flow_state"] is None and "rise_6h_m" not in spots[0]["river_state"]


def test_flood_alerts_are_asked_spot_by_spot_only_when_one_is_in_force_somewhere():
    bs = _build_site()
    asked = []

    def alerts(lat, lon):
        asked.append(lat)
        return []

    spots = [{"id": "a", "name": "a", "lat": 53.9, "lon": -1.8}, {"id": "b", "name": "b", "lat": 54.0, "lon": -1.9}]
    bs.attach_flow_state(spots, alerts=alerts, any_alerts=lambda: False, workers=1, now=NOW)
    assert asked == [] and [s["flood_alerts"] for s in spots] == [[], []]   # none in force in England: none here

    def refused():
        raise httpx.HTTPStatusError("403 Forbidden", request=httpx.Request("GET", f"https://{EA}/"), response=httpx.Response(403))

    counts = bs.attach_flow_state(spots, alerts=alerts, any_alerts=refused, workers=1, now=NOW)
    assert asked == [] and [s["flood_alerts"] for s in spots] == [None, None]   # unchecked, not "none"
    assert counts["flood_alerts_unchecked"] == 2

    bs.attach_flow_state(spots, alerts=alerts, any_alerts=lambda: True, workers=1, now=NOW)
    assert sorted(asked) == [53.9, 54.0]


def test_the_national_flood_list_is_asked_once_more_20_s_after_a_failure_and_all_within_30_s():
    bs = _build_site()
    clock, asked = _Clock(), []

    def flaky(timeout):
        asked.append((clock.t - 1000.0, timeout))
        clock.t += 3.0   # each ask takes 3 s
        if len(asked) == 1:
            raise httpx.ReadTimeout("The read operation timed out")
        return True

    assert bs.ask_flood_list(flaky, sleep=clock.sleep, clock=clock) is True
    assert asked == [(0.0, 10.0), (20.0, 10.0)]   # the second begins 20 s after the first; each has 10 s, so 30 s in all
    assert clock.slept == [17.0]

    clock, asked = _Clock(), []
    assert bs.ask_flood_list(lambda timeout: asked.append(timeout) or False, sleep=clock.sleep, clock=clock) is False
    assert asked == [10.0] and clock.slept == []   # an answer the first time: no retry, no wait

    def refused(timeout):
        raise httpx.HTTPStatusError("403", request=httpx.Request("GET", f"https://{EA}/"), response=httpx.Response(403))

    with pytest.raises(httpx.HTTPStatusError):   # refused twice: the build's asked_now keeps the error, and every spot is unchecked
        bs.ask_flood_list(refused, sleep=clock.sleep, clock=clock)


def test_a_spot_whose_flood_request_timed_out_is_asked_once_more_after_20_s():
    """16 Oct 2026, 21:03 build: the national list answered, then 48 of 105 spots' own requests timed
    out at 4 s and their pages said "not checked". Each is now asked again, once, after 20 s."""
    bs = _build_site()
    spots = [{"id": k, "name": k, "lat": 53.9 + i / 100, "lon": -1.8} for i, k in enumerate(("ok", "slow", "down"))]
    clock, asked = _Clock(), []

    def alerts(lat, lon, timeout=None):
        asked.append((lat, timeout, clock.t - 1000.0))
        if lat == spots[2]["lat"] or (lat == spots[1]["lat"] and timeout is None):
            raise httpx.ReadTimeout("The read operation timed out")
        return []

    counts = bs.attach_flow_state(spots, alerts=alerts, any_alerts=lambda: True, workers=1, now=NOW, sleep=clock.sleep, clock=clock)
    assert [s["flood_alerts"] for s in spots] == [[], [], None]
    assert counts["flood_alerts_unchecked"] == 1
    assert clock.slept == [20.0]   # one wait for all of them, not one a spot
    assert asked[3:] == [(53.91, 10.0, 20.0), (53.92, 10.0, 20.0)]   # only the failed ones, each with what is left of 30 s

    # Nothing failed: no wait, no second round.
    clock = _Clock()
    bs.attach_flow_state(spots, alerts=lambda lat, lon, timeout=None: [], any_alerts=lambda: True, workers=1, now=NOW,
                         sleep=clock.sleep, clock=clock)
    assert clock.slept == []


def test_the_retry_stops_at_the_budget():
    bs = _build_site()
    spots = [{"id": k, "name": k, "lat": 53.9 + i / 100, "lon": -1.8} for i, k in enumerate("abc")]
    clock, retried = _Clock(), []

    def alerts(lat, lon, timeout=None):
        if timeout is None:
            raise httpx.ReadTimeout("slow")
        retried.append((lat, timeout))
        clock.t += 6.0   # the EA takes 6 s to answer each: two fit in what is left of 30 s, the third does not start
        return []

    counts = bs.attach_flow_state(spots, alerts=alerts, any_alerts=lambda: True, workers=1, now=NOW, sleep=clock.sleep, clock=clock)
    assert retried == [(53.9, 10.0), (53.91, 4.0)]
    assert [s["flood_alerts"] for s in spots] == [[], [], None] and counts["flood_alerts_unchecked"] == 1


def test_no_retry_when_the_national_list_was_not_answered():
    bs = _build_site()
    spots = [{"id": "a", "name": "a", "lat": 53.9, "lon": -1.8}]
    clock = _Clock()

    def refused():
        raise httpx.ReadTimeout("slow")

    counts = bs.attach_flow_state(spots, alerts=lambda lat, lon, timeout=None: [], any_alerts=refused, workers=1, now=NOW,
                                  sleep=clock.sleep, clock=clock)
    assert spots[0]["flood_alerts"] is None and counts["flood_alerts_unchecked"] == 1 and clock.slept == []


def test_floods_in_force_anywhere_ignores_warnings_no_longer_in_force(monkeypatch):
    _fake_ea_paths(monkeypatch, {"/flood-monitoring/id/floods": {"items": [FLOODS["items"][2]]}})
    assert flows.floods_in_force_anywhere() is False   # 3 Oct 2026: one item, severity 4
    _fake_ea_paths(monkeypatch, {"/flood-monitoring/id/floods": FLOODS})
    assert flows.floods_in_force_anywhere() is True


def test_a_lake_never_gets_a_river_word():
    """A lake's gauge can match it on the lake's name (Windermere at Far Sawrey, built 3 Oct 2026) or
    on a river sharing a word (Derwent Water and the River Derwent at Portinscale): same_river is
    then True, but the page would say "River high" of a lake. Its flood alerts still count."""
    bs = _build_site()
    asked = []
    spots = [{"id": k, "name": k, "kind": "lake", "lat": 54.3 + i / 100, "lon": -2.9, "location": {"watercourse": "Windermere (N Basin)"},
              "river_state": {**flows.reading_fields(_state(level, NOW - timedelta(minutes=15), river="Windermere"), NOW),
                              "same_river": True, "measure": "735225-level-stage-i-15_min-m"}}
             for i, (k, level) in enumerate((("high", 2.1), ("usual", 0.6)))]
    flood = [{"severity_level": 3, "severity": "Flood alert", "area": "Windermere", "area_id": "011WAF1", "url": None, "raised": None,
              "waters": ["Windermere"]}]
    bs.attach_flow_state(spots, trend=lambda m: asked.append(m) or [], alerts=lambda lat, lon: flood,
                         any_alerts=lambda: True, workers=1, now=NOW)
    assert [s["flow_state"] for s in spots] == [None, None] and asked == []
    assert spots[0]["flood_alerts"] == flood


# ------------------------------------------------------------------------------ fewer requests
# On 3 Oct 2026 the build asked the EA about 300 times for the spots' gauges, three requests a spot,
# and met HTTP 403 or a timeout 8 to 79 times a build; the national flood list, asked after them,
# was refused in 6 of 8 builds, leaving every spot's flood alerts unchecked. Now one request carries
# every gauge's latest reading, each spot's gauge is kept for a week, and the flood list goes first.
def _station(ref: str, measures: list[tuple[str, str, str]]) -> dict:
    return {"stationReference": ref, "label": ref, "riverName": "River Thames", "lat": 51.41, "long": -0.31,
            "stageScale": {"typicalRangeLow": 1.0, "typicalRangeHigh": 2.0},
            "measures": [{"@id": f"http://{EA}/flood-monitoring/id/measures/{ref}-level-{q.lower()}-i-15_min-{u}",
                          "parameter": p, "qualifier": q, "unitName": u} for q, u, p in measures]}


def test_a_gauge_reads_its_stage_in_metres_above_its_datum_first():
    """The stage scale's usual range is for the stage above the gauge's datum: Kingston (3400TH)
    publishes its stage in mAOD and mASD, Silsden (L1515) in m and with no unit."""
    kingston = _station("3400TH", [("Stage", "mAOD", "level"), ("Stage", "mASD", "level")])
    assert flows._level_measures(kingston) == ["3400TH-level-stage-i-15_min-mASD", "3400TH-level-stage-i-15_min-mAOD"]
    silsden = _station("L1515", [("Stage", "---", "level"), ("Stage", "m", "level")])
    assert flows._level_measures(silsden)[0] == "L1515-level-stage-i-15_min-m"
    sluice = _station("1029TH", [("Downstage", "mASD", "level"), ("Stage", "mAOD", "level"), ("Flow", "m3/s", "flow")])
    assert flows._level_measures(sluice) == ["1029TH-level-stage-i-15_min-mAOD", "1029TH-level-downstage-i-15_min-mASD"]
    one = dict(sluice, measures=sluice["measures"][1])   # a single measure comes as an object, not a list
    assert flows._level_measures(one) == ["1029TH-level-stage-i-15_min-mAOD"]


def test_a_gauge_without_its_preferred_reading_takes_the_next_and_never_another_station():
    pick = {"ref": "3400TH", "station": "Kingston", "river": "River Thames", "lat": 51.41, "lon": -0.31,
            "typical_low": 1.0, "typical_high": 2.0, "rloi": "7071",
            "measures": ["3400TH-level-stage-i-15_min-mASD", "3400TH-level-stage-i-15_min-mAOD"]}
    readings = {"3400TH-level-stage-i-15_min-mAOD": ("2026-10-03T20:30:00Z", 4.6),
                "3404TH-level-stage-i-15_min-mASD": ("2026-10-03T20:30:00Z", 1.5)}
    st = flows.river_state(pick, readings)
    assert (st.measure, st.level_m) == ("3400TH-level-stage-i-15_min-mAOD", 4.6)
    st = flows.river_state(pick, {"3404TH-level-stage-i-15_min-mASD": ("2026-10-03T20:30:00Z", 1.5)})
    assert st.level_m is None and st.measure is None and st.station == "Kingston"
    # A stations list without measures: the station's own stage reading, not its downstage one.
    bare = {**pick, "measures": []}
    st = flows.river_state(bare, {"3400TH-level-downstage-i-15_min-mASD": ("t", 0.3), "3400TH-level-stage-i-15_min-mASD": ("t", 1.4)})
    assert st.measure == "3400TH-level-stage-i-15_min-mASD"


def test_latest_levels_is_one_request_and_skips_readings_that_are_not_one_number(monkeypatch):
    asked = _fake_ea_paths(monkeypatch, {"/flood-monitoring/data/readings": {"items": [
        {"measure": f"http://{EA}/flood-monitoring/id/measures/F1902-level-stage-i-15_min-m", "dateTime": "2026-10-03T20:30:00Z", "value": 0.225},
        {"measure": f"http://{EA}/flood-monitoring/id/measures/E1-level-stage-i-15_min-m", "dateTime": "2026-10-03T20:30:00Z", "value": [0.1, 0.2]},
        {"measure": f"http://{EA}/flood-monitoring/id/measures/E2-level-stage-i-15_min-m", "dateTime": "2026-10-03T20:30:00Z", "value": True},
        {"measure": f"http://{EA}/flood-monitoring/id/measures/E3-flow--i-15_min-m3_s", "dateTime": "2026-10-03T20:30:00Z", "value": 4.2},
        {"measure": "http://evil.example/x y", "value": 1.0}, "not a reading"]}})
    got = flows.latest_levels()
    assert got == {"F1902-level-stage-i-15_min-m": ("2026-10-03T20:30:00Z", 0.225)}
    assert len(asked) == 1 and asked[0].url.params.get("parameter") == "level" and "latest" in asked[0].url.params


def _pick(ref="F1902", complete=True):
    return {"ref": ref, "station": ref, "river": "River Wharfe", "lat": 53.93, "lon": -1.82, "typical_low": 0.09,
            "typical_high": 1.8 if complete else None, "rloi": None, "measures": [f"{ref}-level-stage-i-15_min-m"], "complete": complete}


def test_level_lookup_asks_for_each_gauge_once_a_week_and_keeps_old_ones_while_the_ea_refuses(tmp_path):
    path, day = tmp_path / "ea_level_stations.json", 86400
    readings = {"F1902-level-stage-i-15_min-m": ("2026-10-03T20:30:00Z", 0.225)}
    picks, latest_calls = [], []

    def pick(lat, lon, dist, river):
        picks.append(lat)
        return _pick()

    def latest():
        latest_calls.append(1)
        return readings

    lookup, save = flows.level_lookup(path, now=0.0, latest=latest, pick=pick)
    assert [lookup(53.9 + i / 100, -1.8, 15, "River Wharfe").level_m for i in range(3)] == [0.225] * 3
    save()
    assert len(latest_calls) == 1 and len(picks) == 3   # one readings request for all three spots

    lookup, save = flows.level_lookup(path, now=6 * day, latest=latest, pick=pick)
    assert lookup(53.9, -1.8, 15, "River Wharfe").station == "F1902" and len(picks) == 3   # kept: no stations request

    def refused(lat, lon, dist, river):
        raise httpx.HTTPStatusError("403", request=httpx.Request("GET", f"https://{EA}/"), response=httpx.Response(403))

    lookup, save = flows.level_lookup(path, now=20 * day, latest=latest, pick=refused)
    assert lookup(53.9, -1.8, 15, "River Wharfe").level_m == 0.225   # past its week, but the EA refused: the old gauge
    lookup, save = flows.level_lookup(path, now=31 * day, latest=latest, pick=refused)
    assert lookup(53.9, -1.8, 15, "River Wharfe") is None   # over a month old: not used
    save()
    assert json.loads(path.read_text()) == {}   # and dropped from the file


def test_level_lookup_does_not_keep_a_gauge_without_its_range_and_asks_nothing_when_readings_failed(tmp_path):
    path = tmp_path / "picks.json"
    picks = []

    def partial(lat, lon, dist, river):
        picks.append(lat)
        return _pick(complete=False)

    lookup, save = flows.level_lookup(path, now=0.0, latest=lambda: {}, pick=partial)
    st = lookup(53.9, -1.8, 15, "River Wharfe")
    assert st.typical_high is None and st.level_m is None
    save()
    lookup, save = flows.level_lookup(path, now=60.0, latest=lambda: {}, pick=partial)
    lookup(53.9, -1.8, 15, "River Wharfe")
    assert len(picks) == 2   # asked again: the range-less pick was not kept

    def broken():
        raise httpx.ReadTimeout("slow")

    lookup, save = flows.level_lookup(path, now=120.0, latest=broken, pick=partial)
    assert lookup(53.9, -1.8, 15, "River Wharfe") is None and len(picks) == 2   # no readings: no stations requests


def test_a_damaged_gauge_file_is_asked_again(tmp_path):
    path = tmp_path / "picks.json"
    path.write_text('{"53.90000,-1.80000,15,wharfe": {"at": 0, "pick": {"ref": 1}}, "x": "not an entry"}')
    lookup, save = flows.level_lookup(path, now=10.0, latest=lambda: {}, pick=lambda *a: _pick())
    assert lookup(53.9, -1.8, 15, "River Wharfe").station == "F1902"
    save()
    assert "x" not in path.read_text()
    path.write_text("not json")
    lookup, save = flows.level_lookup(path, now=10.0, latest=lambda: {}, pick=lambda *a: None)
    assert lookup(53.9, -1.8, 15, "River Wharfe") is None


def test_the_flood_list_is_asked_before_the_levels_and_its_refusal_is_kept_for_later():
    bs = _build_site()
    order = []
    ok = bs.asked_now(lambda: order.append("floods") or True)
    assert order == ["floods"] and ok() is True and ok() is True and order == ["floods"]

    def refused():
        raise httpx.HTTPStatusError("403", request=httpx.Request("GET", f"https://{EA}/"), response=httpx.Response(403))

    later = bs.asked_now(refused)
    with pytest.raises(httpx.HTTPStatusError):
        later()
    spots = [{"id": "a", "name": "a", "lat": 53.9, "lon": -1.8}]
    assert bs.attach_flow_state(spots, alerts=lambda lat, lon: [], any_alerts=later, workers=1, now=NOW)["flood_alerts_unchecked"] == 1


def test_the_flood_requests_take_the_timeout_they_are_given(monkeypatch):
    seen = []

    def get(url, params=None, headers=None, timeout=None):
        seen.append(timeout)
        return httpx.Response(200, json={"items": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(flows.httpx, "get", get)
    flows.floods_in_force_anywhere()
    flows.floods_in_force_anywhere(timeout=10.0)
    flows.flood_alerts(53.9, -1.8)
    flows.flood_alerts(53.9, -1.8, timeout=7.5)
    assert seen == [flows.EA_TIMEOUT_S, 10.0, flows.EA_TIMEOUT_S, 7.5]


# ------------------------------------------------------------------------------ the spot's own water
# 26 Oct 2026, live: the four Wharfe spots near Burnsall said "Flood alert in force nearby: Lower River
# Ure" (122WAF940, 16.6 km from Burnsall at its nearest), and Dartington on the Dart "South Devon coast
# from Start Point to Dawlish Warren" (113WACT1B). The EA's `dist` is not measured to the area's
# outline, so an alert is the spot's only when its area names the spot's river or lake. The fixture is
# that night's /id/floods, trimmed to eight items.
LIVE_FLOODS = json.loads((Path(__file__).parent / "fixtures" / "ea_floods_2026-10-26.json").read_text())


def _live_alerts(monkeypatch, *area_ids, severity: int | None = None) -> list[dict]:
    """The fixture's items for these areas, read by flows.flood_alerts as the build reads them."""
    items = [dict(f) for a in area_ids for f in LIVE_FLOODS["items"] if f["floodAreaID"] == a]
    for f in items:
        if severity is not None:
            f["severityLevel"] = severity
    _fake_ea_paths(monkeypatch, {"/flood-monitoring/id/floods": {"items": items}})
    return flows.flood_alerts(54.047, -1.953)


def _spot(id_, kind, river, watercourse, name=None):
    return {"id": id_, "name": name or id_, "kind": kind, "river": river, "location": {"watercourse": watercourse}}


BURNSALL = _spot("wharfe-burnsall", "river", "River Wharfe", "River Wharfe", "River Wharfe, Burnsall")
DARTINGTON = _spot("osm-dart-dartington", "river", "River Dart", "River Dart", "River Dart, Dartington Pontoon")
CALFCLOSE = _spot("derwent-water-calfclose", "lake", None, "Derwent Water", "Derwent Water, Calfclose Bay")


def test_flood_alerts_keep_each_areas_waters(monkeypatch):
    found = _live_alerts(monkeypatch, "122WAF940", "113WACT1B", "062WAF38BrentBks")
    by = {a["area_id"]: a["waters"] for a in found}
    assert by["122WAF940"] == ["River Ure", "Swinney Beck", "Bishop Monkton Beck", "River Skell", "River Laver",
                               "River Tutt", "Stainley Beck"]
    assert by["113WACT1B"] == ["South Devon Coast"]
    assert "062WAF38BrentBks" not in by   # severity 4 in the fixture: never shown as in force
    assert flows.flood_waters("Silk Stream;\nDollis Brook;\nDeans Brook") == ["Silk Stream", "Dollis Brook", "Deans Brook"]
    assert flows.flood_waters(None) is None and flows.flood_waters(" , ") is None and flows.flood_waters(["Derwent", 3]) == ["Derwent"]


def test_burnsall_on_the_wharfe_drops_the_lower_river_ure_area(monkeypatch):
    bs = _build_site()
    found = _live_alerts(monkeypatch, "122WAF940")
    assert [a["area"] for a in found] == ["Lower River Ure"]   # what the EA's 10 km query gave Burnsall
    assert flows.split_flood_alerts(found, bs.own_water(BURNSALL)) == ([], 1, 0)   # another named river: not shown, counted


def test_dartington_on_the_dart_drops_the_south_devon_coast_area(monkeypatch):
    bs = _build_site()
    found = _live_alerts(monkeypatch, "113WACT1B")
    assert flows.flood_alert_water(found[0], bs.own_water(DARTINGTON)) == "other"
    assert flows.split_flood_alerts(found, bs.own_water(DARTINGTON)) == ([], 1, 0)


def test_a_wharfe_spot_keeps_an_upper_river_wharfe_alert_most_severe_first(monkeypatch):
    bs = _build_site()
    # 122WAF942 was in the Burnsall answer at severity 4 that night; here in force, beside the Ure.
    found = _live_alerts(monkeypatch, "122WAF940", "122WAF942", severity=3)
    found[1]["severity_level"], found[1]["severity"] = 2, "Flood warning"
    kept, other, unknown = flows.split_flood_alerts(sorted(found, key=lambda a: a["severity_level"]), bs.own_water(BURNSALL))
    assert [(a["area_id"], a["severity"]) for a in kept] == [("122WAF942", "Flood warning")] and (other, unknown) == (1, 0)
    # Welsh names read as English: a spot placed on "Afon Gwy" keeps a River Wye area.
    wye = flows.SpotWater(flows.water_names("Afon Gwy"))
    assert flows.flood_alert_water({"area": "River Wye in Herefordshire", "waters": ["River Wye"]}, wye) == "own"


def test_derwent_water_keeps_its_own_areas_and_never_names_the_lower_river_derwent(monkeypatch):
    bs = _build_site()
    found = _live_alerts(monkeypatch, "011WAFDW", "011FWFNC6KC", "011WAFCD", severity=3)
    kept, other, unknown = flows.split_flood_alerts(found, bs.own_water(CALFCLOSE))
    # "Upper River Derwent, Stonethwaite Beck and Derwent Water" by its name; the Keswick campsite by
    # its water, "Derwentwater". "Rivers Cocker, Marron and Derwent" is another river, which for a lake
    # is "unknown" (a river can run into a lake): not named, said neutrally.
    assert sorted(a["area_id"] for a in kept) == ["011FWFNC6KC", "011WAFDW"] and (other, unknown) == (0, 1)
    # A river spot on the Derwent keeps that river's areas.
    river = bs.own_water(_spot("x", "river", "River Derwent", "River Derwent"))
    assert all(flows.flood_alert_water(a, river) == "own" for a in found if a["area_id"] != "011FWFNC6KC")


def test_a_coastal_or_tidal_area_never_attaches_to_an_inland_spot_even_when_it_names_the_river(monkeypatch):
    bs = _build_site()
    dart = bs.own_water(DARTINGTON)
    assert dart.tidal is False and dart.lake is False
    coast = {"area": "Coast at Dartmouth and Dartmouth Castle", "waters": ["English Channel"]}
    assert flows.flood_alert_water(coast, dart) == "other"   # "dart" is not a word of "dartmouth"
    assert flows.flood_alert_water({**coast, "tidal": True}, dart) == "other"
    # 26 Oct 2026: "Coast at Duddon estuary" (011WACN4, isTidal) named the Duddon at Birks Bridge, far inland.
    estuary = {"area": "Coast at Duddon estuary", "waters": ["Irish Sea"], "tidal": True}
    assert flows.flood_alert_water(estuary, bs.own_water(_spot("d", "river", "River Duddon", "River Duddon"))) == "other"
    tidal_dart = {"area": "Tidal River Dart at Totnes", "waters": ["River Dart"], "tidal": True}
    assert flows.flood_alert_water(tidal_dart, dart) == "other"
    # A spot placed on a tidal river keeps its own river's tidal areas.
    on_tide = bs.own_water({**_spot("t", "river", "River Dart", None), "location": {"watercourse": "River Dart", "form": "tidalRiver"}})
    assert on_tide.tidal and flows.flood_alert_water(tidal_dart, on_tide) == "own"
    # The fixture's live coastal item carries the EA's flag through flows.flood_alerts.
    assert [a["tidal"] for a in _live_alerts(monkeypatch, "113WACT1B", "122WAF940")] == [True, False]


def test_a_lakes_alert_for_another_river_is_unknown_and_a_coast_is_other():
    """The Rothay runs through Grasmere and Rydal Water into Windermere: a lake cannot rule a river
    out by name, so that alert is said neutrally. The coast never reaches a lake."""
    waterhead = _build_site().own_water(_spot("w", "lake", None, "Windermere (N Basin)", "Windermere, Waterhead"))
    rothay = {"area": "Rivers Brathay, Rothay and Winster", "waters": ["River Brathay", "River Rothay", "River Winster"], "tidal": False}
    assert flows.flood_alert_water(rothay, waterhead) == "unknown"
    coast = {"area": "Coast at North Morecambe Bay", "waters": ["Irish Sea"], "tidal": True}
    assert flows.flood_alert_water(coast, waterhead) == "other"
    assert flows.flood_alert_water({"area": "Windermere at Bowness", "waters": ["Windermere"], "tidal": False}, waterhead) == "own"


def test_an_alert_whose_water_cannot_be_told_is_unknown_not_dropped_and_not_named():
    bs = _build_site()
    names = bs.own_water(BURNSALL)
    no_waters = {"severity_level": 3, "severity": "Flood alert", "area": "Grassington area", "waters": None}
    assert flows.flood_alert_water(no_waters, names) == "unknown"
    assert flows.flood_alert_water({**no_waters, "area": "River Wharfe at Grassington"}, names) == "own"   # its name says it
    # A spot with no water name: every alert near it is unknown, never dropped as another river's.
    pond = bs.own_water({"id": "p", "name": "", "kind": "lake", "river": None, "location": None})
    assert pond.names == frozenset() and flows.split_flood_alerts([no_waters, {**no_waters, "waters": ["River Ure"]}], pond) == ([], 0, 2)
    # Malformed items are never the spot's and never raise.
    odd = [None, "x", {}, {"area": 5, "waters": "River Wharfe"}, {"waters": [None, 7]}, {"waters": ["(1)"]}]
    assert flows.split_flood_alerts(odd, names) == ([], 0, 6)
    assert flows.split_flood_alerts(None, names) == (None, None, None)   # unchecked stays unchecked
    # A lake with no watercourse goes by its name before the comma.
    assert "blea tarn" in bs.own_water({"name": "Blea Tarn, Langdale", "kind": "lake", "location": {"watercourse": None}}).names


def test_attach_flow_state_keeps_only_the_spots_own_water(monkeypatch):
    """The build end to end, with the night's alerts as flows.flood_alerts returns them."""
    bs = _build_site()
    ure, coast = _live_alerts(monkeypatch, "122WAF940"), _live_alerts(monkeypatch, "113WACT1B")
    wharfe = _live_alerts(monkeypatch, "122WAF942", severity=3)
    spots = [{**BURNSALL, "lat": 54.047, "lon": -1.953}, {**DARTINGTON, "lat": 50.4394, "lon": -3.69136},
             {**_spot("ilkley", "river", "River Wharfe", "River Wharfe"), "lat": 53.925, "lon": -1.82},
             {"id": "pond", "name": "Hampstead Heath (Ladies Pond)", "kind": "lake", "river": None, "lat": 51.56, "lon": -0.16}]
    answers = {54.047: ure, 50.4394: coast, 53.925: wharfe + ure, 51.56: [{**ure[0], "waters": None, "area": "North London ponds"}]}
    counts = bs.attach_flow_state(spots, trend=lambda m: [], alerts=lambda lat, lon: answers[lat], any_alerts=lambda: True,
                                  workers=1, now=NOW)
    got = {s["id"]: (s["flood_alerts"], s["flood_alerts_other"], s["flood_alerts_unmatched"]) for s in spots}
    assert got["wharfe-burnsall"] == ([], 1, 0) and got["osm-dart-dartington"] == ([], 1, 0)
    assert [a["area"] for a in got["ilkley"][0]] == ["Upper River Wharfe"] and got["ilkley"][1:] == (1, 0)
    assert got["pond"] == ([], 0, 1)
    assert counts["flood_alerts"] == 1 and counts["flood_alerts_other_water"] == 3 and counts["flood_alerts_unmatched"] == 1
    assert all("days" not in s and "now" not in s for s in spots)   # nothing here touches the pollution level
