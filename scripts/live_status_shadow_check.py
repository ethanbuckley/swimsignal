"""The check for docs/LIVE-STATUS-SHADOW-TEST-2026-10.md: the published scored live forecasts, each joined to
its row in the forecast log, which holds the live-status shadow beside the production forecast
(forecast_overflows.p_status, status_known and the three inputs; model/live_status.py). Conditions 1 to 4 per
lead, 0 to 4, on the same rows for both forecasts.

Off CI, by hand, after the window:

    gh release download state -p dipcast.duckdb -D /tmp/shadow-state
    uv run python scripts/live_status_shadow_check.py --db /tmp/shadow-state/dipcast.duckdb \\
        --start <first target day> --end <last target day> --out shadow-check.json

--scored defaults to the published file (https://swimsignal.co.uk/data/verification_live.csv).
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import duckdb
import httpx
import numpy as np
import pandas as pd

from dipcast import config
from dipcast.forecast_log import DECISION_HOUR, LOCAL_TZ
from dipcast.model.training import ece

CSV_URL = "https://swimsignal.co.uk/data/verification_live.csv"
LEADS = (0, 1, 2, 3, 4)
STATUS = ["spilling_at_issue", "spill_hours_24h", "spill_days_7d"]
N_BOOT = 2000              # live_status_test.py's bootstrap: 2,000 draws from default_rng(0), clusters drawn whole,
SEED = 0                   # one set of draws for every lead, company and subset
MIN_SPILLS = 200           # rows with a spill and a known status, at each lead
MIN_COMPANY_SPILLS = 50    # conditions 2 and 3 apply to a company with at least this many at the lead
ECE_OK = 0.02              # live_status_test.py's condition 4: no higher than production's, or at most this
SANITY_MAE = 0.0001        # the published CSV rounds to 4 decimals
MIN_SHADOW_SHARE = 0.99    # scored rows in the window with a logged shadow

# The decision forecasts, as forecast_log.select_decision_forecasts picks them (the latest issued by
# DECISION_HOUR local time on the issue day, live-fed overflows, rain present), with the shadow.
SQL = f"""
    WITH f AS (
        SELECT site_id, issue_day, target_day, lead, p_cal, p_status, status_known,
               spilling_at_issue, spill_hours_24h, spill_days_7d, issued_at,
               (issued_at AT TIME ZONE '{LOCAL_TZ}') <= (issue_day::TIMESTAMP + INTERVAL {int(DECISION_HOUR)} HOUR) AS before_cutoff
        FROM forecast_overflows
        WHERE has_live AND coalesce(rain_available, TRUE) AND target_day BETWEEN ? AND ?)
    SELECT site_id, target_day, lead, p_cal, p_status, status_known, spilling_at_issue, spill_hours_24h, spill_days_7d
    FROM f WHERE before_cutoff
    QUALIFY row_number() OVER (PARTITION BY site_id, issue_day, target_day ORDER BY issued_at DESC) = 1
"""


def read_scored(src: str) -> pd.DataFrame:
    if src.startswith("http"):
        r = httpx.get(src, timeout=120, headers=config.EA_HEADERS, follow_redirects=True)
        r.raise_for_status()
        text = r.text
    else:
        text = Path(src).read_text(encoding="utf-8")
    return pd.read_csv(io.StringIO(text), comment="#", dtype={"overflow_id": str})


def load_rows(db: str, scored: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """The scored rows from `start` to `end`, each with its logged production forecast (p_db) and shadow.
    A scored row with no row in the log, or a NULL shadow, keeps NaN."""
    sc = scored[(scored["day"] >= start) & (scored["day"] <= end)].copy()
    con = duckdb.connect(db, read_only=True)
    try:
        fc = con.execute(SQL, [start, end]).df()
    finally:
        con.close()
    fc["day"] = pd.to_datetime(fc["target_day"]).dt.strftime("%Y-%m-%d")
    fc = fc.assign(overflow_id=fc["site_id"].astype(str), p_db=fc["p_cal"].astype(float))
    keep = ["overflow_id", "day", "lead", "p_db", "p_status", "status_known", *STATUS]
    return sc.merge(fc[keep], on=["overflow_id", "day", "lead"], how="left")


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2)) if len(y) else float("nan")


def week_codes(day: pd.Series) -> np.ndarray:
    """live_status_test.py's cluster: the ISO week of the (target) day."""
    iso = pd.to_datetime(day).dt.isocalendar()
    return pd.factorize(iso["year"].astype(int) * 100 + iso["week"].astype(int), sort=True)[0]


def day_codes(day: pd.Series) -> np.ndarray:
    return pd.factorize(pd.to_datetime(day), sort=True)[0]


def draws_for(codes: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED) -> np.ndarray:
    w = int(codes.max()) + 1 if len(codes) else 1
    return np.random.default_rng(seed).integers(0, w, size=(n_boot, w))


def boot_interval(diff: np.ndarray, codes: np.ndarray, draws: np.ndarray) -> tuple[float, float]:
    """live_status_test.py's boot_interval: the mean difference over clusters drawn with replacement, 2.5th
    and 97.5th percentiles. A draw that holds no row of the subset is left out (that one gives NaN)."""
    w = draws.shape[1]
    s = np.bincount(codes, weights=diff, minlength=w)
    n = np.bincount(codes, minlength=w).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        stat = s[draws].sum(1) / n[draws].sum(1)
    stat = stat[np.isfinite(stat)]
    if not len(stat):
        return float("nan"), float("nan")
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return float(lo), float(hi)


def compare(g: pd.DataFrame, codes: np.ndarray, draws: np.ndarray, day_c: np.ndarray, day_draws: np.ndarray) -> dict:
    y = g["observed"].to_numpy(dtype=float)
    ps, pp = g["p_status"].to_numpy(dtype=float), g["forecast_calibrated"].to_numpy(dtype=float)
    d = (ps - y) ** 2 - (pp - y) ** 2
    lo, hi = boot_interval(d, codes, draws)
    dlo, dhi = boot_interval(d, day_c, day_draws)
    return {"rows": len(g), "spills": int(y.sum()), "base_rate": float(y.mean()) if len(y) else None,
            "brier_shadow": brier(ps, y), "brier_production": brier(pp, y), "difference": float(d.mean()) if len(d) else None,
            "interval_week": [lo, hi], "interval_day": [dlo, dhi],
            "ece_shadow": ece(y, ps) if len(y) else None, "ece_production": ece(y, pp) if len(y) else None}


def check(rows: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    """Sanity checks, then conditions 1 to 4 at each lead, and what is reported beside them."""
    out: dict = {"rows_in_window": len(rows)}
    have = rows["p_status"].notna()
    out["shadow_share"] = float(have.mean()) if len(rows) else 0.0
    joined = rows["p_db"].notna()
    out["sanity_mae"] = float(np.abs(rows.loc[joined, "p_db"] - rows.loc[joined, "forecast_calibrated"]).mean()) if joined.any() else None
    fall = have & ~rows["status_known"].fillna(False).astype(bool)
    out["fallback_mae"] = float(np.abs(rows.loc[fall, "p_status"] - rows.loc[fall, "p_db"]).mean()) if fall.any() else None
    sane = (out["shadow_share"] >= MIN_SHADOW_SHARE and out["sanity_mae"] is not None and out["sanity_mae"] < SANITY_MAE
            and (out["fallback_mae"] is None or out["fallback_mae"] < 1e-9))
    out["sane"] = bool(sane)
    if not sane:
        out["verdict"] = "stopped: a sanity check failed"
        return out
    r = rows[have].reset_index(drop=True)
    r["status_known"] = r["status_known"].astype(bool)
    codes, day_c = week_codes(r["day"]), day_codes(r["day"])
    draws, day_draws = draws_for(codes, n_boot), draws_for(day_c, n_boot)
    out["weeks"], out["days"] = int(codes.max()) + 1, int(day_c.max()) + 1
    known_spills = r[r["status_known"] & (r["observed"] == 1)].groupby("lead").size()
    out["known_spills_by_lead"] = {int(k): int(known_spills.get(k, 0)) for k in LEADS}
    out["enough_data"] = all(known_spills.get(k, 0) >= MIN_SPILLS for k in LEADS)
    out["known_share_by_company"] = r.groupby("company")["status_known"].mean().round(4).to_dict()
    leads = {}
    for k in LEADS:
        m = (r["lead"] == k).to_numpy()
        g = r[m]
        res = {"all": compare(g, codes[m], draws, day_c[m], day_draws)}
        res["known_only"] = compare(g[g["status_known"]], codes[m][g["status_known"].to_numpy()], draws,
                                    day_c[m][g["status_known"].to_numpy()], day_draws)
        dry = (g["status_known"] & (g["spilling_at_issue"] == 0) & (g["spill_days_7d"] == 0)).to_numpy()
        res["dry_start"] = compare(g[dry], codes[m][dry], draws, day_c[m][dry], day_draws)
        sp = (g["status_known"] & (g["spilling_at_issue"] == 1)).to_numpy()
        res["spilling_at_issue"] = compare(g[sp], codes[m][sp], draws, day_c[m][sp], day_draws)
        res["not_spilling_at_issue"] = compare(g[g["status_known"].to_numpy() & ~sp], codes[m][g["status_known"].to_numpy() & ~sp],
                                               draws, day_c[m][g["status_known"].to_numpy() & ~sp], day_draws)
        comp = {}
        for c, gc in g.groupby("company"):
            mc = (g["company"] == c).to_numpy()
            comp[c] = compare(gc, codes[m][mc], draws, day_c[m][mc], day_draws)
        res["by_company"] = comp
        judged = {c: v for c, v in comp.items() if v["spills"] >= MIN_COMPANY_SPILLS}
        a = res["all"]
        res["conditions"] = {
            "1_gain": bool(a["brier_shadow"] < a["brier_production"] and a["interval_week"][1] < 0),
            "2_no_company_clearly_worse": bool(not any(v["interval_week"][0] > 0 for v in judged.values())),
            "3_reliability": bool(all(v["ece_shadow"] <= v["ece_production"] or v["ece_shadow"] <= ECE_OK
                                      for v in judged.values())),
            "4_dry_start": bool(not (res["dry_start"]["interval_week"][0] > 0)),
        }
        res["companies_judged"] = sorted(judged)
        res["passes"] = all(res["conditions"].values())
        leads[k] = res
    out["leads"] = leads
    if not out["enough_data"]:
        out["verdict"] = "not enough data: extend the window by 14 days, once; then inconclusive"
    else:
        out["verdict"] = {int(k): ("passes" if v["passes"] else "fails") for k, v in leads.items()}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--scored", default=CSV_URL)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", default="shadow-check.json")
    a = ap.parse_args()
    rows = load_rows(a.db, read_scored(a.scored), a.start, a.end)
    res = check(rows)
    Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res.get(k) for k in ("rows_in_window", "shadow_share", "sanity_mae", "sane", "enough_data", "verdict")},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
