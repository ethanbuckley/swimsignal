"""The two capped fetches of docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md.

    python -I wt_fetch.py ea --cache <private>/water-temperature/ea [--fetch]
    python -I wt_fetch.py open_meteo --cache <private>/water-temperature/open-meteo --plan <plan.json> [--fetch]

`ea`: determinand 0076 from the EA Water Quality Archive, one query per calendar month (May-September, 2018-2025) for
each material set (fresh, sea), paged by 2,500 rows until a short page. CSV.
`open_meteo`: daily mean air temperature (ERA5-Land) for the cell-seasons in plan.json (written by wt_score.py plan),
in batches of at most 25 cells, 1 April to 30 September.

The caps, fixed here before any request (the statement, "Caps"):
EA: at most 300 requests; at most 8 pages a month and set; one in flight, 1.5 s apart; https to
environment.data.gov.uk only; stop at the first 403, 429, 5xx, redirect or connection error, no retry; stop past 600 MB.
Open-Meteo: at most 20,000 weighted calls in all, 6,000 in a UTC day (from this fetch's own log); one in flight, 60 s
apart; https to archive-api.open-meteo.com only; stop at the first 4xx, 5xx, redirect, connection error or body that
is not JSON, no retry. At the day's cap the process sleeps to 00:10 UTC and, once no other local Open-Meteo job runs,
carries on.
Every answer is cached under --cache and never asked for again; every request is logged to <cache>/requests.log.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wt_protocol as wp  # noqa: E402

EA_HOST = "environment.data.gov.uk"
EA_URL = f"https://{EA_HOST}/water-quality/data/observation"
EA_MAX_REQUESTS = 300
EA_MAX_PAGES = 8
EA_PAUSE_S = 1.5
EA_MAX_BYTES = 600 * 1024 * 1024
PAGE = 2500
EA_YEARS = tuple(range(2018, 2026))
SETS = {"fresh": wp.FRESH_CODES, "sea": wp.SEA_CODES}

OM_HOST = "archive-api.open-meteo.com"
OM_URL = f"https://{OM_HOST}/v1/archive"
OM_PAUSE_S = 25.0          # amended 27 Oct (was 60 s): 4,700 an hour at 32.7 a request is one every 25 s
OM_MODEL = "era5_land"
UA = "swimsignal-research (water temperature model test; hello@swimsignal.co.uk)"


class Stop(SystemExit):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class Log:
    def __init__(self, path: Path):
        self.path = path

    def add(self, status: str, size: int, weight: float, url: str) -> None:
        with open(self.path, "a") as fh:
            fh.write(f"{_now().isoformat(timespec='seconds')}\t{status}\t{size}\t{weight}\t{url}\n")

    def lines(self) -> list[list[str]]:
        if not self.path.exists():
            return []
        return [ln.rstrip("\n").split("\t") for ln in self.path.read_text().splitlines() if ln.strip()]


# ================================================================== EA
class EAClient:
    def __init__(self, cache: Path, fetch: bool, transport: httpx.BaseTransport | None = None, sleep=time.sleep,
                 max_requests: int = EA_MAX_REQUESTS, max_bytes: int = EA_MAX_BYTES):
        self.cache, self.fetch, self.sleep = Path(cache), fetch, sleep
        self.cache.mkdir(parents=True, exist_ok=True)
        self.log = Log(self.cache / "requests.log")
        self.max_requests, self.max_bytes = max_requests, max_bytes
        prior = self.log.lines()
        self.n = len(prior)                                   # the cap counts every request ever made, all runs
        self.bytes = sum(int(x[2]) for x in prior if len(x) > 2 and x[2].isdigit())
        self.http = httpx.Client(timeout=300, follow_redirects=False, transport=transport,
                                 headers={"User-Agent": UA, "Accept": "text/csv"})
        self._last = 0.0

    @staticmethod
    def name(params: dict) -> str:
        return f"{params['set']}_{params['dateFrom']}_{params['dateTo']}_{int(params['skip']):06d}.csv"

    def page(self, set_name: str, date_from: str, date_to: str, skip: int) -> str:
        f = self.cache / self.name({"set": set_name, "dateFrom": date_from, "dateTo": date_to, "skip": skip})
        if f.exists():
            return f.read_text()
        if not self.fetch:
            raise Stop(f"{f.name} is not cached; rerun with --fetch")
        if self.n >= self.max_requests:
            raise Stop(f"EA cap of {self.max_requests} requests reached")
        if self.bytes >= self.max_bytes:
            raise Stop(f"EA byte cap of {self.max_bytes} reached")
        params = {"determinand": "0076", "sampleMaterialType": SETS[set_name], "dateFrom": date_from,
                  "dateTo": date_to, "limit": PAGE, "skip": skip}
        url = EA_URL + "?" + urlencode(params)
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname != EA_HOST:
            raise Stop(f"refused: {url}")
        wait = EA_PAUSE_S - (time.monotonic() - self._last)
        if self._last and wait > 0:
            self.sleep(wait)
        self.n += 1
        try:
            # The multi-point endpoint is POST only (the OpenAPI document lists `post /data/observation`; a GET
            # answered 405 on 27 Oct). The filters go in the query string and the body is empty, as there.
            r = self.http.post(url, content=b"")
        except httpx.HTTPError as e:
            self.log.add("ERR", 0, 0, url)
            raise Stop(f"{url}: {type(e).__name__}: stopping") from e
        finally:
            self._last = time.monotonic()
        self.bytes += len(r.content)
        self.log.add(str(r.status_code), len(r.content), 0, url)
        if r.status_code in (403, 429) or r.status_code >= 500 or 300 <= r.status_code < 400:
            raise Stop(f"{url} answered {r.status_code}: stopping")
        if r.status_code == 204:
            # No rows for that month and set (first seen for sea water, May 2020): an empty page, cached as such.
            f.write_text("")
            return ""
        if r.status_code != 200:
            raise Stop(f"{url} answered {r.status_code}: stopping")
        f.write_text(r.text)
        return r.text


def month_ranges(years=EA_YEARS, months=wp.MONTHS) -> list[tuple[str, str]]:
    """(dateFrom, dateTo) per month. dateTo is the first day of the next month: the archive's dateTo is exclusive.
    On 27 Oct, dateTo=2018-05-31 returned nothing later than 30 May 18:35, and dateTo=2025-06-30 nothing later than
    29 June. A reading at 00:00 on the first of the next month can come in both months; ids are de-duplicated."""
    out = []
    for y in years:
        for m in months:
            ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
            out.append((f"{y}-{m:02d}-01", f"{ny}-{nm:02d}-01"))
    return out


def data_rows(csv_text: str) -> int:
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    return max(0, len(lines) - 1)


def fetch_ea(client: EAClient, ranges=None) -> dict:
    """Every month and set, paged until a short page. Returns {"pages": n, "rows": n}."""
    pages = rows = 0
    for date_from, date_to in ranges or month_ranges():
        for set_name in SETS:
            for k in range(EA_MAX_PAGES + 1):
                if k == EA_MAX_PAGES:
                    raise Stop(f"{set_name} {date_from}: more than {EA_MAX_PAGES} pages; paging not working")
                text = client.page(set_name, date_from, date_to, k * PAGE)
                n = data_rows(text)
                pages += 1
                rows += n
                if n < PAGE:
                    break
    return {"pages": pages, "rows": rows}


# ================================================================== Open-Meteo
def other_open_meteo_jobs(me: int | None = None) -> list[str]:
    """Other local Python processes that fetch from Open-Meteo: a second `wt_fetch.py open_meteo`, or any Python job
    whose command line names Open-Meteo. Shells and log watchers (zsh `until` loops, `tail`, `grep`) and this process
    and its parent are left out. On 27 Oct the first version matched this test's own watcher shells, whose command
    lines name open_meteo.log, and waited on them. Nothing here ever stops another process."""
    me = os.getpid() if me is None else me
    try:
        out = subprocess.run(["pgrep", "-fl", "wt_fetch.py open_meteo|open-meteo|open_meteo|openmeteo"],
                             capture_output=True, text=True).stdout
    except OSError:
        return []
    mine = {me, os.getppid()}
    found = []
    for ln in out.splitlines():
        parts = ln.split()
        if len(parts) < 2 or not parts[0].isdigit() or int(parts[0]) in mine:
            continue
        if not Path(parts[1]).name.lower().startswith("python"):
            continue
        found.append(ln)
    return found


class OMClient:
    def __init__(self, cache: Path, fetch: bool, transport: httpx.BaseTransport | None = None, sleep=time.sleep,
                 now=_now, total_cap: float = wp.OM_TOTAL_CAP, day_cap: float = wp.OM_DAY_CAP,
                 pause_s: float = OM_PAUSE_S, others=other_open_meteo_jobs, model: str | None = OM_MODEL,
                 hour_cap: float = wp.OM_HOUR_CAP):
        self.cache, self.fetch, self.sleep, self.now = Path(cache), fetch, sleep, now
        self.cache.mkdir(parents=True, exist_ok=True)
        self.log = Log(self.cache / "requests.log")
        self.total_cap, self.day_cap, self.pause_s, self.others, self.model = total_cap, day_cap, pause_s, others, model
        self.hour_cap = hour_cap
        self.http = httpx.Client(timeout=120, follow_redirects=False, transport=transport, headers={"User-Agent": UA})
        self._last = None

    def spent_since(self, t0: datetime) -> float:
        """Weight logged after t0 (the rolling-hour cap)."""
        tot = 0.0
        for x in self.log.lines():
            if len(x) >= 4 and datetime.fromisoformat(x[0]) > t0:
                tot += float(x[3])
        return tot

    def spent(self, day: str | None = None) -> float:
        tot = 0.0
        for x in self.log.lines():
            if len(x) < 4:
                continue
            if day is None or x[0][:10] == day:
                tot += float(x[3])
        return tot

    def _wait_for_day(self, weight: float) -> None:
        while self.spent(self.now().strftime("%Y-%m-%d")) + weight > self.day_cap:
            t = self.now()
            nxt = (t + timedelta(days=1)).replace(hour=0, minute=10, second=0, microsecond=0)
            print(f"{t.isoformat(timespec='seconds')}: the day's {self.day_cap:.0f} spent; sleeping to {nxt}",
                  flush=True)
            self.sleep(max(60.0, (nxt - t).total_seconds()))
        while self.spent_since(self.now() - timedelta(hours=1)) + weight > self.hour_cap:
            print(f"{self.now().isoformat(timespec='seconds')}: {self.hour_cap:.0f} spent in the last hour; waiting",
                  flush=True)
            self.sleep(60)
        while (o := self.others()):
            print(f"{self.now().isoformat(timespec='seconds')}: another Open-Meteo job runs, waiting: {o}", flush=True)
            self.sleep(600)

    def batch(self, year: int, cells: list[str]) -> list[dict]:
        key = f"{year}_" + __import__("hashlib").sha1(",".join(cells).encode()).hexdigest()[:16]
        f = self.cache / f"{key}.json"
        if f.exists():
            return json.loads(f.read_text())["answer"]
        if not self.fetch:
            raise Stop(f"{f.name} is not cached; rerun with --fetch")
        w = wp.om_weight(len(cells))
        if self.spent() + w > self.total_cap:
            raise Stop(f"Open-Meteo total cap {self.total_cap:.0f} would be passed ({self.spent():.1f} spent)")
        self._wait_for_day(w)
        if self._last is not None:
            wait = self.pause_s - (time.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
        lat = ",".join(c.split("_")[0] for c in cells)
        lon = ",".join(c.split("_")[1] for c in cells)
        params = {"latitude": lat, "longitude": lon, "start_date": f"{year}-{wp.AIR_FROM}",
                  "end_date": f"{year}-{wp.AIR_TO}", "daily": "temperature_2m_mean", "timezone": "Europe/London"}
        if self.model:
            params["models"] = self.model
        url = OM_URL + "?" + urlencode(params)
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname != OM_HOST:
            raise Stop(f"refused: {url}")
        try:
            r = self.http.get(url)
        except httpx.HTTPError as e:
            self.log.add("ERR", 0, 0, url)
            raise Stop(f"Open-Meteo: {type(e).__name__}: stopping") from e
        finally:
            self._last = time.monotonic()
        # Counted by Open-Meteo whatever the status once it answers; logged at the request's weight.
        self.log.add(str(r.status_code), len(r.content), w if r.status_code == 200 else 0, url)
        if r.status_code != 200:
            raise Stop(f"Open-Meteo answered {r.status_code}: {r.text[:200]!r}: stopping")
        try:
            body = r.json()
        except ValueError as e:
            raise Stop("Open-Meteo body is not JSON: stopping") from e
        ans = body if isinstance(body, list) else [body]
        if len(ans) != len(cells):
            raise Stop(f"Open-Meteo returned {len(ans)} locations for {len(cells)}: stopping")
        for a in ans:
            if "daily" not in a or "temperature_2m_mean" not in a["daily"]:
                raise Stop("Open-Meteo answer has no daily temperature_2m_mean: stopping")
        f.write_text(json.dumps({"year": year, "cells": cells, "model": self.model, "answer": ans}))
        return ans


def fetch_open_meteo(client: OMClient, plan: dict) -> dict:
    n = 0
    for year, cells in sorted(plan["seasons"].items(), key=lambda kv: int(kv[0])):
        for i in range(0, len(cells), wp.OM_BATCH):
            client.batch(int(year), cells[i:i + wp.OM_BATCH])
            n += 1
    return {"batches": n, "spent": client.spent()}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ea", "open_meteo"])
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--default-model", action="store_true",
                    help="the statement's one fallback: ask without models= if era5_land lacks the variable")
    a = ap.parse_args(argv)
    if a.what == "ea":
        c = EAClient(a.cache, a.fetch)
        print(json.dumps(fetch_ea(c)), "requests in log:", c.n, "bytes:", c.bytes, flush=True)
    else:
        if (o := other_open_meteo_jobs()):
            print("another Open-Meteo job runs:", o, flush=True)
        plan = json.loads(a.plan.read_text())
        if plan.get("over_cap"):
            raise Stop("plan is over the cap")
        c = OMClient(a.cache, a.fetch, model=None if a.default_model else OM_MODEL)
        print(json.dumps(fetch_open_meteo(c, plan)), flush=True)


if __name__ == "__main__":
    main()
