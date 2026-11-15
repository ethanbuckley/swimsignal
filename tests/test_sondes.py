"""EA sonde readings beside the forecast (ingest/sondes.py, build_site.attach_sondes; docs/SONDE-READINGS-CONTRACT-v1.md).
Network-free: readings and stations are shaped as the Hydrology API returned them on 13 Nov 2026, and the river
relation is a stub that answers as water_temperature.river_relation does."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from dipcast.ingest import sondes as sd

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 13, 15, 20, tzinfo=UTC)
HYD = "http://environment.data.gov.uk/hydrology/id/"


def _build_site():
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _station(sid: str, label: str, lat: float, lon: float, props=("amm", "do", "turb")) -> dict:
    suffix = {"amm": "amm-i-subdaily-mgL", "do": "do-i-subdaily-pct", "domg": "do-i-subdaily-mgL",
              "turb": "turb-i-subdaily-ntu", "temp": "temp-i-subdaily-C"}
    return {"@id": HYD + "stations/" + sid, "notation": sid, "label": label, "lat": lat, "long": lon,
            "measures": [{"@id": HYD + f"measures/{sid}-{suffix[p]}", "period": 900} for p in props]}


def _reading(sid: str, suffix: str, hours_ago: float, value, quality="Unchecked") -> dict:
    t = NOW - timedelta(hours=hours_ago)
    return {"measure": {"@id": HYD + f"measures/{sid}-{suffix}"}, "date": t.date().isoformat(),
            "dateTime": t.strftime("%Y-%m-%dT%H:%M:%S"), "value": value, "quality": quality}


BOXTED = _station("E06651A", "STOUR_BOXTEDMILL_E_202604", 51.9561, 0.8879)
BURES = _station("E02254A", "STOUR_BURES MILL_E_201704", 51.9707, 0.7700)
TURB_ONLY = _station("E99999A", "STOUR_SOMEWHERE_E_202601", 51.95, 0.9, props=("turb",))


def test_parse_takes_each_property_latest_usable_reading_and_the_day_of_ammonium():
    readings = [
        _reading("E06651A", "amm-i-subdaily-mgL", 3.0, 1.95), _reading("E06651A", "amm-i-subdaily-mgL", 1.0, 2.00),
        _reading("E06651A", "amm-i-subdaily-mgL", 0.25, 1.89),
        _reading("E06651A", "amm-i-subdaily-mgL", 0.1, 1.5, quality="Suspect"),   # the EA's own word: not used
        _reading("E06651A", "do-i-subdaily-pct", 0.25, 86.0), _reading("E06651A", "do-i-subdaily-mgL", 0.25, 9.5),
        _reading("E06651A", "turb-i-subdaily-ntu", 0.25, -1.2),                     # a fault, not the water
        _reading("E06651A", "turb-i-subdaily-ntu", 2.0, 4.38),
        _reading("E06651A", "amm-i-subdaily-mgL", 30.0, 9.0),                       # over a day old
    ]
    got, dropped = sd.parse(readings, [BOXTED, BURES, TURB_ONLY], NOW)
    by = {s.station_id: s for s in got}
    assert set(by) == {"E06651A", "E02254A"}       # a station with no ammonium measure is not listed
    b = by["E06651A"]
    assert (b.river, b.place, b.where) == ("Stour", "Boxtedmill", "at Boxtedmill")
    assert b.readings["ammonium"].value == 1.89 and b.readings["ammonium"].quality == "Unchecked"
    assert b.readings["ammonium"].observed_at == "2026-11-13T15:05:00Z"
    assert b.readings["dissolved-oxygen"].value == 86.0       # % saturation; mg/L is not read
    assert b.readings["turbidity"].value == 4.38              # the negative one is dropped, the older good one kept
    assert [v for _, v in b.series] == [1.95, 2.00, 1.89]     # oldest first, the suspect and the old one out
    assert by["E02254A"].readings == {}                       # listed, quiet: the page says so
    assert dropped == {"unknown measure": 1, "out of range": 1, "flagged by the EA": 1, "too old": 1}
    assert b.url == "https://environment.data.gov.uk/hydrology/station/E06651A"


def test_fetch_is_two_requests_for_the_whole_build_with_the_three_properties_in_one_list():
    calls = []

    def get(url, params):
        calls.append((url, params))
        return [_reading("E06651A", "amm-i-subdaily-mgL", 0.25, 1.89)] if "readings" in url else [BOXTED]

    got = sd.fetch_sondes(NOW, get=get)
    assert got.requests == 2 and len(calls) == 2
    (u1, p1), (u2, p2) = calls
    assert u1 == "https://environment.data.gov.uk/hydrology/data/readings.json"
    assert u2 == "https://environment.data.gov.uk/hydrology/id/stations.json"
    for p in (p1, p2):
        assert [v for k, v in p if k == "observedProperty"] == ["ammonium", "dissolved-oxygen", "turbidity"]
    assert ("mineq-date", "2026-11-12") in p1 and ("status", "statusActive") in p2
    assert got.sondes[0].readings["ammonium"].value == 1.89


def test_a_refusal_is_tried_once_more_and_counted(monkeypatch):
    answers = iter([503, 200, 200])

    def fake_get(url, params=None, headers=None, timeout=None):
        code = next(answers)
        return httpx.Response(code, json={"items": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(sd.httpx, "get", fake_get)
    monkeypatch.setattr(sd.time, "sleep", lambda s: None)
    assert sd.fetch_sondes(NOW).requests == 3   # 503 then 200 for readings, 200 for stations


def _sonde(sid, river="Stour", lat=51.95, lon=0.89, readings=None):
    return sd.Sonde(station_id=sid, label=sid, river=river, place=sid, where=f"at {sid}", lat=lat, lon=lon,
                    readings=readings or {})


def test_only_upstream_or_at_the_spot_on_the_same_river_nearest_along_the_river():
    near_down, far_up, up, at, other, tidal, broken = (
        _sonde("DOWN", lat=51.951), _sonde("FARUP", lat=51.96), _sonde("UP", lat=51.97), _sonde("AT", lat=51.9502),
        _sonde("OTHER", river="Colne"), _sonde("TIDAL"), _sonde("BROKEN"))
    rel = {"DOWN": ("downstream", 1.3), "FARUP": ("upstream", 21.1), "UP": ("upstream", 7.4), "AT": ("downstream", 0.2),
           "OTHER": ("upstream", 1.0), "TIDAL": None}

    def relate(s):
        if s.station_id == "BROKEN":
            raise ValueError("no snap")
        return rel[s.station_id]

    pick = lambda xs: sd.nearest_on_river(xs, 51.95, 0.89, "River Stour", relate)
    assert pick([near_down, far_up, other, tidal, broken]) is None   # downstream, past the cap, another river, tidal
    s, way, km = pick([near_down, far_up, up, other])
    assert (s.station_id, way, km) == ("UP", "upstream", 7.4)
    s, way, km = pick([up, at])
    assert (s.station_id, way, km) == ("AT", "at", 0.2)               # within AT_KM either way is at the spot
    assert sd.nearest_on_river([up], 51.95, 0.89, None, relate) is None   # no river name: no sonde


def test_attach_never_asks_per_spot_and_lakes_get_none():
    bs = _build_site()
    asked = []
    s = _sonde("E06651A", readings={"ammonium": sd.Reading(1.89, "2026-11-13T15:05:00Z", 0.25, "Unchecked")})

    def fetch(now):
        asked.append(now)
        return sd.Fetched(sondes=[s], requests=2, readings=1, since="2026-11-12")

    spots = [{"id": f"r{i}", "name": f"River {i}", "kind": "river", "river": "River Stour", "lat": 51.95, "lon": 0.89}
             for i in range(40)]
    spots.append({"id": "lake", "name": "A lake", "kind": "lake", "river": "Stour", "lat": 51.95, "lon": 0.89})
    doc = bs.attach_sondes(spots, fetch=fetch, relate=lambda r, x: ("upstream", 7.4), now=NOW)
    assert len(asked) == 1 and doc["fetch"]["requests"] == 2
    assert doc["status"] == "ok" and doc["coverage"]["with_sonde"] == 40 and doc["coverage"]["river_spots"] == 40
    assert "sonde" not in spots[-1]
    b = spots[0]["sonde"]
    assert (b["station_id"], b["direction"], b["river_km"]) == ("E06651A", "upstream", 7.4)
    assert b["readings"]["ammonium"] == {"value": 1.89, "unit": "mg/L", "observed_at": "2026-11-13T15:05:00Z",
                                         "age_hours": 0.25, "quality": "Unchecked"}
    assert "not a count of bacteria" in doc["claim"]["public_wording"]
    assert "No reading does not mean clean water" in doc["claim"]["public_wording"]


def test_an_ea_that_does_not_answer_leaves_the_build_standing():
    bs = _build_site()

    def fetch(now):
        raise httpx.ConnectError("refused")

    spots = [{"id": "r", "name": "River", "kind": "river", "river": "River Stour", "lat": 51.95, "lon": 0.89}]
    doc = bs.attach_sondes(spots, fetch=fetch, now=NOW)
    assert doc["status"] == "unavailable" and "refused" in doc["fetch"]["error"]
    assert doc["spots"] == [] and "sonde" not in spots[0]


@pytest.mark.parametrize("prop", sd.PROPS)
def test_each_property_is_its_fifteen_minute_measure(prop):
    assert prop.suffix.split("-")[1:3] == ["i", "subdaily"] and prop.lo < prop.hi
