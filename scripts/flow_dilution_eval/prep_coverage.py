"""Outcome-blind coverage for docs/FLOW-DILUTION-TEST-2026-10.md ("Seen before writing"), from metadata only.

    python scripts/flow_dilution_eval/prep_coverage.py <station cache dir> <out.csv>

Reads, and nothing else:
- the two station lists flow_fetch.py `stations` cached (EA Hydrology flow stations; real-time flow stations);
- the gauge columns of docs/GLOFAS-CHECK-2026-11-spots.csv (station, side, along_km, area_ratio, why), whose
  rule (same river path within 25 km up or down, catchment within a factor of 2, no part channel) is this
  test's spot-gauge rule and was run on the network on 18 October 2026;
- the river bathing waters in data/processed/validation_sites.csv (name, mode) and their EA points in
  data/raw/bathing_waters_inland.json (name, lat, lon).
No E. coli value, no reading of any flow, no model. The run recomputes the mapping on the run's network and pins;
these counts are the expectation, not the gate.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow_fetch import measure_ids

ROOT = Path(__file__).resolve().parents[2]
NEAR_KM = 30.0
IDS = ("stationReference", "wiskiID", "RLOIid")


def ids(st: dict, key: str) -> set[str]:
    """A station id field, which the EA gives as a string or a list of strings."""
    v = st.get(key)
    return {str(x) for x in (v if isinstance(v, list) else [v]) if x not in (None, "")}


def km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = (np.sin((lat2 - lat1) * p / 2) ** 2
         + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * np.arcsin(np.sqrt(a))


def main(cache: str, out: str) -> None:
    hy = json.load(open(glob.glob(f"{cache}/*hydrology_id_stations*")[0]))["items"]
    fm = json.load(open(glob.glob(f"{cache}/*flood-monitoring_id_stations*")[0]))["items"]
    rt_refs = {v for s in fm for k in IDS for v in ids(s, k)}
    by_guid = {s.get("notation"): s for s in hy}
    sites = pd.read_csv(ROOT / "data/processed/validation_sites.csv")
    rivers = sites[sites["mode"] == "river"]["name"]
    pts = {b["name"]: b for b in json.load(open(ROOT / "data/raw/bathing_waters_inland.json"))}
    gl = pd.read_csv(ROOT / "docs/GLOFAS-CHECK-2026-11-spots.csv",
                     usecols=["name", "station", "station_label", "station_river", "side", "along_km", "area_ratio",
                              "why"]).drop_duplicates("name").set_index("name")
    rows = []
    for n in rivers:
        r = {"site": n}
        b = pts.get(n)
        if b is not None:
            same = [s for s in hy if isinstance(s.get("lat"), (int, float))
                    and km(b["lat"], b["lon"], s["lat"], s["long"]) <= NEAR_KM]
            r["hy_flow_stations_within_30km"] = len(same)
        g = gl.loc[n] if n in gl.index else None
        if g is None or not isinstance(g["station"], str):
            r.update(gauge=None, why=None if g is None else g["why"])
            rows.append(r)
            continue
        guid = g["station"].split("_")[0]
        st = by_guid.get(g["station"]) or by_guid.get(guid) or {}
        m = measure_ids(st)
        status = st.get("status")
        status = status[0].get("label") if isinstance(status, list) and status else status
        r.update(gauge=g["station_label"], river=g["station_river"], side=g["side"], along_km=g["along_km"],
                 area_ratio=g["area_ratio"], daily=bool(m["daily"]), q15=bool(m["q15"]),
                 opened=st.get("dateOpened"), closed=st.get("dateClosed"), status=status,
                 realtime=bool({v for k in IDS for v in ids(st, k)} & rt_refs))
        rows.append(r)
    t = pd.DataFrame(rows)
    t.to_csv(out, index=False)
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))
    has = t["gauge"].notna()
    print(f"\n{len(t)} river bathing waters; {int(has.sum())} with a spot gauge "
          f"({int((t.side == 'upstream').sum())} upstream, {int((t.side == 'downstream').sum())} downstream); "
          f"{int(t.get('q15', pd.Series(dtype=bool)).fillna(False).sum())} with a 15-minute flow series; "
          f"{int(t.get('realtime', pd.Series(dtype=bool)).fillna(False).sum())} on the real-time flow feed; "
          f"{t['gauge'].nunique()} distinct gauges; hydrology flow stations {len(hy)}, real-time {len(fm)}")


if __name__ == "__main__":
    main(*sys.argv[1:])
