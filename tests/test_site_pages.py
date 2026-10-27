"""The static site's pages: every spot gets a page of its own whose share preview carries its
name (today's level only on its picture, beside when the forecast was issued, since a cached preview
is shown for days), every page carries
absolute preview links, a spot's page has a relative <base>, and the live scorer reports when the
observation records its coverage rule needs begin."""

import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


SPOTS = [
    {"id": "wharfe-ilkley", "name": 'Wharfe at "Cromwheel" & Ilkley', "kind": "river",
     "upstream_summary": {"overflows": 15}, "days": [{"label": "very high"}]},
    {"id": "tarn", "name": "A Tarn", "kind": "lake", "days": [],
     "error": "An isolated lake with no river connection in the network: storm overflows cannot reach it by water."},
    {"id": "Bad Id", "name": "Odd", "kind": "river", "upstream_summary": {"overflows": 0}, "days": []},   # a space
]


def test_every_spot_gets_its_own_page_and_preview(tmp_path):
    bs = _build_site()
    assert bs.write_pages(tmp_path, SPOTS, root="https://example.org/swim/", day="2026-09-29") == 2
    assert not (tmp_path / "spot" / "Bad Id").exists()   # keeps ?spot= instead
    page = (tmp_path / "spot" / "wharfe-ilkley" / "index.html").read_text()
    head = page.split("</head>")[0]
    assert '<base href="../../">' in head   # relative: the site works at any address
    assert '<link rel="canonical" href="https://example.org/swim/spot/wharfe-ilkley/">' in head
    assert '<meta property="og:image" content="https://example.org/swim/icons/og.png">' in head
    assert "<title>Wharfe at &quot;Cromwheel&quot; &amp; Ilkley: pollution risk forecast · SwimSignal</title>" in head
    assert "from the 15 monitored storm overflows upstream" in head
    assert "very high" not in head.lower().replace("veryhigh", "")
    assert head.count("<title>") == 1 and "page-meta" not in page
    assert '<h2 class="spot-name">Wharfe at &quot;Cromwheel&quot; &amp; Ilkley</h2>' in page   # before the script runs
    assert "no monitored storm overflow found upstream of this lake" in (tmp_path / "spot" / "tarn" / "index.html").read_text()
    home = (tmp_path / "index.html").read_text()
    assert '<link rel="canonical" href="https://example.org/swim/">' in home
    assert '<base href="./">' in home.split("</head>")[0]   # pushState to spot/<id>/ must not move its links
    assert "Loading forecasts…" in home
    for f in ["sw.js", "manifest.webmanifest", "icons/og.png", "icons/fells.webp", "verification.html", "methods.html", "privacy.html", "page.css", ".nojekyll", "404.html", "robots.txt",
              "fonts/SourceSans3-latin.woff2", "fonts/SourceSerif4-latin.woff2", "fonts/LICENSE.txt"]:   # the typefaces page.css declares
        assert (tmp_path / f).exists(), f
    # GitHub Pages serves 404.html at any depth, so its links must be absolute; search engines may not keep it.
    lost = (tmp_path / "404.html").read_text()
    assert 'href="https://example.org/swim/"' in lost and 'href="https://example.org/swim/page.css"' in lost and 'content="noindex"' in lost
    assert 'class="top"' in lost and 'href="https://example.org/swim/about.html">About</a>' in lost   # the shared header, absolute
    assert 'href="https://example.org/swim/icons/apple-touch-icon.png"' in lost
    assert (tmp_path / "robots.txt").read_text() == "User-agent: *\nAllow: /\nSitemap: https://example.org/swim/sitemap.xml\n"
    sm = (tmp_path / "sitemap.xml").read_text()
    assert sm.count("<url>") == 18 and "<loc>https://example.org/swim/spot/tarn/</loc>" in sm   # with sites.html, record.html, clubs.html, quality.html, spots.html and two profiles
    assert (tmp_path / "quality.html").exists()   # without an overflow table its lists say so (tests/test_quality.py)
    assert "<loc>https://example.org/swim/methods.html</loc>" in sm
    assert "<loc>https://example.org/swim/coverage.html</loc>" in sm
    assert "<loc>https://example.org/swim/data.html</loc>" in sm and (tmp_path / "data.html").exists()
    assert "<loc>https://example.org/swim/about.html</loc>" in sm and "<loc>https://example.org/swim/testing.html</loc>" in sm
    # The testers' briefing: linked from About and the feedback page, with flat links of its own.
    testing = (tmp_path / "testing.html").read_text()
    assert 'href="feedback.html"' in testing and 'href="/feedback"' not in testing and 'href="privacy.html"' in testing
    assert 'href="testing.html"' in (tmp_path / "about.html").read_text() and 'href="testing.html"' in (tmp_path / "feedback.html").read_text()
    assert "<lastmod>2026-09-29</lastmod>" in sm
    # The Saved page: its list is in the browser, so nothing in it for a search engine.
    saved = (tmp_path / "saved" / "index.html").read_text()
    head = saved.split("</head>")[0]
    assert '<base href="../">' in head and '<meta name="robots" content="noindex">' in head
    assert '<link rel="canonical" href="https://example.org/swim/saved/">' in head and "<title>Saved spots · SwimSignal</title>" in head
    assert "saved/" not in sm and "noindex" not in home
    # Plan a swim: one page for every plan (the plan is after the #), so it is in the sitemap; the
    # places it starts from are this site's own file.
    plan = (tmp_path / "plan" / "index.html").read_text()
    head = plan.split("</head>")[0]
    assert '<base href="../">' in head and "noindex" not in head and "<title>Plan a swim · SwimSignal</title>" in head
    assert '<link rel="canonical" href="https://example.org/swim/plan/">' in head and "<loc>https://example.org/swim/plan/</loc>" in sm
    assert '<h1 class="page-h">Plan a swim</h1>' in plan
    # Without JavaScript, both say what they need and point to every spot's page, not "Loading…" for ever.
    for page, needs in [(saved, "to show your saved spots"), (plan, "to read the forecasts")]:
        body = page.split("</head>")[1]
        note = re.search(r"<noscript>(.*?)</noscript>", body.split('<div id="result">')[1]).group(1)
        assert f'<p class="notice">This page needs JavaScript {needs}' in note and '<a href="spots.html">Every spot</a>' in note
        assert "<style>#result [data-wait]{display:none}</style>" in note and "data-wait>Loading" in body
    assert (tmp_path / "spots.html").exists()
    places = json.loads((tmp_path / "data" / "places.json").read_text())
    assert places["credit"].startswith("Contains OS data") and len(places["places"]) > 20000
    assert ["Kendal", 54.33, -2.75] in places["places"]
    # The rivers and lakes the search finds on the map, likewise the site's own file (scripts/make_waters.py).
    waters = json.loads((tmp_path / "data" / "waters.json").read_text())
    assert waters["credit"].startswith("Contains OS data") and len(waters["waters"]) > 5000
    assert any(w[0] == "River Kennet" and w[2] == "river" for w in waters["waters"])
    assert any(w[0] == "Ullswater" and w[2] == "lake" for w in waters["waters"])
    assert not any("Canal" in w[0] for w in waters["waters"])


def test_the_built_pages_open_on_the_views_opening_as_the_script_draws_it(tmp_path):
    """The home page and a spot's page carry their opening under the sky (.lead, .answer) before the
    script runs, so the picture paints without waiting for the forecast; the home page's words are
    the list's own, word for word, and stop before anything that depends on the forecast."""
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/")
    home = (tmp_path / "index.html").read_text()
    # data-built: the script updates this opening where it stands (index.html, overBuilt), so its
    # picture is painted once, at the first paint, and that paint is the page's largest (LCP).
    body = home.split('<div id="result" data-built data-nosnippet>', 1)[1].split('<p class="about-line"', 1)[0]
    assert body.startswith('<div class="lead"><section class="intro"><h1>Check the water before you go</h1>')
    assert "Five-day pollution risk forecasts for 3 swim spots in England<span class=\"lede-map\">, and for any river or lake you " in body and 'aria-busy="true"' in body
    assert "best-day" not in body and "data-notices" not in body   # these wait for the forecast
    page = (ROOT / "src" / "dipcast" / "site" / "index.html").read_text()
    lead = page.split("function renderList()", 1)[1].split("h += notices()", 1)[0]
    for part in ['<h1>Check the water before you go</h1>', "Five-day pollution risk forecasts for ${DATA.spots.length} swim spots in England<span class=\"lede-map\">, and for any river or lake you ",
                 " on the map</span>. <a href=\"#about\">How it works</a></p>",
                 'placeholder="River, lake or town" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search"',
                 '<label class="sr" for="listday">When are you swimming?</label><select id="listday"><option value="">Today and tomorrow</option>',
                 '<button type="button" class="chip-btn low" data-low aria-pressed="']:
        assert part in lead and part.split("${")[0] in body, part
    # Near me under the search, the script's own markup; the row of controls is the last thing built in,
    # and the line for groups is at the foot of the list since 14 Oct 2026, not in the opening.
    assert f"const NEAR_CTA = '{bs.NEAR_CTA}';" in page and "(offerNear() ? NEAR_CTA" in lead and bs.NEAR_CTA in body
    assert body.index(bs.NEAR_CTA) < body.index('<div class="toolbar">') < body.index('aria-busy="true"')
    # Under it, the forecast for the water where you are (hereForecast), likewise word for word.
    assert f"const HERE_CTA = '{bs.HERE_CTA}';" in page and "'geolocation' in navigator ? HERE_CTA" in lead
    assert body.index(bs.NEAR_CTA) < body.index(bs.HERE_CTA) < body.index('<div class="toolbar">')
    assert lead.index('<div class="toolbar">') < lead.index('<div id="answer-lines">')   # the answer and best-day lines (answerLines)
    assert "Tools for clubs, centres and events" not in body and "planner-note groups" not in page
    assert f"const SEARCH_ICON = '{bs.SEARCH_ICON}';" in page and "const lowLabel = () => 'Low\\u00a0risk only';" in page
    assert "<span data-low-t>Low\u00a0risk only</span>" in body
    spot = (tmp_path / "spot" / "wharfe-ilkley" / "index.html").read_text()
    assert '<section class="answer"><h2 class="spot-name">Wharfe at &quot;Cromwheel&quot; &amp; Ilkley</h2>' in spot
    # Under the opening, the script's two columns (cols): the list's shape, then the map's empty tile,
    # which a wide desktop shows beside it (20 Oct 2026). The script's view uses the same frame.
    assert body.index('</div><div class="cols"><div class="col-list">') < body.index('aria-busy="true"') < body.index('<div class="col-map"><div class="tile map-tile">')
    # The list's own call has no class, so its frame is the built one; Saved adds 'wide-list' (20 Oct 2026).
    assert "const cols = (h, cls = '') => `<div class=\"cols${cls ? ' ' + cls : ''}\"><div class=\"col-list\">${h}</div>${MAP_TILE}</div>`;" in page
    assert 'const MAP_TILE = `<div class="col-map"><section class="tile map-tile"' in page and "setPanel(h + cols(v));" in page
    # Each screen preloads the sky it draws: the wide one from 1,100 px on the app's views.
    assert bs.SKY_PRELOAD in page and bs.SKY_PRELOAD in home


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_a_spots_page_carries_its_answer_and_five_days_as_the_script_draws_them(tmp_path):
    """With this build's spots.json, a spot's page carries its level, headline and five days in the
    page's own markup (scripts/prerender_spots.js runs index.html's spotTop and daysTile), and the
    view the script will draw, so nothing moves when it does (docs/REVIEW-2026-10-16.md, F4)."""
    bs = _build_site()
    (tmp_path / "data").mkdir()
    days = [{"date": f"2026-09-{29 + i}" if i < 2 else f"2026-10-0{i - 1}", "risk": 0.01, "label": "low"} for i in range(5)]
    river = {"id": "a", "name": "A river", "kind": "river", "source": "curated", "upstream_summary": {"overflows": 3},
             "location": {"mode": "river"}, "now": {"label": "low", "discharging_upstream": 0}, "contributors": [], "days": days}
    (tmp_path / "data" / "spots.json").write_text(json.dumps({"generated_at": "2026-09-29T08:00:00+01:00", "spots": [river, SPOTS[1]]}))
    bs.write_pages(tmp_path, [river, SPOTS[1]], root="https://example.org/swim/")
    page = (tmp_path / "spot" / "a" / "index.html").read_text()
    assert '<body class="view-spot">' in page and '<div id="result" data-built data-nosnippet>' in page
    # A spot's page spans the screen from 801 px, so it preloads the wide sky from there.
    assert bs.SPOT_SKY_PRELOAD in page and bs.SKY_PRELOAD not in page and 'fells-wide.webp" as="image" fetchpriority="high" media="(min-width: 801px)"' in page
    assert '<h1 class="spot-name" tabindex="-1">A river</h1>' in page
    assert '<h2 class="big low" id="risk-headline">Low risk from sewage spills</h2>' in page
    assert '<p class="act">Usual care: cover cuts' in page
    assert page.count('<button class="drow low" type="button" data-day=') == 5 and '<span class="d">Today</span>' in page
    assert '<a href="/swim/" class="back" id="back">All spots</a>' in page   # the script's own back link
    # Issued when, without how long ago, which would be wrong by the time the page is read.
    assert '<p class="issued">Issued Tue 08:00</p>' in page
    # Above the answer, for a reader without scripts: the day and time "Today" and "right now" mean.
    note = "This forecast was issued on Tuesday 29 September 2026 at 08:00 UK time. On this copy, \u201cToday\u201d and " \
           "\u201cright now\u201d mean then, and the levels may have changed since. With JavaScript on, the page updates it " \
           "and adds the map, the overflows upstream and the rest of the detail."
    assert f'<div id="result" data-built data-nosnippet><noscript><p class="muted">{note}</p></noscript>' in page
    assert page.index("<noscript>") < page.index('id="risk-hero"') < page.index('<span class="d">Today</span>')
    # A spot without a forecast: its answer, no five days.
    tarn = (tmp_path / "spot" / "tarn" / "index.html").read_text().split('<div id="result"', 1)[1].split('<p class="about-line"', 1)[0]
    assert 'id="risk-headline">No monitored overflow found upstream</h2>' in tarn and 'id="days-h"' not in tarn
    # The page's script draws over the build's copy without the rise it gives a new view, keeping the
    # answer's element (overBuilt, tests/site_built_opening.test.cjs).
    script = (ROOT / "src" / "dipcast" / "site" / "index.html").read_text()
    assert "if (box.hasAttribute('data-built')) { box.removeAttribute('data-built'); overBuilt(box, h); settleMap(); return; }" in script and "let h = spotTop(d);" in script and "${daysTile(d)}" in script
    # Without the file (or Node), the name-only opening, as before.
    (tmp_path / "data" / "spots.json").unlink()
    bs.write_pages(tmp_path, [river, SPOTS[1]], root="https://example.org/swim/")
    page = (tmp_path / "spot" / "a" / "index.html").read_text()
    assert '<body class="view-list">' in page and '<div id="result" data-built data-nosnippet>' not in page and '<h2 class="spot-name">A river</h2>' in page
    assert '<div id="result" data-nosnippet>' in page   # a level drawn here later is not quoted in search results either


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_accuracy_page_carries_its_figures_and_draws_them_again_only_from_newer_scores(tmp_path):
    """verification.html carries what its script draws from this build's verification.json
    (scripts/prerender_verification.js), and says when those scores were made, so the script does
    not move the page by drawing the same figures again (docs/REVIEW-2026-10-16.md, F3)."""
    bs = _build_site()
    (tmp_path / "data").mkdir()
    table = {"warn_at": 0.4, "level": "high", "n": 23395, "hits": 152, "misses": 573, "false_alarms": 211, "quiet_correct": 22459,
             "hit_rate": 152 / 725, "warnings_true": 152 / 363, "share_correct": 22611 / 23395, "always_no_correct": 22670 / 23395,
             "base_rate": 725 / 23395, "warning_lift": (152 / 363) / (725 / 23395), "n_overflow_days": 4695, "n_spill_overflow_days": 145,
             "n_days": 5, "first_day": "2026-09-29", "last_day": "2026-10-03", "by_lead": []}
    ver = {"live": {"generated_at": "2026-10-04T00:15:52+01:00", "n_scored": 0, "warning_table": table}}
    (tmp_path / "data" / "verification.json").write_text(json.dumps(ver))
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/swim/")
    page = (tmp_path / "verification.html").read_text()
    assert '<main class="doc" data-built="2026-10-04T00:15:52+01:00">' in page
    assert "the spill forecast warned of 21% of spills." in page and "Loading the scores…" not in page
    assert '<dl class="stats">' in page and '<h2 id="short-h">In short</h2>' in page   # the figure tiles and the list
    assert 'href="/' not in page.split("<script>")[0]   # the links in the figures are the static site's too
    script = (ROOT / "src" / "dipcast" / "pages" / "verification.html").read_text()
    assert "if (built && !(fresh > built)) return;" in script
    # Without the file, the page as it is, which its script fills.
    (tmp_path / "data" / "verification.json").unlink()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/swim/")
    page = (tmp_path / "verification.html").read_text()
    assert '<main class="doc">' in page and "Loading the scores…" in page


def test_a_spot_with_a_share_card_previews_it_and_the_rest_keep_the_shared_picture(tmp_path):
    """og:image is the spot's own card (cards/spot/<id>.png, src/dipcast/cards.py) with this build's
    stamp, so a preview fetched again gets the new one; its alt gives the issue time beside the level.
    The words under the preview (description) still carry no level."""
    bs = _build_site()
    alt = "Wharfe: Very high risk right now: sewage spills. Forecast issued Fri 16 Oct, 21:03."
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/swim/", spot_cards={"wharfe-ilkley": alt}, cards_v="202610162103")
    head = (tmp_path / "spot" / "wharfe-ilkley" / "index.html").read_text().split("</head>")[0]
    assert '<meta property="og:image" content="https://example.org/swim/cards/spot/wharfe-ilkley.png?v=202610162103">' in head
    assert f'<meta property="og:image:alt" content="{alt}">' in head and '<meta property="og:image:width" content="1200">' in head
    assert "very high" not in re.search(r'<meta name="description" content="([^"]*)"', head)[1].lower()
    for page in ["spot/tarn/index.html", "index.html", "plan/index.html"]:
        assert '<meta property="og:image" content="https://example.org/swim/icons/og.png">' in (tmp_path / page).read_text(), page


PROSE_PAGES = ["organisers.html", "verification.html", "spots.html", "about.html", "methods.html", "clubs.html", "coverage.html",
               "privacy.html", "terms.html", "testing.html", "feedback.html", "data.html", "sites.html", "record.html",
               "quality.html", "support.html"]


def test_every_prose_page_has_its_own_share_preview(tmp_path):
    """A link to a prose page in a post gets the page's own title and description, its address and the
    shared picture, from one block like the app's (page_meta), with its canonical link at the same address."""
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/swim/", support="https://ko-fi.com/example")
    for name in PROSE_PAGES:
        head = (tmp_path / name).read_text().split("</head>")[0]
        title = re.search(r"<title>([^<]+)</title>", head)[1]
        description = re.search(r'<meta name="description" content="([^"]+)">', head)[1]
        url = f"https://example.org/swim/{name}"
        assert head.count("<title>") == 1 and head.count('name="description"') == 1, name
        assert f'<meta property="og:title" content="{title}">' in head, name
        assert f'<meta property="og:description" content="{description}">' in head, name
        assert f'<meta property="og:url" content="{url}">' in head and f'<link rel="canonical" href="{url}">' in head, name
        assert '<meta property="og:image" content="https://example.org/swim/icons/og.png">' in head, name
        assert '<meta property="og:image:width" content="1200">' in head and '<meta property="og:image:height" content="630">' in head, name
        assert '<meta property="og:type" content="website">' in head and '<meta name="twitter:card" content="summary_large_image">' in head, name
        assert "<base" not in head and "{{" not in head, name
        assert "safe" not in description.lower().replace("unsafe", ""), name
    assert "Event organisers · SwimSignal" in (tmp_path / "organisers.html").read_text().split("</head>")[0]
    with pytest.raises(ValueError, match="no canonical link or share tags"):
        bs.with_share_meta((tmp_path / "about.html").read_text(), "about.html", "https://example.org/swim/")   # never twice


def test_the_build_draws_the_share_cards_from_this_runs_levels(tmp_path):
    bs = _build_site()
    (tmp_path / "data").mkdir()
    gen = "2026-10-16T21:03:00+01:00"
    (tmp_path / "data" / "alerts.json").write_text(json.dumps({"generated_at": gen, "spots": {"wharfe-ilkley": {"level": "low", "headline": "Low risk"}}}))
    assert list(bs.write_spot_cards(tmp_path, SPOTS, gen)) == ["wharfe-ilkley"] and (tmp_path / "cards" / "spot" / "wharfe-ilkley.png").exists()
    assert bs.write_spot_cards(tmp_path, SPOTS, gen, alerts_ok=False) == {}   # this run's alerts.json failed: none, never an old level
    assert bs.write_spot_cards(tmp_path, None, gen) == {}   # nonsense in: nothing, no exception


def test_about_page_counts_this_builds_spots_and_links_work_on_the_static_site(tmp_path):
    bs = _build_site()
    spots = [{**SPOTS[0], "source": "designated"}, {**SPOTS[1], "source": "curated"}]
    bs.write_pages(tmp_path, spots, root="https://example.org/")
    about = (tmp_path / "about.html").read_text()
    assert '<span id="n-spots">2</span> spots, <span id="n-bw">1</span> of them designated' in about
    # The pages' absolute links (written for the FastAPI server, removed 20 Oct 2026) become the static
    # site's relative files, on every page.
    for name in ["about.html", "verification.html", "terms.html", "privacy.html", "testing.html", "feedback.html", "methods.html", "coverage.html", "clubs.html"]:
        page = (tmp_path / name).read_text()
        assert 'href="about.html">About</a>' in page, name
        assert 'href="/' not in page, name
        # A page that declares an icon has its icons and preloaded typefaces at files the static site has.
        if 'rel="icon"' in (bs.STATIC / name).read_text():
            for ref in ("icons/icon.svg", "icons/apple-touch-icon.png", "fonts/SourceSans3-latin.woff2", "fonts/SourceSerif4-latin.woff2"):
                assert f'href="{ref}"' in page and (tmp_path / ref).exists(), (name, ref)
    home = (tmp_path / "index.html").read_text()
    assert '<a href="about.html">About SwimSignal</a>' in home and '<a href="about.html" class="desk-only">About</a>' in home


def test_the_page_view_counter_reaches_spot_pages_and_a_dropped_spot_loses_its_page(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS[:2], token="abcdefghij0123456789", root="https://example.org/")
    assert "cloudflareinsights" in (tmp_path / "spot" / "tarn" / "index.html").read_text()
    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/")
    assert (tmp_path / "spot" / "wharfe-ilkley").exists() and not (tmp_path / "spot" / "tarn").exists()
    assert "cloudflareinsights" not in (tmp_path / "index.html").read_text()
    template = (ROOT / "src" / "dipcast" / "site" / "index.html").read_text()
    assert 'id="count-btn"' in template and "getElementById('page-counter')" in template   # the way to object


def test_site_url_follows_the_repository_unless_set(monkeypatch):
    bs = _build_site()
    monkeypatch.delenv("DIPCAST_SITE_URL", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "EthanBuckley/swimcast")
    assert bs.site_url() == "https://ethanbuckley.github.io/swimcast/"
    monkeypatch.setenv("GITHUB_REPOSITORY", "dipspot/dipspot.github.io")   # an organisation's own site
    assert bs.site_url() == "https://dipspot.github.io/"
    monkeypatch.setenv("GITHUB_REPOSITORY", "EthanBuckley/swimcast")
    monkeypatch.setenv("DIPCAST_SITE_URL", "https://swim.example")
    assert bs.site_url() == "https://swim.example/"
    monkeypatch.setenv("DIPCAST_SITE_URL", "swim.example")   # no scheme: previews would get relative links
    assert bs.site_url() == "https://ethanbuckley.github.io/swimcast/"


def test_the_page_draws_the_spill_levels_at_the_cut_offs_the_build_labels_them_by():
    # The page's scales and bars place a day by SPILL_CUTS (levels.js); the labels in spots.json come
    # from transport.risk_label. A change to one without the other would put "High" on a moderate bar.
    from dipcast.model.transport import risk_label
    rules = (ROOT / "src" / "dipcast" / "site" / "levels.js").read_text()
    cuts = [float(x) for x in re.search(r"const SPILL_CUTS = \[([^\]]+)\]", rules).group(1).split(",")]
    levels = ["low", "moderate", "high", "very high"]
    # Since 23 Oct 2026 the label goes by the score shown, the 3 dp risk times 100 rounded, so the step is
    # just under each cut: 0.146 shows as 15 (moderate), 0.144 as 14 (low).
    for i, c in enumerate(cuts):
        assert risk_label(c - 0.006) == levels[i] and risk_label(c - 0.004) == levels[i + 1] and risk_label(c) == levels[i + 1], c


def test_the_page_and_the_build_use_one_id_rule():
    # Not a check of spots.csv: an odd id only loses its own page (it keeps ?spot=), and a failing
    # test here would stop every build and leave the whole site stale.
    bs = _build_site()
    assert bs.SPOT_ID.pattern == "[A-Za-z0-9_-]+"
    page = (ROOT / "src" / "dipcast" / "site" / "index.html").read_text()
    assert "const PAGE_ID = /^[A-Za-z0-9_-]+$/;" in page and "/\\/spot\\/([A-Za-z0-9_-]+)\\/?$/" in page
    # The pages the build writes below the root, which the page strips to find the root without a <base>.
    assert "replace(/(spot\\/[^/]+|saved|plan)\\/?$/, '')" in page


def test_the_ea_rating_reaches_bathing_water_spots_only(tmp_path):
    bs = _build_site()
    f = tmp_path / "c.json"
    f.write_text('{"sites": {"uke4100-08901": {"class": "poor", "year": 2025, "history": [[2025, "poor"]], "url": "https://e/x", "name": "W"},'
                 ' "uki2203-11942": {"url": "https://e/y", "name": "Ham"}}}')
    spots = [{"id": "bw-uke4100-08901"}, {"id": "bw-uki2203-11942"}, {"id": "thames-henley"}, {"id": "bw-ukx-unknown"}]
    assert bs.attach_classifications(spots, f) == 1   # the not-yet-rated water gets its EA page, not a rating
    assert spots[0]["classification"] == {"class": "poor", "year": 2025, "history": [[2025, "poor"]], "url": "https://e/x"}
    assert spots[1]["classification"] == {"url": "https://e/y"}
    assert "classification" not in spots[2] and "classification" not in spots[3]
    assert bs.attach_classifications(spots, tmp_path / "missing.json") == 0   # no file: no rating, and no failed build


def test_the_committed_ratings_cover_every_inland_bathing_water():
    import json
    sites = json.loads((ROOT / "data" / "raw" / "bathing_waters_inland.json").read_text())
    c = json.loads((ROOT / "data" / "raw" / "bathing_water_classifications.json").read_text())
    assert set(c["sites"]) == {s["id"] for s in sites}
    rated = [v for v in c["sites"].values() if "class" in v]
    assert rated and all(v["class"] in {"excellent", "good", "sufficient", "poor"} and v["year"] >= 2020 for v in rated)
    assert all(v["url"].startswith("https://environment.data.gov.uk/bwq/profiles/") for v in c["sites"].values())
    rules = (ROOT / "src" / "dipcast" / "site" / "levels.js").read_text()   # the page's names for the four
    assert "const CLASS_LEVEL = { excellent: 'low', good: 'low', sufficient: 'moderate', poor: 'high' };" in rules


def test_the_printed_pages_credits_come_one_source_a_line_with_what_swimsignal_changed():
    # docs/ORGANISER-PIVOT-2026-10.md, OP2: the decision record and the sites view print the credits for the
    # sources their spots use (printed.js), from data_credits' `sources`, so the words live in one place.
    from dipcast import config
    bs = _build_site()
    c = bs.data_credits("https://example.org/")
    assert set(c["companies"]) == set(config.LIVE_FEEDS)   # every feed SwimSignal reads, and no Dwr Cymru
    for name, credited in c["companies"].items():
        assert credited.split(" (")[0] in c["attribution"], name
    uses = {"overflows", "always", "gauge", "rain", "model", "lake", "osm", "soil"}
    for x in c["sources"]:
        assert x["use"] in uses and x["changed"].startswith("SwimSignal ") and x["changed"].endswith(".")
        assert not x["licence"] or x["licence"] in c["licences"]
    said = " ".join(x["credit"] for x in c["sources"])
    for must in ("Weather data by Open-Meteo.com", "Met Office", "{companies}", "via the National Storm Overflow Hub",
                 "Environment Agency data © Environment Agency copyright and/or database right",
                 "This uses Environment Agency flood and river level data from the real-time data API (Beta)",
                 "Contains OS data © Crown copyright and database right 2026",
                 "© OpenStreetMap contributors, openstreetmap.org/copyright", "Copernicus", "HydroLAKES",
                 "Soil moisture from ECMWF's IFS forecasts"):
        assert must in said, must
    lic = {x["credit"].split(",")[0]: x["licence"] for x in c["sources"]}
    assert lic["Weather data by Open-Meteo.com"] == "CC BY 4.0" and lic["Met Office data © Crown copyright"] == "CC BY-SA 4.0"
    # The id's commit is the one in every logged forecast's version, and spots.json carries it.
    from dipcast.model.forecast import code_commit, model_version
    assert f"+{code_commit()};" in model_version()
    assert '"commit": code_commit(),' in (ROOT / "scripts" / "build_site.py").read_text()


def test_each_spot_names_every_company_upstream_and_whether_its_sewage_crosses_a_lake():
    bs = _build_site()
    results = [{"id": "a", "upstream_summary": {"overflows": 3}}, {"id": "b", "upstream_summary": {"overflows": 0}}, {"id": "c", "error": "x"}]
    upstream = {"a": [{"company": "Thames Water", "lake_distance_km": 0}, {"company": "Anglian Water", "lake_distance_km": 1.2},
                      {"company": "Thames Water"}], "b": []}
    bs.attach_companies(results, upstream)
    assert results[0]["upstream_summary"] == {"overflows": 3, "companies": ["Anglian Water", "Thames Water"], "through_lake": True}
    assert results[1]["upstream_summary"] == {"overflows": 0, "companies": [], "through_lake": False}
    assert "upstream_summary" not in results[2]


def test_the_credits_travel_with_the_data_and_the_terms_link_every_licence(tmp_path):
    # CC BY 4.0 s.3(a) and s.4 (the water companies' feeds) and OGL v3 (EA, OS): a republished
    # data file must carry its credits, and the page they point to must link each licence.
    bs = _build_site()
    c = bs.data_credits("https://example.org/")
    assert {"attribution", "modified", "licences", "full"} <= set(c) and c["full"] == "https://example.org/terms.html#data"
    terms = (ROOT / "src" / "dipcast" / "pages" / "terms.html").read_text()
    assert all(url in terms for url in c["licences"].values())
    for company in ("Anglian", "Northumbrian", "Severn Trent", "South West", "Southern", "Thames", "United Utilities", "Wessex", "Yorkshire"):
        assert company in c["attribution"] and company in terms, company
    assert "Met Office" in c["attribution"] and "CC BY-SA 4.0" in c["attribution"]
    src = (ROOT / "scripts" / "build_site.py").read_text()   # all three published files get them
    assert '"credits": credits, "spots": results' in src
    assert '{**overflows_geojson(limit=20000), "credits": credits}' in src and '{**load_verification(), "credits": credits}' in src
    page = (ROOT / "src" / "dipcast" / "site" / "index.html").read_text()
    assert "None of these bodies endorses SwimSignal" in page and 'href="terms.html#data"' in page
    # With the counter on, only the privacy notice changes; the terms keep their own date.
    bs.write_pages(tmp_path, SPOTS[:1], token="abcdefghij0123456789", root="https://example.org/")
    assert "(page-view counter)" in (tmp_path / "privacy.html").read_text()
    assert "(page-view counter)" not in (tmp_path / "terms.html").read_text()
    assert 'href="terms.html#data"' in (tmp_path / "verification.html").read_text()


def test_nothing_credits_the_ea_with_advice_the_law_gives_to_the_council():
    # Bathing Water Regulations 2013 reg 13(1)(b): at a poor water the local authority that
    # controls it issues the advice against bathing, not the EA.
    for p in [ROOT / "src" / "dipcast" / "site" / "index.html", ROOT / "src" / "dipcast" / "pages" / "terms.html"]:
        assert "advises against bathing" not in p.read_text(), p.name


def test_observations_from_is_the_first_day_with_a_mask():
    from dipcast.forecast_log import observations_from
    days = pd.to_datetime(["2026-09-27", "2026-09-28", "2026-09-29"]).date
    cov = pd.DataFrame({"site_id": ["a", "a", "b"], "day": days, "slots": [0, 1 << 20, 1 << 3]})
    assert observations_from(cov) == "2026-09-28"
    assert observations_from(cov.assign(slots=0)) is None   # rows written before the masks existed
    assert observations_from(pd.DataFrame()) is None


def test_lead_skill_starts_at_one_and_never_rises():
    skill = _build_site().lead_skill()
    for k in ("spill", "water"):
        s = skill[k]
        assert len(s) == 5 and s[0] == 1.0 and all(0 < b <= a for a, b in pairwise(s))


def test_alerts_are_off_unless_both_settings_are_sound(monkeypatch):
    bs = _build_site()
    monkeypatch.delenv(bs.PUSH_URL_ENV, raising=False)
    monkeypatch.delenv(bs.PUSH_KEY_ENV, raising=False)
    monkeypatch.delenv(bs.PUSH_DATES_ENV, raising=False)
    assert bs.push_config() is None
    key = "B" + "A" * 86
    monkeypatch.setenv(bs.PUSH_URL_ENV, "https://dipspot-push.example.workers.dev/")
    monkeypatch.setenv(bs.PUSH_KEY_ENV, key)
    assert bs.push_config() == {"url": "https://dipspot-push.example.workers.dev/", "key": key}
    # Alerts for a date: only once the variable says the Worker that takes them is deployed.
    monkeypatch.setenv(bs.PUSH_DATES_ENV, "1")
    assert bs.push_config() == {"url": "https://dipspot-push.example.workers.dev/", "key": key, "dates": True}
    monkeypatch.setenv(bs.PUSH_DATES_ENV, "yes please")
    assert "dates" not in bs.push_config()
    monkeypatch.delenv(bs.PUSH_DATES_ENV)
    monkeypatch.setenv(bs.PUSH_URL_ENV, "http://dipspot-push.example.workers.dev/")   # not https
    assert bs.push_config() is None
    monkeypatch.setenv(bs.PUSH_URL_ENV, "https://dipspot-push.example.workers.dev/")
    monkeypatch.setenv(bs.PUSH_KEY_ENV, key + '"')   # would break out of the page's JSON
    assert bs.push_config() is None


def test_the_privacy_notice_covers_research_sessions_with_their_retention(tmp_path):
    # docs/COMPREHENSION-TEST-2026-10-RUN-SHEET.md, section 6: the notice must match what the sessions keep.
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/")
    privacy = (tmp_path / "privacy.html").read_text()
    assert '<h2 id="research">Research sessions</h2>' in privacy
    for kept in ["or 21 days after your session, whichever comes first", "no more than 7 days",
                 "no later than 31 January 2027", "including after your contact details are deleted",
                 "Only genuinely anonymised findings are published", "removed or corrected under your rights to erasure"]:
        assert kept in privacy, kept
    assert "Apart from what is kept for research sessions (above), SwimSignal holds none" in privacy


def test_the_privacy_notice_describes_alerts_only_when_they_are_on(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/")
    off = (tmp_path / "privacy.html").read_text()
    assert "<h2>If alerts are added</h2>" in off and "push address" not in off
    for before, _ in bs.PUSH_SWAPS:   # a rewrite of the notice must not leave a swap with nothing to swap
        assert before in off, before
    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/", push=True)
    on = (tmp_path / "privacy.html").read_text()
    assert "<h2>Alerts</h2>" in on and "push address" in on and "If alerts are added" not in on
    for before, after in bs.PUSH_SWAPS:
        assert after in on and before not in on
    # The weekly note (push/src/weekly.js) is one more thing the record can hold, and one more use.
    assert "if you tick the weekly note, that you asked for it" in on
    assert "The weekly note is off until you tick it, and unticking it stops it." in on
    # Alerts for a date: said only once DIPCAST_PUSH_DATES turns them on.
    for before, after in bs.PUSH_DATES_SWAPS:
        assert before in bs.PUSH_PRIVACY, before
        assert before in on and after not in on
    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/", push=True, push_dates=True)
    dated = (tmp_path / "privacy.html").read_text()
    for before, after in bs.PUSH_DATES_SWAPS:
        assert after in dated and before not in dated, after
    assert "up to 10 pairs of a spot and a date" in dated
    assert (tmp_path / "levels.js").exists()


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_offline_copy_rules():
    # sw.js runs in a browser, so its tests are JavaScript; here so that the build's test step runs them.
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "site_cache.test.cjs"), str(ROOT / "tests" / "site_planner.test.cjs"),
                        str(ROOT / "tests" / "site_counter.test.cjs"), str(ROOT / "tests" / "site_flows.test.cjs")],
                       capture_output=True, text=True, timeout=60, check=False)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_alerts_file_uses_the_page_rules(tmp_path):
    import json
    bs = _build_site()
    (tmp_path / "data").mkdir()
    river = {"id": "a", "name": "A river", "kind": "river", "upstream_summary": {"overflows": 3}, "location": {"mode": "river"},
             "now": {"label": "low", "discharging_upstream": 0},
             "days": [{"date": "2026-09-29", "risk": 0.5, "label": "high"}, {"date": "2026-09-30", "risk": 0.01, "label": "low"}]}
    (tmp_path / "data" / "spots.json").write_text(json.dumps({"generated_at": "2026-09-29T08:00:00+01:00", "spots": [river, SPOTS[1]]}))
    assert bs.write_alerts(tmp_path, "https://example.org/swim/", push_on=False)
    out = json.loads((tmp_path / "data" / "alerts.json").read_text())
    assert out["generated_at"] == "2026-09-29T08:00:00+01:00"
    # Alerts for a date (push/src/dates.js): the five days, and each day's level, headline and
    # action, the sentences as places in `words`; a day with no forecast is null.
    assert out["dates"] == ["2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"]
    words = out["words"]
    assert [[d[0], words[d[1]], words[d[2]]] if d else None for d in out["spots"]["a"]["days"]] == [
        ["high", "High risk: sewage spills", "Better to choose a lower day or spot. If you do swim, try not to swallow any water."],
        ["low", "Low risk", "Usual care: cover cuts, try not to swallow water and wash your hands before eating."], None, None, None]
    assert out["spots"]["a"] == {"name": "A river", "rank": 2, "level": "high", "headline": "High risk today: sewage spills",
                                 "action": "Better to choose a lower day or spot. If you do swim, try not to swallow any water.",
                                 "url": "https://example.org/swim/spot/a/",
                                 "best": {"date": "2026-09-30", "level": "low", "words": "tomorrow, low risk"},
                                 "days": out["spots"]["a"]["days"]}
    assert out["spots"]["tarn"]["rank"] == -1 and out["spots"]["tarn"]["level"] == "no river connection"
    assert out["spots"]["tarn"]["headline"] == "No monitored overflow found upstream"   # one plain wording since 11 Oct 2026
    assert out["spots"]["tarn"]["action"] == "After heavy rain, wait a couple of days before swimming if you can."
    assert "best" not in out["spots"]["tarn"]   # the same every day: nothing for the weekly note
    assert "days" not in out["spots"]["tarn"]   # nor for a date: the alerts use its own level


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_alerts_file_names_the_lowest_days_ahead(tmp_path):
    # The weekly note (push/src/weekly.js) says these words as they are: the four days after today,
    # the lowest level and the days that have it, in levels.js's day words, with "risk".
    import json
    bs = _build_site()
    (tmp_path / "data").mkdir()
    dates = ["2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"]   # Tuesday to Saturday
    risk = {"low": 0.05, "moderate": 0.3, "high": 0.5, "very high": 0.8}

    def river(id, labels, **extra):
        return {"id": id, "name": id, "kind": "river", "upstream_summary": {"overflows": 3}, "location": {"mode": "river"},
                "now": {"label": "low", "discharging_upstream": 0}, **extra,
                "days": [{"date": d, "risk": risk[lv], "label": lv} for d, lv in zip(dates, labels)]}
    spots = [river("two", ["high", "moderate", "low", "moderate", "low"]),
             river("dry", ["moderate", "low", "low", "low", "low"]),
             river("wet", ["very high", "moderate", "high", "moderate", "moderate"]),
             river("first", ["low", "very high", "high", "moderate", "high"]),
             river("poor", ["low", "low", "low", "low", "low"], classification={"class": "Poor"})]
    (tmp_path / "data" / "spots.json").write_text(json.dumps({"generated_at": "2026-09-29T08:00:00+01:00", "spots": spots}))
    assert bs.write_alerts(tmp_path, "https://example.org/swim/", push_on=False)
    out = json.loads((tmp_path / "data" / "alerts.json").read_text())["spots"]
    assert out["two"]["best"] == {"date": "2026-10-01", "level": "low", "words": "Thursday and Saturday, low risk"}
    assert out["dry"]["best"]["words"] == "low risk every day from tomorrow to Saturday"
    assert out["wet"]["best"] == {"date": "2026-09-30", "level": "moderate", "words": "tomorrow, Friday and Saturday, moderate risk"}
    assert out["first"]["best"] == {"date": "2026-10-02", "level": "moderate", "words": "Friday, moderate risk"}   # today's low is not ahead
    assert out["poor"]["best"] == {"date": "2026-09-30", "level": "high", "words": "at least high risk every day"}


def test_feedback_and_experience_are_built_for_nested_github_pages(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/dipcast/")
    feedback = (tmp_path / "feedback.html").read_text()
    assert 'href="page.css"' in feedback and 'href="index.html"' in feedback
    assert 'href="/' not in feedback
    assert "hello@swimsignal.co.uk" in feedback and "Send by email" in feedback
    home = (tmp_path / "index.html").read_text()
    stamp = bs.shell_stamp()
    assert re.fullmatch(r"[0-9a-f]{8}", stamp)
    # The page asks for its scripts at the build's stamp, as the offline copy stores them.
    assert f'<script src="experience.js?v={stamp}" defer>' in home and f'<script src="levels.js?v={stamp}" defer>' in home
    assert f'<script src="plan.js?v={stamp}" defer>' in home and (tmp_path / "plan.js").exists() and "`plan.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    # Named lists of saved spots (lists.js) likewise; a change to it renames the offline copy's cache.
    assert f'<script src="lists.js?v={stamp}" defer>' in home and (tmp_path / "lists.js").exists() and "`lists.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "lists.js" in bs.SHELL_SOURCES
    assert (tmp_path / "experience.js").exists()
    sw = (tmp_path / "sw.js").read_text()
    assert 'feedback.html' in sw and f"const BUILD = '{stamp}';" in sw and "const CACHE = `dipcast-${BUILD}`;" in sw
    assert "`levels.js?v=${BUILD}`" in sw and "unpkg" not in sw and "unpkg" not in home
    # The map library from this site, at the paths the page and the worker ask for.
    for f in ("vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css", "vendor/leaflet/LICENSE", "vendor/leaflet/images/layers.png"):
        assert (tmp_path / f).exists(), f
    assert 'href="vendor/leaflet/leaflet.css"' in home and 'src="vendor/leaflet/leaflet.js"' in home
    assert 'SwimSignal' in (tmp_path / "manifest.webmanifest").read_text()
    # Rebranding preserves the installed application's URL and saved-spot storage; the cache keeps its
    # dipcast- prefix, which the worker and the page's "Turn off the offline copy" clear by.
    assert '"start_url": "./"' in (tmp_path / "manifest.webmanifest").read_text()
    assert "k.startsWith('dipcast-')" in sw


def test_river_levels_are_an_observation_beside_the_forecast():
    """The nearest gauge on the spot's own river, as a dict the page can show; a lookup that fails
    or finds nothing leaves the spot without, and a failed forecast is not looked up at all."""
    from dipcast.ingest.flows import RiverState
    bs = _build_site()
    calls = []

    def lookup(lat, lon, dist, river):
        calls.append((lat, lon, dist, river))
        if river == "River Wharfe":
            return RiverState(station="Netherside Hall", river="River Wharfe", lat=lat + 0.05, lon=lon, level_m=0.433,
                              typical_low=0.3, typical_high=2.2, observed_at="2026-10-01T12:15:00Z", rloi="8276")
        if river == "Hebden Beck":
            raise RuntimeError("EA timed out")
        return None

    spots = [{"id": "a", "name": "Burnsall", "lat": 54.047, "lon": -1.953, "location": {"watercourse": "River Wharfe"}},
             {"id": "b", "name": "Hebden", "lat": 54.0, "lon": -2.0, "location": {"watercourse": "Hebden Beck"}},
             {"id": "c", "name": "Tarn", "lat": 54.4, "lon": -3.0, "location": {"watercourse": None}},
             {"id": "d", "name": "Broken", "lat": 54.5, "lon": -3.1, "error": "forecast failed: boom"}]
    now = datetime(2026, 10, 1, 13, 0, tzinfo=UTC)   # an hour after the reading: current, not stale
    assert bs.attach_river_levels(spots, lookup=lookup, workers=2, now=now) == 1
    rs = spots[0]["river_state"]
    assert rs["station"] == "Netherside Hall" and rs["level_m"] == 0.433 and rs["label"] == "low" and rs["rloi"] == "8276"
    assert rs["same_river"] is True and 5 < rs["distance_km"] < 6 and rs["index"] == 0.07
    assert rs["stale"] is False and rs["age_hours"] == 0.8
    assert spots[1]["river_state"] is None and spots[2]["river_state"] is None and spots[3]["river_state"] is None
    assert len(calls) == 3 and all(c[2] == 15 for c in calls)   # the failed forecast is skipped
    # The EA's own attribution line travels with the data and sits on the terms page.
    line = "this uses Environment Agency flood and river level data from the real-time data API (Beta)"
    assert line in bs.data_credits("https://example.org/")["attribution"]
    assert line in (ROOT / "src" / "dipcast" / "pages" / "terms.html").read_text()
    assert line in (ROOT / "src" / "dipcast" / "site" / "index.html").read_text()


def test_weather_context_is_attached_per_spot_and_a_failed_call_leaves_none(tmp_path, monkeypatch):
    bs = _build_site()
    from dipcast.ingest import rainfall
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)   # the day's Open-Meteo ledger
    seen = []

    def request(url, params, timeout=30):
        seen.append(params)
        lats = params["latitude"].split(",")
        return [{"daily": {"time": ["2026-10-01", "2026-10-02"], "temperature_2m_max": [11.4, None],
                           "sunrise": ["2026-10-01T07:12", "2026-10-02T07:14"], "sunset": ["2026-10-01T18:40", "2026-10-02T18:38"]}}
                for _ in lats]

    spots = [{"id": "a", "name": "A", "lat": 54.0, "lon": -2.0}, {"id": "b", "name": "B", "lat": 54.1, "lon": -2.1},
             {"id": "d", "name": "Broken", "lat": 54.5, "lon": -3.1, "error": "forecast failed: boom"}]
    assert bs.attach_weather(spots, request=request, cache=tmp_path / "weather.json") == 2
    assert seen[0]["daily"] == "temperature_2m_max,sunrise,sunset" and seen[0]["latitude"] == "54.000,54.100"
    assert spots[0]["weather"]["days"] == [{"date": "2026-10-01", "tmax": 11, "sunrise": "07:12", "sunset": "18:40"},
                                           {"date": "2026-10-02", "tmax": None, "sunrise": "07:14", "sunset": "18:38"}]
    assert spots[0]["weather"]["credit"] == "Weather data by Open-Meteo.com" and "weather" not in spots[2]

    def broken(url, params, timeout=30):
        raise RuntimeError("open-meteo request failed")
    fresh = [{"id": "a", "name": "A", "lat": 54.0, "lon": -2.0}]
    assert bs.attach_weather(fresh, request=broken, cache=tmp_path / "none.json") == 0 and "weather" not in fresh[0]


def test_the_data_page_lists_every_file_in_data_with_its_size(tmp_path):
    # data.html describes the files the build publishes; the build fills in their sizes and lists
    # any file in data/ the page does not describe, so the list is always every file published.
    bs = _build_site()
    data = tmp_path / "data"
    (data / "links").mkdir(parents=True)
    (data / "spots.json").write_bytes(b"x" * 626_076)
    (data / "overflows.geojson").write_bytes(b"x" * 5_947_289)
    (data / "verification.json").write_bytes(b"x" * 400)
    (data / "verification_live.csv").write_text("# credits\noverflow_id,observed\n")
    (data / "anypoint").mkdir()
    (data / "anypoint" / "tiles.json").write_text("{}")
    (data / "new.csv").write_text("a,b\n")   # a file nobody has described yet
    (data / "links" / "a.json").write_bytes(b"x" * 1500)
    (data / "links" / "b.json").write_bytes(b"x" * 1500)
    bs.write_pages(tmp_path, SPOTS[:1], token="abcdefghij0123456789", root="https://example.org/")
    page = (tmp_path / "data.html").read_text()
    row = lambda name: re.search(rf'<tr data-file="{re.escape(name)}">(.*?)</tr>', page).group(1)
    assert row("spots.json").endswith('<td class="num">626 kB</td>') and 'href="data/spots.json"' in row("spots.json")
    assert row("overflows.geojson").endswith(">5.9 MB</td>") and row("verification.json").endswith(">1 kB</td>")
    assert row("alerts.json").endswith(">Not in this build</td>")   # described, but this build wrote none
    assert 'href="data/verification_live.csv"' in row("verification_live.csv")
    assert 'href="data/anypoint/tiles.json"' in row("anypoint/")
    assert "Not described here yet" not in row("anypoint/") + row("verification_live.csv")
    assert row("new.csv") == '<td><a href="data/new.csv">new.csv</a></td><td>Not described here yet.</td><td class="num">1 kB</td>'
    assert row("links/") == '<td>links/</td><td>Not described here yet.</td><td class="num">3 kB</td>'   # a folder, whole
    assert bs.with_data_files((bs.STATIC / "data.html").read_text(), data)[1] == ["links/", "new.csv"]
    # The documented files each have a section of their own.
    for name in ("spots.json", "alerts.json", "overflows.geojson", "verification.json", "verification_live.csv", "verification_spots_live.csv", "spot_scores.json", "places.json", "waters.json"):
        assert f'<h2 id="{name.replace(".", "-").replace("_", "-")}">{name}</h2>' in page, name
    assert '<h2 id="anypoint">anypoint/</h2>' in page and '<h2 id="upstream">upstream/</h2>' in page
    # A prose page like the others: the shared head and foot, flat links, and the counter when it is on.
    assert "<title>Data files · SwimSignal</title>" in page and 'href="page.css"' in page and 'href="/' not in page
    assert 'href="terms.html#data"' in page and 'href="about.html#embed"' in page and "cloudflareinsights" in page
    assert 'href="data.html">Data files</a>' in (tmp_path / "about.html").read_text()
    # An empty data/ (write_pages over a fresh folder): every described row says so, and nothing breaks.
    empty = tmp_path / "empty"
    empty.mkdir()
    assert bs.write_data_page(empty) == [] and (empty / "data.html").read_text().count("Not in this build") == 19   # spot_scores.json makes 16, overflows/ 17, waters.json 18, verification_spots_live.csv 19


def test_the_embed_is_written_beside_the_app_with_its_scripts_versioned(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS[:1], token="abcdefghij0123456789", root="https://example.org/")
    page = (tmp_path / "embed.html").read_text()
    v = re.search(r'<script src="levels\.js\?v=([0-9a-f]{8})"></script>', page).group(1)
    assert f'<script src="embed.js?v={v}"></script>' in page and v == bs.write_embed(tmp_path)
    for f in ("embed.js", "levels.js", "page.css", "fonts/SourceSans3-latin.woff2", "fonts/SourceSerif4-latin.woff2", "icons/icon.svg"):
        assert (tmp_path / f).exists(), f
    assert '<meta name="robots" content="noindex">' in page and 'name="viewport" content="width=device-width, initial-scale=1"' in page
    # No page-view counter in someone else's page: it could not see a visitor's choice not to be counted.
    assert "cloudflareinsights" not in page and "page-counter" not in page
    assert 'id="card"' in page and "<noscript>" in page


def test_the_embed_fits_a_column_320_px_wide():
    # What the card lays out at a fixed size must leave the day's bar room at 320 px: the frame's
    # border and padding, and the rows' day and level columns and their gaps. The rest is fluid
    # (checked in Chrome on 3 Oct 2026, and on 4 Oct with the full credits: no spot's card overflowed
    # at 320, 375 or 480 px).
    css = "\n".join(re.findall(r"<style>(.*?)</style>", (ROOT / "src" / "dipcast" / "site" / "embed.html").read_text(), re.DOTALL))
    css = re.sub(r"[^{}]*\.screen[^{}]*\{[^}]*\}", "", css)   # the live sign's rules: a screen, not a frame (below)
    card = re.search(r"\.card \{([^}]*)\}", css).group(1)
    pad = [int(x) for x in re.search(r"padding:(\d+)px (\d+)px", card).groups()]
    border = int(re.search(r"border:(\d+)px", card).group(1))
    drow = re.search(r"\.drow \{([^}]*)\}", css).group(1)
    cols = [int(x) for x in re.search(r"grid-template-columns:(\d+)px (\d+)px minmax\(0, 1fr\)", drow).groups()]
    gap = int(re.search(r"gap:(\d+)px", drow).group(1))
    bar = 320 - 2 * border - 2 * pad[1] - sum(cols) - 2 * gap
    assert bar >= 100, bar
    assert not re.search(r"(?<![-\w])(min-)?width\s*:\s*(3[2-9]\d|[4-9]\d\d|\d{4,})px", css)   # nothing wider than the frame
    assert "max-width:480px" in card.replace(" ", "")


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_embed_card_rules():
    # embed.js runs in a browser, so its tests are JavaScript; here so that the build's test step runs them.
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "site_embed.test.cjs")], capture_output=True, text=True, timeout=60, check=False)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_embed_card_carries_the_data_files_notices_word_for_word():
    # The card goes on other people's pages, so it carries what the data files carry (data_credits):
    # the Stream ID lookup, and Ordnance Survey's and Copernicus's notices as their licences word them.
    embed = ROOT / "src" / "dipcast" / "site" / "embed.js"
    credit = subprocess.run(["node", "-p", "require(process.argv[1]).CREDIT", str(embed)],
                            capture_output=True, text=True, timeout=60, check=True).stdout
    attribution = _build_site().data_credits("https://example.org/")["attribution"]
    notices = ["the Stream ID lookup, via Stream",
               re.search(r"Contains OS data © Crown copyright and database right \d{4}\.", attribution).group(0),
               re.search(r"contains modified Copernicus .*? it contains\.", attribution).group(0)]
    for n in notices:
        assert n in credit, n


def test_about_documents_the_data_page_and_the_embed_and_the_terms_allow_it(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/")
    about = (tmp_path / "about.html").read_text()
    snippet = re.search(r'<h2 id="embed">.*?<pre><code>(.*?)</code></pre>', about, re.DOTALL).group(1)
    assert snippet.startswith("&lt;iframe src=\"https://swimsignal.co.uk/embed.html?spot=wharfe-burnsall\"") and 'title="' in snippet
    assert 'href="embed.html?spot=wharfe-burnsall"' in about and (tmp_path / "embed.html").exists()
    # The frame is the tallest card measured, rounded up to 20 px, so that card fits without scrolling.
    height = int(re.search(r'height="(\d+)"', snippet).group(1))
    tallest = int(re.search(r"the tallest card was (\d+) pixels high", about).group(1))
    assert tallest <= height < tallest + 20 and height % 20 == 0, (tallest, height)
    terms = (tmp_path / "terms.html").read_text()
    allow = re.search(r"<li>You may show a spot's forecast on your own non-commercial website.*?</li>", terms).group(0)
    assert "embed.html" in allow and "credits intact" in allow and 'href="about.html#embed"' in allow
    assert "Ask first about any other use." in allow   # as the reuse bullet above it: Open-Meteo's free rain is non-commercial
    assert 'href="data.html"' in terms
    embed = about[about.index('<h2 id="embed">'):]
    assert "non-commercial website" in embed and "Ask first about any other use" in embed and 'href="mailto:hello@swimsignal.co.uk"' in embed


def _modules(d: str, size: int, border: int = 4) -> list[list[int]]:
    """A QR code's modules, 1 for dark, from segno's SVG path: a row of runs ("h7") and moves ("m2 0")
    for each line of the symbol, drawn half a module down. The quiet zone round it is cut off."""
    grid, x, y = [[0] * size for _ in range(size)], 0.0, 0.0
    for cmd, a, b in re.findall(r"([Mmh])(-?[\d.]+)(?: (-?[\d.]+))?", d):
        if cmd == "M":
            x, y = float(a), float(b)
        elif cmd == "m":
            x, y = x + float(a), y + float(b)
        else:
            for i in range(round(x), round(x + float(a))):
                grid[int(y)][i] = 1
            x += float(a)
    return [row[border:size - border] for row in grid[border:size - border]]


def test_the_organisers_page_is_a_prose_page_with_its_scripts_versioned_and_linked(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, token="abcdefghij0123456789", root="https://example.org/swim/", day="2026-10-04")
    page = (tmp_path / "organisers.html").read_text()
    v = re.search(r'<script src="levels\.js\?v=([0-9a-f]{8})"></script>', page).group(1)
    assert f'<script src="organisers.js?v={v}"></script>' in page and v == bs.write_organisers(tmp_path)
    assert (tmp_path / "organisers.js").exists()
    assert "<title>Event organisers · SwimSignal</title>" in page and '<header class="top">' in page and 'href="about.html">About</a>' in page
    assert 'href="/' not in page and "cloudflareinsights" in page   # flat links, and the counter as on the other prose pages
    assert "<loc>https://example.org/swim/organisers.html</loc>" in (tmp_path / "sitemap.xml").read_text()
    # The checklist links the two pages it is drawn from, and is in the page, so it works and prints without a script.
    assert "events.britishtriathlon.org/uploads/content/Water%20Quality%20Guidance.pdf" in page
    assert "swimming.org/swimengland/running-your-club/" in page
    assert '<ol class="checklist">' in page.split('<script src="levels')[0] and "@page { size:A4 portrait" in page
    # Linked from the app's foot, from every spot's actions (one line in index.html) and from About.
    template = bs.TEMPLATE.read_text()
    assert '<a href="organisers.html">For event organisers</a>' in template
    assert template.count('organisers.html#spot=${encodeURIComponent(d.id)}') == 1
    assert 'href="organisers.html"' in (tmp_path / "about.html").read_text()


def test_write_pages_writes_the_sites_view_and_the_decision_record(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, token="abcdefghij0123456789", root="https://example.org/swim/", day="2026-10-04")
    sitemap = (tmp_path / "sitemap.xml").read_text()
    for name, scripts, title in [("sites.html", bs.SITES_SCRIPTS, "Sites view · SwimSignal"), ("record.html", bs.RECORD_SCRIPTS, "Decision record · SwimSignal")]:
        page = (tmp_path / name).read_text()
        v = re.search(r'<script src="levels\.js\?v=([0-9a-f]{8})"></script>', page).group(1)
        for f in scripts:   # every script at one version, a hash of the scripts, and beside the page
            assert f'<script src="{f}?v={v}"></script>' in page, (name, f)
            assert (tmp_path / f).exists(), (name, f)
        assert f"<title>{title}</title>" in page and '<header class="top">' in page and 'class="site-foot"' in page
        assert 'href="/' not in page and "cloudflareinsights" in page   # flat links, and the counter as on the other prose pages
        assert "@page { size:A4 portrait" in page
        assert f"<loc>https://example.org/swim/{name}</loc>" in sitemap   # as the organisers' page is
    assert bs.write_sites(tmp_path) != bs.write_record(tmp_path)   # each page's own scripts
    # The organisers' page loads the sites link's maker, versioned with its other scripts.
    org = (tmp_path / "organisers.html").read_text()
    v = re.search(r'<script src="levels\.js\?v=([0-9a-f]{8})"></script>', org).group(1)
    assert f'<script src="lists.js?v={v}"></script>' in org and f'<script src="sites.js?v={v}"></script>' in org and 'id="sites-maker"' in org


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_sites_view_and_decision_record_rules():
    # sites.js and record.js run in a browser, so their tests are JavaScript.
    for f in ("site_sites.test.cjs", "site_record.test.cjs"):
        r = subprocess.run(["node", "--test", str(ROOT / "tests" / f)], capture_output=True, text=True, timeout=60, check=False)
        assert r.returncode == 0, r.stdout + r.stderr


def test_every_spot_with_a_page_gets_a_sign_to_print_that_shows_no_level(tmp_path):
    import segno
    bs = _build_site()
    osm = {"id": "osm-x", "name": "River X, Pool", "kind": "river", "source": "openstreetmap", "upstream_summary": {"overflows": 1}, "days": []}
    bs.write_pages(tmp_path, [*SPOTS, osm], root="https://example.org/swim/")
    assert not (tmp_path / "spot" / "Bad Id").exists()   # no page, so no sign
    sign = (tmp_path / "spot" / "wharfe-ilkley" / "sign" / "index.html").read_text()
    head = sign.split("</head>")[0]
    assert '<base href="../../../">' in head and '<meta name="robots" content="noindex">' in head
    assert "<title>Sign to print: Wharfe at &quot;Cromwheel&quot; &amp; Ilkley · SwimSignal</title>" in head
    assert "{{" not in sign and "<script" not in sign   # every slot filled, and nothing to run
    sheet = sign.split('<article class="sheet"')[1].split("</article>")[0]
    assert "Not a safety check: look at the signs at the water before you swim." in sheet   # the site's own words (index.html)
    assert "example.org/swim/spot/<wbr>wharfe-ilkley" in sheet
    assert sheet.split('class="s-credit">')[1].startswith("SwimSignal is independent") and "Data credits: example.org/swim/terms.html#data" in sheet
    assert "OpenStreetMap" not in sheet and "Location © OpenStreetMap contributors" in (tmp_path / "spot" / "osm-x" / "sign" / "index.html").read_text()
    assert not re.search(r"(?i)\b(low|moderate|high) risk\b|no sewage risk|no river connection", sheet)   # printed, a level goes out of date
    assert "@page { size:A4 portrait; margin:0; }" in sign and "zoom:2" in sign   # laid out at A6, printed at twice that
    assert "sign/" not in (tmp_path / "sitemap.xml").read_text()
    # The QR code is the one for the spot's page, on the sign and in the file the live sign shows.
    m = re.search(r'<svg role="img" aria-label="QR code for example\.org/swim/spot/wharfe-ilkley" viewBox="0 0 (\d+) \d+" class="qr"><path stroke="#000" d="([^"]+)"', sheet)
    svg = (tmp_path / "spot" / "wharfe-ilkley" / "qr.svg").read_text()
    assert svg.startswith("<?xml") and f'd="{m.group(2)}"' in svg
    want = segno.make("https://example.org/swim/spot/wharfe-ilkley/", error="q", micro=False)
    assert _modules(m.group(2), int(m.group(1))) == [list(r) for r in want.matrix]
    assert want.error in "QH"   # at least a quarter of the code can be lost and it still reads


def test_the_organisers_page_and_the_signs_stay_out_of_the_offline_copy():
    # Used at a desk or on a screen with a connection, and the live sign must show the newest forecast,
    # so the worker does not store them ahead (build_site.py says why); a visited page is kept as any is.
    bs = _build_site()
    shell = re.search(r"const SHELL = \[(.*?)\];", (bs.TEMPLATE.parent / "sw.js").read_text(), re.DOTALL).group(1)
    assert not any(w in shell for w in ("organisers", "sign.html", "sign/", "embed", "qr.svg", "sites", "record"))
    assert not {bs.ORGANISERS, bs.TEMPLATE.parent / "organisers.js", bs.TEMPLATE.parent / "sign.html"} & set(bs.SHELL_SOURCES)
    assert not {bs.TEMPLATE.parent / f for f in ("sites.html", "sites.js", "record.html", "record.js")} & set(bs.SHELL_SOURCES)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_organisers_page_and_live_sign_rules():
    # organisers.js and embed.js's screen mode run in a browser, so their tests are JavaScript.
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "site_organisers.test.cjs")], capture_output=True, text=True, timeout=60, check=False)
    assert r.returncode == 0, r.stdout + r.stderr


def test_tips_are_off_unless_the_variable_is_a_ko_fi_page(monkeypatch):
    bs = _build_site()
    monkeypatch.delenv(bs.SUPPORT_URL_ENV, raising=False)
    assert bs.support_url() is None
    monkeypatch.setenv(bs.SUPPORT_URL_ENV, " https://ko-fi.com/swimsignal ")
    assert bs.support_url() == "https://ko-fi.com/swimsignal"
    for bad in ["http://ko-fi.com/swimsignal", "https://ko-fi.com.evil.example/x", "https://ko-fi.com/a\"b",
                "https://ko-fi.com/swimsignal/shop", "https://example.org/"]:
        monkeypatch.setenv(bs.SUPPORT_URL_ENV, bad)
        assert bs.support_url() is None, bad


def test_tips_add_a_page_a_link_in_every_foot_and_a_privacy_section_only_when_on(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS[:1], token="abcdefghij0123456789", root="https://example.org/swim/")
    privacy_off = (tmp_path / "privacy.html").read_text()
    for anchor in ["<h2>The server version</h2>", bs.SUPPORT_RIGHTS[0]]:   # what with_support hangs on
        assert anchor in privacy_off, anchor
    assert "<h2>Help test it this winter</h2>" in (tmp_path / "about.html").read_text()
    assert not (tmp_path / "support.html").exists()
    assert not any("Support SwimSignal" in p.read_text() for p in tmp_path.rglob("*.html"))

    bs.write_pages(tmp_path, SPOTS[:1], token="abcdefghij0123456789", root="https://example.org/swim/",
                   support="https://ko-fi.com/swimsignal")
    page = (tmp_path / "support.html").read_text()
    assert 'href="https://ko-fi.com/swimsignal"' in page and "__KOFI_URL__" not in page
    assert 'href="privacy.html#tips"' in page and 'href="/' not in page   # works under a sub-path
    assert "ko-fi.com/widgets" not in page and "<script src" not in page   # a plain link, nothing loaded from Ko-fi
    # Every page with the site's foot links it once, at its own depth.
    feet = {p.relative_to(tmp_path).as_posix(): p.read_text() for p in tmp_path.rglob("*.html") if "Feedback</a>" in p.read_text()}
    for name, html in feet.items():
        if "<footer" in html:
            assert html.count(">Support SwimSignal</a>") == 1, name
    assert 'href="support.html">Support SwimSignal' in feet["about.html"]
    spot = (tmp_path / "spot" / "wharfe-ilkley" / "index.html").read_text()
    assert ">Support SwimSignal</a>" in spot
    privacy = (tmp_path / "privacy.html").read_text()
    assert '<h2 id="tips">If you leave a tip</h2>' in privacy and bs.SUPPORT_RIGHTS[1] in privacy
    assert "Last updated 26 October 2026 (page-view counter, tips)." in privacy   # after the counter's own note
    assert "(tips)" not in (tmp_path / "terms.html").read_text()
    assert 'href="support.html">How to tip' in (tmp_path / "about.html").read_text()
    assert "support.html" in (tmp_path / "sitemap.xml").read_text()

    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/swim/")   # turned off again
    assert not (tmp_path / "support.html").exists()
    assert not any("Support SwimSignal" in p.read_text() for p in tmp_path.rglob("*.html"))
    assert "Last updated 26 October 2026." in (tmp_path / "privacy.html").read_text()


def test_map_tiles_stay_on_openstreetmap_unless_a_known_provider_has_a_key(monkeypatch):
    bs = _build_site()
    monkeypatch.delenv(bs.TILES_ENV, raising=False)
    monkeypatch.delenv(bs.TILE_KEY_ENV, raising=False)
    assert bs.tile_config() is None
    monkeypatch.setenv(bs.TILES_ENV, "carto-voyager")
    assert bs.tile_config() is None   # no key: every tile would say "API key required"
    monkeypatch.setenv(bs.TILE_KEY_ENV, "abc123DEF456_-x")
    t = bs.tile_config()
    assert t["url"] == "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=abc123DEF456_-x"
    assert t["name"] == "CARTO" and "carto.com/attribution" in t["credit"] and "openstreetmap.org/copyright" in t["credit"]
    monkeypatch.setenv(bs.TILE_KEY_ENV, "abc123DEF456'+alert(1)+'")   # would break out of the page's string
    assert bs.tile_config() is None
    monkeypatch.setenv(bs.TILE_KEY_ENV, "abc123DEF456")
    monkeypatch.setenv(bs.TILES_ENV, "mapbox")
    assert bs.tile_config() is None
    for name, p in bs.TILE_PROVIDERS.items():   # every provider: https, the key in its place, a privacy policy
        assert p["url"].startswith("https://") and ("__KEY__" in p["url"]) == (name != "osm"), name
        assert p["privacy"].startswith("https://") and "'" not in p["credit"], name


def test_another_tile_provider_reaches_the_map_the_privacy_notice_and_the_terms(tmp_path):
    bs = _build_site()
    template = (ROOT / "src" / "dipcast" / "site" / "index.html").read_text()
    assert bs.TILE_LINE.format(**bs.TILE_PROVIDERS["osm"]) in template   # what with_tiles swaps
    assert '<link rel="preconnect" href="https://tile.openstreetmap.org">' in template   # and this
    assert bs.tile_origin(bs.TILE_PROVIDERS["carto-voyager"]["url"]) == "https://basemaps.cartocdn.com"
    bs.write_pages(tmp_path, SPOTS[:1], token="abcdefghij0123456789", root="https://example.org/")
    off = {n: (tmp_path / n).read_text() for n in ["index.html", "privacy.html", "terms.html"]}
    assert "tile.openstreetmap.org" in off["index.html"] and bs.OSM_PRIVACY_LI in off["privacy.html"]
    assert bs.TILE_LINE.format(**bs.TILE_PROVIDERS["osm"]) in (tmp_path / "app.js").read_text()
    assert off["privacy.html"].count("map images fetched from OpenStreetMap") == 2 and bs.OSM_TERMS in off["terms.html"]

    monkey = {**bs.TILE_PROVIDERS["carto-positron"], "id": "carto-positron"}
    tiles = {**monkey, "url": monkey["url"].replace("__KEY__", "testkey123")}
    bs.write_pages(tmp_path, SPOTS[:1], token="abcdefghij0123456789", root="https://example.org/", tiles=tiles,
                   support="https://ko-fi.com/swimsignal")
    for page in ["index.html", "saved/index.html", "plan/index.html", "spot/wharfe-ilkley/index.html"]:
        html = (tmp_path / page).read_text() + (tmp_path / "app.js").read_text()   # the map is drawn by the page's script, app.js
        assert "tile.openstreetmap.org" not in html, page
        assert "basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png?key=testkey123" in html, page
        assert '<link rel="preconnect" href="https://basemaps.cartocdn.com">' in html, page
        assert "tile.openstreetmap.org" not in html, page   # the preconnect swapped too
        assert 'href="https://carto.com/attribution/">CARTO</a>' in html, page
    privacy = (tmp_path / "privacy.html").read_text()
    assert "OpenStreetMap Foundation" not in privacy and "fetched from OpenStreetMap" not in privacy
    assert '<li><b>CARTO</b>, for the map images. Its <a href="https://carto.com/privacy/">privacy policy</a>' in privacy
    assert "Last updated 26 October 2026 (page-view counter, map images, tips)." in privacy
    terms = (tmp_path / "terms.html").read_text()
    assert bs.OSM_TERMS not in terms and "map tiles from CARTO:" in terms


def test_carto_tiles_bring_their_own_colour_filter_and_others_keep_openstreetmaps(tmp_path):
    bs = _build_site()
    template = (ROOT / "src" / "dipcast" / "site" / "index.html").read_text()
    osm_filter = bs.TILE_FILTER.search(template)[0]   # what with_tiles swaps for CARTO's
    assert "-6.6667 0 6.6667 0 -.13333" in osm_filter
    for name, key in [("carto-voyager", "voyager"), ("carto-positron", "positron")]:
        p = bs.TILE_PROVIDERS[name]
        html = bs.with_tiles(template, "index.html", {**p, "url": p["url"].replace("__KEY__", "testkey123")})
        assert bs.CARTO_FILTERS[key] in html and osm_filter not in html, name
        assert html.count('<filter id="tiles"') == 1, name
        assert "tintTiles(L.tileLayer(" in html, name   # the tiles still go through it, by script
    p = bs.TILE_PROVIDERS["thunderforest-atlas"]
    html = bs.with_tiles(template, "index.html", {**p, "url": p["url"].replace("__KEY__", "testkey123")})
    assert osm_filter in html
    assert osm_filter in bs.with_tiles(template, "index.html", None)


def test_the_carto_filters_turn_carto_water_blue_and_its_land_grey():
    """The two alpha rows and the land and tint offsets, applied by hand to the colours measured on
    CARTO's tiles on 5 Oct 2026, as the browser applies an feColorMatrix (clamped to 0..1)."""
    bs = _build_site()
    def apply(filt, rgb):
        rows = re.findall(r'values="([^"]+)"', filt)
        R, G, B = (c / 255 for c in rgb)
        cl = lambda x: max(0.0, min(1.0, x))
        def alpha(row):
            a = [float(x) for x in row.split()][15:]
            return cl(a[0] * R + a[1] * G + a[2] * B + a[4])
        water = alpha(rows[0]) * alpha(rows[1])
        lum = .21 * R + .7066 * G + .0713 * B
        land_off = float(rows[2].split()[4])
        tint = [float(x) for x in rows[3].split()[4::5][:3]]
        return tuple(round(255 * ((1 - water) * cl(lum + land_off) + water * cl(lum + t))) for t in tint)
    v, pz = bs.CARTO_FILTERS["voyager"], bs.CARTO_FILTERS["positron"]
    assert apply(v, (213, 232, 235)) == (188, 207, 216) and apply(pz, (212, 218, 220)) == (188, 207, 216)
    for land in [(251, 248, 243), (226, 237, 215), (251, 219, 152)]:   # land, a park, a main road
        r, g, b = apply(v, land)
        assert r == g == b, land
    r, g, b = apply(pz, (250, 250, 248))
    assert r == g == b == 235


def test_the_app_pages_scripts_are_all_deferred_in_their_order_and_the_pages_own_is_app_js(tmp_path):
    # docs/REVIEW-2026-10-16.md, F2: none of the page's scripts holds up the first paint. Deferred
    # scripts run in the order of their tags, so the order is the source's, with the page's own
    # script, now app.js, where it was: after the fourteen and before anypoint.js.
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS[:1], token="abcdefghij0123456789", root="https://example.org/")
    stamp, source = bs.shell_stamp(), bs.TEMPLATE.read_text()
    app = (tmp_path / "app.js").read_text()
    assert app.startswith("const BRAND = ") and "function loadOverflows" in app and "</script>" not in app
    assert bs.js_without_comment_lines(bs.APP_SCRIPT.search(source).group(1)) == app   # the source's script, as lean_page leaves it
    for page in ["index.html", "saved/index.html", "plan/index.html", "spot/wharfe-ilkley/index.html"]:
        html = (tmp_path / page).read_text()
        assert "const BRAND" not in html, page
        tags = re.findall(r"<script\b[^>]*\bsrc=\"([^\"?]+)[^\"]*\"([^>]*)>", html)
        assert tags and all("defer" in rest for _, rest in tags), page
        order = [src for src, _ in tags]
        assert order == [re.search(r'src="([^"]+)"', t).group(1) for t in re.findall(r"<script src=[^>]+>", source)
                         if "anypoint" not in t] + ["app.js", "anypoint.js"], page
        at = order.index
        assert at("reviews.js") < at("visits.js") and at("reviews.js") < at("illness.js") and at("reviews.js") < at("journal.js")
        assert at("levels.js") < at("since.js") and at("levels.js") < at("journal.js")
        assert at("vendor/leaflet/leaflet.js") == 0 and order[-2:] == ["app.js", "anypoint.js"]
        assert f'<script src="app.js?v={stamp}" defer></script>' in html, page
        # The scripts left inline are the head's: the early fetch of the forecast, and the counter.
        assert [m for m in re.findall(r"<script(?: id=\"[^\"]+\")?>", html)] == ["<script>", '<script id="page-counter">'], page
    assert "`app.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()   # the offline copy keeps it


OVERFLOW_TILES = [(51.5074, -0.1278, 511, 340), (54.05, -1.95, 506, 328), (50.1188, -5.5376, 496, 346), (55.7, -2.0, 506, 320),
                  (52.0, 0.0, 512, 338)]   # the same points as tests/site_overflow_tiles.test.cjs, for index.html's ovTile


def test_the_overflow_layer_is_cut_into_the_tiles_the_map_asks_for(tmp_path):
    # docs/REVIEW-2026-10-16.md, C4: data/overflows/<x>-<y>.json at zoom 10 beside the whole file.
    bs = _build_site()
    for lat, lon, x, y in OVERFLOW_TILES:
        assert bs.overflow_tile(lon, lat) == (x, y), (lat, lon)
    pt = lambda i, lat, lon: {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {"site_id": i}}
    feats = [pt("A", 51.5074, -0.1278), pt("B", 51.5075, -0.1279), pt("C", 54.05, -1.95), pt("nowhere", float("nan"), 0.0)]
    old = tmp_path / "data" / "overflows" / "1-1.json"
    old.parent.mkdir(parents=True)
    old.write_text("{}")   # a tile from an earlier build whose overflows have gone
    credits = {"attribution": "Contains data from the water companies"}
    assert bs.write_overflow_tiles(tmp_path, {"type": "FeatureCollection", "features": feats, "credits": credits}) == 2
    out = tmp_path / "data" / "overflows"
    assert sorted(p.name for p in out.iterdir()) == ["506-328.json", "511-340.json", "index.json"]
    assert json.loads((out / "index.json").read_text()) == {"z": 10, "tiles": ["506-328", "511-340"], "credits": credits}
    london = json.loads((out / "511-340.json").read_text())
    assert london["type"] == "FeatureCollection" and [f["properties"]["site_id"] for f in london["features"]] == ["A", "B"]
    assert london["features"][0] == feats[0]   # each overflow as the whole file has it


def test_every_spot_with_a_page_is_linked_from_a_page_search_engines_can_read(tmp_path):
    # Google listed the home page alone on 24 Oct 2026: the list and the map are drawn by the script, so no
    # page linked a spot's page in its HTML. spots.html links each one, and the app's foot links spots.html.
    bs = _build_site()
    spots = [{**SPOTS[0], "area": "Yorkshire"}, {**SPOTS[1], "area": "Cumbria and the Lake District"},
             {"id": "beck", "name": "A Beck & Pool", "kind": "river", "area": "Yorkshire", "days": []},
             {"id": "no-area", "name": "Somewhere", "kind": "lake", "days": []}, {**SPOTS[2], "area": "Yorkshire"}]
    assert bs.write_pages(tmp_path, spots, token="abcdefghij0123456789", root="https://example.org/swim/", day="2026-10-24") == 4
    page = (tmp_path / "spots.html").read_text()
    head = page.split("</head>")[0]
    assert "<title>Every spot · SwimSignal</title>" in head and '<link rel="canonical" href="https://example.org/swim/spots.html">' in head
    assert f'<meta name="description" content="{bs.EVERY_SPOT_DESCRIPTION}">' in head and "noindex" not in head
    assert '<header class="top">' in page and 'class="site-foot"' in page and "cloudflareinsights" in page
    assert "{{" not in page and 'href="/' not in page and "<script src=" not in page   # no script: the links are in the HTML
    main = page.split("<main", 1)[1].split("</main>")[0]
    links = re.findall(r'<a href="spot/([^"/]+)/">', main)
    assert sorted(links) == sorted(p.name for p in (tmp_path / "spot").iterdir())   # every spot with a page, once
    assert "Bad Id" not in main and "Odd" not in main   # no page of its own, so no link
    # Areas A-Z, a spot with none last; names A-Z within each, escaped.
    heads = re.findall(r'<h2 id="([^"]+)">([^<]+)</h2>', main.split("</nav>")[1])   # after the contents list
    assert heads == [("cumbria-and-the-lake-district", "Cumbria and the Lake District"), ("yorkshire", "Yorkshire"), ("other-spots", "Other spots")]
    york = main.split('<h2 id="yorkshire">')[1].split("<h2")[0]
    assert york.index("A Beck &amp; Pool") < york.index("Wharfe at &quot;Cromwheel&quot; &amp; Ilkley")
    assert '<a href="#yorkshire">Yorkshire</a>' in main and 'href="feedback.html?type=spot"' in main
    words = re.sub(r"<[^>]+>", " ", main).lower()
    assert "forecast, not a water test" in words and not re.search(r"\b(safe|clean)\b", words) and not re.search(r"\d", words)
    # Linked from the app's foot, which the home page and every spot's page carry; in the sitemap.
    for f in ("index.html", "spot/wharfe-ilkley/index.html", "spot/no-area/index.html"):
        assert '<a href="methods.html">Method</a> · <a href="spots.html">Every spot</a> · ' in (tmp_path / f).read_text(), f
    assert "<loc>https://example.org/swim/spots.html</loc>" in (tmp_path / "sitemap.xml").read_text()
    # Each spot's overflow history names its own address as canonical.
    prof = (tmp_path / "spot" / "tarn" / "profile" / "index.html").read_text().split("</head>")[0]
    assert '<link rel="canonical" href="https://example.org/swim/spot/tarn/profile/">' in prof and '<meta name="description" content="The' in prof


def test_the_note_without_scripts_names_the_issue_time_in_uk_time():
    """The built answer says "Today", "right now" and "Issued Sun 17:48" as at the issue time; a page
    read days later without scripts had only "This is the forecast as it was issued", under the five
    days (26 Oct 2026). The note names the day, date and time, in UK time either side of a clock change,
    and falls back to the old words when the time cannot be read."""
    bs = _build_site()
    q = "\u201cToday\u201d and \u201cright now\u201d mean then"
    gmt = bs.noscript_note(pd.Timestamp("2026-10-25T17:48:31+00:00"))
    assert gmt.startswith("This forecast was issued on Sunday 25 October 2026 at 17:48 UK time.") and q in gmt
    assert gmt.endswith("With JavaScript on, the page updates it and adds the map, the overflows upstream and the rest of the detail.")
    assert bs.noscript_note(pd.Timestamp("2026-07-01T23:30:00+00:00")).startswith("This forecast was issued on Thursday 2 July 2026 at 00:30 UK time.")
    assert bs.noscript_note(pd.Timestamp("2026-10-25T00:30:00Z")).startswith("This forecast was issued on Sunday 25 October 2026 at 01:30 UK time.")
    for bad in (None, pd.Timestamp("2026-10-25 17:48"), "not a time", pd.NaT):
        assert bs.noscript_note(bad) == bs.NOSCRIPT, bad


def test_the_issue_time_comes_from_the_file_the_built_answers_are_made_from(tmp_path):
    bs = _build_site()
    assert bs.built_issue_time(tmp_path) is None
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "spots.json").write_text("{}")
    assert bs.built_issue_time(tmp_path) is None
    (tmp_path / "data" / "spots.json").write_text(json.dumps({"generated_at": "2026-10-25T17:48:31+00:00"}))
    assert bs.built_issue_time(tmp_path) == pd.Timestamp("2026-10-25T17:48:31+00:00")
