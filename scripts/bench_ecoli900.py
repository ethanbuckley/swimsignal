"""BENCH, first task: E. coli over 900 at inland bathing waters (docs/BENCH-ECOLI900-2026-11.md).

Three baselines scored by leave-one-season-out on the committed data/research/ecoli_evidence.v1.json, with intervals
from a bootstrap of sites. Prints the scores as JSON. Offline; reads nothing else.

    python scripts/bench_ecoli900.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
SEED, DRAWS = 20261105, 2000


def rows(path: Path = EVIDENCE) -> list[dict]:
    """One row a sample, in time order within each site, with the previous sample's result in the same season."""
    out = []
    for s in json.loads(path.read_text())["sites"]:
        prev, season = None, None
        for x in sorted(s["samples"], key=lambda x: x["t"]):
            y = int(x["t"][:4])
            if y != season:
                prev, season = None, y
            out.append({"site": s["spot_id"], "kind": s["kind"], "season": y, "month": int(x["t"][5:7]),
                        "over": bool(x["over"]), "prev": prev, "hindsight": x.get("hindsight")})
            prev = bool(x["over"])
    return out


def baselines(rs: list[dict]) -> dict[str, np.ndarray]:
    """Each baseline's probability for every row; fitted on the other seasons (baseline 3 is as published, NaN where
    missing)."""
    seasons = sorted({r["season"] for r in rs})
    month, last = np.zeros(len(rs)), np.zeros(len(rs))
    for y in seasons:
        train = [r for r in rs if r["season"] != y]
        rate = {m: np.mean([r["over"] for r in train if r["month"] == m]) for m in {r["month"] for r in train}}
        overall = np.mean([r["over"] for r in train])
        after = {p: np.mean([r["over"] for r in train if r["prev"] is p]) for p in (True, False)}
        for i, r in enumerate(rs):
            if r["season"] != y:
                continue
            month[i] = rate.get(r["month"], overall)
            last[i] = month[i] if r["prev"] is None else after[r["prev"]]
    hind = np.array([np.nan if r["hindsight"] is None else float(r["hindsight"]) for r in rs])
    return {"month_rate": month, "last_sample": last, "model_hindsight": hind}


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def auc(p: np.ndarray, y: np.ndarray) -> float | None:
    """The probability a random over-900 sample is given more than a random one under it, ties counting half."""
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return None
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    vals = np.concatenate([pos, neg])[order]
    ranks = np.empty(len(vals))
    i = 0
    while i < len(vals):   # average ranks over ties
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2 + 1
        i = j + 1
    r = np.empty(len(vals))
    r[order] = ranks
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def score(sites: np.ndarray, y: np.ndarray, preds: dict[str, np.ndarray]) -> dict:
    """Brier, Brier skill against the month rate and AUC for each baseline, each with a 95% interval from a bootstrap of
    sites, and each one's Brier difference from the month rate with its interval."""
    ref = "month_rate"
    names = list(preds)
    def stats(idx):
        b = {k: brier(preds[k][idx], y[idx]) for k in names}
        return b, {k: auc(preds[k][idx], y[idx]) for k in names}
    b0, a0 = stats(np.arange(len(y)))
    rng = np.random.default_rng(SEED)
    uniq = np.unique(sites)
    by_site = {s: np.flatnonzero(sites == s) for s in uniq}
    draws = {k: {"brier": [], "auc": [], "diff": [], "skill": []} for k in names}
    for _ in range(DRAWS):
        idx = np.concatenate([by_site[s] for s in rng.choice(uniq, size=len(uniq), replace=True)])
        b, a = stats(idx)
        for k in names:
            draws[k]["brier"].append(b[k]); draws[k]["diff"].append(b[k] - b[ref]); draws[k]["skill"].append(1 - b[k] / b[ref])
            if a[k] is not None:
                draws[k]["auc"].append(a[k])
    ci = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
    out = {"rows": int(len(y)), "over_900": int(y.sum()), "sites": int(len(uniq))}
    for k in names:
        out[k] = {"brier": round(b0[k], 4), "brier_95": ci(draws[k]["brier"]),
                  "skill_vs_month_rate": round(1 - b0[k] / b0[ref], 4), "skill_95": ci(draws[k]["skill"]),
                  "brier_minus_month_rate_95": ci(draws[k]["diff"]),
                  "auc": None if a0[k] is None else round(a0[k], 4), "auc_95": ci(draws[k]["auc"]) if draws[k]["auc"] else None}
    return out


def run(path: Path = EVIDENCE) -> dict:
    rs = rows(path)
    preds = baselines(rs)
    y = np.array([r["over"] for r in rs], dtype=float)
    sites = np.array([r["site"] for r in rs])
    has = ~np.isnan(preds["model_hindsight"])
    return {"task": "E. coli over 900 at inland bathing waters, May-September 2023-26, leave one season out",
            "source": str(path.relative_to(ROOT)), "seed": SEED, "draws": DRAWS,
            "all_rows": score(sites, y, {k: preds[k] for k in ("month_rate", "last_sample")}),
            "rows_with_hindsight": score(sites[has], y[has], {k: v[has] for k, v in preds.items()})}


if __name__ == "__main__":
    json.dump(run(), sys.stdout, indent=1)
    print()
