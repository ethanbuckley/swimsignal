"""Bench self-check candidate: production's E. coli form refitted on the training rows (ecoli.FEATURES, logistic,
C = 1). Its scores must equal the bench's production_refit reference exactly; a difference means the bench passes
the candidate different rows from the ones its references see."""
from __future__ import annotations

import numpy as np
import pandas as pd

from dipcast.model.ecoli import FEATURES, fit as _fit


def fit(rows: pd.DataFrame):
    return _fit(rows, rows["over"].to_numpy(), FEATURES)


def predict(model, rows: pd.DataFrame) -> np.ndarray:
    return model.predict(rows[FEATURES])
