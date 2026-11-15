"""Backtest bench, staging (docs/BACKTEST-BENCH-2026-11.md): E. coli rows at the 38 inland bathing waters, 2012-2026,
with the production model's inputs rebuilt from archive data as validate_ecoli.py's hindcast builds them.

Off CI, by hand, in a scratch root (AGENTS.md: a worktree alone does not isolate data):

    export DIPCAST_ROOT=<scratch copy of data/> DIPCAST_STATE=<scratch>/state BENCH_OUT=<scratch>/out
    uv run python scripts/backtest_bench/stage.py samples          # EA listings since 2012 (cap 120 requests)
    uv run python scripts/backtest_bench/stage.py cells            # rain and soil cells needed; prints the cost, calls nothing
    uv run python scripts/backtest_bench/stage.py rain --cap 1000  # Open-Meteo archive rain, resumable, stops at the cap
    uv run python scripts/backtest_bench/stage.py soil --cap 300   # river soil moisture (Previous Runs), resumable
    uv run python scripts/backtest_bench/stage.py rows             # one row a sample, seen and held-out parts
    uv run python scripts/backtest_bench/stage.py freeze <store>   # copy rows to the store, write the manifest

Every Open-Meteo or EA request goes in BENCH_OUT/requests.jsonl with its weight. Nothing here reads an outcome
against an input; the scoring is bench.py's.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))   # scripts/: validate_ecoli, eval_pins, lake_range_hindcast

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("backtest_bench")

OUT = Path(os.environ.get("BENCH_OUT", "bench_out"))
TZ = "Europe/London"
FIRST_YEAR, LAST_YEAR = 2012, 2026
SEASON = range(5, 10)
# Years used to fit or choose the production E. coli models (train_ecoli.py, train_ecoli_sm.py read
# bwq_samples.parquet, 2023-26). Every other year is held out from production. Which held-out rows an earlier test
# already scored is recorded per row (`prior_reads`), so a reader can drop them.
SEEN_YEARS = range(2023, 2027)
# Held-out rows already scored by an earlier test, from those tests' own records: #584 (LAKE-RANGE-HINDCAST-TEST)
# and the 2012-22 check of the frozen lake-line models (LAKE-LINE-2012-22-CHECK) read 2012-22 at these five
# bathing waters.
PRIOR_READS = {b: "lake-range-hindcast #584; lake-line 2012-22 check" for b in (
    "ukd1203-45625", "ukd1203-45650", "ukd1203-45675", "ukd1203-45700", "ukj2310-11945")}
EA_CAP = 120
ROW_VERSION = "ecoli-rows-v1"


def ledger(kind: str, n: int, weight: float, note: str = "") -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "requests.jsonl").open("a") as f:
        f.write(json.dumps({"t": pd.Timestamp.now("UTC").isoformat(), "kind": kind, "n": n,
                            "weight": round(weight, 2), "note": note}) + "\n")


def spent(kind: str, today_only: bool = False) -> float:
    p = OUT / "requests.jsonl"
    if not p.exists():
        return 0.0
    day = pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
    tot = 0.0
    for line in p.read_text().splitlines():
        r = json.loads(line)
        if r["kind"] == kind and (not today_only or r["t"][:10] == day):
            tot += r["weight"]
    return tot


def sites() -> dict[str, dict]:
    from dipcast import config
    return {s["id"]: s for s in json.loads((config.RAW / "bathing_waters_inland.json").read_text())}


# ------------------------------------------------------------------ samples
def stage_samples() -> None:
    from dipcast.ingest.bwq import fetch_point
    frames, n = [], 0
    for bw_id, s in sorted(sites().items()):
        if n >= EA_CAP:
            raise SystemExit(f"EA cap {EA_CAP} reached before {bw_id}")
        df = pd.DataFrame(fetch_point(bw_id.split("-")[-1], since=f"{FIRST_YEAR}-01-01T00:00:00"))
        n += max(1, -(-len(df) // 500))
        ledger("ea", max(1, -(-len(df) // 500)), 0.0, bw_id)
        if df.empty:
            log.info("%s: none listed", s["name"]); continue
        df["bw_id"], df["name"], df["kind"], df["lat"], df["lon"] = bw_id, s["name"], s["kind"], s["lat"], s["lon"]
        df["undertaker"] = s.get("undertaker")
        frames.append(df)
        time.sleep(0.5)
    out = pd.concat(frames, ignore_index=True)
    out["sample_time"] = pd.to_datetime(out["sample_time"]).dt.tz_localize(
        TZ, ambiguous="NaT", nonexistent="shift_forward")
    for c in ["ecoli", "ie"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    st = out["sample_time"]
    out = out[st.notna() & st.dt.month.isin(SEASON) & st.dt.year.between(FIRST_YEAR, LAST_YEAR)]
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT / "samples.parquet", index=False)
    log.info("%d EA requests; %d in-season samples at %d sites", n, len(out), out["bw_id"].nunique())
    print(out.groupby(["kind", out["sample_time"].dt.year]).size().unstack(fill_value=0).to_string())


def samples() -> pd.DataFrame:
    s = pd.read_parquet(OUT / "samples.parquet").dropna(subset=["ecoli", "sample_time"])
    s = s.drop_duplicates(["bw_id", "sample_time"]).copy()
    s["day"] = s["sample_time"].dt.floor("D")
    return s


# ------------------------------------------------------------------ cells and cost
def network():
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import load_overflows
    net = RiverNetwork.load()
    return net, load_overflows(net)


def site_up(net, ov, bw_id: str, lat: float, lon: float) -> pd.DataFrame:
    from lake_range_hindcast import _site_up
    try:
        return _site_up(net, ov, bw_id, lat, lon)[1]
    except KeyError:
        return pd.DataFrame()


def rain_cells(s: pd.DataFrame, net, ov) -> dict[int, list[tuple[float, float]]]:
    """Cells needed for each year: the spot's rain cell and every upstream overflow's, in the years the spot has
    samples (and the year before, for the first weeks of a season's exposure history)."""
    from dipcast.ingest.rainfall import grid_cell
    need: dict[int, set] = {}
    for bw_id, g in s.groupby("bw_id"):
        r = g.iloc[0]
        cells = {tuple(float(v) for v in grid_cell(float(r["lat"]), float(r["lon"])))}
        up = site_up(net, ov, bw_id, float(r["lat"]), float(r["lon"]))
        if len(up):
            cells |= {(float(a), float(b)) for a, b in zip(*grid_cell(up["lat"].to_numpy(), up["lon"].to_numpy()),
                                                         strict=True)}
        for y in sorted(g["sample_time"].dt.year.unique()):
            need.setdefault(int(y), set()).update(cells)
    return {y: sorted(c) for y, c in sorted(need.items())}


def cached(cell: tuple[float, float], year: int) -> bool:
    from dipcast import config
    from dipcast.ingest.rainfall import cell_key
    return (config.CACHE / "rain" / f"archive_{cell_key(*cell)}_{year}.parquet").exists() or \
        (config.CACHE / f"archive_{cell_key(*cell)}_{year}.parquet").exists()


ARCHIVE_WEIGHT = max(1.0, 0.1 * 365 / 14)   # Open-Meteo's weight for one location-year of one hourly variable


def stage_cells() -> None:
    s = samples()
    net, ov = network()
    need = rain_cells(s, net, ov)
    rows, todo_w = [], 0.0
    for y, cells in need.items():
        missing = [c for c in cells if not cached(c, y)]
        w = len(missing) * ARCHIVE_WEIGHT
        todo_w += w
        rows.append({"year": y, "cells": len(cells), "missing": len(missing), "weight": round(w, 1)})
    (OUT / "cells.json").write_text(json.dumps({str(y): c for y, c in need.items()}))
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"rain still to fetch: about {todo_w:.0f} weighted Open-Meteo calls")


# ------------------------------------------------------------------ rain
def stage_rain(cap: float) -> None:
    """Archive rain for the missing cell-years, one year at a time, into DIPCAST_ROOT's cache (scratch). Stops before
    the day's spend would pass `cap` weighted calls; rerun on a later day to continue."""
    from dipcast import config
    from dipcast.ingest.rainfall import OpenMeteoError, fetch_archive
    assert "DIPCAST_ROOT" in os.environ, "set DIPCAST_ROOT to a scratch copy: this writes the rain cache"
    need = {int(y): [tuple(c) for c in v] for y, v in json.loads((OUT / "cells.json").read_text()).items()}
    for y in sorted(need):
        missing = [c for c in need[y] if not cached(c, y)]
        while missing:
            room = cap - spent("open-meteo-archive", today_only=True)
            n = int(room // ARCHIVE_WEIGHT)
            if n <= 0:
                log.info("cap %s reached today; %d cell-years left in %d", cap, len(missing), y); return
            chunk = missing[:min(n, 50)]
            try:
                fetch_archive(chunk, y, strict=True)
            except OpenMeteoError as e:
                ledger("open-meteo-archive", len(chunk), len(chunk) * ARCHIVE_WEIGHT, f"{y} refused: {e}")
                log.error("refused at %d: %s; stop and retry another day", y, e); return
            ledger("open-meteo-archive", len(chunk), len(chunk) * ARCHIVE_WEIGHT, str(y))
            missing = [c for c in missing if not cached(c, y)]
            if any(c in missing for c in chunk):
                raise SystemExit(f"{y}: cells still missing after a fetch: {[c for c in chunk if c in missing][:5]}")
        log.info("%d: all %d cells cached (%s)", y, len(need[y]), config.CACHE)


# ------------------------------------------------------------------ soil (river model)
def stage_soil(cap: float) -> None:
    """`sm` for river rows, as train_ecoli_sm.py reads it: Previous Runs lead 0, models=ecmwf_ifs,
    soil_moisture_9_to_27cm at the sample's rain cell, fetched per cell-quarter by soil_moisture_eval/fetch.py."""
    sys.path.insert(0, str(HERE.parent / "soil_moisture_eval"))
    from fetch import PREVIOUS_RUNS, Q1_VAR, Refused, fetch

    from dipcast import config
    from dipcast.ingest.rainfall import grid_cell
    from fetch import call_weight

    from dipcast.ingest.rainfall import cell_key
    assert "DIPCAST_ROOT" in os.environ, "set DIPCAST_ROOT to a scratch copy: this writes the soil cache"
    s = samples()
    s = s[s["kind"] == "river"].copy()
    cl, cn = grid_cell(s["lat"].to_numpy(), s["lon"].to_numpy())
    s["cl"], s["cn"], s["y"] = cl, cn, s["sample_time"].dt.tz_convert("UTC").dt.year
    soil = config.CACHE / "soil"
    todo = sorted({(float(a), float(b), int(y)) for a, b, y in zip(s["cl"], s["cn"], s["y"], strict=True)
                   if not (soil / f"q1_{cell_key(a, b)}_{y}.parquet").exists()})
    log.info("%d river cell-years without a soil file", len(todo))
    for a, b, y in todo:
        start, end = f"{y}-04-25", f"{y}-09-30"   # the season, and the days before its first issue
        w = call_weight(1, (pd.Timestamp(end) - pd.Timestamp(start)).days + 1)
        if spent("open-meteo-soil", today_only=True) + w > cap:
            log.info("soil cap reached"); return
        try:
            f = fetch(PREVIOUS_RUNS, Q1_VAR, {"models": "ecmwf_ifs"}, [(a, b)], start, end, soil, "bench")[0]
        except Refused as e:
            ledger("open-meteo-soil", 1, w, f"{a},{b} {y} refused: {e}")
            log.error("refused: %s", e); continue
        ledger("open-meteo-soil", 1, w, f"{a},{b} {y}")
        f.to_parquet(soil / f"q1_{cell_key(a, b)}_{y}.parquet", index=False)
        log.info("%s,%s %d: %d hours, %d with a value", a, b, y, len(f), int(f["sm"].notna().sum()))


# ------------------------------------------------------------------ rows
def stage_rows() -> None:
    from validate_ecoli import load_rain

    from dipcast.model.ecoli import features
    from dipcast.model.features import daily_rain_features
    from dipcast.model.spill_model import SpillModel
    from lake_range_hindcast import build_rows
    s = samples()
    net, ov = network()
    model = SpillModel.load()
    rain = load_rain()
    hourly = rain.set_index(["cell_lat", "cell_lon"]).sort_index()
    daily = daily_rain_features(rain)
    # Sites with no monitored overflow upstream: production's exposure is 0 there (validate_ecoli.main). build_rows
    # handles only sites with overflows upstream, so these are built here with risk 0 and the same rain windows.
    has_up = {b: len(site_up(net, ov, b, float(g.iloc[0].lat), float(g.iloc[0].lon))) > 0
              for b, g in s.groupby("bw_id")}
    with_up = s[s["bw_id"].map(has_up)]
    rows, drops = build_rows(with_up, net, ov, model, hourly, daily)
    rows_none, drops_none = rows_no_upstream(s[~s["bw_id"].map(has_up)], hourly)
    rows = pd.concat([rows, rows_none], ignore_index=True)
    rows["lake"] = (rows["kind"] == "lake").astype(float)
    X = features(rows["rain_48h"], rows["rain_24h"], rows["risk_model"], rows["lake"], rows["sample_time"])
    rows = pd.concat([rows.reset_index(drop=True), X.drop(columns=["lake"])], axis=1)
    rows = add_sm(rows)
    rows = finish(rows)
    audit = {"drops_with_upstream": drops, "drops_no_upstream": drops_none, "rows": len(rows),
             "by_part": rows.groupby("part").size().to_dict(),
             "by_part_kind": {f"{a}/{b}": int(n) for (a, b), n in rows.groupby(["part", "kind"]).size().items()}}
    rows.to_parquet(OUT / "rows.parquet", index=False)
    (OUT / "rows_audit.json").write_text(json.dumps(audit, indent=1, default=str))
    log.info("%s", audit)


def rows_no_upstream(s: pd.DataFrame, hourly) -> tuple[pd.DataFrame, dict]:
    from dipcast.ingest.rainfall import grid_cell
    from dipcast.model.ecoli import rain_windows
    out, drops = [], {"no_site_rain": 0, "rain_window": 0}
    for _, g in s.groupby("bw_id"):
        r = g.iloc[0]
        cl, cn = (float(v) for v in grid_cell(float(r["lat"]), float(r["lon"])))
        try:
            site_rain = hourly.loc[(cl, cn)].set_index("time")["precip_mm"].sort_index()
        except KeyError:
            drops["no_site_rain"] += len(g); continue
        g = g.sort_values("sample_time").reset_index(drop=True)
        g["rain_48h"], g["rain_24h"] = rain_windows(site_rain, pd.DatetimeIndex(g["sample_time"]))
        g["risk_model"], g["missing_share"], g["upstream"] = 0.0, 0.0, 0
        bad = g["rain_48h"].isna() | g["rain_24h"].isna()
        drops["rain_window"] += int(bad.sum())
        out.append(g[~bad])
    return (pd.concat(out, ignore_index=True) if out else pd.DataFrame()), drops


def add_sm(rows: pd.DataFrame) -> pd.DataFrame:
    """`sm` at river rows from the soil cache, as soil_moisture_eval/leads.py reads it (lead 0, 00:00 UTC of the
    sample day); NaN where not cached. Lakes keep NaN: production's lake model has no `sm`."""
    sys.path.insert(0, str(HERE.parent / "soil_moisture_eval"))
    from leads import soil_at_issue

    from dipcast import config
    rows["sm"] = np.nan
    riv = (rows["kind"] == "river").to_numpy()
    if riv.any():
        rows.loc[riv, "sm"] = soil_at_issue(rows.loc[riv].reset_index(drop=True), config.CACHE / "soil", 0)
    return rows


def finish(rows: pd.DataFrame) -> pd.DataFrame:
    from dipcast.model.ecoli import THRESHOLD
    rows = rows.sort_values(["bw_id", "sample_time"]).reset_index(drop=True)
    rows["season"] = rows["sample_time"].dt.year
    rows["month"] = rows["sample_time"].dt.month
    rows["over"] = (rows["ecoli"] > THRESHOLD).astype(int)
    rows["log_ecoli"] = np.log10(rows["ecoli"].clip(lower=1))
    rows["part"] = np.where(rows["season"].isin(SEEN_YEARS), "seen", "heldout")
    rows["prior_reads"] = rows["bw_id"].map(PRIOR_READS).where(rows["part"] == "heldout", None)
    # The previous sample's result at the same site in the same season, known at least 3 days before (lab
    # turnaround; BENCH-ECOLI900's review variant): a reference input, not production's.
    prev = []
    for _, g in rows.groupby(["bw_id", "season"], sort=False):
        t, o = g["sample_time"].to_numpy(), g["over"].to_numpy()
        for i in range(len(g)):
            k = [j for j in range(i) if (t[i] - t[j]) >= np.timedelta64(3, "D")]
            prev.append(float(o[k[-1]]) if k else np.nan)
    rows["prev_over_3d"] = prev
    rows["row_version"] = ROW_VERSION
    return rows


# ------------------------------------------------------------------ freeze
def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze(store: Path) -> None:
    """Split rows into seen.parquet and heldout.parquet in the store (outside git: rows hold values derived from
    Open-Meteo, which BENCH-ECOLI900 keeps out of published files), and write manifest.json with their hashes and the
    hashes of the code and models that built them. bench.py refuses rows whose hash does not match."""
    from dipcast import config
    rows = pd.read_parquet(OUT / "rows.parquet")
    store.mkdir(parents=True, exist_ok=True)
    files = {}
    for part in ("seen", "heldout"):
        p = store / f"{part}.parquet"
        rows[rows["part"] == part].reset_index(drop=True).to_parquet(p, index=False)
        files[part] = {"sha256": sha(p), "rows": int((rows["part"] == part).sum()),
                       "sites": int(rows.loc[rows["part"] == part, "bw_id"].nunique()),
                       "over": int(rows.loc[rows["part"] == part, "over"].sum()),
                       "seasons": sorted(int(x) for x in rows.loc[rows["part"] == part, "season"].unique())}
    inputs = {n: sha(config.PROCESSED / n) for n in
              ("ecoli_model.json", "ecoli_model_sm.json", "lead_calibration.json", "spill_model.pkl")
              if (config.PROCESSED / n).exists()}
    code = {str(p.relative_to(HERE.parents[1])): sha(p) for p in
            [HERE / "stage.py", HERE.parent / "validate_ecoli.py", HERE.parent / "lake_range_hindcast.py"]}
    m = {"bench": "ecoli-v1", "row_version": ROW_VERSION, "frozen_at": pd.Timestamp.now("UTC").isoformat(),
         "files": files, "inputs": inputs, "code": code,
         "audit": json.loads((OUT / "rows_audit.json").read_text()),
         "requests": [json.loads(x) for x in (OUT / "requests.jsonl").read_text().splitlines()]
         if (OUT / "requests.jsonl").exists() else []}
    (store / "manifest.json").write_text(json.dumps(m, indent=1, default=str))
    print(json.dumps({k: m[k] for k in ("files", "inputs")}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["samples", "cells", "rain", "soil", "rows", "freeze"])
    ap.add_argument("store", nargs="?")
    ap.add_argument("--cap", type=float, default=1000.0)
    a = ap.parse_args()
    if a.step == "samples":
        stage_samples()
    elif a.step == "cells":
        stage_cells()
    elif a.step == "rain":
        stage_rain(a.cap)
    elif a.step == "soil":
        stage_soil(a.cap)
    elif a.step == "rows":
        stage_rows()
    else:
        freeze(Path(a.store))


if __name__ == "__main__":
    main()
