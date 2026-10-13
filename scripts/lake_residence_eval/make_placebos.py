"""The residence files of docs/LAKE-RESIDENCE-TEST-2026-10.md: the candidate's (res.csv, a copy of
data/raw/lake_residence.csv) and 20 placebos (ph01.csv to ph20.csv), the same residence times permuted across the
same WFD lakes with numpy default_rng(k), k = 1..20.

    python scripts/lake_residence_eval/make_placebos.py <lake_residence.csv> <out dir>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
t = pd.read_csv(src)
t.to_csv(out / "res.csv", index=False)
for k in range(1, 21):
    p = t.copy()
    p["res_time_d"] = np.random.default_rng(k).permutation(t["res_time_d"].to_numpy())
    p.to_csv(out / f"ph{k:02d}.csv", index=False)
print(f"{len(t)} lakes; res.csv and 20 placebos in {out}")
