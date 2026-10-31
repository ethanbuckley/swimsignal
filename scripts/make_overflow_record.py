"""What each overflow's public record page (overflow/<id>/, build_site.write_overflow_pages) says about its permit and
its improvements, from two Environment Agency sources the forecast never reads:

    uv run python scripts/make_overflow_record.py [--winep path/to/PR24 WINEP National Dataset.xlsx]

Off CI, by hand: when a new annual return is out (about March) or the EA reissues the WINEP. It writes

- data/processed/overflow_record.parquet: one row per overflow and return year (2024 on; the 2023 return has the
  improvement columns empty), with the EA permit reference, the activity reference on the permit, and the return's
  improvement and investigation activity for the year, word for word. From the EDM annual returns layer
  (config.EDM_ANNUAL_RETURNS), "© Environment Agency copyright and/or database right", Open Government Licence v3.0.
  annual_returns.parquet, which the forecast reads, is not touched.
- data/processed/winep_overflow_actions.parquet: the PR24 Water Industry National Environment Programme's storm
  overflow improvement actions (drivers EnvAct_IMP2 to 5, BW_IMP, SW_IMP) with a permit reference: the action's id,
  name, driver and Completion_Date, which the WINEP's READ ME defines as "the date the Action should be delivered":
  a deadline, not a record of delivery. data.gov.uk dataset cf9b80c2-cae9-4ed1-88ce-890940be379a, licence "Open
  Government Licence" (checked 31 Oct 2026); its attribution statement, which the page quotes, is "© Environment
  Agency copyright and/or database right 2025. All rights reserved." The WINEP names a permit, not an overflow, so
  the page says so where a permit covers more than one (docs/OVERFLOW-DATA-SOURCES-2026-10.md, 2.2).

Not used, because nothing licenses publishing them: the EA's consents register, the companies' own event files and
plan layers, and Water UK's plan (docs/OVERFLOW-DATA-SOURCES-2026-10.md, section 7).
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from pathlib import Path

import httpx
import pandas as pd

from dipcast import config
from dipcast.arcgis import fetch_all
from dipcast.ids import CURRENT
from dipcast.ingest.common import write_parquet

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("make_overflow_record")

RECORD = config.PROCESSED / "overflow_record.parquet"
WINEP = config.PROCESSED / "winep_overflow_actions.parquet"
WINEP_URL = ("https://environment.data.gov.uk/api/file/download?fileDataSetId=63ec410d-733f-4042-8682-b70cf25f1d70"
             "&fileName=PR24%20WINEP%20National%20Dataset.xlsx")
WINEP_SHEET = "PR24 WINEP National Data"
WINEP_DRIVERS = r"^(?i:EnvAct_IMP[2-5]|BW_IMP\d|SW_IMP\d?)$"   # storm overflow improvements; the file has ENVAct_ too
FIELDS = {"unique_id": "site_id", "annual_return_year": "year", "water_company_name": "company",
          "permit_reference_ea_condat": "permit", "activity_reference_on_permit": "activity_ref",
          "improvement_activity_for_the_reporting_period": "improvement",
          "investigation_activity_for_the_reporting_period": "investigation"}
FIRST_YEAR = 2024


def clean(s: pd.Series) -> pd.Series:
    """Strings trimmed, with blanks as missing."""
    s = s.astype("string").str.strip()
    return s.mask(s == "")


def fetch_record(first_year: int = FIRST_YEAR) -> pd.DataFrame:
    rows = fetch_all(config.EDM_ANNUAL_RETURNS, where=f"annual_return_year >= '{first_year}'", geometry=False,
                     out_fields=",".join(FIELDS))
    d = pd.DataFrame(rows).rename(columns=FIELDS)[list(FIELDS.values())]
    for c in d.columns:
        d[c] = clean(d[c])
    d["year"] = pd.to_numeric(d["year"], errors="coerce").astype("Int64")
    d = d[d["site_id"].str.fullmatch(CURRENT.pattern, na=False) & d["year"].notna()]
    return d.drop_duplicates(["site_id", "year"], keep="first").sort_values(["site_id", "year"]).reset_index(drop=True)


def read_winep(path: Path) -> pd.DataFrame:
    w = pd.read_excel(path, sheet_name=WINEP_SHEET, dtype=str)
    w = w[w["Driver_Code_Primary"].str.strip().str.match(WINEP_DRIVERS, na=False)]
    out = pd.DataFrame({"permit": clean(w["Licence_Permit_Obstruction_ID"]), "company": clean(w["Water_Company"]),
                        "action_id": clean(w["Action_ID"]), "action_name": clean(w["Action_Name"]),
                        "driver": clean(w["Driver_Code_Primary"]),
                        "completion_date": pd.to_datetime(w["Completion_Date"], errors="coerce").dt.strftime("%Y-%m-%d")})
    return out.dropna(subset=["permit", "completion_date"]).drop_duplicates().sort_values(["permit", "completion_date", "action_id"]).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--winep", type=Path, help="the WINEP XLSX, if already downloaded; else it is fetched into a temporary folder")
    a = ap.parse_args()
    record = fetch_record()
    write_parquet(record, RECORD)
    log.info("%s: %d rows, %d overflows, years %s", RECORD.name, len(record), record["site_id"].nunique(),
             sorted(record["year"].unique().tolist()))
    if a.winep:
        winep = read_winep(a.winep)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "winep.xlsx"
            with httpx.stream("GET", WINEP_URL, follow_redirects=True, timeout=300) as r:
                r.raise_for_status()
                with p.open("wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
            winep = read_winep(p)
    write_parquet(winep, WINEP)
    permits = set(record.loc[record["year"] == record["year"].max(), "permit"].dropna())
    log.info("%s: %d actions, %d on a permit in the latest return", WINEP.name, len(winep), int(winep["permit"].isin(permits).sum()))


if __name__ == "__main__":
    main()
