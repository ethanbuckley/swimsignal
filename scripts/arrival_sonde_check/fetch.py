"""docs/ARRIVAL-TIME-SONDE-CHECK-2026-11.md: the EA requests, through the ledger.

    fetch.py stations <out dir>                 the ammonium station listing (1 request)
    fetch.py readings <plan.csv> <out dir>      one request per row of the plan: station_id, measure, date_from, date_to

Readings come as CSV (dateTime, value, quality), saved outside git as <out dir>/<measure>.csv and never printed. If
the plan would pass the cap, nothing is fetched. A file already there is not fetched again.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from ledger import BASE, Ledger

READINGS_MAX = 90    # section 2: at most 90 readings requests
LIMIT = 100_000      # rows a request may return; two years at 15 minutes is about 70,000
BYTES_MAX = 1_200_000_000   # section 10: the fetch stops once the saved readings pass this


def main(mode: str, *args: str) -> None:
    led = Ledger()
    if mode == "stations":
        out = Path(args[0]); out.mkdir(parents=True, exist_ok=True)
        r = led.request(f"{BASE}/id/stations.json", {"observedProperty": "ammonium", "_limit": 10000})
        (out / "stations_ammonium.json").write_bytes(r.content)
    elif mode == "readings":
        plan, out = list(csv.DictReader(open(args[0]))), Path(args[1])
        out.mkdir(parents=True, exist_ok=True)
        todo = [p for p in plan if not (out / f"{p['measure']}.csv").exists()]
        if len(plan) > READINGS_MAX or len(todo) > led.left():
            raise SystemExit(f"{len(plan)} planned, {len(todo)} to fetch, {led.left()} requests left: nothing fetched")
        for p in todo:
            if sum(f.stat().st_size for f in out.glob("*.csv")) > BYTES_MAX:
                raise SystemExit("saved readings passed the byte cap; stopped")
            r = led.request(f"{BASE}/id/measures/{p['measure']}/readings.csv",
                            {"mineq-date": p["date_from"], "maxeq-date": p["date_to"], "_limit": LIMIT})
            (out / f"{p['measure']}.csv").write_bytes(r.content)
    else:
        raise SystemExit(__doc__)
    print(f"{led.n} requests in the ledger")


if __name__ == "__main__":
    main(*sys.argv[1:])
