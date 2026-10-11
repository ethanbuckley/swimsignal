"""Applies the pre-stated rule of docs/LAKE-NEAR-FIELD-TEST-2026-10.md to two finished runs, from their outputs only.

    DIAG_DIR=<scratch> python scripts/lake_near_eval/judge.py <ref> <new>

Needs, under $DIAG_DIR: roots/<variant>/data/processed/ (run_variant.sh), preds_<variant>.parquet (PR #172's
paired.py prep) and paired_<ref>_<new>.json (paired.py compare <ref> <new>). Prints the full-set table, the
lake measures, the look at the Coniston sites and the verdict, and writes judge_<ref>_<new>.json. The face
check (condition 6) is tests/test_lake_near.py, which must pass separately.
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
BOOT, SEED = 2000, 1
BRIER_MARGIN, AUC_MARGIN, CROSS_MARGIN, WITHIN_MARGIN = 0.0005, 0.005, 0.05, 0.01   # fixed before any run
# The evaluation sites the option changes most (scripts/lake_near_report.py, before any run)
SITES = {"ukd1230-45750": "Coniston Water, Boating Centre", "ukd1230-45775": "Coniston Water, Monk Coniston",
         "ukd1230-45725": "Coniston Water, Brown Howe"}


def processed(v: str) -> Path:
    return HERE / "roots" / v / "data/processed"


def rows(v: str) -> pd.DataFrame:
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
    lake = {x["predictor"]: x for x in val.get("lake", [])}.get("risk_model", {})
    out["lake_within_rho"] = lake.get("spearman_within_site")
    out["loyo_within_rho_combined"] = comb["loyo_within_site"][COMBINED]["rho_within"]
    s = rows(v).groupby("bw_id").agg(risk=("risk_model", "mean"), ecoli=("log_ecoli", "mean"))
    out["cross_site_rho"] = float(spearmanr(s.risk, s.ecoli).statistic)
    return out


def lakes(ref: str, new: str) -> dict:
    """LOYO Brier and AUC on lake samples, paired site-week bootstrap (train_ecoli.cluster_bootstrap)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from train_ecoli import cluster_bootstrap
    a, b = (pd.read_parquet(HERE / f"preds_{v}.parquet") for v in (ref, new))
    m = a["lake"].to_numpy() == 1.0
    out = cluster_bootstrap(a["y"].to_numpy(), a["loyo_full"].to_numpy(), b["loyo_full"].to_numpy(), a["week"].to_numpy(),
                            mask=m.copy(), n_boot=BOOT, seed=SEED)
    out["exceedances"] = int(a["y"].to_numpy()[m].sum())
    return out


def per_site(ref: str, new: str) -> dict:
    p = {v: pd.read_parquet(HERE / f"preds_{v}.parquet") for v in (ref, new)}
    assert p[ref][["bw_id", "sample_time", "y"]].equals(p[new][["bw_id", "sample_time", "y"]])
    r = {v: rows(v) for v in (ref, new)}
    out = {}
    for sid, name in SITES.items():
        m = (p[ref]["bw_id"] == sid).to_numpy()
        y = p[ref]["y"].to_numpy()[m]
        rec = {"name": name, "n_model": int(m.sum()), "over_900": int(y.sum())}
        for v, tag in ((ref, "ref"), (new, "new")):
            q = p[v]["loyo_full"].to_numpy()[m]
            rec[f"loyo_mean_pred_{tag}"] = float(q.mean()) if m.any() else None
            rec[f"loyo_brier_{tag}"] = float(np.mean((q - y) ** 2)) if m.any() else None
            d = r[v][r[v]["bw_id"] == sid]
            rec[f"within_rho_{tag}"] = float(spearmanr(d["risk_model"], d["log_ecoli"]).statistic) if len(d) > 2 else None
            rec[f"mean_exposure_{tag}"] = float(d["risk_model"].mean()) if len(d) else None
        out[sid] = rec
    return out


def judge(ref: str, new: str) -> dict:
    a, b = measures(ref), measures(new)
    pc = json.loads((HERE / f"paired_{ref}_{new}.json").read_text())
    lk = lakes(ref, new)
    brier_up = {k: -pc[k]["brier_gain_ci"][0] for k in ("loyo_all", "loso_all", "fwd_all")}
    auc_lo = {k: pc[k]["auc_gain_ci"][0] for k in ("loyo_all", "loyo_rivers")}
    within = {k: b[k] - a[k] for k in ("within_rho", "loyo_within_rho_combined")}
    cond = {
        "1 Brier: upper end of change <= +0.0005 (LOYO, LOSO, forward)": all(u <= BRIER_MARGIN for u in brier_up.values()),
        "2 AUC: lower end of change >= -0.005 (LOYO all, rivers)": all(x >= -AUC_MARGIN for x in auc_lo.values()),
        "3 cross-site rho: lower end of change >= -0.05": pc["cross_site"]["change_ci"][0] >= -CROSS_MARGIN,
        "4 within-site rho: change >= -0.01 (exposure alone; LOYO rain + risk + season)": all(x >= -WITHIN_MARGIN for x in within.values()),
        "5 lakes: upper end of LOYO Brier change <= +0.0005": -lk["brier_gain_ci"][0] <= BRIER_MARGIN,
    }
    verdict = "passes 1-5 (6 is tests/test_lake_near.py)" if all(cond.values()) else "fails: keep off"
    return {"ref": a, "new": b, "brier_change_upper": brier_up, "auc_change_lower": auc_lo, "within_change": within,
            "lakes": lk, "cross_site": pc["cross_site"], "paired": pc, "sites": per_site(ref, new), "conditions": cond,
            "verdict": verdict}


if __name__ == "__main__":
    ref, new = sys.argv[1], sys.argv[2]
    res = judge(ref, new)
    (HERE / f"judge_{ref}_{new}.json").write_text(json.dumps(res, indent=1, default=float))
    pd.set_option("display.width", 250)
    print(pd.DataFrame({ref: res["ref"], new: res["new"]}).round(4).to_string())
    lk = res["lakes"]
    print(f"lakes: n {lk['n']}, over 900 {lk['exceedances']}, LOYO Brier {lk['brier_ref']:.5f} -> {lk['brier_new']:.5f} "
          f"change [{-lk['brier_gain_ci'][1]:+.5f}, {-lk['brier_gain_ci'][0]:+.5f}], AUC {lk['auc_ref']} -> {lk['auc_new']} "
          f"change CI {lk['auc_gain_ci']}")
    print(pd.DataFrame(res["sites"]).T.to_string())
    for k, v in res["conditions"].items():
        print(("PASS " if v else "FAIL ") + k)
    print("verdict:", res["verdict"])
