"""Thames Water's discharge alerts from April 2022 (review task D8; docs/EARLIER-SPILL-HISTORY-2026-10.md), as
the API gives them in data/processed/thames_alerts.parquet, and as one row per discharge in
data/processed/api_events_thames_water.parquet (the edm_events columns, plus location, permit, site_id_grid,
site_id_events and id_by). Off CI, run by hand (about 1,700 requests, under an hour):

    uv run python scripts/import_thames_alerts.py [--refill]

The API sometimes answers a throttled request with no items, which looks like a day with no alerts
(thames_alerts module note). --refill asks again for every empty day of the months already cached
before reading them; run it twice, at least 30 minutes apart, and a day still empty is taken as quiet.

The API names a location by permit, name and grid reference, not by the annual returns' id. Each location
gets that id two ways, kept apart so either can be checked against the other:
- site_id_grid: the nearest Thames Water outfall in the annual returns, if within 100 m and no other
  outfall is as near. It uses no event times, so the agreement it gives with the EA's files is a test.
- site_id_events: the EA id whose 2024-2025 events start in the same minutes as the location's
  (edm_events.crosswalk_by_events, 80% both ways). Agreement measured through it is partly built in.
site_id is site_id_events, else site_id_grid, else "TW:" with the location; id_by says which.

Credit: thames_alerts.CREDIT. Nothing here trains or scores the model, and nothing is published.
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from dipcast import config
from dipcast.ingest.common import write_parquet
from dipcast.ingest.edm_events import COLS, crosswalk_by_events
from dipcast.ingest.thames_alerts import (
    FIRST_DAY,
    RAW_CACHE,
    alerts_to_events,
    fetch_alerts,
    refill_empty_days,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("import_thames_alerts")

GRID_M = 100.0


def by_grid(locations: pd.DataFrame, ar: pd.DataFrame) -> pd.Series:
    """location -> the nearest annual-returns outfall within GRID_M, unless a second is as near."""
    t = (ar[ar["company"] == "Thames Water"].dropna(subset=["site_id", "ngr_easting", "ngr_northing"])
         .sort_values("year").drop_duplicates("site_id", keep="last"))
    d, i = cKDTree(t[["ngr_easting", "ngr_northing"]].to_numpy()).query(locations[["x", "y"]].to_numpy(), k=2)
    ok = (d[:, 0] <= GRID_M) & (d[:, 1] > d[:, 0])
    return pd.Series(np.where(ok, t["site_id"].to_numpy()[i[:, 0]], None), index=locations["location"])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--refill", action="store_true", help="ask again for the empty days of cached months first")
    args = p.parse_args()
    if args.refill:
        today = datetime.now(UTC).date()
        y, m = FIRST_DAY.year, FIRST_DAY.month
        while date(y, m, 1) < today.replace(day=1):
            if (RAW_CACHE / f"{y}-{m:02d}.parquet").exists():
                refill_empty_days(y, m)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    al = fetch_alerts()
    write_parquet(al.drop(columns="time"), config.PROCESSED / "thames_alerts.parquet")
    ev = alerts_to_events(al)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ea = pd.read_parquet(config.PROCESSED / "ea_events_thames_water.parquet")

    locs = ev.drop_duplicates("location")[["location", "x", "y"]]
    grid = by_grid(locs, ar)
    overlap = ev[ev["event_start"].dt.year.isin([2024, 2025])].rename(columns={"location": "site_id"})
    cw = crosswalk_by_events(overlap, ea[ea["event_start"].dt.year.isin([2024, 2025])])
    by_ev = cw.dropna(subset=["to_id"]).set_index("from_id")["to_id"]
    ev["site_id_grid"] = ev["location"].map(grid)
    ev["site_id_events"] = ev["location"].map(by_ev)
    ev["id_by"] = np.where(ev["site_id_events"].notna(), "events",
                           np.where(ev["site_id_grid"].notna(), "grid", "none"))
    ev["site_id"] = ev["site_id_events"].fillna(ev["site_id_grid"]).fillna("TW:" + ev["location"])
    ev["lat"] = np.nan
    ev["lon"] = np.nan
    ev["source"] = "Thames Water alert stream"
    write_parquet(ev[[*COLS, "location", "permit", "site_id_grid", "site_id_events", "id_by"]],
                  config.PROCESSED / "api_events_thames_water.parquet")

    both = pd.DataFrame({"grid": grid, "events": locs["location"].map(by_ev).to_numpy()}, index=grid.index)
    log.info("locations %d: by events %d, by grid %d, both %d (agree %d), neither %d", len(both),
             both["events"].notna().sum(), both["grid"].notna().sum(),
             (both["events"].notna() & both["grid"].notna()).sum(), (both["events"] == both["grid"]).sum(),
             (both["events"].isna() & both["grid"].isna()).sum())
    pd.set_option("display.width", 200)
    print(al.groupby([al["time"].dt.year, "alertType"]).size().unstack(fill_value=0))
    ev["year"] = ev["event_start"].dt.year
    known = set(ar.loc[ar["company"] == "Thames Water", "site_id"].dropna())
    rows = []
    for y, d in ev.groupby("year"):
        a = ar[(ar["company"] == "Thames Water") & (ar["year"] == y)]
        rows.append({"year": int(y), "events": len(d), "no_stop": int(d["event_end"].isna().sum()),
                     "locations": d["location"].nunique(), "ids_in_returns": len(set(d["site_id"]) & known),
                     "returns_edm": int((a["has_data"] == 1).sum()) if len(a) else None,
                     "returns_spilled": int((a["spills"] > 0).sum()) if len(a) else None})
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
