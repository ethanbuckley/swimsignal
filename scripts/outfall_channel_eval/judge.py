"""Applies the pre-stated rule of docs/OUTFALL-CHANNEL-TEST-2026-10.md to two finished runs, from their outputs only.

    DIAG_DIR=<scratch> python scripts/outfall_channel_eval/judge.py <ref> <new> [<raised site id> ...]

Needs, under $DIAG_DIR: roots/<variant>/data/processed/ (run_variant.sh), preds_<variant>.parquet (PR #172's
paired.py prep) and paired_<ref>_<new>.json (paired.py compare <ref> <new>). The raised sites are the
evaluation sites whose sum of transport weights the variant raises by over 25% (pre-stated, from
scripts/outfall_channel_report.py). Prints the full-set table, the per-site look and the verdict, and
writes judge_<ref>_<new>.json.
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
# Margins, fixed before any run (the lake test's, and the same margin for lakes)
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


def per_site(ref: str, new: str, sites: list[str]) -> dict:
    p = {v: pd.read_parquet(HERE / f"preds_{v}.parquet") for v in (ref, new)}
    assert p[ref][["bw_id", "sample_time", "y"]].equals(p[new][["bw_id", "sample_time", "y"]])
    r = {v: rows(v) for v in (ref, new)}
    rank = {v: r[v].groupby("bw_id")["risk_model"].mean().rank(ascending=False) for v in (ref, new)}
    out = {}
    for key, ids in [(k, [k]) for k in sites] + [("raised sites pooled", sites)]:
        m = p[ref]["bw_id"].isin(ids).to_numpy()
        y = p[ref]["y"].to_numpy()[m]
        rec = {"n_model": int(m.sum()), "share_over_900": float(y.mean()) if m.any() else None}
        for v, tag in ((ref, "ref"), (new, "new")):
            q = p[v]["loyo_full"].to_numpy()[m]
            rec[f"loyo_mean_pred_{tag}"] = float(q.mean()) if m.any() else None
            rec[f"loyo_brier_{tag}"] = float(np.mean((q - y) ** 2)) if m.any() else None
            if len(ids) == 1:
                d = r[v][r[v]["bw_id"] == ids[0]]
                rec[f"within_rho_{tag}"] = float(spearmanr(d["risk_model"], d["log_ecoli"]).statistic)
                rec[f"mean_exposure_{tag}"] = float(d["risk_model"].mean())
                rec[f"exposure_rank_{tag}"] = f"{int(rank[v][ids[0]])} of {len(rank[v])}"
        out[key] = rec
    return out


def lakes_brier(ref: str, new: str) -> dict:
    """LOYO Brier on lake samples, paired site-week bootstrap (train_ecoli.cluster_bootstrap)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from train_ecoli import cluster_bootstrap
    a, b = (pd.read_parquet(HERE / f"preds_{v}.parquet") for v in (ref, new))
    lake = a["lake"].to_numpy() == 1.0
    return cluster_bootstrap(a["y"].to_numpy(), a["loyo_full"].to_numpy(), b["loyo_full"].to_numpy(), a["week"].to_numpy(),
                             mask=lake.copy(), n_boot=BOOT, seed=SEED)


def judge(ref: str, new: str, raised: list[str]) -> dict:
    a, b = measures(ref), measures(new)
    pc = json.loads((HERE / f"paired_{ref}_{new}.json").read_text())
    lk = lakes_brier(ref, new)
    sites = per_site(ref, new, raised)
    # change = new - ref; cluster_bootstrap gives the Brier gain as ref - new
    brier_up = {k: -pc[k]["brier_gain_ci"][0] for k in ("loyo_all", "loso_all", "fwd_all")}
    auc_lo = {k: pc[k]["auc_gain_ci"][0] for k in ("loyo_all", "loyo_rivers")}
    within = {k: b[k] - a[k] for k in ("within_rho", "loyo_within_rho_combined")}
    pooled = sites["raised sites pooled"]
    cond = {
        "1 Brier: upper end of change <= +0.0005 (LOYO, LOSO, forward)": all(u <= BRIER_MARGIN for u in brier_up.values()),
        "2 AUC: lower end of change >= -0.005 (LOYO all, rivers)": all(x >= -AUC_MARGIN for x in auc_lo.values()),
        "3 cross-site rho: lower end of change >= -0.05": pc["cross_site"]["change_ci"][0] >= -CROSS_MARGIN,
        "4 within-site rho: change >= -0.01 (exposure alone; LOYO rain + risk + season)": all(x >= -WITHIN_MARGIN for x in within.values()),
        "5 lakes: upper end of LOYO Brier change <= +0.0005": -lk["brier_gain_ci"][0] <= BRIER_MARGIN,
        "6 raised sites pooled LOYO Brier not higher": (not raised) or pooled["loyo_brier_new"] <= pooled["loyo_brier_ref"],
    }
    ok = list(cond.values())
    verdict = "passes" if all(ok) else "needs more: keep off" if all(ok[:5]) else "fails: keep off"
    return {"ref": a, "new": b, "brier_change_upper": brier_up, "auc_change_lower": auc_lo, "within_change": within,
            "lakes": lk, "cross_site": pc["cross_site"], "paired": pc, "sites": sites, "conditions": cond, "verdict": verdict}


if __name__ == "__main__":
    ref, new, raised = sys.argv[1], sys.argv[2], sys.argv[3:]
    res = judge(ref, new, raised)
    (HERE / f"judge_{ref}_{new}.json").write_text(json.dumps(res, indent=1, default=float))
    pd.set_option("display.width", 250)
    print(pd.DataFrame({ref: res["ref"], new: res["new"]}).round(4).to_string())
    print("lakes LOYO Brier", round(res["lakes"]["brier_ref"], 5), "->", round(res["lakes"]["brier_new"], 5),
          "change CI", [round(-x, 5) for x in res["lakes"]["brier_gain_ci"][::-1]])
    print(pd.DataFrame(res["sites"]).T.to_string())
    for k, v in res["conditions"].items():
        print(("PASS " if v else "FAIL ") + k)
    print("verdict:", res["verdict"])
