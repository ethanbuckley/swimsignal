"""The test pre-stated in docs/LIVE-RECALIBRATION-TEST-2026-10.md: would a correction fitted on live
scored overflow-days improve the forecasts it was not fitted on?

    uv run python scripts/live_recalibration_test.py verification_live.csv

Reads the published verification_live.csv and prints the measures and the adoption rule's verdict.
Changes nothing in the forecast."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

CLIP = (0.001, 0.999)


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), *CLIP)
    return np.log(p / (1 - p))


def fit_predict(kind: str, train: pd.DataFrame, test: pd.DataFrame, companies: list[str]) -> np.ndarray:
    if kind == "A":
        iso = IsotonicRegression(y_min=CLIP[0], y_max=CLIP[1], out_of_bounds="clip")
        iso.fit(train["forecast_calibrated"], train["observed"])
        return iso.predict(test["forecast_calibrated"])

    def design(d):
        return np.column_stack([logit(d["forecast_calibrated"])]
                               + [(d["company"] == c).to_numpy(dtype=float) for c in companies])
    lr = LogisticRegression(C=100, fit_intercept=False, max_iter=2000)
    lr.fit(design(train), train["observed"])
    return lr.predict_proba(design(test))[:, 1]


def brier(p, y) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def main(path: str) -> int:
    df = pd.read_csv(path, comment="#")
    df["observed"] = df["observed"].astype(int)
    days = sorted(df["day"].unique())
    companies = sorted(df["company"].unique())
    print(f"{len(df)} rows, {len(days)} days ({days[0]} to {days[-1]}), {len(companies)} companies")
    out = {k: np.full(len(df), np.nan) for k in "AB"}
    for d in days:
        tr, te = df["day"] != d, df["day"] == d
        for k in "AB":
            out[k][te.to_numpy()] = fit_predict(k, df[tr], df[te], companies)
    y, base = df["observed"].to_numpy(), df["forecast_calibrated"].to_numpy()
    res = {"current": base, **out}
    print("\nPooled, leave one day out")
    for k, p in res.items():
        print(f"  {k:8s} Brier {brier(p, y):.5f}  AUC {roc_auc_score(y, p):.4f}  mean {np.mean(p):.4f} (observed {y.mean():.4f})")
    print("\nPer company Brier (current / A / B), base rate")
    for c in companies:
        m = (df["company"] == c).to_numpy()
        print(f"  {c:20s} {brier(base[m], y[m]):.5f} / {brier(out['A'][m], y[m]):.5f} / {brier(out['B'][m], y[m]):.5f}"
              f"   base {y[m].mean():.4f} n {m.sum()}")
    wins = {k: sum(brier(out[k][(df['day'] == d).to_numpy()], y[(df['day'] == d).to_numpy()])
                   < brier(base[(df['day'] == d).to_numpy()], y[(df['day'] == d).to_numpy()]) for d in days) for k in "AB"}
    print("\nHeld-out days where the candidate's Brier is lower:", wins, "of", len(days))
    half = days[: len(days) // 2]
    first = df["day"].isin(half)
    block = {}
    for k in "AB":
        f2s = fit_predict(k, df[first], df[~first], companies)
        s2f = fit_predict(k, df[~first], df[first], companies)
        block[k] = (brier(f2s, y[~first.to_numpy()]) < brier(base[~first.to_numpy()], y[~first.to_numpy()]),
                    brier(s2f, y[first.to_numpy()]) < brier(base[first.to_numpy()], y[first.to_numpy()]))
        print(f"Block check {k}: first->second lower: {block[k][0]}, second->first lower: {block[k][1]}")
    print("\nReliability, held out (bin: n, current forecast/observed, A forecast, B forecast)")
    bins = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(base, bins) - 1, 0, 9)
    for b in range(10):
        m = idx == b
        if m.sum():
            print(f"  {bins[b]:.1f}-{bins[b+1]:.1f}: n {m.sum():6d}  {base[m].mean():.3f}/{y[m].mean():.3f}"
                  f"  A {out['A'][m].mean():.3f}  B {out['B'][m].mean():.3f}")
    b0, auc0 = brier(base, y), roc_auc_score(y, base)
    passed = {}
    for k in "AB":
        c1 = brier(out[k], y) <= 0.95 * b0
        c2 = wins[k] >= 8
        c3 = roc_auc_score(y, out[k]) >= auc0 - 0.005
        c4 = all(block[k])
        passed[k] = c1 and c2 and c3 and c4
        print(f"\nCandidate {k}: (1) Brier >=5% lower: {c1}; (2) >=8 of 12 days: {c2}; (3) AUC kept: {c3}; "
              f"(4) both blocks: {c4} -> {'PASS' if passed[k] else 'fail'}")
    ok = [k for k in "AB" if passed[k]]
    choice = min(ok, key=lambda k: brier(out[k], y)) if ok else None
    print("\nVerdict:", f"candidate {choice} passes and is preferred" if choice else "neither passes; nothing changes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
