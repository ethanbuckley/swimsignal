"""The EA sensor replay's offline pieces (scripts/water_temperature_model_eval/wt_sensor_replay.py): the readings CSV,
the London-day rules, the request cap and cache. No request is made."""

import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "water_temperature_model_eval"))
import wt_fetch as wf  # noqa: E402
import wt_sensor_replay as sr  # noqa: E402


def _csv(times, values, quality="Unchecked"):
    q = quality if isinstance(quality, list) else [quality] * len(times)
    lines = ["measure,dateTime,date,value,completeness,quality,qcode"]
    lines += [f"m,{t},{t[:10]},{v},,{qq}," for t, v, qq in zip(times, values, q)]
    return "\n".join(lines) + "\n"


def test_readings_drop_suspect_missing_and_rejected_and_keep_unchecked():
    r = sr.readings(_csv(["2025-06-01T00:00:00", "2025-06-01T00:15:00", "2025-06-01T00:30:00", "2025-06-01T00:45:00"],
                         [14.0, 99.0, 15.0, 16.0], ["Unchecked", "Suspect", "Good", "Rejected"]))
    assert list(r["value"]) == [14.0, 15.0] and list(r["quality"]) == ["Unchecked", "Good"]
    assert str(r["time"].dt.tz) == "UTC"


def test_a_day_needs_90_percent_of_its_readings_and_is_a_london_day_with_a_daytime_mean():
    # 1 June 2025 in London (BST) runs 23:00 UTC on 31 May to 23:00 UTC on 1 June: 96 quarter-hours.
    t = pd.date_range("2025-05-31T23:00Z", periods=96, freq="15min")
    v = np.where((t.tz_convert(sr.LONDON).hour >= 10) & (t.tz_convert(sr.LONDON).hour < 16), 18.0, 14.0)
    d = sr.daily_means(sr.readings(_csv([x.strftime("%Y-%m-%dT%H:%M:%S") for x in t], v)), subdaily=True)
    assert list(d["date"]) == [pd.Timestamp("2025-06-01")] and d["n"].iloc[0] == 96
    assert d["daytime"].iloc[0] == 18.0 and d["mean"].iloc[0] == pytest.approx((24 * 18 + 72 * 14) / 96)
    short = sr.daily_means(sr.readings(_csv([x.strftime("%Y-%m-%dT%H:%M:%S") for x in t[:86]], v[:86])), subdaily=True)
    assert short.empty                                           # 86 of 96: not a day
    # An hourly series needs 22 of 24 (amendment 1); 21 is not a day.
    h = pd.date_range("2025-05-31T23:00Z", periods=24, freq="h")
    hours = [x.strftime("%Y-%m-%dT%H:%M:%S") for x in h]
    assert sr.daily_means(sr.readings(_csv(hours[:22], [15.0] * 22)), subdaily=True)["n"].tolist() == [22]
    assert sr.daily_means(sr.readings(_csv(hours[:21], [15.0] * 21)), subdaily=True).empty


def test_a_daily_series_is_taken_as_given():
    d = sr.daily_means(sr.readings(_csv(["2024-07-01T00:00:00", "2024-07-02T00:00:00"], [17.5, 18.0], "Good")), subdaily=False)
    assert list(d["mean"]) == [17.5, 18.0] and d["daytime"].isna().all()


def test_requests_are_cached_logged_and_capped(tmp_path, monkeypatch):
    seen = []

    def h(req):
        seen.append(str(req.url))
        return httpx.Response(200, text=_csv(["2025-06-01T00:00:00"], [12.0]))
    c = sr.EAReadings(tmp_path, fetch=True, transport=httpx.MockTransport(h), sleep=lambda s: None)
    c.get("E1-temp-i-subdaily-C", "2025-05-01", "2025-10-01")
    c.get("E1-temp-i-subdaily-C", "2025-05-01", "2025-10-01")
    assert len(seen) == 1 and "mineq-date=2025-05-01" in seen[0] and "max-date=2025-10-01" in seen[0] and c.spent() == 1
    monkeypatch.setattr(sr, "MAX_REQUESTS", 1)
    with pytest.raises(wf.Stop, match="cap of 1"):
        c.get("E2-temp-i-subdaily-C", "2025-05-01", "2025-10-01")
    with pytest.raises(wf.Stop, match="not cached"):
        sr.EAReadings(tmp_path / "b", fetch=False).get("E3", "2025-05-01", "2025-10-01")


def test_cells_errors_and_the_stated_sensors():
    assert sr.cell_key(52.0626, -2.6632) == "52.100_-2.700" and sr.cell_key(53.9952, -1.4514) == "54.000_-1.500"
    e = sr.errors([10.0, 12.0, np.nan], [11.0, 11.0, 9.0])
    assert e["days"] == 2 and e["rmse"] == pytest.approx(1.0) and e["bias"] == 0.0 and e["within_2"] == 1.0
    assert len(sr.SENSORS) == 6 and sr.MAX_REQUESTS == 12
    assert {sr.cell_key(s[4], s[5]) for s in sr.SENSORS} == {"52.100_-2.700", "52.400_-2.700", "54.000_-1.500"}
