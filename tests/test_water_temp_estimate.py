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


def test_the_click_anywhere_file_carries_each_cells_7_day_air_and_the_curves():
    # #492 stage 2: the page estimates a clicked river or lake from these (anypoint.js, waterAt): no extra request.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_any_point
    t = pd.date_range("2026-10-20", "2026-11-01", freq="h", tz="UTC")
    full = pd.DataFrame({"cell_lat": 54.4, "cell_lon": -2.9, "time": t, "air_c": 9.0})
    short = pd.DataFrame({"cell_lat": 52.0, "cell_lon": -1.0, "time": t[-60:], "air_c": 12.0})   # not 7 whole days
    w = build_any_point.water_air(pd.concat([full, short]), pd.Timestamp("2026-10-31T12:00", tz="Europe/London"))
    assert w["date"] == "2026-10-31" and list(w["cells"]) == ["54.4,-2.9"]
    m = water_temp.load()
    assert w["cells"]["54.4,-2.9"] == pytest.approx(m.bridge[0] + m.bridge[1] * 9.0, abs=0.01)
    assert w["curves"]["river"] == list(m.curves["river"]) and w["months"] == [5, 6, 7, 8, 9]
    assert w["typical_c"] == {"river": 1.85, "lake": 1.93}


# ---- the coastal directory (#492 stage 3, #479) ---------------------------------------------------------------------
def test_a_directory_site_takes_its_own_cell_else_the_nearest_of_the_eight_around_it():
    cells = {"50.7,-1.3": 12.0, "50.6,-1.2": 11.0}
    assert water_temp.nearest_cell_air(cells, 50.71, -1.29) == (12.0, 0)
    a7, km = water_temp.nearest_cell_air({"50.6,-1.2": 11.0}, 50.68, -1.27)   # its own cell is not cached
    assert a7 == 11.0 and km == 10
    assert water_temp.nearest_cell_air({"50.4,-1.3": 11.0}, 50.71, -1.29) is None   # two cells away: nothing


def test_the_sea_estimate_states_its_error_only_where_the_test_measured_one():
    m = water_temp.load()
    cells = {"50.7,-1.3": 15.0}
    july = water_temp.sea_from_cells(m, cells, "2026-07-14", 50.71, -1.29)
    assert july["route"] == "sea_air_curve" and july["tested"] is False and july["typical_c"] == 1.63
    assert july["temp_c"] == round(float(water_temp.mohseni(15.0, *m.curves["sea"]))) and july["air_km"] == 0
    assert water_temp.sea_from_cells(m, cells, "2026-10-31", 50.71, -1.29)["typical_c"] is None   # not measured in October
    estuary = water_temp.sea_from_cells(m, cells, "2026-07-14", 50.71, -1.29, "estuary")
    assert estuary["route"] == "estuary_air_curve" and estuary["typical_c"] is None   # estuaries were left out of the test
    assert water_temp.sea_from_cells(m, {}, "2026-07-14", 50.71, -1.29) is None


def test_every_coastal_site_gets_an_estimate_or_says_why_not(tmp_path):
    import build_site
    from dipcast.coastal import water_line
    points = tmp_path / "points.json"
    points.write_text(json.dumps({"england": {"ukj1-00001": [50.71, -1.29], "ukj1-00002": [52.9, 1.3]}}))
    sites = [{"id": "ukj1-00001", "name": "Here", "kind": "coast"}, {"id": "ukj1-00002", "name": "Far", "kind": "estuary"},
             {"id": "ukj1-00003", "name": "Unplaced", "kind": "coast"}]
    air = {"date": "2026-10-31", "cells": {"50.7,-1.3": 12.0}}
    h = build_site.attach_directory_water_temp(sites, air, model=water_temp.load(), points_file=points)
    assert h == {"estimated": 1, "routes": {"sea_air_curve": 1}, "missing": {"air": 1, "point": 1}}
    assert sites[1]["water_temp_est_missing"] == {"why": "air", "date": "2026-10-31"}
    line = water_line(sites[0])
    assert line.startswith(f'Water about {sites[0]["water_temp_est"]["temp_c"]} °C on 31 Oct: ') and "not measured" in line
    assert "this beach's square" in line and line.endswith("not yet checked in these months")
    assert water_line(sites[1]) == "No water temperature estimate in this update" and water_line({}) == ""
    # No click-anywhere air in this build: every site says so, none is given an old figure.
    again = [{"id": "ukj1-00001", "name": "Here", "kind": "coast"}]
    assert build_site.attach_directory_water_temp(again, None, model=water_temp.load(), points_file=points)["missing"] == {"air": 1}
    assert "water_temp_est" not in again[0]


def test_the_points_file_places_every_english_coastal_directory_site():
    pts = json.loads((ROOT / "data" / "raw" / "bathing_water_points.json").read_text())
    cat = json.loads((ROOT / "data" / "raw" / "coastal_catalogue.json").read_text())["items"]
    from dipcast.coastal import KINDS
    ids = [i["eubwidNotation"] for i in cat if any(t.rsplit("/", 1)[-1] in KINDS for t in i["type"])]
    assert len(ids) == 426 and all(i in pts["england"] for i in ids)
    assert all(49.8 < la < 55.9 and -6.5 < lo < 2.0 for la, lo in pts["england"].values())


# ---- Wales, Scotland, Ireland and Northern Ireland (#492 stage 4) ----------------------------------------------------
def test_an_inland_directory_water_takes_its_own_curve_and_the_error_measured_for_it():
    m = water_temp.load()
    cells = {"53.2,-8.6": 9.0}
    lake = water_temp.directory_estimate(m, cells, "2026-10-31", 53.19, -8.56, "lake")
    assert lake["route"] == "lake_air_curve" and lake["typical_c"] is None and lake["air_km"] == 0
    assert water_temp.directory_estimate(m, cells, "2026-07-14", 53.19, -8.56, "river")["typical_c"] == 1.85
    assert water_temp.directory_estimate(m, cells, "2026-07-14", 53.19, -8.56, "coast")["route"] == "sea_air_curve"
    assert water_temp.directory_estimate(m, cells, "2026-07-14", 53.19, -8.56, "canal") is None
    assert water_temp.nearest_cell_air({"53.4,-8.6": 9.0}, 53.19, -8.56) is None            # two squares away
    assert water_temp.nearest_cell_air({"53.4,-8.6": 9.0}, 53.19, -8.56, ring=2)[1] == 24


def test_the_nations_waters_are_typed_and_placed():
    from dipcast import ireland, northern_ireland, scotland
    assert ireland.water_kind("IEWEBWC010_0000_0040", "Aillebrack") == ("coast", "epa_code")
    assert ireland.water_kind("IESHBWL25_191a_0300", "Lough Derg") == ("lake", "epa_code")
    assert ireland.water_kind("IESEBWT050_0000_0100", "Somewhere") == ("estuary", "epa_code")
    assert ireland.water_kind("BPNBF31_0001", "Lough Muckno Bathing Area") == ("lake", "name")
    assert ireland.water_kind("BPNBF31_0002", "Halton's River (Dromore Lake System)") == ("lake", "name")
    assert ireland.water_kind("BPNBF05_0003", "Silver Strand Louisburgh") == ("coast", "name")
    assert ireland.position(162397, 215167) == (53.18591, -8.56323)   # Loughrea Lake, Irish Grid
    assert ireland.position(None, 1) == (None, None)
    one = {"attributes": {"description": "Loch Morlich", "year": 2025, "class_description": "Excellent",
                          "bw_url": "https://bathingwaters.sepa.org.uk/locations-and-results/results?location=100002"},
           "geometry": {"x": -3.72, "y": 57.17}}
    assert scotland.parse([one])[0]["kind"] == "lake"
    assert northern_ireland._point({"x": -6.87562, "y": 55.16822}) == {"lat": 55.16822, "lon": -6.87562}
    assert northern_ireland._point({}) == {}


def _cache_cell(tmp, lat, lon, day="2026-10-31", air=10.0, age_h=1.0):
    t = pd.date_range(pd.Timestamp(day) - pd.Timedelta(days=9), pd.Timestamp(day) + pd.Timedelta(days=1), freq="h", tz="UTC")
    p = tmp / f"forecast_{rainfall.cell_key(lat, lon)}.parquet"
    pd.DataFrame({"cell_lat": lat, "cell_lon": lon, "time": t, "precip_mm": 0.0, "air_c": air}).to_parquet(p)
    import os
    import time as _t
    os.utime(p, (_t.time() - age_h * 3600,) * 2)
    return p


def test_directory_air_reads_cached_cells_free_and_asks_only_for_the_fewest_missing(tmp_path, monkeypatch):
    import build_site
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    now = pd.Timestamp("2026-10-31T12:00", tz="Europe/London")
    _cache_cell(tmp_path, 57.1, -2.1)                      # a Scottish shadow cell, fresh: free
    points = [(57.12, -2.08), (52.41, -4.09), (52.43, -4.12), (52.6, -4.1)]   # Aberdeen; three Welsh sites
    asked = []

    def fetch(cells):
        asked.append(list(cells))
        for c in cells:
            _cache_cell(tmp_path, *c, age_h=0)
    air, h = build_site.directory_air(points, now=now, fetch=fetch, spare=lambda w: True)
    assert asked == [[(52.5, -4.1)]] and h["asked"] == h["cells_needed"] == 1   # one cell reaches all three Welsh sites
    assert h["calls"] == 1.0 and h["held"] == 0 and "57.1,-2.1" in air["cells"]
    sites = [{"id": str(i), "lat": a, "lon": b, "kind": "coast"} for i, (a, b) in enumerate(points)]
    assert build_site.attach_directory_water_temp(sites, air, nation="wales")["estimated"] == 4
    # The next build: everything is fresh, so nothing is asked for.
    air, h = build_site.directory_air(points, now=now, fetch=fetch, spare=lambda w: True)
    assert len(asked) == 1 and h["asked"] == 0 and h["cells_needed"] == 0
    # No spare calls: nothing asked, the gap said, and an old cell past its age is not used.
    for p in tmp_path.glob("forecast_52*.parquet"):
        p.unlink()
    air, h = build_site.directory_air(points, now=now, fetch=fetch, spare=lambda w: False)
    assert h["held"] == 1 and h["asked"] == 0 and len(asked) == 1
    s = [{"id": "w", "lat": 52.41, "lon": -4.09, "kind": "coast"}]
    assert build_site.attach_directory_water_temp(s, air, nation="wales")["missing"] == {"air": 1}


def test_directory_air_keeps_the_ensembles_day_back():
    import build_site
    # The default rule asks spare_for for the cells and the ensemble's unspent day together.
    import inspect
    src = inspect.getsource(build_site.directory_air)
    assert "ENSEMBLE_DAILY_CALLS" in src and "spare_for" in src
    assert build_site.greedy_cells([(52.41, -4.09), (52.43, -4.12)]) == [(52.4, -4.1)]   # their own, the nearest
    assert build_site.site_water_kind({"kind": "inland"}) == "lake" and build_site.site_water_kind({}) == "coast"
    assert build_site.site_point({"lat": 1.0, "lon": 2.0}, {}) == (1.0, 2.0)
    assert build_site.site_point({"id": "x"}, {"x": [3, 4]}) == (3.0, 4.0) and build_site.site_point({"id": "y"}, {}) is None


def test_each_nations_card_says_the_estimate():
    from dipcast import ireland, northern_ireland, scotland, wales
    est = {"temp_c": 12, "date": "2026-10-31", "route": "lake_air_curve", "tested": False, "typical_c": None,
           "air_7d_c": 9.0, "air_km": 0}
    from dipcast.coastal import water_line
    assert water_line({"water_temp_est": est}).endswith("at this water's square, not measured. Provisional: not yet checked in these months")
    summer = {**est, "date": "2026-07-14", "typical_c": 1.93}
    assert "typical error 1.9 °C at lakes in a summer test" in water_line({"water_temp_est": summer})
    assert wales._water({"water_temp_est": est}).startswith("<br>Water about 12 °C on 31 Oct")
    assert scotland._water({}) == ""
    for mod in (ireland, northern_ireland):
        assert "from dipcast.coastal import water_line" in __import__("inspect").getsource(mod.render)
