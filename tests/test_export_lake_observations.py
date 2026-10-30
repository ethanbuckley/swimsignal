"""scripts/export_lake_observations.py: the contract check and the pieces of a lake record
(docs/LAKE-OBSERVATIONS-CONTRACT-v1.md)."""

import copy
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import export_lake_observations as m  # noqa: E402


def _features(rows):
    return pd.DataFrame(rows, columns=["scene_date", "item_id", "tile", "clear_core", "n_core", "usable", "reading"])


def _doc(as_of="2026-10-30"):
    f = _features([("2026-09-01", "A", "T1", 90, 100, True, 0.01), ("2026-09-10", "B", "T1", 10, 100, False, None),
                   ("2026-09-20", "C", "T1", 95, 100, True, -0.02)])
    base = {"lake_id": "bw-x", "name": "X", "water_body": "X", "wfd_waterbody_id": None, "lat": 54.0, "lon": -3.0,
            "site_ids": {"bathing_water": "x"}, "depth_m": None, "lake_type": None}
    lk = m.lake_record(base, f, {"tiles": {"T1": {"n_core": 100, "passes": True}}}, {}, "every_scene", [],
                       date.fromisoformat(as_of), "2026-09-30")
    small = m.lake_record({**base, "lake_id": "bw-y"}, f.iloc[0:0], {"tiles": {"T1": {"n_core": 3, "passes": False}}}, {},
                          "every_scene", [], date.fromisoformat(as_of), "2026-09-30")
    lakes = [lk, small]
    return {"schema": m.SCHEMA, "version": m.VERSION, "generated_at": "2026-10-30T00:00:00+00:00", "as_of": as_of,
            "processing": {}, "claim": m.CLAIM, "freshness_rules": {}, "lab_definition": m.LAB_DEFINITION, "quality": {},
            "attribution": ["Contains modified Copernicus Sentinel data [2026]"],
            "release": {"scope": "historical", "label": "Historical satellite observations", "regular_refresh": False},
            "lakes": lakes, "coverage": m.coverage(lakes)}


def test_a_built_record_holds_the_contract_and_says_why():
    d = _doc()
    assert m.check(d) == []
    lk, small = d["lakes"]
    assert [x["date"] for x in lk["series"]] == ["2026-09-01", "2026-09-20"]          # the cloudy scene is not a reading
    assert lk["latest"]["date"] == "2026-09-20" and lk["latest"]["age_days"] == 40
    assert lk["latest"]["freshness"] == "older"
    assert lk["latest"]["reasons"] == ["season_closed", "not_refreshed"]
    assert small["latest"]["freshness"] == "none" and "too_small" in small["latest"]["reasons"]


def test_one_primary_reading_a_date_by_the_most_clear_pixels():
    f = _features([("2026-09-01", "B", "T2", 85, 100, True, 0.30), ("2026-09-01", "A", "T1", 95, 100, True, 0.01)])
    base = {"lake_id": "bw-z", "name": "Z", "water_body": "Z", "lat": 54.0, "lon": -3.0, "site_ids": {}}
    lk = m.lake_record(base, f, {"tiles": {"T1": {"n_core": 100, "passes": True}}}, {}, "every_scene", [],
                       date(2026, 9, 5), "2026-09-30")
    assert [x["primary"] for x in lk["series"]] == [True, False]
    assert lk["latest"]["item_id"] == "A" and lk["latest"]["ndci"] == 0.01


def test_freshness_limits():
    a = date(2026, 9, 30)
    assert m.freshness("2026-09-16", a) == (14, "recent")
    assert m.freshness("2026-09-15", a) == (15, "older")
    assert m.freshness("2026-08-01", a) == (60, "older")
    assert m.freshness("2026-07-31", a) == (61, "stale")
    assert m.freshness(None, a) == (None, "none")


def test_in_season_and_refreshed_has_no_gap_reason():
    d = _doc(as_of="2026-09-25")
    lk = d["lakes"][0]
    # as_of before processed_to and inside May-September
    assert lk["latest"]["reasons"] == [] and lk["latest"]["freshness"] == "recent"


@pytest.mark.parametrize("s, want", [("<0.5", (0.5, "<")), ("12", (12.0, None)), (">200", (200.0, ">")),
                                     ("n/a", (None, None)), ("-3", (None, None))])
def test_lab_value_keeps_the_reported_limit(s, want):
    assert m.lab_value(s) == want


def test_check_catches_what_it_should():
    d = _doc()
    bad = copy.deepcopy(d)
    bad["claim"] = {**d["claim"], "public_wording": "Algae-free water, safe to swim."}
    assert any("not swimming advice" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][0]["series"][0]["clear_core"] = 10
    assert any("clear rule" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][0]["latest"]["age_days"] = 3
    assert any("age_days" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][1]["latest"]["reasons"] = []
    assert any("no reason" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][0]["series_scope"] = "near_lab_samples"
    assert any("series_partial" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][0]["series"][1]["primary"] = False
    assert any("primary" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    del bad["lab_definition"]
    assert any("lab_definition" in e for e in m.check(bad))


def test_the_committed_export_holds_the_contract():
    path = ROOT / "data" / "research" / "lake_observations.v1.json"
    doc = json.loads(path.read_text())
    assert m.check(doc) == []
    assert doc["coverage"]["lakes"] == len(doc["lakes"])
    assert all(s["sha256"] for s in doc["processing"]["sources"])


def _refresh_rows():
    return pd.DataFrame([
        # an October reading that passes every check
        dict(bw_id="x", scene_date="2026-10-14", datetime="2026-10-14T11:09:39Z", item_id="R1", tile="T1",
             processing_baseline="05.13", sun_elevation_deg=29.1, clear_core=95, n_core=100, usable=True, reading=0.07,
             clear_core_not_water=2, clear_core_valid_index=95, core_snow_ice=0),
        # same day, a fifth of the clear core classed as vegetation: excluded out of season
        dict(bw_id="x", scene_date="2026-10-27", datetime="2026-10-27T11:24:23Z", item_id="R2", tile="T1",
             processing_baseline="05.13", sun_elevation_deg=24.7, clear_core=90, n_core=100, usable=True, reading=0.06,
             clear_core_not_water=20, clear_core_valid_index=90, core_snow_ice=0),
        # snow in the core
        dict(bw_id="x", scene_date="2026-10-28", datetime="2026-10-28T11:20:00Z", item_id="R3", tile="T1",
             processing_baseline="05.13", sun_elevation_deg=24.0, clear_core=90, n_core=100, usable=True, reading=0.01,
             clear_core_not_water=0, clear_core_valid_index=90, core_snow_ice=3),
        # a band value missing at one clear pixel
        dict(bw_id="x", scene_date="2026-10-29", datetime="2026-10-29T11:20:00Z", item_id="R4", tile="T1",
             processing_baseline="05.13", sun_elevation_deg=24.0, clear_core=90, n_core=100, usable=True, reading=0.01,
             clear_core_not_water=0, clear_core_valid_index=89, core_snow_ice=0),
        # cloudy: not a reading, not listed as excluded
        dict(bw_id="x", scene_date="2026-10-30", datetime="2026-10-30T11:20:00Z", item_id="R5", tile="T1",
             processing_baseline="05.13", sun_elevation_deg=23.7, clear_core=0, n_core=100, usable=False, reading=None,
             clear_core_not_water=0, clear_core_valid_index=None, core_snow_ice=0),
    ])


def test_refreshed_readings_are_checked_flagged_and_traced():
    f = _features([("2026-09-20", "C", "T1", 95, 100, True, -0.02)])
    base = {"lake_id": "bw-x", "name": "X", "water_body": "X", "lat": 52.6, "lon": -0.7, "site_ids": {}}
    info = {"source": "refresh:test", "set": "bathing", "from": "2026-10-01", "to": "2026-10-30"}
    lk = m.lake_record(base, f, {"tiles": {"T1": {"n_core": 100, "passes": True}}}, {}, "every_scene", [],
                       date(2026, 10, 30), "2026-09-30", [(_refresh_rows(), info)])
    shown = [x for x in lk["series"] if x["source"] == "refresh:test"]
    assert [x["item_id"] for x in shown] == ["R1"]
    assert shown[0]["season"] == "out_of_season" and shown[0]["experimental"] is True
    assert {e["item_id"]: e["reason"] for e in lk["excluded"]} == {
        "R2": "core_not_classed_water", "R3": "snow_or_ice_in_core", "R4": "invalid_band_values"}
    assert lk["latest"]["item_id"] == "R1" and lk["latest"]["experimental"] is True and lk["latest"]["age_days"] == 16
    assert lk["processed_to"] == "2026-10-30" and "not_refreshed" not in lk["latest"]["reasons"]
    assert lk["refreshes"][0]["shown"] == 1


def test_check_refuses_future_dates_and_untraced_experimental_readings():
    d = _doc()
    bad = copy.deepcopy(d)
    bad["lakes"][0]["series"][-1]["date"] = "2026-11-05"
    bad["lakes"][0]["latest"]["date"] = "2026-11-05"
    assert any("after as_of" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][0]["series"][0].update(season="out_of_season", experimental=True)
    assert any("from a refresh" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][0]["latest"]["age_days"] = -1
    assert any("negative age_days" in e for e in m.check(bad))


def test_a_latest_release_needs_a_running_refresh():
    bad = copy.deepcopy(_doc())
    bad["release"] = {"scope": "latest", "label": "Latest", "regular_refresh": False}
    assert any("regular refresh" in e for e in m.check(bad))
    assert "Not the latest images" in m.release([], "2026-09-30")["label"]


def test_every_searched_season_is_listed_and_an_empty_one_says_why():
    f = _features([("2021-06-01", "A", "T1", 95, 100, True, 0.01), ("2023-06-01", "B", "T1", 95, 100, True, 0.02)])
    base = {"lake_id": "wqa-p", "name": "P", "water_body": "P", "lat": 52.0, "lon": 1.5, "site_ids": {}}
    sizes = {"tiles": {"T1": {"n_core": 100, "passes": True}}}
    images = {2020: 50, 2021: 50, 2023: 50, 2024: 50, 2025: 70, 2026: 70}   # 2022: the catalogue has none
    lk = m.lake_record(base, f, sizes, {}, "near_lab_samples", [], date(2026, 10, 30), "2026-09-30", images=images)
    by = {x["year"]: x for x in lk["seasons"]}
    assert list(by) == list(m.YEARS)
    assert by[2022]["reason"] == "no_source_images" and by[2022]["source_images"] == 0
    assert by[2020]["reason"] == "no_lab_sample_dates"        # images exist, no lab sample near any
    assert by[2021]["reason"] is None and by[2021]["usable"] == 1
