"""The three stages of docs/LAKE-TEMP-LOCAL-MODEL-2026-11.md. All offline; every shared input is read only and its
SHA-256 is printed at the start and end of each stage.

    python llm_run.py prepare --out <scratch> --lake-work <lake-test/work> --first-work <work> --lakes <lakes.parquet>
    python llm_run.py freeze  --out <scratch> --first-work <work> --model <water_temp_model.json>
    python llm_run.py score   --out <scratch> --truth-sha <sha> --frozen-sha <sha> --pred-sha <sha>

`prepare` prints counts only. `freeze` never opens the test truth file. `score` refuses unless the three SHA-256 given
match the files and are written in the statement.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lake_temperature_eval"))
sys.path.insert(0, str(HERE.parent / "water_temperature_model_eval"))
sys.path.insert(3, str(WORKTREE / "src"))
import llm_protocol as P  # noqa: E402
import lt_protocol as lp  # noqa: E402
import wt_protocol as wp  # noqa: E402

DOC = WORKTREE / "docs" / "LAKE-TEMP-LOCAL-MODEL-2026-11.md"
LAKE_FEATURES_SHA = "fe42bd203ed50251909bab23220547843224177eccd6f03171cfd1befb436dc3"
FIRST_FEATURES_SHA = "4e9ca630a8658aaea7eb69890571def6ab55f5e5e7d95c985d261ff7a77f936d"
AIR = ("a1", "a7", "a14", "a30", "a_apr", *(f"e{t}" for t in P.TAUS))


def fingerprint(paths: list[Path], when: str) -> dict:
    out = {str(p): wp.sha256_file(p) for p in paths if p.exists()}
    print(f"inputs {when}: " + json.dumps(out, indent=1), flush=True)
    return out


def with_air(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
    d = df.copy()
    for c in AIR:
        d[c] = d[f"{c}{suffix}"]
    return d


# ================================================================== prepare
def cmd_prepare(out: Path, lake_work: Path, lakes_path: Path) -> None:
    import geopandas as gpd
    shared = [lake_work / "features.parquet", lake_work / "points.parquet", lakes_path]
    before = fingerprint(shared, "before")
    if before[str(shared[0])] != LAKE_FEATURES_SHA:
        raise SystemExit("lake features file is not the one the statement names")
    f = pd.read_parquet(shared[0])
    keep = (f["hk_ok"] & f["year"].le(2025)) | (f["om_ok"] & f["year"].eq(2026))
    counts = {"rows in file": int(len(f)), "dropped: no air for its span": int((~keep).sum())}
    f = f[keep].reset_index(drop=True)
    f["row_id"] = np.arange(len(f))

    # connected WFD basins
    lakes = gpd.read_parquet(lakes_path)
    lakes["group"] = "lake:" + lakes["wb_id"]
    wfd_groups = set(f.loc[f["how"].eq("WFD polygon"), "group"])
    lk = lakes[lakes["group"].isin(wfd_groups)].reset_index(drop=True)
    pairs = []
    sj = gpd.sjoin(lk[["group", "geometry"]], lk[["group", "geometry"]].assign(geometry=lk.buffer(P.WFD_JOIN_M)),
                   predicate="intersects")
    for a, b in zip(sj["group_left"], sj["group_right"], strict=True):
        if a < b:
            pairs.append((a, b))
    pairs = sorted(set(pairs))

    # OS-link and own waters near a WFD lake with rows
    pts = pd.read_parquet(shared[1])[["point", "easting", "northing"]].drop_duplicates("point")
    other = f.loc[~f["how"].eq("WFD polygon"), ["point", "group"]].drop_duplicates().merge(pts, on="point", how="left")
    other = other.dropna(subset=["easting", "northing"])
    g_other = gpd.GeoDataFrame(other, geometry=gpd.points_from_xy(other["easting"], other["northing"]), crs=lk.crs)
    near = gpd.sjoin_nearest(g_other, lk[["group", "geometry"]], max_distance=P.OTHER_JOIN_M, distance_col="dist_m")
    near = near.sort_values("dist_m").drop_duplicates("group_left")
    near_wfd = dict(zip(near["group_left"], near["group_right"], strict=True))

    f["water"] = P.merge_groups(f["group"], f["how"], pairs, near_wfd)
    f["fold"] = f["water"].map(P.fold_of)
    f["cls"] = P.lake_class(f["depth_m"])
    merged = f.groupby("water")["group"].unique()
    merges = {w: sorted(map(str, g)) for w, g in merged.items() if len(g) > 1}
    counts |= {"WFD pairs within 50 m": [list(p) for p in pairs], "other groups joined to a WFD lake": len(near_wfd),
               "merged waters (more than one #419 group)": merges,
               "waters in more than one fold": int((f.groupby("water")["fold"].nunique() > 1).sum())}

    test = f["year"].isin(P.TEST_YEARS)
    dev = f["year"].isin(P.DEV_YEARS)
    seen26 = f["year"].eq(2026)
    cols = [c for c in f.columns if c != "temp"]
    f[dev].to_parquet(out / "dev.parquet", index=False)
    f.loc[test, cols].to_parquet(out / "test_inputs.parquet", index=False)
    f.loc[test, ["row_id", "point", "date", "temp"]].to_parquet(out / "test_truth.parquet", index=False)
    f.loc[seen26, cols].to_parquet(out / "seen2026_inputs.parquet", index=False)
    f.loc[seen26, ["row_id", "temp"]].to_parquet(out / "seen2026_truth.parquet", index=False)
    for name, sel in (("test 2000-11", test), ("development 2012-25", dev), ("seen 2026", seen26)):
        d = f[sel]
        counts[name] = {"rows": int(len(d)), "waters": int(d["water"].nunique()),
                        "by class": {c: {"rows": int((d["cls"] == c).sum()),
                                         "waters": int(d.loc[d["cls"] == c, "water"].nunique())} for c in P.CLASSES},
                        "WFD 1 km2 and over": {"rows": int(d["lake_area_km2"].ge(P.LARGE_KM2).sum()),
                                               "waters": int(d.loc[d["lake_area_km2"].ge(P.LARGE_KM2), "water"].nunique())},
                        "by fold": {int(k): int(n) for k, n in d.groupby("fold").size().items()}}
    counts["sha256"] = {n: wp.sha256_file(out / n) for n in ("dev.parquet", "test_inputs.parquet",
                                                             "test_truth.parquet", "seen2026_inputs.parquet",
                                                             "seen2026_truth.parquet")}
    (out / "prepare.json").write_text(json.dumps(counts, indent=1))
    print(json.dumps(counts, indent=1))
    if fingerprint(shared, "after") != before:
        raise SystemExit("a shared input changed during the stage")


# ================================================================== freeze
def live_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """The live model's inputs for lake rows; a1/a7/a30 are already on the HadUK scale."""
    area = df["lake_area_km2"].to_numpy(float)
    return pd.DataFrame({"a1": df["a1"].to_numpy(float), "a7": df["a7"].to_numpy(float),
                         "a30": df["a30"].to_numpy(float), "doy_sin": df["doy_sin"].to_numpy(float),
                         "doy_cos": df["doy_cos"].to_numpy(float), "type_code": 1.0,
                         "log_lake_area": np.where(np.isfinite(area) & (area > 0), np.log10(np.where(area > 0, area, 1)),
                                                   np.nan),
                         "log_upstream_km": np.nan, "elevation": df["elevation"].to_numpy(float), "type": "lake"})


def live_deployed(model, df: pd.DataFrame) -> np.ndarray:
    from dipcast.model import water_temp as wt
    x = live_inputs(df)
    large = df["lake_area_km2"].ge(wt.LARGE_LAKE_KM2).to_numpy()
    full = model.predict_rows(x)
    curve = wt.mohseni(x["a7"].to_numpy(float), *model.curves["lake"])
    return np.where(large, curve, full)


def live_refit_fit(first: pd.DataFrame, test_points: set, test_wfd: set) -> dict:
    tr = first[~first["point"].isin(test_points) & ~first["group"].isin(test_wfd)].reset_index(drop=True)
    m = wp.fit_candidate(tr)
    return m | {"train_rows": int(len(tr))}


def live_refit_predict(m: dict, df: pd.DataFrame) -> np.ndarray:
    x = live_inputs(df).reset_index(drop=True)
    _, full = wp.predict_candidate(m, x)
    curve = wp.mohseni(x["a7"].to_numpy(float), *m["curves"]["lake"])
    return np.where(df["lake_area_km2"].ge(P.LARGE_KM2).to_numpy(), curve, full)


def first_rows(first_work: Path) -> pd.DataFrame:
    f = pd.read_parquet(first_work / "features.parquet")
    f = f[f["year"].isin(P.DEV_YEARS) & f[["a1_hk", "a7_hk", "a30_hk"]].notna().all(axis=1)].copy()
    for c in ("a1", "a7", "a30"):
        f[c] = f[f"{c}_hk"]
    return f.reset_index(drop=True)


def predict_all(fold_models: dict, df: pd.DataFrame, live_model) -> pd.DataFrame:
    out = []
    for k, m in fold_models.items():
        d = df[df["fold"].eq(k)].reset_index(drop=True)
        if not len(d):
            continue
        p = lp.predict_fold(m["m419"], d)
        out.append(pd.DataFrame({
            "row_id": d["row_id"], "fold": k, "water": d["water"], "year": d["year"], "date": d["date"],
            "cls": d["cls"], "lake_area_km2": d["lake_area_km2"], "depth_m": d["depth_m"], "lake_name": d["lake_name"],
            "label": d["label"], "size_band": d["size_band"], "reservoir": d["reservoir"],
            "pred_cand": P.predict_form(m["cand"], d), "pred_m419": p["pred_cand"], "pred_air7": p["pred_air7"],
            "pred_doy": p["pred_doy"], "pred_live": live_deployed(live_model, d),
            "pred_live_refit": live_refit_predict(m["live_refit"], d)}))
    return pd.concat(out, ignore_index=True)


def cmd_freeze(out: Path, first_work: Path, model_path: Path) -> None:
    from dipcast.model import water_temp as wt
    shared = [first_work / "features.parquet", model_path, WORKTREE / "src/dipcast/model/water_temp.py"]
    before = fingerprint(shared, "before")
    if before[str(shared[0])] != FIRST_FEATURES_SHA:
        raise SystemExit("first test's features file is not the one the statement names")
    t0 = time.time()
    dev = with_air(pd.read_parquet(out / "dev.parquet"), "_hk")
    test = with_air(pd.read_parquet(out / "test_inputs.parquet"), "_hk")
    seen = with_air(pd.read_parquet(out / "seen2026_inputs.parquet"), "_om")
    assert "temp" not in test.columns and "temp" not in seen.columns
    first = first_rows(first_work)
    live_model = wt.load(model_path, winter_path=None)
    m419_train = dev.assign(group=dev["water"])
    fold_models, frozen = {}, {"folds": {}}
    for k in range(P.N_FOLDS):
        tr = dev[dev["fold"].ne(k)]
        te = test[test["fold"].eq(k)]
        assert not set(tr["water"]) & set(te["water"]), "a water in both training and test"
        cand = P.fit_candidate(tr)
        m419 = lp.fit_fold(m419_train[m419_train["fold"].ne(k)])
        held = pd.concat([test, dev, seen])
        held = held[held["fold"].eq(k)]
        test_wfd = set(held.loc[held["how"].eq("WFD polygon"), "group"])
        live_refit = live_refit_fit(first, set(held["point"]), test_wfd)
        fold_models[k] = {"cand": cand, "m419": m419, "live_refit": live_refit}
        frozen["folds"][k] = {
            "candidate": {x: cand[x] for x in ("form", "taus", "pooled", "classes", "form_scores", "train_rows",
                                               "train_waters")},
            "m419": {x: m419[x] for x in ("third_window", "e_window", "third", "air7", "features", "train_rows",
                                          "train_waters")},
            "live_refit": {"curves": {t: list(map(float, c)) for t, c in live_refit["curves"].items()},
                           "train_rows": live_refit["train_rows"]},
            "test_rows": int(len(te))}
        print(f"fold {k}: {len(tr)} dev rows, {len(te)} test rows, form {cand['form']} taus {cand['taus']}, "
              f"live refit {live_refit['train_rows']} rows, {time.time() - t0:.0f} s", flush=True)
    with open(out / "models.pkl", "wb") as fh:
        pickle.dump({k: {"m419": v["m419"], "live_refit": v["live_refit"]} for k, v in fold_models.items()}, fh)
    frozen["models_pkl_sha256"] = wp.sha256_file(out / "models.pkl")
    (out / "frozen.json").write_text(json.dumps(frozen, indent=1, default=lambda o: o.item() if isinstance(
        o, np.generic) else str(o)))
    pt = predict_all(fold_models, test, live_model)
    pt.to_parquet(out / "predictions_test.parquet", index=False)
    predict_all(fold_models, seen, live_model).to_parquet(out / "predictions_seen2026.parquet", index=False)

    # development: dev-year rows of each fold's held-out waters (lakes unseen, years seen)
    pdv = predict_all(fold_models, dev.drop(columns=["temp"]), live_model).merge(dev[["row_id", "temp"]], on="row_id")
    dcv = {"note": "development evidence: development years 2012-25, waters held out; live (deployed) is in-sample "
                   "for 2012-22",
           "all": {m: P.summary(pdv[f"pred_{m}"] - pdv["temp"]) for m in MODEL_NAMES},
           "by class": {c: {m: P.summary(g[f"pred_{m}"] - g["temp"]) for m in MODEL_NAMES} | {
               "waters": int(g["water"].nunique())} for c, g in pdv.groupby("cls")},
           "WFD 1 km2 and over": {m: P.summary(g[f"pred_{m}"] - g["temp"]) for m in MODEL_NAMES
                                  for g in [pdv[pdv["lake_area_km2"].ge(P.LARGE_KM2)]]}}
    (out / "dev_cv.json").write_text(json.dumps(dcv, indent=1))
    hashes = {n: wp.sha256_file(out / n) for n in ("frozen.json", "models.pkl", "predictions_test.parquet",
                                                     "predictions_seen2026.parquet")}
    print(json.dumps({"sha256": hashes, "dev_cv_rmse": {m: dcv["all"][m]["rmse"] for m in MODEL_NAMES},
                      "seconds": round(time.time() - t0)}, indent=1))
    if fingerprint(shared, "after") != before:
        raise SystemExit("a shared input changed during the stage")


# ================================================================== score
MODEL_NAMES = ("cand", "live", "live_refit", "air7", "m419", "doy")
BASES = ("live", "live_refit", "air7", "m419")


def block(d: pd.DataFrame, gains: bool = True) -> dict:
    b = {m: P.summary(d[f"pred_{m}"] - d["temp"]) for m in MODEL_NAMES}
    b["waters"] = int(d["water"].nunique())
    if gains and b["waters"] >= P.GROUP_MIN_WATERS:
        errs = {k: d[f"pred_{k}"] - d["temp"] for k in BASES}
        b["two_way"] = P.boot(d["water"], d["year"], d["pred_cand"] - d["temp"], errs)
        b["water_only"] = P.boot(d["water"], d["year"], d["pred_cand"] - d["temp"], errs, two_way=False)
        b["answer"] = P.group_answer(b["waters"], b["two_way"])
    return b


def report(p: pd.DataFrame) -> dict:
    month = pd.to_datetime(p["date"]).dt.month
    r = {"all": block(p)}
    r["all"]["p90_cand"] = float(np.percentile(np.abs(p["pred_cand"] - p["temp"]), 90))
    r["all"]["rounded"] = {m: P.summary(np.round(np.maximum(p[f"pred_{m}"], 0)) - p["temp"]) for m in ("cand", "live")}
    r["by class"] = {c: block(g) for c, g in p.groupby("cls")}
    r["groups"] = {"WFD 1 km2 and over": block(p[p["lake_area_km2"].ge(P.LARGE_KM2)]),
                   "reservoirs": block(p[p["reservoir"]]),
                   "May": block(p[month.eq(5)]), "June to September": block(p[month.ge(6)])}
    r["size bands"] = {b: block(g) for b, g in p.groupby("size_band")}
    r["by month"] = {int(m): block(g, False) for m, g in p.groupby(month)}
    r["by year"] = {int(y): block(g, False) for y, g in p.groupby("year")}
    r["by fold"] = {int(k): block(g, False) for k, g in p.groupby("fold")}
    deep = p[p["cls"].eq("deep")]
    r["deep lakes"] = {str(n): {"rows": int(len(g)), "depth_m": float(g["depth_m"].iloc[0]),
                                **{m: P.summary(g[f"pred_{m}"] - g["temp"]).get("rmse") for m in MODEL_NAMES},
                                "cand_bias": float((g["pred_cand"] - g["temp"]).mean()),
                                "live_bias": float((g["pred_live"] - g["temp"]).mean())}
                       for n, g in deep.groupby("lake_name")}
    return r


def cmd_score(out: Path, truth_sha: str, frozen_sha: str, pred_sha: str) -> None:
    doc = DOC.read_text()
    for name, sha in (("test_truth.parquet", truth_sha), ("frozen.json", frozen_sha),
                      ("predictions_test.parquet", pred_sha)):
        got = wp.sha256_file(out / name)
        if got != sha:
            raise SystemExit(f"{name} SHA-256 {got} is not the one given")
        if sha not in doc:
            raise SystemExit(f"the statement does not name {name}'s SHA-256; commit it before scoring")
    frozen = json.loads((out / "frozen.json").read_text())
    if wp.sha256_file(out / "models.pkl") != frozen["models_pkl_sha256"]:
        raise SystemExit("models.pkl is not the frozen one")
    p = pd.read_parquet(out / "predictions_test.parquet").merge(
        pd.read_parquet(out / "test_truth.parquet")[["row_id", "temp"]], on="row_id", validate="1:1")
    r = report(p)
    a = r["all"]
    v = P.verdict(a["waters"], a["cand"]["n"], a["cand"]["rmse"], a["p90_cand"], a["two_way"])
    s = pd.read_parquet(out / "predictions_seen2026.parquet").merge(
        pd.read_parquet(out / "seen2026_truth.parquet"), on="row_id", validate="1:1")
    res = {"test_years": [min(P.TEST_YEARS), max(P.TEST_YEARS)], "verdict": v,
           "frozen": {"forms": {k: f["candidate"]["form"] for k, f in frozen["folds"].items()},
                      "taus": {k: f["candidate"]["taus"] for k, f in frozen["folds"].items()},
                      "form_scores": {k: f["candidate"]["form_scores"] for k, f in frozen["folds"].items()},
                      "m419_windows": {k: f["m419"]["e_window"] for k, f in frozen["folds"].items()}},
           "test": r,
           "seen_2026": {"all": block(s), "by class": {c: block(g, False) for c, g in s.groupby("cls")},
                         "WFD 1 km2 and over": block(s[s["lake_area_km2"].ge(P.LARGE_KM2)], False)},
           "development_cv": json.loads((out / "dev_cv.json").read_text())}
    text = json.dumps(res, indent=1, default=lambda o: o.item() if isinstance(o, np.generic) else str(o))
    (out / "score.json").write_text(text)
    (WORKTREE / "docs" / "LAKE-TEMP-LOCAL-MODEL-2026-11-score.json").write_text(text + "\n")
    print(json.dumps({"verdict": v, "rmse": {m: a[m]["rmse"] for m in MODEL_NAMES},
                      "gains": a["two_way"], "p90": a["p90_cand"],
                      "classes": {c: {m: b[m]["rmse"] for m in MODEL_NAMES} | {"answer": b.get("answer")}
                                  for c, b in r["by class"].items()}}, indent=1))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("prepare", "freeze", "score"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lake-work", type=Path)
    ap.add_argument("--first-work", type=Path)
    ap.add_argument("--lakes", type=Path, default=WORKTREE / "data/processed/lakes.parquet")
    ap.add_argument("--model", type=Path, default=WORKTREE / "data/processed/water_temp_model.json")
    ap.add_argument("--truth-sha")
    ap.add_argument("--frozen-sha")
    ap.add_argument("--pred-sha")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    if a.stage == "prepare":
        cmd_prepare(a.out, a.lake_work, a.lakes)
    elif a.stage == "freeze":
        cmd_freeze(a.out, a.first_work, a.model)
    else:
        cmd_score(a.out, a.truth_sha, a.frozen_sha, a.pred_sha)


if __name__ == "__main__":
    main()
