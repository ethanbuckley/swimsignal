"""docs/SONDE-SIGNAL-TEST-2026-10.md: the sonde feature for one sample, with no reading after the cut.

The cut is t* = sample time - LAG_H (the publication lag). The feature is the log of the median reading in the
NOW_H hours ending at t* minus the log of the median reading in the BASE_DAYS days before that window: an anomaly
against the sonde's own recent level, in natural-log units, clipped to +/- CLIP. Readings are floored at FLOOR before
the log, so a near-zero baseline cannot blow up the ratio.

A reading counts when its time is in the window, its value is finite and inside PLAUSIBLE, and its quality is not
in BAD_QUALITY. The feature is missing unless the now window holds MIN_NOW readings and the baseline MIN_BASE.
A missing feature falls back to 0.0, "as usual", which leaves the candidate's estimate on its other inputs; the
share of fallbacks is reported.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

LAG_H = 6.0            # primary publication lag
ALT_LAG_H = 24.0       # sensitivity, reported in full
NOW_H = 2.0
MIN_NOW = 4            # of 8 fifteen-minute slots
BASE_DAYS = 30
MIN_BASE = 672         # 7 days of fifteen-minute readings, of 2,872 possible
CLIP = 3.0
FLOOR = {"turbidity": 0.1, "ammonium": 0.01}               # NTU, mg/L
PLAUSIBLE = {"turbidity": (0.0, 4000.0), "ammonium": (0.0, 100.0)}
BAD_QUALITY = {"Suspect", "Missing"}


def clean(readings: pd.DataFrame, prop: str) -> pd.Series:
    """A sorted UTC series from a readings table with columns dateTime, value and, optionally, quality. Times
    without a zone are UTC, as the API writes them (water_temperature.py)."""
    if readings.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC"))
    t = pd.to_datetime(readings["dateTime"], utc=True)
    v = pd.to_numeric(readings["value"], errors="coerce")
    lo, hi = PLAUSIBLE[prop]
    ok = np.isfinite(v.to_numpy()) & (v >= lo).to_numpy() & (v <= hi).to_numpy()
    if "quality" in readings:
        ok &= ~readings["quality"].isin(BAD_QUALITY).to_numpy()
    s = pd.Series(v.to_numpy()[ok], index=pd.DatetimeIndex(t[ok]))
    return s[~s.index.duplicated(keep="last")].sort_index()


def cut_time(sample_time, lag_h: float = LAG_H) -> pd.Timestamp:
    t = pd.Timestamp(sample_time)
    t = t.tz_localize("Europe/London") if t.tzinfo is None else t
    return t.tz_convert("UTC") - pd.Timedelta(hours=lag_h)


def anomaly(series: pd.Series, t_cut: pd.Timestamp, prop: str) -> float:
    """The feature at the cut, or NaN. Only readings stamped at or before `t_cut` are read."""
    now_lo = t_cut - pd.Timedelta(hours=NOW_H)
    base_lo = now_lo - pd.Timedelta(days=BASE_DAYS)
    s = series[series.index <= t_cut]          # nothing after the cut, whatever the slices below do
    now = s[s.index > now_lo]
    base = s[(s.index > base_lo) & (s.index <= now_lo)]
    if len(now) < MIN_NOW or len(base) < MIN_BASE:
        return math.nan
    f = FLOOR[prop]
    a = math.log(max(float(now.median()), f)) - math.log(max(float(base.median()), f))
    return float(np.clip(a, -CLIP, CLIP))


def sample_feature(sample_time, ordered: list[str], series: dict[str, pd.Series], prop: str,
                   lag_h: float = LAG_H, at=None) -> tuple[float, str | None]:
    """(feature, station id) from the first sonde in `ordered` with a valid feature; (NaN, None) when none has one.
    `at`, when given, replaces the sample time for the lookup only (the placebo)."""
    t_cut = cut_time(sample_time if at is None else at, lag_h)
    for sid in ordered:
        s = series.get(sid)
        if s is None or s.empty:
            continue
        a = anomaly(s, t_cut, prop)
        if math.isfinite(a):
            return a, sid
    return math.nan, None


def with_fallback(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(values with NaN as 0.0, mask of the rows that had a reading)."""
    v = np.asarray(values, dtype=float)
    have = np.isfinite(v)
    return np.where(have, v, 0.0), have
