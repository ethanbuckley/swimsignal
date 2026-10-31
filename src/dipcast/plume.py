"""Where water from a spill may be: the spill map on a spot's page (docs/PLUME-MAP-2026-10.md).

For each overflow with a spill in the catchment replay's 48 hours (src/dipcast/replay.py), the river route
its water takes down to the spot: the links the forecast traced (transport.upstream_edges), from the
overflow's place on its link down to the pin. The page (site/plume.js) moves each spill's water along that
route at the overflow's own modelled travel time (`travel_h`, the forecast's), so a spill's water reaches
the end of its route when the forecast and the replay say it reaches the spot. Nothing new is modelled
here: the spills are the replay's, the travel times the forecast's, and the die-off its T90.

What is not drawn is listed instead, never left blank: an overflow with no current reading or no live
feed is a marker of its own, and a route through a lake has no path (the replay gives it no travel time,
as a river speed or a residence assumption there is too coarse to draw as times).

No requests: this reads the river network, the overflow table, this build's results and the replay files
already written."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd
from shapely.geometry import LineString
from shapely.ops import substring

from dipcast import config
from dipcast.network.rivers import _TO_WGS
from dipcast.trace import SIMPLIFY_M, encode

log = logging.getLogger(__name__)

PLUME_MAX_BYTES = 40_000   # announced (build_site.plume_files) when a file is over it
SPOT_ID = re.compile(r"[A-Za-z0-9_-]+")
MIN_WEIGHT = 0.005         # replay.MIN_WEIGHT, transport.COUNT_WEIGHT: under it the overflow is not counted here
GAP_STATES = ("stale", "offline", "no_feed")   # replay.STATES other than "live": drawn as not known


def route_xy(net, pin, link_id: str, frac: float, max_km: float = config.MAX_UPSTREAM_KM) -> list[tuple[float, float]] | None:
    """The route (EPSG:27700 points) water takes from `frac` along `link_id` down to a river pin: the rest
    of the overflow's link, then at each node the way out with the least distance left to the pin's trace
    node (upstream_edges' distances, so the route the forecast measured), then the pin's own link down to
    the pin. A gap repair has no geometry and is crossed in a straight line. None when the link is not
    upstream of the pin within max_km, or the pin is not on a river."""
    if pin.mode != "river" or pin.trace_node is None or pin.snap is None:
        return None
    geom, g = net.links.geometry, net.graph
    if link_id == pin.snap.link_id:   # on the pin's own link, above the pin
        if frac >= pin.snap.frac:
            return None
        return list(substring(geom.loc[link_id], frac, pin.snap.frac, normalized=True).coords)
    dist = net.upstream_edges(pin.trace_node, max_km * 1000.0)
    if link_id not in dist:
        return None
    pts = list(substring(geom.loc[link_id], frac, 1.0, normalized=True).coords)
    node, seen = net.link_nodes(link_id)[1], {link_id}
    while node != pin.trace_node:
        ways = [(dist[e["link"]] + e["length"], e["link"], s) for s, e in ((s, g.edges[node, s]) for s in g.successors(node))
                if e["link"] in dist and e["link"] not in seen]
        if not ways:
            return None
        _, lid, node = min(ways)
        seen.add(lid)
        if not lid.startswith("repair:") and lid in geom.index:
            pts += list(geom.loc[lid].coords)[1:]
    pts += list(substring(geom.loc[pin.snap.link_id], 0.0, pin.snap.frac, normalized=True).coords)[1:]
    return pts


def encode_route(xy: list[tuple[float, float]], tolerance_m: float = SIMPLIFY_M) -> tuple[str, float] | None:
    """A route as an encoded polyline (trace.encode, [lat, lon] at five places) and its length in km,
    measured before simplifying. None for a route shorter than two points."""
    if not xy or len(xy) < 2:
        return None
    line = LineString(xy)
    simple = list(line.simplify(tolerance_m).coords)
    lon, lat = _TO_WGS.transform([p[0] for p in simple], [p[1] for p in simple])
    return encode(zip(lat, lon, strict=True)), round(line.length / 1000.0, 2)


def _place(overflows: pd.DataFrame, site_id, lat, lon) -> tuple[str, float] | None:
    """The overflow's link and place along it in the overflow table: the row with its id nearest its
    reported position, where an id is listed twice."""
    rows = overflows[overflows["site_id"] == site_id]
    rows = rows[rows["link_id"].notna()]
    if rows.empty:
        return None
    if len(rows) > 1 and lat is not None and lon is not None:
        rows = rows.assign(_d=(rows["lat"] - float(lat)) ** 2 + (rows["lon"] - float(lon)) ** 2).sort_values("_d")
    r = rows.iloc[0]
    return str(r["link_id"]), float(r["frac"])


def _pos(c: dict) -> list[float] | None:
    lat, lon = c.get("lat"), c.get("lon")
    return None if lat is None or lon is None else [round(float(lat), 5), round(float(lon), 5)]


def spot_plume(net, pin, spot: dict, upstream: list[dict], replay_doc: dict, overflows: pd.DataFrame,
               generated: pd.Timestamp) -> dict:
    """The spill map's file for one spot: where each overflow the replay lists sits, the route of each
    whose water has a travel time (`path`, encoded, and `km`), and every counted overflow with no current
    reading as a marker of its own. The spills and their times stay in the replay file, which the page
    reads beside this one."""
    by_id = {c.get("site_id"): c for c in upstream}
    rows, unrouted = [], 0
    for r in replay_doc.get("overflows") or []:
        sid = r.get("site_id")
        c = by_id.get(sid, {})
        row = {"site_id": sid, "at": _pos(c)}
        if r.get("travel_h") is not None and not r.get("lake_route"):
            place = _place(overflows, sid, c.get("lat"), c.get("lon"))
            route = encode_route(route_xy(net, pin, *place)) if place else None
            if route:
                row["path"], row["km"] = route
            else:
                unrouted += 1
        rows.append(row)
    listed = {r["site_id"] for r in rows}
    gaps = [{"site_id": c.get("site_id"), "at": _pos(c), "state": c.get("data_state")} for c in upstream
            if (c.get("weight") or 0) >= MIN_WEIGHT and c.get("data_state") in GAP_STATES and c.get("site_id") not in listed
            and _pos(c) is not None]
    snapped = (spot.get("location") or {}).get("snapped")
    return {"id": spot.get("id"), "generated_at": generated.isoformat(),
            "pin": [snapped["lat"], snapped["lon"]] if snapped else [round(float(spot["lat"]), 5), round(float(spot["lon"]), 5)],
            "river_velocity_ms": ((spot.get("assumptions") or {}).get("river_velocity_ms")),
            "t90_hours": config.T90_HOURS, "recent_spill_hours": config.RECENT_SPILL_HOURS,
            "overflows": rows, "unrouted": unrouted, "gaps": gaps}


def write_plumes(site: Path, results: list[dict], upstream: dict[str, list[dict]], generated: pd.Timestamp,
                 net=None, overflows: pd.DataFrame | None = None) -> dict:
    """data/spot/<id>-plume.json for each river spot with a replay file (replay.write_replays, which this
    runs after). Returns counts and the largest file's size for the build log."""
    from dipcast.model.transport import locate_pin, spot_hints
    if net is None or overflows is None:
        from dipcast.model.forecast import _net, _overflows
        net, overflows = net or _net(), overflows if overflows is not None else _overflows()
    out = site / "data" / "spot"
    n, largest, failed = 0, (None, 0), []
    for r in results:
        sid = str(r.get("id"))
        src = out / f"{sid}-replay.json"
        if r.get("error") or not SPOT_ID.fullmatch(sid) or not src.exists():
            continue
        try:
            kind, river = spot_hints(r.get("kind"), r.get("river"))
            pin = locate_pin(net, float(r["lon"]), float(r["lat"]), kind_hint=kind, river_hint=river, name=r.get("name"))
            if pin.mode != "river":   # a lake: the replay gives no travel times there, so nothing moves
                continue
            doc =spot_plume(net, pin, r, upstream.get(sid, []), json.loads(src.read_text()), overflows, generated)
        except Exception as e:  # noqa: BLE001 - one spot's map must not sink the rest
            log.warning("%s: no spill map (%s)", sid, e)
            failed.append(sid)
            continue
        body = json.dumps(doc, separators=(",", ":"), default=str)
        (out / f"{sid}-plume.json").write_text(body)
        n += 1
        if len(body) > largest[1]:
            largest = (sid, len(body))
    res = {"written": n, "largest": largest[0], "largest_bytes": largest[1], "failed": len(failed)}
    if largest[1] > PLUME_MAX_BYTES:
        res["warning"] = f"{largest[0]}'s spill map is {largest[1] / 1e3:.0f} kB, over {PLUME_MAX_BYTES / 1e3:.0f} kB"
    return res
