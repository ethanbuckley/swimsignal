"""The redesign preview (src/dipcast/site/preview/; scripts/build_site.py, write_preview; docs/DESIGN.md, "A redesign
kept as a preview"): the build publishes its files beside the live pages, out of search engines and linked from none
of them, with one file of its own, each spot's opening photo. What the pages say is tested in
tests/site_preview.test.cjs."""

import json
import sys
from pathlib import Path

import pytest

from dipcast import hero_photos

ROOT = Path(__file__).resolve().parents[1]
PHOTO = {"file": "geograph-1.jpg", "w": 640, "h": 427, "topic": "overview", "status": "historical", "labels": [], "credit": "A Walker",
         "taken": "2021-06-14", "caption": "The river.", "source": "https://www.geograph.org.uk/photo/1",
         "licence": "https://creativecommons.org/licenses/by-sa/2.0/"}
SPOTS = [{"id": "a", "name": "A", "kind": "river", "days": [], "guide": {"photos": [dict(PHOTO, topic="rules"), PHOTO]}},
         {"id": "b", "name": "B", "kind": "river", "days": []}]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_opening_photo_is_chosen_by_the_live_pages_rule():
    assert hero_photos.hero([dict(PHOTO, topic="rules"), PHOTO])["file"] == "geograph-1.jpg"
    for change in ({"status": "confirmed"}, {"labels": [{"x": 1, "y": 2, "text": "Steps"}]}, {"credit": ""}, {"taken": None},
                   {"file": "../secret.jpg"}, {"topic": "entry"}):
        assert hero_photos.hero([dict(PHOTO, **change)]) is None, change
    toml = dict(PHOTO, width=640, height=360)   # guides/<id>.toml names the size in full
    del toml["w"], toml["h"]
    assert (hero_photos.hero([toml])["w"], hero_photos.hero([toml])["h"]) == (640, 360)
    assert hero_photos.hero([PHOTO])["licence_name"] == "CC BY-SA 2.0"
    assert hero_photos.hero([dict(PHOTO, licence="https://example.org/other")])["licence_name"] == ""
    # guide.js states the same rule: if it changes there, change it here.
    js = (ROOT / "src/dipcast/site/guide.js").read_text()
    assert "x.topic === 'overview' && x.status === 'historical' && guideFile(x.file) && !(x.labels || []).length && x.credit && x.taken" in js


def test_the_build_publishes_the_preview_beside_the_live_pages(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/")
    out = tmp_path / "preview"
    assert sorted(p.name for p in out.iterdir()) == ["app.js", "hero-photos.json", "index.html", "model.js", "preview.css"]
    for name in bs.PREVIEW_FILES:   # copied as they are: no stamp, no counter, no tile key
        assert (out / name).read_bytes() == (bs.PREVIEW / name).read_bytes(), name
    assert list(json.loads((out / "hero-photos.json").read_text())) == ["a"]
    page, css, js = ((out / n).read_text() for n in ("index.html", "preview.css", "app.js"))
    assert bs.PREVIEW_NOINDEX in page
    # What it loads from the live site exists where it asks for it.
    for src in ("../levels.js", "../eatoday.js", "../fonts/SourceSans3-latin.woff2", "../fonts/SourceSerif4-latin.woff2", "../icons/icon.svg",
                "../icons/fells.webp", "../icons/fells-wide.webp"):
        assert src in page or src in css, src
        assert (out / src).resolve().is_file(), src
    for asked in ("'../data/spots-lite.json'", "'hero-photos.json'", "'../data/postcodes.json'", "'../data/places.json'", "../guides/photos/"):
        assert asked in js, asked
    assert (tmp_path / "data" / "places.json").is_file() and (tmp_path / "data" / "postcodes.json").is_file()


def test_the_preview_is_in_no_sitemap_and_linked_from_no_live_page(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/")
    assert "preview" not in (tmp_path / "sitemap.xml").read_text()
    for page in sorted(tmp_path.rglob("*.html")):
        if page.is_relative_to(tmp_path / "preview"):
            continue
        text = page.read_text()
        assert 'href="preview/' not in text and 'href="../preview/' not in text and "example.org/preview" not in text, page


def test_the_offline_copy_leaves_the_preview_to_the_browser():
    sw = (ROOT / "src/dipcast/site/sw.js").read_text()
    assert "if (url.pathname.includes('/preview/')) return;" in sw
    assert "preview/" not in sw.split("const SHELL")[1].split("];")[0]   # and stores none of its files


def test_a_preview_page_that_lost_its_noindex_mark_stops_the_build(tmp_path, monkeypatch):
    bs = _build_site()
    src = tmp_path / "preview"
    src.mkdir()
    for name in bs.PREVIEW_FILES:
        (src / name).write_text((bs.PREVIEW / name).read_text().replace(bs.PREVIEW_NOINDEX, ""))
    monkeypatch.setattr(bs, "PREVIEW", src)
    with pytest.raises(ValueError, match="noindex"):
        bs.write_preview(tmp_path / "site", SPOTS)
