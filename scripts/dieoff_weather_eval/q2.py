"""docs/DIEOFF-WEATHER-TEST-2026-10.md, question 2: sunlight and temperature as E. coli model inputs.

    q2.py <weather cache> <out.json>

train_ecoli.py's rows, filters and evaluations (its own functions), run twice on the same rows: its seven inputs,
and those plus
    sun24   mean shortwave_radiation over the 24 h to the sample time
    temp48  mean temperature_2m over the 48 h to the sample time
from the lead-0 weather at the sample's cell, with ecoli.rain_windows' hours and coverage rule (a mean is the
window's sum over its finite hours). Rows: train_ecoli's, less any without both inputs (counted).

Face check: with no rows dropped, this script's reference LOYO, LOSO and forward Brier scores equal those
train_ecoli.py wrote to ecoli_model_eval.json in the same root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import train_ecoli as te
import weather as wx

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.ecoli import FEATURES, THRESHOLD, features, fit, rain_windows
from dipcast.model.forecast import MAX_MISSING_SHARE
from dipcast.model.verify import scores

NEW = ["sun24", "temp48"]
WITH = [*FEATURES, *NEW]
MARGIN = 0.0005


def weather_at_samples(rows: pd.DataFrame, cache: Path) -> tuple[np.ndarray, np.ndarray]:
    cl, cn = grid_cell(rows["lat"].to_numpy(), rows["lon"].to_numpy())
    cl, cn = np.round(cl, 3), np.round(cn, 3)
    sun, temp = np.full(len(rows), np.nan), np.full(len(rows), np.nan)
    for c in sorted(set(zip(cl, cn, strict=True))):
        idx = np.where((cl == c[0]) & (cn == c[1]))[0]
        w = wx.load(cache, (float(c[0]), float(c[1])))
        if w.empty:
            continue
        w.index = w.index.tz_convert("Europe/London")
        ends = pd.DatetimeIndex(rows["sample_time"].iloc[idx])
        _, s24, _, c24 = rain_windows(w["shortwave_radiation"], ends, return_coverage=True)
        t48, _, c48, _ = rain_windows(w["temperature_2m"], ends, return_coverage=True)
        sun[idx] = s24 / (24 * c24)
        temp[idx] = t48 / (48 * c48)
    return sun, temp


def main(cache_dir: str, out_path: str) -> None:
    cache = Path(cache_dir)
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
    # ---- the two inputs; rows without them leave both arms
    sun, temp = weather_at_samples(rows, cache)
    ok_w = ok & np.isfinite(sun) & np.isfinite(temp)
    rows = rows[ok_w].reset_index(drop=True)
    fc0 = (fc[0][0][ok_w], fc[0][1][ok_w])
    sun, temp = sun[ok_w], temp[ok_w]
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years = rows["sample_time"].dt.year.to_numpy()
    lake = rows["lake"].to_numpy()
    site = rows["bw_id"].to_numpy()
    week = (rows["bw_id"] + "|" + rows["sample_time"].dt.strftime("%G-%V")).to_numpy()
    rivers = lake == 0.0
    X = features(fc0[0], fc0[1], rows["risk_lead0"], rows.lake, rows.sample_time)
    X["sun24"], X["temp48"] = sun, temp
    Xh = features(fc0[0], fc0[1], rows["risk_hold_lead0"], rows.lake, rows.sample_time)
    Xh["sun24"], Xh["temp48"] = sun, temp

    def brier(p, m=None):
        m = np.ones(len(y), dtype=bool) if m is None else m
        m = m & ~np.isnan(p)
        return float(np.mean((p[m] - y[m]) ** 2))

    arms = {"reference": FEATURES, "with_weather": WITH}
    p_loyo = {a: te.leave_one_out(X, y, years, lake, c) for a, c in arms.items()}
    p_loso = {a: te.leave_one_out(X, y, site, lake, c) for a, c in arms.items()}
    tr, tt = years <= te.FORWARD_TRAIN_UNTIL, years > te.FORWARD_TRAIN_UNTIL
    p_fwd = {}
    for a, c in arms.items():
        p = np.full(len(y), np.nan); p[tt] = te._fit_predict(Xh, y, tr, tt, c, lake); p_fwd[a] = p
    res = {"rows_train_ecoli": n_train_ecoli, "rows_scored": len(rows), "rows_dropped_no_weather": n_train_ecoli - len(rows),
           "over_900": int(y.sum()), "sites": int(rows.bw_id.nunique()),
           "inputs": {"sun24_wm2": {"mean": float(np.mean(sun)), "sd": float(np.std(sun)), "min": float(np.min(sun)), "max": float(np.max(sun))},
                      "temp48_c": {"mean": float(np.mean(temp)), "sd": float(np.std(temp)), "min": float(np.min(temp)), "max": float(np.max(temp))},
                      "corr_sun24_lrain48": float(np.corrcoef(sun, X["lrain48"])[0, 1]),
                      "corr_temp48_doy_cos": float(np.corrcoef(temp, X["doy_cos"])[0, 1])}}
    for name, pp, m in (("loyo", p_loyo, None), ("loso", p_loso, None), ("forward", p_fwd, tt)):
        res[name] = {a: {"all": brier(pp[a], m), "rivers": brier(pp[a], (m if m is not None else True) & rivers),
                         "lakes": brier(pp[a], (m if m is not None else True) & ~rivers),
                         "scores": {k: v for k, v in scores(y[~np.isnan(pp[a])], pp[a][~np.isnan(pp[a])]).items()
                                    if k in ("brier", "auc", "log_loss", "n")}} for a in arms}
    res["bootstrap_loyo_site_week"] = te.cluster_bootstrap(y, p_loyo["reference"], p_loyo["with_weather"], week)
    res["bootstrap_loyo_rivers_site_week"] = te.cluster_bootstrap(y, p_loyo["reference"], p_loyo["with_weather"], week, mask=rivers)
    final = {a: fit(X, y, c) for a, c in arms.items()}
    res["coef_per_sd"] = {a: final[a].coef for a in arms}
    L, S, F, B = res["loyo"], res["loso"], res["forward"], res["bootstrap_loyo_site_week"]
    gain = L["reference"]["all"] - L["with_weather"]["all"]
    res["conditions"] = {
        "1_loyo_gain": bool(gain >= MARGIN and B["brier_gain_ci"][0] > 0),
        "2_loso_not_worse": bool(S["with_weather"]["all"] - S["reference"]["all"] <= MARGIN),
        "3_forward_not_worse": bool(F["with_weather"]["all"] - F["reference"]["all"] <= MARGIN),
        "4_rivers_lakes_not_worse": bool(L["with_weather"]["rivers"] - L["reference"]["rivers"] <= MARGIN
                                         and L["with_weather"]["lakes"] - L["reference"]["lakes"] <= MARGIN),
        "5_sun_negative": bool(final["with_weather"].coef["sun24"] < 0),
        "loyo_gain": gain}
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
