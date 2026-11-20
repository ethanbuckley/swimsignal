"""The trial at /next/ (src/dipcast/site/next/; scripts/build_site.py, write_next; docs/DESIGN.md, "A second site at
/next/"): the build publishes its three files beside the live pages, out of search engines and linked from none of
them. What the pages say is tested in tests/site_next.test.cjs."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPOTS = [{"id": "a", "name": "A", "kind": "river", "days": []}]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_build_publishes_the_trial_beside_the_live_pages(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/")
    out = tmp_path / "next"
    assert sorted(p.name for p in out.iterdir()) == ["index.html", "next.css", "next.js"]
    for name in bs.NEXT_FILES:   # copied as they are: no stamp, no counter, no tile key
        assert (out / name).read_bytes() == (bs.NEXT / name).read_bytes(), name
    page = (out / "index.html").read_text()
    assert '<meta name="robots" content="noindex, nofollow">' in page
    # What it loads from the live site exists where it asks for it.
    for src in ("../levels.js", "../eatoday.js", "../fonts/SourceSans3-latin.woff2"):
        assert src in page or src in (out / "next.css").read_text(), src
        assert (out / src).resolve().is_file(), src


def test_the_trial_is_in_no_sitemap_and_linked_from_no_live_page(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/")
    assert "next" not in (tmp_path / "sitemap.xml").read_text()
    for page in sorted(tmp_path.rglob("*.html")):
        if page.is_relative_to(tmp_path / "next"):
            continue
        text = page.read_text()
        assert 'href="next/' not in text and 'href="../next/' not in text and "example.org/next" not in text, page


def test_a_trial_page_that_lost_its_noindex_mark_stops_the_build(tmp_path, monkeypatch):
    bs = _build_site()
    src = tmp_path / "next"
    src.mkdir()
    for name in bs.NEXT_FILES:
        (src / name).write_text((bs.NEXT / name).read_text().replace('<meta name="robots" content="noindex, nofollow">', ""))
    monkeypatch.setattr(bs, "NEXT", src)
    with pytest.raises(ValueError, match="noindex"):
        bs.write_next(tmp_path / "site")
