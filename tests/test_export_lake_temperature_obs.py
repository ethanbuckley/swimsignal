"""scripts/export_lake_temperature_obs.py: the committed file holds docs/LAKE-TEMPERATURE-OBS-CONTRACT-v1.md."""

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import export_lake_temperature_obs as m  # noqa: E402


def _doc():
    return json.loads((ROOT / "data" / "research" / "lake_temperature_obs.v1.json").read_text())


def test_the_committed_file_holds_the_contract():
    d = _doc()
    assert m.check(d) == []
    linked = {s["spot_id"] for lk in d["lakes"] for s in lk["spots"]}
    import csv
    ids = {r["id"] for r in csv.DictReader((ROOT / "spots.csv").open())}
    assert linked <= ids and len(linked) == d["coverage"]["spots_linked"]


def test_check_catches_broken_files():
    d = _doc()
    bad = copy.deepcopy(d)
    lk = bad["lakes"][0]
    lk["readings"]["date"][0] = lk["readings"]["date"][0][:5] + "01" + lk["readings"]["date"][0][7:]
    assert any("outside May-September" in e or "date order" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][0]["readings"]["temp"][0] = 40.0
    assert any("outside 0-35" in e for e in m.check(bad))
    bad = copy.deepcopy(d)
    bad["claim"]["public_wording"] = "The lake is 18 C."
    assert any("today's temperature" in e for e in m.check(bad))
