"""The two small capped fetches of docs/LAKE-TEMPERATURE-TEST-2026-10.md. They reuse the clients of the first test
(scripts/water_temperature_model_eval/wt_fetch.py: POST to the EA archive, dateTo exclusive, a 204 as an empty page,
network errors retried after 30 s, 2 min and 5 min, an answer of any status never retried).

    python -I lt_fetch.py ea2026     --cache <private>/water-temperature/ea-2026 [--fetch]
    python -I lt_fetch.py open_meteo --cache <private>/water-temperature/open-meteo-2026 --plan <plan.json> [--fetch]

ea2026: determinand 0076, fresh water (2AZZ, 2GZZ), one query a calendar month, May to September 2026, paged by 2,500.
Caps: at most 40 requests, 12 pages a month, 200 MB; one in flight, 1.5 s apart; environment.data.gov.uk only.
open_meteo: ERA5-Land daily mean air, 1 April to 30 September 2026, for the lake cells in plan.json, 25 cells a request.
Caps: at most 600 weighted calls in all; the first test's day (9,500) and rolling-hour (4,700) caps, counted over
this fetch's own log plus the first test's log (one Mac, one quota); 25 s apart; archive-api.open-meteo.com only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "water_temperature_model_eval"))
sys.path.insert(0, str(HERE))
import wt_fetch as wf  # noqa: E402
import wt_protocol as wp  # noqa: E402

EA_YEAR = 2026
EA_MAX_REQUESTS = 40
EA_MAX_BYTES = 200 * 1024 * 1024
OM_YEAR = 2026
OM_CAP = 600.0
FIRST_TEST_OM_LOG = Path.home() / "Documents/GitHub/swimsignal-private/water-temperature/open-meteo/requests.log"


def fetch_ea_2026(client: wf.EAClient) -> dict:
    """Fresh water, May to September 2026, each month paged until a short page."""
    pages = rows = 0
    for date_from, date_to in wf.month_ranges(years=(EA_YEAR,)):
        for k in range(wf.EA_MAX_PAGES + 1):
            if k == wf.EA_MAX_PAGES:
                raise wf.Stop(f"fresh {date_from}: more than {wf.EA_MAX_PAGES} pages; paging not working")
            n = wf.data_rows(client.page("fresh", date_from, date_to, k * wf.PAGE))
            pages += 1
            rows += n
            if n < wf.PAGE:
                break
    return {"pages": pages, "rows": rows, "requests_in_log": client.n, "bytes": client.bytes}


class SharedDayOM(wf.OMClient):
    """The first test's client, with the day and rolling-hour caps counted over this log and the first test's log.
    The total cap counts this fetch only."""

    def __init__(self, *a, other_log: Path = FIRST_TEST_OM_LOG, **k):
        super().__init__(*a, **k)
        self.other = wf.Log(other_log)

    def _all(self) -> list[list[str]]:
        return self.log.lines() + self.other.lines()

    def spent(self, day: str | None = None) -> float:
        if day is None:
            return super().spent(None)
        return sum(float(x[3]) for x in self._all() if len(x) >= 4 and x[0][:10] == day)

    def spent_since(self, t0) -> float:
        return sum(float(x[3]) for x in self._all() if len(x) >= 4 and datetime.fromisoformat(x[0]) > t0)


def plan_weight(cells: list[str]) -> float:
    return sum(wp.om_weight(len(cells[i:i + wp.OM_BATCH])) for i in range(0, len(cells), wp.OM_BATCH))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ea2026", "open_meteo"])
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args(argv)
    if a.what == "ea2026":
        c = wf.EAClient(a.cache, a.fetch, max_requests=EA_MAX_REQUESTS, max_bytes=EA_MAX_BYTES)
        print(json.dumps(fetch_ea_2026(c)), flush=True)
        return
    cells = json.loads(a.plan.read_text())["cells"]
    if plan_weight(cells) > OM_CAP:
        raise wf.Stop(f"plan weight {plan_weight(cells):.1f} is over the cap {OM_CAP}")
    c = SharedDayOM(a.cache, a.fetch, total_cap=OM_CAP)
    for i in range(0, len(cells), wp.OM_BATCH):
        c.batch(OM_YEAR, cells[i:i + wp.OM_BATCH])
    print(json.dumps({"batches": -(-len(cells) // wp.OM_BATCH), "spent": c.spent()}), flush=True)


if __name__ == "__main__":
    main()
