"""The rules of docs/FLOW-DILUTION-TEST-2026-10.md as functions, so the tests can check them on synthetic data.

Nothing here reads a file or the network. score.py applies these to the real rows; tests/test_flow_dilution_eval.py
checks them. A constant here is part of the statement: changing one after a result is seen must be stated.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

TZ = "Europe/London"

# ---- the candidate ---------------------------------------------------------------------------------------------
K_PRIMARY = 0.5               # exponent on the flow ratio: transport.DILUTION_POWER, the exponent the length ratio
                              # (a flow-ratio proxy) was fitted at in docs/TRANSPORT-FIT-TEST-2026-10.md
K_SECONDARY = 1.0             # plain dilution (concentration inversely proportional to flow); reported only
FACTOR_MIN, FACTOR_MAX = 0.25, 4.0   # the factor (Q_ref / Q)^k is held inside this range

# ---- timing: only flow published before the issue time ----------------------------------------------------------
ISSUE_HOUR_LOCAL = 9          # the lead-0 issue time: 09:00 London time on the sample day ...
ISSUE_BEFORE_SAMPLE_H = 1.0   # ... or 1 h before the sample, if that is earlier
LAG_REALTIME_H = 1.0          # a gauge on the real-time flow feed: readings usable 1 h after they are taken
LAG_ARCHIVE_H = 315.0         # a gauge only in the Hydrology archive: the lag check of 27 Oct 2026 (statement), was 36 h
WINDOW_H = 24.0               # the flow input is the mean over the 24 h ending at issue time minus the lag
SLOT_MIN = 15
MIN_SLOT_SHARE = 0.9          # share of the window's 96 quarter-hour slots that must hold a usable reading
DROP_QUALITY = frozenset({"Suspect", "Rejected", "Missing"})

# ---- the reference flow -----------------------------------------------------------------------------------------
REF_YEARS = tuple(range(2014, 2024))   # ten seasons, all before the first row (2024)
SEASON_MONTHS = (5, 6, 7, 8, 9)
MIN_REF_SEASONS = 5
REF_DAY_SHARE = 0.9           # a reference season counts if at least 90% of its 153 days have a daily mean

# ---- which gauge ------------------------------------------------------------------------------------------------
MAX_ALONG_KM = 25.0           # spot gauge: on the spot's river path, up or down, within this along the network
AREA_RATIO = 2.0              # ... and its catchment within this factor of the spot's (glofas_check's rule)
SAME_SITE_KM = 0.5
OV_MIN_SHARE = 0.5            # per-overflow rule (secondary): the gauge's catchment at least half the spot's

# ---- placebo, gate, margins, bootstrap --------------------------------------------------------------------------
PLACEBO_N = 200
PLACEBO_SEED = 20261027
PLACEBO_MIN_SHIFT_D = 14      # a placebo shift is at least 14 days from the true day, both ways round the season
SEASON_DAYS = 153             # 1 May to 30 September
GATE_ROW_SHARE = 0.6          # river rows with a flow factor (not the fallback)
GATE_SITES = 10               # river bathing waters with a flow factor on at least one row
GATE_EVENTS = 30              # river samples over 900 among rows with a flow factor
B_FLOOR = 0.001               # Brier units: the smallest benefit margin
BOOT = 2000
BOOT_SEED = 1
LEVEL = 0.95
ECOLI_CUTS = (0.10, 0.25, 0.50)   # the site's E. coli band cuts
WARN = 0.25                   # the site's warning line for E. coli

LABELS = ("Better", "Promising, not shown", "No useful difference", "Possible harm", "Harm", "Too uncertain")
HARMFUL = ("Possible harm", "Harm")   # "Possible harm counts as harm" (26 Oct 2026)


# ---- timing -----------------------------------------------------------------------------------------------------
def issue_time(sample_time) -> pd.Timestamp:
    """The lead-0 issue time in UTC: 09:00 London time on the sample's London date, or 1 h before the sample if that
    is earlier."""
    t = pd.Timestamp(sample_time)
    if t.tzinfo is None:
        raise ValueError("sample_time must carry a time zone")
    local = t.tz_convert(TZ)
    nine = pd.Timestamp(local.date(), tz=TZ) + pd.Timedelta(hours=ISSUE_HOUR_LOCAL)
    return min(nine, local - pd.Timedelta(hours=ISSUE_BEFORE_SAMPLE_H)).tz_convert("UTC")


def window(issue_utc: pd.Timestamp, lag_h: float) -> tuple[pd.Timestamp, pd.Timestamp]:
    """(start, end]: the 24 h of readings published by the issue time."""
    end = pd.Timestamp(issue_utc) - pd.Timedelta(hours=lag_h)
    return end - pd.Timedelta(hours=WINDOW_H), end


def clean_readings(df: pd.DataFrame) -> pd.Series:
    """A Hydrology readings table (dateTime, value, quality) as a UTC-indexed series: unusable quality and
    non-numeric values dropped, one value per stamp (the last)."""
    q = df.copy()
    q["value"] = pd.to_numeric(q.get("value"), errors="coerce")
    qual = q["quality"].fillna("") if "quality" in q else pd.Series("", index=q.index)
    q = q[q["value"].notna() & ~qual.isin(DROP_QUALITY)]
    t = pd.to_datetime(q["dateTime"], utc=True)
    s = pd.Series(q["value"].to_numpy(float), index=t).sort_index()
    return s[~s.index.duplicated(keep="last")]


def flow_at_issue(q15: pd.Series, issue_utc: pd.Timestamp, lag_h: float) -> float:
    """Mean flow over the published 24 h window, or NaN if under MIN_SLOT_SHARE of its slots hold a reading.
    `q15` is clean_readings' output. Nothing after the window's end is read."""
    start, end = window(issue_utc, lag_h)
    w = q15[(q15.index > start) & (q15.index <= end)]
    slots = w.index.floor(f"{SLOT_MIN}min").unique()
    need = int(round(WINDOW_H * 60 / SLOT_MIN))
    if len(slots) < MIN_SLOT_SHARE * need:
        return float("nan")
    return float(w.mean())


def lag_for(realtime: bool) -> float:
    return LAG_REALTIME_H if realtime else LAG_ARCHIVE_H


# ---- reference flow and factor ----------------------------------------------------------------------------------
def reference_flow(daily: pd.Series) -> float:
    """The gauge's median daily-mean flow over May-September of REF_YEARS, from seasons with at least REF_DAY_SHARE
    of their days; NaN if fewer than MIN_REF_SEASONS such seasons. `daily` is indexed by date."""
    s = daily.dropna()
    s = s[s > 0]
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    s = s[~s.index.duplicated(keep="last")]
    keep = []
    for y in REF_YEARS:
        part = s[(s.index.year == y) & s.index.month.isin(SEASON_MONTHS)]
        if len(part) >= REF_DAY_SHARE * SEASON_DAYS:
            keep.append(part)
    if len(keep) < MIN_REF_SEASONS:
        return float("nan")
    return float(pd.concat(keep).median())


def flow_factor(q: float, q_ref: float, k: float = K_PRIMARY) -> float:
    """(Q_ref / Q)^k held inside [FACTOR_MIN, FACTOR_MAX]; NaN when either flow is missing or not positive (the
    caller then falls back to the production rule)."""
    if not (np.isfinite(q) and np.isfinite(q_ref)) or q <= 0 or q_ref <= 0:
        return float("nan")
    return float(np.clip((q_ref / q) ** k, FACTOR_MIN, FACTOR_MAX))


def flow_weights(weight: np.ndarray, dilution: np.ndarray, factor: np.ndarray) -> np.ndarray:
    """Production's transport weights with only the dilution term scaled: weight * min(1, dilution * f) / dilution.
    `factor` is (n,) or (n, days); NaN means no gauge or no published flow, and leaves the weight as it is (the
    fallback). Decay, the lake factor and the low-snap factor are untouched, because weight is their product with
    dilution."""
    w = np.asarray(weight, dtype=float)
    d = np.asarray(dilution, dtype=float)
    f = np.asarray(factor, dtype=float)
    if f.ndim == 2:
        w, d = w[:, None], d[:, None]
    scaled = np.where(d > 0, w * np.minimum(1.0, d * np.nan_to_num(f, nan=1.0)) / np.where(d > 0, d, 1.0), 0.0)
    return np.where(np.isnan(f), np.broadcast_to(w, scaled.shape), scaled)


def exposure_lead0(P0: np.ndarray, weights: np.ndarray, travel_h: np.ndarray) -> np.ndarray:
    """replay_ecoli_leads.combine_daily_leads at lead 0, with weights by arrival day. P0 is (n, days); weights is (n,)
    or (n, days), indexed by the arrival day T. A spill on day S arrives on S + kk (share 1 - a) and S + kk + 1
    (share a), kk and a from its travel time."""
    P0 = np.asarray(P0, dtype=float)
    n, d = P0.shape
    W = np.asarray(weights, dtype=float)
    W = np.broadcast_to(W[:, None], (n, d)) if W.ndim == 1 else W
    shift = np.asarray(travel_h, dtype=float) / 24.0
    kk = np.floor(shift).astype(int)
    a = shift - kk
    eff = np.zeros((n, d))
    for i in range(n):
        for extra, frac in ((0, 1 - a[i]), (1, a[i])):
            lag = kk[i] + extra
            if frac == 0 or lag >= d:
                continue
            eff[i, lag:] += frac * P0[i, : d - lag]
    eff = np.clip(eff, 0, 1) * W
    return 1.0 - np.prod(1.0 - eff, axis=0)


# ---- which gauge ------------------------------------------------------------------------------------------------
def choose_spot_gauge(cands: list[dict]) -> dict | None:
    """The spot gauge: candidates on the spot's river path (side 'upstream' or 'downstream', along_km along the
    network), catchment within AREA_RATIO of the spot's, not a part channel, within MAX_ALONG_KM. The nearest along
    the network; a 'Total' or 'Combined' station at the same site goes first (glofas_check.match's order)."""
    ok = [c for c in cands if c.get("side") in ("upstream", "downstream") and not c.get("part")
          and c["along_km"] <= MAX_ALONG_KM and 1 / AREA_RATIO <= c["area_ratio"] <= AREA_RATIO]
    if not ok:
        return None
    ok.sort(key=lambda c: (round(c["along_km"] / SAME_SITE_KM), not c.get("total", False), c["along_km"]))
    return ok[0]


def choose_overflow_gauge(cands: list[dict]) -> dict | None:
    """Secondary rule (the brief's): for one overflow, a gauge downstream of the overflow and upstream of the spot,
    on the spot's river name, with at least OV_MIN_SHARE of the spot's catchment, not a part channel: the one
    nearest the spot along the network."""
    ok = [c for c in cands if c.get("below_overflow") and c.get("side") == "upstream" and c.get("same_river")
          and not c.get("part") and c["area_ratio"] >= OV_MIN_SHARE]
    return min(ok, key=lambda c: c["along_km"]) if ok else None


# ---- placebo ----------------------------------------------------------------------------------------------------
def season_index(day: pd.Timestamp) -> int | None:
    """0 for 1 May ... 152 for 30 September; None outside the season."""
    d = pd.Timestamp(day)
    if d.month not in SEASON_MONTHS:
        return None
    return int((d.normalize().tz_localize(None) - pd.Timestamp(d.year, 5, 1)).days)


def shifted_day(day: pd.Timestamp, shift_d: int) -> pd.Timestamp:
    """The day `shift_d` days on, wrapped round the same year's May-September season. Time of day is kept."""
    i = season_index(day)
    if i is None:
        raise ValueError(f"{day} is outside May-September")
    j = (i + int(shift_d)) % SEASON_DAYS
    return pd.Timestamp(day) + pd.Timedelta(days=j - i)


def placebo_shifts(gauges: list[str], n: int = PLACEBO_N, seed: int = PLACEBO_SEED) -> np.ndarray:
    """(n, len(gauges)) shifts in days, one per gauge per replicate, uniform on [MIN, SEASON_DAYS - MIN]: never
    within 14 days of the true day either way round the season. Gauges in the order given (sorted by the caller)."""
    rng = np.random.default_rng(seed)
    return rng.integers(PLACEBO_MIN_SHIFT_D, SEASON_DAYS - PLACEBO_MIN_SHIFT_D + 1, size=(n, len(gauges)))


def placebo_passes(real_gain: float, placebo_gains) -> bool:
    """The real gain is above the 95th percentile of the placebo gains: above the 190th of 200 when ranked."""
    g = np.sort(np.asarray(placebo_gains, dtype=float))
    rank = int(math.ceil(LEVEL * len(g)))
    return bool(real_gain > g[rank - 1])


# ---- margins (from predictions alone) and labels ----------------------------------------------------------------
def band(p: np.ndarray) -> np.ndarray:
    return np.searchsorted(np.asarray(ECOLI_CUTS), np.asarray(p, dtype=float), side="right")


def margins(p_ref: np.ndarray, p_cand: np.ndarray) -> dict:
    """B and H from predictions alone. s = mean (p_cand - p_ref)^2 is the expected Brier gain if the candidate's
    probabilities were the truth (and the expected loss if the reference's were): the most the change could be worth
    on these rows. B = max(B_FLOOR, s / 2): the candidate must earn half of it. H = B / 2."""
    a, b = np.asarray(p_ref, dtype=float), np.asarray(p_cand, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    s = float(np.mean((b[ok] - a[ok]) ** 2))
    B = max(B_FLOOR, s / 2)
    return {"n": int(ok.sum()), "mean_sq_change": s, "B": B, "H": B / 2,
            "moved_band_share": float(np.mean(band(a[ok]) != band(b[ok]))),
            "moved_warn_share": float(np.mean((a[ok] >= WARN) != (b[ok] >= WARN))),
            "mean_abs_change": float(np.mean(np.abs(b[ok] - a[ok]))),
            "working": "B = max(0.001, mean((p_cand - p_ref)^2) / 2); H = B / 2; river rows, LOSO predictions"}


def label(d: float, lo: float, hi: float, B: float, H: float, secondary_harm: bool = False) -> str:
    """The near-miss label (docs/LAKE-ECOLI-LINE-TEST-2026-10.md, addendum of 26 Oct 2026): the first that fits.
    `secondary_harm`: some secondary check is labelled Possible harm or Harm, which blocks 'Promising, not shown'."""
    if H > B:
        raise ValueError("H must not exceed B")
    if d >= B and lo > 0:
        return "Better"
    if d > 0 and lo <= 0 and lo > -H and not secondary_harm:
        return "Promising, not shown"
    if -H < lo and hi < B:
        return "No useful difference"
    if lo <= -H and d <= 0:
        return "Possible harm"
    if hi < 0:
        return "Harm"
    # "Too uncertain" proper (lo <= -H, hi >= B), and the three cases no label above fits, stated in the doc: d > 0
    # with lo <= -H and hi < B; lo > 0 with d < B <= hi; and a "Promising" blocked by a secondary with hi >= B.
    return "Too uncertain"


def gate(has_factor: np.ndarray, site: np.ndarray, exceed: np.ndarray) -> dict:
    """The coverage gate, on river rows: share with a flow factor, sites with one, exceedances among them."""
    h = np.asarray(has_factor, dtype=bool)
    out = {"river_rows": int(len(h)), "rows_with_factor": int(h.sum()), "share": float(h.mean()) if len(h) else 0.0,
           "sites_with_factor": int(len(set(np.asarray(site)[h]))),
           "events_with_factor": int(np.asarray(exceed, dtype=bool)[h].sum())}
    out["passes"] = (out["share"] >= GATE_ROW_SHARE and out["sites_with_factor"] >= GATE_SITES
                     and out["events_with_factor"] >= GATE_EVENTS)
    return out
