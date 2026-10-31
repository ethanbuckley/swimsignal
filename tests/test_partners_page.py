"""The page for sampling partners (src/dipcast/pages/partners.html, docs/PARTNER-PROGRAMME-2026-11.md): written with the
other prose pages, in the sitemap, linked from the clubs page, contact by email only, and the programme's wording rules
kept: test use agreed before sampling, results never a rating or "safe", and the forecast's level unchanged."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as bs  # noqa: E402

text = lambda html: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&nbsp;", " ")


def test_the_page_is_written_with_its_links_made_local(tmp_path):
    spot = {"id": "tarn", "name": "Tarn", "kind": "lake", "days": [], "location": {}}
    bs.write_pages(tmp_path, [spot], root="https://example.org/", day="2026-10-31")
    page = (tmp_path / "partners.html").read_text()
    assert "<title>Sampling partners · SwimSignal</title>" in page and 'href="/' not in page
    assert 'href="waterhead.html"' in page and 'href="privacy.html"' in page
    assert 'href="partners.html">sampling partners</a>' in (tmp_path / "clubs.html").read_text()
    assert "<loc>https://example.org/partners.html</loc>" in (tmp_path / "sitemap.xml").read_text()


def test_the_page_keeps_the_programme_s_wording_rules():
    words = text((ROOT / "src" / "dipcast" / "pages" / "partners.html").read_text())
    assert "before the season starts" in words and "label any comparison on them as exploratory" in words
    assert "not the water today" in words and "do not change the forecast's risk level" in words
    assert "Never as a bathing water rating, a pass, or a sign that the water is safe." in words
    assert 'If it says "less than 10", write that, not 0.' in words
    # The only contact is the shared address; nothing posts anywhere yet.
    assert set(re.findall(r"mailto:([^\"]+)", (ROOT / "src" / "dipcast" / "pages" / "partners.html").read_text())) == {"hello@swimsignal.co.uk"}
    assert "<form" not in (ROOT / "src" / "dipcast" / "pages" / "partners.html").read_text()
    # Design rules (docs/DESIGN.md): no pills, eyebrows or callouts.
    assert not re.search(r'class="[^"]*(pill|eyebrow|callout|badge)', (ROOT / "src" / "dipcast" / "pages" / "partners.html").read_text())


def test_the_programme_document_holds_the_open_ico_question():
    doc = (ROOT / "docs" / "PARTNER-PROGRAMME-2026-11.md").read_text()
    assert "## Open question for Ethan: the ICO data protection fee" in doc and "Nothing in this PR registers, pays or contacts the ICO." in doc
    assert "90 days from arrival" in doc and "A community report is never shown as a verified pollution warning." in doc
