"""Applies the pre-stated rule of docs/LAKE-PATH-TEST-2026-10.md to two finished runs, from their outputs only.

    DIAG_DIR=<scratch> python scripts/lake_path_eval/judge.py <ref> <new>

Needs, under $DIAG_DIR: roots/<variant>/data/processed/ (run_variant.sh), preds_<variant>.parquet (PR #172's
paired.py prep) and paired_<ref>_<new>.json (paired.py compare <ref> <new>). Prints the full-set table, the
affected-site look and the verdict, and writes judge_<ref>_<new>.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(os.environ["DIAG_DIR"])
FULL = "rain + spill exposure + season (dipcast)"
COMBINED = "rain + spill risk + season"
# The evaluation sites whose sum of transport weights changes by more than 1% (scripts/lake_path_report.py)
SITES = {"ukd1203-45625": "Windermere, Lakeside YMCA", "ukd1203-45700": "Windermere, Fellfoot",
         "ukj1402-11946": "Wolvercote Mill Stream"}
SOUTH_BASIN = ["ukd1203-45625", "ukd1203-45700"]
# Margins, fixed before any run
BRIER_MARGIN, AUC_MARGIN, CROSS_MARGIN, WITHIN_MARGIN = 0.0005, 0.005, 0.05, 0.01


def processed(v: str) -> Path:
    return HERE / "roots" / v / "data/processed"


def rows(v: str) -> pd.DataFrame:
    """validate_ecoli_combined's rows: samples with upstream overflows and every input."""
    r = pd.read_parquet(processed(v) / "ecoli_validation_rows.parquet")
    return r[r.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "log_ecoli"])


def measures(v: str) -> dict:
    p = processed(v)
    e = json.loads((p / "ecoli_model_eval.json").read_text())
    val = json.loads((p / "ecoli_validation.json").read_text())
    comb = json.loads((p / "ecoli_validation_combined.json").read_text())
    out = {"n_model": e["n_samples"]}
    for split in ("loyo", "loso"):
        t = {x["model"]: x for x in e[split]}[FULL]
        out[f"{split}_brier"], out[f"{split}_auc"], out[f"{split}_auc_rivers"] = t["brier"], t["auc"], t["auc_river"]
    t = {x["model"]: x for x in e["forward"]["table"]}[FULL]
    out["fwd_brier"], out["fwd_auc"] = t["brier"], t["auc"]
    risk = {x["predictor"]: x for x in val["all_sites"]}["risk_model"]
    out["pooled_rho"], out["within_rho"] = risk["spearman_pooled"], risk["spearman_within_site"]
    out["loyo_within_rho_combined"] = comb["loyo_within_site"][COMBINED]["rho_within"]
    s = rows(v).groupby("bw_id").agg(risk=("risk_model", "mean"), ecoli=("log_ecoli", "mean"))
    out["cross_site_rho"] = float(spearmanr(s.risk, s.ecoli).statistic)
    return out


def affected(ref: str, new: str) -> dict:
    p = {v: pd.read_parquet(HERE / f"preds_{v}.parquet") for v in (ref, new)}
    keys = ["bw_id", "sample_time", "y"]
    assert p[ref][keys].equals(p[new][keys])
    r = {v: rows(v) for v in (ref, new)}
    rank = {v: r[v].groupby("bw_id")["risk_model"].mean().rank(ascending=False) for v in (ref, new)}
    out = {}
    for key, ids in [(k, [k]) for k in SITES] + [("south basin pooled", SOUTH_BASIN)]:
        m = p[ref]["bw_id"].isin(ids).to_numpy()
        y = p[ref]["y"].to_numpy()[m]
        rec = {"name": " + ".join(SITES[i] for i in ids), "n_model": int(m.sum()), "share_over_900": float(y.mean())}
        for v, tag in ((ref, "ref"), (new, "new")):
            q = p[v]["loyo_full"].to_numpy()[m]
            rec[f"loyo_mean_pred_{tag}"] = float(q.mean())
            rec[f"loyo_brier_{tag}"] = float(np.mean((q - y) ** 2))
            d = r[v][r[v]["bw_id"].isin(ids)]
            rec["n_rows"] = len(d)
            if len(ids) == 1:
                rec[f"within_rho_{tag}"] = float(spearmanr(d["risk_model"], d["log_ecoli"]).statistic)
                rec[f"mean_exposure_{tag}"] = float(d["risk_model"].mean())
                rec[f"exposure_rank_{tag}"] = f"{int(rank[v][ids[0]])} of {len(rank[v])}"
        out[key] = rec
    return out


def judge(ref: str, new: str) -> dict:
    a, b = measures(ref), measures(new)
    pc = json.loads((HERE / f"paired_{ref}_{new}.json").read_text())
    look = affected(ref, new)
    # change = new - ref; cluster_bootstrap gives the Brier gain as ref - new
    brier_up = {k: -pc[k]["brier_gain_ci"][0] for k in ("loyo_all", "loso_all", "fwd_all")}
    auc_lo = {k: pc[k]["auc_gain_ci"][0] for k in ("loyo_all", "loyo_rivers")}
    within = {k: b[k] - a[k] for k in ("within_rho", "loyo_within_rho_combined")}
    sb = look["south basin pooled"]
    cond = {
        "1 Brier: upper end of change <= +0.0005 (LOYO, LOSO, forward)": all(u <= BRIER_MARGIN for u in brier_up.values()),
        "2 AUC: lower end of change >= -0.005 (LOYO all, rivers)": all(x >= -AUC_MARGIN for x in auc_lo.values()),
        "3 cross-site rho: lower end of change >= -0.05": pc["cross_site"]["change_ci"][0] >= -CROSS_MARGIN,
        "4 within-site rho: change >= -0.01 (exposure alone; LOYO rain + risk + season)": all(x >= -WITHIN_MARGIN for x in within.values()),
        "5 south basin pooled LOYO Brier not higher": sb["loyo_brier_new"] <= sb["loyo_brier_ref"],
    }
    ok = list(cond.values())
    verdict = ("candidate to switch on" if all(ok) else
               "needs more: keep off" if all(ok[:4]) else "keep off")
    return {"ref": a, "new": b, "brier_change_upper": brier_up, "auc_change_lower": auc_lo, "within_change": within,
            "cross_site": pc["cross_site"], "paired": pc, "affected": look, "conditions": cond, "verdict": verdict}


if __name__ == "__main__":
    res = judge(sys.argv[1], sys.argv[2])
    (HERE / f"judge_{sys.argv[1]}_{sys.argv[2]}.json").write_text(json.dumps(res, indent=1, default=float))
    pd.set_option("display.width", 250)
    print(pd.DataFrame({sys.argv[1]: res["ref"], sys.argv[2]: res["new"]}).round(4).to_string())
    print(pd.DataFrame(res["affected"]).T.to_string())
    for k, v in res["conditions"].items():
        print(("PASS " if v else "FAIL ") + k)
    print("verdict:", res["verdict"])
