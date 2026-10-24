"""The test in docs/COMPANY-CALIBRATION-TEST-2026-11.md (review task A8): layer-2 offsets for the eight companies
outside United Utilities, fitted on the live labels, scored on the four weeks after. Off CI, by hand. Never wired
into the build: nothing here writes to the model or to the site.

Fit once, before the window (the offsets file is then frozen):

    gh release download state -p dipcast.duckdb -D /tmp/a8-state
    uv run python scripts/company_calibration.py fit --scored verification_live.csv \\
        --db /tmp/a8-state/dipcast.duckdb --out docs/COMPANY-CALIBRATION-TEST-2026-11-offsets.json

Check once, on or after 25 Nov 2026, on the file and log published then:

    uv run python scripts/company_calibration.py check --scored verification_live.csv \\
        --db /tmp/a8-state/dipcast.duckdb --out company-calibration-check.json

--scored defaults to the published file (https://swimsignal.co.uk/data/verification_live.csv).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import duckdb
import httpx
import numpy as np
import pandas as pd

from dipcast import config
from dipcast.forecast_log import DECISION_HOUR, LOCAL_TZ
from dipcast.model.forecast import _apply
from dipcast.model.spill_model import EPS, PRIOR_STRENGTH

CSV_URL = "https://swimsignal.co.uk/data/verification_live.csv"
EXCLUDED = "United Utilities"        # its offsets stay production's
LAST_FIT_DAY = "2026-10-25"          # every fitting day is before the window
WINDOW = ("2026-10-26", "2026-11-22")
EXTENDED_END = "2026-12-06"          # the one 14-day extension
MAP_MAE = 0.001                      # a lead map matches an issue day if it rebuilds forecast_calibrated this closely
MAX_UNMATCHED = 0.10                 # share of window rows on unmatched issue days at which the check stops
CHANGED_AT = 0.0001                  # the published file's rounding
MIN_COMPANY_SPILLS = 50
MIN_DAYS = 14                        # fewer, after a spill model change cuts the window, and the check stops
N_BOOT = 2000
SEED = 20261026
OFFSET_BANDS = [0.0, 0.05, 0.2, np.inf]
NOT_IN_LOG = "not in log"
MAPS = [config.PROCESSED / "lead_calibration.json", config.ROOT / "docs" / "LEAD-CALIBRATION-B-TEST-2026-10-map.json"]

# The decision forecasts' version stamps, picked as forecast_log.select_decision_forecasts picks the rows.
SQL = f"""
    WITH f AS (
        SELECT site_id, issue_day, target_day, lead, version, issued_at,
               (issued_at AT TIME ZONE '{LOCAL_TZ}') <= (issue_day::TIMESTAMP + INTERVAL {int(DECISION_HOUR)} HOUR) AS before_cutoff
        FROM forecast_overflows
        WHERE has_live AND coalesce(rain_available, TRUE) AND target_day BETWEEN ? AND ?)
    SELECT site_id, target_day, lead, version FROM f WHERE before_cutoff
    QUALIFY row_number() OVER (PARTITION BY site_id, issue_day, target_day ORDER BY issued_at DESC) = 1
"""


def read_scored(src: str) -> tuple[pd.DataFrame, str]:
    """The scored rows and the SHA-256 of the bytes read."""
    if src.startswith("http"):
        r = httpx.get(src, timeout=120, headers=config.EA_HEADERS, follow_redirects=True)
        r.raise_for_status()
        raw = r.content
    else:
        raw = Path(src).read_bytes()
    rows = pd.read_csv(io.BytesIO(raw), comment="#", dtype={"overflow_id": str})
    return rows, hashlib.sha256(raw).hexdigest()


def spill_stamps(db: str, start: str, end: str) -> pd.DataFrame:
    """overflow_id, day, lead and the spill= part of the version stamp of each decision forecast."""
    con = duckdb.connect(db, read_only=True)
    try:
        fc = con.execute(SQL, [start, end]).df()
    finally:
        con.close()
    return pd.DataFrame({"overflow_id": fc["site_id"].astype(str),
                         "day": pd.to_datetime(fc["target_day"]).dt.strftime("%Y-%m-%d"),
                         "lead": fc["lead"].astype(int),
                         "spill": fc["version"].fillna("").str.extract(r"spill=([^;]*)")[0].fillna("unstamped")})


def fit_offsets(rows: pd.DataFrame, prior: float = PRIOR_STRENGTH, last_day: str = LAST_FIT_DAY) -> pd.DataFrame:
    """Per overflow outside United Utilities: n, e, fitting days and ln((n + prior) / (e + prior)), from lead-0 rows
    on or before `last_day`. Lead 0 only, so each overflow-day counts once and the prior means what it means in
    SpillModel.fit_site_offsets."""
    f = rows[(rows["company"] != EXCLUDED) & (rows["lead"] == 0) & (rows["day"] <= last_day)]
    f = f.assign(p=f["forecast_raw"].astype(float).clip(EPS, 1 - EPS), y=f["observed"].astype(float))
    agg = f.groupby("overflow_id").agg(company=("company", "first"), n=("y", "sum"), e=("p", "sum"),
                                       days=("y", "size"), first_day=("day", "min"), last_day=("day", "max"))
    agg["offset"] = np.log((agg["n"] + prior) / (agg["e"] + prior))
    return agg.reset_index()


def offsets_document(fit: pd.DataFrame, source_sha: str, spill: list[str], prior: float = PRIOR_STRENGTH) -> dict:
    return {"test": "docs/COMPANY-CALIBRATION-TEST-2026-11.md", "source": CSV_URL, "source_sha256": source_sha,
            "first_day": str(fit["first_day"].min()), "last_day": str(fit["last_day"].max()),
            "prior_strength": prior, "recency": 1.0, "spill_stamps": spill,
            "offsets": {r.overflow_id: {"company": r.company, "offset": round(float(r.offset), 6), "n": int(r.n),
                                        "e": round(float(r.e), 6), "days": int(r.days)}
                        for r in fit.sort_values("overflow_id").itertuples()}}


def apply_map(cal: dict, p: np.ndarray, lead: np.ndarray) -> np.ndarray:
    """forecast.calibrate_by_lead for one probability per row: lead clamped to the fitted range."""
    leads = {int(k): v for k, v in cal["leads"].items()}
    k = np.clip(lead, 0, max(leads))
    out = np.empty(len(p))
    for j in np.unique(k):
        m = k == j
        out[m] = _apply(leads[int(j)], p[m])
    return out


def match_maps(rows: pd.DataFrame, maps: list[dict]) -> np.ndarray:
    """Per row, the index of the map that made its forecast_calibrated, chosen per issue day as the map with the
    smallest mean absolute difference, if under MAP_MAE; -1 where none is."""
    p = rows["forecast_raw"].to_numpy(dtype=float)
    lead = rows["lead"].to_numpy(dtype=int)
    cal = rows["forecast_calibrated"].to_numpy(dtype=float)
    err = np.vstack([np.abs(apply_map(m, p, lead) - cal) for m in maps])
    issue = pd.to_datetime(rows["issued_at"], utc=True).dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%d").to_numpy()
    out = np.full(len(rows), -1)
    for d in np.unique(issue):
        m = issue == d
        mae = err[:, m].mean(1)
        if mae.min() < MAP_MAE:
            out[m] = int(mae.argmin())
    return out


def candidate(rows: pd.DataFrame, offsets: dict[str, float], maps: list[dict], which: np.ndarray) -> np.ndarray:
    """map_k(expit(logit(clip(forecast_raw)) + offset)), each row through the map that `which` names."""
    p = rows["forecast_raw"].to_numpy(dtype=float).clip(EPS, 1 - EPS)
    off = rows["overflow_id"].map(offsets).fillna(0.0).to_numpy()
    q = 1.0 / (1.0 + np.exp(-(np.log(p / (1 - p)) + off)))
    lead = rows["lead"].to_numpy(dtype=int)
    out = np.full(len(rows), np.nan)
    for i, m in enumerate(maps):
        s = which == i
        out[s] = apply_map(m, q[s], lead[s])
    return out


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2)) if len(y) else float("nan")


def week_codes(day: pd.Series) -> np.ndarray:
    iso = pd.to_datetime(day).dt.isocalendar()
    return pd.factorize(iso["year"].astype(int) * 100 + iso["week"].astype(int), sort=True)[0]


def boot_interval(diff: np.ndarray, codes: np.ndarray, draws: np.ndarray) -> list[float]:
    """Weeks drawn whole with replacement; the 2.5th and 97.5th percentiles of the mean difference."""
    w = draws.shape[1]
    s = np.bincount(codes, weights=diff, minlength=w)
    n = np.bincount(codes, minlength=w).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        stat = s[draws].sum(1) / n[draws].sum(1)
    stat = stat[np.isfinite(stat)]
    return [float(v) for v in np.percentile(stat, [2.5, 97.5])] if len(stat) else [float("nan")] * 2


def window_end(rows: pd.DataFrame, fit_spill: str, start: str, end: str) -> str | None:
    """The last day before the first target day with a scored row on a spill model other than the fitted one;
    `end` if there is none. `rows` carries each row's `spill` stamp. A row missing from the log (a log downloaded
    before the file was published) says nothing about the model, so it does not cut the window."""
    other = rows[(rows["spill"] != fit_spill) & (rows["spill"] != NOT_IN_LOG)
                 & (rows["day"] >= start) & (rows["day"] <= end)]
    if other.empty:
        return end
    return (pd.Timestamp(other["day"].min()) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def score_block(g: pd.DataFrame) -> dict:
    y = g["observed"].to_numpy(dtype=float)
    pc, pq = g["forecast_calibrated"].to_numpy(dtype=float), g["candidate"].to_numpy(dtype=float)
    flat = np.full(len(y), y.mean()) if len(y) else y
    return {"rows": len(g), "spills": int(y.sum()), "observed": float(y.mean()) if len(y) else None,
            "mean_current": float(pc.mean()) if len(y) else None, "mean_candidate": float(pq.mean()) if len(y) else None,
            "brier_current": brier(pc, y), "brier_candidate": brier(pq, y), "brier_flat": brier(flat, y)}


def check(rows: pd.DataFrame, doc: dict, maps: list[dict], start: str = WINDOW[0], end: str = WINDOW[1],
          n_boot: int = N_BOOT) -> dict:
    """The face checks, then conditions 1 and 2 at every changed company, and what is reported beside them.
    `rows` are the scored rows with a `spill` stamp per row (NaN-free strings)."""
    offsets = {k: v["offset"] for k, v in doc["offsets"].items()}
    fair = {c: v for c, v in doc.get("fair_flat", {}).items()}
    out: dict = {"window": [start, end]}
    fit_spill = doc["spill_stamps"][-1]
    cut = window_end(rows, fit_spill, start, end)
    out["window_end_used"] = cut
    days = (pd.Timestamp(cut) - pd.Timestamp(start)).days + 1
    if days < MIN_DAYS:
        out["verdict"] = f"stopped: the spill model changed; {days} days left, fewer than {MIN_DAYS}"
        return out
    w = rows[(rows["day"] >= start) & (rows["day"] <= cut)].reset_index(drop=True)
    out["rows_not_in_log"] = int((w["spill"] == NOT_IN_LOG).sum())
    uu = w[w["company"] == EXCLUDED]
    out["united_utilities_rows"] = len(uu)
    w = w[w["company"] != EXCLUDED].reset_index(drop=True)
    which = match_maps(w, maps)
    out["unmatched_rows"] = int((which < 0).sum())
    out["unmatched_share"] = float((which < 0).mean()) if len(w) else 0.0
    out["map_rows"] = {str(i): int((which == i).sum()) for i in range(len(maps))}
    if out["unmatched_share"] > MAX_UNMATCHED:
        out["verdict"] = "stopped: more than 10% of window rows on issue days no lead map matches"
        return out
    w = w[which >= 0].reset_index(drop=True)
    which = which[which >= 0]
    w["candidate"] = candidate(w, offsets, maps, which)
    w["offset"] = w["overflow_id"].map(offsets).fillna(0.0)
    # A row with no company in the file belongs to no company's conditions: counted, not judged.
    out["rows_no_company"] = int(w["company"].isna().sum())
    # Face check: with every offset 0 the candidate rebuilds the published forecast.
    zero = candidate(w, {}, maps, which)
    out["face_mae"] = float(np.abs(zero - w["forecast_calibrated"].to_numpy(dtype=float)).mean()) if len(w) else None
    codes = week_codes(w["day"])
    draws = np.random.default_rng(SEED).integers(0, int(codes.max()) + 1, size=(n_boot, int(codes.max()) + 1))
    comp = {}
    for c, g in w.groupby("company"):
        r = score_block(g)
        m = (w["company"] == c).to_numpy()
        y = g["observed"].to_numpy(dtype=float)
        d = (g["candidate"].to_numpy() - y) ** 2 - (g["forecast_calibrated"].to_numpy(dtype=float) - y) ** 2
        r["interval_candidate_minus_current"] = boot_interval(d, codes[m], draws)
        r["changed"] = bool((np.abs(g["candidate"] - g["forecast_calibrated"]) > CHANGED_AT).any())
        if c in fair:
            r["brier_fair_flat"] = brier(np.full(len(y), fair[c]), y)
        r["by_lead"] = {int(k): score_block(gl) for k, gl in g.groupby("lead")}
        band = pd.cut(g["offset"].abs(), OFFSET_BANDS, right=False, labels=["under 0.05", "0.05-0.2", "0.2 and over"])
        r["by_offset_band"] = {str(b): {"rows": len(gb), "overflows": int(gb["overflow_id"].nunique()),
                                        "spills": int(gb["observed"].sum())}
                               for b, gb in g.groupby(band, observed=True)}
        r["condition_1"] = bool(r["brier_candidate"] < r["brier_current"])
        r["condition_2"] = bool(r["brier_candidate"] < r["brier_flat"])
        r["enough_data"] = r["spills"] >= MIN_COMPANY_SPILLS
        comp[c] = r
    out["by_company"] = comp
    changed = [c for c, r in comp.items() if r["changed"]]
    out["changed"] = sorted(changed)
    short = [c for c in changed if not comp[c]["enough_data"]]
    out["short"] = sorted(short)
    failing = [c for c in changed if not (comp[c]["condition_1"] and comp[c]["condition_2"])]
    out["failing"] = sorted(failing)
    if short:
        out["verdict"] = ("not enough data: extend the window to " + EXTENDED_END + ", once" if cut < EXTENDED_END
                          else "inconclusive: not adopted")
    elif failing:
        out["verdict"] = "fails: not adopted"
    else:
        out["verdict"] = "passes: both conditions at every changed company"
    return out


def attach_stamps(rows: pd.DataFrame, db: str, start: str, end: str) -> pd.DataFrame:
    st = spill_stamps(db, start, end)
    out = rows.merge(st, on=["overflow_id", "day", "lead"], how="left")
    out["spill"] = out["spill"].fillna(NOT_IN_LOG)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--scored", default=CSV_URL)
    f.add_argument("--db", required=True)
    f.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("--scored", default=CSV_URL)
    c.add_argument("--db", required=True)
    c.add_argument("--offsets", default=str(config.ROOT / "docs" / "COMPANY-CALIBRATION-TEST-2026-11-offsets.json"))
    c.add_argument("--start", default=WINDOW[0])
    c.add_argument("--end", default=WINDOW[1])
    c.add_argument("--out", required=True)
    a = ap.parse_args()
    rows, sha = read_scored(a.scored)
    if a.cmd == "fit":
        fit = fit_offsets(rows)
        r = attach_stamps(rows[rows["overflow_id"].isin(fit["overflow_id"]) & (rows["lead"] == 0)
                               & (rows["day"] <= LAST_FIT_DAY)], a.db, str(fit["first_day"].min()), LAST_FIT_DAY)
        counts = r["spill"].value_counts()
        # Oldest first, so the last is the model the window is checked against.
        first_seen = r.groupby("spill")["day"].min().sort_values()
        doc = offsets_document(fit, sha, list(first_seen.index))
        doc["spill_stamp_rows"] = {k: int(v) for k, v in counts.items()}
        # The fair flat rate, reported only: each company's observed rate on its fitting rows.
        f0 = rows[(rows["company"] != EXCLUDED) & (rows["lead"] == 0) & (rows["day"] <= LAST_FIT_DAY)]
        doc["fair_flat"] = {k: round(float(v), 6) for k, v in f0.groupby("company")["observed"].mean().items()}
        Path(a.out).write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n")
        print(json.dumps({"overflows": len(fit), "source_sha256": sha, "spill_stamp_rows": doc["spill_stamp_rows"],
                          "sha256": hashlib.sha256(Path(a.out).read_bytes()).hexdigest()}, indent=1))
    else:
        doc = json.loads(Path(a.offsets).read_text())
        doc_sha = hashlib.sha256(Path(a.offsets).read_bytes()).hexdigest()
        maps = [json.loads(p.read_text()) for p in MAPS]
        rows = attach_stamps(rows, a.db, a.start, a.end)
        res = {"scored_sha256": sha, "offsets_sha256": doc_sha, **check(rows, doc, maps, a.start, a.end)}
        Path(a.out).write_text(json.dumps(res, indent=1, default=str))
        print(res["verdict"])


if __name__ == "__main__":
    main()
