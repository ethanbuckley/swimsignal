"""The redesign's ways to the research (docs/RESEARCH-ON-THE-SITE-2026-11.md): its foot is the site's one list of links
(docs/DESIGN.md, "One foot, one opening", 12 Nov 2026), so Research and data is a link away from every page, and a
place's page lists the Research Lab's exhibits that hold its record."""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site  # noqa: E402

APP = (ROOT / "src/dipcast/site/preview/app.js").read_text()


def test_the_foot_is_the_sites_one_list_less_data_credits():
    found = re.search(r"const FOOT_LINKS = (\[.*?\]);\n", APP, re.S)
    assert found, "app.js has lost FOOT_LINKS"
    mine = [tuple(x) for x in ast.literal_eval(found.group(1).replace("\n", " "))]
    want = [x for x in build_site.FOOT_LINKS if x[1] != "Data credits"]   # the foot's credits fold gives them, as on the app's foot
    assert mine == want
    assert "Source code</a> (MIT)" in APP and build_site.SOURCE_LINK in APP


def test_the_foot_no_longer_has_its_own_short_list():
    assert "Method and limits</a> · <a href=\"verification.html\">How accurate it has been" not in APP
    assert '<p class="foot-links">${footLinks()}</p>' in APP


def test_the_lab_section_keeps_the_earlier_tiles_words():
    live = (ROOT / "src/dipcast/site/index.html").read_text()
    for words in ("Its satellite pictures and readings, cloudy days left blank. Not a toxin measurement.",
                  "Its E. coli samples against what the estimate, rebuilt afterwards, would have said.",
                  "Rain, spills and samples around it on one timeline, January 2024 to September 2026.",
                  "No Research Lab exhibit holds a record for this spot yet.",
                  "Research Lab: exploratory, on data already read. It changes nothing in this forecast."):
        assert words in live and words in APP, words
