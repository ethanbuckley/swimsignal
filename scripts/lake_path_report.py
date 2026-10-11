"""Transport weights at each spot with lake path "river" (the default) and "lake"
(docs/LAKE-PATH-TEST-2026-10.md). Transport only: no rainfall, spill model or E. coli.

    curl -sS -o spots-lite.json https://swimsignal.co.uk/data/spots-lite.json
    uv run python scripts/lake_path_report.py spots-lite.json [--bathing] [--top 10] [--ids a,b,...]

Each spot is placed as the site build places it (build_site.prefetch_rain): its `kind` as kind_hint and,
for a river spot, its `river` as river_hint. With --bathing the inland bathing waters of the E. coli
evaluation are added, placed as validate_ecoli.py places them (no hints). Prints, for the spots named
with --ids and the --top spots whose weight sum changes most (relative), the sum of weights before and
after, the combined weight 1 - prod(1 - w), and each of the top overflows: weight, travel time and the
WFD lakes its water crosses on the way.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.model import transport as T
from dipcast.network.rivers import RiverNetwork
from dipcast.overflows import load_overflows


def lakes_crossed(net: RiverNetwork, pin: T.PinLocation, ov: pd.DataFrame) -> dict[str, str]:
    """site_id -> the WFD lakes lake path 'lake' finds between the overflow and the pin, with their areas.
    The same walks as upstream_overflows."""
    lakes = T._lakes()
    cap = config.MAX_UPSTREAM_KM * 1000.0
    link_dist, _ = T.upstream_lengths(net, pin.trace_node, cap)
    on_path = set(link_dist)
    lake_of = T._wfd_lake_of(net, on_path, exclude=pin.lake_links)
    below = T._path_lakes(net, pin.trace_node, cap, lake_of) if pin.mode == "river" else {}
    out = {}
    for r in ov[ov["link_id"].isin(on_path)].itertuples():
        if pin.mode == "river":
            if pin.snap is not None and r.link_id == pin.snap.link_id:
                continue
            part = T._with_lake(below.get(r.link_id, T.NO_LAKES), lake_of.get(r.link_id), 1.0, 1.0)
        else:
            res = T._walk_to_lake(net, r.link_id, r.frac, pin.lake_links, on_path, lake_of=lake_of)
            part = T.NO_LAKES if res is None else res[3]
        if part[2]:
            out[r.site_id] = ", ".join(f"{lakes['lake_name'].iloc[k]} ({lakes['area_km2'].iloc[k]:.2f} km²)"
                                       for k in sorted(part[2]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spots_json")
    ap.add_argument("--bathing", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--ids", default="")
    ap.add_argument("--per-spot", type=int, default=3, help="overflows listed per spot")
    a = ap.parse_args()

    net = RiverNetwork.load()
    ov = load_overflows(net)
    spots = pd.DataFrame(json.loads(Path(a.spots_json).read_text())["spots"])
    places = [(r.id, r.name, float(r.lon), float(r.lat), r.kind if r.kind in ("lake", "river") else None,
               r.river if isinstance(r.river, str) and r.river and r.kind != "lake" else None) for r in spots.itertuples()]
    if a.bathing:
        bw = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id")
        places += [(f"eval:{r.bw_id}", r.name, float(r.lon), float(r.lat), None, None) for r in bw.itertuples()]
    v = T.river_velocity(None)
    res, detail = [], {}
    for sid, name, lon, lat, kind, river in places:
        pin = T.locate_pin(net, lon, lat, kind_hint=kind, river_hint=river)
        old = T.upstream_overflows(net, pin, ov, velocity_ms=v, lake_path_mode="river")
        new = T.upstream_overflows(net, pin, ov, velocity_ms=v, lake_path_mode="lake")
        s0, s1 = float(old["weight"].sum()), float(new["weight"].sum())
        res.append({"id": sid, "name": name, "pin": pin.mode, "n": len(old), "sum_old": s0, "sum_new": s1,
                    "comb_old": 1 - float(np.prod(1 - old["weight"].clip(0, 1))),
                    "comb_new": 1 - float(np.prod(1 - new["weight"].clip(0, 1))),
                    "change": s1 / s0 - 1 if s0 > 0 else 0.0})
        if len(old):
            m = old.set_index("site_id")[["site_name", "weight", "travel_h"]].join(
                new.set_index("site_id")[["weight", "travel_h"]], rsuffix="_new")
            m["lakes"] = m.index.map(lakes_crossed(net, pin, ov)).fillna("")
            detail[sid] = m
    res = pd.DataFrame(res).set_index("id")
    ids = [i for i in a.ids.split(",") if i]
    mag = res["change"].abs()
    live = ~res.index.str.startswith("eval:")
    top = list(mag[live & (mag > 0)].sort_values(ascending=False).index[: a.top])
    ev = list(mag[~live & (mag > 0)].sort_values(ascending=False).index)

    def table(sel: list[str]) -> None:
        print("| spot | pin | overflows | sum of weights | change | combined weight |")
        print("|---|---|---|---|---|---|")
        for i in sel:
            r = res.loc[i]
            print(f"| {r['name']} (`{i}`) | {r.pin} | {r.n} | {r.sum_old:.4f} → {r.sum_new:.4f} | {100 * r.change:+.1f}% "
                  f"| {r.comb_old:.4f} → {r.comb_new:.4f} |")

    def overflows(sel: list[str]) -> None:
        print("| spot | overflow | weight | travel (h) | WFD lakes crossed on the way |")
        print("|---|---|---|---|---|")
        for i in sel:
            if i not in detail:
                continue
            d = detail[i]
            show = d.sort_values("weight", ascending=False).head(a.per_spot)
            show = pd.concat([show, d[(d["lakes"] != "") & ~d.index.isin(show.index)]])
            for sid, x in show.iterrows():
                print(f"| `{i}` | {x.site_name} ({sid}) | {x.weight:.4f} → {x.weight_new:.4f} | "
                      f"{x.travel_h:.1f} → {x.travel_h_new:.1f} | {x.lakes or '-'} |")

    for title, sel in (("Named spots", [i for i in ids if i in res.index]), (f"The {a.top} spots that change most", top)):
        print(f"\n## {title}\n")
        table(sel)
        print()
        overflows(sel)
    print(f"\nchanged: {len(mag[live & (mag > 0)])} of {live.sum()} spots")
    if a.bathing:
        print(f"\n## Evaluation bathing waters that change ({len(ev)} of {(res.loc[~live, 'n'] > 0).sum()} "
              "with upstream overflows)\n")
        table(ev)


if __name__ == "__main__":
    main()
