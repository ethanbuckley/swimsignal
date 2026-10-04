"""Bathing waters in the Republic of Ireland from the EPA, kept separate from our inland forecast:
SwimSignal makes no forecast in Ireland, and nothing here is a statement about today's water.

The EPA's Bathing Water Open Data API (https://data.epa.ie/bw/api/v1/, CC BY 4.0) lists 243 waters:
154 "Identified" (designated, "Regulated Bathing Water" on beaches.ie) and 89 "Non-Identified"
(monitored by the councils but not designated, "Other Monitored Water"). It gives each designated
water's latest rating, every sample since 2014 (in season, 22 May to 15 September, and voluntary
out-of-season ones) and the restrictions in force. It answered GitHub's runners on 4 Oct 2026.

The samples have no date or site filter, only pages in date order, so the build reads the last pages
back to the start of the latest season's year. The list of waters (757 KB) changes about once a
year and is read once a day; the samples at most every three hours; the restrictions on every build.
Each part, once read, is kept in the cache. If the EPA does not answer, the kept part is shown with
its date, for a limited time, and restrictions are never shown from a kept copy: a restriction can
be lifted or added at any time, so the page says they could not be checked.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import date, datetime
from html import escape, unescape
from pathlib import Path

import httpx

from dipcast import config
from dipcast.coastal import TZ, instant, when

BASE = "https://data.epa.ie/bw/api/v1/"
LOCATIONS, ALERTS = BASE + "locations", BASE + "alerts"
IN_SEASON, OUT_SEASON = BASE + "measurements/in-season", BASE + "measurements/out-season"
SOURCE = "https://data.epa.ie/api-list/bathing-water-open-data/"
LICENCE = "https://creativecommons.org/licenses/by/4.0/"
CREDIT = ("Contains bathing water data from the Environmental Protection Agency (Ireland), Bathing Water "
          "Open Data API, licensed under CC BY 4.0. SwimSignal shows some of the fields and picks each "
          "water's latest sample.")
PAGE_URL = "https://www.beaches.ie/find-a-beach/#/beach/{}"   # the EPA's own page for each water
HOME = "https://www.beaches.ie/"
CACHE = config.CACHE / "ireland_epa.json"
ID = re.compile(r"[A-Za-z0-9_]{10,30}\Z")   # "IESHBWL25_191a_0300" (Lough Derg) has a lower-case letter
COUNT = re.compile(r"([<>]?)(\d+(?:\.\d+)?)\Z")
RATINGS = {"Excellent Quality": "Excellent", "Good Quality": "Good", "Sufficient Quality": "Sufficient", "Poor Quality": "Poor"}
SAMPLE_WORDS = {"Excellent", "Good", "Sufficient", "Poor"}
TYPES = {"Identified Beach": True, "Non-Identified Beach": False}
PER_PAGE = 1000          # the API takes per_page up to at least 5,000 (checked 4 Oct 2026)
MAX_PAGES = 4            # in season, 2026 was about 2,200 rows: the last three pages reach back into 2025
LOCATIONS_TTL_S, LOCATIONS_KEEP_S = 86400, 30 * 86400
SAMPLES_TTL_S, SAMPLES_KEEP_S = 3 * 3600, 3 * 86400
OLD_DAYS = 30            # a sample older than this says so


def fold(text: str) -> str:
    """Lower case without accents, for sorting Irish names ("Trá" beside "Tra")."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()


def _clean(text) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip() if isinstance(text, str) else ""


def parse_locations(items: list) -> list[dict]:
    """Each water: id, name (as the EPA gives it, accents kept), county, whether it is designated,
    its latest rating with the year (or `unrated_year` for "Not classified"), whether a restriction
    applies for the whole season, and its page on beaches.ie. Designated waters first, then by
    name. Raises on a missing or repeated id, a missing name or an unknown kind of water, so that a
    changed source cannot publish a partial list."""
    out, seen = [], set()
    for item in items:
        key, name = (item or {}).get("beach_id"), _clean((item or {}).get("beach_name"))
        kind = (item or {}).get("beach_type")
        if not isinstance(key, str) or not ID.fullmatch(key) or key in seen or not name or kind not in TYPES:
            raise ValueError("invalid or repeated EPA bathing water")
        seen.add(key)
        word, year = item.get("current_annual_water_quality_classification"), item.get("current_annual_classification_year")
        has_year = isinstance(year, int) and not isinstance(year, bool)
        out.append({"id": key, "name": name, "county": _clean(item.get("county_name")), "designated": TYPES[kind],
                    "rating": {"value": RATINGS[word], "year": year} if word in RATINGS and has_year else None,
                    "unrated_year": year if word == "Not classified" and has_year else None,
                    "season_restriction": item.get("has_all_season_bathing_restriction_in_place") == "Yes",
                    "page": PAGE_URL.format(key)})
    return sorted(out, key=lambda s: (not s["designated"], fold(s["name"]), s["id"]))


def _day(text) -> date:
    return date.fromisoformat(str(text)[:10])


def parse_alerts(items: list, now: datetime) -> dict[str, list[dict]]:
    """{water id: its restrictions in force}: the EPA's type in its own words, the start date, the
    cause it gives and its notice. The API lists only incidents in force; one with an end date
    already past is left out. An alert without a readable id, type or start date is left out."""
    out: dict[str, list[dict]] = {}
    today = now.astimezone(TZ).date()
    for a in items:
        a = a or {}
        key, kind = a.get("beach_id"), _clean(a.get("bathing_restriction_type"))
        try:
            since = _day(a.get("incident_start_date"))
            ends = _day(a["incident_end_date"]) if a.get("incident_end_date") else None
        except (TypeError, ValueError):
            continue
        if not isinstance(key, str) or not ID.fullmatch(key) or not kind or (ends and ends < today):
            continue
        notice = a.get("bathing_notice_pdf")
        out.setdefault(key, []).append({
            "type": kind, "since": since.isoformat(), "cause": _clean(a.get("incident_description")) or None,
            "notice": notice if isinstance(notice, str) and notice.startswith(HOME) else None})
    return out


def _count(text) -> dict | None:
    m = COUNT.fullmatch(str(text).strip()) if isinstance(text, (str, int, float)) and not isinstance(text, bool) else None
    return {"value": float(m[2]), "qualifier": m[1] or "="} if m else None


def parse_samples(in_season: list, out_season: list) -> dict[str, dict]:
    """{water id: its latest sample}: date, both counts per 100 ml, the EPA's word for the sample,
    and whether it was taken in the season. A sample without a readable date or E. coli count is
    left out. On the same day, the in-season sample wins."""
    out: dict[str, dict] = {}
    for season, items in (("in", in_season), ("out", out_season)):
        for m in items:
            m = m or {}
            key, ecoli = m.get("beach_id"), _count(m.get("e_coli_result"))
            try:
                taken = _day(m.get("result_date"))
            except (TypeError, ValueError):
                continue
            if not isinstance(key, str) or not ID.fullmatch(key) or ecoli is None:
                continue
            if key in out and out[key]["date"] >= taken.isoformat():
                continue
            word = m.get("sample_water_quality_status")
            out[key] = {"date": taken.isoformat(), "season": season, "ecoli": ecoli,
                        "enterococci": _count(m.get("intestinal_enterococci_result")),
                        "status": word if word in SAMPLE_WORDS else None}
    return out


def _page(client: httpx.Client, url: str, page: int, per_page: int) -> dict:
    r = client.get(url, params={"page": page, "per_page": per_page}, timeout=20)
    r.raise_for_status()
    body = r.json()
    if not isinstance(body.get("list"), list) or not isinstance(body.get("count"), int):
        raise TypeError("unexpected EPA answer")
    return body


def tail(client: httpx.Client, url: str, since: date | None = None) -> tuple[list, int | None]:
    """The rows of a measurements list from `since` (default: 1 January of the latest row's year)
    to its end, reading pages backwards from the last. Returns (rows, that year). Raises if
    MAX_PAGES pages do not reach back that far, so that a part-season is never shown as the whole."""
    count = _page(client, url, 1, 1)["count"]
    pages = math.ceil(count / PER_PAGE)
    rows: list = []
    year = since.year if since else None
    for p in range(pages, 0, -1):
        if pages - p >= MAX_PAGES:
            raise ValueError("EPA samples go back further than expected")
        items = _page(client, url, p, PER_PAGE)["list"]
        days = []
        for m in items:
            try:
                days.append(_day((m or {}).get("result_date")))
            except (TypeError, ValueError):
                pass
        if year is None and days:
            year = max(days).year
            since = date(year, 1, 1)
        rows += items
        if since and days and min(days) < since:
            break
    return [m for m in rows if _safe_day(m) and since and _safe_day(m) >= since], year


def _safe_day(m) -> date | None:
    try:
        return _day((m or {}).get("result_date"))
    except (TypeError, ValueError):
        return None


def _age(stamp, now: datetime) -> float:
    return (now - instant(stamp)).total_seconds()


def _load(path: Path) -> dict:
    try:
        kept = json.loads(Path(path).read_text())
        return kept if isinstance(kept, dict) else {}
    except (OSError, ValueError):
        return {}


def _part(kept: dict, name: str, now: datetime, ttl: float, keep: float, read):
    """A part of the snapshot: the kept one if it is younger than `ttl`, else a fresh read, else the
    kept one if younger than `keep`. Returns (part or None, state, error)."""
    old = kept.get(name)
    try:
        age = _age(old["fetched_at"], now) if old else None
    except (KeyError, TypeError, ValueError):
        old, age = None, None
    if old and age is not None and 0 <= age < ttl:
        return old, "ok", None
    try:
        return {"fetched_at": now.isoformat(), **read()}, "ok", None
    except Exception as e:  # noqa: BLE001 - the list sits beside the inland forecast
        error = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
    if old and age is not None and 0 <= age < keep:
        return old, "kept", error
    return None, "unavailable", error


def fetch(now: datetime | None = None, client: httpx.Client | None = None, cache: Path | None = None) -> dict:
    """The Republic's list for the build. `state` is "live" when every part is current, "partial"
    when one was kept from an earlier build or could not be read, and "unavailable" when there is
    no list. Never raises."""
    now = now or datetime.now(TZ)
    cache = Path(cache or CACHE)
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": config.USER_AGENT}, follow_redirects=False)
    kept = _load(cache)
    errors = []
    try:
        def read_locations():
            body = _page(client, LOCATIONS, 1, PER_PAGE)
            if len(body["list"]) != body["count"] or not body["list"]:
                raise ValueError("EPA list of waters incomplete")
            return {"sites": parse_locations(body["list"])}

        def read_samples():
            ins, year = tail(client, IN_SEASON)
            outs, _ = tail(client, OUT_SEASON, date(year, 1, 1) if year else None)
            return {"season": year, "latest": parse_samples(ins, outs)}

        locations, loc_state, e1 = _part(kept, "locations", now, LOCATIONS_TTL_S, LOCATIONS_KEEP_S, read_locations)
        samples, smp_state, e2 = _part(kept, "samples", now, SAMPLES_TTL_S, SAMPLES_KEEP_S, read_samples) if locations else (None, "unavailable", None)
        alerts, alr_state, e3 = None, "unavailable", None
        if locations:
            try:
                body = _page(client, ALERTS, 1, PER_PAGE)
                if len(body["list"]) != body["count"]:
                    raise ValueError("EPA list of restrictions incomplete")
                alerts, alr_state = {"fetched_at": now.isoformat(), "items": body["list"]}, "ok"
            except Exception as e:  # noqa: BLE001
                e3 = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
        errors = [f"{n}: {e}" for n, e in (("locations", e1), ("samples", e2), ("alerts", e3)) if e]
        to_keep = {k: v for k, v in (("locations", locations), ("samples", samples)) if v}
        if to_keep and to_keep != {k: kept.get(k) for k in to_keep}:
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps({**kept, **to_keep}))
            except OSError:
                pass
    finally:
        if own:
            client.close()
    snap = {"fetched_at": now.isoformat(), "source": SOURCE, "licence": LICENCE, "credit": CREDIT, "sites": []}
    if not locations:
        return {**snap, "state": "unavailable", "error": "; ".join(errors) or "no list"}
    in_force = parse_alerts(alerts["items"], now) if alerts else {}
    latest = (samples or {}).get("latest") or {}
    sites = []
    for s in locations["sites"]:
        sample = ({"state": "ok", **latest[s["id"]]} if s["id"] in latest
                  else {"state": "none"} if samples else {"state": "unavailable"})
        sites.append({**s, "sample": sample, "alerts": in_force.get(s["id"], []) if alerts else None})
    state = "live" if (loc_state, smp_state, alr_state) == ("ok", "ok", "ok") else "partial"
    return {**snap, "state": state, "sites": sites,
            "locations": {"state": loc_state, "fetched_at": locations["fetched_at"]},
            "samples": {"state": smp_state, **({"fetched_at": samples["fetched_at"], "season": samples.get("season")} if samples else {})},
            "alerts": {"state": alr_state, **({"fetched_at": alerts["fetched_at"]} if alerts else {})},
            **({"error": "; ".join(errors)} if errors else {})}


def day(iso: str) -> str:
    """A date as people read it ("8 Sep 2026"), in a <time> element."""
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return escape(str(iso))
    return f'<time datetime="{d.isoformat()}">{d.day} {d:%b %Y}</time>'


def _n(c: dict) -> str:
    v = c["value"]
    return escape(("" if c["qualifier"] == "=" else c["qualifier"]) + (f"{v:,.0f}" if v.is_integer() else f"{v:,g}"))


def _sample_text(sample: dict, today: date, season: int | None) -> str:
    if sample.get("state") == "unavailable":
        return "Latest sample unavailable for this build"
    if sample.get("state") != "ok":
        return f"No sample listed for {season}" if season else "No sample listed"
    ent = sample.get("enterococci")
    text = (f'Latest sample {day(sample["date"])}{"" if sample["season"] == "in" else ", out of season"}: '
            f'E. coli {_n(sample["ecoli"])}' + (f', intestinal enterococci {_n(ent)}' if ent else '') + ' per 100 ml'
            + (f' (EPA: {escape(sample["status"])})' if sample.get("status") else '') + '.')
    if (today - date.fromisoformat(sample["date"])).days > OLD_DAYS:
        text += f' More than {OLD_DAYS} days old.'
    return text


def _alert_text(a: dict) -> str:
    text = f'<strong>{escape(a["type"])}</strong>, since {day(a["since"])} (EPA).'
    if a.get("cause"):
        text += f' Reason given: {escape(a["cause"].rstrip("."))}.'
    if a.get("notice"):
        text += f' <a href="{escape(a["notice"], quote=True)}">Notice (PDF)</a>'
    return text


def render(snapshot: dict) -> str:
    """The Republic's list, server-rendered and searchable on the page. Every sample and restriction
    carries its date; the restrictions line says when they were checked, or that they were not."""
    if not snapshot or not snapshot.get("sites"):
        return (f'<p>The list for the Republic of Ireland could not be loaded for this build. Use '
                f'<a href="{HOME}">beaches.ie</a>.</p>')
    today = instant(snapshot["fetched_at"]).astimezone(TZ).date()
    season = (snapshot.get("samples") or {}).get("season")
    cards, restricted = [], []
    for s in snapshot["sites"]:
        if s["designated"]:
            rating = (f'{s["rating"]["year"]} rating: {s["rating"]["value"]}' if s["rating"]
                      else f'Not classified in {s["unrated_year"]}' if s.get("unrated_year") else "No rating listed")
            kind = escape(rating)
        else:
            kind = "Other monitored water: not a designated bathing water, so it has no rating"
        lines = [f'{escape(s["county"])} · {kind}' if s["county"] else kind]
        if s.get("season_restriction"):
            lines.append("<strong>Bathing restricted for the whole season</strong> (EPA).")
        for a in s.get("alerts") or []:
            lines.append(_alert_text(a))
            restricted.append(s["name"])
        lines.append(_sample_text(s["sample"], today, season))
        cards.append(f'<li class="ireland-site"><a href="{escape(s["page"], quote=True)}">{escape(s["name"])}</a>'
                     f'<p class="small">{"<br>".join(lines)}</p></li>')
    designated = sum(s["designated"] for s in snapshot["sites"])
    alerts, samples, locations = snapshot.get("alerts") or {}, snapshot.get("samples") or {}, snapshot.get("locations") or {}
    if alerts.get("state") == "ok":
        names = sorted(set(restricted), key=fold)   # names hold commas ("Lilliput, Lough Ennell"): semicolons between them
        alerts_text = (f'Restrictions in force, as the EPA listed them {when(alerts["fetched_at"])}: '
                       + ('; '.join(escape(n) for n in names) if names else 'none') + '.')
    else:
        alerts_text = (f'The EPA\'s list of restrictions could not be read for this build. Check '
                       f'<a href="{HOME}">beaches.ie</a> before you swim.')
    if samples.get("fetched_at"):
        samples_text = (f'Samples as the EPA listed them {when(samples["fetched_at"])}'
                        + (', kept from an earlier build because the EPA did not answer' if samples.get("state") == "kept" else '')
                        + '. A sample describes the water when it was taken, not today. Samples taken from 16 September '
                        'to 21 May are voluntary and do not count towards a rating.')
    else:
        samples_text = 'The EPA\'s samples could not be read for this build.'
    kept = (f' The list of waters is from {when(locations["fetched_at"])}, kept because the EPA did not answer.'
            if locations.get("state") == "kept" else '')
    return (f'<p class="small">{designated} designated bathing waters and {len(cards) - designated} other waters the councils '
            f'monitor, designated first.{kept}</p>'
            f'<p class="small">{alerts_text}</p>'
            f'<p class="small">{samples_text}</p>'
            '<label for="ireland-search">Find a bathing water in the Republic</label> '
            '<input type="search" id="ireland-search" placeholder="Name, with or without accents">'
            f'<p id="ireland-count" class="small" aria-live="polite">{len(cards)} sites</p>'
            '<ul id="ireland-sites">' + ''.join(cards) + '</ul>'
            f'<p class="small">{escape(CREDIT)} <a href="{SOURCE}">Source</a> · <a href="{LICENCE}">Licence</a>. '
            'The EPA does not endorse SwimSignal.</p>')
