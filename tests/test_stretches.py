"""An outing's finish (src/dipcast/stretches.py): the route down from one listed river spot to another, and each
overflow on it, on a side stream joining it, or above the start, on a small network drawn here."""

from types import SimpleNamespace

import networkx as nx
import pandas as pd

from dipcast import stretches as ST

# A river n0 -> n4 in four 1 km links, a 500 m tributary joining at n2, and a canal leaving at n1 for n3 that
# water must not follow. The start pin is half way down L01, the finish half way down L34.
LINKS = [("L01", "n0", "n1", 1000, "inlandRiver"), ("L12", "n1", "n2", 1000, "inlandRiver"),
         ("L23", "n2", "n3", 1000, "inlandRiver"), ("L34", "n3", "n4", 1000, "inlandRiver"),
         ("T", "t0", "n2", 500, "inlandRiver"), ("C", "n1", "n3", 200, "canal")]


def net(lake: str | None = None):
    links = pd.DataFrame([{"id": i, "start_node": a, "end_node": b, "length": float(m), "form": "lake" if i == lake else f}
                          for i, a, b, m, f in LINKS]).set_index("id")
    g = nx.DiGraph()
    for i, r in links.iterrows():
        g.add_edge(r.start_node, r.end_node, link=i, length=r.length, form=r.form)
    return SimpleNamespace(graph=g, links=links, repairs={}, link_nodes=lambda lid: tuple(links.loc[lid, ["start_node", "end_node"]]))


def pin(link, frac):
    return SimpleNamespace(snap=SimpleNamespace(link_id=link, frac=frac))


A, B = pin("L01", 0.5), pin("L34", 0.5)
OVERFLOWS = pd.DataFrame([("above", "L01", 0.2), ("start-link", "L01", 0.8), ("route", "L12", 0.5), ("side", "T", 0.5),
                          ("below", "L34", 0.9)], columns=["site_id", "link_id", "frac"])


def test_the_route_goes_down_the_river_not_the_canal():
    rt = ST.route(net(), A, B)
    assert round(rt["m"]) == 3000   # 500 + 1000 + 1000 + 500, not by the 200 m canal
    assert rt["inner"] == {"L12", "L23"}
    assert ST.route(net(), B, A) is None   # never up the river
    assert ST.route(net(), A, B, max_km=2.5) is None   # longer than allowed: no finish, not a guess
    assert ST.route(net(lake="L23"), A, B) is None   # through a lake: not a stretch of river


def test_each_overflow_is_on_the_route_or_where_it_joins():
    n, rt = net(), ST.route(net(), A, B)
    assert [s for s, l, f in OVERFLOWS.itertuples(index=False) if ST.on_route(rt, l, f)] == ["start-link", "route"]
    assert round(ST.km_below_start(n, rt, "L01", 0.8), 1) == 0.3
    assert round(ST.km_below_start(n, rt, "L12", 0.5), 1) == 1.0
    assert ST.joins_at(n, rt, "T", 60_000) == 1.5   # meets the route at n2, 1.5 km below the start


def test_stretches_group_the_finish_s_overflows(monkeypatch):
    spots = pd.DataFrame([{"id": "a", "name": "A", "kind": "river"}, {"id": "b", "name": "B", "kind": "river"},
                          {"id": "lake", "name": "L", "kind": "lake"}])
    monkeypatch.setattr(ST, "_place", lambda n, r: {"a": A, "b": B}.get(r.id))
    up = {"a": [{"site_id": "above"}], "b": [{"site_id": s} for s in ("above", "start-link", "route", "side")], "lake": []}
    out = ST.stretches(net(), spots, up, OVERFLOWS)
    assert list(out) == ["a"]   # nothing is downstream of b, and a lake is never a start
    assert out["a"] == [{"to": "b", "km": 3.0, "route": [["start-link", 0.3], ["route", 1.0]], "side": [["side", 1.5]], "above": 1}]
    results = [{"id": "a"}, {"id": "b"}]
    monkeypatch.setattr(ST, "stretches", lambda *a, **k: out)
    assert ST.attach(results, spots, up, net(), OVERFLOWS) == 1
    assert results[0]["downstream"] == [["b", 3.0]] and "downstream" not in results[1]
