"""Applies the pre-stated rules of docs/URBAN-DILUTION-DIAGNOSIS-2026-10.md to summary.csv (H1, H3c, H4, H5)."""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(os.environ["DIAG_DIR"])   # roots/, logs/, tables/ and outputs
s = pd.read_csv(HERE / "summary.csv", index_col=0)
M = {"loyo_brier": -1, "loyo_auc": 1, "loyo_auc_rivers": 1, "cross_site_rho": 1}   # sign: +1 higher is better
out = {}
perm = s[s.index.str.startswith("perm")]
out["placebos run"] = len(perm)
h1 = {}
for m, sign in M.items():
    real, pv, flow = s.loc["urban", m], perm[m].to_numpy(), s.loc["flow", m]
    k = int(np.sum(sign * pv <= sign * real))   # placebos at least as bad as the real urban
    h1[m] = {"real_urban": real, "flow": flow, "placebo_median": float(np.median(pv)), "placebo_min": float(pv.min()),
             "placebo_max": float(pv.max()), "k_placebos_at_least_as_bad": k,
             "placebos_worse_than_flow": int(np.sum(sign * pv < sign * flow))}
out["H1"] = h1
ks = [h1[m]["k_placebos_at_least_as_bad"] for m in M]
out["H1 verdict"] = ("proxy carries wrong information" if sum(k <= 1 for k in ks) >= 3 else
                     "proxy carries some right information" if sum(k >= 19 for k in ks) >= 3 else
                     "real A_i no worse than a random spread (formula sensitivity to any spread)")


def frac_gap(v):
    """Share of the urban - flow gap that variant v recovers (1 = back to flow, 0 = same as urban), per measure."""
    return {m: float((s.loc[v, m] - s.loc["urban", m]) / (s.loc["flow", m] - s.loc["urban", m])) for m in M}


h3 = {}
for g in ("large", "floor"):
    rec, keep = frac_gap(f"cf_{g}_median"), frac_gap(f"cf_{g}_only")
    reproduced = {m: 1 - keep[m] for m in M}                  # share of the gap reproduced when only g keeps its spread
    drives = sum(rec[m] >= 0.5 for m in M) >= 3 and sum(reproduced[m] >= 0.5 for m in M) >= 3
    h3[g] = {"set_to_median_recovers": rec, "only_group_spread_reproduces": reproduced, "drives_damage": drives}
out["H3c"] = h3
out["H4"] = {v: {m: float(s.loc[v, m]) for m in M} | {"better_than_urban_on": int(sum(M[m] * s.loc[v, m] > M[m] * s.loc["urban", m] for m in M))}
             for v in ("unsplit", "sqrt")}
out["H5 gamma05"] = {m: float(s.loc["gamma05", m]) for m in M} | {
    "between_flow_and_urban_on": int(sum(min(s.loc["flow", m], s.loc["urban", m]) <= s.loc["gamma05", m] <= max(s.loc["flow", m], s.loc["urban", m]) for m in M)),
    "better_than_flow_on": int(sum(M[m] * s.loc["gamma05", m] > M[m] * s.loc["flow", m] for m in M))}
print(json.dumps(out, indent=1, default=float))
(HERE / "judge.json").write_text(json.dumps(out, indent=1, default=float))
