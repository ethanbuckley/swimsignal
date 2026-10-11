"""Transport weights at each spot under the two outfall options of docs/OUTFALL-CHANNEL-TEST-2026-10.md:
outfall channel "own" / "junction" (transport) and first snap "nearest" / "named" (overflows). Transport
only: no rainfall, spill model or E. coli.

    curl -sS -o spots-lite.json https://swimsignal.co.uk/data/spots-lite.json
    uv run python scripts/outfall_channel_report.py spots-lite.json NEAREST.parquet NAMED.parquet [--bathing] [--json OUT]

NEAREST and NAMED are overflow tables built by overflows.build_overflows with DIPCAST_OUTFALL_SNAP_MODE
nearest and named, from the same live snapshot. Spots are placed as the site build places them (kind,
name, and a river spot's river); with --bathing the inland bathing waters of the E. coli evaluation are
added, placed as validate_ecoli.py places them (no hints). For every place and variant: the sum of
weights and the combined weight 1 - prod(1 - w); for every overflow whose weight changes, its weight in
each variant. Variants: base (nearest, own), junction (nearest, junction), named (named, own), both.
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

VARIANTS = {"base": ("nearest", "own"), "junction": ("nearest", "junction"), "named": ("named", "own"),
            "both": ("named", "junction")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spots_json")
    ap.add_argument("nearest")
    ap.add_argument("named")
    ap.add_argument("--bathing", action="store_true")
    ap.add_argument("--json", default=None, help="write every place's sums and changed overflows here")
    a = ap.parse_args()

    net = RiverNetwork.load()
    tables = {"nearest": pd.read_parquet(a.nearest), "named": pd.read_parquet(a.named)}
    spots = pd.DataFrame(json.loads(Path(a.spots_json).read_text())["spots"])
    places = [(r.id, r.name, float(r.lon), float(r.lat), r.kind if r.kind in ("lake", "river") else None,
               r.river if isinstance(r.river, str) and r.river and r.kind != "lake" else None, r.name)
              for r in spots.itertuples()]
    if a.bathing:
        bw = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id")
        places += [(f"eval:{r.bw_id}", r.name, float(r.lon), float(r.lat), None, None, None) for r in bw.itertuples()]
    v = T.river_velocity(None)
    out = []
    for sid, name, lon, lat, kind, river, hint_name in places:
        pin = T.locate_pin(net, lon, lat, kind_hint=kind, river_hint=river, name=hint_name)
        rec = {"id": sid, "name": name, "pin": pin.mode, "sum": {}, "combined": {}, "n": {}}
        per = {}
        for k, (snap, channel) in VARIANTS.items():
            up = T.upstream_overflows(net, pin, tables[snap], velocity_ms=v, outfall_channel_mode=channel)
            w = up["weight"].astype(float) if len(up) else pd.Series(dtype=float)
            rec["sum"][k] = float(w.sum())
            rec["combined"][k] = 1.0 - float(np.prod(1.0 - w.clip(0, 1)))
            rec["n"][k] = len(up)
            per[k] = up.set_index("site_id")["weight"] if len(up) else pd.Series(dtype=float)
            if len(up):
                per[k + "_name"] = up.set_index("site_id")["site_name"]
        allids = sorted(set().union(*[set(per[k].index) for k in VARIANTS]))
        changed = []
        for o in allids:
            ws = {k: float(per[k].get(o, 0.0)) for k in VARIANTS}
            if max(ws.values()) - min(ws.values()) > 5e-4:
                nm = next((per[k + "_name"].get(o) for k in VARIANTS if k + "_name" in per and o in per[k + "_name"]), None)
                changed.append({"site_id": o, "site_name": nm if isinstance(nm, str) else None, **ws})
        rec["changed"] = sorted(changed, key=lambda c: -max(abs(c[k] - c["base"]) for k in VARIANTS))
        out.append(rec)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))
    live = [r for r in out if not r["id"].startswith("eval:")]
    moved = [r for r in live if max(abs(r["sum"][k] - r["sum"]["base"]) for k in VARIANTS) > 5e-4]
    print(f"live spots whose sum of weights changes: {len(moved)} of {len(live)}")
    print("| spot | " + " | ".join(f"sum {k}" for k in VARIANTS) + " | combined base -> both |")
    print("|---|" + "---|" * (len(VARIANTS) + 1))
    for r in sorted(moved, key=lambda r: -abs(r["sum"]["both"] - r["sum"]["base"])):
        print(f"| {r['name']} (`{r['id']}`) | " + " | ".join(f"{r['sum'][k]:.4f}" for k in VARIANTS)
              + f" | {r['combined']['base']:.3f} -> {r['combined']['both']:.3f} |")


if __name__ == "__main__":
    main()
