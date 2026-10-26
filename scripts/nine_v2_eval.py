"""The nine-company spill model v2 test, as stated in docs/NINE-COMPANY-MODEL-V2-TEST-2026-11.md: one layer 1
fitted on the nine English companies' EA start/stop files for 2024 and 2025 (UK local days), arm (a) that layer
alone and arm (b) with offsets at recency 1, scored with production and the baselines on January to August 2026.
Off CI, by hand, from a git archive of this commit, offline:

    DIPCAST_ROOT=<root> DIPCAST_CACHE=<frozen cache> PYTHONPATH=src \\
        python scripts/nine_v2_eval.py --zip2026 <2026 zip> --coverage <live_coverage.parquet> \\
        --prod <spill_model.pkl> --holdout <spill_model_holdout_2025.pkl> --out <dir>

<root>/data/processed holds annual_returns.parquet and the ea_events_<company>.parquet that
import_ea_events.py --years 2024 2025 2026 wrote. The Welsh set is read from the 2026 zip's Dwr Cymru workbook.
<coverage> is the state release's live_coverage.parquet, downloaded just before the run. Writes scores.csv,
intervals.csv, reliability.csv, sensitivities.csv, monthly.csv, event_defs.csv, training.csv, checks.json and the
fitted models to <out>.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import resource
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast.model import features as _features

# The run used PR #334's UK-local-day code. Without it (features.LOCAL_TZ), rows and labels would be cut on other
# days, so the harness stops rather than give different numbers.
if not hasattr(_features, "LOCAL_TZ"):
    raise SystemExit("nine_v2_eval needs PR #334's local-day code (features.LOCAL_TZ). Run it from "
                     "`git archive record/nine-company-v2-run src scripts`, as docs/NINE-COMPANY-MODEL-V2-TEST-2026-11.md "
                     "says under Reproduction.")

from dipcast import config  # noqa: E402
from dipcast.ingest.edm_events import read_ea_dcww_events  # noqa: E402
from dipcast.ingest.rainfall import grid_cell  # noqa: E402
from dipcast.model.features import ALL_FEATURES, LOCAL_TZ, build_site_days, daily_rain_features, spill_days  # noqa: E402
from dipcast.model.spill_model import SpillModel  # noqa: E402
from dipcast.model.training import NINE, WELSH, cells_of, ece, load_events, load_rain, site_years  # noqa: E402
from dipcast.model.verify import brier_skill, reliability_table, scores  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("nine_v2_eval")
_T0 = time.time()

NEG_FRAC = 0.25
PRIOR = 15.0
RECENCY_B, RECENCY_B25 = 1.0, 0.25
TEST_YEAR = 2026
TEST_END = "2026-08-31"   # the EA file's last day
PROD_SHA = "faa7917e2be725a9441b277fc111091c5bdffe45c80ab4fd042682aa9de4210e"
HOLDOUT_SHA = "882f9d4fb2c9314943fa861d8c6f4c62d8cd1eb57f1aa25059f4eb27d07068dc"
N_BOOT, SEED = 2000, 20261025
MARGIN = 0.01             # "no more than 1% above production's Brier"
ECE_LIMIT = 0.02
MIN_SPILL_DAYS, MIN_SPILL_DAYS_WELSH = 200, 100
# Option B's dead-monitor check (docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md), reference period cut short as the v2
# statement says: from REF_START to the last complete day in the release.
REF_START, REF_DAYS = pd.Timestamp("2026-10-05"), 28
KNOWN_SHARE, STALE_SHARE = 0.8, 0.2
STAMP_ONLY_ON_CHANGE = {"Northumbrian Water", "Southern Water"}
# PR #298 published their 2026 outcome (docs/UPGRADED-OVERFLOWS-2026-10-upstream.csv); option B leaves them out too.
ILKLEY_16 = ["YWS00176", "YWS00674", "YWS00179", "YWS00144", "YWS00145", "YWS00191", "YWS01340", "YWS00828",
             "YWS00188", "YWS00189", "YWS00177", "YWS00190", "YWS00185", "YWS01311", "YWS00186", "YWS00187"]
ARMS = ["(a) pooled", "(b) offsets"]


def step(msg: str) -> None:
    log.info("[%5.0fs, peak %5.0f MB] %s", time.time() - _T0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, msg)


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- rows
def frame(sites: pd.DataFrame, year: int, daily: pd.DataFrame, labels: pd.DataFrame, end: str | None = None) -> pd.DataFrame:
    """train.py's _frame, with an optional last day."""
    days = pd.date_range(f"{year}-01-01", end or f"{year}-12-31", freq="D", tz=LOCAL_TZ)
    sd = build_site_days(sites, daily, days, labels[labels["day"].dt.year == year])
    sd = sd[sd["rain_d"].notna()].copy()
    sd["company"] = sd["site_id"].map(dict(zip(sites["site_id"], sites["company"], strict=True)))
    sd["year"] = year
    return sd.astype({f: np.float32 for f in ALL_FEATURES})


def dead_monitor(coverage: pd.DataFrame, sites: pd.DataFrame) -> tuple[pd.Series, dict]:
    """True for each of `sites` whose monitor passes the check over the reference period."""
    last = coverage["day"].max() - pd.Timedelta(days=1)   # the newest day is still being polled
    cov = coverage[(coverage["day"] >= REF_START) & (coverage["day"] <= last)]
    n = int(cov["day"].nunique())
    need = round(20 * n / REF_DAYS)
    g = cov.groupby("site_id").agg(k=("n_known", "sum"), u=("n_unknown", "sum"), s=("n_stale", "sum"),
                                   d=("n_known", lambda x: int((x > 0).sum())))
    x = sites[["site_id", "company"]].merge(g, left_on="site_id", right_index=True, how="left")
    ok1 = (x["k"] / (x["k"] + x["u"]) >= KNOWN_SHARE).fillna(False)
    ok2 = (x["s"] / x["k"].clip(lower=1) <= STALE_SHARE).fillna(False) | x["company"].isin(STAMP_ONLY_ON_CHANGE)
    ok3 = (x["d"] >= need).fillna(False)
    passes = pd.Series((ok1 & ok2 & ok3).to_numpy(), index=sites.index)
    info = {"reference_first": str(REF_START.date()), "reference_last": str(pd.Timestamp(last).date()),
            "reference_days": n, "days_needed": need, "candidates": len(sites), "pass": int(passes.sum())}
    return passes, info


def test_sites(ar: pd.DataFrame, companies, coverage: pd.DataFrame | None) -> tuple[pd.DataFrame, dict]:
    """The 2026 overflows: a position and covariates in the 2025 return, EDM operation >= 50% in 2025, not the
    Ilkley 16, and (when `coverage` is given) a monitor that passes the dead-monitor check."""
    # An overflow with no id cannot be matched to an event, so it is left out (one Dwr Cymru row in the 2025 return).
    prev = ar[ar["company"].isin(companies) & (ar["year"] == TEST_YEAR - 1) & ar["lat"].notna() & ar["site_id"].notna()]
    prev = prev.drop_duplicates("site_id", keep="last")
    prev = prev[prev["edm_operational_pct"].ge(50) & ~prev["site_id"].isin(ILKLEY_16)].reset_index(drop=True)
    info = {"edm_50_not_ilkley": len(prev)}
    if coverage is not None:
        passes, dm = dead_monitor(coverage, prev)
        info.update(dm)
        prev = prev[passes].reset_index(drop=True)
    cols = ["site_id", "company", "lat", "lon", "lta_spills", "spill_hours", "edm_operational_pct"]
    return prev[cols], info


# ---------------------------------------------------------------- scores
def week_codes(day: pd.Series) -> np.ndarray:
    iso = day.dt.tz_localize(None).dt.isocalendar()
    return (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()


class TwoWay:
    """Option B's interval: each draw takes overflows with replacement and, independently, ISO weeks with
    replacement; a row counts (times its overflow was drawn) x (times its week was drawn). Drawn once, overflows
    first then weeks, and shared by every company, arm and subset. A difference's draws are sum(s D b) / sum(s N b)
    over the overflow x week table of summed differences D and row counts N."""

    def __init__(self, site: np.ndarray, week: np.ndarray, rng: np.random.Generator):
        self.sites, self.si = np.unique(site, return_inverse=True)
        self.weeks, self.wi = np.unique(week, return_inverse=True)
        ns, nw = len(self.sites), len(self.weeks)
        self.S = np.empty((N_BOOT, ns))
        self.W = np.empty((N_BOOT, nw))
        for r in range(N_BOOT):
            self.S[r] = np.bincount(rng.integers(0, ns, ns), minlength=ns)
            self.W[r] = np.bincount(rng.integers(0, nw, nw), minlength=nw)

    def _sums(self, values: list[np.ndarray], mask: np.ndarray, extra: np.ndarray | None = None, k: int = 1):
        """Per draw, the bootstrap-weighted sums of each of `values` over the masked rows (by optional bin
        `extra` of k bins), using only the overflows the mask holds, so a company costs its own size."""
        used, si = np.unique(self.si[mask], return_inverse=True)
        nw = len(self.weeks)
        cell = (si * nw + self.wi[mask]) * k + (extra if extra is not None else 0)
        size = len(used) * nw * k
        S = self.S[:, used]
        out = []
        for v in values:
            t = np.bincount(cell, weights=v, minlength=size).reshape(len(used), nw * k)
            sw = (S @ t).reshape(N_BOOT, nw, k)            # overflows drawn
            out.append(np.einsum("rwk,rw->rk", sw, self.W))  # weeks drawn
        return out

    def interval(self, d: np.ndarray, mask: np.ndarray) -> list[float]:
        num, den = self._sums([d[mask], np.ones(int(mask.sum()))], mask)
        num, den = num[:, 0], den[:, 0]
        stat = num[den > 0] / den[den > 0]
        return [float(v) for v in np.percentile(stat, [2.5, 97.5])]

    def week_only(self, d: np.ndarray, mask: np.ndarray) -> list[float]:
        nw = len(self.weeks)
        D = np.bincount(self.wi[mask], weights=d[mask], minlength=nw)
        N = np.bincount(self.wi[mask], minlength=nw).astype(float)
        num, den = self.W @ D, self.W @ N
        stat = num[den > 0] / den[den > 0]
        return [float(v) for v in np.percentile(stat, [2.5, 97.5])]

    def ece_interval(self, y: np.ndarray, p: np.ndarray, mask: np.ndarray) -> list[float]:
        """ECE's interval from the same draws: per-bin sums by overflow x week, recombined per draw."""
        b = np.clip((p[mask] * 10).astype(int), 0, 9)
        n, sp, sy = self._sums([np.ones(int(mask.sum())), p[mask], y[mask]], mask, b, 10)
        tot = n.sum(1)
        stat = np.abs(sp - sy).sum(1)[tot > 0] / tot[tot > 0]
        return [float(v) for v in np.percentile(stat, [2.5, 97.5])]


def score_rows(y: np.ndarray, preds: dict, mask: np.ndarray, refs=("company flat rate", "overflow climatology")) -> list[dict]:
    rows = []
    ref = {k: scores(y[mask], preds[k][mask])["brier"] for k in refs}
    for k, p in preds.items():
        sc = scores(y[mask], p[mask])
        rows.append({"model": k, **sc, "mean_forecast": float(p[mask].mean()), "ece": ece(y[mask], p[mask]),
                     "brier_skill_vs_clim": brier_skill(sc["brier"], ref["overflow climatology"]),
                     "brier_skill_vs_flat": brier_skill(sc["brier"], ref["company flat rate"])})
    return rows


def short_only_days(ev: pd.DataFrame) -> pd.DataFrame:
    """Spill-days touched only by events under 15 minutes."""
    lab_all = spill_days(ev).assign(any=1)
    lab_long = spill_days(ev[ev["duration_h"].isna() | (ev["duration_h"] >= 0.25)]).assign(long=1)
    m = lab_all.merge(lab_long, on=["site_id", "day"], how="left")
    return m[m["long"].isna()][["site_id", "day"]]


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--zip2026", type=Path, required=True)
    ap.add_argument("--coverage", type=Path, required=True)
    ap.add_argument("--prod", type=Path, required=True)
    ap.add_argument("--holdout", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--smoke", action="store_true",
                    help="a code check only: overflows in cells that already have 2026 rain, 30 per company")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    checks: dict = {"face": {}, "inputs": {}}

    # Face check 1: production's file.
    got = sha256(a.prod)
    checks["face"]["production_sha256"] = got
    if got != PROD_SHA:
        raise SystemExit(f"production model hash {got} is not the stated {PROD_SHA}")
    checks["inputs"]["holdout_sha256"] = sha256(a.holdout)
    checks["inputs"]["coverage_sha256"] = sha256(a.coverage)
    checks["inputs"]["zip2026_sha256"] = sha256(a.zip2026)

    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    ev = ev[ev["site_id"].notna()]
    labels = spill_days(ev)
    step(f"events {len(ev)}, spill-days {len(labels)}")

    # Training rows: PR #251's rule for 2024 and 2025.
    s24, c24 = site_years(ar, ev, NINE, 2024)
    s25, c25 = site_years(ar, ev, NINE, 2025)
    pd.concat([c24, c25]).to_csv(a.out / "training.csv")

    # Test rows.
    coverage = pd.read_parquet(a.coverage)
    s26, info26 = test_sites(ar, NINE, coverage)
    s26_all, _ = test_sites(ar, NINE, None)                 # sensitivity: no dead-monitor check
    with zipfile.ZipFile(a.zip2026) as zf:
        welsh_members = [n for n in zf.namelist() if Path(n).name.startswith("Dwr Cymru")]
    ev_w = read_ea_dcww_events([(a.zip2026, m) for m in welsh_members])
    labels_w = spill_days(ev_w)
    sw, infow = test_sites(ar, [WELSH], None)
    if a.smoke:
        have = {(float(f.stem.split("_")[1]), float(f.stem.split("_")[2])) for f in (config.CACHE / "rain").glob("archive_*_2026.parquet")}

        def few(df: pd.DataFrame) -> pd.DataFrame:
            cells = zip(*grid_cell(df["lat"].to_numpy(), df["lon"].to_numpy()), strict=True)
            keep = np.array([c in have for c in cells], dtype=bool)
            return df[keep].groupby("company", group_keys=False).head(30).reset_index(drop=True)

        s24, s25, s26, s26_all, sw = few(s24), few(s25), few(s26), few(s26_all), few(sw)
    checks["inputs"]["test_rows"] = info26
    checks["inputs"]["welsh_rows"] = infow
    step(f"sites: train {len(s24)} + {len(s25)}, test {len(s26)} (no check {len(s26_all)}), Welsh {len(sw)}")

    # Rain: training as PR #251 (2023 Dec on, both caches, tags 2023-2025); 2026 from one file per cell.
    rain_tr = load_rain(cells_of(pd.concat([s24, s25])))
    rain_tr = rain_tr[rain_tr["time"] < pd.Timestamp("2026-01-01", tz="UTC")]
    daily_tr = daily_rain_features(rain_tr)
    del rain_tr
    train = pd.concat([frame(s24, 2024, daily_tr, labels), frame(s25, 2025, daily_tr, labels)], ignore_index=True)
    del daily_tr
    step(f"training site-days {len(train)}, spill-days {int(train['y'].sum())}")

    cells26 = cells_of(pd.concat([s26_all, sw]))
    files = []
    for cl, cn in sorted(cells26):
        key = f"{cl:.3f}_{cn:.3f}"
        own = config.CACHE / "rain_nine" / f"archive_{key}_2026a.parquet"
        shared = config.CACHE / "rain" / f"archive_{key}_2026.parquet"
        f26 = shared if shared.exists() else own
        dec = [config.CACHE / d / f"archive_{key}_2025.parquet" for d in ("rain", "rain_nine")]
        dec = next((f for f in dec if f.exists()), None)
        if not f26.exists() or dec is None:
            raise SystemExit(f"no 2026 or 2025 rain for cell {key}")
        files += [dec, f26]
    t0, t1 = pd.Timestamp("2025-12-01", tz="UTC"), pd.Timestamp("2026-09-01", tz="UTC")
    rain26 = pd.concat((r[(r["time"] >= t0) & (r["time"] < t1)] for r in (pd.read_parquet(f) for f in files)), ignore_index=True)
    rain26["precip_mm"] = rain26["precip_mm"].astype(np.float32)
    checks["inputs"]["rain_2026"] = {"cells": len(cells26),
                                     "shared_2026_files": sum("rain/archive" in str(f) and f.name.endswith("_2026.parquet") for f in files),
                                     "fetched_2026a_files": sum(f.name.endswith("_2026a.parquet") for f in files)}
    daily26 = daily_rain_features(rain26)
    del rain26
    test_all = frame(s26_all, TEST_YEAR, daily26, labels, TEST_END)
    welsh = frame(sw, TEST_YEAR, daily26, labels_w, TEST_END)
    del daily26
    test_all["checked"] = test_all["site_id"].isin(set(s26["site_id"]))
    step(f"test site-days {len(test_all)} ({int(test_all['checked'].sum())} pass the check), Welsh {len(welsh)}")

    # The models.
    m = SpillModel().fit_pooled(train, neg_frac=NEG_FRAC, seed=0)
    step("layer 1 fitted")
    mb = copy.deepcopy(m).fit_site_offsets(train, prior_strength=PRIOR, recency=RECENCY_B)
    mb25 = copy.deepcopy(m).fit_site_offsets(train, prior_strength=PRIOR, recency=RECENCY_B25)
    m.trained_on = mb.trained_on = mb25.trained_on = (
        "Nine English water companies 2024-2025 (EA start/stop files, UK local days); verified on January-August 2026")
    for name, mod in (("v2_pooled", m), ("v2_offsets", mb), ("v2_offsets_r025", mb25)):
        mod.save(a.out / f"spill_model_{name}.pkl")
    prod, hold = SpillModel.load(a.prod), SpillModel.load(a.holdout)
    step("arms fitted and saved")

    # Baselines from January to August of the training years.
    ja = train[train["day"].dt.month <= 8]
    flat = ja.groupby("company")["y"].mean()
    site_rate = ja.groupby("site_id")["y"].mean()

    def predict_all(df: pd.DataFrame) -> dict:
        return {"(a) pooled": m.predict_pooled(df), "(b) offsets": mb.predict(df), "(b25) offsets, recency 0.25": mb25.predict(df),
                "production": prod.predict(df), "hold-out": hold.predict(df),
                "company flat rate": df["company"].map(flat).to_numpy(dtype=float),
                "overflow climatology": df["site_id"].map(site_rate).fillna(df["company"].map(flat)).to_numpy(dtype=float)}

    P_all = predict_all(test_all)
    pw = {"v2 pooled": m.predict_pooled(welsh), "production pooled": prod.predict_pooled(welsh)}
    y_all = test_all["y"].to_numpy(dtype=float)
    yw = welsh["y"].to_numpy(dtype=float)

    # Face checks 2 and 3: every predictor has a forecast on every row; the labels recount from the events.
    checks["face"]["all_finite"] = bool(all(np.isfinite(p).all() for p in P_all.values()) and all(np.isfinite(p).all() for p in pw.values()))
    ev26 = ev[ev["event_start"] >= pd.Timestamp("2025-10-01", tz="UTC")]   # events run up to 60 days
    s0 = ev26["event_start"].dt.tz_convert(LOCAL_TZ).dt.tz_localize(None).dt.normalize()
    s1 = ev26["event_end"].fillna(ev26["event_start"]).dt.tz_convert(LOCAL_TZ).dt.tz_localize(None).dt.normalize()
    k = ((s1 - s0).dt.days + 1).clip(lower=1).to_numpy()
    recount = pd.DataFrame({"site_id": np.repeat(ev26["site_id"].to_numpy(), k),
                            "day": np.repeat(s0.to_numpy(), k) + np.concatenate([np.arange(j) for j in k]).astype("timedelta64[D]")})
    recount = recount.drop_duplicates()
    rows_days = test_all[["site_id", "day", "company"]].assign(day=test_all["day"].dt.tz_localize(None))
    rc = rows_days.merge(recount.assign(r=1), on=["site_id", "day"], how="left")["r"].fillna(0).to_numpy()
    by_c = pd.DataFrame({"company": test_all["company"], "label": y_all, "recount": rc}).groupby("company").sum()
    checks["face"]["labels_recount_equal"] = bool((by_c["label"] == by_c["recount"]).all())
    checks["face"]["labels_by_company"] = by_c.astype(int).to_dict("index")
    if not (checks["face"]["all_finite"] and checks["face"]["labels_recount_equal"]):
        (a.out / "checks.json").write_text(json.dumps(checks, indent=2, default=str))
        raise SystemExit("a face check failed; see checks.json")
    step("face checks pass")

    # The deciding rows: those whose monitor passes the check.
    sel = test_all["checked"].to_numpy()
    test = test_all[sel].reset_index(drop=True)
    P = {k: v[sel] for k, v in P_all.items()}
    y = y_all[sel]
    comp = test["company"].to_numpy()
    month = test["day"].dt.month.to_numpy()

    rng = np.random.default_rng(SEED)
    boot = TwoWay(test["site_id"].to_numpy(), week_codes(test["day"]), rng)
    boot_w = TwoWay(welsh["site_id"].to_numpy(), week_codes(welsh["day"]), rng)
    step("bootstrap draws made")

    present = [c for c in NINE if (comp == c).any()]   # all nine in a real run; the minimum-data rule checks it
    groups = [*present, "all nine"]
    masks = {c: (comp == c) if c != "all nine" else np.ones(len(y), bool) for c in groups}
    score_tab, rel_tab, iv_tab = [], [], []
    for c in groups:
        for r in score_rows(y, P, masks[c]):
            score_tab.append({"company": c, **r})
        for k in [*ARMS, "(b25) offsets, recency 0.25", "production"]:
            t = reliability_table(y[masks[c]], P[k][masks[c]])
            rel_tab.append(t.assign(company=c, model=k))
    ws = score_rows(yw, {**pw, "company flat rate": np.full(len(yw), yw.mean()), "overflow climatology": np.full(len(yw), yw.mean())},
                    np.ones(len(yw), bool))
    for r in ws:
        if r["model"] in pw:
            score_tab.append({"company": "Welsh set", **r})
    scores_df = pd.DataFrame(score_tab)
    scores_df.to_csv(a.out / "scores.csv", index=False)
    pd.concat(rel_tab).to_csv(a.out / "reliability.csv", index=False)
    step("scores written")

    sq = {k: (P[k] - y) ** 2 for k in P}
    for arm in [*ARMS, "(b25) offsets, recency 0.25", "hold-out"]:
        d = sq[arm] - sq["production"]
        for c in groups:
            mk = masks[c]
            bp, ba = float(sq["production"][mk].mean()), float(sq[arm][mk].mean())
            iv_tab.append({"arm": arm, "company": c, "brier_arm": ba, "brier_production": bp, "difference": ba - bp,
                           "pct": 100 * (ba / bp - 1), "two_way": boot.interval(d, mk), "week_only": boot.week_only(d, mk)})
    d = sq["(b) offsets"] - sq["(a) pooled"]
    iv_tab.append({"arm": "(b) - (a)", "company": "all nine", "difference": float(d.mean()),
                   "two_way": boot.interval(d, masks["all nine"]), "week_only": boot.week_only(d, masks["all nine"])})
    dw = (pw["v2 pooled"] - yw) ** 2 - (pw["production pooled"] - yw) ** 2
    allw = np.ones(len(yw), bool)
    bpw, bvw = float(((pw["production pooled"] - yw) ** 2).mean()), float(((pw["v2 pooled"] - yw) ** 2).mean())
    iv_tab.append({"arm": "v2 pooled", "company": "Welsh set", "brier_arm": bvw, "brier_production": bpw, "difference": bvw - bpw,
                   "pct": 100 * (bvw / bpw - 1), "two_way": boot_w.interval(dw, allw), "week_only": boot_w.week_only(dw, allw)})
    iv = pd.DataFrame(iv_tab)
    step("intervals done")

    ece_iv = {}
    for k in [*ARMS, "production"]:
        for c in present:
            ece_iv[f"{k} | {c}"] = boot.ece_interval(y, P[k], masks[c])
    step("ECE intervals done")

    # The conditions.
    def ivrow(arm, c):
        return iv[(iv["arm"] == arm) & (iv["company"] == c)].iloc[0]

    def sc(model, c):
        return scores_df[(scores_df["model"] == model) & (scores_df["company"] == c)].iloc[0]

    spills = {c: int(y[comp == c].sum()) for c in NINE}
    minimum = {"companies": spills, "welsh": int(yw.sum()),
               "ok": all(v >= MIN_SPILL_DAYS for v in spills.values()) and yw.sum() >= MIN_SPILL_DAYS_WELSH}
    wrow = iv[iv["arm"] == "v2 pooled"].iloc[0]
    c5 = {"two_way": wrow["two_way"], "pct": wrow["pct"],
          "pass": bool(wrow["two_way"][0] <= 0 and wrow["brier_arm"] <= (1 + MARGIN) * wrow["brier_production"])}
    verdict = {}
    for arm in ARMS:
        r9 = ivrow(arm, "all nine")
        c1 = {"difference": r9["difference"], "two_way": r9["two_way"],
              "pass": bool(r9["difference"] < 0 and r9["two_way"][1] < 0)}
        c2, c3, c4 = {}, {}, {}
        for c in present:
            r = ivrow(arm, c)
            c2[c] = {"pct": r["pct"], "two_way": r["two_way"],
                     "pass": bool(r["two_way"][0] <= 0 and r["brier_arm"] <= (1 + MARGIN) * r["brier_production"])}
            s_arm = sc(arm, c)
            c3[c] = {"brier": s_arm["brier"], "flat": sc("company flat rate", c)["brier"],
                     "climatology": sc("overflow climatology", c)["brier"]}
            c3[c]["pass"] = bool(c3[c]["brier"] < c3[c]["flat"] and c3[c]["brier"] < c3[c]["climatology"])
            c4[c] = {"ece": s_arm["ece"], "ece_production": sc("production", c)["ece"]}
            c4[c]["pass"] = bool(c4[c]["ece"] <= c4[c]["ece_production"] or c4[c]["ece"] <= ECE_LIMIT)
        passes = (c1["pass"] and all(v["pass"] for v in c2.values()) and all(v["pass"] for v in c3.values())
                  and all(v["pass"] for v in c4.values()) and c5["pass"] and minimum["ok"])
        verdict[arm] = {"1_gain_over_nine": c1, "2_no_company_clearly_worse": c2, "3_skill_vs_baselines": c3,
                        "4_reliability": c4, "5_welsh": c5, "passes": bool(passes)}
    adopted = "(b) offsets" if verdict["(b) offsets"]["passes"] else "(a) pooled" if verdict["(a) pooled"]["passes"] else None
    checks.update({"minimum_data": minimum, "conditions": verdict, "verdict": adopted, "ece_intervals": ece_iv})

    # Reported, not deciding: sensitivities, months, event definitions.
    sens = []

    def add_sens(name: str, mk: np.ndarray, yy: np.ndarray, PP: dict, cc: np.ndarray):
        for c in groups:
            mm = mk & ((cc == c) if c != "all nine" else True)
            if mm.sum() == 0:
                continue
            row = {"sensitivity": name, "company": c, "rows": int(mm.sum()), "spill_days": int(yy[mm].sum())}
            for k2 in [*ARMS, "production"]:
                row[f"brier {k2}"] = float(((PP[k2][mm] - yy[mm]) ** 2).mean())
            sens.append(row)

    add_sens("as stated", np.ones(len(y), bool), y, P, comp)
    add_sens("without United Utilities' January", ~((comp == "United Utilities") & (month == 1)), y, P, comp)
    add_sens("without July", month != 7, y, P, comp)
    add_sens("without the dead-monitor check", np.ones(len(y_all), bool), y_all, P_all, test_all["company"].to_numpy())
    for mo in range(1, 9):
        add_sens(f"month {mo}", month == mo, y, P, comp)
    pd.DataFrame(sens).to_csv(a.out / "sensitivities.csv", index=False)

    mon = []
    for c in groups:
        for mo in range(1, 9):
            mk = masks[c] & (month == mo)
            if mk.sum():
                mon.append({"company": c, "month": mo, "rows": int(mk.sum()), "observed": float(y[mk].mean()),
                            **{f"mean {k2}": float(P[k2][mk].mean()) for k2 in [*ARMS, "production", "company flat rate"]}})
    pd.DataFrame(mon).to_csv(a.out / "monthly.csv", index=False)

    short = short_only_days(ev).assign(short=1)
    ed = []
    for name, df in (("training", train), ("test", test)):
        j = df[df["y"] == 1][["site_id", "day", "company"]].merge(short, on=["site_id", "day"], how="left")
        t = j.groupby("company")["short"].apply(lambda s: float(s.notna().mean()))
        for c, v in t.items():
            ed.append({"rows": name, "company": c, "share_spill_days_only_short_events": v})
    pd.DataFrame(ed).to_csv(a.out / "event_defs.csv", index=False)

    iv.to_csv(a.out / "intervals.csv", index=False)
    checks["peak_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    (a.out / "checks.json").write_text(json.dumps(checks, indent=2, default=str))
    step(f"done: verdict {adopted}")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
