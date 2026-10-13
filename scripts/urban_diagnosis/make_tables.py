"""The diagnostic urban_km2 tables pre-stated in docs/URBAN-DILUTION-DIAGNOSIS-2026-10.md (H1, H3c, H4, H5).
Each differs from the real table only in the urban_km2 column. Writes tables/<name>.parquet and jobs_diag.txt.
    make_tables.py <overflow_urban_area.parquet>"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(os.environ["DIAG_DIR"])   # roots/, logs/, tables/ and outputs
T = HERE / "tables"
T.mkdir(exist_ok=True)
MED, LO, HI = 0.512, 0.1, 6.0

u = pd.read_parquet(sys.argv[1])
raw = u["urban_km2"].to_numpy(float)
a = np.clip(raw, LO, HI)               # as transport.urban_spill_m3s uses it
large, floor = a >= 2.0, a <= LO
print(f"{len(u)} overflows; large {large.sum()}, cap {(a >= HI).sum()}, floor {floor.sum()}")
bua, n = u["bua_km2"].to_numpy(float), u["n_in_bua"].to_numpy(float)
assigned = u["bua22cd"].notna().to_numpy()
assert np.allclose(np.where(assigned, bua / np.maximum(n, 1), LO), raw)   # the equal split rebuilds the real column


def save(name: str, col: np.ndarray) -> str:
    t = u.copy()
    t["urban_km2"] = col
    t.to_parquet(T / f"{name}.parquet", index=False)
    return f"{name} urban {T / f'{name}.parquet'}"


jobs = []
for s in range(1, 21):                                                                   # H1 placebo
    jobs.append(save(f"perm{s:02d}", np.random.default_rng(s).permutation(raw)))
v = {"cf_large_median": np.where(large, MED, a), "cf_floor_median": np.where(floor, MED, a),   # H3c
     "cf_large_only": np.where(large, a, MED), "cf_floor_only": np.where(floor, a, MED)}
for name, r in (("unsplit", np.where(assigned, bua, LO)), ("sqrt", np.where(assigned, bua / np.sqrt(np.maximum(n, 1)), LO))):
    v[name] = r * MED / np.median(r)                                                     # H4
    c = np.clip(v[name], LO, HI)
    print(f"{name}: raw median {np.median(r):.4f}; after rescale and clip: median {np.median(c):.4f}, "
          f"at cap {np.mean(c >= HI):.3f}, at floor {np.mean(c <= LO):.3f}")
v["gamma05"] = MED * (a / MED) ** 0.5                                                    # H5
for k, col in v.items():
    jobs.append(save(k, col))
(HERE / "jobs_diag.txt").write_text("\n".join(jobs) + "\n")
print(len(jobs), "jobs")
