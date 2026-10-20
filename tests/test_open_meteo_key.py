"""Open-Meteo's paid plan (OP1, docs/ORGANISER-PIVOT-2026-10.md): with DIPCAST_OPEN_METEO_KEY set, every
request goes to the customer- host with apikey=, and the key reaches nothing else: no log line (httpx's
own included), no error, no cache file's name or contents, no build summary, no page data, no committed
file, and no workflow step but the build's. Unset, the requests are as before. No test touches the
network: rainfall._http_get is replaced by an httpx.MockTransport client."""

import json
import logging
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

import httpx
import pandas as pd
import pytest

from dipcast import config
from dipcast.ingest import rainfall, rainfall_leads

ROOT = Path(__file__).resolve().parents[1]
KEY = "om-test-key-5f2c9a7e"   # made up; no real key is ever in a test

FREE = {
    config.OPEN_METEO_FORECAST: "https://customer-api.open-meteo.com/v1/forecast",
    config.OPEN_METEO_ARCHIVE: "https://customer-archive-api.open-meteo.com/v1/archive",
    config.OPEN_METEO_ENSEMBLE: "https://customer-ensemble-api.open-meteo.com/v1/ensemble",
    rainfall_leads.PREVIOUS_RUNS: "https://customer-previous-runs-api.open-meteo.com/v1/forecast",
}


class FakeOpenMeteo:
    """Answers the forecast (hourly rain or the daily weather), ensemble and archive APIs, whichever host
    they come on, or raises `error(request)` when given. `asked` holds each request."""

    def __init__(self, error=None):
        self.error, self.asked = error, []
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        self.asked.append(request)
        if self.error:
            raise self.error(request)
        q = dict(request.url.params)
        n = len(q["latitude"].split(","))
        t = pd.date_range(pd.Timestamp.now(tz="UTC").normalize(), periods=144, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()
        if "daily" in q:
            days = pd.date_range(pd.Timestamp.now(tz="Europe/London").normalize(), periods=5, freq="D")
            one = {"daily": {"time": days.strftime("%Y-%m-%d").tolist(), "temperature_2m_max": [15.0] * 5,
                             "sunrise": days.strftime("%Y-%m-%dT07:30").tolist(),
                             "sunset": days.strftime("%Y-%m-%dT18:10").tolist()}}
        elif request.url.path == "/v1/ensemble":
            one = {"hourly": {"time": t, "precipitation": [0.1] * 144, "precipitation_member01": [0.5] * 144,
                              "precipitation_member02": [1.0] * 144}}
        else:
            one = {"hourly": {"time": t, "precipitation": [0.4] * 144}}
        return httpx.Response(200, json=[one] * n if n > 1 else one)

    def get(self, url, params, timeout):
        return self.client.get(url, params=params, timeout=timeout)


@pytest.fixture
def om(monkeypatch, tmp_path, caplog):
    """Install a FakeOpenMeteo; the cache is tmp_path; every logger, httpx's too, is captured at DEBUG."""
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "_sleep", lambda s: None)
    rainfall.reset_fallbacks()
    rainfall.reset_requests()
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="httpx")

    def install(**kw):
        f = FakeOpenMeteo(**kw)
        monkeypatch.setattr(rainfall, "_http_get", f.get)
        return f

    yield install
    rainfall.reset_fallbacks()
    rainfall.reset_requests()


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def assert_no_key(caplog, cache: Path, *texts):
    """The key is in no log record, no file name or file under the cache, and none of `texts`."""
    for r in caplog.records:
        assert KEY not in r.getMessage(), f"key in a log line from {r.name}"
    assert KEY not in caplog.text
    for p in cache.rglob("*"):
        assert KEY not in p.name, f"key in a cache file name: {p.name}"
        if p.is_file():
            assert KEY.encode() not in p.read_bytes(), f"key in the cache file {p.name}"
    for t in texts:
        assert KEY not in (t if isinstance(t, str) else json.dumps(t, default=str))


def test_unset_changes_nothing(monkeypatch):
    monkeypatch.delenv(rainfall.KEY_ENV, raising=False)
    params = {"latitude": "51.5", "longitude": "-0.1"}
    for url in FREE:
        assert rainfall.customer(url, params) == (url, params)
    assert rainfall.redact(f"x {KEY} y") == f"x {KEY} y"


def test_blank_key_is_unset(monkeypatch):
    monkeypatch.setenv(rainfall.KEY_ENV, "  ")
    assert rainfall.customer(config.OPEN_METEO_FORECAST, {}) == (config.OPEN_METEO_FORECAST, {})


def test_key_moves_every_api_to_its_customer_host(monkeypatch):
    monkeypatch.setenv(rainfall.KEY_ENV, KEY)
    params = {"latitude": "51.5", "longitude": "-0.1"}
    for url, paid in FREE.items():
        assert rainfall.customer(url, params) == (paid, {**params, "apikey": KEY})
    assert params == {"latitude": "51.5", "longitude": "-0.1"}   # the caller's dict is not changed
    # Already a customer host, or not Open-Meteo's: left alone.
    assert rainfall.customer(FREE[config.OPEN_METEO_FORECAST], params)[0] == FREE[config.OPEN_METEO_FORECAST]
    assert rainfall.customer(config.EA_FLOOD_MONITORING, params) == (config.EA_FLOOD_MONITORING, params)


def test_unset_build_requests_go_to_the_free_hosts(om, monkeypatch):
    monkeypatch.delenv(rainfall.KEY_ENV, raising=False)
    f = om()
    rainfall.fetch_forecast([(51.5, -0.1)], attempts=1)
    rainfall.fetch_ensemble([(51.5, -0.1)])
    assert {r.url.host for r in f.asked} == {"api.open-meteo.com", "ensemble-api.open-meteo.com"}
    assert all("apikey" not in r.url.params for r in f.asked)


def test_key_reaches_the_request_and_nothing_else(om, monkeypatch, tmp_path, caplog):
    """A build's Open-Meteo users with the key set: the spots' forecast, the ensemble, the archive and the
    weather beside the forecast. Each request carries the key to a customer host; nothing else has it."""
    monkeypatch.setenv(rainfall.KEY_ENV, KEY)
    f = om()
    cells = [(51.5, -0.1), (53.4, -2.2)]
    rain = rainfall.fetch_forecast(cells, attempts=1)
    ens = rainfall.fetch_ensemble(cells)
    arc = rainfall.fetch_archive(cells, 2025)
    results = [{"name": "Spot", "lat": 51.5, "lon": -0.1}]
    assert _build_site().attach_weather(results, cache=tmp_path / "weather.json") == 1
    assert not rain.empty and not ens.empty and not arc.empty
    assert {r.url.host for r in f.asked} == {"customer-api.open-meteo.com", "customer-ensemble-api.open-meteo.com",
                                            "customer-archive-api.open-meteo.com"}
    assert all(r.url.params["apikey"] == KEY for r in f.asked)
    # httpx logs each request's full URL at INFO; captured here at DEBUG, so the filter is what keeps it out.
    assert any(r.name == "httpx" and "[key]" in r.getMessage() for r in caplog.records)
    assert_no_key(caplog, tmp_path, rainfall.requests_made(), rainfall.calls_today(), rainfall.fallback_summary(),
                  rainfall.fetch_errors(), rainfall.ensemble_summary(), results,
                  *(d.to_json(date_format="iso") for d in (rain, ens, arc)))


def test_the_httpx_line_would_carry_the_key_without_the_filter(om, monkeypatch, caplog):
    """The check above can fail: httpx's own INFO line has the key until _KeyFilter takes it out."""
    monkeypatch.setenv(rainfall.KEY_ENV, KEY)
    om()
    httpx_log = logging.getLogger("httpx")
    filters = [x for x in httpx_log.filters if isinstance(x, rainfall._KeyFilter)]
    assert filters
    for x in filters:
        monkeypatch.setattr(x, "filter", lambda record: True)
    rainfall.fetch_forecast([(51.5, -0.1)], attempts=1)
    assert any(r.name == "httpx" and KEY in r.getMessage() for r in caplog.records)


def test_a_failure_whose_message_has_the_url_is_redacted(om, monkeypatch, tmp_path, caplog):
    """A connect error that prints its URL (key in the query) is retried, then reported without the key:
    in the log, in fetch_errors (the build summary) and in the ensemble's errors."""
    monkeypatch.setenv(rainfall.KEY_ENV, KEY)
    om(error=lambda req: httpx.ConnectError(f"cannot reach {req.url}", request=req))
    rainfall.fetch_forecast([(51.5, -0.1)], attempts=2)
    rainfall.fetch_ensemble([(51.5, -0.1)])
    errors = rainfall.fetch_errors() + rainfall.ensemble_summary()["errors"]
    assert errors and all("[key]" in e for e in errors)
    assert_no_key(caplog, tmp_path, errors, rainfall.fallback_summary())


def test_an_unexpected_httpx_error_is_replaced(om, monkeypatch, caplog, tmp_path):
    """An httpx error outside the retried ones holds the request, key and all: _request raises an
    OpenMeteoError without it, and no traceback of it shows the original."""
    monkeypatch.setenv(rainfall.KEY_ENV, KEY)
    om(error=lambda req: httpx.UnsupportedProtocol(f"no {req.url}", request=req))
    with pytest.raises(rainfall.OpenMeteoError) as e:
        rainfall._request(config.OPEN_METEO_FORECAST, {"latitude": "51.5", "longitude": "-0.1"}, attempts=1)
    shown = "".join(traceback.format_exception(e.value))
    assert "[key]" in shown and KEY not in shown
    assert e.value.__suppress_context__
    assert_no_key(caplog, tmp_path)


def test_an_unexpected_error_unset_is_raised_as_before(om, monkeypatch):
    monkeypatch.delenv(rainfall.KEY_ENV, raising=False)
    om(error=lambda req: httpx.UnsupportedProtocol("no", request=req))
    with pytest.raises(httpx.UnsupportedProtocol):
        rainfall._request(config.OPEN_METEO_FORECAST, {"latitude": "51.5", "longitude": "-0.1"}, attempts=1)


def test_the_workflow_gives_the_key_to_the_build_step_only():
    """site.yml names the secret once, as an env var of the build step, and no shell line mentions it."""
    lines = (ROOT / ".github" / "workflows" / "site.yml").read_text().splitlines()
    hits = [i for i, l in enumerate(lines) if "DIPCAST_OPEN_METEO_KEY" in l and not l.strip().startswith("#")]
    assert len(hits) == 1
    assert lines[hits[0]].strip() == "DIPCAST_OPEN_METEO_KEY: ${{ secrets.DIPCAST_OPEN_METEO_KEY }}"
    step = next(lines[i] for i in range(hits[0], -1, -1) if lines[i].lstrip().startswith("- name:"))
    assert step.strip() == "- name: Build forecasts and site"
    run = next(lines[i] for i in range(hits[0], len(lines)) if lines[i].lstrip().startswith("run:"))
    assert run.strip() == "run: uv run python scripts/build_site.py"


def test_no_key_in_a_committed_file():
    """No tracked file holds an apikey= with a value (the docs' example abc123 and placeholders such as
    __KEY__ aside), nor, when this runs with the real key set, the key."""
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.split(b"\0")
    real = os.environ.get(rainfall.KEY_ENV, "").strip().encode()
    pattern = re.compile(rb"apikey=(?!abc123|__)[A-Za-z0-9_\-]{6,}")
    for name in filter(None, files):
        p = ROOT / name.decode()
        if not p.is_file() or p.stat().st_size > 20_000_000:
            continue
        data = p.read_bytes()
        assert not pattern.search(data), f"an apikey value in {p.relative_to(ROOT)}"
        assert not real or real not in data, f"the key in {p.relative_to(ROOT)}"
