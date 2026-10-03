"""Find each English coastal and estuary bathing water's sampling point in the EA Water
Quality Archive and record it in data/raw/coastal_wqa_points.json, for the dated sample
results the coverage page shows beside the coastal directory (coastal.latest_samples).

The archive labels a designated beach's point with the bathing water's own point number:
"AINSDALE AT AINSDALESEFTON MBC (41300)" is bathing water ukd5300-41300. A point is
accepted when exactly one archive point carries that number: among the archive's
designated-beach points (type CA, listed in two requests), or, for a site none of them
names, among the points within RADIUS_KM of its bathing-water sampling point. Its season's E. coli results are then checked against the
bathing-water service's latest sample for the site (same minute): `evidence` records
"label+latest sample" when it is there, "label" when the archive has not caught up (it
lags the bathing-water service by days). A site whose label matches no point, or more
than one, is left out rather than guessed from distance: several beaches have outfall
and investigation points within metres.

Needs the bathing-water service, which refuses GitHub's runners (see ingest/wqa.py), so
run it from a machine that can reach it, after each season and when the catalogue changes:

    uv run python scripts/map_coastal_wqa.py [season year]
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd

from dipcast import config
from dipcast.coastal import CATALOGUE, ID, KINDS, TZ
from dipcast.ingest import wqa

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "coastal_wqa_points.json"
RADIUS_KM = 1.0
LATEST = re.compile(r"/point/(\d{5})/date/(\d{8})/time/(\d{6})/")


def catalogue(client: httpx.Client) -> list[dict]:
    """Coastal and estuary bathing waters: id, name, sampling point and the latest sample time."""
    rows = []
    for page in range(3):
        r = client.get(CATALOGUE, params={"_pageSize": 500, "_page": page})
        r.raise_for_status()
        batch = r.json()["result"]["items"]
        rows.extend(batch)
        if len(batch) < 500:
            break
    out = []
    for item in rows:
        if not any(t.rsplit("/", 1)[-1] in KINDS for t in item.get("type", [])):
            continue
        key, sp = item.get("eubwidNotation", ""), item.get("samplingPoint") or {}
        if not ID.fullmatch(key) or not isinstance(sp, dict) or sp.get("lat") is None:
            continue
        latest = LATEST.search(str(item.get("latestSampleAssessment") or ""))
        out.append({"id": key, "number": key.rsplit("-", 1)[-1], "lat": float(sp["lat"]), "lon": float(sp["long"]),
                    "latest": (datetime.strptime(latest[2] + latest[3], "%Y%m%d%H%M%S").strftime("%Y-%m-%dT%H:%M")
                               if latest and latest[1] == key.rsplit("-", 1)[-1] else None)})
    return out


def labelled(points: list[dict], number: str) -> list[str]:
    """Archive points whose label ends with the bathing water's point number, "(41300)"."""
    tag = f"({number})"
    return [p["notation"] for p in points if str(p.get("prefLabel") or "").rstrip().endswith(tag)]


def main(year: int) -> None:
    with httpx.Client(timeout=120, headers=config.EA_HEADERS) as c:
        sites = catalogue(c)
    print(f"{len(sites)} coastal and estuary bathing waters in the catalogue")
    beaches = []
    with httpx.Client(timeout=120, headers={**config.EA_HEADERS, "Accept": "application/ld+json"}) as c:
        # Every designated-beach point (type CA, 474 on 3 Oct 2026) in a few pages of the service's
        # 250 limit; searching around each site instead was refused after about 260 requests.
        for skip in range(0, 5000, 250):
            r = c.get(f"{wqa.API}/sampling-point", params={"samplingPointType": "CA", "limit": 250, "skip": skip})
            r.raise_for_status()
            page = r.json().get("member", [])
            beaches.extend(page)
            if len(page) < 250:
                break
            time.sleep(1)
        print(f"{len(beaches)} designated-beach points in the archive")
        candidates = {s["id"]: labelled(beaches, s["number"]) for s in sites}
        # A site whose number labels no beach point (an estuary point can be typed otherwise): its
        # own neighbourhood, slowly, stopping at the first refusal.
        for s in sites:
            if candidates[s["id"]]:
                continue
            time.sleep(2)
            r = c.get(f"{wqa.API}/sampling-point", params={"latitude": s["lat"], "longitude": s["lon"],
                                                           "radius": RADIUS_KM, "limit": 100})
            if r.status_code in (403, 429):
                print(f"archive refused the search at {s['id']}; the rest stay unmatched")
                break
            r.raise_for_status()
            candidates[s["id"]] = labelled(r.json().get("member", []), s["number"])
    points = sorted({p for ps in candidates.values() for p in ps})
    seen: dict[str, set[str]] = defaultdict(set)
    # From August: each site's latest sample, in a query the archive can answer (from May, 50
    # points a request, its second page got a 502 on 3 Oct 2026).
    for o in wqa._observations(points, f"{year}-08-01T00:00:00", wqa.ECOLI, wqa.BATHING_PURPOSES, batch=25):
        seen[(o.get("hasSamplingPoint") or {}).get("notation")].add(str(o.get("phenomenonTime"))[:16])
    found, report = {}, []
    for s in sites:
        mine = candidates[s["id"]]
        point = mine[0] if len(mine) == 1 else None
        evidence = None
        if point:
            evidence = "label+latest sample" if s["latest"] and s["latest"] in seen[point] else "label"
            found[s["id"]] = {"point": point, "evidence": evidence}
        report.append({"id": s["id"], "labelled": len(mine), "point": point, "evidence": evidence,
                       "archive_samples": len(seen[point]) if point else 0})
    df = pd.DataFrame(report)
    print(df["evidence"].fillna("not mapped").value_counts().to_string())
    print(df[df["point"].isna()].to_string(index=False))
    OUT.write_text(json.dumps({
        "checked_at": datetime.now(TZ).isoformat(timespec="seconds"), "season": year,
        "source": f"{wqa.API}/sampling-point", "catalogue": CATALOGUE,
        "method": "one archive point within 1 km whose label ends with the bathing water's point number; "
                  "evidence says whether its E. coli results include the catalogue's latest sample minute",
        "points": dict(sorted(found.items()))}, indent=1) + "\n")
    print(f"{len(found)} of {len(sites)} sites mapped -> {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else pd.Timestamp.now(tz="Europe/London").year)
