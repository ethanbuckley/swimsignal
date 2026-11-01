"""What each bathing water in the coverage page's directories has read in its own official samples, the bathing seasons
2023-2026: the middle sample and the range the middle 8 in 10 fell in (typical.typical_readings), with how many were over
the minimum standard's E. coli line (500 on the coast, 900 inland). Past samples, never a forecast. Off CI, by hand, once
a season, one directory at a time:

    uv run python scripts/export_typical_readings.py england_coast      # EA Water Quality Archive, OGL v3
    uv run python scripts/export_typical_readings.py wales              # Natural Resources Wales, OGL v3
    uv run python scripts/export_typical_readings.py ireland            # EPA Ireland, CC BY 4.0
    uv run python scripts/export_typical_readings.py northern_ireland   # DAERA's results pages, OGL v3

Each writes data/research/typical_<directory>.v1.json (typical.FILES), keyed by the directory's own site ids; the build
puts each site's on its card on the coverage page. Every request is counted against the directory's cap; a server error
is tried again after RETRY_S; a refusal, or the cap, stops the export and nothing is written.

Not Scotland: SEPA's sample results are under "SEPA website conditions of use", and SEPA's data terms list "publishing it
or making it available to the public" among prohibited uses (docs/SCOTLAND-PLAN-2026-10.md). That waits on SEPA.
"""

from __future__ import annotations

import html
import json
import logging
import re
import sys
import time
import unicodedata
from datetime import UTC, datetime

import httpx

from dipcast import config, typical
from dipcast.coastal import TZ, instant
from dipcast.ingest import wqa

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("export_typical_readings")

YEARS = range(2023, 2027)
RETRY_S = (10, 30, 90)
UA = {**config.EA_HEADERS}


class Budget:
    """Requests made, against a cap; server errors and dropped connections tried again after RETRY_S."""

    def __init__(self, cap: int):
        self.cap, self.n = cap, 0

    def call(self, c: httpx.Client, method: str, url: str, **kw) -> httpx.Response:
        for wait in (*RETRY_S, None):
            if self.n >= self.cap:
                raise RuntimeError(f"stopped at the cap of {self.cap} requests: nothing written")
            self.n += 1
            try:
                r = c.request(method, url, timeout=120, **kw)
                if r.status_code not in (502, 503, 504):
                    r.raise_for_status()
                    return r
                why = f"HTTP {r.status_code}"
            except httpx.TransportError as e:
                why = type(e).__name__
            if wait is None:
                raise RuntimeError(f"{why} after {len(RETRY_S)} retries: nothing written")
            log.warning("%s; trying again in %d s", why, wait)
            time.sleep(wait)
        raise AssertionError("unreachable")


def _sample(t: str, v, q) -> dict:
    return {"t": t, "ecoli": float(v), "q": q if q in ("<", ">") else None}


# ------------------------------------------------------------------ the English coast
def england_coast(b: Budget) -> tuple[dict, dict, dict]:
    """EA Water Quality Archive: E. coli (2348, confirmed, membrane filtration), statutory samples (MS), at each site's
    archive point (data/raw/coastal_wqa_points.json). Several points over at most a year a request ("the maximum
    temporal range is 1 year"), so one season at a time, 25 points a request."""
    mapping = json.loads((config.ROOT / "data" / "raw" / "coastal_wqa_points.json").read_text())
    site_of = {v["point"]: k for k, v in mapping["points"].items() if isinstance(v, dict) and v.get("point")}
    points, out = sorted(site_of), {}
    with httpx.Client(headers={**UA, "Accept": "application/ld+json"}) as c:
        for year in YEARS:
            params = {"determinand": wqa.ECOLI, "dateFrom": f"{year}-05-01", "dateTo": f"{year}-09-30",
                      "limit": wqa.PAGE, "samplingPurpose": wqa.BATHING_PURPOSES}
            for i in range(0, len(points), 25):
                skip = 0
                while True:
                    items = b.call(c, "POST", f"{wqa.API}/data/observation",
                                   params={**params, "pointNotation": ",".join(points[i:i + 25]), "skip": skip}).json().get("member") or []
                    for o in items:
                        point = (o.get("hasSamplingPoint") or {}).get("notation")
                        v, q = wqa._count(o.get("hasSimpleResult"))
                        try:
                            t = instant(o.get("phenomenonTime")).astimezone(TZ)
                        except (ValueError, TypeError):
                            continue
                        if point in site_of and v is not None:
                            out.setdefault(site_of[point], {})[t.isoformat()] = _sample(t.isoformat(), v, q)
                    if len(items) < wqa.PAGE:
                        break
                    skip += wqa.PAGE
                    time.sleep(0.5)
                time.sleep(0.5)
            log.info("%d done, %d requests", year, b.n)
    kinds = {k: "coast" for k in mapping["points"]}
    return out, kinds, {"source": wqa.API, "licence": "Open Government Licence v3.0", "months": "May–September",
                        "credit": "Contains Environment Agency data, © Environment Agency copyright and/or database right, "
                                  "Open Government Licence v3.0.",
                        "how": "E. coli (determinand 2348), statutory bathing samples (purpose MS), at each site's archive "
                               "sampling point (data/raw/coastal_wqa_points.json)"}


# ------------------------------------------------------------------ Wales
def wales(b: Budget) -> tuple[dict, dict, dict]:
    """NRW's in-season samples (the EA platform's Welsh service, which answers from here but not from GitHub's runners),
    from 1 May 2023, 200 a page."""
    from dipcast import wales as w
    kept = json.loads(w.SNAPSHOT.read_text())
    kinds = {s["id"]: s["kind"] for s in w.parse_sites(kept["site_items"])}
    url = f"{w.BASE}/bathing-water-quality/in-season/sample.json"
    out, page = {}, 0
    with httpx.Client(headers=UA) as c:
        while True:
            res = b.call(c, "GET", url, params={"_pageSize": 200, "_page": page,
                                               "min-sampleDateTime.inXSDDateTime": "2023-05-01T00:00:00"}).json()["result"]
            items = res.get("items") or []
            for it in items:
                key = (it.get("bwq_bathingWater") or {}).get("eubwidNotation", "")
                try:
                    t = instant((it.get("sampleDateTime") or {}).get("inXSDDateTime")).astimezone(TZ)
                except (ValueError, TypeError):
                    continue
                c_ = w._count(it.get("escherichiaColiCount"), it.get("escherichiaColiQualifier"))
                if key in kinds and c_ and t.year in YEARS:
                    out.setdefault(key, {})[t.isoformat()] = _sample(t.isoformat(), c_["value"], c_["qualifier"])
            if not items or not res.get("next"):
                break
            page += 1
            time.sleep(0.5)
    return out, kinds, {"source": url, "licence": "Open Government Licence v3.0", "months": "May–September",
                        "credit": w.CREDIT, "how": "NRW's in-season statutory samples, E. coli"}


# ------------------------------------------------------------------ the Republic of Ireland
def ireland(b: Budget) -> tuple[dict, dict, dict]:
    """The EPA's in-season measurements: no date or site filter, pages in date order, so read back from the last page
    until a page starts before 2023. Kinds as the directory types them (ireland.water_kind)."""
    from dipcast import ireland as ie
    per = 5000
    out, kinds = {}, {}
    with httpx.Client(headers=UA) as c:
        count = b.call(c, "GET", ie.IN_SEASON, params={"page": 1, "per_page": 1}).json()["count"]
        for p in range(-(-count // per), 0, -1):
            items = b.call(c, "GET", ie.IN_SEASON, params={"page": p, "per_page": per}).json()["list"]
            first = None
            for m in items:
                key, name, day = m.get("beach_id"), m.get("beach_name") or "", m.get("result_date") or ""
                cnt = ie._count(m.get("e_coli_result"))
                first = day if first is None or day < first else first
                if isinstance(key, str) and ie.ID.fullmatch(key) and cnt and day[:4].isdigit() and int(day[:4]) in YEARS:
                    out.setdefault(key, {})[day] = _sample(day, cnt["value"], cnt["qualifier"])
                    kinds[key] = ie.water_kind(key, ie._clean(name))[0]
            if first and first < f"{YEARS[0]}-01-01":
                break
            time.sleep(0.5)
    return out, kinds, {"source": ie.IN_SEASON, "licence": "CC BY 4.0", "months": "bathing seasons",
                        "credit": "Contains bathing water data from the Environmental Protection Agency (Ireland), "
                                  "licensed under CC BY 4.0; SwimSignal summarises each water's samples.",
                        "how": "The EPA's in-season measurements, E. coli"}


# ------------------------------------------------------------------ Northern Ireland
def _fold(name: str) -> str:
    s = unicodedata.normalize("NFKD", html.unescape(name)).encode("ascii", "ignore").decode().lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# DAERA's tables name some waters otherwise than its layer: the same water by place, checked on 1 Nov 2026.
DAERA_ALIASES = {"brompton": "brompton bay"}


def daera_site(name: str, by_name: dict[str, str]) -> str | None:
    """The layer's site id for a results-table heading: as written, then without "(Candidate)", "*", "Inland Bathing
    Water" and a trailing bracket ("Murlough (Co Down)"), then by DAERA_ALIASES."""
    plain = re.sub(r"\(candidate\)|\*|inland bathing water", "", name, flags=re.I).strip()
    for n in (name, plain, re.sub(r"\s*\([^)]*\)\s*$", "", plain)):
        f = _fold(n)
        if f in by_name:
            return by_name[f]
        if DAERA_ALIASES.get(f) in by_name:
            return by_name[DAERA_ALIASES[f]]
    return None


def parse_daera(page: str) -> dict[str, list[tuple[str, float]]]:
    """{site name: [(date, E. coli), ...]} from one of DAERA's yearly results pages: a heading (the site's name) before
    each table of date, E. coli and intestinal enterococci. DAERA's tables give no qualifier: 10 is their lowest value."""
    out, prev = {}, 0
    for m in re.finditer(r"(?s)<table.*?</table>", page):
        heads = re.findall(r"(?s)<h[2-4][^>]*>(.*?)</h[2-4]>", page[prev:m.start()])
        prev = m.end()
        name = html.unescape(re.sub(r"<[^>]+>|\s+", " ", heads[-1])).strip() if heads else ""
        rows = re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", m[0])
        got = []
        for row in rows:
            cells = [re.sub(r"<[^>]+>|\s+", " ", x).strip() for x in re.findall(r"(?s)<t[dh][^>]*>(.*?)</t[dh]>", row)]
            if len(cells) >= 2 and re.fullmatch(r"\d{2}/\d{2}/\d{4}", cells[0]) and re.fullmatch(r"[<>]?\d+(\.\d+)?", cells[1]):
                d, mo, y = cells[0].split("/")
                got.append((f"{y}-{mo}-{d}", cells[1]))
        if name and got:
            out[name] = got
    return out


def northern_ireland(b: Budget) -> tuple[dict, dict, dict]:
    """DAERA's yearly results pages (OGL v3, DAERA's crown copyright page), matched to the directory's sites by name."""
    from dipcast import northern_ireland as ni
    with httpx.Client(headers=UA, follow_redirects=True) as c:
        sites = ni.parse(b.call(c, "GET", ni.LAYER, params={"where": "1=1", "outFields": ni.FIELDS, "f": "json",
                                                             "returnGeometry": "true", "outSR": 4326}).json()["features"])
        by_name = {_fold(s["name"]): s["id"] for s in sites}
        kinds = {s["id"]: s["kind"] for s in sites}
        out, unmatched = {}, set()
        for year in YEARS:
            page = b.call(c, "GET", f"https://www.daera-ni.gov.uk/articles/bathing-water-data-{year}").text
            for name, rows in parse_daera(page).items():
                sid = daera_site(name, by_name)
                if sid is None:
                    unmatched.add(name)
                    continue
                for day, v in rows:
                    q = v[0] if v[0] in "<>" else None
                    out.setdefault(sid, {})[day] = _sample(day, v.lstrip("<>"), q)
            time.sleep(1)
    if unmatched:
        log.warning("DAERA table names not in the directory: %s", sorted(unmatched))
    return out, kinds, {"source": "https://www.daera-ni.gov.uk/articles/bathing-water-data-2026 (and 2023-2025)",
                        "licence": "Open Government Licence v3.0", "months": "bathing seasons",
                        "credit": ni.CREDIT.replace("bathing water monitoring points", "bathing water results"),
                        "how": "DAERA's yearly results tables, E. coli; DAERA gives no qualifier, so 10, its lowest value, "
                               "stands as 10", "unmatched": sorted(unmatched)}


CAPS = {"england_coast": 300, "wales": 120, "ireland": 20, "northern_ireland": 10}
FETCH = {"england_coast": england_coast, "wales": wales, "ireland": ireland, "northern_ireland": northern_ireland}


def main(which: str) -> None:
    b = Budget(CAPS[which])
    by, kinds, meta = FETCH[which](b)
    sites = {}
    for sid in sorted(by):
        line = typical.LINES.get(kinds.get(sid, "coast"), 500)
        t = typical.typical_readings(list(by[sid].values()), line)
        if t:
            sites[sid] = {**t, "months": meta["months"]}
    doc = {"schema": typical.SCHEMA, "version": "1.0.0", "directory": which,
           "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "period": "May to September, 2023 to 2026" if meta["months"] == "May–September" else "the bathing seasons of 2023 to 2026",
           "requests": b.n, "samples": sum(len(v) for v in by.values()), "sites_with_samples": len(by),
           "sites_with_readings": len(sites), "min_samples": typical.MIN_SAMPLES,
           **{k: v for k, v in meta.items() if k != "months"}, "sites": sites}
    path = typical.FILES[which]
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    log.info("%s: %d requests, %d samples at %d sites, readings at %d -> %s", which, b.n, doc["samples"], len(by),
             len(sites), path.name)


if __name__ == "__main__":
    main(sys.argv[1])
