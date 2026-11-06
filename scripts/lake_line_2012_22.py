"""The frozen lake concentration models on 2012-2022 lake seasons: an out-of-time development comparison on previously
examined outcomes (docs/LAKE-LINE-2012-22-CHECK-2026-11.md; protocol 96392731, pushed before any request or join).

The rows are #584's, rebuilt by its own code (an archive of 0be59d2d) in a scratch root under a capped, ledgered fetch:
rows_train.parquet (2023-26) and rows_test.parquet (2012-22) in LAKE_RANGE_OUT. This script reads them, the frozen
files, and nothing else; it fits only production's form (refitted on the 2023-26 rows, as #584 did).

    LAKE_RANGE_OUT=<scratch>/out uv run python scripts/lake_line_2012_22.py      # scores and the rows file
    uv run python scripts/lake_line_2012_22.py --from-rows                         # recompute from the committed rows file
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import log_ndtr, logsumexp, ndtr
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lake_own_rate_test import auc  # noqa: E402

DOC = ROOT / "docs" / "LAKE-LINE-2012-22-CHECK-2026-11"
FROZEN = ROOT / "data" / "research" / "lake_line_frozen.v1.json"
FROZEN_SHA = "83a3a8d0929afb1ff178cc064e4fb8b4ec0af64810b5a2a1435108e3594a1c23"
RANGE = ROOT / "data" / "processed" / "ecoli_lake_range.json"
DEPLOYED = ROOT / "data" / "processed" / "ecoli_model.json"
EVID = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
SEED, DRAWS = 20261106, 2000
LOW, HIGH = 10.0, 10_000.0
PROD = ["lrain48", "lrain24", "logit_risk", "lake", "lake_x_lrain48", "doy_sin", "doy_cos"]
SCORES = ("plain_med", "B_med", "range_med", "production", "deployed")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ the frozen mixtures
def mixture(f: dict, X: pd.DataFrame, bw: str, kind: str) -> tuple[np.ndarray, np.ndarray, float]:
    """(weights over nodes [K], mu [n, K], noise) of a frozen random-intercept model: 'plain' and 'B' from the line file,
    'range' from lake-range-v1's file. A site not in the file uses the prior."""
    m = f if kind == "range" else f[kind]
    Z = np.column_stack([np.ones(len(X))] + [(X[c].to_numpy(float) - m["mean"][c]) / m["sd"][c] for c in m["cols"]])
    mu = (Z @ np.asarray(m["beta"]))[:, None]
    if kind == "B":
        mu = mu + m["tau"] * np.asarray(m["gu"])[None, :] + \
            m["tau_v"] * X["lake_x_wet"].to_numpy(float)[:, None] * np.asarray(m["gv"])[None, :]
    else:
        mu = mu + np.sqrt(2.0) * m["tau"] * np.asarray(m["nodes"])[None, :]
    lw = m["sites"][bw]["log_weights"] if kind == "range" else m["log_weights"].get(bw, m["log_prior"])
    lw = np.asarray(lw)
    return np.exp(lw - logsumexp(lw)), mu, float(m["sigma_lake"])


def add_wet(X: pd.DataFrame, w: dict) -> pd.DataFrame:
    raw = ((X["lrain48"] - w["m48"]) / w["s48"] + (X["logit_risk"] - w["mr"]) / w["sr"]) / 2
    return X.assign(lake_x_wet=X["lake"] * (raw - w["mw"]) / w["sw"])


def summaries(w, mu, s, y, cens) -> dict:
    lo, hi = np.full(len(mu), -2.0), np.full(len(mu), 7.0)
    for _ in range(40):
        mid = (lo + hi) / 2
        below = (w[None, :] * ndtr((mid[:, None] - mu) / s)).sum(1) < 0.5
        lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
    z = (y[:, None] - mu) / s
    ll = np.where(cens[:, None] < 0, log_ndtr((np.log10(LOW) - mu) / s),
                  np.where(cens[:, None] > 0, log_ndtr((mu - np.log10(HIGH)) / s), -0.5 * z * z - np.log(s) - 0.5 * np.log(2 * np.pi)))
    F = (w[None, :] * ndtr(z)).sum(1)
    F_low = (w[None, :] * ndtr((np.log10(LOW) - mu) / s)).sum(1)
    return {"med": (lo + hi) / 2, "ls": logsumexp(np.log(np.clip(w, 1e-300, None))[None, :] + ll, axis=1),
            "F": np.where(cens < 0, F_low / 2, F), "p900": (w[None, :] * ndtr((mu - np.log10(900)) / s)).sum(1),
            "p500": (w[None, :] * ndtr((mu - np.log10(500)) / s)).sum(1)}


# ------------------------------------------------------------------ rows and forecasts
def build(out_dir: Path) -> pd.DataFrame:
    from dipcast.model.ecoli import EcoliModel, fit
    f, rng_f = json.loads(FROZEN.read_text()), json.loads(RANGE.read_text())
    tr, te = pd.read_parquet(out_dir / "rows_train.parquet"), pd.read_parquet(out_dir / "rows_test.parquet")
    tr = tr.drop_duplicates(["bw_id", "sample_time"])
    te = te.reset_index(drop=True)
    te["y"] = np.log10(te["ecoli"].clip(lower=1).astype(float))
    te["cens"] = np.select([te["qual"].eq("<"), te["qual"].eq(">")], [-1, 1], 0)
    tr_over = (tr["ecoli"] > 900).astype(int).to_numpy()
    te["production"] = fit(tr, tr_over, PROD).predict(te)       # refitted on #584's 2023-26 rows, as #584 did
    te["deployed"] = EcoliModel.from_json(DEPLOYED).predict(te)
    Xw = add_wet(te, f["B"]["wet"])
    y, c = te["y"].to_numpy(), te["cens"].to_numpy()
    for bw, idx in te.groupby("bw_id").groups.items():
        idx = np.asarray(idx)
        for kind, X, src in (("plain", te, f), ("B", Xw, f), ("range", te, rng_f)):
            s = summaries(*mixture(src, X.loc[idx], bw, kind), y[idx], c[idx])
            for k, v in s.items():
                te.loc[idx, f"{kind}_{k}"] = v
    te["year"] = pd.to_datetime(te["sample_time"], utc=True).dt.year
    te["cluster"] = te["bw_id"] + "|" + te["year"].astype(str)
    keep = ["bw_id", "name", "sample_time", "year", "cluster", "ecoli", "qual", "y", "cens", "rain_48h", "rain_24h",
            "risk_model", "production", "deployed"] + [f"{k}_{s}" for k in ("plain", "B", "range") for s in ("med", "ls", "F", "p900", "p500")]
    return te[keep]


def mean_site_rho(d: pd.DataFrame, col: str) -> tuple[float, dict]:
    by = {}
    for bw, g in d.groupby("bw_id"):
        if len(g) >= 15 and g[col].nunique() > 1 and g["y"].nunique() > 1:
            by[bw] = float(spearmanr(g[col], g["y"]).statistic)
    return float(np.mean(list(by.values()))), by


def boot_rho_diff(d: pd.DataFrame, a: str, b: str) -> list[float]:
    """95% interval of mean-site-rho(a) - mean-site-rho(b), resampling site x season clusters."""
    groups = {k: g for k, g in d.groupby("cluster")}
    keys = list(groups)
    rng = np.random.default_rng(SEED)
    vals = []
    for _ in range(DRAWS):
        s = pd.concat([groups[k] for k in rng.choice(keys, len(keys))], ignore_index=True)
        vals.append(mean_site_rho(s, a)[0] - mean_site_rho(s, b)[0])
    return [round(float(v), 4) for v in np.percentile(vals, [2.5, 97.5])]


def boot_mean(d: np.ndarray, cluster: np.ndarray) -> list[float]:
    codes, inv = np.unique(cluster, return_inverse=True)
    s, n = np.bincount(inv, weights=d), np.bincount(inv).astype(float)
    draws = np.random.default_rng(SEED).integers(0, len(codes), size=(DRAWS, len(codes)))
    return [round(float(v), 4) for v in np.percentile(s[draws].sum(1) / n[draws].sum(1), [2.5, 97.5])]


def score(d: pd.DataFrame) -> dict:
    res = {"rows": int(len(d)), "sites": int(d["bw_id"].nunique()), "clusters": int(d["cluster"].nunique()),
           "over_900": int((d["ecoli"] > 900).sum()), "over_500": int((d["ecoli"] > 500).sum()),
           "below_limit": int((d["cens"] < 0).sum())}
    rho = {k: mean_site_rho(d, k) for k in SCORES}
    res["mean_site_rho"] = {k: round(v[0], 4) for k, v in rho.items()}
    res["site_rho"] = {k: {bw: round(x, 3) for bw, x in v[1].items()} for k, v in rho.items()}
    res["primary"] = {}
    for a in ("plain_med", "B_med"):
        for b in ("production", "deployed"):
            res["primary"][f"{a}_minus_{b}"] = {"mean": round(rho[a][0] - rho[b][0], 4), "ci95": boot_rho_diff(d, a, b)}
    res["primary"]["B_med_minus_plain_med"] = {"mean": round(rho["B_med"][0] - rho["plain_med"][0], 4),
                                                "ci95": boot_rho_diff(d, "B_med", "plain_med")}
    res["by_season"] = {}
    for yv, g in d.groupby("year"):
        r = {k: round(mean_site_rho(g, k)[0], 3) for k in SCORES}
        res["by_season"][str(yv)] = {"rows": int(len(g)), "over_500": int((g["ecoli"] > 500).sum()), **r}
    # the concentration
    ls = {k: d[f"{k}_ls"].to_numpy() for k in ("plain", "B", "range")}
    res["logscore"] = {k: round(float(v.mean()), 4) for k, v in ls.items()}
    res["logscore_diff"] = {f"{a}_minus_{b}": {"mean": round(float((ls[a] - ls[b]).mean()), 4),
                                               "ci95": boot_mean(ls[a] - ls[b], d["cluster"].to_numpy())}
                            for a, b in (("plain", "range"), ("B", "range"), ("B", "plain"))}
    rng = np.random.default_rng(SEED)
    cov = {}
    for k in ("plain", "B", "range"):
        F = d[f"{k}_F"].to_numpy()
        pit = np.where(d["cens"].to_numpy() < 0, rng.uniform(size=len(d)) * 2 * F, F)   # F stored as F(10)/2 for "<10"
        cov[k] = round(float(((pit >= 0.1) & (pit <= 0.9)).mean()), 4)
    res["central80"] = cov
    # over 500: weak; over 900: counts only
    ev = json.loads(EVID.read_text())
    own500 = {s["bw_id"]: float(np.mean([x["ecoli"] is not None and x["ecoli"] > 500 for x in s["samples"]]))
              for s in ev["sites"] if s["bw_id"] in set(d["bw_id"])}
    f = json.loads(FROZEN.read_text())
    o5 = (d["ecoli"] > 500).astype(int).to_numpy()
    p = {"plain": d["plain_p500"].to_numpy(), "B": d["B_p500"].to_numpy(), "range": d["range_p500"].to_numpy(),
         "usual": np.full(len(d), f["usual_rate_2023_26"]["500"]), "own": d["bw_id"].map(own500).to_numpy()}
    b = {k: round(float(((v - o5) ** 2).mean()), 5) for k, v in p.items()}
    res["over_500"] = {"brier": b, "skill_vs_usual": {k: round(1 - b[k] / b["usual"], 4) for k in b},
                       "auc": {k: round(auc(v, o5), 3) for k, v in p.items()},
                       "note": "28 results over 500 at five sites on two water bodies: weak."}
    res["over_900"] = {"results": res["over_900"], "note": "too few to judge a line chance; counts only, no score"}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-rows", action="store_true")
    args = ap.parse_args()
    assert sha(FROZEN) == FROZEN_SHA, "the frozen file changed"
    inputs = [FROZEN, RANGE, DEPLOYED, EVID]
    before = {p.name: sha(p) for p in inputs}
    if args.from_rows:
        d = pd.read_csv(f"{DOC}-rows.csv")
    else:
        d = build(Path(os.environ["LAKE_RANGE_OUT"]))
        d.round(6).to_csv(f"{DOC}-rows.csv", index=False)
        d = pd.read_csv(f"{DOC}-rows.csv")   # score exactly what is committed
    res = {"schema": "swimsignal.lake-line-2012-22-check", "version": "1.0.0", "protocol": "docs/LAKE-LINE-2012-22-CHECK-2026-11.md",
           "protocol_commit": "96392731", "label": "out-of-time development comparison on previously examined outcomes",
           "seed": SEED, "draws": DRAWS, "inputs_sha256": before, "rows_sha256": sha(Path(f"{DOC}-rows.csv")), **score(d)}
    p = res["primary"]
    res["holds"] = {k: bool(p[f"{k}_minus_production"]["ci95"][0] > 0) for k in ("plain_med", "B_med")}
    assert before == {q.name: sha(q) for q in inputs}
    if not args.from_rows:
        Path(f"{DOC}-scores.json").write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({k: res[k] for k in ("rows", "over_900", "over_500", "mean_site_rho", "primary", "holds", "by_season",
                                          "logscore", "logscore_diff", "central80")}, indent=1, default=float))


if __name__ == "__main__":
    main()
