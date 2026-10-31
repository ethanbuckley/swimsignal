"""scripts/export_spill_durations.py: the contract check, and the committed file (docs/SPILL-DURATIONS-CONTRACT-v1.md)."""

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import export_spill_durations as m  # noqa: E402


def _doc():
    return json.loads((ROOT / "data" / "research" / "spill_durations.v1.json").read_text())


def test_the_committed_file_holds_the_contract():
    d = _doc()
    assert m.check(d) == []
    assert d["coverage"]["overflows"] == len(d["overflows"]["site_id"]) > 10000
    assert set(d["companies"]) == {c["company"] for c in d["company"]}


def test_check_catches_broken_files():
    d = _doc()
    bad = copy.deepcopy(d)
    bad["overflows"]["median_h"][0] = bad["overflows"]["longest_h"][0] + 1
    assert any("out of order" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["overflows"]["few"] = bad["overflows"]["few"][:-1]
    assert any("differ in length" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    r = bad["still_running"][0]
    r["still_after_24h"] = r["still_after_1h"] + 0.1
    assert any("rise with time" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["claim"]["public_wording"] = "How long spills will last."
    assert any("not a forecast" in e for e in m.check(bad))


def test_persistence_rows_carry_years_words_and_counts():
    for r in _doc()["still_running"]:
        assert r["years"] == "2024-2025" and r["label"] and 0 < r["spills"] <= r["hours"]
    assert _doc()["still_running"][0]["label"].startswith("any spill")
