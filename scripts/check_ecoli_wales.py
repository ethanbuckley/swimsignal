"""E. coli check in Wales (task W10 of docs/WALES-PLAN-2026-10.md). Off CI; publishes nothing.

Does SwimSignal's E. coli estimate, and the overflow exposure index under it, tell which Welsh river
samples exceed 900 E. coli per 100 ml, better than rain alone? Samples: Natural Resources Wales'
Water Quality Archive (NRW_DS124903, Open Government Licence v3; "Contains Natural Resources Wales
information © Natural Resources Wales and Database Right. All rights Reserved. Contains Ordnance
Survey Data. Ordnance Survey Licence number AC0000849444. Crown Copyright and Database Right.").
Writes a summary of scores, with no Dŵr Cymru rows and no sample rows, to
data/processed/wales_ecoli_check.json.

    DIPCAST_ROOT=<main checkout> uv run python scripts/check_ecoli_wales.py \
        --wqa <dir with NRW's *_Water_Quality_Archive.zip files> [--fetch]

`--fetch` asks Open-Meteo's ERA5-Land archive for the rain the cache lacks, one cell per request,
sequentially, stopping at the first refusal and before FETCH_BUDGET weighted calls. New rain goes to
<DIPCAST_CACHE>/rain_w10/, never over the shared cache's files. Without `--fetch` it fetches nothing.

THE TEST
========

Written 10 October 2026, before any sample was matched to a predictor, and committed on its own
before the first run on real data. It is not to be changed after any result is seen; a different
rule would be a new, dated rule beside this one, and the write-up would report both. Before writing
it I had looked at the archive's station names, types, sample counts by year and month, and the
'<' and '>' values, but at no E. coli value against rain, exposure or date.

Samples. Rows with parameter_name "Escherichia coli : Confirmed : MF" (unit: number per 100 ml)
that pass, in order:

1. Sampled on or after 1 January 2023: the first year with a Welsh return the year before (W2's
   table starts at 2022), so each sample gets its overflows' covariates from the year before, as
   train.py and the Gate A hindcast do. The 2011-2013 Carmarthen Bay rows are left out: the overflow
   table, positions and covariates are a decade later than them, most Welsh overflows had no
   monitor then, and their rain alone (about 40 cells, three years) is beyond today's fetch budget.
2. deviating_result is not "Yes" (the lab flagged the sample).
3. A river point, not a discharge: station_type starts "FRESHWATER -" and is not a canal or a land
   drain; sampling_medium is "RIVER / RUNNING SURFACE WATER" or "ANY WATER"; and the name does not
   say it is a discharge (DISCHARGE_NAME), unless it says the point is upstream of one ("U/S").
   So "R.WYE U/S LLYSWEN STW OUTFALL" is kept (river water above the works) and "SSO+BRYNMILL
   STREAM OUTFALL" and "CASWELL BAY PIPE DISCHARGE" are not.
4. On the river network: transport.locate_pin, with the river's name as a hint where the station
   name gives one (RIVER_HINTS), places it in "river" mode on an inland river link no more than
   SNAP_OK_M (250 m) away. Tidal links are left out (plan 5.2: no tide in the model).

The headline set is the points that pass 1 to 4 and sit on a river, not a stream: at least
MIN_UPSTREAM_KM (20 km) of mapped network upstream within the 60 km trace (the site's own
upstream_lengths). Swimmers meet rivers; England's E. coli model was fitted on river bathing waters.
The smaller streams that pass 1 to 4 (Swansea's urban streams, expected) are scored as a second set,
"all inland points", and do not decide anything.

Signs. '---' is a plain count. '<v' means below v: it does not exceed 900 if v <= 901, and its
exceedance is unknown (the sample is left out of the exceedance scores) if v > 901. '>v' means above
v: it exceeds 900 if v >= 900, else its exceedance is unknown. For the rank correlation with log E.
coli, '<v' is taken as v / 2, '>v' as v, and a plain count as max(v, 1). Rank scores are unchanged
by any rule that keeps '<10' lowest and '>100000' highest, which this one does.

Predictors, for each sample, on its day (local days, Europe/London, as the site):

- Rain only: rain at the sample point's 0.1 degree cell in the 48 h and 24 h before midday local
  time (model/ecoli.rain_windows, SAMPLE_HOUR), from ERA5-Land hourly rain. "rain_48h" is the raw
  total. "Rain-only model" is a logistic regression on log1p(rain 48 h) and log1p(rain 24 h), fitted
  on England's river samples with overflows upstream (data/processed/ecoli_validation_rows.parquet,
  validate_ecoli.py's ERA5-Land rain to the sample time) and applied unchanged in Wales.
- Exposure: the site's index. Welsh overflows from W2's wales_annual.parquet (one position per
  overflow; emergency overflows left out, plan 5.2; positions whose outlet and asset differ by more
  than 5 km left out, as Gate A), snapped as build_overflows does (750 m, then the 1,500 m second
  pass with the receiving water's name), plus the overflow table's non-Dŵr Cymru rows. Covariates
  from the return of the year before the sample; an overflow with none takes site_static_features'
  fill (company median, then 20 / 100 / 90). Traced with transport.locate_pin and
  upstream_overflows at the default speed (0.5 m/s, 60 km, T90 30 h). Daily spill chances from
  Gate A's model, Layer 1 of spill_model_holdout_2025.pkl (predict_pooled; no Welsh overflow has an
  offset), with ERA5-Land rain; calibrated at lead 0 (calibrate_at_lead) and combined with
  combine_daily over a grid that starts history_days before the sample day, as validate_ecoli.py
  and the live forecast do. If more than 10% of the transport weight comes from days without rain
  (MAX_MISSING_SHARE) the sample has no exposure, as the site shows no figure. The production model
  (spill_model.pkl) is run beside it as a check and decides nothing.
- E. coli estimate: data/processed/ecoli_model.json (EcoliModel.predict) on rain 48 h, rain 24 h,
  the exposure, lake = 0 and the sample day, as forecast_point computes it.
- Climatology: England's river exceedance rate on the same English rows (one figure for every
  sample). "Flat": the Welsh set's own rate (it uses the answer; reported, not a test).

A sample is scored only if every predictor has a value (common rows). A missing rain window
(coverage under 90%) or exposure drops it, and the counts say how many.

Scores, on samples whose exceedance is known: Brier score; Brier skill score (BSS) against
climatology and against the rain-only model; AUC; and, on all scored samples, Spearman's rank
correlation with log10 E. coli, pooled and within station (station means of predictor and log E.
coli removed). Intervals: a bootstrap that resamples sampling days (one storm reaches many stations
on one day; the 2025 Wye survey sampled ten stations on each day), 2,000 draws, seed 0, 95%
percentile intervals. Per station with at least MIN_STATION_N (14) samples: Spearman of rain 48 h,
exposure and the estimate with log E. coli, with n, and no intervals.

Verdict, on the headline set:

- CANNOT CONCLUDE if fewer than MIN_N (60) samples with known exceedance, fewer than MIN_EXCEED (10)
  exceedances or fewer than MIN_DAYS (15) sampling days are scored.
- Otherwise SKILL if the lower ends of the 95% intervals of the estimate's BSS against climatology
  and of its AUC minus 0.5 are both above zero; else NO SKILL SHOWN.
- Reported beside it, not part of the verdict's word but part of what W10 must say: "adds to rain"
  if the lower end of the interval of Brier(rain-only model) minus Brier(estimate) is above zero;
  "exposure ranks" if the exposure index's AUC interval lies above 0.5.

Whatever the verdict, nothing is shown in Wales before the release steps of the plan (W5 to W13).
Plan, W10: the figure stays hidden unless this test shows skill.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from dipcast import config
from dipcast.model import ecoli

log = logging.getLogger("check_ecoli_wales")

PARAM = "Escherichia coli : Confirmed : MF"
THRESHOLD = ecoli.THRESHOLD          # 900 per 100 ml, the inland "sufficient" line
FIRST_DAY = pd.Timestamp("2023-01-01")
TZ = "Europe/London"
DISCHARGE_NAME = re.compile(r"DISCHARGE|OUTFALL|EFFLUENT|\bSTW FE\b|\bFE\b|INLET|\bSSO\b|STORM|PIPE", re.IGNORECASE)
UPSTREAM_OF = re.compile(r"\bU/S\b", re.IGNORECASE)
RIVER_MEDIA = {"RIVER / RUNNING SURFACE WATER", "ANY WATER"}
RIVER_HINTS = {r"\bWYE\b": "River Wye", r"\bTYWI\b|\bTOWY\b": "River Tywi"}
SNAP_OK_M = 250.0
MIN_UPSTREAM_KM = 20.0
MAX_OUTLET_ASSET_M = 5000.0
DWR_CYMRU = "Dwr Cymru Welsh Water"
MIN_N, MIN_EXCEED, MIN_DAYS = 60, 10, 15
MIN_STATION_N = 14
N_BOOT, SEED = 2000, 0
WARMUP_DAYS = 45                     # rain before the first sample: 30-day totals and the index settle
FETCH_BUDGET = 500                   # Open-Meteo weighted calls, today's limit
OUT = config.PROCESSED / "wales_ecoli_check.json"
W10_RAIN = config.CACHE / "rain_w10"
_TO_WGS = Transformer.from_crs(27700, 4326, always_xy=True)

PREDICTORS_P = ["climatology", "rain_only_model", "ecoli_estimate"]   # probabilities: Brier and AUC
PREDICTORS_R = ["rain_48h", "exposure"]                              # ranks only: AUC and Spearman


# ---------------------------------------------------------------------------
# Reading NRW's archive and the sign rules
# ---------------------------------------------------------------------------

def read_wqa(paths: list[Path]) -> pd.DataFrame:
    """E. coli rows from NRW Water Quality Archive zips (one CSV each) or CSVs."""
    frames = []
    for p in paths:
        if p.suffix == ".zip":
            with zipfile.ZipFile(p) as zf:
                for n in zf.namelist():
                    if n.lower().endswith(".csv"):
                        with zf.open(n) as f:
                            frames.append(pd.read_csv(f, dtype=str, encoding_errors="replace"))
        else:
            frames.append(pd.read_csv(p, dtype=str, encoding_errors="replace"))
    d = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["parameter_name"])
    d = d[d["parameter_name"] == PARAM].copy()
    d["value"] = pd.to_numeric(d["sample_value"], errors="coerce")
    d["sign"] = d["sign"].fillna("---").str.strip()
    d["time"] = pd.to_datetime(d["sampling_datetime"], errors="coerce").dt.tz_localize(
        TZ, ambiguous="NaT", nonexistent="NaT")
    for c in ("easting", "northing"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.reset_index(drop=True)


def exceeds(sign: str, value: float, threshold: float = THRESHOLD) -> float:
    """1.0 if the result is above the threshold, 0.0 if not, NaN if a '<' or '>' leaves it unknown."""
    if not np.isfinite(value):
        return np.nan
    if sign == "<":
        return 0.0 if value <= threshold + 1 else np.nan
    if sign == ">":
        return 1.0 if value >= threshold else np.nan
    return float(value > threshold)


def log_count(sign: str, value: float) -> float:
    """log10 E. coli for rank correlations: '<v' as v / 2, '>v' as v, a plain count as max(v, 1)."""
    if not np.isfinite(value):
        return np.nan
    if sign == "<":
        return float(np.log10(max(value / 2, 1e-3)))
    return float(np.log10(max(value, 1.0)))


def screen(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Rules 1 to 3 of the test. Returns the kept rows (with y and log_ecoli) and the rows left out
    at each rule, counted."""
    why = {}
    keep = d["time"].notna() & d["value"].notna()
    why["no_time_or_value"] = int((~keep).sum())
    r1 = keep & (d["time"].dt.tz_localize(None) >= FIRST_DAY)
    why["before_2023"] = int((keep & ~r1).sum())
    r2 = r1 & (d["deviating_result"].fillna("").str.strip().str.lower() != "yes")
    why["lab_flagged"] = int((r1 & ~r2).sum())
    st = d["station_type"].fillna("")
    fresh = st.str.startswith("FRESHWATER -") & ~st.str.contains("CANAL|LAND DRAIN", case=False)
    medium = d["sampling_medium"].fillna("").isin(RIVER_MEDIA)
    name = d["station_name"].fillna("")
    discharge = name.str.contains(DISCHARGE_NAME) & ~name.str.contains(UPSTREAM_OF)
    r3 = r2 & fresh & medium & ~discharge
    why["not_river_water"] = int((r2 & ~r3).sum())
    out = d[r3].copy()
    out["y"] = [exceeds(s, v) for s, v in zip(out["sign"], out["value"], strict=True)]
    out["log_ecoli"] = [log_count(s, v) for s, v in zip(out["sign"], out["value"], strict=True)]
    out["day"] = out["time"].dt.floor("D")
    lon, lat = _TO_WGS.transform(out["easting"].to_numpy(dtype=float), out["northing"].to_numpy(dtype=float))
    out["lon"], out["lat"] = lon, lat
    return out.reset_index(drop=True), why


def river_hint(name: str) -> str | None:
    for pat, river in RIVER_HINTS.items():
        if re.search(pat, name or "", re.IGNORECASE):
            return river
    return None


# ---------------------------------------------------------------------------
# Scores and the sampling-day bootstrap
# ---------------------------------------------------------------------------

def day_draws(days: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED) -> list[np.ndarray]:
    """Row indices of each bootstrap draw: sampling days drawn with replacement, all of a day's rows."""
    uniq, inv = np.unique(days, return_inverse=True)
    by = [np.flatnonzero(inv == i) for i in range(len(uniq))]
    rng = np.random.default_rng(seed)
    return [np.concatenate([by[i] for i in rng.integers(0, len(uniq), len(uniq))]) for _ in range(n_boot)]


def _ci(v) -> list[float]:
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))] if len(v) else [float("nan")] * 2


def _auc(y, p) -> float:
    return float(roc_auc_score(y, p)) if 0 < np.mean(y) < 1 else float("nan")


def _rho(x, y) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return float("nan")
    return float(spearmanr(x, y).statistic)


def _within(df: pd.DataFrame, col: str) -> np.ndarray:
    return (df[col] - df.groupby("station_number")[col].transform("mean")).to_numpy(dtype=float)


def score(df: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    """Scores of every predictor on df (one row per sample, all predictors present), with intervals
    from the sampling-day bootstrap."""
    df = df.reset_index(drop=True)
    known = df[df["y"].notna()].reset_index(drop=True)
    y = known["y"].to_numpy(dtype=float)
    out = {"samples": len(df), "samples_exceedance_known": len(known), "exceedances": int(y.sum()),
           "rate": float(y.mean()) if len(y) else None, "sampling_days": int(df["day"].nunique()),
           "stations": int(df["station_number"].nunique()), "predictors": {}}
    draws_k = day_draws(known["day"].to_numpy(), n_boot)
    draws_a = day_draws(df["day"].to_numpy(), n_boot)

    def brier(p, idx=None):
        idx = slice(None) if idx is None else idx
        return float(np.mean((p[idx] - y[idx]) ** 2))

    ref = {k: known[k].to_numpy(dtype=float) for k in ("climatology", "rain_only_model")}
    for k in PREDICTORS_P + PREDICTORS_R + ["flat", "ecoli_estimate_production"]:
        if k not in df:
            continue
        p = known[k].to_numpy(dtype=float)
        r: dict = {"auc": _auc(y, p), "auc_ci": _ci([_auc(y[i], p[i]) for i in draws_k]),
                   "spearman": _rho(df[k], df["log_ecoli"]),
                   "spearman_ci": _ci([_rho(df[k].to_numpy()[i], df["log_ecoli"].to_numpy()[i]) for i in draws_a]),
                   "spearman_within_station": _rho(_within(df, k), _within(df, "log_ecoli")),
                   "spearman_within_station_ci": _ci([_rho(_within(df.iloc[i], k), _within(df.iloc[i], "log_ecoli"))
                                                      for i in draws_a])}
        if k not in PREDICTORS_R:
            r["brier"] = brier(p)
            r["brier_ci"] = _ci([brier(p, i) for i in draws_k])
            for name, q in ref.items():
                if name == k:
                    continue
                r[f"bss_vs_{name}"] = 1 - brier(p) / brier(q)
                r[f"bss_vs_{name}_ci"] = _ci([1 - brier(p, i) / brier(q, i) for i in draws_k])
                r[f"brier_gain_over_{name}"] = brier(q) - brier(p)
                r[f"brier_gain_over_{name}_ci"] = _ci([brier(q, i) - brier(p, i) for i in draws_k])
        out["predictors"][k] = r
    est, rain = known["ecoli_estimate"].to_numpy(float), known["rain_only_model"].to_numpy(float)
    out["auc_gain_estimate_over_rain_only"] = _auc(y, est) - _auc(y, rain)
    out["auc_gain_estimate_over_rain_only_ci"] = _ci([_auc(y[i], est[i]) - _auc(y[i], rain[i]) for i in draws_k])
    return out


def per_station(df: pd.DataFrame) -> list[dict]:
    rows = []
    for (sid, name), g in df.groupby(["station_number", "station_name"]):
        if len(g) < MIN_STATION_N:
            continue
        rows.append({"station": sid, "name": name, "n": len(g), "exceedances": int(np.nansum(g["y"])),
                     "exceedance_unknown": int(g["y"].isna().sum()),
                     "median_ecoli": float(g["value"].median()),
                     "upstream_overflows": int(g["upstream_overflows"].iloc[0]),
                     **{f"rho_{k}": _rho(g[k], g["log_ecoli"]) for k in ("rain_48h", "exposure", "ecoli_estimate")}})
    return rows


def verdict(s: dict) -> dict:
    """The pre-stated verdict from the headline scores."""
    est = s["predictors"].get("ecoli_estimate", {})
    expo = s["predictors"].get("exposure", {})
    if (s["samples_exceedance_known"] < MIN_N or s["exceedances"] < MIN_EXCEED
            or s["sampling_days"] < MIN_DAYS):
        word = "CANNOT CONCLUDE"
    elif est.get("bss_vs_climatology_ci", [np.nan])[0] > 0 and est.get("auc_ci", [np.nan])[0] > 0.5:
        word = "SKILL"
    else:
        word = "NO SKILL SHOWN"
    return {"verdict": word,
            "adds_to_rain": bool(est.get("brier_gain_over_rain_only_model_ci", [np.nan])[0] > 0),
            "exposure_ranks": bool(expo.get("auc_ci", [np.nan])[0] > 0.5),
            "rule": {"min_n": MIN_N, "min_exceedances": MIN_EXCEED, "min_days": MIN_DAYS}}


# ---------------------------------------------------------------------------
# England's baselines
# ---------------------------------------------------------------------------

def england_baselines() -> tuple[ecoli.EcoliModel, float, dict]:
    """The rain-only model and climatology, fitted on England's river samples with overflows upstream."""
    rows = pd.read_parquet(config.PROCESSED / "ecoli_validation_rows.parquet")
    rows = rows[(rows["kind"] == "river") & (rows["upstream"] > 0)].dropna(subset=["rain_48h", "rain_24h", "ecoli"])
    X = ecoli.features(rows["rain_48h"], rows["rain_24h"], np.full(len(rows), 0.5), np.zeros(len(rows)),
                       rows["sample_time"])
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    m = ecoli.fit(X, y, ["lrain48", "lrain24"], meta={"fitted_on": "England river rows, ecoli_validation_rows"})
    return m, float(y.mean()), {"samples": len(rows), "sites": int(rows["bw_id"].nunique()),
                                "exceedances": int(y.sum()), "coef": m.coef, "intercept": m.intercept}


# ---------------------------------------------------------------------------
# Overflows, trace and rain (need the network, the model files and the cache)
# ---------------------------------------------------------------------------

def welsh_overflows(net, wa: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """One row per Welsh-return overflow, snapped as build_overflows snaps, with the overflow
    table's non-Dŵr Cymru rows beside them."""
    from dipcast.overflows import _second_pass, load_overflows
    last = wa.sort_values("year").groupby("site_id", as_index=False).last()
    pos = wa.groupby("site_id")["outlet_asset_m"].max()
    keep = (~last["emergency"].astype(bool) & last["lat"].notna()
            & ~(last["site_id"].map(pos) > MAX_OUTLET_ASSET_M))
    info = {"return_overflows": len(last), "emergency_left_out": int(last["emergency"].astype(bool).sum()),
            "position_doubt_left_out": int((last["site_id"].map(pos) > MAX_OUTLET_ASSET_M).sum())}
    df = last[keep][["site_id", "company", "site_name", "lat", "lon", "receiving_water"]].rename(
        columns={"receiving_water": "receiving_watercourse"}).reset_index(drop=True)
    snap = net.snap_many(df["lon"].to_numpy(), df["lat"].to_numpy(), max_m=config.SNAP_MAX_M)
    for a, b in (("link_id", "link_id"), ("frac", "frac"), ("snap_dist_m", "dist_m"), ("form", "form")):
        df[a] = snap[b].to_numpy()
    df["snap_confidence"] = np.where(df["link_id"].notna(), "high", None)
    df = _second_pass(net, df)
    df = df[df["link_id"].notna()].copy()
    df["start_node"] = net.links.loc[df["link_id"], "start_node"].to_numpy()
    df["end_node"] = net.links.loc[df["link_id"], "end_node"].to_numpy()
    df["link_length"] = net.links.loc[df["link_id"], "length"].to_numpy()
    df["welsh_return"] = True
    info["snapped"] = len(df)
    eng = load_overflows(net)
    eng = eng[(eng["company"] != DWR_CYMRU) & eng["link_id"].notna()].assign(welsh_return=False)
    cols = [*df.columns]
    both = pd.concat([df, eng[[c for c in cols if c in eng] + ["lta_spills", "spill_hours", "edm_operational_pct"]]],
                     ignore_index=True)
    info["english_rows_added"] = len(eng)
    return both, info


def trace_stations(net, ov: pd.DataFrame, stations: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Rule 4 and the river/stream split for each station, and its upstream overflows."""
    from dipcast.model.transport import (
        locate_pin,
        river_velocity,
        upstream_lengths,
        upstream_overflows,
    )
    rows, ups = [], {}
    for _, s in stations.iterrows():
        pin = locate_pin(net, float(s["lon"]), float(s["lat"]), river_hint=river_hint(s["station_name"]))
        ok = pin.mode == "river" and pin.snap is not None and pin.snap.form == "inlandRiver" \
            and pin.snap.dist_m <= SNAP_OK_M
        up_km = np.nan
        up = pd.DataFrame()
        if ok:
            _, lup = upstream_lengths(net, pin.trace_node, config.MAX_UPSTREAM_KM * 1000)
            up_km = (lup.get(pin.trace_node, 0.0) + pin.trace_offset_m) / 1000
            up = upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None))
        ups[s["station_number"]] = up
        rows.append({"station_number": s["station_number"], "on_network": ok, "mode": pin.mode,
                     "form": None if pin.snap is None else pin.snap.form,
                     "snap_m": None if pin.snap is None else round(pin.snap.dist_m, 1),
                     "watercourse": pin.watercourse, "upstream_km": up_km,
                     "river": bool(ok and up_km >= MIN_UPSTREAM_KM),
                     "upstream_overflows": len(up), "sum_weight": float(up["weight"].sum()) if len(up) else 0.0})
    return pd.DataFrame(rows), ups


def rain_needs(samples: pd.DataFrame, ups: dict) -> pd.DataFrame:
    """(cell, start, end) hour ranges the scores need: each sample year's span with warm-up, for the
    sample cell and every upstream overflow's cell."""
    from dipcast.ingest.rainfall import grid_cell
    from dipcast.model.transport import history_days
    need = []
    for (sid, yr), g in samples.groupby(["station_number", samples["day"].dt.year]):
        up = ups.get(sid, pd.DataFrame())
        hist = history_days(up["travel_h"]) if len(up) else 1
        start = g["day"].min() - pd.Timedelta(days=WARMUP_DAYS + hist)
        end = g["day"].max() + pd.Timedelta(days=1)
        lats = [float(g["lat"].iloc[0]), *(up["lat"].tolist() if len(up) else [])]
        lons = [float(g["lon"].iloc[0]), *(up["lon"].tolist() if len(up) else [])]
        cl, cn = grid_cell(np.array(lats), np.array(lons))
        for a, b in {(round(float(a), 3), round(float(b), 3)) for a, b in zip(cl, cn, strict=True)}:
            need.append((a, b, start, end))
    n = pd.DataFrame(need, columns=["cell_lat", "cell_lon", "start", "end"])
    return n.groupby(["cell_lat", "cell_lon"], as_index=False).agg(start=("start", "min"), end=("end", "max"))


def load_rain(cells: pd.DataFrame) -> pd.DataFrame:
    """Hourly rain for the cells from the shared cache's archive files and this script's own."""
    from dipcast.ingest.rainfall import cell_key
    frames = []
    for c in cells.itertuples():
        key = cell_key(c.cell_lat, c.cell_lon)
        for y in range(c.start.year, c.end.year + 1):
            p = config.CACHE / "rain" / f"archive_{key}_{y}.parquet"
            if p.exists():
                frames.append(pd.read_parquet(p))
        frames += [pd.read_parquet(p) for p in sorted(W10_RAIN.glob(f"archive_{key}_*.parquet"))]
    if not frames:
        return pd.DataFrame(columns=["cell_lat", "cell_lon", "time", "precip_mm"])
    r = pd.concat(frames, ignore_index=True)
    r["cell_lat"], r["cell_lon"] = r["cell_lat"].round(3), r["cell_lon"].round(3)
    r = r[np.isfinite(r["precip_mm"].astype(float))]
    return r.drop_duplicates(["cell_lat", "cell_lon", "time"], keep="first").reset_index(drop=True)


def rain_gaps(cells: pd.DataFrame, rain: pd.DataFrame) -> pd.DataFrame:
    """The cells whose cached hours cover less than 99% of their needed span."""
    out = []
    for c in cells.itertuples():
        hours = pd.date_range(c.start.tz_convert("UTC"), c.end.tz_convert("UTC"), freq="h")
        have = rain[(rain["cell_lat"] == c.cell_lat) & (rain["cell_lon"] == c.cell_lon)]["time"]
        cover = float(pd.Index(have).isin(hours).sum()) / len(hours)
        if cover < 0.99:
            out.append({**c._asdict(), "cover": cover})
    return pd.DataFrame(out)


def weighted_calls(start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Open-Meteo counts a request for more than two weeks of one variable at one place as several:
    days / 14, rounded up here to stay on the safe side."""
    return int(np.ceil(((end - start).days + 1) / 14))


def fetch_gaps(gaps: pd.DataFrame, budget: int = FETCH_BUDGET) -> dict:
    """ERA5-Land hourly rain for each gap, one cell per request, in turn; stops at the first refusal
    or failure, and before the budget of weighted calls would be passed."""
    from dipcast.ingest.rainfall import _request, _to_frame, cell_key
    W10_RAIN.mkdir(parents=True, exist_ok=True)
    latest = pd.Timestamp.now("UTC").tz_localize(None).normalize() - pd.Timedelta(days=6)
    used, requests, stopped = 0, 0, None
    for g in gaps.itertuples():
        s = g.start.tz_convert("UTC").tz_localize(None).normalize()
        e = min(g.end.tz_convert("UTC").tz_localize(None).normalize(), latest)
        w = weighted_calls(s, e)
        if used + w > budget:
            stopped = f"budget: {used} used, next needs {w}"
            break
        params = {"latitude": f"{g.cell_lat:.3f}", "longitude": f"{g.cell_lon:.3f}",
                  "start_date": s.strftime("%Y-%m-%d"), "end_date": e.strftime("%Y-%m-%d"),
                  "hourly": "precipitation", "timezone": "UTC"}
        try:
            res = _request(config.OPEN_METEO_ARCHIVE, params, attempts=1, retry_429=False)
        except Exception as ex:  # noqa: BLE001 - any refusal ends the run
            stopped = f"refused at request {requests + 1}: {ex}"
            requests += 1
            break
        requests += 1
        used += w
        df = _to_frame(res, g.cell_lat, g.cell_lon)
        df.to_parquet(W10_RAIN / f"archive_{cell_key(g.cell_lat, g.cell_lon)}_{s:%Y%m%d}_{e:%Y%m%d}.parquet",
                      index=False)
    return {"requests": requests, "weighted_calls": used, "stopped": stopped, "gaps": len(gaps)}


def predictors(samples: pd.DataFrame, ups: dict, wa: pd.DataFrame, rain: pd.DataFrame, models: dict,
               rain_model: ecoli.EcoliModel, clim: float) -> tuple[pd.DataFrame, dict]:
    """Every predictor for every sample. Rows lacking one keep NaN there and are counted."""
    from dipcast.ingest.rainfall import grid_cell
    from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features
    from dipcast.model.forecast import MAX_MISSING_SHARE, calibrate_at_lead
    from dipcast.model.transport import combine_daily, history_days, missing_share
    em = ecoli.EcoliModel.from_json()
    hourly = rain.assign(time=rain["time"].dt.tz_convert(TZ))
    daily = daily_rain_features(hourly)
    by_cell = hourly.set_index(["cell_lat", "cell_lon"]).sort_index()
    out = []
    for (sid, yr), g in samples.groupby(["station_number", samples["day"].dt.year]):
        g = g.sort_values("time").copy()
        cl, cn = (round(float(v), 3) for v in grid_cell(float(g["lat"].iloc[0]), float(g["lon"].iloc[0])))
        try:
            site = by_cell.loc[(cl, cn)].set_index("time")["precip_mm"].sort_index()
        except KeyError:
            site = pd.Series(dtype=float)
        ends = pd.DatetimeIndex(g["day"] + pd.Timedelta(hours=ecoli.SAMPLE_HOUR))
        g["rain_48h"], g["rain_24h"] = ecoli.rain_windows(site, ends)
        up = ups.get(sid, pd.DataFrame())
        days_s = pd.DatetimeIndex(sorted(g["day"].unique()))
        for name in models:
            g[f"exposure_{name}"] = 0.0 if not len(up) else np.nan
        if len(up):
            hist = history_days(up["travel_h"])
            days = pd.date_range(days_s.min() - pd.Timedelta(days=hist), days_s.max(), freq="D")
            cov = wa[wa["year"] == yr - 1].set_index("site_id")
            sites = up[["site_id", "lat", "lon", "company"]].copy()
            for c in ("lta_spills", "spill_hours", "edm_operational_pct"):
                sites[c] = np.where(up["welsh_return"].to_numpy(dtype=bool), sites["site_id"].map(cov[c]),
                                    up[c].to_numpy(dtype=float))
            sd = build_site_days(sites, daily, days)
            sd["ok"] = sd["rain_d"].notna()
            X = sd.astype({f: np.float32 for f in ALL_FEATURES}).fillna({f: 0.0 for f in ALL_FEATURES})
            okm = sd.pivot(index="site_id", columns="day", values="ok").reindex(index=up["site_id"], columns=days)
            avail = okm.fillna(False).to_numpy(dtype=bool)
            w, tr = up["weight"].to_numpy(dtype=float), up["travel_h"].to_numpy(dtype=float)
            miss = pd.Series(missing_share(avail, w, tr), index=days)
            for name, model in models.items():
                sd["p"] = np.where(sd["ok"], model.predict_pooled(X), np.nan)
                pm = sd.pivot(index="site_id", columns="day", values="p").reindex(index=up["site_id"], columns=days)
                pm = calibrate_at_lead(np.nan_to_num(pm.to_numpy(dtype=float)), lead=0)
                risk = pd.Series(combine_daily(pm, w, tr), index=days)
                risk[miss > MAX_MISSING_SHARE] = np.nan
                g[f"exposure_{name}"] = g["day"].map(risk).to_numpy(dtype=float)
        g["year"] = yr
        out.append(g)
    df = pd.concat(out, ignore_index=True)
    df["exposure"] = df["exposure_gate_a"]
    Xr = ecoli.features(df["rain_48h"], df["rain_24h"], np.full(len(df), 0.5), np.zeros(len(df)), df["day"])
    df["rain_only_model"] = rain_model.predict(Xr)
    for name, col in (("gate_a", "ecoli_estimate"), ("production", "ecoli_estimate_production")):
        X = ecoli.features(df["rain_48h"], df["rain_24h"], df[f"exposure_{name}"], np.zeros(len(df)), df["day"])
        p = em.predict(X)
        df[col] = np.where(df["rain_48h"].notna() & df[f"exposure_{name}"].notna(), p, np.nan)
    df["climatology"] = clim
    counts = {"rain_window_missing": int(df["rain_48h"].isna().sum()),
              "exposure_missing": int(df["exposure"].isna().sum())}
    return df, counts


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(f"{float(o):.4g}")
    return o


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wqa", type=Path, default=config.CACHE / "nrw_wqa" / "Files")
    ap.add_argument("--wales-annual", type=Path, default=config.PROCESSED / "wales_annual.parquet")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    args = ap.parse_args(argv)

    from dipcast.model.spill_model import SpillModel
    from dipcast.network.rivers import RiverNetwork

    raw = read_wqa(sorted(args.wqa.glob("*_Water_Quality_Archive.zip")))
    samples, dropped = screen(raw)
    log.info("%d E. coli rows; %d pass rules 1-3 at %d stations", len(raw), len(samples),
             samples["station_number"].nunique())
    stations = samples.groupby("station_number", as_index=False).agg(
        station_name=("station_name", "first"), lat=("lat", "first"), lon=("lon", "first"))
    net = RiverNetwork.load()
    wa = pd.read_parquet(args.wales_annual)
    ov, ov_info = welsh_overflows(net, wa)
    st, ups = trace_stations(net, ov, stations)
    samples = samples.merge(st, on="station_number", how="left")
    dropped["off_network"] = int((~samples["on_network"]).sum())
    samples = samples[samples["on_network"]].reset_index(drop=True)

    need = rain_needs(samples, ups)
    rain = load_rain(need)
    gaps = rain_gaps(need, rain)
    fetch = {"requests": 0, "weighted_calls": 0, "stopped": None, "gaps": len(gaps)}
    if args.fetch and len(gaps):
        fetch = fetch_gaps(gaps)
        rain = load_rain(need)
        gaps = rain_gaps(need, rain)
    fetch["gaps_left"] = len(gaps)
    log.info("rain: %d cells needed, %d short; fetch %s", len(need), len(gaps), fetch)

    models = {"gate_a": SpillModel.load(config.PROCESSED / "spill_model_holdout_2025.pkl"),
              "production": SpillModel.load(config.PROCESSED / "spill_model.pkl")}
    rain_model, clim, eng = england_baselines()
    df, miss = predictors(samples, ups, wa, rain, models, rain_model, clim)
    need_cols = ["rain_48h", "rain_24h", "exposure", "ecoli_estimate"]
    scored = df.dropna(subset=need_cols).copy()
    scored["flat"] = float(scored["y"].mean())
    head = scored[scored["river"]]
    head = head.assign(flat=float(head["y"].mean()))
    res_head = score(head, args.n_boot)
    res_all = score(scored, args.n_boot)

    station_rows = st.merge(stations[["station_number", "station_name"]], on="station_number")
    station_rows["samples_screened"] = station_rows["station_number"].map(
        df.groupby("station_number").size()).fillna(0).astype(int)
    station_rows["samples_scored"] = station_rows["station_number"].map(
        scored.groupby("station_number").size()).fillna(0).astype(int)
    out = {
        "written": pd.Timestamp.now("UTC").date().isoformat(),
        "what": "W10 E. coli check in Wales (docs/WALES-PLAN-2026-10.md; scripts/check_ecoli_wales.py). "
                "Summary scores only; no sample rows and no Dŵr Cymru rows.",
        "source": "Natural Resources Wales Water Quality Archive (NRW_DS124903), Open Government Licence v3. "
                  "Contains Natural Resources Wales information © Natural Resources Wales and Database Right. "
                  "All rights Reserved. Contains Ordnance Survey Data. Ordnance Survey Licence number "
                  "AC0000849444. Crown Copyright and Database Right.",
        "threshold": THRESHOLD, "bootstrap": {"draws": args.n_boot, "seed": SEED, "clusters": "sampling days"},
        "rows": {"ecoli_rows_read": len(raw), "dropped": dropped, "after_rules_1_to_4": len(df),
                 **miss, "scored_all_inland": len(scored), "scored_headline": len(head),
                 "by_year_headline": {str(k): int(v) for k, v in head["day"].dt.year.value_counts().sort_index().items()},
                 "signs_scored": {str(k): int(v) for k, v in scored["sign"].value_counts().items()}},
        "stations": station_rows.drop(columns=["lat", "lon"], errors="ignore").to_dict("records"),
        "overflows": ov_info, "rain": {"cells": len(need), **fetch},
        "england_baselines": {"climatology_river_rate": clim, **eng},
        "headline": res_head, "all_inland": res_all,
        "per_station": per_station(head),
    }
    out["verdict"] = verdict(res_head)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out = clean(out)
    args.out.write_text(json.dumps(out, indent=1, default=str))
    log.info("W10: %s -> %s", out["verdict"], args.out)
    print(json.dumps(out["verdict"], indent=1))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main(sys.argv[1:])
