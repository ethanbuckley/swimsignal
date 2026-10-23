"""Breaks in OS Open Rivers' network, found and mended when the network loads.

A dead end is a node with no link out of it that is not at the sea. Water reaching one goes no
further, so an overflow above it is never counted for a spot below it. Checks against the
Environment Agency's bathing water profiles and the site (11 Oct 2026) found dead ends on the
Hampshire Avon at Ratfyn, the Windrush, the Thame, the Perry and the Test at Whitchurch: the upper
Avon's overflows were missed at Salisbury, Burford STW at Wolvercote, Cuddington STW at Wallingford,
Gobowen and Oswestry at Shrewsbury, Overton at Chilbolton.

At the sea means a dead end with a tidal link flowing into it, or one within COAST_M of a tidal
link (a short river that meets the sea with no tidal reach). A node drains when a path leads from
it to such an end.

RiverNetwork applies, in this order:

1. The override list, data/raw/network_fixes.csv: links to reverse and joins to add, each with a
   reason, for what the rules below leave alone.
2. The gap repairs (RiverNetwork._repair_gaps): a dead end within 60 m of a headwater is joined to
   it. Where the headwater starts a link flowing into that same dead end, the join makes a loop
   (62 of the 653 joins); at Ratfyn the loop drains nowhere. Those joins are left out here, and
   put back after the rules (restore_loop_repairs) only where the dead end still has no outlet and
   the loop has a way out to the sea.
3. These rules, pass after pass until neither changes anything, so that a break downstream mended
   in one pass lets a break above it be mended in the next. Reversals are repeated until they find
   no more before each pass of joins: turning a link round keeps OS's geometry, a join has none.
   Each looks only at dead ends with at least MIN_UPSTREAM_M of network upstream.

   Reversal. OS Open Rivers draws some links against the flow. At Ratfyn, Warwick and Tamworth the
   main river arrives at a node whose only other link, drawn as flowing in, in fact carries the
   river away to a split node downstream. A dead end T's in-link from A is reversed when
     - A drains by another link out of it,
     - the link has a name, and shares a word of it with another link into T and with another
       link out of A (the river carries on under its own name both ways),
     - the water it brings is less than REVERSE_MAX_SHARE of what reaches T (it is not the main
       inflow), and reversing it makes no loop,
     - and it is the only link into T that passes all of this.

   Named join. A gap the 60 m repair cannot close: the next link starts more than 60 m away
   (the Test at Whitchurch, 205 m; the Thame, 277 m) or at a node some ditch already flows into,
   so it is not a headwater (the Windrush, 11 m). A dead end T is joined to the nearest node within
   JOIN_MAX_M that starts or ends a link sharing a word of the name of the river reaching T
   (main_words: its largest named inflow, looked for up to NAME_STEPS links up an unnamed one),
   drains, and is not upstream of T. An end counts: Scotsgrove Brook stops 10 m from the node where
   another branch of it meets Cuttle Brook, above Wallingford. A dead end whose river is a canal by name is left alone, and so is a side
   arm: one where a node upstream of it carrying SIDE_ARM_SHARE or more of its water already
   drains another way, so the river carries on without it.

scripts/check_network.py lists the dead ends and loops before and after, and how each was dealt with.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import pandas as pd
from shapely.geometry import LineString

from dipcast import config
from dipcast.network.names import river_words

log = logging.getLogger(__name__)

FIXES_CSV = config.RAW / "network_fixes.csv"
MIN_UPSTREAM_M = 10_000.0   # dead ends the rules look at
JOIN_MAX_M = 600.0          # named join: the farthest a dead end is joined
NAME_STEPS = 5              # named join: how many unnamed links up the main inflow to look for its name
REVERSE_MAX_SHARE = 0.5     # reversal: the most of the dead end's water the reversed link may bring
SIDE_ARM_SHARE = 0.5        # named join: a dead end this much of whose water drains elsewhere is a side arm
COAST_M = 2_000.0           # a dead end this close to a tidal link is at the coast
MAX_PASSES = 10


@dataclass(frozen=True)
class Fix:
    """One change to the network. `link` is the link reversed, or the join's edge id."""

    kind: str               # 'reverse' | 'join'
    rule: str               # 'override' | 'reversal' | 'named join'
    dead_end: str | None    # the node the fix gives an outlet (None for an override join elsewhere)
    link: str
    a: str                  # the edge, in the direction of flow after the fix
    b: str
    length_m: float
    name: str | None
    reason: str = ""


# ------------------------------------------------------------------ helpers
def _name(links: pd.DataFrame, lid: str) -> str | None:
    if lid not in links.index:
        return None
    v = links.at[lid, "watercourse_name"]
    return v if isinstance(v, str) and v else None


def link_words(links: pd.DataFrame, lid: str) -> frozenset[str]:
    """The distinctive words of a link's name and of OS's alternative name ("Afon Gwy" / "River Wye")."""
    if lid not in links.index:
        return frozenset()
    out: set[str] = set()
    for col in ("watercourse_name", "watercourse_name_alternative"):
        v = links.at[lid, col] if col in links.columns else None
        if isinstance(v, str):
            out |= river_words(v)
    return frozenset(out)


def _canal(links: pd.DataFrame, lid: str) -> bool:
    """A canal by name, "Canal" or "Navigation", not by OS's form. Some navigations carry their river
    (the Weaver Navigation) and some are cuts (the Aire and Calder's Knottingley and Goole Canal), and
    the name cannot tell which. Measured on 12 Oct 2026: counting "Navigation" as a
    river made one more fix in the whole network, a named join from a dead end into the Knottingley
    and Goole Canal, and changed no spot's overflows. So a navigation stays a canal here."""
    n = _name(links, lid)
    return bool(n) and any(w in n.lower().split() for w in ("canal", "navigation"))


def sea_ends(net, pts: pd.Series) -> set[str]:
    """Nodes with no link out of them that are at the sea: a tidal link flows in, or a tidal link
    is within COAST_M."""
    g = net.graph
    terms = sorted(n for n in g.nodes if g.out_degree(n) == 0)
    sea = {n for n in terms if any(g.edges[p, n].get("form") == "tidalRiver" for p in g.predecessors(n))}
    rest = [n for n in terms if n not in sea and n in pts.index]
    tidal = net.links[net.links["form"] == "tidalRiver"]
    if rest and not tidal.empty:
        import geopandas as gpd
        q = gpd.GeoSeries(pts.loc[rest].values, crs=27700)
        hit = tidal.sindex.nearest(q, return_all=False, max_distance=COAST_M)
        sea |= {rest[i] for i in set(hit[0].tolist())}
    return sea


def draining(g: nx.DiGraph, ends: set[str]) -> set[str]:
    """Every node with a path to one of `ends` (the ends included)."""
    out: set[str] = set()
    stack = [n for n in ends if n in g]
    while stack:
        n = stack.pop()
        if n in out:
            continue
        out.add(n)
        stack.extend(p for p in g.predecessors(n) if p not in out)
    return out


def dead_ends(g: nx.DiGraph, up: dict[str, float], sea: set[str], min_up: float) -> list[str]:
    """Nodes with no link out, not at the sea, with at least `min_up` of network upstream; by id."""
    return sorted(n for n in g.nodes if g.out_degree(n) == 0 and n not in sea and up.get(n, 0.0) >= min_up)


def _real(lid: str) -> bool:
    return not lid.startswith("repair:")


def main_words(net, t: str, up: dict[str, float], max_steps: int = NAME_STEPS) -> tuple[frozenset[str], str | None]:
    """The words of the name of the river reaching `t`, and the link that carries it: the largest
    named link into `t`; with none, the same looked for one link further up the largest inflow, up
    to `max_steps` links (the Lea reaches its dead end at Walthamstow through an unnamed lake link)."""
    g, links = net.graph, net.links
    node = t
    for _ in range(max_steps):
        ins = sorted(((up.get(p, 0.0) + g.edges[p, node]["length"], g.edges[p, node]["link"], p)
                      for p in g.predecessors(node)), key=lambda r: (-r[0], r[1]))
        for _, lid, _p in ins:
            if _real(lid):
                w = link_words(links, lid)
                if w:
                    return w, lid
        if not ins:
            break
        node = ins[0][2]
    return frozenset(), None


def side_share(net, t: str, up: dict[str, float], drains: set[str], anc: set[str] | None = None) -> float:
    """The largest share of `t`'s upstream network that a draining node above it carries: near 1
    for a side arm, whose river carries on without it."""
    anc = nx.ancestors(net.graph, t) if anc is None else anc
    top = max((up.get(a, 0.0) for a in anc if a in drains), default=0.0)
    return top / up[t] if up.get(t, 0.0) > 0 else 0.0


# ------------------------------------------------------------------ edits
def reverse_link(net, lid: str) -> tuple[str, str] | None:
    """Turn a link round: its graph edge, its nodes and its geometry. Returns the new (start, end),
    or None when the link is not the one the graph carries between its nodes, or the reverse edge exists."""
    links, g = net.links, net.graph
    if lid not in links.index:
        return None
    a, b = links.at[lid, "start_node"], links.at[lid, "end_node"]
    if not g.has_edge(a, b) or g.edges[a, b].get("link") != lid or g.has_edge(b, a):
        return None
    data = dict(g.edges[a, b])
    g.remove_edge(a, b)
    g.add_edge(b, a, **data)
    links.at[lid, "start_node"], links.at[lid, "end_node"] = b, a
    links.at[lid, "geometry"] = LineString(list(links.at[lid, "geometry"].coords)[::-1])
    return b, a


def add_join(net, a: str, b: str, length_m: float, tag: str) -> str:
    eid = f"repair:{tag}:{a[:8]}->{b[:8]}"
    length = float(max(length_m, 1.0))
    net.graph.add_edge(a, b, link=eid, length=length, form="repair")
    net.repairs[eid] = length
    return eid


# ------------------------------------------------------------------ rules
def reversal_for(net, t: str, up: dict[str, float], drains: set[str]) -> tuple[str, str] | None:
    """(link, its start node) to reverse to give dead end `t` an outlet, or None (rule in the module doc)."""
    g, links = net.graph, net.links
    ins = sorted((p, g.edges[p, t]["link"]) for p in g.predecessors(t))
    found = []
    for a, lid in ins:
        if not _real(lid) or a not in drains or g.has_edge(t, a) or _canal(links, lid):
            continue
        words = link_words(links, lid)
        if not words:
            continue
        others_in = [l for _, l in ins if l != lid and _real(l)]
        outs = [g.edges[a, s]["link"] for s in g.successors(a) if s != t]
        if not any(words & link_words(links, l) for l in others_in):
            continue
        if not any(words & link_words(links, l) for l in outs if _real(l)):
            continue
        if up.get(a, 0.0) + g.edges[a, t]["length"] >= REVERSE_MAX_SHARE * up.get(t, 0.0):
            continue
        found.append((lid, a))
    if len(found) != 1:
        return None
    lid, a = found[0]
    # No loop: once reversed, t flows to a, so nothing downstream of a may lead back to t.
    data = dict(g.edges[a, t])
    g.remove_edge(a, t)
    loops = nx.has_path(g, a, t)
    g.add_edge(a, t, **data)
    return None if loops else (lid, a)


def join_for(net, t: str, up: dict[str, float], drains: set[str], pts: pd.Series) -> tuple[str, float, str] | None:
    """(node, distance, the link it starts) to join dead end `t` to, or None (rule in the module doc)."""
    words, main = main_words(net, t, up)
    if not words or _canal(net.links, main):
        return None
    anc = nx.ancestors(net.graph, t)
    if side_share(net, t, up, drains, anc) >= SIDE_ARM_SHARE:
        return None
    p = pts[t]
    cand = net.candidates_xy(p.x, p.y, JOIN_MAX_M)
    best = None
    for lid in sorted(cand.index):
        if not words & link_words(net.links, lid):
            continue
        for s in (cand.at[lid, "start_node"], cand.at[lid, "end_node"]):
            if s == t or s in anc or s not in drains or s not in pts.index:
                continue
            d = float(pts[s].distance(p))
            if d <= JOIN_MAX_M and (best is None or (d, s) < (best[1], best[0])):
                best = (s, d, lid)
    return best


def _reversals(net, sea: set[str]) -> list[Fix]:
    """One pass of the reversal rule over every dead end."""
    g = net.graph
    up = net._compute_upstream_m(quiet=True)
    drains = draining(g, sea)
    out = []
    for t in dead_ends(g, up, sea, MIN_UPSTREAM_M):
        r = reversal_for(net, t, up, drains)
        if r is None:
            continue
        lid, a = r
        if reverse_link(net, lid) is not None:
            out.append(Fix("reverse", "reversal", t, lid, t, a, float(net.links.at[lid, "length"]), _name(net.links, lid)))
    return out


def _joins(net, sea: set[str], pts: pd.Series) -> list[Fix]:
    """One pass of the named-join rule over every dead end."""
    g = net.graph
    up = net._compute_upstream_m(quiet=True)
    drains = draining(g, sea)
    out = []
    for t in dead_ends(g, up, sea, MIN_UPSTREAM_M):
        j = join_for(net, t, up, drains, pts)
        if j is None:
            continue
        s, d, lid = j
        eid = add_join(net, t, s, d, "named")
        out.append(Fix("join", "named join", t, eid, t, s, max(d, 1.0), _name(net.links, lid)))
    return out


def apply_rules(net, pts: pd.Series) -> list[Fix]:
    """The rules, pass after pass until neither changes anything. Reversals go first, repeated until
    they find no more, then one pass of joins: where turning a link round mends a dead end, that
    is preferred to a join, which spans a gap with no geometry."""
    sea = sea_ends(net, pts)
    fixes: list[Fix] = []
    for _ in range(MAX_PASSES):
        n0 = len(fixes)
        for _ in range(MAX_PASSES):
            rev = _reversals(net, sea)
            fixes += rev
            if not rev:
                break
        fixes += _joins(net, sea, pts)
        if len(fixes) == n0:
            break
    return fixes


def restore_loop_repairs(net, pts: pd.Series, skipped: list[tuple[str, str, float]]) -> dict[str, float]:
    """The gap repairs left out because they make a loop (RiverNetwork._repair_gaps), put back where
    the dead end still has no outlet after the rules and the headwater drains: the loop then has a way
    out, and the dead end's water reaches the sea through it (the Blackbrook River on Dartmoor
    through the Devonport Leat). A loop with no way out (Ratfyn) stays out."""
    g = net.graph
    sea = sea_ends(net, pts)
    out: dict[str, float] = {}
    for sink, h, length in sorted(skipped):
        # The way out must not be the dead end itself: one near the coast counts as a sea end.
        if g.out_degree(sink) == 0 and not g.has_edge(sink, h) and (nx.descendants(g, h) & sea) - {sink}:
            eid = f"repair:{sink[:8]}->{h[:8]}"
            g.add_edge(sink, h, link=eid, length=length, form="repair")
            out[eid] = length
    if out:
        log.info("network repairs: %d that make a loop with a way out put back (no rule gave their dead end an outlet)",
                 len(out))
    return out


# ------------------------------------------------------------------ overrides
OVERRIDE_COLUMNS = ["action", "a", "b", "length_m", "place", "checked", "reason"]


def read_overrides(path: Path | None = None) -> pd.DataFrame:
    """data/raw/network_fixes.csv: `reverse` rows name a link in `a`; `join` rows add an edge from
    node `a` to node `b`, of `length_m` metres (blank: the straight distance between them)."""
    path = FIXES_CSV if path is None else path
    if not Path(path).exists():
        return pd.DataFrame(columns=OVERRIDE_COLUMNS)
    df = pd.read_csv(path, comment="#", dtype=str).fillna("")
    missing = set(OVERRIDE_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    for i, r in df.iterrows():
        v = str(r["length_m"]).strip()
        try:
            ok = not v or float(v) > 0
        except ValueError:
            ok = False
        if not ok:
            raise ValueError(f"{path}: row {i + 1} ({r['place']}): length_m must be blank or metres as a number, not {v!r}")
    return df


def apply_overrides(net, pts: pd.Series, rows: pd.DataFrame | None = None) -> list[Fix]:
    """The override list. A row whose link or nodes are not in the network (another OS release, or a
    test's small network) is passed over, and said so in the log."""
    rows = read_overrides() if rows is None else rows
    fixes: list[Fix] = []
    g = net.graph
    for r in rows.itertuples(index=False):
        if r.action == "reverse":
            ends = reverse_link(net, r.a)
            if ends is None:
                log.info("network fix not applied (link not in this network as listed): reverse %s, %s", r.a, r.place)
                continue
            fixes.append(Fix("reverse", "override", None, r.a, ends[0], ends[1], float(net.links.at[r.a, "length"]),
                             _name(net.links, r.a), r.reason))
        elif r.action == "join":
            if r.a not in g or r.b not in g or r.a not in pts.index or r.b not in pts.index or g.has_edge(r.a, r.b):
                log.info("network fix not applied (nodes not in this network): join %s -> %s, %s", r.a, r.b, r.place)
                continue
            if nx.has_path(g, r.b, r.a):
                log.warning("network fix not applied (it would make a loop): join %s -> %s, %s", r.a, r.b, r.place)
                continue
            length = float(r.length_m) if str(r.length_m).strip() else float(pts[r.a].distance(pts[r.b]))
            eid = add_join(net, r.a, r.b, length, "fix")
            fixes.append(Fix("join", "override", None, eid, r.a, r.b, max(length, 1.0), r.place or None, r.reason))
        else:
            raise ValueError(f"network_fixes.csv: unknown action {r.action!r}")
    return fixes
