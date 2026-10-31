"""scripts/satellite_pilot.py: the weekly satellite pilot's publish step and its inputs (docs/SATELLITE-PILOT-2026-11.md).
No network: the runs are synthetic records of the shape `run` writes."""

import copy
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import export_lake_observations as ex  # noqa: E402
import satellite_pilot as sp  # noqa: E402
from test_export_lake_observations import _doc, _features, _refresh_rows  # noqa: E402


def _rows(lake_id="bw-x"):
    return [{**r, "lake_id": lake_id} for r in _refresh_rows().drop(columns=["bw_id"]).to_dict("records")]


def _run(run_id, rows, status="ok", finished="2026-11-02T06:30:00+00:00", sites=None):
    st = {"scenes": len(rows), "already_read": 0, "read": len(rows), "status": status, "error": None}
    return {"run_id": run_id, "trigger": "schedule", "started": finished, "finished": finished,
            "window": {"from": "2026-10-20", "to": "2026-11-02"}, "caps": {"requests": 300, "megabytes": 100, "minutes": 20},
            "seconds": 12.0, "requests": 40, "megabytes": 6.5, "status": status, "stop_reason": None,
            "sites": sites or {"bw-x": st}, "rows": rows}


@pytest.fixture
def files(tmp_path, monkeypatch):
    doc = _doc("2026-11-02")
    doc["release"] = ex.release(doc["lakes"], "2026-09-30")
    obs, runs, pilot = tmp_path / "obs.json", tmp_path / "runs.json", tmp_path / "pilot.json"
    obs.write_text(json.dumps(doc))
    runs.write_text("[]")
    pilot.write_text(json.dumps({"sites": [{"lake_id": "bw-x"}]}))
    monkeypatch.setattr(sp, "OBS", obs)
    monkeypatch.setattr(sp, "RUNS", runs)
    monkeypatch.setattr(sp, "PILOT", pilot)
    return obs, runs


def test_apply_refresh_gives_what_the_export_gives():
    f = _features([("2026-09-20", "C", "T1", 95, 100, True, -0.02)])
    base = {"lake_id": "bw-x", "name": "X", "water_body": "X", "lat": 52.6, "lon": -0.7, "site_ids": {}}
    info = {"source": "refresh:test", "set": "bathing", "from": "2026-10-01", "to": "2026-10-30"}
    args = (base, f, {"tiles": {"T1": {"n_core": 100, "passes": True}}}, {}, "every_scene", [], date(2026, 10, 30),
            "2026-09-30")
    exported = ex.lake_record(*args, [(_refresh_rows(), info)])
    applied = ex.lake_record(*args)
    res = ex.apply_refresh(applied, _refresh_rows(), info, date(2026, 10, 30))
    for k in ("series", "excluded", "latest", "processed_to"):
        assert applied[k] == exported[k], k
    assert res == {"shown": 1, "excluded": 3, "scenes": 5, "already_present": 0}
    again = copy.deepcopy(applied)
    # The cloudy R5 is kept nowhere in the record, so only the run log (pilot_runs.json) knows it was read.
    assert ex.apply_refresh(again, _refresh_rows(), info, date(2026, 10, 30))["already_present"] == 4
    assert again["series"] == applied["series"] and again["excluded"] == applied["excluded"]
    assert again["refreshes"] == applied["refreshes"]


def test_publish_sets_operation_and_is_idempotent(files):
    obs, runs = files
    runs.write_text(json.dumps([_run("101", _rows())]))
    sp.publish(date(2026, 11, 2))
    first = json.loads(obs.read_text())
    assert ex.check(first) == []
    lk = next(x for x in first["lakes"] if x["lake_id"] == "bw-x")
    assert lk["operation"]["last_status"] == "new_reading"
    assert lk["operation"]["last_success_at"] == "2026-11-02T06:30:00+00:00"
    assert lk["operation"]["newest_pilot_reading"] == "2026-10-14"
    assert lk["latest"]["item_id"] == "R1" and lk["latest"]["age_days"] == 19
    assert lk["processed_to"] == "2026-11-02"
    assert "operation" not in next(x for x in first["lakes"] if x["lake_id"] == "bw-y")
    assert first["pilot"]["sites"] == ["bw-x"] and first["release"]["pilot_sites"] == ["bw-x"]
    assert "pilot sites are refreshed weekly" in first["release"]["label"]
    sp.publish(date(2026, 11, 2))
    second = json.loads(obs.read_text())
    for a, b in zip(first["lakes"], second["lakes"], strict=True):
        assert a == b


def test_a_failed_week_keeps_the_last_success_and_ages_the_reading(files):
    obs, runs = files
    failed = _run("102", [], status="failed", finished="2026-11-09T06:30:00+00:00",
                  sites={"bw-x": {"scenes": 0, "already_read": 0, "read": 0, "status": "failed",
                                  "error": "Stop: 503 from earth-search"}})
    runs.write_text(json.dumps([_run("101", _rows()), failed]))
    sp.publish(date(2026, 11, 9))
    lk = next(x for x in json.loads(obs.read_text())["lakes"] if x["lake_id"] == "bw-x")
    assert lk["operation"]["last_status"] == "failed" and "503" in lk["operation"]["last_error"]
    assert lk["operation"]["last_success_at"] == "2026-11-02T06:30:00+00:00"
    assert lk["latest"]["age_days"] == 26 and lk["processed_to"] == "2026-11-02"


def test_a_partial_run_counts_only_as_far_as_it_read(files):
    obs, runs = files
    rows = [r for r in _rows() if r["item_id"] in ("R1", "R2")]
    st = {"scenes": 5, "already_read": 0, "read": 2, "status": "partial", "error": None}
    runs.write_text(json.dumps([_run("103", rows, status="partial", sites={"bw-x": st})]))
    sp.publish(date(2026, 11, 2))
    lk = next(x for x in json.loads(obs.read_text())["lakes"] if x["lake_id"] == "bw-x")
    assert lk["operation"]["last_status"] == "partial" and lk["operation"]["last_success_at"] is None
    assert lk["processed_to"] == "2026-10-27"


@pytest.mark.parametrize("st, rows, want", [
    ({"status": "ok", "scenes": 0, "read": 0}, [], "no_scenes"),
    ({"status": "ok", "scenes": 3, "read": 0}, [], "no_new_scenes"),
    ({"status": "ok", "scenes": 2, "read": 2}, ["R2", "R5"], "no_new_clear_image"),
    ({"status": "ok", "scenes": 2, "read": 2}, ["R1", "R5"], "new_reading"),
    ({"status": "not_reached", "scenes": 0, "read": 0}, [], "not_reached"),
])
def test_site_status(st, rows, want):
    df = pd.DataFrame([r for r in _rows() if r["item_id"] in rows])
    assert sp.site_status(st, df) == want
    assert want in ex.PILOT_STATUS


def test_check_refuses_operation_outside_the_pilot():
    d = _doc()
    d["lakes"][1]["operation"] = {"pilot": True, "last_status": "new_reading"}
    assert any("not in the pilot" in e for e in ex.check(d))
    d["pilot"] = {"sites": ["bw-y"]}
    assert ex.check(d) == []
    d["lakes"][1]["operation"]["last_status"] = "fine"
    assert any("last_status" in e for e in ex.check(d))


def test_the_committed_pilot_sites_and_masks():
    pilot = json.loads((ROOT / "data" / "research" / "satellite" / "pilot.json").read_text())["sites"]
    assert len(pilot) == 5 and len({s["water_body"] for s in pilot}) >= 3
    published = {lk["lake_id"]: lk for lk in json.loads(ex.OUT.read_text())["lakes"]}
    for s in pilot:
        cores = sp.site_cores(s["lake_id"])
        assert sorted(cores) == sorted(s["tiles"]) and all(c.dtype == bool and c.any() for c in cores.values())
        assert published[s["lake_id"]]["mask"]["passes_size_rule"], s["lake_id"]
        assert all(int(np.sum(c)) > 0 for c in cores.values())
    runs = json.loads((ROOT / "data" / "research" / "satellite" / "pilot_runs.json").read_text())
    assert isinstance(runs, list)
