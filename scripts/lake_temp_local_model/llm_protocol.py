"""The rules of docs/LAKE-TEMP-LOCAL-MODEL-2026-11.md, as plain functions. No network, no files.

Lake classes from depth, merging connected basins, the three candidate forms (K0 pooled, K1 by class, K2 by class with
month offsets), the choice of tau and form inside training rows, and the two-way cluster bootstrap. Tests:
tests/test_lake_temp_local_model.py, synthetic data only.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd

TEST_YEARS = tuple(range(2000, 2012))
DEV_YEARS = tuple(range(2012, 2026))
TAUS = (5, 10, 15, 20, 30, 45, 60, 90)
CLASSES = ("deep", "mid", "shallow", "no depth")
DEEP_M, SHALLOW_M = 10.0, 3.0
FORMS = ("K0", "K1", "K2")
FORM_MARGIN = 0.02
MIN_CLASS_WATERS, MIN_CLASS_ROWS = 5, 100
WFD_JOIN_M = 50.0
OTHER_JOIN_M = 500.0
N_FOLDS = 5
FOLD_SALT = "lake-local-v1:"
N_BOOT, SEED = 2000, 20261113
GATE_WATERS, GATE_ROWS = 30, 300
RMSE_MAX, P90_MAX = 1.5, 2.5
GROUP_MIN_WATERS, GROUP_FEW_WATERS = 10, 20
HARM_MARGIN = -0.1
LARGE_KM2 = 1.0


# ================================================================== lake facts
def lake_class(depth_m) -> np.ndarray:
    d = np.asarray(depth_m, float)
    return np.select([d >= DEEP_M, d >= SHALLOW_M, d < SHALLOW_M], ["deep", "mid", "shallow"], "no depth")


def fold_of(water: str, k: int = N_FOLDS) -> int:
    return int(hashlib.sha256((FOLD_SALT + water).encode()).hexdigest(), 16) % k


def union_find(items, pairs) -> dict:
    """{item: representative} so that every pair ends up with one representative (the smallest item, as a string)."""
    parent = {i: i for i in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            lo, hi = sorted((ra, rb), key=str)
            parent[hi] = lo
    return {i: find(i) for i in items}


def merge_groups(groups: pd.Series, how: pd.Series, wfd_pairs, near_wfd: dict) -> pd.Series:
    """The merged water of each row.

    groups: each row's #419 group ("lake:GB..." for a WFD polygon). how: "WFD polygon", "OS lake link" or "own water".
    wfd_pairs: pairs of WFD group ids whose outlines are within WFD_JOIN_M. near_wfd: {non-WFD group id: WFD group id}
    for groups with a point within OTHER_JOIN_M of a WFD outline (the nearest). Returns the merged id per row."""
    wfd = sorted(set(groups[how.eq("WFD polygon")]))
    rep = union_find(wfd, [(a, b) for a, b in wfd_pairs if a in set(wfd) and b in set(wfd)])

    def one(g):
        if g in rep:
            return rep[g]
        if g in near_wfd and near_wfd[g] in rep:
            return rep[near_wfd[g]]
        return g
    return groups.map(one)


# ================================================================== forms
def design(df: pd.DataFrame, tau: int, form: str) -> np.ndarray:
    """Columns of one class's (or the pooled) least-squares design for a form."""
    cols = [np.ones(len(df)), df[f"e{tau}"].to_numpy(float)]
    if form == "K2":
        m = pd.to_datetime(df["date"]).dt.month.to_numpy()
        for month in (6, 7, 8, 9):            # May is the intercept
            cols.append((m == month).astype(float))
    else:
        cols += [df["doy_sin"].to_numpy(float), df["doy_cos"].to_numpy(float)]
    cols.append(df["elevation"].to_numpy(float) / 100.0)
    return np.column_stack(cols)


def fit_ls(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def _rmse(e) -> float:
    e = np.asarray(e, float)
    return float(math.sqrt(np.mean(e ** 2))) if len(e) else float("inf")


def choose_tau(scores: dict) -> int:
    """Lowest score; a tie goes to the shorter tau."""
    return min(scores, key=lambda t: (scores[t], t))


def class_ok(train: pd.DataFrame, cls: str) -> bool:
    g = train[train["cls"].eq(cls)]
    return g["water"].nunique() >= MIN_CLASS_WATERS and len(g) >= MIN_CLASS_ROWS


def fit_form(train: pd.DataFrame, form: str, taus: dict) -> dict:
    """Coefficients for a form. taus: {"pooled": tau} for K0, {class: tau} for K1/K2. A class too small to fit on its
    own (class_ok) uses the pooled K0 fit with taus["pooled"]."""
    y = train["temp"].to_numpy(float)
    pooled = fit_ls(design(train, taus["pooled"], "K0"), y)
    out = {"form": form, "taus": dict(taus), "pooled": pooled.tolist(), "classes": {}}
    if form == "K0":
        return out
    for c in CLASSES:
        if c in taus and class_ok(train, c):
            g = train[train["cls"].eq(c)]
            out["classes"][c] = fit_ls(design(g, taus[c], form), g["temp"].to_numpy(float)).tolist()
    return out


def predict_form(m: dict, df: pd.DataFrame) -> np.ndarray:
    out = design(df, m["taus"]["pooled"], "K0") @ np.asarray(m["pooled"])
    for c, beta in m["classes"].items():
        sel = df["cls"].eq(c).to_numpy()
        if sel.any():
            out[sel] = design(df[sel], m["taus"][c], m["form"]) @ np.asarray(beta)
    return out


def inner_folds(train: pd.DataFrame):
    for j in sorted(train["fold"].unique()):
        yield train[train["fold"].ne(j)], train[train["fold"].eq(j)]


def inner_tau_scores(train: pd.DataFrame, form: str, rows_of=None) -> dict:
    """Pooled inner RMSE for each tau of one form fitted on `rows_of` rows only (a class) or on all rows."""
    sub = train if rows_of is None else train[train["cls"].eq(rows_of)]
    scores = {}
    for t in TAUS:
        err = []
        for fit, hold in inner_folds(sub):
            if len(fit) < 10 or not len(hold):
                continue
            beta = fit_ls(design(fit, t, form), fit["temp"].to_numpy(float))
            err.append(hold["temp"].to_numpy(float) - design(hold, t, form) @ beta)
        scores[t] = _rmse(np.concatenate(err)) if err else float("inf")
    return scores


def inner_form_score(train: pd.DataFrame, form: str, taus: dict) -> float:
    err = []
    for fit, hold in inner_folds(train):
        m = fit_form(fit, form, taus)
        err.append(hold["temp"].to_numpy(float) - predict_form(m, hold))
    return _rmse(np.concatenate(err))


def choose_form(scores: dict) -> str:
    """A more complex form only if it beats every simpler one by more than FORM_MARGIN."""
    best = FORMS[0]
    for f in FORMS[1:]:
        if all(scores[f] < scores[s] - FORM_MARGIN for s in FORMS[:FORMS.index(f)]):
            best = f
    return best


def fit_candidate(train: pd.DataFrame) -> dict:
    """Everything one outer fold needs, from its training rows only (columns: water, fold, cls, date, temp, e<tau>,
    doy_sin, doy_cos, elevation)."""
    train = train.reset_index(drop=True)
    pooled_scores = inner_tau_scores(train, "K0")
    taus = {"K0": {"pooled": choose_tau(pooled_scores)}}
    tau_scores = {"K0": {"pooled": pooled_scores}}
    for form in ("K1", "K2"):
        taus[form] = {"pooled": taus["K0"]["pooled"]}
        tau_scores[form] = {}
        for c in CLASSES:
            if class_ok(train, c):
                s = inner_tau_scores(train, form, rows_of=c)
                tau_scores[form][c] = s
                taus[form][c] = choose_tau(s)
    form_scores = {f: inner_form_score(train, f, taus[f]) for f in FORMS}
    form = choose_form(form_scores)
    m = fit_form(train, form, taus[form])
    return m | {"form_scores": form_scores, "tau_scores": tau_scores, "train_rows": int(len(train)),
                "train_waters": int(train["water"].nunique())}


# ================================================================== scores
def summary(err) -> dict:
    e = np.asarray(err, float)
    if not len(e):
        return {"n": 0}
    return {"n": int(len(e)), "rmse": _rmse(e), "bias": float(e.mean()), "mae": float(np.abs(e).mean()),
            "p90_abs": float(np.percentile(np.abs(e), 90))}


def boot(waters, years, err_cand, err_bases: dict, n_boot: int = N_BOOT, seed: int = SEED,
         two_way: bool = True) -> dict:
    """95% intervals for the candidate's RMSE and each gain (base RMSE minus candidate RMSE). Two-way: waters and years
    drawn with replacement independently, a row weighted by its water's count times its year's. Water-only otherwise."""
    wc, wu = pd.factorize(pd.Series(np.asarray(waters)).astype(str))
    yc, yu = pd.factorize(pd.Series(np.asarray(years)).astype(str))
    W, Y = len(wu), len(yu)
    ec = np.asarray(err_cand, float) ** 2
    eb = {k: np.asarray(v, float) ** 2 for k, v in err_bases.items()}
    # sums per (water, year) cell
    cell = wc * Y + yc
    n_cell = np.bincount(cell, minlength=W * Y).reshape(W, Y)
    s_c = np.bincount(cell, weights=ec, minlength=W * Y).reshape(W, Y)
    s_b = {k: np.bincount(cell, weights=v, minlength=W * Y).reshape(W, Y) for k, v in eb.items()}
    rng = np.random.default_rng(seed)
    rc_all, gains = [], {k: [] for k in eb}
    for _ in range(n_boot):
        w_cnt = np.bincount(rng.integers(0, W, W), minlength=W).astype(float)
        y_cnt = np.bincount(rng.integers(0, Y, Y), minlength=Y).astype(float) if two_way else np.ones(Y)
        wt = np.outer(w_cnt, y_cnt)
        n = (wt * n_cell).sum()
        if n == 0:
            continue
        rc = math.sqrt((wt * s_c).sum() / n)
        rc_all.append(rc)
        for k, s in s_b.items():
            gains[k].append(math.sqrt((wt * s).sum() / n) - rc)
    out = {"cand_rmse": {"value": _rmse(np.sqrt(ec)), "lo": float(np.percentile(rc_all, 2.5)),
                         "hi": float(np.percentile(rc_all, 97.5))}}
    for k, v in eb.items():
        out[k] = {"gain": _rmse(np.sqrt(v)) - _rmse(np.sqrt(ec)),
                  "lo": float(np.percentile(gains[k], 2.5)), "hi": float(np.percentile(gains[k], 97.5))}
    return out


def verdict(n_waters: int, n_rows: int, rmse: float, p90: float, gains: dict) -> dict:
    """gains: {"live", "live_refit", "air7", "m419"} -> {"gain", "lo", "hi"} (two-way)."""
    c = {"gate": n_waters >= GATE_WATERS and n_rows >= GATE_ROWS,
         "rmse": rmse <= RMSE_MAX,
         "p90": p90 <= P90_MAX,
         "beats_live": gains["live"]["lo"] > 0,
         "beats_live_refit": gains["live_refit"]["lo"] > 0,
         "beats_air7": gains["air7"]["lo"] > 0,
         "beats_m419": gains["m419"]["lo"] > 0}
    meets = c["gate"] and c["rmse"] and c["p90"] and c["beats_air7"] and c["beats_m419"]
    better = c["gate"] and c["beats_live"] and c["beats_live_refit"]
    if not c["gate"]:
        label = "too few to judge"
    else:
        label = ("meets the limit" if meets else "misses the limit") + "; " + \
                ("better than the live route" if better else "not shown better than the live route")
    return {"conditions": c, "meets_limit": meets, "better_than_live": better, "label": label}


def group_answer(n_waters: int, gains: dict) -> str:
    """For a class or size group: better / not harmed / neither, against both live versions."""
    if n_waters < GROUP_MIN_WATERS:
        return "too few"
    lo = min(gains["live"]["lo"], gains["live_refit"]["lo"])
    tag = " (few waters)" if n_waters < GROUP_FEW_WATERS else ""
    if lo > 0:
        return "better" + tag
    if lo > HARM_MARGIN:
        return "not harmed" + tag
    return "harm not ruled out" + tag
