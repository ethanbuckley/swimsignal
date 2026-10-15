"""The shortest way through a lake's water between two points (lake distance "water",
docs/LAKE-DISTANCE-2026-10.md).

A lake spot's distance from where an overflow's water enters the lake to the spot was a straight
line (transport.upstream_overflows). In a lake that bends, that line crosses land: Pooley Bridge,
at the foot of Ullswater, had 6.7 of 10.9 km outside the lake. Here the distance is the shortest
path that stays inside the WFD lake polygons the spot's lake is made of. Where the straight line
stays in the water, it is that line.

How:
* The water is the union of the WFD lake polygons the lake's centreline links lie in (Windermere's
  two basins become one water), simplified to WATER_SIMPLIFY_M.
* A shortest path inside a polygon is straight between corners, and turns only at corners that
  point into the water (reflex corners: on the shore, where the land juts in; on an island, any
  corner). Those corners are the graph's nodes; two are joined when the segment between them stays
  inside the water widened by WATER_SIMPLIFY_M (so the simplification cannot block a channel). All
  shortest paths between corners are computed once per water.
* A point outside the water (an entry where a beck's line starts on the bank, a pin on the shore)
  first goes straight to the nearest point of the water; that leg is added to the distance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import shapely
from shapely.ops import nearest_points
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path

WATER_SIMPLIFY_M = 10.0   # the polygons' simplification, and the widening a segment may use


@dataclass(frozen=True)
class Water:
    region: object        # the water, simplified (shapely Polygon or MultiPolygon)
    test: object          # the water widened by WATER_SIMPLIFY_M, prepared: what a segment must stay in
    xy: np.ndarray        # (n, 2) reflex corners
    dist: np.ndarray      # (n, n) shortest path between corners, inf where none


def _reflex_corners(region) -> np.ndarray:
    """Corners of the water where a path through it can turn: on each ring, those with the water on
    the outside of the angle. Rings are oriented with the water on the left (exterior anticlockwise,
    holes clockwise), so a corner turns right (cross product < 0) exactly when it is reflex."""
    out = []
    for poly in getattr(region, "geoms", [region]):
        poly = shapely.orient_polygons(poly)
        for ring in [poly.exterior, *poly.interiors]:
            c = np.asarray(ring.coords)[:-1, :2]
            if len(c) < 3:
                continue
            prev, nxt = np.roll(c, 1, axis=0), np.roll(c, -1, axis=0)
            a, b = c - prev, nxt - c
            cross = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
            out.append(c[cross < 0])
    return np.concatenate(out) if out else np.zeros((0, 2))


def _segments(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return shapely.linestrings(np.stack([a, b], axis=1))


@lru_cache(maxsize=64)
def water(polygons: tuple) -> Water:
    """The water made of these WFD lake polygons (a tuple of shapely geometries, so it can be cached)."""
    region = shapely.unary_union([shapely.make_valid(p) for p in polygons])
    region = shapely.simplify(region, WATER_SIMPLIFY_M, preserve_topology=True)
    test = shapely.buffer(region, WATER_SIMPLIFY_M)
    shapely.prepare(test)
    xy = _reflex_corners(region)
    n = len(xy)
    dist = np.full((n, n), np.inf)
    if n:
        i, j = np.triu_indices(n, k=1)
        seen = shapely.covers(test, _segments(xy[i], xy[j]))
        i, j = i[seen], j[seen]
        w = np.hypot(*(xy[i] - xy[j]).T)
        g = csr_matrix((np.concatenate([w, w]), (np.concatenate([i, j]), np.concatenate([j, i]))), shape=(n, n))
        dist = shortest_path(g, method="D", directed=False)
    return Water(region, test, xy, dist)


def _into(w: Water, x: float, y: float) -> tuple[float, float, float]:
    """The point itself if it is in the water, else the nearest point of the water; and the leg to it."""
    p = shapely.Point(x, y)
    if shapely.covers(w.test, p):
        return x, y, 0.0
    q = nearest_points(w.region, p)[0]
    return q.x, q.y, math.hypot(x - q.x, y - q.y)


def water_distance(w: Water, ax: float, ay: float, bx: float, by: float) -> float:
    """Metres from a to b through the water. The straight line where it stays in the water; inf when
    the two are in parts of the water that do not meet."""
    ax, ay, da = _into(w, ax, ay)
    bx, by, db = _into(w, bx, by)
    if shapely.covers(w.test, shapely.LineString([(ax, ay), (bx, by)])):
        return da + math.hypot(ax - bx, ay - by) + db
    if not len(w.xy):
        return math.inf
    a, b = np.array([ax, ay]), np.array([bx, by])
    n = len(w.xy)
    va = shapely.covers(w.test, _segments(np.repeat(a[None], n, axis=0), w.xy))
    vb = shapely.covers(w.test, _segments(np.repeat(b[None], n, axis=0), w.xy))
    if not va.any() or not vb.any():
        return math.inf
    la = np.hypot(*(w.xy[va] - a).T)
    lb = np.hypot(*(w.xy[vb] - b).T)
    best = (la[:, None] + w.dist[np.ix_(va, vb)] + lb[None, :]).min()
    return da + float(best) + db
