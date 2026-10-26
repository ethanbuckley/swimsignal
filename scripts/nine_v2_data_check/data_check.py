"""The data check of docs/NINE-COMPANY-MODEL-V2-DATA-CHECK-2026-10.md: the EA start/stop events per company and
month for 2024-26, the live feeds and the company files against the EA file, and rain per month. Counts only; no
model, no forecast, no Open-Meteo call.

    PYTHONPATH=src uv run python scripts/nine_v2_data_check/data_check.py <scratch root> <state dir> <main checkout> <out>

<scratch root> is the DIPCAST_ROOT that import_ea_events.py --years 2024 2025 2026 wrote to; <state dir> holds
live_history.parquet from the state release; <main checkout> holds data/processed and data/cache.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast.ingest.rainfall import cell_key, grid_cell

ROOT, STATE, MAIN, OUT = (Path(a) for a in sys.argv[1:5])
OUT.mkdir(parents=True, exist_ok=True)
TZ = "Europe/London"
NINE = ["Anglian Water", "Northumbrian Water", "Severn Trent Water", "South West Water", "Southern Water",
        "Thames Water", "United Utilities", "Wessex Water", "Yorkshire Water"]


def slug(c):
    return c.lower().replace(" ", "_")


def local_days(ev):
    """(site_id, day) for every UK local day an event touches."""
    s = ev["event_start"].dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
    e = ev["event_end"].fillna(ev["event_start"]).dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
    n = ((e - s).dt.days + 1).clip(lower=1).to_numpy()
    sid = np.repeat(ev["site_id"].to_numpy(), n)
    off = np.concatenate([np.arange(k) for k in n]) if len(n) else np.array([], int)
    day = np.repeat(s.to_numpy(), n) + off.astype("timedelta64[D]")
    return pd.DataFrame({"site_id": sid, "day": day}).drop_duplicates()


ar = pd.read_parquet(MAIN / "data/processed/annual_returns.parquet",
                     columns=["site_id", "company", "year", "lat", "edm_operational_pct", "spills"])
known_any = set(ar["site_id"].dropna())

ev_all, sd_all, rows, last = [], [], [], []
for c in NINE:
    ev = pd.read_parquet(ROOT / f"data/processed/ea_events_{slug(c)}.parquet")
    ev["company"] = c
    ev["lstart"] = ev["event_start"].dt.tz_convert(TZ)
    ev["year"] = ev["lstart"].dt.year
    ev["month"] = ev["lstart"].dt.month
    sd = local_days(ev)
    sd["company"] = c
    sd["year"] = sd["day"].dt.year
    sd["month"] = sd["day"].dt.month
    sd = sd[sd["year"].isin([2024, 2025, 2026])]
    for y in (2024, 2025, 2026):
        e = ev[ev["year"] == y]
        last.append({"company": c, "year": y, "first_start": e["lstart"].min(), "last_start": e["lstart"].max(),
                     "events": len(e), "ids": e["site_id"].nunique(),
                     "events_id_not_in_any_return": int((~e["site_id"].isin(known_any)).sum()),
                     "ids_not_in_any_return": e.loc[~e["site_id"].isin(known_any), "site_id"].nunique(),
                     "events_id_TBC": int(e["site_id"].str.upper().str.contains("TBC").sum()),
                     "events_no_position": int(e["lat"].isna().sum())})
    g_ev = ev.groupby(["year", "month"]).agg(events=("site_id", "size"), overflows=("site_id", "nunique"),
                                             median_min=("duration_h", lambda s: 60 * s.median()))
    g_sd = sd.groupby(["year", "month"]).agg(spill_days=("site_id", "size"))
    g = g_ev.join(g_sd, how="outer").reset_index()
    g["company"] = c
    rows.append(g)
    ev_all.append(ev[["company", "site_id", "event_start", "event_end", "year", "month"]])
    sd_all.append(sd)

monthly = pd.concat(rows)
monthly = monthly[monthly["year"].isin([2024, 2025, 2026])]
monthly.to_csv(OUT / "monthly.csv", index=False)
pd.DataFrame(last).to_csv(OUT / "years.csv", index=False)
ev_all = pd.concat(ev_all)
sd_all = pd.concat(sd_all)

# Reporting overflows: of the overflows positioned in the year before's return (the covariates), the share with
# at least one event in each month, Jan-Aug, by year.
rep = []
for y in (2024, 2025, 2026):
    base = ar[(ar["year"] == y - 1) & ar["lat"].notna() & ar["company"].isin(NINE)][["site_id", "company"]]
    s = sd_all[(sd_all["year"] == y)].merge(base, on=["site_id", "company"])
    for c, b in base.groupby("company"):
        sc = s[s["company"] == c]
        r = {"company": c, "year": y, "positioned": len(b),
             "any_event_jan_aug": sc.loc[sc["month"] <= 8, "site_id"].nunique()}
        for m in range(1, 13):
            r[f"m{m:02d}"] = sc.loc[sc["month"] == m, "site_id"].nunique()
        rep.append(r)
pd.DataFrame(rep).to_csv(OUT / "reporting.csv", index=False)

# Live feed check: every (overflow, latest event) the polls have shown with a start in Jan-Aug 2026. The EA file
# should hold an event touching the same UK local start day. Matched also to the minute.
lh = pd.read_parquet(STATE / "live_history.parquet")
lh["les"] = pd.to_datetime(lh["latest_event_start"], utc=True)
lh["lee"] = pd.to_datetime(lh["latest_event_end"], utc=True)
fe = lh[(lh["les"] >= "2026-01-01") & (lh["les"] < pd.Timestamp("2026-09-01", tz=TZ))]
fe = fe.drop_duplicates(["site_id", "les"])[["company", "site_id", "les", "lee"]]
fe["day"] = fe["les"].dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
fe["month"] = fe["day"].dt.month
ea26 = ev_all[ev_all["year"] == 2026]
sd26 = sd_all[sd_all["year"] == 2026][["site_id", "day"]].assign(ea_day=1)
fe = fe.merge(sd26, on=["site_id", "day"], how="left")
fe["ea_day"] = fe["ea_day"].fillna(0).astype(int)
exact = ea26.assign(k=1)[["site_id", "event_start", "k"]].rename(columns={"event_start": "les"})
exact["les"] = exact["les"].dt.floor("min")
fe["les_min"] = fe["les"].dt.floor("min")
fe = fe.merge(exact.rename(columns={"les": "les_min"}).drop_duplicates(), on=["site_id", "les_min"], how="left")
fe["exact"] = fe["k"].fillna(0).astype(int)
fe["site_has_ea26"] = fe["site_id"].isin(set(ea26["site_id"])).astype(int)
fe.drop(columns=["k"]).to_csv(OUT / "live_feed_events.csv", index=False)
lf = fe.groupby(["company", "month"]).agg(feed_events=("site_id", "size"), ea_same_day=("ea_day", "sum"),
                                         ea_exact_start=("exact", "sum"),
                                         site_has_no_ea26=("site_has_ea26", lambda s: int((s == 0).sum())))
lf["share_same_day"] = lf["ea_same_day"] / lf["feed_events"]
lf.reset_index().to_csv(OUT / "live_feed_by_month.csv", index=False)

# The company feeds SwimSignal holds for 2026: Thames's alert stream and South West Water's 2025-26 file. Spill-days
# by UK local day against the EA file, per month.
cmp = []
for c, f in [("Thames Water", "api_events_thames_water"), ("South West Water", "stream_events_south_west_water")]:
    o = pd.read_parquet(MAIN / f"data/processed/{f}.parquet")
    o = o[(o["event_start"] >= pd.Timestamp("2025-12-01", tz="UTC"))]
    od = local_days(o)
    od = od[(od["day"] >= "2026-01-01") & (od["day"] < "2026-09-01")].assign(own=1)
    last_own = o["event_start"].max()
    ed = sd_all[(sd_all["company"] == c) & (sd_all["year"] == 2026)][["site_id", "day"]].assign(ea=1)
    m = od.merge(ed, on=["site_id", "day"], how="outer")
    m = m[m["day"] <= last_own.tz_convert(TZ).tz_localize(None).normalize()]
    m["month"] = m["day"].dt.month
    m = m.fillna(0)
    t = m.groupby("month").agg(both=("own", lambda s: int(((s == 1) & (m.loc[s.index, "ea"] == 1)).sum())),
                               own_only=("own", lambda s: int(((s == 1) & (m.loc[s.index, "ea"] == 0)).sum())),
                               ea_only=("ea", lambda s: int(((s == 1) & (m.loc[s.index, "own"] == 0)).sum())))
    t["company"] = c
    t["own_last_event"] = str(last_own)
    cmp.append(t.reset_index())
pd.concat(cmp).to_csv(OUT / "own_feeds_vs_ea.csv", index=False)

# Rain context. ERA5-Land monthly totals (mm, mean over cells) on the cells that hold 2026 in the shared cache, by
# company, 2024-26; radar monthly totals on the radar cells, 2025-26. UTC months. Context only.

pos = ar[ar["company"].isin(NINE) & ar["lat"].notna() & (ar["year"] == 2025)]
lon = pd.read_parquet(MAIN / "data/processed/annual_returns.parquet", columns=["site_id", "year", "lon"])
pos = pos.merge(lon[lon["year"] == 2025][["site_id", "lon"]], on="site_id")
cl, cn = grid_cell(pos["lat"].to_numpy(), pos["lon"].to_numpy())
pos["cell"] = [cell_key(a, b) for a, b in zip(cl, cn)]
cc = pos[["company", "cell"]].drop_duplicates()
rain = []
for c, cells in cc.groupby("company")["cell"]:
    for y in (2024, 2025, 2026):
        fs = [f for k in cells for f in (MAIN / f"data/cache/rain/archive_{k}_{y}.parquet",
                                          MAIN / f"data/cache/rain_nine/archive_{k}_{y}.parquet") if f.exists()]
        have26 = [k for k in cells if (MAIN / f"data/cache/rain/archive_{k}_2026.parquet").exists()]
        fs = [f for f in fs if any(k in f.name for k in have26)]
        if fs:
            d = pd.concat(pd.read_parquet(f) for f in fs)
            d["month"] = pd.to_datetime(d["time"]).dt.month
            per = d.groupby(["cell_lat", "cell_lon", "month"])["precip_mm"].sum().groupby("month").mean()
            for m, v in per.items():
                rain.append({"company": c, "source": "era5", "year": y, "month": m, "mm": v, "cells": len(have26)})
    rc = [k for k in cells if (MAIN / f"data/raw/met_office_radar/radar_{k}_2026-01.parquet").exists()]
    for y in (2025, 2026):
        fs = [MAIN / f"data/raw/met_office_radar/radar_{k}_{y}-{m:02d}.parquet" for k in rc for m in range(1, 9)]
        fs = [f for f in fs if f.exists()]
        if fs:
            d = pd.concat(pd.read_parquet(f) for f in fs)
            d = d[d["coverage"] >= 0.9]
            d["month"] = d["time"].dt.month
            per = d.groupby(["cell_lat", "cell_lon", "month"])["radar_mm"].sum().groupby("month").mean()
            for m, v in per.items():
                rain.append({"company": c, "source": "radar", "year": y, "month": m, "mm": v, "cells": len(rc)})
rain = pd.DataFrame(rain)
# The radar is CC BY-SA 4.0 and is published as summary figures only, so it goes to its own file, not the docs.
rain[rain["source"] == "era5"].to_csv(OUT / "rain.csv", index=False)
rain[rain["source"] == "radar"].to_csv(OUT / "rain_radar.csv", index=False)
print("done", OUT)
