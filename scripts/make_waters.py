"""The rivers and lakes the home page's search can find on the map: data/raw/waters.json, from
Ordnance Survey's OS Open Rivers and the Environment Agency's WFD lake water bodies. The build copies
it to site/data/waters.json, which the page fetches the first time three letters are typed in the
search, so what is typed never leaves the device (as data/places.json for Plan a swim).

    uv run python scripts/make_waters.py                       # config.RIVERS_GPKG and ingest/lakes.RAW
    uv run python scripts/make_waters.py RIVERS.gpkg LAKES.geojson

A search for a river with no listed spot ("River Kennet") used to end at "No spots match", although
a click on the map forecasts any point on it (17 Oct 2026). With this file the page offers the river,
and a press fits the map to it, ready for a tap.

Rivers: one entry per river of one name. Its links (watercourse_name; forms inlandRiver and
tidalRiver, not canals or lake centrelines; nor a name with "Canal" in it, which
OS gives some canal links) are joined where they share a node, and the pieces of one
name are joined again where their ends lie within JOIN_M of each other: OS leaves a named river in
pieces at weirs, side channels and short unnamed links (the Kennet came out as five). So four rivers
called Derwent stay four, and the Thames is one. A Welsh name with an English alternative is shown in
English ("River Wye", alternative "Afon Gwy"), and both are searched. Kept: at least MIN_KM of named
length in England, since the page forecasts England only; a river's box and middle are those of its
links in England.

Lakes: each WFD lake water body (cycle 3) in England with a name, its box and a point inside it.

Each entry is [name, alternative, kind, near, south, west, north, east, lat, lon, km]: kind is
"river" or "lake", the box to two
decimal places (about a kilometre), the middle (a point on the water nearest the box's centre) to
four, and the length in England to the nearest km (a lake's: the long side of the smallest rectangle
around it). `near` is the city or town nearest the middle, from data/raw/places.json, which tells
rivers of one name apart ("River Derwent, near Derby").

OS Open Rivers is OS OpenData under the Open Government Licence v3.0, and the WFD lake water bodies
are Environment Agency data under the same licence; the file carries both credits.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pyogrio
import shapely
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import shape

from dipcast import config
from dipcast.ingest import lakes

OUT = config.RAW / "waters.json"
PLACES = config.RAW / "places.json"
OUTLINE = config.RAW / "outside_england.json"
FORMS = {"inlandRiver", "tidalRiver"}
CANAL = r"(?i)\bcanal\b"   # OS gives some canal links the form inlandRiver ("Kennet and Avon Canal")
MIN_KM = 1.0
JOIN_M = 2000.0
TO_LL = Transformer.from_crs(27700, 4326, always_xy=True)
TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)


class Joins:
    """Union-find."""

    def __init__(self):
        self.up: dict = {}

    def find(self, a):
        self.up.setdefault(a, a)
        while self.up[a] != a:
            self.up[a] = self.up[self.up[a]]
            a = self.up[a]
        return a

    def join(self, a, b) -> None:
        self.up[self.find(a)] = self.find(b)


def towns() -> list:
    """The cities and towns of places.json: it runs cities A-Z, towns A-Z, then smaller places A-Z, so
    the towns end where the names start again at A for the second time."""
    places = json.loads(PLACES.read_text())["places"]
    resets = [i for i in range(1, len(places)) if places[i - 1][0][0] in "WXYZ" and places[i][0][0] == "A"]
    return places[:resets[1]]


def near_of(places: list):
    lat = np.array([p[1] for p in places])
    lon = np.array([p[2] for p in places])
    return lambda la, lo: places[int(np.argmin((lat - la) ** 2 + ((lon - lo) * np.cos(np.radians(la))) ** 2))][0]


def english(outline):
    shapely.prepare(outline)
    return lambda lon, lat: ~shapely.contains_xy(outline, lon, lat)


def rivers(gpkg: Path, in_england, near) -> list:
    cols = ["watercourse_name", "watercourse_name_alternative", "form", "start_node", "end_node", "length"]
    df = pyogrio.read_dataframe(gpkg, layer="watercourse_link", columns=cols)
    df = df[df["form"].isin(FORMS) & df["watercourse_name"].notna()]
    df = df[~df["watercourse_name"].str.contains(CANAL, regex=True)].reset_index(drop=True)
    g = df.geometry.values
    mids = shapely.line_interpolate_point(g, 0.5, normalized=True)
    lon, lat = TO_LL.transform(shapely.get_x(mids), shapely.get_y(mids))
    england = in_england(lon, lat)
    first, last = shapely.get_point(g, 0), shapely.get_point(g, -1)
    ends = np.stack([np.c_[shapely.get_x(first), shapely.get_y(first)], np.c_[shapely.get_x(last), shapely.get_y(last)]], axis=1)
    names, alts = df["watercourse_name"].str.strip().to_numpy(), df["watercourse_name_alternative"].to_numpy()
    starts, stops, length = df["start_node"].to_numpy(), df["end_node"].to_numpy(), df["length"].to_numpy()

    by_name: dict[str, list[int]] = defaultdict(list)
    for i, n in enumerate(names):
        by_name[n].append(i)
    out = []
    for name, idx in by_name.items():
        nodes = Joins()
        for i in idx:
            nodes.join(starts[i], stops[i])
        pieces: dict[str, list[int]] = defaultdict(list)
        for i in idx:
            pieces[nodes.find(starts[i])].append(i)
        pieces = list(pieces.values())
        if len(pieces) > 1:   # the pieces of one name whose ends are within JOIN_M are one river
            owner = np.repeat(np.arange(len(pieces)), [2 * len(p) for p in pieces])
            pts = np.concatenate([ends[p].reshape(-1, 2) for p in pieces])
            near_pairs = cKDTree(pts).query_pairs(JOIN_M, output_type="ndarray")
            same = Joins()
            for a, b in near_pairs:
                same.join(int(owner[a]), int(owner[b]))
            grouped: dict[int, list[int]] = defaultdict(list)
            for k, p in enumerate(pieces):
                grouped[same.find(k)].extend(p)
            pieces = list(grouped.values())
        for part in pieces:
            eng = np.array([i for i in part if england[i]], dtype=int)
            km = float(length[eng].sum()) / 1000 if len(eng) else 0.0
            if km < MIN_KM:
                continue
            la, lo = lat[eng], lon[eng]
            s, w, n, e = la.min(), lo.min(), la.max(), lo.max()
            c = int(np.argmin((la - (s + n) / 2) ** 2 + ((lo - (w + e) / 2) * np.cos(np.radians(la))) ** 2))
            # The alternative name of at least half the river's length: OS also gives local names to
            # short reaches ("Amerdale Dub" on the Wharfe), which are not another name for the river.
            by_len: Counter = Counter()
            for i in part:
                if isinstance(alts[i], str) and alts[i].strip() and alts[i].strip() != name:
                    by_len[alts[i].strip()] += length[i]
            alt = by_len.most_common(1)
            alt = alt[0][0] if alt and alt[0][1] >= 0.5 * length[part].sum() else ""
            shown, other = (alt, name) if name.startswith("Afon ") and alt and not alt.startswith("Afon ") else (name, alt)
            out.append([shown, other, "river", near(float(la[c]), float(lo[c])), round(float(s), 2), round(float(w), 2), round(float(n), 2),
                        round(float(e), 2), round(float(la[c]), 4), round(float(lo[c]), 4), round(km)])
    return out


def lake_rows(path: Path, in_england, near) -> list:
    out = []
    for f in json.loads(path.read_text())["features"]:
        name = (f["properties"].get("WB_NAME") or "").strip()
        if not name:
            continue
        geom = shape(f["geometry"])
        p = geom.representative_point()
        if not in_england(np.array([p.x]), np.array([p.y]))[0]:
            continue
        w, s, e, n = geom.bounds
        bng = shapely.transform(geom, lambda xy: np.c_[TO_BNG.transform(xy[:, 0], xy[:, 1])])
        rect = shapely.minimum_rotated_rectangle(bng)
        xy = np.asarray(rect.exterior.coords)
        long = max(np.hypot(*(xy[1] - xy[0])), np.hypot(*(xy[2] - xy[1]))) / 1000
        out.append([name, "", "lake", near(p.y, p.x), round(s, 2), round(w, 2), round(n, 2), round(e, 2),
                    round(p.y, 4), round(p.x, 4), max(1, round(long))])
    return out


def main(gpkg: Path = config.RIVERS_GPKG, lakes_path: Path = lakes.RAW) -> None:
    in_england = english(shape(json.loads(OUTLINE.read_text())["geometry"]))
    near = near_of(towns())
    out = rivers(gpkg, in_england, near) + lake_rows(lakes_path, in_england, near)
    out.sort(key=lambda r: (-r[10], r[0], r[3]))   # the longest first, so a page offers the big river of a name first
    doc = {
        "source": ["Ordnance Survey, OS Open Rivers (https://www.ordnancesurvey.co.uk/products/os-open-rivers)",
                   "Environment Agency, WFD Lake Water Bodies Cycle 3"],
        "licence": "Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)",
        "credit": "Contains OS data © Crown copyright and database right 2026. © Environment Agency copyright and/or database right 2026.",
        "fields": ["name", "alternative", "kind", "near", "south", "west", "north", "east", "lat", "lon", "km"],
        "waters": out,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    print(f"{len(out)} waters, {OUT.stat().st_size / 1e3:.0f} kB -> {OUT}")


if __name__ == "__main__":
    main(*(Path(a) for a in sys.argv[1:3]))
