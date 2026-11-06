"""A lake E. coli chance from the lake's own rate: development test on 2024-2026 lake seasons
(docs/LAKE-OWN-RATE-TEST-2026-11.md; protocol committed in 95287b4c before any score).

Committed files only, no fetch, no dipcast import, no quota:

- docs/CONCENTRATION-STUDY-2026-11-atlas-rows.csv            the study's rows (637 lake rows, 12 lake bathing waters)
- docs/CONCENTRATION-STUDY-2026-11-predictions-{loyo,cxy,fwd}.csv   out-of-fold generic forecasts, joined by row index
- data/research/ecoli_evidence.v1.json                       every EA sample at each lake, 2023-26: the own history

    uv run python scripts/lake_own_rate_test.py            # writes docs/LAKE-OWN-RATE-TEST-2026-11-scores.json and -rows.csv

The candidate is (k + m g) / (n + m): the lake's own over-900 rate (k of n samples in the seasons the scheme allows),
shrunk toward production's lake form g for the day, m = 10. Scored against production's form, the concentration model,
the usual lake rate, the plain own rate and the last sample; 95% intervals from water-body-by-season cluster resamples.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parent.parent
STEM = ROOT / "docs" / "CONCENTRATION-STUDY-2026-11"
ATLAS = Path(f"{STEM}-atlas-rows.csv")
PRED = {s: Path(f"{STEM}-predictions-{s}.csv") for s in ("loyo", "cxy", "fwd")}
EVID = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
OUT = ROOT / "docs" / "LAKE-OWN-RATE-TEST-2026-11"

SEED = 20261105           # fixed in the protocol before any score
DRAWS = 2000
M = 10                    # the shrinkage weight, fixed in the protocol
M_SENS = (5, 30)          # reported, never selected
LAST_DAYS = 30            # "last sample": the previous sample at the site within this many days
LINES = (900, 500)
SKILL_MARGIN = 0.10
MIN_EVENTS = 15
LOW = 10.0                # the lab's reported limit: "<10" is left-censored at 10
HIGH = 10_000.0
SCHEMES = ("loyo", "cxy", "fwd")
MAIN = "loyo"
# The six lake bathing waters with no monitored overflow upstream: no generic forecast (supplementary population).
NO_OVERFLOW = ("uki1101-11910", "uki1101-11920", "uki1101-11930", "uki1106-11940", "ukk1100-36050", "ukk1302-11760")
ONE_LAKE_OUT = "Derwent Water"   # guardrail G1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ data
def load_rows() -> pd.DataFrame:
    """The study's lake rows with each scheme's out-of-fold generic forecasts, joined by row index (checked)."""
    a = pd.read_csv(ATLAS)
    a["row"] = np.arange(len(a))
    a["t"] = pd.to_datetime(a["sample_time"], utc=True)
    a["year"] = a["sample_time"].str[:4].astype(int)
    for s, path in PRED.items():
        p = pd.read_csv(path).set_index("row")
        if s in ("loyo", "fwd"):   # the atlas carries these two schemes' production forecasts: the join must agree
            d = a.loc[p.index, f"p_{s}"].to_numpy() - p["production_form"].to_numpy()
            assert np.nanmax(np.abs(d)) == 0.0, s
        for c in ("production_form", "candidate", "candidate_median", "candidate_sigma", "candidate_logscore",
                  "background_logscore"):
            a[f"{s}_{c}"] = p[c].reindex(a["row"]).to_numpy()
    lake = a[a["kind"] == "lake"].reset_index(drop=True)
    assert len(lake) == 637 and lake["bw_id"].nunique() == 12 and lake["catchment"].nunique() == 6
    lake["over900"] = (lake["ecoli"] > 900).astype(int)
    lake["over500"] = (lake["ecoli"] > 500).astype(int)
    lake["y"] = np.log10(lake["ecoli"].clip(lower=1).astype(float))
    lake["cens"] = np.select([lake["qual"].eq("<"), lake["qual"].eq(">")], [-1, 1], 0)
    iso = lake["t"].dt.isocalendar()
    lake["week"] = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    lake["cluster"] = lake["catchment"] + "|" + lake["year"].astype(str)
    return lake


def load_history(bw_ids) -> pd.DataFrame:
    """Every EA sample at the given lake bathing waters, from the evidence file (2023-26, May-September)."""
    ev = json.loads(EVID.read_text())
    out = []
    for s in ev["sites"]:
        if s["bw_id"] not in bw_ids:
            continue
        for x in s["samples"]:
            if x["ecoli"] is None:
                continue
            out.append({"bw_id": s["bw_id"], "name": s["name"], "t": pd.Timestamp(x["t"]), "year": int(x["t"][:4]),
                        "ecoli": float(x["ecoli"]), "q": x["q"]})
    h = pd.DataFrame(out)
    h["t"] = pd.to_datetime(h["t"], utc=True)
    h["over900"] = (h["ecoli"] > 900).astype(int)
    h["over500"] = (h["ecoli"] > 500).astype(int)
    h["ylog"] = np.log10(h["ecoli"].clip(lower=LOW))   # a value below the limit taken as 10 (protocol, section 3)
    return h.sort_values(["bw_id", "t"]).reset_index(drop=True)


def allowed(scheme: str, hist_year: np.ndarray, year: int) -> np.ndarray:
    return hist_year < year if scheme == "fwd" else hist_year != year


# ------------------------------------------------------------------ the references and the candidate
def references(rows: pd.DataFrame, hist: pd.DataFrame, scheme: str, line: int) -> pd.DataFrame:
    """Per row: k, n, own rate, usual rate, last-sample rate and own log10 level, from the seasons the scheme allows."""
    over = f"over{line}"
    by_site = {bw: g for bw, g in hist.groupby("bw_id")}
    # transitions for "last sample": each history sample with a previous one at its site within LAST_DAYS
    tr = []
    for bw, g in by_site.items():
        t, o = g["t"].to_numpy(), g[over].to_numpy()
        for i in range(1, len(g)):
            gap = (t[i] - t[i - 1]) / np.timedelta64(1, "D")
            if gap <= LAST_DAYS:
                tr.append((g["year"].iloc[i], bool(o[i - 1]), int(o[i])))
    tr = pd.DataFrame(tr, columns=["year", "prev_over", "over"])
    out = []
    for r in rows.itertuples(index=False):
        ok = allowed(scheme, hist["year"].to_numpy(), r.year)
        usual = float(hist.loc[ok, over].mean()) if ok.any() else np.nan
        g = by_site[r.bw_id]
        own_ok = allowed(scheme, g["year"].to_numpy(), r.year)
        n, k = int(own_ok.sum()), int(g.loc[own_ok, over].sum())
        yl = g.loc[own_ok, "ylog"]
        mu_own = float(yl.mean()) if n else np.nan
        sd_own = float(yl.std(ddof=1)) if n >= 2 else np.nan
        prev = g[g["t"] < r.t - pd.Timedelta(minutes=1)]
        last = usual
        if len(prev) and (r.t - prev["t"].iloc[-1]) / pd.Timedelta(days=1) <= LAST_DAYS:
            tok = tr[allowed(scheme, tr["year"].to_numpy(), r.year) & (tr["prev_over"] == bool(prev[over].iloc[-1]))]
            last = float(tok["over"].mean()) if len(tok) else usual
        out.append({"k": k, "n": n, "usual": usual, "own": k / n if n else usual, "last": last,
                    "mu_own": mu_own, "sd_own": sd_own})
    return pd.DataFrame(out, index=rows.index)


def shrink(k: np.ndarray, n: np.ndarray, g: np.ndarray, m: float) -> np.ndarray:
    return (k + m * g) / (n + m)


def forecasts(rows: pd.DataFrame, hist: pd.DataFrame, scheme: str, line: int) -> pd.DataFrame:
    """Every forecast of P(over `line`) for the rows under one scheme, plus the row's outcome and clusters."""
    ref = references(rows, hist, scheme, line)
    f = pd.DataFrame({"y": rows[f"over{line}"].to_numpy(), "cluster": rows["cluster"].to_numpy(),
                      "week": rows["week"].to_numpy(), "catchment": rows["catchment"].to_numpy(),
                      "year": rows["year"].to_numpy(), "bw_id": rows["bw_id"].to_numpy(),
                      "name": rows["name"].to_numpy()}, index=rows.index)
    for c in ("k", "n", "usual", "own", "last"):
        f[c] = ref[c].to_numpy()
    if line == 900:
        f["production"] = rows[f"{scheme}_production_form"].to_numpy()
        f["concentration"] = rows[f"{scheme}_candidate"].to_numpy()
        g = f["production"].to_numpy()
    else:   # production has no 500 line: shrink toward the concentration model's P(>500), a normal on log10
        z = (np.log10(line) - rows[f"{scheme}_candidate_median"].to_numpy()) / rows[f"{scheme}_candidate_sigma"].to_numpy()
        f["concentration"] = norm.sf(z)
        g = f["concentration"].to_numpy()
    f["candidate"] = shrink(f["k"].to_numpy(), f["n"].to_numpy(), g, M)
    for m in M_SENS:
        f[f"candidate_m{m}"] = shrink(f["k"].to_numpy(), f["n"].to_numpy(), g, m)
    return f


def censored_logscore(mu: np.ndarray, sd: np.ndarray, y: np.ndarray, cens: np.ndarray) -> np.ndarray:
    z = (y - mu) / sd
    return np.where(cens < 0, norm.logcdf((np.log10(LOW) - mu) / sd),
                    np.where(cens > 0, norm.logsf((np.log10(HIGH) - mu) / sd), norm.logpdf(z) - np.log(sd)))


def concentration(rows: pd.DataFrame, hist: pd.DataFrame, scheme: str) -> pd.DataFrame:
    """Log scores on log10 E. coli: the lake's own level, that level shrunk toward the concentration model's median,
    and the committed concentration and background models (protocol, section 3)."""
    ref = references(rows, hist, scheme, 900)
    y, cens = rows["y"].to_numpy(), rows["cens"].to_numpy()
    pooled_mu, pooled_sd = float(hist["ylog"].mean()), float(hist["ylog"].std(ddof=1))
    mu_own = ref["mu_own"].fillna(pooled_mu).to_numpy()
    sd_own = ref["sd_own"].fillna(pooled_sd).to_numpy()
    n = ref["n"].to_numpy()
    med, sig = rows[f"{scheme}_candidate_median"].to_numpy(), rows[f"{scheme}_candidate_sigma"].to_numpy()
    w = n / (n + M)
    f = pd.DataFrame({"cluster": rows["cluster"].to_numpy(), "week": rows["week"].to_numpy()}, index=rows.index)
    f["own_level"] = censored_logscore(mu_own, sd_own, y, cens)
    f["own_level_shrunk"] = censored_logscore(w * mu_own + (1 - w) * med, sig, y, cens)
    f["concentration"] = rows[f"{scheme}_candidate_logscore"].to_numpy()
    f["background"] = rows[f"{scheme}_background_logscore"].to_numpy()
    return f


# ------------------------------------------------------------------ scores
def auc(p, y) -> float:
    p, y = np.asarray(p, float), np.asarray(y, bool)
    if y.all() or not y.any():
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    r = np.empty(len(p))
    r[order] = np.arange(1, len(p) + 1)
    for v in np.unique(p):
        m = p == v
        r[m] = r[m].mean()
    n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def site_auc(f: pd.DataFrame, col: str) -> float | None:
    vals = [auc(g[col], g["y"]) for _, g in f.groupby("bw_id") if g["y"].nunique() > 1]
    return round(float(np.mean(vals)), 3) if vals else None


def brier(p, y) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def logloss(p, y) -> float:
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def boot_mean(d: np.ndarray, cluster: np.ndarray, seed: int = SEED, n: int = DRAWS) -> list[float]:
    """95% interval of the mean of d, resampling whole clusters with replacement."""
    codes, inv = np.unique(cluster, return_inverse=True)
    s, c = np.bincount(inv, weights=d), np.bincount(inv).astype(float)
    draws = np.random.default_rng(seed).integers(0, len(codes), size=(n, len(codes)))
    stat = s[draws].sum(1) / c[draws].sum(1)
    return [round(float(v), 5) for v in np.percentile(stat, [2.5, 97.5])]


def diff(f: pd.DataFrame, a: str, b: str) -> dict:
    """Brier(a) − Brier(b) with its cluster interval (water body × season) and the ISO-week interval."""
    d = (f[a] - f["y"]) ** 2 - (f[b] - f["y"]) ** 2
    d = d.to_numpy()
    return {"mean": round(float(d.mean()), 5), "ci95": boot_mean(d, f["cluster"].to_numpy()),
            "ci95_week": boot_mean(d, f["week"].to_numpy())}


MODELS = ("candidate", "production", "concentration", "usual", "own", "last")


def block(f: pd.DataFrame, with_diffs: bool = True) -> dict:
    cols = [c for c in MODELS if c in f] + [f"candidate_m{m}" for m in M_SENS]
    r = {"n": int(len(f)), "events": int(f["y"].sum()), "sites": int(f["bw_id"].nunique()),
         "clusters": int(f["cluster"].nunique()),
         "brier": {c: round(brier(f[c], f["y"]), 5) for c in cols},
         "auc": {c: round(auc(f[c], f["y"]), 3) for c in cols},
         "site_auc_mean": {c: site_auc(f, c) for c in cols},
         "logloss": {c: round(logloss(f[c], f["y"]), 4) for c in cols}}
    r["skill_vs_usual"] = {c: round(1 - r["brier"][c] / r["brier"]["usual"], 4) for c in cols}
    if with_diffs:
        r["candidate_minus"] = {c: diff(f, "candidate", c) for c in cols if c != "candidate"}
        r["usual_minus_candidate"] = diff(f, "usual", "candidate")
    return r


def by(f: pd.DataFrame, key: str) -> dict:
    return {str(k): block(g, with_diffs=False) for k, g in f.groupby(key)}


def supplementary(hist_all: pd.DataFrame) -> dict:
    """The six lake bathing waters with no overflow upstream: no generic forecast, so the candidate shrinks toward
    the usual rate of those six; leave one season out over 2023-26; description only."""
    h = hist_all[hist_all["bw_id"].isin(NO_OVERFLOW)].reset_index(drop=True)
    out = {}
    for line in LINES:
        over = f"over{line}"
        rows = []
        for r in h.itertuples(index=False):
            ok = h["year"].to_numpy() != r.year
            usual = float(h.loc[ok, over].mean())
            g = h[(h["bw_id"] == r.bw_id) & ok]
            n, k = len(g), int(g[over].sum())
            rows.append({"y": getattr(r, over), "bw_id": r.bw_id, "cluster": f"{r.bw_id}|{r.year}",
                         "usual": usual, "own": k / n if n else usual, "candidate": shrink(k, n, usual, M)})
        f = pd.DataFrame(rows)
        out[str(line)] = {"n": len(f), "events": int(f["y"].sum()), "sites": int(f["bw_id"].nunique()),
                          "brier": {c: round(brier(f[c], f["y"]), 5) for c in ("candidate", "usual", "own")},
                          "auc": {c: round(auc(f[c], f["y"]), 3) for c in ("candidate", "usual", "own")},
                          "candidate_minus_usual": diff(f.assign(week=f["cluster"]), "candidate", "usual")}
    return out


# ------------------------------------------------------------------ run
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    inputs = [ATLAS, *PRED.values(), EVID]
    before = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    rows = load_rows()
    sites = sorted(rows["bw_id"].unique())
    hist_all = load_history(set(sites) | set(NO_OVERFLOW))
    hist = hist_all[hist_all["bw_id"].isin(sites)].reset_index(drop=True)

    res = {"schema": "swimsignal.lake-own-rate-test", "version": "1.0.0", "protocol": "docs/LAKE-OWN-RATE-TEST-2026-11.md",
           "protocol_commit": "95287b4c", "seed": SEED, "draws": DRAWS, "m": M, "m_sensitivity": list(M_SENS),
           "last_sample_days": LAST_DAYS, "skill_margin": SKILL_MARGIN, "min_events": MIN_EVENTS,
           "inputs_sha256": before,
           "population": {"rows": int(len(rows)), "sites": len(sites), "water_bodies": int(rows["catchment"].nunique()),
                          "years": sorted(int(y) for y in rows["year"].unique()),
                          "history_samples": int(len(hist)),
                          "history_by_site": hist.groupby("name").size().to_dict(),
                          "history_archive_only_included": True},
           "schemes": {}}
    main_f = None
    for scheme in SCHEMES:
        sub = rows if scheme != "fwd" else rows[rows["year"] >= 2025]
        sub = sub[sub[f"{scheme}_production_form"].notna()].reset_index(drop=True)
        s = {"line": {}}
        for line in LINES:
            f = forecasts(sub, hist, scheme, line)
            r = block(f)
            r["by_water_body"] = by(f, "catchment")
            r["by_year"] = by(f, "year")
            r["without_" + ONE_LAKE_OUT.replace(" ", "_").lower()] = block(f[f["catchment"] != ONE_LAKE_OUT].reset_index(drop=True))
            r["own_history_n"] = {"min": int(f["n"].min()), "median": float(f["n"].median()), "max": int(f["n"].max())}
            s["line"][str(line)] = r
            if scheme == MAIN and line == 900:
                main_f = f
        c = concentration(sub, hist, scheme)
        s["log_concentration"] = {
            "mean_logscore": {k: round(float(c[k].mean()), 4) for k in ("own_level", "own_level_shrunk", "concentration", "background")},
            "own_level_shrunk_minus_concentration": {"mean": round(float((c["own_level_shrunk"] - c["concentration"]).mean()), 4),
                                                     "ci95": boot_mean((c["own_level_shrunk"] - c["concentration"]).to_numpy(), c["cluster"].to_numpy())},
            "own_level_minus_concentration": {"mean": round(float((c["own_level"] - c["concentration"]).mean()), 4),
                                              "ci95": boot_mean((c["own_level"] - c["concentration"]).to_numpy(), c["cluster"].to_numpy())},
            "own_level_minus_background": {"mean": round(float((c["own_level"] - c["background"]).mean()), 4),
                                           "ci95": boot_mean((c["own_level"] - c["background"]).to_numpy(), c["cluster"].to_numpy())}}
        res["schemes"][scheme] = s
    res["supplementary_no_overflow_lakes"] = supplementary(hist_all)

    # the stated conditions, on the main scheme at 900
    m9 = res["schemes"][MAIN]["line"]["900"]
    cxy9, fwd9 = res["schemes"]["cxy"]["line"]["900"], res["schemes"]["fwd"]["line"]["900"]
    g1 = m9["without_derwent_water"]
    skill = m9["skill_vs_usual"]["candidate"]
    checks = {
        "gate: at least 15 results over 900 in the main scheme": m9["events"] >= MIN_EVENTS,
        "1 skill over the usual rate at least 0.10, usual-minus-candidate interval above zero":
            bool(skill >= SKILL_MARGIN and m9["usual_minus_candidate"]["ci95"][0] > 0),
        "1a skill interval above zero (for 'gain under the margin')": bool(m9["usual_minus_candidate"]["ci95"][0] > 0),
        "2 beats production's form, interval wholly below zero": bool(m9["candidate_minus"]["production"]["ci95"][1] < 0),
        "3 not worse than the plain own rate (point estimate)": bool(m9["candidate_minus"]["own"]["mean"] <= 0),
        "G1 without Derwent Water: at or below production, skill above zero":
            bool(g1["brier"]["candidate"] <= g1["brier"]["production"] and g1["skill_vs_usual"]["candidate"] > 0),
        "G2 lake-out and forward: candidate-minus-production interval not wholly above zero":
            bool(cxy9["candidate_minus"]["production"]["ci95"][0] <= 0 and fwd9["candidate_minus"]["production"]["ci95"][0] <= 0),
    }
    core = checks["2 beats production's form, interval wholly below zero"] and checks["3 not worse than the plain own rate (point estimate)"] \
        and checks["G1 without Derwent Water: at or below production, skill above zero"] \
        and checks["G2 lake-out and forward: candidate-minus-production interval not wholly above zero"]
    if not checks["gate: at least 15 results over 900 in the main scheme"]:
        verdict = "too few to judge"
    elif core and checks["1 skill over the usual rate at least 0.10, usual-minus-candidate interval above zero"]:
        verdict = "pass"
    elif core and checks["1a skill interval above zero (for 'gain under the margin')"]:
        verdict = "gain under the margin"
    elif not checks["3 not worse than the plain own rate (point estimate)"]:
        verdict = "fail: the plain own rate is better"
    else:
        verdict = "fail"
    res["checks"], res["verdict"] = checks, verdict

    after = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    assert before == after, "an input changed during the run"
    Path(f"{args.out}-scores.json").write_text(json.dumps(res, indent=1, default=float) + "\n")
    main_f.drop(columns=["cluster", "week"]).to_csv(f"{args.out}-rows.csv", index=False)
    show = {"verdict": verdict, "checks": checks, "main_900": {k: m9[k] for k in ("n", "events", "brier", "auc", "site_auc_mean",
                                                                                   "skill_vs_usual", "candidate_minus", "usual_minus_candidate")},
            "without_derwent": {k: g1[k] for k in ("n", "events", "brier", "skill_vs_usual")},
            "cxy_900": {k: cxy9[k] for k in ("brier", "skill_vs_usual", "candidate_minus")},
            "fwd_900": {k: fwd9[k] for k in ("n", "events", "brier", "skill_vs_usual", "candidate_minus")},
            "main_500": {k: m9 and res["schemes"][MAIN]["line"]["500"][k] for k in ("events", "brier", "auc", "skill_vs_usual", "candidate_minus")},
            "log_concentration": {s: res["schemes"][s]["log_concentration"] for s in SCHEMES},
            "supplementary": res["supplementary_no_overflow_lakes"]}
    print(json.dumps(show, indent=1, default=float))


if __name__ == "__main__":
    main()
