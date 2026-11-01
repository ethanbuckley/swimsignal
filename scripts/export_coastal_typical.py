"""What each English coastal and estuary bathing water's own EA samples have read, May to September 2023-2026: the
middle sample and the range the middle 8 in 10 fell in (typical.typical_readings, over 500 counted, the coastal
"sufficient" E. coli line). Past samples, never a forecast. Off CI, by hand, once a season:

    uv run python scripts/export_coastal_typical.py

Source: the EA Water Quality Archive, E. coli (determinand 2348, confirmed, membrane filtration), statutory bathing
samples (purpose MS), at each bathing water's archive sampling point (data/raw/coastal_wqa_points.json, as the
directory's latest sample). Writes data/research/coastal_typical.v1.json; the build puts each site's on its card on
the coverage page (coastal.render). At most MAX_REQUESTS requests; a refused one stops the export and nothing is written.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from dipcast import config
from dipcast.coastal import TZ, instant
from dipcast.ingest import wqa
from dipcast.typical import typical_readings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("export_coastal_typical")

POINTS = config.ROOT / "data" / "raw" / "coastal_wqa_points.json"
OUT = Path(__file__).resolve().parents[1] / "data" / "research" / "coastal_typical.v1.json"
YEARS, MONTHS = range(2023, 2027), range(5, 10)
LINE = 500
MAX_REQUESTS = 300
BATCH = 25            # points a request, as coastal.latest_samples
RETRY_S = (10, 30, 90)
SCHEMA, VERSION = "swimsignal.coastal-typical", "1.0.0"


def fetch(points: list[str]) -> tuple[list[dict], int]:
    """wqa._observations' paging, one season at a time (the archive answers several points over a year at most: "the
    maximum temporal range is 1 year"), BATCH points a request, counted and capped. A server error (502, 503, 504) or a
    dropped connection is tried again after RETRY_S; anything else, or the last retry failing, stops the export."""
    out, n = [], 0
    with httpx.Client(timeout=120, headers={**config.EA_HEADERS, "Accept": "application/ld+json"}) as c:
        for year in YEARS:
            params = {"determinand": wqa.ECOLI, "dateFrom": f"{year}-05-01", "dateTo": f"{year}-09-30",
                      "limit": wqa.PAGE, "samplingPurpose": wqa.BATHING_PURPOSES}
            for i in range(0, len(points), BATCH):
                skip = 0
                while True:
                    for wait in (*RETRY_S, None):
                        if n >= MAX_REQUESTS:
                            raise RuntimeError(f"stopped at the cap of {MAX_REQUESTS} requests: nothing written")
                        n += 1
                        try:
                            r = c.post(f"{wqa.API}/data/observation",
                                       params={**params, "pointNotation": ",".join(points[i:i + BATCH]), "skip": skip})
                            if r.status_code not in (502, 503, 504):
                                break
                            why = f"HTTP {r.status_code}"
                        except httpx.TransportError as e:
                            why = type(e).__name__
                        if wait is None:
                            raise RuntimeError(f"{why} after {len(RETRY_S)} retries: nothing written")
                        log.warning("%s; trying again in %d s", why, wait)
                        time.sleep(wait)
                    r.raise_for_status()
                    items = r.json().get("member") or []
                    out.extend(items)
                    if len(items) < wqa.PAGE:
                        break
                    skip += wqa.PAGE
                    time.sleep(0.5)
                log.info("%d, points %d-%d: %d results so far, %d requests", year, i + 1, min(i + BATCH, len(points)),
                         len(out), n)
                time.sleep(0.5)
    return out, n


def main() -> None:
    mapping = json.loads(POINTS.read_text())
    site_of = {v["point"]: k for k, v in mapping["points"].items() if isinstance(v, dict) and v.get("point")}
    obs, n_req = fetch(sorted(site_of))
    samples: dict[str, dict] = {}
    skipped = {"unreadable": 0, "out_of_season": 0, "repeats": 0}
    for o in obs:
        point = (o.get("hasSamplingPoint") or {}).get("notation")
        v, q = wqa._count(o.get("hasSimpleResult"))
        try:
            t = instant(o.get("phenomenonTime")).astimezone(TZ)
        except (ValueError, TypeError):
            t = None
        if point not in site_of or v is None or t is None:
            skipped["unreadable"] += 1
            continue
        if t.year not in YEARS or t.month not in MONTHS:
            skipped["out_of_season"] += 1
            continue
        key = (site_of[point], t.isoformat())
        if key in samples:
            skipped["repeats"] += 1
            continue
        samples[key] = {"t": t.isoformat(), "ecoli": v, "q": q if q in ("<", ">") else None}
    by: dict[str, list[dict]] = {}
    for (site, _), x in samples.items():
        by.setdefault(site, []).append(x)
    sites = {}
    for site in sorted(mapping["points"]):
        t = typical_readings(by.get(site, []), LINE)
        if t:
            sites[site] = {**t, "point": mapping["points"][site]["point"]}
    doc = {"schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "source": wqa.API, "determinand": f"{wqa.ECOLI} (E. coli, confirmed, membrane filtration)",
           "purpose": "MS (statutory bathing water samples)", "period": "May to September, 2023 to 2026",
           "line": LINE, "line_note": "The coastal 'sufficient' E. coli line, per 100 ml (Bathing Water Regulations 2013)",
           "points_file": str(POINTS.relative_to(config.ROOT)), "points_checked_at": mapping.get("checked_at"),
           "requests": n_req, "results": len(obs), "samples": len(samples), "skipped": skipped,
           "sites_mapped": len(site_of), "sites_with_readings": len(sites),
           "licence": "Open Government Licence v3.0", "credit": "Contains Environment Agency data, © Environment Agency "
           "copyright and/or database right.", "sites": sites}
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    log.info("%d requests, %d results, %d samples kept, %d of %d mapped sites with readings; %s", n_req, len(obs),
             len(samples), len(sites), len(site_of), skipped)


if __name__ == "__main__":
    main()
