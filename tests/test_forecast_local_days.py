"""The forecast's days are Europe/London days; Open-Meteo is asked for UTC days.

From 16 Sep to 12 Oct 2026 every build issued between 23:00 and 00:00 UTC had no rain for its fifth
day. In summer time the local date there is a day ahead of the UTC one, and the fifth local day ended
an hour into a UTC day the request did not cover: one hour of rain, under MIN_HOURS_PER_DAY. One build
at 00:09 UTC on 12 Oct had the same gap for the cells whose forecast came from the cache a 23:xx build
had left. The fake Open-Meteo here answers as the real one did on 12 Oct 2026 with timezone=UTC: hourly
stamps from 00:00 UTC `past_days` before the request's UTC date to 23:00 on the last of `forecast_days`.
No test here touches the network."""

import httpx
import pandas as pd
import pytest

from dipcast import config
from dipcast.ingest import rainfall
from dipcast.model import ecoli
from dipcast.model.features import daily_rain_features

CELL = (51.5, -1.3)


def _open_meteo(fetched_at: pd.Timestamp):
    def handle(request: httpx.Request) -> httpx.Response:
        q = request.url.params
        assert q["timezone"] == "UTC"
        day = fetched_at.floor("D")
        t = pd.date_range(day - pd.Timedelta(days=int(q["past_days"])),
                          day + pd.Timedelta(days=int(q["forecast_days"])), freq="h", inclusive="left")
        return httpx.Response(200, json={"hourly": {"time": t.strftime("%Y-%m-%dT%H:%M").tolist(),
                                                    "precipitation": [0.1] * len(t)}})
    client = httpx.Client(transport=httpx.MockTransport(handle))
    return lambda url, params, timeout: client.get(url, params=params, timeout=timeout)


@pytest.mark.parametrize("fetched_at, built_at", [
    ("2026-10-12 12:00", "2026-10-12 12:00"),   # summer time, midday
    ("2026-10-12 23:30", "2026-10-12 23:30"),   # summer time, 00:30 local: the fifth day had 1 hour
    ("2026-10-11 23:10", "2026-10-12 00:09"),   # a 23:xx forecast served from the cache after midnight
    ("2026-10-20 23:30", "2026-10-20 23:30"),   # the fifth day is 25 Oct, 25 hours long
    ("2026-11-15 23:30", "2026-11-15 23:30"),   # winter time
])
def test_every_day_shown_has_its_rain_at_any_hour(fetched_at, built_at, monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "_http_get", _open_meteo(pd.Timestamp(fetched_at, tz="UTC")))
    rainfall.reset_fallbacks()
    rain = rainfall.fetch_forecast([CELL])
    rainfall.reset_fallbacks()
    local = rain.assign(time=rain["time"].dt.tz_convert("Europe/London"))   # as forecast.spill_probabilities
    days = pd.date_range(pd.Timestamp(built_at, tz="UTC").tz_convert("Europe/London").floor("D"),
                         periods=config.FORECAST_DAYS, freq="D")
    daily = daily_rain_features(local).set_index("day")
    assert daily["rain_d"].reindex(days).notna().all(), daily["n_hours"].reindex(days).tolist()
    # The E. coli figure's 48 h window, ending at noon on each day, is whole too.
    hourly = local.set_index("time")["precip_mm"]
    _, _, cov48, _ = ecoli.rain_windows(hourly, days + pd.Timedelta(hours=ecoli.SAMPLE_HOUR), return_coverage=True)
    assert (cov48 == 1.0).all(), cov48.tolist()
