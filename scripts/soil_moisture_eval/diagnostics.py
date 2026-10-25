"""docs/SOIL-MOISTURE-ECOLI-PLAN-2026-10.md, step 2: descriptions of #344's Question 1 run. They decide nothing.

    diagnostics.py <soil dir> <out.json>

Run in the root #344's run.sh q1 built (DIPCAST_ROOT etc.), offline. The rows are q1.py's (train_ecoli's 1,502), the
arms its reference and `main`. Reported:
- within-site Spearman's rho of log E. coli against the LOYO probability, with and without sm, per bathing water
  with at least MIN_SITE_SAMPLES samples, and the median change;
- the LOYO Brier gain by sample month, and for rivers and lakes;
- sm's coefficient (per SD) in each leave-one-year-out fold, and in the fit on all rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import train_ecoli as te
from q1 import ARMS, soil_at
from scipy.stats import spearmanr

from dipcast import config
from dipcast.model.ecoli import THRESHOLD, features, fit
from dipcast.model.forecast import MAX_MISSING_SHARE

MIN_SITE_SAMPLES = 30


def rows_q1() -> tuple[pd.DataFrame, dict]:
    """q1.py's rows and filters (train_ecoli.main's), and the forecast rain at them by lead (train_ecoli's
    forecast_rain_at_samples: 48 h, 24 h, coverage)."""
    # ---- train_ecoli.main's rows and filters, unchanged
    rows = pd.read_parquet(config.PROCESSED / "ecoli_validation_rows.parquet")
    rows = rows[rows.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "ecoli"]).reset_index(drop=True)
    rows["lake"] = (rows["kind"] == "lake").astype(float)
    rows["day"] = rows["sample_time"].dt.floor("D")
    sites = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id").set_index("bw_id")
    rows["lat"], rows["lon"] = sites.loc[rows.bw_id, "lat"].to_numpy(), sites.loc[rows.bw_id, "lon"].to_numpy()
    ex = pd.read_parquet(te.EXPOSURE_FILE)
    ex["day"] = pd.to_datetime(ex["day"])
    if ex["day"].dt.tz is None and rows["day"].dt.tz is not None:
        ex["day"] = ex["day"].dt.tz_localize(rows["day"].dt.tz)
    if "missing_share" not in ex:
        ex["missing_share"] = np.where(ex["risk_prod"].isna(), 1.0, 0.0)
    for k in te.LEADS:
        e = ex[ex.lead == k][["bw_id", "day", "risk_prod", "risk_holdout", "missing_share"]].rename(
            columns={"risk_prod": f"risk_lead{k}", "risk_holdout": f"risk_hold_lead{k}", "missing_share": f"miss_lead{k}"})
        rows = rows.merge(e, on=["bw_id", "day"], how="left")
    fc = te.forecast_rain_at_samples(rows)
    ok_rain = np.all([~np.isnan(fc[k][0]) for k in te.LEADS], axis=0)
    shown = {k: (rows[f"miss_lead{k}"].fillna(1.0).to_numpy() <= MAX_MISSING_SHARE) & rows[f"risk_lead{k}"].notna().to_numpy()
             for k in te.LEADS}
    ok = ok_rain & np.all([shown[k] for k in te.LEADS], axis=0)
    rows = rows[ok].reset_index(drop=True)
    return rows, {k: tuple(a[ok] for a in fc[k]) for k in te.LEADS}


def main(soil_dir: str, out_path: str) -> None:
    rows, fc = rows_q1()
    fc0 = fc[0]
    sm = soil_at(rows, Path(soil_dir))
    assert np.isfinite(sm).all() and len(rows) == 1502, "not #344's rows"
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years = rows["sample_time"].dt.year.to_numpy()
    lake = rows["lake"].to_numpy()
    X = features(fc0[0], fc0[1], rows["risk_lead0"], rows.lake, rows.sample_time)
    X["sm"] = sm
    arms = {a: ARMS[a] for a in ("reference", "main")}
    p = {a: te.leave_one_out(X, y, years, lake, c) for a, c in arms.items()}
    res = {"rows": len(rows), "brier_loyo": {a: float(np.mean((p[a] - y) ** 2)) for a in arms}}
    # within-site rank
    sites = []
    for bw, g in rows.groupby("bw_id"):
        if len(g) < MIN_SITE_SAMPLES:
            continue
        i = g.index.to_numpy()
        r = {a: float(spearmanr(p[a][i], g["log_ecoli"]).statistic) for a in arms}
        sites.append({"bw_id": bw, "name": g["name"].iloc[0], "kind": g["kind"].iloc[0], "n": len(g),
                      "rho_reference": round(r["reference"], 3), "rho_main": round(r["main"], 3),
                      "change": round(r["main"] - r["reference"], 3)})
    s = pd.DataFrame(sites)
    res["within_site"] = {"sites": len(s), "median_change": float(s["change"].median()),
                          "sites_better": int((s["change"] > 0).sum()), "sites_worse": int((s["change"] < 0).sum()),
                          "median_change_rivers": float(s.loc[s.kind != "lake", "change"].median()),
                          "median_change_lakes": float(s.loc[s.kind == "lake", "change"].median()),
                          "median_rho_reference": float(s["rho_reference"].median()),
                          "median_rho_main": float(s["rho_main"].median()), "table": sites}
    # gain by month and type
    month = rows["sample_time"].dt.month.to_numpy()
    d = (p["reference"] - y) ** 2 - (p["main"] - y) ** 2
    res["gain_by_month"] = {int(m): {"n": int((month == m).sum()), "over_900": int(y[month == m].sum()),
                                     "brier_reference": float(np.mean((p["reference"][month == m] - y[month == m]) ** 2)),
                                     "gain": float(d[month == m].mean())} for m in sorted(set(month))}
    res["gain_by_type"] = {t: {"n": int(m.sum()), "over_900": int(y[m].sum()), "gain": float(d[m].mean())}
                           for t, m in (("rivers", lake == 0.0), ("lakes", lake == 1.0))}
    # sm's coefficient by LOYO fold
    res["coef_sm_by_fold"] = {int(g): float(fit(X[years != g], y[years != g], arms["main"]).coef["sm"])
                              for g in np.unique(years)}
    res["coef_sm_all_rows"] = float(fit(X, y, arms["main"]).coef["sm"])
    res["sm_by_month_mean"] = {int(m): float(sm[month == m].mean()) for m in sorted(set(month))}
    Path(out_path).write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: v for k, v in res.items() if k != "within_site"}, indent=1, default=float))
    print(json.dumps({k: v for k, v in res["within_site"].items() if k != "table"}, indent=1))
    print(s.sort_values("change").to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
