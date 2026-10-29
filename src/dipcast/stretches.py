"""A paddle down a river from one listed spot to another: the route between them and the monitored overflows on it.

For an outing's finish (Swim Together S4, docs/SWIM-TOGETHER-2026-10.md): a paddler who starts at one listed river spot
and gets out at another downstream sees both spots' levels, and what drains into the water between. Neither level is
one for the water between, and the page says so. The build gives each river spot `downstream` in the lite file (the
listed river spots it can paddle to, with the distance) and `stretches` in data/spot/<id>.json (build_site.DETAIL_FIELDS),
one a finish, each overflow in one of three groups:

- `route`: on the route itself. The route is the way down OS Open Rivers' links from the start's place on the network
  to the finish's (RiverNetwork, the links as the forecast mends them, never along a canal: spot_links._out), the
  shortest where a river splits. An overflow is on it when its link is on it, or it is on the start's link below the
  start or on the finish's link above the finish. The route is never longer than MAX_KM, under the forecast's 60 km,
  so every monitored overflow the forecast places on it is listed.
- `side`: on a stream that joins the route between the two, or on a branch of a split river beside it: counted by the
  finish's forecast and not by the start's, and not on the route. Each with where its water first meets the route,
  as km below the start. Only those the finish's forecast counts, within 60 km of the finish by water: a long side
  river has more further up.
- `above`: how many the start's forecast counts that the finish's counts too. They are in both levels.

A pair is left out, rather than guessed, where either spot is not placed on a river link, where its pin was moved
to a main channel (PinLocation.adopted_main_channel), where the route crosses a lake, or where no route down joins them
within MAX_KM. Overflows are the monitored storm overflows the forecast knows; unmonitored outfalls, farm and road
runoff are in no group, and the page says so.
"""

from __future__ import annotations

import heapq
import logging

from dipcast.model.transport import locate_pin, spot_hints
from dipcast.spot_links import _out

log = logging.getLogger(__name__)

MAX_KM = 50.0


def _place(net, r):
    """The spot's pin as forecast_point places it, or None where a stretch cannot start or end there."""
    kind_hint, river_hint = spot_hints(r.kind, r.river)
    pin = locate_pin(net, float(r.lon), float(r.lat), kind_hint=kind_hint, river_hint=river_hint, name=r.name)
    if pin.mode != "river" or pin.snap is None or pin.adopted_main_channel:
        return None
    return pin


def _down(net, node: str, cap_m: float) -> tuple[dict[str, float], dict[str, tuple[str, str]]]:
    """The nodes below `node` within cap_m by the shortest way down, with the metres to each and the edge each was
    reached by (for the path back)."""
    dist, prev, heap = {node: 0.0}, {}, [(0.0, node)]
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist.get(n, float("inf")):
            continue
        for m, e in _out(net, n):
            nd = d + float(e["length"])
            if nd <= cap_m and nd < dist.get(m, float("inf")):
                dist[m], prev[m] = nd, (n, e["link"])
                heapq.heappush(heap, (nd, m))
    return dist, prev


def _link_length(net, lid: str) -> float:
    return float(net.repairs.get(lid, 0.0)) if lid.startswith("repair:") else float(net.links.loc[lid, "length"])


def route(net, a, b, max_km: float = MAX_KM) -> dict | None:
    """The route down from pin a to pin b: its metres, its links (`inner`, wholly on it), each node on it with its
    metres below a, and the two end links with the share of each on it. None where there is none within max_km,
    or it crosses a lake."""
    la, fa, lb, fb = a.snap.link_id, a.snap.frac, b.snap.link_id, b.snap.frac
    len_a = _link_length(net, la)
    if la == lb:
        if fb <= fa:
            return None
        metres = (fb - fa) * len_a
        return None if metres > max_km * 1000 else {"m": metres, "inner": set(), "nodes": {}, "a": (la, fa, fb), "b": (lb, fa, fb)}
    a_end = net.link_nodes(la)[1]
    b_start = net.link_nodes(lb)[0]
    head = (1 - fa) * len_a
    dist, prev = _down(net, a_end, max_km * 1000 - head)
    if b_start not in dist:
        return None
    metres = head + dist[b_start] + fb * _link_length(net, lb)
    if metres > max_km * 1000:
        return None
    inner, nodes, n = set(), {b_start: head + dist[b_start]}, b_start
    while n != a_end:
        p, lid = prev[n]
        inner.add(lid)
        nodes[p] = head + dist[p]
        n = p
    if any(not lid.startswith("repair:") and net.links.loc[lid, "form"] == "lake" for lid in inner | {la, lb}):
        return None
    return {"m": metres, "inner": inner, "nodes": nodes, "a": (la, fa, 1.0), "b": (lb, 0.0, fb)}


def on_route(rt: dict, link_id: str, frac: float) -> bool:
    """Whether an overflow at (link_id, frac) is on the route: on a link wholly on it, or on an end link's part on it."""
    if link_id in rt["inner"]:
        return True
    return any(link_id == lid and lo < frac < hi for lid, lo, hi in (rt["a"], rt["b"]))


def km_below_start(net, rt: dict, link_id: str, frac: float) -> float | None:
    """Where an overflow on the route is, as km below the start."""
    la, fa, _ = rt["a"]
    if link_id == la:
        return (frac - fa) * _link_length(net, la) / 1000
    start = net.link_nodes(link_id)[0]
    if start in rt["nodes"]:
        return (rt["nodes"][start] + frac * _link_length(net, link_id)) / 1000
    return None


def joins_at(net, rt: dict, link_id: str, cap_m: float) -> float | None:
    """Where water from an overflow on a link off the route first meets the route, as km below the start; None
    where it does not within cap_m (as on a branch whose water meets the route only at or below the finish)."""
    if not rt["nodes"]:
        return None
    end = net.link_nodes(link_id)[1]
    dist, _ = _down(net, end, cap_m)
    met = [rt["nodes"][n] for n in dist if n in rt["nodes"]]
    return min(met) / 1000 if met else None


def stretches(net, spots, upstream: dict[str, list[dict]], overflows, max_km: float = MAX_KM) -> dict[str, list[dict]]:
    """For each river spot (spots: the build's frame), the listed river spots downstream within max_km, nearest
    first, each { to, km, route: [[site_id, km below the start]], side: [[site_id, km below the start where it
    joins, or None]], above }. upstream: spot id -> every overflow its forecast counts; overflows: the forecast's
    table (site_id, link_id, frac)."""
    rivers = spots[spots["kind"].astype(str).str.lower() == "river"]
    pins = {}
    for r in rivers.itertuples(index=False):
        try:
            p = _place(net, r)
        except Exception as e:  # noqa: BLE001 - a finish must never sink the site
            log.warning("%s: not placed for a finish (%s)", r.name, e)
            p = None
        if p is not None and upstream.get(r.id) is not None:
            pins[r.id] = p
    where = {o.site_id: (o.link_id, float(o.frac)) for o in overflows.itertuples(index=False)
             if isinstance(o.link_id, str) and o.frac == o.frac}
    counted = {sid: {o["site_id"] for o in rows if o.get("site_id")} for sid, rows in upstream.items()}
    out: dict[str, list[dict]] = {}
    for a, pa in pins.items():
        found = []
        for b, pb in pins.items():
            if b == a:
                continue
            rt = route(net, pa, pb, max_km)
            if rt is None:
                continue
            on = sorted(((s, km_below_start(net, rt, *where[s])) for s in where if on_route(rt, *where[s])),
                        key=lambda x: (x[1] is None, x[1], x[0]))
            on_ids = {s for s, _ in on}
            off = counted[b] - counted[a] - on_ids
            side = sorted(([s, None if s not in where else joins_at(net, rt, where[s][0], 60_000.0)] for s in off),
                          key=lambda x: (x[1] is None, x[1] if x[1] is not None else 0, x[0]))
            found.append({"to": b, "km": round(rt["m"] / 1000, 1),
                          "route": [[s, None if k is None else round(k, 1)] for s, k in on],
                          "side": [[s, None if k is None else round(k, 1)] for s, k in side],
                          "above": len(counted[a] & counted[b])})
        if found:
            out[a] = sorted(found, key=lambda x: (x["km"], x["to"]))
    return out


def attach(results: list[dict], spots, upstream: dict[str, list[dict]], net, overflows) -> int:
    """Each river spot's `downstream` ([[id, km]]) and `stretches` (module doc) into its result. Returns how many
    spots have a finish to offer."""
    found = stretches(net, spots, upstream, overflows)
    for s in results:
        st = found.get(s["id"])
        if st:
            s["downstream"] = [[x["to"], x["km"]] for x in st]
            s["stretches"] = st
    return len(found)
