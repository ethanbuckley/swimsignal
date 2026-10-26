"""A plan's outing (src/dipcast/site/outing.js): the build copies the script, the page asks for it from
its own build after plan.js, and the offline copy stores it. Its rules are tested in tests/site_outing.test.cjs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_page_loads_outing_js_from_its_build_and_the_offline_copy_keeps_it(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    html = (tmp_path / "index.html").read_text()
    assert f'<script src="outing.js?v={stamp}" defer></script>' in html
    assert html.index('src="plan.js') < html.index('src="outing.js')   # it uses the plan's rules
    assert (tmp_path / "outing.js").read_bytes() == (bs.TEMPLATE.parent / "outing.js").read_bytes()
    assert "`outing.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "outing.js" in bs.SHELL_SOURCES   # a change to it renames the offline cache
