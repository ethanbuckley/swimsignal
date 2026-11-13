"""Live readings from the Environment Agency's water-quality sondes (Hydrology API, OGL v3): ammonium, dissolved
oxygen and turbidity, every 15 minutes, published unchecked. docs/SONDE-READINGS-CONTRACT-v1.md is the contract.

An observation beside the forecast, never an input to it, and never a level. Ammonium is a marker that can come from
sewage; it is not a bacteria count and not a sign the water is fit to swim in, and no reading is not clean water.

Two requests for the whole build, never one per spot (`fetch_sondes`), as the water-temperature line makes
(`water_temperature.fetch_sensors`): the readings of all three properties since the start of yesterday, in one list
(the API takes `observedProperty` more than once; 18,669 readings, 3.5 MB, on 13 Nov 2026), and the active stations
that measure any of them (154, 0.4 MB). A refusal is tried once more, so at most four.

A spot gets a sonde only on its own river by name (`names.same_river`, as the temperature line), joined to it by the
river network on the same side of the tidal limit (`water_temperature.river_relation`), and upstream of it at most
UP_KM along the river, or at it (AT_KM either way). Straight-line distance only narrows the list first: a station
UP_KM along the river is never further than UP_KM in a straight line. The nearest along the river is shown.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx

from dipcast import config
from dipcast.ingest.flows import MAX_READING_AGE_H
from dipcast.ingest.water_temperature import _last_segment, _utc, parse_label, sensors_on_river

log = logging.getLogger(__name__)

READINGS = f"{config.EA_HYDROLOGY}/data/readings.json"
STATIONS = f"{config.EA_HYDROLOGY}/id/stations.json"
EXPLORER = "https://environment.data.gov.uk/hydrology/station/"   # the EA's own page for a station
TIMEOUT_S = 60.0
READINGS_LIMIT = 100_000      # the API's own cap on one request
UP_KM = 20.0                  # along the river, upstream of the spot (docs/SONDE-SIGNAL-TEST-2026-10.md's rule)
AT_KM = 0.25                  # along the river either way: a sonde this close is at the spot
DROP_QUALITY = {"Suspect", "Missing"}   # the EA's own words for a reading not to use; "Unchecked" is shown, and said


@dataclass(frozen=True)
class Prop:
    key: str          # the API's observedProperty
    suffix: str       # the 15-minute instantaneous measure: <station>-<suffix>
    unit: str         # as the page writes it
    lo: float         # outside lo..hi a reading is a fault, not the water
    hi: float


# The order is the page's: ammonium is the tile's figure, the others ride with it from the same sonde. Dissolved oxygen
# in % saturation; the same sondes also give mg/L (`do-i-subdaily-mgL`), which is not read.
PROPS = (
    Prop("ammonium", "amm-i-subdaily-mgL", "mg/L", 0.0, 100.0),
    Prop("dissolved-oxygen", "do-i-subdaily-pct", "% saturation", 0.0, 300.0),
    Prop("turbidity", "turb-i-subdaily-ntu", "NTU", 0.0, 4000.0),
)
BY_SUFFIX = {p.suffix: p for p in PROPS}


@dataclass(frozen=True)
class Reading:
    value: float
    observed_at: str          # ISO 8601, UTC, with Z
    age_hours: float          # at the build
    quality: str | None       # the EA's word: "Unchecked" until it has checked the reading


@dataclass(frozen=True)
class Sonde:
    station_id: str
    label: str
    river: str | None         # "Don", from the label, or the station's riverName
    place: str                # "Wharncliffe WwTW"
    where: str                # "below Wharncliffe WwTW"
    lat: float
    lon: float
    readings: dict[str, Reading] = field(default_factory=dict)   # Prop.key -> the latest usable reading
    series: tuple[tuple[str, float], ...] = ()                    # ammonium over the last MAX_READING_AGE_H, oldest first

    @property
    def url(self) -> str:
        return EXPLORER + quote(self.station_id, safe="")


@dataclass
class Fetched:
    sondes: list[Sonde]
    requests: int = 0          # requests sent, retries included
    readings: int = 0          # readings in the answer
    since: str = ""            # the readings asked for start this day (UTC)
    dropped: dict[str, int] = field(default_factory=dict)   # readings not used, by reason


def _station_id(s: dict) -> str:
    return str(s.get("notation") or _last_segment(s))


def parse(readings: list[dict], stations: list[dict], now: datetime, max_age_h: float = MAX_READING_AGE_H
          ) -> tuple[list[Sonde], dict[str, int]]:
    """Every station with an ammonium measure, with its latest usable reading of each property read within
    `max_age_h` of `now` and its ammonium series over that time. A station whose ammonium measure has no such reading is
    kept with no readings, so the page can say the sonde has gone quiet. `readings` and `stations` are the `items` of
    the API's two lists."""
    by_measure: dict[str, tuple[dict, Prop]] = {}
    keep: dict[str, dict] = {}
    for s in stations:
        sid = _station_id(s)
        for m in s.get("measures") or []:
            mid = _last_segment(m)
            for p in PROPS:
                if mid == f"{sid}-{p.suffix}" and int(m.get("period") or 0) == 900:
                    by_measure[mid] = (s, p)
                    if p.key == "ammonium":
                        keep[sid] = s
    dropped = {"unknown measure": 0, "not a number": 0, "out of range": 0, "flagged by the EA": 0, "too old": 0,
               "in the future": 0}
    latest: dict[tuple[str, str], tuple[datetime, Reading]] = {}
    series: dict[str, dict[datetime, float]] = {}
    for x in readings:
        hit = by_measure.get(_last_segment(x.get("measure")))
        if hit is None:
            dropped["unknown measure"] += 1
            continue
        s, p = hit
        sid = _station_id(s)
        try:
            v = float(x["value"])
        except (KeyError, TypeError, ValueError):
            dropped["not a number"] += 1
            continue
        t = _utc(x.get("dateTime"))
        if t is None or not math.isfinite(v):
            dropped["not a number"] += 1
            continue
        if not p.lo <= v <= p.hi:
            dropped["out of range"] += 1
            continue
        if x.get("quality") in DROP_QUALITY:
            dropped["flagged by the EA"] += 1
            continue
        age = (now - t).total_seconds() / 3600.0
        if age < -1.0:     # a reading from the future is a bad clock
            dropped["in the future"] += 1
            continue
        if age > max_age_h:
            dropped["too old"] += 1
            continue
        if p.key == "ammonium":
            series.setdefault(sid, {})[t] = v      # a repeated stamp keeps the last
        r = Reading(value=v, observed_at=t.strftime("%Y-%m-%dT%H:%M:%SZ"), age_hours=round(max(age, 0.0), 2),
                    quality=x.get("quality"))
        k = (sid, p.key)
        if k not in latest or t >= latest[k][0]:
            latest[k] = (t, r)
    out = []
    for sid, s in sorted(keep.items()):
        try:
            lat, lon = float(s["lat"]), float(s["long"])
        except (KeyError, TypeError, ValueError):
            continue
        river, place, where = parse_label(s.get("label"), s.get("riverName"))
        got = {p.key: latest[(sid, p.key)][1] for p in PROPS if (sid, p.key) in latest}
        line = tuple((t.strftime("%Y-%m-%dT%H:%M:%SZ"), v) for t, v in sorted(series.get(sid, {}).items()))
        out.append(Sonde(station_id=sid, label=str(s.get("label") or sid), river=river, place=place, where=where,
                         lat=lat, lon=lon, readings=got, series=line))
    return out, {k: v for k, v in dropped.items() if v}


def _get_counted(url: str, params: list[tuple[str, object]], sent: list[int], tries: int = 2,
                 wait_s: float = 5.0) -> list[dict]:
    """The `items` of one API list. A 403, 429 or 5xx is tried once more after `wait_s`, as the water-temperature line
    does (its gateway refused and then answered a minute later on 3 Oct 2026); each try counts in `sent`."""
    for i in range(tries):
        sent[0] += 1
        try:
            r = httpx.get(url, params=params, headers=config.EA_HEADERS, timeout=TIMEOUT_S)
            r.raise_for_status()
            return r.json().get("items", [])
        except httpx.HTTPStatusError as e:
            if i + 1 == tries or e.response.status_code not in (403, 429, 500, 502, 503, 504):
                raise
            log.info("sondes: %s answered %d; trying again in %.0f s", url, e.response.status_code, wait_s)
            time.sleep(wait_s)
    return []


def fetch_sondes(now: datetime | None = None, get=None, max_age_h: float = MAX_READING_AGE_H) -> Fetched:
    """Two requests for the whole build, at most four with retries: the three properties' readings since the start of
    the day `max_age_h` ago, and the active stations that measure any of them. `get(url, params)` returns a list's
    `items`; a test passes its own, and each call counts as one request."""
    now = now or datetime.now(UTC)
    sent = [0]

    def ask(url: str, params: list[tuple[str, object]]) -> list[dict]:
        if get is None:
            return _get_counted(url, params, sent)
        sent[0] += 1
        return get(url, params)

    since = (now - timedelta(hours=max_age_h)).date().isoformat()
    props: list[tuple[str, object]] = [("observedProperty", p.key) for p in PROPS]   # a key given three times
    readings = ask(READINGS, props + [("mineq-date", since), ("_limit", READINGS_LIMIT)])
    if len(readings) >= READINGS_LIMIT:
        log.warning("sondes: %d readings, the API's limit; some stations may be missing", len(readings))
    stations = ask(STATIONS, props + [("status", "statusActive"), ("_limit", 10_000)])
    sondes, dropped = parse(readings, stations, now, max_age_h)
    return Fetched(sondes=sondes, requests=sent[0], readings=len(readings), since=since, dropped=dropped)


def nearest_on_river(sondes: list[Sonde], lat: float, lon: float, river: str | None, relate,
                     up_km: float = UP_KM, at_km: float = AT_KM) -> tuple[Sonde, str, float] | None:
    """The sonde nearest the spot along its river, upstream at most `up_km` or at the spot (within `at_km` either
    way), as (sonde, "upstream" or "at", km along the river); None if there is none. `relate(sonde)` gives
    `water_temperature.river_relation`'s answer: ("upstream" or "downstream", km), or None where the network does not
    join the two or only one is tidal. Candidates come from `sensors_on_river` (the same river by name, within `up_km`
    in a straight line)."""
    best = None
    for s, _ in sensors_on_river(sondes, lat, lon, river, up_km):
        try:
            rel = relate(s)
        except Exception as e:  # noqa: BLE001 - a sonde the network cannot place is not shown
            log.warning("sondes: %s could not be placed on the river: %s", s.station_id, e)
            rel = None
        if rel is None:
            continue
        way, km = rel[0], float(rel[1])
        if km <= at_km:
            got = (s, "at", km)
        elif way == "upstream" and km <= up_km:
            got = (s, "upstream", km)
        else:
            continue
        if best is None or (got[2], got[0].station_id) < (best[2], best[0].station_id):
            best = got
    return best


def spot_block(s: Sonde, way: str, km: float) -> dict:
    """What a spot's page gets (`sonde` in spots-lite.json; the contract's `spots[].sonde`)."""
    return {"station_id": s.station_id, "station": s.place, "where": s.where, "river": s.river, "url": s.url,
            "direction": way, "river_km": round(km, 1),
            "readings": {k: {"value": r.value, "unit": next(p.unit for p in PROPS if p.key == k),
                             "observed_at": r.observed_at, "age_hours": r.age_hours, "quality": r.quality}
                         for k, r in s.readings.items()},
            "series": [[t, v] for t, v in s.series]}
