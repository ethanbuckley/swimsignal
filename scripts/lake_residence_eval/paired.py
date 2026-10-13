"""Paired comparisons between variant roots, reading their outputs only: PR #199's
scripts/eval_pins_test/paired.py (from #197's at 34924c1, the #166 / urban-test harness), unchanged but for this
docstring, for docs/LAKE-RESIDENCE-TEST-2026-10.md.

  paired.py prep <root> <out.parquet>    per-sample held-out predictions, rebuilt exactly as train_ecoli.main
                                          (run with DIPCAST_ROOT=<root>; checked against its ecoli_model_eval.json)
  paired.py compare <ref> <new>           paired bootstraps, ref vs new (variant names under roots/), on the
                                          samples that both runs keep
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(os.environ["DIAG_DIR"])   # roots/, logs/, tables/ and outputs
BOOT, SEED = 2000, 1
SCRIPTS = str(Path(__file__).resolve().parents[1])


def prep(root: str, out: str) -> None:
    sys.path.insert(0, SCRIPTS)
    import train_ecoli as T

    from dipcast import config
    from dipcast.model.ecoli import THRESHOLD, features
    from dipcast.model.forecast import MAX_MISSING_SHARE
    assert str(config.ROOT) == root, (config.ROOT, root)
    # --- the row preparation of train_ecoli.main, unchanged
    rows = pd.read_parquet(config.PROCESSED / "ecoli_validation_rows.parquet")
    rows = rows[rows.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "ecoli"]).reset_index(drop=True)
    rows["lake"] = (rows["kind"] == "lake").astype(float)
    rows["day"] = rows["sample_time"].dt.floor("D")
    sites = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id").set_index("bw_id")
    rows["lat"], rows["lon"] = sites.loc[rows.bw_id, "lat"].to_numpy(), sites.loc[rows.bw_id, "lon"].to_numpy()
    ex = pd.read_parquet(T.EXPOSURE_FILE)
    ex["day"] = pd.to_datetime(ex["day"])
    if ex["day"].dt.tz is None and rows["day"].dt.tz is not None:
        ex["day"] = ex["day"].dt.tz_localize(rows["day"].dt.tz)
    if "missing_share" not in ex:
        ex["missing_share"] = np.where(ex["risk_prod"].isna(), 1.0, 0.0)
    for k in T.LEADS:
        e = ex[ex.lead == k][["bw_id", "day", "risk_prod", "risk_holdout", "missing_share"]].rename(
            columns={"risk_prod": f"risk_lead{k}", "risk_holdout": f"risk_hold_lead{k}", "missing_share": f"miss_lead{k}"})
        rows = rows.merge(e, on=["bw_id", "day"], how="left")
    fc = T.forecast_rain_at_samples(rows)
    ok_rain = np.all([~np.isnan(fc[k][0]) for k in T.LEADS], axis=0)
    shown = {k: (rows[f"miss_lead{k}"].fillna(1.0).to_numpy() <= MAX_MISSING_SHARE) & rows[f"risk_lead{k}"].notna().to_numpy()
             for k in T.LEADS}
    ok = ok_rain & np.all([shown[k] for k in T.LEADS], axis=0)
    rows = rows[ok].reset_index(drop=True)
    fc = {k: (fc[k][0][ok], fc[k][1][ok], fc[k][2][ok]) for k in T.LEADS}
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years = rows["sample_time"].dt.year.to_numpy()
    lake = rows["lake"].to_numpy()
    site = rows["bw_id"].to_numpy()
    X = features(fc[0][0], fc[0][1], rows["risk_lead0"], rows.lake, rows.sample_time)
    # --- held-out predictions
    res = pd.DataFrame({"bw_id": site, "sample_time": rows["sample_time"], "y": y, "lake": lake,
                        "week": (rows["bw_id"] + "|" + rows["sample_time"].dt.strftime("%G-%V")).to_numpy()})
    res["loyo_full"] = T.leave_one_out(X, y, years, lake, T.VARIANTS[T.FULL])
    res["loyo_rain"] = T.leave_one_out(X, y, years, lake, T.VARIANTS[T.RAIN_ONLY])
    res["loso_full"] = T.leave_one_out(X, y, site, lake, T.VARIANTS[T.FULL])
    if rows["risk_hold_lead0"].notna().all():
        Xh = features(fc[0][0], fc[0][1], rows["risk_hold_lead0"], rows.lake, rows.sample_time)
        tr, te = years <= T.FORWARD_TRAIN_UNTIL, years > T.FORWARD_TRAIN_UNTIL
        p = np.full(len(y), np.nan); p[te] = T._fit_predict(Xh, y, tr, te, T.VARIANTS[T.FULL], lake)
        res["fwd_full"] = p
    ev = json.loads((config.PROCESSED / "ecoli_model_eval.json").read_text())
    want = {r["model"]: r for r in ev["loyo"]}[T.FULL]["brier"]
    got = float(np.mean((res.loyo_full - res.y) ** 2))
    print(f"{root}: n={len(res)} LOYO full Brier {got:.4f} (train_ecoli {want:.4f}, n {ev['n_samples']})")
    assert abs(round(got, 4) - want) < 1e-9 and len(res) == ev["n_samples"]
    res.to_parquet(out, index=False)


def site_means(v: str) -> pd.DataFrame:
    """The rows and site means of validate_ecoli_combined.between_site."""
    r = pd.read_parquet(HERE / "roots" / v / "data/processed/ecoli_validation_rows.parquet")
    d = r[r.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "log_ecoli"])
    return d.groupby("bw_id").agg(risk=("risk_model", "mean"), ecoli=("log_ecoli", "mean"))


def compare(ref: str, new: str) -> dict:
    sys.path.insert(0, SCRIPTS)
    from scipy.stats import spearmanr
    from train_ecoli import cluster_bootstrap
    a = pd.read_parquet(HERE / f"preds_{ref}.parquet")
    b = pd.read_parquet(HERE / f"preds_{new}.parquet")
    # The samples that both runs keep (#166's statement). A run drops a whole site when more than
    # MAX_MISSING_SHARE of its weight comes from overflows without rain data, and the sizes move that weight.
    # A site can have two samples at one time: they pair in order.
    keys = ["bw_id", "sample_time", "occ"]
    a, b = (d.assign(occ=d.groupby(["bw_id", "sample_time"]).cumcount()) for d in (a, b))
    m = a.merge(b, on=keys, how="inner", suffixes=("_a", "_b"), validate="one_to_one")
    assert (m.y_a == m.y_b).all() and (m.week_a == m.week_b).all() and (m.lake_a == m.lake_b).all()
    y, week, rivers = m.y_a.to_numpy(), m.week_a.to_numpy(), m.lake_a.to_numpy() == 0.0
    out = {"n_ref": len(a), "n_new": len(b), "n_paired": len(m),
           "sites_ref_only": sorted(set(a.bw_id) - set(b.bw_id)), "sites_new_only": sorted(set(b.bw_id) - set(a.bw_id))}
    for key, mask in (("loyo_all", None), ("loyo_rivers", rivers)):
        out[key] = cluster_bootstrap(y, m.loyo_full_a.to_numpy(), m.loyo_full_b.to_numpy(), week,
                                     mask=None if mask is None else mask.copy(), n_boot=BOOT, seed=SEED)
    out["loyo_lakes"] = cluster_bootstrap(y, m.loyo_full_a.to_numpy(), m.loyo_full_b.to_numpy(), week,
                                          mask=(m.lake_a.to_numpy() == 1.0).copy(), n_boot=BOOT, seed=SEED)
    out["loso_all"] = cluster_bootstrap(y, m.loso_full_a.to_numpy(), m.loso_full_b.to_numpy(), week, n_boot=BOOT, seed=SEED)
    if "fwd_full_a" in m and "fwd_full_b" in m:
        te = ~np.isnan(m.fwd_full_a.to_numpy()) & ~np.isnan(m.fwd_full_b.to_numpy())
        out["fwd_all"] = cluster_bootstrap(y, m.fwd_full_a.to_numpy(), m.fwd_full_b.to_numpy(), week, mask=te, n_boot=BOOT, seed=SEED)
    sa, sb = site_means(ref), site_means(new)
    s = sa.join(sb, lsuffix="_a", rsuffix="_b", how="inner")
    assert np.allclose(s.ecoli_a, s.ecoli_b)
    rho = lambda d, c: spearmanr(d[c], d.ecoli_a).statistic
    rng = np.random.default_rng(SEED)
    diffs, ra, rb = [], [], []
    for _ in range(BOOT):
        d = s.iloc[rng.integers(0, len(s), len(s))]
        x, z = rho(d, "risk_a"), rho(d, "risk_b")
        if np.isfinite(x) and np.isfinite(z):
            ra.append(x); rb.append(z); diffs.append(z - x)
    out["cross_site"] = {"sites": len(s), "rho_ref": float(rho(s, "risk_a")), "rho_new": float(rho(s, "risk_b")),
                         "rho_ref_ci": [float(np.percentile(ra, 2.5)), float(np.percentile(ra, 97.5))],
                         "rho_new_ci": [float(np.percentile(rb, 2.5)), float(np.percentile(rb, 97.5))],
                         "change": float(rho(s, "risk_b") - rho(s, "risk_a")),
                         "change_ci": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
                         "resamples": len(diffs)}
    return out


if __name__ == "__main__":
    if sys.argv[1] == "prep":
        prep(sys.argv[2], sys.argv[3])
    else:
        r = compare(sys.argv[2], sys.argv[3])
        (HERE / f"paired_{sys.argv[2]}_{sys.argv[3]}.json").write_text(json.dumps(r, indent=1, default=float))
        print(json.dumps(r, indent=1, default=float))
