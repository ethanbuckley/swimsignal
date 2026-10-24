"""Verify the spill model with the rain a user would have seen: archived
forecasts by lead time (Open-Meteo previous-runs API) instead of reanalysis.

Lead 0 = the latest model run for that day (what 'today' uses); lead k = the
forecast issued k days before the target day ('tomorrow' is lead 1, and so on).

Approximation, stated in the README: for lead k the target day's rainfall and
intensity features and the two previous days use lead-appropriate forecasts
(k, k-1, k-2, floored at 0); the 7-day, 30-day and antecedent-index features
use reanalysis, because on the issue day those windows are almost entirely
observed history.

Which model and rows (docs/NINE-COMPANY-MODEL-TEST-2026-10.md, 16 Oct 2026): the
map is fitted for the model named by --model (default: the production model, spill_model.pkl), and
lead_calibration.json records that model's trained_on, so the map and the model it corrects cannot
drift apart again (until then a 2023-24 hold-out's map was applied to a 2023-25 refit). Rows: the
YEAR site-days of every overflow of the nine English companies in a cell with archived lead
forecasts, covered by the EA start/stop files (training.site_years). Each map is scored cross-fitted
by month parity; a lead whose cross-fitted Brier is not below the raw Brier is saved as an identity
map. The skill reference is the overflow climatology (each overflow's YEAR-1 spill-day rate) on the
same rows.
"""

from __future__ import annotations

import logging
import sys

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.features import ALL_FEATURES, LOCAL_TZ, build_site_days, daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel
from dipcast.model.training import NINE, RAIN_DIRS, load_events, load_rain, site_years
from dipcast.model.verify import reliability_table, scores

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("verify_leads")
YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
LEADS = [0, 1, 2, 3, 4]


def load(pattern: str) -> pd.DataFrame:
    files = sorted(f for d in RAIN_DIRS for f in (config.CACHE / d).glob(pattern))
    log.info("%d files for %s", len(files), pattern)
    return pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)


def main() -> None:
    path = config.PROCESSED / "spill_model.pkl"
    if "--model" in sys.argv:
        path = config.PROCESSED / sys.argv[sys.argv.index("--model") + 1]
    model = SpillModel.load(path)
    log.info("model: %s (%s)", model.trained_on, path.name)
    ev = load_events(NINE)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    all_labels = spill_days(ev)
    labels = all_labels[all_labels.day.dt.year == YEAR]

    leads = load(f"leads_*_{YEAR}.parquet")
    cells_with_leads = set(map(tuple, leads[["cell_lat", "cell_lon"]].drop_duplicates().to_numpy()))
    era = load_rain(cells_with_leads, tags=(str(YEAR - 1), str(YEAR)), start=f"{YEAR - 1}-12-01")
    daily_era = daily_rain_features(era)
    daily_lead = {k: daily_rain_features(leads[leads.lead == k].drop(columns="lead")) for k in LEADS}

    # Rainfall skill itself: daily total by lead vs reanalysis.
    key = ["cell_lat", "cell_lon", "day"]
    print(f"\n=== Daily rainfall vs ERA5-Land, {YEAR}, {len(cells_with_leads)} cells ===")
    print(f"{'lead':>4} {'MAE mm':>7} {'bias mm':>8} {'corr':>6} {'hit>10mm':>9} {'FA>10mm':>8}")
    for k in LEADS:
        m = daily_era[key + ["rain_d"]].merge(daily_lead[k][key + ["rain_d"]], on=key, suffixes=("_obs", "_fc")).dropna()
        obs, fc = m["rain_d_obs"].to_numpy(), m["rain_d_fc"].to_numpy()
        wet = obs > 10
        hit = (fc[wet] > 10).mean() if wet.any() else np.nan
        fa = (fc[~wet] > 10).mean() if (~wet).any() else np.nan
        print(f"{k:>4} {np.abs(fc - obs).mean():7.2f} {(fc - obs).mean():8.2f} {np.corrcoef(obs, fc)[0, 1]:6.3f} {hit:9.2f} {fa:8.3f}")

    # Covariates from the previous year's return, as in training; the overflows the files cover.
    sites, _ = site_years(ar, ev, NINE, YEAR)
    # --exclude COMPANY (repeatable): leave out a company whose YEAR the model was trained on, so the
    # map is fitted out of sample (the production model, United Utilities 2023-25, saw 2025 there).
    excluded = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--exclude"]
    sites = sites[~sites["company"].isin(excluded)]
    sites = sites[[c in cells_with_leads for c in zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True)]]
    print("\noverflows per company:", sites["company"].value_counts().to_dict())
    days = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31", freq="D", tz=LOCAL_TZ)
    base = build_site_days(sites, daily_era, days, labels)
    base = base[base["rain_d"].notna()].copy()
    y = base["y"].to_numpy()
    # Overflow climatology: each overflow's spill-day share the year before, among the overflows the
    # files covered that year (0 if it had no event); else its company's mean share.
    covered, _ = site_years(ar, ev, NINE, YEAR - 1)
    n_days = 366 if (YEAR - 1) % 4 == 0 else 365
    spilled = all_labels[all_labels.day.dt.year == YEAR - 1].groupby("site_id").size()
    covered["rate"] = covered["site_id"].map(spilled).fillna(0) / n_days
    company = base["site_id"].map(dict(zip(sites["site_id"], sites["company"], strict=True))).to_numpy()
    rate = base["site_id"].map(dict(zip(covered["site_id"], covered["rate"], strict=True)))
    rate = rate.fillna(pd.Series(company, index=base.index).map(covered.groupby("company")["rate"].mean()))
    clim = scores(y, rate.to_numpy())["brier"]

    def with_lead(k: int) -> pd.DataFrame:
        df = base.copy()
        same = daily_lead[k][key + ["rain_d", "max1h_d", "max3h_d", "max6h_d"]]
        df = df.drop(columns=["rain_d", "max1h_d", "max3h_d", "max6h_d"]).merge(same, on=key, how="left")
        for shift, col in ((1, "rain_d1"), (2, "rain_d2")):
            src = daily_lead[max(k - shift, 0)][key + ["rain_d"]].copy()
            src["day"] = src["day"] + pd.DateOffset(days=shift)   # calendar days: 24 h misses a clock change
            df = df.drop(columns=[col]).merge(src.rename(columns={"rain_d": col}), on=key, how="left")
        df["rain_3d"] = df["rain_d"].fillna(0) + df["rain_d1"].fillna(0) + df["rain_d2"].fillna(0)
        return df

    rows = []
    calib: dict[str, dict[str, float]] = {}
    print(f"\n=== Spill model on {YEAR} by rainfall source ===")
    p_era = model.predict(base.astype({f: np.float32 for f in ALL_FEATURES}).fillna({f: 0.0 for f in ALL_FEATURES}))
    # Not an upper bound (11 Oct 2026, the label until then): the same-day forecast scores better than it.
    s = scores(y, p_era); rows.append({"source": "reanalysis (the weather as it was)", **s})
    for k in LEADS:
        dfk = with_lead(k)
        ok = dfk["rain_d"].notna().to_numpy()
        pk = model.predict(dfk.astype({f: np.float32 for f in ALL_FEATURES}).fillna({f: 0.0 for f in ALL_FEATURES}))
        s = scores(y[ok], pk[ok]); rows.append({"source": f"forecast lead {k}", **s})
        # Per-lead Platt scaling: logit(p') = a + b * logit(p). Two parameters per
        # lead, fitted on this year; corrects the over-confidence that comes from
        # treating forecast rain as if it were observed.
        from sklearn.linear_model import LogisticRegression
        z = np.log(pk[ok] / (1 - pk[ok])).reshape(-1, 1)
        lr = LogisticRegression(C=1e6).fit(z, y[ok])
        a, b = float(lr.intercept_[0]), float(lr.coef_[0][0])
        pc = 1 / (1 + np.exp(-(a + b * z[:, 0])))
        sc = scores(y[ok], pc); rows.append({"source": f"forecast lead {k}, Platt-calibrated", **sc})
        # Isotonic map: monotone, piecewise, fitted on the same out-of-sample year. Platt's
        # two parameters cannot fix over-confidence at the top end alone (0.85 verified at
        # 0.78 on the held-out year); this can. Stored as ~40 knots on the quantiles of p.
        from sklearn.isotonic import IsotonicRegression
        iso = IsotonicRegression(y_min=0.001, y_max=0.99, out_of_bounds="clip").fit(pk[ok], y[ok])
        grid = np.unique(np.concatenate([[0.0, 1.0], np.quantile(pk[ok], np.linspace(0, 1, 41)),
                                         np.linspace(0.5, 1.0, 11)]))
        knots_y = iso.predict(grid)
        pi = np.interp(pk[ok], grid, knots_y)
        si = scores(y[ok], pi); rows.append({"source": f"forecast lead {k}, isotonic-calibrated", **si})
        # Fitting and scoring the map on the same year is optimistic. Cross-fit by
        # month parity: calibrate on odd months, score even months, and the reverse,
        # so every scored day is calibrated by a map that never saw its month.
        month = dfk.loc[ok, "day"].dt.month.to_numpy()
        pcf = np.full(ok.sum(), np.nan)
        for parity in (0, 1):
            fit_m, sc_m = month % 2 != parity, month % 2 == parity
            iso_cf = IsotonicRegression(y_min=0.001, y_max=0.99, out_of_bounds="clip").fit(pk[ok][fit_m], y[ok][fit_m])
            pcf[sc_m] = iso_cf.predict(pk[ok][sc_m])
        scf = scores(y[ok], pcf); rows.append({"source": f"forecast lead {k}, isotonic cross-fitted (odd/even months)", **scf})
        helps = scf["brier"] < s["brier"]
        calib[str(k)] = {"a": a, "b": b, "brier_before": s["brier"], "brier_after": sc["brier"],
                         "iso_x": [round(float(v), 5) for v in grid] if helps else [0.0, 1.0],
                         "iso_y": [round(float(v), 5) for v in knots_y] if helps else [0.0, 1.0],
                         "identity": not helps,
                         "brier_isotonic": si["brier"], "brier_isotonic_crossfit": scf["brier"]}
        by_co = pd.DataFrame({"company": company[ok], "y": y[ok], "raw": pk[ok], "cf": pcf})
        for co, d in by_co.groupby("company"):
            calib[str(k)].setdefault("by_company", {})[co] = {
                "n": len(d), "brier_raw": float(((d.raw - d.y) ** 2).mean()),
                "brier_crossfit": float(((d.cf - d.y) ** 2).mean())}
        if k in (0, 2):
            print(f"\n--- reliability, lead {k} (raw) ---")
            print(reliability_table(y[ok], pk[ok]).round(3).to_string())
            print(f"--- reliability, lead {k} (Platt) ---")
            print(reliability_table(y[ok], pc).round(3).to_string())
            print(f"--- reliability, lead {k} (isotonic) ---")
            print(reliability_table(y[ok], pi).round(3).to_string())
    from dipcast.model.verify import brier_skill
    res = pd.DataFrame(rows).set_index("source")
    print(f"\noverflow climatology Brier on these rows: {clim:.4f}")
    res["brier_skill_vs_clim"] = [brier_skill(b, clim) for b in res["brier"]]
    pd.set_option("display.width", 160)
    print()
    print(res.round(4).to_string())
    res.to_csv(config.PROCESSED / f"verification_leads_{YEAR}.csv")
    import json
    (config.PROCESSED / "lead_calibration.json").write_text(json.dumps(
        {"fitted_on": YEAR, "model": model.trained_on, "method": "isotonic",
         "rows": "the nine English companies' overflows in cells with archived lead forecasts"
                 + (f", except {', '.join(excluded)} (in the model's training year)" if excluded else ""),
         "crossfit": "odd/even months; a lead whose cross-fitted Brier is not below the raw one is an identity map",
         "climatology_brier": clim, "leads": calib}, indent=1))
    log.info("saved per-lead calibration -> %s", config.PROCESSED / "lead_calibration.json")


if __name__ == "__main__":
    main()
