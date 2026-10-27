"""The build's Open-Meteo use fits the free 10,000 calls a day, however many builds run.

Open-Meteo weighs a request per location (call_weight, after its own calculateQueryWeight). Each
user of the forecast API asks for a cell only once its cache is older than a floor, and a ledger
in the rain cache adds up the day's calls, so a request past the ration is not made. No test here
touches the network: rainfall._http_get is replaced by an httpx.MockTransport client."""

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import httpx
import pandas as pd
import pytest

from dipcast.ingest import rainfall

ROOT = Path(__file__).resolve().parents[1]


def _bap():
    spec = importlib.util.spec_from_file_location("build_any_point", ROOT / "scripts" / "build_any_point.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


class Fake:
    """Open-Meteo's forecast API: every request answered with three hours of rain per location,
    or with `body` (text) when given. `asked` holds each request's cells."""

    def __init__(self, body=None):
        self.body, self.asked = body, []
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        lats = request.url.params["latitude"].split(",")
        lons = request.url.params["longitude"].split(",")
        self.asked.append([(float(a), float(b)) for a, b in zip(lats, lons, strict=True)])
        if self.body is not None:
            return httpx.Response(200, text=self.body)
        hours = pd.date_range("2026-10-16", periods=3, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()
        body = [{"hourly": {"time": hours, "precipitation": [0.0, 0.4, 1.2]}} for _ in lats]
        return httpx.Response(200, json=body if len(body) > 1 else body[0])

    def get(self, url, params, timeout):
        return self.client.get(url, params=params, timeout=timeout)


@pytest.fixture
def om(monkeypatch, tmp_path):
    """A Fake installed, the rain cache (and so the ledger) in tmp_path: om() or om(body=...)."""
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "_sleep", lambda s: None)
    rainfall.reset_fallbacks()

    def install(**kw):
        f = Fake(**kw)
        monkeypatch.setattr(rainfall, "_http_get", f.get)
        return f

    yield install
    rainfall.reset_fallbacks()


def _cells(n, lat0=50.0):
    return [(round(lat0 + 0.1 * i, 3), -2.0) for i in range(n)]


def _age(cell, hours):
    p = rainfall.CACHE / f"forecast_{rainfall.cell_key(*cell)}.parquet"
    t = time.time() - hours * 3600
    os.utime(p, (t, t))


# ------------------------------------------------------------------ the weight
def test_call_weight_is_open_meteos_own_rule():
    # The cases of Open-Meteo's own test (Tests/AppTests/OutputformatTests.swift, 16 Oct 2026).
    assert round(rainfall.call_weight(1, 7671), 5) == 54.79286        # 2000-01-01 to 2021-01-01, one variable
    assert round(rainfall.call_weight(1, 7671, variables=2), 5) == 109.58571
    assert rainfall.call_weight(1, 7) == 1 and rainfall.call_weight(1, 7, variables=15) == 1.5
    assert rainfall.call_weight(2, 31) == 2.0                           # "1 month data, two locations, one variable"
    assert round(rainfall.call_weight(2, 31, variables=15), 4) == 6.6429


def test_a_forecast_cell_is_one_call_however_many_past_days():
    # 37 days of one variable: max(1, 0.1 x 37/14 = 0.26) = 1 a cell, not 37/14 = 2.64.
    assert rainfall.forecast_weight(332) == 332
    assert rainfall.forecast_weight(332, past_days=1) == rainfall.forecast_weight(332)
    from dipcast.scottish_shadow import forecast_calls
    assert forecast_calls(150) == 150


# ------------------------------------------------------------------ the ledger
def test_the_ledger_adds_up_the_day_and_starts_again_at_midnight_utc(om):
    day = pd.Timestamp("2026-10-16T23:59:00Z").timestamp()
    rainfall.spend(50, "spots", now=day)
    rainfall.spend(105, "weather", now=day)
    rainfall.spend(50, "spots", now=day)
    d = rainfall.calls_today(now=day)
    assert d["day"] == "2026-10-16" and d["calls"] == 205 and d["by"] == {"spots": 100, "weather": 105}
    assert rainfall.calls_left(now=day) == rainfall.DAILY_CALLS - 205
    after = day + 120   # 00:01 UTC: Open-Meteo's own count has started again
    assert rainfall.calls_today(now=after)["calls"] == 0 and rainfall.calls_left(now=after) == rainfall.DAILY_CALLS
    (rainfall.CACHE / rainfall.LEDGER_NAME).write_text("{not json")
    assert rainfall.calls_today(now=day)["calls"] == 0   # a torn ledger is a fresh day, not a stopped build


def test_fetch_forecast_books_each_request_and_makes_none_past_the_ration(om, monkeypatch):
    fake = om()
    monkeypatch.setattr(rainfall, "DAILY_CALLS", 60.0)
    cells = _cells(70)   # two requests: 50 cells, then 20
    rainfall.fetch_forecast(cells[:50])
    for c in cells[50:55]:   # five of the rest have a cached forecast 5 hours old
        rainfall._to_frame({"hourly": {"time": ["2026-10-16T00:00"], "precipitation": [1.0]}}, *c).assign(
            issued_at=pd.Timestamp.now(tz="UTC")).to_parquet(rainfall.CACHE / f"forecast_{rainfall.cell_key(*c)}.parquet")
        _age(c, 5)
    df = rainfall.fetch_forecast(cells)
    assert len(fake.asked) == 1 and len(fake.asked[0]) == 50   # the 20 would take the day to 70 of 60
    d = rainfall.calls_today()
    assert d["calls"] == 50 and d["by"] == {"spots": 50} and d["held"] == {"spots": 20}
    assert rainfall.fallback_summary()["stale"] == 5 and rainfall.fallback_summary()["missing"] == 15
    assert set(zip(df["cell_lat"], df["cell_lon"], strict=True)) == set(cells[:55])


def test_an_answer_cut_short_is_counted_though_not_read(om):
    fake = om(body='[{"hourly": {"time": ["2026-')
    rainfall.fetch_forecast(_cells(3), attempts=1)
    assert len(fake.asked) == 1 and rainfall.calls_today()["by"] == {"spots": 3}


# ------------------------------------------------------------------ the floors
def test_a_day_of_builds_every_30_minutes_asks_each_cell_by_its_floor_not_each_build(om, monkeypatch):
    """48 builds 30 minutes apart over one UTC day: the spots' cells are asked for every 2 hours
    (12 times), the click-anywhere cells every 12 hours (twice). The ledger adds up to that."""
    fake = om()
    bap = _bap()
    clock = {"t": pd.Timestamp("2026-10-17T00:00:30Z").timestamp()}
    monkeypatch.setattr(time, "time", lambda: clock["t"])
    spots, extra = _cells(3), _cells(5, lat0=52.0)
    sub = pd.DataFrame({"lat": [c[0] for c in spots + extra], "lon": [c[1] for c in spots + extra]})

    def touch_new():   # each file written in this build gets the build's time, as a real build would
        for req in fake.asked[seen:]:
            for c in req:
                p = rainfall.CACHE / f"forecast_{rainfall.cell_key(*c)}.parquet"
                os.utime(p, (clock["t"], clock["t"]))

    for k in range(48):
        seen = len(fake.asked)
        rainfall.reset_fallbacks()
        rainfall.fetch_forecast(spots)
        touch_new()
        seen = len(fake.asked)
        bap.any_point_rain(sub, budget=300)
        touch_new()
        clock["t"] += 1800
    asked = [c for req in fake.asked for c in req]
    assert {c: asked.count(c) for c in spots} == dict.fromkeys(spots, 12)
    assert {c: asked.count(c) for c in extra} == dict.fromkeys(extra, 2)
    d = rainfall.calls_today(now=clock["t"] - 1800)
    assert d["by"] == {"spots": 36, "anypoint": 10} and d["calls"] == 46


def test_the_floors_fit_the_free_tier_at_a_build_every_30_minutes():
    """The day's most at a build every 30 minutes, with 16 Oct 2026's counts: 332 spot cells, about
    1,270 click-anywhere cells the spots do not share, 105 weather points, 320 Scottish cells. The
    weather can be asked for once more when the local day turns. And the soil moisture the river E. coli
    estimate reads: at most soil.MAX_ATTEMPTS calls per river spot cell per UTC day (one, and one retry after a
    failure; soil.fetch), 62 cells on 26 Oct 2026."""
    day = rainfall.planned_day(332, 1270, 105, 320, 62, **_floors())
    assert day["by"] == {"spots": 3984, "anypoint": 2540, "weather": 945, "scotland": 1280, "soil": 124}
    assert day["calls"] == 8873 and day["spare"] == 127
    assert day["calls"] <= rainfall.DAILY_CALLS < 10_000


def test_the_planned_hour_and_month_fit_the_free_tier():
    """Open-Meteo's free tier has an hourly cap (5,000), a minute cap (600) and a monthly one (300,000) beside the
    daily one; planned_day is a day only. Only the day is enforced in the code; the month follows from the day's
    ration; the hour and the minute are not enforced (rainfall.py). The hour, bounded from the floors: 2,588 for
    any number of builds; for the cron's two builds an hour, 1,898 with the per-build caps and 4,966 with every
    build asking for everything (the review of 27 Oct 2026 made that 4,302 without the ensemble's 332 cells)."""
    from dipcast import scottish_shadow
    from dipcast.ingest import soil
    assert 31 * rainfall.DAILY_CALLS == 279_000 < rainfall.FREE_MONTH_CALLS
    assert 31 * rainfall.planned_day(332, 1270, 105, 320, 62, **_floors())["calls"] == 275_063
    h = rainfall.planned_hour(332, 1270, 105, 320, 62, 332, anypoint_per_build=_bap().RAIN_CELLS_PER_BUILD,
                              scotland_per_build=scottish_shadow.RAIN_CELLS_PER_BUILD, soil_attempts=soil.MAX_ATTEMPTS)
    assert h["any_builds"] == 332 + 1270 + 2 * 105 + 320 + 124 + 332 == 2588 < rainfall.FREE_HOUR_CALLS
    assert h["by_scheduled"] == {"spots": 332, "anypoint": 600, "weather": 210, "scotland": 300, "soil": 124, "ensemble": 332}
    assert h["scheduled"] == 1898
    assert h["scheduled_crude"] == 2 * (332 + 1270 + 105 + 320 + 124 + 332) == 4966 < rainfall.FREE_HOUR_CALLS
    # The minute is not bounded. Each step of a build alone asks for under 600 (spots 332, ensemble 332,
    # click-anywhere 300, Scotland 150), but two steps back to back can pass it: a 429 is retried (_request).
    assert max(332, 332, _bap().RAIN_CELLS_PER_BUILD, scottish_shadow.RAIN_CELLS_PER_BUILD) < rainfall.FREE_MINUTE_CALLS


def _floors(*keep):
    bap, bs = _bap(), _build_site()
    from dipcast import scottish_shadow
    from dipcast.ingest import soil
    f = {"anypoint_refresh_h": bap.RAIN_REFRESH_H, "weather_refresh_h": bs.WEATHER_REFRESH_H,
         "scotland_refresh_h": scottish_shadow.RAIN_REFRESH_H, "soil_attempts": soil.MAX_ATTEMPTS}
    return {k: v for k, v in f.items() if not keep or k in keep}


def test_what_one_more_listed_spot_adds_to_the_planned_day():
    """A spot whose cells the spots already ask for adds its weather point alone, 9 calls a day. Each
    new cell adds the spots' 12 a day, less the 2 click-anywhere paid where it was one of its cells; a
    river spot in a new cell adds its soil, 2. The counts below are what planned_day gives when the
    spot is added to the counts, so the two can never disagree."""
    f = _floors("anypoint_refresh_h", "weather_refresh_h", "soil_attempts")
    assert rainfall.new_spot_calls(0, 0, False, **f) == 9
    assert rainfall.new_spot_calls(1, 1, True, **f) == 9 + 12 - 2 + 2 == 21
    assert rainfall.new_spot_calls(1, 0, False, **f) == 21   # a pin cell with no overflow in it
    base = rainfall.planned_day(332, 1270, 105, 320, 62, **_floors())["calls"]
    for new, from_anypoint, soil_cell in ((0, 0, False), (1, 1, True), (4, 4, True), (15, 15, True)):
        after = rainfall.planned_day(332 + new, 1270 - from_anypoint, 106, 320, 62 + soil_cell, **_floors())["calls"]
        assert after - base == rainfall.new_spot_calls(new, from_anypoint, soil_cell, **f)
    # Today's spare, 127 calls: 14 spots that share every cell, or 6 that each add one click-anywhere cell and a soil cell.
    assert 127 // rainfall.new_spot_calls(0, 0, False, **f) == 14 and 127 // rainfall.new_spot_calls(1, 1, True, **f) == 6


def test_the_spots_rain_cells_are_their_own_and_their_upstream_overflows(monkeypatch):
    """build_site.spot_rain_cells, what prefetch_rain asks for and scripts/spot_cost.py prices a new spot
    against: each spot's own cell and its upstream overflows' cells, once each; a soil cell for a river
    spot only; a spot that cannot be placed keeps its own cell and adds nothing else."""
    from types import SimpleNamespace
    bs = _build_site()
    up = {"river": pd.DataFrame({"lat": [54.41, 54.52], "lon": [-2.96, -2.96]}),
          "lake": pd.DataFrame({"lat": [54.36], "lon": [-2.94]})}

    def pin(net, lon, lat, kind_hint=None, river_hint=None, name=None):
        if name == "nowhere":
            raise ValueError("no link within 1 km")
        return SimpleNamespace(mode="lake" if kind_hint == "lake" else "river")
    monkeypatch.setattr(bs, "locate_pin", pin)
    monkeypatch.setattr(bs, "upstream_overflows", lambda net, p, ov, velocity_ms: up[p.mode])
    spots = pd.DataFrame({"name": ["a river", "a lake", "nowhere"], "kind": ["river", "lake", "river"],
                          "river": ["River Rothay", "", "River Brathay"],
                          "lat": [54.43, 54.36, 52.0], "lon": [-2.97, -2.94, -1.0]})
    cells, soil_cells = bs.spot_rain_cells(spots, None, None)
    assert cells == [(52.0, -1.0), (54.4, -3.0), (54.4, -2.9), (54.5, -3.0)]
    assert soil_cells == [(54.4, -3.0)]


# ------------------------------------------------------------------ the weather
def _weather_request(seen):
    def request(url, params, timeout=30):
        seen.append(params["latitude"].split(","))
        return [{"daily": {"time": ["2026-10-17"], "temperature_2m_max": [12.0], "sunrise": ["2026-10-17T07:30"],
                           "sunset": ["2026-10-17T18:10"]}} for _ in params["latitude"].split(",")]
    return request


def test_weather_is_asked_for_once_in_3_hours_and_only_for_spots_not_cached(om, tmp_path):
    bs = _build_site()
    seen, cache = [], tmp_path / "weather.json"
    spots = [{"id": "a", "name": "A", "lat": 54.0, "lon": -2.0}, {"id": "b", "name": "B", "lat": 54.1, "lon": -2.1}]
    assert bs.attach_weather(spots, request=_weather_request(seen), cache=cache) == 2 and len(seen) == 1
    again = [dict(s) for s in spots] + [{"id": "c", "name": "C", "lat": 54.2, "lon": -2.2}]
    assert bs.attach_weather(again, request=_weather_request(seen), cache=cache) == 3
    assert seen[1] == ["54.200"] and again[0]["weather"]["days"][0]["tmax"] == 12
    assert rainfall.calls_today()["by"] == {"weather": 3}
    # Three hours on, all of them are asked for again.
    d = json.loads(cache.read_text())
    cache.write_text(json.dumps({**d, "fetched_at": time.time() - 3.1 * 3600}))
    bs.attach_weather([dict(s) for s in again], request=_weather_request(seen), cache=cache)
    assert len(seen[2]) == 3

    # A failed call leaves today's cached answer in place.
    def broken(url, params, timeout=30):
        raise RuntimeError("open-meteo request failed")
    cache.write_text(json.dumps({**json.loads(cache.read_text()), "fetched_at": time.time() - 4 * 3600}))
    late = [dict(s) for s in again]
    assert bs.attach_weather(late, request=broken, cache=cache) == 3 and late[2]["weather"]["days"][0]["sunset"] == "18:10"
    # One from another day is not used: its first day would be yesterday.
    cache.write_text(json.dumps({**json.loads(cache.read_text()), "day": "2026-10-01"}))
    assert bs.attach_weather([dict(s) for s in again], request=broken, cache=cache) == 0


def test_weather_is_not_asked_for_once_the_ration_is_spent(om, tmp_path, monkeypatch):
    bs = _build_site()
    monkeypatch.setattr(rainfall, "DAILY_CALLS", 1.0)
    seen = []
    spots = [{"id": "a", "name": "A", "lat": 54.0, "lon": -2.0}, {"id": "b", "name": "B", "lat": 54.1, "lon": -2.1}]
    assert bs.attach_weather(spots, request=_weather_request(seen), cache=tmp_path / "w.json") == 0
    assert seen == [] and rainfall.calls_today()["held"] == {"weather": 2}
