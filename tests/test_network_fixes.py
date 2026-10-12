"""Breaks in the river network mended at load (dipcast.network.fixes) and the check that lists them
(scripts/check_network.py). Network-free: a few links built in memory, in British National Grid metres,
in the shapes found in OS Open Rivers on 11 Oct 2026 (Ratfyn, the Windrush, the Test at Chilbolton)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pytest
from shapely.geometry import LineString

from dipcast.network import fixes as nf
from dipcast.network.rivers import RiverNetwork

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_override_file(monkeypatch, tmp_path):
    """The rules alone, unless a test writes its own override list."""
    monkeypatch.setattr(nf, "FIXES_CSV", tmp_path / "none.csv")


def _gdf(links: list[tuple]) -> gpd.GeoDataFrame:
    """links: (id, name, form, start node, end node, [(x, y), ...]), drawn from start to end."""
    return gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": f, "fictitious": False,
          "watercourse_name": n, "watercourse_name_alternative": None, "start_node": s, "end_node": e,
          "geometry": LineString(xy)} for i, n, f, s, e, xy in links], crs=27700)


def _net(links: list[tuple], fix: bool = True) -> RiverNetwork:
    return RiverNetwork.from_links(_gdf(links), fix=fix)


def _reaches(net: RiverNetwork, a: str, b: str) -> bool:
    return nx.has_path(net.graph, a, b)


# Ratfyn, on the Hampshire Avon: the river arrives at t, and the only link on from t is drawn flowing
# into it from s, a split node whose other link carries the Avon on to the sea. A 42 m unnamed stub
# also flows into t from a headwater h, 30 m away.
RATFYN = [
    ("U1", "River Avon", "inlandRiver", "u0", "u1", [(0, 30000), (0, 15000)]),
    ("U2", "River Avon", "inlandRiver", "u1", "t", [(0, 15000), (0, 10000)]),
    ("E", "River Avon", "inlandRiver", "s", "t", [(1000, 9000), (0, 10000)]),        # drawn uphill
    ("D1", "River Avon", "inlandRiver", "s", "d1", [(1000, 9000), (1000, 4000)]),
    ("D2", "River Avon", "tidalRiver", "d1", "d2", [(1000, 4000), (1000, 0)]),
    ("H", None, "inlandRiver", "h", "t", [(30, 10000), (0, 10000)]),
]


def test_a_link_drawn_against_the_flow_is_turned_round():
    old = _net(RATFYN, fix=False)
    assert old.graph.out_degree("t") == 1 and not _reaches(old, "u0", "d2")
    net = _net(RATFYN)
    assert _reaches(net, "u0", "d2")
    assert [(f.kind, f.rule, f.link, f.a, f.b) for f in net.fixes] == [("reverse", "reversal", "E", "t", "s")]
    assert (net.links.at["E", "start_node"], net.links.at["E", "end_node"]) == ("t", "s")
    assert net.links.at["E", "geometry"].coords[0] == (0.0, 10000.0)   # geometry follows the flow
    assert net.upstream_m["d1"] > 21_000


def test_a_gap_repair_no_longer_closes_a_loop():
    """Before 11 Oct 2026 the dead end t was joined to the head of the stub flowing into it, a loop
    that drained nowhere; the upper Avon then reached nothing below Ratfyn."""
    old = _net(RATFYN, fix=False)
    assert {"t", "h"} in [set(c) for c in nx.strongly_connected_components(old.graph)]
    net = _net(RATFYN)
    assert all(len(c) == 1 for c in nx.strongly_connected_components(net.graph))
    assert not any(k.startswith("repair:t") for k in net.repairs)


def test_a_loop_with_a_way_out_is_kept_where_no_rule_mends_the_dead_end():
    """The Blackbrook River on Dartmoor: the stream stops at s; a head h 30 m away starts a link to x,
    which splits into a link back to s and one on to the sea. The old join s -> h made a loop with a
    way out, the only way the stream's water reached the sea. Under 10 km upstream, so no rule looks
    at s; the join is put back."""
    links = [
        ("M1", None, "inlandRiver", "m0", "s", [(0, 6000), (0, 1000)]),
        ("H", None, "inlandRiver", "h", "x", [(30, 1000), (300, 800)]),
        ("X1", None, "inlandRiver", "x", "s", [(300, 800), (0, 1000)]),
        ("X2", None, "inlandRiver", "x", "y", [(300, 800), (600, 0)]),
        ("Y", "Estuary", "tidalRiver", "y", "z", [(600, 0), (600, -3000)]),
    ]
    old, net = _net(links, fix=False), _net(links)
    assert _reaches(old, "m0", "z") and _reaches(net, "m0", "z")
    assert set(net.repairs) == set(old.repairs) == {"repair:s->h"}


def test_a_loop_with_no_way_out_is_not_put_back_near_the_coast():
    """As above, but x has no link on to the sea, and s is within 2 km of a tidal link: s counts as a
    sea end, so h reaches the sea only through s. Joining s to h would make a loop with no way out."""
    links = [
        ("M1", None, "inlandRiver", "m0", "s", [(0, 6000), (0, 1000)]),
        ("H", None, "inlandRiver", "h", "x", [(30, 1000), (300, 800)]),
        ("X1", None, "inlandRiver", "x", "s", [(300, 800), (0, 1000)]),
        ("Y", "Estuary", "tidalRiver", "y", "z", [(1500, 0), (3000, 0)]),
    ]
    net = _net(links)
    assert not net.repairs
    assert all(len(c) == 1 for c in nx.strongly_connected_components(net.graph))


def _variant(changes: dict[str, tuple]) -> list[tuple]:
    out = [changes.get(r[0], r) for r in RATFYN]
    return [r for r in out if r is not None] + [v for k, v in changes.items() if v is not None and k not in {r[0] for r in RATFYN}]


@pytest.mark.parametrize("why, changes", [
    ("the link has no name", {"E": ("E", None, "inlandRiver", "s", "t", [(1000, 9000), (0, 10000)])}),
    ("its name is not the river's", {"E": ("E", "Mill Stream", "inlandRiver", "s", "t", [(1000, 9000), (0, 10000)])}),
    ("it brings most of the water", {"S0": ("S0", "River Avon", "inlandRiver", "s0", "s", [(9000, 30000), (1000, 9000)])}),
    ("its start does not drain", {"D2": ("D2", "River Avon", "inlandRiver", "d1", "d2", [(1000, 4000), (1000, 0)])}),
])
def test_a_link_is_left_as_drawn_when_the_rule_does_not_hold(why, changes):
    net = _net(_variant(changes))
    assert not any(f.kind == "reverse" for f in net.fixes), why


def test_two_links_that_could_be_turned_round_leave_both_as_drawn():
    """Ambiguous: two named links of the river flow into the dead end from split nodes that drain."""
    links = RATFYN + [
        ("E2", "River Avon", "inlandRiver", "s2", "t", [(-1000, 9000), (0, 10000)]),
        ("F1", "River Avon", "inlandRiver", "s2", "f1", [(-1000, 9000), (-1000, 4000)]),
        ("F2", "River Avon", "tidalRiver", "f1", "f2", [(-1000, 4000), (-1000, 0)]),
    ]
    assert not _net(links).fixes


# The Windrush above Wolvercote: the river stops at w1; 11 m on, the next Windrush link starts at a
# node an unnamed ditch already flows into, so it is no headwater and the 60 m repair passes it by.
WINDRUSH = [
    ("W1", "River Windrush", "inlandRiver", "w0", "w1", [(0, 20000), (0, 5000)]),
    ("W2", "River Windrush", "inlandRiver", "n", "w3", [(8, 4992), (0, 0)]),
    ("X", None, "inlandRiver", "x0", "n", [(300, 5200), (8, 4992)]),
    ("W3", "River Thames", "tidalRiver", "w3", "w4", [(0, 0), (0, -3000)]),
]


def test_a_dead_end_is_joined_to_the_next_link_of_its_name():
    assert not _reaches(_net(WINDRUSH, fix=False), "w0", "w4")
    net = _net(WINDRUSH)
    assert _reaches(net, "w0", "w4")
    [f] = net.fixes
    assert (f.kind, f.rule, f.a, f.b, f.name) == ("join", "named join", "w1", "n", "River Windrush")
    assert f.link in net.repairs and 10 < net.repairs[f.link] < 12
    assert net.graph.edges["w1", "n"]["form"] == "repair"


@pytest.mark.parametrize("why, row", [
    ("another river's name", ("W2", "River Evenlode", "inlandRiver", "n", "w3", [(8, 4992), (0, 0)])),
    ("too far", ("W2", "River Windrush", "inlandRiver", "n", "w3", [(700, 4992), (0, 0)])),
])
def test_no_join_to_another_river_or_beyond_the_distance(why, row):
    links = [row if r[0] == "W2" else r for r in WINDRUSH]
    if why == "too far":
        links = [("X", None, "inlandRiver", "x0", "n", [(900, 5200), (700, 4992)]) if r[0] == "X" else r for r in links]
    assert not _net(links).fixes, why


def test_a_dead_end_on_a_canal_or_a_navigation_is_not_joined():
    """Some navigations are cuts, and the name cannot tell which (fixes._canal). On the real network,
    counting "Navigation" as a river added only a join into the Knottingley and Goole Canal (12 Oct 2026)."""
    rename = lambda new: [(i, new if n == "River Windrush" else n, f, s, e, xy) for i, n, f, s, e, xy in WINDRUSH]
    for name in ("Trent and Mersey Canal", "Aire and Calder Navigation"):
        assert not _net(rename(name)).fixes, name
        assert nf._canal(_gdf(rename(name)).set_index("id"), "W1")
    [f] = _net(rename("River Weaver")).fixes
    assert (f.rule, f.name) == ("named join", "River Weaver")


def test_a_dead_end_is_joined_where_another_branch_of_its_brook_ends():
    """Scotsgrove Brook stops 10 m from the node where its other branch meets Cuttle Brook: no link
    of its name starts there, one ends there."""
    links = [
        ("S1", "Scotsgrove Brook", "inlandRiver", "s0", "s1", [(0, 30000), (0, 5000)]),
        ("S2", "Scotsgrove Brook", "inlandRiver", "r0", "c", [(2000, 9000), (6, 4992)]),
        ("C1", "Cuttle Brook", "inlandRiver", "c", "c1", [(6, 4992), (0, 0)]),
        ("C2", "River Thame", "tidalRiver", "c1", "c2", [(0, 0), (0, -3000)]),
    ]
    assert not _reaches(_net(links, fix=False), "s0", "c2")
    net = _net(links)
    assert [(f.rule, f.a, f.b) for f in net.fixes] == [("named join", "s1", "c")]
    assert _reaches(net, "s0", "c2")


def test_no_join_to_a_link_that_reaches_no_sea():
    links = [r for r in WINDRUSH if r[0] != "W3"]   # W2 now ends inland too, with under 10 km above it
    assert not _net(links).fixes


def test_a_break_below_is_mended_first_then_the_one_above_it():
    """Two breaks on one river: the upper dead end's next link reaches the sea only once the lower
    break is joined, in the pass before."""
    links = [
        ("A1", "River Coln", "inlandRiver", "a0", "a1", [(0, 40000), (0, 25000)]),
        ("A2", "River Coln", "inlandRiver", "b0", "b1", [(100, 24900), (100, 12000)]),
        ("A3", "River Coln", "inlandRiver", "c0", "c1", [(300, 11800), (300, 2000)]),
        ("T1", "River Thames", "tidalRiver", "c1", "c2", [(300, 2000), (300, 0)]),
    ]
    net = _net(links)
    assert [(f.a, f.b) for f in net.fixes] == [("b1", "c0"), ("a1", "b0")]
    assert _reaches(net, "a0", "c2")


def test_a_side_arm_is_left_alone():
    """The river splits at p; the arm ends at q while the river carries on to the sea. The arm's
    water is the river's, which is counted below the split already."""
    links = [
        ("M1", "River Frome", "inlandRiver", "m0", "p", [(0, 30000), (0, 10000)]),
        ("M2", "River Frome", "inlandRiver", "p", "m2", [(0, 10000), (0, 3000)]),
        ("M3", "River Frome", "tidalRiver", "m2", "m3", [(0, 3000), (0, 0)]),
        ("AR", "River Frome", "inlandRiver", "p", "q", [(0, 10000), (400, 9000)]),
        ("M4", "River Frome", "inlandRiver", "r", "m2", [(450, 8800), (0, 3000)]),
    ]
    net = _net(links)
    assert not net.fixes
    assert net.graph.out_degree("q") == 0


def test_a_dead_end_near_a_tidal_link_is_at_the_sea():
    links = [
        ("C1", "River Char", "inlandRiver", "c0", "c1", [(0, 20000), (0, 1000)]),
        ("C2", "River Char", "inlandRiver", "c2", "c3", [(30, 900), (30, 300)]),
        ("T1", "Some Estuary", "tidalRiver", "t0", "t1", [(1500, 0), (3000, 0)]),
    ]
    net = _net(links)
    assert "c1" in nf.sea_ends(net, net.node_points())
    assert not net.fixes


# The Test above Chilbolton: two channels, both River Test; the eastern one starts 21 m from the
# western and OS joins it to nothing but a ditch. The override list joins it.
CHILBOLTON = [
    ("T1", "River Test", "inlandRiver", "t0", "t1", [(0, 30000), (0, 10000)]),
    ("T2", "River Test", "inlandRiver", "t1", "t2", [(0, 10000), (0, 8000), (0, 2000)]),
    ("B1", "River Test", "inlandRiver", "b0", "t2", [(21, 8000), (500, 5000), (0, 2000)]),
    ("DI", None, "inlandRiver", "di", "b0", [(300, 8100), (21, 8000)]),
    ("T3", "River Test", "tidalRiver", "t2", "t3", [(0, 2000), (0, 0)]),
]


def _overrides(tmp_path: Path, monkeypatch, rows: list[str]) -> None:
    p = tmp_path / "network_fixes.csv"
    p.write_text("# test\naction,a,b,length_m,place,checked,reason\n" + "\n".join(rows) + "\n")
    monkeypatch.setattr(nf, "FIXES_CSV", p)


def test_the_override_list_joins_and_reverses(tmp_path, monkeypatch):
    assert not _reaches(_net(CHILBOLTON), "t0", "b0")
    _overrides(tmp_path, monkeypatch, [
        "join,t1,b0,2021,River Test braid,2026-10-11,the eastern channel leaves the western here",
        "reverse,DI,,,a ditch,2026-10-11,a test of reverse",
        "join,nowhere,b0,,missing node,2026-10-11,passed over",
        "reverse,NOLINK,,,missing link,2026-10-11,passed over",
    ])
    net = _net(CHILBOLTON)
    assert _reaches(net, "t0", "b0")
    assert net.repairs["repair:fix:t1->b0"] == 2021.0
    assert (net.links.at["DI", "start_node"], net.links.at["DI", "end_node"]) == ("b0", "di")
    assert sorted((f.kind, f.rule) for f in net.fixes) == [("join", "override"), ("reverse", "override")]


def test_an_override_join_that_would_close_a_loop_is_refused(tmp_path, monkeypatch):
    _overrides(tmp_path, monkeypatch, ["join,t2,t1,,a loop,2026-10-11,refused"])
    net = _net(CHILBOLTON)
    assert not net.fixes and not net.graph.has_edge("t2", "t1")


def test_the_override_file_in_the_repository_reads():
    rows = nf.read_overrides(ROOT / "data" / "raw" / "network_fixes.csv")   # raises on a bad length_m
    assert set(rows["action"]) <= {"reverse", "join"}
    assert (rows["reason"].str.len() > 40).all() and (rows["checked"].str.len() == 10).all()


@pytest.mark.parametrize("length", ["533 m", "-5", "0", "about 500"])
def test_a_malformed_length_is_named_when_the_list_is_read(tmp_path, length):
    """A length the code cannot read stopped every site build at network load, and CI did not see it,
    since the repo test checked only the action, reason and date (review of #184)."""
    p = tmp_path / "network_fixes.csv"
    p.write_text(f"action,a,b,length_m,place,checked,reason\njoin,x,y,{length},River Test braid,2026-10-12,a test\n")
    with pytest.raises(ValueError, match=r"row 1 \(River Test braid\): length_m must be blank or metres"):
        nf.read_overrides(p)
    p.write_text("action,a,b,length_m,place,checked,reason\njoin,x,y,,blank is the straight line,2026-10-12,a test\n"
                 "join,x,z,533,a number,2026-10-12,a test\n")
    assert len(nf.read_overrides(p)) == 2


def test_the_topology_key_follows_the_fixes():
    a, b = _net(RATFYN), _net(RATFYN)
    assert a.topology_key() == b.topology_key()
    assert a.topology_key() != _net(RATFYN, fix=False).topology_key()


def test_upstream_lengths_match_condensing_the_whole_graph():
    """_compute_upstream_m condenses only the nodes in or below a cycle; the sums must be those of
    condensing the whole graph, the rule before 11 Oct 2026."""
    net = RiverNetwork.__new__(RiverNetwork)
    net.graph = nx.DiGraph()
    for a, b, length in [("head", "alpha", 1000), ("alpha", "beta", 200), ("beta", "gamma", 300), ("gamma", "alpha", 400),
                         ("gamma", "out", 500), ("side", "out", 50), ("out", "sea", 10), ("x", "x", 5), ("x", "sea", 7)]:
        net.graph.add_edge(a, b, length=length)
    g, up = net.graph, {}
    cyc = nx.condensation(g)
    for comp in nx.topological_sort(cyc):
        for n in sorted(cyc.nodes[comp]["members"]):
            up[n] = sum(up.get(p, 0.0) + g.edges[p, n]["length"] for p in g.predecessors(n) if p in up)
    assert net._compute_upstream_m(quiet=True) == up


def test_the_fixes_do_not_depend_on_the_hash_seed():
    source = f"""
import json, sys
sys.path.insert(0, {str(ROOT / 'tests')!r})
from dipcast.network import fixes as nf
nf.FIXES_CSV = nf.Path('/nonexistent.csv')
import test_network_fixes as t
links = t.RATFYN + [(i + '_w', n, f, s + '_w', e + '_w', [(x + 50000, y) for x, y in xy]) for i, n, f, s, e, xy in t.WINDRUSH]
net = t._net(links)
print(json.dumps([[f.kind, f.link, f.a, f.b] for f in net.fixes]))
"""
    out = [subprocess.check_output([sys.executable, "-c", source], text=True,
                                   env={**os.environ, "PYTHONHASHSEED": str(seed)}) for seed in (1, 2, 13)]
    assert out[0] == out[1] == out[2]
    assert len(json.loads(out[0])) == 2


# ------------------------------------------------------------------ scripts/check_network.py
def _check():
    spec = importlib.util.spec_from_file_location("check_network", ROOT / "scripts" / "check_network.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_check_puts_each_dead_end_in_a_class():
    def shift(rows, dx):   # each case 100 km east of the one before, its ids suffixed
        return [(i + dx, n, f, s + dx, e + dx, [(x + int(dx[1:]) * 100000, y) for x, y in xy])
                for i, n, f, s, e, xy in rows]

    side_arm = [
        ("M1", "River Frome", "inlandRiver", "m0", "p", [(0, 30000), (0, 10000)]),
        ("M2", "River Frome", "inlandRiver", "p", "m2", [(0, 10000), (0, 3000)]),
        ("M3", "River Frome", "tidalRiver", "m2", "m3", [(0, 3000), (0, 0)]),
        ("AR", None, "inlandRiver", "p", "q", [(0, 10000), (5000, 9000)]),
    ]
    lake = [("L1", "Lake Beck", "inlandRiver", "l0", "l1", [(0, 30000), (0, 5000)]),
            ("L2", None, "lake", "l1", "l2", [(0, 5000), (0, 4000)])]
    unclear = [("Q1", "River Nowhere", "inlandRiver", "q0", "q1", [(0, 30000), (0, 5000)])]
    rows = shift(RATFYN, "_1") + shift(WINDRUSH, "_2") + shift(side_arm, "_3") + shift(lake, "_4") + shift(unclear, "_5")
    before = RiverNetwork(*RiverNetwork.oriented(_gdf(rows)), fix=False)
    after = RiverNetwork(*RiverNetwork.oriented(_gdf(rows)))
    df = _check().classify(before, after, 10_000.0)
    got = dict(zip(df["node"], df["cls"], strict=True))
    assert got == {"t_1": "c", "w1_2": "b", "q_3": "a", "l2_4": "d", "q1_5": "e"}
    assert df.set_index("node").at["t_1", "loop"]   # the gap repair's loop, before
    left = _check().classify(after, after, 10_000.0)
    assert sorted(left["cls"]) == ["a", "d", "e"]
