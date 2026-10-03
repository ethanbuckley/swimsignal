"""Where a clicked point is outside England: data/raw/outside_england.json, from the Office for
National Statistics' country boundaries. The any-point build copies it to
site/data/anypoint/outside_england.json, and the page answers a click inside it with "England
only" before it looks for a river.

    uv run python scripts/make_outside_england.py                 # downloads the boundaries (13 MB)
    uv run python scripts/make_outside_england.py countries.json  # or reads a GeoJSON already downloaded

Why: the water companies' overflow data covers England. Squares near the border have files, so a
click on the Taff in Cardiff or the Tweed at Kelso found no monitored overflow upstream and said
"No sewage risk from monitored overflows", when SwimSignal simply has no data there.

The shape is Wales and Scotland, widened by BUFFER_M into the sea and up the tidal rivers that the
boundaries leave out (they are clipped to mean high water, so the tidal Taff is in no country),
less every point nearer England than Wales or Scotland. The last step keeps the shared estuaries
fair: the Severn at Lydney, between two English banks, stays England, and the Wye at Chepstow is
split down the middle. Away from England the outline is simplified hard (SIMPLIFY_FAR_M), since
there it only has to cover the land; near England it keeps to SIMPLIFY_NEAR_M of the boundary.

Countries (December 2025) Boundaries UK BGC: generalised to 20 m, clipped to the coastline. ONS
boundaries are under the Open Government Licence v3.0; the file carries the two notices ONS asks
for (https://www.ons.gov.uk/methodology/geography/licences).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import shapely
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union

from dipcast import config

OUT = config.RAW / "outside_england.json"
LAYER = ("https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
         "Countries_December_2025_Boundaries_UK_BGC/FeatureServer/0")
URL = f"{LAYER}/query?where=1%3D1&outFields=CTRY25NM&outSR=27700&f=geojson"
CREDIT = ["Source: Office for National Statistics licensed under the Open Government Licence v.3.0",
          "Contains OS data © Crown copyright and database right 2026"]

BUFFER_M = 3000.0         # how far past Wales's and Scotland's mean high water the shape reaches
STEP_M = 100.0            # resolution of "nearer England": the split in a shared estuary is this close
NEAR_M = 5000.0           # within this of England the outline keeps its detail
OVERLAP_M = 2000.0        # the detailed and the rough parts overlap by this, so no sliver opens between them
SIMPLIFY_NEAR_M = 50.0
SIMPLIFY_FAR_M = 1000.0


def download() -> dict:
    r = httpx.get(URL, timeout=300, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def countries(doc: dict) -> dict[str, shapely.Geometry]:
    return {f["properties"]["CTRY25NM"]: shape(f["geometry"]).buffer(0) for f in doc["features"]}


def nearer_england(england: shapely.Geometry, other: shapely.Geometry, reach_m: float) -> shapely.Geometry:
    """Every point within reach_m of `other` that is nearer England than `other`, to STEP_M: a point
    is in it when, for some k, it lies within k*STEP_M of England and further than that from `other`."""
    # Only the parts of each country near the other can matter (a nearer-England point within
    # reach_m of `other` has its nearest English point within 2 * reach_m of `other`).
    e = england.intersection(other.buffer(2 * reach_m + STEP_M))
    o = other.intersection(england.buffer(3 * reach_m + STEP_M))
    if e.is_empty:
        return shapely.Polygon()
    rings = [e.buffer(k * STEP_M).difference(o.buffer(k * STEP_M)) for k in range(1, int(reach_m / STEP_M) + 2)]
    return unary_union(rings)


def outside_england(c: dict[str, shapely.Geometry]) -> shapely.Geometry:
    england, other = c["England"], unary_union([c["Wales"], c["Scotland"]])
    region = other.buffer(BUFFER_M).difference(england)
    region = region.difference(nearer_england(england, other, BUFFER_M))
    detail = region.intersection(england.buffer(NEAR_M)).simplify(SIMPLIFY_NEAR_M)
    # Widening by SIMPLIFY_FAR_M before simplifying keeps the rough part over the land it stands for;
    # it starts NEAR_M - OVERLAP_M from England, so it stays clear of English land.
    rough = region.difference(england.buffer(NEAR_M - OVERLAP_M)).buffer(SIMPLIFY_FAR_M).simplify(SIMPLIFY_FAR_M)
    out = unary_union([detail, rough]).buffer(0)
    # Drop specks the operations leave (a real piece of Wales or Scotland is far bigger), and every
    # hole: England has no enclave in either, so a hole is sea, such as Scapa Flow.
    return shapely.MultiPolygon([shapely.Polygon(p.exterior) for p in getattr(out, "geoms", [out]) if p.area > 1e6])


def to_wgs84(g: shapely.Geometry) -> dict:
    t = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    g = transform(t.transform, g)
    rnd = lambda ring: [[round(x, 5), round(y, 5)] for x, y in ring]   # 5 places: about a metre
    return {"type": "MultiPolygon", "coordinates": [[rnd(r) for r in poly] for poly in mapping(g)["coordinates"]]}


def main() -> None:
    doc = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else download()
    if (doc.get("crs") or {}).get("properties", {}).get("name", "").split(":")[-1] not in ("27700", ""):
        raise SystemExit("expected British National Grid (EPSG:27700); download with outSR=27700")
    region = outside_england(countries(doc))
    out = {"source": f"Office for National Statistics, Countries (December 2025) Boundaries UK BGC ({LAYER.rsplit('/', 2)[0]})",
           "licence": "Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)",
           "credit": CREDIT,
           "made": f"Wales and Scotland, widened {BUFFER_M / 1000:g} km past mean high water, less every point "
                   f"nearer England (to {STEP_M:g} m), simplified to {SIMPLIFY_NEAR_M:g} m within "
                   f"{NEAR_M / 1000:g} km of England and {SIMPLIFY_FAR_M:g} m elsewhere, by scripts/make_outside_england.py",
           "geometry": to_wgs84(region)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    n = sum(len(r) for poly in out["geometry"]["coordinates"] for r in poly)
    print(f"{len(out['geometry']['coordinates'])} polygons, {n:,} vertices, {OUT.stat().st_size / 1e3:,.0f} kB: {OUT}")


if __name__ == "__main__":
    main()
