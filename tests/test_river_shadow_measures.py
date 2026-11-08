"""The river-rises shadow logger's committed measure list (river-shadow/measures.json, written by
scripts/river_rises_eval/shadow_measures.py) against the scope CSVs it was built from."""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "river-shadow" / "measures.json"
JS = ROOT / "river-shadow" / "src" / "measures.js"
FM = "http://environment.data.gov.uk/flood-monitoring/id/measures/"
LEVEL = re.compile(re.escape(FM) + r"[A-Za-z0-9_.-]+-level-[A-Za-z0-9_.-]+$")


def _doc():
    return json.loads(DOC.read_text())


def _csv(name):
    with (ROOT / "docs" / name).open(newline="") as f:
        return list(csv.DictReader(f))


def test_parses_with_schema():
    d = _doc()
    assert d["schema"] == "swimsignal.river-shadow.measures" and d["version"] == 1
    assert isinstance(d["stations"], list) and d["stations"]
    assert isinstance(d["missing"], list)
    for r in d["stations"]:
        assert r["role"] in ("spot", "same", "trib")
        assert isinstance(r["low"], float) and isinstance(r["high"], float) and r["low"] < r["high"]
        if r["role"] == "spot":
            assert r["spot_gauge"] == r["station"]


def test_every_spot_gauge_with_a_measure_is_covered():
    d = _doc()
    want = {r["gauge"] for r in _csv("RIVER-RISES-SCOPE-2026-10-gauges.csv") if r["measure"].strip()}
    assert len(want) == 45
    have = {r["station"] for r in d["stations"] if r["role"] == "spot"} | {m["station"] for m in d["missing"]}
    assert want <= have


def test_every_upstream_slot_is_covered():
    d = _doc()
    want = {(r["up"], r["slot"], r["gauge"]) for r in _csv("RIVER-RISES-SCOPE-2026-10-slots.csv")}
    have = {(r["station"], r["role"], r["spot_gauge"]) for r in d["stations"]}
    have |= {(m["station"], m["role"], m["spot_gauge"]) for m in d["missing"]}
    assert want <= have


def test_measures_are_flood_monitoring_level_measures():
    d = _doc()
    for r in d["stations"]:
        assert LEVEL.match(r["measure"]), r["measure"]
        assert r["measure"] in r["site_order"]
        assert all(LEVEL.match(m) for m in r["site_order"])
        # the station's own measure, under its id with spaces as underscores (e.g. "055807_TG 320")
        assert r["measure"].removeprefix(FM).startswith(r["station"].replace(" ", "_") + "-level-")


def test_no_duplicate_rows():
    keys = [(r["station"], r["role"], r["spot_gauge"]) for r in _doc()["stations"]]
    assert len(keys) == len(set(keys))


def test_worker_filter_matches():
    d = _doc()
    want = sorted({m.removeprefix(FM) for r in d["stations"] for m in r["site_order"]})
    assert d["filter"] == want
    js = JS.read_text()
    ids = json.loads(js[js.index("Object.freeze(") + len("Object.freeze("):js.rindex(");")])
    assert ids == want
