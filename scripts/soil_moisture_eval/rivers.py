"""docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md: soil moisture on rivers only, judged on Welsh and Wessex river samples.

    rivers.py fetch <wessex dir>
    rivers.py prepare <soil dir> <wessex dir> <wales_annual.parquet> <main cache dir> <budget>
    rivers.py run <soil dir> <wessex dir> <wqa dir> <wales_annual.parquet> <main cache dir> <out dir>

fetch: Wessex Water's E. coli rows (CC BY 4.0), every field, to <wessex dir>/ecoli.parquet, with provenance.json.
prepare: places the Wessex points (check_ecoli_wales's rule 4 and trace), reports their rain gaps, fetches `sm`
    (Previous Runs lead 0, models=ecmwf_ifs) for each cell-quarter holding a placed sample, then ERA5-Land rain for the
    gaps into <main cache dir>/rain_rivers, stopping before <budget> weighted calls in all. No Result is read against
    an input; nothing is scored.
run: the English fits of leads.py at lead 0 (reference and candidate), the English rows by lead under the rule
    (reported), then the Welsh frame (wales.py's) and the Wessex frame (W10's predictors, production exposure), both
    estimates on each, and the stated conditions.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import check_ecoli_wales as w
import httpx
import numpy as np
import pandas as pd
import train_ecoli as te
from diagnostics import rows_q1
from fetch import PREVIOUS_RUNS, Q1_VAR, Refused, fetch
from leads import CAND, soil_at_issue
from wales import soil_wales

from dipcast import config
from dipcast.ingest.rainfall import call_weight, cell_key, grid_cell
from dipcast.model import ecoli
from dipcast.model.ecoli import FEATURES, THRESHOLD, features, fit

WESSEX = ("https://services.arcgis.com/3SZ6e0uCvPROr4mS/arcgis/rest/services/"
          "Wessex_Water_Environmental_Water_Quality_view/FeatureServer/0/query")
CREDIT = ("Wessex Water Environmental Water Quality (c) 2026 by Wessex Water, licensed under CC BY 4.0 "
          "(ArcGIS item 4659ab28caa640c58e725b41ecbba79f)")
YEARS = range(2020, 2026)
MONTHS = range(5, 10)
RAIN_DIRS = ("rain", "rain_nine", "rain_multi", "rain_rivers", "rain_w10")
MARGIN_REL = 0.01
N_BOOT, SEED = 2000, 0


# ------------------------------------------------------------------ Wessex rows
def stage_fetch(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rows, off = [], 0
    while True:
        d = httpx.get(WESSEX, params={"f": "json", "where": "Determinand='E. coli'", "outFields": "*",
                                      "returnGeometry": "false", "resultOffset": off, "resultRecordCount": 2000,
                                      "orderByFields": "OBJECTID"}, timeout=180).json()
        f = d["features"]
        rows += [x["attributes"] for x in f]
        off += len(f)
        if not f or not d.get("exceededTransferLimit"):
            break
    pd.DataFrame(rows).to_parquet(out / "ecoli.parquet", index=False)
    (out / "provenance.json").write_text(json.dumps({"query": WESSEX, "where": "Determinand='E. coli'", "rows": len(rows),
                                                     "fetched": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "credit": CREDIT}))
    print(f"wessex: {len(rows)} E. coli rows -> {out / 'ecoli.parquet'}")


def wessex_samples(wessex: Path) -> tuple[pd.DataFrame, dict]:
    """W10's sample frame from Wessex's rows: May to September 2020-25, one station per position, W10's sign rules."""
    d = pd.read_parquet(wessex / "ecoli.parquet")
    why = {"rows": len(d)}
    d["time"] = pd.to_datetime(d["SampleDate"], errors="coerce").dt.tz_localize(w.TZ, ambiguous="NaT", nonexistent="NaT")
    d["value"] = pd.to_numeric(d["Result"], errors="coerce")
    keep = d["time"].notna() & d["value"].notna()
    why["no_time_or_value"] = int((~keep).sum())
    d = d[keep]
    inwin = d["time"].dt.year.isin(list(YEARS)) & d["time"].dt.month.isin(list(MONTHS))
    why["outside_may_sep_2020_25"] = int((~inwin).sum())
    d = d[inwin].copy()
    d["sign"] = d["Operator"].fillna("").str.strip().replace("", "---")
    d["y"] = [w.exceeds(s, v) for s, v in zip(d["sign"], d["value"], strict=True)]
    d["log_ecoli"] = [w.log_count(s, v) for s, v in zip(d["sign"], d["value"], strict=True)]
    d["day"] = d["time"].dt.floor("D")
    d["lat"], d["lon"] = d["Latitude"].astype(float), d["Longitude"].astype(float)
    d["station_number"] = [f"wsx {a:.5f},{b:.5f}" for a, b in zip(d["lat"], d["lon"], strict=True)]
    d["station_name"] = d["station_number"]
    cl, cn = grid_cell(d["lat"].to_numpy(), d["lon"].to_numpy())
    d["cell_lat"], d["cell_lon"] = np.round(cl, 3), np.round(cn, 3)
    why["kept"] = len(d)
    return d.reset_index(drop=True), why


def load_rain_any(cells: pd.DataFrame, cache: Path) -> pd.DataFrame:
    """Hourly ERA5-Land rain for the cells from every archive file in the caches named in RAIN_DIRS (the first folder
    holding an hour wins), over each cell's needed span."""
    frames = []
    for c in cells.itertuples():
        key = cell_key(c.cell_lat, c.cell_lon)
        for i, d in enumerate(RAIN_DIRS):
            for p in sorted((cache / d).glob(f"archive_{key}_*.parquet")):
                r = pd.read_parquet(p)
                r = r[(r["time"] >= c.start - pd.Timedelta(days=1)) & (r["time"] <= c.end + pd.Timedelta(days=1))]
                frames.append(r.assign(_prio=i))
    if not frames:
        return pd.DataFrame(columns=["cell_lat", "cell_lon", "time", "precip_mm"])
    r = pd.concat(frames, ignore_index=True)
    r["cell_lat"], r["cell_lon"] = r["cell_lat"].round(3), r["cell_lon"].round(3)
    r = r[np.isfinite(r["precip_mm"].astype(float))].sort_values("_prio", kind="mergesort")
    return r.drop_duplicates(["cell_lat", "cell_lon", "time"], keep="first").drop(columns="_prio").reset_index(drop=True)


def place(samples: pd.DataFrame, wa: pd.DataFrame, trace: Path):
    from dipcast.network.rivers import RiverNetwork
    stations = samples.groupby("station_number", as_index=False).agg(
        station_name=("station_name", "first"), lat=("lat", "first"), lon=("lon", "first"))
    if trace.exists():
        st, ups, ov_info = pd.read_pickle(trace)
    else:
        net = RiverNetwork.load()
        ov, ov_info = w.welsh_overflows(net, wa)
        st, ups = w.trace_stations(net, ov, stations)
        del net
        pd.to_pickle((st, ups, ov_info), trace)
    s = samples.merge(st, on="station_number", how="left")
    off = int((~s["on_network"]).sum())
    return s[s["on_network"]].reset_index(drop=True), ups, ov_info, off, st


# ------------------------------------------------------------------ prepare (no score)
def stage_prepare(soil: Path, wessex: Path, wales_annual: Path, cache: Path, budget: float) -> None:
    samples, why = wessex_samples(wessex)
    s, ups, _, off, st = place(samples, pd.read_parquet(wales_annual), wessex / "trace_wessex.pkl")
    print(f"wessex: {why}; off network {off}; placed {len(s)} samples at {s.station_number.nunique()} stations; "
          f"headline (>= 20 km upstream) {int(s['river'].sum())} at {s.loc[s['river'], 'station_number'].nunique()}")
    used = 0.0
    # sm, every placed sample's cell-quarter
    s["year"], s["q"] = s["day"].dt.year, s["day"].dt.quarter
    todo = s[["cell_lat", "cell_lon", "year", "q"]].drop_duplicates()
    todo = todo[[not (soil / f"rivers_{cell_key(a, b)}_{y}Q{q}.parquet").exists() for a, b, y, q in todo.itertuples(index=False)]]
    print(f"sm: {len(todo)} cell-quarters to fetch")
    for (y, q), g in todo.groupby(["year", "q"]):
        start = pd.Timestamp(year=y, month=3 * q - 2, day=1)
        end = start + pd.offsets.QuarterEnd(0)
        cells = list(zip(g["cell_lat"], g["cell_lon"], strict=True))
        for i in range(0, len(cells), 4):
            chunk = cells[i:i + 4]
            wt = call_weight(len(chunk), (end - start).days + 1)
            if used + wt > budget:
                print("sm: budget reached, stopping"); return
            try:
                frames = fetch(PREVIOUS_RUNS, Q1_VAR, {"models": "ecmwf_ifs"}, chunk, start.strftime("%Y-%m-%d"),
                               end.strftime("%Y-%m-%d"), soil, "rivers")
            except Refused as e:
                print("refused:", e); continue
            used += wt
            for (a, b), f in zip(chunk, frames, strict=True):
                f.to_parquet(soil / f"rivers_{cell_key(a, b)}_{y}Q{q}.parquet", index=False)
    print(f"sm: done, {used:.0f} calls")
    # rain gaps
    need = w.rain_needs(s, ups)
    gaps = w.rain_gaps(need, load_rain_any(need, cache))
    est = sum(w.weighted_calls(g.start.tz_localize(None), g.end.tz_localize(None)) for g in gaps.itertuples()) if len(gaps) else 0
    print(f"rain: {len(need)} cell-years needed, {len(gaps)} gaps, about {est} weighted calls; budget left {budget - used:.0f}")
    if len(gaps):
        w.W10_RAIN = cache / "rain_rivers"
        res = w.fetch_gaps(gaps, budget=int(budget - used))
        print("rain fetch:", res)
        gaps = w.rain_gaps(need, load_rain_any(need, cache))
        print(f"rain: {len(gaps)} gaps left")


# ------------------------------------------------------------------ run
def boot(region: np.ndarray, day: np.ndarray, rng_seed: int = SEED) -> list[np.ndarray]:
    """Row indices of each draw: (region, sampling day) clusters drawn with replacement, all rows of a cluster."""
    key = pd.Series(region).astype(str) + "|" + pd.Series(day).astype(str)
    uniq, inv = np.unique(key.to_numpy(), return_inverse=True)
    by = [np.flatnonzero(inv == i) for i in range(len(uniq))]
    rng = np.random.default_rng(rng_seed)
    return [np.concatenate([by[i] for i in rng.integers(0, len(uniq), len(uniq))]) for _ in range(N_BOOT)]


def log_loss(y, p) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def scores_pair(df: pd.DataFrame) -> dict:
    """Both estimates on df: Brier (with the gain's interval), AUC and log loss on known exceedance; rho pooled and
    within station on all rows."""
    df = df.reset_index(drop=True)
    k = df[df["y"].notna()].reset_index(drop=True)
    y = k["y"].to_numpy(float)
    dk, da = boot(k["region"].to_numpy(), k["day"].to_numpy()), boot(df["region"].to_numpy(), df["day"].to_numpy())
    pr, pc = k["reference"].to_numpy(float), k["candidate"].to_numpy(float)
    lg, ar, ac = df["log_ecoli"].to_numpy(float), df["reference"].to_numpy(float), df["candidate"].to_numpy(float)

    def b(p, i=slice(None)):
        return float(np.mean((p[i] - y[i]) ** 2))

    def within(d, col):
        return w._rho(w._within(d, col), w._within(d, "log_ecoli"))

    out = {"samples": len(df), "known": len(k), "exceedances": int(y.sum()), "rate": float(y.mean()) if len(y) else None,
           "sampling_days": int(df["day"].nunique()), "stations": int(df["station_number"].nunique())}
    for name, p, pa in (("reference", pr, ar), ("candidate", pc, ac)):
        out[name] = {"mean": float(p.mean()), "brier": b(p), "auc": w._auc(y, p), "log_loss": log_loss(y, p),
                     "spearman": w._rho(pa, lg), "spearman_within_station": within(df, name)}
    out["gain"] = b(pr) - b(pc)
    out["gain_ci"] = w._ci([b(pr, i) - b(pc, i) for i in dk])
    out["brier_rel_change"] = b(pc) / b(pr) - 1
    out["spearman_within_change"] = within(df, "candidate") - within(df, "reference")
    out["spearman_within_change_ci"] = w._ci([within(df.iloc[i], "candidate") - within(df.iloc[i], "reference") for i in da])
    out["auc_change"] = w._auc(y, pc) - w._auc(y, pr)
    out["log_loss_change"] = log_loss(y, pc) - log_loss(y, pr)
    return out


def english_by_lead(soil: Path) -> dict:
    """Leave one year out by lead, as leads.py, for today's model and the rule (rivers with sm, lakes without)."""
    rows, fc = rows_q1()
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years, lake = rows["sample_time"].dt.year.to_numpy(), rows["lake"].to_numpy()
    XL = {k: features(fc[k][0], fc[k][1], rows[f"risk_lead{k}"], rows.lake, rows.sample_time) for k in te.LEADS}
    sm = {k: soil_at_issue(rows, soil, k) for k in te.LEADS}
    X0 = XL[0].copy()
    X0["sm"] = sm[0]
    out = {}
    for k in te.LEADS:
        pr, pu = np.full(len(y), np.nan), np.full(len(y), np.nan)
        for g in np.unique(years):
            tr, tt = years != g, years == g
            if y[tr].sum() == 0:
                continue
            mr, mc = fit(X0[tr], y[tr], FEATURES), fit(X0[tr], y[tr], CAND)
            lo, hi = float(np.nanmin(sm[0][tr])), float(np.nanmax(sm[0][tr]))
            Xe = XL[k][tt].copy()
            Xe["sm"] = np.clip(sm[k][tt], lo, hi)
            a, c = mr.predict(Xe), mc.predict(Xe)
            pr[tt], pu[tt] = a, np.where(lake[tt] == 1.0, a, np.where(np.isfinite(sm[k][tt]), c, a))
        out[k] = {t: {"reference": float(np.mean((pr[m] - y[m]) ** 2)), "rule": float(np.mean((pu[m] - y[m]) ** 2))}
                  for t, m in (("all", np.ones(len(y), bool)), ("rivers", lake == 0.0), ("lakes", lake == 1.0))}
    return out


def stage_run(soil: Path, wessex: Path, wqa: Path, wales_annual: Path, cache: Path, out: Path) -> None:
    from dipcast.model.spill_model import SpillModel
    # ---- the English fits (leads.py, lead 0)
    rows, fc = rows_q1()
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    X0 = features(fc[0][0], fc[0][1], rows["risk_lead0"], rows.lake, rows.sample_time)
    X0["sm"] = soil_at_issue(rows, soil, 0)
    ok = np.isfinite(X0["sm"].to_numpy())
    ref, cand = fit(X0, y, FEATURES), fit(X0[ok], y[ok], CAND)
    lo, hi = float(X0["sm"][ok].min()), float(X0["sm"][ok].max())
    em = ecoli.EcoliModel.from_json()
    face = {"reference_vs_ecoli_model_json": max([abs(ref.coef[c] - em.coef[c]) for c in FEATURES] + [abs(ref.intercept - em.intercept)])}
    assert face["reference_vs_ecoli_model_json"] < 1e-9, face
    res: dict = {"credit": CREDIT, "england_sm_range": [lo, hi], "candidate_coef_per_sd": cand.coef,
                 "english_by_lead": english_by_lead(soil)}
    wa = pd.read_parquet(wales_annual)
    models = {"gate_a": SpillModel.load(config.PROCESSED / "spill_model_holdout_2025.pkl"),
              "production": SpillModel.load(config.PROCESSED / "spill_model.pkl")}
    rain_model, clim, _ = w.england_baselines()

    def frame(samples, trace, exposure, region, prefix):
        s, ups, ov_info, off, _ = place(samples, wa, trace)
        need = w.rain_needs(s, ups)
        rain = load_rain_any(need, cache)
        gaps = len(w.rain_gaps(need, rain))
        df, miss = w.predictors(s, ups, wa, rain, models, rain_model, clim)
        df["exposure"] = df[f"exposure_{exposure}"]
        est = "ecoli_estimate" if exposure == "gate_a" else "ecoli_estimate_production"
        n0 = len(df)
        df = df.dropna(subset=["rain_48h", "rain_24h", "exposure", est]).reset_index(drop=True)
        X = features(df["rain_48h"], df["rain_24h"], df["exposure"], np.zeros(len(df)), df["day"])
        df["reference"] = ref.predict(X)
        diff = float(np.max(np.abs(df["reference"] - df[est]))) if len(df) else 0.0
        face[f"{region}_reference_vs_check_estimate"] = diff
        assert diff < 1e-9, face
        sm = soil_wales(df.assign(), soil) if prefix == "wales" else soil_rivers(df, soil)
        Xc = X.copy()
        Xc["sm"] = np.clip(sm, lo, hi)
        df["candidate"] = np.where(np.isfinite(sm), cand.predict(Xc), df["reference"])
        df["region"] = region
        info = {"off_network": off, "after_placement": n0, "dropped_missing_input": n0 - len(df), **miss,
                "rain_gaps": gaps, "sm_missing": int(np.isnan(sm).sum()), "sm_held_to_range": int(((sm < lo) | (sm > hi)).sum()),
                "sm_mean": float(np.nanmean(sm)), "overflows": ov_info, "headline_samples": int(df["river"].sum()),
                "all_samples": len(df)}
        return df, info

    wales_s = w.screen(w.read_wqa(sorted(wqa.glob("*_Water_Quality_Archive.zip"))))[0]
    cl, cn = grid_cell(wales_s["lat"].to_numpy(), wales_s["lon"].to_numpy())
    wales_s["cell_lat"], wales_s["cell_lon"] = np.round(cl, 3), np.round(cn, 3)
    dw, iw = frame(wales_s, out / "trace.pkl", "gate_a", "Wales", "wales")
    wsx_s, why = wessex_samples(wessex)
    dx, ix = frame(wsx_s, out / "trace_wessex.pkl", "production", "Wessex", "rivers")
    res["rows"] = {"Wales": iw, "Wessex": {**why, **ix}}
    res["face_check"] = face
    both = pd.concat([dw, dx], ignore_index=True)
    head = both[both["river"]].reset_index(drop=True)
    res["headline"] = {"pooled": scores_pair(head), "Wales": scores_pair(head[head.region == "Wales"]),
                       "Wessex": scores_pair(head[head.region == "Wessex"])}
    res["all_placed"] = {"pooled": scores_pair(both), "Wales": scores_pair(both[both.region == "Wales"]),
                         "Wessex": scores_pair(both[both.region == "Wessex"])}
    H = res["headline"]
    c1 = H["pooled"]["gain"] > 0 and H["pooled"]["gain_ci"][0] > 0
    worse = {r: bool(H[r]["gain_ci"][1] < 0 or H[r]["brier_rel_change"] > MARGIN_REL) for r in ("Wales", "Wessex")}
    res["conditions"] = {"1_pooled_gain": bool(c1), "2_no_region_clearly_worse": not any(worse.values()),
                         "regions_clearly_worse": [r for r, v in worse.items() if v]}
    res["passes"] = bool(c1 and not any(worse.values()))
    res["per_station"] = [{"region": g["region"].iloc[0], "station": sid, "n": len(g), "exceedances": int(np.nansum(g["y"])),
                           "mean_reference": float(g["reference"].mean()), "mean_candidate": float(g["candidate"].mean()),
                           "rho_reference": w._rho(g["reference"], g["log_ecoli"]),
                           "rho_candidate": w._rho(g["candidate"], g["log_ecoli"])}
                          for sid, g in head.groupby("station_number") if len(g) >= w.MIN_STATION_N]
    res = w.clean(res)
    (out / "rivers.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("face_check", "rows", "conditions", "passes")}, indent=1))
    print(json.dumps(res["headline"], indent=1))


def soil_rivers(df: pd.DataFrame, soil: Path) -> np.ndarray:
    """sm at 00:00 UTC of the sample's local day from the rivers_* files (prepare's fetch); NaN if none."""
    t = pd.to_datetime(df["day"].dt.strftime("%Y-%m-%d")).dt.tz_localize("UTC")
    out = np.full(len(df), np.nan)
    cache: dict = {}
    for i, (a, b, ti) in enumerate(zip(df["cell_lat"], df["cell_lon"], t, strict=True)):
        k = (a, b, ti.year, ti.quarter)
        if k not in cache:
            f = soil / f"rivers_{cell_key(a, b)}_{ti.year}Q{ti.quarter}.parquet"
            cache[k] = pd.read_parquet(f).set_index("time")["sm"] if f.exists() else pd.Series(dtype=float)
        v = cache[k].get(ti, np.nan)
        out[i] = float(v) if v is not None else np.nan
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "fetch":
        stage_fetch(Path(a[1]))
    elif a[0] == "prepare":
        stage_prepare(Path(a[1]), Path(a[2]), Path(a[3]), Path(a[4]), float(a[5]))
    else:
        stage_run(*(Path(x) for x in a[1:7]))
