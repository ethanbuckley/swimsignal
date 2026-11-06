"""The research shadow log (scripts/lake_chl_shadow.py, docs/SATELLITE-CHL-CANDIDATES-2026-11.md amendment 1): each
model's value and the fallback from one reading, rows only for usable readings, an idempotent versioned file of its
own, nothing without a model, and the frozen model and log as committed, kept off the site."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lake_chl_shadow as S  # noqa: E402

FAKE = {"version": "0.0.0-test", "bright_floor": 0.002, "iqr_floor": 0.005, "reference": 1.0,
        "models": {"B0": {"a": 1.0, "b": 2.0}, "A": {"a": 1.1, "b": 2.1},
                   "B": {"a": 1.0, "b": 2.0, "c": -3.0, "g": 1.0, "reference": 1.2, "reference_variance": 0.2},
                   "C": {"beta": [1.0, 2.0, 0.1, 0.5, 0.3]}}}


def test_each_model_value_and_the_fallback():
    v = S.values(FAKE, 0.1, 0.05, 0.03, False)
    assert v["fallback"] == 1.0 and v["B0"] == 1.2 and v["A"] == 1.31
    lb = np.log10(0.05)
    assert v["C"] == round(1 + 0.2 + 0.1 * lb + 0.5 * 0.03 + 0.3 * 0.1 * lb, 4)
    var = np.exp(-3 + np.log(0.035) - np.log(0.05))
    assert v["B"] == round((1.2 / var + 1.2 / 0.2) / (1 / var + 1 / 0.2), 4)
    flagged = S.values(FAKE, 0.1, 0.005, 0.3, True)
    assert flagged["A"] is None and flagged["B0"] == 1.2 and flagged["fallback"] == 1.0
    none = S.values(FAKE, None, None, None, None)
    assert all(none[k] is None for k in ("B0", "A", "B", "C"))
    assert S.values(FAKE, 0.1, None, None, None)["C"] is None


def test_rows_only_for_usable_readings_with_their_own_mark():
    scene = [{"lake_id": "x", "item_id": "i1", "tile": "T", "datetime": "2027-06-01T11:00:00Z", "usable": True,
              "reading": 0.1, "core_brightness": 0.01, "index_iqr": 0.03},
             {"lake_id": "x", "item_id": "i2", "usable": False, "reading": None},
             {"lake_id": "x", "item_id": "i3", "usable": True, "reading": float("nan")}]
    rows = S.rows_for(scene, FAKE, "2027-06-02T06:20:00+00:00", "pilot", "lake_id")
    assert len(rows) == 1 and rows[0]["inputs"]["low_signal"] is True and rows[0]["values"]["A"] is None
    assert rows[0]["acquired"] == "2027-06-01T11:00:00Z" and rows[0]["read_at"].startswith("2027-06-02")


def test_append_is_idempotent_and_versioned(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "model_sha", lambda path=S.MODEL: "abc")
    rows = S.rows_for([{"lake_id": "x", "item_id": "i1", "usable": True, "reading": 0.1, "core_brightness": 0.05,
                        "index_iqr": 0.03}], FAKE, "t", "pilot", "lake_id")
    log = tmp_path / "log.json"
    assert S.append(rows, log, FAKE) == 1 and S.append(rows, log, FAKE) == 0
    doc = json.loads(log.read_text())
    assert doc["schema"] == S.SCHEMA and doc["model"] == {"version": "0.0.0-test", "sha256": "abc"} and len(doc["rows"]) == 1


def test_nothing_without_a_model(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "load", lambda path=S.MODEL: None)
    assert S.log_run([{"usable": True, "reading": 0.1}], "pilot", "lake_id", "t", tmp_path / "log.json") is None
    assert not (tmp_path / "log.json").exists()


def test_the_frozen_model_and_log_as_committed():
    m = S.load()
    d = json.loads((ROOT / "data/research/satellite_chl_candidates_2026_11.json").read_text())
    assert m["schema"] == "swimsignal.lake-chl-shadow-model" and m["version"].split(".")[0] == "1"
    assert set(m["models"]) == {"B0"} | {c for c, s in d["support"].items() if s["supported"]}
    assert d["support"]["E"].get("tested") is False and "E" not in m["models"]
    assert "not shown on the site" in m["description"] and "Not a measurement" in m["description"]
    assert np.isfinite(m["reference"])
    log = json.loads(S.LOG.read_text())
    assert log["schema"] == S.SCHEMA and log["model"]["sha256"] == S.model_sha()


def test_the_log_stays_off_the_site():
    bs = (ROOT / "scripts/build_site.py").read_text()
    assert "chl_shadow" not in bs
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    assert not any("chl_shadow" in f for f in build_site.LAB_DATA)
    for page in (ROOT / "src/dipcast/pages").rglob("*"):
        if page.is_file() and page.suffix in (".html", ".js"):
            assert "chl_shadow" not in page.read_text(errors="ignore"), page
    pilot = (ROOT / ".github/workflows/satellite-pilot.yml").read_text()
    assert "data/research/satellite/chl_shadow_log.v1.json" in pilot


def test_a_local_pilot_trial_writes_beside_its_own_run_record(tmp_path, monkeypatch):
    src = (ROOT / "scripts/satellite_pilot.py").read_text()
    assert 'log_run(rows, "pilot", "lake_id", rec["finished"], RUNS.parent / "chl_shadow_log.v1.json")' in src
    import importlib
    monkeypatch.setenv("DIPCAST_CHL_SHADOW_LOG", str(tmp_path / "x.json"))
    assert importlib.reload(S).LOG == tmp_path / "x.json"
    monkeypatch.delenv("DIPCAST_CHL_SHADOW_LOG")
    importlib.reload(S)


def test_nothing_new_leaves_the_file_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "model_sha", lambda path=S.MODEL: "abc")
    log = tmp_path / "log.json"
    assert S.append([], log, FAKE) == 0 and log.exists()
    before = log.read_text()
    assert S.append([], log, FAKE) == 0 and log.read_text() == before
    assert not (tmp_path / "log.json.tmp").exists()
