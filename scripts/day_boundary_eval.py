"""The day-boundary test, as stated in docs/DAY-BOUNDARY-TEST-2026-10.md: two hold-out spill models, one
trained on UTC days (the old arm) and one on UK local days (the new arm), scored on the same 2025 rows
against the same local-day labels, fed the same local-day features. Off CI, by hand, after both arms'
`train.py 2025 --refit-all` has run in its own DIPCAST_ROOT, with this commit's code:

    DIPCAST_ROOT=<new root> DIPCAST_CACHE=<frozen cache> PYTHONPATH=src \\
        python scripts/day_boundary_eval.py --old <old root> --new <new root> --out <dir>

N1: United Utilities 2025, ERA5-Land rain, train.py's test rows. N2: the nine English companies' 2025
overflows in cells with archived lead forecasts, leads 0-4, as verify_leads.py builds them. Paired
bootstrap of Brier(new) - Brier(old) over ISO weeks of the target day (and over days, reported). Writes
<out>/scores.csv, <out>/companies.csv, <out>/moves.csv and <out>/checks.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.features import ALL_FEATURES, LOCAL_TZ, build_site_days, daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel
from dipcast.model.training import NINE, RAIN_DIRS, ece, load_events, load_rain, site_years
from dipcast.model.verify import scores

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train  # noqa: E402  (train.py's covariate rule and filters, so N1's rows are its test rows)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("day_boundary_eval")

YEAR = 2025
LEADS = [0, 1, 2, 3, 4]
N_BOOT = 2000
SEED = 1
MARGIN = 0.01   # the stated non-inferiority margin: 1% of the old model's Brier
KEY = ["cell_lat", "cell_lon", "day"]


# ---------------------------------------------------------------- rows
def uu_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    """train.py main()'s YEAR test frame, on local days: United Utilities overflows with a YEAR-1 return
    position, the same-year EDM filter, the day's rain known. Rain from the cells those overflows sit in,
    every archive file train.py's load_rain_archive would read for them, up to the end of YEAR."""
    ev = pd.read_parquet(config.PROCESSED / "edm_events.parquet")
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    cov = train.site_year_covariates(ar)
    sites = cov[cov.year == YEAR].drop(columns="year")
    cells = set(zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True))
    files = [f for f in sorted((config.CACHE / "rain").glob("archive_*.parquet"))
             if (float(f.stem.split("_")[1]), float(f.stem.split("_")[2])) in cells]
    log.info("N1: %d overflows in %d cells, %d rain files", len(sites), len(cells), len(files))
    end = pd.Timestamp(f"{YEAR + 1}-01-02", tz="UTC")
    rain = pd.concat((r[r["time"] < end] for r in (pd.read_parquet(f) for f in files)), ignore_index=True)
    daily = daily_rain_features(rain)
    utc_rain = utc_daily_rain(rain)
    del rain
    days = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31", freq="D", tz=LOCAL_TZ)
    labels = spill_days(ev)
    df = build_site_days(sites.assign(company=train.COMPANY), daily, days, labels)
    qual = ar[ar.company == train.COMPANY][["site_id", "year", "edm_operational_pct"]].rename(
        columns={"edm_operational_pct": "edm_pct_same_year"}).drop_duplicates(subset=["site_id", "year"])
    qual = qual[qual["year"].astype(int) == YEAR].drop(columns="year")
    df = df.merge(qual, on="site_id", how="left")
    df = df[df["rain_d"].notna()]
    df = df[df["edm_pct_same_year"].isna() | (df["edm_pct_same_year"] >= train.MIN_EDM_PCT)]
    df = df.astype({f: np.float32 for f in ALL_FEATURES}).reset_index(drop=True)
    moves = how_much_moves(ev[ev["site_id"].isin(sites["site_id"])], daily, utc_rain, days)
    return df, moves


def utc_daily_rain(rain: pd.DataFrame) -> pd.DataFrame:
    """rain_d on UTC days, as daily_rain_features cut them before this test: only to count what moves."""
    r = rain.assign(day=rain["time"].dt.floor("D"), ok=np.isfinite(rain["precip_mm"]))
    r = r[~r.duplicated(["cell_lat", "cell_lon", "time"], keep="last")]
    d = r.groupby(KEY).agg(rain_d=("precip_mm", "sum"), n=("ok", "sum")).reset_index()
    d.loc[d["n"] < 20, "rain_d"] = np.nan
    return d


def utc_spill_days(ev: pd.DataFrame) -> pd.DataFrame:
    """features.spill_days as it was, on UTC days: only to count what moves."""
    ev = ev.dropna(subset=["event_start"])
    d0 = ev["event_start"].dt.floor("D")
    d1 = ev["event_end"].fillna(ev["event_start"]).dt.floor("D")
    n = ((d1 - d0).dt.days.clip(lower=0, upper=60) + 1).to_numpy()
    base = np.repeat(d0.dt.tz_convert(None).to_numpy().astype("datetime64[D]"), n)
    offs = np.concatenate([np.arange(k) for k in n]) if len(n) else np.array([], dtype=int)
    return pd.DataFrame({"site_id": np.repeat(ev["site_id"].to_numpy(), n),
                         "date": base + offs.astype("timedelta64[D]")}).drop_duplicates()


def how_much_moves(ev: pd.DataFrame, daily: pd.DataFrame, utc_rain: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """The share of YEAR's spill-day labels and of cell rain_d values that differ between UTC and local days,
    on the same overflow (or cell) and date, in summer time and in winter apart."""
    bst = {d.date(): d.utcoffset() != pd.Timedelta(0) for d in days}
    loc = spill_days(ev)
    loc = pd.DataFrame({"site_id": loc["site_id"], "date": loc["day"].dt.tz_localize(None).dt.date})
    utc = utc_spill_days(ev)
    utc["date"] = pd.to_datetime(utc["date"]).dt.date
    lab = loc.assign(local=1).merge(utc.assign(utc=1), on=["site_id", "date"], how="outer")
    lab = lab[lab["date"].isin(list(bst))]
    lab["bst"] = lab["date"].map(bst)
    lab["differs"] = lab["local"].isna() | lab["utc"].isna()
    rl = daily[["cell_lat", "cell_lon", "day", "rain_d"]].assign(date=daily["day"].dt.tz_localize(None).dt.date)
    ru = utc_rain.assign(date=utc_rain["day"].dt.tz_convert(None).dt.date)
    r = rl.drop(columns="day").merge(ru.drop(columns=["day", "n"]), on=["cell_lat", "cell_lon", "date"],
                                     suffixes=("_local", "_utc"))
    r = r[r["date"].isin(list(bst)) & r["rain_d_local"].notna() & r["rain_d_utc"].notna()]
    r["bst"] = r["date"].map(bst)
    r["differs"] = (r["rain_d_local"] - r["rain_d_utc"]).abs() > 1e-6
    rows = []
    for what, t in (("spill-day labels", lab), ("cell rain_d", r)):
        for season, m in (("summer time", t["bst"]), ("winter", ~t["bst"])):
            rows.append({"what": what, "season": season, "rows": int(m.sum()), "differ": int(t.loc[m, "differs"].sum()),
                         "share": float(t.loc[m, "differs"].mean()) if m.any() else np.nan})
    return pd.DataFrame(rows)


def nine_rows() -> tuple[pd.DataFrame, dict[int, pd.DataFrame], pd.Series]:
    """verify_leads.py's YEAR base rows and lead features, every company kept, on local days."""
    ev = load_events(NINE)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    labels = spill_days(ev)
    labels = labels[labels.day.dt.year == YEAR]
    files = sorted(f for d in RAIN_DIRS for f in (config.CACHE / d).glob(f"leads_*_{YEAR}.parquet"))
    leads = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    cells = set(map(tuple, leads[["cell_lat", "cell_lon"]].drop_duplicates().to_numpy()))
    era = load_rain(cells, tags=(str(YEAR - 1), str(YEAR)), start=f"{YEAR - 1}-12-01")
    daily_era = daily_rain_features(era)
    del era
    daily_lead = {k: daily_rain_features(leads[leads.lead == k].drop(columns="lead")) for k in LEADS}
    del leads
    sites, _ = site_years(ar, ev, NINE, YEAR)
    sites = sites[[c in cells for c in zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True)]]
    log.info("N2: %d overflows in %d lead cells: %s", len(sites), len(cells), sites["company"].value_counts().to_dict())
    days = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31", freq="D", tz=LOCAL_TZ)
    base = build_site_days(sites, daily_era, days, labels)
    base = base[base["rain_d"].notna()].reset_index(drop=True)
    company = base["site_id"].map(dict(zip(sites["site_id"], sites["company"], strict=True)))
    return base, daily_lead, company


def with_lead(base: pd.DataFrame, daily_lead: dict[int, pd.DataFrame], k: int) -> pd.DataFrame:
    """verify_leads.with_lead: the target day's rain and intensities and the two days before from the
    forecast at leads k, k-1, k-2 (floored at 0); the longer windows stay ERA5-Land."""
    same = ["rain_d", "max1h_d", "max3h_d", "max6h_d"]
    df = base.drop(columns=same).merge(daily_lead[k][KEY + same], on=KEY, how="left")
    for shift, col in ((1, "rain_d1"), (2, "rain_d2")):
        src = daily_lead[max(k - shift, 0)][KEY + ["rain_d"]].copy()
        src["day"] = src["day"] + pd.DateOffset(days=shift)
        df = df.drop(columns=[col]).merge(src.rename(columns={"rain_d": col}), on=KEY, how="left")
    df["rain_3d"] = df["rain_d"].fillna(0) + df["rain_d1"].fillna(0) + df["rain_d2"].fillna(0)
    return df


# ---------------------------------------------------------------- scoring
def predict(model: SpillModel, df: pd.DataFrame, fill: bool) -> np.ndarray:
    """`fill`: missing features as 0, as verify_leads.py and the forecast give them; train.py does not."""
    x = df.astype({f: np.float32 for f in ALL_FEATURES})
    return model.predict(x.fillna({f: 0.0 for f in ALL_FEATURES}) if fill else x)


def clusters(day: pd.Series) -> dict[str, np.ndarray]:
    iso = day.dt.isocalendar()
    return {"week": pd.factorize(iso["year"].astype(int) * 100 + iso["week"].astype(int), sort=True)[0],
            "day": pd.factorize(day.dt.strftime("%Y-%m-%d"), sort=True)[0]}


def boot(y: np.ndarray, pa: np.ndarray, pb: np.ndarray, cl: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    """95% interval of Brier(b) - Brier(a), resampling whole clusters with replacement."""
    k = cl.max() + 1
    n = np.bincount(cl, minlength=k).astype(float)
    sa = np.bincount(cl, weights=(pa - y) ** 2, minlength=k)
    sb = np.bincount(cl, weights=(pb - y) ** 2, minlength=k)
    draws = rng.integers(0, k, size=(N_BOOT, k))
    c = np.stack([np.bincount(d, minlength=k) for d in draws]).astype(float)
    diff = (c @ sb - c @ sa) / (c @ n)
    return float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5))


def compare(name: str, y: np.ndarray, pa: np.ndarray, pb: np.ndarray, day: pd.Series) -> dict:
    a, b = scores(y, pa), scores(y, pb)
    cl = clusters(day)
    lo, hi = boot(y, pa, pb, cl["week"], np.random.default_rng(SEED))
    dlo, dhi = boot(y, pa, pb, cl["day"], np.random.default_rng(SEED))
    d = b["brier"] - a["brier"]
    return {"set": name, "rows": len(y), "base_rate": a["base_rate"], "brier_old": a["brier"], "brier_new": b["brier"],
            "delta": d, "delta_rel": d / a["brier"], "week_lo": lo, "week_hi": hi, "day_lo": dlo, "day_hi": dhi,
            "limit": MARGIN * a["brier"], "pass": bool(hi <= MARGIN * a["brier"]),
            "auc_old": a["auc"], "auc_new": b["auc"], "ece_old": ece(y, pa), "ece_new": ece(y, pb),
            "mean_old": float(pa.mean()), "mean_new": float(pb.mean()), "weeks": int(cl["week"].max() + 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", type=Path, required=True, help="the old arm's DIPCAST_ROOT")
    ap.add_argument("--new", type=Path, required=True, help="the new arm's DIPCAST_ROOT")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    proc = {arm: root / "data" / "processed" for arm, root in (("old", args.old), ("new", args.new))}
    hold = {arm: SpillModel.load(p / f"spill_model_holdout_{YEAR}.pkl") for arm, p in proc.items()}
    prod = {arm: SpillModel.load(p / "spill_model.pkl") for arm, p in proc.items()}
    checks: dict = {"models": {f"{arm} {kind}": m.trained_on for kind, ms in (("hold-out", hold), ("production", prod))
                               for arm, m in ms.items()}}
    rows, comp = [], []

    df, moves = uu_rows()
    y = df["y"].to_numpy()
    pa, pb = predict(hold["old"], df, False), predict(hold["new"], df, False)
    rows.append(compare("N1 United Utilities, reanalysis", y, pa, pb, df["day"]))
    # The harness's rows are train.py's own test rows: the new model scores here as it did in train.py.
    own = pd.read_csv(proc["new"] / f"verification_{YEAR}.csv", index_col=0).loc["dipcast (pooled + site offsets)"]
    checks["N1 rows are train.py's"] = {"train_py_brier": float(own["brier"]), "train_py_n": int(own["n"]),
                                        "here_brier": rows[-1]["brier_new"], "here_n": len(y),
                                        "match": bool(abs(own["brier"] - rows[-1]["brier_new"]) < 1e-9 and own["n"] == len(y))}
    qa, qb = predict(prod["old"], df, False), predict(prod["new"], df, False)
    checks["production refits on N1 rows"] = {"mean_old": float(qa.mean()), "mean_new": float(qb.mean()),
                                              "mean_abs_diff": float(np.abs(qb - qa).mean()),
                                              "p99_abs_diff": float(np.quantile(np.abs(qb - qa), 0.99))}
    moves.to_csv(args.out / "moves.csv", index=False)
    del df

    base, daily_lead, company = nine_rows()
    for k in LEADS:
        dfk = with_lead(base, daily_lead, k)
        ok = dfk["rain_d"].notna().to_numpy()
        dfk = dfk[ok].reset_index(drop=True)
        yk = dfk["y"].to_numpy()
        pa, pb = predict(hold["old"], dfk, True), predict(hold["new"], dfk, True)
        rows.append({**compare(f"N2 nine companies, lead {k}", yk, pa, pb, dfk["day"]), "lead": k})
        if k == 0:
            ck = company.to_numpy()[ok]
            for co in sorted(set(ck)):
                m = ck == co
                comp.append({"company": co, "rows": int(m.sum()), "base_rate": float(yk[m].mean()),
                             "brier_old": float(((pa[m] - yk[m]) ** 2).mean()),
                             "brier_new": float(((pb[m] - yk[m]) ** 2).mean())})
        log.info("lead %d done", k)

    res = pd.DataFrame(rows)
    res.to_csv(args.out / "scores.csv", index=False)
    co = pd.DataFrame(comp)
    co["delta"] = co["brier_new"] - co["brier_old"]
    co.to_csv(args.out / "companies.csv", index=False)
    checks["N1"] = bool(res.iloc[0]["pass"])
    checks["N2"] = {int(r.lead): bool(r["pass"]) for _, r in res.iloc[1:].iterrows()}
    checks["verdict"] = "PASS" if checks["N1"] and all(checks["N2"].values()) else "FAIL"
    (args.out / "checks.json").write_text(json.dumps(checks, indent=1))
    pd.set_option("display.width", 220)
    print(res.drop(columns=["auc_old", "auc_new"]).round(6).to_string(index=False))
    print(co.round(6).to_string(index=False))
    print(moves.to_string(index=False))
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
