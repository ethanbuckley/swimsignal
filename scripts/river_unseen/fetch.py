"""Fetch the Environment Agency's river E. coli results away from bathing waters, with a request ledger
(docs/RIVER-UNSEEN-PROTOCOL-2026-11.md). Off CI, by hand:

    python scripts/river_unseen/fetch.py <out dir> [first year] [last year]

Determinand 2348 (E. coli, confirmed, membrane filtration) at sampling points of type F6 (freshwater, rivers), one
calendar year a query (the archive's limit across points), CSV pages of 2,500 rows (its page limit). Years run from
the newest of the held-out span down, then the later years: 2022 to 2012, then 2023 to 2026.

Resumable: a saved page is never asked for again. A refusal (HTTP 401, 403 or 429) stops the run and is written to
the ledger; it is not retried. A server error (502, 503, 504) or a dropped connection is tried again after RETRY_S,
and each try counts against the cap. An empty year answers 204.

<out dir>/ledger.jsonl has one line per request sent: time, year, skip, HTTP status, bytes, rows, the body's SHA-256
and the seconds it took. <out dir>/raw/ keeps each page. The pages hold lab results: this script counts their rows
and reads no value. Data: Environment Agency, Open Government Licence v3.0."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
URL = "https://environment.data.gov.uk/water-quality/data/observation"
DETERMINAND, POINT_TYPE, PAGE = "2348", "F6", 2500
HELD_OUT, LATER = range(2022, 2011, -1), range(2023, 2027)
# Sizing, written before the run (15 Nov 2026). Measured that day: 2019 and 2024 each fill one page of 2,500, so a
# year holds at least 2,500 rows; the true count is not known. At 2,500 to 20,000 rows a year that is 2 to 9
# requests a year, 30 to 135 for 15 years, about 1 MB a page. Cap 150 requests and 200 MB. At 4 s between requests
# and about 10 s an answer: at most 35 minutes.
CAP_REQUESTS, CAP_BYTES, PACE_S = 150, 200 * 2**20, 4.0
RETRY_S = (30, 90)
REFUSALS = (401, 403, 429)


class Stopped(RuntimeError):
    """A cap reached or a refusal: nothing more is asked in this run."""


def rows_in(body: bytes) -> int:
    """Data rows in a CSV page: its records less the header (a quoted field may hold a line break)."""
    return max(sum(1 for _ in csv.reader(io.StringIO(body.decode("utf-8", "replace")))) - 1, 0) if body else 0


def run(out: Path, years: list[int], user_agent: str) -> None:
    raw, ledger = out / "raw", out / "ledger.jsonl"
    raw.mkdir(parents=True, exist_ok=True)
    past = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    sent, got = len(past), sum(r.get("bytes") or 0 for r in past)
    last = 0.0
    with httpx.Client(timeout=180, headers={"User-Agent": user_agent, "Accept": "text/csv"}) as client:
        for year in years:
            skip = 0
            while True:
                page = raw / f"ecoli_F6_{year}_s{skip:06d}.csv"
                if page.exists():
                    n = rows_in(page.read_bytes())
                else:
                    for wait in (*RETRY_S, None):
                        if sent >= CAP_REQUESTS or got >= CAP_BYTES:
                            raise Stopped(f"cap reached after {sent} requests and {got} bytes, at {year} skip {skip}")
                        time.sleep(max(0.0, PACE_S - (time.monotonic() - last)))
                        params = {"determinand": DETERMINAND, "samplingPointType": POINT_TYPE,
                                  "dateFrom": f"{year}-01-01", "dateTo": f"{year}-12-31", "limit": PAGE, "skip": skip}
                        t0, sent = time.monotonic(), sent + 1
                        row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "n": sent, "year": year,
                               "skip": skip, "url": URL, "params": params}
                        try:
                            r = client.post(URL, params=params)
                            body, status = r.content, r.status_code
                        except httpx.TransportError as e:
                            body, status = b"", None
                            row["error"] = type(e).__name__
                        last = time.monotonic()
                        got += len(body)
                        row.update(status=status, bytes=len(body), rows=rows_in(body) if status == 200 else 0,
                                   sha256=hashlib.sha256(body).hexdigest(), seconds=round(last - t0, 2))
                        if status not in (200, 204):
                            row["body_start"] = body[:200].decode("utf-8", "replace")
                        with ledger.open("a") as f:
                            f.write(json.dumps(row, sort_keys=True) + "\n")
                        if status in (200, 204):
                            page.write_bytes(body)
                            break
                        if status in REFUSALS:
                            raise Stopped(f"refused with HTTP {status} at request {sent} ({year} skip {skip})")
                        if status not in (None, 502, 503, 504):
                            raise RuntimeError(f"{year} skip {skip}: HTTP {status}: {row['body_start']}")
                        if wait is None:
                            raise RuntimeError(f"{year} skip {skip}: no answer after {len(RETRY_S)} retries")
                        print(f"{year} skip {skip}: {status or row['error']}; again in {wait} s", flush=True)
                        time.sleep(wait)
                    n = row["rows"]
                    print(f"{year} skip {skip}: {n} rows ({sent} requests, {got / 2**20:.1f} MiB)", flush=True)
                if n < PAGE:
                    break
                skip += PAGE


if __name__ == "__main__":
    sys.path.insert(0, str(REPO / "src"))
    from dipcast import config   # only for the User-Agent that names the project to the EA

    lo, hi = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (2012, 2026)
    wanted = [y for y in (*HELD_OUT, *LATER) if lo <= y <= hi]
    try:
        run(Path(sys.argv[1]), wanted, config.USER_AGENT)
    except Stopped as e:
        print(f"stopped: {e}")
        sys.exit(2)
