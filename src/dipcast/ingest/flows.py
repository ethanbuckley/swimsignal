"""River state from Environment Agency gauges.

Near-real-time *flow* is only published for ~350 stations, so we use *level*
stations (thousands) and express the latest level relative to the station's
typical range. That gives a 0..1+ "river state" index good enough to scale
travel speed and to show the swimmer whether the river is up.
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit, urlunsplit

import httpx
from pyproj import Transformer
import numpy as np
import shapely
from shapely import make_valid
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union

from dipcast import config
from dipcast.network.names import WELSH, river_words

log = logging.getLogger(__name__)

MAX_READING_AGE_H = 24.0   # an older "latest" reading is not today's level: a gauge can go quiet for weeks
EA_TIMEOUT_S = 4.0          # the EA API is sometimes very slow; never let it stall a forecast
_STATION_CACHE: dict[tuple[float, float], tuple[float, RiverState | None]] = {}
_STATION_TTL_S = 1800.0
_EA_HOST = urlsplit(config.EA_FLOOD_MONITORING).hostname


def _ea_link(url: str) -> str | None:
    """A link the EA API gave us, as https; None if it points off the EA's host.

    The flood-monitoring API writes its own links as http://, and those answer 301 to
    https://. httpx does not follow redirects, so the http form always failed. Rewriting
    the scheme avoids the redirect, and checking the host means we never fetch a URL
    from a response body on some other server.
    """
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or u.hostname != _EA_HOST:
        return None
    return urlunsplit(u._replace(scheme="https"))


@dataclass
class RiverState:
    station: str
    river: str | None
    lat: float
    lon: float
    level_m: float | None
    typical_low: float | None
    typical_high: float | None
    observed_at: str | None
    rloi: str | None = None   # the station's id on check-for-flooding.service.gov.uk, for a link
    measure: str | None = None   # the level measure's id ("F1903-level-stage-i-15_min-m"), for its recent readings

    @property
    def index(self) -> float | None:
        """0 at typical low, 1 at typical high; may exceed 1 in flood."""
        if None in (self.level_m, self.typical_low, self.typical_high):
            return None
        rng = self.typical_high - self.typical_low
        if rng <= 0:
            return None
        return (self.level_m - self.typical_low) / rng

    def age_hours(self, now: datetime | None = None) -> float | None:
        """Hours since the reading was taken; None if the time is missing or unreadable."""
        if not self.observed_at:
            return None
        try:
            t = datetime.fromisoformat(str(self.observed_at))   # Python 3.11+ reads the trailing Z
        except ValueError:
            return None
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        return ((now or datetime.now(UTC)) - t).total_seconds() / 3600.0

    def is_stale(self, now: datetime | None = None, max_age_h: float = MAX_READING_AGE_H) -> bool:
        """The EA's "latest" reading can be weeks old (Salisbury's was 708 h on 2 Oct 2026); one
        older than `max_age_h`, or with no time, is not the river's level now."""
        age = self.age_hours(now)
        return age is None or age > max_age_h

    @property
    def label(self) -> str:
        i = self.index
        if i is None:
            return "unknown"
        if i < 0.15:
            return "low"
        if i < 0.6:
            return "normal"
        if i < 1.0:
            return "high"
        return "very high"


def nearest_level_station(lat: float, lon: float, dist_km: int = 15, river: str | None = None) -> RiverState | None:
    import time
    key = (round(lat, 2), round(lon, 2), _river_words(river))
    hit = _STATION_CACHE.get(key)
    if hit and time.time() - hit[0] < _STATION_TTL_S:
        return hit[1]
    try:
        st = _nearest_level_station(lat, lon, dist_km, river)
    except Exception as e:  # noqa: BLE001 - enrichment only; a forecast must never fail on it
        log.warning("river state lookup failed: %s", e)
        st = None
    _STATION_CACHE[key] = (time.time(), st)
    return st


def reading_fields(st: RiverState, now: datetime | None = None, max_age_h: float = MAX_READING_AGE_H) -> dict:
    """A gauge reading as the site and the API publish it. A reading over `max_age_h` old (or
    with no time) is not the level now: its value moves to `last_level_m`, and `level_m` and
    `index` become None and `label` "unknown", so that nothing shows it as current."""
    age = st.age_hours(now)
    stale = age is None or age > max_age_h
    out = {"station": st.station, "river": st.river, "level_m": st.level_m, "typical_low_m": st.typical_low,
           "typical_high_m": st.typical_high, "index": None if st.index is None else round(st.index, 2),
           "label": st.label, "observed_at": st.observed_at,
           "age_hours": None if age is None else round(age, 1), "stale": stale}
    if stale:
        out.update(last_level_m=out["level_m"], level_m=None, index=None, label="unknown")
    return out


# The distinctive words of a watercourse name, Welsh names read as English ("Afon Gwy" -> {wye}).
_river_words = river_words


def _nearest_level_station(lat: float, lon: float, dist_km: int = 15, river: str | None = None) -> RiverState | None:
    """The spot's gauge (station_pick) with its latest reading asked of that station alone: three
    requests at most. The site asks for every gauge's reading at once instead (level_lookup)."""
    try:
        pick = station_pick(lat, lon, dist_km, river)
    except httpx.HTTPError as e:
        log.warning("EA stations lookup failed: %s", e)
        return None
    if pick is None:
        return None
    ref = pick["ref"]
    readings = {}
    try:
        rr = httpx.get(f"{config.EA_FLOOD_MONITORING}/id/stations/{ref}/readings",
                       params={"latest": ""}, headers=config.EA_HEADERS, timeout=EA_TIMEOUT_S)
        rr.raise_for_status()
        readings = _readings_by_measure(rr.json().get("items", []))
    except (httpx.HTTPError, ValueError) as e:
        log.warning("EA readings failed for %s: %s", ref, e)
    return river_state(pick, readings)


def _num(x) -> float | None:
    if isinstance(x, dict):
        x = x.get("value")
    if isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _measure_id(url) -> str | None:
    m = str(url or "").rstrip("/").rsplit("/", 1)[-1]
    return m if _MEASURE_ID.fullmatch(m) else None


# The order a gauge's level measures are tried in. The stage scale's usual range is for the stage
# (a downstream or tidal level has its own), above the stage datum: "m" and "mASD" are that, "mAOD"
# is above sea level and equal to it only where the scale's datum is 0 (Trowlock Island, 3 Oct 2026),
# and "---" has no unit. Kingston (3400TH) publishes its stage in both mASD and mAOD.
_UNIT_ORDER = {"m": 0, "mASD": 0, "mAOD": 1}


def _level_measures(station: dict) -> list[str]:
    """A station's level measure ids from the stations list, in the order to try them: stage before
    any other level, then by unit (_UNIT_ORDER), then as listed."""
    ms = station.get("measures")
    ms = ms if isinstance(ms, list) else [ms] if isinstance(ms, dict) else []
    ranked = []
    for i, m in enumerate(ms):
        mid = _measure_id(m.get("@id")) if isinstance(m, dict) else None
        if mid is None or m.get("parameter") != "level":
            continue
        ranked.append((0 if m.get("qualifier") == "Stage" else 1, _UNIT_ORDER.get(str(m.get("unitName")), 2), i, mid))
    return [r[-1] for r in sorted(ranked)]


def station_pick(lat: float, lon: float, dist_km: int = 15, river: str | None = None) -> dict | None:
    """The gauge a spot's level comes from, without a reading: the closest station with a stage
    scale on the spot's own river, if its name is known and any station carries it, else the
    closest with a scale; its usual range, and its level measures in the order to try them
    (_level_measures). One request for the stations near the point and, where the station links its
    scale instead of embedding it, one for the scale. `complete` is False when that scale could not
    be fetched, so that a pick without its range is not kept for later builds. None when no station
    nearby has a scale; raises when the stations request fails."""
    r = httpx.get(f"{config.EA_FLOOD_MONITORING}/id/stations",
                  params={"lat": lat, "long": lon, "dist": dist_km, "parameter": "level",
                          "type": "SingleLevel"}, headers=config.EA_HEADERS, timeout=EA_TIMEOUT_S)
    r.raise_for_status()
    items = r.json().get("items", [])
    # Without the river's name, Burnsall on the Wharfe got Hebden Beck, a tributary 3 km away, over
    # Netherside Hall on the Wharfe 6 km up (1 Oct 2026).
    want = _river_words(river)
    best = None
    for s in items:
        if not s.get("stageScale"):
            continue  # accept dict or URL; both are resolved below
        same = bool(want) and bool(want & _river_words(s.get("riverName")))
        d = (float(s["lat"]) - lat) ** 2 + (float(s["long"]) - lon) ** 2
        rank = (0 if same else 1, d)
        if best is None or rank < best[0]:
            best = (rank, s)
    if best is None:
        return None
    s = best[1]
    scale, complete = s.get("stageScale", {}), True
    if isinstance(scale, str):  # some stations link to the scale instead of embedding it
        url = _ea_link(scale)
        try:
            if url is None:
                raise ValueError(f"stage scale link is not on the EA host: {scale}")
            rs = httpx.get(url, params={"_view": "full"}, headers=config.EA_HEADERS, timeout=EA_TIMEOUT_S)
            rs.raise_for_status()
            scale = rs.json().get("items", {})
            if isinstance(scale, list):
                scale = scale[0] if scale else {}
        except (httpx.HTTPError, ValueError) as e:
            log.warning("EA stage scale fetch failed: %s", e)
            scale, complete = {}, url is None   # a link off the EA's host will not improve
    if not isinstance(scale, dict):
        scale = {}
    ref, rloi = s.get("stationReference"), s.get("RLOIid")
    return {"ref": ref, "station": s.get("label", ref), "river": s.get("riverName"),
            "lat": float(s["lat"]), "lon": float(s["long"]),
            "typical_low": _num(scale.get("typicalRangeLow")), "typical_high": _num(scale.get("typicalRangeHigh")),
            "rloi": str(rloi) if rloi not in (None, "") else None, "measures": _level_measures(s), "complete": complete}


def _readings_by_measure(items: list) -> dict[str, tuple[str | None, float]]:
    """Readings as {measure id: (time, value)}, the first of each measure kept. A reading whose value
    is not one number is left out (one in the national list had a list on 3 Oct 2026)."""
    out = {}
    for rd in items:
        if not isinstance(rd, dict):
            continue
        m, v = _measure_id(rd.get("measure")), rd.get("value")
        if m and m not in out and "-level-" in m and isinstance(v, (int, float)) and not isinstance(v, bool):
            out[m] = (rd.get("dateTime"), float(v))
    return out


def river_state(pick: dict, readings: dict[str, tuple[str | None, float]]) -> RiverState:
    """A picked gauge with its latest reading: the first of its level measures (in pick order) that
    has one. With no measure list (a stations list without them), any level reading of the station."""
    order = pick.get("measures") or sorted((m for m in readings if m.startswith(f"{pick['ref']}-level-")),
                                           key=lambda m: ("-level-stage-" not in m, _UNIT_ORDER.get(m.rsplit("-", 1)[-1], 2), m))
    measure = next((m for m in order if m in readings), None)
    observed, level = readings[measure] if measure else (None, None)
    return RiverState(station=pick["station"], river=pick["river"], lat=pick["lat"], lon=pick["lon"],
                      level_m=level, typical_low=pick["typical_low"], typical_high=pick["typical_high"],
                      observed_at=observed, rloi=pick["rloi"], measure=measure)


LATEST_TIMEOUT_S = 30.0   # one answer for every level gauge in England: 1.3 MB in about 3 s on 3 Oct 2026


def latest_levels() -> dict[str, tuple[str | None, float]]:
    """The latest reading of every level measure the EA publishes, in one request instead of one a
    gauge: {measure id: (time, metres)}, about 4,100 measures on 3 Oct 2026. Raises on a failed
    request, so that "no reading" and "could not ask" stay apart."""
    r = httpx.get(f"{config.EA_FLOOD_MONITORING}/data/readings", params={"latest": "", "parameter": "level"},
                  headers=config.EA_HEADERS, timeout=LATEST_TIMEOUT_S)
    r.raise_for_status()
    return _readings_by_measure(r.json().get("items", []))


PICK_TTL_S = 7 * 86400        # a spot's gauge and its usual range are asked again after a week ...
PICK_KEEP_S = 30 * 86400      # ... and an older pick is used, past its week, while that lookup fails


def level_lookup(path, now: float | None = None, latest=None, pick=None):
    """The site's gauge lookup: every reading in one request (latest_levels), and each spot's gauge
    (station_pick) kept in the JSON file at `path` for PICK_TTL_S, so that a build asks the EA a
    handful of times, not three times a spot. On 3 Oct 2026 those per-spot requests, about 300 a
    build, met HTTP 403 or a timeout 8 to 79 times a build, and the national flood list asked after
    them was refused in 6 of 8 builds. Returns (lookup, save): lookup(lat, lon, dist_km, river) gives a RiverState or None, as
    nearest_level_station does, and save() writes the picks back. If the readings request fails,
    every spot is left without a reading (logged once) rather than asking gauge by gauge."""
    import json
    import threading
    import time
    from pathlib import Path

    path, now = Path(path), time.time() if now is None else now
    latest, pick = latest or latest_levels, pick or station_pick
    try:
        kept = json.loads(path.read_text())
        kept = kept if isinstance(kept, dict) else {}
    except (OSError, ValueError):
        kept = {}
    try:
        readings = latest()
    except Exception as e:  # noqa: BLE001 - observations beside the forecast must not sink the build
        log.warning("EA latest levels failed, so no spot gets a reading this time: %s", e)
        readings = None
    lock = threading.Lock()

    def lookup(lat: float, lon: float, dist_km: int = 15, river: str | None = None) -> RiverState | None:
        if readings is None:
            return None   # nothing to show, so no stations request either
        key = f"{lat:.5f},{lon:.5f},{dist_km},{' '.join(sorted(_river_words(river)))}"
        with lock:
            old = kept.get(key)
        age = now - old["at"] if isinstance(old, dict) and isinstance(old.get("at"), (int, float)) else None
        p = old.get("pick") if age is not None else None
        if p is not None and not (isinstance(p, dict) and {"ref", "station", "lat", "lon"} <= p.keys()):
            p, age = None, None   # a damaged entry is asked again
        if age is None or age > PICK_TTL_S:
            try:
                new = pick(lat, lon, dist_km, river)
                if new is None or new.get("complete", True):
                    with lock:
                        kept[key] = {"at": now, "pick": new}
                p = new if new is None or new.get("complete", True) or not p else p   # not a range-less pick over a whole one
            except Exception as e:  # noqa: BLE001
                if age is None or age > PICK_KEEP_S:
                    log.warning("EA stations lookup failed: %s", e)
                    return None
                log.info("EA stations lookup failed; using the gauge picked %.0f days ago: %s", age / 86400, e)
        return None if p is None else river_state(p, readings)

    def save() -> None:
        with lock:
            fresh = {k: v for k, v in kept.items()
                     if isinstance(v, dict) and isinstance(v.get("at"), (int, float)) and now - v["at"] <= PICK_KEEP_S}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(fresh, sort_keys=True))
        tmp.replace(path)

    return lookup, save


# ------------------------------------------------------------------------------ too high to swim
# Words beside the pollution level, never part of it: a high river and a flood are a different
# hazard (faster, colder water; debris), not a sign of sewage. The site shows them under the
# headline (build_site.attach_flow_state); nothing here changes a forecast or a level.
HIGH_INDEX = 1.0           # above the top of the gauge's usual range ("typicalRangeHigh")
RISING_SHARE = 0.2         # a rise of more than this share of the usual range ...
RISE_WINDOW_H = 6.0        # ... over the last six hours is "rising fast"
RISE_MIN_SPAN_H = 1.0      # fewer hours of readings than this is too short to call a trend
TREND_READINGS = 24        # the last 24 readings: six hours at the usual 15-minute interval
# The `dist` asked of /id/floods. The EA does not measure it to the area's outline: on 26 Oct 2026 it
# returned 122WAF940 for Burnsall, whose outline is 16.6 km from the pin (6.7 km from the area's
# bounding box), so which alerts apply is decided by the outline (flood_alert_water).
FLOOD_DIST_KM = 10
# The EA's four severity levels. 4 is "Warning no longer in force", so it is never shown as in force.
FLOOD_WORDS = {1: "Severe flood warning", 2: "Flood warning", 3: "Flood alert"}
_MEASURE_ID = re.compile(r"[A-Za-z0-9_.-]+")
_AREA_ID = _MEASURE_ID


def _when(s: str | None) -> datetime | None:
    """An EA time as an aware datetime; one with no zone is UTC. None if missing or unreadable."""
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def recent_levels(measure: str, limit: int = TREND_READINGS) -> list[tuple[str, float]]:
    """The latest `limit` readings of one level measure, as (time, metres), newest first. Raises on
    a bad measure id or a failed request; the caller decides what a failure means."""
    if not measure or not _MEASURE_ID.fullmatch(measure):
        raise ValueError(f"not a measure id: {measure!r}")
    r = httpx.get(f"{config.EA_FLOOD_MONITORING}/id/measures/{measure}/readings",
                  params={"_sorted": "", "_limit": limit}, headers=config.EA_HEADERS, timeout=EA_TIMEOUT_S)
    r.raise_for_status()
    out = []
    for rd in r.json().get("items", []):
        try:
            out.append((str(rd["dateTime"]), float(rd["value"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def rise_over_window(readings: list[tuple[str, float]], now: datetime,
                     window_h: float = RISE_WINDOW_H, min_span_h: float = RISE_MIN_SPAN_H) -> dict | None:
    """How far the level rose over the readings taken in the `window_h` hours before `now`: the
    last minus the first, in metres (negative if it fell), with the two times. None with fewer than
    two readings in the window, or with readings spanning less than `min_span_h`: so a gauge that
    went quiet, or a reading from yesterday, never makes a trend."""
    pts = sorted((t, v) for t, v in ((_when(s), v) for s, v in readings)
                 if t is not None and 0 <= (now - t).total_seconds() <= window_h * 3600)
    if len(pts) < 2 or (pts[-1][0] - pts[0][0]).total_seconds() < min_span_h * 3600:
        return None
    (t0, v0), (t1, v1) = pts[0], pts[-1]
    return {"rise_m": round(v1 - v0, 3), "from": t0.isoformat().replace("+00:00", "Z"), "to": t1.isoformat().replace("+00:00", "Z")}


def flow_state(index: float | None, same_river: bool | None, rise_share: float | None) -> str | None:
    """The word for a gauge reading at a spot: "high" above the gauge's usual range, else "rising
    fast" when it rose more than RISING_SHARE of that range over the last six hours, else None. Only
    from a gauge on the spot's own river (`same_river` True): a tributary's level is not the river's.
    `index` is None for a stale reading (reading_fields), so a stale reading never says "high"; the
    rise comes from readings in the last six hours only (rise_over_window)."""
    if same_river is not True:
        return None
    if index is not None and index > HIGH_INDEX:
        return "high"
    if rise_share is not None and rise_share > RISING_SHARE:
        return "rising fast"
    return None


def floods_in_force_anywhere(timeout: float = EA_TIMEOUT_S) -> bool:
    """Whether any flood alert or warning (severity 1 to 3) is in force anywhere in England: one
    request for the whole list, so that on most days the build asks nothing per spot. Raises on a
    failed request."""
    r = httpx.get(f"{config.EA_FLOOD_MONITORING}/id/floods", headers=config.EA_HEADERS, timeout=timeout)
    r.raise_for_status()
    levels = []
    for f in r.json().get("items", []):
        try:
            levels.append(int(f.get("severityLevel")))
        except (TypeError, ValueError):
            continue
    return any(v in FLOOD_WORDS for v in levels)


def flood_alerts(lat: float, lon: float, dist_km: float = FLOOD_DIST_KM, timeout: float = EA_TIMEOUT_S) -> list[dict]:
    """The Environment Agency's flood alerts and warnings in force for flood areas within `dist_km`
    of a point, the most severe first. Severity 4 ("Warning no longer in force") is left out. Each
    keeps the EA's area name and a link to its page on check-for-flooding.service.gov.uk. Raises on
    a failed request, so that "none in force" and "could not ask" stay apart."""
    r = httpx.get(f"{config.EA_FLOOD_MONITORING}/id/floods", params={"lat": round(lat, 5), "long": round(lon, 5), "dist": dist_km},
                  headers=config.EA_HEADERS, timeout=timeout)
    r.raise_for_status()
    out = []
    for f in r.json().get("items", []):
        try:
            sev = int(f.get("severityLevel"))
        except (TypeError, ValueError):
            continue
        if sev not in FLOOD_WORDS:
            continue
        fa = f.get("floodArea") if isinstance(f.get("floodArea"), dict) else {}
        area = str(f.get("floodAreaID") or fa.get("notation") or "")
        ok = bool(_AREA_ID.fullmatch(area))
        out.append({"severity_level": sev, "severity": FLOOD_WORDS[sev], "area": f.get("description") or None,
                    "area_id": area if ok else None, "raised": f.get("timeRaised"),
                    "url": f"https://check-for-flooding.service.gov.uk/target-area/{area}" if ok else None,
                    "waters": flood_waters(fa.get("riverOrSea")),
                    "tidal": f.get("isTidal") if isinstance(f.get("isTidal"), bool) else None})
    out.sort(key=lambda a: a["severity_level"])
    return out


# Which alerts apply to a spot. The EA's `dist` above is not measured to the area's outline: on 26 Oct
# 2026 the four Wharfe spots near Burnsall were given "Lower River Ure" (122WAF940), whose outline is
# 15.7 to 18.7 km away, and Dartington on the Dart "South Devon coast from Start Point to Dawlish Warren"
# (113WACT1B), 8.8 km away. Each flood area's outline is the EA's own statement of where an alert applies
# (check-for-flooding.service.gov.uk draws the same one), so geometry decides first and names second:
#  1. It applies, and is named: a river spot's point on its water (location.snapped; the pin when there
#     is none) lies inside the outline; for a lake, the outline reaches the lake's own outline; for a lake
#     with no outline, its pin lies inside. Inside or not, with no distance allowed. The point on the
#     water, not the pin: three of the four Wharfe pins sit 60 to 160 m outside "Upper River Wharfe"
#     (on banks and paths) while their points on the river are inside.
#  2. Outside, and the area names the spot's own water: "unknown", said neutrally with the EA's flood map.
#     It is for this river, but another stretch; the outline cannot say whether its flooding reaches here.
#  3. Outside, and it is tidal (isTidal: a coast, estuary or tidal river) for an inland spot, or it names
#     other water: "other", counted, never named.
#  4. No outline (no area id, a failed fetch, unreadable geometry): never "own"; otherwise as 2 and 3, and
#     an area that names nothing is "unknown".
# Short river names ("wharfe") are matched against the area's list of waters only, never its free-text
# title, where a short name can be part of a place's name ("Ouse Bridge", "Bradford"). Words
# beside the pollution level, never part of it: nothing here changes a forecast or a level.
FLOOD_OUTLINE_SIMPLIFY_M = 10.0
# The outline cache (OutlineStore), in config.CACHE/flood_areas: <area id>.geojson entries and one attempt
# record, FLOOD_OUTLINE_ATTEMPTS, all made by the build; nothing else lives there. The EA redraws flood
# areas rarely (in its periodic flood-warning area updates, not from day to day), and one outline is up
# to 0.9 MB raw, so it is not asked for in every build:
#  - each area is asked for at most once per FLOOD_OUTLINE_REFRESH_S, success or failure, while the
#    build's state cache carries over (best effort): each attempt's time is written to the record,
#    atomically, just before its request, so a request that fails, a later step that fails, or a
#    cancelled or timed-out run still leaves it on disk for the workflow's always() cache save. Cache
#    eviction (7 days unused, or the repository's 10 GB limit), a lost runner or a failed cache save
#    (a re-run of the same run_id included) resets it for the areas involved. Whatever happens, a build
#    asks for at most FLOOD_OUTLINE_FETCHES_PER_BUILD outlines, and an area with no outline (at most 30
#    days old) is never named. A kept outline under FLOOD_OUTLINE_REFRESH_S old is used without asking.
#  - a kept outline is used, when it is not asked for or its request fails, only while its recorded
#    fetch time is at most FLOOD_OUTLINE_MAX_AGE_S old; past that, or with none, the area has no outline
#    (rule 4: its alerts are counted or said neutrally, never named). This holds for a first fetch too:
#    one failed request leaves that area without an outline for up to 7 days.
#  - at most FLOOD_OUTLINE_FETCHES_PER_BUILD areas are asked for in one build: those with no usable
#    outline (missing or expired) first, then the oldest, then by id. 8 is one wave of the build's 8
#    workers. It bounds the cold-cache worst case at 8 GETs a build, 384 a day at 30-minute builds,
#    about 346 MB a day at the ~0.9 MB largest outline seen; normally one GET per area per week. On a
#    night like 26 Oct 2026 (~25 distinct in-force areas at the spots) a cold cache takes about four
#    builds to fill. Areas past it are not asked and not recorded as asked; they get a kept outline at
#    most 30 days old or none (never named), and the build counts and announces them.
#  - pruning (prune_flood_outlines) keeps the areas in force in this build and entries fetched within
#    FLOOD_OUTLINE_MAX_AGE_S, removes older ones, and then keeps at most FLOOD_OUTLINE_CACHE_MAX, the
#    newest. 500 is over 3.5 times the 137 items the national list held on 26 Oct 2026; at a few kB to
#    ~120 kB each it bounds the cache to tens of MB. The record drops attempts over 30 days old for
#    areas not in force.
FLOOD_OUTLINE_REFRESH_S = 7 * 86400
FLOOD_OUTLINE_MAX_AGE_S = 30 * 86400
FLOOD_OUTLINE_CACHE_MAX = 500
FLOOD_OUTLINE_FETCHES_PER_BUILD = 8
FLOOD_OUTLINE_ATTEMPTS = "_attempts.json"
# An EA flood-area id as the service writes them: three digits (the EA area), then letters and digits
# ("122WAF940", "011FWFNC6KC", "062WAF38BrentBks"; all 137 on 26 Oct 2026 fit). ASCII only, anchored by
# fullmatch, so no "/", "..", "?", "#", space or other character can reach a URL or a file name.
_FLOOD_AREA_ID = re.compile(r"[0-9]{3}[A-Za-z0-9]{1,40}", re.ASCII)
_TO_BNG = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
_FROM_BNG = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def _reproject(g, tr: Transformer):
    """A shape's coordinates through a pyproj transformer (x, y order)."""
    return shapely.transform(g, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1])))


def bng(lat, lon) -> tuple[float, float] | None:
    """A WGS84 point in British National Grid metres (x, y); None if either is not a number."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    return _TO_BNG.transform(lon, lat)


class SpotWater(NamedTuple):
    """The spot as its flood alerts need it: the names an area may give its water (`names`, matched
    against the area's title and waters; `short`, river names without "River", matched against its
    waters only), whether it is a lake or on tidal water, its point on its water and its pin (British
    National Grid x, y), and its lake's outline (BNG) for a lake."""
    names: frozenset[str] = frozenset()
    short: frozenset[str] = frozenset()
    lake: bool = False
    tidal: bool = False
    point: tuple[float, float] | None = None
    pin: tuple[float, float] | None = None
    lake_outline: object | None = None


def flood_waters(river_or_sea) -> list[str] | None:
    """A flood area's riverOrSea as a list of names: the EA gives one string, the waters split by
    commas, semicolons or new lines ("River Ure, Swinney Beck"), or now and then a list. None when
    it names none, which is not the same as naming another water."""
    items = river_or_sea if isinstance(river_or_sea, list) else [river_or_sea]
    out = [w.strip() for x in items if isinstance(x, str) for w in re.split(r"[,;\n]", x) if w.strip()]
    return out or None


def _water_text(name) -> str:
    """A water's name for matching: lower case, a bracket dropped ("Windermere (N Basin)"), letters
    only, Welsh words read as English ("Afon Gwy" is "river wye")."""
    t = re.sub(r"\([^)]*\)", " ", str(name or "").lower())
    words = ["river" if w == "afon" else WELSH.get(w, w) for w in re.findall(r"[^\W\d_]+", t)]
    return " ".join(words)


def water_names(*names) -> frozenset[str]:
    """The whole names an area may give the spot's water: as written ("river wharfe", "derwent water")
    and run together ("derwentwater", as the EA writes it for the Keswick campsite)."""
    out = set()
    for n in names:
        t = _water_text(n)
        if t:
            out |= {t, t.replace(" ", "")}
    return frozenset(out)


def short_water_names(*names) -> frozenset[str]:
    """A river's names without "River" ("wharfe", as a list of waters may give it: "Bure, Ant,
    Thurne"), for the area's waters only. A lake has none: "Derwent" alone is the river."""
    out = set()
    for n in names:
        t = _water_text(n)
        core = re.sub(r"^(the )?river |( river)$", "", t).strip()
        if core and core != t and len(core) >= 3:
            out.add(core)
    return frozenset(out)


def names_own_water(alert: dict, spot: SpotWater) -> bool:
    """Whether the area names the spot's water: a whole name in its title or its waters, or a short
    river name in its waters."""
    waters = [_water_text(w) for w in (alert.get("waters") if isinstance(alert.get("waters"), list) else []) if isinstance(w, str)]
    title = [_water_text(alert.get("area"))] if isinstance(alert.get("area"), str) else []
    has = lambda texts, names: any(f" {n} " in f" {t} " for t in texts for n in names)  # noqa: E731
    return has(waters + title, spot.names) or has(waters, spot.short)


def load_outline(geojson) -> object | None:
    """A flood area's or lake's outline from GeoJSON in WGS84 (a geometry, a Feature or a
    FeatureCollection), as one shape in British National Grid metres, simplified to
    FLOOD_OUTLINE_SIMPLIFY_M. None for anything that is not a polygon with an area: unreadable
    geometry is no outline (rule 4), never a guess."""
    try:
        if isinstance(geojson, str | bytes):
            geojson = json.loads(geojson)
        feats = geojson["features"] if geojson.get("type") == "FeatureCollection" else [geojson]
        # Each part made valid before they are joined: the EA's own coast outlines can have a ring that
        # crosses itself (054WACDV4B, 051WACDV4C on 26 Oct 2026), and joining them as they come raises.
        parts = [make_valid(shape(f["geometry"] if f.get("type") == "Feature" else f)) for f in feats]
        g = _reproject(unary_union(parts), _TO_BNG)
        g = make_valid(g) if not g.is_valid else g
        g = unary_union([p for p in getattr(g, "geoms", [g]) if p.geom_type in ("Polygon", "MultiPolygon")])
        g = g.simplify(FLOOD_OUTLINE_SIMPLIFY_M, preserve_topology=True)
    except Exception as e:  # noqa: BLE001 - shapely and pyproj raise many kinds on bad input; all mean "no outline"
        log.info("flood outline unreadable: %s", e)
        return None
    return g if not g.is_empty and g.area > 0 and g.is_valid else None


def _outline_url(area_id: str) -> str | None:
    """The one URL an outline is asked for: https, the EA service's own host and path, then
    /id/floodAreas/<id>/polygon, for an id that is strictly an EA flood-area id. Built here, never
    taken from a response."""
    if not isinstance(area_id, str) or not _FLOOD_AREA_ID.fullmatch(area_id):
        return None
    base = urlsplit(config.EA_FLOOD_MONITORING)
    return urlunsplit(("https", _EA_HOST, f"{base.path.rstrip('/')}/id/floodAreas/{area_id}/polygon", "", ""))


def _entry(path: Path, now: float) -> tuple[dict | None, float | None]:
    """A kept entry and its age in seconds, from the fetch time recorded in it. An entry without a
    readable fetch time has no age, so it is never used once a refresh fails, and pruning removes it."""
    try:
        entry = json.loads(path.read_text())
        fetched = float(entry["properties"]["fetched_at"])
    except (OSError, ValueError, TypeError, KeyError):
        return None, None
    return (entry, now - fetched) if math.isfinite(fetched) else (None, None)


def _entry_age(path: Path, now: float) -> float | None:
    return _entry(path, now)[1]


def _kept_outline(path: Path, now: float) -> tuple[object | None, float | None]:
    """A kept outline (load_outline) and its recorded age."""
    entry, age = _entry(path, now)
    return (load_outline(entry), age) if entry is not None else (None, None)


def _write_json(path: Path, obj) -> None:
    """Write JSON atomically: a temporary file beside it, then a rename."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(obj))
    tmp.replace(path)


def _attempt_times(cache_dir: Path) -> dict[str, float]:
    """The attempt record (FLOOD_OUTLINE_ATTEMPTS): area id -> the time of its last outline request,
    success or failure. Anything unreadable in it is left out."""
    try:
        raw = json.loads((cache_dir / FLOOD_OUTLINE_ATTEMPTS).read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in (raw.items() if isinstance(raw, dict) else []):
        try:
            t = float(v)
        except (TypeError, ValueError):
            continue
        if isinstance(k, str) and _FLOOD_AREA_ID.fullmatch(k) and math.isfinite(t):
            out[k] = t
    return out


class OutlineStore:
    """The outline cache for one build (see the notes at FLOOD_OUTLINE_REFRESH_S). plan() decides, for
    each in-force area, what is used without asking and which areas are asked for this build (at most
    `cap`); fetch() asks for one, from any thread; finish() writes the attempt record."""

    def __init__(self, cache_dir: Path, now: float | None = None, get=None, cap: int | None = None):
        self.dir, self.get = cache_dir, get
        self.now = time.time() if now is None else now
        self.cap = FLOOD_OUTLINE_FETCHES_PER_BUILD if cap is None else cap
        self.attempts = _attempt_times(cache_dir)
        self._asked: dict[str, float] = {}
        self._usable: dict[str, object | None] = {}
        self._lock = threading.Lock()

    def plan(self, area_ids) -> tuple[dict, list[str], list[str]]:
        """(ready, ask, capped). `ready` maps each area not asked this build to what it has: a kept
        outline under FLOOD_OUTLINE_REFRESH_S old; or, for an area asked within the last
        FLOOD_OUTLINE_REFRESH_S (success or failure) or over the cap, a kept outline at most
        FLOOD_OUTLINE_MAX_AGE_S old, else None (rule 4). `ask` is the areas to ask for this build, in
        a stable order: those with no usable outline first, then the oldest, then by id, at most
        `cap`. `capped` are the ones past the cap: not asked and not recorded as asked."""
        ready, candidates = {}, []
        for aid in sorted({a for a in area_ids if isinstance(a, str)}):
            if _outline_url(aid) is None:
                ready[aid] = None
                continue
            path = self.dir / f"{aid}.geojson"
            kept, age = _kept_outline(path, self.now) if path.exists() else (None, None)
            usable = kept if kept is not None and age is not None and 0 <= age <= FLOOD_OUTLINE_MAX_AGE_S else None
            self._usable[aid] = usable
            if usable is not None and age < FLOOD_OUTLINE_REFRESH_S:
                ready[aid] = usable
                continue
            last = self.attempts.get(aid)
            if last is not None and 0 <= self.now - last < FLOOD_OUTLINE_REFRESH_S:
                ready[aid] = usable   # asked within the week: not again, whatever came of it
                continue
            candidates.append((usable is not None, -(age if age is not None else math.inf), aid))
        candidates.sort()
        ask = [aid for _, _, aid in candidates[:self.cap]]
        capped = [aid for _, _, aid in candidates[self.cap:]]
        for aid in capped:
            ready[aid] = self._usable[aid]
        return ready, ask, capped

    def fetch(self, area_id: str, timeout: float = EA_TIMEOUT_S) -> object | None:
        """Ask for one planned area's outline, once, at _outline_url with redirects not followed. The
        attempt is recorded on disk first (record_attempt), whatever comes of it. A good answer is kept by area id, simplified, with its
        fetch time. On a failure (no answer, any status but 200, a redirect included, unreadable
        geometry), the kept outline is used only while at most FLOOD_OUTLINE_MAX_AGE_S old, else None."""
        url = _outline_url(area_id)
        if url is None:
            return None
        self.record_attempt(area_id)
        fallback = self._usable.get(area_id)
        try:
            r = (self.get or httpx.get)(url, headers=config.EA_HEADERS, timeout=timeout, follow_redirects=False)
            if r.status_code != 200:   # a redirect is a failure too: no URL from a response is ever followed
                raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
            outline = load_outline(r.json())
        except Exception as e:  # noqa: BLE001 - a failed outline is rule 4 for that area, not a failed build
            log.info("flood outline %s: %s", area_id, e)
            return fallback
        if outline is None:
            return fallback
        try:   # kept simplified, in WGS84 GeoJSON as the EA gives it, a few kB to ~120 kB each
            self.dir.mkdir(parents=True, exist_ok=True)
            _write_json(self.dir / f"{area_id}.geojson",
                        {"type": "Feature", "properties": {"floodAreaID": area_id, "fetched_at": self.now},
                         "geometry": mapping(_reproject(outline, _FROM_BNG))})
        except OSError as e:
            log.info("flood outline %s not kept: %s", area_id, e)
        return outline

    def record_attempt(self, area_id: str) -> None:
        """Write one attempt's time to the record before its request: under the lock, read the record,
        merge, and replace it atomically (_write_json). A record that cannot be written is logged; the
        request still goes, and the per-build cap still holds."""
        with self._lock:
            self._asked[area_id] = self.now
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
                _write_json(self.dir / FLOOD_OUTLINE_ATTEMPTS, {**_attempt_times(self.dir), **self._asked})
            except OSError as e:
                log.warning("flood outline attempt for %s not recorded: %s", area_id, e)

    def finish(self) -> None:
        """Make sure the record holds this build's attempts (each was written before its request; this
        writes again only if one is missing). Harmless to call more than once."""
        if not self._asked:
            return
        on_disk = _attempt_times(self.dir)
        if all(on_disk.get(a) == t for a, t in self._asked.items()):
            return
        with self._lock:
            try:
                _write_json(self.dir / FLOOD_OUTLINE_ATTEMPTS, {**_attempt_times(self.dir), **self._asked})
            except OSError as e:
                log.warning("flood outline attempts not recorded: %s", e)


def flood_area_outline(area_id: str | None, cache_dir: Path, timeout: float = EA_TIMEOUT_S, now: float | None = None,
                       get=None) -> object | None:
    """One area's outline through the cache's rules (OutlineStore), as one build would get it."""
    store = OutlineStore(cache_dir, now=now, get=get, cap=1)
    ready, ask, _ = store.plan([area_id])
    out = store.fetch(area_id, timeout) if ask else ready.get(area_id)
    store.finish()
    return out


def prune_flood_outlines(cache_dir: Path, keep=(), now: float | None = None, cap: int | None = None) -> list[str]:
    """Bound the outline cache. Only generated files are touched: regular files directly inside
    `cache_dir` named <area id>.geojson (_FLOOD_AREA_ID), and the attempt record
    (FLOOD_OUTLINE_ATTEMPTS); never a link, a subdirectory or anything else. An entry is kept while its
    area is in force in this build (`keep`) or its recorded fetch time is within
    FLOOD_OUTLINE_MAX_AGE_S; older ones, and ones with no readable fetch time, go. Then, past
    FLOOD_OUTLINE_CACHE_MAX entries, the oldest not in force go. The record drops attempt times over
    FLOOD_OUTLINE_MAX_AGE_S old for areas not in force. Returns the names removed (and the record's, if
    it changed)."""
    now = time.time() if now is None else now
    cap = FLOOD_OUTLINE_CACHE_MAX if cap is None else cap
    keep = set(keep)
    try:
        root = cache_dir.resolve(strict=True)
        entries = [p for p in root.iterdir() if p.name.endswith(".geojson")
                   and _FLOOD_AREA_ID.fullmatch(p.name[:-len(".geojson")]) and not p.is_symlink() and p.is_file()
                   and p.parent == root]
    except OSError:
        return []
    ages = {p: _entry_age(p, now) for p in entries}
    gone = [p for p in entries if p.name[:-len(".geojson")] not in keep
            and (ages[p] is None or ages[p] > FLOOD_OUTLINE_MAX_AGE_S)]
    left = sorted((p for p in entries if p not in gone and p.name[:-len(".geojson")] not in keep), key=lambda p: -(ages[p] or 0))
    n_kept = len(entries) - len(gone)
    gone += left[:max(0, n_kept - cap)]
    removed = []
    for p in gone:
        try:
            p.unlink()
            removed.append(p.name)
        except OSError as e:
            log.info("flood outline cache: %s not removed: %s", p.name, e)
    record = root / FLOOD_OUTLINE_ATTEMPTS
    if record.is_file() and not record.is_symlink():
        times = _attempt_times(root)
        try:
            raw = json.loads(record.read_text())
        except (OSError, ValueError):
            raw = None
        kept = {k: t for k, t in times.items() if k in keep or 0 <= now - t <= FLOOD_OUTLINE_MAX_AGE_S}
        if kept != raw:
            try:
                _write_json(record, kept)
                removed.append(FLOOD_OUTLINE_ATTEMPTS)
            except OSError as e:
                log.info("flood outline cache: attempt record not pruned: %s", e)
    return removed


def _applies(outline, spot: SpotWater) -> bool:
    """Rule 1: the area covers the spot's water (see the notes above)."""
    if spot.lake and spot.lake_outline is not None:
        return bool(outline.intersects(spot.lake_outline))
    at = spot.pin if spot.lake else (spot.point or spot.pin)
    return at is not None and bool(outline.covers(Point(at)))


def flood_alert_water(alert: dict, spot: SpotWater, outline=None) -> str:
    """"own" (rule 1: the area covers the spot's water; named on the page), "other" (rule 3: tidal for
    an inland spot, or the area names other water; counted) or "unknown" (rules 2 and 4: the area
    names the spot's water but does not cover it, it has no outline and names the spot's water or
    nothing, or the spot has no water name; said neutrally). Never "own" without an outline."""
    if not isinstance(alert, dict):
        return "unknown"
    if outline is not None and _applies(outline, spot):
        return "own"
    if alert.get("tidal") is True and not spot.tidal:
        return "other"
    if not (spot.names or spot.short) or names_own_water(alert, spot):
        return "unknown"
    waters = alert.get("waters") if isinstance(alert.get("waters"), list) else []
    return "other" if any(_water_text(w) for w in waters if isinstance(w, str)) else "unknown"


def split_flood_alerts(alerts: list[dict] | None, spot: SpotWater, outlines: dict | None = None
                       ) -> tuple[list[dict] | None, int | None, int | None]:
    """The alerts that apply to the spot (in the order given, the most severe first), and how many
    others are in force for other water and for water that could not be told. `outlines` maps area ids
    to outlines (load_outline); an area missing from it has none. None for all three when the EA did
    not answer (`alerts` None): unchecked is never "none"."""
    if alerts is None:
        return None, None, None
    outlines = outlines or {}
    kinds = [flood_alert_water(a, spot, outlines.get(a.get("area_id")) if isinstance(a, dict) else None) for a in alerts]
    return ([a for a, k in zip(alerts, kinds, strict=True) if k == "own"], kinds.count("other"), kinds.count("unknown"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    st = nearest_level_station(54.1995, -2.5945)
    print(st, st.index if st else None, st.label if st else None)
