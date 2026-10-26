"""docs/LAKE-WIND-TEST-2026-10.md: the wind, its fetch, and the projection on a bearing.

    wind.py fetch <out dir>   hourly wind_speed_10m (m/s) and wind_direction_10m at lead 0 from Open-Meteo's
                              Previous Runs API, at the cells of the lake bathing waters with overflows upstream,
                              2023 to 2026, by quarter (dieoff_weather_eval/weather.py's fetch, strict); one parquet
                              per cell-year, wind_leads_<cell>_<year>.parquet

Cells: rainfall.grid_cell of each bathing water's lat and lon in bwq_samples.parquet, as train_ecoli.py places a
sample's rain. Times are UTC. Both variables are the instant at the stamp. Open-Meteo's direction is where the wind
blows from, degrees clockwise from true north.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dieoff_weather_eval"))
import weather as wx

from dipcast import config
from dipcast.ingest.rainfall import grid_cell

VARS = ("wind_speed_10m", "wind_direction_10m")
PREFIX = "wind_leads"
UNITS = {"wind_speed_unit": "ms"}
MIN_COVERAGE = 0.9   # as ecoli.MIN_COVERAGE
# The lake bathing waters with overflows upstream on the frozen data (geometry.py, 24 Oct 2026); score.py checks
# that geometry.py finds the same set in its root.
LAKE_BWS = ("ukf2208-09701", "ukf2208-09702", "ukj2310-11945", "ukd1203-45625", "ukd1203-45650", "ukd1203-45675",
            "ukd1203-45700", "ukd1230-45725", "ukd1230-45750", "ukd1230-45775", "ukd1101-45800")


def cells() -> list[tuple[float, float]]:
    s = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id")
    s = s[s.bw_id.isin(LAKE_BWS)]
    cl, cn = grid_cell(s["lat"].to_numpy(dtype=float), s["lon"].to_numpy(dtype=float))
    return sorted({(round(float(a), 3), round(float(b), 3)) for a, b in zip(cl, cn, strict=True)})


def fetch(out_dir: str) -> None:
    wx.fetch(out_dir, cells(), VARS, PREFIX, UNITS)


def load(cache: Path, cell: tuple[float, float]) -> pd.DataFrame:
    """One cell's hourly wind over all years, on a complete hourly UTC index, with the components of the wind's
    travel: north (v_n) and east (v_e), m/s. Missing cell-years are missing hours."""
    frames = [pd.read_parquet(p) for y in wx.YEARS if (p := wx.path(cache, cell, y, PREFIX)).exists()]
    if not frames:
        return pd.DataFrame(columns=["v_n", "v_e"])
    w = pd.concat(frames, ignore_index=True).drop_duplicates("time", keep="last").set_index("time").sort_index()
    w = w.reindex(pd.date_range(w.index.min(), w.index.max(), freq="h"))
    to = np.radians(w["wind_direction_10m"] + 180.0)
    w["v_n"], w["v_e"] = w["wind_speed_10m"] * np.cos(to), w["wind_speed_10m"] * np.sin(to)
    return w


def towards(speed, direction, bearing):
    """The part of a wind of `speed` from `direction` that blows along `bearing` (all degrees from true north)."""
    return np.asarray(speed, dtype=float) * np.cos(np.radians(np.asarray(direction, dtype=float) + 180.0
                                                              - np.asarray(bearing, dtype=float)))


def window_means(s: pd.Series, ends: pd.DatetimeIndex, hours: int) -> np.ndarray:
    """Mean of the stamps (t - (hours - 1) h ... t] for each t in `ends` (floored to the hour), as ecoli.rain_windows
    windows rain; NaN unless MIN_COVERAGE of the stamps are finite. `s` and `ends` share a time zone."""
    s = s.astype(float)
    s = s[np.isfinite(s.to_numpy())]
    out = np.full(len(ends), np.nan)
    for i, t in enumerate(ends):
        t = pd.Timestamp(t).floor("h")
        w = s.reindex(pd.date_range(t - pd.Timedelta(hours=hours - 1), t, freq="h"))
        if w.notna().mean() >= MIN_COVERAGE:
            out[i] = float(w.mean())
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    {"fetch": fetch}[sys.argv[1]](*sys.argv[2:])
