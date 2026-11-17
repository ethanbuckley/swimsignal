"""A course briefing's data: one event's route on the river network, split into sections where the water-quality
evidence changes, and replayed on a few past dates (docs/COURSE-BRIEFING-HENLEY-2026-11.md).

    DIPCAST_ROOT=<scratch root> DIPCAST_STATE=<scratch state> PYTHONPATH=src python scripts/course_briefing.py \
        prototypes/course-briefing/henley-classic/course.toml --events <ea_events_thames_water.parquet> \
        [--openmap <OS OpenMap Local data folder>]

It writes course.json beside the course file, for the prototype page in that folder. Nothing here is built into
the site, and it calls no outside service.

What it reuses, so the briefing can never disagree with the site:
- the route between the two ends and the overflows on it, on a side stream or above it: stretches.route and
  stretches.between, the outing planner's own (a paddle's finish);
- each end's upstream overflows, travel times and weights: transport.upstream_overflows, as the site build calls it;
- the exposure index: transport.combine_daily, here fed recorded spills in place of forecast chances, as
  forecast_log.verify_spots does, and labelled a reconstruction;
- a recorded spill's days: forecast_log.observed_spill_days;
- a poll's day and half-hour slot: as ingest.live.coverage_rows keeps them;
- the limits wording: briefing.LIMITS and briefing.DECIDES, word for word.

It reads the river network, the annual returns and the join files under DIPCAST_ROOT, and the live history, the
poll coverage and the issued page records under DIPCAST_STATE. Building the overflow table writes it to
DIPCAST_STATE, so the script refuses to run unless that is a scratch folder outside this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
UK = ZoneInfo("Europe/London")
CONTRACT = "course-briefing-v1"
RECENT_H = 48.0          # the site's "recent spill" window (assumptions.recent_spill_hours)
TOLERANCE_M = 60.0       # the route between the ends must be within this of the organiser's length
LOG_FROM = "2026-09-12"  # the forecast log's first day (forecast_points)
RECORDS_FROM = "2026-10-31"   # the first kept page record (issued-2026-10.parquet)
PLATE_PAD_M = 260.0


class CourseError(Exception):
    """A problem to fix before a briefing is made: said in one plain message."""


# ------------------------------------------------------------------ pure parts (tests/test_course_briefing.py)
def load_course(path: Path) -> dict:
    c = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    need = {"id", "name", "organiser", "length_m", "river", "spot", "start", "finish", "date"}
    if need - set(c):
        raise CourseError(f"{path}: missing {', '.join(sorted(need - set(c)))}")
    for end in ("start", "finish"):
        if {"easting", "northing", "how", "sure"} - set(c[end]):
            raise CourseError(f"{path}: [{end}] needs easting, northing, how and sure")
    for m in c.get("mouth", []):
        if m.get("link") not in ("mapped", "possible"):
            raise CourseError(f"{path}: mouth {m.get('name')!r}: link must be 'mapped' or 'possible'")
    return c


def sections(course_km: float, inflows: list[dict]) -> list[dict]:
    """The course cut where the evidence changes, from the start (0 km, the downstream end, where the swim begins)
    to the finish. inflows: [{ site_id, join_km (the network's join, km from the start, or None where the network
    has none on the course), mouths: [{ km (from the start), link: 'mapped' | 'possible' }] }], each an overflow
    whose water meets the river on the course, so that the start's forecast counts it and the finish's does not.

    Water flows towards the start. So an inflow is upstream of every point between the start and its join, and of
    none beyond it. The sure reach runs from the start to the furthest join the network or a mapped mouth gives.
    From there to the furthest 'possible' mouth the connection is not shown either way: that part is "unresolved",
    never guessed. Each section: { from_km, to_km, adds: [site_id] (counted here and not at the finish),
    unresolved: [site_id] }."""
    cuts = {0.0, round(course_km, 2)}
    reach = {}
    for f in inflows:
        on = [m["km"] for m in f.get("mouths", []) if 0 < m["km"] < course_km]
        sure = [k for k in ([f.get("join_km")] + [m["km"] for m in f.get("mouths", []) if m["link"] == "mapped"])
                if k is not None and 0 < k < course_km]
        s = max(sure) if sure else 0.0
        maybe = max([k for k in on if k > s], default=s)
        reach[f["site_id"]] = (round(s, 2), round(maybe, 2))
        cuts |= {round(s, 2), round(maybe, 2)}
    edges = sorted(cuts)
    out = []
    for a, b in zip(edges, edges[1:]):
        mid = (a + b) / 2
        out.append({"from_km": a, "to_km": b,
                    "adds": sorted(s for s, (sure, _) in reach.items() if mid < sure),
                    "unresolved": sorted(s for s, (sure, maybe) in reach.items() if sure < mid < maybe)})
    return out


def monitor_state(n_known, n_unknown) -> str:
    """One overflow's readings over one day of polls: 'reported' (a status at every poll), 'part' (at some),
    'none' (at no poll), 'not polled' (no poll that day)."""
    if n_known is None or (not n_known and not n_unknown):
        return "not polled"
    if not n_known:
        return "none"
    return "part" if n_unknown else "reported"


def events_in_window(events: list[dict], as_of: datetime, hours: float = RECENT_H) -> list[dict]:
    """The recorded spills that touch the `hours` before as_of, latest first. events: [{ site_id, start, end
    (aware datetimes; end None while still running), source }]. A spill that began after as_of is left out:
    the replay shows what a record could have shown at that time."""
    lo = as_of - timedelta(hours=hours)
    hit = [e for e in events if e["start"] <= as_of and (e["end"] is None or e["end"] >= lo)]
    return sorted(hit, key=lambda e: (e["start"], e["site_id"]), reverse=True)


def slot_of(t: datetime) -> tuple[date, int]:
    """A poll's UK day and half-hour slot, as the coverage file keeps them (ingest.live.coverage_rows)."""
    u = t.astimezone(UK)
    return u.date(), u.hour * 2 + u.minute // 30


def issue_time(issue: str) -> datetime:
    """When an issue id says it was issued: '6743baf-20261114T0718Z' is 07:18 UTC on 14 Nov 2026."""
    return datetime.strptime(issue.split("-")[-1], "%Y%m%dT%H%MZ").replace(tzinfo=ZoneInfo("UTC"))


def _covers(r: dict, t: datetime) -> bool:
    """Whether this event-log row says the overflow was spilling at time t: by its status, or by its spill's own
    start and stop. It says nothing about when the row was received (replay_at)."""
    by_status = r["status"] == 1 and r.get("status_start") is not None and r["status_start"] <= t <= r["fetched_at"]
    start, end = r.get("start"), r.get("end")
    by_spill = start is not None and start <= t and (end >= t if end is not None else r["status"] == 1 and t <= r["fetched_at"])
    return bool(by_status or by_spill)


def replay_at(cutoff: datetime, polls: list[datetime], slots: dict[tuple[str, date], int], history: list[dict],
              sites: list[str], hours: float = RECENT_H) -> dict:
    """What SwimSignal had received about these overflows by `cutoff`, and nothing received later.

    polls: every time the company's feed was polled. slots: (site_id, UK day) -> the bitmask of half-hour slots in
    which a poll received a known status for that overflow (live_coverage.parquet). history: the event log's rows
    (live_history.parquet): { site_id, status, status_start, start, end, fetched_at }, where fetched_at is the LAST
    poll that saw that state.

    The rules, each chosen so that a later record cannot enter:
    - Only polls at or before the cutoff count. A poll's status was known if its slot's bit is set. The file keeps
      half hours, not polls: where a poll after the cutoff shares the slot, the bit may be that later poll's, so
      the status is taken as not received.
    - A spill counts as received only if a row for it was last seen at or before the cutoff: fetched_at <= cutoff
      proves receipt. A spill whose rows were all last seen after the cutoff is counted in `unproven` and not
      shown: the archive does not keep when a state was FIRST seen.
    - An overflow with no known status at the last poll is 'unknown', with when a status was last received. No
      poll in the window is 'not polled'. Neither is ever 'not spilling'.
    - Where a status WAS received at the last poll, its value is held to the same proof as a spill. A row "covers"
      that poll when it says the overflow was spilling then: status 1 with status_start <= poll <= fetched_at, or a
      spill whose own start and stop span the poll. status_start and the spill times are the feed's own, and a
      feed can backdate them. So:
        'spilling' needs a covering row last seen at or before the cutoff (proof it had been received);
        'not spilling' needs no covering row at all, proven or not;
        otherwise the state is 'unproven': a status arrived, but only a row last seen after the cutoff says what
        it was. That is neither spilling nor not spilling, and the page puts it under Unknown.
      The state and the events list use one test of receipt (fetched_at <= cutoff), so they cannot disagree.

    Per site: { state: 'not spilling' | 'spilling' | 'unproven' | 'unknown' | 'not polled', polls, last_known_at,
    unknown_polls (polls since the last known status) }. Also events (received spills touching the window, with
    received_by, the earliest poll that provably held them) and unproven (a count)."""
    lo = cutoff - timedelta(hours=hours)
    before = sorted(t for t in polls if lo <= t <= cutoff)
    late_slots = {slot_of(t) for t in polls if t > cutoff}
    out = {}
    for s in sites:
        seen = [(t, slot_of(t)) for t in before]
        known = [bool((slots.get((s, d), 0) >> k) & 1) and (d, k) not in late_slots for t, (d, k) in seen]
        if not seen:
            out[s] = {"state": "not polled", "polls": 0, "last_known_at": None, "unknown_polls": 0}
            continue
        last_known = max((t for (t, _), k in zip(seen, known) if k), default=None)
        trailing = len(known) - 1 - max((i for i, k in enumerate(known) if k), default=-1)
        if not known[-1]:
            state = "unknown"
        else:
            t = seen[-1][0]
            covering = [r for r in history if r["site_id"] == s and _covers(r, t)]
            state = ("spilling" if any(r["fetched_at"] <= cutoff for r in covering)
                     else "unproven" if covering else "not spilling")
        out[s] = {"state": state, "polls": len(seen), "last_known_at": last_known, "unknown_polls": trailing}
    events, unproven = {}, set()
    for r in history:
        if r["site_id"] not in sites or r.get("start") is None or r["start"] > cutoff:
            continue
        end = r["end"] if r.get("end") is not None else r["fetched_at"]
        if end < lo:
            continue
        key = (r["site_id"], r["start"])
        if r["fetched_at"] <= cutoff:
            e = events.get(key)
            if e is None or r["fetched_at"] < e["received_by"]:
                closed = r.get("end") is not None
                events[key] = {"site_id": r["site_id"], "start": r["start"], "end": r["end"] if closed else None,
                               "received_by": r["fetched_at"]}
            elif r.get("end") is not None and e["end"] is None:
                e["end"] = r["end"]
        else:
            unproven.add(key)
    return {"sites": out, "events": sorted(events.values(), key=lambda e: e["start"], reverse=True),
            "unproven": len(unproven - set(events)), "polls": before}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def guard_state(state: Path, repo: Path = REPO) -> None:
    """The overflow table is written to the state folder: never this repository's, or another checkout's data."""
    s = Path(state).resolve()
    if repo.resolve() in [s, *s.parents] or any((p / ".git").exists() for p in [s, *s.parents]):
        raise CourseError(f"DIPCAST_STATE is {s}, inside a checkout. Set DIPCAST_ROOT and DIPCAST_STATE to scratch "
                          "folders first (AGENTS.md): this script writes the overflow table there.")


# ------------------------------------------------------------------ the route's facts
def _lonlat(e: float, n: float) -> tuple[float, float]:
    from dipcast.network.rivers import bng_to_lonlat
    lon, lat = bng_to_lonlat(e, n)
    return round(lat, 5), round(lon, 5)


def _upstream(net, pin, ov):
    from dipcast.model.transport import river_velocity, upstream_overflows
    return upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None))   # gauge off, as the site build's trace


def _rows(up, order_by: str = "weight") -> list[dict]:
    out = []
    for r in up.sort_values(order_by, ascending=False).itertuples(index=False):
        km = (float(r.distance_m) + float(getattr(r, "lake_distance_m", 0.0) or 0.0)) / 1000
        out.append({"site_id": r.site_id, "site_name": r.site_name, "company": r.company,
                    "water": r.receiving_watercourse if isinstance(r.receiving_watercourse, str) else None,
                    "km": round(km, 1), "travel_h": round(float(r.travel_h), 1), "weight": round(float(r.weight), 4),
                    "has_live": bool(r.has_live), "state_now": r.data_state})
    return out


def route_facts(net, ov, course: dict) -> dict:
    """The course on the network: both ends placed, the route between them, each overflow in the route tool's three
    groups, the sections, and each end's upstream overflows with their weights."""
    from dipcast import stretches as ST
    from dipcast.model.transport import _snap_to_links, locate_pin
    from dipcast.network.rivers import bng_to_lonlat

    pins, ends = {}, {}
    for end in ("start", "finish"):
        e, n = float(course[end]["easting"]), float(course[end]["northing"])
        lon, lat = bng_to_lonlat(e, n)
        pin = locate_pin(net, lon, lat, kind_hint="river", river_hint=course["river"], name=course["name"])
        if pin.mode != "river" or pin.snap is None or pin.adopted_main_channel:
            raise CourseError(f"the {end} is not placed on {course['river']} ({pin.mode}, {pin.placement})")
        pins[end] = pin
        ends[end] = {"lat": round(lat, 5), "lon": round(lon, 5), "snap_m": round(float(pin.snap.dist_m)),
                     "how": course[end]["how"], "sure": course[end]["sure"]}
    # The route tool runs downstream: from the finish (the upper end) down to the start (the lower end).
    rt = ST.route(net, pins["finish"], pins["start"], max_km=20.0)
    if rt is None:
        raise CourseError("no route down the network from the finish to the start")
    if abs(rt["m"] - float(course["length_m"])) > TOLERANCE_M:
        raise CourseError(f"the route between the ends is {rt['m']:.0f} m on the network; the course is "
                          f"{course['length_m']} m. Fix the ends in the course file.")
    up = {end: _upstream(net, pins[end], ov) for end in pins}
    where = {o.site_id: (o.link_id, float(o.frac)) for o in ov.itertuples(index=False)
             if isinstance(o.link_id, str) and o.frac == o.frac}
    counted = {end: set(up[end]["site_id"]) for end in up}
    bt = ST.between(net, rt, where, counted["finish"], counted["start"], places=2)
    km = round(rt["m"] / 1000, 2)
    from_start = lambda below_finish: None if below_finish is None else round(km - below_finish, 2)   # noqa: E731
    on_links = set(rt["inner"]) | {rt["a"][0], rt["b"][0]}
    mouths = []
    for m in course.get("mouth", []):
        sn = _snap_to_links(net, float(m["easting"]), float(m["northing"]), on_links)
        below = ST.km_below_start(net, rt, sn.link_id, sn.frac)
        lat, lon = _lonlat(float(m["easting"]), float(m["northing"]))
        mouths.append({"name": m["name"], "link": m["link"], "note": m.get("note"), "lat": lat, "lon": lon,
                       "km": from_start(below), "on_course": below is not None and 0 <= below <= km,
                       "easting": m["easting"], "northing": m["northing"]})
    # Every mouth in the file belongs to the one stream below the works: the side overflows share them.
    inflows = [{"site_id": s, "join_km": from_start(j),
                "mouths": [{"km": m["km"], "link": m["link"]} for m in mouths if m["km"] is not None]}
               for s, j in bt["side"]]
    secs = sections(km, inflows)
    start_rows = {r["site_id"]: r for r in _rows(up["start"])}
    return {"km": km, "ends": ends, "pins": pins, "rt": rt, "up": up,
            "on_route": [[s, from_start(k)] for s, k in bt["route"]], "above": bt["above"],
            "start_counts": len(counted["start"]), "beyond_start": sorted(counted["finish"] - counted["start"]),
            "inflows": [{**f, **start_rows.get(f["site_id"], {})} for f in inflows], "mouths": mouths, "sections": secs,
            "upstream": _rows(up["finish"]), "counted": counted}


# ------------------------------------------------------------------ the records
def _events(frame, source: str) -> list[dict]:
    out = []
    for r in frame.itertuples(index=False):
        if r.start != r.start:
            continue
        out.append({"site_id": r.site_id, "start": r.start.to_pydatetime(),
                    "end": None if r.end != r.end else r.end.to_pydatetime(), "source": source})
    return out


def load_events(ea_path: Path | None, history, sites: set[str]) -> list[dict]:
    """Every recorded spill at these overflows: the Environment Agency's start and stop files, and the events
    SwimSignal's polls of the live feed saw (one row per event)."""
    import pandas as pd
    out = []
    if ea_path:
        ea = pd.read_parquet(ea_path)
        ea = ea[ea["site_id"].isin(sites)]
        f = pd.DataFrame({"site_id": ea["site_id"], "start": pd.to_datetime(ea["event_start"], utc=True),
                          "end": pd.to_datetime(ea["event_end"], utc=True)})
        out += _events(f, "Environment Agency start and stop record")
    if history is not None and len(history):
        # A poll that finds an overflow still discharging has no end yet: the spill ran at least to that poll
        # (forecast_log.observed_spill_days). A later poll of the same spill, with its end, replaces it.
        h = history[history["site_id"].isin(sites)]
        end = pd.to_datetime(h["latest_event_end"], utc=True)
        f = pd.DataFrame({"site_id": h["site_id"], "start": pd.to_datetime(h["latest_event_start"], utc=True),
                          "end": end.fillna(pd.to_datetime(h["fetched_at"], utc=True)), "closed": end.notna()}).dropna(subset=["start"])
        f = f.sort_values(["closed", "end"]).drop_duplicates(["site_id", "start"], keep="last")
        f = f[f["start"] >= pd.Timestamp(LOG_FROM, tz="UTC")]
        out += _events(f, "SwimSignal's polls of the live feed")
    return out


def spill_days(events: list[dict]) -> set[tuple[str, date]]:
    """(site_id, local day) with a recorded spill, by the site's own rule (forecast_log.observed_spill_days)."""
    import pandas as pd

    from dipcast.forecast_log import observed_spill_days
    if not events:
        return set()
    h = pd.DataFrame({"site_id": [e["site_id"] for e in events], "status": 0,
                      "latest_event_start": [e["start"] for e in events],
                      "latest_event_end": [e["end"] or e["start"] for e in events],
                      "fetched_at": [e["end"] or e["start"] for e in events]})
    d = observed_spill_days(h)
    return set(zip(d["site_id"], d["day"]))


def rebuilt_index(up, days_spilled: set[tuple[str, date]], day: date) -> int:
    """The exposure index (0 to 100) on `day` at one end of the course, with each overflow's recorded spill days in
    place of the forecast's spill chances: transport.combine_daily over the same weights and travel times."""
    import numpy as np

    from dipcast.model.transport import combine_daily, history_days
    if not len(up):
        return 0
    grid = [day - timedelta(days=k) for k in range(history_days(up["travel_h"]), -1, -1)]
    p = np.array([[1.0 if (s, d) in days_spilled else 0.0 for d in grid] for s in up["site_id"]])
    return int(round(100 * float(combine_daily(p, up["weight"].to_numpy(float), up["travel_h"].to_numpy(float))[-1])))


def issued_record(state: Path, spot: str, issue: str | None) -> dict | None:
    """The page record kept for this spot at this issue (issue_history), as it was issued."""
    import pandas as pd
    if not issue:
        return None
    stamp = issue.split("-")[-1]                       # 20261101T0832Z
    f = Path(state) / f"issued-{stamp[:4]}-{stamp[4:6]}.parquet"
    if not f.exists():
        raise CourseError(f"{f} is not in the state folder: download the state release first")
    d = pd.read_parquet(f)
    row = d[(d["spot"] == spot) & (d["issue_id"] == issue)]
    if len(row) != 1:
        raise CourseError(f"issue {issue} has {len(row)} records for {spot} in {f.name}")
    rec = json.loads(row.iloc[0]["record"])
    at = pd.Timestamp(row.iloc[0]["issued_at"]).tz_convert(UK)
    return {"issue": issue, "issued_at": at.isoformat(timespec="minutes"), "level": rec.get("level"),
            "now_level": rec.get("nowLevel"), "now_score": rec.get("nowScore"), "days": rec.get("days"),
            "reporting": rec.get("reporting"), "upstream": rec.get("upstream"), "discharging": rec.get("discharging"),
            "recent": rec.get("recent"), "model": rec.get("model")}


def same_time(d: dict, facts: dict, history, coverage, poll_log, issued: dict | None) -> dict | None:
    """The same-time comparison for one date: the course's monitors as received by the decision time
    (replay_at), beside the pin's archived issue. None before the forecast log, when nothing was polled."""
    import pandas as pd
    if d["day"] < LOG_FROM or history is None or coverage is None or poll_log is None:
        return None
    cutoff = datetime.fromisoformat(d["as_of"]).replace(tzinfo=UK)
    if issued and issue_time(issued["issue"]) > cutoff:
        raise CourseError(f"{d['id']}: issue {issued['issue']} is after the decision time {d['as_of']}")
    side = {f["site_id"] for f in facts["inflows"]}
    rows = {r["site_id"]: r for r in facts["upstream"]} | {f["site_id"]: f for f in facts["inflows"]}
    sites = sorted(rows)
    company = {r.get("company") for r in rows.values()}
    polls = [t.to_pydatetime() for t in pd.to_datetime(poll_log[poll_log["company"].isin(company)]["fetched_at"], utc=True).drop_duplicates()]
    c = coverage[coverage["site_id"].isin(sites)]
    slots = {(r.site_id, pd.Timestamp(r.day).date()): int(r.slots) for r in c.itertuples(index=False)}
    h = history[history["site_id"].isin(sites)]
    ts = lambda v: None if v != v or v is None else pd.Timestamp(v).tz_convert("UTC").to_pydatetime()   # noqa: E731
    hist = [{"site_id": r.site_id, "status": int(r.status), "status_start": ts(r.status_start), "start": ts(r.latest_event_start),
             "end": ts(r.latest_event_end), "fetched_at": ts(r.fetched_at)} for r in h.itertuples(index=False)]
    got = replay_at(cutoff, polls, slots, hist, sites)
    local = lambda t: None if t is None else t.astimezone(UK).isoformat(timespec="minutes")   # noqa: E731
    one = lambda s: {"site_id": s, "site_name": rows[s].get("site_name"), "km": rows[s].get("km"), "weight": rows[s].get("weight"),   # noqa: E731
                     "side": s in side, "state": got["sites"][s]["state"], "last_known_at": local(got["sites"][s]["last_known_at"]),
                     "unknown_polls": got["sites"][s]["unknown_polls"]}
    main = [s for s in sites if s not in side]
    return {"cutoff": cutoff.isoformat(timespec="minutes"), "window_h": RECENT_H,
            "polls": len(got["polls"]), "last_poll": local(got["polls"][-1]) if got["polls"] else None,
            "prev_poll": local(got["polls"][-2]) if len(got["polls"]) > 1 else None,
            "counted": len(main), "known": sum(got["sites"][s]["state"] in ("not spilling", "spilling") for s in main),
            "spilling": [one(s) for s in main if got["sites"][s]["state"] == "spilling"],
            "unproven_state": [one(s) for s in main if got["sites"][s]["state"] == "unproven"],
            "unknown": sorted((one(s) for s in main if got["sites"][s]["state"] in ("unknown", "not polled")), key=lambda r: -(r["weight"] or 0)),
            "side": [one(s) for s in sites if s in side],
            "events": [{"site_id": e["site_id"], "site_name": rows[e["site_id"]].get("site_name"), "km": rows[e["site_id"]].get("km"),
                        "weight": rows[e["site_id"]].get("weight"), "side": e["site_id"] in side, "start": local(e["start"]),
                        "end": local(e["end"]), "received_by": local(e["received_by"])} for e in got["events"]],
            "unproven": got["unproven"]}


def date_record(d: dict, facts: dict, events: list[dict], coverage, state: Path, spot: str, names: dict,
                history=None, poll_log=None) -> dict:
    import pandas as pd
    day = date.fromisoformat(d["day"])
    as_of = datetime.fromisoformat(d["as_of"]).replace(tzinfo=UK)
    every = facts["counted"]["start"] | facts["counted"]["finish"]
    days_spilled = spill_days([e for e in events if e["start"] <= as_of.replace(hour=23, minute=59)])
    hit = events_in_window([e for e in events if e["site_id"] in every], as_of)
    local = lambda t: None if t is None else t.astimezone(UK).isoformat(timespec="minutes")   # noqa: E731
    side = {f["site_id"] for f in facts["inflows"]}
    # Each overflow's weight where it counts first: at the finish, or for a side stream's overflow at the start.
    weights = {r["site_id"]: r["weight"] for r in facts["upstream"]} | {f["site_id"]: f.get("weight") for f in facts["inflows"]}
    spills = [{"site_id": e["site_id"], "start": local(e["start"]), "end": local(e["end"]) if e["end"] and e["end"] <= as_of else None,
               "ended_after": bool(e["end"] and e["end"] > as_of), "source": e["source"], "side": e["site_id"] in side,
               "weight": weights.get(e["site_id"])}
              for e in hit]
    monitors = None
    if coverage is not None and d["day"] >= LOG_FROM:
        c = coverage[(coverage["day"].astype(str) == d["day"]) & coverage["site_id"].isin(every)].set_index("site_id")
        monitors = {}
        for s in sorted(every):
            k, u = (int(c.loc[s, "n_known"]), int(c.loc[s, "n_unknown"])) if s in c.index else (None, None)
            st = monitor_state(k, u)
            if st != "reported":
                monitors[s] = {"state": st, "known": k, "unknown": u, "side": s in side}
        polls = int(pd.concat([c["n_known"] + c["n_unknown"]]).max()) if len(c) else 0
        monitors = {"polls": polls, "counted": len(every), "not_reporting": monitors}
    issued = issued_record(state, spot, d.get("issue"))
    replay = same_time(d, facts, history, coverage, poll_log, issued)
    return {"id": d["id"], "day": d["day"], "as_of": as_of.isoformat(timespec="minutes"), "title": d["title"],
            "kind": "same time" if replay else "historical", "replay": replay,
            "issued": issued,
            "no_issue_why": None if d.get("issue") else (
                "SwimSignal's forecast log starts on 12 September 2026, so nothing was issued for this date."
                if d["day"] < LOG_FROM else "No page record was kept for this date."),
            "rebuilt": {"finish": rebuilt_index(facts["up"]["finish"], days_spilled, day),
                        "start": rebuilt_index(facts["up"]["start"], days_spilled, day)},
            "spills": spills, "monitors": monitors, "names": {s["site_id"]: names.get(s["site_id"]) for s in spills}}


def poll_facts(state: Path, company: str) -> dict | None:
    """How often SwimSignal's build has polled this company's feed, over the 30 days to its last poll."""
    import pandas as pd
    f = Path(state) / "poll_log.parquet"
    if not f.exists():
        return None
    p = pd.read_parquet(f)
    t = p[p["company"] == company].sort_values("fetched_at")
    t = t[t["fetched_at"] >= t["fetched_at"].max() - pd.Timedelta(days=30)]
    gap = t["fetched_at"].diff().dt.total_seconds().dropna() / 3600
    if not len(gap):
        return None
    return {"company": company, "polls": int(len(t)), "to": t["fetched_at"].max().tz_convert(UK).isoformat(timespec="minutes"),
            "median_gap_h": round(float(gap.median()), 1), "longest_gap_h": round(float(gap.max()), 1),
            "gaps_over_6h": int((gap > 6).sum())}


def bathing_waters(net, ids: list[str], finish_pin, root: Path) -> list[dict]:
    """Each named bathing water's distance down the network to the finish, by the route tool; None where no route
    down joins them within 80 km."""
    from dipcast import stretches as ST
    from dipcast.model.transport import locate_pin
    rows = {r["id"]: r for r in json.loads((root / "data" / "raw" / "bathing_waters_inland.json").read_text())}
    out = []
    for i in ids:
        r = rows.get(i)
        if not r:
            raise CourseError(f"bathing water {i} is not in bathing_waters_inland.json")
        pin = locate_pin(net, float(r["lon"]), float(r["lat"]), kind_hint="river", river_hint="River Thames", name=r["name"])
        rt = ST.route(net, pin, finish_pin, max_km=80.0) if pin.mode == "river" and pin.snap is not None else None
        out.append({"id": i, "name": r["name"], "designated": str(r.get("year_designated", ""))[-4:],
                    "km_above_finish": None if rt is None else round(rt["m"] / 1000, 1)})
    return out


def spot_above_finish_m(net, spot_id: str, finish_pin) -> int | None:
    """How far the listed spot's pin is above the finish, in metres down the network (spots.csv, placed as the
    site build places it); None where it is not above it."""
    import csv

    from dipcast import stretches as ST
    from dipcast.model.transport import locate_pin, spot_hints
    with open(REPO / "spots.csv", newline="", encoding="utf-8") as f:
        row = next((r for r in csv.DictReader(f) if r["id"] == spot_id), None)
    if row is None:
        raise CourseError(f"{spot_id} is not in spots.csv")
    kind, river = spot_hints(row["kind"], row["river"])
    pin = locate_pin(net, float(row["lon"]), float(row["lat"]), kind_hint=kind, river_hint=river, name=row["name"])
    rt = ST.route(net, pin, finish_pin, max_km=20.0) if pin.mode == "river" and pin.snap is not None else None
    return None if rt is None else int(round(rt["m"]))


# ------------------------------------------------------------------ the plate (a drawing of the reach)
def plate(net, facts: dict, course: dict, openmap: Path | None) -> dict | None:
    """The reach as a small drawing: OS OpenMap Local's water, the OS Open Rivers lines SwimSignal traces, the
    course and its marks, in metres from the drawing's top left. None without the OpenMap folder: the caller then
    keeps the drawing already in course.json."""
    if openmap is None:
        return None
    import geopandas as gpd
    from shapely.geometry import box

    from dipcast.network.rivers import lonlat_to_bng
    pts = [(float(course[e]["easting"]), float(course[e]["northing"])) for e in ("start", "finish")]
    pts += [(float(m["easting"]), float(m["northing"])) for m in course.get("mouth", [])]
    works = [lonlat_to_bng(f["lon"], f["lat"]) for f in facts["works"]]
    pts += works
    x0, x1 = min(p[0] for p in pts) - PLATE_PAD_M, max(p[0] for p in pts) + PLATE_PAD_M
    y0, y1 = min(p[1] for p in pts) - PLATE_PAD_M, max(p[1] for p in pts) + PLATE_PAD_M
    win = box(x0, y0, x1, y1)
    pt = lambda x, y: f"{x - x0:.0f},{y1 - y:.0f}"   # noqa: E731
    ring = lambda r: "M" + "L".join(pt(*c[:2]) for c in r.coords) + "Z"   # noqa: E731

    def parts(g, kind):
        if g.is_empty:
            return []
        if g.geom_type.startswith("Multi") or g.geom_type == "GeometryCollection":
            return [p for q in g.geoms for p in parts(q, kind)]
        return [g] if g.geom_type == kind else []

    area = gpd.read_file(Path(openmap) / "SU_SurfaceWater_Area.shp", bbox=(x0, y0, x1, y1))
    line = gpd.read_file(Path(openmap) / "SU_SurfaceWater_Line.shp", bbox=(x0, y0, x1, y1))
    water = "".join(ring(p.exterior) + "".join(ring(i) for i in p.interiors)
                    for g in area.geometry for p in parts(g.intersection(win).simplify(3.0), "Polygon"))
    ditches = "".join("M" + "L".join(pt(*c[:2]) for c in p.coords)
                      for g in line.geometry for p in parts(g.intersection(win).simplify(3.0), "LineString"))
    rt = facts["rt"]
    L = net.links
    traced = "".join("M" + "L".join(pt(*c[:2]) for c in p.coords)
                     for g in L[L.intersects(win)].geometry for p in parts(g.intersection(win).simplify(2.0), "LineString"))

    def along(below_km: float) -> tuple[float, float]:
        """The point on the route this many km below the finish."""
        m, (la, fa, _), (lb, _, _) = below_km * 1000, rt["a"], rt["b"]
        head = (1 - fa) * float(L.loc[la, "length"])
        if m <= head or la == lb:
            p = L.loc[la, "geometry"].interpolate(fa * float(L.loc[la, "length"]) + m)
            return p.x, p.y
        for lid in rt["inner"]:
            s = rt["nodes"][net.link_nodes(lid)[0]]
            if s <= m <= s + float(L.loc[lid, "length"]):
                p = L.loc[lid, "geometry"].interpolate(m - s)
                return p.x, p.y
        p = L.loc[lb, "geometry"].interpolate(max(0.0, m - rt["nodes"][net.link_nodes(lb)[0]]))
        return p.x, p.y

    km = facts["km"]
    cuts = sorted({s["from_km"] for s in facts["sections"]} | {km})
    seg = []
    for s in facts["sections"]:
        a, b = km - s["to_km"], km - s["from_km"]                      # km below the finish
        seg.append({"from_km": s["from_km"], "to_km": s["to_km"],
                    "d": "M" + "L".join(pt(*along(a + (b - a) * i / 30)) for i in range(31))})
    xy = lambda p: [round(p[0] - x0), round(y1 - p[1])]   # noqa: E731
    marks = [{"kind": "start", "label": "Start", "at": xy(pts[0])}, {"kind": "finish", "label": "Finish", "at": xy(pts[1])}]
    marks += [{"kind": "cut", "label": f"{c:.2f} km", "at": xy(along(km - c))} for c in cuts if 0 < c < km]
    marks += [{"kind": "mouth", "label": m["name"], "link": m["link"], "at": xy((float(m["easting"]), float(m["northing"])))}
              for m in course.get("mouth", [])]
    marks += [{"kind": "works", "label": f["site_name"], "at": xy(w)} for f, w in zip(facts["works"], works)]
    return {"w": round(x1 - x0), "h": round(y1 - y0), "water": water, "ditches": ditches, "traced": traced,
            "sections": seg, "marks": marks,
            "credit": "Water: OS OpenMap Local, October 2026. Traced lines: OS Open Rivers, as SwimSignal mends them. "
                      "Contains OS data © Crown copyright and database right 2026."}


# ------------------------------------------------------------------ the whole file
def build(course_path: Path, events_path: Path | None, openmap: Path | None, out: Path | None = None) -> dict:
    import pandas as pd

    from dipcast import config
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import build_overflows
    sys.path.insert(0, str(REPO / "scripts"))
    import briefing   # the organiser tools' wording

    guard_state(config.STATE)
    course = load_course(course_path)
    out = out or Path(course_path).with_name("course.json")
    inputs = {"river_network.pkl": config.PROCESSED / "river_network.pkl", "annual_returns.parquet": config.PROCESSED / "annual_returns.parquet",
              "overflow_joins.csv": config.RAW / "overflow_joins.csv", "network_fixes.csv": config.RAW / "network_fixes.csv",
              "live_latest.parquet": config.state_read("live_latest.parquet"), "live_history.parquet": config.state_read("live_history.parquet"),
              "live_coverage.parquet": config.state_read("live_coverage.parquet"), "poll_log.parquet": config.state_read("poll_log.parquet"),
              **({"ea_events": Path(events_path)} if events_path else {})}
    before = {k: sha256(p) for k, p in inputs.items() if Path(p).exists()}
    net = RiverNetwork.load()
    ov = build_overflows(net)          # written to DIPCAST_STATE (scratch): never the shared table
    facts = route_facts(net, ov, course)
    side_ids = [f["site_id"] for f in facts["inflows"]]
    facts["works"] = [{"site_id": r.site_id, "site_name": r.site_name, "lat": float(r.lat), "lon": float(r.lon)}
                      for r in ov[ov["site_id"].isin(side_ids)].itertuples(index=False)]
    every = facts["counted"]["start"] | facts["counted"]["finish"]
    history = pd.read_parquet(inputs["live_history.parquet"]) if Path(inputs["live_history.parquet"]).exists() else None
    coverage = pd.read_parquet(inputs["live_coverage.parquet"]) if Path(inputs["live_coverage.parquet"]).exists() else None
    events = load_events(events_path, history, every)
    names = {r["site_id"]: r["site_name"] for r in facts["upstream"]} | {f["site_id"]: f.get("site_name") for f in facts["inflows"]}
    poll_log = pd.read_parquet(inputs["poll_log.parquet"]) if Path(inputs["poll_log.parquet"]).exists() else None
    dates = [date_record(d, facts, events, coverage, config.STATE, course["spot"], names, history, poll_log) for d in course["date"]]
    ar = pd.read_parquet(inputs["annual_returns.parquet"])
    returns = {s: [{"year": int(r.year), "spills": None if r.spills != r.spills else int(r.spills),
                    "hours": None if r.spill_hours != r.spill_hours else round(float(r.spill_hours))}
                   for r in ar[ar["site_id"] == s].sort_values("year").itertuples(index=False)] for s in side_ids}
    last_event = {s: max((e["start"] for e in events if e["site_id"] == s), default=None) for s in side_ids}
    drawing = plate(net, facts, course, openmap)
    pin_m = spot_above_finish_m(net, course["spot"], facts["pins"]["finish"])
    if drawing is None and out.exists():
        drawing = json.loads(out.read_text()).get("plate")
    companies = sorted({r["company"] for r in facts["upstream"]} | {f.get("company") for f in facts["inflows"]} - {None})
    after = {k: sha256(p) for k, p in inputs.items() if Path(p).exists()}
    if after != before:
        raise CourseError("an input changed while the script ran: " + ", ".join(k for k in before if before[k] != after.get(k)))
    doc = {
        "contract": CONTRACT,
        "made": datetime.now(UK).isoformat(timespec="minutes"),
        "course": {k: course.get(k) for k in ("id", "name", "organiser", "source_url", "source_read", "said", "next_event",
                                             "next_event_start", "length_m", "river", "spot")},
        "km": facts["km"], "ends": facts["ends"], "pin_above_finish_m": pin_m,
        "limits": briefing.LIMITS, "decides": briefing.DECIDES.format(org="The organiser"),
        "sections": facts["sections"], "inflows": [{**f, "returns": returns.get(f["site_id"]),
                                                    "last_event": None if last_event.get(f["site_id"]) is None else last_event[f["site_id"]].astimezone(UK).isoformat(timespec="minutes")}
                                                   for f in facts["inflows"]],
        "mouths": [{k: m[k] for k in ("name", "link", "note", "lat", "lon", "km", "on_course")} for m in facts["mouths"]],
        "on_route": facts["on_route"], "above": facts["above"], "start_counts": facts["start_counts"],
        "beyond_start": facts["beyond_start"], "upstream": facts["upstream"],
        "companies": companies,
        "observations": course.get("observation", []),
        "bathing_waters": bathing_waters(net, course.get("bathing_waters", []), facts["pins"]["finish"], config.ROOT),
        "polls": poll_facts(config.STATE, "Thames Water"),
        "log_from": LOG_FROM, "records_from": RECORDS_FROM, "recent_h": RECENT_H,
        "dates": dates, "plate": drawing,
        "inputs": {k: v[:16] for k, v in before.items()},
    }
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("course", type=Path)
    ap.add_argument("--events", type=Path, help="the Environment Agency start and stop file for the company (parquet)")
    ap.add_argument("--openmap", type=Path, help="OS OpenMap Local's data folder, to redraw the plate")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    try:
        doc = build(a.course, a.events, a.openmap, a.out)
    except CourseError as e:
        print(f"course briefing: {e}", file=sys.stderr)
        return 1
    print(f"{doc['course']['name']}: {doc['km']} km, {len(doc['sections'])} sections, {len(doc['upstream'])} overflows above the "
          f"finish, {len(doc['inflows'])} more by the start, {len(doc['dates'])} dates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
