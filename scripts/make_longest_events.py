"""Each overflow's longest spill in the Environment Agency's start/stop records:
data/processed/longest_events.parquet, one row per overflow (site_id, longest_h, n_events). The data-quality
page reads it for its list of monitors reporting a spill far longer than any on record
(monitor_anomalies.long_runs; docs/MONITOR-ANOMALIES-2026-10.md, section 8). The build reads only this file,
never the event files.

    uv run python scripts/make_longest_events.py [--ea-events DIR] [--out FILE]

Off CI, by hand: when scripts/import_ea_events.py has read a new year. --ea-events is the folder of
ea_events_<company>.parquet (default data/processed), England's nine companies; Dwr Cymru Welsh Water's
events are a test set kept apart and have no live feed here. An overflow with no event in the records has
no row: the page then says it has none on record.

Contains Environment Agency data: © Environment Agency copyright and/or database right, licensed under the
Open Government Licence v3.0.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from dipcast import config
from dipcast.ingest.common import write_parquet
from dipcast.monitor_anomalies import LONGEST_FILE, longest_events_table


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ea-events", type=Path, default=config.PROCESSED)
    ap.add_argument("--out", type=Path, default=LONGEST_FILE)
    a = ap.parse_args()
    files = sorted(a.ea_events.glob("ea_events_*.parquet"))
    if not files:
        raise SystemExit(f"no ea_events_*.parquet in {a.ea_events}")
    ev = pd.concat([pd.read_parquet(p, columns=["site_id", "event_start", "event_end"]) for p in files], ignore_index=True)
    out = longest_events_table(ev)
    write_parquet(out, a.out)
    print(f"{len(files)} files, {len(ev):,} events from {ev['event_start'].min()} to {ev['event_end'].max()}; "
          f"{len(out):,} overflows; {a.out} is {a.out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
