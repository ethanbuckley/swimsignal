"""Site-day feature table: rainfall history and forecast joined to overflows.

One row per (site, day). The same builder serves training (rain from the
archive, labels from event history) and inference (rain from the forecast,
labels absent), so the two cannot drift apart.

Rainfall features are computed per grid cell, then joined to sites by cell.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from dipcast.ingest.rainfall import grid_cell

log = logging.getLogger(__name__)

# The model's day: a UK local date, as swimmers read the site and as live spills are scored
# (forecast_log.observed_spill_days). Training, calibration and the forecast all cut days here, so a model
# is fed the same days it was fitted on (docs/DAY-BOUNDARY-TEST-2026-10.md).
LOCAL_TZ = "Europe/London"
API_DECAY = 0.85  # daily decay of the antecedent precipitation index
MIN_HOURS_PER_DAY = 20  # fewer finite hourly values than this and the day's rain is unknown (NaN)

RAIN_FEATURES = [
    "rain_d", "rain_d1", "rain_d2", "rain_3d", "rain_7d", "rain_30d",
    "api", "max1h_d", "max3h_d", "max6h_d",
]
SEASON_FEATURES = ["doy_sin", "doy_cos"]
SITE_FEATURES = ["log_lta_spills", "log_spill_hours", "edm_pct"]
ALL_FEATURES = RAIN_FEATURES + SEASON_FEATURES + SITE_FEATURES

# Physically, more rain can only raise spill probability. Used by the model.
MONOTONE = {f: 1 for f in RAIN_FEATURES}


def daily_rain_features(rain_hourly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hourly cell rainfall to daily features. Input columns:
    cell_lat, cell_lon, time (tz-aware, any zone), precip_mm. Output one row per cell-day, the day a
    LOCAL_TZ date: UTC archive stamps and the forecast's local ones give the same days. A value stamped
    H is the rain in the hour ending at H, as Open-Meteo stamps it, and a day holds its stamps 00:00 to
    23:00, as Open-Meteo's own daily sums do."""
    df = rain_hourly.copy()
    df["time"] = df["time"].dt.tz_convert(LOCAL_TZ)
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
    # A day with too few finite hours (a null-filled forecast, a truncated series, a
    # partial day at the edge of the pull) has an unknown total, not a dry one.
    short = daily["n_hours"] < MIN_HOURS_PER_DAY
    daily.loc[short, ["rain_d", "max1h_d", "max3h_d", "max6h_d"]] = np.nan
    out = []
    for (cl, cn), d in daily.groupby(["cell_lat", "cell_lon"], sort=False):
        d = d.set_index("day").asfreq("D")  # fill missing days with NaN rows
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


# The annual-return covariates the spill model reads, and what a value missing everywhere becomes.
COVARIATES = ("lta_spills", "spill_hours", "edm_operational_pct")
COVARIATE_DEFAULTS = {"lta_spills": 20.0, "spill_hours": 100.0, "edm_operational_pct": 90.0}
FILLED = "{}_filled"   # the column fill_covariates writes beside each covariate


def fill_covariates(table: pd.DataFrame) -> pd.DataFrame:
    """`table` (the whole overflow table, overflows.build_overflows) with `<covariate>_filled` beside
    each of COVARIATES: the overflow's own value, else the median over every overflow of its company
    in the table, else the median over the table, else COVARIATE_DEFAULTS. The raw columns are left
    as they are, so the pages never show a filled count as the overflow's own; `covariates_filled`
    says which rows had any value filled.

    The fill is over the whole table, not over the overflows upstream of one spot: a median of
    whatever else of its company was upstream gave 16.0 to 41.0 spills a year at the 10 spots with a
    gap, against company-wide medians of 11.2 to 25.4, and YWS02298 34.3 at one spot and 41.0 at
    another. The accuracy baseline (forecast_log._site_climatology) reads these columns too."""
    t = table.copy()
    missing = pd.Series(False, index=t.index)
    for c in COVARIATES:
        v = pd.to_numeric(t[c], errors="coerce") if c in t else pd.Series(np.nan, index=t.index)
        filled = v
        if "company" in t:
            filled = filled.fillna(v.groupby(t["company"]).transform("median"))
        t[FILLED.format(c)] = filled.fillna(v.median()).fillna(COVARIATE_DEFAULTS[c]).astype(float)
        missing |= v.isna()
    t["covariates_filled"] = missing
    return t


def model_covariates(ov: pd.DataFrame) -> pd.DataFrame:
    """The covariate columns to give the spill model for `ov`: the filled ones (fill_covariates)
    where the table has them, else the raw ones, which site_static_features then fills itself."""
    return pd.DataFrame({c: ov[FILLED.format(c)] if FILLED.format(c) in ov else ov.get(c, np.nan)
                         for c in COVARIATES}, index=ov.index)


def site_static_features(sites: pd.DataFrame) -> pd.DataFrame:
    """Per-site covariates from the EA annual returns.

    `sites` needs: site_id, lat, lon, lta_spills, spill_hours, edm_operational_pct.
    Missing values fall back to company medians, then to global medians, over `sites`. The forecast
    gives values already filled over the whole overflow table (fill_covariates); training and the
    offline scripts give their own tables and are filled here."""
    s = sites.copy()
    for c, dflt in COVARIATE_DEFAULTS.items():
        if c not in s:
            s[c] = np.nan
        if "company" in s:
            s[c] = s[c].fillna(s.groupby("company")[c].transform("median"))
        s[c] = s[c].fillna(s[c].median()).fillna(dflt)
    s["log_lta_spills"] = np.log1p(s["lta_spills"].clip(lower=0))
    s["log_spill_hours"] = np.log1p(s["spill_hours"].clip(lower=0))
    s["edm_pct"] = s["edm_operational_pct"].clip(0, 100) / 100.0
    cl, cn = grid_cell(s["lat"].to_numpy(), s["lon"].to_numpy())
    s["cell_lat"], s["cell_lon"] = cl, cn
    return s[["site_id", "lat", "lon", "cell_lat", "cell_lon", *SITE_FEATURES]]


def spill_days(events: pd.DataFrame, max_span_days: int = 60) -> pd.DataFrame:
    """Explode events (tz-aware start and end) to the set of (site_id, day) with at least one spill,
    the days LOCAL_TZ dates."""
    ev = events.dropna(subset=["event_start"]).copy()
    # Wall-clock dates, so a span across a clock change counts whole days (a 23- or 25-hour day apart).
    d0 = ev["event_start"].dt.tz_convert(LOCAL_TZ).dt.tz_localize(None).dt.floor("D")
    d1 = ev["event_end"].fillna(ev["event_start"]).dt.tz_convert(LOCAL_TZ).dt.tz_localize(None).dt.floor("D")
    n = ((d1 - d0).dt.days.clip(lower=0, upper=max_span_days) + 1).to_numpy()
    site = np.repeat(ev["site_id"].to_numpy(), n)
    base = np.repeat(d0.to_numpy().astype("datetime64[D]"), n)
    offs = np.concatenate([np.arange(k) for k in n]) if len(n) else np.array([], dtype=int)
    day = base + offs.astype("timedelta64[D]")
    out = pd.DataFrame({"site_id": site, "day": pd.to_datetime(day).tz_localize(LOCAL_TZ)})
    return out.drop_duplicates()


def _zone(days) -> str:
    """The time zone of a column or index of days, "naive" without one, "not dates" for anything else."""
    days = pd.Series(days)
    if not pd.api.types.is_datetime64_any_dtype(days):
        return "not dates"
    return str(days.dt.tz) if days.dt.tz is not None else "naive"


def build_site_days(sites: pd.DataFrame, daily_rain: pd.DataFrame, days: pd.DatetimeIndex,
                    labels: pd.DataFrame | None = None) -> pd.DataFrame:
    """Cross sites with days, join rain by cell and day, attach labels if given. The three must give
    their days in one zone: a UTC grid joined to local days finds no rain on any summer day, since local
    midnight is 23:00 UTC then, and pandas does not complain."""
    zones = {"days": _zone(days), "rain": _zone(daily_rain["day"])}
    if labels is not None:
        zones["labels"] = _zone(labels["day"])
    if len(set(zones.values())) > 1:
        raise ValueError(f"build_site_days: days in different zones {zones}; the model's day is {LOCAL_TZ}")
    st = site_static_features(sites)
    grid = st.merge(pd.DataFrame({"day": days}), how="cross")
    grid = grid.merge(daily_rain, on=["cell_lat", "cell_lon", "day"], how="left")
    if labels is not None:
        lab = labels.assign(y=1)
        grid = grid.merge(lab, on=["site_id", "day"], how="left")
        grid["y"] = grid["y"].fillna(0).astype(np.int8)
    return grid
