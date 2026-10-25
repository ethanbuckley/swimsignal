"""docs/SOIL-MOISTURE-TEST-2026-10.md, question 1: soil moisture in the E. coli model.

    q1.py <soil dir> <out.json>

train_ecoli.py's rows, filters and evaluations (its own functions), run three times on the same rows: its seven
inputs; those plus sm (arm main); those plus sm and sm_x_lrain48 (arm interaction). sm is Previous Runs lead-0
soil_moisture_9_to_27cm (m3/m3) at the sample's rain cell, at the hour floor(t) - 48 h, t the sample time: the
ground's state when the 48-hour rain window began (fetch.py q1). Rows missing sm leave all three arms (counted).
The row-building block is scripts/dry_spell_eval/score.py's, unchanged.

Face check: with no rows dropped, the reference LOYO, LOSO and forward Brier scores equal those train_ecoli.py wrote to
ecoli_model_eval.json in the same root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import train_ecoli as te

from dipcast import config
from dipcast.ingest.rainfall import cell_key, grid_cell
from dipcast.model.ecoli import FEATURES, THRESHOLD, features, fit
from dipcast.model.forecast import MAX_MISSING_SHARE
from dipcast.model.verify import scores

ARMS = {"reference": FEATURES, "main": [*FEATURES, "sm"], "interaction": [*FEATURES, "sm", "sm_x_lrain48"]}
SIGN = {"main": "sm", "interaction": "sm_x_lrain48"}
MARGIN = 0.0005
LAG_H = 48


def soil_at(rows: pd.DataFrame, soil: Path) -> np.ndarray:
    """sm at floor(t) - 48 h (UTC) from each sample's cell file; NaN where the file or the hour has no value."""
    cl, cn = grid_cell(rows["lat"].to_numpy(), rows["lon"].to_numpy())
    when = rows["sample_time"].dt.floor("h").dt.tz_convert("UTC") - pd.Timedelta(hours=LAG_H)
    out = np.full(len(rows), np.nan)
    series: dict = {}
    for i, (a, b, t) in enumerate(zip(cl, cn, when, strict=True)):
        k = (a, b, t.year)
        if k not in series:
            f = soil / f"q1_{cell_key(a, b)}_{t.year}.parquet"
            s = pd.read_parquet(f).set_index("time")["sm"] if f.exists() else pd.Series(dtype=float)
            series[k] = s[~s.index.duplicated(keep="last")]
        v = series[k].get(t, np.nan)
        out[i] = float(v) if v is not None else np.nan
    return out


def main(soil_dir: str, out_path: str) -> None:
    # ---- train_ecoli.main's rows and filters, unchanged
    rows = pd.read_parquet(config.PROCESSED / "ecoli_validation_rows.parquet")
    rows = rows[rows.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "ecoli"]).reset_index(drop=True)
    rows["lake"] = (rows["kind"] == "lake").astype(float)
    rows["day"] = rows["sample_time"].dt.floor("D")
    sites = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id").set_index("bw_id")
    rows["lat"], rows["lon"] = sites.loc[rows.bw_id, "lat"].to_numpy(), sites.loc[rows.bw_id, "lon"].to_numpy()
    ex = pd.read_parquet(te.EXPOSURE_FILE)
    ex["day"] = pd.to_datetime(ex["day"])
    if ex["day"].dt.tz is None and rows["day"].dt.tz is not None:
        ex["day"] = ex["day"].dt.tz_localize(rows["day"].dt.tz)
    if "missing_share" not in ex:
        ex["missing_share"] = np.where(ex["risk_prod"].isna(), 1.0, 0.0)
    for k in te.LEADS:
        e = ex[ex.lead == k][["bw_id", "day", "risk_prod", "risk_holdout", "missing_share"]].rename(
            columns={"risk_prod": f"risk_lead{k}", "risk_holdout": f"risk_hold_lead{k}", "missing_share": f"miss_lead{k}"})
        rows = rows.merge(e, on=["bw_id", "day"], how="left")
    fc = te.forecast_rain_at_samples(rows)
    ok_rain = np.all([~np.isnan(fc[k][0]) for k in te.LEADS], axis=0)
    shown = {k: (rows[f"miss_lead{k}"].fillna(1.0).to_numpy() <= MAX_MISSING_SHARE) & rows[f"risk_lead{k}"].notna().to_numpy()
             for k in te.LEADS}
    ok = ok_rain & np.all([shown[k] for k in te.LEADS], axis=0)
    n_train_ecoli = int(ok.sum())
    # ---- sm; rows without it leave all three arms
    sm = soil_at(rows, Path(soil_dir))
    ok_new = ok & np.isfinite(sm)
    rows, sm = rows[ok_new].reset_index(drop=True), sm[ok_new]
    fc0 = (fc[0][0][ok_new], fc[0][1][ok_new])
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years = rows["sample_time"].dt.year.to_numpy()
    lake = rows["lake"].to_numpy()
    site = rows["bw_id"].to_numpy()
    week = (rows["bw_id"] + "|" + rows["sample_time"].dt.strftime("%G-%V")).to_numpy()
    rivers = lake == 0.0

    def add(X):
        X["sm"] = sm
        X["sm_x_lrain48"] = sm * X["lrain48"]
        return X

    X = add(features(fc0[0], fc0[1], rows["risk_lead0"], rows.lake, rows.sample_time))
    Xh = add(features(fc0[0], fc0[1], rows["risk_hold_lead0"], rows.lake, rows.sample_time))

    def brier(p, m=None):
        m = np.ones(len(y), dtype=bool) if m is None else m
        m = m & ~np.isnan(p)
        return float(np.mean((p[m] - y[m]) ** 2))

    p_loyo = {a: te.leave_one_out(X, y, years, lake, c) for a, c in ARMS.items()}
    p_loso = {a: te.leave_one_out(X, y, site, lake, c) for a, c in ARMS.items()}
    tr, tt = years <= te.FORWARD_TRAIN_UNTIL, years > te.FORWARD_TRAIN_UNTIL
    p_fwd = {}
    for a, c in ARMS.items():
        p = np.full(len(y), np.nan); p[tt] = te._fit_predict(Xh, y, tr, tt, c, lake); p_fwd[a] = p
    site_mean = pd.Series(sm).groupby(site).mean()
    res = {"rows_train_ecoli": n_train_ecoli, "rows_scored": len(rows), "rows_dropped_missing_input": n_train_ecoli - len(rows),
           "over_900": int(y.sum()), "sites": int(rows.bw_id.nunique()),
           "inputs": {"sm_mean": float(sm.mean()), "sm_sd": float(sm.std()), "sm_min": float(sm.min()), "sm_max": float(sm.max()),
                      "sm_mean_rivers": float(sm[rivers].mean()), "sm_mean_lakes": float(sm[~rivers].mean()),
                      "corr_sm_lrain48": float(np.corrcoef(X["sm"], X["lrain48"])[0, 1]),
                      "corr_sm_lrain24": float(np.corrcoef(X["sm"], X["lrain24"])[0, 1]),
                      "site_means": {"min": float(site_mean.min()), "max": float(site_mean.max()), "sd": float(site_mean.std())},
                      "share_of_variance_between_sites": float(pd.Series(sm).groupby(site).transform("mean").var() / sm.var())}}
    for name, pp, m in (("loyo", p_loyo, None), ("loso", p_loso, None), ("forward", p_fwd, tt)):
        res[name] = {a: {"all": brier(pp[a], m), "rivers": brier(pp[a], (m if m is not None else True) & rivers),
                         "lakes": brier(pp[a], (m if m is not None else True) & ~rivers),
                         "scores": {k: v for k, v in scores(y[~np.isnan(pp[a])], pp[a][~np.isnan(pp[a])]).items()
                                    if k in ("brier", "auc", "log_loss", "n")}} for a in ARMS}
    final = {a: fit(X, y, c) for a, c in ARMS.items()}
    res["coef_per_sd"] = {a: final[a].coef for a in ARMS}
    L, S, F = res["loyo"], res["loso"], res["forward"]
    res["conditions"] = {}
    for a in ("main", "interaction"):
        B = te.cluster_bootstrap(y, p_loyo["reference"], p_loyo[a], week)
        res[f"bootstrap_loyo_site_week_{a}"] = B
        res[f"bootstrap_loyo_rivers_site_week_{a}"] = te.cluster_bootstrap(y, p_loyo["reference"], p_loyo[a], week, mask=rivers)
        gain = L["reference"]["all"] - L[a]["all"]
        res["conditions"][a] = {
            "1_loyo_gain": bool(gain >= MARGIN and B["brier_gain_ci"][0] > 0),
            "2_loso_not_worse": bool(S[a]["all"] - S["reference"]["all"] <= MARGIN),
            "3_forward_not_worse": bool(F[a]["all"] - F["reference"]["all"] <= MARGIN),
            "4_rivers_lakes_not_worse": bool(L[a]["rivers"] - L["reference"]["rivers"] <= MARGIN
                                             and L[a]["lakes"] - L["reference"]["lakes"] <= MARGIN),
            "5_sign_positive": bool(final[a].coef[SIGN[a]] > 0),
            "loyo_gain": gain}
        res["conditions"][a]["passes"] = all(v for k, v in res["conditions"][a].items() if k[0].isdigit())
    c = res["conditions"]
    taken = None
    if c["main"]["passes"] and c["interaction"]["passes"]:
        taken = "interaction" if L["main"]["all"] - L["interaction"]["all"] >= MARGIN else "main"
    elif c["main"]["passes"] or c["interaction"]["passes"]:
        taken = "main" if c["main"]["passes"] else "interaction"
    res["question_1"] = {"passes": taken is not None, "arm_taken_forward": taken}
    # Face check against train_ecoli.py's own output in this root.
    ev = config.PROCESSED / "ecoli_model_eval.json"
    if ev.exists():
        e = json.loads(ev.read_text())
        full = te.FULL
        pub = {"loyo": next(r["brier"] for r in e["loyo"] if r["model"] == full),
               "loso": next(r["brier"] for r in e["loso"] if r["model"] == full),
               "forward": next(r["brier"] for r in e["forward"]["table"] if r["model"] == full) if e.get("forward") else None,
               "n": e["n_samples"]}
        res["face_check"] = {"train_ecoli": pub, "here_reference": {"loyo": round(L["reference"]["all"], 4),
                             "loso": round(S["reference"]["all"], 4), "forward": round(F["reference"]["all"], 4),
                             "n": n_train_ecoli}}
    Path(out_path).write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:])
