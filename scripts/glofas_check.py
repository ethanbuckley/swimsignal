"""GloFAS daily discharge (Open-Meteo Flood API) against EA daily mean flow, for docs/GLOFAS-CHECK-2026-11.md.

    python scripts/glofas_check.py --cache <dir> --out <dir> [--network <river_network.pkl>] [--fetch]
                                   [--step match|compare|all]

Research only: nothing here feeds the site or the model. `match` needs the river network and writes
pairs.csv; `compare` reads pairs.csv and needs no network.

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

The measures and the verdict rule are the ones stated in the doc before any flow was fetched. The
measures marked "added after the first results" in `measures` are reported, not part of the rule.

Without --fetch, only cached responses are read: a missing one stops the run, so a rerun never
reaches the network by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_lake_spill_ratio import RIVER_FORMS, stations

from dipcast import config
from dipcast.model import transport as T
from dipcast.network.names import same_river
from dipcast.network.rivers import RiverNetwork, lonlat_to_bng

START, END = "2025-10-01", "2026-09-30"   # one year of days, ending before EA's qualified data thins out
GAUGE_SNAP_M = 250.0
MAX_ALONG_M = 25_000.0
AREA_RATIO = 2.0          # gauge catchment within a factor of 2 of the spot's
GLOFAS_MODEL = "seamless_v4"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
BATCH = 100               # locations per Flood API request
PAUSE_S = 2.0             # between EA requests
# Open-Meteo weighs a location max(1, variables/10 x days/14): 2.6 for one variable over 365 days, so
# a batch of 100 is about 260 calls. Its free limit is 600 a minute per IP, shared with other local work.
FLOOD_PAUSE_S = 40.0
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
MIN_DAYS = 300            # days with both values for a pair to count
DROP_QUALITY = {"Suspect", "Rejected", "Missing"}


class Cache:
    """GET with a file cache. With fetch=False a miss is an error, not a request."""

    def __init__(self, root: Path, fetch: bool, pause_s: float = PAUSE_S):
        self.root, self.fetch, self.n, self.pause_s = root, fetch, 0, pause_s
        root.mkdir(parents=True, exist_ok=True)
        self.http = httpx.Client(timeout=180, headers=config.EA_HEADERS)

    def get(self, url: str, params: dict, name: str) -> dict | list:
        f = self.root / name
        if f.exists():
            return json.loads(f.read_text())
        if not self.fetch:
            raise SystemExit(f"{f} is not cached; rerun with --fetch to request it")
        if self.n:
            time.sleep(self.pause_s)
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
    return " / ".join(map(str, v)) if isinstance(v, list) else ("" if v is None or pd.isna(v) else str(v))


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


def cell_centre(v: float) -> float:
    return round(np.floor(v / GRID) * GRID + GRID / 2, 3)


def block(lat: float, lon: float) -> list[tuple[float, float]]:
    """The 3 x 3 GloFAS cells centred on the cell holding (lat, lon); the centre cell first."""
    c = (cell_centre(lat), cell_centre(lon))
    out = [c]
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                out.append((round(c[0] + dy * GRID, 3), round(c[1] + dx * GRID, 3)))
    return out


def ea_flow(ea: Cache, measure: str) -> tuple[pd.Series, dict]:
    d = ea.get(f"{config.EA_HYDROLOGY}/id/measures/{measure}/readings.json",
               {"mineq-date": START, "maxeq-date": END, "_limit": 2000}, f"readings_{measure}_{START}_{END}.json")
    q = pd.DataFrame(d.get("items", []))
    if q.empty:
        return pd.Series(dtype=float), {}
    q["value"] = pd.to_numeric(q.get("value"), errors="coerce")
    qual = q["quality"].fillna("") if "quality" in q else pd.Series("", index=q.index)
    counts = qual.value_counts().to_dict()
    q = q[q["value"].notna() & ~qual.isin(DROP_QUALITY)]
    return pd.Series(q["value"].to_numpy(float), index=pd.to_datetime(q["date"])).sort_index(), counts


def glofas(om: Cache, cells: list[tuple[float, float]]) -> dict[tuple[float, float], pd.Series]:
    out = {}
    cells = sorted(set(cells))
    for i in range(0, len(cells), BATCH):
        part = cells[i:i + BATCH]
        key = hashlib.sha256(json.dumps(part).encode()).hexdigest()[:12]
        d = om.get(FLOOD_URL, {"latitude": ",".join(f"{c[0]:.3f}" for c in part),
                               "longitude": ",".join(f"{c[1]:.3f}" for c in part),
                               "daily": "river_discharge", "models": GLOFAS_MODEL, "cell_selection": "nearest",
                               "start_date": START, "end_date": END}, f"flood_{START}_{END}_{key}.json")
        d = d if isinstance(d, list) else [d]
        for c, r in zip(part, d, strict=True):
            got = (round(r["latitude"], 3), round(r["longitude"], 3))
            if abs(got[0] - c[0]) > 0.001 or abs(got[1] - c[1]) > 0.001:
                raise SystemExit(f"asked for cell {c}, got {got}")
            daily = r["daily"]
            col = next(k for k in daily if k.startswith("river_discharge"))
            out[c] = pd.Series(pd.to_numeric(pd.Series(daily[col]), errors="coerce").to_numpy(float),
                               index=pd.to_datetime(daily["time"]))
    return out


def anomaly(x: pd.Series) -> pd.Series:
    lx = np.log(x.clip(lower=1e-3))
    return lx - lx.rolling(31, center=True, min_periods=15).mean()


def measures(g: pd.Series, q: pd.Series) -> dict:
    """GloFAS g against gauge q (already scaled), on the days both have."""
    days = pd.date_range(START, END, freq="D")
    g, q = g.reindex(days), q.reindex(days)
    both = g.notna() & q.notna()
    n = int(both.sum())
    if n < MIN_DAYS:
        return {"days": n}
    gb, qb = g[both], q[both]
    ga, qa = anomaly(g.where(both)), anomaly(q.where(both))
    rho = float(gb.corr(qb, method="spearman"))
    ev = float(ga.corr(qa, method="spearman"))
    lags = {L: float(qa.corr(ga.shift(-L), method="spearman")) for L in range(-3, 4)}
    q90, g90 = qb.quantile(0.9), gb.quantile(0.9)
    high = (g.where(both) >= g90)
    near = high | high.shift(1, fill_value=False) | high.shift(-1, fill_value=False)
    qhigh = both & (q >= q90)
    r = float(np.corrcoef(gb, qb)[0, 1])
    alpha, beta = float(gb.std() / qb.std()), float(gb.mean() / qb.mean())
    # Added after the first results, outside the verdict rule: the same measures one day later, the
    # same-day hit rate, and a seasonal-only benchmark (GloFAS's centred 31-day mean, which keeps the
    # wet winter and dry summer and loses every event).
    g1 = g.shift(-1).where(both)
    hi1 = g1 >= g1[both].quantile(0.9)
    smooth = g.rolling(31, center=True, min_periods=15).mean().where(both)
    s90 = smooth[both].quantile(0.9)
    shigh = smooth >= s90
    snear = shigh | shigh.shift(1, fill_value=False) | shigh.shift(-1, fill_value=False)
    return {"days": n, "bias": beta, "rho": rho, "event_rho": ev, "hit": float(near[qhigh].mean()),
            "lag": max(lags, key=lags.get), "kge": 1 - float(np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)),
            "g_mean": float(gb.mean()), "q_mean": float(qb.mean()),
            "wrong": bool(not (1 / 3 <= beta <= 3) or rho < 0.5),
            "event_rho_lag1": lags[1], "rho_lag1": float(g1.corr(q.where(both), method="spearman")),
            "hit_same_day": float(high[qhigh].mean()), "hit_same_day_lag1": float(hi1[qhigh].mean()),
            "season_rho": float(smooth.corr(q.where(both), method="spearman")), "season_hit": float(snear[qhigh].mean())}


def compare(pairs: pd.DataFrame, ea: Cache, om: Cache, out: Path) -> None:
    ok = pairs[pairs["why"].fillna("") == ""].reset_index(drop=True)
    blocks = {r.id: block(r.lat, r.lon) for r in ok.itertuples()}
    gcell = {r.station: (cell_centre(r.g_lat), cell_centre(r.g_lon)) for r in ok.itertuples()}
    cells = sorted({c for b in blocks.values() for c in b} | set(gcell.values()))
    weight = len(cells) * max(1.0, 1 / 10 * len(pd.date_range(START, END)) / 14)
    print(f"{len(cells)} distinct GloFAS cells, about {weight:.0f} Open-Meteo calls by its own weighting, "
          f"in {-(-len(cells) // BATCH)} requests")
    g = glofas(om, cells)
    flows, quality = {}, {}
    for st, m in ok.groupby("station")["measure"].first().items():
        flows[st], quality[st] = ea_flow(ea, m)

    rows, block_rows = [], []
    for r in ok.itertuples():
        q = flows[r.station]
        scale = r.spot_km2 / r.gauge_km2
        est = T.QMEAN_PER_KM2 * r.spot_km2
        means = {c: float(g[c].mean()) for c in blocks[r.id]}
        valid = {c: v for c, v in means.items() if np.isfinite(v) and v > 0}
        rule = min(valid, key=lambda c: abs(np.log(valid[c] / est))) if valid else blocks[r.id][0]
        base = {"id": r.id, "name": r.name, "station": r.station_label, "side": r.side, "along_km": r.along_km,
                "straight_km": r.straight_km, "area_ratio": round(1 / scale, 3), "net_est_m3s": est}
        for c in blocks[r.id]:
            mm = measures(g[c], q * scale)
            block_rows.append({**base, "cell": f"{c[0]:.3f},{c[1]:.3f}", "centre": c == blocks[r.id][0],
                               "rule": c == rule, "cell_mean": means[c], **mm})
        for name, c in (("a_nearest", blocks[r.id][0]), ("b_area_rule", rule)):
            rows.append({**base, "cells": name, "cell": f"{c[0]:.3f},{c[1]:.3f}",
                         "cell_km": round(km(r.lat, r.lon, *c), 2), "moved": c != blocks[r.id][0],
                         **measures(g[c], q * scale)})
    st_rows = []
    for st, grp in ok.groupby("station"):
        r = grp.iloc[0]
        c = gcell[st]
        st_rows.append({"station": r.station_label, "river": r.station_river, "spots": len(grp), "cells": "c_gauge_cell",
                        "cell": f"{c[0]:.3f},{c[1]:.3f}", "cell_km": round(km(r.g_lat, r.g_lon, *c), 2),
                        "quality": json.dumps(quality[st]), **measures(g[c], flows[st])})
    spot = pd.DataFrame(rows)
    gauge = pd.DataFrame(st_rows)
    spot.to_csv(out / "spot_measures.csv", index=False, float_format="%.4g")
    gauge.to_csv(out / "gauge_measures.csv", index=False, float_format="%.4g")
    pd.DataFrame(block_rows).to_csv(out / "block_measures.csv", index=False, float_format="%.4g")

    def summary(df: pd.DataFrame, label: str) -> dict:
        d = df[df["days"] >= MIN_DAYS]
        return {"cells": label, "pairs": len(d), "short": int((df["days"] < MIN_DAYS).sum()),
                "median_bias": d["bias"].median(), "median_rho": d["rho"].median(),
                "median_event_rho": d["event_rho"].median(), "median_hit": d["hit"].median(),
                "median_kge": d["kge"].median(), "wrong": int(d["wrong"].sum()),
                "lag0_share": float((d["lag"] == 0).mean()), "lag1_share": float((d["lag"] == 1).mean()),
                "median_event_rho_lag1": d["event_rho_lag1"].median(), "median_rho_lag1": d["rho_lag1"].median(),
                "median_hit_same_day": d["hit_same_day"].median(), "median_hit_same_day_lag1": d["hit_same_day_lag1"].median(),
                "median_season_rho": d["season_rho"].median(), "median_season_hit": d["season_hit"].median()}
    summ = pd.DataFrame([summary(spot[spot["cells"] == "a_nearest"], "a_nearest"),
                         summary(spot[spot["cells"] == "b_area_rule"], "b_area_rule"),
                         summary(gauge, "c_gauge_cell")])
    summ.to_csv(out / "summary.csv", index=False, float_format="%.4g")
    print(summ.T.to_string())
    b = summ.set_index("cells").loc["b_area_rule"]
    cond = {"1 median rho >= 0.80": b["median_rho"] >= 0.80, "2 median event rho >= 0.50": b["median_event_rho"] >= 0.50,
            "3 median hit >= 0.50": b["median_hit"] >= 0.50, "4 wrong river <= 4": b["wrong"] <= 4}
    for k, v in cond.items():
        print(f"condition {k}: {'PASS' if v else 'FAIL'}")
    print(f"verdict: {'tracks' if all(cond.values()) else 'does not track'} (rule b, {int(b['pairs'])} spots); "
          f"{om.n} Flood API requests, {ea.n} EA requests made")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--network", default=str(config.PROCESSED / "river_network.pkl"))
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--step", choices=("match", "compare", "all"), default="all")
    a = ap.parse_args()
    cache, out = Path(a.cache), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ea = Cache(cache / "ea", a.fetch)
    if a.step in ("match", "all"):
        net = RiverNetwork.load(Path(a.network))
        m = match(net, ea)
        m.to_csv(out / "pairs.csv", index=False)
        ok = m[m["why"] == ""]
        print(m["why"].replace("", "qualifies").value_counts().to_string())
        print(ok[["name", "river", "station_label", "station_river", "side", "along_km", "straight_km",
                  "spot_km2", "gauge_km2", "same_name"]].to_string())
    if a.step in ("compare", "all"):
        compare(pd.read_csv(out / "pairs.csv"), ea, Cache(cache / "om", a.fetch, FLOOD_PAUSE_S), out)


if __name__ == "__main__":
    main()
