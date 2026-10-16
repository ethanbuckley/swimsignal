"""The page against the API on seeded random clicks (docs/ANYPOINT-LINES-2026-10.md, docs/ANYPOINT-LAKES-2026-10.md).

Builds the click-anywhere files into OUT/files, and writes OUT/clicks.json with the API's answers. parity.cjs then places the same clicks with anypoint.js and sorts the misses by cause.
Never run it against the main checkout's state: it writes overflows.parquet and the upstream table.

    DIPCAST_ROOT=<scratch root> DIPCAST_STATE=<scratch state> PYTHONPATH=<worktree>/src \\
        python scripts/anypoint_shore_check/sweep.py <worktree> <out> 400 18
    node scripts/anypoint_shore_check/parity.cjs src/dipcast/site/anypoint.js <out>/files <out>/clicks.json \
        data/raw/outside_england.json

Arguments: worktree, out dir, clicks per set (the shore set has half), seed. The runs in
docs/ANYPOINT-LAKES-2026-10.md also wrote files with 30 m river lines, before #225 removed that option. Three sets:
  on     points on river links that have an overflow upstream, in proportion to length;
  off    the same, then 0 to 200 m in a random direction;
  shore  a random WFD lake, a random point on its outline, then 0 to 250 m in a random direction.
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point

WT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 400
SEED = int(sys.argv[4]) if len(sys.argv) > 4 else 16
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(WT / "src"))
from dipcast import config  # noqa: E402
from dipcast.model import transport  # noqa: E402
from dipcast.network.rivers import RiverNetwork, bng_to_lonlat  # noqa: E402
from dipcast.overflows import load_overflows  # noqa: E402

spec = importlib.util.spec_from_file_location("build_any_point", WT / "scripts" / "build_any_point.py")
bap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bap)

t0 = time.time()
net = RiverNetwork.load()
ov = load_overflows(net, rebuild=True)
lakes = transport._lakes()
table, stats = bap.upstream_table(net, ov, lakes, "sweep", "sweep", OUT / "cache.pkl")
print("table", stats, f"{time.time() - t0:.0f} s", flush=True)
d = OUT / "files"
meta = bap.write_files(d, net, ov, table, "sweep")
cfg = {"network": "sweep", "tile_deg": bap.TILE_DEG, "tiles": meta["tiles"], "snap_m": transport.PIN_SNAP_M,
       "lake_snap_m": transport.LAKE_SNAP_M, "lake_shore_m": transport.LAKE_SHORE_M, "lake_bias": transport.LAKE_BIAS}
(d / "tiles.json").write_text(json.dumps(cfg))
sizes = {k: sum(f.stat().st_size for f in (d / k).rglob("*") if f.is_file()) for k in ("link_index", "links", "lake_outlines")}
sizes["lakes.json"] = (d / "lakes.json").stat().st_size
sizes["all"] = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
sizes["tiles"] = len(meta["tiles"])
print("files", sizes, meta["counts"], f"{time.time() - t0:.0f} s", flush=True)

links = net.links
rec = links.loc[[lid for lid in table["records"] if links.at[lid, "form"] in transport.RIVER_FORMS]]
rng = np.random.default_rng(SEED)
pick = rng.choice(len(rec), size=2 * N, p=(rec["length"] / rec["length"].sum()).to_numpy())
fr = rng.random(2 * N)
ang, off = rng.random(2 * N) * 2 * np.pi, rng.random(2 * N) * 200
ovd = ov.drop(columns="snap_confidence")
v = transport.river_velocity(None)


def answer(kind: str, x: float, y: float, **extra) -> dict:
    lon, lat = bng_to_lonlat(x, y)
    pin = transport.locate_pin(net, lon, lat)
    up = transport.upstream_overflows(net, pin, ovd, velocity_ms=v)
    poly = transport._lake_polygon_at(x, y)
    return {"set": kind, "lat": float(lat), "lon": float(lon), "mode": pin.mode, "watercourse": pin.watercourse,
            "link": pin.snap.link_id if pin.snap else None, "lake_source": pin.lake_source,
            "adopted": bool(pin.adopted_main_channel),
            # The WFD lake within 150 m (whether or not the API placed the click in it), and how far.
            "wfd": str(poly["wb_id"]) if poly is not None else None,
            "wfd_m": float(poly.geometry.distance(Point(x, y))) if poly is not None else None,
            "rows": [{"site_id": r.site_id, "distance_m": float(r.distance_m), "lake_distance_m": float(r.lake_distance_m),
                      "dilution": float(r.dilution)} for r in up.itertuples()], **extra}


clicks = []
for k, (i, f) in enumerate(zip(pick, fr, strict=True)):
    p = rec.geometry.iloc[i].interpolate(f, normalized=True)
    x, y = p.x, p.y
    kind = "on" if k < N else "off"
    if kind == "off":
        x, y = x + off[k] * np.cos(ang[k]), y + off[k] * np.sin(ang[k])
    clicks.append(answer(kind, x, y))
wl = lakes[lakes.geometry.notna()]
for i in rng.integers(0, len(wl), size=N // 2):
    g = wl.geometry.iloc[i]
    ext = (g.geoms[0] if hasattr(g, "geoms") else g).exterior
    p = ext.interpolate(rng.random(), normalized=True)
    a, dd = rng.random() * 2 * np.pi, rng.random() * 250
    clicks.append(answer("shore", p.x + dd * np.cos(a), p.y + dd * np.sin(a), from_lake=str(wl["wb_id"].iloc[i])))
lno = pd.Series(np.arange(len(links)), index=links.index.sort_values())
for c in clicks:
    c["link_lno"] = int(lno[c["link"]]) if c["link"] else None
(OUT / "clicks.json").write_text(json.dumps({"seed": SEED, "ids": list(table["placements"].index), "sizes": sizes,
    "od": {"assumptions": {"max_upstream_km": config.MAX_UPSTREAM_KM, "l0_m": transport.L0_M,
                           "lake_area_halving_km2": transport.LAKE_A0_KM2}}, "clicks": clicks}))
print("clicks", len(clicks), f"{time.time() - t0:.0f} s", flush=True)
