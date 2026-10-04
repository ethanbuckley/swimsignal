"""Inputs for the Welsh hindcast (Wales plan, task W3), off CI. Publishes nothing.

1. Hafren Dyfrdwy's 2025 discharges -> data/processed/hd_events.parquet, in the edm_events schema
   (edm_events.fetch_hd_events). Credit: Hafren Dyfrdwy Event Duration Monitoring 2025, Hafren
   Dyfrdwy, via Stream, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
2. The Welsh rain cells -> data/processed/wales_rain_cells.csv: the RAIN_GRID_DEG cells holding a
   Dŵr Cymru overflow (every row of its live layer, positions only) or a Hafren Dyfrdwy site, with
   how many of each, and how many of those lie in Wales.
3. ERA5-Land hourly rain for those cells (rainfall.fetch_archive), cached per cell-year.

Dŵr Cymru's live layer has no licence (Wales plan, section 2.1). Only its outlet positions are
read, to pick grid cells; nothing from it is published or committed.

Open-Meteo's free tier allows 600 calls a minute, 5,000 an hour and 10,000 a day, and counts a
request as locations x (days / 14) x (variables / 10, at least 1) calls. One cell-year of hourly
rain is therefore about 26 calls, and a request of rainfall.BATCH cells about 261. This script
spaces requests to stay under `--per-hour` calls an hour and stops at `--max-calls` for the run,
so a large fetch is spread over several runs (several days). Cells already cached are not asked
for again: point DIPCAST_CACHE at a shared cache to reuse it. It stops at the first request that
still fails after fetch_archive's retries, rather than going round a refusal.

    DIPCAST_CACHE=<shared cache> uv run python scripts/fetch_wales_history.py            # all
    DIPCAST_CACHE=<shared cache> uv run python scripts/fetch_wales_history.py --dry-run  # count only
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape
from shapely.prepared import prep

from dipcast import config
from dipcast.arcgis import fetch_all
from dipcast.ingest import edm_events, rainfall
from dipcast.ingest.common import write_parquet

log = logging.getLogger("fetch_wales_history")

DCWW_LIVE = ("https://services3.arcgis.com/KLNF7YxtENPLYVey/arcgis/rest/services/"
             "Spill_Prod__view/FeatureServer/0")
HD_OUT = config.PROCESSED / "hd_events.parquet"
CELLS_OUT = config.PROCESSED / "wales_rain_cells.csv"
YEARS = [2024, 2025]
SHAPE = Path(__file__).resolve().parents[1] / "data" / "raw" / "outside_england.json"   # committed
WALES_MAX_LAT = 54.0   # the outside-England shape's Wales and Scotland part, south of 54 N, is Wales


def archive_days(year: int, today: pd.Timestamp | None = None) -> int:
    """Days fetch_archive asks for in `year` (it stops 6 days before today)."""
    today = today if today is not None else pd.Timestamp.now("UTC").tz_localize(None)
    end = min(pd.Timestamp(f"{year}-12-31"), today.normalize() - pd.Timedelta(days=6))
    return max(0, (end - pd.Timestamp(f"{year}-01-01")).days + 1)


def archive_calls(n_cells: int, days: int, variables: int = 1) -> float:
    """Open-Meteo's count for one request: locations x days/14 x variables/10, each at least 1."""
    return n_cells * max(1.0, days / 14) * max(1.0, variables / 10)


def wales_test(path: Path = SHAPE) -> Callable[[float, float], bool]:
    """(lat, lon) -> inside Wales, by the outside-England shape's Wales and Scotland polygons
    south of 54 N (as the Wales plan's section 4 measured)."""
    d = json.loads(path.read_text())
    polys = [p for p, part in zip(shape(d["geometry"]).geoms, d["parts"], strict=True)
             if part == "wales_scotland"]
    prepared = [prep(p) for p in polys]
    return lambda lat, lon: lat < WALES_MAX_LAT and any(p.contains(Point(lon, lat)) for p in prepared)


def rain_cells(dcww: pd.DataFrame, hd: pd.DataFrame,
               in_wales: Callable[[float, float], bool]) -> pd.DataFrame:
    """One row per rain cell: cell_lat, cell_lon, dcww (overflows), hd (sites), wales (of them in
    Wales). Both inputs need lat and lon; `hd` one row per site."""
    pts = pd.concat([dcww[["lat", "lon"]].assign(who="dcww"), hd[["lat", "lon"]].assign(who="hd")],
                    ignore_index=True).dropna(subset=["lat", "lon"])
    pts["cell_lat"], pts["cell_lon"] = rainfall.grid_cell(pts["lat"].to_numpy(), pts["lon"].to_numpy())
    pts["wales"] = [in_wales(a, b) for a, b in zip(pts["lat"], pts["lon"], strict=True)]
    g = pts.groupby(["cell_lat", "cell_lon"])
    out = pd.DataFrame({"dcww": g["who"].apply(lambda s: int((s == "dcww").sum())),
                        "hd": g["who"].apply(lambda s: int((s == "hd").sum())),
                        "wales": g["wales"].sum().astype(int)}).reset_index()
    return out.sort_values(["cell_lat", "cell_lon"]).reset_index(drop=True)


def uncached(cells: list[tuple[float, float]], year: int) -> list[tuple[float, float]]:
    return [c for c in cells
            if not (rainfall.CACHE / f"archive_{rainfall.cell_key(*c)}_{year}.parquet").exists()]


def fetch_paced(cells: list[tuple[float, float]], years: list[int], max_calls: float, per_hour: float,
                fetch: Callable = rainfall.fetch_archive, sleep: Callable[[float], None] = time.sleep,
                clock: Callable[[], float] = time.monotonic) -> dict:
    """Fetch the uncached cell-years one request (rainfall.BATCH cells) at a time. Each request
    waits until the last one's calls fit inside `per_hour`; the run stops before `max_calls`, or
    at the first request whose cells are still uncached afterwards (fetch_archive gave up)."""
    done = {"requests": 0, "calls": 0.0, "cell_years": 0, "stopped": None}
    next_at = clock()
    for year in years:
        days = archive_days(year)
        todo = uncached(cells, year)
        for i in range(0, len(todo), rainfall.BATCH):
            chunk = todo[i:i + rainfall.BATCH]
            calls = archive_calls(len(chunk), days)
            if done["calls"] + calls > max_calls:
                done["stopped"] = f"budget: {done['calls']:.0f} of {max_calls:.0f} calls used"
                return done
            wait = next_at - clock()
            if wait > 0:
                sleep(wait)
            fetch(chunk, year)
            done["requests"] += 1
            done["calls"] += calls
            next_at = clock() + 3600 * calls / per_hour
            left = uncached(chunk, year)
            done["cell_years"] += len(chunk) - len(left)
            if left:
                done["stopped"] = f"refused: {len(left)} cells of {year} still uncached after retries"
                return done
            log.info("%d: %d/%d cells; %.0f calls this run", year, i + len(chunk), len(todo), done["calls"])
    return done


def dcww_positions() -> pd.DataFrame:
    rows = fetch_all(DCWW_LIVE, key="GlobalID", out_fields="GlobalID", geometry=True)
    df = pd.DataFrame(rows).rename(columns={"_x": "lon", "_y": "lat"})
    return df[["GlobalID", "lat", "lon"]]


def describe_events(ev: pd.DataFrame) -> None:
    d = ev["duration_h"] * 60
    print(f"Hafren Dyfrdwy: {len(ev)} discharges at {ev.site_id.nunique()} sites, "
          f"{ev.event_start.min()} -> {ev.event_start.max()}; {ev.event_end.isna().sum()} with no end")
    print(f"  minutes: min {d.min():.1f}, median {d.median():.1f}; under 1 min {(d < 1).sum()}, "
          f"under 15 min {(d < 15).sum()}, under 1 h {(d < 60).sum()}")
    days = ev.assign(day=ev.event_start.dt.floor("D")).groupby(["site_id", "day"]).size()
    print(f"  spill-days (any discharge that day, by start): {len(days)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--years", type=int, nargs="+", default=YEARS)
    ap.add_argument("--max-calls", type=float, default=9000, help="Open-Meteo calls this run (10,000 a day)")
    ap.add_argument("--per-hour", type=float, default=4000, help="Open-Meteo calls an hour (5,000 allowed)")
    ap.add_argument("--dry-run", action="store_true", help="count cells and calls; fetch no rain")
    ap.add_argument("--refresh-events", action="store_true", help="read Hafren Dyfrdwy's layer again")
    args = ap.parse_args()

    ev = edm_events.fetch_hd_events(refresh=args.refresh_events)
    write_parquet(ev, HD_OUT)
    describe_events(ev)

    hd_sites = ev.groupby("site_id")[["lat", "lon"]].first().reset_index()
    dcww = dcww_positions()
    cells_df = rain_cells(dcww, hd_sites, wales_test())
    CELLS_OUT.parent.mkdir(parents=True, exist_ok=True)
    cells_df.to_csv(CELLS_OUT, index=False)
    cells = list(zip(cells_df.cell_lat, cells_df.cell_lon, strict=True))
    print(f"{len(dcww)} Dŵr Cymru overflows + {len(hd_sites)} Hafren Dyfrdwy sites -> {len(cells)} rain cells "
          f"({(cells_df.wales > 0).sum()} with an overflow in Wales) -> {CELLS_OUT}")
    for y in args.years:
        todo = uncached(cells, y)
        print(f"  {y}: {len(cells) - len(todo)} cached, {len(todo)} to fetch, "
              f"about {archive_calls(len(todo), archive_days(y)):.0f} calls")
    print(f"rain cache: {rainfall.CACHE}")
    if args.dry_run:
        return
    done = fetch_paced(cells, args.years, args.max_calls, args.per_hour)
    print(f"requests {done['requests']}, about {done['calls']:.0f} calls, {done['cell_years']} cell-years fetched")
    left = {y: len(uncached(cells, y)) for y in args.years}
    print(f"still uncached: {left}" + (f"; stopped on {done['stopped']}" if done["stopped"] else ""))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main()
