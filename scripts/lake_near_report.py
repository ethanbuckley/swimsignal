"""The ceiling of every lake spot under lake near "off" and "blend" (docs/LAKE-NEAR-FIELD-TEST-2026-10.md):
the exposure index with every upstream overflow discharging, 1 - prod(1 - w), and its level. Transport
only: no rainfall, spill model or E. coli.

    curl -sS -o spots-lite.json https://swimsignal.co.uk/data/spots-lite.json
    uv run python scripts/lake_near_report.py spots-lite.json [OVERFLOWS.parquet] [--bathing] [--json OUT]

Lake spots (kind 'lake') are placed as the site build places them; with --bathing the lake bathing
waters of the E. coli evaluation are added, placed as validate_ecoli.py places them (no hints). The
overflow table is the state's (overflows.load_overflows) unless one is given. For each spot: the
number of upstream overflows, the ceiling and its level in each mode, and the overflow with the most
weight under "blend": its straight line across the lake, its own river dilution where it enters
(near), the lake dilution (far) and its weight in each mode.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.model import transport as T
from dipcast.network.rivers import RiverNetwork
from dipcast.overflows import load_overflows


def ceiling(w: pd.Series) -> float:
    return 1.0 - float(np.prod(1.0 - np.clip(w.astype(float), 0, 1))) if len(w) else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spots_json")
    ap.add_argument("overflows", nargs="?", default=None)
    ap.add_argument("--bathing", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    net = RiverNetwork.load()
    ov = pd.read_parquet(a.overflows) if a.overflows else load_overflows(net)
    spots = pd.DataFrame(json.loads(Path(a.spots_json).read_text())["spots"])
    places = [(r.id, r.name, float(r.lon), float(r.lat), "lake", r.name) for r in spots.itertuples() if r.kind == "lake"]
    if a.bathing:
        bw = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id")
        places += [(f"eval:{r.bw_id}", r.name, float(r.lon), float(r.lat), None, None)
                   for r in bw.itertuples() if r.kind == "lake"]
    v = T.river_velocity(None)
    out = []
    for sid, name, lon, lat, kind, hint in places:
        pin = T.locate_pin(net, lon, lat, kind_hint=kind, name=hint)
        rec = {"id": sid, "name": name, "pin": pin.mode, "lake": pin.watercourse, "area_km2": pin.lake_area_km2}
        ups = {}
        for mode in ("off", "blend"):
            up = T.upstream_overflows(net, pin, ov, velocity_ms=v, lake_near_mode=mode)
            ups[mode] = up
            rec["n"] = len(up)
            rec[f"ceiling_{mode}"] = ceiling(up["weight"]) if len(up) else 0.0
            rec[f"level_{mode}"] = T.risk_label(rec[f"ceiling_{mode}"]) if len(up) else "no overflow"
        if len(ups["blend"]):
            b = ups["blend"].set_index("site_id")
            o = ups["off"].set_index("site_id")
            top = b["weight"].idxmax()
            rec["top"] = {"site_id": top, "site_name": b.at[top, "site_name"],
                          "across_m": round(float(b.at[top, "lake_distance_m"])),
                          "river_m": round(float(b.at[top, "distance_m"])),
                          "weight_off": round(float(o.at[top, "weight"]), 4), "weight_blend": round(float(b.at[top, "weight"]), 4),
                          "near_share": round(math.exp(-float(b.at[top, "lake_distance_m"]) / T.LAKE_NEAR_M), 3)}
        out.append(rec)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=str))
    print("| spot | lake (km²) | overflows | ceiling off | ceiling blend | top overflow under blend: across, weight off → blend |")
    print("|---|---|---|---|---|---|")
    for r in out:
        t = r.get("top")
        top = (f"{t['site_name']}: {t['across_m']} m, {t['weight_off']:.3f} → {t['weight_blend']:.3f}" if t else "-")
        area = "" if not r["area_km2"] else f"{r['area_km2']:.2f}"
        print(f"| {r['name']} (`{r['id']}`) | {r['lake'] or ''} {area} | {r['n']} | {r['ceiling_off']:.3f} {r['level_off']} "
              f"| {r['ceiling_blend']:.3f} {r['level_blend']} | {top} |")
    live = [r for r in out if not r["id"].startswith("eval:") and r["n"]]
    for mode in ("off", "blend"):
        print(f"live lake spots with overflows: {len(live)}; ceiling under 0.15 ({mode}): "
              f"{sum(r[f'ceiling_{mode}'] < T.LOW_CUT for r in live)}")


if __name__ == "__main__":
    main()
