"""GloFAS daily discharge (Open-Meteo Flood API) against EA daily mean flow, for docs/GLOFAS-CHECK-2026-11.md.

    python scripts/glofas_check.py --cache <dir> --out <dir> [--network <river_network.pkl>] [--fetch]

Research only: nothing here feeds the site or the model.

- **Spots:** the river spots in spots.csv and spots-osm.csv, placed with locate_pin and the same hints
  as the site build (transport.spot_hints). Lakes are left out (see the note).
- **Gauges:** the Environment Agency Hydrology API's flow stations with a daily mean flow measure
  (OGL v3.0), snapped within GAUGE_SNAP_M of a river link, as scripts/make_lake_spill_ratio.py does.
  A spot qualifies when such a station is on the same river path (upstream or downstream of the spot
  along the network) within MAX_ALONG_M, and its catchment is within AREA_RATIO of the spot's. The
  catchments come from the network's upstream length (transport.catchment_km2), for both, so the
  ratio is like for like. Of the qualifying stations the nearest along the network is used.
- **GloFAS:** the Flood API's daily river_discharge, model GLOFAS_MODEL, cell_selection=nearest, at
  three places per pair: the spot, the 3 x 3 block of cells around the spot (0.05 degrees apart), and
  the gauge itself. One request per batch of locations; every response is cached in --cache.
- **EA:** each station's daily mean flow for the same days, one request per station with PAUSE_S
  between them, cached.

Without --fetch, only cached responses are read: a missing one stops the run, so a rerun never
reaches the network by accident.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_lake_spill_ratio import RIVER_FORMS, stations  # noqa: E402

from dipcast import config  # noqa: E402
from dipcast.model import transport as T  # noqa: E402
from dipcast.network.names import same_river  # noqa: E402
from dipcast.network.rivers import RiverNetwork, lonlat_to_bng  # noqa: E402

START, END = "2025-10-01", "2026-09-30"   # one year of days, ending before EA's qualified data thins out
GAUGE_SNAP_M = 250.0
MAX_ALONG_M = 25_000.0
AREA_RATIO = 2.0          # gauge catchment within a factor of 2 of the spot's
GLOFAS_MODEL = "seamless_v4"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
BATCH = 100               # locations per Flood API request
PAUSE_S = 2.0
SPOT_FILES = [config.ROOT / "spots.csv", config.ROOT / "spots-osm.csv"]
GRID = 0.05               # GloFAS v4 cell size, degrees
# A station that gauges one channel of several measures part of the river's flow, not GloFAS's error.
# The words were read off the EA labels of the stations near the spots on 18 Oct 2026, before any
# flow was fetched: Chilbolton Side and Main (Total exists), East Mills Flume (Combined exists),
# Barcombe Fishladder (Barcombe exists), Taplow Weir on the Jubilee Flood Relief Channel, Allbrook on
# the Itchen Navigation.
PART_LABEL = {"side", "main", "flume", "fishladder", "bypass", "intake"}
PART_RIVER = {"relief", "navigation", "carrier", "leat"}
TOTAL_WORDS = {"total", "combined"}
SAME_SITE_KM = 0.5


class Cache:
    """GET with a file cache. With fetch=False a miss is an error, not a request."""

    def __init__(self, root: Path, fetch: bool):
        self.root, self.fetch, self.n = root, fetch, 0
        root.mkdir(parents=True, exist_ok=True)
        self.http = httpx.Client(timeout=180, headers=config.EA_HEADERS)

    def get(self, url: str, params: dict, name: str) -> dict | list:
        f = self.root / name
        if f.exists():
            return json.loads(f.read_text())
        if not self.fetch:
            raise SystemExit(f"{f} is not cached; rerun with --fetch to request it")
        if self.n:
            time.sleep(PAUSE_S)
        self.n += 1
        r = self.http.get(url, params=params)
        if r.status_code in (403, 429) or r.status_code >= 500:
            raise SystemExit(f"{url} answered {r.status_code}: stopping")
        r.raise_for_status()
        f.write_text(r.text)
        return r.json()


def words(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", s.lower()))


def part_channel(label: str, river: str) -> bool:
    """A gauge that measures one channel of several, by its EA label or river name."""
    return bool(PART_LABEL & words(label)) or bool(PART_RIVER & words(river))


def name_of(v) -> str:
    """riverName is a string, a list of strings, or missing."""
    return " / ".join(map(str, v)) if isinstance(v, list) else ("" if v is None or v != v else str(v))


def catchment_at(net: RiverNetwork, link_id: str, frac: float) -> float:
    up = net.link_upstream_m(link_id) + frac * float(net.links.at[link_id, "length"])
    return float(T.catchment_km2(up))


def along(net: RiverNetwork, spot: tuple[str, float], gauge: tuple[str, float], cap: float) -> tuple[str, float] | None:
    """('downstream' | 'upstream', metres along the network) from the spot to the gauge, or None."""
    (ls, fs), (lg, fg) = spot, gauge
    Ls, Lg = float(net.links.at[ls, "length"]), float(net.links.at[lg, "length"])
    if ls == lg:
        return ("downstream" if fg >= fs else "upstream", abs(fg - fs) * Ls)
    a, b = net.links.at[ls, "start_node"], net.links.at[ls, "end_node"]
    down = net.downstream_nodes(b, cap)
    s = net.links.at[lg, "start_node"]
    if s in down:
        d = (1 - fs) * Ls + down[s] + fg * Lg
        return ("downstream", d) if d <= cap else None
    up = net.upstream_edges(a, cap)
    if lg in up:
        d = up[lg] + (1 - fg) * Lg + fs * Ls
        return ("upstream", d) if d <= cap else None
    return None


def km(lat1, lon1, lat2, lon2) -> float:
    p = np.pi / 180
    a = (np.sin((lat2 - lat1) * p / 2) ** 2
         + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return float(12742 * np.arcsin(np.sqrt(a)))


def match(net: RiverNetwork, ea: Cache) -> pd.DataFrame:
    spots = pd.concat([pd.read_csv(p) for p in SPOT_FILES if p.exists()], ignore_index=True).fillna("")
    spots = spots[~spots["id"].duplicated()]
    st = stations(ea)
    x, y = lonlat_to_bng(st["lon"].to_numpy(), st["lat"].to_numpy())
    snaps = []
    for s, sx, sy in zip(st.itertuples(), np.asarray(x), np.asarray(y), strict=True):
        sn = net.snap_xy(float(sx), float(sy), max_m=GAUGE_SNAP_M, forms=RIVER_FORMS)
        if sn is not None:
            snaps.append({**s._asdict(), "link_id": sn.link_id, "frac": sn.frac, "snap_m": sn.dist_m})
    snaps = pd.DataFrame(snaps).drop(columns="Index")
    print(f"{len(st)} EA flow stations with a daily mean; {len(snaps)} within {GAUGE_SNAP_M:.0f} m of a river link")

    rows = []
    for r in spots.itertuples(index=False):
        kind, river = T.spot_hints(r.kind, r.river)
        rec = {"id": r.id, "name": r.name, "kind": r.kind, "river": r.river, "area": r.area,
               "lat": float(r.lat), "lon": float(r.lon)}
        if r.kind != "river":
            rows.append({**rec, "why": "lake"})
            continue
        pin = T.locate_pin(net, float(r.lon), float(r.lat), kind_hint=kind, river_hint=river, name=r.name)
        if pin.mode != "river" or pin.snap is None:
            rows.append({**rec, "why": f"pin mode {pin.mode}"})
            continue
        spot = (pin.snap.link_id, pin.snap.frac)
        a_spot = catchment_at(net, *spot)
        rec.update(spot_km2=round(a_spot, 1), watercourse=pin.watercourse)
        near = snaps[[km(rec["lat"], rec["lon"], la, lo) <= MAX_ALONG_M / 1000 for la, lo in zip(snaps["lat"], snaps["lon"], strict=True)]]
        cands, seen = [], 0
        for g in near.itertuples():
            pos = along(net, spot, (g.link_id, g.frac), MAX_ALONG_M)
            if pos is None:
                continue
            seen += 1
            a_g = catchment_at(net, g.link_id, g.frac)
            ratio = a_g / a_spot if a_spot > 0 else np.inf
            label, griver = name_of(g.label), name_of(g.river)
            cands.append({"station": g.station, "station_label": label, "station_river": griver,
                          "measure": g.measure, "g_lat": g.lat, "g_lon": g.lon, "side": pos[0],
                          "along_km": round(pos[1] / 1000, 2),
                          "straight_km": round(km(rec["lat"], rec["lon"], g.lat, g.lon), 2),
                          "gauge_km2": round(a_g, 1), "area_ratio": round(ratio, 3),
                          "same_name": same_river(griver, r.river or pin.watercourse),
                          "part": part_channel(label, griver),
                          "total": bool(TOTAL_WORDS & words(label)),
                          "area_ok": 1 / AREA_RATIO <= ratio <= AREA_RATIO})
        ok = [c for c in cands if c["area_ok"] and not c["part"]]
        if not ok:
            why = ("no gauge on the river path" if not seen else
                   "only part-channel gauges" if any(c["area_ok"] for c in cands) else
                   "gauges on the path, catchment too different")
            rows.append({**rec, "why": why})
            continue
        # nearest along the network; a 'Total' or 'Combined' station at the same site goes first
        ok.sort(key=lambda c: (round(c["along_km"] / SAME_SITE_KM), not c["total"], c["along_km"]))
        skipped = [c["station_label"] for c in cands if c["part"] and c["area_ok"] and c["along_km"] < ok[0]["along_km"]]
        best = {k: v for k, v in ok[0].items() if k not in ("part", "total", "area_ok")}
        rows.append({**rec, **best, "skipped_part_channel": "; ".join(skipped), "why": ""})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--network", default=str(config.PROCESSED / "river_network.pkl"))
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--step", choices=("match", "all"), default="all")
    a = ap.parse_args()
    cache, out = Path(a.cache), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ea = Cache(cache / "ea", a.fetch)
    net = RiverNetwork.load(Path(a.network))
    m = match(net, ea)
    m.to_csv(out / "pairs.csv", index=False)
    ok = m[m["why"] == ""]
    print(m["why"].replace("", "qualifies").value_counts().to_string())
    print(ok[["name", "river", "station_label", "station_river", "side", "along_km", "straight_km",
              "spot_km2", "gauge_km2", "same_name"]].to_string())
    if a.step == "match":
        return


if __name__ == "__main__":
    main()
