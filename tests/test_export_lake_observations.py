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
            "processing": {}, "claim": m.CLAIM, "freshness_rules": {}, "lab_definition": m.LAB_DEFINITION,
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
    del bad["lab_definition"]
    assert any("lab_definition" in e for e in m.check(bad))


def test_the_committed_export_holds_the_contract():
    path = ROOT / "data" / "research" / "lake_observations.v1.json"
    doc = json.loads(path.read_text())
    assert m.check(doc) == []
    assert doc["coverage"]["lakes"] == len(doc["lakes"])
    assert all(s["sha256"] for s in doc["processing"]["sources"])
