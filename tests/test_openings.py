"""Spot openings (src/dipcast/openings.py, guides/openings/openings.toml): every entry is valid before a build runs, says
nothing a source does not, and carries no safety claim; the build's own sentence on what is upstream follows the
trace and never calls missing data low; the page's description, its built HTML and its structured data carry it."""

import csv
import json
import re
import sys
import tomllib
from datetime import date
from pathlib import Path

import pytest

from dipcast import openings as op

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def spot_ids() -> set[str]:
    return {r["id"] for f in ("spots.csv", "spots-osm.csv", "spots-scotland.csv") for r in csv.DictReader((ROOT / f).open())}


def test_every_opening_in_the_file_is_valid_and_names_a_listed_spot():
    entries, warnings = op.load_openings(spot_ids())
    assert warnings == []
    raw = tomllib.loads(op.OPENINGS.read_text())
    assert set(entries) == set(raw), "no entry is left out"
    assert len(entries) <= 40
    for sid, e in entries.items():
        assert 1 <= op.sentences(e["place"]) <= 2 and len(e["place"]) <= op.MAX_PLACE, sid
        assert e["sources"] and all(s["url"].startswith("https://") for s in e["sources"]), sid
        assert date.fromisoformat(e["checked"]) <= date(2026, 11, 10), sid
        assert not re.search(r"\b(?:safe|clean|low risk)\b", e["place"], re.IGNORECASE), sid


def test_the_file_says_how_the_spots_were_chosen_without_the_private_figures():
    head = op.OPENINGS.read_text().split("\n[", 1)[0]
    assert "40 most-visited" in head and "private" in head
    assert not re.search(r"\b\d+ visits\b", head)


@pytest.mark.parametrize("text, why", [
    ("A quiet lake. The water is safe for swimming.", "safe"),
    ("A popular river beach.", "popular"),
    ("The cleanest lake in Cumbria.", "clean"),
    ("A stunning tarn.", "stunning"),
    ("Low risk most days.", "low risk"),
])
def test_an_opening_cannot_make_a_safety_claim_or_sound_like_an_advert(text, why):
    with pytest.raises(op.OpeningError, match="verdict or an advert"):
        op.parse_entry({"text": text, "checked": date(2026, 11, 10), "sources": [{"name": "X", "url": "https://x.example/"}]}, "x")


@pytest.mark.parametrize("raw, match", [
    ({"text": "A lake.", "checked": date(2026, 11, 10)}, "sources"),
    ({"text": "A lake.", "checked": date(2026, 11, 10), "sources": [{"name": "X", "url": "http://x.example/"}]}, "https"),
    ({"text": "A lake.", "sources": [{"name": "X", "url": "https://x.example/"}]}, "checked"),
    ({"text": "One. Two. Three.", "checked": date(2026, 11, 10), "sources": [{"name": "X", "url": "https://x.example/"}]}, "one or two"),
    ({"text": "A lake.", "checked": date(2026, 11, 10), "sources": [{"name": "X", "url": "https://x.example/"}], "note": "x"}, "only"),
    ({"text": "x" * 400 + ".", "checked": date(2026, 11, 10), "sources": [{"name": "X", "url": "https://x.example/"}]}, "at most"),
])
def test_a_bad_entry_says_what_is_wrong(raw, match):
    with pytest.raises(op.OpeningError, match=match):
        op.parse_entry(raw, "x")


def _ov(name, km, lake_km=0.0, company="United Utilities"):
    return {"site_name": name, "company": company, "distance_km": km, "lake_distance_km": lake_km}


def test_the_upstream_sentence_follows_the_trace():
    river = {"kind": "river", "upstream_summary": {"overflows": 22, "with_live_feed": 20, "companies": ["Anglian Water"]},
             "contributors": [_ov("HASLINGFIELD-STW", 5.8), _ov("BURES HAMLET-SP", 22.1), _ov("X", None)]}
    assert op.upstream_sentence(river) == ("SwimSignal's trace of the river network finds 22 monitored storm overflows within 60 km "
                                           "upstream, all run by Anglian Water; the nearest, Haslingfield sewage works overflow, is 5.8 km "
                                           "upstream, and 2 of the 22 do not report live.")
    # A lake: the distance by water is along the river, then across the lake.
    lake = {"kind": "lake", "upstream_summary": {"overflows": 3, "with_live_feed": 3, "companies": ["United Utilities"]},
            "contributors": [_ov("Glebe Road PS", 0.0, 7.1), _ov("AMBLESIDE WwTW", 1.4, 0.4)]}
    assert "the nearest, Ambleside sewage works overflow, is 1.8 km away by water." in op.upstream_sentence(lake)
    one = {"kind": "river", "upstream_summary": {"overflows": 1, "with_live_feed": 0, "companies": ["Dwr Cymru Welsh Water"]},
           "contributors": [_ov("CASTERTON WwTW", 2.04)]}
    assert op.upstream_sentence(one) == ("SwimSignal's trace of the river network finds one monitored storm overflow within 60 km "
                                         "upstream, run by Dŵr Cymru Welsh Water; it is Casterton sewage works overflow, 2.0 km upstream, "
                                         "and it does not report live.")
    two = {"kind": "river", "upstream_summary": {"overflows": 13, "with_live_feed": 1, "companies": ["Dwr Cymru Welsh Water", "United Utilities"]},
           "contributors": [_ov("Chester Belgrave Park", 1.4)]}
    assert "run by Dŵr Cymru Welsh Water and United Utilities;" in op.upstream_sentence(two)


def test_missing_data_is_never_said_as_low():
    none = op.upstream_sentence({"kind": "river", "upstream_summary": {"overflows": 0}, "contributors": []})
    assert "finds no monitored storm overflow within 60 km upstream" in none and "not traced" in none
    isolated = op.upstream_sentence({"kind": "lake", "error": "An isolated lake: the river network links no monitored storm overflow to it."})
    assert "no monitored storm overflow can be traced to it" in isolated and "not checked" in isolated
    assert op.upstream_sentence({"kind": "river", "error": "forecast failed: timeout"}) == ""
    for s in (none, isolated):
        assert not re.search(r"\b(?:safe|clean|low|no risk)\b", s, re.IGNORECASE)


def test_attach_puts_the_opening_on_listed_spots_only(tmp_path):
    f = tmp_path / "openings.toml"
    f.write_text('[a]\ntext = "A lake on a hill."\nchecked = 2026-11-10\nsources = [{ name = "Owner", url = "https://owner.example/a" }]\n'
                 '[gone]\ntext = "Not a spot."\nchecked = 2026-11-10\nsources = [{ name = "Owner", url = "https://owner.example/b" }]\n')
    results = [{"id": "a", "kind": "lake", "upstream_summary": {"overflows": 0}}, {"id": "b", "kind": "river"}]
    got = op.attach_openings(results, f)
    assert got["openings"] == 1 and any("gone" in w for w in got["warnings"])
    o = results[0]["opening"]
    assert o["place"] == "A lake on a hill." and o["text"].startswith("A lake on a hill. SwimSignal's trace")
    assert o["sources"] == [{"name": "Owner", "url": "https://owner.example/a"}] and o["checked"] == "2026-11-10"
    assert "opening" not in results[1]


def test_a_spots_page_carries_its_opening_as_its_description_its_place_and_its_structured_data(tmp_path):
    bs = _build_site()
    opening = {"place": "A pool on the beck, reached from the village car park.", "checked": "2026-11-10",
               "upstream": "SwimSignal's trace of the river network finds no monitored storm overflow within 60 km upstream; farm runoff, wildlife and other bathers are not traced.",
               "sources": [{"name": "The <Park> Authority", "url": "https://park.example/pool"}]}
    opening["text"] = opening["place"] + " " + opening["upstream"]
    spots = [{"id": "pool", "name": "The Pool", "kind": "river", "lat": 54.0, "lon": -2.1, "upstream_summary": {"overflows": 0},
              "days": [{"label": "low"}], "opening": opening},
             {"id": "other", "name": "Other", "kind": "river", "upstream_summary": {"overflows": 4}, "days": [{"label": "low"}]}]
    bs.write_pages(tmp_path, spots, root="https://example.org/", day="2026-11-10")
    page = (tmp_path / "spot" / "pool" / "index.html").read_text()
    head = page.split("</head>")[0]
    from html import escape
    assert f'<meta name="description" content="{escape(opening["text"])}">' in head
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', head).group(1))
    assert ld["@graph"][0]["description"] == opening["text"]
    other = (tmp_path / "spot" / "other" / "index.html").read_text().split("</head>")[0]
    assert escape(bs.spot_blurb(spots[1])) in other   # no opening: the one-line description, as before
    assert "id=\"place\"" not in (tmp_path / "spot" / "other" / "index.html").read_text()
    # The opening is in the detail file the spot's page reads, not in the list's lite file.
    assert "opening" in bs.DETAIL_FIELDS


def test_the_built_opening_matches_the_one_the_page_draws():
    """place_html (the build's copy, for crawlers and readers without scripts) and guide.js's placeTile give the same
    words and links."""
    import subprocess
    bs = _build_site()
    d = {"id": "pool", "name": "The Pool", "opening": {"place": "A pool's edge & a beck.", "upstream": "Nothing upstream is traced.",
                                                        "sources": [{"name": "Owner", "url": "https://owner.example/?a=1&b=2"}]}}
    js = subprocess.run(["node", "-e", "const g=require('./src/dipcast/site/guide.js');process.stdout.write(g.placeTile(JSON.parse(process.argv[1])))",
                         json.dumps(d)], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    py = bs.place_html(d)
    words = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h.replace("&#x27;", "'").replace("&#39;", "'"))).strip()   # noqa: E731
    assert words(js) == words(py) and "edge &amp; a beck." in py
    assert re.findall(r'href="([^"]+)"', js) == re.findall(r'href="([^"]+)"', py) == ["https://owner.example/?a=1&amp;b=2"]
