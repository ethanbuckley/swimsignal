"""The UTC-day feature rows the 13 September 2026 spill model files were fitted on, frozen for checking them.

main's `spill_model.pkl` and `spill_model_holdout_2025.pkl` (8ac835f) were fitted on United Utilities site-days cut
at UTC midnight. `features.daily_rain_features`, `features.spill_days` and `features.build_site_days` may move to
another day boundary for new models; a check of the old files must still rebuild the rows those files saw. These are
copies of those three functions as they stood when `scripts/check_model_provenance.py` reproduced every stored
offset exactly (main b37bfa6, which gives the same rows as 8ac835f's code: site_n equal at every overflow). Their
constants are fixed here, not read from `features`. Do not change them and do not use them for new models.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dipcast.model.features import site_static_features

API_DECAY = 0.85
MIN_HOURS_PER_DAY = 20
DAY_TZ = "UTC"


def daily_rain_features(rain_hourly: pd.DataFrame) -> pd.DataFrame:
    """Hourly cell rain (cell_lat, cell_lon, time in UTC, precip_mm) to one row per cell and UTC day."""
    df = rain_hourly.copy()
    df["time"] = df["time"].dt.tz_convert(DAY_TZ)
    df["day"] = df["time"].dt.floor("D")
    df = df.sort_values(["cell_lat", "cell_lon", "time"])
    df = df[~df.duplicated(["cell_lat", "cell_lon", "time"], keep="last")]
    df["precip_mm"] = pd.to_numeric(df["precip_mm"], errors="coerce").astype(float)
    df["ok"] = np.isfinite(df["precip_mm"])
    g = df.groupby(["cell_lat", "cell_lon"], sort=False)
    df["r3"] = g["precip_mm"].transform(lambda s: s.rolling(3, min_periods=1).sum())
    df["r6"] = g["precip_mm"].transform(lambda s: s.rolling(6, min_periods=1).sum())
    daily = (
        df.groupby(["cell_lat", "cell_lon", "day"], sort=True)
        .agg(rain_d=("precip_mm", "sum"), max1h_d=("precip_mm", "max"),
             max3h_d=("r3", "max"), max6h_d=("r6", "max"), n_hours=("ok", "sum"))
        .reset_index()
    )
    short = daily["n_hours"] < MIN_HOURS_PER_DAY
    daily.loc[short, ["rain_d", "max1h_d", "max3h_d", "max6h_d"]] = np.nan
    out = []
    for (cl, cn), d in daily.groupby(["cell_lat", "cell_lon"], sort=False):
        d = d.set_index("day").asfreq("D")
        r = d["rain_d"]
        d["rain_d1"] = r.shift(1)
        d["rain_d2"] = r.shift(2)
        d["rain_3d"] = r.rolling(3, min_periods=1).sum()
        d["rain_7d"] = r.rolling(7, min_periods=1).sum()
        d["rain_30d"] = r.rolling(30, min_periods=1).sum()
        api = np.zeros(len(r))
        acc = 0.0
        for i, v in enumerate(r.to_numpy()):
            acc = API_DECAY * acc + (0.0 if np.isnan(v) else v)
            api[i] = acc
        d["api"] = api
        d["cell_lat"], d["cell_lon"] = cl, cn
        out.append(d.reset_index())
    res = pd.concat(out, ignore_index=True)
    doy = res["day"].dt.dayofyear
    res["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    res["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return res


def spill_days(events: pd.DataFrame, max_span_days: int = 60) -> pd.DataFrame:
    """Events (UTC start and end) to the set of (site_id, UTC day) with at least one spill."""
    ev = events.dropna(subset=["event_start"]).copy()
    start = ev["event_start"].dt.tz_convert(DAY_TZ)
    d0 = start.dt.floor("D")
    d1 = ev["event_end"].dt.tz_convert(DAY_TZ).fillna(start).dt.floor("D")
    n = ((d1 - d0).dt.days.clip(lower=0, upper=max_span_days) + 1).to_numpy()
    site = np.repeat(ev["site_id"].to_numpy(), n)
    base = np.repeat(d0.dt.tz_convert(None).to_numpy().astype("datetime64[D]"), n)
    offs = np.concatenate([np.arange(k) for k in n]) if len(n) else np.array([], dtype=int)
    day = base + offs.astype("timedelta64[D]")
    out = pd.DataFrame({"site_id": site, "day": pd.to_datetime(day).tz_localize(DAY_TZ)})
    return out.drop_duplicates()


def build_site_days(sites: pd.DataFrame, daily_rain: pd.DataFrame, days: pd.DatetimeIndex,
                    labels: pd.DataFrame | None = None) -> pd.DataFrame:
    """Cross sites with UTC days, join rain by cell and day, attach labels if given."""
    st = site_static_features(sites)
    grid = st.merge(pd.DataFrame({"day": days}), how="cross")
    grid = grid.merge(daily_rain, on=["cell_lat", "cell_lon", "day"], how="left")
    if labels is not None:
        lab = labels.assign(y=1)
        grid = grid.merge(lab, on=["site_id", "day"], how="left")
        grid["y"] = grid["y"].fillna(0).astype(np.int8)
    return grid
