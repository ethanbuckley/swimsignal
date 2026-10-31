"""The research catalogue (docs/RESEARCH-CATALOGUE-CONTRACT-v1.md, build_site.write_research_catalogue): every record the
recovery register links is in it, each quote is word for word in its record, an archived version says what would reopen
it, adopted and scheduled work does not read as archived, and the page shows every entry."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "data" / "research" / "research_catalogue.v1.json"
REGISTER = ROOT / "docs" / "RESEARCH-RECOVERY-2026-10.md"


def _doc():
    return json.loads(CATALOGUE.read_text())


def _mod(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


def test_every_entry_holds_the_contract():
    doc = _doc()
    assert doc["schema"] == "swimsignal.research-catalogue" and doc["version"].split(".")[0] == "1"
    ids = [x["id"] for x in doc["entries"]]
    assert len(ids) == len(set(ids))
    for x in doc["entries"]:
        for k in ("id", "title", "section", "topics", "verdict", "scope", "stage", "stage_note", "records", "prs"):
            assert x.get(k), (x["id"], k)
        assert x["stage"] in doc["stages"] and x["section"] in doc["sections"], x["id"]
        assert all(str(n) in doc["prs"] for n in x["prs"]), x["id"]
        if x["stage"] == "archived":   # an archived version says what would reopen it
            assert x.get("reopen_when"), x["id"]
        else:   # work in use, running or waiting does not read as archived
            assert "reopen_when" not in x, x["id"]
        if x["stage"] == "scheduled":
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", x.get("read_on", "")), x["id"]
        assert not re.search(r"\b(impossible|proves?|proved|cannot help)\b", x["verdict"] + x["scope"], re.I), x["id"]


def test_every_quote_is_word_for_word_in_its_record():
    for x in _doc()["entries"]:
        for r in x["records"]:
            if "branch" in r:   # a closed PR's record, only on its branch
                assert any(p["branch"] == r["branch"] for p in (_doc()["prs"][str(n)] for n in x["prs"])), x["id"]
                continue
            text = (ROOT / r["doc"]).read_text()
            assert r.get("quote", "") in text, (x["id"], r["doc"], r.get("quote"))


def test_every_record_the_register_links_is_catalogued():
    doc = _doc()
    register = REGISTER.read_text()
    linked = {"docs/" + f for f in re.findall(r"\]\(([A-Z0-9_.-]+\.md)\)", register)} - {"docs/RESEARCH-WORKFLOW.md", "docs/RESEARCH-CATALOGUE-CONTRACT-v1.md"}
    held = {r["doc"] for x in doc["entries"] for r in x["records"]}
    assert linked - held == set()
    prs = {n for x in doc["entries"] for n in x["prs"]}
    for n in (181, 187, 208, 219, 396):   # the closed, unmerged PRs the register names
        assert n in prs and doc["prs"][str(n)]["state"] == "closed" and doc["prs"][str(n)]["branch"]
    assert "docs/NOISE-AUDIT-2026-10.md" in held


def test_the_page_shows_every_entry(tmp_path):
    bs, doc = _mod("build_site"), _doc()
    assert bs.write_research_catalogue(tmp_path) == {"available": True, "entries": len(doc["entries"]), "version": doc["version"]}
    html = (tmp_path / "research-catalogue.html").read_text()
    assert "<title>Research catalogue · SwimSignal</title>" in html and "<!-- CATALOGUE" not in html
    assert html.count('<section class="rc-entry"') == len(doc["entries"])
    assert all(f'id="{x["id"]}"' in html for x in doc["entries"])
    assert 'href="https://github.com/ethanbuckley/swimsignal/pull/187">#187</a> (closed, not merged, branch <code>claude/lake-near-field</code>)' in html
    assert "blob/claude/lake-near-field/docs/LAKE-NEAR-FIELD-TEST-2026-10.md" in html
    assert "<b>Reopen when:</b>" in html and "Next date: 28 Nov 2026." in html
    assert 'data-stage="scheduled"' in html and '<option value="archived">This version archived</option>' in html
    assert json.loads((tmp_path / "data" / "research" / "research_catalogue.json").read_text())["schema"] == "swimsignal.research-catalogue"


def test_another_schema_is_not_published(tmp_path):
    bs = _mod("build_site")
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"schema": "swimsignal.research-catalogue", "version": "2.0.0"}))
    h = bs.write_research_catalogue(tmp_path, path=other)
    assert h["available"] is False and "not swimsignal.research-catalogue 1.x" in h["why"]
    assert "No records are published in this build." in (tmp_path / "research-catalogue.html").read_text()
    assert not (tmp_path / "data" / "research" / "research_catalogue.json").exists()
