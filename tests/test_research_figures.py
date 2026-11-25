"""What each figure was tested on (docs/RESEARCH-ON-THE-SITE-2026-11.md; the research catalogue's `figures`,
docs/RESEARCH-CATALOGUE-CONTRACT-v1.md). The rows a place's page and the method page show: every number in a row comes
from the catalogue entries, scorecard models or quotes it names, so a figure cannot drift from its record; the label
for its basis comes from the catalogue's fixed words, so an untested figure cannot read as tested; and every key is one
the place's page draws."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "data" / "research" / "research_catalogue.v1.json"
SCORECARD = ROOT / "data" / "research" / "model_scorecard.v1.json"
MODEL = (ROOT / "src/dipcast/site/preview/model.js").read_text()
BASES = {"held_out": "Tested on data it never saw", "seen": "Development result, on data already seen",
         "checked": "Checked against samples: no gain shown", "untested": "Not tested"}
# A row whose figure the place's page does not draw yet, and why. It shows on the method page meanwhile.
UNDRAWN = {"lake-range": "the redesign does not show the lake range (reversal 5, to be looked at again in May 2027)"}
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
squash = lambda s: re.sub(r"\s+", " ", re.sub(r"\*\*|`", "", s))


def _doc():
    return json.loads(CATALOGUE.read_text())


def _bs():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_catalogue_names_the_four_bases_in_fixed_words():
    doc = _doc()
    assert doc["version"].split(".")[:2] == ["1", "1"]
    assert doc["bases"] == BASES


def test_every_row_holds_the_rules():
    doc = _doc()
    entries = {x["id"]: x for x in doc["entries"]}
    models = {m["id"]: m for m in json.loads(SCORECARD.read_text())["models"]}
    ids = [f["id"] for f in doc["figures"]]
    assert len(ids) == len(set(ids))
    for f in doc["figures"]:
        for k in ("id", "figure", "kinds", "label", "basis", "result", "not_known", "links"):
            assert f.get(k), (f["id"], k)
        assert f["basis"] in BASES and set(f["kinds"]) <= {"river", "lake", "coast"}, f["id"]
        # Never an untested result as tested: an untested figure says what it was not tested on, nothing else.
        assert (f["basis"] == "untested") == (not f["tested_on"]), f["id"]
        assert all(x in entries for x in f["entries"]) and all(m in models for m in f["models"]), f["id"]
        text = " ".join((f["label"], f["tested_on"], f["result"], f["not_known"]))
        assert not re.search(r"\b(safe|safely|clean|cleaner|accurate|proves?|proved|all clear)\b", text, re.I), f["id"]
        assert "—" not in text, f["id"]
        # A satellite index is not a toxin measurement, and a row about one says so.
        if re.search(r"satellite|NDCI|index", text, re.I):
            assert "not a toxin" in text, f["id"]
        for link in f["links"]:
            assert link["label"] and re.match(r"(https://github\.com/ethanbuckley/swimsignal/blob/main/docs/[A-Z0-9-]+\.md|[a-z-]+\.html(#[a-z-]+)?|lab/[a-z-/]*)$", link["href"]), (f["id"], link)
            if link["href"].startswith("https://github.com"):
                assert (ROOT / "docs" / link["href"].rsplit("/", 1)[1]).is_file(), (f["id"], link)


def test_every_number_in_a_row_comes_from_what_it_rests_on():
    doc = _doc()
    entries = {x["id"]: x for x in doc["entries"]}
    models = {m["id"]: m for m in json.loads(SCORECARD.read_text())["models"]}
    for f in doc["figures"]:
        sources = [entries[x].get(k) or "" for x in f["entries"] for k in ("verdict", "scope", "stage_note")]
        sources += [models[m].get(k) or "" for m in f["models"] for k in ("tested", "misses", "wrong")]
        for q in f.get("quotes", []):
            assert squash(q["quote"]) in squash((ROOT / q["doc"]).read_text()), (f["id"], q["quote"])
            sources.append(q["quote"])
        known = set(NUMBER.findall(" ".join(sources)))
        for n in NUMBER.findall(" ".join((f["tested_on"], f["result"], f["not_known"]))):
            assert n in known, (f["id"], n)


def test_every_figure_is_one_the_place_page_draws():
    for f in _doc()["figures"]:
        # Or drawn on another page, which the row names (a beach card on coverage.html, say).
        assert f"'{f['figure']}'" in MODEL or f["figure"] in UNDRAWN or re.fullmatch(r"[a-z-]+\.html", f.get("shown_on", "")), f["id"]


def test_the_build_writes_the_rows_and_the_method_section(tmp_path):
    bs = _bs()
    assert bs.write_figures(tmp_path)["available"] is True
    out = json.loads((tmp_path / "data" / "research" / "figures.json").read_text())
    assert out["schema"] == "swimsignal.figures" and out["bases"] == BASES
    assert [f["id"] for f in out["figures"]] == [f["id"] for f in _doc()["figures"]]
    assert "quotes" not in out["figures"][0] and "entries" not in out["figures"][0]   # the sources stay in the catalogue
    page = (ROOT / "src/dipcast/pages/methods.html").read_text()
    built = bs.with_figures(page, bs.figures_doc())
    assert "<!-- FIGURES_TESTED -->" not in built and built.count('<section id="tested">') == 1
    for f in out["figures"]:
        assert f'<dt id="tested-{f["id"]}">' in built
    assert "Not tested · Rivers" in built and "Tested on data it never saw · Rivers and lakes" in built
    assert '<li><a href="#tested">What each figure was tested on</a></li>' in page
    assert bs.with_figures(page, None).count('<section id="tested">') == 0


def test_no_catalogue_means_no_file(tmp_path):
    bs = _bs()
    (tmp_path / "data" / "research").mkdir(parents=True)
    (tmp_path / "data" / "research" / "figures.json").write_text("{}")
    assert bs.write_figures(tmp_path, tmp_path / "missing.json")["available"] is False
    assert not (tmp_path / "data" / "research" / "figures.json").exists()
