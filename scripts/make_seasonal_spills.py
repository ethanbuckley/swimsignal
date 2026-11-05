"""Write data/raw/seasonal_spills.json: each listed spot's past spills upstream by month (src/dipcast/seasonal.py).

Off CI, from a checkout with the event files in data/processed (git-ignored): the EA start/stop files
(ea_events_*.parquet, dcww_ea_events.parquet), Northumbrian's and Wessex's own layers
(stream_events_*.parquet), United Utilities' 2023 layer (edm_events.parquet), the annual returns and the
Wessex id crosswalk. It traces each spot's upstream overflows the way the build does (upstream_overflows,
with the default velocity, as the build has no gauge), so it needs the river network and the overflow
table the build would use. No network requests.

    uv run python scripts/make_seasonal_spills.py

Run it again when a spot is added or a river re-traced: the build hides a spot's panel when its overflows
no longer match the ones counted here, and says how many in its health.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from dipcast import config, seasonal
from dipcast.model.features import spill_days
from dipcast.model.forecast import _net, _overflows
from dipcast.model.transport import locate_pin, spot_hints, upstream_overflows

log = logging.getLogger("make_seasonal_spills")
OUT = config.RAW / "seasonal_spills.json"
SPOT_FILES = [config.ROOT / "spots.csv", config.ROOT / "spots-osm.csv"]


def events(processed: Path) -> pd.DataFrame:
    """Every held event in a year RECORDS lists for its source, the columns spill_days needs."""
    cols = ["site_id", "event_start", "event_end"]
    parts = [pd.read_parquet(f, columns=cols) for f in sorted(processed.glob("ea_events_*.parquet"))]
    parts.append(pd.read_parquet(processed / "dcww_ea_events.parquet", columns=cols))
    ea = pd.concat(parts)
    ea = ea[ea["event_start"].dt.year.isin([2024, 2025])]
    early = []
    for name, years in (("stream_events_northumbrian_water", (2021, 2022, 2023)),
                        ("stream_events_wessex_water", (2021, 2022, 2023)), ("edm_events", (2023,))):
        d = pd.read_parquet(processed / f"{name}.parquet", columns=cols)
        early.append(d[d["event_start"].dt.year.isin(years)])
    return pd.concat([ea, *early], ignore_index=True)


def day_sets(ev: pd.DataFrame) -> dict[str, set]:
    sd = spill_days(ev)
    sd = sd[(sd["day"] >= pd.Timestamp(f"{seasonal.YEARS[0]}-01-01", tz="UTC"))
            & (sd["day"] < pd.Timestamp(f"{seasonal.YEARS[-1] + 1}-01-01", tz="UTC"))]
    out: dict[str, set] = {}
    for sid, day in zip(sd["site_id"].astype(str), sd["day"].dt.date):
        out.setdefault(sid, set()).add(day)
    return out


def covered(processed: Path) -> set[tuple[str, int]]:
    ar = pd.read_parquet(processed / "annual_returns.parquet", columns=["site_id", "company", "year", "edm_operational_pct"])
    mapped = set(pd.read_csv(processed / "wessex_id_crosswalk.csv")["to_id"].astype(str))
    keep = lambda sid, company, year: not (company == "Wessex Water" and year < 2024 and sid not in mapped)  # noqa: E731
    rows = ar.itertuples(index=False, name=None)
    return seasonal.covered_years(((s, c, int(y), None if pd.isna(p) else float(p)) for s, c, y, p in rows), keep=keep)


def upstream_ids() -> dict[str, list[str]]:
    net, ov_all = _net(), _overflows()
    spots = pd.concat([pd.read_csv(p) for p in SPOT_FILES if p.exists()], ignore_index=True).fillna("")
    spots = spots[~spots["id"].duplicated()]
    out = {}
    for r in spots.itertuples(index=False):
        kind, river = spot_hints(r.kind, r.river)
        pin = locate_pin(net, float(r.lon), float(r.lat), kind_hint=kind, river_hint=river, name=r.name)
        if pin.mode in ("none", "isolated"):
            out[r.id] = []
            continue
        ov = upstream_overflows(net, pin, ov_all, velocity_ms=config.RIVER_VELOCITY_MS, max_km=config.MAX_UPSTREAM_KM)
        out[r.id] = [str(s) for s in ov["site_id"]]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--processed", type=Path, default=config.PROCESSED)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sets, cov, ups = day_sets(events(a.processed)), covered(a.processed), upstream_ids()
    spots = {sid: seasonal.spot_history(ids, sets, cov) for sid, ids in sorted(ups.items())}
    doc = {"made": dt.date.today().isoformat(), "years": list(seasonal.YEARS), "min_edm_pct": seasonal.MIN_EDM_PCT,
           "min_covered": seasonal.MIN_COVERED, "spill_day": "UTC day an event touches at the overflow",
           "sources": seasonal.SOURCES, "spots": spots}
    body = json.dumps(doc, separators=(",", ":"), sort_keys=False)
    a.out.write_text(body + "\n", encoding="utf-8")
    used = sum(1 for e in spots.values() if e["years"])
    log.info("%s: %d spots, %d with a year used, %d with nothing upstream, %d bytes",
             a.out, len(spots), used, sum(1 for e in spots.values() if not e["overflows"]), len(body))
    return 0


if __name__ == "__main__":
    sys.exit(main())
