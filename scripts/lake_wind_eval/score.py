"""docs/LAKE-WIND-TEST-2026-10.md: wind towards a lake bathing water from its heaviest inflow, as an E. coli input.

    score.py <wind cache> <out dir>

1. Face check of the projection; then geometry.py's inflows in this root, which must cover wind.LAKE_BWS exactly.
2. train_ecoli.py's rows and filters, unchanged. wind24_to for each lake row at a site with a bearing (the heaviest
   inflow enters 1,000 m or more from the pin): the 24 h mean of the wind along the bearing from that entry to the pin,
   from the lead-0 wind at the sample's cell. Rows at those sites without it leave both arms (counted).
3. Conditions 1 and 2 on lake rows at the sites with a bearing; conditions 3 to 5 from train_ecoli.py's own
   evaluations with and without lake_x_wind24; condition 6's face check against ecoli_model_eval.json in this root.
4. The reported-only figures and the per-lake description.

Writes <out dir>/score.json and <out dir>/geometry.csv.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geometry as geo
import numpy as np
import pandas as pd
import train_ecoli as te
import wind as wd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model import transport as T
from dipcast.model.ecoli import FEATURES, THRESHOLD, features, fit
from dipcast.model.forecast import MAX_MISSING_SHARE
from dipcast.model.verify import scores
from dipcast.network.rivers import RiverNetwork
from dipcast.overflows import load_overflows

NEW = "lake_x_wind24"
ARMS = {"reference": FEATURES, "with_wind": [*FEATURES, NEW]}
MARGIN = 0.0005
NEAR_FIELD_M = T.LAKE_DOWN_MARGIN_M
CONTROLS = ["lrain48", "lrain24", "logit_risk", "doy_sin", "doy_cos"]
BOOT, BOOT_SEED = 2000, 20261024
PLACEBOS, PLACEBO_SEED = 1000, 1024
WINDOWS = (24, 6, 48)   # 24 h decides; 6 h and 48 h are reported only


def check_projection() -> dict:
    b = 37.0
    along, against, across = wd.towards(5.0, b + 180.0, b), wd.towards(5.0, b, b), wd.towards(5.0, b + 90.0, b)
    ok = abs(along - 5.0) < 1e-9 and abs(against + 5.0) < 1e-9 and abs(across) < 1e-9
    if not ok:
        raise SystemExit(f"projection face check failed: {along}, {against}, {across}")
    return {"along": float(along), "against": float(against), "across": float(across)}


def lake_geometry(out_dir: Path) -> pd.DataFrame:
    net = RiverNetwork.load()
    ov = load_overflows(net)
    bw = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id")
    parts = [geo.inflows(net, ov, r.bw_id, r.name, float(r.lon), float(r.lat)) for r in bw.itertuples()]
    g = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    g.to_csv(out_dir / "geometry.csv", index=False)
    if set(g.bw_id) != set(wd.LAKE_BWS):
        raise SystemExit(f"geometry finds other lake waters than the fetch: {sorted(set(g.bw_id) ^ set(wd.LAKE_BWS))}")
    c = g[g.chosen].set_index("bw_id")
    c["has_bearing"] = c["line_m"] >= NEAR_FIELD_M
    return c


def site_ranks(d: pd.DataFrame, col: str) -> np.ndarray:
    """Ranks within each site (ties averaged), over the site's count, centred on the site's mean."""
    g = d.groupby("bw_id")[col]
    r = g.rank(method="average") / g.transform("size")
    return (r - r.groupby(d["bw_id"]).transform("mean")).to_numpy()


def partial_rho(d: pd.DataFrame, col: str) -> float:
    """Condition 1's score: correlation of the within-site ranks of log10 E. coli and `col`, each less its pooled
    least-squares fit on the controls' within-site ranks."""
    d = d.reset_index(drop=True)
    y, x = site_ranks(d, "log_ecoli"), site_ranks(d, col)
    Z = np.column_stack([site_ranks(d, c) for c in CONTROLS])
    ry = y - Z @ np.linalg.lstsq(Z, y, rcond=None)[0]
    rx = x - Z @ np.linalg.lstsq(Z, x, rcond=None)[0]
    return float(np.corrcoef(ry, rx)[0, 1])


def within_rho(d: pd.DataFrame, col: str) -> float:
    """Within-site Spearman as validate_ecoli.py computes it: each value less its site's mean."""
    w = lambda c: d[c] - d.groupby("bw_id")[c].transform("mean")   # noqa: E731
    return float(spearmanr(w(col), w("log_ecoli")).statistic)


def week_boot(d: pd.DataFrame, stat, seed: int = BOOT_SEED) -> list[float]:
    """95% interval of stat(d) over a cluster bootstrap of calendar weeks (ISO year and week)."""
    rng = np.random.default_rng(seed)
    wk = d["sample_time"].dt.strftime("%G-%V").to_numpy()
    uniq, inv = np.unique(wk, return_inverse=True)
    idx_by = [np.where(inv == i)[0] for i in range(len(uniq))]
    vals = []
    for _ in range(BOOT):
        pick = rng.integers(0, len(uniq), len(uniq))
        vals.append(stat(d.iloc[np.concatenate([idx_by[i] for i in pick])]))
    vals = np.asarray(vals, dtype=float)
    return [float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))]


def wind_at_rows(rows: pd.DataFrame, cache: Path, chosen: pd.DataFrame) -> pd.DataFrame:
    """For lake rows at sites with a bearing: the window means of the north and east components, of speed, and the
    projection on the bearing, for each window. NaN elsewhere."""
    out = pd.DataFrame(np.nan, index=rows.index, columns=[f"{k}{h}" for h in WINDOWS for k in ("vn", "ve", "speed", "to")])
    cl, cn = grid_cell(rows["lat"].to_numpy(), rows["lon"].to_numpy())
    cl, cn = np.round(cl, 3), np.round(cn, 3)
    sites = chosen.index[chosen.has_bearing]
    for c in sorted(set(zip(cl, cn, strict=True))):
        idx = np.where((cl == c[0]) & (cn == c[1]) & rows["bw_id"].isin(sites).to_numpy())[0]
        if len(idx) == 0:
            continue
        w = wd.load(cache, (float(c[0]), float(c[1])))
        if w.empty:
            continue
        w.index = w.index.tz_convert("Europe/London")
        ends = pd.DatetimeIndex(rows["sample_time"].iloc[idx])
        beta = np.radians(chosen.loc[rows["bw_id"].iloc[idx], "bearing_deg"].to_numpy())
        for h in WINDOWS:
            vn, ve = wd.window_means(w["v_n"], ends, h), wd.window_means(w["v_e"], ends, h)
            sp = wd.window_means(w["wind_speed_10m"].where(w["v_n"].notna()), ends, h)
            out.iloc[idx, out.columns.get_loc(f"vn{h}")] = vn
            out.iloc[idx, out.columns.get_loc(f"ve{h}")] = ve
            out.iloc[idx, out.columns.get_loc(f"speed{h}")] = sp
            out.iloc[idx, out.columns.get_loc(f"to{h}")] = vn * np.cos(beta) + ve * np.sin(beta)
        # The component form equals the hourly projection averaged directly.
        bw = rows["bw_id"].iloc[idx[0]]
        hourly = pd.Series(wd.towards(w["wind_speed_10m"], w["wind_direction_10m"], chosen.loc[bw, "bearing_deg"]),
                           index=w.index)
        same = rows["bw_id"].iloc[idx].to_numpy() == bw
        direct = wd.window_means(hourly, ends[same], 24)
        if not np.allclose(direct, out["to24"].to_numpy()[idx[same]], atol=1e-9, equal_nan=True):
            raise SystemExit(f"component and hourly projections differ at {bw}")
    return out


def main(cache_dir: str, out_dir: str) -> None:
    cache, out = Path(cache_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res: dict = {"projection_check": check_projection()}
    chosen = lake_geometry(out)
    res["inflows_used"] = chosen.reset_index()[["bw_id", "bw_name", "names", "share", "line_m", "lake_distance_m",
                                                "bearing_deg", "has_bearing"]].to_dict("records")
    # ---- train_ecoli.main's rows and filters, unchanged
    rows = pd.read_parquet(config.PROCESSED / "ecoli_validation_rows.parquet")
    rows = rows[rows.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "ecoli"]).reset_index(drop=True)
    rows["lake"] = (rows["kind"] == "lake").astype(float)
    rows["day"] = rows["sample_time"].dt.floor("D")
    sites = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id").set_index("bw_id")
    rows["lat"], rows["lon"] = sites.loc[rows.bw_id, "lat"].to_numpy(), sites.loc[rows.bw_id, "lon"].to_numpy()
    ex = pd.read_parquet(te.EXPOSURE_FILE)
    ex["day"] = pd.to_datetime(ex["day"])
    if ex["day"].dt.tz is None and rows["day"].dt.tz is not None:
        ex["day"] = ex["day"].dt.tz_localize(rows["day"].dt.tz)
    if "missing_share" not in ex:
        ex["missing_share"] = np.where(ex["risk_prod"].isna(), 1.0, 0.0)
    for k in te.LEADS:
        e = ex[ex.lead == k][["bw_id", "day", "risk_prod", "risk_holdout", "missing_share"]].rename(
            columns={"risk_prod": f"risk_lead{k}", "risk_holdout": f"risk_hold_lead{k}", "missing_share": f"miss_lead{k}"})
        rows = rows.merge(e, on=["bw_id", "day"], how="left")
    fc = te.forecast_rain_at_samples(rows)
    ok_rain = np.all([~np.isnan(fc[k][0]) for k in te.LEADS], axis=0)
    shown = {k: (rows[f"miss_lead{k}"].fillna(1.0).to_numpy() <= MAX_MISSING_SHARE) & rows[f"risk_lead{k}"].notna().to_numpy()
             for k in te.LEADS}
    ok = ok_rain & np.all([shown[k] for k in te.LEADS], axis=0)
    n_train_ecoli = int(ok.sum())
    lake_unplaced = sorted(set(rows.loc[ok & (rows.lake == 1.0).to_numpy(), "bw_id"]) - set(chosen.index))
    if lake_unplaced:
        raise SystemExit(f"lake rows at waters geometry.py does not place: {lake_unplaced}")
    # ---- the wind; rows at a site with a bearing but no wind leave both arms
    wr = wind_at_rows(rows, cache, chosen)
    bearing_site = rows["bw_id"].map(chosen["has_bearing"]).fillna(False).to_numpy(dtype=bool)
    ok_w = ok & (~bearing_site | np.isfinite(wr["to24"].to_numpy()))
    res["rows"] = {"train_ecoli": n_train_ecoli, "dropped_no_wind": int((ok & ~ok_w).sum()), "scored": int(ok_w.sum())}
    rows, wr, bearing_site = rows[ok_w].reset_index(drop=True), wr[ok_w].reset_index(drop=True), bearing_site[ok_w]
    fc0 = (fc[0][0][ok_w], fc[0][1][ok_w])
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years = rows["sample_time"].dt.year.to_numpy()
    lake = rows["lake"].to_numpy()
    site = rows["bw_id"].to_numpy()
    week = (rows["bw_id"] + "|" + rows["sample_time"].dt.strftime("%G-%V")).to_numpy()
    rivers, lakes = lake == 0.0, lake == 1.0
    wind24 = np.where(bearing_site, wr["to24"].to_numpy(), 0.0)

    def add(X):
        X[NEW] = wind24
        return X

    X = add(features(fc0[0], fc0[1], rows["risk_lead0"], rows.lake, rows.sample_time))
    Xh = add(features(fc0[0], fc0[1], rows["risk_hold_lead0"], rows.lake, rows.sample_time))

    def brier(p, m=None):
        m = np.ones(len(y), dtype=bool) if m is None else m
        m = m & ~np.isnan(p)
        return float(np.mean((p[m] - y[m]) ** 2))

    p_loyo = {a: te.leave_one_out(X, y, years, lake, c) for a, c in ARMS.items()}
    p_loso = {a: te.leave_one_out(X, y, site, lake, c) for a, c in ARMS.items()}
    tr, tt = years <= te.FORWARD_TRAIN_UNTIL, years > te.FORWARD_TRAIN_UNTIL
    p_fwd = {}
    for a, c in ARMS.items():
        p = np.full(len(y), np.nan); p[tt] = te._fit_predict(Xh, y, tr, tt, c, lake); p_fwd[a] = p
    for name, pp, m in (("loyo", p_loyo, None), ("loso", p_loso, None), ("forward", p_fwd, tt)):
        res[name] = {a: {"all": brier(pp[a], m), "rivers": brier(pp[a], (m if m is not None else True) & rivers),
                         "lakes": brier(pp[a], (m if m is not None else True) & lakes),
                         "scores": {k: v for k, v in scores(y[~np.isnan(pp[a])], pp[a][~np.isnan(pp[a])]).items()
                                    if k in ("brier", "auc", "log_loss", "n")}} for a in ARMS}
    res["bootstrap_loyo_site_week"] = te.cluster_bootstrap(y, p_loyo["reference"], p_loyo["with_wind"], week)
    res["bootstrap_loyo_lakes_site_week"] = te.cluster_bootstrap(y, p_loyo["reference"], p_loyo["with_wind"], week,
                                                                 mask=lakes.copy())
    final = {a: fit(X, y, c) for a, c in ARMS.items()}
    res["coef_per_sd"] = {a: final[a].coef for a in ARMS}

    # ---- conditions 1 and 2: lake rows at the sites with a bearing
    d = rows.loc[bearing_site, ["bw_id", "name", "sample_time", "log_ecoli", "ecoli"]].copy()
    for c in CONTROLS:
        d[c] = X.loc[bearing_site, c].to_numpy()
    for h in WINDOWS:
        for k in ("vn", "ve", "speed", "to"):
            d[f"{k}{h}"] = wr.loc[bearing_site, f"{k}{h}"].to_numpy()
    d = d.reset_index(drop=True)
    rho = partial_rho(d, "to24")
    ci = week_boot(d, lambda x: partial_rho(x, "to24"))
    rng = np.random.default_rng(PLACEBO_SEED)
    order = sorted(d.bw_id.unique())
    plc = []
    for _ in range(PLACEBOS):
        b = dict(zip(order, np.radians(rng.uniform(0.0, 360.0, len(order))), strict=True))
        bb = d.bw_id.map(b).to_numpy()
        plc.append(partial_rho(d.assign(p=d.vn24 * np.cos(bb) + d.ve24 * np.sin(bb)), "p"))
    plc = np.asarray(plc)
    res["condition_1"] = {"n": len(d), "sites": int(d.bw_id.nunique()), "weeks": int(d.sample_time.dt.strftime("%G-%V").nunique()),
                          "over_900": int((d.ecoli > THRESHOLD).sum()), "partial_rho": rho, "ci": ci}
    res["condition_2"] = {"placebos": PLACEBOS, "share_at_least_as_high": float((plc >= rho).mean()),
                          "lowest": float(plc.min()), "median": float(np.median(plc)),
                          "p95": float(np.percentile(plc, 95)), "highest": float(plc.max())}

    # ---- condition 3: the model's within-site ranking at lakes
    dl = rows.loc[lakes, ["bw_id", "sample_time", "log_ecoli"]].assign(
        ref=p_loyo["reference"][lakes], new=p_loyo["with_wind"][lakes]).dropna().reset_index(drop=True)
    r_ref, r_new = within_rho(dl, "ref"), within_rho(dl, "new")
    res["condition_3"] = {"n": len(dl), "sites": int(dl.bw_id.nunique()), "rho_reference": r_ref, "rho_with_wind": r_new,
                          "change": r_new - r_ref, "change_ci": week_boot(dl, lambda x: within_rho(x, "new") - within_rho(x, "ref"))}

    L, S, F = res["loyo"], res["loso"], res["forward"]
    worse = {"loyo_all": L["with_wind"]["all"] - L["reference"]["all"],
             "loyo_rivers": L["with_wind"]["rivers"] - L["reference"]["rivers"],
             "loyo_lakes": L["with_wind"]["lakes"] - L["reference"]["lakes"],
             "loso_all": S["with_wind"]["all"] - S["reference"]["all"],
             "forward_all": F["with_wind"]["all"] - F["reference"]["all"]}
    res["condition_4_worse_by"] = worse
    # ---- condition 6: train_ecoli.py's own output in this root
    e = json.loads((config.PROCESSED / "ecoli_model_eval.json").read_text())
    pub = {"loyo": next(r["brier"] for r in e["loyo"] if r["model"] == te.FULL),
           "loso": next(r["brier"] for r in e["loso"] if r["model"] == te.FULL),
           "forward": next(r["brier"] for r in e["forward"]["table"] if r["model"] == te.FULL), "n": e["n_samples"]}
    here = {"loyo": round(L["reference"]["all"], 4), "loso": round(S["reference"]["all"], 4),
            "forward": round(F["reference"]["all"], 4), "n": n_train_ecoli}
    face = all(abs(round(pub[k], 4) - here[k]) < 1e-12 for k in ("loyo", "loso", "forward")) and pub["n"] == here["n"]
    res["face_check"] = {"train_ecoli": pub, "here_reference": here, "matches": bool(face),
                         "rows_dropped_no_wind": res["rows"]["dropped_no_wind"]}
    res["conditions"] = {
        "1_partial_rho_above_zero": bool(rho > 0 and ci[0] > 0),
        "2_placebos": bool(res["condition_2"]["share_at_least_as_high"] <= 0.05),
        "3_lake_ranking_rises": bool(res["condition_3"]["change"] > 0),
        "4_no_harm": bool(all(v <= MARGIN for v in worse.values())),
        "5_sign_positive": bool(final["with_wind"].coef[NEW] > 0),
        "6_face_check": bool(face)}
    res["conditions"]["passes"] = all(res["conditions"].values())

    # ---- reported only
    rep: dict = {}
    for h in (6, 48):
        rep[f"partial_rho_{h}h"] = {"rho": partial_rho(d, f"to{h}"), "ci": week_boot(d, lambda x, h=h: partial_rho(x, f"to{h}"))}
    rep["partial_rho_speed24"] = {"rho": partial_rho(d, "speed24"), "ci": week_boot(d, lambda x: partial_rho(x, "speed24"))}
    med = float(np.median(d.logit_risk))
    for nm, m in (("above", d.logit_risk > med), ("at_or_below", d.logit_risk <= med)):
        dd = d[m].reset_index(drop=True)
        rep[f"partial_rho_exposure_{nm}_median"] = {"n": len(dd), "rho": partial_rho(dd, "to24")}
    yl = y[lakes]
    rep["lake_loyo_auc"] = {a: float(roc_auc_score(yl, p_loyo[a][lakes])) for a in ARMS} if 0 < yl.mean() < 1 else None
    rep["corr_wind24_lrain48"] = float(np.corrcoef(d.to24, d.lrain48)[0, 1])
    desc = []
    for bw, c in chosen.sort_values("bw_name").iterrows():
        g = rows[rows.bw_id == bw]
        row = {"bw_id": bw, "name": c.bw_name, "samples": len(g), "over_900": int((g.ecoli > THRESHOLD).sum()),
               "inflow": c.names, "line_m": round(float(c.line_m)), "bearing_deg": round(float(c.bearing_deg), 1),
               "has_bearing": bool(c.has_bearing)}
        if c.has_bearing:
            gd = d[d.bw_id == bw]
            to, le = gd.to24.to_numpy(), gd.log_ecoli.to_numpy()
            row |= {"mean_wind24_to": float(to.mean()), "share_towards": float((to > 0).mean()),
                    "rho_raw": float(spearmanr(to, le).statistic),
                    "gmean_towards": float(10 ** le[to > 0].mean()) if (to > 0).any() else None,
                    "gmean_away": float(10 ** le[to <= 0].mean()) if (to <= 0).any() else None}
        desc.append(row)
    rep["description_only"] = desc
    res["reported_only"] = rep
    (out / "score.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:])
