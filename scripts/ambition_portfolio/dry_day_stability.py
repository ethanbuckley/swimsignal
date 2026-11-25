"""Development check, SEEN river rows only: is a river's dry-day level stable from one pair of seasons to the next?
Dry day: under 2 mm in the 48 h before the sample. Never opens heldout.parquet."""
import sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
d = pd.read_parquet(sys.argv[1]); assert set(d.part)=={"seen"}
r = d[(d.kind=="river")&(d.rain_48h<2)]
a = r[r.season<=2024].groupby("name").log_ecoli.agg(["median","count"]); b = r[r.season>=2025].groupby("name").log_ecoli.agg(["median","count"])
j = a.add_suffix("_early").join(b.add_suffix("_late"), how="inner"); j = j[(j.count_early>=8)&(j.count_late>=8)]
print("sites with 8+ dry-day samples in both halves:", len(j))
rho = spearmanr(j.median_early, j.median_late)[0]
rng = np.random.default_rng(20261115); bs=[]
for _ in range(4000):
    k = j.sample(len(j), replace=True, random_state=int(rng.integers(1e9)))
    if k.median_early.nunique()>2:
        bs.append(spearmanr(k.median_early,k.median_late)[0])
print(f"Spearman across sites, 2023-24 dry-day median vs 2025-26: {rho:.2f}  95% {np.round(np.nanpercentile(bs,[2.5,97.5]),2)}")
print("median absolute change, as a ratio:", round(10**np.median(np.abs(j.median_early-j.median_late)),2))
j["early"]=(10**j.median_early).round(0); j["late"]=(10**j.median_late).round(0)
print(j[["early","count_early","late","count_late"]].sort_values("late",ascending=False).to_string())
allr = d[d.kind=="river"]
wet = allr[allr.rain_48h>10].groupby("name").ecoli.agg(["median","count"]); dry = r.groupby("name").ecoli.agg(["median","count"])
k = dry.add_suffix("_dry").join(wet.add_suffix("_wet")); print("\nriver sites with 5+ samples in both groups (>10 mm, <2 mm):", ((k.count_dry>=5)&(k.count_wet>=5)).sum(), "of", len(k))
print(k.sort_values("median_dry",ascending=False).head(8).to_string())
cam = r[r.name.str.contains("Cam")].groupby("season").ecoli.agg(n="count", middle="median", over_900=lambda s: (s > 900).sum())
print("\nSheep's Green, River Cam, dry-day samples by season:")
print(cam.to_string())
