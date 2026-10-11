"""Inputs for the Scottish hindcast (Scotland plan, task S2), off CI. Publishes nothing.

1. The three spill-model covariates per overflow and year, from S1's events
   (data/processed/sw_events.parquet and sw_events_yearly.parquet; run scripts/fetch_sw_history.py
   first) by the rule in ingest/sw_covariates.py -> data/processed/sw_covariates.parquet.
2. The Scottish rain cells -> data/processed/scotland_rain_cells.csv: the RAIN_GRID_DEG cells holding
   an asset of Scottish Water's near-real-time API (S1's cached answer,
   data/raw/scottish_water/near_real_time.json; nothing is fetched from Scottish Water here) or an
   overflow with event history, with how many of each.
3. ERA5-Land hourly rain for those cells, 2021 to 2025 (rainfall.fetch_archive), cached per
   cell-year in the same cache as England's and Wales's (DIPCAST_CACHE/rain).

Contains Scottish Water data licensed under the Open Government Licence v3.0.

Open-Meteo counts a request as locations x (days / 14) calls, so one cell-year of hourly rain is
about 26 calls; its free tier allows 10,000 a day and 5,000 an hour. The whole archive is about
55,000 calls, so it is spread over several days: each run stops before `--max-calls`, and spaces
its requests to stay under `--per-hour` (the pattern of scripts/fetch_wales_history.py). Cell-years
already cached are never asked for again, so the same command resumes. It stops at the first
refusal: a 429 is not retried, and any request that still fails after fetch_archive's retries ends
the run. Never run it beside a site build or another Open-Meteo job on the same IP.

The order puts first what S3's hindcast needs most: cell-years holding an overflow with a label
that year and a count the year before (the arm the gate is about), then other labelled
cell-years, then cells of API assets with no history; newest year first within each, and within a
year the cells with most such overflows first.

    DIPCAST_ROOT=<main checkout> uv run python scripts/fetch_scotland_history.py --dry-run
    DIPCAST_ROOT=<main checkout> uv run python scripts/fetch_scotland_history.py --max-calls 3000
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_wales_history import archive_calls, archive_days

from dipcast import config
from dipcast.ingest import rainfall, scottish_water, sw_covariates, sw_history
from dipcast.ingest.common import write_parquet

log = logging.getLogger("fetch_scotland_history")

EVENTS = config.PROCESSED / "sw_events.parquet"
YEARLY = config.PROCESSED / "sw_events_yearly.parquet"
API_ANSWER = sw_history.RAW_DIR / "near_real_time.json"
COV_OUT = config.PROCESSED / "sw_covariates.parquet"
CELLS_OUT = config.PROCESSED / "scotland_rain_cells.csv"
YEARS = [2021, 2022, 2023, 2024, 2025]
TIERS = {1: "label + count the year before", 2: "label only", 3: "no label (API assets, other years)"}


def cell_years(api: pd.DataFrame, sites: pd.DataFrame, cov: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """One row per rain cell and year: api (assets), history (overflows with any history), gate
    (overflows with a label that year and a count the year before), labelled (a label that year),
    and the fetch tier (TIERS). `api` and `sites` need site_id, lat and lon."""
    pos = pd.concat([api[["site_id", "lat", "lon"]].assign(who="api"),
                     sites[["site_id", "lat", "lon"]].assign(who="history")], ignore_index=True).dropna(subset=["lat", "lon"])
    pos["cell_lat"], pos["cell_lon"] = rainfall.grid_cell(pos["lat"].to_numpy(), pos["lon"].to_numpy())
    hist = pos[pos["who"] == "history"].drop_duplicates("site_id").set_index("site_id")[["cell_lat", "cell_lon"]]
    cells = (pos.groupby(["cell_lat", "cell_lon"])["who"]
             .agg(api=lambda s: int((s == "api").sum()), history=lambda s: int((s == "history").sum())).reset_index())
    has = cov[cov["spills"].notna()][["site_id", "year"]]
    lab = set(map(tuple, has.to_numpy()))
    rows = []
    for y in years:
        labelled = [s for s in hist.index if (s, y) in lab]
        gate = [s for s in labelled if (s, y - 1) in lab]
        n_lab = hist.loc[labelled].value_counts().rename("labelled")
        n_gate = hist.loc[gate].value_counts().rename("gate")
        c = cells.merge(n_lab.reset_index(), on=["cell_lat", "cell_lon"], how="left").merge(
            n_gate.reset_index(), on=["cell_lat", "cell_lon"], how="left")
        rows.append(c.assign(year=y))
    out = pd.concat(rows, ignore_index=True)
    out[["labelled", "gate"]] = out[["labelled", "gate"]].fillna(0).astype(int)
    out["tier"] = (out["gate"] > 0).map({True: 1, False: 0})
    out.loc[out["tier"] == 0, "tier"] = (out["labelled"] > 0).map({True: 2, False: 3})
    return out.sort_values(["tier", "year", "gate", "labelled", "api", "cell_lat", "cell_lon"],
                           ascending=[True, False, False, False, False, True, True]).reset_index(drop=True)


def history_sites(cov: pd.DataFrame, ev: pd.DataFrame, api: pd.DataFrame) -> pd.DataFrame:
    """site_id, lat, lon of every overflow in the covariate table: the position S1 gave its events,
    else its API asset's (an overflow listed only with "No Events" has no event row)."""
    pos = ev.dropna(subset=["lat", "lon"]).groupby("site_id")[["lat", "lon"]].first()
    pos = pos.combine_first(api.drop_duplicates("site_id").set_index("site_id")[["lat", "lon"]])
    return pos.reindex(sorted(cov["site_id"].unique())).rename_axis("site_id").reset_index()


def is_cached(cell: tuple[float, float], year: int) -> bool:
    return (rainfall.CACHE / f"archive_{rainfall.cell_key(*cell)}_{year}.parquet").exists()


def requests_plan(cy: pd.DataFrame, batch: int | None = None) -> list[tuple[int, int, list[tuple[float, float]]]]:
    """(tier, year, cells) per request, in `cy`'s order, uncached cell-years only; one request
    never mixes tiers or years."""
    batch = batch or rainfall.BATCH
    out = []
    for (tier, year), g in cy.groupby(["tier", "year"], sort=False):
        todo = [(a, b) for a, b in zip(g["cell_lat"], g["cell_lon"], strict=True) if not is_cached((a, b), year)]
        out += [(int(tier), int(year), todo[i:i + batch]) for i in range(0, len(todo), batch)]
    return out


def fetch_paced(plan: list[tuple[int, int, list]], max_calls: float, per_hour: float,
                fetch: Callable = lambda chunk, year: rainfall.fetch_archive(chunk, year, strict=True),
                sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> dict:
    """Make the planned requests one at a time. Each waits until the last one's calls fit inside
    `per_hour`; the run stops before `max_calls`, at the first request that raises (a refusal:
    fetch_archive(strict=True) does not retry a 429), or at one whose cells are still uncached."""
    done = {"requests": 0, "calls": 0.0, "cell_years": 0, "stopped": None}
    next_at = clock()
    for tier, year, chunk in plan:
        calls = archive_calls(len(chunk), archive_days(year))
        if done["calls"] + calls > max_calls:
            done["stopped"] = f"budget: {done['calls']:.0f} of {max_calls:.0f} calls used"
            return done
        wait = next_at - clock()
        if wait > 0:
            sleep(wait)
        done["requests"] += 1
        done["calls"] += calls          # a refused request may still count against the quota
        try:
            fetch(chunk, year)
        except Exception as e:  # noqa: BLE001 - any failure ends the run; the cache keeps what came
            done["stopped"] = f"refused: {e}"
            return done
        next_at = clock() + 3600 * calls / per_hour
        left = [c for c in chunk if not is_cached(c, year)]
        done["cell_years"] += len(chunk) - len(left)
        if left:
            done["stopped"] = f"refused: {len(left)} cells of {year} still uncached"
            return done
        log.info("tier %d, %d: %d cells; %.0f calls this run", tier, year, len(chunk), done["calls"])
    return done


def status(cy: pd.DataFrame) -> pd.DataFrame:
    """Cached and missing cell-years, and the calls still to make, by tier and year."""
    d = cy.assign(cached=[is_cached((a, b), y) for a, b, y in zip(cy.cell_lat, cy.cell_lon, cy.year, strict=True)])
    t = d.groupby(["tier", "year"]).agg(cells=("cached", "size"), cached=("cached", "sum")).reset_index()
    t["missing"] = t["cells"] - t["cached"]
    t["calls_left"] = [round(archive_calls(m, archive_days(y))) for m, y in zip(t["missing"], t["year"], strict=True)]
    return t


def describe_covariates(cov: pd.DataFrame) -> None:
    c = cov[cov["spills"].notna()]
    t = c.groupby("year").agg(overflows=("site_id", "size"), spills_median=("spills", "median"),
                              hours_median=("spill_hours", "median"),
                              uptime_known=("edm_operational_pct", lambda s: int(s.notna().sum())),
                              uptime_median=("edm_operational_pct", "median"),
                              lta_median=("lta_spills", "median"), short_dropped=("short_dropped", "sum"))
    t["lta_uptime90"] = c[c["lta_basis"] == "uptime90"].groupby("year").size()
    print("covariates by return year (overflows with a count):")
    print(t.round(1).to_string())
    for y in YEARS[1:] + [2026]:
        print(f"  a run for {y} has year-before covariates for {len(sw_covariates.covariates_for(cov, y))} overflows")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--years", type=int, nargs="+", default=YEARS)
    ap.add_argument("--max-calls", type=float, default=3000, help="Open-Meteo calls this run (10,000 a day, shared IP)")
    ap.add_argument("--per-hour", type=float, default=3000, help="Open-Meteo calls an hour (5,000 allowed)")
    ap.add_argument("--dry-run", action="store_true", help="covariates, cells and call counts; fetch no rain")
    ap.add_argument("--no-write", action="store_true", help="write neither the covariates nor the cell list")
    args = ap.parse_args()

    ev, yearly = pd.read_parquet(EVENTS), pd.read_parquet(YEARLY)
    cov = sw_covariates.covariates(ev, yearly)
    api = scottish_water.parse(json.loads(API_ANSWER.read_text()), pd.Timestamp.now("UTC"))
    sites = history_sites(cov, ev, api)
    cov = cov.merge(sites, on="site_id", how="left").merge(
        api[["site_id", "asset_type", "emergency"]].assign(in_api=True), on="site_id", how="left")
    cov["in_api"] = cov["in_api"].fillna(False).astype(bool)
    describe_covariates(cov)

    cy = cell_years(api, sites, cov, args.years)
    if not args.no_write:
        write_parquet(cov, COV_OUT)
        cy.to_csv(CELLS_OUT, index=False)
        print(f"-> {COV_OUT}\n-> {CELLS_OUT}")
    n_cells = cy[["cell_lat", "cell_lon"]].drop_duplicates()
    print(f"{len(api)} API assets + {sites.site_id.nunique()} overflows with history -> {len(n_cells)} rain cells "
          f"({(cy.drop_duplicates(['cell_lat', 'cell_lon']).api > 0).sum()} with an API asset, "
          f"{(cy.drop_duplicates(['cell_lat', 'cell_lon']).history > 0).sum()} with history)")
    st = status(cy)
    print(st.to_string(index=False))
    print(f"total: {int(st.cached.sum())} of {int(st.cells.sum())} cell-years cached; "
          f"about {int(st.calls_left.sum())} calls left ({int(st[st.tier < 3].calls_left.sum())} for tiers 1-2)")
    print(f"rain cache: {rainfall.CACHE}")
    if args.dry_run:
        return
    done = fetch_paced(requests_plan(cy), args.max_calls, args.per_hour)
    print(f"requests {done['requests']}, about {done['calls']:.0f} calls, {done['cell_years']} cell-years fetched")
    st = status(cy)
    print(st.to_string(index=False))
    print(f"total: {int(st.cached.sum())} of {int(st.cells.sum())} cell-years cached; about {int(st.calls_left.sum())} "
          f"calls left" + (f"; stopped on {done['stopped']}" if done["stopped"] else ""))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main()
