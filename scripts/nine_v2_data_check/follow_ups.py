"""Follow-ups to data_check.py (docs/NINE-COMPANY-MODEL-V2-DATA-CHECK-2026-10.md): whether the live feeds' events
missing from the EA file are in South West Water's own file, how long the missing ones are, and Thames's alert
stream against the EA file by month. Prints only.

    PYTHONPATH=src uv run python scripts/nine_v2_data_check/follow_ups.py <scratch root> <out> <main checkout>

<out> is data_check.py's output folder (it reads live_feed_events.csv).
"""
import sys
from pathlib import Path

import pandas as pd

ROOT, OUT, MAIN = (Path(a) for a in sys.argv[1:4])
TZ = "Europe/London"
pd.set_option("display.width", 250)


def local_day(t: pd.Series) -> pd.Series:
    return t.dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()


fe = pd.read_csv(OUT / "live_feed_events.csv", parse_dates=["day"])
fe["dur_min"] = (pd.to_datetime(fe["lee"], utc=True, format="ISO8601")
                 - pd.to_datetime(fe["les"], utc=True, format="ISO8601")).dt.total_seconds() / 60

# South West Water's own 2025-26 layer runs to 31 May 2026.
own = pd.read_parquet(MAIN / "data/processed/stream_events_south_west_water.parquet")
own = own.assign(day=local_day(own["event_start"]))[["site_id", "day"]].drop_duplicates().assign(in_own=1)
s = fe[(fe["company"] == "South West Water") & (fe["month"] <= 5)].merge(own, on=["site_id", "day"], how="left")
s["in_own"] = s["in_own"].fillna(0).astype(int)
print("South West Water feed events, Jan-May 2026, by EA same day and company file same day:")
print(s.groupby(["month", "ea_day", "in_own"]).size().unstack(fill_value=0))

print("\nFeed event length (minutes) by whether the EA file has an event that local day, all nine:")
print(fe.groupby("ea_day")["dur_min"].describe(percentiles=[0.25, 0.5, 0.75]).round(1))
print(fe.dropna(subset=["dur_min"]).assign(short=lambda d: d["dur_min"] < 15).groupby(["ea_day", "short"]).size().unstack())
print(fe.groupby(["company", "ea_day"])["dur_min"].agg(["size", "median", lambda x: (x < 15).mean()]).round(2).unstack())

a = pd.read_parquet(MAIN / "data/processed/api_events_thames_water.parquet")
a = a[(a["event_start"] >= "2026-01-01") & (a["event_start"] < "2026-09-01")].assign(day=lambda d: local_day(d["event_start"]))
e = pd.read_parquet(ROOT / "data/processed/ea_events_thames_water.parquet")
e = e[e["event_start"] >= "2025-12-31"].assign(day=lambda d: local_day(d["event_start"]))
a = a.merge(e[["site_id", "day"]].drop_duplicates().assign(ea=1), on=["site_id", "day"], how="left")
a["ea"] = a["ea"].fillna(0)
print("\nThames alert-stream events by month: with and without an EA event starting that local day, median hours:")
print(a.groupby([a["day"].dt.month, "ea"])["duration_h"].agg(["size", "median"]).round(2).unstack())
