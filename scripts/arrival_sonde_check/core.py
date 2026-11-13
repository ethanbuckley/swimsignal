"""docs/ARRIVAL-TIME-SONDE-CHECK-2026-11.md, sections 4 to 6: the rise, the events and the implied speed.

Pure functions on arrays and tables: no file is read and no request is made here. Times are minutes since the epoch
(UTC) unless a name says otherwise. A sonde's series is a 15-minute grid: `g0` the first slot's minute, `x` the
readings, NaN where there is no valid reading.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

SLOT = 15                       # minutes between readings
BASE_FROM_H, BASE_TO_H = 30.0, 6.0   # baseline window: [t0 - 30 h, t0 - 6 h)
BASE_MIN_SLOTS = 48             # of its 96
PRE_H = 6.0                     # the search window opens this long before the start
GAP_SLOTS = 4                   # a run of this many invalid slots is a gap
SUSTAIN = (3, 4)                # 3 of the 4 slots from the onset must be above the threshold
QUIET_H = 48.0
H_SLOW_MS, H_MIN_H, H_MAX_H = 0.05, 6.0, 72.0
D_MIN_M, D_MAX_M = 500.0, 30_000.0
MODEL_MS = 0.2
# Threshold = b + max(floor mg/L, rel x b, k x s). The main rule and the two reported beside it.
RULES = {"main": (0.05, 0.5, 3.0), "looser": (0.03, 0.25, 2.0), "stricter": (0.10, 1.0, 5.0)}
VALUE_MAX = 100.0
BAD_QUALITY = ("suspect", "missing")


def horizon_h(d_m: float) -> float:
    """Search horizon after the start, hours: d at 0.05 m/s, at least 6 h, at most 72 h."""
    return float(min(max(d_m / H_SLOW_MS / 3600.0, H_MIN_H), H_MAX_H))


def to_grid(minutes: np.ndarray, values: np.ndarray, quality=None) -> tuple[int, np.ndarray]:
    """(g0, x): the readings on the 15-minute grid from the first slot to the last. A reading is valid when finite,
    0 to 100 mg/L and not of Suspect or Missing quality; duplicates keep the last; a stamp off the grid goes to the
    slot it falls in."""
    minutes = np.asarray(minutes, dtype=np.int64)
    values = np.asarray(values, dtype=float)
    ok = np.isfinite(values) & (values >= 0) & (values <= VALUE_MAX)
    if quality is not None:
        q = np.array([str(v).strip().lower() for v in quality])
        ok &= ~np.isin(q, BAD_QUALITY)
    if len(minutes) == 0:
        return 0, np.array([], dtype=float)
    slot = minutes // SLOT
    g0 = int(slot.min())
    x = np.full(int(slot.max()) - g0 + 1, np.nan)
    order = np.argsort(minutes, kind="stable")
    for i in order:                      # in time order, so a duplicate stamp keeps the last
        x[slot[i] - g0] = values[i] if ok[i] else np.nan
    return g0 * SLOT, x


def _slots(g0: int, n: int, lo_min: float, hi_min: float, closed_hi: bool) -> tuple[int, int]:
    """Index range [a, b) of the slots with lo <= time < hi (or <= hi), cut to the series."""
    a = math.ceil((lo_min - g0) / SLOT)
    b = (math.floor((hi_min - g0) / SLOT) + 1) if closed_hi else math.ceil((hi_min - g0) / SLOT)
    return max(a, 0), min(b, n)


def detect(g0: int, x: np.ndarray, t0: float, h_h: float, rule: str = "main") -> dict:
    """The outcome at reference minute t0 with horizon h_h hours: status one of 'outside', 'no baseline', 'gap',
    'raised before', 'rise', 'no rise'; for a rise, lag_h and peak_lag_h; with a baseline, b, s and theta."""
    n = len(x)
    end = g0 + (n - 1) * SLOT
    if n == 0 or t0 - BASE_FROM_H * 60 < g0 or t0 + h_h * 60 > end:
        return {"status": "outside"}
    a, b_ = _slots(g0, n, t0 - BASE_FROM_H * 60, t0 - BASE_TO_H * 60, closed_hi=False)
    base = x[a:b_]
    base = base[np.isfinite(base)]
    if len(base) < BASE_MIN_SLOTS:
        return {"status": "no baseline"}
    b = float(np.median(base))
    s = 1.4826 * float(np.median(np.abs(base - b)))
    floor, rel, k = RULES[rule]
    theta = b + max(floor, rel * b, k * s)
    out = {"b": b, "s": s, "theta": theta}
    a, b_ = _slots(g0, n, t0 - PRE_H * 60, t0 + h_h * 60, closed_hi=True)
    w = x[a:b_]
    valid = np.isfinite(w)
    above = valid & (w > theta)
    need, span = SUSTAIN
    onset = None
    for i in np.flatnonzero(above):
        nxt = x[a + i:a + i + span]                     # may run past the window: the readings exist or they do not
        if int((np.isfinite(nxt) & (nxt > theta)).sum()) >= need:
            onset = int(i)
            break
    upto = len(w) if onset is None else onset + 1
    run = longest = 0
    for v in valid[:upto]:
        run = 0 if v else run + 1
        longest = max(longest, run)
    if longest >= GAP_SLOTS:
        return {**out, "status": "gap"}
    if onset is None:
        return {**out, "status": "no rise"}
    tau = g0 + (a + onset) * SLOT
    if tau < t0:
        return {**out, "status": "raised before", "lag_h": (tau - t0) / 60.0}
    pk = x[a + onset:a + onset + int(24 * 60 / SLOT) + 1]
    peak = g0 + (a + onset + int(np.nanargmax(pk))) * SLOT
    return {**out, "status": "rise", "lag_h": (tau - t0) / 60.0, "peak_lag_h": (peak - t0) / 60.0,
            "peak": float(np.nanmax(pk))}


CADENCES = (15, 30, 60)                       # amendment 2: the reading intervals a sonde may have, minutes
D_MIN_BY_CADENCE = {15: 500.0, 30: 1000.0, 60: 2000.0}   # the model's travel time is at least 3 readings


def valid_readings(minutes, values, quality=None) -> tuple[np.ndarray, np.ndarray]:
    """(minutes, values) of the valid readings in time order, a duplicate stamp keeping the last. Valid as in
    to_grid. Amendment 2 works on these, not on 15-minute slots."""
    minutes = np.asarray(minutes, dtype=np.int64)
    values = np.asarray(values, dtype=float)
    order = np.argsort(minutes, kind="stable")
    minutes, values = minutes[order], values[order]
    ok = np.isfinite(values) & (values >= 0) & (values <= VALUE_MAX)
    if quality is not None:
        q = np.array([str(v).strip().lower() for v in np.asarray(quality)[order]])
        ok &= ~np.isin(q, BAD_QUALITY)
    last = np.r_[minutes[1:] != minutes[:-1], True] if len(minutes) else np.array([], dtype=bool)
    keep = last & ok
    return minutes[keep].astype(float), values[keep]


def detect_c(tm: np.ndarray, v: np.ndarray, t0: float, h_h: float, rule: str = "main") -> dict:
    """Amendment 2: detect's rules counted in the sonde's own reading interval c (15, 30 or 60 minutes, the median
    gap between valid readings in the baseline window). `tm`, `v`: valid_readings. Adds c to the answer."""
    if len(tm) == 0 or t0 - BASE_FROM_H * 60 < tm[0] or t0 + h_h * 60 > tm[-1]:
        return {"status": "outside"}
    a, b_ = np.searchsorted(tm, [t0 - BASE_FROM_H * 60, t0 - BASE_TO_H * 60], side="left")
    base = v[a:b_]
    if len(base) < 3:
        return {"status": "no baseline"}
    gap = float(np.median(np.diff(tm[a:b_])))
    c = next((k for k in CADENCES if abs(gap - k) <= 0.2 * k), None)
    if c is None or len(base) < 0.5 * 24 * 60 / c:
        return {"status": "no baseline"}
    b = float(np.median(base))
    s = 1.4826 * float(np.median(np.abs(base - b)))
    floor, rel, k = RULES[rule]
    theta = b + max(floor, rel * b, k * s)
    out = {"b": b, "s": s, "theta": theta, "c": c}
    lo, hi = t0 - PRE_H * 60, t0 + h_h * 60
    a = int(np.searchsorted(tm, lo, side="left"))
    b_ = int(np.searchsorted(tm, hi, side="right"))
    wt, wv = tm[a:b_], v[a:b_]
    span = max(45, c)
    expected = span // c + 1                      # 4 readings in 45 min at 15 min; 2 at 30 or 60 min
    need = 3 if expected == 4 else expected
    onset = None
    for i in np.flatnonzero(wv > theta):
        j = int(np.searchsorted(tm, wt[i] + span + 1, side="left"))
        if int((v[a + i:j] > theta).sum()) >= need:
            onset = int(i)
            break
    pts = np.r_[lo - c, wt[:onset + 1]] if onset is not None else np.r_[lo - c, wt, hi + c]
    if (np.diff(pts) >= 60 + c).any():
        return {**out, "status": "gap"}
    if onset is None:
        return {**out, "status": "no rise"}
    tau = wt[onset]
    if tau < t0:
        return {**out, "status": "raised before", "lag_h": (tau - t0) / 60.0}
    j = int(np.searchsorted(tm, tau + 24 * 60, side="right"))
    k_pk = int(np.argmax(v[a + onset:j]))
    return {**out, "status": "rise", "lag_h": (tau - t0) / 60.0, "peak_lag_h": (tm[a + onset + k_pk] - t0) / 60.0,
            "peak": float(v[a + onset + k_pk])}


def find_events(spills: pd.DataFrame, quiet_h: float = QUIET_H) -> pd.DataFrame:
    """The quiet-rule events above one sonde. `spills`: site_id, start, end (minutes), d_m, for every monitored
    overflow upstream. A start at t0 is an event when no spill upstream overlaps [t0 - quiet, t0). The anchor is the
    overflow that starts; of several starting in the same minute, the nearest. Returns t0, site_id, end, d_m."""
    if spills.empty:
        return pd.DataFrame(columns=["t0", "site_id", "end", "d_m"])
    sp = spills.sort_values(["start", "d_m", "site_id"]).reset_index(drop=True)
    start, end = sp["start"].to_numpy(dtype=float), sp["end"].to_numpy(dtype=float)
    # The latest end among spills that start strictly before each start.
    cummax = np.maximum.accumulate(end)
    first_of_start = np.searchsorted(start, start, side="left")
    prev_end = np.where(first_of_start > 0, cummax[np.maximum(first_of_start - 1, 0)], -np.inf)
    keep = (prev_end <= start - quiet_h * 60) & (first_of_start == np.arange(len(sp)))
    ev = sp.loc[keep, ["start", "site_id", "end", "d_m"]].rename(columns={"start": "t0"})
    return ev.reset_index(drop=True)


def others_in_window(spills: pd.DataFrame, t0: float, h_h: float, anchor: str) -> pd.DataFrame:
    """Spills of other overflows upstream that overlap [t0, t0 + H]."""
    m = (spills["site_id"] != anchor) & (spills["start"] <= t0 + h_h * 60) & (spills["end"] >= t0)
    return spills[m]


def implied_speed(starts_min: np.ndarray, d_m: np.ndarray, onset_min: float) -> float:
    """The speed v (m/s) at which the first water from any of the overflows reaches the sonde at the onset:
    min_j(start_j + d_j / v) = onset. NaN when the onset is not after the earliest start. One overflow: d / lag."""
    starts = np.asarray(starts_min, dtype=float) * 60.0
    d = np.asarray(d_m, dtype=float)
    onset = onset_min * 60.0
    live = starts < onset
    if not live.any():
        return float("nan")
    # Each overflow that started before the onset would need speed d / (onset - start); the first arrival is the
    # one that needs the least.
    return float(np.min(d[live] / (onset - starts[live])))


def model_window(lag_h: float, travel_h: float, spill_h: float, grace_h: float = 0.25) -> str:
    """Where a rise begins against the model's window [start + travel_h, end + travel_h], with 15 minutes' grace."""
    if lag_h < travel_h - grace_h:
        return "before"
    return "inside" if lag_h <= travel_h + spill_h + grace_h else "after"


def median_ci(v, draws: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """(median, lo, hi): a 95% percentile interval for the median, bootstrap over the values."""
    v = np.asarray(v, dtype=float)
    rng = np.random.default_rng(seed)
    med = np.median(rng.choice(v, size=(draws, len(v)), replace=True), axis=1)
    return float(np.median(v)), float(np.quantile(med, 0.025)), float(np.quantile(med, 0.975))
