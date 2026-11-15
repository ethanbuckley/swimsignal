"""Archive rain for coastal candidate C1 (docs/COASTAL-C1-PROTOCOL-2026-11.md), from this Mac, never from CI.

    uv run python scripts/coastal_c1/fetch_rain.py --out "$HOME/dipcast-scratch/coastal-c1-rain" --dry-run
    uv run python scripts/coastal_c1/fetch_rain.py --out "$HOME/dipcast-scratch/coastal-c1-rain" --status
    uv run python scripts/coastal_c1/fetch_rain.py --out "$HOME/dipcast-scratch/coastal-c1-rain"

What it asks for: hourly precipitation from Open-Meteo's archive API, model `era5_land`, for the 0.1 degree cell of
each mapped coastal sampling point (185 cells, from data/research/coastal/sites.csv), from 24 April to 30 September
of each season 2012 to 2026. One request is one season for up to 10 cells. Fit seasons (2026 to 2022) come first, then
the backtest seasons (2021 to 2012). No sample result is fetched or read here.

The rules (the protocol's section 3):
  * It does not send a request before FIRST_DAY (22 Nov 2026, UTC). --dry-run and --status send nothing and run
    any day.
  * At most DAILY_CAP weighted calls in a UTC day (Open-Meteo's own weight, rainfall.call_weight), counted from the
    ledger, every attempt included. A request that would take the day over the cap is not sent; the run stops and
    the next UTC day carries on.
  * The first refusal (HTTP 429, 401 or 403, or a 4xx whose "reason" names a limit) stops the run, and no further
    request is sent that UTC day. Any other 4xx stops the run too: it means the request is wrong.
  * A 5xx or a lost connection is tried again after 30 s and then 90 s. Each try is ledgered and counted.
  * PACE_S seconds between requests.
  * Every request sent is one line of <out>/ledger.jsonl. Each cell-season answer is <out>/rain/<season>/<cell>.parquet.
    A cell-season already on disk is never asked for again, so the same command resumes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SITES = REPO / "data" / "research" / "coastal" / "sites.csv"

URL = "https://archive-api.open-meteo.com/v1/archive"
MODEL = "era5_land"
FIRST_DAY = date(2026, 11, 22)       # the D4 ensemble test is read on 21 Nov (docs/ENSEMBLE-RAIN-TEST-2026-11.md)
DAILY_CAP = 1000.0                   # weighted calls a UTC day; the protocol's section 3 says why
FIT_SEASONS = (2026, 2025, 2024, 2023, 2022)
BACKTEST_SEASONS = tuple(range(2021, 2011, -1))
SEASONS = FIT_SEASONS + BACKTEST_SEASONS
START_MD, END_MD = "04-24", "09-30"  # 7 days before 1 May for the longest window, to the season's last day
GRID_DEG = 0.1
BATCH = 10
PACE_S = 5.0
RETRY_WAITS_S = (30.0, 90.0)
REFUSALS = (401, 403, 429)
TIMEOUT_S = 120.0
USER_AGENT = "swimsignal-research (coastal C1 rain, archive)"
# Exit codes, so the run sheet can say what each means.
OK, TOO_EARLY, REFUSED, FAILED = 0, 2, 3, 4


@dataclass(frozen=True)
class Answer:
    """What came back for one attempt: status None means no HTTP answer (a lost connection or a timeout)."""
    status: int | None
    body: bytes = b""
    error: str | None = None


Get = Callable[[str, dict], Answer]


def call_weight(n_locations: int, days: float, variables: int = 1) -> float:
    """Open-Meteo's count for one request: per location max(1, v/10, v/10 x days/14), v the variables. The same rule
    as dipcast.ingest.rainfall.call_weight (a test keeps the two equal); repeated so this script imports nothing that
    reads the build's cache or ledger."""
    v = variables / 10
    return n_locations * max(1.0, v, v * days / 14)


def season_days(season: int) -> tuple[str, str, int]:
    start, end = f"{season}-{START_MD}", f"{season}-{END_MD}"
    return start, end, (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def cell_key(lat: float, lon: float) -> str:
    return f"{lat + 0.0:.3f}_{lon + 0.0:.3f}"


def cells(sites: Path = SITES) -> list[tuple[float, float]]:
    """The 0.1 degree cell of every mapped sampling point, sorted. The same snapping as rainfall.grid_cell."""
    s = pd.read_csv(sites)
    s = s[s["wqa_point"].notna()]
    lat = np.round(np.round(s["lat"].to_numpy() / GRID_DEG) * GRID_DEG, 3) + 0.0
    lon = np.round(np.round(s["lon"].to_numpy() / GRID_DEG) * GRID_DEG, 3) + 0.0
    return sorted({(float(a), float(b)) for a, b in zip(lat, lon, strict=True)})


def cell_file(out: Path, season: int, cell: tuple[float, float]) -> Path:
    return out / "rain" / str(season) / f"{cell_key(*cell)}.parquet"


def todo(out: Path, all_cells: list[tuple[float, float]]) -> list[tuple[int, list[tuple[float, float]]]]:
    """The requests still to send, in order: for each season, its missing cells in chunks of BATCH."""
    jobs = []
    for season in SEASONS:
        missing = [c for c in all_cells if not cell_file(out, season, c).exists()]
        jobs += [(season, missing[i:i + BATCH]) for i in range(0, len(missing), BATCH)]
    return jobs


def job_weight(season: int, chunk: list) -> float:
    return call_weight(len(chunk), season_days(season)[2])


# ------------------------------------------------------------------ the ledger
def ledger_rows(out: Path) -> list[dict]:
    f = out / "ledger.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []


def spent_on(rows: list[dict], day: str) -> float:
    return round(sum(r["weight"] for r in rows if r["day"] == day), 3)


def refused_on(rows: list[dict], day: str) -> bool:
    return any(r["day"] == day and r["outcome"] == "refused" for r in rows)


def _log(out: Path, row: dict) -> None:
    with (out / "ledger.jsonl").open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


# ------------------------------------------------------------------ one answer
def frames(body: bytes, season: int, chunk: list[tuple[float, float]]) -> list[pd.DataFrame]:
    """One frame per requested cell, in request order. Raises ValueError for an answer that does not hold every hour
    of the season for every cell, so a short answer is never saved as if whole."""
    data = json.loads(body)
    items = data if isinstance(data, list) else [data]
    if len(items) != len(chunk):
        raise ValueError(f"{len(items)} locations in the answer for {len(chunk)} asked")
    start, _, days = season_days(season)
    want = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    out = []
    for (cl, cn), it in zip(chunk, items, strict=True):
        h = it["hourly"]
        t = pd.to_datetime(h["time"], utc=True)
        if len(t) != len(want) or not (t == want).all():
            raise ValueError(f"cell {cell_key(cl, cn)}: {len(t)} hours, expected {len(want)}")
        out.append(pd.DataFrame({
            "cell_lat": cl, "cell_lon": cn, "time": t,
            "precip_mm": np.asarray(h["precipitation"], dtype=float),
            # where Open-Meteo took the series from (its land-selected grid point), kept for the audit
            "grid_lat": float(it.get("latitude", np.nan)), "grid_lon": float(it.get("longitude", np.nan)),
            "elevation_m": float(it["elevation"]) if isinstance(it.get("elevation"), (int, float)) else np.nan,
        }))
    return out


def params(season: int, chunk: list[tuple[float, float]]) -> dict:
    start, end, _ = season_days(season)
    return {"latitude": ",".join(f"{c[0]:.3f}" for c in chunk), "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
            "start_date": start, "end_date": end, "hourly": "precipitation", "models": MODEL, "timezone": "UTC"}


def http_get(url: str, p: dict) -> Answer:
    import httpx   # only the real run needs it
    try:
        r = httpx.get(url, params=p, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT})
    except httpx.TransportError as e:
        return Answer(None, b"", type(e).__name__)
    return Answer(r.status_code, r.content)


def _is_error_body(body: bytes) -> str | None:
    try:
        d = json.loads(body)
    except ValueError:
        return None
    if isinstance(d, dict) and d.get("error"):
        return str(d.get("reason", "error: true"))[:300]
    return None


# ------------------------------------------------------------------ the run
def run(out: Path, get: Get = http_get, now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], None] = time.sleep, cap: float = DAILY_CAP, sites: Path = SITES) -> int:
    out.mkdir(parents=True, exist_ok=True)
    today = now().date()
    if today < FIRST_DAY:
        print(f"Not before {FIRST_DAY} (UTC). Today is {today}. No request sent.")
        return TOO_EARLY
    day = today.isoformat()
    rows = ledger_rows(out)
    if refused_on(rows, day):
        print(f"Open-Meteo refused a request today ({day}). No request sent. Read the ledger's last line.")
        return REFUSED
    all_cells = cells(sites)
    spent = spent_on(rows, day)
    sent_any = False
    for season, chunk in todo(out, all_cells):
        w = job_weight(season, chunk)
        for attempt, wait in enumerate((*RETRY_WAITS_S, None)):
            if spent + w > cap:
                print(f"Daily cap reached: {spent:.1f} of {cap:.0f} calls used today. Run again after 00:00 UTC.")
                return summary(out, all_cells, day, cap) or OK
            if sent_any:
                sleep(PACE_S)
            sent_any = True
            t0 = now()
            a = get(URL, params(season, chunk))
            spent = round(spent + w, 3)
            row = {"at": t0.isoformat(timespec="seconds"), "day": day, "season": season, "cells": len(chunk),
                   "first_cell": cell_key(*chunk[0]), "weight": round(w, 3), "attempt": attempt + 1,
                   "status": a.status, "bytes": len(a.body), "sha256": hashlib.sha256(a.body).hexdigest()}
            reason = _is_error_body(a.body) if a.body else None
            if a.status in REFUSALS or (a.status is not None and a.status < 500 and reason and "limit" in reason.lower()):
                row.update(outcome="refused", reason=reason or a.body[:300].decode("utf-8", "replace"))
                _log(out, row)
                print(f"Refused: HTTP {a.status} ({row['reason']}). Stopped. No further request today.")
                return REFUSED
            if a.status == 200:
                try:
                    fs = frames(a.body, season, chunk)
                except (ValueError, KeyError, TypeError) as e:
                    row.update(outcome="bad_answer", reason=str(e)[:300])
                    _log(out, row)
                    print(f"Season {season}: an answer that is not whole ({e}). Stopped.")
                    return FAILED
                for c, f in zip(chunk, fs, strict=True):
                    p = cell_file(out, season, c)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    tmp = p.with_suffix(".tmp")
                    f.to_parquet(tmp, index=False)
                    tmp.replace(p)
                row["outcome"] = "ok"
                _log(out, row)
                break
            if a.status is not None and a.status < 500:
                row.update(outcome="failed", reason=a.body[:300].decode("utf-8", "replace"))
                _log(out, row)
                print(f"HTTP {a.status}: the request is wrong, not refused. Stopped.")
                return FAILED
            row.update(outcome="retry" if wait is not None else "failed", reason=a.error or f"HTTP {a.status}")
            _log(out, row)
            if wait is None:
                print(f"No answer after {len(RETRY_WAITS_S) + 1} tries ({row['reason']}). Stopped.")
                return FAILED
            sleep(wait)
    summary(out, all_cells, day, cap)
    return OK


def summary(out: Path, all_cells: list, day: str, cap: float = DAILY_CAP) -> None:
    """Prints progress. Writes <out>/complete.json once every cell-season is on disk."""
    left = todo(out, all_cells)
    total = len(all_cells) * len(SEASONS)
    missing = sum(len(c) for _, c in left)
    rows = ledger_rows(out)
    w_left = sum(job_weight(s, c) for s, c in left)
    print(f"Cell-seasons on disk: {total - missing} of {total}. Requests left: {len(left)}, "
          f"{w_left:.1f} calls (about {math.ceil(w_left / cap) if w_left else 0} more day(s) at {cap:.0f}). "
          f"Today ({day}): {spent_on(rows, day):.1f} calls used.")
    if not left:
        files = sorted((out / "rain").rglob("*.parquet"))
        h = hashlib.sha256()
        for f in files:
            h.update(f.relative_to(out).as_posix().encode())
            h.update(hashlib.sha256(f.read_bytes()).digest())
        done = {"complete": True, "cell_seasons": len(files), "cells": len(all_cells), "seasons": list(SEASONS),
                "model": MODEL, "requests_sent": len(rows), "calls_counted": round(sum(r["weight"] for r in rows), 3),
                "refusals": sum(r["outcome"] == "refused" for r in rows), "files_sha256": h.hexdigest()}
        (out / "complete.json").write_text(json.dumps(done, indent=1) + "\n")
        print("COMPLETE: every cell-season is on disk. complete.json written.")


def dry_run(cap: float = DAILY_CAP, sites: Path = SITES) -> dict:
    """The size of the whole fetch, sending nothing: requests, weighted calls, days at the cap, wall time."""
    c = cells(sites)
    jobs = [(s, c[i:i + BATCH]) for s in SEASONS for i in range(0, len(c), BATCH)]
    weights = [job_weight(s, ch) for s, ch in jobs]
    days, used = 1, 0.0
    for w in weights:   # the run packs whole requests into each day
        if used + w > cap:
            days, used = days + 1, 0.0
        used += w
    fit = sum(w for (s, _), w in zip(jobs, weights, strict=True) if s in FIT_SEASONS)
    return {"cells": len(c), "seasons": len(SEASONS), "days_per_season": season_days(2026)[2],
            "requests": len(jobs), "calls": round(sum(weights), 1), "calls_fit_seasons": round(fit, 1),
            "calls_backtest_seasons": round(sum(weights) - fit, 1), "cap": cap, "days_at_cap": days,
            "max_requests_a_day": int(cap // max(weights)),
            "wall_minutes_a_day_at_5s_plus_5s": round(int(cap // max(weights)) * (PACE_S + 5) / 60, 1)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="a folder outside every checkout; the ledger lives there")
    ap.add_argument("--dry-run", action="store_true", help="print the fetch's size; send nothing")
    ap.add_argument("--status", action="store_true", help="print progress and today's calls; send nothing")
    a = ap.parse_args(argv)
    if a.dry_run:
        print(json.dumps(dry_run(), indent=1))
        return OK
    if a.status:
        a.out.mkdir(parents=True, exist_ok=True)
        summary(a.out, cells(), datetime.now(UTC).date().isoformat())
        return OK
    return run(a.out)


if __name__ == "__main__":
    sys.exit(main())
