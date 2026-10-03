"""River state from Environment Agency gauges.

Near-real-time *flow* is only published for ~350 stations, so we use *level*
stations (thousands) and express the latest level relative to the station's
typical range. That gives a 0..1+ "river state" index good enough to scale
travel speed and to show the swimmer whether the river is up.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from dipcast import config
from dipcast.network.names import river_words

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
FLOOD_DIST_KM = 10         # flood areas within this distance of the spot (the API measures to the area)
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


def floods_in_force_anywhere() -> bool:
    """Whether any flood alert or warning (severity 1 to 3) is in force anywhere in England: one
    request for the whole list, so that on most days the build asks nothing per spot. Raises on a
    failed request."""
    r = httpx.get(f"{config.EA_FLOOD_MONITORING}/id/floods", headers=config.EA_HEADERS, timeout=EA_TIMEOUT_S)
    r.raise_for_status()
    levels = []
    for f in r.json().get("items", []):
        try:
            levels.append(int(f.get("severityLevel")))
        except (TypeError, ValueError):
            continue
    return any(v in FLOOD_WORDS for v in levels)


def flood_alerts(lat: float, lon: float, dist_km: float = FLOOD_DIST_KM) -> list[dict]:
    """The Environment Agency's flood alerts and warnings in force for flood areas within `dist_km`
    of a point, the most severe first. Severity 4 ("Warning no longer in force") is left out. Each
    keeps the EA's area name and a link to its page on check-for-flooding.service.gov.uk. Raises on
    a failed request, so that "none in force" and "could not ask" stay apart."""
    r = httpx.get(f"{config.EA_FLOOD_MONITORING}/id/floods", params={"lat": round(lat, 5), "long": round(lon, 5), "dist": dist_km},
                  headers=config.EA_HEADERS, timeout=EA_TIMEOUT_S)
    r.raise_for_status()
    out = []
    for f in r.json().get("items", []):
        try:
            sev = int(f.get("severityLevel"))
        except (TypeError, ValueError):
            continue
        if sev not in FLOOD_WORDS:
            continue
        area = str(f.get("floodAreaID") or (f.get("floodArea") or {}).get("notation") or "")
        ok = bool(_AREA_ID.fullmatch(area))
        out.append({"severity_level": sev, "severity": FLOOD_WORDS[sev], "area": f.get("description") or None,
                    "area_id": area if ok else None, "raised": f.get("timeRaised"),
                    "url": f"https://check-for-flooding.service.gov.uk/target-area/{area}" if ok else None})
    out.sort(key=lambda a: a["severity_level"])
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    st = nearest_level_station(54.1995, -2.5945)
    print(st, st.index if st else None, st.label if st else None)
