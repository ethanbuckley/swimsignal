"""Official Welsh bathing-water observations from Natural Resources Wales, kept separate from our
inland forecast: no Welsh forecast is made here.

NRW publishes its bathing waters, their ratings, each site's latest in-season sample and its daily
pollution-risk forecasts through an OGL API on the EA's data platform. That platform's gateway
refuses GitHub's runners (HTTP 403 on all three Welsh endpoints, checked from a runner on 3 Oct
2026), so the build publishes a dated snapshot of the sites and samples
(data/raw/wales_bathing_waters.json, written off CI by scripts/fetch_wales.py), and the coverage
page asks NRW for the current samples and forecasts in the reader's browser when the Welsh list is
opened, which NRW allows (access-control-allow-origin: *). A snapshot never carries a forecast.
"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

import httpx

from dipcast import config
from dipcast.coastal import ID, TZ, instant, uri, value, when

BASE = "https://environment.data.gov.uk/wales/bathing-waters/doc"
SITES = f"{BASE}/bathing-water.json"
SAMPLES = f"{BASE}/bathing-water-quality/in-season/latest.json"
PREDICTIONS = f"{BASE}/bathing-water-quality/stp-risk-prediction/latest.json"
LICENCE = "https://environment.data.gov.uk/wales/bathing-waters/"
CREDIT = ("Contains Natural Resources Wales information © Natural Resources Wales and Database Right. "
          "All rights reserved. Open Government Licence v3.0.")
PROFILE = "https://environment.data.gov.uk/wales/bathing-waters/profiles/profile.html?site={}"
SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "wales_bathing_waters.json"
KINDS = {"CoastalBathingWater": "coast", "TransitionalBathingWater": "estuary",
         "LakeBathingWater": "lake", "RiverBathingWater": "river"}
RATINGS = {"Excellent", "Good", "Sufficient", "Poor"}
PAGE = 200   # the API's documented page limit; 114 sites on 3 Oct 2026


def _count(n, qualifier) -> dict | None:
    """A bacterial count and its qualifier ("<" below the detection limit), or None."""
    if isinstance(n, bool) or not isinstance(n, (int, float)) or n < 0:
        return None
    q = (qualifier or {}).get("countQualifierNotation") if isinstance(qualifier, dict) else None
    return {"value": float(n), "qualifier": q if q in ("<", ">") else "="}


def parse_sites(items: list) -> list[dict]:
    """Each bathing water: id, name, kind (coast, estuary, lake or river), the latest rating with
    its year, and its official profile. Raises on a missing or duplicated id or name, so that a
    changed source cannot publish a partial list."""
    out, seen = [], set()
    for item in items:
        kinds = [KINDS[t.rsplit("/", 1)[-1]] for t in item.get("type", []) if t.rsplit("/", 1)[-1] in KINDS]
        if not kinds:
            continue
        key, name = item.get("eubwidNotation", ""), value(item.get("name"))
        if not ID.fullmatch(key) or not isinstance(name, str) or not name.strip() or key in seen:
            raise ValueError("invalid or duplicate Welsh bathing water")
        seen.add(key)
        assessment = item.get("latestComplianceAssessment") or {}
        rating = value((assessment.get("complianceClassification") or {}).get("name"))
        link = str(uri(assessment) or "")   # none yet for a newly designated water
        year = link.rsplit("/year/", 1)[-1] if "/year/" in link else ""
        out.append({"id": key, "name": name.strip(), "kind": kinds[0],
                    "rating": {"value": rating, "year": int(year), "source": link}
                    if rating in RATINGS and year.isdigit() else None,
                    "profile": PROFILE.format(key)})
    return sorted(out, key=lambda s: s["name"].casefold())


def parse_samples(items: list) -> dict[str, dict]:
    """{site id: its latest in-season sample}: sampling time (UK time) and both counts per 100 ml.
    A sample without a readable time or E. coli count is left out."""
    out = {}
    for item in items:
        key = (item.get("bwq_bathingWater") or {}).get("eubwidNotation", "")
        try:
            taken = instant((item.get("sampleDateTime") or {}).get("inXSDDateTime"))
        except (ValueError, TypeError):
            continue
        ecoli = _count(item.get("escherichiaColiCount"), item.get("escherichiaColiQualifier"))
        if not ID.fullmatch(key) or ecoli is None or (key in out and out[key]["taken_at"] >= taken.isoformat()):
            continue
        out[key] = {"taken_at": taken.isoformat(), "ecoli": ecoli,
                    "enterococci": _count(item.get("intestinalEnterococciCount"), item.get("intestinalEnterococciQualifier"))}
    return out


def snapshot_from(site_items: list, sample_items: list, fetched_at: str) -> dict:
    """Sites with their latest samples, as published and as kept off CI. No forecasts."""
    sites, samples = parse_sites(site_items), parse_samples(sample_items)
    if not sites:
        raise ValueError("no Welsh bathing waters")
    for s in sites:
        s["sample"] = {"state": "ok", **samples[s["id"]]} if s["id"] in samples else {"state": "none"}
    return {"fetched_at": fetched_at, "source": SITES, "samples_source": SAMPLES, "licence": LICENCE,
            "credit": CREDIT, "sites": sites}


def _items(client: httpx.Client, url: str) -> list:
    r = client.get(url, params={"_pageSize": PAGE}, timeout=15)
    r.raise_for_status()
    items = r.json()["result"]["items"]
    if not isinstance(items, list) or len(items) >= PAGE:
        raise ValueError("unexpected Welsh source page")
    return items


def fetch(now: datetime | None = None, client: httpx.Client | None = None, seed: Path | None = None) -> dict:
    """The Welsh directory for the build: live if NRW's service answers (two requests, stopping at
    the first refusal), else the dated snapshot (`state` "cached"), else an empty list ("unavailable").
    Never raises: the directory sits beside the inland forecast."""
    now = now or datetime.now(TZ)
    own = client is None
    client = client or httpx.Client(headers=config.EA_HEADERS, follow_redirects=False)
    try:
        try:
            snap = snapshot_from(_items(client, SITES), _items(client, SAMPLES), now.isoformat())
            return {**snap, "state": "live"}
        except Exception as e:  # noqa: BLE001 - one refusal is enough: no retry, no second endpoint
            error = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
        try:
            kept = json.loads(Path(seed or SNAPSHOT).read_text())
            if kept.get("source") != SITES or instant(kept["fetched_at"]) > now:
                raise ValueError("invalid Welsh snapshot")
            snap = snapshot_from(kept["site_items"], kept["sample_items"], kept["fetched_at"])
            return {**snap, "state": "cached", "error": error}
        except (OSError, ValueError, KeyError, TypeError) as e:
            return {"fetched_at": now.isoformat(), "source": SITES, "licence": LICENCE, "credit": CREDIT,
                    "sites": [], "state": "unavailable", "error": f"{error}; snapshot: {type(e).__name__}"}
    finally:
        if own:
            client.close()


def _sample_text(sample: dict) -> str:
    if sample.get("state") != "ok":
        return "No in-season sample listed"
    count = lambda r: escape(f'{"" if r["qualifier"] == "=" else r["qualifier"]}{r["value"]:,.0f}')   # noqa: E731
    ent = sample.get("enterococci")
    return (f'Latest NRW sample {when(sample["taken_at"])}: E. coli {count(sample["ecoli"])}'
            + (f', intestinal enterococci {count(ent)}' if ent else '') + ' per 100 ml')


def render(snapshot: dict) -> str:
    """The Welsh list, server-rendered so it works without JavaScript. Every line carries its date.
    The page's script (coverage.html) replaces the samples with NRW's current ones and fills the
    forecast line when the list is opened; without it, the forecast line points to the profile."""
    if not snapshot or not snapshot.get("sites"):
        return '<p>The Welsh list could not be loaded for this build. Use the NRW link above.</p>'
    cards = []
    for s in snapshot["sites"]:
        rating = f'{s["rating"]["year"]} rating: {s["rating"]["value"]}' if s["rating"] else "No rating yet"
        sample = s["sample"]
        cards.append(f'<li class="wales-site" data-site="{escape(s["id"], quote=True)}"'
                     + (f' data-sample-at="{escape(sample["taken_at"], quote=True)}"' if sample.get("state") == "ok" else '') + '>'
                     f'<a href="{escape(s["profile"], quote=True)}">{escape(s["name"])}</a>'
                     f'<p class="small">{escape(s["kind"].title())} · {escape(rating)}<br>'
                     f'<span class="wales-advice">Current NRW forecast: open the profile</span><br>'
                     f'<span class="wales-sample">{_sample_text(sample)}</span></p></li>')
    inland = sum(s["kind"] in ("lake", "river") for s in snapshot["sites"])
    dated = (f'Snapshot of sites and samples {when(snapshot["fetched_at"])}.' if snapshot.get("state") != "live"
             else f'Sites and samples as published {when(snapshot["fetched_at"])}.')
    return (f'<p class="small">{len(cards)} designated Welsh bathing waters, {inland} of them on lakes or rivers. '
            f'{dated} NRW forecasts pollution risk at some sites in the season; a forecast of no increased risk '
            'is not a water test, and no forecast does not mean clean water.</p>'
            '<p class="small" id="wales-status" aria-live="polite"></p>'
            '<label for="wales-search">Find a Welsh bathing water</label> '
            '<input type="search" id="wales-search" placeholder="Bathing-water name">'
            f'<p id="wales-count" class="small" aria-live="polite">{len(cards)} sites</p>'
            '<ul id="wales-sites">' + ''.join(cards) + '</ul>'
            f'<p class="small">{escape(CREDIT)} <a href="{LICENCE}">Source and licence</a>. '
            'NRW does not endorse SwimSignal.</p>')
