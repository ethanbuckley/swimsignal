"""The answer first on three standalone pages (design audit of 17 November 2026, sections 10 and 11): Research opens
with what a visitor can look at, For organisations with its two entry tasks and one line on the limit, and the worked
example no longer names the briefing script. The Accuracy page's order is checked in tests/site_verification.test.cjs."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "src" / "dipcast" / "pages"
SITE = ROOT / "src" / "dipcast" / "site"


def _main(path: Path) -> str:
    s = path.read_text()
    return s[s.index("<main"):s.index("</main>")]


def test_research_opens_with_what_to_look_at_and_every_item_keeps_its_status():
    body = _main(PAGES / "research.html")
    lead = re.search(r'<p class="lead">(.*?)</p>', body).group(1)
    assert lead.startswith("Explore satellite images, river maps and lab results.")
    assert "None of it changes a spot's level." in lead
    assert "Each item says what it is" not in body
    # Every item keeps its own stage line.
    assert body.count("<b>Status:</b>") == 12


def test_organisations_opens_with_two_tasks_then_the_limit_then_the_full_limits():
    body = _main(PAGES / "clubs.html")
    at = body.index
    assert at('<h1>For organisations</h1>') < at('>Brief a session</a>') < at('>Compare your venues</a>')
    assert 'href="/organisers.html">Brief a session' in body and 'href="organisers.html#sites-maker">Compare your venues' in body
    limit = at("<b>It is a forecast, not a water test.</b>")
    assert at('>Compare your venues</a>') < limit < at('id="limits-h"') < at("<h2>Tools for planning a session</h2>")
    # Nothing else stands between the tasks and the line on the limit.
    assert "<h2" not in body[at('id="start"'):limit]
    # The full limits and the warning figures, word for word.
    for said in ("It is a forecast, not a water test. Nothing on the site says the water is safe.",
                 '<span id="warn-figures">It misses most spills.',
                 "It sees monitored storm overflows only.",
                 "The level is about pollution only. Cold water, currents and high water stay in your own risk assessment.",
                 "It covers rivers and lakes in England. Coasts are not forecast."):
        assert said in body, said
    # Who the page is for is kept, under the tools' heading.
    assert at("<h2>Tools for planning a session</h2>") < at("One page for clubs, activity centres, Scouts and Guides leaders")
    assert "swimming, ghyll scrambling, gorge walking, paddling, sailing, windsurfing and rowing on rivers and lakes in England" in body


def test_the_worked_example_does_not_name_the_briefing_script():
    body = _main(SITE / "demo.html")
    assert "briefing.py" not in body and "<code>" not in body
    assert "This is the text a pilot briefing would carry, drawn here from the live forecast." in body
