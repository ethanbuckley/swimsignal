"""Fetch what the coastal explorer and baselines read from the Environment Agency, with a request ledger
(docs/COASTAL-BASELINES-2026-11.md). Off CI, by hand, from a machine the EA's services answer:

    uv run python scripts/coastal_baselines/fetch.py <out dir> catalogue ecoli prf-probe prf enterococci

Stages, each resumable (a saved response is never asked for again):

  catalogue    the bathing-water list with each site's sampling point position (3 pages), bathing-water service
  ecoli        E. coli (determinand 2348), statutory samples (purpose MS), 2022 to 2026, at the archive points in
               data/raw/coastal_wqa_points.json, one calendar year and 25 points a request, Water Quality Archive
  prf-probe    one day of the EA's risk predictions from 2022, to see whether the history is open
  prf          every bathing-season day's risk predictions, 2026 back to 2022, one request a day
  enterococci  intestinal enterococci (determinand 3723), as `ecoli`

Each service has its own cap and pace (SERVICES). A refusal (HTTP 401, 403 or 429) stops that service for the
rest of the run and is written to the ledger: it is not retried and not routed round. A server error (502, 503,
504) or a dropped connection is tried again after RETRY_S, and each try counts against the cap.

<out dir>/ledger.jsonl has one line per request sent: time, service, stage, what was asked, the HTTP status, the
bytes and items that came back, the body's SHA-256 and the seconds it took. <out dir>/raw/ keeps each response.
Data: Environment Agency, Open Government Licence v3.0.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
WQA = "https://environment.data.gov.uk/water-quality"
BWQ_CATALOGUE = "https://environment.data.gov.uk/doc/bathing-water.json"
BWQ_PRF = "https://environment.data.gov.uk/doc/bathing-water-quality/stp-risk-prediction.json"
DETERMINANDS = {"ecoli": "2348", "enterococci": "3723"}
YEARS = (2022, 2023, 2024, 2025, 2026)
SEASON = ((5, 15), (9, 30))      # the EA's risk predictions run for the bathing season
POINTS_A_REQUEST = 25
PAGE = 250                       # the archive's page limit for JSON-LD
# Sizing, written before the run. Archive: 407 points are 17 requests of 25 a year; about 6,600 results a year is
# about 390 a request, so two pages each, some three: about 40 requests a year, 200 for five years, per determinand.
# At 3 s between requests and about 2 s an answer that is about 17 minutes a determinand. Bathing-water service:
# 3 catalogue pages, 1 probe and 139 season days x 5 years = 695 days, 699 requests. Its gateway refused a home
# connection after 55 requests 1.3 s apart and after 62 requests 2.3 s apart (scripts/compare_prf.py, 3 Oct 2026),
# so 10 s between requests here: about 12 s a request, 2.3 hours.
SERVICES = {"wqa": {"cap": 430, "pace_s": 3.0}, "bwq": {"cap": 730, "pace_s": 10.0}}
RETRY_S = (30, 90)
REFUSALS = (401, 403, 429)


class Stopped(RuntimeError):
    """A cap reached or a refusal: nothing more is asked of that service in this run."""


class Fetcher:
    def __init__(self, out: Path, user_agent: str):
        self.out, self.raw = out, out / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.ledger = out / "ledger.jsonl"
        self.sent = {s: 0 for s in SERVICES}
        if self.ledger.exists():   # a resumed run keeps counting against the same caps
            for line in self.ledger.read_text().splitlines():
                self.sent[json.loads(line)["service"]] += 1
        self.stopped: dict[str, str] = {}
        self.last = {s: 0.0 for s in SERVICES}
        self.client = httpx.Client(timeout=120, headers={"User-Agent": user_agent})

    def _log(self, **row) -> None:
        with self.ledger.open("a") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    def get(self, service: str, stage: str, key: str, method: str, url: str, params: dict, headers: dict | None = None,
            count=lambda body: None):
        """The JSON body for `key`, from <out>/raw/<key>.json when held, else from one paced, ledgered request."""
        f = self.raw / f"{key}.json"
        if f.exists():
            return json.loads(f.read_bytes())
        if service in self.stopped:
            raise Stopped(self.stopped[service])
        for wait in (*RETRY_S, None):
            if self.sent[service] >= SERVICES[service]["cap"]:
                self.stopped[service] = f"cap of {SERVICES[service]['cap']} requests reached"
                raise Stopped(self.stopped[service])
            pause = SERVICES[service]["pace_s"] - (time.monotonic() - self.last[service])
            if pause > 0:
                time.sleep(pause)
            t0 = time.monotonic()
            self.sent[service] += 1
            row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "service": service, "stage": stage, "key": key,
                   "method": method, "url": url, "params": params, "n": self.sent[service]}
            try:
                r = self.client.request(method, url, params=params, headers=headers)
                body = r.content
                row.update(status=r.status_code, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            except httpx.TransportError as e:
                r, body = None, b""
                row.update(status=None, error=type(e).__name__)
            self.last[service] = time.monotonic()
            row["seconds"] = round(self.last[service] - t0, 2)
            if r is not None and r.status_code == 200:
                data = json.loads(body)
                row["items"] = count(data)
                self._log(**row)
                f.write_bytes(body)
                return data
            if r is not None and r.status_code in REFUSALS:
                row["refusal"] = True
                row["body_start"] = body[:300].decode("utf-8", "replace")
                self._log(**row)
                self.stopped[service] = f"refused with HTTP {r.status_code} at request {self.sent[service]} ({key})"
                raise Stopped(self.stopped[service])
            if r is not None and r.status_code not in (502, 503, 504):
                row["body_start"] = body[:300].decode("utf-8", "replace")
                self._log(**row)
                raise RuntimeError(f"{key}: HTTP {r.status_code}")
            self._log(**row)
            if wait is None:
                raise RuntimeError(f"{key}: no answer after {len(RETRY_S)} retries")
            print(f"{key}: {row.get('status') or row.get('error')}; again in {wait} s", flush=True)
            time.sleep(wait)
        raise AssertionError("unreachable")


def catalogue(fx: Fetcher) -> None:
    for page in range(3):
        d = fx.get("bwq", "catalogue", f"catalogue_p{page}", "GET", BWQ_CATALOGUE, {"_pageSize": 500, "_page": page},
                   count=lambda b: len(b["result"]["items"]))
        if len(d["result"]["items"]) < 500:
            break


def observations(fx: Fetcher, name: str) -> None:
    mapping = json.loads((REPO / "data" / "raw" / "coastal_wqa_points.json").read_text())
    points = sorted({v["point"] for v in mapping["points"].values() if isinstance(v, dict) and v.get("point")})
    for year in reversed(YEARS):
        for i in range(0, len(points), POINTS_A_REQUEST):
            skip = 0
            while True:
                params = {"determinand": DETERMINANDS[name], "dateFrom": f"{year}-01-01", "dateTo": f"{year}-12-31",
                          "limit": PAGE, "samplingPurpose": "MS", "skip": skip,
                          "pointNotation": ",".join(points[i:i + POINTS_A_REQUEST])}
                d = fx.get("wqa", name, f"{name}_{year}_b{i // POINTS_A_REQUEST:02d}_s{skip}", "POST",
                           f"{WQA}/data/observation", params, headers={"Accept": "application/ld+json"},
                           count=lambda b: len(b.get("member") or []))
                if len(d.get("member") or []) < PAGE:
                    break
                skip += PAGE
        print(f"{name} {year}: done, {fx.sent['wqa']} archive requests so far", flush=True)


def prf_day(fx: Fetcher, day: date, stage: str = "prf") -> list:
    items, page = [], 0
    while True:
        d = fx.get("bwq", stage, f"prf_{day.isoformat()}" + (f"_p{page}" if page else ""), "GET", BWQ_PRF,
                   {"predictedOn": day.isoformat(), "_pageSize": 500, "_page": page},
                   count=lambda b: len(b["result"].get("items", [])))
        got = d["result"].get("items", [])
        items += got
        if len(got) < 500:
            return items
        page += 1


def prf(fx: Fetcher) -> None:
    for year in reversed(YEARS):
        day, end = date(year, *SEASON[0]), date(year, *SEASON[1])
        n = 0
        while day <= end:
            n += len(prf_day(fx, day))
            day += timedelta(days=1)
        print(f"prf {year}: {n} predictions, {fx.sent['bwq']} bathing-water requests so far", flush=True)


def main(out: Path, stages: list[str]) -> None:
    sys.path.insert(0, str(REPO / "src"))
    from dipcast import config   # only for the User-Agent that names the project to the EA
    fx = Fetcher(out, config.USER_AGENT)
    for stage in stages:
        try:
            if stage == "catalogue":
                catalogue(fx)
            elif stage in DETERMINANDS:
                observations(fx, stage)
            elif stage == "prf-probe":
                print(f"prf-probe: {len(prf_day(fx, date(2022, 7, 15), 'prf-probe'))} predictions for 2022-07-15", flush=True)
            elif stage == "prf":
                prf(fx)
            else:
                raise SystemExit(f"unknown stage {stage}")
        except Stopped as e:
            print(f"{stage}: STOPPED, {e}", flush=True)
        print(f"{stage}: finished; requests sent so far {fx.sent}", flush=True)
    (out / "fetch_summary.json").write_text(json.dumps({"sent": fx.sent, "stopped": fx.stopped, "caps": SERVICES,
                                                        "finished_at": datetime.now(UTC).isoformat(timespec="seconds")},
                                                       indent=1) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), sys.argv[2:])
