"""CATCH-SIM, first deliverable: what the production spill model says at Cromwheel and Waterhead if the rain had been
scaled, or if one upstream overflow had not discharged. The method and the monotonicity check are in
docs/CATCH-SIM-2026-12.md, written before this was run. A sensitivity of the model on days already past: not a
prediction of any real upgrade, and never made by editing lta_spills (PR #298: that covariate is not monotone).

Offline: no Open-Meteo call, no EA request, no fetch. Every shared input is copied into the scratch DIPCAST_ROOT and
DIPCAST_STATE first and the originals are hashed (SHA-256) before and after; the run fails if any changed. The three
committed model files are copied from this checkout and must hash as committed.

    DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch>/state uv run python scripts/lab_catch_sim.py \
        --cache <main checkout> --log <a copy of the state release's dipcast.duckdb>

--cache is the checkout whose data/cache/rain (ERA5-Land archive, the forecast's cache) and
data/processed/ea_events_{yorkshire_water,united_utilities}.parquet are read. --log is the forecast log; from it this
reads only forecast_points.risk and forecast_overflows.p_cal, weight and travel_h (issued predictions, not outcomes).

Writes prototypes/research-lab/workspace/whatif/data/{cromwheel,waterhead}.json and index.json (the workspace's what-if
mode; build_site.write_lab leaves that folder out of the site) and docs/CATCH-SIM-2026-12-*.csv.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
assert os.environ.get("DIPCAST_ROOT") and os.environ.get("DIPCAST_STATE"), "set scratch DIPCAST_ROOT and DIPCAST_STATE"
ROOT = Path(os.environ["DIPCAST_ROOT"]).resolve()
assert not str(ROOT).startswith(str(REPO.parents[2] if len(REPO.parents) > 2 else REPO)), \
    "DIPCAST_ROOT must be a scratch folder outside the repositories"

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from dipcast import config  # noqa: E402
from dipcast.ingest.rainfall import cell_key, grid_cell  # noqa: E402
from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features, spill_days  # noqa: E402
from dipcast.model.forecast import calibrate_at_lead  # noqa: E402
from dipcast.model.spill_model import SpillModel  # noqa: E402
from dipcast.model.transport import combine_daily, history_days, risk_label, shown_score  # noqa: E402

TZ = "Europe/London"
YEARS = (2024, 2025)
SCALES = [round(0.5 + 0.1 * k, 1) for k in range(11)]   # x0.5 to x1.5
BASE = SCALES.index(1.0)
FALL_TOL = 1e-6          # a fall in expected spill days larger than this, one rain step up, is non-monotone
STOP_SHARE = 0.10        # the scoping record's stop rule: more than 10% non-monotone keeps removal only
LEVELS = ["low", "moderate", "high", "very high"]
LOG_LEADS = (3, 4)       # leads the log can rebuild exactly (no travel shift reaches before lead 0)
COMMITTED = ("spill_model.pkl", "lead_calibration.json", "annual_returns.parquet")
OUT = REPO / "prototypes" / "research-lab" / "workspace" / "whatif" / "data"
DOCS = REPO / "docs" / "CATCH-SIM-2026-12"

PLACES = {
    "cromwheel": {"spot": "bw-uke4100-08901", "lat": 53.93189, "lon": -1.81618, "workspace": "wharfe-ilkley",
                  "company": "yorkshire_water", "company_name": "Yorkshire Water", "short": "Cromwheel"},
    "waterhead": {"spot": "osm-windermere-waterhead", "lat": 54.41897, "lon": -2.96235, "workspace": "windermere",
                  "company": "united_utilities", "company_name": "United Utilities", "short": "Waterhead"},
}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def level(r: float) -> str:
    return risk_label(float(r))


# ------------------------------------------------------------------ inputs
def paths_asset(spot: str) -> dict:
    return json.loads((REPO / "prototypes" / "research-lab" / "assets" / "paths" / f"{spot}.json").read_text())


def overflow_cells(spot: str) -> list[tuple[float, float]]:
    ovs = paths_asset(spot)["overflows"]
    la, lo = grid_cell(np.array([o["lat"] for o in ovs]), np.array([o["lon"] for o in ovs]))
    return sorted({(float(a), float(b)) for a, b in zip(la, lo, strict=True)})


def shared_inputs(cache: Path, log: Path) -> dict[Path, Path]:
    """Each shared original and where its scratch copy goes."""
    m = {}
    for spec in PLACES.values():
        for cl, cn in overflow_cells(spec["spot"]):
            for y in (2023, 2024, 2025):
                name = f"archive_{cell_key(cl, cn)}_{y}.parquet"
                m[cache / "data" / "cache" / "rain" / name] = ROOT / "data" / "cache" / "rain" / name
        name = f"ea_events_{spec['company']}.parquet"
        m[cache / "data" / "processed" / name] = ROOT / "data" / "processed" / name
    m[log] = Path(os.environ["DIPCAST_STATE"]).resolve() / "dipcast.duckdb"
    return m


def copy_inputs(shared: dict[Path, Path]) -> dict:
    """Copy the shared originals and the committed model files into scratch. Returns the hashes."""
    for src, dst in shared.items():
        assert src.is_file(), f"missing input {src}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    committed = {}
    for name in COMMITTED:
        src, dst = REPO / "data" / "processed" / name, config.PROCESSED / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        committed[name] = {"sha256": sha(src), "md5": md5(src)}
    assert config.PROCESSED.resolve().is_relative_to(ROOT), "config.PROCESSED is not under the scratch root"
    return committed


def upstream(con: duckdb.DuckDBPyConnection, place: str) -> pd.DataFrame:
    """The spot's upstream overflows at the last issue in the log: weight and travel time as issued, name and
    position from the paths asset (the forecast's own network)."""
    spec = PLACES[place]
    where = f"lat = {spec['lat']} and lon = {spec['lon']}"
    last = con.execute(f"select cast(max(issued_at) as varchar) from forecast_overflows where {where}").fetchall()[0][0]
    up = con.execute(f"""select site_id, any_value(weight) as weight, any_value(travel_h) as travel_h, any_value(version) as version
                     from forecast_overflows where {where} and cast(issued_at as varchar) = ? group by site_id""", [last]).df()
    asset = {o["id"]: o for o in paths_asset(spec["spot"])["overflows"]}
    assert set(up["site_id"]) == set(asset), f"{place}: log and paths asset list different overflows"
    for k in ("name", "lat", "lon", "distance_km", "spills_a_year"):
        up[k] = up["site_id"].map(lambda s, k=k: asset[s][k])
    up["asset_weight"] = up["site_id"].map(lambda s: asset[s]["weight"])
    up["asset_travel_h"] = up["site_id"].map(lambda s: asset[s]["travel_h"])
    up["cell_lat"], up["cell_lon"] = grid_cell(up["lat"].to_numpy(), up["lon"].to_numpy())
    up["log_issued_at"] = str(last)
    return up.sort_values(["weight", "site_id"], ascending=[False, True]).reset_index(drop=True)


# ------------------------------------------------------------------ the hindcast
class Hindcast:
    def __init__(self, place: str, up: pd.DataFrame):
        self.place, self.up = place, up
        self.model = SpillModel.load()
        ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet").dropna(subset=["site_id"])
        self.ar = ar.drop_duplicates(["site_id", "year"], keep="last").set_index(["site_id", "year"])
        frames = []
        for cl, cn in sorted(set(zip(up["cell_lat"], up["cell_lon"], strict=True))):
            for y in (2023, 2024, 2025):
                frames.append(pd.read_parquet(config.CACHE / "rain" / f"archive_{cell_key(cl, cn)}_{y}.parquet"))
        rain = pd.concat(frames, ignore_index=True)
        self.rain = rain.assign(time=rain["time"].dt.tz_convert(TZ))
        self.w = up["weight"].to_numpy(float)
        self.t = up["travel_h"].to_numpy(float)
        self.hist = history_days(self.t)
        self.missing_returns: list[str] = []

    def sites(self, year: int) -> pd.DataFrame:
        """The covariates the forecast for `year` reads: the return of year - 1, unchanged."""
        rows = []
        for _, u in self.up.iterrows():
            key = (u["site_id"], year - 1)
            a = self.ar.loc[key] if key in self.ar.index else None
            if a is None:
                self.missing_returns.append(f"{u['site_id']} {year - 1}")
            r = {"site_id": u["site_id"], "lat": u["cell_lat"], "lon": u["cell_lon"], "company": PLACES[self.place]["company_name"]}
            for c in ("lta_spills", "spill_hours", "edm_operational_pct"):
                r[c] = np.nan if a is None else a[c]
            rows.append(r)
        return pd.DataFrame(rows)

    def days(self, year: int) -> tuple[pd.DatetimeIndex, np.ndarray]:
        # local midnights, built as calendar dates and then localised, so a clock change never shifts a day
        start = pd.Timestamp(f"{year}-01-01")
        days = pd.date_range(start - pd.Timedelta(days=self.hist), pd.Timestamp(f"{year}-12-31"), freq="D").tz_localize(TZ)
        return days, np.asarray(days >= start.tz_localize(TZ))

    def daily(self, scale: float) -> pd.DataFrame:
        return daily_rain_features(self.rain.assign(precip_mm=self.rain["precip_mm"] * scale))

    def chances(self, year: int, daily: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Lead-0 calibrated chances (overflows x days of the year's grid) and each overflow-day's rain_d."""
        days, _ = self.days(year)
        sd = build_site_days(self.sites(year), daily, days)
        for f in ALL_FEATURES:
            sd[f] = sd[f].astype(np.float32)
        sd["p"] = np.where(sd["rain_d"].notna(), self.model.predict(sd.fillna({f: 0.0 for f in ALL_FEATURES})), np.nan)
        piv = lambda col: sd.pivot(index="site_id", columns="day", values=col).reindex(index=self.up["site_id"], columns=days)  # noqa: E731
        raw = piv("p").to_numpy(float)
        return calibrate_at_lead(raw, 0), piv("rain_d").to_numpy(float)

    def risk(self, P: np.ndarray, drop: int | None = None) -> np.ndarray:
        p = np.nan_to_num(P)
        if drop is not None:
            p = p.copy()
            p[drop] = 0.0
        return combine_daily(p, self.w, self.t)


# ------------------------------------------------------------------ the forecast log: reproduction and removal
def issued(con: duckdb.DuckDBPyConnection, place: str, up: pd.DataFrame) -> dict:
    spec = PLACES[place]
    where = f"lat = {spec['lat']} and lon = {spec['lon']}"
    ov = con.sql(f"""select distinct issued_at, site_id, lead, p_cal, weight, travel_h from forecast_overflows
                     where {where}""").df()
    pts = con.sql(f"select distinct issued_at, lead, target_day, risk from forecast_points where {where}").df()
    ids = list(up["site_id"])
    rows, removal = [], {s: {"days": 0, "lowered": 0, "risk_drop_sum": 0.0, "risk_drop_max": 0.0} for s in ids}
    no_match = no_travel = 0
    for when, g in ov.groupby("issued_at"):
        if g["travel_h"].isna().any():   # the log kept no travel time before 12 Oct 2026 14:10: cannot be rebuilt
            no_travel += 1
            continue
        pr = pts[pts["issued_at"] == when].drop_duplicates("lead").set_index("lead")
        if pr.empty:
            no_match += 1
            continue
        sids = [s for s in ids if s in set(g["site_id"])]
        P = np.zeros((len(sids), 5))
        w = np.zeros(len(sids))
        t = np.zeros(len(sids))
        for i, s in enumerate(sids):
            gs = g[g["site_id"] == s].drop_duplicates("lead").set_index("lead")
            P[i] = [gs["p_cal"].get(k, np.nan) for k in range(5)]
            w[i], t[i] = gs["weight"].iloc[0], gs["travel_h"].iloc[0]
        r = combine_daily(np.nan_to_num(P), w, t)
        for k in LOG_LEADS:
            pub = pr["risk"].get(k, np.nan)
            if pd.isna(pub):
                continue
            rows.append({"issued_at": str(when), "lead": k, "target_day": str(pr.loc[k, "target_day"]), "published_risk": float(pub),
                         "rebuilt_risk": float(r[k]), "published_level": level(pub), "rebuilt_level": level(r[k]),
                         "overflows": len(sids)})
            for i, s in enumerate(sids):
                keep = np.ones(len(sids), bool)
                keep[i] = False
                rr = combine_daily(np.nan_to_num(P[keep]), w[keep], t[keep])[k]
                d = removal[s]
                d["days"] += 1
                d["lowered"] += int(LEVELS.index(level(rr)) < LEVELS.index(level(pub)))
                d["risk_drop_sum"] += float(r[k] - rr)
                d["risk_drop_max"] = max(d["risk_drop_max"], float(r[k] - rr))
    rep = pd.DataFrame(rows)
    diff = (rep["published_risk"] - rep["rebuilt_risk"]).abs()
    out = {
        "issues": int(rep["issued_at"].nunique()) if len(rep) else 0,
        "first_issue": rep["issued_at"].min() if len(rep) else None, "last_issue": rep["issued_at"].max() if len(rep) else None,
        "days": len(rep), "leads": list(LOG_LEADS),
        "level_equal": int((rep["published_level"] == rep["rebuilt_level"]).sum()),
        "max_abs_risk_diff": float(diff.max()) if len(rep) else None,
        "issues_without_points": no_match, "issues_without_travel_time": no_travel,
        "published_levels": {lv: int((rep["published_level"] == lv).sum()) for lv in LEVELS},
        "removal": {s: {"days": d["days"], "lowered": d["lowered"],
                        "mean_risk_drop": round(d["risk_drop_sum"] / max(1, d["days"]), 4),
                        "max_risk_drop": round(d["risk_drop_max"], 3)} for s, d in removal.items()},
    }
    out["passed"] = bool(len(rep) and out["level_equal"] == len(rep) and out["max_abs_risk_diff"] <= 1e-6)
    return out, rep


# ------------------------------------------------------------------ one place
def run_place(place: str, con, ea_events: pd.DataFrame) -> tuple[dict, dict]:
    spec = PLACES[place]
    up = upstream(con, place)
    hc = Hindcast(place, up)
    n = len(up)
    ids = list(up["site_id"])
    print(f"{place}: {n} overflows, history {hc.hist} days, log issue {up['log_issued_at'].iloc[0]}")

    # chances for every year and scale; rain_d for the outside-range share
    P, RD = {}, {}
    for s in SCALES:
        daily = hc.daily(s)
        for y in YEARS:
            P[(y, s)], RD[(y, s)] = hc.chances(y, daily)
            assert not np.isnan(P[(y, s)]).any(), f"{place} {y} x{s}: a day has no rain"
    assert not hc.missing_returns, f"{place}: missing annual returns {sorted(set(hc.missing_returns))}"

    # largest unscaled daily rain at any of this run's cells, 2023-25 (the outside-range proxy)
    unscaled = hc.daily(1.0)
    unscaled = unscaled[unscaled["day"] >= pd.Timestamp("2023-01-01", tz=TZ)]

    # expected spill days per overflow, year, scale
    expected = {y: np.array([[float(P[(y, s)][i][hc.days(y)[1]].sum()) for s in SCALES] for i in range(n)]) for y in YEARS}

    # monotonicity
    falls_ov = np.zeros(n, bool)
    largest_E_fall = 0.0
    day_falls = day_pairs = 0
    largest_day_fall = 0.0
    risk_falls = risk_pairs = 0
    for y in YEARS:
        E = expected[y]
        dE = np.diff(E, axis=1)
        falls_ov |= (dE < -FALL_TOL).any(axis=1)
        largest_E_fall = max(largest_E_fall, float(max(0.0, -dE.min())))
        keep = hc.days(y)[1]
        stack = np.stack([P[(y, s)][:, keep] for s in SCALES])           # scales x overflows x days
        d = np.diff(stack, axis=0)
        day_falls += int((d < -1e-12).sum())
        day_pairs += d.size
        largest_day_fall = max(largest_day_fall, float(max(0.0, -d.min())))
        rk = np.stack([hc.risk(P[(y, s)])[keep] for s in SCALES])
        dr = np.diff(rk, axis=0)
        risk_falls += int((dr < -1e-12).sum())
        risk_pairs += dr.size
    mono = {"overflows": n, "non_monotone": int(falls_ov.sum()), "non_monotone_ids": [ids[i] for i in np.flatnonzero(falls_ov)],
            "largest_expected_fall": largest_E_fall, "overflow_day_steps": day_pairs, "overflow_day_falls": day_falls,
            "largest_chance_fall": largest_day_fall, "spot_day_steps": risk_pairs, "spot_day_falls": risk_falls}

    # observed spill days (EA start/stop, UTC days as the model trains on) for calibration error at x1
    ev = ea_events[ea_events["site_id"].isin(ids)]
    obs = spill_days(ev)
    obs["year"] = obs["day"].dt.year
    observed = {y: obs[obs["year"] == y].groupby("site_id").size().reindex(ids).fillna(0).astype(int).to_numpy() for y in YEARS}
    events_any = ev.groupby("site_id").size().reindex(ids).fillna(0).astype(int)

    # risk series: year x scale x removal (None = as fitted)
    series, summary = {}, []
    for y in YEARS:
        days, keep = hc.days(y)
        for s in SCALES:
            for drop in [None, *range(n)]:
                r = hc.risk(P[(y, s)], drop)[keep]
                key = "none" if drop is None else ids[drop]
                score = [shown_score(v) for v in r]
                series[(y, s, key)] = (r, score)
                lv = [level(v) for v in r]
                summary.append({"place": place, "year": y, "scale": s, "removed": key,
                                **{f"days_{L.replace(' ', '_')}": lv.count(L) for L in LEVELS},
                                "days_moderate_or_above": sum(v != "low" for v in lv), "mean_risk": round(float(r.mean()), 4)})
    summ = pd.DataFrame(summary)

    # removal effects at x1 (and at every scale, for the mode)
    removal_rows = []
    for y in YEARS:
        for s in SCALES:
            base_r, _ = series[(y, s, "none")]
            base_l = np.array([LEVELS.index(level(v)) for v in base_r])
            for i, sid in enumerate(ids):
                r, _ = series[(y, s, sid)]
                lv = np.array([LEVELS.index(level(v)) for v in r])
                drop = base_r - r
                removal_rows.append({"place": place, "year": y, "scale": s, "removed": sid, "name": up.loc[i, "name"],
                                     "weight": round(float(up.loc[i, "weight"]), 5), "days_level_lower": int((lv < base_l).sum()),
                                     "days_level_higher": int((lv > base_l).sum()),
                                     "moderate_or_above_as_fitted": int((base_l > 0).sum()),
                                     "mean_risk_drop": round(float(drop.mean()), 4), "max_risk_drop": round(float(drop.max()), 3)})
    rem = pd.DataFrame(removal_rows)
    assert (rem["days_level_higher"] == 0).all(), "removing an overflow raised a level"

    # outside the rain the 2023-25 cells had: share of overflow-days whose scaled rain_d is above the largest unscaled
    outside = {}
    for s in SCALES:
        vals = np.concatenate([RD[(y, s)][:, hc.days(y)[1]].ravel() for y in YEARS])
        outside[s] = round(float((vals > CELL_MAX).mean()), 4)
    # Added after the protocol (13 Nov 2026), supplementary: the same share against this place's own cells only. The
    # stated proxy uses all 8 cells, whose wettest day is a Lake District one, so it says little at Cromwheel.
    place_max = float(unscaled["rain_d"].max())
    outside_place = {}
    for s in SCALES:
        vals = np.concatenate([RD[(y, s)][:, hc.days(y)[1]].ravel() for y in YEARS])
        outside_place[s] = round(float((vals > place_max).mean()), 4)

    # three storms: the wettest days of 2024-25 by the mean rain_d over this place's cells, unscaled, 7+ days apart
    cm = unscaled[(unscaled["day"] >= pd.Timestamp("2024-01-01", tz=TZ)) & (unscaled["day"] <= pd.Timestamp("2025-12-31", tz=TZ))]
    mean_rain = cm.groupby("day")["rain_d"].mean().sort_values(ascending=False)
    storms = []
    for d, mm in mean_rain.items():
        if all(abs((d - pd.Timestamp(x["day"], tz=TZ)).days) >= 7 for x in storms):
            storms.append({"day": d.date().isoformat(), "cells_mean_mm": round(float(mm), 1)})
        if len(storms) == 3:
            break
    storm_rows = []
    for st in storms:
        d0 = pd.Timestamp(st["day"], tz=TZ)
        y = d0.year
        days, keep = hc.days(y)
        yd = days[keep]
        for k in range(3):
            d = d0 + pd.Timedelta(days=k)
            if d.year != y:
                continue
            j = int(np.flatnonzero(yd == d)[0])
            for s in SCALES:
                for key in ["none", *ids]:
                    r, _ = series[(y, s, key)]
                    storm_rows.append({"place": place, "storm": st["day"], "day": d.date().isoformat(), "scale": s, "removed": key,
                                       "risk": round(float(r[j]), 3), "level": level(r[j])})
    storms_df = pd.DataFrame(storm_rows)

    # the forecast log
    log_check, log_rows = issued(con, place, up)
    print(f"{place}: log reproduction {log_check['level_equal']}/{log_check['days']} levels equal, "
          f"max risk diff {log_check['max_abs_risk_diff']:.2e}, passed {log_check['passed']}")

    # the export the mode reads
    ws = json.loads((REPO / "prototypes" / "research-lab" / "workspace" / "data" / f"{spec['workspace']}.json").read_text())
    ovs = []
    for i, u in up.iterrows():
        ovs.append({"id": u["site_id"], "name": u["name"], "weight": round(float(u["weight"]), 5), "travel_h": round(float(u["travel_h"]), 1),
                    "km": u["distance_km"], "lat": u["lat"], "lon": u["lon"],
                    "expected": {str(y): [round(v, 2) for v in expected[y][i]] for y in YEARS},
                    "observed": {str(y): int(observed[y][i]) for y in YEARS}, "events_in_file": int(events_any.iloc[i]),
                    "log_removal": log_check["removal"][u["site_id"]]})
    calib = {}
    for y in YEARS:
        E1, O = float(expected[y][:, BASE].sum()), int(observed[y].sum())
        calib[str(y)] = {"expected": round(E1, 1), "observed": O, "ratio": round(O / E1, 2) if E1 else None}
    out = {
        "place": place, "spot": spec["spot"], "name": paths_asset(spec["spot"])["name"], "short": spec["short"],
        "kind": paths_asset(spec["spot"])["kind"], "workspace": spec["workspace"], "company": spec["company_name"],
        "years": list(YEARS), "scales": SCALES, "base_scale": 1.0,
        "first_day": {str(y): f"{y}-01-01" for y in YEARS}, "overflows": ovs, "box": ws["box"],
        "lines": [ln for ln in ws["lines"]], "spot_lat": spec["lat"], "spot_lon": spec["lon"],
        "series": {str(y): {f"{s:.1f}": {k: series[(y, s, k)][1] for k in ["none", *ids]} for s in SCALES} for y in YEARS},
        "summary": summ.drop(columns=["place"]).to_dict(orient="records"),
        "monotonicity": mono, "calibration": calib, "outside_fitted_rain": {f"{s:.1f}": v for s, v in outside.items()},
        "outside_place_rain": {"max_daily_mm_2023_25": round(place_max, 1), "share": {f"{s:.1f}": v for s, v in outside_place.items()},
                               "note": "added after the protocol: against this place's own cells"},
        "storms": storms, "storm_levels": storms_df.drop(columns=["place", "risk"]).to_dict(orient="records"),
        "issued": {k: v for k, v in log_check.items() if k != "removal"},
        "model_version": up["version"].iloc[0], "log_issue": up["log_issued_at"].iloc[0],
        "weights_vs_paths_asset": {"max_weight_diff": round(float((up["weight"] - up["asset_weight"]).abs().max()), 5),
                                   "max_travel_h_diff": round(float((up["travel_h"] - up["asset_travel_h"]).abs().max()), 2)},
    }
    frames = {"summary": summ, "removal": rem, "storms": storms_df, "issued": log_rows.assign(place=place),
              "expected": pd.DataFrame([{"place": place, "site_id": ids[i], "name": up.loc[i, "name"], "year": y, "scale": s,
                                         "expected_spill_days": round(float(expected[y][i][k]), 3),
                                         **({"observed_spill_days": int(observed[y][i])} if s == 1.0 else {})}
                                        for y in YEARS for i in range(n) for k, s in enumerate(SCALES)])}
    return out, frames


CELL_MAX = np.nan   # set in main: the largest unscaled daily rain over all of this run's cells, 2023-25


def main() -> None:
    global CELL_MAX
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, required=True, help="the checkout whose data/cache/rain and ea_events files are read")
    ap.add_argument("--log", type=Path, required=True, help="the forecast log, dipcast.duckdb from the state release")
    args = ap.parse_args()

    shared = shared_inputs(args.cache.resolve(), args.log.resolve())
    before = {str(p): sha(p) for p in shared}
    committed = copy_inputs(shared)
    copies = {str(dst): sha(dst) for dst in shared.values()}
    assert sorted(before.values()) == sorted(copies.values()), "a scratch copy differs from its original"
    print(f"{len(shared)} shared inputs copied to scratch and hashed; committed model files {', '.join(COMMITTED)}")

    # the cell maximum, over all cells this run reads
    frames = [pd.read_parquet(dst) for src, dst in shared.items() if "/rain/" in str(dst)]
    rain = pd.concat(frames, ignore_index=True)
    d1 = daily_rain_features(rain.assign(time=rain["time"].dt.tz_convert(TZ)))
    CELL_MAX = float(d1.loc[d1["day"] >= pd.Timestamp("2023-01-01", tz=TZ), "rain_d"].max())

    con = duckdb.connect(str(shared[args.log.resolve()]), read_only=True)
    ea = pd.concat([pd.read_parquet(ROOT / "data" / "processed" / f"ea_events_{s['company']}.parquet") for s in PLACES.values()],
                   ignore_index=True)
    results, frames_all = {}, {}
    for place in PLACES:
        results[place], fr = run_place(place, con, ea)
        for k, v in fr.items():
            frames_all.setdefault(k, []).append(v)
    con.close()

    # the stop rule, over both places
    n_all = sum(r["monotonicity"]["overflows"] for r in results.values())
    bad = sum(r["monotonicity"]["non_monotone"] for r in results.values())
    rain_allowed = bad / n_all <= STOP_SHARE
    print(f"monotonicity: {bad} of {n_all} overflows non-monotone; rain scaling {'kept' if rain_allowed else 'dropped'}")

    after = {str(p): sha(p) for p in shared}
    assert before == after, "a shared input changed during the run"
    for name in COMMITTED:
        assert sha(REPO / "data" / "processed" / name) == committed[name]["sha256"], f"{name} changed during the run"

    commit = subprocess.run(["git", "rev-parse", "--short=8", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    made = datetime.now(UTC).isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    rel = lambda p: str(Path(p).relative_to(args.cache.resolve())) if Path(p).is_relative_to(args.cache.resolve()) else Path(p).name  # noqa: E731
    meta = {"made": made, "commit": commit, "code_sha256": sha(Path(__file__)), "cell_max_daily_mm_2023_25": round(CELL_MAX, 1),
            "monotonicity": {"overflows": n_all, "non_monotone": bad, "share_monotone": round(1 - bad / n_all, 3),
                             "stop_share": STOP_SHARE, "fall_tolerance": FALL_TOL, "rain_allowed": rain_allowed},
            "inputs": {"shared_sha256": {rel(k): v for k, v in before.items()}, "committed": committed,
                       "unchanged_after_run": True, "fetches": 0},
            "label": "The model's answer to a what-if, on days already past. Not a prediction of a real upgrade."}
    for place, r in results.items():
        r |= {"meta": meta, "rain_allowed": rain_allowed}
        (OUT / f"{place}.json").write_text(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n")
    (OUT / "index.json").write_text(json.dumps({"places": [{"id": p, "name": r["name"], "short": r["short"], "lat": r["spot_lat"], "lon": r["spot_lon"]}
                                                           for p, r in results.items()],
                                                **meta}, indent=1) + "\n")
    for k, v in frames_all.items():
        pd.concat(v, ignore_index=True).to_csv(f"{DOCS}-{k}.csv", index=False)
    print(f"{len(shared)} shared inputs hashed before and after: unchanged. Wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
