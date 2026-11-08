"""scripts/derwent_level_flow.py (docs/DERWENT-WATER-DIAGNOSIS-2026-11.md, "Lake level and outflow"): the committed
daily series reproduce the recorded answer, and the fetch stayed inside its cap."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import derwent_level_flow as m  # noqa: E402


def test_committed_series_reproduce_the_recorded_answer(tmp_path, monkeypatch):
    rec = json.loads(Path(f"{m.DOC}-levelflow.json").read_text())
    monkeypatch.setattr(m, "DOC", tmp_path / "out")
    m.stage_run()
    got = json.loads((tmp_path / "out-levelflow.json").read_text())
    assert got["checks"] == rec["checks"] == {"L1": False, "L2": False, "L3": False}
    assert got["answer"] == rec["answer"] == "does not track"
    assert got["L1"] == rec["L1"] and got["L1"]["level"]["n"] == 46 and got["L1"]["flow7"]["n"] == 19
    assert rec["L3"]["computable"] is False


def test_the_fetch_stayed_inside_its_cap():
    led = json.loads(m.LEDGER.read_text())
    assert len(led) <= m.CAP and all(r["status"] == 200 for r in led)
