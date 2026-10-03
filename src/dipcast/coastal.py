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


# ------------------------------------------------------------------------------ dated samples
# The latest statutory sample at each site, from the EA Water Quality Archive: the bathing-water
# service refuses GitHub's runners (ingest/wqa.py), the archive does not. It lags the official
# profile by days, so each result keeps its own sampling time and the page says so.
POINTS = Path(__file__).resolve().parents[2] / "data" / "raw" / "coastal_wqa_points.json"
SAMPLES_SOURCE = "https://environment.data.gov.uk/water-quality"
DETERMINANDS = {"2348": "ecoli", "3723": "enterococci"}   # E. coli and intestinal enterococci, confirmed, by membrane filtration
SAMPLES_TTL_S = 6 * 3600     # the archive is asked at most every six hours ...
SAMPLES_KEEP_S = 3 * 86400   # ... and an older answer is shown, dated, for three days while it does not answer


def sample_window(now):
    """Where to look for the latest sample: the last 35 days in May to October (weekly sampling),
    otherwise from 1 August of the last season, so that a winter page shows September's sample."""
    local = now.astimezone(TZ)
    if 5 <= local.month <= 10:
        return (local - timedelta(days=35)).date()
    return local.date().replace(year=local.year if local.month >= 11 else local.year - 1, month=8, day=1)


def _result(text):
    """'45' -> {"value": 45.0, "qualifier": "="}; '<10' -> {"value": 10.0, "qualifier": "<"}; None if unreadable."""
    t = str(text or "").strip()
    q = t[0] if t[:1] in ("<", ">") else "="
    try:
        v = float(t.lstrip("<>= "))
    except ValueError:
        return None
    return {"value": v, "qualifier": q} if v >= 0 else None


def latest_samples(points, since, observations=None):
    """{bathing water id: its latest statutory (MS) sample}: the sampling time, E. coli and, from the
    same sample, intestinal enterococci (None if that sample has none). Only samples with an E. coli
    result count. A site with no sample since `since` is left out. Raises if the archive fails."""
    from dipcast.ingest import wqa
    observations = observations or wqa._observations
    site_of = {v["point"]: k for k, v in points.items()}
    by = {}
    for code, field in DETERMINANDS.items():
        for o in observations(sorted(site_of), f"{since.isoformat()}T00:00:00", code, wqa.BATHING_PURPOSES, batch=25):
            point = (o.get("hasSamplingPoint") or {}).get("notation")
            r = _result(o.get("hasSimpleResult"))
            if point not in site_of or r is None:
                continue
            try:
                taken = instant(o.get("phenomenonTime"))
            except (ValueError, TypeError):
                continue
            by.setdefault((site_of[point], taken), {})[field] = r
    out = {}
    for (site, taken), results in by.items():
        if "ecoli" in results and (site not in out or taken > out[site][0]):
            out[site] = (taken, results)
    return {site: {"taken_at": t.isoformat(), "ecoli": r["ecoli"], "enterococci": r.get("enterococci"),
                   "point": points[site]["point"]} for site, (t, r) in out.items()}


def attach_samples(snapshot, now=None, points_file=None, cache=None, fetch=None):
    """Each site's `sample`: {"state": "ok", ...latest_samples} or "none" (no sample in the window),
    "unmapped" (no archive point matched, scripts/map_coastal_wqa.py) or "unavailable" (the archive
    did not answer and nothing it said in the last SAMPLES_KEEP_S is kept). The snapshot's `samples`
    says where they came from and when. Never raises: samples sit beside the directory."""
    now = now or datetime.now(TZ)
    fetch = fetch or latest_samples
    info = {"source": SAMPLES_SOURCE, "state": "unavailable"}
    try:
        mapping = json.loads(Path(points_file or POINTS).read_text())
        points = {k: v for k, v in mapping["points"].items() if ID.fullmatch(k) and isinstance(v, dict) and v.get("point")}
        info["points_checked_at"] = mapping.get("checked_at")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        points = {}
    since = sample_window(now)
    info["since"] = since.isoformat()
    found = None
    kept = None
    if cache:
        try:
            kept = json.loads(Path(cache).read_text())
            age = (now - instant(kept["fetched_at"])).total_seconds()
            if not 0 <= age <= SAMPLES_KEEP_S or not isinstance(kept["samples"], dict):
                kept = None
            else:   # the window moves daily: a kept sample from before it is no longer the latest in it
                kept["samples"] = {k: v for k, v in kept["samples"].items()
                                   if instant(v["taken_at"]).astimezone(TZ).date() >= since}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            kept = None
    if kept and (now - instant(kept["fetched_at"])).total_seconds() <= SAMPLES_TTL_S:
        found, info["fetched_at"], info["state"] = kept["samples"], kept["fetched_at"], "ok"
    elif points:
        try:
            found = fetch(points, since)
            info.update(state="ok", fetched_at=now.isoformat())
            if cache:
                Path(cache).parent.mkdir(parents=True, exist_ok=True)
                Path(cache).write_text(json.dumps({"fetched_at": now.isoformat(), "since": since.isoformat(), "samples": found}))
        except Exception as e:  # noqa: BLE001 - samples beside the directory must not stop it
            info["error"] = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
            if kept:
                found, info["fetched_at"], info["state"] = kept["samples"], kept["fetched_at"], "cached"
    for site in snapshot.get("sites", []):
        if site["id"] not in points:
            site["sample"] = {"state": "unmapped"}
        elif found is None:
            site["sample"] = {"state": "unavailable"}
        elif site["id"] in found:
            site["sample"] = {"state": "ok", **found[site["id"]]}
        else:
            site["sample"] = {"state": "none"}
    snapshot["samples"] = info
    return snapshot


def _count(r):
    return escape(f'{"" if r["qualifier"] == "=" else r["qualifier"]}{r["value"]:,.0f}')


def sample_line(sample, since):
    """One line under a site: its latest sample with both results, or why there is none."""
    state = (sample or {}).get("state")
    if state == "ok":
        ent = sample.get("enterococci")
        both = f'E. coli {_count(sample["ecoli"])}' + (f', intestinal enterococci {_count(ent)}' if ent else '')
        return f'Latest archived EA sample {when(sample["taken_at"])}: {both} per 100 ml'
    if state == "none":
        return f'No EA sample in the archive since {when(since + "T00:00") if since else "this season began"}'
    if state == "unavailable":
        return 'EA sample results unavailable in this update'
    return 'Sample results: see the official profile'


def when(iso):
    """A source time as people read it, in UK time ("3 Oct 2026, 21:45"), in a <time> element that
    keeps the exact value. Unreadable values are shown as they came."""
    try:
        t = instant(iso)
    except (ValueError, TypeError):
        return escape(str(iso))
    t = t.astimezone(TZ)
    return f'<time datetime="{escape(t.isoformat(), quote=True)}">{t.day} {t:%b %Y, %H:%M}</time>'


def render(snapshot):
    """Server-rendered list works without JavaScript; dates are always visible."""
    if not snapshot or not snapshot.get("sites"):
        return '<p>The official directory could not be loaded for this build. Use the EA link above.</p>'
    messages = {"increased": "EA: increased pollution risk",
                "no_increased_risk": "EA: no increased pollution risk forecast. Not a water test",
                "no_forecast": "No EA pollution risk forecast at this site",
                "no_current_advice": "No current EA advice in this snapshot",
                "unavailable": "Current EA advice unavailable"}
    cards = []
    for site in snapshot["sites"]:
        rating, advice = site["rating"], site["advice"]
        historical = f'{rating["year"]} rating: {rating["value"]}' if rating else "Historical rating unavailable"
        stamp = ''
        if advice.get("expires_at"):
            stamp = f'<br>Issued {when(advice["published_at"])}; expires {when(advice["expires_at"])}'
        expiry = f' data-advice-expires="{escape(advice["expires_at"], quote=True)}"' if advice.get("expires_at") else ''
        sample = f'<br>{sample_line(site["sample"], (snapshot.get("samples") or {}).get("since"))}' if "sample" in site else ''
        cards.append(f'<li class="coastal-site"><a href="{escape(site["profile"], quote=True)}">{escape(site["name"])}</a>'
                     f'<p class="small">{escape(site["kind"].title())} · {escape(historical)}<br>'
                     f'<span{expiry}>At snapshot: {messages[advice["state"]]}</span>{stamp}{sample}</p></li>')
    return (f'<p class="small">{len(cards)} designated coastal and estuary bathing waters. Snapshot '
            f'{when(snapshot["fetched_at"])}. Advice can change after this snapshot: open the official profile '
            'and check the signs before swimming. Missing advice does not mean clean water.</p>'
            + (f'<p class="small">The live catalogue could not be retrieved; names and historical ratings use '
               f'the official catalogue retrieved {when(snapshot["catalogue_fetched_at"])}. '
               'New designations or changed ratings may not be included.</p>' if snapshot.get("catalogue_state") == "cached" else '')
            + (('<p class="small">Sample results are the latest statutory samples in the EA Water Quality Archive'
                + (f', checked {when(snapshot["samples"]["fetched_at"])}' if snapshot["samples"].get("fetched_at") else '')
                + '. The archive can lag the official profile by several days. A sample describes the water when '
                'it was taken, not today. The rating uses four seasons of samples.</p>') if snapshot.get("samples") else '') +
            '<label for="coastal-search">Find a beach or estuary</label> '
            '<input type="search" id="coastal-search" placeholder="Bathing-water name">'
            f'<p id="coastal-count" class="small" aria-live="polite">{len(cards)} sites</p>'
            '<ul id="coastal-sites">' + ''.join(cards) + '</ul>'
            '<p class="small">Contains Environment Agency data, © Environment Agency copyright and/or '
            'database right, <a href="https://environment.data.gov.uk/bwq/">Open Government Licence v3.0</a>. '
            'The EA does not endorse SwimSignal.</p>')
