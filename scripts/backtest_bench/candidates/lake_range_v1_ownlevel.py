"""lake-range-v1 with its own level at each lake bathing water it has none for (docs/BENCH-READ-LAKE-RANGE-COVERAGE-2026-11.md).

Every frozen parameter of lake-range-v1 stays (`data/processed/ecoli_lake_range.json`, sha256 5566b12e...: beta,
tau, the lake noise level, the nodes and the prior). A lake bathing water the file has no level for gets one from the
training rows the bench passes to `fit`: its node weights are the prior's plus the summed censored-normal
log-likelihood of its own samples, normalised, the rule `concentration_study.CensoredRI._site_post` used to export the
11 levels the file holds. A lake with no training rows keeps the average lake's. Ranks, chances and the 8-in-10 range
then come from `lake_range_v1_range.py` unchanged.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import norm

_spec = importlib.util.spec_from_file_location("lake_range_v1_range", Path(__file__).with_name("lake_range_v1_range.py"))
rng = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rng)

LAB_LOW, LAB_HIGH = np.log10(10.0), np.log10(10000.0)


def own_weights(m: dict, rows: pd.DataFrame) -> np.ndarray:
    """Normalised log node weights for one lake from its rows (log10 E. coli, censored at the lab's limits)."""
    cols = m["cols"]
    Z = np.column_stack([np.ones(len(rows))] + [(rows[c].to_numpy(dtype=float) - m["mean"][c]) / m["sd"][c] for c in cols])
    mu = (Z @ np.asarray(m["beta"]))[:, None] + np.sqrt(2.0) * m["tau"] * np.asarray(m["nodes"])[None, :]
    s = m["sigma_lake"]
    q = rows["ecoli_qual"].astype(str).to_numpy()[:, None]
    y = np.log10(rows["ecoli"].to_numpy(dtype=float))[:, None]
    ll = np.where(q == "<", norm.logcdf((LAB_LOW - mu) / s),
                  np.where(q == ">", norm.logsf((LAB_HIGH - mu) / s), norm.logpdf((y - mu) / s) - np.log(s)))
    w = np.asarray(m["log_prior"]) + ll.sum(0)
    return w - logsumexp(w)


def fit(rows: pd.DataFrame) -> dict:
    model = rng.fit(rows)
    m = copy.deepcopy(model["m"])
    lake = rows[(rows["kind"] == "lake") & ~rows["bw_id"].isin(m["sites"])]
    for bw, g in lake.groupby("bw_id"):
        m["sites"][bw] = {"name": str(g["name"].iloc[0]), "log_weights": own_weights(m, g).tolist(), "from": "bench fit rows"}
    return {**model, "m": m}


def predict(model: dict, rows: pd.DataFrame) -> dict[str, np.ndarray]:
    return rng.predict(model, rows)
