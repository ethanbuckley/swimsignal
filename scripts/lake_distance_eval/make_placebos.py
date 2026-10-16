"""The 20 placebo files of docs/LAKE-DISTANCE-2026-10.md, from report.py's output on the frozen data.

    python scripts/lake_distance_eval/make_placebos.py <report.csv> <out dir>

For every evaluation bathing water placed in a lake ("where" = eval), each overflow's ratio of the through-water
distance to the straight line (one row per pin and overflow id, the first where an id appears twice). Placebo k
(ph01.csv to ph20.csv) permutes those ratios across all the rows with numpy default_rng(k): the same detours, given to
other overflows at other lakes. Also writes ratios.csv, the candidate's own.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
t = pd.read_csv(src)
t = t[(t["where"] == "eval") & t["site_id"].notna()].copy()
t["ratio"] = t["lake_distance_m_water"] / t["lake_distance_m_line"]
t = t.drop_duplicates(["pin_x", "pin_y", "site_id"])[["spot", "pin_x", "pin_y", "site_id", "ratio"]].reset_index(drop=True)
t.to_csv(out / "ratios.csv", index=False)
for k in range(1, 21):
    p = t.copy()
    p["ratio"] = np.random.default_rng(k).permutation(t["ratio"].to_numpy())
    p.to_csv(out / f"ph{k:02d}.csv", index=False)
print(f"{len(t)} rows at {t.spot.nunique()} bathing waters, {int((t.ratio > 1).sum())} with a detour; "
      f"ratios.csv and 20 placebos in {out}")
