"""Wales hindcast, Stage A (task W4 of docs/WALES-PLAN-2026-10.md, section 6). Off CI; publishes nothing.

A hindcast is a forecast made after the fact with the rain that fell, scored against what the
overflows did. This script applies the English spill model, unchanged, to overflows run by Dŵr
Cymru Welsh Water and Hafren Dyfrdwy, and writes a summary of scores (no rows) to
data/processed/wales_hindcast.json.

    DIPCAST_CACHE=<shared cache> uv run python scripts/hindcast_wales.py \
        --wales-annual <W2>/wales_annual.parquet --hd-events <W3>/hd_events.parquet \
        --dcww-events <W3>/dcww_ea_events.parquet

It reads rain only from the cache (ERA5-Land archive_*.parquet and archived forecasts
leads_*.parquet) and fetches nothing.

GATE A
======

Written 4 October 2026, before the first run on real data, and committed on its own before that
run. It is not to be changed after any result is seen. A different rule would be a new, dated rule
beside this one, and the write-up would report both.

Model. Layer 1 (the pooled model) of data/processed/spill_model_holdout_2025.pkl: trained by
scripts/train.py on United Utilities' discharges of 2023 and 2024, and not refitted. No Welsh or Dŵr
Cymru overflow has a site offset, so predict_pooled is used throughout. The production model
(spill_model.pkl, refitted on 2023 to 2025) is scored beside it as a check and has no part in the
gate.

Rain. ERA5-Land hourly rain per 0.1 degree cell, days in UTC, features from
model/features.daily_rain_features, exactly as train.py builds them. Rows whose day has no rain
total are dropped, as in train.py. "Lead 0" in this gate means this rain, the rain that fell.
"Leads 1, 2 and 3" mean Open-Meteo's archived forecasts, built as scripts/verify_leads.py builds
them (the target day and the two days before from the forecast, longer windows from ERA5-Land),
and only for cells whose forecasts are already in the cache.

Test sets (plan, section 6):

- A1, Hafren Dyfrdwy, 2025. Discharges: Hafren Dyfrdwy's 2025 file (CC BY 4.0). Overflows: Hafren
  Dyfrdwy's rows in the 2024 return of wales_annual.parquet (covariates from the year before, as
  train.py), with a position. Each discharge site is joined to the nearest return overflow within
  MATCH_M (200 m), nearest pairs first, one to one.
- A2, Dŵr Cymru's English overflows, 2024 and 2025 pooled. Discharges: the Environment Agency's
  event files for Welsh Water (Open Government Licence). Overflows: Dŵr Cymru's rows in the EA
  annual return of the year before. Discharge sites are joined by site id, then by position as in A1.
- A3, Dŵr Cymru's overflows in Wales, 2025, as yearly totals. Overflows: Dŵr Cymru's rows in
  wales_annual.parquet with country "Wales", a 2024 return, a 2025 counted spill figure and 2025
  monitor uptime of at least 90%.

In all three: emergency overflows are left out (plan 5.2: they do not spill because of rain). So is
an overflow whose outlet and asset positions differ by more than 5 km (W2's outlet_asset_m), whose
rain cell is in doubt. In A1 and A2, a site-year whose same-year monitor uptime is below 50% is left
out, as train.py does; unknown uptime is kept. A return overflow joined to no discharge site is kept
with no spill-days only if its same-year return counts 0 spills; otherwise its discharges cannot be
found, and it is left out. A discharge site joined to no return overflow is left out and counted.
A label is a spill-day: a UTC day touched by a discharge (features.spill_days).

Arms. "Own covariates", the arm the gate is about: lta_spills, spill_hours and
edm_operational_pct from the return of the year before (W2's long-term average rule for Hafren
Dyfrdwy and for A3; the EA's values for A2). "Default covariates": all three missing, so
features.site_static_features gives every overflow 20 spills, 100 hours and 90%.

Baselines. "Year before": each overflow's counted spills in the return of the year before, times
SPILL_DAYS_PER_SPILL (1.004, United Utilities, data/processed/spill_day_ratio.json), over 365, cut to
0.001 to 0.95, as one probability for every day; an overflow with no count takes the median of the
set's others. "Flat": the test set's own spill-day rate on every row (it uses the answer, so it is a
hard baseline for skill, as the accuracy page shows it).

Scores. Brier score; Brier skill score (BSS) = 1 - Brier(model) / Brier(baseline); log loss; AUC;
reliability by tenths; wet days (rain_d + rain_d1 > 10 mm) and dry days apart. Intervals: a cluster
bootstrap that resamples overflows and ISO weeks together (rows weighted by the product of the
overflow's and the week's draw counts), 2,000 draws, seed 0, 95% percentile intervals. A3 resamples
overflows only.

Pass rule.

- G1. A1 at lead 0: the lower end of the 95% interval of BSS (own covariates against the
  year-before baseline) is above zero.
- G2. A2 at lead 0: the same.
- G3. A1 and A2 at leads 1, 2 and 3, each lead separately: the same, on the rows whose cell has
  archived forecasts. A set's lead test runs only if those rows hold at least LEAD_MIN_SITES (20)
  overflows and LEAD_MIN_SPILL_DAYS (200) spill-days; otherwise it is untested.
- A set with fewer than MIN_SITES (10) overflows or MIN_SPILL_DAYS (100) spill-days at lead 0 is
  untested.

Verdict: FAIL if any tested part fails. PASS if every part is tested and passes. NOT COMPLETE if no
tested part fails and some part is untested; that is not a pass, and the Welsh spill forecast does
not go ahead on it.

A3 is reported, not gated (plan, section 6). R = (sum of expected spill-days) / (1.004 x sum of
counted spills), for the own-covariates arm. If R is outside 1/1.5 to 1.5, the model's level is
wrong for Dŵr Cymru, and Stage B must show otherwise before any release. Expected spill-days for an
overflow are the mean daily probability over its 2025 days with rain, times 365; an overflow with
rain on fewer than 360 days is left out. Spearman's rank correlation between expected spill-days
and counted spills is reported beside R, for the model and for the year-before count.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

from dipcast import config
from dipcast.ingest.rainfall import cell_key, grid_cell
from dipcast.model.features import ALL_FEATURES, build_site_days, daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel
from dipcast.model.verify import reliability_table

log = logging.getLogger("hindcast_wales")

MODEL = config.PROCESSED / "spill_model_holdout_2025.pkl"
PRODUCTION = config.PROCESSED / "spill_model.pkl"
OUT = config.PROCESSED / "wales_hindcast.json"
DWR_CYMRU = "Dwr Cymru Welsh Water"
HAFREN_DYFRDWY = "Hafren Dyfrdwy"

MATCH_M = 200.0
MAX_OUTLET_ASSET_M = 5000.0
MIN_EDM_PCT = 50.0
A3_MIN_UPTIME = 90.0
A3_MIN_RAIN_DAYS = 360
WET_MM = 10.0
BASE_CLIP = (0.001, 0.95)
N_BOOT = 2000
SEED = 0
MIN_SITES, MIN_SPILL_DAYS = 10, 100
LEAD_MIN_SITES, LEAD_MIN_SPILL_DAYS = 20, 200
LEVEL_BAND = 1.5
GATE_LEADS = [1, 2, 3]
EMERGENCY = r"\bEO\b|Emergency"

OWN, DEFAULT, PROD, BEFORE, FLAT = ("own covariates", "default covariates", "production model, own covariates",
                                    "year before", "flat")
COV = ["lta_spills", "spill_hours", "edm_operational_pct"]
_TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)


def spill_days_per_spill() -> float:
    p = config.PROCESSED / "spill_day_ratio.json"
    return float(json.loads(p.read_text())["spill_days_per_spill"]) if p.exists() else 1.004


# ---------------------------------------------------------------------------
# Joining discharge sites to return overflows
# ---------------------------------------------------------------------------

def match_by_position(a: pd.DataFrame, b: pd.DataFrame, max_m: float = MATCH_M) -> pd.DataFrame:
    """Pairs (a_id, b_id, dist_m): each row of `a` to the nearest row of `b` within max_m, nearest
    pairs first, one to one. Both need site_id, lat and lon."""
    a = a.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    b = b.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    if a.empty or b.empty:
        return pd.DataFrame(columns=["a_id", "b_id", "dist_m"])
    ax, ay = _TO_BNG.transform(a["lon"].to_numpy(), a["lat"].to_numpy())
    bx, by = _TO_BNG.transform(b["lon"].to_numpy(), b["lat"].to_numpy())
    tree = cKDTree(np.c_[bx, by])
    k = min(5, len(b))
    d, j = tree.query(np.c_[ax, ay], k=k, distance_upper_bound=max_m)
    d, j = np.asarray(d).reshape(len(a), k), np.asarray(j).reshape(len(a), k)
    cand = [(d[i, c], i, j[i, c]) for i in range(len(a)) for c in range(k) if np.isfinite(d[i, c])]
    used_a, used_b, rows = set(), set(), []
    for dist, i, jj in sorted(cand):
        if i in used_a or jj in used_b:
            continue
        used_a.add(i)
        used_b.add(jj)
        rows.append((a.at[i, "site_id"], b.at[jj, "site_id"], float(dist)))
    return pd.DataFrame(rows, columns=["a_id", "b_id", "dist_m"])


def link_events(events: pd.DataFrame, overflows: pd.DataFrame, max_m: float = MATCH_M) -> tuple[pd.DataFrame, dict]:
    """Events with site_id rewritten to the return overflow's id: by id where the ids agree, else by
    position (match_by_position). Events whose site joins nothing are dropped and counted."""
    sites = events.groupby("site_id", as_index=False)[["lat", "lon"]].first()
    known = set(overflows["site_id"])
    by_id = sites[sites["site_id"].isin(known)]
    rest = sites[~sites["site_id"].isin(known)]
    free = overflows[~overflows["site_id"].isin(set(by_id["site_id"]))]
    pos = match_by_position(rest, free, max_m)
    mapping = dict(zip(by_id["site_id"], by_id["site_id"], strict=True))
    mapping.update(dict(zip(pos["a_id"], pos["b_id"], strict=True)))
    ev = events.assign(site_id=events["site_id"].map(mapping)).dropna(subset=["site_id"])
    info = {"event_sites": len(sites), "joined_by_id": len(by_id), "joined_by_position": len(pos),
            "unjoined_sites": int(len(sites) - len(by_id) - len(pos)),
            "events": len(events), "events_joined": len(ev),
            "max_join_m": float(pos["dist_m"].max()) if len(pos) else None}
    return ev, info


# ---------------------------------------------------------------------------
# Rain
# ---------------------------------------------------------------------------

def cells_of(sites: pd.DataFrame) -> set[tuple[float, float]]:
    cl, cn = grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy())
    return {(float(a), float(b)) for a, b in zip(cl, cn, strict=True)}


def load_cache(kind: str, cells: set[tuple[float, float]], years: list[int]) -> tuple[pd.DataFrame, dict]:
    """Rain files of `kind` ("archive" or "leads") for the cells and years that are cached, and the
    number of cells missing in each year."""
    frames, missing = [], {}
    for y in years:
        missing[str(y)] = 0
        for cl, cn in sorted(cells):
            p = config.CACHE / "rain" / f"{kind}_{cell_key(cl, cn)}_{y}.parquet"
            if p.exists():
                frames.append(pd.read_parquet(p))
            else:
                missing[str(y)] += 1
    cols = ["cell_lat", "cell_lon", "time", "precip_mm"] + (["lead"] if kind == "leads" else [])
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)), missing


def with_lead(base: pd.DataFrame, daily_lead: dict[int, pd.DataFrame], k: int) -> pd.DataFrame:
    """scripts/verify_leads.py's with_lead: the target day's rain and intensities and the two days
    before from the forecast at leads k, k-1, k-2 (floored at 0); longer windows stay ERA5-Land."""
    key = ["cell_lat", "cell_lon", "day"]
    df = base.drop(columns=["rain_d", "max1h_d", "max3h_d", "max6h_d"]).merge(
        daily_lead[k][key + ["rain_d", "max1h_d", "max3h_d", "max6h_d"]], on=key, how="left")
    for shift, col in ((1, "rain_d1"), (2, "rain_d2")):
        src = daily_lead[max(k - shift, 0)][key + ["rain_d"]].copy()
        src["day"] = src["day"] + pd.Timedelta(days=shift)
        df = df.drop(columns=[col]).merge(src.rename(columns={"rain_d": col}), on=key, how="left")
    df["rain_3d"] = df["rain_d"].fillna(0) + df["rain_d1"].fillna(0) + df["rain_d2"].fillna(0)
    return df


# ---------------------------------------------------------------------------
# Site-days, forecasts and baselines
# ---------------------------------------------------------------------------

def year_before_rate(prev_spills: pd.Series, ratio: float) -> pd.Series:
    r = prev_spills.astype(float) * ratio / 365.0
    r = r.fillna(r.median() if r.notna().any() else 20 * ratio / 365.0)
    return r.clip(*BASE_CLIP)


def site_days(sites: pd.DataFrame, daily: pd.DataFrame, year: int, labels: pd.DataFrame) -> pd.DataFrame:
    """train.py's site-day table for one year, rain-less days dropped, other gaps filled with 0
    as forecast.py and verify_leads.py fill them."""
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D", tz="UTC")
    sd = build_site_days(sites, daily, days, labels[labels["day"].dt.year == year])
    sd = sd[sd["rain_d"].notna()].copy()
    sd["year"] = year
    return sd


def features(df: pd.DataFrame) -> pd.DataFrame:
    return df.astype({f: np.float32 for f in ALL_FEATURES}).fillna({f: 0.0 for f in ALL_FEATURES})


def default_arm(sites: pd.DataFrame) -> pd.DataFrame:
    """The same overflows with no covariates, so site_static_features gives 20 / 100 / 90."""
    return sites.drop(columns=[c for c in COV + ["company"] if c in sites]).assign(
        **{c: np.nan for c in COV})


def build_event_set(sites: pd.DataFrame, events: pd.DataFrame, same_year: pd.DataFrame, years: list[int],
                    daily: pd.DataFrame, ratio: float, models: dict[str, SpillModel]) -> tuple[pd.DataFrame, dict]:
    """The scored rows of an event-level set (A1 or A2), one per overflow-day, with y, the forecasts
    of each arm and model, and the baselines.

    sites: one row per overflow and test year (site_id, year, lat, lon, company, covariates of the
    year before, prev_spills). same_year: site_id, year, spills, edm_operational_pct of the test
    year's own return."""
    ev, info = link_events(events, sites.drop_duplicates("site_id"))
    labels = spill_days(ev)
    frames = []
    dropped = {"no_events_but_spills": 0, "low_uptime_site_years": 0}
    for y in years:
        s = sites[sites["year"] == y].drop(columns="year")
        sy = same_year[same_year["year"] == y].set_index("site_id")
        have = set(labels.loc[labels["day"].dt.year == y, "site_id"])
        count = s["site_id"].map(sy["spills"]) if len(sy) else pd.Series(np.nan, index=s.index)
        keep = s["site_id"].isin(have) | (count == 0)
        dropped["no_events_but_spills"] += int((~keep).sum())
        up = s["site_id"].map(sy["edm_operational_pct"]) if len(sy) else pd.Series(np.nan, index=s.index)
        low = up < MIN_EDM_PCT
        dropped["low_uptime_site_years"] += int((keep & low).sum())
        s = s[keep & ~low]
        if s.empty:
            continue
        sd = site_days(s, daily, y, labels)
        X = features(sd)
        sd[OWN] = models["holdout"].predict_pooled(X)
        dd = features(site_days(default_arm(s), daily, y, labels))
        assert (dd["site_id"].to_numpy() == sd["site_id"].to_numpy()).all() and (dd["day"].to_numpy() == sd["day"].to_numpy()).all()
        sd[DEFAULT] = models["holdout"].predict_pooled(dd)
        if "production" in models:
            sd[PROD] = models["production"].predict_pooled(X)
        sd[BEFORE] = sd["site_id"].map(dict(zip(s["site_id"], year_before_rate(s["prev_spills"], ratio), strict=True)))
        frames.append(sd)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(df):
        df[FLAT] = df["y"].mean()
        df["wet"] = (df["rain_d"].fillna(0) + df["rain_d1"].fillna(0)) > WET_MM
    info.update(dropped)
    info["overflows"] = int(df["site_id"].nunique()) if len(df) else 0
    info["rows"] = len(df)
    info["spill_days"] = int(df["y"].sum()) if len(df) else 0
    return df, info


# ---------------------------------------------------------------------------
# Scores and the cluster bootstrap
# ---------------------------------------------------------------------------

def _week_ids(day: pd.Series) -> np.ndarray:
    iso = day.dt.isocalendar()
    return pd.factorize(iso["year"].astype(str) + "-" + iso["week"].astype(str))[0]


def boot_draws(n_sites: int, n_weeks: int, n_boot: int = N_BOOT, seed: int = SEED) -> tuple[np.ndarray, np.ndarray]:
    """Draw counts for overflows and weeks: each row of a and b is one bootstrap draw."""
    rng = np.random.default_rng(seed)
    a = rng.multinomial(n_sites, np.full(n_sites, 1 / n_sites), size=n_boot).astype(float)
    b = rng.multinomial(n_weeks, np.full(n_weeks, 1 / n_weeks), size=n_boot).astype(float) if n_weeks else np.ones((n_boot, 0))
    return a, b


def weighted_auc(y: np.ndarray, p: np.ndarray, w: np.ndarray | None = None,
                 groups: tuple[np.ndarray, int] | None = None) -> float:
    """AUC with row weights; tied forecasts count half. `groups`, (rank of each row's forecast
    among the distinct forecasts, number of distinct forecasts), saves sorting again."""
    w = np.ones(len(y)) if w is None else w
    if groups is None:
        g, inv = np.unique(p, return_inverse=True)
        groups = (inv, len(g))
    inv, ng = groups
    pos = np.bincount(inv, weights=w * (y == 1), minlength=ng)
    neg = np.bincount(inv, weights=w * (y == 0), minlength=ng)
    tp, tn = pos.sum(), neg.sum()
    if tp <= 0 or tn <= 0:
        return float("nan")
    below = np.cumsum(neg) - neg
    return float((pos * (below + 0.5 * neg)).sum() / (tp * tn))


class Scorer:
    """Point scores and two-way cluster-bootstrap intervals for one set of rows."""

    def __init__(self, df: pd.DataFrame, n_boot: int = N_BOOT, seed: int = SEED):
        self.df = df.reset_index(drop=True)
        self.y = self.df["y"].to_numpy().astype(float)
        self.s = pd.factorize(self.df["site_id"])[0]
        self.w = _week_ids(self.df["day"])
        self.ns, self.nw = int(self.s.max()) + 1, int(self.w.max()) + 1
        self.a, self.b = boot_draws(self.ns, self.nw, n_boot, seed)
        self.n = self._cells(np.ones(len(self.y)))

    def _cells(self, v: np.ndarray) -> np.ndarray:
        m = np.zeros((self.ns, self.nw))
        np.add.at(m, (self.s, self.w), v)
        return m

    def _boot(self, m: np.ndarray) -> np.ndarray:
        return np.einsum("bs,sw,bw->b", self.a, m, self.b)

    def brier_parts(self, p: np.ndarray) -> np.ndarray:
        return self._cells((p - self.y) ** 2)

    def summary(self, p: np.ndarray, refs: dict[str, np.ndarray], auc_ci: bool = True) -> dict:
        p = np.clip(p, 1e-6, 1 - 1e-6)
        se = self.brier_parts(p)
        ll = self._cells(-(self.y * np.log(p) + (1 - self.y) * np.log(1 - p)))
        nb = self._boot(self.n)
        out = {"brier": float(se.sum() / self.n.sum()), "log_loss": float(ll.sum() / self.n.sum()),
               "auc": weighted_auc(self.y, p)}
        out["brier_ci"] = _ci(self._boot(se) / nb)
        out["log_loss_ci"] = _ci(self._boot(ll) / nb)
        for name, r in refs.items():
            sr = self.brier_parts(np.clip(r, 1e-6, 1 - 1e-6))
            out[f"bss_vs_{name}"] = float(1 - se.sum() / sr.sum())
            out[f"bss_vs_{name}_ci"] = _ci(1 - self._boot(se) / self._boot(sr))
        if auc_ci:
            g, inv = np.unique(p, return_inverse=True)
            vals = [weighted_auc(self.y, p, self.a[i, self.s] * self.b[i, self.w], (inv, len(g)))
                    for i in range(len(self.a))]
            out["auc_ci"] = _ci(np.array(vals))
        return out


def _ci(v: np.ndarray) -> list[float]:
    v = v[np.isfinite(v)]
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))] if len(v) else [float("nan")] * 2


def _reliability(y: np.ndarray, p: np.ndarray) -> list[dict]:
    t = reliability_table(y, p)
    return [{"band": f"{r.lo:.1f}-{r.hi:.1f}", "n": int(r.n), "forecast": round(float(r.forecast), 4),
             "observed": round(float(r.observed), 4)} for r in t.itertuples()]


def score_set(df: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    """Every forecast in df scored against the year-before and flat baselines, plus reliability and
    wet / dry days for the own-covariates arm."""
    sc = Scorer(df, n_boot)
    refs = {"year_before": df[BEFORE].to_numpy(), "flat": df[FLAT].to_numpy()}
    out = {"overflows": sc.ns, "weeks": sc.nw, "rows": len(df), "spill_days": int(sc.y.sum()),
           "base_rate": float(sc.y.mean()), "forecasts": {}}
    for k in [OWN, DEFAULT, PROD, BEFORE, FLAT]:
        if k in df:
            out["forecasts"][k] = sc.summary(df[k].to_numpy(), refs, auc_ci=k in (OWN, DEFAULT))
    out["reliability_own"] = _reliability(sc.y, df[OWN].to_numpy())
    out["wet_dry"] = {}
    for name, mask in (("wet", df["wet"].to_numpy()), ("dry", ~df["wet"].to_numpy())):
        if mask.sum() == 0 or df.loc[mask, "y"].nunique() < 2:
            continue
        sub = df[mask]
        ss = Scorer(sub, n_boot)
        r = {"year_before": sub[BEFORE].to_numpy(), "flat": np.full(len(sub), sub["y"].mean())}
        out["wet_dry"][name] = {"rows": len(sub), "spill_days": int(sub["y"].sum()),
                                "base_rate": float(sub["y"].mean()),
                                OWN: ss.summary(sub[OWN].to_numpy(), r, auc_ci=False)}
    return out


def score_leads(df: pd.DataFrame, daily_lead: dict[int, pd.DataFrame], model: SpillModel,
                n_boot: int = N_BOOT) -> dict:
    """G3: the own-covariates arm at forecast leads, on the rows whose cell has archived forecasts."""
    out = {}
    if not daily_lead:
        return {str(k): {"tested": False, "why": "no archived forecasts cached for these cells"} for k in GATE_LEADS}
    for k in [0, *GATE_LEADS]:
        dk = with_lead(df, daily_lead, k)
        dk = dk[dk["rain_d"].notna()]
        n_sites, n_sd = int(dk["site_id"].nunique()), int(dk["y"].sum())
        r = {"overflows": n_sites, "rows": len(dk), "spill_days": n_sd}
        if n_sites < LEAD_MIN_SITES or n_sd < LEAD_MIN_SPILL_DAYS:
            r.update(tested=False, why=f"below {LEAD_MIN_SITES} overflows or {LEAD_MIN_SPILL_DAYS} spill-days")
        else:
            p = model.predict_pooled(features(dk))
            s = Scorer(dk, n_boot).summary(p, {"year_before": dk[BEFORE].to_numpy()}, auc_ci=False)
            r.update(tested=True, **s)
            r["passes"] = bool(s["bss_vs_year_before_ci"][0] > 0)
        out[str(k)] = r
    return out


# ---------------------------------------------------------------------------
# A3: yearly totals
# ---------------------------------------------------------------------------

def annual_totals(sites: pd.DataFrame, daily: pd.DataFrame, year: int, model: SpillModel) -> pd.DataFrame:
    """Per overflow: expected spill-days in `year` for each arm (mean daily probability over days
    with rain x 365), the days with rain, and the counted spills of the year and the year before.
    `sites` needs the covariates of the year before, spills (the year's own count) and prev_spills."""
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D", tz="UTC")
    out = sites[["site_id", "spills", "prev_spills"]].copy().set_index("site_id")
    for arm, s in ((OWN, sites), (DEFAULT, default_arm(sites))):
        sd = build_site_days(s, daily, days)
        sd = sd[sd["rain_d"].notna()]
        sd["p"] = model.predict_pooled(features(sd)) if len(sd) else []
        g = sd.groupby("site_id")["p"]
        out[arm] = g.mean() * 365
        out["rain_days"] = g.size()
    out["rain_days"] = out["rain_days"].fillna(0).astype(int)
    return out.reset_index()


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")      # a constant draw has no rank correlation: NaN, dropped
        return float(spearmanr(x, y).statistic) if len(x) > 2 else float("nan")


def score_annual(t: pd.DataFrame, ratio: float, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    t = t[t["rain_days"] >= A3_MIN_RAIN_DAYS].dropna(subset=["spills", OWN]).reset_index(drop=True)
    obs = ratio * t["spills"].to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(t), size=(n_boot, len(t))) if len(t) else np.zeros((n_boot, 0), dtype=int)
    out = {"overflows": len(t), "counted_spills_total": float(t["spills"].sum()),
           "observed_spill_days_estimate": float(obs.sum()), "counted_spills_mean": float(t["spills"].mean())}
    preds = {OWN: t[OWN].to_numpy(), DEFAULT: t[DEFAULT].to_numpy()}
    before = t["prev_spills"].to_numpy() * ratio
    ok_before = np.isfinite(before)
    for name, e in preds.items():
        rho = _spearman(e, obs)
        rb = [e[i].sum() / obs[i].sum() if obs[i].sum() > 0 else np.nan for i in idx]
        rhob = [_spearman(e[i], obs[i]) for i in idx]
        out[name] = {"expected_spill_days_total": float(e.sum()), "expected_mean": float(e.mean()),
                     "ratio": float(e.sum() / obs.sum()) if obs.sum() > 0 else float("nan"),
                     "ratio_ci": _ci(np.array(rb, dtype=float)), "spearman": float(rho),
                     "spearman_ci": _ci(np.array(rhob, dtype=float))}
    tb = t[ok_before]
    if len(tb) > 2:
        eb, ob = before[ok_before], obs[ok_before]
        out[BEFORE] = {"overflows": len(tb), "ratio": float(eb.sum() / ob.sum()),
                       "spearman": _spearman(eb, ob),
                       "spearman_model_same_overflows": _spearman(t.loc[ok_before, OWN].to_numpy(), ob)}
    r = out[OWN]["ratio"]
    out["level_ok"] = bool(1 / LEVEL_BAND <= r <= LEVEL_BAND) if np.isfinite(r) else None
    return out


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def gate(results: dict) -> dict:
    """Gate A from the module docstring, applied to the results of A1, A2 and A3."""
    parts = {}
    for name in ("A1", "A2"):
        r = results.get(name) or {}
        lead0 = (r.get("scores") or {}).get("forecasts", {}).get(OWN)
        info = r.get("info") or {}
        if not lead0 or info.get("overflows", 0) < MIN_SITES or info.get("spill_days", 0) < MIN_SPILL_DAYS:
            parts[f"{name} lead 0"] = {"tested": False}
        else:
            lo = lead0["bss_vs_year_before_ci"][0]
            parts[f"{name} lead 0"] = {"tested": True, "bss": lead0["bss_vs_year_before"],
                                       "ci": lead0["bss_vs_year_before_ci"], "passes": bool(lo > 0)}
        leads = r.get("leads") or {}
        for k in GATE_LEADS:
            lk = leads.get(str(k)) or {"tested": False}
            parts[f"{name} lead {k}"] = ({"tested": True, "bss": lk["bss_vs_year_before"],
                                          "ci": lk["bss_vs_year_before_ci"], "passes": lk["passes"]}
                                         if lk.get("tested") else {"tested": False, "why": lk.get("why")})
    tested = [p for p in parts.values() if p["tested"]]
    if any(not p["passes"] for p in tested):
        verdict = "FAIL"
    elif len(tested) == len(parts):
        verdict = "PASS"
    else:
        verdict = "NOT COMPLETE"
    a3 = (results.get("A3") or {}).get("scores") or {}
    return {"verdict": verdict, "parts": parts, "a3_level_ok": a3.get("level_ok"),
            "a3_ratio": (a3.get(OWN) or {}).get("ratio")}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def _emergency(s: pd.Series) -> pd.Series:
    return s.astype("string").str.contains(EMERGENCY, case=False, regex=True).fillna(False).astype(bool)


def wales_sites(wa: pd.DataFrame, company: str, year: int, country: str | None = None) -> pd.DataFrame:
    """Overflows of `company` in W2's table for a test year: covariates from year - 1 (as train.py),
    prev_spills from year - 1, and the test year's own spills and uptime. Emergency overflows and
    doubtful positions left out."""
    from dipcast.ingest import wales_annual
    w = wa[wa["company"] == company]
    cov = wales_annual.covariates(w, year - 1)
    prev = w[w["year"] == year - 1].set_index("site_id")
    own = w[w["year"] == year].set_index("site_id")
    pos = w.groupby("site_id")["outlet_asset_m"].max()
    s = cov[~cov["emergency"].astype(bool) & cov["lat"].notna()].copy()
    if country:
        s = s[s["country"] == country]
    s = s[~(s["site_id"].map(pos) > MAX_OUTLET_ASSET_M)]
    s["prev_spills"] = s["site_id"].map(prev["spills"])
    s["spills"] = s["site_id"].map(own["spills"])
    s["same_year_uptime"] = s["site_id"].map(own["edm_operational_pct"])
    s["year"] = year
    return s[["site_id", "year", "lat", "lon", "company", *COV, "prev_spills", "spills", "same_year_uptime"]]


def ea_sites(ar: pd.DataFrame, company: str, year: int) -> pd.DataFrame:
    """The same from the EA's annual returns, for Dŵr Cymru's overflows in England."""
    a = ar[(ar["company"] == company) & ar["site_id"].notna() & ar["year"].notna()].copy()
    a["year"] = a["year"].astype(int)
    a = a.sort_values("year").drop_duplicates(["site_id", "year"], keep="last")
    prev = a[a["year"] == year - 1]
    own = a[a["year"] == year].set_index("site_id")
    s = prev[prev["lat"].notna() & ~_emergency(prev["asset_type"])].copy()
    s["prev_spills"] = s["spills"]
    s["spills"] = s["site_id"].map(own["spills"])
    s["same_year_uptime"] = s["site_id"].map(own["edm_operational_pct"])
    s["year"] = year
    return s[["site_id", "year", "lat", "lon", "company", *COV, "prev_spills", "spills", "same_year_uptime"]]


def _same_year(sites: pd.DataFrame) -> pd.DataFrame:
    return sites[["site_id", "year", "spills", "same_year_uptime"]].rename(
        columns={"same_year_uptime": "edm_operational_pct"})


def _daily(cells: set, years: list[int]) -> tuple[pd.DataFrame, dict]:
    rain, missing = load_cache("archive", cells, years)
    info = {"cells": len(cells), "cells_missing_by_year": missing}
    return (daily_rain_features(rain) if len(rain) else pd.DataFrame()), info


def _daily_leads(cells: set, years: list[int]) -> tuple[dict[int, pd.DataFrame], dict]:
    leads, missing = load_cache("leads", cells, years)
    info = {"cells_with_forecasts": int(leads[["cell_lat", "cell_lon"]].drop_duplicates().shape[0]) if len(leads) else 0,
            "cells_missing_by_year": missing}
    if leads.empty:
        return {}, info
    return {k: daily_rain_features(leads[leads["lead"] == k].drop(columns="lead")) for k in [0, *GATE_LEADS]}, info


def run_event_set(name: str, sites: pd.DataFrame, events: pd.DataFrame, years: list[int], ratio: float,
                  models: dict[str, SpillModel], n_boot: int) -> dict:
    cells = cells_of(sites)
    daily, rinfo = _daily(cells, sorted({*years, *(y - 1 for y in years)}))
    if daily.empty:
        return {"info": {"rain": rinfo, "overflows": 0}, "untested": "no rain cached"}
    df, info = build_event_set(sites, events, _same_year(sites), years, daily, ratio, models)
    info["rain"] = rinfo
    res = {"info": info}
    if df.empty or df["y"].nunique() < 2:
        res["untested"] = "no scored rows with both outcomes"
        return res
    log.info("%s: %d overflows, %d rows, %d spill-days", name, info["overflows"], len(df), info["spill_days"])
    res["scores"] = score_set(df, n_boot)
    res["by_year"] = {}
    if len(years) > 1:
        for y in years:
            d = df[df["year"] == y]
            if len(d) and d["y"].nunique() == 2:
                sc = Scorer(d, n_boot)
                res["by_year"][str(y)] = {"overflows": sc.ns, "spill_days": int(sc.y.sum()),
                                          OWN: sc.summary(d[OWN].to_numpy(), {"year_before": d[BEFORE].to_numpy()},
                                                          auc_ci=False)}
    dl, linfo = _daily_leads(cells, years)
    res["leads"] = score_leads(df, dl, models["holdout"], n_boot)
    res["leads_info"] = linfo
    return res


def clean(o):
    """JSON-safe: numpy numbers to Python, NaN to None, floats to 5 significant figures."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(f"{float(o):.5g}")
    return o


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wales-annual", type=Path, default=config.PROCESSED / "wales_annual.parquet")
    ap.add_argument("--hd-events", type=Path, default=config.PROCESSED / "hd_events.parquet")
    ap.add_argument("--dcww-events", type=Path, default=config.PROCESSED / "dcww_ea_events.parquet")
    ap.add_argument("--annual-returns", type=Path, default=config.PROCESSED / "annual_returns.parquet")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    args = ap.parse_args(argv)

    ratio = spill_days_per_spill()
    models = {"holdout": SpillModel.load(MODEL)}
    if PRODUCTION.exists():
        models["production"] = SpillModel.load(PRODUCTION)
    wa = pd.read_parquet(args.wales_annual)
    ar = pd.read_parquet(args.annual_returns)
    results: dict = {}

    # A1: Hafren Dyfrdwy 2025
    hd = pd.read_parquet(args.hd_events) if args.hd_events.exists() else None
    if hd is None:
        results["A1"] = {"untested": f"missing {args.hd_events.name}"}
    else:
        results["A1"] = run_event_set("A1", wales_sites(wa, HAFREN_DYFRDWY, 2025), hd, [2025], ratio, models,
                                      args.n_boot)

    # A2: Dŵr Cymru's English overflows, 2024 and 2025, from the EA's event files
    dc = pd.read_parquet(args.dcww_events) if args.dcww_events.exists() else None
    if dc is None:
        results["A2"] = {"untested": f"missing {args.dcww_events.name}"}
    else:
        dc = dc[dc["event_start"].dt.year.isin([2024, 2025]) | dc["event_end"].dt.year.isin([2024, 2025])]
        sites = pd.concat([ea_sites(ar, DWR_CYMRU, y) for y in (2024, 2025)], ignore_index=True)
        results["A2"] = run_event_set("A2", sites, dc, [2024, 2025], ratio, models, args.n_boot)

    # A3: Dŵr Cymru's overflows in Wales, 2025, yearly totals
    s3 = wales_sites(wa, DWR_CYMRU, 2025, country="Wales")
    n_all = len(s3)
    s3 = s3[s3["spills"].notna() & (s3["same_year_uptime"] >= A3_MIN_UPTIME)]
    daily3, rinfo3 = _daily(cells_of(s3), [2024, 2025])
    if daily3.empty:
        results["A3"] = {"untested": "no rain cached", "info": {"rain": rinfo3}}
    else:
        t = annual_totals(s3, daily3, 2025, models["holdout"])
        results["A3"] = {"info": {"overflows_with_2024_return": n_all, "with_2025_count_and_uptime90": len(s3),
                                  "rain": rinfo3},
                         "scores": score_annual(t, ratio, args.n_boot)}

    out = {
        "written": pd.Timestamp.now("UTC").date().isoformat(),
        "what": "Wales hindcast, Stage A (docs/WALES-PLAN-2026-10.md, section 6; scripts/hindcast_wales.py). "
                "Summary scores only; no Dŵr Cymru or Hafren Dyfrdwy rows.",
        "model": models["holdout"].trained_on, "model_file": MODEL.name,
        "production_model": models["production"].trained_on if "production" in models else None,
        "spill_days_per_spill": ratio, "bootstrap": {"draws": args.n_boot, "seed": SEED,
                                                     "clusters": "overflows x ISO weeks (A3: overflows)"},
        "sources": {"A1": "Hafren Dyfrdwy Event Duration Monitoring 2025, Hafren Dyfrdwy, via Stream, CC BY 4.0",
                    "A2": "Environment Agency, Event Duration Monitoring - Storm Overflow - Start/Stop Detailed Data, "
                          "Welsh Water files; Open Government Licence v3; © Environment Agency copyright and/or "
                          "database right",
                    "covariates": "Dŵr Cymru annual-return layers and the Rivers Trust's compilations "
                                  "(wales_annual.parquet, task W2); EA annual returns for A2",
                    "rain": "ERA5-Land via Open-Meteo (cached); archived forecasts via Open-Meteo previous-runs API"},
        **results,
    }
    out["gate"] = gate(results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out = clean(out)
    args.out.write_text(json.dumps(out, indent=1))
    log.info("Gate A: %s -> %s", out["gate"]["verdict"], args.out)
    print(json.dumps(out["gate"], indent=1))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main(sys.argv[1:])
