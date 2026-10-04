"""The May-September 2027 evaluation, exactly as registered in docs/PREREGISTRATION-2027.md.

Reads only published files and the frozen inputs, and never fetches anything:

* --spills: data/verification_live.csv as the site publishes it, one row per scored overflow-day
  forecast (overflow_id, company, day, lead, issued_at, forecast_raw, forecast_calibrated,
  climatology, observed, and, once published, version).
* --ecoli: data/verification_ecoli_live.csv, once published (protocol section 4): one row per
  Environment Agency sample and lead (bathing_water, sample_time, day, ecoli, observed, lead,
  issued_at, forecast, version), with lead and forecast empty where no forecast came before the sample.
* --unscored (optional, once published): one row per overflow-day forecast that was not scored, with
  overflow_id, day, lead, reason.
* data/eval2027/sites.csv and data/eval2027/climatology.json, frozen on 4 October 2026.

Writes a JSON of every figure the protocol names and prints the headline lines. The analysis:
Brier score, skill against the training-only season/site climatology (and the climatology the
Accuracy page uses), reliability in the site's four bands, discrimination (AUC: given one forecast
whose event happened and one whose did not, the share of such pairs where the first got the higher
chance; a tie counts as half), the warning table at the site's High risk line on the same rows,
and coverage: every eligible overflow-day or sample in the season is a cell, scored or not, and none
is dropped from the count. Intervals from a two-way bootstrap (site and 7-day block), RESAMPLES draws
from SEED.

    uv run python scripts/evaluate_2027.py --spills verification_live.csv [--ecoli ...] \\
        [--repo . --tag eval-2027-model] [--out results.json]

The settings below are the registered ones. --from, --to, --resamples and --seed exist for the
dry run and the tests; a run that changes them is not the registered analysis, and its output says so.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "data" / "eval2027" / "sites.csv"
CLIMATOLOGY = ROOT / "data" / "eval2027" / "climatology.json"

# ---- The registered settings (docs/PREREGISTRATION-2027.md) --------------------------------------
SEASON = (date(2027, 5, 1), date(2027, 9, 30))   # target days, Europe/London, inclusive
LEADS = (0, 1, 2, 3, 4)                           # days from the issue day to the target day
ADVANCE = (1, 2, 3, 4)                            # "in advance"; lead 0 is "same day"
BANDS = ("low", "moderate", "high", "very high")
SPILL_CUTS = (0.15, 0.40, 0.70)    # site/levels.js SPILL_CUTS; transport.LOW_CUT and risk_label
ECOLI_CUTS = (0.10, 0.25, 0.50)    # site/levels.js ECOLI_CUTS
SPILL_WARN_AT = 0.40               # forecast_log.SPILL_WARN_AT: High risk, where alerts are sent
ECOLI_WARN_AT = 0.25               # forecast_log.ECOLI_WARN_AT: High risk, rivers only
ECOLI_THRESHOLD = 900              # E. coli per 100 ml; observed = count > 900 (forecast_log.verify_ecoli)
ECOLI_MIN_SAMPLES, ECOLI_MIN_OVER = 100, 10   # forecast_log.ECOLI_MIN_SAMPLES, ECOLI_MIN_EXCEEDANCES
CLIM_FLOOR, CLIM_CAP = 0.001, 0.95  # forecast_log._site_climatology's clip, kept for the season version
BLOCK_DAYS = 7
BLOCK_ANCHOR = date(2027, 5, 1)    # blocks are 1-7 May, 8-14 May, ...; the last, 25-30 Sep, has 6 days
RESAMPLES = 2000
SEED = 20270501
CONFIDENCE = 0.95
# A change to any of these after the tag makes a forecast a candidate's, not the frozen model's.
MODEL_PATHS = (
    "data/processed/spill_model.pkl", "data/processed/lead_calibration.json", "data/processed/ecoli_model.json",
    "data/processed/annual_returns.parquet", "data/processed/id_lookup.parquet", "data/processed/lakes.parquet",
    "src/dipcast/model/", "src/dipcast/network/", "src/dipcast/overflows.py", "src/dipcast/ids.py",
    "src/dipcast/ingest/rainfall.py", "src/dipcast/ingest/flows.py", "src/dipcast/ingest/lakes.py",
    "src/dipcast/ingest/annual_returns.py",
)
# The model's constants in src/dipcast/config.py: changing one is a model change; the rest of the
# file (feed addresses, paths) is not.
MODEL_CONSTANTS = ("SNAP_MAX_M", "RIVER_VELOCITY_MS", "LAKE_VELOCITY_MS", "T90_HOURS", "RECENT_SPILL_HOURS",
                   "MAX_UPSTREAM_KM", "RAIN_GRID_DEG", "FORECAST_DAYS", "FORECAST_PAST_DAYS")
# Changes here after the tag do not change a forecast, but can change how it is scored: listed as
# deviations, rows kept.
WATCHED_PATHS = ("src/dipcast/forecast_log.py", "src/dipcast/ingest/live.py", "src/dipcast/ingest/wqa.py",
                 "src/dipcast/ingest/bwq.py", "data/processed/spill_day_ratio.json", "data/raw/bathing_waters_inland.json",
                 "spots.csv", "scripts/build_site.py")
SPILL_COLUMNS = ["overflow_id", "company", "day", "lead", "issued_at", "forecast_raw", "forecast_calibrated",
                 "climatology", "observed"]
ECOLI_COLUMNS = ["bathing_water", "sample_time", "day", "ecoli", "lead", "issued_at", "forecast"]


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_published(path: Path, **kw) -> pd.DataFrame:
    """A published CSV, skipping the lines at its top that start with '#' (its notes and credits).
    Only those: a '#' later in a line is data (an overflow's name can hold one), so pandas'
    comment='#' is not used."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    start = next((i for i, x in enumerate(lines) if not x.startswith("#")), len(lines))
    kw = {"dtype": {"overflow_id": str, "bathing_water": str, "version": str, "id": str}, **kw}
    return pd.read_csv(io.StringIO("".join(lines[start:])), **kw)


def band_index(p: np.ndarray, cuts: tuple[float, ...]) -> np.ndarray:
    """0-3 for low to very high. A value on a cut belongs to the band above it, as in
    transport.risk_label (r < 0.15 is low) and levels.js (ECOLI_BANDS: p < t)."""
    return np.searchsorted(np.asarray(cuts), np.asarray(p, dtype=float), side="right")


def block_of(days: pd.Series) -> np.ndarray:
    """The 7-day block of each target day, counted from BLOCK_ANCHOR (negative before it)."""
    d = (pd.to_datetime(days) - pd.Timestamp(BLOCK_ANCHOR)).dt.days.to_numpy()
    return np.floor_divide(d, BLOCK_DAYS)


def auc(y: np.ndarray, p: np.ndarray, w: np.ndarray | None = None, vidx: np.ndarray | None = None,
        nv: int | None = None) -> float:
    """Given one row whose event happened (y = 1) and one whose did not, the share of such pairs in
    which the first had the higher forecast; ties count half (the Mann-Whitney form of the ROC area).
    Weighted when w is given. None-like (nan) without both outcomes."""
    y = np.asarray(y).astype(bool)
    w = np.ones(len(y)) if w is None else np.asarray(w, dtype=float)
    if vidx is None:
        _, vidx = np.unique(np.asarray(p, dtype=float), return_inverse=True)
        nv = int(vidx.max()) + 1 if len(vidx) else 0
    pos = np.bincount(vidx[y], weights=w[y], minlength=nv)
    neg = np.bincount(vidx[~y], weights=w[~y], minlength=nv)
    tp, tn = pos.sum(), neg.sum()
    if tp <= 0 or tn <= 0:
        return float("nan")
    below = np.cumsum(neg) - neg
    return float(np.sum(pos * (below + 0.5 * neg)) / (tp * tn))


def warning_table(y: np.ndarray, p: np.ndarray, warn_at: float) -> dict:
    """A forecast at or above warn_at is a warning (forecast_log.warning_counts): hits, misses,
    false alarms and correct quiet ones on the same rows as the Brier score, with the share of
    events warned of, the share of warnings that came true, and the share right beside what
    saying "no" every time gets right."""
    y = np.asarray(y).astype(bool)
    warn = np.asarray(p, dtype=float) >= warn_at
    h, m = int((warn & y).sum()), int((~warn & y).sum())
    fa, q = int((warn & ~y).sum()), int((~warn & ~y).sum())
    n = len(y)
    div = lambda a, b: a / b if b else None
    return {"warn_at": warn_at, "n": n, "hits": h, "misses": m, "false_alarms": fa, "quiet_correct": q,
            "hit_rate": div(h, h + m), "warnings_true": div(h, h + fa), "share_correct": div(h + q, n),
            "always_no_correct": div(fa + q, n)}


# ---- The statistics, as weighted sums so the bootstrap can reuse them ----------------------------

class _Rows:
    """The per-row terms of every bootstrapped figure, computed once for a stratum."""

    def __init__(self, y, p, refs: dict, cuts, warn_at):
        self.y = np.asarray(y, dtype=float)
        self.yb = self.y.astype(bool)
        self.se = (p - self.y) ** 2
        self.se_ref = {k: (c - self.y) ** 2 for k, c in refs.items()}
        self.band = band_index(p, cuts)
        warn = np.asarray(p) >= warn_at
        self.hit, self.miss, self.fa = (warn & self.yb).astype(float), (~warn & self.yb).astype(float), (warn & ~self.yb).astype(float)
        _, self.vidx = np.unique(np.asarray(p, dtype=float), return_inverse=True)
        self.nv = int(self.vidx.max()) + 1 if len(self.vidx) else 0


def _stats(r: _Rows, w: np.ndarray) -> dict:
    """Every bootstrapped figure for one set of rows under weights w (all 1 for the point estimate)."""
    sw = w.sum()
    if sw <= 0:
        return {}
    nan = float("nan")
    out = {"brier": float(np.dot(w, r.se) / sw)}
    for k, se in r.se_ref.items():
        ref = float(np.dot(w, se) / sw)
        out[f"skill_{k}"] = 1.0 - out["brier"] / ref if ref > 0 else nan
    out["auc"] = auc(r.yb, None, w, r.vidx, r.nv)
    wb = np.bincount(r.band, weights=w, minlength=len(BANDS))
    yb = np.bincount(r.band, weights=w * r.y, minlength=len(BANDS))
    for b, name in enumerate(BANDS):
        out[f"observed_{name}"] = float(yb[b] / wb[b]) if wb[b] > 0 else nan
    hits, misses, fas = np.dot(w, r.hit), np.dot(w, r.miss), np.dot(w, r.fa)
    out["hit_rate"] = float(hits / (hits + misses)) if hits + misses > 0 else nan
    out["warnings_true"] = float(hits / (hits + fas)) if hits + fas > 0 else nan
    return out


class Bootstrap:
    """Two-way resampling: each draw takes the sites (overflows, or bathing waters) with replacement
    and, independently, the 7-day blocks with replacement; a row counts (times its site was drawn) x
    (times its block was drawn). All the leads of a site and day share both, so they are resampled
    together. The draws are made once per analysis, in a fixed order (sites, then blocks, per draw),
    and shared by every stratum, so the strata's intervals come from the same draws."""

    def __init__(self, site: np.ndarray, block: np.ndarray, resamples: int, seed: int):
        self.site_codes, self.site = np.unique(site, return_inverse=True)
        self.block_codes, self.block = np.unique(block, return_inverse=True)
        rng = np.random.default_rng(seed)
        ns, nb = len(self.site_codes), len(self.block_codes)
        self.draws = []
        for _ in range(resamples):
            s = np.bincount(rng.integers(0, ns, ns), minlength=ns) if ns else np.zeros(0)
            b = np.bincount(rng.integers(0, nb, nb), minlength=nb) if nb else np.zeros(0)
            self.draws.append((s, b))

    def weights(self, r: int, rows: np.ndarray) -> np.ndarray:
        s, b = self.draws[r]
        return (s[self.site[rows]] * b[self.block[rows]]).astype(float)


def describe(df: pd.DataFrame, refs: list[str], cuts, warn_at, boot: Bootstrap, rows: np.ndarray) -> dict:
    """Point estimates and percentile intervals for one stratum (df: the analysis rows; rows: their
    positions in it). df has y, p and one column per reference."""
    g = df.iloc[rows]
    y, p = g["y"].to_numpy(dtype=float), g["p"].to_numpy(dtype=float)
    out = {"n": len(g), "n_sites": int(g["site"].nunique()), "events": int(y.sum())}
    if not len(g):
        return out
    out["observed_rate"], out["mean_forecast"] = float(y.mean()), float(p.mean())
    refd = {k: g[k].to_numpy(dtype=float) for k in refs}
    band = band_index(p, cuts)
    pre = _Rows(y, p, refd, cuts, warn_at)
    point = _stats(pre, np.ones(len(g)))
    out.update({k: v for k, v in point.items() if not k.startswith("observed_") and k not in ("hit_rate", "warnings_true")})
    for k in refs:
        out[f"brier_ref_{k}"] = float(np.mean((refd[k] - y) ** 2))
    if "p_raw" in g:
        pr = g["p_raw"].to_numpy(dtype=float)
        out["brier_raw"] = float(np.mean((pr - y) ** 2))
    out["reliability"] = [{"band": name, "n": int((band == b).sum()),
                           "mean_forecast": float(p[band == b].mean()) if (band == b).any() else None,
                           "observed": float(y[band == b].mean()) if (band == b).any() else None}
                          for b, name in enumerate(BANDS)]
    out["warning"] = warning_table(y, p, warn_at)
    # The intervals.
    # A draw that picks none of this stratum's rows has no figures: it counts as undefined.
    reps: dict[str, list[float]] = {k: [] for k in point}
    for r in range(len(boot.draws)):
        st = _stats(pre, boot.weights(r, rows))
        for k, values in reps.items():
            values.append(st.get(k, float("nan")))
    lo, hi = 100 * (1 - CONFIDENCE) / 2, 100 * (1 + CONFIDENCE) / 2
    ci = {}
    for k, v in reps.items():
        a = np.asarray(v, dtype=float)
        ok = a[~np.isnan(a)]
        ci[k] = {"lo": float(np.percentile(ok, lo)), "hi": float(np.percentile(ok, hi)),
                 "undefined_draws": int(len(a) - len(ok))} if len(ok) else {"lo": None, "hi": None, "undefined_draws": len(a)}
    for rel in out["reliability"]:
        rel["observed_ci"] = ci.pop(f"observed_{rel['band']}", None)
    out["warning"]["hit_rate_ci"] = ci.pop("hit_rate", None)
    out["warning"]["warnings_true_ci"] = ci.pop("warnings_true", None)
    out["ci"] = ci
    out["undefined_draws_rule"] = "a draw with no event, or none of the stratum's rows, has no AUC or skill: left out of the interval and counted"
    return out


# ---- The frozen model and its candidates ---------------------------------------------------------

def parse_stamp(s) -> dict:
    """'spill=808da63d;cal=9b3cc24c;ecoli=55b5d280;code=0.1.0+be1c85e;rain=open-meteo-forecast' -> dict."""
    if not isinstance(s, str) or "=" not in s:
        return {}
    return dict(part.split("=", 1) for part in s.split(";") if "=" in part)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)


def frozen_hashes(repo: Path, tag: str) -> dict:
    """The spill, cal and ecoli parts of the version stamp the frozen model writes: the first 8 hex
    digits of each model file's MD5 at the tag (forecast.model_version)."""
    out = {}
    for k, path in (("spill", "data/processed/spill_model.pkl"), ("cal", "data/processed/lead_calibration.json"),
                    ("ecoli", "data/processed/ecoli_model.json")):
        r = _git(repo, "show", f"{tag}:{path}")
        out[k] = hashlib.md5(r.stdout).hexdigest()[:8] if r.returncode == 0 else "none"
    out["rain"] = "open-meteo-forecast"
    return out


def _constants(repo: Path, rev: str) -> dict:
    text = _git(repo, "show", f"{rev}:src/dipcast/config.py").stdout.decode(errors="replace")
    return {k: (m.group(1).strip() if (m := re.search(rf"^{k}\s*=\s*([^#\n]+)", text, re.MULTILINE)) else None) for k in MODEL_CONSTANTS}


def code_changes(repo: Path, tag: str, sha: str) -> dict:
    """What changed between the tag and a commit that issued forecasts: model files (a candidate),
    the model's constants in config.py (a candidate) and watched files (a deviation, rows kept)."""
    if _git(repo, "cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        return {"known": False}
    names = lambda paths: [x for x in _git(repo, "diff", "--name-only", tag, sha, "--", *paths).stdout.decode().splitlines() if x]
    a, b = _constants(repo, tag), _constants(repo, sha)
    return {"known": True, "model": names(MODEL_PATHS) + [f"config.py {k}" for k in MODEL_CONSTANTS if a[k] != b[k]],
            "watched": names(WATCHED_PATHS)}


def split_versions(df: pd.DataFrame, model: dict | None, repo: Path | None, tag: str | None) -> tuple[pd.DataFrame, dict]:
    """Keep the frozen model's rows. A row is the frozen model's when its version stamp has the
    tag's spill, cal, ecoli and rain parts and, when a repository is given, its code commit changed
    no MODEL_PATHS file and no model constant since the tag. Every other row is counted under its
    label and left out. Without a version column nothing can be checked: all rows are kept, and
    the output says so."""
    if "version" not in df:
        return df, {"checked": False, "why": "no version column in the published file"}
    if model is None:
        return df, {"checked": False, "why": "no frozen model given (--tag with --repo, or --model)"}
    stamps = df["version"].map(parse_stamp)
    same = stamps.map(lambda s: all(s.get(k) == v for k, v in model.items()))
    info: dict = {"checked": True, "model": model, "commits": {}}
    keep = same.copy()
    if repo is not None and tag is not None:
        code = stamps.map(lambda s: s.get("code", "").split("+")[-1])
        for sha in sorted(code[same].unique()):
            ch = code_changes(repo, tag, sha) if sha else {"known": False}
            info["commits"][sha or "(none)"] = ch
            if not ch["known"] or ch["model"]:
                keep &= ~(code == sha)
    labels = df["version"].fillna("(no stamp)").where(~keep, "frozen model")
    info["rows_by_label"] = {str(k): int(v) for k, v in labels.value_counts().items()}
    info["left_out"] = int((~keep).sum())
    return df[keep.to_numpy()], info


# ---- The two analyses ----------------------------------------------------------------------------

def _grid(units: pd.DataFrame, n_days: int, leads: tuple[int, ...], scored: pd.DataFrame, by: str | None) -> list[dict]:
    """Cells (eligible unit x day x lead) against scored rows, overall or by a column of the site list."""
    keys = [None] if by is None else sorted(units[by].unique())
    out = []
    for k in keys:
        u = units if k is None else units[units[by] == k]
        for ld in ([None] if by is not None else [None, *leads]):
            ls = leads if ld is None else (ld,)
            s = scored[scored["site"].isin(u["id"]) & scored["lead"].isin(ls)]
            cells = len(u) * n_days * len(ls)
            row = {"cells": cells, "scored": len(s), "not_scored": cells - len(s),
                   "share_scored": len(s) / cells if cells else None}
            if by is not None:
                row = {by: k, **row}
            elif ld is not None:
                row = {"lead": ld, **row}
            out.append(row)
    return out


def evaluate_spills(path: Path, sites: pd.DataFrame, clim: dict, first: date, last: date, resamples: int, seed: int,
                    model: dict | None = None, repo: Path | None = None, tag: str | None = None,
                    unscored: Path | None = None) -> dict:
    raw = read_published(path)
    missing = [c for c in SPILL_COLUMNS if c not in raw]
    if missing:
        raise SystemExit(f"{path}: missing columns {missing}")
    raw["day"] = pd.to_datetime(raw["day"]).dt.date
    out: dict = {"file": str(path), "sha256": sha256(path), "rows_read": len(raw)}
    w = raw[(raw["day"] >= first) & (raw["day"] <= last) & raw["lead"].isin(LEADS)]
    out["rows_in_window"] = len(w)
    units = sites[sites["unit"] == "overflow"]
    inlist = w["overflow_id"].isin(units["id"])
    out["rows_outside_list"] = int((~inlist).sum())
    out["outside_list_overflows"] = int(w.loc[~inlist, "overflow_id"].nunique())
    w = w[inlist]
    w, out["versions"] = split_versions(w, model, repo, tag)
    dup = w.duplicated(["overflow_id", "day", "lead"])
    if dup.any():
        raise SystemExit(f"{path}: {int(dup.sum())} repeated (overflow, day, lead) rows")
    f = clim["spill_month"]["factor"]
    month = pd.to_datetime(w["day"]).dt.month.astype(str)
    df = pd.DataFrame({
        "site": w["overflow_id"].to_numpy(), "day": w["day"].to_numpy(), "lead": w["lead"].astype(int).to_numpy(),
        "y": w["observed"].astype(int).to_numpy(), "p": w["forecast_calibrated"].astype(float).to_numpy(),
        "p_raw": w["forecast_raw"].astype(float).to_numpy(),
        "site_rate": w["climatology"].astype(float).to_numpy(),
        "season_site": np.clip(w["climatology"].astype(float).to_numpy() * month.map(f).astype(float).to_numpy(), CLIM_FLOOR, CLIM_CAP)})
    meta = units.set_index("id")
    df["company"] = meta.loc[df["site"], "company"].to_numpy()
    df["water"] = meta.loc[df["site"], "water"].to_numpy()
    n_days = (last - first).days + 1
    out["coverage"] = {"unit": "overflow-day forecast: one eligible overflow, one target day, one lead",
                       "eligible_overflows": len(units), "days": n_days,
                       "overall_and_by_lead": _grid(units, n_days, LEADS, df, None),
                       "by_company": _grid(units, n_days, LEADS, df, "company"),
                       "by_water": _grid(units, n_days, LEADS, df, "water")}
    # By 7-day block, with what happened on the scored cells: if the unscored ones bunch in wet
    # weeks, the scores describe the dry ones.
    season_days = pd.Series(pd.date_range(first, last, freq="D").date)
    day_block, row_block = block_of(season_days), block_of(pd.Series(df["day"]))
    out["coverage"]["by_block"] = [
        {"from": str(season_days[day_block == b].min()), "to": str(season_days[day_block == b].max()),
         "cells": len(units) * int((day_block == b).sum()) * len(LEADS), "scored": int((row_block == b).sum()),
         "observed_rate": float(df.loc[row_block == b, "y"].mean()) if (row_block == b).any() else None,
         "mean_forecast": float(df.loc[row_block == b, "p"].mean()) if (row_block == b).any() else None}
        for b in np.unique(day_block)]
    if unscored is not None:
        u = read_published(unscored)
        u["day"] = pd.to_datetime(u["day"]).dt.date
        u = u[(u["day"] >= first) & (u["day"] <= last) & u["lead"].isin(LEADS) & u["overflow_id"].isin(units["id"])]
        out["coverage"]["unscored_by_reason"] = {str(k): int(v) for k, v in u["reason"].value_counts().items()}
        out["coverage"]["unscored_file_sha256"] = sha256(unscored)
    else:
        out["coverage"]["unscored_by_reason"] = None
    boot = Bootstrap(df["site"].to_numpy(), block_of(pd.Series(df["day"])), resamples, seed)
    out["bootstrap"] = {"sites": len(boot.site_codes), "blocks": len(boot.block_codes), "resamples": resamples, "seed": seed}
    refs = ["season_site", "site_rate"]
    strata = [("all leads", None, df.index.to_numpy()),
              ("same day (lead 0)", "primary", np.flatnonzero(df["lead"] == 0)),
              ("in advance (leads 1-4)", "primary", np.flatnonzero(df["lead"].isin(ADVANCE)))]
    strata += [(f"lead {k}", "lead", np.flatnonzero(df["lead"] == k)) for k in LEADS]
    strata += [(f"company: {c}", "company", np.flatnonzero(df["company"] == c)) for c in sorted(df["company"].unique())]
    strata += [(f"water: {x}", "water", np.flatnonzero(df["water"] == x)) for x in sorted(df["water"].unique())]
    out["strata"] = [{"stratum": name, "group": grp, **describe(df, refs, SPILL_CUTS, SPILL_WARN_AT, boot, rows)}
                     for name, grp, rows in strata]
    return out


def evaluate_ecoli(path: Path, sites: pd.DataFrame, clim: dict, first: date, last: date, resamples: int, seed: int,
                   model: dict | None = None, repo: Path | None = None, tag: str | None = None) -> dict:
    raw = read_published(path)
    missing = [c for c in ECOLI_COLUMNS if c not in raw]
    if missing:
        raise SystemExit(f"{path}: missing columns {missing}")
    raw["day"] = pd.to_datetime(raw["day"]).dt.date
    raw["sample_time"] = pd.to_datetime(raw["sample_time"], utc=True)
    raw["issued_at"] = pd.to_datetime(raw["issued_at"], utc=True)
    out: dict = {"file": str(path), "sha256": sha256(path), "rows_read": len(raw)}
    units = sites[sites["unit"] == "bathing_water"]
    w = raw[(raw["day"] >= first) & (raw["day"] <= last)]
    inlist = w["bathing_water"].isin(units["id"])
    out["samples_outside_list"] = int(w.loc[~inlist, ["bathing_water", "sample_time"]].drop_duplicates().shape[0])
    w = w[inlist]
    y_of = (w["ecoli"].astype(float) > ECOLI_THRESHOLD).astype(int)
    if "observed" in w and (w["observed"].astype(int) != y_of).any():
        raise SystemExit(f"{path}: 'observed' disagrees with ecoli > {ECOLI_THRESHOLD}")
    w = w.assign(y=y_of)
    samples = w[["bathing_water", "sample_time", "day", "y"]].drop_duplicates(["bathing_water", "sample_time"])
    pairs = w[w["forecast"].notna() & w["lead"].notna()].copy()
    pairs["lead"] = pairs["lead"].astype(int)
    pairs = pairs[pairs["lead"].isin(LEADS)]
    late = pairs["issued_at"] >= pairs["sample_time"]
    out["pairs_issued_after_sample"] = int(late.sum())     # not a forecast of that sample: left out, counted
    pairs = pairs[~late]
    pairs, out["versions"] = split_versions(pairs, model, repo, tag)
    if pairs.duplicated(["bathing_water", "sample_time", "lead"]).any():
        raise SystemExit(f"{path}: repeated (bathing water, sample, lead) rows")
    meta = units.set_index("id")
    rate = clim["ecoli_site"]["rate"]
    trate = clim["ecoli_type"]["rate"]
    kind = meta.loc[pairs["bathing_water"], "water"].to_numpy()
    site_rate = np.array([(rate.get(b) or {}).get("rate") or trate[k] for b, k in zip(pairs["bathing_water"], kind, strict=True)], dtype=float)
    df = pd.DataFrame({"site": pairs["bathing_water"].to_numpy(), "day": pairs["day"].to_numpy(),
                       "lead": pairs["lead"].to_numpy(), "y": pairs["y"].to_numpy(),
                       "p": pairs["forecast"].astype(float).to_numpy(), "season_site": site_rate,
                       "type_rate": np.array([trate[k] for k in kind], dtype=float), "water": kind,
                       "company": meta.loc[pairs["bathing_water"], "company"].to_numpy(),
                       "issued_at": pairs["issued_at"].to_numpy(), "sample_time": pairs["sample_time"].to_numpy()})
    sk = samples.assign(water=meta.loc[samples["bathing_water"], "water"].to_numpy())
    forecast_for = set(zip(df["site"], pd.to_datetime(df["sample_time"], utc=True), strict=True))
    sk["has_forecast"] = [(b, t) in forecast_for for b, t in zip(sk["bathing_water"], sk["sample_time"], strict=True)]
    out["coverage"] = {"unit": "sample and lead: one Environment Agency sample at an eligible bathing water, one lead",
                       "samples": len(sk), "samples_over_900": int(sk["y"].sum()),
                       "by_water": [{"water": x, "samples": int((sk["water"] == x).sum()),
                                     "cells": int((sk["water"] == x).sum()) * len(LEADS),
                                     "scored": int((df["water"] == x).sum()),
                                     "samples_with_no_forecast": int(((sk["water"] == x) & ~sk["has_forecast"]).sum())}
                                    for x in ("river", "lake")],
                       "by_lead": [{"lead": k, "cells": len(sk), "scored": int((df["lead"] == k).sum())} for k in LEADS]}
    # The warning table, rivers only: one row per sample, the latest forecast before it whatever its
    # lead (forecast_log.ecoli_warning_table), with the samples that had none counted beside it.
    riv = df[df["water"] == "river"].sort_values("issued_at").groupby(["site", "sample_time"], as_index=False).last()
    n_riv = int((sk["water"] == "river").sum())
    out["warning_rivers"] = {**warning_table(riv["y"].to_numpy(), riv["p"].to_numpy(), ECOLI_WARN_AT),
                             "samples": n_riv, "samples_with_no_forecast": n_riv - len(riv),
                             "unit": "sample (the latest forecast issued before it)"}
    # The Accuracy page's rule (forecast_log.ECOLI_MIN_SAMPLES, ECOLI_MIN_EXCEEDANCES): shown, but
    # called too few to judge, under 100 river samples with a forecast or 10 of them over 900.
    w = out["warning_rivers"]
    w["too_few_to_judge"] = bool(w["n"] < ECOLI_MIN_SAMPLES or w["hits"] + w["misses"] < ECOLI_MIN_OVER)
    if df.empty:
        out["strata"] = []
        return out
    boot = Bootstrap(df["site"].to_numpy(), block_of(pd.Series(df["day"])), resamples, seed)
    out["bootstrap"] = {"sites": len(boot.site_codes), "blocks": len(boot.block_codes), "resamples": resamples, "seed": seed}
    refs = ["season_site", "type_rate"]
    strata = []
    for x in ("river", "lake"):
        grp = "primary" if x == "river" else "water"
        strata += [(f"{x}: all leads", "water", np.flatnonzero(df["water"] == x)),
                   (f"{x}: same day (lead 0)", grp, np.flatnonzero((df["water"] == x) & (df["lead"] == 0))),
                   (f"{x}: in advance (leads 1-4)", grp, np.flatnonzero((df["water"] == x) & df["lead"].isin(ADVANCE)))]
        strata += [(f"{x}: lead {k}", "lead", np.flatnonzero((df["water"] == x) & (df["lead"] == k))) for k in LEADS]
    strata += [(f"river, company: {c}", "company", np.flatnonzero((df["water"] == "river") & (df["company"] == c)))
               for c in sorted(df.loc[df["water"] == "river", "company"].unique())]
    out["strata"] = [{"stratum": name, "group": grp, **describe(df, refs, ECOLI_CUTS, ECOLI_WARN_AT, boot, rows)}
                     for name, grp, rows in strata]
    return out


# ---- Running it ----------------------------------------------------------------------------------

def _fmt(x, d=3):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def clean(x):
    """NaN to None, so the output is strict JSON."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    if isinstance(x, float) and np.isnan(x):
        return None
    return x


def headline(res: dict) -> list[str]:
    """The lines the protocol says are reported first: the primary outcomes with their intervals,
    the share of cells scored and whether the frozen model's rows could be told apart."""
    lines = [f"{res['label']}"]
    for key, title in (("spills", "Spill forecasts"), ("ecoli", "E. coli estimate")):
        part = res.get(key)
        if not part or "strata" not in part:
            lines.append(f"{title}: {part.get('status') if part else 'not run'}")
            continue
        v = part.get("versions") or {}
        lines.append(f"{title}, frozen-model check: " + (f"{v.get('left_out', 0):,} rows of other versions left out"
                                                         if v.get("checked") else f"not made ({v.get('why')})"))
        cov = part["coverage"]
        if key == "spills":
            c = cov["overall_and_by_lead"][0]
            lines.append(f"{title}, cells scored: {c['scored']:,} of {c['cells']:,} ({100 * c['share_scored']:.1f}%); "
                         f"rows for overflows outside the list: {part['rows_outside_list']:,}")
        else:
            lines.append(f"{title}, samples: {cov['samples']:,} ({cov['samples_over_900']:,} over 900); "
                         + "; ".join(f"{w['water']}: {w['samples_with_no_forecast']:,} with no forecast" for w in cov["by_water"]))
        for s in part["strata"]:
            if s["group"] != "primary" or not s["n"]:
                continue
            ci = s.get("ci", {})
            sk, au = ci.get("skill_season_site", {}), ci.get("auc", {})
            lines.append(f"{title}, {s['stratum']}: n {s['n']:,}, events {s['events']:,}; Brier {_fmt(s['brier'], 4)}; "
                         f"skill vs season/site climatology {_fmt(s.get('skill_season_site'))} "
                         f"[{_fmt(sk.get('lo'))}, {_fmt(sk.get('hi'))}]; AUC {_fmt(s.get('auc'))} [{_fmt(au.get('lo'))}, {_fmt(au.get('hi'))}]")
    return lines


def recorded_hashes(protocol: Path = ROOT / "docs" / "PREREGISTRATION-2027.md") -> dict:
    """The SHA-256 the protocol records for each frozen file, from its table rows '| `path` | `hash` |'."""
    return dict(re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|", protocol.read_text())) if protocol.exists() else {}


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spills", type=Path, required=True)
    ap.add_argument("--ecoli", type=Path)
    ap.add_argument("--unscored", type=Path)
    ap.add_argument("--sites", type=Path, default=SITES)
    ap.add_argument("--climatology", type=Path, default=CLIMATOLOGY)
    ap.add_argument("--from", dest="first", type=date.fromisoformat, default=SEASON[0])
    ap.add_argument("--to", dest="last", type=date.fromisoformat, default=SEASON[1])
    ap.add_argument("--resamples", type=int, default=RESAMPLES)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--repo", type=Path, help="a clone holding the tag and every commit in the version stamps")
    ap.add_argument("--tag", help="the frozen model's tag, eval-2027-model")
    ap.add_argument("--model", help="the frozen stamp parts, 'spill=..;cal=..;ecoli=..;rain=..' (else read from --tag)")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    sites = read_published(a.sites, dtype=str, keep_default_na=False)
    clim = json.loads(a.climatology.read_text())
    model = parse_stamp(a.model) if a.model else (frozen_hashes(a.repo, a.tag) if a.repo and a.tag else None)
    files = {"scripts/evaluate_2027.py": sha256(Path(__file__)), "data/eval2027/sites.csv": sha256(a.sites),
             "data/eval2027/climatology.json": sha256(a.climatology)}
    recorded = recorded_hashes()
    match = all(recorded.get(k) == v for k, v in files.items())
    registered = match and (a.first, a.last, a.resamples, a.seed) == (*SEASON, RESAMPLES, SEED)
    res = {"label": a.label or ("registered analysis" if registered else
                                "NOT the registered analysis (settings or frozen files differ from the protocol)"),
           "registered_settings": registered,
           "settings": {"from": str(a.first), "to": str(a.last), "leads": list(LEADS), "spill_cuts": list(SPILL_CUTS),
                        "ecoli_cuts": list(ECOLI_CUTS), "spill_warn_at": SPILL_WARN_AT, "ecoli_warn_at": ECOLI_WARN_AT,
                        "ecoli_threshold": ECOLI_THRESHOLD, "block_days": BLOCK_DAYS, "block_anchor": str(BLOCK_ANCHOR),
                        "resamples": a.resamples, "seed": a.seed, "confidence": CONFIDENCE},
           "frozen_files": {k: {"sha256": v, "as_registered": recorded.get(k) == v} for k, v in files.items()}}
    res["spills"] = evaluate_spills(a.spills, sites, clim, a.first, a.last, a.resamples, a.seed, model, a.repo, a.tag, a.unscored)
    res["ecoli"] = (evaluate_ecoli(a.ecoli, sites, clim, a.first, a.last, a.resamples, a.seed, model, a.repo, a.tag)
                    if a.ecoli else {"status": "not run: no E. coli file given"})
    res = clean(res)
    if a.out:
        a.out.write_text(json.dumps(res, indent=1, default=str, allow_nan=False) + "\n")
    print("\n".join(headline(res)))
    return res


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
