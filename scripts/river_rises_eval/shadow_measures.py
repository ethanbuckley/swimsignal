"""The measures the river-rises shadow logger keeps (docs/RIVER-RISES-C3-2026-11.md, "The shadow log").

    uv run python scripts/river_rises_eval/shadow_measures.py [--cache <dir>] [--out river-shadow]

Writes <out>/measures.json (for people and the offline scorer) and <out>/src/measures.js (the Worker's filter, a
plain ES module, so the Worker needs no JSON import). Offline: no request is made. Research only: nothing here
feeds the site.

- **Gauges:** every spot gauge in docs/RIVER-RISES-SCOPE-2026-10-gauges.csv with a Hydrology measure (45), and
  every upstream gauge in docs/RIVER-RISES-SCOPE-2026-10-slots.csv (`same` and `trib`), one row per role. The
  CSVs' `measure` column is a Hydrology id; the logger needs the flood-monitoring one.
- **Measure:** the one the site would read, as flows.station_pick and flows.river_state choose it: the station's
  level measures from the national stations list in the order flows._level_measures gives (stage first, then
  m/mASD before mAOD, then as listed), and the first of those with a reading in the national latest-readings
  answer. Where none has a reading in that answer, the first in that order, and the row is flagged.
- **Filter:** every level measure of every listed station, in that order (`site_order`), so that the scorer can
  apply the site's rule at each issue time if the first measure stops publishing.

Both sources are read-only caches of 26 October 2026 (the coverage run's), opened and never written.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from dipcast.ingest import flows

ROOT = Path(__file__).resolve().parents[2]
GAUGES = ROOT / "docs" / "RIVER-RISES-SCOPE-2026-10-gauges.csv"
SLOTS = ROOT / "docs" / "RIVER-RISES-SCOPE-2026-10-slots.csv"
CACHE = Path.home() / "Documents/GitHub/swimsignal-private/river-rises/coverage-cache-2026-10-26"
LATEST_KEY = "2b62dc54723fe5998fe3fb84"     # flood-monitoring/data/readings?latest&parameter=level, 26 Oct 2026 18:59 UTC
STATIONS_KEY = "b0ce32a9d80a311709cefe25"   # flood-monitoring/id/stations?parameter=level&type=SingleLevel&_limit=10000
FM_MEASURE = "http://environment.data.gov.uk/flood-monitoring/id/measures/"
SCHEMA = "swimsignal.river-shadow.measures"


def _cached(cache: Path, key: str) -> tuple[dict, dict]:
    meta = json.loads((cache / f"{key}.json").read_text())
    return meta, json.loads((cache / f"{key}.body").read_text())


def gauge_rows() -> list[dict]:
    """(station, role, spot_gauge, low, high) for every spot gauge with a measure and every upstream slot."""
    rows = []
    with GAUGES.open(newline="") as f:
        for r in csv.DictReader(f):
            if r["measure"].strip():
                rows.append({"station": r["gauge"], "role": "spot", "spot_gauge": r["gauge"],
                             "low": float(r["low"]), "high": float(r["high"])})
    with SLOTS.open(newline="") as f:
        for r in csv.DictReader(f):
            rows.append({"station": r["up"], "role": r["slot"], "spot_gauge": r["gauge"],
                         "low": float(r["low"]), "high": float(r["high"])})
    return rows


def resolve(rows: list[dict], stations: list[dict], readings: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """The rows with their measure, the refs with no level measure, and the rows whose measure had no reading."""
    by_ref = {s.get("stationReference"): s for s in stations}
    out, missing, unread, seen_missing = [], [], [], set()
    for r in rows:
        s = by_ref.get(r["station"])
        order = flows._level_measures(s) if s else []
        if not order:
            if r["station"] not in seen_missing:
                seen_missing.add(r["station"])
                why = ("not in the flood-monitoring stations list (parameter=level, type=SingleLevel)" if s is None
                       else "station lists no level measure")
                missing.append({"station": r["station"], "role": r["role"], "spot_gauge": r["spot_gauge"],
                                "reason": why})
            continue
        pick = next((m for m in order if m in readings), None)
        row = {**r, "measure": FM_MEASURE + (pick or order[0]), "site_order": [FM_MEASURE + m for m in order],
               "reading_in_source": pick is not None}
        if pick is None:
            status = str(s.get("status", "")).rsplit("/", 1)[-1] or "unknown"
            unread.append({"station": r["station"], "role": r["role"], "spot_gauge": r["spot_gauge"],
                           "measure": row["measure"], "station_status": status,
                           "reason": "no level reading of this station in the latest-readings source; "
                                     "first measure in the site's order kept"})
        out.append(row)
    return out, missing, unread


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cache", type=Path, default=CACHE, help="the coverage run's cache folder (read-only)")
    ap.add_argument("--out", type=Path, default=ROOT / "river-shadow")
    a = ap.parse_args(argv)

    latest_meta, latest = _cached(a.cache, LATEST_KEY)
    stations_meta, stations = _cached(a.cache, STATIONS_KEY)
    readings = flows._readings_by_measure(latest.get("items", []))
    rows = gauge_rows()
    resolved, missing, unread = resolve(rows, stations.get("items", []), readings)

    seen, keys = set(), []
    for r in resolved:
        k = (r["station"], r["role"], r["spot_gauge"])
        if k in seen:
            raise SystemExit(f"duplicate row {k}")
        seen.add(k)
        keys.append(k)
    filt = sorted({m.removeprefix(FM_MEASURE) for r in resolved for m in r["site_order"]})

    doc = {
        "schema": SCHEMA, "version": 1, "written": datetime.now(UTC).date().isoformat(),
        "source": {
            "gauges": str(GAUGES.relative_to(ROOT)), "slots": str(SLOTS.relative_to(ROOT)),
            "stations": {"url": stations_meta["url"], "params": stations_meta.get("params"),
                         "at": stations_meta.get("at"), "n": len(stations.get("items", []))},
            "latest": {"url": latest_meta["url"], "params": latest_meta.get("params"),
                       "at": latest_meta.get("at"), "n": len(latest.get("items", []))},
            "rule": "flows._level_measures order, first with a reading in `latest` (flows.river_state); "
                    "else the first in that order",
        },
        "stations": resolved,
        "missing": missing,
        "no_reading_in_source": unread,
        "filter": filt,
    }
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "measures.json").write_text(json.dumps(doc, indent=1) + "\n")
    (a.out / "src").mkdir(exist_ok=True)
    (a.out / "src" / "measures.js").write_text(
        "// Generated by scripts/river_rises_eval/shadow_measures.py from measures.json; do not edit by hand.\n"
        "// The flood-monitoring level measure ids the logger keeps (every level measure of each listed station).\n"
        f"export const MEASURE_IDS = Object.freeze({json.dumps(filt, indent=1)});\n")

    by_role = {}
    for r in resolved:
        by_role[r["role"]] = by_role.get(r["role"], 0) + 1
    picks = {r["measure"] for r in resolved}
    print(f"rows: {len(resolved)} ({', '.join(f'{k} {v}' for k, v in sorted(by_role.items()))}); "
          f"distinct stations {len({r['station'] for r in resolved})}; distinct picked measures {len(picks)}; "
          f"filter measures {len(filt)}")
    print(f"missing (no flood-monitoring level measure): {len(missing)}"
          + "".join(f"\n  {m['station']} ({m['role']}): {m['reason']}" for m in missing))
    print(f"no reading in the latest-readings source: {len(unread)}"
          + "".join(f"\n  {u['station']} ({u['role']} of {u['spot_gauge']}, {u['station_status']})" for u in unread))
    return 0


if __name__ == "__main__":
    sys.exit(main())
