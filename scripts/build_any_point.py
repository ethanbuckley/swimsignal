"""Publish the data a page needs to forecast any clicked point, with no server.

forecast_point forecasts a point by loading the river network (113 MB on disk, about 900 MB in
memory) and tracing upstream. GitHub Pages cannot run that, so the build does the tracing here,
once per network release, and publishes what is left for the page: snap the click to a link, read
that link's upstream overflows, and do the transport arithmetic of model/transport.py with the
day's spill probabilities.

Everything is written under site/data/anypoint/:

  tiles.json           the 0.25-degree squares that have files, the scales and the versions
  overflow_ids.json    the overflows: id, name and position; every other file names an overflow
                       by its place in this list
  overflow_days.json   per overflow: spill probability by day (thousandths; null where its rain
                       cell had no data, which is the `ok` mask), the "right now" weight
                       (thousandths), live status, company, how old its rain forecast is, and
                       the low-confidence snaps; and per rain square, the rain in the 48 h to
                       midday on each day ahead, for a click with no overflow upstream
  link_index/<t>.bin   per link: number, form, name and its line as the network has it, packed
                       Int32/Float32
                       (layout in `pack_link_index`), so the page can snap a click to a link
  links/<t>.json       per traced link: its length, the network length upstream of it, and its
                       upstream overflows as transport.upstream_overflows finds them, in a form
                       that gives the distance and dilution for a click anywhere along it
                       (`rows_at`), and for those whose water crosses a WFD lake on the way, the
                       metres of lake and the lake factor; a lake link points at its lake in lakes.json;
                       and `arms`: where a click on a small side arm goes (arm_heads)
  lakes.json           the WFD lake polygons (England) and every lake an overflow reaches: its
                       inlets, each with the overflows whose water enters there (river distance
                       and dilution before the lake-area term, and any WFD lake crossed before it)
  lake_outlines/<n>.json the real outline of the n-th WFD lake, which the page fetches when a click is
                       too near 150 m from the simplified outline in lakes.json to tell
  lake_water/<n>.json  lake distance "water": the water of the n-th lake in lakes.json's lakes, and the way
                       from each of its inlets into it, which the page fetches for a click placed on that lake
  outside_england.json Wales, Scotland and the island of Ireland, widened over their estuaries, where a
                       click gets "England only", and which part of the island is Northern Ireland (a
                       copy of data/raw/outside_england.json, scripts/make_outside_england.py)

A click is placed as transport._locate places it: inside or within 150 m of a WFD lake polygon it
is that lake (one with no lake centreline inside takes the centreline nearest the click within
1.5 km, as _in_polygon does); otherwise the nearest link within 1.5 km, or the nearest lake
centreline when that is less than twice as far; a click on a side channel near a much bigger
river is traced as that river (_adopt_main_channel, which the page applies with each link's
upstream network length from the index), and then, as a listed spot on a side arm is, to the river
the arm leaves, where the arm begins (transport._click_at_head; the page reads it from `arms`, as it
cannot walk the network). River distances and dilutions then follow upstream_overflows exactly for
the click's position along the link. A WFD lake between an overflow and the click is crossed as
upstream_overflows crosses it in config.LAKE_PATH_MODE "lake": its metres at the lake velocity, and the
dilution times 1 / (1 + area / 5 km2) for each such lake (lake_crossings). In lake paths "residence"
(docs/LAKE-RESIDENCE-TEST-2026-10.md) and "residence_spill" (the default,
docs/LAKE-RESIDENCE-SPILL-2026-10.md: the residence time at spill-day flow) a lake with a residence time is
crossed as a well-mixed lake instead: the records carry, per overflow, its metres, the survivors' hours
in it and the share that leaves it alive ("h"), and its area factor is left out of the path factor.
In lake distance "water" (the default, docs/LAKE-DISTANCE-2026-10.md) a lake click's distance from each inlet
is the shortest way through the lake's water (model/lake_water.py): lake_water/<n>.json carries the lake's water (its
reflex corners and outlines) and, per inlet, where it enters the water and the metres on to every corner (ways), and
the lake in lakes.json says it has one (water: true). Lake distance "line" writes none.

The upstream lists depend on the network, on where each overflow sits on it and on the transport
rule. They are cached in the state directory keyed by the network and lakes files' hashes, what the
network's load mended (RiverNetwork.topology_key), the lake path mode and CACHE_VERSION; when
overflows are added, removed or moved, only the links downstream of them (within
config.MAX_UPSTREAM_KM) are traced again. A new key traces everything again.

Rain: every overflow's cell (about 1,590) against the spots' 330. Open-Meteo stopped answering
this build after 600 locations in a minute (3 Oct 2026), so each build fetches at most
RAIN_CELLS_PER_BUILD of the oldest cells and uses cached ones up to RAIN_MAX_AGE_H old; an
overflow without either has no rain data, which the page shows as no data, as for a spot. A cell
is asked for again only once its cached forecast is RAIN_REFRESH_H old, however many builds run:
with a 1-hour floor, builds every 30 minutes would have asked for 300 cells each time, 14,400
Open-Meteo calls a day, more than the free 10,000 alone. At 12 hours the 1,270 cells the spots do
not share cost about 2,540 a day.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import pickle
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd
import shapely

from dipcast import config
from dipcast.model import lake_water, transport
from dipcast.model.forecast import day_grid
from dipcast.model.transport import (
    ADOPT_MIN_M,
    ADOPT_RADIUS_M,
    ADOPT_RATIO,
    L0_M,
    LAKE_A0_KM2,
    LAKE_SHORE_M,
    LAKE_SNAP_M,
    LOW_CONFIDENCE_FACTOR,
    PIN_SNAP_M,
    RIVER_FORMS,
    history_days,
    live_now_risk,
    river_velocity,
    running,
    upstream_lengths,
)
from dipcast.network.rivers import _TO_WGS, RiverNetwork, Snap

log = logging.getLogger("build_any_point")

TILE_DEG = 0.25           # squares of 0.25 degrees: about 28 km north-south, 17 km east-west
LAKE_SIMPLIFY_M = 15.0    # lake outlines in lakes.json; the shore rule is 150 m. Each carries how far it is from
                          # the real outline (err), and the page fetches the real one (lake_outlines/) when that matters
OUTLINE_DP = 6            # decimals of the real outlines: 0.1 m
WATER_INSIDE_M = 1.0      # lake distance "water": the widened outline a straight way must stay in, simplified
DAYS_AHEAD = 4            # today and four more, as forecast_point
DIL_SCALE = 10_000        # dilutions and dilution ratios in ten-thousandths
PATH_SCALE = 1_000_000    # the lake factor of lakes crossed on the way, in millionths
HOLD_SCALE = 1_000        # lake path "residence": survivors' hours in thousandths
PASS_SCALE = 1_000_000_000   # ... and the share that leaves alive in billionths (Windermere's chain is ~1e-6)
BASE_UNIT_M = 10          # base distances in links/<t>.json, in tens of metres
P_SCALE = 1_000           # probabilities and live weights in thousandths (three decimals)
# How long after a spill's end its hours are published (ended_h): the 48 h window plus a week, longer
# than any travel time to a click (60 km of river is 33 h; across Windermere, 17 km, another 94 h).
ENDED_KEEP_H = config.RECENT_SPILL_HOURS + 7 * 24
FORMS = ["inlandRiver", "tidalRiver", "lake", "canal"]
INDEX_MAGIC = 0x494C5353  # "SSLI" read as a little-endian Int32
INDEX_VERSION = 1
CACHE_NAME = "anypoint_links.pkl"
CACHE_VERSION = 8         # bump when the table's rules change (6: lakes crossed on the way; 7: the network
                          # mended at load, dipcast.network.fixes, and keyed by RiverNetwork.topology_key;
                          # 8: no centreline for a WFD lake with none inside)
OUT = "anypoint"
OUTSIDE_ENGLAND = config.RAW / "outside_england.json"
RAIN_CELLS_PER_BUILD = int(os.environ.get("DIPCAST_ANYPOINT_RAIN_CELLS", "300"))
RAIN_MAX_AGE_H = 24.0
RAIN_REFRESH_H = 12.0   # a cell is asked for at most every 12 hours (module docstring, "Rain")


# ------------------------------------------------------------------ helpers
def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def tile_key(lat: float, lon: float) -> str:
    """The square a point is in, as '<row>_<col>' with row = floor(lat / 0.25), col = floor(lon / 0.25)."""
    return f"{math.floor(lat / TILE_DEG)}_{math.floor(lon / TILE_DEG)}"


def placements(ov: pd.DataFrame) -> pd.DataFrame:
    """Where each snapped overflow sits on the network, one row per site id, sorted by id. These
    are the only overflow fields an upstream list depends on."""
    p = ov[ov["link_id"].notna()].drop_duplicates("site_id").set_index("site_id")
    p = p[["link_id", "frac", "link_length", "start_node", "end_node"]].copy()
    p["frac"] = p["frac"].astype(float)
    p["link_length"] = p["link_length"].astype(float)
    return p.sort_index()


def reach_of(net: RiverNetwork, end_nodes, cap_m: float) -> set[str]:
    """Nodes within cap_m downstream of any of the given nodes: the trace roots whose upstream
    search (RiverNetwork.upstream_edges) can reach an overflow ending there."""
    out: set[str] = set()
    for e in pd.unique(pd.Series(list(end_nodes), dtype=object).dropna()):
        if e in net.graph:
            out.update(net.downstream_nodes(e, cap_m))
    return out


def link_names(net: RiverNetwork, lids) -> dict[str, str | None]:
    """transport._link_name for many links: the link's own name, else the first named link
    downstream within 12 steps, following the first successor at a fork."""
    links, g = net.links, net.graph
    names = dict(zip(links.index, links["watercourse_name"], strict=True))
    end = dict(zip(links.index, links["end_node"], strict=True))
    first_succ: dict[str, str | None] = {}

    def succ_link(node: str) -> str | None:
        if node not in first_succ:
            nxt = next(iter(g.successors(node)), None) if node in g else None
            first_succ[node] = None if nxt is None else g.edges[node, nxt]["link"]
        return first_succ[node]

    out = {}
    for lid in lids:
        cur, name = lid, None
        for _ in range(12):
            if cur is None or cur not in names:
                break
            n = names[cur]
            if isinstance(n, str) and n:
                name = n
                break
            cur = succ_link(end[cur])
        out[lid] = name
    return out


def arm_heads(net: RiverNetwork, lids) -> dict[str, dict[str, Snap | None]]:
    """transport._click_at_head for every click the page can make, as the page cannot walk the
    network: small river link (the arm) -> {main channel _adopt_main_channel could choose -> where the
    click goes, or None where it stays}. Only arms with a channel big enough for _adopt_main_channel
    within ADOPT_RADIUS_M of their head can move, and only to a channel it could choose for a click
    on them: within PIN_SNAP_M + ADOPT_RADIUS_M of the arm, and big enough. Each is asked with that
    channel's own name, as _click_at_head asks (transport.channel_words), and kept only above the floor
    against that channel (transport.keeps_river). Arms with no move are left out."""
    links = net.links
    up = links["start_node"].map(net.upstream_m).fillna(0.0)
    river = links["form"].isin(RIVER_FORMS)
    small = [l for l in lids if river.at[l] and up.at[l] < ADOPT_MIN_M]
    big = links.index[river & (up >= ADOPT_MIN_M)]
    if not small or not len(big):
        return {}
    bigs = links.loc[big]
    heads = shapely.points([transport._side_arm_head(net, l) for l in small])
    near_head = set(np.asarray(small)[np.unique(bigs.sindex.query(heads, predicate="dwithin", distance=ADOPT_RADIUS_M)[0])])
    out: dict[str, dict[str, Snap | None]] = {}
    words_of: dict[str, frozenset[str]] = {}
    for arm in sorted(near_head):
        floor = max(ADOPT_MIN_M, ADOPT_RATIO * up.at[arm])
        reach = bigs.index[bigs.sindex.query(links.at[arm, "geometry"], predicate="dwithin", distance=PIN_SNAP_M + ADOPT_RADIUS_M)]
        asked: dict[frozenset[str], Snap | None] = {frozenset(): None}
        moves: dict[str, Snap | None] = {}
        for ch in sorted(reach):
            if up.at[ch] < floor:
                continue
            if ch not in words_of:
                words_of[ch] = transport.channel_words(net, ch)
            want = words_of[ch]
            if want not in asked:
                asked[want] = transport.head_of_arm(net, arm, want)
            moves[ch] = transport.keeps_river(net, asked[want], ch)   # the floor is against this channel
        if any(h is not None for h in moves.values()):
            out[arm] = moves
    return out


ARM_FRAC_SCALE = 10_000   # an arm's head along its main channel, in ten-thousandths (under a metre on a 10 km link)


def encode_arm(net: RiverNetwork, moves: dict[str, Snap | None], names: dict[str, str | None], lno_of: pd.Series,
               tiles_of: dict[str, list[str]], here: str) -> list:
    """An arm's moves (arm_heads) for links/<t>.json `arms`: one row per place a click can go,
    [link number, a square with its record (0: this one; null: none), fraction x ARM_FRAC_SCALE,
    metres from the arm's head, form as the index codes it, the channels that send a click there].
    The channels are given by the name the index gives them, which the page has for the channel it
    chose, where that settles it: every channel of a name goes to the same place, and none that moves
    is unnamed. Otherwise by link number. A row with no square ends with the link's name, which the
    page then cannot read from an index. `names`: link_names for every channel; `tiles_of`: the
    squares each link is in, sorted."""
    def place(h):
        return None if h is None else (h.link_id, round(h.frac * ARM_FRAC_SCALE), round(h.dist_m))
    by_name: dict[str | None, set] = {}
    for ch, h in moves.items():
        by_name.setdefault(names[ch], set()).add(place(h))
    by_number = any(len(v) > 1 for v in by_name.values()) or any(p is not None for p in by_name.get(None, ()))
    rows: dict[tuple, list] = {}
    form: dict[str, str] = {}
    for ch, h in sorted(moves.items()):
        p = place(h)
        if p is None:
            continue
        form[h.link_id] = h.form
        key = int(lno_of[ch]) if by_number else names[ch]
        if key not in rows.setdefault(p, []):
            rows[p].append(key)
    out = []
    for (lid, frac, dist), keys in sorted(rows.items()):
        sq = tiles_of.get(lid, [])
        row = [int(lno_of[lid]), 0 if here in sq else (sq[0] if sq else None), frac, dist, FORMS.index(form[lid]), keys]
        out.append(row if sq else [*row, transport._link_name(net, lid)])
    return out


def lake_crossings(net: RiverNetwork) -> dict[str, tuple[int, float]] | None:
    """Every lake-form link in a WFD lake polygon: link -> (the lake's row, its area km2), as
    transport._wfd_lake_of gives it, for config.LAKE_PATH_MODE "lake" and "residence"; None in mode
    "river". Which polygon a link is in does not depend on the trace, so one map serves every root."""
    if config.LAKE_PATH_MODE not in ("lake", *config.RESIDENCE_MODES):
        return None
    links = net.links
    return transport._wfd_lake_of(net, list(links.index[links["form"] == "lake"]))


def _crossing(part: transport.PathLakes, area: dict[int, float], mixed: frozenset = frozenset()) -> tuple[float, float] | None:
    """(metres of WFD lake, the factor 1 / prod(1 + A / LAKE_A0_KM2)) for a path that crosses one, else None.
    The lakes in `mixed` (lake path "residence": those with a residence time) are left out of the factor."""
    if not part[2]:
        return None
    return part[0], 1.0 / transport._lake_divisor(part[2] - mixed, area)


def residence_lakes() -> dict[int, float]:
    """Lake path "residence": WFD lake row -> residence time (hours); empty in the other modes."""
    return transport.lake_residence_h(config.LAKE_PATH_MODE) if config.LAKE_PATH_MODE in config.RESIDENCE_MODES else {}


def _mixing(part: transport.PathLakes, tau: dict[int, float]) -> tuple[float, float, float] | None:
    """Lake path "residence", for a path walked with only the lakes that have a residence time: (their metres, the
    survivors' hours in them, the share that leaves them alive), as transport._put_residence; None if it crosses none."""
    if not part[2]:
        return None
    return (part[0], float(sum(transport.lake_hold_h(tau[k]) for k in part[2])),
            float(np.prod([transport.lake_pass(tau[k]) for k in sorted(part[2])])))


class Tracer:
    """The river branch of transport.upstream_overflows, kept open in the click's position. For a
    link T traced from its start node (the root) and a click at fraction f along it,
    upstream_overflows gives, with offset = f x length(T):

      another link's overflow: distance = (1 - frac) x link length + network distance from that
                               link's end to the root + offset, kept if within the cap;
                               dilution = min(1, (L_up(overflow) + L0) / (L_up(root) + offset + L0))
      an overflow on T itself, above the click (frac < f): distance = (f - frac) x length(T),
                               dilution as above with L_up(overflow) = L_up(root)

    where L_up is the exact upstream network length within the root's capped search
    (upstream_lengths). L_up(overflow) is part of L_up(root), so the dilution is
    r x (L_up(root) + L0) / (L_up(root) + L0 + offset) with r = (L_up(overflow) + L0) / (L_up(root) + L0),
    at most 1. A link's record is its length, L_up(root), and per overflow either (base distance,
    r) or its position along T; `rows_at` turns that into upstream_overflows' rows for any f. One search per
    root, and L_up only for the nodes a dilution needs: calling upstream_overflows per link would
    take over 12 minutes (measured on 3 Oct 2026).

    With `crossings` (lake_crossings), an overflow whose water crosses a WFD lake on the way to the
    root also gets (metres of lake, lake factor) in the record's "path": the page moves those metres
    from the river distance to the lake distance and multiplies the dilution by the factor, as
    upstream_overflows does. Only roots with such a lake upstream walk the network a second time.
    With `tau` (lake path "residence"), an overflow whose water crosses a lake with a residence time also
    gets (its metres, hours, share alive) in "hold", and that lake's area is left out of the path factor."""

    def __init__(self, net: RiverNetwork, ov: pd.DataFrame, cap_m: float = config.MAX_UPSTREAM_KM * 1000.0,
                 crossings: dict[str, tuple[int, float]] | None = None, tau: dict[int, float] | None = None):
        self.net, self.g, self.cap = net, net.graph, cap_m
        self.crossings = crossings or {}
        self.tau = tau or {}
        self.length = dict(zip(net.links.index, net.links["length"].astype(float), strict=True))
        self.length.update(net.repairs)
        self.by_link: dict[str, list] = {}
        for r in ov.itertuples(index=False):
            self.by_link.setdefault(r.link_id, []).append((r.site_id, float(r.frac), float(r.link_length), r.start_node))

    def records(self, root: str, targets: list[str]) -> dict[str, dict]:
        """{link: {"lup", "len", "other": [(site_id, base_m, r)], "same": [(site_id, pos_m)]}, and
        "path": {site_id: (lake_m, factor)} where an overflow's water crosses a WFD lake} for links
        whose trace starts at `root`."""
        link_dist = self.net.upstream_edges(root, self.cap)
        lake_of = {lid: self.crossings[lid] for lid in link_dist if lid in self.crossings}
        length_of = {lid: self.length[lid] for lid in link_dist}
        graph, memo = self.g, {}

        def total(n: str) -> float:   # upstream_lengths' total(), for one node
            if n not in memo:
                seen: set[str] = set()
                stack = [n]
                while stack:
                    m = stack.pop()
                    for p in graph.predecessors(m):
                        lid = graph.edges[p, m]["link"]
                        if lid in length_of and lid not in seen:
                            seen.add(lid)
                            stack.append(p)
                memo[n] = float(sum(length_of[l] for l in seen))
            return memo[n]

        upstream = [(lid, d0, self.by_link[lid]) for lid, d0 in link_dist.items() if lid in self.by_link]
        path: dict[str, tuple[float, float]] = {}
        hold: dict[str, tuple[float, float, float]] = {}
        if lake_of:   # transport.upstream_overflows' river branch in lake path "lake" (or "residence")
            below = transport._path_lakes(self.net, root, self.cap, lake_of)
            area = {k: a for k, a in lake_of.values()}
            res_of = {lid: v for lid, v in lake_of.items() if v[0] in self.tau}
            below_res = transport._path_lakes(self.net, root, self.cap, res_of) if res_of else {}
            mixed = frozenset(k for k, _ in res_of.values())
            for lid, _, ovs in upstream:
                for sid, f, ll, _ in ovs:
                    part = transport._with_lake(below.get(lid, transport.NO_LAKES), lake_of.get(lid), (1.0 - f) * ll, 1.0)
                    c = _crossing(part, area, mixed)
                    if c is not None:
                        path[sid] = c
                    if res_of:
                        m = _mixing(transport._with_lake(below_res.get(lid, transport.NO_LAKES), res_of.get(lid),
                                                         (1.0 - f) * ll, 1.0), self.tau)
                        if m is not None:
                            hold[sid] = m
        out = {}
        for t in targets:
            spot = total(root) + L0_M
            other = [(sid, (1.0 - f) * ll + d0, (total(sn) + L0_M) / spot) for lid, d0, ovs in upstream if lid != t
                     for sid, f, ll, sn in ovs]
            out[t] = {"lup": total(root), "len": self.length[t],
                      "other": [r for r in other if r[1] <= self.cap],
                      "same": [(sid, f * ll) for sid, f, ll, _ in self.by_link.get(t, ())]}
            crossed = {r[0]: path[r[0]] for r in out[t]["other"] if r[0] in path}
            if crossed:
                out[t]["path"] = crossed
            mixed_here = {r[0]: hold[r[0]] for r in out[t]["other"] if r[0] in hold}
            if mixed_here:
                out[t]["hold"] = mixed_here
        return out


def rows_at(rec: dict, frac: float, cap_m: float = config.MAX_UPSTREAM_KM * 1000.0,
            power: float = transport.DILUTION_POWER) -> pd.DataFrame:
    """A link record's rows for a click at `frac` along the link: site_id, distance_m, lake_distance_m,
    dilution, as upstream_overflows computes them (the page's anypoint.js does the same), and res_m,
    hold_h and lake_pass (lake path "residence": the metres, survivors' hours and share alive of the
    lakes with a residence time; 0, 0 and 1 where none). The cap applies to the whole distance along
    the network; a WFD lake crossed on the way then moves its metres to the lake distance and
    multiplies the dilution by its factor. The capped length ratio is raised to `power`
    (transport.DILUTION_POWER) before that factor."""
    offset = frac * rec["len"]
    shrink = (rec["lup"] + L0_M) / (rec["lup"] + L0_M + offset)   # the click's own extra upstream length
    path, hold = rec.get("path", {}), rec.get("hold", {})
    rows = []
    for sid, base, r in rec["other"]:
        if base + offset <= cap_m:
            lake_m, factor = path.get(sid, (0.0, 1.0))
            rows.append((sid, base + offset - lake_m, lake_m, min(1.0, r * shrink) ** power * factor, *hold.get(sid, (0.0, 0.0, 1.0))))
    rows += [(sid, offset - pos, 0.0, min(1.0, shrink) ** power, 0.0, 0.0, 1.0) for sid, pos in rec["same"] if pos < offset]
    return pd.DataFrame(rows, columns=["site_id", "distance_m", "lake_distance_m", "dilution", "res_m", "hold_h", "lake_pass"])


# ------------------------------------------------------------------ lakes
def lake_link_sets(net: RiverNetwork, lakes) -> tuple[list[dict], dict[str, frozenset], dict[str, str]]:
    """(WFD lakes with the lake links transport._locate gives a click inside them, centreline
    lakes {id: links}, lake link -> centreline lake id). A WFD lake's links are the lake-form links
    crossing its polygon, else none. With none, transport._in_polygon takes the centreline lake
    nearest the click within 1.5 km, which the page finds in the link index (lake -1 in lakes.json).
    The one nearest the lake's middle would not be _in_polygon's (docs/ANYPOINT-LAKES-2026-10.md)."""
    links = net.links
    lake_links = links.index[links["form"] == "lake"]
    # Centreline lakes: lake links joined through shared nodes (RiverNetwork.lake_component).
    parent: dict[str, str] = {}

    def find(a: str) -> str:
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for lid in lake_links:
        s, e = links.at[lid, "start_node"], links.at[lid, "end_node"]
        parent[find(s)] = find(e)
    comps: dict[str, set] = {}
    for lid in lake_links:
        comps.setdefault(find(links.at[lid, "start_node"]), set()).add(lid)
    comp_sets = {f"c{i}": frozenset(v) for i, v in enumerate(sorted(comps.values(), key=lambda s: min(s)))}
    link_comp = {lid: cid for cid, s in comp_sets.items() for lid in s}
    wfd = []
    if lakes is not None and not lakes.empty:
        for _, poly in lakes.iterrows():
            idx = links.sindex.query(poly.geometry, predicate="intersects")
            cand = links.iloc[idx]
            ll = frozenset(cand.index[cand["form"] == "lake"])
            name = poly.get("lake_name")
            wfd.append({"wb_id": str(poly.get("wb_id") or ""), "name": str(name) if isinstance(name, str) else None,
                        "area_km2": float(poly["area_km2"]), "geometry": poly.geometry, "links": ll or None})
    return wfd, comp_sets, link_comp


def lake_rows(net: RiverNetwork, ov: pd.DataFrame, comp: frozenset, outlet: str,
              cap_m: float = config.MAX_UPSTREAM_KM * 1000.0,
              crossings: dict[str, tuple[int, float]] | None = None, tau: dict[int, float] | None = None) -> pd.DataFrame:
    """Overflows upstream of a lake's outlet that reach the lake: site_id, distance along the
    network to the lake (m), where the water enters the lake (BNG x, y), the dilution before the
    lake-area term, and the metres and factor of any other WFD lake crossed on the way (lake_m 0,
    factor 1 where none, or with no `crossings`), as the lake branch of transport.upstream_overflows
    computes them. The page takes lake_m off the river distance, adds it and the straight line from
    the entry to the click at the lake velocity, and multiplies by the factor and 1 / (1 + area / 5 km2).
    With `tau` (lake path "residence"): res_m, hold_h and lake_pass of the lakes on the way with a
    residence time (0, 0 and 1 where none), whose area is then left out of the factor."""
    cols = ["site_id", "distance_m", "entry_x", "entry_y", "dilution", "lake_m", "factor", "res_m", "hold_h", "lake_pass"]
    link_dist, lup = upstream_lengths(net, outlet, cap_m)
    on_path = set(link_dist)
    lake_of = {lid: v for lid, v in (crossings or {}).items() if lid in link_dist and lid not in comp}
    area = {k: a for k, a in lake_of.values()}
    tau = tau or {}
    res_of = {lid: v for lid, v in lake_of.items() if v[0] in tau}
    mixed = frozenset(k for k, _ in res_of.values())
    sub = ov[ov["link_id"].isin(on_path)]
    spot_lup = lup.get(outlet, 0.0)
    rows = []
    for r in sub.itertuples(index=False):
        res = transport._walk_to_lake(net, r.link_id, r.frac, set(comp), on_path, lake_of=lake_of)
        if res is None:
            continue
        d_river, (ex, ey), _, part = res
        if d_river > cap_m:
            continue
        ov_lup = lup.get(r.start_node, 0.0)
        lake_m, factor = _crossing(part, area, mixed) or (0.0, 1.0)
        mix = None
        if res_of:   # the same walk, with only the lakes that have a residence time (transport.upstream_overflows)
            mix = _mixing(transport._walk_to_lake(net, r.link_id, r.frac, set(comp), on_path, lake_of=res_of)[3], tau)
        rows.append((r.site_id, d_river, ex, ey, min(1.0, (ov_lup + L0_M) / (spot_lup + L0_M)), lake_m, factor,
                     *(mix or (0.0, 0.0, 1.0))))
    return pd.DataFrame(rows, columns=cols)


# ------------------------------------------------------------------ the cached table
def _net_key(net_hash: str, lakes_hash: str) -> dict:
    """What the cached upstream lists depend on besides the overflows: a change to any of it traces
    everything again. The lake path mode changes the rows' lake metres and factors; CACHE_VERSION
    changes with the code's rules."""
    key = {"version": CACHE_VERSION, "network": net_hash, "lakes": lakes_hash, "cap_km": config.MAX_UPSTREAM_KM,
           "l0_m": L0_M, "lake_path": config.LAKE_PATH_MODE, "lake_a0_km2": LAKE_A0_KM2}
    if config.LAKE_PATH_MODE in config.RESIDENCE_MODES:   # the residence times and T90 set the rows' holds
        f = config.LAKE_RESIDENCE_SPILL_FILE if config.LAKE_PATH_MODE == "residence_spill" else config.LAKE_RESIDENCE_FILE
        key["residence"] = hashlib.sha256(Path(f).read_bytes()).hexdigest()[:16]
        key["t90_h"] = config.T90_HOURS
    return key


def upstream_table(net: RiverNetwork, ov: pd.DataFrame, lakes, net_hash: str, lakes_hash: str = "",
                   cache_path: Path | None = None) -> tuple[dict, dict]:
    """The link records and lake inlets, from the cache where it still holds. Returns (table,
    stats). table: records {link: record}, wfd, comp_sets, link_comp, outlets, lake_rows {lake id:
    frame}, placements."""
    cap = config.MAX_UPSTREAM_KM * 1000.0
    stats: dict = {"cache": "cold"}
    key = _net_key(net_hash, lakes_hash)
    cached = None
    if cache_path is not None and cache_path.exists():
        try:
            cached = pickle.loads(cache_path.read_bytes())
            if cached.get("key") != key:
                old = cached.get("key") or {}
                stats["cache"] = ("stale network" if (old.get("network"), old.get("lakes")) != (key["network"], key["lakes"])
                                  else "stale rules")
                cached = None
        except Exception as e:  # noqa: BLE001 - a broken cache is rebuilt, never fatal
            log.warning("any-point cache unreadable, rebuilding: %s", e)
            cached = None
    place = placements(ov)
    ovp = place.reset_index()   # what upstream_overflows reads: site_id, link_id, frac, link_length, start_node
    links = net.links

    crossings = lake_crossings(net)
    tau = residence_lakes()
    if cached is None:
        t = time.time()
        wfd, comp_sets, link_comp = lake_link_sets(net, lakes)
        stats["network_s"] = round(time.time() - t, 1)
        log.info("any-point: %d WFD lakes, %d centreline lakes (%.0f s)", len(wfd), len(comp_sets), time.time() - t)
        table = {"key": key, "wfd": wfd, "comp_sets": comp_sets, "link_comp": link_comp,
                 "outlets": {}, "placements": place.iloc[0:0], "records": {}, "lake_rows": {}}
        todo_nodes = todo_links = None   # everything
    else:
        table = cached
        old = table["placements"]
        both = old.index.union(place.index)
        a = old.reindex(both)
        b = place.reindex(both)
        same = ((a == b) | (a.isna() & b.isna())).all(axis=1)
        changed = both[~same.to_numpy()]
        stats["cache"] = "warm" if len(changed) == 0 else f"{len(changed)} overflows changed"
        if len(changed) == 0:
            stats["traced_links"] = 0
            return table, stats
        moved = pd.concat([a.loc[changed], b.loc[changed]]).dropna(subset=["link_id"])
        todo_nodes = reach_of(net, moved["end_node"], cap)
        todo_links = set(moved["link_id"])

    # The links a river click can be traced along: every link but a lake's. One with an overflow
    # upstream gets a record.
    start = links["start_node"]
    targets = list(links.index[links["form"] != "lake"])
    reach = reach_of(net, place["end_node"], cap)
    ov_links = set(place["link_id"])
    if todo_nodes is None:
        redo = targets
    else:
        redo = [l for l in targets if start.at[l] in todo_nodes or l in todo_links]
    for l in redo:
        table["records"].pop(l, None)
    t = time.time()
    groups: dict[str, list] = {}
    for l in redo:
        s = start.at[l]
        if s in reach or l in ov_links:
            groups.setdefault(s, []).append(l)
    tracer = Tracer(net, ovp, cap, crossings, tau)
    for i, (root, ts) in enumerate(groups.items()):
        for l, rec in tracer.records(root, ts).items():
            if rec["other"] or rec["same"]:
                table["records"][l] = rec
        if (i + 1) % 10000 == 0:
            log.info("any-point: traced %d of %d roots (%.0f s)", i + 1, len(groups), time.time() - t)
    stats["traced_links"] = sum(len(v) for v in groups.values())
    stats["trace_s"] = round(time.time() - t, 1)

    # Lakes: every lake an overflow can reach is worked out again whenever any overflow changed
    # (a few hundred lakes, seconds). The outlet depends only on the network and is kept.
    t = time.time()
    sets = {f"w{i}": w["links"] for i, w in enumerate(table["wfd"]) if w["links"]}
    sets.update(table["comp_sets"])
    lake_out = {}
    for lake_id, comp in sets.items():
        nodes = {n for lid in comp for n in net.link_nodes(lid)}
        if not nodes & reach:
            continue
        if lake_id not in table["outlets"]:
            table["outlets"][lake_id] = transport._lake_outlet(net, set(comp))
        rows = lake_rows(net, ovp, comp, table["outlets"][lake_id], cap, crossings, tau)
        if len(rows):
            lake_out[lake_id] = rows
    table["lake_rows"] = lake_out
    stats["lake_s"] = round(time.time() - t, 1)
    table["placements"] = place
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(table, protocol=5))
        tmp.replace(cache_path)
    return table, stats


# ------------------------------------------------------------------ the files
def pack_link_index(lnos: np.ndarray, meta: np.ndarray, upstream: np.ndarray, offsets: np.ndarray,
                    lonlat: np.ndarray, names: list[str]) -> bytes:
    """One square's links, little-endian, every block 4-byte aligned:
      Int32[6]     magic "SSLI", version 1, n links, n vertices, bytes of names, 0
      Int32[n]     link number (its place in the network's links sorted by OS id)
      Int32[n]     form + 4 x (name + 1): form = meta & 3 (0 inland river, 1 tidal river, 2 lake,
                   3 canal), name = (meta >> 2) - 1, an index into the names, -1 for none
      Float32[n]   network length upstream of the link's start (m), RiverNetwork.upstream_m: the
                   page moves a click on a side channel to a much bigger river with it
      Int32[n + 1] where each link's vertices start; the last is the number of vertices
      Float32[2v]  longitude, latitude of each vertex, in order along the flow
      UTF-8        the names, as a JSON list
    """
    nb = json.dumps(names, ensure_ascii=False, separators=(",", ":")).encode()
    head = np.array([INDEX_MAGIC, INDEX_VERSION, len(lnos), len(lonlat), len(nb), 0], dtype="<i4")
    parts = [head, lnos.astype("<i4"), meta.astype("<i4"), upstream.astype("<f4"), offsets.astype("<i4"),
             lonlat.astype("<f4").ravel()]
    return b"".join(p.tobytes() for p in parts) + nb


def unpack_link_index(buf: bytes) -> dict:
    """The inverse of pack_link_index (for tests and checks)."""
    h = np.frombuffer(buf, dtype="<i4", count=6)
    assert h[0] == INDEX_MAGIC and h[1] == INDEX_VERSION
    n, nv, nb = int(h[2]), int(h[3]), int(h[4])
    off = 24
    out = {}
    for k, cnt, dt in (("lno", n, "<i4"), ("meta", n, "<i4"), ("upstream", n, "<f4"), ("offsets", n + 1, "<i4")):
        out[k] = np.frombuffer(buf, dtype=dt, count=cnt, offset=off)
        off += 4 * cnt
    out["form"] = out["meta"] & 3
    out["name"] = (out["meta"] >> 2) - 1
    out["lonlat"] = np.frombuffer(buf, dtype="<f4", count=2 * nv, offset=off).reshape(-1, 2)
    off += 8 * nv
    out["names"] = json.loads(buf[off:off + nb].decode())
    return out


def encode_record(rec: dict, pos: dict[str, int]) -> dict:
    """A link record for links/<t>.json: n its length (m), u the network length upstream of its start
    (m), o flat triples (overflow index as the difference from the previous one, the indices
    ascending; base distance in tens of metres; r in ten-thousandths), s flat pairs (overflow index,
    position along the link in m) for the overflows on the link itself, and k flat triples (overflow
    index, metres of WFD lake crossed on the way, lake factor in millionths) for the overflows in o
    whose water crosses one (lake path "lake" and "residence"), and h flat quadruples (overflow index,
    metres of lake with a residence time, the survivors' hours in thousandths, the share alive in
    billionths) for those whose water crosses such a lake (lake path "residence" only)."""
    o, last = [], 0
    for i, base, r in sorted((pos[sid], base, r) for sid, base, r in rec["other"]):
        o += [i - last, round(float(base) / BASE_UNIT_M), round(float(r) * DIL_SCALE)]
        last = i
    s = []
    for i, p in sorted((pos[sid], p) for sid, p in rec["same"]):
        s += [i, round(float(p))]
    k = []
    for i, (m, f) in sorted((pos[sid], c) for sid, c in rec.get("path", {}).items()):
        k += [i, round(float(m)), round(float(f) * PATH_SCALE)]
    h = []
    for i, (m, hh, ps) in sorted((pos[sid], c) for sid, c in rec.get("hold", {}).items()):
        h += [i, round(float(m)), round(float(hh) * HOLD_SCALE), round(float(ps) * PASS_SCALE)]
    return {"n": round(float(rec["len"])), "u": round(float(rec["lup"])), "o": o, **({"s": s} if s else {}),
            **({"k": k} if k else {}), **({"h": h} if h else {})}


def decode_record(entry: dict, ids: list[str]) -> dict:
    """A links/<t>.json record back into the form rows_at takes (for tests and checks)."""
    o = np.asarray(entry.get("o", []), dtype=float).reshape(-1, 3)
    s = np.asarray(entry.get("s", []), dtype=float).reshape(-1, 2)
    k = np.asarray(entry.get("k", []), dtype=float).reshape(-1, 3)
    h = np.asarray(entry.get("h", []), dtype=float).reshape(-1, 4)
    idx = np.cumsum(o[:, 0]).astype(int) if len(o) else []
    return {"len": entry["n"], "lup": entry["u"],
            "other": [(ids[i], b * BASE_UNIT_M, r / DIL_SCALE) for i, (_, b, r) in zip(idx, o, strict=True)],
            "same": [(ids[int(i)], p) for i, p in s],
            **({"path": {ids[int(i)]: (m, f / PATH_SCALE) for i, m, f in k}} if len(k) else {}),
            **({"hold": {ids[int(i)]: (m, hh / HOLD_SCALE, ps / PASS_SCALE) for i, m, hh, ps in h}} if len(h) else {})}


def _to_lonlat(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lon, lat = _TO_WGS.transform(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return np.asarray(lon), np.asarray(lat)


def _tiles_of_bounds(b: np.ndarray) -> list[list[str]]:
    """Squares each lon/lat bounding box (minx, miny, maxx, maxy) touches."""
    out = []
    for x0, y0, x1, y1 in b:
        r0, r1 = math.floor(y0 / TILE_DEG), math.floor(y1 / TILE_DEG)
        c0, c1 = math.floor(x0 / TILE_DEG), math.floor(x1 / TILE_DEG)
        out.append([f"{r}_{c}" for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)])
    return out


def ids_version(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(ids).encode()).hexdigest()[:12]


def _water_json(w) -> dict:
    """A lake's water (lake distance "water") as the page reads it, in lon/lat to six decimals."""
    def rings(g, tol=0.0) -> list:
        g = shapely.simplify(g, tol) if tol else g
        out = []
        for part in getattr(g, "geoms", [g]):
            for ring in [part.exterior, *part.interiors]:
                x, y = np.asarray(ring.coords)[:, :2].T
                rlon, rlat = _to_lonlat(x, y)
                out.append(np.round(np.column_stack([rlon, rlat]), 6).tolist())
        return out
    clon, clat = _to_lonlat(w.xy[:, 0], w.xy[:, 1]) if len(w.xy) else (np.zeros(0), np.zeros(0))
    return {"corners": np.round(np.column_stack([clon, clat]), 6).tolist(), "inside": rings(w.test, WATER_INSIDE_M),
            "shore": rings(w.region)}


def write_files(out: Path, net: RiverNetwork, ov: pd.DataFrame, table: dict, net_hash: str,
                credits: dict | None = None) -> dict:
    """Every file except overflow_days.json and tiles.json. Returns {ids, ids_version, tiles,
    past_days, counts}."""
    links = net.links
    place = table["placements"]
    ids = list(place.index)
    pos = {s: i for i, s in enumerate(ids)}
    idv = ids_version(ids)
    lno_of = pd.Series(np.arange(len(links), dtype=np.int64), index=links.index.sort_values())
    records = table["records"]

    # Squares with data: any with an overflow, any with a link that has one upstream.
    ovl = ov[ov["site_id"].isin(pos)].drop_duplicates("site_id").set_index("site_id").loc[ids]
    covered = {tile_key(a, b) for a, b in zip(ovl["lat"], ovl["lon"], strict=True)}
    mids = shapely.line_interpolate_point(links.geometry.values, 0.5, normalized=True)
    mlon, mlat = _to_lonlat(shapely.get_x(mids), shapely.get_y(mids))
    home = pd.Series([tile_key(a, b) for a, b in zip(mlat, mlon, strict=True)], index=links.index)
    lake_ids = sorted(table["lake_rows"], key=lambda k: (k[0], int(k[1:])))
    lake_pos = {k: i for i, k in enumerate(lake_ids)}
    entry_links = set(records) | {l for l, c in table["link_comp"].items() if c in lake_pos}
    covered |= set(home.loc[list(entry_links)])

    # Lines in lon/lat, every vertex the network has, and every square each line's box touches. Lines
    # simplified to 30 m sit up to 30 m from the network's own: a click on a short side link 0.001 m from
    # it was 24 m from its simplified line, so the page took a lake centreline 35 m away and found no
    # river, where forecast_point traced the River Stor (docs/ANYPOINT-LINES-2026-10.md). The full lines
    # add about 5.7 MB, most of it link_index/.
    coords, which = shapely.get_coordinates(links.geometry.values, return_index=True)
    lon, lat = _to_lonlat(coords[:, 0], coords[:, 1])
    lonlat = np.column_stack([lon, lat])
    starts = np.searchsorted(which, np.arange(len(links) + 1))
    bounds = np.column_stack([np.minimum.reduceat(lon, starts[:-1]), np.minimum.reduceat(lat, starts[:-1]),
                              np.maximum.reduceat(lon, starts[:-1]), np.maximum.reduceat(lat, starts[:-1])])
    # A click by a WFD lake with no lake link inside takes the lake link nearest it within 1.5 km
    # (transport._in_polygon). The page finds it in the link index, so every square such a link touches has files.
    no_line = [w["geometry"] for w in table["wfd"] if not w["links"]]
    if no_line:
        lake_pos_ix = np.flatnonzero((links["form"] == "lake").to_numpy())
        near = links.iloc[lake_pos_ix].sindex.query(shapely.buffer(no_line, LAKE_SHORE_M + LAKE_SNAP_M), predicate="intersects")[1]
        for ts in _tiles_of_bounds(bounds[lake_pos_ix[np.unique(near)]]):
            covered.update(ts)
    by_tile: dict[str, list[int]] = {}
    for i, ts in enumerate(_tiles_of_bounds(bounds)):
        for t in ts:
            if t in covered:
                by_tile.setdefault(t, []).append(i)

    form_code = links["form"].map({f: i for i, f in enumerate(FORMS)}).fillna(0).astype(int).to_numpy()
    lids = links.index.to_numpy()
    own_name = links["watercourse_name"].to_numpy()
    in_tiles = sorted({i for ix in by_tile.values() for i in ix})
    river_names = link_names(net, [lids[i] for i in in_tiles if form_code[i] != 2])
    upstream = links["start_node"].map(net.upstream_m).fillna(0.0).to_numpy()
    name_of = {}   # by position
    for i in in_tiles:
        if form_code[i] == 2:   # a lake click keeps the lake's own name, never the outflow's
            n = own_name[i]
            name_of[i] = n if isinstance(n, str) and n else None
        else:
            name_of[i] = river_names[lids[i]]
    # Side arms: where a click on one goes (arm_heads, encode_arm), in each square the arm is in.
    arms = arm_heads(net, [lids[i] for i in in_tiles])
    tiles_of: dict[str, list[str]] = {}
    for t, ix in sorted(by_tile.items()):
        for i in ix:
            tiles_of.setdefault(lids[i], []).append(t)
    arm_names = link_names(net, sorted({ch for moves in arms.values() for ch in moves}))

    for d in ("link_index", "links"):
        (out / d).mkdir(parents=True, exist_ok=True)
        for f in (out / d).iterdir():
            f.unlink()
    n_rows = n_entries = 0
    for t, ix in sorted(by_tile.items()):
        ix = np.asarray(ix)
        names: list[str] = []
        npos: dict[str, int] = {}
        meta = []
        for i in ix:
            n = name_of[i]
            if n is not None and n not in npos:
                npos[n] = len(names)
                names.append(n)
            meta.append(form_code[i] + 4 * (npos[n] + 1 if n is not None else 0))
        seg = [lonlat[starts[i]:starts[i + 1]] for i in ix]
        offsets = np.concatenate([[0], np.cumsum([len(s) for s in seg])])
        lnos = lno_of.loc[lids[ix]].to_numpy()
        (out / "link_index" / f"{t}.bin").write_bytes(
            pack_link_index(lnos, np.asarray(meta), upstream[ix], offsets, np.concatenate(seg), names))
        entries, arms_here = {}, {}
        for i, lno in zip(ix, lnos, strict=True):
            lid = lids[i]
            if lid in arms:
                arms_here[str(int(lno))] = encode_arm(net, arms[lid], arm_names, lno_of, tiles_of, t)
            if form_code[i] == 2:
                c = table["link_comp"].get(lid)
                if c in lake_pos:
                    entries[str(int(lno))] = {"lake": lake_pos[c]}
            elif lid in records:
                entries[str(int(lno))] = encode_record(records[lid], pos)
                n_rows += len(records[lid]["other"]) + len(records[lid]["same"])
        n_entries += len(entries)
        (out / "links" / f"{t}.json").write_text(json.dumps(
            {"ids": idv, "network": net_hash, **({"credits": credits["full"]} if credits and "full" in credits else {}), "links": entries,
             **({"arms": arms_here} if arms_here else {})}, separators=(",", ":")))

    # Lakes. The longest travel a click can have sets how many past days of spill probabilities the
    # page may need (transport.history_days): 60 km of river, or, where an overflow's water crosses a
    # WFD lake on the way, up to 60 km with that lake's metres at the lake velocity.
    cap = config.MAX_UPSTREAM_KM * 1000.0
    v, v_lake = river_velocity(None), config.LAKE_VELOCITY_MS
    crossed = max((m for rec in records.values() for m, _ in rec.get("path", {}).values()), default=0.0)
    held = max((hh for rec in records.values() for _, hh, _ in rec.get("hold", {}).values()), default=0.0)
    past = history_days(np.array([((cap - crossed) / v + crossed / v_lake) / 3600.0 + held]))   # held: an upper bound
    lakes_json = []
    (out / "lake_water").mkdir(parents=True, exist_ok=True)
    for f in (out / "lake_water").iterdir():
        f.unlink()
    for k in lake_ids:
        r = table["lake_rows"][k]
        r = r[[sid in pos for sid in r["site_id"]]].copy()
        elon, elat = _to_lonlat(r["entry_x"].to_numpy(), r["entry_y"].to_numpy())
        r["lon"], r["lat"] = np.round(elon, 5), np.round(elat, 5)
        if "lake_m" not in r:   # rows from before lakes crossed on the way
            r["lake_m"], r["factor"] = 0.0, 1.0
        if "res_m" not in r:    # rows from before lake path "residence"
            r["res_m"], r["hold_h"], r["lake_pass"] = 0.0, 0.0, 1.0
        comp = table["wfd"][int(k[1:])]["links"] if k.startswith("w") else table["comp_sets"][k]
        # Lake distance "water": the lake's water, and from each inlet its way into it and to every corner.
        water = transport.links_water(net, comp) if config.LAKE_DISTANCE_MODE == "water" and comp else None
        far_via = 0.0
        inlets, ways = [], []
        # Lake direction (docs/LAKE-DIRECTION-TEST-2026-10.md): where the lake's water leaves it, and each inlet's
        # metres to there (through the water, else the straight line), as transport.down_lake_m measures them.
        out_xy = transport.lake_outlet_xy(net, set(comp)) if comp else None

        def to_outlet(x: float, y: float, water=water, out_xy=out_xy) -> float:
            d = lake_water.water_distance(water, x, y, *out_xy) if water is not None else math.inf
            return d if math.isfinite(d) else math.hypot(x - out_xy[0], y - out_xy[1])

        for (a, b), g in r.groupby(["lon", "lat"], sort=True):
            flat, cross, mix = [], [], []
            for s, d, w, m, f, rm, hh, ps in zip(g["site_id"], g["distance_m"], g["dilution"], g["lake_m"], g["factor"],
                                                 g["res_m"], g["hold_h"], g["lake_pass"], strict=True):
                flat += [pos[s], round(float(d)), round(float(w) * DIL_SCALE)]
                if m > 0:
                    cross += [pos[s], round(float(m)), round(float(f) * PATH_SCALE)]
                if hh > 0:
                    mix += [pos[s], round(float(rm)), round(float(hh) * HOLD_SCALE), round(float(ps) * PASS_SCALE)]
            way = None
            if water is not None:
                px, py, leg, via = lake_water.from_point(water, float(g["entry_x"].iloc[0]), float(g["entry_y"].iloc[0]))
                (plon,), (plat,) = _to_lonlat(np.array([px]), np.array([py]))
                way = [round(float(plon), 6), round(float(plat), 6), round(leg, 1),
                       *[round(float(v)) if np.isfinite(v) else -1 for v in via]]
                far_via = max(far_via, float(np.max(via[np.isfinite(via)], initial=0.0)))
            ways.append(way)
            dn = {"dn": round(to_outlet(float(g["entry_x"].iloc[0]), float(g["entry_y"].iloc[0])))} if out_xy else {}
            inlets.append({"at": [float(a), float(b)], "o": flat, **({"k": cross} if cross else {}), **({"h": mix} if mix else {}),
                           **dn})
        # The furthest a click in this lake can be from an inlet: across the lake's box, plus the
        # shore rule (WFD lakes) or the snap radius (centreline lakes). It sets how many past days
        # of spill probabilities the page may need (transport.history_days).
        if k.startswith("w"):
            x0, y0, x1, y1 = table["wfd"][int(k[1:])]["geometry"].bounds
            pad = LAKE_SHORE_M
        else:
            x0, y0, x1, y1 = shapely.total_bounds(links.loc[list(comp), "geometry"].values)
            pad = PIN_SNAP_M
        if len(r):
            far = max(math.hypot(max(abs(ex - x0), abs(ex - x1)) + pad, max(abs(ey - y0), abs(ey - y1)) + pad)
                      for ex, ey in zip(r["entry_x"], r["entry_y"], strict=True))
            if water is not None:   # round the bends: to a corner, then across the box
                far = max(far, far_via + math.hypot(x1 - x0, y1 - y0) + pad)
            travel = float(((r["distance_m"] - r["lake_m"]) / v + (far + r["lake_m"]) / v_lake).max()) / 3600.0
            travel += float(r["hold_h"].max())   # lake path "residence": an upper bound
            past = max(past, history_days(np.array([travel])))
        name = None
        if k.startswith("c"):
            own = [own_name[j] for j in sorted(links.index.get_indexer(list(comp)))]
            name = next((n for n in own if isinstance(n, str) and n), None)
        outlet, out_way = {}, {}
        if out_xy:
            (olon,), (olat,) = _to_lonlat(np.array([out_xy[0]]), np.array([out_xy[1]]))
            outlet = {"out": [round(float(olon), 6), round(float(olat), 6)]}
            if water is not None:
                px, py, leg, via = lake_water.from_point(water, *out_xy)
                (plon,), (plat,) = _to_lonlat(np.array([px]), np.array([py]))
                out_way = {"outlet": [round(float(plon), 6), round(float(plat), 6), round(leg, 1),
                                      *[round(float(v)) if np.isfinite(v) else -1 for v in via]]}
        lakes_json.append({"id": k, "name": name, "inlets": inlets, **({"water": True} if water is not None else {}), **outlet})
        if water is not None:
            (out / "lake_water" / f"{lake_pos[k]}.json").write_text(json.dumps(
                {"ids": idv, **_water_json(water), "ways": ways, **out_way}, separators=(",", ":")))
    # WFD lake outlines (exterior rings: no island has a point more than 150 m from its water). lakes.json has
    # them simplified to LAKE_SIMPLIFY_M, with err, the most they are off by; lake_outlines/<n>.json has the real ones.
    def rings_of(g, dp: int) -> list:
        rings = []
        for part in getattr(g, "geoms", [g]):
            x, y = np.asarray(part.exterior.coords).T
            plon, plat = _to_lonlat(x, y)
            rings.append(np.round(np.column_stack([plon, plat]), dp).tolist())
        return rings

    def exteriors(g):
        return shapely.MultiLineString([p.exterior for p in getattr(g, "geoms", [g])])

    (out / "lake_outlines").mkdir(parents=True, exist_ok=True)
    for f in (out / "lake_outlines").iterdir():
        f.unlink()
    polys = []
    for i, w in enumerate(table["wfd"]):
        g = shapely.simplify(w["geometry"], LAKE_SIMPLIFY_M)
        rings = rings_of(g, 5)
        # Densified: the largest gap can be partway along a simplified segment. + 1 m: the 5 decimals.
        err = math.ceil(shapely.hausdorff_distance(exteriors(w["geometry"]), exteriors(g), densify=0.25) + 1.0)
        (out / "lake_outlines" / f"{i}.json").write_text(json.dumps(
            {"wb_id": w["wb_id"], **({"credits": credits["full"]} if credits and "full" in credits else {}),
             "rings": rings_of(w["geometry"], OUTLINE_DP)}, separators=(",", ":")))
        allc = np.concatenate([np.asarray(r) for r in rings])
        lake = f"w{i}"
        polys.append({"name": w["name"], "wb_id": w["wb_id"], "area_km2": round(w["area_km2"], 3),
                      "bbox": [float(allc[:, 0].min()), float(allc[:, 1].min()), float(allc[:, 0].max()), float(allc[:, 1].max())],
                      "lake": (lake_pos.get(lake) if w["links"] else -1), "err": err, "rings": rings})
    (out / "lakes.json").write_text(json.dumps({
        "ids": idv, "network": net_hash,
        "note": ("polygons: the Environment Agency's WFD lakes, outlines simplified to 15 m. err: the most, in metres, an "
                 "outline is off from the real one in lake_outlines/<place in polygons>.json. lake: index into lakes; null "
                 "when no monitored overflow upstream reaches it; -1 when no lake centreline is inside the lake: a click "
                 "there takes the lake centreline nearest it within lake_snap_m (link index), else it is isolated. lakes[].inlets: "
                 "where water enters the lake, and o = flat triples (overflow index, distance along the network m, "
                 "dilution x 10000 before dividing by 1 + area / 5 km2); k = flat triples (overflow index, metres of "
                 "another WFD lake crossed on the way, which travel at the lake velocity, lake factor x 1000000 to "
                 "multiply the dilution by) for the overflows in o whose water crosses one; h = flat quadruples (lake path "
                 "residence: overflow index, metres of those lakes with a residence time, which do not travel at the lake "
                 "velocity, survivors' hours in them x 1000 added to the travel time, share alive x 1000000000 to multiply "
                 "the die-off by). lakes[].water: true where lake_water/<place in lakes>.json has the lake's water (lake "
                 "distance water): corners, the reflex corners of the lake's water (model/lake_water.py); inside, its outline "
                 "widened by 10 m, which a straight way must stay in; shore, its outline, for a click outside it; ways, one per "
                 "inlet in order: where it enters the water (lon, lat), the metres to there, then the metres through the water "
                 "to each corner, -1 where none."),
        "polygons": polys, "lakes": lakes_json, **({"credits": credits} if credits else {})}, separators=(",", ":")))

    names = ovl["site_name"].where(ovl["site_name"].notna(), None) if "site_name" in ovl else pd.Series(None, index=ovl.index)
    (out / "overflow_ids.json").write_text(json.dumps({
        "ids_version": idv, "ids": ids, "name": [None if not isinstance(n, str) else n for n in names],
        "lon": [round(float(v), 4) for v in ovl["lon"]], "lat": [round(float(v), 4) for v in ovl["lat"]],
        **({"credits": credits} if credits else {})}, separators=(",", ":")))
    return {"ids": ids, "ids_version": idv, "tiles": sorted(by_tile), "past_days": int(past),
            "counts": {"links_indexed": len(in_tiles), "links_traced": len(records), "entries": n_entries, "arms": len(arms),
                       "rows": n_rows, "lakes_reached": len(lake_ids), "wfd_lakes": len(polys),
                       "wfd_no_centreline": sum(p["lake"] == -1 for p in polys)}}


# ------------------------------------------------------------------ rain and the days
def any_point_rain(sub: pd.DataFrame, budget: int = RAIN_CELLS_PER_BUILD,
                   max_age_h: float = RAIN_MAX_AGE_H, refresh_h: float = RAIN_REFRESH_H) -> tuple[pd.DataFrame, dict]:
    """Hourly rain for every overflow's cell: the cached forecast where it is under max_age_h old,
    after fetching the `budget` oldest cells that are due (`refresh_h` old, or never fetched). A
    failed fetch, or one the day's Open-Meteo ration has no room for, keeps what is cached; nothing
    here raises."""
    from dipcast.ingest import rainfall
    cells = rainfall.cells_for_sites(sub["lat"], sub["lon"])
    path = {c: rainfall.CACHE / f"forecast_{rainfall.cell_key(*c)}.parquet" for c in cells}

    def age(c) -> float:
        return time.time() - path[c].stat().st_mtime if path[c].exists() else math.inf

    due = sorted((c for c in cells if age(c) >= max(rainfall.FORECAST_TTL_S, refresh_h * 3600)), key=lambda c: -age(c))
    take = due[:max(0, budget)]
    error = None
    if take:
        seen = len(rainfall.fetch_errors())
        try:
            # One retry, after 1-2 s or a Retry-After of up to a minute. A failed request does not
            # raise or stop the later ones; its cells keep their cached forecast, read below.
            rainfall.fetch_forecast(take, attempts=2, what="anypoint")
        except Exception as e:  # noqa: BLE001 - what was fetched before the failure is kept
            error = str(e)
        error = error or next(iter(rainfall.fetch_errors()[seen:]), None)
        if error:
            log.warning("any-point rain: %s", error)
    frames = [pd.read_parquet(path[c]) for c in cells if age(c) <= max_age_h * 3600]
    cols = ["cell_lat", "cell_lon", "time", "precip_mm", "issued_at"]
    rain = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
    fetched = sum(1 for c in take if age(c) < rainfall.FORECAST_TTL_S)
    return rain, {"cells": len(cells), "due": len(due), "fetched": fetched, "usable": len(frames),
                  "calls": rainfall.forecast_weight(fetched), **({"error": error} if error else {})}


def cell_rain_48h(hourly: pd.DataFrame, days: pd.DatetimeIndex) -> dict[str, list]:
    """Each rain square's rain in the 48 h to midday, local time, on each of `days`, in mm to one
    decimal: the figure a listed spot's day rows show (forecast.py, rain_48h_mm, by ecoli.rain_windows,
    with its rule for missing hours: None where under 90% of them have a value). Keyed "lat,lon" by
    the square's centre. A click with no overflow upstream has only rain to show (anypoint.js, rainAt)."""
    from dipcast.model import ecoli
    if not len(hourly):
        return {}
    days = pd.DatetimeIndex(days)
    days = days.tz_localize("Europe/London") if days.tz is None else days.tz_convert("Europe/London")
    ends = days + pd.Timedelta(hours=ecoli.SAMPLE_HOUR)
    out = {}
    for (a, b), g in hourly.groupby(["cell_lat", "cell_lon"]):
        series = pd.Series(g["precip_mm"].to_numpy(dtype=float),
                           index=pd.to_datetime(g["time"], utc=True).dt.tz_convert("Europe/London"))
        r48, _ = ecoli.rain_windows(series, ends)
        out[f"{float(a) + 0.0:.1f},{float(b) + 0.0:.1f}"] = [None if np.isnan(v) else round(float(v), 1) for v in r48]
    return out


def write_overflow_days(out: Path, ov: pd.DataFrame, ids: list[str], idv: str, past: int, now: pd.Timestamp,
                        probabilities, credits: dict | None = None, rain=any_point_rain) -> dict:
    """overflow_days.json. `probabilities(ov, days, rain)` is forecast.spill_probabilities with the
    model bound, the same call the spots use, given the rain from `rain(ov)`."""
    sub = ov.drop_duplicates("site_id").set_index("site_id").loc[ids].reset_index()
    # Calendar days, as the spots count them: 48 h back from the midnight after the clocks go back is 01:00
    # on the repeated hour, which pandas cannot place, so no click-anywhere file was written from 25 Oct 2026.
    days = day_grid(now, past, DAYS_AHEAD)
    hourly, rstats = rain(sub)
    if len(hourly):
        p, ok = probabilities(sub, days, hourly)
        p = np.where(ok, p, np.nan)
    else:   # no cell has rain: every probability is unknown
        p = np.full((len(sub), len(days)), np.nan)
    # How old each overflow's rain forecast is, in hours, where it has one.
    from dipcast.ingest.rainfall import grid_cell
    issued = {}
    if len(hourly) and "issued_at" in hourly:
        got = hourly.groupby(["cell_lat", "cell_lon"])["issued_at"].max()
        issued = {k: pd.Timestamp(v) for k, v in got.items()}
    cl, cn = grid_cell(sub["lat"].to_numpy(), sub["lon"].to_numpy())
    rain_h = []
    for a, b in zip(cl, cn, strict=True):
        t = issued.get((float(a), float(b)))
        rain_h.append(None if t is None or pd.isna(t) else max(0, int((now - t).total_seconds() // 3600)))
    # The weight a spill counts with right now depends on its travel time to the click (live_now_risk
    # holds it in full until its water has passed), so the page works it out from `ended_h`. `live` is
    # the weight with no travel time, kept for a page from before 4 Oct 2026 that reads it.
    _, live = live_now_risk(sub.assign(weight=1.0, travel_h=0.0), now)
    since_end = ((now - pd.to_datetime(sub["latest_event_end"], utc=True)).dt.total_seconds() / 3600.0).to_numpy(dtype=float)
    ended_h = [None if run or not 0 <= h <= ENDED_KEEP_H else round(float(h), 1)
               for run, h in zip(running(sub), since_end, strict=True)]
    companies = sorted(sub["company"].fillna("unknown").astype(str).unique())
    cpos = {c: i for i, c in enumerate(companies)}
    from dipcast.ingest.live import FEED_DOWN, NO_FEED, STALE, with_data_states
    down = sub[sub["status"] == FEED_DOWN]
    since = {}
    if len(down) and "feed_down_since" in down:
        for c, g in down.groupby(down["company"].fillna("unknown")):
            t = pd.to_datetime(g["feed_down_since"], utc=True).min()
            since[str(c)] = None if pd.isna(t) else t.isoformat()
    # Data states go by company (ingest.live.data_states): a stale feed and its last update, and
    # the companies with no live feed. The page works each overflow's state out from these.
    st = with_data_states(sub)
    rec = st["record_stale"].fillna(False).astype(bool) if "record_stale" in st else pd.Series(False, index=st.index)
    stale_since = {}
    for c, g in st[(st["data_state"] == STALE) & ~rec].groupby(st["company"].fillna("unknown")):
        t = pd.to_datetime(g["feed_updated_at"], utc=True).max()
        stale_since[str(c)] = None if pd.isna(t) else t.isoformat()
    # A record that has stopped updating in a feed that has not (ingest.live.frozen_records), by its
    # index here, with its own last stamp; and the overflows carried through a feed outage whose
    # spill was running when the feed last answered (transport.running).
    stale_rows = {str(i): (None if pd.isna(t) else pd.Timestamp(t).isoformat())
                  for i, t in zip(np.flatnonzero(rec.to_numpy()), pd.to_datetime(st.loc[rec, "feed_updated_at"], utc=True), strict=True)}
    last_running = [int(i) for i in np.flatnonzero(running(sub) & (sub["status"] == FEED_DOWN).to_numpy())]
    no_feed = sorted(str(c) for c in st.loc[st["data_state"] == NO_FEED, "company"].fillna("unknown").unique())
    # Each current feed's last update, so the page can age its quiet readings where it is read, as a spot's
    # page does (index.html, ageReadings): otherwise a click hours after the build would count them live.
    from dipcast.ingest.live import LIVE
    feed_updated = {}
    for c, g in st[st["data_state"] == LIVE].groupby(st["company"].fillna("unknown")):
        t = pd.to_datetime(g["feed_updated_at"], utc=True).max()
        if not pd.isna(t):
            feed_updated[str(c)] = t.isoformat()
    body = {
        "generated_at": now.isoformat(), "ids": idv, "days": [d.date().isoformat() for d in days], "today": int(past),
        "scale": P_SCALE,
        "p": [[None if np.isnan(v) else round(float(v) * P_SCALE) for v in row] for row in p],
        "live": [round(float(v) * P_SCALE) for v in np.asarray(live, dtype=float)],
        "ended_h": ended_h,
        "status": [int(s) for s in sub["status"]],
        "company": [cpos[str(c)] for c in sub["company"].fillna("unknown")],
        "companies": companies, "feed_down_since": since, "feed_stale_since": stale_since, "no_feed": no_feed,
        "stale_rows": stale_rows, "last_running": last_running, "feed_updated": feed_updated,
        "rain_h": rain_h,
        "rain_48h": cell_rain_48h(hourly, days[past:]),
        "low": [int(i) for i in np.flatnonzero((sub.get("snap_confidence") == "low").to_numpy())],
        "assumptions": {"river_velocity_ms": river_velocity(None), "lake_velocity_ms": config.LAKE_VELOCITY_MS,
                        "t90_hours": config.T90_HOURS, "max_upstream_km": config.MAX_UPSTREAM_KM,
                        "recent_spill_hours": config.RECENT_SPILL_HOURS, "l0_m": L0_M, "dilution_power": transport.DILUTION_POWER,
                        "lake_area_halving_km2": LAKE_A0_KM2,
                        "lake_direction": config.LAKE_DIRECTION_MODE, "lake_down_margin_m": transport.LAKE_DOWN_MARGIN_M,
                        "low_confidence_factor": LOW_CONFIDENCE_FACTOR, "max_missing_share": 0.1,
                        "rain_max_age_h": RAIN_MAX_AGE_H},
        "note": ("p: per overflow, spill probability per day in thousandths, before the lead calibration; null where "
                 "the overflow's rain cell had no data that day (the ok mask). ended_h: hours from the end of the "
                 "overflow's latest spill to generated_at (null while it runs, with no end, or over 216 h): a spill "
                 "counts in full until its water has passed the point, its end plus the travel time there, then "
                 "decays with T90, for 48 h. live: the same weight with no travel time, in thousandths, for older "
                 "pages. status: "
                 "1 discharging, 0 not, -1 monitor offline, -2 no live feed, -3 company feed down. feed_stale_since: "
                 "companies whose feed answered but had not updated within 6 h, with the last update (null: no time); "
                 "their statuses are not current. stale_rows: overflows, by index, whose own record has not "
                 "updated within 6 h while the rest of their company's feed has, with their last update (null: "
                 "none); their statuses are not current either. last_running: overflows, by index, on a feed "
                 "that is down whose spill was running when it last answered; they count as discharging. "
                 "no_feed: companies with no live feed. feed_updated: each current feed's last update; where "
                 "the page is read over 6 h after it, that feed's quiet overflows are stale too. rain_h: hours "
                 "between the rain forecast the overflow's probabilities used and generated_at. rain_48h: per "
                 "rain square (0.1 degrees, keyed by its centre, \"lat,lon\"), the rain in mm in the 48 h to midday "
                 "local time on each day from today (days[today:]), as a listed spot's rain_48h_mm; null where "
                 "under 90% of the hours have data. low: overflows "
                 "snapped by proximity alone, whose weight is multiplied by low_confidence_factor."),
        **({"credits": credits} if credits else {}),
    }
    (out / "overflow_days.json").write_text(json.dumps(body, separators=(",", ":")))
    return {"days": len(days), "n": len(ids), "rain": rstats,
            "no_data_share": round(float(np.isnan(p).mean()), 4) if p.size else 0.0}


def size_of(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def build(site: Path, net: RiverNetwork, ov: pd.DataFrame, probabilities, credits: dict | None = None,
          now: pd.Timestamp | None = None, state_dir: Path | None = None) -> dict:
    """Write site/data/anypoint/. Returns a summary for the build log and spots.json's build."""
    from dipcast.ingest.lakes import PATH as LAKES_PATH
    t0 = time.time()
    now = now or pd.Timestamp.now(tz="Europe/London")
    out = site / "data" / OUT
    out.mkdir(parents=True, exist_ok=True)
    net_path = config.PROCESSED / "river_network.pkl"
    # The file's hash and what the load changed: the gap repairs and fixes are made afresh at every load,
    # so a change to them leaves the file as it was (RiverNetwork.topology_key).
    net_hash = f"{file_hash(net_path) if net_path.exists() else 'unknown'}-{net.topology_key()}"
    lakes = transport._lakes()
    lakes_hash = file_hash(LAKES_PATH) if LAKES_PATH.exists() else "none"
    cache = (state_dir or config.STATE) / CACHE_NAME
    table, stats = upstream_table(net, ov, lakes, net_hash, lakes_hash, cache)
    t1 = time.time()
    meta = write_files(out, net, ov, table, net_hash, credits)
    t2 = time.time()
    days = write_overflow_days(out, ov, meta["ids"], meta["ids_version"], meta["past_days"], now, probabilities, credits)
    t3 = time.time()
    (out / "tiles.json").write_text(json.dumps({
        "generated_at": now.isoformat(), "network": net_hash, "ids": meta["ids_version"], "tile_deg": TILE_DEG,
        "tiles": meta["tiles"], "dilution_scale": DIL_SCALE, "p_scale": P_SCALE,
        "forms": FORMS, "snap_m": PIN_SNAP_M, "lake_snap_m": LAKE_SNAP_M, "lake_shore_m": LAKE_SHORE_M,
        "lake_bias": transport.LAKE_BIAS, **({"credits": credits} if credits else {})}, separators=(",", ":")))
    # The overflow data is England's: without this file a click in Wales or Scotland near the border is
    # traced as if in England, and finds no overflow upstream.
    if OUTSIDE_ENGLAND.exists():
        shutil.copyfile(OUTSIDE_ENGLAND, out / OUTSIDE_ENGLAND.name)
    else:
        log.warning("any-point data: %s is missing, so the page cannot tell a click outside England", OUTSIDE_ENGLAND)
    summary = {**stats, **meta["counts"], "tiles": len(meta["tiles"]), "overflows": days["n"], "days": days["days"],
               "rain": days["rain"], "rain_unavailable_share": days["no_data_share"],
               "outside_england": OUTSIDE_ENGLAND.exists(), "bytes": size_of(out),
               "table_s": round(t1 - t0, 1), "files_s": round(t2 - t1, 1), "days_s": round(t3 - t2, 1),
               "seconds": round(time.time() - t0, 1)}
    log.info("any-point data: %s", summary)
    return summary
