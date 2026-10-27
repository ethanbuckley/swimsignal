"""docs/SONDE-SIGNAL-TEST-2026-10.md: which EA sondes count for a spot, from station metadata only.

A sonde is an EA Hydrology API station with a 15-minute instantaneous measure of the property (turbidity in NTU, or
ammonium in mg/L). It counts for a spot when, from metadata alone:
1. its river, read from its label or riverName as the site's water-temperature line reads it
   (`water_temperature.parse_label`), shares a distinctive word with the spot's river (`names.same_river`);
2. it is within MAX_KM in a straight line;
3. at scoring time only: the river network joins the two on the same side of the tidal limit
   (`water_temperature.river_relation`), with the sonde upstream at most UP_KM along the river, or downstream at most
   DOWN_KM;
4. its deployment (dateOpened to dateClosed, or to today when open) covers the sample's day.
Among the sondes that count for a sample, the one used is the first with a valid feature (feature.py) in this order:
upstream before downstream, then the shorter distance along the river, then the station id. At preparation, before
the network is loaded, the order is straight-line distance, then the station id, and rule 3 is not applied: counts
made then are upper bounds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from dipcast.ingest.water_temperature import parse_label
from dipcast.network.names import same_river

MAX_KM = 15.0     # straight line, the site's water-temperature rule
UP_KM = 20.0      # along the river, upstream of the spot
DOWN_KM = 2.0     # along the river, downstream of the spot: water that has just passed it
PROPERTIES = {"turbidity": "TURBIDITY", "ammonium": "AMMONIUM"}
UNITS = {"turbidity": "ntu", "ammonium": "mgL"}


@dataclass(frozen=True)
class Sonde:
    station_id: str
    label: str
    river: str | None
    lat: float
    lon: float
    opened: date | None
    closed: date | None                       # None while the station is open
    measures: dict[str, str] = field(default_factory=dict)   # property -> measure id (last URI segment)

    def covers(self, day: date) -> bool:
        """The deployment covers `day`. A station with no dateOpened is never counted."""
        if self.opened is None or day < self.opened:
            return False
        return self.closed is None or day <= self.closed


def _date(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


def _seg(ref) -> str:
    if isinstance(ref, dict):
        ref = ref.get("@id")
    return str(ref or "").rstrip("/").rsplit("/", 1)[-1]


def parse_stations(items: list[dict]) -> list[Sonde]:
    """Sondes from the `items` of /hydrology/id/stations.json (one or more property listings, merged by station id).
    Only 15-minute instantaneous measures in the stated unit count (`<id>-turb-i-subdaily-ntu`,
    `<id>-amm-i-subdaily-mgL`)."""
    out: dict[str, Sonde] = {}
    for s in items:
        sid = str(s.get("notation") or _seg(s))
        try:
            lat, lon = float(s["lat"]), float(s["long"])
        except (KeyError, TypeError, ValueError):
            continue
        measures = dict(out[sid].measures) if sid in out else {}
        for m in s.get("measures") or []:
            mid = _seg(m)
            for prop, param in PROPERTIES.items():
                if (m.get("parameter") == param and int(m.get("period") or 0) == 900
                        and mid.endswith(f"-i-subdaily-{UNITS[prop]}")):
                    measures[prop] = mid
        river, _, _ = parse_label(s.get("label"), s.get("riverName"))
        opened, closed = _date(s.get("dateOpened")), _date(s.get("dateClosed"))
        if opened and closed and closed < opened:
            closed = None   # a placeholder (E04662A: opened 2026-05-05, "closed" 1970-01-01); the readings decide
        out[sid] = Sonde(sid, str(s.get("label") or sid), river, lat, lon, opened, closed, measures)
    return list(out.values())


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = math.pi / 180
    h = math.sin((lat2 - lat1) * r / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin((lon2 - lon1) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def candidates(sondes: list[Sonde], lat: float, lon: float, river: str | None, prop: str,
               max_km: float = MAX_KM) -> list[tuple[Sonde, float]]:
    """Rules 1 and 2: sondes with the property's measure, on a river sharing a name with `river`, within `max_km`
    in a straight line; nearest first, then by station id. None without a river name."""
    near = [(s, km_between(lat, lon, s.lat, s.lon)) for s in sondes
            if prop in s.measures and river and same_river(river, s.river)]
    return sorted(((s, d) for s, d in near if d <= max_km), key=lambda x: (x[1], x[0].station_id))


def network_ok(relation: tuple[str, float] | None, up_km: float = UP_KM, down_km: float = DOWN_KM) -> bool:
    """Rule 3, given `water_temperature.river_relation`'s answer: ("upstream" or "downstream", km along the river),
    or None when the network does not join the two or only one is tidal."""
    if relation is None:
        return False
    way, km = relation
    return (way == "upstream" and km <= up_km) or (way == "downstream" and km <= down_km)


def order(matched: list[tuple[Sonde, tuple[str, float]]]) -> list[Sonde]:
    """The order in which a sample tries its sondes: upstream first, then the shorter distance along the river,
    then the station id."""
    return [s for s, rel in sorted(matched, key=lambda x: (x[1][0] != "upstream", x[1][1], x[0].station_id))]
