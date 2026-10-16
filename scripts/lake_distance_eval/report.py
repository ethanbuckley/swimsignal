"""Transport weights at every lake spot under lake distance "line" and "water" (docs/LAKE-DISTANCE-2026-10.md).
Transport only: no rain, spill model or E. coli.

    python scripts/lake_distance_eval/report.py <out.csv>

The site's spots (spots.csv and spots-osm.csv of this checkout) are placed as build_site.prefetch_rain places them,
and the inland bathing waters of the E. coli evaluation as eval_pins.bathing_water_pin does. Lake path, velocity and
dilution stay at their defaults. Writes one row per lake spot and overflow (both distances, travel times and weights)
and prints the spots whose weights change, with how many there are.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "scripts"))
import eval_pins
from build_site import load_spots

from dipcast import config
from dipcast.model import transport as T
from dipcast.network.rivers import RiverNetwork
from dipcast.overflows import load_overflows


def main() -> None:
    out = Path(sys.argv[1])
    net = RiverNetwork.load()
    ov = load_overflows(net)
    spots = load_spots([W / "spots.csv", W / "spots-osm.csv"])
    places = []
    for r in spots.itertuples(index=False):
        kind, river = T.spot_hints(r.kind, r.river)
        places.append(("site", r.id, r.name, T.locate_pin(net, float(r.lon), float(r.lat), kind_hint=kind,
                                                          river_hint=river, name=r.name)))
    bw = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id")
    for r in bw.itertuples():
        places.append(("eval", r.bw_id, r.name, eval_pins.bathing_water_pin(net, r.bw_id, float(r.lon), float(r.lat))))
    v = T.river_velocity(None)
    rows = []
    for where, sid, name, pin in places:
        if pin.mode != "lake":
            continue
        a = T.upstream_overflows(net, pin, ov, velocity_ms=v, lake_distance_mode="line")
        b = T.upstream_overflows(net, pin, ov, velocity_ms=v, lake_distance_mode="water")
        assert len(a) == len(b), sid
        key = ["site_id", "link_id", "frac"]
        m = a[key + ["site_name", "lake_distance_m", "travel_h", "weight"]].merge(
            b[key + ["lake_distance_m", "travel_h", "weight"]], on=key, suffixes=("_line", "_water"), validate="1:1")
        m.insert(0, "spot", sid); m.insert(0, "where", where); m.insert(2, "spot_name", name)
        m["pin_x"], m["pin_y"] = pin.x, pin.y
        rows.append(m if len(m) else pd.DataFrame([{"where": where, "spot": sid, "spot_name": name}]))
    df = pd.concat(rows, ignore_index=True)
    df.to_csv(out, index=False)
    g = df.dropna(subset=["site_id"]).groupby(["where", "spot", "spot_name"]).agg(
        overflows=("site_id", "size"), changed=("weight_water", lambda s: 0),
        sum_line=("weight_line", "sum"), sum_water=("weight_water", "sum"),
        max_extra_m=("lake_distance_m_water", "max"))
    d = df.dropna(subset=["site_id"])
    d = d.assign(extra=d.lake_distance_m_water - d.lake_distance_m_line,
                 moved=~np.isclose(d.weight_water, d.weight_line, rtol=1e-9, atol=0))
    g["changed"] = d.groupby(["where", "spot", "spot_name"])["moved"].sum()
    g["max_extra_m"] = d.groupby(["where", "spot", "spot_name"])["extra"].max()
    g["change"] = g.sum_water / g.sum_line - 1
    pd.set_option("display.width", 250)
    print(g.to_string(float_format=lambda x: f"{x:.6g}"))
    lake_pins = df.groupby("where")["spot"].nunique()
    for where in ("site", "eval"):
        gg = g.loc[where] if where in g.index.get_level_values(0) else g.iloc[0:0]
        print(f"{where}: {lake_pins.get(where, 0)} lake pins, {len(gg)} with overflows, "
              f"{int((gg.changed > 0).sum())} whose weights change")


if __name__ == "__main__":
    main()
