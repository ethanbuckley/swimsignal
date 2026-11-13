"""Score the coastal baselines of docs/COASTAL-BASELINES-2026-11.md (sections 4 to 6) from build.py's table.

    uv run python scripts/coastal_baselines/score.py <features.parquet> <out dir>

Writes <out dir>/scores.json (every figure), scores.md (the tables the record quotes) and predictions_<target>.parquet
(each held-out prediction, for audit). Reads nothing else and makes no request. Development evidence on seen data.

Models, per fold, all fitted on the history set H (rows not in a test year and not at a test site):

  B0        the pooled rate in H
  B1        the site's rate in H, shrunk towards B0 (prior strength by the method of moments)
  B2        the pooled rate of the calendar month in H
  R         logistic regression on logit(site rate) and month indicators
  <input>   logistic regression on the input alone: last, rain, spills; for prf the rate in H under each level
  R|<input> R fitted on the same rows as R+<input> (rows of H that have the input)
  R+<input> logistic regression on R's features and the input's
  B7a       R + last + rain;  B7b  R + last + rain + spills (rows with both, 2025 only)

The deciding comparison is R+<input> against R|<input>: the same rows to fit and to test, so the difference is the
input's and not a recalibration to the years the input covers.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

SEED = 20261113
RESAMPLES = 2000
MONTHS = (5, 6, 7, 8, 9)
FORWARD_YEARS = (2025, 2026)
TARGETS = {"over_500": "exceeds_500", "over_250": "exceeds_250"}
INPUTS = ("last", "rain", "spills", "prf")
CLIP = (0.001, 0.999)


def logit(p):
    return np.log(p / (1 - p))


def fit_predict(X: np.ndarray, y: np.ndarray, train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray | None, list | None]:
    """Logistic regression with in effect no penalty, fitted on `train` rows, predicted on `test` rows."""
    if train.sum() == 0 or test.sum() == 0 or y[train].min() == y[train].max():
        return None, None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = LogisticRegression(C=1e6, max_iter=5000).fit(X[train], y[train])
    return m.predict_proba(X[test])[:, 1], [float(m.intercept_[0]), *map(float, m.coef_[0])]


class Fold:
    """One fold's history set and everything fitted on it."""

    def __init__(self, d: dict, hist: np.ndarray, test: np.ndarray):
        self.d, self.hist, self.test = d, hist, test
        y, s, yr = d["y"], d["site"], d["year_code"]
        k_sy = np.zeros((d["n_sites"], d["n_years"]))
        n_sy = np.zeros_like(k_sy)
        np.add.at(k_sy, (s[hist], yr[hist]), y[hist])
        np.add.at(n_sy, (s[hist], yr[hist]), 1)
        k_s, n_s = k_sy.sum(1), n_sy.sum(1)
        self.p0 = p0 = k_s.sum() / n_s.sum()
        big = n_s >= 10
        v = (k_s[big] / n_s[big]).var(ddof=1) - p0 * (1 - p0) * np.mean(1 / n_s[big])
        self.m = m = float(np.clip(p0 * (1 - p0) / v - 1, 1, 500)) if v > 0 else 500.0
        # A row's own year is left out, so a history row never sees its own outcome. A test row's year or site is not
        # in H, so nothing is subtracted for it; a held-out site gets p0.
        self.site_rate = (k_s[s] - k_sy[s, yr] + m * p0) / (n_s[s] - n_sy[s, yr] + m)
        self.month_rate = np.full(len(y), p0)
        for mo in MONTHS:
            rows = hist & (d["month"] == mo)
            if rows.sum() >= 50:
                self.month_rate[d["month"] == mo] = y[rows].mean()
        self.Xr = np.c_[logit(self.site_rate), *[(d["month"] == mo).astype(float) for mo in MONTHS[1:]]]

    def predictions(self) -> tuple[dict[str, np.ndarray], dict]:
        """Each model's prediction for this fold's test rows: NaN where the model's input is missing."""
        d, hist, test, y = self.d, self.hist, self.test, self.d["y"]
        n = int(test.sum())
        out = {"B0": np.full(n, self.p0), "B1": self.site_rate[test], "B2": self.month_rate[test]}
        coefs = {"p0": float(self.p0), "m": self.m}

        def run(name: str, X: np.ndarray, has: np.ndarray) -> None:
            p, c = fit_predict(X, y, hist & has, test & has)
            col = np.full(n, np.nan)
            if p is not None:
                col[has[test]] = p
                coefs[name] = c
            out[name] = col

        everything = np.ones(len(y), bool)
        run("R", self.Xr, everything)
        for name in ("last", "rain", "spills"):
            X, has = d[f"X_{name}"], d[f"has_{name}"]
            run(name, X, has)
            run(f"R|{name}", self.Xr, has)
            run(f"R+{name}", np.c_[self.Xr, X], has)
        has = d["has_prf"]
        col = np.full(n, np.nan)
        rates = {}
        for lvl in (0.0, 1.0):
            rows = hist & has & (d["X_prf"][:, 0] == lvl)
            rates[lvl] = float(y[rows].mean()) if rows.sum() >= 20 else float(self.p0)
        if (hist & has).sum():
            col[has[test]] = np.where(d["X_prf"][test & has, 0] == 1.0, rates[1.0], rates[0.0])
            coefs["prf"] = [rates[0.0], rates[1.0]]
        out["prf"] = col
        run("R|prf", self.Xr, has)
        run("R+prf", np.c_[self.Xr, d["X_prf"]], has)
        both = d["has_rain"] & d["has_spills"]
        run("B7a", np.c_[self.Xr, d["X_last"], d["X_rain"]], d["has_rain"])
        run("R|rain&spills", self.Xr, both)
        run("B7b", np.c_[self.Xr, d["X_last"], d["X_rain"], d["X_spills"]], both)
        return out, coefs


def folds(d: dict, split: str):
    year, group = d["year"], d["group"]
    years = sorted(set(year))
    if split == "Y":
        for y in years:
            yield f"{y}", year != y, year == y
    elif split == "G":
        for g in range(5):
            yield f"g{g}", group != g, group == g
    elif split == "YG":
        for y in years:
            for g in range(5):
                yield f"{y}:g{g}", (year != y) & (group != g), (year == y) & (group == g)
    elif split == "F":
        for y in FORWARD_YEARS:
            yield f"{y}", year < y, year == y


def held_out(d: dict, split: str) -> tuple[pd.DataFrame, dict]:
    parts, coefs = [], {}
    for name, hist, test in folds(d, split):
        if not hist.any() or not test.any():
            continue
        pred, coefs[name] = Fold(d, hist, test).predictions()
        parts.append(pd.DataFrame(pred, index=np.flatnonzero(test)).assign(fold=name))
    return pd.concat(parts).sort_index(), coefs


# ------------------------------------------------------------------ scores
def auc_parts(score: np.ndarray):
    """What a weighted AUC needs, sorted once: each row's tie group in ascending score order."""
    _, group = np.unique(score, return_inverse=True)
    return group, (int(group.max()) + 1 if len(group) else 0)


def auc_weighted(group: np.ndarray, n_groups: int, y: np.ndarray, w: np.ndarray) -> float:
    """AUC with row weights (a site resampled twice counts twice); ties count a half."""
    pos = np.bincount(group, w * y, minlength=n_groups)
    neg = np.bincount(group, w * (1 - y), minlength=n_groups)
    if pos.sum() == 0 or neg.sum() == 0:
        return np.nan
    below = np.cumsum(neg) - neg
    return float((pos * (below + 0.5 * neg)).sum() / (pos.sum() * neg.sum()))


def stats(p: np.ndarray, y: np.ndarray, w: np.ndarray, parts) -> dict:
    sw = w.sum()
    if sw == 0:
        return {"brier": np.nan, "logloss": np.nan, "auc": np.nan}
    q = np.clip(p, *CLIP)
    return {"brier": float((w * (p - y) ** 2).sum() / sw),
            "logloss": float(-(w * (y * np.log(q) + (1 - y) * np.log(1 - q))).sum() / sw),
            "auc": auc_weighted(*parts, y, w)}


def ci(values: list[float]) -> list[float | None]:
    v = np.array(values, float)
    v = v[np.isfinite(v)]
    return [None, None] if len(v) < 100 else [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


def evaluate(pred: pd.DataFrame, d: dict, models: list[str], pairs: list[tuple[str, str]],
             subset: np.ndarray | None = None) -> dict:
    """Point scores and site-bootstrap intervals for `models`, and paired differences for `pairs`, on the rows of
    `pred` (optionally only those in `subset`). A model is scored on the rows where it has a prediction; a pair on
    the rows where both have one."""
    rows = pred.index.to_numpy()
    keep = np.ones(len(rows), bool) if subset is None else subset[rows]
    rows = rows[keep]
    y, site, year = d["y"][rows].astype(float), d["site"][rows], d["year"][rows]
    P = {m: pred[m].to_numpy()[keep] for m in set(models) | {a for p in pairs for a in p} | {"B0"}}
    rng = np.random.default_rng(SEED)
    sites = np.unique(site)
    code = np.searchsorted(sites, site)
    draws = [np.bincount(rng.integers(0, len(sites), len(sites)), minlength=len(sites))[code].astype(float)
             for _ in range(RESAMPLES)]
    out = {"models": {}, "pairs": {}}

    def prepared(names: tuple[str, ...]):
        ok = np.all([np.isfinite(P[n]) for n in names], axis=0)
        return ok, {n: (P[n][ok], auc_parts(P[n][ok])) for n in names}

    for m in models:
        ok, prep = prepared((m, "B0"))
        if ok.sum() == 0:
            continue
        yy, one = y[ok], np.ones(int(ok.sum()))
        a, b = stats(prep[m][0], yy, one, prep[m][1]), stats(prep["B0"][0], yy, one, prep["B0"][1])
        boot = {"brier": [], "bss_b0": [], "auc": []}
        for w in draws:
            w = w[ok]
            sa, sb = stats(prep[m][0], yy, w, prep[m][1]), stats(prep["B0"][0], yy, w, prep["B0"][1])
            boot["brier"].append(sa["brier"])
            boot["bss_b0"].append(1 - sa["brier"] / sb["brier"] if sb["brier"] else np.nan)
            boot["auc"].append(sa["auc"])
        by_year = {}
        for yr in sorted(set(year[ok])):
            r = year[ok] == yr
            sy = stats(prep[m][0][r], yy[r], np.ones(int(r.sum())), auc_parts(prep[m][0][r]))
            s0 = stats(prep["B0"][0][r], yy[r], np.ones(int(r.sum())), auc_parts(prep["B0"][0][r]))
            by_year[int(yr)] = {"rows": int(r.sum()), "exceedances": int(yy[r].sum()), "brier": sy["brier"],
                                "bss_b0": 1 - sy["brier"] / s0["brier"] if s0["brier"] else None, "auc": sy["auc"]}
        out["models"][m] = {"rows": int(ok.sum()), "sites": int(len(np.unique(site[ok]))), "exceedances": int(yy.sum()),
                            "observed_rate": float(yy.mean()), "mean_prediction": float(prep[m][0].mean()),
                            "brier": a["brier"], "brier_ci": ci(boot["brier"]),
                            "bss_b0": 1 - a["brier"] / b["brier"] if b["brier"] else None, "bss_b0_ci": ci(boot["bss_b0"]),
                            "auc": a["auc"], "auc_ci": ci(boot["auc"]), "logloss": a["logloss"], "by_year": by_year}
    for a_name, b_name in pairs:
        ok, prep = prepared((a_name, b_name))
        if ok.sum() == 0:
            continue
        yy, one = y[ok], np.ones(int(ok.sum()))
        a, b = stats(prep[a_name][0], yy, one, prep[a_name][1]), stats(prep[b_name][0], yy, one, prep[b_name][1])
        boot = {"d_brier": [], "skill": [], "d_auc": []}
        for w in draws:
            w = w[ok]
            sa, sb = stats(prep[a_name][0], yy, w, prep[a_name][1]), stats(prep[b_name][0], yy, w, prep[b_name][1])
            boot["d_brier"].append(sa["brier"] - sb["brier"])
            boot["skill"].append(1 - sa["brier"] / sb["brier"] if sb["brier"] else np.nan)
            boot["d_auc"].append(sa["auc"] - sb["auc"])
        out["pairs"][f"{a_name} vs {b_name}"] = {
            "rows": int(ok.sum()), "sites": int(len(np.unique(site[ok]))), "exceedances": int(yy.sum()),
            "brier_a": a["brier"], "brier_b": b["brier"], "d_brier": a["brier"] - b["brier"], "d_brier_ci": ci(boot["d_brier"]),
            "skill": 1 - a["brier"] / b["brier"] if b["brier"] else None, "skill_ci": ci(boot["skill"]),
            "auc_a": a["auc"], "auc_b": b["auc"], "d_auc": a["auc"] - b["auc"], "d_auc_ci": ci(boot["d_auc"])}
    return out


MODELS = ["B0", "B1", "B2", "R", "last", "R+last", "rain", "R|rain", "R+rain", "spills", "R|spills", "R+spills",
          "prf", "R|prf", "R+prf", "B7a", "R|rain&spills", "B7b"]
PAIRS = [("B1", "B0"), ("B2", "B0"), ("R", "B0"), ("R", "B1"), ("last", "B0"), ("rain", "B0"), ("spills", "B0"),
         ("prf", "B0"), ("R+last", "R|last"), ("R+rain", "R|rain"), ("R+spills", "R|spills"), ("R+prf", "R|prf"),
         ("R+rain", "R"), ("R+spills", "R"), ("R+prf", "R"), ("B7a", "R|rain"), ("B7a", "R+rain"),
         ("B7b", "R|rain&spills"), ("prf", "R|prf"), ("rain", "prf"), ("R+rain", "R+prf")]
DECIDING = {"last": "R+last vs R|last", "rain": "R+rain vs R|rain", "spills": "R+spills vs R|spills",
            "prf": "R+prf vs R|prf"}


def table(d: pd.DataFrame, target: str) -> dict:
    """The arrays every fold reads. Rows are statutory samples from May to September."""
    d = d[d["month"].isin(MONTHS)].reset_index(drop=True)
    sites, site = np.unique(d["site_id"].to_numpy(), return_inverse=True)
    years, year_code = np.unique(d["year"].to_numpy(), return_inverse=True)
    prev = d["prev_ecoli"].to_numpy(float)
    none = ~np.isfinite(prev)
    X_last = np.c_[np.where(none, 0.0, np.log10(np.where(none, 10.0, prev)) - 1), none.astype(float)]
    has_rain = d["rain_ok"].to_numpy(bool)
    X_rain = np.nan_to_num(np.c_[np.log1p(d["r24"].to_numpy(float)), np.log1p(d["r72"].to_numpy(float))])
    has_spills = d["near_h"].notna().to_numpy()
    X_spills = np.nan_to_num(np.log1p(d[["near_h", "ring_h", "river_h"]].to_numpy(float)))
    has_prf = d["prf_level"].isin(["normal", "increased"]).to_numpy()
    X_prf = (d["prf_level"] == "increased").to_numpy(float).reshape(-1, 1)
    return {"frame": d, "y": d[TARGETS[target]].to_numpy(int), "site": site, "n_sites": len(sites), "sites": sites,
            "year": d["year"].to_numpy(int), "year_code": year_code, "n_years": len(years), "month": d["month"].to_numpy(int),
            "group": d["site_group"].to_numpy(int), "X_last": X_last, "has_last": np.ones(len(d), bool),
            "X_rain": X_rain, "has_rain": has_rain, "X_spills": X_spills, "has_spills": has_spills,
            "X_prf": X_prf, "has_prf": has_prf, "own": d["ea_own_forecast"].to_numpy(bool) & has_prf}


def prf_counts(d: dict, rows: np.ndarray) -> dict:
    y, inc = d["y"][rows], d["X_prf"][rows, 0] == 1.0
    return {"rows": int(rows.sum()), "exceedances": int(y.sum()), "increased_in_force": int(inc.sum()),
            "exceedances_under_increased": int(y[inc].sum()), "exceedances_under_normal": int(y[~inc].sum()),
            "rate_under_increased": float(y[inc].mean()) if inc.any() else None,
            "rate_under_normal": float(y[~inc].mean()) if (~inc).any() else None,
            "share_of_exceedances_with_increased": float(y[inc].sum() / y.sum()) if y.sum() else None,
            "by_year": {int(yr): {"rows": int((d["year"][rows] == yr).sum()), "increased": int(inc[d["year"][rows] == yr].sum()),
                                  "exceedances": int(y[d["year"][rows] == yr].sum()),
                                  "exceedances_under_increased": int(y[(d["year"][rows] == yr) & inc].sum())}
                        for yr in sorted(set(d["year"][rows]))}}


def f(x, n=4):
    return "–" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{n}f}"


def span(c, n=4):
    return "–" if c is None or c[0] is None else f"{c[0]:.{n}f} to {c[1]:.{n}f}"


def markdown(res: dict) -> str:
    lines = []
    for target, by_split in res["targets"].items():
        for split, r in by_split["splits"].items():
            lines += [f"### {target}, split {split}", "",
                      "| Model | Rows | Sites | Exceed. | Brier | Skill vs B0 (95%) | AUC (95%) | Mean pred. | Observed |",
                      "|---|---|---|---|---|---|---|---|---|"]
            for m, s in r["all"]["models"].items():
                lines.append(f"| {m} | {s['rows']:,} | {s['sites']} | {s['exceedances']} | {f(s['brier'], 5)} | "
                             f"{f(s['bss_b0'], 3)} ({span(s['bss_b0_ci'], 3)}) | {f(s['auc'], 3)} ({span(s['auc_ci'], 3)}) | "
                             f"{f(s['mean_prediction'])} | {f(s['observed_rate'])} |")
            lines += ["", "| Pair (a vs b) | Rows | Exceed. | Brier a − b (95%) | Skill of a over b (95%) | AUC a − b (95%) |",
                      "|---|---|---|---|---|---|"]
            for name, s in r["all"]["pairs"].items():
                lines.append(f"| {name} | {s['rows']:,} | {s['exceedances']} | {f(s['d_brier'], 5)} ({span(s['d_brier_ci'], 5)}) | "
                             f"{f(s['skill'], 3)} ({span(s['skill_ci'], 3)}) | {f(s['d_auc'], 3)} ({span(s['d_auc_ci'], 3)}) |")
            lines.append("")
    return "\n".join(lines)


def main(features: Path, out: Path) -> None:
    raw = pd.read_parquet(features)
    res = {"seed": SEED, "resamples": RESAMPLES, "targets": {}}
    for target in TARGETS:
        d = table(raw, target)
        entry = {"rows": len(d["y"]), "sites": d["n_sites"], "exceedances": int(d["y"].sum()),
                 "by_year": {int(y): {"rows": int((d["year"] == y).sum()), "exceedances": int(d["y"][d["year"] == y].sum())}
                             for y in sorted(set(d["year"]))},
                 "rows_with": {k: int(d[f"has_{k}"].sum()) for k in INPUTS},
                 "prf_counts": {"all": prf_counts(d, d["has_prf"]), "ea_own_forecast": prf_counts(d, d["own"])},
                 "splits": {}}
        keep = []
        for split in ("Y", "G", "YG", "F"):
            pred, coefs = held_out(d, split)
            r = {"folds": sorted(set(pred["fold"])), "fitted": coefs, "all": evaluate(pred, d, MODELS, PAIRS)}
            if d["own"].any():
                r["ea_own_forecast"] = evaluate(pred, d, ["B0", "R|prf", "prf", "R+prf", "rain", "R+rain"],
                                                [("prf", "B0"), ("R+prf", "R|prf"), ("rain", "prf"), ("R+rain", "R+prf")],
                                                subset=d["own"])
            entry["splits"][split] = r
            keep.append(pred.assign(split=split, row=pred.index))
            print(f"{target} {split}: scored", flush=True)
        entry["supported"] = {}
        for name, pair in DECIDING.items():
            cis = [entry["splits"][s]["all"]["pairs"].get(pair, {}).get("d_brier_ci") for s in ("Y", "YG")]
            entry["supported"][name] = bool(all(c and c[1] is not None and c[1] < 0 for c in cis))
        res["targets"][target] = entry
        ids = d["frame"][["site_id", "time", "year"]].assign(y=d["y"])
        pd.concat(keep).merge(ids, left_on="row", right_index=True).to_parquet(out / f"predictions_{target}.parquet", index=False)
    (out / "scores.json").write_text(json.dumps(res, indent=1) + "\n")
    (out / "scores.md").write_text(markdown(res) + "\n")
    print(json.dumps({t: res["targets"][t]["supported"] for t in res["targets"]}), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
