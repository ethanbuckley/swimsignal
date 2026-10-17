"""docs/TRANSPORT-FIT-TEST-2026-10.md: fit river speed, T90 and a dilution exponent to the E. coli samples.

    fit.py prep  <out.parquet>    hindcast risk on every sample day, for every setting on the grid
    fit.py score <rows.parquet> <out.json>   leave-one-year-out selection, held-out scores, bootstrap

prep is validate_ecoli.py's hindcast, unchanged up to the transport step: the same samples, pins
(eval_pins.bathing_water_pin), overflows, spill model, reanalysis rain, lead-0 calibration and missing-rain
rule. The spill chances do not depend on the transport settings, so they are made once per bathing water;
then for each setting the transport weights and travel times come from transport.upstream_overflows, and
the risk from combine_daily's rule. combine_daily and missing_share loop in Python, so they are
re-written here with numpy (_shift); prep checks them against transport's own on the current settings.

score: rows with a figure under every setting. Rivers and lakes apart. For each year, the setting with the
best within-site Spearman on the other years is scored on that year. The held-out rows of the four years
are pooled and compared with the current settings on the same rows, with a calendar-week cluster bootstrap.
"""

from __future__ import annotations

import itertools
import json
import logging
import sys

import numpy as np
import pandas as pd
from eval_pins import bathing_water_pin
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model import transport
from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features
from dipcast.model.forecast import MAX_MISSING_SHARE, calibrate_at_lead
from dipcast.model.spill_model import SpillModel
from dipcast.network.rivers import RiverNetwork
from dipcast.overflows import load_overflows

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("transport_fit")
TZ = "Europe/London"

SPEEDS = (0.2, 0.35, 0.5, 0.75, 1.0)          # river speed, m/s
T90S = (12.0, 20.0, 30.0, 48.0, 72.0)         # hours
POWERS = (0.5, 1.0, 1.5)                      # exponent on the length ratio
CURRENT = (0.5, 30.0, 1.0)
GRID = [CURRENT] + [g for g in itertools.product(SPEEDS, T90S, POWERS) if g != CURRENT]   # current first: wins ties
BOOT = 2000
SEED = 20261016


def key(g: tuple[float, float, float]) -> str:
    v, t, p = g
    return f"v{v:g}_t{t:g}_p{p:g}"


def _shift(p: np.ndarray, travel_h: np.ndarray) -> np.ndarray:
    """transport.shift_by_travel with numpy slices: each row moved later by its travel time in days,
    a fractional day split between two arrival days."""
    n, d = p.shape
    shift = np.asarray(travel_h, dtype=float) / 24.0
    k = np.floor(shift).astype(int)
    a = shift - k
    eff = np.zeros((n, d), dtype=float)
    for i in range(n):
        if k[i] < d:
            eff[i, k[i]:] += (1 - a[i]) * p[i, :d - k[i]]
        if k[i] + 1 < d:
            eff[i, k[i] + 1:] += a[i] * p[i, :d - k[i] - 1]
    return eff


def combine(pm: np.ndarray, w: np.ndarray, tr: np.ndarray) -> np.ndarray:
    if len(w) == 0:
        return np.zeros(pm.shape[1])
    return 1.0 - np.prod(1.0 - np.clip(_shift(np.nan_to_num(pm, nan=0.0), tr), 0, 1) * w[:, None], axis=0)


def missing(ok: np.ndarray, w: np.ndarray, tr: np.ndarray) -> np.ndarray:
    if len(w) == 0 or w.sum() <= 0:
        return np.zeros(ok.shape[1])
    return np.clip((_shift((~ok).astype(float), tr) * w[:, None]).sum(axis=0) / w.sum(), 0, 1)


def prep(out_path: str) -> None:
    samples = pd.read_parquet(config.RAW / "bwq_samples.parquet").dropna(subset=["ecoli", "sample_time"]).copy()
    samples["day"] = samples["sample_time"].dt.floor("D")
    samples["log_ecoli"] = np.log10(samples["ecoli"].clip(lower=1))
    net = RiverNetwork.load(); ov = load_overflows(net)
    model = SpillModel.load()
    files = sorted((config.CACHE / "rain").glob("archive_*.parquet"))
    rain = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    rain["time"] = rain["time"].dt.tz_convert(TZ)
    daily = daily_rain_features(rain)
    cells = set(zip(rain["cell_lat"].round(3), rain["cell_lon"].round(3), strict=True))
    log.info("%d samples, %d sites, %d rain files, %d settings", len(samples), samples.bw_id.nunique(), len(files), len(GRID))

    out, checks = [], []
    for bw_id, g in samples.groupby("bw_id"):
        s = g.iloc[0]
        cl, cn = (round(float(v), 3) for v in grid_cell(float(s.lat), float(s.lon)))
        if (cl, cn) not in cells:
            log.warning("%s: no rainfall for site cell", s["name"]); continue   # validate_ecoli skips these too
        pin = bathing_water_pin(net, bw_id, float(s.lon), float(s.lat))
        ups = {gg: transport.upstream_overflows(net, pin, ov, velocity_ms=gg[0], t90_h=gg[1], dilution_power=gg[2])
               for gg in GRID}
        base = ups[CURRENT]
        rows = g[["bw_id", "name", "kind", "undertaker", "sample_time", "day", "ecoli", "log_ecoli"]].copy()
        rows["upstream"] = len(base)
        if len(base):
            ids = base["site_id"].to_numpy()
            assert len(set(ids)) == len(ids), bw_id
            for gg, up in ups.items():
                assert set(up["site_id"]) == set(ids), (bw_id, gg)   # the cap is on distance: the same overflows
                ups[gg] = up.set_index("site_id").loc[ids].reset_index()
            sample_days = pd.DatetimeIndex(sorted(g["day"].unique()))
            lead = max(transport.history_days(up["travel_h"]) for up in ups.values())
            days = pd.date_range(sample_days.min() - pd.Timedelta(days=lead), sample_days.max(), freq="D")
            sd = build_site_days(base[["site_id", "lat", "lon", "company", "lta_spills", "spill_hours",
                                       "edm_operational_pct"]], daily, days)
            sd["ok"] = sd["rain_d"].notna()
            X = sd.astype({f: np.float32 for f in ALL_FEATURES}).fillna({f: 0.0 for f in ALL_FEATURES})
            sd["p"] = np.where(sd["ok"], model.predict(X), np.nan)
            mat = sd.pivot(index="site_id", columns="day", values="p").reindex(index=ids, columns=days)
            okm = sd.pivot(index="site_id", columns="day", values="ok").reindex(index=ids, columns=days)
            pm = calibrate_at_lead(mat.to_numpy(dtype=float), lead=0)
            ok = okm.fillna(False).to_numpy(dtype=bool)
            for gg, up in ups.items():
                w = up["weight"].to_numpy(dtype=float); tr = up["travel_h"].to_numpy(dtype=float)
                miss = missing(ok, w, tr); risk = combine(pm, w, tr)
                if gg == CURRENT:   # the numpy rewrite against transport's own
                    checks.append({"bw_id": bw_id,
                                   "combine": float(np.nanmax(np.abs(risk - transport.combine_daily(pm, w, tr)))),
                                   "missing": float(np.nanmax(np.abs(miss - transport.missing_share(ok, w, tr))))})
                r = pd.Series(np.where(miss <= MAX_MISSING_SHARE, risk, np.nan), index=days)
                rows[key(gg)] = rows["day"].map(r).to_numpy(dtype=float)
        out.append(rows)
    df = pd.concat(out, ignore_index=True)
    df.to_parquet(out_path, index=False)
    ch = pd.DataFrame(checks)
    print(json.dumps({"rows": len(df), "sites": int(df.bw_id.nunique()),
                      "sites_with_upstream": int(df[df.upstream > 0].bw_id.nunique()),
                      "max_diff_combine": float(ch["combine"].max()), "max_diff_missing": float(ch["missing"].max())}))


# --------------------------------------------------------------------------- scoring

def _within(d: pd.DataFrame, col: str, by: list[str]) -> pd.Series:
    return d[col] - d.groupby(by)[col].transform("mean")


def rho_within(d: pd.DataFrame, col: str, by: list[str]) -> float:
    """validate_ecoli's within-site Spearman: prediction and log E. coli less their group means, pooled."""
    return float(spearmanr(_within(d, col, by), _within(d, "log_ecoli", by)).statistic)


def auc900(d: pd.DataFrame, col: str) -> float:
    y = (d["ecoli"] > 900).astype(int)
    return float(roc_auc_score(y, d[col])) if 0 < y.mean() < 1 else float("nan")


def select(train: pd.DataFrame) -> tuple[tuple, float]:
    """The setting with the best within-site Spearman on these rows (site means over all their years)."""
    best, best_s = None, -np.inf
    for gg in GRID:
        sc = rho_within(train, key(gg), ["bw_id"])
        if sc > best_s:
            best, best_s = gg, sc
    return best, best_s


def loyo(d: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Held-out rows with 'cand' (the setting chosen without their year) and 'cur' (current settings)."""
    held, folds = [], []
    for y in sorted(d["year"].unique()):
        g, s = select(d[d["year"] != y])
        h = d[d["year"] == y].copy()
        h["cand"] = h[key(g)]; h["cur"] = h[key(CURRENT)]
        held.append(h)
        folds.append({"year": int(y), "chosen": key(g), "train_rho": round(s, 4), "n_held": len(h),
                      "held_rho_chosen": round(rho_within(h, "cand", ["bw_id"]), 4),
                      "held_rho_current": round(rho_within(h, "cur", ["bw_id"]), 4)})
    return pd.concat(held), folds


def paired(h: pd.DataFrame, rng: np.random.Generator) -> dict:
    """Held-out scores, chosen against current, with a calendar-week cluster bootstrap of the changes.
    Within-site means are over each site's rows in one year (each held-out year had its own setting)."""
    by = ["bw_id", "year"]

    def scores(x: pd.DataFrame) -> tuple[float, float, float, float]:
        return rho_within(x, "cand", by), rho_within(x, "cur", by), auc900(x, "cand"), auc900(x, "cur")

    rc, ru, ac, au = scores(h)
    weeks = h["week"].to_numpy()
    uw = np.unique(weeks)
    pos = {w: np.flatnonzero(weeks == w) for w in uw}
    dr, da = [], []
    for _ in range(BOOT):
        idx = np.concatenate([pos[w] for w in rng.choice(uw, size=len(uw), replace=True)])
        b = h.iloc[idx]
        brc, bru, bac, bau = scores(b)
        dr.append(brc - bru); da.append(bac - bau)
    q = lambda x: [round(float(v), 4) for v in np.nanpercentile(x, [2.5, 97.5])]
    return {"n": len(h), "sites": int(h.bw_id.nunique()), "weeks": len(uw), "over_900": int((h.ecoli > 900).sum()),
            "rho_chosen": round(rc, 4), "rho_current": round(ru, 4), "rho_change": round(rc - ru, 4), "rho_ci": q(dr),
            "auc_chosen": round(ac, 4), "auc_current": round(au, 4), "auc_change": round(ac - au, 4), "auc_ci": q(da)}


def score(rows_path: str, out_path: str) -> None:
    df = pd.read_parquet(rows_path)
    cols = [key(gg) for gg in GRID]
    d = df[df.upstream > 0].dropna(subset=cols + ["log_ecoli"]).copy()
    t = d["sample_time"].dt.tz_convert(TZ) if d["sample_time"].dt.tz is not None else d["sample_time"]
    d["year"] = t.dt.year
    iso = t.dt.isocalendar()
    d["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    res = {"rows_with_upstream": int((df.upstream > 0).sum()), "rows_scored": len(d),
           "rows_dropped_no_figure": int((df.upstream > 0).sum() - len(d))}
    rng = np.random.default_rng(SEED)
    held = {}
    for kind in ("river", "lake"):
        dk = d[d.kind == kind]
        h, folds = loyo(dk)
        held[kind] = h
        full, full_s = select(dk)
        res[kind] = {"n": len(dk), "sites": int(dk.bw_id.nunique()),
                     "by_year": dk.groupby("year").size().to_dict(),
                     "folds": folds, "full_data_choice": key(full), "full_data_rho": round(full_s, 4),
                     "held_out": paired(h, rng),
                     "in_sample": {key(gg): {"rho": round(rho_within(dk, key(gg), ["bw_id"]), 4),
                                             "auc900": round(auc900(dk, key(gg)), 4)} for gg in GRID}}
    # Lakes scored with the settings chosen on rivers (the settings are shared): the condition on lakes.
    hr = held["river"]
    pick = {f["year"]: f["chosen"] for f in res["river"]["folds"]}
    dl = d[d.kind == "lake"].copy()
    dl["cand"] = [r[pick[y]] if y in pick else np.nan for y, (_, r) in zip(dl["year"], dl.iterrows(), strict=True)]
    dl["cur"] = dl[key(CURRENT)]
    missing_years = sorted(set(dl["year"]) - set(pick))
    dl = dl.dropna(subset=["cand"])
    res["lake_with_river_choice"] = {"years_without_river_fold": missing_years, **paired(dl, rng)}
    res["all_with_river_choice"] = paired(pd.concat([hr, dl]), rng)
    res["full_data_river_choice_on_lakes"] = res["lake"]["in_sample"][res["river"]["full_data_choice"]]
    res["current_in_sample"] = {k: res[k]["in_sample"][key(CURRENT)] for k in ("river", "lake")}
    # Conditions 1-3 of the statement (condition 4, the face check, is prep's and check's output).
    hv, lk = res["river"]["held_out"], res["lake_with_river_choice"]
    res["conditions"] = {
        "1_river_rho": bool(hv["rho_change"] > 0 and hv["rho_ci"][0] > 0),
        "2_river_auc": bool(hv["auc_change"] >= -0.005 and hv["auc_ci"][1] > 0),
        "3_lake_rho": bool(lk["rho_change"] >= -0.02 and lk["rho_ci"][1] > 0),
        "would_deploy": res["river"]["full_data_choice"], "current": key(CURRENT)}
    with open(out_path, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    brief = {k: v for k, v in res.items() if k not in ("river", "lake")}
    for k in ("river", "lake"):
        brief[k] = {kk: vv for kk, vv in res[k].items() if kk != "in_sample"}
    print(json.dumps(brief, indent=1, default=str))


def check(rows_path: str, validation_rows: str) -> None:
    """The current settings' column against validate_ecoli.py's risk_model, row by row (same run root)."""
    a = pd.read_parquet(rows_path)
    b = pd.read_parquet(validation_rows)[["bw_id", "sample_time", "risk_model", "upstream"]]
    m = a.merge(b, on=["bw_id", "sample_time"], how="outer", suffixes=("", "_v"), indicator=True)
    both = m[m["_merge"] == "both"]
    up = both[both.upstream > 0]
    diff = (up[key(CURRENT)] - up["risk_model"]).abs()
    nan_mismatch = int((up[key(CURRENT)].isna() != up["risk_model"].isna()).sum())
    print(json.dumps({"rows_here": len(a), "rows_validate": len(b), "unmatched": int((m["_merge"] != "both").sum()),
                      "upstream_differs": int((both["upstream"] != both["upstream_v"]).sum()),
                      "max_abs_diff": float(diff.max()), "nan_mismatch": nan_mismatch}))


if __name__ == "__main__":
    {"prep": prep, "score": score, "check": check}[sys.argv[1]](*sys.argv[2:])
