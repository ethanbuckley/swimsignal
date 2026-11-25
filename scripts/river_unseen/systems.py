"""River system and catchment size for the placed points of docs/RIVER-UNSEEN-PROTOCOL-2026-11.md (its amendment 1),
from positions and the river network only. No sample is read. Offline, in a scratch root:

    export DIPCAST_ROOT=<scratch copy of data/> DIPCAST_STATE=<scratch>/state DIPCAST_CACHE=<scratch>/cache
    python scripts/river_unseen/systems.py docs/river-unseen/points.csv docs/river-unseen/systems.csv \
        docs/river-unseen/rain_cells.csv

For every point that passed rules 1 and 2: the outlet it drains to (the terminal node of the network reached by going
downstream from where its trace starts; the smallest id when a braid reaches several), the length of channel
upstream of it, its size band, and its 0.1-degree rain cell. Points with the same outlet are one river system. The
third file lists every rain cell stage 2 needs: the kept points' cells and their upstream overflows' cells."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

BANDS = ((10.0, "small"), (100.0, "medium"), (float("inf"), "large"))   # km of channel upstream, upper ends


def band(upstream_km: float) -> str:
    return next(name for top, name in BANDS if upstream_km < top)


def outlet(graph, node: str) -> str:
    """The terminal node downstream of `node`; the smallest id if the network splits and reaches several."""
    seen, stack, ends = {node}, [node], []
    while stack:
        n = stack.pop()
        nxt = list(graph.successors(n))
        if not nxt:
            ends.append(n)
        for s in nxt:
            if s not in seen:
                seen.add(s)
                stack.append(s)
    return min(ends)


def main(points_csv: Path, out: Path, cells_out: Path) -> None:
    assert "DIPCAST_ROOT" in os.environ and "DIPCAST_STATE" in os.environ, "set a scratch DIPCAST_ROOT and DIPCAST_STATE"
    from dipcast import config
    from dipcast.ingest.rainfall import grid_cell
    from dipcast.model.forecast import _net, _overflows
    from dipcast.model.transport import locate_pin, upstream_overflows

    t = pd.read_csv(points_csv)
    t = t[t["rule1_count"] & t["rule2_on_river"]]
    net, ov = _net(), _overflows()
    rows, cells = [], set()
    for p in t.itertuples():
        pin = locate_pin(net, p.lon, p.lat, kind_hint="river")
        up_km = (net.upstream_length(pin.trace_node) + pin.trace_offset_m) / 1000.0
        cell = tuple(float(v) for v in grid_cell(p.lat, p.lon))
        if p.kept_point:
            up = upstream_overflows(net, pin, ov, velocity_ms=config.RIVER_VELOCITY_MS, max_km=config.MAX_UPSTREAM_KM)
            cells.add((*cell, "point"))
            cells.update((float(a), float(b), "overflow") for a, b in zip(*grid_cell(up["lat"].to_numpy(), up["lon"].to_numpy())))
        rows.append({"point": p.point, "label": p.label, "kept_point": bool(p.kept_point), "outlet": outlet(net.graph, pin.trace_node),
                     "upstream_km": round(up_km, 1), "band": band(up_km),
                     "cell_lat": cell[0], "cell_lon": cell[1],
                     "watercourse": p.watercourse, "kept_held_out": int(p.kept_held_out)})
    s = pd.DataFrame(rows)
    order = {o: i + 1 for i, o in enumerate(sorted(s["outlet"].unique()))}
    s.insert(3, "system", s["outlet"].map(lambda o: f"S{order[o]:02d}"))
    s.sort_values(["system", "upstream_km"]).to_csv(out, index=False)
    k = s[s["kept_point"]]
    print("placed points", len(s), "| systems", s["system"].nunique(), "| kept points", len(k), "in", k["system"].nunique(), "systems")
    print("kept points by band:", k["band"].value_counts().to_dict(), "| rows by band:",
          k.groupby("band")["kept_held_out"].sum().to_dict())
    print("kept points a system:", k.groupby("system").size().sort_values(ascending=False).head(8).to_dict())
    c = pd.DataFrame(sorted(cells), columns=["cell_lat", "cell_lon", "for"])
    c = c.groupby(["cell_lat", "cell_lon"])["for"].agg(lambda v: "+".join(sorted(set(v)))).reset_index()
    c.to_csv(cells_out, index=False)
    print("rain cells: kept points", k[["cell_lat", "cell_lon"]].drop_duplicates().shape[0], "| with overflows' cells", len(c))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
