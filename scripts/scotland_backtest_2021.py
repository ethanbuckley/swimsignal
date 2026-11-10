"""Scotland trial: frozen-model backtest on 2021 (docs/SCOTLAND-2021-BACKTEST-2026-11.md). Off CI; publishes nothing.

The protocol, its pass rule and its amendments are in that file, committed before either archived file was
downloaded. This script carries them out and changes none of them. Contains Scottish Water data licensed under the
Open Government Licence v3.0.

    E="--edition-2017 <dir>/sepa-2017-2021.xlsx --edition-2020 <dir>/sepa-2020-2024.xlsx"
    DIPCAST_ROOT=<scratch root> DIPCAST_CACHE=<scratch cache> uv run python scripts/scotland_backtest_2021.py $E --dry-run
    ... --fetch --until-done --max-total 2200        # Open-Meteo, paced, booked in the scratch cache's ledger
    ... --out <dir>                                    # score; refuses while any needed cell-year is missing

The dry run makes no forecast and joins no label to a forecast: it runs the protocol's checks (section 5) and
counts the overflows and the rain the test needs. The fetch books every request in the ration ledger
(rainfall.spend) by the scripts' count (archive_calls, days / 14 a cell-year), the larger of the two counts the
protocol names, so DIPCAST_OPEN_METEO_DAILY_CALLS=1000 caps the UTC day at 1,000 by that count.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_scotland_history as fsh
import hindcast_scotland as hs
import hindcast_wales as hw
from fetch_wales_history import archive_calls, archive_days

from dipcast import config
from dipcast.ingest import rainfall, scottish_water, sw_archive, sw_covariates, sw_history
from dipcast.model.forecast import calibrate_at_lead
from dipcast.model.spill_model import SpillModel

log = logging.getLogger("scotland_backtest_2021")

TEST_YEAR = 2021
HISTORY_FROM_2020 = [2020]               # from the 2020-2024 edition
HISTORY_FROM_2017 = [2017, 2018, 2019]   # from the 2017-2021 edition
LEVEL_RANGE = (0.9, 1.1)
WHAT = "scotland-2021-backtest"          # the ledger's name for these requests
CELLS_PER_REQUEST = 3                    # 78 calls by the scripts' count, so a day's 1,000 is used closely
PER_HOUR = 500.0
MAP_FILE = config.PROCESSED / "scotland_calibration.json"
REPORTED = sw_history.RAW_DIR / sw_history.FILES["Scottish Water reported 2021-2025"][0]
NON_REPORTED = sw_history.RAW_DIR / sw_history.FILES["Scottish Water non-reported 2022-2025"][0]
SRC_2020 = "Scottish Water reported 2020-2024 (archived 7 Oct 2025)"
SRC_2017 = "Scottish Water reported 2017-2021 (archived 19 Dec 2022)"
MAPPED, ENGLAND = "trial forecast (production, Scotland's map)", "production, England's lead-0 calibration"



def use_2021() -> None:
    """Gate A's code reads these module constants at call time. Set them for this run only, from main, so that
    importing this script (as its tests do) leaves Gate A's own defaults alone."""
    hs.TEST_YEARS = [TEST_YEAR]
    hs.FIRST_RAIN_YEAR = TEST_YEAR - 1


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def input_hashes(args) -> dict:
    files = [hs.PRODUCTION, hs.MODEL, MAP_FILE, hs.COVARIATES, hs.EVENTS, fsh.YEARLY, hs.API_ANSWER,
             REPORTED, NON_REPORTED, config.PROCESSED / "lead_calibration.json", args.edition_2017, args.edition_2020]
    return {p.name: sha256(p) for p in files}


# ---------------------------------------------------------------------------
# Inputs: local events plus the archived years
# ---------------------------------------------------------------------------

def archived(args) -> dict:
    """Each archived edition loaded once, every year; the protocol's years are picked from these."""
    cur = [sw_history.read_workbook(REPORTED)[0], sw_history.read_workbook(NON_REPORTED)[0]]
    return {"2020": sw_archive.load(args.edition_2020, SRC_2020, cur),
            "2017": sw_archive.load(args.edition_2017, SRC_2017, cur)}


def combine(arc: dict, first_history_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Local events and yearly rows (2021 on) plus the archived years from first_history_year to 2020, each
    year from the newest edition holding it (protocol, section 4)."""
    ev, yr = pd.read_parquet(hs.EVENTS), pd.read_parquet(fsh.YEARLY)
    evs, yrs = [ev], [yr]
    for key, years in (("2020", HISTORY_FROM_2020), ("2017", HISTORY_FROM_2017)):
        e, y, _ = arc[key]
        keep = [v for v in years if v >= first_history_year]
        evs.append(e[e["year"].isin(keep)])
        yrs.append(y[y["year"].isin(keep)])
    return pd.concat(evs, ignore_index=True), pd.concat(yrs, ignore_index=True)


def build(ev: pd.DataFrame, yearly: pd.DataFrame, first_year: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(overflow-years, covariates, labels) as fetch_scotland_history and hindcast_scotland build them."""
    cov = sw_covariates.covariates(ev, yearly, first_year=first_year)
    api = scottish_water.parse(json.loads(hs.API_ANSWER.read_text()), pd.Timestamp.now("UTC"))
    sites = fsh.history_sites(cov, ev, api)
    cov = cov.merge(sites, on="site_id", how="left").merge(
        api[["site_id", "asset_type", "emergency"]].assign(in_api=True), on="site_id", how="left")
    cov["in_api"] = cov["in_api"].fillna(False).astype(bool)
    oy = hs.overflow_years(cov, hs.emergency_by_name(ev), hs.authorities(hs.API_ANSWER))
    return oy, cov, hs.labels(ev)


def check_covariates_unchanged() -> dict:
    """Protocol check 2: the rule with first_year 2021 on the local events reproduces the committed table."""
    ev, yr = pd.read_parquet(hs.EVENTS), pd.read_parquet(fsh.YEARLY)
    new = sw_covariates.covariates(ev, yr, first_year=2021).sort_values(["site_id", "year"]).reset_index(drop=True)
    old = pd.read_parquet(hs.COVARIATES)[sw_covariates.COLS].sort_values(["site_id", "year"]).reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(new, old, check_dtype=False)
        return {"reproduced": True, "rows": len(old)}
    except AssertionError as e:
        return {"reproduced": False, "rows": len(old), "why": str(e)[:500]}


def overlaps(arc: dict) -> dict:
    """Protocol check 3, counts only: per-overflow 12/24 counts where two editions hold the same year."""
    def compare(a: pd.DataFrame, b: pd.DataFrame) -> dict:
        m = a[["site_id", "spills_12_24"]].merge(b[["site_id", "spills_12_24"]], on="site_id", suffixes=("_a", "_b"))
        m = m.dropna()
        return {"overflows_in_both": len(m), "equal": int((m["spills_12_24_a"] == m["spills_12_24_b"]).sum()),
                "sum_abs_difference": int((m["spills_12_24_a"] - m["spills_12_24_b"]).abs().sum())}
    y20, y17 = arc["2020"][1], arc["2017"][1]
    loc = pd.read_parquet(fsh.YEARLY)
    loc21 = loc[(loc["year"] == TEST_YEAR) & loc["source"].str.contains("reported 2021")]
    return {"2020: 2020-2024 vs 2017-2021 edition": compare(y20[y20["year"] == 2020], y17[y17["year"] == 2020]),
            "2021: 2017-2021 edition vs local": compare(y17[y17["year"] == TEST_YEAR], loc21)}


def bathing_season_only() -> set[str]:
    """Asset IDs the local reported summary flags as reporting in the bathing season only."""
    from openpyxl import load_workbook
    wb = load_workbook(REPORTED, read_only=True, data_only=True)
    try:
        ws = wb[next(n for n in wb.sheetnames if n.startswith("Overflow Summary"))]
        rows = ws.iter_rows(values_only=True)
        next(rows)
        head = [str(h or "").strip().lower() for h in next(rows)]
        ia, ib = head.index("asset id"), next(i for i, h in enumerate(head) if h.startswith("bathing season"))
        return {str(r[ia]).strip() for r in rows if r[ia] and r[ib] not in (None, "")}
    finally:
        wb.close()


# ---------------------------------------------------------------------------
# Rain: needs, and the booked, paced fetch
# ---------------------------------------------------------------------------

def plan(need: set) -> list[tuple[int, int, list[tuple[float, float]]]]:
    out = []
    for year in sorted({k[2] for k in need}, reverse=True):
        todo = sorted((a, b) for a, b, y in hs.missing("archive", need) if y == year)
        out += [(1, year, todo[i:i + CELLS_PER_REQUEST]) for i in range(0, len(todo), CELLS_PER_REQUEST)]
    return out


def fetch_booked(chunk: list[tuple[float, float]], year: int) -> None:
    """One archive request, booked in the ledger by the scripts' count; refused if the day has no room."""
    w = archive_calls(len(chunk), archive_days(year))
    if not rainfall.may_spend(w, WHAT):
        raise RuntimeError(f"ration: {rainfall.calls_left():.0f} of {rainfall.DAILY_CALLS:.0f} calls left today")
    try:
        rainfall.fetch_archive(chunk, year, strict=True)
    finally:
        rainfall.spend(w, WHAT)          # a refused request may still count


def other_open_meteo_jobs() -> list[str]:
    """Other processes on this Mac that look like Open-Meteo jobs (fetch or build scripts), by command line."""
    out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True).stdout.splitlines()
    marks = ("fetch_scotland_history", "fetch_wales_history", "build_site", "hindcast_", "fetch_rain", "verify_leads")
    return [s.strip()[:160] for s in out if any(m in s for m in marks) and "scotland_backtest_2021" not in s]


def seconds_to_next_utc_day(pad_s: float = 300) -> float:
    now = pd.Timestamp.now("UTC")
    return (now.normalize() + pd.Timedelta(days=1) - now).total_seconds() + pad_s


def fetch(need: set, max_total: float, until_done: bool, log_path: Path) -> dict:
    """Fetch the missing cell-years in `need` within the day's ration, and with --until-done day after day,
    never past max_total calls in all (the running total is kept in log_path)."""
    hist = json.loads(log_path.read_text()) if log_path.exists() else {"calls": 0.0, "runs": []}
    while True:
        todo = plan(need)
        if not todo:
            break
        jobs = other_open_meteo_jobs()
        budget = min(rainfall.calls_left(), max_total - hist["calls"])
        first = archive_calls(len(todo[0][2]), archive_days(todo[0][1]))
        if jobs:
            log.warning("other Open-Meteo jobs running, not fetching: %s", jobs)
        if jobs or budget < first:
            if not until_done or max_total - hist["calls"] < first:
                break
            wait = 900 if jobs else seconds_to_next_utc_day()
            log.info("waiting %.0f min (budget %.0f, %d requests left)", wait / 60, budget, len(todo))
            time.sleep(wait)
            continue
        done = fsh.fetch_paced(todo, budget, PER_HOUR, fetch=fetch_booked)
        hist["calls"] += done["calls"]
        hist["runs"].append({"at": pd.Timestamp.now("UTC").isoformat(), **done})
        log_path.write_text(json.dumps(hist, indent=1))
        log.info("fetched %d cell-years, %.0f calls; %.0f in all; stopped: %s", done["cell_years"], done["calls"],
                 hist["calls"], done["stopped"])
        if done["stopped"] and done["stopped"].startswith("refused") and "ration" not in done["stopped"]:
            break
        if not until_done:
            break
    return {"missing": len(hs.missing("archive", need)), "calls_in_all": hist["calls"]}


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------

def apply_map(m: dict, p: np.ndarray) -> np.ndarray:
    q = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return 1 / (1 + np.exp(-(m["a"] + m["b"] * np.log(q / (1 - q)))))


def rows_for(oy, cov, lab, models: dict, m: dict) -> pd.DataFrame:
    """G(2021)'s scored rows: Gate A's arms plus the trial forecast and England's lead-0 calibration."""
    g = oy[oy["set"] == "G"]
    daily = hs.daily_rain_features(hs.load_rain("archive", hs.rain_needs(g)))
    df = hs._set_rows(oy, cov, lab, daily, "G", models)
    if df.empty:
        return df
    df[MAPPED] = apply_map(m, df[hs.PROD].to_numpy())
    df[ENGLAND] = calibrate_at_lead(df[hs.PROD].to_numpy(), 0)
    return hs._finish(df)


def rule(df: pd.DataFrame, n_boot: int) -> dict:
    """B1 to B3 and the minimum (protocol, section 6)."""
    if df.empty:
        return {"overflows": 0, "rows": 0, "spill_days": 0, "verdict": "NOT COMPLETE"}
    n_sites, n_sd = int(df["site_id"].nunique()), int(df["y"].sum())
    out = {"overflows": n_sites, "rows": len(df), "spill_days": n_sd}
    if n_sites < hs.MIN_SITES or n_sd < hs.MIN_SPILL_DAYS:
        return {**out, "verdict": "NOT COMPLETE"}
    p = df[MAPPED].to_numpy()
    s = hw.Scorer(df, n_boot).summary(p, {"earlier_years": df[hs.EARLIER].to_numpy(),
                                          "unmapped": df[hs.PROD].to_numpy()}, auc_ci=False)
    level = float(p.sum() / n_sd)
    parts = {"B1": bool(s["bss_vs_earlier_years_ci"][0] > 0),
             "B2": bool(LEVEL_RANGE[0] <= level <= LEVEL_RANGE[1]),
             "B3": bool(s["bss_vs_unmapped_ci"][0] > 0)}
    return {**out, **s, "level": level, "parts": parts, "verdict": "PASS" if all(parts.values()) else "FAIL"}


def reported(df: pd.DataFrame, n_boot: int) -> dict:
    sc = hw.Scorer(df, n_boot)
    refs = {"earlier_years": df[hs.EARLIER].to_numpy(), "flat": df[hs.FLAT].to_numpy()}
    arms = {}
    for k in (MAPPED, hs.PROD, ENGLAND, hs.SCOT, hs.DEFAULT, hs.EARLIER, hs.FLAT):
        p = df[k].to_numpy()
        arms[k] = {**sc.summary(p, refs, auc_ci=k in (MAPPED, hs.SCOT)), "level": float(p.sum() / max(sc.y.sum(), 1))}
    y = df["y"].to_numpy()
    wet = df["wet"].to_numpy()
    return {"weeks": sc.nw, "base_rate": float(y.mean()), "arms": arms,
            "reliability": hw._reliability(y, df[MAPPED].to_numpy()),
            "wet_dry": {name: {"rows": int(sel.sum()), "spill_days": int(y[sel].sum()),
                               "level": float(df.loc[sel, MAPPED].sum() / max(y[sel].sum(), 1)),
                               **hw.Scorer(df[sel], n_boot).summary(
                                   df.loc[sel, MAPPED].to_numpy(), {"earlier_years": df.loc[sel, hs.EARLIER].to_numpy()},
                                   auc_ci=False)}
                        for name, sel in (("wet", wet), ("dry", ~wet)) if len(set(y[sel])) == 2},
            "by_type": hs.score_groups(df, "type", MAPPED, n_boot),
            "by_authority": hs.score_groups(df, "authority", MAPPED, n_boot)}


def main(argv: list[str] | None = None) -> dict:
    use_2021()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--edition-2017", type=Path, required=True)
    ap.add_argument("--edition-2020", type=Path, required=True)
    ap.add_argument("--out", type=Path, help="folder for the summary (scoring)")
    ap.add_argument("--n-boot", type=int, default=hs.N_BOOT)
    ap.add_argument("--dry-run", action="store_true", help="checks and counts; no forecast, no fetch")
    ap.add_argument("--fetch", action="store_true", help="fetch the missing rain, booked and paced; no score")
    ap.add_argument("--until-done", action="store_true", help="with --fetch: keep going day after day")
    ap.add_argument("--max-total", type=float, default=2200, help="calls in all, by the scripts' count")
    ap.add_argument("--seed-cache-from", type=Path, help="copy needed cell-years cached here (read only) first")
    args = ap.parse_args(argv)

    before = input_hashes(args)
    arc = archived(args)
    first = min(int(arc["2017"][1]["year"].min()), min(HISTORY_FROM_2020))
    ev, yr = combine(arc, first)
    oy, cov, lab = build(ev, yr, first)
    g = oy[oy["set"] == "G"]
    need = hs.rain_needs(g)
    if args.seed_cache_from:
        import shutil
        for k in sorted(hs.missing("archive", need)):
            src = args.seed_cache_from / hs.rain_path("archive", k).name
            if src.exists():
                hs.rain_path("archive", k).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, hs.rain_path("archive", k))
    miss = hs.missing("archive", need)
    cover = {"first_history_year": first, "G_overflows": int(g["site_id"].nunique()),
             "eligible_2021": int((oy["eligible"] & (oy["year"] == TEST_YEAR)).sum()),
             "cells": len({(a, b) for a, b, _ in need}), "cell_years_needed": len(need),
             "cell_years_missing": {str(y): sum(1 for k in miss if k[2] == y) for y in (TEST_YEAR, TEST_YEAR - 1)},
             "calls_missing_scripts_count": round(hs.archive_calls_for(miss)),
             "calls_missing_open_meteo_rule": round(sum(rainfall.call_weight(1, archive_days(k[2])) for k in miss), 1)}
    print(json.dumps(cover, indent=1))
    if args.dry_run:
        checks = {"covariates": check_covariates_unchanged(), "overlaps": overlaps(arc),
                  "bathing_season_only_in_G": sorted(set(g["site_id"]) & bathing_season_only())}
        print(json.dumps(hw.clean(checks), indent=1))
        return {"coverage": cover, "checks": checks}
    if args.fetch:
        done = fetch(need, args.max_total, args.until_done, config.CACHE / "rain" / f"{WHAT}.json")
        print(json.dumps(done, indent=1))
        return done

    if miss:
        raise SystemExit(f"Not scoring: {len(miss)} of {len(need)} cell-years are not cached.")
    if not args.out:
        raise SystemExit("--out is needed to score")
    m = json.loads(MAP_FILE.read_text())
    prod, hold = SpillModel.load(hs.PRODUCTION), SpillModel.load(hs.MODEL)
    if m.get("spill_stamp") != "808da63d":
        raise SystemExit(f"map stamped for {m.get('spill_stamp')}, not 808da63d")
    models = {"holdout": hold, "production": prod}
    df = rows_for(oy, cov, lab, models, m)
    result = {"rule": rule(df, args.n_boot)}
    if result["rule"]["verdict"] != "NOT COMPLETE":
        result["reported"] = reported(df, args.n_boot)
        flagged = bathing_season_only()
        result["without_bathing_season_only"] = {"dropped": sorted(set(df["site_id"]) & flagged),
                                                 **rule(df[~df["site_id"].isin(flagged)].reset_index(drop=True), args.n_boot)}
        ev20, yr20 = combine(arc, 2020)
        oy20, cov20, lab20 = build(ev20, yr20, 2020)
        df20 = rows_for(oy20, cov20, lab20, models, m)
        result["history_from_2020_only"] = rule(df20, args.n_boot)
    after = input_hashes(args)
    out = {"written": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
           "what": "Scotland trial, frozen-model backtest on 2021 (docs/SCOTLAND-2021-BACKTEST-2026-11.md). "
                   "Summary scores only; no Scottish Water rows.",
           "model": prod.trained_on, "map": {k: m[k] for k in ("a", "b", "spill_stamp", "fitted_on")},
           "bootstrap": {"draws": args.n_boot, "seed": hs.SEED, "clusters": "overflows x ISO weeks"},
           "coverage": cover, **result, "inputs_sha256": before, "inputs_unchanged": before == after,
           "source": "Contains Scottish Water data licensed under the Open Government Licence v3.0."}
    out = hw.clean(out)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "SCOTLAND-2021-BACKTEST-2026-11.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"verdict": out["rule"]["verdict"], "parts": out["rule"].get("parts")}, indent=1))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main(sys.argv[1:])
