"""A catchment-aware distribution of log10 E. coli at inland bathing waters: audit, misses atlas and one bounded
exploratory comparison (docs/CONCENTRATION-STUDY-2026-11.md). Off CI, by hand, offline:

    DIPCAST_ROOT=<checkout with data> uv run python scripts/concentration_study.py audit
    DIPCAST_ROOT=<checkout with data> uv run python scripts/concentration_study.py atlas
    DIPCAST_ROOT=<checkout with data> uv run python scripts/concentration_study.py run

The rows are train_ecoli.py's (scripts/soil_moisture_eval/diagnostics.rows_q1): EA statutory samples at inland bathing
waters with overflows upstream, 2024-26, with archived lead-0 forecast rain and replayed lead-0 exposure; plus
soil moisture at issue (leads.soil_at_issue) and the lab's qualifier joined back from bwq_samples.parquet. Nothing here
writes to a model path, to data/eval2027 or to anything the 2027 pre-registration hashes or watches.

The candidate is a censored normal model of log10 E. coli with a random intercept per bathing water (its background),
integrated out by Gauss-Hermite quadrature, and shared fixed responses to rain, upstream exposure, soil moisture and
season. "<10" is a left-censored value at 10 and ">10000" a right-censored value at 10,000, as the lab reports them.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import norm, spearmanr

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent / "docs" / "CONCENTRATION-STUDY-2026-11"
LOW, HIGH = 10.0, 10_000.0            # the lab's reported limits: "<10" and ">10000"
CUT = np.log10(900.0)
WARN_AT = 0.25                        # forecast_log.ECOLI_WARN_AT: rivers, the site's warning line
WET_MM = 10.0                         # train_ecoli.HEAVY_RAIN_MM: a 48 h total above this is a wet sample
N_NODES = 24
N_BOOT = 2000
PROD = ["lrain48", "lrain24", "logit_risk", "lake", "lake_x_lrain48", "doy_sin", "doy_cos"]   # ecoli.FEATURES
PROD_SM = PROD + ["sm"]                                                                       # ecoli_model_sm.json
RAIN_SEASON = ["lrain48", "lrain24", "lake", "lake_x_lrain48", "doy_sin", "doy_cos"]          # train_ecoli's variant
CANDIDATE = PROD_SM
BACKGROUND = ["lake"]

# Connected water, fixed before any score: sites that share a river system above tidal water, or one lake, form one
# group, so a held-out group never has a connected site in training. Wharfe is apart from the Nidd and Swale (it meets
# the Ouse below its tidal limit, spot_links.py). Ham and Kingston is above Teddington, so on the non-tidal Thames.
CATCHMENT = {
    "uke4100-08901": "Wharfe", "uke4200-08904": "Wharfe",
    "uke2203-08903": "Ouse (Nidd, Swale)", "uke2204-08905": "Ouse (Nidd, Swale)",
    "ukf2208-09701": "Rutland Water", "ukf2208-09702": "Rutland Water",
    "ukf1400-09750": "Colwick", "ukh1201-09801": "Cam", "ukh1406-10712": "Waveney", "ukh1401-11051": "Suffolk Stour",
    "ukk1302-11760": "Cotswold Country Park",
    "uki1101-11910": "Hampstead Heath", "uki1101-11920": "Hampstead Heath", "uki1101-11930": "Hampstead Heath",
    "uki1106-11940": "Serpentine",
    "ukj1102-11941": "Thames", "uki2203-11942": "Thames", "ukj1402-11946": "Thames", "ukj1403-11947": "Thames",
    "ukj2310-11945": "Frensham",
    "ukj3308-19001": "Hampshire Avon", "ukk1500-19002": "Hampshire Avon",
    "ukk2304-35201": "Tone", "ukk1100-36050": "Henleaze", "ukk2301-36051": "Somerset Frome",
    "ukg2200-36060": "Severn", "ukg2100-36070": "Severn", "ukg2200-36071": "Severn",
    "ukd6300-40752": "Dee",
    "ukd1203-45625": "Windermere", "ukd1203-45650": "Windermere", "ukd1203-45675": "Windermere", "ukd1203-45700": "Windermere",
    "ukd1230-45725": "Coniston Water", "ukd1230-45750": "Coniston Water", "ukd1230-45775": "Coniston Water",
    "ukd1101-45800": "Derwent Water", "ukd4308-46501": "Ribble",
}


# ------------------------------------------------------------------ data
def load_rows() -> pd.DataFrame:
    """The study rows, one per distinct sample, with every input and the lab's qualifier."""
    sys.path[:0] = [str(HERE), str(HERE / "soil_moisture_eval")]
    from diagnostics import rows_q1
    from leads import soil_at_issue

    from dipcast import config
    from dipcast.model.ecoli import features
    rows, fc = rows_q1()
    soil = Path(os.environ.get("CONC_SOIL_DIR", str(config.CACHE / "soil")))
    X = features(fc[0][0], fc[0][1], rows["risk_lead0"], rows["lake"], rows["sample_time"])
    X["sm"] = soil_at_issue(rows, soil, 0)
    df = pd.concat([rows.reset_index(drop=True), X.reset_index(drop=True)], axis=1)
    df = df.loc[:, ~df.columns.duplicated()]
    df["n_listed"] = df.groupby(["bw_id", "sample_time"])["ecoli"].transform("size")
    n_before = len(df)
    df = df.drop_duplicates(["bw_id", "sample_time"]).reset_index(drop=True)
    df.attrs["repeats_dropped"] = n_before - len(df)
    raw = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates(["bw_id", "sample_time"])
    q = raw.set_index(["bw_id", "sample_time"])["ecoli_qual"]
    df["qual"] = q.reindex(pd.MultiIndex.from_frame(df[["bw_id", "sample_time"]])).to_numpy()
    return prepare(df)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["y"] = np.log10(df["ecoli"].clip(lower=1).astype(float))
    df["cens"] = np.select([df["qual"].eq("<"), df["qual"].eq(">")], [-1, 1], 0)
    df["over"] = (df["ecoli"] > 900).astype(int)
    df["year"] = df["sample_time"].dt.year
    iso = df["sample_time"].dt.isocalendar()
    df["week"] = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    df["catchment"] = df["bw_id"].map(CATCHMENT)
    df["wet"] = df["rain_48h"] > WET_MM
    return df


# ------------------------------------------------------------------ the censored random-intercept model
def _std(X: pd.DataFrame, cols: list[str], ref: pd.DataFrame | None = None) -> np.ndarray:
    """Standardised columns with an intercept, using `ref`'s means and SDs (the training fold) when given."""
    ref = X if ref is None else ref
    mu, sd = ref[cols].mean(), ref[cols].std(ddof=0).replace(0, 1.0)
    return np.column_stack([np.ones(len(X)), ((X[cols] - mu) / sd).to_numpy(dtype=float)])


def row_loglik(mu: np.ndarray, sigma: float, y: np.ndarray, cens: np.ndarray) -> np.ndarray:
    """log density (log10 scale) or log mass of each observation; mu may be [n] or [n, K]."""
    y = y.reshape(-1, *([1] * (mu.ndim - 1)))
    c = cens.reshape(-1, *([1] * (mu.ndim - 1)))
    z = (y - mu) / sigma
    return np.where(c < 0, norm.logcdf(z), np.where(c > 0, norm.logsf(z), norm.logpdf(z) - np.log(sigma)))


class CensoredRI:
    """y = Z beta + u_site + e; e ~ N(0, sigma^2), u ~ N(0, tau^2), y censored as the lab reports it."""

    def __init__(self, cols: list[str], n_nodes: int = N_NODES):
        self.cols = cols
        x, w = np.polynomial.hermite.hermgauss(n_nodes)
        self.x, self.logw = x, np.log(w / np.sqrt(np.pi))

    def _node_ll(self, theta, Z, y, cens):
        p = Z.shape[1]
        beta, sigma, tau = theta[:p], np.exp(theta[p]), np.exp(theta[p + 1])
        mu = (Z @ beta)[:, None] + np.sqrt(2.0) * tau * self.x[None, :]
        return row_loglik(mu, sigma, y, cens)

    def _site_post(self, ll: np.ndarray, site: np.ndarray, n_sites: int) -> np.ndarray:
        """log weights over nodes per site: prior weight plus the site's summed log-likelihood."""
        S = np.zeros((n_sites, ll.shape[1]))
        np.add.at(S, site, ll)
        return self.logw[None, :] + S

    def fit(self, X: pd.DataFrame, y: np.ndarray, cens: np.ndarray, site: np.ndarray) -> CensoredRI:
        self.ref = X[self.cols].copy()
        Z = _std(X, self.cols)
        self.sites = pd.Index(np.unique(site))
        si = self.sites.get_indexer(site)
        ok = cens == 0
        b0 = np.linalg.lstsq(Z[ok], y[ok], rcond=None)[0]
        s0 = float(np.std(y[ok] - Z[ok] @ b0)) or 1.0
        theta0 = np.concatenate([b0, [np.log(s0 * 0.8), np.log(s0 * 0.5)]])

        def nll(theta):
            post = self._site_post(self._node_ll(theta, Z, y, cens), si, len(self.sites))
            return -float(logsumexp(post, axis=1).sum())

        p = Z.shape[1]
        bounds = [(None, None)] * p + [(-5, 3), (-6, 2)]
        res = minimize(nll, theta0, method="L-BFGS-B", bounds=bounds)
        self.theta, self.converged, self.nll = res.x, bool(res.success), float(res.fun)
        self.train_post = self._site_post(self._node_ll(self.theta, Z, y, cens), si, len(self.sites))
        self.sigma, self.tau = float(np.exp(self.theta[p])), float(np.exp(self.theta[p + 1]))
        return self

    def _weights_mu(self, X: pd.DataFrame, site: np.ndarray):
        Z = _std(X, self.cols, ref=self.ref)
        mu = Z @ self.theta[: Z.shape[1]]
        si = self.sites.get_indexer(site)
        logp = np.where((si >= 0)[:, None], self.train_post[np.clip(si, 0, None)], self.logw[None, :])
        w = np.exp(logp - logsumexp(logp, axis=1, keepdims=True))
        u = np.sqrt(2.0) * self.tau * self.x
        return w, mu, u

    def p_over(self, X: pd.DataFrame, site: np.ndarray, cut: float = CUT) -> np.ndarray:
        w, mu, u = self._weights_mu(X, site)
        return (w * norm.sf((cut - mu[:, None] - u[None, :]) / self.sigma)).sum(1)

    def cdf(self, X: pd.DataFrame, site: np.ndarray, yv: np.ndarray) -> np.ndarray:
        w, mu, u = self._weights_mu(X, site)
        return (w * norm.cdf((yv[:, None] - mu[:, None] - u[None, :]) / self.sigma)).sum(1)

    def log_score(self, X: pd.DataFrame, site: np.ndarray, y: np.ndarray, cens: np.ndarray) -> np.ndarray:
        w, mu, u = self._weights_mu(X, site)
        ll = row_loglik(mu[:, None] + u[None, :], self.sigma, y, cens)
        return logsumexp(np.log(np.clip(w, 1e-300, None)) + ll, axis=1)

    def pit(self, X: pd.DataFrame, site: np.ndarray, y: np.ndarray, cens: np.ndarray, rng) -> np.ndarray:
        """Randomised PIT: F(y) for a counted value; uniform on (0, F(10)) below the limit, on (F(10000), 1) above it."""
        F = self.cdf(X, site, y)
        v = rng.uniform(size=len(y))
        return np.where(cens < 0, v * F, np.where(cens > 0, F + v * (1 - F), F))


# ------------------------------------------------------------------ comparators and folds
def logistic(train: pd.DataFrame, test: pd.DataFrame, cols: list[str]) -> np.ndarray:
    sys.path.insert(0, str(HERE))
    from dipcast.model.ecoli import fit
    return fit(train, train["over"].to_numpy(), cols).predict(test)


def production_form(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """As the site serves it: the soil-moisture model for river spots, the seven-input model for lakes; both fitted on
    every training row, rivers and lakes together, as production's were."""
    p_r, p_l = logistic(train, test, PROD_SM), logistic(train, test, PROD)
    return np.where(test["lake"].to_numpy() == 1.0, p_l, p_r)


def folds(df: pd.DataFrame, scheme: str):
    """(name, train mask, test mask). fwd: earlier years predict a later one. loyo: each year from the others.
    loso: each site from the others. cxy: each (connected group, year) from rows in neither that group nor that year."""
    yr, site, grp = df["year"].to_numpy(), df["bw_id"].to_numpy(), df["catchment"].to_numpy()
    if scheme == "fwd":
        for y in (2025, 2026):
            yield str(y), yr < y, yr == y
    elif scheme == "loyo":
        for y in np.unique(yr):
            yield str(y), yr != y, yr == y
    elif scheme == "loso":
        for s in np.unique(site):
            yield s, site != s, site == s
    elif scheme == "cxy":
        for g in np.unique(grp):
            for y in np.unique(yr):
                te = (grp == g) & (yr == y)
                if te.any():
                    yield f"{g}|{y}", (grp != g) & (yr != y), te


def predict_all(df: pd.DataFrame, scheme: str, with_candidates: bool = True) -> pd.DataFrame:
    """Out-of-fold P(>900) from every predictor, and the distribution scores of the two censored models."""
    rng = np.random.default_rng(0)
    out = []
    for name, tr, te in folds(df, scheme):
        a, b = df[tr], df[te]
        r = pd.DataFrame({"row": np.flatnonzero(te), "fold": name})
        r["seen_site"] = b["bw_id"].isin(set(a["bw_id"])).to_numpy()
        r["production_form"] = production_form(a, b)
        r["rain_season"] = logistic(a, b, RAIN_SEASON)
        r["climatology_by_type"] = np.where(b["lake"].to_numpy() == 1, a.loc[a["lake"] == 1, "over"].mean(),
                                            a.loc[a["lake"] == 0, "over"].mean())
        if with_candidates:
            for nm, cols in (("background", BACKGROUND), ("candidate", CANDIDATE)):
                m = CensoredRI(cols).fit(a, a["y"].to_numpy(), a["cens"].to_numpy(), a["bw_id"].to_numpy())
                s = b["bw_id"].to_numpy()
                r[nm] = m.p_over(b, s)
                r[f"{nm}_logscore"] = m.log_score(b, s, b["y"].to_numpy(), b["cens"].to_numpy())
                r[f"{nm}_pit"] = m.pit(b, s, b["y"].to_numpy(), b["cens"].to_numpy(), rng)
                r[f"{nm}_median"] = median_from(m, b, s)
                r[f"{nm}_converged"] = m.converged
                r[f"{nm}_tau"], r[f"{nm}_sigma"] = m.tau, m.sigma
        out.append(r)
    return pd.concat(out, ignore_index=True).sort_values("row").reset_index(drop=True)


def median_from(m: CensoredRI, X: pd.DataFrame, site: np.ndarray) -> np.ndarray:
    """The predictive median of log10 E. coli, by bisection on the mixture CDF."""
    lo, hi = np.full(len(X), -2.0), np.full(len(X), 7.0)
    for _ in range(40):
        mid = (lo + hi) / 2
        below = m.cdf(X, site, mid) < 0.5
        lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
    return (lo + hi) / 2


# ------------------------------------------------------------------ scores
def boot_diff(d: np.ndarray, cluster: np.ndarray, n: int = N_BOOT, seed: int = 0) -> tuple[float, float]:
    """95% interval of the mean of d, resampling whole clusters (ISO weeks: one storm reaches many sites)."""
    codes, inv = np.unique(cluster, return_inverse=True)
    s, c = np.bincount(inv, weights=d), np.bincount(inv).astype(float)
    draws = np.random.default_rng(seed).integers(0, len(codes), size=(n, len(codes)))
    stat = s[draws].sum(1) / c[draws].sum(1)
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return float(lo), float(hi)


def warn_counts(y: np.ndarray, p: np.ndarray, at: float = WARN_AT) -> dict:
    w = p >= at
    return {"n": int(len(y)), "over": int(y.sum()), "hits": int((w & (y == 1)).sum()),
            "false_reassurance": int((~w & (y == 1)).sum()), "false_alarms": int((w & (y == 0)).sum()),
            "quiet_correct": int((~w & (y == 0)).sum())}


def within_site_rho(df: pd.DataFrame, score: np.ndarray, mask: np.ndarray, min_n: int = 15) -> dict:
    """Median over sites (with at least min_n rows) of Spearman's rho between a score and log10 E. coli."""
    vals = {}
    for s, g in df[mask].groupby("bw_id"):
        if len(g) >= min_n and g["y"].nunique() > 1:
            vals[s] = float(spearmanr(score[g.index], g["y"]).statistic)
    v = np.array(list(vals.values()))
    return {"sites": len(v), "median": float(np.median(v)) if len(v) else None,
            "positive": int((v > 0).sum()) if len(v) else 0}


def brier_split(y: np.ndarray, p: np.ndarray, site: np.ndarray) -> dict:
    """Brier = between-site part (site mean forecast against site rate) + within-site part (the rest)."""
    d = pd.DataFrame({"y": y, "p": p, "s": site})
    g = d.groupby("s").agg(n=("y", "size"), ybar=("y", "mean"), pbar=("p", "mean"))
    between = float((g["n"] * (g["pbar"] - g["ybar"]) ** 2).sum() / len(d))
    total = float(((d["p"] - d["y"]) ** 2).mean())
    return {"brier": total, "between_site": between, "within_site": total - between}


# ------------------------------------------------------------------ stages
def stage_audit() -> None:
    from dipcast import config
    raw = pd.read_parquet(config.RAW / "bwq_samples.parquet")
    df = load_rows()
    a = {"raw_rows": len(raw), "raw_distinct_samples": int((~raw.duplicated(["bw_id", "sample_time"])).sum()),
         "raw_repeated_rows": int(raw.duplicated(["bw_id", "sample_time"]).sum()),
         "raw_qualifiers": raw["ecoli_qual"].value_counts().to_dict(),
         "raw_censored_values": {q: sorted(raw.loc[raw["ecoli_qual"] == q, "ecoli"].unique().tolist()) for q in ("<", ">")},
         "raw_years": raw["sample_time"].dt.year.value_counts().sort_index().to_dict(),
         "study_rows_before_repeats": len(df) + df.attrs["repeats_dropped"], "study_rows": len(df),
         "study_repeat_rows_dropped": df.attrs["repeats_dropped"], "study_samples_listed_more_than_once": int((df["n_listed"] > 1).sum()),
         "study_qual_missing": int(df["qual"].isna().sum()),
         "study_sites": int(df["bw_id"].nunique()), "study_groups": int(df["catchment"].nunique()),
         "study_site_years": int(df.groupby(["bw_id", "year"]).ngroups)}
    tab = (df.groupby(["kind", "year"]).agg(rows=("y", "size"), sites=("bw_id", "nunique"), over_900=("over", "sum"),
                                            below_10=("cens", lambda c: int((c < 0).sum())),
                                            above_10000=("cens", lambda c: int((c > 0).sum())),
                                            wet=("wet", "sum"), wet_over=("over", lambda o: int(o[df.loc[o.index, "wet"]].sum())))
           .reset_index())
    per_site = (df.groupby(["bw_id", "name", "kind", "catchment"]).agg(
        rows=("y", "size"), years=("year", "nunique"), first=("year", "min"), over_900=("over", "sum"),
        below_10=("cens", lambda c: int((c < 0).sum())), wet=("wet", "sum"), median_log10=("y", "median"),
        sd_log10=("y", "std")).reset_index())
    tab.to_csv(f"{DOCS}-audit-by-year.csv", index=False)
    per_site.to_csv(f"{DOCS}-audit-by-site.csv", index=False)
    with open(f"{DOCS}-audit.json", "w") as f:
        json.dump(a, f, indent=2, default=int)
    print(json.dumps(a, indent=2, default=int))
    print(tab.to_string(index=False))


def stage_atlas() -> None:
    """Production-form predictions out of fold (refitted within each fold; retrospective, not issued), and where they
    miss: false reassurance (over 900, forecast under 0.25) and false alarms (under, forecast 0.25 or more)."""
    df = load_rows()
    rows = []
    preds = {}
    for scheme in ("fwd", "loyo", "loso"):
        p = predict_all(df, scheme, with_candidates=False)
        preds[scheme] = p
        d = df.loc[p["row"]].reset_index(drop=True).assign(p=p["production_form"].to_numpy(), seen=p["seen_site"].to_numpy())
        d["month"] = d["sample_time"].dt.month
        d["coverage"] = np.where(d["miss_lead0"].fillna(0) > 0, "some upstream rain missing", "complete")
        for by in ("kind", "bw_id", "month", "wet", "coverage", "catchment"):
            for k, g in d.groupby(by):
                rows.append({"scheme": scheme, "by": by, "group": str(k), **warn_counts(g["over"].to_numpy(), g["p"].to_numpy()),
                             **brier_split(g["over"].to_numpy(), g["p"].to_numpy(), g["bw_id"].to_numpy()),
                             "mean_forecast": float(g["p"].mean()), "observed": float(g["over"].mean())})
    pd.DataFrame(rows).to_csv(f"{DOCS}-atlas.csv", index=False)
    keep = df[["bw_id", "name", "kind", "catchment", "sample_time", "ecoli", "qual", "rain_48h", "risk_lead0", "sm"]]
    for scheme, p in preds.items():
        keep = keep.assign(**{f"p_{scheme}": p.set_index("row")["production_form"].reindex(range(len(df))).to_numpy()})
    keep.to_csv(f"{DOCS}-atlas-rows.csv", index=False)
    print(pd.DataFrame(rows).query("by in ['kind', 'wet', 'coverage']").to_string(index=False))


def stage_run() -> None:
    df = load_rows()
    res, tables = {}, []
    for scheme in ("fwd", "loyo", "cxy"):
        p = predict_all(df, scheme)
        p.to_csv(f"{DOCS}-predictions-{scheme}.csv", index=False)
        d = df.loc[p["row"]].reset_index(drop=True)
        y, wk = d["over"].to_numpy(), d["week"].to_numpy()
        for kind in ("river", "lake"):
            for seen in ((True,), (False,), (True, False)):
                m = (d["kind"].to_numpy() == kind) & p["seen_site"].isin(seen).to_numpy()
                if m.sum() < 20:
                    continue
                label = {(True,): "seen sites", (False,): "new sites", (True, False): "all"}[seen]
                row = {"scheme": scheme, "kind": kind, "sites": label, "n": int(m.sum()), "over": int(y[m].sum())}
                for nm in ("candidate", "background", "production_form", "rain_season", "climatology_by_type"):
                    row[f"brier_{nm}"] = float(((p.loc[m, nm] - y[m]) ** 2).mean())
                    row.update({f"{k}_{nm}": v for k, v in warn_counts(y[m], p.loc[m, nm].to_numpy()).items() if k != "n"})
                for ref in ("background", "production_form"):
                    dd = (p.loc[m, "candidate"] - y[m]) ** 2 - (p.loc[m, ref] - y[m]) ** 2
                    row[f"cand_minus_{ref}"], row[f"cand_minus_{ref}_ci"] = float(dd.mean()), boot_diff(dd.to_numpy(), wk[m])
                dl = (p.loc[m, "candidate_logscore"] - p.loc[m, "background_logscore"]).to_numpy()
                row["logscore_candidate"] = float(p.loc[m, "candidate_logscore"].mean())
                row["logscore_background"] = float(p.loc[m, "background_logscore"].mean())
                row["logscore_diff_ci"] = boot_diff(dl, wk[m])
                pit = p.loc[m, "candidate_pit"].to_numpy()
                row["pit_central80"] = float(((pit >= 0.1) & (pit <= 0.9)).mean())
                row["pit_deciles"] = np.histogram(pit, bins=10, range=(0, 1))[0].tolist()
                row["pit_central80_background"] = float(((p.loc[m, "background_pit"] >= 0.1) & (p.loc[m, "background_pit"] <= 0.9)).mean())
                mm = np.zeros(len(df), bool)
                mm[p.loc[m, "row"]] = True
                full = lambda col: pd.Series(p.set_index("row")[col]).reindex(range(len(df))).to_numpy()  # noqa: E731
                row["within_site_rho_candidate_median"] = within_site_rho(df, full("candidate_median"), mm)
                row["within_site_rho_production_form"] = within_site_rho(df, full("production_form"), mm)
                row["within_site_rho_background_median"] = within_site_rho(df, full("background_median"), mm)
                tables.append(row)
        res[scheme] = {"converged_candidate": float(p["candidate_converged"].mean()),
                       "converged_background": float(p["background_converged"].mean()),
                       "tau_candidate": sorted(set(np.round(p["candidate_tau"], 3))),
                       "sigma_candidate": sorted(set(np.round(p["candidate_sigma"], 3)))}
    t = pd.DataFrame(tables)
    t.to_json(f"{DOCS}-scores.json", orient="records", indent=1)
    prim = t[(t.scheme == "fwd") & (t.kind == "river") & (t.sites == "seen sites")].iloc[0]
    checks = {
        "P1a candidate beats background, interval below zero": bool(prim["cand_minus_background_ci"][1] < 0),
        "P1b candidate beats production form, interval below zero": bool(prim["cand_minus_production_form_ci"][1] < 0),
        "P2a log score above background, interval above zero": bool(prim["logscore_diff_ci"][0] > 0),
        "P2b central 80% interval covers 70% to 90%": bool(0.70 <= prim["pit_central80"] <= 0.90),
    }
    checks["promising"] = all(checks.values())
    with open(f"{DOCS}-checks.json", "w") as f:
        json.dump({"checks": checks, "fits": res}, f, indent=2, default=float)
    print(t[["scheme", "kind", "sites", "n", "over", "brier_candidate", "brier_background", "brier_production_form",
             "brier_rain_season", "cand_minus_background_ci", "cand_minus_production_form_ci", "pit_central80"]].to_string(index=False))
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    {"audit": stage_audit, "atlas": stage_atlas, "run": stage_run}[sys.argv[1]]()
