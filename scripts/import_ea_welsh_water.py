"""Write data/processed/dcww_ea_events.parquet (one row per discharge, the edm_events columns) from
the Environment Agency's start/stop files for Dwr Cymru Welsh Water's overflows in England. The
files are under the Open Government Licence (docs/WALES-PLAN-2026-10.md, section 2.2), so the
hindcast (scripts/hindcast_wales.py, set A2) can use them.
Nothing here reaches the site. Off CI, run by hand:

    uv run python scripts/import_ea_welsh_water.py [--years 2024 2025 2026] [--refresh]

The EA publishes the files as one zip per year, shared with scripts/import_ea_events.py and kept in
data/raw/ea_events/. Any year missing there is found in the dataset page's file list and downloaded
through the EA platform's signed-link route (edm_events.ea_yearly_zips); --refresh downloads them
again. Only the Welsh Water member of each zip is read.

Contains Environment Agency data: © Environment Agency copyright and/or database right, licensed
under the Open Government Licence v3.0.
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd

from dipcast import config
from dipcast.ingest.common import write_parquet
from dipcast.ingest.edm_events import ea_yearly_zips, ea_zip_members, read_ea_dcww_events

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("import_ea_welsh_water")

RAW = config.RAW / "ea_events"
YEARS = [2024, 2025, 2026]
WELSH = "Dwr Cymru Welsh Water"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--years", type=int, nargs="+", default=YEARS)
    ap.add_argument("--refresh", action="store_true", help="download the listed zips again")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    files = []
    for year, zp in sorted(ea_yearly_zips(args.years, RAW, refresh=args.refresh).items()):
        members = ea_zip_members(zp).get(WELSH, [])
        if not members:
            raise SystemExit(f"{zp.name} holds no Welsh Water file ({year})")
        files.extend(members)
    ev = read_ea_dcww_events(files)
    write_parquet(ev, config.PROCESSED / "dcww_ea_events.parquet")

    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet", columns=["site_id", "company", "year"])
    dcww = set(ar.loc[ar["company"].str.contains("Cymru", na=False), "site_id"].dropna())
    ev["year"] = ev["event_start"].dt.year
    by_year = ev.groupby("year").agg(events=("site_id", "size"), overflows=("site_id", "nunique"),
                                     first=("event_start", "min"), last=("event_start", "max"))
    print(by_year.to_string())
    ids = set(ev["site_id"])
    print(f"\n{len(ev)} events at {len(ids)} overflows; {len(ids & dcww)} ids are Dwr Cymru rows in "
          f"annual_returns.parquet; {int(ev['lat'].isna().sum())} events have no position; "
          f"{int(ev['event_end'].isna().sum())} have no end.")


if __name__ == "__main__":
    main()
