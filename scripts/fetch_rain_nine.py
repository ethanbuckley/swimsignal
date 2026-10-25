"""Fetch the rain the nine-company spill model test needs (docs/NINE-COMPANY-MODEL-TEST-2026-10.md)
for the cells the shared cache lacks. Off CI, by hand, paced under Open-Meteo's free limits:

    uv run python scripts/fetch_rain_nine.py --dry-run          # what is missing, and its cost
    uv run python scripts/fetch_rain_nine.py archive 2024 2023dec
    uv run python scripts/fetch_rain_nine.py archive 2025        # the next UTC day
    uv run python scripts/fetch_rain_nine.py leads               # the 150 sampled lead cells
    uv run python scripts/fetch_rain_nine.py archive 2026a       # v2's test rain (below)

Everything new goes to data/cache/rain_nine/, never data/cache/rain/. Other evaluations
(validate_ecoli.py, the hindcasts) read every file in data/cache/rain/, so a new cell there would
change what they compute. The cells are those of every overflow with a position in the 2023 or
2024 annual return of the nine English companies. "2023dec" is 1 to 31 December 2023 for cells with
no 2023 file, so January 2024's 7-day and 30-day windows are complete. "leads" is the 2025 archived
forecasts for 30 cells each of Anglian, Northumbrian, South West, Southern and Yorkshire, drawn
with numpy default_rng(0) from that company's cells with no lead file.

"2026a" is the rain the v2 test needs (docs/NINE-COMPANY-MODEL-V2-TEST-2026-11.md): 1 January to 31 August 2026
for every cell of the nine companies' overflows in the 2025 return that has no 2026 file in data/cache/rain/. Its
files are tagged 2026a, not 2026, because fetch_archive takes any archive_<cell>_2026.parquet as a whole year
already fetched. Every request is logged, one JSON line each, in data/cache/rain_nine/requests_2026a.jsonl.
"""

from __future__ import annotations

import json
import logging
import sys
import time

import httpx
import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest import rainfall, rainfall_leads
from dipcast.ingest.rainfall import _request, _to_frame, cell_key, grid_cell

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("fetch_rain_nine")

NINE = ["Anglian Water", "Northumbrian Water", "Severn Trent Water", "South West Water", "Southern Water",
        "Thames Water", "United Utilities", "Wessex Water", "Yorkshire Water"]
SHARED = config.CACHE / "rain"
OWN = config.CACHE / "rain_nine"
LEAD_SAMPLE = {"Anglian Water": 30, "Northumbrian Water": 30, "South West Water": 30,
               "Southern Water": 30, "Yorkshire Water": 30}
CALLS_PER_HOUR = 3000   # Open-Meteo's free limit is 5,000 an hour and 10,000 a day
V2_START, V2_END = "2026-01-01", "2026-08-31"   # the v2 test's days: the EA file's 2026 to August
V2_DAYS = (pd.Timestamp(V2_END) - pd.Timestamp(V2_START)).days + 1


def calls(n_cells: int, days: int, variables: int = 1) -> float:
    """Open-Meteo's count: locations x days/14 x variables/10, days at least 14 and each location
    at least 1 call (their blog, "Weather Data for Multiple Locations At Once": one variable at 10
    locations for 10 years weighs about 260, so fewer than 10 variables do weigh less). So one
    variable for a year is 2.6 calls a cell. (fetch_wales_history.archive_calls floors the
    variables factor at 1 and counts ten times that.)"""
    return n_cells * max(1.0, max(days, 14) / 14 * variables / 10)


def cells_by_company() -> pd.DataFrame:
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet",
                         columns=["site_id", "company", "year", "lat", "lon"])
    a = ar[ar["company"].isin(NINE) & ar["lat"].notna() & ar["year"].isin([2023, 2024])]
    cl, cn = grid_cell(a["lat"].to_numpy(), a["lon"].to_numpy())
    return pd.DataFrame({"company": a["company"].to_numpy(), "cell_lat": cl, "cell_lon": cn}).drop_duplicates()


def have(kind: str, tag: str) -> set[tuple[float, float]]:
    out = set()
    for d in (SHARED, OWN):
        for f in d.glob(f"{kind}_*_{tag}.parquet"):
            p = f.stem.split("_")
            out.add((float(p[1]), float(p[2])))
    return out


def pace(n_calls: float) -> None:
    time.sleep(3600.0 * n_calls / CALLS_PER_HOUR)


def fetch_year(cells: list, year: int) -> None:
    rainfall.CACHE = OWN
    days = (min(pd.Timestamp(f"{year}-12-31"), pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=6))
            - pd.Timestamp(f"{year}-01-01")).days + 1
    for i in range(0, len(cells), rainfall.BATCH):
        chunk = cells[i:i + rainfall.BATCH]
        rainfall.fetch_archive(chunk, year, strict=True)
        log.info("archive %d: %d/%d cells", year, i + len(chunk), len(cells))
        pace(calls(len(chunk), days))


def fetch_dec2023(cells: list) -> None:
    for i in range(0, len(cells), rainfall.BATCH):
        chunk = cells[i:i + rainfall.BATCH]
        params = {"latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
                  "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
                  "start_date": "2023-12-01", "end_date": "2023-12-31", "hourly": "precipitation",
                  "timezone": "UTC"}
        res = _request(config.OPEN_METEO_ARCHIVE, params, retry_429=False)
        for (cl, cn), r in zip(chunk, res if isinstance(res, list) else [res], strict=True):
            _to_frame(r, cl, cn).to_parquet(OWN / f"archive_{cell_key(cl, cn)}_2023dec.parquet", index=False)
        log.info("archive 2023dec: %d/%d cells", i + len(chunk), len(cells))
        pace(calls(len(chunk), 31))


def cells_2025() -> list:
    """The cells of every overflow with a position in the 2025 annual return of the nine companies."""
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet", columns=["company", "year", "lat", "lon"])
    a = ar[ar["company"].isin(NINE) & ar["lat"].notna() & (ar["year"] == 2025)]
    cl, cn = grid_cell(a["lat"].to_numpy(), a["lon"].to_numpy())
    return sorted(set(zip(cl.tolist(), cn.tolist())))


def missing_2026a() -> list:
    """2025-return cells with neither a 2026 file in the shared cache nor a 2026a file here."""
    shared = {(float(f.stem.split("_")[1]), float(f.stem.split("_")[2])) for f in SHARED.glob("archive_*_2026.parquet")}
    return [c for c in cells_2025() if c not in shared and c not in have("archive", "2026a")]


def fetch_2026a(cells: list) -> None:
    """1 January to 31 August 2026 for `cells`, strict (a refusal stops the fetch), paced, every request logged."""
    host = httpx.URL(config.OPEN_METEO_ARCHIVE).host
    with open(OWN / "requests_2026a.jsonl", "a") as logf:
        for i in range(0, len(cells), rainfall.BATCH):
            chunk = cells[i:i + rainfall.BATCH]
            params = {"latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
                      "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
                      "start_date": V2_START, "end_date": V2_END, "hourly": "precipitation", "timezone": "UTC"}
            weight = rainfall.call_weight(len(chunk), V2_DAYS)
            before = rainfall._requests.get(host, 0)
            entry = {"at": pd.Timestamp.now("UTC").isoformat(), "cells": len(chunk), "days": V2_DAYS,
                     "weight": round(weight, 3), "first_cell": cell_key(*chunk[0])}
            try:
                res = _request(config.OPEN_METEO_ARCHIVE, params, retry_429=False)
            except Exception as e:
                entry.update(status="failed", error=str(e)[:200], attempts=rainfall._requests.get(host, 0) - before)
                logf.write(json.dumps(entry) + "\n")
                logf.flush()
                raise
            for (cl, cn), r in zip(chunk, res if isinstance(res, list) else [res], strict=True):
                _to_frame(r, cl, cn).to_parquet(OWN / f"archive_{cell_key(cl, cn)}_2026a.parquet", index=False)
            entry.update(status="ok", attempts=rainfall._requests.get(host, 0) - before)
            logf.write(json.dumps(entry) + "\n")
            logf.flush()
            log.info("archive 2026a: %d/%d cells", i + len(chunk), len(cells))
            pace(weight * entry["attempts"])


def lead_sample(cc: pd.DataFrame) -> list:
    got = have("leads", "2025")
    rng = np.random.default_rng(0)
    out = []
    for company, n in LEAD_SAMPLE.items():
        pool = sorted({(a, b) for a, b in cc.loc[cc["company"] == company, ["cell_lat", "cell_lon"]].itertuples(index=False)} - got)
        k = min(n, len(pool))
        out += [pool[j] for j in sorted(rng.choice(len(pool), size=k, replace=False))]
    return out


def main() -> None:
    OWN.mkdir(parents=True, exist_ok=True)
    cc = cells_by_company()
    allc = sorted({(a, b) for a, b in cc[["cell_lat", "cell_lon"]].itertuples(index=False)})
    miss = {y: [c for c in allc if c not in have("archive", str(y))] for y in (2024, 2025)}
    miss_dec = [c for c in allc if c not in have("archive", "2023") and c not in have("archive", "2023dec")]
    leads = [c for c in lead_sample(cc) if c not in have("leads", "2025")]
    cost = {"2024": calls(1, 366) * len(miss[2024]), "2025": calls(1, 365) * len(miss[2025]),
            "2023dec": calls(1, 31) * len(miss_dec), "leads": calls(1, 365, 5) * len(leads)}
    miss_2026a = missing_2026a()
    cost["2026a"] = rainfall.call_weight(len(miss_2026a), V2_DAYS)
    print(f"{len(allc)} cells; missing 2024 {len(miss[2024])}, 2025 {len(miss[2025])}, "
          f"2023dec {len(miss_dec)}, lead sample {len(leads)}, 2026a {len(miss_2026a)}")
    print("calls:", {k: round(v) for k, v in cost.items()})
    if "--dry-run" in sys.argv:
        return
    if "archive" in sys.argv:
        for tag in sys.argv[sys.argv.index("archive") + 1:]:
            if tag == "2023dec":
                fetch_dec2023(miss_dec)
            elif tag == "2026a":
                fetch_2026a(miss_2026a)
            elif tag.isdigit():
                fetch_year(miss[int(tag)], int(tag))
    if "leads" in sys.argv:
        rainfall_leads.CACHE = OWN
        for i in range(0, len(leads), rainfall_leads.BATCH):
            chunk = leads[i:i + rainfall_leads.BATCH]
            rainfall_leads.fetch_leads(chunk, 2025)
            pace(calls(len(chunk), 365, 5))
    print("DONE")


if __name__ == "__main__":
    main()
