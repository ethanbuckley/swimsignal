"""Rows, water bodies, the Open-Meteo plan, features, and the one scoring run of
docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md. All offline.

    python -I wt_score.py rows     --ea <ea cache> --out <dir>
    python -I wt_score.py groups   --out <dir> [--network <river_network.pkl>]
    python -I wt_score.py plan     --out <dir>
    python -I wt_score.py features --om <open-meteo cache> --out <dir>
    python -I wt_score.py score    --out <dir> --sha <features sha256> --doc <statement .md>

`rows`, `groups` and `plan` print counts only: no temperature is summarised before the features file's hash is
committed. `score` refuses a features file whose SHA-256 is not the one given and written in the statement.
Python is run with -I, so the worktree's src is put on the path here, from this file's own location.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(WORKTREE / "src"))
import wt_protocol as wp  # noqa: E402


def _cell_keys(lat, lon) -> list[str]:
    from dipcast.ingest.rainfall import cell_key, grid_cell
    cl, cn = grid_cell(np.asarray(lat, float), np.asarray(lon, float))
    return [cell_key(float(a), float(b)) for a, b in zip(np.atleast_1d(cl), np.atleast_1d(cn), strict=True)]


# ================================================================== rows
def cmd_rows(ea: Path, out: Path) -> None:
    files = sorted(ea.glob("*.csv"))
    frames = []
    for f in files:
        d = pd.read_csv(f, dtype=str)
        if len(d):
            frames.append(d)
    raw = pd.concat(frames, ignore_index=True)
    for c in ("samplingPoint.easting", "samplingPoint.northing"):
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    rows, counts = wp.clean_rows(raw)
    no_xy = rows["easting"].isna() | rows["northing"].isna()
    counts["no_coordinates"] = int(no_xy.sum())
    rows = rows[~no_xy].copy()
    rows["season"] = wp.season_of(rows["date"])
    counts["files"] = len(files)
    counts["by_type"] = rows["type"].value_counts().to_dict()
    counts["by_type_season"] = {f"{t}/{s}": int(n) for (t, s), n in rows.groupby(["type", "season"]).size().items()}
    counts["points_by_type"] = rows.drop_duplicates("point")["type"].value_counts().to_dict()
    out.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(out / "rows.parquet")
    (out / "rows_counts.json").write_text(json.dumps(counts, indent=1, default=int))
    print(json.dumps(counts, indent=1, default=int))


# ================================================================== groups
def cmd_groups(out: Path, network_pkl: Path) -> None:
    import geopandas as gpd
    from pyproj import Transformer

    from dipcast.network.rivers import RiverNetwork

    t0 = time.time()
    rows = pd.read_parquet(out / "rows.parquet")
    pts = rows.drop_duplicates("point")[["point", "type", "easting", "northing"]].reset_index(drop=True)
    lon, lat = Transformer.from_crs(27700, 4326, always_xy=True).transform(pts["easting"].values,
                                                                          pts["northing"].values)
    pts["lat"], pts["lon"] = lat, lon
    pts["cell"] = _cell_keys(lat, lon)
    net = RiverNetwork.load(network_pkl)
    links = net.links
    print(f"network loaded in {time.time() - t0:.0f} s: {len(links)} links", flush=True)
    river_of = wp.named_rivers(links.reset_index(drop=True)[["id", "watercourse_name", "start_node", "end_node"]])
    geo = gpd.GeoSeries(gpd.points_from_xy(pts["easting"], pts["northing"]), crs=27700)

    pts["group"] = None
    pts["upstream_km"] = np.nan
    pts["lake_area_km2"] = np.nan
    pts["how"] = None

    # rivers
    rl = links[links["form"].isin(["inlandRiver", "tidalRiver"])]
    ri = np.flatnonzero(pts["type"].eq("river").to_numpy())
    if len(ri):
        q, t = rl.sindex.nearest(geo.iloc[ri].values, return_all=False, max_distance=wp.RIVER_SNAP_M)
        for qi, ti in zip(q, t, strict=True):
            i = ri[qi]
            row = rl.iloc[ti]
            lid = rl.index[ti]
            geom = row.geometry
            frac = float(geom.project(geo.iloc[i], normalized=True))
            pts.at[i, "upstream_km"] = (net.upstream_m.get(row["start_node"], 0.0) + frac * float(row["length"])) / 1000
            if lid in river_of:
                pts.at[i, "group"], pts.at[i, "how"] = river_of[lid], "named link"
            else:
                rid = wp.first_named_downstream(net.graph, row["end_node"], river_of)
                if rid:
                    pts.at[i, "group"], pts.at[i, "how"] = rid, "named downstream"
    # lakes
    lakes = gpd.read_parquet(WORKTREE / "data" / "processed" / "lakes.parquet").to_crs(27700)
    li = np.flatnonzero(pts["type"].eq("lake").to_numpy())
    if len(li):
        lg = gpd.GeoDataFrame({"i": li}, geometry=geo.iloc[li].values, crs=27700)
        j = gpd.sjoin_nearest(lg, lakes[["wb_id", "area_km2", "geometry"]], max_distance=wp.LAKE_POLY_M,
                              distance_col="d").sort_values(["i", "d", "wb_id"]).drop_duplicates("i")
        for r in j.itertuples():
            pts.at[r.i, "group"], pts.at[r.i, "how"] = f"lake:{r.wb_id}", "WFD polygon"
            pts.at[r.i, "lake_area_km2"] = float(r.area_km2)
        rest = [i for i in li if pts.at[i, "group"] is None]
        ll = links[links["form"].eq("lake")]
        if rest:
            q, t = ll.sindex.nearest(geo.iloc[rest].values, return_all=False, max_distance=wp.LAKE_LINK_M)
            for qi, ti in zip(q, t, strict=True):
                i = rest[qi]
                comp = net.lake_component(ll.index[ti])
                pts.at[i, "group"], pts.at[i, "how"] = f"oslake:{min(comp)}", "OS lake link"
    # sea
    si = pts["type"].eq("sea")
    pts.loc[si, "group"] = [wp.sea_group(e, n) for e, n in zip(pts.loc[si, "easting"], pts.loc[si, "northing"],
                                                                    strict=True)]
    pts.loc[si, "how"] = "10 km square"
    # the rest
    none = pts["group"].isna()
    pts.loc[none, "group"] = "pt:" + pts.loc[none, "point"]
    pts.loc[none, "how"] = "own water"
    pts["fold"] = pts["group"].map(wp.fold_of)
    pts.to_parquet(out / "points.parquet")
    summ = {
        "points_by_type_and_rule": {f"{t}/{h}": int(n) for (t, h), n in pts.groupby(["type", "how"]).size().items()},
        "waters_by_type": pts.groupby("type")["group"].nunique().to_dict(),
        "waters_by_fold": pts.groupby("fold")["group"].nunique().to_dict(),
        "cells": int(pts["cell"].nunique()),
        "seconds": round(time.time() - t0),
    }
    (out / "groups_counts.json").write_text(json.dumps(summ, indent=1, default=int))
    print(json.dumps(summ, indent=1, default=int))


# ================================================================== plan
def cmd_plan(out: Path) -> None:
    rows = pd.read_parquet(out / "rows.parquet")
    pts = pd.read_parquet(out / "points.parquet")
    r = rows[rows["season"].notna()].merge(pts[["point", "cell"]], on="point")
    r["year"] = pd.to_datetime(r["date"]).dt.year
    by = {int(y): sorted(g["cell"].unique()) for y, g in r.groupby("year")}
    types_by_cell = r.groupby("cell")["type"].agg(set)
    sea_only = {c for c, ts in types_by_cell.items() if ts == {"sea"}}
    plan = wp.plan_open_meteo(by, sea_cells=sea_only)
    plan["cells_by_season_before"] = {y: len(c) for y, c in by.items()}
    plan["cells_by_season"] = {y: len(c) for y, c in plan["seasons"].items()}
    plan["sea_only_cells"] = len(sea_only)
    plan["requests"] = sum(-(-len(c) // wp.OM_BATCH) for c in plan["seasons"].values())
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    print(json.dumps({k: v for k, v in plan.items() if k != "seasons"}, indent=1))


# ================================================================== features
def load_air(om: Path) -> tuple[dict, dict]:
    """{(cell, year): daily Series}, {cell: elevation}."""
    air, elev = {}, {}
    for f in sorted(om.glob("*.json")):
        d = json.loads(f.read_text())
        for cell, a in zip(d["cells"], d["answer"], strict=True):
            s = pd.Series(a["daily"]["temperature_2m_mean"], index=pd.to_datetime(a["daily"]["time"]), dtype=float)
            air[(cell, int(d["year"]))] = s
            elev.setdefault(cell, float(a.get("elevation", np.nan)))
    return air, elev


def cmd_features(out: Path, om: Path) -> None:
    rows = pd.read_parquet(out / "rows.parquet")
    pts = pd.read_parquet(out / "points.parquet")
    air, elev = load_air(om)
    r = rows[rows["season"].notna()].drop(columns=["type"]).merge(
        pts[["point", "type", "group", "fold", "cell", "upstream_km", "lake_area_km2"]], on="point")
    r["year"] = pd.to_datetime(r["date"]).dt.year
    parts = []
    for (cell, year), g in r.groupby(["cell", "year"]):
        s = air.get((cell, int(year)))
        if s is None:
            f = pd.DataFrame(np.nan, index=g.index, columns=["a1", "a7", "a30"])
        else:
            f = wp.air_features(s, g["date"]).set_index(g.index)
        parts.append(f)
    r = r.join(pd.concat(parts))
    r["elevation"] = r["cell"].map(elev)
    before = r.groupby("type").size()
    miss = r[["a1", "a7", "a30"]].isna().any(axis=1)
    dropped = r[miss].groupby("type").size().reindex(before.index, fill_value=0)
    r = r[~miss].copy()
    r = wp.add_doy(r)
    r["type_code"] = r["type"].map(wp.TYPE_CODE)
    r["log_lake_area"] = np.where(r["type"].eq("lake"), np.log10(r["lake_area_km2"]), np.nan)
    r["log_upstream_km"] = np.where(r["type"].eq("river") & (r["upstream_km"] > 0), np.log10(r["upstream_km"]), np.nan)
    r["small_upland"] = [wp.small_upland(t, u, e) for t, u, e in zip(r["type"], r["upstream_km"], r["elevation"],
                                                                     strict=True)]
    r["band"] = [wp.catchment_band(t, u) or wp.lake_band(t, a) or "sea"
                 for t, u, a in zip(r["type"], r["upstream_km"], r["lake_area_km2"], strict=True)]
    cols = ["point", "group", "fold", "type", "date", "season", "year", "temp", "n_readings", "cell", "upstream_km",
            "lake_area_km2", "small_upland", "band", "doy", *wp.FEATURES]
    r = r[cols].sort_values(["point", "date"]).reset_index(drop=True)
    path = out / "features.parquet"
    r.to_parquet(path, index=False)
    sha = wp.sha256_file(path)
    info = {"sha256": sha, "rows": int(len(r)), "rows_by_type_season": {f"{t}/{s}": int(n) for (t, s), n in
                                                                         r.groupby(["type", "season"]).size().items()},
            "dropped_no_air_by_type": dropped.to_dict(), "cells_with_air": len(elev),
            "waters_by_type": r.groupby("type")["group"].nunique().to_dict()}
    (out / "features_info.json").write_text(json.dumps(info, indent=1, default=int))
    print(json.dumps(info, indent=1, default=int))


# ================================================================== score
def cmd_score(out: Path, sha: str, doc: Path) -> None:
    path = out / "features.parquet"
    got = wp.sha256_file(path)
    if got != sha:
        raise SystemExit(f"features SHA-256 {got} is not the one given ({sha})")
    if sha not in doc.read_text():
        raise SystemExit("the statement does not name this SHA-256; commit it before scoring")
    t0 = time.time()
    f = pd.read_parquet(path)
    preds = []
    fits = {}
    for k in range(wp.N_FOLDS):
        tr = f[(f["season"] == "train") & (f["fold"] != k)].reset_index(drop=True)
        te = f[(f["season"] == "test") & (f["fold"] == k)].reset_index(drop=True)
        assert not set(tr["group"]) & set(te["group"]), "a water in both training and test"
        cand = wp.fit_candidate(tr)
        s1, full = wp.predict_candidate(cand, te)
        te = te.assign(pred_stage1=s1, pred_cand=full, pred_doy=np.nan, pred_air7=np.nan)
        fits[k] = {"curves": cand["curves"], "fit_ok": cand["fit_ok"], "train_rows": len(tr), "test_rows": len(te),
                   "air7": {}}
        for t, g in tr.groupby("type"):
            doy = wp.fit_doy_baseline(g["doy"], g["temp"])
            a, b = wp.fit_air7(g["a7"], g["temp"])
            fits[k]["air7"][t] = (a, b)
            m = te["type"].eq(t)
            te.loc[m, "pred_doy"] = wp.predict_doy(doy, te.loc[m, "doy"])
            te.loc[m, "pred_air7"] = a + b * te.loc[m, "a7"]
        preds.append(te)
        print(f"fold {k}: {len(tr)} training rows, {len(te)} test rows, {time.time() - t0:.0f} s", flush=True)
    p = pd.concat(preds, ignore_index=True)
    p.to_parquet(out / "predictions.parquet", index=False)
    models = {"cand": "pred_cand", "stage1": "pred_stage1", "doy": "pred_doy", "air7": "pred_air7"}

    def block(d: pd.DataFrame) -> dict:
        return {m: wp.summary(d[c] - d["temp"]) for m, c in models.items()} | {
            "waters": int(d["group"].nunique())}

    res = {"features_sha256": sha, "rows_test": int(len(p)), "by_type": {}, "verdict": {}, "groups": {},
           "by_year": {}, "by_month": {}, "by_fold": {}, "fits": fits}
    for t in wp.TYPES:
        d = p[p["type"] == t]
        if not len(d):
            continue
        res["by_type"][t] = block(d)
        gains = wp.boot_gains(d["group"], d["pred_cand"] - d["temp"],
                              {"doy": d["pred_doy"] - d["temp"], "air7": d["pred_air7"] - d["temp"]})
        res["by_type"][t]["gains"] = gains
        if t in wp.RMSE_MAX:
            res["verdict"][t] = wp.verdict(t, d["group"].nunique(), len(d), wp.rmse(d["pred_cand"] - d["temp"]), gains)
        res["by_year"][t] = {int(y): block(g) for y, g in d.groupby("year")}
        res["by_month"][t] = {int(m): block(g) for m, g in d.groupby(pd.to_datetime(d["date"]).dt.month)}
        res["by_fold"][t] = {int(k): block(g) for k, g in d.groupby("fold")}
    for b, g in p.groupby("band"):
        res["groups"][f"band: {b}"] = block(g)
    su = p[p["small_upland"]]
    res["groups"]["small upland streams"] = block(su) if len(su) else {"waters": 0}
    if len(su):
        res["groups"]["small upland streams"]["gains"] = wp.boot_gains(
            su["group"], su["pred_cand"] - su["temp"], {"doy": su["pred_doy"] - su["temp"],
                                                        "air7": su["pred_air7"] - su["temp"]})
    res["seconds"] = round(time.time() - t0)
    (out / "score.json").write_text(json.dumps(res, indent=1, default=lambda o: o if not isinstance(o, np.generic)
                                               else o.item()))
    print(json.dumps({"verdict": res["verdict"], "by_type": {t: {m: v.get("rmse") if isinstance(v, dict) else v
                                                                 for m, v in b.items() if m != "gains"}
                                                             for t, b in res["by_type"].items()}}, indent=1))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["rows", "groups", "plan", "features", "score"])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--ea", type=Path)
    ap.add_argument("--om", type=Path)
    ap.add_argument("--network", type=Path,
                    default=Path.home() / "Documents/GitHub/dipcast/data/processed/river_network.pkl")
    ap.add_argument("--sha")
    ap.add_argument("--doc", type=Path, default=WORKTREE / "docs" / "WATER-TEMPERATURE-MODEL-TEST-2026-10.md")
    a = ap.parse_args(argv)
    if a.what == "rows":
        cmd_rows(a.ea, a.out)
    elif a.what == "groups":
        cmd_groups(a.out, a.network)
    elif a.what == "plan":
        cmd_plan(a.out)
    elif a.what == "features":
        cmd_features(a.out, a.om)
    else:
        cmd_score(a.out, a.sha, a.doc)


if __name__ == "__main__":
    main()
