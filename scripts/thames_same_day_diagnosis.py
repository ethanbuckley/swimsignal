"""Thames Water's same-day loss to persistence, level or ranking (docs/THAMES-SAME-DAY-DIAGNOSIS-2026-11.md). A
description of seen data: nothing is refitted except the page's own persistence and rain chances, no corrected
forecast is made or scored, and nothing is written but the output JSON.

Reads the calibration check's scored file and a state release, read only (no pipeline run, no Open-Meteo call):

    DIPCAST_ROOT=/tmp/x DIPCAST_STATE=/tmp/x DIPCAST_CACHE=/tmp/x uv run python scripts/thames_same_day_diagnosis.py \\
        --scored verification_live.csv --state /tmp/s --to 2026-10-17 --out docs/THAMES-SAME-DAY-DIAGNOSIS-2026-11.json

--to 2026-10-23 is the extension the record fixes for on or after 21 November 2026.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_2027 import auc, sha256  # noqa: E402
from simple_references import scored_frame  # noqa: E402

from dipcast import simple_references as sr  # noqa: E402
from dipcast.forecast_log import load_coverage  # noqa: E402

FIRST = date(2026, 9, 29)
RECORD_LAST = date(2026, 10, 23)        # the calibration check's last target day
THAMES = "Thames Water"
CUTS = (0.01, 0.03, 0.07, 0.15, 0.40, 0.70)
MIN_JUDGED = 50                         # overflow-days with a spill below which the reading rule is not applied
STATE_FILES = ("dipcast.duckdb", "live_history.parquet", "live_coverage.parquet", "poll_log.parquet")
# The interim read's counts on 29 Sep to 23 Oct (docs/INTERIM-USEFULNESS-2026-10.json); no outcome enters them.
EXPECTED_COUNTS = {"rows": 117324, "status_known": 91444, "rain_both_days": 107650, "common": 91391,
                   "lead0_known_active": 1382, "lead0_known_quiet": 19130, "thames_status_known": 17426,
                   "thames_common": 17416}


def interval(a: np.ndarray) -> dict:
    a = np.asarray(a, float)
    ok = a[~np.isnan(a)]
    return {"lo": float(np.percentile(ok, 2.5)) if len(ok) else None,
            "hi": float(np.percentile(ok, 97.5)) if len(ok) else None, "undefined_draws": int(len(a) - len(ok))}


class Weights:
    """Per-row bootstrap weights from simple_references.Draws' count matrices: overflows x blocks (the page's), or
    overflows only (blocks held at one each, the declared sensitivity)."""

    def __init__(self, draws: sr.Draws, blocks: bool = True):
        self.d, self.blocks = draws, blocks

    def __len__(self) -> int:
        return self.d.S.shape[0]

    def row(self, r: int, rows: np.ndarray) -> np.ndarray:
        w = self.d.S[r, self.d.site[rows]]
        return w * self.d.B[r, self.d.block[rows]] if self.blocks else w


def murphy(q: np.ndarray, y: np.ndarray, w: np.ndarray) -> dict:
    """Brier = level + spread + association (Murphy 1988), weighted, standard deviations divided by the weight."""
    n = w.sum()
    if n <= 0:
        return {}
    my, mq = np.dot(w, y) / n, np.dot(w, q) / n
    vy, vq = my * (1 - my), max(np.dot(w, q * q) / n - mq * mq, 0.0)
    cov = np.dot(w, q * y) / n - mq * my
    r = cov / np.sqrt(vq * vy) if vq > 0 and vy > 0 else 0.0
    out = {"brier": float(np.dot(w, (q - y) ** 2) / n), "level": float((mq - my) ** 2),
           "spread": float((np.sqrt(vq) - r * np.sqrt(vy)) ** 2), "association": float(vy * (1 - r * r)),
           "r": float(r), "mean": float(mq), "spill_rate": float(my)}
    out["calibration"] = out["level"] + out["spread"]
    return out


def banded(q: np.ndarray, y: np.ndarray, w: np.ndarray, band: np.ndarray, nb: int) -> dict:
    """Reliability, resolution and uncertainty over bands, and the within-band remainder (Stephenson, Coelho and
    Jolliffe 2008) so that reliability - resolution + uncertainty + remainder = Brier exactly."""
    n = w.sum()
    if n <= 0:
        return {}
    nk = np.bincount(band, weights=w, minlength=nb)
    ok = nk > 0
    fk = np.bincount(band, weights=w * q, minlength=nb)[ok] / nk[ok]
    yk = np.bincount(band, weights=w * y, minlength=nb)[ok] / nk[ok]
    ybar = np.dot(w, y) / n
    rel = float(np.dot(nk[ok], (fk - yk) ** 2) / n)
    res = float(np.dot(nk[ok], (yk - ybar) ** 2) / n)
    unc = float(ybar * (1 - ybar))
    bs = float(np.dot(w, (q - y) ** 2) / n)
    return {"brier": bs, "reliability": rel, "resolution": res, "uncertainty": unc, "remainder": bs - (rel - res + unc),
            "bands": int(ok.sum())}


def hits_at(f: np.ndarray, y: np.ndarray, w: np.ndarray, k: float) -> float:
    """Spills among the k (weighted) highest-forecast rows; rows tied at the cut count pro rata."""
    vals, inv = np.unique(-f, return_inverse=True)       # descending forecast
    W = np.bincount(inv, weights=w, minlength=len(vals))
    WY = np.bincount(inv, weights=w * y, minlength=len(vals))
    cw = np.cumsum(W)
    g = int(np.searchsorted(cw, k, side="left"))
    if g >= len(vals):
        return float(WY.sum())
    above_w = cw[g] - W[g]
    above_y = WY[:g].sum()
    return float(above_y + (k - above_w) * (WY[g] / W[g] if W[g] > 0 else 0.0))


def cell_stats(f, p, y, act, band, w) -> dict:
    """Everything the bootstrap needs for one cell under one set of weights (one persistence forecast p)."""
    if w.sum() <= 0 or np.dot(w, y) <= 0 or np.dot(w, 1 - y) <= 0:
        return {}
    mf, mp = murphy(f, y, w), murphy(p, y, w)
    out = {f"F_{k}": v for k, v in mf.items()}
    out.update({f"P_{k}": v for k, v in mp.items()})
    for k in ("brier", "level", "spread", "association", "calibration"):
        out[f"diff_{k}"] = mf[k] - mp[k]
    out["skill"] = 1 - mf["brier"] / mp["brier"] if mp["brier"] > 0 else np.nan
    bf, bp = banded(f, y, w, band, len(CUTS) + 1), banded(p, y, w, act.astype(int), 2)
    out.update({f"F_band_{k}": v for k, v in bf.items() if k != "bands"})
    out.update({f"P_side_{k}": v for k, v in bp.items() if k != "bands"})
    out["auc_F"], out["auc_active"] = auc(y, f, w), auc(y, act.astype(float), w)
    out["diff_auc"] = out["auc_F"] - out["auc_active"]
    k = float(np.dot(w, act))
    out["alerts"] = k
    out["hits_active"] = float(np.dot(w, y * act))
    out["hits_F_same_count"] = hits_at(f, y, w, k)
    out["diff_hits"] = out["hits_F_same_count"] - out["hits_active"]
    n = w.sum()
    for name, side in (("ends", act), ("starts", ~act)):    # active rows hold the spill ends, quiet rows the starts
        ws = w * side
        ns = ws.sum()
        if ns <= 0:
            continue
        bf_s, bp_s = np.dot(ws, (f - y) ** 2) / ns, np.dot(ws, (p - y) ** 2) / ns
        my, mfs, mps = np.dot(ws, y) / ns, np.dot(ws, f) / ns, np.dot(ws, p) / ns
        share = ns / n
        out[f"{name}_contribution"] = share * (bf_s - bp_s)
        out[f"{name}_contribution_level"] = share * ((mfs - my) ** 2 - (mps - my) ** 2)
        out[f"{name}_contribution_rest"] = out[f"{name}_contribution"] - out[f"{name}_contribution_level"]
    return out


INTERVAL_KEYS = ("skill", "F_brier", "P_brier", "diff_brier", "F_level", "P_level", "diff_level", "F_spread", "P_spread",
                 "diff_spread", "F_association", "P_association", "diff_association", "F_calibration", "P_calibration",
                 "diff_calibration", "F_band_reliability", "F_band_resolution", "P_side_reliability", "P_side_resolution",
                 "auc_F", "auc_active", "diff_auc", "hits_F_same_count", "hits_active", "diff_hits",
                 "ends_contribution", "ends_contribution_level", "ends_contribution_rest",
                 "starts_contribution", "starts_contribution_level", "starts_contribution_rest")
SENSITIVITY_KEYS = ("skill", "diff_brier", "diff_level", "diff_spread", "diff_association", "diff_calibration",
                    "diff_auc", "diff_hits", "ends_contribution", "starts_contribution")


def sides(g: pd.DataFrame, pcol: str) -> dict:
    """Spill ends (active rows) and starts (quiet rows), point figures; active rows also by spilling at issue."""
    out = {}
    for name, m in (("active (ends)", g["active"]), ("quiet (starts)", ~g["active"]),
                    ("active, spilling at issue", g["active"] & g["spilling_now"]),
                    ("active, stopped in the 48 h before", g["active"] & ~g["spilling_now"])):
        s = g[m]
        if not len(s):
            out[name] = {"rows": 0}
            continue
        y = s["y"].to_numpy(float)
        d = {"rows": len(s), "spills": int(y.sum()), "spill_rate": float(y.mean()), "mean_F": float(s["p_cal"].mean()),
             "mean_P": float(s[pcol].mean()), "brier_F": float(np.mean((s["p_cal"] - y) ** 2)),
             "brier_P": float(np.mean((s[pcol] - y) ** 2)), "auc_F_within": auc(y, s["p_cal"].to_numpy(float))}
        out[name] = d
    return out


def describe(df: pd.DataFrame, rows: np.ndarray, pcol: str, weights: list[tuple[str, Weights]]) -> dict:
    g = df.iloc[rows]
    y, f, p = g["y"].to_numpy(float), g["p_cal"].to_numpy(float), g[pcol].to_numpy(float)
    act = g["active"].to_numpy(bool)
    band = np.searchsorted(np.asarray(CUTS), f, side="right")
    spill = g[g["y"] == 1]
    out = {"rows": len(g), "overflows": int(g["site_id"].nunique()), "spill_rows": int(y.sum()),
           "spill_overflow_days": int(spill[["site_id", "day"]].drop_duplicates().shape[0]),
           "active_rows": int(act.sum())}
    if not len(g) or not y.sum():
        return out
    out["judged"] = out["spill_overflow_days"] >= MIN_JUDGED
    out["point"] = cell_stats(f, p, y, act, band, np.ones(len(g)))
    out["bands_F"] = [{"band": i, "rows": int((band == i).sum()), "spills": int(y[band == i].sum()),
                       "mean_F": float(f[band == i].mean()) if (band == i).any() else None,
                       "spill_rate": float(y[band == i].mean()) if (band == i).any() else None}
                      for i in range(len(CUTS) + 1)]
    out["sides"] = sides(g, pcol)
    for label, W in weights:
        keys = INTERVAL_KEYS if label == "overflow_and_block" else SENSITIVITY_KEYS
        reps = {k: np.full(len(W), np.nan) for k in keys}
        for r in range(len(W)):
            st = cell_stats(f, p, y, act, band, W.row(r, rows))
            for k in keys:
                reps[k][r] = st.get(k, np.nan)
        out[f"ci_{label}"] = {k: interval(v) for k, v in reps.items()}
    return out


def reading(c: dict) -> dict:
    """The record's reading rule, applied mechanically to one cell (P-trail)."""
    if not c.get("judged"):
        return {"applied": False, "why": f"fewer than {MIN_JUDGED} overflow-days with a spill"}
    ci = c["ci_overflow_and_block"]
    above = lambda k: ci[k]["lo"] is not None and ci[k]["lo"] > 0
    below = lambda k: ci[k]["hi"] is not None and ci[k]["hi"] < 0
    calib = above("diff_calibration")
    rank_fault = below("diff_auc") or above("diff_association")
    rank_better = above("diff_auc") or below("diff_association")
    answer = ("both" if calib and rank_fault else "level (calibration)" if calib else "ranking" if rank_fault
              else "not shown either way")
    where = [s for s in ("starts", "ends") if above(f"{s}_contribution")]
    return {"applied": True, "calibration_fault": calib, "ranking_fault": rank_fault, "F_ranks_better": rank_better,
            "spread_fault": above("diff_spread"), "answer": answer, "loss_sits_on": where}


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", required=True, type=Path)
    ap.add_argument("--state", required=True, type=Path, help="folder with dipcast.duckdb and the three poll files")
    ap.add_argument("--to", dest="last", type=date.fromisoformat, required=True)
    ap.add_argument("--resamples", type=int, default=sr.RESAMPLES)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if a.last > RECORD_LAST:
        raise SystemExit(f"--to is past the calibration check's record ({RECORD_LAST})")
    before = {f: sha256(a.state / f) for f in STATE_FILES} | {"scored": sha256(a.scored)}

    # The rows of the whole record, for the count check. Outcomes after --to are dropped before anything is computed.
    con = duckdb.connect(str(a.state / "dipcast.duckdb"), read_only=True)
    try:
        fc, join = scored_frame(a.scored, con, FIRST, RECORD_LAST)
        rain_log = sr.rain_log_rows(con, FIRST, RECORD_LAST, sr.epoch_ms(fc["issued_at"]))
    finally:
        con.close()
    fc["y"] = fc["y"].astype(float).where(pd.to_datetime(fc["target_day"]).dt.date <= a.last)
    fc = fc.assign(issued_ms=sr.epoch_ms(fc["issued_at"]), target_day=pd.to_datetime(fc["target_day"]))
    fc["rain48"] = sr.rain_48h(fc[["site_id", "issued_ms", "target_day", "lead", "rain_mm"]], rain_log).to_numpy()
    hist = pd.read_parquet(a.state / "live_history.parquet")
    cov = load_coverage(a.state / "live_coverage.parquet")
    polls = pd.read_parquet(a.state / "poll_log.parquet")
    ps = sr.persistence_status(fc[["site_id", "issued_ms"]], hist, cov, polls)
    fc[["known", "active", "spilling_now"]] = ps[["known", "active", "spilling_now"]].to_numpy()
    known, rain_ok, lead0 = fc["known"].to_numpy(bool), fc["rain48"].notna().to_numpy(), (fc["lead"] == 0).to_numpy()
    act, th = fc["active"].to_numpy(bool), (fc["company"] == THAMES).to_numpy()
    counts = {"rows": join["issue_time_matches"], "status_known": int(known.sum()), "rain_both_days": int(rain_ok.sum()),
              "common": int((known & rain_ok).sum()), "lead0_known_active": int((lead0 & known & act).sum()),
              "lead0_known_quiet": int((lead0 & known & ~act).sum()), "thames_status_known": int((th & known).sum()),
              "thames_common": int((th & known & rain_ok).sum())}
    check = {"counts": counts, "expected": EXPECTED_COUNTS, "join": join, "matches": counts == EXPECTED_COUNTS}
    if not check["matches"]:
        out = {"inputs": before, "count_check": check, "stopped": "counts differ from the interim read's"}
        if a.out:
            a.out.write_text(json.dumps(out, indent=1, default=float) + "\n")
        print(json.dumps(check, indent=1, default=float))
        raise SystemExit("count check failed: stopped before any outcome is used")

    # The analysis rows: target days to --to.
    df = fc[fc["target_day"].dt.date <= a.last].reset_index(drop=True)
    df["day"] = df["target_day"].dt.strftime("%Y-%m-%d")
    lead, y = df["lead"].to_numpy(int), df["y"].to_numpy(float)
    known, act = df["known"].to_numpy(bool), df["active"].to_numpy(bool)
    rain_ok = df["rain48"].notna().to_numpy()
    df["p_trail"] = sr.trailing_chances(df["issue_day"], df["target_day"], lead, act, y, known)
    df["p_rain"] = sr.trailing_chances(df["issue_day"], df["target_day"], lead, sr.is_wet(df["rain48"].to_numpy()), y, rain_ok)
    p_in = np.full(len(df), np.nan)
    fitted_in = {}
    for k in np.unique(lead):
        for s in (True, False):
            m = known & (lead == k) & (act == s)
            p_in[m] = y[m].mean() if m.any() else np.nan
            fitted_in[f"lead{k}_{'active' if s else 'quiet'}"] = {"rows": int(m.sum()), "chance": float(p_in[m][0]) if m.any() else None}
    df["p_in"] = p_in
    cell_ok = df["p_trail"].notna().to_numpy() & df["p_rain"].notna().to_numpy()

    draws = sr.Draws(df["site_id"].to_numpy(), sr.block_of(df["target_day"]), a.resamples, sr.SEED)
    weights = [("overflow_and_block", Weights(draws, True)), ("overflow_only", Weights(draws, False))]
    comp = df["company"].to_numpy()
    named = (comp != THAMES) & (comp != "unknown") & pd.notna(comp)
    cells = {"Thames Water, same day": cell_ok & (comp == THAMES) & (lead == 0),
             "Other eight companies, same day": cell_ok & named & (lead == 0),
             "Thames Water, leads 1-4": cell_ok & (comp == THAMES) & (lead >= 1)}
    results = {}
    for name, m in cells.items():
        rows = np.flatnonzero(m)
        res = {"P-trail": describe(df, rows, "p_trail", weights),
               "P-in": describe(df, rows, "p_in", weights[:1])}
        res["reading"] = reading(res["P-trail"])
        results[name] = res
        print(name, res["P-trail"].get("rows"), res["P-trail"].get("spill_overflow_days"), res["reading"], flush=True)

    after = {f: sha256(a.state / f) for f in STATE_FILES} | {"scored": sha256(a.scored)}
    out = {"record": "docs/THAMES-SAME-DAY-DIAGNOSIS-2026-11.md", "inputs": before, "inputs_unchanged": before == after,
           "window": {"first": str(FIRST), "last": str(a.last)}, "count_check": check,
           "settings": {"resamples": a.resamples, "seed": sr.SEED, "block_days": sr.BLOCK_DAYS, "cuts": CUTS,
                        "min_judged": MIN_JUDGED, "fit_days": sr.FIT_DAYS, "min_fit_rows": sr.MIN_FIT_ROWS},
           "bootstrap": {"overflows": len(draws.site_codes), "blocks": [int(b) for b in draws.block_codes]},
           "analysis_rows": len(df), "cell_rows": int(cell_ok.sum()),
           "first_cell_day": str(df.loc[cell_ok, "target_day"].min().date()) if cell_ok.any() else None,
           "p_in_fitted": fitted_in, "cells": results}
    text = json.dumps(out, indent=1, default=float)
    if a.out:
        a.out.write_text(text + "\n")
    return out


if __name__ == "__main__":
    main()
