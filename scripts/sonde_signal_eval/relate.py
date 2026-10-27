"""docs/SONDE-SIGNAL-TEST-2026-10.md: rule 3 of sondes.py for each (spot, sonde) that prep.py listed, metadata only.

    relate.py <river_network.pkl> <prep candidates.csv> <out.csv>

Adds direction and km along the river (`water_temperature.river_relation`, the site's own rule for its temperature
line) and whether rule 3 holds (sondes.network_ok). Offline: reads the network and the candidate list only.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from sondes import network_ok

from dipcast.ingest.water_temperature import Sensor, river_relation
from dipcast.network.rivers import RiverNetwork


def main(net_path: str, cand_csv: str, out_csv: str) -> None:
    net = RiverNetwork.load(Path(net_path))
    spots = {b["id"]: b for b in json.loads(Path(__file__).resolve().parents[2].joinpath(
        "data/raw/bathing_waters_inland.json").read_text())}
    rows = list(csv.DictReader(open(cand_csv)))
    cache: dict[tuple[str, str], tuple[str, float] | None] = {}
    for r in rows:
        key = (r["bw_id"], r["station_id"])
        if key not in cache:
            sp = spots[r["bw_id"]]
            s = Sensor(r["station_id"], r["label"], r["sonde_river"] or None, "", "", float(r["sonde_lat"]),
                       float(r["sonde_lon"]), 0.0, "", 0.0, None)
            try:
                cache[key] = river_relation(net, sp["lat"], sp["lon"], r["spot_river"], s)
            except Exception as e:  # noqa: BLE001 - a sonde the network cannot place does not count
                print("relate failed", key, e)
                cache[key] = None
        rel = cache[key]
        r["direction"], r["river_km"] = (rel or ("", ""))
        r["network_ok"] = network_ok(rel)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        if r["property"] == "turbidity":
            print(r["spot"][:30], r["station_id"], r["label"][:36], r["direction"], r["river_km"], r["network_ok"],
                  r["samples_covered"])


if __name__ == "__main__":
    main(*sys.argv[1:])
