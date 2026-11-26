"""Shared parts of coastal candidate C1 (docs/COASTAL-C1-PROTOCOL-2026-11.md, section 2 and amendment 1).

Rain: hourly ERA5-Land files made by scripts/era5land/to_cells.py, one per cell and year
(archive_<lat>_<lon>_<year>.parquet; time is the end of the hour in UTC, precip_mm the rain in that hour).
Nothing here makes a request.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

GRID_DEG = 0.1
MONTHS = (5, 6, 7, 8, 9)
WINDOWS = {"W4": (24,), "W1": (24, 72), "W2": (24, 120), "W3": (48, 168)}
TIE_ORDER = ("W4", "W1", "W2", "W3")
TIE = 0.000005
MIN_COVER = 0.9
CLIP = (1e-6, 1 - 1e-6)
LINES = {"over_500": 500, "over_250": 250}


def snap(x) -> np.ndarray:
    return np.round(np.round(np.asarray(x, dtype=float) / GRID_DEG) * GRID_DEG, 3) + 0.0


def site_cells(sites: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Each mapped site's 0.1 degree cell, from its own position (fetch_rain.cells uses the same rule)."""
    s = sites[sites["wqa_point"].notna()]
    return {sid: (float(a), float(b)) for sid, a, b in zip(s["site_id"], snap(s["lat"]), snap(s["lon"]), strict=True)}


def cell_key(cell: tuple[float, float]) -> str:
    return f"{cell[0] + 0.0:.3f}_{cell[1] + 0.0:.3f}"


def load_cell(rain_dir: Path, cell: tuple[float, float], years) -> pd.Series | None:
    """The cell's hourly rain over `years` and the year before (for windows that cross 1 January), indexed by the end
    of the hour in UTC. None when no file exists for any of them."""
    parts = []
    for y in sorted({*years, min(years) - 1}):
        f = rain_dir / f"archive_{cell_key(cell)}_{y}.parquet"
        if f.exists():
            parts.append(pd.read_parquet(f, columns=["time", "precip_mm"]))
    if not parts:
        return None
    df = pd.concat(parts).drop_duplicates("time").sort_values("time")
    return pd.Series(df["precip_mm"].to_numpy(float), index=pd.DatetimeIndex(df["time"]).tz_convert("UTC"))


def window_sums(times_utc: pd.Series, rain: pd.Series | None, hours: int) -> tuple[np.ndarray, np.ndarray]:
    """Rain over the `hours` hours whose hour-ending label is at or before each time rounded down to the hour, and the
    share of those hours with a value. Missing rain is never zero: a window under MIN_COVER gives NaN."""
    n = len(times_utc)
    if rain is None or n == 0:
        return np.full(n, np.nan), np.zeros(n)
    full = rain.reindex(pd.date_range(rain.index.min(), rain.index.max(), freq="h", tz="UTC"))
    vals = full.to_numpy(float)
    have = np.isfinite(vals)
    csum = np.concatenate([[0.0], np.cumsum(np.where(have, vals, 0.0))])
    ccnt = np.concatenate([[0], np.cumsum(have)])
    end = pd.DatetimeIndex(times_utc).floor("h")
    pos = ((end - full.index[0]) / pd.Timedelta(hours=1)).to_numpy()
    out, cov = np.full(n, np.nan), np.zeros(n)
    for i, p in enumerate(pos):
        if not np.isfinite(p):
            continue
        hi = int(p) + 1          # rows 0..p inclusive
        lo = hi - hours
        if lo < 0 or hi > len(vals):
            continue
        c = (ccnt[hi] - ccnt[lo]) / hours
        cov[i] = c
        if c >= MIN_COVER:
            out[i] = csum[hi] - csum[lo]              # the hours with a value; the protocol does not rescale
    return out, cov


def over(value: pd.Series, qual: pd.Series, line: float) -> np.ndarray:
    """#692 section 4: a '<' result is never over; a '>' result is over when its value reaches the line."""
    return (((qual == "=") & (value > line)) | ((qual == ">") & (value >= line))).to_numpy()


def last_sample(df: pd.DataFrame) -> np.ndarray:
    """x1 = log10(previous result) - 1, 0 when none; x2 = 1 when none. Previous statutory sample at the site in the
    same calendar year. `df` must hold site_id, year, time and ecoli."""
    prev = df.sort_values("time").groupby(["site_id", "year"])["ecoli"].shift(1).reindex(df.index)
    none = prev.isna().to_numpy()
    x1 = np.where(none, 0.0, np.log10(np.clip(prev.fillna(1).to_numpy(float), 1, None)) - 1)
    return np.c_[x1, none.astype(float)]


def month_dummies(month: np.ndarray) -> np.ndarray:
    return np.c_[[(month == m).astype(float) for m in MONTHS[1:]]].T


def logit(p):
    p = np.clip(p, *CLIP)
    return np.log(p / (1 - p))


def site_table(site: np.ndarray, year: np.ndarray, y: np.ndarray) -> dict:
    """k and n by site and by site-year, p0 and the method-of-moments prior strength m, as #692's Fold."""
    sites = sorted(set(site))
    k, n, ky, ny = {}, {}, {}, {}
    for s, yr, v in zip(site, year, y, strict=True):
        k[s] = k.get(s, 0) + int(v)
        n[s] = n.get(s, 0) + 1
        ky[(s, int(yr))] = ky.get((s, int(yr)), 0) + int(v)
        ny[(s, int(yr))] = ny.get((s, int(yr)), 0) + 1
    p0 = sum(k.values()) / sum(n.values())
    ks = np.array([k[s] for s in sites], float)
    ns = np.array([n[s] for s in sites], float)
    big = ns >= 10
    v = (ks[big] / ns[big]).var(ddof=1) - p0 * (1 - p0) * np.mean(1 / ns[big])
    m = float(np.clip(p0 * (1 - p0) / v - 1, 1, 500)) if v > 0 else 500.0
    return {"p0": p0, "m": m, "k": k, "n": n, "k_year": ky, "n_year": ny}


def site_rate(tab: dict, site: np.ndarray, year: np.ndarray, leave_own_year: bool) -> np.ndarray:
    p0, m = tab["p0"], tab["m"]
    out = np.empty(len(site))
    for i, (s, yr) in enumerate(zip(site, year, strict=True)):
        k, n = tab["k"].get(s, 0), tab["n"].get(s, 0)
        if leave_own_year:
            k -= tab["k_year"].get((s, int(yr)), 0)
            n -= tab["n_year"].get((s, int(yr)), 0)
        out[i] = (k + m * p0) / (n + m)
    return out


def design(rate: np.ndarray, month: np.ndarray, last: np.ndarray | None, rain: np.ndarray | None) -> np.ndarray:
    """R's columns (logit site rate, month indicators), then the last sample, then log1p of each rain window."""
    cols = [logit(rate)[:, None], month_dummies(month)]
    if last is not None:
        cols.append(last)
    if rain is not None:
        cols.append(np.log1p(rain))
    return np.hstack(cols)


def predict(coef: list[float], X: np.ndarray) -> np.ndarray:
    z = coef[0] + X @ np.asarray(coef[1:], float)
    return 1 / (1 + np.exp(-z))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(obj) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True, default=float) + "\n").encode()
