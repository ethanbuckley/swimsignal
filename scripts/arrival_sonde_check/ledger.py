"""docs/ARRIVAL-TIME-SONDE-CHECK-2026-11.md, section 2: every EA request, capped and written to a ledger.

At most CAP requests in total, retries included. One in flight, at least PACE_S after the previous one ends. A 403,
429 or 5xx is retried once after RETRY_S and counts twice. The ledger is one JSON line per request: n, url, params,
status, bytes, start and end (UTC). The count is read back from the file, so the cap holds across runs.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

BASE = "https://environment.data.gov.uk/hydrology"
CAP = 100
PACE_S = 1.5
RETRY_S = 10.0
UA = {"User-Agent": "research-script/1.0"}
LEDGER = Path(__file__).resolve().parents[2] / "docs" / "ARRIVAL-TIME-SONDE-CHECK-2026-11-ledger.jsonl"


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Ledger:
    def __init__(self, path: Path = LEDGER, cap: int = CAP, pace_s: float = PACE_S, get=None, sleep=time.sleep,
                 clock=time.time):
        self.path, self.cap, self.pace_s = Path(path), cap, pace_s
        self.n = len(self.path.read_text().splitlines()) if self.path.exists() else 0
        self.last_end = None
        self.get = get
        self.sleep, self.clock = sleep, clock

    def _get(self, url: str, params: dict):
        if self.get is not None:
            return self.get(url, params)
        import httpx
        return httpx.get(url, params=params, headers=UA, timeout=180)

    def left(self) -> int:
        return self.cap - self.n

    def request(self, url: str, params: dict):
        """The response, or SystemExit at the cap. Raises for a status that is still bad after the one retry."""
        r = None
        for attempt in range(2):
            if self.n >= self.cap:
                raise SystemExit(f"request cap {self.cap} reached; stopped")
            if self.last_end is not None:
                wait = self.pace_s - (self.clock() - self.last_end)
                if wait > 0:
                    self.sleep(wait)
            t0 = self.clock()
            try:
                r = self._get(url, params)
                status, size = r.status_code, len(r.content)
            except Exception as e:  # noqa: BLE001 - a dropped connection is a request made: it counts
                r, status, size = None, f"error: {type(e).__name__}", 0
            self.last_end = self.clock()
            self.n += 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a") as f:
                f.write(json.dumps({"n": self.n, "url": url, "params": params, "status": status, "bytes": size,
                                    "start": _iso(t0), "end": _iso(self.last_end)}) + "\n")
            if r is not None and r.status_code < 400:
                return r
            retry = r is None or r.status_code in (403, 429) or r.status_code >= 500
            if attempt == 0 and retry:
                self.sleep(RETRY_S)
                continue
            break
        if r is None:
            raise RuntimeError(f"no answer from {url}")
        r.raise_for_status()
        return r
