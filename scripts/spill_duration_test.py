"""How long a running spill goes on: a pre-stated test (docs/SPILL-DURATION-TEST-2026-11.md). Off CI, by hand:

    uv run python scripts/spill_duration_test.py describe   # 2024 only: how long spills run; nothing on 2025
    uv run python scripts/spill_duration_test.py check      # 2024 only: the whole pipeline, first half -> second half
    uv run python scripts/spill_duration_test.py run        # fit on 2024, score on 2025 (needs approval first)
    uv run python scripts/spill_duration_test.py diagnose   # after the verdict: development diagnostics only

Run with DIPCAST_ROOT pointing at a checkout that holds data/processed and the rain caches (data/cache/rain, data/cache/rain_nine).

The site's "When will it clear?" (transport.clear_time) assumes every overflow discharging now stops now. This test
asks whether the chance that a running spill is still running 1, 3, 6, 12 and 24 hours later can be told better than
by its company and how long it has run so far. The rows are whole UTC hours at which a spill was running, as a site
build would see it; the label is whether the same spill was still running h hours later. Spills are the EA start/stop
events with each overflow's overlapping events, and those less than GAP_H apart, merged.

No Open-Meteo calls: rain is the ERA5-Land hourly cache that the nine-company tests read (training.load_rain).
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.features import site_static_features
from dipcast.model.training import NINE, cells_of, load_events, load_rain, site_years

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True)
log = logging.getLogger("spill_duration_test")

GAP_H = 1.0                       # events of one overflow less than this far apart are one spill
CAP_H = 72                        # issue hours at most this long after the spill began (statement: "Rows")
HORIZONS = (1, 3, 6, 12, 24)      # hours ahead
ELAPSED_EDGES = (0, 1, 2, 3, 6, 12, 24, 48, 72)   # the baseline's elapsed bins, hours
SHORT_H = 3                       # condition 5: spills that began less than this long before the issue hour
N_BOOT = 2000
MATERIAL = 0.02                   # condition 1b: the gain must be at least this share of the baseline's score
H = 3600.0
TRAIN = (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-12-31", tz="UTC"))   # issue hours [lo, hi)
TEST = (pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2025-12-31", tz="UTC"))
# The files end at 2026-01-01 00:00, so every label of an issue hour before 2025-12-31 00:00 (24 h ahead) is known.
DOCS = Path(__file__).resolve().parents[1] / "docs" / "SPILL-DURATION-TEST-2026-11"   # beside this script, whatever DIPCAST_ROOT says
_T = time.time()


def step(msg: str) -> None:
    log.info("[%6.0fs] %s", time.time() - _T, msg)


# ------------------------------------------------------------------ spills and rows
def merge_spells(events: pd.DataFrame, gap_h: float = GAP_H) -> pd.DataFrame:
    """Each overflow's events joined into spills: overlapping events, and events that start less than `gap_h` hours
    after the spill so far has ended. Columns site_id, company, start, end (UTC). An event without an end is a point."""
    e = pd.DataFrame({"site_id": events["site_id"].to_numpy(), "company": events["company"].to_numpy(),
                      "start": events["event_start"].to_numpy(),
                      "end": events["event_end"].fillna(events["event_start"]).to_numpy()})
    e = e.sort_values(["site_id", "start"], kind="mergesort").reset_index(drop=True)
    reach = e.groupby("site_id")["end"].cummax().groupby(e["site_id"]).shift()   # the spill so far's end
    new = reach.isna() | (e["start"] - reach >= pd.Timedelta(hours=gap_h))
    g = new.cumsum()
    out = e.groupby(g).agg(site_id=("site_id", "first"), company=("company", "first"),
                           start=("start", "min"), end=("end", "max")).reset_index(drop=True)
    return out


def _ranges(k: np.ndarray) -> np.ndarray:
    """0 .. k_j - 1 for each j, concatenated."""
    if not len(k) or k.sum() == 0:
        return np.zeros(0, np.int64)
    return np.arange(k.sum()) - np.repeat(np.cumsum(k) - k, k)


def issue_rows(spells: pd.DataFrame, lo: pd.Timestamp, hi: pd.Timestamp, cap_h: int = CAP_H) -> pd.DataFrame:
    """One row per whole UTC hour t in [lo, hi) at which a spill runs (start <= t < end) and began less than cap_h
    hours before: spell (index into `spells`), t, elapsed_h, remaining_h (end - t)."""
    s = ((spells["start"] - lo).dt.total_seconds() / H).to_numpy()
    e = ((spells["end"] - lo).dt.total_seconds() / H).to_numpy()
    first = np.maximum(np.ceil(s), 0)
    last = np.minimum.reduce([np.ceil(e) - 1, np.floor(s + cap_h - 1e-9), np.full_like(s, (hi - lo) / pd.Timedelta(hours=1) - 1)])
    k = np.clip(last - first + 1, 0, None).astype(np.int64)
    idx = np.repeat(np.arange(len(spells)), k)
    t = np.repeat(first, k) + _ranges(k)
    return pd.DataFrame({"spell": idx, "t": lo + pd.to_timedelta(t, unit="h"),
                         "elapsed_h": (t - s[idx]).astype(np.float32), "remaining_h": (e[idx] - t).astype(np.float32)})


def labels(rows: pd.DataFrame) -> np.ndarray:
    """[n, len(HORIZONS)]: 1 where the spill is still running h hours after the issue hour."""
    return (rows["remaining_h"].to_numpy()[:, None] > np.asarray(HORIZONS, np.float32)[None, :]).astype(np.float32)


def elapsed_bin(elapsed_h: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(ELAPSED_EDGES, elapsed_h, side="right") - 1, 0, len(ELAPSED_EDGES) - 2)


# ------------------------------------------------------------------ baselines
def empirical_survival(company: np.ndarray, ebin: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    """The baseline B1, fitted on training rows: per (company, elapsed bin), the share still running at each horizon.
    A cell with no training rows takes the company's figure across all bins."""
    df = pd.DataFrame(y, columns=[f"h{h}" for h in HORIZONS]).assign(company=company, ebin=ebin)
    cell = df.groupby(["company", "ebin"]).mean()
    comp = df.drop(columns="ebin").groupby("company").mean()
    return cell, comp


def predict_empirical(table, company: np.ndarray, ebin: np.ndarray) -> np.ndarray:
    cell, comp = table
    key = pd.MultiIndex.from_arrays([company, ebin])
    p = cell.reindex(key).to_numpy()
    miss = np.isnan(p).any(1)
    if miss.any():
        p = p.copy()
        p[miss] = comp.reindex(company[miss]).to_numpy()
    return p


def monotone(p: np.ndarray) -> np.ndarray:
    """Still running at a later horizon can be no likelier than at an earlier one."""
    return np.minimum.accumulate(np.clip(p, 0.0, 1.0), axis=1)


# ------------------------------------------------------------------ describe (2024 only)
def stage_describe() -> None:
    """2024 only: spills per company at several merge gaps, and how often a running spill is still running h hours on,
    by elapsed bin. Nothing from 2025 is read."""
    ev = load_events(NINE)
    ev = ev[(ev["event_start"] >= TRAIN[0]) & (ev["event_start"] < pd.Timestamp("2025-01-01", tz="UTC"))]
    step(f"2024 events: {len(ev)}")
    gaps = []
    for gap in (0.0, 0.25, 1.0, 3.0):
        sp = merge_spells(ev, gap)
        d = (sp["end"] - sp["start"]).dt.total_seconds() / H
        for c, x in d.groupby(sp["company"]):
            gaps.append({"gap_h": gap, "company": c, "spills": len(x), "median_h": round(float(x.median()), 3),
                         "p90_h": round(float(x.quantile(0.9)), 2), "share_over_24h": round(float((x > 24).mean()), 4)})
        gaps.append({"gap_h": gap, "company": "all nine", "spills": len(d), "median_h": round(float(d.median()), 3),
                     "p90_h": round(float(d.quantile(0.9)), 2), "share_over_24h": round(float((d > 24).mean()), 4)})
    pd.DataFrame(gaps).to_csv(f"{DOCS}-describe-2024-gaps.csv", index=False)
    step("gaps written")
    # The 2024 issue hours end before 31 Dec, and every spill that runs into 2025 is cut at 1 Jan 00:00 by the 2024
    # file, so a label 24 h on from an hour before 31 Dec 00:00 never needs the 2025 file.
    sp = merge_spells(ev, GAP_H)
    rows = issue_rows(sp, *TRAIN)
    y = labels(rows)
    comp = sp["company"].to_numpy()[rows["spell"].to_numpy()]
    eb = elapsed_bin(rows["elapsed_h"].to_numpy())
    out = []
    for c in [*NINE, "all nine"]:
        m = np.ones(len(rows), bool) if c == "all nine" else comp == c
        spells_c = int(len(sp) if c == "all nine" else (sp["company"] == c).sum())
        out.append({"company": c, "elapsed": "all", "spills": spells_c, "rows": int(m.sum()),
                    **{f"running_after_{h}h": round(float(y[m, j].mean()), 4) for j, h in enumerate(HORIZONS)}})
        for b in range(len(ELAPSED_EDGES) - 1):
            mb = m & (eb == b)
            out.append({"company": c, "elapsed": f"{ELAPSED_EDGES[b]}-{ELAPSED_EDGES[b + 1]}h", "spills": None,
                        "rows": int(mb.sum()),
                        **{f"running_after_{h}h": round(float(y[mb, j].mean()), 4) if mb.any() else None
                           for j, h in enumerate(HORIZONS)}})
    t = pd.DataFrame(out)
    t.to_csv(f"{DOCS}-describe-2024.csv", index=False)
    print(t[t["company"] == "all nine"].to_string(index=False))
    print(t[t["elapsed"] == "all"].to_string(index=False))
    step(f"2024: {len(sp)} spills at gap {GAP_H} h, {len(rows)} issue hours")


# ------------------------------------------------------------------ run (2024 fit, 2025 score)
def site_table(ar: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    """Per overflow and issue year, the previous year's return figures as every model test fills them
    (training.site_years, features.site_static_features), and log hours per spill. A year's rows use only the year
    before's return."""
    out = []
    for y in (2024, 2025):
        s, _ = site_years(ar, ev, NINE, y)
        f = site_static_features(s)
        out.append(f.assign(year=y))
    s = pd.concat(out, ignore_index=True)
    s["log_hours_per_spill"] = s["log_spill_hours"] - s["log_lta_spills"]
    return s.drop_duplicates(["site_id", "year"], keep="last").reset_index(drop=True)


def rain_sums(grid: dict, cell: np.ndarray, t: np.ndarray, spans: list[tuple[int, int]]) -> np.ndarray:
    """Sum of hourly rain over [t + a, t + b) hours for each (a, b) in spans; NaN where any hour is missing.
    grid: {"keys": Index of cell keys, "t0": Timestamp, "mm": [cells, hours]}."""
    ci = grid["keys"].get_indexer(cell)
    hi = ((pd.DatetimeIndex(t) - grid["t0"]) // pd.Timedelta(hours=1)).to_numpy()
    cs = grid["cs"]
    out = np.full((len(t), len(spans)), np.nan, np.float32)
    ok = ci >= 0
    for j, (a, b) in enumerate(spans):
        lo, up = hi + a, hi + b
        good = ok & (lo >= 0) & (up < cs.shape[1])
        s = cs[ci[good], up[good]] - cs[ci[good], lo[good]]
        n = grid["cn"][ci[good], up[good]] - grid["cn"][ci[good], lo[good]]
        out[good, j] = np.where(n == (b - a), s, np.nan)
    return out


def build_grid(sites: pd.DataFrame) -> dict:
    rain = load_rain(cells_of(sites))
    rain = rain.sort_values(["cell_lat", "cell_lon", "time"])
    rain = rain[~rain.duplicated(["cell_lat", "cell_lon", "time"], keep="last")]
    key = (np.round(rain["cell_lat"].to_numpy() * 10).astype(np.int64) * 100_000
           + np.round(rain["cell_lon"].to_numpy() * 10).astype(np.int64))
    keys = pd.Index(np.unique(key))
    t0 = pd.Timestamp("2023-12-01", tz="UTC")
    n = int((pd.Timestamp("2026-01-02", tz="UTC") - t0) / pd.Timedelta(hours=1))
    mm = np.full((len(keys), n), np.nan, np.float32)
    hi = ((rain["time"] - t0) // pd.Timedelta(hours=1)).to_numpy()
    ok = (hi >= 0) & (hi < n)
    mm[keys.get_indexer(key)[ok], hi[ok]] = pd.to_numeric(rain["precip_mm"], errors="coerce").to_numpy()[ok]
    fin = np.isfinite(mm)
    zero = np.zeros((len(keys), 1), np.float64)
    return {"keys": keys, "t0": t0,
            "cs": np.concatenate([zero, np.cumsum(np.where(fin, mm, 0.0), axis=1, dtype=np.float64)], axis=1),
            "cn": np.concatenate([zero, np.cumsum(fin, axis=1, dtype=np.float64)], axis=1)}


def cell_keys(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    cl, cn = grid_cell(lat, lon)
    return np.round(np.asarray(cl) * 10).astype(np.int64) * 100_000 + np.round(np.asarray(cn) * 10).astype(np.int64)


PAST = [(-6, 0), (-24, 0), (-72, 0)]
FUTURE = [(0, h) for h in HORIZONS]
COMPANY_CODE = {c: i for i, c in enumerate(NINE)}


def features(rows: pd.DataFrame, sp: pd.DataFrame, sites: pd.DataFrame, grid: dict, before: np.ndarray) -> pd.DataFrame:
    """Candidate C1's inputs, each known at the issue hour, and C2's future rain (ERA5-Land, so an upper bound)."""
    spell = sp.iloc[rows["spell"].to_numpy()]
    year = rows["t"].dt.year.to_numpy()
    st = sites.set_index(["site_id", "year"])
    site = st.reindex(pd.MultiIndex.from_arrays([spell["site_id"].to_numpy(), year]))
    t = rows["t"]
    doy = t.dt.day_of_year.to_numpy()
    X = pd.DataFrame({
        "elapsed_h": rows["elapsed_h"].to_numpy(),
        "company": spell["company"].map(COMPANY_CODE).to_numpy(),
        "hour_utc": t.dt.hour.to_numpy(),
        "doy_sin": np.sin(2 * np.pi * doy / 365.25), "doy_cos": np.cos(2 * np.pi * doy / 365.25),
        "log_lta_spills": site["log_lta_spills"].to_numpy(), "log_spill_hours": site["log_spill_hours"].to_numpy(),
        "log_hours_per_spill": site["log_hours_per_spill"].to_numpy(), "edm_pct": site["edm_pct"].to_numpy(),
    })
    # Hours this overflow spilled in the 7 days before this spill began (earlier spills only).
    X["spilled_7d_before_h"] = before[rows["spell"].to_numpy()]
    cell = cell_keys(site["cell_lat"].to_numpy(), site["cell_lon"].to_numpy())
    past = rain_sums(grid, cell, t.to_numpy(), PAST)
    for j, (a, _) in enumerate(PAST):
        X[f"rain_past_{-a}h"] = past[:, j]
    fut = rain_sums(grid, cell, t.to_numpy(), FUTURE)
    for j, (_, b) in enumerate(FUTURE):
        X[f"rain_next_{b}h"] = fut[:, j]
    return X


def history_hours(sp: pd.DataFrame, window_h: float = 168.0) -> np.ndarray:
    """Per spill in `sp` (merge_spells' output), the hours its overflow spilled in the `window_h` hours before the
    spill began, from its earlier spills only. Spills of one overflow never overlap, so the earlier ones in the
    window are a run ending just before this one: their total less the part of the first that began before it."""
    o = sp.sort_values(["site_id", "start"], kind="mergesort")
    t0 = pd.Timestamp("2000-01-01", tz="UTC")
    s = (o["start"] - t0).dt.total_seconds().to_numpy() / H
    e = (o["end"] - t0).dt.total_seconds().to_numpy() / H
    site = pd.factorize(o["site_id"])[0]
    cum = np.concatenate([[0.0], np.cumsum(e - s)])            # hours of spells 0 .. j-1
    lo = s - window_h
    # first spell j (same site, j <= i) whose end is after lo: ends are sorted within a site
    key_e = site * 1e7 + e
    j = np.searchsorted(key_e, site * 1e7 + lo, side="right")
    i = np.arange(len(s))
    total = cum[i] - cum[j]
    clip = np.where(j < i, np.clip(lo - s[np.minimum(j, len(s) - 1)], 0, None), 0.0)
    out = np.empty(len(s), np.float32)
    out[o.index.to_numpy()] = np.clip(total - clip, 0, None)
    return out


C1 = ["elapsed_h", "company", "hour_utc", "doy_sin", "doy_cos", "log_lta_spills", "log_spill_hours",
      "log_hours_per_spill", "edm_pct", "spilled_7d_before_h", "rain_past_6h", "rain_past_24h", "rain_past_72h"]
C2 = C1 + [f"rain_next_{h}h" for h in HORIZONS]


def fit(X: pd.DataFrame, y: np.ndarray, cols: list[str]):
    from sklearn.ensemble import HistGradientBoostingClassifier
    cat = [cols.index("company")]
    models = []
    for j in range(len(HORIZONS)):
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
                                           categorical_features=cat, random_state=0)
        models.append(m.fit(X[cols], y[:, j]))
    return models


def predict(models, X: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return monotone(np.column_stack([m.predict_proba(X[cols])[:, 1] for m in models]))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    b = np.clip((p * bins).astype(int), 0, bins - 1)
    n = np.bincount(b, minlength=bins)
    gap = np.abs(np.bincount(b, weights=p, minlength=bins) - np.bincount(b, weights=y, minlength=bins))
    return float(gap.sum() / max(n.sum(), 1))


def week_codes(t: pd.Series) -> np.ndarray:
    iso = t.dt.isocalendar()
    return pd.factorize(iso["year"].astype(int) * 100 + iso["week"].astype(int), sort=True)[0]


def boot(diff: np.ndarray, week: np.ndarray, draws: np.ndarray) -> tuple[float, float]:
    W = draws.shape[1]
    s = np.bincount(week, weights=diff, minlength=W)
    n = np.bincount(week, minlength=W).astype(float)
    stat = s[draws].sum(1) / np.maximum(n[draws].sum(1), 1)
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return float(lo), float(hi)


def stage_run() -> None:
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    sp = merge_spells(ev, GAP_H)
    step(f"{len(ev)} events -> {len(sp)} spills")
    sites = site_table(ar, ev)
    grid = build_grid(sites)
    step("rain grid built")
    tr, te = issue_rows(sp, *TRAIN), issue_rows(sp, *TEST)
    # Only overflows with a position and the year before's return (site_years' rule), as every model test.
    def keep(rows):
        k = pd.MultiIndex.from_arrays([sp["site_id"].to_numpy()[rows["spell"].to_numpy()], rows["t"].dt.year.to_numpy()])
        return rows[k.isin(pd.MultiIndex.from_frame(sites[["site_id", "year"]]))].reset_index(drop=True)
    tr, te = keep(tr), keep(te)
    step(f"issue hours: train {len(tr)}, test {len(te)}")
    before = history_hours(sp)
    Xtr, Xte = features(tr, sp, sites, grid, before), features(te, sp, sites, grid, before)
    ytr, yte = labels(tr), labels(te)
    ctr = sp["company"].to_numpy()[tr["spell"].to_numpy()]
    cte = sp["company"].to_numpy()[te["spell"].to_numpy()]
    preds = {"B0 stops now": np.zeros_like(yte),
             "B1 company x elapsed": predict_empirical(empirical_survival(ctr, elapsed_bin(tr["elapsed_h"].to_numpy()), ytr),
                                                      cte, elapsed_bin(te["elapsed_h"].to_numpy()))}
    preds["B1 company x elapsed"] = monotone(preds["B1 company x elapsed"])
    for name, cols in (("C1", C1), ("C2 (ERA5 future rain)", C2)):
        preds[name] = predict(fit(Xtr, ytr, cols), Xte, cols)
        step(f"{name} fitted and scored")
    score_and_write(preds, yte, te, cte)


# ------------------------------------------------------------------ diagnose (after the verdict; development only)
def active_at(raw: pd.DataFrame, site_id: np.ndarray, t: np.ndarray) -> np.ndarray:
    """True where a raw event (overlaps joined, no gap rule) of that overflow runs at t: start <= t < end. This is what
    a monitor reports, as against a spill joined across a short pause. raw: merge_spells(events, 0.0)."""
    codes = pd.Index(np.unique(raw["site_id"].to_numpy()))
    t0 = pd.Timestamp("2000-01-01", tz="UTC")
    hrs = lambda x: (pd.DatetimeIndex(x) - t0).total_seconds().to_numpy() / H   # noqa: E731
    big = 1e7
    rc = codes.get_indexer(raw["site_id"].to_numpy())
    o = np.lexsort((hrs(raw["start"]), rc))
    ks = rc[o] * big + hrs(raw["start"])[o]
    ke = rc[o] * big + hrs(raw["end"])[o]
    qc = codes.get_indexer(site_id)
    q = qc * big + hrs(t)
    j = np.searchsorted(ks, q, side="right") - 1
    ok = (qc >= 0) & (j >= 0)
    jj = np.clip(j, 0, None)
    return ok & (ks[jj] // big == qc) & (ke[jj] > q)


def reliability(p: np.ndarray, y: np.ndarray, company: np.ndarray, model: str) -> pd.DataFrame:
    """Per company (and all nine) and horizon: mean forecast, observed share, signed gap (forecast minus observed),
    ECE, and the ten-bin table, so over- and under-forecasting can be told apart."""
    out = []
    for c in [*NINE, "all nine"]:
        m = np.ones(len(y), bool) if c == "all nine" else company == c
        for j, h in enumerate(HORIZONS):
            pj, yj = p[m, j], y[m, j]
            b = np.clip((pj * 10).astype(int), 0, 9)
            for k in range(10):
                mk = b == k
                out.append({"model": model, "company": c, "horizon_h": h, "bin": k, "rows": int(mk.sum()),
                            "mean_forecast": float(pj[mk].mean()) if mk.any() else None,
                            "observed": float(yj[mk].mean()) if mk.any() else None})
            out.append({"model": model, "company": c, "horizon_h": h, "bin": "all", "rows": int(m.sum()),
                        "mean_forecast": float(pj.mean()), "observed": float(yj.mean()), "ece": ece(pj, yj)})
    return pd.DataFrame(out)


def stage_diagnose() -> None:
    """After the verdict, development only (docs/SPILL-DURATION-DIAGNOSTICS-2026-11.md): reproduce C1 exactly, save its
    2025 predictions, break its reliability down by over- and under-forecasting, and measure how much of the target
    rests on joining events across short pauses. The verdict above the line in SPILL-DURATION-TEST is unchanged."""
    out_dir = config.PROCESSED / "spill_duration"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(__file__).resolve().parents[1] / "docs" / "SPILL-DURATION-DIAGNOSTICS-2026-11"
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    sp, raw = merge_spells(ev, GAP_H), merge_spells(ev, 0.0)
    sites = site_table(ar, ev)
    grid = build_grid(sites)
    tr, te = issue_rows(sp, *TRAIN), issue_rows(sp, *TEST)
    def keep(rows):
        k = pd.MultiIndex.from_arrays([sp["site_id"].to_numpy()[rows["spell"].to_numpy()], rows["t"].dt.year.to_numpy()])
        return rows[k.isin(pd.MultiIndex.from_frame(sites[["site_id", "year"]]))].reset_index(drop=True)
    tr, te = keep(tr), keep(te)
    before = history_hours(sp)
    Xtr, Xte = features(tr, sp, sites, grid, before), features(te, sp, sites, grid, before)
    ytr, yte = labels(tr), labels(te)
    ctr = sp["company"].to_numpy()[tr["spell"].to_numpy()]
    cte = sp["company"].to_numpy()[te["spell"].to_numpy()]
    step(f"rows: train {len(tr)}, test {len(te)}")

    # 1. The target: issue hours inside a joined pause, and labels that differ between "in the spill" and "a monitor
    # reports a discharge" at t + h.
    def active_cols(rows):
        sid = sp["site_id"].to_numpy()[rows["spell"].to_numpy()]
        now = active_at(raw, sid, rows["t"].to_numpy())
        later = np.column_stack([active_at(raw, sid, (rows["t"] + pd.Timedelta(hours=h)).to_numpy()) for h in HORIZONS])
        return now, later.astype(np.float32)
    now_tr, act_tr = active_cols(tr)
    now_te, act_te = active_cols(te)
    aud = []
    for name, now, y, act, comp in (("2024", now_tr, ytr, act_tr, ctr), ("2025", now_te, yte, act_te, cte)):
        for c in [*NINE, "all nine"]:
            m = np.ones(len(y), bool) if c == "all nine" else comp == c
            aud.append({"year": name, "company": c, "rows": int(m.sum()),
                        "share_in_a_pause": float(1 - now[m].mean()),
                        **{f"label_differs_{h}h": float((y[m, j] != act[m, j]).mean()) for j, h in enumerate(HORIZONS)},
                        **{f"in_spill_{h}h": float(y[m, j].mean()) for j, h in enumerate(HORIZONS)},
                        **{f"discharging_{h}h": float(act[m, j].mean()) for j, h in enumerate(HORIZONS)}})
    pd.DataFrame(aud).to_csv(f"{stem}-target.csv", index=False)
    step("target audit written")

    # 2. C1 as run (same rows, settings and seed), its 2025 predictions saved, and B1's.
    b1 = monotone(predict_empirical(empirical_survival(ctr, elapsed_bin(tr["elapsed_h"].to_numpy()), ytr),
                                    cte, elapsed_bin(te["elapsed_h"].to_numpy())))
    c1 = predict(fit(Xtr, ytr, C1), Xte, C1)
    ib = float(((c1 - yte) ** 2).mean())
    step(f"C1 reproduced: integrated Brier {ib:.4f} (the run: 0.1507)")
    pd.DataFrame({"spell": te["spell"], "t": te["t"], "elapsed_h": te["elapsed_h"], "company": cte, "discharging_now": now_te,
                  **{f"y_{h}h": yte[:, j] for j, h in enumerate(HORIZONS)},
                  **{f"b1_{h}h": b1[:, j] for j, h in enumerate(HORIZONS)},
                  **{f"c1_{h}h": c1[:, j] for j, h in enumerate(HORIZONS)}}).to_parquet(out_dir / "predictions_2025.parquet")
    rel = pd.concat([reliability(b1, yte, cte, "B1"), reliability(c1, yte, cte, "C1")], ignore_index=True)
    # Where the elapsed bins matter: C1's signed gap by elapsed bin, all nine.
    eb = elapsed_bin(te["elapsed_h"].to_numpy())
    byb = [{"model": n, "elapsed_bin": f"{ELAPSED_EDGES[b]}-{ELAPSED_EDGES[b + 1]}h", "horizon_h": h, "rows": int((eb == b).sum()),
            "mean_forecast": float(p[eb == b, j].mean()), "observed": float(yte[eb == b, j].mean())}
           for n, p in (("B1", b1), ("C1", c1)) for b in range(len(ELAPSED_EDGES) - 1) for j, h in enumerate(HORIZONS)]
    rel.to_csv(f"{stem}-reliability.csv", index=False)
    pd.DataFrame(byb).to_csv(f"{stem}-by-elapsed.csv", index=False)
    step("reliability written")

    # 3. Only rows a live monitor would show as discharging, on both labels. B1 and C1 refitted on the same kind of
    # 2024 rows and label, so each version is trained on what it is scored on.
    rs = []
    for lab, ytr_l, yte_l in (("in the spill", ytr, yte), ("discharging", act_tr, act_te)):
        mtr, mte = now_tr, now_te
        b = monotone(predict_empirical(empirical_survival(ctr[mtr], elapsed_bin(tr["elapsed_h"].to_numpy()[mtr]), ytr_l[mtr]),
                                       cte[mte], elapsed_bin(te["elapsed_h"].to_numpy()[mte])))
        c = predict(fit(Xtr[mtr], ytr_l[mtr], C1), Xte[mte], C1)
        yy = yte_l[mte]
        for c_ in [*NINE, "all nine"]:
            m = np.ones(len(yy), bool) if c_ == "all nine" else cte[mte] == c_
            ibb, ibc = ((b[m] - yy[m]) ** 2).mean(), ((c[m] - yy[m]) ** 2).mean()
            rs.append({"rows": "discharging at t", "label": lab, "company": c_, "n": int(m.sum()),
                       "B1": float(ibb), "C1": float(ibc), "gain": float(1 - ibc / ibb),
                       **{f"ece_c1_{h}h": ece(c[m, j], yy[m, j]) for j, h in enumerate(HORIZONS)},
                       **{f"ece_b1_{h}h": ece(b[m, j], yy[m, j]) for j, h in enumerate(HORIZONS)}})
        step(f"live-reproducible rows, label '{lab}' done")
    pd.DataFrame(rs).to_csv(f"{stem}-live-rows.csv", index=False)
    print(pd.DataFrame(aud).to_string(index=False))
    print(pd.DataFrame(rs)[["label", "company", "n", "B1", "C1", "gain"]].to_string(index=False))


def stage_check() -> None:
    """2024 only: build every input and fit both candidates on the first half of 2024, then score the second half,
    so the harness is known to run before the 2025 score. Writes nothing to docs; reads nothing from 2025."""
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    ev = ev[ev["event_start"] < pd.Timestamp("2025-01-01", tz="UTC")]
    sp = merge_spells(ev, GAP_H)
    sites = site_table(ar, ev)
    sites = sites[sites["year"] == 2024]
    grid = build_grid(sites)
    rows = issue_rows(sp, *TRAIN)
    k = pd.MultiIndex.from_arrays([sp["site_id"].to_numpy()[rows["spell"].to_numpy()], rows["t"].dt.year.to_numpy()])
    rows = rows[k.isin(pd.MultiIndex.from_frame(sites[["site_id", "year"]]))].reset_index(drop=True)
    X = features(rows, sp, sites, grid, history_hours(sp))
    print(X.describe().T[["count", "mean", "min", "max"]].to_string())
    y = labels(rows)
    a = (rows["t"] < pd.Timestamp("2024-07-01", tz="UTC")).to_numpy()
    comp = sp["company"].to_numpy()[rows["spell"].to_numpy()]
    eb = elapsed_bin(rows["elapsed_h"].to_numpy())
    b1 = monotone(predict_empirical(empirical_survival(comp[a], eb[a], y[a]), comp[~a], eb[~a]))
    print("2024 H2, integrated Brier: B1", float(((b1 - y[~a]) ** 2).mean()))
    for name, cols in (("C1", C1), ("C2", C2)):
        p = predict(fit(X[a], y[a], cols), X[~a], cols)
        print(f"2024 H2, integrated Brier: {name}", float(((p - y[~a]) ** 2).mean()))
    step(f"check done: {len(rows)} rows")


def score_and_write(preds: dict, y: np.ndarray, rows: pd.DataFrame, company: np.ndarray) -> None:
    week = week_codes(rows["t"])
    draws = np.random.default_rng(0).integers(0, week.max() + 1, size=(N_BOOT, week.max() + 1))
    base = preds["B1 company x elapsed"]
    short = rows["elapsed_h"].to_numpy() < SHORT_H
    per_spell = 1.0 / rows.groupby("spell")["spell"].transform("size").to_numpy()
    out, checks = [], {}
    for name, p in preds.items():
        bs = (p - y) ** 2                       # [n, horizons]
        ib = bs.mean(1)
        d = ib - ((base - y) ** 2).mean(1)
        for c in [*NINE, "all nine"]:
            m = np.ones(len(y), bool) if c == "all nine" else company == c
            if not m.any():
                continue
            lo, hi = boot(d[m], week[m], draws)
            out.append({"model": name, "company": c, "subset": "all", "rows": int(m.sum()),
                        "integrated_brier": float(ib[m].mean()), "diff_vs_B1": float(d[m].mean()), "lo": lo, "hi": hi,
                        **{f"brier_{h}h": float(bs[m, j].mean()) for j, h in enumerate(HORIZONS)},
                        **{f"ece_{h}h": ece(p[m, j], y[m, j]) for j, h in enumerate(HORIZONS)}})
        lo, hi = boot(d[short], week[short], draws)
        out.append({"model": name, "company": "all nine", "subset": f"elapsed < {SHORT_H} h", "rows": int(short.sum()),
                    "integrated_brier": float(ib[short].mean()), "diff_vs_B1": float(d[short].mean()), "lo": lo, "hi": hi})
        out.append({"model": name, "company": "all nine", "subset": "one weight per spill", "rows": len(y),
                    "integrated_brier": float(np.average(ib, weights=per_spell)),
                    "diff_vs_B1": float(np.average(d, weights=per_spell))})
        for j, h in enumerate(HORIZONS):
            dh = bs[:, j] - (base[:, j] - y[:, j]) ** 2
            lo, hi = boot(dh, week, draws)
            out.append({"model": name, "company": "all nine", "subset": f"horizon {h} h", "rows": len(y),
                        "diff_vs_B1": float(dh.mean()), "lo": lo, "hi": hi})
    t = pd.DataFrame(out)
    t.to_csv(f"{DOCS}-scores.csv", index=False)
    t1 = t.set_index(["model", "company", "subset"])
    b1 = t1.loc[("B1 company x elapsed", "all nine", "all")]
    for name in ("C1", "C2 (ERA5 future rain)"):
        a = t1.loc[(name, "all nine", "all")]
        comp = t1.loc[name].xs("all", level="subset").drop("all nine")
        bcomp = t1.loc["B1 company x elapsed"].xs("all", level="subset").drop("all nine")
        checks[name] = {
            "1a gain, interval below zero": bool(a["hi"] < 0),
            "1b gain at least 2% of B1": bool(-a["diff_vs_B1"] >= MATERIAL * b1["integrated_brier"]),
            "2 no horizon clearly worse": bool(all(t1.loc[(name, "all nine", f"horizon {h} h"), "lo"] <= 0 for h in HORIZONS)),
            "3 no company clearly worse": bool((comp["lo"] <= 0).all()),
            "4 reliability": bool(all(((comp[f"ece_{h}h"] <= bcomp[f"ece_{h}h"]) | (comp[f"ece_{h}h"] <= 0.02)).all()
                                      for h in HORIZONS)),
            "5 not worse on new spills": bool(t1.loc[(name, "all nine", f"elapsed < {SHORT_H} h"), "lo"] <= 0),
        }
        checks[name]["passes"] = all(checks[name].values())
    with open(f"{DOCS}-checks.json", "w") as f:
        json.dump(checks, f, indent=2)
    print(t[t["subset"] == "all"][["model", "company", "rows", "integrated_brier", "diff_vs_B1", "lo", "hi"]].to_string(index=False))
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    {"describe": stage_describe, "check": stage_check, "run": stage_run, "diagnose": stage_diagnose}[sys.argv[1]]()
