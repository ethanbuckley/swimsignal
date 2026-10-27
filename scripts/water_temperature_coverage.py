"""How many spots could show a measured water temperature, and how fresh it would be (read-only).

docs/WATER-TEMPERATURE-2026-10.md has the method and the numbers. The site's own lookup is
build_site.attach_water_temperature (src/dipcast/ingest/water_temperature.py); this script asks the
same questions of the whole temperature catalogue and reports counts. It writes nothing outside
its cache and its report.

Request caps (the doc's): at most 300 requests a run, one in flight, at least 1.5 s apart, stop on
HTTP 429 or 5xx, Environment Agency host only, every answer cached on disk and never asked again.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

from dipcast import config
from dipcast.ingest import water_temperature as wt

EA_HOST = "environment.data.gov.uk"
MAX_REQUESTS = 300
GAP_S = 1.5
TIMEOUT_S = 90.0


class Stop(RuntimeError):
    """The EA answered 429 or 5xx, or the cap was reached: the run ends here."""


class CappedClient:
    """GETs to the EA host, one at a time, at least `gap_s` apart, at most `cap` a run, each answer
    cached in `cache_dir` by its URL. `get` is httpx.get, or a stand-in for tests."""

    def __init__(self, cache_dir: Path, cap: int = MAX_REQUESTS, gap_s: float = GAP_S, get=None, sleep=time.sleep,
                 clock=time.monotonic):
        self.cache_dir, self.cap, self.gap_s = Path(cache_dir), cap, gap_s
        self.get, self.sleep, self.clock = get or httpx.get, sleep, clock
        self.used = 0          # requests sent this run
        self.cached = 0        # answers read from the cache
        self.last_end: float | None = None
        self.log: list[tuple[str, int]] = []

    @staticmethod
    def full_url(url: str, params: dict | list | None = None) -> str:
        """The URL with its query in a fixed order; `params` is a dict, or (key, value) pairs where a
        key repeats (measure=A&measure=B)."""
        items = list(params.items()) if isinstance(params, dict) else list(params or [])
        return url + ("?" + urlencode(sorted(items)) if items else "")

    def _path(self, full: str) -> Path:
        return self.cache_dir / (hashlib.sha256(full.encode()).hexdigest()[:24] + ".json")

    def fetch(self, url: str, params: dict | list | None = None, as_text: bool = False):
        full = self.full_url(url, params)
        u = urlsplit(full)
        if u.scheme != "https" or u.hostname != EA_HOST:
            raise ValueError(f"not an EA URL: {full}")
        p = self._path(full)
        if p.exists():
            self.cached += 1
            body = json.loads(p.read_text())["body"]
            return body if as_text else json.loads(body)
        if self.used >= self.cap:
            raise Stop(f"request cap of {self.cap} reached before {full}")
        if self.last_end is not None:
            wait = self.gap_s - (self.clock() - self.last_end)
            if wait > 0:
                self.sleep(wait)
        self.used += 1
        try:
            r = self.get(full, headers=config.EA_HEADERS, timeout=TIMEOUT_S)
        finally:
            self.last_end = self.clock()
        self.log.append((full, r.status_code))
        if r.status_code == 429 or r.status_code >= 500:
            raise Stop(f"{full} answered {r.status_code}; stopping")
        r.raise_for_status()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"url": full, "fetched_at": time.time(), "body": r.text}))
        return r.text if as_text else json.loads(r.text)


DEFAULT_CACHE = config.CACHE / "water_temperature_coverage"
HYDROLOGY = config.EA_HYDROLOGY
FLOOD = config.EA_FLOOD_MONITORING
KM_STEPS = (2.0, 5.0, 15.0)      # the distances the report counts at; 15 km is the site's rule (water_temperature.MAX_KM)


# ------------------------------------------------------------------ air or water
def _labels(x) -> list[str]:
    xs = x if isinstance(x, list) else [x]
    return [str(v.get("label") or v.get("@id", "")).rsplit("/", 1)[-1] if isinstance(v, dict) else str(v) for v in xs if v]


def station_kind(station: dict) -> str:
    """What a Hydrology API temperature station is, from its `type` list.

    "sonde": a WaterQualityStation, a sonde in the water (1,948 of the 1,964 on 27 Oct 2026).
    "gauge": a RiverStation (a level or flow gauge) with a temperature series. Derby St Marys' series
    moved by a median 0.6 °C a day from June to November 2025, so it is in the water, not the air (air
    moves several degrees a day); the other 15 gauges were not checked one by one.
    "unknown": anything else, which the site does not use."""
    kinds = set(_labels(station.get("type")))
    if "WaterQualityStation" in kinds:
        return "sonde"
    if "RiverStation" in kinds:
        return "gauge"
    return "unknown"


def flood_measure_kind(measure: dict) -> str:
    """Air or water for a flood-monitoring temperature measure, from its qualifier. The API's own
    reference calls `temperature` "dry bulb air temperature measurement available from some stations";
    on 27 Oct 2026 23 of its 25 temperature measures were Dry Bulb or Wet Bulb (air) and 2 were Water."""
    q = str(measure.get("qualifier") or "").lower()
    if q == "water":
        return "water"
    if "bulb" in q:
        return "air"
    return "unknown"


def status(station: dict) -> str:
    return "/".join(_labels(station.get("status"))) or "unknown"


_SUFFIX = re.compile(r"_[A-Z]{1,3}_\d{6}$")


def place_key(label: str | None) -> str:
    """A sonde site across its deployments: the label without the team and start month
    ("STOUR_BOXTEDMILL_E_202604" -> "STOUR_BOXTEDMILL"). Each deployment is a new station."""
    return _SUFFIX.sub("", str(label or "").strip()).upper()


def deployments(stations: list[dict]) -> dict[str, dict]:
    """Per sonde site (place_key): how many deployments, the first opened, the last closed (None
    while one is open) and whether one is active now."""
    out: dict[str, dict] = {}
    for s in stations:
        if station_kind(s) != "sonde":
            continue
        k = place_key(s.get("label"))
        d = out.setdefault(k, {"n": 0, "first": None, "last_closed": "", "active": False})
        d["n"] += 1
        o, c = s.get("dateOpened"), s.get("dateClosed")
        if o and (d["first"] is None or o < d["first"]):
            d["first"] = o
        if c is None:
            d["last_closed"] = None
        elif d["last_closed"] is not None and c > d["last_closed"]:
            d["last_closed"] = c
        d["active"] = d["active"] or status(s) == "Active"
    return out


def cadence_minutes(readings: list[dict]) -> dict[str, float]:
    """The median minutes between a measure's readings, per measure id."""
    by: dict[str, list[datetime]] = {}
    for x in readings:
        m = wt._last_segment(x.get("measure"))
        t = wt._utc(x.get("dateTime"))
        if m and t:
            by.setdefault(m, []).append(t)
    out = {}
    for m, ts in by.items():
        ts.sort()
        gaps = [(b - a).total_seconds() / 60 for a, b in zip(ts, ts[1:]) if b > a]
        if gaps:
            out[m] = statistics.median(gaps)
    return out


# ------------------------------------------------------------------ spots
def lake_name(spot_name: str) -> str:
    """The lake's own name from a spot's: "Windermere, Lakeside YMCA" -> "Windermere",
    "Hampstead Heath (Mens Pond)" -> "Mens Pond", "The Serpentine - Hyde Park" -> "The Serpentine"."""
    m = re.search(r"\(([^)]*)\)", spot_name)
    if m:
        return m.group(1)
    return re.split(r",| - ", spot_name)[0].strip()


def spot_water(spot: dict) -> str | None:
    """The water a sensor must be on to count for this spot: a river spot's river, a lake spot's
    lake (a beck flowing into a lake is not the lake)."""
    if spot.get("kind") == "lake":
        return lake_name(str(spot.get("name") or ""))
    r = spot.get("river")
    return r if isinstance(r, str) and r.strip() else None


def spot_coverage(spot: dict, live: list[wt.Sensor], sondes: list[dict], places: dict[str, dict],
                  relate=None, max_km: float = wt.MAX_KM) -> dict:
    """One spot: the nearest live sensor on its own water within `max_km` (upstream first when `relate`
    places it, as the site does), the nearest live sensor on any water, and the nearest past sonde site
    on its own water, with that site's deployments."""
    lat, lon, water = float(spot["lat"]), float(spot["lon"]), spot_water(spot)
    out = {"id": spot.get("id"), "name": spot.get("name"), "kind": spot.get("kind"), "water": water,
           "designated": spot.get("source") == "designated"}
    anyw = sorted(((s, wt.km_between(lat, lon, s.lat, s.lon)) for s in live), key=lambda x: x[1])
    if anyw:
        s, km = anyw[0]
        out["nearest_any"] = {"station": s.label, "river": s.river, "km": round(km, 1)}
    same = wt.sensors_on_river(live, lat, lon, water, max_km) if water else []
    chosen = None
    for s, km in same:
        rel = ("unplaced", None)
        if relate is not None:
            try:
                rel = relate(spot, s)
            except Exception:  # noqa: BLE001 - a sensor the network cannot place is passed over, as on the site
                rel = None
            if rel is None:
                continue
        if chosen is None or rel[0] == "upstream":
            chosen = (s, km, rel)
        if rel[0] == "upstream":
            break
    if chosen:
        s, km, rel = chosen
        out["same_water"] = {"station": s.label, "station_id": s.station_id, "river": s.river, "km": round(km, 1),
                             "direction": rel[0], "river_km": rel[1], "temp_c": s.temp_c,
                             "observed_at": s.observed_at, "age_hours": s.age_hours,
                             "site_history": places.get(place_key(s.label))}
    if water:
        past = sorted(((p, wt.km_between(lat, lon, float(p["lat"]), float(p["long"]))) for p in sondes
                       if wt.same_river(water, wt.parse_label(p.get("label"))[0])), key=lambda x: x[1])
        past = [(p, km) for p, km in past if km <= max_km]
        if past:
            p, km = past[0]
            out["past_same_water"] = {"station": p.get("label"), "km": round(km, 1), "status": status(p),
                                      "site_history": places.get(place_key(p.get("label"))),
                                      "sites_within": len({place_key(q.get("label")) for q, _ in past})}
    return out


def summarise(rows: list[dict], live: list[wt.Sensor], cadence: dict[str, float]) -> dict:
    def count(pred):
        return sum(1 for r in rows if pred(r))
    out = {"spots": len(rows), "river_spots": count(lambda r: r["kind"] == "river"),
           "lake_spots": count(lambda r: r["kind"] == "lake"),
           "designated": count(lambda r: r["designated"]),
           "live_sensors": len(live)}
    for km in KM_STEPS:
        ok = lambda r, km=km: r.get("same_water") and r["same_water"]["km"] <= km   # noqa: E731
        out[f"same_water_within_{km:g}km"] = count(ok)
        out[f"same_water_within_{km:g}km_designated"] = count(lambda r, ok=ok: ok(r) and r["designated"])
        out[f"same_water_within_{km:g}km_upstream"] = count(lambda r, ok=ok: ok(r) and r["same_water"]["direction"] == "upstream")
    out["past_same_water_within_15km_no_live"] = count(lambda r: r.get("past_same_water") and not r.get("same_water"))
    ages = sorted(s.age_hours for s in live)
    out["live_age_hours_median"] = statistics.median(ages) if ages else None
    out["live_age_hours_max"] = ages[-1] if ages else None
    shown = sorted(r["same_water"]["age_hours"] for r in rows if r.get("same_water"))
    out["shown_age_hours_median"] = statistics.median(shown) if shown else None
    cad = [round(v) for v in cadence.values()]
    out["cadence_minutes"] = dict(collections.Counter(cad).most_common())
    return out


# ------------------------------------------------------------------ run
def load_spots() -> list[dict]:
    import pandas as pd
    frames = [pd.read_csv(f) for f in (config.ROOT / "spots.csv", config.ROOT / "spots-osm.csv") if f.exists()]
    return pd.concat(frames).to_dict("records")


def catalogue(client: CappedClient, now: datetime) -> dict:
    """Five requests (all cached): the Hydrology temperature measures and stations, a week of its
    temperature readings, and the flood-monitoring temperature measures and stations."""
    since = (now - timedelta(days=7)).date().isoformat()
    return {
        "h_measures": client.fetch(f"{HYDROLOGY}/id/measures.json", {"observedProperty": "temperature", "_limit": 3000})["items"],
        "h_stations": client.fetch(f"{HYDROLOGY}/id/stations.json", {"observedProperty": "temperature", "_limit": 10000})["items"],
        "readings": client.fetch(f"{HYDROLOGY}/data/readings.json",
                                 {"observedProperty": "temperature", "mineq-date": since, "_limit": 100000})["items"],
        "f_measures": client.fetch(f"{FLOOD}/id/measures", {"parameter": "temperature"})["items"],
        "f_stations": client.fetch(f"{FLOOD}/id/stations", {"parameter": "temperature"})["items"],
    }


def run(cat: dict, spots: list[dict], now: datetime, relate=None, max_age_h: float = wt.MAX_READING_AGE_H) -> dict:
    stations = cat["h_stations"]
    kinds = collections.Counter(station_kind(s) for s in stations)
    by_station = {str(s.get("notation") or wt._last_segment(s)): s for s in stations}
    m_kinds = collections.Counter()
    for m in cat["h_measures"]:
        s = by_station.get(wt._last_segment(m.get("station")))
        m_kinds[(station_kind(s) if s else "no station", str(m.get("valueType")))] += 1
    live = [s for s in wt.live_sensors(cat["readings"], stations, now, max_age_h)
            if station_kind(by_station.get(s.station_id, {})) in ("sonde", "gauge")]
    sondes = [s for s in stations if station_kind(s) == "sonde"]
    places = deployments(stations)
    rows = [spot_coverage(sp, live, sondes, places, relate) for sp in spots]
    f_kinds = collections.Counter(flood_measure_kind(m) for m in cat["f_measures"])
    f_water = [m.get("stationReference") for m in cat["f_measures"] if flood_measure_kind(m) == "water"]
    f_where = {s.get("stationReference"): s for s in cat["f_stations"]}
    return {
        "as_of": now.strftime("%Y-%m-%dT%H:%MZ"),
        "hydrology": {"measures": len(cat["h_measures"]), "stations": len(stations), "station_kinds": dict(kinds),
                      "measures_by_kind": {f"{k}/{v}": n for (k, v), n in sorted(m_kinds.items())},
                      "stations_by_status": {f"{k}/{v}": n for (k, v), n in sorted(
                          collections.Counter((station_kind(s), status(s)) for s in stations).items())},
                      "sonde_sites": len(places), "sonde_sites_active": sum(p["active"] for p in places.values()),
                      "readings_last_7_days": len(cat["readings"])},
        "flood_monitoring": {"measures": len(cat["f_measures"]), "by_kind": dict(f_kinds),
                             "water": [{"station": r, "label": (f_where.get(r) or {}).get("label"),
                                        "lat": (f_where.get(r) or {}).get("lat"), "lon": (f_where.get(r) or {}).get("long")}
                                       for r in f_water]},
        "summary": summarise(rows, live, cadence_minutes(cat["readings"])),
        "live_sensors": [{"station": s.label, "river": s.river, "temp_c": s.temp_c, "age_hours": s.age_hours} for s in live],
        "spots": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--out", type=Path, help="write the full report here as JSON")
    ap.add_argument("--now", help="the time to measure ages from (ISO 8601, UTC); default now")
    ap.add_argument("--network", type=Path, metavar="PICKLE",
                    help="river_network.pkl: place each sensor up- or downstream on the network, as the site does")
    a = ap.parse_args(argv)
    now = wt._utc(a.now) if a.now else datetime.now(UTC)
    client = CappedClient(a.cache)
    try:
        cat = catalogue(client, now)
    except Stop as e:
        print(f"stopped: {e}", file=sys.stderr)
        return 2
    finally:
        print(f"requests sent: {client.used}; answers from cache: {client.cached}", file=sys.stderr)
    relate = None
    if a.network:
        from dipcast.network.rivers import RiverNetwork
        if not a.network.exists():   # RiverNetwork.load would build one from OS Open Rivers instead
            print(f"no network at {a.network}", file=sys.stderr)
            return 2
        net = RiverNetwork.load(a.network)
        relate = lambda sp, s: wt.river_relation(net, float(sp["lat"]), float(sp["lon"]), spot_water(sp), s)  # noqa: E731
    report = run(cat, load_spots(), now, relate)
    report["requests_sent"] = client.used
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({k: report[k] for k in ("as_of", "hydrology", "flood_monitoring", "summary")}, indent=1, ensure_ascii=False))
    for r in report["spots"]:
        if r.get("same_water"):
            w = r["same_water"]
            print(f"  {r['name']}: {w['temp_c']} °C at {w['station']}, {w['km']} km, {w['direction']}, {w['age_hours']} h old")
    return 0


if __name__ == "__main__":
    sys.exit(main())
