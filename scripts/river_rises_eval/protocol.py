"""docs/RIVER-RISES-SCOPE-2026-10.md, "Evaluation plan": the stated plan as functions of arrays and frames, no network.

fetch.py gets the series (capped, behind the heavy-run lock). score.py runs two stages: `predict` (the gate, the
fits and the test-period predictions; no test outcome is scored) and `score` (needs the run statement with B and H).
tests/test_river_rises_eval.py checks each piece on synthetic series.

- **Issue times:** every hour on the hour, UTC (issue_grid).
- **What the site showed** at an issue time t (site_view): the site's own rule (flows.flow_state, build_site's
  index and flows.rise_over_window) on the readings published by then, r <= t - d.
- **Inputs** (trend_inputs, rain_inputs): only readings at or before t - d (gauges) or hours ending at or before
  t - 1 h (radar). Every read goes through Readings.value, whose cut can only look back.
- **Label** (labels): the spot gauge's highest reading in (t, t + h] more than 0.2 of its EA range above its last
  reading at or before t. The label alone reads past t.
- **Separation:** time (period) and river systems in 5 folds (system_folds); cross_fold fits on the training period
  of the other folds' gauges only.
- **References:** R1 base rate by gauge and month, R2 the site's words, R3 persistence. **Candidates:** C1 adds the
  upstream gauges, C2 adds radar.
- **Metrics, gate, the six conditions, the placebo and the near-miss labels** as stated.

Choices the plan leaves open are fixed here and listed in the doc ("Harness choices", 26 October 2026).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast.ingest import flows

# ------------------------------------------------------------------ the plan's fixed values
SHARE = flows.RISING_SHARE            # 0.2 of the EA usual range, the site's RISING_SHARE
HIGH_INDEX = flows.HIGH_INDEX         # the site's "high": index above 1
SITE_RISE_H = flows.RISE_WINDOW_H     # the site's "rising fast" window, 6 h
SITE_MIN_SPAN_H = flows.RISE_MIN_SPAN_H
SITE_TREND_READINGS = flows.TREND_READINGS
MAX_AGE_H = flows.MAX_READING_AGE_H   # a published reading at most 24 h old
HORIZONS_H = (3, 6)                   # primary 3 h, secondary 6 h
PRIMARY_H = 3
DELAY_H = 1.0                         # d for every gauge ...
DELAY_SENS_H = 3.0                    # ... and the sensitivity
RADAR_DELAY_H = 1.0                   # radar hours ending at or before t - 1 h
SPOT_RISES_H = (1, 3)                 # R3: index and rise over 1 h and 3 h
UP_RISES_H = (1, 3, 6)                # C1: each upstream gauge's rise over 1, 3, 6 h and its index
RAIN_SUMS_H = (3, 6, 12)              # C2: radar sums
TRAIN = (pd.Timestamp("2024-11-21", tz="UTC"), pd.Timestamp("2025-10-01", tz="UTC"))   # [start, end)
TEST = (pd.Timestamp("2025-10-01", tz="UTC"), pd.Timestamp("2026-10-25", tz="UTC"))    # to 24 Oct 2026 inclusive
NOT_BEFORE = pd.Timestamp("2026-11-02", tz="UTC")
N_FOLDS, SEED, N_BOOT, N_PLACEBO = 5, 20261026, 2000, 200
PLACEBO_WEEKS = (1, 2, 3, 4)
C = 1.0
GATE_PAIRED_GAUGES, GATE_LABELLED = 25, 0.80
GATE_EPISODES, GATE_EP_GAUGES, GATE_EP_SYSTEMS = 150, 15, 6
SKILL_MIN = 0.05
SYSTEM_EPISODES = 5                   # condition 2: river systems with this many test episodes or more
LINE, HIT_MIN, FAR_MAX = 0.5, 0.5, 0.5
LEAD_MIN_H, LEAD_LOOK_H = 1.0, 6
BINS = 10
LO, HI = 2.5, 97.5                    # the 95% interval

# ------------------------------------------------------------------ harness choices (doc, "Harness choices")
FETCH_FROM = pd.Timestamp("2024-11-20", tz="UTC")   # one day before the first issue time, for the 24 h look back
STEP_MAX_H = 1.0          # a rise's two readings: each the last at or before its time, at most this much older
LABEL_NOW_MAX_H = 1.0     # the label's "last reading at or before t": at most this much older than t
HOUR = 3_600_000_000_000  # ns


class StopRule(RuntimeError):
    """A stated rule refuses the run: nothing is scored, and that is reported first."""


def ns(times) -> np.ndarray:
    """UTC times as int64 nanoseconds."""
    idx = pd.DatetimeIndex(times)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return idx.as_unit("ns").asi8


def issue_grid(start=TRAIN[0], end=TEST[1]) -> pd.DatetimeIndex:
    """Every hour on the hour, UTC, from `start` to before `end`."""
    return pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="1h", inclusive="left")


def period(issues, horizon_h: float) -> np.ndarray:
    """"train" or "test" when the issue time and its whole label window (t, t + h] lie in that period, else ""."""
    t = ns(issues)
    h = int(horizon_h * HOUR)
    out = np.full(len(t), "", dtype=object)
    for name, (a, b) in (("train", TRAIN), ("test", TEST)):
        out[(t >= ns([a])[0]) & (t + h <= ns([b])[0])] = name
    return out


# ------------------------------------------------------------------ readings: only ever looked at backwards
@dataclass(frozen=True)
class Readings:
    """A gauge's usable readings, sorted by time (int64 ns, UTC). Inputs read them only through `value` and
    `last_at_or_before`, which never return a reading after the cut they are given."""
    t: np.ndarray
    v: np.ndarray

    @classmethod
    def of(cls, s: pd.Series | None) -> Readings:
        if s is None or len(s) == 0:
            return cls(np.array([], dtype=np.int64), np.array([], dtype=float))
        s = s.dropna()
        t = ns(s.index)
        order = np.argsort(t, kind="stable")
        return cls(t[order], s.to_numpy(dtype=float)[order])

    def last_at_or_before(self, cut: np.ndarray) -> np.ndarray:
        """The index of the last reading at or before each cut; -1 where there is none."""
        cut = np.asarray(cut, dtype=np.int64)
        i = np.searchsorted(self.t, cut, side="right") - 1
        ok = i >= 0
        if ok.any() and not (self.t[i[ok]] <= cut[ok]).all():   # cannot happen; kept as the guard it is
            raise StopRule("a reading after its cut was read")
        return i

    def value(self, cut, oldest) -> np.ndarray:
        """The last reading at or before `cut`, if it is not before `oldest`; NaN otherwise."""
        cut = np.asarray(cut, dtype=np.int64)
        oldest = np.broadcast_to(np.asarray(oldest, dtype=np.int64), cut.shape)
        if len(self.t) == 0:
            return np.full(cut.shape, np.nan)
        i = self.last_at_or_before(cut)
        ii = np.where(i >= 0, i, 0)
        ok = (i >= 0) & (self.t[ii] >= oldest)
        return np.where(ok, self.v[ii], np.nan)


def _round3(x: np.ndarray) -> np.ndarray:
    """Python's round(x, 3), as flows.rise_over_window rounds the rise."""
    return np.array([round(float(a), 3) if np.isfinite(a) else np.nan for a in x], dtype=float)


def site_view(r: Readings, issues, delay_h: float, low: float, rng: float) -> pd.DataFrame:
    """What the site showed at each issue time t from the readings published by then (r <= t - delay_h):
    `index` (the latest published reading at most MAX_AGE_H old, as build_site), `rise` (flows.rise_over_window
    on the newest SITE_TREND_READINGS published readings, as a share of the range) and `word`: "high", "rising
    fast", "none", or "unknown" when there is no published reading at most 24 h old (the site shows nothing)."""
    t = ns(issues)
    cut = t - int(delay_h * HOUR)
    level = r.value(cut, t - int(MAX_AGE_H * HOUR))
    index = (level - low) / rng
    rise = np.full(len(t), np.nan)
    if len(r.t):
        i = r.last_at_or_before(cut)
        first = np.searchsorted(r.t, t - int(SITE_RISE_H * HOUR), side="left")
        j = np.maximum(first, i - (SITE_TREND_READINGS - 1))
        ok = (i >= 0) & (i > j)
        ii, jj = np.where(ok, i, 0), np.where(ok, j, 0)
        ok &= (r.t[ii] - r.t[jj]) >= int(SITE_MIN_SPAN_H * HOUR)
        rise = np.where(ok, _round3(np.where(ok, r.v[ii] - r.v[jj], np.nan)), np.nan) / rng
    word = np.full(len(t), "none", dtype=object)
    known = np.isfinite(index)
    word[~known] = "unknown"
    with np.errstate(invalid="ignore"):
        word[known & (index <= HIGH_INDEX) & (rise > SHARE)] = "rising fast"
        word[known & (index > HIGH_INDEX)] = "high"
    return pd.DataFrame({"site_index": index, "site_rise": rise, "word": word})


def trend_inputs(r: Readings, issues, delay_h: float, low: float, rng: float, rises_h: Iterable[int],
                 prefix: str) -> dict[str, np.ndarray]:
    """A gauge's inputs at each issue time t from readings at or before t - delay_h only: `<prefix>_index` (the
    latest at most MAX_AGE_H old) and `<prefix>_rise<k>`: the reading at the cut minus the reading k hours before
    the cut, each the last at or before its time and at most STEP_MAX_H older, as a share of the EA range."""
    t = ns(issues)
    cut = t - int(delay_h * HOUR)
    step = int(STEP_MAX_H * HOUR)
    out = {f"{prefix}_index": (r.value(cut, t - int(MAX_AGE_H * HOUR)) - low) / rng}
    now = r.value(cut, cut - step)
    for k in rises_h:
        then = r.value(cut - k * HOUR, cut - k * HOUR - step)
        out[f"{prefix}_rise{k}"] = (now - then) / rng
    return out


def missing_inputs(n: int, rises_h: Iterable[int], prefix: str) -> dict[str, np.ndarray]:
    """A slot with no gauge: every input missing."""
    return {f"{prefix}_index": np.full(n, np.nan), **{f"{prefix}_rise{k}": np.full(n, np.nan) for k in rises_h}}


def fill_missing(cols: dict[str, np.ndarray], prefix: str) -> dict[str, np.ndarray]:
    """Missing inputs filled with 0, and `<prefix>_missing` 1 where any of the prefix's inputs was missing."""
    names = [k for k in cols if k.startswith(prefix) and not k.endswith("_missing")]
    miss = np.zeros(len(cols[names[0]]), dtype=bool)
    for k in names:
        miss |= ~np.isfinite(cols[k])
    out = {k: np.where(np.isfinite(cols[k]), cols[k], 0.0) for k in names}
    out[f"{prefix}_missing"] = miss.astype(float)
    return out


def cell_mean(per_cell: list[pd.Series]) -> pd.Series | None:
    """Hourly radar (hour-ending labels) averaged over the cells that have a value that hour."""
    per_cell = [s for s in per_cell if s is not None and len(s)]
    if not per_cell:
        return None
    return pd.concat(per_cell, axis=1).mean(axis=1, skipna=True).sort_index()


def rain_inputs(hourly: pd.Series | None, issues) -> dict[str, np.ndarray]:
    """`rain<k>`: the radar sum over the k hours ending at t - RADAR_DELAY_H, t - RADAR_DELAY_H - 1 h, ...; NaN
    unless every one of those hours has a value. A rolling sum labelled by its last hour reads nothing after it."""
    t = pd.DatetimeIndex(issues)
    cut = t - pd.Timedelta(hours=RADAR_DELAY_H)
    if hourly is None or len(hourly) == 0:
        return {f"rain{k}": np.full(len(t), np.nan) for k in RAIN_SUMS_H}
    s = hourly.copy()
    s.index = pd.DatetimeIndex(s.index).tz_convert("UTC") if pd.DatetimeIndex(s.index).tz else pd.DatetimeIndex(s.index).tz_localize("UTC")
    s = s[~s.index.duplicated()].sort_index()
    s = s.reindex(pd.date_range(s.index[0], s.index[-1], freq="1h"))
    return {f"rain{k}": s.rolling(k, min_periods=k).sum().reindex(cut).to_numpy(dtype=float) for k in RAIN_SUMS_H}


def labels(r: Readings, issues, horizon_h: float, rng: float) -> np.ndarray:
    """1 when the highest reading in (t, t + horizon_h] is more than SHARE of `rng` above the last reading at or
    before t (at most LABEL_NOW_MAX_H old); 0 otherwise; NaN when either side has no reading."""
    t = ns(issues)
    if len(r.t) == 0:
        return np.full(len(t), np.nan)
    now = r.value(t, t - int(LABEL_NOW_MAX_H * HOUR))
    a = np.searchsorted(r.t, t, side="right")
    b = np.searchsorted(r.t, t + int(horizon_h * HOUR), side="right")
    best = np.full(len(t), -np.inf)
    for k in range(int((b - a).max()) if len(t) else 0):
        m = a + k < b
        best[m] = np.maximum(best[m], r.v[a[m] + k])
    ahead = np.where(b > a, best, np.nan)
    with np.errstate(invalid="ignore"):
        y = (ahead - now > SHARE * rng).astype(float)
    return np.where(np.isfinite(now) & np.isfinite(ahead), y, np.nan)


# ------------------------------------------------------------------ gauges and rows
@dataclass
class Upstream:
    ref: str
    low: float
    high: float
    series: pd.Series | None


@dataclass
class Gauge:
    """A spot gauge with its EA range, river system, chosen upstream gauges (the pair on the same river, `same`,
    and the tributary, `trib`; None where there is none) and its hourly radar mean (None without)."""
    ref: str
    system: str
    low: float
    high: float
    series: pd.Series
    same: Upstream | None = None
    trib: Upstream | None = None
    rain: pd.Series | None = None


SPOT_COLS = ["spot_index"] + [f"spot_rise{k}" for k in SPOT_RISES_H] + ["spot_missing"]


def up_cols(slot: str) -> list[str]:
    return [f"{slot}_index"] + [f"{slot}_rise{k}" for k in UP_RISES_H] + [f"{slot}_missing"]


RAIN_COLS = [f"rain{k}" for k in RAIN_SUMS_H] + ["rain_missing"]
LOGISTIC = {"R3": SPOT_COLS, "C1": SPOT_COLS + up_cols("same") + up_cols("trib"),
            "C2": SPOT_COLS + up_cols("same") + up_cols("trib") + RAIN_COLS}


def roll_weeks(s: pd.Series | None, weeks: int) -> pd.Series | None:
    """The placebo's shift: the series moved by a whole number of weeks within itself, wrapping at its ends, on
    its regular grid, so its own gaps move with it and none are added."""
    if s is None or len(s) < 2 or weeks == 0:
        return s
    step = s.index[1] - s.index[0]
    if not (pd.Series(s.index).diff().dropna() == step).all():
        raise StopRule("roll_weeks needs a regular series")
    k = int(pd.Timedelta(weeks=abs(weeks)) / step) * (1 if weeks > 0 else -1)
    return pd.Series(np.roll(s.to_numpy(), k), index=s.index)


def gauge_rows(g: Gauge, issues, delay_h: float, shifts: dict[str, int] | None = None,
               rain_weeks: int = 0) -> pd.DataFrame:
    """One row per issue time for one spot gauge: what the site showed, every model's inputs (filled and
    flagged), the populations, and the labels and periods for each horizon. `shifts` moves upstream series by
    whole weeks and `rain_weeks` the radar (the placebo); the spot gauge's own series never moves."""
    issues = pd.DatetimeIndex(issues)
    n, rng = len(issues), g.high - g.low
    spot = Readings.of(g.series)
    view = site_view(spot, issues, delay_h, g.low, rng)
    cols: dict[str, np.ndarray] = fill_missing(trend_inputs(spot, issues, delay_h, g.low, rng, SPOT_RISES_H, "spot"), "spot")
    cols["spot_index"] = view["site_index"].to_numpy()   # the same reading; never missing in P or A
    for slot, up in (("same", g.same), ("trib", g.trib)):
        if up is None or up.series is None or not (up.high - up.low) > 0:
            raw = missing_inputs(n, UP_RISES_H, slot)
        else:
            s = roll_weeks(up.series, (shifts or {}).get(up.ref, 0))
            raw = trend_inputs(Readings.of(s), issues, delay_h, up.low, up.high - up.low, UP_RISES_H, slot)
        cols.update(fill_missing(raw, slot))
    cols.update(fill_missing(rain_inputs(roll_weeks(g.rain, rain_weeks), issues), "rain"))
    df = pd.DataFrame(cols)
    df.insert(0, "issue", issues)
    df.insert(1, "gauge", g.ref)
    df.insert(2, "system", g.system)
    df["month"] = issues.month
    df["word"] = view["word"].to_numpy()
    df["site_rise"] = view["site_rise"].to_numpy()
    df["in_A"] = np.isfinite(view["site_index"].to_numpy())
    df["in_P"] = df["in_A"] & (df["word"] == "none")
    for h in HORIZONS_H:
        df[f"y{h}"] = labels(spot, issues, h, rng)
        df[f"period{h}"] = period(issues, h)
    return df


def build_rows(gauges: list[Gauge], issues, delay_h: float, folds: dict[str, int],
               shifts: dict[str, int] | None = None, rain_weeks: dict[str, int] | None = None) -> pd.DataFrame:
    out = [gauge_rows(g, issues, delay_h, shifts, (rain_weeks or {}).get(g.ref, 0)) for g in gauges]
    rows = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if len(rows):
        rows["fold"] = rows["system"].map(folds).astype(int)
    return rows


# ------------------------------------------------------------------ river systems and folds
def outlet(graph, node, upstream_m: dict | None = None) -> str:
    """The network outlet a node drains to: the sink reached downstream. Where the river splits and reaches more
    than one, the sink with the most network above it (then the larger name). A loop with no way out is named by
    its smallest node."""
    seen, stack, sinks = {node}, [node], []
    while stack:
        n = stack.pop()
        succ = list(graph.successors(n))
        if not succ:
            sinks.append(n)
        for s in succ:
            if s not in seen:
                seen.add(s)
                stack.append(s)
    if not sinks:
        return str(min(map(str, seen)))
    return str(max(sinks, key=lambda s: ((upstream_m or {}).get(s, 0.0), str(s))))


def system_folds(systems: Iterable[str], n: int = N_FOLDS, seed: int = SEED) -> dict[str, int]:
    """River systems into n folds: sorted, permuted with default_rng(seed), dealt round in turn."""
    keys = sorted(set(map(str, systems)))
    perm = np.random.default_rng(seed).permutation(len(keys))
    return {keys[p]: i % n for i, p in enumerate(perm)}


# ------------------------------------------------------------------ models and references
def fit_predict(Xtr: pd.DataFrame, ytr: np.ndarray, Xte: pd.DataFrame, cols: list[str]) -> np.ndarray:
    """ecoli.fit: logistic regression on standardised inputs, C = 1, not tuned. A training set whose labels are
    all one value predicts that rate; one with no rows predicts nothing (NaN)."""
    if len(ytr) == 0:
        return np.full(len(Xte), np.nan)
    if ytr.min() == ytr.max():
        return np.full(len(Xte), float(np.mean(ytr)))
    from dipcast.model.ecoli import fit
    return fit(Xtr, ytr, cols, C=C).predict(Xte)


def _masks(rows: pd.DataFrame, y: str, per: str, pop: str):
    yv = rows[y].to_numpy(dtype=float)
    pop_m = rows[pop].to_numpy(dtype=bool)
    tr = (rows[per].to_numpy() == "train") & pop_m & np.isfinite(yv)
    te = (rows[per].to_numpy() == "test") & pop_m
    return yv, tr, te


def cross_fold(rows: pd.DataFrame, cols: list[str], y: str, per: str, pop: str) -> np.ndarray:
    """Test-period predictions, in population `pop`, each from a model fitted on the training period of the other
    folds' gauges. A test row gets a prediction whether or not it has a label; NaN outside the test population."""
    yv, tr_all, te_all = _masks(rows, y, per, pop)
    fold = rows["fold"].to_numpy()
    p = np.full(len(rows), np.nan)
    for f in range(N_FOLDS):
        tr, te = tr_all & (fold != f), te_all & (fold == f)
        if te.any():
            p[te] = fit_predict(rows.loc[tr], yv[tr], rows.loc[te], cols)
    return p


def base_rate(rows: pd.DataFrame, y: str, per: str, pop: str) -> np.ndarray:
    """R1: the training share of label 1 by spot gauge and calendar month, in the same population, from the
    gauge's own training period; a gauge-month with no training rows takes the gauge's share, then the pooled one."""
    yv, tr, te = _masks(rows, y, per, pop)
    t = rows.loc[tr].assign(_y=yv[tr])
    by_gm = t.groupby(["gauge", "month"])["_y"].mean()
    by_g = t.groupby("gauge")["_y"].mean()
    pooled = float(t["_y"].mean()) if len(t) else np.nan
    p = np.full(len(rows), np.nan)
    sub = rows.loc[te, ["gauge", "month"]]
    gm = pd.MultiIndex.from_frame(sub)
    v = by_gm.reindex(gm).to_numpy()
    v = np.where(np.isfinite(v), v, by_g.reindex(sub["gauge"]).to_numpy())
    p[te] = np.where(np.isfinite(v), v, pooled)
    return p


def site_words(rows: pd.DataFrame, y: str, per: str, pop: str = "in_A") -> np.ndarray:
    """R2 (population A): the training share of label 1 given the site's word at t, from the other folds' gauges;
    a word with no training rows takes the pooled share."""
    yv, tr_all, te_all = _masks(rows, y, per, pop)
    fold = rows["fold"].to_numpy()
    p = np.full(len(rows), np.nan)
    for f in range(N_FOLDS):
        tr, te = tr_all & (fold != f), te_all & (fold == f)
        if not te.any():
            continue
        t = pd.DataFrame({"word": rows["word"].to_numpy()[tr], "y": yv[tr]})
        rate = t.groupby("word")["y"].mean()
        pooled = float(t["y"].mean()) if len(t) else np.nan
        v = rate.reindex(rows["word"].to_numpy()[te]).to_numpy()
        p[te] = np.where(np.isfinite(v), v, pooled)
    return p


# ------------------------------------------------------------------ metrics
def _ok(*a) -> np.ndarray:
    m = np.ones(len(a[0]), dtype=bool)
    for x in a:
        m &= np.isfinite(np.asarray(x, dtype=float))
    return m


def brier(p, y) -> float:
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    ok = _ok(p, y)
    return float(np.mean((p[ok] - y[ok]) ** 2)) if ok.any() else float("nan")


def skill(p, ref, y) -> float:
    """Brier skill of p against ref, on the rows where both and the label exist."""
    p, ref, y = (np.asarray(a, dtype=float) for a in (p, ref, y))
    ok = _ok(p, ref, y)
    b_ref = brier(ref[ok], y[ok])
    return 1 - brier(p[ok], y[ok]) / b_ref if ok.any() and b_ref > 0 else float("nan")


def auc(p, y) -> float:
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    ok = _ok(p, y)
    if not ok.any() or y[ok].min() == y[ok].max():
        return float("nan")
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y[ok], p[ok]))


def reliability(p, y, bins: int = BINS) -> list[dict]:
    """Ten equal bins of the forecast, 0 to 1 (the last includes 1): rows, mean forecast, observed share."""
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    ok = _ok(p, y)
    p, y = p[ok], y[ok]
    k = np.minimum((p * bins).astype(int), bins - 1)
    out = []
    for b in range(bins):
        m = k == b
        out.append({"bin": f"{b / bins:.1f}-{(b + 1) / bins:.1f}", "n": int(m.sum()),
                    "forecast": float(p[m].mean()) if m.any() else None, "observed": float(y[m].mean()) if m.any() else None})
    return out


def hit_far(p, y, line: float = LINE) -> dict:
    """At the warning line (a forecast at or above it warns): hit rate = hits / events, false-alarm ratio = false
    alarms / warnings."""
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    ok = _ok(p, y)
    w, e = p[ok] >= line, y[ok] == 1
    hits, misses, fa = int((w & e).sum()), int((~w & e).sum()), int((w & ~e).sum())
    return {"hits": hits, "misses": misses, "false_alarms": fa,
            "hit_rate": hits / (hits + misses) if hits + misses else float("nan"),
            "false_alarm_ratio": fa / (hits + fa) if hits + fa else float("nan")}


def cluster_skill(y, p, ref, clusters, n: int = N_BOOT, seed: int = SEED) -> dict:
    """Brier skill of p against ref, point and 95% interval from a cluster bootstrap: river systems drawn with
    replacement (sorted order), n draws, default_rng(seed). Skill on a draw is 1 - SSE(p) / SSE(ref) over its rows."""
    y, p, ref = (np.asarray(a, dtype=float) for a in (y, p, ref))
    ok = _ok(y, p, ref)
    cl = np.asarray(clusters)[ok]
    keys = np.array(sorted(set(cl.tolist())))
    if len(keys) == 0:
        return {"d": float("nan"), "L": float("nan"), "U": float("nan"), "clusters": 0}
    pos = np.searchsorted(keys, cl)
    sse_p = np.bincount(pos, (p[ok] - y[ok]) ** 2, minlength=len(keys))
    sse_r = np.bincount(pos, (ref[ok] - y[ok]) ** 2, minlength=len(keys))
    rng = np.random.default_rng(seed)
    draws = np.empty(n)
    for i in range(n):
        cnt = np.bincount(rng.integers(0, len(keys), len(keys)), minlength=len(keys))
        den = cnt @ sse_r
        draws[i] = 1 - (cnt @ sse_p) / den if den > 0 else np.nan
    good = draws[np.isfinite(draws)]
    d = 1 - sse_p.sum() / sse_r.sum() if sse_r.sum() > 0 else float("nan")
    return {"d": float(d), "L": float(np.percentile(good, LO)) if len(good) else float("nan"),
            "U": float(np.percentile(good, HI)) if len(good) else float("nan"), "clusters": int(len(keys)),
            "draws_without_value": int(n - len(good))}


def episodes(rows: pd.DataFrame, y: str, pop: str) -> pd.DataFrame:
    """Runs of label 1 at consecutive hourly issue times of one gauge, inside the population: gauge, system,
    start, hours."""
    hit = rows[(rows[y] == 1) & rows[pop].astype(bool)].sort_values(["gauge", "issue"])
    if hit.empty:
        return pd.DataFrame(columns=["gauge", "system", "start", "hours"])
    new = (hit["gauge"] != hit["gauge"].shift()) | (hit["issue"] - hit["issue"].shift() != pd.Timedelta(hours=1))
    run = new.cumsum()
    g = hit.groupby(run)
    return pd.DataFrame({"gauge": g["gauge"].first(), "system": g["system"].first(), "start": g["issue"].first(),
                         "hours": g.size()}).reset_index(drop=True)


def lead_gained(rows: pd.DataFrame, p_col: str, line: float = LINE, look_h: int = LEAD_LOOK_H) -> pd.DataFrame:
    """For each test onset of the site's own "rising fast" (the word at t0 is "rising fast" and at t0 - 1 h was
    "none"), with its look-back window inside the test period: lead_h, the hours from the first issue time,
    within the look_h before t0, from which the forecast stayed at or above `line` up to t0 - 1 h (0 if not at
    t0 - 1 h). An issue time without a forecast breaks the run."""
    out = []
    lo, hi = TEST[0] + pd.Timedelta(hours=look_h), TEST[1]
    for (gauge, system), g in rows.groupby(["gauge", "system"], sort=True):
        g = g.set_index("issue").sort_index()
        full = pd.date_range(g.index.min(), g.index.max(), freq="1h")
        word = g["word"].reindex(full)
        p = g[p_col].reindex(full).to_numpy(dtype=float)
        w = word.to_numpy()
        for k in np.flatnonzero((w[1:] == "rising fast") & (w[:-1] == "none")) + 1:
            t0 = full[k]
            if not (lo <= t0 < hi):
                continue
            lead = 0
            for j in range(1, look_h + 1):
                if k - j >= 0 and np.isfinite(p[k - j]) and p[k - j] >= line:
                    lead = j
                else:
                    break
            out.append({"gauge": gauge, "system": system, "onset": t0, "lead_h": float(lead), "caught": lead > 0})
    return pd.DataFrame(out, columns=["gauge", "system", "onset", "lead_h", "caught"])


# ------------------------------------------------------------------ gate, conditions, placebo, labels
def gate(rows: pd.DataFrame, paired_gauges: int, y: str = f"y{PRIMARY_H}", per: str = f"period{PRIMARY_H}") -> dict:
    """Checked before any score, from labels and populations only (rows at d = 1 h)."""
    share = {}
    for name in ("train", "test"):
        m = rows[per] == name
        share[name] = float(rows.loc[m, y].notna().mean()) if m.any() else 0.0
    ep = episodes(rows[rows[per] == "test"], y, "in_P")
    n_g, n_s = int(ep["gauge"].nunique()), int(ep["system"].nunique())
    ok = (paired_gauges >= GATE_PAIRED_GAUGES and all(v >= GATE_LABELLED for v in share.values())
          and len(ep) >= GATE_EPISODES and n_g >= GATE_EP_GAUGES and n_s >= GATE_EP_SYSTEMS)
    return {"paired_gauges": int(paired_gauges), "labelled_share": share, "episodes": int(len(ep)),
            "gauges_with_episode": n_g, "systems_with_episode": n_s,
            "episodes_by_system": {str(k): int(v) for k, v in ep.groupby("system").size().items()},
            "judged": bool(ok)}


def placebo_shifts(refs: Iterable[str], n: int = N_PLACEBO, seed: int = SEED) -> list[dict[str, int]]:
    """For each of n draws, each series (sorted refs) gets a whole number of weeks, 1 to 4, and a random sign."""
    keys = sorted(set(refs))
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        d = {}
        for k in keys:
            w = int(rng.integers(PLACEBO_WEEKS[0], PLACEBO_WEEKS[-1] + 1))
            d[k] = w * int(rng.choice((-1, 1)))
        out.append(d)
    return out


def placebo_holds(real_gain: float, gains) -> dict:
    g = np.asarray(gains, dtype=float)
    g = g[np.isfinite(g)]
    p95 = float(np.percentile(g, 95)) if len(g) else float("nan")
    return {"real_gain": float(real_gain), "p95": p95, "draws": int(len(g)),
            "at_or_above_real": int((g >= real_gain).sum()), "holds": bool(len(g) and real_gain > p95)}


def systems_needed(n: int) -> int:
    return math.ceil(2 * n / 3)


def conditions(y, p_new, p_ref, systems, system_episodes: dict[str, int], leads: pd.DataFrame, skill_sens: float,
               placebo: dict, boot: dict | None = None) -> dict:
    """The six pass conditions for one candidate against its reference (population P, 3 h)."""
    y, p_new, p_ref = (np.asarray(a, dtype=float) for a in (y, p_new, p_ref))
    systems = np.asarray(systems)
    b = boot or cluster_skill(y, p_new, p_ref, systems)
    c1 = {**b, "holds": bool(b["d"] >= SKILL_MIN and b["L"] > 0)}
    judged = sorted(s for s, n in system_episodes.items() if n >= SYSTEM_EPISODES)
    per = {s: skill(p_new[systems == s], p_ref[systems == s], y[systems == s]) for s in judged}
    pos = sum(1 for v in per.values() if np.isfinite(v) and v > 0)
    c2 = {"by_system": per, "positive": pos, "systems": len(judged), "needed": systems_needed(len(judged)),
          "holds": bool(len(judged) > 0 and pos >= systems_needed(len(judged)))}
    hf = hit_far(p_new, y)
    c3 = {**hf, "holds": bool(hf["hit_rate"] >= HIT_MIN and hf["false_alarm_ratio"] <= FAR_MAX)}
    caught = leads[leads["caught"]] if len(leads) else leads
    med = float(caught["lead_h"].median()) if len(caught) else float("nan")
    c4 = {"onsets": int(len(leads)), "caught": int(len(caught)), "median_lead_h": med,
          "holds": bool(len(caught) and med >= LEAD_MIN_H)}
    c5 = {"skill_d3": float(skill_sens), "holds": bool(np.isfinite(skill_sens) and skill_sens > 0)}
    c6 = dict(placebo)
    return {"1": c1, "2": c2, "3": c3, "4": c4, "5": c5, "6": c6}


def nearmiss_label(d: float, L: float, U: float, B: float, H: float, secondary_harm: bool = False) -> str:
    """The near-miss labels of the 26 October addendum (docs/LAKE-ECOLI-LINE-TEST-2026-10.md): the first that fits."""
    if d >= B and L > 0:
        return "Better"
    if d > 0 and L <= 0 and L > -H and not secondary_harm:
        return "Promising, not shown"
    if -H < L and U < B:
        return "No useful difference"
    if L <= -H and d <= 0:
        return "Possible harm"
    if U < 0:
        return "Harm"
    if L <= -H and U >= B:
        return "Too uncertain"
    return "Unlabelled"


# A secondary comparison with either label blocks "Promising, not shown". In the addendum's order "Harm" can never
# be reached (see the doc's questions), so "Possible harm" is counted too: the stricter reading.
SECONDARY_HARM = {"Harm", "Possible harm"}


def verdict(gate_judged: bool, conds: dict) -> str:
    if not gate_judged:
        return "Too few to judge: description only"
    return "Passes" if all(c["holds"] for c in conds.values()) else "Fails"


# ------------------------------------------------------------------ the run statement
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_statement(path: Path, predictions_sha: str, candidates=("C1", "C2")) -> dict:
    """The run statement, written from predictions alone before any outcome is read: JSON with
    "predictions_sha256" (the predictions file it was written from), "margins": {"C1": {"B": .., "H": ..}, ...}
    in Brier-skill units, and "working" (how B and H were worked out). Refused unless it names these predictions
    and every margin has 0 <= H <= B and B > 0."""
    if path is None or not Path(path).exists():
        raise StopRule("no run statement: write B and H from the predictions first")
    s = json.loads(Path(path).read_text())
    if s.get("predictions_sha256", "").strip().lower() != predictions_sha:
        raise StopRule("the statement names other predictions than these")
    if not str(s.get("working", "")).strip():
        raise StopRule("the statement does not show how B and H were worked out")
    for c in candidates:
        m = (s.get("margins") or {}).get(c)
        if not m or not (float(m["B"]) > 0 and 0 <= float(m["H"]) <= float(m["B"])):
            raise StopRule(f"margins for {c} missing or not 0 <= H <= B, B > 0")
    return s
