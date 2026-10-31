"""Measured lake temperatures on the site (build_site.write_lake_temperatures, lake-temperatures.html): the research
export (docs/LAKE-TEMPERATURE-OBS-CONTRACT-v1.md) split into an index and one file a lake, published only when it is
that contract's schema and major version, and the viewer written beside the app and listed on the data page."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "lake_temperature_obs_v1_sample.json"


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_export_is_split_into_an_index_and_a_file_a_lake(tmp_path):
    bs = _build_site()
    h = bs.write_lake_temperatures(tmp_path, SAMPLE)
    assert h == {"available": True, "lakes": 4, "skipped_ids": 0, "spots": 4, "version": "1.1.0"}
    out = tmp_path / "data" / "research" / "lake-temperatures"
    index = json.loads((out / "index.json").read_text())
    assert index["available"] is True and index["schema"] == "swimsignal.lake-temperature-obs"
    assert {"claim", "period", "method", "attribution", "coverage"} <= set(index) and "sources" not in index
    # 1.1: the page's lead and method sentence travel in the index; each lake's years list too.
    assert index["claim"]["page_wording"] and index["method"]["public_sentence"]
    assert all(len(x["summary"]["years_list"]) == x["summary"]["years"] for x in index["lakes"])
    # The index carries the list's names, counts and links, never the readings.
    for x in index["lakes"]:
        assert not {"readings", "points", "monthly"} & set(x) and len(x["n"]) == 5
    win = next(x for x in index["lakes"] if x["wb_id"] == "GB31247007")
    assert win["n"] == [143, 166, 155, 154, 104] and win["n_points"] >= 1
    assert next(x for x in index["lakes"] if x["wb_id"] == "GB31229000")["n"] == [0, 0, 3, 0, 0]   # Crummock: July only
    # The spots' links: the lake, the distance to the nearest sampling point and the years.
    assert index["spots"]["brothers-water"] == {"wb_id": "GB30229116", "lake": "Brothers Water", "nearest_point_m": 184,
                                                "outside_lake_m": 0.0, "first": "2000-07-11", "last": "2026-09-21", "readings": 22}
    assert set(index["spots"]) == {"bw-ukd1203-45650", "bw-ukd1203-45675", "brothers-water", "crummock-water"}
    whole = json.loads(SAMPLE.read_text())["lakes"][0]
    assert json.loads((out / "lake" / "GB31247007.json").read_text()) == whole   # one lake, exactly as exported
    assert sorted(p.name for p in (out / "lake").iterdir()) == sorted(f"{x['wb_id']}.json" for x in json.loads(SAMPLE.read_text())["lakes"])


def test_nothing_is_published_from_a_missing_or_foreign_export_and_only_its_own_folder_is_replaced(tmp_path):
    bs = _build_site()
    other_research = tmp_path / "data" / "research" / "lakes.json"   # another research file beside it stays
    other_research.parent.mkdir(parents=True)
    other_research.write_text("{}")
    bs.write_lake_temperatures(tmp_path, SAMPLE)
    assert bs.write_lake_temperatures(tmp_path, tmp_path / "none.json") == {"available": False, "why": "no export in this build"}
    out = tmp_path / "data" / "research" / "lake-temperatures"
    assert not list((out / "lake").iterdir())   # and nothing left from the earlier build
    v2 = tmp_path / "v2.json"
    v2.write_text(json.dumps({**json.loads(SAMPLE.read_text()), "version": "2.0.0"}))
    h = bs.write_lake_temperatures(tmp_path, v2)
    assert h["available"] is False and "not swimsignal.lake-temperature-obs 1.x" in h["why"]
    assert json.loads((out / "index.json").read_text()) == {"schema": "swimsignal.lake-temperature-obs", "available": False, "why": h["why"]}
    other = tmp_path / "other.json"
    other.write_text(json.dumps({**json.loads(SAMPLE.read_text()), "schema": "swimsignal.something-else"}))
    assert bs.write_lake_temperatures(tmp_path, other)["available"] is False
    assert not list((out / "lake").iterdir()) and other_research.read_text() == "{}"
    assert bs.write_lake_temperatures(tmp_path, SAMPLE)["available"] is True   # a 1.x again publishes


def test_the_viewer_is_written_and_listed(tmp_path, monkeypatch):
    bs = _build_site()
    monkeypatch.setattr(bs, "LAKE_TEMPS", SAMPLE)
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "lake", "days": []}], root="https://example.org/")
    html = (tmp_path / "lake-temperatures.html").read_text()
    assert "<title>Measured lake temperatures · SwimSignal</title>" in html and '<script src="lake-temperatures.js?v=' in html
    assert (tmp_path / "lake-temperatures.js").read_bytes() == (bs.TEMPLATE.parent / "lake-temperatures.js").read_bytes()
    # The shared header and foot, as the other scripted pages carry them.
    sites = (tmp_path / "sites.html").read_text()
    for tag in (r'<header class="top">.*?</header>', r'<footer class="site-foot">.*?</footer>'):
        assert re.search(tag, html, re.S).group(0) == re.search(tag, sites, re.S).group(0)
    assert json.loads((tmp_path / "data" / "research" / "lake-temperatures" / "index.json").read_text())["available"] is True
    data = (tmp_path / "data.html").read_text()
    assert 'href="lake-temperatures.html"' in data and '<tr data-file="research/">' in data
    assert "Not described here yet" not in data.split('data-file="research/"')[1].split("</tr>")[0]
    assert "<loc>https://example.org/lake-temperatures.html</loc>" in (tmp_path / "sitemap.xml").read_text()
