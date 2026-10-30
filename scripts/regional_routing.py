"""The regional routing rule v1 for the nine-company v2 spill model (docs/REGIONAL-ROUTING-2026-11.md), frozen:

    the eight companies other than United Utilities  -> v2 arm (b), offsets at recency 1 (SHA-256 9e0fc54a...)
    United Utilities, any other company, no company   -> production (data/processed/spill_model.pkl)

Both models take the same 15 inputs (features.ALL_FEATURES), so one frame serves both. A site the v2 model has no
offset for gets its pooled layer (SpillModel.predict's own rule). This module only routes and predicts; it writes
nothing and is not imported by the forecast. The shadow that will log its predictions is a separate milestone.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

RULE = "regional-v1"
V2_SHA256 = "9e0fc54a9356e4cea528606422dc569691453fc3ab98ea31986f19437ba501f2"
EIGHT = ("Anglian Water", "Northumbrian Water", "Severn Trent Water", "South West Water", "Southern Water",
         "Thames Water", "Wessex Water", "Yorkshire Water")
FALLBACK = "production"
V2 = "v2_offsets"


def route(company: pd.Series) -> np.ndarray:
    """The model each row goes to: V2 for the eight companies, FALLBACK for United Utilities and everything else."""
    return np.where(company.isin(EIGHT).to_numpy(), V2, FALLBACK)


def check_v2(path: Path) -> None:
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != V2_SHA256:
        raise SystemExit(f"{path} is {got[:16]}, not the frozen v2 model {V2_SHA256[:16]}")


def predict(df: pd.DataFrame, v2, production) -> tuple[np.ndarray, np.ndarray]:
    """(probability, route) per row. `df` needs `company`, `site_id` and the models' features."""
    r = route(df["company"])
    p = np.empty(len(df))
    m = r == V2
    if m.any():
        p[m] = v2.predict(df[m])
    if (~m).any():
        p[~m] = production.predict(df[~m])
    return p, r
