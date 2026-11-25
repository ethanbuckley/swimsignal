"""Fit, choose and freeze coastal candidate C1 and its no-rain twin C0 on 2022 to 2026 (protocol section 2,
amendment 1). Reads only committed 2022-26 samples and converted ERA5-Land cells; makes no request.

    uv run python scripts/coastal_c1/fit.py --rain "$HOME/dipcast-scratch/coastal-c1-era5land/cache/rain" \\
        --cells-map "$HOME/dipcast-scratch/coastal-c1-era5land/cache/rain/ERA5LAND_CELLS.csv" \\
        --frozen data/research/coastal/c1_frozen.v1.json --report docs/coastal-c1/fit.json

Writes the frozen file (every coefficient, the site table, the cell map, the window pair) and a report with the
leave-one-year-out scores of each window pair and the nested estimate (development evidence; decides nothing).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import c1  # noqa: E402

SAMPLES = REPO / "data" / "research" / "coastal" / "samples.parquet"
SITES = REPO / "data" / "research" / "coastal" / "sites.csv"
FIT_YEARS = (2022, 2023, 2024, 2025, 2026)
ALL_H = (24, 48, 72, 120, 168)


def fit(X: np.ndarray, y: np.ndarray) -> list[float]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = LogisticRegression(C=1e6, max_iter=10000).fit(X, y)
    return [float(m.intercept_[0]), *map(float, m.coef_[0])]


def rows(samples: Path, sites: Path, rain_dir: Path, years) -> tuple[pd.DataFrame, dict]:
    """The rows with their targets, last-sample features and every rain window."""
    df = pd.read_parquet(samples)
    df = df[df["year"].isin(years) & df["ecoli"].notna()].copy().reset_index(drop=True)
    st = pd.read_csv(sites)
    cells = c1.site_cells(st)
    df["cell"] = df["site_id"].map(lambda s: cells.get(s))
    df["t_utc"] = pd.DatetimeIndex(df["time"]).tz_convert("UTC")
    for name, line in c1.LINES.items():
        df[name] = c1.over(df["ecoli"], df["ecoli_qual"], line).astype(int)
    last = c1.last_sample(df)
    df["x_last1"], df["x_last2"] = last[:, 0], last[:, 1]
    for h in ALL_H:
        df[f"r{h}"] = np.nan
    no_file = []
    for cell, g in df.groupby("cell", sort=True):
        if cell is None:
            continue
        rain = c1.load_cell(rain_dir, cell, years)
        if rain is None:
            no_file.append(c1.cell_key(cell))
            continue
        for h in ALL_H:
            v, _ = c1.window_sums(g["t_utc"], rain, h)
            df.loc[g.index, f"r{h}"] = v
    info = {"rows": len(df), "sites": int(df["site_id"].nunique()), "cells": int(df["cell"].nunique()),
            "cells_with_no_rain_file": sorted(no_file),
            "rows_without_cell": int(df["cell"].isna().sum())}
    return df, info


def covered(df: pd.DataFrame, pair: tuple[int, ...]) -> np.ndarray:
    return np.all([df[f"r{h}"].notna().to_numpy() for h in pair], axis=0)


def loyo(df: pd.DataFrame, target: str, pair: tuple[int, ...] | None, years, cov: np.ndarray) -> dict:
    """Leave one year out over `years`: predictions for C1 (pair given) or C0 (pair None) on covered rows."""
    y = df[target].to_numpy()
    site, year, month = df["site_id"].to_numpy(), df["year"].to_numpy(), df["month"].to_numpy()
    last = df[["x_last1", "x_last2"]].to_numpy()
    rain = df[[f"r{h}" for h in pair]].to_numpy() if pair else None
    pred = np.full(len(df), np.nan)
    for yr in years:
        hist, test = (year != yr) & np.isin(year, years), year == yr
        tab = c1.site_table(site[hist], year[hist], y[hist])
        rate = c1.site_rate(tab, site, year, leave_own_year=True)
        X = c1.design(rate, month, last, None if rain is None else np.nan_to_num(rain))
        tr, te = hist & cov, test & cov
        coef = fit(X[tr], y[tr])
        pred[te] = c1.predict(coef, X[te])
    keep = np.isin(year, years) & cov
    return {"pred": pred, "rows": keep, "brier": c1.brier(pred[keep], y[keep])}


def choose(df: pd.DataFrame, target: str, years, cov: np.ndarray) -> tuple[str, dict]:
    scores = {w: loyo(df, target, pair, years, cov)["brier"] for w, pair in c1.WINDOWS.items()}
    best = min(scores.values())
    for w in c1.TIE_ORDER:                      # earlier in the order wins within TIE of the best
        if scores[w] <= best + c1.TIE:
            return w, scores
    raise AssertionError


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rain", type=Path, required=True)
    ap.add_argument("--cells-map", type=Path, required=True)
    ap.add_argument("--frozen", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args(argv)

    df, info = rows(SAMPLES, SITES, a.rain, FIT_YEARS)
    cov = covered(df, ALL_H)
    info["covered_rows"] = int(cov.sum())
    info["covered_over_500"] = int(df.loc[cov, "over_500"].sum())
    print(json.dumps(info), flush=True)

    # 1. The window pair, leave one year out, over 500.
    chosen, scores = choose(df, "over_500", FIT_YEARS, cov)
    c0 = loyo(df, "over_500", None, FIT_YEARS, cov)["brier"]
    print(f"window Brier {scores}; C0 {c0:.6f}; chosen {chosen}", flush=True)

    # 2. The nested estimate: the choice made inside each outer year, scored on that year. Decides nothing.
    nested = {}
    y = df["over_500"].to_numpy()
    year = df["year"].to_numpy()
    for outer in FIT_YEARS:
        inner = tuple(v for v in FIT_YEARS if v != outer)
        inner_cov = cov & np.isin(year, inner)
        w, _ = choose(df.assign(), "over_500", inner, inner_cov)
        p1 = loyo(df, "over_500", c1.WINDOWS[w], (*inner, outer), cov)["pred"]
        p0 = loyo(df, "over_500", None, (*inner, outer), cov)["pred"]
        t = (year == outer) & cov
        nested[str(outer)] = {"window": w, "rows": int(t.sum()), "over_500": int(y[t].sum()),
                              "brier_c1": c1.brier(p1[t], y[t]), "brier_c0": c1.brier(p0[t], y[t]),
                              "difference": c1.brier(p1[t], y[t]) - c1.brier(p0[t], y[t])}
    print(json.dumps(nested), flush=True)

    # 3. Freeze on every fit row.
    pair = c1.WINDOWS[chosen]
    site, month = df["site_id"].to_numpy(), df["month"].to_numpy()
    last = df[["x_last1", "x_last2"]].to_numpy()
    rain = df[[f"r{h}" for h in pair]].to_numpy()
    models = {}
    tables = {}
    for target in c1.LINES:
        yt = df[target].to_numpy()
        tab = c1.site_table(site, year, yt)
        rate = c1.site_rate(tab, site, year, leave_own_year=True)
        allrows = np.ones(len(df), bool)
        models[target] = {
            "R": fit(c1.design(rate, month, None, None)[allrows], yt[allrows]),
            "C0": fit(c1.design(rate, month, last, None)[cov], yt[cov]),
            "C1": fit(c1.design(rate, month, last, np.nan_to_num(rain))[cov], yt[cov]),
        }
        tables[target] = {"p0": tab["p0"], "m": tab["m"],
                          "sites": {s: {"k": tab["k"][s], "n": tab["n"][s]} for s in sorted(tab["k"])}}
    cmap = pd.read_csv(a.cells_map)
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    frozen = {
        "schema": "coastal-c1-frozen", "version": 1,
        "protocol": "docs/COASTAL-C1-PROTOCOL-2026-11.md (sections 2, 5, 6; amendment 1)",
        "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"), "code_commit": commit,
        "fit_years": list(FIT_YEARS), "months": list(c1.MONTHS),
        "window": {"name": chosen, "hours": list(pair)},
        "features": ["logit(site rate)", "month 6", "month 7", "month 8", "month 9", "x_last1", "x_last2",
                     *[f"log1p(rain {h} h)" for h in pair]],
        "models": models, "site_tables": tables,
        "rain": {"source": "ERA5-Land, Copernicus CDS reanalysis-era5-land total_precipitation, de-accumulated "
                           "hourly by scripts/era5land/to_cells.py, 0.1 mm",
                 "cell_rule": "era5land_core.map_cells, max_step 3",
                 "min_cover": c1.MIN_COVER,
                 "cells": cmap.to_dict(orient="records")},
        "samples": {"file": "data/research/coastal/samples.parquet", "sha256": c1.sha256(SAMPLES)},
    }
    a.frozen.parent.mkdir(parents=True, exist_ok=True)
    a.frozen.write_bytes(c1.canonical(frozen))
    report = {"info": info, "window_brier_loyo": scores, "c0_brier_loyo": c0, "chosen": chosen,
              "nested": nested, "frozen_file": str(a.frozen), "frozen_sha256": c1.sha256(a.frozen),
              "note": "Development evidence on 2022-26 rows. Decides nothing beyond the window choice."}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_bytes(c1.canonical(report))
    print(f"frozen {a.frozen} sha256 {report['frozen_sha256']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
