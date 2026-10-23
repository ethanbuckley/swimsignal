"""docs/DIEOFF-WEATHER-TEST-2026-10.md, question 1: a die-off rate that moves with sunlight and temperature.

    q1.py prep  <weather cache> <out.parquet>          hindcast risk on every sample day under every setting
    q1.py check <rows.parquet> <validation rows>       the face check against validate_ecoli.py, same root
    q1.py score <rows.parquet> <out.json>              leave-one-year-out selection, held-out scores, bootstrap

prep is validate_ecoli.py's hindcast, unchanged up to the transport step (as scripts/transport_fit_eval/fit.py):
the same samples, pins, overflows, spill model, reanalysis rain, lead-0 calibration and missing-rain rule, at main's
transport settings. Then, per setting (s, theta), each overflow's weight on each arrival day is its weight today
with the fixed decay replaced by transport.weather_decay over the journey that ends at 12:00 London time on that
day, with weather.rate at the spot's cell.

Columns: `const`, today's fixed weights (the face check's reference, as validate_ecoli computes risk_model), and one
per setting. A day whose weather window is incomplete for any overflow with weight has no figure under any setting
(the rate has the same missing hours for all). The missing-rain rule uses today's fixed weights for every setting,
so it removes the same days from each. Rows scored: those with a figure under all 12 settings.
"""

from __future__ import annotations

import itertools
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import weather as wx
from eval_pins import bathing_water_pin
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model import transport
from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features
from dipcast.model.forecast import MAX_MISSING_SHARE, calibrate_at_lead
from dipcast.model.spill_model import SpillModel
from dipcast.network.rivers import RiverNetwork
from dipcast.overflows import load_overflows

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dieoff_q1")
TZ = "Europe/London"
ARRIVAL_HOUR = 12                       # ecoli.SAMPLE_HOUR

SUN_SHARES = (0.0, 0.25, 0.5, 0.75)     # s
THETAS = (1.00, 1.04, 1.07)             # theta
REFERENCE = (0.0, 1.00)                 # today's model: the fixed rate
GRID = [REFERENCE] + [g for g in itertools.product(SUN_SHARES, THETAS) if g != REFERENCE]   # reference first: wins ties
BOOT = 2000
SEED = 20261023


def key(g: tuple[float, float]) -> str:
    return f"s{g[0]:g}_th{g[1]:g}"


def _shift(p: np.ndarray, travel_h: np.ndarray) -> np.ndarray:
    """transport.shift_by_travel with numpy slices (scripts/transport_fit_eval/fit.py)."""
    n, d = p.shape
    shift = np.asarray(travel_h, dtype=float) / 24.0
    k = np.floor(shift).astype(int)
    a = shift - k
    eff = np.zeros((n, d), dtype=float)
    for i in range(n):
        if k[i] < d:
            eff[i, k[i]:] += (1 - a[i]) * p[i, :d - k[i]]
        if k[i] + 1 < d:
            eff[i, k[i] + 1:] += a[i] * p[i, :d - k[i] - 1]
    return eff


def combine(shifted: np.ndarray, w: np.ndarray) -> np.ndarray:
    """1 - prod(1 - shifted p * w); w is (n,) or (n, days)."""
    if shifted.shape[0] == 0:
        return np.zeros(shifted.shape[1])
    return 1.0 - np.prod(1.0 - shifted * (w[:, None] if w.ndim == 1 else w), axis=0)


def missing(ok: np.ndarray, w: np.ndarray, tr: np.ndarray) -> np.ndarray:
    if len(w) == 0 or w.sum() <= 0:
        return np.zeros(ok.shape[1])
    return np.clip((_shift((~ok).astype(float), tr) * w[:, None]).sum(axis=0) / w.sum(), 0, 1)


def prep(cache_dir: str, out_path: str) -> None:
    cache = Path(cache_dir)
    samples = pd.read_parquet(config.RAW / "bwq_samples.parquet").dropna(subset=["ecoli", "sample_time"]).copy()
    samples["day"] = samples["sample_time"].dt.floor("D")
    samples["log_ecoli"] = np.log10(samples["ecoli"].clip(lower=1))
    net = RiverNetwork.load(); ov = load_overflows(net)
    model = SpillModel.load()
    files = sorted((config.CACHE / "rain").glob("archive_*.parquet"))
    rain = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    rain["time"] = rain["time"].dt.tz_convert(TZ)
    daily = daily_rain_features(rain)
    cells = set(zip(rain["cell_lat"].round(3), rain["cell_lon"].round(3), strict=True))
    means = wx.season_means(cache, wx.cells())
    log.info("%d samples, %d sites, %d rain files, %d settings, means %s", len(samples), samples.bw_id.nunique(),
             len(files), len(GRID), means)

    out, checks = [], []
    for bw_id, g in samples.groupby("bw_id"):
        s = g.iloc[0]
        cl, cn = (round(float(v), 3) for v in grid_cell(float(s.lat), float(s.lon)))
        if (cl, cn) not in cells:
            log.warning("%s: no rainfall for site cell", s["name"]); continue   # validate_ecoli skips these too
        pin = bathing_water_pin(net, bw_id, float(s.lon), float(s.lat))
        up = transport.upstream_overflows(net, pin, ov, velocity_ms=transport.river_velocity(None), keep_parts=True)
        rows = g[["bw_id", "name", "kind", "undertaker", "sample_time", "day", "ecoli", "log_ecoli"]].copy()
        rows["upstream"] = len(up)
        if len(up):
            ids = up["site_id"].to_numpy()
            assert len(set(ids)) == len(ids), bw_id
            sample_days = pd.DatetimeIndex(sorted(g["day"].unique()))
            days = pd.date_range(sample_days.min() - pd.Timedelta(days=transport.history_days(up["travel_h"])),
                                 sample_days.max(), freq="D")
            sd = build_site_days(up[["site_id", "lat", "lon", "company", "lta_spills", "spill_hours",
                                     "edm_operational_pct"]], daily, days)
            sd["ok"] = sd["rain_d"].notna()
            X = sd.astype({f: np.float32 for f in ALL_FEATURES}).fillna({f: 0.0 for f in ALL_FEATURES})
            sd["p"] = np.where(sd["ok"], model.predict(X), np.nan)
            mat = sd.pivot(index="site_id", columns="day", values="p").reindex(index=ids, columns=days)
            okm = sd.pivot(index="site_id", columns="day", values="ok").reindex(index=ids, columns=days)
            pm = calibrate_at_lead(mat.to_numpy(dtype=float), lead=0)
            ok = okm.fillna(False).to_numpy(dtype=bool)
            w = up["weight"].to_numpy(dtype=float); tr = up["travel_h"].to_numpy(dtype=float)
            decay = up["decay"].to_numpy(dtype=float)
            rest = w / decay                                   # dilution and the low-confidence factor
            miss = missing(ok, w, tr)
            keep = miss <= MAX_MISSING_SHARE
            shifted = np.clip(_shift(np.nan_to_num(pm, nan=0.0), tr), 0, 1)
            const = combine(shifted, w)
            # 12:00 on the London wall clock, also on the two days the clocks change
            arrivals = ((days.tz_convert(TZ).tz_localize(None) if days.tz is not None else days)
                        + pd.Timedelta(hours=ARRIVAL_HOUR)).tz_localize(TZ)
            wcell = wx.load(cache, (cl, cn))
            chk = {"bw_id": bw_id, "combine": float(np.nanmax(np.abs(const - transport.combine_daily(pm, w, tr)))),
                   "missing": float(np.nanmax(np.abs(miss - transport.missing_share(ok, w, tr))))}
            r = pd.Series(np.where(keep, const, np.nan), index=days)
            rows["const"] = rows["day"].map(r).to_numpy(dtype=float)
            on_sample = np.isin(days, sample_days)
            for gg in GRID:
                if wcell.empty:
                    rows[key(gg)] = np.nan; continue
                surv = transport.weather_decay(up["moving_h"].to_numpy(dtype=float), up["lake_pass"].to_numpy(dtype=float),
                                               tr, wx.rate(wcell, gg[0], gg[1], means), arrivals)
                W = rest[:, None] * surv
                gap = np.isnan(W[w > 0]).any(axis=0) if (w > 0).any() else np.zeros(len(days), dtype=bool)
                risk = combine(shifted, np.nan_to_num(W, nan=0.0))
                if gg == REFERENCE:   # the weather path at the fixed rate against today's weights
                    good = ~np.isnan(surv)
                    chk["survival_vs_decay"] = float(np.nanmax(np.abs(surv - decay[:, None]))) if good.any() else None
                    chk["reference_vs_const"] = float(np.nanmax(np.abs(np.where(gap, np.nan, risk) - const)[on_sample])) \
                        if (~gap & on_sample).any() else None
                    chk["combine_2d"] = float(np.nanmax(np.abs(risk - transport.combine_daily(pm, np.nan_to_num(W, nan=0.0), tr))))
                    chk["sample_days_without_weather"] = int((gap & on_sample).sum())
                rr = pd.Series(np.where(keep & ~gap, risk, np.nan), index=days)
                rows[key(gg)] = rows["day"].map(rr).to_numpy(dtype=float)
            checks.append(chk)
        out.append(rows)
    df = pd.concat(out, ignore_index=True)
    df.to_parquet(out_path, index=False)
    ch = pd.DataFrame(checks)
    ch.to_csv(Path(out_path).with_suffix(".checks.csv"), index=False)
    print(json.dumps({"rows": len(df), "sites": int(df.bw_id.nunique()), "sites_with_upstream": int(df[df.upstream > 0].bw_id.nunique()),
                      "means": means, "max_diff_combine": float(ch["combine"].max()), "max_diff_missing": float(ch["missing"].max()),
                      "max_diff_combine_2d": float(ch["combine_2d"].max()),
                      "max_survival_vs_decay": float(ch["survival_vs_decay"].max()),
                      "max_reference_vs_const": float(ch["reference_vs_const"].max()),
                      "sample_days_without_weather": int(ch["sample_days_without_weather"].sum())}))


# --------------------------------------------------------------------------- scoring (as transport_fit_eval/fit.py)

def _within(d: pd.DataFrame, col: str, by: list[str]) -> pd.Series:
    return d[col] - d.groupby(by)[col].transform("mean")


def rho_within(d: pd.DataFrame, col: str, by: list[str]) -> float:
    return float(spearmanr(_within(d, col, by), _within(d, "log_ecoli", by)).statistic)


def auc900(d: pd.DataFrame, col: str) -> float:
    y = (d["ecoli"] > 900).astype(int)
    return float(roc_auc_score(y, d[col])) if 0 < y.mean() < 1 else float("nan")


def select(train: pd.DataFrame) -> tuple[tuple, float]:
    best, best_s = None, -np.inf
    for gg in GRID:
        sc = rho_within(train, key(gg), ["bw_id"])
        if sc > best_s:
            best, best_s = gg, sc
    return best, best_s


def loyo(d: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    held, folds = [], []
    for y in sorted(d["year"].unique()):
        g, s = select(d[d["year"] != y])
        h = d[d["year"] == y].copy()
        h["cand"] = h[key(g)]; h["cur"] = h[key(REFERENCE)]
        held.append(h)
        folds.append({"year": int(y), "chosen": key(g), "train_rho": round(s, 4), "n_held": len(h),
                      "held_rho_chosen": round(rho_within(h, "cand", ["bw_id"]), 4),
                      "held_rho_reference": round(rho_within(h, "cur", ["bw_id"]), 4)})
    return pd.concat(held), folds


def paired(h: pd.DataFrame, rng: np.random.Generator) -> dict:
    by = ["bw_id", "year"]

    def scores(x: pd.DataFrame) -> tuple[float, float, float, float]:
        return rho_within(x, "cand", by), rho_within(x, "cur", by), auc900(x, "cand"), auc900(x, "cur")

    rc, ru, ac, au = scores(h)
    weeks = h["week"].to_numpy()
    uw = np.unique(weeks)
    pos = {w: np.flatnonzero(weeks == w) for w in uw}
    dr, da = [], []
    for _ in range(BOOT):
        idx = np.concatenate([pos[w] for w in rng.choice(uw, size=len(uw), replace=True)])
        brc, bru, bac, bau = scores(h.iloc[idx])
        dr.append(brc - bru); da.append(bac - bau)
    q = lambda x: [round(float(v), 4) for v in np.nanpercentile(x, [2.5, 97.5])]
    return {"n": len(h), "sites": int(h.bw_id.nunique()), "weeks": len(uw), "over_900": int((h.ecoli > 900).sum()),
            "rho_chosen": round(rc, 4), "rho_reference": round(ru, 4), "rho_change": round(rc - ru, 4), "rho_ci": q(dr),
            "auc_chosen": round(ac, 4), "auc_reference": round(au, 4), "auc_change": round(ac - au, 4), "auc_ci": q(da)}


def score(rows_path: str, out_path: str) -> None:
    df = pd.read_parquet(rows_path)
    cols = [key(gg) for gg in GRID]
    up = df[df.upstream > 0]
    d = up.dropna(subset=cols + ["log_ecoli"]).copy()
    t = d["sample_time"].dt.tz_convert(TZ) if d["sample_time"].dt.tz is not None else d["sample_time"]
    d["year"] = t.dt.year
    iso = t.dt.isocalendar()
    d["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    res = {"rows_with_upstream": len(up), "rows_scored": len(d),
           "rows_without_const_figure": int(up["const"].isna().sum()),
           "rows_dropped_no_weather": int((up["const"].notna() & up[cols].isna().any(axis=1)).sum())}
    rng = np.random.default_rng(SEED)
    held = {}
    for kind in ("river", "lake"):
        dk = d[d.kind == kind]
        h, folds = loyo(dk)
        held[kind] = h
        full, full_s = select(dk)
        res[kind] = {"n": len(dk), "sites": int(dk.bw_id.nunique()), "by_year": dk.groupby("year").size().to_dict(),
                     "folds": folds, "full_data_choice": key(full), "full_data_rho": round(full_s, 4),
                     "held_out": paired(h, rng),
                     "in_sample": {key(gg): {"rho": round(rho_within(dk, key(gg), ["bw_id"]), 4),
                                             "auc900": round(auc900(dk, key(gg)), 4)} for gg in GRID}}
    hr = held["river"]
    pick = {f["year"]: f["chosen"] for f in res["river"]["folds"]}
    dl = d[d.kind == "lake"].copy()
    dl["cand"] = [r[pick[y]] if y in pick else np.nan for y, (_, r) in zip(dl["year"], dl.iterrows(), strict=True)]
    dl["cur"] = dl[key(REFERENCE)]
    missing_years = sorted(set(dl["year"]) - set(pick))
    dl = dl.dropna(subset=["cand"])
    res["lake_with_river_choice"] = {"years_without_river_fold": missing_years, **paired(dl, rng)}
    res["all_with_river_choice"] = paired(pd.concat([hr, dl]), rng)
    hv, lk = res["river"]["held_out"], res["lake_with_river_choice"]
    res["conditions"] = {
        "1_river_rho": bool(hv["rho_change"] > 0 and hv["rho_ci"][0] > 0),
        "2_river_auc": bool(hv["auc_change"] >= -0.005 and hv["auc_ci"][1] > 0),
        "3_lake_rho": bool(lk["rho_change"] >= -0.02 and lk["rho_ci"][1] > 0),
        "would_deploy": res["river"]["full_data_choice"], "reference": key(REFERENCE)}
    with open(out_path, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    brief = {k: v for k, v in res.items() if k not in ("river", "lake")}
    for k in ("river", "lake"):
        brief[k] = {kk: vv for kk, vv in res[k].items() if kk != "in_sample"}
    print(json.dumps(brief, indent=1, default=str))


def check(rows_path: str, validation_rows: str) -> None:
    """`const` against validate_ecoli.py's risk_model, row by row (same run root)."""
    a = pd.read_parquet(rows_path)
    b = pd.read_parquet(validation_rows)[["bw_id", "sample_time", "risk_model", "upstream"]]
    m = a.merge(b, on=["bw_id", "sample_time"], how="outer", suffixes=("", "_v"), indicator=True)
    both = m[m["_merge"] == "both"]
    up = both[both.upstream > 0]
    diff = (up["const"] - up["risk_model"]).abs()
    print(json.dumps({"rows_here": len(a), "rows_validate": len(b), "unmatched": int((m["_merge"] != "both").sum()),
                      "upstream_differs": int((both["upstream"] != both["upstream_v"]).sum()),
                      "max_abs_diff": float(diff.max()),
                      "nan_mismatch": int((up["const"].isna() != up["risk_model"].isna()).sum())}))


if __name__ == "__main__":
    {"prep": prep, "score": score, "check": check}[sys.argv[1]](*sys.argv[2:])
