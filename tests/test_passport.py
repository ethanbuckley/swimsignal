"""The swim passport (src/dipcast/site/passport.js): the build copies the script, the page asks for it from its own
build after journal.js, the offline copy stores it, and the privacy notice names what it keeps. Its rules are tested
in tests/site_passport.test.cjs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_page_loads_passport_js_from_its_build_and_the_offline_copy_keeps_it(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    html = (tmp_path / "index.html").read_text()
    assert f'<script src="passport.js?v={stamp}" defer></script>' in html
    assert html.index('src="journal.js') < html.index('src="passport.js')
    assert (tmp_path / "passport.js").read_bytes() == (bs.TEMPLATE.parent / "passport.js").read_bytes()
    assert "`passport.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "passport.js" in bs.SHELL_SOURCES
    privacy = (tmp_path / "privacy.html").read_text()
    assert "The swim passport on the Saved page is worked out from that journal" in privacy
    assert "never a place, a date or your name" in privacy
