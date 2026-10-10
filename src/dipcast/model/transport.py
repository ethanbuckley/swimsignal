"""From 'that overflow spilled' to 'it reaches this swim spot'.

Three physical effects, each a multiplicative weight in [0, 1]:

* travel time     t = d_river / v_river + d_lake / v_lake
* die-off         10 ** (-t / T90)   first-order decay of faecal indicator
                  bacteria; T90 is the time for a 90% reduction
* dilution        (L_up(overflow) + L0) / (L_up(spot) + L0), capped at 1, where
                  L_up is the total upstream network length, a proxy for
                  catchment area and hence flow. L0 keeps tiny tributaries
                  from vanishing.

Their product is treated as the probability that a spill at that overflow, if
it happens, meaningfully affects water quality at the spot. Risk is then
1 - prod(1 - p_i * w_i) over upstream overflows: the chance at least one spill
reaches the swimmer.

Two options, off by default (config.VELOCITY_MODE, config.DILUTION_MODE), follow
Dr James Shucksmith's review of 9 Oct 2026:

* velocity "catchment"  each reach moves at its own speed, a power law in its
                        catchment area (reach_velocity). The catchment area is
                        estimated from the upstream network length (catchment_km2).
                        Travel time is the sum of length / speed along the path.
* dilution "flow"       Q_SPILL / (Q_SPILL + Q50 at the spot): a spill of fixed
                        size mixed into the spot's median flow, estimated from its
                        catchment area (q50_m3s). Every overflow upstream of a spot
                        gets the same dilution; where it joins no longer matters.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd
from shapely.geometry import Point

from dipcast import config
from dipcast.ingest.lakes import load_lakes
from dipcast.network.names import river_words
from dipcast.network.rivers import RiverNetwork, Snap, lonlat_to_bng

log = logging.getLogger(__name__)

L0_M = 5_000.0          # dilution smoothing length
LAKE_SNAP_M = 1_500.0   # fallback: a pin this close to a lake centreline is 'in the lake'
LAKE_SHORE_M = 150.0    # a click this close to a WFD lake polygon counts as in that lake
LAKE_A0_KM2 = 5.0       # lake area at which the lake dilution factor halves the weight
LOW_CONFIDENCE_FACTOR = 0.7   # outfalls snapped by proximity alone (750-1500 m, no name match)


@lru_cache(maxsize=1)
def _lakes():
    try:
        return load_lakes()
    except Exception as e:  # noqa: BLE001 - polygons are an enhancement; the centreline heuristic still works
        log.warning("lake polygons unavailable: %s", e)
        return None


@dataclass
class PinLocation:
    mode: str                          # 'river' | 'lake' | 'none'
    x: float
    y: float
    snap: Snap | None
    lake_links: set[str] = field(default_factory=set)
    outlet_node: str | None = None
    trace_node: str | None = None      # node from which upstream tracing starts
    trace_offset_m: float = 0.0        # distance from trace_node down to the pin (river mode)
    watercourse: str | None = None
    lake_area_km2: float | None = None
    lake_source: str | None = None     # 'polygon' (WFD) or 'centreline' (OS Open Rivers only)
    adopted_main_channel: bool = False # pin was on a side channel; traced the main river instead
    placement: str | None = None       # with a river hint: 'on river' (nearest link is that river),
                                       # 'moved to river' (a nearer link of another name was passed over),
                                       # 'river not found' (none within HINT_SNAP_M; nearest kept)


PIN_SNAP_M = 1_500.0    # users click imprecisely; allow a wider search than for outfalls
LAKE_BIAS = 0.5         # lake centrelines sit further from the shore than inflow becks do
ADOPT_RADIUS_M = 500.0  # side channels: look this far for the main channel
ADOPT_MIN_M = 5_000.0   # ...when the snapped link has less than this much network upstream
ADOPT_RATIO = 5.0       # ...and the alternative has at least this many times more
HINT_SNAP_M = 1_000.0   # a spot's named river this close beats a nearer link of another name
RIVER_FORMS = ("inlandRiver", "tidalRiver")


def _names_match(cand: pd.DataFrame, want: frozenset[str]) -> pd.Series:
    """Which candidate links carry the wanted river's name, as their name or OS's alternative
    (Welsh links often have the English name there)."""
    def matches(col: pd.Series) -> pd.Series:
        # .astype(bool): on an empty frame pandas 3 keeps the str dtype through .map, and
        # OR-ing two empty str Series raises (Shilley Pool, no link within HINT_SNAP_M, 3 Oct 2026).
        return col.map(lambda n: bool(river_words(n) & want) if isinstance(n, str) else False).astype(bool)
    alt = cand.get("watercourse_name_alternative", pd.Series(None, index=cand.index, dtype=object))
    return matches(cand["watercourse_name"]) | matches(alt)


def _adopt_main_channel(net: RiverNetwork, x: float, y: float, river: Snap,
                        want: frozenset[str] | None = None) -> tuple[Snap, bool]:
    """A pin on a mill stream, leat or braided side channel is in main-channel
    water, but OS Open Rivers often leaves such channels disconnected upstream.
    If the snapped link has a tiny upstream network and a nearby river link has a
    much larger one, snap to that link instead. With `want` (a river's words), only
    links carrying that name are considered."""
    own = net.link_upstream_m(river.link_id)
    if own >= ADOPT_MIN_M:
        return river, False
    cand = net.candidates_xy(x, y, ADOPT_RADIUS_M)
    cand = cand[cand["form"].isin(RIVER_FORMS) & (cand.index != river.link_id)]
    if want:
        cand = cand[_names_match(cand, want)]
    if cand.empty:
        return river, False
    ups = cand["start_node"].map(net.upstream_m).fillna(0.0)
    best = ups.idxmax()
    if ups[best] < max(ADOPT_MIN_M, ADOPT_RATIO * own):
        return river, False
    row = cand.loc[best]
    pt = Point(x, y)
    frac = float(row.geometry.project(pt, normalized=True))
    sp = row.geometry.interpolate(frac, normalized=True)
    log.info("adopted main channel %s (%.0f km upstream) over side channel (%.1f km)",
             row["watercourse_name"], ups[best] / 1000, own / 1000)
    return Snap(link_id=best, frac=frac, dist_m=float(row["dist_m"]), form=row["form"], x=sp.x, y=sp.y), True


def _lake_polygon_at(x: float, y: float):
    lakes = _lakes()
    if lakes is None or lakes.empty:
        return None
    pt = Point(x, y)
    idx = lakes.sindex.query(pt.buffer(LAKE_SHORE_M), predicate="intersects")
    if len(idx) == 0:
        return None
    cand = lakes.iloc[idx]
    return cand.loc[cand.geometry.distance(pt).idxmin()]


def _snap_to_links(net: RiverNetwork, x: float, y: float, link_ids: set[str]) -> Snap | None:
    if not link_ids:
        return None
    pt = Point(x, y)
    sub = net.links.loc[list(link_ids)]
    d = sub.geometry.distance(pt)
    lid = d.idxmin()
    geom = sub.loc[lid, "geometry"]
    frac = float(geom.project(pt, normalized=True))
    sp = geom.interpolate(frac, normalized=True)
    return Snap(link_id=lid, frac=frac, dist_m=float(d.min()), form=sub.loc[lid, "form"], x=sp.x, y=sp.y)


def locate_pin(net: RiverNetwork, lon: float, lat: float, kind_hint: str | None = None,
               river_hint: str | None = None) -> PinLocation:
    """`kind_hint` = 'lake' says the caller knows this is a lake (e.g. a designated
    lake bathing water or a curated spot). A lake with no WFD polygon and no lake
    centreline nearby is then treated as isolated rather than snapped to whatever
    river passes closest, which would credit it with that river's overflows.

    `river_hint` is the river the spot is on (spots.csv's `river` column). The pin
    goes to the nearest link carrying that name (or OS's alternative name, so
    "River Wye" finds "Afon Gwy") within HINT_SNAP_M, even when a link of another
    name is nearer: Crook o' Lune sat 262 m from Escow Beck and 672 m from the Lune
    and was traced up the beck, finding no overflows (2 Oct 2026). With no such link
    the nearest is kept, with a warning. Ignored for lakes."""
    x, y = lonlat_to_bng(lon, lat)
    pin = _locate(net, x, y, kind_hint)
    if river_hint and kind_hint != "lake":
        pin = _apply_river_hint(net, pin, river_hint)
    return pin


def _apply_river_hint(net: RiverNetwork, pin: PinLocation, hint: str) -> PinLocation:
    want = river_words(hint)
    shown = river_words(hint, welsh=False)   # the name is shown as spots.csv spells it, Welsh or English
    if not want:
        return pin
    if pin.mode == "river" and pin.snap is not None:
        own = net.links.loc[[pin.snap.link_id]]
        if bool(_names_match(own, want).iloc[0]):   # the link itself, not a name borrowed from downstream
            pin.watercourse = _link_name(net, pin.snap.link_id, prefer=shown)
            pin.placement = "on river"
            return pin
    cand = net.candidates_xy(pin.x, pin.y, HINT_SNAP_M)
    cand = cand[cand["form"].isin(RIVER_FORMS)]
    cand = cand[_names_match(cand, want)]
    if cand.empty:
        log.warning("no link named like %r within %.0f m of (%.0f, %.0f); kept the nearest, %s",
                    hint, HINT_SNAP_M, pin.x, pin.y, pin.watercourse)
        pin.placement = "river not found"
        return pin
    snap = _snap_to_links(net, pin.x, pin.y, {cand.index[0]})
    snap, adopted = _adopt_main_channel(net, pin.x, pin.y, snap, want=want)
    log.info("placed on %s %.0f m away rather than %s", hint, snap.dist_m, pin.watercourse)
    start, _ = net.link_nodes(snap.link_id)
    return PinLocation("river", pin.x, pin.y, snap, trace_node=start,
                       trace_offset_m=snap.frac * net.links.loc[snap.link_id, "length"],
                       watercourse=_link_name(net, snap.link_id, prefer=shown), adopted_main_channel=adopted,
                       placement="moved to river")


def _locate(net: RiverNetwork, x: float, y: float, kind_hint: str | None) -> PinLocation:
    # 1. Inside (or on the shore of) a WFD lake polygon: the lake's centreline
    #    links are the ones intersecting the polygon.
    poly = _lake_polygon_at(x, y)
    if poly is not None:
        idx = net.links.sindex.query(poly.geometry, predicate="intersects")
        cand = net.links.iloc[idx]
        lake_links = set(cand.index[cand["form"] == "lake"])
        if not lake_links:
            near = net.snap_xy(x, y, max_m=LAKE_SNAP_M, forms=("lake",))
            if near is not None:
                lake_links = net.lake_component(near.link_id)
        if lake_links:
            outlet = _lake_outlet(net, lake_links)
            name = poly.get("lake_name")
            return PinLocation("lake", x, y, _snap_to_links(net, x, y, lake_links), lake_links, outlet,
                               trace_node=outlet, watercourse=str(name) if isinstance(name, str) else None,
                               lake_area_km2=float(poly["area_km2"]), lake_source="polygon")

    # 2. Otherwise decide between river and (small, unmapped) lake by centreline distance.
    river = net.snap_xy(x, y, max_m=PIN_SNAP_M)
    lake = net.snap_xy(x, y, max_m=LAKE_SNAP_M, forms=("lake",))
    if kind_hint == "lake":
        if lake is None:
            return PinLocation("isolated", x, y, None, watercourse=None, lake_source="none")
        use_lake = True
    else:
        use_lake = lake is not None and (
            river is None or river.form == "lake" or lake.dist_m * LAKE_BIAS < river.dist_m
        )
    if use_lake:
        comp = net.lake_component(lake.link_id)
        outlet = _lake_outlet(net, comp)
        own = net.links.loc[lake.link_id, "watercourse_name"]  # do not borrow the outflow river's name
        return PinLocation("lake", x, y, lake, comp, outlet, trace_node=outlet,
                           watercourse=str(own) if isinstance(own, str) and own else None, lake_source="centreline")
    if river is None:
        return PinLocation("none", x, y, None)
    river, adopted = _adopt_main_channel(net, x, y, river)
    start, _ = net.link_nodes(river.link_id)
    return PinLocation("river", x, y, river, trace_node=start,
                       trace_offset_m=river.frac * net.links.loc[river.link_id, "length"],
                       watercourse=_link_name(net, river.link_id), adopted_main_channel=adopted)


def _link_name(net: RiverNetwork, link_id: str, max_steps: int = 12,
               prefer: frozenset[str] | None = None) -> str | None:
    """Name of the link, else the first named link downstream (the river it feeds).
    With `prefer` (a river's words), OS's alternative name is given when it is the one
    spelt that way: "River Wye" rather than "Afon Gwy" for a spot said to be on the River Wye."""
    lid = link_id
    for _ in range(max_steps):
        if lid not in net.links.index:
            return None
        name = net.links.loc[lid, "watercourse_name"]
        if isinstance(name, str) and name:
            alt = net.links.loc[lid].get("watercourse_name_alternative")
            if (prefer and isinstance(alt, str) and alt and river_words(alt, welsh=False) & prefer
                    and not river_words(name, welsh=False) & prefer):
                return alt
            return name
        end = net.links.loc[lid, "end_node"]
        succ = list(net.graph.successors(end))
        if not succ:
            return None
        lid = net.graph.edges[end, succ[0]]["link"]
    return None


def _lake_outlet(net: RiverNetwork, comp: set[str]) -> str:
    """Node where water leaves the lake: an out-edge to a non-lake link, else a sink."""
    g = net.graph
    nodes = set()
    for lid in comp:
        s, e = net.link_nodes(lid)
        nodes.update((s, e))
    candidates = []
    for n in nodes:
        outs = [g.edges[n, m]["link"] for m in g.successors(n)]
        if not outs or any(l not in comp for l in outs):
            candidates.append(n)
    if not candidates:
        candidates = list(nodes)
    # Prefer the candidate with the most upstream network (the main outlet).
    return max(candidates, key=lambda n: net.upstream_length(n, max_length_m=200_000))


def upstream_lengths(net: RiverNetwork, root: str, cap_m: float) -> tuple[dict[str, float], dict[str, float]]:
    """(link -> distance from link's downstream end to root, node -> exact upstream
    network length within the cap) for the subgraph upstream of `root`.
    Exact means the total length of the *set* of links upstream, so braided
    channels that split and rejoin are not counted twice."""
    link_dist = net.upstream_edges(root, cap_m)
    nodes = {root}
    for lid in link_dist:
        if lid.startswith("repair:"):
            continue
        s_, e_ = net.link_nodes(lid)
        nodes.update((s_, e_))
    length_of = {lid: (net.repairs.get(lid, 0.0) if lid.startswith("repair:") else net.links.loc[lid, "length"])
                 for lid in link_dist}
    g = net.graph
    memo: dict[str, float] = {}

    def total(n: str) -> float:
        if n in memo:
            return memo[n]
        seen: set[str] = set()
        stack = [n]
        while stack:
            m = stack.pop()
            for p in g.predecessors(m):
                lid = g.edges[p, m]["link"]
                if lid in length_of and lid not in seen:
                    seen.add(lid)
                    stack.append(p)
        memo[n] = float(sum(length_of[l] for l in seen))
        return memo[n]

    lup = {n: total(n) for n in nodes}
    return link_dist, lup


def river_velocity(state_index: float | None) -> float:
    """Reach-averaged velocity (m/s) from the EA level index (0 = typical low, 1 = typical high)."""
    if state_index is None or not np.isfinite(state_index):
        return config.RIVER_VELOCITY_MS
    return float(0.3 + 0.7 * min(max(state_index, 0.0), 1.5))


# Catchment area, flows and reach speed from the upstream network length (velocity "catchment",
# dilution "flow"). The three ratios are medians over 1,010 NRFA gauging stations in England and
# Wales snapped to the network (scripts/fit_reach_velocity.py prints them; checked 10 Oct 2026).
# One ratio per quantity: within each eighth of the stations by area the median network length per
# km² stays between 0.52 and 0.68, so a straight proportion fits; half the stations are within a
# factor of 1.9 of it. No rainfall or geology term, so a wet upland river's flow is underestimated.
DRAINAGE_KM_PER_KM2 = 0.60    # OS Open Rivers length (km) per km² of catchment
QMEAN_PER_KM2 = 0.0138        # mean flow, m³/s per km²
Q50_PER_KM2 = 0.0082          # median daily flow (Q50), m³/s per km²
# Jobson (1996), USGS WRIR 96-4013, eq. 14, peak velocity without slope (R² 0.62 on 986 US tracer
# measurements): Vp = 0.020 + 0.051 Da'^0.821 Qa'^-0.465 Q/Da, Da' = Da^1.25 g^0.5 / Qa, Qa' = Q/Qa,
# SI units (Da in m²). Taken at Q = Q50, so a speed per place and not per day. Smalley et al. (2025,
# Sci. Total Environ. 991, 179794, supplement) used the same family (eq. 12, with slope) for the
# Thames. It gives 0.13 m/s at 10 km², 0.19 at 100 km², 0.29 at 1,000 km².
JOBSON = (0.020, 0.051, 0.821, -0.465)
VEL_MIN, VEL_MAX = 0.05, 1.5  # floor for headwater links (tiny areas tend to 0.02 m/s); cap


def catchment_km2(upstream_m: float | np.ndarray) -> float | np.ndarray:
    """Catchment area (km²) estimated from the total network length upstream (m)."""
    return np.asarray(upstream_m, dtype=float) / 1000.0 / DRAINAGE_KM_PER_KM2


def q50_m3s(area_km2: float | np.ndarray) -> float | np.ndarray:
    """Median daily flow (m³/s) estimated from catchment area alone."""
    return Q50_PER_KM2 * np.maximum(np.asarray(area_km2, dtype=float), 0.0)


def reach_velocity(upstream_m: float | np.ndarray) -> float | np.ndarray:
    """Characteristic speed (m/s) of a reach with this much network upstream: Jobson's eq. 14 at
    the median flow. One value per place, not varying with the day's flow."""
    a, b, c, d = JOBSON
    da = np.maximum(catchment_km2(upstream_m), 1e-3) * 1e6           # m²
    qa, q = QMEAN_PER_KM2 * da / 1e6, Q50_PER_KM2 * da / 1e6
    v = a + b * np.power(da ** 1.25 * math.sqrt(9.81) / qa, c) * (q / qa) ** d * q / da
    return np.clip(v, VEL_MIN, VEL_MAX)


def flow_dilution(spot_upstream_m: float | np.ndarray) -> float | np.ndarray:
    """config.DILUTION_MODE 'flow': Q_spill / (Q_spill + Q50 at the spot). The spill's size is not
    known, so Q_spill is the median flow of a catchment with L0_M of network: a spot that small
    halves a spill, as the 'length' rule does for an overflow at the head of its network. Fixed
    before any evaluation, not tuned on samples."""
    q_spill = float(q50_m3s(catchment_km2(L0_M)))
    return q_spill / (q_spill + q50_m3s(catchment_km2(spot_upstream_m)))


def upstream_times(net: RiverNetwork, root: str, cap_m: float, scale: float = 1.0) -> dict[str, float]:
    """Link -> seconds for water to go from the link's downstream end to `root`, each link run at
    reach_velocity of the network upstream of its downstream end, times `scale`. The walk is
    upstream_edges', on path distance, so each link's time is along the same path as its distance."""
    dist = {root: 0.0}
    time = {root: 0.0}
    out: dict[str, float] = {}
    best: dict[str, float] = {}
    stack = [root]
    g = net.graph
    up = net.upstream_m
    while stack:
        n = stack.pop()
        dn, tn = dist[n], time[n]
        v = float(reach_velocity(up.get(n, 0.0))) * scale
        for pred in g.predecessors(n):
            ed = g.edges[pred, n]
            lid = ed["link"]
            if lid not in best or dn < best[lid]:
                best[lid], out[lid] = dn, tn
            d_pred = dn + ed["length"]
            if d_pred <= cap_m and d_pred < dist.get(pred, np.inf):
                dist[pred], time[pred] = d_pred, tn + ed["length"] / v
                stack.append(pred)
    return out


def _link_velocity(net: RiverNetwork, link_ids: pd.Series, scale: float) -> np.ndarray:
    """reach_velocity at each link's downstream end, times `scale`."""
    ends = net.links.loc[link_ids, "end_node"].map(net.upstream_m).fillna(0.0).to_numpy(dtype=float)
    return np.asarray(reach_velocity(ends), dtype=float) * scale


def _path_to_lake(net: RiverNetwork, link_id: str, frac: float, comp: set[str],
                  on_path: set[str], max_steps: int = 5000) -> tuple[float, tuple[float, float]] | None:
    """Walk downstream from an overflow until the water enters the lake.
    Returns (river distance m, entry point xy) or None if the lake is never reached."""
    res = _walk_to_lake(net, link_id, frac, comp, on_path, max_steps)
    return None if res is None else res[:2]


def _walk_to_lake(net: RiverNetwork, link_id: str, frac: float, comp: set[str], on_path: set[str],
                  max_steps: int = 5000) -> tuple[float, tuple[float, float], float] | None:
    """_path_to_lake, also giving the seconds the river part takes at reach_velocity (scale 1)."""
    links = net.links
    if link_id in comp:
        pt = links.loc[link_id, "geometry"].interpolate(frac, normalized=True)
        return 0.0, (pt.x, pt.y), 0.0

    def speed(node: str) -> float:
        return float(reach_velocity(net.upstream_m.get(node, 0.0)))

    node = links.loc[link_id, "end_node"]
    d = (1.0 - frac) * links.loc[link_id, "length"]
    t = d / speed(node)
    for _ in range(max_steps):
        nxt = None
        for m in net.graph.successors(node):
            lid = net.graph.edges[node, m]["link"]
            if lid in comp:
                pt = links.loc[lid, "geometry"].coords[0]
                return d, (pt[0], pt[1]), t
            if lid in on_path:
                nxt = (m, lid)
        if nxt is None:
            return None
        node, lid = nxt
        step = net.repairs.get(lid, 0.0) if lid.startswith("repair:") else links.loc[lid, "length"]
        d += step
        t += step / speed(node)
    return None


def upstream_overflows(net: RiverNetwork, pin: PinLocation, overflows: pd.DataFrame,
                       velocity_ms: float, max_km: float = config.MAX_UPSTREAM_KM,
                       t90_h: float = config.T90_HOURS, velocity_mode: str | None = None,
                       dilution_mode: str | None = None) -> pd.DataFrame:
    """Overflows upstream of the pin with distance, travel time and transport weight.
    `velocity_mode` and `dilution_mode` default to config.VELOCITY_MODE and config.DILUTION_MODE.
    With velocity 'catchment', `velocity_ms` only scales each reach's speed by
    velocity_ms / config.RIVER_VELOCITY_MS, so a gauge's level index still moves it."""
    velocity_mode = velocity_mode or config.VELOCITY_MODE
    dilution_mode = dilution_mode or config.DILUTION_MODE
    if velocity_mode not in ("fixed", "catchment") or dilution_mode not in ("length", "flow"):
        raise ValueError(f"unknown transport option: velocity {velocity_mode!r}, dilution {dilution_mode!r}")
    by_reach = velocity_mode == "catchment"
    scale = velocity_ms / config.RIVER_VELOCITY_MS
    cols = list(overflows.columns) + ["distance_m", "lake_distance_m", "travel_h", "decay", "dilution", "weight"]
    if pin.mode == "none" or pin.trace_node is None:
        return pd.DataFrame(columns=cols)
    cap = max_km * 1000.0
    link_dist, lup = upstream_lengths(net, pin.trace_node, cap)
    on_path = set(link_dist)
    ov = overflows[overflows["link_id"].isin(on_path)].copy()

    # Overflows on the pin's own link, upstream of the pin (river mode only).
    if pin.mode == "river" and pin.snap is not None:
        same = overflows[(overflows["link_id"] == pin.snap.link_id) & (overflows["frac"] < pin.snap.frac)].copy()
        same["distance_m"] = (pin.snap.frac - same["frac"]) * same["link_length"]
        ov = ov[ov["link_id"] != pin.snap.link_id]
    else:
        same = ov.iloc[0:0].copy()

    if pin.mode == "river":
        ov["distance_m"] = ((1.0 - ov["frac"]) * ov["link_length"]
                            + ov["link_id"].map(link_dist) + pin.trace_offset_m)
        ov["lake_distance_m"] = 0.0
        same["lake_distance_m"] = 0.0
        if by_reach:
            # seconds on the river: the overflow's own link, the links between, then the pin's link
            v_pin = float(_link_velocity(net, pd.Series([pin.snap.link_id]), scale)[0])
            link_s = upstream_times(net, pin.trace_node, cap, scale)
            ov["river_s"] = ((1.0 - ov["frac"]) * ov["link_length"] / _link_velocity(net, ov["link_id"], scale)
                             + ov["link_id"].map(link_s) + pin.trace_offset_m / v_pin)
            same["river_s"] = same["distance_m"] / v_pin
        ov = pd.concat([ov, same], ignore_index=True)
        spot_lup = lup.get(pin.trace_node, 0.0) + pin.trace_offset_m
        spot_up_full = net.upstream_m.get(pin.trace_node, 0.0) + pin.trace_offset_m
    else:
        rows = []
        for _, r in ov.iterrows():
            res = _walk_to_lake(net, r["link_id"], r["frac"], pin.lake_links, on_path)
            if res is None:
                continue
            d_river, (ex, ey), t_river = res
            d_lake = math.hypot(ex - pin.x, ey - pin.y)
            rows.append((r.name, d_river, d_lake, t_river / scale))
        if rows:
            idx, dr, dl, tr = zip(*rows, strict=True)
            ov = ov.loc[list(idx)].copy()
            ov["distance_m"] = list(dr)
            ov["lake_distance_m"] = list(dl)
            ov["river_s"] = list(tr)
        else:
            ov = ov.iloc[0:0].copy()
            ov["distance_m"] = []
            ov["lake_distance_m"] = []
        spot_lup = lup.get(pin.trace_node, 0.0)
        spot_up_full = net.upstream_m.get(pin.trace_node, 0.0)

    if ov.empty:
        return pd.DataFrame(columns=cols)
    river_s = ov["river_s"] if by_reach else ov["distance_m"] / velocity_ms
    ov["travel_h"] = (river_s + ov["lake_distance_m"] / config.LAKE_VELOCITY_MS) / 3600.0
    ov = ov.drop(columns="river_s", errors="ignore")
    ov["decay"] = np.power(10.0, -ov["travel_h"] / t90_h)
    if dilution_mode == "flow":
        # The whole catchment's network, not the traced 60 km: flow comes from all of it.
        ov["dilution"] = float(flow_dilution(spot_up_full))
    else:
        ov_lup = ov["start_node"].map(lup).fillna(0.0) + (1.0 - ov["frac"]) * ov["link_length"] * 0  # at the outfall
        ov["dilution"] = np.minimum(1.0, (ov_lup + L0_M) / (spot_lup + L0_M))
    if pin.mode == "lake" and pin.lake_area_km2:
        # A big lake dilutes an inflow far more than a river reach of similar
        # upstream network would; halve the weight at LAKE_A0_KM2 and shrink from there.
        ov["dilution"] = ov["dilution"] / (1.0 + pin.lake_area_km2 / LAKE_A0_KM2)
    ov["weight"] = ov["decay"] * ov["dilution"]
    if "snap_confidence" in ov:
        ov.loc[ov["snap_confidence"] == "low", "weight"] *= LOW_CONFIDENCE_FACTOR
    ov = ov[ov["distance_m"] <= cap]
    return ov.sort_values("weight", ascending=False).reset_index(drop=True)


def history_days(travel_h: np.ndarray | pd.Series | None) -> int:
    """How many days before the first day of interest the spill grid must start so
    that every upstream overflow's travel time is covered: ceil(max travel / 24 h) + 1.
    Shared by the hindcast (validate_ecoli.py) and the live forecast so the two
    cannot drift apart. (The live forecast started only at yesterday until
    16 Sep 2026, so a 48 h travel time contributed nothing to today.)"""
    if travel_h is None or len(travel_h) == 0:
        return 1
    mx = float(np.nanmax(np.asarray(travel_h, dtype=float)))
    return max(1, int(np.ceil(mx / 24.0)) + 1)


def shift_by_travel(p: np.ndarray, travel_h: np.ndarray) -> np.ndarray:
    """Move each overflow's daily values later by its travel time, splitting a
    fractional day between two arrival days. p: (n_overflows, n_days)."""
    n, d = p.shape
    shift = np.asarray(travel_h, dtype=float) / 24.0
    k = np.floor(shift).astype(int)
    a = shift - k
    eff = np.zeros_like(p, dtype=float)
    for i in range(n):
        for j in range(d):
            if j + k[i] < d:
                eff[i, j + k[i]] += (1 - a[i]) * p[i, j]
            if j + k[i] + 1 < d:
                eff[i, j + k[i] + 1] += a[i] * p[i, j]
    return eff


def daily_effects(p: np.ndarray, weights: np.ndarray, travel_h: np.ndarray) -> np.ndarray:
    """(n_overflows, n_days): each overflow's chance of affecting the spot on each arrival day,
    its spill probability moved later by its travel time, times its weight. These are the terms
    combine_daily multiplies, kept apart so the page can say which overflows a day's risk comes from."""
    return np.clip(shift_by_travel(np.nan_to_num(p, nan=0.0), travel_h), 0, 1) * weights[:, None]


def combine_daily(p: np.ndarray, weights: np.ndarray, travel_h: np.ndarray) -> np.ndarray:
    """p: (n_overflows, n_days) spill probabilities by overflow and spill day.
    Returns risk per day at the spot, shifting each overflow's effect by its travel time."""
    n, d = p.shape
    if n == 0:
        return np.zeros(d)
    return 1.0 - np.prod(1.0 - daily_effects(p, weights, travel_h), axis=0)


def risk_shares(eff: np.ndarray) -> np.ndarray:
    """Each source's share of a combined risk, 1 - prod(1 - e_i) (combine_daily, live_now_risk).
    The product splits exactly in logs: -ln(1 - risk) = sum of -ln(1 - e_i), so a source's share is
    its term over that sum. For small terms this is its effect over the sum of effects. eff: (n,) or
    (n, n_days); the shares in each column add to 1, or are all 0 where the risk is 0."""
    h = -np.log1p(-np.clip(np.asarray(eff, dtype=float), 0.0, 1.0 - 1e-9))
    tot = h.sum(axis=0)
    return np.divide(h, tot, out=np.zeros_like(h), where=tot > 0)


def spread_count(shares: np.ndarray, cover: float = 0.9) -> int:
    """How many sources, largest share first, it takes to make up `cover` of a risk. A risk "spread
    over 12 overflows" is one where 12 make up nine tenths of it; the rest are slivers."""
    s = np.sort(np.asarray(shares, dtype=float))[::-1]
    if s.sum() <= 0:
        return 0
    return int(min(len(s), np.searchsorted(np.cumsum(s), cover - 1e-9) + 1))


def missing_share(available: np.ndarray, weights: np.ndarray, travel_h: np.ndarray) -> np.ndarray:
    """Per arrival day, the share of transport weight whose source day has no
    rainfall data (`available` is a bool (n_overflows, n_days) mask). Days with a
    large share get no risk figure rather than one computed as if it were dry."""
    n, d = available.shape
    if n == 0 or weights.sum() <= 0:
        return np.zeros(d)
    miss = shift_by_travel((~available).astype(float), travel_h) * weights[:, None]
    return np.clip(miss.sum(axis=0) / weights.sum(), 0, 1)


def live_now_risk(ov: pd.DataFrame, now: pd.Timestamp, recent_h: float = config.RECENT_SPILL_HOURS,
                  t90_h: float = config.T90_HOURS) -> tuple[float, pd.Series]:
    """Risk right now from the live status. A spill counts at its full weight from its start until its
    water has passed the spot: its end plus its travel time, or, while it runs, its travel time from
    now. Then it dies off with T90, and it stops counting recent_h after its water passed.

    Until 4 Oct 2026 a finished spill died off from its end and left the count recent_h after it,
    whatever its travel time, so a spill 20 h upstream was let go while its water was still arriving,
    and the headline eased before clear_time's "should clear by" did. A spill whose water has not
    reached the spot yet still counts in full from its start: still_coming says when it arrives, and
    the level does not wait for it. On 4 Oct 2026 Ethan chose this over also waiting for the water,
    which in the 13 Sep to 4 Oct builds would have dropped 15 headlines while sewage was on its way,
    one to "Low risk for the next five days" with the water 20 minutes off."""
    if ov.empty:
        return 0.0, pd.Series(dtype=float)
    counted, w, to_end, travel = _counted(ov, now, recent_h)
    contrib = np.where(counted, _contributions(0.0, w, to_end + travel, recent_h, t90_h), 0.0)
    risk = 1.0 - np.prod(1.0 - np.clip(contrib, 0, 1))
    return float(risk), pd.Series(contrib, index=ov.index)


LOW_CUT = 0.15   # risk_label: a risk under this is low


def _counted(ov: pd.DataFrame, now: pd.Timestamp, recent_h: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The spills live_now_risk counts right now, with any weight: running, or finished with its water
    passed under recent_h ago or still passing. A mask over `ov`, and for every row its weight, the
    hours from now to its end (taking a running spill to end now: 0, or negative for one that ended)
    and its travel time (`travel_h`, 0 where unknown)."""
    active = (ov["status"] == 1).to_numpy()
    end = pd.to_datetime(ov["latest_event_end"], utc=True)
    hrs_since = ((now - end).dt.total_seconds() / 3600.0).to_numpy(dtype=float)
    w = np.clip(ov["weight"].to_numpy(dtype=float), 0.0, None)
    travel = np.nan_to_num(ov["travel_h"].to_numpy(dtype=float), nan=0.0)
    counted = (active | ((hrs_since >= 0) & (hrs_since - travel <= recent_h))) & (w > 0)
    return counted, w, np.where(active, 0.0, -hrs_since), travel


def _contributions(t: float, w: np.ndarray, passed: np.ndarray, recent_h: float, t90_h: float) -> np.ndarray:
    """Each spill's part of the live risk t hours from now, if its water finishes passing the spot
    `passed` hours from now: its full weight until then, then dying off with T90, and nothing once it
    passed more than recent_h ago. With `passed` its end plus its travel time, this is live_now_risk
    run forward (a spill running now taken to end now); with its end alone, the same as if its water
    had passed the moment it stopped (the rule before 4 Oct 2026, which clear_time compares against)."""
    age = t - passed
    return np.where(age <= 0, w, np.where(age <= recent_h, w * np.power(10.0, -np.maximum(age, 0.0) / t90_h), 0.0))


ARRIVING_SAYS = 0.5   # the part of right now's risk whose water must still be on its way for the page to say when it arrives


def still_coming(ov: pd.DataFrame, now: pd.Timestamp, contrib: np.ndarray | pd.Series) -> np.ndarray:
    """Hours from now until each spill's water first reaches the spot (its start plus its travel time),
    for the spills right now's risk counts (`contrib` > 0, live_now_risk's) whose water has not arrived
    yet; NaN for the rest. A spill with no start time is taken to have arrived."""
    if ov.empty or "latest_event_start" not in ov:
        return np.full(len(ov), np.nan)
    start = pd.to_datetime(ov["latest_event_start"], utc=True)
    left = ov["travel_h"].to_numpy(dtype=float) - ((now - start).dt.total_seconds() / 3600.0).to_numpy(dtype=float)
    return np.where((np.asarray(contrib, dtype=float) > 0) & (left > 0), left, np.nan)


def _first_under(w: np.ndarray, passed: np.ndarray, cut: float, recent_h: float, t90_h: float) -> tuple[float, bool]:
    """Hours from now until the combined risk first falls below `cut`, and whether a spill leaving
    the count (recent_h after its water passed) took it under. The risk only falls as time goes on:
    smoothly as spills die off, flat while one is held, in steps as each leaves. So a bisection
    within the stretch between two steps finds the time, to well under a minute."""
    def risk(t: float, keep: np.ndarray) -> float:
        c = np.clip(_contributions(t, w[keep], passed[keep], recent_h, t90_h), 0.0, 1.0)
        return float(1.0 - np.prod(1.0 - c))

    leaves = passed + recent_h                               # hours from now until each stops counting
    start = 0.0
    for step in np.unique(leaves[leaves >= 0]):
        keep = leaves >= step                                  # still counted up to and at `step`
        if risk(step, keep) < cut:                             # dies off under the cut before this step
            lo, hi = start, float(step)
            for _ in range(40):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if risk(mid, keep) >= cut else (lo, mid)
            return hi, False
        if risk(step, leaves > step) < cut:                    # this step takes it under
            return float(step), True
        start = float(step)
    return start, True   # not reached: after the last step nothing counts


TRAVEL_SAYS = 0.5   # the part of the risk, as it clears, that travel time must hold for 'travel'


def clear_time(ov: pd.DataFrame, now: pd.Timestamp, cut: float = LOW_CUT,
               recent_h: float = config.RECENT_SPILL_HOURS,
               t90_h: float = config.T90_HOURS) -> tuple[pd.Timestamp | None, str | None, object]:
    """The time to tell a swimmer right now's risk should be back to low: live_now_risk run forward
    from `now`, if the overflows discharging now stop now, the finished spills keep their end times,
    and no new spill starts. Each spill is held at its full weight until its water has passed the spot
    (its end, or now for one running, plus its travel time), then dies off with T90, and leaves the
    count recent_h after its water passed. A small far spill then barely moves the time; a big one
    holds it up. Until 4 Oct 2026 this alone allowed for travel time and the headline's risk did not;
    both now follow one rule (live_now_risk).

    Returns (time, what set it, the index label in `ov` of the overflow named with 'travel').
    'travel' when, as it clears, travel time holds at least half the risk: the risk over and above
    what it would be had each spill's water passed the moment the spill stopped, split as risk_shares
    splits it; the overflow named is the one with the most of that. Otherwise 'window' when a spill
    leaving the count took it under, else 'die-off'. (None, None, None) when right now's risk is low."""
    if ov.empty:
        return None, None, None
    counted, w, end, travel = _counted(ov, now, recent_h)
    idx, w, end, passed = ov.index[counted], w[counted], end[counted], (end + travel)[counted]
    if 1.0 - np.prod(1.0 - np.clip(_contributions(0.0, w, passed, recent_h, t90_h), 0, 1)) < cut:
        return None, None, None
    t, jumped = _first_under(w, passed, cut, recent_h, t90_h)

    def hazard(c: np.ndarray) -> np.ndarray:   # risk_shares' split of 1 - prod(1 - c)
        return -np.log1p(-np.clip(c, 0.0, 1.0 - 1e-9))

    held = hazard(_contributions(t, w, passed, recent_h, t90_h))
    extra = held - hazard(_contributions(t, w, end, recent_h, t90_h))   # what travel time adds, per spill
    at = now + pd.Timedelta(hours=t)
    if held.sum() > 0 and extra.sum() >= TRAVEL_SAYS * held.sum():
        return at, "travel", idx[int(np.argmax(extra))]
    return at, "window" if jumped else "die-off", None


def risk_label(r: float) -> str:
    if r < LOW_CUT:
        return "low"
    if r < 0.4:
        return "moderate"
    if r < 0.7:
        return "high"
    return "very high"
