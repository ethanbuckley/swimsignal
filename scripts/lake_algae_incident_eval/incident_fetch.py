"""docs/LAKE-ALGAE-INCIDENT-TEST-2026-10.md, "The fetch": the EA incident history of each test site, once.

    incident_fetch.py <out dir> <features file> <committed features SHA-256>

Refuses unless the features file hashes to the committed value, and refuses if <out dir>/incidents.json exists (one
fetch). Then one request per site, in sorted order, for the 14 sites past #377's size rule:
    https://environment.data.gov.uk/doc/bathing-water-quality/pollution-incident.json
        ?bathingWater.eubwidNotation=<id>&_pageSize=200

The caps, written here before any request:
* One request at a time, at least PAUSE_S between requests, a TIMEOUT_S timeout on each.
* At most MAX_REQUESTS requests and MAX_BYTES bytes in all, MAX_BYTES_PER_RESPONSE in one response.
* Only HOST, over https. No Authorization header, cookie or key is ever sent.
* Stop at once on HTTP 429, any 5xx, or any status other than 200. Nothing is retried. A stopped fetch saves no
  bodies (only the ledger, one line per request: time, URL, status, bytes); it is reported, and a second attempt
  needs Ethan's yes.

On success it writes incidents.json (the fetch time and day, and each response's site, URL, status, bytes and parsed
body) and incidents.sha256. The page-completeness stop rules are checked again at scoring.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import algae_incidents as inc

HOST = "environment.data.gov.uk"
MAX_REQUESTS = 40
MAX_BYTES = 20 * 1024**2
MAX_BYTES_PER_RESPONSE = 5 * 1024**2
PAUSE_S = 1.0
TIMEOUT_S = 60.0
CHUNK = 64 * 1024
USER_AGENT = "swimsignal-lake-algae-incident-eval/1"

ROOT = Path(__file__).resolve().parents[2]
SIZES = ROOT / "docs" / "LAKE-ALGAE-SATELLITE-TEST-2026-10-sizes.json"


class Stop(RuntimeError):
    """A cap, a status or a refused request: the fetch stops, nothing is retried."""


class Client:
    def __init__(self, ledger: Path | None = None, client=None, sleep=time.sleep, clock=time.monotonic):
        if client is None:
            import httpx
            client = httpx.Client(timeout=TIMEOUT_S, follow_redirects=False, headers={"User-Agent": USER_AGENT})
        self.client, self.sleep, self.clock, self.ledger = client, sleep, clock, ledger
        self.requests = 0
        self.bytes = 0
        self._last = None

    def get(self, url: str, headers: dict | None = None) -> tuple[int, bytes]:
        from urllib.parse import urlsplit
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname != HOST:
            raise Stop(f"host not allowed: {u.scheme}://{u.hostname}")
        bad = {k.lower() for k in (headers or {})} & {"authorization", "cookie", "x-api-key"}
        if bad:
            raise Stop(f"credentials refused: {sorted(bad)}")
        if self.requests + 1 > MAX_REQUESTS:
            raise Stop(f"request cap ({MAX_REQUESTS})")
        if self.bytes >= MAX_BYTES:
            raise Stop(f"byte cap ({MAX_BYTES})")
        if self._last is not None:
            wait = PAUSE_S - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self.requests += 1
        body = bytearray()
        status = None
        try:
            with self.client.stream("GET", url, headers=headers) as r:
                status = r.status_code
                if status == 429 or status >= 500:
                    raise Stop(f"HTTP {status} from {url}: stopped, not retried")
                if status != 200:
                    raise Stop(f"HTTP {status} from {url}: stopped")
                for chunk in r.iter_bytes(CHUNK):
                    body += chunk
                    if len(body) > MAX_BYTES_PER_RESPONSE:
                        raise Stop(f"response over {MAX_BYTES_PER_RESPONSE} bytes: {url}")
                    if self.bytes + len(body) > MAX_BYTES:
                        raise Stop(f"byte cap ({MAX_BYTES})")
        finally:
            self._last = self.clock()
            self.bytes += len(body)
            if self.ledger is not None:
                self.ledger.parent.mkdir(parents=True, exist_ok=True)
                with self.ledger.open("a") as f:
                    f.write(json.dumps({"t": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "url": url,
                                        "status": status, "bytes": len(body)}) + "\n")
        return status, bytes(body)


def test_sites(sizes_path: Path = SIZES) -> list[str]:
    sizes = json.loads(Path(sizes_path).read_text())
    return sorted(k for k, v in sizes.items() if v["in_test"])


def fetch(out: Path, features: Path, features_sha: str, client: Client | None = None,
          sites: list[str] | None = None) -> str:
    if features_sha.strip().lower() != inc.FEATURES_SHA256:
        raise inc.StopRule("the features hash given is not the one committed in #377")
    inc.check_hash(features, features_sha)
    target = out / "incidents.json"
    if target.exists():
        raise inc.StopRule("incidents.json exists: the histories are fetched once")
    sites = sites if sites is not None else test_sites()
    client = client or Client(ledger=out / "ledger-incidents.jsonl")
    started = datetime.now(UTC)
    responses = []
    for s in sites:
        url = inc.HISTORY_URL.format(s, inc.PAGE_SIZE)
        status, body = client.get(url)
        responses.append({"bw_id": s, "url": url, "status": status, "bytes": len(body), "body": json.loads(body)})
    saved = {"fetched_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"), "fetch_day": started.date().isoformat(),
             "requests": client.requests, "bytes": client.bytes, "responses": responses}
    out.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(saved, sort_keys=True, indent=1))
    h = inc.sha256(target)
    (out / "incidents.sha256").write_text(h + "\n")
    print(f"incidents fetched: {len(responses)} sites, {client.requests} requests, {client.bytes} bytes; "
          f"SHA-256 {h}")
    return h


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    fetch(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
