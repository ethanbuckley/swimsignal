"""Dead ends and loops in the river network, before and after the fixes made at load.

A dead end is a node no link leaves that is not at the sea (dipcast.network.fixes.sea_ends); a loop
is a set of nodes that all reach one another (a strongly connected component of more than one node).
Water reaching either goes no further, so an overflow above it is never counted below it.

Each dead end with at least --min-km of network upstream in the network as it loaded before 11 Oct
2026 (RiverNetwork(fix=False): the 60 m gap repairs, loops and all) is put in one class:

  (a) side arm      a node above it carrying at least half its water drains another way: the river
                    carries on without it (dipcast.network.fixes.side_share, in the mended network)
  (b) gap break     mended by a join: the named-join rule, or a join in data/raw/network_fixes.csv
  (c) flow direction mended by turning a link round: the reversal rule, or the override list
  (d) inland sink   a lake with no outflow, or the end of a canal (by name)
  (e) unclear       none of these; the nearest link start of the same name, and whether it drains,
                    are listed to look at

Usage:
  DIPCAST_ROOT=... PYTHONPATH=src python scripts/check_network.py [--min-km 30] [--csv out.csv]
"""

from __future__ import annotations

import argparse
import logging
import pickle
import sys
from pathlib import Path

import networkx as nx
import pandas as pd

from dipcast import config
from dipcast.network import fixes as nf
from dipcast.network.rivers import RiverNetwork, bng_to_lonlat

log = logging.getLogger("check_network")

CLASSES = {"a": "side arm", "b": "gap break", "c": "flow direction", "d": "inland sink", "e": "unclear"}
LOOK_M = 2_000.0   # unclear dead ends: how far to look for a link start of the same name


def terminal_groups(net: RiverNetwork, sea: set[str], min_up: float) -> list[tuple[str, frozenset[str], float]]:
    """Each dead end or loop that no link leaves, not at the sea, with at least min_up upstream:
    (its node with the most upstream, its nodes, that upstream). Sorted by node id."""
    g = net.graph
    cond = nx.condensation(g)
    out = []
    for c in cond.nodes:
        if cond.out_degree(c):
            continue
        members = frozenset(cond.nodes[c]["members"])
        if members & sea:
            continue
        rep = max(sorted(members), key=lambda n: net.upstream_m.get(n, 0.0))
        up = net.upstream_m.get(rep, 0.0)
        if up >= min_up:
            out.append((rep, members, up))
    return sorted(out)


def loops(net: RiverNetwork) -> pd.DataFrame:
    """Every loop: where, how much network is above it, its links, and whether a gap repair made it."""
    g, pts = net.graph, net.node_points()
    rows = []
    for comp in nx.strongly_connected_components(g):
        if len(comp) < 2:
            continue
        sub = g.subgraph(comp)
        lids = sorted(sub.edges[e]["link"] for e in sub.edges)
        rep = min(comp)
        lon, lat = bng_to_lonlat(pts[rep].x, pts[rep].y)
        names = sorted({n for n in (nf._name(net.links, l) for l in lids) if n})
        rows.append({"lat": round(lat, 4), "lon": round(lon, 4), "nodes": len(comp),
                     "up_km": round(max(net.upstream_m.get(n, 0.0) for n in comp) / 1000, 1),
                     "made_by": "gap repair" if any(l.startswith("repair:") for l in lids) else "OS data",
                     "drains_out": any(s not in comp for n in comp for s in g.successors(n)),
                     "names": "; ".join(names), "links": " ".join(l[:8] if not l.startswith("repair:") else l for l in lids)})
    return pd.DataFrame(rows).sort_values(["made_by", "up_km"], ascending=[True, False]).reset_index(drop=True) \
        if rows else pd.DataFrame(columns=["lat", "lon", "nodes", "up_km", "made_by", "drains_out", "names", "links"])


def _nearest_same_name(net: RiverNetwork, t: str, words: frozenset[str], anc: set[str], drains: set[str],
                       pts: pd.Series) -> tuple[float | None, bool | None]:
    if not words:
        return None, None
    p = pts[t]
    cand = net.candidates_xy(p.x, p.y, LOOK_M)
    best = None
    for lid in sorted(cand.index):
        s = cand.at[lid, "start_node"]
        if s == t or s in anc or s not in pts.index or not words & nf.link_words(net.links, lid):
            continue
        d = float(pts[s].distance(p))
        if best is None or d < best[0]:
            best = (d, s in drains)
    return (round(best[0]), best[1]) if best else (None, None)


def classify(before: RiverNetwork, after: RiverNetwork, min_up: float) -> pd.DataFrame:
    """One row per dead end or loop in `before` with at least min_up upstream, with its class."""
    pts = after.node_points()
    sea_b = nf.sea_ends(before, pts)
    sea_a = nf.sea_ends(after, pts)
    drains_a = nf.draining(after.graph, sea_a)
    by_node: dict[str, nf.Fix] = {}
    for f in after.fixes:
        if f.dead_end is not None:
            by_node.setdefault(f.dead_end, f)
        elif f.rule == "override":
            by_node.setdefault(f.a, f)   # the node the override gives an outlet (a reversed link's new start)
    rows = []
    for rep, members, up in terminal_groups(before, sea_b, min_up):
        p = pts[rep]
        lon, lat = bng_to_lonlat(p.x, p.y)
        words, main = nf.main_words(before, rep, before.upstream_m)
        fix = next((by_node[m] for m in sorted(members) if m in by_node), None)
        row = {"node": rep, "lat": round(lat, 4), "lon": round(lon, 4), "up_km": round(up / 1000, 1),
               "loop": len(members) > 1, "name": nf._name(before.links, main) if main else None,
               "drains_after": rep in drains_a, "fix": None, "fix_link": None, "fix_m": None,
               "side_share": None, "nearest_same_name_m": None, "that_drains": None}
        if fix is not None:
            row.update(cls="c" if fix.kind == "reverse" else "b", fix=fix.rule, fix_link=fix.link,
                       fix_m=round(fix.length_m))
        elif rep in drains_a:
            row.update(cls="b", fix="drains after other fixes")
        else:
            g = after.graph
            anc = nx.ancestors(g, rep)
            share = nf.side_share(after, rep, after.upstream_m, drains_a, anc)
            ins = [g.edges[q, rep]["link"] for q in g.predecessors(rep)]
            forms = {after.links.at[l, "form"] for l in ins if l in after.links.index}
            near, near_drains = _nearest_same_name(after, rep, words, anc, drains_a, pts)
            row.update(side_share=round(share, 2), nearest_same_name_m=near, that_drains=near_drains)
            if share >= nf.SIDE_ARM_SHARE:
                row["cls"] = "a"
            elif (main and nf._canal(after.links, main)) or forms == {"canal"}:
                row.update(cls="d", fix="canal end")
            elif forms == {"lake"}:
                row.update(cls="d", fix="lake with no outflow")
            else:
                row["cls"] = "e"
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["class"] = df["cls"].map(CLASSES)
        df = df.sort_values(["cls", "up_km"], ascending=[True, False]).reset_index(drop=True)
    return df


def load_both(path: Path) -> tuple[RiverNetwork, RiverNetwork]:
    with open(path, "rb") as f:
        d = pickle.load(f)
    before = RiverNetwork(d["links"].copy(), d["graph"].copy(), fix=False)
    after = RiverNetwork(d["links"], d["graph"])
    return before, after


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-km", type=float, default=30.0, help="dead ends with at least this much network upstream")
    ap.add_argument("--network", type=Path, default=config.PROCESSED / "river_network.pkl")
    ap.add_argument("--csv", type=Path, help="write the dead ends here")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    before, after = load_both(args.network)
    min_up = args.min_km * 1000.0
    df = classify(before, after, min_up)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 1000)
    pd.set_option("display.max_colwidth", 40)
    print(f"\nDead ends and loops with >= {args.min_km:g} km upstream, as the network loaded before: {len(df)}")
    if not df.empty:
        print(df.groupby(["cls", "class"]).size().rename("count").to_string())
        print(df.drop(columns=["node", "cls"]).to_string())
    left = classify(after, after, min_up)
    print(f"\nLeft after the fixes (>= {args.min_km:g} km): {len(left)}")
    if not left.empty:
        print(left.groupby(["cls", "class"]).size().rename("count").to_string())
    lb, la = loops(before), loops(after)
    print(f"\nLoops before: {len(lb)} ({int((lb['made_by'] == 'gap repair').sum()) if len(lb) else 0} made by a gap "
          f"repair); after: {len(la)}")
    if len(la):
        print(la.to_string())
    kinds = pd.Series([f"{f.rule} ({f.kind})" for f in after.fixes]).value_counts()
    print("\nFixes made at load:")
    print(kinds.to_string())
    ov = nf.read_overrides()
    applied = {f.link if f.kind == "reverse" else (f.a, f.b) for f in after.fixes if f.rule == "override"}
    for r in ov.itertuples(index=False):
        key = r.a if r.action == "reverse" else (r.a, r.b)
        print(f"override {r.action} {r.place}: {'applied' if key in applied else 'NOT APPLIED'}")
    if args.csv:
        df.to_csv(args.csv, index=False)
        print("wrote", args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
