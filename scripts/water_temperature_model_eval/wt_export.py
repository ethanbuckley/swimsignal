"""The river water-temperature model for the site, fitted as tested and written as plain JSON
(docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md; rivers passed, lakes failed).

    python -I wt_export.py --out <private>/water-temperature/work --model data/processed/water_temp_model.json

The tested recipe exactly (wt_protocol.fit_candidate: the Mohseni curves per type, then the boosted correction with the
fixed settings), fitted once on every training row (May–September 2000–2022, HadUK air, all five folds' waters), from
the features file whose SHA-256 the statement names. No setting is changed and nothing is refitted on test rows. The
boosted trees are written out node by node, so the site predicts with numpy alone (dipcast.model.water_temp) and no
scikit-learn pickle crosses versions. The export is checked against scikit-learn's own predictions before it is
written.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parents[1] / "src"))
import wt_protocol as wp  # noqa: E402

FEATURES_SHA = "4e9ca630a8658aaea7eb69890571def6ab55f5e5e7d95c985d261ff7a77f936d"
BRIDGE = (0.5012729716522162, 0.9791684691913549)      # the statement's results: HadUK = c + d x Open-Meteo
RIVER_RMSE = 1.5610789039828783                         # held-out rivers, primary input
SHOWN_WITHIN_C = 2.0                                    # RMSE rounded up to the next 0.5 C


def export_trees(gbm) -> dict:
    known, f_idx_map = gbm._bin_mapper.make_known_categories_bitsets()
    trees = []
    for (pred,) in gbm._predictors:
        n = pred.nodes
        trees.append({
            "feature": n["feature_idx"].astype(int).tolist(),
            "threshold": [float(x) for x in n["num_threshold"]],
            "left": n["left"].astype(int).tolist(), "right": n["right"].astype(int).tolist(),
            "missing_left": n["missing_go_to_left"].astype(int).tolist(),
            "leaf": n["is_leaf"].astype(int).tolist(), "value": [float(x) for x in n["value"]],
            "categorical": n["is_categorical"].astype(int).tolist(),
            "bitset": n["bitset_idx"].astype(int).tolist(),
            "left_cat_bitsets": pred.raw_left_cat_bitsets.astype(np.int64).tolist(),
        })
    # With categorical inputs, scikit-learn reorders the columns before the trees see them (categorical first, each
    # ordinal-encoded by its sorted categories; an unknown category becomes missing): the trees' feature indices are
    # into that order. Read it from the fitted preprocessor rather than assume it.
    order, categories = list(range(gbm.n_features_in_)), {}
    pp = getattr(gbm, "_preprocessor", None)
    if pp is not None:
        order = []
        for name, tr, mask in pp.transformers_:
            if name == "remainder":
                continue
            cols = [int(i) for i in np.flatnonzero(np.asarray(mask))]
            order += cols
            if name == "encoder":
                categories = {str(c): [float(x) for x in cats] for c, cats in zip(cols, tr.categories_, strict=True)}
    return {"baseline": float(np.ravel(gbm._baseline_prediction)[0]), "trees": trees,
            "known_cat_bitsets": known.astype(np.int64).tolist(), "f_idx_map": f_idx_map.astype(int).tolist(),
            "column_order": order, "categories": categories}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--model", required=True, type=Path)
    a = ap.parse_args(argv)
    path = a.out / "features.parquet"
    if wp.sha256_file(path) != FEATURES_SHA:
        raise SystemExit("features file is not the one the statement names")
    f = pd.read_parquet(path)
    tr = f[f["season"] == "train"].reset_index(drop=True)
    cand = wp.fit_candidate(tr)
    if cand["features"] != wp.FEATURES:
        raise SystemExit(f"an input was left out of the fit: {cand['features']}")
    model = {
        "what": "River water temperature, May-September: docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md",
        "features": wp.FEATURES, "type_code": wp.TYPE_CODE, "months": list(wp.MONTHS),
        "curves": {t: list(p) for t, p in cand["curves"].items()}, "fit_ok": cand["fit_ok"],
        "bridge": {"c": BRIDGE[0], "d": BRIDGE[1]},
        "test": {"river_rmse_c": RIVER_RMSE, "shown_within_c": SHOWN_WITHIN_C, "types_passed": ["river"]},
        "trained_on": {"features_sha256": FEATURES_SHA, "rows": int(len(tr)),
                       "seasons": f"May-September {wp.TRAIN_YEARS[0]}-{wp.TRAIN_YEARS[-1]}", "air": "HadUK-Grid 5 km tas"},
        "gbm": export_trees(cand["gbm"]),
    }
    # check the export against scikit-learn on every test row and on rows with missing inputs
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    from dipcast.model.water_temp import WaterTempModel
    m = WaterTempModel(model)
    te = f[f["season"] == "test"].reset_index(drop=True)
    probe = pd.concat([te, te.sample(500, random_state=0).assign(log_upstream_km=np.nan, elevation=np.nan)],
                      ignore_index=True)
    want = cand["gbm"].predict(probe[wp.FEATURES].to_numpy(float))
    got = m.correction(probe[wp.FEATURES].to_numpy(float))
    diff = float(np.max(np.abs(want - got)))
    if diff > 1e-9:
        raise SystemExit(f"exported trees differ from scikit-learn by {diff}")
    s1, full = wp.predict_candidate(cand, probe)
    diff_full = float(np.nanmax(np.abs(m.predict_rows(probe) - full)))
    if diff_full > 1e-9:
        raise SystemExit(f"exported model differs from the fitted one by {diff_full}")
    model["check"] = {"rows": int(len(probe)), "max_abs_diff_trees": diff, "max_abs_diff_model": diff_full}
    a.model.write_text(json.dumps(model, separators=(",", ":")))
    print(json.dumps({k: v for k, v in model.items() if k != "gbm"}, indent=1),
          f"\n{len(model['gbm']['trees'])} trees, {a.model.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
