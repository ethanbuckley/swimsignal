"""Write data/processed/dcww_ea_events.parquet (one row per discharge, the edm_events columns) from
the Environment Agency's start/stop files for Dwr Cymru Welsh Water's overflows in England. Wales
plan task W3, corrected 4 Oct 2026 (docs/WALES-PLAN-2026-10.md, section 2.2): the files are under
the Open Government Licence, so the hindcast (scripts/hindcast_wales.py, set A2) can use them.
Nothing here reaches the site. Off CI, run by hand:

    uv run python scripts/import_ea_welsh_water.py

It reads the three workbooks from data/raw/ea_welsh_water/. If they are missing, it downloads them
through the EA platform's own route (a download-url request that returns a signed link), as the
dataset page's Download buttons do. The page's older file links, on api.agrimetrics.co.uk, did not
resolve on 4 Oct 2026.

Contains Environment Agency data: © Environment Agency copyright and/or database right, licensed
under the Open Government Licence v3.0.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx
import pandas as pd

from dipcast import config
from dipcast.ingest.common import write_parquet
from dipcast.ingest.edm_events import read_ea_dcww_events

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("import_ea_welsh_water")

FILES = ["Welsh 2024 Detailed EDM Data.xlsx", "Welsh Water 2025 Detailed EDM Data.xlsx",
         "Welsh Water Detailed Data 2026.xlsx"]
FILE_API = ("https://environment.data.gov.uk/file-management-open/data-sets/"
            "c95ecc47-fa70-4a24-b8cc-098232987526/files/{name}/download-url")
RAW = config.RAW / "ea_welsh_water"


def download(name: str) -> None:
    with httpx.Client(headers=config.EA_HEADERS, timeout=60, follow_redirects=True) as c:
        r = c.get(FILE_API.format(name=quote(name)))
        r.raise_for_status()
        f = c.get(r.json()["url"])
        f.raise_for_status()
    (RAW / name).write_bytes(f.content)
    log.info("downloaded %s (%d bytes)", name, len(f.content))


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        if not (RAW / name).exists():
            download(name)
    ev = read_ea_dcww_events([RAW / n for n in FILES])
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
