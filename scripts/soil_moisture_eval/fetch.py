"""docs/SOIL-MOISTURE-TEST-2026-10.md: fetch the soil moisture both questions read. Off CI, by hand, once:

    fetch.py <soil dir> q1 <frozen data dir> [--dry-run]
    fetch.py <soil dir> q2 [--dry-run]            # DIPCAST_ROOT: the checkout whose EA files and returns D2's rows use

q1: Previous Runs lead 0, soil_moisture_9_to_27cm, at the rain cell (rainfall.grid_cell) of every bathing water in the
    E. coli rows, 1 April to 30 September of 2023-26, by two quarters, 4 cells a request (a year times out on this
    API; docs/DIEOFF-WEATHER-TEST-2026-10.md). Saved as q1_<cell>_<year>.parquet.
q2: ERA5-Land (models=era5_land) soil_moisture_7_to_28cm at each overflow's 0.25-degree node, 2024 and 2025, by
    year, 5 nodes a request, paced at CALLS_PER_HOUR. Saved as q2_<node>_<year>.parquet.

Strict: a refusal or a body that is not JSON stops that request. It is tried once more in smaller pieces (months for
q1, quarters for q2); a piece that still fails stays missing and is logged. Every request's weight by Open-Meteo's
rule (rainfall.call_weight) goes to calls.jsonl in the soil dir. Existing files are not fetched again.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from dipcast.ingest.rainfall import call_weight, cell_key, grid_cell

PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
Q1_VAR, Q2_VAR = "soil_moisture_9_to_27cm", "soil_moisture_7_to_28cm"
Q1_YEARS, Q2_YEARS = (2023, 2024, 2025, 2026), (2024, 2025)
Q1_PARTS = (("04-01", "06-30"), ("07-01", "09-30"))
Q2_NODE_DEG = 0.25
Q1_BATCH, Q2_BATCH = 4, 5
CALLS_PER_HOUR = 3000


class Refused(RuntimeError):
    pass


def node(lat, lon) -> tuple[np.ndarray, np.ndarray]:
    d = Q2_NODE_DEG
    return (np.round(np.round(np.asarray(lat) / d) * d, 3) + 0.0, np.round(np.round(np.asarray(lon) / d) * d, 3) + 0.0)


def get(url: str, params: dict, n: int, days: int, soil: Path, what: str) -> list[dict]:
    """One request. Its weight is logged whether or not it succeeds: Open-Meteo counts what it was asked."""
    w = call_weight(n, days)
    with open(soil / "calls.jsonl", "a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "what": what, "locations": n, "days": days,
                            "weight": w}) + "\n")
    try:
        r = httpx.get(url, params=params, timeout=180)
    except httpx.HTTPError as e:
        raise Refused(f"{what}: {type(e).__name__}") from None
    if not r.is_success:
        raise Refused(f"{what}: HTTP {r.status_code} {r.text[:200]}")
    try:
        j = r.json()
    except ValueError:
        raise Refused(f"{what}: body is not JSON: {r.text[:200]}") from None
    js = j if isinstance(j, list) else [j]
    if any("hourly" not in x for x in js):
        raise Refused(f"{what}: no hourly block: {str(js)[:200]}")
    time.sleep(3600.0 * w / CALLS_PER_HOUR)
    return js


def frame(r: dict, cl: float, cn: float, var: str) -> pd.DataFrame:
    h = r["hourly"]
    return pd.DataFrame({"cell_lat": cl, "cell_lon": cn, "time": pd.to_datetime(h["time"], utc=True),
                         "sm": np.asarray(h[var], dtype=float), "got_lat": r["latitude"], "got_lon": r["longitude"]})


def fetch(url: str, var: str, extra: dict, cells: list, start: str, end: str, soil: Path, what: str) -> list[pd.DataFrame]:
    params = {"latitude": ",".join(f"{c[0]:.3f}" for c in cells), "longitude": ",".join(f"{c[1]:.3f}" for c in cells),
              "start_date": start, "end_date": end, "hourly": var, "timezone": "UTC", **extra}
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    js = get(url, params, len(cells), days, soil, f"{what} {start}..{end} x{len(cells)}")
    return [frame(r, cl, cn, var) for (cl, cn), r in zip(cells, js, strict=True)]


def pieces(start: str, end: str, freq: str) -> list[tuple[str, str]]:
    s = pd.date_range(start, end, freq=freq + "S")
    return [(a.strftime("%Y-%m-%d"), min(a + pd.offsets.DateOffset(**{"months": 1 if freq == "M" else 3}) - pd.Timedelta(days=1),
                                         pd.Timestamp(end)).strftime("%Y-%m-%d")) for a in s]


def run(url, var, extra, todo, parts, batch, retry_freq, soil, prefix, what):
    """todo: [(year, [cells])]. Each batch of cells and year: the parts, joined; on a refusal, each part again in
    smaller pieces, one cell at a time."""
    failed = []
    for year, cells in todo:
        for i in range(0, len(cells), batch):
            chunk = cells[i:i + batch]
            got: dict = {c: [] for c in chunk}
            for a, b in parts(year):
                try:
                    for c, f in zip(chunk, fetch(url, var, extra, chunk, a, b, soil, what), strict=True):
                        got[c].append(f)
                except Refused as e:
                    print("refused:", e, "- retrying in pieces", flush=True)
                    for c in chunk:
                        for pa, pb in pieces(a, b, retry_freq):
                            try:
                                got[c] += fetch(url, var, extra, [c], pa, pb, soil, what)
                            except Refused as e2:
                                print("still refused:", e2, flush=True)
                                failed.append((c, year, pa, pb))
            for (cl, cn), fs in got.items():
                if fs:
                    pd.concat(fs, ignore_index=True).to_parquet(soil / f"{prefix}_{cell_key(cl, cn)}_{year}.parquet",
                                                                index=False)
            print(f"{what} {year}: {min(i + batch, len(cells))}/{len(cells)}", flush=True)
    print(f"{what}: {len(failed)} pieces failed", failed[:20], flush=True)


def q1_cells(frozen: Path) -> list[tuple[float, float]]:
    rows = pd.read_parquet(frozen / "processed" / "ecoli_validation_rows.parquet", columns=["bw_id"])
    sites = pd.read_parquet(frozen / "raw" / "bwq_samples.parquet", columns=["bw_id", "lat", "lon"]).drop_duplicates("bw_id")
    sites = sites[sites.bw_id.isin(set(rows.bw_id))]
    cl, cn = grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy())
    return sorted(set(zip(cl.tolist(), cn.tolist(), strict=True)))


def q2_nodes() -> list[tuple[float, float]]:
    from dipcast import config
    from dipcast.model.training import NINE, load_events, site_years
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    s = pd.concat([site_years(ar, ev, NINE, y)[0] for y in Q2_YEARS])
    a, b = node(s["lat"].to_numpy(), s["lon"].to_numpy())
    return sorted(set(zip(a.tolist(), b.tolist(), strict=True)))


def main() -> None:
    soil, which = Path(sys.argv[1]), sys.argv[2]
    soil.mkdir(parents=True, exist_ok=True)
    dry = "--dry-run" in sys.argv
    if which == "q1":
        cells = q1_cells(Path(sys.argv[3]))
        todo = [(y, [c for c in cells if not (soil / f"q1_{cell_key(*c)}_{y}.parquet").exists()]) for y in Q1_YEARS]
        cost = sum(call_weight(1, (pd.Timestamp(f"{y}-{b}") - pd.Timestamp(f"{y}-{a}")).days + 1)
                   for y, cs in todo for _ in cs for a, b in Q1_PARTS)
        print(f"q1: {len(cells)} cells; to fetch {sum(len(c) for _, c in todo)} cell-years; weight {cost:.1f}")
        if not dry:
            run(PREVIOUS_RUNS, Q1_VAR, {}, todo, lambda y: [(f"{y}-{a}", f"{y}-{b}") for a, b in Q1_PARTS],
                Q1_BATCH, "M", soil, "q1", "q1")
    elif which == "q2":
        nodes = q2_nodes()
        todo = [(y, [c for c in nodes if not (soil / f"q2_{cell_key(*c)}_{y}.parquet").exists()]) for y in Q2_YEARS]
        cost = sum(call_weight(len(cs), 366 if y == 2024 else 365) for y, cs in todo)
        print(f"q2: {len(nodes)} nodes; to fetch {sum(len(c) for _, c in todo)} node-years; weight {cost:.1f}")
        if not dry:
            run(ARCHIVE, Q2_VAR, {"models": "era5_land"}, todo, lambda y: [(f"{y}-01-01", f"{y}-12-31")],
                Q2_BATCH, "Q", soil, "q2", "q2")
    print("DONE")


if __name__ == "__main__":
    main()
