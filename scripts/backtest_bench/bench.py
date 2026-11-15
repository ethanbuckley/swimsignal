"""Backtest bench, scoring (docs/BACKTEST-BENCH-2026-11.md). Score an E. coli candidate on frozen rows.

    uv run python scripts/backtest_bench/bench.py verify
    uv run python scripts/backtest_bench/bench.py dev   --candidate scripts/backtest_bench/candidates/production_refit.py
    uv run python scripts/backtest_bench/bench.py final --candidate <committed .py> --statement <committed .md>

`dev` reads the seen rows only (2023-26, used to fit production) and scores by leave one season out. Run it as often
as you like: it is development evidence and never touches a held-out outcome.

`final` fits on every seen row and scores once on the held-out rows (2012-22 lakes, 2021-22 rivers), which no
production model was fitted on. It refuses to run unless the candidate and its statement are committed and unchanged
in the working tree, and it appends one line to the ledger (docs/backtest-bench/ledger.jsonl) for every run, pass or
fail, so repeated reads of the same rows are visible. Commit the ledger line and the result file it writes.

A candidate is a .py file with two functions:

    def fit(rows: pd.DataFrame) -> object
    def predict(model, rows: pd.DataFrame) -> np.ndarray | dict

`predict` returns P(E. coli > 900) for each row, or a dict with "p900" and optionally "p500" (P over 500) and "rank"
(any score that orders a site's samples, e.g. a predicted median log10 count). The rows' columns are in the record.
Outcome columns (ecoli, log_ecoli, over, ecoli_qual) are removed from the rows `predict` sees.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))


def _default_store() -> Path:
    """swimsignal-private/bench/ecoli-v1 beside the main checkout (found through git, so a worktree finds it too)."""
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=REPO,
                                capture_output=True, text=True, check=True).stdout.strip()
        base = Path(common).parent.parent
    except (OSError, subprocess.CalledProcessError):
        base = REPO.parent
    return base / "swimsignal-private" / "bench" / "ecoli-v1"


STORE = Path(os.environ["BENCH_STORE"]) if os.environ.get("BENCH_STORE") else _default_store()
MANIFEST = REPO / "docs" / "backtest-bench" / "ecoli-v1-manifest.json"   # committed copy: the hashes to check
LEDGER = REPO / "docs" / "backtest-bench" / "ledger.jsonl"
RESULTS = REPO / "docs" / "backtest-bench" / "results"
OUTCOMES = ["ecoli", "log_ecoli", "over", "ecoli_qual", "ie", "ie_qual", "prev_over_3d_raw"]
SEED, DRAWS = 20261115, 2000
MIN_SITE_ROWS = 15   # a site's rank correlation counts with at least this many rows (LAKE-LINE-2012-22-CHECK's rule)
SHRINK_M = 10        # site rate shrunk toward the pooled rate with m = 10 pseudo-rows (LAKE-OWN-RATE-TEST's rule)


# ------------------------------------------------------------------ rows
def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(part: str) -> pd.DataFrame:
    m = json.loads(MANIFEST.read_text())
    p = STORE / f"{part}.parquet"
    if not p.exists():
        raise SystemExit(f"no {p}: build the rows with stage.py and freeze them to {STORE} (or set BENCH_STORE)")
    if sha(p) != m["files"][part]["sha256"]:
        raise SystemExit(f"{p} does not match the committed manifest: these are not the frozen rows")
    d = pd.read_parquet(p)
    d["cluster"] = d["name"].map(water_body)
    return d


def water_body(name: str) -> str:
    """Bathing waters on one water body share weather and water, so they resample together: Windermere's four and
    Hampstead Heath's three ponds are one cluster each."""
    for k in ("Windermere", "Hampstead Heath"):
        if name.startswith(k):
            return k
    return name


def blind(rows: pd.DataFrame) -> pd.DataFrame:
    return rows.drop(columns=[c for c in OUTCOMES if c in rows], errors="ignore")


# ------------------------------------------------------------------ references
def production_deployed(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """The E. coli models as deployed (no refit): the river model with soil moisture where `sm` is known, the base
    model elsewhere, as forecast.py chooses."""
    from dipcast.model.ecoli import FEATURES, SM_MODEL_PATH, EcoliModel
    paths = {n: REPO / "data" / "processed" / n for n in ("ecoli_model.json", SM_MODEL_PATH.name)}
    frozen = json.loads(MANIFEST.read_text())["inputs"]
    for n, p in paths.items():
        if sha(p) != frozen.get(n):
            print(f"note: {n} has changed since the rows were frozen; production_deployed is today's model",
                  file=sys.stderr)
    cal = REPO / "data" / "processed" / "lead_calibration.json"
    if sha(cal) != frozen.get("lead_calibration.json"):
        print("warning: lead_calibration.json has changed since the rows were frozen. The rows' exposure was built "
              "with the old map: rebuild them (stage.py, a new row_version) before comparing with production",
              file=sys.stderr)
    base = EcoliModel.from_json(paths["ecoli_model.json"])
    sm_m = EcoliModel.from_json(paths[SM_MODEL_PATH.name])
    p = base.predict(test[FEATURES])
    riv = (test["kind"] == "river").to_numpy() & test["sm"].notna().to_numpy()
    if riv.any():
        X = test.loc[riv, FEATURES].copy()
        lo, hi = sm_m.meta["sm_range"]
        X["sm"] = np.clip(test.loc[riv, "sm"].to_numpy(dtype=float), lo, hi)
        p[riv] = sm_m.predict(X)   # with_sm's clip, per row (one sample, one issue)
    return {"p900": p}


def production_refit(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """Production's form (ecoli.FEATURES, logistic, C = 1) refitted on the same training rows a candidate gets."""
    from dipcast.model.ecoli import FEATURES, fit
    return {"p900": fit(train, train["over"].to_numpy(), FEATURES).predict(test[FEATURES])}


def month_rate(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    out = {}
    for thr, key in ((900, "p900"), (500, "p500")):
        y = (train["ecoli"] > thr).astype(float)
        pooled = float(y.mean())
        rate = y.groupby(train["month"]).mean()
        out[key] = test["month"].map(rate).fillna(pooled).to_numpy(dtype=float)
    return out


def site_rate(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """The site's own share in the training rows, shrunk toward the pooled share (m = 10); pooled where unseen."""
    out = {}
    for thr, key in ((900, "p900"), (500, "p500")):
        y = (train["ecoli"] > thr).astype(float)
        pooled = float(y.mean())
        g = y.groupby(train["bw_id"]).agg(["sum", "count"])
        rate = (g["sum"] + SHRINK_M * pooled) / (g["count"] + SHRINK_M)
        out[key] = test["bw_id"].map(rate).fillna(pooled).to_numpy(dtype=float)
    return out


REFERENCES = {"production_deployed": production_deployed, "production_refit": production_refit,
              "month_rate": month_rate, "site_rate": site_rate}


# ------------------------------------------------------------------ candidate
def load_candidate(path: Path):
    spec = importlib.util.spec_from_file_location("bench_candidate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for f in ("fit", "predict"):
        if not hasattr(mod, f):
            raise SystemExit(f"{path} has no {f}()")
    return mod


def run_candidate(mod, train: pd.DataFrame, test: pd.DataFrame) -> dict:
    out = mod.predict(mod.fit(train.copy()), blind(test).copy())
    out = {"p900": out} if not isinstance(out, dict) else out
    for k, v in out.items():
        v = np.asarray(v, dtype=float)
        if v.shape != (len(test),):
            raise SystemExit(f"candidate's {k} has shape {v.shape}, expected ({len(test)},)")
        if k.startswith("p") and (np.nanmin(v) < 0 or np.nanmax(v) > 1):
            raise SystemExit(f"candidate's {k} is outside [0, 1]")
        if np.isnan(v).any():
            raise SystemExit(f"candidate's {k} has {int(np.isnan(v).sum())} NaN: give every row a figure")
        out[k] = v
    return out


# ------------------------------------------------------------------ scores
def brier(y, p):
    return float(np.mean((p - y) ** 2))


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    """Mann-Whitney AUC with ties counted half (the same value as sklearn's roc_auc_score)."""
    r = rankdata(p)
    n1 = y.sum()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1)))


def site_auc(d: pd.DataFrame, y: np.ndarray, p: np.ndarray) -> float:
    """Mean over sites with both classes of the within-site AUC: does the figure order a site's own days."""
    v = [_auc(y[idx], p[idx]) for idx in d.groupby("bw_id").indices.values() if 0 < y[idx].sum() < len(idx)]
    return float(np.mean(v)) if v else float("nan")


def site_rho(d: pd.DataFrame, s: np.ndarray) -> float:
    """Mean over sites (at least MIN_SITE_ROWS rows) of the Spearman correlation between the figure and the measured
    log10 count, as LAKE-LINE-2012-22-CHECK computes it."""
    le = d["log_ecoli"].to_numpy()
    v = []
    for idx in d.groupby("bw_id").indices.values():
        if len(idx) >= MIN_SITE_ROWS and np.unique(s[idx]).size > 1 and np.unique(le[idx]).size > 1:
            v.append(spearmanr(s[idx], le[idx]).statistic)
    return float(np.mean(v)) if v else float("nan")


def metrics(d: pd.DataFrame, f: dict) -> dict:
    y9 = (d["ecoli"] > 900).to_numpy(dtype=float)
    y5 = (d["ecoli"] > 500).to_numpy(dtype=float)
    out = {"brier900": brier(y9, f["p900"]), "auc900_site": site_auc(d, y9, f["p900"]),
           "rho_site": site_rho(d, f.get("rank", f["p900"]))}
    if "p500" in f:
        out["brier500"] = brier(y5, f["p500"])
    return out


def boot(d: pd.DataFrame, figs: dict[str, dict], pairs: list[tuple[str, str]], by_season: bool = False) -> dict:
    """95% intervals from resampling clusters with replacement, the same draws for every figure, for each metric and
    each paired difference a - b. Clusters are water bodies; with by_season, a water body in one season (as
    LAKE-LINE-2012-22-CHECK resampled site x season, but with a water body's sites together). A water body drawn twice
    counts as two sites; a water-body season drawn twice adds its rows twice to the same site (that check's rule)."""
    clusters = (d["cluster"] + "|" + d["season"].astype(str)).to_numpy() if by_season else d["cluster"].to_numpy()
    keys = np.unique(clusters)
    idx_of = {k: np.flatnonzero(clusters == k) for k in keys}
    rng = np.random.default_rng(SEED)
    draws: dict[str, list] = {}
    for _ in range(DRAWS):
        pick = rng.choice(keys, size=len(keys), replace=True)
        ii = np.concatenate([idx_of[k] for k in pick])
        dd = d.iloc[ii].reset_index(drop=True)
        if not by_season:
            dd["bw_id"] = dd["bw_id"] + "#" + np.repeat(np.arange(len(pick)),
                                                        [len(idx_of[k]) for k in pick]).astype(str)
        m = {n: metrics(dd, {k: v[ii] for k, v in f.items()}) for n, f in figs.items()}
        for n, mm in m.items():
            for k, v in mm.items():
                draws.setdefault(f"{n}.{k}", []).append(v)
        for a, b in pairs:
            for k in m[a]:
                if k in m[b]:
                    draws.setdefault(f"{a}-{b}.{k}", []).append(m[a][k] - m[b][k])
    return {k: [round(float(x), 5) for x in np.nanpercentile(v, [2.5, 97.5])] for k, v in draws.items()}


def report(d: pd.DataFrame, figs: dict[str, dict], cand: str | None) -> dict:
    pairs = [(cand, r) for r in REFERENCES] if cand else [("production_refit", "month_rate"),
                                                           ("production_deployed", "month_rate")]
    point = {n: {k: round(v, 5) for k, v in metrics(d, f).items()} for n, f in figs.items()}
    ci, cs = boot(d, figs, pairs), boot(d, figs, pairs, by_season=True)
    diffs = {f"{a}-{b}": {k: {"mean": round(point[a][k] - point[b][k], 5), "ci95": ci.get(f"{a}-{b}.{k}"),
                              "ci95_season": cs.get(f"{a}-{b}.{k}")}
                          for k in point[a] if k in point[b]} for a, b in pairs}
    return {"rows": int(len(d)), "sites": int(d["bw_id"].nunique()), "clusters": int(d["cluster"].nunique()),
            "season_clusters": int((d["cluster"] + "|" + d["season"].astype(str)).nunique()),
            "over_900": int((d["ecoli"] > 900).sum()), "over_500": int((d["ecoli"] > 500).sum()),
            "scores": {n: {k: {"value": v, "ci95": ci.get(f"{n}.{k}"), "ci95_season": cs.get(f"{n}.{k}")}
                           for k, v in s.items()} for n, s in point.items()},
            "differences": diffs}


def subsets(d: pd.DataFrame) -> dict[str, np.ndarray]:
    """The subsets every read reports. Seasons split at 2017 because the archive rain's source most likely changes
    there (docs/ERA5-LAND-BULK-RAIN-2026-11.md: IFS from 2017, inferred; reanalysis before)."""
    lake = (d["kind"] == "lake").to_numpy()
    fresh = d["prior_reads"].isna().to_numpy() if "prior_reads" in d else np.ones(len(d), bool)
    return {"all": np.ones(len(d), bool), "lake": lake, "river": (d["kind"] == "river").to_numpy(),
            "not_read_before": fresh, "lake_not_read_before": lake & fresh,
            "seasons_to_2016": (d["season"] <= 2016).to_numpy(), "seasons_from_2017": (d["season"] >= 2017).to_numpy()}


def score_all(d: pd.DataFrame, figs: dict, cand: str | None) -> dict:
    out = {}
    for name, m in subsets(d).items():
        if m.sum() == 0:
            continue
        dd = d[m].reset_index(drop=True)
        out[name] = report(dd, {n: {k: v[m] for k, v in f.items()} for n, f in figs.items()}, cand)
    return out


# ------------------------------------------------------------------ modes
def dev(cand_path: Path | None) -> dict:
    seen = load("seen")
    mod = load_candidate(cand_path) if cand_path else None
    figs: dict[str, dict] = {n: {} for n in REFERENCES}
    if mod:
        figs["candidate"] = {}
    parts = []
    for y in sorted(seen["season"].unique()):
        tr, te = seen[seen["season"] != y].reset_index(drop=True), seen[seen["season"] == y].reset_index(drop=True)
        parts.append(te)
        for n, f in REFERENCES.items():
            for k, v in f(tr, te).items():
                figs[n].setdefault(k, []).append(v)
        if mod:
            for k, v in run_candidate(mod, tr, te).items():
                figs["candidate"].setdefault(k, []).append(v)
    d = pd.concat(parts, ignore_index=True)
    figs = {n: {k: np.concatenate(v) for k, v in f.items()} for n, f in figs.items()}
    res = {"mode": "dev", "split": "leave one season out, seen rows (2023-26)",
           "note": "development evidence: production was fitted on these rows; production_deployed is in-sample here",
           **score_all(d, figs, "candidate" if mod else None)}
    return res


def committed(path: Path) -> str:
    """The commit that last changed path, if path is tracked and unchanged in the working tree; else exit."""
    rel = str(path.resolve().relative_to(REPO))
    if subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=REPO, capture_output=True).returncode:
        raise SystemExit(f"{rel} is not committed: commit the candidate and its statement before a final read")
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=REPO).returncode:
        raise SystemExit(f"{rel} differs from HEAD: commit it before a final read")
    return subprocess.run(["git", "log", "-1", "--format=%H", "--", rel], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def final(cand_path: Path, statement: Path) -> dict:
    c_commit, s_commit = committed(cand_path), committed(statement)
    seen, held = load("seen"), load("heldout")
    mod = load_candidate(cand_path)
    figs = {n: f(seen, held) for n, f in REFERENCES.items()}
    figs["candidate"] = run_candidate(mod, seen, held)
    reads = [json.loads(x) for x in LEDGER.read_text().splitlines()] if LEDGER.exists() else []
    t = pd.Timestamp.now("UTC")
    res = {"mode": "final", "split": "fit on seen rows (2023-26), scored on held-out rows",
           "candidate": str(cand_path.resolve().relative_to(REPO)), "candidate_commit": c_commit,
           "candidate_sha256": sha(cand_path), "statement": str(statement.resolve().relative_to(REPO)),
           "statement_commit": s_commit, "rows_sha256": json.loads(MANIFEST.read_text())["files"]["heldout"]["sha256"],
           "read_number": len(reads) + 1, "at": t.isoformat(), **score_all(held, figs, "candidate")}
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{cand_path.stem}-{t.strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(res, indent=1))
    a = res["all"]["differences"].get("candidate-production_deployed", {})
    with LEDGER.open("a") as f:
        f.write(json.dumps({"at": res["at"], "read_number": res["read_number"], "candidate": res["candidate"],
                            "candidate_sha256": res["candidate_sha256"], "statement": res["statement"],
                            "rows_sha256": res["rows_sha256"], "result": str(out.relative_to(REPO)),
                            "brier900_vs_deployed": a.get("brier900"), "rho_site_vs_deployed": a.get("rho_site")})
                + "\n")
    print(f"final read #{res['read_number']} on these rows; result {out.relative_to(REPO)}; ledger line added")
    return res


def verify() -> None:
    m = json.loads(MANIFEST.read_text())
    for part, v in m["files"].items():
        p = STORE / f"{part}.parquet"
        ok = p.exists() and sha(p) == v["sha256"]
        print(f"{part}: {'ok' if ok else 'MISMATCH or missing'} ({v['rows']} rows, {v['sites']} sites, "
              f"{v['over']} over 900, seasons {v['seasons'][0]}-{v['seasons'][-1]})")
        if not ok:
            raise SystemExit(1)


def table(res: dict) -> str:
    lines = []
    def iv(v, key):
        return f"[{v[key][0]:+.4f}, {v[key][1]:+.4f}]" if v.get(key) else "[n/a]"

    for sub in ("all", "lake", "river", "not_read_before", "lake_not_read_before", "seasons_to_2016",
                "seasons_from_2017"):
        if sub not in res:
            continue
        r = res[sub]
        lines.append(f"\n{sub}: {r['rows']} rows, {r['sites']} sites, {r['clusters']} water bodies "
                     f"({r['season_clusters']} water-body seasons), {r['over_900']} over 900, {r['over_500']} over 500")
        for n, s in r["scores"].items():
            lines.append(f"  {n:20s} " + "  ".join(f"{k} {v['value']:.4f}" for k, v in s.items()))
        lines.append("  differences: mean [water bodies] [water-body seasons]")
        for n, s in r["differences"].items():
            lines.append(f"  {n:40s} " + "  ".join(
                f"{k} {v['mean']:+.4f} {iv(v, 'ci95')} {iv(v, 'ci95_season')}" for k, v in s.items()))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["verify", "dev", "final"])
    ap.add_argument("--candidate", type=Path)
    ap.add_argument("--statement", type=Path)
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    a = ap.parse_args()
    if a.mode == "verify":
        verify(); return
    if a.mode == "final" and not (a.candidate and a.statement):
        raise SystemExit("final needs --candidate and --statement, both committed")
    res = dev(a.candidate) if a.mode == "dev" else final(a.candidate, a.statement)
    print(json.dumps(res, indent=1) if a.json else table(res))


if __name__ == "__main__":
    main()
