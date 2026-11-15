"""Fit and freeze river-range-v0, the candidate of docs/RIVER-UNSEEN-PROTOCOL-2026-11.md, before any archive sample
is fetched.

    python scripts/river_unseen/freeze_candidate.py <bench seen.parquet> docs/river-unseen/river_range_v0.json

A log10 E. coli model on the backtest bench's seen river rows (2023-26, bathing waters): ordinary least squares on
rain in the 48 and 24 hours before the sample, upstream exposure and season. No site level, so it can be applied at
a point it has no samples for. The spread is the residual standard deviation. Reads only the seen rows; the bench's
held-out file is never opened."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

FEATURES = ["lrain48", "lrain24", "logit_risk", "doy_sin", "doy_cos"]


def fit(rows: pd.DataFrame) -> dict:
    x = np.c_[np.ones(len(rows)), rows[FEATURES].to_numpy(float)]
    y = rows["log_ecoli"].to_numpy(float)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    sd = float(np.std(y - x @ beta, ddof=len(FEATURES) + 1))
    return {"intercept": float(beta[0]), "coef": {f: float(b) for f, b in zip(FEATURES, beta[1:])}, "sd_log10": sd}


def predict(model: dict, rows: pd.DataFrame) -> pd.DataFrame:
    """The likely reading (median, as log10) and the 8-in-10 range's ends for rows holding FEATURES."""
    mu = model["intercept"] + sum(model["coef"][f] * rows[f].to_numpy(float) for f in FEATURES)
    z = norm.ppf(0.9) * model["sd_log10"]
    return pd.DataFrame({"mu_log10": mu, "low_log10": mu - z, "high_log10": mu + z}, index=rows.index)


def main(seen: Path, out: Path) -> None:
    rows = pd.read_parquet(seen)
    assert set(rows["part"]) == {"seen"}, "seen rows only"
    rows = rows[rows["kind"] == "river"]
    assert rows[FEATURES + ["log_ecoli"]].notna().all().all()
    model = fit(rows)
    doc = {"name": "river-range-v0", "target": "log10 E. coli per 100 ml; a result below the lab limit kept at the limit",
           "features": {"lrain48": "ln(1 + mm of rain in the 48 h before the sample)",
                        "lrain24": "ln(1 + mm of rain in the 24 h before the sample)",
                        "logit_risk": "logit of the lead-0 upstream exposure, as the bench builds it",
                        "doy_sin": "sin of the day of year", "doy_cos": "cos of the day of year"},
           **model, "range": "likely reading 10^mu; 8 in 10 between 10^(mu - z*sd) and 10^(mu + z*sd), z = 1.2816",
           "fitted_on": {"rows": int(len(rows)), "sites": int(rows["bw_id"].nunique()),
                         "seasons": sorted(int(s) for s in rows["season"].unique()),
                         "file": "swimsignal-private/bench/ecoli-v1/seen.parquet",
                         "sha256": hashlib.sha256(seen.read_bytes()).hexdigest(),
                         "row_version": str(rows["row_version"].iloc[0])},
           "frozen_at": datetime.now(UTC).isoformat(timespec="seconds")}
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(json.dumps(model, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
