"""docs/SONDE-SIGNAL-TEST-2026-10.md: the margins B and H from predictions alone, and the near-miss labels.

Labels are those of the 26 October 2026 addendum to docs/LAKE-ECOLI-LINE-TEST-2026-10.md, in its order, with its
note: "Harm" cannot come first in that order, so "a check labelled harm" means "Possible harm" or "Harm".
"""

from __future__ import annotations

import numpy as np

ECOLI_CUTS = (0.10, 0.25, 0.50)    # src/dipcast/site/levels.js
SHARE = 0.05                       # the share of forecasts moved one band
B_FLOOR = 0.0005                   # the margin the soil-moisture leads test used
HARMFUL = {"Possible harm", "Harm"}


def band_mids(cuts=ECOLI_CUTS) -> np.ndarray:
    edges = np.array([0.0, *cuts, 1.0])
    return (edges[:-1] + edges[1:]) / 2


def one_band_move(p: np.ndarray, cuts=ECOLI_CUTS) -> np.ndarray:
    """For each forecast, the mid-point of the adjacent band on the side of the nearer cut (the only adjacent band
    for the first and last bands)."""
    p = np.asarray(p, dtype=float)
    c = np.asarray(cuts)
    mids = band_mids(cuts)
    k = np.searchsorted(c, p, side="right")          # band index 0..len(cuts)
    lower = np.where(k > 0, c[np.maximum(k - 1, 0)], -np.inf)
    upper = np.where(k < len(c), c[np.minimum(k, len(c) - 1)], np.inf)
    go_down = (p - lower) < (upper - p)
    j = np.where(k == 0, 1, np.where(k == len(c), len(c) - 1, np.where(go_down, k - 1, k + 1)))
    return mids[j]


def margin_b(p_ref: np.ndarray, share: float = SHARE, floor: float = B_FLOOR) -> dict:
    """B = share x mean (p - p')^2, where p' is the one-band move: the Brier gain if that share of forecasts moved
    one band and the moved forecast were right (a moved forecast p' that is calibrated gains (p - p')^2 in
    expectation). Never below `floor`. H = B. Predictions only: no outcome is read."""
    p = np.asarray(p_ref, dtype=float)
    p = p[np.isfinite(p)]
    sq = (p - one_band_move(p)) ** 2
    raw = float(share * sq.mean()) if len(p) else float("nan")
    b = max(raw, floor) if np.isfinite(raw) else floor
    return {"n": int(len(p)), "mean_move_sq": float(sq.mean()) if len(p) else None, "share": share,
            "B_raw": raw, "B": b, "H": b, "floor_used": bool(not np.isfinite(raw) or raw < floor)}


def label(d: float, lo: float, hi: float, b: float, h: float, secondary_harm: bool = False) -> str:
    """The first label that fits, in the addendum's order. d is the gain (reference Brier minus candidate Brier),
    (lo, hi) its interval."""
    assert 0 < h <= b, "H must be positive and no larger than B"
    if d >= b and lo > 0:
        return "Better"
    if d > 0 and lo <= 0 and lo > -h and not secondary_harm:
        return "Promising, not shown"
    if -h < lo and hi < b:
        return "No useful difference"
    if lo <= -h and d <= 0:
        return "Possible harm"
    if hi < 0:
        return "Harm"
    if lo <= -h and hi >= b:
        return "Too uncertain"
    return "Unlabelled"   # e.g. d > 0, lo <= -h, hi < b: reported as it is
