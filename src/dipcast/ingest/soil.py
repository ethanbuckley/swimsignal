"""Root-zone soil moisture for the river E. coli estimate (docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md).

What the tests passed, and so what the site reads: ECMWF IFS `soil_moisture_9_to_27cm` (m3/m3) from Open-Meteo,
named with models=ecmwf_ifs. It equals Open-Meteo's default for this variable on every hour checked (plan step 1,
docs/SOIL-MOISTURE-ECOLI-PLAN-2026-10.md). One value per cell per issue: the hour 00:00 UTC of the build's UTC day,
held for every day the forecast shows, as the leads test held it (its gain held from lead 0 to lead 4).

It is its own request, never added to the rain's: a second variable in the rain request would let Open-Meteo pick
one model for both, and the rain would change.

Fetching (`fetch`) is the build's prefetch alone; a spot only reads the cache (`value`). Per cell and UTC day:
- a cell fetched today is not asked for again;
- a failed attempt is remembered in ATTEMPTS_FILE, with its time and reason, and the cell is tried at most once more
  that day (MAX_ATTEMPTS), no sooner than RETRY_GAP_H after the failure. Builds run every 30 minutes at most and a
  median 2.9 hours apart, so the retry falls in a later build, after a short outage has had time to clear. The worst
  case is two calls a cell a day, each booked in the day's ledger under "soil" and not made if the ration has no room
  (rainfall.may_spend). One variable over PAST_DAYS + FORECAST_DAYS days weighs 1 a location (rainfall.call_weight);
- `force=True` skips both rules, for a diagnostic run, and books under "soil_forced".

A failure has a named reason: network (no answer after the retries), bad_body (a 200 that is not JSON), schema (no
`hourly`, no soil-moisture series, series of different lengths, or the wrong number of results) or cache_write. The
response is checked before anything is written. A value outside 0 to 1 m3/m3 is not soil moisture and is read as
missing. Nothing is ever filled in: a cell without a usable value gives None, and the spot uses today's model.

`value` gives the 00:00 UTC value from a fetch made at most MAX_AGE_H before it, or None and why: missing (never
fetched), bad: <reason> (today's attempts failed), held (the ration held today's request back), expired (the last
fetch is over MAX_AGE_H old) or no value at 00:00 UTC.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest import rainfall
from dipcast.ingest.rainfall import cell_key

log = logging.getLogger(__name__)

SOIL_VAR = "soil_moisture_9_to_27cm"
SOIL_MODEL = "ecmwf_ifs"
CACHE = config.CACHE / "soil"
ATTEMPTS_FILE = "soil_attempts.json"
PAST_DAYS = 1
FORECAST_DAYS = 2      # today and tomorrow, so yesterday's fetch also holds today's 00:00 UTC
BATCH = 50
# A fetch up to this old may give today's 00:00 UTC value: yesterday's fetch, when today's failed, holds it as a
# forecast under a day ahead. The leads test held a value for four days with its gain intact.
MAX_AGE_H = 36
MAX_ATTEMPTS = 2       # per cell per UTC day: the first and one retry
RETRY_GAP_H = 1.0      # at least a build later (builds run every 30 minutes at most)
_errors: list[str] = []


def issue_hour(now: pd.Timestamp | None = None) -> pd.Timestamp:
    """00:00 UTC of `now`'s UTC day."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
    return now.floor("D")


def _cell(c) -> tuple[float, float]:
    return (round(float(c[0]), 3) + 0.0, round(float(c[1]), 3) + 0.0)


def _path(c: tuple[float, float]):
    return CACHE / f"soil_{cell_key(*c)}.parquet"


def _fetched_at(c: tuple[float, float]) -> pd.Timestamp | None:
    p = _path(c)
    if not p.exists():
        return None
    try:
        return pd.Timestamp(pd.read_parquet(p, columns=["fetched_at"])["fetched_at"].iloc[0])
    except (OSError, ValueError, KeyError, IndexError):   # a torn or foreign file counts as none
        return None


# ------------------------------------------------------------------ the day's attempts
def attempts(now: pd.Timestamp | None = None) -> dict:
    """The day's record: {"day", "cells": {key: {"tries", "last_at", "last_reason", "ok"}}, "held": {key: time}}.
    A missing or unreadable file, or one from an earlier UTC day, is a fresh day."""
    day = issue_hour(now).date().isoformat()
    try:
        d = json.loads((CACHE / ATTEMPTS_FILE).read_text())
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict) or d.get("day") != day:
        d = {"day": day, "cells": {}, "held": {}}
    d.setdefault("cells", {})
    d.setdefault("held", {})
    return d


def _save_attempts(d: dict) -> None:
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = CACHE / (ATTEMPTS_FILE + ".tmp")
        tmp.write_text(json.dumps(d))
        tmp.replace(CACHE / ATTEMPTS_FILE)
    except OSError as e:   # a record that cannot be written must not stop a build; it costs at most a retry
        log.warning("soil moisture: attempts not written: %s", e)


def _due(key: str, rec: dict, now: pd.Timestamp, fetched: pd.Timestamp | None, day: pd.Timestamp) -> bool:
    if fetched is not None and fetched >= day:
        return False
    a = rec["cells"].get(key)
    if not a:
        return True
    if a.get("ok") or a["tries"] >= MAX_ATTEMPTS:
        return False
    return (now - pd.Timestamp(a["last_at"])).total_seconds() >= RETRY_GAP_H * 3600


# ------------------------------------------------------------------ the response
def _frame(r, c: tuple[float, float], now: pd.Timestamp) -> tuple[pd.DataFrame | None, str | None]:
    """The cell's hourly series from one result, or None and why. Checked before anything is written."""
    if not isinstance(r, dict) or not isinstance(r.get("hourly"), dict):
        return None, "schema: no hourly block"
    h = r["hourly"]
    t, v = h.get("time"), h.get(SOIL_VAR)
    if not isinstance(t, list) or not isinstance(v, list):
        return None, f"schema: no {SOIL_VAR} series"
    if len(t) != len(v) or not t:
        return None, f"schema: {len(t)} times and {len(v)} values"
    times = pd.to_datetime(pd.Series(t), utc=True, errors="coerce")
    vals = np.array(pd.to_numeric(pd.Series(v, dtype=object), errors="coerce"), dtype=float)
    if times.isna().any():
        return None, "schema: unreadable times"
    vals[(vals < 0) | (vals > 1)] = np.nan   # not soil moisture: read as missing, never clipped
    return pd.DataFrame({"cell_lat": c[0], "cell_lon": c[1], "time": times, "sm": vals, "fetched_at": now}), None


# ------------------------------------------------------------------ fetch: the build's prefetch alone
def fetch(cells: list[tuple[float, float]], now: pd.Timestamp | None = None, what: str = "soil",
          force: bool = False) -> dict:
    """Ask Open-Meteo for each due cell (module docstring), in requests of BATCH cells. Never raises for a failed
    request, a bad answer or a cache that cannot be written: the cell's reason is recorded and the spot falls back.
    Returns counts for the build log."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
    day = issue_hour(now)
    rec = attempts(now)
    cells = list(dict.fromkeys(_cell(c) for c in cells))
    todo = [c for c in cells if force or _due(cell_key(*c), rec, now, _fetched_at(c), day)]
    out = {"cells": len(cells), "due": len(todo), "fetched": 0, "calls": 0.0, "held": 0, "failed": {}}
    if not todo:
        return out
    what = "soil_forced" if force else what
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        weight = rainfall.call_weight(len(chunk), PAST_DAYS + FORECAST_DAYS)
        if not rainfall.may_spend(weight, what):
            out["held"] += len(chunk)
            for c in chunk:
                rec["held"][cell_key(*c)] = now.isoformat()
            continue
        params = {"latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
                  "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
                  "hourly": SOIL_VAR, "models": SOIL_MODEL, "past_days": PAST_DAYS,
                  "forecast_days": FORECAST_DAYS, "timezone": "UTC"}
        reasons: dict[tuple, str | None] = {}
        try:
            res = rainfall._request(config.OPEN_METEO_FORECAST, params, timeout=30, attempts=1)
        except rainfall.OpenMeteoBadBody as e:
            rainfall.spend(weight, what)   # answered, so counted
            reasons = {c: "bad_body" for c in chunk}
            _errors.append(rainfall.redact(str(e)))
        except rainfall.OpenMeteoError as e:
            reasons = {c: "network" for c in chunk}
            _errors.append(rainfall.redact(str(e)))
        else:
            rainfall.spend(weight, what)
            out["calls"] += weight
            results = res if isinstance(res, list) else [res]
            if len(results) != len(chunk):
                reasons = {c: f"schema: {len(results)} results for {len(chunk)} cells" for c in chunk}
            else:
                for c, r in zip(chunk, results, strict=True):
                    df, why = _frame(r, c, now)
                    if why is None:
                        try:
                            CACHE.mkdir(parents=True, exist_ok=True)
                            df.to_parquet(_path(c), index=False)
                        except OSError as e:
                            why = "cache_write"
                            _errors.append(f"{cell_key(*c)}: {e}")
                    reasons[c] = why
        for c in chunk:
            key, why = cell_key(*c), reasons.get(c)
            a = rec["cells"].get(key, {"tries": 0})
            rec["cells"][key] = {"tries": a["tries"] + 1, "last_at": now.isoformat(), "last_reason": why, "ok": why is None}
            if why is None:
                out["fetched"] += 1
            else:
                kind = why.split(":")[0]
                out["failed"][kind] = out["failed"].get(kind, 0) + 1
        if any(reasons.get(c) for c in chunk):
            log.warning("soil moisture: %d of %d cells failed (%s)", sum(1 for c in chunk if reasons.get(c)), len(chunk),
                        "; ".join(sorted({w for w in reasons.values() if w})))
    _save_attempts(rec)
    return out


# ------------------------------------------------------------------ value: what a spot reads
def value(cell: tuple[float, float], now: pd.Timestamp | None = None) -> tuple[float | None, dict]:
    """The cell's soil moisture at 00:00 UTC of `now`'s UTC day, and how it was got, from the cache alone. None, with
    `reason` (module docstring), when there is no usable value."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
    at, c = issue_hour(now), _cell(cell)
    key, rec = cell_key(*c), attempts(now)
    a = rec["cells"].get(key) or {}
    failed = {"reason": f"bad: {a['last_reason']}", "tries": a["tries"]} if a.get("last_reason") else None
    p = _path(c)
    try:
        d = pd.read_parquet(p) if p.exists() else None
    except (OSError, ValueError):
        d = None
    if d is None or d.empty:
        if failed:
            return None, failed
        return None, {"reason": "held"} if key in rec["held"] else {"reason": "missing"}
    fetched = pd.Timestamp(d["fetched_at"].iloc[0])
    age_h = (now - fetched).total_seconds() / 3600
    if age_h > MAX_AGE_H:
        return None, failed or ({"reason": "held"} if key in rec["held"] else
                                {"reason": "expired", "fetched_at": fetched.isoformat()})
    v = d.loc[pd.to_datetime(d["time"], utc=True) == at, "sm"]
    if v.empty or not np.isfinite(v.iloc[0]):
        return None, {"reason": "no value at 00:00 UTC", "fetched_at": fetched.isoformat()}
    return float(v.iloc[0]), {"at": at.isoformat(), "fetched_at": fetched.isoformat()}


def errors() -> list[str]:
    return list(_errors)


def reset() -> None:
    _errors.clear()


def cell_of(lat: float, lon: float) -> tuple[float, float]:
    a, b = rainfall.grid_cell(lat, lon)
    return _cell((a, b))
