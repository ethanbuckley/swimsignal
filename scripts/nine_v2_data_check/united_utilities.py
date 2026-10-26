"""United Utilities' 2026 record against 2024 and 2025 (docs/NINE-COMPANY-MODEL-V2-DATA-CHECK-2026-10.md): the share
of overflows reporting per month, the shape of its events, and January day by day beside the radar rain on its
cells. Prints only.

    PYTHONPATH=src uv run python scripts/nine_v2_data_check/united_utilities.py <scratch root> <out> <main checkout>
"""
import sys
from pathlib import Path

import pandas as pd

from dipcast.ingest.rainfall import cell_key, grid_cell

ROOT, OUT, MAIN = (Path(a) for a in sys.argv[1:4])
TZ = "Europe/London"
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)

r = pd.read_csv(OUT / "reporting.csv")
r["share_jan_aug"] = (r["any_event_jan_aug"] / r["positioned"]).round(3)
print(r[["company", "year", "positioned", "any_event_jan_aug", "share_jan_aug", *[f"m{m:02d}" for m in range(1, 9)]]]
      .to_string(index=False))

e = pd.read_parquet(ROOT / "data/processed/ea_events_united_utilities.parquet").sort_values(["site_id", "event_start"])
lt = e["event_start"].dt.tz_convert(TZ)
e["y"], e["m"], e["day"] = lt.dt.year, lt.dt.month, lt.dt.tz_localize(None).dt.normalize()
e["gap"] = (e["event_start"] - e.groupby("site_id")["event_end"].shift()).dt.total_seconds() / 60
print("\nUnited Utilities by month: events, median length (min), median gap (min), share of gaps under 60 min")
print(e[e["m"] <= 8].groupby(["y", "m"]).agg(
    ev=("site_id", "size"), dur=("duration_h", lambda s: round(60 * s.median(), 1)), gap=("gap", "median"),
    g60=("gap", lambda s: round((s < 60).mean(), 3))).unstack(0).to_string())

ar = pd.read_parquet(MAIN / "data/processed/annual_returns.parquet", columns=["company", "year", "lat", "lon"])
a = ar[(ar["company"] == "United Utilities") & (ar["year"] == 2025) & ar["lat"].notna()]
cells = {cell_key(x, y) for x, y in zip(*grid_cell(a["lat"].to_numpy(), a["lon"].to_numpy()))}
radar = MAIN / "data/raw/met_office_radar"
files = [radar / f"radar_{k}_{y}-01.parquet" for k in cells for y in (2025, 2026)]
rd = pd.concat(pd.read_parquet(f) for f in files if f.exists())
rd = rd[rd["coverage"] >= 0.9]
rd["day"] = rd["time"].dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
rain = rd.groupby(["cell_lat", "cell_lon", "day"])["radar_mm"].sum().groupby("day").mean()
spilling = e.groupby("day")["site_id"].nunique()
for y in (2025, 2026):
    idx = pd.date_range(f"{y}-01-01", f"{y}-01-31")
    print(f"\nJanuary {y}: overflows spilling, radar mm (mean over United Utilities cells)")
    print(pd.DataFrame({"spilling": spilling.reindex(idx).fillna(0).astype(int),
                        "radar_mm": rain.reindex(idx).round(1)}).T.to_string())
