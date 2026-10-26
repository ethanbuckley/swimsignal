"""Each overflow's spill-days in dry weather in one year: data/raw/dry_weather_spills.csv, read by the build
(build_site.attach_dry_weather), which notes on a spot's page an overflow that spilled on many of its dry days.

    uv run python scripts/make_dry_weather_spills.py --year 2025

Off CI, by hand: once a year, when the Environment Agency's start/stop file for a whole year is out for all nine
companies (scripts/import_ea_events.py) and ERA5-Land rain for the year is in the cache (scripts/fetch_rain_nine.py).
It needs data/processed/ea_events_*.parquet and annual_returns.parquet, and the rain in data/cache/rain and
data/cache/rain_nine; it fetches nothing. The build reads only the CSV, and has neither the event files nor the rain.

The rule is the one stated and run in docs/DRY-WEATHER-SPILLS-TEST-2026-10.md (dipcast.dry_weather), on the same
rows: the overflows that test kept for the year (training.site_years) and their days with known rain. Every overflow
with at least one dry spill-day is written; the build applies the note's rule (dry_weather.noted), so the rule lives
in one place. For 2025 the file equals that test's -overflows.csv rows for 2025, which tests/test_dry_weather.py
checks.

Sources: "Event Duration Monitoring - Storm Overflow - Start/Stop Detailed Data", Environment Agency,
https://environment.data.gov.uk/dataset/e9677ac1-fd32-4ceb-88a0-2735be5f27c7, Open Government Licence v3.0,
© Environment Agency copyright and/or database right; not formally verified by the Environment Agency. ERA5-Land
hourly rain via Open-Meteo, CC BY 4.0, contains modified Copernicus Climate Change Service information.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.dry_weather import classify, dry_started_days, merge_overlaps, overflow_counts
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features, spill_days
from dipcast.model.training import NINE, cells_of, load_events, load_rain, site_years

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("make_dry_weather_spills")

OUT = config.RAW / "dry_weather_spills.csv"
HEADER = """# Each overflow's spill-days in dry weather in {year}, for the note beside it on a spot's page.
# Made by scripts/make_dry_weather_spills.py on {made}; read only by scripts/build_site.py (attach_dry_weather).
# The spill model never reads this file. Rule: docs/DRY-WEATHER-SPILLS-TEST-2026-10.md and dipcast.dry_weather.
# dry_days: UTC days with under 0.25 mm of ERA5-Land rain in the overflow's cell on the day and the two before,
# less days with a spill only from events that started on wet days. dry_spill_days: those of them on which an
# event that started on a dry day spilled. Only overflows with at least one dry spill-day are listed.
# Contains Environment Agency data: Event Duration Monitoring - Storm Overflow - Start/Stop Detailed Data,
# © Environment Agency copyright and/or database right, Open Government Licence v3.0; not formally verified by the
# Environment Agency. Rain: ERA5-Land via Open-Meteo (CC BY 4.0); contains modified Copernicus Climate Change
# Service information.
"""


def counts_for(year: int) -> pd.DataFrame:
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    sites, _ = site_years(ar, ev, NINE, year)
    rain = load_rain(cells_of(sites), tags=(str(year - 1), f"{year - 1}dec", str(year)), start=f"{year - 1}-12-01")
    daily = daily_rain_features(rain)
    del rain
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D", tz="UTC")
    labels = spill_days(ev)
    frame = build_site_days(sites, daily, days, labels[labels["day"].dt.year == year])
    frame = frame[frame["rain_d"].notna()].copy()   # the spill model's rows: a day with unknown rain is not counted
    frame = frame.astype({f: np.float32 for f in ALL_FEATURES})   # as scripts/train.py's rows hold them, so a day at
    # 0.25 mm falls on the same side of the threshold as in the test
    frame["company"] = frame["site_id"].map(dict(zip(sites["site_id"], sites["company"], strict=True)))
    cl, cn = grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy())
    cell_of = pd.DataFrame({"site_id": sites["site_id"].to_numpy(), "cell_lat": cl, "cell_lon": cn})
    touched = dry_started_days(merge_overlaps(ev), cell_of, daily)
    c = overflow_counts(frame, classify(frame, touched))
    log.info("%d: %d overflows, %d site-days, %d dry spill-days", year, len(c), len(frame), int(c["k"].sum()))
    return c


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--year", type=int, required=True)
    year = ap.parse_args().year
    c = counts_for(year)
    c = c[c["k"] >= 1].sort_values("site_id")
    out = pd.DataFrame({"site_id": c["site_id"], "company": c["company"], "year": year,
                        "dry_spill_days": c["k"].astype(int), "dry_days": c["n"].astype(int)})
    OUT.write_text(HEADER.format(year=year, made=date.today().isoformat()) + out.to_csv(index=False))
    log.info("wrote %d overflows -> %s", len(out), OUT)


if __name__ == "__main__":
    main()
