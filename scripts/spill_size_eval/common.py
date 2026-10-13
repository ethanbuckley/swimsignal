"""Condition 1 of docs/SPILL-SIZE-TEST-2026-10.md recomputed on the samples that every run keeps.

Added after summary.csv was seen, and before any paired result. The runs keep different samples: a run drops a
whole site when more than MAX_MISSING_SHARE of its weight comes from overflows without rain data, and the sizes
move that weight. So the stated condition 1 compares runs partly on different samples. This asks whether its
answer depends on that. Cross-site rho uses every site in every run, so it is taken from summary.csv unchanged.

    DIAG_DIR=<scratch> python scripts/spill_size_eval/common.py

Writes common.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(os.environ["DIAG_DIR"])
PLACEBOS, K_MAX, OF_FOUR = 20, 1, 3                     # judge.py's condition 1
MEASURES = {"loyo_brier": False, "loyo_auc": True, "loyo_auc_rivers": True, "cross_site_rho": True}


def measures(d: pd.DataFrame) -> dict:
    riv = (d.lake == 0.0).to_numpy()
    y, p = d.y.to_numpy(), d.loyo_full.to_numpy()
    return {"loyo_brier": float(np.mean((p - y) ** 2)), "loyo_auc": float(roc_auc_score(y, p)),
            "loyo_auc_rivers": float(roc_auc_score(y[riv], p[riv]))}


def main() -> None:
    s = pd.read_csv(HERE / "summary.csv").set_index("variant")
    preds = {}
    for v in s.index:
        d = pd.read_parquet(HERE / f"preds_{v}.parquet")
        preds[v] = d.assign(occ=d.groupby(["bw_id", "sample_time"]).cumcount()).set_index(["bw_id", "sample_time", "occ"])
        for k, x in measures(preds[v]).items():           # on its own samples it must give summary.csv's figure
            assert round(x, 4) == s.loc[v, k], (v, k, x, s.loc[v, k])
    common = preds["length"].index
    for d in preds.values():
        common = common.intersection(d.index)
    t = pd.DataFrame({v: {**measures(d.loc[common]), "cross_site_rho": float(s.loc[v, "cross_site_rho"])}
                      for v, d in preds.items()}).T
    ph, real = t.loc[[f"ph{k:02d}" for k in range(1, PLACEBOS + 1)]], t.loc["sh"]
    c1 = {}
    for m, higher in MEASURES.items():
        k = int(((ph[m] >= real[m]) if higher else (ph[m] <= real[m])).sum())
        c1[m] = {"sh": real[m], "length": t.loc["length", m], "flow": t.loc["flow", m],
                 "placebo_min": ph[m].min(), "placebo_median": ph[m].median(), "placebo_max": ph[m].max(),
                 "k_at_least_as_good": k, "holds": k <= K_MAX}
    held = sum(v["holds"] for v in c1.values())
    sites = sorted(set(preds["length"].index.get_level_values(0)) - set(common.get_level_values(0)))
    out = {"n_common": len(common), "positives": int(preds["length"].loc[common, "y"].sum()),
           "sites_left_out": sites, "measures": c1, "holds_on": held, "C1_holds": held >= OF_FOUR}
    (HERE / "common.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=lambda x: round(float(x), 5)))


if __name__ == "__main__":
    main()
