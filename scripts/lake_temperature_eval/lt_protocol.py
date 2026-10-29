"""The rules of docs/LAKE-TEMPERATURE-TEST-2026-10.md, as plain functions. No network, no files.

The first test's rules (scripts/water_temperature_model_eval/wt_protocol.py) are reused for rows, water bodies, folds,
the day-of-year baseline and the group bootstrap. What is new is here: the longer air windows, the choice of window
inside training data, the lake-only candidate, the third baseline and the six-condition verdict. Tests:
tests/test_lake_temperature_eval.py, synthetic data only.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "water_temperature_model_eval"))
import wt_protocol as wp  # noqa: E402

# ---- arms ---------------------------------------------------------------------------------------------------------
ARMS = {
    "primary": {"train": tuple(range(2000, 2026)), "test": (2026,), "decides": True},
    "secondary": {"train": tuple(range(2000, 2023)), "test": (2023, 2024, 2025), "decides": False},
}
OM_TEST_YEARS = (2023, 2024, 2025, 2026)

# ---- the bridge, copied from the first test's features_info.json (2018 air only, no water temperature) ------------
BRIDGE_C = 0.5012729716522162
BRIDGE_D = 0.9791684691913549

# ---- windows ------------------------------------------------------------------------------------------------------
TAUS = (5, 10, 15, 20, 30, 45, 60, 90)
ROLLING = {"a1": 1, "a7": 7, "a14": 14, "a30": 30}
E_WINDOWS = tuple(f"e{t}" for t in TAUS)
THIRD_CHOICES = ("a14", "a30", "a_apr", *E_WINDOWS)      # in this order; a tie goes to the earlier one
AIR_COLS = (*ROLLING, "a_apr", *E_WINDOWS)
SEASON_START = "04-01"
SEASON_END = "09-30"

# ---- the verdict --------------------------------------------------------------------------------------------------
GATE_WATERS, GATE_ROWS = 30, 300
RMSE_MAX = 1.5
P90_MAX = 2.5
N_BOOT, SEED = 2000, 20261027

# ---- the candidate ------------------------------------------------------------------------------------------------
GBM_PARAMS = dict(wp.GBM_PARAMS)
LAKE_FACTS = ("doy_sin", "doy_cos", "log_lake_area", "log_depth", "elevation")
LARGE_KM2, SMALL_KM2 = 1.0, 0.1


# ================================================================== air
def alpha_of(tau: float) -> float:
    return 1.0 - math.exp(-1.0 / float(tau))


def air_windows(daily: pd.Series, year: int, dates: Iterable) -> pd.DataFrame:
    """Every air window of the statement for each date, from one cell's daily means (index: dates) in one year.

    The series is cut to 1 April - 30 September of `year`. A date gets values only if every day from 1 April to it is
    present; otherwise every column is NaN. a_apr is the mean from 1 April to the date. e<tau> is the exponentially
    weighted mean from 1 April: weight (1 - alpha)^i for the day i days back, alpha = 1 - exp(-1/tau), divided by the
    sum of the weights used (pandas ewm with adjust=True)."""
    idx = pd.date_range(f"{year}-{SEASON_START}", f"{year}-{SEASON_END}", freq="D")
    s = daily.copy()
    s.index = pd.to_datetime(s.index).normalize()
    s = s[~s.index.duplicated()].reindex(idx)
    complete = s.isna().cumsum().eq(0)
    cols = {}
    for name, n in ROLLING.items():
        cols[name] = s.rolling(n, min_periods=n).mean()
    cols["a_apr"] = s.expanding(min_periods=1).mean()
    for t in TAUS:
        cols[f"e{t}"] = s.ewm(alpha=alpha_of(t), adjust=True).mean()
    full = pd.DataFrame(cols, index=idx)
    full.loc[~complete.to_numpy()] = np.nan
    want = pd.to_datetime(list(dates)).normalize()
    out = full.reindex(want)
    return out[list(AIR_COLS)].reset_index(drop=True)


def bridge(x):
    return BRIDGE_C + BRIDGE_D * np.asarray(x, float)


# ================================================================== simple fits
def fit_line(x, y) -> tuple[float, float]:
    b, a = np.polyfit(np.asarray(x, float), np.asarray(y, float), 1)
    return float(a), float(b)


def inner_scores(train: pd.DataFrame, windows: Iterable[str], fold_col: str = "fold") -> dict[str, float]:
    """For each window, the pooled RMSE of a straight line T = a + b x w when each training fold in turn is held out
    and the line is fitted on the others. Uses only `train` (one outer fold's training rows)."""
    folds = sorted(train[fold_col].unique())
    out = {}
    for w in windows:
        sse = 0.0
        n = 0
        for j in folds:
            fit = train[train[fold_col] != j]
            hold = train[train[fold_col] == j]
            if len(fit) < 2 or not len(hold):
                continue
            a, b = fit_line(fit[w], fit["temp"])
            e = hold["temp"].to_numpy(float) - (a + b * hold[w].to_numpy(float))
            sse += float((e ** 2).sum())
            n += len(e)
        out[w] = math.sqrt(sse / n) if n else float("inf")
    return out


def choose(scores: dict[str, float], order: Iterable[str]) -> str:
    """The window with the lowest score; a tie goes to the earlier one in `order`."""
    order = list(order)
    return min(order, key=lambda w: (scores[w], order.index(w)))


# ================================================================== the candidate
def gbm_inputs(e_window: str) -> list[str]:
    return ["a1", "a7", "a14", "a30", "a_apr", e_window, *LAKE_FACTS]


def fit_fold(train: pd.DataFrame) -> dict:
    """Everything one outer fold needs, from its lake training rows only: the windows chosen, the three baselines and
    the candidate (stage 1 = the third baseline; stage 2 = the boosted residual)."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    train = train.reset_index(drop=True)
    sc = inner_scores(train, THIRD_CHOICES)
    w3 = choose(sc, THIRD_CHOICES)
    we = choose({w: sc[w] for w in E_WINDOWS}, E_WINDOWS)
    a3, b3 = fit_line(train[w3], train["temp"])
    a7, b7 = fit_line(train["a7"], train["temp"])
    doy = wp.fit_doy_baseline(train["doy"], train["temp"])
    resid = train["temp"].to_numpy(float) - (a3 + b3 * train[w3].to_numpy(float))
    feats = [c for c in gbm_inputs(we) if np.isfinite(train[c].to_numpy(float)).any()]
    gbm = HistGradientBoostingRegressor(**GBM_PARAMS)
    gbm.fit(train[feats].to_numpy(float), resid)
    return {"inner_scores": sc, "third_window": w3, "e_window": we, "third": (a3, b3), "air7": (a7, b7), "doy": doy,
            "gbm": gbm, "features": feats, "train_rows": int(len(train)),
            "train_waters": int(train["group"].nunique())}


def predict_fold(m: dict, df: pd.DataFrame) -> pd.DataFrame:
    a3, b3 = m["third"]
    a7, b7 = m["air7"]
    s1 = a3 + b3 * df[m["third_window"]].to_numpy(float)
    s2 = m["gbm"].predict(df[m["features"]].to_numpy(float)) if len(df) else np.zeros(0)
    return df.assign(pred_cand=s1 + s2, pred_third=s1, pred_air7=a7 + b7 * df["a7"].to_numpy(float),
                     pred_doy=wp.predict_doy(m["doy"], df["doy"]) if len(df) else np.zeros(0))


# ================================================================== groups for reporting
def is_reservoir(*names) -> bool:
    return any(isinstance(n, str) and "reservoir" in n.lower() for n in names)


def size_band(area_km2) -> str:
    if area_km2 is None or not np.isfinite(area_km2):
        return "not matched to a WFD polygon"
    if area_km2 >= LARGE_KM2:
        return "WFD 1 km2 and over"
    if area_km2 < SMALL_KM2:
        return "WFD under 0.1 km2"
    return "WFD 0.1 to 1 km2"


# ================================================================== verdict
def p90(err) -> float:
    e = np.abs(np.asarray(err, float))
    return float(np.percentile(e, 90)) if len(e) else float("nan")


def verdict(n_waters: int, n_rows: int, rmse_cand: float, p90_cand: float, gains: dict) -> dict:
    """The six conditions. gains: {"doy", "air7", "third"} -> {"gain", "lo", "hi"} from wp.boot_gains."""
    conds = {
        "gate": n_waters >= GATE_WATERS and n_rows >= GATE_ROWS,
        "beats_doy": gains["doy"]["lo"] > 0,
        "beats_air7": gains["air7"]["lo"] > 0,
        "beats_third": gains["third"]["lo"] > 0,
        "rmse": rmse_cand <= RMSE_MAX,
        "p90": p90_cand <= P90_MAX,
    }
    if not conds["gate"]:
        return {"label": "too few to judge", "conditions": conds}
    return {"label": "pass" if all(conds.values()) else "fail", "conditions": conds}
