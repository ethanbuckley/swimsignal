"""Where, and on which days, a new E. coli sample would teach the model most. Offline prototype.

Two questions are kept apart on purpose:

* **Informativeness.** Which (site, day) sample would most reduce what the model does not know? Scored as the expected
  information, in bits, that one sample's outcome (over the line or not) carries about the model. The model is a
  bootstrap ensemble of the logistic E. coli fit (`model.ecoli.fit`) plus a random offset per site (partial pooling,
  so a site never sampled carries the full between-site spread). With two candidate models the ensemble is their
  union, so the score also counts what a sample says about which model is right.
* **High risk.** Which days is a sample most likely to be over the line? A swimmer-protection question, answered by
  the predicted chance alone. It is a separate table and never mixed into the first.

The score is BALD ("Bayesian active learning by disagreement"): H(mean p) - mean H(p) over the ensemble members, where
H is the Bernoulli entropy. It is high where members disagree about the chance and the chance is not near 0 or 1. Its
parts, for the plain-language reason on each row: the between-model part is the Jensen-Shannon divergence of the two
models' mean chances; the site part comes from the site offset's spread (high for a site never or seldom sampled).

Nothing here reads the network or writes a file. `scripts/sampling_priorities.py` runs it on saved rows when they exist
and on `synthetic_world` otherwise; `scripts/sampling_priorities_sim.py` runs the stated simulation
(docs/SAMPLING-PRIORITIES-SIM-2026-10.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dipcast.model.ecoli import EcoliModel, fit

GH_NODES, GH_WEIGHTS = np.polynomial.hermite_e.hermegauss(7)   # quadrature over a standard normal site offset
GH_WEIGHTS = GH_WEIGHTS / GH_WEIGHTS.sum()
TAU_GRID = np.array([0.01, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.7, 2.0])


def entropy_bits(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return -(p * np.log2(p) + (1 - p) * np.log2(1 - p))


def eta(model: EcoliModel, X: pd.DataFrame) -> np.ndarray:
    """The model's log-odds (EcoliModel.predict before the logistic)."""
    z = np.full(len(X), model.intercept)
    for f, b in model.coef.items():
        z += b * (X[f].to_numpy(dtype=float) - model.mean[f]) / model.scale[f]
    return z


def site_offsets(eta_rows: np.ndarray, y: np.ndarray, site_idx: np.ndarray, n_sites: int, tau: float,
                 iters: int = 25) -> tuple[np.ndarray, np.ndarray, float]:
    """Posterior mode and variance of each site's offset u ~ N(0, tau^2) given the fixed part's log-odds, by
    Newton steps and a Laplace approximation, and the approximate log marginal likelihood. A site with no rows
    keeps mean 0 and variance tau^2."""
    u = np.zeros(n_sites)
    prior_prec = 1.0 / tau ** 2
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(eta_rows + u[site_idx])))
        g = np.bincount(site_idx, y - p, n_sites) - u * prior_prec
        h = np.bincount(site_idx, p * (1 - p), n_sites) + prior_prec
        u = u + g / h
    p = np.clip(1 / (1 + np.exp(-(eta_rows + u[site_idx]))), 1e-12, 1 - 1e-12)
    h = np.bincount(site_idx, p * (1 - p), n_sites) + prior_prec
    loglik = np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)) - np.sum(u ** 2) * prior_prec / 2
    log_marg = loglik - n_sites * np.log(tau) - 0.5 * np.sum(np.log(h))
    return u, 1.0 / h, float(log_marg)


@dataclass
class Ensemble:
    """A point fit, bootstrap refits of the fixed part (whole sites resampled), and partial-pooling site offsets."""
    name: str
    cols: list[str]
    point: EcoliModel
    members: list[EcoliModel]
    sites: list[str]
    tau: float
    u_mean: np.ndarray
    u_var: np.ndarray
    n_by_site: np.ndarray
    extra: dict = field(default_factory=dict)

    def site_index(self, sites) -> np.ndarray:
        """Index into the offset arrays; a site the fit never saw gets the last slot (mean 0, variance tau^2)."""
        pos = {s: i for i, s in enumerate(self.sites)}
        return np.array([pos.get(s, len(self.sites)) for s in sites])

    def offsets(self) -> tuple[np.ndarray, np.ndarray]:
        return np.append(self.u_mean, 0.0), np.append(self.u_var, self.tau ** 2)

    def predict(self, X: pd.DataFrame, sites) -> np.ndarray:
        """Point chance with the site's offset (posterior mean of the chance over the offset)."""
        um, uv = self.offsets()
        i = self.site_index(sites)
        e = eta(self.point, X)[None, :] + um[i][None, :] + GH_NODES[:, None] * np.sqrt(uv[i])[None, :]
        return GH_WEIGHTS @ (1 / (1 + np.exp(-e)))


def fit_ensemble(X: pd.DataFrame, y: np.ndarray, sites, cols: list[str], name: str, all_sites=None,
                 n_boot: int = 20, seed: int = 0, tau: float | None = None) -> Ensemble:
    """Fit `cols` by `ecoli.fit` (C = 1), `n_boot` refits on whole sites drawn with replacement, and the site
    offsets with tau chosen on TAU_GRID by the Laplace marginal likelihood (or fixed by `tau`). `all_sites` lists
    sites to carry with no rows (offset mean 0, variance tau^2)."""
    sites = np.asarray(sites)
    y = np.asarray(y, dtype=int)
    names = list(dict.fromkeys(list(sites) + list(all_sites if all_sites is not None else [])))
    pos = {s: i for i, s in enumerate(names)}
    sidx = np.array([pos[s] for s in sites])
    point = fit(X, y, cols)
    e = eta(point, X)
    if tau is None:
        tau = float(max(TAU_GRID, key=lambda t: site_offsets(e, y, sidx, len(names), t)[2]))
    u, v, _ = site_offsets(e, y, sidx, len(names), tau)
    rng = np.random.default_rng(seed)
    seen = np.unique(sidx)
    rows_by = {s: np.where(sidx == s)[0] for s in seen}
    members = []
    while len(members) < n_boot:
        pick = rng.choice(seen, len(seen), replace=True)
        idx = np.concatenate([rows_by[s] for s in pick])
        if 0 < y[idx].sum() < len(idx):
            members.append(fit(X.iloc[idx], y[idx], cols))
    return Ensemble(name, cols, point, members, names, tau, u, v, np.bincount(sidx, minlength=len(names)))


def _member_chances(ens: Ensemble, X: pd.DataFrame, i: np.ndarray, u_mean: np.ndarray, u_var: np.ndarray,
                    eta_members: np.ndarray | None = None) -> np.ndarray:
    """Chances, shape (members, nodes, rows): every bootstrap member at every quadrature node of the offset."""
    em = np.stack([eta(m, X) for m in ens.members]) if eta_members is None else eta_members
    e = em[:, None, :] + u_mean[i][None, None, :] + GH_NODES[None, :, None] * np.sqrt(u_var[i])[None, None, :]
    return 1 / (1 + np.exp(-e))


def _info(pa: np.ndarray, pb: np.ndarray | None) -> dict[str, np.ndarray]:
    """BALD over the union of the ensembles (each model weighted 1/2), and its parts."""
    w = GH_WEIGHTS[None, :, None] / pa.shape[0]
    ma = (pa * w).sum((0, 1))
    ha = (entropy_bits(pa) * w).sum((0, 1))
    out = {"p_a": ma, "within_a": entropy_bits(ma) - ha, "fixed_sd_a": (pa * GH_WEIGHTS[None, :, None]).sum(1).std(0)}
    if pb is None:
        out.update(p_mean=ma, info_bits=out["within_a"], disagree_bits=np.zeros_like(ma), p_b=np.full_like(ma, np.nan))
        return out
    wb = GH_WEIGHTS[None, :, None] / pb.shape[0]
    mb = (pb * wb).sum((0, 1))
    hb = (entropy_bits(pb) * wb).sum((0, 1))
    m = (ma + mb) / 2
    out.update(p_b=mb, p_mean=m, info_bits=entropy_bits(m) - (ha + hb) / 2,
               disagree_bits=entropy_bits(m) - (entropy_bits(ma) + entropy_bits(mb)) / 2)
    return out


def score_candidates(cand: pd.DataFrame, a: Ensemble, b: Ensemble | None = None, state=None) -> pd.DataFrame:
    """Score candidate (site, day) rows. `cand` holds `site`, `day`, the columns both models use, and optionally
    `kind`, `rain_48h` for the reasons. `state` overrides the offsets (used by `plan` as picks accrue)."""
    sites = cand["site"].to_numpy()
    ia, ib = a.site_index(sites), b.site_index(sites) if b is not None else None
    sa = state["a"] if state else a.offsets()
    pa = _member_chances(a, cand, ia, *sa)
    pb = None
    if b is not None:
        sb = state["b"] if state else b.offsets()
        pb = _member_chances(b, cand, ib, *sb)
    r = _info(pa, pb)
    out = cand[[c for c in ("site", "day", "kind", "rain_48h") if c in cand]].copy()
    for k in ("p_mean", "p_a", "p_b", "info_bits", "disagree_bits", "within_a", "fixed_sd_a"):
        out[k] = r[k]
    out["site_sd"] = np.sqrt(sa[1][ia])
    out["n_samples"] = np.append(a.n_by_site, 0)[ia]
    return out


def reason(row, names=("model A", "model B"), wet_mm: float = 10.0) -> str:
    """A plain-language reason for one scored row: the site's record, then model disagreement, then the day."""
    n = int(row["n_samples"])
    parts = []
    if n == 0:
        parts.append(f"never sampled (site level unknown: sd {row['site_sd']:.2f} on the log-odds)")
    elif n < 10:
        parts.append(f"only {n} samples (site level sd {row['site_sd']:.2f})")
    elif row["site_sd"] >= 0.2:
        parts.append(f"site level still uncertain after {n} samples (sd {row['site_sd']:.2f})")
    if np.isfinite(row["p_b"]) and abs(row["p_a"] - row["p_b"]) >= 0.05:
        parts.append(f"models disagree: {row['p_a']:.2f} ({names[0]}) vs {row['p_b']:.2f} ({names[1]})")
    if 0.15 <= row["p_mean"] <= 0.85:
        wet = "rain_48h" in row and row["rain_48h"] >= wet_mm
        lead = f"rain forecast ({row['rain_48h']:.0f} mm in 48 h) lifts the chance to" if wet else "chance"
        parts.append(f"{lead} {row['p_mean']:.2f}, near the middle, where one result says most")
    if row["fixed_sd_a"] >= 0.05:
        parts.append(f"refits of the model spread by {row['fixed_sd_a']:.2f} at these conditions")
    return "; ".join(parts) if parts else f"chance {row['p_mean']:.2f}; site level sd {row['site_sd']:.2f}"


def plan(cand: pd.DataFrame, a: Ensemble, b: Ensemble | None = None, budget: int = 3, per_day: int = 2,
         per_site_day: int = 1, state=None) -> tuple[pd.DataFrame, dict]:
    """Greedy plan of `budget` samples by information. After each pick the picked site's offset variance shrinks
    by the expected precision of one sample, p(1 - p) (Laplace), in each model, so the next pick weighs a
    second visit to the same site less. No outcome is used. Returns the picks, in order, and the state after
    them (to carry into the next week)."""
    if state is None:
        state = {"a": a.offsets()} | ({"b": b.offsets()} if b is not None else {})
    state = {k: (v[0].copy(), v[1].copy()) for k, v in state.items()}
    sites, days = cand["site"].to_numpy(), cand["day"].to_numpy()
    ia = a.site_index(sites)
    ib = b.site_index(sites) if b is not None else None
    ema = np.stack([eta(m, cand) for m in a.members])
    emb = np.stack([eta(m, cand) for m in b.members]) if b is not None else None
    taken = np.zeros(len(cand), dtype=bool)
    day_count: dict = {}
    site_day: dict = {}
    picks, gain = [], []
    for _ in range(budget):
        pa = _member_chances(a, cand, ia, *state["a"], eta_members=ema)
        pb = _member_chances(b, cand, ib, *state["b"], eta_members=emb) if b is not None else None
        r = _info(pa, pb)
        ok = ~taken & np.array([day_count.get(d, 0) < per_day and site_day.get((s, d), 0) < per_site_day
                                for s, d in zip(sites, days, strict=True)])
        if not ok.any():
            break
        j = int(np.argmax(np.where(ok, r["info_bits"], -np.inf)))
        picks.append(j); gain.append(float(r["info_bits"][j]))
        taken[j] = True
        day_count[days[j]] = day_count.get(days[j], 0) + 1
        site_day[(sites[j], days[j])] = site_day.get((sites[j], days[j]), 0) + 1
        for key, idx, p in (("a", ia, r["p_a"]), ("b", ib, r["p_b"])):
            if key in state:
                um, uv = state[key]
                uv[idx[j]] = 1 / (1 / uv[idx[j]] + p[j] * (1 - p[j]))
    scored = score_candidates(cand, a, b)
    # info_bits is each row's score before any pick; info_at_pick its score when picked, after earlier picks
    return scored.iloc[picks].assign(order=np.arange(1, len(picks) + 1), info_at_pick=gain), state


def high_risk(cand: pd.DataFrame, a: Ensemble, b: Ensemble | None = None, min_p: float = 0.3,
              top: int = 20) -> pd.DataFrame:
    """Days a sample is most likely to be over the line: the mean chance across the models, highest first.
    This is a swimmer-protection list, not a learning list: it says nothing about what a sample would teach."""
    s = score_candidates(cand, a, b)
    s = s[s["p_mean"] >= min_p].sort_values("p_mean", ascending=False).head(top)
    def why(r):
        t = [f"chance over the line {r['p_mean']:.2f}"]
        if "rain_48h" in r and np.isfinite(r["rain_48h"]):
            t.append(f"{r['rain_48h']:.0f} mm rain forecast in 48 h")
        if np.isfinite(r["p_b"]) and abs(r["p_a"] - r["p_b"]) >= 0.1:
            t.append(f"models differ ({r['p_a']:.2f} vs {r['p_b']:.2f})")
        return "; ".join(t)
    return s.assign(reason=[why(r) for _, r in s.iterrows()])


# ---------------------------------------------------------------------------
# A synthetic world, for the stated simulation, the tests, and the script when no saved rows exist.
# ---------------------------------------------------------------------------
COLS_A = ["lrain48", "logit_risk", "lake", "lake_x_lrain48"]
COLS_B = COLS_A + ["sm"]
DAYS_PER_SEASON = 140      # 20 weeks from 8 May
WEEKDAYS = 5               # candidate days per week: Monday to Friday


@dataclass
class World:
    sites: pd.DataFrame          # site, kind, region, sampled (in history), u (true offset)
    days: pd.DataFrame           # one row per site-day of every season: features and the true chance
    gamma: float
    tau: float


def synthetic_world(seed: int, n_rivers: int = 28, n_lakes: int = 12, unsampled_rivers: int = 8,
                    unsampled_lakes: int = 4, tau: float = 0.7, gamma: float = 0.0, seasons: int = 4,
                    intercept: float = -2.2) -> World:
    """Sites, weather and a true exceedance chance, as stated in docs/SAMPLING-PRIORITIES-SIM-2026-10.md.
    Seasons 0-1 are history, 2 the season planned, 3 held out."""
    rng = np.random.default_rng(seed)
    n = n_rivers + n_lakes
    lake = np.r_[np.zeros(n_rivers), np.ones(n_lakes)]
    unsampled = np.r_[np.arange(n_rivers - unsampled_rivers, n_rivers), np.arange(n - unsampled_lakes, n)]
    sites = pd.DataFrame({"site": [f"{'L' if k else 'R'}{i:02d}" for i, k in enumerate(lake)],
                          "kind": np.where(lake == 1, "lake", "river"), "region": np.arange(n) % 4,
                          "sampled": ~np.isin(np.arange(n), unsampled), "u": rng.normal(0, tau, n),
                          "exposure_base": np.where(lake == 1, rng.normal(-4, 1, n), rng.normal(-3, 1, n)),
                          "soil": rng.normal(0, 0.5, n), "weekday": rng.integers(0, WEEKDAYS, n)})
    T = seasons * DAYS_PER_SEASON
    wet = rng.random((4, T + 1)) < 0.35
    regional = np.where(wet, rng.gamma(0.8, 6.0, (4, T + 1)), 0.0)
    sm_reg = np.zeros((4, T + 1))
    for t in range(1, T + 1):
        start = t % DAYS_PER_SEASON == 0
        sm_reg[:, t] = (0.15 if start else 0.92 * sm_reg[:, t - 1]) + 0.08 * np.minimum(regional[:, t] / 10, 3)
    rain = regional[sites.region.to_numpy()][:, 1:] * rng.lognormal(0, 0.3, (n, T))
    rain_prev = np.c_[regional[sites.region.to_numpy(), 0], rain[:, :-1]]
    r48 = rain + rain_prev
    sm = sm_reg[sites.region.to_numpy()][:, 1:] + sites.soil.to_numpy()[:, None]
    lr = np.log1p(r48)
    lrisk = np.clip(sites.exposure_base.to_numpy()[:, None] + 1.0 * (lr - 1.0) + rng.normal(0, 0.5, (n, T)), -6.9, 6.9)
    hist = sm[:, :2 * DAYS_PER_SEASON]
    sm_z = (sm - hist.mean()) / hist.std()
    lk = lake[:, None] * np.ones((1, T))
    z = (intercept + 0.8 * lr + 0.45 * (lrisk + 3) - 1.6 * lk - 0.6 * lk * lr + gamma * (1 - lk) * sm_z
         + sites.u.to_numpy()[:, None])
    t_idx = np.tile(np.arange(T), n)
    days = pd.DataFrame({"site": np.repeat(sites.site.to_numpy(), T), "kind": np.repeat(sites.kind.to_numpy(), T),
                         "season": t_idx // DAYS_PER_SEASON, "day": t_idx % DAYS_PER_SEASON,
                         "rain_48h": r48.ravel(), "lrain48": lr.ravel(), "logit_risk": lrisk.ravel(),
                         "lake": lk.ravel(), "lake_x_lrain48": (lk * lr).ravel(), "sm": sm_z.ravel(),
                         "p_true": (1 / (1 + np.exp(-z))).ravel()})
    days["week"] = days["day"] // 7
    days["dow"] = days["day"] % 7
    return World(sites, days, gamma, tau)


def history_rows(world: World, seed: int) -> pd.DataFrame:
    """Seasons 0-1: each sampled site once a week on its own weekday, with an outcome drawn from the true chance."""
    rng = np.random.default_rng(seed)
    d = world.days[(world.days.season < 2)].merge(world.sites[["site", "sampled", "weekday"]], on="site")
    d = d[d.sampled & (d.dow == d.weekday)].drop(columns=["sampled", "weekday"]).reset_index(drop=True)
    return d.assign(y=(rng.random(len(d)) < d.p_true).astype(int))


def forecast_view(rows: pd.DataFrame, rng: np.random.Generator, sd: float = 0.5) -> pd.DataFrame:
    """What a planner sees a few days ahead: 48 h rain times a lognormal error, exposure moved with it.
    Soil moisture is a state known at issue, so it is not perturbed."""
    f = rows.copy()
    f["rain_48h"] = rows["rain_48h"] * rng.lognormal(0, sd, len(rows))
    lr = np.log1p(f["rain_48h"])
    f["logit_risk"] = np.clip(rows["logit_risk"] + 1.0 * (lr - rows["lrain48"]), -6.9, 6.9)
    f["lrain48"], f["lake_x_lrain48"] = lr, rows["lake"] * lr
    return f
