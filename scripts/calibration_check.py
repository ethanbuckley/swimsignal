"""The calibration check (docs/CALIBRATION-CHECK-2026-10.md): whether the live spill forecast's chances
run too high, where, and across which range of chances. A diagnostic only: nothing is refitted, and the
logistic fits describe the forecast; no corrected forecast is made or scored. The diagnostics, strata,
missing-data rules and the judgement rules are stated in the doc, before the run.

The same fixed record as the interim usefulness read (PR #338), checked by hash; its rows are rebuilt
with that read's own functions (scripts/interim_usefulness.py) and its bootstrap (evaluate_2027.Bootstrap,
same seed and draws):

    uv run python scripts/calibration_check.py --scored verification_live.csv --state /tmp/s \\
        --out docs/CALIBRATION-CHECK-2026-10.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_2027 import SPILL_CUTS, Bootstrap, read_published, sha256  # noqa: E402
from interim_usefulness import (  # noqa: E402
    FIRST_DAY, RESAMPLES, SEED, SQL, block_of, decision_rows, fit_two_sided, persistence_status, rain_48h,
)

from dipcast.forecast_log import LOCAL_TZ, load_coverage  # noqa: E402

# The record PR #338 scored (docs/INTERIM-USEFULNESS-2026-10.json, inputs). A different file stops the run.
EXPECTED = {
    "scored": "434f910aa0170ec59bba08eaf5f038b423caae0209b4c89ac75891de786eb598",
    "dipcast.duckdb": "8544507fda525c3cb7f3cb3e246d57728e911cbf54dbe6b9e35d519313aed4e7",
    "live_history.parquet": "b38bb6a8e7f58e501b11d01af03dd19006926b1b4bc74fc6437233fb61349052",
    "live_coverage.parquet": "75cdd298c062cc28b907b25bdaf8b1577496f0741775c0812f5be731c5542676",
    "poll_log.parquet": "b09aafb84e2a9be1ba4eedd03b0dceadc457f329b667a2f506e50cf424f63662",
}
# The pre-registration's spill bands, the low one split where most forecasts fall.
CUTS = (0.01, 0.03, 0.07, *SPILL_CUTS)
BAND_NAMES = ("under 0.01", "0.01-0.03", "0.03-0.07", "0.07-0.15", "0.15-0.40", "0.40-0.70", "0.70 or more")
LEAD_GROUPS = {"0": (0,), "1-4": (1, 2, 3, 4)}
EACH_LEAD = {str(k): (k,) for k in range(5)}
MIN_JUDGED = 50        # overflow-days with a spill below which a stratum is reported, not judged
MIN_BAND_SPILLS = 20   # spill overflow-days a band needs to count in the too-extreme rule
EPS = 1e-4


def bands(p: np.ndarray) -> np.ndarray:
    """0-6, a value on a cut in the band above it (as evaluate_2027.band_index)."""
    return np.searchsorted(np.asarray(CUTS), p, side="right")


def logit(p: np.ndarray) -> np.ndarray:
    q = np.clip(p, EPS, 1 - EPS)
    return np.log(q / (1 - q))


def fit_offset(y, x, w, a0=0.0, iters=25):
    """a in logit P(y) = a + x, weighted (the slope fixed at 1): Newton's method."""
    a = a0
    for _ in range(iters):
        m = 1 / (1 + np.exp(-(a + x)))
        g, h = np.dot(w, y - m), np.dot(w, m * (1 - m))
        if h <= 0:
            return np.nan
        step = g / h
        a += step
        if abs(step) < 1e-9:
            break
    return a


def fit_line(y, x, w, start=(0.0, 1.0), iters=25):
    """(alpha, b) in logit P(y) = alpha + b x, weighted: Newton's method on the two parameters."""
    al, b = start
    for _ in range(iters):
        m = 1 / (1 + np.exp(-(al + b * x)))
        r, v = y - m, m * (1 - m)
        g = np.array([np.dot(w, r), np.dot(w, r * x)])
        wv = w * v
        h = np.array([[wv.sum(), np.dot(wv, x)], [np.dot(wv, x), np.dot(wv, x * x)]])
        try:
            step = np.linalg.solve(h, g)
        except np.linalg.LinAlgError:
            return np.nan, np.nan
        al, b = al + step[0], b + step[1]
        if np.abs(step).max() < 1e-9:
            break
    return al, b


def murphy(y, p, band, w):
    """Brier score and its band decomposition: reliability - resolution + uncertainty (+ within-band rest)."""
    sw = w.sum()
    obar = np.dot(w, y) / sw
    rel = res = 0.0
    for k in np.unique(band):
        m = band == k
        nk = w[m].sum()
        if nk <= 0:
            continue
        fk, ok = np.dot(w[m], p[m]) / nk, np.dot(w[m], y[m]) / nk
        rel += nk * (fk - ok) ** 2
        res += nk * (ok - obar) ** 2
    brier = np.dot(w, (p - y) ** 2) / sw
    unc = obar * (1 - obar)
    return {"brier": brier, "reliability": rel / sw, "resolution": res / sw, "uncertainty": unc,
            "within_band": brier - (rel / sw - res / sw + unc)}


def point_and_draws(g: pd.DataFrame, rows: np.ndarray, boot: Bootstrap) -> dict:
    y, p = g["y"].to_numpy(float), g["p"].to_numpy(float)
    x, band = logit(p), bands(p)
    one = np.ones(len(g))
    a_pt = fit_offset(y, x, one)
    line_pt = fit_line(y, x, one)

    def stats(w):
        sw = w.sum()
        if sw <= 0 or np.dot(w, y) <= 0:
            return None
        e, o = np.dot(w, p) / sw, np.dot(w, y) / sw
        out = {"o_over_e": o / e, "a": fit_offset(y, x, w, a_pt)}
        out["alpha"], out["b"] = fit_line(y, x, w, line_pt)
        for k in range(len(BAND_NAMES)):
            m = band == k
            nk = w[m].sum()
            out[f"band{k}"] = np.dot(w[m], y[m]) / nk if nk > 0 else np.nan
        return out

    point = stats(one)
    reps = [stats(boot.weights(r, rows)) for r in range(len(boot.draws))]
    ci = {}
    for k in point:
        a = np.array([r[k] if r else np.nan for r in reps], float)
        ok = a[np.isfinite(a)]
        ci[k] = {"lo": float(np.percentile(ok, 2.5)) if len(ok) else None,
                 "hi": float(np.percentile(ok, 97.5)) if len(ok) else None, "undefined_draws": int(len(a) - len(ok))}
    return {"point": point, "ci": ci, "murphy": murphy(y, p, band, one)}


def describe(df: pd.DataFrame, rows: np.ndarray, boot: Bootstrap) -> dict:
    g = df.iloc[rows]
    spill = g[g["y"] == 1]
    od = g[["overflow_id", "day"]].drop_duplicates().shape[0]
    sod = spill[["overflow_id", "day"]].drop_duplicates().shape[0]
    out = {"rows": len(g), "overflow_days": int(od), "spill_rows": len(spill), "spill_overflow_days": int(sod),
           "observed_rate": float(g["y"].mean()) if len(g) else None,
           "mean_forecast": float(g["p"].mean()) if len(g) else None}
    if not len(spill):
        return out
    pc = point_and_draws(g, rows, boot)
    pt, ci = pc["point"], pc["ci"]
    out.update({"o_over_e": pt["o_over_e"], "a": pt["a"], "alpha": pt["alpha"], "b": pt["b"], "murphy": pc["murphy"],
                "ci": {k: ci[k] for k in ("o_over_e", "a", "alpha", "b")}})
    band = bands(g["p"].to_numpy(float))
    out["bands"] = []
    for k, name in enumerate(BAND_NAMES):
        m = band == k
        gb = g[m]
        out["bands"].append({"band": name, "rows": int(m.sum()),
                             "overflow_days": int(gb[["overflow_id", "day"]].drop_duplicates().shape[0]),
                             "spill_overflow_days": int(gb[gb["y"] == 1][["overflow_id", "day"]].drop_duplicates().shape[0]),
                             "mean_forecast": float(gb["p"].mean()) if m.any() else None,
                             "observed": float(gb["y"].mean()) if m.any() else None,
                             "observed_ci": ci[f"band{k}"]})
    blk = block_of(g["day"])
    out["blocks"] = []
    for k in np.unique(blk):
        gb = g[blk == k]
        e = gb["p"].mean()
        out["blocks"].append({"from": gb["day"].min(), "to": gb["day"].max(), "rows": len(gb),
                              "spill_overflow_days": int(gb[gb["y"] == 1][["overflow_id", "day"]].drop_duplicates().shape[0]),
                              "observed_rate": float(gb["y"].mean()), "mean_forecast": float(e),
                              "o_over_e": float(gb["y"].mean() / e) if e > 0 else None})
    out["judgement"] = judge(out)
    return out


def judge(r: dict) -> dict:
    """The rules stated in the doc, applied to one stratum."""
    if r["spill_overflow_days"] < MIN_JUDGED:
        return {"average": "not judged (fewer than 50 overflow-days with a spill)", "range": "not judged"}
    oe = r["ci"]["o_over_e"]
    below_blocks = sum(1 for b in r["blocks"] if b["o_over_e"] is not None and b["o_over_e"] < 1)
    if oe["hi"] is not None and oe["hi"] < 1 and below_blocks >= 3:
        avg = "too high on average"
    elif oe["hi"] is not None and oe["hi"] < 1:
        avg = f"interval below 1, but below 1 in only {below_blocks} of {len(r['blocks'])} blocks: not met"
    elif oe["lo"] is not None and oe["lo"] > 1:
        avg = "too low on average (contradicts overprediction)"
    else:
        avg = "no clear evidence either way"
    bc = r["ci"]["b"]
    upper = [b for b in r["bands"][4:] if b["spill_overflow_days"] >= MIN_BAND_SPILLS]
    upper_high = bool(upper) and all(b["observed"] < b["mean_forecast"] for b in upper)
    if bc["hi"] is not None and bc["hi"] < 1 and upper_high:
        rng = "too extreme: high chances too high"
    elif bc["hi"] is not None and bc["hi"] < 1:
        rng = "slope below 1, but the bands from 0.15 do not all sit above their observed rate: not met"
    elif bc["lo"] is not None and bc["lo"] > 1:
        rng = "too timid (contradicts overprediction at high chances)"
    else:
        rng = "no clear evidence either way"
    return {"average": avg, "range": rng, "blocks_below_1": below_blocks, "upper_bands_used": len(upper)}


def check_inputs(scored: Path, state: Path) -> dict:
    got = {"scored": sha256(scored), **{f: sha256(state / f) for f in EXPECTED if f != "scored"}}
    bad = [k for k in EXPECTED if got[k] != EXPECTED[k]]
    if bad:
        raise SystemExit(f"not the record PR #338 scored: {', '.join(bad)} differ")
    return got


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", required=True, type=Path)
    ap.add_argument("--state", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--resamples", type=int, default=RESAMPLES)
    a = ap.parse_args()
    hashes = check_inputs(a.scored, a.state)

    # The rows, exactly as interim_usefulness.main builds them.
    sc = read_published(a.scored)
    sc = sc[sc["day"] >= str(FIRST_DAY)].reset_index(drop=True)
    first, last = sc["day"].min(), sc["day"].max()
    con = duckdb.connect(str(a.state / "dipcast.duckdb"), read_only=True)
    try:
        log = con.execute(SQL, [str(date.fromisoformat(first) - timedelta(days=1)), last]).df()
    finally:
        con.close()
    log["site_id"] = log["site_id"].astype(str)
    log["target_day"] = pd.to_datetime(log["target_day"])
    dec = decision_rows(log)
    dec = dec.assign(day=dec["target_day"].dt.strftime("%Y-%m-%d"))
    df = sc.merge(dec[["site_id", "day", "lead", "issued_ms", "target_day", "rain_mm", "spilling_at_issue"]],
                  left_on=["overflow_id", "day", "lead"], right_on=["site_id", "day", "lead"], how="left")
    issued_min = pd.to_datetime(df["issued_ms"], unit="ms", utc=True).dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%dT%H:%M%:z")
    match = df["issued_ms"].notna() & (issued_min == df["issued_at"])
    df["y"], df["p"] = df["observed"].astype(float), df["forecast_calibrated"].astype(float)
    j = df[match].copy()
    j = j.assign(site_id=j["site_id"].astype(str), issued_ms=j["issued_ms"].astype(np.int64))
    df["rain48"] = np.nan
    df.loc[match, "rain48"] = rain_48h(j, log).to_numpy()
    rain_ok = df["rain48"].notna().to_numpy()
    ps = persistence_status(j, pd.read_parquet(a.state / "live_history.parquet"),
                            load_coverage(a.state / "live_coverage.parquet"), pd.read_parquet(a.state / "poll_log.parquet"))
    for c in ps:
        df[c] = False
        df.loc[ps.index, c] = ps[c].to_numpy()
    known = df["known"].to_numpy(bool)
    common = known & rain_ok
    lead = df["lead"].to_numpy()

    boot = Bootstrap(df["overflow_id"].to_numpy(), block_of(df["day"]), a.resamples, SEED)
    companies = ["All companies", *sorted(c for c in df["company"].dropna().unique() if c != "unknown")]
    results = []
    for comp in companies:
        cm = np.ones(len(df), bool) if comp == "All companies" else (df["company"] == comp).to_numpy()
        groups = {**LEAD_GROUPS, **(EACH_LEAD if comp == "All companies" else {})}
        for lg, leads in groups.items():
            lm = np.isin(lead, leads)
            res = {"company": comp, "leads": lg, "all_scored": describe(df, np.flatnonzero(cm & lm), boot)}
            if lg in LEAD_GROUPS:
                res["common_rows"] = describe(df, np.flatnonzero(cm & lm & common), boot)
            results.append(res)
            s = res["all_scored"]
            print(comp, lg, round(s.get("o_over_e", float("nan")), 3), s.get("ci", {}).get("o_over_e"),
                  round(s.get("b", float("nan")), 3), s.get("judgement"), flush=True)
    unknown = df["company"].isna() | (df["company"] == "unknown")

    # Sensitivity: persistence from the shadow's own logged status, as it was at issue (point estimates only).
    sh = df["spilling_at_issue"].notna().to_numpy() & match.to_numpy()
    sens = None
    if sh.any():
        y = df["y"].to_numpy(float)
        on = (df["spilling_at_issue"].fillna(0).to_numpy() > 0)
        asof, _ = fit_two_sided(y, on, lead, sh)
        rebuilt, _ = fit_two_sided(y, df["active"].to_numpy(bool), lead, sh & known)
        sens = []
        for lg, leads in LEAD_GROUPS.items():
            m = sh & np.isin(lead, leads)
            mk = m & known
            bf = float(np.mean((df["p"].to_numpy()[m] - y[m]) ** 2))
            ba = float(np.mean((asof[m] - y[m]) ** 2))
            row = {"leads": lg, "rows": int(m.sum()), "first_day": df.loc[m, "day"].min(), "last_day": df.loc[m, "day"].max(),
                   "spill_rows": int(y[m].sum()), "brier_forecast": bf, "brier_persistence_as_of": ba,
                   "skill_vs_as_of": 1 - bf / ba if ba > 0 else None}
            if mk.any():
                bfk, brk = float(np.mean((df["p"].to_numpy()[mk] - y[mk]) ** 2)), float(np.mean((rebuilt[mk] - y[mk]) ** 2))
                row.update({"rows_status_known": int(mk.sum()), "brier_forecast_known": bfk,
                            "brier_persistence_rebuilt": brk, "skill_vs_rebuilt": 1 - bfk / brk if brk > 0 else None})
            sens.append(row)

    out = {"inputs": {"scored": {"file": a.scored.name, "sha256": hashes["scored"], "rows": len(sc), "first_day": first,
                                 "last_day": last}, **{k: v for k, v in hashes.items() if k != "scored"}},
           "settings": {"resamples": a.resamples, "seed": SEED, "cuts": list(CUTS), "bands": list(BAND_NAMES),
                        "min_judged_spill_overflow_days": MIN_JUDGED, "min_band_spill_overflow_days": MIN_BAND_SPILLS,
                        "logit_clip": EPS},
           "rows": {"all_scored": len(df), "common": int(common.sum()), "unknown_company": int(unknown.sum()),
                    "issue_time_matches": int(match.sum())},
           "bootstrap": {"overflows": len(boot.site_codes), "blocks": len(boot.block_codes)},
           "results": results, "sensitivity_persistence_as_of": sens}
    text = json.dumps(out, indent=1, default=float)
    if a.out:
        a.out.write_text(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
