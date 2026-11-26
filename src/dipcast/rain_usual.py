"""Whether the rain in the last two days is more, about or less than usual at a river spot with no monitored overflow
upstream (docs/RAIN-WORD-NO-OVERFLOW-2026-11.md). One word on today's day, beside the rain the page already gives.

Usual is the middle third of the spot's own rain in the 48 hours to midday: on October to April days for a winter day,
on May to September days for a summer one (scripts/rain_usual.py, FILE, frozen). Rain under the lower cut-point is
"less", over the upper one "more", else "about". The word's order was tested on winter samples held back for it at
river monitoring points with no overflow upstream; the summer side rests on a development figure (the record says
which). It is a word about rain: it sets no level, colour or alert, and nothing is logged.

No word at a lake, a point that is not a listed spot, a spot with an overflow upstream (the caller's rule), a spot or
season with no cut-points, a day with no rain figure, or when the file is missing or is not the frozen one."""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache

from dipcast import config
from dipcast.river_usual import key

log = logging.getLogger(__name__)

RULE = "rain-usual-v1"
FILE = config.PROCESSED / "rain_usual.v1.json"
SHA256 = "d7ceb252b32676cfeac617956dd9a19139d8c3f2b06736531e4e1c0623caceac"
WINTER = (10, 11, 12, 1, 2, 3, 4)
SUMMER_ON = True    # the statement's rule: the summer development figure's raw interval, 0.241 to 0.367, lies above 0.15


@lru_cache(maxsize=1)
def cuts() -> dict:
    """{position key: {"winter": (low, high), "summer": (low, high)}}; empty when the file is missing or not frozen."""
    if not FILE.exists():
        log.info("rain word off: %s missing", FILE.name)
        return {}
    raw = FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        log.warning("rain word off: %s is not the frozen file", FILE.name)
        return {}
    return {k: {s: (float(v[s]["low"]), float(v[s]["high"])) for s in ("winter", "summer") if v.get(s)}
            for k, v in json.loads(raw)["spots"].items()}


def clear_cache() -> None:
    cuts.cache_clear()


def direction(lat: float, lon: float, rain_48h_mm: float | None, month: int) -> str | None:
    """"more", "less" or "about" for the rain in the 48 hours to midday as published (0.1 mm), or None (see the
    module's docstring). The caller gives it today's day only, at a river spot with no overflow upstream."""
    if rain_48h_mm is None:
        return None
    season = "winter" if month in WINTER else "summer"
    if season == "summer" and not SUMMER_ON:
        return None
    c = cuts().get(key(lat, lon), {}).get(season)
    if c is None:
        return None
    r = round(float(rain_48h_mm), 1)
    return "less" if r < c[0] else "more" if r > c[1] else "about"
