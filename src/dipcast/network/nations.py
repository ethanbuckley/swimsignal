"""How much of the river network the trace walks above a spot lies in Wales.

Dŵr Cymru Welsh Water's overflows in Wales are not in SwimSignal's data: its live layer has no reuse
licence yet (config.DWR_CYMRU, docs/WALES-PLAN-2026-10.md), and the Environment Agency's returns cover
its overflows in England only. So at a spot on the Dee, the Wye or the Severn below the border, the
trace walks up into Wales and finds no overflow there, which reads as none. The spot's page says
plainly that overflows in Wales are not counted, and how much of the river it traced lies in Wales.

The share is by length: the links the trace walks (net.upstream_edges, within the forecast's
max_upstream_km, as transport.upstream_overflows walks them), cut by the Wales outline. The outline is
data/raw/outside_england.json (scripts/make_outside_england.py): Wales and Scotland widened past mean
high water and less every point nearer England, so a shared estuary is split down the middle. Its
Welsh polygons are those south of WALES_NORTH_LAT; Scotland's are all far north of it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union

from dipcast import config

OUTLINE = config.RAW / "outside_england.json"
WALES_NORTH_LAT = 54.0   # Wales reaches 53.43 N at Point of Ayr; Scotland's southernmost point is 54.63 N
MIN_SHARE = 0.005        # less than this rounds to 0% and is not said


@lru_cache(maxsize=2)
def wales_outline(path: Path = OUTLINE):
    """Wales, from the outline's "wales_scotland" polygons south of WALES_NORTH_LAT, in British National
    Grid metres, prepared for fast tests."""
    doc = json.loads(Path(path).read_text())
    polys = list(shape(doc["geometry"]).geoms)
    if len(polys) != len(doc["parts"]):
        raise ValueError("outside_england.json: geometry and parts disagree")
    welsh = [p for p, part in zip(polys, doc["parts"], strict=True)
             if part == "wales_scotland" and p.centroid.y < WALES_NORTH_LAT]
    if not welsh:
        raise ValueError("outside_england.json has no Welsh polygon")
    to_bng = Transformer.from_crs(4326, 27700, always_xy=True).transform
    wales = transform(to_bng, unary_union(welsh))
    shapely.prepare(wales)
    return wales


def wales_share(net, link_ids, wales=None) -> float:
    """The share, 0 to 1, of the length of these links (river network link ids; "repair:" joins, which
    have no line, are left out) that lies in Wales."""
    ids = [lid for lid in link_ids if not str(lid).startswith("repair:") and lid in net.links.index]
    if not ids:
        return 0.0
    wales = wales_outline() if wales is None else wales
    lines = net.links.loc[ids, "geometry"].values
    total = float(np.sum(shapely.length(lines)))
    if total <= 0:
        return 0.0
    inside = shapely.intersects(wales, lines)
    if not inside.any():
        return 0.0
    welsh = float(np.sum(shapely.length(shapely.intersection(lines[inside], wales))))
    return min(1.0, welsh / total)


def traced_wales_share(net, trace_node: str | None, max_km: float, wales=None) -> float | None:
    """wales_share of the network the trace walks above a spot's trace node, rounded to 0.01; None where
    there is nothing to walk (no trace node) and 0.0 where none of it is in Wales."""
    if trace_node is None:
        return None
    share = wales_share(net, net.upstream_edges(trace_node, max_km * 1000.0), wales)
    return round(share, 2) if share >= MIN_SHARE else 0.0
