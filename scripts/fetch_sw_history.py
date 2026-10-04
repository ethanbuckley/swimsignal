"""Write data/processed/sw_events.parquet (one row per event, the edm_events columns) and
data/processed/sw_events_yearly.parquet (per overflow and year: 12/24-hour spill count, events,
hours) from Scottish Water's two published overflow event workbooks. Scotland plan task S1
(docs/SCOTLAND-PLAN-2026-10.md); nothing here reaches the site. Off CI, run by hand:

    uv run python scripts/fetch_sw_history.py           # download once, parse, report
    uv run python scripts/fetch_sw_history.py --api     # also compare ids with the live API

The workbooks are cached in data/raw/scottish_water/ and not downloaded again unless --refresh.
On 4 Oct 2026 Scottish Water's website answered 403 to this script's request (and to curl),
while it served the same files to a browser. If the download fails, save the two files from
the "Published Overflow Data" page into data/raw/scottish_water/ under the names in
sw_history.FILES and run it again. --api fetches the near-real-time API once (it answered
plain requests) and caches it in the same folder.

Contains Scottish Water data licensed under the Open Government Licence v3.0.
"""

from __future__ import annotations

import argparse
import json
import logging

import httpx
import pandas as pd

from dipcast import config
from dipcast.ingest import sw_history
from dipcast.ingest.common import write_parquet

API = "https://api.scottishwater.co.uk/overflow-event-monitoring/v1/near-real-time"
API_CACHE = sw_history.RAW_DIR / "near_real_time.json"


def download(refresh: bool = False) -> dict[str, object]:
    sw_history.RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    with httpx.Client(headers=config.EA_HEADERS, follow_redirects=True, timeout=120) as c:
        for source, (name, size) in sw_history.FILES.items():
            path = sw_history.RAW_DIR / name
            if refresh or not path.exists():
                r = c.get(sw_history.BASE + name)
                if r.status_code != 200:
                    raise SystemExit(f"{name}: HTTP {r.status_code}. Save it from {sw_history.PAGE} "
                                     f"into {sw_history.RAW_DIR}/ and run again.")
                tmp = path.with_suffix(".part")
                tmp.write_bytes(r.content)
                tmp.replace(path)
            if path.stat().st_size != size:
                print(f"note: {name} is {path.stat().st_size:,} bytes, not {size:,}: a new version?")
            paths[source] = path
    return paths


def api_ids(refresh: bool = False) -> set[str]:
    if refresh or not API_CACHE.exists():
        r = httpx.get(API, headers=config.EA_HEADERS, timeout=60)
        r.raise_for_status()
        API_CACHE.write_bytes(r.content)
    return {row["ASSET_ID"] for row in json.loads(API_CACHE.read_text())["results"]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true", help="download the workbooks (and the API) again")
    ap.add_argument("--api", action="store_true", help="compare Asset IDs with the live API's")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    ev, yr, rows = sw_history.load(download(args.refresh))
    write_parquet(ev, config.PROCESSED / "sw_events.parquet")
    write_parquet(yr, config.PROCESSED / "sw_events_yearly.parquet")

    ids = api_ids(args.refresh) if args.api else None
    t = sw_history.report(ev, yr, rows, ids)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(t.to_string(index=False))
    for src, g in ev.groupby("source"):
        print(f"{src}: {g.site_id.nunique()} overflows, {len(g)} events, "
              f"{g.event_start.min():%Y-%m-%d} to {g.event_start.max():%Y-%m-%d}")
    if ids is not None:
        have = set(ev.site_id)
        pub = set(ev.asset_id_published)
        print(f"API: {len(ids)} assets. Overflows with events: {len(have)}, of which {len(have & ids)} "
              f"({len(have & ids) / len(have):.1%}) are API ASSET_IDs; as published, "
              f"{len(pub & ids)} of {len(pub)} ({len(pub & ids) / len(pub):.1%}). "
              f"API assets with history: {len(ids & have)} ({len(ids & have) / len(ids):.1%}).")
    print(sw_history.CREDIT)


if __name__ == "__main__":
    main()
