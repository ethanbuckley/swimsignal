"""docs/LAKE-AVERAGE-BASIS-CHECK-2026-11.md: does lake-range-v1's range hold at a lake the model knows nothing about?
Development, on the bench's seen rows (2023-26) only. Writes docs/lake-average-check/results.json.

    uv run python scripts/lake_average_check.py

A: the average lake (the refit's prior), leave one water body out. B: an equal-weight mixture over the known lakes'
levels, same folds. C: another site on the same lake, leave one site out. No request.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "backtest_bench"))
import bench  # noqa: E402
from concentration_study import CensoredRI, _std, row_loglik  # noqa: E402

from dipcast.model.ecoli import FEATURES  # noqa: E402

OUT = REPO / "docs" / "lake-average-check" / "results.json"
LAKES = ("Windermere", "Hampstead Heath", "Coniston Water", "Rutland Water", "Derwent Water")


def wb(name: str) -> str:
    return next((k for k in LAKES if name.startswith(k)), name)


def prep(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["y"] = np.log10(d["ecoli"].clip(lower=1).astype(float))
    d["cens"] = np.select([d["ecoli_qual"].eq("<"), d["ecoli_qual"].eq(">")], [-1, 1], 0)
    d["wb"] = d["name"].map(wb)
    return d


def fit(tr: pd.DataFrame) -> CensoredRI:
    m = CensoredRI(list(FEATURES), lake_sigma=True).fit(tr, tr["y"].to_numpy(), tr["cens"].to_numpy(), tr["bw_id"].to_numpy())
    assert m.converged
    return m


def post(m: CensoredRI) -> dict[str, np.ndarray]:
    """Each fitted site's node weights (probabilities)."""
    p = m.train_post - logsumexp(m.train_post, axis=1, keepdims=True)
    return {s: np.exp(p[i]) for i, s in enumerate(m.sites)}


def own(m: CensoredRI, rows: pd.DataFrame) -> np.ndarray:
    """A site not in the fit: the prior plus its rows' summed log-likelihood (bench read 2's rule)."""
    mu = _std(rows, m.cols, ref=m.ref) @ m.theta[:m.p]
    ll = row_loglik(mu[:, None] + np.sqrt(2.0) * m.tau * m.x[None, :], m.sigma_lake, rows["y"].to_numpy(),
                    rows["cens"].to_numpy()).sum(0)
    w = m.logw + ll
    return np.exp(w - logsumexp(w))


def mix(ws: list[np.ndarray]) -> np.ndarray:
    w = np.mean(ws, axis=0)
    return w / w.sum()


def figures(m: CensoredRI, rows: pd.DataFrame, w: np.ndarray) -> dict[str, np.ndarray]:
    mu = _std(rows, m.cols, ref=m.ref) @ m.theta[:m.p]
    u, s = np.sqrt(2.0) * m.tau * m.x, m.sigma_lake
    cdf = lambda v: (w[None, :] * norm.cdf((v[:, None] - mu[:, None] - u[None, :]) / s)).sum(1)   # noqa: E731
    out = {"p_le10": cdf(np.full(len(rows), 1.0)), "p_le10000": cdf(np.full(len(rows), 4.0))}
    for q in (0.1, 0.9):
        lo, hi = np.full(len(rows), -2.0), np.full(len(rows), 7.0)
        for _ in range(40):
            mid = (lo + hi) / 2
            below = cdf(mid) < q
            lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
        out[f"q{int(q * 100)}"] = (lo + hi) / 2
    return out


def score(rows: pd.DataFrame, f: dict) -> dict:
    ins, below, above = bench.inside80(rows.reset_index(drop=True), f)
    return {"rows": int(len(rows)), "inside": round(float(ins.mean()), 4), "below": round(float(below.mean()), 4),
            "above": round(float(above.mean()), 4), "median": round(float(10 ** np.median((f["q10"] + f["q90"]) / 2)), 1)}


def wb_levels(m: CensoredRI, d: pd.DataFrame) -> dict[str, np.ndarray]:
    """Each fitted lake water body's level: the mean of its sites' node weights."""
    p = post(m)
    lake = d[(d["kind"] == "lake") & d["bw_id"].isin(p)]
    return {k: mix([p[s] for s in g["bw_id"].unique()]) for k, g in lake.groupby("wb")}


def main() -> int:
    d = prep(bench.load("seen"))
    m_ref = json.loads((REPO / "data" / "processed" / "ecoli_lake_range.json").read_text())
    no_ov = set(d.loc[(d["kind"] == "lake") & ~d["bw_id"].isin(m_ref["sites"]), "bw_id"])
    train = d[~d["bw_id"].isin(no_ov)].reset_index(drop=True)
    full = fit(train)
    res = {"plan": "docs/LAKE-AVERAGE-BASIS-CHECK-2026-11.md", "rows_sha256": json.loads(bench.MANIFEST.read_text())["files"]["seen"]["sha256"],
           "train": {"rows": int(len(train)), "sites": int(train["bw_id"].nunique()),
                     "refit_vs_frozen": {"tau": [round(full.tau, 4), round(m_ref["tau"], 4)],
                                         "sigma_lake": [round(full.sigma_lake, 4), round(m_ref["sigma_lake"], 4)]}},
           "A": {}, "B": {}, "C": {}}
    lake = d[d["kind"] == "lake"]
    for w, rows in lake.groupby("wb"):
        if rows["bw_id"].isin(no_ov).all():
            m = full
        else:
            m = fit(train[train["wb"] != w].reset_index(drop=True))
        known = wb_levels(m, train[train["wb"] != w])
        res["A"][w] = score(rows, figures(m, rows, np.exp(m.logw - logsumexp(m.logw))))
        res["B"][w] = score(rows, figures(m, rows, mix(list(known.values()))))
        print(w, res["A"][w], res["B"][w], flush=True)
    p = post(full)
    for w, rows in lake.groupby("wb"):
        sites = list(rows["bw_id"].unique())
        if len(sites) < 2:
            continue
        for s in sites:
            others = [p[o] if o in p else own(full, lake[lake["bw_id"] == o]) for o in sites if o != s]
            r = rows[rows["bw_id"] == s]
            res["C"][f"{w} | {r['name'].iloc[0]}"] = score(r, figures(full, r, mix(others)))
    for k in ("A", "B", "C"):
        allrows = sum(v["rows"] for v in res[k].values())
        res[k + "_overall"] = round(sum(v["inside"] * v["rows"] for v in res[k].values()) / allrows, 4)
        res[k + "_lowest"] = min(v["inside"] for v in res[k].values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in res if k.endswith(("_overall", "_lowest"))} | {"train": res["train"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
