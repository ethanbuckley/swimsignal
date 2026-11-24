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
    assert sorted(p.name for p in out.iterdir()) == ["alerts.js", "app.js", "hero-photos.json", "index.html", "map.js", "map.json", "model.js",
                                                     "preview.css", "spot"]
    for name in bs.PREVIEW_FILES:   # copied as they are: no stamp, no counter, no tile key
        assert (out / name).read_bytes() == (bs.PREVIEW / name).read_bytes(), name
    assert list(json.loads((out / "hero-photos.json").read_text())) == ["a"]
    page, css, js = ((out / n).read_text() for n in ("index.html", "preview.css", "app.js"))
    assert bs.PREVIEW_NOINDEX in page
    # What it loads from the live site exists where it asks for it.
    # The page asks from the site's root, where its <base> points; its stylesheet asks from where it is, preview/.
    assert '<base href="../">' in page and 'data-home="preview/"' in page
    for src in ("levels.js", "eatoday.js", "experience.js", "lists.js", "plan.js", "fonts/SourceSans3-latin.woff2", "fonts/SourceSerif4-latin.woff2",
                "icons/icon.svg", "preview/preview.css", "preview/app.js", "preview/model.js", "preview/map.js", "preview/alerts.js"):
        assert f'"{src}"' in page, src
        assert (tmp_path / src).is_file(), src
    for src in ("../icons/fells.webp", "../icons/fells-wide.webp", "../fonts/SourceSerif4-latin.woff2"):
        assert src in css and (out / src).resolve().is_file(), src
    for asked in ("'data/spots-lite.json'", "'preview/hero-photos.json'", "'data/postcodes.json'", "'data/places.json'", "guides/photos/"):
        assert asked in js, asked
    assert (tmp_path / "data" / "places.json").is_file() and (tmp_path / "data" / "postcodes.json").is_file()
    # The map library, the worker the alerts arrive through and the pages the views link to are the live site's own.
    for asked in ("vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css", "sw.js", "privacy.html"):
        assert (tmp_path / asked).is_file(), asked
    for asked in ("'vendor/leaflet/leaflet.js'", "'vendor/leaflet/leaflet.css'", "'preview/map.json'"):
        assert asked in (out / "map.js").read_text(), asked
    tiles = json.loads((out / "map.json").read_text())   # no provider chosen: OpenStreetMap's, in index.html's own colours
    assert tiles["url"] == bs.TILE_PROVIDERS["osm"]["url"] and tiles["credit"] == bs.OSM_ATTRIBUTION
    assert tiles["filter"].startswith('<filter id="tiles"') and tiles["filter"] in bs.TEMPLATE.read_text()


def test_the_previews_maps_take_the_live_maps_tile_provider(tmp_path):
    bs = _build_site()
    tiles = {**bs.TILE_PROVIDERS["carto-voyager"], "id": "carto-voyager",
             "url": bs.TILE_PROVIDERS["carto-voyager"]["url"].replace("__KEY__", "abcdefgh12345678")}
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/", tiles=tiles)
    got = json.loads((tmp_path / "preview" / "map.json").read_text())
    assert got == {"url": tiles["url"], "credit": tiles["credit"], "filter": bs.CARTO_FILTERS["voyager"]}
    assert tiles["url"] in (tmp_path / "app.js").read_text()   # the same address the live map draws from (the page's script)
    # A provider with no filter of its own keeps the one index.html carries, as the live map does.
    plain = bs.preview_map({**bs.TILE_PROVIDERS["thunderforest-atlas"]})
    assert plain["filter"].startswith('<filter id="tiles"')


def test_the_preview_is_in_no_sitemap_and_linked_from_no_live_page(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/")
    assert "preview" not in (tmp_path / "sitemap.xml").read_text()
    for page in sorted(tmp_path.rglob("*.html")):
        if page.is_relative_to(tmp_path / "preview"):
            continue
        text = page.read_text()
        assert 'href="preview/' not in text and 'href="../preview/' not in text and "example.org/preview" not in text, page


def test_the_offline_copy_keeps_a_preview_page_once_opened_and_stores_none_at_install():
    """What the worker does with them is tested where it runs (tests/site_cache.test.cjs). Here: it no longer leaves
    preview/ to the browser, the preview has its own stand-in page, and no visitor stores its files at install."""
    sw = (ROOT / "src/dipcast/site/sw.js").read_text()
    assert "if (url.pathname.includes('/preview/')) return;" not in sw
    assert "const root = inPreview(req.url) ? PREVIEW_ROOT() : self.registration.scope;" in sw
    assert "preview/" not in sw.split("const SHELL")[1].split("];")[0]


RISK = {"low": 0.05, "moderate": 0.2, "high": 0.5}
DAYS = ["2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27", "2026-11-28"]


def _forecast_spot(**extra):
    """A spot as data/spots-lite.json holds one, with five days: enough for the page's script to draw its answer."""
    labels = ["moderate", "moderate", "low", "high", "moderate"]
    return {"id": "a", "name": "River Aire, Somewhere", "kind": "river", "river": "River Aire", "area": "Yorkshire", "source": "curated",
            "lat": 53.9, "lon": -1.8, "upstream_summary": {"overflows": 10}, "location": {"mode": "river"},
            "assumptions": {"max_upstream_km": 60, "recent_spill_hours": 48}, "detail_file": "spot/a.json",
            "now": {"label": "low", "risk": 0.02, "discharging_upstream": 0, "recent_upstream": 0, "monitored_upstream": 8},
            "days": [{"date": d, "label": lab, "risk": RISK[lab], "rain_48h_mm": 4, "expected_spilling_overflows": 0.2,
                      "in_validated_season": False} for d, lab in zip(DAYS, labels)],
            "weather": {"days": [{"date": d, "tmax": 7, "sunrise": "07:43", "sunset": "16:01", "wind_kmh": 15, "gust_kmh": 33} for d in DAYS]},
            **extra}


def test_each_place_has_a_page_of_its_own_with_its_head_and_a_base(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/", spot_cards={"a": "River A: low risk today"}, cards_v="202611241321")
    out = tmp_path / "preview"
    assert sorted(p.name for p in (out / "spot").iterdir()) == ["a", "b"]
    page = (out / "spot" / "a" / "index.html").read_text()
    head = page.split("</head>")[0]
    # The <base> is the site's root from there, before every relative address, so each means what it means on the opening.
    assert head.index('<base href="../../../">') < head.index('href="fonts/') < head.index('href="preview/preview.css"')
    assert head.count("<base ") == 1 and 'data-home="preview/"' in page
    assert f"<title>{bs.spot_title(SPOTS[0])}</title>" in head and "SwimSignal preview" not in head   # the live page's own title
    assert '<link rel="canonical" href="https://example.org/preview/spot/a/">' in head
    assert '<meta property="og:image" content="https://example.org/cards/spot/a.png?v=202611241321">' in head
    assert '<meta property="og:image:alt" content="River A: low risk today">' in head
    assert bs.PREVIEW_NOINDEX in head and "application/ld+json" not in page   # a preview: out of search engines
    assert (tmp_path / "spot" / "a" / "index.html").is_file()   # the live page is still the place's page
    assert 'href="https://example.org/preview/' not in (tmp_path / "sitemap.xml").read_text()
    # No forecast was written here, so nothing is built in: the pages keep their loading line.
    assert "data-built" not in page and "Reading the forecast" in page
    assert (out / "index.html").read_bytes() == (bs.PREVIEW / "index.html").read_bytes()


def test_a_place_page_as_the_sites_own_would_be_indexed_at_the_sites_address():
    """The form a swap of the home page would publish. The build does not ask for it."""
    bs = _build_site()
    shell = (bs.PREVIEW / "index.html").read_text()
    page = bs.preview_place_page(shell, _forecast_spot(), "https://example.org/", live=True)
    assert '<link rel="canonical" href="https://example.org/spot/a/">' in page
    assert "noindex" not in page and "SwimSignal preview" not in page and "A redesign kept beside" not in page and "one\n     folder down" not in page
    assert '"@type":"Place"' in page and '"@id":"https://example.org/spot/a/#place"' in page
    assert '<base href="../../">' in page and '<html lang="en-GB" data-home="">' in page and page.count("<base ") == 1
    assert '<link rel="manifest" href="manifest.webmanifest">' in page   # the Home Screen app opens these pages
    assert "noindex" in bs.preview_place_page(shell, _forecast_spot(), "https://example.org/")


def test_the_built_pages_hold_what_the_script_would_draw(tmp_path):
    import shutil
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    bs = _build_site()
    spot = _forecast_spot()
    (tmp_path / "data" / "spot").mkdir(parents=True)
    (tmp_path / "data" / "spots-lite.json").write_text(json.dumps({"generated_at": "2026-11-24T13:21:00+00:00", "spots": [spot]}))
    (tmp_path / "data" / "spots.json").write_text(json.dumps({"generated_at": "2026-11-24T13:21:00+00:00", "spots": [spot]}))
    (tmp_path / "data" / "spot" / "a.json").write_text(json.dumps({"id": "a", "contributors": []}))
    bs.write_preview(tmp_path, [spot], root="https://example.org/")
    place = (tmp_path / "preview" / "spot" / "a" / "index.html").read_text()
    assert '<div id="app" data-built>' in place
    assert '<h1 id="title" tabindex="-1">River Aire, Somewhere</h1>' in place
    assert "Moderate risk from sewage spills" in place and "Issued 13:21 ·" in place and " ago" not in place.split('<div id="app"')[1].split("<script")[0]
    # A reader without scripts is told when the forecast was issued, and is not told the page needs JavaScript.
    assert "<p class=\"notice\">This forecast was issued on Tuesday 24 November 2026 at 13:21 UK time." in place
    assert "With JavaScript on, the page updates it and shows the other days, the map and your saved places.</p></noscript>" in place
    assert "the overflows upstream and the rest of the detail" not in place   # they are in this page's HTML
    assert "<noscript><style>button,.picks{display:none!important}</style>" in place   # nothing to press that would do nothing
    assert "This preview needs JavaScript" not in place
    assert place.count('<main id="main"') == 1 and place.count('<p id="said"') == 1
    home = (tmp_path / "preview" / "index.html").read_text()
    assert '<div id="app" data-built>' in home and "Where do you swim?" in home and "Yorkshire" in home
    # The opening's search and lists are the script's: without it, the reader is sent to the list of every spot.
    assert 'This page needs JavaScript to search for a place' in home and '<a href="spots.html">Every spot</a>' in home
    assert bs.PREVIEW_NOINDEX in home and bs.PREVIEW_NOINDEX in place
    for tag in ('<script src="levels.js"></script>', '<script src="preview/app.js"></script>'):
        assert tag in place and tag in home
    assert 'href="preview/spot/a/?day=2026-11-28"' in place   # its links, from the site's root


def test_a_preview_page_that_lost_its_noindex_mark_stops_the_build(tmp_path, monkeypatch):
    bs = _build_site()
    src = tmp_path / "preview"
    src.mkdir()
    for name in bs.PREVIEW_FILES:
        (src / name).write_text((bs.PREVIEW / name).read_text().replace(bs.PREVIEW_NOINDEX, ""))
    monkeypatch.setattr(bs, "PREVIEW", src)
    with pytest.raises(ValueError, match="noindex"):
        bs.write_preview(tmp_path / "site", SPOTS)


def test_a_preview_page_that_lost_the_live_sites_rules_stops_the_build(tmp_path, monkeypatch):
    bs = _build_site()
    src = tmp_path / "preview"
    src.mkdir()
    for name in bs.PREVIEW_FILES:
        (src / name).write_text((bs.PREVIEW / name).read_text().replace('<script src="lists.js"></script>', ""))
    monkeypatch.setattr(bs, "PREVIEW", src)
    with pytest.raises(ValueError, match="lists.js"):
        bs.write_preview(tmp_path / "site", SPOTS)


# ------------------------------------------------------------------------------------------------ the switch
def _site(tmp_path, monkeypatch, on):
    bs = _build_site()
    if on:
        monkeypatch.setenv(bs.REDESIGN_ENV, "1")
    else:
        monkeypatch.delenv(bs.REDESIGN_ENV, raising=False)
    out = tmp_path / ("on" if on else "off")
    out.mkdir()
    bs.write_pages(out, SPOTS, root="https://example.org/", spot_cards={"a": "River A: low risk today"}, cards_v="1")
    return bs, out


def test_the_switch_is_one_value_and_anything_else_is_off(monkeypatch):
    bs = _build_site()
    for value, on in (("1", True), (" 1 ", True), ("", False), ("0", False), ("true", False), ("yes", False)):
        monkeypatch.setenv(bs.REDESIGN_ENV, value)
        assert bs.redesign_on() is on, value
    monkeypatch.delenv(bs.REDESIGN_ENV)
    assert bs.redesign_on() is False
    assert "DIPCAST_REDESIGN: ${{ vars.DIPCAST_REDESIGN }}" in (ROOT / ".github/workflows/site.yml").read_text()


def test_switched_off_the_app_has_the_sites_addresses_and_there_is_no_classic(tmp_path, monkeypatch):
    bs, site = _site(tmp_path, monkeypatch, False)
    assert not (site / "classic").exists()
    for page in ("index.html", "spot/a/index.html", "plan/index.html", "saved/index.html"):
        text = (site / page).read_text()
        assert '<html lang="en">' in text and "data-home" not in text.split("</head>")[0] and "classic" not in text.split("<script")[0], page
    assert (site / "preview" / "spot" / "a" / "index.html").is_file()


def test_switched_on_the_redesign_has_the_sites_addresses_and_the_app_is_under_classic(tmp_path, monkeypatch):
    bs, site = _site(tmp_path, monkeypatch, True)
    home = (site / "index.html").read_text()
    place = (site / "spot" / "a" / "index.html").read_text()
    for name, page, base in (("home", home, "./"), ("place", place, "../../"), ("plan", (site / "plan" / "index.html").read_text(), "../"),
                             ("saved", (site / "saved" / "index.html").read_text(), "../")):
        head = page.split("</head>")[0]
        assert '<html lang="en-GB" data-home="">' in page and head.count("<base ") == 1 and f'<base href="{base}">' in head, name
        assert '<script src="preview/app.js"></script>' in page and '<link rel="manifest" href="manifest.webmanifest">' in head, name
        assert "SwimSignal preview" not in page and "This preview" not in page, name
        assert ("noindex" in head) is (name == "saved"), name   # Saved is this browser's own list, as the app's page is
    assert f"<title>{bs.HOME_TITLE}</title>" in home and '<link rel="canonical" href="https://example.org/">' in home
    assert '<link rel="canonical" href="https://example.org/spot/a/">' in place and '"@type":"Place"' in place
    assert '<meta property="og:image" content="https://example.org/cards/spot/a.png?v=1">' in place
    assert '<link rel="canonical" href="https://example.org/plan/">' in (site / "plan" / "index.html").read_text()
    # The same addresses are in the sitemap as before, and the place still has its sign beside its page.
    assert "<loc>https://example.org/spot/a/</loc>" in (site / "sitemap.xml").read_text()
    assert (site / "spot" / "a" / "sign" / "index.html").is_file()
    # The app, whole, one folder down: its files asked for from the site's root, its own pages under classic/.
    for page, base in (("index.html", "../"), ("spot/a/index.html", "../../../"), ("plan/index.html", "../../"), ("saved/index.html", "../../")):
        text = (site / "classic" / page).read_text()
        head = text.split("</head>")[0]
        assert f'<base href="{base}">' in head and head.count("<base ") == 1, page
        assert '<html lang="en" data-home="classic/">' in text and '<meta name="robots" content="noindex">' in head, page
        assert "This is the earlier version of SwimSignal" in text and 'href="classic/plan/"' in text and 'href="classic/saved/"' in text, page
        assert 'href="plan/"' not in text and 'href="saved/"' not in text and 'href="./" id="nav-list"' not in text, page
    assert '<link rel="canonical" href="https://example.org/spot/a/">' in (site / "classic" / "spot" / "a" / "index.html").read_text()
    # An address kept from the preview opens the same page at the site's own address; its files stay where they were.
    moved = (site / "preview" / "index.html").read_text()
    assert 'location.replace("../"' in moved and "noindex" in moved
    assert not (site / "preview" / "spot").exists() and (site / "preview" / "app.js").is_file()
    # Switched off again, the next build is as it was: nothing of classic/ is left.
    monkeypatch.delenv(bs.REDESIGN_ENV)
    bs.write_pages(site, SPOTS, root="https://example.org/")
    assert not (site / "classic").exists() and '<html lang="en">' in (site / "index.html").read_text()


def test_the_app_makes_its_own_addresses_from_one_root_and_asks_the_site_from_another():
    """index.html: ROOT is where the app's pages are (the site's root, or classic/), SITE_ROOT where the site's
    files are. The worker, the printable list, the record page and a kept outing's files are the site's."""
    app = (ROOT / "src/dipcast/site/index.html").read_text()
    assert "const ROOT = new URL(document.documentElement.dataset.home || './', SITE_ROOT);" in app
    for line in ("navigator.serviceWorker.register(new URL('sw.js', SITE_ROOT))", "new URL('sites.html', SITE_ROOT).href",
                 "${esc(SITE_ROOT.pathname)}record.html#spot="):
        assert line in app, line
    assert "new URL('sw.js', ROOT)" not in app
    assert "fetch(new URL(p, SITE_ROOT).href" in (ROOT / "src/dipcast/site/outingpack.js").read_text()
