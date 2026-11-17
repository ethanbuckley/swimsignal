"""The read of docs/RIVER-UNSEEN-PROTOCOL-2026-11.md: the frozen candidate on river samples it never saw.

    python scripts/river_unseen/read.py <held-out rows> <seen river rows on the same rain> \\
        docs/river-unseen/river_range_v0e.json <production ecoli_model.json> docs/river-unseen [--dev]

Rows come from build_rows.py. Without --dev this is THE read: it refuses unless the candidate file is committed and
unchanged and its SHA-256 is named in the statement, it writes docs/river-unseen/result.json, and it appends a line
to docs/river-unseen/reads.jsonl whatever the result. With --dev it scores rows already seen (a test of the script),
writes nothing under docs/ and logs nothing.

Deciding (statement and amendment 1): the mean over points of the within-point Spearman correlation between the
likely reading and the measured log10 count, with a 95% interval from 2,000 resamples of river-system seasons, must
lie wholly above 0.15; and the share of samples inside the 8-in-10 range must be between 72% and 88%."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import freeze_candidate as fc  # noqa: E402

LINE, RHO_BAR, COVER = np.log10(900.0), 0.15, (0.72, 0.88)
MIN_ROWS, DRAWS, SEED, WEAK_LIMIT_SHARE = 15, 2000, 20261115, 0.25
STATEMENT = REPO / "docs" / "RIVER-UNSEEN-PROTOCOL-2026-11.md"


def rho_points(d: pd.DataFrame, col: str, point: str = "bw_id") -> float:
    """Mean over points with MIN_ROWS or more rows of the Spearman correlation of `col` with the log10 count."""
    r = [spearmanr(g[col], g["log_ecoli"])[0] for _, g in d.groupby(point) if len(g) >= MIN_ROWS and g[col].nunique() > 1
         and g["log_ecoli"].nunique() > 1]
    return float(np.mean(r)) if r else float("nan")


def system_season_draws(d: pd.DataFrame, fn, draws: int = DRAWS, seed: int = SEED) -> np.ndarray:
    """`fn` on resamples of system-seasons drawn with replacement; one drawn twice counts as two sets of points."""
    rng = np.random.default_rng(seed)
    blocks = [g for _, g in d.groupby(["system", "season"])]
    out = []
    for _ in range(draws):
        pick = rng.integers(0, len(blocks), len(blocks))
        out.append(fn(pd.concat([blocks[b].assign(_p=blocks[b]["bw_id"] + f"#{i}") for i, b in enumerate(pick)])))
    return np.asarray(out, dtype=float)


def interval(d: pd.DataFrame, fn_full, fn_draw) -> dict:
    v = system_season_draws(d, fn_draw)
    return {"value": round(float(fn_full(d)), 4), "ci95": [round(float(x), 4) for x in np.nanpercentile(v, [2.5, 97.5])]}


def inside(d: pd.DataFrame) -> pd.Series:
    """Amendment 1, section 5: a "<" result is inside when the range's lower end is at or below the limit, a ">"
    result when its upper end is at or above it, any other when it lies between the ends."""
    y, q = d["log_ecoli"], d["ecoli_qual"]
    plain = (y >= d["low_log10"]) & (y <= d["high_log10"])
    return pd.Series(np.where(q == "<", d["low_log10"] <= y, np.where(q == ">", d["high_log10"] >= y, plain)), index=d.index)


def brier(p, y) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def production_deployed(model: dict, d: pd.DataFrame) -> np.ndarray:
    """Production's chance over 900 as deployed, for a river (lake terms zero), without soil moisture."""
    z = model["intercept"]
    for f, c in model["coef"].items():
        x = d[f].to_numpy(float) if f in d else np.zeros(len(d))
        z = z + c * (x - model["mean"][f]) / model["scale"][f]
    return 1.0 / (1.0 + np.exp(-z))


def references(seen: pd.DataFrame, held: pd.DataFrame, prod: dict) -> pd.DataFrame:
    """The chance over 900 from each reference, for the held-out rows; all fitted on the seen rows only."""
    mu, sd = seen[fc.FEATURES].mean(), seen[fc.FEATURES].std()
    refit = LogisticRegression(C=1e6, max_iter=5000).fit((seen[fc.FEATURES] - mu) / sd, seen["over"])
    month = seen.groupby("month")["over"].mean()
    wet = seen["rain_48h"] > 10
    out = pd.DataFrame(index=held.index)
    out["production_refit"] = refit.predict_proba((held[fc.FEATURES] - mu) / sd)[:, 1]
    out["production_deployed"] = production_deployed(prod, held)
    out["month_rate"] = held["month"].map(month).fillna(seen["over"].mean()).to_numpy()
    out["rain_rule"] = np.where(held["rain_48h"] > 10, seen.loc[wet, "over"].mean(), seen.loc[~wet, "over"].mean())
    return out


def score(held: pd.DataFrame, seen: pd.DataFrame, cand: dict, prod: dict) -> dict:
    d = pd.concat([held.reset_index(drop=True), fc.predict(cand, held).reset_index(drop=True)], axis=1)
    d["p_candidate"] = 1.0 - norm.cdf((LINE - d["mu_log10"]) / cand["sd_log10"])
    d = pd.concat([d, references(seen, d, prod)], axis=1)
    d["inside"] = inside(d)
    primary = interval(d, lambda x: rho_points(x, "mu_log10"), lambda x: rho_points(x, "mu_log10", "_p"))
    cover = float(d["inside"].mean())
    at_limit = float(d["ecoli_qual"].isin(["<", ">"]).mean())
    res = {"rows": int(len(d)), "points": int(d["bw_id"].nunique()), "systems": int(d["system"].nunique()),
           "seasons": sorted(int(s) for s in d["season"].unique()), "over_900": int(d["over"].sum()),
           "primary_rho": primary, "primary_pass": bool(primary["ci95"][0] > RHO_BAR),
           "range_coverage": round(cover, 4), "range_pass": bool(COVER[0] <= cover <= COVER[1]),
           "share_at_a_lab_limit": round(at_limit, 4), "range_check_weak": bool(at_limit > WEAK_LIMIT_SHARE)}
    rep = {"rho_by_figure": {c: round(rho_points(d, c), 4) for c in ("mu_log10", "production_refit", "production_deployed",
                                                                    "lrain48")},
           "candidate_rho_minus_production_refit": interval(
               d, lambda x: rho_points(x, "mu_log10") - rho_points(x, "production_refit"),
               lambda x: rho_points(x, "mu_log10", "_p") - rho_points(x, "production_refit", "_p")),
           "brier_over_900": {c: round(brier(d[c], d["over"]), 4) for c in ("p_candidate", "production_refit",
                                                                           "production_deployed", "month_rate", "rain_rule")},
           "exposure_quantiles": {k: [round(float(v), 4) for v in x["risk_model"].quantile([0.1, 0.5, 0.9])]
                                  for k, x in (("seen", seen), ("held_out", d))}}
    subsets = {"seasons_to_2016": d[d["season"] <= 2016], "seasons_from_2017": d[d["season"] >= 2017]}
    subsets.update({f"band_{b}": x for b, x in d.groupby("band")})
    if "purpose" in d:
        subsets.update({f"purpose_{p}": x for p, x in d.groupby("purpose")})
    rep["subsets"] = {k: {"rows": int(len(x)), "points": int(x["bw_id"].nunique()),
                          "rho": round(rho_points(x, "mu_log10"), 4), "coverage": round(float(x["inside"].mean()), 4),
                          "over_900": int(x["over"].sum())} for k, x in subsets.items() if len(x)}
    res["reported"] = rep
    return res


def outcome(res: dict) -> str:
    if res["primary_pass"] and res["range_pass"]:
        return "both pass"
    if res["primary_pass"]:
        return "order passes, range fails"
    return "order fails"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_frozen(cand_path: Path) -> None:
    rel = cand_path.resolve().relative_to(REPO)
    if subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", str(rel), "docs/RIVER-UNSEEN-PROTOCOL-2026-11.md",
                       "scripts/river_unseen"], capture_output=True, text=True).stdout.strip():
        raise SystemExit("the candidate, the statement or the scripts have uncommitted changes: commit them first")
    if sha(cand_path)[:8] not in STATEMENT.read_text():
        raise SystemExit("the candidate's SHA-256 is not named in the statement")


def main(argv: list[str]) -> None:
    dev = "--dev" in argv
    held_p, seen_p, cand_p, prod_p, out = (Path(a) for a in argv[:5])
    held, seen = pd.read_parquet(held_p), pd.read_parquet(seen_p)
    cand, prod = json.loads(cand_p.read_text()), json.loads(prod_p.read_text())
    if dev:
        for c, v in (("system", held["bw_id"]), ("band", "seen"), ("ecoli_qual", "=")):
            if c not in held:
                held[c] = v
    else:
        check_frozen(cand_p)
    res = score(held, seen, cand, prod)
    res["outcome"] = outcome(res)
    res["inputs"] = {"held_out_rows": sha(held_p), "seen_rows": sha(seen_p), "candidate": sha(cand_p), "production": sha(prod_p)}
    print(json.dumps(res, indent=1))
    if dev:
        return
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    (out / "result.json").write_text(json.dumps({"read_at": stamp, "commit": commit, **res}, indent=1) + "\n")
    with (out / "reads.jsonl").open("a") as f:
        f.write(json.dumps({"read_at": stamp, "commit": commit, "candidate": cand["name"], "outcome": res["outcome"],
                            "rows": res["rows"], "primary_rho": res["primary_rho"], "range_coverage": res["range_coverage"],
                            "inputs": res["inputs"]}) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
