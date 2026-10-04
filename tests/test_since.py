"""Since you last looked (src/dipcast/site/since.js): the build copies the script, the page asks for it
from its own build, and the offline copy stores it. Its rules are tested in tests/site_since.test.cjs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_page_loads_since_js_from_its_build_and_the_offline_copy_keeps_it(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    for page in ("index.html", "saved/index.html"):
        html = (tmp_path / page).read_text()
        assert f'<script src="since.js?v={stamp}"></script>' in html
        assert html.index('src="levels.js') < html.index('src="since.js')   # it uses the level rules
    assert (tmp_path / "since.js").read_bytes() == (bs.TEMPLATE.parent / "since.js").read_bytes()
    assert "`since.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "since.js" in bs.SHELL_SOURCES   # a change to it renames the offline cache
