"""docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md, "Download caps": every public request this harness makes goes through
Capped, which holds the caps below. They were written into the statement and into this file before any request was
made through it.

* One request at a time, a pause between requests, a timeout on each.
* A cap on requests and on bytes per run, and a cap over all runs of the coverage prototype together (kept in a
  ledger file, one JSON line per request).
* Stop at once on HTTP 429 or any 5xx, and on any other status that is not 200 or 206. Nothing is retried.
* Only the hosts listed. Never an Authorization header, a cookie or a token: no account is used.

Amendment A1 (26 October 2026, Ethan, during stage 1; recorded in the statement's run log): range reads from the two
public AWS buckets (PARALLEL_HOSTS) take no pause and may run WORKERS at a time; the STAC API and the CDSE catalogue
keep one request at a time with the pause. Counters, caps and the ledger are kept under one lock, so every request is
still counted. When one read stops the run, reads already in flight (at most WORKERS - 1) still finish and are
counted; nothing new starts, and nothing is retried.

A response body is read in chunks and stops when it would pass the per-response cap or the run's byte cap, so a cap
is never exceeded by more than one chunk.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

MAX_REQUESTS_PER_RUN = 300
MAX_BYTES_PER_RUN = 100 * 1024**2
MAX_REQUESTS_TOTAL = 900          # the coverage prototype, all runs together (ledger)
MAX_BYTES_TOTAL = 300 * 1024**2
MAX_BYTES_PER_RESPONSE = 32 * 1024**2
# Stage 1 (stage1.py), set after the coverage prototype and before any stage 1 request: its own ledger, larger per-run
# caps, the same pause, hosts and stop rules. Estimate from the prototype's counts: about 27,000 requests and 2 GB.
STAGE1_MAX_REQUESTS_PER_RUN = 4000
STAGE1_MAX_BYTES_PER_RUN = 500 * 1024**2
STAGE1_MAX_REQUESTS_TOTAL = 40000
STAGE1_MAX_BYTES_TOTAL = 4 * 1024**3
PAUSE_S = 1.0
TIMEOUT_S = 60.0
CHUNK = 64 * 1024
HOSTS = (
    "earth-search.aws.element84.com",                     # Earth Search STAC API (metadata)
    "e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com",   # C1 L2A COGs, public bucket
    "sentinel-cogs.s3.us-west-2.amazonaws.com",
    "catalogue.dataspace.copernicus.eu",                  # CDSE OData catalogue (search only, no download)
    "stac.dataspace.copernicus.eu",                       # CDSE STAC (search only)
)
# A1: the COG buckets, built for parallel range reads; no pause there, WORKERS reads at a time (stage1.py).
PARALLEL_HOSTS = frozenset(HOSTS[1:3])
WORKERS = 16
USER_AGENT = "swimsignal-lake-algae-sat-eval/1"   # the CDSE firewall refused one with brackets and a URL (HTTP 403)


class CapReached(RuntimeError):
    """A cap would be passed: the run stops, nothing more is fetched."""


class Stop(RuntimeError):
    """HTTP 429, a 5xx or another unexpected status: the run stops, nothing is retried."""


class Capped:
    def __init__(self, ledger: Path | None = None, client=None, sleep=time.sleep, *,
                 max_requests: int = MAX_REQUESTS_PER_RUN, max_bytes: int = MAX_BYTES_PER_RUN,
                 max_requests_total: int = MAX_REQUESTS_TOTAL, max_bytes_total: int = MAX_BYTES_TOTAL):
        if client is None:
            import httpx
            client = httpx.Client(timeout=TIMEOUT_S, follow_redirects=False, headers={"User-Agent": USER_AGENT})
        self.client, self.sleep, self.ledger = client, sleep, ledger
        self.max_requests, self.max_bytes = max_requests, max_bytes
        self.max_requests_total, self.max_bytes_total = max_requests_total, max_bytes_total
        self.requests = 0
        self.bytes = 0
        self._last = None
        self._lock = threading.Lock()
        self.prior_requests, self.prior_bytes = self._prior()

    def _prior(self) -> tuple[int, int]:
        if self.ledger is None or not self.ledger.exists():
            return 0, 0
        rows = [json.loads(line) for line in self.ledger.read_text().splitlines() if line.strip()]
        return len(rows), sum(int(r.get("bytes", 0)) for r in rows)

    def _check_url(self, url: str, headers: dict | None) -> None:
        from urllib.parse import urlsplit
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname not in HOSTS:
            raise CapReached(f"host not allowed: {u.scheme}://{u.hostname}")
        bad = {k.lower() for k in (headers or {})} & {"authorization", "cookie", "x-api-key"}
        if bad:
            raise CapReached(f"credentials refused: {sorted(bad)}")

    def request(self, method: str, url: str, *, headers: dict | None = None, json_body=None) -> tuple[int, bytes]:
        from urllib.parse import urlsplit
        self._check_url(url, headers)
        paced = urlsplit(url).hostname not in PARALLEL_HOSTS
        with self._lock:
            if self.requests + 1 > self.max_requests:
                raise CapReached(f"request cap per run ({self.max_requests})")
            if self.prior_requests + self.requests + 1 > self.max_requests_total:
                raise CapReached(f"request cap over all runs ({self.max_requests_total})")
            if paced and self._last is not None:
                wait = PAUSE_S - (time.monotonic() - self._last)
                if wait > 0:
                    self.sleep(wait)
            self.requests += 1
        body = bytearray()
        status = None
        try:
            with self.client.stream(method, url, headers=headers, json=json_body) as r:
                status = r.status_code
                if status == 429 or status >= 500:
                    raise Stop(f"HTTP {status} from {url}: stopped, not retried")
                if status not in (200, 206):
                    raise Stop(f"HTTP {status} from {url}: stopped")
                for chunk in r.iter_bytes(CHUNK):
                    body += chunk
                    if len(body) > MAX_BYTES_PER_RESPONSE:
                        raise CapReached(f"response over {MAX_BYTES_PER_RESPONSE} bytes: {url}")
                    if self.bytes + len(body) > self.max_bytes:
                        raise CapReached(f"byte cap per run ({self.max_bytes})")
                    if self.prior_bytes + self.bytes + len(body) > self.max_bytes_total:
                        raise CapReached(f"byte cap over all runs ({self.max_bytes_total})")
        finally:
            with self._lock:
                if paced:
                    self._last = time.monotonic()
                self.bytes += len(body)
                if self.ledger is not None:
                    self.ledger.parent.mkdir(parents=True, exist_ok=True)
                    with self.ledger.open("a") as f:
                        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "method": method,
                                            "url": url, "status": status, "bytes": len(body)}) + "\n")
        return status, bytes(body)

    def get_json(self, url: str):
        return json.loads(self.request("GET", url)[1])

    def post_json(self, url: str, body: dict):
        return json.loads(self.request("POST", url, json_body=body)[1])

    def get_range(self, url: str, start: int, end: int) -> bytes:
        """Bytes start to end inclusive. A server that ignores Range and sends the whole file is stopped by the
        per-response cap."""
        status, b = self.request("GET", url, headers={"Range": f"bytes={start}-{end}"})
        if status == 200 and len(b) > end - start + 1:
            b = b[start:end + 1]
        return b

    def summary(self) -> dict:
        return {"requests": self.requests, "bytes": self.bytes, "requests_all_runs": self.prior_requests + self.requests,
                "bytes_all_runs": self.prior_bytes + self.bytes}
