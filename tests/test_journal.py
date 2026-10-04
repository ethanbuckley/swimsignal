"""The swim journal (src/dipcast/site/journal.js) is built and stored with the app: the page asks for
it at the build's stamp, after the scripts it uses, the offline copy keeps it, and a change to it
renames the offline copy's cache. Its rules are tested in tests/site_journal.test.cjs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_page_loads_the_journal_from_its_build(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    page = (tmp_path / "index.html").read_text()
    assert f'<script src="journal.js?v={stamp}">' in page
    # After reviews.js (its photo shrinking) and levels.js (the headline it keeps).
    assert page.index('src="reviews.js') < page.index('src="levels.js') < page.index('src="journal.js')
    assert (tmp_path / "journal.js").read_bytes() == (bs.TEMPLATE.parent / "journal.js").read_bytes()
    assert "`journal.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "journal.js" in bs.SHELL_SOURCES
    # The Saved page and a spot's page are the same app page, so both have it.
    assert 'src="journal.js' in (tmp_path / "saved" / "index.html").read_text()
    assert 'src="journal.js' in (tmp_path / "spot" / "a" / "index.html").read_text()


def test_the_privacy_notice_describes_the_journal():
    notice = (ROOT / "src" / "dipcast" / "api" / "static" / "privacy.html").read_text()
    assert '"Log a swim"' in notice and "IndexedDB" in notice and "Save a copy" in notice
    assert "I swam here today" not in notice
