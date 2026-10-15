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
* dilution "urban"      Q_i / (Q_i + Q50 at the spot), with each overflow's spill
                        Q_i in proportion to the urban area apportioned to it
                        (urban_spill_m3s). Pre-stated in
                        docs/URBAN-DILUTION-TEST-2026-10.md.

Lakes on the way (config.LAKE_PATH_MODE) follow a note on lakes from a Lake District water-quality
group (11 Oct 2026). "residence_spill" is the default after the test pre-stated in
docs/LAKE-RESIDENCE-SPILL-2026-10.md; "lake" was the default from 11 Oct 2026, after the test pre-stated in
docs/LAKE-PATH-TEST-2026-10.md:

* lake path "lake"      a WFD lake crossed between an overflow and the spot is treated as the
                        spot's own lake is: its centreline length at LAKE_VELOCITY_MS, and the
                        dilution times 1 / (1 + A / LAKE_A0_KM2) for its area A. Lake-form links
                        outside every WFD polygon (mill ponds, weir pools) stay river.
* lake path "river"     the rule before: such a lake is walked at river speed, with no lake
                        dilution.
* lake path "residence" passed docs/LAKE-RESIDENCE-TEST-2026-10.md. A WFD lake
                        crossed on the way that has a residence time tau in config.LAKE_RESIDENCE_FILE
                        is a well-mixed lake whose bacteria die at k = ln 10 / T90: the share of a
                        spill's bacteria that leaves it alive is 1 / (1 + k tau) (lake_pass), and the
                        survivors' mean time in it is tau / (1 + k tau) (lake_hold_h). Those replace
                        the crossing at LAKE_VELOCITY_MS, its die-off and the area factor. A lake with
                        no residence time is crossed as in "lake". The spot's own lake is unchanged.
* lake path "residence_spill" the default (docs/LAKE-RESIDENCE-SPILL-2026-10.md): as "residence", with
                        each tau divided by the lake's spill-time flow ratio R >= 1, from
                        config.LAKE_RESIDENCE_SPILL_FILE.

scripts/build_any_point.py and site/anypoint.js (click anywhere) follow all four.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point

from dipcast import config
from dipcast.ingest.lakes import load_lakes
from dipcast.network.names import river_words
from dipcast.network.rivers import RiverNetwork, Snap, lonlat_to_bng

log = logging.getLogger(__name__)

L0_M = 5_000.0          # dilution smoothing length
LAKE_SNAP_M = 1_500.0   # fallback: a pin this close to a lake centreline is 'in the lake'
LAKE_SHORE_M = 150.0    # a click this close to a WFD lake polygon counts as in that lake
LAKE_NAMED_M = 1_000.0  # a lake spot named after a WFD lake this close is in that lake
LAKE_UNMAPPED_M = 500.0 # a lake spot with no WFD lake: its own centreline must be this close
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
        # A list, not .map: on an empty frame pandas 3 kept the str dtype through .map, and OR-ing two
        # empty str Series raised (Shilley Pool, 3 Oct 2026); and .map on an arrow string column cost
        # about 9 ms a call, which the click-anywhere build makes tens of thousands of (13 Oct 2026).
        return pd.Series([bool(river_words(n) & want) if isinstance(n, str) else False for n in col],
                         index=col.index, dtype=bool)
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


def _lake_words(name: str) -> str:
    """A lake's or spot's name as lower-case words, without a bracketed part:
    "Windermere (N Basin)" -> "windermere", "Ullswater, Pooley Bridge" -> "ullswater pooley bridge"."""
    name = re.sub(r"\(.*?\)", " ", name)
    return " ".join(re.findall(r"[a-z]+", name.lower()))


def _named_lake_polygon(x: float, y: float, name: str | None):
    """The nearest WFD lake within LAKE_NAMED_M whose name is in the spot's name, else None.
    Curated pins often sit on the shore path or in the village: Ullswater, Pooley Bridge is
    587 m from the Ullswater polygon. Matched on whole words, so Blea Tarn, Langdale does not
    take Little Langdale Tarn."""
    if not name:
        return None
    lakes = _lakes()
    if lakes is None or lakes.empty or "lake_name" not in lakes:
        return None
    pt = Point(x, y)
    idx = lakes.sindex.query(pt.buffer(LAKE_NAMED_M), predicate="intersects")
    if len(idx) == 0:
        return None
    cand = lakes.iloc[idx]
    spot = f" {_lake_words(name)} "
    keep = cand["lake_name"].map(lambda n: isinstance(n, str) and bool(_lake_words(n))
                                 and f" {_lake_words(n)} " in spot)
    cand = cand[keep.astype(bool)]
    if cand.empty:
        return None
    return cand.loc[cand.geometry.distance(pt).idxmin()]


def _in_mapped_lake(net: RiverNetwork, links: set[str]) -> bool:
    """Whether any of these lake centreline links lies inside a WFD lake polygon."""
    lakes = _lakes()
    if lakes is None or lakes.empty or not links:
        return False
    geom = net.links.loc[list(links)].geometry.union_all()
    return len(lakes.sindex.query(geom, predicate="intersects")) > 0


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
               river_hint: str | None = None, name: str | None = None) -> PinLocation:
    """`kind_hint` = 'lake' says the caller knows this is a lake (e.g. a designated
    lake bathing water or a curated spot). A lake with no WFD polygon and no lake
    centreline nearby is then treated as isolated rather than snapped to whatever
    river passes closest, which would credit it with that river's overflows.
    `name` is the spot's name; for a lake it finds the WFD lake the spot is named
    after when the pin is off its shore (_locate_lake).

    `river_hint` is the river the spot is on (spots.csv's `river` column). The pin
    goes to the nearest link carrying that name (or OS's alternative name, so
    "River Wye" finds "Afon Gwy") within HINT_SNAP_M, even when a link of another
    name is nearer: Crook o' Lune sat 262 m from Escow Beck and 672 m from the Lune
    and was traced up the beck, finding no overflows (2 Oct 2026). With no such link
    the nearest is kept, with a warning. Ignored for lakes."""
    x, y = lonlat_to_bng(lon, lat)
    pin = _locate(net, x, y, kind_hint, name)
    if river_hint and kind_hint != "lake":
        pin = _apply_river_hint(net, pin, river_hint)
    elif kind_hint != "lake" and pin.mode == "river" and pin.adopted_main_channel:
        pin = _click_at_head(net, pin)
    return pin


def spot_hints(kind, river) -> tuple[str | None, str | None]:
    """locate_pin's `kind_hint` and `river_hint` for a listed spot, from its spots.csv `kind` and `river`:
    the kind only when it is 'lake' or 'river', the river only for a spot that is not a lake. The site
    build and the E. coli evaluation (scripts/eval_pins.py) both place spots with it. Until 12 Oct 2026
    the evaluation passed no hints, and put Colwick West Lake on the River Trent, 357 overflows that the
    site does not count (docs/EVAL-PINS-TEST-2026-10.md)."""
    kind = kind if kind in ("lake", "river") else None
    river = river.strip() if isinstance(river, str) else ""
    return kind, (river if river and kind != "lake" else None)


def _side_arm_head(net: RiverNetwork, link_id: str) -> tuple[float, float]:
    """Where a side arm with little network above it begins: up its links while there is exactly one
    link in and the network above stays under ADOPT_MIN_M. Returns that point (BNG)."""
    return _side_arm(net, link_id)[0]


ARM_MAX_M = 2_000.0   # a side arm longer than this, head to the end of the link clicked, takes no head move


def _side_arm(net: RiverNetwork, link_id: str) -> tuple[tuple[float, float], float]:
    """_side_arm_head's point, and the arm's length along its links from there to the downstream end
    of `link_id`. The length is what ARM_MAX_M limits: on the Little Stour at 51.3240, 1.2561 a click
    was sent to an arm's head 3.6 km away (docs/ANYPOINT-SIDE-ARM-LENGTH-2026-10.md)."""
    lid = link_id
    length = float(net.links.at[lid, "length"])
    for _ in range(50):
        s, _e = net.link_nodes(lid)
        preds = list(net.graph.predecessors(s))
        if len(preds) != 1:
            break
        up = net.graph.edges[preds[0], s]["link"]
        if up.startswith("repair:") or net.link_upstream_m(up) >= ADOPT_MIN_M:
            break
        lid = up
        length += float(net.links.at[lid, "length"])
    x, y = net.links.loc[lid, "geometry"].coords[0][:2]
    return (x, y), length


def _adopt_at_head(net: RiverNetwork, x: float, y: float, want: frozenset[str]) -> Snap | None:
    """A spot on a side arm takes the water of the river the arm leaves: of the channels named like the
    spot's river near the arm's head, with at least ADOPT_RATIO times its network, the one with most, snapped
    where the head is. None when the pin's link is not a side arm or no such channel is near its head.

    _adopt_main_channel takes the candidate near the pin with the most network, which is right for a
    mill stream beside its river but not where the arm passes a confluence: at Queen Elizabeth Gardens,
    Salisbury, the sampling point is 1 m from an arm of the Avon that OS draws with nothing above it,
    and the Avon link with the most network was the one below the Nadder, so the Nadder and the Wylye
    were counted, which the EA's zone of influence leaves out (11 Oct 2026)."""
    river = net.snap_xy(x, y, max_m=PIN_SNAP_M)
    if river is None or river.form not in RIVER_FORMS:
        return None
    return head_of_arm(net, river.link_id, want)


def head_of_arm(net: RiverNetwork, link_id: str, want: frozenset[str]) -> Snap | None:
    """_adopt_at_head from the arm's own link: where a pin on that river link goes, or None. The
    click-anywhere build (scripts/build_any_point.py, arm_heads) calls it for every small link, as
    the page cannot walk the network."""
    own = net.link_upstream_m(link_id)
    if own >= ADOPT_MIN_M:
        return None
    (hx, hy), arm_m = _side_arm(net, link_id)
    if arm_m > ARM_MAX_M:
        return None
    cand = net.candidates_xy(hx, hy, ADOPT_RADIUS_M)
    cand = cand[cand["form"].isin(RIVER_FORMS) & (cand.index != link_id)]
    cand = cand[_names_match(cand, want)]
    if cand.empty:
        return None
    ups = pd.Series([net.upstream_m.get(n, 0.0) for n in cand["start_node"]], index=cand.index)   # as _names_match, no .map
    keep = ups >= max(ADOPT_MIN_M, ADOPT_RATIO * own)
    if not keep.any():
        return None
    # The one with the most network, not the nearest: OS draws braided channels of a big river under its
    # name, disconnected above, and the nearest of those took a click on the Medway from 420 km of network
    # to 12 km (docs/ANYPOINT-SIDE-ARM-MOST-2026-10.md). idxmax keeps the first of equals, and
    # candidates_xy sorts nearest first, so a tie goes to the nearer.
    return _snap_to_links(net, hx, hy, {ups[keep].idxmax()})


def _at_head(net: RiverNetwork, pin: PinLocation, head: Snap, prefer: frozenset[str] | None = None) -> PinLocation:
    start, _ = net.link_nodes(head.link_id)
    return PinLocation("river", pin.x, pin.y, head, trace_node=start,
                       trace_offset_m=head.frac * net.links.loc[head.link_id, "length"],
                       watercourse=_link_name(net, head.link_id, prefer=prefer), adopted_main_channel=True,
                       placement="side arm head")


def channel_words(net: RiverNetwork, link_id: str) -> frozenset[str]:
    """The words of a link's own name and OS's alternative: the river a click moved to that link is
    taken to be on. Empty for an unnamed link."""
    row = net.links.loc[link_id]
    words: frozenset[str] = frozenset()
    for col in ("watercourse_name", "watercourse_name_alternative"):
        n = row.get(col)
        if isinstance(n, str) and n:
            words |= river_words(n)
    return words


HEAD_FLOOR_SHARE = 0.10   # a side-arm head move keeps at least this share of the old rule's channel's network


def keeps_river(net: RiverNetwork, head: Snap | None, old_link: str) -> Snap | None:
    """`head`, unless its channel has under HEAD_FLOOR_SHARE of the network above `old_link`, the
    channel _adopt_main_channel chose. On the Test at 50.9379, -1.4865 the arm's head is 362 m from
    the click and the only Test channel near it has 9 km above it, against the 391 km of the Test
    under the click (docs/ANYPOINT-SIDE-ARM-FLOOR-2026-10.md). At Queen Elizabeth Gardens the Avon
    above the Nadder keeps 40% of the Avon below it, so that move stands."""
    if head is None:
        return None
    up = lambda lid: net.upstream_m.get(net.links.at[lid, "start_node"], 0.0)   # noqa: E731
    return head if up(head.link_id) >= HEAD_FLOOR_SHARE * up(old_link) else None


def _click_at_head(net: RiverNetwork, pin: PinLocation) -> PinLocation:
    """A click, with no river named, that the old rule moved from a side channel to a main channel
    takes the side-arm head rule too, the wanted river being the channel the old rule chose. Until
    13 Oct 2026 only listed spots did: a click at Queen Elizabeth Gardens, Salisbury, counted the
    Nadder and the Wylye, which the spot leaves out (docs/ANYPOINT-SIDE-ARM-2026-10.md)."""
    want = channel_words(net, pin.snap.link_id)
    if not want:
        return pin
    head = keeps_river(net, _adopt_at_head(net, pin.x, pin.y, want), pin.snap.link_id)
    return pin if head is None else _at_head(net, pin, head)


def _apply_river_hint(net: RiverNetwork, pin: PinLocation, hint: str) -> PinLocation:
    want = river_words(hint)
    shown = river_words(hint, welsh=False)   # the name is shown as spots.csv spells it, Welsh or English
    if not want:
        return pin
    if pin.mode == "river" and pin.adopted_main_channel:
        head = keeps_river(net, _adopt_at_head(net, pin.x, pin.y, want), pin.snap.link_id)
        if head is not None:
            log.info("placed on %s where the side arm leaves it, %.0f m from the arm's head", hint, head.dist_m)
            return _at_head(net, pin, head, prefer=shown)
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


def _in_polygon(net: RiverNetwork, x: float, y: float, poly) -> PinLocation | None:
    """The pin placed in a WFD lake: the lake's centreline links are the ones intersecting
    the polygon. None when the polygon holds no lake centreline and none is near."""
    idx = net.links.sindex.query(poly.geometry, predicate="intersects")
    cand = net.links.iloc[idx]
    lake_links = set(cand.index[cand["form"] == "lake"])
    if not lake_links:
        near = net.snap_xy(x, y, max_m=LAKE_SNAP_M, forms=("lake",))
        if near is not None:
            lake_links = net.lake_component(near.link_id)
    if not lake_links:
        return None
    outlet = _lake_outlet(net, lake_links)
    name = poly.get("lake_name")
    return PinLocation("lake", x, y, _snap_to_links(net, x, y, lake_links), lake_links, outlet,
                       trace_node=outlet, watercourse=str(name) if isinstance(name, str) else None,
                       lake_area_km2=float(poly["area_km2"]), lake_source="polygon")


def _centreline_lake(net: RiverNetwork, x: float, y: float, lake: Snap) -> PinLocation:
    comp = net.lake_component(lake.link_id)
    outlet = _lake_outlet(net, comp)
    own = net.links.loc[lake.link_id, "watercourse_name"]  # do not borrow the outflow river's name
    return PinLocation("lake", x, y, lake, comp, outlet, trace_node=outlet,
                       watercourse=str(own) if isinstance(own, str) and own else None, lake_source="centreline")


def _locate_lake(net: RiverNetwork, x: float, y: float, name: str | None) -> PinLocation:
    """A spot known to be a lake, with no WFD lake within LAKE_SHORE_M.

    1. A WFD lake within LAKE_NAMED_M that the spot is named after: the spot is in it.
    2. Otherwise the spot is a small lake the WFD set leaves out (under 50 ha). Its own
       centreline, if OS Open Rivers draws one, is within LAKE_UNMAPPED_M: half the width
       of a 50 ha lake, plus a margin for a pin on the bank. A centreline inside a WFD lake
       is that lake's, not this one's.
    3. Otherwise it is isolated: no overflow reaches it by water.

    Until 11 Oct 2026 any lake centreline within LAKE_SNAP_M counted. Loughrigg Tarn then
    took Grasmere's centreline, 883 m away, and with it Grasmere WwTW as an overflow upstream,
    though no water flows from Grasmere into the tarn (reported by a Lake District water-quality
    group, 11 Oct 2026)."""
    poly = _named_lake_polygon(x, y, name)
    if poly is not None:
        pin = _in_polygon(net, x, y, poly)
        if pin is not None:
            return pin
    lake = net.snap_xy(x, y, max_m=LAKE_UNMAPPED_M, forms=("lake",))
    if lake is not None:
        comp = net.lake_component(lake.link_id)
        if not _in_mapped_lake(net, comp):
            return _centreline_lake(net, x, y, lake)
        # A pin 150-500 m off a WFD lake whose name it does not carry: most likely that lake under
        # another name, so say so in the build log rather than let it pass as isolated unseen.
        log.warning("lake spot %r: the nearest lake centreline, %.0f m away, is in a WFD lake the spot "
                    "is not named after; treated as isolated", name, lake.dist_m)
    return PinLocation("isolated", x, y, None, watercourse=None, lake_source="none")


def _locate(net: RiverNetwork, x: float, y: float, kind_hint: str | None, name: str | None = None) -> PinLocation:
    # 1. Inside (or on the shore of) a WFD lake polygon.
    poly = _lake_polygon_at(x, y)
    if poly is not None:
        pin = _in_polygon(net, x, y, poly)
        if pin is not None:
            return pin

    # 2. A spot known to be a lake: its own lake, or isolated, never a river.
    if kind_hint == "lake":
        return _locate_lake(net, x, y, name)

    # 3. Otherwise decide between river and (small, unmapped) lake by centreline distance.
    river = net.snap_xy(x, y, max_m=PIN_SNAP_M)
    lake = net.snap_xy(x, y, max_m=LAKE_SNAP_M, forms=("lake",))
    use_lake = lake is not None and (
        river is None or river.form == "lake" or lake.dist_m * LAKE_BIAS < river.dist_m
    )
    if use_lake:
        return _centreline_lake(net, x, y, lake)
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


# Spill flow of modes "flow" and "urban" (the median overflow): the Q50 of a catchment with L0_M of network.
Q_SPILL_M3S = float(q50_m3s(catchment_km2(L0_M)))


def flow_dilution(spot_upstream_m: float | np.ndarray) -> float | np.ndarray:
    """config.DILUTION_MODE 'flow': Q_spill / (Q_spill + Q50 at the spot). The spill's size is not
    known, so Q_spill is the median flow of a catchment with L0_M of network: a spot that small
    halves a spill, as the 'length' rule does for an overflow at the head of its network. Fixed
    before any evaluation, not tuned on samples."""
    return Q_SPILL_M3S / (Q_SPILL_M3S + q50_m3s(catchment_km2(spot_upstream_m)))


# Dilution "urban": a spill per overflow from the urban area apportioned to it. Quaranta et al.
# (2022, J. Hydrol. Reg. Stud. 41, 101080) model spill volume as linear in impervious urban area.
# The areas come from ONS Built Up Areas (December 2022) Boundaries GB BGG, Open Government Licence
# v3.0 (https://www.arcgis.com/home/item.html?id=ad30b234308f4b02b4bb9b0f4766f7bb; "Source: Office
# for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data © Crown
# copyright and database right 2022"), split equally between the overflows nearest each area
# (scripts/make_overflow_urban_area.py). URBAN_MEDIAN_KM2 is the median share over all 14,630
# overflows, so the median overflow spills Q_SPILL_M3S, as in mode "flow". Fixed before any
# evaluation (docs/URBAN-DILUTION-TEST-2026-10.md), not tuned on samples.
URBAN_AREA_FILE = "overflow_urban_area.parquet"
URBAN_MEDIAN_KM2 = 0.512
URBAN_MIN_KM2, URBAN_MAX_KM2 = 0.1, 6.0


def urban_spill_m3s(urban_km2: float | np.ndarray) -> float | np.ndarray:
    """An overflow's spill flow (m³/s): Q_SPILL_M3S scaled by its urban area over the median one's."""
    a = np.clip(np.asarray(urban_km2, dtype=float), URBAN_MIN_KM2, URBAN_MAX_KM2)
    return Q_SPILL_M3S * a / URBAN_MEDIAN_KM2


def urban_dilution(urban_km2: float | np.ndarray, spot_upstream_m: float) -> float | np.ndarray:
    """config.DILUTION_MODE 'urban': Q_i / (Q_i + Q50 at the spot), Q_i from the overflow's urban area."""
    q = urban_spill_m3s(urban_km2)
    return q / (q + q50_m3s(catchment_km2(spot_upstream_m)))


@lru_cache(maxsize=1)
def _urban_km2_by_site() -> pd.Series:
    """site_id -> apportioned urban area (km²), from scripts/make_overflow_urban_area.py."""
    path = config.PROCESSED / URBAN_AREA_FILE
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run scripts/make_overflow_urban_area.py for dilution 'urban'")
    t = pd.read_parquet(path, columns=["site_id", "urban_km2"])
    return t.drop_duplicates("site_id").set_index("site_id")["urban_km2"]


def overflow_urban_km2(ov: pd.DataFrame) -> pd.Series:
    """The overflows' urban areas: their own `urban_km2` column if present, else the lookup by
    site_id. An overflow missing from both gets URBAN_MEDIAN_KM2, the spill of mode 'flow'."""
    if "urban_km2" in ov:
        a = ov["urban_km2"]
    else:
        a = ov["site_id"].map(_urban_km2_by_site())
    return a.astype(float).fillna(URBAN_MEDIAN_KM2)


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


# Lakes on the way (lake path "lake"): (metres of WFD lake, their seconds at reach_velocity, the lakes
# by row in _lakes()) along a path. NO_LAKES for a path that crosses none.
PathLakes = tuple[float, float, frozenset]
NO_LAKES: PathLakes = (0.0, 0.0, frozenset())


def _with_lake(part: PathLakes, lake: tuple[int, float] | None, length: float, speed: float) -> PathLakes:
    """`part` and one more link of `length` m, if that link is in a WFD lake (`lake` from _wfd_lake_of)."""
    if lake is None:
        return part
    m, s, lakes = part
    return m + length, s + length / speed, lakes | {lake[0]}


def _wfd_lake_of(net: RiverNetwork, link_ids, exclude=frozenset()) -> dict[str, tuple[int, float]]:
    """The lake-form links among `link_ids` (less `exclude`) that lie in a WFD lake polygon:
    link -> (the polygon's row in _lakes(), its area km²). A link in two polygons (Windermere's two
    basins meet on one) goes to the one that holds more of its length; one that only touches a
    polygon is not in it. Lake-form links outside every polygon (mill ponds, weir pools, tarns under
    the WFD size) are left out, so they stay river."""
    lakes = _lakes()
    if lakes is None or lakes.empty:
        return {}
    ids = [lid for lid in link_ids if lid not in exclude and not lid.startswith("repair:")]
    if not ids:
        return {}
    sub = net.links.loc[ids]
    sub = sub[sub["form"] == "lake"]
    if sub.empty:
        return {}
    li, pi = lakes.sindex.query(sub.geometry.values, predicate="intersects")
    if len(li) == 0:
        return {}
    poly = np.asarray(lakes.geometry.values[pi], dtype=object)
    bad = ~shapely.is_valid(poly)   # 14 of the 564 have nested shells; GEOS refuses to intersect those
    poly[bad] = shapely.make_valid(poly[bad])
    inside = shapely.length(shapely.intersection(np.asarray(sub.geometry.values[li], dtype=object), poly))
    pairs = pd.DataFrame({"link": sub.index.values[li], "lake": pi, "m": inside})
    pairs = pairs[pairs["m"] > 0].sort_values(["m", "lake"], ascending=[False, True]).drop_duplicates("link")
    area = lakes["area_km2"].to_numpy(dtype=float)
    return {lid: (int(p), float(area[p])) for lid, p in zip(pairs["link"], pairs["lake"], strict=True)}


@lru_cache(maxsize=4)
def _residence_by_wb(path: str) -> dict[str, float]:
    """WFD water body id -> residence time (hours), from the file scripts/make_lake_residence.py writes.
    Rows with no positive time are left out, so those lakes are crossed as in lake path 'lake'."""
    t = pd.read_csv(path, usecols=["wb_id", "res_time_d"])
    t = t[t["res_time_d"] > 0]
    return dict(zip(t["wb_id"], t["res_time_d"].astype(float) * 24.0, strict=True))


def lake_residence_h(mode: str = "residence") -> dict[int, float]:
    """Row in _lakes() -> residence time (hours), for the WFD lakes that have one: from
    config.LAKE_RESIDENCE_FILE for lake path 'residence', config.LAKE_RESIDENCE_SPILL_FILE for 'residence_spill'."""
    lakes = _lakes()
    if lakes is None or lakes.empty or "wb_id" not in lakes:
        return {}
    path = config.LAKE_RESIDENCE_SPILL_FILE if mode == "residence_spill" else config.LAKE_RESIDENCE_FILE
    by_wb = _residence_by_wb(str(path))
    return {i: by_wb[w] for i, w in enumerate(lakes["wb_id"]) if w in by_wb}


def lake_pass(tau_h: float | np.ndarray, t90_h: float = config.T90_HOURS) -> float | np.ndarray:
    """Share of a spill's bacteria that leaves a well-mixed lake alive: 1 / (1 + k tau), k = ln 10 / T90.
    Bacteria leave at rate 1 / tau and die at rate k, so a share (1/tau) / (1/tau + k) leaves alive."""
    return 1.0 / (1.0 + math.log(10.0) * np.asarray(tau_h, dtype=float) / t90_h)


def lake_hold_h(tau_h: float | np.ndarray, t90_h: float = config.T90_HOURS) -> float | np.ndarray:
    """Mean time (hours) that the bacteria which leave a well-mixed lake alive spent in it: 1 / (1/tau + k)."""
    return np.asarray(tau_h, dtype=float) * lake_pass(tau_h, t90_h)


def _lake_divisor(lakes: frozenset, lake_area: dict[int, float]) -> float:
    """The product of 1 + A / LAKE_A0_KM2 over the lakes crossed: the spot's own-lake factor, once per lake."""
    return float(np.prod([1.0 + lake_area[k] / LAKE_A0_KM2 for k in sorted(lakes)])) if lakes else 1.0


def _path_lakes(net: RiverNetwork, root: str, cap_m: float, lake_of: dict[str, tuple[int, float]],
                scale: float = 1.0) -> dict[str, PathLakes]:
    """Link -> the WFD lakes on the path from the link's downstream end to `root`, their metres and
    their seconds at reach_velocity times `scale` (what upstream_times gives those metres). The walk
    is upstream_edges', on path distance, so each link's lakes are on the same path as its distance."""
    dist = {root: 0.0}
    part = {root: NO_LAKES}
    out: dict[str, PathLakes] = {}
    best: dict[str, float] = {}
    stack = [root]
    g = net.graph
    up = net.upstream_m
    while stack:
        n = stack.pop()
        dn, pn = dist[n], part[n]
        for pred in g.predecessors(n):
            ed = g.edges[pred, n]
            lid = ed["link"]
            if lid not in best or dn < best[lid]:
                best[lid], out[lid] = dn, pn
            d_pred = dn + ed["length"]
            if d_pred <= cap_m and d_pred < dist.get(pred, np.inf):
                lake = lake_of.get(lid)
                speed = float(reach_velocity(up.get(n, 0.0))) * scale if lake is not None else 1.0
                dist[pred], part[pred] = d_pred, _with_lake(pn, lake, ed["length"], speed)
                stack.append(pred)
    return out


def _walk_to_lake(net: RiverNetwork, link_id: str, frac: float, comp: set[str], on_path: set[str],
                  max_steps: int = 5000, lake_of: dict[str, tuple[int, float]] | None = None,
                  ) -> tuple[float, tuple[float, float], float, PathLakes] | None:
    """_path_to_lake, also giving the seconds the river part takes at reach_velocity (scale 1) and,
    with `lake_of` (_wfd_lake_of), the WFD lakes crossed before the spot's lake. The distance and
    seconds still include those lakes' links."""
    links = net.links
    lake_of = lake_of or {}
    if link_id in comp:
        pt = links.loc[link_id, "geometry"].interpolate(frac, normalized=True)
        return 0.0, (pt.x, pt.y), 0.0, NO_LAKES

    def speed(node: str) -> float:
        return float(reach_velocity(net.upstream_m.get(node, 0.0)))

    node = links.loc[link_id, "end_node"]
    d = (1.0 - frac) * links.loc[link_id, "length"]
    t = d / speed(node)
    crossed = _with_lake(NO_LAKES, lake_of.get(link_id), d, speed(node)) if lake_of else NO_LAKES
    for _ in range(max_steps):
        nxt = None
        for m in net.graph.successors(node):
            lid = net.graph.edges[node, m]["link"]
            if lid in comp:
                pt = links.loc[lid, "geometry"].coords[0]
                return d, (pt[0], pt[1]), t, crossed
            if lid in on_path:
                nxt = (m, lid)
        if nxt is None:
            return None
        node, lid = nxt
        step = net.repairs.get(lid, 0.0) if lid.startswith("repair:") else links.loc[lid, "length"]
        d += step
        t += step / speed(node)
        if lake_of and lid in lake_of:
            crossed = _with_lake(crossed, lake_of[lid], step, speed(node))
    return None


def upstream_overflows(net: RiverNetwork, pin: PinLocation, overflows: pd.DataFrame,
                       velocity_ms: float, max_km: float = config.MAX_UPSTREAM_KM,
                       t90_h: float = config.T90_HOURS, velocity_mode: str | None = None,
                       dilution_mode: str | None = None, lake_path_mode: str | None = None) -> pd.DataFrame:
    """Overflows upstream of the pin with distance, travel time and transport weight.
    `velocity_mode`, `dilution_mode` and `lake_path_mode` default to config.VELOCITY_MODE,
    config.DILUTION_MODE and config.LAKE_PATH_MODE.
    With velocity 'catchment', `velocity_ms` only scales each reach's speed by
    velocity_ms / config.RIVER_VELOCITY_MS, so a gauge's level index still moves it.
    With lake path 'lake', the length of each WFD lake crossed on the way moves from distance_m to
    lake_distance_m (their sum, the distance along the network, is unchanged, and the 60 km cap
    still applies to it), and the dilution is divided by 1 + A / LAKE_A0_KM2 for each such lake.
    With lake path 'residence', a lake on the way with a residence time (lake_residence_h) is crossed
    as a well-mixed lake instead: its metres still move to lake_distance_m, but travel_h counts
    lake_hold_h for it in place of its metres at LAKE_VELOCITY_MS, decay is the die-off of the rest of
    the journey times lake_pass, and its area factor is dropped. Other lakes are crossed as in 'lake'."""
    velocity_mode = velocity_mode or config.VELOCITY_MODE
    dilution_mode = dilution_mode or config.DILUTION_MODE
    lake_path_mode = lake_path_mode or config.LAKE_PATH_MODE
    if (velocity_mode not in ("fixed", "catchment") or dilution_mode not in ("length", "flow", "urban")
            or lake_path_mode not in ("river", "lake", *config.RESIDENCE_MODES)):
        raise ValueError(f"unknown transport option: velocity {velocity_mode!r}, dilution {dilution_mode!r}, "
                         f"lake path {lake_path_mode!r}")
    by_reach = velocity_mode == "catchment"
    on_lakes = lake_path_mode in ("lake", *config.RESIDENCE_MODES)
    residence = lake_path_mode in config.RESIDENCE_MODES
    scale = velocity_ms / config.RIVER_VELOCITY_MS
    cols = list(overflows.columns) + ["distance_m", "lake_distance_m", "travel_h", "decay", "dilution", "weight"]
    if pin.mode == "none" or pin.trace_node is None:
        return pd.DataFrame(columns=cols)
    cap = max_km * 1000.0
    link_dist, lup = upstream_lengths(net, pin.trace_node, cap)
    on_path = set(link_dist)
    ov = overflows[overflows["link_id"].isin(on_path)].copy()
    # The WFD lakes on the way, other than the spot's own (lake path 'lake' only).
    lake_of = _wfd_lake_of(net, on_path, exclude=pin.lake_links) if on_lakes else {}
    lake_area = {k: a for k, a in lake_of.values()}
    # Lake path 'residence': the lakes on the way that have a residence time, and those times (hours).
    tau = lake_residence_h(lake_path_mode) if residence else {}
    res_of = {lid: v for lid, v in lake_of.items() if v[0] in tau}

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
        if on_lakes:
            # Lakes below the overflow's link, then the part of its own link below it if that is
            # a lake. The pin's own link is a river link (_locate puts a pin on a lake link in lake mode).
            below = _path_lakes(net, pin.trace_node, cap, lake_of, scale)
            parts = []
            for lid, frac, length in zip(ov["link_id"], ov["frac"], ov["link_length"], strict=True):
                own = lake_of.get(lid)
                v = float(_link_velocity(net, pd.Series([lid]), scale)[0]) if own is not None else 1.0
                parts.append(_with_lake(below.get(lid, NO_LAKES), own, (1.0 - frac) * length, v))
            _put_lakes(ov, parts, lake_area)
            _put_lakes(same, [NO_LAKES] * len(same), lake_area)
            if residence:
                below_res = _path_lakes(net, pin.trace_node, cap, res_of, scale)
                _put_residence(ov, [_with_lake(below_res.get(lid, NO_LAKES), res_of.get(lid), (1.0 - frac) * length, 1.0)
                                    for lid, frac, length in zip(ov["link_id"], ov["frac"], ov["link_length"], strict=True)],
                               lake_area, tau, t90_h)
                _put_residence(same, [NO_LAKES] * len(same), lake_area, tau, t90_h)
        ov = pd.concat([ov, same], ignore_index=True)
        spot_lup = lup.get(pin.trace_node, 0.0) + pin.trace_offset_m
        spot_up_full = net.upstream_m.get(pin.trace_node, 0.0) + pin.trace_offset_m
    else:
        rows = []
        for _, r in ov.iterrows():
            res = _walk_to_lake(net, r["link_id"], r["frac"], pin.lake_links, on_path, lake_of=lake_of)
            if res is None:
                continue
            d_river, (ex, ey), t_river, (lm, ls, lk) = res
            d_lake = math.hypot(ex - pin.x, ey - pin.y)
            rows.append((r.name, d_river, d_lake, t_river / scale, (lm, ls / scale, lk)))
        if rows:
            idx, dr, dl, tr, crossed = zip(*rows, strict=True)
            ov = ov.loc[list(idx)].copy()
            ov["distance_m"] = list(dr)
            ov["lake_distance_m"] = list(dl)
            ov["river_s"] = list(tr)
            if on_lakes:
                _put_lakes(ov, list(crossed), lake_area)
            if residence:
                # The same walk, with only the lakes that have a residence time.
                _put_residence(ov, [_walk_to_lake(net, r["link_id"], r["frac"], pin.lake_links, on_path, lake_of=res_of)[3]
                                    for _, r in ov.iterrows()], lake_area, tau, t90_h)
        else:
            ov = ov.iloc[0:0].copy()
            ov["distance_m"] = []
            ov["lake_distance_m"] = []
        spot_lup = lup.get(pin.trace_node, 0.0)
        spot_up_full = net.upstream_m.get(pin.trace_node, 0.0)

    if ov.empty:
        return pd.DataFrame(columns=cols)
    if on_lakes:
        # A lake on the way is crossed as the spot's own lake is: its metres leave the river distance
        # (and their seconds at river speed leave the reach-by-reach time) for the lake distance.
        # The cap is kept on the distance as it was, so the same overflows are traced in both modes.
        ov["_cap_m"] = ov["distance_m"]
        ov["distance_m"] = ov["distance_m"] - ov["_lake_m"]
        ov["lake_distance_m"] = ov["lake_distance_m"] + ov["_lake_m"]
        if by_reach:
            ov["river_s"] = ov["river_s"] - ov["_lake_s"]
    river_s = ov["river_s"] if by_reach else ov["distance_m"] / velocity_ms
    if residence:
        # A lake with a residence time: the survivors' time in it, not its metres at LAKE_VELOCITY_MS;
        # its die-off is in lake_pass, so the rest of the journey decays as before.
        moving_h = (river_s + (ov["lake_distance_m"] - ov["_res_m"]) / config.LAKE_VELOCITY_MS) / 3600.0
        ov["travel_h"] = moving_h + ov["_res_hold_h"]
        ov["decay"] = np.power(10.0, -moving_h / t90_h) * ov["_res_pass"]
        ov["_lake_div"] = ov["_lake_div"] / ov["_res_div"]   # no area factor for those lakes
    else:
        ov["travel_h"] = (river_s + ov["lake_distance_m"] / config.LAKE_VELOCITY_MS) / 3600.0
        ov["decay"] = np.power(10.0, -ov["travel_h"] / t90_h)
    ov = ov.drop(columns="river_s", errors="ignore")
    if dilution_mode == "flow":
        # The whole catchment's network, not the traced 60 km: flow comes from all of it.
        ov["dilution"] = float(flow_dilution(spot_up_full))
    elif dilution_mode == "urban":
        ov["dilution"] = np.asarray(urban_dilution(overflow_urban_km2(ov).to_numpy(), spot_up_full), dtype=float)
    else:
        ov_lup = ov["start_node"].map(lup).fillna(0.0) + (1.0 - ov["frac"]) * ov["link_length"] * 0  # at the outfall
        ov["dilution"] = np.minimum(1.0, (ov_lup + L0_M) / (spot_lup + L0_M))
    if pin.mode == "lake" and pin.lake_area_km2:
        # A big lake dilutes an inflow far more than a river reach of similar
        # upstream network would; halve the weight at LAKE_A0_KM2 and shrink from there.
        ov["dilution"] = ov["dilution"] / (1.0 + pin.lake_area_km2 / LAKE_A0_KM2)
    if on_lakes:
        ov["dilution"] = ov["dilution"] / ov["_lake_div"]   # the same factor for each lake on the way
    ov["weight"] = ov["decay"] * ov["dilution"]
    if "snap_confidence" in ov:
        ov.loc[ov["snap_confidence"] == "low", "weight"] *= LOW_CONFIDENCE_FACTOR
    if on_lakes:
        ov = ov[ov["_cap_m"] <= cap].drop(columns=["_cap_m", "_lake_m", "_lake_s", "_lake_div"])
        ov = ov.drop(columns=["_res_m", "_res_hold_h", "_res_pass", "_res_div"], errors="ignore")
    else:
        ov = ov[ov["distance_m"] <= cap]
    return ov.sort_values("weight", ascending=False).reset_index(drop=True)


def _put_residence(ov: pd.DataFrame, parts: list[PathLakes], lake_area: dict[int, float], tau: dict[int, float],
                   t90_h: float) -> None:
    """Lake path 'residence': each row's lakes on the way that have a residence time (`parts`, walked with only
    those lakes), as working columns: their metres, the survivors' hours in them (sum of lake_hold_h), the share
    that leaves them alive (product of lake_pass) and their area divisor, which comes out of _lake_div."""
    ov["_res_m"] = [p[0] for p in parts]
    ov["_res_hold_h"] = [float(sum(lake_hold_h(tau[k], t90_h) for k in p[2])) for p in parts]
    ov["_res_pass"] = [float(np.prod([lake_pass(tau[k], t90_h) for k in sorted(p[2])])) if p[2] else 1.0 for p in parts]
    ov["_res_div"] = [_lake_divisor(p[2], lake_area) for p in parts]


def _put_lakes(ov: pd.DataFrame, parts: list[PathLakes], lake_area: dict[int, float]) -> None:
    """Each row's lakes on the way as the working columns upstream_overflows reads in lake path 'lake':
    their metres, their seconds at reach speed, and the divisor of the dilution."""
    ov["_lake_m"] = [p[0] for p in parts]
    ov["_lake_s"] = [p[1] for p in parts]
    ov["_lake_div"] = [_lake_divisor(p[2], lake_area) for p in parts]


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


def running(ov: pd.DataFrame) -> np.ndarray:
    """Whether each overflow's spill is running, as far as the live feeds last said: status 1, or a row
    carried through its company's feed outage (ingest.live.carry_forward, status FEED_DOWN) whose
    last status read was 1. Until 11 Oct 2026 only status 1 counted, and as every discharging row has
    an empty event end, a spill running when its company's feed failed (or a short read missed it)
    left the right-now risk and the count of what is discharging until the feed answered again."""
    from dipcast.ingest.live import FEED_DOWN
    status = pd.to_numeric(ov["status"], errors="coerce")
    last = pd.to_numeric(ov["last_status"], errors="coerce") if "last_status" in ov else pd.Series(np.nan, index=ov.index)
    return (status.eq(1) | (status.eq(FEED_DOWN) & last.eq(1))).to_numpy(dtype=bool)


def _counted(ov: pd.DataFrame, now: pd.Timestamp, recent_h: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The spills live_now_risk counts right now, with any weight: running (`running`, which keeps a
    spill running at the last poll before its company's feed failed), or finished with its water
    passed under recent_h ago or still passing. A mask over `ov`, and for every row its weight, the
    hours from now to its end (taking a running spill to end now: 0, or negative for one that ended)
    and its travel time (`travel_h`, 0 where unknown)."""
    active = running(ov)
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
