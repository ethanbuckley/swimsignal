"""Scottish bathing waters from SEPA, kept separate from our inland forecast: no Scottish
forecast is made here, and nothing here is a current water-quality statement.

SEPA's environmental-data page lists "Bathing Water Points" for map view, download, WMS and REST
under the Open Government Licence (its link is to version 2.0); its REST layer is the one read
here, with each water's name, latest rating and year, and a link to SEPA's own page for it. The
"Locations" results site, where SEPA shows samples, and the signs' daily predictions carry "SEPA
website conditions of use" or no stated licence (checked 3 Oct 2026), so neither is read: each
entry links to SEPA's page for its signs, samples and current advice. The layer answers GitHub's
runners (checked from a runner on 3 Oct 2026).
"""

from __future__ import annotations

import re
from datetime import datetime
from html import escape

import httpx

from dipcast import config
from dipcast.coastal import TZ, when

LAYER = "https://map.sepa.org.uk/server/rest/services/Open/Environmental_Monitoring/MapServer/1/query"
SOURCE = "https://www.sepa.org.uk/environment/environmental-data/"
LICENCE = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/2/"
CREDIT = ("Contains public sector information licensed under the Open Government Licence v2.0: "
          "SEPA bathing water points.")
RATINGS = {"Excellent", "Good", "Sufficient", "Poor"}
PAGE = re.compile(r"https://bathingwaters\.sepa\.org\.uk/locations-and-results/results/?\?location=(\d{3,7})\Z")
MAX_FEATURES = 1000   # the layer's own transfer limit; 90 waters on 3 Oct 2026


def parse(features: list) -> list[dict]:
    """Each water: SEPA's location code as `id`, `name`, latest `rating` and year (None for a water
    not yet rated, "Unclassified" in SEPA's words), its SEPA page and its point. Raises on a missing
    name or page link, or a repeated code, so that a changed layer cannot publish a partial list."""
    out, seen = [], set()
    for f in features:
        a, g = (f or {}).get("attributes") or {}, (f or {}).get("geometry") or {}
        name, link = a.get("description"), PAGE.fullmatch(str(a.get("bw_url") or "").strip())
        if not isinstance(name, str) or not name.strip() or not link or link[1] in seen:
            raise ValueError("invalid or repeated SEPA bathing water")
        seen.add(link[1])
        year, rating = a.get("year"), a.get("class_description")
        try:
            lat, lon = round(float(g["y"]), 5), round(float(g["x"]), 5)
        except (KeyError, TypeError, ValueError):
            lat = lon = None
        out.append({"id": f"sepa-{link[1]}", "name": name.strip(), "page": link[0],
                     "rating": {"value": rating, "year": int(year)} if rating in RATINGS and isinstance(year, int) else None,
                     "unrated_year": int(year) if rating == "Unclassified" and isinstance(year, int) else None,
                     "lat": lat, "lon": lon})
    return sorted(out, key=lambda s: s["name"].casefold())


def fetch(now: datetime | None = None, client: httpx.Client | None = None) -> dict:
    """One request; `state` "live" or "unavailable" (with the error). Never raises."""
    now = now or datetime.now(TZ)
    snap = {"fetched_at": now.isoformat(), "source": SOURCE, "layer": LAYER, "licence": LICENCE, "credit": CREDIT, "sites": []}
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": config.USER_AGENT}, follow_redirects=False)
    try:
        r = client.get(LAYER, params={"where": "1=1", "outFields": "description,year,class_description,bw_url",
                                      "outSR": 4326, "f": "json"}, timeout=15)
        r.raise_for_status()
        body = r.json()
        features = body.get("features")
        if not isinstance(features, list) or body.get("exceededTransferLimit") or len(features) >= MAX_FEATURES:
            raise ValueError("unexpected SEPA layer answer")
        snap["sites"] = parse(features)
        if not snap["sites"]:
            raise ValueError("no SEPA bathing waters")
        return {**snap, "state": "live"}
    except Exception as e:  # noqa: BLE001 - the list sits beside the inland forecast
        error = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
        return {**snap, "sites": [], "state": "unavailable", "error": error}
    finally:
        if own:
            client.close()


def render(snapshot: dict) -> str:
    """The Scottish list, server-rendered and searchable on the page. Ratings only: signs, samples
    and current advice are on each water's SEPA page."""
    if not snapshot or not snapshot.get("sites"):
        return "<p>The Scottish list could not be loaded for this build. Use SEPA's link above.</p>"
    cards = []
    for s in snapshot["sites"]:
        rating = (f'{s["rating"]["year"]} rating: {s["rating"]["value"]}' if s["rating"]
                  else f'Not yet rated (SEPA: unclassified, {s["unrated_year"]})' if s.get("unrated_year") else "No rating listed")
        cards.append(f'<li class="scotland-site"><a href="{escape(s["page"], quote=True)}">{escape(s["name"])}</a>'
                     f'<p class="small">{escape(rating)}<br>Signs, samples and current advice: on SEPA\'s page</p></li>')
    return (f'<p class="small">{len(cards)} designated Scottish bathing waters, as SEPA listed them '
            f'{when(snapshot["fetched_at"])}. A rating covers up to four seasons of samples; it is not '
            'today\'s water quality.</p>'
            '<label for="scotland-search">Find a Scottish bathing water</label> '
            '<input type="search" id="scotland-search" placeholder="Bathing-water name">'
            f'<p id="scotland-count" class="small" aria-live="polite">{len(cards)} sites</p>'
            '<ul id="scotland-sites">' + ''.join(cards) + '</ul>'
            f'<p class="small">{escape(CREDIT)} <a href="{SOURCE}">Source</a> · <a href="{LICENCE}">Licence</a>. '
            'SEPA does not endorse SwimSignal.</p>')
