"""Waterhead bacteria samples on the site (build_site.write_waterhead, waterhead.html): the export
(docs/WATERHEAD-WET-CONTRACT-v1.md) holds its contract, the page shows every sample with its credit and open questions,
and an export of another schema is not published."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "data" / "research" / "waterhead_wet.v1.json"


def _mod(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


def test_the_committed_export_holds_its_contract():
    doc = json.loads(EXPORT.read_text())
    assert _mod("export_waterhead_wet").check(doc) == []
    assert [s["samples"] for s in doc["seasons"]] == [29, 30] and len(doc["samples"]) == 59
    assert doc["site"]["confirmed"] is False and "tc" not in doc["samples"][0]   # total coliforms are left out
    assert max(x["ecoli"] for x in doc["samples"]) == 649   # none over 900 (docs/WATERHEAD-WET-CONTRACT-v1.md)


def test_the_check_refuses_a_broken_export():
    m, doc = _mod("export_waterhead_wet"), json.loads(EXPORT.read_text())
    doc["samples"] = doc["samples"][1:]
    doc["claim"]["public_wording"] = "Clean water."
    assert m.check(doc) == ["the claim must say it is not today's water", "season counts do not add up to the samples"]


def test_the_page_shows_every_sample_with_its_credit(tmp_path):
    bs = _mod("build_site")
    assert bs.write_waterhead(tmp_path) == {"available": True, "samples": 59, "version": "1.1.0"}
    html = (tmp_path / "waterhead.html").read_text()
    assert "<title>Waterhead bacteria samples · SwimSignal</title>" in html and "<!-- WET" not in html
    assert html.count('<tr><th scope="row">') == 59
    assert "<th scope=\"row\">1 Jun 2026</th><td class=\"num\">649</td>" in html
    assert "Ambleside Action for a Future, Waterhead E. coli Testing (WET) project." in html
    assert "not today&#x27;s water" in html and "laboratory, method and time of day are not yet confirmed" in html
    assert json.loads((tmp_path / "data" / "research" / "waterhead_wet.json").read_text())["schema"] == "swimsignal.waterhead-wet"
    # Newest first: 2026 before 2025, and the latest sample is the first row; the forecast is linked back to.
    assert html.index("<h2>2026</h2>") < html.index("<h2>2025</h2>")
    row = lambda d: html.index(f'<th scope="row">{d}</th>')
    assert row("12 Oct 2026") < row("23 Mar 2026") < row("30 Oct 2025") and "at the time it was taken" in html
    assert '<a href="spot/osm-windermere-waterhead/">' in html and "Mostly on Thursday mornings" in html
    local = json.loads((tmp_path / "data" / "research" / "local-samples.json").read_text())
    assert local == {"available": True, "spots": {"osm-windermere-waterhead": {
        "href": "waterhead.html", "place": "Waterhead, Windermere", "by": "Ambleside Action for a Future",
        "samples": 59, "first": "2025-04-16", "last": "2026-10-12", "data": "data/research/waterhead_wet.json"}}}


def test_another_schema_is_not_published(tmp_path):
    bs = _mod("build_site")
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"schema": "swimsignal.waterhead-wet", "version": "2.0.0"}))
    h = bs.write_waterhead(tmp_path, path=other)
    assert h["available"] is False and "not swimsignal.waterhead-wet 1.x" in h["why"]
    assert "No samples are published in this build." in (tmp_path / "waterhead.html").read_text()
    assert not (tmp_path / "data" / "research" / "waterhead_wet.json").exists()
    assert json.loads((tmp_path / "data" / "research" / "local-samples.json").read_text())["available"] is False
