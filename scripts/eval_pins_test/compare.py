"""Reports what docs/EVAL-PINS-TEST-2026-10.md says will be reported, from two finished runs of
run_variant.sh: the E. coli chain with the old pins (bare) and with the site's (site). Outputs only.

    DIAG_DIR=<scratch> python scripts/eval_pins_test/compare.py [ref=bare] [new=site]

1. The check. At the 35 bathing waters other than CHANGED, both runs score the same samples, with the same
   upstream count and rain, and risk_model and the replayed exposures within TOL; no run tried the network.
   If it fails the change does more than the statement says: stop and report, do not read on.
2. The published measures, from each run's own outputs.
3. The three bathing waters whose upstream overflows change.
4. Paired bootstraps on the samples both runs keep (paired.py compare).
Writes compare_<ref>_<new>.json under DIAG_DIR.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

HERE = Path(os.environ["DIAG_DIR"])
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paired

FULL = "rain + spill exposure + season (dipcast)"
COMBINED = "rain + spill risk + season"
CHANGED = {"ukf1400-09750": "Colwick Country Park (West Lake)",
           "ukk1500-19002": "River Avon at Queen Elizabeth Gardens",
           "ukj1402-11946": "Wolvercote Mill Stream"}
# Fixed before any run. The site's pins use spots.csv's position, the EA's rounded to 5 decimals (at most
# 0.6 m away); at the 35 other sites that moved single transport weights by at most 3e-5.
TOL = 0.001


def processed(v: str) -> Path:
    return HERE / "roots" / v / "data/processed"


def _occ(d: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return d.assign(occ=d.groupby(keys).cumcount())


def check(ref: str, new: str) -> dict:
    out = {}
    a, b = (_occ(pd.read_parquet(processed(v) / "ecoli_validation_rows.parquet"), ["bw_id", "sample_time"]) for v in (ref, new))
    m = a.merge(b, on=["bw_id", "sample_time", "occ"], how="outer", suffixes=("_a", "_b"), indicator=True)
    o = m[~m.bw_id.isin(CHANGED)]
    same_rain = (o.rain_48h_a == o.rain_48h_b) | (o.rain_48h_a.isna() & o.rain_48h_b.isna())
    out["rows"] = {"samples_other_sites": len(o), "unpaired": int((o["_merge"] != "both").sum()),
                   "upstream_differs": int((o.upstream_a != o.upstream_b).sum()),
                   "rain_48h_differs": int((~same_rain).sum()),
                   "risk_model_max_abs_diff": float((o.risk_model_a - o.risk_model_b).abs().max())}
    ea, eb = (pd.read_parquet(processed(v) / "ecoli_exposure_leads.parquet") for v in (ref, new))
    e = ea.merge(eb, on=["bw_id", "day", "lead"], how="outer", suffixes=("_a", "_b"), indicator=True)
    eo = e[~e.bw_id.isin(CHANGED)]
    out["exposure"] = {"rows_other_sites": len(eo), "unpaired": int((eo["_merge"] != "both").sum()),
                       **{f"{c}_max_abs_diff": float((eo[f"{c}_a"] - eo[f"{c}_b"]).abs().max())
                          for c in ("risk_prod", "risk_holdout", "missing_share")}}
    attempts = {}
    for v in (ref, new):
        logs = HERE / "logs" / v
        attempts[v] = sum(int(line.split(":")[1]) for f in logs.glob("*.log") for line in f.read_text().splitlines()
                          if line.startswith("network attempts:"))
    out["network_attempts"] = attempts
    out["holds"] = bool(out["rows"]["unpaired"] == 0 and out["rows"]["upstream_differs"] == 0
                        and out["rows"]["rain_48h_differs"] == 0 and out["rows"]["risk_model_max_abs_diff"] <= TOL
                        and out["exposure"]["unpaired"] == 0
                        and max(v for k, v in out["exposure"].items() if k.endswith("_max_abs_diff")) <= TOL
                        and not any(attempts.values()))
    return out


def fit_rows(v: str) -> pd.DataFrame:
    """validate_ecoli_combined's rows: samples with upstream overflows and every input."""
    r = pd.read_parquet(processed(v) / "ecoli_validation_rows.parquet")
    return r[r.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "log_ecoli"])


def measures(v: str) -> dict:
    p = processed(v)
    e = json.loads((p / "ecoli_model_eval.json").read_text())
    val = json.loads((p / "ecoli_validation.json").read_text())
    comb = json.loads((p / "ecoli_validation_combined.json").read_text())
    model = json.loads((p / "ecoli_model.json").read_text())
    out = {"n_samples": e["n_samples"], "n_sites": e["n_sites"]}
    for split in ("loyo", "loso"):
        t = {x["model"]: x for x in e[split]}[FULL]
        for k in ("brier", "auc", "brier_river", "auc_river", "brier_lake", "auc_lake"):
            out[f"{split}_{k}"] = t.get(k)
    t = {x["model"]: x for x in e["forward"]["table"]}[FULL]
    out["fwd_brier"], out["fwd_auc"], out["fwd_n"] = t["brier"], t["auc"], t["n"]
    clim = {x["model"]: x for x in e["loyo"]}["climatology by type"]["brier_river"]
    by = {x["lead"]: x["brier_river"] for x in e["by_lead"] if x["exposure"] == "replayed exposure"}
    for k in sorted(by):
        out[f"water_skill_lead{k}"] = 1 - by[k] / clim   # build_site.lead_skill's "water", before it is held
    for part in ("all_sites", "river", "lake"):
        r = {x["predictor"]: x for x in val[part]}.get("risk_model", {})
        for k in ("n", "sites", "spearman_pooled", "spearman_within_site", "auc_gt900", "auc_gt500"):
            out[f"val_{part}_{k}"] = r.get(k)
    out["comb_n"], out["comb_sites"] = comb["n_samples"], comb["sites"]
    out["comb_between_site_rho_risk"] = comb["between_site_rho_risk"]
    out["comb_loyo_within_rho"] = comb["loyo_within_site"][COMBINED]["rho_within"]
    s = fit_rows(v).groupby("bw_id").agg(risk=("risk_model", "mean"), ecoli=("log_ecoli", "mean"))
    out["cross_site_rho"] = float(spearmanr(s.risk, s.ecoli).statistic)   # unrounded
    out["cross_site_sites"] = len(s)
    for k, c in model["coef"].items():
        out[f"coef_{k}"] = c
    out["intercept"] = model["intercept"]
    return out


def sites(v: str) -> dict:
    r = pd.read_parquet(processed(v) / "ecoli_validation_rows.parquet")
    f = fit_rows(v)
    out = {}
    for bw, name in CHANGED.items():
        g, h = r[r.bw_id == bw], f[f.bw_id == bw]
        out[name] = {"samples": len(g), "in_fit": len(h), "upstream": int(g.upstream.max()) if len(g) else None,
                     "risk_mean": float(g.risk_model.mean()) if len(g) else None,
                     "risk_max": float(g.risk_model.max()) if len(g) else None,
                     "rho_within": float(spearmanr(h.risk_model, h.log_ecoli).statistic) if len(h) > 2 else None}
    return out


def main(ref: str = "bare", new: str = "site") -> None:
    c = check(ref, new)
    print("1. check:", json.dumps(c, indent=1))
    res = {"check": c}
    if not c["holds"]:
        print("THE CHECK FAILS: stop; the change does more than the statement says")
        (HERE / f"compare_{ref}_{new}.json").write_text(json.dumps(res, indent=1, default=float))
        return
    t = pd.DataFrame({ref: measures(ref), new: measures(new)})
    t["change"] = pd.to_numeric(t[new], errors="coerce") - pd.to_numeric(t[ref], errors="coerce")
    pd.set_option("display.width", 200)
    print("\n2. published measures\n", t.to_string())
    s = {v: sites(v) for v in (ref, new)}
    print("\n3. changed sites\n", json.dumps(s, indent=1, default=float))
    p = paired.compare(ref, new)
    print("\n4. paired\n", json.dumps(p, indent=1, default=float))
    res.update({"measures": t.to_dict(), "sites": s, "paired": p})
    (HERE / f"compare_{ref}_{new}.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:3])
