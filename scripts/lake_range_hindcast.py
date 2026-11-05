"""A likely E. coli reading and range for lakes, tested on 2012-2022 lake seasons the model never read
(docs/LAKE-RANGE-HINDCAST-TEST-2026-11.md; statement committed in e5840042 before any test row was built).
Off CI, by hand, in a scratch root:

    export DIPCAST_ROOT=<scratch copy with data> DIPCAST_STATE=<scratch>/state LAKE_RANGE_OUT=<scratch>/out
    uv run python scripts/lake_range_hindcast.py samples   # EA listings, 2012-2022, the five test lakes
    uv run python scripts/lake_range_hindcast.py rain      # Open-Meteo archive, their cells, 2012-2022 (cap 400 calls)
    uv run python scripts/lake_range_hindcast.py rows      # training (2023-26) and test (2012-22) rows, one pipeline
    uv run python scripts/lake_range_hindcast.py run       # fit on training rows once, score on test rows

Inputs come from validate_ecoli.py's hindcast: archive rain at the spot, and the exposure from archive rain at every
upstream overflow through the spill model and transport, calibrated as lead 0. The models are concentration_study.py's
CensoredRI, unchanged, plus a heavy-tailed variant (Student-t errors at lakes), secondary and reported only.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import norm, spearmanr
from scipy.stats import t as student_t

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from concentration_study import (  # noqa: E402
    BACKGROUND, CUT, N_NODES, PROD, CensoredRI, _std, boot_diff, median_from, prepare, row_loglik,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("lake_range_hindcast")

OUT = Path(os.environ.get("LAKE_RANGE_OUT", "lake_range_out"))
DOC = HERE.parent / "docs" / "LAKE-RANGE-HINDCAST-TEST-2026-11"
TZ = "Europe/London"
TEST_YEARS = list(range(2012, 2023))
SEASON = list(range(5, 10))
EA_CAP, OM_CAP = 40, 400
# Fixed in the statement: the inland lake bathing waters with overflows upstream (site pins) and samples before 2023.
TEST_SITES = {
    "ukd1203-45625": "Windermere", "ukd1203-45650": "Windermere", "ukd1203-45675": "Windermere",
    "ukd1203-45700": "Windermere", "ukj2310-11945": "Frensham",
}
CAND = PROD   # ecoli.FEATURES: no soil moisture, as production's lake model (statement section 3)


# ------------------------------------------------------------------ data
def stage_samples() -> None:
    from dipcast import config
    from dipcast.ingest.bwq import fetch_point
    sites = {s["id"]: s for s in json.loads((config.RAW / "bathing_waters_inland.json").read_text())}
    assert set(TEST_SITES) <= set(sites), set(TEST_SITES) - set(sites)
    frames = []
    for bw_id in TEST_SITES:
        s = sites[bw_id]
        df = pd.DataFrame(fetch_point(bw_id.split("-")[-1], since="2012-01-01T00:00:00"))
        df["bw_id"], df["name"], df["kind"], df["lat"], df["lon"] = bw_id, s["name"], s["kind"], s["lat"], s["lon"]
        frames.append(df)
        log.info("%s: %d listed since 2012", s["name"], len(df))
    out = pd.concat(frames, ignore_index=True)
    out["sample_time"] = pd.to_datetime(out["sample_time"]).dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward")
    for c in ["ecoli", "ie"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out[out["sample_time"].dt.year.isin(TEST_YEARS) & out["sample_time"].dt.month.isin(SEASON)]
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT / "test_samples.parquet", index=False)
    print(out.groupby(["name", out["sample_time"].dt.year]).size().unstack(fill_value=0).to_string())


def _site_up(net, ov, bw_id: str, lat: float, lon: float):
    from eval_pins import bathing_water_pin

    from dipcast.model.transport import river_velocity, upstream_overflows
    pin = bathing_water_pin(net, bw_id, lon, lat)
    return pin, upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None))


def stage_rain() -> None:
    from dipcast.ingest.rainfall import fetch_archive, grid_cell
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import load_overflows
    net = RiverNetwork.load(); ov = load_overflows(net)
    s = pd.read_parquet(OUT / "test_samples.parquet").drop_duplicates("bw_id")
    cells = set()
    for _, r in s.iterrows():
        _, up = _site_up(net, ov, r["bw_id"], float(r["lat"]), float(r["lon"]))
        cells.add(tuple(float(v) for v in grid_cell(float(r["lat"]), float(r["lon"]))))
        for a, b in zip(*grid_cell(up["lat"].to_numpy(), up["lon"].to_numpy()), strict=True):
            cells.add((float(a), float(b)))
    cells = sorted(cells)
    weight = len(cells) * len(TEST_YEARS) * max(1.0, 0.1 * 365 / 14)
    log.info("%d cells x %d years: about %.0f weighted calls (cap %d)", len(cells), len(TEST_YEARS), weight, OM_CAP)
    assert weight <= OM_CAP, "over the stated Open-Meteo cap"
    for y in TEST_YEARS:
        df = fetch_archive(cells, y, strict=True)
        log.info("%d: %d hourly rows, %d cells", y, len(df), df[["cell_lat", "cell_lon"]].drop_duplicates().shape[0])
    (OUT / "rain_cells.json").write_text(json.dumps({"cells": cells, "years": list(TEST_YEARS), "weight": weight}))


def build_rows(samples: pd.DataFrame, net, ov, model, rain_hourly, daily) -> tuple[pd.DataFrame, dict]:
    """validate_ecoli.main's rows (hindcast exposure, archive rain at the spot), for sites with overflows upstream."""
    from validate_ecoli import hindcast

    from dipcast.ingest.rainfall import grid_cell
    from dipcast.model.ecoli import rain_windows
    from dipcast.model.forecast import MAX_MISSING_SHARE
    from dipcast.model.transport import history_days
    out, drops = [], {"no_upstream": 0, "no_site_rain": 0, "rain_window": 0, "exposure_missing": 0}
    for bw_id, g in samples.groupby("bw_id"):
        s = g.iloc[0]
        try:
            _, up = _site_up(net, ov, bw_id, float(s.lat), float(s.lon))
        except KeyError:
            drops["no_upstream"] += len(g); continue
        if not len(up):
            drops["no_upstream"] += len(g); continue
        cl, cn = (float(v) for v in grid_cell(float(s.lat), float(s.lon)))
        try:
            site_rain = rain_hourly.loc[(cl, cn)].set_index("time")["precip_mm"].sort_index()
        except KeyError:
            drops["no_site_rain"] += len(g); continue
        g = g.sort_values("sample_time").reset_index(drop=True)
        risk = pd.Series(dtype=float); miss = pd.Series(dtype=float)
        sample_days = pd.DatetimeIndex(sorted(g["day"].unique()))
        lead_days = history_days(up["travel_h"])
        for y in sorted(g["sample_time"].dt.year.unique()):   # one season at a time: days stay consecutive
            sd = sample_days[sample_days.year == y]
            days = pd.date_range(sd.min() - pd.Timedelta(days=lead_days), sd.max(), freq="D")
            r, m = hindcast(up, daily, days, model)
            risk, miss = pd.concat([risk, r]), pd.concat([miss, m])
        r48, r24 = rain_windows(site_rain, pd.DatetimeIndex(g["sample_time"]))
        g["rain_48h"], g["rain_24h"] = r48, r24
        g["risk_model"] = risk.reindex(g["day"]).to_numpy()
        g["missing_share"] = miss.reindex(g["day"]).to_numpy()
        g["upstream"] = len(up)
        bad_rain = g["rain_48h"].isna() | g["rain_24h"].isna()
        drops["rain_window"] += int(bad_rain.sum())
        bad_exp = ~bad_rain & (g["risk_model"].isna() | (g["missing_share"] > MAX_MISSING_SHARE))
        drops["exposure_missing"] += int(bad_exp.sum())
        out.append(g[~bad_rain & ~bad_exp])
    return pd.concat(out, ignore_index=True), drops


def stage_rows() -> None:
    from validate_ecoli import load_rain

    from dipcast import config
    from dipcast.model.ecoli import features
    from dipcast.model.features import daily_rain_features
    from dipcast.model.spill_model import SpillModel
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import load_overflows
    net = RiverNetwork.load(); ov = load_overflows(net); model = SpillModel.load()
    rain = load_rain()
    hourly = rain.set_index(["cell_lat", "cell_lon"]).sort_index()
    daily = daily_rain_features(rain)
    sites = {s["id"]: s for s in json.loads((config.RAW / "bathing_waters_inland.json").read_text())}
    res = {}
    for part, path in (("train", config.RAW / "bwq_samples.parquet"), ("test", OUT / "test_samples.parquet")):
        s = pd.read_parquet(path).dropna(subset=["ecoli", "sample_time"])
        n0 = len(s)
        s = s.drop_duplicates(["bw_id", "sample_time"]).copy()
        n_rep = n0 - len(s)
        s["kind"] = s["bw_id"].map(lambda b: sites[b]["kind"])
        s["day"] = s["sample_time"].dt.floor("D")
        rows, drops = build_rows(s, net, ov, model, hourly, daily)
        rows["lake"] = (rows["kind"] == "lake").astype(float)
        X = features(rows["rain_48h"], rows["rain_24h"], rows["risk_model"], rows["lake"], rows["sample_time"])
        rows = pd.concat([rows.reset_index(drop=True), X.drop(columns=["lake"])], axis=1)
        rows["qual"] = rows["ecoli_qual"]
        rows.to_parquet(OUT / f"rows_{part}.parquet", index=False)
        res[part] = {"listed_with_count": n0, "repeats_dropped": n_rep, **drops, "rows": len(rows),
                     "sites": int(rows["bw_id"].nunique()), "lakes": int(rows.loc[rows.lake == 1, "bw_id"].nunique()),
                     "first": str(rows["sample_time"].min()), "last": str(rows["sample_time"].max())}
        log.info("%s: %s", part, res[part])
    (OUT / "rows_audit.json").write_text(json.dumps(res, indent=1))


# ------------------------------------------------------------------ the heavy-tailed variant (secondary)
class HeavyTailRI(CensoredRI):
    """CensoredRI with its own lake noise level and Student-t errors at lakes (degrees of freedom fitted); rivers
    keep normal errors. theta = [beta, log sigma, log tau, lake shift, log(nu - 1)]."""

    def __init__(self, cols: list[str], n_nodes: int = N_NODES):
        super().__init__(cols, n_nodes, lake_sigma=True)

    def _ll(self, mu, sig, y, cens, lake, nu):
        normal = row_loglik(mu, sig, y, cens)
        yy = y.reshape(-1, 1); c = cens.reshape(-1, 1); z = (yy - mu) / sig
        tl = np.where(c < 0, student_t.logcdf(z, nu), np.where(c > 0, student_t.logsf(z, nu),
                                                                 student_t.logpdf(z, nu) - np.log(sig)))
        return np.where(lake.reshape(-1, 1) == 1, tl, normal)

    def _nu(self, theta):
        return 1.0 + float(np.exp(theta[-1]))

    def _node_ll(self, theta, Z, y, cens, lake=None):
        p = Z.shape[1]
        lake = np.zeros(len(y)) if lake is None else lake
        mu = (Z @ theta[:p])[:, None] + np.sqrt(2.0) * np.exp(theta[p + 1]) * self.x[None, :]
        return self._ll(mu, self._sig(theta, p, lake), y, cens, lake, self._nu(theta))

    def fit(self, X, y, cens, site):
        base = CensoredRI(self.cols, lake_sigma=True).fit(X, y, cens, site)   # start from the normal fit
        self.ref = X[self.cols].copy()
        Z = _std(X, self.cols)
        self.sites = base.sites
        si = self.sites.get_indexer(site)
        lake = X["lake"].to_numpy(dtype=float)
        p = Z.shape[1]

        def nll(theta):
            return -float(logsumexp(self._site_post(self._node_ll(theta, Z, y, cens, lake), si, len(self.sites)), axis=1).sum())

        theta0 = np.concatenate([base.theta, [np.log(9.0)]])
        bounds = [(None, None)] * p + [(-5, 3), (-6, 2), (-3, 3), (-3, 5)]
        res = minimize(nll, theta0, method="L-BFGS-B", bounds=bounds)
        self.theta, self.converged, self.nll = res.x, bool(res.success), float(res.fun)
        self.train_post = self._site_post(self._node_ll(self.theta, Z, y, cens, lake), si, len(self.sites))
        self.p = p
        self.sigma, self.tau = float(np.exp(self.theta[p])), float(np.exp(self.theta[p + 1]))
        self.sigma_lake = float(np.exp(self.theta[p] + self.theta[p + 2]))
        self.nu = self._nu(self.theta)
        return self

    def _F(self, z, lake):
        return np.where(lake.reshape(-1, 1) == 1, student_t.cdf(z, self.nu), norm.cdf(z))

    def cdf(self, X, site, yv):
        w, mu, u = self._weights_mu(X, site)
        z = (yv[:, None] - mu[:, None] - u[None, :]) / self._sigma_rows(X)
        return (w * self._F(z, X["lake"].to_numpy(dtype=float))).sum(1)

    def p_over(self, X, site, cut: float = CUT):
        w, mu, u = self._weights_mu(X, site)
        z = (cut - mu[:, None] - u[None, :]) / self._sigma_rows(X)
        return (w * (1 - self._F(z, X["lake"].to_numpy(dtype=float)))).sum(1)

    def log_score(self, X, site, y, cens):
        w, mu, u = self._weights_mu(X, site)
        ll = self._ll(mu[:, None] + u[None, :], self._sigma_rows(X), y, cens, X["lake"].to_numpy(dtype=float), self.nu)
        return logsumexp(np.log(np.clip(w, 1e-300, None)) + ll, axis=1)


# ------------------------------------------------------------------ scores
def within_rho(d: pd.DataFrame, score: np.ndarray) -> dict:
    out = {}
    for s, g in d.groupby("bw_id"):
        if len(g) >= 15 and g["y"].nunique() > 1:
            out[g["name"].iloc[0]] = round(float(spearmanr(score[g.index], g["y"]).statistic), 3)
    return out


def coverage(pit: np.ndarray, lo: float, hi: float) -> float:
    return round(float(((pit >= lo) & (pit <= hi)).mean()), 4)


def stage_run() -> None:
    from concentration_study import logistic
    tr = prepare(pd.read_parquet(OUT / "rows_train.parquet"))
    te = prepare(pd.read_parquet(OUT / "rows_test.parquet")).reset_index(drop=True)
    te["water"] = te["bw_id"].map(TEST_SITES)
    assert te["water"].notna().all() and (te["lake"] == 1).all()
    assert tr["year"].min() >= 2023 and te["year"].max() <= 2022
    rng = np.random.default_rng(0)
    yt, ct, st = tr["y"].to_numpy(), tr["cens"].to_numpy(), tr["bw_id"].to_numpy()
    models = {"candidate": CensoredRI(CAND, lake_sigma=True), "background": CensoredRI(BACKGROUND, lake_sigma=True),
              "shared_spread": CensoredRI(CAND, lake_sigma=False), "heavy_tail": HeavyTailRI(CAND)}
    y, c, s = te["y"].to_numpy(), te["cens"].to_numpy(), te["bw_id"].to_numpy()
    wk = te["week"].to_numpy()
    fits, pred = {}, {}
    for nm, m in models.items():
        m.fit(tr, yt, ct, st)
        fits[nm] = {"converged": m.converged, "sigma_river": round(m.sigma, 4), "sigma_lake": round(m.sigma_lake, 4),
                    "tau": round(m.tau, 4), **({"nu": round(m.nu, 3)} if nm == "heavy_tail" else {}),
                    "coef_std": dict(zip(["intercept", *m.cols], np.round(m.theta[:m.p], 4).tolist(), strict=True))}
        pred[nm] = {"ls": m.log_score(te, s, y, c), "pit": m.pit(te, s, y, c, rng), "med": median_from(m, te, s),
                    "p900": m.p_over(te, s), "p500": m.p_over(te, s, np.log10(500.0))}
    tr["over500"] = (tr["ecoli"] > 500).astype(int)
    pred["production"] = {"p900": logistic(tr, te, PROD)}
    o900, o500 = te["over"].to_numpy(), (te["ecoli"] > 500).astype(int).to_numpy()

    def block(mask: np.ndarray) -> dict:
        r = {"n": int(mask.sum()), "over_500": int(o500[mask].sum()), "over_900": int(o900[mask].sum())}
        for nm in models:
            pit = pred[nm]["pit"][mask]
            r[nm] = {"central80": coverage(pit, 0.1, 0.9), "central50": coverage(pit, 0.25, 0.75),
                     "below_range": coverage(pit, 0, 0.1), "above_range": coverage(pit, 0.9, 1),
                     "logscore": round(float(pred[nm]["ls"][mask].mean()), 4),
                     "brier900": round(float(((pred[nm]["p900"][mask] - o900[mask]) ** 2).mean()), 5),
                     "brier500": round(float(((pred[nm]["p500"][mask] - o500[mask]) ** 2).mean()), 5)}
        r["production_brier900"] = round(float(((pred["production"]["p900"][mask] - o900[mask]) ** 2).mean()), 5)
        return r

    allm = np.ones(len(te), bool)
    res = {"rows": block(allm),
           "pit_deciles": {nm: np.histogram(pred[nm]["pit"], bins=10, range=(0, 1))[0].tolist() for nm in models},
           "by_water": {w: block(te["water"].to_numpy() == w) for w in ("Windermere", "Frensham")},
           "by_site": {n: block(te["name"].to_numpy() == n) for n in sorted(te["name"].unique())},
           "by_year": {int(yr): block(te["year"].to_numpy() == yr) for yr in sorted(te["year"].unique())},
           "within_site_rho_median": {nm: within_rho(te, pred[nm]["med"]) for nm in models},
           "within_site_rho_production": within_rho(te, pred["production"]["p900"]),
           "fits": fits, "train_rows": len(tr), "train_sites": int(tr["bw_id"].nunique()),
           "train_lake_rows": int((tr["lake"] == 1).sum())}
    diffs = {}
    for ref in ("background", "shared_spread"):
        d = pred["candidate"]["ls"] - pred[ref]["ls"]
        diffs[f"candidate_minus_{ref}"] = {"mean": round(float(d.mean()), 4), "ci95": [round(v, 4) for v in boot_diff(d, wk)]}
    d = pred["heavy_tail"]["ls"] - pred["candidate"]["ls"]
    diffs["heavy_tail_minus_candidate"] = {"mean": round(float(d.mean()), 4), "ci95": [round(v, 4) for v in boot_diff(d, wk)]}
    res["logscore_differences"] = diffs
    cov = res["rows"]["candidate"]["central80"]
    checks = {
        "1 central 80% range holds 70-90% of results": bool(0.70 <= cov <= 0.90),
        "2 log score above background, interval above zero": bool(diffs["candidate_minus_background"]["ci95"][0] > 0),
        "3 each water body at least 60% inside the range": all(res["by_water"][w]["candidate"]["central80"] >= 0.60
                                                               for w in res["by_water"]),
    }
    res["checks"] = checks
    with open(f"{DOC}-scores.json", "w") as f:
        json.dump(res, f, indent=1, default=float)
    print(json.dumps({"checks": checks, "rows": res["rows"], "diffs": diffs, "by_water": res["by_water"],
                      "rho": res["within_site_rho_median"], "fits": fits}, indent=1, default=float))


def quantile_from(m: CensoredRI, X: pd.DataFrame, site: np.ndarray, q: float) -> np.ndarray:
    """The predictive q-quantile of log10 E. coli, by bisection on the mixture CDF (median_from's method)."""
    lo, hi = np.full(len(X), -2.0), np.full(len(X), 7.0)
    for _ in range(40):
        mid = (lo + hi) / 2
        below = m.cdf(X, site, mid) < q
        lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
    return (lo + hi) / 2


def stage_extra() -> None:
    """Supplementary, not in the statement. (a) The test rows predicted as if their lakes had no samples of their own:
    the candidate and background refitted without Windermere and Frensham, so each site gets the prior intercept, as
    an unsampled lake would. (b) What the fitted candidate's range reads at each test site on 1 July: a dry day and a
    wet day."""
    from dipcast.model.ecoli import features
    tr = prepare(pd.read_parquet(OUT / "rows_train.parquet"))
    te = prepare(pd.read_parquet(OUT / "rows_test.parquet")).reset_index(drop=True)
    rng = np.random.default_rng(0)
    y, c, s, wk = te["y"].to_numpy(), te["cens"].to_numpy(), te["bw_id"].to_numpy(), te["week"].to_numpy()
    keep = ~tr["bw_id"].isin(TEST_SITES)
    a = tr[keep]
    res = {"unseen": {"train_rows": int(keep.sum()), "train_lake_sites": int(a.loc[a.lake == 1, "bw_id"].nunique())}}
    ls = {}
    for nm, cols in (("candidate", CAND), ("background", BACKGROUND)):
        m = CensoredRI(cols, lake_sigma=True).fit(a, a["y"].to_numpy(), a["cens"].to_numpy(), a["bw_id"].to_numpy())
        pit = m.pit(te, s, y, c, rng)
        ls[nm] = m.log_score(te, s, y, c)
        res["unseen"][nm] = {"central80": coverage(pit, 0.1, 0.9), "below_range": coverage(pit, 0, 0.1),
                             "above_range": coverage(pit, 0.9, 1), "logscore": round(float(ls[nm].mean()), 4),
                             "by_water": {w: coverage(pit[te["bw_id"].map(TEST_SITES).to_numpy() == w], 0.1, 0.9)
                                          for w in ("Windermere", "Frensham")}}
    d = ls["candidate"] - ls["background"]
    res["unseen"]["candidate_minus_background"] = {"mean": round(float(d.mean()), 4),
                                                   "ci95": [round(v, 4) for v in boot_diff(d, wk)]}
    m = CensoredRI(CAND, lake_sigma=True).fit(tr, tr["y"].to_numpy(), tr["cens"].to_numpy(), tr["bw_id"].to_numpy())
    names = te.drop_duplicates("bw_id").set_index("bw_id")["name"]
    when = pd.Series(pd.Timestamp("2026-07-01 12:00", tz=TZ), index=range(2))
    ex = {}
    for bw, nm in names.items():
        # dry: no rain in 48 h, the site's 10th-percentile test exposure; wet: 25 mm in 48 h (15 in the last 24 h),
        # its 90th-percentile exposure
        r = te.loc[te.bw_id == bw, "risk_model"]
        X = features([0.0, 25.0], [0.0, 15.0], [r.quantile(.1), r.quantile(.9)], [1.0, 1.0], when)
        site = np.array([bw, bw])
        q = {k: [float(f"{v:.2g}") for v in 10 ** quantile_from(m, X, site, k)] for k in (0.1, 0.5, 0.9)}   # 2 sig. fig.
        ex[nm] = {day: {"median": float(q[0.5][i]), "range80": [float(q[0.1][i]), float(q[0.9][i])],
                        "p_over_900": round(float(m.p_over(X, site)[i]), 3)} for i, day in enumerate(("dry", "wet"))}
    res["examples_1_july"] = ex
    with open(f"{DOC}-extra.json", "w") as f:
        json.dump(res, f, indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


def background(tr: pd.DataFrame, lakes: list[str]) -> dict:
    m = CensoredRI(BACKGROUND, lake_sigma=True).fit(tr, tr["y"].to_numpy(), tr["cens"].to_numpy(), tr["bw_id"].to_numpy())
    assert m.converged
    post = m.train_post - logsumexp(m.train_post, axis=1, keepdims=True)
    return {"cols": BACKGROUND, "mean": {c: float(tr[c].mean()) for c in BACKGROUND},
            "sd": {c: float(tr[c].std(ddof=0)) or 1.0 for c in BACKGROUND}, "beta": m.theta[:m.p].tolist(),
            "sigma_lake": m.sigma_lake, "tau": m.tau,
            "log_weights": {bw: np.round(post[m.sites.get_loc(bw)], 6).tolist() for bw in lakes}}


def stage_export() -> None:
    """Freeze the tested candidate for the lake range (src/dipcast/lake_range.py): the same fit as `run`, on
    every training row, written to data/processed/ecoli_lake_range.json with each lake site's intercept weights and
    check values the site's own code must reproduce (tests/test_lake_range.py)."""
    import hashlib

    from dipcast.model.ecoli import features
    tr = prepare(pd.read_parquet(OUT / "rows_train.parquet"))
    m = CensoredRI(CAND, lake_sigma=True).fit(tr, tr["y"].to_numpy(), tr["cens"].to_numpy(), tr["bw_id"].to_numpy())
    assert m.converged
    spots = pd.read_csv(HERE.parent / "spots.csv").set_index("id")
    post = m.train_post - logsumexp(m.train_post, axis=1, keepdims=True)   # each site's normalised node weights
    lakes = sorted(tr.loc[tr["lake"] == 1, "bw_id"].unique())
    sites = {}
    for bw in lakes:
        r = spots.loc[f"bw-{bw}"]
        sites[bw] = {"name": str(r["name"]), "lat": round(float(r["lat"]), 6), "lon": round(float(r["lon"]), 6),
                     "log_weights": np.round(post[m.sites.get_loc(bw)], 6).tolist()}
    ref = tr[CAND]
    checks = []
    when = pd.Series(pd.Timestamp("2026-07-01 12:00", tz=TZ), index=range(2))
    for bw in (lakes[0], lakes[-1], "unsampled"):
        X = features([0.0, 25.0], [0.0, 15.0], [0.002, 0.08], [1.0, 1.0], when)
        site = np.array([bw, bw])
        q = {k: (10 ** quantile_from(m, X, site, k)).tolist() for k in (0.1, 0.5, 0.9)}
        for i in range(2):
            checks.append({"site": bw, "rain_48h": float([0.0, 25.0][i]), "rain_24h": float([0.0, 15.0][i]),
                           "risk": [0.002, 0.08][i], "day": "2026-07-01", "low": q[0.1][i], "median": q[0.5][i],
                           "high": q[0.9][i]})
    rows_sha = hashlib.sha256(pd.util.hash_pandas_object(tr[["bw_id", "sample_time", "ecoli", "qual", *CAND]],
                                                         index=False).to_numpy().tobytes()).hexdigest()
    out = {"rule": "lake-range-v1",
           "target": "log10 E. coli per 100 ml in a lake sample: the median and the central 80% range",
           "record": "docs/LAKE-RANGE-HINDCAST-TEST-2026-11.md", "pr": 584,
           "fitted_on": {"rows": len(tr), "sites": int(tr["bw_id"].nunique()), "lake_rows": int((tr["lake"] == 1).sum()),
                         "first": str(tr["sample_time"].min().date()), "last": str(tr["sample_time"].max().date()),
                         "rows_sha256": rows_sha},
           "cols": CAND, "mean": {c: float(ref[c].mean()) for c in CAND},
           "sd": {c: float(ref[c].std(ddof=0)) or 1.0 for c in CAND},
           "beta": m.theta[:m.p].tolist(), "sigma_lake": m.sigma_lake, "sigma_river": m.sigma, "tau": m.tau,
           "nodes": m.x.tolist(), "log_prior": m.logw.tolist(), "sites": sites, "checks": checks,
           # The reference for the prospective read (docs/LAKE-RANGE-WORDING-2026-11.md): the lake's typical range with
           # no weather (the test's background), frozen with the candidate so the read never refits it.
           "background": background(tr, lakes)}
    path = HERE.parent / "data" / "processed" / "ecoli_lake_range.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(path, hashlib.sha256(path.read_bytes()).hexdigest())
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    {"samples": stage_samples, "rain": stage_rain, "rows": stage_rows, "run": stage_run,
     "extra": stage_extra, "export": stage_export}[sys.argv[1]]()
