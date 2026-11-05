"""Where does the pollution go? The connected upstream network of every listed swim spot, for Research Lab exhibit 2.

For each spot in spots.csv and spots-osm.csv: the build's own pin (transport.locate_pin), its overflows upstream with
the forecast's own distance, travel time and weight (transport.upstream_overflows, the production settings), and the
river lines that join those overflows to the spot (OS Open Rivers links, walked down the network from each overflow).
Distances are along the mapped network; travel times and weights are the model's, never measurements.

Offline. It imports dipcast's network code, so it must run with scratch DIPCAST_ROOT and DIPCAST_STATE whose data
folders hold links to the cached inputs (AGENTS.md); any file the loader writes then lands in scratch. Writes only to
prototypes/research-lab/assets/paths/. The site build runs export() itself at every build, with its own network
and overflows, into the Lab's copy at lab/assets/paths/ (build_site.write_lab_paths): this run only refreshes the copy
kept in the repository for running the Lab locally.

    DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch>/state uv run python scripts/lab_pollution_paths.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = REPO / "prototypes" / "research-lab" / "assets" / "paths"
SIMPLIFY_M = 25          # line simplification, metres: drawing only
ROUND = 5                # decimal places of lon/lat (about 1 m)

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

from dipcast import config  # noqa: E402
from dipcast.model.transport import locate_pin, river_velocity, spot_hints, upstream_overflows  # noqa: E402
from dipcast.network.rivers import bng_to_lonlat  # noqa: E402


def path_links(net, start_node: str, over_links: list[str], allowed: set[str]) -> set[str]:
    """Links on the way from each overflow's link down to start_node, inside `allowed` (the upstream set)."""
    g, keep = net.graph, set()
    by_link = {}
    for (s, e, d) in g.edges(data=True):
        if d["link"] in allowed:
            by_link[d["link"]] = (s, e)
    reach_spot: dict[str, bool] = {}
    for lid in over_links:
        if lid not in by_link:
            continue
        # breadth-first down the graph from the overflow's link, keeping parents, until the spot's node
        s0, e0 = by_link[lid]
        parent = {e0: None}
        q = deque([e0])
        found = e0 == start_node
        while q and not found:
            n = q.popleft()
            for succ in g.successors(n):
                link = g.edges[n, succ]["link"]
                if link not in allowed or succ in parent:
                    continue
                parent[succ] = (n, link)
                if succ == start_node:
                    found = True
                    break
                q.append(succ)
        reach_spot[lid] = found
        if found:
            keep.add(lid)
            n = start_node
            while parent.get(n):
                n, link = parent[n]
                keep.add(link)
    return keep


def line_lonlat(geom) -> list[list[float]]:
    g = geom.simplify(SIMPLIFY_M)
    return [[round(v, ROUND) for v in bng_to_lonlat(x, y)] for x, y in g.coords]


def spots_frame(repo: Path = REPO):
    """Every listed spot, as the build lists them: spots.csv, then spots-osm.csv."""
    import pandas as pd
    return pd.concat([pd.read_csv(repo / f) for f in ("spots.csv", "spots-osm.csv") if (repo / f).exists()], ignore_index=True)


def export(folder: Path, spots, net, ov, inputs: dict[str, str], say=print) -> dict:
    """One file a spot in `folder`, and index.json; returns the index. The site build calls this with its own network and
    overflow table (build_site.write_lab_paths); run alone, main() calls it with the cached ones."""
    t0 = time.time()
    folder.mkdir(parents=True, exist_ok=True)
    index = []
    for r in spots.itertuples(index=False):
        rec = {"id": r.id, "name": r.name, "lat": float(r.lat), "lon": float(r.lon), "kind": r.kind,
               "area": getattr(r, "area", None) if isinstance(getattr(r, "area", None), str) else None}
        try:
            kind, river = spot_hints(r.kind, r.river if isinstance(r.river, str) else "")
            pin = locate_pin(net, float(r.lon), float(r.lat), kind_hint=kind, river_hint=river, name=r.name)
            up = upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None))
        except Exception as e:  # noqa: BLE001 - one spot that cannot be placed is recorded, the rest still run
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
            index.append(rec)
            continue
        if pin.trace_node is None:   # not on the mapped network (a sea or ground pin): no upstream to draw
            rec.update({"mode": pin.mode, "overflows": len(up), "note": "not on the mapped river network"})
            index.append(rec)
            continue
        allowed = set(net.upstream_edges(pin.trace_node, config.MAX_UPSTREAM_KM * 1000))
        allowed |= set(getattr(pin, "lake_links", None) or [])
        links = path_links(net, pin.trace_node, list(up["link_id"]) if "link_id" in up else [], allowed)
        geo = net.links.loc[sorted(x for x in links if x in net.links.index)]   # sorted: the same file every build
        lines = [{"form": f, "coords": line_lonlat(gm)} for f, gm in zip(geo["form"], geo.geometry, strict=True)]
        cols = {"site_id": "id", "site_name": "name", "company": "company", "receiving_watercourse": "water",
                "lat": "lat", "lon": "lon", "lta_spills": "spills_a_year", "travel_h": "travel_h", "weight": "weight",
                "decay": "decay", "dilution": "dilution"}
        ovs = []
        for o in up.sort_values("weight", ascending=False).itertuples(index=False):
            d = {v: getattr(o, k, None) for k, v in cols.items()}
            d["distance_km"] = round(float(o.distance_m + getattr(o, "lake_distance_m", 0.0)) / 1000, 2)
            d["lake_km"] = round(float(getattr(o, "lake_distance_m", 0.0)) / 1000, 2)
            for k in ("travel_h", "weight", "decay", "dilution", "spills_a_year"):
                if d[k] is not None and d[k] == d[k]:
                    d[k] = round(float(d[k]), 5 if k in ("weight", "decay", "dilution") else 1)
                else:
                    d[k] = None
            d["lat"], d["lon"] = round(float(d["lat"]), ROUND), round(float(d["lon"]), ROUND)
            ovs.append(d)
        px, py = bng_to_lonlat(pin.x, pin.y)
        out = {**rec, "pin": {"mode": pin.mode, "lon": round(px, ROUND), "lat": round(py, ROUND)},
               "overflows": ovs, "lines": lines}
        (folder / f"{r.id}.json").write_text(json.dumps(out, separators=(",", ":")) + "\n")
        rec.update({"mode": pin.mode, "overflows": len(ovs), "with_path": sum(1 for o in up.get("link_id", []) if o in links),
                    "nearest_h": min((o["travel_h"] for o in ovs if o["travel_h"] is not None), default=None),
                    "total_weight": round(sum(o["weight"] or 0 for o in ovs), 4)})
        index.append(rec)
        say(f"{r.id}: {len(ovs)} overflows, {len(lines)} lines")
    meta = {"made": datetime.now(UTC).isoformat(timespec="seconds"),
            "settings": {"velocity_mode": config.VELOCITY_MODE, "dilution_mode": config.DILUTION_MODE,
                         "lake_path_mode": config.LAKE_PATH_MODE, "t90_h": config.T90_HOURS,
                         "river_velocity_ms": config.RIVER_VELOCITY_MS, "max_upstream_km": config.MAX_UPSTREAM_KM},
            "inputs": inputs,
            "credit": ["Contains OS data © Crown copyright and database right 2026 (OS Open Rivers, OGL v3.0)",
                       "Overflow positions and annual spill counts: Environment Agency Event Duration Monitoring returns, OGL v3.0"],
            "simplify_m": SIMPLIFY_M, "seconds": round(time.time() - t0), "spots": index}
    (folder / "index.json").write_text(json.dumps(meta, indent=1) + "\n")
    say(f"done: {len(index)} spots, {sum(1 for x in index if 'error' in x)} errors, {time.time() - t0:.0f}s")
    return meta


def overview(out: Path = OUT, say=print) -> None:
    """Every spot's lines merged into one small file for the title map: coordinates at 3 decimals (about 100 m),
    repeated points dropped, a reach shared by several spots kept once."""
    seen, lines = set(), []
    for f in sorted(out.glob("*.json")):
        if f.name in ("index.json", "overview.json"):
            continue
        for ln in json.loads(f.read_text())["lines"]:
            pts = []
            for lon, lat in ln["coords"]:
                q = [round(lon, 3), round(lat, 3)]
                if not pts or pts[-1] != q:
                    pts.append(q)
            key = json.dumps(pts)
            if len(pts) > 1 and key not in seen:
                seen.add(key)
                lines.append(pts)
    (out / "overview.json").write_text(json.dumps({"lines": lines}, separators=(",", ":")) + "\n")
    say(f"overview: {len(lines)} lines")


def main() -> None:
    assert os.environ.get("DIPCAST_ROOT") and os.environ.get("DIPCAST_STATE"), "set scratch DIPCAST_ROOT and DIPCAST_STATE"
    from dipcast.model.forecast import _net, _overflows
    t0 = time.time()
    net, ov = _net(), _overflows()
    print(f"loaded network and {len(ov)} overflows in {time.time() - t0:.0f}s", flush=True)
    export(OUT, spots_frame(), net, ov, {
        "overflows": "data/processed/overflows.parquet (the cached overflow table)",
        "network": "OS Open Rivers via data/processed/river_network.pkl, mended as the build mends it"},
        say=lambda m: print(m, flush=True))
    overview(OUT)


if __name__ == "__main__":
    main()
