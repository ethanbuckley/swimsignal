"""Catchment replay (prototype, docs/CATCHMENT-REPLAY-2026-10.md): for one spot, the last 48 hours
upstream, from what the build already holds.

  observed     each upstream overflow's spills as its company's live feed reported them, from the poll
               history (ingest.live, live_history.parquet) and this build's poll (the contributors);
               and the times a monitor reported itself offline
  estimated    when each spill's water was modelled to reach the spot: the spill's start and end moved
               on by the overflow's travel time (model.transport, travel_h), the same shift the
               forecast uses. Never a measurement.
  rain         Open-Meteo's hourly rain over the cells of the counted overflows, read from the rain cache
               the build's own prefetch filled (ingest.rainfall, forecast_<cell>.parquet). Past hours are
               the weather model's record, not rain gauges; hours after the cache was issued are forecast.
  gauge        the spot gauge's latest reading and six-hour rise, as attach_river_levels and
               attach_flow_state already fetched them. No 48-hour series: the build holds none.

What is not held is marked unavailable and never filled: a spill whose end the feed never reported has
no end, an hour of rain missing at any cell has no value, and a monitor with no reading is listed as such.
Nothing here says a spill caused anything; the words are the page's (replay.js).

No requests: this reads the poll history, the rain cache and the build's results. It never calls
Open-Meteo or the EA."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config

log = logging.getLogger(__name__)

WINDOW_H = 48.0            # how far back the replay looks
AHEAD_MAX_H = 24.0         # water still due later than now is drawn this far ahead at most
MAX_ROWS = 12              # overflows listed with their spills; the rest are counted
MAX_SPILLS = 8             # spills listed per overflow, the latest; earlier ones in the window are counted
MIN_WEIGHT = 0.005         # transport.COUNT_WEIGHT: under it the page says "0% reach", so not listed
REPLAY_MAX_BYTES = 20_000  # a file at MAX_ROWS x MAX_SPILLS (tests/test_replay.py); real spots were 2-7 kB on 25 Oct 2026
SPOT_ID = re.compile(r"[A-Za-z0-9_-]+")
FEED_DOWN = -3             # ingest.live.FEED_DOWN, repeated so this module needs nothing from the feed code
STATES = ("live", "stale", "offline", "no_feed")


def _ts(x) -> pd.Timestamp | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    try:
        t = pd.Timestamp(x)
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _iso(t: pd.Timestamp | None) -> str | None:
    return None if t is None else t.tz_convert("UTC").strftime("%Y-%m-%dT%H:%MZ")


def _key(t: pd.Timestamp) -> pd.Timestamp:
    return t.floor("min")


def _first(*xs) -> pd.Timestamp | None:
    """The first of xs that is a time (NaT, None and NaN are not)."""
    return next((t for t in map(_ts, xs) if t is not None), None)


def spill_intervals(history: pd.DataFrame, current: dict, now: pd.Timestamp) -> list[dict]:
    """One overflow's reported spills, oldest first: {start, end, running, end_known}. `history` is its
    rows of live_history.parquet (any order), `current` its row in this build (status, latest_event_*,
    last_status). A start with no reported end is `running` when the feed says it is discharging now, and
    otherwise has no end (`end_known` False): the feed went offline or stopped answering, so when it ended
    is not known, and nothing is drawn after the start. An end before its start (a feed's previous
    event's) is ignored."""
    events: dict[pd.Timestamp, pd.Timestamp | None] = {}

    def put(s, e) -> None:
        s, e = _ts(s), _ts(e)
        if s is None or s > now:
            return
        k = _key(s)
        if e is not None and (e < s or e > now):
            e = None
        if e is not None or k not in events:
            events[k] = e if e is not None else events.get(k)

    rows = [] if history is None or history.empty else history.to_dict("records")
    for r in [*rows, current]:
        put(r.get("latest_event_start"), r.get("latest_event_end"))
        if r.get("status") == 1:
            put(_first(r.get("status_start"), r.get("latest_event_start")), None)
    status = current.get("status")
    running_from = None
    if status == 1:
        running_from = _first(current.get("status_start"), current.get("latest_event_start"))
        if running_from is not None and running_from <= now:
            running_from = _key(running_from)
            events[running_from] = None   # discharging now: whatever end an earlier poll had is not this one's
    # A start with no reported event end is closed by the feed's next "not discharging" (a status-0
    # row's status start, the time the feed says it stopped), when there is one. Yorkshire Water's
    # latest event is the last part of a spill (YWS00199 on 24 Oct 2026: discharging from 17:04,
    # stopped 20:51:50, "latest event" 20:51:20 to 20:51:50), so its start alone would lose the rest.
    stops = sorted(t for r in [*rows, current] if r.get("status") == 0
                   and (t := _ts(r.get("status_start"))) is not None and t <= now)
    for k in [k for k, e in events.items() if e is None and k != running_from]:
        events[k] = next((t for t in stops if t >= k), None)
    # An event inside a longer one (the part a feed reports as its latest event, or the same start a
    # minute apart) is that one, not another spill. Longest first at each start.
    minute = pd.Timedelta(minutes=1)

    def until(k, e):
        return now if k == running_from else e

    kept: list[tuple[pd.Timestamp, pd.Timestamp | None]] = []
    for k, e in sorted(events.items(), key=lambda x: (x[0], -((until(*x) or x[0]) - x[0]).total_seconds())):
        end = until(k, e)
        covered = any(until(a, b) is not None and a <= k + minute and (end or k) <= until(a, b) + minute for a, b in kept)
        if not covered:
            kept.append((k, e))
    out = []
    for k, e in kept:
        if k == running_from:
            out.append({"start": k, "end": None, "running": True, "end_known": False})
        elif e is None:   # never closed: the feed went offline or stopped answering before it said
            out.append({"start": k, "end": None, "running": False, "end_known": False})
        else:
            out.append({"start": k, "end": e, "running": False, "end_known": True})
    return out


def offline_spans(history: pd.DataFrame, current: dict, now: pd.Timestamp) -> list[dict]:
    """When the overflow's monitor reported itself offline (status -1), from the poll history: each from
    the time the feed gives (status_start, else the poll) to the next reported state, or to now while it
    is still offline. A company feed that did not answer (status -3, this build only) is a span from
    `feed_down_since`. Oldest first, as {from, to}."""
    rows = [] if history is None or history.empty else history.to_dict("records")
    seq = []
    for r in rows:
        b = _first(r.get("status_start"), r.get("fetched_at"))
        if b is not None and b <= now:
            seq.append((b, r.get("status")))
    seq.sort(key=lambda x: x[0])
    out = []
    for i, (b, st) in enumerate(seq):
        if st != -1:
            continue
        nxt = seq[i + 1][0] if i + 1 < len(seq) else None
        if nxt is None:
            nxt = now if current.get("status") == -1 else None
        out.append({"from": b, "to": nxt})
    if current.get("status") == FEED_DOWN:
        since = _ts(current.get("feed_down_since"))
        if since is not None:
            out.append({"from": since, "to": now, "feed_down": True})
    return out


def arrival(spill: dict, travel_h: float | None, now: pd.Timestamp) -> dict | None:
    """When a spill's water was modelled to reach the spot: its start and end moved on by travel_h.
    `state`: 'due' (not there yet), 'at_spot' (arriving now), 'passed' (its last water modelled past the
    spot), or 'unknown_end' (the spill's end was not reported, so neither is when its water passed).
    None without a travel time."""
    if travel_h is None or not np.isfinite(travel_h):
        return None
    shift = pd.Timedelta(hours=float(travel_h))
    a = spill["start"] + shift
    b = spill["end"] + shift if spill["end"] is not None else None
    if a > now:
        state = "due"
    elif b is not None and b <= now:
        state = "passed"
    elif spill["running"] or b is not None:
        state = "at_spot"
    else:
        state = "unknown_end"
    return {"from": a, "to": b, "state": state}


def rain_series(cells: list[tuple[float, float]], start: pd.Timestamp, hours: int, cache_dir: Path) -> dict:
    """Hourly rain over `cells` from the build's rain cache, `hours` values from `start`. An hour has a
    value only where every cell has one (the mean of them); otherwise None. `forecast_from` is the
    earliest cache issue time: hours from then on are forecast, not the model's record of the past.
    With no cell cached: {"unavailable": reason}. Reads files only."""
    if not cells:
        return {"unavailable": "no counted overflow upstream"}
    frames, issued = [], []
    for cl, cn in cells:
        p = cache_dir / f"forecast_{cl + 0.0:.3f}_{cn + 0.0:.3f}.parquet"
        if not p.exists():
            return {"unavailable": "not every rain cell upstream is in this build's rain cache"}
        try:
            df = pd.read_parquet(p, columns=["time", "precip_mm", "issued_at"])
        except Exception as e:  # noqa: BLE001 - a torn cache file counts as none
            log.warning("replay rain %s: %s", p.name, e)
            return {"unavailable": "a rain cache file could not be read"}
        t = pd.to_datetime(df["time"], utc=True)
        frames.append(pd.Series(df["precip_mm"].to_numpy(dtype=float), index=t))
        if len(df) and (t0 := _ts(df["issued_at"].iloc[0])) is not None:
            issued.append(t0)
    grid = pd.date_range(start.floor("h"), periods=hours, freq="h", tz="UTC")
    m = np.vstack([s[~s.index.duplicated()].reindex(grid).to_numpy(dtype=float) for s in frames])
    ok = np.isfinite(m).all(axis=0)
    mean = np.where(ok, np.nanmean(np.where(np.isfinite(m), m, 0.0), axis=0) if len(m) else np.nan, np.nan)
    vals = [None if not np.isfinite(v) else round(float(v), 1) for v in mean]
    first = min(issued) if issued else None
    return {"start": _iso(grid[0]), "step_h": 1, "mm": vals, "cells": len(cells),
            "issued_at": _iso(first), "forecast_from": _iso(first.ceil("h")) if first is not None else None}


def gauge_of(spot: dict) -> dict:
    """The spot gauge as this build read it: the latest reading, and the six-hour rise where the build
    fetched one. Nothing older is held."""
    rs = spot.get("river_state") or {}
    if not rs or (rs.get("level_m") is None and rs.get("last_level_m") is None):
        return {"unavailable": "no level gauge matched to this spot"}
    out = {"station": rs.get("station"), "river": rs.get("river"), "level_m": rs.get("level_m"),
           "observed_at": rs.get("observed_at"), "stale": bool(rs.get("stale")),
           "typical_low_m": rs.get("typical_low_m"), "typical_high_m": rs.get("typical_high_m")}
    if rs.get("stale"):
        out["level_m"], out["last_level_m"] = None, rs.get("last_level_m")
    if rs.get("rise_6h_m") is not None:
        out.update(rise_6h_m=rs.get("rise_6h_m"), rise_from=rs.get("rise_from"), rise_to=rs.get("rise_to"))
    return out


def _state(c: dict) -> str:
    s = c.get("data_state")
    if s in STATES:
        return s
    st = c.get("status")
    return "live" if st in (0, 1) else "no_feed" if st == -2 else "offline"


def spot_replay(spot: dict, upstream: list[dict], history: pd.DataFrame | None, now: pd.Timestamp,
                rain_cache: Path | None = None) -> dict:
    """The replay for one spot: `upstream` is every overflow the forecast counted there (the build's
    full contributor list), `history` live_history.parquet (all sites; None if there is none)."""
    since = now - pd.Timedelta(hours=WINDOW_H)
    by_site = {k: g for k, g in history.groupby("site_id")} if history is not None and len(history) else {}
    counted = [c for c in upstream if (c.get("weight") or 0) >= MIN_WEIGHT]
    rows, quiet = [], {s: {"n": 0, "weight": 0.0} for s in STATES}
    for c in counted:
        h = by_site.get(c.get("site_id"))
        travel = c.get("travel_h")
        spills = [s for s in spill_intervals(h, c, now)
                  if (s["end"] or now) >= since
                  or (travel is not None and (s["end"] or now) + pd.Timedelta(hours=float(travel)) >= since)]
        offline = [o for o in offline_spans(h, c, now) if (o["to"] or now) >= since]
        state = _state(c)
        if not spills and not offline:
            quiet[state]["n"] += 1
            quiet[state]["weight"] += float(c.get("weight") or 0)
            continue
        rows.append({
            "site_id": c.get("site_id"), "name": c.get("site_name"), "company": c.get("company"),
            "receiving": c.get("receiving_watercourse"),
            "km": round(float(c.get("distance_km") or 0) + float(c.get("lake_distance_km") or 0), 1),
            "travel_h": travel, "weight": c.get("weight"), "state": state,
            "status": c.get("status"),
            "spills": [{"start": _iso(s["start"]), "end": _iso(s["end"]), "running": s["running"],
                        "end_known": s["end_known"], "arrival": _arr(arrival(s, travel, now))} for s in spills[-MAX_SPILLS:]],
            "earlier_spills": max(0, len(spills) - MAX_SPILLS),
            "offline": [{"from": _iso(o["from"]), "to": _iso(o["to"]), **({"feed_down": True} if o.get("feed_down") else {})}
                        for o in offline],
        })
    rows.sort(key=lambda r: -(r["weight"] or 0))
    more = rows[MAX_ROWS:]
    cells = sorted({(float(a), float(b)) for a, b in zip(*_cells(counted), strict=True)})
    ahead = max([(_ts(a["to"]) or _ts(a["from"])) for r in rows[:MAX_ROWS] for s in r["spills"]
                 if (a := s["arrival"]) and a["state"] == "due"] or [now])
    return {
        "id": spot.get("id"), "window": {"from": _iso(since), "to": _iso(now), "hours": WINDOW_H,
                                         "ahead_to": _iso(min(ahead, now + pd.Timedelta(hours=AHEAD_MAX_H)))},
        "counted": len(counted),
        "overflows": rows[:MAX_ROWS],
        "more_with_events": len(more),
        "quiet": {k: {"n": v["n"], "weight": round(v["weight"], 3)} for k, v in quiet.items() if v["n"]},
        "rain": rain_series(cells, since, int(WINDOW_H), rain_cache) if rain_cache is not None
        else {"unavailable": "rain cache not read"},
        "gauge": gauge_of(spot),
        "recent_spill_hours": config.RECENT_SPILL_HOURS, "t90_hours": config.T90_HOURS,
    }


def _arr(a: dict | None) -> dict | None:
    return None if a is None else {"from": _iso(a["from"]), "to": _iso(a["to"]), "state": a["state"]}


def _cells(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    lat = np.array([float(r["lat"]) for r in rows if r.get("lat") is not None and r.get("lon") is not None])
    lon = np.array([float(r["lon"]) for r in rows if r.get("lat") is not None and r.get("lon") is not None])
    if not len(lat):
        return np.zeros(0), np.zeros(0)
    d = config.RAIN_GRID_DEG   # ingest.rainfall.grid_cell, without importing the request code
    return (np.round(np.round(lat / d) * d, 3) + 0.0, np.round(np.round(lon / d) * d, 3) + 0.0)


def load_history(path: Path | None = None) -> pd.DataFrame | None:
    p = path or config.state_read("live_history.parquet")
    if not p.exists():
        return None
    return pd.read_parquet(p, columns=["site_id", "status", "status_start", "latest_event_start", "latest_event_end", "fetched_at"])


def write_replays(site: Path, results: list[dict], upstream: dict[str, list[dict]], now: pd.Timestamp,
                  history: pd.DataFrame | None = None, rain_cache: Path | None = None) -> dict:
    """data/spot/<id>-replay.json for each spot with an id that can be a file name and a forecast. After
    write_app_data, which clears data/spot/. The page asks for it only with ?replay=1. Returns counts
    and the largest file's size for the build log."""
    out = site / "data" / "spot"
    out.mkdir(parents=True, exist_ok=True)
    history = load_history() if history is None else history
    rain_cache = rain_cache or (config.CACHE / "rain")
    n, largest = 0, (None, 0)
    for r in results:
        sid = str(r.get("id"))
        if r.get("error") or not SPOT_ID.fullmatch(sid):
            continue
        body = json.dumps({**spot_replay(r, upstream.get(sid, []), history, now, rain_cache),
                           "generated_at": now.isoformat()}, separators=(",", ":"), default=str)
        (out / f"{sid}-replay.json").write_text(body)
        n += 1
        if len(body) > largest[1]:
            largest = (sid, len(body))
    out = {"written": n, "largest": largest[0], "largest_bytes": largest[1], "history": history is not None}
    if largest[1] > REPLAY_MAX_BYTES:
        out["warning"] = f"{largest[0]}'s replay is {largest[1] / 1e3:.0f} kB, over {REPLAY_MAX_BYTES / 1e3:.0f} kB"
    return out
