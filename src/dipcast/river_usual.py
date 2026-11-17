"""Whether a river spot's E. coli figure is higher or lower than usual there
(docs/RIVER-ORDER-LINE-PROPOSAL-2026-11.md, decided 17 November 2026): one word on each in-season day, beside the
chance of a sample over 900 that the page already gives. The figure and the level are unchanged.

Usual is the middle third of the spot's own figures on May to September days of 2023 to 2026, hindcast at lead 0
(scripts/river_usual.py). FILE holds each spot's two cut-points, keyed by its position in the spot lists, and is
frozen before 1 May 2027 so the 2027 season can judge the words. A figure under the lower cut-point is "lower", over
the upper one "higher", else "about".

No word out of season, at a lake, for a point that is not a listed spot, for a spot with no cut-points, or when the
file is missing or is not the frozen one. It sets no level, colour or alert, and nothing is logged."""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache

from dipcast import config

log = logging.getLogger(__name__)

RULE = "river-usual-v1"
FILE = config.PROCESSED / "river_usual.v1.json"
SHA256 = "feaa2fa3629377ca0f246f5208f4673af0bb484292491a27566d785f97337c0f"
SEASON = range(5, 10)      # the months the figure is tested for


def key(lat: float, lon: float) -> str:
    """A spot's position as the file keys it: five decimal places, about a metre."""
    return f"{float(lat):.5f},{float(lon):.5f}"


@lru_cache(maxsize=1)
def cuts() -> dict:
    """{position key: (lower cut-point, upper cut-point)}; empty when the file is missing or not the frozen one."""
    if not FILE.exists():
        log.info("river usual off: %s missing", FILE.name)
        return {}
    raw = FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        log.warning("river usual off: %s is not the frozen file", FILE.name)
        return {}
    return {k: (float(v["low"]), float(v["high"])) for k, v in json.loads(raw)["spots"].items()}


def clear_cache() -> None:
    cuts.cache_clear()


def direction(lat: float, lon: float, p: float | None, month: int) -> str | None:
    """"higher", "lower" or "about" for a figure as published (three decimal places), or None: see the module's
    docstring for where there is no word."""
    if p is None or month not in SEASON:
        return None
    c = cuts().get(key(lat, lon))
    if c is None:
        return None
    return "lower" if p < c[0] else "higher" if p > c[1] else "about"
