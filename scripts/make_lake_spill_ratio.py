"""Spill-time flow ratios of WFD lakes, for lake path 'residence_spill' (docs/LAKE-RESIDENCE-SPILL-2026-10.md).

    python scripts/make_lake_spill_ratio.py --cache <dir> [--out data/raw/lake_residence_spill.csv]

HydroLAKES' residence time (data/raw/lake_residence.csv) is the lake's volume over its long-term MEAN
outflow. Overflows spill in wet weather, when more water passes through. For each lake this finds:

- **Its spill days:** the calendar days (UTC) that any part of a United Utilities event in
  data/processed/edm_events.parquet (2023-2025, the only event records held) covers, at an overflow upstream
  of the lake's outlet within config.MAX_UPSTREAM_KM, or on the lake.
- **Its reference gauge:** of the Environment Agency Hydrology API's flow stations (daily mean flow,
  OGL v3.0) that snap within GAUGE_SNAP_M of a river link, the one nearest the lake along the network,
  within GAUGE_MAX_M. A station counts if it is on the outflow (downstream of the outlet) or on an inflow
  (it drains into the lake), measured from the outlet or to the lake. A tie goes to the outflow.
- **R:** the median, over spill days with a reading, of that day's mean flow over the station's long-term mean
  flow, which is the mean of every daily mean in its record. At least MIN_DAYS such days are needed.

τ_spill = τ / max(R, 1). A lake with no R takes the median R of the lakes that have one: no gauge, no United
Utilities overflow upstream, or too few days. Requests go to the EA Hydrology API only, one at a time with
PAUSE_S between them. Each response is cached in --cache, so a second run makes none.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from dipcast import config
from dipcast.model import transport as T
from dipcast.network.rivers import RiverNetwork, lonlat_to_bng
from dipcast.overflows import load_overflows

STATIONS = f"{config.EA_HYDROLOGY}/id/stations.json"
GAUGE_SNAP_M = 250.0     # a station this close to a river link is on it
GAUGE_MAX_M = 10_000.0   # along the network, from the outlet (outflow) or to the lake (inflow)
MIN_DAYS = 30            # spill days with a reading
PAUSE_S = 2.0
RIVER_FORMS = ("inlandRiver", "tidalRiver", "canal")
OUT = config.RAW / "lake_residence_spill.csv"


class Client:
    def __init__(self, cache: Path):
        self.cache, self.n = cache, 0
        cache.mkdir(parents=True, exist_ok=True)
        self.http = httpx.Client(timeout=120, headers=config.EA_HEADERS)

    def get(self, url: str, params: dict, name: str) -> dict:
        f = self.cache / name
        if f.exists():
            return json.loads(f.read_text())
        if self.n:
            time.sleep(PAUSE_S)
        self.n += 1
        r = self.http.get(url, params=params)
        if r.status_code in (403, 429) or r.status_code >= 500:
            raise SystemExit(f"EA Hydrology answered {r.status_code} for {r.url}: stopping, as the statement says")
        r.raise_for_status()
        f.write_text(r.text)
        return r.json()


def daily_mean_measure(st: dict) -> str | None:
    for m in st.get("measures", []):
        mid = m.get("@id", "") if isinstance(m, dict) else str(m)
        if mid.endswith("-flow-m-86400-m3s-qualified"):
            return mid.rsplit("/", 1)[-1]
    return None


def stations(client: Client) -> pd.DataFrame:
    d = client.get(STATIONS, {"observedProperty": "waterFlow", "_limit": 10000}, "stations_waterFlow.json")
    rows = []
    for st in d.get("items", []):
        mid = daily_mean_measure(st)
        lat, lon = st.get("lat"), st.get("long")
        if mid and isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            rows.append({"station": st.get("notation") or st.get("stationReference"), "label": st.get("label"),
                         "river": st.get("riverName"), "lat": float(lat), "lon": float(lon), "measure": mid})
    return pd.DataFrame(rows)


def lake_links(net: RiverNetwork) -> dict[int, set[str]]:
    links = net.links
    of = T._wfd_lake_of(net, list(links.index[links["form"] == "lake"]))
    out: dict[int, set[str]] = {}
    for lid, (k, _) in of.items():
        out.setdefault(k, set()).add(lid)
    return out


def gauge_for(net: RiverNetwork, comp: set[str], outlet: str, snaps: pd.DataFrame) -> dict | None:
    """The nearest station along the network within GAUGE_MAX_M: on the outflow or on an inflow."""
    down = net.downstream_nodes(outlet, GAUGE_MAX_M)
    up = net.upstream_edges(outlet, GAUGE_MAX_M + 50_000)
    best = None
    for s in snaps.itertuples():
        start, length = net.links.at[s.link_id, "start_node"], float(net.links.at[s.link_id, "length"])
        cand = None
        if start in down:
            cand = ("outflow", down[start] + s.frac * length)
        elif s.link_id in up and s.link_id not in comp:
            res = T._walk_to_lake(net, s.link_id, s.frac, comp, set(up))
            if res is not None:
                cand = ("inflow", res[0])
        if cand and cand[1] <= GAUGE_MAX_M:
            key = (cand[1], cand[0] != "outflow")
            if best is None or key < best[0]:
                best = (key, {"side": cand[0], "gauge_m": round(cand[1]), "station": s.station, "label": s.label,
                              "river": s.river, "measure": s.measure})
    return None if best is None else best[1]


def spill_days(events: pd.DataFrame, sites: set[str]) -> set:
    e = events[events["site_id"].isin(sites)]
    days: set = set()
    for a, b in zip(e["event_start"].dt.date, e["event_end"].dt.date, strict=True):
        days.update(pd.date_range(a, b, freq="D").date)
    return days


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--residence", default=str(config.RAW / "lake_residence.csv"))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    client = Client(Path(a.cache))
    res = pd.read_csv(a.residence)
    net = RiverNetwork.load()
    ov = load_overflows(net)
    uu = ov[ov["site_id"].str.startswith("UU")]
    events = pd.read_parquet(config.PROCESSED / "edm_events.parquet", columns=["site_id", "event_start", "event_end"])
    lakes = T._lakes()
    row_of = {w: i for i, w in enumerate(lakes["wb_id"])}
    comps = lake_links(net)

    st = stations(client)
    x, y = lonlat_to_bng(st["lon"].to_numpy(), st["lat"].to_numpy())
    snaps = []
    for s, sx, sy in zip(st.itertuples(), np.asarray(x), np.asarray(y), strict=True):
        sn = net.snap_xy(float(sx), float(sy), max_m=GAUGE_SNAP_M, forms=RIVER_FORMS)
        if sn is not None:
            snaps.append({"station": s.station, "label": s.label, "river": s.river, "measure": s.measure,
                          "link_id": sn.link_id, "frac": sn.frac})
    snaps = pd.DataFrame(snaps)
    print(f"{len(st)} flow stations with a daily mean; {len(snaps)} within {GAUGE_SNAP_M:.0f} m of a river link")

    cap = config.MAX_UPSTREAM_KM * 1000.0
    rows = []
    for r in res.itertuples():
        k = row_of.get(r.wb_id)
        comp = comps.get(k) if k is not None else None
        rec = {"wb_id": r.wb_id, "lake_name": r.lake_name, "res_time_mean_d": r.res_time_d}
        if not comp:
            rows.append({**rec, "why": "no lake links"})
            continue
        outlet = T._lake_outlet(net, comp)
        on_path = set(net.upstream_edges(outlet, cap)) | comp
        sites = set(uu.loc[uu["link_id"].isin(on_path), "site_id"])
        rec["uu_overflows"] = len(sites)
        g = gauge_for(net, comp, outlet, snaps)
        if g:
            rec.update(g)
        days = spill_days(events, sites) if sites else set()
        rec["spill_days"] = len(days)
        if not g or not days:
            rows.append({**rec, "why": "no gauge" if not g else "no United Utilities overflow upstream"})
            continue
        d = client.get(f"{config.EA_HYDROLOGY}/id/measures/{g['measure']}/readings.json", {"_limit": 100000},
                       f"readings_{g['measure']}.json")
        q = pd.DataFrame(d.get("items", []))
        if q.empty or "value" not in q:
            rows.append({**rec, "why": "no readings"})
            continue
        q = q[pd.to_numeric(q["value"], errors="coerce").notna()]
        q["value"] = q["value"].astype(float)
        when = q["date"] if "date" in q else q["dateTime"].astype(str).str[:10]
        q["day"] = pd.to_datetime(when).dt.date
        qmean = float(q["value"].mean())
        on = q[q["day"].isin(days)]
        rec.update({"q_mean_m3s": qmean, "record_from": str(q["day"].min()), "record_to": str(q["day"].max()),
                    "days_with_flow": len(on)})
        if len(on) < MIN_DAYS or qmean <= 0:
            rows.append({**rec, "why": f"under {MIN_DAYS} spill days with a reading"})
            continue
        rec["R"] = float((on["value"] / qmean).median())
        rec["R_source"] = "gauge"
        rows.append(rec)
    out = pd.DataFrame(rows)
    gauged = out["R"].notna() if "R" in out else pd.Series(False, index=out.index)
    med = float(out.loc[gauged, "R"].median()) if gauged.any() else 1.0
    out.loc[~gauged, "R"] = med
    out.loc[~gauged, "R_source"] = "median of gauged lakes"
    out["R_used"] = out["R"].clip(lower=1.0)
    out["res_time_d"] = out["res_time_mean_d"] / out["R_used"]
    out.to_csv(a.out, index=False, float_format="%.6g")
    print(f"{int(gauged.sum())} of {len(out)} lakes gauged with enough spill days; median R {med:.3f}; "
          f"{client.n} requests made")


if __name__ == "__main__":
    main()
