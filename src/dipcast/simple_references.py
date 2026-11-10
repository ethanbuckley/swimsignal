"""Two simple rules scored beside the live spill forecast on the Accuracy page, on the same rows, with intervals
(docs/SIMPLE-REFERENCES-LIVE-2026-11.md, stated before any score; docs/PREREGISTRATION-2027-AMENDMENT-4.md for 2027).

P, same-day persistence: the overflow is active at the issue time T if its poll record shows it spilling at T or in the
RECENT_SPILL_HOURS before it (the rebuild of scripts/interim_usefulness.py, vectorised). R, the rain rule: the logged
rain for the target day and the day before, over RAIN_MM. Each side of each rule gets a chance fitted only on outcomes
known at the issue: the same lead and side, all companies, target days I - FIT_DAYS to I - 1, (spills + 0.5) / (rows + 1),
none under MIN_FIT_ROWS rows. Skill is 1 - Brier(forecast) / Brier(rule) on the rows with both rules, with the 2027
pre-registration's two-way bootstrap (overflows x 7-day blocks from FIRST_DAY)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.forecast_log import LOCAL_TZ, MAX_GAP_H
from dipcast.model.live_status import SLOT_H, _merge, poll_events

RECENT_H = config.RECENT_SPILL_HOURS
RAIN_MM = 10.0                 # wet when the 48 h rain is over this (model.verify.rain_rule)
FIT_DAYS = 28
MIN_FIT_ROWS = 100
FIRST_DAY = date(2026, 9, 29)  # the first scored live day; blocks are 7 days from it
BLOCK_DAYS = 7
RESAMPLES = 2000
SEED = 20270501                # the 2027 pre-registration's seed (section 10)
MIN_SPILL_ROWS = 20            # a company cell with fewer spill rows among its common rows is too few to judge
RULES = {"persistence": "same-day persistence", "rain": f"rain over {RAIN_MM:g} mm"}
LEAD_GROUPS = {"0": (0,), "1-4": (1, 2, 3, 4)}
ALL = "All companies"


# ------------------------------------------------------------------ rule P: the status at issue, rebuilt from the polls
def poll_readings(cov: pd.DataFrame, polls: pd.DataFrame, company: pd.Series, first: date, last: date) -> pd.DataFrame:
    """(site_id, t): each poll of the overflow's company (poll_log.parquet's fetched_at) whose half-hour slot in
    live_coverage.parquet holds a current reading of the overflow, at the poll's own time."""
    t = pd.to_datetime(polls["fetched_at"], utc=True)
    wall = t.dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    p = pd.DataFrame({"company": polls["company"].to_numpy(), "t": t, "day": wall.dt.date,
                      "slot": ((wall - wall.dt.floor("D")).dt.total_seconds() // (SLOT_H * 3600)).astype(int)})
    p = p[(p["day"] >= first) & (p["day"] <= last)].drop_duplicates(["company", "t"])
    c = cov[(cov["day"] >= first) & (cov["day"] <= last)][["site_id", "day", "slots"]].astype({"site_id": str})
    c = c.assign(company=c["site_id"].map(company)).dropna(subset=["company"])
    m = c.merge(p, on=["company", "day"])
    seen = (m["slots"].to_numpy(dtype=np.int64) >> m["slot"].to_numpy(dtype=np.int64)) & 1
    return m.loc[seen.astype(bool), ["site_id", "t"]]


def persistence_status(rows: pd.DataFrame, history: pd.DataFrame, cov: pd.DataFrame, polls: pd.DataFrame) -> pd.DataFrame:
    """Per row (site_id, issued_ms): known (current readings over the RECENT_H before issue with no stretch over
    MAX_GAP_H, the stretch to the issue time included), active (a merged spill interval that had started by the last
    reading at or before issue and had not ended RECENT_H before it) and spilling_now (one still running at issue)."""
    n = len(rows)
    known, active, now = np.zeros(n, bool), np.zeros(n, bool), np.zeros(n, bool)
    if not n or history.empty:
        return pd.DataFrame({"known": known, "active": active, "spilling_now": now}, index=rows.index)
    t_ns = rows["issued_ms"].to_numpy(dtype=np.int64) * 1_000_000
    T = pd.to_datetime(t_ns, utc=True)
    first = (T.min() - pd.Timedelta(hours=RECENT_H)).tz_convert(LOCAL_TZ).date() - timedelta(days=1)
    h = history.assign(site_id=history["site_id"].astype(str))
    company = h.drop_duplicates("site_id", keep="last").set_index("site_id")["company"]
    rt = poll_readings(cov, polls, company, first, T.max().tz_convert(LOCAL_TZ).date())
    rd = {s: np.sort(g["t"].to_numpy(dtype="datetime64[ns]").astype(np.int64)) for s, g in rt.groupby("site_id")}
    ev = _merge(poll_events(history))
    ivs = {s: (g["start"].to_numpy(dtype="datetime64[ns]").astype(np.int64),
               g["end"].to_numpy(dtype="datetime64[ns]").astype(np.int64)) for s, g in ev.groupby("site_id")}
    win, gap = int(RECENT_H * 3600e9), MAX_GAP_H * 3600e9
    for s, idx in rows.groupby(rows["site_id"].astype(str)).indices.items():
        r = rd.get(s)
        if r is None or not len(r):
            continue
        t = t_ns[idx]
        hi = np.searchsorted(r, t, side="right")          # readings at or before t: r[:hi]
        lo = np.searchsorted(r, t - win, side="right") - 1  # the last reading at or before t - win, or -1
        has = hi > 0
        # Stretches: from t - win (or the last reading before it) through the readings to t. A gap between readings
        # i-1 and i is bad when over MAX_GAP_H; count the bad ones inside the window with a running sum.
        bad = np.concatenate([[0], np.cumsum(np.diff(r) > gap)])   # bad[i]: bad gaps among r[0..i]
        last = r[np.maximum(hi - 1, 0)]
        start = np.maximum(lo, 0)
        inner = bad[np.maximum(hi - 1, 0)] - bad[start]
        head_ok = (lo >= 0) | (r[0] - (t - win) <= gap)
        k = has & (inner == 0) & (t - last <= gap) & head_ok
        st, en = ivs.get(s, (np.zeros(0, np.int64), np.zeros(0, np.int64)))
        j = np.searchsorted(st, last, side="right") - 1
        ok = has & (j >= 0)
        e = np.where(ok, en[np.maximum(j, 0)] if len(en) else 0, np.iinfo(np.int64).min)
        known[idx] = k
        active[idx] = ok & (e >= t - win)
        now[idx] = ok & (e >= t)
    return pd.DataFrame({"known": known, "active": active, "spilling_now": now}, index=rows.index)


# ------------------------------------------------------------------ rule R: the 48 h forecast rain
def rain_48h(rows: pd.DataFrame, log: pd.DataFrame) -> pd.Series:
    """rain_mm for the target day plus rain_mm for the day before: from the same issue for leads 1-4, and for lead 0
    from the latest logged forecast of that overflow for the day before issued before it. rows: site_id, issued_ms,
    target_day (datetime64), lead, rain_mm. log: the logged rows (site_id, issued_ms, target_day, rain_mm)."""
    day = lambda s: pd.to_datetime(s).astype("datetime64[ns]")   # one unit on both sides, for the keys and the as-of join
    rows = rows.assign(site_id=rows["site_id"].astype(str), issued_ms=rows["issued_ms"].astype(np.int64),
                       target_day=day(rows["target_day"]))
    log = log.assign(site_id=log["site_id"].astype(str), issued_ms=log["issued_ms"].astype(np.int64), target_day=day(log["target_day"]))
    prev = rows["target_day"] - pd.Timedelta(days=1)
    same = log.dropna(subset=["rain_mm"]).drop_duplicates(["site_id", "issued_ms", "target_day"])
    key = same.set_index(["site_id", "issued_ms", "target_day"])["rain_mm"]
    d1 = pd.Series(key.reindex(pd.MultiIndex.from_arrays([rows["site_id"], rows["issued_ms"], prev])).to_numpy(),
                   index=rows.index)
    z = (rows["lead"] == 0).to_numpy()
    if z.any():
        q = pd.DataFrame({"site_id": rows.loc[z, "site_id"].to_numpy(), "target_day": prev[z].to_numpy(),
                          "issued_ms": rows.loc[z, "issued_ms"].to_numpy() - 1, "_i": rows.index[z]}).sort_values("issued_ms")
        ref = same[["site_id", "target_day", "issued_ms", "rain_mm"]].sort_values("issued_ms")
        m = pd.merge_asof(q, ref, on="issued_ms", by=["site_id", "target_day"], direction="backward")
        d1.loc[m["_i"].to_numpy()] = m["rain_mm"].to_numpy()
    return rows["rain_mm"].astype(float) + d1


def rain_log_rows(con, first: date, last: date, issued_ms) -> pd.DataFrame:
    """The logged rows rain_48h needs, from the forecast log (a duckdb connection): every row with rain issued at one
    of the scored issue times (`issued_ms`, for leads 1-4's day before), and each overflow's last issue with rain for
    each target day (lead 0's day before: every forecast for day I - 1 was issued before any issue on day I). Target
    days from the day before `first` to `last`."""
    times = pd.DataFrame({"issued_ms": np.unique(np.asarray(issued_ms, dtype=np.int64))})
    con.register("_sr_times", times)
    try:
        return con.execute("""
            WITH f AS (SELECT site_id, epoch_ms(issued_at) AS issued_ms, target_day, rain_mm FROM forecast_overflows
                       WHERE rain_mm IS NOT NULL AND target_day BETWEEN ? AND ?)
            SELECT * FROM f WHERE issued_ms IN (SELECT issued_ms FROM _sr_times)
            UNION
            SELECT * FROM f QUALIFY row_number() OVER (PARTITION BY site_id, target_day ORDER BY issued_ms DESC) = 1
        """, [first - timedelta(days=1), last]).df()
    finally:
        con.unregister("_sr_times")


def is_wet(rain48: np.ndarray) -> np.ndarray:
    """Rule R's yes: the 48 h rain over RAIN_MM, strictly (10 mm itself is dry). Missing rain is not wet."""
    r = np.asarray(rain48, dtype=float)
    return np.where(np.isnan(r), False, r > RAIN_MM)


# ------------------------------------------------------------------ chances fitted on what was known at issue
def epoch_ms(t) -> np.ndarray:
    """Milliseconds since 1970 (UTC) of a datetime series, whatever its unit (pandas 3 keeps microseconds)."""
    return ((pd.to_datetime(pd.Series(t), utc=True) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)).to_numpy(np.int64)


def _days(d) -> np.ndarray:
    return (pd.to_datetime(pd.Series(d)).to_numpy(dtype="datetime64[D]").astype(np.int64))


def trailing_chances(issue_day, target_day, lead, side, y, ok, fit_days: int = FIT_DAYS,
                     min_rows: int = MIN_FIT_ROWS) -> np.ndarray:
    """Each row's chance on its side of a rule: (spills + 0.5) / (rows + 1) over the rows of the same lead and side
    where the rule applies (ok), with target day from issue_day - fit_days to issue_day - 1; NaN where the rule does
    not apply to the row, or the side has fewer than min_rows such rows."""
    iday, tday = _days(issue_day), _days(target_day)
    lead, side, y, ok = np.asarray(lead), np.asarray(side, bool), np.asarray(y, float), np.asarray(ok, bool)
    out = np.full(len(y), np.nan)
    if not len(y):
        return out
    d0 = min(iday.min(), tday.min()) - fit_days - 1
    span = max(iday.max(), tday.max()) - d0 + 2
    for k in np.unique(lead):
        for s in (True, False):
            fit = ok & (lead == k) & (side == s)
            n = np.bincount(tday[fit] - d0, minlength=span).astype(float)
            sp = np.bincount(tday[fit] - d0, weights=y[fit], minlength=span)
            cn, cs = np.concatenate([[0.0], np.cumsum(n)]), np.concatenate([[0.0], np.cumsum(sp)])
            use = ok & (lead == k) & (side == s)
            hi, lo = iday[use] - d0, iday[use] - fit_days - d0   # target days lo .. hi-1
            rows, spills = cn[hi] - cn[lo], cs[hi] - cs[lo]
            out[use] = np.where(rows >= min_rows, (spills + 0.5) / (rows + 1.0), np.nan)
    return out


# ------------------------------------------------------------------ the two-way bootstrap, aggregated
def block_of(days, first: date = FIRST_DAY) -> np.ndarray:
    return np.floor_divide((pd.to_datetime(pd.Series(days)) - pd.Timestamp(first)).dt.days.to_numpy(), BLOCK_DAYS)


class Draws:
    """evaluate_2027.Bootstrap's draws (sites, then blocks, per draw, from one generator), kept as two count
    matrices so a weighted sum over rows is sum((S @ M) * B, axis=1) for M the rows' sums by (site, block)."""

    def __init__(self, site, block, resamples: int = RESAMPLES, seed: int = SEED):
        self.site_codes, self.site = np.unique(np.asarray(site), return_inverse=True)
        self.block_codes, self.block = np.unique(np.asarray(block), return_inverse=True)
        ns, nb = len(self.site_codes), len(self.block_codes)
        rng = np.random.default_rng(seed)
        S, B = np.zeros((resamples, ns)), np.zeros((resamples, nb))
        for r in range(resamples):
            S[r] = np.bincount(rng.integers(0, ns, ns), minlength=ns) if ns else 0
            B[r] = np.bincount(rng.integers(0, nb, nb), minlength=nb) if nb else 0
        self.S, self.B = S, B

    def sums(self, rows: np.ndarray, values: np.ndarray) -> np.ndarray:
        """The weighted sum of `values` over `rows` in every draw."""
        ns, nb = self.S.shape[1], self.B.shape[1]
        M = np.bincount(self.site[rows] * nb + self.block[rows], weights=values, minlength=ns * nb).reshape(ns, nb)
        return np.einsum("rb,rb->r", self.S @ M, self.B)


def _interval(a: np.ndarray) -> dict:
    ok = a[~np.isnan(a)]
    return {"lo": float(np.percentile(ok, 2.5)) if len(ok) else None,
            "hi": float(np.percentile(ok, 97.5)) if len(ok) else None, "undefined_draws": int(len(a) - len(ok))}


def verdict(ci: dict | None, too_few: bool) -> str:
    """'beats', 'worse' or 'unclear' from the interval of the skill against a rule; 'too_few' for a small cell."""
    if too_few:
        return "too_few"
    if not ci or ci.get("lo") is None:
        return "unclear"
    return "beats" if ci["lo"] > 0 else "worse" if ci["hi"] < 0 else "unclear"


def describe(df: pd.DataFrame, rows: np.ndarray, draws: Draws, min_spill_rows: int) -> dict:
    """One cell on its common rows: counts, each Brier score, the skill against each reference and its interval."""
    g = df.iloc[rows]
    y = g["y"].to_numpy(float)
    out = {"rows": len(g), "overflows": int(g["site_id"].nunique()), "spill_rows": int(y.sum()),
           "spill_rate": float(y.mean()) if len(g) else None, "mean_forecast": float(g["p_cal"].mean()) if len(g) else None}
    if not len(g):
        return out
    se = {k: (g[c].to_numpy(float) - y) ** 2 for k, c in
          (("forecast", "p_cal"), ("persistence", "p_persistence"), ("rain", "p_rain"), ("climatology", "p_clim"))}
    out["brier"] = {k: float(v.mean()) for k, v in se.items()}
    w = {k: draws.sums(rows, v) for k, v in se.items()}
    out["skill"], out["ci"], out["verdict"] = {}, {}, {}
    too_few = int(y.sum()) < min_spill_rows
    out["too_few"] = too_few
    refs = ("persistence", "rain", "climatology")
    for k in refs:
        ref = out["brier"][k]
        out["skill"][k] = 1 - out["brier"]["forecast"] / ref if ref > 0 else None
        with np.errstate(divide="ignore", invalid="ignore"):
            a = np.where(w[k] > 0, 1 - w["forecast"] / w[k], np.nan)
        out["ci"][k] = _interval(a)
        out["verdict"][k] = verdict(out["ci"][k], too_few)
    # The best of the three in each draw (and in the point estimate): stricter on the forecast than any one fixed rule.
    best = min(refs, key=lambda k: out["brier"][k])
    out["best_reference"] = best
    out["skill"]["best"] = out["skill"][best]
    low = np.min(np.vstack([w[k] for k in refs]), axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["ci"]["best"] = _interval(np.where(low > 0, 1 - w["forecast"] / low, np.nan))
    out["verdict"]["best"] = verdict(out["ci"]["best"], too_few)
    return out


# ------------------------------------------------------------------ the page's figures
def score(fc: pd.DataFrame, rain_log: pd.DataFrame, history: pd.DataFrame, cov: pd.DataFrame, polls: pd.DataFrame,
          resamples: int = RESAMPLES, seed: int = SEED, first_day: date = FIRST_DAY, score_from: date | None = None,
          score_to: date | None = None) -> dict:
    """fc: verify_live's scored rows (site_id, company, issue_day, target_day, lead, issued_at, p_cal, p_clim, y,
    rain_mm; optionally water, and keep, False for a row that is fitted on but not scored). rain_log: logged rows
    (site_id, issued_ms, target_day, rain_mm) covering the day before the first target day onwards. Each rule's chances
    are fitted on every row from first_day; the scores and the bootstrap use the kept rows from score_from (default
    first_day, which also anchors the 7-day blocks) to score_to. Returns live.simple_refs for verification_live.json."""
    df = fc[pd.to_datetime(fc["target_day"]).dt.date >= first_day].reset_index(drop=True)
    df = df.assign(site_id=df["site_id"].astype(str), issued_ms=epoch_ms(df["issued_at"]),
                   target_day=pd.to_datetime(df["target_day"]))
    if "company" not in df:
        df["company"] = None
    df["company"] = df["company"].fillna("unknown")
    lead, y = df["lead"].to_numpy(int), df["y"].to_numpy(float)
    df["rain48"] = rain_48h(df[["site_id", "issued_ms", "target_day", "lead", "rain_mm"]], rain_log).to_numpy()
    rain_ok = df["rain48"].notna().to_numpy()
    wet = is_wet(df["rain48"].to_numpy())
    ps = persistence_status(df[["site_id", "issued_ms"]], history, cov, polls)
    known, act = ps["known"].to_numpy(bool), ps["active"].to_numpy(bool)
    df["p_rain"] = trailing_chances(df["issue_day"], df["target_day"], lead, wet, y, rain_ok, FIT_DAYS, MIN_FIT_ROWS)
    df["p_persistence"] = trailing_chances(df["issue_day"], df["target_day"], lead, act, y, known, FIT_DAYS, MIN_FIT_ROWS)
    # The scored window: everything above is fitted on every row; what follows only on the rows scored.
    start = score_from or first_day
    td = df["target_day"].dt.date
    s = (td >= start).to_numpy() & ((td <= score_to).to_numpy() if score_to else True)
    if "keep" in df:
        s &= df["keep"].fillna(False).to_numpy(bool)
    df, lead, y, known, act, rain_ok, wet = (df[s].reset_index(drop=True), lead[s], y[s], known[s], act[s], rain_ok[s], wet[s])
    common = df["p_rain"].notna().to_numpy() & df["p_persistence"].notna().to_numpy()
    draws = Draws(df["site_id"].to_numpy(), block_of(df["target_day"], start), resamples, seed)
    cells = []

    def add(key: dict, m: np.ndarray, min_spills: int):
        cells.append({**key, "scored_rows": int(m.sum()), "status_known": int((m & known).sum()), "rain_known": int((m & rain_ok).sum()),
                      **describe(df, np.flatnonzero(m & common), draws, min_spills)})
    every = np.ones(len(df), bool)
    for lg, leads in {**LEAD_GROUPS, **{str(k): (k,) for k in (1, 2, 3, 4)}}.items():
        add({"company": ALL, "leads": lg}, every & np.isin(lead, leads), 0)
    for comp in sorted(c for c in df["company"].unique() if c != "unknown"):
        for lg, leads in LEAD_GROUPS.items():
            add({"company": comp, "leads": lg}, (df["company"] == comp).to_numpy() & np.isin(lead, leads), MIN_SPILL_ROWS)
    if "water" in df:
        for wv in sorted(df["water"].dropna().unique()):
            for lg, leads in LEAD_GROUPS.items():
                add({"water": wv, "leads": lg}, (df["water"] == wv).to_numpy() & np.isin(lead, leads), MIN_SPILL_ROWS)
    sides = {}
    for k in sorted(set(lead)):
        lm, cm = lead == k, common
        sides[str(k)] = {"persistence_active": {"rows": int((lm & cm & act).sum()), "spill_rate": _rate(y[lm & cm & act])},
                         "persistence_quiet": {"rows": int((lm & cm & ~act).sum()), "spill_rate": _rate(y[lm & cm & ~act])},
                         "rain_wet": {"rows": int((lm & cm & wet).sum()), "spill_rate": _rate(y[lm & cm & wet])},
                         "rain_dry": {"rows": int((lm & cm & ~wet).sum()), "spill_rate": _rate(y[lm & cm & ~wet])}}
    return {"protocol": "docs/SIMPLE-REFERENCES-LIVE-2026-11.md", "rules": RULES,
            "settings": {"rain_mm": RAIN_MM, "recent_spill_hours": RECENT_H, "max_gap_h": MAX_GAP_H, "fit_days": FIT_DAYS,
                         "min_fit_rows": MIN_FIT_ROWS, "smoothing": "(spills + 0.5) / (rows + 1)", "first_day": str(first_day),
                         "block_days": BLOCK_DAYS, "block_anchor": str(start), "resamples": resamples, "seed": seed,
                         "min_spill_rows": MIN_SPILL_ROWS},
            "first_day": str(df["target_day"].min().date()) if len(df) else None,
            "last_day": str(df["target_day"].max().date()) if len(df) else None,
            "first_common_day": str(df.loc[common, "target_day"].min().date()) if common.any() else None,
            "scored_rows": len(df), "common_rows": int(common.sum()),
            "bootstrap": {"overflows": len(draws.site_codes), "blocks": len(draws.block_codes)},
            "sides": sides, "cells": cells}


def _rate(y: np.ndarray) -> float | None:
    return float(y.mean()) if len(y) else None
