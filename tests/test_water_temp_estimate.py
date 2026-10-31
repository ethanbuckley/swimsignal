"""The river water-temperature estimate (dipcast.model.water_temp, build_site.attach_water_temperature_estimate) and
the air temperature on the rain request (ingest.rainfall). docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md: rivers
passed, lakes failed, so only river spots get an estimate, and only from May to September."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dipcast import config
from dipcast.ingest import rainfall
from dipcast.model import water_temp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "water_temperature_model_eval"))
sys.path.insert(0, str(ROOT / "scripts"))


# ---- the rain request ----------------------------------------------------------------------------------------------
def test_the_rain_request_asks_for_air_temperature_at_no_extra_weight():
    assert rainfall.FORECAST_VARIABLES == "precipitation,temperature_2m"
    assert rainfall.forecast_weight(1) == 1.0 and rainfall.forecast_weight(332) == 332
    assert rainfall.call_weight(1, config.FORECAST_PAST_DAYS + config.FORECAST_DAYS + 1, 2) == 1.0


def test_rain_values_are_the_same_with_or_without_temperature():
    t = ["2026-07-01T00:00", "2026-07-01T01:00", "2026-07-01T02:00"]
    rain = [0.0, 0.4, 1.2]
    a = rainfall._to_frame({"hourly": {"time": t, "precipitation": rain}}, 51.5, -0.1)
    b = rainfall._to_frame({"hourly": {"time": t, "precipitation": rain, "temperature_2m": [14.0, 13.5, 13.1]},
                            "elevation": 42.0}, 51.5, -0.1)
    pd.testing.assert_series_equal(a["precip_mm"], b["precip_mm"])
    assert a["air_c"].isna().all() and list(b["air_c"]) == [14.0, 13.5, 13.1]
    assert a["elevation_m"].isna().all() and (b["elevation_m"] == 42.0).all()


def test_fetch_forecast_sends_both_variables(tmp_path, monkeypatch):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    seen = []

    def fake(url, params, **kw):
        seen.append(params)
        h = pd.date_range("2026-07-01", periods=3, freq="h", tz="UTC").strftime("%Y-%m-%dT%H:%M").tolist()
        return [{"hourly": {"time": h, "precipitation": [0.0, 0.1, 0.2], "temperature_2m": [15.0, 15.5, 16.0]},
                 "elevation": 12.0}]
    monkeypatch.setattr(rainfall, "_request", fake)
    monkeypatch.setattr(rainfall, "may_spend", lambda w, what: True)
    monkeypatch.setattr(rainfall, "spend", lambda w, what: None)
    df = rainfall.fetch_forecast([(51.5, -0.1)])
    assert seen[0]["hourly"] == "precipitation,temperature_2m"
    assert list(df["precip_mm"]) == [0.0, 0.1, 0.2] and list(df["air_c"]) == [15.0, 15.5, 16.0]


# ---- the model file and the tree walk ------------------------------------------------------------------------------
def test_the_model_file_is_the_tested_river_model():
    d = json.loads((config.PROCESSED / "water_temp_model.json").read_text())
    assert d["test"]["types_passed"] == ["river"] and d["test"]["shown_within_c"] == 2.0
    assert d["months"] == [5, 6, 7, 8, 9]
    assert d["trained_on"]["features_sha256"].startswith("4e9ca630")
    assert d["check"]["max_abs_diff_trees"] <= 1e-9 and d["check"]["max_abs_diff_model"] <= 1e-9
    m = water_temp.load()
    assert m is not None and len(m.trees) == 400


def test_the_tree_walk_matches_scikit_learn_with_categories_and_missing_values():
    from sklearn.ensemble import HistGradientBoostingRegressor
    import wt_export
    rng = np.random.default_rng(0)
    n = 4000
    X = np.column_stack([rng.normal(size=n), rng.integers(0, 3, n).astype(float),
                         np.where(rng.random(n) < 0.3, np.nan, rng.normal(size=n))])
    y = 2 * X[:, 0] + 3 * (X[:, 1] == 1) + np.nan_to_num(X[:, 2])
    g = HistGradientBoostingRegressor(categorical_features=[1], max_iter=60, random_state=0).fit(X, y)
    m = water_temp.WaterTempModel({"features": ["a", "b", "c"], "curves": {}, "type_code": {}, "months": [],
                                   "bridge": {"c": 0, "d": 1}, "test": {"shown_within_c": 2},
                                   "gbm": wt_export.export_trees(g)})
    X2 = X.copy()
    X2[:50, 1] = 7          # a category never seen
    X2[50:100, 1] = np.nan
    X2[100:150, 0] = np.nan
    assert np.max(np.abs(g.predict(X2) - m.correction(X2))) <= 1e-9


# ---- the estimate --------------------------------------------------------------------------------------------------
def hourly_air(days: int, end: str = "2026-07-14", temp=16.0, gap: str | None = None) -> pd.DataFrame:
    """Hourly UTC rows covering `days` whole London days up to and including `end`."""
    start = pd.Timestamp(end, tz="Europe/London") - pd.Timedelta(days=days - 1)
    t = pd.date_range(start, pd.Timestamp(end, tz="Europe/London") + pd.Timedelta(days=1), freq="h",
                      inclusive="left").tz_convert("UTC")
    df = pd.DataFrame({"time": t, "air_c": float(temp), "precip_mm": 0.0})
    if gap:
        df.loc[df["time"].dt.tz_convert("Europe/London").dt.date.astype(str) == gap, "air_c"] = np.nan
    return df


def test_estimate_for_a_river_in_july():
    m = water_temp.load()
    e = water_temp.estimate(m, hourly_air(31), pd.Timestamp("2026-07-14"), 120.0, 60.0)
    assert e is not None and e["date"] == "2026-07-14" and e["within_c"] == 2.0
    assert 10 <= e["temp_c"] <= 25            # 16 C air for a month: a plausible river, not a check of accuracy
    warmer = water_temp.estimate(m, hourly_air(31, temp=22.0), pd.Timestamp("2026-07-14"), 120.0, 60.0)
    assert warmer["temp_c"] > e["temp_c"]


def test_no_estimate_for_a_lake_out_of_season_or_without_30_whole_days():
    m = water_temp.load()
    d = pd.Timestamp("2026-07-14")
    assert water_temp.estimate(m, hourly_air(31), d, 120.0, 60.0, kind="lake") is None
    assert water_temp.estimate(m, hourly_air(31, end="2026-10-14"), pd.Timestamp("2026-10-14"), 120.0, 60.0) is None
    assert water_temp.estimate(m, hourly_air(29), d, 120.0, 60.0) is None
    assert water_temp.estimate(m, hourly_air(31, gap="2026-07-01"), d, 120.0, 60.0) is None
    assert water_temp.estimate(None, hourly_air(31), d, 120.0, 60.0) is None
    assert water_temp.estimate(m, pd.DataFrame(), d, 120.0, 60.0) is None


def test_daily_air_counts_the_clock_change_day_with_its_25_hours():
    t = pd.date_range("2026-10-24T23:00Z", "2026-10-26T23:59Z", freq="h")
    df = pd.DataFrame({"time": t, "air_c": np.arange(len(t), dtype=float)})
    d = water_temp.daily_air(df)
    assert list(d.index) == [pd.Timestamp("2026-10-25"), pd.Timestamp("2026-10-26")]
    assert d.iloc[0] == pytest.approx(np.mean(np.arange(25)))


# ---- the build step ------------------------------------------------------------------------------------------------
def test_attach_gives_every_river_and_lake_spot_an_estimate_all_year_with_its_route():
    # Ethan's decision of 30 October 2026 (#492): a provisional estimate at every spot, all year, each saying its route.
    import build_site
    m = water_temp.load()
    def spots():
        return [{"id": "r", "name": "A river", "kind": "river", "lat": 53.9, "lon": -1.8},
                {"id": "s", "name": "A small lake", "kind": "lake", "lat": 54.4, "lon": -2.9, "location": {"lake_area_km2": 0.4}},
                {"id": "b", "name": "A large lake", "kind": "lake", "lat": 54.4, "lon": -2.9, "location": {"lake_area_km2": 14.8}},
                {"id": "c", "name": "A coast", "kind": "coast", "lat": 50.0, "lon": -5.0}]
    july = spots()
    h = build_site.attach_water_temperature_estimate(july, forecast=lambda cells: hourly_air(31).assign(elevation_m=80.0), model=m,
                                                     upstream=lambda r: 50.0, now=pd.Timestamp("2026-07-14T09:00", tz="Europe/London"))
    assert h["estimated"] == 3 and h["routes"] == {"river_model": 1, "lake_model": 1, "lake_curve": 1}
    assert [x["water_temp_est"]["route"] for x in july[:3]] == ["river_model", "lake_model", "lake_curve"]
    r, s = july[0]["water_temp_est"], july[1]["water_temp_est"]
    assert r["tested"] is True and r["typical_c"] == 1.56 and r["within_c"] == 2.0 and r["date"] == "2026-07-14"
    assert s["tested"] is False and s["typical_c"] == 1.70 and "within_c" not in s   # measured, but the lake test failed
    assert "water_temp_est" not in july[3] and "water_temp_est_missing" not in july[3]   # coasts: their own route (#479)
    october = spots()
    h = build_site.attach_water_temperature_estimate(october, forecast=lambda cells: hourly_air(31, end="2026-10-27"), model=m,
                                                     upstream=lambda r: 50.0, now=pd.Timestamp("2026-10-27T09:00", tz="Europe/London"))
    assert h["routes"] == {"river_off_season": 1, "lake_off_season": 2}
    for x in october[:3]:
        e = x["water_temp_est"]
        assert e["tested"] is False and e["typical_c"] is None and e["temp_c"] >= 0   # not measured in October: no error said


def test_a_spot_without_its_air_says_why_and_never_gets_an_old_estimate():
    import build_site
    m = water_temp.load()
    spots = [{"id": "r", "name": "A river", "kind": "river", "lat": 53.9, "lon": -1.8}]
    # The forecast ends two days early: not all 30 days to today, so no estimate, and the gap is said.
    h = build_site.attach_water_temperature_estimate(spots, forecast=lambda c: hourly_air(31, end="2026-10-25"), model=m,
                                                     upstream=lambda r: 50.0, now=pd.Timestamp("2026-10-27T09:00", tz="Europe/London"))
    assert h["estimated"] == 0 and h["missing"] == {"air": 1}
    assert spots[0]["water_temp_est_missing"] == {"why": "air", "date": "2026-10-27"} and "water_temp_est" not in spots[0]

    def boom(cells):
        raise RuntimeError("no rain cache")
    spots = [{"id": "r", "name": "A river", "kind": "river", "lat": 53.9, "lon": -1.8}]
    h = build_site.attach_water_temperature_estimate(spots, forecast=boom, model=m, upstream=lambda r: 50.0,
                                                     now=pd.Timestamp("2026-07-14T09:00", tz="Europe/London"))
    assert h["missing"] == {"error": 1} and "water_temp_est" not in spots[0]


def test_every_estimate_is_saved_before_its_observations_arrive(tmp_path):
    import build_site
    log = tmp_path / "water_temp_estimates.parquet"
    spots = [{"id": "r", "kind": "river", "water_temp_est": {"date": "2026-10-31", "route": "river_off_season", "temp_c": 11, "air_7d_c": 9.3},
              "water_temp": {"temp_c": 10.4, "observed_at": "2026-10-31T09:00:00Z", "river_km": 2.1, "direction": "upstream"}},
             {"id": "l", "kind": "lake", "water_temp_est_missing": {"why": "air", "date": "2026-10-31"}}]
    assert build_site.log_water_temp_estimates(spots, pd.Timestamp("2026-10-31T10:00Z"), log) == 1
    assert build_site.log_water_temp_estimates(spots, pd.Timestamp("2026-10-31T10:30Z"), log) == 1   # only ever added to
    df = pd.read_parquet(log)
    assert len(df) == 2 and list(df["spot"]) == ["r", "r"] and df["sensor_c"].iloc[0] == 10.4 and df["route"].iloc[0] == "river_off_season"
