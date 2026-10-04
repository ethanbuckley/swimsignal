"""Inputs for the Welsh hindcast (Wales plan, task W3): Hafren Dyfrdwy's 2025 discharges in the
edm_events schema, the Welsh rain cells, and the paced ERA5-Land fetch that stays inside
Open-Meteo's free tier and stops at a refusal.

The three discharge rows in HD_ROWS are copied from "Hafren Dyfrdwy Event Duration Monitoring
2025", Hafren Dyfrdwy, via Stream, licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). Everything else here is made up."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from dipcast.ingest import edm_events, rainfall

ROOT = Path(__file__).resolve().parents[1]

NAME = "Llanfair Caereinion - Railway Stn, Penybontfawr, Carno, Llanfyllin - Ffordd Y Cain CSOs"
HD_ROWS = [
    {"SiteId": "10552-ST1", "SiteName": NAME, "OutfallLatitude": "52.651187", "OutfallLongitude": "-3.3227728",
     "EventStart": "2025-11-11T10:17:03Z", "EventEnd": "2025-11-11T10:36:36Z"},
    {"SiteId": "10552-ST1", "SiteName": NAME, "OutfallLatitude": "52.651187", "OutfallLongitude": "-3.3227728",
     "EventStart": "2025-11-11T11:45:50Z", "EventEnd": "2025-11-11T12:03:44Z"},
    {"SiteId": "10552-ST1", "SiteName": NAME, "OutfallLatitude": "52.651187", "OutfallLongitude": "-3.3227728",
     "EventStart": "2025-11-11T14:17:23Z", "EventEnd": "2025-11-11T14:45:47Z"},
]


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("fetch_wales_history", ROOT / "scripts" / "fetch_wales_history.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hd_events_land_in_the_edm_schema_with_numbers_and_utc(monkeypatch, tmp_path):
    asked = {}

    def fake_fetch_all(url, **kw):
        asked["url"], asked["fields"] = url, kw["out_fields"]
        return HD_ROWS

    monkeypatch.setattr(edm_events, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(edm_events, "RAW_CACHE", tmp_path)
    ev = edm_events.fetch_hd_events()
    assert asked["url"].endswith("/HD_EDM_2025_Final_File/FeatureServer/0")
    assert "ReceivingWatercourse" not in asked["fields"]   # the layer has none; ArcGIS refuses the query
    assert list(ev.columns) == edm_events.COLS
    assert set(ev.source) == {edm_events.HD_SOURCE}
    assert ev.site_id.tolist() == ["10552-ST1"] * 3
    assert ev.lat.dtype.kind == "f" and ev.lat.iloc[0] == pytest.approx(52.651187)
    assert str(ev.event_start.dt.tz) == "UTC"
    assert ev.event_start.iloc[0] == pd.Timestamp("2025-11-11 10:17:03", tz="UTC")
    assert ev.duration_h.round(4).tolist() == [round(1173 / 3600, 4), round(1074 / 3600, 4), round(1704 / 3600, 4)]
    assert (tmp_path / "Hafren_Dyfrdwy_2025.parquet").exists()   # a second run reads the cache
    monkeypatch.setattr(edm_events, "fetch_all", lambda *a, **k: pytest.fail("fetched again"))
    assert len(edm_events.fetch_hd_events()) == 3


def test_credit_names_the_licence():
    assert "CC BY 4.0" in edm_events.HD_CREDIT and "CC BY 4.0" in edm_events.__doc__


def test_call_count_follows_open_meteo_rule(script):
    assert script.archive_days(2024, pd.Timestamp("2026-10-04")) == 366
    assert script.archive_days(2026, pd.Timestamp("2026-01-10")) == 4      # stops six days back
    assert script.archive_calls(10, 365) == pytest.approx(10 * 365 / 14)
    assert script.archive_calls(1, 7) == 1          # less than two weeks still counts as one
    assert script.archive_calls(1, 14, variables=20) == 2


def test_rain_cells_count_each_company_and_wales(script):
    dcww = pd.DataFrame({"lat": [51.48, 51.52, 52.03], "lon": [-3.18, -3.21, -2.71]})   # two Cardiff, one Hereford
    hd = pd.DataFrame({"lat": [52.651187], "lon": [-3.3227728]})
    cells = script.rain_cells(dcww, hd, lambda lat, lon: lon < -2.9)
    assert cells.to_dict("records") == [
        {"cell_lat": 51.5, "cell_lon": -3.2, "dcww": 2, "hd": 0, "wales": 2},
        {"cell_lat": 52.0, "cell_lon": -2.7, "dcww": 1, "hd": 0, "wales": 0},
        {"cell_lat": 52.7, "cell_lon": -3.3, "dcww": 0, "hd": 1, "wales": 1},
    ]


def test_wales_shape(script):
    in_wales = script.wales_test()
    assert in_wales(51.48, -3.18)          # Cardiff
    assert in_wales(53.12, -4.13)          # Llanberis
    assert not in_wales(51.45, -2.59)      # Bristol
    assert not in_wales(55.95, -3.19)      # Edinburgh: Scotland, north of 54 N
    assert not in_wales(53.35, -6.26)      # Dublin


class Clock:
    def __init__(self):
        self.t, self.waits = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.waits.append(round(s, 3))
        self.t += s


def _cells(n):
    return [(52.0 + i / 10, -3.0) for i in range(n)]


def test_paced_fetch_spaces_requests_skips_cached_and_stops_at_the_budget(script, monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "BATCH", 2)
    cells = _cells(5)
    (tmp_path / f"archive_{rainfall.cell_key(*cells[0])}_2024.parquet").touch()   # already cached
    asked = []

    def fake_fetch(chunk, year):
        asked.append((len(chunk), year))
        for c in chunk:
            (tmp_path / f"archive_{rainfall.cell_key(*c)}_{year}.parquet").touch()

    clock = Clock()
    per_cell = script.archive_calls(1, 366)
    done = script.fetch_paced(cells, [2024], max_calls=3 * per_cell + 1, per_hour=4000,
                              fetch=fake_fetch, sleep=clock.sleep, clock=clock)
    assert asked == [(2, 2024)]               # a second request of 2 would pass 3 cells' calls
    assert done["requests"] == 1 and done["cell_years"] == 2
    assert done["stopped"].startswith("budget")
    done = script.fetch_paced(cells, [2024], max_calls=1e9, per_hour=4000,
                              fetch=fake_fetch, sleep=clock.sleep, clock=clock)
    assert asked[1:] == [(2, 2024)] and done["stopped"] is None
    assert script.uncached(cells, 2024) == []
    done = script.fetch_paced(cells, [2024], max_calls=1e9, per_hour=4000,
                              fetch=fake_fetch, sleep=clock.sleep, clock=clock)
    assert done["requests"] == 0              # all cached: nothing asked


def test_paced_fetch_waits_between_requests(script, monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "BATCH", 10)

    def fake_fetch(chunk, year):
        for c in chunk:
            (tmp_path / f"archive_{rainfall.cell_key(*c)}_{year}.parquet").touch()

    clock = Clock()
    script.fetch_paced(_cells(30), [2025], max_calls=1e9, per_hour=4000, fetch=fake_fetch, sleep=clock.sleep, clock=clock)
    gap = 3600 * script.archive_calls(10, script.archive_days(2025)) / 4000
    assert clock.waits == [pytest.approx(gap, abs=1e-3)] * 2   # three requests, two gaps of about 235 s


def test_paced_fetch_stops_at_a_refusal(script, monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "BATCH", 2)
    asked = []
    clock = Clock()
    done = script.fetch_paced(_cells(6), [2024, 2025], max_calls=1e9, per_hour=4000,
                              fetch=lambda chunk, year: asked.append(year), sleep=clock.sleep, clock=clock)
    assert asked == [2024]                     # fetch_archive gave up: no files, so no more requests
    assert done["stopped"].startswith("refused") and done["cell_years"] == 0
