"""How many of a place's own samples give it a range that beats the no-sample range
(docs/PLACE-LEVEL-READ-0-2026-11.md, issue #716). Development: every row was read on 16 November 2026.

    python scripts/river_unseen/place_level_read0.py <held-out rows> docs/river-unseen/systems.csv \\
        docs/river-level/result.json <seen bathing river rows> docs/river-level/bathing_sites.csv \\
        docs/river-level/river_level_v1.json docs/river-unseen/river_range_v0e.json docs/place-level

`river-level-v1` is used unchanged (level_candidate.fit, fixed, ranges). At each place with OWN + MIN_SCORED samples
or more from 2017, in time order: the first OWN are the place's own samples, the rest are scored. For each n, the
place's level is the mean residual of the last n own samples, shrunk as in L2; n = 0 is L1. Every n is scored on the
same samples.

Set A (decides): archive points, each from a fit that never saw its river system (the candidate's own folds).
Set B (reported): bathing-water rivers, from the frozen fit.

Run once. It refuses to run when <out>/result.json exists, or when the statement or these scripts are not committed.
It writes <out>/result.json and appends to <out>/runs.jsonl whatever it shows."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import freeze_candidate as fc  # noqa: E402
import level_candidate as lc  # noqa: E402
import read as rd  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
STATEMENT = "docs/PLACE-LEVEL-READ-0-2026-11.md"
OWN, MIN_SCORED = 20, 10
DRAWS = rd.DRAWS          # the statement fixes 2,000; tests lower it
NS = (3, 5, 8, 12, 20)
EXPECTED = {"A": (32, 1673), "B": (14, 548)}   # places and scored samples, as the statement counted them
GAPS = {"same season": (0, 0), "next season": (1, 1), "two or more later": (2, 99)}


def split_places(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each kept place's own samples (its first OWN in time order) and its scored samples (the rest)."""
    own, scored = [], []
    for _, x in d.groupby("bw_id"):
        if len(x) < OWN + MIN_SCORED:
            continue
        x = x.sort_values("sample_time", kind="stable")
        own.append(x.iloc[:OWN])
        scored.append(x.iloc[OWN:].assign(seasons_after=x.iloc[OWN:]["season"] - int(x.iloc[OWN - 1]["season"])))
    return pd.concat(own), pd.concat(scored)


def level_ranges(scored: pd.DataFrame, own: pd.DataFrame, m: dict) -> pd.DataFrame:
    """One place's scored samples with a range whose level comes from `own` (no rows: no level, the L1 width)."""
    t2, s2, n = m["tau"] ** 2, m["sigma"] ** 2, len(own)
    if n == 0:
        level, sd = 0.0, np.sqrt(t2 + s2)
    else:
        level = (t2 / (t2 + s2 / n)) * float((own["log_ecoli"] - lc.fixed(m, own)).mean())
        sd = np.sqrt(t2 * s2 / (n * t2 + s2) + s2)
    return lc.ranges(scored, lc.fixed(m, scored) + level, lc.Z * sd).assign(sd_log10=sd, level_log10=level)


def running_ranges(scored: pd.DataFrame, own: pd.DataFrame, m: dict) -> pd.DataFrame:
    """Each scored sample with a level from the place's own samples and every scored sample before it."""
    out = [level_ranges(scored.iloc[[i]], pd.concat([own, scored.iloc[:i]]), m) for i in range(len(scored))]
    return pd.concat(out)


def all_ranges(own: pd.DataFrame, scored: pd.DataFrame, model_for) -> dict[str, pd.DataFrame]:
    """Ranges on the same scored samples for n = 0, the last n and the first n of the own samples, and a running level."""
    got: dict[str, list] = {}
    for p, x in scored.groupby("bw_id"):
        o, m = own[own["bw_id"] == p], model_for(x)
        got.setdefault("n0", []).append(level_ranges(x, o.iloc[:0], m))
        for n in NS:
            got.setdefault(f"last{n}", []).append(level_ranges(x, o.iloc[OWN - n:], m))
            got.setdefault(f"first{n}", []).append(level_ranges(x, o.iloc[:n], m))
        got.setdefault("running", []).append(running_ranges(x, o, m))
    return {k: pd.concat(v) for k, v in got.items()}


def log_density(x: pd.DataFrame) -> pd.Series:
    return pd.Series(norm.logpdf(x["log_ecoli"], x["mu_log10"], x["sd_log10"]), index=x.index)


def gain_over(x: pd.DataFrame, base: pd.DataFrame) -> dict:
    g = x.assign(gain=log_density(x) - log_density(base.loc[x.index]))
    draws = rd.system_season_draws(g, lambda b: float(b["gain"].mean()), draws=DRAWS)
    return {"value": round(float(g["gain"].mean()), 4), "ci95": [round(float(v), 4) for v in np.nanpercentile(draws, [2.5, 97.5])]}


def one(x: pd.DataFrame, base: pd.DataFrame) -> dict:
    keep = ("rows", "points", "systems", "coverage", "coverage_ci95", "above", "below", "median_half_width_log10",
            "level_correlation_across_points", "by_band")
    s = lc.summary(x)
    gain = gain_over(x, base)
    by_gap = {k: {"rows": int(len(v)), "coverage": round(float(v["inside"].mean()), 4), "above": round(float(v["above"].mean()), 4),
                  "below": round(float(v["below"].mean()), 4)}
              for k, (lo, hi) in GAPS.items() if len(v := x[x["seasons_after"].between(lo, hi)])}
    return {**{k: s[k] for k in keep}, "rule_1_range": bool(s["pass"]), "log_density_gain_over_n0": gain,
            "rule_2_gain": bool(gain["ci95"][0] > 0), "pass": bool(s["pass"] and gain["ci95"][0] > 0), "by_seasons_after": by_gap}


def score(own: pd.DataFrame, scored: pd.DataFrame, model_for) -> dict:
    r = all_ranges(own, scored, model_for)
    base = r["n0"]
    res = {"places": int(scored["bw_id"].nunique()), "systems": int(scored["system"].nunique()), "scored": int(len(scored)),
           "n0": {k: v for k, v in one(base, base).items() if k not in ("log_density_gain_over_n0", "rule_2_gain", "pass")},
           "last_n": {str(n): one(r[f"last{n}"], base) for n in NS},
           "first_n_reported": {str(n): one(r[f"first{n}"], base) for n in NS},
           "running_reported": one(r["running"], base)}
    passed = [n for n in NS if res["last_n"][str(n)]["pass"]]
    res["answer"] = f"n = {passed[0]}" if passed else f"not shown by {NS[-1]}"
    return res


def system_fits(d: pd.DataFrame) -> dict[str, dict]:
    """The candidate's folds: for each river system with samples from 2017, a fit on the other systems to 2016."""
    early, late = d[d["season"] <= lc.SPLIT], d[d["season"] > lc.SPLIT]
    return {s: lc.fit(early[early["system"] != s]) for s in sorted(late["system"].unique())}


def check_fits(fits: dict[str, dict], record: dict) -> None:
    for k in ("tau", "sigma"):
        mine = [round(float(np.percentile([f[k] for f in fits.values()], q)), 4) for q in (0, 50, 100)]
        if mine != record["fits"][k]:
            raise SystemExit(f"the folds' {k} {mine} do not match the candidate's record {record['fits'][k]}: not scored")


def check_counts(name: str, scored: pd.DataFrame) -> None:
    got = (int(scored["bw_id"].nunique()), int(len(scored)))
    if got != EXPECTED[name]:
        raise SystemExit(f"set {name} has {got} places and scored samples, not the statement's {EXPECTED[name]}: not scored")


def check_committed(out: Path) -> None:
    if (out / "result.json").exists():
        raise SystemExit("this read has run: a second run needs an amendment to the statement first")
    if subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", STATEMENT, "scripts/river_unseen"],
                      capture_output=True, text=True).stdout.strip():
        raise SystemExit("the statement or the scripts have uncommitted changes: commit them first")


def main(argv: list[str]) -> None:
    held_p, sys_p, record_p, seen_p, sites_p, model_p, cand_p, out = (Path(a) for a in argv[:8])
    check_committed(out)
    hashes = {p.name: rd.sha(p) for p in (held_p, seen_p, model_p)}
    d = lc.with_place_inputs(pd.read_parquet(held_p), pd.read_csv(sys_p))
    fits = system_fits(d)
    check_fits(fits, json.loads(record_p.read_text()))
    own, scored = split_places(d[d["season"] > lc.SPLIT])
    check_counts("A", scored)
    a = score(own, scored, lambda x: fits[x["system"].iloc[0]])

    b = pd.read_parquet(seen_p)
    if "ecoli_qual" not in b or b["ecoli_qual"].isna().any():
        b["ecoli_qual"] = b.get("ecoli_qual", pd.Series("=", index=b.index)).fillna("=")
    b = lc.with_place_inputs(b, pd.read_csv(sites_p)).assign(system=lambda t: t["bw_id"], band="bathing")
    frozen, cand = json.loads(model_p.read_text()), json.loads(cand_p.read_text())
    own_b, scored_b = split_places(b)
    check_counts("B", scored_b)
    set_b = score(own_b, scored_b, lambda x: frozen)
    old = lc.ranges(scored_b, fc.predict(cand, scored_b)["mu_log10"].to_numpy(), lc.Z * cand["sd_log10"])
    set_b["river_range_v0e_same_rows_in_sample"] = {k: v for k, v in lc.summary(old).items() if k in ("rows", "coverage", "above", "below")}

    res = {"read": "PLACE-LEVEL read 0", "evidence": "development (every row was read on 16 November 2026)",
           "own_samples": OWN, "set_A_archive_points": a, "set_B_bathing_rivers_reported": set_b, "outcome": a["answer"]}
    print(json.dumps(res, indent=1))
    assert hashes == {p.name: rd.sha(p) for p in (held_p, seen_p, model_p)}, "an input changed during the run"
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps({"run_at": stamp, "commit": commit, "inputs_sha256": hashes, **res}, indent=1) + "\n")
    with (out / "runs.jsonl").open("a") as f:
        f.write(json.dumps({"run_at": stamp, "commit": commit, "outcome": res["outcome"],
                            "set_A_scored": a["scored"], "set_B_scored": set_b["scored"]}) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
