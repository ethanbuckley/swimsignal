"""lake-range-v1's 8-in-10 range as the bench's candidate (docs/BENCH-READ-LAKE-RANGE-COVERAGE-2026-11.md): bench
read 1's candidate (`lake_range_v1.py`, unchanged) plus, at lake rows, the range the page shows: the 10th and 90th
centiles of the model's predictive distribution of log10 E. coli (`lake_range._quantiles`, the same mixture over the
intercept's nodes with the lake noise level), and its chance of a count at or under 10 and 10,000, the lab's limits.
A bathing water with its own level uses it; any other gets the average lake's. At river rows the range is a
placeholder (production gives none there), so river coverage is not a comparison.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logsumexp, ndtr

from dipcast import lake_range

_spec = importlib.util.spec_from_file_location("lake_range_v1", Path(__file__).with_name("lake_range_v1.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)


def fit(rows: pd.DataFrame) -> dict:
    return base.fit(rows)


def _range(m: dict, X: pd.DataFrame, bw: str | None) -> dict[str, np.ndarray]:
    cols = m["cols"]
    q = lake_range._quantiles(m, X[cols], bw, qs=(0.1, 0.9))
    Z = np.column_stack([np.ones(len(X))] + [(X[c].to_numpy(dtype=float) - m["mean"][c]) / m["sd"][c] for c in cols])
    mu = Z @ np.asarray(m["beta"])
    logw = np.asarray(m["sites"][bw]["log_weights"] if bw is not None else m["log_prior"])
    w = np.exp(logw - logsumexp(logw))
    u = np.sqrt(2.0) * m["tau"] * np.asarray(m["nodes"])
    s = m["sigma_lake"]
    cdf = {c: (w[None, :] * ndtr((np.log10(c) - mu[:, None] - u[None, :]) / s)).sum(1) for c in (10, 10000)}
    return {"q10": np.log10(q[0.1]), "q90": np.log10(q[0.9]), "p_le10": cdf[10], "p_le10000": cdf[10000]}


def predict(model: dict, rows: pd.DataFrame) -> dict[str, np.ndarray]:
    out = base.predict(model, rows)
    m = model["m"]
    extra = {"q10": np.zeros(len(rows)), "q90": np.full(len(rows), 4.0), "p_le10": np.full(len(rows), 0.5),
             "p_le10000": np.ones(len(rows))}
    lake = (rows["kind"] == "lake").to_numpy()
    for bw in rows.loc[lake, "bw_id"].unique():
        i = np.flatnonzero(lake & (rows["bw_id"] == bw).to_numpy())
        f = _range(m, rows.iloc[i], bw if bw in m["sites"] else None)
        for k in extra:
            extra[k][i] = f[k]
    return {**out, **extra}
