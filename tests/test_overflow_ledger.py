"""The overflow ledger (LEDGER stage 1, docs/OVERFLOW-LEDGER-CONTRACT-v1.md): the roll-up adds exhibit 2's weights and
makes none of its own, the committed file holds its contract and says what it is, and the site build leaves the
prototype page out."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site  # noqa: E402
import export_overflow_ledger as ledger  # noqa: E402

FILE = ROOT / "data" / "research" / "overflow_ledger.v1.json"
PAGE = ROOT / "prototypes" / "research-lab" / "overflow-ledger"


def _ov(oid, weight, spills=10.0, company="A Water", name="AN OVERFLOW"):
    return {"id": oid, "name": name, "company": company, "water": "River X", "lat": 54.0, "lon": -2.0,
            "spills_a_year": spills, "travel_h": 1.0, "weight": weight, "decay": weight, "dilution": 1.0,
            "distance_km": 1.0, "lake_km": 0.0}


@pytest.fixture
def export(tmp_path) -> Path:
    """A small exhibit 2 export: two spots sharing one overflow, one spot alone, one with none, one off the network."""
    spots = {"s1": [_ov("O1", 0.5), _ov("O2", 0.25, spills=float("nan"))],
             "s2": [_ov("O1", 0.2), _ov("O3", 0.9, company="B Water", name=float("nan"))],
             "s3": [_ov("O4", 0.1, spills=4.0)], "s4": []}
    index = [{"id": k, "name": k.upper(), "kind": "river", "area": None, "mode": "river", "overflows": len(v)} for k, v in spots.items()]
    index.append({"id": "s5", "name": "S5", "kind": "lake", "area": None, "mode": "ground", "overflows": 0, "note": "not on the mapped river network"})
    for k, v in spots.items():
        (tmp_path / f"{k}.json").write_text(json.dumps({"id": k, "overflows": v, "lines": []}))
    (tmp_path / "index.json").write_text(json.dumps({
        "made": "2026-11-17T00:00:00+00:00", "settings": {"t90_h": 72.0, "max_upstream_km": 60.0}, "inputs": {},
        "credit": ["A credit line"], "spots": index}))
    return tmp_path


def test_the_roll_up_adds_the_exports_weights(export):
    doc = ledger.rollup(export, generated_at="2026-11-17T00:00:00+00:00")
    assert ledger.check(doc) == []
    o = doc["overflows"]
    row = {k: v[o["site_id"].index("O1")] for k, v in o.items()}
    assert (row["spots_reached"], row["weight_sum"], row["weight_max"], row["weighted_spills"]) == (2, 0.7, 0.5, 7.0)
    assert doc["spots"][row["max_spot"]]["id"] == "s1" and row["top_at"] == 1   # largest at s1; O3 is larger at s2
    assert row["links"] == [[0, 0.5, 1.0], [1, 0.2, 1.0]]
    assert o["site_id"][0] == "O3"   # ordered by summed weight
    # no average in the return: no weighted spills, never a zero; a missing name is null, and the file is plain JSON
    i2, i3 = o["site_id"].index("O2"), o["site_id"].index("O3")
    assert o["spills_a_year"][i2] is None and o["weighted_spills"][i2] is None and o["name"][i3] is None
    json.dumps(doc, allow_nan=False)
    assert doc["attribution"] == ["A credit line"]   # the export's credits carried through


def test_groups_and_coverage(export):
    doc = ledger.rollup(export)
    assert [g["spots"] for g in doc["groups"]] == [[0, 1], [2]]   # s1 and s2 share O1; s3 stands alone
    assert doc["groups"][0]["overflows"] == 3 and doc["groups"][0]["links"] == 4
    c = doc["coverage"]
    assert (c["spots"], c["spots_with_overflows"], c["spots_no_overflow"], c["spots_off_network"]) == (5, 3, 1, 1)
    assert (c["overflows"], c["links"], c["overflows_reaching_one_spot"], c["overflows_without_average"]) == (4, 5, 3, 1)
    assert [s["status"] for s in doc["spots"]] == ["traced", "traced", "traced", "no_overflow", "off_network"]
    by = {x["company"]: x for x in doc["company"]}
    assert by["A Water"]["overflows"] == 3 and by["A Water"]["no_average"] == 1 and by["B Water"]["spots"] == 1


def test_check_catches_a_changed_figure(export):
    doc = ledger.rollup(export)
    doc["overflows"]["weight_sum"][0] += 0.1
    assert any("roll-up" in b for b in ledger.check(doc))
    doc = ledger.rollup(export)
    doc["claim"]["not_claimed"] = []
    assert "claim.not_claimed" in ledger.check(doc)


def test_the_script_makes_no_exposure_calculation():
    """It reads the export's weights. It does not import the transport code that computes them."""
    src = (ROOT / "scripts" / "export_overflow_ledger.py").read_text()
    assert "upstream_overflows" not in src.split('"""', 2)[2] and "combine_daily" not in src
    assert "lab_pollution_paths" in src


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(FILE.read_text())


def test_the_committed_file_holds_the_contract(doc):
    assert ledger.check(doc) == []
    assert doc["schema"] == "swimsignal.overflow-ledger" and doc["version"] == "1.0.0"
    assert doc["source_export"]["settings"]["t90_h"] == 72.0 and doc["source_export"]["settings"]["river_velocity_ms"] == 0.2
    assert all(x["unchanged_after"] and len(x["sha256"]) == 64 for x in doc["inputs"]) and len(doc["inputs"]) == 4
    assert any("OS Open Rivers" in a for a in doc["attribution"]) and any("Environment Agency" in a for a in doc["attribution"])
    listed = {r["id"] for f in ("spots.csv", "spots-osm.csv") for r in __import__("csv").DictReader(open(ROOT / f))}
    assert {s["id"] for s in doc["spots"]} == listed and doc["coverage"]["spots_error"] == 0


def test_the_file_says_it_is_model_accounting(doc):
    claim = doc["claim"]
    assert "An account of SwimSignal's forecast model, not of measured bacteria" in claim["public_wording"]
    assert any("caused a sample result" in t for t in claim["not_claimed"]) and any("permit" in t for t in claim["not_claimed"])
    ev = claim["evidence"]
    assert "0.376" in ev["text"] and "0.355" in ev["text"]
    record = (ROOT / ev["record"]).read_text()   # the figures are the record's own
    assert "| Production as deployed | 0.376 |" in record and "| Rain in the last 48 hours alone | 0.355 |" in record
    assert "not in this version" in doc["definitions"]["season_figure_not_made"]


def test_cromwheel_matches_the_forecasts_own_export(doc):
    """The repository's exhibit 2 copy for Cromwheel (1 Nov 2026, the same overflow table): the same 16 weights."""
    spot = next(i for i, s in enumerate(doc["spots"]) if s["id"] == "bw-uke4100-08901")
    o = doc["overflows"]
    mine = {o["site_id"][i]: ln[1] for i in range(len(o["site_id"])) for ln in o["links"][i] if ln[0] == spot}
    old = json.loads((ROOT / "prototypes" / "research-lab" / "assets" / "paths" / "bw-uke4100-08901.json").read_text())
    assert mine == {x["id"]: x["weight"] for x in old["overflows"]} and len(mine) == 16


def test_the_page_says_what_it_is():
    html = (PAGE / "index.html").read_text()
    assert '<meta name="robots" content="noindex">' in html
    assert "An account of the model, not of measured bacteria" in html and "Not published" in html
    js = (PAGE / "ledger.js").read_text()
    assert "Model weights, not measurements" in js
    for word in ("causes", "caused by", "responsible for", "polluter", "worst"):   # no blame, no league table
        assert word not in html.lower() and word not in js.lower(), word


def test_the_build_leaves_the_ledger_out(tmp_path):
    assert "overflow-ledger" in build_site.LAB_UNPUBLISHED and "overflow_ledger.v1.json" not in build_site.LAB_DATA
    build_site.write_lab(tmp_path)
    lab = tmp_path / "lab"
    assert (lab / "pollution" / "index.html").is_file() and not (lab / "overflow-ledger").exists()
    for f in lab.rglob("*"):
        if f.suffix in (".html", ".js", ".css"):
            text = f.read_text(errors="ignore")
            assert "overflow-ledger" not in text and "overflow_ledger" not in text, f


def test_no_published_page_links_the_ledger():
    for f in [*(ROOT / "src" / "dipcast").rglob("*.html"), *(ROOT / "src" / "dipcast").rglob("*.js"),
              *(ROOT / "prototypes" / "research-lab").rglob("*")]:
        if f.is_file() and f.suffix in (".html", ".js") and PAGE not in f.parents:
            assert "overflow-ledger" not in f.read_text() and "overflow_ledger" not in f.read_text(), f
