"""The overflow's own recent spill status as an input to the spill model: a pre-stated test
(docs/LIVE-STATUS-FEATURE-TEST-2026-10.md). Off CI, by hand:

    uv run python scripts/live_status_test.py describe   # 2024 only: how spill status persists; nothing on 2025
    uv run python scripts/live_status_test.py run        # one candidate per lead, fitted on 2024, scored on 2025

The candidate is the nine-company model's layer 1 and layer 2 (scripts/train.py --nine, review task D2) with three
status inputs added, each known at the issue time, 00:00 UTC of day d-k for lead k. `run` needs D2's candidate,
spill_model_nine_2024.pkl (SHA-256 begins 1603678923cc), kept off-repo: put it in data/processed/ first.

The rain helpers (RainGrid, the lead window, boosted_features, the week bootstrap) are copied from
scripts/train_nn.py, so the lead rows and the forecast-rain features are built as that test built them.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.model import spill_model as sm
from dipcast.model.features import (
    ALL_FEATURES,
    API_DECAY,
    MIN_HOURS_PER_DAY,
    MONOTONE,
    RAIN_FEATURES,
    SEASON_FEATURES,
    SITE_FEATURES,
    daily_rain_features,
    spill_days,
)
from dipcast.model.spill_model import SpillModel
from dipcast.model.training import (
    MIN_EDM_PCT,
    NINE,
    RAIN_DIRS,
    cells_of,
    ece,
    load_events,
    load_rain,
    site_years,
)
from dipcast.model.verify import reliability_table, scores

sys.path.insert(0, str(Path(__file__).resolve().parent))
# D2's rows, built exactly as D2 built them (scripts/train.py main_nine).
from train import NINE_PATH, _frame

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True)
log = logging.getLogger("live_status_test")

STATUS = ["spilling_at_issue", "spill_hours_24h", "spill_days_7d"]
FEATURES = ALL_FEATURES + STATUS
STATIC = SEASON_FEATURES + SITE_FEATURES
LEADS = [0, 1, 2, 3, 4]
NEG_FRAC, PRIOR_STRENGTH, RECENCY = 0.25, 15.0, 1.0
N_BOOT = 2000
HOURS = 72
MIN_FINITE = int(np.ceil(0.9 * HOURS))     # train_nn.py's 90% rule: at least 65 of the 72 hours finite
DAY0 = pd.Timestamp("2024-01-01", tz="UTC")
N_DAYS = 731                               # 2024-01-01 .. 2025-12-31
DAYS_2024 = 366
DAY_S = 86_400
T0 = pd.Timestamp("2023-12-01", tz="UTC")  # load_rain's start
T_END = pd.Timestamp("2026-01-01", tz="UTC")
CANDIDATE_SHA = "1603678923cc"
OUT = config.PROCESSED / "live_status"
DOCS = config.ROOT / "docs" / "LIVE-STATUS-FEATURE-TEST-2026-10"
_T = time.time()


def step(msg: str) -> None:
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9   # bytes on macOS
    log.info("[%6.0fs, peak %5.1f GB] %s", time.time() - _T, rss, msg)


# ------------------------------------------------------------------ status
def covered_years(ar: pd.DataFrame, events: pd.DataFrame, years) -> dict[int, set]:
    """Per year, the overflows whose spill status that year is known: an event in the file that year, or 0 spills in
    that year's return, and EDM operation not under MIN_EDM_PCT. This is training.site_years' rule without its need
    for a position in the year before."""
    out = {}
    for y in years:
        same = ar[ar["company"].isin(NINE) & (ar["year"] == y)].drop_duplicates("site_id", keep="last").set_index("site_id")
        in_file = set(events.loc[events["event_start"].dt.year == y, "site_id"])
        zero = set(same.index[same["spills"].eq(0)])
        low = set(same.index[same["edm_operational_pct"].lt(MIN_EDM_PCT)])
        out[y] = (in_file | zero) - low
    return out


def merged_intervals(events: pd.DataFrame, sites: pd.Index) -> pd.DataFrame:
    """Each overflow's events with overlapping ones merged: i (site index), s and e (seconds from DAY0, e exclusive).
    The 2024 and 2025 files overlap at the new year at some companies (an event in the 2024 file runs past midnight
    and the 2025 file starts it again at 00:00), so merging keeps an hour from counting twice."""
    e = pd.DataFrame({"i": sites.get_indexer(events["site_id"]),
                      "s": (events["event_start"] - DAY0).dt.total_seconds().to_numpy(),
                      "e": (events["event_end"].fillna(events["event_start"]) - DAY0).dt.total_seconds().to_numpy()})
    e = e.sort_values(["i", "s"], kind="mergesort").reset_index(drop=True)
    prev = e.groupby("i")["e"].cummax().groupby(e["i"]).shift()
    group = (prev.isna() | (e["s"] > prev)).cumsum()
    return e.groupby(group).agg(i=("i", "first"), s=("s", "min"), e=("e", "max")).reset_index(drop=True)


class Status:
    """Each overflow's spill status per UTC day of 2024-25, from the EA start/stop events:
      now[i, m]    1 if a (merged) event runs at 00:00 UTC of day m: start <= 00:00 < stop
      hours[i, D]  hours spilled in day D, from the merged events, so at most 24
      sday[i, D]   1 if D is a spill-day, by features.spill_days (the label's own rule)
    and whether the status is known on a day (covered_years). Day 0 is 1 January 2024."""

    def __init__(self, events: pd.DataFrame, sites, covered: dict[int, set]):
        self.sites = pd.Index(sorted(set(sites) | set(events["site_id"])))
        n = len(self.sites)
        self.now = np.zeros((n, N_DAYS), np.float32)
        self.hours = np.zeros((n, N_DAYS), np.float32)
        sday = np.zeros((n, N_DAYS), np.float32)
        iv = merged_intervals(events, self.sites)
        self.n_intervals = len(iv)
        i, s, e = iv["i"].to_numpy(), iv["s"].to_numpy(), iv["e"].to_numpy()
        # 00:00 of day m with s <= m * DAY_S < e
        first, last = np.ceil(s / DAY_S).astype(np.int64), np.ceil(e / DAY_S).astype(np.int64) - 1
        k = np.clip(last - first + 1, 0, None)
        ii, mm = np.repeat(i, k), np.repeat(first, k) + _ranges(k)
        ok = (mm >= 0) & (mm < N_DAYS)
        self.now[ii[ok], mm[ok]] = 1.0
        # hours in day D: the overlap of [s, e) with [D, D + 1)
        pos = e > s
        i, s, e = i[pos], s[pos], e[pos]
        d0, d1 = np.floor(s / DAY_S).astype(np.int64), np.floor((e - 1e-6) / DAY_S).astype(np.int64)
        k = d1 - d0 + 1
        ii, dd = np.repeat(i, k), np.repeat(d0, k) + _ranges(k)
        ss, ee = np.repeat(s, k), np.repeat(e, k)
        hrs = (np.minimum(ee, (dd + 1) * DAY_S) - np.maximum(ss, dd * DAY_S)) / 3600.0
        ok = (dd >= 0) & (dd < N_DAYS)
        np.add.at(self.hours, (ii[ok], dd[ok]), hrs[ok])
        self.hours = np.minimum(self.hours, 24.0)
        lab = spill_days(events)
        li = self.sites.get_indexer(lab["site_id"])
        ld = ((lab["day"] - DAY0) // pd.Timedelta(days=1)).to_numpy()
        ok = (li >= 0) & (ld >= 0) & (ld < N_DAYS)
        sday[li[ok], ld[ok]] = 1.0
        self.sday = sday
        self.csum = np.concatenate([np.zeros((n, 1), np.float32), np.cumsum(sday, axis=1, dtype=np.float32)], axis=1)
        self.k24 = self.sites.isin(covered.get(2024, set()))
        self.k25 = self.sites.isin(covered.get(2025, set()))

    def known(self, i: np.ndarray, d: np.ndarray) -> np.ndarray:
        return (d >= 0) & np.where(d < DAYS_2024, self.k24[i], self.k25[i])

    def features(self, site_id: pd.Series, day: pd.Series, k: int) -> pd.DataFrame:
        """The three status inputs for rows (site_id, day d) at lead k, issued at 00:00 UTC of day d-k:
        spilling_at_issue (0/1), spill_hours_24h (hours in day d-k-1), spill_days_7d (spill-days among d-k-7 .. d-k-1).
        NaN where any day the input reads is not known."""
        i = self.sites.get_indexer(site_id)
        assert (i >= 0).all(), "a row's overflow has no status"
        d = ((day - DAY0) // pd.Timedelta(days=1)).to_numpy().astype(np.int64)
        m = d - k
        c = lambda a: np.clip(a, 0, None)   # index guard; the NaN mask decides
        now = np.where(self.known(i, m), self.now[i, c(m)], np.nan)
        h24 = np.where(self.known(i, m - 1), self.hours[i, c(m - 1)], np.nan)
        d7 = np.where(self.known(i, m - 7) & self.known(i, m - 1), self.csum[i, c(m)] - self.csum[i, c(m - 7)], np.nan)
        return pd.DataFrame({"spilling_at_issue": now, "spill_hours_24h": h24, "spill_days_7d": d7},
                            index=site_id.index).astype(np.float32)


def _ranges(k: np.ndarray) -> np.ndarray:
    """0 .. k_j - 1 for each j, concatenated."""
    if not len(k) or k.sum() == 0:
        return np.zeros(0, np.int64)
    starts = np.repeat(np.cumsum(k) - k, k)
    return np.arange(k.sum()) - starts


def run_lengths(sday: np.ndarray) -> np.ndarray:
    """For each spill-day in sday [n, days], the length of the run of consecutive spill-days it belongs to."""
    out = np.zeros_like(sday)
    for r in range(sday.shape[0]):
        row = sday[r]
        if not row.any():
            continue
        x = np.concatenate([[0], row, [0]])
        dif = np.diff(x)
        starts, ends = np.flatnonzero(dif == 1), np.flatnonzero(dif == -1)
        for a, b in zip(starts, ends, strict=True):
            out[r, a:b] = b - a
    return out


# ------------------------------------------------------------------ describe (2024 only)
def stage_describe() -> None:
    """How spill status persists in 2024, on the kept 2024 overflow-days (no rain filter). Nothing from 2025 is read:
    events are cut to those starting in 2024, and only 2024 days are tabulated."""
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    ev = ev[ev["event_start"] < pd.Timestamp("2025-01-01", tz="UTC")]
    s24, _ = site_years(ar, ev, NINE, 2024)
    cov = covered_years(ar, ev, [2024])
    st = Status(ev, s24["site_id"], cov)
    step(f"status: {len(st.sites)} overflows, {st.n_intervals} merged events (2024 file only)")
    days = pd.date_range("2024-01-01", "2024-12-31", freq="D", tz="UTC")
    rows = s24[["site_id", "company"]].merge(pd.DataFrame({"day": days}), how="cross")
    i = st.sites.get_indexer(rows["site_id"])
    d = ((rows["day"] - DAY0) // pd.Timedelta(days=1)).to_numpy()
    rows["y"] = st.sday[i, d]
    step(f"rows: {len(rows)} overflow-days, base rate {rows.y.mean():.4f}")

    out = []

    def add(group: str, k, subset: str, mask: np.ndarray, comp: str = "all nine"):
        y = rows["y"].to_numpy()[mask]
        out.append({"company": comp, "lead": k, "group": group, "subset": subset, "rows": int(mask.sum()),
                    "share_of_rows": float(mask.mean()), "spill_rate": float(y.mean()) if len(y) else np.nan})

    for k in LEADS:
        f = st.features(rows["site_id"], rows["day"], k)
        now, h, c7 = (f[c].to_numpy() for c in STATUS)
        add("all", k, "all rows", np.ones(len(rows), bool))
        add("spilling_at_issue", k, "1", now == 1)
        add("spilling_at_issue", k, "0", now == 0)
        add("spilling_at_issue", k, "unknown", np.isnan(now))
        add("spill_hours_24h", k, "0", h == 0)
        add("spill_hours_24h", k, "(0, 6]", (h > 0) & (h <= 6))
        add("spill_hours_24h", k, "(6, 24)", (h > 6) & (h < 24))
        add("spill_hours_24h", k, "24", h >= 24)
        add("spill_hours_24h", k, "unknown", np.isnan(h))
        for lo, hi, lab in ((0, 0, "0"), (1, 3, "1-3"), (4, 6, "4-6"), (7, 7, "7")):
            add("spill_days_7d", k, lab, (c7 >= lo) & (c7 <= hi))
        add("spill_days_7d", k, "unknown", np.isnan(c7))
        add("dry start", k, "not spilling at issue and 0 spill-days in 7", (now == 0) & (c7 == 0))
        if k in (0, 1):
            for comp in NINE:
                cm = (rows["company"] == comp).to_numpy()
                add("all", k, "all rows", cm, comp)
                add("spilling_at_issue", k, "1", cm & (now == 1), comp)
                add("spill_days_7d", k, "7", cm & (c7 == 7), comp)
                add("dry start", k, "not spilling at issue and 0 spill-days in 7", cm & (now == 0) & (c7 == 0), comp)
    t = pd.DataFrame(out)

    # Spill-days that continue a spell running at midnight (lead 0: the label is then certain), and spill-days in
    # runs of 7 or more consecutive days, per company.
    f0 = st.features(rows["site_id"], rows["day"], 0)
    runs = run_lengths(st.sday[:, :DAYS_2024])
    rows["run"] = runs[i, d]
    spells = []
    for comp in [*NINE, "all nine"]:
        cm = np.ones(len(rows), bool) if comp == "all nine" else (rows["company"] == comp).to_numpy()
        sp = cm & (rows["y"].to_numpy() == 1)
        spells.append({"company": comp, "overflow_days": int(cm.sum()), "spill_days": int(sp.sum()),
                       "base_rate": float(rows["y"].to_numpy()[cm].mean()),
                       "spill_days_running_at_midnight": float((f0["spilling_at_issue"].to_numpy()[sp] == 1).mean()),
                       "spill_days_in_runs_7plus": float((rows["run"].to_numpy()[sp] >= 7).mean()),
                       "spill_days_in_runs_30plus": float((rows["run"].to_numpy()[sp] >= 30).mean())})
    sp = pd.DataFrame(spells)
    pd.set_option("display.width", 220)
    print("\n=== 2024, spill rate by status at issue (all nine) ===")
    print(t[t.company == "all nine"].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\n=== 2024, per company, leads 0-1 ===")
    print(t[t.company != "all nine"].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\n=== 2024, spells ===")
    print(sp.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    t.to_csv(f"{DOCS}-persistence-2024.csv", index=False)
    sp.to_csv(f"{DOCS}-spells-2024.csv", index=False)
    step("2024 tables written")


# ------------------------------------------------------------------ rain (copied from scripts/train_nn.py)
def _key(lat, lon) -> np.ndarray:
    """One integer per 0.1-degree cell."""
    return (np.round(np.asarray(lat, float) * 10).astype(np.int64) * 100_000
            + np.round(np.asarray(lon, float) * 10).astype(np.int64))


class RainGrid:
    """ERA5-Land hourly rain (mm, NaN where missing) as one row per cell, hour 0 = T0, and the nine-company model's
    daily rain total and antecedent index (daily_rain_features) per cell-day."""

    def __init__(self, rain: pd.DataFrame, daily: pd.DataFrame):
        r = rain.sort_values(["cell_lat", "cell_lon", "time"])   # the dedup daily_rain_features does
        r = r[~r.duplicated(["cell_lat", "cell_lon", "time"], keep="last")]
        self.keys = pd.Index(np.unique(_key(r["cell_lat"], r["cell_lon"])))
        self.n_hours = int((T_END - T0) / pd.Timedelta(hours=1))
        self.n_days = self.n_hours // 24
        self.mm = np.full((len(self.keys), self.n_hours), np.nan, np.float32)
        ci = self.keys.get_indexer(_key(r["cell_lat"], r["cell_lon"]))
        hi = ((r["time"] - T0) // pd.Timedelta(hours=1)).to_numpy()
        ok = (hi >= 0) & (hi < self.n_hours)
        self.mm[ci[ok], hi[ok]] = pd.to_numeric(r["precip_mm"], errors="coerce").to_numpy()[ok]
        self.rain_d = np.full((len(self.keys), self.n_days), np.nan, np.float32)
        self.api = np.full((len(self.keys), self.n_days), np.nan, np.float32)
        dci = self.keys.get_indexer(_key(daily["cell_lat"], daily["cell_lon"]))
        ddi = ((daily["day"] - T0) // pd.Timedelta(days=1)).to_numpy()
        ok = (dci >= 0) & (ddi >= 0) & (ddi < self.n_days)
        self.rain_d[dci[ok], ddi[ok]] = daily["rain_d"].to_numpy()[ok]
        self.api[dci[ok], ddi[ok]] = daily["api"].to_numpy()[ok]

    def rows(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        ci = self.keys.get_indexer(_key(frame["cell_lat"], frame["cell_lon"]))
        assert (ci >= 0).all(), "a row's cell has no rain"
        di = ((frame["day"] - T0) // pd.Timedelta(days=1)).to_numpy().astype(np.int64)
        return ci.astype(np.int64), di

    def window(self, ci: np.ndarray, di: np.ndarray) -> np.ndarray:
        """The 72 hourly values (mm) from 00:00 UTC on d-2 to 23:00 UTC on d; NaN where missing."""
        return self.mm[ci[:, None], (di * 24 - 48)[:, None] + np.arange(HOURS)]


def day_total(w: np.ndarray) -> np.ndarray:
    t = np.nansum(w, axis=1)
    t[np.isfinite(w).sum(1) < MIN_HOURS_PER_DAY] = np.nan
    return t


def nansum_or_nan(a: np.ndarray) -> np.ndarray:
    t = np.nansum(a, axis=1)
    t[~np.isfinite(a).any(1)] = np.nan
    return t


def rain_features(grid: RainGrid, win: np.ndarray, ci: np.ndarray, di: np.ndarray) -> pd.DataFrame:
    """The ten rain features for day d from the 72-hour window `win` (days d-2..d) and the ERA5-Land daily totals and
    antecedent index before it, as daily_rain_features would compute them from one hourly series (train_nn.py's
    boosted_features, without the static columns)."""
    d2, d1, d0 = day_total(win[:, :24]), day_total(win[:, 24:48]), day_total(win[:, 48:])
    short = np.isnan(d0)

    def peak(width):
        r = np.stack([nansum_or_nan(win[:, t - width + 1:t + 1]) for t in range(48, 72)], axis=1)
        with np.errstate(all="ignore"):
            m = np.nanmax(np.where(np.isfinite(r), r, -np.inf), axis=1)
        m[~np.isfinite(m) | short] = np.nan
        return m

    def era(lo, hi):   # ERA5-Land daily totals for d-lo .. d-hi
        return grid.rain_d[ci[:, None], di[:, None] + np.arange(-lo, -hi + 1)]

    last3 = np.stack([d2, d1, d0], axis=1)
    f = pd.DataFrame({"rain_d": d0, "rain_d1": d1, "rain_d2": d2})
    f["rain_3d"] = nansum_or_nan(last3)
    f["rain_7d"] = nansum_or_nan(np.concatenate([era(6, 3), last3], axis=1))
    f["rain_30d"] = nansum_or_nan(np.concatenate([era(29, 3), last3], axis=1))
    f["api"] = (API_DECAY ** 3 * grid.api[ci, di - 3] + API_DECAY ** 2 * np.nan_to_num(d2)
                + API_DECAY * np.nan_to_num(d1) + np.nan_to_num(d0))
    f["max1h_d"] = peak(1)
    f["max3h_d"] = peak(3)
    f["max6h_d"] = peak(6)
    return f[RAIN_FEATURES].astype(np.float32)


def week_codes(day: pd.Series) -> np.ndarray:
    iso = day.dt.isocalendar()
    return pd.factorize(iso["year"].astype(int) * 100 + iso["week"].astype(int), sort=True)[0]


def boot_interval(diff: np.ndarray, week: np.ndarray, draws: np.ndarray) -> tuple[float, float]:
    W = draws.shape[1]
    s = np.bincount(week, weights=diff, minlength=W)
    n = np.bincount(week, minlength=W).astype(float)
    stat = s[draws].sum(1) / n[draws].sum(1)
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return float(lo), float(hi)


# ------------------------------------------------------------------ run
def prepare():
    """D2's rows (2024 training, 2025 verification), the rain grid, and the status of every overflow in them."""
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    labels = spill_days(ev)
    s24, _ = site_years(ar, ev, NINE, 2024)
    s25, _ = site_years(ar, ev, NINE, 2025)
    rain = load_rain(cells_of(pd.concat([s24, s25])))
    step(f"rain loaded: {len(rain)} cell-hours")
    daily = daily_rain_features(rain)
    grid = RainGrid(rain, daily)
    del rain
    train = _frame(s24, 2024, daily, labels)
    test = _frame(s25, 2025, daily, labels)
    del daily
    step(f"site-days: train {len(train)}, test {len(test)}")
    assert len(train) == 4_976_868 and len(test) == 5_077_150, "not D2's rows (its Results: 4,976,868 and 5,077,150)"
    status = Status(ev, pd.concat([s24["site_id"], s25["site_id"]]), covered_years(ar, ev, [2024, 2025]))
    step(f"status: {len(status.sites)} overflows, {status.n_intervals} merged events")
    return grid, train, test, status


def fit_candidate(train: pd.DataFrame, k: int) -> SpillModel:
    """D2's fit (fit_pooled with neg_frac 0.25 and seed 0, then fit_site_offsets with prior 15 and recency 1) on
    FEATURES. `train` holds lead k's status columns."""
    m = SpillModel(features=list(FEATURES)).fit_pooled(train, neg_frac=NEG_FRAC)
    m.fit_site_offsets(train, prior_strength=PRIOR_STRENGTH, recency=RECENCY)
    m.trained_on = f"Live-status candidate, lead {k}: nine English water companies 2024 (EA start/stop files)"
    return m


def stage_run() -> None:
    path = config.PROCESSED / NINE_PATH.name
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha.startswith(CANDIDATE_SHA), f"{path.name} is not D2's candidate ({sha[:12]})"
    base = SpillModel.load(path)
    # More of each status input can only raise the risk, as more rain can (features.MONOTONE).
    sm.MONOTONE = {**MONOTONE, **{f: 1 for f in STATUS}}
    grid, train, test, status = prepare()
    y24 = train["y"].to_numpy()
    sub = (y24 == 1) | (np.random.default_rng(0).random(len(y24)) < NEG_FRAC)
    assert sub.sum() == 1_569_401, "not D2's subsample (its log: 1,569,401 of 4,976,868 rows used)"
    checks: dict = {"baseline_sha256": sha, "subsample_rows": int(sub.sum()), "status_unknown": {}}

    # ---- fit one candidate per lead, on 2024 only
    OUT.mkdir(parents=True, exist_ok=True)
    cands = {}
    for k in LEADS:
        train[STATUS] = status.features(train["site_id"], train["day"], k)
        checks["status_unknown"][f"train lead {k}"] = {c: int(train[c].isna().sum()) for c in STATUS}
        cands[k] = fit_candidate(train, k)
        cands[k].save(OUT / f"candidate_lead{k}.pkl")
        step(f"lead {k}: candidate fitted ({cands[k].clf.n_iter_} iterations), saved")
    flat = train.groupby("company")["y"].mean()
    del train

    # ---- 2025, ERA5-Land rain
    y = test["y"].to_numpy()
    company = test["company"].to_numpy()
    week = week_codes(test["day"])
    draws = np.random.default_rng(0).integers(0, week.max() + 1, size=(N_BOOT, week.max() + 1))
    p_base = base.predict(test)
    p_base1 = base.predict_pooled(test)
    checks["baseline_all_nine_brier"] = float(((p_base - y) ** 2).mean())
    rows, diffs, rel, subsets = [], [], [], []
    for k in LEADS:
        test[STATUS] = status.features(test["site_id"], test["day"], k)
        checks["status_unknown"][f"test lead {k}"] = {c: int(test[c].isna().sum()) for c in STATUS}
        c = cands[k]
        blind = test[["site_id", *FEATURES]].copy()
        blind[STATUS] = np.float32(np.nan)
        preds = {"candidate": c.predict(test), "baseline (D2)": p_base, "candidate, layer 1 only": c.predict_pooled(test),
                 "baseline, layer 1 only": p_base1, "candidate, status unknown": c.predict(blind),
                 "company flat rate": test["company"].map(flat).to_numpy()}
        del blind
        diff = (preds["candidate"] - y) ** 2 - (p_base - y) ** 2
        for comp in [*NINE, "all nine"]:
            m = np.ones(len(y), bool) if comp == "all nine" else company == comp
            for name, p in preds.items():
                s = scores(y[m], p[m])
                rows.append({"lead": k, "company": comp, "predictor": name, "rows": s["n"], "base_rate": s["base_rate"],
                             "brier": s["brier"], "auc": s["auc"], "ece": ece(y[m], p[m]), "log_loss": s["log_loss"]})
            for name in ("candidate", "baseline (D2)"):
                rel.append(reliability_table(y[m], preds[name][m]).assign(lead=k, company=comp, predictor=name))
            lo, hi = boot_interval(diff[m], week[m], draws)
            diffs.append({"lead": k, "company": comp, "rows": int(m.sum()),
                          "brier_candidate": float(((preds["candidate"][m] - y[m]) ** 2).mean()),
                          "brier_baseline": float(((p_base[m] - y[m]) ** 2).mean()),
                          "difference": float(diff[m].mean()), "ci_low": lo, "ci_high": hi})
        now, c7 = test["spilling_at_issue"].to_numpy(), test["spill_days_7d"].to_numpy()
        for name, m in (("dry start: not spilling at issue, 0 spill-days in the 7 before", (now == 0) & (c7 == 0)),
                        ("not spilling at issue", now == 0),
                        ("spilling at issue", now == 1),
                        ("status unknown (any input)", test[STATUS].isna().any(axis=1).to_numpy())):
            if not m.any():
                continue
            lo, hi = boot_interval(diff[m], week[m], draws)
            sc, sb = scores(y[m], preds["candidate"][m]), scores(y[m], p_base[m])
            subsets.append({"lead": k, "subset": name, "rows": int(m.sum()), "base_rate": float(y[m].mean()),
                            "brier_candidate": sc["brier"], "brier_baseline": sb["brier"],
                            "auc_candidate": sc["auc"], "auc_baseline": sb["auc"],
                            "difference": float(diff[m].mean()), "ci_low": lo, "ci_high": hi})
        step(f"lead {k}, ERA5-Land: candidate {((preds['candidate'] - y) ** 2).mean():.5f}, "
             f"baseline {((p_base - y) ** 2).mean():.5f}")
    res, dif, sub_t = pd.DataFrame(rows), pd.DataFrame(diffs), pd.DataFrame(subsets)
    pd.set_option("display.width", 220)
    print("\n=== 2025, ERA5-Land rain: candidate minus baseline, 95% week-cluster bootstrap ===")
    print(dif.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print("\n=== Subsets ===")
    print(sub_t.to_string(index=False, float_format=lambda v: f"{v:.5f}"))

    # ---- 2025, forecast rain: days d, d-1, d-2 from the forecasts issued k, k-1, k-2 days ahead (floored at 0),
    # every earlier day from ERA5-Land; the same series feeds both models (train_nn.py's rule)
    lead_files = sorted(f for d in RAIN_DIRS for f in (config.CACHE / d).glob("leads_*_2025.parquet"))
    lf = pd.concat((pd.read_parquet(f) for f in lead_files), ignore_index=True)
    lf = lf.sort_values(["cell_lat", "cell_lon", "lead", "time"])
    lf = lf[~lf.duplicated(["cell_lat", "cell_lon", "lead", "time"], keep="last")]
    lkeys = pd.Index(np.unique(_key(lf["cell_lat"], lf["cell_lon"])))
    L = np.full((len(LEADS), len(lkeys), grid.n_hours), np.nan, np.float32)
    li = lkeys.get_indexer(_key(lf["cell_lat"], lf["cell_lon"]))
    hi = ((lf["time"] - T0) // pd.Timedelta(hours=1)).to_numpy()
    lead = lf["lead"].to_numpy()
    ok = np.isin(lead, LEADS) & (hi >= 0) & (hi < grid.n_hours)
    L[lead[ok], li[ok], hi[ok]] = lf["precip_mm"].to_numpy()[ok]
    del lf
    ci_all, di_all = grid.rows(test)
    to_lead = lkeys.get_indexer(grid.keys)          # grid cell -> lead cell, -1 if none
    era_ok = np.isfinite(grid.window(ci_all, di_all)).sum(1) >= MIN_FINITE
    in_lead = np.flatnonzero((to_lead[ci_all] >= 0) & era_ok)
    checks["lead_rows"] = {"files": len(lead_files), "cells": len(lkeys), "rows": len(in_lead),
                           "overflows": int(test.iloc[in_lead]["site_id"].nunique()),
                           "era_window_under_90pct": int((~era_ok).sum())}
    step(f"lead rows: {checks['lead_rows']}")
    lead_rows = []
    for k in LEADS:
        ci, di = ci_all[in_lead], di_all[in_lead]
        win = np.empty((len(in_lead), HOURS), np.float32)
        lc = to_lead[ci]
        for j in (2, 1, 0):                          # day d-j from the forecast issued k-j days ahead
            pos = (2 - j) * 24
            win[:, pos:pos + 24] = L[max(k - j, 0)][lc[:, None], ((di - j) * 24)[:, None] + np.arange(24)]
        okk = (np.isfinite(win).sum(1) >= MIN_FINITE) & np.isfinite(day_total(win[:, 48:]))
        sel = np.flatnonzero(okk)
        r = test.iloc[in_lead[sel]]
        fr = rain_features(grid, win[sel], ci[sel], di[sel]).fillna(0.0)   # a missing rain feature is 0 (verify_leads.py)
        fr.index = r.index
        st = status.features(r["site_id"], r["day"], k)
        x = pd.concat([r[["site_id", *STATIC]], fr, st], axis=1)
        pb, pc = base.predict(x), cands[k].predict(x)
        yk = r["y"].to_numpy()
        dk = (pc - yk) ** 2 - (pb - yk) ** 2
        lo, hi = boot_interval(dk, week[in_lead[sel]], draws)
        sc, sb = scores(yk, pc), scores(yk, pb)
        comp_k = r["company"].to_numpy()
        row = {"lead": k, "rows": len(sel), "dropped": int((~okk).sum()), "base_rate": float(yk.mean()),
               "brier_candidate": sc["brier"], "brier_baseline": sb["brier"], "auc_candidate": sc["auc"],
               "auc_baseline": sb["auc"], "difference": float(dk.mean()), "ci_low": lo, "ci_high": hi}
        for cmp in NINE:
            mc = comp_k == cmp
            if mc.any():
                lo_c, hi_c = boot_interval(dk[mc], week[in_lead[sel]][mc], draws)
                row |= {f"rows_{cmp}": int(mc.sum()), f"brier_candidate_{cmp}": float(((pc - yk) ** 2)[mc].mean()),
                        f"brier_baseline_{cmp}": float(((pb - yk) ** 2)[mc].mean()),
                        f"ci_low_{cmp}": lo_c, f"ci_high_{cmp}": hi_c}
        lead_rows.append(row)
        step(f"lead {k}, forecast rain: {len(sel)} rows, candidate {sc['brier']:.5f}, baseline {sb['brier']:.5f}")
    leads = pd.DataFrame(lead_rows)
    print("\n=== Forecast rain, leads 0-4 (all nine) ===")
    print(leads[["lead", "rows", "dropped", "base_rate", "brier_candidate", "brier_baseline", "auc_candidate",
                 "auc_baseline", "difference", "ci_low", "ci_high"]].to_string(index=False, float_format=lambda v: f"{v:.5f}"))

    # ---- the conditions, lead by lead
    b = res.set_index(["lead", "company", "predictor"])
    d = dif.set_index(["lead", "company"])
    s5 = sub_t[sub_t["subset"].str.startswith("dry start")].set_index("lead")
    cond = {}
    for k in LEADS:
        lr = leads.set_index("lead").loc[k]
        worse = [c for c in NINE if d.loc[(k, c), "difference"] > 0 and d.loc[(k, c), "ci_low"] > 0]
        ece_fail = [c for c in NINE if not (b.loc[(k, c, "candidate"), "ece"] <= b.loc[(k, c, "baseline (D2)"), "ece"]
                                            or b.loc[(k, c, "candidate"), "ece"] <= 0.02)]
        c5_worse = bool(s5.loc[k, "difference"] > 0 and s5.loc[k, "ci_low"] > 0)
        cond[k] = {"1 gain with forecast rain": bool(lr["difference"] < 0 and lr["ci_high"] < 0),
                   "2 gain with ERA5-Land rain": bool(d.loc[(k, "all nine"), "difference"] < 0
                                                      and d.loc[(k, "all nine"), "ci_high"] < 0),
                   "3 no company clearly worse": not worse,
                   "4 reliability": not ece_fail,
                   "5 not worse at a dry start": not c5_worse,
                   "companies clearly worse": worse, "ECE failures": ece_fail}
        cond[k]["helps"] = all(v for kk, v in cond[k].items() if kk[0].isdigit())
    print("\n=== Conditions ===")
    for k, v in cond.items():
        print(f"lead {k}:", {kk: ("PASS" if vv else "FAIL") if isinstance(vv, bool) and kk[0].isdigit() else vv
                             for kk, vv in v.items()})
    checks["conditions"] = cond

    res.to_csv(f"{DOCS}-scores.csv", index=False)
    dif.to_csv(f"{DOCS}-differences.csv", index=False)
    sub_t.to_csv(f"{DOCS}-subsets.csv", index=False)
    pd.concat(rel).to_csv(f"{DOCS}-reliability.csv", index=False)
    leads.to_csv(f"{DOCS}-leads.csv", index=False)
    Path(f"{DOCS}-checks.json").write_text(json.dumps(checks, indent=1, default=str))
    step("tables written")


if __name__ == "__main__":
    {"describe": stage_describe, "run": stage_run}[sys.argv[1]]()
