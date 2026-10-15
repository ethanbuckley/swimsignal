"""Paired intervals (paired.compare) for every diagnostic variant against `urban` and against `flow`.
Writes pairs.csv in $DIAG_DIR. Brier change is new minus ref (positive = worse); AUC and rho change new minus ref."""
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import paired

HERE = Path(os.environ["DIAG_DIR"])
VARIANTS = ["urban", "cf_large_median", "cf_floor_median", "cf_large_only", "cf_floor_only", "unsplit", "sqrt", "gamma05"]
rows = []
for ref in ("flow", "urban"):
    for new in VARIANTS:
        if new == ref:
            continue
        r = paired.compare(ref, new)
        rec = {"ref": ref, "new": new}
        for k in ("loyo_all", "loyo_rivers", "loso_all", "fwd_all"):
            x = r[k]
            rec[f"{k} brier change"] = x["brier_new"] - x["brier_ref"]
            rec[f"{k} brier CI"] = f"[{-x['brier_gain_ci'][1]:+.4f}, {-x['brier_gain_ci'][0]:+.4f}]"
            rec[f"{k} auc change"] = x["auc_new"] - x["auc_ref"]
            rec[f"{k} auc CI"] = f"[{x['auc_gain_ci'][0]:+.4f}, {x['auc_gain_ci'][1]:+.4f}]"
        c = r["cross_site"]
        rec["rho change"] = c["change"]
        rec["rho CI"] = f"[{c['change_ci'][0]:+.3f}, {c['change_ci'][1]:+.3f}]"
        rows.append(rec)
        print(ref, new, flush=True)
df = pd.DataFrame(rows)
df.to_csv(HERE / "pairs.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 50)
print(df.round(4).to_string())
