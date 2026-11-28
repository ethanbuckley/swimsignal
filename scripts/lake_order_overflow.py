"""Freeze each spot's usual thirds for the lake word at the 7 English lake spots whose average-lake range is withheld
(docs/LAKE-ORDER-OVERFLOW-LAKES-2026-11.md). The figure is lake-range-v1's likely reading on the average-lake basis,
as the forecast computes it, from rain at the spot and spill exposure from the overflows upstream, hindcast at lead 0
(validate_ecoli.hindcast, as #584 and the bench built exposure), on every May to September day of 2023 to 2026.
Usual is the middle third of those figures (the river order line's rule, scripts/lake_order.py).

    DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch> DIPCAST_CACHE=<scratch>/data/cache \\
        uv run python scripts/lake_order_overflow.py

Archive rain comes from the cache; a missing cell-year is fetched into DIPCAST_CACHE (strict, so a refusal stops it).
Writes data/processed/lake_order_overflow.v1.json in the repository.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

SPOTS = ("ullswater-glenridding", "ullswater-pooley-bridge", "osm-ullswater-sandwick", "bassenthwaite", "grasmere",
         "rydal-water", "elter-water")
YEARS = range(2023, 2027)
SEASON = range(5, 10)
OUT = REPO / "data" / "processed" / "lake_order_overflow.v1.json"


def main() -> int:
    for v in ("DIPCAST_ROOT", "DIPCAST_STATE", "DIPCAST_CACHE"):
        assert os.environ.get(v), f"set {v} to a scratch path"
    from lake_order import cut_points
    from validate_ecoli import hindcast

    from dipcast import config, lake_range, river_usual
    from dipcast.ingest.rainfall import fetch_archive, grid_cell
    from dipcast.model.ecoli import SAMPLE_HOUR, features, rain_windows
    from dipcast.model.features import daily_rain_features
    from dipcast.model.spill_model import SpillModel
    from dipcast.model.transport import history_days, locate_pin, river_velocity, upstream_overflows
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import load_overflows

    model_file = REPO / "data" / "processed" / lake_range.FILE.name
    assert hashlib.sha256(model_file.read_bytes()).hexdigest() == lake_range.SHA256
    m = json.loads(model_file.read_text())
    net = RiverNetwork.load()
    ov, spill = load_overflows(net), SpillModel.load()
    sp = pd.concat([pd.read_csv(REPO / "spots.csv"), pd.read_csv(REPO / "spots-osm.csv")]).set_index("id")
    plan, cells = {}, set()
    for sid in SPOTS:
        r = sp.loc[sid]
        pin = locate_pin(net, float(r.lon), float(r.lat), kind_hint="lake", river_hint=None, name=r["name"])
        up = upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None), max_km=config.MAX_UPSTREAM_KM)
        assert pin.mode == "lake" and len(up), sid
        cell = tuple(float(v) for v in grid_cell(float(r.lat), float(r.lon)))
        plan[sid] = (r, up, cell)
        cells.add(cell)
        cells |= set(zip(*[a.tolist() for a in grid_cell(up["lat"].to_numpy(), up["lon"].to_numpy())], strict=True))
    cells = sorted(cells)
    rain = pd.concat([fetch_archive(cells, y, strict=True) for y in YEARS], ignore_index=True)
    rain["time"] = rain["time"].dt.tz_convert("Europe/London")
    files = sorted(Path(config.CACHE, "rain").glob("archive_*.parquet"))
    used = [f for f in files if any(f.name.startswith(f"archive_{a:.3f}_{b:.3f}_") for a, b in cells)
            and int(f.stem.rsplit("_", 1)[1]) in YEARS]
    hourly = rain.set_index(["cell_lat", "cell_lon"]).sort_index()
    daily = daily_rain_features(rain)
    spots = {}
    for sid, (r, up, cell) in plan.items():
        site_rain = hourly.loc[cell].set_index("time")["precip_mm"].sort_index()
        figs = []
        for y in YEARS:
            days = pd.date_range(f"{y}-05-01", f"{y}-09-30", freq="D", tz="Europe/London")
            run = pd.date_range(days[0] - pd.Timedelta(days=history_days(up["travel_h"])), days[-1], freq="D")
            risk, _ = hindcast(up, daily, run, spill)
            ends = days + pd.Timedelta(hours=SAMPLE_HOUR)
            r48, r24 = rain_windows(site_rain, ends)
            rk = risk.reindex(days).to_numpy(dtype=float)
            ok = np.isfinite(r48) & np.isfinite(r24) & np.isfinite(rk)   # risk is NaN where too much rain is missing
            X = features(r48[ok], r24[ok], rk[ok], np.ones(ok.sum()), days[ok])
            med = lake_range._quantiles(m, X[m["cols"]], None, qs=(0.5,))[0.5]
            figs.append(np.round(np.log10(med), 3))
        f = np.concatenate(figs)
        c = cut_points(pd.Series(f))
        assert c is not None, (sid, len(f))
        spots[river_usual.key(float(r.lat), float(r.lon))] = {"id": sid, "name": str(r["name"]), "upstream": int(len(up)), **c}
        print(sid, spots[river_usual.key(float(r.lat), float(r.lon))], flush=True)
    doc = {"rule": "lake-order-overflow-v1", "record": "docs/LAKE-ORDER-OVERFLOW-LAKES-2026-11.md",
           "model_sha256": lake_range.SHA256, "years": [YEARS[0], YEARS[-1]], "months": [SEASON[0], SEASON[-1]],
           "rain_files_sha256": hashlib.sha256(b"".join(hashlib.sha256(p.read_bytes()).digest() for p in used)).hexdigest(),
           "rain_files": len(used), "spots": spots}
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(OUT, hashlib.sha256(OUT.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
