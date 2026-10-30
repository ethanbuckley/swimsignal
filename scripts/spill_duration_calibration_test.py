"""Spill duration with a calibration step, judged on January to August 2026: a pre-stated test
(docs/SPILL-DURATION-CALIBRATION-TEST-2026-11.md). Off CI, by hand, with DIPCAST_ROOT pointing at a checkout that holds
data/processed and the rain caches:

    uv run python scripts/spill_duration_calibration_test.py gate   # 2024-25 only: out-of-fold check, then fits and saves
    uv run python scripts/spill_duration_calibration_test.py run    # 2026: predicts and scores (EVENTS_2026 must be set)

`gate` reads nothing from 2026. It fits C1 eight times (one quarter of 2024-25 held out each time), checks the gate on
the out-of-fold predictions, fits the isotonic calibrators on them, fits the final C1 on every 2024-25 row, and saves
all of it under data/processed/spill_duration/. `run` reads the EA's 2026 events from EVENTS_2026 (a folder of
ea_events_<company>.parquet written by scripts/import_ea_events.py --years 2026 into a scratch root), predicts and
scores. It refuses to run if the gate failed or the saved fits do not match the training rows.

Rows, labels, inputs and settings are PR #459's (scripts/spill_duration_test.py), with the change PR #461 found was
needed: an issue hour counts only when an EA event is running then (a monitor would show "discharging").
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spill_duration_test as base  # noqa: E402
from dipcast import config  # noqa: E402
from dipcast.model.features import site_static_features  # noqa: E402
from dipcast.model.training import NINE, load_events, site_years  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True)
log = logging.getLogger("spill_duration_calibration_test")

HORIZONS = base.HORIZONS
TRAIN = (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-12-31", tz="UTC"))   # issue hours [lo, hi)
TEST = (pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-08-31", tz="UTC"))    # labels to 31 Aug 00:00
LEFT_OUT = "United Utilities"   # recording changed in 2026: scored and reported, not in conditions 3 and 4
GATE_GAP = 0.03                 # the gate: at 24 h, rows forecast >= 0.8 out of fold come true this much less often
GATE_FROM = 0.8
RAIN_TAGS = ("2023", "2023dec", "2024", "2025", "2026", "2026a")
GRID_END = "2026-09-03"
H = base.H
OUT = config.PROCESSED / "spill_duration"
DOCS = Path(__file__).resolve().parents[1] / "docs" / "SPILL-DURATION-CALIBRATION-TEST-2026-11"
step = base.step


# ------------------------------------------------------------------ pieces
def quarter_fold(t: pd.Series) -> np.ndarray:
    """0..7: the calendar quarter of 2024-25 an issue hour falls in."""
    return ((t.dt.year.to_numpy() - 2024) * 4 + (t.dt.month.to_numpy() - 1) // 3).astype(np.int64)


def fit_calibrators(oof: np.ndarray, y: np.ndarray, company: np.ndarray) -> dict:
    """Isotonic regression per (company, horizon), fitted on out-of-fold forecasts and their outcomes."""
    from sklearn.isotonic import IsotonicRegression
    cal = {}
    for c in np.unique(company):
        m = company == c
        for j in range(len(HORIZONS)):
            cal[(c, j)] = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(oof[m, j], y[m, j])
    return cal


def apply_calibrators(cal: dict, p: np.ndarray, company: np.ndarray) -> np.ndarray:
    """Each column through its company's calibrator, then forced not to rise with the horizon. A company with no
    calibrator keeps the raw forecast."""
    out = p.copy()
    for c in np.unique(company):
        m = company == c
        for j in range(len(HORIZONS)):
            if (c, j) in cal:
                out[m, j] = cal[(c, j)].predict(p[m, j])
    return base.monotone(out)


def gate(oof: np.ndarray, y: np.ndarray, j24: int) -> tuple[bool, float, int]:
    """True when, at the 24 h horizon, out-of-fold forecasts of at least GATE_FROM come true at least GATE_GAP less
    often than forecast: the over-sharpness a calibration step fitted on these forecasts could remove."""
    m = oof[:, j24] >= GATE_FROM
    if not m.any():
        return False, float("nan"), 0
    gap = float(oof[m, j24].mean() - y[m, j24].mean())
    return gap >= GATE_GAP, gap, int(m.sum())


class RawIndex:
    """Raw events (overlaps joined, no gap rule) sorted for lookups: is an event running at t, and when did it begin."""

    def __init__(self, raw: pd.DataFrame):
        self.codes = pd.Index(np.unique(raw["site_id"].to_numpy()))
        rc = self.codes.get_indexer(raw["site_id"].to_numpy())
        s, e = self._h(raw["start"]), self._h(raw["end"])
        o = np.lexsort((s, rc))
        self.c, self.s, self.e = rc[o], s[o], e[o]
        self.key = self.c * 1e7 + self.s

    @staticmethod
    def _h(x) -> np.ndarray:
        return (pd.DatetimeIndex(x) - pd.Timestamp("2000-01-01", tz="UTC")).total_seconds().to_numpy() / H

    def lookup(self, site_id: np.ndarray, t_hours: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(running at t, start in hours since 2000 of the event running then, NaN where none)."""
        qc = self.codes.get_indexer(site_id)
        j = np.searchsorted(self.key, qc * 1e7 + t_hours, side="right") - 1
        jj = np.clip(j, 0, None)
        run = (qc >= 0) & (j >= 0) & (self.c[jj] == qc) & (self.e[jj] > t_hours)
        return run, np.where(run, self.s[jj], np.nan)


def poll_elapsed(idx: RawIndex, site_id: np.ndarray, t: pd.Series, cap_h: int = base.CAP_H) -> np.ndarray:
    """Elapsed hours as polls on every whole hour would see them: the start of the event running at the earliest of
    the unbroken run of hourly polls, ending at t, that each saw a discharge. A pause that spans an hour mark breaks the
    run, so this can be shorter than the true elapsed time; a pause between two marks is not seen."""
    th = RawIndex._h(t)
    run, start = idx.lookup(site_id, th)
    chain = run.copy()
    for k in range(1, cap_h + 1):
        rk, sk = idx.lookup(site_id, th - k)
        chain &= rk
        start = np.where(chain, sk, start)
        if not chain.any():
            break
    return (th - start).astype(np.float32)


def rows_hash(rows: pd.DataFrame, y: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(rows["t"].astype("int64").to_numpy().tobytes())
    h.update(rows["elapsed_h"].to_numpy().tobytes())
    h.update(y.tobytes())
    return h.hexdigest()[:16]


# ------------------------------------------------------------------ data
def load_2026(folder: Path) -> pd.DataFrame:
    frames = []
    for c in NINE:
        p = folder / f"{base_slug(c)}.parquet"
        frames.append(pd.read_parquet(p).assign(company=c))
    ev = pd.concat(frames, ignore_index=True)
    return ev[ev["event_start"] >= pd.Timestamp("2026-01-01", tz="UTC")]


def base_slug(company: str) -> str:
    import re
    return "ea_events_" + re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")


def site_table(ar: pd.DataFrame, ev: pd.DataFrame, years) -> pd.DataFrame:
    out = []
    for y in years:
        s, _ = site_years(ar, ev, NINE, y)
        out.append(site_static_features(s).assign(year=y))
    s = pd.concat(out, ignore_index=True)
    s["log_hours_per_spill"] = s["log_spill_hours"] - s["log_lta_spills"]
    return s.drop_duplicates(["site_id", "year"], keep="last").reset_index(drop=True)


def prepare(ev: pd.DataFrame, years, window, sites=None, grid=None):
    """Spills, raw events, rows a monitor would show as discharging in `window`, their labels and C1's inputs."""
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    sp, raw = base.merge_spells(ev, base.GAP_H), base.merge_spells(ev, 0.0)
    sites = site_table(ar, ev, years) if sites is None else sites
    grid = base.build_grid(sites, tags=RAIN_TAGS, end=GRID_END) if grid is None else grid
    rows = base.issue_rows(sp, *window)
    k = pd.MultiIndex.from_arrays([sp["site_id"].to_numpy()[rows["spell"].to_numpy()], rows["t"].dt.year.to_numpy()])
    rows = rows[k.isin(pd.MultiIndex.from_frame(sites[["site_id", "year"]]))].reset_index(drop=True)
    idx = RawIndex(raw)
    sid = sp["site_id"].to_numpy()[rows["spell"].to_numpy()]
    run, _ = idx.lookup(sid, RawIndex._h(rows["t"]))
    n_all = len(rows)
    rows = rows[run].reset_index(drop=True)
    X = base.features(rows, sp, sites, grid, base.history_hours(sp))
    y = base.labels(rows)
    comp = sp["company"].to_numpy()[rows["spell"].to_numpy()]
    return {"sp": sp, "idx": idx, "sites": sites, "grid": grid, "rows": rows, "X": X, "y": y, "company": comp,
            "site_id": sp["site_id"].to_numpy()[rows["spell"].to_numpy()], "n_before_running_filter": n_all}


# ------------------------------------------------------------------ gate (2024-25 only)
def stage_gate() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ev = load_events(NINE)
    ev = ev[ev["event_start"] < pd.Timestamp("2026-01-01", tz="UTC")]
    d = prepare(ev, (2024, 2025), TRAIN)
    X, y, comp, rows = d["X"], d["y"], d["company"], d["rows"]
    step(f"training rows: {len(rows)} running at t, of {d['n_before_running_filter']}")
    fold = quarter_fold(rows["t"])
    oof = np.full_like(y, np.nan)
    for k in range(8):
        m = fold == k
        oof[m] = base.predict(base.fit(X[~m], y[~m], base.C1), X[m], base.C1)
        step(f"fold {k}: {int(m.sum())} rows predicted")
    j24 = HORIZONS.index(24)
    ok, gap, n = gate(oof, y, j24)
    cal = fit_calibrators(oof, y, comp)
    rel = base.reliability(oof, y, comp, "C1 out of fold")
    rel.to_csv(f"{DOCS}-gate-reliability.csv", index=False)
    final = base.fit(X, y, base.C1)
    b1 = base.empirical_survival(comp, base.elapsed_bin(rows["elapsed_h"].to_numpy()), y)
    info = {"gate_passes": ok, "gap_24h_at_0.8_plus": gap, "rows_at_0.8_plus": n, "train_rows": len(rows),
            "rows_hash": rows_hash(rows, y),
            "oof_ece_24h_all_nine": base.ece(oof[:, j24], y[:, j24]),
            "oof_ece_24h_calibrated_in_sample": base.ece(apply_calibrators(cal, oof, comp)[:, j24], y[:, j24])}
    with open(OUT / "calibration_fits.pkl", "wb") as f:
        pickle.dump({"final": final, "cal": cal, "b1": b1, "info": info}, f)
    with open(f"{DOCS}-gate.json", "w") as f:
        json.dump(info, f, indent=2)
    print(json.dumps(info, indent=2))


def fold_overlap(spell: np.ndarray, fold: np.ndarray) -> dict:
    """How much of the out-of-fold design is shared across folds: spills whose rows fall in more than one quarter, and
    the rows of those spills. A held-out row whose spill also has rows in a training quarter was predicted by a model
    that saw part of the same spill."""
    d = pd.DataFrame({"spell": spell, "fold": fold})
    n_folds = d.groupby("spell")["fold"].nunique()
    split = n_folds.index[n_folds > 1]
    in_split = d["spell"].isin(split).to_numpy()
    by_fold = d.assign(split=in_split).groupby("fold")["split"].agg(["size", "mean"])
    return {"spills": int(len(n_folds)), "spills_in_two_or_more_quarters": int(len(split)),
            "share_of_spills": float(len(split) / max(len(n_folds), 1)),
            "rows": int(len(d)), "rows_in_split_spills": int(in_split.sum()), "share_of_rows": float(in_split.mean()),
            "share_of_rows_by_fold": {int(k): round(float(v), 4) for k, v in by_fold["mean"].items()}}


def stage_overlap() -> None:
    """2024-25 only, no model: the gate's training rows, and how many sit in spills split across quarters
    (review of 30 October 2026). Reported as a limitation of the gate; the frozen conditions are unchanged."""
    ev = load_events(NINE)
    ev = ev[ev["event_start"] < pd.Timestamp("2026-01-01", tz="UTC")]
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    sp, raw = base.merge_spells(ev, base.GAP_H), base.merge_spells(ev, 0.0)
    sites = site_table(ar, ev, (2024, 2025))
    rows = base.issue_rows(sp, *TRAIN)
    k = pd.MultiIndex.from_arrays([sp["site_id"].to_numpy()[rows["spell"].to_numpy()], rows["t"].dt.year.to_numpy()])
    rows = rows[k.isin(pd.MultiIndex.from_frame(sites[["site_id", "year"]]))].reset_index(drop=True)
    run, _ = RawIndex(raw).lookup(sp["site_id"].to_numpy()[rows["spell"].to_numpy()], RawIndex._h(rows["t"]))
    rows = rows[run].reset_index(drop=True)
    y = base.labels(rows)
    info = {"rows_hash_matches_gate": rows_hash(rows, y) == json.loads(Path(f"{DOCS}-gate.json").read_text())["rows_hash"],
            **fold_overlap(rows["spell"].to_numpy(), quarter_fold(rows["t"]))}
    with open(f"{DOCS}-fold-overlap.json", "w") as f:
        json.dump(info, f, indent=2)
    print(json.dumps(info, indent=2))


# ------------------------------------------------------------------ run (2026)
def stage_run() -> None:
    with open(OUT / "calibration_fits.pkl", "rb") as f:
        saved = pickle.load(f)
    if not saved["info"]["gate_passes"]:
        raise SystemExit("the gate failed: the 2026 score is not run (statement, 'The gate')")
    folder = Path(os.environ["EVENTS_2026"])
    ev = pd.concat([load_events(NINE), load_2026(folder)], ignore_index=True)
    step(f"events with 2026: {len(ev)}")
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    sites = site_table(ar, ev, (2024, 2025, 2026))
    grid = base.build_grid(sites, tags=RAIN_TAGS, end=GRID_END)
    # The training rows again, with 2026 events present, must be the gate's (statement, "Why the fits are made first").
    ev_train = ev[ev["event_start"] < pd.Timestamp("2026-01-01", tz="UTC")]
    tr = prepare(ev_train, (2024, 2025), TRAIN, sites=sites[sites["year"] < 2026], grid=grid)
    if rows_hash(tr["rows"], tr["y"]) != saved["info"]["rows_hash"]:
        raise SystemExit("training rows differ from the gate's: not run")
    te = prepare(ev, (2026,), TEST, sites=sites, grid=grid)
    X, y, comp, rows = te["X"], te["y"], te["company"], te["rows"]
    step(f"2026 rows: {len(rows)} running at t, of {te['n_before_running_filter']}")
    raw_c1 = base.predict(saved["final"], X, base.C1)
    preds = {"B1 company x elapsed": base.monotone(base.predict_empirical(saved["b1"], comp,
                                                                          base.elapsed_bin(rows["elapsed_h"].to_numpy()))),
             "C1 raw": raw_c1,
             "C1-cal": apply_calibrators(saved["cal"], raw_c1, comp)}
    # Reported: elapsed time as hourly polls would see it, through the same C1-cal.
    Xp = X.copy()
    Xp["elapsed_h"] = poll_elapsed(te["idx"], te["site_id"], rows["t"])
    preds["C1-cal, poll elapsed (reported)"] = apply_calibrators(saved["cal"], base.predict(saved["final"], Xp, base.C1), comp)
    # Reported: "a monitor reports a discharge at +h".
    act = np.column_stack([te["idx"].lookup(te["site_id"], RawIndex._h(rows["t"]) + h)[0] for h in HORIZONS]).astype(np.float32)
    extra = {"rain_missing_share": float(X[["rain_past_6h", "rain_past_24h", "rain_past_72h"]].isna().any(axis=1).mean()),
             "poll_elapsed_shorter_share": float((Xp["elapsed_h"].to_numpy() < X["elapsed_h"].to_numpy() - 1e-3).mean()),
             "events_2026": int((ev["event_start"] >= TEST[0]).sum())}
    score(preds, y, act, rows, comp, extra)


def score(preds: dict, y: np.ndarray, act: np.ndarray, rows: pd.DataFrame, company: np.ndarray, extra: dict) -> None:
    week = base.week_codes(rows["t"])
    W = week.max() + 1
    draws = np.random.default_rng(0).integers(0, W, size=(base.N_BOOT, W))
    ref = preds["B1 company x elapsed"]
    short = rows["elapsed_h"].to_numpy() < base.SHORT_H
    out = []
    for name, p in preds.items():
        bs = (p - y) ** 2
        d = bs.mean(1) - ((ref - y) ** 2).mean(1)
        for c in [*NINE, "all nine"]:
            m = np.ones(len(y), bool) if c == "all nine" else company == c
            lo, hi = base.boot(d[m], week[m], draws)
            out.append({"model": name, "company": c, "subset": "all", "rows": int(m.sum()),
                        "integrated_brier": float(bs[m].mean()), "diff_vs_B1": float(d[m].mean()), "lo": lo, "hi": hi,
                        "brier_vs_discharging_label": float(((p[m] - act[m]) ** 2).mean()),
                        **{f"ece_{h}h": base.ece(p[m, j], y[m, j]) for j, h in enumerate(HORIZONS)},
                        **{f"gap_{h}h": float(p[m, j].mean() - y[m, j].mean()) for j, h in enumerate(HORIZONS)}})
        lo, hi = base.boot(d[short], week[short], draws)
        out.append({"model": name, "company": "all nine", "subset": f"elapsed < {base.SHORT_H} h", "rows": int(short.sum()),
                    "integrated_brier": float(bs[short].mean()), "diff_vs_B1": float(d[short].mean()), "lo": lo, "hi": hi})
        for j, h in enumerate(HORIZONS):
            dh = bs[:, j] - (ref[:, j] - y[:, j]) ** 2
            lo, hi = base.boot(dh, week, draws)
            out.append({"model": name, "company": "all nine", "subset": f"horizon {h} h", "rows": len(y),
                        "diff_vs_B1": float(dh.mean()), "lo": lo, "hi": hi})
    t = pd.DataFrame(out)
    t.to_csv(f"{DOCS}-scores.csv", index=False)
    base.reliability(preds["C1-cal"], y, company, "C1-cal").to_csv(f"{DOCS}-reliability.csv", index=False)
    checks = {"extra": extra}
    t1 = t.set_index(["model", "company", "subset"])
    b1 = t1.loc[("B1 company x elapsed", "all nine", "all")]
    eight = [c for c in NINE if c != LEFT_OUT]
    for name in ("C1-cal", "C1 raw"):
        a = t1.loc[(name, "all nine", "all")]
        comp_rows = t1.loc[name].xs("all", level="subset").loc[eight]
        bcomp = t1.loc["B1 company x elapsed"].xs("all", level="subset").loc[eight]
        checks[name] = {
            "1a gain, interval below zero": bool(a["hi"] < 0),
            "1b gain at least 2% of B1": bool(-a["diff_vs_B1"] >= base.MATERIAL * b1["integrated_brier"]),
            "2 no horizon clearly worse": bool(all(t1.loc[(name, "all nine", f"horizon {h} h"), "lo"] <= 0 for h in HORIZONS)),
            "3 no company clearly worse (eight)": bool((comp_rows["lo"] <= 0).all()),
            "4 reliability (eight)": bool(all(((comp_rows[f"ece_{h}h"] <= bcomp[f"ece_{h}h"]) | (comp_rows[f"ece_{h}h"] <= 0.02)).all()
                                              for h in HORIZONS)),
            "5 not worse on new spills": bool(t1.loc[(name, "all nine", f"elapsed < {base.SHORT_H} h"), "lo"] <= 0),
        }
        checks[name]["passes"] = all(checks[name].values())
    with open(f"{DOCS}-checks.json", "w") as f:
        json.dump(checks, f, indent=2)
    print(t[t["subset"] == "all"][["model", "company", "rows", "integrated_brier", "diff_vs_B1", "lo", "hi"]].to_string(index=False))
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    {"gate": stage_gate, "run": stage_run, "overlap": stage_overlap}[sys.argv[1]]()
