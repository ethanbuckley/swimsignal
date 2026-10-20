"""Pair each supplied lab result that may be used to test the forecast (evaluate = true, samples/README.md)
with the forecasts that were live for its spot when the sample was taken, and write the pairs out.

    gh release download state -p dipcast.duckdb -D ~/tmp/state
    uv run python scripts/evaluate_samples.py --db ~/tmp/state/dipcast.duckdb

It needs the forecast log, the DuckDB file the build appends to (forecast_log.py, forecast_points: one row
per spot, issue and target day). That file is on the runner (DIPCAST_STATE) and in the repository's
rolling "state" release, which the commands above download; a local checkout's data/processed copy is
only as new as its last build. It reads the private folder (DIPCAST_SAMPLES_PRIVATE), so it runs where
that folder is, and the pairs it writes go there too: they hold samples that may not be published.

The rule is verify_ecoli's for the EA's samples: for each sample and each lead (0 for a forecast issued
on the sampling day, up to 4 for four days ahead), the latest forecast issued before the sample was
taken, for the sample's UK day. A forecast issued after the sample is not a forecast of it. The row
marked live_at_sample is the newest of them: what the spot's page said when the sample was taken. A
logged forecast is found by the spot's coordinates in spots.csv, to 4 decimal places (about 10 m), as
verify_ecoli finds a bathing water's: a spot moved since leaves its earlier forecasts unmatched.

over_900 is 1 or 0 where the E. coli count settles it ("<10" is under, ">24196" over; "<1000" settles
nothing), as the page and the level count it (levels.js, sampleOver). Nothing here scores the pairs:
with a handful of samples a score would mean little, and which test to run belongs in a
pre-registration first (docs/PREREGISTRATION-2027.md).
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from dipcast import config
from dipcast import samples as sm

ROOT = Path(__file__).resolve().parents[1]
SPOT_FILES = (ROOT / "spots.csv", ROOT / "spots-osm.csv")
LEADS = range(5)   # 0, a forecast issued on the sampling day, to 4, four days ahead
OUT_COLUMNS = ["spot_id", "supplier", "sampled_at", "ecoli_per_100ml", "over_900", "enterococci_per_100ml", "lab",
               "ukas_accredited", "lead", "issued_at", "live_at_sample", "p_ecoli", "risk", "rain_48h", "version",
               "in_tested_season"]
LINE = 900


def spot_points(files=SPOT_FILES) -> dict[str, tuple[float, float]]:
    return {r["id"]: (round(float(r["lat"]), 4), round(float(r["lon"]), 4))
            for f in files if f.exists() for r in csv.DictReader(f.open(newline="", encoding="utf-8"))}


def over_900(c: tuple[float, str] | None) -> int | None:
    """1, 0, or None where the count is a limit that does not settle it (levels.js, sampleOver)."""
    if c is None:
        return None
    n, q = c
    if q == "<":
        return 0 if n <= LINE else None
    if q == ">":
        return 1 if n >= LINE else None
    return int(n > LINE)


def logged_points(db: Path, days: list) -> pd.DataFrame:
    """The forecast log's spot forecasts for these target days, read only."""
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute("""
            SELECT epoch_ms(issued_at) AS issued_ms, round(lat, 4) AS lat, round(lon, 4) AS lon, target_day, lead,
                   p_ecoli, risk, rain_48h, version
            FROM forecast_points WHERE target_day IN (SELECT unnest(?))""", [days]).df()
    finally:
        con.close()


def pairs(rows: list[dict], points: pd.DataFrame, where: dict[str, tuple[float, float]]) -> list[dict]:
    """A row for each sample and lead with a forecast issued before the sample; one row with no forecast
    for a sample that has none, so a gap is counted rather than dropped."""
    out = []
    if len(points):
        points = points.assign(issued_at=pd.to_datetime(points["issued_ms"], unit="ms", utc=True).dt.tz_convert(sm.UK),
                               target_day=pd.to_datetime(points["target_day"]).dt.date)
    for r in rows:
        day, at = r["_at"].astimezone(sm.UK).date(), pd.Timestamp(r["_at"])
        base = {"spot_id": r["spot_id"], "supplier": r["supplier"], "sampled_at": r["sampled_at"],
                "ecoli_per_100ml": r["ecoli_per_100ml"], "over_900": over_900(r["_ecoli"]),
                "enterococci_per_100ml": r["enterococci_per_100ml"], "lab": r["lab"], "ukas_accredited": r["ukas_accredited"],
                "in_tested_season": 5 <= day.month <= 9}   # the E. coli estimate is tested May to September only
        lat, lon = where.get(r["spot_id"], (None, None))
        m = points[(points["lat"] == lat) & (points["lon"] == lon) & (points["target_day"] == day)
                   & (points["issued_at"] < at)] if len(points) and lat is not None else pd.DataFrame()
        found = []
        for lead in LEADS:
            g = m[m["lead"] == lead] if len(m) else m
            if len(g):
                x = g.sort_values("issued_at").iloc[-1]
                found.append(base | {"lead": lead, "issued_at": x["issued_at"].isoformat(timespec="minutes"),
                                     "p_ecoli": None if pd.isna(x["p_ecoli"]) else round(float(x["p_ecoli"]), 4),
                                     "risk": None if pd.isna(x["risk"]) else round(float(x["risk"]), 4),
                                     "rain_48h": None if pd.isna(x["rain_48h"]) else round(float(x["rain_48h"]), 1),
                                     "version": x["version"], "_t": x["issued_at"]})
        if found:
            newest = max(f["_t"] for f in found)
            out += [{k: v for k, v in f.items() if k != "_t"} | {"live_at_sample": f["_t"] == newest} for f in found]
        else:
            out.append(base | {"lead": None, "issued_at": None, "live_at_sample": None})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=None, help="the forecast log (default: DIPCAST_STATE's dipcast.duckdb)")
    ap.add_argument("--private", help=f"the private folder (default ${sm.PRIVATE_ENV}, else {sm.PRIVATE_DEFAULT})")
    ap.add_argument("--out", type=Path, default=None, help="where to write the pairs (default: <private>/evaluation/pairs.csv)")
    a = ap.parse_args(argv)
    try:
        private = sm.private_dir(a.private)
        rows = [r for rs in sm.read_private(private, now=datetime.now(sm.UK)).values() for r in rs if r["evaluate"] == "true"]
    except sm.SampleError as e:
        print(e, file=sys.stderr)
        return 1
    db = a.db or config.state_read("dipcast.duckdb")
    if not db.exists():
        print(f"no forecast log at {db}: download the state release (see the top of this file)", file=sys.stderr)
        return 1
    if not rows:
        print("no sample may be used to test the forecast (evaluate = true)")
        return 0
    points = logged_points(db, sorted({r["_at"].astimezone(sm.UK).date() for r in rows}))
    out = pairs(rows, points, spot_points())
    dst = a.out or private / "evaluation" / "pairs.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    paired = {(p["spot_id"], p["sampled_at"]) for p in out if p["lead"] is not None}
    print(f"{len(rows)} sample{'' if len(rows) == 1 else 's'} to test against; {len(paired)} with a forecast issued before "
          f"them, {len(rows) - len(paired)} without. {len(out)} rows in {dst}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
