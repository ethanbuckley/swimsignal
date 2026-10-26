"""Each spot says how old its rain forecast is (docs/REVIEW-2026-10-16.md, A4 and finding 3.4).

fetch_forecast serves a cell's cached forecast up to a day old when Open-Meteo does not send a new one,
or when the day's ration has no room for the request; until this, only the build's warnings said so.
forecast_point now writes the oldest cell's time and age into the spot's `assumptions`, with why it was
not fetched afresh. No test here touches the network: rainfall._http_get is a fake that answers 503 or
200. The page's sentence is tested in tests/site_rain_age.test.cjs, run below."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pandas as pd
import pytest

from dipcast.ingest import rainfall

ROOT = Path(__file__).resolve().parents[1]


def _overflows() -> pd.DataFrame:
    """Two overflows upstream, in two rain cells."""
    return pd.DataFrame({
        "site_id": ["ST1", "ST2"], "company": "Severn Trent Water", "site_name": ["Weir CSO", "Bridge SO"],
        "receiving_watercourse": "RIVER SEVERN", "lat": [52.71, 52.84], "lon": [-2.75, -2.95],
        "status": 0, "has_live": True, "latest_event_start": pd.NaT, "latest_event_end": pd.NaT,
        "lta_spills": [30.0, 10.0], "spill_hours": 100.0, "edm_operational_pct": 95.0, "snap_confidence": "high",
        "distance_m": [2000.0, 5000.0], "lake_distance_m": 0.0, "travel_h": [1.0, 3.0], "weight": [0.5, 0.3]})


def _hours() -> list[str]:
    t0 = pd.Timestamp.now(tz="UTC").floor("D") - pd.Timedelta(days=5)
    return pd.date_range(t0, periods=24 * 12, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()


def _answer(request: httpx.Request) -> httpx.Response:
    n = len(request.url.params["latitude"].split(","))
    h = _hours()
    body = [{"hourly": {"time": h, "precipitation": [0.2] * len(h)}} for _ in range(n)]
    return httpx.Response(200, json=body if n > 1 else body[0])


def _cache(cell, age_h: float) -> None:
    """A cached forecast for `cell`, fetched `age_h` hours ago: older than FORECAST_TTL_S, so a build asks again."""
    h = _hours()
    df = rainfall._to_frame({"hourly": {"time": h, "precipitation": [0.5] * len(h)}}, *cell)
    df["issued_at"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=age_h)
    p = rainfall.CACHE / f"forecast_{rainfall.cell_key(*cell)}.parquet"
    df.to_parquet(p, index=False)
    t = time.time() - age_h * 3600
    os.utime(p, (t, t))


@pytest.fixture
def spot(monkeypatch, tmp_path):
    """forecast_point at a river spot with _overflows upstream, the rain cache in tmp_path and Open-Meteo
    faked: spot(status) runs it with every request answered `status` (200 is a forecast), or by
    `status(request)` where it is a function."""
    from dipcast.model import forecast
    from dipcast.model.transport import PinLocation

    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "_sleep", lambda s: None)
    rainfall.reset_fallbacks()
    ov = _overflows()
    monkeypatch.setattr(forecast, "_net", lambda: None)
    monkeypatch.setattr(forecast, "_overflows", lambda: ov)
    monkeypatch.setattr(forecast, "_model", lambda: None)   # climatology: no spill model file needed
    monkeypatch.setattr(forecast, "_lead_calibration", lambda: {})
    monkeypatch.setattr(forecast, "locate_pin", lambda *a, **k: PinLocation(mode="river", x=0.0, y=0.0, snap=None,
                                                                             watercourse="River Severn"))
    monkeypatch.setattr(forecast, "upstream_overflows", lambda *a, **k: ov.copy())
    monkeypatch.setattr(forecast.ecoli, "load", lambda: None)

    def run(status) -> dict:
        def handle(request):
            if callable(status):
                return status(request)
            return _answer(request) if status == 200 else httpx.Response(status, text="Service Unavailable")
        client = httpx.Client(transport=httpx.MockTransport(handle))
        monkeypatch.setattr(rainfall, "_http_get", lambda url, params, timeout: client.get(url, params=params, timeout=timeout))
        return forecast.forecast_point(52.70, -2.75, days_ahead=4, gauge=False, log_to_store=False)

    run.cells = rainfall.cells_for_sites(ov["lat"], ov["lon"])
    assert len(run.cells) == 2
    yield run
    rainfall.reset_fallbacks()


def test_a_cached_forecast_older_than_the_ttl_gives_the_spot_its_age_and_the_build_still_warns(spot):
    for c in spot.cells:
        _cache(c, age_h=9)
    out = spot(503)
    a = json.loads(json.dumps(out["assumptions"]))   # as it goes into spots.json
    assert 8.9 <= a["rain_age_h"] <= 9.2, a
    assert a["rain_fallback"] == "no answer" and "rain_mixed" not in a
    issued = pd.Timestamp(a["rain_issued_at"])
    assert issued.second == 0 and abs((pd.Timestamp.now(tz="UTC") - issued).total_seconds() / 3600 - 9) < 0.1
    # UK time, as query.issued_at: the offset London had at that moment, which is not today's within
    # 9 h of a clock change (it failed the 25 Oct 2026 builds between 01:00 and 10:00 UTC).
    assert issued.utcoffset() == issued.tz_convert("Europe/London").utcoffset()
    assert all(d["risk"] is not None for d in out["days"])   # the cached rain still made a forecast

    # The build's own warning stays.
    fb = rainfall.fallback_summary()
    assert fb["stale"] == 2 and 8.9 <= fb["oldest_stale_h"] <= 9.1
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    h = build_site.build_health([{"name": "ok", "days": [{"data_status": "ok"}]}] * 3, rain_fallback=fb)
    assert len(h["warnings"]) == 1 and "used a cached forecast up to 9" in h["warnings"][0]


def test_a_request_the_daily_limit_held_back_does_not_blame_open_meteo(spot, monkeypatch):
    for c in spot.cells:
        _cache(c, age_h=7)
    monkeypatch.setattr(rainfall, "DAILY_CALLS", 0.0)   # the day's ration spent: no request is made
    a = spot(200)["assumptions"]
    assert 6.9 <= a["rain_age_h"] <= 7.2 and a["rain_fallback"] == "daily limit"


def test_one_old_cell_among_new_ones_is_part_of_the_rain(spot, monkeypatch):
    _cache(spot.cells[0], age_h=10)
    monkeypatch.setattr(rainfall, "FORECAST_BATCH", 1)   # one cell a request, so one can fail alone
    a = spot(lambda request: httpx.Response(503) if float(request.url.params["latitude"]) == spot.cells[0][0]
             else _answer(request))["assumptions"]
    assert 9.9 <= a["rain_age_h"] <= 10.2 and a["rain_fallback"] == "no answer" and a["rain_mixed"] is True


def test_fresh_rain_is_young_and_a_frame_without_issue_times_says_nothing(spot):
    out = spot(200)
    a = out["assumptions"]
    assert a["rain_age_h"] < 0.1 and "rain_fallback" not in a and "rain_mixed" not in a
    now = pd.Timestamp.now(tz="Europe/London")
    assert rainfall.forecast_age([None, rainfall._empty_forecast()], now) == {}
    bare = pd.DataFrame({"cell_lat": [52.7], "cell_lon": [-2.8], "time": [now], "precip_mm": [0.1]})
    assert rainfall.forecast_age([bare], now) == {}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_page_says_it_over_six_hours_and_not_under():
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "site_rain_age.test.cjs")], capture_output=True, text=True,
                       timeout=60, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
