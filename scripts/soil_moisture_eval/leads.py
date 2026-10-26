"""docs/SOIL-MOISTURE-ECOLI-LEADS-TEST-2026-11.md: soil moisture at issue time, held for every lead.

    leads.py <soil dir> <out.json>

train_ecoli.py's rows (diagnostics.rows_q1). sm_k is the cached ECMWF IFS soil_moisture_9_to_27cm (fetch.py q1) at
00:00 UTC of the sample's UTC day minus k days. Each LOYO fold is fitted on lead 0 (today's seven inputs, and those
plus sm_0) and scored with lead-k rain, lead-k replayed exposure and sm_k held inside the fold's sm_0 range, as
train_ecoli.py's by-lead table scores today's model. A row with no sm_k takes the reference prediction of its fold.

Face check: the reference's Brier at each lead equals train_ecoli.py's by-lead "replayed exposure" row in the same
root, all and rivers, to 4 decimals. The script stops if it does not.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import train_ecoli as te
from diagnostics import MIN_SITE_SAMPLES, rows_q1
from q1 import soil_at
from scipy.stats import spearmanr

from dipcast import config
from dipcast.ingest.rainfall import cell_key, grid_cell
from dipcast.model.ecoli import FEATURES, THRESHOLD, features, fit
from dipcast.model.verify import scores

CAND = [*FEATURES, "sm"]
MARGIN = 0.0005


def soil_at_issue(rows: pd.DataFrame, soil: Path, k: int) -> np.ndarray:
    """sm at 00:00 UTC of the sample's UTC day minus k days, from each sample's cell file; NaN if none."""
    cl, cn = grid_cell(rows["lat"].to_numpy(), rows["lon"].to_numpy())
    when = rows["sample_time"].dt.tz_convert("UTC").dt.floor("D") - pd.Timedelta(days=k)
    out = np.full(len(rows), np.nan)
    series: dict = {}
    for i, (a, b, t) in enumerate(zip(cl, cn, when, strict=True)):
        key = (a, b, t.year)
        if key not in series:
            f = soil / f"q1_{cell_key(a, b)}_{t.year}.parquet"
            s = pd.read_parquet(f).set_index("time")["sm"] if f.exists() else pd.Series(dtype=float)
            series[key] = s[~s.index.duplicated(keep="last")]
        v = series[key].get(t, np.nan)
        out[i] = float(v) if v is not None else np.nan
    return out


def brier(y, p, m=None) -> float:
    m = np.ones(len(y), bool) if m is None else m
    return float(np.mean((p[m] - y[m]) ** 2))


def main(soil_dir: str, out_path: str) -> None:
    soil = Path(soil_dir)
    rows, fc = rows_q1()
    n = len(rows)
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years = rows["sample_time"].dt.year.to_numpy()
    lake = rows["lake"].to_numpy()
    site = rows["bw_id"].to_numpy()
    week = (rows["bw_id"] + "|" + rows["sample_time"].dt.strftime("%G-%V")).to_numpy()
    rivers, lakes = lake == 0.0, lake == 1.0
    X_lead = {k: features(fc[k][0], fc[k][1], rows[f"risk_lead{k}"], rows.lake, rows.sample_time) for k in te.LEADS}
    sm = {k: soil_at_issue(rows, soil, k) for k in te.LEADS}
    X0 = X_lead[0].copy()
    X0["sm"] = sm[0]
    fit_ok = np.isfinite(sm[0])
    res: dict = {"rows": n, "over_900": int(y.sum()), "sites": int(rows.bw_id.nunique()),
                 "rows_without_sm0": int((~fit_ok).sum()), "inputs": {}}
    for k in te.LEADS:
        both = np.isfinite(sm[k]) & fit_ok
        res["inputs"][k] = {"missing": int(np.isnan(sm[k]).sum()), "mean": float(np.nanmean(sm[k])),
                            "corr_with_sm0": float(np.corrcoef(sm[k][both], sm[0][both])[0, 1]),
                            "mean_abs_change_from_sm0": float(np.mean(np.abs(sm[k][both] - sm[0][both])))}

    # ---- LOYO by lead: folds fitted on lead 0, scored with lead-k inputs
    folds = [g for g in np.unique(years) if y[(years != g) & fit_ok].sum() > 0]
    models = {}
    for g in folds:
        tr = (years != g) & fit_ok
        models[g] = (fit(X0[tr], y[tr], FEATURES), fit(X0[tr], y[tr], CAND),
                     float(np.nanmin(sm[0][tr])), float(np.nanmax(sm[0][tr])))
    res["coef_sm_by_fold"] = {int(g): models[g][1].coef["sm"] for g in folds}
    final = fit(X0[fit_ok], y[fit_ok], CAND)
    res["coef_per_sd_all_rows"] = final.coef
    p_ref, p_cand, held, filled = {}, {}, {}, {}
    for k in te.LEADS:
        pr, pc = np.full(n, np.nan), np.full(n, np.nan)
        h = f = 0
        for g in folds:
            tt = years == g
            mref, mc, lo, hi = models[g]
            Xe = X_lead[k][tt].copy()
            s = sm[k][tt]
            h += int(((s < lo) | (s > hi)).sum())
            Xe["sm"] = np.clip(s, lo, hi)
            a = mref.predict(Xe)
            b = mc.predict(Xe)
            miss = ~np.isfinite(s)
            f += int(miss.sum())
            pr[tt], pc[tt] = a, np.where(miss, a, b)
        p_ref[k], p_cand[k], held[k], filled[k] = pr, pc, h, f
    # The reference must be train_ecoli's own by-lead table.
    ev = json.loads((config.PROCESSED / "ecoli_model_eval.json").read_text())
    pub = {r["lead"]: r for r in ev["by_lead"] if r["exposure"] == "replayed exposure"}
    face = {k: {"train_ecoli": [pub[k]["brier"], pub[k]["brier_river"]],
                "here": [round(brier(y, p_ref[k]), 4), round(brier(y, p_ref[k], rivers), 4)]} for k in te.LEADS}
    res["face_check"] = face
    assert all(v["train_ecoli"] == v["here"] for v in face.values()), f"reference is not train_ecoli's: {face}"

    res["by_lead"] = {}
    for k in te.LEADS:
        r = {"rows_held_to_range": held[k], "rows_scored_with_reference": filled[k]}
        for name, m in (("all", np.ones(n, bool)), ("rivers", rivers), ("lakes", lakes)):
            r[name] = {"reference": brier(y, p_ref[k], m), "candidate": brier(y, p_cand[k], m),
                       "gain": brier(y, p_ref[k], m) - brier(y, p_cand[k], m),
                       "auc_reference": scores(y[m], p_ref[k][m])["auc"], "auc_candidate": scores(y[m], p_cand[k][m])["auc"]}
        r["bootstrap_all"] = te.cluster_bootstrap(y, p_ref[k], p_cand[k], week)
        r["bootstrap_rivers"] = te.cluster_bootstrap(y, p_ref[k], p_cand[k], week, mask=rivers.copy())
        r["bootstrap_lakes"] = te.cluster_bootstrap(y, p_ref[k], p_cand[k], week, mask=lakes.copy())
        res["by_lead"][k] = r

    # ---- reported at lead 0: LOSO, forward, #344's input, within-site rank
    ok = fit_ok
    lo_ref = te.leave_one_out(X0, y, site, lake, FEATURES)
    lo_c = te.leave_one_out(X0, y, site, lake, CAND)
    Xh = features(fc[0][0], fc[0][1], rows["risk_hold_lead0"], rows.lake, rows.sample_time)
    Xh["sm"] = sm[0]
    tr, tt = (years <= te.FORWARD_TRAIN_UNTIL) & ok, years > te.FORWARD_TRAIN_UNTIL
    fw = {c: te._fit_predict(Xh, y, tr, tt, cols, lake) for c, cols in (("reference", FEATURES), ("candidate", CAND))}
    X48 = X_lead[0].copy()
    X48["sm"] = soil_at(rows, soil)
    p48 = te.leave_one_out(X48, y, years, lake, CAND)
    res["lead0_reported"] = {
        "loso": {"reference": brier(y, lo_ref), "candidate": brier(y, lo_c)},
        "forward": {"reference": float(np.mean((fw["reference"] - y[tt]) ** 2)),
                    "candidate": float(np.mean((fw["candidate"] - y[tt]) ** 2)), "rows": int(tt.sum())},
        "input_48h_before_sample_loyo": brier(y, p48)}
    sites = []
    for bw, g in rows.groupby("bw_id"):
        if len(g) < MIN_SITE_SAMPLES:
            continue
        i = g.index.to_numpy()
        a = float(spearmanr(p_ref[0][i], g["log_ecoli"]).statistic)
        b = float(spearmanr(p_cand[0][i], g["log_ecoli"]).statistic)
        sites.append({"bw_id": bw, "name": g["name"].iloc[0], "kind": g["kind"].iloc[0], "n": len(g),
                      "rho_reference": round(a, 3), "rho_candidate": round(b, 3), "change": round(b - a, 3)})
    s = pd.DataFrame(sites)
    res["within_site_lead0"] = {"sites": len(s), "median_change": float(s["change"].median()),
                                "better": int((s["change"] > 0).sum()), "worse": int((s["change"] < 0).sum()),
                                "table": sites}

    # ---- the conditions
    B = res["by_lead"]
    c1 = B[0]["all"]["gain"] >= MARGIN and B[0]["bootstrap_all"]["brier_gain_ci"][0] > 0
    c2 = all(-B[k]["all"]["gain"] <= MARGIN for k in te.LEADS if k > 0)
    c3 = all(-B[k][t]["gain"] <= MARGIN for k in te.LEADS for t in ("rivers", "lakes"))
    c4 = final.coef["sm"] > 0
    res["conditions"] = {"1_lead0_gain": bool(c1), "2_leads1_4_not_worse": bool(c2),
                         "3_rivers_lakes_not_worse": bool(c3), "4_sign_positive": bool(c4)}
    res["passes"] = bool(c1 and c2 and c3 and c4)
    Path(out_path).write_text(json.dumps(res, indent=1, default=float))
    brief = {k: {t: round(B[k][t]["gain"], 5) for t in ("all", "rivers", "lakes")} | {
        "ci_all": [round(v, 5) for v in B[k]["bootstrap_all"]["brier_gain_ci"]]} for k in te.LEADS}
    print(json.dumps({"face_check": face, "by_lead_gain": brief, "conditions": res["conditions"], "passes": res["passes"],
                      "coef_sm": res["coef_sm_by_fold"], "lead0_reported": res["lead0_reported"],
                      "inputs": res["inputs"]}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:])
