"""docs/DIEOFF-WEATHER-TEST-2026-10.md: the weather both questions read, and the fetch.

    weather.py fetch <out dir>    hourly shortwave_radiation and temperature_2m at lead 0 from Open-Meteo's
                                  Previous Runs API, for the bathing waters' cells, 2023 to 2026; one parquet per
                                  cell-year, weather_leads_<cell>_<year>.parquet; stops at the first refusal
    weather.py means <cache dir>  the May-September means (I-bar, T-bar) the rate is scaled by, from the weather alone

Cells: rainfall.grid_cell of each bathing water's lat and lon in bwq_samples.parquet, as validate_ecoli.py and
train_ecoli.py place a sample's rain. Times are UTC; a value stamped H is the hour ending at H (Open-Meteo's
shortwave_radiation is the preceding hour's mean; temperature_2m is the instant at H).
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest import rainfall
from dipcast.ingest.rainfall import cell_key, grid_cell

log = logging.getLogger("dieoff_weather")
PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"
VARS = ("shortwave_radiation", "temperature_2m")
YEARS = (2023, 2024, 2025, 2026)
BATCH = 4
T90_H = 72.0                      # config.T90_HOURS on main bfe47f2; the average rate is held here
K0 = math.log(10.0) / T90_H       # per hour
TEMP_WINDOW_H = 24                # the stand-in for water temperature: mean air temperature over 24 h to each hour
MIN_COVERAGE = 0.9                # as ecoli.MIN_COVERAGE
SEASON = (5, 6, 7, 8, 9)          # months (London) the means are taken over
TZ = "Europe/London"


def cells() -> list[tuple[float, float]]:
    s = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id")
    cl, cn = grid_cell(s["lat"].to_numpy(dtype=float), s["lon"].to_numpy(dtype=float))
    return sorted({(round(float(a), 3), round(float(b), 3)) for a, b in zip(cl, cn, strict=True)})


def path(cache: Path, cell: tuple[float, float], year: int) -> Path:
    return cache / f"weather_leads_{cell_key(*cell)}_{year}.parquet"


def fetch(out_dir: str) -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    cs = cells()
    spent, requests = 0.0, 0
    last = pd.Timestamp.now("UTC").tz_localize(None).normalize() - pd.Timedelta(days=2)
    for year in YEARS:
        todo = [c for c in cs if not path(out, c, year).exists()]
        end = min(pd.Timestamp(f"{year}-12-31"), last)
        days = (end - pd.Timestamp(f"{year}-01-01")).days + 1
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            params = {"latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
                      "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
                      "start_date": f"{year}-01-01", "end_date": end.strftime("%Y-%m-%d"),
                      "hourly": ",".join(VARS), "timezone": "UTC"}
            res = rainfall._request(PREVIOUS_RUNS, params, retry_429=False)   # raises at a refusal: stop
            requests += 1
            spent += rainfall.call_weight(len(chunk), days, len(VARS))
            for c, r in zip(chunk, res if isinstance(res, list) else [res], strict=True):
                h = r["hourly"]
                df = pd.DataFrame({"cell_lat": c[0], "cell_lon": c[1], "time": pd.to_datetime(h["time"], utc=True),
                                   **{v: np.asarray(h[v], dtype=float) for v in VARS}})
                df.to_parquet(path(out, c, year), index=False)
            log.info("%d: %d/%d cells, %.1f calls so far", year, min(i + BATCH, len(todo)), len(todo), spent)
            time.sleep(1.0)
    print(json.dumps({"cells": len(cs), "years": list(YEARS), "requests": requests, "calls_by_open_meteo_rule": round(spent, 1),
                      "requests_made_by_host": rainfall.requests_made()}))


def load(cache: Path, cell: tuple[float, float]) -> pd.DataFrame:
    """One cell's hourly weather over all years, indexed by UTC time, with temp24, the mean air temperature over
    the 24 stamps to each hour (NaN unless MIN_COVERAGE of them are finite). Missing cell-years are missing hours."""
    frames = [pd.read_parquet(p) for y in YEARS if (p := path(cache, cell, y)).exists()]
    if not frames:
        return pd.DataFrame(columns=[*VARS, "temp24"])
    w = pd.concat(frames, ignore_index=True).drop_duplicates("time", keep="last").set_index("time").sort_index()
    w = w.reindex(pd.date_range(w.index.min(), w.index.max(), freq="h"))
    t = w["temperature_2m"]
    n = t.notna().rolling(TEMP_WINDOW_H, min_periods=1).sum()
    w["temp24"] = t.rolling(TEMP_WINDOW_H, min_periods=1).mean().where(n >= MIN_COVERAGE * TEMP_WINDOW_H)
    return w[[*VARS, "temp24"]]


def season_means(cache: Path, cs: list[tuple[float, float]]) -> dict:
    """I-bar and T-bar: means of shortwave_radiation and temp24 over every hour of May to September (London),
    2023 to 2026, at all the cells, pooled."""
    sw, tt = [], []
    for c in cs:
        w = load(cache, c)
        if w.empty:
            continue
        local = w.index.tz_convert(TZ)
        m = np.isin(local.month, SEASON) & np.isin(local.year, YEARS)
        sw.append(w.loc[m, "shortwave_radiation"].dropna()); tt.append(w.loc[m, "temp24"].dropna())
    return {"sun_mean_wm2": float(pd.concat(sw).mean()), "temp24_mean_c": float(pd.concat(tt).mean()),
            "sun_hours": int(sum(len(x) for x in sw)), "temp_hours": int(sum(len(x) for x in tt))}


def rate(w: pd.DataFrame, s: float, theta: float, means: dict) -> pd.Series:
    """k(h) = K0 * [(1 - s) * theta ** (temp24 - T-bar) + s * sun / I-bar], per hour; NaN unless both are known,
    so every setting has the same missing hours."""
    sun, t24 = w["shortwave_radiation"], w["temp24"]
    k = K0 * ((1 - s) * np.power(theta, t24 - means["temp24_mean_c"]) + s * sun / means["sun_mean_wm2"])
    return k.where(sun.notna() & t24.notna())


def means(cache_dir: str) -> None:
    print(json.dumps(season_means(Path(cache_dir), cells())))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    {"fetch": fetch, "means": means}[sys.argv[1]](*sys.argv[2:])
