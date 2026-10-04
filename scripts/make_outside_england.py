"""Where a clicked point is outside England: data/raw/outside_england.json, from the Office for
National Statistics' UK country boundaries and Tailte Éireann's boundaries of the Republic of
Ireland. The any-point build copies it to site/data/anypoint/outside_england.json, and the page
answers a click inside it with "England only" before it looks for a river.

    uv run python scripts/make_outside_england.py                    # downloads both (13 MB and 1.7 MB)
    uv run python scripts/make_outside_england.py countries.json provinces.json   # or reads them already downloaded

Why: the water companies' overflow data covers England. Squares near the border have files, so a
click on the Taff in Cardiff or the Tweed at Kelso found no monitored overflow upstream and said
"No sewage risk from monitored overflows", when SwimSignal simply has no data there. In Ireland
there are no squares at all, so a click in Belfast or Dublin said "No river or lake near this
point has a monitored storm overflow within 60 km upstream": SwimSignal's river network has no
link on the island and it reads no Irish overflow data, so it has no basis for that.

The file has three parts:

- `geometry`, one MultiPolygon: everywhere outside England. First Wales and Scotland, widened by
  BUFFER_M into the sea and up the tidal rivers that the boundaries leave out (they are clipped to
  mean high water, so the tidal Taff is in no country), less every point nearer England than Wales
  or Scotland. The last step keeps the shared estuaries fair: the Severn at Lydney, between two
  English banks, stays England, and the Wye at Chepstow is split down the middle. Away from England
  the outline is simplified hard (SIMPLIFY_FAR_M), since there it only has to cover the land; near
  England it keeps to SIMPLIFY_NEAR_M of the boundary. Then the island of Ireland, widened further
  (IRELAND_BUFFER_M) and simplified hard all round: no part of it is near England.
- `parts`: for each polygon of `geometry`, "wales_scotland" or "ireland".
- `northern_ireland`: Northern Ireland, widened as far, less every point nearer the Republic,
  with its detail kept near the border. A click on the island inside it is in Northern Ireland, and
  anywhere else on the island it is in the Republic, so the page can name the right official
  source. It is only read for a click on the island, so it never decides "England only".

Countries (December 2025) Boundaries UK BGC: generalised to 20 m, clipped to the coastline. ONS
boundaries are under the Open Government Licence v3.0; the file carries the two notices ONS asks
for (https://www.ons.gov.uk/methodology/geography/licences). Provinces - National Statutory
Boundaries - 2019 - Generalised 20m: the Republic's four provinces, whose union is the State, in
Irish Transverse Mercator (EPSG:2157), © Tailte Éireann under CC BY 4.0; the file carries the
credit and says what was changed. The island's shapes are worked in Irish Transverse Mercator,
so Northern Ireland is moved there from British National Grid.
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
IE_LAYER = ("https://services-eu1.arcgis.com/FH5XCsx8rYXqnjF5/arcgis/rest/services/"
            "Provinces___OSi_National_Statutory_Boundaries___Generalised_20m/FeatureServer/0")
IE_URL = f"{IE_LAYER}/query?where=1%3D1&outFields=PROVINCE&outSR=2157&geometryPrecision=0&f=geojson"
IE_ITEM = "https://www.arcgis.com/home/item.html?id=1b341039d3344c74b95293012312f44d"
IE_CREDIT = ("© Tailte Éireann. Provinces - National Statutory Boundaries - 2019 - Generalised 20m, licensed under "
             "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changed by SwimSignal: the provinces joined, "
             "widened and simplified. Tailte Éireann accepts no liability for errors in the data.")

BUFFER_M = 3000.0         # how far past Wales's and Scotland's mean high water the shape reaches
# The island of Ireland reaches further: England is 116 km off at its nearest, so widening costs
# nothing, and it covers the middle of its sea loughs and bays (a point in the middle of Lough Foyle is
# 4.9 km from the nearest shore). Scotland is 20 km off, and make() checks the two shapes stay apart.
IRELAND_BUFFER_M = 8000.0
STEP_M = 100.0            # resolution of "nearer England": the split in a shared estuary is this close
# In Ireland the split between Northern Ireland and the Republic only picks which official source a click
# names, never whether it has a forecast, so it is worked coarser: in shared water (Lough Foyle, Carlingford
# Lough) to IRELAND_STEP_M, on outlines simplified to half that. On land the boundaries decide it.
IRELAND_STEP_M = 250.0
NEAR_M = 5000.0           # within this of the neighbour the outline keeps its detail
OVERLAP_M = 2000.0        # the detailed and the rough parts overlap by this, so no sliver opens between them
SIMPLIFY_NEAR_M = 50.0
SIMPLIFY_FAR_M = 1000.0


def download(url: str) -> dict:
    r = httpx.get(url, timeout=300, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def crs_of(doc: dict) -> str:
    return (doc.get("crs") or {}).get("properties", {}).get("name", "").split(":")[-1]


def countries(doc: dict) -> dict[str, shapely.Geometry]:
    return {f["properties"]["CTRY25NM"]: shape(f["geometry"]).buffer(0) for f in doc["features"]}


def republic(doc: dict) -> shapely.Geometry:
    """The State: the union of its four provinces."""
    return unary_union([shape(f["geometry"]).buffer(0) for f in doc["features"]])


def nearer(neighbour: shapely.Geometry, home: shapely.Geometry, reach_m: float, step_m: float = STEP_M) -> shapely.Geometry:
    """Every point within reach_m of `home` that is nearer `neighbour` than `home`, to step_m: a point
    is in it when, for some k, it lies within k*step_m of `neighbour` and further than that from `home`."""
    # Only the parts of each near the other can matter (a nearer-neighbour point within reach_m of
    # `home` has its nearest neighbouring point within 2 * reach_m of `home`).
    e = neighbour.intersection(home.buffer(2 * reach_m + step_m))
    o = home.intersection(neighbour.buffer(3 * reach_m + step_m))
    if e.is_empty:
        return shapely.Polygon()
    rings = [e.buffer(k * step_m).difference(o.buffer(k * step_m)) for k in range(1, int(reach_m / step_m) + 2)]
    return unary_union(rings)


def polygons(g: shapely.Geometry) -> shapely.MultiPolygon:
    """The pieces of g without specks (a real piece of land, widened, is far bigger) or holes: no
    country here has an enclave of its neighbour, so a hole is sea or a lake, such as Scapa Flow."""
    return shapely.MultiPolygon([shapely.Polygon(p.exterior) for p in getattr(g, "geoms", [g]) if p.area > 1e6])


def outside(home: shapely.Geometry, neighbour: shapely.Geometry, buffer_m: float = BUFFER_M,
            step_m: float = STEP_M) -> shapely.MultiPolygon:
    """`home` widened by buffer_m, less `neighbour` and every point nearer it (to step_m), simplified to
    SIMPLIFY_NEAR_M within NEAR_M of `neighbour` and to SIMPLIFY_FAR_M elsewhere."""
    region = home.buffer(buffer_m).difference(neighbour)
    # Coarser than STEP_M, the split is worked on outlines simplified to half the step: a point of
    # `home` is then within half a step of the simplified outline, so it is never counted nearer.
    h, n = (home, neighbour) if step_m <= STEP_M else (home.simplify(step_m / 2), neighbour.simplify(step_m / 2))
    region = region.difference(nearer(n, h, buffer_m, step_m))
    detail = region.intersection(neighbour.buffer(NEAR_M)).simplify(SIMPLIFY_NEAR_M)
    # Widening by SIMPLIFY_FAR_M before simplifying keeps the rough part over the land it stands for;
    # it starts NEAR_M - OVERLAP_M from the neighbour, so it stays clear of the neighbour's land.
    rough = region.difference(neighbour.buffer(NEAR_M - OVERLAP_M)).buffer(SIMPLIFY_FAR_M).simplify(SIMPLIFY_FAR_M)
    return polygons(unary_union([detail, rough]).buffer(0))


def outside_england(c: dict[str, shapely.Geometry]) -> shapely.MultiPolygon:
    return outside(unary_union([c["Wales"], c["Scotland"]]), c["England"])


def island(ni: shapely.Geometry, roi: shapely.Geometry) -> shapely.MultiPolygon:
    """The island of Ireland, widened by IRELAND_BUFFER_M and simplified to SIMPLIFY_FAR_M, widened that
    much more first so it still covers the land. One shape, so no sliver opens along the border. Its edge
    is kilometres out at sea, so the coast is simplified to IRELAND_STEP_M first, and the widening made
    that much longer: buffering every inlet and islet of the full outline is slow and changes nothing."""
    land = unary_union([ni, roi]).simplify(IRELAND_STEP_M)
    wide = land.buffer(IRELAND_BUFFER_M + SIMPLIFY_FAR_M + IRELAND_STEP_M, quad_segs=4)
    return polygons(wide.simplify(SIMPLIFY_FAR_M).buffer(0))


def northern_ireland(ni: shapely.Geometry, roi: shapely.Geometry) -> shapely.MultiPolygon:
    """Northern Ireland, widened by IRELAND_BUFFER_M, less the Republic and every point nearer it. Only
    the Republic within reach of Northern Ireland can matter, so the rest is cut away first."""
    near = roi.intersection(ni.buffer(3 * IRELAND_BUFFER_M + NEAR_M))
    return outside(ni, near, IRELAND_BUFFER_M, IRELAND_STEP_M)


def to_wgs84(g: shapely.Geometry, epsg: int) -> dict:
    t = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    g = transform(t.transform, g)
    rnd = lambda ring: [[round(x, 5), round(y, 5)] for x, y in ring]   # 5 places: about a metre
    return {"type": "MultiPolygon", "coordinates": [[rnd(r) for r in poly] for poly in mapping(g)["coordinates"]]}


def make(uk: dict, ie: dict) -> dict:
    if crs_of(uk) not in ("27700", ""):
        raise SystemExit("expected the ONS countries in British National Grid (EPSG:27700); download with outSR=27700")
    if crs_of(ie) != "2157":
        raise SystemExit("expected the provinces in Irish Transverse Mercator (EPSG:2157); download with outSR=2157")
    c = countries(uk)
    gb = to_wgs84(outside_england(c), 27700)
    ni = transform(Transformer.from_crs("EPSG:27700", "EPSG:2157", always_xy=True).transform, c["Northern Ireland"]).buffer(0)
    roi = republic(ie)
    whole = to_wgs84(island(ni, roi), 2157)
    north = to_wgs84(northern_ireland(ni, roi), 2157)
    if shape(whole).intersects(shape(gb)):   # a click there would be named the wrong country
        raise SystemExit("the island of Ireland's shape reaches Scotland's: widen it less")
    return {"source": [f"Office for National Statistics, Countries (December 2025) Boundaries UK BGC ({LAYER.rsplit('/', 2)[0]})",
                       f"Tailte Éireann, Provinces - National Statutory Boundaries - 2019 - Generalised 20m ({IE_ITEM})"],
            "licence": ["Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)",
                        "Creative Commons Attribution 4.0 International (https://creativecommons.org/licenses/by/4.0/)"],
            "credit": [*CREDIT, IE_CREDIT],
            "made": f"Wales and Scotland, widened {BUFFER_M / 1000:g} km past mean high water, less every point nearer "
                    f"England (to {STEP_M:g} m), simplified to {SIMPLIFY_NEAR_M:g} m within {NEAR_M / 1000:g} km of "
                    f"England and {SIMPLIFY_FAR_M:g} m elsewhere; then the island of Ireland (Northern Ireland and the "
                    f"Republic's provinces), widened {IRELAND_BUFFER_M / 1000:g} km and simplified to {SIMPLIFY_FAR_M:g} m. "
                    f"northern_ireland: Northern Ireland widened {IRELAND_BUFFER_M / 1000:g} km, less every point nearer the "
                    f"Republic (to {IRELAND_STEP_M:g} m), simplified to {SIMPLIFY_NEAR_M:g} m within {NEAR_M / 1000:g} km of "
                    f"the Republic and {SIMPLIFY_FAR_M:g} m elsewhere. By scripts/make_outside_england.py",
            "geometry": {"type": "MultiPolygon", "coordinates": gb["coordinates"] + whole["coordinates"]},
            "parts": ["wales_scotland"] * len(gb["coordinates"]) + ["ireland"] * len(whole["coordinates"]),
            "northern_ireland": north}


def main() -> None:
    uk = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else download(URL)
    ie = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else download(IE_URL)
    out = make(uk, ie)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    count = lambda g: sum(len(r) for poly in g["coordinates"] for r in poly)
    print(f"{out['parts'].count('wales_scotland')} polygons in Wales and Scotland, {out['parts'].count('ireland')} on the "
          f"island of Ireland, {count(out['geometry']):,} vertices; northern_ireland {count(out['northern_ireland']):,} "
          f"vertices; {OUT.stat().st_size / 1e3:,.0f} kB: {OUT}")


if __name__ == "__main__":
    main()
