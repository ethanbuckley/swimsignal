"""docs/ARRIVAL-TIME-SONDE-CHECK-2026-11.md, section 13: the extension to January-August 2026.

    extend.py plan <stations.csv> <amended per_sonde.json> <out dir>      the 7 sondes and their fetch plan
    extend.py merge <plan.csv> <2024-25 readings dir> <2026 readings dir> <out dir>
    extend.py split <events.csv> <amended events.csv> <out.json>          seen (before 2026) and new, per sonde
    extend.py reach <events.csv> <stations.csv> <out.json>                description: per-reach speed beside the lags

The fetch itself is fetch.py readings, through the ledger. The join is analyse.py amended on the merged readings,
with a scratch root that also links the 2026 spill tables.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from core import median_ci  # noqa: E402

N_SONDES = 7
DATE_FROM, DATE_TO = "2026-01-03", "2026-08-31"
NEW_FROM = "2026-01-01"
MIN_RISES = 5


def plan(stations_csv: str, per_sonde_json: str, out_dir: str) -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    stations = {r["station_id"]: r for r in csv.DictReader(open(stations_csv))}
    per = [p for p in json.loads(Path(per_sonde_json).read_text()) if "tier_a" in p and not p["artificial_channel"]]
    per = [p for p in per if stations[p["station_id"]]["closed"] == ""]          # status Active
    ranked = sorted(per, key=lambda p: (not p["dry"]["signal"], -p["a_rise"], p["station_id"]))[:N_SONDES]
    with open(out / "plan_2026.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["station_id", "measure", "date_from", "date_to"])
        for p in ranked:
            w.writerow([p["station_id"], stations[p["station_id"]]["measure"], DATE_FROM, DATE_TO])
    cols = list(next(iter(stations.values())))
    with open(out / "stations_2026.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        w.writerows({**stations[p["station_id"]], "fetch": "True"} for p in ranked)
    for p in ranked:
        print(p["station_id"], p["label"], "signal" if p["dry"]["signal"] else "no signal", p["a_rise"])


def merge(plan_csv: str, dir_a: str, dir_b: str, out_dir: str) -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    for p in csv.DictReader(open(plan_csv)):
        parts = [pd.read_csv(f) for f in (Path(d) / f"{p['measure']}.csv" for d in (dir_a, dir_b))
                 if f.exists() and f.stat().st_size]
        d = pd.concat(parts, ignore_index=True).drop_duplicates("dateTime", keep="last").sort_values("dateTime")
        d.to_csv(out / f"{p['measure']}.csv", index=False)
        print(p["station_id"], [len(x) for x in parts], len(d))


def _stats(v) -> dict:
    v = [float(a) for a in v if np.isfinite(a)]
    if len(v) < MIN_RISES:
        return {"n": len(v), "values": [round(a, 2) for a in sorted(v)]}
    med, lo, hi = median_ci(v)
    return {"n": len(v), "median": round(med, 3), "lo": round(lo, 3), "hi": round(hi, 3)}


def split(events_csv: str, amended_csv: str, out_json: str) -> None:
    ev = pd.read_csv(events_csv)
    old = pd.read_csv(amended_csv)
    ev["period"] = np.where(ev["t0"] < NEW_FROM, "seen", "new")
    key = ["station_id", "t0", "site_id"]
    both = ev[ev["period"] == "seen"].merge(old[key + ["tier", "status"]], on=key, how="outer", suffixes=("", "_before"),
                                            indicator=True)
    both = both[both["station_id"].isin(set(ev["station_id"]))]
    changed = both[(both["_merge"] != "both") | (both["tier"] != both["tier_before"]) | (both["status"] != both["status_before"])]
    res = {"seen_events_compared": int(len(both)), "seen_events_changed": int(len(changed)),
           "changed": changed[key + ["tier_before", "status_before", "tier", "status", "_merge"]].astype(str).to_dict("records"),
           "sondes": []}
    a = ev[ev["tier"] == "A"]
    for sid, g in a.groupby("station_id"):
        row = {"station_id": sid}
        for name, h in (("seen", g[g["period"] == "seen"]), ("new", g[g["period"] == "new"]), ("all", g)):
            r = h[h["status"] == "rise"]
            row[name] = {"tier_a": len(h), **{k.replace(" ", "_"): int((h["status"] == k).sum())
                                             for k in ("rise", "no rise", "raised before", "gap", "no baseline")},
                         "lag_h": _stats(r["lag_h"]), "v_ms": _stats(r["v_ms"]), "model_travel_h": _stats(r["travel_h"])}
        s, n = row["seen"]["lag_h"], row["new"]["lag_h"]
        if n["n"] >= 3 and "lo" in s:
            med = n.get("median", float(np.median(n.get("values", [np.nan]))))
            row["new_median_inside_seen_interval"] = bool(s["lo"] <= med <= s["hi"])
            row["new_median_lag_h"] = round(float(med), 3)
        res["sondes"].append(row)
    tot = {p: {k: int(((a["period"] == p) & (a["status"] == k)).sum()) for k in ("rise", "no rise", "raised before", "gap", "no baseline")}
           for p in ("seen", "new")}
    res["tier_a_totals"] = tot
    Path(out_json).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))




def reach(events_csv: str, stations_csv: str, out_json: str) -> None:
    """Description only, chosen after the results: for each sonde's Tier A rises, the implied speed beside the
    fixed 0.2 m/s and beside the speed the code's per-reach option (transport.reach_velocity, velocity 'catchment',
    off by default) gives at the sonde's own reach and at the anchor overflow's reach. The path's speed lies between
    those two. Needs a scratch DIPCAST_ROOT and DIPCAST_STATE."""
    import os
    assert os.environ.get("DIPCAST_ROOT") and os.environ.get("DIPCAST_STATE")
    sys.path[:0] = [str(HERE.parents[1] / "src")]
    from dipcast import config
    from dipcast.model.transport import catchment_km2, locate_pin, reach_velocity
    from dipcast.network.rivers import RiverNetwork
    net = RiverNetwork.load()
    ov = pd.read_parquet(config.PROCESSED / "overflows.parquet").drop_duplicates("site_id").set_index("site_id")
    ev = pd.read_csv(events_csv)
    ev = ev[(ev["tier"] == "A") & (ev["status"] == "rise")]
    out = []
    for s in csv.DictReader(open(stations_csv)):
        g = ev[ev["station_id"] == s["station_id"]]
        if g.empty:
            continue
        pin = locate_pin(net, float(s["lon"]), float(s["lat"]), kind_hint="river", river_hint=s["river"] or None)
        up_sonde = float(net.upstream_m.get(pin.trace_node, 0.0)) + pin.trace_offset_m
        anchor = g["site_id"].mode().iloc[0]
        up_anchor = float(net.upstream_m.get(ov.at[anchor, "start_node"], 0.0))
        out.append({"station_id": s["station_id"], "label": s["label"], "rises": len(g),
                    "d_km": round(float((g["d_m"] / 1000).median()), 2),
                    "implied_speed_ms_median": round(float(g["v_ms"].median()), 3),
                    "catchment_km2_at_sonde": round(float(catchment_km2(up_sonde)), 1),
                    "reach_speed_ms_at_sonde": round(float(reach_velocity(up_sonde)), 3),
                    "reach_speed_ms_at_anchor": round(float(reach_velocity(up_anchor)), 3),
                    "fixed_speed_ms": config.RIVER_VELOCITY_MS})
    Path(out_json).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"plan": plan, "merge": merge, "split": split, "reach": reach}[sys.argv[1]](*sys.argv[2:])
