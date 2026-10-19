"""Write one parquet of discharges per company, data/processed/stream_events_<company>.parquet (the
edm_events columns), from the event histories the companies publish as ArcGIS layers
(config.EDM_HISTORY_FEEDS): Northumbrian Water 2020-2024, Wessex Water 2020-2023 and South West Water
January 2025 to May 2026. Review task D3 (docs/REVIEW-2026-10-16.md); what they hold and how they agree
with the EA's files is in docs/EARLIER-SPILL-HISTORY-2026-10.md. Off CI, run by hand:

    uv run python scripts/import_stream_events.py [--refresh]

It checks every read against the layer: the rows fetched must equal the layer's own count and carry no
repeated object id, or it stops. Then it prints, per company and year, the events, the overflows with
at least one event, how many of those ids are in the annual returns (any year), and the annual returns' own count
of overflows with an EDM reporting that year and with at least one counted spill.

Nothing here trains or scores the model: the parquets are kept out of edm_events.parquet (see config).
Credits, all CC BY 4.0: edm_events.HISTORY_CREDITS.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys

import pandas as pd

from dipcast import config
from dipcast.arcgis import count
from dipcast.ingest.common import write_parquet
from dipcast.ingest.edm_events import (
    HISTORY_COMPANY,
    WESSEX_2024_SOURCE,
    crosswalk_by_events,
    fetch_history,
    fetch_wessex_2024,
    raw_cache_path,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("import_stream_events")


def slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")


def events_path(company: str):
    return config.PROCESSED / f"stream_events_{slug(company)}.parquet"


def check_read(source: str, url: str | None = None) -> int:
    """The layer's count, after checking the cached read holds exactly that many distinct rows."""
    n_layer = count(url or config.EDM_HISTORY_FEEDS[source])
    raw = pd.read_parquet(raw_cache_path(source))
    oid = next(c for c in raw.columns if c.lower() == "objectid")
    n_raw, n_ids = len(raw), raw[oid].nunique()
    log.info("%s: layer %d, fetched %d, distinct object ids %d", source, n_layer, n_raw, n_ids)
    if not n_layer == n_raw == n_ids:
        sys.exit(f"{source}: the read does not match the layer; run again with --refresh")
    return n_layer


def wessex_ids(ev: pd.DataFrame, refresh: bool) -> pd.DataFrame:
    """Wessex Water's 2020-2023 events under the annual returns' ids. Its layers use the company's own
    ids; the crosswalk comes from matching its 2024 layer's events to the EA's 2024 file
    (edm_events.crosswalk_by_events), written to data/processed/wessex_id_crosswalk.csv."""
    own = fetch_wessex_2024(refresh=refresh)
    check_read(WESSEX_2024_SOURCE, config.WESSEX_EDM_2024)
    ea = pd.read_parquet(config.PROCESSED / "ea_events_wessex_water.parquet")
    cw = crosswalk_by_events(own, ea[ea["event_start"].dt.year == 2024])
    cw.to_csv(config.PROCESSED / "wessex_id_crosswalk.csv", index=False)
    found = cw.dropna(subset=["to_id"])
    log.info("Wessex crosswalk: %d of %d own ids matched (median share %.3f); %d target ids used twice",
             len(found), len(cw), found["share"].median(), int(found["to_id"].duplicated().sum()))
    mapped = ev["site_id"].map(found.set_index("from_id")["to_id"])
    log.info("Wessex 2020-2023: %d of %d events mapped to annual-return ids", int(mapped.notna().sum()), len(ev))
    return ev.assign(site_id=mapped.fillna(ev["site_id"]))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true", help="read the layers again instead of the cache")
    args = p.parse_args()
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet",
                         columns=["site_id", "company", "year", "has_data", "spills"])
    rows = []
    for source, company in HISTORY_COMPANY.items():
        ev = fetch_history(source, refresh=args.refresh)
        n_layer = check_read(source)
        log.info("%s: %d events kept of %d (unreadable start, or negative or over 60 days long)",
                 source, len(ev), n_layer)
        if company == "Wessex Water":
            ev = wessex_ids(ev, args.refresh)
        write_parquet(ev, events_path(company))
        ev["year"] = ev["event_start"].dt.year
        for y, d in ev.groupby("year"):
            a = ar[(ar["company"] == company) & (ar["year"] == y)]
            ids = set(d["site_id"])
            known = set(ar.loc[ar["company"] == company, "site_id"].dropna())   # any year: early returns lack ids
            rows.append({"company": company, "year": int(y), "events": len(d), "overflows": len(ids),
                         "ids_in_returns": len(ids & known),
                         "returns_edm": int((a["has_data"] == 1).sum()) if len(a) else None,
                         "returns_spilled": int((a["spills"] > 0).sum()) if len(a) else None})
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
