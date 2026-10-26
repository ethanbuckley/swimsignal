"""docs/SOIL-MOISTURE-TEST-2026-10.md, question 2: soil moisture in the nine-company spill model.

    q2.py <soil dir> <out dir>

D2's rows (scripts/train.py _frame, as scripts/live_status_test.py builds them), D2's fit, and two arms fitted on 2024
and scored on 2025 with ERA5-Land rain:
  add      D2's fifteen inputs plus sm28
  replace  D2's inputs without api, rain_7d and rain_30d, plus sm28
sm28 is ERA5-Land soil_moisture_7_to_28cm (m3/m3) at 00:00 UTC of day d at the overflow's 0.25-degree node (fetch.py
q2), NaN where missing; monotone, like the rain inputs. A refit of D2's own inputs is reported as a check of the fit.
The baseline is D2's candidate, spill_model_nine_2024.pkl, in DIPCAST_STATE (data/processed). The week bootstrap is
the live-status test's. Stops if the rows, the subsample or the baseline's 2025 Brier are not D2's.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fetch import Q2_YEARS, node
from live_status_test import NEG_FRAC, PRIOR_STRENGTH, RECENCY, boot_interval, step, week_codes
from train import NINE_PATH, _frame

from dipcast import config
from dipcast.ingest.rainfall import cell_key
from dipcast.model import spill_model as sm
from dipcast.model.features import ALL_FEATURES, MONOTONE, daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel
from dipcast.model.training import NINE, cells_of, ece, load_events, load_rain, site_years
from dipcast.model.verify import reliability_table, scores

SM = "sm28"
PROXIES = ["api", "rain_7d", "rain_30d"]
ARMS = {"refit": list(ALL_FEATURES), "add": [*ALL_FEATURES, SM], "replace": [f for f in ALL_FEATURES if f not in PROXIES] + [SM]}
N_BOOT = 2000
CANDIDATE_SHA = "1603678923cc"
D2_BRIER = 0.03615
DAY0 = pd.Timestamp("2024-01-01", tz="UTC")
N_DAYS = 731


class Soil:
    """sm28 per node and UTC day of 2024-25: the hourly value stamped 00:00 UTC."""

    def __init__(self, soil: Path):
        frames = [pd.read_parquet(f) for y in Q2_YEARS for f in sorted(soil.glob(f"q2_*_{y}.parquet"))]
        s = pd.concat(frames, ignore_index=True)
        s = s[s["time"].dt.hour == 0]
        s = s[~s.duplicated(["cell_lat", "cell_lon", "time"], keep="last")]
        self.got = s.drop_duplicates(["cell_lat", "cell_lon"])[["cell_lat", "cell_lon", "got_lat", "got_lon"]]
        self.keys = pd.Index([cell_key(a, b) for a, b in zip(self.got.cell_lat, self.got.cell_lon, strict=True)])
        self.v = np.full((len(self.keys), N_DAYS), np.nan, np.float32)
        ki = self.keys.get_indexer([cell_key(a, b) for a, b in zip(s.cell_lat, s.cell_lon, strict=True)])
        di = ((s["time"] - DAY0) // pd.Timedelta(days=1)).to_numpy()
        ok = (di >= 0) & (di < N_DAYS)
        self.v[ki[ok], di[ok]] = s["sm"].to_numpy()[ok]

    def at(self, frame: pd.DataFrame, sites: pd.DataFrame) -> np.ndarray:
        """sm28 for rows (site_id, day), the node from `sites`' position (the year's site list); NaN if none."""
        pos = sites.drop_duplicates("site_id").set_index("site_id")
        a, b = node(pos.loc[frame["site_id"], "lat"].to_numpy(), pos.loc[frame["site_id"], "lon"].to_numpy())
        ki = self.keys.get_indexer([cell_key(x, y) for x, y in zip(a, b, strict=True)])
        di = ((frame["day"] - DAY0) // pd.Timedelta(days=1)).to_numpy().astype(np.int64)
        out = np.full(len(frame), np.nan, np.float32)
        ok = ki >= 0
        out[ok] = self.v[ki[ok], di[ok]]
        return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(soil_dir: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = config.PROCESSED / NINE_PATH.name
    checks: dict = {"baseline_sha256": sha(path),
                    "inputs_sha256": {f.name: sha(f) for f in sorted(config.PROCESSED.glob("*.parquet"))}}
    assert checks["baseline_sha256"].startswith(CANDIDATE_SHA), f"{path.name} is not D2's candidate"
    base = SpillModel.load(path)
    sm.MONOTONE = {**MONOTONE, SM: 1}   # wetter ground can only raise the risk, as more rain can

    # ---- D2's rows (scripts/live_status_test.py prepare, without the status)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    labels = spill_days(ev)
    s24, _ = site_years(ar, ev, NINE, 2024)
    s25, _ = site_years(ar, ev, NINE, 2025)
    rain = load_rain(cells_of(pd.concat([s24, s25])))
    step(f"rain loaded: {len(rain)} cell-hours")
    daily = daily_rain_features(rain)
    del rain
    train = _frame(s24, 2024, daily, labels)
    test = _frame(s25, 2025, daily, labels)
    del daily
    step(f"site-days: train {len(train)}, test {len(test)}")
    assert len(train) == 4_976_868 and len(test) == 5_077_150, "not D2's rows (its Results: 4,976,868 and 5,077,150)"
    y24 = train["y"].to_numpy()
    sub = (y24 == 1) | (np.random.default_rng(0).random(len(y24)) < NEG_FRAC)
    assert sub.sum() == 1_569_401, "not D2's subsample (its log: 1,569,401 of 4,976,868 rows used)"
    y = test["y"].to_numpy()
    p_base = base.predict(test)
    checks["baseline_all_nine_brier"] = float(((p_base - y) ** 2).mean())
    assert round(checks["baseline_all_nine_brier"], 5) == D2_BRIER, f"baseline gives {checks['baseline_all_nine_brier']:.5f}"
    step(f"baseline reproduces: {checks['baseline_all_nine_brier']:.5f}")

    # ---- sm28
    soil = Soil(Path(soil_dir))
    train[SM] = soil.at(train, s24)
    test[SM] = soil.at(test, s25)
    gl = soil.got
    checks["soil"] = {"nodes": len(soil.keys),
                      "node_to_returned_point_km_max": float(np.max(np.hypot(
                          (gl.got_lat - gl.cell_lat) * 111.2, (gl.got_lon - gl.cell_lon) * 111.2 * np.cos(np.radians(gl.cell_lat))))),
                      "missing_train": int(np.isnan(train[SM]).sum()), "missing_test": int(np.isnan(test[SM]).sum()),
                      "train": {"mean": float(np.nanmean(train[SM])), "sd": float(np.nanstd(train[SM])),
                                "min": float(np.nanmin(train[SM])), "max": float(np.nanmax(train[SM]))},
                      "corr_2024": {f: float(train[[SM, f]].dropna().corr().iloc[0, 1]) for f in [*PROXIES, "rain_d"]}}
    step(f"sm28: {checks['soil']}")

    # ---- fit each arm on 2024, D2's settings
    arms = {}
    for a, cols in ARMS.items():
        m = SpillModel(features=cols).fit_pooled(train, neg_frac=NEG_FRAC)
        m.fit_site_offsets(train, prior_strength=PRIOR_STRENGTH, recency=RECENCY)
        arms[a] = m
        checks.setdefault("iterations", {})[a] = int(m.clf.n_iter_)
        step(f"{a}: fitted ({m.clf.n_iter_} iterations)")
    del train

    # ---- 2025, ERA5-Land rain
    company = test["company"].to_numpy()
    week = week_codes(test["day"])
    draws = np.random.default_rng(0).integers(0, week.max() + 1, size=(N_BOOT, week.max() + 1))
    preds = {"baseline (D2)": p_base, **{a: m.predict(test) for a, m in arms.items()},
             **{f"{a}, layer 1 only": m.predict_pooled(test) for a, m in arms.items() if a != "refit"},
             "baseline, layer 1 only": base.predict_pooled(test)}
    rows, diffs, rel = [], [], []
    for comp in [*NINE, "all nine"]:
        msk = np.ones(len(y), bool) if comp == "all nine" else company == comp
        for name, p in preds.items():
            s = scores(y[msk], p[msk])
            rows.append({"company": comp, "predictor": name, "rows": s["n"], "base_rate": s["base_rate"],
                         "brier": s["brier"], "auc": s["auc"], "ece": ece(y[msk], p[msk]), "log_loss": s["log_loss"]})
        for name in ("baseline (D2)", "add", "replace"):
            rel.append(reliability_table(y[msk], preds[name][msk]).assign(company=comp, predictor=name))
        for a in ARMS:
            d = (preds[a] - y) ** 2 - (p_base - y) ** 2
            lo, hi = boot_interval(d[msk], week[msk], draws)
            diffs.append({"arm": a, "company": comp, "rows": int(msk.sum()),
                          "brier_arm": float(((preds[a][msk] - y[msk]) ** 2).mean()),
                          "brier_baseline": float(((p_base[msk] - y[msk]) ** 2).mean()),
                          "difference": float(d[msk].mean()), "ci_low": lo, "ci_high": hi})
    res, dif = pd.DataFrame(rows), pd.DataFrame(diffs)
    # Reported only: the add arm against the replace arm, all nine.
    d = (preds["replace"] - y) ** 2 - (preds["add"] - y) ** 2
    checks["replace_minus_add"] = {"difference": float(d.mean()), "ci": boot_interval(d, week, draws)}
    # Reported only: rows with sm28 missing in 2025.
    miss = np.isnan(test[SM].to_numpy())
    if miss.any():
        checks["missing_rows_2025"] = {a: float((((preds[a] - y) ** 2) - ((p_base - y) ** 2))[miss].mean()) for a in ("add", "replace")}

    # ---- the conditions
    b = res.set_index(["company", "predictor"])
    dd = dif.set_index(["arm", "company"])
    cond = {}
    for a in ("add", "replace"):
        worse = [c for c in NINE if dd.loc[(a, c), "difference"] > 0 and dd.loc[(a, c), "ci_low"] > 0]
        ece_fail = [c for c in NINE if not (b.loc[(c, a), "ece"] <= b.loc[(c, "baseline (D2)"), "ece"] or b.loc[(c, a), "ece"] <= 0.02)]
        cond[a] = {"1 gain, all nine": bool(dd.loc[(a, "all nine"), "difference"] < 0 and dd.loc[(a, "all nine"), "ci_high"] < 0),
                   "2 no company clearly worse": not worse,
                   "3 reliability": not ece_fail,
                   "companies clearly worse": worse, "ECE failures": ece_fail}
        cond[a]["passes"] = all(v for k, v in cond[a].items() if k[0].isdigit())
    checks["conditions"] = cond
    checks["verdict"] = {"soil moisture adds (add passes)": cond["add"]["passes"],
                         "soil moisture beats the rain proxies (replace passes)": cond["replace"]["passes"]}
    pd.set_option("display.width", 220)
    print("\n=== 2025, ERA5-Land rain: arm minus baseline, 95% week-cluster bootstrap ===")
    print(dif.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print("\n=== Scores ===")
    print(res.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print("\n=== Conditions ===")
    print(json.dumps(cond, indent=1))
    res.to_csv(out / "scores.csv", index=False)
    dif.to_csv(out / "differences.csv", index=False)
    pd.concat(rel).to_csv(out / "reliability.csv", index=False)
    gl.to_csv(out / "nodes.csv", index=False)
    (out / "checks.json").write_text(json.dumps(checks, indent=1, default=str))
    step("tables written")


if __name__ == "__main__":
    main(*sys.argv[1:])
