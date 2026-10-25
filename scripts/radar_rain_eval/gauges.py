"""docs/RADAR-RAIN-CHECK-2026-10.md: the Environment Agency's 15-minute rain gauge totals in the radar cells.

    gauges.py <radar dir> <out dir>

Every Hydrology API rainfall station whose position falls in a cell with radar files gets its 15-minute totals
(measure `-rainfall-t-900-mm-qualified`) from 21 Nov 2024 to 23 Oct 2026, fetched one station and one year at a
time. Readings flagged Suspect or Missing, or with no value, are dropped. A reading's dateTime is taken as the start
of its quarter-hour (GMT), so the quarters starting HH:00 to HH:45 make the hour ending HH+1, the stamp the radar and
the forecast use. An hour is kept only with all four quarters. Writes <out dir>/gauges_hourly.parquet (station,
cell_lat, cell_lon, time, precip_mm), stations.csv and requests.json (every request and its result).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.rainfall import grid_cell

API = "https://environment.data.gov.uk/hydrology"
SPANS = (("2024-11-21", "2025-01-01"), ("2025-01-01", "2026-01-01"), ("2026-01-01", "2026-10-24"))
DROP_QUALITY = {"Suspect", "Missing"}
PAUSE_S = 0.3


def radar_cells(radar_dir: Path) -> set[tuple[float, float]]:
    out = set()
    for f in radar_dir.glob("radar_*.parquet"):
        p = f.stem.split("_")
        out.add((float(p[1]), float(p[2])))
    return out


def get(client: httpx.Client, url: str, params: dict, log: list) -> dict | None:
    for attempt in range(5):
        try:
            r = client.get(url, params=params)
            log.append({"url": url, "params": params, "status": r.status_code, "attempt": attempt})
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError as e:
            log.append({"url": url, "params": params, "error": str(e), "attempt": attempt})
        time.sleep(2 ** attempt)
    return None


def hourly(items: list[dict]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=["time", "precip_mm"])
    d = pd.DataFrame(items)
    d = d[~d["quality"].isin(DROP_QUALITY) & d["value"].notna()]
    t = pd.to_datetime(d["dateTime"]).dt.tz_localize("UTC")
    d = pd.DataFrame({"start": t, "v": d["value"].astype(float)}).drop_duplicates("start", keep="last")
    d["time"] = d["start"].dt.floor("h") + pd.Timedelta(hours=1)
    g = d.groupby("time")["v"].agg(["sum", "count"])
    g = g[g["count"] == 4]
    return g["sum"].rename("precip_mm").reset_index()


def main(radar_dir: str, out_dir: str) -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    cells = radar_cells(Path(radar_dir))
    log: list = []
    client = httpx.Client(headers=config.EA_HEADERS, timeout=120.0, follow_redirects=True)
    st = get(client, f"{API}/id/stations.json", {"observedProperty": "rainfall", "_limit": 5000}, log)["items"]
    rows = []
    for s in st:
        if s.get("lat") is None or s.get("long") is None:
            continue
        cl, cn = grid_cell(float(s["lat"]), float(s["long"]))
        cl, cn = float(cl), float(cn)
        m = [x["@id"] for x in s.get("measures", []) if x.get("period") == 900]
        if (cl, cn) in cells and m:
            rows.append({"station": s["notation"], "label": s.get("label"), "lat": s["lat"], "lon": s["long"],
                         "cell_lat": cl, "cell_lon": cn, "measure": m[0]})
    stations = pd.DataFrame(rows)
    stations.to_csv(out / "stations.csv", index=False)
    print(f"{len(st)} rainfall stations, {len(stations)} in {stations[['cell_lat', 'cell_lon']].drop_duplicates().shape[0]} radar cells")
    frames = []
    for i, s in stations.iterrows():
        items = []
        for a, b in SPANS:
            j = get(client, f"{s['measure']}/readings.json", {"mineq-date": a, "max-date": b, "_limit": 200000}, log)
            if j is not None:
                items += j.get("items", [])
            time.sleep(PAUSE_S)
        h = hourly(items)
        h = h[(h["time"] > pd.Timestamp("2024-11-21", tz="UTC")) & (h["time"] <= pd.Timestamp("2026-10-24", tz="UTC"))]
        frames.append(h.assign(station=s["station"], cell_lat=s["cell_lat"], cell_lon=s["cell_lon"]))
        if i % 25 == 0:
            print(f"{i + 1}/{len(stations)} stations, {sum(len(f) for f in frames)} hours")
    g = pd.concat(frames, ignore_index=True)
    g["precip_mm"] = g["precip_mm"].astype(np.float32)
    g.to_parquet(out / "gauges_hourly.parquet", index=False)
    fails = [x for x in log if x.get("status") != 200]
    (out / "requests.json").write_text(json.dumps({"requests": len(log), "not_200": len(fails), "failures": fails[:200]},
                                                  indent=1, default=str))
    print(f"done: {len(g)} gauge-hours, {len(log)} requests, {len(fails)} not 200")


if __name__ == "__main__":
    main(*sys.argv[1:])
