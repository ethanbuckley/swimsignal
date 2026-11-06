"""BENCH, first task: E. coli over 900 at inland bathing waters (docs/BENCH-ECOLI900-2026-11.md).

Three baselines scored by leave-one-season-out on the committed data/research/ecoli_evidence.v1.json, with intervals
from a bootstrap of sites. Prints the scores as JSON. Offline; reads nothing else.

    python scripts/bench_ecoli900.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
# The concentration study's rows (one of the evidence file's sources): p_fwd is the production model's form refitted
# forward in time (2024 predicts 2025; 2024-25 predict 2026), p_loyo the hindsight the evidence file publishes.
ATLAS = ROOT / "docs" / "CONCENTRATION-STUDY-2026-11-atlas-rows.csv"
SEED, DRAWS = 20261105, 2000


def rows(path: Path = EVIDENCE, gap_days: float = 0.0) -> list[dict]:
    """One row a sample, in time order within each site, with the result of the latest earlier sample at the same site
    in the same season taken at least gap_days before (None for none). gap_days 0 is the protocol's "previous sample";
    3 is the review's "a result known by then" (an assumption about lab turnaround, not a checked one)."""
    fwd = {}
    with ATLAS.open() as f:
        for a in csv.DictReader(f):
            fwd[(a["bw_id"], datetime.fromisoformat(a["sample_time"]))] = (float(a["p_fwd"]) if a["p_fwd"] not in ("", "nan") else None,
                                                                          float(a["p_loyo"]) if a["p_loyo"] not in ("", "nan") else None)
    out = []
    for s in json.loads(path.read_text())["sites"]:
        seen: list[tuple[datetime, bool]] = []
        for x in sorted(s["samples"], key=lambda x: x["t"]):
            t, y = datetime.fromisoformat(x["t"]), int(x["t"][:4])
            seen = [z for z in seen if z[0].year == y]
            known = [o for (u, o) in seen if (t - u).total_seconds() >= gap_days * 86400 and u < t]
            f, loyo = fwd.get((s["bw_id"], t), (None, None))
            out.append({"site": s["spot_id"], "kind": s["kind"], "season": y, "month": int(x["t"][5:7]),
                        "over": bool(x["over"]), "prev": known[-1] if known else None, "hindsight": x.get("hindsight"),
                        "forward": f, "loyo": loyo})
            seen.append((t, bool(x["over"])))
    return out


def baselines(rs: list[dict], forward: bool = False) -> dict[str, np.ndarray]:
    """Each baseline's probability for every row; baselines 1 and 2 fitted on the other seasons (the protocol), or with
    forward on the earlier seasons only (NaN for a season with none before it). Baseline 3 is as published, NaN where
    missing; it is refitted leaving each year out, so it is never forward-only."""
    seasons = sorted({r["season"] for r in rs})
    month, last = np.full(len(rs), np.nan), np.full(len(rs), np.nan)
    for y in seasons:
        train = [r for r in rs if (r["season"] < y if forward else r["season"] != y)]
        if not train:
            continue
        rate = {m: np.mean([r["over"] for r in train if r["month"] == m]) for m in {r["month"] for r in train}}
        overall = np.mean([r["over"] for r in train])
        after = {p: np.mean([r["over"] for r in train if r["prev"] is p]) for p in (True, False)}
        for i, r in enumerate(rs):
            if r["season"] != y:
                continue
            month[i] = rate.get(r["month"], overall)
            last[i] = month[i] if r["prev"] is None else after[r["prev"]]
    hind = np.array([np.nan if r["hindsight"] is None else float(r["hindsight"]) for r in rs])
    if forward:   # the model's own forward fit (2025-26 only), never the leave-one-year-out hindsight
        return {"month_rate": month, "last_sample": last,
                "model_forward": np.array([np.nan if r["forward"] is None else r["forward"] for r in rs])}
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


def score(sites: np.ndarray, y: np.ndarray, preds: dict[str, np.ndarray], seasons: np.ndarray) -> dict:
    """Brier, Brier skill against the month rate and AUC for each baseline, with 95% intervals from a bootstrap of sites,
    and the paired Brier difference between every two baselines from the same draws (a difference is shown only by
    its own interval, never by two separate intervals). AUC both pooled across seasons and within each season: under
    leave one season out each season's predictions come from one fit, so only a within-season AUC compares predictions
    from the same fit; a pooled AUC also ranks one fit's numbers against another's."""
    ref = "month_rate"
    names = list(preds)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    years = sorted(set(seasons.tolist()))

    def within(k, idx):   # the mean of the seasons' own AUCs, over seasons with both outcomes
        v = [auc(preds[k][idx][seasons[idx] == yr], y[idx][seasons[idx] == yr]) for yr in years]
        v = [a for a in v if a is not None]
        return float(np.mean(v)) if v else None

    def stats(idx):
        b = {k: brier(preds[k][idx], y[idx]) for k in names}
        return b, {k: auc(preds[k][idx], y[idx]) for k in names}, {k: within(k, idx) for k in names}
    b0, a0, w0 = stats(np.arange(len(y)))
    rng = np.random.default_rng(SEED)
    uniq = np.unique(sites)
    by_site = {s: np.flatnonzero(sites == s) for s in uniq}
    draws = {k: {"brier": [], "auc": [], "within": [], "skill": []} for k in names}
    diffs = {f"{a} - {b}": [] for a, b in pairs}
    for _ in range(DRAWS):
        idx = np.concatenate([by_site[s] for s in rng.choice(uniq, size=len(uniq), replace=True)])
        b, a, w = stats(idx)
        for k in names:
            draws[k]["brier"].append(b[k]); draws[k]["skill"].append(1 - b[k] / b[ref])
            if a[k] is not None:
                draws[k]["auc"].append(a[k])
            if w[k] is not None:
                draws[k]["within"].append(w[k])
        for a_, b_ in pairs:
            diffs[f"{a_} - {b_}"].append(b[a_] - b[b_])
    ci = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
    out = {"rows": int(len(y)), "over_900": int(y.sum()), "sites": int(len(uniq))}
    for k in names:
        out[k] = {"brier": round(b0[k], 4), "brier_95": ci(draws[k]["brier"]),
                  "skill_vs_month_rate": round(1 - b0[k] / b0[ref], 4), "skill_95": ci(draws[k]["skill"]),
                  "auc_pooled": None if a0[k] is None else round(a0[k], 4), "auc_pooled_95": ci(draws[k]["auc"]) if draws[k]["auc"] else None,
                  "auc_within_season": None if w0[k] is None else round(w0[k], 4),
                  "auc_within_season_95": ci(draws[k]["within"]) if draws[k]["within"] else None,
                  "auc_by_season": {str(yr): (lambda v: None if v is None else round(v, 4))(
                      auc(preds[k][seasons == yr], y[seasons == yr])) for yr in years}}
    out["brier_differences"] = {d: {"point": round(b0[d.split(" - ")[0]] - b0[d.split(" - ")[1]], 4), "ci_95": ci(v)} for d, v in diffs.items()}
    return out


def table(rs: list[dict], forward: bool = False) -> dict:
    preds = baselines(rs, forward)
    y = np.array([r["over"] for r in rs], dtype=float)
    sites = np.array([r["site"] for r in rs])
    model = "model_forward" if forward else "model_hindsight"
    scored = ~np.isnan(preds["month_rate"])
    has = scored & ~np.isnan(preds[model])
    seasons = np.array([r["season"] for r in rs])
    return {"all_rows": score(sites[scored], y[scored], {k: preds[k][scored] for k in ("month_rate", "last_sample")}, seasons[scored]),
            ("rows_with_model_forward" if forward else "rows_with_hindsight"):
                score(sites[has], y[has], {k: v[has] for k, v in preds.items()}, seasons[has])}


def run(path: Path = EVIDENCE) -> dict:
    """The protocol's scores as fixed before the first run, then the review's two variants (5 Nov 2026, after it):
    forward-only fitting, and a previous result counted only when its sample was 3 days older."""
    return {"task": "E. coli over 900 at inland bathing waters, May-September 2023-26",
            "source": str(path.relative_to(ROOT)), "seed": SEED, "draws": DRAWS,
            **table(rows(path)),
            "review_forward_only": table(rows(path), forward=True),
            "review_result_known_3_days": table(rows(path, gap_days=3.0)),
            "review_forward_and_3_days": table(rows(path, gap_days=3.0), forward=True),
            # How the last sample's score depends on when its result is taken to be known: the file has no report
            # dates, so the true turnaround is not known here. Forward fits; the last sample against the month rate.
            "review_turnaround_sensitivity": {f"{g:g}_days": (lambda t: {
                "rows": t["rows"],
                # Positive: the last sample's Brier is lower than the month rate's (it helps).
                "month_rate_minus_last_sample": t["brier_differences"]["month_rate - last_sample"],
                "rows_using_a_previous_result": sum(r["prev"] is not None for r in rows(path, gap_days=g) if r["season"] >= 2024)})(
                table(rows(path, gap_days=g), forward=True)["all_rows"]) for g in (0, 1, 2, 3, 5, 7)}}


if __name__ == "__main__":
    json.dump(run(), sys.stdout, indent=1)
    print()
