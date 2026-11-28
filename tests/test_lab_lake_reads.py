"""Research Lab exhibit 8 (docs/LAB-LAKES-EXHIBIT-2026-11.md): its reads.json matches the committed results it was made
from, carries no NaN, and the page types no figure of its own."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lab_lake_reads  # noqa: E402


def test_the_committed_file_matches_its_sources():
    raw = lab_lake_reads.OUT.read_text()
    assert "NaN" not in raw, "browsers refuse NaN in JSON"
    doc = json.loads(raw)
    assert lab_lake_reads.check(doc) == []
    assert doc["order"]["rho"]["value"] > 0.28 and doc["own_level"]["inside"]["value"] > 0.86
    assert len(doc["lakes"]) == 12 and sum(x["had_level"] for x in doc["lakes"]) == 5


def test_the_page_reads_every_figure_from_the_file():
    js = (ROOT / "prototypes" / "research-lab" / "lakes" / "lakes.js").read_text()
    html = (ROOT / "prototypes" / "research-lab" / "lakes" / "index.html").read_text()
    for figure in ("0.289", "86.9", "69.4", "0.286"):
        assert figure not in js and figure not in html, figure
    assert "fetch('reads.json')" in js and "development" in js
