"""Overflows with no 2026 event (docs/NINE-COMPANY-MODEL-V2-DATA-CHECK-2026-10.md): how many, against the same count
for 2025 and that year's return; ids in the 2026 file that are in no annual return; and a preview of option B's
dead-monitor check on the reference days the state release holds so far. Prints only.

    PYTHONPATH=src uv run python scripts/nine_v2_data_check/no_event_rule.py <scratch root> <state dir> <main checkout>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT, STATE, MAIN = (Path(a) for a in sys.argv[1:4])
TZ = "Europe/London"
NINE = ["Anglian Water", "Northumbrian Water", "Severn Trent Water", "South West Water", "Southern Water",
        "Thames Water", "United Utilities", "Wessex Water", "Yorkshire Water"]
# Option B's reference period and its three conditions (docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md).
REF_START, REF_END, REF_DAYS = pd.Timestamp("2026-10-05"), pd.Timestamp("2026-11-01"), 28
STAMP_ONLY_ON_CHANGE = {"Northumbrian Water", "Southern Water"}
pd.set_option("display.width", 250)

ar = pd.read_parquet(MAIN / "data/processed/annual_returns.parquet",
                     columns=["site_id", "company", "year", "lat", "spills", "edm_operational_pct"])
ev = pd.concat(pd.read_parquet(ROOT / f"data/processed/ea_events_{c.lower().replace(' ', '_')}.parquet",
                               columns=["site_id", "event_start"]).assign(company=c) for c in NINE)
lt = ev["event_start"].dt.tz_convert(TZ)
ev["y"], ev["m"] = lt.dt.year, lt.dt.month
jan_aug = ev[ev["m"] <= 8].groupby(["site_id", "y"]).size().rename("n").reset_index()


def bucket(s: pd.Series) -> pd.Series:
    return pd.cut(s.fillna(-1), [-2, -0.5, 0.5, 9.5, 49.5, 1e9], labels=["no count", "0", "1-9", "10-49", "50+"])


def silent(year: int) -> pd.DataFrame:
    """Overflows positioned in the year before's return with no event from January to August of `year`."""
    b = ar[(ar["year"] == year - 1) & ar["lat"].notna() & ar["company"].isin(NINE)]
    x = b.merge(jan_aug[jan_aug["y"] == year][["site_id", "n"]], on="site_id", how="left")
    print(f"\n{year}: {int(x['n'].isna().sum())} of {len(x)} overflows in the {year - 1} return have no event Jan-Aug")
    return x[x["n"].isna()].assign(prev=lambda d: bucket(d["spills"]))


z25 = silent(2025)
same = ar[ar["year"] == 2025][["site_id", "spills"]].rename(columns={"spills": "sp_2025"})
z25 = z25.merge(same, on="site_id", how="left")
z25["return_2025"] = np.where(z25["sp_2025"].isna(), "no row/count", np.where(z25["sp_2025"] == 0, "0 spills", ">0 spills"))
print(pd.crosstab(z25["prev"], z25["return_2025"], margins=True))
print(pd.crosstab(z25["company"], z25["prev"], margins=True))
z26 = silent(2026)
print(pd.crosstab(z26["company"], z26["prev"], margins=True))

known = set(ar["site_id"].dropna())
e26 = ev[ev["y"] == 2026]
print("\n2026 events whose id is in no annual return:")
print(e26[~e26["site_id"].isin(known)].groupby(["company", "site_id"]).size())

cov = pd.read_parquet(STATE / "live_coverage.parquet")
# The release's newest day is still being polled, so it is left out.
cov = cov[(cov["day"] >= REF_START) & (cov["day"] <= REF_END) & (cov["day"] < cov["day"].max())]
n_days = cov["day"].nunique()
g = cov.groupby("site_id").agg(k=("n_known", "sum"), u=("n_unknown", "sum"), s=("n_stale", "sum"),
                               d=("n_known", lambda x: int((x > 0).sum())))
base = ar[(ar["year"] == 2025) & ar["lat"].notna() & (ar["edm_operational_pct"] >= 50) & ar["company"].isin(NINE)]
x = base.merge(g, left_on="site_id", right_index=True, how="left")
ok1 = (x["k"] / (x["k"] + x["u"]) >= 0.8).fillna(False)
ok2 = (x["s"] / x["k"].clip(lower=1) <= 0.2).fillna(False) | x["company"].isin(STAMP_ONLY_ON_CHANGE)
ok3 = (x["d"] >= round(20 * n_days / REF_DAYS)).fillna(False)
x["passes"] = ok1 & ok2 & ok3
print(f"\nDead-monitor check on {n_days} of {REF_DAYS} reference days "
      f"({cov['day'].min():%d %b} to {cov['day'].max():%d %b}), third condition scaled to {round(20 * n_days / REF_DAYS)} days:")
t = x.groupby("company").agg(edm_50=("site_id", "size"), in_feed=("k", lambda s: int(s.notna().sum())),
                             passes=("passes", "sum"))
t.loc["all"] = t.sum()
print(t)
