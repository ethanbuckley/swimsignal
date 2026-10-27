"""docs/SONDE-SIGNAL-TEST-2026-10.md, scoring-time fetch. NOT RUN until Ethan approves the test.

    fetch.py stations <out dir>                     two station listings (turbidity, ammonium), frozen for the run
    fetch.py readings <matched.csv> <out dir>       readings for each matched (station, property, year)

`matched.csv` is relate.py's output with network_ok True and samples_covered > 0. One request per (measure, year):
1 April to 30 September of that year (the 30-day baseline before 1 May, and room for the placebo's shifts), _limit
100000 (about 17,600 rows at 15 minutes). One request in flight, at least PACE_S after the previous one ends; a
403, 429 or 5xx is retried once after RETRY_S and counts twice. The whole run stops at CAP requests. Every request
goes to <out dir>/ledger.jsonl. Readings are saved as they come, outside git, and never printed or summarised here.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import httpx

BASE = "https://environment.data.gov.uk/hydrology"
CAP = 40
PACE_S = 1.5
RETRY_S = 10.0
UA = {"User-Agent": "SwimSignal sonde-signal test (hello@swimsignal.co.uk)"}


class Ledger:
    def __init__(self, out: Path, cap: int = CAP, pace_s: float = PACE_S, get=None, sleep=time.sleep, clock=time.time):
        self.path, self.cap, self.pace_s = out / "ledger.jsonl", cap, pace_s
        self.n = len(self.path.read_text().splitlines()) if self.path.exists() else 0
        self.last_end = None
        self.get = get or (lambda url, params: httpx.get(url, params=params, headers=UA, timeout=120))
        self.sleep, self.clock = sleep, clock

    def request(self, url: str, params: dict):
        for attempt in range(2):
            if self.n >= self.cap:
                raise SystemExit(f"request cap {self.cap} reached; stopped")
            if self.last_end is not None:
                wait = self.pace_s - (self.clock() - self.last_end)
                if wait > 0:
                    self.sleep(wait)
            t0 = self.clock()
            r = self.get(url, params)
            self.last_end = self.clock()
            self.n += 1
            with open(self.path, "a") as f:
                f.write(json.dumps({"n": self.n, "url": url, "params": params, "status": r.status_code,
                                    "bytes": len(r.content), "t_start": t0, "t_end": self.last_end}) + "\n")
            if r.status_code in (403, 429) or r.status_code >= 500:
                if attempt == 0:
                    self.sleep(RETRY_S)
                    continue
            r.raise_for_status()
            return r
        return None


def plan(matched_csv: str) -> list[tuple[str, str, int]]:
    """(measure id, property, year) to fetch: one per matched sonde, property and sample year, sorted."""
    from sondes import UNITS
    want = set()
    for r in csv.DictReader(open(matched_csv)):
        if r.get("network_ok") != "True" or not int(r.get("samples_covered") or 0):
            continue
        prop = r["property"]
        code = {"turbidity": "turb", "ammonium": "amm"}[prop]
        for y in json.loads(r.get("years") or "[]"):
            want.add((f"{r['station_id']}-{code}-i-subdaily-{UNITS[prop]}", prop, int(y)))
    return sorted(want)


def main(mode: str, *args: str) -> None:
    if mode == "stations":
        out = Path(args[0]); out.mkdir(parents=True, exist_ok=True)
        led = Ledger(out)
        for prop in ("turbidity", "ammonium"):
            r = led.request(f"{BASE}/id/stations.json", {"observedProperty": prop, "_limit": 10000})
            (out / f"stations_{prop}.json").write_bytes(r.content)
    elif mode == "readings":
        matched, out = args[0], Path(args[1]); out.mkdir(parents=True, exist_ok=True)
        todo = plan(matched)
        led = Ledger(out)
        if led.n + len(todo) > CAP:
            raise SystemExit(f"{len(todo)} requests planned and {led.n} made: over the cap of {CAP}; nothing fetched")
        for mid, prop, year in todo:
            f = out / f"{mid}_{year}.json"
            if f.exists():
                continue
            r = led.request(f"{BASE}/id/measures/{mid}/readings.json",
                            {"mineq-date": f"{year}-04-01", "maxeq-date": f"{year}-09-30", "_limit": 100000})
            f.write_bytes(r.content)
        print(f"{led.n} requests in the ledger")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(*sys.argv[1:])
