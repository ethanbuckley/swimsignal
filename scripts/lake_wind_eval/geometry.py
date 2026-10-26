"""docs/LAKE-WIND-TEST-2026-10.md: where overflow water enters each lake bathing water's lake, and the bearing the
wind is projected on. Transport only: no rain, spill model, wind or E. coli.

    geometry.py <out.csv>

Each inland bathing water is placed as eval_pins.bathing_water_pin places it. For those placed in a lake, every
overflow upstream (transport.upstream_overflows at main's defaults) is walked to the point where its water enters the
spot's lake (transport._walk_to_lake, as report.py of the lake direction test does). Overflows that share an entry
point (within ENTRY_TOL_M) are one inflow, and the inflow's weight is the sum of their transport weights. The inflow
with the largest weight is the one the wind is projected from. Its bearing to the pin is the initial geodesic bearing,
degrees clockwise from true north, so it compares with Open-Meteo's wind direction without a grid correction.

Writes one row per lake bathing water and inflow, with `chosen` marking the inflow used.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod, Transformer

W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "scripts"))
import eval_pins

from dipcast import config
from dipcast.model import transport as T
from dipcast.network.rivers import RiverNetwork
from dipcast.overflows import load_overflows

ENTRY_TOL_M = 50.0   # overflows that join the lake through the same inflow link end within a few metres
TO_WGS84 = Transformer.from_crs(27700, 4326, always_xy=True)
GEOD = Geod(ellps="WGS84")


def bearing_deg(x0: float, y0: float, x1: float, y1: float) -> float:
    """Initial geodesic bearing from BNG point 0 to point 1, 0 to 360 clockwise from true north."""
    lon0, lat0 = TO_WGS84.transform(x0, y0)
    lon1, lat1 = TO_WGS84.transform(x1, y1)
    az, _, _ = GEOD.inv(lon0, lat0, lon1, lat1)
    return float(az % 360.0)


def inflows(net: RiverNetwork, ov: pd.DataFrame, bw_id: str, name: str, lon: float, lat: float) -> pd.DataFrame:
    pin = eval_pins.bathing_water_pin(net, bw_id, lon, lat)
    if pin.mode != "lake":
        return pd.DataFrame()
    a = T.upstream_overflows(net, pin, ov, velocity_ms=T.river_velocity(None))
    if a.empty:
        return pd.DataFrame()
    link_dist, _ = T.upstream_lengths(net, pin.trace_node, config.MAX_UPSTREAM_KM * 1000.0)
    on_path = set(link_dist)
    e = np.asarray([T._walk_to_lake(net, r.link_id, r.frac, pin.lake_links, on_path)[1] for r in a.itertuples()],
                   dtype=float)
    # Group entries: each overflow joins the first group whose entry is within ENTRY_TOL_M of its own.
    group, heads = np.zeros(len(e), dtype=int), []
    for i, (x, y) in enumerate(e):
        for g, (hx, hy) in enumerate(heads):
            if np.hypot(x - hx, y - hy) <= ENTRY_TOL_M:
                group[i] = g
                break
        else:
            heads.append((x, y)); group[i] = len(heads) - 1
    d = a.assign(group=group, entry_x=e[:, 0], entry_y=e[:, 1])
    g = d.groupby("group").agg(entry_x=("entry_x", "first"), entry_y=("entry_y", "first"), weight=("weight", "sum"),
                               overflows=("site_id", "size"), lake_distance_m=("lake_distance_m", "min"),
                               names=("site_name", lambda s: "; ".join(sorted(set(map(str, s))))))
    g["share"] = g.weight / g.weight.sum()
    g["line_m"] = np.hypot(g.entry_x - pin.x, g.entry_y - pin.y)
    g["bearing_deg"] = [bearing_deg(x, y, pin.x, pin.y) for x, y in zip(g.entry_x, g.entry_y, strict=True)]
    g["chosen"] = False
    g.loc[g.weight.idxmax(), "chosen"] = True
    return g.reset_index(drop=True).assign(bw_id=bw_id, bw_name=name, pin_x=pin.x, pin_y=pin.y,
                                           lake_area_km2=pin.lake_area_km2)


def main(out: str) -> None:
    net = RiverNetwork.load()
    ov = load_overflows(net)
    bw = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id")
    parts = [inflows(net, ov, r.bw_id, r.name, float(r.lon), float(r.lat)) for r in bw.itertuples()]
    df = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    cols = ["bw_id", "bw_name", "chosen", "share", "weight", "overflows", "line_m", "lake_distance_m", "bearing_deg",
            "entry_x", "entry_y", "pin_x", "pin_y", "lake_area_km2", "names"]
    df[cols].to_csv(out, index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    print(df[cols[:9] + ["names"]].to_string(float_format=lambda x: f"{x:.4g}"))
    print(f"{df.bw_id.nunique()} lake bathing waters with overflows upstream, {len(df)} inflows")


if __name__ == "__main__":
    main(*sys.argv[1:])
