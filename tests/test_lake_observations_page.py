"""The satellite lake observations on the site (build_site.write_lake_observations, lakes.html): the research export
(docs/LAKE-OBSERVATIONS-CONTRACT-v1.md) split into an index and one file a monitoring location, published only when
it is that contract's schema and major version, and the Research page and its viewer linked from every page."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "lake_observations_v1_sample.json"


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_export_is_split_into_an_index_and_a_file_a_location(tmp_path):
    bs = _build_site()
    h = bs.write_lake_observations(tmp_path, SAMPLE)
    assert h == {"available": True, "lakes": 5, "skipped_ids": 0, "version": "1.1.0", "processing": "s2c1-l2a.ndci-core-median.v1"}
    index = json.loads((tmp_path / "data" / "research" / "lakes.json").read_text())
    assert index["available"] is True and index["schema"] == "swimsignal.lake-observations"
    # The index carries what the list and the claim need, never the readings or the lab values.
    assert {"claim", "freshness_rules", "lab_definition", "processing", "coverage"} <= set(index)
    for x in index["lakes"]:
        assert "series" not in x and "lab" not in x and {"latest", "seasons", "series_scope", "n_series", "n_lab"} <= set(x)
    whole = json.loads(SAMPLE.read_text())["lakes"][1]
    one = json.loads((tmp_path / "data" / "research" / "lake" / f"{whole['lake_id']}.json").read_text())
    assert one == whole   # one location, exactly as exported


def test_nothing_is_published_from_a_missing_or_foreign_export(tmp_path):
    bs = _build_site()
    assert bs.write_lake_observations(tmp_path, tmp_path / "none.json") == {"available": False, "why": "no export in this build"}
    other = tmp_path / "v2.json"
    other.write_text(json.dumps({**json.loads(SAMPLE.read_text()), "version": "2.0.0"}))
    h = bs.write_lake_observations(tmp_path, other)
    assert h["available"] is False and "not swimsignal.lake-observations 1.x" in h["why"]
    assert json.loads((tmp_path / "data" / "research" / "lakes.json").read_text())["available"] is False
    assert not list((tmp_path / "data" / "research" / "lake").iterdir())   # and nothing left from an earlier build


def test_research_and_the_viewer_are_written_and_linked_from_every_page(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "lake", "days": []}], root="https://example.org/")
    research, lakes = (tmp_path / "research.html").read_text(), (tmp_path / "lakes.html").read_text()
    assert "<title>Research · SwimSignal</title>" in research and 'href="lakes.html"' in research
    assert "<title>Satellite lake observations · SwimSignal</title>" in lakes and '<script src="lakes.js?v=' in lakes
    assert (tmp_path / "lakes.js").read_bytes() == (bs.TEMPLATE.parent / "lakes.js").read_bytes()
    # In the header (desktop) and the foot (every width) of the app and of every prose page.
    for page in ("index.html", "about.html", "methods.html", "verification.html", "data.html", "feedback.html", "clubs.html",
                 "organisers.html", "sites.html", "lakes.html", "research.html", "404.html"):
        html = (tmp_path / page).read_text()
        assert html.count("research.html") >= 2, page
