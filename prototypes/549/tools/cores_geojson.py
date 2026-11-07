"""The open-water core pixels each pilot reading uses, as GeoJSON for the #550 prototype map.

Reads data/research/satellite/cores/<id>.npz (one 101x101 boolean per Sentinel-2 tile, 20 m pixels, centred on the
site: scripts/lake_algae_sat_eval/stac.py window_for with COMPONENT_RADIUS_M 1000) and each site's point from the
public lakes.json. The window's grid is rebuilt from the tile's UTM zone, whose 20 m grid sits on multiples of 20 m,
so this is a reconstruction for the prototype; the research manifest's core.png (lake_imagery.v1) replaces it.

uv run python prototypes/549/tools/cores_geojson.py lakes.json > prototypes/549/data/cores.geojson
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[3]
PIXEL, HALF = 20, 50


def zone_epsg(tile_key: str) -> int:   # "MGRS_30UVF" -> 32630 (all pilot sites are north of the equator)
    return 32600 + int(tile_key.split("_")[1][:2])


def main(lakes_path: str) -> None:
    lakes = {x["lake_id"]: x for x in json.loads(Path(lakes_path).read_text())["lakes"]}
    feats = []
    for f in sorted((ROOT / "data/research/satellite/cores").glob("*.npz")):
        site = f.stem
        z = np.load(f, allow_pickle=False)
        key = sorted(z.files)[0]
        core = z[key]
        lon, lat = lakes[site]["lon"], lakes[site]["lat"]
        fwd = Transformer.from_crs(4326, zone_epsg(key), always_xy=True)
        back = Transformer.from_crs(zone_epsg(key), 4326, always_xy=True)
        x, y = fwd.transform(lon, lat)
        left = PIXEL * math.floor(x / PIXEL) - HALF * PIXEL          # column c0's left edge
        top = PIXEL * math.floor(y / PIXEL) + PIXEL + HALF * PIXEL   # row r0's top edge (rows run south)
        polys = []
        for r, c in zip(*np.nonzero(core)):
            x0, y0 = left + c * PIXEL, top - r * PIXEL
            ring = [back.transform(px, py) for px, py in ((x0, y0), (x0 + PIXEL, y0), (x0 + PIXEL, y0 - PIXEL), (x0, y0 - PIXEL), (x0, y0))]
            polys.append([[[round(a, 6), round(b, 6)] for a, b in ring]])
        feats.append({"type": "Feature", "properties": {"lake_id": site, "tile": key, "core_pixels": int(core.sum()), "pixel_m": PIXEL,
                                                        "source": f"data/research/satellite/cores/{f.name}"},
                      "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    json.dump({"type": "FeatureCollection", "features": feats}, sys.stdout)


if __name__ == "__main__":
    main(sys.argv[1])
