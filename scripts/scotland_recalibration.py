"""Scotland trial: a calibration map for Scottish overflows (after Gate A, docs/SCOTLAND-HINDCAST-2026-11.md). Off CI.

Gate A passed on 1 November 2026, but the model forecast 72% of the spill-days that happened: in the bands from
0.1 to 0.6, spills happened 8 to 15 points more often than forecast. A Scottish forecast shown as it stands would
understate the chance of a spill. This script fits one correction and checks it on a year it was not fitted on.
It writes the map (data/processed/scotland_calibration.json) and a summary of scores (no rows,
docs/SCOTLAND-RECALIBRATION-2026-11.json). Contains Scottish Water data licensed under the Open Government Licence v3.0.

    DIPCAST_ROOT=<main checkout> uv run python scripts/scotland_recalibration.py --out <dir>

It reads what hindcast_scotland.py reads, from the cache only, and never calls Open-Meteo.

RULE
====

Written 1 November 2026 and committed before the script is first run. Not to be changed after a result is seen.

Status: exploratory. The model and the map's fitting years are separate from the check year, but the check year,
2025, was scored in Gate A's write-up, so its aggregate scores (level 0.73 at lead 0, BSS 0.21) were seen before
this rule was written. A pass here supports a labelled trial, not a confirmed Scottish forecast; Gate B (live)
stays the prospective check.

Model. The production spill model, data/processed/spill_model.pkl (stamp spill=808da63d, the one the live shadow
uses), layer 1 (predict_pooled; no English site offsets apply to Scottish overflows). Not refitted.

Rows. Gate A's set G with Scottish covariates (hindcast_scotland: overflow-years counted in that year and the year
before, emergency overflows left out, uptime rule), built by the same code.

Map. A Platt map on the logit: p' = 1 / (1 + exp(-(a + b * logit(p)))), p clipped to 1e-6 .. 1 - 1e-6, fitted
by unpenalised logistic regression of y on logit(p) over every G row of 2022, 2023 and 2024 at lead 0 (ERA5-Land
rain). One map for all Scottish overflows, every lead and every month. No other form is tried. The map that ships
is this one, fitted on 2022 to 2024; it is not refitted on 2025 after the check.

Check. G's 2025 rows at leads 0, 1, 2 and 3, rain built as hindcast_scotland.score_leads builds it (archived
forecasts for the target day and the two days before, ERA5-Land for longer windows), rows with rain only.
Intervals: hindcast_wales.Scorer's cluster bootstrap (overflows x ISO weeks, 2,000 draws, seed 0).

Pass rule, at every one of the four leads:

- R1. Level of the mapped forecast (sum of forecasts / spill-days) between 0.9 and 1.1.
- R2. The mapped forecast beats the unmapped one: the lower end of the 95% interval of
  1 - Brier(mapped) / Brier(unmapped) is above zero.
- R3. The mapped forecast still beats each overflow's earlier years: the lower end of the 95% interval of BSS
  against hindcast_scotland's earlier-years baseline is above zero.

PASS if all twelve hold. Otherwise FAIL, and the trial does not show Scottish spill chances; it may still show
live overflow status and say why chances are missing.

Reported, not part of the rule: reliability by tenths; the mapped forecast against the same rows with England's
lead calibration (forecast.calibrate_at_lead, what the shadow applies now); wet and dry days. Leads 4 and 5, which
the site also shows, have no archived forecasts here and are not checked; the trial applies the same map there.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hindcast_scotland as hs
import hindcast_wales as hw

from dipcast import config
from dipcast.model.forecast import calibrate_at_lead
from dipcast.model.spill_model import SpillModel

log = logging.getLogger("scotland_recalibration")

FIT_YEARS = [2022, 2023, 2024]
CHECK_YEAR = 2025
LEADS = [0, 1, 2, 3]
LEVEL_RANGE = (0.9, 1.1)
EPS = 1e-6
MAP_OUT = config.PROCESSED / "scotland_calibration.json"
RAW, MAPPED, ENGLISH = "unmapped", "mapped", "england lead calibration"


def logit(p: np.ndarray) -> np.ndarray:
    q = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(q / (1 - q))


def fit_map(p: np.ndarray, y: np.ndarray) -> dict:
    """The Platt map (a, b) of the rule: unpenalised logistic regression of y on logit(p)."""
    lr = LogisticRegression(penalty=None, solver="lbfgs", max_iter=1000)
    lr.fit(logit(p).reshape(-1, 1), np.asarray(y, dtype=int))
    return {"a": float(lr.intercept_[0]), "b": float(lr.coef_[0, 0])}


def apply_map(m: dict, p: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-(m["a"] + m["b"] * logit(p))))


def check_lead(dk: pd.DataFrame, raw: np.ndarray, m: dict, k: int, n_boot: int) -> dict:
    """R1 to R3 at one lead, and the reported extras."""
    mapped = apply_map(m, raw)
    sc = hw.Scorer(dk, n_boot)
    n_sd = int(dk["y"].sum())
    s = sc.summary(mapped, {"earlier_years": dk[hs.EARLIER].to_numpy(), "unmapped": raw}, auc_ci=False)
    level = float(mapped.sum() / max(n_sd, 1))
    r = {"overflows": int(dk["site_id"].nunique()), "rows": len(dk), "spill_days": n_sd, **s,
         "level": level, "level_unmapped": float(raw.sum() / max(n_sd, 1)),
         "R1": bool(LEVEL_RANGE[0] <= level <= LEVEL_RANGE[1]),
         "R2": bool(s["bss_vs_unmapped_ci"][0] > 0),
         "R3": bool(s["bss_vs_earlier_years_ci"][0] > 0)}
    eng = calibrate_at_lead(raw, k)
    r["england_lead_calibration"] = {"brier": float(np.mean((eng - dk["y"].to_numpy()) ** 2)),
                                     "level": float(eng.sum() / max(n_sd, 1))}
    r["reliability"] = hw._reliability(dk["y"].to_numpy(), mapped)
    wet = ((dk["rain_d"].fillna(0) + dk["rain_d1"].fillna(0)) > hs.WET_MM).to_numpy()
    y = dk["y"].to_numpy()
    r["wet_dry"] = {name: {"rows": int(sel.sum()), "spill_days": int(y[sel].sum()),
                           "level": float(mapped[sel].sum() / max(y[sel].sum(), 1)),
                           "brier": float(np.mean((mapped[sel] - y[sel]) ** 2)),
                           "brier_unmapped": float(np.mean((raw[sel] - y[sel]) ** 2))}
                    for name, sel in (("wet", wet), ("dry", ~wet))}
    return r


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True, help="folder for the map and the summary")
    ap.add_argument("--n-boot", type=int, default=hs.N_BOOT)
    args = ap.parse_args(argv)

    oy, cov, lab = hs.load_inputs(hs.EVENTS, hs.COVARIATES, hs.API_ANSWER)
    g = oy[oy["set"] == "G"]
    need, lead_keys = hs.rain_needs(g), hs.lead_needs(g)
    miss, miss_l = hs.missing("archive", need), hs.missing("leads", lead_keys)
    if miss or miss_l:
        raise SystemExit(f"Not run: {len(miss)} archive cell-years and {len(miss_l)} lead files not cached.")
    daily = hs.daily_rain_features(hs.load_rain("archive", need))
    model = SpillModel.load(hs.PRODUCTION)
    rows = hs._set_rows(oy, cov, lab, daily, "G", {"holdout": model})
    fit = rows[rows["year"].isin(FIT_YEARS)]
    m = fit_map(fit[hs.SCOT].to_numpy(), fit["y"].to_numpy())
    log.info("map fitted on %d rows, %d spill-days: a=%.4f b=%.4f", len(fit), int(fit["y"].sum()), m["a"], m["b"])

    d = rows[rows["year"] == CHECK_YEAR]
    daily_lead = hs._daily_leads(lead_keys)
    leads = {}
    for k in LEADS:
        dk = hw.with_lead(d, daily_lead, k)
        dk = dk[dk["rain_d"].notna()].reset_index(drop=True)
        leads[str(k)] = check_lead(dk, model.predict_pooled(hw.features(dk)), m, k, args.n_boot)
    parts = {f"lead {k} {r}": leads[str(k)][r] for k in LEADS for r in ("R1", "R2", "R3")}
    verdict = "PASS" if all(parts.values()) else "FAIL"

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = {"written": pd.Timestamp.now("UTC").date().isoformat(), "method": "platt",
             "fitted_on": FIT_YEARS, "rows": len(fit), "spill_days": int(fit["y"].sum()),
             "model": model.trained_on, "model_file": hs.PRODUCTION.name, **m,
             "verdict": verdict, "rule": "scripts/scotland_recalibration.py",
             "source": "Contains Scottish Water data licensed under the Open Government Licence v3.0."}
    (args.out / MAP_OUT.name).write_text(json.dumps(stamp, indent=1))
    summary = {"what": "Scotland trial calibration map, fitted 2022-24, checked on 2025 at leads 0-3 "
                       "(scripts/scotland_recalibration.py). Summary scores only; no Scottish Water rows.",
               "map": stamp, "verdict": verdict, "parts": parts, "leads": leads,
               "bootstrap": {"draws": args.n_boot, "seed": hs.SEED, "clusters": "overflows x ISO weeks"}}
    summary = hw.clean(summary)
    (args.out / "SCOTLAND-RECALIBRATION-2026-11.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({"verdict": verdict, "map": m, "parts": parts}, indent=1))
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main(sys.argv[1:])
