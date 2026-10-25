"""scripts/farm_pressure_eval/score.py's face check (docs/FARM-PRESSURE-TEST-2026-10.md, "Data"): the reference arm
must match train_ecoli.py's ecoli_model_eval.json, or the run stops with no verdict. Mocked results only: no data is
read, no model trained."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "farm_pressure_eval"))
import score  # noqa: E402

VERDICT = ("conditions", "reading", "gain")


def _res(loyo=0.0612, loso=0.0655, forward=0.0598):
    return {"rnags_sha256": "x", "rows": 120, "sites": 12, "split": {}, "gain": {"loso": 0.002},
            "conditions": {"passes": True}, "reading": "predicts new sites",
            "loyo": {"reference": {"all": loyo}}, "loso": {"reference": {"all": loso}},
            "forward": {"reference": {"all": forward}}}


def _eval(tmp_path, loyo=0.0612, loso=0.0655, forward=0.0598, n=120):
    full = score.te.FULL
    e = {"n_samples": n, "loyo": [{"model": full, "brier": loyo}], "loso": [{"model": full, "brier": loso}],
         "forward": {"table": [{"model": full, "brier": forward}]}}
    p = tmp_path / "ecoli_model_eval.json"
    p.write_text(json.dumps(e))
    return p


def _stopped(tmp_path, ev, res=None):
    out = tmp_path / "out.json"
    with pytest.raises(SystemExit) as stop:
        score.finish(res or _res(), 120, str(out), ev)
    assert stop.value.code == score.STOP_EXIT
    written = json.loads(out.read_text())
    assert written["stopped"].startswith("face check failed") and written["face_check"]["holds"] is False
    assert not any(k in written for k in VERDICT)     # no verdict can be read from a stopped run
    return written


def test_a_missing_reference_file_stops_the_run(tmp_path):
    w = _stopped(tmp_path, tmp_path / "ecoli_model_eval.json")
    assert "not found" in w["face_check"]["why"]


def test_a_reference_that_differs_stops_the_run(tmp_path):
    w = _stopped(tmp_path, _eval(tmp_path, loso=0.0660))
    assert w["face_check"]["why"].endswith("loso")
    assert "n" in _stopped(tmp_path, _eval(tmp_path, n=119))["face_check"]["why"]


def test_an_unreadable_reference_stops_the_run(tmp_path):
    p = tmp_path / "ecoli_model_eval.json"
    p.write_text("{not json")
    assert "unreadable" in _stopped(tmp_path, p)["face_check"]["why"]
    p.write_text(json.dumps({"n_samples": 120, "loyo": []}))     # the reference row is missing
    assert "unreadable" in _stopped(tmp_path, p)["face_check"]["why"]


def test_a_matching_reference_writes_the_result_with_its_verdict(tmp_path, capsys):
    out = tmp_path / "out.json"
    # Equal to 4 decimals, as train_ecoli writes them.
    score.finish(_res(loso=0.065541), 120, str(out), _eval(tmp_path, loso=0.0655))
    written = json.loads(out.read_text())
    assert written["face_check"]["holds"] is True and written["conditions"]["passes"] is True
    assert "stopped" not in written and '"conditions"' in capsys.readouterr().out


def test_a_malformed_score_stops_the_run_and_replaces_a_stale_accepted_result(tmp_path):
    """Review case: the reference row exists but its scores are not numbers. The run must stop the same way, and an
    accepted out.json left by an earlier run must not survive."""
    out = tmp_path / "out.json"
    out.write_text(json.dumps({"conditions": {"passes": True}, "stale": True}))
    full = score.te.FULL
    p = tmp_path / "ecoli_model_eval.json"
    p.write_text(json.dumps({"n_samples": 10, "loyo": [{"model": full, "brier": "bad score"}],
                             "loso": [{"model": full, "brier": "bad score"}],
                             "forward": {"table": [{"model": full, "brier": "bad score"}]}}))
    res = _res(loyo=0.1, loso=0.1, forward=0.1)
    with pytest.raises(SystemExit) as stop:
        score.finish(res, 10, str(out), p)
    assert stop.value.code == score.STOP_EXIT
    written = json.loads(out.read_text())
    assert "stale" not in written and not any(k in written for k in VERDICT)
    assert "unreadable" in written["face_check"]["why"] and "not a finite number" in written["face_check"]["why"]


@pytest.mark.parametrize("bad", [None, True, float("nan"), "0.0612"])
def test_non_numeric_or_non_finite_scores_are_malformed(tmp_path, bad):
    full = score.te.FULL
    p = tmp_path / "ecoli_model_eval.json"
    p.write_text(json.dumps({"n_samples": 120, "loyo": [{"model": full, "brier": bad}],
                             "loso": [{"model": full, "brier": 0.0655}],
                             "forward": {"table": [{"model": full, "brier": 0.0598}]}}))
    assert "unreadable" in _stopped(tmp_path, p)["face_check"]["why"]
