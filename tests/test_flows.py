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
    from shapely.geometry import Point
    area = Point(flows.bng(spots[4]["lat"], spots[4]["lon"])).buffer(100)   # the alert's area covers the lake's pin
    counts = bs.attach_flow_state(spots, trend=trend, alerts=alerts, any_alerts=lambda: True, workers=1, now=NOW,
                                  sleep=clock.sleep, clock=clock, outline=lambda aid, timeout: area, lake_at=lambda x, y: None)
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
                      "flood_alerts_other_water": 0, "flood_alerts_unmatched": 0, "flood_outlines": 1, "flood_outlines_missing": 0}
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
    from shapely.geometry import box
    lake = box(*flows.bng(54.29, -2.91), *flows.bng(54.32, -2.89))   # the alert's area reaches the lake's outline
    bs.attach_flow_state(spots, trend=lambda m: asked.append(m) or [], alerts=lambda lat, lon: flood,
                         any_alerts=lambda: True, workers=1, now=NOW, outline=lambda aid, timeout: lake.buffer(-500),
                         lake_at=lambda x, y: lake)
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


# ------------------------------------------------------------------------------ which alerts apply here
# 26 Oct 2026, live: the four Wharfe spots near Burnsall said "Flood alert in force nearby: Lower River
# Ure" (122WAF940, whose outline is 15.7 to 18.7 km away), and Dartington on the Dart "South Devon coast
# from Start Point to Dawlish Warren" (113WACT1B, 8.8 km away). An alert is now the spot's only when the
# EA's outline of its area covers the spot's point on its water, or its lake. The fixtures are that
# night's /id/floods (trimmed), the EA outlines of five of its areas and three WFD lake outlines,
# simplified to 10 m (outcomes checked identical to the raw outlines), and ten spots from the site data.
FIX = Path(__file__).parent / "fixtures"
LIVE_FLOODS = json.loads((FIX / "ea_floods_2026-10-26.json").read_text())
SPOTS = {s["id"]: s for s in json.loads((FIX / "flood_areas" / "spots.json").read_text())["spots"]}
OUTLINES = {a: flows.load_outline((FIX / "flood_areas" / f"{a}.geojson").read_text())
            for a in ("122WAF940", "122WAF942", "113WACT1B", "011WAFDW", "011FWFNC6KC")}
LAKES = [flows.load_outline(p.read_text()) for p in sorted((FIX / "flood_areas").glob("lake-*.geojson"))]


def _lake_at(x, y):
    """The fixture lake outline a point lies in, as build_site.lake_outline_at reads lakes.parquet."""
    from shapely.geometry import Point
    return next((g for g in LAKES if g.covers(Point(x, y))), None)


@pytest.fixture(autouse=True)
def _no_live_fetch(monkeypatch):
    """Nothing in these tests asks the EA: a request a test did not fake fails it."""
    def refuse(url, **kw):
        raise AssertionError(f"live request in a test: {url}")
    monkeypatch.setattr(flows.httpx, "get", refuse)


def _live_alerts(monkeypatch, *area_ids, severity: int | None = None) -> list[dict]:
    """The fixture's items for these areas, read by flows.flood_alerts as the build reads them."""
    items = [dict(f) for a in area_ids for f in LIVE_FLOODS["items"] if f["floodAreaID"] == a]
    for f in items:
        if severity is not None:
            f["severityLevel"] = severity
    _fake_ea_paths(monkeypatch, {"/flood-monitoring/id/floods": {"items": items}})
    return flows.flood_alerts(54.047, -1.953)


def _water(spot_id, **change):
    bs = _build_site()
    return bs.own_water({**SPOTS[spot_id], **change}, _lake_at)


def _kind(monkeypatch, spot_id, area_id, severity=None, outline=True, **change):
    alert = _live_alerts(monkeypatch, area_id, severity=severity)[0]
    return flows.flood_alert_water(alert, _water(spot_id, **change), OUTLINES[area_id] if outline else None)


def _pin_inside(spot_id, area_id):
    from shapely.geometry import Point
    return OUTLINES[area_id].covers(Point(_water(spot_id).pin))


def test_flood_alerts_keep_each_areas_waters(monkeypatch):
    found = _live_alerts(monkeypatch, "122WAF940", "113WACT1B", "062WAF38BrentBks")
    by = {a["area_id"]: (a["waters"], a["tidal"]) for a in found}
    assert by["122WAF940"] == (["River Ure", "Swinney Beck", "Bishop Monkton Beck", "River Skell", "River Laver",
                                "River Tutt", "Stainley Beck"], False)
    assert by["113WACT1B"] == (["South Devon Coast"], True)
    assert "062WAF38BrentBks" not in by   # severity 4 in the fixture: never shown as in force
    assert flows.flood_waters("Silk Stream;\nDollis Brook;\nDeans Brook") == ["Silk Stream", "Dollis Brook", "Deans Brook"]
    assert flows.flood_waters(None) is None and flows.flood_waters(" , ") is None and flows.flood_waters(["Derwent", 3]) == ["Derwent"]


def test_burnsall_on_the_wharfe_is_outside_the_lower_river_ure_area_so_it_is_other(monkeypatch):
    assert _kind(monkeypatch, "wharfe-burnsall", "122WAF940") == "other"
    for s in ("wharfe-bolton-abbey", "wharfe-appletreewick", "wharfe-linton-falls"):
        assert _kind(monkeypatch, s, "122WAF940") == "other"
    found = _live_alerts(monkeypatch, "122WAF940")
    assert flows.split_flood_alerts(found, _water("wharfe-burnsall"), OUTLINES) == ([], 1, 0)   # counted, not named


def test_dartington_on_the_dart_is_outside_the_south_devon_coast_area_so_it_is_other(monkeypatch):
    from shapely.geometry import Point
    dart = _water("osm-dart-dartington")
    assert not OUTLINES["113WACT1B"].covers(Point(dart.point)) and not dart.tidal   # outside, and tidal for an inland spot
    assert _kind(monkeypatch, "osm-dart-dartington", "113WACT1B") == "other"
    assert _kind(monkeypatch, "osm-dart-dartington", "113WACT1B", outline=False) == "other"


def test_the_wharfe_spots_are_in_upper_river_wharfe_by_their_point_on_the_river_not_their_pin(monkeypatch):
    """122WAF942 was at severity 4 that night (not shown); here a copy in force. Three of the four pins
    sit on a bank or path just outside the outline, while each spot's point on the river is inside:
    a pin test would turn a genuine same-river alert neutral."""
    for s in ("wharfe-burnsall", "wharfe-bolton-abbey", "wharfe-linton-falls"):
        assert not _pin_inside(s, "122WAF942"), s
        assert _kind(monkeypatch, s, "122WAF942", severity=3) == "own", s
    assert _kind(monkeypatch, "wharfe-appletreewick", "122WAF942", severity=3) == "own"
    # Beside the Ure alert, the Wharfe one is named, the most severe first, and the Ure one counted.
    found = _live_alerts(monkeypatch, "122WAF940", "122WAF942", severity=3)
    found[1]["severity_level"], found[1]["severity"] = 2, "Flood warning"
    kept, other, unknown = flows.split_flood_alerts(sorted(found, key=lambda a: a["severity_level"]), _water("wharfe-burnsall"), OUTLINES)
    assert [(a["area_id"], a["severity"]) for a in kept] == [("122WAF942", "Flood warning")] and (other, unknown) == (1, 0)


def test_a_spot_without_location_snapped_uses_its_pin(monkeypatch):
    no_snap = {"location": {**SPOTS["wharfe-burnsall"]["location"], "snapped": None}}
    w = _water("wharfe-burnsall", **no_snap)
    assert w.point == w.pin
    # Burnsall's pin is outside Upper River Wharfe: the same river, another stretch, so not matched.
    assert _kind(monkeypatch, "wharfe-burnsall", "122WAF942", severity=3, **no_snap) == "unknown"


def test_aysgarth_on_the_ure_is_outside_lower_river_ure_so_it_is_not_matched(monkeypatch):
    """The same river, 11.6 km outside its outline: for this river, but not for here. Said neutrally."""
    assert _kind(monkeypatch, "ure-aysgarth", "122WAF940") == "unknown"
    found = _live_alerts(monkeypatch, "122WAF940")
    assert flows.split_flood_alerts(found, _water("ure-aysgarth"), OUTLINES) == ([], 0, 1)


def test_derwent_water_spots_are_reached_by_their_lake_outline(monkeypatch):
    """Calfclose Bay's pin is 1.85 km from the Keswick Campsite area (riverOrSea "Derwentwater"), but
    that area reaches Derwent Water's shore, and the lake is the spot's water."""
    from shapely.geometry import Point
    calf = _water("derwent-water-calfclose")
    assert calf.lake and calf.lake_outline is not None
    assert 1700 < OUTLINES["011FWFNC6KC"].distance(Point(calf.pin)) < 2000
    for s in ("bw-ukd1101-45800", "derwent-water-calfclose"):
        for a in ("011WAFDW", "011FWFNC6KC"):
            assert _kind(monkeypatch, s, a, severity=3) == "own", (s, a)


def test_buttermere_and_wast_water_are_not_reached_by_the_derwent_area(monkeypatch):
    for s in ("buttermere", "wastwater"):
        assert _water(s).lake_outline is not None
        assert _kind(monkeypatch, s, "011WAFDW", severity=3) == "other", s


def test_without_an_outline_an_alert_is_never_named(monkeypatch):
    # Rule 4: the same water is not matched, other water or the coast is other, never "own".
    assert _kind(monkeypatch, "wharfe-burnsall", "122WAF942", severity=3, outline=False) == "unknown"
    assert _kind(monkeypatch, "derwent-water-calfclose", "011WAFDW", severity=3, outline=False) == "unknown"
    assert _kind(monkeypatch, "wharfe-burnsall", "122WAF940", outline=False) == "other"
    assert _kind(monkeypatch, "buttermere", "011WAFDW", severity=3, outline=False) == "other"
    burnsall = _water("wharfe-burnsall")
    nothing = {"severity_level": 3, "severity": "Flood alert", "area": "Grassington area", "waters": None, "tidal": False}
    assert flows.flood_alert_water(nothing, burnsall, None) == "unknown"   # names nothing
    # A spot with no water name: every alert near it is not matched, never dropped as another river's.
    pond = _build_site().own_water({"id": "p", "name": "", "kind": "lake", "river": None, "location": None, "lat": 51.56, "lon": -0.16})
    assert flows.split_flood_alerts([nothing, {**nothing, "waters": ["River Ure"]}], pond, {}) == ([], 0, 2)


def test_malformed_geometry_is_no_outline(monkeypatch):
    for bad in ("not json", "{}", {"type": "Feature", "geometry": None}, {"type": "Point", "coordinates": [-1.9, 54.0]},
                {"type": "Polygon", "coordinates": [[[0, 0], [0, 0], [0, 0], [0, 0]]]}, {"type": "Polygon", "coordinates": "x"},
                {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "LineString",
                                                                                           "coordinates": [[-1.9, 54.0], [-1.8, 54.1]]}}]}):
        assert flows.load_outline(bad) is None, bad
    # Treated as no outline: the Wharfe alert at Burnsall is then not matched, never named.
    found = _live_alerts(monkeypatch, "122WAF942", severity=3)
    assert flows.split_flood_alerts(found, _water("wharfe-burnsall"), {"122WAF942": flows.load_outline("{}")}) == ([], 0, 1)
    # Malformed items are never the spot's and never raise.
    odd = [None, "x", {}, {"area": 5, "waters": "River Wharfe"}, {"waters": [None, 7]}, {"waters": ["(1)"]}]
    assert flows.split_flood_alerts(odd, _water("wharfe-burnsall"), OUTLINES) == ([], 0, 6)


def test_unchecked_stays_unchecked():
    assert flows.split_flood_alerts(None, _water("wharfe-burnsall"), OUTLINES) == (None, None, None)


def test_a_short_river_name_counts_in_the_areas_waters_never_its_title():
    w = _water("wharfe-burnsall")
    assert w.short == frozenset({"wharfe"}) and "river wharfe" in w.names
    place = {"area": "Wharfe Lodge and Bradford", "waters": ["Bradford Beck"], "tidal": False}
    assert flows.flood_alert_water(place, w, None) == "other"   # "Wharfe" in a title is a place
    assert flows.flood_alert_water({**place, "waters": ["Wharfe", "Bradford Beck"]}, w, None) == "unknown"
    assert flows.flood_alert_water({"area": "River Wharfe at Ilkley", "waters": None}, w, None) == "unknown"   # a whole name may
    # Welsh names read as English, and a lake goes by its whole name, run together too.
    assert "river wye" in flows.water_names("Afon Gwy") and flows.short_water_names("Afon Gwy") == {"wye"}
    assert flows.water_names("Derwent Water") == {"derwent water", "derwentwater"} and _water("buttermere").short == frozenset()


def test_a_coastal_area_is_other_for_an_inland_spot_and_can_apply_to_a_tidal_one():
    dart = _water("osm-dart-dartington")
    estuary = {"area": "Coast at Duddon estuary", "waters": ["Irish Sea"], "tidal": True}
    assert flows.flood_alert_water(estuary, _build_site().own_water(
        {"kind": "river", "river": "River Duddon", "lat": 54.372, "lon": -3.19, "location": {"watercourse": "River Duddon"}}), None) == "other"
    tidal_dart = {"area": "Tidal River Dart at Totnes", "waters": ["River Dart"], "tidal": True}
    assert flows.flood_alert_water(tidal_dart, dart, None) == "other"
    on_tide = _water("osm-dart-dartington", location={**SPOTS["osm-dart-dartington"]["location"], "form": "tidalRiver"})
    assert on_tide.tidal and flows.flood_alert_water(tidal_dart, on_tide, None) == "unknown"   # its river, no outline
    from shapely.geometry import Point
    assert flows.flood_alert_water(tidal_dart, on_tide, Point(on_tide.point).buffer(50)) == "own"


def test_an_outline_is_asked_for_once_and_kept_by_area_id(tmp_path):
    raw = (FIX / "flood_areas" / "011FWFNC6KC.geojson").read_text()
    asked = []

    def get(url, headers=None, timeout=None):
        asked.append((url, timeout))
        return httpx.Response(200, text=raw, request=httpx.Request("GET", url))

    first = flows.flood_area_outline("011FWFNC6KC", tmp_path, 7.0, now=1000.0, get=get)
    assert first is not None and asked == [(f"https://{EA}/flood-monitoring/id/floodAreas/011FWFNC6KC/polygon", 7.0)]
    assert (tmp_path / "011FWFNC6KC.geojson").exists()
    t = (tmp_path / "011FWFNC6KC.geojson").stat().st_mtime
    again = flows.flood_area_outline("011FWFNC6KC", tmp_path, now=t + 86400, get=get)
    assert len(asked) == 1 and abs(again.area - first.area) < 0.01 * first.area   # kept: no second request

    def down(url, headers=None, timeout=None):
        asked.append(url)
        raise httpx.ConnectTimeout("EA timed out")

    old = flows.flood_area_outline("011FWFNC6KC", tmp_path, now=t + flows.FLOOD_OUTLINE_MAX_AGE_S + 1, get=down)
    assert len(asked) == 2 and old is not None   # past its month the EA is asked; refused, the kept outline stands
    assert flows.flood_area_outline("122WAF940", tmp_path, now=t, get=down) is None   # nothing kept: no outline
    assert flows.flood_area_outline("bad id/../x", tmp_path, get=down) is None and len(asked) == 3   # never asked
    assert flows.flood_area_outline(None, tmp_path, get=down) is None

    def junk(url, headers=None, timeout=None):
        return httpx.Response(200, text="{}", request=httpx.Request("GET", url))
    assert flows.flood_area_outline("113WACT1B", tmp_path, get=junk) is None and not (tmp_path / "113WACT1B.geojson").exists()


def test_attach_flow_state_names_only_the_alerts_whose_area_covers_the_spot(monkeypatch):
    """The build end to end, with the night's alerts as flows.flood_alerts returns them and the
    fixture outlines in place of the EA's: each area's outline asked for once, and none fetched."""
    bs = _build_site()
    ure, coast = _live_alerts(monkeypatch, "122WAF940"), _live_alerts(monkeypatch, "113WACT1B")
    wharfe, derwent = _live_alerts(monkeypatch, "122WAF942", severity=3), _live_alerts(monkeypatch, "011WAFDW", severity=3)
    ids = ["wharfe-burnsall", "wharfe-bolton-abbey", "osm-dart-dartington", "ure-aysgarth", "derwent-water-calfclose", "buttermere"]
    spots = [dict(SPOTS[i]) for i in ids]
    answers = {"wharfe-burnsall": ure, "wharfe-bolton-abbey": wharfe + ure, "osm-dart-dartington": coast,
               "ure-aysgarth": ure, "derwent-water-calfclose": derwent, "buttermere": derwent}
    by_lat = {SPOTS[i]["lat"]: answers[i] for i in ids}
    asked = []

    def outline(aid, timeout):
        asked.append(aid)
        return OUTLINES[aid]

    counts = bs.attach_flow_state(spots, trend=lambda m: [], alerts=lambda lat, lon: by_lat[lat], any_alerts=lambda: True,
                                  workers=1, now=NOW, outline=outline, lake_at=_lake_at)
    got = {s["id"]: ([a["area_id"] for a in s["flood_alerts"]], s["flood_alerts_other"], s["flood_alerts_unmatched"]) for s in spots}
    assert got == {"wharfe-burnsall": ([], 1, 0), "wharfe-bolton-abbey": (["122WAF942"], 1, 0), "osm-dart-dartington": ([], 1, 0),
                   "ure-aysgarth": ([], 0, 1), "derwent-water-calfclose": (["011WAFDW"], 0, 0), "buttermere": ([], 1, 0)}
    assert sorted(asked) == ["011WAFDW", "113WACT1B", "122WAF940", "122WAF942"]   # once each, not once a spot
    assert counts["flood_alerts"] == 2 and counts["flood_alerts_other_water"] == 4 and counts["flood_alerts_unmatched"] == 1
    assert counts["flood_outlines"] == 4 and counts["flood_outlines_missing"] == 0
    assert all("days" not in s and "now" not in s for s in spots)   # nothing here touches the pollution level

    # An outline that fails is rule 4 for its area: Bolton Abbey's Wharfe alert is then not matched.
    spots = [dict(SPOTS["wharfe-bolton-abbey"])]

    def broken(aid, timeout):
        if aid == "122WAF942":
            raise httpx.ReadTimeout("slow")
        return OUTLINES[aid]

    counts = bs.attach_flow_state(spots, trend=lambda m: [], alerts=lambda lat, lon: wharfe + ure, any_alerts=lambda: True,
                                  workers=1, now=NOW, outline=broken, lake_at=_lake_at)
    assert (spots[0]["flood_alerts"], spots[0]["flood_alerts_other"], spots[0]["flood_alerts_unmatched"]) == ([], 1, 1)
    assert counts["flood_outlines_missing"] == 1


def test_the_outlines_are_all_asked_within_the_budget():
    bs = _build_site()
    clock, asked = _Clock(), []

    def slow(aid, timeout):
        asked.append((aid, timeout))
        clock.t += 12.0
        return OUTLINES.get(aid)

    got = bs.flood_outlines({"122WAF940", "122WAF942", "113WACT1B", "011WAFDW"}, slow, workers=1, clock=clock)
    assert [a for a, _ in asked] == ["011WAFDW", "113WACT1B", "122WAF940"]   # the fourth would start after 30 s
    assert got["122WAF942"] is None and got["011WAFDW"] is not None
    assert [t for _, t in asked] == [10.0, 10.0, 6.0]
