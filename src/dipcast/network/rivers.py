"""River network from OS Open Rivers: snapping, upstream tracing, path lengths.

The OS Open Rivers product is a directed link/node network in British National
Grid (EPSG:27700, metres). Links carry `form` (inlandRiver, tidalRiver, lake,
canal) and a flow direction. We build a `networkx.DiGraph` whose nodes are
hydro-node IDs and whose edges are links oriented in the direction of flow.

Coordinates in this module are always (easting, northing) in metres unless a
function name says otherwise.
"""

from __future__ import annotations

import hashlib
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point

from dipcast import config

log = logging.getLogger(__name__)

_TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)
_TO_WGS = Transformer.from_crs(27700, 4326, always_xy=True)


def lonlat_to_bng(lon: float, lat: float) -> tuple[float, float]:
    return _TO_BNG.transform(lon, lat)


def bng_to_lonlat(x: float, y: float) -> tuple[float, float]:
    return _TO_WGS.transform(x, y)


@dataclass(frozen=True)
class Snap:
    """A point snapped onto a link."""

    link_id: str
    frac: float        # fraction along the link in flow direction, 0 = upstream end
    dist_m: float      # distance from the original point to the link
    form: str
    x: float           # snapped easting
    y: float           # snapped northing


class RiverNetwork:
    def __init__(self, links: gpd.GeoDataFrame, graph: nx.DiGraph, upstream_m: dict[str, float] | None = None,
                 repairs: dict[str, float] | None = None, fix: bool = True):
        """With `repairs` None the network is mended as it loads: the override list, the gap repairs
        and the rules in dipcast.network.fixes (`self.fixes` lists what each changed). `fix=False`
        makes the gap repairs alone, loops and all (scripts/check_network.py
        compares the two)."""
        self.links = links            # indexed by link id, EPSG:27700
        self.graph = graph
        self._sindex = links.sindex   # STRtree, built lazily by geopandas
        self.fixes: list = []
        if repairs is not None:
            self.repairs = repairs
        elif not fix:
            self.repairs = self._repair_gaps(no_loops=False)
        else:
            from dipcast.network import fixes as nf
            pts = self.node_points()
            self.repairs = {}
            self.fixes = nf.apply_overrides(self, pts)
            skipped: list = []
            self.repairs.update(self._repair_gaps(pts=pts, skipped=skipped))
            self.fixes += nf.apply_rules(self, pts)
            self.repairs.update(nf.restore_loop_repairs(self, pts, skipped))
            if self.fixes:
                kinds = pd.Series([f"{f.rule} ({f.kind})" for f in self.fixes]).value_counts().to_dict()
                log.info("network fixes: %s", ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
        self.upstream_m = upstream_m if upstream_m is not None else self._compute_upstream_m()

    def topology_key(self) -> str:
        """A short hash of what the load changed: every repair edge and its length, every fix. The
        network file's hash does not change when the repairs or fixes do, so the click-anywhere
        cache (scripts/build_any_point.py) is keyed by both."""
        h = hashlib.sha256()
        for eid, length in sorted(self.repairs.items()):
            h.update(f"{eid} {length:.1f}\n".encode())
        for f in sorted((f.kind, f.link, f.a, f.b) for f in self.fixes):
            h.update((" ".join(f) + "\n").encode())
        return h.hexdigest()[:8]

    def node_points(self) -> gpd.GeoSeries:
        """One point per hydro node, from the link ends (nodes carry no geometry of their own)."""
        starts = pd.DataFrame({"node": self.links["start_node"].to_numpy(),
                               "geom": [Point(l.coords[0]) for l in self.links.geometry]})
        ends = pd.DataFrame({"node": self.links["end_node"].to_numpy(),
                             "geom": [Point(l.coords[-1]) for l in self.links.geometry]})
        pts = pd.concat([starts, ends]).drop_duplicates("node").set_index("node")["geom"]
        return gpd.GeoSeries(pts.values, index=pts.index, crs=27700)

    def _repair_gaps(self, max_gap_m: float = 60.0, min_upstream_m: float = 1_000.0, no_loops: bool = True,
                     pts: gpd.GeoSeries | None = None, skipped: list | None = None) -> dict[str, float]:
        """OS Open Rivers leaves small breaks at weirs, mills and culverts: a channel
        ends in a dead-end node a few metres from where the next section starts as
        a fresh 'headwater'. Join each headwater to a foreign dead-end within
        `max_gap_m` that carries real upstream network. Adds graph edges with
        form 'repair' and no geometry; returns {edge_id: length_m}.

        A headwater whose own water already reaches that dead end is not joined to it (`no_loops`):
        the join would make a loop. 62 of the 653 joins would be such loops, among them the
        Hampshire Avon at Ratfyn, where a 42 m stub flows into the dead end its head would be joined
        from, and the loop drains nowhere. Each one left out is added to `skipped` as (dead end,
        headwater, length): dipcast.network.fixes.restore_loop_repairs puts it back after the rules
        when the dead end still has no outlet and the loop has a way out to the sea."""
        g = self.graph
        pts = self.node_points() if pts is None else pts
        heads = [n for n in g.nodes if g.in_degree(n) == 0 and n in pts.index]
        sinks = {n for n in g.nodes if g.out_degree(n) == 0 and g.in_degree(n) > 0}
        # provisional upstream lengths (before repairs) to judge which sinks matter
        prov = self._compute_upstream_m(quiet=True)
        sink_pts = pts[pts.index.isin([n for n in sinks if prov.get(n, 0.0) >= min_upstream_m])]
        repairs: dict[str, float] = {}
        if sink_pts.empty:
            return repairs
        loops = 0
        for h in heads:
            hp = pts[h]
            idx = sink_pts.sindex.query(hp.buffer(max_gap_m), predicate="intersects")
            if len(idx) == 0:
                continue
            cand = sink_pts.iloc[idx]
            d = cand.distance(hp)
            sink = d.idxmin()
            if sink == h or g.has_edge(sink, h):
                continue
            if no_loops and nx.has_path(g, h, sink):
                loops += 1
                if skipped is not None:
                    skipped.append((sink, h, float(max(d.min(), 1.0))))
                continue
            eid = f"repair:{sink[:8]}->{h[:8]}"
            g.add_edge(sink, h, link=eid, length=float(max(d.min(), 1.0)), form="repair")
            repairs[eid] = float(max(d.min(), 1.0))
        log.info("network repairs: %d gaps joined (<= %.0f m)%s", len(repairs), max_gap_m,
                 f"; {loops} left alone that would have made a loop" if loops else "")
        return repairs

    def _compute_upstream_m(self, quiet: bool = False) -> dict[str, float]:
        """Total network length upstream of every node, in one topological pass.
        Cycles (braided channels with inconsistent directions) are linearised in
        node-ID order. This is an approximation, but must not change between processes."""
        g = self.graph
        up: dict[str, float] = {}
        # A topological order by Kahn's algorithm; the nodes it cannot place are in a cycle or below
        # one, and only those are condensed (a handful in OS data: condensing the whole graph took a
        # second or two, and the fixes at load recompute these lengths several times). Any
        # topological order gives the same sums, so this matches condensing the whole graph.
        indeg = {n: d for n, d in g.in_degree()}
        ready = [n for n, d in indeg.items() if d == 0]
        order = []
        while ready:
            n = ready.pop()
            order.append(n)
            for s in g.successors(n):
                indeg[s] -= 1
                if indeg[s] == 0:
                    ready.append(s)
        if len(order) < len(indeg):
            cyc = nx.condensation(g.subgraph([n for n, d in indeg.items() if d > 0]))
            for comp in nx.topological_sort(cyc):
                order.extend(sorted(cyc.nodes[comp]["members"]))
        for n in order:
            up[n] = sum(up.get(p, 0.0) + g.edges[p, n]["length"] for p in g.predecessors(n) if p in up)
        if not quiet:
            log.info("upstream lengths computed for %d nodes", len(up))
        return up

    # ------------------------------------------------------------------ build
    @classmethod
    def from_links(cls, links: gpd.GeoDataFrame, fix: bool = True) -> RiverNetwork:
        """The network from OS Open Rivers' watercourse_link layer (or a small frame with the
        same columns, as the tests build)."""
        return cls(*cls.oriented(links), fix=fix)

    @staticmethod
    def oriented(links: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, nx.DiGraph]:
        """OS Open Rivers' links indexed by id and turned to the direction of flow, and the graph of
        them, as data/processed/river_network.pkl holds them: before any repair or fix."""
        links = links.set_index("id", drop=False)
        # Orient every link in the direction of flow.
        rev = links["flow_direction"].eq("in opposite direction")
        if rev.any():
            s, e = links.loc[rev, "start_node"].copy(), links.loc[rev, "end_node"].copy()
            links.loc[rev, "start_node"], links.loc[rev, "end_node"] = e.values, s.values
            links.loc[rev, "geometry"] = links.loc[rev, "geometry"].reverse()
        links["length"] = links.geometry.length
        g = nx.DiGraph()
        g.add_edges_from(
            zip(links["start_node"], links["end_node"], strict=True),
        )
        # Store link id and length on edges (one link per node pair in practice).
        nx.set_edge_attributes(
            g,
            {(s, e): {"link": i, "length": ln, "form": f}
             for s, e, i, ln, f in zip(links["start_node"], links["end_node"], links.index,
                                       links["length"], links["form"], strict=True)},
        )
        log.info("network: %d links, %d nodes", len(links), g.number_of_nodes())
        return links, g

    @classmethod
    def load(cls, path: Path = config.PROCESSED / "river_network.pkl", fix: bool = True) -> RiverNetwork:
        """The network from the pickle, mended as it loads. The pickle holds the links and graph as
        OS draws them (RiverNetwork.oriented), never a mended copy: the repairs and fixes are made
        afresh at every load, so a change to them needs no new pickle (the data-v1 release)."""
        if not path.exists():
            links, g = cls.oriented(gpd.read_file(config.RIVERS_GPKG, layer="watercourse_link"))
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump({"links": links, "graph": g}, f, protocol=5)
            return cls(links, g, fix=fix)
        with open(path, "rb") as f:
            d = pickle.load(f)
        return cls(d["links"], d["graph"], fix=fix)

    # ------------------------------------------------------------------ snap
    def snap_xy(self, x: float, y: float, max_m: float = config.SNAP_MAX_M,
                forms: tuple[str, ...] | None = None) -> Snap | None:
        pt = Point(x, y)
        cand = self.links if forms is None else self.links[self.links["form"].isin(forms)]
        if cand.empty:
            return None
        idx = cand.sindex.nearest(pt, return_all=False, max_distance=max_m)
        if idx.shape[1] == 0:
            return None
        row = cand.iloc[idx[1, 0]]
        geom = row.geometry
        frac = float(geom.project(pt, normalized=True))
        sp = geom.interpolate(frac, normalized=True)
        return Snap(link_id=row["id"], frac=frac, dist_m=float(geom.distance(pt)),
                    form=row["form"], x=sp.x, y=sp.y)

    def snap_lonlat(self, lon: float, lat: float, **kw) -> Snap | None:
        x, y = lonlat_to_bng(lon, lat)
        return self.snap_xy(x, y, **kw)

    def candidates_xy(self, x: float, y: float, max_m: float) -> pd.DataFrame:
        """All links within `max_m` of a point, with distance, nearest first."""
        pt = Point(x, y)
        idx = self.links.sindex.query(pt.buffer(max_m), predicate="intersects")
        if len(idx) == 0:
            return self.links.iloc[0:0].assign(dist_m=pd.Series(dtype=float))
        cand = self.links.iloc[idx].copy()
        cand["dist_m"] = cand.geometry.distance(pt)
        return cand[cand["dist_m"] <= max_m].sort_values("dist_m")

    def snap_many(self, lon: np.ndarray, lat: np.ndarray, max_m: float = config.SNAP_MAX_M) -> pd.DataFrame:
        """Vectorised snap for many points. Returns a frame aligned to the input."""
        x, y = _TO_BNG.transform(lon, lat)
        pts = gpd.GeoSeries(gpd.points_from_xy(x, y), crs=27700)
        idx = self.links.sindex.nearest(pts, return_all=False, max_distance=max_m)
        out = pd.DataFrame({"link_id": pd.Series([None] * len(pts), dtype=object),
                            "frac": np.nan, "dist_m": np.nan, "form": None})
        if idx.shape[1]:
            q, t = idx[0], idx[1]
            geoms = self.links.geometry.values[t]
            p = pts.values[q]
            out.loc[q, "link_id"] = self.links.index.values[t]
            out.loc[q, "frac"] = [g.project(pp, normalized=True) for g, pp in zip(geoms, p, strict=True)]
            out.loc[q, "dist_m"] = [g.distance(pp) for g, pp in zip(geoms, p, strict=True)]
            out.loc[q, "form"] = self.links["form"].values[t]
        return out

    # ------------------------------------------------------------------ trace
    def link_nodes(self, link_id: str) -> tuple[str, str]:
        r = self.links.loc[link_id]
        return r["start_node"], r["end_node"]

    def upstream_edges(self, node: str, max_length_m: float | None = None) -> dict[str, float]:
        """All links upstream of `node`, mapped to the along-network distance (m)
        from the link's downstream end to `node`. Capped by path distance."""
        cap = np.inf if max_length_m is None else max_length_m
        dist = {node: 0.0}
        out: dict[str, float] = {}
        stack = [node]
        g = self.graph
        while stack:
            n = stack.pop()
            dn = dist[n]
            for pred in g.predecessors(n):
                ed = g.edges[pred, n]
                d_pred = dn + ed["length"]
                lid = ed["link"]
                if lid not in out or dn < out[lid]:
                    out[lid] = dn
                if d_pred <= cap and d_pred < dist.get(pred, np.inf):
                    dist[pred] = d_pred
                    stack.append(pred)
        return out

    def upstream_length(self, node: str, max_length_m: float | None = None) -> float:
        """Total upstream network length (m): a proxy for catchment area / flow."""
        if max_length_m is None:
            return float(self.upstream_m.get(node, 0.0))
        edges = self.upstream_edges(node, max_length_m)
        real = [e for e in edges if not e.startswith("repair:")]
        total = float(self.links.loc[real, "length"].sum()) if real else 0.0
        return total + sum(self.repairs.get(e, 0.0) for e in edges if e.startswith("repair:"))

    def link_upstream_m(self, link_id: str) -> float:
        """Upstream network length arriving at the upstream end of a link."""
        return float(self.upstream_m.get(self.links.loc[link_id, "start_node"], 0.0))

    def downstream_nodes(self, node: str, max_length_m: float) -> dict[str, float]:
        """Nodes reachable downstream within a path distance, with distances."""
        dist = {node: 0.0}
        stack = [node]
        g = self.graph
        while stack:
            n = stack.pop()
            for succ in g.successors(n):
                d = dist[n] + g.edges[n, succ]["length"]
                if d <= max_length_m and d < dist.get(succ, np.inf):
                    dist[succ] = d
                    stack.append(succ)
        return dist

    def lake_component(self, link_id: str) -> set[str]:
        """All lake-form links forming the same water body as `link_id`."""
        if self.links.loc[link_id, "form"] != "lake":
            return {link_id}
        seen: set[str] = set()
        frontier = [link_id]
        while frontier:
            lid = frontier.pop()
            if lid in seen:
                continue
            seen.add(lid)
            s, e = self.link_nodes(lid)
            for n in (s, e):
                for a, b in list(self.graph.in_edges(n)) + list(self.graph.out_edges(n)):
                    nb = self.graph.edges[a, b]["link"]
                    if nb not in seen and nb in self.links.index and self.links.loc[nb, "form"] == "lake":
                        frontier.append(nb)
        return seen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    net = RiverNetwork.load()
    # Smoke test: the Lune at Kirkby Lonsdale (Devil's Bridge).
    s = net.snap_lonlat(-2.5945, 54.1995)
    print("snap:", s)
    if s:
        start, end = net.link_nodes(s.link_id)
        up = net.upstream_edges(start, max_length_m=config.MAX_UPSTREAM_KM * 1000)
        print("upstream links within cap:", len(up), "upstream length km:",
              round(net.upstream_length(start) / 1000, 1))
