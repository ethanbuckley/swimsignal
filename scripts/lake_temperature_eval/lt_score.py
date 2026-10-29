"""Rows, water bodies, the Open-Meteo plan, features and the one scoring run of docs/LAKE-TEMPERATURE-TEST-2026-10.md.
All offline.

    python -I lt_score.py rows     --out <dir> --ea <ea cache> --ea <ea-2026 cache>
    python -I lt_score.py groups   --out <dir> [--network <river_network.pkl>]
    python -I lt_score.py plan     --out <dir>
    python -I lt_score.py features --out <dir> --first <first test work dir> --om <open-meteo> --om <open-meteo-2026>
    python -I lt_score.py score    --out <dir> --sha <features sha256>

`rows`, `groups`, `plan` and `features` print counts only: no water temperature is summarised before the features
file's SHA-256 is committed. `score` refuses a features file whose SHA-256 is not the one given and written in the
statement.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "water_temperature_model_eval"))
sys.path.insert(0, str(HERE))
sys.path.insert(2, str(WORKTREE / "src"))
import lt_protocol as lp  # noqa: E402
import wt_protocol as wp  # noqa: E402
import wt_score as ws  # noqa: E402

DOC = WORKTREE / "docs" / "LAKE-TEMPERATURE-TEST-2026-10.md"
FIRST_TEST_OM = re.compile(r"^(2018|2023|2024|2025|elev)_[0-9a-f]{16}\.json$")
OM_2026 = re.compile(r"^2026_[0-9a-f]{16}\.json$")


def _bucket(y: int) -> str:
    return "2000-22" if y <= 2022 else ("2023-25" if y <= 2025 else "2026")


# ================================================================== rows
def cmd_rows(eas: list[Path], out: Path, first: Path | None) -> None:
    frames = []
    for ea in eas:
        for f in sorted(ea.glob("*.csv")):
            if f.stat().st_size == 0:          # an HTTP 204 page: no rows
                continue
            d = pd.read_csv(f, dtype=str)
            if len(d):
                frames.append(d)
    raw = pd.concat(frames, ignore_index=True)
    for c in ("samplingPoint.easting", "samplingPoint.northing"):
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    labels = raw.groupby("samplingPoint.notation")["samplingPoint.prefLabel"].first()
    rows, counts = wp.clean_rows(raw)
    no_xy = rows["easting"].isna() | rows["northing"].isna()
    counts["no_coordinates"] = int(no_xy.sum())
    rows = rows[~no_xy].copy()
    rows["year"] = pd.to_datetime(rows["date"]).dt.year
    rows["label"] = rows["point"].map(labels)
    counts["files"] = len(frames)
    counts["by_type_years"] = {f"{t}/{b}": int(n) for (t, b), n in
                               rows.groupby(["type", rows["year"].map(_bucket)]).size().items()}
    counts["points_by_type"] = rows.drop_duplicates("point")["type"].value_counts().to_dict()
    lk = rows[rows["type"].eq("lake")]
    counts["lake_points_by_years"] = {b: int(g["point"].nunique()) for b, g in lk.groupby(lk["year"].map(_bucket))}
    if first is not None and (first / "points.parquet").exists():
        old = pd.read_parquet(first / "points.parquet").set_index("point")["type"]
        new = rows.drop_duplicates("point").set_index("point")["type"]
        both = old.index.intersection(new.index)
        ch = (old[both] != new[both])
        counts["points_changed_type_vs_first_test"] = {f"{a}->{b}": int(n) for (a, b), n in
                                                      pd.DataFrame({"a": old[both][ch], "b": new[both][ch]})
                                                      .groupby(["a", "b"]).size().items()}
        counts["points_new_since_first_test"] = int(len(new.index.difference(old.index)))
    out.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(out / "rows.parquet")
    (out / "rows_counts.json").write_text(json.dumps(counts, indent=1, default=int))
    print(json.dumps(counts, indent=1, default=int))


# ================================================================== plan
def cmd_plan(out: Path) -> None:
    rows = pd.read_parquet(out / "rows.parquet")
    pts = pd.read_parquet(out / "points.parquet")
    r = rows[rows["type"].eq("lake") & rows["year"].eq(2026)].merge(pts[["point", "cell"]], on="point")
    cells = sorted(r["cell"].unique())
    w = sum(wp.om_weight(len(cells[i:i + wp.OM_BATCH])) for i in range(0, len(cells), wp.OM_BATCH))
    plan = {"cells": cells, "n_cells": len(cells), "requests": -(-len(cells) // wp.OM_BATCH), "weight": round(w, 3),
            "lake_rows_2026": int(len(r)), "lake_points_2026": int(r["point"].nunique())}
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    print(json.dumps({k: v for k, v in plan.items() if k != "cells"}, indent=1))


# ================================================================== features
def load_om(dirs: list[Path]) -> tuple[dict, dict]:
    """{(cell, year): daily Series}, {cell: elevation}, from the first test's season and elevation answers and this
    test's 2026 answers. Other files in those folders (another session's checks) are not read."""
    air, elev = {}, {}
    for om in dirs:
        for f in sorted(om.glob("*.json")):
            if not (FIRST_TEST_OM.match(f.name) or OM_2026.match(f.name)):
                continue
            d = json.loads(f.read_text())
            for cell, a in zip(d["cells"], d["answer"], strict=True):
                elev.setdefault(cell, float(a.get("elevation", np.nan)))
                if d.get("elevation_only"):
                    continue
                s = pd.Series(a["daily"]["temperature_2m_mean"], index=pd.to_datetime(a["daily"]["time"]),
                              dtype=float)
                air[(cell, int(d["year"]))] = s
    return air, elev


def _windows(r: pd.DataFrame, keys: list[str], get) -> pd.DataFrame:
    parts = []
    for (key, year), g in r.groupby([*keys, "year"]):
        s = get(key, int(year))
        if s is None or not len(s):
            parts.append(pd.DataFrame(np.nan, index=g.index, columns=list(lp.AIR_COLS)))
        else:
            parts.append(lp.air_windows(s, int(year), g["date"]).set_index(g.index))
    return pd.concat(parts) if parts else pd.DataFrame(columns=list(lp.AIR_COLS))


def cmd_features(out: Path, first: Path, oms: list[Path]) -> None:
    import geopandas as gpd
    t0 = time.time()
    rows = pd.read_parquet(out / "rows.parquet")
    pts = pd.read_parquet(out / "points.parquet")
    r = rows[rows["type"].eq("lake")].merge(pts[["point", "group", "fold", "cell", "lake_area_km2", "how"]],
                                             on="point").reset_index(drop=True)
    hk, hk_of = ws.load_haduk(first)
    r["hk_cell"] = r["point"].map(hk_of).fillna(-1).astype(int)
    air, elev = load_om(oms)

    def hk_get(hc, y):
        return ws._season(hk[hc], y) if hc >= 0 and y <= 2025 else None

    def om_get(cell, y):
        s = air.get((cell, y))
        return None if s is None else pd.Series(lp.bridge(s.to_numpy()), index=s.index)

    def omraw_get(cell, y):
        return air.get((cell, y))

    f_hk = _windows(r[r["year"] <= 2025], ["hk_cell"], hk_get).add_suffix("_hk")
    om_rows = r[r["year"].isin(lp.OM_TEST_YEARS)]
    f_om = _windows(om_rows, ["cell"], om_get).add_suffix("_om")
    f_raw = _windows(om_rows, ["cell"], omraw_get).add_suffix("_omraw")
    r = r.join(f_hk).join(f_om).join(f_raw)

    lakes = gpd.read_parquet(WORKTREE / "data" / "processed" / "lakes.parquet")[["wb_id", "lake_name"]]
    res = pd.read_csv(WORKTREE / "data" / "raw" / "lake_residence.csv", usecols=["wb_id", "hl_depth_avg_m"])
    r["wb_id"] = r["group"].where(r["group"].str.startswith("lake:")).str.slice(5)
    r = r.merge(lakes, on="wb_id", how="left").merge(res, on="wb_id", how="left")
    r = r.rename(columns={"hl_depth_avg_m": "depth_m"})
    r["elevation"] = r["cell"].map(elev)
    r = wp.add_doy(r)
    r["log_lake_area"] = np.log10(r["lake_area_km2"])
    r["log_depth"] = np.log10(r["depth_m"].where(r["depth_m"] > 0))
    r["reservoir"] = [lp.is_reservoir(a, b) for a, b in zip(r["lake_name"], r["label"], strict=True)]
    r["size_band"] = [lp.size_band(a) for a in r["lake_area_km2"]]

    hk_ok = r[[f"{c}_hk" for c in lp.AIR_COLS]].notna().all(axis=1)
    om_ok = r[[f"{c}_om" for c in lp.AIR_COLS]].notna().all(axis=1)
    keep = hk_ok | om_ok
    by = r["year"].map(_bucket)
    info_drop = {
        "training rows (2000-25) without HadUK air": int((~hk_ok & (r["year"] <= 2025)).sum()),
        "2023-25 rows without Open-Meteo air": int((~om_ok & r["year"].between(2023, 2025)).sum()),
        "2026 rows without Open-Meteo air": int((~om_ok & r["year"].eq(2026)).sum()),
        "rows with neither, removed": int((~keep).sum()),
    }
    r = r[keep].copy()
    r["hk_ok"], r["om_ok"] = hk_ok[keep], om_ok[keep]
    cols = (["point", "group", "fold", "how", "wb_id", "lake_name", "label", "date", "year", "temp", "n_readings",
             "cell", "hk_cell", "lake_area_km2", "depth_m", "reservoir", "size_band", "doy", "doy_sin", "doy_cos",
             "log_lake_area", "log_depth", "elevation", "hk_ok", "om_ok"]
            + [f"{c}{s}" for s in ("_hk", "_om", "_omraw") for c in lp.AIR_COLS])
    r = r[cols].sort_values(["point", "date"]).reset_index(drop=True)
    path = out / "features.parquet"
    r.to_parquet(path, index=False)
    sha = wp.sha256_file(path)
    by = r["year"].map(_bucket)
    info = {
        "sha256": sha, "rows": int(len(r)), "seconds": round(time.time() - t0),
        "dropped": info_drop,
        "rows_by_years": {b: int(n) for b, n in by.value_counts().items()},
        "training_rows_with_haduk_by_years": {b: int(n) for b, n in by[r["hk_ok"]].value_counts().items()},
        "test_rows_with_open_meteo_by_years": {b: int(n) for b, n in by[r["om_ok"]].value_counts().items()},
        "waters_2026_with_air": int(r.loc[r["year"].eq(2026) & r["om_ok"], "group"].nunique()),
        "rows_2026_with_air": int((r["year"].eq(2026) & r["om_ok"]).sum()),
        "waters_by_how": r.groupby("how")["group"].nunique().to_dict(),
        "rows_with_area": int(r["lake_area_km2"].notna().sum()),
        "rows_with_depth": int(r["depth_m"].notna().sum()),
        "waters_with_depth": int(r.loc[r["depth_m"].notna(), "group"].nunique()),
        "rows_without_elevation": int(r["elevation"].isna().sum()),
        "infinite_values": int(np.isinf(r.select_dtypes("number").to_numpy(float)).sum()),
        "waters_in_more_than_one_fold": int((r.groupby("group")["fold"].nunique() > 1).sum()),
    }
    (out / "features_info.json").write_text(json.dumps(info, indent=1, default=int))
    print(json.dumps(info, indent=1, default=int))


# ================================================================== score
def _as(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
    d = df.copy()
    for c in lp.AIR_COLS:
        d[c] = d[f"{c}{suffix}"]
    return d


MODELS = {"cand": "pred_cand", "third": "pred_third", "air7": "pred_air7", "doy": "pred_doy"}


def _block(d: pd.DataFrame, with_gains: bool = False) -> dict:
    b = {m: wp.summary(d[c] - d["temp"]) for m, c in MODELS.items()}
    b["waters"] = int(d["group"].nunique())
    if with_gains and b["waters"] >= lp.GATE_WATERS:
        b["gains"] = _gains(d)
    return b


def _gains(d: pd.DataFrame) -> dict:
    return wp.boot_gains(d["group"], d["pred_cand"] - d["temp"],
                         {k: d[MODELS[k]] - d["temp"] for k in ("doy", "air7", "third")},
                         n_boot=lp.N_BOOT, seed=lp.SEED)


def _report(p: pd.DataFrame) -> dict:
    month = pd.to_datetime(p["date"]).dt.month
    rep = {"all": _block(p), "groups": {}, "by_month": {}, "by_fold": {}, "by_year": {}}
    rep["all"]["gains"] = _gains(p)          # always, so the verdict has them even below the gate
    rep["all"]["p90_cand"] = lp.p90(p["pred_cand"] - p["temp"])
    for bnd, g in p.groupby("size_band"):
        rep["groups"][f"size: {bnd}"] = _block(g, True)
    rep["groups"]["reservoirs"] = _block(p[p["reservoir"]], True)
    rep["groups"]["not reservoirs"] = _block(p[~p["reservoir"]], True)
    rep["groups"]["with a HydroLAKES depth"] = _block(p[p["depth_m"].notna()], True)
    rep["groups"]["without a depth"] = _block(p[p["depth_m"].isna()], True)
    rep["groups"]["May"] = _block(p[month.eq(5)], True)
    rep["groups"]["June to September"] = _block(p[month.ge(6)], True)
    rep["by_month"] = {int(m): _block(g) for m, g in p.groupby(month)}
    rep["by_fold"] = {int(k): _block(g) for k, g in p.groupby("fold")}
    rep["by_year"] = {int(y): _block(g) for y, g in p.groupby("year")}
    return rep


def cmd_score(out: Path, sha: str, doc: Path) -> None:
    path = out / "features.parquet"
    got = wp.sha256_file(path)
    if got != sha:
        raise SystemExit(f"features SHA-256 {got} is not the one given ({sha})")
    if sha not in doc.read_text():
        raise SystemExit("the statement does not name this SHA-256; commit it before scoring")
    t0 = time.time()
    f = pd.read_parquet(path)
    res = {"features_sha256": sha, "arms": {}}
    for arm, spec in lp.ARMS.items():
        preds, raw_preds, fits = [], [], {}
        for k in range(wp.N_FOLDS):
            tr = _as(f[f["year"].isin(spec["train"]) & f["fold"].ne(k) & f["hk_ok"]], "_hk")
            te0 = f[f["year"].isin(spec["test"]) & f["fold"].eq(k) & f["om_ok"]]
            assert not set(tr["group"]) & set(te0["group"]), "a water in both training and test"
            m = lp.fit_fold(tr)
            fits[k] = {x: m[x] for x in ("inner_scores", "third_window", "e_window", "third", "air7", "features",
                                         "train_rows", "train_waters")} | {"test_rows": int(len(te0))}
            preds.append(lp.predict_fold(m, _as(te0, "_om").reset_index(drop=True)))
            if arm == "primary":
                raw = te0[te0[[f"{c}_omraw" for c in lp.AIR_COLS]].notna().all(axis=1)]
                raw_preds.append(lp.predict_fold(m, _as(raw, "_omraw").reset_index(drop=True)))
            print(f"{arm} fold {k}: {len(tr)} training rows, {len(te0)} test rows, third {m['third_window']}, "
                  f"e {m['e_window']}, {time.time() - t0:.0f} s", flush=True)
        p = pd.concat(preds, ignore_index=True)
        p.to_parquet(out / f"predictions_{arm}.parquet", index=False)
        rep = _report(p)
        a = rep["all"]
        v = lp.verdict(a["waters"], a["cand"]["n"], a["cand"]["rmse"], a["p90_cand"], a["gains"])
        res["arms"][arm] = {"decides": spec["decides"], "train_years": [min(spec["train"]), max(spec["train"])],
                            "test_years": list(spec["test"]), "fits": fits, "verdict": v} | rep
        if raw_preds:
            pr = pd.concat(raw_preds, ignore_index=True)
            res["arms"][arm]["open_meteo_unbridged"] = _block(pr, True) | {
                "p90_cand": lp.p90(pr["pred_cand"] - pr["temp"])}
    res["verdict"] = res["arms"]["primary"]["verdict"]
    res["seconds"] = round(time.time() - t0)
    (out / "score.json").write_text(json.dumps(res, indent=1, default=lambda o: o.item() if isinstance(o, np.generic)
                                               else str(o)))
    print(json.dumps({"verdict": res["verdict"],
                      "rmse": {arm: {m: v["all"][m]["rmse"] for m in MODELS} for arm, v in res["arms"].items()},
                      "p90": {arm: v["all"]["p90_cand"] for arm, v in res["arms"].items()},
                      "gains": {arm: v["all"].get("gains") for arm, v in res["arms"].items()}}, indent=1))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["rows", "groups", "plan", "features", "score"])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--ea", type=Path, action="append")
    ap.add_argument("--om", type=Path, action="append")
    ap.add_argument("--first", type=Path)
    ap.add_argument("--network", type=Path,
                    default=Path.home() / "Documents/GitHub/dipcast/data/processed/river_network.pkl")
    ap.add_argument("--sha")
    ap.add_argument("--doc", type=Path, default=DOC)
    a = ap.parse_args(argv)
    if a.what == "rows":
        cmd_rows(a.ea, a.out, a.first)
    elif a.what == "groups":
        ws.cmd_groups(a.out, a.network)
    elif a.what == "plan":
        cmd_plan(a.out)
    elif a.what == "features":
        cmd_features(a.out, a.first, a.om)
    else:
        cmd_score(a.out, a.sha, a.doc)


if __name__ == "__main__":
    main()
