"""How the listed spots are joined by water, for the spot page's "Nearby" card (outside review, 20 Oct 2026).

The reviewer found that around Oxford the card offers other places on the Thames, which can share
pollution sources: River Thames, Long Bridges, at moderate risk, offered "Lower risk nearby: River Thames,
Hurley, 23 miles away", downstream on the same river, with nothing to say so. They asked for each
suggestion's reason in words, and that a different catchment get no reassuring label. The build gives
each spot two fields in spots.json:

- `catchment`: a short id of where its water reaches tidal water, or the end of the network (catchment_end).
  Spots with different ids drain apart: water from one never reaches the other above an estuary. The
  Wharfe meets the Ouse below the Ouse's tidal limit at Naburn, so it is not in the Nidd's catchment.
  The lite file the page loads keeps it, since the card compares every candidate's.
- `linked`: the other listed spots its water reaches or comes from, each with a code. "s": at least one
  monitored overflow counts at both, from the forecast's full upstream sets (transport.upstream_overflows,
  every overflow within 60 km of river, not the ten a spot keeps). "d" downstream of it and "u" upstream,
  joined by the river with no overflow counted at both: further apart along the river than the forecast
  traces (Hurley is 87 km of river below Long Bridges), or with no overflow above the higher one. Only
  the spot's own page reads it, so it goes in data/spot/<id>.json (build_site.DETAIL_FIELDS): in the
  lite file it was 1.6 kB gzipped on the data of 20 Oct 2026, the catchment 0.55 kB.

A spot with no place on the network (an isolated lake) has neither field, and the page says nothing of its
catchment. Down the river means down OS Open Rivers' links in the direction of flow, as the forecast's
network mends them (RiverNetwork), but never along a canal: OS draws some canals flowing out of a river,
and one would carry the walk into another river's catchment.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator

from dipcast.model.transport import locate_pin, spot_hints

log = logging.getLogger(__name__)


def _out(net, n: str) -> Iterator[tuple[str, dict]]:
    """The links out of node n that water follows: every one but a canal."""
    g = net.graph
    for m in g.successors(n):
        e = g.edges[n, m]
        if e.get("form") != "canal":
            yield m, e


def downstream_of(net, node: str) -> set[str]:
    """Every node below `node` (itself included), down to the sea or the end of the network."""
    seen, stack = {node}, [node]
    while stack:
        for m, _ in _out(net, stack.pop()):
            if m not in seen:
                seen.add(m)
                stack.append(m)
    return seen


def catchment_end(net, node: str) -> str:
    """Where the water from `node` reaches tidal water: the start of the first tidal link on its way down,
    or the end of the network where it meets none. Where the river splits and the branches end apart, the
    end with the most network upstream, the main river's; a tie goes to the lowest id, so one network
    always gives one answer. A node on tidal water already is its own end."""
    up = net.upstream_m
    ends, seen, stack = set(), {node}, [node]
    while stack:
        n = stack.pop()
        nxt = list(_out(net, n))
        if not nxt or any(e.get("form") == "tidalRiver" for _, e in nxt):
            ends.add(n)
            continue
        for m, _ in nxt:
            if m not in seen:
                seen.add(m)
                stack.append(m)
    return min(ends, key=lambda n: (-up.get(n, 0.0), n))


def short_id(node: str) -> str:
    """Eight hex characters for a node id: the page only compares them, and OS's ids are 36 characters."""
    return hashlib.sha1(node.encode()).hexdigest()[:8]


def shared_overflows(upstream: dict[str, list[dict]]) -> dict[str, set[str]]:
    """For each spot, the other spots with at least one of the same monitored overflows upstream (site_id)."""
    by_overflow: dict[str, set[str]] = {}
    for sid, rows in upstream.items():
        for o in rows:
            if o.get("site_id"):
                by_overflow.setdefault(o["site_id"], set()).add(sid)
    out: dict[str, set[str]] = {sid: set() for sid in upstream}
    for spots in by_overflow.values():
        for sid in spots:
            out[sid] |= spots - {sid}
    return out


def spot_links(net, places: dict[str, tuple[str, float] | None], upstream: dict[str, list[dict]]) -> dict[str, dict]:
    """Each placed spot's `catchment` and `linked` (module doc). `places`: spot id -> (the node its forecast
    traces up from, the metres from that node down to the spot), or None. `upstream`: spot id -> every
    overflow its forecast counts. Two spots on one stretch of river (one node) are joined by the metres
    down it; two at one lake (one node, its outlet, and no metres) by their shared overflows alone."""
    shares = shared_overflows(upstream)
    placed = {sid: p for sid, p in places.items() if p and p[0] in net.graph}
    down = {sid: downstream_of(net, node) for sid, (node, _) in placed.items()}
    out: dict[str, dict] = {}
    for a, (na, oa) in placed.items():
        linked: dict[str, str] = {}
        for b, (nb, ob) in placed.items():
            if b == a:
                continue
            if b in shares.get(a, ()):
                linked[b] = "s"
            elif na == nb:
                if ob != oa:
                    linked[b] = "d" if ob > oa else "u"
            elif nb in down[a]:
                linked[b] = "d"
            elif na in down[b]:
                linked[b] = "u"
        out[a] = {"catchment": short_id(catchment_end(net, na)), "linked": dict(sorted(linked.items()))}
    return out


def spot_place(net, lat: float, lon: float, kind=None, river=None, name: str | None = None) -> tuple[str, float] | None:
    """Where a listed spot's forecast traces up from, placed as forecast_point places it (the same hints
    from spots.csv, as trace.spot_trace): the node and the metres down to the spot. None off the network."""
    kind_hint, river_hint = spot_hints(kind, river)
    pin = locate_pin(net, lon, lat, kind_hint=kind_hint, river_hint=river_hint, name=name)
    return (pin.trace_node, float(pin.trace_offset_m)) if pin.mode in ("river", "lake") and pin.trace_node else None


def attach(results: list[dict], spots, upstream: dict[str, list[dict]], net) -> int:
    """Each spot's `catchment` and `linked` (module doc) into its result, from the spot list (`spots`, the
    build's frame) and every overflow each forecast counted (`upstream`). A spot that cannot be placed is
    left without them; the card then gives no reason for it. Returns how many spots have them."""
    places = {}
    for r in spots.itertuples(index=False):
        try:
            places[r.id] = spot_place(net, float(r.lat), float(r.lon), r.kind, r.river, r.name)
        except Exception as e:  # noqa: BLE001 - a reason beside a suggestion must never sink the site
            log.warning("%s: not placed for the Nearby card's reasons (%s)", r.name, e)
    links = spot_links(net, places, upstream)
    for s in results:
        s.update(links.get(s["id"], {}))
    return sum(1 for s in results if "catchment" in s)
