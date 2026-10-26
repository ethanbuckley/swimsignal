"""Build the static site: a forecast for every spot in spots.csv and spots-osm.csv, the overflow
layer, the verification data and the pages, written to ./site for GitHub Pages.

Also refreshes live status, rebuilds the overflow table and scores logged
forecasts, so one scheduled run of this script is the whole back end.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import __version__, config
from dipcast.access import attach_access
from dipcast.algae import by_site, refresh_algae
from dipcast.forecast_log import describe_fetch, latest_samples, load_poll_log, load_verification, samples_status
from dipcast.guides import attach_guides, copy_photos
from dipcast.samples import attach_measured
from dipcast.ingest import rainfall
from dipcast.ingest.live import expected_rows, is_short
from dipcast.ingest.rainfall import cells_for_sites, fallback_summary, fetch_forecast
from dipcast.jobs import refresh_all
from dipcast.model.forecast import (
    _net,
    _overflows,
    code_commit,
    forecast_point,
    overflows_geojson,
    reload_caches,
)
from dipcast.model.spill_model import MODEL_PATH
from dipcast.model.transport import locate_pin, river_velocity, spot_hints, upstream_overflows
from dipcast.overflows import duplicate_site_ids
from dipcast.spot_links import attach as attach_spot_links
from dipcast.trace import SIMPLIFY_M, spot_trace

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("build_site")

ROOT = config.ROOT
SITE = ROOT / "site"
STATIC = ROOT / "src" / "dipcast" / "pages"
TEMPLATE = ROOT / "src" / "dipcast" / "site" / "index.html"
KEEP_CONTRIBUTORS = 10
# Open-Meteo requests a build may send, retries included, before the log warns. On 18 Oct 2026
# a build sent 19 and retried 5; the ensemble adds 7 when it refreshes.
MAX_OPEN_METEO_REQUESTS = 40
# Every overflow upstream, for data/upstream/<id>.json (write_upstream): the most within 60 km of a
# listed spot was 185 on 4 Oct 2026, at Warleigh Weir.
ALL_CONTRIBUTORS = 10_000
UPSTREAM_FIELDS = ("site_id", "site_name", "company", "receiving_watercourse", "distance_km", "lake_distance_km",
                   "travel_h", "weight", "lta_spills", "spill_hours", "has_live", "lat", "lon")
MIN_OK_SHARE = 0.8        # fewer spots with a forecast than this and the build fails (no publish)
MAX_NO_DATA_SHARE = 0.5   # more of today's forecasts without rainfall data than this: fail
# The pages link to server-style routes (/about, /static/...); rewrite them for flat files. Their
# /static/icons/ are the site's own icons at icons/ (copy_app_files), their /static/fonts/ the fonts
# at fonts/.
REWRITES = [('href="/feedback"', 'href="feedback.html"'), ('href="/feedback?type=spot"', 'href="feedback.html?type=spot"'), ('href="/verification"', 'href="verification.html"'), ('href="/terms"', 'href="terms.html"'),
            ('href="/about"', 'href="about.html"'), ('href="/testing"', 'href="testing.html"'),
            ('href="/privacy"', 'href="privacy.html"'), ('href="/terms#data"', 'href="terms.html#data"'), ('href="/"', 'href="index.html"'),
            ('href="/static/page.css"', 'href="page.css"'), ('href="/static/fonts/LICENSE.txt"', 'href="fonts/LICENSE.txt"'),
            ('href="/static/icons/icon.svg"', 'href="icons/icon.svg"'), ('href="/static/icons/apple-touch-icon.png"', 'href="icons/apple-touch-icon.png"'),
            ('href="/static/fonts/SourceSans3-latin.woff2"', 'href="fonts/SourceSans3-latin.woff2"'),
            ('href="/static/fonts/SourceSerif4-latin.woff2"', 'href="fonts/SourceSerif4-latin.woff2"'),
            ("fetch('/api/verification')", "fetch('data/verification.json')"),
            ('href="/methods"', 'href="methods.html"'), ('href="/methods#', 'href="methods.html#'),
            ('href="/verification#', 'href="verification.html#'), ('href="/coverage"', 'href="coverage.html"')]
BRAND = "SwimSignal"
# The home page leads with the name, for search; every other page is "Page · SwimSignal" (docs/DESIGN.md, Words).
HOME_TITLE = f"{BRAND} · pollution risk forecasts for swim spots"
DESCRIPTION = ("Five-day pollution risk forecasts for river and lake swim spots in England, from live sewage-overflow "
               "data, rainfall forecasts and the river network.")
SAVED_TITLE = f"Saved spots · {BRAND}"
SAVED_DESCRIPTION = "A list of river and lake swim spots, each with its five-day pollution risk forecast."
PLAN_TITLE = f"Plan a swim · {BRAND}"
PLAN_DESCRIPTION = ("Pick a day, where you are starting from and how far you will go: the river and lake swim spots "
                    "within reach, with their pollution risk forecast for that day.")
# Spot ids that get a page of their own at spot/<id>/; index.html uses the same rule. Any other
# id keeps its ?spot= address: one odd row in spots.csv must not stop the build.
SPOT_ID = re.compile(r"[A-Za-z0-9_-]+")
PAGE_META = re.compile(r"<!-- page-meta.*?<!-- /page-meta -->", re.DOTALL)
LOADING = '<div id="result"><p class="muted">Loading forecasts…</p></div>'
# index.html's, word for word: the sky for each screen (the wide one from 1,100 px, where the list,
# Saved and Plan a swim span the page), and the same pair for a spot's page, which spans it from 801 px.
SKY_PRELOAD = ('<link rel="preload" href="icons/fells.webp" as="image" fetchpriority="high" media="(max-width: 1099px)">\n'
               '<link rel="preload" href="icons/fells-wide.webp" as="image" fetchpriority="high" media="(min-width: 1100px)">')
SPOT_SKY_PRELOAD = SKY_PRELOAD.replace('1099px', '800px').replace('1100px', '801px')
# The brand mark, inline in every page's header (the static pages carry the same markup), so it needs no path.
MARK = ('<svg viewBox="0 0 512 512" aria-hidden="true"><rect width="512" height="512" fill="#0f5a61"/>'
        '<path d="M430-20C330 110 470 230 300 290S110 380 190 540" fill="none" stroke="#5CC2B5" stroke-width="70" stroke-linecap="round"/>'
        '<circle cx="318" cy="138" r="38" fill="#F08A4B"/><circle cx="165" cy="358" r="46" fill="none" stroke="#fff" stroke-width="22"/></svg>')
SITE_URL_ENV = "DIPCAST_SITE_URL"
# Optional page-view counter (Cloudflare Web Analytics). Off unless the repository
# variable is set; the token is public (it sits in the page), so it is a variable,
# not a secret. Since 5 Feb 2026 PECR (Schedule A1) lets a counter run without consent only
# if visitors get clear information and a free, simple way to object: counter.js loads it
# only for a browser that has not objected, and the home page has the button. The first
# string is the privacy notice's own lead, so the terms page's date is not touched.
COUNTER_TOKEN_ENV = "DIPCAST_CF_BEACON_TOKEN"
COUNTER_JS = TEMPLATE.parent / "counter.js"
NO_COUNTER = ("and what it does not. Last updated 20 October 2026.", "There is no analytics script and no third-party tracking.")
WITH_COUNTER = ("and what it does not. Last updated 20 October 2026 (page-view counter).",
                ("Page views are counted with Cloudflare Web Analytics. Cloudflare states that it sets no cookies, "
                 "uses no local storage and does not fingerprint visitors. It sees your IP address when the counter "
                 "loads, as any web server would, and its "
                 '<a href="https://www.cloudflare.com/privacypolicy/">privacy policy</a> applies to that. '
                 "Your visits are not counted if you choose \"Don't count my visits\" under \"Saved spots, "
                 "offline use and your data\" at the bottom of the home page; the choice is kept in your browser. "
                 "Nor are they if your browser sends Global Privacy Control or Do Not Track. "
                 "There is no other analytics or tracking."))
# Tips through Ko-fi. Off unless the repository variable is a Ko-fi page's address. When on, the
# build writes support.html, links it from every page's foot and from About, and adds to the
# privacy notice what Ko-fi passes on (its privacy policy, read 5 Oct 2026: a tip shares the
# supporter's name or username and email address with the creator, who is then a controller).
# A plain link, never Ko-fi's widget, so no page loads anything from Ko-fi. One-off tips only:
# Open-Meteo's free plan excludes sites "that have subscriptions", so no Ko-fi memberships.
SUPPORT_URL_ENV = "DIPCAST_KOFI_URL"
SUPPORT_URL = re.compile(r"https://ko-fi\.com/[A-Za-z0-9_]{1,50}/?")
SUPPORT_LINK = re.compile(r'(<footer\b(?:(?!</footer>).)*?<a href="([^"]*?)feedback\.html">Feedback</a>)', re.DOTALL)
SUPPORT_ABOUT = ('<h2>Support SwimSignal</h2>\n<p>SwimSignal is free, with no adverts. If it has helped you, you can '
                 'leave a one-off tip towards what it costs to run. A tip changes no forecast and buys nothing extra. '
                 '<a href="support.html">How to tip, and other ways to help</a>.</p>\n\n')
SUPPORT_PRIVACY = (
    '<h2 id="tips">If you leave a tip</h2>\n<p>Tips are made on Ko-fi, a separate website run by Ko-fi Labs Limited, '
    "and paid through Stripe or PayPal. What you give them is covered by Ko-fi's "
    '<a href="https://more.ko-fi.com/privacy">privacy policy</a> and the payment service\'s own. SwimSignal\'s pages '
    "send Ko-fi nothing: the support page has a plain link to Ko-fi, and loads no Ko-fi script or button.</p>\n"
    "<p>Ko-fi passes the operator your name or username, your email address and any message you write, and Stripe "
    "or PayPal show the payment's details, as they do for any payment. The operator uses these only to thank you or "
    "answer you, and to keep the records of money received that tax law requires. The basis is legitimate interests "
    "and, for the records, a legal obligation. They are never shared or sold, and never added to a mailing list. They "
    "are kept as long as tax law requires, then deleted.</p>\n\n")
# Map tiles. The OpenStreetMap Foundation's servers unless DIPCAST_TILES names another provider
# below and DIPCAST_TILE_KEY holds its key. OSM's tile policy says services "that seek donations
# should be especially aware that access may be withdrawn at any point", so move before tips go
# on. The key sits in the page, so it is a variable; lock it to the site's domain at the provider.
# Each provider's address, credit and privacy policy were read from its own pages on 5 Oct 2026:
# CARTO (carto.com/basemaps, /legal/basemap-terms: free to 5M tile requests a month for
# non-commercial use, 1M for commercial; without a key every tile says "API key required") and
# Thunderforest (/docs/map-tiles-api, /terms: Hobby plan 150,000 tiles a month). CARTO documents
# rastertiles/voyager; light_all is from its list of raster variants.
TILES_ENV, TILE_KEY_ENV = "DIPCAST_TILES", "DIPCAST_TILE_KEY"


def tile_filter(r1: str, r2: str, land: str, tint: tuple[str, str, str]) -> str:
    """The map's SVG filter (#tiles in index.html) for tiles drawn in other colours than
    OpenStreetMap's: grey land (luminance plus `land`), and water, where both alpha rows r1 and r2
    are 1, as the grey plus `tint`. Each row is the 4th row of a colour matrix (R G B A offset)."""
    lum = ".21 .7066 .0713 0"
    land_row = f"{lum} {land}"
    return ('<filter id="tiles" color-interpolation-filters="sRGB" x="0" y="0" width="1" height="1">\n'
            f'    <feColorMatrix in="SourceGraphic" type="matrix" result="r1" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  {r1}"/>\n'
            f'    <feColorMatrix in="SourceGraphic" type="matrix" result="r2" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  {r2}"/>\n'
            '    <feComposite in="r1" in2="r2" operator="arithmetic" k1="1" result="water"/>\n'
            f'    <feColorMatrix in="SourceGraphic" type="matrix" result="land" values="{land_row}  {land_row}  {land_row}  0 0 0 1 0"/>\n'
            f'    <feColorMatrix in="SourceGraphic" type="matrix" result="tint" values="{lum} {tint[0]}  {lum} {tint[1]}  {lum} {tint[2]}  0 0 0 1 0"/>\n'
            '    <feComposite in="tint" in2="water" operator="in" result="blue"/>\n'
            '    <feMerge><feMergeNode in="land"/><feMergeNode in="blue"/></feMerge>\n'
            '  </filter>')


# CARTO's colours, measured on its own tiles on 5 Oct 2026 (most common pixels, zooms 6, 7 and 10):
# Voyager land (251,248,243), water (213,232,235), parks (226,237,215); Positron land (250,250,248),
# water (212,218,220). OpenStreetMap's filter tinted Voyager's sea a third of the way and Positron's
# not at all, and left both lands white. These take each land to grey 235 and each water to the
# muted blue OpenStreetMap's water becomes, #bccfd8 (188,207,216): the grey land and blue water of
# docs/DESIGN.md. Water is where blue and green are both above red by about 10/255 (Voyager) or
# 5/255 (Positron); land, parks, roads and labels are not.
CARTO_FILTERS = {
    "voyager": tile_filter("-25 0 25 0 -1", "-30 30 0 0 -1", "-.04", ("-.147", "-.072", "-.037")),
    "positron": tile_filter("-60 0 60 0 -.8", "-80 80 0 0 -.8", "-.045", ("-.103", "-.028", ".007")),
}
TILE_FILTER = re.compile(r'<filter id="tiles".*?</filter>', re.DOTALL)
OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
_CARTO = {"name": "CARTO", "privacy": "https://carto.com/privacy/",
          "credit": OSM_ATTRIBUTION + ' contributors, &copy; <a href="https://carto.com/attribution/">CARTO</a>'}
_THUNDERFOREST = {"name": "Thunderforest", "privacy": "https://www.thunderforest.com/privacy/",
                  "credit": ('Maps &copy; <a href="https://www.thunderforest.com">Thunderforest</a>, Data &copy; '
                             '<a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>')}
TILE_PROVIDERS = {
    "osm": {"url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "credit": OSM_ATTRIBUTION,
            "name": "The OpenStreetMap Foundation", "privacy": "https://osmfoundation.org/wiki/Privacy_Policy"},
    "carto-voyager": {**_CARTO, "url": "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=__KEY__",
                      "filter": CARTO_FILTERS["voyager"]},
    "carto-positron": {**_CARTO, "url": "https://basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png?key=__KEY__",
                       "filter": CARTO_FILTERS["positron"]},
    "thunderforest-atlas": {**_THUNDERFOREST, "url": "https://api.thunderforest.com/atlas/{z}/{x}/{y}{r}.png?apikey=__KEY__"},
    "thunderforest-outdoors": {**_THUNDERFOREST, "url": "https://api.thunderforest.com/outdoors/{z}/{x}/{y}{r}.png?apikey=__KEY__"},
}
TILE_LINE = "L.tileLayer('{url}', {{ maxZoom: 19,\n  attribution: '{credit}' }})"
# The preconnect in index.html's head, for the tile host; with_tiles swaps the host, so the
# page opens the right connection early. No crossorigin: the tiles are plain images.
TILE_PRECONNECT = '<link rel="preconnect" href="{origin}">'


def tile_origin(url: str) -> str:
    """The scheme and host of a tile URL template: https://basemaps.cartocdn.com."""
    m = re.match(r"(https://[^/]+)/", url)
    if not m:
        raise ValueError(f"tile url has no https host: {url!r}")
    return m.group(1)
OSM_PRIVACY_LI = ('<li><b>The OpenStreetMap Foundation</b>, for the map images. Its '
                  '<a href="https://osmfoundation.org/wiki/Privacy_Policy">privacy policy</a> applies.</li>')
OSM_TERMS = "map tiles from the OpenStreetMap Foundation."
SUPPORT_RIGHTS = ("SwimSignal holds none, as described above;",
                  "SwimSignal holds none, as described above, apart from the details Ko-fi passes on when you leave a tip;")


def lead_skill(processed: Path = config.PROCESSED) -> dict | None:
    """How good a forecast for each day ahead has been, as a share of the same-day forecast's skill
    (Brier skill against climatology), for a picked day on a spot's page. Spills: the 2025 held-out
    test with archived rain forecasts, lead-calibrated and cross-fitted as the site runs it. Water
    quality: the leave-one-year-out replay on rivers, where the figure is shown. Held from rising
    with the days: a forecast further ahead is not better, and water quality's 0.64 at four days
    against 0.55 at three (29 Sep 2026) is noise in 907 river samples. None if the tables are
    missing."""
    try:
        leads = pd.read_csv(processed / "verification_leads_2025.csv").set_index("source")["brier_skill_vs_clim"]
        spill = [float(leads[f"forecast lead {k}, isotonic cross-fitted (odd/even months)"]) for k in range(5)]
        ev = json.loads((processed / "ecoli_model_eval.json").read_text())
        clim = next(r["brier_river"] for r in ev["loyo"] if r["model"] == "climatology by type")
        by = {r["lead"]: r["brier_river"] for r in ev["by_lead"] if r["exposure"] == "replayed exposure"}
        water = [1 - by[k] / clim for k in range(5)]
    except (OSError, KeyError, StopIteration, ValueError) as e:
        log.warning("lead skill tables unreadable, a picked day will not say how sure it is: %s", e)
        return None
    held = lambda xs: [round(min(xs[: k + 1]) / xs[0], 2) for k in range(len(xs))]
    return {"spill": held(spill), "water": held(water)}


# The test of the E. coli estimate on Welsh river samples (docs/WALES-PLAN-2026-10.md, task W10, run 10 Oct
# 2026): 185 samples at 11 stations on the Wye and the Tywi, 11 of them over 900 per 100 ml; the estimate
# averaged 32.4%, and its Brier score was worse than England's flat rate. Its summary file is not in git
# (data/processed/wales_ecoli_check.json in the main checkout), so its result is here, with where it is from.
WALES_ECOLI_TEST = {"n_samples": 185, "mean": 0.324, "observed": 0.059, "run": "2026-10-10",
                    "source": "docs/WALES-PLAN-2026-10.md, W10"}
# Shown skill on live samples: a Brier score better than the samples' own rate, and an AUC of at least this.
LIVE_SKILL_AUC = 0.6


def ecoli_check(live: dict | None = None) -> dict:
    """What a spot's page says about the E. coli estimate beside it (levels.js, ecoliNotes: shown all
    year, labelled with what is true today), for spots.json's `ecoli_check`. `live` is
    verification_live.json, as the scoring in refresh_all wrote it this build; its ecoli_live is each EA
    sample since the forecast began against the latest forecast issued before it (forecast_log.verify_ecoli).
    On 11 Oct 2026: 37 samples at 26 spots, AUC 0.52, Brier 0.107 against 0.104 for the samples' own rate,
    so no skill shown yet. The words follow the numbers each build; nothing here says how they read."""
    if live is None:
        p = config.state_read("verification_live.json")
        try:
            live = json.loads(p.read_text()) if p.exists() else None
        except (OSError, ValueError) as e:
            log.warning("verification_live.json unreadable, the E. coli label leaves out its live record: %s", e)
            live = None
    e = (live or {}).get("ecoli_live") or {}
    o = e.get("overall") or {}
    out: dict = {"wales": WALES_ECOLI_TEST}
    if e.get("n_samples") and o.get("auc") is not None and o.get("brier") is not None:
        clim = o.get("climatology_brier")
        out["live"] = {"n_samples": int(e["n_samples"]), "n_sites": e.get("n_sites"), "auc": round(float(o["auc"]), 2),
                       "brier": round(float(o["brier"]), 3), "climatology_brier": None if clim is None else round(float(clim), 3),
                       "skill": bool(clim is not None and o["brier"] < clim and o["auc"] >= LIVE_SKILL_AUC)}
    return out


# Alerts (push/): on when both repository variables are set. The Worker's address and its public
# key sit in spots.json for the page; the private key never leaves the Worker.
PUSH_URL_ENV, PUSH_KEY_ENV = "DIPCAST_PUSH_URL", "DIPCAST_VAPID_PUBLIC_KEY"
# Alerts for a date (push/README.md, "Alerts for a date"): "1" once the Worker that takes dates is
# deployed. It adds "dates": true to the push settings in spots.json, which is what shows "Alert me
# about this date" on the organisers' page; an older Worker would refuse the request.
PUSH_DATES_ENV = "DIPCAST_PUSH_DATES"
# With alerts on, the privacy notice's sentences that say nothing leaves the device, and that
# SwimSignal holds no personal data, would be untrue: each is swapped for one that is not. A test
# checks that every one is still in the notice, so a rewrite cannot leave one behind unswapped.
PUSH_SWAPS = [
    ("<li>Your saved spots, your last plan, your swim journal and your location stay on your device.</li>",
     "<li>Your location, your last plan and your swim journal stay on your device. So do your saved spots, unless you turn on alerts.</li>"),
    ("It stays on your device: it is not sent to SwimSignal or to anyone else.",
     "It stays on your device: it is not sent to SwimSignal or to anyone else, unless you turn on alerts (below)."),
    ("SwimSignal holds none, as described above;",
     "SwimSignal holds none except, if you turn on alerts, the record described under Alerts, which turning them off deletes;"),
    ('at the bottom of the home page. Clearing this site\'s data removes it too.',
     'at the bottom of the home page. Alerts need it, so turning it off turns them off too. Clearing this site\'s data removes it too.'),
]


# Email alerts (push/src/email.js, in the same Worker): on when DIPCAST_EMAIL_URL is set to the
# Worker's address, which the Saved page then posts sign-ups to. The Worker refuses them until its own
# secrets are set too (push/README.md, "Email alerts"), so set this variable last.
EMAIL_URL_ENV = "DIPCAST_EMAIL_URL"


def push_config() -> dict | None:
    url, key = (os.environ.get(PUSH_URL_ENV, "").strip(), os.environ.get(PUSH_KEY_ENV, "").strip())
    if not (url or key):
        return None
    # An https address and a 65-byte P-256 public key in base64url (87 characters, no padding).
    if not (re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d+)?/", url) and re.fullmatch(r"[A-Za-z0-9_-]{87}", key)):
        log.warning("%s must be https://host/ and %s a base64url P-256 public key: alerts left off", PUSH_URL_ENV, PUSH_KEY_ENV)
        return None
    dates = os.environ.get(PUSH_DATES_ENV, "").strip().lower()
    if dates not in ("", "0", "1", "true"):
        log.warning("%s must be 1 or unset: alerts for a date left off", PUSH_DATES_ENV)
    return {"url": url, "key": key, **({"dates": True} if dates in ("1", "true") else {})}


def email_config() -> dict | None:
    url = os.environ.get(EMAIL_URL_ENV, "").strip()
    if not url:
        return None
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d+)?/", url):
        log.warning("%s must be https://host/: email alerts left off", EMAIL_URL_ENV)
        return None
    return {"url": url}


def with_push(html: str, on: bool, email: bool = False, dates: bool = False) -> str:
    """The privacy page: the alerts section when alerts are on (in the browser, by email or both),
    else the planned-feature note. dates: alerts for a date are on too (DIPCAST_PUSH_DATES)."""
    if not (on or email):
        return html
    # An email sign-up sends the saved spots too, and its record is described under Alerts, so the
    # first three swaps hold for it. The offline copy's sentence is about browser alerts only.
    for a, b in PUSH_SWAPS if on else PUSH_SWAPS[:3]:
        html = html.replace(a, EMAIL_OFFLINE_SWAP if (email and a == PUSH_SWAPS[3][0]) else b)
    if email:
        html = html.replace(PUSH_SWAPS[0][1], PUSH_SWAPS[0][1] + "\n" + EMAIL_SHORT_LINE, 1)
    push_section = PUSH_PRIVACY
    for a, b in PUSH_DATES_SWAPS if on and dates else []:
        push_section = push_section.replace(a, b)
    section = (push_section + "\n" if on else "<h2>Alerts</h2>\n") + (EMAIL_PRIVACY if email else "")
    return re.sub(r"<h2>If alerts are added</h2>\s*<p>.*?</p>", lambda _: section.rstrip("\n"), html, count=1, flags=re.DOTALL)


PUSH_PRIVACY = (
    "<h2>Alerts</h2>\n<p>If you turn on alerts on the Saved page, your browser gives SwimSignal a push address: a "
    "long random web address, run by your browser's maker (Google, Apple, Mozilla or Microsoft), that delivers "
    "notifications to this browser. SwimSignal's alert service stores that address, with the identifiers of your "
    "saved spots and, if you tick the weekly note, that you asked for it, and nothing else: no name, email address "
    "or location. It uses them only to send a notification when one of those spots' forecast reaches high or very high "
    "risk and, if you asked, a weekly note on Thursday evenings with the days of lowest pollution risk ahead at those spots. "
    "The weekly note is "
    "off until you tick it, and unticking it stops it. Each notification passes through your browser maker's push "
    "service, encrypted so that the push service cannot read it; that company is responsible for its own service. "
    "Your browser also keeps a note of what it last sent, so that an unchanged list is sent again only about once a "
    "week. The basis is "
    "your consent: you turn alerts on, and you can turn them off on the Saved page at any time, which withdraws it. "
    "An alert can be late or not come at all, so no alert does not mean the water is clean. The record is kept "
    "until you turn alerts off, remove all your saved spots or turn off the offline copy (alerts need it), or until "
    "your browser's push service says the address no longer works; then it is deleted. The alert service runs on "
    "Cloudflare Workers, which may handle the record outside the UK under its own safeguards, and which sees your "
    "IP address when you turn alerts on or off or change your saved spots, and about once a week when you open the "
    "site, as any web server would; "
    '<a href="https://www.cloudflare.com/privacypolicy/">Cloudflare\'s privacy policy</a> applies to that.</p>')

# Alerts for a date (push/README.md, "Alerts for a date"), once DIPCAST_PUSH_DATES is set: the record
# can also hold up to 10 pairs of a spot and a date, for one more use, and is kept while it has any.
# Each "before" is in PUSH_PRIVACY (a test checks), so a rewrite cannot leave one unswapped.
PUSH_DATES_SWAPS = [
    ("saved spots and, if you tick the weekly note, that you asked for it, and nothing else",
     "saved spots, if you tick the weekly note, that you asked for it, and, if you ask on the organisers' page "
     "for alerts about a date, up to 10 pairs of a spot and a date, and nothing else"),
    ("with the days of lowest pollution risk ahead at those spots. ",
     "with the days of lowest pollution risk ahead at those spots, and, for each spot and date you asked about, a "
     "notification when that day's forecast first appears and again each time its level changes. Each spot and date "
     "is deleted once the date has passed. "),
    ("you can turn them off on the Saved page at any time, which withdraws it.",
     "you can turn them off on the Saved page at any time, which withdraws it; the alerts for a date can also be "
     "stopped on the organisers' page."),
    ("until you turn alerts off, remove all your saved spots or turn off the offline copy",
     "until you turn alerts off, remove all your saved spots and dates, or turn off the offline copy"),
    ("turn alerts on or off or change your saved spots",
     "turn alerts on or off, change your saved spots or change the dates you asked about"),
]


# With email alerts on, the privacy notice gains this section under Alerts, a line in its short
# version, and, with browser alerts on too, an offline-copy sentence that names browser alerts only.
# What the law asks, and where this section answers it (checked 4 Oct 2026, not by a lawyer):
# - UK GDPR Article 6(1)(a) and Article 7: consent as the basis, given by a clear act (the sign-up and
#   the confirmation), shown by a record (the time of confirming), and as easy to withdraw as to give
#   (one click in every email). ICO, "What is valid consent?":
#   https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/consent/what-is-valid-consent/
# - UK GDPR Articles 13 and 28: say who receives the data and why; the email service is a processor,
#   so a contract with the Article 28(3) terms is needed (Resend's DPA, part of its terms of service).
#   Articles 44-46: transfers outside the UK need safeguards (its DPA's section 6.4, the UK Addendum
#   to the EU standard contractual clauses).
# - PECR regulations 22 and 23 govern direct marketing by email. These alerts are service messages,
#   with no promotion, which the ICO says are not direct marketing ("Identify direct marketing", last
#   updated 20 August 2025:
#   https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/direct-marketing-guidance/identify-direct-marketing/).
#   They meet regulation 23 anyway: the sender is named and every email has a working way to stop them.
EMAIL_SHORT_LINE = ("<li>If you sign up for email alerts, SwimSignal keeps your email address and your list of spots "
                    "until you unsubscribe.</li>")
EMAIL_OFFLINE_SWAP = ("at the bottom of the home page. Browser alerts need it, so turning it off turns them off too; email "
                      "alerts do not. Clearing this site's data removes it too.")
EMAIL_PRIVACY = (
    '<h3 id="email-alerts">Email alerts</h3>\n'
    "<p>If you sign up for email alerts on the Saved page, your browser sends SwimSignal's alert service your email "
    "address and the identifiers of your saved spots. The service emails you a link to confirm, and sends nothing else "
    "to that address until you open the link and press Confirm. A request that is not confirmed is deleted after two "
    "days. When you confirm, the service keeps your address, the identifiers of those spots and the time you "
    "confirmed, and nothing else. It uses them only to email you when one of those spots' forecast reaches high or very "
    "high risk, at most once a day for each spot. To change the spots, you sign up again; the new list replaces the old "
    "one when you confirm it.</p>\n"
    "<p>The emails contain the forecast and nothing to sell. They carry no tracking: no images, no pixels that report "
    "when you open them, and links that go straight to this site. The basis is your consent: you sign up and confirm, "
    "and you can withdraw it at any time with the unsubscribe link in every email, or the unsubscribe button your "
    "email program may show. Either deletes your address and your list of spots at once. You can also reply to an "
    "alert or email the operator to be removed. If an email to your address cannot be delivered for good, or you "
    "mark one as spam, the email service tells the alert service, which deletes your address and your list of spots "
    "at once. An alert can be late or not come at all, so no alert does not mean the water is clean.</p>\n"
    "<p>To limit sign-ups, the service counts them for an hour under a scrambled form of your IP address, made with a "
    "secret key, and counts confirmation emails to each address for a day under a scrambled form of the address; the "
    "counts delete themselves, and the IP address itself is not stored.</p>\n"
    "<p>The emails are sent by Resend (Plus Five Five, Inc.), an email service in the United States, which acts only on "
    "SwimSignal's instructions under a data processing agreement. That agreement covers transfers from the UK with "
    "the UK's addendum to the EU standard contractual clauses. Resend keeps its record of each email it sends, "
    "including your address, for 30 days. The alert service runs on Cloudflare Workers, which may handle your address "
    "outside the UK under its own safeguards, and which sees your IP address when you sign up, confirm or "
    "unsubscribe, as any web server would. "
    '<a href="https://resend.com/legal/privacy-policy">Resend\'s privacy policy</a> and '
    '<a href="https://www.cloudflare.com/privacypolicy/">Cloudflare\'s privacy policy</a> apply to what each of them '
    "does for its own purposes.</p>\n")


def write_alerts(site: Path, root: str, push_on: bool) -> bool:
    """alerts.json beside spots.json: each spot's level and headline by the page's own rules
    (scripts/alerts.js runs levels.js in Node). Without Node the file is not written; with alerts
    on that stops them, so it is announced."""
    try:
        subprocess.run(["node", str(ROOT / "scripts" / "alerts.js"), str(site / "data" / "spots.json"),
                        str(site / "data" / "alerts.json"), root], check=True, capture_output=True, text=True, timeout=120)
        return True
    except (OSError, subprocess.SubprocessError) as e:
        msg = f"alerts.json not written ({getattr(e, 'stderr', '') or e})"
        if push_on:
            announce(msg)
        else:
            log.warning("%s", msg)
        return False


def with_counter(html: str, token: str | None) -> str:
    """Add the counter's script to a page and, on the privacy page, say so. Without a
    plausible token (16-64 letters and digits, so nothing can break out of the
    attribute) the page is returned unchanged."""
    if not token:
        return html
    if not re.fullmatch(r"[A-Za-z0-9]{16,64}", token):
        log.warning("%s is not 16-64 letters and digits: page-view counter left off", COUNTER_TOKEN_ENV)
        return html
    beacon = '<script id="page-counter">' + COUNTER_JS.read_text().replace("__TOKEN__", token) + "</script>"
    html = html.replace("</head>", beacon + "</head>", 1)
    for a, b in zip(NO_COUNTER, WITH_COUNTER):
        html = html.replace(a, b)
    return html


def tile_config() -> dict | None:
    """The map tile provider, or None for OpenStreetMap's own servers. A provider not in
    TILE_PROVIDERS, or one with no plausible key, is refused with a warning and the map stays on
    OpenStreetMap: a wrong key would draw "API key required" on every tile."""
    name = os.environ.get(TILES_ENV, "").strip().lower()
    if not name or name == "osm":
        return None
    key = os.environ.get(TILE_KEY_ENV, "").strip()
    if name not in TILE_PROVIDERS:
        log.warning("%s=%r is not one of %s: map tiles left on OpenStreetMap", TILES_ENV, name, ", ".join(TILE_PROVIDERS))
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", key):
        log.warning("%s is unset or not 8-128 letters, digits, _ and -: map tiles left on OpenStreetMap", TILE_KEY_ENV)
        return None
    p = TILE_PROVIDERS[name]
    return {**p, "id": name, "url": p["url"].replace("__KEY__", key)}


def with_tiles(html: str, name: str, tiles: dict | None) -> str:
    """Another tile provider in the app (the map's tile layer, its credit and, where the provider
    has one, its colour filter), the privacy notice
    (who gets your IP address for the map images, with "(map images)" after its date) and the
    terms' map credit. Unchanged with tiles None."""
    if not tiles:
        return html
    osm = TILE_PROVIDERS["osm"]
    if name == "index.html":
        before = TILE_LINE.format(**osm)
        if before not in html:
            raise ValueError("index.html has lost its tile layer line: build_site.TILE_LINE no longer matches it")
        html = html.replace(before, TILE_LINE.format(**tiles))
        pre = TILE_PRECONNECT.format(origin=tile_origin(osm["url"]))
        if pre not in html:
            raise ValueError("index.html has lost its tile preconnect: build_site.TILE_PRECONNECT no longer matches it")
        html = html.replace(pre, TILE_PRECONNECT.format(origin=tile_origin(tiles["url"])))
        if tiles.get("filter"):   # tuned to the provider's own colours; Thunderforest keeps OpenStreetMap's
            if not TILE_FILTER.search(html):
                raise ValueError('index.html has lost its <filter id="tiles">: build_site.TILE_FILTER no longer finds it')
            html = TILE_FILTER.sub(lambda _: tiles["filter"], html, count=1)
    if name == "privacy.html":
        html = html.replace(OSM_PRIVACY_LI, f'<li><b>{tiles["name"]}</b>, for the map images. Its '
                                            f'<a href="{tiles["privacy"]}">privacy policy</a> applies.</li>')
        html = html.replace("map images fetched from OpenStreetMap", f'map images fetched from {tiles["name"]}')
        html = privacy_updated(html, "map images")
    if name == "terms.html":
        html = html.replace(OSM_TERMS, f'map tiles from {tiles["name"]}: {tiles["credit"]}.')
    return html


def privacy_updated(html: str, what: str) -> str:
    """Say after the privacy notice's date what a setting added: "Last updated 20 October 2026
    (page-view counter, tips)"."""
    return re.sub(r"(Last updated [^.<(]*?)(?: \(([^)]*)\))?\.", lambda m: f"{m[1]} ({m[2] + ', ' if m[2] else ''}{what}).",
                  html, count=1)


def support_url() -> str | None:
    """The Ko-fi page tips go to, or None (tips off). Anything but a Ko-fi page's address is
    refused with a warning, so the variable cannot put an arbitrary link on every page."""
    url = os.environ.get(SUPPORT_URL_ENV, "").strip()
    if url and not SUPPORT_URL.fullmatch(url):
        log.warning("%s=%r is not a Ko-fi page (https://ko-fi.com/<name>): tips left off", SUPPORT_URL_ENV, url)
        return None
    return url or None


def with_support(html: str, name: str) -> str:
    """With tips on: About gains its short section and the privacy notice says what Ko-fi passes
    on, with "(tips)" after its date. Every page's foot is done separately (add_support_links)."""
    if name == "about.html":
        html = html.replace("<h2>Help test it this winter</h2>", SUPPORT_ABOUT + "<h2>Help test it this winter</h2>", 1)
    if name == "privacy.html":
        html = html.replace("<h2>The server version</h2>", SUPPORT_PRIVACY + "<h2>The server version</h2>", 1)
        html = html.replace(*SUPPORT_RIGHTS)
        html = privacy_updated(html, "tips")   # after the counter's own note, if any
    return html


def add_support_links(site: Path) -> int:
    """Put "Support SwimSignal" after Feedback in the foot of every page under site/ that has
    one, at that page's own path to the site's root. Returns the number of pages changed."""
    n = 0
    for p in site.rglob("*.html"):
        html = p.read_text()
        if "support.html\">Support SwimSignal" in html:
            continue
        new = SUPPORT_LINK.sub(lambda m: f'{m[1]} · <a href="{m[2]}support.html">Support SwimSignal</a>', html, count=1)
        if new != html:
            p.write_text(new)
            n += 1
    return n


# The spots: SwimSignal's own list, and the swim places chosen from OpenStreetMap, in a file of their
# own because the ODbL would cover any file that mixed the two (LICENSE-DATA.md). No column joins them.
SPOT_FILES = [ROOT / "spots.csv", ROOT / "spots-osm.csv"]


def load_spots(files: list[Path] | None = None) -> pd.DataFrame:
    """Every spot from spots.csv and spots-osm.csv; a file that is not there adds none. A row whose
    id an earlier row already has is left out with a warning, so two spots never share a page."""
    frames = [pd.read_csv(p) for p in (files or SPOT_FILES) if p.exists()]
    spots = pd.concat(frames, ignore_index=True).fillna("")
    dup = spots["id"].duplicated()
    for i in spots.loc[dup, "id"]:
        log.warning("spot id %r is used twice; the later row is left out", i)
    return spots[~dup].reset_index(drop=True)


def _river_of(row) -> str | None:
    """spots.csv's `river` for a river spot (the river it is on), None for a lake or a blank."""
    return spot_hints(getattr(row, "kind", ""), getattr(row, "river", ""))[1]


def prefetch_rain(spots: pd.DataFrame, ensemble: bool = True) -> None:
    """One pass over every spot's upstream overflows to collect the rainfall cells,
    then a handful of 50-cell requests. Per-spot fetching would mean up to one request
    per spot, each risking a slow TLS handshake on shared CI runners. A request that
    fails its retries does not stop the build (a 503 at 00:29 UTC on 6 Oct 2026 would
    have): fetch_forecast serves those cells' cached forecast up to a day old, or leaves
    them without rain data, and build_health reports it (fallback_summary)."""
    net, ov = _net(), _overflows()
    lat, lon = list(spots["lat"]), list(spots["lon"])
    for r in spots.itertuples(index=False):
        try:
            kind, river = spot_hints(r.kind, r.river)
            pin = locate_pin(net, float(r.lon), float(r.lat), kind_hint=kind, river_hint=river, name=r.name)
            up = upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None))
            lat += list(up["lat"]); lon += list(up["lon"])
        except Exception as e:  # noqa: BLE001
            log.warning("prefetch: %s: %s", r.name, e)
    cells = cells_for_sites(pd.Series(lat, dtype=float), pd.Series(lon, dtype=float))
    t0 = time.time()
    df = fetch_forecast(cells)
    fb = fallback_summary()
    log.info("rainfall prefetched: %d cells, %d rows, %.0fs%s", len(cells), len(df), time.time() - t0,
             f"; not fetched: {fb['stale']} from the cache, {fb['missing']} with no rain data" if fb else "")
    # The ensemble's members for the same cells, after the spots' own rain and by the
    # ensemble's own floor, cap and spare-calls rule (rainfall, "ensemble"): each spot's forecast reads them
    # from the cache, and none asks again in this build.
    if ensemble:
        t0 = time.time()
        ens = fetch_forecast(cells, ensemble=True)
        log.info("rain ensemble: %d of %d cells with members, %.0fs; %s", ens[["cell_lat", "cell_lon"]].drop_duplicates().shape[0]
                 if len(ens) else 0, len(cells), time.time() - t0, rainfall.ensemble_summary() or "all from the cache")


class BuildUnhealthy(RuntimeError):
    """Raised instead of publishing when most forecasts failed or lack data. The
    workflow's deploy job depends on the build job, so this keeps the previous
    site up rather than replacing it with a page of blanks."""


def require_spill_model(path: Path | None = None) -> None:
    """Raises BuildUnhealthy when the trained spill model file is missing. Checked before anything is
    fetched, so a build that cannot forecast spends no API calls and keeps the previous site up."""
    path = MODEL_PATH if path is None else path
    if not path.exists():
        raise BuildUnhealthy(f"no trained spill model at {path}; not publishing climatology as a forecast")


def live_feed_health(poll_log: pd.DataFrame | None) -> dict | None:
    """Rows per company in the last poll and the one before, from poll_log.parquet, the
    companies whose feed returned none in the last poll, and those whose read was short
    against their usual size before it (ingest.live.is_short). None without a poll log."""
    if poll_log is None or poll_log.empty:
        return None
    times = sorted(poll_log["fetched_at"].unique())
    rows = lambda t: {str(k): int(v) for k, v in poll_log.loc[poll_log["fetched_at"] == t].groupby("company")["n_rows"].sum().items()}
    last = rows(times[-1])
    prev = rows(times[-2]) if len(times) > 1 else {}
    usual = expected_rows(poll_log[poll_log["fetched_at"] < times[-1]])
    return {"polled_at": str(pd.Timestamp(times[-1])), "rows": last, "previous_rows": prev,
            "down": sorted(c for c, n in last.items() if n == 0),
            "short": {c: {"rows": n, "usual": usual[c]} for c, n in sorted(last.items()) if is_short(n, c, usual)}}


def snapshot_duplicates() -> list[str]:
    """Overflow ids the live snapshot lists more than once; build_overflows keeps one row of each."""
    p = config.state_read("live_latest.parquet")
    return duplicate_site_ids(pd.read_parquet(p, columns=["site_id"])) if p.exists() else []


def build_health(results: list[dict], ecoli_samples: dict | None = None, poll_log: pd.DataFrame | None = None,
                 duplicate_overflow_ids: list[str] | None = None, rain_fallback: dict | None = None) -> dict:
    """Counts the workflow and the page use to judge a build; raises BuildUnhealthy
    when the site should not be published. `ecoli_samples` is the last EA sample fetch
    (forecast_log.samples_status); if no source answered it goes in `warnings`. That
    stalls the E. coli scores, not the forecasts, so it does not stop the publish.
    `poll_log` is the live poller's log (poll_log.parquet): a company whose feed returned
    no rows in the last poll goes in `warnings` (its overflows keep their last snapshot,
    marked feed down). If every company returned none the build still publishes, with every
    overflow marked feed down and one more warning: refusing would also freeze the rain
    forecasts and leave the previous statuses on the page with no note that they are old.
    `duplicate_overflow_ids` (snapshot_duplicates) is counted, and any goes in `warnings`.
    `rain_fallback` (rainfall.fallback_summary) is the rain cells Open-Meteo did not send after its
    retries: kept as `rain_fallback` and said in `warnings`. Spots whose rain it left out show
    "rain unavailable" and count in today_rain_unavailable, under MAX_NO_DATA_SHARE."""
    n = len(results)
    # A spot the model cannot say anything about (an isolated lake, no river within
    # reach) returns an explanation with an empty day list; that is an answer, not a
    # failure. A failure is an exception in forecast_point, which leaves no `days`.
    ok = [r for r in results if "days" in r]
    with_days = [r for r in ok if r["days"]]
    today_no_data = sum(1 for r in with_days if r["days"][0].get("data_status") == "rain unavailable")
    health = {"spots": n, "forecast_ok": len(ok), "forecast_failed": n - len(ok),
              "no_forecast_possible": len(ok) - len(with_days), "today_rain_unavailable": today_no_data,
              "failed_spots": [r["name"] for r in results if "days" not in r][:20], "warnings": []}
    # One failed spot publishes without its forecast, so it goes in `warnings` as well as the log: Warleigh
    # Weir (21 Oct 2026) and Tellisford (22 Oct) failed at the clock change with green runs.
    failed = [r for r in results if "days" not in r]
    if failed:
        more = f"; and {len(failed) - 5} more" if len(failed) > 5 else ""
        health["warnings"].append(
            f"{len(failed)} spot{'' if len(failed) == 1 else 's'} published with no forecast: "
            + "; ".join(f"{r['name']} ({r.get('error', 'no days')})" for r in failed[:5]) + more)
    # Spots on the wrong water, and gauges whose latest reading is old: reported, never a reason not to publish.
    health["river_levels_stale"] = sum(bool((r.get("river_state") or {}).get("stale")) for r in results)
    misplaced = placement_check(results)
    if misplaced:
        health["placement_check"] = misplaced
        health["warnings"].append(
            f"{len(misplaced)} river spot{'' if len(misplaced) == 1 else 's'} may be on the wrong water (check spots.csv and spots-osm.csv): "
            + "; ".join(f"{m['id']}: {m['reason']}" for m in misplaced))
    if n and len(ok) < MIN_OK_SHARE * n:
        raise BuildUnhealthy(f"only {len(ok)}/{n} spots got a forecast; not publishing")
    if with_days and today_no_data > MAX_NO_DATA_SHARE * len(with_days):
        raise BuildUnhealthy(f"{today_no_data}/{len(ok)} forecasts have no rainfall data for today; not publishing")
    # An overflow listed twice failed four forecasts on 3 Oct 2026; build_overflows drops it, and it is
    # counted here.
    dups = list(duplicate_overflow_ids or [])
    health["duplicate_overflow_ids"] = len(dups)
    if dups:
        more = f" and {len(dups) - 10} more" if len(dups) > 10 else ""
        health["warnings"].append(f"the live snapshot lists {len(dups)} overflow id{'' if len(dups) == 1 else 's'} more than once "
                                  f"({', '.join(dups[:10])}{more}); build_overflows keeps the most recent row of each")
    if rain_fallback:
        fb = rain_fallback
        health["rain_fallback"] = fb
        why = f" ({'; '.join(fb['errors'])})" if fb.get("errors") else ""
        health["warnings"].append(
            f"Open-Meteo did not send the rain forecast for {fb['cells']} cell{'' if fb['cells'] == 1 else 's'} after retrying{why}: "
            f"{fb['stale']} used a cached forecast up to {fb['oldest_stale_h']:g} h old, and {fb['missing']} had none under a day old, "
            "so the overflows there show no data")
    feeds = live_feed_health(poll_log)
    if feeds:
        health["live_feeds"] = feeds
        if feeds["rows"] and len(feeds["down"]) == len(feeds["rows"]):
            health["warnings"].append(f"no live overflow feed returned any rows at {feeds['polled_at']}; "
                                      "published with every overflow's last snapshot marked feed down")
        for c in feeds["down"]:
            before = feeds["previous_rows"].get(c)
            health["warnings"].append(f"{c}'s live overflow feed returned no rows at {feeds['polled_at']} "
                                      f"(previous poll: {'no record' if before is None else before} rows); "
                                      "its overflows show their last snapshot, marked feed down")
        for c, n in feeds["short"].items():
            health["warnings"].append(f"{c}'s live overflow feed returned {n['rows']} rows at {feeds['polled_at']}, where it "
                                      f"usually has {n['usual']:.0f}, after reading again; the missing overflows show their "
                                      "last snapshot, marked feed down")
    if ecoli_samples:
        s = ecoli_samples
        health["ecoli_samples"] = {k: s.get(k) for k in ("checked_at", "n_sites", "n_failed", "last_ok_at", "sources")}
        if s.get("all_failed"):
            health["warnings"].append(f"E. coli scoring stalled: no EA source answered for any of the {s.get('n_sites')} "
                                      f"bathing waters at {s.get('checked_at')} ({describe_fetch(s)}); "
                                      f"last good fetch {s.get('last_ok_at') or 'never'}")
    return health


MAX_SNAP_M = 250.0   # a river spot further than this from its snapped link is probably misplaced
UNSURE_JOIN_M = 200.0     # an outfall this far from the line it was snapped to joins its river somewhere unknown
UNSURE_MARGIN_M = 300.0   # ...and could join below a spot this much nearer than that distance


NEAR_SPOT_M = 50.0   # an overflow this close to a spot's pin is at the spot: it should be counted


def near_uncounted(results: list[dict], upstream: dict[str, list[dict]], ov: pd.DataFrame) -> list[dict]:
    """Overflows within NEAR_SPOT_M of a spot's pin that the trace did not count. Positions are good to
    tens of metres, and a swim spot is a stretch of water, so an outfall at the spot should count
    whichever side of the pin its snap fell. Wetherby High Street CSO was 5 m from the Wharfe at
    Wilderness Carpark bathing water, snapped onto a stub joining 43 m below it (11 Oct 2026).
    Settle each one in data/raw/overflow_joins.csv. A row there is settled either way, so it is not
    listed: Knaresborough's Abbey Mill CSO is placed 29 m below the Lido and kept uncounted, per the
    EA's profile."""
    from dipcast.network.rivers import lonlat_to_bng
    if ov is None or ov.empty:
        return []
    settled = ov["position_source"].eq("join") if "position_source" in ov else pd.Series(False, index=ov.index)
    snapped = ov[ov["link_id"].notna() & ov["lat"].notna() & ~settled]
    ox, oy = lonlat_to_bng(snapped["lon"].to_numpy(), snapped["lat"].to_numpy())
    out = []
    for r in results:
        if r.get("lat") is None or r.get("lon") is None:
            continue
        x, y = lonlat_to_bng(r["lon"], r["lat"])
        d = np.hypot(np.asarray(ox) - x, np.asarray(oy) - y)
        counted = {c.get("site_id") for c in upstream.get(r["id"], [])}
        for i in np.flatnonzero(d <= NEAR_SPOT_M):
            sid = snapped["site_id"].iloc[i]
            if sid not in counted:
                out.append({"spot": r["id"], "site_id": sid, "metres": round(float(d[i]))})
    return out


def unsure_joins(upstream: dict[str, list[dict]]) -> list[dict]:
    """Counted overflows whose join with the river could be on the other side of the spot: snapped from
    UNSURE_JOIN_M or more, onto a link that does not carry its receiving water's name, and nearer the spot
    along the river than that snap distance plus UNSURE_MARGIN_M. Such an outfall is on a stream OS Open
    Rivers does not draw, and where that stream meets the river is not known. Rochester Road CSO was
    709 m from the Rivelin and counted 0.7 km above its plunge pool; its stream, Black Brook, joins
    241 m below it (11 Oct 2026). Settle each one in data/raw/overflow_joins.csv."""
    out = []
    for sid, contrib in upstream.items():
        for c in contrib:
            snap = c.get("snap_m")
            if snap is None or snap < UNSURE_JOIN_M or c.get("position_source") == "join" or c.get("on_named"):
                continue
            if c.get("distance_km") is None or c["distance_km"] * 1000 > snap + UNSURE_MARGIN_M:
                continue
            out.append({"spot": sid, "site_id": c.get("site_id"), "snap_m": snap,
                        "km": c["distance_km"], "receiving": c.get("receiving_watercourse")})
    return out


def placement_check(results: list[dict], max_snap_m: float = MAX_SNAP_M) -> list[dict]:
    """River spots whose snapped watercourse does not share a word with spots.csv's `river` (after
    the Welsh aliases), or that sit more than `max_snap_m` from it. Such a spot is traced up the
    wrong water: on 2 Oct 2026 six were on a side beck and showed no overflows upstream. A spot
    moved to a mapped main channel from a side channel it sits on (adopted_main_channel) is
    judged by name only, since its distance is the side channel's offset by design."""
    from dipcast.network.names import same_river
    out = []
    for r in results:
        if r.get("kind") != "river" or str(r.get("error") or "").startswith("forecast failed"):
            continue
        loc = r.get("location") or {}
        river, wc, d = (r.get("river") or None), loc.get("watercourse"), loc.get("snap_distance_m")
        reasons = []
        if not river:
            reasons.append(f"no river named in {'spots-osm.csv' if r.get('source') == 'openstreetmap' else 'spots.csv'}")
        elif not same_river(wc, river):
            reasons.append(f"snapped to {wc or 'an unnamed watercourse'}, not the {river}")
        if d is not None and d > max_snap_m and not loc.get("adopted_main_channel"):
            reasons.append(f"{d:.0f} m from the river network")
        if loc.get("mode") not in (None, "river"):
            reasons.append(f"placed as a {loc.get('mode')}")
        elif loc.get("form") not in (None, "inlandRiver", "tidalRiver"):
            reasons.append(f"snapped to a {loc.get('form')} link")
        if reasons:
            out.append({"id": r.get("id"), "river": river, "watercourse": wc, "snap_distance_m": d,
                        "reason": ", ".join(reasons)})
    return out


def attach_algae(results: list[dict], fetch: bool = True) -> int:
    """The EA sampler's latest visual algae check, and this season's tally, on each
    bathing-water spot (spot id 'bw-' + the EA id). Returns how many spots got one; a
    failure leaves the spots without it rather than failing the build."""
    try:
        checks = by_site(refresh_algae(fetch=fetch))
    except Exception as e:  # noqa: BLE001 - an observation beside the forecast must not sink the site
        log.warning("algae checks: %s", e)
        return 0
    n = 0
    for r in results:
        c = checks.get(str(r["id"]).removeprefix("bw-")) if str(r["id"]).startswith("bw-") else None
        if c:
            r["algae"] = c
            n += 1
    return n


def attach_lab_samples(results: list[dict], samples: dict | None = None) -> int | None:
    """The latest E. coli lab sample on each bathing-water spot (spot id 'bw-' + the EA id), for the
    page's "What the level rests on": the samples the live scoring already holds
    (forecast_log.latest_samples), so no request is made. A bathing water with none in the file gets
    None ("no lab sample this season"); without a readable file no spot gets the field, and the page
    says the sample is not in this forecast's data. Returns how many spots got one, None without a file."""
    samples = latest_samples() if samples is None else samples
    if samples is None:
        return None
    n = 0
    for r in results:
        if str(r["id"]).startswith("bw-"):
            r["lab_sample"] = samples.get(str(r["id"]).removeprefix("bw-"))
            n += r["lab_sample"] is not None
    return n


# The credits every published data file carries. A credit has to travel with republished data:
# CC BY 4.0 s.3(a) and s.4 for the water companies' feeds, OGL v3 for the EA and OS. The full
# notices are on the terms page ("Data sources and credits"), which the "full" link points to.
LICENCES = {
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "OGL v3.0": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
    "ODbL 1.0": "https://opendatacommons.org/licenses/odbl/1-0/",
}
# For the spots in spots-osm.csv (source "openstreetmap"). ODbL 4.3 asks for a notice wherever the
# data, or a work made from it, is shown; the terms page carries the same line.
OSM_CREDIT = ("Swim spot locations from OpenStreetMap, © OpenStreetMap contributors, ODbL 1.0 "
              '(https://www.openstreetmap.org/copyright): the spots whose source is "openstreetmap".')


# Each company's name in the data (config.LIVE_FEEDS) and as its licence credits it, as the terms page names it.
# Dwr Cymru Welsh Water is not here: SwimSignal reuses none of its data yet, only the EA's annual returns.
CREDITED_COMPANIES = {
    "Anglian Water": "Anglian Water Services", "Northumbrian Water": "Northumbrian Water",
    "Severn Trent Water": "Severn Trent Water", "South West Water": "South West Water",
    "Southern Water": "Southern Water (© 2026 Southern Water)", "Thames Water": "Thames Water",
    "United Utilities": "United Utilities", "Wessex Water": "Wessex Water (© 2024 Wessex Water)",
    "Yorkshire Water": "Yorkshire Water",
}
# The credits one source at a time, for the pages that are printed (the decision record and the sites view,
# docs/ORGANISER-PIVOT-2026-10.md): each page shows the ones its spots use (`use`), each with its licence
# and what SwimSignal changed, since CC BY 4.0 s.3(a)(1)(B) and OGL v3 ask a reuser to say so. "{companies}"
# is the companies upstream of the page's spots, by their CREDITED_COMPANIES names. `use`: "overflows" where a
# credited company's overflows are upstream, "always", "rain" where the spot has a daily rain forecast, "gauge"
# where it shows a river level or flood alerts, "model" where any overflow is upstream (the models were trained
# on ERA5-Land), "lake" where water crosses a lake on its way to the spot, "osm" for a spot from OpenStreetMap.
CREDIT_SOURCES = [
    {"use": "overflows", "credit": "Storm overflow status from {companies}, via the National Storm Overflow Hub, and "
     "overflow identifiers from the Stream ID lookup, via Stream", "licence": "CC BY 4.0",
     "changed": "SwimSignal combined, matched and modelled them."},
    {"use": "always", "credit": "Environment Agency data © Environment Agency copyright and/or database right", "licence": "OGL v3.0",
     "changed": "SwimSignal used it in its forecast."},
    {"use": "gauge", "credit": "This uses Environment Agency flood and river level data from the real-time data API (Beta)",
     "licence": "OGL v3.0", "changed": "SwimSignal picks the nearest gauge."},
    {"use": "always", "credit": "Contains OS data © Crown copyright and database right 2026", "licence": "OGL v3.0",
     "changed": "SwimSignal traced the rivers on OS Open Rivers."},
    {"use": "rain", "credit": "Weather data by Open-Meteo.com", "licence": "CC BY 4.0",
     "changed": "SwimSignal adds up the rain and models it."},
    {"use": "rain", "credit": "Met Office data © Crown copyright, served by Open-Meteo", "licence": "CC BY-SA 4.0",
     "changed": "SwimSignal models it; its rainfall figures stay under CC BY-SA 4.0."},
    {"use": "model", "credit": "Contains modified Copernicus Climate Change Service information 2026 (ERA5-Land). "
     "Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains",
     "licence": "", "changed": "SwimSignal trained its models on it."},
    {"use": "lake", "credit": "Lake residence times from HydroLAKES v1.0 (Messager et al. 2016, Nature Communications 7: 13603)",
     "licence": "CC BY 4.0", "changed": "SwimSignal matched the lakes and shortened the times for spill-day flows."},
    {"use": "osm", "credit": "Swim spot location © OpenStreetMap contributors, openstreetmap.org/copyright", "licence": "ODbL 1.0",
     "changed": "SwimSignal picked the spot from it."},
]


def data_credits(root: str) -> dict:
    return {
        "attribution": (
            "Storm overflow status from Anglian Water Services, Northumbrian Water, Severn Trent Water, South West Water, "
            "Southern Water (© 2026), Thames Water, United Utilities, Wessex Water (© 2024) and Yorkshire Water, via the "
            "National Storm Overflow Hub, CC BY 4.0; overflow identifiers matched with the Stream ID lookup, via Stream, "
            "CC BY 4.0. Environment Agency data © Environment Agency copyright and/or "
            "database right, OGL v3.0; river levels: this uses Environment Agency flood and river level data from the "
            "real-time data API (Beta). Contains OS data © Crown copyright and database right 2026. Weather data by "
            "Open-Meteo.com, CC BY 4.0, from Met Office forecasts © Crown copyright, CC BY-SA 4.0: rainfall figures "
            "stay under CC BY-SA 4.0. Lake residence times from HydroLAKES v1.0 (Messager et al. 2016, Nature "
            "Communications 7: 13603), CC BY 4.0. The models were trained on ERA5-Land reanalysis (doi:10.24381/cds.e2161bac): "
            "contains modified Copernicus "
            "Climate Change Service information 2026; neither the European Commission nor ECMWF is responsible for any "
            "use that may be made of the Copernicus information or data it contains."),
        "modified": ("Combined, filtered and modelled by SwimSignal. The forecasts, levels and scores are SwimSignal's own "
                     "estimates, not the data providers'. None of the providers endorses SwimSignal."),
        "spot_locations": OSM_CREDIT,
        "sources": CREDIT_SOURCES,   # one a line, each saying what SwimSignal changed, so the printed pages close with this alone:
        "endorsement": "None of the providers endorses SwimSignal.",
        "companies": CREDITED_COMPANIES,
        "licences": LICENCES,
        "full": f"{root}terms.html#data",
    }


def attach_companies(results: list[dict], upstream: dict[str, list[dict]]) -> None:
    """The water companies with overflows upstream of each spot, all of them (upstream holds every
    contributor, the spot only its first KEEP_CONTRIBUTORS), as upstream_summary.companies, and whether
    any of their sewage crosses a lake on the way (through_lake: HydroLAKES' residence times). The sites
    view reads spots-lite.json, which has no contributors, and credits each source by name (data_credits)."""
    for r in results:
        if not isinstance(r.get("upstream_summary"), dict):
            continue
        ups = upstream.get(r["id"], [])
        r["upstream_summary"]["companies"] = sorted({str(c["company"]) for c in ups if c.get("company")})
        r["upstream_summary"]["through_lake"] = any((c.get("lake_distance_km") or 0) > 0 for c in ups)


def scored_csv_header(credits: dict, root: str) -> str:
    """The comment lines above data/verification_live.csv: what a row is, the columns, where the
    rules are, and the credits, since the observed column is the water companies' data (CC BY 4.0)."""
    lic = "; ".join(f"{k} {v}" for k, v in credits["licences"].items())
    lines = [
        "SwimSignal live verification: one row per scored forecast (overflow, day and lead), the rows behind the live scores on the",
        f"Accuracy page ({root}verification.html#live-scoring). The row count is n_scored in data/verification.json.",
        "Columns: overflow_id, the water company's id for the overflow, as in its live feed; company; day, the target",
        "day (Europe/London); lead, days from the issue day to the target day (0 is the same day); issued_at, when",
        "the scored forecast was issued (the latest one by 08:00 local time on the issue day); forecast_raw, the",
        "spill probability before lead calibration; forecast_calibrated, after it (as the map uses it); climatology,",
        "the overflow's long-run daily spill rate from the Environment Agency annual returns (the baseline);",
        "observed, 1 if the live feed showed the overflow discharging that day, else 0.",
        f"Scoring rules and method: {root}methods.html",
        "Lines that start with # are notes: skip them when reading (pandas: comment='#'; R: comment.char='#').",
        f"Credits: {credits['attribution']}",
        credits["modified"],
        f"Licences: {lic}. Full credits: {credits['full']}",
    ]
    return "".join(f"# {x}\n" for x in lines)


def publish_scored_csv(site: Path, credits: dict, root: str) -> int | None:
    """data/verification_live.csv: the live scorer's rows (forecast_log.SCORED_CSV in the state
    directory) under a header comment with the credits. Published only when its row count equals
    n_scored in the verification.json this build has just written; otherwise any old copy is removed,
    live.scored_csv is dropped from that verification.json and the build warns, so the page never
    links to rows that disagree with its scores, or to no file. Returns the
    number of rows published, or None."""
    from dipcast.forecast_log import SCORED_CSV
    dst = site / "data" / "verification_live.csv"
    ver = site / "data" / "verification.json"
    live = json.loads(ver.read_text()).get("live") or {}
    src = config.state_read(SCORED_CSV)

    def withdraw():
        # The Accuracy page links the file whenever live.scored_csv is set, so drop it with the file.
        dst.unlink(missing_ok=True)
        if live.get("scored_csv"):
            d = json.loads(ver.read_text())
            d["live"].pop("scored_csv", None)
            ver.write_text(json.dumps(d, default=str))

    if not live.get("scored_csv") or not src.exists():
        withdraw()
        log.info("no scored rows to publish: the live scorer has not written %s yet", SCORED_CSV)
        return None
    body = src.read_text()
    n = max(body.count("\n") - 1, 0)   # rows after the column names; no field holds a line break
    if n != live.get("n_scored", 0):
        withdraw()
        announce(f"{SCORED_CSV} has {n} rows but the live scores count {live.get('n_scored', 0)}: not published")
        return None
    dst.write_text(scored_csv_header(credits, root) + body)
    return n


def spots_csv_header(credits: dict, root: str) -> str:
    """The comment lines above data/verification_spots_live.csv (docs/PREREGISTRATION-2027.md, amendment 1, file D):
    what a row is, the columns, and the credits, since the observed column is built from the water companies' data."""
    lic = "; ".join(f"{k} {v}" for k, v in credits["licences"].items())
    lines = [
        "SwimSignal live verification of the spot level: one row per spot with a monitored overflow upstream, target day and lead",
        f"0-4, the rows behind \"How the level itself has done\" on the Accuracy page ({root}verification.html#spot-level).",
        "Columns: spot_id, the spot's id on the site; day, the target day (Europe/London); lead, days from the issue day to the",
        "target day (0 is the same day); issued_at, when the forecast was issued (the latest by 08:00 local time on the issue",
        "day); forecast, the spot's sewage spill exposure index as logged; observed, the same index with the spills that",
        "happened in place of the forecast ones: 1 - prod(1 - w x e) over the overflows, w each overflow's weight in that",
        "forecast and e its observed spill days moved later by its logged travel time, empty when not observed; climatology,",
        "the same index from each overflow's long-run spill rate for the month (the reference); covered, the share of the spot's weight",
        "whose overflows were observed on every day that reaches the target day (observed needs 0.95); reason, why there is",
        "no observation, else empty; version, the forecast's model stamp. Empty issued_at, forecast and version: no forecast",
        "by 08:00 on the issue day. Values have 6 decimal places, and the Accuracy page's figures are computed from them as",
        "written. A level is the site's: the value rounded to 3 places, times 100, rounded half up; Low risk under 15,",
        "Moderate risk from 15, High risk from 40, Very high risk from 70.",
        f"Pre-registered rules: https://github.com/ethanbuckley/swimsignal/blob/main/docs/PREREGISTRATION-2027.md (amendment 1). Method: {root}methods.html",
        "Lines that start with # are notes: skip them when reading (pandas: comment='#'; R: comment.char='#').",
        f"Credits: {credits['attribution']}",
        credits["modified"],
        f"Licences: {lic}. Full credits: {credits['full']}",
    ]
    return "".join(f"# {x}\n" for x in lines)


def publish_spots_csv(site: Path, credits: dict, root: str) -> int | None:
    """data/verification_spots_live.csv: the spot-level rows (forecast_log.SPOTS_CSV in the state directory) under a
    header comment with the credits. Published only when its row count equals live.spots_live.csv.rows in the
    verification.json this build has just written; otherwise any old copy is removed and the page's link with it,
    as publish_scored_csv does. Returns the number of rows published, or None."""
    from dipcast.forecast_log import SPOTS_CSV
    dst = site / "data" / SPOTS_CSV
    ver = site / "data" / "verification.json"
    spots = (json.loads(ver.read_text()).get("live") or {}).get("spots_live") or {}
    src = config.state_read(SPOTS_CSV)

    def withdraw():
        dst.unlink(missing_ok=True)
        if spots.get("csv"):
            d = json.loads(ver.read_text())
            d["live"]["spots_live"].pop("csv", None)
            ver.write_text(json.dumps(d, default=str))

    if not spots.get("csv") or not src.exists():
        withdraw()
        log.info("no spot-level rows to publish: the live scorer has not written %s yet", SPOTS_CSV)
        return None
    body = src.read_text()
    n = max(body.count("\n") - 1, 0)   # rows after the column names; no field holds a line break
    if n != spots["csv"].get("rows"):
        withdraw()
        announce(f"{SPOTS_CSV} has {n} rows but the spot-level scores count {spots['csv'].get('rows')}: not published")
        return None
    dst.write_text(spots_csv_header(credits, root) + body)
    return n


CLASSIFICATIONS = config.RAW / "bathing_water_classifications.json"


def attach_classifications(results: list[dict], path: Path = CLASSIFICATIONS) -> int:
    """The EA's latest classification of each bathing-water spot (spot id 'bw-' + the EA id), from
    the file scripts/fetch_classifications.py writes, and the address of the EA's page for it.
    Returns how many spots got a classification. A missing or unreadable file leaves every spot
    without: the forecast stands without it, and the page then shows no rating."""
    try:
        sites = json.loads(path.read_text())["sites"]
    except Exception as e:  # noqa: BLE001 - a record beside the forecast must not sink the build
        log.warning("bathing-water classifications: %s", e)
        return 0
    n = 0
    for r in results:
        c = sites.get(str(r["id"]).removeprefix("bw-")) if str(r["id"]).startswith("bw-") else None
        if c:
            r["classification"] = {k: c[k] for k in ("class", "year", "history", "url") if k in c}
            n += "class" in c
    return n


RNAGS = config.RAW / "rnags.json"
FARM_PRESSURE = ("Agriculture and rural land management", "Pollution from rural areas")


def attach_water_body(results: list[dict], path: Path = RNAGS) -> tuple[int, list[str]] | None:
    """Each spot's Environment Agency water body, and whether the Environment Agency lists agriculture and
    rural land management as a confirmed or probable reason it does not reach good status, under "Pollution
    from rural areas", for the page's "What the level rests on" (evidence.js, evidenceRunoff): `water_body`
    {id, name, agriculture?}. Both come from data/raw/rnags.json, which scripts/make_rnags.py writes off CI
    from the Catchment Data Explorer and which places every listed spot in its water body, so no request is
    made. A spot the file places nowhere (a tributary it does not name, a lake under 50 ha), or in a water
    body it lists no reasons for, gets no field. Returns (how many spots got one, the ids of the spots the
    file does not know: added since it was made), or None without a readable file, when no spot gets one."""
    try:
        doc = json.loads(path.read_text())
        spots, bodies = doc["spots"], doc["water_bodies"]
    except Exception as e:  # noqa: BLE001 - a record beside the forecast must not sink the build
        log.warning("reasons for not achieving good status: %s", e)
        return None
    n, unknown = 0, []
    for r in results:
        if r["id"] not in spots:
            unknown.append(r["id"])
            continue
        at = spots[r["id"]]
        b = bodies.get(at["id"]) if at else None
        if b is None or r.get("error"):
            continue
        farm = [p["certainty"] for p in b["pressures"] if (p["sector"], p["issue"]) == FARM_PRESSURE]
        r["water_body"] = {"id": at["id"], "name": b["name"],
                           **({"agriculture": min(farm, key=("confirmed", "probable").index)} if farm else {})}
        n += 1
    return n, unknown


UPGRADES = config.RAW / "overflow_upgrades.csv"
UPGRADE_STAGES = ("upgraded", "upgrading")
UPGRADE_MATCHES = ("name", "shared name")


def read_upgrades(path: Path = UPGRADES) -> dict[str, dict]:
    """data/raw/overflow_upgrades.csv by site id: the upgrades a company says it has made or is making,
    each with its source. Raises ValueError on a row the page could not word truthfully: an unknown stage
    or match, a source that is not https, no quote, a date not YYYY-MM-DD, or an overflow listed twice."""
    import csv
    rows = list(csv.DictReader(line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")))
    out: dict[str, dict] = {}
    day = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for r in rows:
        sid = (r.get("site_id") or "").strip()
        bad = ("no site_id" if not sid else "listed twice" if sid in out
               else f"stage {r.get('stage')!r}" if r.get("stage") not in UPGRADE_STAGES
               else f"match {r.get('match')!r}" if r.get("match") not in UPGRADE_MATCHES
               else "source_url not https" if not re.fullmatch(r"https://[^\s<>\"']+", r.get("source_url") or "")
               else "no quote" if not (r.get("quote") or "").strip()
               else "no company" if not (r.get("company") or "").strip()
               else "checked not YYYY-MM-DD" if not day.match(r.get("checked") or "")
               else "completed not YYYY-MM-DD" if r.get("completed") and not day.match(r["completed"])
               else "")
        if bad:
            raise ValueError(f"{path.name}: {sid or 'a row'}: {bad}")
        out[sid] = r
    return out


def latest_return_years(path: Path = config.PROCESSED / "annual_returns.parquet") -> dict[str, int]:
    """Each overflow's annual-return year whose counts the forecast reads, by the forecast's own rule
    (overflows.latest_annual_returns), for the note's "spill counts for 2020 to ..."."""
    from dipcast.overflows import latest_annual_returns
    a = latest_annual_returns(pd.read_parquet(path))
    return {str(s): int(y) for s, y in zip(a["site_id"], a["ar_year"]) if pd.notna(y)}


def attach_upgrades(results: list[dict], path: Path = UPGRADES, years: dict[str, int] | None = None) -> dict:
    """A note's facts on each listed overflow in a spot's list, as `upgrade` on its row in contributors:
    the company's words (has upgraded / is upgrading), the source and the day it was read, and the last
    return year the forecast still counts. Runs after the forecasts, and the spill model never reads the
    file: an announced upgrade is a target, not a measurement, and the model's response to its count
    covariate is not monotone, so the page says what the company says and leaves the forecast as it is.
    A row whose company is not the overflow's is passed over and named in the warnings, as a wrong
    site id would be. Never stops the build: a bad file leaves every page without the note."""
    try:
        listed = read_upgrades(path)
    except Exception as e:  # noqa: BLE001 - a note beside the forecast must not sink the build
        return {"overflows": 0, "spots": 0, "warnings": [f"overflow upgrades not shown: {e}"]}
    if years is None:
        try:
            years = latest_return_years()
        except Exception as e:  # noqa: BLE001 - without the year the note says "past spill counts"
            log.warning("annual-return years for the upgrade notes: %s", e)
            years = {}
    seen, spots, warnings = set(), 0, []
    for r in results:
        hit = False
        for c in r.get("contributors") or []:
            u = listed.get(c.get("site_id"))
            if u is None:
                continue
            if u["company"] != c.get("company"):
                msg = f"{u['site_id']} is {c.get('company')}'s, not {u['company']}'s: no upgrade note for it ({path.name})"
                if msg not in warnings:
                    warnings.append(msg)
                continue
            c["upgrade"] = {"company": u["company"], "stage": u["stage"], "match": u["match"], "source_name": u["source_name"],
                            "url": u["source_url"], "checked": u["checked"],
                            **({"completed": u["completed"]} if u.get("completed") else {}),
                            **({"returns_to": years[u["site_id"]]} if u["site_id"] in years else {})}
            seen.add(u["site_id"])
            hit = True
        spots += hit
    return {"overflows": len(seen), "spots": spots, "warnings": warnings}


DRY_WEATHER = config.RAW / "dry_weather_spills.csv"


def read_dry_weather(path: Path = DRY_WEATHER) -> dict[str, dict]:
    """data/raw/dry_weather_spills.csv (scripts/make_dry_weather_spills.py) by site id: each overflow's dry
    spill-days and dry days in one year. Raises ValueError on a file the note could not word truthfully: more
    than one year, a count that is not a whole number, more dry spill-days than dry days, or an overflow listed
    twice."""
    import csv
    rows = list(csv.DictReader(line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")))
    out: dict[str, dict] = {}
    years = {r.get("year") for r in rows}
    if len(years) > 1:
        raise ValueError(f"{path.name}: more than one year ({', '.join(sorted(map(str, years)))})")
    for r in rows:
        sid = (r.get("site_id") or "").strip()
        try:
            year, k, n = int(r["year"]), int(r["dry_spill_days"]), int(r["dry_days"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"{path.name}: {sid or 'a row'}: a count or the year is not a whole number") from None
        bad = ("no site_id" if not sid else "listed twice" if sid in out else "no company" if not (r.get("company") or "").strip()
               else "more dry spill-days than dry days" if not 0 <= k <= n else "")
        if bad:
            raise ValueError(f"{path.name}: {sid or 'a row'}: {bad}")
        out[sid] = {"company": r["company"], "year": year, "days": k, "dry_days": n}
    return out


def attach_dry_weather(results: list[dict], path: Path = DRY_WEATHER) -> dict:
    """`dry_weather` ({year, days, dry_days}) on each overflow in a spot's list that spilled on many of its dry days
    in the file's year, by the rule tested in docs/DRY-WEATHER-SPILLS-TEST-2026-10.md (dry_weather.noted). The page
    says it beside the overflow in the test's wording (index.html, dryWeatherNote). Runs after the forecasts, and the
    spill model never reads the file: the test found the history adds nothing to the forecast, so it is a record of
    the past, not a risk. A row whose company is not the overflow's is passed over and named in the warnings, as a
    wrong site id would be. Never stops the build: a bad file leaves every page without the note."""
    from dipcast.dry_weather import noted
    try:
        listed = read_dry_weather(path)
    except Exception as e:  # noqa: BLE001 - a note beside the forecast must not sink the build
        return {"overflows": 0, "spots": 0, "warnings": [f"dry-weather spills not shown: {e}"]}
    seen, spots, warnings = set(), 0, []
    for r in results:
        hit = False
        for c in r.get("contributors") or []:
            d = listed.get(c.get("site_id"))
            if d is None or not noted(d["days"], d["dry_days"]):
                continue
            if d["company"] != c.get("company"):
                msg = f"{c['site_id']} is {c.get('company')}'s, not {d['company']}'s: no dry-weather note for it ({path.name})"
                if msg not in warnings:
                    warnings.append(msg)
                continue
            c["dry_weather"] = {"year": d["year"], "days": d["days"], "dry_days": d["dry_days"]}
            seen.add(c["site_id"])
            hit = True
        spots += hit
    return {"overflows": len(seen), "spots": spots, "warnings": warnings}


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = math.pi / 180
    h = math.sin((lat2 - lat1) * r / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin((lon2 - lon1) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


RIVER_WORD = re.compile(r"\b(river|afon|beck|brook|burn|stream|cut|gill|ghyll|canal|ditch|dyke)\b", re.IGNORECASE)


def lake_gauge(r: dict, state: dict | None) -> dict | None:
    """The gauge reading a spot keeps. A lake keeps only a gauge on the lake itself, marked `water`
    "lake", whose page words it as a lake level (index.html, riverTile); a gauge on another water is
    dropped. On 11 Oct 2026 Loughrigg Tarn showed the River Brathay's level, the Serpentine the Wandle's,
    eight km away, and Windermere's "0.73 m, High water" sat inside its usual 0.23 to 1.00 m with "A high
    river runs faster": a river's level says nothing about a lake's water, and the river words do not fit
    a lake's own. On the lake: its name shares a word with the lake's, as same_river reads them, and has
    no river word (the River Derwent at Portinscale shares "Derwent" with Derwent Water but is the river
    below it). A river spot keeps its gauge."""
    if state is None or not (r.get("kind") == "lake" or (r.get("location") or {}).get("mode") in ("lake", "isolated")):
        return state
    from dipcast.network.names import same_river
    lake = (r.get("location") or {}).get("watercourse") or r.get("name")
    gauge = state.get("river") or ""
    if RIVER_WORD.search(gauge) or not (same_river(lake, gauge) or same_river(r.get("name"), gauge)):
        return None
    return {**state, "same_river": True, "water": "lake"}


def attach_river_levels(results: list[dict], lookup=None, workers: int = 8, now=None) -> int:
    """The Environment Agency's nearest level gauge, on the spot's own river where it has one, as
    an observation beside the forecast: the latest level, the gauge's usual range and a word for
    where the level sits. The forecast itself is unchanged (forecast_point runs with gauge=False):
    gauge=True would scale travel speed by the level; the site only shows it. By default the readings
    come in one request for every gauge and each spot's gauge is kept for a week (flows.level_lookup),
    so the build asks the EA a few times rather than three times a spot. The spot's own river
    is spots.csv's `river`, else the snapped watercourse. A "latest" reading over
    flows.MAX_READING_AGE_H old is not the level now (Salisbury's was 708 h old on 2 Oct 2026): it
    is kept as `last_level_m` with `stale: true` and its age, and `level_m`, `index` and `label`
    become None and `label` "unknown" (flows.reading_fields), so it is never shown as the current level. Returns how many spots got a
    current reading; a failure leaves a spot without, and nothing here can stop a build."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import UTC, datetime

    from dipcast.ingest.flows import MAX_READING_AGE_H, level_lookup, reading_fields
    from dipcast.network.names import same_river
    save = None
    if lookup is None:   # every reading in one request, each spot's gauge kept a week (flows.level_lookup)
        lookup, save = level_lookup(config.CACHE / "ea_level_stations.json")
    now = now or datetime.now(UTC)

    def one(r: dict) -> dict | None:
        if r.get("error") and str(r["error"]).startswith("forecast failed"):
            return None
        river = r.get("river") or (r.get("location") or {}).get("watercourse")
        try:
            st = lookup(r["lat"], r["lon"], 15, river)
        except Exception as e:  # noqa: BLE001 - an observation beside the forecast must not sink the build
            log.warning("river level for %s: %s", r["name"], e)
            return None
        if st is None or st.level_m is None:
            return None
        return {**reading_fields(st, now, MAX_READING_AGE_H), "rloi": st.rloi, "measure": st.measure,
                "distance_km": round(_km(r["lat"], r["lon"], st.lat, st.lon), 1),
                "same_river": same_river(river, st.river) if river else None}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        states = list(pool.map(one, results))
    if save:
        try:
            save()
        except OSError as e:
            log.warning("river level gauges not kept for the next build: %s", e)
    n = 0
    for r, s in zip(results, states, strict=True):
        r["river_state"] = lake_gauge(r, s)   # a lake keeps only a gauge on itself
        n += r["river_state"] is not None and not r["river_state"]["stale"]
    return n


def asked_now(ask):
    """Ask now and answer later: a function returning ask()'s answer, or raising its error. The build
    asks for the national flood list before the river levels, whose requests the EA's gateway has
    answered with HTTP 403 by the time the flood list came last (3 Oct 2026)."""
    try:
        answer = ask()
    except Exception as e:  # noqa: BLE001 - re-raised where the answer is used
        error = e

        def again():
            raise error
        return again
    return lambda: answer


# The EA's flood requests sometimes time out: on 16 Oct 2026 (21:03 build) the national list
# answered and then 48 of the 105 spots' own requests timed out at 4 s, so 48 pages said "not
# checked". A failed request is asked once more FLOOD_RETRY_S later, and every answer is in within
# FLOOD_BUDGET_S, so a slow EA adds at most half a minute to the national list and to the spots'.
FLOOD_RETRY_S = 20.0
FLOOD_BUDGET_S = 30.0


def ask_flood_list(ask=None, sleep=time.sleep, clock=time.monotonic) -> bool:
    """The national flood list (flows.floods_in_force_anywhere), with one retry: if the first ask
    fails, the second begins FLOOD_RETRY_S after the first began, and each is allowed what is left
    of FLOOD_BUDGET_S (10 s each, against flows.EA_TIMEOUT_S's 4 s). Raises the second failure."""
    if ask is None:
        from dipcast.ingest.flows import floods_in_force_anywhere as ask
    start = clock()
    try:
        return ask(timeout=FLOOD_BUDGET_S - FLOOD_RETRY_S)
    except Exception as e:  # noqa: BLE001 - asked again; the second failure is raised
        log.info("flood list: %s; asking again", e)
    sleep(max(0.0, start + FLOOD_RETRY_S - clock()))
    return ask(timeout=max(1.0, start + FLOOD_BUDGET_S - clock()))


def attach_flow_state(results: list[dict], trend=None, alerts=None, any_alerts=None, workers: int = 8, now=None,
                      sleep=time.sleep, clock=time.monotonic, outline=None, lake_at=None) -> dict:
    """"Too high to swim", beside the pollution level and never part of it: a high river and a flood
    are a different hazard. After attach_river_levels, each spot gets `flow_state`, a word from the
    gauge on its own river (flows.flow_state: "high" above the usual range, "rising fast" up more
    than a fifth of that range in the last six hours, else None), and `flood_alerts`, the
    Environment Agency's flood alerts and warnings in force whose area covers the spot's water, the
    most severe first ([] for none, None if the EA did not answer). The EA's 10 km is not measured to
    the area's outline, so each area's outline is read (flood_outlines: cached by area id, else one
    request) and an alert is the spot's only when it covers the spot's point on its water, or its
    lake (flows.split_flood_alerts, `lake_at` for the lake outlines); `flood_alerts_other` counts those
    for other water and `flood_alerts_unmatched` those that could not be matched to it (None when
    unchecked). The alerts are asked for spot by spot only when the
    national list has one in force (flows.floods_in_force_anywhere): on most days one request, not
    one a spot. The rise is fetched only where it could set the word, a current reading on the
    spot's own river not already above its range, from the last 24 readings, and kept in
    `river_state` as `rise_6h_m` with the times it runs between. A stale reading has no index
    (reading_fields), so it is never "high". The spots whose flood request failed are asked once
    more, FLOOD_RETRY_S after the first round, all within FLOOD_BUDGET_S of its end; those still
    unanswered keep None. Returns counts for the build log; nothing here can stop a build or
    change a level."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import UTC, datetime

    from dipcast.ingest import flows
    trend = trend or flows.recent_levels
    alerts = alerts or flows.flood_alerts
    any_alerts = any_alerts or (lambda: ask_flood_list(sleep=sleep, clock=clock))
    now = now or datetime.now(UTC)
    try:
        ask = any_alerts()
    except Exception as e:  # noqa: BLE001 - an observation beside the forecast must not sink the build
        log.warning("flood alerts: %s", e)
        ask = None   # unchecked: asking 89 times more would not help a service that refused once
    if not ask:
        alerts = (lambda lat, lon: []) if ask is False else None

    def one(r: dict) -> tuple[str | None, dict | None, list | None]:
        rs, rise = r.get("river_state"), None
        index, rng = None, None
        # A lake's gauge matches on the lake's name (Windermere at Far Sawrey) or on a beck or river
        # that shares a word with it (Derwent Water and the River Derwent): never a "River" word.
        own = bool(rs) and rs.get("same_river") is True and r.get("kind") != "lake"
        if rs and not rs.get("stale") and rs.get("level_m") is not None:
            lo, hi = rs.get("typical_low_m"), rs.get("typical_high_m")
            if lo is not None and hi is not None and hi > lo:
                rng = hi - lo
                index = (rs["level_m"] - lo) / rng   # unrounded: the published index is rounded to 0.01
            if own and rs.get("measure") and rng and index <= flows.HIGH_INDEX:
                try:
                    rise = flows.rise_over_window(trend(rs["measure"]), now)
                except Exception as e:  # noqa: BLE001 - an observation beside the forecast must not sink the build
                    log.warning("river trend for %s: %s", r["name"], e)
        word = flows.flow_state(index, own, rise["rise_m"] / rng if rise and rng else None)
        found = None
        if alerts is not None:
            try:
                found = alerts(r["lat"], r["lon"])
            except Exception as e:  # noqa: BLE001
                log.info("flood alerts for %s: %s; asking again", r["name"], e)
        return word, rise, found

    with ThreadPoolExecutor(max_workers=workers) as pool:
        out = list(pool.map(one, results))
    failed = [i for i, (_, _, found) in enumerate(out) if found is None] if alerts is not None else []
    if failed:
        log.info("flood alerts: %d of %d spots not answered; asking again in %.0f s", len(failed), len(results), FLOOD_RETRY_S)
        sleep(FLOOD_RETRY_S)
        deadline = clock() + FLOOD_BUDGET_S - FLOOD_RETRY_S

        def again(i: int) -> list | None:
            r, left = results[i], deadline - clock()
            if left < 1:   # out of time: unchecked, as before the retry
                log.warning("flood alerts for %s: no time left to ask again", r["name"])
                return None
            try:
                return alerts(r["lat"], r["lon"], timeout=left)
            except Exception as e:  # noqa: BLE001
                log.warning("flood alerts for %s: %s", r["name"], e)
                return None

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for i, found in zip(failed, pool.map(again, failed), strict=True):
                out[i] = (*out[i][:2], found)
    shapes = flood_outlines({a.get("area_id") for _, _, found in out for a in found or [] if isinstance(a, dict)},
                            outline, workers, clock) if any(found for _, _, found in out) else {}
    lake_at = lake_at or lake_outline_at
    counts = {"river_high": 0, "river_rising_fast": 0, "flood_alerts": 0, "flood_alerts_unchecked": 0,
              "flood_alerts_other_water": 0, "flood_alerts_unmatched": 0}
    for r, (word, rise, found) in zip(results, out, strict=True):
        spot = own_water(r, lake_at) if found else own_water(r, None)
        r["flood_alerts"], r["flood_alerts_other"], r["flood_alerts_unmatched"] = flows.split_flood_alerts(found, spot, shapes)
        r["flow_state"], found = word, r["flood_alerts"]
        if rise and r.get("river_state"):
            r["river_state"].update(rise_6h_m=rise["rise_m"], rise_from=rise["from"], rise_to=rise["to"])
        counts["river_high"] += word == "high"
        counts["river_rising_fast"] += word == "rising fast"
        counts["flood_alerts"] += bool(found)
        counts["flood_alerts_unchecked"] += found is None
        counts["flood_alerts_other_water"] += bool(r["flood_alerts_other"])
        counts["flood_alerts_unmatched"] += bool(r["flood_alerts_unmatched"])
    counts["flood_outlines"] = sum(v is not None for v in shapes.values())
    counts["flood_outlines_missing"] = sum(v is None for v in shapes.values())
    return counts


def flood_outlines(area_ids: set, outline=None, workers: int = 8, clock=time.monotonic) -> dict:
    """Each in-force area's outline (flows.flood_area_outline: from the cache by area id, or asked
    for once, one GET per area not already kept), all within FLOOD_BUDGET_S. An area with no outline
    by then, or whose outline failed, maps to None: its alerts are never named (rule 4)."""
    from concurrent.futures import ThreadPoolExecutor

    from dipcast.ingest import flows
    outline = outline or (lambda aid, timeout: flows.flood_area_outline(aid, config.CACHE / "flood_areas", timeout))
    ids = sorted(a for a in area_ids if a)
    deadline = clock() + FLOOD_BUDGET_S

    def one(aid: str):
        left = deadline - clock()
        if left < 1:
            log.warning("flood outline %s: no time left", aid)
            return None
        try:
            return outline(aid, min(left, FLOOD_BUDGET_S - FLOOD_RETRY_S))
        except Exception as e:  # noqa: BLE001 - a missing outline is rule 4, not a failed build
            log.warning("flood outline %s: %s", aid, e)
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip(ids, pool.map(one, ids), strict=True))


_LAKES = None


def lake_outline_at(x: float, y: float):
    """The WFD lake outline (data/processed/lakes.parquet, British National Grid) that the point lies
    in, else None. Read from the file only, never fetched: no file is no lake outline."""
    global _LAKES
    from shapely.geometry import Point

    from dipcast.ingest import lakes
    if _LAKES is None:
        try:
            import geopandas as gpd
            _LAKES = gpd.read_parquet(lakes.PATH) if lakes.PATH.exists() else False
        except Exception as e:  # noqa: BLE001 - no lake outlines is the rule's lake-without-outline case
            log.warning("lake outlines: %s", e)
            _LAKES = False
    if _LAKES is False or _LAKES is None or _LAKES.empty:
        return None
    pt = Point(x, y)
    hit = _LAKES.iloc[_LAKES.sindex.query(pt, predicate="intersects")]
    return hit.geometry.iloc[0] if len(hit) else None


def own_water(r: dict, lake_at=None):
    """The spot's own water for its flood alerts (flows.SpotWater). Its names, from its river and the
    watercourse it was placed on, and for a lake with no watercourse its name before the first comma
    ("Blea Tarn, Langdale"): whole names (flows.water_names) and, for a river, short ones
    (flows.short_water_names). Whether it is a lake, and on tidal water (placed on a tidal river, or of
    a kind that is neither a river nor a lake). Its point on its water (location.snapped, else the
    pin) and its pin, in British National Grid. For a lake, the lake outline that point lies in
    (`lake_at`, lake_outline_at in the build). snap_distance_m is not used."""
    from dipcast.ingest import flows
    loc = r.get("location") if isinstance(r.get("location"), dict) else {}
    lake = r.get("kind") == "lake"
    names = [r.get("river"), loc.get("watercourse")]
    if lake and not loc.get("watercourse"):
        names.append(str(r.get("name") or "").split(",")[0])
    tidal = loc.get("form") == "tidalRiver" or r.get("kind") not in (None, "", "river", "lake")
    pin = flows.bng(r.get("lat"), r.get("lon"))
    snapped = loc.get("snapped") if isinstance(loc.get("snapped"), dict) else {}
    point = flows.bng(snapped.get("lat"), snapped.get("lon")) or pin
    lake_outline = lake_at(*point) if lake and lake_at and point else None
    return flows.SpotWater(flows.water_names(*names), frozenset() if lake else flows.short_water_names(*names),
                           lake, tidal, point, pin, lake_outline)


WEATHER_CREDIT = "Weather data by Open-Meteo.com"
# The weather's refresh floor. Asked for in every build, it would be 105 calls a build, 5,040 a day at a
# build every 30 minutes. A daily high, sunrise and sunset change little in 3 hours.
WEATHER_REFRESH_H = 3.0
WEATHER_CACHE = "weather.json"


def _weather_key(r: dict) -> str:
    return f"{r['lat']:.3f},{r['lon']:.3f}"


def attach_weather(results: list[dict], request=None, batch: int = 50, cache: Path | None = None,
                   refresh_h: float = WEATHER_REFRESH_H) -> int:
    """Each spot's daytime high, sunrise and sunset for the forecast's days, from Open-Meteo in a
    few calls for all spots (three daily variables over five days weigh one call per location).
    Context beside the forecast, not an input to it. The answers are kept in `cache` (in the rain
    cache, so they persist with the state) and used again while under `refresh_h` old and from the
    same Europe/London day, so only spots not in it are asked for; the day's Open-Meteo ration
    (rainfall.may_spend) can hold the request back. A failed or held call leaves a spot with what
    the cache has from today, or without."""
    from dipcast.ingest import rainfall
    request = request or rainfall._request
    cache = cache or rainfall.CACHE / WEATHER_CACHE
    spots = [r for r in results if not (r.get("error") and str(r["error"]).startswith("forecast failed"))]
    today = pd.Timestamp.now(tz="Europe/London").strftime("%Y-%m-%d")
    try:
        stored = json.loads(cache.read_text())
        stored = stored if isinstance(stored, dict) and stored.get("day") == today else {}
    except (OSError, ValueError):
        stored = {}
    known = stored.get("points") or {}
    fresh = bool(known) and time.time() - float(stored.get("fetched_at", 0)) < refresh_h * 3600
    todo = [r for r in spots if not (fresh and _weather_key(r) in known)]
    got = {}
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        weight = rainfall.call_weight(len(chunk), config.FORECAST_DAYS, variables=3)
        if not rainfall.may_spend(weight, "weather"):
            break
        try:
            res = request(config.OPEN_METEO_FORECAST, {
                "latitude": ",".join(f"{r['lat']:.3f}" for r in chunk), "longitude": ",".join(f"{r['lon']:.3f}" for r in chunk),
                "daily": "temperature_2m_max,sunrise,sunset", "forecast_days": config.FORECAST_DAYS, "timezone": "Europe/London"}, timeout=30)
        except Exception as e:  # noqa: BLE001 - context beside the forecast must not sink the build
            if isinstance(e, rainfall.OpenMeteoBadBody):
                rainfall.spend(weight, "weather")
            log.warning("weather: %s", e)
            break
        rainfall.spend(weight, "weather")
        for r, w in zip(chunk, res if isinstance(res, list) else [res], strict=False):
            got[_weather_key(r)] = (w or {}).get("daily") or {}
    if got:
        # Spots added to a fresh set keep its time, so the whole set is asked for again together.
        keep = {**known, **got} if fresh else got
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"day": today, "fetched_at": stored.get("fetched_at") if fresh else time.time(),
                                         "points": keep}))
        except OSError as e:
            log.warning("weather cache not written: %s", e)
    n = 0
    for r in spots:
        d = got.get(_weather_key(r)) or known.get(_weather_key(r))
        if d is None:
            continue
        try:
            days = [{"date": t, "tmax": None if x is None else round(float(x)), "sunrise": str(sr)[11:16], "sunset": str(ss)[11:16]}
                    for t, x, sr, ss in zip(d["time"], d["temperature_2m_max"], d["sunrise"], d["sunset"], strict=True)]
        except (KeyError, TypeError, ValueError) as e:
            log.warning("weather for %s: %s", r["name"], e)
            continue
        r["weather"] = {"days": days, "credit": WEATHER_CREDIT}
        n += 1
    return n


def attach_water_temperature(results: list[dict], fetch=None, relate=None, now=None, max_km: float = 15.0) -> int:
    """Beside attach_river_levels: the latest reading of an Environment Agency water-temperature sensor
    within `max_km` (straight line) on a river spot's own river (`same_river` on spots.csv's `river`,
    else the snapped watercourse), with the distance, whether it is upstream or downstream and how far
    along the river, and when it was read. The nearest upstream sensor is taken before any downstream
    one: the water at the spot comes from upstream, while a downstream sensor reads water that has
    passed it, perhaps at a tidal barrage (Cattawade, below Dedham, read 2 °C warmer than Boxted Mill
    above it on 3 Oct 2026). With none upstream, the nearest downstream. Two Hydrology API requests for the whole build
    (water_temperature.fetch_sensors); only readings under flows.MAX_READING_AGE_H old count, so a spot
    whose nearest sensor has gone quiet gets the next one, or nothing. `relate(spot, sensor)` gives
    (direction, km along the river), or None where the network does not join the two or only one is
    tidal (water_temperature.river_relation); such a sensor is passed over for the next. Never an
    estimate: a spot with no sensor gets no `water_temp`, and lakes get none, since a river sensor is
    not the lake's water. Returns how many spots got one; nothing here can stop a build."""
    from dipcast.ingest.water_temperature import fetch_sensors, river_relation, sensors_on_river
    try:
        sensors = (fetch or fetch_sensors)(now)
    except Exception as e:  # noqa: BLE001 - an observation beside the forecast must not sink the build
        log.warning("water temperature: %s", e)
        return 0
    relate = relate or (lambda r, s: river_relation(_net(), r["lat"], r["lon"], r.get("river"), s))
    rivers = [r for r in results if r.get("kind") == "river" and not str(r.get("error") or "").startswith("forecast failed")]
    n = 0
    for r in rivers:
        river = r.get("river") or (r.get("location") or {}).get("watercourse")
        chosen = None
        for s, km in sensors_on_river(sensors, r["lat"], r["lon"], river, max_km):
            try:
                rel = relate(r, s)
            except Exception as e:  # noqa: BLE001 - a sensor the network cannot place is not shown
                log.warning("water temperature for %s at %s: %s", r["name"], s.station_id, e)
                rel = None
            if rel is None:
                continue
            if chosen is None or rel[0] == "upstream":
                chosen = (s, km, rel)
            if rel[0] == "upstream":
                break
        if chosen is None:
            continue
        s, km, rel = chosen
        r["water_temp"] = {"temp_c": s.temp_c, "observed_at": s.observed_at, "age_hours": s.age_hours,
                           "quality": s.quality, "station": s.place, "where": s.where, "river": s.river,
                           "station_id": s.station_id, "url": s.url, "distance_km": round(km, 1),
                           "direction": rel[0], "river_km": rel[1]}
        n += 1
    log.info("water temperature: %d of %d river spots have an EA sensor on their river within %.0f km "
             "(%d sensors read in the last day)", n, len(rivers), max_km, len(sensors))
    return n


# What the offline copy (sw.js) stores, or decides what it stores: the files whose hash names its
# cache. A file here changes, and so does sw.js, so browsers install the new worker and fill a new
# cache from the server; nothing else (the forecast, a spot's page) changes the name. Directories
# count whole.
SHELL_SOURCES = [TEMPLATE, TEMPLATE.parent / "sw.js", TEMPLATE.parent / "levels.js", TEMPLATE.parent / "experience.js",
                 TEMPLATE.parent / "manifest.webmanifest", TEMPLATE.parent / "icons", TEMPLATE.parent / "vendor",
                 STATIC / "page.css", STATIC / "feedback.html", STATIC / "fonts",
                 TEMPLATE.parent / "anypoint.js"]
# The worker's build line, and the page's scripts, which get ?v=<stamp> so a page and its scripts
# always come from one build (sw.js explains). The page must keep these exact tags.
SW_BUILD = "const BUILD = 'dev';"
VERSIONED_SCRIPTS = ('<script src="experience.js"></script>', '<script src="levels.js"></script>',
                     '<script src="anypoint.js" defer></script>')


def shell_stamp() -> str:
    """Eight hex digits of a hash over the shell's source files, their paths and their bytes."""
    h = hashlib.sha256()
    for src in SHELL_SOURCES:
        for f in sorted(src.rglob("*")) if src.is_dir() else [src]:
            if f.is_file() and f.name != ".DS_Store":
                h.update(str(f.relative_to(ROOT)).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()[:8]


def with_build(template: str, stamp: str) -> str:
    """The app page with its scripts asked for at ?v=<stamp>, as the worker stores them."""
    for tag in VERSIONED_SCRIPTS:
        if tag not in template:
            raise ValueError(f"index.html has lost {tag}, which the offline copy versions")
        template = template.replace(tag, tag.replace('.js"', f'.js?v={stamp}"'), 1)
    return template


# Swimmers' reviews (src/dipcast/reviews.py): the page's reviews.js is stored and versioned as the
# scripts above are.
SHELL_SOURCES.append(TEMPLATE.parent / "reviews.js")
VERSIONED_SCRIPTS += ('<script src="reviews.js"></script>',)
SHELL_SOURCES.append(TEMPLATE.parent / "visits.js")   # and the notes on a visit, which use it
VERSIONED_SCRIPTS += ('<script src="visits.js"></script>',)
SHELL_SOURCES.append(TEMPLATE.parent / "illness.js")   # and the reports of illness, which use it too
VERSIONED_SCRIPTS += ('<script src="illness.js"></script>',)
# Practical guides (src/dipcast/guides.py): guide.js draws a spot's guide, which the app reads from data/spot/<id>.json (write_app_data).
SHELL_SOURCES.append(TEMPLATE.parent / "guide.js")
VERSIONED_SCRIPTS += ('<script src="guide.js"></script>',)
# Plan a swim (plan/): its rules, plan.js, likewise. The places it starts from are data, fetched the
# first time one is typed (PLACES, below).
SHELL_SOURCES.append(TEMPLATE.parent / "plan.js")
VERSIONED_SCRIPTS += ('<script src="plan.js"></script>',)
# Since you last looked: since.js, what changed at a saved spot since this browser last showed it.
SHELL_SOURCES.append(TEMPLATE.parent / "since.js")
VERSIONED_SCRIPTS += ('<script src="since.js"></script>',)
# Named lists of saved spots, and the links that share a list or a plan (saved/): lists.js, likewise.
SHELL_SOURCES.append(TEMPLATE.parent / "lists.js")
VERSIONED_SCRIPTS += ('<script src="lists.js"></script>',)
# What the level rests on: evidence.js draws a spot's evidence, with its ages and sources, from spots.json.
SHELL_SOURCES.append(TEMPLATE.parent / "evidence.js")
VERSIONED_SCRIPTS += ('<script src="evidence.js"></script>',)
# How the forecast has done here: spotscores.js draws it from data/spot_scores.json (src/dipcast/spot_scores.py).
SHELL_SOURCES.append(TEMPLATE.parent / "spotscores.js")
VERSIONED_SCRIPTS += ('<script src="spotscores.js"></script>',)
# Today's EA advice: eatoday.js, the fold that loads the EA's own panel in the reader's browser (no build request).
SHELL_SOURCES.append(TEMPLATE.parent / "eatoday.js")
VERSIONED_SCRIPTS += ('<script src="eatoday.js"></script>',)
# The swim journal (journal.js): kept on the device, so its script is stored and versioned as the rest.
SHELL_SOURCES.append(TEMPLATE.parent / "journal.js")
VERSIONED_SCRIPTS += ('<script src="journal.js"></script>',)
# Lab results an organisation sent (src/dipcast/samples.py, samples/README.md): measured.js draws a spot's,
# which the app reads from data/spot/<id>.json as it does the guide (DETAIL_FIELDS).
SHELL_SOURCES.append(TEMPLATE.parent / "measured.js")
VERSIONED_SCRIPTS += ('<script src="measured.js"></script>',)


def copy_app_files(site: Path, stamp: str | None = None) -> None:
    """The web-app manifest and icons beside index.html: Add to Home Screen then gives an
    icon, a name and a full-screen window. The offline copy, sw.js, gets the build's stamp."""
    stamp = stamp or shell_stamp()
    shutil.copy(TEMPLATE.parent / "manifest.webmanifest", site / "manifest.webmanifest")
    sw = (TEMPLATE.parent / "sw.js").read_text()
    if sw.count(SW_BUILD) != 1:
        raise ValueError(f"sw.js has lost its line {SW_BUILD!r}, which the build stamps")
    (site / "sw.js").write_text(sw.replace(SW_BUILD, f"const BUILD = '{stamp}';"))   # the offline copy; see the file
    shutil.copy(TEMPLATE.parent / "experience.js", site / "experience.js")
    shutil.copy(TEMPLATE.parent / "reviews.js", site / "reviews.js")   # swimmers' reviews (src/dipcast/reviews.py)
    shutil.copy(TEMPLATE.parent / "visits.js", site / "visits.js")   # quick notes on a visit, beside them
    shutil.copy(TEMPLATE.parent / "illness.js", site / "illness.js")   # reports of illness after a swim, as counts
    shutil.copy(TEMPLATE.parent / "guide.js", site / "guide.js")   # practical guides (src/dipcast/guides.py)
    shutil.copy(TEMPLATE.parent / "levels.js", site / "levels.js")   # the level rules, which the page loads
    shutil.copy(TEMPLATE.parent / "anypoint.js", site / "anypoint.js")   # a forecast for any point clicked on the map
    shutil.copy(TEMPLATE.parent / "plan.js", site / "plan.js")   # Plan a swim
    shutil.copy(TEMPLATE.parent / "since.js", site / "since.js")   # what changed since you last looked
    shutil.copy(TEMPLATE.parent / "lists.js", site / "lists.js")   # named lists of saved spots
    shutil.copy(TEMPLATE.parent / "evidence.js", site / "evidence.js")   # what the level rests on
    shutil.copy(TEMPLATE.parent / "spotscores.js", site / "spotscores.js")   # how the forecast has done here
    shutil.copy(TEMPLATE.parent / "eatoday.js", site / "eatoday.js")   # today's EA advice, the EA's own panel
    shutil.copy(TEMPLATE.parent / "journal.js", site / "journal.js")   # the swim journal, on the device only
    shutil.copy(TEMPLATE.parent / "measured.js", site / "measured.js")   # lab results an organisation sent (samples/)
    shutil.copytree(TEMPLATE.parent / "icons", site / "icons", dirs_exist_ok=True)
    # The map library, Leaflet, served from this site (vendor/leaflet/VERSION.txt) rather than a CDN.
    shutil.copytree(TEMPLATE.parent / "vendor", site / "vendor", dirs_exist_ok=True)


def site_url() -> str:
    """The published address, for canonical links, share previews and the sitemap. A custom
    domain sets DIPCAST_SITE_URL; otherwise it is this repository's GitHub Pages address, so a
    fork or a renamed repository gets its own."""
    url = os.environ.get(SITE_URL_ENV, "").strip()
    if url and not re.match(r"https?://[^/\s]+", url):   # "swimsignal.co.uk" would make every preview link relative
        log.warning("%s=%r is not an http(s) address; using the Pages address", SITE_URL_ENV, url)
        url = ""
    if not url:
        owner, _, repo = os.environ.get("GITHUB_REPOSITORY", "ethanbuckley/swimsignal").partition("/")
        # A repository named <owner>.github.io is that account's own site, served at the root.
        home = f"{owner.lower()}.github.io"
        url = f"https://{home}/" if repo.lower() == home else f"https://{home}/{repo}/"
    return url.rstrip("/") + "/"


def page_meta(title: str, description: str, url: str, root: str, base: str | None = None, noindex: bool = False,
              image: tuple[str, str] | None = None, feed: tuple[str, str] | None = None) -> str:
    """The <head> block index.html marks with page-meta. Messaging apps and search engines need
    absolute addresses for the page and its preview image. Every page gets a relative <base> at
    the site root ("./" on the home page, "../../" in spot/<id>/). The page moves between the list
    and spots with pushState, and without a <base> every relative link would then resolve inside
    spot/<id>/; a <base> is resolved once, as the page loads. Relative, so the pages work at any
    address (a custom domain serves the site at / rather than /dipcast/). image: a picture of the page's
    own and its description, (path from the site root, alt), in place of the shared icons/og.png. feed: the
    page's Atom feed, (path from the site root, title), so a feed reader given the page finds it."""
    src, alt = image or ("icons/og.png", f"{BRAND}: pollution risk forecasts for river and lake swim spots")
    return "\n".join([
        *([f'<base href="{escape(base)}">'] if base else []),
        f"<title>{escape(title)}</title>",
        f'<meta name="description" content="{escape(description)}">',
        *(['<meta name="robots" content="noindex">'] if noindex else []),
        f'<link rel="canonical" href="{escape(url)}">',
        *([f'<link rel="alternate" type="application/atom+xml" title="{escape(feed[1])}" href="{escape(root + feed[0])}">'] if feed else []),
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{escape(BRAND)}">',
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        f'<meta property="og:url" content="{escape(url)}">',
        f'<meta property="og:image" content="{escape(root + src)}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{escape(alt)}">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def spot_blurb(spot: dict) -> str:
    """One sentence for a spot's search result and link preview. It leaves out today's level:
    messaging apps keep a preview for days, and a level in it would go stale."""
    name, kind = spot["name"], "lake" if spot.get("kind") == "lake" else "river"
    n = (spot.get("upstream_summary") or {}).get("overflows")
    if spot.get("error") and not str(spot["error"]).startswith("forecast failed"):
        return f"{name}: no monitored storm overflow found upstream of this {kind} on the river network, so {BRAND} has no spill forecast for it."
    if n == 0:   # not "no sewage risk", which reads as no risk at all
        return (f"{name}: no monitored storm overflow found within {config.MAX_UPSTREAM_KM:g} km upstream, so {BRAND} has no spill "
                "forecast for it. Other risks apply: algae, wildlife, runoff and bathers.")
    upstream = f" from the {n} monitored storm overflow{'' if n == 1 else 's'} upstream," if n else ""
    return (f"Five-day pollution risk forecast for {name},{upstream} using live overflow status, rainfall forecasts "
            f"and the river network. Updated several times a day.")


# The opening of each view, written into the built page so that its words and the picture behind them
# (the ::before of .lead and .answer, index.html) paint before data/spots.json arrives. That picture is
# the largest thing on a phone's first screen, so page-speed scores time the first load by it: drawn
# only by the script, it came 4.3 s into a slow 4G load (5 Oct 2026). The stand-in must be no taller
# than what the script draws, or the picture would sit lower and paint larger when it arrives, and that
# later paint would count instead; so it holds only what does not depend on the forecast.
SEARCH_ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
               'aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/></svg>')   # index.html's
# Near me, under the search (index.html's NEAR_CTA, word for word). The line for groups is at the
# foot of the list, so the opening ends with the row of controls.
NEAR_CTA = ('<button type="button" class="btn primary near-cta" data-near-cta><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/></svg><span class="cta-l">Show spots near me</span><span class="cta-s">Near me</span></button>')
# Under it, the forecast for the water where you are (index.html's HERE_CTA, word for word).
HERE_CTA = '<button type="button" class="linkbtn here-cta" data-here-cta>Or check the river or lake where you are</button>'
# Under the opening, the first tile's place in hairline grey, so that nothing but the opening's words
# sits on the picture (docs/DESIGN.md, the sky and the glass) and the page does not jump when it comes.
SKELETON_TILE = '<div class="skel tile" aria-hidden="true">' + '<span class="skel-r"></span>' * 4 + '</div>'


def home_lead(n: int) -> str:
    """The list's opening as index.html's renderList draws it, down to the row of controls, for n spots,
    then the list's shape in hairline grey until the forecast comes. The search works at once: what is
    typed carries over. The day picker has only its first choice until the forecast's dates are known.
    data-built: the script updates this .lead where it stands rather than replacing it (index.html,
    overBuilt), so its picture is painted once, at the first paint. data-nosnippet: search engines may index
    what is in #result but not quote it in a result, where a level would outlive its forecast; they quote
    the page's description instead, which gives none (the script keeps #result, so the mark stays)."""
    return ('<div id="result" data-built data-nosnippet><div class="lead"><section class="intro"><h1>Check the water before you go</h1>'
            f'<p class="lede">Five-day pollution risk forecasts for {n} swim spots in England<span class="lede-map">, and for any river or lake you '
            '<span class="w-touch">tap</span><span class="w-click">click</span> on the map</span>. <a href="#about">How it works</a></p>'
            f'<div class="search">{SEARCH_ICON}<label class="sr" for="q">Find a spot</label><input type="search" id="q" '
            'placeholder="River, lake or town" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search" value=""></div>'
            f'{NEAR_CTA}{HERE_CTA}</section>'
            '<div class="toolbar"><label class="sr" for="listday">When are you swimming?</label><select id="listday">'
            '<option value="">Today and tomorrow</option></select><button type="button" class="chip-btn low" data-low aria-pressed="false">'
            '<span class="dot" style="background:#3b7d4f"></span><span data-low-t>Low\u00a0risk only</span></button></div>'
            f'</div><div class="cols"><div class="col-list"><p class="sr" aria-busy="true">Loading forecasts…</p>{SKELETON_TILE}</div>'
            # The map's tile, as index.html's MAP_TILE frames it, empty until the script moves the map in.
            '<div class="col-map"><div class="tile map-tile"></div></div></div></div>')


def spot_page(template: str, spot: dict, root: str, top: str | None = None, card: tuple[str, str] | None = None,
              feed: bool = False) -> str:
    """A spot's own page: the map page with the spot's name, description and address in its
    <head>, and its share card (card: path and alt, write_spot_cards) as the preview picture. In the body, top: the spot's answer and five days as the page's script draws them
    (prerender_spots), for crawlers, readers without scripts and the moment before the script runs.
    Without it, its name under the sky, as the answer will be (see home_lead). feed: link its Atom feed
    (write_feeds)."""
    url = f"{root}spot/{spot['id']}/"
    blurb = spot_blurb(spot)
    page = PAGE_META.sub(lambda m: page_meta(f"{spot['name']}: pollution risk forecast · {BRAND}", blurb, url, root,
                                             base="../../", image=card,
                                             feed=(f"spot/{spot['id']}/feed.xml", f"{BRAND} · {spot['name']}") if feed else None),
                       template, count=1)
    if top:
        # The script's own view of a spot is view-spot: the About section folded to a line, Map in the header.
        page = page.replace('<body class="view-list">', '<body class="view-spot">', 1)
        # A desktop's spot page spans the screen and draws the wide sky from 801 px (index.html, "A spot
        # opens as a page"), so each screen asks early for the picture it shows, and only that one.
        page = page.replace(SKY_PRELOAD, SPOT_SKY_PRELOAD, 1)
        return page.replace(LOADING, f'<div id="result" data-built data-nosnippet>{top}<noscript><p class="muted">{NOSCRIPT}</p></noscript></div>', 1)
    return page.replace(LOADING, '<div id="result" data-nosnippet><div class="top-row"><a href="./" class="back">All spots</a></div>'
                                 f'<section class="answer"><h2 class="spot-name">{escape(spot["name"])}</h2>'
                                 f'<p class="muted">{escape(blurb)} Loading the forecast…</p></section>{SKELETON_TILE}</div>', 1)


# Under a built spot page's five days, for a reader without scripts: what they are seeing, and what not.
NOSCRIPT = ("This is the forecast as it was issued. With JavaScript on, the page updates it and adds the map, "
            "the overflows upstream and the rest of the detail.")


def prerender_spots(site: Path, root: str) -> dict[str, str]:
    """Each spot's answer and five days as index.html draws them, {id: html}, from this build's
    data/spots.json (scripts/prerender_spots.js runs the page's own spotTop and daysTile in Node,
    in UK time, as at the moment the forecast was issued). Without Node, or the file, {}: the pages
    keep the name-only opening, and the build says why."""
    src = site / "data" / "spots.json"
    if not src.exists():
        return {}
    try:
        run = subprocess.run(["node", str(ROOT / "scripts" / "prerender_spots.js"), str(src), "-", root], check=True,
                             capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "Europe/London"})
        return json.loads(run.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log.warning("spot pages without their forecast in the HTML (%s)", getattr(e, "stderr", "") or e)
        return {}


def saved_page(template: str, root: str) -> str:
    """The Saved page, saved/: the map page, where the script shows the lists of spots this browser
    has saved, or a list someone shared (saved/#list=...&spots=..., lists.js). The lists live in the
    browser, not in the page, so search engines are asked to leave it out and the sitemap does not
    list it."""
    page = PAGE_META.sub(lambda m: page_meta(SAVED_TITLE, SAVED_DESCRIPTION, f"{root}saved/", root, base="../",
                                             noindex=True), template, count=1)
    return page.replace(LOADING, '<div id="result"><h1 class="page-h">Saved spots</h1>'
                                 '<p class="muted">Loading your saved spots…</p></div>', 1)


# The places Plan a swim can start from: OS Open Names' cities, towns, districts and villages in England
# and Wales (scripts/make_places.py writes it; it changes only when that is run again).
PLACES = config.RAW / "places.json"
# The rivers and lakes the home page's search finds on the map: OS Open Rivers' named rivers and the
# WFD lakes in England (scripts/make_waters.py writes it; likewise only when run again).
WATERS = config.RAW / "waters.json"


def plan_page(template: str, root: str) -> str:
    """Plan a swim, plan/: the map page, where the script asks for a day, a starting place and a
    distance, and lists the spots within reach (plan.js). The plan itself is after the # in the
    address, so every plan is this one page."""
    page = PAGE_META.sub(lambda m: page_meta(PLAN_TITLE, PLAN_DESCRIPTION, f"{root}plan/", root, base="../"), template, count=1)
    return page.replace(LOADING, '<div id="result"><h1 class="page-h">Plan a swim</h1>'
                                 f'<p class="muted">{escape(PLAN_DESCRIPTION)} Loading the forecasts…</p></div>', 1)


# The Accuracy page's five boxes, which its script fills from data/verification.json.
VERIFICATION_BOXES = {"top": '<div id="top"><p class="muted">Loading the scores…</p></div>', "answer": '<div id="answer"></div>',
                      "short": '<div id="short"></div>',
                      "live": '<div id="live"></div>', "offline": '<div id="offline"></div>'}


def with_verification_figures(html: str, verification: Path) -> str:
    """The Accuracy page with its figures, tables and lists written in from this build's
    verification.json (scripts/prerender_verification.js runs the page's own script in Node, in UK
    time), and data-built on <main>: when those live scores were made, so the script draws them
    again only from newer ones. Unchanged, with the reason in the log, without Node or the file."""
    if not verification.exists():
        return html
    try:
        run = subprocess.run(["node", str(ROOT / "scripts" / "prerender_verification.js"), "-", str(verification)], input=html,
                             check=True, capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "Europe/London"})
        out = json.loads(run.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log.warning("Accuracy page without its figures in the HTML (%s)", getattr(e, "stderr", "") or e)
        return html
    if not all(box in html for box in VERIFICATION_BOXES.values()) or '<main class="doc">' not in html:
        log.warning("Accuracy page without its figures in the HTML: its boxes have changed")
        return html
    for key, box in VERIFICATION_BOXES.items():
        html = html.replace(box, f'<div id="{key}">{out[key]}</div>', 1)
    return html.replace('<main class="doc">', f'<main class="doc" data-built="{escape(out["built"])}">' if out["built"] else '<main class="doc">', 1)


def with_counts(html: str, results: list[dict]) -> str:
    """The About page's spot counts, from this build's spots, and how far upstream the tracing
    goes, from the config, so they cannot go stale."""
    n_bw = sum(r.get("source") == "designated" for r in results)
    html = re.sub(r'(<span id="n-spots">)\d+(</span>)', rf"\g<1>{len(results)}\g<2>", html, count=1)
    html = re.sub(r'(<span id="max-km">)\d+(</span>)', rf"\g<1>{config.MAX_UPSTREAM_KM:g}\g<2>", html, count=1)
    return re.sub(r'(<span id="n-bw">)\d+(</span>)', rf"\g<1>{n_bw}\g<2>", html, count=1)


# The warning figures on clubs.html, in words, from the live warning table (verification.json's
# live.warning_table): the share of spills warned of (hit_rate) and the share of warnings followed by a
# spill (warnings_true), each as the nearest simple fraction. The page's own words stay when the table
# or a field is missing.
WARN_FIGURES = re.compile(r'(<span id="warn-figures">).*?(</span>)', re.DOTALL)
NUMBERS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 9: "nine", 10: "ten"}
FRACTIONS = sorted({(n, d) for d in (2, 3, 4, 5, 6, 10) for n in range(1, d) if math.gcd(n, d) == 1}, key=lambda f: f[1])


def share_words(p: float) -> str:
    """A share as words a reader can picture: "about one in five". The nearest of the fractions with 2, 3, 4,
    5, 6 or 10 below the line (the smaller denominator on a tie); below 1 in 20 and above 19 in 20 it says so.
    Sixths are there because 16.7% of spills warned of would read "about one in five", the nearest of
    the others."""
    if p < 0.05:
        return "fewer than one in twenty"
    if p > 0.95:
        return "nearly all"
    n, d = min(FRACTIONS, key=lambda f: (abs(p - f[0] / f[1]), f[1]))
    return f"about {NUMBERS[n]} in {NUMBERS[d]}"


def day_words(a: pd.Timestamp, b: pd.Timestamp) -> str:
    """"29 September to 4 October 2026", with the first year only when the years differ."""
    first = f"{a.day} {a:%B}" + (f" {a.year}" if a.year != b.year else "")
    return f"{first} to {b.day} {b:%B %Y}"


def with_warning_words(html: str, verification: Path) -> str:
    try:
        w = json.loads(verification.read_text())["live"]["warning_table"]
        hit, true = float(w["hit_rate"]), float(w["warnings_true"])
        a, b = pd.Timestamp(w["first_day"]), pd.Timestamp(w["last_day"])
    except (OSError, ValueError, KeyError, TypeError):
        return html   # the hand-written figures stay
    lead = "It misses most spills." if hit < 0.45 else "It misses about half of all spills." if hit <= 0.55 else "It misses some spills."
    # A count of days where the scorer gives one: "ran from 29 September to 10 October" read as an
    # unbroken run, and 8 and 9 October had nothing scored.
    n = w.get("n_days")
    when = (f"cover {n} day{'' if n == 1 else 's'} between {day_words(a, b).replace(' to ', ' and ', 1)}"
            if isinstance(n, int) and n > 0 else f"ran from {day_words(a, b)}")
    said = (f"{lead} Its live scores {when}. At the {escape(str(w.get('level') or 'high'))} risk line, "
            f"it warned of {share_words(hit)} spills. {share_words(true).capitalize()} of its warnings were followed by a spill.")
    # Whose spills: on 11 Oct 2026, 208 of the 223 hits were at United Utilities, the one company the
    # spill model learned from; elsewhere it warned of 15 of 638 (forecast_log: warning_table.by_company).
    rows = w.get("by_company") or []
    own = next((r for r in rows if r.get("company") == w.get("trained_on")), None)
    rest = [r for r in rows if r is not own]
    spills = sum(r["hits"] + r["misses"] for r in rest)
    if own and own.get("hits") and w.get("hits") and spills:
        said += (f" {own['hits']} of the {w['hits']} warnings that came true were at {escape(own['company'])}, the one company "
                 f"the spill model learned from. At the other companies, so far, it warned of "
                 f"{share_words(sum(r['hits'] for r in rest) / spills)} spills.")
    return WARN_FIGURES.sub(lambda m: m.group(1) + said + m.group(2), html, count=1)


def not_found_page(root: str) -> str:
    """404.html: GitHub Pages serves it for any missing address, at any depth, so every link in it
    is absolute. Without it, a mistyped or outdated link gets GitHub's own page, with no way back."""
    r = escape(root)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>Page not found · {BRAND}</title><meta name="robots" content="noindex">\n'
        '<meta name="theme-color" content="#3d5b5d">\n'
        f'<link rel="icon" href="{r}icons/icon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="{r}icons/apple-touch-icon.png">\n'
        f'<link rel="stylesheet" href="{r}page.css">\n'
        f'<link rel="preload" href="{r}fonts/SourceSans3-latin.woff2" as="font" type="font/woff2" crossorigin>'
        f'<link rel="preload" href="{r}fonts/SourceSerif4-latin.woff2" as="font" type="font/woff2" crossorigin>\n'
        f'</head><body>\n<header class="top"><a class="brand" href="{r}">{MARK}{BRAND}</a>'
        f'<nav aria-label="Site"><a href="{r}">Explore</a><a href="{r}verification.html">Accuracy</a><a href="{r}about.html">About</a><a href="{r}feedback.html">Feedback</a></nav></header>\n'
        '<main class="doc"><h1>No page at this address</h1>\n'
        '<p class="lead">A spot changes address when it is renamed or removed, and a link can be copied or typed wrongly.</p>\n'
        f'<ul><li><a href="{r}">All spots</a>, each with its five-day forecast</li><li><a href="{r}saved/">Your saved spots</a></li>'
        f'<li><a href="{r}feedback.html?type=spot">Ask for a spot to be added</a></li></ul></main>\n'
        f'<footer class="site-foot"><div class="rule"><p>{BRAND} is a free, non-commercial pollution risk forecast for river and lake swim spots in England, run by Ethan Buckley. A forecast, not a water test.</p>'
        f'<p><a href="{r}terms.html">Terms of use</a> · <a href="{r}privacy.html">Privacy</a> · <a href="{r}feedback.html">Feedback</a></p></div></footer></body></html>\n')


def robots(root: str) -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {root}sitemap.xml\n"


def sitemap(root: str, spot_ids: list[str], day: str, extra: list[str] | None = None) -> str:
    urls = [root, f"{root}plan/", f"{root}about.html", f"{root}verification.html", f"{root}methods.html", f"{root}testing.html", f"{root}coverage.html", f"{root}data.html", f"{root}organisers.html", f"{root}sites.html", f"{root}record.html", f"{root}clubs.html", f"{root}quality.html", f"{root}spots.html"] +[f"{root}{x}" for x in extra or []] + [f"{root}spot/{i}/" for i in spot_ids] + [f"{root}spot/{i}/profile/" for i in spot_ids]
    body = "".join(f"<url><loc>{escape(u)}</loc><lastmod>{day}</lastmod></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'


# Atom feeds, from this build's alerts.json: feed.xml for every spot,
# feed/<area>.xml for each of the list's areas, spot/<id>/feed.xml for each spot with a page. Each
# build adds one entry a spot, its headline and what to do, with the build's time as `updated`, so a
# reader (Slack's RSS app, Feedly, IFTTT, a Discord bot) gets every new forecast. The entry's id has
# the build's time in it, so a reader sees a new entry and not an edited one. sw.js stores none of them.
ATOM = "http://www.w3.org/2005/Atom"


def area_slug(area: str) -> str:
    """'Cumbria and the Lake District' -> 'cumbria-and-the-lake-district', the area feed's file name."""
    return re.sub(r"[^a-z0-9]+", "-", area.lower()).strip("-")


def atom_feed(url: str, alternate: str, title: str, subtitle: str, entries: list[dict], generated: pd.Timestamp,
              root: str, credits: dict | None) -> str:
    """One Atom document (RFC 4287). entries: alerts.json's spots, each with its `id`."""
    from urllib.parse import urlsplit
    from xml.etree import ElementTree as ET
    ET.register_namespace("", ATOM)
    q = lambda tag: f"{{{ATOM}}}{tag}"
    when = generated.tz_convert("UTC").floor("s")
    stamp = when.isoformat().replace("+00:00", "Z")
    feed = ET.Element(q("feed"))

    def add(parent, tag, text=None, **attrs):
        el = ET.SubElement(parent, q(tag), {k: str(v) for k, v in attrs.items()})
        if text is not None:
            el.text = text
        return el

    add(feed, "id", url)
    add(feed, "title", title)
    add(feed, "subtitle", subtitle)
    add(feed, "updated", stamp)
    add(feed, "link", rel="self", type="application/atom+xml", href=url)
    add(feed, "link", rel="alternate", type="text/html", href=alternate)
    author = add(feed, "author")
    add(author, "name", BRAND)
    add(author, "uri", root)
    add(feed, "icon", f"{root}icons/icon-192.png")
    if credits:
        add(feed, "rights", " ".join(x for x in (credits.get("attribution"), credits.get("modified"),
                                                 f"Full credits: {credits['full']}" if credits.get("full") else None) if x))
    # tag: URIs (RFC 4151), from the site's host and the build's date and time: one id a spot a build.
    host = urlsplit(root).hostname or "swimsignal.co.uk"
    for s in entries:
        e = add(feed, "entry")
        add(e, "id", f"tag:{host},{when.date().isoformat()}:spot/{s['id']}/{when.strftime('%Y%m%dT%H%M%SZ')}")
        add(e, "title", f"{s['name']} · {s['headline']}")
        add(e, "updated", stamp)
        add(e, "link", rel="alternate", type="text/html", href=s["url"])
        add(e, "category", term=s["level"])
        add(e, "summary", f"{s['headline']}. {s['action']}" if s.get("action") else s["headline"])
    ET.indent(feed)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(feed, encoding="unicode") + "\n"


def write_feeds(site: Path, results: list[dict], root: str) -> dict | None:
    """feed.xml, feed/<area>.xml and spot/<id>/feed.xml from site/data/alerts.json, after the spot pages
    (write_pages clears spot/). Without alerts.json (Node missing, or a preview) there are no feeds,
    and none left from an earlier build. Returns the counts, or None."""
    shutil.rmtree(site / "feed", ignore_errors=True)
    (site / "feed.xml").unlink(missing_ok=True)
    path = site / "data" / "alerts.json"
    try:
        alerts = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    generated, credits = pd.Timestamp(alerts["generated_at"]), alerts.get("credits")
    spots = [{"id": sid, **a} for sid, a in alerts["spots"].items()]
    area_of = {r["id"]: r.get("area") for r in results}
    (site / "feed.xml").write_text(atom_feed(
        f"{root}feed.xml", root, f"{BRAND} · every spot", "The pollution risk forecast at every river and lake swim spot, "
        "a new entry a spot each time the forecast is issued.", spots, generated, root, credits))
    areas: dict[str, list[dict]] = {}
    for s in spots:
        if area_of.get(s["id"]):
            areas.setdefault(area_of[s["id"]], []).append(s)
    (site / "feed").mkdir()
    for area, rows in areas.items():
        (site / "feed" / f"{area_slug(area)}.xml").write_text(atom_feed(
            f"{root}feed/{area_slug(area)}.xml", root, f"{BRAND} · {area}",
            f"The pollution risk forecast at the swim spots in {area}.", rows, generated, root, credits))
    n = 0
    for s in spots:
        if SPOT_ID.fullmatch(s["id"]) and (site / "spot" / s["id"]).is_dir():
            (site / "spot" / s["id"] / "feed.xml").write_text(atom_feed(
                f"{root}spot/{s['id']}/feed.xml", s["url"], f"{BRAND} · {s['name']}",
                f"The pollution risk forecast at {s['name']}.", [s], generated, root, credits))
            n += 1
    return {"site": len(spots), "areas": {area_slug(a): len(r) for a, r in areas.items()}, "spots": n}


FEEDS = "<!-- feeds -->"


def with_feed_list(html: str, site: Path) -> str:
    """The data page's list of the area feeds this build wrote, at its FEEDS marker."""
    files = sorted((site / "feed").glob("*.xml")) if (site / "feed").is_dir() else []
    items = "".join(f'<li><a href="feed/{escape(p.name)}">feed/{escape(p.name)}</a></li>' for p in files)
    return html.replace(FEEDS, f'<ul class="feeds">{items}</ul>' if items else "", 1)


# The app's page carries its reasons as comments, kept in the source. The built pages leave out the
# CSS comments and the script lines that are only a comment: 22 kB of the page's 86 kB compressed on
# 6 Oct 2026. A comment after code on the same line stays, and so does every HTML comment (the
# page-meta block is found by its comments). js_without_comment_lines follows the strings, templates,
# regular expressions and comments, so that a line inside a template that starts with "//" stays; a
# script it cannot follow to the end is left whole.
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
INLINE_SCRIPT = re.compile(r"(<script>)(.*?)(</script>)", re.S)
STYLE_BLOCK = re.compile(r"(<style>)(.*?)(</style>)", re.S)
REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
REGEX_AFTER_WORDS = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw", "yield", "await", "instanceof"}


def js_without_comment_lines(js: str) -> str:
    """js less each line that is only a // comment, or js itself if its strings, templates, regular
    expressions or comments do not all close."""
    out, stack, mode, last, word = [], ["code"], None, None, ""   # stack: code / template frames; mode: in a token
    for line in js.split("\n"):
        if mode is None and stack[-1] == "code" and line.lstrip().startswith("//"):
            continue
        i, n = 0, len(line)
        while i < n:
            c = line[i]
            if mode == "block":
                if line.startswith("*/", i):
                    mode, i = None, i + 2
                    continue
            elif mode in ("'", '"'):
                if c == "\\":
                    i += 1
                elif c == mode:
                    mode, last = None, c
            elif mode == "regex" or mode == "class":
                if c == "\\":
                    i += 1
                elif mode == "regex" and c == "[":
                    mode = "class"
                elif mode == "class" and c == "]":
                    mode = "regex"
                elif mode == "regex" and c == "/":
                    mode, last = None, ")"   # a division may follow, as after a value
            elif stack[-1] == "template":
                if c == "\\":
                    i += 1
                elif c == "`":
                    stack.pop()
                    last = "`"
                elif line.startswith("${", i):
                    stack.append("code")
                    i += 1
            else:   # code
                if line.startswith("//", i):
                    break
                if line.startswith("/*", i):
                    mode, i = "block", i + 2
                    continue
                if c in "'\"":
                    mode = c
                elif c == "`":
                    stack.append("template")
                elif c == "/":
                    if last is None or last in REGEX_AFTER or word in REGEX_AFTER_WORDS:
                        mode = "regex"
                    else:
                        last = c
                elif c == "{":
                    stack.append("code")
                    last = c
                elif c == "}":
                    if len(stack) > 1:
                        stack.pop()   # a block, or the end of ${...} back into its template
                    last = c
                elif not c.isspace():
                    last = c
                if c.isalnum() or c in "_$":
                    word = (word + c) if (i and (line[i - 1].isalnum() or line[i - 1] in "_$")) else c
                elif not c.isspace():
                    word = ""
            i += 1
        if mode in ("'", '"', "regex", "class"):   # these never run over a line
            return js
        out.append(line)
    return "\n".join(out) if mode is None and stack == ["code"] else js


def lean_page(html: str) -> str:
    """The page without CSS comments and comment-only script lines (js_without_comment_lines)."""
    html = STYLE_BLOCK.sub(lambda m: m.group(1) + CSS_COMMENT.sub("", m.group(2)) + m.group(3), html)
    return INLINE_SCRIPT.sub(lambda m: m.group(1) + js_without_comment_lines(m.group(2)) + m.group(3), html)


# The app page's scripts, none of them blocking the first paint (blocking, they
# held it back 850 ms on 16 Oct 2026). In the built page every <script src> is deferred and the page's
# own script, inline in the source, is app.js?v=<stamp>, deferred too, which the offline copy stores
# as it does the others. Deferred scripts run in the order of their tags once the page is parsed, so
# the order is the source's: the fourteen, then the page's script, then anypoint.js. The source keeps
# the script inline, where the tests and scripts/prerender_spots.js read it.
APP_SCRIPT = re.compile(r"<script>\n(const BRAND = .*?)</script>", re.S)
SCRIPT_TAG = re.compile(r'<script src="[^"]+"(?: integrity="[^"]+")?></script>')


def split_app_script(html: str, stamp: str) -> tuple[str, str]:
    """The built app page with its scripts deferred, and app.js: its own script, out of the page."""
    m = APP_SCRIPT.search(html)
    if not m or html.count("\nconst BRAND = ") != 1:
        raise ValueError("index.html has lost its script, which starts const BRAND = ...")
    html = html[:m.start()] + f'<script src="app.js?v={stamp}" defer></script>' + html[m.end():]
    return SCRIPT_TAG.sub(lambda t: t[0].replace("></script>", " defer></script>"), html), m.group(1)


def write_pages(site: Path, results: list[dict], token: str | None = None, root: str | None = None,
                day: str | None = None, push: bool = False, coastal: dict | None = None, wales: dict | None = None,
                scotland: dict | None = None, email: bool = False, ireland: dict | None = None,
                northern_ireland: dict | None = None, support: str | None = None, tiles: dict | None = None,
                push_dates: bool = False, spot_cards: dict[str, str] | None = None, cards_v: str = "",
                overflows: pd.DataFrame | None = None, generated: pd.Timestamp | None = None) -> int:
    """Every HTML page, the sitemap and the app files. Returns the number of spot pages. A spot
    whose id is not letters, digits and hyphens gets no page of its own and keeps ?spot=.
    support is the Ko-fi page tips go to (support_url), or None for no tips; tiles the map tile
    provider (tile_config), or None for OpenStreetMap's. spot_cards: {id: alt} for the spots with a share
    card in cards/spot/ (write_spot_cards); cards_v goes on its address, so a preview fetched again
    gets this build's card rather than a cached one. overflows: this build's overflow table, for the
    data-quality page (write_quality_page); generated: the forecast's issue time, which that page gives."""
    root = root or site_url()
    stamp = shell_stamp()
    template = with_tiles(with_build(TEMPLATE.read_text(), stamp), "index.html", tiles)
    if not (PAGE_META.search(template) and LOADING in template):
        raise ValueError("index.html has lost its page-meta block or its loading placeholder")
    template = lean_page(template)   # its CSS comments and comment-only script lines: the source keeps them
    template, app_js = split_app_script(template, stamp)   # the page's own script, deferred, as app.js
    for name in ["about.html", "verification.html", "terms.html", "privacy.html", "feedback.html", "testing.html", "methods.html", "coverage.html", "clubs.html"]:
        s = (STATIC / name).read_text()
        if name == "verification.html":   # before REWRITES, which then reach the links the figures carry
            s = with_verification_figures(s, site / "data" / "verification.json")   # build() writes it before the pages
        for a, b in REWRITES:
            s = s.replace(a, b)
        if name == "about.html":
            s = with_counts(s, results)
        if name == "clubs.html":
            s = with_warning_words(s, site / "data" / "verification.json")   # build() writes it before the pages
        if name == "coverage.html":
            from dipcast.coastal import render
            s = re.sub(r'<!-- COASTAL_DIRECTORY -->.*?<!-- END_COASTAL_DIRECTORY -->',
                       lambda _: render(coastal), s, flags=re.S)
            from dipcast.wales import render as render_wales
            s = re.sub(r'<!-- WALES_DIRECTORY -->.*?<!-- END_WALES_DIRECTORY -->',
                       lambda _: render_wales(wales), s, flags=re.S)
            from dipcast.scotland import render as render_scotland
            s = re.sub(r'<!-- SCOTLAND_DIRECTORY -->.*?<!-- END_SCOTLAND_DIRECTORY -->',
                       lambda _: render_scotland(scotland), s, flags=re.S)
            from dipcast.ireland import render as render_ireland
            s = re.sub(r'<!-- IRELAND_DIRECTORY -->.*?<!-- END_IRELAND_DIRECTORY -->',
                       lambda _: render_ireland(ireland), s, flags=re.S)
            from dipcast.northern_ireland import render as render_ni
            s = re.sub(r'<!-- NI_DIRECTORY -->.*?<!-- END_NI_DIRECTORY -->',
                       lambda _: render_ni(northern_ireland), s, flags=re.S)
        s = with_counter(with_push(s, push, email, push_dates) if name == "privacy.html" else s, token)
        s = with_tiles(s, name, tiles)
        (site / name).write_text(with_support(s, name) if support else s)
    if support:
        s = (STATIC / "support.html").read_text().replace("__KOFI_URL__", escape(support))
        for a, b in REWRITES:
            s = s.replace(a, b)
        (site / "support.html").write_text(with_counter(s, token))
    else:
        (site / "support.html").unlink(missing_ok=True)   # tips turned off: no page, no links
    shutil.copy(STATIC / "page.css", site / "page.css")
    shutil.copytree(STATIC / "fonts", site / "fonts", dirs_exist_ok=True)   # declared in page.css and index.html
    copy_app_files(site, stamp)
    (site / "app.js").write_text(app_js)
    feeds = (site / "data" / "alerts.json").is_file()   # write_feeds writes them from it, after the spot pages
    home = PAGE_META.sub(lambda m: page_meta(HOME_TITLE, DESCRIPTION, root, root, base="./",
                                             feed=("feed.xml", f"{BRAND} · every spot") if feeds else None), template, count=1)
    home = home.replace(LOADING, home_lead(len(results)), 1)
    (site / "index.html").write_text(with_counter(home, token))
    (site / "saved").mkdir(exist_ok=True)
    (site / "saved" / "index.html").write_text(with_counter(saved_page(template, root), token))
    (site / "plan").mkdir(exist_ok=True)
    (site / "plan" / "index.html").write_text(with_counter(plan_page(template, root), token))
    (site / "data").mkdir(exist_ok=True)
    shutil.copy(PLACES, site / "data" / "places.json")   # before the data page, which lists data/
    shutil.copy(WATERS, site / "data" / "waters.json")
    shutil.rmtree(site / "spot", ignore_errors=True)   # a spot dropped from spots.csv loses its page
    tops = prerender_spots(site, root)
    ids = []
    for r in results:
        if not SPOT_ID.fullmatch(str(r["id"])):
            log.warning("spot id %r is not letters, digits and hyphens: no page of its own, it keeps ?spot=", r["id"])
            continue
        (site / "spot" / r["id"]).mkdir(parents=True, exist_ok=True)
        (site / "spot" / r["id"] / "index.html").write_text(with_counter(spot_page(template, r, root, tops.get(r["id"]),
            (f"cards/spot/{r['id']}.png?v={cards_v}", spot_cards[r["id"]]) if r["id"] in (spot_cards or {}) else None, feeds), token))
        write_sign(site, r, root, token)   # spot/<id>/sign/, and the QR code the live sign shows
        ids.append(r["id"])
    paged = [r for r in results if r["id"] in set(ids)]
    write_profiles(site, paged, token, root=root)   # spot/<id>/profile/, from data/upstream/
    write_every_spot(site, paged, root, token)   # spots.html, the spots' pages as plain links
    write_feeds(site, results, root)   # feed.xml, feed/, spot/<id>/feed.xml: after spot/ is written, before the data page lists them
    (site / "sitemap.xml").write_text(sitemap(root, ids, day or pd.Timestamp.now(tz="Europe/London").date().isoformat(),
                                              extra=["support.html"] if support else []))
    (site / "404.html").write_text(with_counter(not_found_page(root), token))
    (site / "robots.txt").write_text(robots(root))
    (site / ".nojekyll").write_text("")
    write_data_page(site, token)   # lists what is in data/, so build() writes the data files first
    write_quality_page(site, overflows, generated, token)
    write_embed(site)
    write_organisers(site, token)
    write_sites(site, token)
    write_record(site, token)
    if support:
        add_support_links(site)   # last, so every page written above has its foot
    return len(ids)


def write_any_point(site: Path, credits: dict) -> dict | None:
    """site/data/anypoint/: what the page needs to forecast a click away from the listed spots
    (scripts/build_any_point.py). Run after the spot forecasts, from the same overflow table, model
    and rain. A failure leaves the files out and is announced; it never stops the spots publishing."""
    import importlib.util

    from dipcast.model.forecast import _model, spill_probabilities
    try:
        spec = importlib.util.spec_from_file_location("build_any_point", ROOT / "scripts" / "build_any_point.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        model = _model()
        return mod.build(site, _net(), _overflows(), lambda ov, days, rain: spill_probabilities(ov, days, model, rain=rain),
                         credits)
    except Exception as e:  # noqa: BLE001 - an addition beside the spots must not sink the site
        announce(f"click-anywhere data not written: {e}")
        shutil.rmtree(site / "data" / "anypoint", ignore_errors=True)   # never half a set of files
        return None


def announce(warning: str) -> None:
    """Log a build warning and, on GitHub Actions, raise it as an annotation on the run page."""
    log.warning("%s", warning)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("::warning title=dipcast build health::" + warning.replace("%", "%25").replace("\n", "%0A"), flush=True)


# The data page, data.html: every file under data/, what it holds, its fields and its licence. The
# words are the page's (src/dipcast/pages/data.html), one table row and one section a file. The
# build fills in each file's size, marks a described file this build did not write, and adds a row
# for any file in data/ the page does not describe, with a build warning, so the list is always
# every file published. REWRITES gains the links to it, to About's embed section and to About's
# example card.
REWRITES += [('href="/data"', 'href="data.html"'), ('href="/about#embed"', 'href="about.html#embed"'),
             ('href="/embed.html?spot=wharfe-burnsall"', 'href="embed.html?spot=wharfe-burnsall"')]
DATA_ROW = re.compile(r'(<tr data-file="([^"]+)">[^\n]*?<td class="num">)[^<]*(</td></tr>)')
MORE_FILES = "<!-- more files -->"


def file_size(n: int) -> str:
    return f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{max(1, round(n / 1e3))} kB"


def data_files(data: Path) -> dict[str, int]:
    """Every entry in data/ and its size in bytes; a folder counts whole, as name/."""
    if not data.is_dir():
        return {}
    return {p.name + "/" * p.is_dir(): sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size
            for p in sorted(data.iterdir()) if not p.name.startswith(".")}


def with_data_files(html: str, data: Path) -> tuple[str, list[str]]:
    """The data page with this build's file sizes, and the files it does not describe."""
    files, described = data_files(data), set()

    def size(m: re.Match) -> str:
        described.add(m.group(2))
        return m.group(1) + (file_size(files[m.group(2)]) if m.group(2) in files else "Not in this build") + m.group(3)

    html = DATA_ROW.sub(size, html)
    if MORE_FILES not in html:
        raise ValueError(f"data.html has lost its {MORE_FILES!r} marker, where undescribed files are listed")
    extra = [n for n in files if n not in described]
    name = lambda n: escape(n) if n.endswith("/") else f'<a href="data/{escape(n)}">{escape(n)}</a>'   # a folder has no page
    rows = "".join(f'<tr data-file="{escape(n)}"><td>{name(n)}</td><td>Not described here yet.</td>'
                   f'<td class="num">{file_size(files[n])}</td></tr>\n' for n in extra)
    return html.replace(MORE_FILES, rows, 1), extra


# The overflow layer cut into map tiles: data/overflows/<x>-<y>.json, and
# index.json naming the tiles that have any. The map asks for the tiles in view (index.html, loadOverflows)
# rather than the whole 6.3 MB overflows.geojson, which stays for the data page and the download. Zoom 10:
# on 16 Oct 2026 293 tiles, and a spot's view at zoom 12 needed at most 38 kB of them gzipped (the
# median 8 kB); zoom 9's 89 tiles needed up to 92 kB. The offline copy (sw.js) stores neither.
OVERFLOW_TILE_Z = 10


def overflow_tile(lon: float, lat: float, z: int = OVERFLOW_TILE_Z) -> tuple[int, int]:
    """The Web Mercator (slippy map) tile at zoom z that holds a point, as index.html's ovTile works it out."""
    n, r = 2 ** z, math.radians(max(-85.0511, min(85.0511, lat)))
    y = (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n
    return min(n - 1, max(0, math.floor((lon + 180) / 360 * n))), min(n - 1, max(0, math.floor(y)))


def write_overflow_tiles(site: Path, geo: dict) -> int:
    """data/overflows/: geo's features by tile, and index.json with the zoom, the tiles and the credits.
    Returns the number of tiles."""
    out = site / "data" / "overflows"
    shutil.rmtree(out, ignore_errors=True)   # a tile that has lost its overflows goes
    out.mkdir(parents=True)
    tiles: dict[tuple[int, int], list] = {}
    for f in geo["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        if not (math.isfinite(lon) and math.isfinite(lat)):   # nowhere on the map
            continue
        tiles.setdefault(overflow_tile(lon, lat), []).append(f)
    for (x, y), feats in tiles.items():
        (out / f"{x}-{y}.json").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":"), default=str))
    (out / "index.json").write_text(json.dumps({"z": OVERFLOW_TILE_Z, "tiles": [f"{x}-{y}" for x, y in sorted(tiles)],
                                                **({"credits": geo["credits"]} if geo.get("credits") else {})}))
    return len(tiles)


def write_upstream(site: Path, upstream: dict[str, list[dict]], generated: pd.Timestamp, credits: dict) -> int:
    """data/upstream/<id>.json: every monitored overflow upstream of a spot, most reach first, with the
    fields the organisers' page lists. spots.json keeps the KEEP_CONTRIBUTORS that matter most this week,
    which left the page's table partial at 42 of 105 spots on 4 Oct 2026; one file per spot, loaded on
    demand, keeps spots.json the size it was (measured on 4 Oct 2026: 1,720 overflows at 81 spots, 506 kB
    before each file's 2 kB of credits; the largest, Warleigh Weir's 185, 55 kB). Reach does not
    change with the weather, so an event weeks away is best judged on it. A spot whose id cannot be a
    file name, or with nothing upstream, gets no file. Returns the number written."""
    out = site / "data" / "upstream"
    shutil.rmtree(out, ignore_errors=True)   # no file left from a spot that has gone
    out.mkdir(parents=True)
    n = 0
    for sid, rows in upstream.items():
        if not rows or not SPOT_ID.fullmatch(str(sid)):
            continue
        listed = sorted(({k: r.get(k) for k in UPSTREAM_FIELDS} for r in rows), key=lambda r: -(r["weight"] or 0.0))
        (out / f"{sid}.json").write_text(json.dumps({"id": sid, "generated_at": generated.isoformat(), "overflows": listed,
                                                     "credits": credits}, separators=(",", ":"), default=str))
        n += 1
    return n


# The river each spot's forecast traced upstream (src/dipcast/trace.py), drawn on its map at zoom 10 or
# more: data/spot/<id>-trace.json, beside the spot's own file, which sw.js stores it with. `lines` are
# encoded polylines (trace.encode); `overflows` the monitored overflows counted on them, [site_id, lat, lon].
TRACE_MAX_BYTES = 50_000   # a trace file's limit; Warleigh Weir's, with the most overflows, is the largest


def write_traces(site: Path, traces: dict[str, list[str]], upstream: dict[str, list[dict]], generated: pd.Timestamp,
                 credits: dict) -> dict:
    """data/spot/<id>-trace.json for each spot with a traced river and an id that can be a file name.
    Returns the number written and the largest file's size; a file over TRACE_MAX_BYTES is announced."""
    out = site / "data" / "spot"
    out.mkdir(parents=True, exist_ok=True)
    n, largest = 0, (None, 0)
    for sid, lines in traces.items():
        if not lines or not SPOT_ID.fullmatch(str(sid)):
            continue
        ovs = [[o.get("site_id"), round(o["lat"], 5), round(o["lon"], 5)] for o in upstream.get(sid, [])
               if o.get("lat") is not None and o.get("lon") is not None]
        body = json.dumps({"id": sid, "generated_at": generated.isoformat(), "max_upstream_km": config.MAX_UPSTREAM_KM,
                           "simplified_m": SIMPLIFY_M, "lines": lines, "overflows": ovs, "credits": credits},
                          separators=(",", ":"), default=str)
        (out / f"{sid}-trace.json").write_text(body)
        n += 1
        if len(body) > largest[1]:
            largest = (sid, len(body))
    if largest[1] > TRACE_MAX_BYTES:
        announce(f"{largest[0]}'s upstream trace is {largest[1] / 1e3:.0f} kB, over {TRACE_MAX_BYTES / 1e3:.0f} kB: "
                 "simplify it more (trace.SIMPLIFY_M)")
    return {"written": n, "largest": largest[0], "largest_bytes": largest[1]}


# What every view of the app loads first is spots.json without the fields only a spot's own page
# shows: its overflows (contributors) and its practical guide. On 6 Oct 2026 they were 52% of
# spots.json (39% and 13%), and taking them out cut the file from 115 kB to 36 kB gzipped. The
# spot's page asks for its own data/spot/<id>.json. spots.json itself stays whole, for anyone who
# reads it, for the organisers' page and the decision record, and for scripts/alerts.js. The lab
# results an organisation sent (measured) are a spot page's alone too.
DETAIL_FIELDS = ("contributors", "guide", "measured", "linked")   # linked: spot_links, the Nearby card's


def reach_by_company(contributors: list[dict]) -> list[list]:
    """Whose overflows a spot's are, by their reach: [[company, share of the summed weight], ...], the largest
    first, shares to three places. The lite file keeps this in place of the contributors, for Plan a swim's
    evidence line (evidence.js, evidenceCoverage), which tells the company the spill model learned from apart
    from the rest. An overflow with no company counts as "unknown". [] with no weight."""
    by: dict[str, float] = {}
    for c in contributors or []:
        by[c.get("company") or "unknown"] = by.get(c.get("company") or "unknown", 0.0) + float(c.get("weight") or 0)
    total = sum(by.values())
    return [] if total <= 0 else [[k, round(w / total, 3)] for k, w in sorted(by.items(), key=lambda kv: -kv[1])]


def write_app_data(site: Path, doc: dict) -> int:
    """data/spots-lite.json, spots.json (doc) without DETAIL_FIELDS, and data/spot/<id>.json with them,
    one file a spot. A lite spot names its file in `detail_file`, relative to data/, and gives whose its
    overflows are in `reach_by_company` (reach_by_company), where it has any. A spot whose id
    cannot be a file name keeps every field in the lite file. Returns the number of spot files."""
    out = site / "data" / "spot"
    shutil.rmtree(out, ignore_errors=True)   # no file left from a spot that has gone
    out.mkdir(parents=True)
    lite = []
    for s in doc["spots"]:
        if not SPOT_ID.fullmatch(str(s["id"])):
            lite.append(s)
            continue
        detail = {k: s[k] for k in DETAIL_FIELDS if k in s}
        (out / f"{s['id']}.json").write_text(json.dumps({"id": s["id"], "generated_at": doc["generated_at"], **detail,
                                                         "credits": doc.get("credits")}, separators=(",", ":"), default=str))
        lite.append({**{k: v for k, v in s.items() if k not in DETAIL_FIELDS}, "detail_file": f"spot/{s['id']}.json",
                     **({"reach_by_company": by} if (by := reach_by_company(s.get("contributors"))) else {})})
    # generated_at first: the push Worker reads only the file's first 4 KB for it (push/src/dispatch.js).
    (site / "data" / "spots-lite.json").write_text(json.dumps({"generated_at": doc["generated_at"], **doc, "spots": lite},
                                                              separators=(",", ":"), default=str))
    return len(doc["spots"]) - sum(1 for s in lite if "detail_file" not in s)


def write_data_page(site: Path, token: str | None = None) -> list[str]:
    """data.html, from the files in site/data. Returns the ones it does not describe."""
    page = (STATIC / "data.html").read_text()
    for a, b in REWRITES:
        page = page.replace(a, b)
    page, extra = with_data_files(page, site / "data")
    page = with_feed_list(page, site)
    if extra:
        announce(f"data.html does not describe {', '.join(extra)}: listed without a description. "
                 "Add a row and a section for each to src/dipcast/pages/data.html")
    (site / "data.html").write_text(with_counter(page, token))
    return extra


# The embed, embed.html?spot=<id>: one spot's card for a club's or a council's page (embed.js says
# what is on it). Its two scripts are asked for at ?v=<a hash of both>, so that a card and its level
# rules come from one build, as the app's do (VERSIONED_SCRIPTS). It has no page-view counter: inside
# another site's page it could not see a visitor's choice not to be counted, which is kept on this one.
EMBED = TEMPLATE.parent / "embed.html"
EMBED_SCRIPTS = ('<script src="levels.js"></script>', '<script src="embed.js"></script>')


def write_embed(site: Path) -> str:
    """embed.html and embed.js beside the app (which has levels.js, page.css and the fonts). Returns
    the scripts' version."""
    h = hashlib.sha256()
    for f in ("levels.js", "embed.js"):
        h.update((TEMPLATE.parent / f).read_bytes())
    v = h.hexdigest()[:8]
    page = EMBED.read_text()
    for tag in EMBED_SCRIPTS:
        if tag not in page:
            raise ValueError(f"embed.html has lost {tag}, which the build versions")
        page = page.replace(tag, tag.replace('.js"', f'.js?v={v}"'), 1)
    shutil.copy(TEMPLATE.parent / "embed.js", site / "embed.js")
    (site / "embed.html").write_text(page)
    return v


# The organisers' page, organisers.html: a prose page for event organisers (organisers.js says what is
# on it), with its scripts versioned as the embed's are. And a sign to print for every spot with a page,
# spot/<id>/sign/, with the QR code made here (src/dipcast/signs.py); the same code as a file,
# spot/<id>/qr.svg, is what the live sign (embed.html?spot=<id>&screen) shows. None of them is in the
# offline copy (sw.js): they are used at a desk or on a screen with a connection, ahead of the swim, and
# the live sign must show the newest forecast, so storing them would only make every visitor's offline
# copy larger. A sign asks search engines to leave it out, and the sitemap lists only the organisers' page.
ORGANISERS = TEMPLATE.parent / "organisers.html"
REWRITES += [('href="/organisers.html"', 'href="organisers.html"')]   # About links it
REWRITES += [('href="/privacy#tips"', 'href="privacy.html#tips"')]   # the support page links it
# The organisers' page loads lists.js and sites.js too, for "Make a sites link" (sites.js, maker).
ORGANISERS_SCRIPTS = ("levels.js", "lists.js", "organisers.js", "sites.js")


def write_scripted_page(site: Path, name: str, scripts: tuple[str, ...], own: tuple[str, ...],
                        token: str | None = None) -> str:
    """A prose page from src/dipcast/site/<name> that reads spots.json with its own scripts, written
    beside the app with its scripts at ?v=<hash of the scripts>, as the embed's are, so the page and its
    level rules always come from one build. own: the scripts this page brings (the app's, levels.js,
    lists.js and evidence.js, are copied with it). Returns the scripts' version."""
    h = hashlib.sha256()
    for f in scripts:
        h.update((TEMPLATE.parent / f).read_bytes())
    v = h.hexdigest()[:8]
    page = (TEMPLATE.parent / name).read_text()
    for f in scripts:
        tag = f'<script src="{f}"></script>'
        if tag not in page:
            raise ValueError(f"{name} has lost {tag}, which the build versions")
        page = page.replace(tag, f'<script src="{f}?v={v}"></script>', 1)
    for f in own:
        shutil.copy(TEMPLATE.parent / f, site / f)
    (site / name).write_text(with_counter(page, token))
    return v


def write_organisers(site: Path, token: str | None = None) -> str:
    """organisers.html and organisers.js beside the app (which has levels.js, lists.js and spots.json).
    Returns the scripts' version."""
    return write_scripted_page(site, "organisers.html", ORGANISERS_SCRIPTS, ("organisers.js", "sites.js"), token)


# The sites view, sites.html#spots=a,b&name=...: several spots on one page, each with its five days, for a
# centre, a club or a council to print before a session (sites.js). And the decision record,
# record.html#spot=<id>&day=YYYY-MM-DD: one A4 page for one spot and one day, to attach to a written
# go/no-go decision (record.js). Both reuse organisers.js's words, so they load it, and printed.js gives both
# their issue id and data credits. Neither is in the offline copy, for the organisers' page's reasons, and
# the sitemap lists both, as it lists that page.
SITES_SCRIPTS = ("levels.js", "lists.js", "organisers.js", "printed.js", "sites.js")
RECORD_SCRIPTS = ("levels.js", "evidence.js", "organisers.js", "printed.js", "record.js")


def write_sites(site: Path, token: str | None = None) -> str:
    return write_scripted_page(site, "sites.html", SITES_SCRIPTS, ("organisers.js", "printed.js", "sites.js"), token)


def write_record(site: Path, token: str | None = None) -> str:
    return write_scripted_page(site, "record.html", RECORD_SCRIPTS, ("organisers.js", "printed.js", "record.js"), token)


# A spot's overflow history, spot/<id>/profile/ (docs/MARKETS-2026-10.md): every monitored overflow
# upstream with its spills and spill hours each year 2021-2025, from the Environment Agency's annual returns
# (data/processed/annual_returns.parquet, OGL v3, credited in the terms). The list is the spot's
# data/upstream/<id>.json, which build() writes (write_upstream) before the pages, so the pages can be
# written again from a downloaded data/ alone. A prose page with no script, in the sitemap beside the
# spot's page; not in the offline copy, and not on the data page, which lists data files.
REWRITES += [('href="/clubs"', 'href="clubs.html"')]   # the page for clubs, centres and leaders (About links it)


def write_quality_page(site: Path, overflows: pd.DataFrame | None, generated: pd.Timestamp | None = None,
                       token: str | None = None, live: Path | None = None, returns: Path | None = None) -> None:
    """quality.html: the overflow records to correct, from the position conflicts' cases
    file, the live snapshot's positions, the annual returns' outlets and this build's overflow table
    (src/dipcast/quality.py). A missing input leaves its part of the page saying so; nothing here stops
    the build."""
    from dipcast import quality
    try:
        cases = quality.load_cases()
    except Exception as e:  # noqa: BLE001 - a page of corrections must not stop the forecast publishing
        announce(f"quality.html without the position conflicts ({quality.CASES}): {e}")
        cases = pd.DataFrame(columns=["site_id", "company", "site_name", "gap_m", "rw_live", "rw_ar", "outcome", "reason"])
    empty = pd.DataFrame(columns=["lat", "lon"])
    try:
        snap = pd.read_parquet(live or config.state_read("live_latest.parquet"), columns=["site_id", "lat", "lon"])
        positions = snap.dropna(subset=["site_id"]).drop_duplicates("site_id", keep="last").set_index("site_id")
    except Exception as e:  # noqa: BLE001
        announce(f"quality.html without the live positions: {e}")
        positions = empty
    try:
        outlets = quality.latest_outlets(pd.read_parquet(returns or quality.RETURNS, columns=["site_id", "year", "lat", "lon"]))
    except Exception as e:  # noqa: BLE001
        announce(f"quality.html without the annual returns' outlets: {e}")
        outlets = empty
    when = (generated or pd.Timestamp.now(tz="UTC")).tz_convert("Europe/London").strftime("%-d %b %Y, %H:%M")
    (site / "quality.html").write_text(with_counter(quality.site_page(cases, positions, outlets, overflows, when, MARK), token))


def write_profiles(site: Path, spots: list[dict], token: str | None = None, returns: Path | None = None,
                   root: str | None = None) -> int:
    """spot/<id>/profile/index.html for each spot (each with a page), joining its data/upstream/<id>.json
    to the annual returns. A spot with no file gets a short page saying why. Returns the number of pages
    with overflows listed. root: the published address, for each page's canonical link (site_url)."""
    from dipcast import profile
    root = root or site_url()
    lists = {}
    for r in spots:
        f = site / "data" / "upstream" / f"{r['id']}.json"
        if f.exists():
            lists[r["id"]] = pd.DataFrame(json.loads(f.read_text()).get("overflows") or [])
    wide = None
    if any(len(t) for t in lists.values()):
        path = returns or profile.RETURNS
        try:   # read once, pivot once, for every spot's overflows
            ids = set().union(*(set(t["site_id"]) for t in lists.values() if len(t)))
            wide = profile.yearly(profile.load_returns(path), ids)
        except Exception as e:  # noqa: BLE001 - the history beside the forecast must not stop the site
            announce(f"overflow history pages without the annual returns ({path}): {e}")
            wide = profile.yearly(pd.DataFrame(columns=profile.RETURN_FIELDS))
    n = 0
    for r in spots:
        t = lists.get(r["id"])
        t = profile.with_returns(t, wide=wide) if t is not None and len(t) else None
        n += t is not None
        (site / "spot" / r["id"] / "profile").mkdir(parents=True, exist_ok=True)
        (site / "spot" / r["id"] / "profile" / "index.html").write_text(
            with_counter(profile.site_page(r, t, MARK, url=f"{root}spot/{r['id']}/profile/"), token))
    return n


# Every spot, spots.html: the spots with a page of their own, each an ordinary link to it, by area
# (spots.csv's `area`) A-Z and A-Z within each. The home list and the map are drawn by the page's script,
# so until 24 Oct 2026 no page linked a spot's page in its HTML; search engines had the sitemap alone, and
# Google listed the home page alone. The app's foot links it, on the home page and every spot's page. A
# prose page with no script, in the sitemap; not in the offline copy. It gives no counts or levels, which
# would go stale between builds.
EVERY_SPOT = TEMPLATE.parent / "spots.html"
EVERY_SPOT_DESCRIPTION = ("Every river and lake swim spot in England that SwimSignal forecasts, by area, each linked "
                          "to its five-day pollution risk forecast.")
NO_AREA = "Other spots"   # a spot with no area in spots.csv: last, so no group is without a name


def every_spot_body(spots: list[dict]) -> str:
    """The page's <main>: the opening, the areas as a contents list, then each area's spots."""
    by: dict[str, list[dict]] = {}
    for s in spots:
        by.setdefault(str(s.get("area") or "").strip() or NO_AREA, []).append(s)
    areas = sorted(by, key=lambda a: (a == NO_AREA, a.casefold()))
    out = ['<h1>Every spot</h1>',
           '<p class="lead">These are the river and lake swim spots SwimSignal forecasts, by area. Each has its own page, '
           'with the pollution risk for the next five days. It is a forecast, not a water test.</p>',
           '<nav class="toc" aria-labelledby="toc-h"><h2 id="toc-h">Areas</h2><ol>'
           + "".join(f'<li><a href="#{area_slug(a)}">{escape(a)}</a></li>' for a in areas) + '</ol></nav>']
    for a in areas:
        rows = sorted(by[a], key=lambda s: str(s["name"]).casefold())
        out.append(f'<h2 id="{area_slug(a)}">{escape(a)}</h2>')
        out.append('<ul class="spots">' + "".join(f'<li><a href="spot/{escape(str(s["id"]))}/">{escape(str(s["name"]))}</a></li>'
                                                   for s in rows) + '</ul>')
    out.append('<p>A spot missing? <a href="feedback.html?type=spot">Ask for it to be added</a>.</p>')
    return "\n".join(out)


def write_every_spot(site: Path, spots: list[dict], root: str, token: str | None = None) -> None:
    """spots.html, from the spots with a page of their own (write_pages passes the ones it wrote)."""
    slots = {"mark": MARK, "body": every_spot_body(spots), "description": escape(EVERY_SPOT_DESCRIPTION),
             "url": escape(f"{root}spots.html")}
    page = EVERY_SPOT.read_text()
    missing = set(re.findall(r"\{\{(\w+)\}\}", page)) - slots.keys()
    if missing:
        raise ValueError(f"spots.html has slots this build does not fill: {sorted(missing)}")
    (site / "spots.html").write_text(with_counter(re.sub(r"\{\{(\w+)\}\}", lambda m: slots[m.group(1)], page), token))


def write_cards(site: Path, results: list[dict], generated_at: str, root: str, alerts_ok: bool = True) -> dict:
    """site/cards/: the weekend and storm cards, their captions and the unlisted page that shows them
    (src/dipcast/cards.py). The weekend levels are this run's alerts.json, the page's own rules; a
    copy left from an earlier run is not used. Nothing here stops the build: a failure is a warning
    in the build log, and the site publishes without the cards."""
    try:
        from dipcast import cards
        path = site / "data" / "alerts.json"
        alerts = json.loads(path.read_text()) if alerts_ok and path.exists() else None
        if alerts is not None and alerts.get("generated_at") != generated_at:
            alerts = None
        return cards.write_cards(site / "cards", results, alerts, generated_at, root)
    except Exception as e:  # noqa: BLE001 - cards to post must never stop the site publishing
        log.warning("cards not written: %s", e)
        return {"warning": f"cards not written: {e}"}


def write_spot_cards(site: Path, results: list[dict], generated_at: str, alerts_ok: bool = True) -> dict[str, str]:
    """site/cards/spot/<id>.png, each spot's share card with its level in the page's own words (this
    run's alerts.json; src/dipcast/cards.py). Returns {id: alt}. Nothing here stops the build: without
    the cards the pages keep the shared picture, and the log says why."""
    try:
        from dipcast import cards
        path = site / "data" / "alerts.json"
        alerts = json.loads(path.read_text()) if alerts_ok and path.exists() else None
        return cards.write_spot_cards(site / "cards" / "spot", results, alerts, generated_at)
    except Exception as e:  # noqa: BLE001 - a picture for previews must never stop the site publishing
        log.warning("spot share cards not written: %s", e)
        return {}


def write_sign(site: Path, spot: dict, root: str, token: str | None = None) -> None:
    """A spot's sign, spot/<id>/sign/index.html, and its QR code as a file, spot/<id>/qr.svg."""
    from dipcast.signs import page_url, qr_file, sign_page
    (site / "spot" / spot["id"] / "sign").mkdir(parents=True, exist_ok=True)
    (site / "spot" / spot["id"] / "sign" / "index.html").write_text(with_counter(sign_page(spot, root, MARK), token))
    (site / "spot" / spot["id"] / "qr.svg").write_text(qr_file(page_url(root, spot["id"])))


def build(refresh: bool = True) -> dict:
    t0 = time.time()
    require_spill_model()
    if refresh:
        refresh_all(_net())
        reload_caches()
    spots = load_spots()
    prefetch_rain(spots)
    results, upstream, traces = [], {}, {}
    for r in spots.itertuples(index=False):
        try:
            kind, river = spot_hints(r.kind, r.river)
            f = forecast_point(float(r.lat), float(r.lon), gauge=False, include_contributors=ALL_CONTRIBUTORS,
                               kind_hint=kind, river_hint=river, name=r.name, ensemble=True)
            upstream[r.id] = f.get("contributors", [])   # all of them, for the organisers' page
            f["contributors"] = f.get("contributors", [])[:KEEP_CONTRIBUTORS]
        except Exception as e:  # noqa: BLE001 - one bad spot must not sink the site
            log.error("%s: %s", r.name, e)
            f = {"error": f"forecast failed: {e}"}
        try:   # the river the forecast traced, for the spot's map (write_traces)
            traces[r.id] = spot_trace(_net(), float(r.lat), float(r.lon), r.kind, r.river, r.name)
        except Exception as e:  # noqa: BLE001 - a map line must not sink the site
            log.warning("%s: no upstream trace (%s)", r.name, e)
        results.append({"id": r.id, "name": r.name, "kind": r.kind, "river": _river_of(r), "source": r.source,
                        "notes": r.notes, "lat": float(r.lat), "lon": float(r.lon),
                        **({"area": r.area} if getattr(r, "area", "") else {}),   # the list's groups in A-Z
                        **({"osm_id": r.osm_id} if getattr(r, "osm_id", "") else {}), **f})
    attach_companies(results, upstream)
    attach_access(results)
    guides = attach_guides(results)   # practical guides from guides/: parking, paths, entry and exit
    n_algae = attach_algae(results, fetch=refresh)
    n_lab = attach_lab_samples(results)   # read from the samples refresh_all's scoring fetched: no request
    measured = attach_measured(results)   # lab results organisations sent, from samples/: not part of the level
    n_classified = attach_classifications(results)
    water_body = attach_water_body(results)   # the EA's reasons for not reaching good status, from a file: no request
    upgrades = attach_upgrades(results)   # notes on announced upgrades, after the forecasts: the model never reads them
    dry = attach_dry_weather(results)   # notes on past dry-weather spills, from a file: the model never reads them
    # Network only, like the levels, and before their EA requests: one request for the national flood
    # list, two for the water temperatures.
    any_floods = asked_now(ask_flood_list) if refresh else None
    n_water_temp = attach_water_temperature(results) if refresh else 0
    n_levels = attach_river_levels(results) if refresh else 0   # observations beside the forecast, network only
    n_flows = attach_flow_state(results, any_alerts=any_floods) if refresh else {}   # river high or rising, flood alerts: not part of the level
    n_weather = attach_weather(results) if refresh else 0
    generated = pd.Timestamp.now(tz="Europe/London")
    # Raises before anything is written if the build is bad. The live check needs this run's poll.
    health = build_health(results, samples_status(), load_poll_log() if refresh else None,
                          duplicate_overflow_ids=snapshot_duplicates(), rain_fallback=fallback_summary())
    health["algae_checks"], health["classifications"] = n_algae, n_classified
    health["upgrade_notes"] = {"overflows": upgrades["overflows"], "spots": upgrades["spots"]}
    health["warnings"] += upgrades["warnings"]
    health["dry_weather_notes"] = {"overflows": dry["overflows"], "spots": dry["spots"]}
    health["warnings"] += dry["warnings"]
    health["lab_samples"] = n_lab
    if water_body is None:
        health["warnings"].append("data/raw/rnags.json is missing or unreadable: no spot says what the Environment Agency lists on its water body")
    else:
        health["water_bodies"] = water_body[0]
        if water_body[1]:
            health["warnings"].append(f"{len(water_body[1])} spot{'' if len(water_body[1]) == 1 else 's'} not in data/raw/rnags.json "
                                      f"(rerun scripts/make_rnags.py): {', '.join(water_body[1][:10])}")
    near = near_uncounted(results, upstream, _overflows())
    if near:
        health["near_uncounted"] = near
        health["warnings"].append(
            f"{len(near)} overflow{'' if len(near) == 1 else 's'} within {NEAR_SPOT_M:.0f} m of a spot not counted there "
            "(an outfall at the spot should count; place it in data/raw/overflow_joins.csv): "
            + "; ".join(f"{n['site_id']} {n['metres']} m from {n['spot']}" for n in near))
    unsure = unsure_joins(upstream)
    if unsure:
        health["unsure_joins"] = unsure
        health["warnings"].append(
            f"{len(unsure)} counted overflow{'' if len(unsure) == 1 else 's'} may join the river below the spot "
            "(check where each one's stream meets the river and add it to data/raw/overflow_joins.csv): "
            + "; ".join(f"{u['site_id']} for {u['spot']}, {u['snap_m']} m off the river, {u['km']} km above, "
                        f"into {u['receiving']}" for u in unsure))
    # How the spots are joined by water, for the reasons on the Nearby card (spot_links), from every overflow
    # each forecast counted, not the ten a spot keeps: the catchment in the lite file, the links in each
    # spot's own (DETAIL_FIELDS), which only its page reads.
    # A reason beside a suggestion must never sink the site: if the links fail, the cards give none.
    try:
        health["spot_links"] = attach_spot_links(results, spots, upstream, _net())
    except Exception as e:  # noqa: BLE001
        health["spot_links"] = 0
        health["warnings"].append(f"Nearby reasons not made this update: {e}")
    health["river_levels"], health["weather"] = n_levels, n_weather
    health.update(n_flows)
    if n_flows.get("flood_alerts_unchecked"):
        health["warnings"].append(f"flood alerts not checked for {n_flows['flood_alerts_unchecked']} of {len(results)} spots: "
                                  "the Environment Agency did not answer; their pages say so")
    health["water_temperature"] = n_water_temp
    health["guides"] = guides["guides"]
    health["warnings"] += guides["warnings"]
    health["measured"] = {"spots": measured["spots"], "samples": measured["samples"]}
    health["warnings"] += measured["warnings"]
    for w in health["warnings"]:
        announce(w)
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    credits = data_credits(site_url())
    health["anypoint"] = write_any_point(SITE, credits)
    health["guide_photos"] = copy_photos(SITE, results)
    from dipcast.coastal import attach_samples
    from dipcast.coastal import fetch as fetch_coastal
    # The latest statutory sample at each site from the EA's archive, kept six hours in the cache.
    coastal = attach_samples(fetch_coastal(), cache=config.CACHE / "coastal_samples.json")
    (SITE / "data" / "coastal.json").write_text(json.dumps(coastal))
    health["coastal"] = {"status": coastal["status"], "sites": len(coastal["sites"]),
                         "samples": coastal.get("samples", {}).get("state"),
                         "with_sample": sum((s.get("sample") or {}).get("state") == "ok" for s in coastal["sites"])}
    # Welsh bathing waters: NRW's sites and latest samples, live or from the dated snapshot (wales.py).
    from dipcast.wales import fetch as fetch_wales
    wales = fetch_wales()
    (SITE / "data" / "wales.json").write_text(json.dumps(wales))
    health["wales"] = {"state": wales["state"], "sites": len(wales["sites"]), "fetched_at": wales["fetched_at"],
                       **({"error": wales["error"]} if wales.get("error") else {})}
    # Scottish bathing waters: SEPA's points layer, names, ratings and links (scotland.py).
    from dipcast.scotland import fetch as fetch_scotland
    scotland = fetch_scotland()
    (SITE / "data" / "scotland.json").write_text(json.dumps(scotland))
    health["scotland"] = {"state": scotland["state"], "sites": len(scotland["sites"]),
                          **({"error": scotland["error"]} if scotland.get("error") else {})}
    # The Republic of Ireland's bathing waters: the EPA's list, samples and restrictions (ireland.py).
    from dipcast.ireland import fetch as fetch_ireland
    ireland = fetch_ireland()
    (SITE / "data" / "ireland.json").write_text(json.dumps(ireland))
    health["ireland"] = {"state": ireland["state"], "sites": len(ireland["sites"]),
                         "restrictions": sum(len(s["alerts"] or []) for s in ireland["sites"]),
                         **({"error": ireland["error"]} if ireland.get("error") else {})}
    # Northern Ireland's bathing waters: DAERA's monitoring points layer (northern_ireland.py).
    from dipcast.northern_ireland import fetch as fetch_ni
    northern_ireland = fetch_ni()
    (SITE / "data" / "northern_ireland.json").write_text(json.dumps(northern_ireland))
    health["northern_ireland"] = {"state": northern_ireland["state"], "sites": len(northern_ireland["sites"]),
                                  **({"error": northern_ireland["error"]} if northern_ireland.get("error") else {})}
    push, email = push_config(), email_config()
    doc = {"generated_at": generated.isoformat(), "version": __version__, "n": len(results), "build": health,
           "lead_skill": lead_skill(), "ecoli_check": ecoli_check(),
           **({"push": push} if push else {}), **({"email": email} if email else {}),
           "commit": code_commit(), "credits": credits, "spots": results}
    (SITE / "data" / "spots.json").write_text(json.dumps(doc, default=str))
    write_app_data(SITE, doc)   # spots-lite.json and data/spot/<id>.json, what the app loads
    health["trace_files"] = write_traces(SITE, traces, upstream, generated, credits)   # data/spot/<id>-trace.json, after write_app_data clears data/spot/
    alerts_ok = write_alerts(SITE, site_url(), push is not None or email is not None)   # carries the credits from spots.json
    spot_cards = write_spot_cards(SITE, results, generated.isoformat(), alerts_ok)   # before the pages, which point at them
    health["spot_cards"] = len(spot_cards)
    health["upstream_files"] = write_upstream(SITE, upstream, generated, credits)
    # GeoJSON allows extra top-level members, so the credits sit beside the features.
    geo = {**overflows_geojson(limit=20000), "credits": credits}
    (SITE / "data" / "overflows.geojson").write_text(json.dumps(geo, default=str))
    health["overflow_tiles"] = write_overflow_tiles(SITE, geo)   # what the map loads, a few tiles at a time
    if refresh:   # the run log, before verification.json reads it (forecast_log.service_record)
        from dipcast.forecast_log import log_build
        log_build(health, generated)
    (SITE / "data" / "verification.json").write_text(json.dumps({**load_verification(), "credits": credits}, default=str))
    health["scored_rows_published"] = publish_scored_csv(SITE, credits, site_url())
    health["spot_rows_published"] = publish_spots_csv(SITE, credits, site_url())
    # How the forecast has done at each spot's upstream overflows, from that CSV: before the pages, for data.html.
    from dipcast import spot_scores
    health["spot_scores"] = spot_scores.write(SITE, upstream, generated, credits)
    token = os.environ.get(COUNTER_TOKEN_ENV, "").strip()
    health["spot_pages"] = write_pages(SITE, results, token, day=generated.date().isoformat(), push=push is not None,
                                       coastal=coastal, wales=wales, scotland=scotland, email=email is not None,
                                       ireland=ireland, northern_ireland=northern_ireland, support=support_url(), tiles=tile_config(),
                                       push_dates=bool(push and push.get("dates")),
                                       spot_cards=spot_cards, cards_v=generated.strftime("%Y%m%d%H%M"),
                                       overflows=_overflows(), generated=generated)
    # Swimmers' reviews: the published ones into site/reviews/, and their sections into the pages just written.
    from dipcast.reviews import write_reviews
    try:
        health["reviews"] = write_reviews(SITE, spot_ids=[r["id"] for r in results], fetch=refresh)
    except Exception as e:  # noqa: BLE001 - reviews beside the forecast must never stop the site publishing
        health["reviews"] = {"warning": f"reviews not written, so the site shows none this time: {e}"}
    if health["reviews"].get("warning"):
        announce(health["reviews"]["warning"])
    # Cards to post to Instagram and Facebook, at site/cards/: last, from what is written above.
    health["cards"] = write_cards(SITE, results, generated.isoformat(), site_url(), alerts_ok)
    summary = {**health, "seconds": round(time.time() - t0, 1), "generated_at": generated.isoformat()}
    summary.pop("failed_spots", None)
    if refresh and config.SCOTTISH_WATER:
        # Shadow only (docs/SCOTLAND-PLAN-2026-10.md, S5): after everything the site publishes is written, so it can
        # change none of it, and last, away from the spots' and click-anywhere's rain requests. It writes
        # to the state directory alone; the build log gets counts and costs, no scores.
        from dipcast.scottish_shadow import run as scottish_shadow
        summary["scottish_water_shadow"] = scottish_shadow(_net())
    if refresh:
        # Open-Meteo calls since 00:00 UTC by every build that day, and what the ration held back; the
        # requests this build sent, retries included, and what the ensemble's did. Over
        # MAX_OPEN_METEO_REQUESTS, the build warns.
        summary["open_meteo"] = rainfall.calls_today()
        summary["open_meteo_requests"] = rainfall.requests_made()
        summary["rain_ensemble"] = rainfall.ensemble_summary()
        if summary["open_meteo_requests"]["total"] > MAX_OPEN_METEO_REQUESTS:
            announce(f"{summary['open_meteo_requests']['total']} Open-Meteo requests in this build, over "
                     f"{MAX_OPEN_METEO_REQUESTS}: {summary['open_meteo_requests']['by_host']}")
    log.info("site built: %s", summary)
    return summary


if __name__ == "__main__":
    try:
        print(build(refresh="--no-refresh" not in sys.argv))
    except BuildUnhealthy as e:
        log.error("%s", e)
        if "--no-refresh" not in sys.argv:   # a run that did not publish is in the run log too
            from dipcast.forecast_log import log_build
            log_build(None, pd.Timestamp.now(tz="Europe/London"), failed=str(e))
        sys.exit(2)
