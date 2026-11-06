"""Lake E. coli line chance and within-lake wet response: candidates A, B and C on 2024-2026 lake seasons
(docs/LAKE-LINE-CANDIDATES-2026-11.md; protocol committed in 3717a7aa before any score). Off CI, by hand, in a scratch
root holding copies of the cached inputs that concentration_study.load_rows reads:

    export DIPCAST_ROOT=<scratch root> DIPCAST_STATE=<scratch>/state LAKE_LINE_OUT=<scratch>/out
    uv run python scripts/lake_line_candidates.py rows       # the study's 1,537 rows, checked against the atlas
    uv run python scripts/lake_line_candidates.py run        # every model in every fold; scores and conditions
    uv run python scripts/lake_line_candidates.py diagnose   # Derwent Water 2025, described only
    uv run python scripts/lake_line_candidates.py export     # freeze plain and B for the 2027 read (not a logger)

plain = lake-range-v1's form (CensoredRI with its own lake noise); A = plain's line chance recalibrated on inner
season-out predictions; B = plain plus a partially pooled lake-specific slope on a wet index (rain 48 h and exposure);
C = B recalibrated. References: production's lake form and #466's model (committed out-of-fold predictions), the usual
rate, own rate and last sample (scripts/lake_own_rate_test.py).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, log_ndtr, logit, logsumexp, ndtr
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from concentration_study import PROD, CensoredRI  # noqa: E402
from lake_own_rate_test import auc, boot_mean, brier, load_history, logloss, references, shrink, site_auc  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("lake_line_candidates")

OUT = Path(os.environ.get("LAKE_LINE_OUT", "lake_line_out"))
DOC = ROOT / "docs" / "LAKE-LINE-CANDIDATES-2026-11"
STEM = ROOT / "docs" / "CONCENTRATION-STUDY-2026-11"
ATLAS = Path(f"{STEM}-atlas-rows.csv")
PRED = {s: Path(f"{STEM}-predictions-{s}.csv") for s in ("loyo", "cxy", "fwd")}
SEED = 20261106          # fixed in the protocol
DRAWS = 2000
LINES = (900, 500)
SCHEMES = ("loyo", "cxy", "fwd")
MAIN = "loyo"
SKILL_MARGIN = 0.10      # #625's margin, unchanged
N1_MARGIN, N2_MARGIN, N3_MARGIN, N4_MARGIN = 0.002, 0.004, -0.02, 0.001
PRIOR_A, PRIOR_B = (0.0, 1.5), (1.0, 0.5)   # recalibration priors: a ~ N(0, 1.5^2), b ~ N(1, 0.5^2)
N_U, N_V = 16, 10        # Gauss-Hermite nodes for B's intercept and slope
B_COLS = PROD + ["lake_x_wet"]
BINS = {900: [0, 0.01, 0.02, 0.05, 0.1, 1.0], 500: [0, 0.02, 0.05, 0.1, 0.2, 1.0]}
KEEP = ["bw_id", "name", "kind", "catchment", "sample_time", "ecoli", "qual", "y", "cens", "over", "year", "week",
        "rain_48h", "rain_24h", "risk_lead0", *PROD]


# ------------------------------------------------------------------ rows
def stage_rows() -> None:
    from concentration_study import load_rows
    df = load_rows()
    a = pd.read_csv(ATLAS)
    assert len(df) == len(a) == 1537, (len(df), len(a))
    same = (df["bw_id"].to_numpy() == a["bw_id"].to_numpy()) & (df["ecoli"].to_numpy() == a["ecoli"].to_numpy()) & \
        (df["sample_time"].astype(str).to_numpy() == a["sample_time"].astype(str).to_numpy())
    assert same.all(), f"{(~same).sum()} rows differ from the atlas"
    OUT.mkdir(parents=True, exist_ok=True)
    df[KEEP].to_parquet(OUT / "rows.parquet", index=False)
    print(df.groupby("kind").size().to_dict(), "rows match the atlas")


def load() -> pd.DataFrame:
    df = pd.read_parquet(OUT / "rows.parquet")
    df["row"] = np.arange(len(df))
    df["lake"] = df["lake"].astype(float)
    df["t"] = pd.to_datetime(df["sample_time"], utc=True)
    df["cluster"] = df["catchment"] + "|" + df["year"].astype(str)
    df["rain48_fc"] = np.expm1(df["lrain48"])   # the lead-0 forecast rain the model reads (rain_48h is reanalysis)
    for s, path in PRED.items():
        p = pd.read_csv(path).set_index("row")
        for c in ("production_form", "candidate", "candidate_median"):
            df[f"{s}_{c}"] = p[c].reindex(df["row"]).to_numpy()
    return df


# ------------------------------------------------------------------ candidate B: random intercept and lake slope
def _z(X: pd.DataFrame, cols, ref: pd.DataFrame) -> np.ndarray:
    mu, sd = ref[cols].mean(), ref[cols].std(ddof=0).replace(0, 1.0)
    return np.column_stack([np.ones(len(X)), ((X[cols] - mu) / sd).to_numpy(dtype=float)])


def _row_ll(mu: np.ndarray, s: np.ndarray, y: np.ndarray, cens: np.ndarray) -> np.ndarray:
    """Censored normal log-likelihood, mu and s of shape (n, K) and (n, 1); fast path for counted values."""
    z = (y[:, None] - mu) / s
    out = -0.5 * z * z - np.log(s) - 0.5 * np.log(2 * np.pi)
    lo, hi = cens < 0, cens > 0
    if lo.any():
        out[lo] = log_ndtr(z[lo])
    if hi.any():
        out[hi] = log_ndtr(-z[hi])
    return out


class LakeSlopeRI:
    """y = Z beta + u_site + v_site * (lake x wet) + e; u ~ N(0, tau^2), v ~ N(0, tau_v^2); e normal with its own lake
    noise; censored as the lab reports. theta = [beta, log sigma, log tau, lake shift, log tau_v]."""

    def __init__(self, cols=B_COLS, n_u: int = N_U, n_v: int = N_V):
        self.cols = cols
        xu, wu = np.polynomial.hermite.hermgauss(n_u)
        xv, wv = np.polynomial.hermite.hermgauss(n_v)
        self.gu = np.repeat(np.sqrt(2.0) * xu, n_v)
        self.gv = np.tile(np.sqrt(2.0) * xv, n_u)
        self.logw = (np.log(wu / np.sqrt(np.pi))[:, None] + np.log(wv / np.sqrt(np.pi))[None, :]).ravel()

    def _sig(self, theta, lake):
        p = self.p
        return np.exp(theta[p] + theta[p + 2] * lake)[:, None]

    def _mu(self, theta, Z, lw):
        p = self.p
        return (Z @ theta[:p])[:, None] + np.exp(theta[p + 1]) * self.gu[None, :] + np.exp(theta[p + 3]) * lw[:, None] * self.gv[None, :]

    def fit(self, X: pd.DataFrame, y, cens, site):
        self.ref = X[self.cols].copy()
        Z = _z(X, self.cols, self.ref)
        self.p = Z.shape[1]
        lake, lw = X["lake"].to_numpy(dtype=float), X["lake_x_wet"].to_numpy(dtype=float)
        self.sites = pd.Index(np.unique(site))
        si = self.sites.get_indexer(site)
        start = CensoredRI(self.cols, lake_sigma=True).fit(X, y, cens, site)   # the plain fit with the extra column
        theta0 = np.concatenate([start.theta, [np.log(0.1)]])

        def post(theta):
            ll = _row_ll(self._mu(theta, Z, lw), self._sig(theta, lake), y, cens)
            S = np.zeros((len(self.sites), ll.shape[1]))
            np.add.at(S, si, ll)
            return self.logw[None, :] + S

        def nll(theta):
            return -float(logsumexp(post(theta), axis=1).sum())

        bounds = [(None, None)] * self.p + [(-5, 3), (-6, 2), (-3, 3), (-7, 1)]
        res = minimize(nll, theta0, method="L-BFGS-B", bounds=bounds)
        self.theta, self.converged, self.nll = res.x, bool(res.success), float(res.fun)
        self.train_post = post(self.theta)
        p = self.p
        self.sigma, self.tau = float(np.exp(self.theta[p])), float(np.exp(self.theta[p + 1]))
        self.sigma_lake, self.tau_v = float(np.exp(self.theta[p] + self.theta[p + 2])), float(np.exp(self.theta[p + 3]))
        return self

    def _parts(self, X, site):
        Z = _z(X, self.cols, self.ref)
        mu = self._mu(self.theta, Z, X["lake_x_wet"].to_numpy(dtype=float))
        si = self.sites.get_indexer(site)
        logp = np.where((si >= 0)[:, None], self.train_post[np.clip(si, 0, None)], self.logw[None, :])
        w = np.exp(logp - logsumexp(logp, axis=1, keepdims=True))
        return w, mu, self._sig(self.theta, X["lake"].to_numpy(dtype=float))

    def p_over(self, X, site, cut):
        w, mu, s = self._parts(X, site)
        return (w * ndtr((mu - cut) / s)).sum(1)

    def cdf(self, X, site, yv):
        w, mu, s = self._parts(X, site)
        return (w * ndtr((yv[:, None] - mu) / s)).sum(1)

    def log_score(self, X, site, y, cens):
        w, mu, s = self._parts(X, site)
        return logsumexp(np.log(np.clip(w, 1e-300, None)) + _row_ll(mu, s, y, cens), axis=1)

    def slope_means(self) -> dict:
        """Each fitted site's posterior mean of v (the lake's own slope minus the all-lake slope), log10 per unit wet."""
        w = np.exp(self.train_post - logsumexp(self.train_post, axis=1, keepdims=True))
        return dict(zip(self.sites, (w @ (self.tau_v * self.gv)).round(4).tolist(), strict=True))


def add_wet(X: pd.DataFrame, ref: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """wet = mean of standardised lrain48 and logit_risk, standardised again, all on ref's lake rows."""
    lk = ref[ref["lake"] == 1]
    m48, s48 = float(lk["lrain48"].mean()), float(lk["lrain48"].std(ddof=0)) or 1.0
    mr, sr = float(lk["logit_risk"].mean()), float(lk["logit_risk"].std(ddof=0)) or 1.0
    raw = lambda d: ((d["lrain48"] - m48) / s48 + (d["logit_risk"] - mr) / sr) / 2   # noqa: E731
    mw, sw = float(raw(lk).mean()), float(raw(lk).std(ddof=0)) or 1.0
    wet = (raw(X) - mw) / sw
    return X.assign(lake_x_wet=X["lake"] * wet), {"m48": m48, "s48": s48, "mr": mr, "sr": sr, "mw": mw, "sw": sw}


def median_of(m, X, site) -> np.ndarray:
    lo, hi = np.full(len(X), -2.0), np.full(len(X), 7.0)
    for _ in range(40):
        mid = (lo + hi) / 2
        below = m.cdf(X, site, mid) < 0.5
        lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
    return (lo + hi) / 2


def pit(m, X, site, y, cens, rng) -> np.ndarray:
    F = m.cdf(X, site, y)
    v = rng.uniform(size=len(y))
    return np.where(cens < 0, v * F, np.where(cens > 0, F + v * (1 - F), F))


# ------------------------------------------------------------------ recalibration
def fit_map(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """logit p' = a + b logit p, the posterior mode under a ~ N(0, 1.5^2), b ~ N(1, 0.5^2)."""
    x = logit(np.clip(p, 1e-4, 1 - 1e-4))

    def nlp(t):
        q = np.clip(expit(t[0] + t[1] * x), 1e-12, 1 - 1e-12)
        return -float(np.sum(y * np.log(q) + (1 - y) * np.log(1 - q))) + \
            (t[0] - PRIOR_A[0]) ** 2 / (2 * PRIOR_A[1] ** 2) + (t[1] - PRIOR_B[0]) ** 2 / (2 * PRIOR_B[1] ** 2)
    r = minimize(nlp, np.array([0.0, 1.0]), method="L-BFGS-B")
    return float(r.x[0]), float(r.x[1])


def apply_map(p: np.ndarray, ab: tuple[float, float] | None) -> np.ndarray:
    return p if ab is None else expit(ab[0] + ab[1] * logit(np.clip(p, 1e-4, 1 - 1e-4)))


# ------------------------------------------------------------------ folds
def folds(df: pd.DataFrame, scheme: str):
    yr, grp, lake = df["year"].to_numpy(), df["catchment"].to_numpy(), df["lake"].to_numpy() == 1
    if scheme == "loyo":
        for y in (2024, 2025, 2026):
            yield str(y), yr != y, (yr == y) & lake
    elif scheme == "fwd":
        for y in (2025, 2026):
            yield str(y), yr < y, (yr == y) & lake
    elif scheme == "cxy":
        for g in sorted(np.unique(grp[lake])):
            for y in (2024, 2025, 2026):
                te = (grp == g) & (yr == y) & lake
                if te.any():
                    yield f"{g}|{y}", (grp != g) & (yr != y), te


def fit_both(tr: pd.DataFrame):
    """plain and B on the fitting rows (B with the wet index standardised on them)."""
    y, c, s = tr["y"].to_numpy(), tr["cens"].to_numpy(), tr["bw_id"].to_numpy()
    plain = CensoredRI(PROD, lake_sigma=True).fit(tr, y, c, s)
    trw, wet = add_wet(tr, tr)
    b = LakeSlopeRI().fit(trw, y, c, s)
    return plain, b, wet


def line_probs(plain, b, wet, te: pd.DataFrame) -> dict:
    s = te["bw_id"].to_numpy()
    tew = add_wet_with(te, wet)
    return {f"{nm}_{line}": m.p_over(X, s, np.log10(line)) for nm, m, X in (("plain", plain, te), ("B", b, tew))
            for line in LINES}


def add_wet_with(X: pd.DataFrame, w: dict) -> pd.DataFrame:
    raw = ((X["lrain48"] - w["m48"]) / w["s48"] + (X["logit_risk"] - w["mr"]) / w["sr"]) / 2
    return X.assign(lake_x_wet=X["lake"] * (raw - w["mw"]) / w["sw"])


def inner_maps(fit_rows: pd.DataFrame) -> dict | None:
    """Recalibration maps from inner season-out predictions at the fitting set's lake rows; None with one season."""
    seasons = sorted(fit_rows["year"].unique())
    if len(seasons) < 2:
        return None
    oof = []
    for yv in seasons:
        tr, te = fit_rows[fit_rows["year"] != yv], fit_rows[(fit_rows["year"] == yv) & (fit_rows["lake"] == 1)]
        if not len(te):
            continue
        plain, b, wet = fit_both(tr)
        oof.append(pd.DataFrame({**line_probs(plain, b, wet, te), "over900": (te["ecoli"] > 900).astype(int).to_numpy(),
                                 "over500": (te["ecoli"] > 500).astype(int).to_numpy()}))
    o = pd.concat(oof, ignore_index=True)
    return {f"{nm}_{line}": fit_map(o[f"{nm}_{line}"].to_numpy(), o[f"over{line}"].to_numpy())
            for nm in ("plain", "B") for line in LINES} | {"_n": len(o), "_events900": int(o["over900"].sum()),
                                                            "_events500": int(o["over500"].sum())}


def run_scheme(df: pd.DataFrame, scheme: str) -> tuple[pd.DataFrame, list]:
    rng = np.random.default_rng(SEED)
    out, fits = [], []
    for name, trm, tem in folds(df, scheme):
        t0 = time.time()
        tr, te = df[trm], df[tem]
        plain, b, wet = fit_both(tr)
        maps = inner_maps(tr)
        s, y, c = te["bw_id"].to_numpy(), te["y"].to_numpy(), te["cens"].to_numpy()
        tew = add_wet_with(te, wet)
        r = pd.DataFrame({"row": te["row"].to_numpy(), "fold": name})
        r = r.assign(**line_probs(plain, b, wet, te))
        for line in LINES:
            r[f"A_{line}"] = apply_map(r[f"plain_{line}"].to_numpy(), None if maps is None else maps[f"plain_{line}"])
            r[f"C_{line}"] = apply_map(r[f"B_{line}"].to_numpy(), None if maps is None else maps[f"B_{line}"])
        r["plain_ls"], r["B_ls"] = plain.log_score(te, s, y, c), b.log_score(tew, s, y, c)
        r["plain_med"], r["B_med"] = median_of(plain, te, s), median_of(b, tew, s)
        r["plain_pit"], r["B_pit"] = pit(plain, te, s, y, c, rng), pit(b, tew, s, y, c, rng)
        out.append(r)
        fits.append({"fold": name, "fit_rows": int(len(tr)), "scored": int(len(te)),
                     "plain": {"converged": plain.converged, "sigma_lake": round(plain.sigma_lake, 4), "tau": round(plain.tau, 4)},
                     "B": {"converged": b.converged, "sigma_lake": round(b.sigma_lake, 4), "tau": round(b.tau, 4),
                           "tau_v": round(b.tau_v, 4), "lake_x_wet_coef_std": round(float(b.theta[b.cols.index("lake_x_wet") + 1]), 4),
                           "lake_slopes": {k: v for k, v in b.slope_means().items() if k in set(df.loc[df.lake == 1, "bw_id"])}},
                     "maps": None if maps is None else {k: (v if k.startswith("_") else [round(v[0], 4), round(v[1], 4)])
                                                         for k, v in maps.items()},
                     "seconds": round(time.time() - t0, 1)})
        log.info("%s %s: %d scored, %.0f s, B tau_v %.3f", scheme, name, len(te), time.time() - t0, b.tau_v)
    return pd.concat(out, ignore_index=True).sort_values("row").reset_index(drop=True), fits


# ------------------------------------------------------------------ scores
def reliability(p, y, edges) -> dict:
    p, y = np.asarray(p, float), np.asarray(y, float)
    bins = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo)
        bins.append({"bin": [lo, hi], "n": int(m.sum()), "mean_forecast": round(float(p[m].mean()), 4) if m.any() else None,
                     "observed": round(float(y[m].mean()), 4) if m.any() else None})
    x = logit(np.clip(p, 1e-4, 1 - 1e-4))

    def nll(t):
        q = np.clip(expit(t[0] + t[1] * x), 1e-12, 1 - 1e-12)
        return -float(np.sum(y * np.log(q) + (1 - y) * np.log(1 - q)))
    slope = minimize(nll, np.array([0.0, 1.0]), method="L-BFGS-B").x[1]
    return {"bins": bins, "in_the_large": round(float(p.mean() - y.mean()), 5), "slope": round(float(slope), 3)}


def site_rho(f: pd.DataFrame, col: str) -> dict:
    v = {}
    for bw, g in f.groupby("bw_id"):
        if len(g) >= 15 and g["yobs"].nunique() > 1 and g[col].nunique() > 1:
            v[bw] = float(spearmanr(g[col], g["yobs"]).statistic)
    return v


def rho_diff(a: dict, b: dict, seed=SEED) -> dict:
    keys = sorted(set(a) & set(b))
    d = np.array([a[k] - b[k] for k in keys])
    draws = np.random.default_rng(seed).integers(0, len(d), size=(DRAWS, len(d)))
    lo, hi = np.percentile(d[draws].mean(1), [2.5, 97.5])
    return {"mean": round(float(d.mean()), 4), "ci95_by_site": [round(float(lo), 4), round(float(hi), 4)], "sites": len(d)}


def pdiff(f, a, b, ycol) -> dict:
    d = ((f[a] - f[ycol]) ** 2 - (f[b] - f[ycol]) ** 2).to_numpy()
    return {"mean": round(float(d.mean()), 5), "ci95": boot_mean(d, f["cluster"].to_numpy(), SEED, DRAWS),
            "ci95_week": boot_mean(d, f["week"].to_numpy(), SEED, DRAWS)}


def line_block(f: pd.DataFrame, line: int, models: list, diffs: bool = True) -> dict:
    yc = f"over{line}"
    g = f.assign(y=f[yc])
    r = {"n": int(len(f)), "events": int(g["y"].sum()), "clusters": int(f["cluster"].nunique()),
         "brier": {m: round(brier(g[m], g["y"]), 5) for m in models},
         "auc": {m: round(auc(g[m], g["y"]), 3) for m in models},
         "site_auc_mean": {m: site_auc(g, m) for m in models},
         "sites_with_both": int(sum(gg["y"].nunique() > 1 for _, gg in g.groupby("bw_id"))),
         "logloss": {m: round(logloss(g[m], g["y"]), 4) for m in models}}
    r["skill_vs_usual"] = {m: round(1 - r["brier"][m] / r["brier"]["usual"], 4) for m in models}
    if diffs:
        r["reliability"] = {m: reliability(g[m], g["y"], BINS[line]) for m in models if m not in ("usual",)}
        for c in ("A", "B", "C"):
            refs = ["production", "plain", "usual", "own", "last"] if line == 900 else ["plain", "usual", "own", "last"]
            r[f"{c}_minus"] = {ref: pdiff(g, c, ref, "y") for ref in refs}
            r[f"usual_minus_{c}"] = pdiff(g, "usual", c, "y")
    return r


def scheme_frame(df, pred, hist, scheme, line) -> pd.DataFrame:
    """The scored lake rows of one scheme with every forecast of P(over line)."""
    lk = df.loc[pred["row"]].reset_index(drop=True)
    p = pred.reset_index(drop=True)
    ref = references(lk.assign(t=lk["t"]), hist, scheme, line)
    f = pd.DataFrame({"row": lk["row"], "bw_id": lk["bw_id"], "name": lk["name"], "catchment": lk["catchment"],
                      "year": lk["year"], "cluster": lk["cluster"], "week": lk["week"], "yobs": lk["y"],
                      "over900": (lk["ecoli"] > 900).astype(int), "over500": (lk["ecoli"] > 500).astype(int)})
    for c in ("usual", "own", "last", "k", "n"):
        f[c] = ref[c].to_numpy()
    for c in ("plain", "A", "B", "C"):
        f[c] = p[f"{c}_{line}"].to_numpy()
    if line == 900:
        f["production"] = lk[f"{scheme}_production_form"].to_numpy()
        f["model466"] = lk[f"{scheme}_candidate"].to_numpy()
        f["own_rate_cand"] = shrink(f["k"].to_numpy(), f["n"].to_numpy(), f["production"].to_numpy(), 10)
    return f


def stage_run() -> None:
    from lake_own_rate_test import EVID
    df = load()
    inputs = [ATLAS, *PRED.values(), EVID, OUT / "rows.parquet"]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    lake_sites = sorted(df.loc[df.lake == 1, "bw_id"].unique())
    hist = load_history(set(lake_sites))
    res = {"schema": "swimsignal.lake-line-candidates", "version": "1.0.0", "protocol": "docs/LAKE-LINE-CANDIDATES-2026-11.md",
           "protocol_commit": "3717a7aa", "seed": SEED, "draws": DRAWS,
           "inputs_sha256": {Path(k).name: v for k, v in before.items()}, "schemes": {}}
    all_rows = []
    for scheme in SCHEMES:
        pred, fits = run_scheme(df, scheme)
        sres = {"fits": fits, "line": {}}
        for line in LINES:
            f = scheme_frame(df, pred, hist, scheme, line)
            models = ["A", "B", "C", "plain", "usual", "own", "last"] + (["production", "model466", "own_rate_cand"] if line == 900 else [])
            b = line_block(f, line, models)
            b["by_water_body"] = {k: line_block(g, line, models, diffs=False) for k, g in f.groupby("catchment")}
            b["by_year"] = {str(k): line_block(g, line, models, diffs=False) for k, g in f.groupby("year")}
            b["without_derwent_water"] = line_block(f[f["catchment"] != "Derwent Water"].reset_index(drop=True), line, models)
            sres["line"][str(line)] = b
            if line == 900:
                f900 = f
        # the concentration
        lk = df.loc[pred["row"]].reset_index(drop=True)
        pr = pred.reset_index(drop=True)
        c = pd.DataFrame({"bw_id": lk["bw_id"], "yobs": lk["y"], "cluster": lk["cluster"], "week": lk["week"],
                          "plain_med": pr["plain_med"], "B_med": pr["B_med"], "production": lk[f"{scheme}_production_form"],
                          "model466_med": lk[f"{scheme}_candidate_median"]})
        d = (pr["B_ls"] - pr["plain_ls"]).to_numpy()
        rhos = {k: site_rho(c, k) for k in ("plain_med", "B_med", "production", "model466_med")}
        sres["concentration"] = {
            "logscore": {"plain": round(float(pr["plain_ls"].mean()), 4), "B": round(float(pr["B_ls"].mean()), 4)},
            "B_minus_plain": {"mean": round(float(d.mean()), 4), "ci95": boot_mean(d, c["cluster"].to_numpy(), SEED, DRAWS),
                              "ci95_week": boot_mean(d, c["week"].to_numpy(), SEED, DRAWS)},
            "central80": {k: round(float(((pr[f"{k}_pit"] >= 0.1) & (pr[f"{k}_pit"] <= 0.9)).mean()), 4) for k in ("plain", "B")},
            "site_rho": {k: {"mean": round(float(np.mean(list(v.values()))), 4), "sites": len(v),
                             "by_site": {kk: round(vv, 3) for kk, vv in v.items()}} for k, v in rhos.items()},
            "rho_B_minus_plain": rho_diff(rhos["B_med"], rhos["plain_med"]),
            "rho_plain_minus_production": rho_diff(rhos["plain_med"], rhos["production"])}
        res["schemes"][scheme] = sres
        all_rows.append(f900.assign(scheme=scheme, **{f"{k}_500": scheme_frame(df, pred, hist, scheme, 500)[k].to_numpy()
                                                      for k in ("A", "B", "C", "plain", "usual")},
                                    plain_med=pr["plain_med"].to_numpy(), B_med=pr["B_med"].to_numpy()))
        log.info("scheme %s done", scheme)
    res["checks"], res["logged"] = conditions(res)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    assert before == after, "an input changed during the run"
    Path(f"{DOC}-scores.json").write_text(json.dumps(res, indent=1, default=float) + "\n")
    pd.concat(all_rows, ignore_index=True).round(6).to_csv(f"{DOC}-rows.csv", index=False)
    print(json.dumps({"checks": res["checks"], "logged": res["logged"]}, indent=1))


def conditions(res: dict) -> tuple[dict, list]:
    S = res["schemes"]
    m9 = S[MAIN]["line"]["900"]
    out = {}
    for c in ("A", "C"):
        out[f"{c}: A1 Brier at 900 below production, interval below zero"] = bool(m9[f"{c}_minus"]["production"]["ci95"][1] < 0)
        out[f"{c}: A2 skill over the usual rate at least 0.10, interval above zero"] = bool(
            m9["skill_vs_usual"][c] >= SKILL_MARGIN and m9[f"usual_minus_{c}"]["ci95"][0] > 0)
        out[f"{c}: A3 (reported) Brier at or below plain"] = bool(m9["brier"][c] <= m9["brier"]["plain"])
    con = S[MAIN]["concentration"]
    out["B: B1 log score above plain, interval above zero"] = bool(con["B_minus_plain"]["ci95"][0] > 0)
    out["B: B2 mean within-site rho above plain (point)"] = bool(con["rho_B_minus_plain"]["mean"] > 0)
    logged = []
    for c in ("A", "B", "C"):
        n1 = all(S[s]["line"]["900"][f"{c}_minus"]["production"]["ci95"][1] < N1_MARGIN for s in SCHEMES)
        n2 = all(S[s]["line"]["500"][f"{c}_minus"]["plain"]["ci95"][1] < N2_MARGIN for s in SCHEMES)
        n3 = True if c == "A" else all(S[s]["concentration"]["B_minus_plain"]["ci95"][0] > N3_MARGIN for s in ("loyo", "fwd"))
        w = m9["without_derwent_water"]
        n4 = bool(w["brier"][c] <= w["brier"]["usual"] + N4_MARGIN)
        out[f"{c}: N1 vs production at 900, upper end below +0.002, all schemes"] = n1
        out[f"{c}: N2 vs plain at 500, upper end below +0.004, all schemes"] = n2
        out[f"{c}: N3 concentration not worse than plain by 0.02 (main, forward)"] = n3
        out[f"{c}: N4 without Derwent Water, at most usual + 0.001"] = n4
        if n1 and n2 and n3 and n4:
            logged.append(c)
    return out, logged


# ------------------------------------------------------------------ diagnosis (described only)
def stage_diagnose() -> None:
    df = load()
    d = df[df["catchment"] == "Derwent Water"].copy()
    rows = pd.read_csv(f"{DOC}-rows.csv")
    r = rows[(rows["scheme"] == MAIN) & (rows["catchment"] == "Derwent Water")].set_index("row")
    d = d.set_index("row").join(r[["A", "B", "C", "plain", "production", "usual", "own"]])
    d["month"] = d["t"].dt.tz_convert("Europe/London").dt.month
    by_year = d.groupby("year").agg(samples=("ecoli", "size"), over900=("ecoli", lambda v: int((v > 900).sum())),
                                    over500=("ecoli", lambda v: int((v > 500).sum())),
                                    median_count=("ecoli", "median"), rain48_median=("rain48_fc", "median"),
                                    rain48_mean=("rain48_fc", "mean"), wet_samples_over10mm=("rain48_fc", lambda v: int((v > 10).sum())),
                                    exposure_median=("risk_lead0", "median"), exposure_max=("risk_lead0", "max"),
                                    first=("t", "min"), last=("t", "max"))
    over = d[d["ecoli"] > 900][["t", "ecoli", "rain48_fc", "rain_48h", "risk_lead0", "A", "B", "plain", "production"]]
    corr = {str(y): {"rho_rain48": round(float(spearmanr(g["rain48_fc"], g["y"]).statistic), 3),
                     "rho_exposure": round(float(spearmanr(g["risk_lead0"], g["y"]).statistic), 3)}
            for y, g in d.groupby("year")}
    other = df[(df["lake"] == 1) & (df["catchment"] != "Derwent Water")]
    out = {"note": "Diagnosis only: described, not used in any scored candidate.",
           "by_year": json.loads(by_year.to_json(date_format="iso")),
           "over_900_samples": json.loads(over.assign(t=over["t"].astype(str)).to_json(orient="records")),
           "within_year_rank_correlation": corr,
           "other_lakes_by_year": json.loads(other.groupby("year").agg(rain48_median=("rain48_fc", "median"),
                                                                      exposure_median=("risk_lead0", "median"),
                                                                      over900=("ecoli", lambda v: int((v > 900).sum()))).to_json())}
    Path(f"{DOC}-derwent.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))


# ------------------------------------------------------------------ freeze plain and B for the 2027 read
FROZEN = ROOT / "data" / "research" / "lake_line_frozen.v1.json"


def frozen_probs(f: dict, rain_48h, rain_24h, risk, when, bw: str | None) -> dict:
    """Every frozen candidate's P(over 900), P(over 500) and B's median, from the file alone (numpy only): what the
    2027 read computes from shadow_lake_range_v1's logged inputs. `bw` None is a lake without its own samples."""
    from dipcast.model.ecoli import features
    n = len(rain_48h)
    X = features(rain_48h, rain_24h, risk, np.ones(n), when)
    w = f["B"]["wet"]
    raw = ((X["lrain48"] - w["m48"]) / w["s48"] + (X["logit_risk"] - w["mr"]) / w["sr"]) / 2
    X["lake_x_wet"] = (raw - w["mw"]) / w["sw"]
    out = {}
    for nm in ("plain", "B"):
        m = f[nm]
        Z = np.column_stack([np.ones(n)] + [(X[c].to_numpy(float) - m["mean"][c]) / m["sd"][c] for c in m["cols"]])
        mu = (Z @ np.asarray(m["beta"]))[:, None]
        if nm == "plain":
            mu = mu + np.sqrt(2.0) * m["tau"] * np.asarray(m["nodes"])[None, :]
        else:
            mu = mu + m["tau"] * np.asarray(m["gu"])[None, :] + \
                m["tau_v"] * X["lake_x_wet"].to_numpy(float)[:, None] * np.asarray(m["gv"])[None, :]
        lw = np.asarray(m["log_weights"][bw] if bw is not None else m["log_prior"])
        wt = np.exp(lw - logsumexp(lw))[None, :]
        for line in LINES:
            p = (wt * ndtr((mu - np.log10(line)) / m["sigma_lake"])).sum(1)
            out[f"{nm}_{line}"] = p
            out[f"{'A' if nm == 'plain' else 'C'}_{line}"] = apply_map(p, tuple(f["maps"][f"{nm}_{line}"]))
        if nm == "B":
            lo, hi = np.full(n, -2.0), np.full(n, 7.0)
            for _ in range(40):
                mid = (lo + hi) / 2
                below = (wt * ndtr((mid[:, None] - mu) / m["sigma_lake"])).sum(1) < 0.5
                lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
            out["B_median"] = 10 ** ((lo + hi) / 2)
    return out


def stage_export() -> None:
    """Freeze plain and B (with A's and C's maps), fitted on all 1,537 rows, for the 2027 read in the record. Not a
    logger and not loaded by the site: the 2027 read computes them from shadow_lake_range_v1's logged inputs."""
    res = json.loads(Path(f"{DOC}-scores.json").read_text())
    df = load()
    plain, b, wet = fit_both(df)
    assert plain.converged and b.converged
    maps = inner_maps(df)
    lake_sites = sorted(df.loc[df.lake == 1, "bw_id"].unique())
    spots = pd.read_csv(ROOT / "spots.csv").set_index("id")

    def logw(m):
        post = m.train_post - logsumexp(m.train_post, axis=1, keepdims=True)
        return {bw: np.round(post[m.sites.get_loc(bw)], 8).tolist() for bw in lake_sites}

    dw, _ = add_wet(df, df)
    out = {"rule": "lake-line-frozen-v1", "record": "docs/LAKE-LINE-CANDIDATES-2026-11.md",
           "status": "frozen for the 2027 read; not logged, not shown, not loaded by the site",
           "guardrails_met": res["logged"],
           "target": "P(E. coli over 900 and over 500 per 100 ml) in a lake sample; B also the median",
           "fitted_on": {"rows": len(df), "lake_rows": int((df.lake == 1).sum()), "sites": int(df["bw_id"].nunique()),
                         "first": str(df["t"].min().date()), "last": str(df["t"].max().date())},
           "sites": {bw: {"name": str(spots.loc[f"bw-{bw}", "name"]), "lat": round(float(spots.loc[f"bw-{bw}", "lat"]), 6),
                          "lon": round(float(spots.loc[f"bw-{bw}", "lon"]), 6)} for bw in lake_sites},
           "plain": {"cols": PROD, "mean": {c: float(df[c].mean()) for c in PROD},
                     "sd": {c: float(df[c].std(ddof=0)) or 1.0 for c in PROD}, "beta": plain.theta[:plain.p].tolist(),
                     "sigma_lake": plain.sigma_lake, "tau": plain.tau, "nodes": plain.x.tolist(),
                     "log_prior": plain.logw.tolist(), "log_weights": logw(plain)},
           "B": {"cols": B_COLS, "mean": {c: float(dw[c].mean()) for c in B_COLS},
                 "sd": {c: float(dw[c].std(ddof=0)) or 1.0 for c in B_COLS}, "wet": wet, "beta": b.theta[:b.p].tolist(),
                 "sigma_lake": b.sigma_lake, "tau": b.tau, "tau_v": b.tau_v, "gu": b.gu.tolist(), "gv": b.gv.tolist(),
                 "log_prior": b.logw.tolist(), "log_weights": logw(b)},
           "maps": {k: list(v) for k, v in maps.items() if not k.startswith("_")},
           "usual_rate_2023_26": {str(line): round(float(load_history(set(lake_sites))[f"over{line}"].mean()), 5)
                                  for line in LINES}}
    from dipcast.model.ecoli import features
    when = pd.Series(pd.Timestamp("2026-07-01 12:00", tz="Europe/London"), index=range(2))
    X = features([0.0, 25.0], [0.0, 15.0], [0.002, 0.08], [1.0, 1.0], when)
    Xw = add_wet_with(X, wet)
    checks = []
    for bw in ("ukd1203-45650", "ukd1101-45800", "unsampled"):
        site = np.array([bw, bw])
        for i in range(2):
            ck = {"site": bw, "rain_48h": [0.0, 25.0][i], "rain_24h": [0.0, 15.0][i], "risk": [0.002, 0.08][i],
                  "day": "2026-07-01"}
            for line in LINES:
                pp, pb = plain.p_over(X, site, np.log10(line))[i], b.p_over(Xw, site, np.log10(line))[i]
                ck[f"plain_{line}"], ck[f"B_{line}"] = float(pp), float(pb)
                ck[f"A_{line}"] = float(apply_map(np.array([pp]), maps[f"plain_{line}"])[0])
                ck[f"C_{line}"] = float(apply_map(np.array([pb]), maps[f"B_{line}"])[0])
            ck["B_median"] = float(10 ** median_of(b, Xw, site)[i])
            checks.append(ck)
    out["checks"] = checks
    FROZEN.write_text(json.dumps(out, indent=1) + "\n")
    print(FROZEN, hashlib.sha256(FROZEN.read_bytes()).hexdigest())
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    {"rows": stage_rows, "run": stage_run, "diagnose": stage_diagnose, "export": stage_export}[sys.argv[1]]()
