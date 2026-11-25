"""Score the frozen C1 and C0 once on the unread 2012 to 2021 coastal samples (protocol sections 5 and 6).

    uv run python scripts/coastal_c1/backtest.py --fetch "$HOME/dipcast-scratch/coastal-c1-backtest" \\
        --rain "$HOME/dipcast-scratch/coastal-c1-era5land/cache/rain" \\
        --frozen data/research/coastal/c1_frozen.v1.json --sha <the hash in the protocol> --out docs/coastal-c1

The read is logged in <out>/reads.jsonl and refused if a read is already logged there. It checks the frozen file's
hash first. No request is made: the samples come from scripts/coastal_baselines/fetch.py's saved responses.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts" / "coastal_baselines"))
import c1  # noqa: E402

SITES = REPO / "data" / "research" / "coastal" / "sites.csv"
YEARS = tuple(range(2012, 2022))
SEED = 20261122
RESAMPLES = 2000
LATE = tuple(range(2015, 2022))
MIN_EXCEEDANCES = 300
MIN_SEASONS_AGREE = 6


# ------------------------------------------------------------------ rows
def backtest_rows(fetch: Path) -> tuple[pd.DataFrame, dict]:
    import build  # scripts/coastal_baselines/build.py: the same parsing and mapping #692 used

    st = pd.read_csv(SITES)
    site_of = st.dropna(subset=["wqa_point"]).set_index("wqa_point")["site_id"]
    ec, info = build.observations(fetch, "ecoli")
    ec["site_id"] = ec["wqa_point"].map(site_of)
    info["rows_at_unmapped_points"] = int(ec["site_id"].isna().sum())
    ec, d = build.one_per_minute(ec.dropna(subset=["site_id"]))
    info.update(d)
    df = ec.rename(columns={"value": "ecoli", "qual": "ecoli_qual"})
    df["year"], df["month"] = df["time"].dt.year, df["time"].dt.month
    df = df[df["year"].isin(YEARS) & df["month"].isin(c1.MONTHS)].sort_values(["site_id", "time"])
    df = df.reset_index(drop=True)
    info["rows_in_season"] = len(df)
    return df, info


def features(df: pd.DataFrame, frozen: dict, rain_dir: Path) -> pd.DataFrame:
    df = df.copy()
    st = pd.read_csv(SITES)
    cells = c1.site_cells(st)
    df["cell"] = df["site_id"].map(lambda s: cells.get(s))
    df["t_utc"] = pd.DatetimeIndex(df["time"]).tz_convert("UTC")
    for name, line in c1.LINES.items():
        df[name] = c1.over(df["ecoli"], df["ecoli_qual"], line).astype(int)
    last = c1.last_sample(df)
    df["x_last1"], df["x_last2"] = last[:, 0], last[:, 1]
    hours = frozen["window"]["hours"]
    for h in hours:
        df[f"r{h}"] = np.nan
    for cell, g in df.groupby("cell", sort=True):
        if cell is None:
            continue
        rain = c1.load_cell(rain_dir, cell, YEARS)
        for h in hours:
            df.loc[g.index, f"r{h}"] = c1.window_sums(g["t_utc"], rain, h)[0]
    return df


def predictions(df: pd.DataFrame, frozen: dict, target: str) -> dict[str, np.ndarray]:
    tab = frozen["site_tables"][target]
    p0, m = tab["p0"], tab["m"]
    rate = np.array([(tab["sites"].get(s, {"k": 0})["k"] + m * p0) / (tab["sites"].get(s, {"n": 0})["n"] + m)
                     for s in df["site_id"]])
    month = df["month"].to_numpy()
    last = df[["x_last1", "x_last2"]].to_numpy()
    rain = df[[f"r{h}" for h in frozen["window"]["hours"]]].to_numpy()
    mod = frozen["models"][target]
    return {"B0": np.full(len(df), p0),
            "R": c1.predict(mod["R"], c1.design(rate, month, None, None)),
            "C0": c1.predict(mod["C0"], c1.design(rate, month, last, None)),
            "C1": c1.predict(mod["C1"], c1.design(rate, month, last, np.nan_to_num(rain)))}


# ------------------------------------------------------------------ intervals
def cells_of(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, int, int]:
    s_code, s_uni = pd.factorize(df["site_id"])
    t_code, t_uni = pd.factorize(df["year"])
    return s_code, t_code, len(s_uni), len(t_uni)


def two_way_mean(values: np.ndarray, s: np.ndarray, t: np.ndarray, ns: int, nt: int, rng, sites_only=False):
    """Bootstrap the row mean of `values`, drawing whole sites and whole seasons independently (protocol section 5),
    or sites alone. Returns the resampled means."""
    D = np.zeros((ns, nt))
    N = np.zeros((ns, nt))
    np.add.at(D, (s, t), values)
    np.add.at(N, (s, t), 1)
    out = np.empty(RESAMPLES)
    for b in range(RESAMPLES):
        a = np.bincount(rng.integers(0, ns, ns), minlength=ns).astype(float)
        c = np.ones(nt) if sites_only else np.bincount(rng.integers(0, nt, nt), minlength=nt).astype(float)
        den = a @ N @ c
        out[b] = (a @ D @ c) / den if den else np.nan
    return out


def ci(x: np.ndarray) -> list[float]:
    x = x[np.isfinite(x)]
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


def auc_interval(y, p, s, t, ns, nt, rng) -> list[float]:
    vals = []
    for _ in range(RESAMPLES // 4):          # AUC is slower; 500 two-way draws
        a = np.bincount(rng.integers(0, ns, ns), minlength=ns)
        c = np.bincount(rng.integers(0, nt, nt), minlength=nt)
        w = a[s] * c[t]
        k = w > 0
        if y[k].min() == y[k].max():
            continue
        vals.append(roc_auc_score(y[k], p[k], sample_weight=w[k]))
    return ci(np.array(vals))


def calibration(y: np.ndarray, p: np.ndarray) -> dict:
    m = LogisticRegression(C=1e6, max_iter=5000).fit(c1.logit(p)[:, None], y)
    return {"mean_predicted": float(p.mean()), "observed_rate": float(y.mean()),
            "in_the_large": float(p.mean() - y.mean()), "slope": float(m.coef_[0][0])}


def compare(df: pd.DataFrame, preds: dict, target: str, keep: np.ndarray, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    d = df[keep]
    y = d[target].to_numpy()
    s, t, ns, nt = cells_of(d)
    diff = (preds["C1"][keep] - y) ** 2 - (preds["C0"][keep] - y) ** 2
    out = {"rows": int(keep.sum()), "exceedances": int(y.sum()), "sites": ns, "seasons": nt,
           "brier": {k: c1.brier(v[keep], y) for k, v in preds.items()},
           "difference_c1_minus_c0": float(diff.mean()),
           "interval_two_way": ci(two_way_mean(diff, s, t, ns, nt, rng)),
           "interval_sites_only": ci(two_way_mean(diff, s, t, ns, nt, rng, sites_only=True))}
    by = {}
    for yr in sorted(d["year"].unique()):
        k = (d["year"] == yr).to_numpy()
        by[str(int(yr))] = {"rows": int(k.sum()), "exceedances": int(y[k].sum()), "difference": float(diff[k].mean())}
    out["by_season"] = by
    out["seasons_below_zero"] = sum(v["difference"] < 0 for v in by.values())
    out["auc"] = {}
    for k_, v in preds.items():
        if k_ == "B0":
            continue
        out["auc"][k_] = {"value": float(roc_auc_score(y, v[keep])),
                          "interval": auc_interval(y, v[keep], s, t, ns, nt, rng)}
    out["calibration_c1"] = calibration(y, preds["C1"][keep])
    out["calibration_c0"] = calibration(y, preds["C0"][keep])
    return out


def verdict(main: dict) -> str:
    if main["exceedances"] < MIN_EXCEEDANCES:
        return "too few"
    lo, hi = main["interval_two_way"]
    if main["difference_c1_minus_c0"] >= 0:
        return "not supported"
    if hi < 0 and main["seasons_below_zero"] >= MIN_SEASONS_AGREE:
        return "supported on unseen seasons"
    return "mixed"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch", type=Path, required=True)
    ap.add_argument("--rain", type=Path, required=True)
    ap.add_argument("--frozen", type=Path, required=True)
    ap.add_argument("--sha", required=True, help="the frozen file's SHA-256 as committed in the protocol")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    reads = a.out / "reads.jsonl"
    if reads.exists() and reads.read_text().strip():
        print("A read is already logged. The backtest is scored once.", file=sys.stderr)
        return 2
    got = c1.sha256(a.frozen)
    if got != a.sha:
        print(f"Frozen file hash {got} is not {a.sha}. Stopped.", file=sys.stderr)
        return 3
    frozen = json.loads(a.frozen.read_text())

    rows, info = backtest_rows(a.fetch)
    df = features(rows, frozen, a.rain)
    hours = frozen["window"]["hours"]
    cov = np.all([df[f"r{h}"].notna().to_numpy() for h in hours], axis=0)
    info.update(rows=len(df), sites=int(df["site_id"].nunique()), covered_rows=int(cov.sum()),
                uncovered_rows=int((~cov).sum()), rows_by_year={str(k): int(v) for k, v in df.groupby("year").size().items()})

    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    a.out.mkdir(parents=True, exist_ok=True)
    with reads.open("a") as f:
        f.write(json.dumps({"at": datetime.now(UTC).isoformat(timespec="seconds"), "commit": commit,
                            "frozen_sha256": got}) + "\n")

    res = {"read_at": datetime.now(UTC).isoformat(timespec="seconds"), "commit": commit, "frozen_sha256": got,
           "window": frozen["window"], "rows": info}
    p500 = predictions(df, frozen, "over_500")
    res["main"] = compare(df, p500, "over_500", cov, SEED)
    res["verdict"] = verdict(res["main"])
    late = cov & df["year"].isin(LATE).to_numpy()
    res["reported"] = {"seasons_2015_to_2021": compare(df, p500, "over_500", late, SEED + 1),
                       "over_250": compare(df, predictions(df, frozen, "over_250"), "over_250", cov, SEED + 2)}
    (a.out / "result.json").write_bytes(c1.canonical(res))
    print(json.dumps({"verdict": res["verdict"], "difference": res["main"]["difference_c1_minus_c0"],
                      "interval": res["main"]["interval_two_way"], "seasons_below_zero": res["main"]["seasons_below_zero"],
                      "exceedances": res["main"]["exceedances"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
