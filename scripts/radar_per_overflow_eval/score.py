"""docs/RADAR-PER-OVERFLOW-TEST-2026-11.md: the spill model's form refitted on each rain source, with rain at each
overflow's own position (3 x 3 block, L3, and one pixel, L1) against the 0.1 deg cell's radar (C), Open-Meteo lead 0
(P) and ERA5-Land (E), plus two issue-time arms (the day from P, the two days before from C or L3).

    score.py <per-overflow radar dir> <cell radar dir> <out dir>

Reads the EA start/stop files, annual returns, Thames's stream file and overflow_urban_area from config.PROCESSED, and
lead and ERA5-Land rain from config.CACHE. Writes <out dir>/score.json (summary figures only) and the frozen 2025
models' pickles. No per-overflow rain value is written.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel
from dipcast.model.training import NINE, RAIN_DIRS, load_events, load_rain, site_years

COVERAGE = 0.9
SEED, BOOT = 20261106, 2000
EMBARGO = 7
WARN = 0.4
MARGIN = 0.01
URBAN_M = 100.0
Y0, Y1 = pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2025-12-31", tz="UTC")
F0, F1 = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-08-31", tz="UTC")
READ0 = pd.Timestamp("2024-12-20", tz="UTC")       # radar read from here: lags and 3 h windows need the days before
KEY = ["cell_lat", "cell_lon", "day"]
SKEY = ["site_id", "day"]
DAY_COLS = ["rain_d", "max1h_d", "max3h_d", "max6h_d"]
SHORT = DAY_COLS + ["rain_d1", "rain_d2", "rain_3d"]
ARMS = ["C", "L3", "L1", "P", "E", "C-lag", "L3-lag"]
FOLD_A = {0, 2, 4}                                   # two-month blocks Jan-Feb, May-Jun, Sep-Oct
PLUMBING = os.environ.get("RADAR_OVERFLOW_PLUMBING") == "1"
T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.1f} s] {msg}", flush=True)


def cells_in(glob_dirs, pattern: str) -> set:
    out = set()
    for d in glob_dirs:
        for f in d.glob(pattern):
            p = f.stem.split("_")
            out.add((float(p[1]), float(p[2])))
    return out


# ------------------------------------------------------------------ rain sources, daily
def cell_radar_daily(radar_dir: Path, cells: set) -> pd.DataFrame:
    frames = []
    for f in sorted(radar_dir.glob("radar_*.parquet")):
        p = f.stem.split("_")
        if (float(p[1]), float(p[2])) in cells:
            frames.append(pd.read_parquet(f))
    r = pd.concat(frames, ignore_index=True)
    r = r[r["time"] >= READ0]
    r["precip_mm"] = np.where(r["coverage"] >= COVERAGE, r["radar_mm"], np.nan).astype(float)
    return daily_rain_features(r[["cell_lat", "cell_lon", "time", "precip_mm"]])


def lead0_daily(cells: set) -> pd.DataFrame:
    frames = []
    for d in RAIN_DIRS:
        for f in (config.CACHE / d).glob("leads_*.parquet"):
            p = f.stem.split("_")
            if (float(p[1]), float(p[2])) in cells and p[3] in ("2024", "2025", "2026"):
                lv = pd.read_parquet(f)
                frames.append(lv[lv["lead"] == 0])
    lv = pd.concat(frames, ignore_index=True).drop_duplicates(["cell_lat", "cell_lon", "time", "lead"], keep="last")
    return daily_rain_features(lv.drop(columns="lead"))


def local_daily(ov_dir: Path, sites: list[str], chunk: int = 800) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Daily features from each overflow's 3 x 3 block (L3) and its own pixel (L1). An hour counts only with its
    coverage at least COVERAGE; otherwise it is missing (NaN), never zero. Days come from daily_rain_features with
    the site in place of the cell."""
    files = sorted(f for f in ov_dir.glob("radar_overflows_*.parquet")
                   if READ0 <= pd.Timestamp(f.stem.split("_")[-1], tz="UTC") <= F1)
    want = pd.Index(sites)
    ref, order = None, None
    hours = []
    blk = np.full((len(files) * 24, len(sites)), np.nan, dtype=np.float32)
    ctr = np.full_like(blk, np.nan)
    stats = {"files": len(files), "hours_block_low_cov": 0, "hours_centre_low_cov": 0, "site_hours": 0}
    for i, f in enumerate(files):
        d = pd.read_parquet(f, columns=["site_id", "time", "radar_mm", "coverage", "centre_mm", "centre_coverage"])
        assert len(d) % 24 == 0
        ids = d["site_id"].to_numpy()[::24]
        if ref is None:
            ref = ids
            pos = pd.Index(ref).get_indexer(want)
            assert (pos >= 0).all(), "a site has no per-overflow radar"
            order = pos
        assert np.array_equal(ids, ref), f"site order changed in {f.name}"
        t = d["time"].to_numpy()[:24]
        hours.extend(pd.to_datetime(t, utc=True))
        for col, cov, arr, k in (("radar_mm", "coverage", blk, "hours_block_low_cov"),
                                 ("centre_mm", "centre_coverage", ctr, "hours_centre_low_cov")):
            v = d[col].to_numpy(dtype=np.float32).reshape(-1, 24)[order]
            c = d[cov].to_numpy(dtype=np.float32).reshape(-1, 24)[order]
            ok = c >= COVERAGE
            stats[k] += int((~ok).sum())
            arr[i * 24:(i + 1) * 24] = np.where(ok, v, np.nan).T
        stats["site_hours"] += len(sites) * 24
    hours = pd.DatetimeIndex(hours)
    log(f"per-overflow radar read: {len(files)} files, {len(sites)} overflows")
    outs = []
    for arr in (blk, ctr):
        parts = []
        for s0 in range(0, len(sites), chunk):
            sl = slice(s0, s0 + chunk)
            n = arr[:, sl].shape[1]
            df = pd.DataFrame({"cell_lat": np.tile(np.arange(s0, s0 + n, dtype=float), len(hours)),
                               "cell_lon": 0.0, "time": np.repeat(hours, n),
                               "precip_mm": arr[:, sl].reshape(-1).astype(float)})
            dd = daily_rain_features(df)
            dd["site_id"] = np.asarray(sites)[dd["cell_lat"].to_numpy().astype(int)]
            parts.append(dd[["site_id", "day", *DAY_COLS, "rain_d1", "rain_d2"]])
        outs.append(pd.concat(parts, ignore_index=True))
    return outs[0], outs[1], stats


# ------------------------------------------------------------------ arms
def attach(base: pd.DataFrame, src: pd.DataFrame, key: list[str]) -> pd.DataFrame:
    """The short-range columns of `src` on base's rows, in base's order."""
    cols = DAY_COLS + ["rain_d1", "rain_d2"]
    m = base[key].merge(src[key + cols], on=key, how="left")
    assert len(m) == len(base)
    m = m[cols].reset_index(drop=True)
    m["rain_3d"] = m["rain_d"] + m["rain_d1"] + m["rain_d2"]
    return m


def arm_frames(base: pd.DataFrame, src: dict) -> dict:
    out = {k: src[k] for k in ("C", "L3", "L1", "P", "E")}
    for lag, s in (("C-lag", "C"), ("L3-lag", "L3")):
        f = src["P"].copy()
        f[["rain_d1", "rain_d2"]] = src[s][["rain_d1", "rain_d2"]].to_numpy()
        f["rain_3d"] = f["rain_d"] + f["rain_d1"] + f["rain_d2"]
        out[lag] = f
    return out


def frame_for(base: pd.DataFrame, short: pd.DataFrame) -> pd.DataFrame:
    df = base.drop(columns=[c for c in SHORT if c in base]).reset_index(drop=True)
    df[SHORT] = short[SHORT].to_numpy()
    return df.astype({c: np.float32 for c in ALL_FEATURES})


def fit(df: pd.DataFrame) -> SpillModel:
    m = SpillModel()
    m.fit_pooled(df, seed=0)
    m.fit_site_offsets(df, prior_strength=15.0, recency=1.0)
    return m


# ------------------------------------------------------------------ scoring
class Boot:
    """Brier differences with two-way (overflow x week, overflow x day) and one-way (week) cluster bootstraps,
    the same draws for every comparison."""

    def __init__(self, site, week, day, rng):
        self.si = pd.factorize(site)[0]
        self.wi = pd.factorize(week)[0]
        self.di = pd.factorize(day)[0]
        ns, nw, nd = self.si.max() + 1, self.wi.max() + 1, self.di.max() + 1
        self.ds = np.stack([np.bincount(rng.integers(0, ns, ns), minlength=ns) for _ in range(BOOT)]).astype(float)
        self.dw = np.stack([np.bincount(rng.integers(0, nw, nw), minlength=nw) for _ in range(BOOT)]).astype(float)
        self.dd = np.stack([np.bincount(rng.integers(0, nd, nd), minlength=nd) for _ in range(BOOT)]).astype(float)
        self.ns, self.nw, self.nd = ns, nw, nd

    def _two(self, e, mask, a_idx, n_a, draws_a, b_idx, n_b, draws_b):
        lin = a_idx[mask] * n_b + b_idx[mask]
        S = np.bincount(lin, e[mask], minlength=n_a * n_b).reshape(n_a, n_b)
        N = np.bincount(lin, minlength=n_a * n_b).reshape(n_a, n_b).astype(float)
        num = ((draws_a @ S) * draws_b).sum(axis=1)
        den = ((draws_a @ N) * draws_b).sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            st = num / den
        return [float(np.nanpercentile(st, 2.5)), float(np.nanpercentile(st, 97.5))]

    def diff(self, y, pa, pb, mask=None) -> dict:
        mask = np.ones(len(y), bool) if mask is None else mask
        e = (pa - y) ** 2 - (pb - y) ** 2
        ba = float(np.mean((pa[mask] - y[mask]) ** 2)); bb = float(np.mean((pb[mask] - y[mask]) ** 2))
        wk = np.bincount(self.wi[mask], e[mask], minlength=self.nw); wn = np.bincount(self.wi[mask], minlength=self.nw)
        with np.errstate(invalid="ignore", divide="ignore"):
            one = (self.dw @ wk) / (self.dw @ wn)
        return {"rows": int(mask.sum()), "brier_a": ba, "brier_b": bb, "diff": ba - bb,
                "skill_vs_b": 1 - ba / bb if bb > 0 else None,
                "ci95_overflow_week": self._two(e, mask, self.si, self.ns, self.ds, self.wi, self.nw, self.dw),
                "ci95_overflow_day": self._two(e, mask, self.si, self.ns, self.ds, self.di, self.nd, self.dd),
                "ci95_week": [float(np.nanpercentile(one, 2.5)), float(np.nanpercentile(one, 97.5))]}


def summary(y, p) -> dict:
    return {"brier": float(np.mean((p - y) ** 2)),
            "auc": float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else None,
            "spill_days_at_0.4": float((p[y == 1] >= WARN).mean()) if (y == 1).any() else None,
            "dry_days_at_0.4": float((p[y == 0] >= WARN).mean()) if (y == 0).any() else None,
            "mean_p": float(p.mean()), "rate": float(y.mean())}


def verdict(d: dict, lp: dict) -> dict:
    lo, hi = d["ci95_overflow_week"]
    below, above = hi < 0, lo > 0
    skill = d["skill_vs_b"]
    h = below and skill >= MARGIN and lp["ci95_overflow_week"][1] < 0
    v = "H" if h else "S" if below else "W" if above else "N"
    return {"verdict": v, "l3_minus_c_ci_below_zero": bool(below), "skill_vs_c": skill,
            "skill_at_least_margin": bool(skill >= MARGIN), "l3_minus_p_ci_below_zero": bool(lp["ci95_overflow_week"][1] < 0),
            "rules_out_1pct_gain": bool(lo > -MARGIN * d["brier_b"])}


def season(day: pd.Series) -> np.ndarray:
    m = day.dt.month.to_numpy()
    return np.select([np.isin(m, [12, 1, 2]), np.isin(m, [3, 4, 5]), np.isin(m, [6, 7, 8])], ["DJF", "MAM", "JJA"], "SON")


def model_hash(m: SpillModel) -> str:
    return hashlib.sha256(pickle.dumps(m, protocol=5)).hexdigest()


# ------------------------------------------------------------------ main
def main(ov_dir: str, radar_dir: str, out_dir: str) -> None:
    ov_dir, radar_dir, out = Path(ov_dir), Path(radar_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res: dict = {"protocol": "docs/RADAR-PER-OVERFLOW-TEST-2026-11.md", "seed": SEED, "draws": BOOT}

    # rows: 2025 site-years of the nine companies, in cells with cell radar and 2025 lead 0, with per-overflow radar
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    sites, counts = site_years(ar, ev, NINE, 2025)
    radar_cells = cells_in([radar_dir], "radar_*.parquet")
    lead25 = cells_in([config.CACHE / d for d in RAIN_DIRS], "leads_*_2025.parquet")
    use = radar_cells & lead25
    sc = list(zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True))
    in_use = np.array([c in use for c in sc])
    have_local = sites["site_id"].isin(set(pd.read_parquet(ov_dir / "overflow_pixels.parquet")["site_id"]))
    res["sites"] = {"site_years_2025": int(len(sites)), "in_cells_with_cell_radar_and_lead0": int(in_use.sum()),
                    "without_per_overflow_radar": int((in_use & ~have_local.to_numpy()).sum()),
                    "site_years_counts": counts.reset_index().to_dict(orient="records")}
    sites = sites[in_use & have_local.to_numpy()].reset_index(drop=True)
    if PLUMBING:   # a harness check on random labels and a few overflows: says nothing about the comparison
        sites = sites.sample(n=min(300, len(sites)), random_state=1).reset_index(drop=True)
        res["plumbing"] = True
    res["sites"]["used"] = int(len(sites))
    res["sites"]["by_company"] = sites["company"].value_counts().to_dict()
    cells = set(zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True))
    res["cells"] = len(cells)
    log(f"{len(sites)} overflows in {len(cells)} cells")

    era = daily_rain_features(load_rain(cells, tags=("2024", "2025", "2026", "2026a"), start="2024-11-25"))
    cr = cell_radar_daily(radar_dir, cells)
    p0 = lead0_daily(cells)
    l3, l1, lstats = local_daily(ov_dir, sites["site_id"].tolist())
    res["local_radar_read"] = lstats
    log("rain sources built")

    labels = spill_days(ev)
    labels = labels[(labels.day >= Y0) & (labels.day <= Y1)]
    days = pd.date_range(Y0, Y1, freq="D", tz="UTC")
    base = build_site_days(sites, era, days, labels).reset_index(drop=True)
    base = base.merge(sites[["site_id", "company"]], on="site_id", how="left")
    ua = pd.read_parquet(config.PROCESSED / "overflow_urban_area.parquet")[["site_id", "bua_dist_m"]]
    base = base.merge(ua, on="site_id", how="left").reset_index(drop=True)
    src = {"C": attach(base, cr, KEY), "L3": attach(base, l3, SKEY), "L1": attach(base, l1, SKEY),
           "P": attach(base, p0, KEY), "E": base[SHORT].reset_index(drop=True).copy()}
    arms = arm_frames(base, src)
    ok = np.ones(len(base), bool)
    dropped = {}
    for k in ("C", "L3", "L1", "P", "E"):
        good = src[k][["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()
        dropped[k] = int((~good).sum())
        ok &= good
    ok &= base[["rain_7d", "rain_30d", "api"]].notna().all(axis=1).to_numpy()
    res["rows"] = {"before_mask": int(len(base)), "missing_by_source": dropped, "scored": int(ok.sum()),
                   "spill_days": int(base["y"].to_numpy()[ok].sum())}
    if PLUMBING:
        base["y"] = (np.random.default_rng(1).random(len(base)) < base["y"].mean()).astype(np.int8)
    base = base[ok].reset_index(drop=True)
    arms = {k: v[ok].reset_index(drop=True) for k, v in arms.items()}
    log(f"rows: {len(base)} of {res['rows']['before_mask']}, spill days {res['rows']['spill_days']}")

    # how the rain sources differ (description)
    dl = arms["L3"]["rain_d"].to_numpy(); dc = arms["C"]["rain_d"].to_numpy(); d1 = arms["L1"]["rain_d"].to_numpy()
    res["rain_description"] = {
        "pearson_L3_C": float(np.corrcoef(dl, dc)[0, 1]), "pearson_L1_L3": float(np.corrcoef(d1, dl)[0, 1]),
        "share_abs_L3_minus_C_ge_5mm": float((np.abs(dl - dc) >= 5).mean()),
        "share_abs_L1_minus_C_ge_5mm": float((np.abs(d1 - dc) >= 5).mean()),
        "ratio_totals_L3_over_C": float(dl.sum() / dc.sum()), "ratio_totals_P_over_C": float(arms["P"]["rain_d"].sum() / dc.sum()),
        "share_JJA_abs_L3_minus_C_ge_5mm": float((np.abs(dl - dc) >= 5)[season(base["day"]) == "JJA"].mean())}

    # folds
    block = ((base["day"].dt.month.to_numpy() - 1) // 2)
    in_a = np.isin(block, list(FOLD_A))
    dayn = (base["day"] - Y0).dt.days.to_numpy()
    test_days = {f: np.unique(dayn[in_a if f == "A" else ~in_a]) for f in ("A", "B")}

    def train_mask(f: str) -> np.ndarray:
        td = test_days[f]
        idx = np.searchsorted(td, dayn)
        near = np.minimum(np.abs(dayn - td[np.clip(idx, 0, len(td) - 1)]), np.abs(dayn - td[np.clip(idx - 1, 0, len(td) - 1)]))
        return (~(in_a if f == "A" else ~in_a)) & (near > EMBARGO)

    res["folds"] = {f: {"test_rows": int((in_a if f == "A" else ~in_a).sum()), "train_rows": int(train_mask(f).sum())}
                    for f in ("A", "B")}
    y = base["y"].to_numpy().astype(float)
    oof = {}
    hashes = {}
    for k in ARMS:
        df = frame_for(base, arms[k])
        p = np.full(len(df), np.nan)
        for f in ("A", "B"):
            tr, te = train_mask(f), (in_a if f == "A" else ~in_a)
            m = fit(df[tr])
            p[te] = m.predict(df[te])
            hashes[f"{k}/{f}"] = model_hash(m)
        oof[k] = p
        log(f"arm {k} fitted and predicted out of fold")
        del df
    assert all(np.isfinite(v).all() for v in oof.values())
    res["fold_model_sha256"] = hashes

    rng = np.random.default_rng(SEED)
    week = base["day"].dt.strftime("%G-%V").to_numpy()
    bt = Boot(base["site_id"].to_numpy(), week, dayn, rng)
    res["primary"] = {"by_arm": {k: summary(y, v) for k, v in oof.items()}}
    comps = {"L3-C": ("L3", "C"), "L1-C": ("L1", "C"), "L3-L1": ("L3", "L1"), "C-P": ("C", "P"), "L3-P": ("L3", "P"),
             "L1-P": ("L1", "P"), "C-E": ("C", "E"), "L3-E": ("L3", "E"), "L3-lag-P": ("L3-lag", "P"),
             "L3-lag-C-lag": ("L3-lag", "C-lag"), "C-lag-P": ("C-lag", "P")}
    res["primary"]["comparisons"] = {n: bt.diff(y, oof[a], oof[b]) for n, (a, b) in comps.items()}
    res["primary"]["verdict"] = verdict(res["primary"]["comparisons"]["L3-C"], res["primary"]["comparisons"]["L3-P"])
    log("primary comparisons done")

    # breakdowns (reported only)
    sn = season(base["day"])
    urban = (base["bua_dist_m"].fillna(np.inf) <= URBAN_M).to_numpy()
    groups = {**{f"company:{c}": (base["company"] == c).to_numpy() for c in sorted(base["company"].unique())},
              "urban": urban, "rural": ~urban, **{f"season:{s}": sn == s for s in ("DJF", "MAM", "JJA", "SON")}}
    res["breakdowns"] = {}
    for g, msk in groups.items():
        if y[msk].sum() == 0:
            res["breakdowns"][g] = {"rows": int(msk.sum()), "spill_days": 0}
            continue
        res["breakdowns"][g] = {"rows": int(msk.sum()), "spill_days": int(y[msk].sum()),
                                "brier": {k: float(np.mean((oof[k][msk] - y[msk]) ** 2)) for k in ARMS},
                                "L3-C": bt.diff(y, oof["L3"], oof["C"], msk)}
    # exploratory (decides nothing): where cell rain should miss most
    gap = np.abs(dl - dc)
    top = gap >= np.quantile(gap, 0.9)
    jja = sn == "JJA"
    top_jja = jja & (gap >= np.quantile(gap[jja], 0.9))
    res["exploratory"] = {n: {"spill_days": int(y[m].sum()), "L3-C": bt.diff(y, oof["L3"], oof["C"], m),
                              "L1-C": bt.diff(y, oof["L1"], oof["C"], m)}
                          for n, m in (("JJA", jja), ("top_tenth_L3_C_gap", top), ("top_tenth_gap_within_JJA", top_jja))}

    # the no-refit check: production spill_model.pkl on #343's rows (2025, United Utilities left out)
    prod = SpillModel.load(config.PROCESSED / "spill_model.pkl")
    nu = (base["company"] != "United Utilities").to_numpy()
    pn = {k: prod.predict(frame_for(base[nu].reset_index(drop=True), arms[k][nu].reset_index(drop=True)))
          for k in ("C", "L3", "L1", "P", "E")}
    bt2 = Boot(base["site_id"].to_numpy()[nu], week[nu], dayn[nu], np.random.default_rng(SEED))
    res["no_refit"] = {"rows": int(nu.sum()), "spill_days": int(y[nu].sum()),
                       "model_sha256": hashlib.sha256((config.PROCESSED / "spill_model.pkl").read_bytes()).hexdigest(),
                       "by_arm": {k: summary(y[nu], v) for k, v in pn.items()},
                       "L3-C": bt2.diff(y[nu], pn["L3"], pn["C"]), "L1-C": bt2.diff(y[nu], pn["L1"], pn["C"]),
                       "C-P": bt2.diff(y[nu], pn["C"], pn["P"])}
    log("no-refit check done")

    # the 2026 forward check: fit on all 2025 rows, freeze, score Thames 2026
    frozen = {}
    for k in ARMS:
        m = fit(frame_for(base, arms[k]))
        frozen[k] = m
        (out / f"model_2025_{k}.pkl").write_bytes(pickle.dumps(m, protocol=5))
    res["frozen_model_sha256"] = {k: model_hash(m) for k, m in frozen.items()}
    api = pd.read_parquet(config.PROCESSED / "api_events_thames_water.parquet")
    lead26 = cells_in([config.CACHE / d for d in RAIN_DIRS], "leads_*_2026.parquet")
    th = sites[(sites["company"] == "Thames Water") & sites["site_id"].isin(set(api["site_id"]))]
    thc = list(zip(*grid_cell(th["lat"].to_numpy(), th["lon"].to_numpy()), strict=True))
    th = th[[c in lead26 for c in thc]].reset_index(drop=True)
    fw = {"thames_overflows_in_stream_and_2025_rows": int((sites["company"] == "Thames Water").sum()),
          "with_2026_lead0": int(len(th))}
    if len(th):
        lab26 = spill_days(api)
        lab26 = lab26[(lab26.day >= F0) & (lab26.day <= F1)]
        b26 = build_site_days(th, era, pd.date_range(F0, F1, freq="D", tz="UTC"), lab26).reset_index(drop=True)
        s26 = {"C": attach(b26, cr, KEY), "L3": attach(b26, l3, SKEY), "L1": attach(b26, l1, SKEY),
               "P": attach(b26, p0, KEY), "E": b26[SHORT].reset_index(drop=True).copy()}
        a26 = arm_frames(b26, s26)
        ok26 = np.ones(len(b26), bool)
        for k in ("C", "L3", "L1", "P", "E"):
            ok26 &= s26[k][["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()
        ok26 &= b26[["rain_7d", "rain_30d", "api"]].notna().all(axis=1).to_numpy()
        b26 = b26[ok26].reset_index(drop=True)
        a26 = {k: v[ok26].reset_index(drop=True) for k, v in a26.items()}
        if PLUMBING:
            b26["y"] = (np.random.default_rng(2).random(len(b26)) < max(b26["y"].mean(), 0.01)).astype(np.int8)
        y26 = b26["y"].to_numpy().astype(float)
        p26 = {k: frozen[k].predict(frame_for(b26, a26[k])) for k in ARMS}
        bt3 = Boot(b26["site_id"].to_numpy(), b26["day"].dt.strftime("%G-%V").to_numpy(),
                   (b26["day"] - F0).dt.days.to_numpy(), np.random.default_rng(SEED))
        fw.update({"rows_before_mask": int(len(ok26)), "rows": int(len(b26)), "spill_days": int(y26.sum()),
                   "overflows_scored": int(b26["site_id"].nunique()),
                   "last_day": str(b26["day"].max().date()) if len(b26) else None,
                   "by_arm": {k: summary(y26, v) for k, v in p26.items()},
                   "comparisons": {n: bt3.diff(y26, p26[a], p26[b]) for n, (a, b) in comps.items()}})
    res["forward_2026_thames"] = fw
    log("forward check done")

    res["seconds"] = round(time.time() - T0, 1)
    (out / "score.json").write_text(json.dumps(res, indent=1, default=float))
    pc = res["primary"]["comparisons"]
    if PLUMBING:
        print("plumbing run: done; scores on random labels are not printed")
        return
    print(json.dumps({"verdict": res["primary"]["verdict"], "rows": res["rows"],
                      "brier": {k: v["brier"] for k, v in res["primary"]["by_arm"].items()},
                      "L3-C": pc["L3-C"], "L3-P": pc["L3-P"]}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:])
