"""scripts/lake_line_2012_22.py (docs/LAKE-LINE-2012-22-CHECK-2026-11.md): the committed rows reproduce the recorded
figures, the frozen files are the ones scored, and the fetch stayed inside its caps. The rows were built by #584's
code under a capped fetch; rebuilding them needs Open-Meteo and EA requests, so it is not repeated here."""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lake_line_2012_22 as m  # noqa: E402

REC = json.loads(Path(f"{m.DOC}-scores.json").read_text())


def test_scored_files_are_the_frozen_ones():
    assert m.sha(m.FROZEN) == m.FROZEN_SHA
    for p in (m.FROZEN, m.RANGE, m.DEPLOYED, m.EVID):
        assert m.sha(p) == REC["inputs_sha256"][p.name], p.name
    assert m.sha(Path(f"{m.DOC}-rows.csv")) == REC["rows_sha256"]


def test_committed_rows_reproduce_the_point_estimates(monkeypatch):
    monkeypatch.setattr(m, "DRAWS", 20)
    d = pd.read_csv(f"{m.DOC}-rows.csv")
    got = m.score(d)
    assert got["rows"] == 962 and got["over_900"]["results"] == 9 and got["over_500"]["brier"] == REC["over_500"]["brier"] and got["clusters"] == 52
    assert got["mean_site_rho"] == REC["mean_site_rho"]
    assert got["logscore"] == REC["logscore"]
    assert {k: got["primary"][k]["mean"] for k in REC["primary"]} == {k: v["mean"] for k, v in REC["primary"].items()}


def test_recorded_answer_and_label():
    assert REC["holds"] == {"plain_med": True, "B_med": True}
    assert REC["label"] == "out-of-time development comparison on previously examined outcomes"
    assert "too few" in REC["over_900"]["note"]


def test_the_fetch_stayed_inside_its_caps():
    led = json.loads(Path(f"{m.DOC}-ledger.json").read_text())
    assert sum(r["weight"] for r in led["open_meteo"]) <= 300 and all(r["ok"] for r in led["open_meteo"])
    assert len(led["ea"]) <= 10 and all(r["ok"] for r in led["ea"])


COR = json.loads(Path(f"{m.CORRECTED}-scores.json").read_text())


def test_corrected_run_reproduces_and_holds(monkeypatch):
    """The correction (6 Nov 2026): rows rebuilt to match #584's (calibrated exposure). The point estimates recompute
    from the committed corrected rows, every frozen model still holds against production's form, and the original files
    are kept beside it."""
    assert m.sha(Path(f"{m.CORRECTED}-rows.csv")) == COR["rows_sha256"]
    assert COR["inputs_sha256"]["lake_line_frozen.v2.json"] == m.FROZEN_V2_SHA
    monkeypatch.setattr(m, "DRAWS", 20)
    got = m.score(pd.read_csv(f"{m.CORRECTED}-rows.csv"))
    assert got["mean_site_rho"] == COR["mean_site_rho"]
    assert all(COR["holds"].values()) and set(COR["holds"]) == {"plain_med", "B_med", "plain2_med", "B2_med", "range_med"}
    assert COR["mean_site_rho"]["range_med"] == 0.2862 and COR["mean_site_rho"]["production"] == 0.1316
    assert Path(f"{m.DOC}-scores.json").exists()   # the first report stays as the record
