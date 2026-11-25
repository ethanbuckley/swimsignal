"""Research Lab exhibit 7, a river's bad days: its file is the two committed read results as they are, every figure on
the page is read from it, and the page says what was tested, where, and what is not known."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site  # noqa: E402
import lab_river_reads  # noqa: E402

PAGE = ROOT / "prototypes" / "research-lab" / "rivers"


def test_the_file_is_the_results_as_committed():
    doc = json.loads((PAGE / "reads.json").read_text())
    assert lab_river_reads.check(doc) == []
    s = json.loads((ROOT / "docs" / "river-unseen" / "result.json").read_text())
    w = json.loads((ROOT / "docs" / "river-winter" / "result.json").read_text())
    assert doc["summer"]["order"]["candidate"]["value"] == s["primary_rho"]["value"] and doc["summer"]["range"]["pass"] is False
    assert doc["winter"]["order"]["production"]["value"] == w["condition_1_raw"]["value"] and doc["winter"]["order"]["pass"] is True
    assert len(doc["points"]) == s["points"] == 59
    assert "NaN" not in (PAGE / "reads.json").read_text()


def test_no_figure_is_typed_into_the_page():
    # Every number on the page comes from reads.json: no correlation, share or count from the results is written in.
    doc = json.loads((PAGE / "reads.json").read_text())
    text = (PAGE / "index.html").read_text() + (PAGE / "rivers.js").read_text()
    for v in (doc["summer"]["order"]["production_deployed"], doc["summer"]["order"]["rain_48h"], doc["winter"]["order"]["production"]["value"],
              doc["winter"]["level"]["mean_production_chance"], doc["summer"]["rows"], doc["winter"]["rows"]):
        for shown in {f"{v:.3f}", f"{v:.2f}", f"{100 * v:.1f}%", f"{v:,}"} if isinstance(v, float) else {str(v), f"{v:,}"}:
            assert shown not in text, shown


def test_the_page_says_what_was_tested_and_what_is_not_known():
    html = (PAGE / "index.html").read_text()
    assert "Tested, at monitoring points, not swim spots." in html and "each was read once" in html
    for limit in ("Nothing about a swim spot directly.", "Nothing about days ahead.", "Nothing about live spill reports.",
                  "Not the in-season model with soil moisture.", "Not \"safe\"."):
        assert limit in html, limit
    js = (PAGE / "rivers.js").read_text()
    assert "Neither test shows it better than the rain." in js and "development" in js
    assert not re.search(r"\b(safe to swim|clean water)\b", html + js.replace("does not mean clean water", ""), re.I)


def test_the_build_publishes_it_with_its_date(tmp_path):
    build_site.write_lab(tmp_path)
    lab = tmp_path / "lab"
    assert (lab / "rivers" / "index.html").is_file() and (lab / "rivers" / "reads.json").is_file()
    part = json.loads((lab / "refresh.json").read_text())["parts"]["river-reads"]
    assert part["as_of"] == json.loads((PAGE / "reads.json").read_text())["last_read"][:10] and "stale_days" not in part
