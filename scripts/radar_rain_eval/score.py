"""docs/RADAR-RAIN-CHECK-2026-10.md: radar against gauges (Q1, Q1b), forecast rain against radar (Q2), and the spill
model fed radar rain (Q3).

    score.py <radar dir> <gauge dir> <out.json>

Rain sources, all hourly per cell, made daily with features.daily_rain_features (UTC days, a day with under
MIN_HOURS_PER_DAY valid hours has no total):
    radar      <radar dir>/radar_<cell>_<YYYY-MM>.parquet, an hour valid when coverage >= 0.9
    gauges     <gauge dir>/gauges_hourly.parquet (gauges.py), one series per station
    forecast   cache leads_<cell>_<year>.parquet, leads 0 to 4 (training.RAIN_DIRS)
    ERA5-Land  cache archive_<cell>_<year>.parquet (training.load_rain)
Q3 follows scripts/verify_leads.py for 2025, with radar as one more source, United Utilities left out.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel
from dipcast.model.training import NINE, RAIN_DIRS, load_events, load_rain, site_years

COVERAGE = 0.9
W_START, W_END = pd.Timestamp("2024-12-01", tz="UTC"), pd.Timestamp("2026-09-13", tz="UTC")
X_START, X_END = pd.Timestamp("2026-09-14", tz="UTC"), pd.Timestamp("2026-10-23", tz="UTC")
LEADS = [0, 1, 2, 3, 4]
KEY = ["cell_lat", "cell_lon", "day"]
WARN = 0.4
SEED, BOOT = 20261024, 2000
EXCLUDE = "United Utilities"


def season(day: pd.Series) -> pd.Series:
    m = day.dt.month
    return pd.Series(np.select([m.isin([12, 1, 2]), m.isin([3, 4, 5]), m.isin([6, 7, 8])], ["DJF", "MAM", "JJA"], "SON"),
                     index=day.index)


def north_west(cl, cn) -> np.ndarray:
    return (np.asarray(cl) > 53.3) & (np.asarray(cn) < -2.0)


def load_radar(radar_dir: Path, cells=None) -> pd.DataFrame:
    frames = []
    for f in sorted(radar_dir.glob("radar_*.parquet")):
        p = f.stem.split("_")
        if cells is not None and (float(p[1]), float(p[2])) not in cells:
            continue
        frames.append(pd.read_parquet(f))
    r = pd.concat(frames, ignore_index=True)
    r["precip_mm"] = np.where(r["coverage"] >= COVERAGE, r["radar_mm"], np.nan).astype(float)
    return r[["cell_lat", "cell_lon", "time", "precip_mm"]]


def load_leads(cells) -> dict[int, pd.DataFrame]:
    frames = []
    for d in RAIN_DIRS:
        for f in (config.CACHE / d).glob("leads_*.parquet"):
            p = f.stem.split("_")
            if (float(p[1]), float(p[2])) in cells and p[3] in ("2024", "2025", "2026"):
                frames.append(pd.read_parquet(f))
    lv = pd.concat(frames, ignore_index=True).drop_duplicates(["cell_lat", "cell_lon", "time", "lead"], keep="last")
    return {k: daily_rain_features(lv[lv.lead == k].drop(columns="lead")) for k in LEADS}


def daily(df: pd.DataFrame, a=W_START, b=W_END) -> pd.DataFrame:
    d = df[(df["day"] >= a) & (df["day"] <= b)]
    return d[KEY + ["rain_d"]].dropna()


def three(truth: np.ndarray, est: np.ndarray, groups: np.ndarray, min_days: int = 200) -> dict:
    """Question 1's three figures for est against truth (daily totals, mm)."""
    rho = []
    for g in np.unique(groups):
        m = groups == g
        if m.sum() >= min_days and np.std(truth[m]) > 0 and np.std(est[m]) > 0:
            rho.append(spearmanr(truth[m], est[m]).statistic)
    wet, dry = truth >= 1.0, truth < 0.2
    return {"n_days": int(len(truth)), "ratio_totals": float(est.sum() / truth.sum()) if truth.sum() > 0 else None,
            "median_spearman": float(np.median(rho)) if rho else None, "n_series_spearman": len(rho),
            "wet_detected": float((est[wet] >= 1.0).mean()) if wet.any() else None,
            "dry_kept_dry": float((est[dry] < 1.0).mean()) if dry.any() else None,
            "mae_mm": float(np.abs(est - truth).mean()), "bias_mm": float((est - truth).mean())}


def q1_pass(t: dict) -> dict:
    c = {"1_totals": t["ratio_totals"] is not None and 0.80 <= t["ratio_totals"] <= 1.25,
         "2_spearman": t["median_spearman"] is not None and t["median_spearman"] >= 0.75,
         "3_wet_dry": (t["wet_detected"] or 0) >= 0.80 and (t["dry_kept_dry"] or 0) >= 0.90}
    c["passes"] = all(c.values())
    return c


def rain_skill(truth: np.ndarray, fc: np.ndarray) -> dict:
    wet = truth >= 10
    return {"n": int(len(truth)), "mae_mm": float(np.abs(fc - truth).mean()), "bias_mm": float((fc - truth).mean()),
            "ratio_totals": float(fc.sum() / truth.sum()) if truth.sum() > 0 else None,
            "pearson": float(np.corrcoef(truth, fc)[0, 1]) if len(truth) > 2 else None,
            "hit_10mm": float((fc[wet] >= 10).mean()) if wet.any() else None,
            "false_10mm": float((fc[~wet] >= 10).mean()) if (~wet).any() else None}


def week_boot(y, pa, pb, week) -> dict:
    """Brier(a) - Brier(b), with a bootstrap over ISO weeks."""
    ea, eb = (pa - y) ** 2, (pb - y) ** 2
    wk, inv = np.unique(week, return_inverse=True)
    sa, sb, n = np.bincount(inv, ea), np.bincount(inv, eb), np.bincount(inv)
    rng = np.random.default_rng(SEED)
    d = []
    for _ in range(BOOT):
        pick = rng.integers(0, len(wk), len(wk))
        d.append((sa[pick].sum() - sb[pick].sum()) / n[pick].sum())
    return {"diff": float(ea.mean() - eb.mean()), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
            "weeks": int(len(wk))}


def main(radar_dir: str, gauge_dir: str, out_path: str) -> None:
    radar_dir, res = Path(radar_dir), {}
    radar_hourly = load_radar(radar_dir)
    cells = set(map(tuple, radar_hourly[["cell_lat", "cell_lon"]].drop_duplicates().to_numpy()))
    radar = daily_rain_features(radar_hourly)
    res["radar_cells"] = len(cells)

    # ---- Q1: radar (and ERA5-Land) against gauges
    gh = pd.read_parquet(Path(gauge_dir) / "gauges_hourly.parquet")
    st = gh[["station", "cell_lat", "cell_lon"]].drop_duplicates("station").reset_index(drop=True)
    st["gid"] = np.arange(len(st), dtype=float)
    gh = gh.merge(st[["station", "gid"]], on="station")
    gd = daily_rain_features(gh.assign(cell_lat=gh["gid"], cell_lon=0.0)[["cell_lat", "cell_lon", "time", "precip_mm"]])
    gd = gd.rename(columns={"cell_lat": "gid"})[["gid", "day", "rain_d"]].dropna().merge(st, on="gid")
    era = daily_rain_features(load_rain(cells, tags=("2024", "2025", "2026"), start="2024-11-25"))

    def vs_gauges(a, b, with_era: bool):
        m = gd[(gd.day >= a) & (gd.day <= b)].merge(radar[KEY + ["rain_d"]].dropna(), on=KEY, suffixes=("_g", "_r"))
        if with_era:
            m = m.merge(era[KEY + ["rain_d"]].dropna().rename(columns={"rain_d": "rain_d_e"}), on=KEY, how="left")
        return m

    m = vs_gauges(W_START, W_END, True)
    t, r, g = m["rain_d_g"].to_numpy(), m["rain_d_r"].to_numpy(), m["station"].to_numpy()
    q1 = {"gauges_with_days": int(m["station"].nunique()), "gauges_fetched": int(len(st)),
          "all": three(t, r, g)}
    q1["conditions"] = q1_pass(q1["all"])
    s = season(m["day"])
    q1["by_season"] = {k: three(t[s == k], r[s == k], g[s == k], min_days=50) for k in ("DJF", "MAM", "JJA", "SON")}
    nw = north_west(m["cell_lat"], m["cell_lon"])
    q1["north_west"] = three(t[nw], r[nw], g[nw]); q1["rest"] = three(t[~nw], r[~nw], g[~nw])
    q1["per_gauge"] = [{"station": k, "cell": [float(d.cell_lat.iloc[0]), float(d.cell_lon.iloc[0])], "n": len(d),
                        "ratio": float(d.rain_d_r.sum() / d.rain_d_g.sum()) if d.rain_d_g.sum() > 0 else None,
                        "spearman": float(spearmanr(d.rain_d_g, d.rain_d_r).statistic) if len(d) > 10 else None}
                       for k, d in m.groupby("station")]
    e = m.dropna(subset=["rain_d_e"])
    q1["q1b_same_days"] = {"n_days": len(e),
                          "radar": three(e.rain_d_g.to_numpy(), e.rain_d_r.to_numpy(), e.station.to_numpy()),
                          "era5_land": three(e.rain_d_g.to_numpy(), e.rain_d_e.to_numpy(), e.station.to_numpy())}
    mx = vs_gauges(X_START, X_END, False)
    q1["extra_window_radar"] = three(mx.rain_d_g.to_numpy(), mx.rain_d_r.to_numpy(), mx.station.to_numpy(), min_days=20)
    # Face check on time stamps: hourly gauge against radar at -1, 0 and +1 h.
    gh2 = gh[(gh.time > W_START) & (gh.time <= W_END + pd.Timedelta(days=1))]
    align = {}
    for sh in (-1, 0, 1):
        rr = radar_hourly.assign(time=radar_hourly.time + pd.Timedelta(hours=sh))
        j = gh2.merge(rr, on=["cell_lat", "cell_lon", "time"], suffixes=("_g", "_r")).dropna()
        j = j[(j.precip_mm_g > 0) | (j.precip_mm_r > 0)]
        align[str(sh)] = float(np.corrcoef(j.precip_mm_g, j.precip_mm_r)[0, 1])
    q1["hourly_alignment_corr"] = align
    res["q1"] = q1
    radar_ok = q1["conditions"]["passes"]

    # ---- Q2: forecast rain by lead against radar (and against gauges in gauge cells)
    leads = load_leads(cells)
    base = daily(radar).rename(columns={"rain_d": "truth"})
    for k in LEADS:
        base = base.merge(daily(leads[k]).rename(columns={"rain_d": f"l{k}"}), on=KEY)
    s2, nw2 = season(base["day"]), north_west(base["cell_lat"], base["cell_lon"])
    q2 = {"truth": "radar", "cells": int(base[["cell_lat", "cell_lon"]].drop_duplicates().shape[0]),
          "by_lead": {k: rain_skill(base.truth.to_numpy(), base[f"l{k}"].to_numpy()) for k in LEADS},
          "by_lead_season": {sn: {k: rain_skill(base.truth[s2 == sn].to_numpy(), base[f"l{k}"][s2 == sn].to_numpy())
                                  for k in LEADS} for sn in ("DJF", "MAM", "JJA", "SON")},
          "by_lead_north_west": {k: rain_skill(base.truth[nw2].to_numpy(), base[f"l{k}"][nw2].to_numpy()) for k in LEADS},
          "by_lead_rest": {k: rain_skill(base.truth[~nw2].to_numpy(), base[f"l{k}"][~nw2].to_numpy()) for k in LEADS}}
    gcell = gd.groupby(KEY)["rain_d"].mean().rename("truth").reset_index()
    gb = gcell[(gcell.day >= W_START) & (gcell.day <= W_END)]
    for k in LEADS:
        gb = gb.merge(daily(leads[k]).rename(columns={"rain_d": f"l{k}"}), on=KEY)
    q2["against_gauges"] = {"cells": int(gb[["cell_lat", "cell_lon"]].drop_duplicates().shape[0]),
                            "by_lead": {k: rain_skill(gb.truth.to_numpy(), gb[f"l{k}"].to_numpy()) for k in LEADS}}
    bl = q2["by_lead"]
    q2["stated"] = {"error_grows_with_lead": all(bl[k]["mae_mm"] <= bl[k + 1]["mae_mm"] for k in LEADS[:-1]),
                    "lead0_pearson_ge_0.7": bl[0]["pearson"] >= 0.7,
                    "totals_within_20pct_every_lead": all(0.8 <= bl[k]["ratio_totals"] <= 1.2 for k in LEADS)}
    res["q2"] = q2

    # ---- Q3: the spill model fed each rain source, 2025 (verify_leads.py's rows and method)
    model = SpillModel.load(config.PROCESSED / "spill_model.pkl")
    ev = load_events(NINE)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    labels = spill_days(ev)
    labels = labels[labels.day.dt.year == 2025]
    lv25 = set()
    for d in RAIN_DIRS:
        for f in (config.CACHE / d).glob("leads_*_2025.parquet"):
            p = f.stem.split("_"); lv25.add((float(p[1]), float(p[2])))
    use = lv25 & cells
    era25 = daily_rain_features(load_rain(use, tags=("2024", "2025"), start="2024-12-01"))
    sites, _ = site_years(ar, ev, NINE, 2025)
    sites = sites[sites["company"] != EXCLUDE]
    sites = sites[[c in use for c in zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True)]]
    days = pd.date_range("2025-01-01", "2025-12-31", freq="D", tz="UTC")
    b3 = build_site_days(sites, era25, days, labels)

    def fed(name: str, k: int) -> pd.DataFrame:
        df = b3.copy()
        cols = ["rain_d", "max1h_d", "max3h_d", "max6h_d"]
        same = (radar if name == "radar" else leads[k])[KEY + cols]
        df = df.drop(columns=cols).merge(same, on=KEY, how="left")
        for shift, col in ((1, "rain_d1"), (2, "rain_d2")):
            s_ = (radar if name == "radar" else leads[max(k - shift, 0)])[KEY + ["rain_d"]].copy()
            s_["day"] = s_["day"] + pd.Timedelta(days=shift)
            df = df.drop(columns=[col]).merge(s_.rename(columns={"rain_d": col}), on=KEY, how="left")
        df["rain_3d"] = df["rain_d"].fillna(0) + df["rain_d1"].fillna(0) + df["rain_d2"].fillna(0)
        return df

    frames = {"era5_land": b3, "radar": fed("radar", 0), **{f"lead{k}": fed("lead", k) for k in LEADS}}
    ok = np.ones(len(b3), dtype=bool)
    for f in frames.values():
        ok &= f["rain_d"].notna().to_numpy() & f["rain_d1"].notna().to_numpy() & f["rain_d2"].notna().to_numpy()
    y = b3["y"].to_numpy()[ok]
    week = b3["day"].dt.strftime("%G-%V").to_numpy()[ok]
    p = {n: model.predict(f[ok].astype({c: np.float32 for c in ALL_FEATURES}).fillna({c: 0.0 for c in ALL_FEATURES}))
         for n, f in frames.items()}
    q3 = {"rows": int(ok.sum()), "rows_before_mask": len(b3), "spill_days": int(y.sum()), "overflows": int(sites.shape[0]),
          "companies": sites["company"].value_counts().to_dict(), "cells": len(use),
          "by_source": {n: {"brier": float(np.mean((v - y) ** 2)), "auc": float(roc_auc_score(y, v)),
                            "spill_days_at_0.4": float((v[y == 1] >= WARN).mean()),
                            "dry_days_at_0.4": float((v[y == 0] >= WARN).mean())} for n, v in p.items()},
          "radar_minus_lead1": week_boot(y, p["radar"], p["lead1"], week),
          "radar_minus_lead0": week_boot(y, p["radar"], p["lead0"], week)}
    bs = q3["by_source"]
    a = q3["radar_minus_lead1"]["ci95"][1] < 0 and bs["radar"]["auc"] >= bs["lead1"]["auc"] + 0.03
    bverdict = q3["radar_minus_lead0"]["ci95"][1] >= 0
    q3["verdict"] = "not decided (radar failed Q1)" if not radar_ok else ("A" if a else "B" if bverdict else "C")
    q3["verdict_if_radar_trusted"] = "A" if a else "B" if bverdict else "C"
    q3["scale_check"] = {"radar_minus_era5": bs["radar"]["brier"] - bs["era5_land"]["brier"],
                         "lead0_minus_era5": bs["lead0"]["brier"] - bs["era5_land"]["brier"]}
    res["q3"] = q3
    Path(out_path).write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("radar_cells",)} | {"q1_conditions": q1["conditions"], "q1_all": q1["all"],
                     "q2_stated": q2["stated"], "q3_verdict": q3["verdict"]}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:])
