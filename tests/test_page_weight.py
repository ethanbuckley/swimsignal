"""What the app's first view downloads. data/spots-lite.json and data/spot/<id>.json
(build_site.write_app_data): what the app loads first, and each spot's overflows and guide, which only
its own page shows; spots.json stays whole. And the built page without its comment-only script lines
and CSS comments (build_site.lean_page)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site as bs

CREDITS = {"attribution": "Contains data from the water companies", "full": "https://swimsignal.co.uk/terms.html#data"}


def _doc() -> dict:
    contrib = [{"site_id": "T1", "weight": 0.4, "p_spill_days": [0.1] * 5, "status": 0}]
    guide = {"checked": "2026-10-03", "facts": [{"kind": "parking", "text": "Car park by the bridge."}]}
    return {"generated_at": "2026-10-06T14:51:36+01:00", "version": "1", "n": 4, "build": {"spots": 4}, "credits": CREDITS,
            "spots": [{"id": "thames-henley", "name": "Henley", "days": [{"date": "2026-10-06", "label": "low"}],
                       "contributors": contrib, "guide": guide},
                      {"id": "henleaze-lake", "name": "Henleaze Lake", "days": [], "contributors": []},     # no guide
                      {"id": "osm-great-ouse-overcote", "name": "Overcote", "error": "forecast failed: x"},  # neither
                      {"id": "bad id", "name": "Odd", "days": [], "contributors": contrib, "guide": guide}]}


def test_lite_file_leaves_out_overflows_and_guides_and_each_spot_file_has_them(tmp_path):
    doc = _doc()
    stale = tmp_path / "data" / "spot" / "gone-spot.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}")                                     # a spot no longer listed
    assert bs.write_app_data(tmp_path, doc) == 3
    lite = json.loads((tmp_path / "data" / "spots-lite.json").read_text())
    assert {k: v for k, v in lite.items() if k != "spots"} == {k: v for k, v in doc.items() if k != "spots"}
    by = {s["id"]: s for s in lite["spots"]}
    assert [s["id"] for s in lite["spots"]] == [s["id"] for s in doc["spots"]]   # same spots, same order
    for sid in ("thames-henley", "henleaze-lake", "osm-great-ouse-overcote"):
        assert "contributors" not in by[sid] and "guide" not in by[sid]
        assert by[sid]["detail_file"] == f"spot/{sid}.json"
    assert by["thames-henley"]["days"] == doc["spots"][0]["days"]   # everything else as in spots.json
    assert by["bad id"] == doc["spots"][3]                         # no file name possible: kept whole
    files = sorted(p.name for p in (tmp_path / "data" / "spot").iterdir())
    assert files == ["henleaze-lake.json", "osm-great-ouse-overcote.json", "thames-henley.json"]
    d = json.loads((tmp_path / "data" / "spot" / "thames-henley.json").read_text())
    assert d == {"id": "thames-henley", "generated_at": doc["generated_at"], "contributors": doc["spots"][0]["contributors"],
                 "guide": doc["spots"][0]["guide"], "credits": CREDITS}
    assert json.loads((tmp_path / "data" / "spot" / "henleaze-lake.json").read_text())["contributors"] == []
    assert "guide" not in json.loads((tmp_path / "data" / "spot" / "henleaze-lake.json").read_text())


def test_the_lite_file_and_the_spot_files_together_are_spots_json(tmp_path):
    doc = _doc()
    bs.write_app_data(tmp_path, doc)
    lite = json.loads((tmp_path / "data" / "spots-lite.json").read_text())
    whole = []
    for s in lite["spots"]:
        if "detail_file" in s:
            extra = json.loads((tmp_path / "data" / s.pop("detail_file")).read_text())
            s.update({k: v for k, v in extra.items() if k not in ("id", "generated_at", "credits")})
        whole.append(s)
    assert whole == json.loads(json.dumps(doc["spots"]))


def test_the_data_page_describes_the_new_files(tmp_path):
    (tmp_path / "data" / "spot").mkdir(parents=True)
    (tmp_path / "data" / "spot" / "a.json").write_text("{}")
    (tmp_path / "data" / "spots-lite.json").write_text("{}")
    page, extra = bs.with_data_files((bs.STATIC / "data.html").read_text(), tmp_path / "data")
    assert extra == []
    assert 'id="spots-lite-json"' in page and "detail_file" in page


def test_comment_only_script_lines_go_and_everything_else_stays():
    js = "\n".join([
        "// a reason, on its own line",
        "const a = 1;   // a reason after code: kept",
        "    // indented, on its own line",
        "const t = `first line",
        "// inside a template: words on the page, kept",
        "${a > 0 ? `nested",
        "// inside a nested template: kept",
        "` : ''}`;",
        "const re = /['\"`]/g, d = a / 2 / 1;   // quotes in a regular expression, then division",
        "const s = 'http://example.org', u = \"//not a comment\";",
        "/* a block",
        "// inside a block comment: kept as part of it",
        "*/",
        "if (a) { return /x\\/\\//.test(s); }",
        "// the last reason",
        "const b = 2;"])
    out = bs.js_without_comment_lines(js).split("\n")
    assert "// a reason, on its own line" not in out and "    // indented, on its own line" not in out
    assert "// the last reason" not in out
    for kept in ("const a = 1;   // a reason after code: kept", "// inside a template: words on the page, kept",
                 "// inside a nested template: kept", "// inside a block comment: kept as part of it", "const b = 2;"):
        assert kept in out
    assert len(out) == 13


def test_a_script_the_reader_cannot_follow_is_left_whole():
    for js in ("const t = `never closed\n// a line\n", "const s = 'runs on \\\n// a line\nstill';",
               "x = 1 /* never closed\n// a line\n"):
        assert bs.js_without_comment_lines(js) == js


def test_the_page_keeps_its_html_comments_and_loses_css_comments():
    html = ("<!-- page-meta --><title>x</title><!-- /page-meta -->\n<style>a { color: red; } /* why red */\n</style>\n"
            "<script>\n// why\nlet x = 1;\n</script>\n<script src=\"a.js\">\n</script>")
    out = bs.lean_page(html)
    assert out == ("<!-- page-meta --><title>x</title><!-- /page-meta -->\n<style>a { color: red; } \n</style>\n"
                   "<script>\nlet x = 1;\n</script>\n<script src=\"a.js\">\n</script>")


def test_the_built_app_page_has_no_comment_only_script_lines_but_works_the_same():
    """The real page: its scripts lose 20% or more of their length, so the reader followed them to the
    end. (On 6 Oct 2026 esbuild, run by hand, minified each script to the same bytes before and after.)"""
    src = (bs.TEMPLATE).read_text()
    lean = bs.lean_page(src)
    before = [m.group(2) for m in bs.INLINE_SCRIPT.finditer(src)]
    after = [m.group(2) for m in bs.INLINE_SCRIPT.finditer(lean)]
    assert len(after) == len(before) and sum(map(len, after)) < 0.8 * sum(map(len, before))
    assert bs.PAGE_META.search(lean) and bs.LOADING in lean
