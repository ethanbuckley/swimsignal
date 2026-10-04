"""Bathing waters in Northern Ireland from DAERA, kept separate from our inland forecast: SwimSignal
makes no forecast in Northern Ireland, and nothing here is a statement about today's water.

DAERA's Bathing Water Quality Dashboard reads an ArcGIS layer, "Bathing Water Monitoring Points
Public View", which DAERA lets anyone reuse under the Open Government Licence v3.0. For each of its
33 waters it gives the name, coast or inland, confirmed or candidate, a link to the bathing water
profile, a water quality indicator and the sampling time that goes with it. It answered GitHub's
runners on 4 Oct 2026. The samples themselves are HTML tables on DAERA's website, not read here.

One request per build. A good answer is kept in the cache; if DAERA does not answer, the kept copy
is shown with its date for up to three days, then the list says it is unavailable. Rain figures
are left out on purpose (plan section 11, item 5): the list holds DAERA's information only.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from html import escape
from pathlib import Path

import httpx

from dipcast import config
from dipcast.coastal import TZ, instant, when

LAYER = ("https://services-eu1.arcgis.com/kswen6BYexuc1SUk/arcgis/rest/services/"
         "Bathing_Water_Monitoring_Points_Public_View_PRD/FeatureServer/0/query")
FIELDS = ("Unique_Site_ID_Code,Site_name,Type,Status,Activity,Profile__URL,water_quality_indicator,"
          "Sampling_datetime")
SOURCE = "https://www.daera-ni.gov.uk/articles/bathing-water-quality-dashboard"
ABOUT = "https://www.daera-ni.gov.uk/articles/about-bathing-water-quality"
LICENCE = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
CREDIT = ("Contains public sector information licensed under the Open Government Licence v3.0: "
          "DAERA bathing water monitoring points.")
PROFILE = re.compile(r"https://www\.daera-ni\.gov\.uk/[^\s\"'<>]+\Z")
# The layer's coded values and DAERA's names for them, from its field domain on 4 Oct 2026.
INDICATORS = {"Excellent": "Excellent water quality", "Good": "Good water quality",
              "Satisfactory": "Satisfactory water quality", "NoBathing": "Temporary advice against bathing"}
# Season-long advice DAERA states on its "About bathing water quality" page, read 4 Oct 2026, shown
# until the end of the year it names. Keyed by the layer's Unique_Site_ID_Code.
SEASON_ADVICE = {30203: (2026, "DAERA advises against bathing here for the 2026 bathing season, after a Poor rating in 2025.")}
CACHE = config.CACHE / "northern_ireland.json"
KEEP_S = 3 * 86400
MAX_FEATURES = 2000      # the layer's own transfer limit; 33 waters on 4 Oct 2026
OLD_DAYS = 30


def parse(features: list) -> list[dict]:
    """Each water: DAERA's site code as `id`, `name`, `kind` (coast or inland), `candidate`,
    `inactive`, the profile link, the indicator in DAERA's words (with its code) and the sampling
    time in UK time. Raises on a missing name, a repeated code or a profile off DAERA's site, so that
    a changed layer cannot publish a partial list. An indicator not in DAERA's list is kept as given."""
    out, seen = [], set()
    for f in features:
        a = (f or {}).get("attributes") or {}
        code, name = a.get("Unique_Site_ID_Code"), re.sub(r"\s+", " ", str(a.get("Site_name") or "")).strip()
        profile = str(a.get("Profile__URL") or "").strip()
        if not isinstance(code, int) or isinstance(code, bool) or code in seen or not name or not PROFILE.fullmatch(profile):
            raise ValueError("invalid or repeated DAERA bathing water")
        seen.add(code)
        raw, taken = a.get("water_quality_indicator"), a.get("Sampling_datetime")
        try:   # ArcGIS dates are milliseconds since 1970 in UTC
            sampled = datetime.fromtimestamp(taken / 1000, UTC).astimezone(TZ).isoformat() \
                if isinstance(taken, (int, float)) and not isinstance(taken, bool) and taken > 0 else None
        except (OverflowError, OSError, ValueError):
            sampled = None
        out.append({"id": f"daera-{code}", "code": code, "name": name,
                    "kind": "inland" if a.get("Type") == "Inland" else "coast",
                    "candidate": a.get("Status") == "Candidate", "inactive": a.get("Activity") == "Inactive",
                    "profile": profile,
                    "indicator": {"code": raw, "words": INDICATORS.get(raw)} if isinstance(raw, str) and raw.strip() else None,
                    "sampled_at": sampled})
    return sorted(out, key=lambda s: s["name"].casefold())


def _read(client: httpx.Client) -> list[dict]:
    r = client.get(LAYER, params={"where": "1=1", "outFields": FIELDS, "returnGeometry": "false", "f": "json"}, timeout=15)
    r.raise_for_status()
    body = r.json()
    features = body.get("features")
    if not isinstance(features, list) or body.get("exceededTransferLimit") or len(features) >= MAX_FEATURES:
        raise ValueError("unexpected DAERA layer answer")
    sites = parse(features)
    if not sites:
        raise ValueError("no DAERA bathing waters")
    return sites


def fetch(now: datetime | None = None, client: httpx.Client | None = None, cache: Path | None = None) -> dict:
    """One request. `state` "live", "kept" (DAERA did not answer; the copy kept from an earlier build,
    with its time) or "unavailable" (with the error). Never raises."""
    now = now or datetime.now(TZ)
    cache = Path(cache or CACHE)
    snap = {"fetched_at": now.isoformat(), "checked_at": now.isoformat(), "source": SOURCE, "layer": LAYER, "licence": LICENCE, "credit": CREDIT, "sites": []}
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": config.USER_AGENT}, follow_redirects=False)
    try:
        sites = _read(client)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"fetched_at": now.isoformat(), "sites": sites}))
        except OSError:
            pass
        return {**snap, "sites": sites, "state": "live"}
    except Exception as e:  # noqa: BLE001 - the list sits beside the inland forecast
        error = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
    finally:
        if own:
            client.close()
    try:
        kept = json.loads(cache.read_text())
        age = (now - instant(kept["fetched_at"])).total_seconds()
        if not (0 <= age < KEEP_S and isinstance(kept["sites"], list) and kept["sites"]):
            raise ValueError("kept copy too old")
        return {**snap, "fetched_at": kept["fetched_at"], "sites": kept["sites"], "state": "kept", "error": error}
    except (OSError, ValueError, KeyError, TypeError):
        return {**snap, "state": "unavailable", "error": error}


def _line(s: dict, today: date) -> str:
    ind = s.get("indicator")
    if not ind:
        text = "No indicator listed"
    elif ind["words"] is None:
        text = f'DAERA\'s indicator: {escape(ind["code"])} (not a value SwimSignal knows; see the dashboard)'
    elif ind["code"] == "NoBathing":
        text = f'<strong>DAERA: {escape(ind["words"])}</strong>'
    else:
        text = f'DAERA\'s indicator: {escape(ind["words"])}'
    if s.get("sampled_at"):
        text += f'. Sampled {when(s["sampled_at"])}.'
        if (today - instant(s["sampled_at"]).astimezone(TZ).date()).days > OLD_DAYS:
            text += f' More than {OLD_DAYS} days ago.'
    else:
        text += '. No sampling time listed.'
    return text


def render(snapshot: dict) -> str:
    """The Northern Irish list, server-rendered and searchable on the page. Every indicator carries
    its sampling time."""
    if not snapshot or not snapshot.get("sites"):
        return (f'<p>The list for Northern Ireland could not be loaded for this build. Use '
                f'<a href="{SOURCE}">DAERA\'s dashboard</a>.</p>')
    today = instant(snapshot.get("checked_at") or snapshot["fetched_at"]).astimezone(TZ).date()
    cards = []
    for s in snapshot["sites"]:
        about = ["Inland" if s["kind"] == "inland" else "Coast"]
        if s.get("candidate"):
            about.append("candidate bathing water")
        if s.get("inactive"):
            about.append("DAERA lists it as inactive")
        lines = [escape(", ".join(about)), _line(s, today)]
        advice = SEASON_ADVICE.get(s.get("code"))
        if advice and today.year <= advice[0]:
            lines.append(f'{escape(advice[1])} <a href="{ABOUT}">DAERA\'s note</a>')
        cards.append(f'<li class="ni-site"><a href="{escape(s["profile"], quote=True)}">{escape(s["name"])}</a>'
                     f'<p class="small">{"<br>".join(lines)}</p></li>')
    inland = sum(s["kind"] == "inland" for s in snapshot["sites"])
    dated = (f'as DAERA listed them {when(snapshot["fetched_at"])}' if snapshot.get("state") != "kept"
             else f'as DAERA listed them {when(snapshot["fetched_at"])}, kept from an earlier build because DAERA did not answer')
    return (f'<p class="small">{len(cards)} bathing waters, {len(cards) - inland} on the coast and {inland} inland, {dated}. '
            'Each name links to DAERA\'s profile of the water. Each line gives DAERA\'s water quality indicator and the '
            'sampling time DAERA gives with it.</p>'
            '<label for="ni-search">Find a bathing water in Northern Ireland</label> '
            '<input type="search" id="ni-search" placeholder="Bathing-water name">'
            f'<p id="ni-count" class="small" aria-live="polite">{len(cards)} sites</p>'
            '<ul id="ni-sites">' + ''.join(cards) + '</ul>'
            f'<p class="small">{escape(CREDIT)} <a href="{SOURCE}">Source</a> · <a href="{LICENCE}">Licence</a>. '
            'DAERA does not endorse SwimSignal.</p>')
