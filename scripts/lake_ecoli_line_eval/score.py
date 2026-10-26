"""docs/LAKE-ECOLI-LINE-TEST-2026-10.md: does the E. coli model rank lake sample days at a lower line?

    score.py face <out dir>     the face check at 900; writes face.json and stops
    score.py score <out dir>    the gate and the scores at 235 and 500 (and the tables at 900); writes score.json

train_ecoli.py's rows, filters, features, fitting and functions, with the outcome redefined as over the line.

Face check: this script's LOYO, LOSO and forward predictions at 900 equal, row by row to 1e-9, the ones
train_ecoli.main() makes in the same process and root (captured by wrapping its leave_one_out and _fit_predict).
run.sh runs the score phase only if face.json passes and every step made 0 network attempts.

Choices fixed here before any score:
* Brier is the mean of (p - y)^2 without clipping, as train_ecoli.cluster_bootstrap computes it.
* The bootstrap replays cluster_bootstrap's draws (same seed and order; checked against its own 95% output) and
  reads the 1.25th and 98.75th percentiles. Draws whose lake rows hold no event give no AUC and are counted.
* Placebo: lake outcomes permuted within each lake (sorted bw_id order), numpy default_rng(20261025), 200 shuffles,
  LOSO refitted on each. Condition 6 needs the real gain above np.percentile(gains, 95) (linear), which is at least
  the 190th smallest; both are reported.
* R2 for rivers (description only) is the same rule fitted on training river rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import train_ecoli as te
from sklearn.metrics import roc_auc_score

from dipcast import config
from dipcast.model import ecoli
from dipcast.model.ecoli import FEATURES, features, fit
from dipcast.model.forecast import MAX_MISSING_SHARE

LINES = (235, 500)
TABLE_LINES = (235, 500, 900)
RAIN_RULE_MM = te.HEAVY_RAIN_MM
GATE_EVENTS, GATE_LAKES, GATE_PER_YEAR = 30, 5, 5
SKILL_MIN, AUC_MIN = 0.02, 0.65
LO, HI = 1.25, 98.75
N_PLACEBO, PLACEBO_SEED = 200, 20261025
FACE_TOL = 1e-9


def rows_as_train_ecoli():
    """train_ecoli.main's rows and filters, unchanged, with the lead-0 inputs it fits on."""
    rows = pd.read_parquet(config.PROCESSED / "ecoli_validation_rows.parquet")
    rows = rows[rows.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "ecoli"]).reset_index(drop=True)
    rows["lake"] = (rows["kind"] == "lake").astype(float)
    rows["day"] = rows["sample_time"].dt.floor("D")
    sites = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id").set_index("bw_id")
    rows["lat"], rows["lon"] = sites.loc[rows.bw_id, "lat"].to_numpy(), sites.loc[rows.bw_id, "lon"].to_numpy()
    n0 = len(rows)
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
    ok_exp = np.all([shown[k] for k in te.LEADS], axis=0)
    lake_all = rows["lake"].to_numpy() == 1.0
    miss = {"samples_with_upstream": n0, "lake_samples_with_upstream": int(lake_all.sum()),
            "dropped_missing_forecast_rain": int((~ok_rain).sum()),
            "dropped_missing_forecast_rain_lakes": int((~ok_rain & lake_all).sum()),
            "dropped_missing_replayed_exposure": int((ok_rain & ~ok_exp).sum()),
            "dropped_missing_replayed_exposure_lakes": int((ok_rain & ~ok_exp & lake_all).sum())}
    ok = ok_rain & ok_exp
    rows = rows[ok].reset_index(drop=True)
    r48 = fc[0][0][ok]
    X = features(r48, fc[0][1][ok], rows["risk_lead0"], rows.lake, rows.sample_time)
    Xh = features(r48, fc[0][1][ok], rows["risk_hold_lead0"], rows.lake, rows.sample_time)
    return rows, X, Xh, r48, miss


def capture_train_ecoli() -> dict:
    """Run train_ecoli.main() and keep its full-model LOYO, LOSO and forward predictions."""
    got, depth = {}, [0]
    loo, fp = te.leave_one_out, te._fit_predict

    def leave_one_out(X, y, groups, lake, cols, X_eval=None):
        depth[0] += 1
        try:
            p = loo(X, y, groups, lake, cols, X_eval)
        finally:
            depth[0] -= 1
        if list(cols) == FEATURES and X_eval is None:
            key = "loyo" if np.issubdtype(np.asarray(groups).dtype, np.integer) else "loso"
            got.setdefault(key, p.copy())
        return p

    def _fit_predict(X, y, tr, tt, cols, lake, X_eval=None):
        p = fp(X, y, tr, tt, cols, lake, X_eval)
        if depth[0] == 0 and list(cols) == FEATURES and X_eval is None:
            full = np.full(len(y), np.nan); full[tt] = p; got.setdefault("forward", full)
        return p

    te.leave_one_out, te._fit_predict = leave_one_out, _fit_predict
    try:
        te.main()
    finally:
        te.leave_one_out, te._fit_predict = loo, fp
    return got


def forward(X, Xh, y, years, lake, cols):
    tr, tt = years <= te.FORWARD_TRAIN_UNTIL, years > te.FORWARD_TRAIN_UNTIL
    p = np.full(len(y), np.nan)
    if Xh[FEATURES].notna().all().all():
        p[tt] = te._fit_predict(Xh, y, tr, tt, cols, lake)
    return p


def rain_rule(y, groups, lake, r48, fold_groups=None):
    """R2: per training fold, by type, the share over the line when 48 h rain >= 10 mm and when below; R1 if a group
    has no training rows. fold_groups=None scores every group as test once (LOO); otherwise (tr, tt) pairs."""
    wet = r48 >= RAIN_RULE_MM
    p = np.full(len(y), np.nan)
    folds = fold_groups if fold_groups is not None else [(groups != g, groups == g) for g in np.unique(groups)]
    for tr, tt in folds:
        if y[tr].sum() == 0 and fold_groups is None:
            continue
        for kind in (0.0, 1.0):
            base_m = tr & (lake == kind)
            base = y[base_m].mean() if base_m.any() else y[tr].mean()
            for w in (True, False):
                m = base_m & (wet == w)
                p[tt & (lake == kind) & (wet == w)] = y[m].mean() if m.any() else base
    return p


def brier(y, p, m):
    m = m & ~np.isnan(p)
    return float(np.mean((p[m] - y[m]) ** 2)) if m.any() else float("nan")


def auc(y, p, m):
    m = m & ~np.isnan(p)
    return float(roc_auc_score(y[m], p[m])) if m.any() and 0 < y[m].mean() < 1 else float("nan")


def boot(y, p_ref, p_new, clusters, mask, n_boot=te.BOOT, seed=1) -> dict:
    """cluster_bootstrap's draws, replayed, keeping the distributions."""
    rng = np.random.default_rng(seed)
    m = mask & ~np.isnan(p_ref) & ~np.isnan(p_new)
    y, p_ref, p_new, clusters = y[m], p_ref[m], p_new[m], np.asarray(clusters)[m]
    uniq, inv = np.unique(clusters, return_inverse=True)
    idx_by = [np.where(inv == i)[0] for i in range(len(uniq))]
    d_brier, d_auc, a_new, no_event = [], [], [], 0
    for _ in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([idx_by[i] for i in pick])
        yy = y[idx]
        d_brier.append(np.mean((p_ref[idx] - yy) ** 2) - np.mean((p_new[idx] - yy) ** 2))
        if 0 < yy.mean() < 1:
            an = roc_auc_score(yy, p_new[idx])
            d_auc.append(an - roc_auc_score(yy, p_ref[idx])); a_new.append(an)
        else:
            no_event += 1
    d_brier, a_new = np.array(d_brier), np.array(a_new)
    return {"n": int(len(y)), "clusters": int(len(uniq)),
            "brier_gain": float(np.mean((p_ref - y) ** 2) - np.mean((p_new - y) ** 2)),
            "brier_gain_ci95": [float(np.percentile(d_brier, 2.5)), float(np.percentile(d_brier, 97.5))],
            "brier_gain_ci975": [float(np.percentile(d_brier, LO)), float(np.percentile(d_brier, HI))],
            "auc_new_ci975": [float(np.percentile(a_new, LO)), float(np.percentile(a_new, HI))] if len(a_new) else None,
            "draws_without_auc": no_event}


def table(y, preds: dict, m_all, lake):
    out = {}
    for name, p in preds.items():
        out[name] = {}
        for sub, m in (("lakes", m_all & (lake == 1.0)), ("rivers", m_all & (lake == 0.0))):
            out[name][sub] = {"n": int((m & ~np.isnan(p)).sum()), "over": int(y[m & ~np.isnan(p)].sum()),
                              "brier": brier(y, p, m), "auc": auc(y, p, m)}
    for sub in ("lakes", "rivers"):
        ref = out["R1"][sub]["brier"]
        for name in preds:
            out[name][sub]["skill_vs_R1"] = 1 - out[name][sub]["brier"] / ref if ref and ref > 0 else float("nan")
    return out


def face(out: Path) -> None:
    rows, X, Xh, r48, miss = rows_as_train_ecoli()
    y = (rows["ecoli"] > ecoli.THRESHOLD).astype(int).to_numpy()
    years, site, lake = rows["sample_time"].dt.year.to_numpy(), rows["bw_id"].to_numpy(), rows["lake"].to_numpy()
    mine = {"loyo": te.leave_one_out(X, y, years, lake, FEATURES), "loso": te.leave_one_out(X, y, site, lake, FEATURES),
            "forward": forward(X, Xh, y, years, lake, FEATURES)}
    theirs = capture_train_ecoli()
    res = {"rows": len(rows), "lake_rows": int((lake == 1).sum()), "sites": int(rows.bw_id.nunique()),
           "lakes": int(rows.loc[lake == 1, "bw_id"].nunique()), "over_900": int(y.sum()),
           "lake_over_900": int(y[lake == 1].sum()), "published": {"rows": 1502, "lake_rows": 595}, "missingness": miss,
           "compare": {}}
    ok = True
    for k, p in mine.items():
        q = theirs.get(k)
        if q is None or len(q) != len(p):
            res["compare"][k] = {"found": q is not None, "same_length": False}; ok = False; continue
        same_nan = bool(np.array_equal(np.isnan(p), np.isnan(q)))
        diff = float(np.nanmax(np.abs(p - q))) if (~np.isnan(p)).any() else 0.0
        res["compare"][k] = {"same_missing": same_nan, "max_abs_diff": diff, "n_missing": int(np.isnan(p).sum())}
        ok &= same_nan and diff <= FACE_TOL
    ev = json.loads((config.PROCESSED / "ecoli_model_eval.json").read_text())
    res["train_ecoli_eval"] = {"n_samples": ev["n_samples"], "base_rate_by_type": ev["base_rate_by_type"],
                               "loyo_brier_full": ev["bootstrap"]["loyo|all|site_week"]["brier_new"],
                               "loso_brier_full": ev["bootstrap"]["loso|all|site_week"]["brier_new"]}
    res["here"] = {"loyo_brier_full": brier(y, mine["loyo"], np.ones(len(y), bool)),
                   "loso_brier_full": brier(y, mine["loso"], np.ones(len(y), bool))}
    res["passes"] = bool(ok)
    (out / "face.json").write_text(json.dumps(res, indent=1, default=float))
    print("face check", "passes" if ok else "FAILS", json.dumps(res["compare"]))


def score(out: Path) -> None:
    rows, X, Xh, r48, miss = rows_as_train_ecoli()
    years, site, lake = rows["sample_time"].dt.year.to_numpy(), rows["bw_id"].to_numpy(), rows["lake"].to_numpy()
    is_lake = lake == 1.0
    every = np.ones(len(rows), dtype=bool)
    tr_f, tt_f = years <= te.FORWARD_TRAIN_UNTIL, years > te.FORWARD_TRAIN_UNTIL
    res = {"rows": len(rows), "lake_rows": int(is_lake.sum()), "lakes": int(rows.loc[is_lake, "bw_id"].nunique()),
           "missingness": miss, "lines": {}}

    # The gate first: the first counts at 235 and 500.
    for T in LINES:
        y = (rows["ecoli"] > T).astype(int).to_numpy()
        by_year = {int(v): int(y[is_lake & (years == v)].sum()) for v in sorted(set(years.tolist()))}
        lakes_hit = int(rows.loc[is_lake & (y == 1), "bw_id"].nunique())
        gate = {"over": int(y[is_lake].sum()), "lakes_with_one_or_more": lakes_hit, "by_year": by_year,
                "lake_rows_by_year": {int(v): int((is_lake & (years == v)).sum()) for v in sorted(set(years.tolist()))}}
        gate["judged"] = bool(gate["over"] >= GATE_EVENTS and lakes_hit >= GATE_LAKES
                              and all(c >= GATE_PER_YEAR for c in by_year.values()))
        res["lines"][T] = {"gate": gate}
        print(f"gate at {T}:", json.dumps(gate))

    for T in TABLE_LINES:
        y = (rows["ecoli"] > T).astype(int).to_numpy()
        p = {"loso": {"model": te.leave_one_out(X, y, site, lake, FEATURES), "R1": te.leave_one_out(X, y, site, lake, []),
                      "R2": rain_rule(y, site, lake, r48)},
             "loyo": {"model": te.leave_one_out(X, y, years, lake, FEATURES), "R1": te.leave_one_out(X, y, years, lake, []),
                      "R2": rain_rule(y, years, lake, r48)},
             "forward": {"model": forward(X, Xh, y, years, lake, FEATURES), "R1": forward(X, Xh, y, years, lake, []),
                         "R2": rain_rule(y, years, lake, r48, fold_groups=[(tr_f, tt_f)])}}
        L = res["lines"].setdefault(T, {})
        L["tables"] = {"loso": table(y, p["loso"], every, lake), "loyo": table(y, p["loyo"], every, lake),
                       "forward": table(y, p["forward"], tt_f, lake)}
        L["missing_lake_predictions"] = {ev: {k: int(np.isnan(v[is_lake]).sum()) for k, v in pp.items()} for ev, pp in p.items()}
        L["loyo_by_year_lakes"] = {int(v): {"n": int((is_lake & (years == v)).sum()), "over": int(y[is_lake & (years == v)].sum()),
                                            "brier_model": brier(y, p["loyo"]["model"], is_lake & (years == v)),
                                            "brier_R1": brier(y, p["loyo"]["R1"], is_lake & (years == v))}
                                   for v in sorted(set(years.tolist()))}
        for v in L["loyo_by_year_lakes"].values():
            v["gain"] = v["brier_R1"] - v["brier_model"]
        final = fit(X, y, FEATURES, meta={"target": f"E. coli > {T} cfu/100 ml", "test": "docs/LAKE-ECOLI-LINE-TEST-2026-10.md",
                                           "n_samples": len(rows), "lake_base_rate": float(y[is_lake].mean())})
        L["coef_per_sd"] = final.coef
        L["intercept"] = final.intercept
        L["lake_base_rate_all_rows"] = float(y[is_lake].mean())
        if T not in LINES:
            continue
        final.save(out / f"model_{T}.json")
        bm = boot(y, p["loso"]["R1"], p["loso"]["model"], site, is_lake)
        b_check = te.cluster_bootstrap(y, p["loso"]["R1"], p["loso"]["model"], site, mask=is_lake.copy())
        bm["matches_cluster_bootstrap_95"] = bool(np.allclose(bm["brier_gain_ci95"], b_check["brier_gain_ci"], atol=0, rtol=0))
        L["bootstrap_loso_lakes_vs_R1"] = bm
        L["bootstrap_loso_lakes_vs_R2"] = boot(y, p["loso"]["R2"], p["loso"]["model"], site, is_lake)
        # Placebo: outcomes shuffled within each lake, LOSO refitted.
        rng = np.random.default_rng(PLACEBO_SEED)
        lake_sites = sorted(set(site[is_lake].tolist()))
        idx_by = [np.where(is_lake & (site == s))[0] for s in lake_sites]
        real_gain = L["tables"]["loso"]["R1"]["lakes"]["brier"] - L["tables"]["loso"]["model"]["lakes"]["brier"]
        gains = []
        for _ in range(N_PLACEBO):
            yp = y.copy()
            for ix in idx_by:
                yp[ix] = y[ix][rng.permutation(len(ix))]
            pm, pr = te.leave_one_out(X, yp, site, lake, FEATURES), te.leave_one_out(X, yp, site, lake, [])
            gains.append(brier(yp, pr, is_lake) - brier(yp, pm, is_lake))
        g = np.sort(np.array(gains))
        L["placebo"] = {"n": N_PLACEBO, "seed": PLACEBO_SEED, "real_gain": real_gain, "lowest": float(g[0]),
                        "median": float(np.median(g)), "p95": float(np.percentile(g, 95)), "rank_190": float(g[round(0.95 * len(g)) - 1]),
                        "highest": float(g[-1]), "share_at_or_above_real": float((g >= real_gain).mean()),
                        "gains": g.tolist()}
        # Per lake, LOSO.
        L["loso_by_lake"] = [{"bw_id": s, "name": rows.loc[site == s, "name"].iloc[0], "n": int((site == s).sum()),
                              "over": int(y[site == s].sum()), "mean_model": float(np.nanmean(p["loso"]["model"][site == s])),
                              "brier_model": brier(y, p["loso"]["model"], site == s), "brier_R1": brier(y, p["loso"]["R1"], site == s),
                              "brier_R2": brier(y, p["loso"]["R2"], site == s)} for s in lake_sites]
        # The seven conditions.
        S, Y, F = L["tables"]["loso"], L["tables"]["loyo"], L["tables"]["forward"]
        skill = S["model"]["lakes"]["skill_vs_R1"]
        yrs = [v["gain"] for v in L["loyo_by_year_lakes"].values()]
        c = {"1_loso_skill_vs_R1": bool(skill >= SKILL_MIN and bm["brier_gain_ci975"][0] > 0),
             "2_loso_not_worse_than_R2": bool(S["R2"]["lakes"]["brier"] - S["model"]["lakes"]["brier"] >= 0),
             "3_loso_auc": bool(S["model"]["lakes"]["auc"] >= AUC_MIN and bm["auc_new_ci975"] is not None
                                and bm["auc_new_ci975"][0] > 0.5),
             "4_loyo_gain": bool(Y["R1"]["lakes"]["brier"] - Y["model"]["lakes"]["brier"] > 0
                                 and sum(gv > 0 for gv in yrs) >= 2),
             "5_forward_gain": bool(not np.isnan(F["model"]["lakes"]["brier"])
                                    and F["R1"]["lakes"]["brier"] - F["model"]["lakes"]["brier"] > 0),
             "6_placebo": bool(real_gain > L["placebo"]["p95"]),
             "7_face_check": True}
        L["conditions"] = c
        L["passes"] = bool(L["gate"]["judged"] and all(c.values()))
        L["verdict"] = "passes" if L["passes"] else ("too few to judge" if not L["gate"]["judged"] else "fails")
        print(f"line {T}: {L['verdict']}", json.dumps(c))
    (out / "score.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    phase, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    {"face": face, "score": score}[phase](out)
