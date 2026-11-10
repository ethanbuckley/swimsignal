"""River names for a click outside England: data/raw/outside_names/. The any-point build copies the folder to
site/data/anypoint/names/, and the page names the water nearest a click in Wales, Scotland or Ireland, which has no
forecast, instead of calling it "This point".

    uv run python scripts/make_outside_names.py OS_GPKG [RIVERS_JSON LAKES_JSON]

OS_GPKG is OS Open Rivers for Great Britain (oprvrs_gb.gpkg, about 118 MB from
https://osdatahub.os.uk/downloads/open/OpenRivers). RIVERS_JSON and LAKES_JSON are the Overpass API's answers to
OSM_QUERY (about 65 MB) and LAKES_QUERY (about 120 MB); without them the script asks for them.

Two sources, kept in two folders because their licences differ:

- os/: Wales and Scotland, from OS Open Rivers (Open Government Licence v3.0). Every named watercourse link, and every
  link through a lake with its name left out: OS names those after a stream ("Arn Burn" and "Finlas Water" through
  Loch Lomond), so a click nearest one keeps "This point". A Welsh name with an English alternative is given in
  English, as on the rest of the site (build_any_point.english_names).
- osm/: from OpenStreetMap (ODbL 1.0, LICENSE-DATA.md): the island of Ireland's named rivers, canals and streams,
  and the named lakes of Ireland, Wales and Scotland of at least MIN_LAKE_M2 ("lakes"), so that a click on a lake
  is given the lake's name, never a stream's: OSM's streams stop at the shore, and a tap on Lough Derg 350 m off the
  Nenagh River's mouth said "Nenagh River" without them. The English name where there is one (name:en), else the
  name.

Lines of one name are joined, simplified to SIMPLIFY_M in metres (British or Irish National Grid), cut at the edges
of the any-point squares (build_any_point.TILE_DEG) and written per square, kept only for squares within REACH_DEG of
Wales and Scotland or of the island (outside_england.json): a click near the border can be nearest a line in England.

A square's file: {"names": [...], "lines": [[name, x0, y0, dx1, dy1, ...], ...], "lakes": [[name, x0, y0, ...], ...]}:
name an index into names, -1 for a line through a lake; x, y in units of Q degrees east and north of the square's
south-west corner, then differences. A lake is its whole outline (a closed ring) in every square it reaches; a line
is cut at the square's edges.
index.json lists each source's squares and its credit.
"""

from __future__ import annotations

import importlib.util
import json
import math
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pyogrio
import shapely
from pyproj import Transformer
from shapely.geometry import box, shape

from dipcast import config

OUT = config.RAW / "outside_names"
OUTSIDE = config.RAW / "outside_england.json"
TILE_DEG = 0.25        # build_any_point.TILE_DEG: the page fetches the squares near a click
SIMPLIFY_M = 50.0      # os/ 2.2 MB; 25 m was 2.9 MB and 100 m 1.7 MB with the lake lines (10 Nov 2026)
Q = 1e-4               # about 11 m north-south
REACH_DEG = 0.03       # beyond PIN_SNAP_M (1.5 km) from the outline, in degrees of longitude at 50 N
MIN_LAKE_M2 = 10_000   # a hectare: 0.5 ha cost 0.08 MB more, 2 ha saved 0.11 MB (10 Nov 2026)
OSM_QUERY = ('[out:json][timeout:300];(area["ISO3166-1"="IE"][admin_level=2];area["ISO3166-2"="GB-NIR"];)->.a;'
             'way(area.a)[waterway~"^(river|canal|stream)$"][name];out geom qt;')
_NOT_LAKE = '[water!~"^(river|canal|stream|riverbank|moat|pond|basin|wastewater|ditch|drain)$"]'
LAKES_QUERY = ('[out:json][timeout:600];(area["ISO3166-1"="IE"][admin_level=2];area["ISO3166-2"="GB-NIR"];'
               'area["ISO3166-2"="GB-SCT"];area["ISO3166-2"="GB-WLS"];)->.a;'
               f'(way(area.a)[natural=water][name]{_NOT_LAKE};relation(area.a)[natural=water][name]{_NOT_LAKE};);out geom qt;')
OVERPASS = "https://overpass-api.de/api/interpreter"
CREDITS = {
    "os": {"source": "OS Open Rivers", "licence": "Open Government Licence v3.0",
           "credit": "Contains OS data © Crown copyright and database right 2026"},
    "osm": {"source": "OpenStreetMap", "licence": "Open Database Licence 1.0",
            "credit": "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)"},
}
TO_WGS = {c: Transformer.from_crs(c, 4326, always_xy=True) for c in (27700, 2157, 3035)}
FROM_WGS = {c: Transformer.from_crs(4326, c, always_xy=True) for c in (2157, 3035)}


def english_names(links: pd.DataFrame) -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("build_any_point", Path(__file__).with_name("build_any_point.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.english_names(links)


def region(part: str) -> shapely.Geometry:
    """outside_england.json's Wales and Scotland ("wales_scotland") or the island ("ireland"), in degrees."""
    o = json.loads(OUTSIDE.read_text())
    polys = [shape({"type": "Polygon", "coordinates": c}) for c, p in zip(o["geometry"]["coordinates"], o["parts"], strict=True)
             if p == part]
    return shapely.union_all(polys)


def squares_near(area: shapely.Geometry) -> set[str]:
    """The squares within REACH_DEG of `area`."""
    near = area.buffer(REACH_DEG)
    shapely.prepare(near)
    w, s, e, n = near.bounds
    out = set()
    for r in range(math.floor(s / TILE_DEG), math.floor(n / TILE_DEG) + 1):
        for c in range(math.floor(w / TILE_DEG), math.floor(e / TILE_DEG) + 1):
            if near.intersects(box(c * TILE_DEG, r * TILE_DEG, (c + 1) * TILE_DEG, (r + 1) * TILE_DEG)):
                out.add(f"{r}_{c}")
    return out


def _squares(geom: shapely.Geometry, keep: set[str]):
    """The squares in `keep` that `geom` (degrees) touches: (key, row, column, the square's box)."""
    w, s, e, n = geom.bounds
    for r in range(math.floor(s / TILE_DEG), math.floor(n / TILE_DEG) + 1):
        for c in range(math.floor(w / TILE_DEG), math.floor(e / TILE_DEG) + 1):
            key, sq = f"{r}_{c}", box(c * TILE_DEG, r * TILE_DEG, (c + 1) * TILE_DEG, (r + 1) * TILE_DEG)
            if key in keep and geom.intersects(sq):
                yield key, r, c, sq


def _flat(coords: np.ndarray, r: int, c: int) -> list[int] | None:
    """Points in Q units from the square's south-west corner, the first as it is and the rest as differences, with
    no point repeated; None where fewer than two are left."""
    q = np.round((coords - [c * TILE_DEG, r * TILE_DEG]) / Q).astype(int)
    q = q[np.r_[True, np.any(np.diff(q, axis=0) != 0, axis=1)]]
    return np.r_[q[:1], np.diff(q, axis=0)].ravel().tolist() if len(q) >= 2 else None


def to_wgs(g: shapely.Geometry, crs: int) -> shapely.Geometry:
    return shapely.transform(g, lambda xy: np.c_[TO_WGS[crs].transform(xy[:, 0], xy[:, 1])])


def line_pieces(lines: list[tuple[str | None, shapely.Geometry]], crs: int, keep: set[str]) -> dict:
    """{square: {name: [flat line, ...]}} for `lines`, (name, or None for a line through a lake; metric geometry):
    joined by name, simplified, cut at the squares' edges, for the squares in `keep`."""
    groups: dict[str | None, list] = defaultdict(list)
    for name, g in lines:
        groups[name].append(g)
    per: dict = defaultdict(lambda: defaultdict(list))
    for name in sorted(groups, key=lambda n: (n is not None, n or "")):
        merged = shapely.simplify(shapely.line_merge(shapely.union_all(groups[name])), SIMPLIFY_M)
        for part in shapely.get_parts(merged):
            if part.is_empty or len(shapely.get_coordinates(part)) < 2:
                continue
            line = to_wgs(part, crs)
            for key, r, c, sq in _squares(line, keep):
                cut = line.intersection(sq)
                for piece in shapely.get_parts(shapely.line_merge(cut) if cut.geom_type == "MultiLineString" else cut):
                    if piece.geom_type == "LineString" and not piece.is_empty and (f := _flat(shapely.get_coordinates(piece), r, c)):
                        per[key][name].append(f)
    return per


def lake_pieces(lakes: list[tuple[str, shapely.Geometry]], crs: int, keep: set[str]) -> dict:
    """{square: {name: [flat ring, ...]}} for named lakes (metric polygons): each outline simplified, whole, in every
    square of `keep` that the lake reaches, so the page can tell whether a click is on it from one square."""
    per: dict = defaultdict(lambda: defaultdict(list))
    for name, poly in lakes:
        for part in shapely.get_parts(shapely.simplify(poly, SIMPLIFY_M)):
            if part.geom_type != "Polygon" or part.is_empty or part.area < MIN_LAKE_M2:
                continue
            ring = to_wgs(part.exterior, crs)
            for key, r, c, _ in _squares(shapely.Polygon(ring), keep):
                if f := _flat(shapely.get_coordinates(ring), r, c):
                    per[key][name].append(f)
    return per


def tiles_of(lines: dict, lakes: dict | None = None) -> dict[str, dict]:
    """The square files from line_pieces and lake_pieces."""
    lakes = lakes or {}
    out = {}
    for key in sorted(set(lines) | set(lakes)):
        ln, lk = lines.get(key, {}), lakes.get(key, {})
        names = sorted({n for n in ln if n is not None} | set(lk))
        ix = {n: i for i, n in enumerate(names)}
        body = {"names": names, "lines": [[-1 if n is None else ix[n], *v]
                                          for n in sorted(ln, key=lambda n: (n is not None, n or "")) for v in ln[n]]}
        if lk:
            body["lakes"] = [[ix[n], *v] for n in sorted(lk) for v in lk[n]]
        out[key] = body
    return out


def os_lines(gpkg: Path) -> list[tuple[str | None, shapely.Geometry]]:
    df = pyogrio.read_dataframe(gpkg, layer="watercourse_link",
                                columns=["watercourse_name", "watercourse_name_alternative", "form", "length"])
    english = english_names(df)
    lake = df["form"].eq("lake").to_numpy()
    names = df["watercourse_name"].astype("string").str.strip()
    out = []
    for g, n, is_lake in zip(df.geometry.to_numpy(), names, lake, strict=True):
        if is_lake:
            out.append((None, g))
        elif isinstance(n, str) and n:
            out.append((english.get(n, n), g))
    return out


def osm_lines(answer: dict) -> list[tuple[str | None, shapely.Geometry]]:
    out = []
    for el in answer["elements"]:
        tags, geom = el.get("tags", {}), el.get("geometry") or []
        name = (tags.get("name:en") or tags.get("name") or "").strip()
        if el.get("type") != "way" or not name or len(geom) < 2:
            continue
        x, y = FROM_WGS[2157].transform([p["lon"] for p in geom], [p["lat"] for p in geom])
        out.append((name, shapely.LineString(np.c_[x, y])))
    return out


def osm_lakes(answer: dict) -> list[tuple[str, shapely.Geometry]]:
    """Named lakes (LAKES_QUERY's answer) as metric polygons: a closed way, or a relation's outer ways joined. Islands
    are left in: a click on one is still said to be on the lake."""
    out = []
    for el in answer["elements"]:
        tags = el.get("tags", {})
        name = (tags.get("name:en") or tags.get("name") or "").strip()
        if not name:
            continue
        if el["type"] == "way":
            rings = [el.get("geometry") or []]
        else:
            rings = [m.get("geometry") or [] for m in el.get("members", []) if m.get("type") == "way" and m.get("role") == "outer"]
        lines = []
        for g in rings:
            if len(g) >= 2:
                x, y = FROM_WGS[3035].transform([p["lon"] for p in g], [p["lat"] for p in g])
                lines.append(shapely.LineString(np.c_[x, y]))
        if not lines:
            continue
        polys = shapely.get_parts(shapely.polygonize([shapely.line_merge(shapely.union_all(lines))]))
        for p in polys:
            if p.is_valid and p.area >= MIN_LAKE_M2:
                out.append((name, p))
    return out


def write(source: str, tiles: dict[str, dict], index: dict) -> int:
    d = OUT / source
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    size = 0
    for key, body in tiles.items():
        text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        (d / f"{key}.json").write_text(text, encoding="utf-8")
        size += len(text.encode())
    index["sources"][source] = {**CREDITS[source], "tiles": sorted(tiles), "bytes": size}
    return size


def overpass(query: str, path: str | None) -> dict:
    if path:
        return json.loads(Path(path).read_text())
    r = httpx.post(OVERPASS, data={"data": query}, timeout=900, headers={"User-Agent": "swimsignal-data"})
    r.raise_for_status()
    return r.json()


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    gpkg = Path(argv[0])
    rivers = overpass(OSM_QUERY, argv[1] if len(argv) > 1 else None)
    lakes = overpass(LAKES_QUERY, argv[2] if len(argv) > 2 else None)
    gb, ie = squares_near(region("wales_scotland")), squares_near(region("ireland"))
    index = {"version": 1, "tile_deg": TILE_DEG, "q": Q, "simplify_m": SIMPLIFY_M,
             "osm_base": min(a.get("osm3s", {}).get("timestamp_osm_base") or "" for a in (rivers, lakes)), "sources": {}}
    os_size = write("os", tiles_of(line_pieces(os_lines(gpkg), 27700, gb)), index)
    osm_size = write("osm", tiles_of(line_pieces(osm_lines(rivers), 2157, ie), lake_pieces(osm_lakes(lakes), 3035, gb | ie)), index)
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"os: {len(index['sources']['os']['tiles'])} squares, {os_size / 1e6:.2f} MB; "
          f"osm: {len(index['sources']['osm']['tiles'])} squares, {osm_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main(sys.argv[1:])
