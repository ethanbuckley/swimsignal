"""lake-range-v1 as the bench's candidate (docs/BENCH-READ-LAKE-RANGE-2026-11.md): the frozen lake model the site
shows at every lake spot (src/dipcast/lake_range.py, data/processed/ecoli_lake_range.json, sha256 5566b12e...).

Nothing is fitted: `fit` loads the frozen file and checks its hash. At a lake row, `predict` gives the model's
predictive distribution of log10 E. coli, as `lake_range._quantiles` builds it (a mixture over the intercept's
nodes, the lake noise level): its median as `rank`, and its chance over 900 and over 500. A lake bathing water with
its own level in the model uses it; any other gets the average lake's (the "average lake" basis the page shows).
The bathing water is matched by its id, where the live forecast matches a spot by position.

At a river row it gives production's figure (the deployed river model with soil moisture where known, else the base
model), so every difference on river rows is zero: lake-range-v1 is shown at lakes only.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logsumexp, ndtr

from dipcast import lake_range
from dipcast.model.ecoli import FEATURES, SM_MODEL_PATH, EcoliModel

PROCESSED = Path(__file__).resolve().parents[3] / "data" / "processed"


def fit(rows: pd.DataFrame) -> dict:
    import hashlib
    p = PROCESSED / "ecoli_lake_range.json"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == lake_range.SHA256, "not the frozen lake-range-v1 file"
    import json
    return {"m": json.loads(p.read_text()), "base": EcoliModel.from_json(PROCESSED / "ecoli_model.json"),
            "sm": EcoliModel.from_json(PROCESSED / SM_MODEL_PATH.name)}


def _lake(m: dict, X: pd.DataFrame, bw: str | None) -> dict[str, np.ndarray]:
    cols = m["cols"]
    Z = np.column_stack([np.ones(len(X))] + [(X[c].to_numpy(dtype=float) - m["mean"][c]) / m["sd"][c] for c in cols])
    mu = Z @ np.asarray(m["beta"])
    logw = np.asarray(m["sites"][bw]["log_weights"] if bw is not None else m["log_prior"])
    w = np.exp(logw - logsumexp(logw))
    u = np.sqrt(2.0) * m["tau"] * np.asarray(m["nodes"])
    s = m["sigma_lake"]
    over = {c: (w[None, :] * (1 - ndtr((np.log10(c) - mu[:, None] - u[None, :]) / s))).sum(1) for c in (900, 500)}
    med = lake_range._quantiles(m, X[cols], bw, qs=(0.5,))[0.5]
    return {"p900": over[900], "p500": over[500], "rank": np.log10(med)}


def predict(model: dict, rows: pd.DataFrame) -> dict[str, np.ndarray]:
    m = model["m"]
    out = {k: np.full(len(rows), np.nan) for k in ("p900", "p500", "rank")}
    lake = (rows["kind"] == "lake").to_numpy()
    for bw in rows.loc[lake, "bw_id"].unique():
        i = np.flatnonzero(lake & (rows["bw_id"] == bw).to_numpy())
        f = _lake(m, rows.iloc[i], bw if bw in m["sites"] else None)
        for k in out:
            out[k][i] = f[k]
    riv = ~lake
    if riv.any():
        X = rows.loc[riv, FEATURES]
        p = model["base"].predict(X)
        has = rows.loc[riv, "sm"].notna().to_numpy()
        if has.any():
            lo, hi = model["sm"].meta["sm_range"]
            Xs = X[has].copy()
            Xs["sm"] = np.clip(rows.loc[riv, "sm"].to_numpy(dtype=float)[has], lo, hi)
            p[has] = model["sm"].predict(Xs)
        out["p900"][riv] = p
        out["p500"][riv] = p   # no river figure over 500 exists; the over-500 Brier on rivers is not a comparison
        out["rank"][riv] = p
    return out
