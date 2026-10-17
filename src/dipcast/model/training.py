"""What the nine-company spill model trains and is verified on (docs/NINE-COMPANY-MODEL-TEST-2026-10.md):
the EA start/stop events of the nine English companies, the overflow-years they cover, and the rain
for their cells. Shared by scripts/train.py and scripts/verify_leads.py so the two pick the same rows.
"""

from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.rainfall import grid_cell

log = logging.getLogger(__name__)

NINE = ["Anglian Water", "Northumbrian Water", "Severn Trent Water", "South West Water", "Southern Water",
        "Thames Water", "United Utilities", "Wessex Water", "Yorkshire Water"]
WELSH = "Dwr Cymru Welsh Water"   # a test set: dcww_ea_events.parquet, never training
MIN_EDM_PCT = 50.0
RAIN_DIRS = ("rain", "rain_nine")   # the shared cache, then the nine-company fetch's own


def events_path(company: str):
    return config.PROCESSED / f"ea_events_{re.sub(r'[^a-z0-9]+', '_', company.lower()).strip('_')}.parquet"


def load_events(companies=NINE) -> pd.DataFrame:
    """The EA start/stop events of `companies` (scripts/import_ea_events.py), with a company column.
    Dwr Cymru Welsh Water comes from dcww_ea_events.parquet (scripts/import_ea_welsh_water.py)."""
    frames = []
    for c in companies:
        p = config.PROCESSED / "dcww_ea_events.parquet" if c == WELSH else events_path(c)
        frames.append(pd.read_parquet(p).assign(company=c))
    return pd.concat(frames, ignore_index=True)


def site_years(ar: pd.DataFrame, events: pd.DataFrame, companies, year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The overflows of `companies` to use in `year`, with covariates from the `year - 1` return, and a
    per-company count of what each rule dropped. Kept: a position in the year-1 return, and either an
    event in `year` or 0 spills in the `year` return; dropped as well when the `year` return gives EDM
    operation under MIN_EDM_PCT (a missing value is kept, as train.py always has)."""
    prev = ar[ar["company"].isin(companies) & (ar["year"] == year - 1) & ar["lat"].notna()]
    prev = prev.drop_duplicates("site_id", keep="last")
    same = ar[ar["company"].isin(companies) & (ar["year"] == year)].drop_duplicates("site_id", keep="last")
    same = same.set_index("site_id")
    spilled = set(events.loc[events["event_start"].dt.year == year, "site_id"])
    sid = prev["site_id"]
    in_file = sid.isin(spilled)
    zero = sid.map(same["spills"]).eq(0)
    edm = sid.map(same["edm_operational_pct"])
    covered = in_file | zero
    low_edm = edm.lt(MIN_EDM_PCT)
    keep = covered & ~low_edm
    counts = pd.DataFrame({"company": prev["company"], "with_position": 1,
                           "missing_from_file": (~covered).astype(int),
                           "edm_under_50": (covered & low_edm).astype(int), "kept": keep.astype(int)})
    counts = counts.groupby("company").sum()
    counts["year"] = year
    cols = ["site_id", "company", "lat", "lon", "lta_spills", "spill_hours", "edm_operational_pct"]
    return prev.loc[keep, cols].reset_index(drop=True), counts


def cells_of(sites: pd.DataFrame) -> set[tuple[float, float]]:
    cl, cn = grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy())
    return set(zip(cl.tolist(), cn.tolist(), strict=True))


def load_rain(cells: set[tuple[float, float]], tags=("2023", "2023dec", "2024", "2025"),
              start: str = "2023-12-01") -> pd.DataFrame:
    """Hourly ERA5-Land rain for `cells` from both caches, files tagged `tags`, from `start` on."""
    files = []
    for d in RAIN_DIRS:
        for t in tags:
            for f in (config.CACHE / d).glob(f"archive_*_{t}.parquet"):
                p = f.stem.split("_")
                if (float(p[1]), float(p[2])) in cells:
                    files.append(f)
    log.info("loading %d rain cell-files for %d cells", len(files), len(cells))
    t0 = pd.Timestamp(start, tz="UTC")
    rain = pd.concat((r[r["time"] >= t0] for r in (pd.read_parquet(f) for f in files)), ignore_index=True)
    rain["precip_mm"] = rain["precip_mm"].astype(np.float32)
    return rain


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error: |mean forecast - observed rate| over equal-width bins, weighted by rows."""
    idx = np.clip((p * bins).astype(int), 0, bins - 1)
    n = np.bincount(idx, minlength=bins)
    sp = np.bincount(idx, weights=p, minlength=bins)
    sy = np.bincount(idx, weights=y.astype(float), minlength=bins)
    ok = n > 0
    return float(np.abs(sp[ok] - sy[ok]).sum() / n.sum())
