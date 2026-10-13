"""Applies the rule of docs/LAKE-RESIDENCE-TEST-2026-10.md to the finished runs, from their outputs only.

    DIAG_DIR=<scratch> python scripts/lake_residence_eval/judge.py

Needs, under $DIAG_DIR: summary.csv (summary.py), paired_lake_res.json (paired.py compare lake res), preds_lake and
preds_res parquets, and the roots. Runs tests/test_lake_residence.py for condition 7. Prints each condition, the
record table of the sites that move, and the verdict; writes judge.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(os.environ["DIAG_DIR"])
W = Path(__file__).resolve().parents[2]
BRIER_MARGIN, AUC_MARGIN, CROSS_MARGIN, WITHIN_MARGIN = 0.0005, 0.005, 0.05, 0.01   # fixed before any run
PLACEBOS = 20
# measure -> True where higher is better
MEASURES = {"loyo_brier": False, "loyo_auc": True, "loyo_auc_rivers": True, "cross_site_rho": True}
RECORD = {"ukd1203-45625": "Windermere, Lakeside YMCA", "ukd1203-45700": "Windermere, Fellfoot",
          "ukd1203-45650": "Windermere, Millerground Landing", "ukd1203-45675": "Windermere, Rayrigg Meadow",
          "ukj1402-11946": "Wolvercote Mill Stream"}


def record() -> dict:
    out = {}
    for v in ("lake", "res"):
        p = pd.read_parquet(HERE / f"preds_{v}.parquet")
        r = pd.read_parquet(HERE / "roots" / v / "data/processed/ecoli_validation_rows.parquet")
        r = r[r.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "log_ecoli"])
        means = r.groupby("bw_id")["risk_model"].mean()
        rank = means.rank(ascending=False)
        for bw, name in RECORD.items():
            g, h = p[p.bw_id == bw], r[r.bw_id == bw]
            out.setdefault(name, {})[v] = {
                "samples": len(g), "over_900": int(g.y.sum()),
                "mean_loyo_pred": float(g.loyo_full.mean()) if len(g) else None,
                "loyo_brier": float(np.mean((g.loyo_full - g.y) ** 2)) if len(g) else None,
                "within_rho": float(spearmanr(h.risk_model, h.log_ecoli).statistic) if len(h) > 2 else None,
                "mean_exposure": float(means.get(bw, np.nan)), "exposure_rank": float(rank.get(bw, np.nan)),
                "of_sites": len(means)}
    return out


def main() -> None:
    s = pd.read_csv(HERE / "summary.csv").set_index("variant")
    ph = s.loc[[f"ph{k:02d}" for k in range(1, PLACEBOS + 1)]]
    assert len(ph) == PLACEBOS, "not every placebo has finished"
    res, lake = s.loc["res"], s.loc["lake"]
    p = json.loads((HERE / "paired_lake_res.json").read_text())
    up = lambda key: -p[key]["brier_gain_ci"][0]     # upper end of the Brier change (new minus ref)
    c1 = {k: {"change": -p[k]["brier_gain"], "upper": up(k), "holds": up(k) <= BRIER_MARGIN}
          for k in ("loyo_all", "loso_all", "fwd_all")}
    c2 = {k: {"auc_ref": p[k]["auc_ref"], "auc_new": p[k]["auc_new"], "lower": p[k]["auc_gain_ci"][0],
              "holds": p[k]["auc_gain_ci"][0] >= -AUC_MARGIN} for k in ("loyo_all", "loyo_rivers")}
    cs = p["cross_site"]
    c3 = {"rho_ref": cs["rho_ref"], "rho_new": cs["rho_new"], "change": cs["change"], "ci": cs["change_ci"],
          "holds": cs["change_ci"][0] >= -CROSS_MARGIN}
    c4 = {k: {"lake": float(lake[k]), "res": float(res[k]), "change": float(res[k] - lake[k]),
              "holds": float(res[k] - lake[k]) >= -WITHIN_MARGIN}
          for k in ("within_rho_all_sites", "loyo_within_rho_combined")}
    c4["within_rho_lake (reported)"] = {"lake": float(lake["within_rho_lake"]), "res": float(res["within_rho_lake"])}
    c5 = {"change": -p["loyo_lakes"]["brier_gain"], "ci_upper": up("loyo_lakes"), "n": p["loyo_lakes"].get("n"),
          "holds": up("loyo_lakes") <= BRIER_MARGIN}
    c6 = {}
    for m, higher in MEASURES.items():
        worse = int(((ph[m] <= res[m]) if higher else (ph[m] >= res[m])).sum())   # placebos at least as bad as res
        better = int(((ph[m] >= res[m]) if higher else (ph[m] <= res[m])).sum())  # at least as good (reported)
        c6[m] = {"res": float(res[m]), "lake": float(lake[m]), "placebo_min": float(ph[m].min()),
                 "placebo_median": float(ph[m].median()), "placebo_max": float(ph[m].max()),
                 "placebos_at_least_as_bad": worse, "placebos_at_least_as_good": better, "holds": worse >= 1}
    c6_holds = all(v["holds"] for v in c6.values())
    t = subprocess.run([sys.executable, "-m", "pytest", "-q", str(W / "tests/test_lake_residence.py")],
                       cwd=W, capture_output=True, text=True, check=False, env={**os.environ, "PYTHONPATH": str(W / "src")})
    c7 = {"pytest": t.stdout.strip().splitlines()[-1] if t.stdout.strip() else t.stderr[-300:], "holds": t.returncode == 0}
    attempts = {k: int(v) for k, v in s["net_attempts"].items()}
    verdict = (all(v["holds"] for v in c1.values()) and all(v["holds"] for v in c2.values()) and c3["holds"]
               and all(v["holds"] for k, v in c4.items() if "reported" not in k) and c5["holds"] and c6_holds
               and c7["holds"] and not any(attempts.values()))
    out = {"C1_brier": c1, "C2_auc": c2, "C3_cross_site": c3, "C4_within_site": c4, "C5_lakes": c5,
           "C6_placebos": {"holds": c6_holds, "measures": c6}, "C7_face_check": c7, "network_attempts": attempts,
           "samples": {"lake": int(lake["n"]), "res": int(res["n"]), "paired": p["n_paired"]},
           "record": record(), "passes": verdict}
    (HERE / "judge.json").write_text(json.dumps(out, indent=1, default=float))
    for name in ("C1_brier", "C2_auc", "C3_cross_site", "C4_within_site", "C5_lakes", "C6_placebos", "C7_face_check",
                 "network_attempts", "samples", "record"):
        print(name, json.dumps(out[name], default=lambda x: round(float(x), 5)))
    print("VERDICT:", "passes" if verdict else "fails")


if __name__ == "__main__":
    main()
