"""Do the spill model's annual-return covariates carry their return year's wetness, and does a relative form
fix it? (docs/COVARIATE-YEAR-TEST-2026-10.md)

Two deciding folds, each trained on one year and judged on the next: F24 (2023 -> 2024 at United Utilities,
Northumbrian and Wessex) and F25 (2024 -> 2025 at the nine English companies, D2's rows). Three covariate forms
are fitted on the same rows: A (raw, as today), R2 (log ratio to the company-year median; it decides) and R1
(percentile rank within the company-year; reported). Off CI, by hand, with the main checkout's event files
linked into data/processed/ and DIPCAST_CACHE at its data/cache/:

    uv run python scripts/test_covariate_year.py rows    # every fold's site-days and covariates, and their counts
    uv run python scripts/test_covariate_year.py rain    # question 1a: annual returns and rain only
    uv run python scripts/test_covariate_year.py train   # A, R2 and R1 for F24 and F25 -> swimsignal-private
    uv run python scripts/test_covariate_year.py score   # the judged years: every predictor, the bootstrap, the conditions

Only `score` reads a judged year's labels or predicts it. F26 (2025 -> 2026) waits for the 2026 files.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.features import (
    ALL_FEATURES,
    daily_rain_features,
    site_static_features,
    spill_days,
)
from dipcast.model.training import NINE, cells_of, load_events, load_rain, site_years

sys.path.insert(0, str(Path(__file__).resolve().parent))
# D2's site-day frame (scripts/train.py).
from train import _frame

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True)
log = logging.getLogger("test_covariate_year")

UU, NW, WX, TW = "United Utilities", "Northumbrian Water", "Wessex Water", "Thames Water"
THREE = [UU, NW, WX]
WELSH = "Dwr Cymru Welsh Water"
FOLDS = {"F24": (2023, 2024, THREE), "F25": (2024, 2025, NINE)}   # (training year, judged year, companies)
FORMS = ("A", "R2", "R1")
RELATIVE = {"lta_spills": "log_lta_spills", "spill_hours": "log_spill_hours"}   # what R2 and R1 change
CONTEXT = "CTX"   # A, with the judged rows' covariates from the training year's return
PR259_2023 = {UU: 691_675, NW: 352_590, WX: 358_795}   # train_multi_year.py's 2023 site-days at the three companies
D2_ROWS = {2024: 4_976_868, 2025: 5_077_150}
D2_SHA = "1603678923cc"
SHIFT_MIN = 0.25          # |spill-hours shift| from which question 1b predicts a sign
PRIOR_STRENGTH, RECENCY, NEG_FRAC = 15.0, 1.0, 0.25
N_BOOT = 2000
RAIN_DIRS = ("rain", "rain_nine", "rain_multi")
OUT = config.PROCESSED / "covariate_year"
MODELS = Path.home() / "Documents" / "GitHub" / "swimsignal-private" / "baselines" / "covariate_year"
BASELINES = MODELS.parent
DOCS = config.ROOT / "docs" / "COVARIATE-YEAR-TEST-2026-10"
KEEP_COLS = ["site_id", "company", "year", "day", "cell_lat", "cell_lon", "y", *ALL_FEATURES]

# Question 1a: (company, first year) for each pair of consecutive return years compared with the rain.
PAIRS = [(c, y) for c in (NW, WX) for y in (2021, 2022, 2023, 2024)] + [(c, y) for c in (UU, TW) for y in (2023, 2024)] \
    + [(c, 2024) for c in ("Anglian Water", WELSH, "Severn Trent Water", "South West Water", "Southern Water",
                           "Yorkshire Water")]
CELL_MIN_HOURS, COMPANY_MIN_CELLS, PAIRS_NEEDED = 0.95, 0.85, 14

_T = time.time()


def step(msg: str) -> None:
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9   # bytes on macOS
    log.info("[%6.0fs, peak %5.1f GB] %s", time.time() - _T, rss, msg)


# ------------------------------------------------------------------ returns and covariate forms
def load_returns() -> pd.DataFrame:
    return pd.read_parquet(config.PROCESSED / "annual_returns.parquet")


def population(ar: pd.DataFrame) -> pd.DataFrame:
    """One row per id and return year (the last, as training.site_years keeps), with or without a position."""
    return ar[ar["site_id"].notna()].drop_duplicates(["year", "site_id"], keep="last")


def log_values(v) -> pd.Series:
    return np.log1p(pd.to_numeric(v, errors="coerce").clip(lower=0))


def medians(ar: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """{covariate: company x return year} median of log1p(value) over the population's values."""
    pop = population(ar)
    return {c: log_values(pop[c]).groupby([pop["company"], pop["year"]]).median().unstack() for c in RELATIVE}


def relative(sites: pd.DataFrame, ar: pd.DataFrame, ret: int) -> pd.DataFrame:
    """R2 and R1 for `sites` (raw covariates from return `ret`), per site_id.
    R2: log1p(x) minus the median of log1p over the company's population in `ret`; a missing x is 0.
    R1: (average rank of x in that population - 0.5) / population size, ties averaged; a missing x is 0.5.
    The rank is placed by value, so an id held twice in the return still gets one."""
    pop = population(ar)
    pop = pop[pop["year"] == ret]
    out = pd.DataFrame({"site_id": sites["site_id"].to_numpy()})
    for c, col in RELATIVE.items():
        x = log_values(sites[c]).to_numpy(float)
        r2, r1 = np.full(len(x), np.nan), np.full(len(x), np.nan)
        for co in sites["company"].unique():
            m = (sites["company"] == co).to_numpy()
            v = np.sort(log_values(pop.loc[pop["company"] == co, c]).dropna().to_numpy(float))
            assert len(v), f"{co} has no {c} in the {ret} return"
            r2[m] = x[m] - np.median(v)
            lo, hi = np.searchsorted(v, x[m], "left"), np.searchsorted(v, x[m], "right")
            r1[m] = ((lo + 1 + hi) / 2 - 0.5) / len(v)
        nan = np.isnan(x)
        r2[nan], r1[nan] = 0.0, 0.5
        out[f"R2_{col}"], out[f"R1_{col}"] = r2.astype(np.float32), r1.astype(np.float32)
    return out


def context(sites: pd.DataFrame, ar: pd.DataFrame, ret: int) -> tuple[pd.DataFrame, int]:
    """A's three covariates for `sites` from an older return `ret` (its last row per id with a position); an id
    it lacks takes the company median over `sites` (site_static_features). Also how many ids lack a value."""
    r = ar[(ar["year"] == ret) & ar["lat"].notna() & ar["site_id"].notna()]
    r = r.drop_duplicates("site_id", keep="last").set_index("site_id")
    s = sites[["site_id", "company", "lat", "lon"]].copy()
    for c in ("lta_spills", "spill_hours", "edm_operational_pct"):
        s[c] = s["site_id"].map(r[c])
    st = site_static_features(s)
    out = st[["site_id", "log_lta_spills", "log_spill_hours", "edm_pct"]].copy()
    out.columns = ["site_id", *(f"{CONTEXT}_{c}" for c in ("log_lta_spills", "log_spill_hours", "edm_pct"))]
    return out, int(s[["lta_spills", "spill_hours", "edm_operational_pct"]].isna().any(axis=1).sum())


def with_form(frame: pd.DataFrame, form: str) -> pd.DataFrame:
    """`frame` with the covariate columns of `form` in the model's own columns (A: as built)."""
    if form == "A":
        return frame
    cols = list(RELATIVE.values()) + (["edm_pct"] if form == CONTEXT else [])
    return frame.assign(**{c: frame[f"{form}_{c}"] for c in cols})


# ------------------------------------------------------------------ events and rain
def history_events() -> pd.DataFrame:
    """2023 events at the three companies, as train_multi_year.py reads them (docs/MULTI-YEAR-TEST-2026-10.md):
    Northumbrian and Wessex from their own layers (import_stream_events.py), United Utilities from its Stream
    2023 layer. December 2022 is kept so that an event running over New Year labels the 2023 days it touches."""
    p = config.PROCESSED
    uu = pd.read_parquet(p / "edm_events.parquet")
    parts = [
        pd.read_parquet(p / "stream_events_northumbrian_water.parquet").assign(company=NW),
        pd.read_parquet(p / "stream_events_wessex_water.parquet").assign(company=WX),
        uu[uu["source"] == "United Utilities 2023"].assign(company=UU),
    ]
    ev = pd.concat([e[["site_id", "event_start", "event_end", "company"]] for e in parts], ignore_index=True)
    ev["site_id"] = ev["site_id"].astype(object)
    ev = ev[ev["site_id"].notna() & (ev["event_start"] < pd.Timestamp("2024-01-01", tz="UTC"))]
    return ev.reset_index(drop=True)


_RAIN_INDEX: dict = {}


def rain_files(cells: set, tags) -> list[Path]:
    """The cell-files tagged `tags` for `cells`, in all three folders (listed once)."""
    if not _RAIN_INDEX:
        for d in RAIN_DIRS:
            for f in (config.CACHE / d).glob("archive_*.parquet"):
                p = f.stem.split("_")
                if len(p) == 4:
                    _RAIN_INDEX.setdefault(((float(p[1]), float(p[2])), p[3]), []).append(f)
    return sorted(f for c in cells for t in tags for f in _RAIN_INDEX.get((c, t), []))


def load_rain_f24(cells: set) -> pd.DataFrame:
    """Hourly ERA5-Land for F24's cells from 1 December 2022 to the end of 2024, from all three folders."""
    files = rain_files(cells, ("2022", "2022dec", "2023", "2023dec", "2024"))
    log.info("F24: loading %d rain cell-files for %d cells", len(files), len(cells))
    t0, t1 = pd.Timestamp("2022-12-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")
    rain = pd.concat((r[(r["time"] >= t0) & (r["time"] < t1)] for r in map(pd.read_parquet, files)), ignore_index=True)
    rain["precip_mm"] = rain["precip_mm"].astype(np.float32)
    return rain


# ------------------------------------------------------------------ rows
def fold_frame(sites: pd.DataFrame, year: int, daily, labels, ar, ret: int, judged_ctx: int | None) -> tuple:
    """D2's site-day frame for `sites` in `year`, with R2 and R1 (from return `ret`) beside A's columns, and the
    context covariates (from return `judged_ctx`) for a judged frame."""
    f = _frame(sites, year, daily, labels)[KEEP_COLS].reset_index(drop=True)
    rel = relative(sites, ar, ret).set_index("site_id")
    for c in rel.columns:
        f[c] = f["site_id"].map(rel[c]).astype(np.float32)
    n_ctx_missing = None
    if judged_ctx is not None:
        ctx, n_ctx_missing = context(sites, ar, judged_ctx)
        ctx = ctx.set_index("site_id")
        for c in ctx.columns:
            f[c] = f["site_id"].map(ctx[c]).astype(np.float32)
    days = 366 if year % 4 == 0 else 365
    expected = sites.groupby("company").size() * days
    got = f.groupby("company").size()
    lacking = {k: int(expected.get(k, 0) - got.get(k, 0)) for k in expected.index}
    filled = sites.groupby("company")[["lta_spills", "spill_hours", "edm_operational_pct"]].agg(lambda v: int(v.isna().sum()))
    check = {"site_days": {k: int(v) for k, v in got.items()}, "overflows": {k: int(v) for k, v in sites.groupby("company").size().items()},
             "site_days_without_rain": lacking, "raw_values_missing": filled.to_dict(orient="index"),
             "base_rate": {k: float(v) for k, v in f.groupby("company")["y"].mean().items()}}
    if n_ctx_missing is not None:
        check["overflows_the_training_return_lacks"] = n_ctx_missing
    cov = ["log_lta_spills", "log_spill_hours", "edm_pct", *(c for c in f.columns if c.startswith(("R2_", "R1_", f"{CONTEXT}_")))]
    assert f[cov].notna().all().all(), "a covariate column holds NaN"
    return f, check


def stage_rows() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ar = load_returns()
    checks: dict = {}

    # F25: D2's rows and D2's rain (training.load_rain, from 1 December 2023, rain/ and rain_nine/).
    ev_n = load_events(NINE)
    lab_n = spill_days(ev_n)
    s24, _ = site_years(ar, ev_n, NINE, 2024)
    s25, _ = site_years(ar, ev_n, NINE, 2025)
    for y, s in ((2024, s24), (2025, s25)):
        assert s["site_id"].notna().all(), f"D2's {y} rows hold an overflow with no id"
    daily = daily_rain_features(load_rain(cells_of(pd.concat([s24, s25]))))
    step("F25 rain")
    f, checks["F25 training 2024"] = fold_frame(s24, 2024, daily, lab_n, ar, 2023, None)
    assert len(f) == D2_ROWS[2024], f"2024: {len(f)} rows, not D2's {D2_ROWS[2024]}"
    f.to_parquet(OUT / "F25_train.parquet", index=False)
    f24_judged_counts = {c: int((f["company"] == c).sum()) for c in THREE}
    del f
    f, checks["F25 judged 2025"] = fold_frame(s25, 2025, daily, lab_n, ar, 2024, 2023)
    assert len(f) == D2_ROWS[2025], f"2025: {len(f)} rows, not D2's {D2_ROWS[2025]}"
    f.to_parquet(OUT / "F25_judged.parquet", index=False)
    del f, daily
    step("F25 rows saved")

    # F24: train_multi_year.py's 2023 rows at the three companies, then D2's 2024 rows there; one rain
    # series from Dec 2022.
    ev_h = history_events()
    s23, _ = site_years(ar, ev_h, THREE, 2023)
    checks["F24 2023 overflows with no id, dropped"] = int(s23["site_id"].isna().sum())
    s23 = s23[s23["site_id"].notna()].reset_index(drop=True)
    s24_3 = s24[s24["company"].isin(THREE)].reset_index(drop=True)
    daily = daily_rain_features(load_rain_f24(cells_of(pd.concat([s23, s24_3]))))
    step("F24 rain")
    f, checks["F24 training 2023"] = fold_frame(s23, 2023, daily, spill_days(ev_h), ar, 2022, None)
    for c, n in PR259_2023.items():
        assert checks["F24 training 2023"]["site_days"][c] == n, f"2023 {c}: not PR #259's {n}"
    f.to_parquet(OUT / "F24_train.parquet", index=False)
    del f
    f, checks["F24 judged 2024"] = fold_frame(s24_3, 2024, daily, spill_days(load_events(THREE)), ar, 2023, 2022)
    for c, n in f24_judged_counts.items():
        assert checks["F24 judged 2024"]["site_days"][c] == n, f"2024 {c}: not D2's {n}"
    f.to_parquet(OUT / "F24_judged.parquet", index=False)
    del f, daily
    (OUT / "rows_checks.json").write_text(json.dumps(checks, indent=1, default=int))
    print(json.dumps(checks, indent=1, default=int))
    step("rows saved")


def load_frame(name: str, columns=None) -> pd.DataFrame:
    f = pd.read_parquet(OUT / f"{name}.parquet", columns=columns)
    for c in ("site_id", "company"):
        if c in f:
            f[c] = f[c].astype(str).astype(object)
    return f


# ------------------------------------------------------------------ question 1a
def stage_rain() -> None:
    """For each pair in PAIRS: the change in the company-year median of log1p(spill_hours), and the change in mean
    calendar-year ERA5-Land rain over the company's cells in that year's return."""
    from scipy.stats import spearmanr
    ar = load_returns()
    med = medians(ar)["spill_hours"]
    pos = ar[ar["site_id"].notna() & ar["lat"].notna()]
    totals: dict = {}

    def cell_total(cell, year):
        if (cell, year) not in totals:
            files = rain_files({cell}, (str(year),))
            if not files:
                totals[(cell, year)] = None
            else:
                r = pd.concat(map(pd.read_parquet, files), ignore_index=True).drop_duplicates("time", keep="last")
                r = r[r["time"].dt.year == year]
                v = pd.to_numeric(r["precip_mm"], errors="coerce").to_numpy(float)
                hours = (366 if year % 4 == 0 else 365) * 24
                ok = np.isfinite(v).sum() >= CELL_MIN_HOURS * hours
                totals[(cell, year)] = float(np.nansum(v)) if ok else np.nan
        return totals[(cell, year)]

    def company_year(co, year):
        g = pos[(pos["company"] == co) & (pos["year"] == year)]
        cl, cn = grid_cell(g["lat"].to_numpy(), g["lon"].to_numpy())
        cells = sorted(set(zip(cl.tolist(), cn.tolist(), strict=True)))
        t = [cell_total(c, year) for c in cells]
        with_file = [v for v in t if v is not None]
        full = [v for v in with_file if np.isfinite(v)]
        share = len(with_file) / len(cells)
        return {"cells": len(cells), "with_file": len(with_file), "full_year": len(full), "share_with_file": share,
                "mean_rain_mm": float(np.mean(full)) if share >= COMPANY_MIN_CELLS and full else np.nan}

    rows = []
    for co, y in PAIRS:
        a, b = company_year(co, y), company_year(co, y + 1)
        d_hours = float(med.loc[co, y + 1] - med.loc[co, y])
        d_rain = b["mean_rain_mm"] - a["mean_rain_mm"]
        rows.append({"company": co, "from": y, "to": y + 1, "median_log_hours_from": float(med.loc[co, y]),
                     "median_log_hours_to": float(med.loc[co, y + 1]), "hours_change": d_hours,
                     "rain_from_mm": a["mean_rain_mm"], "rain_to_mm": b["mean_rain_mm"], "rain_change_mm": d_rain,
                     "same_sign": bool(np.sign(d_hours) == np.sign(d_rain)) if np.isfinite(d_rain) else None,
                     **{f"from_{k}": v for k, v in a.items() if k != "mean_rain_mm"},
                     **{f"to_{k}": v for k, v in b.items() if k != "mean_rain_mm"}})
        step(f"1a {co} {y}-{y + 1}: hours {d_hours:+.3f}, rain {d_rain:+.1f} mm")
    t = pd.DataFrame(rows)
    assert t["rain_change_mm"].notna().all(), "a pair has no rain: the statement's 18 pairs all need it"
    rho = spearmanr(t["hours_change"], t["rain_change_mm"])
    agree = int(t["same_sign"].sum())
    res = {"pairs": len(t), "same_sign": agree, "needed": PAIRS_NEEDED, "pass": agree >= PAIRS_NEEDED,
           "spearman_rho": float(rho.statistic), "spearman_p": float(rho.pvalue)}
    t.to_csv(f"{DOCS}-rain.csv", index=False)
    (OUT / "rain_check.json").write_text(json.dumps(res, indent=1))
    pd.set_option("display.width", 220)
    print(t[["company", "from", "to", "hours_change", "rain_from_mm", "rain_to_mm", "rain_change_mm", "same_sign"]]
          .round(3).to_string(index=False))
    print(json.dumps(res, indent=1))


# ------------------------------------------------------------------ training
def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_train() -> None:
    from dipcast.model.spill_model import SpillModel
    MODELS.mkdir(parents=True, exist_ok=True)
    log_rows = []
    for fold, (ty, jy, companies) in FOLDS.items():
        train = load_frame(f"{fold}_train")
        step(f"{fold}: {len(train)} training site-days ({ty}), base rate {train['y'].mean():.4f}")
        for form in FORMS:
            t0 = time.time()
            rows = with_form(train, form)
            m = SpillModel().fit_pooled(rows, neg_frac=NEG_FRAC)
            m.fit_site_offsets(rows, prior_strength=PRIOR_STRENGTH, recency=RECENCY)
            m.trained_on = f"Covariate return-year test {fold} ({form}): {', '.join(companies)} {ty}"
            path = MODELS / f"{fold}_{form}.pkl"
            m.save(path)
            log_rows.append({"fold": fold, "form": form, "training_year": ty, "rows": len(train),
                             "iterations": int(m.clf.n_iter_), "offsets": len(m.site_offset),
                             "seconds": round(time.time() - t0), "sha256": sha(path)[:12]})
            step(f"{fold} {form}: {m.clf.n_iter_} iterations, {len(m.site_offset)} offsets")
            pd.DataFrame(log_rows).to_csv(f"{DOCS}-training.csv", index=False)
        del train, rows


# ------------------------------------------------------------------ scoring
def week_codes(day: pd.Series) -> np.ndarray:
    """ISO (year, week) of the UTC day, as scripts/train_nn.py's (which imports PyTorch)."""
    iso = day.dt.isocalendar()
    return pd.factorize(iso["year"].astype(int) * 100 + iso["week"].astype(int), sort=True)[0]


def boot_interval(diff: np.ndarray, week: np.ndarray, draws: np.ndarray) -> tuple[float, float]:
    W = draws.shape[1]
    s = np.bincount(week, weights=diff, minlength=W)
    n = np.bincount(week, minlength=W).astype(float)
    stat = s[draws].sum(1) / n[draws].sum(1)
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return float(lo), float(hi)


def predicted_shifts(ar: pd.DataFrame) -> pd.DataFrame:
    med = medians(ar)
    rows = []
    for fold, (ty, jy, companies) in FOLDS.items():
        for c in companies:
            dh = float(med["spill_hours"].loc[c, jy - 1] - med["spill_hours"].loc[c, ty - 1])
            dl = float(med["lta_spills"].loc[c, jy - 1] - med["lta_spills"].loc[c, ty - 1])
            rows.append({"fold": fold, "company": c, "hours_shift": dh, "lta_shift": dl,
                         "predicted_sign": int(np.sign(dh)) if abs(dh) >= SHIFT_MIN else 0})
    return pd.DataFrame(rows)


def stage_score() -> None:
    from dipcast.model.spill_model import EPS, SpillModel
    from dipcast.model.training import ece
    from dipcast.model.verify import reliability_table, scores

    d2_path = BASELINES / "spill_model_nine_2024.pkl"
    assert sha(d2_path).startswith(D2_SHA), f"{d2_path.name} is not D2's candidate"
    d2 = SpillModel.load(d2_path)
    parts, d2_check = [], {}
    for fold, (ty, jy, companies) in FOLDS.items():
        flat = load_frame(f"{fold}_train", ["company", "y"]).groupby("company")["y"].mean()
        test = load_frame(f"{fold}_judged")
        models = {f: SpillModel.load(MODELS / f"{fold}_{f}.pkl") for f in FORMS}
        pr = {f: models[f].predict(with_form(test, f)) for f in FORMS}
        pr[CONTEXT] = models["A"].predict(with_form(test, CONTEXT))
        pr["flat rate"] = test["company"].map(flat).to_numpy()
        for f in FORMS:
            pr[f"{f}, layer 1 only"] = models[f].predict_pooled(with_form(test, f))
        if fold == "F25":
            pr["D2"] = d2.predict(test)
            d2_check = {"largest_forecast_difference_A_vs_D2": float(np.abs(pr["A"] - pr["D2"]).max())}
        else:
            pr["D2"] = np.full(len(test), np.nan)
        parts.append(pd.DataFrame({"fold": fold, "company": test["company"].to_numpy(), "day": test["day"].to_numpy(),
                                   "y": test["y"].to_numpy(), **{k: np.clip(v, EPS, 1 - EPS) for k, v in pr.items()}}))
        step(f"{fold}: {len(test)} judged site-days predicted")
        del test
    df = pd.concat(parts, ignore_index=True)
    del parts
    y = df["y"].to_numpy()
    week = week_codes(pd.to_datetime(df["day"], utc=True))
    draws = np.random.default_rng(0).integers(0, week.max() + 1, size=(N_BOOT, week.max() + 1))

    groups = {}
    for fold, (_, _, companies) in FOLDS.items():
        fm = (df["fold"] == fold).to_numpy()
        for c in companies:
            groups[(fold, c)] = fm & (df["company"] == c).to_numpy()
        groups[(fold, "together")] = fm
    groups[("both", "together")] = np.ones(len(df), bool)
    preds = [k for k in df.columns if k not in ("fold", "company", "day", "y")]
    pairs = [("R2", "A"), ("R1", "A"), ("R2", "R1"), (CONTEXT, "A"), ("A", "D2")]

    rows, rel, diffs = [], [], []
    for (fold, g), m in groups.items():
        for k in preds:
            p = df[k].to_numpy()
            if np.isnan(p[m]).any():
                continue
            sc = scores(y[m], p[m])
            rows.append({"fold": fold, "group": g, "predictor": k, "rows": sc["n"], "base_rate": sc["base_rate"],
                         "mean_forecast": float(p[m].mean()), "brier": sc["brier"], "auc": sc["auc"],
                         "ece": ece(y[m], p[m]), "log_loss": sc["log_loss"]})
        for k in (*FORMS, CONTEXT):
            rel.append(reliability_table(y[m], df[k].to_numpy()[m]).assign(fold=fold, group=g, predictor=k))
        for one, two in pairs:
            a, b = df[one].to_numpy(), df[two].to_numpy()
            if np.isnan(a[m]).any() or np.isnan(b[m]).any():
                continue
            d = (a[m] - y[m]) ** 2 - (b[m] - y[m]) ** 2
            lo, hi = boot_interval(d, week[m], draws)
            diffs.append({"fold": fold, "group": g, "first": one, "second": two, "rows": int(m.sum()),
                          "brier_first": float(((a[m] - y[m]) ** 2).mean()), "brier_second": float(((b[m] - y[m]) ** 2).mean()),
                          "difference": float(d.mean()), "ci_low": lo, "ci_high": hi})
    res, dif = pd.DataFrame(rows), pd.DataFrame(diffs)
    pd.set_option("display.width", 240)
    print("\n=== Judged years, ERA5-Land rain ===")
    print(res.round(5).to_string(index=False))
    print("\n=== Brier differences, first minus second, 95% week-cluster bootstrap ===")
    print(dif.to_string(index=False, float_format=lambda v: f"{v:.5f}"))

    # Question 1b: the forecast shift s_c = mean A - mean R2 at each company-fold, against the predicted sign.
    ar = load_returns()
    sh = predicted_shifts(ar)
    b = res.set_index(["fold", "group", "predictor"])
    sh["s_c"] = [b.loc[(r.fold, r.company, "A"), "mean_forecast"] - b.loc[(r.fold, r.company, "R2"), "mean_forecast"]
                 for r in sh.itertuples()]
    sh["s_c_R1"] = [b.loc[(r.fold, r.company, "A"), "mean_forecast"] - b.loc[(r.fold, r.company, "R1"), "mean_forecast"]
                    for r in sh.itertuples()]
    sh["observed_minus_A"] = [b.loc[(r.fold, r.company, "A"), "base_rate"] - b.loc[(r.fold, r.company, "A"), "mean_forecast"]
                              for r in sh.itertuples()]
    sh["holds"] = np.where(sh["predicted_sign"] != 0, np.sign(sh["s_c"]) == sh["predicted_sign"], np.nan)
    pred = sh[sh["predicted_sign"] != 0]
    q1b = {"predictions": len(pred), "held": int(pred["holds"].astype(bool).sum()), "needed": 8}
    q1b["pass"] = q1b["held"] >= q1b["needed"]
    q1a = json.loads((OUT / "rain_check.json").read_text())
    print("\n=== Question 1b: forecast shifts ===")
    print(sh.round(5).to_string(index=False))

    # Question 2, for R2 (deciding) and R1 (observation).
    dd = dif.set_index(["fold", "group", "first", "second"])
    cfolds = [(f, c) for f, (_, _, cs) in FOLDS.items() for c in cs]

    def q2(form):
        k = (form, "A")
        return {
            "1 real gain overall": bool(dd.loc[("both", "together", *k), "difference"] < 0
                                        and dd.loc[("both", "together", *k), "ci_high"] < 0),
            "2 neither fold clearly worse": not [f for f in FOLDS if dd.loc[(f, "together", *k), "ci_low"] > 0],
            "3 no company clearly worse": not [fc for fc in cfolds if dd.loc[(*fc, *k), "ci_low"] > 0],
            "4 reliability": not [fc for fc in cfolds if not (b.loc[(*fc, form), "ece"] <= b.loc[(*fc, "A"), "ece"]
                                                              or b.loc[(*fc, form), "ece"] <= 0.02)],
        }
    q2_r2, q2_r1 = q2("R2"), q2("R1")
    print("\n=== Question 1 ===")
    print(f"1a: {q1a['same_sign']} of {q1a['pairs']} pairs agree ({'PASS' if q1a['pass'] else 'FAIL'}); "
          f"1b: {q1b['held']} of {q1b['predictions']} ({'PASS' if q1b['pass'] else 'FAIL'})")
    print("YES" if q1a["pass"] and q1b["pass"] else "NO")
    for name, q in (("R2 (deciding)", q2_r2), ("R1 (observation)", q2_r1)):
        print(f"\n=== Question 2, {name} ===")
        for k, v in q.items():
            print(f"{k}: {'PASS' if v else 'FAIL'}")
        print("YES" if all(q.values()) else "NO")

    res.to_csv(f"{DOCS}-scores.csv", index=False)
    dif.to_csv(f"{DOCS}-differences.csv", index=False)
    pd.concat(rel).to_csv(f"{DOCS}-reliability.csv", index=False)
    sh.to_csv(f"{DOCS}-shifts.csv", index=False)
    checks = json.loads((OUT / "rows_checks.json").read_text())
    Path(f"{DOCS}-checks.json").write_text(json.dumps(
        {"rows": checks, "question_1a": q1a, "question_1b": q1b, "question_1_yes": bool(q1a["pass"] and q1b["pass"]),
         "question_2_R2": q2_r2, "question_2_yes": all(q2_r2.values()), "question_2_R1_observation": q2_r1,
         "F25_reproduces_D2": d2_check, "bootstrap": {"draws": N_BOOT, "weeks": int(week.max() + 1)},
         "layer_2": {"prior_strength": PRIOR_STRENGTH, "recency": RECENCY}}, indent=1, default=float))
    step("tables written")


def stage_f26() -> None:
    sys.exit("F26 waits for the EA's full-year 2026 start/stop files for all nine companies and the 2026 annual "
             "return (docs/COVARIATE-YEAR-TEST-2026-10.md); its rain fetch is asked of Ethan then")


if __name__ == "__main__":
    {"rows": stage_rows, "rain": stage_rain, "train": stage_train, "score": stage_score, "f26": stage_f26}[sys.argv[1]]()
