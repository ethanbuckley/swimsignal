"""Transport weights at every lake spot under lake direction "any" and "down" (docs/LAKE-DIRECTION-TEST-2026-10.md).
Transport only: no rain, spill model or E. coli.

    python scripts/lake_direction_eval/report.py <out.csv>

The site's spots (spots.csv and spots-osm.csv of this checkout) are placed as build_site.prefetch_rain places them,
and the inland bathing waters of the E. coli evaluation as eval_pins.bathing_water_pin does. Everything else stays at
its default. Writes one row per lake pin and overflow whose water enters the pin's own lake (its entry point, how far
down the lake from the pin it enters, whether "down" leaves it out, and its weight under "any"), and prints the pins
that lose an overflow.
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
    cap = config.MAX_UPSTREAM_KM * 1000.0
    rows = []
    for where, sid, name, pin in places:
        if pin.mode != "lake":
            continue
        a = T.upstream_overflows(net, pin, ov, velocity_ms=v, lake_direction_mode="any")
        b = T.upstream_overflows(net, pin, ov, velocity_ms=v, lake_direction_mode="down")
        if a.empty:
            continue
        link_dist, _ = T.upstream_lengths(net, pin.trace_node, cap)
        on_path = set(link_dist)
        entry = [T._walk_to_lake(net, r.link_id, r.frac, pin.lake_links, on_path)[1] for r in a.itertuples()]
        e = np.asarray(entry, dtype=float)
        down = T.down_lake_m(net, pin, e)
        kept = set(zip(b.site_id, b.link_id, b.frac))
        rows.append(pd.DataFrame({
            "where": where, "spot": sid, "spot_name": name, "pin_x": pin.x, "pin_y": pin.y,
            "site_id": a.site_id, "site_name": a.site_name, "entry_x": e[:, 0], "entry_y": e[:, 1],
            "down_m": down, "dropped": [k not in kept for k in zip(a.site_id, a.link_id, a.frac)],
            "lake_distance_m": a.lake_distance_m, "weight_any": a.weight}))
    df = pd.concat(rows, ignore_index=True)
    assert (df.dropped == (df.down_m > T.LAKE_DOWN_MARGIN_M)).all(), "report and rule disagree"
    df.to_csv(out, index=False)
    g = df.groupby(["where", "spot", "spot_name"]).agg(
        overflows=("site_id", "size"), left_out=("dropped", "sum"), sum_any=("weight_any", "sum"),
        sum_down=("weight_any", lambda s: s[~df.loc[s.index, "dropped"]].sum()))
    g["change"] = g.sum_down / g.sum_any - 1
    pd.set_option("display.width", 250)
    print(g.to_string(float_format=lambda x: f"{x:.4g}"))
    print()
    print(df[df.dropped][["where", "spot_name", "site_name", "down_m", "lake_distance_m", "weight_any"]]
          .to_string(float_format=lambda x: f"{x:.4g}"))
    for where in ("site", "eval"):
        gg = g.loc[where] if where in g.index.get_level_values(0) else g.iloc[0:0]
        print(f"{where}: {len(gg)} lake pins with overflows, {int((gg.left_out > 0).sum())} lose at least one, "
              f"{int((gg.sum_down == 0).sum())} lose all")


if __name__ == "__main__":
    main()
