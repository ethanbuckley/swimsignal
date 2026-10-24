"""Hourly rainfall from Open-Meteo, on a coarse grid shared by nearby overflows.

Two sources with one interface:
  * archive  - ERA5-Land reanalysis, ~0.1 deg, from 1940 to ~5 days ago.
  * forecast - current model run, hourly, up to 16 days ahead plus recent past.
And, for the listed spots' cells, fetch_forecast(ensemble=True): the members of the Met Office's
MOGREPS-UK ensemble (config.ENSEMBLE_MODEL), for the band on days 3 to 5 and the test in
docs/ENSEMBLE-RAIN-TEST-2026-11.md ("Ensemble" below).

Both are cached under data/cache/rain. Archive is cached per cell-year (it never
changes); forecast per cell with a short TTL.

Transient failures (a 429, a 5xx, a connect, TLS or read timeout) are retried a few
times with a jittered, growing wait (`_request`). If the forecast still does not come,
fetch_forecast uses the cell's cached forecast up to STALE_MAX_AGE_S old and leaves a
cell with nothing that fresh out, so its overflows have no rain data: the build goes on
and the page says "no data" for them. `fallback_summary` reports what was served stale, for the
build's warnings, and `forecast_age` how old the rain behind one spot is, for its page.

Open-Meteo's free API allows 10,000 calls a day. It weighs a request by its own rule
(call_weight): one variable over up to 140 days is one call per location, so a forecast cell
costs 1 however many past days it asks for. Each build's users of the forecast API ask for a cell
only once its cached copy is older than a floor (FORECAST_TTL_S here for the spots; the
click-anywhere rain, the weather and the Scottish shadow have their own), so the cost per day is
set by the floors, not by how many builds run. The ledger (calls_today, spend) adds up what was
asked for since 00:00 UTC, when Open-Meteo starts its count again, and a request that would take
the day over DAILY_CALLS is not made: its cells get their cached forecast, as after a failure.
Every request this process sends, retries included, is counted by host (requests_made), for the
build log. A paid plan's key (KEY_ENV) moves every request to Open-Meteo's customer hosts (customer).
"""

from __future__ import annotations

import email.utils
import json
import logging
import os
import random
import time

import httpx
import numpy as np
import pandas as pd

from dipcast import config

log = logging.getLogger(__name__)

CACHE = config.CACHE / "rain"
# The spots' refresh floor. At 1 hour, builds every 30 minutes would ask for the 332 cells 24
# times a day (7,968 calls) before the map's rain and the weather. At 2 hours it is 12 times
# (3,984), and the rain a spot shows is at most 2 hours old plus the build's own minutes.
FORECAST_TTL_S = 2 * 3600
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
# covers today and the next four days, but not the last of them for a build from 23:00 UTC in summer time.
STALE_MAX_AGE_S = 24 * 3600
# After this many forecast requests in a row fail every attempt, Open-Meteo is taken to be down:
# fetch_forecast makes no request for OUTAGE_COOLOFF_S and serves the cache, so an outage costs a
# build two requests' retries rather than every chunk's.
OUTAGE_AFTER = 2
OUTAGE_COOLOFF_S = 600
# The day's ration. Open-Meteo's free limit is 10,000 calls a day; the floors keep the build near
# 8,700 at a build every 30 minutes, and the rest is room for answers the ledger cannot see (a
# request that timed out after Open-Meteo had counted it).
DAILY_CALLS = float(os.environ.get("DIPCAST_OPEN_METEO_DAILY_CALLS", "9000"))
LEDGER_NAME = "open_meteo_calls.json"
# A paid plan (OP1, docs/ORGANISER-PIVOT-2026-10.md): the free API is for non-commercial use only.
# With KEY_ENV set, every request goes to the same path on the host with "customer-" in front
# (api. -> customer-api., archive-api. -> customer-archive-api., and so on) and carries &apikey=.
# Open-Meteo's docs, the apikey row of each API's parameters: "The server URL requires the prefix
# customer-"; its pricing page: "requests include &apikey=abc123". Unset, nothing changes. The key
# goes into the request and nowhere else: not a log line, an error, a cache name or the build
# summary (redact, _KeyFilter; tests/test_open_meteo_key.py).
KEY_ENV = "DIPCAST_OPEN_METEO_KEY"

_sleep = time.sleep      # replaced in tests
_random = random.random  # replaced in tests
_requests: dict[str, int] = {}   # requests sent by this process, retries included, by host (requests_made)


class OpenMeteoError(RuntimeError):
    """A request that failed after its retries, or one not worth retrying (a 4xx other than 429)."""


class OpenMeteoBadBody(OpenMeteoError):
    """Open-Meteo answered 2xx with a body that is not JSON (cut short): it counted the call."""


# ------------------------------------------------------------------ the day's calls
def call_weight(n_locations: int, days: float, variables: int = 1) -> float:
    """Open-Meteo's count for one request, by its own rule (open-meteo/open-meteo,
    ForecastApiResult.calculateQueryWeight, 16 Oct 2026): per location max(1, v/10, v/10 x days/14),
    summed over the locations, with v the variables (times the models; one for the default). So one
    variable over up to 140 days is 1 a location: asking for fewer past days saves no calls."""
    v = variables / 10
    return n_locations * max(1.0, v, v * days / 14)


def forecast_weight(n_cells: int, past_days: int = config.FORECAST_PAST_DAYS,
                    forecast_days: int = config.FORECAST_DAYS) -> float:
    """What fetch_forecast's request for n_cells costs: one variable over past + forecast + 1 days."""
    return call_weight(n_cells, past_days + forecast_days + 1)


def _utc_day(now: float | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() if now is None else now))


def calls_today(now: float | None = None) -> dict:
    """The ledger for the current UTC day: {"day", "calls", "by": {what: calls}, "held": {what: calls
    not asked for because the ration was spent}, "limit"}. A missing or unreadable file, or one from
    an earlier day, is a fresh day."""
    day = _utc_day(now)
    try:
        d = json.loads((CACHE / LEDGER_NAME).read_text())
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict) or d.get("day") != day:
        d = {"day": day, "calls": 0.0, "by": {}, "held": {}}
    d.setdefault("by", {})
    d.setdefault("held", {})
    d["limit"] = DAILY_CALLS
    return d


def calls_left(now: float | None = None) -> float:
    return DAILY_CALLS - float(calls_today(now)["calls"])


def _book(weight: float, what: str, key: str, now: float | None = None) -> None:
    d = calls_today(now)
    d[key][what] = round(float(d[key].get(what, 0.0)) + weight, 2)
    if key == "by":
        d["calls"] = round(float(d["calls"]) + weight, 2)
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = CACHE / (LEDGER_NAME + ".tmp")
        tmp.write_text(json.dumps(d))
        tmp.replace(CACHE / LEDGER_NAME)
    except OSError as e:   # a ledger that cannot be written must not stop a build
        log.warning("open-meteo ledger not written: %s", e)


def spend(weight: float, what: str, now: float | None = None) -> None:
    """Add a request Open-Meteo answered to the day's ledger, under `what` (spots, weather, ...)."""
    _book(weight, what, "by", now)


def may_spend(weight: float, what: str, now: float | None = None) -> bool:
    """Whether a request of `weight` fits what is left of the day's ration. One that does not is
    booked under "held", so the build's summary says what the ration kept back."""
    if calls_left(now) >= weight:
        return True
    _book(weight, what, "held", now)
    log.warning("open-meteo: %s request of %.0f calls not made; the day's ration (%.0f) is spent",
                what, weight, DAILY_CALLS)
    return False


def api_key() -> str:
    """The paid plan's key from KEY_ENV, "" when unset. Read at each request, not at import."""
    return os.environ.get(KEY_ENV, "").strip()


def customer(url: str, params: dict) -> tuple[str, dict]:
    """`url` and `params` as a paid plan sends them: the open-meteo.com host with "customer-" in
    front and the key as apikey. Without a key, or for a host that is not Open-Meteo's, unchanged."""
    key = api_key()
    u = httpx.URL(url)
    if not key or not u.host.endswith(".open-meteo.com") or u.host.startswith("customer-"):
        return url, params
    return str(u.copy_with(host="customer-" + u.host)), {**params, "apikey": key}


def redact(text: str) -> str:
    """`text` with the key, if any, replaced by "[key]"."""
    key = api_key()
    return text.replace(key, "[key]") if key else text


class _KeyFilter(logging.Filter):
    """Takes the key out of a log record. On the httpx logger, whose INFO line for each request
    prints the full URL, query and all (build_site sets that logger to WARNING; other scripts may not)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if api_key():
            msg = record.getMessage()
            clean = redact(msg)
            if clean != msg:
                record.msg, record.args = clean, None
        return True


logging.getLogger("httpx").addFilter(_KeyFilter())
log.addFilter(_KeyFilter())


def _http_get(url: str, params: dict, timeout: float) -> httpx.Response:
    """The one place a request leaves; tests replace it with an httpx.MockTransport client."""
    return httpx.get(url, params=params, timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT_S))


def grid_cell(lat: float | np.ndarray, lon: float | np.ndarray) -> tuple:
    """Snap to the centre of a RAIN_GRID_DEG cell. Returns (cell_lat, cell_lon). Adding 0.0 turns
    -0.0 (a point just west of the Greenwich meridian) into 0.0, so each cell has one value."""
    d = config.RAIN_GRID_DEG
    return (np.round(np.round(np.asarray(lat) / d) * d, 3) + 0.0, np.round(np.round(np.asarray(lon) / d) * d, 3) + 0.0)


def cell_key(cell_lat: float, cell_lon: float) -> str:
    """The cache name of a cell. -0.0 and 0.0 are the same cell and get the same name: with two
    names for one file, a cell the prefetch saved under one is fetched again under the other, and
    that second request failed River Great Ouse, Overcote (lon -0.004) in most builds of 3 to 6
    Oct 2026."""
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


def _request(url: str, params: dict, timeout: float = 120, attempts: int = 5,
             retry_429: bool = True) -> list[dict] | dict:
    """GET `url` and return its JSON, retrying a 429, a 5xx and a connect, TLS-handshake, read or
    network failure up to `attempts` times in all (waits: WAIT_BASE_S and the comments by it). Raises
    OpenMeteoError when they run out, at once for any other 4xx. A Retry-After over
    MAX_RETRY_AFTER_S ends the retries. Each request is one API call to Open-Meteo, so retries
    are the only calls added, and only after a failure. `retry_429=False` raises at the first 429:
    the off-CI archive fetchers stop at a refusal rather than ask again. With a key (KEY_ENV) the
    request goes to the customer host (customer); counted under that host, so the build log shows it."""
    waited, why = 0.0, "no attempt made"
    url, params = customer(url, params)
    host = httpx.URL(url).host
    for attempt in range(attempts):
        hint = None
        _requests[host] = _requests.get(host, 0) + 1
        try:
            r = _http_get(url, params, timeout)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            # TLS handshake and connect timeouts are common from shared CI runners and clear on retry.
            why = redact(str(e) or type(e).__name__)
        except Exception as e:
            if not api_key():
                raise
            # An httpx error keeps the request, key and all, and may print its URL: replaced by one
            # that has neither, and `from None` keeps the original out of a traceback.
            raise OpenMeteoError(f"open-meteo request failed: {redact(str(e) or type(e).__name__)}") from None
        else:
            if r.is_success:
                try:
                    return r.json()
                except ValueError as e:
                    raise OpenMeteoBadBody(f"open-meteo sent a body that is not JSON: {e}") from e
            why = f"HTTP {r.status_code}"
            if r.status_code == 429 and not retry_429:
                log.warning("open-meteo %s; not retried (retry_429=False)", why)
                raise OpenMeteoError(f"open-meteo request refused: {why}")
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


def requests_made() -> dict:
    """The Open-Meteo requests this process has sent, retries included: {"total", "by_host": {host: n}}.
    The build log shows it, so a build that asks for more than 40 stands out."""
    return {"total": sum(_requests.values()), "by_host": dict(sorted(_requests.items()))}


def reset_requests() -> None:
    _requests.clear()


def _to_frame(res: dict, cell_lat: float, cell_lon: float) -> pd.DataFrame:
    h = res["hourly"]
    t = pd.to_datetime(h["time"], utc=True)
    p = np.asarray(h["precipitation"], dtype=float)
    return pd.DataFrame({"cell_lat": cell_lat, "cell_lon": cell_lon, "time": t, "precip_mm": p})


# ------------------------------------------------------------------ archive
def fetch_archive(cells: list[tuple[float, float]], year: int, strict: bool = False) -> pd.DataFrame:
    """Hourly precipitation for each cell for one calendar year (cached). A request that fails
    after its retries is skipped, unless `strict`: then a 429 is not retried and any failure
    raises OpenMeteoError, so a paced off-CI fetch can stop at the first refusal."""
    CACHE.mkdir(parents=True, exist_ok=True)
    frames, todo = [], []
    for cl, cn in cells:
        p = CACHE / f"archive_{cell_key(cl, cn)}_{year}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
        else:
            todo.append((cl, cn))
    end = min(pd.Timestamp(f"{year}-12-31"), pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=6))
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
            res = _request(config.OPEN_METEO_ARCHIVE, params, retry_429=not strict)
        except RuntimeError as e:
            if strict:
                raise
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
# cell -> why it was served from the cache past FORECAST_TTL_S: "no answer" (the request failed, or
# Open-Meteo was taken as down) or "daily limit" (the ration had no room, so no request was made). The
# spot's page words the two differently (forecast_age): only the first is Open-Meteo's doing.
_why: dict[tuple[float, float], str] = {}
_missing: set[tuple[float, float]] = set()       # cells with no cached forecast young enough
_errors: list[str] = []
_outage = {"run": 0, "until": 0.0}   # failed requests in a row; no requests before `until`


def reset_fallbacks() -> None:
    """Forget failed cells and any outage (tests; a long-running process may call it too)."""
    _failed_at.clear()
    _stale.clear()
    _why.clear()
    _missing.clear()
    _errors.clear()
    _outage.update(run=0, until=0.0)
    _ens_asked.clear()
    _ens.clear()


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


def forecast_age(frames: list[pd.DataFrame], now: pd.Timestamp) -> dict:
    """How old the rain forecast in `frames` (fetch_forecast's) is, from the oldest cell in them:
    `rain_issued_at`, when it was fetched; `rain_age_h`, hours from then to `now`; `rain_fallback`, why
    that cell was not fetched afresh (_why), where it was served from the cache past FORECAST_TTL_S;
    and `rain_mixed`, true where other cells were fetched more than an hour later, so only part of the
    rain is that old. {} where no frame has an issue time."""
    issued = [f[["cell_lat", "cell_lon", "issued_at"]] for f in frames if f is not None and len(f) and "issued_at" in f]
    if not issued:
        return {}
    cells = pd.concat(issued, ignore_index=True)
    cells["issued_at"] = pd.to_datetime(cells["issued_at"], utc=True)
    cells = cells.dropna(subset=["issued_at"]).groupby(["cell_lat", "cell_lon"])["issued_at"].min()
    if cells.empty:
        return {}
    oldest, newest = cells.min(), cells.max()
    out = {"rain_issued_at": oldest, "rain_age_h": round(max(0.0, (now - oldest).total_seconds()) / 3600, 1)}
    why = _why.get(cells.idxmin())
    if why:
        out["rain_fallback"] = why
    if newest - oldest > pd.Timedelta(hours=1):
        out["rain_mixed"] = True
    return out


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
                   stale_max_age_s: float = STALE_MAX_AGE_S, what: str = "spots",
                   ensemble: bool = False) -> pd.DataFrame:
    """Recent observed-ish and forecast hourly precipitation per cell (cached FORECAST_TTL_S). `attempts` per
    request of up to FORECAST_BATCH cells (see _request). A request that still fails does not
    raise: its cells get their cached forecast if it is at most `stale_max_age_s` old and are
    left out otherwise, so they have no rain data (never zero rain). Requests are the same as
    before, one per FORECAST_BATCH cells not freshly cached; a cell that failed earlier in this
    process, or any cell during an outage (OUTAGE_AFTER), goes to the cache without one.
    `forecast_days` counts the Europe/London days the forecast shows, today first. Open-Meteo is
    asked for one more UTC day than that, so the last of them is whole at any hour. Each request
    is booked in the day's ledger under `what`; one the ration has no room for is not made, and its
    cells go to the cache as after a failure.

    With `ensemble`, the ensemble's members instead, by their own rules (fetch_ensemble): one row per
    cell, hour and member, from 00:00 UTC today, and no past days. At most two attempts a request: the
    members are optional, and a retry is one more request in the build."""
    if ensemble:
        return fetch_ensemble(cells, forecast_days=forecast_days, attempts=min(attempts, 2))
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
        weight = forecast_weight(len(chunk), past_days, forecast_days)
        cause = "no answer"
        if time.time() < _outage["until"]:
            why = "open-meteo taken as down after repeated failures"
        elif not may_spend(weight, what):
            why, cause = "the day's Open-Meteo ration is spent", "daily limit"
        else:
            params = {
                "latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
                "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
                "hourly": "precipitation",
                "past_days": past_days,
                # One UTC day more than the local days shown. In summer time, from 23:00 UTC the
                # local date is a day ahead of the UTC one, so the fifth local day ends an hour into
                # a UTC day not asked for. With forecast_days alone that day has one hour of rain, and a
                # build issued from 23:00 to 00:00 UTC shows no figure for it.
                "forecast_days": forecast_days + 1,
                "timezone": "UTC",
            }
            try:
                res = _request(config.OPEN_METEO_FORECAST, params, timeout=30, attempts=attempts)  # small payload; fail fast on a bad handshake
            except Exception as e:  # noqa: BLE001 - OpenMeteoError, or anything else a request raises
                if isinstance(e, OpenMeteoBadBody):
                    spend(weight, what)   # answered, so counted, though not readable
                why = redact(str(e) or type(e).__name__)
                _errors.append(why)
                _outage["run"] += 1
                if _outage["run"] >= OUTAGE_AFTER:
                    _outage.update(run=0, until=time.time() + OUTAGE_COOLOFF_S)
                    log.warning("open-meteo: %d forecast requests in a row failed; none for %.0f min",
                                OUTAGE_AFTER, OUTAGE_COOLOFF_S / 60)
            else:
                spend(weight, what)
                _outage["run"] = 0
                results = res if isinstance(res, list) else [res]
                for (cl, cn), r in zip(chunk, results, strict=True):
                    df = _to_frame(r, cl, cn)
                    df["issued_at"] = pd.Timestamp.now(tz="UTC")
                    df.to_parquet(CACHE / f"forecast_{cell_key(cl, cn)}.parquet", index=False)
                    frames.append(df)
                    _failed_at.pop((cl, cn), None)
                    _stale.pop((cl, cn), None)
                    _why.pop((cl, cn), None)
                    _missing.discard((cl, cn))
                continue
        t = time.time()
        _failed_at.update({c: t for c in chunk})
        _why.update({c: cause for c in chunk})
        got = _cached_instead(chunk, stale_max_age_s)
        frames += got
        log.warning("rain forecast: %d cells not fetched (%s): %d from a cached forecast at most %.0f h old, "
                    "%d with no rain data", len(chunk), why, len(got), stale_max_age_s / 3600, len(chunk) - len(got))
    return pd.concat(frames, ignore_index=True) if frames else _empty_forecast()


# ------------------------------------------------------------------ ensemble
# The ensemble members (docs/ENSEMBLE-RAIN-TEST-2026-11.md). Open-Meteo weighs an ensemble request by its
# variables times the model's members (ForecastapiController.swift, 13 Oct 2026), so one variable from three members
# over six days is max(1, 0.3, 0.3 x 6/14) = 1 call a cell, as a forecast cell is. The 332 spot cells are
# 7 requests and 332 calls a refresh. Three rules keep that out of the way of everything else:
#   * a cell is asked for again only when its cached members are ENSEMBLE_TTL_S old, or no longer reach far
#     enough into the fifth local day for it to count (ensemble_until): about two refreshes a day;
#   * at most ENSEMBLE_DAILY_CALLS in a UTC day;
#   * only from spare calls (spare_for): after the request, what is left of the day's ration must still
#     cover PLANNED_DAY_CALLS spread over the rest of the UTC day. That is the others' most at a build
#     every 30 minutes, so at that rate no ensemble request is made, and none is held from the others.
# A request the rules hold back or that fails, and any cell asked for once in this process, goes to the
# cached members if under ENSEMBLE_STALE_MAX_AGE_S old; a day they do not reach has no band, never no rain.
ENSEMBLE_TTL_S = 12 * 3600
ENSEMBLE_STALE_MAX_AGE_S = 24 * 3600
ENSEMBLE_DAILY_CALLS = 1000.0
# The others' most in a UTC day (spots 3,984, click-anywhere 2,540, weather 945, Scotland 1,280):
# tests/test_open_meteo_ration.py, test_the_floors_fit_the_free_tier_at_a_build_every_30_minutes.
PLANNED_DAY_CALLS = 8750.0
# A day's rain counts with this many finite hours (model.features.MIN_HOURS_PER_DAY; features imports
# this module, so the number is repeated here and a test keeps the two equal).
DAY_HOURS_NEEDED = 20
_ens_asked: set[tuple[float, float]] = set()   # cells asked for (or held back) in this process
_ens: dict[str, object] = {}                    # what this process's ensemble requests did (ensemble_summary)


def ensemble_weight(n_cells: int, forecast_days: int = config.FORECAST_DAYS) -> float:
    """What fetch_ensemble's request for n_cells costs: one variable from each member, forecast_days + 1 days."""
    return call_weight(n_cells, forecast_days + 1, variables=config.ENSEMBLE_MEMBERS)


def spare_for(weight: float, now: float | None = None) -> bool:
    """Whether `weight` calls are spare today: after them, what is left of the ration still covers
    PLANNED_DAY_CALLS spread over what is left of the UTC day."""
    t = time.time() if now is None else now
    rest_of_day = (86400 - t % 86400) / 86400
    return calls_left(t) - weight >= PLANNED_DAY_CALLS * rest_of_day


def ensemble_until(forecast_days: int = config.FORECAST_DAYS, now: pd.Timestamp | None = None) -> pd.Timestamp:
    """The last hour (UTC) the members must reach: DAY_HOURS_NEEDED hours into the last local day shown."""
    now = pd.Timestamp.now(tz="Europe/London") if now is None else now.tz_convert("Europe/London")
    last_day = now.normalize() + pd.DateOffset(days=forecast_days - 1)   # local midnight, across a clock change too
    return (last_day + pd.Timedelta(hours=DAY_HOURS_NEEDED - 1)).tz_convert("UTC")


def ensemble_reach(df: pd.DataFrame) -> pd.Timestamp | None:
    """The last hour at which every member of a cell's cached ensemble has a value, None when none has."""
    ok = df.dropna(subset=["precip_mm"]).groupby("time")["member"].nunique()
    full = ok[ok >= df["member"].nunique()]
    return None if full.empty else full.index.max()


def _ensemble_frame(res: dict, cell_lat: float, cell_lon: float) -> pd.DataFrame:
    """One cell's answer as rows of (time, member, precip_mm): the control is `precipitation` (member 0),
    the others `precipitation_memberNN`."""
    h = res["hourly"]
    t = pd.to_datetime(h["time"], utc=True)
    frames = []
    for k in sorted(k for k in h if k == "precipitation" or k.startswith("precipitation_member")):
        m = 0 if k == "precipitation" else int(k.rsplit("member", 1)[1])
        frames.append(pd.DataFrame({"cell_lat": cell_lat, "cell_lon": cell_lon, "time": t, "member": m,
                                    "precip_mm": np.asarray([np.nan if v is None else v for v in h[k]], dtype=float)}))
    return pd.concat(frames, ignore_index=True)


def _empty_ensemble() -> pd.DataFrame:
    return pd.DataFrame({"cell_lat": pd.Series(dtype=float), "cell_lon": pd.Series(dtype=float),
                         "time": pd.Series(dtype="datetime64[ns, UTC]"), "member": pd.Series(dtype=int),
                         "precip_mm": pd.Series(dtype=float), "issued_at": pd.Series(dtype="datetime64[ns, UTC]")})


def _ensemble_cached(c: tuple[float, float], max_age_s: float) -> pd.DataFrame | None:
    p = CACHE / f"ensemble_{cell_key(*c)}.parquet"
    if not p.exists() or time.time() - p.stat().st_mtime > max_age_s:
        return None
    try:
        return pd.read_parquet(p)
    except Exception as e:  # noqa: BLE001 - a torn cache file counts as none
        log.warning("ensemble cache %s unreadable: %s", p.name, e)
        return None


def _tally(key: str, n: int = 1) -> None:
    _ens[key] = int(_ens.get(key, 0)) + n


def fetch_ensemble(cells: list[tuple[float, float]], forecast_days: int = config.FORECAST_DAYS,
                   attempts: int = 2) -> pd.DataFrame:
    """The ensemble's hourly rain per cell and member (config.ENSEMBLE_MODEL), by the rules above the
    constants. Rows: cell_lat, cell_lon, time (UTC, from 00:00 today), member, precip_mm (NaN past the
    run's reach), issued_at. Booked in the ledger as "ensemble". Never raises: a cell with nothing cached
    young enough is left out, so its overflows' members have no rain."""
    CACHE.mkdir(parents=True, exist_ok=True)
    until = ensemble_until(forecast_days)
    frames, todo = [], []
    for c in cells:
        df = _ensemble_cached(c, ENSEMBLE_TTL_S)
        reach = None if df is None else ensemble_reach(df)
        if df is not None and (c in _ens_asked or (reach is not None and reach >= until)):
            frames.append(df)
        elif c in _ens_asked:
            got = _ensemble_cached(c, ENSEMBLE_STALE_MAX_AGE_S)
            frames += [] if got is None else [got]
        else:
            todo.append(c)
    for i in range(0, len(todo), FORECAST_BATCH):
        chunk = todo[i:i + FORECAST_BATCH]
        _ens_asked.update(chunk)
        weight = ensemble_weight(len(chunk), forecast_days)
        spent = float(calls_today()["by"].get("ensemble", 0.0))
        if _ens.get("down"):
            why = "an earlier ensemble request failed in this build"
        elif spent + weight > ENSEMBLE_DAILY_CALLS:
            why = f"the day's {ENSEMBLE_DAILY_CALLS:.0f} ensemble calls are spent"
        elif not spare_for(weight):
            why = "no spare calls beside the others' planned use for the rest of the day"
        else:
            params = {
                "latitude": ",".join(f"{c[0]:.3f}" for c in chunk),
                "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
                "hourly": "precipitation",
                "models": config.ENSEMBLE_MODEL,
                "past_days": 0,
                "forecast_days": forecast_days + 1,   # one UTC day more than the local days, as fetch_forecast
                "timezone": "UTC",
            }
            try:
                res = _request(config.OPEN_METEO_ENSEMBLE, params, timeout=30, attempts=attempts)
            except Exception as e:  # noqa: BLE001 - the band is optional: no ensemble, no band
                if isinstance(e, OpenMeteoBadBody):
                    spend(weight, "ensemble")
                why = redact(str(e) or type(e).__name__)
                _ens["down"] = True
                _ens.setdefault("errors", []).append(why)
            else:
                spend(weight, "ensemble")
                issued = pd.Timestamp.now(tz="UTC")
                for (cl, cn), r in zip(chunk, res if isinstance(res, list) else [res], strict=True):
                    df = _ensemble_frame(r, cl, cn).assign(issued_at=issued)
                    if df["member"].nunique() != config.ENSEMBLE_MEMBERS:
                        log.warning("ensemble: %d members for %s, not %d (the test's window ends: "
                                    "docs/ENSEMBLE-RAIN-TEST-2026-11.md)", df["member"].nunique(), cell_key(cl, cn),
                                    config.ENSEMBLE_MEMBERS)
                    df.to_parquet(CACHE / f"ensemble_{cell_key(cl, cn)}.parquet", index=False)
                    frames.append(df)
                _tally("fetched", len(chunk))
                continue
        got = [d for d in (_ensemble_cached(c, ENSEMBLE_STALE_MAX_AGE_S) for c in chunk) if d is not None]
        frames += got
        _tally("not_fetched", len(chunk))
        _tally("from_older_cache", len(got))
        log.info("rain ensemble: %d cells not fetched (%s): %d from cached members at most %.0f h old",
                 len(chunk), why, len(got), ENSEMBLE_STALE_MAX_AGE_S / 3600)
    return pd.concat(frames, ignore_index=True) if frames else _empty_ensemble()


def ensemble_summary() -> dict:
    """What this process's ensemble fetches did: cells fetched, not fetched (held by the rules or failed)
    and of those how many had older members, and the first errors."""
    return {k: (list(dict.fromkeys(v))[:3] if k == "errors" else v) for k, v in _ens.items() if k != "down"}


def cells_for_sites(lat: pd.Series, lon: pd.Series) -> list[tuple[float, float]]:
    cl, cn = grid_cell(lat.to_numpy(), lon.to_numpy())
    return sorted({(float(a), float(b)) for a, b in zip(cl, cn, strict=True)})
