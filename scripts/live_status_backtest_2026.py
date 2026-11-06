"""The live-status candidates (PR #254) scored on January to August 2026: a frozen-model backtest, as stated in
docs/LIVE-STATUS-BACKTEST-2026-11.md. Off CI, by hand, offline (no Open-Meteo call, no download):

    DIPCAST_ROOT=<scratch root> DIPCAST_STATE=<scratch state> DIPCAST_CACHE=<rain cache, read-only> PYTHONPATH=src \\
        python scripts/live_status_backtest_2026.py count|run --events2026 <dir> --events2025 <dir> \\
        --coverage <live_coverage.parquet> --zip2026 <2026 zip> --d2 <spill_model_nine_2024.pkl> --out <dir>

`count` builds the rows and prints how many there are per company and lead, and how many have an unknown status.
It reads no label and computes no forecast. `run` scores the candidates against #254's baseline (D2's model) and
against production, with ERA5-Land rain and with archived forecast rain, and checks #254's five conditions.

Status is rebuilt by #254's own code (scripts/live_status_test.py: Status, merged_intervals, the 00:00 UTC issue
time), imported unchanged with its dates moved to 2025-26. The forecast-rain rows and features are #254's
(RainGrid, the 72-hour window, rain_features). The 2026 rows are PR #357's window E on UTC days; its two-way
bootstrap is copied below.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_status_test as lst  # noqa: E402  (#254's code, used unchanged)

from dipcast import config  # noqa: E402
from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features, spill_days  # noqa: E402
from dipcast.model.forecast import _apply  # noqa: E402  (production's lead map, as the site applies it)
from dipcast.model.spill_model import SpillModel  # noqa: E402
from dipcast.model.training import MIN_EDM_PCT, NINE, ece  # noqa: E402
from dipcast.model.verify import reliability_table, scores  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True)
log = logging.getLogger("live_status_backtest_2026")
_T0 = time.time()

# ---------------------------------------------------------------- frozen inputs (the statement's hashes)
CANDIDATE_SHA = {
    0: "deb5e1e5ee64df0e48e789b9b8eba9bb0be76fba4a23e6745f6a259cec436d00",
    1: "e0756b1e97485d458bafb868480d73b8c95c502f4136aa05937cb166d3909c3e",
    2: "ed5bb2b9a39ee222303e3c923b824deffde00e1c63eca89371a3800e51c894da",
    3: "5180de7086c682fcfebcc9b02e12e197bbd7fb09d5aeb7dfeb940350d8a1360f",
    4: "ecc835c96d707534d88dbecf6f286c59adb90839f31985926110b85ec4824066",
}
D2_SHA = "1603678923ccdd1553830fa67c2069714c0a836c9df7e8c52578aabd729b5bcc"
PROD_SHA = "faa7917e2be725a9441b277fc111091c5bdffe45c80ab4fd042682aa9de4210e"
LEADCAL_SHA = "734202bc7f22af38fd72d65c4038bb51828b11f5436ed1de40ffa0f381ad0f09"
ZIP2026_SHA = "d0dbf32fb8622f98fe072466598d706590e5f8e667619cba7d0639c6555a1a8f"
CANDIDATES = Path(__file__).resolve().parents[1] / "data" / "processed" / "live_status"
PROD = Path(__file__).resolve().parents[1] / "data" / "processed" / "spill_model.pkl"
LEADCAL = Path(__file__).resolve().parents[1] / "data" / "processed" / "lead_calibration.json"
AR = Path(__file__).resolve().parents[1] / "data" / "processed" / "annual_returns.parquet"

# ---------------------------------------------------------------- the period and rows
FIRST, LAST = "2026-01-01", "2026-08-31"       # UTC days; the EA's 2026 file ends on 31 August
lst.DAY0 = pd.Timestamp("2025-01-01", tz="UTC")  # status grid: 1 Jan 2025 .. 31 Aug 2026
lst.N_DAYS = 365 + 243
lst.T0 = pd.Timestamp("2025-12-01", tz="UTC")    # rain grid: 1 Dec 2025 .. 31 Aug 2026 (30-day antecedent)
lst.T_END = pd.Timestamp("2026-09-01", tz="UTC")
DAYS_2025 = 365
LEADS = lst.LEADS
STATUS = lst.STATUS
# Option B's dead-monitor check (docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md), its full reference period.
REF_START, REF_END, REF_DAYS = pd.Timestamp("2026-10-05"), pd.Timestamp("2026-11-01"), 28
KNOWN_SHARE, STALE_SHARE, DAYS_NEEDED = 0.8, 0.2, 20
STAMP_ONLY_ON_CHANGE = {"Northumbrian Water", "Southern Water"}
ILKLEY_16 = ["YWS00176", "YWS00674", "YWS00179", "YWS00144", "YWS00145", "YWS00191", "YWS01340", "YWS00828",
             "YWS00188", "YWS00189", "YWS00177", "YWS00190", "YWS00185", "YWS01311", "YWS00186", "YWS00187"]
N_BOOT, SEED = 2000, 20261106
ECE_LIMIT = 0.02


def step(msg: str) -> None:
    log.info("[%5.0fs, peak %5.0f MB] %s", time.time() - _T0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, msg)


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- status: #254's class, one year later
class Status2026(lst.Status):
    """#254's Status on a grid from 1 January 2025. Known: in 2025 #254's rule (an event in the 2025 file or 0 spills
    in the 2025 return, EDM operation not under 50%); in 2026 the window-E overflows (no 2026 return exists; the
    dead-monitor check stands in for it, as in PR #357)."""

    def __init__(self, events: pd.DataFrame, sites, known25: set, known26: set):
        super().__init__(events, sites, {})
        self.k25 = self.sites.isin(known25)
        self.k26 = self.sites.isin(known26)

    def known(self, i: np.ndarray, d: np.ndarray) -> np.ndarray:
        return (d >= 0) & np.where(d < DAYS_2025, self.k25[i], self.k26[i])


# ---------------------------------------------------------------- rows (PR #357's window E, UTC days)
def dead_monitor(coverage: pd.DataFrame, sites: pd.DataFrame) -> tuple[pd.Series, dict]:
    cov = coverage[(coverage["day"] >= REF_START) & (coverage["day"] <= REF_END)]
    n = int(cov["day"].nunique())
    if n != REF_DAYS:
        raise SystemExit(f"coverage holds {n} of the {REF_DAYS} reference days")
    g = cov.groupby("site_id").agg(k=("n_known", "sum"), u=("n_unknown", "sum"), s=("n_stale", "sum"),
                                   d=("n_known", lambda x: int((x > 0).sum())))
    x = sites[["site_id", "company"]].merge(g, left_on="site_id", right_index=True, how="left")
    ok1 = (x["k"] / (x["k"] + x["u"]) >= KNOWN_SHARE).fillna(False)
    ok2 = (x["s"] / x["k"].clip(lower=1) <= STALE_SHARE).fillna(False) | x["company"].isin(STAMP_ONLY_ON_CHANGE)
    ok3 = (x["d"] >= DAYS_NEEDED).fillna(False)
    passes = pd.Series((ok1 & ok2 & ok3).to_numpy(), index=sites.index)
    return passes, {"reference": f"{REF_START.date()} to {REF_END.date()}", "reference_days": n,
                    "days_needed": DAYS_NEEDED, "candidates": len(sites), "pass": int(passes.sum())}


def test_sites(ar: pd.DataFrame, coverage: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    prev = ar[ar["company"].isin(NINE) & (ar["year"] == 2025) & ar["lat"].notna() & ar["site_id"].notna()]
    prev = prev.drop_duplicates("site_id", keep="last")
    prev = prev[prev["edm_operational_pct"].ge(MIN_EDM_PCT) & ~prev["site_id"].isin(ILKLEY_16)].reset_index(drop=True)
    passes, info = dead_monitor(coverage, prev)
    info["edm_50_not_ilkley"] = len(prev)
    prev = prev[passes].reset_index(drop=True)
    cols = ["site_id", "company", "lat", "lon", "lta_spills", "spill_hours", "edm_operational_pct"]
    return prev[cols], info


def load_rain_2026(sites: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """ERA5-Land, 1 Dec 2025 to 31 Aug 2026, one 2026 file per cell (PR #357's rule): the shared cache's
    archive_<cell>_2026 if present, else the nine-company fetch's archive_<cell>_2026a; December from the 2025 file."""
    files = []
    for cl, cn in sorted(lst.cells_of(sites)):
        key = f"{cl:.3f}_{cn:.3f}"
        shared = config.CACHE / "rain" / f"archive_{key}_2026.parquet"
        own = config.CACHE / "rain_nine" / f"archive_{key}_2026a.parquet"
        f26 = shared if shared.exists() else own
        dec = next((f for f in (config.CACHE / d / f"archive_{key}_2025.parquet" for d in ("rain", "rain_nine")) if f.exists()), None)
        if not f26.exists() or dec is None:
            raise SystemExit(f"no 2026 or 2025 rain for cell {key}")
        files += [dec, f26]
    rain = pd.concat((r[(r["time"] >= lst.T0) & (r["time"] < lst.T_END)] for r in map(pd.read_parquet, files)),
                     ignore_index=True)
    rain["precip_mm"] = rain["precip_mm"].astype(np.float32)
    h = hashlib.sha256("\n".join(sorted(f"{f.name} {f.stat().st_size}" for f in files)).encode()).hexdigest()
    return rain, {"cells": len(files) // 2, "files": len(files),
                  "shared_2026": sum(f.name.endswith("_2026.parquet") for f in files),
                  "fetched_2026a": sum(f.name.endswith("_2026a.parquet") for f in files),
                  "file_list_sha256": h}


def frame(sites: pd.DataFrame, daily: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """train.py's _frame (UTC days), 1 Jan to 31 Aug 2026."""
    days = pd.date_range(FIRST, LAST, freq="D", tz="UTC")
    sd = build_site_days(sites, daily, days, labels[labels["day"].dt.year == 2026])
    sd = sd[sd["rain_d"].notna()].copy()
    sd["company"] = sd["site_id"].map(dict(zip(sites["site_id"], sites["company"], strict=True)))
    return sd.astype({f: np.float32 for f in ALL_FEATURES}).reset_index(drop=True)


def load_lead_rain(grid: lst.RainGrid):
    files = sorted(f for d in ("rain", "rain_nine") for f in (config.CACHE / d).glob("leads_*_2026.parquet"))
    lf = pd.concat(map(pd.read_parquet, files), ignore_index=True)
    lf = lf.sort_values(["cell_lat", "cell_lon", "lead", "time"])
    lf = lf[~lf.duplicated(["cell_lat", "cell_lon", "lead", "time"], keep="last")]
    lkeys = pd.Index(np.unique(lst._key(lf["cell_lat"], lf["cell_lon"])))
    L = np.full((len(LEADS), len(lkeys), grid.n_hours), np.nan, np.float32)
    li = lkeys.get_indexer(lst._key(lf["cell_lat"], lf["cell_lon"]))
    hi = ((lf["time"] - lst.T0) // pd.Timedelta(hours=1)).to_numpy()
    lead = lf["lead"].to_numpy()
    ok = np.isin(lead, LEADS) & (hi >= 0) & (hi < grid.n_hours)
    L[lead[ok], li[ok], hi[ok]] = lf["precip_mm"].to_numpy()[ok]
    h = hashlib.sha256("\n".join(sorted(f"{f.name} {f.stat().st_size}" for f in files)).encode()).hexdigest()
    return L, lkeys, {"files": len(files), "cells": len(lkeys), "file_list_sha256": h}


def lead_frames(test: pd.DataFrame, grid: lst.RainGrid, L, lkeys) -> dict[int, tuple[np.ndarray, pd.DataFrame]]:
    """#254's forecast-rain rows: per lead k, the test row positions kept and their rain features (days d, d-1, d-2
    from the forecasts issued k, k-1, k-2 days ahead, floored at 0; earlier days ERA5-Land; a row needs 65 of 72
    finite hours and a day-d total; a missing rain feature is 0)."""
    ci_all, di_all = grid.rows(test)
    to_lead = lkeys.get_indexer(grid.keys)
    era_ok = np.isfinite(grid.window(ci_all, di_all)).sum(1) >= lst.MIN_FINITE
    in_lead = np.flatnonzero((to_lead[ci_all] >= 0) & era_ok)
    out = {}
    for k in LEADS:
        ci, di = ci_all[in_lead], di_all[in_lead]
        win = np.empty((len(in_lead), lst.HOURS), np.float32)
        lc = to_lead[ci]
        for j in (2, 1, 0):
            pos = (2 - j) * 24
            win[:, pos:pos + 24] = L[max(k - j, 0)][lc[:, None], ((di - j) * 24)[:, None] + np.arange(24)]
        okk = (np.isfinite(win).sum(1) >= lst.MIN_FINITE) & np.isfinite(lst.day_total(win[:, 48:]))
        sel = np.flatnonzero(okk)
        fr = lst.rain_features(grid, win[sel], ci[sel], di[sel]).fillna(0.0)
        out[k] = (in_lead[sel], fr)
    return out


def build(a) -> dict:
    """Everything up to the forecasts: inputs checked, sites, events, status, rows, lead rows. No label is read here
    except as a column carried in the frame."""
    inputs = {"zip2026_sha256": sha256(a.zip2026), "coverage_sha256": sha256(a.coverage),
              "annual_returns_sha256": sha256(AR)}
    if inputs["zip2026_sha256"] != ZIP2026_SHA:
        raise SystemExit("the 2026 zip is not the stated file")
    ar = pd.read_parquet(AR)
    ev_files = sorted(Path(a.events2025).glob("ea_events_*.parquet")) + sorted(Path(a.events2026).glob("ea_events_*.parquet"))
    inputs["event_files"] = {str(f): sha256(f) for f in ev_files}
    ev = []
    for c in NINE:
        slug = c.lower().replace(" ", "_")
        for d in (a.events2025, a.events2026):
            ev.append(pd.read_parquet(Path(d) / f"ea_events_{slug}.parquet").assign(company=c))
    ev = pd.concat(ev, ignore_index=True)
    ev = ev[ev["site_id"].notna()]
    e25 = ev[(ev["event_start"] < pd.Timestamp("2026-01-01", tz="UTC"))]
    if e25["event_start"].max() >= pd.Timestamp("2026-01-01", tz="UTC") or ev["event_start"].max() >= pd.Timestamp("2026-09-02", tz="UTC"):
        raise SystemExit("events outside the stated files' years")
    step(f"events: {len(ev)} (2024-25 file {int((ev['event_start'] < pd.Timestamp('2026-01-01', tz='UTC')).sum())}, 2026 file {int((ev['event_start'] >= pd.Timestamp('2026-01-01', tz='UTC')).sum())})")
    coverage = pd.read_parquet(a.coverage)
    sites, site_info = test_sites(ar, coverage)
    step(f"window E: {site_info}")
    labels = spill_days(ev)
    rain, rain_info = load_rain_2026(sites)
    daily = daily_rain_features(rain)
    grid = lst.RainGrid(rain, daily)
    del rain
    test = frame(sites, daily, labels)
    del daily
    known25 = lst.covered_years(ar, ev, [2025])[2025]
    status = Status2026(ev, sites["site_id"], known25, set(sites["site_id"]))
    L, lkeys, lead_info = load_lead_rain(grid)
    leadrows = lead_frames(test, grid, L, lkeys)
    del L
    step(f"rows {len(test)}, lead cells {lead_info['cells']}")
    return {"inputs": inputs | {"rain_2026": rain_info, "lead_rain_2026": lead_info}, "site_info": site_info,
            "sites": sites, "test": test, "status": status, "grid": grid, "leadrows": leadrows,
            "n_intervals": status.n_intervals}


def stage_count(a) -> None:
    b = build(a)
    test, status = b["test"], b["status"]
    out = {"inputs": b["inputs"], "window_e": b["site_info"], "merged_events": b["n_intervals"], "per_company": {}}
    for comp in [*NINE, "all nine"]:
        m = np.ones(len(test), bool) if comp == "all nine" else (test["company"] == comp).to_numpy()
        row = {"overflows": int(test.loc[m, "site_id"].nunique()), "rows_era5": int(m.sum())}
        for k in LEADS:
            pos, _ = b["leadrows"][k]
            row[f"rows_forecast_lead{k}"] = int(m[pos].sum())
        out["per_company"][comp] = row
    out["status_unknown_any"] = {}
    for k in LEADS:
        f = status.features(test["site_id"], test["day"], k)
        out["status_unknown_any"][f"lead {k}"] = int(f.isna().any(axis=1).sum())
    print(json.dumps(out, indent=1, default=str))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "counts.json").write_text(json.dumps(out, indent=1, default=str))


# ---------------------------------------------------------------- the interval (PR #357's TwoWay, copied)
class TwoWay:
    """Each draw takes overflows with replacement and, independently, ISO weeks with replacement; a row counts
    (times its overflow was drawn) x (times its week was drawn). Drawn once, overflows first then weeks, and shared
    by every comparison, lead, rain source, company and subset."""

    def __init__(self, site: np.ndarray, week: np.ndarray, rng: np.random.Generator):
        self.sites, self.si = np.unique(site, return_inverse=True)
        self.weeks, self.wi = np.unique(week, return_inverse=True)
        ns, nw = len(self.sites), len(self.weeks)
        self.S = np.empty((N_BOOT, ns))
        self.W = np.empty((N_BOOT, nw))
        for r in range(N_BOOT):
            self.S[r] = np.bincount(rng.integers(0, ns, ns), minlength=ns)
            self.W[r] = np.bincount(rng.integers(0, nw, nw), minlength=nw)

    def interval(self, d: np.ndarray, mask: np.ndarray) -> list[float]:
        used, si = np.unique(self.si[mask], return_inverse=True)
        nw = len(self.weeks)
        cell = si * nw + self.wi[mask]
        D = np.bincount(cell, weights=d[mask], minlength=len(used) * nw).reshape(len(used), nw)
        N = np.bincount(cell, minlength=len(used) * nw).reshape(len(used), nw).astype(float)
        S = self.S[:, used]
        num = ((S @ D) * self.W).sum(1)
        den = ((S @ N) * self.W).sum(1)
        stat = num[den > 0] / den[den > 0]
        return [float(v) for v in np.percentile(stat, [2.5, 97.5])]

    def week_only(self, d: np.ndarray, mask: np.ndarray) -> list[float]:
        nw = len(self.weeks)
        D = np.bincount(self.wi[mask], weights=d[mask], minlength=nw)
        N = np.bincount(self.wi[mask], minlength=nw).astype(float)
        num, den = self.W @ D, self.W @ N
        stat = num[den > 0] / den[den > 0]
        return [float(v) for v in np.percentile(stat, [2.5, 97.5])]


def week_codes(day: pd.Series) -> np.ndarray:
    iso = day.dt.tz_convert(None).dt.isocalendar()
    return (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()


# ---------------------------------------------------------------- run
def load_models(a):
    for k in LEADS:
        p = CANDIDATES / f"candidate_lead{k}.pkl"
        if sha256(p) != CANDIDATE_SHA[k]:
            raise SystemExit(f"{p.name} is not the frozen candidate")
    if sha256(a.d2) != D2_SHA or sha256(PROD) != PROD_SHA or sha256(LEADCAL) != LEADCAL_SHA:
        raise SystemExit("D2, production or the lead map is not the stated file")
    cands = {k: SpillModel.load(CANDIDATES / f"candidate_lead{k}.pkl") for k in LEADS}
    cal = {int(k): v for k, v in json.loads(LEADCAL.read_text())["leads"].items()}
    return cands, SpillModel.load(a.d2), SpillModel.load(PROD), cal


def stage_run(a) -> None:
    cands, d2, prod, cal = load_models(a)
    b = build(a)
    test, status, leadrows = b["test"], b["status"], b["leadrows"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    checks: dict = {"inputs": b["inputs"], "window_e": b["site_info"], "merged_events": b["n_intervals"],
                    "models": {"candidates": CANDIDATE_SHA, "d2": D2_SHA, "production": PROD_SHA, "lead_map": LEADCAL_SHA},
                    "status_unknown": {}, "face": {}}
    y = test["y"].to_numpy().astype(float)
    company = test["company"].to_numpy()
    month = test["day"].dt.month.to_numpy()
    site = test["site_id"].to_numpy()
    tw = TwoWay(site, week_codes(test["day"]), np.random.default_rng(SEED))
    step("bootstrap draws made")

    p_d2 = d2.predict(test)
    p_prod = prod.predict(test)
    for name, p in (("D2", p_d2), ("production", p_prod)):
        if not np.isfinite(p).all():
            raise SystemExit(f"{name} gave a non-finite forecast")

    score_rows, int_rows, rel_rows, month_rows = [], [], [], []
    COMPS = [*NINE, "all nine"]
    cmask = {c: (np.ones(len(y), bool) if c == "all nine" else company == c) for c in COMPS}

    def record(q, rain, k, d, mask, label, extra=None):
        lo, hi = tw.interval(d, mask)
        wlo, whi = tw.week_only(d, mask)
        r = {"question": q, "rain": rain, "lead": k, "subset": label, "rows": int(mask.sum()),
             "spill_rows": int(y[mask].sum()), "difference": float(d[mask].mean()),
             "ci_low": lo, "ci_high": hi, "week_ci_low": wlo, "week_ci_high": whi}
        int_rows.append(r | (extra or {}))
        return r

    for k in LEADS:
        st = status.features(test["site_id"], test["day"], k)
        checks["status_unknown"][f"lead {k}"] = {c: int(st[c].isna().sum()) for c in STATUS}
        unknown = st.isna().any(axis=1).to_numpy()
        x = pd.concat([test.drop(columns=[c for c in STATUS if c in test]), st], axis=1)
        p_c = cands[k].predict(x)                           # Q1: as #254 scored it, a missing input as it is
        p_cf = np.where(unknown, p_prod, p_c)               # Q2: #262's fallback, production where status unknown
        if not np.isfinite(p_c).all():
            raise SystemExit("a candidate gave a non-finite forecast")
        now, c7 = st["spilling_at_issue"].to_numpy(), st["spill_days_7d"].to_numpy()
        subsets = {"dry start": (now == 0) & (c7 == 0), "not spilling at issue": now == 0,
                   "spilling at issue": now == 1, "status unknown": unknown}
        for q, pc, pb, bname in (("Q1 vs D2", p_c, p_d2, "D2"), ("Q2 vs production", p_cf, p_prod, "production")):
            d = (pc - y) ** 2 - (pb - y) ** 2
            for c in COMPS:
                m = cmask[c]
                for name, p in (("candidate", pc), (bname, pb)):
                    s = scores(y[m], p[m])
                    score_rows.append({"question": q, "rain": "ERA5-Land", "lead": k, "company": c, "predictor": name,
                                       "rows": int(m.sum()), "base_rate": float(y[m].mean()), "brier": s["brier"],
                                       "auc": s["auc"], "log_loss": s["log_loss"], "ece": ece(y[m], p[m]),
                                       "mean_forecast": float(p[m].mean())})
                    if c == "all nine" or name == "candidate":
                        rel_rows.append(reliability_table(y[m], p[m]).assign(question=q, lead=k, company=c, predictor=name))
                record(q, "ERA5-Land", k, d, m, c)
            for label, m in subsets.items():
                if m.any():
                    record(q, "ERA5-Land", k, d, m, label,
                           {"brier_candidate": float(((pc - y) ** 2)[m].mean()), "brier_baseline": float(((pb - y) ** 2)[m].mean())})
            if q == "Q2 vs production":
                # Reported: as shipped, Southern falls back throughout (#262: 0% known on the polls).
                p_ship = np.where(company == "Southern Water", p_prod, pc)
                record(q, "ERA5-Land", k, (p_ship - y) ** 2 - (pb - y) ** 2, cmask["all nine"], "all nine, Southern on fallback")
                no_uu_jan = ~((company == "United Utilities") & (month == 1))
                record(q, "ERA5-Land", k, d, no_uu_jan, "all nine, without United Utilities' January")
            for mo in range(1, 9):
                m = month == mo
                month_rows.append({"question": q, "lead": k, "month": mo, "rows": int(m.sum()), "spill_rows": int(y[m].sum()),
                                   "brier_candidate": float(((pc - y) ** 2)[m].mean()),
                                   "brier_baseline": float(((pb - y) ** 2)[m].mean())})
        step(f"lead {k}, ERA5-Land: candidate {np.mean((p_c - y) ** 2):.5f}, with fallback {np.mean((p_cf - y) ** 2):.5f}, "
             f"D2 {np.mean((p_d2 - y) ** 2):.5f}, production {np.mean((p_prod - y) ** 2):.5f}")

        # ---- forecast rain
        pos, fr = leadrows[k]
        r = test.iloc[pos]
        fr.index = r.index
        stk = st.iloc[pos]
        xk = pd.concat([r[["site_id", *lst.STATIC]], fr, stk], axis=1)
        yk = y[pos]
        f_c = cands[k].predict(xk)
        f_d2 = d2.predict(xk)
        f_raw = prod.predict(xk)
        f_cal = _apply(cal[min(k, max(cal))], f_raw)        # what the site shows at lead k
        f_cf = np.where(unknown[pos], f_cal, f_c)
        lm = np.zeros(len(y), bool)
        lm[pos] = True
        for q, pc, pb, bname in (("Q1 vs D2", f_c, f_d2, "D2"), ("Q2 vs production", f_cf, f_cal, "production (lead map)")):
            full = np.zeros(len(y))
            full[pos] = (pc - yk) ** 2 - (pb - yk) ** 2
            for c in COMPS:
                m = cmask[c] & lm
                if not m.any():
                    continue
                mk = cmask[c][pos]
                for name, p in (("candidate", pc), (bname, pb)):
                    s = scores(yk[mk], p[mk])
                    score_rows.append({"question": q, "rain": "forecast", "lead": k, "company": c, "predictor": name,
                                       "rows": int(mk.sum()), "base_rate": float(yk[mk].mean()), "brier": s["brier"],
                                       "auc": s["auc"], "log_loss": s["log_loss"], "ece": ece(yk[mk], p[mk]),
                                       "mean_forecast": float(p[mk].mean())})
                record(q, "forecast", k, full, m, c)
            if q == "Q2 vs production":
                s = scores(yk, f_raw)
                score_rows.append({"question": q, "rain": "forecast", "lead": k, "company": "all nine",
                                   "predictor": "production, no lead map", "rows": len(yk), "base_rate": float(yk.mean()),
                                   "brier": s["brier"], "auc": s["auc"], "log_loss": s["log_loss"], "ece": ece(yk, f_raw),
                                   "mean_forecast": float(f_raw.mean())})
        step(f"lead {k}, forecast rain: {len(pos)} rows")

    sc, iv = pd.DataFrame(score_rows), pd.DataFrame(int_rows)
    # ---- the conditions (#254's five, unchanged), per question and lead
    cond = {}
    for q, bname in (("Q1 vs D2", "D2"), ("Q2 vs production", "production")):
        cond[q] = {}
        for k in LEADS:
            I = iv[(iv["question"] == q) & (iv["lead"] == k)].set_index(["rain", "subset"])
            S = sc[(sc["question"] == q) & (sc["lead"] == k) & (sc["rain"] == "ERA5-Land")].set_index(["company", "predictor"])
            f9, e9 = I.loc[("forecast", "all nine")], I.loc[("ERA5-Land", "all nine")]
            worse = [c for c in NINE if I.loc[("ERA5-Land", c), "difference"] > 0 and I.loc[("ERA5-Land", c), "ci_low"] > 0]
            ece_fail = [c for c in NINE if not (S.loc[(c, "candidate"), "ece"] <= S.loc[(c, bname), "ece"]
                                                or S.loc[(c, "candidate"), "ece"] <= ECE_LIMIT)]
            dry = I.loc[("ERA5-Land", "dry start")]
            v = {"1 gain with forecast rain": bool(f9["difference"] < 0 and f9["ci_high"] < 0),
                 "2 gain with ERA5-Land rain": bool(e9["difference"] < 0 and e9["ci_high"] < 0),
                 "3 no company clearly worse": not worse,
                 "4 reliability": not ece_fail,
                 "5 not worse at a dry start": not bool(dry["difference"] > 0 and dry["ci_low"] > 0),
                 "companies clearly worse": worse, "ECE failures": ece_fail}
            v["all five"] = all(vv for kk, vv in v.items() if kk[0].isdigit())
            cond[q][k] = v
    checks["conditions"] = cond
    sc.to_csv(out / "scores.csv", index=False)
    iv.to_csv(out / "intervals.csv", index=False)
    pd.concat(rel_rows).to_csv(out / "reliability.csv", index=False)
    pd.DataFrame(month_rows).to_csv(out / "monthly.csv", index=False)
    (out / "checks.json").write_text(json.dumps(checks, indent=1, default=str))
    pd.set_option("display.width", 250)
    print(iv[iv["subset"].isin(["all nine", "dry start"])].to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    for q, v in cond.items():
        for k, c in v.items():
            print(q, "lead", k, {kk: vv for kk, vv in c.items()})
    step("written")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=["count", "run"])
    ap.add_argument("--events2025", type=Path, required=True, help="folder with the 2024-25 ea_events_*.parquet (17 Oct import)")
    ap.add_argument("--events2026", type=Path, required=True, help="folder with the 2026 ea_events_*.parquet")
    ap.add_argument("--coverage", type=Path, required=True)
    ap.add_argument("--zip2026", type=Path, required=True)
    ap.add_argument("--d2", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    {"count": stage_count, "run": stage_run}[a.stage](a)


if __name__ == "__main__":
    main()
