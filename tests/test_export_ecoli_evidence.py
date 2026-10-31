"""scripts/export_ecoli_evidence.py: the committed file holds docs/ECOLI-EVIDENCE-CONTRACT-v1.md."""

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import export_ecoli_evidence as m  # noqa: E402


def _doc():
    return json.loads((ROOT / "data" / "research" / "ecoli_evidence.v1.json").read_text())


def test_the_committed_file_holds_the_contract():
    d = _doc()
    assert m.check(d) == []
    assert d["hindsight"]["issued"] is False
    assert {s["bw_id"] for s in d["sites"]} == {s["id"] for s in json.loads((ROOT / "data/raw/bathing_waters_inland.json").read_text())}


def test_check_catches_broken_files():
    d = _doc()
    bad = copy.deepcopy(d)
    bad["hindsight"]["issued"] = True
    assert any("not issued" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    x = bad["sites"][0]["samples"][0]
    x["over"] = not x["over"]
    assert any("over flag" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["sites"][0]["samples"].reverse()
    assert any("time order" in e for e in m.check(bad))
