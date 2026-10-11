"""Where transport.py's DRAINAGE_KM_PER_KM2, QMEAN_PER_KM2 and Q50_PER_KM2 come from.

The 'catchment' travel speed and the 'flow' dilution (config.VELOCITY_MODE, config.DILUTION_MODE)
need each place's catchment area and median flow. The network has neither, only the length of
river upstream (RiverNetwork.upstream_m). This script snaps the NRFA's gauging stations to the
network and prints three medians: network km per km² of catchment, and mean flow and Q50 per km².

Input: one call to the NRFA station-info API, kept in CACHE/nrfa_stations.csv. NRFA data are
under UKCEH's own terms, not the OGL: no redistribution of the data and no cache older than 30
days (https://eidc.ceh.ac.uk/licences/nrfa-data-terms-and-conditions-for-api-access-to-time-series-data-and-metadata).
The station table stays in the git-ignored cache; only the three medians enter the code.
Credit: "Data from the UK National River Flow Archive".

Stations: open, in England and Wales (northing under 660 km), with a catchment area. Each goes
to the river link within 300 m with the most network upstream (gauges sit on the main channel,
not a mill race beside it). Stations with under 0.5 km of network upstream are left out.

    uv run python scripts/fit_reach_velocity.py
"""

from __future__ import annotations

import io
import time

import httpx
import numpy as np
import pandas as pd
from shapely.geometry import Point

from dipcast import config
from dipcast.network.rivers import RiverNetwork

URL = "https://nrfaapps.ceh.ac.uk/nrfa/ws/station-info"
FIELDS = "id,name,catchment-area,easting,northing,gdf-mean-flow,gdf-q50-flow,closed"
CACHE = config.CACHE / "nrfa_stations.csv"
MAX_AGE_DAYS = 30
SNAP_M = 300.0


def stations() -> pd.DataFrame:
    if not CACHE.exists() or time.time() - CACHE.stat().st_mtime > MAX_AGE_DAYS * 86400:
        r = httpx.get(URL, params={"station": "*", "format": "csv", "fields": FIELDS},
                      headers=config.EA_HEADERS, timeout=120)
        r.raise_for_status()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(r.text)
    return pd.read_csv(io.StringIO(CACHE.read_text()))


def main() -> None:
    st = stations().rename(columns={"catchment-area": "area", "gdf-mean-flow": "qmean", "gdf-q50-flow": "q50"})
    st = st[st["closed"].isna() & (st["northing"] < 660_000)].dropna(subset=["area", "easting", "northing"])
    net = RiverNetwork.load()
    rows = []
    for s in st.itertuples(index=False):
        cand = net.candidates_xy(s.easting, s.northing, SNAP_M)
        cand = cand[cand["form"].isin(["inlandRiver", "tidalRiver", "lake"])]
        if cand.empty:
            continue
        pt = Point(s.easting, s.northing)
        up = cand["start_node"].map(net.upstream_m).fillna(0.0) + cand["length"] * cand.geometry.project(pt, normalized=True)
        rows.append({"area": s.area, "lup_km": float(up.max()) / 1000, "qmean": s.qmean, "q50": s.q50})
    d = pd.DataFrame(rows)
    d = d[d["lup_km"] > 0.5]
    dd = d["lup_km"] / d["area"]
    print(f"{len(d)} stations snapped of {len(st)}")
    print(f"DRAINAGE_KM_PER_KM2 = {dd.median():.2f}  (half within a factor of "
          f"{np.exp(np.subtract(*np.percentile(np.log(dd), [75, 25]))):.2f} of the median)")
    by = d.assign(dd=dd, bin=pd.qcut(np.log(d["area"]), 8)).groupby("bin", observed=True)["dd"].median()
    print("median by eighth of the stations, smallest catchments first:", by.round(2).tolist())
    for col, name in (("qmean", "QMEAN_PER_KM2"), ("q50", "Q50_PER_KM2")):
        ok = d[col] > 0
        print(f"{name} = {(d.loc[ok, col] / d.loc[ok, 'area']).median():.4f}  ({ok.sum()} stations)")


if __name__ == "__main__":
    main()
