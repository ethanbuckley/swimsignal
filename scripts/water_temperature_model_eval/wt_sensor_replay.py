"""The EA sensor replay of docs/WATER-TEMPERATURE-SENSOR-REPLAY-2026-10.md (exploratory; deciding nothing).

    python -I wt_sensor_replay.py fetch --cache <private>/water-temperature/sensor-replay/ea [--fetch]
    python -I wt_sensor_replay.py score --cache <...>/ea --om-check <private>/water-temperature/open-meteo/check \\
        --features <private>/water-temperature/work/features.parquet --haduk-dir <private>/water-temperature/haduk \\
        --haduk-series <private>/water-temperature/work/haduk_series.npz --out <dir>

`fetch` asks the EA Hydrology API for each stated measure once (at most MAX_REQUESTS, cached, logged; network errors
retried after 30 s, 2 min and 5 min; any answer other than 200 a stop). `score` reads only files on disk: Part A runs
the estimate #418 ships (src/dipcast/model/water_temp.py) on amendment 3's cached archived forecast air; Part B refits
#414's fold model that holds each station's river group out (wt_protocol.fit_candidate) and feeds it HadUK air.
No Open-Meteo request is made by either.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "src")]
import wt_fetch as wf  # noqa: E402
import wt_protocol as wp  # noqa: E402

BASE = "https://environment.data.gov.uk/hydrology/id/measures"
MAX_REQUESTS = 12
LONDON = "Europe/London"
DAY_SHARE = 0.9               # a day needs this share of its expected readings at the series' own step (amendment 1)
DAYTIME = (10, 16)             # local hours [from, to) for the daytime mean, reported only
DROP_QUALITY = {"Suspect", "Missing", "Rejected"}

# The stated sensors: (key, label, river name as the statement gives it, measure, lat, lon, part-B years).
SENSORS = [
    ("lugg-meadows", "Lugg Meadows", "River Lugg", "E02703A-temp-i-subdaily-C", 52.0626, -2.6632, (2025,)),
    ("lugwardine", "Lugwardine", "River Lugg", "fe43947f-a0e9-49fe-9a11-5ef97f102fbd-temp-m-86400-C-qualified", 52.0618, -2.6597, (2023, 2024, 2025)),
    ("three-elms", "Three Elms", "Yazor Brook", "553c2147-bb82-4d86-8f0a-00b892d3c314-temp-m-86400-C-qualified", 52.0691, -2.7436, (2023, 2024, 2025)),
    ("teme-ludlow", "Teme at Ludlow", "River Teme", "E06567A-temp-i-subdaily-C", 52.3675, -2.7254, (2025,)),
    ("nidd-lido", "Nidd at Knaresborough Lido", "River Nidd", "E03700A-temp-i-subdaily-C", 53.9952, -1.4514, (2025,)),
    ("nidd-harrogate", "Nidd upstream of Harrogate WwTW", "River Nidd", "E08559A-temp-i-subdaily-C", 54.0253, -1.5409, (2025,)),
]


def window(years) -> tuple[str, str]:
    """Part A needs May-Sep 2025; a daily series also gives Part B's 2023-25. max-date is exclusive."""
    return (f"{min(years)}-05-01", "2025-10-01")


# ================================================================== fetching
class EAReadings:
    def __init__(self, cache: Path, fetch: bool, transport: httpx.BaseTransport | None = None, sleep=time.sleep):
        self.cache, self.fetch, self.sleep = Path(cache), fetch, sleep
        self.cache.mkdir(parents=True, exist_ok=True)
        self.log = wf.Log(self.cache / "requests.log")
        self.http = httpx.Client(transport=transport, timeout=120, headers={"Accept": "text/csv"})

    def spent(self) -> int:
        return sum(1 for x in self.log.lines() if len(x) >= 5 and x[1] == "200")

    def get(self, measure: str, start: str, end: str) -> str:
        f = self.cache / f"{measure}_{start}_{end}.csv"
        if f.exists():
            return f.read_text()
        if not self.fetch:
            raise wf.Stop(f"{f.name} is not cached; rerun with --fetch")
        if self.spent() >= MAX_REQUESTS:
            raise wf.Stop(f"the stated cap of {MAX_REQUESTS} EA requests is spent")
        url = f"{BASE}/{measure}/readings.csv?mineq-date={start}&max-date={end}&_limit=400000"
        r, _ = wf.send_with_retries(lambda: self.http.get(url), self.log, url, self.sleep)
        self.log.add(str(r.status_code), len(r.content), 1 if r.status_code == 200 else 0, url)
        if r.status_code != 200:
            raise wf.Stop(f"EA answered {r.status_code} for {measure}: stopping")
        f.write_text(r.text)
        return r.text


def readings(csv_text: str) -> pd.DataFrame:
    """The readings CSV as (time UTC, value, quality), with Suspect, Missing and Rejected readings dropped. The EA's
    hydrology times are GMT all year (its FAQ)."""
    d = pd.read_csv(io.StringIO(csv_text)) if csv_text.strip() else pd.DataFrame()
    if d.empty:
        return pd.DataFrame({"time": pd.Series(dtype="datetime64[ns, UTC]"), "value": [], "quality": []})
    q = d["quality"] if "quality" in d else pd.Series("", index=d.index)
    d = d.assign(quality=q.fillna("")).loc[~q.fillna("").isin(DROP_QUALITY)]
    t = pd.to_datetime(d["dateTime"], utc=True)
    return pd.DataFrame({"time": t, "value": pd.to_numeric(d["value"], errors="coerce"), "quality": d["quality"]}).dropna(subset=["value"])


def daily_means(r: pd.DataFrame, subdaily: bool) -> pd.DataFrame:
    """London-day means: a sub-daily series needs ceil(DAY_SHARE x the day's expected readings) at its own step (the
    most common gap: 87 of 96 at 15 minutes, 44 of 48 at 30, 22 of 24 hourly); a daily series is taken as given.
    Also the 10:00-16:00 local mean of a sub-daily series (NaN for a daily one)."""
    if r.empty:
        return pd.DataFrame(columns=["date", "mean", "daytime", "n"])
    local = r["time"].dt.tz_convert(LONDON)
    if not subdaily:
        return pd.DataFrame({"date": local.dt.normalize().dt.tz_localize(None), "mean": r["value"].to_numpy(),
                             "daytime": np.nan, "n": 1}).groupby("date", as_index=False).first()
    step = float(r["time"].sort_values().diff().dt.total_seconds().round(-1).mode().iloc[0])
    need = math.ceil(DAY_SHARE * 86400 / step)
    g = r.assign(date=local.dt.normalize().dt.tz_localize(None), hour=local.dt.hour)
    out = []
    for day, x in g.groupby("date"):
        if len(x) < need:
            continue
        dt = x[(x["hour"] >= DAYTIME[0]) & (x["hour"] < DAYTIME[1])]["value"]
        out.append({"date": day, "mean": float(x["value"].mean()), "daytime": float(dt.mean()) if len(dt) else np.nan, "n": len(x)})
    return pd.DataFrame(out)


# ================================================================== scoring helpers
def cell_key(lat: float, lon: float) -> str:
    return f"{np.round(np.round(lat / 0.1) * 0.1, 3) + 0.0:.3f}_{np.round(np.round(lon / 0.1) * 0.1, 3) + 0.0:.3f}"


def hist_forecast_frames(check_dir: Path) -> dict[str, dict]:
    """{cell: {"hourly": DataFrame(time, air_c), "elevation": m}} from amendment 3's cached archived forecasts."""
    out = {}
    for f in sorted(Path(check_dir).glob("histforecast_hist2025_*.json")):
        d = json.loads(f.read_text())
        lats, lons = d["params"]["latitude"].split(","), d["params"]["longitude"].split(",")
        for la, lo, a in zip(lats, lons, d["answer"], strict=True):
            h = a["hourly"]
            out[f"{float(la):.3f}_{float(lo):.3f}"] = {
                "hourly": pd.DataFrame({"time": pd.to_datetime(h["time"], utc=True), "air_c": np.asarray(h["temperature_2m"], float)}),
                "elevation": a.get("elevation")}
    return out


def errors(pred, obs) -> dict:
    e = np.asarray(pred, float) - np.asarray(obs, float)
    e = e[np.isfinite(e)]
    if not len(e):
        return {"days": 0}
    return {"days": int(len(e)), "rmse": float(np.sqrt(np.mean(e ** 2))), "bias": float(e.mean()),
            "p90": float(np.quantile(np.abs(e), 0.9)), "within_2": float(np.mean(np.abs(e) <= 2.0))}


# ================================================================== commands
def cmd_fetch(a) -> None:
    c = EAReadings(a.cache, a.fetch)
    for key, _label, _river, measure, _la, _lo, years in SENSORS:
        start, end = window(years)
        text = c.get(measure, start, end)
        print(f"{key}: {max(0, text.count(chr(10)) - 1)} rows ({start} to {end})")
    print(f"EA requests logged: {c.spent()} of {MAX_REQUESTS}")


def cmd_score(a) -> None:
    from dipcast.model import water_temp
    from dipcast.model.forecast import _net
    model = water_temp.load()
    net = _net()
    fc = hist_forecast_frames(a.om_check)
    c = EAReadings(a.cache, fetch=False)
    res = {"part_a": {}, "part_b": {}}
    obs = {}
    for key, label, river, measure, la, lo, years in SENSORS:
        start, end = window(years)
        dm = daily_means(readings(c.get(measure, start, end)), subdaily="subdaily" in measure)
        dm = dm[pd.to_datetime(dm["date"]).dt.month.between(5, 9)]
        obs[key] = dm
        if dm.empty:      # the two qualified daily series have no published readings (run log)
            res["part_a"][key] = {"label": label, "daily": {"days": 0}, "note": "no readings"}
            continue
        # ---- Part A: the deployed estimate, archived 2025 forecast air for the station's cell.
        cell = cell_key(la, lo)
        up = water_temp.upstream_km(net, lo, la)
        rows = []
        for d in dm[pd.to_datetime(dm["date"]).dt.year == 2025].itertuples():
            est = water_temp.estimate(model, fc[cell]["hourly"], pd.Timestamp(d.date), up, fc[cell]["elevation"])
            t = None
            if est:   # the unrounded value, for scoring: rebuild it as estimate() does before rounding
                t = _unrounded(model, fc[cell]["hourly"], pd.Timestamp(d.date), up, fc[cell]["elevation"])
            rows.append({"date": d.date, "obs": d.mean, "daytime": d.daytime, "est": t, "shown": est["temp_c"] if est else None})
        p = pd.DataFrame(rows)
        res["part_a"][key] = {"label": label, "cell": cell, "upstream_km": up, "elevation": fc[cell]["elevation"],
                              "daily": errors(p["est"], p["obs"]), "shown_whole_degrees": errors(p["shown"], p["obs"]),
                              "daytime": errors(p["est"], p["daytime"]),
                              "by_month": {int(m): errors(g["est"], g["obs"]) for m, g in p.groupby(pd.to_datetime(p["date"]).dt.month)}}
    res["part_a"]["pooled"] = _pool(res["part_a"])
    res["part_b"] = part_b(a, net, obs, {k: fc[cell_key(la, lo)]["elevation"] for k, _l, _r, _m, la, lo, _y in SENSORS})
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "sensor_replay.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


def _unrounded(model, hourly, today, upstream, elevation) -> float:
    """estimate()'s value before its int(round()): the same inputs and steps (water_temp.estimate)."""
    from dipcast.model.water_temp import daily_air
    day = daily_air(hourly)
    days = pd.date_range(today - pd.Timedelta(days=29), today, freq="D")
    s = day.reindex(days)
    c, d = model.bridge
    s = c + d * s
    ang = 2 * np.pi * today.dayofyear / 365.25
    up = np.log10(upstream) if upstream is not None and upstream > 0 else np.nan
    feats = {"a1": s.iloc[-1], "a7": s.iloc[-7:].mean(), "a30": s.mean(), "doy_sin": np.sin(ang), "doy_cos": np.cos(ang),
             "type_code": model.type_code["river"], "log_lake_area": np.nan, "log_upstream_km": up,
             "elevation": np.nan if elevation is None else float(elevation)}
    return float(model.predict_rows(pd.DataFrame([{**feats, "type": "river"}]))[0])


def _pool(part: dict) -> dict:
    """Pooled daily errors over the stations, weighted by days (from each station's RMSE and bias)."""
    blocks = [v["daily"] for k, v in part.items() if k != "pooled" and v["daily"].get("days")]
    n = sum(b["days"] for b in blocks)
    if not n:
        return {"days": 0}
    return {"days": n, "rmse": math.sqrt(sum(b["days"] * b["rmse"] ** 2 for b in blocks) / n),
            "bias": sum(b["days"] * b["bias"] for b in blocks) / n,
            "within_2": sum(b["days"] * b["within_2"] for b in blocks) / n}


def group_of(net, lat: float, lon: float) -> tuple[str | None, str]:
    """#414's river group for a point (wt_score.cmd_groups): the river link within RIVER_SNAP_M, its named river,
    else the first named river downstream."""
    import geopandas as gpd

    from dipcast.network.rivers import lonlat_to_bng
    x, y = lonlat_to_bng(lon, lat)
    links = net.links
    river_of = wp.named_rivers(links.reset_index(drop=True)[["id", "watercourse_name", "start_node", "end_node"]])
    rl = links[links["form"].isin(["inlandRiver", "tidalRiver"])]
    q, t = rl.sindex.nearest(gpd.points_from_xy([x], [y]), return_all=False, max_distance=wp.RIVER_SNAP_M)
    if not len(t):
        return None, "no river link within 250 m"
    lid = rl.index[t[0]]
    if lid in river_of:
        return river_of[lid], "named link"
    rid = wp.first_named_downstream(net.graph, rl.iloc[t[0]]["end_node"], river_of)
    return rid, "named downstream" if rid else "none"


def part_b(a, net, obs: dict, elevation: dict) -> dict:
    """#414's fold model with each station's river group out of fitting, fed HadUK air for the station's 5 km cell and
    the station's own catchment length; the cell elevation is Open-Meteo's for its 0.1 degree cell, as #414's rows had."""
    import h5py
    import wt_score as ws

    from dipcast.network.rivers import lonlat_to_bng
    f = pd.read_parquet(a.features)
    nc = sorted(Path(a.haduk_dir).glob("tas_hadukgrid_uk_5km_day_2018*.nc"))[0]
    with h5py.File(nc, "r") as h:
        tas0 = ws._read_var(h, "tas")[0]
        gx = h["projection_x_coordinate"][...].astype(float)
        gy = h["projection_y_coordinate"][...].astype(float)
    iy, ix = np.nonzero(np.isfinite(tas0))
    cx, cy = gx[ix], gy[iy]
    with np.load(a.haduk_series) as hz:
        cells, dates, tas = hz["cells"], pd.to_datetime(hz["dates"]), hz["tas"]
    out, fits = {}, {}
    for key, label, river, _measure, la, lo, years in SENSORS:
        if obs[key].empty:
            out[key] = {"label": label, "note": "no readings"}
            continue
        group, how = group_of(net, la, lo)
        if group is None:
            out[key] = {"label": label, "group": None, "how": how}
            continue
        k = wp.fold_of(group)
        if k not in fits:
            tr = f[(f["season"] == "train") & (f["fold"] != k)].reset_index(drop=True)
            rv = tr[tr["type"] == "river"]
            fits[k] = (wp.fit_candidate(tr), wp.fit_doy_baseline(rv["doy"], rv["temp"]), wp.fit_air7(rv["a7"], rv["temp"]),
                       set(tr["group"]))
        cand, doy_m, (ia, ib), train_groups = fits[k]
        bx, by = lonlat_to_bng(lo, la)
        ci, dist = wp.nearest_valid_cell(cx, cy, [bx], [by])
        j = np.flatnonzero(cells == int(ci[0]))
        if not len(j):
            out[key] = {"label": label, "group": group, "fold": k, "hk_cell": int(ci[0]), "note": "HadUK cell not in the stored series"}
            continue
        hk = pd.Series(tas[j[0]].astype(float), index=dates)
        dm = obs[key]
        dm = dm[pd.to_datetime(dm["date"]).dt.year.isin(years)]
        rows = []
        for y, g in dm.groupby(pd.to_datetime(dm["date"]).dt.year):
            feats = wp.air_features(ws._season(hk, y), pd.to_datetime(g["date"]))
            rows.append(pd.concat([g.reset_index(drop=True), feats], axis=1))
        te = pd.concat(rows, ignore_index=True).dropna(subset=["a1", "a7", "a30"])
        te = wp.add_doy(te)
        from dipcast.model import water_temp
        u = water_temp.upstream_km(net, lo, la)
        te = te.assign(type="river", type_code=wp.TYPE_CODE["river"], log_lake_area=np.nan,
                       log_upstream_km=np.log10(u) if u else np.nan,
                       elevation=np.nan if elevation.get(key) is None else float(elevation[key]), temp=te["mean"])
        s1, full = wp.predict_candidate(cand, te)
        out[key] = {"label": label, "group": group, "how": how, "fold": k, "group_in_training": group in train_groups,
                    "hk_cell": int(ci[0]), "hk_dist_m": float(dist[0]), "years": list(years),
                    "candidate": errors(full, te["temp"]), "air7": errors(ia + ib * te["a7"], te["temp"]),
                    "doy": errors(wp.predict_doy(doy_m, te["doy"]), te["temp"]),
                    "by_year": {int(y): errors(full[g.index], g["temp"]) for y, g in te.groupby(pd.to_datetime(te["date"]).dt.year)}}
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch")
    p.add_argument("--cache", required=True, type=Path)
    p.add_argument("--fetch", action="store_true")
    s = sub.add_parser("score")
    for k in ("cache", "om_check", "features", "haduk_dir", "haduk_series", "out"):
        s.add_argument("--" + k.replace("_", "-"), required=True, type=Path, dest=k)
    a = ap.parse_args(argv)
    (cmd_fetch if a.cmd == "fetch" else cmd_score)(a)


if __name__ == "__main__":
    main()
