"""docs/SOIL-MOISTURE-WALES-CHECK-2026-11.md: the English-fitted E. coli estimate with and without soil moisture, on
W10's Welsh river samples. Nothing is fitted on Welsh data.

    wales.py fetch <soil dir> <wqa dir> [--dry-run]
    wales.py run <soil dir> <wqa dir> <wales_annual.parquet> <welsh rain cache dir> <trace pickle> <out.json>

fetch: Previous Runs lead 0, models=ecmwf_ifs, soil_moisture_9_to_27cm at the 0.1-degree cell of each station that
    passes W10's rules 1 to 3, for each calendar quarter holding a sample, up to 4 cells a request. Saved as
    wales_<cell>_<year>Q<q>.parquet. Weights logged to calls.jsonl, as fetch.py logs them.
run: the English rows and fits of leads.py at lead 0 (reference: today's inputs; candidate: plus sm at 00:00 UTC of the
    sample day), then W10's samples, trace, rain and exposure (check_ecoli_wales.py's own functions), and both
    estimates on them. Welsh rain is read from <welsh rain cache dir>'s rain and rain_w10 folders; English rain from
    DIPCAST_CACHE. The trace is written to (or read from) <trace pickle>.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import check_ecoli_wales as w
import numpy as np
import pandas as pd
from diagnostics import rows_q1
from fetch import PREVIOUS_RUNS, Q1_VAR, Refused, fetch
from leads import CAND, soil_at_issue

from dipcast import config
from dipcast.ingest.rainfall import cell_key, grid_cell
from dipcast.model import ecoli
from dipcast.model.ecoli import FEATURES, THRESHOLD, features, fit

MODEL = {"models": "ecmwf_ifs"}
BATCH = 4


def screened(wqa: Path) -> pd.DataFrame:
    raw = w.read_wqa(sorted(wqa.glob("*_Water_Quality_Archive.zip")))
    s, _ = w.screen(raw)
    cl, cn = grid_cell(s["lat"].to_numpy(), s["lon"].to_numpy())
    s["cell_lat"], s["cell_lon"] = np.round(cl, 3), np.round(cn, 3)
    return s


def utc_issue(day: pd.Series) -> pd.Series:
    """00:00 UTC of the sample's local calendar day."""
    return pd.to_datetime(day.dt.strftime("%Y-%m-%d")).dt.tz_localize("UTC")


def stage_fetch(soil: Path, wqa: Path, dry: bool) -> None:
    s = screened(wqa)
    s["year"], s["q"] = s["day"].dt.year, s["day"].dt.quarter
    todo = s[["cell_lat", "cell_lon", "year", "q"]].drop_duplicates().sort_values(["year", "q", "cell_lat", "cell_lon"])
    todo = todo[[not (soil / f"wales_{cell_key(a, b)}_{y}Q{q}.parquet").exists()
                 for a, b, y, q in todo.itertuples(index=False)]]
    print(f"wales: {s.station_number.nunique()} stations, {len(s[['cell_lat', 'cell_lon']].drop_duplicates())} cells, "
          f"{len(todo)} cell-quarters to fetch, weight about {len(todo)}")
    if dry:
        return
    failed = []
    for (y, q), g in todo.groupby(["year", "q"]):
        start = pd.Timestamp(year=y, month=3 * q - 2, day=1)
        end = start + pd.offsets.QuarterEnd(0)
        cells = list(zip(g["cell_lat"], g["cell_lon"], strict=True))
        for i in range(0, len(cells), BATCH):
            chunk = cells[i:i + BATCH]
            try:
                frames = fetch(PREVIOUS_RUNS, Q1_VAR, MODEL, chunk, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
                               soil, "wales")
            except Refused as e:
                print("refused:", e, flush=True)
                failed += [(c, y, q) for c in chunk]
                continue
            for (a, b), f in zip(chunk, frames, strict=True):
                f.to_parquet(soil / f"wales_{cell_key(a, b)}_{y}Q{q}.parquet", index=False)
        print(f"wales {y}Q{q}: {len(cells)} cells", flush=True)
    print(f"wales: {len(failed)} cell-quarters failed", failed)


def soil_wales(df: pd.DataFrame, soil: Path) -> np.ndarray:
    t = utc_issue(df["day"])
    out = np.full(len(df), np.nan)
    cache: dict = {}
    for i, (a, b, ti) in enumerate(zip(df["cell_lat"], df["cell_lon"], t, strict=True)):
        k = (a, b, ti.year, ti.quarter)
        if k not in cache:
            f = soil / f"wales_{cell_key(a, b)}_{ti.year}Q{ti.quarter}.parquet"
            cache[k] = pd.read_parquet(f).set_index("time")["sm"] if f.exists() else pd.Series(dtype=float)
        v = cache[k].get(ti, np.nan)
        out[i] = float(v) if v is not None else np.nan
    return out


def compare(df: pd.DataFrame, n_boot: int) -> dict:
    """Both estimates on df (one row per sample), with the candidate-minus-reference intervals from W10's
    sampling-day bootstrap."""
    df = df.reset_index(drop=True)
    known = df[df["y"].notna()].reset_index(drop=True)
    y = known["y"].to_numpy(float)
    dk, da = w.day_draws(known["day"].to_numpy(), n_boot), w.day_draws(df["day"].to_numpy(), n_boot)
    lg = df["log_ecoli"].to_numpy(float)

    def brier(p, i=slice(None)):
        return float(np.mean((p[i] - y[i]) ** 2))

    def within(d, col):
        return w._rho(w._within(d, col), w._within(d, "log_ecoli"))

    out = {"samples": len(df), "samples_exceedance_known": len(known), "exceedances": int(y.sum()),
           "rate": float(y.mean()), "sampling_days": int(df["day"].nunique()), "stations": int(df["station_number"].nunique())}
    for k in ("reference", "candidate"):
        p, pa = known[k].to_numpy(float), df[k].to_numpy(float)
        out[k] = {"mean": float(p.mean()), "brier": brier(p), "auc": w._auc(y, p), "spearman": w._rho(pa, lg),
                  "spearman_within_station": within(df, k)}
    pr, pc = known["reference"].to_numpy(float), known["candidate"].to_numpy(float)
    ar, ac = df["reference"].to_numpy(float), df["candidate"].to_numpy(float)
    out["difference"] = {
        "brier": brier(pc) - brier(pr), "brier_ci": w._ci([brier(pc, i) - brier(pr, i) for i in dk]),
        "auc": w._auc(y, pc) - w._auc(y, pr), "auc_ci": w._ci([w._auc(y[i], pc[i]) - w._auc(y[i], pr[i]) for i in dk]),
        "spearman": w._rho(ac, lg) - w._rho(ar, lg),
        "spearman_ci": w._ci([w._rho(ac[i], lg[i]) - w._rho(ar[i], lg[i]) for i in da]),
        "spearman_within_station": within(df, "candidate") - within(df, "reference"),
        "spearman_within_station_ci": w._ci([within(df.iloc[i], "candidate") - within(df.iloc[i], "reference") for i in da])}
    return out


def stage_run(soil: Path, wqa: Path, wales_annual: Path, rain_dir: Path, trace: Path, out_path: Path) -> None:
    from dipcast.model.spill_model import SpillModel
    from dipcast.network.rivers import RiverNetwork

    # ---- the English fits (leads.py, lead 0)
    rows, fc = rows_q1()
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    X0 = features(fc[0][0], fc[0][1], rows["risk_lead0"], rows.lake, rows.sample_time)
    X0["sm"] = soil_at_issue(rows, soil, 0)
    ok = np.isfinite(X0["sm"].to_numpy())
    ref, cand = fit(X0, y, FEATURES), fit(X0[ok], y[ok], CAND)
    lo, hi = float(X0["sm"][ok].min()), float(X0["sm"][ok].max())
    em = ecoli.EcoliModel.from_json()
    face = {"england_rows": len(rows), "england_rows_without_sm": int((~ok).sum()),
            "reference_vs_ecoli_model_json_max_coef_diff": max(abs(ref.coef[c] - em.coef[c]) for c in FEATURES),
            "reference_vs_ecoli_model_json_intercept_diff": abs(ref.intercept - em.intercept)}
    assert face["reference_vs_ecoli_model_json_max_coef_diff"] < 1e-9 and face["reference_vs_ecoli_model_json_intercept_diff"] < 1e-9, face

    # ---- W10's samples, trace, rain and exposure, with its own functions
    w.W10_RAIN = rain_dir / "rain_w10"
    shared = rain_dir / "rain"

    def load_rain(cells: pd.DataFrame) -> pd.DataFrame:   # check_ecoli_wales.load_rain, reading the Welsh rain cache
        frames = []
        for c in cells.itertuples():
            key = cell_key(c.cell_lat, c.cell_lon)
            for yy in range(c.start.year, c.end.year + 1):
                p = shared / f"archive_{key}_{yy}.parquet"
                if p.exists():
                    frames.append(pd.read_parquet(p))
            frames += [pd.read_parquet(p) for p in sorted(w.W10_RAIN.glob(f"archive_{key}_*.parquet"))]
        r = pd.concat(frames, ignore_index=True)
        r["cell_lat"], r["cell_lon"] = r["cell_lat"].round(3), r["cell_lon"].round(3)
        r = r[np.isfinite(r["precip_mm"].astype(float))]
        return r.drop_duplicates(["cell_lat", "cell_lon", "time"], keep="first").reset_index(drop=True)

    samples = screened(wqa)
    stations = samples.groupby("station_number", as_index=False).agg(
        station_name=("station_name", "first"), lat=("lat", "first"), lon=("lon", "first"))
    wa = pd.read_parquet(wales_annual)
    if trace.exists():
        st, ups, ov_info = pd.read_pickle(trace)
    else:
        net = RiverNetwork.load()
        ov, ov_info = w.welsh_overflows(net, wa)
        st, ups = w.trace_stations(net, ov, stations)
        del net
        pd.to_pickle((st, ups, ov_info), trace)
    samples = samples.merge(st, on="station_number", how="left")
    off = int((~samples["on_network"]).sum())
    samples = samples[samples["on_network"]].reset_index(drop=True)
    need = w.rain_needs(samples, ups)
    rain = load_rain(need)
    gaps = w.rain_gaps(need, rain)
    models = {"gate_a": SpillModel.load(config.PROCESSED / "spill_model_holdout_2025.pkl"),
              "production": SpillModel.load(config.PROCESSED / "spill_model.pkl")}
    rain_model, clim, _ = w.england_baselines()
    df, miss = w.predictors(samples, ups, wa, rain, models, rain_model, clim)
    df = df.dropna(subset=["rain_48h", "rain_24h", "exposure", "ecoli_estimate"]).reset_index(drop=True)

    # ---- both estimates
    X = features(df["rain_48h"], df["rain_24h"], df["exposure"], np.zeros(len(df)), df["day"])
    df["reference"] = ref.predict(X)
    sm = soil_wales(df, soil)
    Xc = X.copy()
    Xc["sm"] = np.clip(sm, lo, hi)
    df["candidate"] = np.where(np.isfinite(sm), cand.predict(Xc), df["reference"])
    face["welsh_reference_vs_check_estimate_max_diff"] = float(np.max(np.abs(df["reference"] - df["ecoli_estimate"])))
    assert face["welsh_reference_vs_check_estimate_max_diff"] < 1e-9, face
    head = df[df["river"]]
    res = {"face_check": face, "candidate_coef_per_sd": cand.coef, "england_sm_range": [lo, hi],
           "rows": {"off_network": off, **miss, "scored_all_inland": len(df), "scored_headline": len(head),
                    "rain_gaps": len(gaps), "welsh_sm_missing": int(np.isnan(sm).sum()),
                    "welsh_sm_held_to_range": int(((sm < lo) | (sm > hi)).sum())},
           "welsh_sm": {"mean": float(np.nanmean(sm)), "min": float(np.nanmin(sm)), "max": float(np.nanmax(sm))},
           "overflows": ov_info,
           "headline": compare(head, w.N_BOOT), "all_inland": compare(df, w.N_BOOT)}
    d = res["headline"]["difference"]
    res["clearly_worse"] = bool(d["brier_ci"][0] > 0 or d["spearman_within_station_ci"][1] < 0)
    res["per_station"] = [{"station": sid, "name": nm, "n": len(g), "exceedances": int(np.nansum(g["y"])),
                           "sm_mean": float(np.nanmean(sm[g.index])),
                           "mean_reference": float(g["reference"].mean()), "mean_candidate": float(g["candidate"].mean()),
                           "rho_reference": w._rho(g["reference"], g["log_ecoli"]),
                           "rho_candidate": w._rho(g["candidate"], g["log_ecoli"])}
                          for (sid, nm), g in head.groupby(["station_number", "station_name"]) if len(g) >= w.MIN_STATION_N]
    res = w.clean(res)
    out_path.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("face_check", "rows", "welsh_sm", "clearly_worse")}, indent=1))
    print(json.dumps(res["headline"], indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "fetch":
        stage_fetch(Path(a[1]), Path(a[2]), "--dry-run" in a)
    else:
        stage_run(*(Path(x) for x in a[1:7]))
