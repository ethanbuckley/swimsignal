"""Official English coastal observations, kept separate from our inland forecast."""

from datetime import datetime, timedelta
from html import escape
import json
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

CATALOGUE = "https://environment.data.gov.uk/doc/bathing-water.json"
PREDICTIONS = "https://environment.data.gov.uk/doc/bathing-water-quality/stp-risk-prediction.json"
LICENCE = "https://environment.data.gov.uk/bwq/"
CREDIT = "Environment Agency copyright and/or database right, Open Government Licence v3.0."
TZ = ZoneInfo("Europe/London")
FALLBACK = Path(__file__).resolve().parents[2] / "data" / "raw" / "coastal_catalogue.json"
ID = re.compile(r"uk[a-z0-9]+-\d{5}\Z")
KINDS = {"CoastalBathingWater": "coast", "TransitionalBathingWater": "estuary"}


def value(x):
    return x.get("_value") if isinstance(x, dict) else x


def uri(x):
    return x.get("_about", "") if isinstance(x, dict) else x or ""


def instant(x):
    stamp = pd.Timestamp(value(x))
    if pd.isna(stamp):
        raise ValueError("missing time")
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("Europe/London", ambiguous="raise", nonexistent="raise")
    return stamp.to_pydatetime()


def parse(catalogue, predictions, now, advice_available=True):
    """A normal NON_PRF_SITE record does not establish an official forecast or clean water."""
    by_site = {}
    for p in predictions:
        key = uri(p.get("stp_bathingWater")).rsplit("/", 1)[-1]
        by_site.setdefault(key, []).append(p)
    sites = []
    seen = set()
    for item in catalogue:
        kinds = [KINDS[t.rsplit("/", 1)[-1]] for t in item.get("type", [])
                 if t.rsplit("/", 1)[-1] in KINDS]
        if not kinds:
            continue
        key = item.get("eubwidNotation", "")
        name = value(item.get("name"))
        if not ID.fullmatch(key) or not isinstance(name, str) or not name.strip() or key in seen:
            raise ValueError("invalid or duplicate bathing water")
        seen.add(key)
        assessment = item.get("latestComplianceAssessment", {})
        classification = value(assessment.get("complianceClassification", {}).get("name"))
        year = re.search(r"/year/(\d{4})\Z", uri(assessment))
        rating = {"value": classification, "year": int(year[1]), "source": uri(assessment)} \
            if classification in {"Excellent", "Good", "Sufficient", "Poor"} and year else None
        advice = {"state": "unavailable" if not advice_available else "no_current_advice"}
        current = []
        for p in by_site.get(key, []):
            try:
                published, predicted, expires = (instant(p.get(k)) for k in ("publishedAt", "predictedAt", "expiresAt"))
                day = value(p.get("predictedOn"))
                level = uri(p.get("riskLevel")).rsplit("/", 1)[-1]
                origin = p.get("prfOriginType")
                if (predicted <= published <= now < expires and expires - predicted <= timedelta(hours=36)
                        and day == predicted.astimezone(TZ).date().isoformat()
                        and level in {"normal", "increased"} and origin in {"PRF_PROVIDED", "NON_PRF_SITE"}):
                    current.append({"state": "increased" if level == "increased" else
                                    "no_increased_risk" if origin == "PRF_PROVIDED" else "no_forecast",
                                    "origin": origin, "predicted_at": predicted.isoformat(),
                                    "published_at": published.isoformat(), "expires_at": expires.isoformat(),
                                    "source": uri(p)})
            except (ValueError, TypeError, OverflowError):
                continue
        if advice_available and current:
            # Overlapping source records must agree; conflicting ones are not an all-clear.
            if len({p["state"] for p in current}) > 1:
                advice = {"state": "unavailable"}
            else:
                advice = max(current, key=lambda p: datetime.fromisoformat(p["published_at"]))
        sites.append({"id": key, "name": name.strip(), "kind": kinds[0], "rating": rating,
                      "advice": advice, "profile": f"https://environment.data.gov.uk/bwq/profiles/profile.html?site={key}"})
    return sorted(sites, key=lambda s: s["name"].casefold())


def fetch(now=None, client=None):
    """At most six requests; a shared request budget; failures publish unavailability."""
    now = now or datetime.now(TZ)
    snapshot = {"fetched_at": now.isoformat(), "source": CATALOGUE, "licence": LICENCE,
                "credit": CREDIT, "status": "unavailable", "catalogue_state": "unavailable", "sites": []}
    deadline = time.monotonic() + 40
    own = client is None
    client = client or httpx.Client(follow_redirects=False)

    def items(url, params=None):
        rows = []
        for page in range(2):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("coastal source deadline")
            with client.stream("GET", url, params={**(params or {}), "_pageSize": 500, "_page": page},
                               timeout=min(12, remaining)) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if time.monotonic() > deadline or len(body) > 4_000_000:
                        raise ValueError("source exceeded time or size budget")
            batch = json.loads(body)["result"]["items"]
            if not isinstance(batch, list) or any(not isinstance(x, dict) for x in batch):
                raise ValueError("invalid source rows")
            rows.extend(batch)
            if len(batch) < 500:
                return rows
        raise ValueError("source exceeded bounded page count")

    try:
        blocked = False
        try:
            catalogue = items(CATALOGUE)
            if not parse(catalogue, [], now):
                raise ValueError("empty catalogue")
            snapshot.update(catalogue_state="live", catalogue_fetched_at=now.isoformat())
        except Exception as exc:
            # Stable names and historical ratings can be kept; advice is never cached here.
            blocked = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403, 429}
            snapshot["catalogue_error"] = (f"HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError)
                                            else type(exc).__name__)
            seed = json.loads(FALLBACK.read_text())
            catalogue = seed["items"]
            if seed["source"] != CATALOGUE or not parse(catalogue, [], now) or instant(seed["fetched_at"]) > now:
                raise ValueError("invalid catalogue fallback")
            snapshot.update(catalogue_state="cached", catalogue_fetched_at=seed["fetched_at"])
        predictions, available = [], True
        try:
            if blocked:
                raise ValueError("source refused this build; do not retry")
            # Yesterday can remain valid before this morning's issue; never show expired advice.
            for day in (now.astimezone(TZ).date(), now.astimezone(TZ).date() - timedelta(days=1)):
                predictions.extend(items(PREDICTIONS, {"predictedOn": day.isoformat()}))
        except Exception:
            available = False
        snapshot["sites"] = parse(catalogue, predictions, now, available)
        if not snapshot["sites"]:
            raise ValueError("no coastal sites")
        snapshot["status"] = ("ok" if snapshot["catalogue_state"] == "live" else "catalogue_cached") if available else "advice_unavailable"
    except Exception:
        snapshot["sites"] = []
    finally:
        if own:
            client.close()
    return snapshot


def render(snapshot):
    """Server-rendered list works without JavaScript; dates are always visible."""
    if not snapshot or not snapshot.get("sites"):
        return '<p>The official directory could not be loaded for this build. Use the EA link above.</p>'
    messages = {"increased": "EA: increased pollution risk",
                "no_increased_risk": "EA: no increased pollution risk forecast — not a water test",
                "no_forecast": "No EA pollution risk forecast at this site",
                "no_current_advice": "No current EA advice in this snapshot",
                "unavailable": "Current EA advice unavailable"}
    cards = []
    for site in snapshot["sites"]:
        rating, advice = site["rating"], site["advice"]
        historical = f'{rating["year"]} rating: {rating["value"]}' if rating else "Historical rating unavailable"
        stamp = ''
        if advice.get("expires_at"):
            stamp = f'<br>Issued {escape(advice["published_at"])}; expires {escape(advice["expires_at"])}'
        expiry = f' data-advice-expires="{escape(advice["expires_at"], quote=True)}"' if advice.get("expires_at") else ''
        cards.append(f'<li class="coastal-site"><a href="{escape(site["profile"], quote=True)}">{escape(site["name"])}</a>'
                     f'<p class="small">{escape(site["kind"].title())} · {escape(historical)}<br>'
                     f'<span{expiry}>At snapshot: {messages[advice["state"]]}</span>{stamp}</p></li>')
    return (f'<p class="small">{len(cards)} designated coastal and estuary bathing waters. Snapshot '
            f'{escape(snapshot["fetched_at"])}. Advice can change after this snapshot: open the official profile '
            'and check the signs before swimming. Missing advice does not mean clean water.</p>'
            + (f'<p class="small">The live catalogue could not be retrieved; names and historical ratings use '
               f'the official catalogue retrieved {escape(snapshot["catalogue_fetched_at"])}. '
               'New designations or changed ratings may not be included.</p>' if snapshot.get("catalogue_state") == "cached" else '') +
            '<label for="coastal-search">Find a beach or estuary</label> '
            '<input type="search" id="coastal-search" placeholder="Bathing-water name">'
            f'<p id="coastal-count" class="small" aria-live="polite">{len(cards)} sites</p>'
            '<ul id="coastal-sites">' + ''.join(cards) + '</ul>'
            '<p class="small">Contains Environment Agency data, © Environment Agency copyright and/or '
            'database right, <a href="https://environment.data.gov.uk/bwq/">Open Government Licence v3.0</a>. '
            'The EA does not endorse SwimSignal.</p>')
