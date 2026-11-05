"""Exploratory buoy check for the lake test (docs/LAKE-TEMPERATURE-SENSORS-2026-10.md, "Exploratory score runs"):
apply the fixed #419 primary outer-fold model for a held-out lake to an EIDC hourly buoy series. Offline: reads the
EIDC zips where they are, the private features file and the HadUK daily series; makes no request and writes nothing.

    python -I lt_buoy_check.py --features <private>/water-temperature/lake-test/work/features.parquet \\
        --haduk <private>/water-temperature/work/haduk_series.npz --point NW-88016157 --fold 4 --depth 0.5m \\
        --zip "blelham_buoy_2016_2018.zip:data/blel-2016_2017_2018.csv:%d/%m/%Y %H:%M" \\
        --zip "blelham_buoy_2019.zip:data/blel-2019.csv:%d/%b/%Y %H:%M"

The depth is picked by the CSV's second header row ("0.5m", "2m"), never by position, and a depth column with no
values stops the run: Windermere South's published 1 m column is empty (27 Oct 2026). --exclude-wb leaves more WFD
waterbodies out of training, for a sensitivity fit reported apart from the exact fold score. Nothing here decides
anything: the preregistered verdict is #419's 2026 result.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "water_temperature_model_eval"))
import lt_protocol as lp  # noqa: E402
import lt_score as ls  # noqa: E402
import wt_score as ws  # noqa: E402

MIN_HOURS = 18   # hourly readings a day needs to count (exploratory; 0 keeps every day)


def read_buoy(sources: list[tuple[str, str, str]], depth: str) -> dict[pd.Timestamp, list[float]]:
    """{GMT date: hourly values at `depth`} from (zip, member, date format) sources. The column is the one whose
    second header row reads `depth`; a source without that label, or with no value in it, raises ValueError."""
    obs: dict[pd.Timestamp, list[float]] = {}
    for path, member, fmt in sources:
        with zipfile.ZipFile(path) as z:
            rows = csv.reader(io.TextIOWrapper(z.open(member), encoding="utf-8-sig"))
            next(rows)
            labels = [x.strip() for x in next(rows)]
            if depth not in labels:
                raise ValueError(f"{member}: no {depth} column (labels {labels})")
            col, seen = labels.index(depth), 0
            for r in rows:
                try:
                    dt, v = pd.to_datetime(r[0], format=fmt), float(r[col])
                except (ValueError, IndexError):
                    continue
                if math.isfinite(v):
                    obs.setdefault(dt.normalize(), []).append(v)
                    seen += 1
            if not seen:
                raise ValueError(f"{member}: the {depth} column has no values")
    return obs


def daily(obs: dict[pd.Timestamp, list[float]], year: int, min_hours: int = MIN_HOURS) -> pd.Series:
    """May to September daily means of one year, from days with at least `min_hours` readings."""
    keep = sorted(d for d in obs if d.year == year and 5 <= d.month <= 9 and len(obs[d]) >= min_hours)
    return pd.Series([float(np.mean(obs[d])) for d in keep], index=pd.DatetimeIndex(keep), dtype=float)


def run(features: pd.DataFrame, haduk: pd.Series, obs: dict, point: str, fold: int, exclude_wb=(), min_hours=MIN_HOURS) -> dict:
    """lt_score's primary-arm fit for `fold` (training 2000-25, the fold's waterbodies out, HadUK air), with any
    extra waterbodies out, scored on the buoy's daily means with the static features of `point`'s latest row."""
    f = features
    train = f[f["year"].between(2000, 2025) & f["fold"].ne(fold) & f["hk_ok"] & ~f["wb_id"].isin(list(exclude_wb))]
    model = lp.fit_fold(ls._as(train.copy(), "_hk"))
    meta = f[(f["point"] == point) & (f["year"] == f["year"].max())].iloc[0]
    parts = []
    for y in sorted({d.year for d in obs}):
        s = daily(obs, y, min_hours)
        if not len(s):
            continue
        win = lp.air_windows(ws._season(haduk, y), y, s.index)
        t = pd.DataFrame([meta.to_dict() for _ in s.index])
        t["date"], t["year"], t["temp"] = s.index, y, s.to_numpy()
        doy = s.index.dayofyear.to_numpy(float)
        t["doy"], t["doy_sin"], t["doy_cos"] = doy, np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
        for c in lp.AIR_COLS:
            t[c] = win[c].to_numpy()
        parts.append(t)
    te = pd.concat(parts, ignore_index=True)
    te = te[te[[model["third_window"], model["e_window"], "a7"]].notna().all(axis=1)]
    p = lp.predict_fold(model, te.copy())

    def score(e):
        return {"rmse": float(np.sqrt(np.mean(e ** 2))), "bias": float(e.mean()), "p90": float(np.quantile(np.abs(e), 0.9))}
    return {"fit_rows": model["train_rows"], "fit_waters": model["train_waters"], "days": int(len(p)),
            "days_by_year": {int(y): int(n) for y, n in p.groupby("year").size().items()},
            "test_rows_in_training": int(train["wb_id"].isin(f.loc[f["point"] == point, "wb_id"]).sum()),
            **{k: score(p[c] - p["temp"]) for k, c in (("candidate", "pred_cand"), ("longer_window", "pred_third"),
                                                         ("air7", "pred_air7"), ("doy", "pred_doy"))},
            "candidate_rmse_by_year": {int(y): float(np.sqrt(np.mean((g["pred_cand"] - g["temp"]) ** 2)))
                                       for y, g in p.groupby("year")}}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True, type=Path)
    ap.add_argument("--haduk", required=True, type=Path)
    ap.add_argument("--point", required=True)
    ap.add_argument("--fold", required=True, type=int)
    ap.add_argument("--depth", required=True)
    ap.add_argument("--zip", action="append", required=True, help="path:member:date format")
    ap.add_argument("--exclude-wb", nargs="*", default=[])
    ap.add_argument("--min-hours", type=int, default=MIN_HOURS)
    a = ap.parse_args(argv)
    f = pd.read_parquet(a.features)
    cell = int(f.loc[f["point"].eq(a.point), "hk_cell"].dropna().iloc[0])
    with np.load(a.haduk) as h:
        haduk = pd.Series(h["tas"][int(np.flatnonzero(h["cells"] == cell)[0])].astype(float), index=pd.to_datetime(h["dates"]))
    obs = read_buoy([tuple(z.split(":", 2)) for z in a.zip], a.depth)
    res = run(f, haduk, obs, a.point, a.fold, a.exclude_wb, a.min_hours)
    print(json.dumps({"point": a.point, "hk_cell": cell, "fold": a.fold, "depth": a.depth, "exclude_wb": a.exclude_wb, **res}, indent=1))


if __name__ == "__main__":
    main()
