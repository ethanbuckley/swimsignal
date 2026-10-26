"""Baseline check for PR #361 (asked 26 Oct 2026, after the rivers-only test's results were seen).

    c_baseline.py <soil dir> <main ecoli_model.json> <rivers run out dir> <out.json> <wales_annual> <wqa dir> <wessex dir> <cache dir>

Run offline in the rivers-only test's root (the frozen data folder after its chain), with the test's harness on the
path. Three E. coli models on the same rows:
  test_arm   today's seven inputs fitted on the 1,502 frozen rows: the rivers test's reference
  main_model data/processed/ecoli_model.json as on main (fitted 17 Oct on overflow table e6ef0459), fixed coefficients
  candidate  the river model (ecoli_model_sm.json's fit)
On the English rows: each model's in-sample Brier, the features' differences, and the test arm's LOYO.
On the rivers test's Welsh and Wessex rows: the rivers test's conditions with main_model as the reference, beside the
published ones. Nothing is retuned and no threshold changes.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import check_ecoli_wales as w  # noqa: E402
import rivers as R  # noqa: E402
import train_ecoli as te  # noqa: E402
from diagnostics import rows_q1  # noqa: E402
from leads import CAND, soil_at_issue  # noqa: E402

from dipcast import config  # noqa: E402
from dipcast.model import ecoli  # noqa: E402
from dipcast.model.ecoli import FEATURES, THRESHOLD, features, fit  # noqa: E402
from dipcast.model.spill_model import SpillModel  # noqa: E402


def main(soil_dir, main_json, rivers_out, out_path):
    soil, rivers_out = Path(soil_dir), Path(rivers_out)
    rows, fc = rows_q1()
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years, lake = rows["sample_time"].dt.year.to_numpy(), rows["lake"].to_numpy()
    X0 = features(fc[0][0], fc[0][1], rows["risk_lead0"], rows.lake, rows.sample_time)
    X0["sm"] = soil_at_issue(rows, soil, 0)
    arm, cand = fit(X0, y, FEATURES), fit(X0, y, CAND)
    main_m = ecoli.EcoliModel.from_json(Path(main_json))
    root_m = ecoli.EcoliModel.from_json()   # train_ecoli's own fit in this root
    b = lambda p, m=None: float(np.mean((p[m] - y[m]) ** 2)) if m is not None else float(np.mean((p - y) ** 2))
    res = {"note": "computed 26 Oct 2026, after the rivers-only test's results were seen; decides nothing by itself",
           "english_rows": len(rows), "english_in_sample": {}}
    for name, m, X in (("test_arm", arm, X0), ("root_ecoli_model_json", root_m, X0), ("main_model", main_m, X0),
                       ("candidate", cand, X0)):
        p = m.predict(X)
        res["english_in_sample"][name] = {"all": b(p), "rivers": b(p, lake == 0), "lakes": b(p, lake == 1)}
    res["test_arm_equals_root_json"] = max(abs(arm.coef[c] - root_m.coef[c]) for c in FEATURES)
    res["coef"] = {"test_arm": arm.coef, "main_model": main_m.coef, "intercepts": [arm.intercept, main_m.intercept]}
    res["main_vs_arm_feature_means"] = {c: [arm.mean[c], main_m.mean[c]] for c in FEATURES}
    res["main_vs_arm_feature_scales"] = {c: [arm.scale[c], main_m.scale[c]] for c in FEATURES}
    res["test_arm_loyo"] = b(te.leave_one_out(X0, y, years, lake, FEATURES))
    # ---- Welsh and Wessex rows, as the rivers test built them (its trace pickles, no network)
    lo, hi = float(X0["sm"].min()), float(X0["sm"].max())
    import wales as W  # noqa: E402
    wa = pd.read_parquet(Path(sys.argv[5]))
    models = {"gate_a": SpillModel.load(config.PROCESSED / "spill_model_holdout_2025.pkl"),
              "production": SpillModel.load(config.PROCESSED / "spill_model.pkl")}
    rain_model, clim, _ = w.england_baselines()
    frames = []
    for samples, trace, exposure, region, soil_fn in (
            (None, rivers_out / "trace.pkl", "gate_a", "Wales", W.soil_wales),
            (None, rivers_out / "trace_wessex.pkl", "production", "Wessex", R.soil_rivers)):
        if region == "Wales":
            s = w.screen(w.read_wqa(sorted(Path(sys.argv[6]).glob("*_Water_Quality_Archive.zip"))))[0]
            cl, cn = R.grid_cell(s["lat"].to_numpy(), s["lon"].to_numpy())
            s["cell_lat"], s["cell_lon"] = np.round(cl, 3), np.round(cn, 3)
        else:
            s, _ = R.wessex_samples(Path(sys.argv[7]))
        s, ups, _, _, _ = R.place(s, wa, trace)
        rain = R.load_rain_any(w.rain_needs(s, ups), Path(sys.argv[8]))
        df, _ = w.predictors(s, ups, wa, rain, models, rain_model, clim)
        df["exposure"] = df[f"exposure_{exposure}"]
        df = df.dropna(subset=["rain_48h", "rain_24h", "exposure"]).reset_index(drop=True)
        X = features(df["rain_48h"], df["rain_24h"], df["exposure"], np.zeros(len(df)), df["day"])
        sm = soil_fn(df, soil)
        df["test_arm"], df["main_model"] = arm.predict(X), main_m.predict(X)
        df["cand"] = np.where(np.isfinite(sm), cand.predict(X.assign(sm=np.clip(sm, lo, hi))), df["test_arm"])
        df["region"] = region
        frames.append(df)
    both = pd.concat(frames, ignore_index=True)
    head = both[both["river"]].reset_index(drop=True)
    out = {}
    for ref in ("test_arm", "main_model"):
        r = {}
        for g, d in (("pooled", head), ("Wales", head[head.region == "Wales"]), ("Wessex", head[head.region == "Wessex"])):
            r[g] = R.scores_pair(d.assign(reference=d[ref], candidate=d["cand"]))
        H = r
        c1 = H["pooled"]["gain"] > 0 and H["pooled"]["gain_ci"][0] > 0
        worse = {g: bool(H[g]["gain_ci"][1] < 0 or H[g]["brier_rel_change"] > R.MARGIN_REL) for g in ("Wales", "Wessex")}
        out[ref] = {"scores": r, "1_pooled_gain": bool(c1), "regions_clearly_worse": [g for g, v in worse.items() if v],
                    "passes": bool(c1 and not any(worse.values()))}
    res["rivers_test_with_reference"] = out
    Path(out_path).write_text(json.dumps(w.clean(res), indent=1))
    for ref in out:
        p = out[ref]["scores"]["pooled"]
        print(ref, "pooled gain", round(p["gain"], 5), p["gain_ci"], "Wales", round(out[ref]["scores"]["Wales"]["gain"], 5),
              "Wessex", round(out[ref]["scores"]["Wessex"]["gain"], 5), out[ref]["scores"]["Wessex"]["gain_ci"], "passes", out[ref]["passes"])
    print(json.dumps({k: res[k] for k in ("english_in_sample", "test_arm_loyo", "test_arm_equals_root_json")}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
