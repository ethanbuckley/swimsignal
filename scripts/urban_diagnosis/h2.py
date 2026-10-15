"""H2 of docs/URBAN-DILUTION-DIAGNOSIS-2026-10.md: does A_i track spill size where there is independent evidence?
  h2.py <overflow_urban_area.parquet> <overflows.parquet> <annual_returns.parquet> <uwwtps.csv> <out.json>"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

BOOT, SEED = 2000, 1
ua, ovp, arp, uwp, outp = sys.argv[1:6]


def spearman(x, y):
    rx, ry = rankdata(x), rankdata(y)
    return float(np.corrcoef(rx, ry)[0, 1])


def boot(x, y, clusters=None, x2=None):
    """Spearman rho of x with y, 95% percentile interval (resampling rows, or clusters); with x2, also
    rho(x2, y) and the paired difference rho(x2, y) - rho(x, y)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    rng = np.random.default_rng(SEED)
    if clusters is None:
        draws = (rng.integers(0, len(x), len(x)) for _ in range(BOOT))
    else:
        codes, inv = np.unique(np.asarray(clusters), return_inverse=True)
        members = [np.flatnonzero(inv == c) for c in range(len(codes))]
        draws = (np.concatenate([members[c] for c in rng.integers(0, len(codes), len(codes))]) for _ in range(BOOT))
    r1, r2 = [], []
    for i in draws:
        r1.append(spearman(x[i], y[i]))
        if x2 is not None:
            r2.append(spearman(np.asarray(x2, float)[i], y[i]))
    r1 = np.array(r1)
    res = {"n": len(x), "rho": spearman(x, y), "ci": [float(np.nanpercentile(r1, 2.5)), float(np.nanpercentile(r1, 97.5))]}
    if clusters is not None:
        res["clusters"] = len(np.unique(np.asarray(clusters)))
    if x2 is not None:
        r2 = np.array(r2)
        res.update({"rho_x2": spearman(x2, y), "ci_x2": [float(np.nanpercentile(r2, 2.5)), float(np.nanpercentile(r2, 97.5))],
                    "diff_x2_minus_x": spearman(x2, y) - spearman(x, y),
                    "diff_ci": [float(np.nanpercentile(r2 - r1, 2.5)), float(np.nanpercentile(r2 - r1, 97.5))]})
    return res


u = pd.read_parquet(ua)
u["A"] = u["urban_km2"].clip(0.1, 6.0)                              # as transport.urban_spill_m3s uses it
u["unsplit"] = u["bua_km2"].where(u["bua22cd"].notna(), 0.1)        # H4's unsplit rule, floor 0.1
ov = pd.read_parquet(ovp).drop_duplicates("site_id")[["site_id", "asset_type", "lat", "lon"]]
u = u.merge(ov, on="site_id", how="left")
out = {"n_overflows": len(u)}

# H2a: EDM annual returns, mean over 2021-2025 of years with a value
ar = pd.read_parquet(arp).dropna(subset=["site_id"])
m = ar.groupby("site_id").agg(hours=("spill_hours", "mean"), spills=("spills", "mean"))
d = u.merge(m, left_on="site_id", right_index=True, how="inner")
for col in ("hours", "spills"):
    dd = d.dropna(subset=[col])
    out[f"H2a A vs mean annual {col}, all overflows"] = boot(dd.A, dd[col])
    nw = dd[dd.asset_type == "SO on sewer network"]
    out[f"H2a A vs mean annual {col}, SO on sewer network"] = boot(nw.A, nw[col])

# H2b: population equivalent entering the works (UWWTD Art. 15, data as at 31 Dec 2022)
w = pd.read_csv(uwp)
w = w[(w.uwwLoadEnteringUWWTP > 0) & w.uwwLatitude.notna()].reset_index(drop=True)
works = u[u.asset_type.fillna("").str.contains("WwTW") & u.lat.notna()].reset_index(drop=True)
la1, lo1 = np.radians(works.lat.to_numpy())[:, None], np.radians(works.lon.to_numpy())[:, None]
la2, lo2 = np.radians(w.uwwLatitude.to_numpy())[None, :], np.radians(w.uwwLongitude.to_numpy())[None, :]
D = 2 * 6371000 * np.arcsin(np.sqrt(np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2))
j = D.argmin(axis=1)
works["dist_m"] = D[np.arange(len(works)), j]
works["uwwCode"] = w.uwwCode.to_numpy()[j]
works["pe"] = w.uwwLoadEnteringUWWTP.to_numpy()[j].astype(float)
mt = works[works.dist_m <= 500]
out["H2b UWWTD works with load > 0"] = len(w)
out["H2b overflows at works (asset_type contains WwTW)"] = len(works)
out["H2b matched within 500 m"] = len(mt)
out["H2b distinct works matched"] = int(mt.uwwCode.nunique())
out["H2b matched overflows on the 0.1 floor"] = int((mt.A <= 0.1).sum())
out["H2b pe vs A (x) and vs unsplit bua_km2 (x2), works resampled"] = boot(mt.A, mt.pe, clusters=mt.uwwCode, x2=mt.unsplit)
pw = mt.groupby("uwwCode").agg(A=("A", "mean"), pe=("pe", "first"), unsplit=("unsplit", "max"))
out["H2b per works (one row each): pe vs mean A (x) and unsplit (x2)"] = boot(pw.A, pw.pe, x2=pw.unsplit)

# H2c: works against network overflows
wk = works.A.to_numpy()
nt = u.loc[u.asset_type == "SO on sewer network", "A"].to_numpy()
rng = np.random.default_rng(SEED)
ratios = [np.median(rng.choice(wk, len(wk))) / np.median(rng.choice(nt, len(nt))) for _ in range(BOOT)]
out["H2c"] = {"n_works": len(wk), "n_network": len(nt), "median_A_works": float(np.median(wk)),
              "median_A_network": float(np.median(nt)), "ratio": float(np.median(wk) / np.median(nt)),
              "ci": [float(np.percentile(ratios, 2.5)), float(np.percentile(ratios, 97.5))]}
print(json.dumps(out, indent=1))
Path(outp).write_text(json.dumps(out, indent=1))
