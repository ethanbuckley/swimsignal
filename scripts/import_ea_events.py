"""Write one parquet of discharges per company, data/processed/ea_events_<company>.parquet (the
edm_events columns), from the Environment Agency's start/stop files for the companies that operate
in England, 2024 and 2025 by default. The test it feeds is stated in docs/NINE-COMPANY-MODEL-TEST-2026-10.md.
Off CI, run by hand:

    uv run python scripts/import_ea_events.py [--years 2024 2025] [--refresh]

The EA publishes the files as one zip per year ("2025 Detailed EDM Start-Stop Data.zip"). The zips
are kept in data/raw/ea_events/; any year missing there is found in the dataset page's file list
and downloaded through the EA platform's signed-link route (edm_events.ea_yearly_zips). --refresh
reads the list and downloads the zips again, for a revised file or a year-to-date zip that has
grown. Each company's files are read straight from the zips. Dwr Cymru Welsh Water's files stay
with scripts/import_ea_welsh_water.py and dcww_ea_events.parquet: a test set, never training.

Then it prints, per company and year, the measured signs of how each company defines an event (the
DSP note gives one definition for all): events, overflows, the share of ids in the annual returns,
the median event length, the share under 15 minutes, and the median gap from one event's stop to
the next start at the same overflow.

Contains Environment Agency data: © Environment Agency copyright and/or database right, licensed
under the Open Government Licence v3.0.
"""

from __future__ import annotations

import argparse
import logging
import re

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.common import write_parquet
from dipcast.ingest.edm_events import EA_TEST_ONLY, ea_yearly_zips, ea_zip_members, read_ea_events

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("import_ea_events")

RAW = config.RAW / "ea_events"
YEARS = [2024, 2025]   # the years the nine-company test was stated on


def slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")


def events_path(company: str):
    return config.PROCESSED / f"ea_events_{slug(company)}.parquet"


def company_files(years, refresh: bool = False) -> dict[str, list]:
    """Company -> its (zip, member) files for `years`, Dwr Cymru Welsh Water left out."""
    by_company: dict[str, list] = {}
    for _, zp in sorted(ea_yearly_zips(years, RAW, refresh=refresh).items()):
        for company, members in ea_zip_members(zp).items():
            if company not in EA_TEST_ONLY:
                by_company.setdefault(company, []).extend(members)
    return by_company


def event_signs(ev: pd.DataFrame) -> dict:
    """Per-file measures that would show a company-specific event definition."""
    d = ev.sort_values(["site_id", "event_start"])
    gap = (d["event_start"] - d.groupby("site_id")["event_end"].shift()).dt.total_seconds() / 60
    return {"events": len(d), "overflows": d["site_id"].nunique(),
            "no_end": int(d["event_end"].isna().sum()),
            "median_h": float(d["duration_h"].median()),
            "under_15min": float((d["duration_h"] < 0.25).mean()),
            "median_gap_min": float(gap.median()),
            "gap_under_15min": float((gap < 15).mean())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--years", type=int, nargs="+", default=YEARS)
    ap.add_argument("--refresh", action="store_true", help="download the listed zips again")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet", columns=["site_id", "company", "year"])
    rows = []
    for company, files in sorted(company_files(args.years, args.refresh).items()):
        ev = read_ea_events(files)
        write_parquet(ev, events_path(company))
        known = set(ar.loc[ar["company"] == company, "site_id"].dropna())
        ev["year"] = ev["event_start"].dt.year
        for y, d in ev.groupby("year"):
            if len(d) < 50:   # a few events dated outside the file's year
                continue
            ids = set(d["site_id"])
            rows.append({"company": company, "year": int(y), **event_signs(d),
                         "ids_in_returns": len(ids & known) / len(ids),
                         "positioned": float(d["lat"].notna().mean())})
        outside = ev[~ev["year"].isin(args.years)]
        log.info("%s: %d events, %d dated outside %s", company, len(ev), len(outside), args.years)
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(t.round(3).to_string(index=False))
    (config.PROCESSED / "ea_events_summary.csv").write_text(t.round(4).to_csv(index=False))


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
