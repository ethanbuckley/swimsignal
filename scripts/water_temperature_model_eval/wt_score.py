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
        if f.stat().st_size == 0:          # an HTTP 204 page: no rows
            continue
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
    """Amendment 2: the bridge season (2018) and the test seasons, for the cells with a row that year; one-day
    elevation requests for every other cell."""
    rows = pd.read_parquet(out / "rows.parquet")
    pts = pd.read_parquet(out / "points.parquet")
    r = rows[rows["season"].notna()].merge(pts[["point", "cell"]], on="point")
    r["year"] = pd.to_datetime(r["date"]).dt.year
    by = {int(y): sorted(g["cell"].unique()) for y, g in r.groupby("year")}
    plan = wp.plan_open_meteo_narrowed(by, r["cell"].unique())
    plan["cells_by_season"] = {y: len(c) for y, c in plan["seasons"].items()}
    plan["elevation_cells_n"] = len(plan["elevation_cells"])
    plan["requests"] = (sum(-(-len(c) // wp.OM_BATCH) for c in plan["seasons"].values())
                        + -(-len(plan["elevation_cells"]) // wp.OM_BATCH))
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    print(json.dumps({k: v for k, v in plan.items() if k not in ("seasons", "elevation_cells")}, indent=1))


# ================================================================== HadUK (run in an environment with h5py)
def _read_var(h, name):
    v = h[name]
    a = v[...].astype("float64")
    for k in ("_FillValue", "missing_value"):
        if k in v.attrs:
            fv = np.atleast_1d(v.attrs[k]).astype("float64")
            for x in fv:
                a[a == x] = np.nan
    if "scale_factor" in v.attrs:
        a = a * float(np.atleast_1d(v.attrs["scale_factor"])[0])
    if "add_offset" in v.attrs:
        a = a + float(np.atleast_1d(v.attrs["add_offset"])[0])
    a[np.abs(a) > 1e10] = np.nan
    return a


def cmd_haduk(out: Path, haduk: Path) -> None:
    """Checks the 156 HadUK files (each opens; `tas` has one step per day of its month; one grid), maps every point to
    its nearest valid 5 km cell within 10 km, and writes the used cells' daily series. No water temperature is read."""
    import calendar

    import h5py
    want = [f"tas_hadukgrid_uk_5km_day_{y}{m:02d}01-{y}{m:02d}{calendar.monthrange(y, m)[1]:02d}.nc"
            for y in range(2000, 2026) for m in range(4, 10)]
    missing = [f for f in want if not (haduk / f).is_file()]
    if missing:
        raise SystemExit(f"{len(missing)} of {len(want)} HadUK files missing, first {missing[0]}")
    pts = pd.read_parquet(out / "points.parquet")
    grid = None
    dates, blocks, idx = [], [], None
    for f in want:
        y, m = int(f[25:29]), int(f[29:31])
        n = calendar.monthrange(y, m)[1]
        with h5py.File(haduk / f, "r") as h:
            tas = _read_var(h, "tas")
            x = h["projection_x_coordinate"][...].astype(float)
            yy = h["projection_y_coordinate"][...].astype(float)
        if tas.shape[0] != n:
            raise SystemExit(f"{f}: {tas.shape[0]} days, not {n}")
        if grid is None:
            grid = (x, yy)
            valid = np.isfinite(tas[0])
            iy, ix = np.nonzero(valid)
            cx, cy = x[ix], yy[iy]
            k, dist = wp.nearest_valid_cell(cx, cy, pts["easting"], pts["northing"])
            pts["hk_cell"] = np.where(k >= 0, k, -1)
            pts["hk_dist_m"] = dist
            used = np.unique(k[k >= 0])
            idx = (iy[used], ix[used])
            cell_ids = used
        elif not (np.array_equal(x, grid[0]) and np.array_equal(yy, grid[1])):
            raise SystemExit(f"{f}: a different grid")
        blocks.append(tas[:, idx[0], idx[1]].astype("float32"))
        dates.extend(pd.date_range(f"{y}-{m:02d}-01", periods=n).strftime("%Y-%m-%d"))
    series = np.concatenate(blocks, axis=0).T          # used cells x days
    np.savez_compressed(out / "haduk_series.npz", cells=cell_ids, dates=np.array(dates), tas=series)
    pts[["point", "hk_cell", "hk_dist_m"]].to_parquet(out / "haduk_points.parquet")
    info = {"files": len(want), "days": len(dates), "valid_cells": int(len(cx)), "used_cells": int(len(cell_ids)),
            "points_without_cell": int((pts["hk_cell"] < 0).sum()),
            "points_moved_to_a_neighbour": int((pts["hk_dist_m"] > 2500 * np.sqrt(2)).sum()),
            "missing_values_in_used_cells": int(np.isnan(series).sum())}
    (out / "haduk_info.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


# ================================================================== features
def load_air(om: Path) -> tuple[dict, dict]:
    """{(cell, year): daily Series}, {cell: elevation}, from every cached Open-Meteo answer."""
    air, elev = {}, {}
    for f in sorted(om.glob("*.json")):
        d = json.loads(f.read_text())
        for cell, a in zip(d["cells"], d["answer"], strict=True):
            elev.setdefault(cell, float(a.get("elevation", np.nan)))
            if d.get("elevation_only"):
                continue
            s = pd.Series(a["daily"]["temperature_2m_mean"], index=pd.to_datetime(a["daily"]["time"]), dtype=float)
            air[(cell, int(d["year"]))] = s
    return air, elev


def load_haduk(out: Path) -> tuple[dict, pd.Series]:
    z = np.load(out / "haduk_series.npz")
    idx = pd.to_datetime(z["dates"])
    series = {int(c): pd.Series(z["tas"][i].astype(float), index=idx) for i, c in enumerate(z["cells"])}
    hp = pd.read_parquet(out / "haduk_points.parquet").set_index("point")["hk_cell"]
    return series, hp


def _season(s: pd.Series, year: int) -> pd.Series:
    return s[(s.index >= f"{year}-{wp.AIR_FROM}") & (s.index <= f"{year}-{wp.AIR_TO}")]


def _feats(groups, get_series) -> pd.DataFrame:
    parts = []
    for key, g in groups:
        s = get_series(key)
        if s is None or not len(s):
            parts.append(pd.DataFrame(np.nan, index=g.index, columns=["a1", "a7", "a30"]))
        else:
            parts.append(wp.air_features(s, g["date"]).set_index(g.index))
    return pd.concat(parts) if parts else pd.DataFrame(columns=["a1", "a7", "a30"])


def cmd_features(out: Path, om: Path) -> None:
    rows = pd.read_parquet(out / "rows.parquet")
    pts = pd.read_parquet(out / "points.parquet")
    air, elev = load_air(om)
    hk, hk_of = load_haduk(out)
    r = rows[rows["season"].notna()].drop(columns=["type"]).merge(
        pts[["point", "type", "group", "fold", "cell", "upstream_km", "lake_area_km2"]], on="point")
    r["year"] = pd.to_datetime(r["date"]).dt.year
    r["hk_cell"] = r["point"].map(hk_of).fillna(-1).astype(int)

    # the bridge: 2018 daily pairs, one per distinct (HadUK cell, Open-Meteo cell), no water temperature
    b = r[(r["year"] == wp.BRIDGE_YEAR) & (r["hk_cell"] >= 0)][["hk_cell", "cell"]].drop_duplicates()
    om_x, hk_y = [], []
    for hc, oc in b.itertuples(index=False):
        so = air.get((oc, wp.BRIDGE_YEAR))
        if so is None:
            continue
        sh = _season(hk[hc], wp.BRIDGE_YEAR)
        j = pd.concat([so.rename("om"), sh.rename("hk")], axis=1, join="inner")
        om_x.append(j["om"].to_numpy())
        hk_y.append(j["hk"].to_numpy())
    om_x, hk_y = np.concatenate(om_x), np.concatenate(hk_y)
    c, d = wp.fit_bridge(om_x, hk_y)
    ok = np.isfinite(om_x) & np.isfinite(hk_y)
    bridge = {"c": c, "d": d, "pairs": int(ok.sum()), "cell_pairs": int(len(b)),
              "rms_before": float(np.sqrt(np.mean((hk_y[ok] - om_x[ok]) ** 2))),
              "rms_after": float(np.sqrt(np.mean((hk_y[ok] - (c + d * om_x[ok])) ** 2)))}

    def hk_get(key):
        hc, y = key
        return _season(hk[hc], y) if hc >= 0 else None

    def om_get(key):
        oc, y = key
        return air.get((oc, int(y)))

    tr = r["season"].eq("train")
    te = ~tr
    f_hk = _feats(r[tr | te].groupby(["hk_cell", "year"]), hk_get).add_suffix("_hk")
    f_om = _feats(r[te].groupby(["cell", "year"]), om_get).add_suffix("_om")
    r = r.join(f_hk).join(f_om)
    # primary inputs: HadUK in training; bridged Open-Meteo in the test seasons
    for k in ("a1", "a7", "a30"):
        r[k] = np.where(tr, r[f"{k}_hk"], c + d * r[f"{k}_om"])
    r["elevation"] = r["cell"].map(elev)
    before = r.groupby(["type", "season"]).size()
    miss = r[["a1", "a7", "a30"]].isna().any(axis=1)
    dropped = r[miss].groupby(["type", "season"]).size().reindex(before.index, fill_value=0)
    r = r[~miss].copy()
    r = wp.add_doy(r)
    r["type_code"] = r["type"].map(wp.TYPE_CODE)
    r["log_lake_area"] = np.where(r["type"].eq("lake"), np.log10(r["lake_area_km2"]), np.nan)
    r["log_upstream_km"] = np.where(r["type"].eq("river") & (r["upstream_km"] > 0), np.log10(r["upstream_km"]), np.nan)
    r["small_upland"] = [wp.small_upland(t, u, e) for t, u, e in zip(r["type"], r["upstream_km"], r["elevation"],
                                                                     strict=True)]
    r["band"] = [wp.catchment_band(t, u) or wp.lake_band(t, a) or "sea"
                 for t, u, a in zip(r["type"], r["upstream_km"], r["lake_area_km2"], strict=True)]
    cols = ["point", "group", "fold", "type", "date", "season", "year", "temp", "n_readings", "cell", "hk_cell",
            "upstream_km", "lake_area_km2", "small_upland", "band", "doy", *wp.FEATURES,
            "a1_hk", "a7_hk", "a30_hk", "a1_om", "a7_om", "a30_om"]
    r = r[cols].sort_values(["point", "date"]).reset_index(drop=True)
    path = out / "features.parquet"
    r.to_parquet(path, index=False)
    sha = wp.sha256_file(path)
    info = {"sha256": sha, "rows": int(len(r)), "bridge": bridge,
            "rows_by_type_season": {f"{t}/{s}": int(n) for (t, s), n in r.groupby(["type", "season"]).size().items()},
            "dropped_no_air_by_type_season": {f"{t}/{s}": int(n) for (t, s), n in dropped.items()},
            "test_rows_with_haduk_air": int(r.loc[r.season.eq("test"), ["a1_hk", "a7_hk", "a30_hk"]].notna()
                                            .all(axis=1).sum()),
            "cells_with_elevation": int(sum(np.isfinite(v) for v in elev.values())),
            "rows_without_elevation": int(r["elevation"].isna().sum()),
            "waters_by_type": r.groupby("type")["group"].nunique().to_dict()}
    (out / "features_info.json").write_text(json.dumps(info, indent=1, default=int))
    print(json.dumps(info, indent=1, default=int))


# ================================================================== score
def _variant(te: pd.DataFrame, suffix: str) -> pd.DataFrame:
    """The test rows with their air inputs replaced: `_hk` (HadUK), `_om` (Open-Meteo, raw); rows lacking it dropped."""
    v = te.copy()
    for k in ("a1", "a7", "a30"):
        v[k] = v[f"{k}{suffix}"]
    return v[v[["a1", "a7", "a30"]].notna().all(axis=1)]


def cmd_score(out: Path, sha: str, doc: Path) -> None:
    path = out / "features.parquet"
    got = wp.sha256_file(path)
    if got != sha:
        raise SystemExit(f"features SHA-256 {got} is not the one given ({sha})")
    if sha not in doc.read_text():
        raise SystemExit("the statement does not name this SHA-256; commit it before scoring")
    t0 = time.time()
    f = pd.read_parquet(path)
    variants = {"primary": None, "haduk": "_hk", "om_raw": "_om"}
    preds = {v: [] for v in variants}
    fits = {}
    for k in range(wp.N_FOLDS):
        tr = f[(f["season"] == "train") & (f["fold"] != k)].reset_index(drop=True)
        te0 = f[(f["season"] == "test") & (f["fold"] == k)].reset_index(drop=True)
        assert not set(tr["group"]) & set(te0["group"]), "a water in both training and test"
        cand = wp.fit_candidate(tr)
        base = {}
        for t, g in tr.groupby("type"):
            base[t] = (wp.fit_doy_baseline(g["doy"], g["temp"]), wp.fit_air7(g["a7"], g["temp"]))
        fits[k] = {"curves": cand["curves"], "fit_ok": cand["fit_ok"], "features": cand["features"],
                   "train_rows": len(tr), "test_rows": len(te0), "air7": {t: v[1] for t, v in base.items()}}
        for name, suf in variants.items():
            te = te0 if suf is None else _variant(te0, suf).reset_index(drop=True)
            s1, full = wp.predict_candidate(cand, te)
            te = te.assign(pred_stage1=s1, pred_cand=full, pred_doy=np.nan, pred_air7=np.nan)
            for t, (doy, (a, b)) in base.items():
                m = te["type"].eq(t)
                te.loc[m, "pred_doy"] = wp.predict_doy(doy, te.loc[m, "doy"])
                te.loc[m, "pred_air7"] = a + b * te.loc[m, "a7"]
            preds[name].append(te)
        print(f"fold {k}: {len(tr)} training rows, {len(te0)} test rows, {time.time() - t0:.0f} s", flush=True)
    models = {"cand": "pred_cand", "stage1": "pred_stage1", "doy": "pred_doy", "air7": "pred_air7"}

    def block(d: pd.DataFrame) -> dict:
        return {m: wp.summary(d[c] - d["temp"]) for m, c in models.items()} | {"waters": int(d["group"].nunique())}

    def gains(d: pd.DataFrame) -> dict:
        return wp.boot_gains(d["group"], d["pred_cand"] - d["temp"],
                             {"doy": d["pred_doy"] - d["temp"], "air7": d["pred_air7"] - d["temp"]})

    res = {"features_sha256": sha, "fits": fits, "variants": {}}
    for name in variants:
        p = pd.concat(preds[name], ignore_index=True)
        p.to_parquet(out / f"predictions_{name}.parquet", index=False)
        vr = {"rows_test": int(len(p)), "by_type": {}, "verdict": {}, "groups": {}, "by_year": {}, "by_month": {},
              "by_fold": {}}
        for t in wp.TYPES:
            d = p[p["type"] == t]
            if not len(d):
                continue
            vr["by_type"][t] = block(d) | {"gains": gains(d)}
            if t in wp.RMSE_MAX:
                vr["verdict"][t] = wp.verdict(t, d["group"].nunique(), len(d), wp.rmse(d["pred_cand"] - d["temp"]),
                                              vr["by_type"][t]["gains"])
            vr["by_year"][t] = {int(y): block(g) for y, g in d.groupby("year")}
            vr["by_month"][t] = {int(m): block(g) for m, g in d.groupby(pd.to_datetime(d["date"]).dt.month)}
            vr["by_fold"][t] = {int(k): block(g) for k, g in d.groupby("fold")}
        for bnd, g in p.groupby("band"):
            vr["groups"][f"band: {bnd}"] = block(g)
        su = p[p["small_upland"]]
        vr["groups"]["small upland streams"] = (block(su) | {"gains": gains(su)}) if len(su) else {"waters": 0}
        res["variants"][name] = vr
    res["verdict"] = res["variants"]["primary"]["verdict"]
    res["seconds"] = round(time.time() - t0)
    (out / "score.json").write_text(json.dumps(res, indent=1, default=lambda o: o.item() if isinstance(o, np.generic)
                                               else str(o)))
    print(json.dumps({"verdict": res["verdict"],
                      "rmse": {n: {t: {m: b[m].get("rmse") for m in models} for t, b in v["by_type"].items()}
                               for n, v in res["variants"].items()}}, indent=1))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["rows", "groups", "plan", "haduk", "features", "score"])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--ea", type=Path)
    ap.add_argument("--om", type=Path)
    ap.add_argument("--haduk", type=Path)
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
    elif a.what == "haduk":
        cmd_haduk(a.out, a.haduk)
    elif a.what == "features":
        cmd_features(a.out, a.om)
    else:
        cmd_score(a.out, a.sha, a.doc)


if __name__ == "__main__":
    main()
