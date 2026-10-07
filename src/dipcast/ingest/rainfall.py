"""Hourly rainfall from Open-Meteo, on a coarse grid shared by nearby overflows.

Two sources with one interface:
  * archive  - ERA5-Land reanalysis, ~0.1 deg, from 1940 to ~5 days ago.
  * forecast - current model run, hourly, up to 16 days ahead plus recent past.

Both are cached under data/cache/rain. Archive is cached per cell-year (it never
changes); forecast per cell with a short TTL.

Transient failures (a 429, a 5xx, a connect, TLS or read timeout) are retried a few
times with a jittered, growing wait (`_request`). If the forecast still does not come,
fetch_forecast uses the cell's cached forecast up to STALE_MAX_AGE_S old and leaves a
cell with nothing that fresh out, so its overflows have no rain data: the build goes on
and the page says "no data" for them. `fallback_summary` reports what was served stale.
"""

from __future__ import annotations

import email.utils
import logging
import random
import time

import httpx
import numpy as np
import pandas as pd

from dipcast import config

log = logging.getLogger(__name__)

CACHE = config.CACHE / "rain"
FORECAST_TTL_S = 3600
BATCH = 10           # archive: coordinates per request (long series, keep small)
FORECAST_BATCH = 50  # forecast: short series, so many cells per request; fewer handshakes

# Retries (_request). The wait before retry k (0-based) is drawn from [d/2, d], d = min(WAIT_CAP_S,
# WAIT_BASE_S * 2**k): 1-2, 2-4, 4-8, 8-16 s for five attempts, so at most 30 s of waiting. A
# Retry-After header makes the wait at least that long; one over MAX_RETRY_AFTER_S is a quota, not a
# blip, and ends the retries. No request sleeps more than MAX_WAIT_S in all.
WAIT_BASE_S = 2.0
WAIT_CAP_S = 30.0
MAX_RETRY_AFTER_S = 60.0
MAX_WAIT_S = 60.0
CONNECT_TIMEOUT_S = 8.0
# A cached forecast up to this old stands in for one Open-Meteo did not send. The same rule as
# the click-anywhere data's (scripts/build_any_point.py, RAIN_MAX_AGE_H): a day-old run still
# covers today and the next days but its last.
STALE_MAX_AGE_S = 24 * 3600
# After this many forecast requests in a row fail every attempt, Open-Meteo is taken to be down:
# fetch_forecast makes no request for OUTAGE_COOLOFF_S and serves the cache, so an outage costs a
# build two requests' retries rather than every chunk's.
OUTAGE_AFTER = 2
OUTAGE_COOLOFF_S = 600

_sleep = time.sleep      # replaced in tests
_random = random.random  # replaced in tests


class OpenMeteoError(RuntimeError):
    """A request that failed after its retries, or one not worth retrying (a 4xx other than 429)."""


def _http_get(url: str, params: dict, timeout: float) -> httpx.Response:
    """The one place a request leaves; tests replace it with an httpx.MockTransport client."""
    return httpx.get(url, params=params, timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT_S))


def grid_cell(lat: float | np.ndarray, lon: float | np.ndarray) -> tuple:
    """Snap to the centre of a RAIN_GRID_DEG cell. Returns (cell_lat, cell_lon). Adding 0.0 turns
    -0.0 (a point just west of the Greenwich meridian) into 0.0, so each cell has one value."""
    d = config.RAIN_GRID_DEG
    return (np.round(np.round(np.asarray(lat) / d) * d, 3) + 0.0, np.round(np.round(np.asarray(lon) / d) * d, 3) + 0.0)


def cell_key(cell_lat: float, cell_lon: float) -> str:
    """The cache name of a cell. -0.0 and 0.0 are the same cell and get the same name: "-0.000"
    and "0.000" were two names for one file, so a cell the prefetch had saved under one was
    fetched again under the other. That second request failed River Great Ouse, Overcote
    (lon -0.004) in most scheduled builds from 3 to 6 Oct 2026."""
    return f"{cell_lat + 0.0:.3f}_{cell_lon + 0.0:.3f}"


def retry_after_s(response: httpx.Response) -> float | None:
    """The Retry-After header in seconds (delta-seconds or an HTTP date), None when absent or unreadable."""
    v = (response.headers.get("retry-after") or "").strip()
    if not v:
        return None
    try:
        return max(0.0, float(v))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(v)
    except (TypeError, ValueError):
        return None
    if when is None or when.tzinfo is None:
        return None
    return max(0.0, when.timestamp() - time.time())


def _backoff_s(attempt: int) -> float:
    d = min(WAIT_CAP_S, WAIT_BASE_S * 2**attempt)
    return d / 2 + _random() * d / 2


def _request(url: str, params: dict, timeout: float = 120, attempts: int = 5) -> list[dict] | dict:
    """GET `url` and return its JSON, retrying a 429, a 5xx and a connect, TLS-handshake, read or
    network failure up to `attempts` times in all (waits: WAIT_BASE_S and the comments by it). Raises
    OpenMeteoError when they run out, at once for any other 4xx. A Retry-After over
    MAX_RETRY_AFTER_S ends the retries. Each request is one API call to Open-Meteo, so retries
    are the only calls added, and only after a failure."""
    waited, why = 0.0, "no attempt made"
    for attempt in range(attempts):
        hint = None
        try:
            r = _http_get(url, params, timeout)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            # TLS handshake and connect timeouts are common from shared CI runners and clear on retry.
            why = str(e) or type(e).__name__
        else:
            if r.is_success:
                try:
                    return r.json()
                except ValueError as e:
                    raise OpenMeteoError(f"open-meteo sent a body that is not JSON: {e}") from e
            why = f"HTTP {r.status_code}"
            if r.status_code != 429 and r.status_code < 500:
                log.warning("open-meteo %s; not retried", why)
                raise OpenMeteoError(f"open-meteo request failed: {why}")
            hint = retry_after_s(r)
        if attempt + 1 == attempts:   # no wait before giving up
            log.warning("open-meteo %s; giving up after %d attempts", why, attempts)
            break
        if hint is not None and hint > MAX_RETRY_AFTER_S:
            log.warning("open-meteo %s with Retry-After %.0fs; giving up", why, hint)
            break
        wait = max(hint or 0.0, _backoff_s(attempt))
        if waited + wait > MAX_WAIT_S:
            log.warning("open-meteo %s; giving up after %d attempts (%.0fs waited)", why, attempt + 1, waited)
            break
        log.warning("open-meteo %s; retry in %.1fs", why, wait)
        _sleep(wait)
        waited += wait
    raise OpenMeteoError(f"open-meteo request failed: {why}")


def _to_frame(res: dict, cell_lat: float, cell_lon: float) -> pd.DataFrame:
    h = res["hourly"]
    t = pd.to_datetime(h["time"], utc=True)
    p = np.asarray(h["precipitation"], dtype=float)
    return pd.DataFrame({"cell_lat": cell_lat, "cell_lon": cell_lon, "time": t, "precip_mm": p})


# ------------------------------------------------------------------ archive
def fetch_archive(cells: list[tuple[float, float]], year: int) -> pd.DataFrame:
    """Hourly precipitation for each cell for one calendar year (cached)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    frames, todo = [], []
    for cl, cn in cells:
        p = CACHE / f"archive_{cell_key(cl, cn)}_{year}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
        else:
            todo.append((cl, cn))
    end = min(pd.Timestamp(f"{year}-12-31"), pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=6))
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        params = {
            "latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
            "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
            "start_date": f"{year}-01-01",
            "end_date": end.strftime("%Y-%m-%d"),
            "hourly": "precipitation",
            "timezone": "UTC",
        }
        try:
            res = _request(config.OPEN_METEO_ARCHIVE, params)
        except RuntimeError as e:
            log.error("archive %d: skipping %d cells after repeated failures (%s)", year, len(chunk), e)
            continue
        results = res if isinstance(res, list) else [res]
        for (cl, cn), r in zip(chunk, results, strict=True):
            df = _to_frame(r, cl, cn)
            df.to_parquet(CACHE / f"archive_{cell_key(cl, cn)}_{year}.parquet", index=False)
            frames.append(df)
        log.info("archive %d: %d/%d cells", year, min(i + BATCH, len(todo)), len(todo))
        time.sleep(0.5)  # stay well inside the free-tier rate limit
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["cell_lat", "cell_lon", "time", "precip_mm"])


# ------------------------------------------------------------------ forecast
# What this process asked Open-Meteo for and did not get (fallback_summary). A cell whose request
# failed is not asked for again within FORECAST_TTL_S: after a failed prefetch, every spot's own
# fetch would otherwise retry it, one spot at a time.
_failed_at: dict[tuple[float, float], float] = {}
_stale: dict[tuple[float, float], float] = {}   # cell -> age (s) of the cached forecast served instead
_missing: set[tuple[float, float]] = set()       # cells with no cached forecast young enough
_errors: list[str] = []
_outage = {"run": 0, "until": 0.0}   # failed requests in a row; no requests before `until`


def reset_fallbacks() -> None:
    """Forget failed cells and any outage (tests; a long-running process may call it too)."""
    _failed_at.clear()
    _stale.clear()
    _missing.clear()
    _errors.clear()
    _outage.update(run=0, until=0.0)


def fallback_summary() -> dict | None:
    """The forecast cells this process did not get from Open-Meteo, None when there were none.
    `stale`: served from a cached forecast up to STALE_MAX_AGE_S old (the oldest `oldest_stale_h`
    hours); `missing`: none that fresh, so the overflows there have no rain data; `errors`: the
    first few distinct reasons."""
    if not (_stale or _missing):
        return None
    return {"cells": len(_stale) + len(_missing), "stale": len(_stale), "missing": len(_missing),
            "oldest_stale_h": round(max(_stale.values(), default=0.0) / 3600, 1),
            "errors": list(dict.fromkeys(_errors))[:3]}


def fetch_errors() -> list[str]:
    """Why each failed forecast request failed, in order, since the last reset_fallbacks."""
    return list(_errors)


def _empty_forecast() -> pd.DataFrame:
    return pd.DataFrame({"cell_lat": pd.Series(dtype=float), "cell_lon": pd.Series(dtype=float),
                         "time": pd.Series(dtype="datetime64[ns, UTC]"), "precip_mm": pd.Series(dtype=float),
                         "issued_at": pd.Series(dtype="datetime64[ns, UTC]")})


def _cached_instead(cells: list[tuple[float, float]], max_age_s: float) -> list[pd.DataFrame]:
    """Each cell's cached forecast if it is at most `max_age_s` old; a cell without one is missing."""
    frames, now = [], time.time()
    for c in cells:
        p = CACHE / f"forecast_{cell_key(*c)}.parquet"
        age = now - p.stat().st_mtime if p.exists() else float("inf")
        if age <= max_age_s:
            try:
                frames.append(pd.read_parquet(p))
                _stale[c] = age
                _missing.discard(c)
                continue
            except Exception as e:  # noqa: BLE001 - a torn cache file counts as none
                log.warning("rain cache %s unreadable: %s", p.name, e)
        _missing.add(c)
    return frames


def fetch_forecast(cells: list[tuple[float, float]],
                   past_days: int = config.FORECAST_PAST_DAYS,
                   forecast_days: int = config.FORECAST_DAYS, attempts: int = 5,
                   stale_max_age_s: float = STALE_MAX_AGE_S) -> pd.DataFrame:
    """Recent observed-ish and forecast hourly precipitation per cell (cached 1 h). `attempts` per
    request of up to FORECAST_BATCH cells (see _request). A request that still fails does not
    raise: its cells get their cached forecast if it is at most `stale_max_age_s` old and are
    left out otherwise, so they have no rain data (never zero rain). Requests are the same as
    before, one per FORECAST_BATCH cells not freshly cached; a cell that failed earlier in this
    process, or any cell during an outage (OUTAGE_AFTER), goes to the cache without one."""
    CACHE.mkdir(parents=True, exist_ok=True)
    frames, todo, held = [], [], []
    now = time.time()
    for cl, cn in cells:
        p = CACHE / f"forecast_{cell_key(cl, cn)}.parquet"
        if p.exists() and now - p.stat().st_mtime < FORECAST_TTL_S:
            frames.append(pd.read_parquet(p))
        elif now - _failed_at.get((cl, cn), -float("inf")) < FORECAST_TTL_S:
            held.append((cl, cn))
        else:
            todo.append((cl, cn))
    if held:
        frames += _cached_instead(held, stale_max_age_s)
    for i in range(0, len(todo), FORECAST_BATCH):
        chunk = todo[i:i + FORECAST_BATCH]
        if time.time() < _outage["until"]:
            why = "open-meteo taken as down after repeated failures"
        else:
            params = {
                "latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
                "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
                "hourly": "precipitation",
                "past_days": past_days,
                "forecast_days": forecast_days,
                "timezone": "UTC",
            }
            try:
                res = _request(config.OPEN_METEO_FORECAST, params, timeout=30, attempts=attempts)  # small payload; fail fast on a bad handshake
            except Exception as e:  # noqa: BLE001 - OpenMeteoError, or anything else a request raises
                why = str(e) or type(e).__name__
                _errors.append(why)
                _outage["run"] += 1
                if _outage["run"] >= OUTAGE_AFTER:
                    _outage.update(run=0, until=time.time() + OUTAGE_COOLOFF_S)
                    log.warning("open-meteo: %d forecast requests in a row failed; none for %.0f min",
                                OUTAGE_AFTER, OUTAGE_COOLOFF_S / 60)
            else:
                _outage["run"] = 0
                results = res if isinstance(res, list) else [res]
                for (cl, cn), r in zip(chunk, results, strict=True):
                    df = _to_frame(r, cl, cn)
                    df["issued_at"] = pd.Timestamp.now(tz="UTC")
                    df.to_parquet(CACHE / f"forecast_{cell_key(cl, cn)}.parquet", index=False)
                    frames.append(df)
                    _failed_at.pop((cl, cn), None)
                    _stale.pop((cl, cn), None)
                    _missing.discard((cl, cn))
                continue
        t = time.time()
        _failed_at.update({c: t for c in chunk})
        got = _cached_instead(chunk, stale_max_age_s)
        frames += got
        log.warning("rain forecast: %d cells not fetched (%s): %d from a cached forecast at most %.0f h old, "
                    "%d with no rain data", len(chunk), why, len(got), stale_max_age_s / 3600, len(chunk) - len(got))
    return pd.concat(frames, ignore_index=True) if frames else _empty_forecast()


def cells_for_sites(lat: pd.Series, lon: pd.Series) -> list[tuple[float, float]]:
    cl, cn = grid_cell(lat.to_numpy(), lon.to_numpy())
    return sorted({(float(a), float(b)) for a, b in zip(cl, cn, strict=True)})
