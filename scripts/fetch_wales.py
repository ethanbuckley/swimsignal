"""Write data/raw/wales_bathing_waters.json: Natural Resources Wales's bathing waters, ratings and
latest in-season samples, trimmed to the fields wales.parse_sites and parse_samples read, with the
time it was fetched. The build shows it, dated, when NRW's service refuses GitHub's runners (it
did on 3 Oct 2026); it never holds a forecast. Run it from a machine NRW answers, in the season
after new samples and once more after the year's ratings are published, and commit the file:

    uv run python scripts/fetch_wales.py
"""

from __future__ import annotations

import json
from datetime import datetime

import httpx

from dipcast import config, wales


def trim_site(item: dict) -> dict:
    a = item.get("latestComplianceAssessment") or {}
    return {"eubwidNotation": item.get("eubwidNotation"), "name": item.get("name"), "type": item.get("type"),
            "latestComplianceAssessment": {"_about": a.get("_about"),
                                           "complianceClassification": {"name": (a.get("complianceClassification") or {}).get("name")}}}


def trim_sample(item: dict) -> dict:
    keep = ("escherichiaColiCount", "escherichiaColiQualifier", "intestinalEnterococciCount", "intestinalEnterococciQualifier")
    return {"bwq_bathingWater": {"eubwidNotation": (item.get("bwq_bathingWater") or {}).get("eubwidNotation")},
            "sampleDateTime": {"inXSDDateTime": (item.get("sampleDateTime") or {}).get("inXSDDateTime")},
            **{k: item.get(k) for k in keep}}


def main() -> None:
    with httpx.Client(headers=config.EA_HEADERS) as c:
        sites, samples = wales._items(c, wales.SITES), wales._items(c, wales.SAMPLES)
    now = datetime.now(wales.TZ).isoformat(timespec="seconds")
    kept = {"fetched_at": now, "source": wales.SITES, "samples_source": wales.SAMPLES, "licence": wales.LICENCE,
            "credit": wales.CREDIT, "site_items": [trim_site(s) for s in sites], "sample_items": [trim_sample(s) for s in samples]}
    snap = wales.snapshot_from(kept["site_items"], kept["sample_items"], now)   # raises if the trimmed copy no longer parses
    wales.SNAPSHOT.write_text(json.dumps(kept, indent=1, ensure_ascii=False) + "\n")
    with_sample = sum(s["sample"]["state"] == "ok" for s in snap["sites"])
    print(f"{len(snap['sites'])} Welsh bathing waters, {with_sample} with a sample -> {wales.SNAPSHOT}")


if __name__ == "__main__":
    main()
