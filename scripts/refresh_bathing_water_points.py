"""Record where each English and Welsh bathing water is sampled, in data/raw/bathing_water_points.json, for the
directories' provisional water temperature (issue #492, stage 3: build_site.attach_directory_water_temp).

The site's catalogue snapshot (data/raw/coastal_catalogue.json) and the live catalogue the build asks for carry no
position, so the build cannot place a site on the air grid without this file. It holds the bathing-water service's own
sampling point (`samplingPoint` lat and long) for every designated water, England's and NRW's: three requests in all.
The service refuses GitHub's runners (see ingest/wqa.py), so run it from a machine that can reach it, when a
catalogue changes (a new designation or a moved point):

    uv run python scripts/refresh_bathing_water_points.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx

from dipcast.coastal import CATALOGUE, CREDIT, ID, LICENCE, TZ
from dipcast.wales import SITES as WALES_SITES

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "bathing_water_points.json"


def points(client: httpx.Client, url: str) -> dict[str, list[float]]:
    """{bathing water id: [lat, lon]} of its sampling point, to 5 decimals (about a metre)."""
    rows = []
    for page in range(3):
        r = client.get(url, params={"_pageSize": 500, "_page": page,
                                    "_properties": "samplingPoint.lat,samplingPoint.long"})
        r.raise_for_status()
        batch = r.json()["result"]["items"]
        rows.extend(batch)
        if len(batch) < 500:
            break
    out = {}
    for item in rows:
        key, sp = item.get("eubwidNotation", ""), item.get("samplingPoint") or {}
        if ID.fullmatch(key) and isinstance(sp, dict) and isinstance(sp.get("lat"), (int, float)) \
                and isinstance(sp.get("long"), (int, float)):
            out[key] = [round(float(sp["lat"]), 5), round(float(sp["long"]), 5)]
    return dict(sorted(out.items()))


def main() -> None:
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        england, wales = points(client, CATALOGUE), points(client, WALES_SITES)
    if len(england) < 400 or len(wales) < 100:
        raise SystemExit(f"too few points (England {len(england)}, Wales {len(wales)}): not written")
    OUT.write_text(json.dumps({
        "fetched_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "sources": {"england": CATALOGUE, "wales": WALES_SITES},
        "licence": LICENCE, "credit": CREDIT + " Contains Natural Resources Wales information © Natural Resources "
                                                "Wales and Database Right.",
        "what": "Each designated bathing water's sampling point, [lat, lon], from the bathing-water service.",
        "england": england, "wales": wales}, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT}: England {len(england)}, Wales {len(wales)}")


if __name__ == "__main__":
    main()
