"""Applies the pre-stated rule of docs/SPILL-SIZE-TEST-2026-10.md to the finished runs, from their outputs only.

    DIAG_DIR=<scratch> python scripts/spill_size_eval/judge.py

Needs, under $DIAG_DIR: summary.csv (summary.py), paired_length_sh.json and paired_flow_sh.json (paired.py
compare). Prints each condition and the verdict, and writes judge.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

HERE = Path(os.environ["DIAG_DIR"])
BRIER_MARGIN, AUC_MARGIN, CROSS_MARGIN = 0.0005, 0.005, 0.05   # fixed before any run
PLACEBOS, K_MAX, OF_FOUR = 20, 1, 3                             # C1: k <= 1 on at least 3 of the 4 measures
# measure -> True where higher is better
MEASURES = {"loyo_brier": False, "loyo_auc": True, "loyo_auc_rivers": True, "cross_site_rho": True}


def main() -> None:
    s = pd.read_csv(HERE / "summary.csv").set_index("variant")
    ph = s.loc[[f"ph{k:02d}" for k in range(1, PLACEBOS + 1)]]
    assert len(ph) == PLACEBOS, "not every placebo has finished"
    real = s.loc["sh"]
    c1 = {}
    for m, higher in MEASURES.items():
        k = int(((ph[m] <= real[m]) if higher else (ph[m] >= real[m])).sum())   # placebos at least as good as the real one
        c1[m] = {"real": float(real[m]), "flow": float(s.loc["flow", m]), "length": float(s.loc["length", m]),
                 "placebo_median": float(ph[m].median()), "placebo_min": float(ph[m].min()), "placebo_max": float(ph[m].max()),
                 "k_at_least_as_good": k, "holds": k <= K_MAX}
    c1_holds = sum(v["holds"] for v in c1.values()) >= OF_FOUR

    p = json.loads((HERE / "paired_length_sh.json").read_text())
    up = lambda key: -p[key]["brier_gain_ci"][0]     # upper end of the Brier change (new minus ref)
    c2 = {k: {"change": -p[k]["brier_gain"], "upper": up(k), "holds": up(k) <= BRIER_MARGIN}
          for k in ("loyo_all", "loso_all", "fwd_all")}
    c3 = {k: {"auc_ref": p[k]["auc_ref"], "auc_new": p[k]["auc_new"], "lower": p[k]["auc_gain_ci"][0],
              "holds": p[k]["auc_gain_ci"][0] >= -AUC_MARGIN} for k in ("loyo_all", "loyo_rivers")}
    cs = p["cross_site"]
    c4 = {"rho_ref": cs["rho_ref"], "rho_new": cs["rho_new"], "change": cs["change"], "lower": cs["change_ci"][0],
          "holds": cs["change_ci"][0] >= -CROSS_MARGIN}
    c5 = {"change": -p["loyo_lakes"]["brier_gain"], "upper": up("loyo_lakes"), "n": p["loyo_lakes"]["n"],
          "holds": up("loyo_lakes") <= BRIER_MARGIN}
    verdict = c1_holds and all(v["holds"] for v in c2.values()) and all(v["holds"] for v in c3.values()) \
        and c4["holds"] and c5["holds"]
    out = {"C1_information": {"holds": c1_holds, "measures": c1}, "C2_brier": c2, "C3_auc": c3,
           "C4_cross_site": c4, "C5_lakes": c5, "passes": verdict,
           "against_flow": json.loads((HERE / "paired_flow_sh.json").read_text())}
    (HERE / "judge.json").write_text(json.dumps(out, indent=1, default=float))
    for name, c in (("C1 information", out["C1_information"]), ("C2 Brier", c2), ("C3 AUC", c3),
                    ("C4 cross-site rho", c4), ("C5 lakes", c5)):
        print(name, json.dumps(c, default=lambda x: round(float(x), 5)))
    print("VERDICT:", "passes" if verdict else "fails")


if __name__ == "__main__":
    main()
