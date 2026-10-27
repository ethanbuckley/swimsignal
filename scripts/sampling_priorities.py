"""Rank where and on which days a new E. coli sample would teach the model most, and list high-risk days apart.
Offline prototype (docs/SAMPLING-PRIORITIES-SIM-2026-10.md); no network, writes nothing unless --out is given.

With saved rows (`ecoli_validation_rows.parquet`, from validate_ecoli.py; --rows to point elsewhere, read only):
  model A  today's inputs, `ecoli.FEATURES` (rain, overflow exposure, lake, season)
  model B  the "rain + season" variant of train_ecoli.py, with no exposure term
  So "models disagree" marks a day where a sample would say whether overflow exposure matters there.
  Candidates come from --candidates (a CSV or parquet with site, day, rain_48h, rain_24h, risk, kind: for example a
  forecast export), else three scenario days per site (dry, moderate, wet) in mid-July, with the site's own median
  exposure on rows of similar rain. Scenario days rank sites; they are not a dated plan.

With no saved rows (or --synthetic): the synthetic world of the simulation, seed 1, week 0 of the planned season.

    uv run python scripts/sampling_priorities.py
    uv run python scripts/sampling_priorities.py --rows ../../data/processed/ecoli_validation_rows.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.model.ecoli import FEATURES, THRESHOLD, features
from dipcast.sampling_priorities import (COLS_A, COLS_B, fit_ensemble, forecast_view, high_risk, history_rows, plan,
                                         reason, score_candidates, synthetic_world)

RAIN_SEASON = ["lrain48", "lrain24", "lake", "lake_x_lrain48", "doy_sin", "doy_cos"]
SCENARIOS = {"dry": (0.0, 0.0), "moderate": (8.0, 4.0), "wet": (25.0, 15.0)}
SCENARIO_DATE = "2027-07-15 12:00"


def real_inputs(rows_path: Path, cand_path: Path | None):
    rows = pd.read_parquet(rows_path)
    rows = rows[rows.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "ecoli"]).reset_index(drop=True)
    lake = (rows["kind"] == "lake").astype(float)
    X = features(rows.rain_48h, rows.rain_24h, rows.risk_model, lake, rows.sample_time)
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    if cand_path is not None:
        c = pd.read_csv(cand_path) if cand_path.suffix == ".csv" else pd.read_parquet(cand_path)
        c["lake"] = (c["kind"] == "lake").astype(float)
    else:
        bucket = lambda r: np.select([r < 2, r < 15], ["dry", "moderate"], "wet")
        rows["bucket"] = bucket(rows.rain_48h.to_numpy())
        med = rows.groupby(["bw_id", "bucket"]).risk_model.median()
        site_med = rows.groupby("bw_id").risk_model.median()
        meta = rows.drop_duplicates("bw_id").set_index("bw_id")
        recs = []
        for s in meta.index:
            for name, (r48, r24) in SCENARIOS.items():
                recs.append({"site": s, "day": f"scenario: {name}", "rain_48h": r48, "rain_24h": r24,
                             "risk": med.get((s, name), site_med[s]), "kind": meta.at[s, "kind"]})
        c = pd.DataFrame(recs)
        c["lake"] = (c["kind"] == "lake").astype(float)
        c["when"] = pd.Timestamp(SCENARIO_DATE)
    when = c["when"] if "when" in c else pd.to_datetime(c["day"])
    Xc = features(c.rain_48h, c.rain_24h, c.risk, c.lake, when)
    cand = pd.concat([c[["site", "day", "kind", "rain_48h"]].reset_index(drop=True), Xc], axis=1)
    names = rows.drop_duplicates("bw_id").set_index("bw_id")["name"].to_dict()
    A = fit_ensemble(X, y, rows.bw_id, FEATURES, "today's model", sorted(set(cand.site)), n_boot=30, seed=0)
    B = fit_ensemble(X, y, rows.bw_id, RAIN_SEASON, "rain + season", sorted(set(cand.site)), n_boot=30, seed=0)
    return cand, A, B, names, ("with exposure", "rain only")


def synthetic_inputs():
    w = synthetic_world(1)
    hist = history_rows(w, 1)
    names = w.sites["site"].tolist()
    A = fit_ensemble(hist, hist.y, hist.site, COLS_A, "A", names, n_boot=20, seed=0)
    B = fit_ensemble(hist, hist.y, hist.site, COLS_B, "B", names, n_boot=20, seed=0)
    season = w.days[(w.days.season == 2) & (w.days.week == 0) & (w.days.dow < 5)]
    cand = forecast_view(season, np.random.default_rng(1)).reset_index(drop=True)
    return cand, A, B, {s: s for s in names}, ("no soil term", "with soil term")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path, default=config.PROCESSED / "ecoli_validation_rows.parquet")
    ap.add_argument("--candidates", type=Path)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--budget", type=int, default=10)
    ap.add_argument("--per-day", type=int, default=2)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--out", type=Path, help="prefix for two CSVs: <out>-informative.csv, <out>-high-risk.csv")
    a = ap.parse_args()
    if a.synthetic or not a.rows.exists():
        print("no saved rows: synthetic world (seed 1), week 0 of the planned season" if not a.synthetic else "synthetic world")
        cand, A, B, names, labels = synthetic_inputs()
        per_day = a.per_day
    else:
        print(f"saved rows: {a.rows}")
        cand, A, B, names, labels = real_inputs(a.rows, a.candidates)
        per_day = a.per_day if a.candidates is not None else a.budget   # scenario days are not dates
    print(f"model A ({A.name}): tau {A.tau:.2f}; model B ({B.name}): tau {B.tau:.2f}; {len(cand)} candidates")
    picks, _ = plan(cand, A, B, budget=a.budget, per_day=per_day)
    picks["name"] = picks["site"].map(names)
    picks["reason"] = [reason(r, labels) for _, r in picks.iterrows()]
    risk = high_risk(cand, A, B, top=a.top)
    risk["name"] = risk["site"].map(names)
    scored = score_candidates(cand, A, B).sort_values("info_bits", ascending=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_colwidth", 120)
    show = ["order", "name", "day", "p_mean", "p_a", "p_b", "info_at_pick", "reason"]
    print(f"\n=== informativeness: a greedy plan of {a.budget} samples (bits of information about the models) ===")
    print(picks[show].round(3).to_string(index=False))
    print(f"\n=== high risk, separate: chance over {THRESHOLD} of at least 0.3 (swimmer protection, not learning) ===")
    print(risk[["name", "day", "p_mean", "reason"]].round(3).to_string(index=False) if len(risk) else "none")
    overlap = len(set(zip(picks.site, picks.day, strict=True)) & set(zip(risk.site, risk.day, strict=True)))
    print(f"\n{overlap} of {len(picks)} planned samples are also on the high-risk list. "
          f"Top information score {scored.info_bits.iloc[0]:.3f} bits; median {scored.info_bits.median():.3f}.")
    if a.out:
        picks.to_csv(f"{a.out}-informative.csv", index=False)
        risk.to_csv(f"{a.out}-high-risk.csv", index=False)


if __name__ == "__main__":
    main()
