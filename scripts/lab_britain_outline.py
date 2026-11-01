"""Great Britain's outline for the Research Lab's drawn map (prototype only).

One request to ONS's Countries (December 2025) boundaries, the layer scripts/make_outside_england.py reads, asking the
server to simplify (maxAllowableOffset) and return WGS84. Writes prototypes/research-lab/assets/britain.json: each
country's rings rounded to 3 decimals, with the credit the licence asks for.

    uv run python scripts/lab_britain_outline.py
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "prototypes" / "research-lab" / "assets" / "britain.json"
LAYER = ("https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
         "Countries_December_2025_Boundaries_UK_BGC/FeatureServer/0")
URL = (f"{LAYER}/query?where=CTRY25NM%20IN%20(%27England%27,%27Wales%27,%27Scotland%27)&outFields=CTRY25NM"
       "&outSR=4326&maxAllowableOffset=0.004&geometryPrecision=3&f=geojson")
MIN_RING = 6       # drop islets drawn with fewer points than this


def main() -> None:
    r = httpx.get(URL, timeout=120, follow_redirects=True, headers={"User-Agent": "dipcast/0.1.0 (+https://github.com/ethanbuckley/swimsignal)"})
    r.raise_for_status()
    gj = r.json()
    out = {"source": f"{LAYER} (simplified on the server, maxAllowableOffset 0.004 degrees)",
           "credit": "Source: Office for National Statistics licensed under the Open Government Licence v.3.0. "
                     "Contains OS data © Crown copyright and database right 2025",
           "countries": {}}
    for f in gj["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = [[[round(x, 3), round(y, 3)] for x, y in ring] for poly in polys for ring in poly[:1] if len(ring) >= MIN_RING]
        out["countries"][f["properties"]["CTRY25NM"]] = rings
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print({k: (len(v), sum(map(len, v))) for k, v in out["countries"].items()}, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
