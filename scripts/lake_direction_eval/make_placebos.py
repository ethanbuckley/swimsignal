"""The 10 placebo files of docs/LAKE-DIRECTION-TEST-2026-10.md, from report.py's output on the frozen data.

    python scripts/lake_direction_eval/make_placebos.py <report.csv> <out dir>

For every evaluation bathing water placed in a lake ("where" = eval), each row whose water enters the pin's own lake
(one per pin and entry point), with the rule's own flag: left out under lake direction "down" or not. Placebo k
(ph01.csv to ph10.csv) permutes those flags across all the rows with numpy default_rng(k): as many rows left out, at
other lakes or other overflows. Also writes flags.csv, the candidate's own.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
t = pd.read_csv(src)
t = t[(t["where"] == "eval") & t["site_id"].notna()].copy()
t = t.drop_duplicates(["pin_x", "pin_y", "entry_x", "entry_y"])
t = t[["spot", "pin_x", "pin_y", "entry_x", "entry_y", "site_id", "down_m", "dropped"]].reset_index(drop=True)
t.to_csv(out / "flags.csv", index=False)
for k in range(1, 11):
    p = t.copy()
    p["dropped"] = np.random.default_rng(k).permutation(t["dropped"].to_numpy())
    p.to_csv(out / f"ph{k:02d}.csv", index=False)
print(f"{len(t)} rows at {t.spot.nunique()} bathing waters, {int(t.dropped.sum())} left out; flags.csv and 10 placebos in {out}")
