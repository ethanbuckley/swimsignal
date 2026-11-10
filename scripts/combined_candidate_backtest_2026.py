"""One combined spill-forecast candidate scored on January to August 2026, as stated in
docs/COMBINED-CANDIDATE-BACKTEST-2026-11.md. Off CI, by hand, offline (no Open-Meteo call, no download):

    DIPCAST_ROOT=<scratch root> DIPCAST_STATE=<scratch state> DIPCAST_CACHE=<rain cache, read-only> PYTHONPATH=src \\
        python scripts/combined_candidate_backtest_2026.py count|run --events2026 <dir> --events2025 <dir> \\
        --coverage <live_coverage.parquet> --zip2026 <2026 zip> --d2 <spill_model_nine_2024.pkl> --out <dir>

The candidate ("combined-v1"), frozen by file hashes:
  base     regional-v1 (scripts/regional_routing.py): v2 arm (b) at the eight companies other than United Utilities,
           production at United Utilities; raw chances, no lead map.
  status   where the overflow's status at issue is known, the base's log-odds plus the live-status uplift of lead k,
           logit(candidate_k) - logit(D2): what #254's lead-k candidate adds to its own base (D2) on the same row.
  fallback where any status input is missing, the base alone.
Nothing is fitted. Every model file is one already frozen and hashed by an earlier record.

The rows, the status rebuild, the rain (ERA5-Land and archived forecasts) and the two-way bootstrap are PR #639's
(scripts/live_status_backtest_2026.py), imported unchanged. The two simple rules are PR #662's
(docs/SIMPLE-REFERENCES-LIVE-2026-11.md), rebuilt on the EA records: P (spilling at issue or in the 48 hours
before) and R (rain on the target day and the day before over 10 mm), each side's chance fitted on the 28 days of
results before the issue day.

`count` builds the rows and prints counts per company and lead, and how many rows each rule can be applied to. It
reads no label and computes no forecast. `run` scores everything once and writes the tables.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_status_backtest_2026 as lsb  # noqa: E402  (#639's harness: rows, status, rain, bootstrap; unchanged)
import live_status_test as lst  # noqa: E402  (#254's code, its dates moved by lsb on import)
import regional_routing as rr  # noqa: E402  (regional-v1, frozen)

from dipcast.model.forecast import _apply  # noqa: E402
from dipcast.model.spill_model import SpillModel  # noqa: E402
from dipcast.model.training import NINE, ece  # noqa: E402
from dipcast.model.verify import scores  # noqa: E402

V2 = Path(__file__).resolve().parents[1] / "data" / "processed" / "regional" / "spill_model_v2_offsets.pkl"
LEADS = lsb.LEADS
step = lsb.step

# ---------------------------------------------------------------- stated settings
CLIP = 1e-6                    # probabilities clipped to [CLIP, 1 - CLIP] before a logit
RAIN_RULE_MM = 10.0            # R: rain on day d and d-1 over this (strictly greater); #662's threshold
FIT_DAYS, MIN_FIT_ROWS = 28, 100   # #662: trailing 28 target days before the issue day, at least 100 rows
WARN_AT = 0.40                 # forecast_log.SPILL_WARN_AT, the Accuracy page's warning line
BAR_LEADS = (1, 2)
BAR_REFS = ("production", "persistence P", "rain rule R")
COMPS = [*NINE, "all nine"]


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, CLIP, 1 - CLIP)
    return np.log(p / (1 - p))


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def combine(base: np.ndarray, cand: np.ndarray, d2: np.ndarray, unknown: np.ndarray) -> np.ndarray:
    """combined-v1: the base's log-odds plus the status uplift where the status is known, the base where it is not."""
    return np.where(unknown, base, sigmoid(logit(base) + logit(cand) - logit(d2)))


# ---------------------------------------------------------------- the two simple rules (#662), on the EA records
def persistence_side(status: lst.Status, site_id: pd.Series, day: pd.Series, k: int) -> np.ndarray:
    """P for rows (site, day d) at lead k, issued 00:00 UTC of day m = d-k: 1 if a merged event runs at the issue
    time, or a spill-day (the label's rule: an event touches the UTC day) is among days m-1 and m-2, the 48 hours
    before the issue; 0 if not; NaN where any of days m, m-1, m-2 is not known."""
    i = status.sites.get_indexer(site_id)
    d = ((day - lst.DAY0) // pd.Timedelta(days=1)).to_numpy().astype(np.int64)
    m = d - k
    c = lambda a: np.clip(a, 0, None)
    known = status.known(i, m) & status.known(i, m - 1) & status.known(i, m - 2)
    active = (status.now[i, c(m)] > 0) | (status.sday[i, c(m - 1)] > 0) | (status.sday[i, c(m - 2)] > 0)
    return np.where(known, active.astype(float), np.nan)


def rain_side(rain_d: np.ndarray, rain_d1: np.ndarray) -> np.ndarray:
    """R: 1 if rain on the target day plus the day before is over RAIN_RULE_MM, 0 if not, NaN if either is missing."""
    tot = np.asarray(rain_d, float) + np.asarray(rain_d1, float)
    return np.where(np.isfinite(tot), (tot > RAIN_RULE_MM).astype(float), np.nan)


def trailing_chance(side: np.ndarray, y: np.ndarray, tday: np.ndarray, k: int) -> np.ndarray:
    """Each row's chance from its side of the rule: (spills + 0.5) / (rows + 1) over the rows of the same lead and
    side, all companies, with target day from I-28 to I-1, I = the row's issue day (target day - k). NaN where the
    side has fewer than MIN_FIT_ROWS such rows or the rule cannot be applied. `tday` counts days from 1 Jan 2026."""
    out = np.full(len(side), np.nan)
    ok = np.isfinite(side)
    nd = int(tday.max()) + 1
    for s in (0, 1):
        m = ok & (side == s)
        n = np.bincount(tday[m], minlength=nd).astype(float)
        sp = np.bincount(tday[m], weights=y[m], minlength=nd)
        cn, cs = np.concatenate([[0.0], np.cumsum(n)]), np.concatenate([[0.0], np.cumsum(sp)])
        hi = np.clip(tday[m] - k, 0, nd)               # target days < I  (I = t - k)
        lo = np.clip(tday[m] - k - FIT_DAYS, 0, nd)    # target days >= I - 28
        N, S = cn[hi] - cn[lo], cs[hi] - cs[lo]
        out[np.flatnonzero(m)] = np.where(N >= MIN_FIT_ROWS, (S + 0.5) / (N + 1.0), np.nan)
    return out


def warning_counts(y: np.ndarray, warn: np.ndarray) -> dict:
    """The Accuracy page's warning figures (forecast_log.warning_counts) for a yes/no warning."""
    yy = y.astype(bool)
    hits, misses = int((warn & yy).sum()), int((~warn & yy).sum())
    fa = int((warn & ~yy).sum())
    return {"warnings": hits + fa, "hits": hits, "misses": misses, "false_alarms": fa,
            "hit_rate": hits / (hits + misses) if hits + misses else None,
            "false_alarm_share": fa / (hits + fa) if hits + fa else None}


# ---------------------------------------------------------------- count
def stage_count(a) -> None:
    b = lsb.build(a)
    test, status = b["test"], b["status"]
    out = {"inputs": b["inputs"], "window_e": b["site_info"], "per_company": {}, "rules": {}}
    comp = test["company"].to_numpy()
    for c in COMPS:
        m = np.ones(len(test), bool) if c == "all nine" else comp == c
        row = {"overflows": int(test.loc[m, "site_id"].nunique()), "rows_era5": int(m.sum())}
        for k in LEADS:
            row[f"rows_forecast_lead{k}"] = int(m[b["leadrows"][k][0]].sum())
        out["per_company"][c] = row
    r_era = rain_side(test["rain_d"].to_numpy(), test["rain_d1"].to_numpy())
    for k in LEADS:
        p = persistence_side(status, test["site_id"], test["day"], k)
        pos, fr = b["leadrows"][k]
        r_f = rain_side(fr["rain_d"].to_numpy(), fr["rain_d1"].to_numpy())
        out["rules"][f"lead {k}"] = {"era5_P_applicable": int(np.isfinite(p).sum()), "era5_R_applicable": int(np.isfinite(r_era).sum()),
                                     "forecast_P_applicable": int(np.isfinite(p[pos]).sum()), "forecast_R_applicable": int(np.isfinite(r_f).sum())}
    print(json.dumps(out, indent=1, default=str))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "counts.json").write_text(json.dumps(out, indent=1, default=str))


# ---------------------------------------------------------------- run
def stage_run(a) -> None:
    cands, d2, prod, cal = lsb.load_models(a)
    rr.check_v2(V2)
    v2 = SpillModel.load(V2)
    b = lsb.build(a)
    test, status, leadrows = b["test"], b["status"], b["leadrows"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    checks: dict = {"inputs": b["inputs"], "window_e": b["site_info"], "merged_events": b["n_intervals"],
                    "models": {"candidates": lsb.CANDIDATE_SHA, "d2": lsb.D2_SHA, "production": lsb.PROD_SHA,
                               "lead_map": lsb.LEADCAL_SHA, "v2": rr.V2_SHA256},
                    "settings": {"clip": CLIP, "rain_rule_mm": RAIN_RULE_MM, "fit_days": FIT_DAYS,
                                 "min_fit_rows": MIN_FIT_ROWS, "warn_at": WARN_AT, "n_boot": lsb.N_BOOT, "seed": lsb.SEED},
                    "status_unknown": {}, "rule_rows": {}}
    y = test["y"].to_numpy().astype(float)
    company = test["company"].to_numpy()
    tday = ((test["day"] - pd.Timestamp(lsb.FIRST, tz="UTC")) // pd.Timedelta(days=1)).to_numpy().astype(np.int64)
    tw = lsb.TwoWay(test["site_id"].to_numpy(), lsb.week_codes(test["day"]), np.random.default_rng(lsb.SEED))
    step("bootstrap draws made")
    cmask = {c: (np.ones(len(y), bool) if c == "all nine" else company == c) for c in COMPS}

    p_prod = prod.predict(test)
    p_route, route = rr.predict(test, v2, prod)
    p_d2 = d2.predict(test)
    checks["route_rows"] = {"v2": int((route == rr.V2).sum()), "production": int((route == rr.FALLBACK).sum()),
                            "production_rows_all_united_utilities": bool((company[route == rr.FALLBACK] == "United Utilities").all())}
    r_era = rain_side(test["rain_d"].to_numpy(), test["rain_d1"].to_numpy())

    score_rows, int_rows, warn_rows = [], [], []

    def score(rain, k, c, name, yy, p, rows_label):
        s = scores(yy, p)
        score_rows.append({"rain": rain, "lead": k, "company": c, "predictor": name, "rows": rows_label, "n": len(yy),
                           "base_rate": float(yy.mean()), "brier": s["brier"], "auc": s["auc"], "log_loss": s["log_loss"],
                           "ece": ece(yy, p), "mean_forecast": float(p.mean())})
        warn_rows.append({"rain": rain, "lead": k, "company": c, "predictor": name, "rows": rows_label,
                          **warning_counts(yy, p >= WARN_AT)})

    def compare(rain, k, c, ref, d_full, mask):
        lo, hi = tw.interval(d_full, mask)
        wlo, whi = tw.week_only(d_full, mask)
        int_rows.append({"rain": rain, "lead": k, "company": c, "reference": ref, "rows": int(mask.sum()),
                         "spill_rows": int(y[mask].sum()), "difference": float(d_full[mask].mean()),
                         "ci_low": lo, "ci_high": hi, "week_ci_low": wlo, "week_ci_high": whi})

    for k in LEADS:
        st = status.features(test["site_id"], test["day"], k)
        unknown = st.isna().any(axis=1).to_numpy()
        checks["status_unknown"][f"lead {k}"] = int(unknown.sum())
        x = pd.concat([test.drop(columns=[c for c in lsb.STATUS if c in test]), st], axis=1)
        p_cand = cands[k].predict(x)
        preds = {"combined-v1": combine(p_route, p_cand, p_d2, unknown),
                 "production": p_prod,
                 "live status alone": np.where(unknown, p_prod, p_cand),     # #639's Q2 predictor
                 "routing alone": p_route}
        p_side = persistence_side(status, test["site_id"], test["day"], k)
        p_P = trailing_chance(p_side, y, tday, k)
        p_R = trailing_chance(r_era, y, tday, k)
        common = np.isfinite(p_P) & np.isfinite(p_R)
        checks["rule_rows"][f"ERA5-Land lead {k}"] = {"P": int(np.isfinite(p_P).sum()), "R": int(np.isfinite(p_R).sum()),
                                                      "common": int(common.sum())}
        for name, p in preds.items():
            if not np.isfinite(p).all():
                raise SystemExit(f"{name} gave a non-finite forecast at lead {k}")
        se = {n: (p - y) ** 2 for n, p in preds.items()}
        se_P, se_R = np.where(common, (np.nan_to_num(p_P) - y) ** 2, 0.0), np.where(common, (np.nan_to_num(p_R) - y) ** 2, 0.0)
        for c in COMPS:
            m = cmask[c]
            mc = m & common
            for name, p in preds.items():
                score("ERA5-Land", k, c, name, y[m], p[m], "all")
                score("ERA5-Land", k, c, name, y[mc], p[mc], "common")
            score("ERA5-Land", k, c, "persistence P", y[mc], p_P[mc], "common")
            score("ERA5-Land", k, c, "rain rule R", y[mc], p_R[mc], "common")
            warn_rows.append({"rain": "ERA5-Land", "lead": k, "company": c, "predictor": "P as a yes/no warning", "rows": "common",
                              **warning_counts(y[mc], p_side[mc] == 1)})
            warn_rows.append({"rain": "ERA5-Land", "lead": k, "company": c, "predictor": "R as a yes/no warning", "rows": "common",
                              **warning_counts(y[mc], r_era[mc] == 1)})
            for ref in ("production", "live status alone", "routing alone"):
                compare("ERA5-Land", k, c, ref, se["combined-v1"] - se[ref], m)
            compare("ERA5-Land", k, c, "persistence P", se["combined-v1"] - se_P, mc)
            compare("ERA5-Land", k, c, "rain rule R", se["combined-v1"] - se_R, mc)
            compare("ERA5-Land", k, c, "check: live status alone vs production", se["live status alone"] - se["production"], m)
            compare("ERA5-Land", k, c, "check: routing alone vs production", se["routing alone"] - se["production"], m)
        step(f"lead {k}, ERA5-Land: combined {se['combined-v1'].mean():.5f}, production {se['production'].mean():.5f}, "
             f"live status {se['live status alone'].mean():.5f}, routing {se['routing alone'].mean():.5f}")

        # ---- forecast rain (#254's rows and features; reported, not deciding)
        pos, fr = leadrows[k]
        r = test.iloc[pos]
        fr.index = r.index
        xk = pd.concat([r[["site_id", "company", *lst.STATIC]], fr, st.iloc[pos]], axis=1)
        yk = y[pos]
        f_raw = prod.predict(xk)
        f_cal = _apply(cal[min(k, max(cal))], f_raw)
        f_route, _ = rr.predict(xk, v2, prod)
        f_cand, f_d2 = cands[k].predict(xk), d2.predict(xk)
        uk = unknown[pos]
        fpreds = {"combined-v1": combine(f_route, f_cand, f_d2, uk), "production": f_cal,
                  "live status alone": np.where(uk, f_cal, f_cand), "routing alone": f_route,
                  "production, no lead map": f_raw}
        fP = trailing_chance(p_side[pos], yk, tday[pos], k)
        fR = trailing_chance(rain_side(fr["rain_d"].to_numpy(), fr["rain_d1"].to_numpy()), yk, tday[pos], k)
        fcommon = np.isfinite(fP) & np.isfinite(fR)
        checks["rule_rows"][f"forecast lead {k}"] = {"rows": len(pos), "common": int(fcommon.sum())}
        lm = np.zeros(len(y), bool)
        lm[pos] = True
        lc = np.zeros(len(y), bool)
        lc[pos[fcommon]] = True

        def full(v):
            o = np.zeros(len(y))
            o[pos] = v
            return o
        fse = {n: (p - yk) ** 2 for n, p in fpreds.items()}
        for c in COMPS:
            mk = cmask[c][pos]
            if not mk.any():
                continue
            mkc = mk & fcommon
            for name, p in fpreds.items():
                score("forecast", k, c, name, yk[mk], p[mk], "all")
            if mkc.any():
                score("forecast", k, c, "persistence P", yk[mkc], fP[mkc], "common")
                score("forecast", k, c, "rain rule R", yk[mkc], fR[mkc], "common")
                for name, p in fpreds.items():
                    score("forecast", k, c, name, yk[mkc], p[mkc], "common")
            for ref in ("production", "live status alone", "routing alone"):
                compare("forecast", k, c, ref, full(fse["combined-v1"] - fse[ref]), cmask[c] & lm)
            if mkc.any():
                compare("forecast", k, c, "persistence P", full(np.where(fcommon, fse["combined-v1"] - (np.nan_to_num(fP) - yk) ** 2, 0)), cmask[c] & lc)
                compare("forecast", k, c, "rain rule R", full(np.where(fcommon, fse["combined-v1"] - (np.nan_to_num(fR) - yk) ** 2, 0)), cmask[c] & lc)
            compare("forecast", k, c, "check: live status alone vs production", full(fse["live status alone"] - fse["production"]), cmask[c] & lm)
        step(f"lead {k}, forecast rain: {len(pos)} rows, combined {fse['combined-v1'].mean():.5f}, production {fse['production'].mean():.5f}")

    sc, iv, wn = pd.DataFrame(score_rows), pd.DataFrame(int_rows), pd.DataFrame(warn_rows)
    # ---- the pass bar: ERA5-Land, leads 1 and 2, lower than production, P and R with the interval below zero
    bar = {}
    for c in COMPS:
        I = iv[(iv["rain"] == "ERA5-Land") & (iv["company"] == c)].set_index(["lead", "reference"])
        cells = {f"lead {k} vs {ref}": bool(I.loc[(k, ref), "difference"] < 0 and I.loc[(k, ref), "ci_high"] < 0)
                 for k in BAR_LEADS for ref in BAR_REFS}
        bar[c] = {"passes": all(cells.values()), **cells}
    checks["bar"] = bar
    sc.to_csv(out / "scores.csv", index=False)
    iv.to_csv(out / "intervals.csv", index=False)
    wn.to_csv(out / "warnings.csv", index=False)
    (out / "checks.json").write_text(json.dumps(checks, indent=1, default=str))
    pd.set_option("display.width", 250)
    show = iv[(iv["company"] == "all nine") & (iv["rain"] == "ERA5-Land")]
    print(show.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    for c, v in bar.items():
        print(c, v)
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
