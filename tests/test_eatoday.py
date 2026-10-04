"""Today's EA advice on a bathing water's page (src/dipcast/site/eatoday.js) is built and stored with the
app, as the other scripts are, and the build itself never asks the EA for it: the reader's browser loads
the EA's own panel when the fold is opened. Its rules are tested in tests/site_eatoday.test.cjs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_page_loads_the_ea_advice_script_from_its_build(tmp_path):
    bs = _build_site()
    spot = {"id": "bw-ukj2310-11945", "name": "Frensham Great Pond", "kind": "lake", "source": "designated", "days": [],
            "classification": {"class": "excellent", "year": 2025,
                               "url": "https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945"}}
    bs.write_pages(tmp_path, [spot], root="https://example.org/")
    stamp = bs.shell_stamp()
    page = (tmp_path / "spot" / "bw-ukj2310-11945" / "index.html").read_text()
    assert f'<script src="eatoday.js?v={stamp}">' in page
    assert (tmp_path / "eatoday.js").read_bytes() == (bs.TEMPLATE.parent / "eatoday.js").read_bytes()
    assert "`eatoday.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "eatoday.js" in bs.SHELL_SOURCES
    # The panel is loaded by the reader's browser, never written into a built page.
    assert "bwq/widget" not in page


def test_the_build_never_asks_for_the_panel():
    # No request is added to the build: only the page's script knows the widget's address.
    for f in [ROOT / "scripts" / "build_site.py", *(ROOT / "src" / "dipcast").rglob("*.py")]:
        assert "bwq/widget" not in f.read_text(), f


def test_the_privacy_notice_names_the_panel_on_a_bathing_waters_page():
    notice = (ROOT / "src" / "dipcast" / "api" / "static" / "privacy.html").read_text()
    para = next(p for p in notice.split("<p>") if "environment.data.gov.uk" in p)
    assert "on a bathing water's page" in para and 'Opening "Today\'s EA advice"' in para
    assert "scripts switched off" in para and "does not tell it which page you were on" in para
