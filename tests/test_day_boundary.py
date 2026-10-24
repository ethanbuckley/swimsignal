"""One day boundary for training and inference (docs/DAY-BOUNDARY-TEST-2026-10.md).

Training hands daily_rain_features the archive's UTC stamps; the forecast hands it stamps already in
Europe/London. Both must give the same UK local days, and the labels must be cut on the same days. In
summer time a local day runs from 23:00 UTC the day before. A day holds the stamps 00:00 to 23:00 (each
the rain of the hour ending then, as Open-Meteo's own daily sums take them), so the stamp 23:00 UTC is
where the two used to differ."""

import numpy as np
import pandas as pd
import pytest

from dipcast.model.features import LOCAL_TZ, build_site_days, daily_rain_features, spill_days

CELL = {"cell_lat": 54.2, "cell_lon": -2.6}
DAILY = ["rain_d", "rain_d1", "rain_d2", "rain_3d", "max1h_d", "max3h_d", "max6h_d", "api"]


def _hourly(start: str, days: int, wet: dict[str, float]) -> pd.DataFrame:
    """Hourly rain in UTC, each stamp the hour ending then; `wet` maps UTC stamps to mm."""
    t = pd.date_range(start, periods=24 * days, freq="h", tz="UTC")
    p = pd.Series(0.0, index=t)
    for stamp, mm in wet.items():
        p[pd.Timestamp(stamp, tz="UTC")] = mm
    return pd.DataFrame({**CELL, "time": t, "precip_mm": p.to_numpy()})


def test_a_bst_day_has_the_same_rain_by_the_training_and_the_forecast_path():
    # 10 July 2025 is in summer time: its local day is 9 July 23:00 UTC to 10 July 23:00 UTC.
    rain = _hourly("2025-07-06", 8, {"2025-07-09 23:00": 6.0, "2025-07-10 12:00": 2.0, "2025-07-10 23:00": 5.0})
    # UTC days, as training cut them before: 9 July 6 mm, 10 July 7 mm.
    training = daily_rain_features(rain).set_index("day")                    # as scripts/train.py passes it
    forecast = daily_rain_features(rain.assign(time=rain["time"].dt.tz_convert(LOCAL_TZ))).set_index("day")
    day = pd.Timestamp("2025-07-10", tz=LOCAL_TZ)
    assert training.loc[day, DAILY].equals(forecast.loc[day, DAILY])
    pd.testing.assert_frame_equal(training[DAILY], forecast[DAILY])
    # The stamp 23:00 UTC on 9 July is 00:00 BST on the 10th, so it is the 10th's; the one on 10 July is
    # the 11th's.
    assert training.loc[day, "rain_d"] == 6.0 + 2.0
    assert training.loc[day - pd.DateOffset(days=1), "rain_d"] == 0.0
    assert training.loc[day + pd.DateOffset(days=1), "rain_d"] == 5.0
    assert training.loc[day, "max1h_d"] == 6.0
    assert training.loc[day + pd.DateOffset(days=1), "rain_d1"] == 8.0


def test_a_winter_day_is_the_utc_day():
    rain = _hourly("2025-01-06", 5, {"2025-01-08 00:00": 4.0, "2025-01-08 23:00": 3.0})
    d = daily_rain_features(rain).set_index("day")
    assert str(d.index.tz) == LOCAL_TZ
    assert d.loc[pd.Timestamp("2025-01-07", tz=LOCAL_TZ), "rain_d"] == 0.0
    assert d.loc[pd.Timestamp("2025-01-08", tz=LOCAL_TZ), "rain_d"] == 7.0


@pytest.mark.parametrize("day, hours", [("2026-03-29", 23), ("2026-10-25", 25)])
def test_clock_change_days_are_whole_days(day, hours):
    rain = _hourly("2026-03-25" if day.startswith("2026-03") else "2026-10-21", 8, {})
    rain["precip_mm"] = 1.0
    d = daily_rain_features(rain).set_index("day")
    row = d.loc[pd.Timestamp(day, tz=LOCAL_TZ)]
    assert row["n_hours"] == hours and row["rain_d"] == float(hours)
    nxt = d.loc[pd.Timestamp(day, tz=LOCAL_TZ) + pd.DateOffset(days=1)]
    assert nxt["rain_d1"] == float(hours) and nxt["rain_d"] == 24.0


def test_a_late_evening_spill_in_summer_is_the_next_local_day():
    ev = pd.DataFrame({
        "site_id": ["S", "W", "X"],
        "event_start": pd.to_datetime(["2025-07-09 23:30", "2025-01-09 23:30", "2025-03-29 22:00"], utc=True),
        "event_end": pd.to_datetime(["2025-07-09 23:45", "2025-01-09 23:45", "2025-03-31 00:30"], utc=True),
    })
    sd = spill_days(ev)
    assert str(sd["day"].dt.tz) == LOCAL_TZ
    got = {s: sd[sd.site_id == s].day.dt.strftime("%Y-%m-%d").tolist() for s in "SWX"}
    assert got["S"] == ["2025-07-10"]                     # 00:30-00:45 BST on the 10th
    assert got["W"] == ["2025-01-09"]                     # winter: the UTC date
    # Across the spring clock change (30 Mar 2025, a 23-hour day): 29 Mar 22:00 GMT to 31 Mar 01:30 BST.
    assert got["X"] == ["2025-03-29", "2025-03-30", "2025-03-31"]


def test_labels_and_rain_meet_on_the_same_local_day():
    # Rain stamped 00:00 UTC on 10 July (01:00 BST) and a spill at 00:20-00:40 BST: one local day. On UTC
    # days the rain was the 10th's and the spill the 9th's.
    rain = _hourly("2025-07-06", 8, {"2025-07-10 00:00": 6.0})
    ev = pd.DataFrame({"site_id": ["A"], "event_start": pd.to_datetime(["2025-07-09 23:20"], utc=True),
                       "event_end": pd.to_datetime(["2025-07-09 23:40"], utc=True)})
    sites = pd.DataFrame({"site_id": ["A"], "lat": [54.2], "lon": [-2.6], "company": "X",
                          "lta_spills": 20.0, "spill_hours": 100.0, "edm_operational_pct": 100.0})
    days = pd.date_range("2025-07-08", "2025-07-11", freq="D", tz=LOCAL_TZ)
    sd = build_site_days(sites, daily_rain_features(rain), days, spill_days(ev)).set_index("day")
    wet = pd.Timestamp("2025-07-10", tz=LOCAL_TZ)
    assert sd.loc[wet, "rain_d"] == 6.0 and sd.loc[wet, "y"] == 1     # rain and spill on one local day
    assert sd["y"].sum() == 1 and sd["rain_d"].notna().all()


def test_a_grid_in_another_zone_is_refused():
    rain = _hourly("2025-07-06", 8, {})
    sites = pd.DataFrame({"site_id": ["A"], "lat": [54.2], "lon": [-2.6]})
    utc = pd.date_range("2025-07-07", "2025-07-10", freq="D", tz="UTC")
    with pytest.raises(ValueError, match="different zones"):
        build_site_days(sites, daily_rain_features(rain), utc)
    labels = pd.DataFrame({"site_id": ["A"], "day": [pd.Timestamp("2025-07-08", tz="UTC")]})
    with pytest.raises(ValueError, match="different zones"):
        build_site_days(sites, daily_rain_features(rain), utc.tz_convert(LOCAL_TZ).normalize(), labels)


def test_naive_times_are_refused():
    rain = _hourly("2025-07-06", 3, {})
    with pytest.raises(TypeError):
        daily_rain_features(rain.assign(time=rain["time"].dt.tz_localize(None)))
    assert np.isfinite(daily_rain_features(rain)["rain_d"]).any()
