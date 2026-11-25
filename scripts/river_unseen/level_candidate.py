"""A usual level for a river place, and a range that knows how unsure that level is
(docs/RIVER-LEVEL-CANDIDATE-2026-11.md). Development: the rows were read on 16 November 2026.

    python scripts/river_unseen/level_candidate.py <held-out rows> docs/river-unseen/systems.csv \\
        docs/river-unseen/river_range_v0e.json docs/river-level [<seen bathing river rows>]

The form `river-level-v1`: log10 E. coli = intercept + the five river-range-v0 inputs + log10(km of channel upstream)
+ log(1 + overflows upstream) + a level for the place (normal, spread tau) + noise (normal, spread sigma). Fitted by
maximum likelihood (profile over tau^2 / sigma^2).

L1, a place with no samples: for each river system in turn, fit on the other systems' seasons to 2016, then give the
left-out system's samples from 2017 a range of half-width z * sqrt(tau^2 + sigma^2).
L2, a place with earlier samples: the same fit, then the place's level is estimated from its own seasons to 2016
(mean residual shrunk by tau^2 / (tau^2 + sigma^2 / n)); half-width z * sqrt(tau^2 sigma^2 / (n tau^2 + sigma^2)
+ sigma^2). Points with 10 or more samples to 2016.

Nothing is tuned on the scored rows. It writes <out>/result.json and appends to <out>/runs.jsonl whatever it shows."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

sys.path.insert(0, str(Path(__file__).resolve().parent))
import freeze_candidate as fc  # noqa: E402
import read as rd  # noqa: E402

Z = 1.2816
SPLIT = 2016
MIN_EARLY = 10
COVER = (0.72, 0.88)
MAX_TAIL = 0.18
PLACE = ["log_km", "log_overflows"]
INPUTS = [*fc.FEATURES, *PLACE]


def with_place_inputs(rows: pd.DataFrame, systems: pd.DataFrame) -> pd.DataFrame:
    d = rows.reset_index(drop=True).copy()
    km = systems.set_index("point")["upstream_km"]
    d["log_km"] = np.log10(d["bw_id"].map(km).astype(float).clip(lower=0.1))
    d["log_overflows"] = np.log1p(d["upstream"].astype(float))
    assert d[INPUTS].notna().all().all(), "a row has no place input"
    return d


def _gls(x: np.ndarray, y: np.ndarray, g: np.ndarray, r: float) -> tuple[np.ndarray, float, float]:
    """Coefficients, sigma^2 and minus twice the log-likelihood for a random intercept with tau^2 = r * sigma^2."""
    xtx, xty, logdet, parts = np.zeros((x.shape[1],) * 2), np.zeros(x.shape[1]), 0.0, []
    for k in np.unique(g):
        m = g == k
        xg, yg, n = x[m], y[m], int(m.sum())
        w = r / (1.0 + n * r)
        sx, sy = xg.sum(0), yg.sum()
        xtx += xg.T @ xg - w * np.outer(sx, sx)
        xty += xg.T @ yg - w * sx * sy
        logdet += np.log1p(n * r)
        parts.append((xg, yg, w))
    beta = np.linalg.solve(xtx, xty)
    q = 0.0
    for xg, yg, w in parts:
        e = yg - xg @ beta
        q += e @ e - w * e.sum() ** 2
    s2 = q / len(y)
    return beta, float(s2), float(len(y) * np.log(s2) + logdet)


def fit(d: pd.DataFrame) -> dict:
    x = np.column_stack([np.ones(len(d)), d[INPUTS].to_numpy(float)])
    y, g = d["log_ecoli"].to_numpy(float), d["bw_id"].to_numpy(str)
    best = minimize_scalar(lambda lr: _gls(x, y, g, float(np.exp(lr)))[2], bounds=(-8.0, 4.0), method="bounded")
    r = float(np.exp(best.x))
    beta, s2, _ = _gls(x, y, g, r)
    return {"intercept": float(beta[0]), "coef": dict(zip(INPUTS, map(float, beta[1:]), strict=True)),
            "sigma": float(np.sqrt(s2)), "tau": float(np.sqrt(r * s2)), "rows": int(len(d)), "points": int(len(set(g)))}


def fixed(model: dict, d: pd.DataFrame) -> np.ndarray:
    return model["intercept"] + d[INPUTS].to_numpy(float) @ np.array([model["coef"][c] for c in INPUTS])


def ranges(d: pd.DataFrame, mu: np.ndarray, half: np.ndarray | float) -> pd.DataFrame:
    out = d.copy()
    out["mu_log10"], out["low_log10"], out["high_log10"] = mu, mu - half, mu + half
    out["inside"] = rd.inside(out)
    out["above"] = (~out["inside"]) & (out["log_ecoli"] > out["high_log10"])
    out["below"] = (~out["inside"]) & (out["log_ecoli"] < out["low_log10"])
    return out


def leave_system_out(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """L1 and L2 ranges for every sample from 2017, each from a fit that never saw its river system."""
    early, late = d[d["season"] <= SPLIT], d[d["season"] > SPLIT]
    l1, l2, fits = [], [], []
    for s in sorted(late["system"].unique()):
        m = fit(early[early["system"] != s])
        fits.append({"system": s, **m})
        t2, s2 = m["tau"] ** 2, m["sigma"] ** 2
        x = late[late["system"] == s]
        l1.append(ranges(x, fixed(m, x), Z * np.sqrt(t2 + s2)))
        own = early[early["system"] == s]
        for p, xp in x.groupby("bw_id"):
            e = own[own["bw_id"] == p]
            if len(e) < MIN_EARLY:
                continue
            n = len(e)
            level = (t2 / (t2 + s2 / n)) * float((e["log_ecoli"] - fixed(m, e)).mean())
            l2.append(ranges(xp, fixed(m, xp) + level, Z * np.sqrt(t2 * s2 / (n * t2 + s2) + s2)))
    return pd.concat(l1), pd.concat(l2) if l2 else l1[0].iloc[:0], fits


def summary(x: pd.DataFrame) -> dict:
    cover, above, below = (float(x[c].mean()) for c in ("inside", "above", "below"))
    draws = rd.system_season_draws(x, lambda b: float(b["inside"].mean()))
    by_point = x.groupby("bw_id").agg(level=("log_ecoli", "mean"), said=("mu_log10", "mean"), n=("inside", "size"))
    by_point = by_point[by_point["n"] >= 15]
    return {"rows": int(len(x)), "points": int(x["bw_id"].nunique()), "systems": int(x["system"].nunique()),
            "coverage": round(cover, 4), "coverage_ci95": [round(float(v), 4) for v in np.nanpercentile(draws, [2.5, 97.5])],
            "above": round(above, 4), "below": round(below, 4),
            "pass": bool(COVER[0] <= cover <= COVER[1] and max(above, below) <= MAX_TAIL),
            "median_half_width_log10": round(float((x["high_log10"] - x["mu_log10"]).median()), 4),
            "rho_within_point": round(rd.rho_points(x, "mu_log10"), 4),
            "level_correlation_across_points": round(float(by_point["level"].corr(by_point["said"], method="spearman")), 4),
            "by_band": {b: {"rows": int(len(v)), "coverage": round(float(v["inside"].mean()), 4),
                            "above": round(float(v["above"].mean()), 4)} for b, v in x.groupby("band")}}


def main(argv: list[str]) -> None:
    held_p, sys_p, cand_p, out = (Path(a) for a in argv[:4])
    d = with_place_inputs(pd.read_parquet(held_p), pd.read_csv(sys_p))
    cand = json.loads(cand_p.read_text())
    l1, l2, fits = leave_system_out(d)
    late = d[d["season"] > SPLIT]
    base = ranges(late, fc.predict(cand, late)["mu_log10"].to_numpy(), Z * cand["sd_log10"])
    res = {"form": "river-level-v1", "evidence": "development (rows read on 16 November 2026)",
           "L1_no_samples": summary(l1), "L2_earlier_samples": summary(l2),
           "river_range_v0e_same_rows": summary(base),
           "river_range_v0e_on_L2_rows": summary(base.loc[base.index.intersection(l2.index)]),
           "fits": {k: [round(float(np.percentile([f[k] for f in fits], q)), 4) for q in (0, 50, 100)] for k in ("tau", "sigma")},
           "coef_median": {c: round(float(np.median([f["coef"][c] for f in fits])), 4) for c in INPUTS}}
    final = fit(d[d["season"] <= SPLIT])
    res["fit_all_systems_to_2016"] = final
    if len(argv) > 4:
        b = pd.read_parquet(argv[4]).reset_index(drop=True)
        b["system"], b["band"] = b["bw_id"], "bathing"
        if "ecoli_qual" not in b:
            b["ecoli_qual"] = "="
        mu = fc.predict(cand, b)["mu_log10"].to_numpy()
        res["bathing_rivers_reported"] = {"note": "seen bathing-water river rows; no km of channel, so the level form "
                                                  "is not applied; v0e range only", **{k: v for k, v in summary(
                                                      ranges(b, mu, Z * cand["sd_log10"])).items() if k in ("rows", "coverage", "above", "below")}}
    res["outcome"] = f"L1 {'passes' if res['L1_no_samples']['pass'] else 'fails'}, L2 {'passes' if res['L2_earlier_samples']['pass'] else 'fails'}"
    print(json.dumps(res, indent=1))
    commit = subprocess.run(["git", "-C", str(Path(__file__).resolve().parents[2]), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps({"run_at": stamp, "commit": commit, "rows_sha256": rd.sha(held_p), **res}, indent=1) + "\n")
    with (out / "runs.jsonl").open("a") as f:
        f.write(json.dumps({"run_at": stamp, "commit": commit, "outcome": res["outcome"],
                            "L1": res["L1_no_samples"]["coverage"], "L2": res["L2_earlier_samples"]["coverage"]}) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
