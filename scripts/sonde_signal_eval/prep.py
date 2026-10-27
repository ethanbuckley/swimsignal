"""docs/SONDE-SIGNAL-TEST-2026-10.md, preparation: sondes near the river bathing waters, from metadata only.

    prep.py <stations_turbidity.json> <stations_ammonium.json> <out.csv> <out.json> [ecoli_validation_rows.parquet]

Reads the two station listings (/hydrology/id/stations.json?observedProperty=...&_limit=10000), the river bathing
waters with overflows upstream (data/processed/validation_sites.csv, coordinates from
data/raw/bathing_waters_inland.json), and, when given, only the columns bw_id, kind, upstream and sample_time of the
validation rows: never `ecoli` or any other value. Writes each (spot, sonde, property) that passes rules 1 and 2 of
sondes.py with its deployment, and counts of May-September sample days in 2024-2026 that a deployment covers. No
network rule is applied, so the counts are upper bounds. No reading is fetched or read.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from sondes import PROPERTIES, candidates, parse_stations

YEARS = (2024, 2025, 2026)
REPO = Path(__file__).resolve().parents[2]


def river_spots(repo: Path = REPO) -> list[dict]:
    """The river bathing waters with overflows upstream, from files in the repository (not DIPCAST_ROOT)."""
    sites = {}
    with open(repo / "data/processed/validation_sites.csv") as f:
        for r in csv.DictReader(f):
            if r["mode"] == "river" and int(r["upstream"]) > 0:
                sites[r["name"]] = r["watercourse"]
    bws = json.loads((repo / "data/raw/bathing_waters_inland.json").read_text())
    return [{"bw_id": b["id"], "name": b["name"], "river": sites[b["name"]], "lat": b["lat"], "lon": b["lon"]}
            for b in bws if b["name"] in sites]


def sample_days(path: str | None) -> dict[str, list]:
    """May-September sample days by bathing water, from the identifying columns only."""
    if not path:
        return {}
    import pandas as pd
    rows = pd.read_parquet(path, columns=["bw_id", "kind", "upstream", "sample_time"])
    rows = rows[(rows.kind == "river") & (rows.upstream > 0)]
    t = rows["sample_time"]
    rows = rows[t.dt.year.isin(YEARS) & t.dt.month.between(5, 9)]
    return {bw: sorted(g["sample_time"].dt.date) for bw, g in rows.groupby("bw_id")}


def main(turb: str, amm: str, out_csv: str, out_json: str, rows_path: str | None = None) -> None:
    items = json.loads(Path(turb).read_text())["items"] + json.loads(Path(amm).read_text())["items"]
    sondes = parse_stations(items)
    spots = river_spots()
    days = sample_days(rows_path)
    out, counts = [], {"stations_listed": len(sondes),
                       "stations_with": {p: sum(p in s.measures for s in sondes) for p in PROPERTIES},
                       "river_spots": len(spots), "by_spot": {}}
    for sp in spots:
        d = days.get(sp["bw_id"], [])
        per = {"samples_may_sep_2024_26": len(d)}
        for prop in PROPERTIES:
            covered = set()
            for s, km in candidates(sondes, sp["lat"], sp["lon"], sp["river"], prop):
                n = sum(s.covers(x) for x in d)
                covered |= {i for i, x in enumerate(d) if s.covers(x)}
                out.append({"bw_id": sp["bw_id"], "spot": sp["name"], "spot_river": sp["river"], "property": prop,
                            "station_id": s.station_id, "label": s.label, "sonde_river": s.river,
                            "sonde_lat": s.lat, "sonde_lon": s.lon, "km_straight": round(km, 2), "opened": s.opened, "closed": s.closed or "",
                            "samples_covered": n if rows_path else "",
                            "years": json.dumps(sorted({x.year for x in d if s.covers(x)}))})
            per[f"{prop}_samples_covered_upper_bound"] = len(covered)
        counts["by_spot"][sp["name"]] = per
    tot = defaultdict(int)
    for per in counts["by_spot"].values():
        for k, v in per.items():
            tot[k] += v
    counts["totals"] = dict(tot)
    counts["spots_with_any"] = {p: sum(per[f"{p}_samples_covered_upper_bound"] > 0 for per in counts["by_spot"].values())
                                for p in PROPERTIES}
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]) if out else ["bw_id"])
        w.writeheader()
        w.writerows(out)
    Path(out_json).write_text(json.dumps(counts, indent=1, default=str))
    print(json.dumps(counts, indent=1, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:])
