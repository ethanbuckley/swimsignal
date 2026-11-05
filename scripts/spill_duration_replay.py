"""Spill duration, the next development package (docs/SPILL-DURATION-NEXT-2026-11.md, write-up
docs/SPILL-DURATION-REPLAY-2026-11.md): 2024-25 replayed at the live site's own poll timetable, folds that keep each
spill whole with an embargo, and calibration fitted inside each training fold. Off CI, by hand:

    DIPCAST_ROOT=<checkout with data/processed and the rain caches> \\
        uv run python scripts/spill_duration_replay.py run --poll-log <poll_log.parquet> --out <scratch dir>

Development on seen data: every 2024-25 row has been looked at by #459 and #461, so this gives a direction, not a
verdict. It reads no 2026 event (the January-August 2026 outcomes stay unread) and makes no Open-Meteo call (rain is
the ERA5-Land cache #459 read).

1. Polls. The real poll timetable from the state release's poll_log.parquet (from 28 Sep 2026 16:51 UTC, when feed
   ages were first recorded) is laid over 2024-25 in 24-hour blocks drawn at random (seeded), each poll with its
   companies' feed ages and the share of each company's overflows with unknown status. A poll sees an overflow at
   its feed's time (poll time less feed age). A feed more than 8 hours old, or with no age, is stale: unknown, never
   "stopped". Each overflow is unknown at a poll with its company's unknown share then (drawn per overflow and poll).
2. Rows. An issue hour is every whole UTC hour of 2024-25 at which the latest poll saw the overflow discharging,
   fresh. Elapsed time is what the site's own history can tell: the start of the event seen at the earliest poll of
   the unbroken run of polls, ending at the latest, that each saw a discharge (#461's poll_elapsed, on these polls).
   Hours with elapsed under CAP_H. The label is #459's: the spill (EA events, 1-hour gaps joined) still running h
   hours after the issue hour. Reported too: the label as the polls would see it at t + h.
3. Folds. Each spill belongs to the month it began in (a spill begun before 2024 to January 2024). Six outer folds:
   month index mod 6, so each holds four months spread over both years. Training rows are the other folds' spills,
   less every row within EMBARGO_H of a held-out month. Calibration: per company and horizon, isotonic on inner
   out-of-fold forecasts (three inner folds over the training months, same embargo), applied to the outer model.
   Models are fitted on a seeded TRAIN_SHARE of their training rows (the budget is about one CPU-hour); B1 and
   scoring use every row.
4. Decision (stated before the run, 31 Oct 2026): C1-cal "keeps most of its gain" when its integrated Brier gain over
   B1 is at least KEEP_GAIN of B1's score with the interval below zero, and is "calibrated at most cells" when its ECE
   is at most ECE_OK in at least MOST_CELLS of the 45 company-horizon cells. Both: write the shadow statement. Either
   missing: the dated description stays the product, and the record says which part failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spill_duration_calibration_test as cal  # noqa: E402
import spill_duration_test as base  # noqa: E402
from dipcast import config  # noqa: E402
from dipcast.model.training import NINE, events_path, load_events  # noqa: E402

HORIZONS = base.HORIZONS
CAP_H = base.CAP_H
STALE_H = 8.0
BLOCK_H = 24.0
EMBARGO_H = 48.0
OUTER, INNER = 6, 3
TRAIN_SHARE = 0.10
KEEP_GAIN = 0.058     # half of #459's 11.6% gain, as a share of B1's integrated Brier
ECE_OK = 0.02
MOST_CELLS = 23       # of 45
WINDOW = base.TRAIN[0], pd.Timestamp("2025-12-31", tz="UTC")   # issue hours [lo, hi); labels to 2025-12-31 24:00
T0 = pd.Timestamp("2000-01-01", tz="UTC")
DOCS = Path(__file__).resolve().parents[1] / "docs" / "SPILL-DURATION-REPLAY-2026-11"
_T = time.time()


def step(msg: str) -> None:
    print(f"[{time.time() - _T:6.0f}s] {msg}", flush=True)


def hours(x) -> np.ndarray:
    return (pd.DatetimeIndex(x) - T0).total_seconds().to_numpy() / 3600.0


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fingerprint(poll_log: Path) -> dict:
    """The shared inputs, by hash (the rain caches by name and size: thousands of files)."""
    files = [events_path(c) for c in NINE] + [config.PROCESSED / "annual_returns.parquet", poll_log]
    rain = sorted((str(f.relative_to(config.CACHE)), f.stat().st_size)
                  for d in ("rain", "rain_nine") for f in (config.CACHE / d).glob("archive_*.parquet"))
    return {**{str(p.name): sha256(p) for p in files},
            "rain_listing": hashlib.sha256(json.dumps(rain).encode()).hexdigest(), "rain_files": len(rain)}


# ------------------------------------------------------------------ 1. polls
def real_polls(poll_log: pd.DataFrame) -> dict:
    """The real polls from the first with a recorded feed age: times (h), ages and unknown shares [polls, companies]."""
    p = poll_log.copy()
    p["fetched_at"] = pd.to_datetime(p["fetched_at"], utc=True)
    p = p[p["fetched_at"] >= p.loc[p["feed_age_h"].notna(), "fetched_at"].min()]
    t = np.sort(p["fetched_at"].unique())
    age = p.pivot_table(index="fetched_at", columns="company", values="feed_age_h", aggfunc="first", dropna=False)
    age = age.reindex(index=t, columns=list(NINE))
    unk = (1 - p["n_known"] / p["n_rows"].where(p["n_rows"] > 0)).groupby([p["fetched_at"], p["company"]]).first()
    unk = unk.unstack().reindex(index=t, columns=list(NINE)).fillna(1.0)
    return {"t": hours(t), "age": age.to_numpy(float), "unk": unk.to_numpy(float)}


def lay_polls(real: dict, lo_h: float, hi_h: float, seed: int = 0) -> dict:
    """The real timetable laid from lo_h to hi_h in BLOCK_H blocks of consecutive real polls, each block starting at a
    random real poll; the gap after a block is the real gap after its last poll."""
    rng = np.random.default_rng(seed)
    t, n = real["t"], len(real["t"])
    gaps = np.diff(t)
    out_t, idx = [], []
    now = lo_h
    while now < hi_h:
        k0 = int(rng.integers(0, n - 1))
        k1 = int(np.searchsorted(t, t[k0] + BLOCK_H, side="left"))
        k1 = min(max(k1, k0 + 1), n - 1)
        for k in range(k0, k1):
            out_t.append(now)
            idx.append(k)
            now += gaps[k]
    out_t, idx = np.asarray(out_t), np.asarray(idx)
    return {"t": out_t, "src": idx, "age": real["age"][idx], "unk": real["unk"][idx]}


def known_draw(site: np.ndarray, poll: np.ndarray) -> np.ndarray:
    """A uniform number per (overflow, poll), fixed: the same overflow at the same poll always draws the same."""
    x = (site.astype(np.uint64) * np.uint64(1_000_003) + poll.astype(np.uint64) + np.uint64(0x9E3779B9))
    x ^= x >> np.uint64(33)
    x *= np.uint64(0xFF51AFD7ED558CCD)
    x ^= x >> np.uint64(33)
    return (x >> np.uint64(11)).astype(np.float64) / float(1 << 53)


class Polls:
    """What a poll knows of each overflow: seen at poll time less its company's feed age; unknown when stale or drawn
    unknown."""

    def __init__(self, laid: dict, raw_idx: cal.RawIndex):
        self.t, self.age, self.unk, self.idx = laid["t"], laid["age"], laid["unk"], raw_idx

    def at(self, h: np.ndarray) -> np.ndarray:
        return np.searchsorted(self.t, h, side="right") - 1

    def look(self, site_code: np.ndarray, site_id: np.ndarray, comp: np.ndarray, i: np.ndarray, now: np.ndarray):
        """(known, running, event start h) at poll i for an issue time `now` (fresh means the feed time is at most
        STALE_H before `now`)."""
        ok = i >= 0
        ii = np.clip(i, 0, None)
        a = self.age[ii, comp]
        seen = self.t[ii] - a
        known = ok & np.isfinite(a) & (now - seen <= STALE_H) & (known_draw(site_code, ii) >= self.unk[ii, comp])
        run, start = self.idx.lookup(site_id, np.where(known, seen, -1e9))
        return known, run & known, start


# ------------------------------------------------------------------ 2. rows
def replay_rows(raw: pd.DataFrame, sp: pd.DataFrame, polls: Polls, lo: pd.Timestamp, hi: pd.Timestamp) -> pd.DataFrame:
    """Every (overflow, whole hour in [lo, hi)) at which the latest poll saw a discharge, fresh and known; with the
    elapsed time the site's history gives, the spill it belongs to and its labels."""
    lo_h, n_h = hours([lo])[0], int((hi - lo) / pd.Timedelta(hours=1))
    grid = lo_h + np.arange(n_h, dtype=float)
    gi = polls.at(grid)
    codes = pd.Index(np.unique(raw["site_id"].to_numpy()))
    rs, re_ = hours(raw["start"]), hours(raw["end"])
    rc = codes.get_indexer(raw["site_id"].to_numpy())
    rcomp = pd.Index(list(NINE)).get_indexer(raw["company"].to_numpy())
    parts = []
    for c in range(len(NINE)):
        # Hours ordered by the time their latest poll saw this company's feed: an event [s, e) holds a run of them.
        seen = np.where(gi >= 0, polls.t[np.clip(gi, 0, None)] - polls.age[np.clip(gi, 0, None), c], np.nan)
        good = np.isfinite(seen)
        order = np.flatnonzero(good)[np.argsort(seen[good], kind="mergesort")]
        v = seen[order]
        j = np.flatnonzero(rcomp == c)
        a = np.searchsorted(v, rs[j], side="left")
        b = np.searchsorted(v, re_[j], side="left")
        k = (b - a).astype(np.int64)
        ev = np.repeat(j, k)
        hrs = order[np.repeat(a, k) + base._ranges(k)]
        parts.append((ev, hrs))
    ev = np.concatenate([p[0] for p in parts])
    hk = np.concatenate([p[1] for p in parts])
    t_h = grid[hk]
    site_id = raw["site_id"].to_numpy()[ev]
    comp = rcomp[ev]
    known, run, _ = polls.look(rc[ev], site_id, comp, gi[hk], t_h)
    keep = run
    step(f"hours a poll saw a discharge: {len(ev)}; fresh and known: {int(keep.sum())}")
    ev, hk, t_h, site_id, comp = ev[keep], hk[keep], t_h[keep], site_id[keep], comp[keep]
    # Elapsed from the site's history: back through the unbroken run of polls that each saw a discharge.
    start = rs[ev].copy()
    chain = np.ones(len(ev), bool)
    i0 = gi[hk]
    for back in range(1, 400):
        i = i0 - back
        known, running, s = polls.look(rc[ev], site_id, comp, i, polls.t[np.clip(i, 0, None)])
        chain &= running & (i >= 0) & (t_h - polls.t[np.clip(i, 0, None)] < CAP_H + 24)
        start = np.where(chain, np.minimum(start, s), start)
        if not chain.any():
            break
    elapsed = (t_h - start).astype(np.float32)
    keep = elapsed < CAP_H
    ev, t_h, site_id, comp, elapsed, i0 = ev[keep], t_h[keep], site_id[keep], comp[keep], elapsed[keep], i0[keep]
    # The spill (1-hour gaps joined) the seen event belongs to.
    sc = pd.Index(np.unique(sp["site_id"].to_numpy()))
    skey = sc.get_indexer(sp["site_id"].to_numpy()) * 1e7 + hours(sp["start"])
    spell = np.searchsorted(skey, sc.get_indexer(site_id) * 1e7 + rs[ev], side="right") - 1
    sp_end = hours(sp["end"])[spell]
    assert (sc.get_indexer(sp["site_id"].to_numpy())[spell] == sc.get_indexer(site_id)).all()
    rows = pd.DataFrame({"spell": spell, "t": T0 + pd.to_timedelta(t_h, unit="h"), "elapsed_h": elapsed,
                         "remaining_h": (sp_end - t_h).astype(np.float32), "company_i": comp, "poll": i0,
                         "site_code": codes.get_indexer(site_id), "obs_age_h": (t_h - (polls.t[i0] - polls.age[i0, comp])).astype(np.float32),
                         "true_elapsed_h": (t_h - hours(sp["start"])[spell]).astype(np.float32)})
    rows = rows.sort_values(["t", "site_code"], kind="mergesort").reset_index(drop=True)
    # As the polls would see it at t + h: the latest poll then saw a discharge (NaN when stale or unknown).
    sid = codes[rows["site_code"].to_numpy()].to_numpy()
    th = hours(rows["t"])
    seen_lab = np.full((len(rows), len(HORIZONS)), np.nan, np.float32)
    for j, hh in enumerate(HORIZONS):
        known, running, _ = polls.look(rows["site_code"].to_numpy(), sid, rows["company_i"].to_numpy(), polls.at(th + hh), th + hh)
        seen_lab[:, j] = np.where(known, running.astype(np.float32), np.nan)
    rows[[f"seen_{h}h" for h in HORIZONS]] = seen_lab
    return rows


# ------------------------------------------------------------------ 3. folds
def month_index(h: np.ndarray) -> np.ndarray:
    t = T0 + pd.to_timedelta(h, unit="h")
    return np.clip((t.year.to_numpy() - 2024) * 12 + t.month.to_numpy() - 1, 0, 23)


MONTH_START = hours([pd.Timestamp(2024 + m // 12, m % 12 + 1, 1, tz="UTC") for m in range(25)])


def embargoed(t_h: np.ndarray, months) -> np.ndarray:
    """True for rows within EMBARGO_H of any of `months`."""
    m = np.zeros(len(t_h), bool)
    for k in months:
        m |= (t_h >= MONTH_START[k] - EMBARGO_H) & (t_h < MONTH_START[k + 1] + EMBARGO_H)
    return m


def fit_sub(X: pd.DataFrame, y: np.ndarray, mask: np.ndarray, seed: int):
    idx = np.flatnonzero(mask)
    pick = np.sort(np.random.default_rng(seed).choice(idx, size=max(int(len(idx) * TRAIN_SHARE), 1), replace=False))
    return base.fit(X.iloc[pick], y[pick], base.C1)


def nested(X, y, comp, block, t_h) -> tuple[np.ndarray, np.ndarray, dict]:
    """Out-of-fold C1 raw and C1-cal over the outer folds, and what each fold held."""
    raw = np.full_like(y, np.nan)
    cald = np.full_like(y, np.nan)
    info = {}
    for f in range(OUTER):
        held = [m for m in range(24) if m % OUTER == f]
        test = block % OUTER == f
        train = ~test & ~embargoed(t_h, held)
        tr_months = [m for m in range(24) if m % OUTER != f]
        inner_oof = np.full_like(y, np.nan)
        for g in range(INNER):
            ih = [m for i, m in enumerate(tr_months) if i % INNER == g]
            itest = train & np.isin(block, ih)
            itrain = train & ~np.isin(block, ih) & ~embargoed(t_h, ih)
            mods = fit_sub(X, y, itrain, 100 * f + g)
            inner_oof[itest] = base.predict(mods, X[itest], base.C1)
            step(f"fold {f} inner {g}: fit on {int(itrain.sum() * TRAIN_SHARE)} of {int(itrain.sum())}, predicted {int(itest.sum())}")
        have = train & np.isfinite(inner_oof[:, 0])
        calib = cal.fit_calibrators(inner_oof[have], y[have], comp[have])
        mods = fit_sub(X, y, train, 100 * f + 99)
        raw[test] = base.predict(mods, X[test], base.C1)
        cald[test] = cal.apply_calibrators(calib, raw[test], comp[test])
        info[f] = {"held_months": held, "test_rows": int(test.sum()), "train_rows": int(train.sum()),
                   "embargoed_rows": int((~test & embargoed(t_h, held)).sum()), "inner_calibration_rows": int(have.sum())}
        step(f"fold {f}: train {int(train.sum())}, test {int(test.sum())}")
    return raw, cald, info


def b1_oof(comp, ebin, y, block, t_h) -> np.ndarray:
    out = np.full_like(y, np.nan)
    for f in range(OUTER):
        held = [m for m in range(24) if m % OUTER == f]
        test = block % OUTER == f
        train = ~test & ~embargoed(t_h, held)
        out[test] = base.monotone(base.predict_empirical(base.empirical_survival(comp[train], ebin[train], y[train]),
                                                         comp[test], ebin[test]))
    return out


# ------------------------------------------------------------------ 4. scores
def scores(preds: dict, y: np.ndarray, rows: pd.DataFrame, comp: np.ndarray, seen: np.ndarray) -> pd.DataFrame:
    week = base.week_codes(rows["t"])
    W = week.max() + 1
    draws = np.random.default_rng(0).integers(0, W, size=(base.N_BOOT, W))
    ref = preds["B1 company x elapsed"]
    subsets = {"all": np.ones(len(y), bool), f"elapsed < {base.SHORT_H} h": rows["elapsed_h"].to_numpy() < base.SHORT_H,
               "poll seen 2 h or more before": rows["obs_age_h"].to_numpy() >= 2,
               "spill already ended at t": rows["remaining_h"].to_numpy() <= 0,
               "elapsed shorter than the spill's by 1 h or more": (rows["true_elapsed_h"] - rows["elapsed_h"]).to_numpy() >= 1}
    out = []
    for name, p in preds.items():
        bs = (p - y) ** 2
        d = bs.mean(1) - ((ref - y) ** 2).mean(1)
        for c in [*NINE, "all nine"]:
            for sname, sm in subsets.items():
                if c != "all nine" and sname != "all":
                    continue
                m = sm & (np.ones(len(y), bool) if c == "all nine" else comp == c)
                if not m.any():
                    continue
                lo, hi = base.boot(d[m], week[m], draws)
                ok = np.isfinite(seen[m])
                out.append({"model": name, "company": c, "subset": sname, "rows": int(m.sum()),
                            "integrated_brier": float(bs[m].mean()), "diff_vs_B1": float(d[m].mean()), "lo": lo, "hi": hi,
                            "brier_vs_seen_label": float(((p[m][ok] - seen[m][ok]) ** 2).mean()) if ok.any() else None,
                            **{f"ece_{h}h": base.ece(p[m, j], y[m, j]) for j, h in enumerate(HORIZONS)},
                            **{f"gap_{h}h": float(p[m, j].mean() - y[m, j].mean()) for j, h in enumerate(HORIZONS)}})
        for j, h in enumerate(HORIZONS):
            dh = bs[:, j] - (ref[:, j] - y[:, j]) ** 2
            lo, hi = base.boot(dh, week, draws)
            out.append({"model": name, "company": "all nine", "subset": f"horizon {h} h", "rows": len(y),
                        "integrated_brier": float(bs[:, j].mean()), "diff_vs_B1": float(dh.mean()), "lo": lo, "hi": hi})
    return pd.DataFrame(out)


def decide(t: pd.DataFrame) -> dict:
    t1 = t.set_index(["model", "company", "subset"])
    b1 = t1.loc[("B1 company x elapsed", "all nine", "all")]
    out = {}
    for name in ("C1-cal", "C1 raw"):
        a = t1.loc[(name, "all nine", "all")]
        comp = t1.loc[name].xs("all", level="subset").loc[list(NINE)]
        cells = int(sum((comp[f"ece_{h}h"] <= ECE_OK).sum() for h in HORIZONS))
        gain = -a["diff_vs_B1"] / b1["integrated_brier"]
        out[name] = {"gain_share_of_B1": round(float(gain), 4), "interval": [round(a["lo"], 5), round(a["hi"], 5)],
                     "keeps_gain": bool(gain >= KEEP_GAIN and a["hi"] < 0),
                     "cells_ece_at_most_0.02": cells, "calibrated_most_cells": cells >= MOST_CELLS}
        out[name]["write_shadow_statement"] = out[name]["keeps_gain"] and out[name]["calibrated_most_cells"]
    return out


# ------------------------------------------------------------------ run
def run(poll_log: Path, out: Path, seed: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    before = fingerprint(poll_log)
    ev = load_events(NINE)
    ev = ev[ev["event_start"] < pd.Timestamp("2026-01-01", tz="UTC")]   # no 2026 event is read
    sp, raw = base.merge_spells(ev, base.GAP_H), base.merge_spells(ev, 0.0)
    step(f"{len(ev)} events -> {len(raw)} raw events, {len(sp)} spills")
    real = real_polls(pd.read_parquet(poll_log))
    lo_h, hi_h = hours([WINDOW[0]])[0] - CAP_H - 48, hours([WINDOW[1]])[0] + 48
    laid = lay_polls(real, lo_h, hi_h, seed)
    gaps = np.diff(laid["t"])
    poll_info = {"real_polls": len(real["t"]), "real_from": str(T0 + pd.Timedelta(hours=real["t"][0])),
                 "real_gap_median_h": float(np.median(np.diff(real["t"]))), "real_gap_p95_h": float(np.percentile(np.diff(real["t"]), 95)),
                 "laid_polls": len(laid["t"]), "laid_gap_median_h": float(np.median(gaps)), "laid_gap_p95_h": float(np.percentile(gaps, 95)),
                 "stale_share_by_company": {c: float(np.mean(~np.isfinite(laid["age"][:, k]) | (laid["age"][:, k] > STALE_H)))
                                            for k, c in enumerate(NINE)},
                 "unknown_share_by_company": {c: float(laid["unk"][:, k].mean()) for k, c in enumerate(NINE)}}
    step(f"polls laid: {len(laid['t'])}, gap median {poll_info['laid_gap_median_h']:.2f} h, p95 {poll_info['laid_gap_p95_h']:.2f} h")
    polls = Polls(laid, cal.RawIndex(raw))
    rows = replay_rows(raw, sp, polls, *WINDOW)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    sites = cal.site_table(ar, ev, (2024, 2025))
    k = pd.MultiIndex.from_arrays([sp["site_id"].to_numpy()[rows["spell"].to_numpy()], rows["t"].dt.year.to_numpy()])
    rows = rows[k.isin(pd.MultiIndex.from_frame(sites[["site_id", "year"]]))].reset_index(drop=True)
    step(f"replayed rows on overflows with the year before's return: {len(rows)}")
    grid = base.build_grid(sites)
    X = base.features(rows, sp, sites, grid, base.history_hours(sp))
    y = base.labels(rows)
    comp = sp["company"].to_numpy()[rows["spell"].to_numpy()]
    seen = rows[[f"seen_{h}h" for h in HORIZONS]].to_numpy(np.float32)
    t_h = hours(rows["t"])
    block = month_index(hours(sp["start"])[rows["spell"].to_numpy()])
    step("features built")
    c1_raw, c1_cal, folds = nested(X, y, comp, block, t_h)
    ebin = base.elapsed_bin(rows["elapsed_h"].to_numpy())
    preds = {"B1 company x elapsed": b1_oof(comp, ebin, y, block, t_h), "C1 raw": c1_raw, "C1-cal": c1_cal,
             "stops now (the site today)": np.zeros_like(y), "keeps running": np.ones_like(y)}
    t = scores(preds, y, rows, comp, seen)
    t.to_csv(out / "scores.csv", index=False)
    rel = pd.concat([base.reliability(preds[m], y, comp, m) for m in ("B1 company x elapsed", "C1 raw", "C1-cal")])
    rel.to_csv(out / "reliability.csv", index=False)
    after = fingerprint(poll_log)
    summary = {
        "inputs": before, "inputs_unchanged": before == after, "seed": seed, "polls": poll_info, "folds": folds,
        "rows": len(rows), "spills": int(rows["spell"].nunique()),
        "rows_spill_already_ended": int((rows["remaining_h"] <= 0).sum()),
        "rows_elapsed_shorter_than_spill_by_1h": int(((rows["true_elapsed_h"] - rows["elapsed_h"]) >= 1).sum()),
        "seen_label_known_share": {f"{h}h": float(np.isfinite(seen[:, j]).mean()) for j, h in enumerate(HORIZONS)},
        "rain_missing_share": float(X[["rain_past_6h", "rain_past_24h", "rain_past_72h"]].isna().any(axis=1).mean()),
        "train_share": TRAIN_SHARE, "decision_rule": {"keep_gain": KEEP_GAIN, "ece_ok": ECE_OK, "most_cells": MOST_CELLS},
        "decision": decide(t), "seconds": round(time.time() - _T)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(t[t["subset"] == "all"][["model", "company", "rows", "integrated_brier", "diff_vs_B1", "lo", "hi"]].to_string(index=False))
    print(json.dumps(summary["decision"], indent=2))
    if not summary["inputs_unchanged"]:
        raise SystemExit("an input changed during the run")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["run"])
    ap.add_argument("--poll-log", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    run(a.poll_log, a.out, a.seed)


if __name__ == "__main__":
    main()
