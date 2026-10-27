"""docs/SONDE-SIGNAL-TEST-2026-10.md: the placebo. Each sample reads its sondes at a time shifted by a whole number of
weeks, inside the same May-September season, so the feature keeps each sonde's level and season but loses the day.

A draw gives each sample its own shift: k weeks, k drawn from WEEKS with a random sign, kept only if the shifted day
stays in 1 May to 30 September of the sample's year. Up to TRIES draws per sample; a sample with none valid keeps no
placebo feature (the fallback, 0.0). numpy.random.default_rng(SEED + draw).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEEKS = (2, 3, 4, 5, 6)
DRAWS = 200
SEED = 0
TRIES = 50


def in_season(t: pd.Timestamp, year: int) -> bool:
    d = t.tz_convert("Europe/London").date() if t.tzinfo else t.date()
    return d.year == year and 5 <= d.month <= 9


def shifted_times(sample_times, rng: np.random.Generator) -> list[pd.Timestamp | None]:
    out = []
    for t in sample_times:
        t = pd.Timestamp(t)
        t = t.tz_localize("Europe/London") if t.tzinfo is None else t
        year = t.tz_convert("Europe/London").year
        pick = None
        for _ in range(TRIES):
            k = int(rng.choice(WEEKS)) * (1 if rng.random() < 0.5 else -1)
            s = t + pd.Timedelta(weeks=k)
            if in_season(s, year):
                pick = s
                break
        out.append(pick)
    return out


def rank_p(real: float, placebo: np.ndarray) -> float:
    """Share of placebo gains at or above the real gain, counting the real one (so never 0)."""
    placebo = np.asarray(placebo, dtype=float)
    placebo = placebo[np.isfinite(placebo)]
    return float((1 + (placebo >= real).sum()) / (1 + len(placebo)))
