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


def test_outingpack_js_is_loaded_versioned_and_kept_by_the_offline_copy(tmp_path):
    # outingpack.js keeps a plan's outing for offline use, in a cache of its own beside the offline copy's.
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    html = (tmp_path / "plan" / "index.html").read_text()
    assert f'<script src="outingpack.js?v={stamp}" defer></script>' in html
    assert html.index('src="outing.js') < html.index('src="outingpack.js')
    assert (tmp_path / "outingpack.js").read_bytes() == (bs.TEMPLATE.parent / "outingpack.js").read_bytes()
    sw = (tmp_path / "sw.js").read_text()
    assert "`outingpack.js?v=${BUILD}`" in sw and "const PACK = 'swimsignal-outing'" in sw
    assert "k.startsWith('dipcast-') && k !== CACHE" in sw   # the pack's name is not one the worker deletes
    assert bs.TEMPLATE.parent / "outingpack.js" in bs.SHELL_SOURCES


def test_spotdate_js_comes_before_outing_js_and_organisers_js_and_the_offline_copy_keeps_it(tmp_path):
    # spotdate.js (the calendar file and alerts for a date) is shared by the outing and the organisers' page.
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    html = (tmp_path / "index.html").read_text()
    assert f'<script src="spotdate.js?v={stamp}" defer></script>' in html
    assert html.index('src="spotdate.js') < html.index('src="outing.js')
    assert (tmp_path / "spotdate.js").read_bytes() == (bs.TEMPLATE.parent / "spotdate.js").read_bytes()
    assert "`spotdate.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "spotdate.js" in bs.SHELL_SOURCES
    organisers = (tmp_path / "organisers.html").read_text()
    assert organisers.index('src="spotdate.js?v=') < organisers.index('src="organisers.js?v=')


def test_outingwatch_js_comes_after_since_js_and_the_offline_copy_keeps_it(tmp_path):
    # outingwatch.js (what would change the outing, and what has since it was planned) uses since.js's rules.
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    html = (tmp_path / "index.html").read_text()
    assert f'<script src="outingwatch.js?v={stamp}" defer></script>' in html
    assert html.index('src="since.js') < html.index('src="outingwatch.js')
    assert (tmp_path / "outingwatch.js").read_bytes() == (bs.TEMPLATE.parent / "outingwatch.js").read_bytes()
    assert "`outingwatch.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "outingwatch.js" in bs.SHELL_SOURCES
    # The privacy notice names the note it keeps in this browser.
    privacy = (tmp_path / "privacy.html").read_text()
    assert "So that the outing can say what has changed since you planned it, your browser also keeps a note" in privacy


def test_dayplan_js_is_loaded_versioned_after_outing_js_and_kept_by_the_offline_copy(tmp_path):
    # dayplan.js: the day plan's options and its picture, on Plan a swim; it uses outing.js's words.
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    html = (tmp_path / "plan" / "index.html").read_text()
    assert f'<script src="dayplan.js?v={stamp}" defer></script>' in html
    assert html.index('src="outing.js') < html.index('src="dayplan.js')
    assert (tmp_path / "dayplan.js").read_bytes() == (bs.TEMPLATE.parent / "dayplan.js").read_bytes()
    assert "`dayplan.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "dayplan.js" in bs.SHELL_SOURCES
