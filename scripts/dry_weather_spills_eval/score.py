"""Overflows that spill in dry weather: the description, Question 1 and Question 2 of
docs/DRY-WEATHER-SPILLS-TEST-2026-10.md, and its 2026 check. Run by run.sh, from a git archive, offline:

    score.py <out dir> [<2026 processed dir>]

<2026 processed dir> holds ea_events_united_utilities.parquet as scripts/import_ea_events.py --years 2026 wrote it.
Without it the 2026 check is skipped.

D2's rows come from D2's own code (scripts/train.py `_frame`); the rain grid, the lead-row rule and the week bootstrap
come from scripts/live_status_test.py, so Question 2 is scored exactly as the live-status test scored its candidates.
DRY_SPILLS_SMOKE=1 is a code check only: Thames Water alone, every 2025 and 2026 label shuffled, no row-count checks.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model import spill_model as sm
from dipcast.model.features import ALL_FEATURES, MONOTONE, SEASON_FEATURES, SITE_FEATURES, build_site_days, \
    daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel
from dipcast.model.training import NINE, RAIN_DIRS, cells_of, ece, load_events, load_rain, site_years
from dipcast.model.verify import reliability_table, scores

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_status_test import (  # noqa: E402
    HOURS,
    LEADS,
    MIN_FINITE,
    RainGrid,
    T0,
    _key,
    boot_interval,
    day_total,
    rain_features,
    week_codes,
)
from train import _frame  # noqa: E402

THRESHOLDS = {"0.25": 0.25, "1.0": 1.0}   # mm on each of days t, t-1, t-2; 0.25 decides, 1.0 is reported only
MAIN = "0.25"
PRIOR = 30.0                              # pseudo dry days toward the company's rate
MAX_SPAN = 60                             # features.spill_days' cap on the days one event marks
NEG_FRAC, PRIOR_STRENGTH, RECENCY = 0.25, 15.0, 1.0
N_BOOT = 2000
UU = "United Utilities"
D2_SHA, PROD_SHA = "1603678923cc", "faa7917e2be7"
FEATURE = "dry_spill_rate"
STATIC = SEASON_FEATURES + SITE_FEATURES
NAMES = r"ambleside|waterhead|rothay|brathay"
SMOKE = os.environ.get("DRY_SPILLS_SMOKE") == "1"
COMPANIES = ["Thames Water"] if SMOKE else NINE
_T = time.time()


def step(msg: str) -> None:
    import resource
    print(f"[{time.time() - _T:6.0f}s, peak {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9:4.1f} GB] {msg}",
          flush=True)


def sha(path: Path, want: str) -> str:
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    assert h.startswith(want), f"{path.name} is {h[:12]}, not {want}"
    return h


# ------------------------------------------------------------------ the dry-day rule
def dry_days(daily: pd.DataFrame, thr: float) -> pd.Series:
    """Per cell-day of `daily` (daily_rain_features): under `thr` mm on the day and on each of the two before, all
    three known. A NaN compares False, so an unknown day is never dry."""
    return (daily["rain_d"] < thr) & (daily["rain_d1"] < thr) & (daily["rain_d2"] < thr)


def merge_overlaps(ev: pd.DataFrame) -> pd.DataFrame:
    """Each overflow's events with overlapping ones merged (live_status_test.merged_intervals' rule, in timestamps).
    Events that do not overlap stay apart, whatever the gap."""
    e = ev[["site_id", "event_start", "event_end"]].dropna(subset=["event_start"]).copy()
    e["event_end"] = e["event_end"].fillna(e["event_start"])
    e = e.sort_values(["site_id", "event_start"], kind="mergesort").reset_index(drop=True)
    prev = e.groupby("site_id")["event_end"].cummax().groupby(e["site_id"]).shift()
    group = (prev.isna() | (e["event_start"] > prev)).cumsum()
    return e.groupby(group).agg(site_id=("site_id", "first"), start=("event_start", "min"),
                                end=("event_end", "max")).reset_index(drop=True)


def dry_started_days(merged: pd.DataFrame, cell_of: pd.DataFrame, daily: pd.DataFrame, thr: float) -> pd.DataFrame:
    """(site_id, day) on which a dry-started event spilled: a merged event whose start's UTC day is a dry day at the
    overflow's cell, marking every day from its start's day to its stop's day (at most MAX_SPAN on), as spill_days
    marks them. `cell_of` maps site_id to cell_lat, cell_lon; events of other overflows are dropped."""
    m = merged.merge(cell_of, on="site_id", how="inner")
    m["start_day"] = m["start"].dt.floor("D")
    flags = daily[["cell_lat", "cell_lon", "day"]].assign(dry=dry_days(daily, thr).to_numpy())
    m = m.merge(flags.rename(columns={"day": "start_day"}), on=["cell_lat", "cell_lon", "start_day"], how="left")
    m = m[m["dry"].eq(True)]
    n = ((m["end"].dt.floor("D") - m["start_day"]).dt.days.clip(lower=0, upper=MAX_SPAN) + 1).to_numpy()
    base = np.repeat(m["start_day"].dt.tz_convert(None).to_numpy().astype("datetime64[D]"), n)
    offs = np.concatenate([np.arange(k) for k in n]) if len(n) else np.zeros(0, int)
    out = pd.DataFrame({"site_id": np.repeat(m["site_id"].to_numpy(), n),
                        "day": pd.to_datetime(base + offs.astype("timedelta64[D]")).tz_localize("UTC")})
    return out.drop_duplicates()


def classify(frame: pd.DataFrame, touched: pd.DataFrame, thr: float) -> pd.DataFrame:
    """For each row of `frame` (D2's columns: site_id, day, y and the rain columns), at threshold `thr`:
      dry        the day is a dry day at the overflow's cell
      continuing a dry day with a spill, but only from events started on days that were not dry
      kept       dry and not continuing: a row of Question 1 and of the counts n
      y_dry      a dry spill-day (kept rows only can be 1)"""
    dry = dry_days(frame, thr).to_numpy()
    key = pd.MultiIndex.from_frame(frame[["site_id", "day"]])
    hit = key.isin(pd.MultiIndex.from_frame(touched[["site_id", "day"]]))
    y = frame["y"].to_numpy() == 1
    cont = dry & y & ~hit
    return pd.DataFrame({"dry": dry, "continuing": cont, "kept": dry & ~cont, "y_dry": dry & y & hit},
                        index=frame.index)


# ------------------------------------------------------------------ the description
def overflow_counts(frame: pd.DataFrame, cls: pd.DataFrame) -> pd.DataFrame:
    """Per overflow of `frame` (one year): kept days, dry days, continuing days, n, k, the rate and all spill-days."""
    t = pd.DataFrame({"site_id": frame["site_id"].to_numpy(), "company": frame["company"].to_numpy(),
                      "y": frame["y"].to_numpy(), **{c: cls[c].to_numpy() for c in cls}})
    g = t.groupby(["site_id", "company"])
    out = g.agg(days=("y", "size"), spill_days=("y", "sum"), dry_days=("dry", "sum"),
                continuing=("continuing", "sum"), n=("kept", "sum"), k=("y_dry", "sum")).reset_index()
    out["rate"] = out["k"] / out["n"].where(out["n"] > 0)
    out["dry_share_of_spill_days"] = out["k"] / out["spill_days"].where(out["spill_days"] > 0)
    return out


def company_table(counts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (year, comp), d in counts.groupby(["year", "company"]):
        k = d["k"]
        rows.append({"year": year, "company": comp, "overflows": len(d), "k_0": float((k == 0).mean()),
                     "k_1_4": float(k.between(1, 4).mean()), "k_5_19": float(k.between(5, 19).mean()),
                     "k_20plus": float((k >= 20).mean()), "k_median": float(k.median()), "k_p90": float(k.quantile(0.9)),
                     "k_max": int(k.max()), "k_total": int(k.sum()), "n_total": int(d["n"].sum()),
                     "rate": float(k.sum() / max(d["n"].sum(), 1)), "dry_days_total": int(d["dry_days"].sum()),
                     "continuing_total": int(d["continuing"].sum()), "spill_days_total": int(d["spill_days"].sum()),
                     "dry_share_of_spill_days": float(k.sum() / max(d["spill_days"].sum(), 1))})
    return pd.DataFrame(rows)


def shrunk(k, n, c) -> np.ndarray:
    return (np.asarray(k, float) + PRIOR * np.asarray(c, float)) / (np.asarray(n, float) + PRIOR)


# ------------------------------------------------------------------ main
def main(out: Path, dir26: Path | None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(12345)          # the smoke check's shuffles only
    checks: dict = {"smoke": SMOKE, "thresholds_mm": THRESHOLDS, "prior_dry_days": PRIOR}
    d2_path, prod_path = config.PROCESSED / "spill_model_nine_2024.pkl", config.PROCESSED / "spill_model.pkl"
    checks["d2_sha256"], checks["production_sha256"] = sha(d2_path, D2_SHA), sha(prod_path, PROD_SHA)
    d2, prod = SpillModel.load(d2_path), SpillModel.load(prod_path)

    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(COMPANIES)
    labels = spill_days(ev)
    s24, _ = site_years(ar, ev, COMPANIES, 2024)
    s25, _ = site_years(ar, ev, COMPANIES, 2025)
    rain = load_rain(cells_of(pd.concat([s24, s25])))
    step(f"rain loaded: {len(rain)} cell-hours")
    daily = daily_rain_features(rain)
    grid = RainGrid(rain, daily)
    del rain
    train = _frame(s24, 2024, daily, labels)
    test = _frame(s25, 2025, daily, labels)
    step(f"site-days: 2024 {len(train)}, 2025 {len(test)}")
    if not SMOKE:
        assert len(train) == 4_976_868 and len(test) == 5_077_150, "not D2's rows (4,976,868 and 5,077,150)"
    else:
        test["y"] = rng.permutation(test["y"].to_numpy())
    checks["rows"] = {"2024": len(train), "2025": len(test)}

    # ---- classify every row at both thresholds
    sites = pd.concat([s24, s25]).drop_duplicates("site_id", keep="last")
    cl, cn = grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy())
    cell_of = pd.DataFrame({"site_id": sites["site_id"].to_numpy(), "cell_lat": cl, "cell_lon": cn})
    merged = merge_overlaps(ev)
    checks["merged_events"] = len(merged)
    cls = {}
    for name, thr in THRESHOLDS.items():
        touched = dry_started_days(merged, cell_of, daily, thr)
        cls[name] = {2024: classify(train, touched, thr), 2025: classify(test, touched, thr)}
        if SMOKE:   # shuffle the 2025 dry labels among kept rows too, so no real 2025 count is printed
            c = cls[name][2025]
            k = c["kept"].to_numpy()
            yd = c["y_dry"].to_numpy().copy()
            yd[k] = rng.permutation(yd[k])
            c["y_dry"] = yd
        step(f"{name} mm: {len(touched)} dry-started overflow-days")
    del daily

    # ---- Part 1: the description
    names = ev.sort_values("event_start").drop_duplicates("site_id", keep="last").set_index("site_id")["site_name"]
    counts, comp_tabs = {}, []
    for name in THRESHOLDS:
        c = pd.concat([overflow_counts(train, cls[name][2024]).assign(year=2024),
                       overflow_counts(test, cls[name][2025]).assign(year=2025)], ignore_index=True)
        c["site_name"] = c["site_id"].map(names)
        counts[name] = c
        comp_tabs.append(company_table(c).assign(threshold_mm=name))
    comp = pd.concat(comp_tabs, ignore_index=True)
    c = counts[MAIN]
    c.to_csv(out / "overflows.csv", index=False)
    comp.to_csv(out / "companies.csv", index=False)
    wide = c.pivot_table(index=["site_id", "company"], columns="year", values=["k", "n", "rate", "spill_days"])
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index()
    wide["k_both"] = wide[["k_2024", "k_2025"]].fillna(0).sum(axis=1)
    wide["site_name"] = wide["site_id"].map(names)
    top = wide.sort_values(["k_both", "k_2025", "site_id"], ascending=[False, False, True]).head(25)
    top.to_csv(out / "top.csv", index=False)
    both = wide.dropna(subset=["k_2024", "k_2025"])
    sp = both[(both["n_2024"] >= 30) & (both["n_2025"] >= 30)]
    n5 = int(np.ceil(0.05 * len(both)))
    t24 = set(both.sort_values(["k_2024", "site_id"], ascending=[False, True]).head(n5)["site_id"])
    t25 = set(both.sort_values(["k_2025", "site_id"], ascending=[False, True]).head(n5)["site_id"])
    checks["years"] = {"spearman_rate_n30": float(sp["rate_2024"].corr(sp["rate_2025"], method="spearman")),
                       "overflows_n30": len(sp), "top5pct_size": n5, "top5pct_overlap": len(t24 & t25) / max(n5, 1)}
    local = ar[(ar["company"] == UU) & ar["site_name"].str.contains(NAMES, case=False, na=False)]
    amb = local.drop_duplicates("site_id", keep="last")[["site_id", "site_name"]].merge(
        wide.drop(columns="site_name"), on="site_id", how="left")
    amb.to_csv(out / "ambleside.csv", index=False)
    step("description written")

    # ---- the rate from 2024 (Question 1's R and Question 2's input on 2025 rows)
    def rate_from(frame, cl_year):
        cnt = overflow_counts(frame, cl_year)
        crate = cnt.groupby("company")["k"].sum() / cnt.groupby("company")["n"].sum()
        return cnt.set_index("site_id"), crate

    q1_rows, diffs_q1 = [], []
    week = week_codes(test["day"])
    draws = np.random.default_rng(0).integers(0, week.max() + 1, size=(N_BOOT, week.max() + 1))
    p_d2_all, p_prod_all = d2.predict(test), prod.predict(test)
    comp25 = test["company"].to_numpy()
    for name in THRESHOLDS:
        cnt24, crate24 = rate_from(train, cls[name][2024])
        c25 = cls[name][2025]
        m = c25["kept"].to_numpy()
        sid = test["site_id"].to_numpy()[m]
        comp_m = comp25[m]
        cc = pd.Series(comp_m).map(crate24).to_numpy()
        k = pd.Series(sid).map(cnt24["k"]).fillna(0).to_numpy()
        n = pd.Series(sid).map(cnt24["n"]).fillna(0).to_numpy()
        y = c25["y_dry"].to_numpy()[m].astype(int)
        preds = {"R (shrunk 2024 rate)": shrunk(k, n, cc),
                 "unshrunk 2024 rate": np.where(n > 0, k / np.maximum(n, 1), cc),
                 "D2": p_d2_all[m], "P (production)": p_prod_all[m], "F (company 2024 rate)": cc}
        wk = week[m]
        for scope, sm_ in [("all nine", np.ones(len(y), bool)), ("eight (no United Utilities)", comp_m != UU),
                           *[(cmp, comp_m == cmp) for cmp in COMPANIES]]:
            if not sm_.any():
                continue
            for pn, p in preds.items():
                s = scores(y[sm_], p[sm_])
                q1_rows.append({"threshold_mm": name, "scope": scope, "predictor": pn, "rows": s["n"],
                                "base_rate": s["base_rate"], "brier": s["brier"], "auc": s["auc"],
                                "ece": ece(y[sm_], p[sm_])})
            r = preds["R (shrunk 2024 rate)"]
            for other in ("D2", "P (production)", "F (company 2024 rate)", "unshrunk 2024 rate"):
                d = (r[sm_] - y[sm_]) ** 2 - (preds[other][sm_] - y[sm_]) ** 2
                lo, hi = boot_interval(d, wk[sm_], draws)
                diffs_q1.append({"threshold_mm": name, "scope": scope, "against": other, "rows": int(sm_.sum()),
                                 "difference": float(d.mean()), "ci_low": lo, "ci_high": hi})
        if name == MAIN:
            r25 = pd.Series(shrunk(cnt24["k"], cnt24["n"], cnt24["company"].map(crate24)), index=cnt24.index)
            crate24_main = crate24
        step(f"Question 1 scored at {name} mm")
    q1, dq1 = pd.DataFrame(q1_rows), pd.DataFrame(diffs_q1)
    q1.to_csv(out / "q1-scores.csv", index=False)
    dq1.to_csv(out / "q1-differences.csv", index=False)
    b = q1[q1.threshold_mm == MAIN].set_index(["scope", "predictor"])
    dd = dq1[dq1.threshold_mm == MAIN].set_index(["scope", "against"])
    eight, nine = "eight (no United Utilities)", "all nine"

    def below(scope, against):
        r = dd.loc[(scope, against)]
        return bool(r["difference"] < 0 and r["ci_high"] < 0)

    q1c = {"1 against production (eight)": below(eight, "P (production)"),
           "2 against D2 (nine)": below(nine, "D2"),
           "3 against the flat rate (nine)": below(nine, "F (company 2024 rate)"),
           "4 ranking": bool(b.loc[(eight, "R (shrunk 2024 rate)"), "auc"] > b.loc[(eight, "P (production)"), "auc"]
                             and b.loc[(nine, "R (shrunk 2024 rate)"), "auc"] > b.loc[(nine, "D2"), "auc"])}
    q1c["yes"] = all(q1c.values())
    checks["question_1"] = q1c
    print("\n=== Question 1 ===", json.dumps(q1c, indent=1))

    # ---- Question 2: the rate as an input, 2024 rows with their own month left out
    c24 = cls[MAIN][2024]
    t = pd.DataFrame({"site_id": train["site_id"].to_numpy(), "company": train["company"].to_numpy(),
                      "month": train["day"].dt.month.to_numpy(), "n": c24["kept"].to_numpy().astype(float),
                      "k": c24["y_dry"].to_numpy().astype(float)})
    sm_cnt = t.groupby(["site_id", "month"])[["n", "k"]].sum()
    s_cnt = t.groupby("site_id")[["n", "k"]].sum()
    cm_cnt = t.groupby(["company", "month"])[["n", "k"]].sum()
    c_cnt = t.groupby("company")[["n", "k"]].sum()
    key_sm = pd.MultiIndex.from_arrays([t["site_id"], t["month"]])
    key_cm = pd.MultiIndex.from_arrays([t["company"], t["month"]])
    n_o = t["site_id"].map(s_cnt["n"]).to_numpy() - sm_cnt["n"].reindex(key_sm).to_numpy()
    k_o = t["site_id"].map(s_cnt["k"]).to_numpy() - sm_cnt["k"].reindex(key_sm).to_numpy()
    cn_o = t["company"].map(c_cnt["n"]).to_numpy() - cm_cnt["n"].reindex(key_cm).to_numpy()
    ck_o = t["company"].map(c_cnt["k"]).to_numpy() - cm_cnt["k"].reindex(key_cm).to_numpy()
    train[FEATURE] = shrunk(k_o, n_o, ck_o / cn_o).astype(np.float32)
    test[FEATURE] = test["site_id"].map(r25).fillna(test["company"].map(crate24_main)).astype(np.float32)
    checks["feature"] = {"train_min": float(train[FEATURE].min()), "train_max": float(train[FEATURE].max()),
                         "test_from_company_rate": int((~test["site_id"].isin(r25.index)).sum()),
                         "nan_train": int(train[FEATURE].isna().sum()), "nan_test": int(test[FEATURE].isna().sum())}
    sm.MONOTONE = {**MONOTONE, FEATURE: 1}   # more dry-weather history may only raise the risk, as more rain may
    y24 = train["y"].to_numpy()
    sub = (y24 == 1) | (np.random.default_rng(0).random(len(y24)) < NEG_FRAC)
    if not SMOKE:
        assert sub.sum() == 1_569_401, "not D2's subsample (1,569,401 rows)"
    cand = SpillModel(features=[*ALL_FEATURES, FEATURE]).fit_pooled(train, neg_frac=NEG_FRAC)
    cand.fit_site_offsets(train, prior_strength=PRIOR_STRENGTH, recency=RECENCY)
    cand.trained_on = "Dry-weather-spill candidate: nine English water companies 2024 (EA start/stop files)"
    cand.save(out / "candidate.pkl")
    checks["candidate_iterations"] = int(cand.clf.n_iter_)
    step(f"candidate fitted ({cand.clf.n_iter_} iterations)")
    flat24 = train.groupby("company")["y"].mean()
    del train

    y = test["y"].to_numpy()
    blind = test[["site_id", *ALL_FEATURES]].copy()
    blind[FEATURE] = test["company"].map(crate24_main).astype(np.float32)
    preds = {"candidate": cand.predict(test), "baseline (D2)": p_d2_all,
             "candidate, layer 1 only": cand.predict_pooled(test), "baseline, layer 1 only": d2.predict_pooled(test),
             "candidate, company rate for every overflow": cand.predict(blind),
             "company flat rate": test["company"].map(flat24).to_numpy()}
    del blind
    checks["baseline_all_nine_brier"] = float(((p_d2_all - y) ** 2).mean())
    diff = (preds["candidate"] - y) ** 2 - (p_d2_all - y) ** 2
    rows, dif, rel = [], [], []
    for cmp in [*COMPANIES, "all nine"]:
        m = np.ones(len(y), bool) if cmp == "all nine" else comp25 == cmp
        for pn, p in preds.items():
            s = scores(y[m], p[m])
            rows.append({"company": cmp, "predictor": pn, "rows": s["n"], "base_rate": s["base_rate"],
                         "brier": s["brier"], "auc": s["auc"], "ece": ece(y[m], p[m])})
        for pn in ("candidate", "baseline (D2)"):
            rel.append(reliability_table(y[m], preds[pn][m]).assign(company=cmp, predictor=pn))
        lo, hi = boot_interval(diff[m], week[m], draws)
        dif.append({"company": cmp, "rows": int(m.sum()), "brier_candidate": float(((preds["candidate"][m] - y[m]) ** 2).mean()),
                    "brier_baseline": float(((p_d2_all[m] - y[m]) ** 2).mean()), "difference": float(diff[m].mean()),
                    "ci_low": lo, "ci_high": hi})
    kept25 = cls[MAIN][2025]["kept"].to_numpy()
    subsets = []
    for sn, m in (("dry rows (Question 1's rows)", kept25), ("all other rows", ~kept25)):
        lo, hi = boot_interval(diff[m], week[m], draws)
        subsets.append({"subset": sn, "rows": int(m.sum()), "base_rate": float(y[m].mean()),
                        "brier_candidate": float(((preds["candidate"][m] - y[m]) ** 2).mean()),
                        "brier_baseline": float(((p_d2_all[m] - y[m]) ** 2).mean()),
                        "difference": float(diff[m].mean()), "ci_low": lo, "ci_high": hi})
    q2s, q2d, q2sub = pd.DataFrame(rows), pd.DataFrame(dif), pd.DataFrame(subsets)
    step("Question 2 scored on ERA5-Land rain")

    # ---- Question 2 with forecast rain: live_status_test's lead rows and rule
    lead_files = sorted(f for d in RAIN_DIRS for f in (config.CACHE / d).glob("leads_*_2025.parquet"))
    lf = pd.concat((pd.read_parquet(f) for f in lead_files), ignore_index=True)
    lf = lf.sort_values(["cell_lat", "cell_lon", "lead", "time"])
    lf = lf[~lf.duplicated(["cell_lat", "cell_lon", "lead", "time"], keep="last")]
    lkeys = pd.Index(np.unique(_key(lf["cell_lat"], lf["cell_lon"])))
    L = np.full((len(LEADS), len(lkeys), grid.n_hours), np.nan, np.float32)
    li = lkeys.get_indexer(_key(lf["cell_lat"], lf["cell_lon"]))
    hi_ = ((lf["time"] - T0) // pd.Timedelta(hours=1)).to_numpy()
    lead = lf["lead"].to_numpy()
    ok = np.isin(lead, LEADS) & (hi_ >= 0) & (hi_ < grid.n_hours)
    L[lead[ok], li[ok], hi_[ok]] = lf["precip_mm"].to_numpy()[ok]
    del lf
    ci_all, di_all = grid.rows(test)
    to_lead = lkeys.get_indexer(grid.keys)
    era_ok = np.isfinite(grid.window(ci_all, di_all)).sum(1) >= MIN_FINITE
    in_lead = np.flatnonzero((to_lead[ci_all] >= 0) & era_ok)
    checks["lead_rows"] = {"files": len(lead_files), "cells": len(lkeys), "rows": len(in_lead)}
    lead_rows = []
    for k in LEADS:
        ci, di = ci_all[in_lead], di_all[in_lead]
        win = np.empty((len(in_lead), HOURS), np.float32)
        lc = to_lead[ci]
        for j in (2, 1, 0):
            pos = (2 - j) * 24
            win[:, pos:pos + 24] = L[max(k - j, 0)][lc[:, None], ((di - j) * 24)[:, None] + np.arange(24)]
        okk = (np.isfinite(win).sum(1) >= MIN_FINITE) & np.isfinite(day_total(win[:, 48:]))
        sel = np.flatnonzero(okk)
        r = test.iloc[in_lead[sel]]
        fr = rain_features(grid, win[sel], ci[sel], di[sel]).fillna(0.0)
        fr.index = r.index
        x = pd.concat([r[["site_id", *STATIC, FEATURE]], fr], axis=1)
        pb, pc = d2.predict(x), cand.predict(x)
        yk = r["y"].to_numpy()
        dk = (pc - yk) ** 2 - (pb - yk) ** 2
        lo, hi = boot_interval(dk, week[in_lead[sel]], draws)
        sc, sb = scores(yk, pc), scores(yk, pb)
        lead_rows.append({"lead": k, "rows": len(sel), "base_rate": float(yk.mean()), "brier_candidate": sc["brier"],
                          "brier_baseline": sb["brier"], "auc_candidate": sc["auc"], "auc_baseline": sb["auc"],
                          "difference": float(dk.mean()), "ci_low": lo, "ci_high": hi})
        step(f"lead {k}: {len(sel)} rows")
    q2l = pd.DataFrame(lead_rows)
    del L

    bq = q2s.set_index(["company", "predictor"])
    dq = q2d.set_index("company")
    worse = [cmp for cmp in COMPANIES if dq.loc[cmp, "difference"] > 0 and dq.loc[cmp, "ci_low"] > 0]
    ece_fail = [cmp for cmp in COMPANIES if not (bq.loc[(cmp, "candidate"), "ece"] <= bq.loc[(cmp, "baseline (D2)"), "ece"]
                                                 or bq.loc[(cmp, "candidate"), "ece"] <= 0.02)]
    q2c = {"1 a gain": bool(dq.loc["all nine", "difference"] < 0 and dq.loc["all nine", "ci_high"] < 0),
           "2 no company clearly worse": not worse,
           "3 reliability": not ece_fail,
           "4 with forecast rain": bool((q2l["difference"] < 0).all() and not (q2l["ci_low"] > 0).any()),
           "companies clearly worse": worse, "ECE failures": ece_fail}
    q2c["passes"] = all(v for kk, v in q2c.items() if kk[0].isdigit())
    checks["question_2"] = q2c
    print("\n=== Question 2 ===", json.dumps(q2c, indent=1))
    q2s.to_csv(out / "q2-scores.csv", index=False)
    q2d.to_csv(out / "q2-differences.csv", index=False)
    q2sub.to_csv(out / "q2-subsets.csv", index=False)
    q2l.to_csv(out / "q2-leads.csv", index=False)
    pd.concat(rel).to_csv(out / "q2-reliability.csv", index=False)

    # ---- the 2026 check, United Utilities only, reported
    if dir26 is not None:
        checks["2026"] = check_2026(dir26, ar, ev, s25, counts[MAIN], d2, prod, out, rng)
    (out / "score.json").write_text(json.dumps(checks, indent=1, default=str))
    step("done")


def check_2026(dir26, ar, ev, s25, counts, d2, prod, out, rng) -> dict:
    """Question 1's comparison on United Utilities, January to June 2026, with R from 2025: the one comparison in which
    production has not seen the year it is scored on there. Months failing the data check are left out."""
    res: dict = {}
    e26 = pd.read_parquet(dir26 / "ea_events_united_utilities.parquet")
    e26 = e26[e26["event_start"] >= pd.Timestamp("2026-01-01", tz="UTC")]
    ev = ev if UU in set(ev["company"]) else load_events([UU])   # the smoke check holds Thames alone
    s25 = s25 if UU in set(s25["company"]) else site_years(ar, ev, [UU], 2025)[0]
    e25 = ev[(ev["company"] == UU) & (ev["event_start"].dt.year == 2025)]
    res["events_2026"] = len(e26)
    by25 = e25.groupby(e25["event_start"].dt.month)["site_id"].nunique()
    by26 = e26.groupby(e26["event_start"].dt.month)["site_id"].nunique()
    months = {int(mo): {"overflows_2025": int(by25.get(mo, 0)), "overflows_2026": int(by26.get(mo, 0))} for mo in range(1, 9)}
    use = [mo for mo in range(1, 7) if months[mo]["overflows_2026"] >= 0.5 * months[mo]["overflows_2025"]]
    res["months"], res["months_used"] = months, use
    if not use:
        return res
    keep = set(s25.loc[s25["company"] == UU, "site_id"])
    prev = ar[(ar["company"] == UU) & (ar["year"] == 2025) & ar["lat"].notna()].drop_duplicates("site_id", keep="last")
    sites = prev[prev["site_id"].isin(keep)][["site_id", "company", "lat", "lon", "lta_spills", "spill_hours",
                                              "edm_operational_pct"]].reset_index(drop=True)
    if SMOKE:
        sites = sites.head(100)
    rain = load_rain(cells_of(sites), tags=("2025", "2026"), start="2025-12-01")
    daily = daily_rain_features(rain)
    del rain
    allev = pd.concat([e25, e26.assign(company=UU)], ignore_index=True)
    labels = spill_days(allev)
    days = pd.DatetimeIndex([d for d in pd.date_range("2026-01-01", "2026-06-30", freq="D", tz="UTC") if d.month in use])
    fr = build_site_days(sites, daily, days, labels[labels["day"].dt.year == 2026])
    res["sites"], res["sites_with_rain"] = len(sites), int(fr.loc[fr["rain_d"].notna(), "site_id"].nunique())
    fr = fr[fr["rain_d"].notna()].copy()
    fr["company"] = UU
    fr = fr.astype({f: np.float32 for f in ALL_FEATURES})
    if SMOKE:
        fr["y"] = rng.permutation(fr["y"].to_numpy())
    cl, cn = grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy())
    cell_of = pd.DataFrame({"site_id": sites["site_id"].to_numpy(), "cell_lat": cl, "cell_lon": cn})
    touched = dry_started_days(merge_overlaps(allev), cell_of, daily, THRESHOLDS[MAIN])
    c = classify(fr, touched, THRESHOLDS[MAIN])
    m = c["kept"].to_numpy()
    y = c["y_dry"].to_numpy()[m].astype(int)
    if SMOKE:
        y = rng.permutation(y)
    c25 = counts[(counts["year"] == 2025) & (counts["company"] == UU)].set_index("site_id")
    crate = c25["k"].sum() / c25["n"].sum() if len(c25) else 0.05   # 0.05 in the smoke check only
    sid = fr["site_id"].to_numpy()[m]
    k = pd.Series(sid).map(c25["k"]).fillna(0).to_numpy()
    n = pd.Series(sid).map(c25["n"]).fillna(0).to_numpy()
    sub = fr[m]
    preds = {"R (shrunk 2025 rate)": shrunk(k, n, np.full(len(k), crate)), "D2": d2.predict(sub),
             "P (production)": prod.predict(sub), "F (company 2025 rate)": np.full(len(k), crate)}
    week = week_codes(sub["day"])
    draws = np.random.default_rng(0).integers(0, week.max() + 1, size=(N_BOOT, week.max() + 1))
    res["rows"], res["dry_rows"], res["continuing"] = len(fr), int(m.sum()), int(c["continuing"].sum())
    res["base_rate"] = float(y.mean())
    res["scores"] = {pn: scores(y, p) for pn, p in preds.items()}
    r = preds["R (shrunk 2025 rate)"]
    res["differences"] = {}
    for other in ("D2", "P (production)", "F (company 2025 rate)"):
        d = (r - y) ** 2 - (preds[other] - y) ** 2
        lo, hi = boot_interval(d, week, draws)
        res["differences"][other] = {"difference": float(d.mean()), "ci_low": lo, "ci_high": hi}
    pd.DataFrame([{"predictor": pn, **s} for pn, s in res["scores"].items()]).to_csv(out / "y2026.csv", index=False)
    step(f"2026 check: months {use}, {m.sum()} dry rows")
    return res


if __name__ == "__main__":
    np.seterr(all="ignore")
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
