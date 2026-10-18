"""Write one parquet of discharges per company, data/processed/ea_events_<company>.parquet (the
edm_events columns), from the Environment Agency's start/stop files for the companies that operate
in England, 2024 and 2025. Review task D2 (docs/REVIEW-2026-10-16.md); the test it feeds is stated in
docs/NINE-COMPANY-MODEL-TEST-2026-10.md. Off CI, run by hand:

    uv run python scripts/import_ea_events.py

It reads the files from data/raw/ea_events/ and downloads any that are missing through the EA
platform's signed-link route (import_ea_welsh_water.download; a runner was not refused, 16 Oct 2026,
run 38964387549). Dwr Cymru Welsh Water's files stay with scripts/import_ea_welsh_water.py and
dcww_ea_events.parquet: a test set, never training.

Then it prints, per company and year, the measured signs of how each company defines an event (the
DSP note gives one definition for all): events, overflows, the share of ids in the annual returns,
the median event length, the share under 15 minutes, and the median gap from one event's stop to
the next start at the same overflow.

Contains Environment Agency data: © Environment Agency copyright and/or database right, licensed
under the Open Government Licence v3.0.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

import httpx
import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.common import write_parquet
from dipcast.ingest.edm_events import EA_TEST_ONLY, ea_company, read_ea_events

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("import_ea_events")

FILES = [
    "Anglian 2024 Detailed EDM Data.xlsx", "Anglian Water Detailed Data 2025.csv",
    "Northumbrian 2024 Detailed EDM Data.csv", "Northumbrian 2025 Detailed EDM Data.csv",
    "Severn Trent 2024 Detailed EDM Data.xlsx", "Severn Trent 2025 Detailed EDM Data.csv",
    "South West 2024 Detailed EDM Data.xlsx", "South West Water 2025 Detailed EDM Data.csv",
    "Southern 2024 Detailed EDM Data.csv", "Southern Water 2025 EDM Detailed Data.xlsx",
    "Thames 2024 Detailed EDM Data.csv", "Thames Water 2025 EDM Detailed Data.xlsx",
    "United Utilities 2024 Detailed EDM Data.csv", "United Utilities 2025 Detailed EDM Data.csv",
    "Wessex 2024 Detailed EDM Data.csv", "Wessex 2025 Detailed EDM Data.xlsx",
    "Yorkshire 2024 Detailed EDM Data.csv", "Yorkshire 2025 Detailed EDM Data.xlsx",
]
FILE_API = ("https://environment.data.gov.uk/file-management-open/data-sets/"
            "c95ecc47-fa70-4a24-b8cc-098232987526/files/{name}/download-url")
RAW = config.RAW / "ea_events"


def slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")


def events_path(company: str):
    return config.PROCESSED / f"ea_events_{slug(company)}.parquet"


def download(name: str) -> None:
    with httpx.Client(headers=config.EA_HEADERS, timeout=120, follow_redirects=True) as c:
        r = c.get(FILE_API.format(name=quote(name)))
        r.raise_for_status()
        f = c.get(r.json()["url"])
        f.raise_for_status()
    (RAW / name).write_bytes(f.content)
    log.info("downloaded %s (%d bytes)", name, len(f.content))


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
    RAW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        if not (RAW / name).exists():
            download(name)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet", columns=["site_id", "company", "year"])
    by_company: dict[str, list] = {}
    for name in FILES:
        company = ea_company(name)
        assert company and company not in EA_TEST_ONLY, name
        by_company.setdefault(company, []).append(RAW / name)
    rows = []
    for company, paths in by_company.items():
        ev = read_ea_events(paths)
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
        outside = ev[~ev["year"].isin([2024, 2025])]
        log.info("%s: %d events, %d dated outside 2024-25", company, len(ev), len(outside))
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(t.round(3).to_string(index=False))
    (config.PROCESSED / "ea_events_summary.csv").write_text(t.round(4).to_csv(index=False))


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
