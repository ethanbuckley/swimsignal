"""docs/RADAR-ISSUE-HOUR-TEST-2026-11.md: the spill model's form refitted on rain as a build would have it at an
issue hour. Cell radar for the hours the bucket had published by then, forecast rain for the rest of the day, against
the forecast alone. Eight issue hours, two forecasts for the hours still to come (lead 0 and lead 1).

    score.py <cell radar dir> <radar_publish_times.csv> <out dir>

Reads the EA start/stop files, annual returns, Thames's stream file and spill_model.pkl from config.PROCESSED, and
lead and ERA5-Land rain from config.CACHE. Writes <out dir>/score.json (summary figures only) and the frozen 2025
models' pickles. RADAR_ISSUE_HOUR_PLUMBING=1 runs the harness on 300 overflows with random labels and prints no score.
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
from dipcast.model.features import ALL_FEATURES, MIN_HOURS_PER_DAY, build_site_days, daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel
from dipcast.model.training import NINE, RAIN_DIRS, load_events, load_rain, site_years

COVERAGE = 0.9
SEED, BOOT = 20261113, 2000
EMBARGO = 7
WARN = 0.4
MARGIN = 0.01
HOURS = (0, 3, 6, 9, 12, 15, 18, 21)                 # issue hours, UTC
Y0, Y1 = pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2025-12-31", tz="UTC")
F0, F1 = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-08-31", tz="UTC")
READ0 = pd.Timestamp("2024-12-20", tz="UTC")       # hourly rain read from here: lags and 6 h windows need the days before
READ1 = pd.Timestamp("2026-09-01", tz="UTC")       # exclusive
RADAR_MONTHS = [f"{p:%Y-%m}" for p in pd.period_range("2024-12", "2025-12", freq="M")]
KEY = ["cell_lat", "cell_lon", "day"]
DAY_COLS = ["rain_d", "max1h_d", "max3h_d", "max6h_d"]
SHORT = DAY_COLS + ["rain_d1", "rain_d2", "rain_3d"]
FOLD_A = {0, 2, 4}                                   # two-month blocks Jan-Feb, May-Jun, Sep-Oct
PLUMBING = os.environ.get("RADAR_ISSUE_HOUR_PLUMBING") == "1"
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


# ------------------------------------------------------------------ hourly rain, wide (cells x hours)
class Hourly:
    """Hourly rain per cell on one grid of hour stamps (hour-ending, UTC), READ0 to READ1: radar (NaN where the
    hour's coverage is under COVERAGE or the hour is not held), lead 0 and lead 1 (NaN where not held), and for each
    hour the time the last of its composites reached the bucket (inf when none is listed)."""

    def __init__(self, radar_dir: Path, pub_csv: Path, cells: list[tuple[float, float]]):
        self.cells = cells
        self.stamps = pd.date_range(READ0, READ1, freq="h", tz="UTC", inclusive="left")
        self.nh = len(self.stamps)
        ci = {c: i for i, c in enumerate(cells)}
        self.radar = self._wide(self._radar_long(radar_dir, set(cells)), ci)
        lv = self._leads_long(set(cells))
        self.f0 = self._wide(lv[lv["lead"] == 0], ci)
        self.f1 = self._wide(lv[lv["lead"] == 1], ci)
        self.pub, self.pub_stats = self._publish(pub_csv)
        self.stamp_h = np.arange(self.nh, dtype=float)      # each stamp in hours since READ0, as `pub` is

    def _wide(self, long: pd.DataFrame, ci: dict) -> np.ndarray:
        out = np.full((len(ci), self.nh), np.nan, dtype=np.float32)
        long = long[(long["time"] >= READ0) & (long["time"] < READ1)]
        r = np.fromiter((ci[c] for c in zip(long["cell_lat"].round(3), long["cell_lon"].round(3), strict=True)),
                        dtype=np.int64, count=len(long))
        h = ((long["time"] - READ0) / pd.Timedelta(hours=1)).to_numpy().astype(np.int64)
        out[r, h] = long["precip_mm"].to_numpy(dtype=np.float32)
        return out

    @staticmethod
    def _radar_long(radar_dir: Path, cells: set) -> pd.DataFrame:
        frames = []
        for f in sorted(radar_dir.glob("radar_*.parquet")):
            p = f.stem.split("_")
            if (float(p[1]), float(p[2])) in cells and "2024-12" <= p[3] <= "2026-08":
                frames.append(pd.read_parquet(f))
        r = pd.concat(frames, ignore_index=True)
        r["precip_mm"] = np.where(r["coverage"] >= COVERAGE, r["radar_mm"], np.nan).astype(float)
        return r[["cell_lat", "cell_lon", "time", "precip_mm"]]

    @staticmethod
    def _leads_long(cells: set) -> pd.DataFrame:
        frames = []
        for d in RAIN_DIRS:
            for f in (config.CACHE / d).glob("leads_*.parquet"):
                p = f.stem.split("_")
                if (float(p[1]), float(p[2])) in cells and p[3] in ("2024", "2025", "2026"):
                    lv = pd.read_parquet(f)
                    frames.append(lv[lv["lead"].isin([0, 1])])
        lv = pd.concat(frames, ignore_index=True)
        return lv.drop_duplicates(["cell_lat", "cell_lon", "time", "lead"], keep="last")

    def _publish(self, pub_csv: Path) -> tuple[np.ndarray, dict]:
        """For the hour ending T, the latest LastModified among the composites at T-60, T-45, T-30, T-15 and T that
        the listing holds, in hours since READ0. inf when none is listed."""
        t = pd.read_csv(pub_csv, dtype={"scan_time": str})
        scan = pd.to_datetime(t["scan_time"], format="%Y%m%d%H%M", utc=True)
        lm = pd.to_datetime(t["last_modified"], utc=True)
        s = pd.Series(((lm - READ0) / pd.Timedelta(hours=1)).to_numpy(), index=scan).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        pub = np.full(self.nh, -np.inf)
        n = np.zeros(self.nh, dtype=int)
        for back in (0, 15, 30, 45, 60):
            v = s.reindex(self.stamps - pd.Timedelta(minutes=back)).to_numpy()
            ok = np.isfinite(v)
            pub = np.where(ok, np.maximum(pub, v), pub)
            n += ok
        pub = np.where(n > 0, pub, np.inf)
        return pub, {"hours": int(self.nh), "hours_with_5_composites_listed": int((n == 5).sum()),
                     "hours_with_none_listed": int((n == 0).sum())}

    def as_long(self, arr: np.ndarray) -> pd.DataFrame:
        cl = np.repeat([c[0] for c in self.cells], self.nh)
        cn = np.repeat([c[1] for c in self.cells], self.nh)
        return pd.DataFrame({"cell_lat": cl, "cell_lon": cn, "time": np.tile(self.stamps, len(self.cells)),
                             "precip_mm": arr.reshape(-1).astype(float)})


def window_features(w: np.ndarray) -> dict[str, np.ndarray]:
    """Day features from 72 hourly values per cell-day (the two days before, then the day), as
    features.daily_rain_features makes them: a day with under MIN_HOURS_PER_DAY finite hours has no total; the 3 h and
    6 h windows end in the day's hours and reach back into the day before."""
    fin = np.isfinite(w)
    z = np.where(fin, w, 0.0).astype(np.float64)
    out = {}
    for name, a, b in (("rain_d2", 0, 24), ("rain_d1", 24, 48), ("rain_d", 48, 72)):
        tot = z[..., a:b].sum(axis=-1)
        out[name] = np.where(fin[..., a:b].sum(axis=-1) >= MIN_HOURS_PER_DAY, tot, np.nan)
    known = np.isfinite(out["rain_d"])
    cs = np.concatenate([np.zeros(z.shape[:-1] + (1,)), np.cumsum(z, axis=-1)], axis=-1)
    out["max1h_d"] = np.where(known, z[..., 48:].max(axis=-1), np.nan)
    for name, k in (("max3h_d", 3), ("max6h_d", 6)):
        roll = cs[..., 49:73] - cs[..., 49 - k:73 - k]
        out[name] = np.where(known, roll.max(axis=-1), np.nan)
    return out


def windows(h: Hourly, days: pd.DatetimeIndex) -> np.ndarray:
    """Hour index of each day's 72-hour window: the two days before, then the day."""
    start = ((days - READ0) / pd.Timedelta(hours=1)).to_numpy().astype(np.int64)
    assert start.min() >= 48 and start.max() + 24 <= h.nh
    return start[:, None] - 48 + np.arange(72)[None, :]


def issue_arms(h: Hourly, days: pd.DatetimeIndex, hour: int) -> tuple[dict[str, pd.DataFrame], dict]:
    """The three arms at one issue hour, per cell-day. At the issue instant (the day's 00:00 UTC plus `hour`):
    R0  radar for each hour the bucket had published by then (and with coverage); lead 0 for every other hour;
    R1  the same, with lead 1 for the hours stamped after the issue instant;
    F1  no radar: lead 0 for hours stamped up to the issue instant, lead 1 after."""
    idx = windows(h, days)                                   # days x 72
    issue = idx[:, 48] + hour                                # stamp index of the issue instant
    past = h.stamp_h[idx] <= issue[:, None]                  # days x 72
    there = h.pub[idx] <= issue[:, None]
    rad, f0, f1 = h.radar[:, idx], h.f0[:, idx], h.f1[:, idx]   # cells x days x 72
    use = there[None] & np.isfinite(rad)
    rest1 = np.where(past[None], f0, f1)
    vals = {"R0": np.where(use, rad, f0), "R1": np.where(use, rad, rest1), "F1": rest1}
    today = np.zeros(72, bool); today[48:] = True
    stats = {"radar_hours_of_the_day_used_mean": float(use[..., 48:].sum(axis=-1).mean()),
             "share_past_hours_of_the_day_on_forecast": float(1 - use[:, past & today[None]].mean()) if hour else None,
             "share_two_days_before_on_forecast": float(1 - use[..., :48].mean())}
    return {k: to_frame(h, days, window_features(v)) for k, v in vals.items()}, stats


def to_frame(h: Hourly, days: pd.DatetimeIndex, feats: dict[str, np.ndarray]) -> pd.DataFrame:
    nc, nd = len(h.cells), len(days)
    df = pd.DataFrame({"cell_lat": np.repeat([c[0] for c in h.cells], nd), "cell_lon": np.repeat([c[1] for c in h.cells], nd),
                       "day": np.tile(days, nc)})
    for k in DAY_COLS + ["rain_d1", "rain_d2"]:
        df[k] = feats[k].reshape(-1)
    return df


def check_features(h: Hourly, days: pd.DatetimeIndex) -> dict:
    """window_features against features.daily_rain_features, on radar alone and on lead 0 alone. Rain values only."""
    idx = windows(h, days)
    out = {}
    for name, arr in (("radar", h.radar), ("lead0", h.f0)):
        mine = to_frame(h, days, window_features(arr[:, idx]))
        ref = daily_rain_features(h.as_long(arr))
        m = mine.merge(ref[KEY + DAY_COLS + ["rain_d1", "rain_d2"]], on=KEY, how="left", suffixes=("", "_ref"))
        worst, nan_mismatch = 0.0, 0
        for c in DAY_COLS + ["rain_d1", "rain_d2"]:
            a, b = m[c].to_numpy(), m[c + "_ref"].to_numpy()
            nan_mismatch += int((np.isnan(a) != np.isnan(b)).sum())
            both = np.isfinite(a) & np.isfinite(b)
            worst = max(worst, float(np.abs(a[both] - b[both]).max()))
        out[name] = {"cell_days": int(len(m)), "largest_abs_difference_mm": worst, "nan_mismatches": nan_mismatch}
        assert worst < 1e-3 and nan_mismatch == 0, f"window_features differs from daily_rain_features on {name}: {out[name]}"
    return out


# ------------------------------------------------------------------ arms on rows
def attach(base: pd.DataFrame, src: pd.DataFrame) -> pd.DataFrame:
    """The short-range columns of `src` on base's rows, in base's order."""
    cols = DAY_COLS + ["rain_d1", "rain_d2"]
    m = base[KEY].merge(src[KEY + cols], on=KEY, how="left")
    assert len(m) == len(base)
    m = m[cols].reset_index(drop=True)
    m["rain_3d"] = m["rain_d"] + m["rain_d1"] + m["rain_d2"]
    return m


def frame_for(base: pd.DataFrame, short: pd.DataFrame) -> pd.DataFrame:
    df = base.drop(columns=[c for c in SHORT if c in base]).reset_index(drop=True)
    df[SHORT] = short[SHORT].to_numpy()
    return df.astype({c: np.float32 for c in ALL_FEATURES})


def fit(df: pd.DataFrame) -> SpillModel:
    m = SpillModel()
    m.fit_pooled(df, seed=0)
    m.fit_site_offsets(df, prior_strength=15.0, recency=1.0)
    return m


def build_arms(h: Hourly, days: pd.DatetimeIndex, cr: pd.DataFrame, p0: pd.DataFrame) -> tuple[dict, dict]:
    """Every arm's short-range features per cell-day. C and P as #640 made them; C-lag is P's day with C's two days
    before; then R0, R1 and F1 at each issue hour."""
    arms = {"C": cr, "P": p0}
    lag = p0[KEY + DAY_COLS].merge(cr[KEY + ["rain_d1", "rain_d2"]], on=KEY, how="inner")
    arms["C-lag"] = lag
    stats = {}
    for hr in HOURS:
        a, stats[str(hr)] = issue_arms(h, days, hr)
        for k, v in a.items():
            arms[f"{k}@{hr:02d}"] = v
    return arms, stats


# ------------------------------------------------------------------ scoring
class Boot:
    """Brier differences with two-way (overflow x week, overflow x day) and one-way (week) cluster bootstraps,
    the same draws for every comparison. `diff` takes one arm against another; `pooled` takes several pairs on the
    same rows and averages each row's difference over the pairs."""

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

    def pooled(self, y, pairs: list[tuple[np.ndarray, np.ndarray]], mask=None) -> dict:
        mask = np.ones(len(y), bool) if mask is None else mask
        e = np.mean([(pa - y) ** 2 - (pb - y) ** 2 for pa, pb in pairs], axis=0)
        ba = float(np.mean([np.mean((pa[mask] - y[mask]) ** 2) for pa, _ in pairs]))
        bb = float(np.mean([np.mean((pb[mask] - y[mask]) ** 2) for _, pb in pairs]))
        wk = np.bincount(self.wi[mask], e[mask], minlength=self.nw); wn = np.bincount(self.wi[mask], minlength=self.nw)
        with np.errstate(invalid="ignore", divide="ignore"):
            one = (self.dw @ wk) / (self.dw @ wn)
        return {"rows": int(mask.sum()), "brier_a": ba, "brier_b": bb, "diff": ba - bb,
                "skill_vs_b": 1 - ba / bb if bb > 0 else None,
                "ci95_overflow_week": self._two(e, mask, self.si, self.ns, self.ds, self.wi, self.nw, self.dw),
                "ci95_overflow_day": self._two(e, mask, self.si, self.ns, self.ds, self.di, self.nd, self.dd),
                "ci95_week": [float(np.nanpercentile(one, 2.5)), float(np.nanpercentile(one, 97.5))]}

    def diff(self, y, pa, pb, mask=None) -> dict:
        return self.pooled(y, [(pa, pb)], mask)


def summary(y, p) -> dict:
    return {"brier": float(np.mean((p - y) ** 2)),
            "auc": float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else None,
            "spill_days_at_0.4": float((p[y == 1] >= WARN).mean()) if (y == 1).any() else None,
            "dry_days_at_0.4": float((p[y == 0] >= WARN).mean()) if (y == 0).any() else None,
            "mean_p": float(p.mean()), "rate": float(y.mean())}


def verdict(d0: dict, d1: dict) -> dict:
    """H, S, N or W from the two pooled comparisons, as the statement gives them."""
    lo0, hi0 = d0["ci95_overflow_week"]
    lo1, hi1 = d1["ci95_overflow_week"]
    below0, below1 = hi0 < 0, hi1 < 0
    above = lo0 > 0 or lo1 > 0
    big = d0["skill_vs_b"] >= MARGIN and d1["skill_vs_b"] >= MARGIN
    v = "W" if above else "H" if (below0 and below1 and big) else "S" if (below0 or below1) else "N"
    return {"verdict": v, "d0_ci_below_zero": bool(below0), "d1_ci_below_zero": bool(below1),
            "d0_skill": d0["skill_vs_b"], "d1_skill": d1["skill_vs_b"], "both_skills_at_least_margin": bool(big),
            "d0_rules_out_1pct_gain": bool(lo0 > -MARGIN * d0["brier_b"]),
            "d1_rules_out_1pct_gain": bool(lo1 > -MARGIN * d1["brier_b"])}


def season(day: pd.Series) -> np.ndarray:
    m = day.dt.month.to_numpy()
    return np.select([np.isin(m, [12, 1, 2]), np.isin(m, [3, 4, 5]), np.isin(m, [6, 7, 8])], ["DJF", "MAM", "JJA"], "SON")


def model_hash(m: SpillModel) -> str:
    return hashlib.sha256(pickle.dumps(m, protocol=5)).hexdigest()


def comparisons(bt: Boot, y: np.ndarray, p: dict, mask=None) -> dict:
    """The pooled deciding pair and the per-hour figures, on one set of predictions."""
    out = {"D0_pooled_R0_minus_P": bt.pooled(y, [(p[f"R0@{h:02d}"], p["P"]) for h in HOURS], mask),
           "D1_pooled_R1_minus_F1": bt.pooled(y, [(p[f"R1@{h:02d}"], p[f"F1@{h:02d}"]) for h in HOURS], mask)}
    if mask is None:
        out["by_hour"] = {f"{h:02d}": {"R0-P": bt.diff(y, p[f"R0@{h:02d}"], p["P"]),
                                       "R1-F1": bt.diff(y, p[f"R1@{h:02d}"], p[f"F1@{h:02d}"]),
                                       "R0-C-lag": bt.diff(y, p[f"R0@{h:02d}"], p["C-lag"]),
                                       "C-R0": bt.diff(y, p["C"], p[f"R0@{h:02d}"]),
                                       "F1-P": bt.diff(y, p[f"F1@{h:02d}"], p["P"])} for h in HOURS}
        out["C-P"] = bt.diff(y, p["C"], p["P"])
        out["C-lag-P"] = bt.diff(y, p["C-lag"], p["P"])
    return out


# ------------------------------------------------------------------ main
def main(radar_dir: str, pub_csv: str, out_dir: str) -> None:
    radar_dir, out = Path(radar_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res: dict = {"protocol": "docs/RADAR-ISSUE-HOUR-TEST-2026-11.md", "seed": SEED, "draws": BOOT, "issue_hours_utc": list(HOURS)}

    # rows: 2025 site-years of the nine companies, in cells with cell radar for every month and 2025 lead forecasts
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    sites, counts = site_years(ar, ev, NINE, 2025)
    radar_cells = set.intersection(*(cells_in([radar_dir], f"radar_*_{m}.parquet") for m in RADAR_MONTHS))
    lead25 = cells_in([config.CACHE / d for d in RAIN_DIRS], "leads_*_2025.parquet")
    use = radar_cells & lead25
    sc = list(zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True))
    in_use = np.array([c in use for c in sc])
    res["sites"] = {"site_years_2025": int(len(sites)), "in_cells_with_cell_radar_and_leads": int(in_use.sum()),
                    "site_years_counts": counts.reset_index().to_dict(orient="records")}
    sites = sites[in_use].reset_index(drop=True)
    if PLUMBING:   # a harness check on random labels and a few overflows: says nothing about the comparison
        sites = sites.sample(n=min(300, len(sites)), random_state=1).reset_index(drop=True)
        res["plumbing"] = True
    res["sites"]["used"] = int(len(sites))
    res["sites"]["by_company"] = sites["company"].value_counts().to_dict()
    cells = sorted(set(zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True)))
    cells = [(round(float(a), 3), round(float(b), 3)) for a, b in cells]
    res["cells"] = len(cells)
    log(f"{len(sites)} overflows in {len(cells)} cells")

    era = daily_rain_features(load_rain(set(cells), tags=("2024", "2025", "2026", "2026a"), start="2024-11-25"))
    h = Hourly(radar_dir, Path(pub_csv), cells)
    res["publish_times"] = h.pub_stats
    all_days = pd.date_range(Y0, F1, freq="D", tz="UTC")
    res["feature_check"] = check_features(h, all_days)
    log(f"hourly rain read; window features match daily_rain_features: {res['feature_check']}")
    cr = daily_rain_features(h.as_long(h.radar))
    p0 = daily_rain_features(h.as_long(h.f0))
    arms, res["issue_hour_stats"] = build_arms(h, all_days, cr, p0)
    names = list(arms)
    res["arms"] = names
    log(f"{len(names)} arms built")

    labels = spill_days(ev)
    labels = labels[(labels.day >= Y0) & (labels.day <= Y1)]
    days = pd.date_range(Y0, Y1, freq="D", tz="UTC")
    base = build_site_days(sites, era, days, labels).reset_index(drop=True)
    base = base.merge(sites[["site_id", "company"]], on="site_id", how="left").reset_index(drop=True)
    ok = base[["rain_7d", "rain_30d", "api"]].notna().all(axis=1).to_numpy().copy()
    ok &= base[["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()          # ERA5-Land, as #640's E
    dropped = {"E": int((~ok).sum())}
    for k in names:
        good = attach(base, arms[k])[["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()
        dropped[k] = int((~good).sum())
        ok &= good
    res["rows"] = {"before_mask": int(len(base)), "missing_by_arm": dropped, "scored": int(ok.sum()),
                   "spill_days": int(base["y"].to_numpy()[ok].sum())}
    if PLUMBING:
        base["y"] = (np.random.default_rng(1).random(len(base)) < base["y"].mean()).astype(np.int8)
    base = base[ok].reset_index(drop=True)
    log(f"rows: {len(base)} of {res['rows']['before_mask']}, spill days {res['rows']['spill_days']}")

    # how much of the day's rain the radar has seen by each issue hour (description, no label)
    cday = attach(base, arms["C"])["rain_d"].to_numpy()
    wet = cday >= 1.0
    res["rain_description"] = {"rows_with_radar_day_total_ge_1mm": int(wet.sum())}
    res["rain_description"]["pearson_P_day_total_with_C"] = float(np.corrcoef(attach(base, arms["P"])["rain_d"].to_numpy(), cday)[0, 1])
    for hr in HOURS:
        r = attach(base, arms[f"R0@{hr:02d}"])["rain_d"].to_numpy()
        res["rain_description"][f"{hr:02d}"] = {"pearson_R0_day_total_with_C": float(np.corrcoef(r, cday)[0, 1])}

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
    oof, one_model, hashes, frozen = {}, {}, {}, {}
    c_models = {}
    for k in names:                                    # C first: its fold models also score the one-model variant
        df = frame_for(base, attach(base, arms[k]))
        p = np.full(len(df), np.nan)
        q = np.full(len(df), np.nan)
        for f in ("A", "B"):
            tr, te = train_mask(f), (in_a if f == "A" else ~in_a)
            m = fit(df[tr])
            p[te] = m.predict(df[te])
            hashes[f"{k}/{f}"] = model_hash(m)
            if k == "C":
                c_models[f] = m
            if k.startswith("R0@"):
                q[te] = c_models[f].predict(df[te])
        oof[k] = p
        if k.startswith("R0@"):
            one_model[k] = q
        frozen[k] = fit(df)
        (out / f"model_2025_{k.replace('@', '_')}.pkl").write_bytes(pickle.dumps(frozen[k], protocol=5))
        log(f"arm {k} fitted, predicted out of fold, and refitted on all of 2025")
        del df
    assert all(np.isfinite(v).all() for v in oof.values())
    res["fold_model_sha256"] = hashes
    res["frozen_model_sha256"] = {k: model_hash(m) for k, m in frozen.items()}

    rng = np.random.default_rng(SEED)
    week = base["day"].dt.strftime("%G-%V").to_numpy()
    bt = Boot(base["site_id"].to_numpy(), week, dayn, rng)
    res["primary"] = {"by_arm": {k: summary(y, v) for k, v in oof.items()}, "comparisons": comparisons(bt, y, oof)}
    pc = res["primary"]["comparisons"]
    res["primary"]["verdict"] = verdict(pc["D0_pooled_R0_minus_P"], pc["D1_pooled_R1_minus_F1"])
    log("primary comparisons done")

    # breakdowns (reported only)
    sn = season(base["day"])
    groups = {**{f"company:{c}": (base["company"] == c).to_numpy() for c in sorted(base["company"].unique())},
              **{f"season:{s}": sn == s for s in ("DJF", "MAM", "JJA", "SON")}}
    res["breakdowns"] = {}
    for g, msk in groups.items():
        if y[msk].sum() == 0:
            res["breakdowns"][g] = {"rows": int(msk.sum()), "spill_days": 0}
            continue
        res["breakdowns"][g] = {"rows": int(msk.sum()), "spill_days": int(y[msk].sum()), **comparisons(bt, y, oof, msk)}

    # one model for every hour (secondary): the full-day radar fit (C's fold models) fed each hour's R0, against P's own fit
    res["one_model"] = {"by_arm": {k: summary(y, v) for k, v in one_model.items()},
                        "pooled_C_model_on_R0_minus_P": bt.pooled(y, [(one_model[f"R0@{hr:02d}"], oof["P"]) for hr in HOURS]),
                        "by_hour": {f"{hr:02d}": bt.diff(y, one_model[f"R0@{hr:02d}"], oof["P"]) for hr in HOURS}}

    # the no-refit check (secondary): production spill_model.pkl fed each hour's R0 and P, United Utilities left out
    prod = SpillModel.load(config.PROCESSED / "spill_model.pkl")
    nu = (base["company"] != "United Utilities").to_numpy()
    bnu = base[nu].reset_index(drop=True)
    pn = {k: prod.predict(frame_for(bnu, attach(bnu, arms[k]))) for k in ["P", "C"] + [f"R0@{hr:02d}" for hr in HOURS]}
    bt2 = Boot(bnu["site_id"].to_numpy(), week[nu], dayn[nu], np.random.default_rng(SEED))
    res["no_refit"] = {"rows": int(nu.sum()), "spill_days": int(y[nu].sum()),
                       "model_sha256": hashlib.sha256((config.PROCESSED / "spill_model.pkl").read_bytes()).hexdigest(),
                       "by_arm": {k: summary(y[nu], v) for k, v in pn.items()},
                       "pooled_R0_minus_P": bt2.pooled(y[nu], [(pn[f"R0@{hr:02d}"], pn["P"]) for hr in HOURS]),
                       "by_hour": {f"{hr:02d}": bt2.diff(y[nu], pn[f"R0@{hr:02d}"], pn["P"]) for hr in HOURS},
                       "C-P": bt2.diff(y[nu], pn["C"], pn["P"])}
    log("one-model and no-refit checks done")

    # the 2026 forward check: the models fitted on all 2025 rows, frozen, on Thames 2026
    api = pd.read_parquet(config.PROCESSED / "api_events_thames_water.parquet")
    lead26 = cells_in([config.CACHE / d for d in RAIN_DIRS], "leads_*_2026.parquet")
    th = sites[(sites["company"] == "Thames Water") & sites["site_id"].isin(set(api["site_id"]))]
    thc = list(zip(*grid_cell(th["lat"].to_numpy(), th["lon"].to_numpy()), strict=True))
    th = th[[(round(float(a), 3), round(float(b), 3)) in lead26 for a, b in thc]].reset_index(drop=True)
    fw = {"thames_overflows_in_2025_rows": int((sites["company"] == "Thames Water").sum()), "with_2026_leads": int(len(th))}
    if len(th):
        lab26 = spill_days(api)
        lab26 = lab26[(lab26.day >= F0) & (lab26.day <= F1)]
        b26 = build_site_days(th, era, pd.date_range(F0, F1, freq="D", tz="UTC"), lab26).reset_index(drop=True)
        ok26 = b26[["rain_d", "rain_d1", "rain_d2", "rain_7d", "rain_30d", "api"]].notna().all(axis=1).to_numpy().copy()
        for k in names:
            ok26 &= attach(b26, arms[k])[["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()
        n26 = len(b26)
        b26 = b26[ok26].reset_index(drop=True)
        if PLUMBING:
            b26["y"] = (np.random.default_rng(2).random(len(b26)) < max(b26["y"].mean(), 0.01)).astype(np.int8)
        y26 = b26["y"].to_numpy().astype(float)
        p26 = {k: frozen[k].predict(frame_for(b26, attach(b26, arms[k]))) for k in names}
        bt3 = Boot(b26["site_id"].to_numpy(), b26["day"].dt.strftime("%G-%V").to_numpy(),
                   (b26["day"] - F0).dt.days.to_numpy(), np.random.default_rng(SEED))
        fw.update({"rows_before_mask": int(n26), "rows": int(len(b26)), "spill_days": int(y26.sum()),
                   "overflows_scored": int(b26["site_id"].nunique()),
                   "last_day": str(b26["day"].max().date()) if len(b26) else None,
                   "by_arm": {k: summary(y26, v) for k, v in p26.items()}, "comparisons": comparisons(bt3, y26, p26)})
    res["forward_2026_thames"] = fw
    log("forward check done")

    res["seconds"] = round(time.time() - T0, 1)
    (out / "score.json").write_text(json.dumps(res, indent=1, default=float))
    if PLUMBING:
        print("plumbing run: done; scores on random labels are not printed")
        return
    print(json.dumps({"verdict": res["primary"]["verdict"], "rows": res["rows"]["scored"],
                      "D0": pc["D0_pooled_R0_minus_P"], "D1": pc["D1_pooled_R1_minus_F1"]}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:])
