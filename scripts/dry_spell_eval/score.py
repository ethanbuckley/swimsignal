"""docs/DRY-SPELL-TEST-2026-10.md: dry days before rain, and rain over 72 hours, as E. coli model inputs.

    score.py <out.json>

train_ecoli.py's rows, filters and evaluations (its own functions), run three times on the same rows: its seven
inputs; those plus dry3 and dry3_x_lrain48 (question 1); those plus lrain72 (question 2). The new inputs come from
the lead-0 hourly rain at the sample's cell, with ecoli.rain_windows' stamping and coverage rule. Rows missing any new
input leave all three arms (counted). Then the per-site lag description.

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
from scipy.stats import spearmanr

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.ecoli import FEATURES, MIN_COVERAGE, THRESHOLD, features, fit
from dipcast.model.forecast import MAX_MISSING_SHARE
from dipcast.model.verify import scores

Q1 = ["dry3", "dry3_x_lrain48"]
Q2 = ["lrain72"]
ARMS = {"reference": FEATURES, "q1_dry_spell": [*FEATURES, *Q1], "q2_rain72": [*FEATURES, *Q2]}
SIGN = {"q1_dry_spell": "dry3_x_lrain48", "q2_rain72": "lrain72"}
MARGIN = 0.0005
DRY_MM = 1.0
BLOCKS = ((48, 72), (72, 96), (96, 120))   # hours before the sample: (t - 72 h, t - 48 h], ...
MIN_SITE_SAMPLES = 30


def window_total(s: pd.Series, t: pd.Timestamp, near: int, far: int) -> float:
    """Rain over (t - far h, t - near h], NaN unless MIN_COVERAGE of its hours carry a value."""
    idx = pd.date_range(t - pd.Timedelta(hours=far - 1), t - pd.Timedelta(hours=near), freq="h")
    w = s.reindex(idx)
    return float(w.sum()) if w.notna().mean() >= MIN_COVERAGE else np.nan


def dry_run(blocks: list[float]) -> float:
    """Dry blocks counted back from t - 48 h, stopping at the first wet or missing one; NaN if the first is missing."""
    if np.isnan(blocks[0]):
        return np.nan
    n = 0
    for b in blocks:
        if np.isnan(b) or b >= DRY_MM:
            break
        n += 1
    return float(n)


def lead0_inputs(rows: pd.DataFrame) -> pd.DataFrame:
    """dry_run, rain over 72 h, and (for the description) 24 h and 48 h, from lead 0 at each sample's cell."""
    cl, cn = grid_cell(rows["lat"].to_numpy(), rows["lon"].to_numpy())
    cl, cn = np.round(cl, 3), np.round(cn, 3)
    cells = set(zip(cl, cn, strict=True))
    frames = []
    for f in sorted((config.CACHE / "rain").glob("leads_*.parquet")):
        _, lat, lon, _ = f.stem.split("_")
        if (float(lat), float(lon)) in cells:
            frames.append(pd.read_parquet(f))
    leads = pd.concat(frames, ignore_index=True)
    leads = leads[leads.lead == 0]
    leads["time"] = leads["time"].dt.tz_convert("Europe/London")
    out = pd.DataFrame(np.nan, index=rows.index, columns=["dry_run", "rain72", "rain48", "rain24"])
    for (a, b), g in leads.groupby(["cell_lat", "cell_lon"]):
        idx = np.where((cl == a) & (cn == b))[0]
        if len(idx) == 0:
            continue
        s = g.set_index("time")["precip_mm"].astype(float)
        s = s[np.isfinite(s.to_numpy())]
        s = s[~s.index.duplicated(keep="last")].sort_index()
        for i in idx:
            t = pd.Timestamp(rows["sample_time"].iloc[i]).floor("h")
            out.iloc[i] = [dry_run([window_total(s, t, n, f) for n, f in BLOCKS]),
                           window_total(s, t, 0, 72), window_total(s, t, 0, 48), window_total(s, t, 0, 24)]
    return out


def site_lags(rows: pd.DataFrame, inp: pd.DataFrame) -> dict:
    table, picks = [], {"24": 0, "48": 0, "72": 0}
    for bw, g in rows.groupby("bw_id"):
        if len(g) < MIN_SITE_SAMPLES:
            continue
        rho = {h: float(spearmanr(inp.loc[g.index, f"rain{h}"], g["log_ecoli"]).statistic) for h in ("24", "48", "72")}
        best = max(rho, key=lambda h: (-np.inf if np.isnan(rho[h]) else rho[h]))
        picks[best] += 1
        table.append({"bw_id": bw, "name": g["name"].iloc[0], "kind": g["kind"].iloc[0], "n": len(g),
                      **{f"rho_{h}h": round(v, 3) for h, v in rho.items()}, "best": f"{best} h"})
    return {"sites": table, "picks": picks, "min_samples": MIN_SITE_SAMPLES}


def main(out_path: str) -> None:
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
    # ---- the new inputs; rows without them leave all three arms
    inp = lead0_inputs(rows)
    ok_new = ok & inp["dry_run"].notna().to_numpy() & inp["rain72"].notna().to_numpy()
    rows, inp = rows[ok_new].reset_index(drop=True), inp[ok_new].reset_index(drop=True)
    fc0 = (fc[0][0][ok_new], fc[0][1][ok_new])
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years = rows["sample_time"].dt.year.to_numpy()
    lake = rows["lake"].to_numpy()
    site = rows["bw_id"].to_numpy()
    week = (rows["bw_id"] + "|" + rows["sample_time"].dt.strftime("%G-%V")).to_numpy()
    rivers = lake == 0.0

    def add(X):
        X["dry3"] = inp["dry_run"].to_numpy() / 3
        X["dry3_x_lrain48"] = X["dry3"] * X["lrain48"]
        X["lrain72"] = np.log1p(np.clip(inp["rain72"].to_numpy(), 0, None))
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
    dr = inp["dry_run"].to_numpy()
    res = {"rows_train_ecoli": n_train_ecoli, "rows_scored": len(rows), "rows_dropped_missing_input": n_train_ecoli - len(rows),
           "over_900": int(y.sum()), "sites": int(rows.bw_id.nunique()),
           "inputs": {"dry_run_share": {str(int(v)): float((dr == v).mean()) for v in (0, 1, 2, 3)},
                      "dry_run_share_rivers": {str(int(v)): float((dr[rivers] == v).mean()) for v in (0, 1, 2, 3)},
                      "corr_lrain72_lrain48": float(np.corrcoef(X["lrain72"], X["lrain48"])[0, 1]),
                      "corr_dry3_lrain48": float(np.corrcoef(X["dry3"], X["lrain48"])[0, 1])}}
    for name, pp, m in (("loyo", p_loyo, None), ("loso", p_loso, None), ("forward", p_fwd, tt)):
        res[name] = {a: {"all": brier(pp[a], m), "rivers": brier(pp[a], (m if m is not None else True) & rivers),
                         "lakes": brier(pp[a], (m if m is not None else True) & ~rivers),
                         "scores": {k: v for k, v in scores(y[~np.isnan(pp[a])], pp[a][~np.isnan(pp[a])]).items()
                                    if k in ("brier", "auc", "log_loss", "n")}} for a in ARMS}
    final = {a: fit(X, y, c) for a, c in ARMS.items()}
    res["coef_per_sd"] = {a: final[a].coef for a in ARMS}
    L, S, F = res["loyo"], res["loso"], res["forward"]
    res["conditions"] = {}
    for a in ("q1_dry_spell", "q2_rain72"):
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
    res["site_lags"] = site_lags(rows, inp)
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
