"""Do the converted ERA5-Land cells (scripts/era5land/to_cells.py) match Open-Meteo archive rain for the same cells and
hours? (docs/ERA5-LAND-BULK-RAIN-2026-11.md, "The match check"). Offline: it reads parquet files and writes one report.
The reference files are only read; their SHA-256 is taken before and after, and the report says if any changed.

    uv run python scripts/era5land/match_check.py --era5land "$HOME/dipcast-scratch/era5land/cache/rain" \\
        --reference ~/Documents/GitHub/dipcast/data/cache/rain --reference ~/Documents/GitHub/dipcast/data/cache/rain_nine \\
        --kind best_match --years 2023-2025 --report "$HOME/dipcast-scratch/era5land/match_best_match.json"

--kind names what the reference is, and so which thresholds apply. Both sets were written in the record before any
comparison was run, and are not changed after a result is seen:

  era5_land   Reference fetched from Open-Meteo with models=era5_land (for example the coastal C1 files). The same
              product, so this checks the pipeline (times, units, de-accumulation, cells). PASS needs all of:
                S1 share of paired hours with |ERA5-Land - reference| <= 0.1 mm        >= 0.99
                S2 share of cells (100+ wet hours) with hourly r >= 0.99               >= 0.98
                S3 |mean daily difference| <= max(0.02 mm, 1% of the reference mean)
                S4 share of paired cell-days within 0.5 mm                             >= 0.99
  best_match  Reference is the cached archive files, fetched with no model named (Open-Meteo's best_match). A
              different product from 2017 on (the record's "What the cached rain is"), so this asks whether ERA5-Land
              can stand in for it without refitting. PASS needs all of:
                B1 pooled daily r                                                      >= 0.90
                B2 |mean daily difference| / reference mean                            <= 0.10
                B3 share of paired cell-days within 0.5 mm                             >= 0.85
                B4 share of cells (30+ days of 1 mm or more) with daily r >= 0.80      >= 0.90

No verdict with fewer than 10 cells, or fewer than 1,000 (era5_land) or 10,000 (best_match) paired cell-days.
Days are UTC days of the hour-ending label with at least 20 paired hours, as the model's features take them.
For an era5_land reference whose files record the grid point Open-Meteo used (grid_lat, grid_lon), each cell is
compared with ERA5-Land at that point, so convert that point too (to_cells.py --all-land covers every one).
Hourly r at lags of -1 and +1 hour is reported (not judged) to show a one-hour label shift if there is one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import era5land_core as core  # noqa: E402

HOURLY_TOL_MM = 0.1
DAILY_TOL_MM = 0.5
WET_HOUR_MM = 0.1
WET_DAY_MM = 1.0
MIN_WET_HOURS = 100
MIN_WET_DAYS = 30
EPS = 1e-9
# The thresholds, as the record states them. (name, comparison, value)
THRESHOLDS = {
    "era5_land": [("S1 hourly share within 0.1 mm", ">=", 0.99),
                  ("S2 share of cells with hourly r >= 0.99", ">=", 0.98),
                  ("S3 |mean daily difference| mm", "<=", "max(0.02, 0.01 x reference mean)"),
                  ("S4 daily share within 0.5 mm", ">=", 0.99)],
    "best_match": [("B1 daily r", ">=", 0.90),
                   ("B2 |mean daily difference| / reference mean", "<=", 0.10),
                   ("B3 daily share within 0.5 mm", ">=", 0.85),
                   ("B4 share of cells with daily r >= 0.80", ">=", 0.90)],
}
MIN_CELLS = 10
MIN_CELL_DAYS = {"era5_land": 1000, "best_match": 10000}


# ------------------------------------------------------------------ files
def index_files(dirs: list[Path], years: set[int] | None) -> dict[tuple[float, float], list[Path]]:
    """Every parquet file under `dirs` by cell, in the order the dirs are given (an earlier dir wins a duplicate
    hour). A file whose name carries a year outside `years` is skipped unread."""
    found: dict[tuple[float, float], list[Path]] = defaultdict(list)
    for d in dirs:
        for p in sorted(Path(d).rglob("*.parquet")):
            c = core.cell_from_name(p.name)
            if c is None:
                continue
            y = core.year_from_name(p.name)
            if years is not None and y is not None and y not in years:
                continue
            found[c].append(p)
    return found


def recorded_point(path: Path) -> tuple[float, float] | None:
    """The grid point Open-Meteo used, snapped to 0.1 degree, when the file records it (grid_lat, grid_lon)."""
    if not {"grid_lat", "grid_lon"} <= set(pq.read_schema(path).names):
        return None
    g = pd.read_parquet(path, columns=["grid_lat", "grid_lon"]).dropna()
    if g.empty:
        return None
    return float(core.snap(g["grid_lat"].iloc[0])), float(core.snap(g["grid_lon"].iloc[0]))


def fingerprint(files: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(str(p).encode())
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def load(files: list[Path], years: set[int] | None) -> tuple[pd.Series, int]:
    """One cell's hourly rain (index: UTC time), the first file holding an hour wins. Also the count of hours that two
    files both hold with different values."""
    parts = [pd.read_parquet(p, columns=["time", "precip_mm"]) for p in files]
    if not parts:
        return pd.Series(dtype=float), 0
    df = pd.concat(parts, ignore_index=True)
    if years is not None:
        df = df[df["time"].dt.year.isin(sorted(years))]
    dup = df.duplicated("time", keep=False)
    disagree = int((df[dup].groupby("time")["precip_mm"].nunique() > 1).sum()) if dup.any() else 0
    df = df.drop_duplicates("time", keep="first")
    return df.set_index("time")["precip_mm"].astype(float).sort_index(), disagree


# ------------------------------------------------------------------ the comparison
class Tally:
    """Pooled sums over every cell, and one row of results per cell."""

    def __init__(self):
        self.hourly = core.Moments()
        self.lag = {-1: core.Moments(), 1: core.Moments()}
        self.daily = core.Moments()
        self.hours_within = self.days_within = 0
        self.cells: list[dict] = []
        self.disagree = 0


def compare_cell(cell, era: pd.Series, ref: pd.Series, t: Tally) -> None:
    both = pd.DataFrame({"era": era, "ref": ref}).dropna()
    if both.empty:
        return
    x, y = both["era"].to_numpy(), both["ref"].to_numpy()
    t.hourly.add(x, y)
    t.hours_within += int(np.sum(np.abs(x - y) <= HOURLY_TOL_MM + EPS))
    for k, m in t.lag.items():   # era at t against the reference at t + k hours
        shifted = ref.copy()
        shifted.index = shifted.index - pd.Timedelta(hours=k)
        j = pd.DataFrame({"era": era, "ref": shifted}).dropna()
        m.add(j["era"].to_numpy(), j["ref"].to_numpy())
    d = core.daily_pairs(both.rename_axis("time").reset_index())
    t.daily.add(d["era"].to_numpy(), d["ref"].to_numpy())
    t.days_within += int(np.sum(np.abs(d["era"] - d["ref"]) <= DAILY_TOL_MM + EPS))
    wet_h = int(np.sum(y >= WET_HOUR_MM))
    wet_d = int(np.sum(d["ref"] >= WET_DAY_MM))
    t.cells.append({"cell": core.cell_key(*cell), "hours": len(both), "days": len(d), "wet_hours": wet_h,
                    "wet_days": wet_d, "hourly_r": core.pearson(x, y), "daily_r": core.pearson(d["era"], d["ref"]),
                    "daily_mean_diff_mm": float((d["era"] - d["ref"]).mean()) if len(d) else float("nan"),
                    "daily_share_within_0.5mm": float(np.mean(np.abs(d["era"] - d["ref"]) <= DAILY_TOL_MM + EPS))
                    if len(d) else float("nan"),
                    "ratio_of_totals": float(x.sum() / y.sum()) if y.sum() > 0 else float("nan")})


def _share(values, cut) -> float:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    return float(np.mean(v >= cut)) if len(v) else float("nan")


def results(t: Tally) -> dict:
    cells = pd.DataFrame(t.cells)
    n_h, n_d = t.hourly.n, t.daily.n
    hr_cells = cells[cells["wet_hours"] >= MIN_WET_HOURS] if len(cells) else cells
    dr_cells = cells[cells["wet_days"] >= MIN_WET_DAYS] if len(cells) else cells
    ref_mean = t.daily.mean_y()
    return {
        "cells": int(len(cells)), "paired_hours": n_h, "paired_cell_days": n_d,
        "hourly_r": t.hourly.r(), "hourly_r_lag_minus_1h": t.lag[-1].r(), "hourly_r_lag_plus_1h": t.lag[1].r(),
        "hourly_mean_diff_mm": t.hourly.bias(), "hourly_share_within_0.1mm": t.hours_within / n_h if n_h else None,
        "cells_judged_hourly": int(len(hr_cells)),
        "share_of_cells_hourly_r_ge_0.99": _share(hr_cells["hourly_r"], 0.99) if len(hr_cells) else None,
        "daily_r": t.daily.r(), "daily_mean_era5land_mm": t.daily.mean_x(), "daily_mean_reference_mm": ref_mean,
        "daily_mean_diff_mm": t.daily.bias(),
        "daily_relative_diff": t.daily.bias() / ref_mean if ref_mean else None,
        "daily_share_within_0.5mm": t.days_within / n_d if n_d else None,
        "cells_judged_daily": int(len(dr_cells)),
        "share_of_cells_daily_r_ge_0.80": _share(dr_cells["daily_r"], 0.80) if len(dr_cells) else None,
        "reference_hours_two_files_disagree": t.disagree,
    }


def verdict(kind: str, r: dict) -> tuple[str, list[dict]]:
    """("PASS" | "FAIL" | "NO VERDICT", one row per threshold)."""
    if kind == "era5_land":
        bias_cap = max(0.02, 0.01 * (r["daily_mean_reference_mm"] or 0.0))
        values = [r["hourly_share_within_0.1mm"], r["share_of_cells_hourly_r_ge_0.99"],
                  abs(r["daily_mean_diff_mm"]) if r["daily_mean_diff_mm"] is not None else None,
                  r["daily_share_within_0.5mm"]]
        cuts = [0.99, 0.98, bias_cap, 0.99]
    else:
        values = [r["daily_r"], abs(r["daily_relative_diff"]) if r["daily_relative_diff"] is not None else None,
                  r["daily_share_within_0.5mm"], r["share_of_cells_daily_r_ge_0.80"]]
        cuts = [0.90, 0.10, 0.85, 0.90]
    rows = []
    for (name, op, _), v, cut in zip(THRESHOLDS[kind], values, cuts, strict=True):
        ok = v is not None and np.isfinite(v) and (v >= cut if op == ">=" else v <= cut)
        rows.append({"test": name, "value": v, "op": op, "threshold": cut, "pass": bool(ok)})
    if r["cells"] < MIN_CELLS or r["paired_cell_days"] < MIN_CELL_DAYS[kind]:
        return "NO VERDICT", rows
    return ("PASS" if all(x["pass"] for x in rows) else "FAIL"), rows


def run(era_dir: Path, ref_dirs: list[Path], kind: str, years: set[int] | None) -> dict:
    if kind not in THRESHOLDS:
        raise ValueError(f"--kind is era5_land or best_match, not {kind!r}")
    t0 = time.monotonic()
    era_idx = index_files([era_dir], years)
    ref_idx = index_files(ref_dirs, years)
    # Which ERA5-Land series each reference cell is compared with: its own cell, or, for an era5_land reference that
    # records the grid point Open-Meteo used (grid_lat, grid_lon, as the C1 files do), that point.
    pairs = {}
    for c, files in ref_idx.items():
        g = recorded_point(files[0]) if kind == "era5_land" else None
        pairs[c] = g if g is not None else c
    common = sorted(c for c, e in pairs.items() if e in era_idx)
    moved = sum(pairs[c] != c for c in common)
    ref_files = [p for c in common for p in ref_idx[c]]
    before = fingerprint(ref_files)
    t = Tally()
    for c in common:
        era, _ = load(era_idx[pairs[c]], years)
        ref, disagree = load(ref_idx[c], years)
        t.disagree += disagree
        compare_cell(c, era, ref, t)
    after = fingerprint(ref_files)
    r = results(t)
    v, rows = verdict(kind, r)
    cells = pd.DataFrame(t.cells)
    worst = []
    if len(cells):
        judged = cells[cells["wet_days"] >= MIN_WET_DAYS]
        worst = judged.sort_values("daily_r").head(10).to_dict("records")
    return {"kind": kind, "verdict": v, "tests": rows, "results": r, "worst_cells_by_daily_r": worst,
            "largest_daily_mean_diff": (cells.reindex(cells["daily_mean_diff_mm"].abs().sort_values(ascending=False)
                                                      .index).head(10).to_dict("records") if len(cells) else []),
            "era5land_dir": str(era_dir), "reference_dirs": [str(d) for d in ref_dirs],
            "years": sorted(years) if years else "all", "cells_era5land": len(era_idx), "cells_reference": len(ref_idx),
            "cells_compared": len(common), "cells_compared_at_open_meteo_point": moved,
            "reference_files_read": len(ref_files),
            "reference_sha256_before": before, "reference_sha256_after": after,
            "reference_unchanged": before == after, "seconds": round(time.monotonic() - t0, 1)}


def _years(text: str | None) -> set[int] | None:
    if not text:
        return None
    out = set()
    for part in text.split(","):
        a, _, b = part.partition("-")
        out |= set(range(int(a), int(b or a) + 1))
    return out


def _fmt(v) -> str:
    return "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.4f}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--era5land", type=Path, required=True, help="to_cells.py's output folder")
    ap.add_argument("--reference", type=Path, action="append", required=True, help="a folder of Open-Meteo files")
    ap.add_argument("--kind", required=True, choices=sorted(THRESHOLDS), help="what the reference is")
    ap.add_argument("--years", default=None, help="e.g. 2023-2025 (default: every hour both hold)")
    ap.add_argument("--report", type=Path, required=True, help="where the JSON report goes (not a data/cache folder)")
    a = ap.parse_args(argv)
    problem = core.out_ok(a.report.parent)
    if problem:
        print(problem)
        return 2
    rep = run(a.era5land, a.reference, a.kind, _years(a.years))
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(rep, indent=1, default=float) + "\n")
    r = rep["results"]
    print(f"{rep['cells_compared']} cells, {r['paired_hours']} paired hours, {r['paired_cell_days']} paired cell-days")
    print(f"hourly r {_fmt(r['hourly_r'])} (lag -1 h {_fmt(r['hourly_r_lag_minus_1h'])}, "
          f"+1 h {_fmt(r['hourly_r_lag_plus_1h'])}), mean difference {_fmt(r['hourly_mean_diff_mm'])} mm")
    for row in rep["tests"]:
        print(f"  {'pass' if row['pass'] else 'FAIL'}  {row['test']}: {_fmt(row['value'])} "
              f"{row['op']} {_fmt(row['threshold'])}")
    print(f"Reference files unchanged: {rep['reference_unchanged']}")
    if rep["verdict"] == "NO VERDICT":
        print(f"Too little to judge: needs {MIN_CELLS} cells and {MIN_CELL_DAYS[rep['kind']]:,} paired cell-days.")
    print(f"VERDICT ({rep['kind']}): {rep['verdict']}. Report: {a.report}")
    return {"PASS": 0, "FAIL": 1}.get(rep["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main())
