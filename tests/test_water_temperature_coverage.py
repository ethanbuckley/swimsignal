"""scripts/water_temperature_coverage.py on fixtures: air or water, the request caps, matching a spot to
a sensor on its own water, staleness, and the counts. No request leaves the machine."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("water_temperature_coverage", ROOT / "scripts" / "water_temperature_coverage.py")
cov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cov)

NOW = datetime(2026, 10, 27, 1, 5, tzinfo=UTC)
T = "http://environment.data.gov.uk/flood-monitoring/def/core/"


def station(sid, label, lat, lon, kinds=("WaterQualityStation",), state="Active", opened="2026-04-01", closed=None,
            river=None):
    s = {"@id": f"http://environment.data.gov.uk/hydrology/id/stations/{sid}", "notation": sid, "label": label,
         "lat": lat, "long": lon, "type": [{"@id": T + k} for k in ("Station", *kinds)],
         "status": [{"@id": T + "status" + state, "label": state}], "dateOpened": opened, "dateClosed": closed,
         "measures": [{"@id": f"http://environment.data.gov.uk/hydrology/id/measures/{sid}-temp-i-subdaily-C"}]}
    if river:
        s["riverName"] = river
    return s


def reading(sid, when, value):
    return {"measure": {"@id": f"http://environment.data.gov.uk/hydrology/id/measures/{sid}-temp-i-subdaily-C"},
            "dateTime": when, "value": value, "quality": "Unchecked"}


# A sonde 5 km up the Stour from Dedham, one on the Brett nearer still, a gauge on the Stour, a sonde
# that last reported two days ago, and a finished deployment at the spot itself.
STATIONS = [
    station("E06651A", "STOUR_BOXTEDMILL_E_202604", 51.9530, 0.9100),
    station("E99999A", "BRETT_HADLEIGH_E_202604", 51.9600, 0.9700),
    station("E11111A", "STOUR_LANGHAM_E_202601", 51.9640, 0.9550),
    station("E00001A", "STOUR_DEDHAM_E_201906", 51.9590, 0.9900, state="Closed", opened="2019-06-01", closed="2019-09-01"),
    station("E00002A", "STOUR_DEDHAM_E_202106", 51.9590, 0.9900, state="Closed", opened="2021-06-01", closed="2021-08-01"),
    station("g1", "Derby St.Marys", 52.9300, -1.4700, kinds=("RiverStation", "RiverFlow"), river="River Derwent"),
]
READINGS = [
    reading("E06651A", "2026-10-26T21:06:17", 10.4),
    reading("E06651A", "2026-10-26T20:06:17", 10.5),
    reading("E99999A", "2026-10-27T00:00:00", 11.0),
    reading("E11111A", "2026-10-25T00:00:00", 9.0),     # 49 h old: not the water now
]
DEDHAM = {"id": "dedham", "name": "River Stour, Dedham", "kind": "river", "river": "River Stour", "lat": 51.9590,
          "lon": 0.9900, "source": "curated"}
LAKE = {"id": "wm", "name": "Windermere, Lakeside YMCA", "kind": "lake", "river": float("nan"), "lat": 51.9590,
        "lon": 0.9901, "source": "designated"}


def test_a_water_quality_sonde_and_a_river_gauge_are_water_and_flood_monitoring_bulbs_are_air():
    assert cov.station_kind(STATIONS[0]) == "sonde"
    assert cov.station_kind(STATIONS[-1]) == "gauge"
    assert cov.station_kind({"type": [{"@id": T + "RainfallStation"}]}) == "unknown"
    assert cov.station_kind({}) == "unknown"
    assert cov.flood_measure_kind({"qualifier": "Water"}) == "water"
    assert cov.flood_measure_kind({"qualifier": "Dry Bulb"}) == "air"
    assert cov.flood_measure_kind({"qualifier": "Wet Bulb"}) == "air"
    assert cov.flood_measure_kind({}) == "unknown"


def test_deployments_at_one_place_count_as_one_site_with_its_history():
    assert cov.place_key("STOUR_BOXTEDMILL_E_202604") == "STOUR_BOXTEDMILL"
    assert cov.place_key("WMD_MANIFOLD_DS HULME END_E_202604") == "WMD_MANIFOLD_DS HULME END"
    assert cov.place_key("SERPENTINE") == "SERPENTINE"
    d = cov.deployments(STATIONS)["STOUR_DEDHAM"]
    assert d == {"n": 2, "first": "2019-06-01", "last_closed": "2021-08-01", "active": False}
    assert cov.deployments(STATIONS)["STOUR_BOXTEDMILL"]["last_closed"] is None
    assert "Derby St.Marys".upper() not in cov.deployments(STATIONS)   # a gauge is not a sonde site


def test_a_spot_gets_a_live_sensor_on_its_own_river_never_a_nearer_one_on_another_or_a_stale_one():
    cat = {"h_measures": [], "h_stations": STATIONS, "readings": READINGS, "f_measures": [], "f_stations": []}
    rep = cov.run(cat, [DEDHAM], NOW)
    row = rep["spots"][0]
    assert row["same_water"]["station"] == "STOUR_BOXTEDMILL_E_202604"   # not the Brett, though nearer; not Langham, 49 h old
    assert row["same_water"]["age_hours"] == 4.0
    assert row["nearest_any"]["river"] == "Brett"
    assert row["past_same_water"]["site_history"]["n"] == 2
    assert rep["summary"]["live_sensors"] == 2
    assert rep["summary"]["same_water_within_15km"] == 1 and rep["summary"]["same_water_within_5km"] == 0


def test_upstream_is_taken_before_a_nearer_sensor_downstream_and_an_unplaced_one_is_passed_over():
    cat = {"h_measures": [], "h_stations": STATIONS, "readings": READINGS + [reading("E11111A", "2026-10-27T00:30:00", 9.5)],
           "f_measures": [], "f_stations": []}
    rel = {"STOUR_LANGHAM_E_202601": ("downstream", 3.0), "STOUR_BOXTEDMILL_E_202604": ("upstream", 7.4)}
    row = cov.run(cat, [DEDHAM], NOW, relate=lambda sp, s: rel[s.label])["spots"][0]
    assert (row["same_water"]["station"], row["same_water"]["direction"]) == ("STOUR_BOXTEDMILL_E_202604", "upstream")
    row = cov.run(cat, [DEDHAM], NOW, relate=lambda sp, s: None)["spots"][0]
    assert "same_water" not in row


def test_a_lake_needs_a_sensor_named_for_the_lake_not_a_river_beside_it():
    assert cov.lake_name("Windermere, Lakeside YMCA") == "Windermere"
    assert cov.lake_name("Hampstead Heath (Mens Pond)") == "Mens Pond"
    assert cov.lake_name("The Serpentine - Hyde Park") == "The Serpentine"
    cat = {"h_measures": [], "h_stations": STATIONS, "readings": READINGS, "f_measures": [], "f_stations": []}
    row = cov.run(cat, [LAKE], NOW)["spots"][0]
    assert "same_water" not in row and "past_same_water" not in row
    assert row["nearest_any"]["km"] < 2   # the Brett, 1.4 km off, is not the lake


class Resp:
    def __init__(self, code, text='{"items": []}'):
        self.status_code, self.text = code, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_the_client_keeps_to_the_caps(tmp_path):
    sent, slept = [], []
    clock = iter(range(0, 1000, 1))   # one second passes between each look at the clock
    c = cov.CappedClient(tmp_path, cap=2, gap_s=1.5, get=lambda url, **kw: sent.append(url) or Resp(200),
                         sleep=slept.append, clock=lambda: next(clock))
    c.fetch("https://environment.data.gov.uk/hydrology/id/stations.json", {"b": 2, "a": 1})
    c.fetch("https://environment.data.gov.uk/hydrology/id/stations.json", {"a": 1, "b": 2})   # cached: not sent
    assert len(sent) == 1 and c.cached == 1
    c.fetch("https://environment.data.gov.uk/hydrology/id/measures.json", [("measure", "x"), ("measure", "w")])
    assert sent[-1].endswith("?measure=w&measure=x")
    assert slept and all(s >= 0.5 for s in slept)   # waited out the rest of the 1.5 s
    with pytest.raises(cov.Stop, match="cap of 2"):
        c.fetch("https://environment.data.gov.uk/hydrology/id/other.json")
    with pytest.raises(ValueError, match="not an EA URL"):
        c.fetch("https://api.open-meteo.com/v1/forecast")
    with pytest.raises(ValueError):
        c.fetch("http://environment.data.gov.uk/hydrology/id/stations.json")


@pytest.mark.parametrize("code", [429, 500, 503])
def test_the_client_stops_on_429_and_5xx_and_caches_nothing(tmp_path, code):
    c = cov.CappedClient(tmp_path, get=lambda url, **kw: Resp(code), sleep=lambda s: None)
    with pytest.raises(cov.Stop, match=str(code)):
        c.fetch("https://environment.data.gov.uk/hydrology/id/stations.json")
    assert not list(tmp_path.glob("*.json"))
