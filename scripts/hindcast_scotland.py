"""Scotland hindcast, Stage A (task S3 of docs/SCOTLAND-PLAN-2026-10.md, section 6). Off CI; publishes nothing.

A hindcast is a forecast made after the fact with the rain that fell, scored against what the
overflows did. This script applies the English spill model, unchanged, to Scottish Water's
overflows, and writes a summary of scores (no rows) to data/processed/scotland_hindcast.json.
Contains Scottish Water data licensed under the Open Government Licence v3.0.

    DIPCAST_ROOT=<main checkout> uv run python scripts/hindcast_scotland.py --dry-run
    DIPCAST_ROOT=<main checkout> uv run python scripts/hindcast_scotland.py

It reads S1's events (sw_events.parquet), S2's covariates (sw_covariates.parquet) and rain cells
(scotland_rain_cells.csv), and rain only from the cache: ERA5-Land archive_*.parquet and archived
forecasts leads_*.parquet. It never calls Open-Meteo, except with --fetch-leads (see "Rain").

GATE A
======

Written 11 October 2026, before any run that scores a forecast against a Scottish label, and
committed on its own before the script's code. It is not to be changed after any result is seen.
A different rule would be a new, dated rule beside this one, and the write-up would report both.
Before writing it I had looked at: the number of Scottish overflow-years with a count, by year; the
rain cell-years cached so far; and the durations of United Utilities' training events (below). No
Scottish forecast had been made or scored.

Model. Layer 1 (the pooled model) of data/processed/spill_model_holdout_2025.pkl: trained by
scripts/train.py on United Utilities' discharges of 2023 and 2024, and not refitted. The
production model (spill_model.pkl, refitted on 2023 to 2025) is scored beside it as a check and has
no part in the gate.

Rain. ERA5-Land hourly rain per 0.1 degree cell, UK local days, features from
model/features.daily_rain_features, as train.py builds them. A year's features come from its own
cell-year and, for January's antecedent windows, the cell-year before, where that is 2021 or later
(the archive starts in 2021). Rows whose day has no rain total are dropped, as in train.py. "Lead 0"
means this rain, the rain that fell. "Leads 1, 2 and 3" mean Open-Meteo's archived forecasts for
2025, built as scripts/verify_leads.py builds them (the target day and the two days before from the
forecast, longer windows from ERA5-Land).

Overflows and labels. Scottish Water's event history (task S1) and the covariates of task S2
(ingest/sw_covariates.py). A label is a spill-day: a UK local day touched by an event that
sw_covariates.counted_events keeps (longer than 15 min 30 s, or of unknown duration), in every year
and both files. A day record (no end time; its start is local midnight) labels its local date. An
overflow-year is "counted" when its S2 status is "events" or "no events". Left out: emergency
overflows (EO in the API's overflow type, or "EO" or "Emergency" in the measurement point's name;
plan 5.2: they do not spill because of rain); overflows with no position; and an overflow-year
whose own uptime (edm_operational_pct) is below 50%, as train.py does. Unknown uptime is kept.

Sets.

- G, the gated set: overflow-years of 2022 to 2025 counted in that year and in the year before.
- N, reported only: overflow-years of 2022 to 2025 counted in that year but not the year before.
  Most are the overflows whose first published year is 2025.

Arms, on G.

- "Scottish covariates", the arm the gate is about, named before the run: lta_spills, spill_hours
  and edm_operational_pct from S2's return of the year before (sw_covariates.covariates_for). A
  missing value takes the median of that year's G overflows, then the model's default, as
  features.site_static_features does with company "Scottish Water".
- "Default covariates": all three missing, so site_static_features gives 20 spills, 100 hours and
  90%. This is what Scotland would get with no new code.
- "Calibration layer": the Scottish-covariates arm plus SpillModel.fit_site_offsets (prior 15
  spill-days, recency 1, as train.py), fitted for each test year only on the overflow's counted
  years before it, each with its own year-before covariates.
- "Production model, Scottish covariates": a check.

On N: "default covariates" only (N has no year before to take covariates from).

Baselines.

- "Earlier years", the gate's baseline: the overflow's spill-day rate over its counted years
  before the test year (the same uptime rule): spill-days divided by days in those years. Where
  it has none, the spill-day rate of all counted Scottish overflow-years before the test year in the
  same calendar month. Clipped to 0.001 to 0.95.
- "Flat": the test set's own spill-day rate on every row. It uses the answer, so it is a hard
  baseline, as the accuracy page shows it.

Scores. Brier score; Brier skill score (BSS) = 1 - Brier(model) / Brier(baseline); log loss; AUC;
reliability by tenths; the level, sum of forecasts / spill-days; wet days (rain_d + rain_d1 > 10 mm)
and dry days apart; by year; by overflow type (CSO, SSSO, CSO/SSSO, not in the API); by local
authority (the API's LOCAL_AUTHORITY_NAME). Intervals: a cluster bootstrap that resamples
overflows and ISO weeks together (rows weighted by the product of the overflow's and the week's
draw counts), 2,000 draws, seed 0, 95% percentile intervals.

Pass rule.

- G1. G at lead 0, the four test years pooled: the lower end of the 95% interval of BSS (Scottish
  covariates against earlier years) is above zero.
- G2, G3, G4. G's 2025 rows at leads 1, 2 and 3, each lead separately: the same, on the rows whose
  cell has archived forecasts. A lead test runs only if those rows hold at least LEAD_MIN_SITES
  (20) overflows and LEAD_MIN_SPILL_DAYS (200) spill-days; otherwise it is untested.
- G with fewer than MIN_SITES (10) overflows or MIN_SPILL_DAYS (100) spill-days at lead 0 is
  untested.

Verdict: FAIL if any tested part fails. PASS if all four parts are tested and pass. NOT COMPLETE if
no tested part fails and some part is untested; that is not a pass, and the Scottish forecast does
not go ahead on it. On FAIL, the next step is a short write-up in the accuracy page's terms, and
Scotland's spill forecast stops (plan, task S3).

The other arms, set N, the groups and the level are reported, not gated. The gated arm is not
re-chosen from them after the fact.

The 15 min 30 s cut and the training labels (the plan's open check, section 6). Checked on 11
October 2026 in the code and in the training file: neither ingest/edm_events.py nor train.py cuts
short events, and in data/processed/edm_events.parquet 52.1%, 48.4% and 49.8% of United Utilities'
2023, 2024 and 2025 events last 15 min 30 s or less. Leaving those out removes 13.9% of UU's
spill-days (14.1%, 13.3% and 14.2% by year). So the model learned from labels that include short
events, and here it is scored on labels without them. Inferred, not measured: if short events are
as common in Scotland, the model forecasts about 1 / 0.86 = 1.16 times too many spill-days. The
earlier-years baseline is built from the same cut labels, so the mismatch can only lower the
model's skill against it. The rule stays as the plan states it, the gate is not eased for it, and
the level is reported. A second mismatch pushes the other way (inferred, not measured): S2 counts
lta_spills after the cut, while the EA returns the model learned from count every event, so a
Scottish overflow reads as quieter than an English one with the same discharges.

Rain needed, and the refusal. The script scores only when every archive cell-year that G's scored
rows need (the test year and the year before) is cached, and every 2025 archived-forecast file
for the cells of G's 2025 rows. Otherwise it stops with the count missing and scores nothing.
`--without-leads` drops the second condition; G2 to G4 are then untested, so the verdict cannot be
PASS. The calibration arm (its fitting years need more cell-years) and set N each run only if all
their cell-years are cached; otherwise the result says "not run" and how many are missing.
`--fetch-leads --max-calls N` asks Open-Meteo's previous-runs API for the missing 2025 forecast
files of G's cells, paced, stopping at the first refusal or before N calls; it scores nothing.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hindcast_wales as hw
from fetch_wales_history import archive_calls, archive_days

from dipcast import config
from dipcast.ingest import sw_covariates, sw_history
from dipcast.ingest.rainfall import cell_key, grid_cell
from dipcast.model.features import daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel

log = logging.getLogger("hindcast_scotland")

MODEL = config.PROCESSED / "spill_model_holdout_2025.pkl"
PRODUCTION = config.PROCESSED / "spill_model.pkl"
OUT = config.PROCESSED / "scotland_hindcast.json"
EVENTS = config.PROCESSED / "sw_events.parquet"
COVARIATES = config.PROCESSED / "sw_covariates.parquet"
CELLS = config.PROCESSED / "scotland_rain_cells.csv"
API_ANSWER = sw_history.RAW_DIR / "near_real_time.json"
COMPANY = "Scottish Water"
TZ = "Europe/London"

MIN_EDM_PCT = 50.0
WET_MM = 10.0
BASE_CLIP = (0.001, 0.95)
N_BOOT = 2000
SEED = 0
MIN_SITES, MIN_SPILL_DAYS = 10, 100
LEAD_MIN_SITES, LEAD_MIN_SPILL_DAYS = 20, 200
GATE_LEADS = [1, 2, 3]
TEST_YEARS = [2022, 2023, 2024, 2025]
LEAD_YEAR = 2025
FIRST_RAIN_YEAR = 2021
LEAD_VARIABLES = 5          # precipitation and precipitation_previous_day1..4 (ingest/rainfall_leads.py)
LEADS_PER_REQUEST = 2       # a year x 5 leads x 5 cells timed out before (fetch_rain_leads_upstream.py)
GROUP_MIN_SITES = 5

SCOT, DEFAULT, CALIB, PROD = ("Scottish covariates", "default covariates", "calibration layer",
                              "production model, Scottish covariates")
EARLIER, FLAT = "earlier years", "flat"
COV = hw.COV

Key = tuple[float, float, int]


# ---------------------------------------------------------------------------
# Labels and overflow-years
# ---------------------------------------------------------------------------

def labels(ev: pd.DataFrame) -> pd.DataFrame:
    """(site_id, day) spill-days from the events sw_covariates.counted_events keeps (over 15 min
    30 s, or of unknown duration; one row per overflow, start and end across both files). A timed
    event touches local days as features.spill_days counts them; a day record (no end) labels its
    local date too."""
    kept = sw_covariates.counted_events(ev)
    timed = spill_days(kept[kept["event_end"].notna()])
    rec = kept[kept["event_end"].isna()]
    local = rec["event_start"].dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
    days = pd.DataFrame({"site_id": rec["site_id"].to_numpy(),
                         "day": pd.DatetimeIndex(local).tz_localize(TZ)})
    out = pd.concat([timed.astype({"day": f"datetime64[ns, {TZ}]"}),
                     days.astype({"day": f"datetime64[ns, {TZ}]"})], ignore_index=True)
    return out.drop_duplicates().reset_index(drop=True)


def emergency_by_name(ev: pd.DataFrame) -> set[str]:
    """Overflows whose measurement point is named as an emergency overflow in any event row."""
    names = ev[["site_id", "site_name"]].drop_duplicates()
    hit = names["site_name"].astype("string").str.contains(hw.EMERGENCY, case=False, regex=True)
    return set(names.loc[hit.fillna(False).astype(bool), "site_id"])


def type_group(asset_type: pd.Series) -> pd.Series:
    t = asset_type.astype("string").str.upper().str.strip()
    named = t.map({"CSO": "CSO", "SSSO": "SSSO", "CSO/SSSO": "CSO/SSSO"})
    return named.where(named.notna(), t.where(t.isna(), "other")).fillna("not in the API").astype(str)


def overflow_years(cov: pd.DataFrame, by_name: set[str], authority: dict[str, str] | None = None) -> pd.DataFrame:
    """S2's covariate table, one row per overflow and year, with: counted, emergency (API type or
    name), eligible (counted, position known, not emergency, uptime not below MIN_EDM_PCT), prev
    (counted the year before), set ("G", "N" or None), type, authority and rain cell."""
    c = cov.copy()
    c["counted"] = c["spills"].notna().to_numpy(dtype=bool)
    c["emergency"] = c["emergency"].eq(True).to_numpy(dtype=bool) | c["site_id"].isin(by_name).to_numpy()
    low = (c["edm_operational_pct"] < MIN_EDM_PCT).fillna(False).to_numpy(dtype=bool)
    c["eligible"] = c["counted"] & c["lat"].notna() & ~c["emergency"] & ~low
    counted = set(zip(c.loc[c["counted"], "site_id"], c.loc[c["counted"], "year"], strict=True))
    c["prev"] = [(s, y - 1) in counted for s, y in zip(c["site_id"], c["year"], strict=True)]
    test = (c["eligible"] & c["year"].isin(TEST_YEARS)).to_numpy()
    prev = c["prev"].to_numpy(dtype=bool)
    c["set"] = pd.Series(np.where(test & prev, "G", np.where(test & ~prev, "N", "")), index=c.index).replace("", None)
    c["type"] = type_group(c["asset_type"] if "asset_type" in c else pd.Series(pd.NA, index=c.index))
    c["authority"] = c["site_id"].map(authority or {}).fillna("not in the API")
    cl, cn = grid_cell(c["lat"].to_numpy(), c["lon"].to_numpy())
    c["cell_lat"], c["cell_lon"] = cl, cn
    return c


def fit_years(oy: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    """The calibration layer's fitting rows: eligible overflow-years of G's overflows before the
    latest year each is tested in (each test year then uses only the years before it)."""
    last = g.groupby("site_id")["year"].max()
    e = oy[oy["eligible"] & oy["site_id"].isin(last.index)]
    return e[e["year"] < e["site_id"].map(last)]


# ---------------------------------------------------------------------------
# Rain needs and the cache
# ---------------------------------------------------------------------------

def rain_needs(rows: pd.DataFrame) -> set[Key]:
    """Archive cell-years the rows need: each row's year and, from FIRST_RAIN_YEAR on, the one before."""
    out: set[Key] = set()
    for a, b, y in zip(rows["cell_lat"], rows["cell_lon"], rows["year"], strict=True):
        if np.isfinite(a) and np.isfinite(b):
            out.add((float(a), float(b), int(y)))
            if y - 1 >= FIRST_RAIN_YEAR:
                out.add((float(a), float(b), int(y) - 1))
    return out


def lead_needs(g: pd.DataFrame) -> set[Key]:
    r = g[g["year"] == LEAD_YEAR]
    return {(float(a), float(b), LEAD_YEAR) for a, b in zip(r["cell_lat"], r["cell_lon"], strict=True)
            if np.isfinite(a) and np.isfinite(b)}


def rain_path(kind: str, k: Key) -> Path:
    return config.CACHE / "rain" / f"{kind}_{cell_key(k[0], k[1])}_{k[2]}.parquet"


def missing(kind: str, keys: set[Key]) -> set[Key]:
    return {k for k in keys if not rain_path(kind, k).exists()}


def load_rain(kind: str, keys: set[Key]) -> pd.DataFrame:
    frames = [pd.read_parquet(rain_path(kind, k)) for k in sorted(keys)]
    cols = ["cell_lat", "cell_lon", "time", "precip_mm"] + (["lead"] if kind == "leads" else [])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)


def archive_calls_for(keys: set[Key]) -> float:
    return float(sum(archive_calls(1, archive_days(y)) for _, _, y in keys))


def lead_calls_for(keys: set[Key]) -> float:
    """Open-Meteo calls to fetch these lead files: one location each, a whole past year (fetch_leads
    asks to 31 December), 5 variables, so 365 / 14 = 26.1 calls a file."""
    return float(sum(archive_calls(1, _days_in(y), LEAD_VARIABLES) for _, _, y in keys))


def by_tier(keys: set[Key], tiers: dict[Key, int]) -> dict:
    """Needed, cached and missing archive cell-years and calls left, by S2's fetch tier."""
    out = {}
    for t in sorted({tiers.get(k, 0) for k in keys}):
        ks = {k for k in keys if tiers.get(k, 0) == t}
        miss = missing("archive", ks)
        out[f"tier {t}" if t else "not listed"] = {"needed": len(ks), "cached": len(ks) - len(miss),
                                                   "missing": len(miss), "calls_left": round(archive_calls_for(miss))}
    return out


# ---------------------------------------------------------------------------
# Baselines, site-days and arms
# ---------------------------------------------------------------------------

def _days_in(year: int) -> int:
    return 366 if pd.Timestamp(f"{year}-12-31").dayofyear == 366 else 365


def earlier_rates(oy: pd.DataFrame, lab: pd.DataFrame, year: int) -> tuple[pd.Series, pd.Series]:
    """(per overflow, per calendar month) spill-day rates over eligible overflow-years before `year`.
    The first is spill-days / days in those years; the second pools every such overflow-year."""
    e = oy[oy["eligible"] & (oy["year"] < year)][["site_id", "year"]]
    if e.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    lab = lab.assign(year=lab["day"].dt.year, month=lab["day"].dt.month).merge(e, on=["site_id", "year"])
    days = e.assign(days=e["year"].map(_days_in)).groupby("site_id")["days"].sum()
    own = lab.groupby("site_id").size().reindex(days.index, fill_value=0) / days
    month_days = pd.Series({m: sum(pd.Period(f"{y}-{m:02d}").days_in_month for y in e["year"])
                            for m in range(1, 13)}, dtype=float)
    month = lab.groupby("month").size().reindex(range(1, 13), fill_value=0) / month_days
    return own, month


def baseline(sd: pd.DataFrame, own: pd.Series, month: pd.Series) -> np.ndarray:
    r = sd["site_id"].map(own)
    r = r.fillna(sd["day"].dt.month.map(month))
    return r.fillna(0.0).clip(*BASE_CLIP).to_numpy()


def sites_for(oy: pd.DataFrame, cov: pd.DataFrame, year: int, which: str) -> pd.DataFrame:
    """The overflows of set `which` in `year`, with the year-before covariates (missing where S2
    has none) and company "Scottish Water" for site_static_features' median fill."""
    s = oy[(oy["set"] == which) & (oy["year"] == year)][["site_id", "lat", "lon"]]
    c = sw_covariates.covariates_for(cov, year)[["site_id", *COV]]
    return s.merge(c, on="site_id", how="left").assign(company=COMPANY)


def year_rows(oy: pd.DataFrame, cov: pd.DataFrame, lab: pd.DataFrame, daily: pd.DataFrame, year: int,
              which: str, models: dict) -> pd.DataFrame:
    """Scored rows of set `which` in one test year: y, each arm's forecast and the baseline."""
    s = sites_for(oy, cov, year, which)
    if s.empty:
        return pd.DataFrame()
    sd = hw.site_days(s, daily, year, lab)
    dd = hw.features(hw.site_days(hw.default_arm(s), daily, year, lab))
    assert (dd["site_id"].to_numpy() == sd["site_id"].to_numpy()).all()
    assert (dd["day"].to_numpy() == sd["day"].to_numpy()).all()
    sd[DEFAULT] = models["holdout"].predict_pooled(dd)
    if which == "G":
        X = hw.features(sd)
        sd[SCOT] = models["holdout"].predict_pooled(X)
        if "production" in models:
            sd[PROD] = models["production"].predict_pooled(X)
    own, month = earlier_rates(oy, lab, year)
    sd[EARLIER] = baseline(sd, own, month)
    oyy = oy[oy["year"] == year].set_index("site_id")
    sd["type"] = sd["site_id"].map(oyy["type"])
    sd["authority"] = sd["site_id"].map(oyy["authority"])
    return sd


def calibration(oy: pd.DataFrame, cov: pd.DataFrame, lab: pd.DataFrame, daily: pd.DataFrame,
                g_rows: pd.DataFrame, model: SpillModel) -> np.ndarray:
    """The calibration arm on G's rows: for each test year, site offsets fitted on the overflows'
    eligible years before it only, each year with its own year-before covariates."""
    out = np.full(len(g_rows), np.nan)
    for year in sorted(g_rows["year"].unique()):
        idx = np.flatnonzero(g_rows["year"].to_numpy() == year)
        ids = set(g_rows["site_id"].iloc[idx])
        fit = []
        for y0 in range(FIRST_RAIN_YEAR, int(year)):
            e = oy[oy["eligible"] & (oy["year"] == y0) & oy["site_id"].isin(ids)][["site_id", "lat", "lon"]]
            if e.empty:
                continue
            s = e.merge(sw_covariates.covariates_for(cov, y0)[["site_id", *COV]], on="site_id", how="left")
            fit.append(hw.site_days(s.assign(company=COMPANY), daily, y0, lab))
        m = dataclasses.replace(model, site_offset={}, site_n={})
        if fit:
            m.fit_site_offsets(hw.features(pd.concat(fit, ignore_index=True)))
        out[idx] = m.predict(hw.features(g_rows.iloc[idx]))
    return out


# ---------------------------------------------------------------------------
# Scores and the gate
# ---------------------------------------------------------------------------

def score_rows(df: pd.DataFrame, main: str, n_boot: int = N_BOOT) -> dict:
    """Every forecast in df against both baselines, with its level (forecasts / spill-days), and
    reliability and wet / dry days for the `main` arm."""
    sc = hw.Scorer(df, n_boot)
    refs = {"earlier_years": df[EARLIER].to_numpy(), "flat": df[FLAT].to_numpy()}
    out = {"overflows": sc.ns, "weeks": sc.nw, "rows": len(df), "spill_days": int(sc.y.sum()),
           "base_rate": float(sc.y.mean()), "forecasts": {}}
    for k in [SCOT, CALIB, DEFAULT, PROD, EARLIER, FLAT]:
        if k in df and df[k].notna().all():
            p = df[k].to_numpy()
            out["forecasts"][k] = {**sc.summary(p, refs, auc_ci=k in (SCOT, DEFAULT, CALIB)),
                                   "level": float(p.sum() / max(sc.y.sum(), 1))}
    out["reliability"] = hw._reliability(sc.y, df[main].to_numpy())
    out["wet_dry"] = {}
    for name, mask in (("wet", df["wet"].to_numpy()), ("dry", ~df["wet"].to_numpy())):
        sub = df[mask]
        if sub.empty or sub["y"].nunique() < 2:
            continue
        r = {"earlier_years": sub[EARLIER].to_numpy(), "flat": np.full(len(sub), sub["y"].mean())}
        out["wet_dry"][name] = {"rows": len(sub), "spill_days": int(sub["y"].sum()),
                                "base_rate": float(sub["y"].mean()),
                                main: hw.Scorer(sub, n_boot).summary(sub[main].to_numpy(), r, auc_ci=False)}
    return out


def score_groups(df: pd.DataFrame, col: str, arm: str, n_boot: int = N_BOOT) -> dict:
    """The arm against earlier years within each group of `col`. Groups under GROUP_MIN_SITES
    overflows, or with one outcome only, are counted, not scored; "small" marks groups under the
    gate's MIN_SITES or MIN_SPILL_DAYS."""
    out = {}
    for name, sub in df.groupby(col):
        n, k = int(sub["site_id"].nunique()), int(sub["y"].sum())
        r = {"overflows": n, "spill_days": k, "rows": len(sub)}
        if n >= GROUP_MIN_SITES and sub["y"].nunique() == 2:
            r.update(hw.Scorer(sub, n_boot).summary(sub[arm].to_numpy(),
                                                    {"earlier_years": sub[EARLIER].to_numpy()}, auc_ci=False))
            r["small"] = bool(n < MIN_SITES or k < MIN_SPILL_DAYS)
        out[str(name)] = r
    return out


def score_leads(df: pd.DataFrame, daily_lead: dict[int, pd.DataFrame], model: SpillModel,
                n_boot: int = N_BOOT) -> dict:
    """G2 to G4: the Scottish-covariates arm on G's LEAD_YEAR rows at leads 0 to 3."""
    d = df[df["year"] == LEAD_YEAR]
    if not daily_lead or d.empty:
        return {str(k): {"tested": False, "why": "no archived forecasts"} for k in GATE_LEADS}
    out = {}
    for k in [0, *GATE_LEADS]:
        dk = hw.with_lead(d, daily_lead, k)
        dk = dk[dk["rain_d"].notna()]
        n_sites, n_sd = int(dk["site_id"].nunique()), int(dk["y"].sum())
        r = {"overflows": n_sites, "rows": len(dk), "spill_days": n_sd}
        if n_sites < LEAD_MIN_SITES or n_sd < LEAD_MIN_SPILL_DAYS:
            r.update(tested=False, why=f"below {LEAD_MIN_SITES} overflows or {LEAD_MIN_SPILL_DAYS} spill-days")
        else:
            p = model.predict_pooled(hw.features(dk))
            s = hw.Scorer(dk, n_boot).summary(p, {"earlier_years": dk[EARLIER].to_numpy()}, auc_ci=False)
            r.update(tested=True, **s, level=float(p.sum() / max(n_sd, 1)))
            r["passes"] = bool(s["bss_vs_earlier_years_ci"][0] > 0)
        out[str(k)] = r
    return out


def gate(results: dict) -> dict:
    """Gate A from the module docstring, applied to set G's results."""
    g = results.get("G") or {}
    parts = {}
    lead0 = ((g.get("scores") or {}).get("forecasts") or {}).get(SCOT)
    info = g.get("info") or {}
    if not lead0 or info.get("overflows", 0) < MIN_SITES or info.get("spill_days", 0) < MIN_SPILL_DAYS:
        parts["G1 lead 0"] = {"tested": False}
    else:
        ci = lead0["bss_vs_earlier_years_ci"]
        parts["G1 lead 0"] = {"tested": True, "bss": lead0["bss_vs_earlier_years"], "ci": ci,
                              "passes": bool(ci[0] > 0)}
    leads = g.get("leads") or {}
    for i, k in enumerate(GATE_LEADS, start=2):
        lk = leads.get(str(k)) or {"tested": False}
        parts[f"G{i} lead {k}"] = ({"tested": True, "bss": lk["bss_vs_earlier_years"],
                                    "ci": lk["bss_vs_earlier_years_ci"], "passes": lk["passes"]}
                                   if lk.get("tested") else {"tested": False, "why": lk.get("why")})
    tested = [p for p in parts.values() if p["tested"]]
    if any(not p["passes"] for p in tested):
        verdict = "FAIL"
    elif len(tested) == len(parts):
        verdict = "PASS"
    else:
        verdict = "NOT COMPLETE"
    return {"verdict": verdict, "parts": parts}


# ---------------------------------------------------------------------------
# Inputs, coverage and the run
# ---------------------------------------------------------------------------

def authorities(api_path: Path) -> dict[str, str]:
    """ASSET_ID -> LOCAL_AUTHORITY_NAME from S1's cached API answer (nothing is fetched)."""
    if not api_path.exists():
        return {}
    rows = json.loads(api_path.read_text()).get("results") or []
    return {str(r["ASSET_ID"]).strip(): (str(r.get("LOCAL_AUTHORITY_NAME") or "").strip() or "not given")
            for r in rows if r.get("ASSET_ID")}


def read_tiers(path: Path) -> dict[Key, int]:
    if not path.exists():
        return {}
    cy = pd.read_csv(path)
    return {(float(a), float(b), int(y)): int(t)
            for a, b, y, t in zip(cy["cell_lat"], cy["cell_lon"], cy["year"], cy["tier"], strict=True)}


def coverage(oy: pd.DataFrame, lab: pd.DataFrame, tiers: dict[Key, int]) -> dict:
    """What the dry run reports: overflows, labelled overflow-years, the sets, and the rain each part
    needs against what is cached. Counts only; no forecast is made."""
    g, n = oy[oy["set"] == "G"], oy[oy["set"] == "N"]
    need_g = rain_needs(g)
    need_fit = rain_needs(fit_years(oy, g)) - need_g
    need_n = rain_needs(n) - need_g - need_fit
    leads = lead_needs(g)
    lead_miss = missing("leads", leads)
    lab_g = lab.assign(year=lab["day"].dt.year).merge(g[["site_id", "year"]], on=["site_id", "year"])
    rows = {}
    for y, d in oy.groupby("year"):
        rows[str(y)] = {"overflows": len(d), "counted": int(d["counted"].sum()),
                        "counted_emergency_left_out": int((d["counted"] & d["emergency"]).sum()),
                        "eligible": int(d["eligible"].sum()), "G": int((d["set"] == "G").sum()),
                        "N": int((d["set"] == "N").sum())}
    return {
        "overflows_in_s2": int(oy["site_id"].nunique()),
        "overflows_with_a_count": int(oy.loc[oy["counted"], "site_id"].nunique()),
        "overflows_emergency": int(oy.loc[oy["emergency"], "site_id"].nunique()),
        "overflows_no_position": int(oy.loc[oy["lat"].isna(), "site_id"].nunique()),
        "overflow_years_by_year": rows,
        "G": {"overflows": int(g["site_id"].nunique()), "overflow_years": len(g), "spill_days": len(lab_g),
              "spill_days_by_year": {str(k): int(v) for k, v in lab_g.groupby("year").size().items()}},
        "N": {"overflows": int(n["site_id"].nunique()), "overflow_years": len(n)},
        "rain_archive": {"G (required)": by_tier(need_g, tiers),
                         "calibration arm, extra": by_tier(need_fit, tiers),
                         "N, extra": by_tier(need_n, tiers)},
        "rain_leads_2025": {"cells": len(leads), "cached": len(leads) - len(lead_miss), "missing": len(lead_miss),
                            "calls_left": round(lead_calls_for(lead_miss)),
                            "requests_left": int(np.ceil(len(lead_miss) / LEADS_PER_REQUEST))},
    }


def _daily_leads(keys: set[Key]) -> dict[int, pd.DataFrame]:
    leads = load_rain("leads", keys)
    if leads.empty:
        return {}
    return {k: daily_rain_features(leads[leads["lead"] == k].drop(columns="lead")) for k in [0, *GATE_LEADS]}


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    df[FLAT] = df["y"].mean()
    df["wet"] = (df["rain_d"].fillna(0) + df["rain_d1"].fillna(0)) > WET_MM
    return df


def _set_rows(oy, cov, lab, daily, which, models) -> pd.DataFrame:
    frames = [year_rows(oy, cov, lab, daily, y, which, models).assign(year=y) for y in TEST_YEARS]
    frames = [f for f in frames if len(f)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def run(oy: pd.DataFrame, cov: pd.DataFrame, lab: pd.DataFrame, models: dict, n_boot: int = N_BOOT,
        without_leads: bool = False) -> dict:
    """Score sets G and N. Stops (SystemExit), scoring nothing, unless G's rain is all cached."""
    g, n = oy[oy["set"] == "G"], oy[oy["set"] == "N"]
    need_g, lead_keys = rain_needs(g), lead_needs(g)
    miss_g, miss_l = missing("archive", need_g), missing("leads", lead_keys)
    why = []
    if miss_g:
        why.append(f"{len(miss_g)} of {len(need_g)} archive cell-years G needs are not cached "
                   f"(about {archive_calls_for(miss_g):.0f} calls); run scripts/fetch_scotland_history.py until they are")
    if miss_l and not without_leads:
        why.append(f"{len(miss_l)} of {len(lead_keys)} {LEAD_YEAR} archived-forecast files G needs are not cached "
                   f"(about {lead_calls_for(miss_l):.0f} calls); fetch them with --fetch-leads --max-calls N, "
                   "or score lead 0 only with --without-leads")
    if why:
        raise SystemExit("Not scoring: " + "; ".join(why) + ".")
    need_fit, need_n = rain_needs(fit_years(oy, g)), rain_needs(n)
    miss_fit, miss_n = missing("archive", need_fit), missing("archive", need_n)
    use = need_g | (need_fit if not miss_fit else set()) | (need_n if not miss_n else set())
    daily = daily_rain_features(load_rain("archive", use))
    log.info("rain: %d cell-years loaded", len(use))

    results: dict = {}
    gdf = _set_rows(oy, cov, lab, daily, "G", models)
    info = {"rain_cell_years": len(need_g),
            "calibration": "run" if not miss_fit else f"not run: {len(miss_fit)} of {len(need_fit)} cell-years not cached"}
    if gdf.empty or gdf["y"].nunique() < 2:
        results["G"] = {"info": {**info, "overflows": 0, "spill_days": 0}, "untested": "no scored rows with both outcomes"}
    else:
        if not miss_fit:
            gdf[CALIB] = calibration(oy, cov, lab, daily, gdf, models["holdout"])
        gdf = _finish(gdf)
        info.update(overflows=int(gdf["site_id"].nunique()), rows=len(gdf), spill_days=int(gdf["y"].sum()))
        log.info("G: %d overflows, %d rows, %d spill-days", info["overflows"], len(gdf), info["spill_days"])
        results["G"] = {
            "info": info, "scores": score_rows(gdf, SCOT, n_boot),
            "by_year": score_groups(gdf, "year", SCOT, n_boot),
            "by_type": score_groups(gdf, "type", SCOT, n_boot),
            "by_authority": score_groups(gdf, "authority", SCOT, n_boot),
            "leads": ({str(k): {"tested": False, "why": "--without-leads"} for k in GATE_LEADS} if without_leads
                      else score_leads(gdf, _daily_leads(lead_keys), models["holdout"], n_boot)),
        }
    if miss_n:
        results["N"] = {"not_run": f"{len(miss_n)} of {len(need_n)} cell-years not cached"}
    else:
        ndf = _set_rows(oy, cov, lab, daily, "N", models)
        if ndf.empty or ndf["y"].nunique() < 2:
            results["N"] = {"untested": "no scored rows with both outcomes"}
        else:
            ndf = _finish(ndf)
            results["N"] = {"scores": score_rows(ndf, DEFAULT, n_boot),
                            "by_year": score_groups(ndf, "year", DEFAULT, n_boot)}
    return results


# ---------------------------------------------------------------------------
# --fetch-leads: the only path that calls Open-Meteo
# ---------------------------------------------------------------------------

def fetch_leads_strict(chunk: list[tuple[float, float]], year: int) -> None:
    """One previous-runs request, written as ingest/rainfall_leads.fetch_leads writes its files, but
    a 429 is not retried and any failure raises (fetch_leads logs it and goes on)."""
    from dipcast.ingest import rainfall_leads
    from dipcast.ingest.rainfall import _request
    end = min(pd.Timestamp(f"{year}-12-31"), pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=2))
    params = {"latitude": ",".join(f"{c[0]:.3f}" for c in chunk), "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
              "start_date": f"{year}-01-01", "end_date": end.strftime("%Y-%m-%d"),
              "hourly": ",".join(rainfall_leads.VARS), "timezone": "UTC"}
    res = _request(rainfall_leads.PREVIOUS_RUNS, params, retry_429=False)
    for (cl, cn), r in zip(chunk, res if isinstance(res, list) else [res], strict=True):
        t = pd.to_datetime(r["hourly"]["time"], utc=True)
        df = pd.concat([pd.DataFrame({"cell_lat": cl, "cell_lon": cn, "time": t, "lead": lead,
                                      "precip_mm": np.asarray(r["hourly"][var], dtype=float)})
                        for lead, var in zip(rainfall_leads.LEADS, rainfall_leads.VARS, strict=True)],
                       ignore_index=True)
        p = rain_path("leads", (cl, cn, year))
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p, index=False)


def fetch_leads_paced(keys: set[Key], max_calls: float, per_hour: float,
                      fetch: Callable = fetch_leads_strict, sleep: Callable[[float], None] = time.sleep,
                      clock: Callable[[], float] = time.monotonic) -> dict:
    """Fetch the missing lead files in `keys`, LEADS_PER_REQUEST cells a request, spaced to stay under
    `per_hour` calls. Stops before `max_calls`, at the first request that raises, or at one whose
    files are still missing after it."""
    todo = sorted(missing("leads", keys))
    done = {"requests": 0, "calls": 0.0, "files": 0, "stopped": None}
    next_at = clock()
    for i in range(0, len(todo), LEADS_PER_REQUEST):
        chunk = todo[i:i + LEADS_PER_REQUEST]
        calls = lead_calls_for(set(chunk))
        if done["calls"] + calls > max_calls:
            done["stopped"] = f"budget: {done['calls']:.0f} of {max_calls:.0f} calls used"
            return done
        wait = next_at - clock()
        if wait > 0:
            sleep(wait)
        done["requests"] += 1
        done["calls"] += calls          # a refused request may still count against the quota
        try:
            fetch([(a, b) for a, b, _ in chunk], chunk[0][2])
        except Exception as e:  # noqa: BLE001 - any failure ends the run
            done["stopped"] = f"refused: {e}"
            return done
        next_at = clock() + 3600 * calls / per_hour
        left = missing("leads", set(chunk))
        done["files"] += len(chunk) - len(left)
        if left:
            done["stopped"] = f"refused: {len(left)} files still missing"
            return done
    return done


def load_inputs(events: Path, covariates: Path, api: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ev, cov = pd.read_parquet(events), pd.read_parquet(covariates)
    return overflow_years(cov, emergency_by_name(ev), authorities(api)), cov, labels(ev)


def main(argv: list[str] | None = None, models: dict | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--events", type=Path, default=EVENTS)
    ap.add_argument("--covariates", type=Path, default=COVARIATES)
    ap.add_argument("--cells", type=Path, default=CELLS, help="S2's cell list, for the fetch tiers")
    ap.add_argument("--api-answer", type=Path, default=API_ANSWER, help="S1's cached API answer, for local authorities")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--dry-run", action="store_true", help="coverage only: no forecast, no score, nothing written")
    ap.add_argument("--without-leads", action="store_true", help="score lead 0 only; G2 to G4 untested")
    ap.add_argument("--fetch-leads", action="store_true", help="fetch G's missing 2025 lead files from Open-Meteo")
    ap.add_argument("--max-calls", type=float, default=0, help="Open-Meteo calls --fetch-leads may use")
    ap.add_argument("--per-hour", type=float, default=3000, help="Open-Meteo calls an hour for --fetch-leads")
    args = ap.parse_args(argv)

    oy, cov, lab = load_inputs(args.events, args.covariates, args.api_answer)
    cv = coverage(oy, lab, read_tiers(args.cells))
    if args.dry_run:
        print(json.dumps(hw.clean(cv), indent=1))
        return {"coverage": cv}
    if args.fetch_leads:
        if args.max_calls <= 0:
            raise SystemExit("--fetch-leads needs --max-calls (Open-Meteo allows 10,000 a day per IP)")
        done = fetch_leads_paced(lead_needs(oy[oy["set"] == "G"]), args.max_calls, args.per_hour)
        print(json.dumps(done, indent=1))
        return {"fetch_leads": done}

    if models is None:
        models = {"holdout": SpillModel.load(MODEL)}
        if PRODUCTION.exists():
            models["production"] = SpillModel.load(PRODUCTION)
    results = run(oy, cov, lab, models, args.n_boot, args.without_leads)
    out = {
        "written": pd.Timestamp.now("UTC").date().isoformat(),
        "what": "Scotland hindcast, Stage A (docs/SCOTLAND-PLAN-2026-10.md, section 6; "
                "scripts/hindcast_scotland.py). Summary scores only; no Scottish Water rows.",
        "model": models["holdout"].trained_on, "model_file": MODEL.name,
        "production_model": models["production"].trained_on if "production" in models else None,
        "bootstrap": {"draws": args.n_boot, "seed": SEED, "clusters": "overflows x ISO weeks"},
        "sources": {"events": sw_history.CREDIT,
                    "rain": "ERA5-Land via Open-Meteo (cached); archived forecasts via Open-Meteo previous-runs API"},
        "coverage": cv, **results,
    }
    out["gate"] = gate(results)
    out = hw.clean(out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1))
    log.info("Gate A: %s -> %s", out["gate"]["verdict"], args.out)
    print(json.dumps(out["gate"], indent=1))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main(sys.argv[1:])
