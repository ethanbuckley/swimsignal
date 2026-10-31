"""Ask SwimSignal (ask/, the Worker; src/dipcast/site/ask.js, its tile on Plan a swim): off until DIPCAST_ASK_URL
is set; then spots.json says where the Worker is and the privacy notice gains its section. The Worker's own
tests are in ask/test (node --test); the page's in tests/site_ask.test.cjs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_off_unless_the_worker_address_is_set(monkeypatch):
    bs = _build_site()
    monkeypatch.delenv(bs.ASK_URL_ENV, raising=False)
    assert bs.ask_config() is None
    monkeypatch.setenv(bs.ASK_URL_ENV, "https://swimsignal-ask.swimsignal-push.workers.dev/")
    assert bs.ask_config() == {"url": "https://swimsignal-ask.swimsignal-push.workers.dev/"}
    for bad in ("http://example.org/", "https://example.org/ask", "javascript:alert(1)//"):
        monkeypatch.setenv(bs.ASK_URL_ENV, bad)
        assert bs.ask_config() is None


def test_the_page_loads_ask_js_from_its_build_and_the_offline_copy_keeps_it(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    html = (tmp_path / "index.html").read_text()
    assert f'<script src="ask.js?v={stamp}" defer></script>' in html
    assert (tmp_path / "ask.js").read_bytes() == (bs.TEMPLATE.parent / "ask.js").read_bytes()
    assert "`ask.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "ask.js" in bs.SHELL_SOURCES


def test_the_privacy_notice_has_its_section_only_when_on(tmp_path):
    bs = _build_site()
    spots = [{"id": "a", "name": "A", "kind": "river", "days": []}]
    bs.write_pages(tmp_path, spots, root="https://example.org/")
    off = (tmp_path / "privacy.html").read_text()
    assert 'id="ask"' not in off and "Anthropic" not in off
    bs.write_pages(tmp_path, spots, root="https://example.org/", ask=True)
    on = (tmp_path / "privacy.html").read_text()
    assert on.index('<h2 id="ask">Ask SwimSignal</h2>') < on.index("<h2>The server version</h2>")
    assert "SwimSignal does not keep your question or its answer" in on
    assert "keyed hash of your IP address and the day" in on
    assert "(Ask SwimSignal)." in on.split("</p>", 2)[0] + on   # after the notice's date
    assert "Last updated" in on and "Ask SwimSignal)" in on[on.index("Last updated"):on.index("Last updated") + 80]
