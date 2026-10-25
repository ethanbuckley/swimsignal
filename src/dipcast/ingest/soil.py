"""Root-zone soil moisture for the river E. coli estimate (docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md).

What the tests passed, and so what the site reads: ECMWF IFS `soil_moisture_9_to_27cm` (m3/m3) from Open-Meteo,
named with models=ecmwf_ifs. It equals Open-Meteo's default for this variable on every hour checked (plan step 1,
docs/SOIL-MOISTURE-ECOLI-PLAN-2026-10.md). One value per cell per issue: the hour 00:00 UTC of the build's UTC day,
held for every day the forecast shows, as the leads test held it (its gain held from lead 0 to lead 4).

It is its own request, never added to the rain's: a second variable in the rain request would let Open-Meteo pick
one model for both, and the rain would change. A cell is asked for once per UTC day (`fetch`): one variable over
PAST_DAYS + FORECAST_DAYS days weighs 1 a location (rainfall.call_weight), so the cost is one call per river spot cell
per day, however many builds run. Each request is booked in the day's ledger under "soil" and is not made if the
ration has no room (rainfall.may_spend).

`value` gives the 00:00 UTC value from a fetch made at most MAX_AGE_H before it. None otherwise (no fetch, a failed one,
a cell Open-Meteo has no value for): the spot then uses today's model, never a guessed wetness (forecast.py).
"""

from __future__ import annotations

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
PAST_DAYS = 1
FORECAST_DAYS = 2      # today and tomorrow, so yesterday's fetch also holds today's 00:00 UTC
BATCH = 50
# A fetch up to this old may give today's 00:00 UTC value: yesterday's fetch, when today's failed, holds it as a
# forecast under a day ahead. The leads test held a value for four days with its gain intact.
MAX_AGE_H = 36
_errors: list[str] = []


def issue_hour(now: pd.Timestamp | None = None) -> pd.Timestamp:
    """00:00 UTC of `now`'s UTC day."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
    return now.floor("D")


def _path(c: tuple[float, float]):
    return CACHE / f"soil_{cell_key(*c)}.parquet"


def _fetched_at(c: tuple[float, float]) -> pd.Timestamp | None:
    p = _path(c)
    if not p.exists():
        return None
    try:
        return pd.Timestamp(pd.read_parquet(p, columns=["fetched_at"])["fetched_at"].iloc[0])
    except Exception:  # noqa: BLE001 - a torn file counts as none
        return None


def fetch(cells: list[tuple[float, float]], now: pd.Timestamp | None = None, what: str = "soil") -> dict:
    """Ask Open-Meteo for each cell not yet fetched on `now`'s UTC day, in requests of BATCH cells. A request that
    fails is logged and its cells keep whatever the cache holds. Returns counts for the build log."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
    day = issue_hour(now)
    cells = list(dict.fromkeys((round(float(a), 3) + 0.0, round(float(b), 3) + 0.0) for a, b in cells))
    todo = [c for c in cells if (_fetched_at(c) is None or _fetched_at(c) < day)]
    out = {"cells": len(cells), "due": len(todo), "fetched": 0, "calls": 0.0, "held": 0, "failed": 0}
    if not todo:
        return out
    CACHE.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        weight = rainfall.call_weight(len(chunk), PAST_DAYS + FORECAST_DAYS)
        if not rainfall.may_spend(weight, what):
            out["held"] += len(chunk)
            continue
        params = {"latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
                  "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
                  "hourly": SOIL_VAR, "models": SOIL_MODEL, "past_days": PAST_DAYS,
                  "forecast_days": FORECAST_DAYS, "timezone": "UTC"}
        try:
            res = rainfall._request(config.OPEN_METEO_FORECAST, params, timeout=30, attempts=3)
        except Exception as e:  # noqa: BLE001 - soil moisture is optional; the spot falls back to today's model
            if isinstance(e, rainfall.OpenMeteoBadBody):
                rainfall.spend(weight, what)
            _errors.append(rainfall.redact(str(e) or type(e).__name__))
            out["failed"] += len(chunk)
            log.warning("soil moisture: request for %d cells failed: %s", len(chunk), _errors[-1])
            continue
        rainfall.spend(weight, what)
        out["calls"] += weight
        for c, r in zip(chunk, res if isinstance(res, list) else [res], strict=True):
            h = r["hourly"]
            pd.DataFrame({"cell_lat": c[0], "cell_lon": c[1], "time": pd.to_datetime(h["time"], utc=True),
                          "sm": np.asarray(h[SOIL_VAR], dtype=float), "fetched_at": now}).to_parquet(_path(c), index=False)
            out["fetched"] += 1
    return out


def value(cell: tuple[float, float], now: pd.Timestamp | None = None) -> tuple[float | None, dict]:
    """The cell's soil moisture at 00:00 UTC of `now`'s UTC day, and how it was got. None, with `reason`, when the
    cache has no fetch at most MAX_AGE_H old or that fetch has no value at that hour."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
    at = issue_hour(now)
    c = (round(float(cell[0]), 3) + 0.0, round(float(cell[1]), 3) + 0.0)
    p = _path(c)
    if not p.exists():
        return None, {"reason": "not fetched"}
    try:
        d = pd.read_parquet(p)
    except Exception:  # noqa: BLE001
        return None, {"reason": "cache unreadable"}
    fetched = pd.Timestamp(d["fetched_at"].iloc[0])
    age_h = (now - fetched).total_seconds() / 3600
    if age_h > MAX_AGE_H:
        return None, {"reason": f"last fetch {age_h:.0f} h old", "fetched_at": fetched.isoformat()}
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
    return (round(float(a), 3) + 0.0, round(float(b), 3) + 0.0)

