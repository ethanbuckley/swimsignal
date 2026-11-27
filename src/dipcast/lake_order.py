"""Whether today's E. coli estimate is higher, about or lower than usual at a lake bathing water with no monitored
overflow upstream (docs/LAKE-ORDER-NO-OVERFLOW-2026-11.md). One word on today's day; no figure, level or colour.

The estimate is lake-range-v1's likely reading on the average-lake basis with exposure 0, from rain at the lake in the
48 and 24 hours to midday and the date: what bench read 1 scored at these lakes (docs/BENCH-READ-LAKE-RANGE-2026-11.md,
order within a lake on 2012-22 samples it never saw, pass). Usual is the middle third of the spot's own figures on May
to September days of 2023 to 2026, hindcast at lead 0 (scripts/lake_order.py, FILE, frozen), the river order line's
rule. Under the lower cut-point is "lower", over the upper one "higher", else "about".

Only the five spots in FILE, only in season (the read's months), only today (the read was at lead 0). No word with the
model or the file off, or with an input missing. Nothing is logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache

import numpy as np
import pandas as pd

from dipcast import config, lake_range
from dipcast.river_usual import key

log = logging.getLogger(__name__)

RULE = "lake-order-v1"
FILE = config.PROCESSED / "lake_order.v1.json"
SHA256 = "93174f9b494e0c8101e5144514e6739f7ed18c6709dcdabb368cf81ef40440d5"
SEASON = range(5, 10)


@lru_cache(maxsize=1)
def cuts() -> dict:
    """{position key: (low, high)} on log10; empty when the file is missing, is not the frozen one, or was made for
    another model file."""
    if not FILE.exists():
        log.info("lake order word off: %s missing", FILE.name)
        return {}
    raw = FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        log.warning("lake order word off: %s is not the frozen file", FILE.name)
        return {}
    doc = json.loads(raw)
    if doc.get("model_sha256") != lake_range.SHA256:
        return {}
    return {k: (float(v["low"]), float(v["high"])) for k, v in doc["spots"].items()}


def clear_cache() -> None:
    cuts.cache_clear()


def direction(lat: float, lon: float, X: pd.DataFrame, month: int, m: dict | None = None) -> str | None:
    """"higher", "lower" or "about" for X's one row (ecoli.features' frame for today), or None (see the docstring).
    The caller gives it today's row only, at a lake spot with no monitored overflow upstream."""
    if month not in SEASON:
        return None
    c = cuts().get(key(lat, lon))
    m = m if m is not None else lake_range.model()
    if c is None or m is None or X is None or len(X) != 1:
        return None
    x = X[m["cols"]].to_numpy(dtype=float)
    if not np.isfinite(x).all():
        return None
    f = round(float(np.log10(lake_range._quantiles(m, X[m["cols"]], None, qs=(0.5,))[0.5][0])), 3)
    return "lower" if f < c[0] else "higher" if f > c[1] else "about"
