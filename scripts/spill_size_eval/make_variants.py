"""The size tables of docs/SPILL-SIZE-TEST-2026-10.md, from the annual returns and the overflow table only.

    python scripts/spill_size_eval/make_variants.py <annual_returns.parquet> <overflows.parquet> <out dir>

Writes <out dir>/sh.parquet and ph01.parquet .. ph20.parquet, each with site_id and urban_km2, the column
transport's dilution "urban" reads (overflow_urban_area.parquet). An overflow's size is its mean annual spill
hours over 2021-2025 (years with a value) over the median of that mean, times URBAN_MEDIAN_KM2, so the
median overflow spills as in "flow" and transport.urban_spill_m3s clips as it does for the urban areas.
An overflow with no spill hours is left out of the table and so takes the median. ph<k> permutes the sizes
across the same overflows with numpy default_rng(k)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

URBAN_MEDIAN_KM2 = 0.512   # transport.URBAN_MEDIAN_KM2
YEARS = (2021, 2025)
PLACEBOS = 20

ar, ov, out = pd.read_parquet(sys.argv[1]), pd.read_parquet(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
a = ar[ar["year"].between(*YEARS)].dropna(subset=["spill_hours"])
sh = a.groupby("site_id")["spill_hours"].mean().reindex(ov["site_id"].drop_duplicates()).dropna()
size = URBAN_MEDIAN_KM2 * sh / float(sh.median())
t = pd.DataFrame({"site_id": size.index, "urban_km2": size.to_numpy()})
t.to_parquet(out / "sh.parquet", index=False)
for k in range(1, PLACEBOS + 1):
    t.assign(urban_km2=np.random.default_rng(k).permutation(t["urban_km2"].to_numpy())).to_parquet(out / f"ph{k:02d}.parquet", index=False)
print(f"{len(t)} overflows with spill hours of {ov['site_id'].nunique()}; median {sh.median():.1f} h a year; {PLACEBOS} placebos")
