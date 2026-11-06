"""docs/RIVER-RISES-C3-2026-11.md: the C3 candidate, developed on seen data, frozen, then read on the fresh week.

    # development on seen data (21 Nov 2024 to 24 Oct 2026): blocked, embargoed, grouped splits
    uv run python scripts/river_rises_eval/c3.py develop --data <fetch_c3 out> --out <run dir>
    # the frozen models: fitted on every seen row, written with their SHA-256 (commit before `fresh`)
    uv run python scripts/river_rises_eval/c3.py freeze --data <fetch_c3 out> --out <run dir>
    # the fresh week, 25 to 31 October 2026: needs a statement naming the frozen file's SHA-256
    uv run python scripts/river_rises_eval/c3.py fresh --data <fetch_c3 out> --out <run dir> --frozen <file> --statement <file>

Offline: reads fetch_c3.py's tables and series and the saved radar months; makes no request. `develop` and `freeze`
cut every series at DEV_END before anything is built, so no reading after 24 October 2026 can enter them. Research
only: nothing here feeds the site. The #627 harness (protocol.py, score.py) is used unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from river_rises_eval import protocol as pr  # noqa: E402
from river_rises_eval import score as sc  # noqa: E402

# ------------------------------------------------------------------ fixed by the protocol (docs/RIVER-RISES-C3-2026-11.md)
UTC_ = "UTC"
BLOCK_EDGES = pd.DatetimeIndex(["2024-11-21", "2025-02-01", "2025-05-01", "2025-08-01", "2025-11-01", "2026-02-01",
                                "2026-05-01", "2026-08-01", "2026-10-25"], tz=UTC_)
DEV_START, DEV_END = BLOCK_EDGES[0], BLOCK_EDGES[-1]
EMBARGO = pd.Timedelta(days=7)
M_MONTH, M_GAUGE = 240.0, 2400.0            # prior weights, in issue hours, of the smoothed base rate R1s
BR_CLIP = (1e-4, 0.5)
NEW_SYSTEM_SEED = 20261027                  # folds for the river systems only the extra gauges bring
ALERT_RATES = (0.005, 0.01, 0.02)
FORWARD_BLOCKS = tuple(range(2, 8))         # forward-only sensitivity: blocks 3 to 8
FRESH = (pd.Timestamp("2026-10-25", tz=UTC_), pd.Timestamp("2026-11-01", tz=UTC_))   # label windows inside
CONFIGS = {"H1": ("own", 3, 1.0), "H05": ("own", 3, 0.5), "H3": ("own", 3, 3.0), "H6": ("own", 6, 1.0),
           "N1": ("all", 3, 1.0)}
MAIN = "H1"
COLS = {"R3": pr.LOGISTIC["R3"], "C2": pr.LOGISTIC["C2"], "C3": pr.LOGISTIC["C2"] + ["br_logit"],
        "C3n": pr.SPOT_COLS + pr.RAIN_COLS + ["br_logit"]}
MODELS = {"own": ("R1", "R1s", "R3", "C2", "C3"), "all": ("R1", "R1s", "R3", "C3n")}
PAIRS = {"own": (("C3", "R3"), ("C3", "R1"), ("C3", "R1s"), ("C3", "C2"), ("C2", "R3"), ("C2", "R1"), ("R1", "R3")),
         "all": (("C3n", "R3"), ("C3n", "R1"), ("C3n", "R1s"), ("R1", "R3"))}
DAY = pd.Timedelta(days=1)


# ------------------------------------------------------------------ gauges, folds, rows
def new_system_folds(own: dict[str, int], systems) -> dict[str, int]:
    """#627's folds for its systems; any other system sorted, permuted with NEW_SYSTEM_SEED, dealt round."""
    extra = sorted(set(map(str, systems)) - set(own))
    perm = np.random.default_rng(NEW_SYSTEM_SEED).permutation(len(extra))
    return {**own, **{extra[p]: i % pr.N_FOLDS for i, p in enumerate(perm)}}


def cut(s: pd.Series | None, end: pd.Timestamp) -> pd.Series | None:
    """The series before `end` only: nothing at or after it can be read."""
    if s is None:
        return None
    idx = pd.DatetimeIndex(s.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return pd.Series(s.to_numpy(), index=idx)[idx < end]


def load(data: Path, radar: Path | None, end: pd.Timestamp) -> tuple[list[pr.Gauge], set[str], dict[str, int], dict]:
    """Every spot gauge with a series and a range (the 33 of #627 and the 12 it left out), each series and radar
    mean cut at `end`, then #627's datum rule. Returns the kept gauges, the refs of the 33, the folds and the
    datum figures."""
    g = pd.read_csv(data / "gauges.csv", dtype={"gauge": str, "system": str, "why": str, "measure": str}).fillna({"why": ""})
    g = g[g["measure"].notna() & (g["high"] > g["low"])]
    slots = pd.read_csv(data / "slots.csv", dtype={"gauge": str, "up": str, "measure": str})
    cells = pd.read_csv(data / "radar_cells.csv", dtype={"gauge": str, "cell": str})
    gauges = []
    for r in g.sort_values("gauge").itertuples(index=False):
        ups = {s.slot: pr.Upstream(s.up, float(s.low), float(s.high),
                                   cut(sc.read_series(data / "series" / f"{s.measure}.parquet"), end))
               for s in slots[slots["gauge"] == r.gauge].itertuples(index=False)}
        gauges.append(pr.Gauge(r.gauge, str(r.system), float(r.low), float(r.high),
                               cut(sc.read_series(data / "series" / f"{r.measure}.parquet"), end),
                               ups.get("same"), ups.get("trib"), cut(sc.read_rain(cells[cells["gauge"] == r.gauge], radar), end)))
    own_refs = set(g.loc[g["why"] == "", "gauge"])
    folds = new_system_folds(pr.system_folds(g.loc[g["why"] == "", "system"]), g["system"])
    kept, datum = pr.datum_rule(gauges)
    return kept, own_refs, folds, datum


def blocks_of(issues: pd.Series, h: int) -> tuple[np.ndarray, np.ndarray]:
    """(vblock, blk): vblock is the block holding the whole label window (t, t + h], else -1; blk is the block
    holding the issue time itself, else -1."""
    t = pd.DatetimeIndex(issues)
    blk = np.searchsorted(BLOCK_EDGES, t, side="right") - 1
    blk = np.where((t >= DEV_START) & (t < DEV_END), blk, -1)
    end_blk = np.searchsorted(BLOCK_EDGES, t + pd.Timedelta(hours=h), side="left") - 1
    vblock = np.where((blk >= 0) & (end_blk == blk), blk, -1)
    return vblock, blk


def zone(b: int, h: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Block b widened by the embargo, with the label horizon: an issue time in [a, z) has a label window that
    touches block b +- EMBARGO."""
    return BLOCK_EDGES[b] - EMBARGO - pd.Timedelta(hours=h), BLOCK_EDGES[b + 1] + EMBARGO


# ------------------------------------------------------------------ base rates: the gauge's own history, by time only
def day_counts(rows: pd.DataFrame, y: str) -> pd.DataFrame:
    """Labelled population-P rows summed by gauge, UTC day and calendar month: label-1 count and labelled hours."""
    m = rows["in_P"].to_numpy(dtype=bool) & rows[y].notna().to_numpy()
    d = rows.loc[m, ["gauge", "issue", "month", y]].copy()
    d["day"] = pd.DatetimeIndex(d["issue"]).floor("D")
    out = d.groupby(["gauge", "day", "month"], observed=True)[y].agg(["sum", "count"]).reset_index()
    out["gauge"] = out["gauge"].astype(str)
    return out


def base_tables(dc: pd.DataFrame, excl: list[tuple[pd.Timestamp, pd.Timestamp]]) -> dict:
    """Counts from the days that do not touch any excluded interval (whole days: at least the stated embargo)."""
    keep = np.ones(len(dc), dtype=bool)
    day = pd.DatetimeIndex(dc["day"])
    for a, z in excl:
        keep &= ~((day + DAY > a) & (day < z))
    k = dc[keep]
    gm = k.groupby(["gauge", "month"])[["sum", "count"]].sum()
    g = k.groupby("gauge")[["sum", "count"]].sum()
    tot = k[["sum", "count"]].sum()
    return {"gm": gm, "g": g, "pool": float(tot["sum"] / tot["count"]) if tot["count"] > 0 else float("nan")}


def rates(tab: dict, gauges, months) -> tuple[np.ndarray, np.ndarray]:
    """(R1, R1s) for each (gauge, month). R1: #627's base rate (gauge-month share, then the gauge's, then pooled).
    R1s: the gauge-month count shrunk to the gauge's rate (weight M_MONTH), itself shrunk to the pooled rate
    (weight M_GAUGE)."""
    key = pd.MultiIndex.from_arrays([np.asarray(gauges, dtype=str), np.asarray(months, dtype=int)])
    gm = tab["gm"].reindex(key)
    g = tab["g"].reindex(np.asarray(gauges, dtype=str))
    pool = tab["pool"]
    y_gm, n_gm = gm["sum"].fillna(0).to_numpy(float), gm["count"].fillna(0).to_numpy(float)
    y_g, n_g = g["sum"].fillna(0).to_numpy(float), g["count"].fillna(0).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        r1 = np.where(n_gm > 0, y_gm / n_gm, np.where(n_g > 0, y_g / n_g, pool))
        r_g = (y_g + M_GAUGE * pool) / (n_g + M_GAUGE)
        r1s = (y_gm + M_MONTH * r_g) / (n_gm + M_MONTH)
    return r1, r1s


def br_logit(r1s: np.ndarray) -> np.ndarray:
    p = np.clip(r1s, *BR_CLIP)
    return np.log(p / (1 - p))


# ------------------------------------------------------------------ fits
def fit_model(X: pd.DataFrame, y: np.ndarray, cols: list[str]):
    from dipcast.model.ecoli import EcoliModel, fit
    if len(y) == 0:
        return None
    if y.min() == y.max():
        return EcoliModel({}, float(np.log(max(y.mean(), 1e-6) / max(1 - y.mean(), 1e-6))), {}, {}, {"constant": True})
    return fit(X, y, cols, C=pr.C)


def threshold(p_train: np.ndarray, q: float) -> float:
    """The alert threshold for alert rate q: that upper quantile of the model's own predictions on its training rows."""
    p = p_train[np.isfinite(p_train)]
    return float(np.quantile(p, 1 - q)) if len(p) else float("nan")


def cross_validate(rows: pd.DataFrame, models: tuple[str, ...], h: int, forward: bool = False) -> pd.DataFrame:
    """Validation predictions for every population-P row whose label window lies in one block, each from a model
    fitted on the other folds' rows outside that block +- EMBARGO (forward: only rows ending EMBARGO before it),
    with base rates from the row's own gauge outside the same zone. Thresholds per fold-block cell."""
    y = f"y{h}"
    issue = pd.DatetimeIndex(rows["issue"])
    vblock, blk = blocks_of(rows["issue"], h)
    in_p = rows["in_P"].to_numpy(dtype=bool)
    lab = rows[y].notna().to_numpy()
    fold = rows["fold"].to_numpy()
    gauges, months = rows["gauge"].astype(str).to_numpy(), rows["month"].to_numpy(dtype=int)
    yv = rows[y].to_numpy(dtype=float)
    dc = day_counts(rows, y)
    out = {m: np.full(len(rows), np.nan) for m in models}
    thr = {(m, q): np.full(len(rows), np.nan) for m in models for q in ALERT_RATES}
    blocks = FORWARD_BLOCKS if forward else range(len(BLOCK_EDGES) - 1)
    for b in blocks:
        a, z = zone(b, h)
        if forward:
            z = pd.Timestamp.max.tz_localize("UTC")
        out_zone = ~((issue >= a) & (issue < z))
        val_b = (vblock == b) & in_p
        if not val_b.any():
            continue
        r1_v, r1s_v = rates(base_tables(dc, [(a, z)]), gauges[val_b], months[val_b])
        br_tr = {"R1": np.full(len(rows), np.nan), "R1s": np.full(len(rows), np.nan)}
        for bp in range(len(BLOCK_EDGES) - 1):
            sel = (blk == bp) & out_zone & in_p & lab
            if not sel.any():
                continue
            r1_t, r1s_t = rates(base_tables(dc, [(a, z), zone(bp, h)]), gauges[sel], months[sel])
            br_tr["R1"][sel], br_tr["R1s"][sel] = r1_t, r1s_t
        for f in range(pr.N_FOLDS):
            v = val_b & (fold == f)
            tr = (fold != f) & out_zone & in_p & lab
            if not v.any():
                continue
            Xv = rows.loc[v].assign(br_logit=br_logit(r1s_v[np.flatnonzero(v[val_b])]))
            Xt = rows.loc[tr].assign(br_logit=br_logit(br_tr["R1s"][tr]))
            for m in models:
                if m in ("R1", "R1s"):
                    pv = (r1_v if m == "R1" else r1s_v)[np.flatnonzero(v[val_b])]
                    pt = br_tr[m][tr]
                else:
                    model = fit_model(Xt, yv[tr], COLS[m])
                    pv = model.predict(Xv) if model else np.full(int(v.sum()), np.nan)
                    pt = model.predict(Xt) if model else np.array([])
                out[m][v] = pv
                for q in ALERT_RATES:
                    thr[(m, q)][v] = threshold(pt, q)
    res = rows.loc[:, ["gauge", "system", "issue", "fold", "word", "in_P", y]].copy()
    res["vblock"] = vblock
    for m in models:
        res[m] = out[m]
        for q in ALERT_RATES:
            res[f"thr_{m}_{q}"] = thr[(m, q)]
    return res


# ------------------------------------------------------------------ metrics
def calibration(p, y) -> dict:
    """Calibration-in-the-large (mean forecast minus observed rate) and the intercept and slope of a logistic fit of
    the label on the forecast's logit (1 and 0 for a perfectly calibrated forecast's slope and intercept)."""
    from sklearn.linear_model import LogisticRegression
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(p) & np.isfinite(y)
    p, y = p[ok], y[ok]
    out = {"mean_forecast": float(p.mean()), "observed": float(y.mean()), "citl": float(p.mean() - y.mean())}
    if y.min() == y.max():
        return {**out, "intercept": float("nan"), "slope": float("nan")}
    x = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(x, y)
    return {**out, "intercept": float(lr.intercept_[0]), "slope": float(lr.coef_[0][0])}


def quantile_reliability(p, y, bins: int = pr.BINS) -> list[dict]:
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(p) & np.isfinite(y)
    p, y = p[ok], y[ok]
    order = np.argsort(p, kind="stable")
    out = []
    for k, idx in enumerate(np.array_split(order, bins)):
        out.append({"bin": k + 1, "n": int(len(idx)), "forecast": float(p[idx].mean()), "observed": float(y[idx].mean()),
                    "low": float(p[idx].min()), "high": float(p[idx].max())})
    return out


def onset_leads(res: pd.DataFrame, alert: np.ndarray, look_h: int = pr.LEAD_LOOK_H) -> pd.DataFrame:
    """#627's lead per onset with an alert flag instead of the 0.5 line: for each onset of the site's own "rising
    fast" (word at t0 "rising fast", at t0 - 1 h "none"), with its look-back inside the rows, the hours from the first
    issue time from which the alert stayed on up to t0 - 1 h. An hour without a forecast breaks the run."""
    out = []
    d = res.assign(_a=np.asarray(alert, dtype=float))
    for (gauge, system), g in d.groupby(["gauge", "system"], sort=True):
        g = g.set_index("issue").sort_index()
        full = pd.date_range(g.index.min(), g.index.max(), freq="1h")
        w = g["word"].astype(object).reindex(full).to_numpy()
        a = g["_a"].reindex(full).to_numpy(dtype=float)
        for k in np.flatnonzero((w[1:] == "rising fast") & (w[:-1] == "none")) + 1:
            if k - look_h < 0:
                continue
            lead = 0
            for j in range(1, look_h + 1):
                if np.isfinite(a[k - j]) and a[k - j] > 0:
                    lead = j
                else:
                    break
            out.append({"gauge": gauge, "system": system, "onset": full[k], "lead_h": float(lead), "caught": lead > 0,
                        "forecast_at_t0_1": bool(np.isfinite(a[k - 1]))})
    return pd.DataFrame(out, columns=["gauge", "system", "onset", "lead_h", "caught", "forecast_at_t0_1"])


def alert_table(res: pd.DataFrame, y: str, m: str, q: float, scored: np.ndarray) -> dict:
    """Alerts at alert rate q on every row of `res` (all hours, so the site's onsets are visible); scored only on
    the `scored` rows (population P with every compared model's prediction)."""
    p, thr, yy = (res[c].to_numpy(dtype=float) for c in (m, f"thr_{m}_{q}", y))
    ok = np.isfinite(p) & np.isfinite(thr) & scored
    alert = np.where(ok, (p >= thr).astype(float), np.nan)
    sc_ = ok & np.isfinite(yy)
    w, e = alert[sc_] == 1, yy[sc_] == 1
    hits, misses, fa = int((w & e).sum()), int((~w & e).sum()), int((w & ~e).sum())
    ep = pr.episodes(res.assign(**{"in_P": ok & res["in_P"].to_numpy(dtype=bool)}), y, "in_P")
    first = res.assign(_a=alert).set_index(["gauge", "issue"])["_a"]
    warned = first.reindex(pd.MultiIndex.from_arrays([ep["gauge"].astype(str), ep["start"]])).to_numpy() == 1 if len(ep) else np.array([])
    leads = onset_leads(res, alert)
    caught = leads[leads["caught"] & leads["forecast_at_t0_1"]]
    judged = leads[leads["forecast_at_t0_1"]]
    return {"alert_rate": q, "threshold_median": float(np.nanmedian(thr[ok])) if ok.any() else float("nan"),
            "alert_share": float(np.nanmean(alert[sc_])) if sc_.any() else float("nan"),
            "hits": hits, "misses": misses, "false_alarms": fa,
            "hit_rate": hits / (hits + misses) if hits + misses else float("nan"),
            "false_alarm_ratio": fa / (hits + fa) if hits + fa else float("nan"),
            "episodes": int(len(ep)), "episodes_warned_first_hour": int(np.sum(warned)),
            "onsets": int(len(leads)), "onsets_with_forecast": int(len(judged)), "onsets_caught": int(len(caught)),
            "lead_h": {k: (float(caught["lead_h"].quantile(v)) if len(caught) else float("nan"))
                       for k, v in (("p25", .25), ("median", .5), ("p75", .75))},
            "caught_2h_or_more": int((caught["lead_h"] >= 2).sum())}


def evaluate(res: pd.DataFrame, y: str, models: tuple[str, ...], pairs, with_alerts: bool = True,
             bootstrap: bool = True) -> dict:
    scored = res["in_P"].to_numpy(dtype=bool)
    for m in models:
        scored &= np.isfinite(res[m].to_numpy(dtype=float))
    sub = res[scored]
    yy = sub[y].to_numpy(dtype=float)
    out = {"rows": int(len(sub)), "rows_with_label": int(np.isfinite(yy).sum()), "events": int(np.nansum(yy)),
           "gauges": int(sub["gauge"].nunique()), "systems": int(sub["system"].nunique()), "models": {}, "pairs": {}}
    for m in models:
        p = sub[m].to_numpy(dtype=float)
        out["models"][m] = {"brier": pr.brier(p, yy), "auc": pr.auc(p, yy), "calibration": calibration(p, yy),
                            "reliability": pr.reliability(p, yy), "quantile_reliability": quantile_reliability(p, yy)}
        if with_alerts:
            out["models"][m]["alerts"] = [alert_table(res, y, m, q, scored) for q in ALERT_RATES]
    for c, r in pairs:
        if c not in sub or r not in sub:
            continue
        d = {"skill": pr.skill(sub[c], sub[r], yy)}
        if bootstrap:
            d["by_system"] = pr.cluster_skill(yy, sub[c], sub[r], sub["system"])
            d["by_block"] = pr.cluster_skill(yy, sub[c], sub[r], sub["vblock"])
        out["pairs"][f"{c} vs {r}"] = d
    return out


def per_system(res: pd.DataFrame, y: str, c: str, r: str) -> dict:
    sub = res[res["in_P"].to_numpy(dtype=bool) & np.isfinite(res[c].to_numpy(dtype=float)) & np.isfinite(res[r].to_numpy(dtype=float))]
    ep = pr.episodes(sub, y, "in_P").groupby("system").size()
    return {str(s): {"episodes": int(ep.get(s, 0)), "skill": pr.skill(g[c], g[r], g[y]), "events": int(np.nansum(g[y]))}
            for s, g in sub.groupby("system")}


# ------------------------------------------------------------------ stages
def build(gauges, folds, delay_h: float, start=DEV_START, end=DEV_END) -> pd.DataFrame:
    issues = pd.date_range(start, end, freq="1h", inclusive="left")
    rows = pr.build_rows(gauges, issues, delay_h, folds)
    rows["gauge"] = rows["gauge"].astype(str)
    return rows


def stage_develop(args) -> dict:
    gauges, own, folds, datum = load(args.data, args.radar, DEV_END)
    args.out.mkdir(parents=True, exist_ok=True)
    res_all, out = {}, {"made": datetime.now(UTC).isoformat(timespec="seconds"), "datum": datum,
                        "gauges": {"own": sorted(g.ref for g in gauges if g.ref in own),
                                   "all": sorted(g.ref for g in gauges)}, "folds": folds, "configs": {}}
    rows_by_delay = {}
    for name, (who, h, d) in CONFIGS.items():
        if d not in rows_by_delay:
            rows_by_delay[d] = build(gauges, folds, d)
        rows = rows_by_delay[d]
        rows = rows[rows["gauge"].isin(own)] if who == "own" else rows
        res = cross_validate(rows.reset_index(drop=True), MODELS[who], h)
        res_all[name] = res.assign(config=name)
        ev = evaluate(res, f"y{h}", MODELS[who], PAIRS[who])
        if name in (MAIN, "N1"):
            c = "C3" if who == "own" else "C3n"
            ev["by_system"] = {k: per_system(res, f"y{h}", c, k) for k in ("R3", "R1")}
        out["configs"][name] = ev
        print(f"{name}: done", flush=True)
    rows = rows_by_delay[pr.DELAY_H]
    fwd = cross_validate(rows[rows["gauge"].isin(own)].reset_index(drop=True), ("R1", "R3", "C3"), pr.PRIMARY_H, forward=True)
    blocked = res_all[MAIN]
    keyc = ["gauge", "issue"]
    both = fwd.merge(blocked[keyc + ["R1", "R3", "C3"]].rename(columns={"R1": "R1_b", "R3": "R3_b", "C3": "C3_b"}), on=keyc)
    both = both[np.isfinite(both["C3"]) & np.isfinite(both["C3_b"])]
    yy = both["y3"].to_numpy(dtype=float)
    out["forward_only"] = {"blocks": [int(b) + 1 for b in FORWARD_BLOCKS], "rows": int(len(both)), "events": int(np.nansum(yy)),
                           "forward": {k: pr.cluster_skill(yy, both["C3"], both[k], both["system"]) for k in ("R1", "R3")},
                           "blocked_same_rows": {k: pr.cluster_skill(yy, both["C3_b"], both[f"{k}_b"], both["system"]) for k in ("R1", "R3")}}
    out["coverage"] = coverage(args.data, gauges, own)
    pred = pd.concat(res_all.values(), ignore_index=True)
    pred["word"] = pred["word"].astype(str)
    path = args.out / "c3_dev_predictions.parquet"
    pred.to_parquet(path, index=False)
    out["predictions_sha256"] = pr.sha256(path)
    (args.out / "c3_dev.json").write_text(json.dumps(out, indent=1, default=str))
    write_report(out, args.out / "c3_dev.md", "Development on seen data")
    print((args.out / "c3_dev.md").read_text())
    return out


def coverage(data: Path, gauges, own) -> dict:
    g = pd.read_csv(data / "gauges.csv", dtype={"gauge": str, "why": str, "measure": str}).fillna({"why": ""})
    cells = pd.read_csv(data / "radar_cells.csv", dtype={"gauge": str})
    kept = {x.ref for x in gauges}
    radar = set(cells.loc[cells["saved_months"] > 0, "gauge"])
    rows = []
    for r in g.itertuples(index=False):
        spots = [s for s in str(r.spots).split(";") if s]
        if r.gauge in kept and r.gauge in own:
            cov = "C3 and C3n"
        elif r.gauge in kept:
            cov = "C3n only (no upstream gauge)"
        elif pd.isna(r.measure):
            cov = "none: no Hydrology series for R1's history"
        else:
            cov = "none: " + (r.why or "dropped by the datum rule")
        rows.append({"gauge": r.gauge, "label": r.label, "spots": len(spots), "covered": cov, "radar_saved": r.gauge in radar})
    t = pd.DataFrame(rows)
    by = t.groupby("covered").agg(gauges=("gauge", "size"), spots=("spots", "sum")).reset_index().to_dict("records")
    return {"river_spots": 72, "spots_with_usable_gauge": int(t["spots"].sum()),
            "spots_without_usable_gauge": 72 - int(t["spots"].sum()), "by_coverage": by,
            "covered_without_saved_radar": t[(~t["covered"].str.startswith("none")) & (~t["radar_saved"])]["label"].tolist(),
            "gauges": rows}


def stage_freeze(args) -> dict:
    """Every frozen model fitted on all seen rows (d = 1 h, 3 h, population P); base-rate tables from all seen rows;
    training rows' br_logit from their gauge's rows outside their own block +- EMBARGO; alert thresholds from the
    training predictions."""
    from dipcast.model.ecoli import EcoliModel  # noqa: F401  (the frozen models are EcoliModel fields)
    gauges, own, folds, datum = load(args.data, args.radar, DEV_END)
    h, y = pr.PRIMARY_H, f"y{pr.PRIMARY_H}"
    rows = build(gauges, folds, pr.DELAY_H)
    _, blk = blocks_of(rows["issue"], h)
    in_p, lab = rows["in_P"].to_numpy(dtype=bool), rows[y].notna().to_numpy()
    dc = day_counts(rows, y)
    br = np.full(len(rows), np.nan)
    for b in range(len(BLOCK_EDGES) - 1):
        sel = (blk == b) & in_p & lab
        br[sel] = rates(base_tables(dc, [zone(b, h)]), rows["gauge"].to_numpy()[sel], rows["month"].to_numpy(dtype=int)[sel])[1]
    tr = in_p & lab & np.isfinite(br)
    X = rows.loc[tr].assign(br_logit=br_logit(br[tr]))
    yv = rows.loc[tr, y].to_numpy(dtype=float)
    is_own = X["gauge"].isin(own).to_numpy()
    full = base_tables(dc, [])
    frozen = {"schema": "swimsignal.river-rises-c3-frozen", "version": 1, "made": datetime.now(UTC).isoformat(timespec="seconds"),
              "protocol": "docs/RIVER-RISES-C3-2026-11.md", "horizon_h": h, "delay_h": pr.DELAY_H, "radar_delay_h": pr.RADAR_DELAY_H,
              "population": "P: the site shows no word", "share": pr.SHARE, "seen_to": str(DEV_END), "models": {}, "base_rates": {},
              "constants": {"m_month": M_MONTH, "m_gauge": M_GAUGE, "br_clip": list(BR_CLIP), "alert_rates": list(ALERT_RATES)}}
    for m, sel in (("R3", is_own), ("C2", is_own), ("C3", is_own), ("C3n", np.ones(len(X), dtype=bool))):
        model = fit_model(X[sel], yv[sel], COLS[m])
        pt = model.predict(X[sel])
        frozen["models"][m] = {"cols": COLS[m], "coef": model.coef, "intercept": model.intercept, "mean": model.mean,
                               "scale": model.scale, "gauges": sorted(set(X.loc[sel, "gauge"])), "rows": int(sel.sum()),
                               "events": int(yv[sel].sum()),
                               "thresholds": {str(q): threshold(pt, q) for q in ALERT_RATES}}
    r1_all, r1s_all = rates(full, X["gauge"].to_numpy(), X["month"].to_numpy(dtype=int))
    for m, v in (("R1", r1_all), ("R1s", r1s_all)):
        frozen["models"][m] = {"thresholds": {str(q): threshold(v, q) for q in ALERT_RATES},
                               "note": "the frozen table's value at every seen labelled row; thresholds from those values"}
    for g in sorted({x.ref for x in gauges}):
        r1, r1s = rates(full, [g] * 12, list(range(1, 13)))
        frozen["base_rates"][g] = {"R1": dict(zip(range(1, 13), map(float, r1), strict=True)),
                                   "R1s": dict(zip(range(1, 13), map(float, r1s), strict=True))}
    frozen["gauges"] = [{"gauge": g.ref, "system": g.system, "low": g.low, "high": g.high, "own": g.ref in own,
                         "same": None if g.same is None else {"ref": g.same.ref, "low": g.same.low, "high": g.same.high},
                         "trib": None if g.trib is None else {"ref": g.trib.ref, "low": g.trib.low, "high": g.trib.high}}
                        for g in gauges]
    frozen["folds"], frozen["datum"] = folds, datum
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "c3_frozen.json"
    path.write_text(json.dumps(frozen, indent=1, default=str) + "\n")
    sha = pr.sha256(path)
    print(json.dumps({"frozen": str(path), "sha256": sha,
                      "models": {k: {kk: v.get(kk) for kk in ("rows", "events", "thresholds")} for k, v in frozen["models"].items()}},
                     indent=1, default=str))
    return frozen


def predict_frozen(frozen: dict, rows: pd.DataFrame) -> pd.DataFrame:
    """The frozen models on rows built at the frozen delay: base rates from the frozen tables by gauge and month."""
    from dipcast.model.ecoli import EcoliModel
    br = frozen["base_rates"]
    g, mth = rows["gauge"].astype(str).to_numpy(), rows["month"].to_numpy(dtype=int)
    r1 = np.array([br.get(a, {}).get("R1", {}).get(str(b), np.nan) for a, b in zip(g, mth, strict=True)], dtype=float)
    r1s = np.array([br.get(a, {}).get("R1s", {}).get(str(b), np.nan) for a, b in zip(g, mth, strict=True)], dtype=float)
    X = rows.assign(br_logit=br_logit(r1s))
    out = rows.loc[:, ["gauge", "system", "issue", "fold", "word", "in_P", f"y{frozen['horizon_h']}"]].copy()
    out["vblock"] = 0
    out["R1"], out["R1s"] = r1, r1s
    for m in ("R3", "C2", "C3", "C3n"):
        d = frozen["models"][m]
        p = EcoliModel(d["coef"], d["intercept"], d["mean"], d["scale"], {}).predict(X)
        out[m] = np.where(rows["gauge"].isin(d["gauges"]).to_numpy(), p, np.nan)
    for m in ("R1", "R1s", "R3", "C2", "C3", "C3n"):
        for q in ALERT_RATES:
            out[f"thr_{m}_{q}"] = frozen["models"][m]["thresholds"][str(q)]
    return out


def stage_fresh(args) -> dict:
    sha = pr.sha256(args.frozen)
    st = json.loads(Path(args.statement).read_text()) if args.statement and Path(args.statement).exists() else {}
    if str(st.get("frozen_sha256", "")).lower() != sha:
        raise SystemExit("the statement must name the frozen file's SHA-256, committed before the fresh week is read")
    frozen = json.loads(args.frozen.read_text())
    h = frozen["horizon_h"]
    end = FRESH[1] + pd.Timedelta(minutes=15)          # readings up to 1 Nov 2026 00:00, the last label window's end
    gauges, own, folds, _ = load(args.data, args.radar, end)
    keep = {x["gauge"] for x in frozen["gauges"]}
    gauges = [g for g in gauges if g.ref in keep]
    rows = build(gauges, folds, frozen["delay_h"], start=FRESH[0], end=FRESH[1] - pd.Timedelta(hours=h - 1))
    res = predict_frozen(frozen, rows)
    y = f"y{h}"
    out = {"made": datetime.now(UTC).isoformat(timespec="seconds"), "frozen_sha256": sha, "window": [str(FRESH[0]), str(FRESH[1])],
           "own": evaluate(res[res["gauge"].isin(own)], y, MODELS["own"], PAIRS["own"], bootstrap=False),
           "all": evaluate(res, y, MODELS["all"], PAIRS["all"], bootstrap=False),
           "label_share": float(res.loc[res["in_P"], y].notna().mean())}
    args.out.mkdir(parents=True, exist_ok=True)
    res.to_parquet(args.out / "c3_fresh_predictions.parquet", index=False)
    (args.out / "c3_fresh.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: (v if k in ("window", "label_share") else None) for k, v in out.items() if k in ("window", "label_share")}))
    for who in ("own", "all"):
        e = out[who]
        print(who, "rows", e["rows"], "events", e["events"],
              {m: round(v["brier"], 5) for m, v in e["models"].items()}, {k: round(v["skill"], 4) for k, v in e["pairs"].items()})
    return out


# ------------------------------------------------------------------ report
def f(x, n=4) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def write_report(out: dict, path: Path, title: str) -> None:
    L = [f"# River rises C3: {title}", "", f"Made {out['made']}. Predictions SHA-256 `{out.get('predictions_sha256', '')}`.", ""]
    for name, ev in out["configs"].items():
        who, h, d = CONFIGS[name]
        L += [f"## {name}: {'the 33 gauges of #627' if who == 'own' else 'all 45 gauges'}, {h} h, d = {d:g} h", "",
              f"{ev['rows_with_label']} labelled rows, {ev['events']} events, {ev['gauges']} gauges, {ev['systems']} river systems.", "",
              "| Model | Brier | AUC | Mean forecast | Observed | Calibration intercept | Slope |", "|---|---|---|---|---|---|---|"]
        for m, t in ev["models"].items():
            c = t["calibration"]
            L.append(f"| {m} | {f(t['brier'], 5)} | {f(t['auc'], 3)} | {f(c['mean_forecast'], 5)} | {f(c['observed'], 5)} | "
                     f"{f(c['intercept'], 2)} | {f(c['slope'], 2)} |")
        L += ["", "| Comparison | Skill | 95% interval, river systems | 95% interval, time blocks |", "|---|---|---|---|"]
        for k, v in ev["pairs"].items():
            s, b = v.get("by_system", {}), v.get("by_block", {})
            L.append(f"| {k} | {f(v['skill'])} | {f(s.get('L'))} to {f(s.get('U'))} | {f(b.get('L'))} to {f(b.get('U'))} |")
        L += ["", "| Model | Alert rate | Share alerted | Hit rate | False-alarm ratio | Episodes warned | Onsets caught | Median lead h |",
              "|---|---|---|---|---|---|---|---|"]
        for m, t in ev["models"].items():
            for a in t.get("alerts", []):
                L.append(f"| {m} | {a['alert_rate']:.1%} | {f(a['alert_share'], 4)} | {f(a['hit_rate'], 3)} | {f(a['false_alarm_ratio'], 3)} | "
                         f"{a['episodes_warned_first_hour']} of {a['episodes']} | {a['onsets_caught']} of {a['onsets_with_forecast']} | "
                         f"{f(a['lead_h']['median'], 1)} |")
        L.append("")
    if "forward_only" in out:
        fo = out["forward_only"]
        L += ["## Forward-only sensitivity (blocks 3 to 8, H1)", "",
              f"{fo['rows']} rows, {fo['events']} events. C3 skill, forward-only training: "
              + "; ".join(f"vs {k} {f(v['d'])} [{f(v['L'])}, {f(v['U'])}]" for k, v in fo["forward"].items())
              + ". Blocked training, same rows: "
              + "; ".join(f"vs {k} {f(v['d'])} [{f(v['L'])}, {f(v['U'])}]" for k, v in fo["blocked_same_rows"].items()) + ".", ""]
    if "coverage" in out:
        L += ["## Coverage of the 72 river spots", "", "| Covered | Gauges | Spots |", "|---|---|---|"]
        for r in out["coverage"]["by_coverage"]:
            L.append(f"| {r['covered']} | {r['gauges']} | {r['spots']} |")
        L += [f"| no usable gauge on the spot's river | n/a | {out['coverage']['spots_without_usable_gauge']} |", ""]
    L += ["Development on seen data: no figure here is a confirmation, and nothing here reaches the site."]
    path.write_text("\n".join(L) + "\n")


def main(argv: list[str] | None = None) -> None:
    from dipcast import config
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("develop", "freeze", "fresh"))
    ap.add_argument("--data", type=Path, required=True, help="fetch_c3.py's --out directory")
    ap.add_argument("--out", type=Path, required=True, help="this run's directory (outside git)")
    ap.add_argument("--radar", type=Path, default=config.RAW / "met_office_radar", help="saved radar months, read only")
    ap.add_argument("--frozen", type=Path, help="fresh: the frozen models file")
    ap.add_argument("--statement", type=Path, help="fresh: JSON naming the frozen file's SHA-256")
    args = ap.parse_args(argv)
    if args.radar and not args.radar.exists():
        args.radar = None
    {"develop": stage_develop, "freeze": stage_freeze, "fresh": stage_fresh}[args.stage](args)


if __name__ == "__main__":
    main()
