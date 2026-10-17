"""The live check of lead-calibration option B, as stated in docs/LEAD-CALIBRATION-B-TEST-2026-10.md:
both maps applied to the same logged model probabilities (forecast_raw) of the published scored live
forecasts, paired, over a window of target days. Off CI, by hand:

    uv run python scripts/lead_calibration_b_check.py --from 2026-10-18 --to 2026-11-14
    uv run python scripts/lead_calibration_b_check.py --to 2026-10-17          # the secondary check

--csv defaults to the published file (https://swimsignal.co.uk/data/verification_live.csv); --today
to data/processed/lead_calibration.json; --b to docs/LEAD-CALIBRATION-B-TEST-2026-10-map.json.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from dipcast import config

CSV_URL = "https://swimsignal.co.uk/data/verification_live.csv"
LEADS_MAX = 4
MIN_SPILLS = 200
MIN_COMPANY_SPILLS = 50
COMPANY_SLACK = 1.02
SANITY_MAE = 0.001


def apply_map(cal: dict, p: np.ndarray, lead: np.ndarray) -> np.ndarray:
    """forecast.calibrate_by_lead for one probability per row: lead clamped to the fitted range."""
    leads = {int(k): v for k, v in cal["leads"].items()}
    kmax = max(leads)
    out = np.empty(len(p))
    k = np.clip(lead, 0, kmax)
    for j in np.unique(k):
        m = k == j
        out[m] = np.interp(p[m], np.asarray(leads[j]["iso_x"], float), np.asarray(leads[j]["iso_y"], float))
    return out


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    idx = np.clip((p * bins).astype(int), 0, bins - 1)
    n = np.bincount(idx, minlength=bins)
    gap = np.abs(np.bincount(idx, weights=p, minlength=bins) - np.bincount(idx, weights=y, minlength=bins))
    return float(gap[n > 0].sum() / n.sum())


def read_rows(src: str) -> pd.DataFrame:
    if src.startswith("http"):
        r = httpx.get(src, timeout=120, headers=config.EA_HEADERS, follow_redirects=True)
        r.raise_for_status()
        text = r.text
    else:
        text = Path(src).read_text(encoding="utf-8")
    return pd.read_csv(io.StringIO(text), comment="#")


def check(rows: pd.DataFrame, today: dict, b: dict) -> dict:
    y = rows["observed"].to_numpy(dtype=float)
    p = rows["forecast_raw"].to_numpy(dtype=float)
    lead = rows["lead"].to_numpy(dtype=int)
    pt, pb = apply_map(today, p, lead), apply_map(b, p, lead)
    res = {"rows": len(rows), "spills": int(y.sum()), "first_day": rows["day"].min(), "last_day": rows["day"].max(),
           "sanity_mae": float(np.abs(pt - rows["forecast_calibrated"].to_numpy(dtype=float)).mean())}
    res["brier_today"], res["brier_b"] = float(np.mean((pt - y) ** 2)), float(np.mean((pb - y) ** 2))
    res["ece_today"], res["ece_b"] = ece(y, pt), ece(y, pb)
    res["mean_today"], res["mean_b"], res["observed"] = float(pt.mean()), float(pb.mean()), float(y.mean())
    comp = []
    for c, g in rows.assign(pt=pt, pb=pb).groupby("company"):
        yy = g["observed"].to_numpy(dtype=float)
        comp.append({"company": c, "rows": len(g), "spills": int(yy.sum()), "observed": float(yy.mean()),
                     "mean_today": float(g["pt"].mean()), "mean_b": float(g["pb"].mean()),
                     "brier_today": float(np.mean((g["pt"] - yy) ** 2)), "brier_b": float(np.mean((g["pb"] - yy) ** 2))})
    res["by_company"] = comp
    bins = np.clip((pt * 10).astype(int), 0, 9) / 10
    res["by_bin_of_today"] = [{"bin": float(k), "rows": int((bins == k).sum()), "observed": float(y[bins == k].mean()),
                               "today": float(pt[bins == k].mean()), "b": float(pb[bins == k].mean())}
                              for k in np.unique(bins)]
    res["L1"] = res["brier_b"] < res["brier_today"]
    res["L2_failing"] = [r["company"] for r in comp
                         if r["spills"] >= MIN_COMPANY_SPILLS and r["brier_b"] > COMPANY_SLACK * r["brier_today"]]
    res["L2"] = not res["L2_failing"]
    res["L3"] = res["ece_b"] <= res["ece_today"]
    res["enough"] = res["spills"] >= MIN_SPILLS
    res["sane"] = res["sanity_mae"] < SANITY_MAE
    res["pass"] = bool(res["sane"] and res["enough"] and res["L1"] and res["L2"] and res["L3"])
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=CSV_URL)
    ap.add_argument("--today", default=str(config.PROCESSED / "lead_calibration.json"))
    ap.add_argument("--b", default=str(config.ROOT / "docs" / "LEAD-CALIBRATION-B-TEST-2026-10-map.json"))
    ap.add_argument("--from", dest="start", default=None)
    ap.add_argument("--to", dest="end", default=None)
    a = ap.parse_args()
    rows = read_rows(a.csv)
    if a.start:
        rows = rows[rows["day"] >= a.start]
    if a.end:
        rows = rows[rows["day"] <= a.end]
    res = check(rows, json.loads(Path(a.today).read_text()), json.loads(Path(a.b).read_text()))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
