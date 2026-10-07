"""Open-Meteo retries and the cached-rain fallback, against a fake HTTP layer (httpx.MockTransport).

The scheduled build at 00:29 UTC on 6 Oct 2026 stopped before any forecast: one 50-cell prefetch
request timed out four times (TLS handshake and read) and then got a 503, and fetch_forecast raised.
No test here touches the network: rainfall._http_get is replaced by a MockTransport client, and
rainfall._sleep records the waits instead of sleeping."""

import os
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from dipcast.ingest import rainfall

HANDSHAKE = "_ssl.c:983: The handshake operation timed out"


def _hours():
    return pd.date_range("2026-10-06", periods=3, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()


def _ok(request: httpx.Request) -> httpx.Response:
    n = len(request.url.params["latitude"].split(","))
    body = [{"hourly": {"time": _hours(), "precipitation": [0.0, 0.4, 1.2]}} for _ in range(n)]
    return httpx.Response(200, json=body if n > 1 else body[0])


class FakeOpenMeteo:
    """Answers each request with the next item of `script` (the last repeats): a status code, a
    (status, headers) pair, "ok", or an exception to raise, such as a TLS handshake timeout."""

    def __init__(self, *script):
        self.script, self.requests = list(script), []
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        self.requests.append(request)
        step = self.script[min(len(self.requests), len(self.script)) - 1]
        if isinstance(step, Exception):
            raise step
        if step == "ok":
            return _ok(request)
        status, headers = step if isinstance(step, tuple) else (step, {})
        return httpx.Response(status, headers=headers, text="Service Unavailable")

    def get(self, url, params, timeout):
        return self.client.get(url, params=params, timeout=timeout)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    """Install a FakeOpenMeteo: fake(*script). Waits are recorded in fake.waits, the cache is tmp_path."""
    waits = []
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "_sleep", waits.append)
    monkeypatch.setattr(rainfall, "_random", lambda: 1.0)   # the longest wait each time
    rainfall.reset_fallbacks()

    def install(*script):
        f = FakeOpenMeteo(*script)
        monkeypatch.setattr(rainfall, "_http_get", f.get)
        f.waits = waits
        return f

    yield install
    rainfall.reset_fallbacks()


def _cache(tmp_path, cell, age_h):
    """A cached forecast for `cell`, written `age_h` hours ago."""
    df = rainfall._to_frame({"hourly": {"time": _hours(), "precipitation": [2.0, 2.0, 2.0]}}, *cell)
    df["issued_at"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=age_h)
    p = tmp_path / f"forecast_{rainfall.cell_key(*cell)}.parquet"
    df.to_parquet(p, index=False)
    t = time.time() - age_h * 3600
    os.utime(p, (t, t))


A, B, C = (52.3, 0.0), (52.4, -0.1), (51.5, -1.2)


def test_a_503_then_success_is_retried_and_cached(fake, tmp_path):
    f = fake(503, "ok")
    got = rainfall.fetch_forecast([A, B])
    assert len(f.requests) == 2
    assert len(got) == 6 and set(zip(got["cell_lat"], got["cell_lon"], strict=True)) == {A, B}
    assert f.waits == [2.0]                         # first wait: 1-2 s, the longest drawn here
    assert (tmp_path / f"forecast_{rainfall.cell_key(*A)}.parquet").exists()
    assert rainfall.fallback_summary() is None


def test_persistent_503_falls_back_to_the_cached_rain_and_the_build_says_so(fake, tmp_path):
    _cache(tmp_path, A, age_h=6)      # fresh enough to stand in
    _cache(tmp_path, C, age_h=30)     # too old: over a day
    f = fake(503)
    got = rainfall.fetch_forecast([A, B, C])       # does not raise
    assert len(f.requests) == 5                    # attempts, then give up
    assert f.waits == [2.0, 4.0, 8.0, 16.0] and sum(f.waits) <= rainfall.MAX_WAIT_S
    assert set(zip(got["cell_lat"], got["cell_lon"], strict=True)) == {A}   # B never cached, C too old
    assert (got["precip_mm"] == 2.0).all()
    fb = rainfall.fallback_summary()
    assert fb["cells"] == 3 and fb["stale"] == 1 and fb["missing"] == 2
    assert 5.9 <= fb["oldest_stale_h"] <= 6.1 and fb["errors"] == ["open-meteo request failed: HTTP 503"]

    # A spot's own fetch later in the build does not ask for the failed cells again.
    again = rainfall.fetch_forecast([A])
    assert len(f.requests) == 5 and len(again) == 3

    # The build publishes and says what happened.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_site
    good = {"name": "ok", "days": [{"data_status": "ok"}]}
    h = build_site.build_health([good] * 5, rain_fallback=fb)
    assert h["rain_fallback"] == fb and len(h["warnings"]) == 1
    assert "3 cells" in h["warnings"][0] and "1 used a cached forecast up to 6" in h["warnings"][0]
    assert "HTTP 503" in h["warnings"][0]


def test_a_tls_handshake_timeout_is_retried(fake):
    f = fake(httpx.ConnectTimeout(HANDSHAKE), httpx.ReadTimeout("The read operation timed out"), "ok")
    got = rainfall.fetch_forecast([A])
    assert len(f.requests) == 3 and len(got) == 3 and f.waits == [2.0, 4.0]
    assert rainfall.fallback_summary() is None


def test_tls_timeouts_that_never_clear_leave_the_cell_without_rain_not_a_failed_build(fake):
    f = fake(httpx.ConnectTimeout(HANDSHAKE))
    got = rainfall.fetch_forecast([B], attempts=2)
    assert len(f.requests) == 2 and got.empty
    assert str(got["time"].dtype) == "datetime64[ns, UTC]"   # typed, so callers can still use .dt
    assert rainfall.fallback_summary()["missing"] == 1
    assert rainfall.fetch_errors() == [f"open-meteo request failed: {HANDSHAKE}"]


def test_retry_after_is_respected_and_a_long_one_ends_the_retries(fake):
    f = fake((429, {"Retry-After": "7"}), "ok")
    rainfall.fetch_forecast([A])
    assert f.waits == [7.0] and len(f.requests) == 2

    rainfall.reset_fallbacks()
    f.waits.clear()
    f = fake((429, {"Retry-After": "3600"}))   # a quota, not a blip
    rainfall.fetch_forecast([B])
    assert f.waits == [] and len(f.requests) == 1


def test_a_client_error_is_not_retried(fake):
    f = fake(400)
    with pytest.raises(rainfall.OpenMeteoError, match="HTTP 400"):
        rainfall._request("https://api.open-meteo.com/v1/forecast", {"latitude": "52.3"})
    assert len(f.requests) == 1 and f.waits == []


def test_after_two_failed_requests_in_a_row_no_more_are_made(fake, monkeypatch):
    monkeypatch.setattr(rainfall, "FORECAST_BATCH", 1)
    f = fake(503)
    got = rainfall.fetch_forecast([A, B, C], attempts=2)
    assert got.empty
    assert len(f.requests) == 2 * rainfall.OUTAGE_AFTER   # the third chunk is not requested
    assert rainfall.fallback_summary()["missing"] == 3


def test_the_normal_path_makes_one_request_per_batch_and_none_for_cached_cells(fake):
    cells = [(50.0 + i / 10, -1.0) for i in range(120)]
    f = fake("ok")
    rainfall.fetch_forecast(cells)
    assert len(f.requests) == 3 and f.waits == []   # ceil(120 / 50)
    rainfall.fetch_forecast(cells)
    assert len(f.requests) == 3                    # all cached under an hour old


def test_retry_after_as_an_http_date():
    when = pd.Timestamp.now(tz="UTC") + pd.Timedelta(seconds=30)
    r = httpx.Response(503, headers={"Retry-After": when.strftime("%a, %d %b %Y %H:%M:%S GMT")})
    assert 25 <= rainfall.retry_after_s(r) <= 31
    assert rainfall.retry_after_s(httpx.Response(503)) is None


def test_spill_probabilities_with_no_rain_are_unknown_not_an_error():
    from dipcast.model.forecast import spill_probabilities
    ov = pd.DataFrame({"site_id": ["X1", "X2"], "lat": [52.3, 52.4], "lon": [0.0, -0.1]})
    days = pd.date_range("2026-10-06", periods=3, freq="D", tz="Europe/London")
    p, ok, mm = spill_probabilities(ov, days, None, return_rain=True, rain=rainfall._empty_forecast())
    assert p.shape == ok.shape == mm.shape == (2, 3)
    assert np.isnan(p).all() and not ok.any() and np.isnan(mm).all()
