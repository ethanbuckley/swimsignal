"""docs/ARRIVAL-TIME-SONDE-CHECK-2026-11.md, section 3: which sondes can be used, from metadata and spill records.

    relate.py <stations_ammonium.json> <out dir>

No sonde reading is read here. Places each ammonium sonde on the river network as the site places a temperature
sensor, lists the overflows the model traces upstream with their distance and travel time, and counts the quiet-rule
spill starts (section 5) inside each sonde's deployment. Writes stations.csv, pairs.csv and recount.json.
Run with a scratch DIPCAST_ROOT that links the main checkout's inputs.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO / "src"), str(HERE), str(REPO / "scripts" / "sonde_signal_eval")]
assert os.environ.get("DIPCAST_ROOT") and os.environ.get("DIPCAST_STATE"), "set scratch DIPCAST_ROOT and DIPCAST_STATE"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from core import D_MAX_M, D_MIN_M, find_events, horizon_h, others_in_window  # noqa: E402
from sondes import km_between, parse_stations  # noqa: E402

from dipcast import config  # noqa: E402
from dipcast.model.transport import locate_pin, upstream_overflows  # noqa: E402
from dipcast.network.rivers import RiverNetwork  # noqa: E402

PERIOD = (date(2024, 1, 1), date(2025, 12, 31))     # the EA start/stop files
MIN_DAYS = 30
SNAP_MAX_M = 250.0
SPOT_KM = 5.0
PLAN_MAX = 90            # readings requests (section 2)
PLAN_MIN_QUIET = 3       # section 10: a sonde with fewer quiet starts is not fetched
ARTIFICIAL = ("DRAIN", "DELPH")   # section 10: pumped fen channels, reported apart


def load_events() -> pd.DataFrame:
    parts = [pd.read_parquet(p, columns=["site_id", "event_start", "event_end"])
             for p in sorted(config.PROCESSED.glob("ea_events_*.parquet"))]
    ev = pd.concat(parts, ignore_index=True).dropna()
    ev["start"] = ev["event_start"].astype("datetime64[s, UTC]").astype("int64") // 60
    ev["end"] = ev["event_end"].astype("datetime64[s, UTC]").astype("int64") // 60
    return ev[["site_id", "start", "end"]]


def _minute(d: date) -> int:
    return int(pd.Timestamp(d, tz="UTC").timestamp() // 60)


def main(stations_json: str, out_dir: str) -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    sondes = [s for s in parse_stations(json.loads(Path(stations_json).read_text())["items"]) if "ammonium" in s.measures]
    spots = list(csv.DictReader(open(REPO / "spots.csv")))
    near = lambda s: min(km_between(s.lat, s.lon, float(p["lat"]), float(p["lon"])) for p in spots)  # noqa: E731
    today = date(2026, 11, 13)
    recount = {"listing_date": str(today), "with_ammonium_measure": len(sondes),
               "open_no_date_closed": sum(s.closed is None for s in sondes)}
    open_near = [s for s in sondes if s.closed is None and near(s) <= SPOT_KM]
    recount["open_within_5km_of_a_spot"] = len(open_near)
    recount["open_within_5km_labels"] = sorted(s.label for s in open_near)

    def overlap(s) -> tuple[date, date] | None:
        if s.opened is None:
            return None
        a, b = max(s.opened, PERIOD[0]), min(s.closed or today, PERIOD[1])
        return (a, b) if (b - a).days >= MIN_DAYS else None

    cand = [s for s in sondes if overlap(s)]
    recount["deployed_30_days_in_2024_25"] = len(cand)

    net = RiverNetwork.load()
    overflows = pd.read_parquet(config.PROCESSED / "overflows.parquet")
    events = load_events()
    monitored = set(events["site_id"])
    by_site = {k: g for k, g in events[events["site_id"].isin(set(overflows["site_id"]))].groupby("site_id")}

    rows, pairs, why = [], [], {}
    for s in sorted(cand, key=lambda s: s.station_id):
        a, b = overlap(s)
        row = {"station_id": s.station_id, "label": s.label, "river": s.river or "", "lat": s.lat, "lon": s.lon,
               "opened": s.opened, "closed": s.closed or "", "from": a, "to": b, "measure": s.measures["ammonium"],
               "km_to_spot": round(near(s), 1)}
        try:
            pin = locate_pin(net, s.lon, s.lat, kind_hint="river", river_hint=s.river)
        except Exception as e:  # noqa: BLE001 - a sonde the network cannot place is out
            row["out"] = f"not placed ({type(e).__name__})"
            rows.append(row); continue
        if pin.mode != "river" or pin.snap is None:
            row["out"] = "not on a river"
        elif pin.snap.form == "tidalRiver":
            row["out"] = "tidal"
        elif pin.snap.dist_m > SNAP_MAX_M:
            row["out"] = "over 250 m from the link"
        if "out" in row:
            rows.append(row); continue
        row.update(snap_m=round(pin.snap.dist_m), watercourse=pin.watercourse or "", placement=pin.placement or "")
        up = upstream_overflows(net, pin, overflows, config.RIVER_VELOCITY_MS)
        up = up[up["site_id"].isin(monitored)].copy()
        up["d_m"] = up["distance_m"] + up["lake_distance_m"]
        timing = up[(up["lake_distance_m"] == 0) & (up["snap_confidence"] == "high")
                    & (up["distance_m"] >= D_MIN_M) & (up["distance_m"] <= D_MAX_M)]
        row.update(monitored_upstream=len(up), timing_overflows=len(timing))
        if timing.empty:
            row["out"] = "no timing overflow upstream"
            rows.append(row); continue
        lo, hi = _minute(a), _minute(b) + 1440
        sp = pd.concat([by_site[k] for k in up["site_id"] if k in by_site], ignore_index=True)
        sp = sp.merge(up[["site_id", "d_m"]], on="site_id")
        ev = find_events(sp)
        ev = ev[(ev["t0"] >= lo + 30 * 60) & (ev["t0"] <= hi) & ev["site_id"].isin(set(timing["site_id"]))]
        tier_a = 0
        per = {}
        for e in ev.itertuples():
            h = horizon_h(e.d_m)
            one = others_in_window(sp, e.t0, h, e.site_id).empty
            tier_a += one
            c = per.setdefault(e.site_id, [0, 0])
            c[0] += 1; c[1] += one
        row.update(quiet_starts=len(ev), tier_a_starts=tier_a)
        for t in timing.itertuples():
            n, na = per.get(t.site_id, (0, 0))
            pairs.append({"station_id": s.station_id, "label": s.label, "site_id": t.site_id, "company": t.company,
                          "site_name": t.site_name, "distance_m": round(t.distance_m), "travel_h": round(t.travel_h, 2),
                          "quiet_starts": n, "tier_a_starts": na})
        rows.append(row)
    for r in rows:
        why[r.get("out", "eligible")] = why.get(r.get("out", "eligible"), 0) + 1
    recount["placement"] = why
    elig = [r for r in rows if "out" not in r]
    recount["eligible_with_a_quiet_start"] = sum(r["quiet_starts"] > 0 for r in elig)
    recount["eligible_with_a_tier_a_start"] = sum(r["tier_a_starts"] > 0 for r in elig)
    recount["eligible_open_now"] = sum(r["closed"] == "" for r in elig)
    # Section 10: the fetch plan. Ranked by Tier A starts, then quiet starts, then id; the first PLAN_MAX with at
    # least PLAN_MIN_QUIET quiet starts. One request per sonde, its deployment in 2024-25 with room for the baseline
    # before and the horizon after.
    ranked = sorted((r for r in elig if r["quiet_starts"] >= PLAN_MIN_QUIET),
                    key=lambda r: (-r["tier_a_starts"], -r["quiet_starts"], r["station_id"]))[:PLAN_MAX]
    chosen = {r["station_id"] for r in ranked}
    for r in rows:
        r["artificial_channel"] = any(w in r["label"].upper() for w in ARTIFICIAL)
        r["fetch"] = r["station_id"] in chosen
    with open(out / "plan.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["station_id", "measure", "date_from", "date_to"])
        for r in ranked:
            w.writerow([r["station_id"], r["measure"], r["from"] - pd.Timedelta(days=2).to_pytimedelta(),
                        r["to"] + pd.Timedelta(days=4).to_pytimedelta()])
    recount["planned_requests"] = len(ranked)
    recount["planned_station_days"] = int(sum((r["to"] - r["from"]).days + 7 for r in ranked))
    recount["planned_tier_a_starts"] = int(sum(r["tier_a_starts"] for r in ranked))
    recount["planned_quiet_starts"] = int(sum(r["quiet_starts"] for r in ranked))
    recount["planned_artificial_channel"] = int(sum(r["artificial_channel"] for r in ranked))
    cols = ["station_id", "label", "river", "watercourse", "placement", "lat", "lon", "opened", "closed", "from", "to",
            "measure", "km_to_spot", "snap_m", "monitored_upstream", "timing_overflows", "quiet_starts",
            "tier_a_starts", "artificial_channel", "fetch", "out"]
    with open(out / "stations.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    with open(out / "pairs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pairs[0])); w.writeheader(); w.writerows(pairs)
    (out / "recount.json").write_text(json.dumps(recount, indent=1))
    print(json.dumps(recount, indent=1))
    top = sorted(elig, key=lambda r: (-r["tier_a_starts"], -r["quiet_starts"], r["station_id"]))[:40]
    for r in top:
        print(r["station_id"], r["label"][:38].ljust(38), r["from"], r["to"], r["monitored_upstream"],
              r["timing_overflows"], r["quiet_starts"], r["tier_a_starts"], r["km_to_spot"])
    print("eligible", len(elig), "tier A starts", int(np.sum([r["tier_a_starts"] for r in elig])))


if __name__ == "__main__":
    main(*sys.argv[1:])
