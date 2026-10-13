"""The size tables of docs/PE-SIZE-TEST-2026-10.md: each overflow's consented dry weather flow (DWF), joined from
the EA's consents by outlet position, and 20 placebos.

    python scripts/pe_size_eval/make_variants.py <consents tables dir> <overflows.parquet> <annual_returns.parquet> \
        <out dir> [overflow_urban_area.parquet]

<consents tables dir> holds export_consents.py's parquet tables. The consents are under the Environment Agency
Conditional Licence (internal use only, never published), so <out dir> must lie outside the repo: the tables
written there hold per-overflow values taken from them. The script prints aggregates only.

Writes <out dir>/dwf.parquet and pd01.parquet .. pd20.parquet, each with site_id and urban_km2, the column the
dilution "urban" reads (transport.URBAN_AREA_FILE). An overflow's size is its DWF over the median DWF of the
overflows given one, times URBAN_MEDIAN_KM2, so the median such overflow spills as in "flow", and
transport.urban_spill_m3s clips it as it does the urban areas. An overflow with no DWF is left out and takes the
median. pd<k> permutes the sizes across the same overflows with numpy default_rng(k).

The join, fixed in the statement before any run:
- Candidates: rows of the active consents whose effluent is a water company's sewer storm overflow, pumping
  station overflow, or storm overflow / storm tank at a treatment works; placed at the outlet grid reference
  (the effluent's when the outlet has none).
- A candidate's DWF: its own effluent's DWF (the Effluents table, else the determinand "FLOW : DRY WEATHER :-
  {DWF}" converted to m3/d); else the largest DWF of any effluent on the same permit (a works' final effluent).
- Each overflow is matched to the nearest candidate within MAX_M of either of its positions (the overflow table's
  and its latest annual return's grid reference). If another candidate lies within TIE_M of the nearest one's
  distance and carries a different DWF, the overflow is left unjoined.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

URBAN_MEDIAN_KM2 = 0.512                 # transport.URBAN_MEDIAN_KM2
URBAN_MIN_KM2, URBAN_MAX_KM2 = 0.1, 6.0  # transport's clip
PLACEBOS = 20
MAX_M, TIE_M = 100.0, 10.0
TYPES = ("SEWAGE DISCHARGES - SEWER STORM OVERFLOW - WATER COMPANY",
         "SEWAGE DISCHARGES - PUMPING STATION - WATER COMPANY",
         "SEWAGE DISCHARGES - STW STORM OVERFLOW/STORM TANK - WATER COMPANY")
DWF_DETE = "FLOW : DRY WEATHER :- {DWF}"
TO_M3D = {"CUBIC METRE PER DAY": 1.0, "MEGALITRE PER DAY": 1000.0, "LITRE PER SECOND": 86.4,
          "CUBIC METRE PER HOUR": 24.0}
KEY = ["PERMIT_NUMBER", "PERMIT_VERSION", "OUTLET_NUMBER", "EFFLUENT_NUMBER"]
EKEY = ["PERMIT_REF", "VERSION", "OUTLET_NUMBER", "EFFLUENT_NUMBER"]
REPO = Path(__file__).resolve().parents[2]


def ngr_to_en(ref) -> tuple[float, float]:
    """An OS grid reference (two letters and an even count of digits, e.g. "SU 12345 67890", a made-up one) to easting and northing (m), at the centre of its precision."""
    if not isinstance(ref, str):
        return np.nan, np.nan
    r = ref.replace(" ", "").upper()
    if len(r) < 4 or not r[:2].isalpha() or not r[2:].isdigit() or len(r[2:]) % 2:
        return np.nan, np.nan
    a, b = ord(r[0]) - 65, ord(r[1]) - 65
    a, b = a - (a > 7), b - (b > 7)        # no letter I
    e100 = ((a - 2) % 5) * 5 + b % 5
    n100 = (19 - (a // 5) * 5) - b // 5
    h = len(r[2:]) // 2
    if h > 5:
        return np.nan, np.nan
    scale = 10 ** (5 - h)
    half = scale / 2 if scale > 1 else 0.0
    return e100 * 1e5 + int(r[2:2 + h]) * scale + half, n100 * 1e5 + int(r[2 + h:]) * scale + half


def candidates(folder: Path) -> pd.DataFrame:
    a = pd.read_parquet(folder / "consents_active.parquet")
    e = pd.read_parquet(folder / "Effluents.parquet")
    d = pd.read_parquet(folder / "Determinands.parquet")
    own = e.assign(dwf=pd.to_numeric(e["DWF (m3_d)"], errors="coerce")).rename(columns=dict(zip(EKEY, KEY)))
    own = own[own.dwf > 0].groupby(KEY).dwf.max()
    dd = d[d.DETE.str.upper().str.strip() == DWF_DETE].copy()
    dd["dwf"] = pd.to_numeric(dd.VAL_1, errors="coerce") * dd.UNITS.str.upper().map(TO_M3D)
    det = dd[dd.dwf > 0].rename(columns=dict(zip(EKEY, KEY))).groupby(KEY).dwf.max()
    rows = a.set_index(KEY)
    rows["dwf"] = own.reindex(rows.index)
    rows["dwf"] = rows["dwf"].fillna(det.reindex(rows.index))
    rows = rows.reset_index()
    permit = rows.groupby("PERMIT_NUMBER").dwf.max()
    c = rows[rows.EFF_TYPE_DESCRIPTION.isin(TYPES)].copy()
    c["size"] = c.dwf.fillna(c.PERMIT_NUMBER.map(permit))
    ref = c.OUTLET_GRID_REF.where(c.OUTLET_GRID_REF.notna() & (c.OUTLET_GRID_REF.str.strip() != ""), c.EFFLUENT_GRID_REF)
    en = np.array([ngr_to_en(x) for x in ref], dtype=float).reshape(-1, 2)
    c["e"], c["n"] = en[:, 0], en[:, 1]
    return c.dropna(subset=["e", "n"])[["e", "n", "size"]].reset_index(drop=True)


def overflow_positions(ov: pd.DataFrame, ar: pd.DataFrame) -> list[np.ndarray]:
    tr = Transformer.from_crs(4326, 27700, always_xy=True)
    e, n = tr.transform(ov.lon.to_numpy(), ov.lat.to_numpy())
    a = ar.dropna(subset=["site_id", "ngr_easting", "ngr_northing"]).sort_values("year").drop_duplicates("site_id", keep="last")
    a = a.set_index("site_id").reindex(ov.site_id)
    return [np.c_[e, n], np.c_[a.ngr_easting.to_numpy(float), a.ngr_northing.to_numpy(float)]]


def join(ov: pd.DataFrame, ar: pd.DataFrame, c: pd.DataFrame) -> pd.DataFrame:
    tree = cKDTree(c[["e", "n"]].to_numpy())
    best: list[dict[int, float]] = [dict() for _ in range(len(ov))]
    for pos in overflow_positions(ov, ar):
        ok = np.isfinite(pos).all(axis=1)
        idx = np.flatnonzero(ok)
        for i, hits in zip(idx, tree.query_ball_point(pos[ok], r=MAX_M)):
            for j in hits:
                dist = float(np.hypot(*(pos[i] - c.loc[j, ["e", "n"]].to_numpy(float))))
                best[i][j] = min(dist, best[i].get(j, np.inf))
    size = c["size"].to_numpy()
    out = []
    for b in best:
        if not b:
            out.append(("none", np.nan, np.nan))
            continue
        d0 = min(b.values())
        near = [j for j, dist in b.items() if dist <= d0 + TIE_M]
        s = {("nan" if np.isnan(size[j]) else round(float(size[j]), 6)) for j in near}
        if len(s) > 1:
            out.append(("ambiguous", d0, np.nan))
        else:
            j = min(near, key=lambda j: b[j])
            out.append(("joined", d0, size[j]))
    r = pd.DataFrame(out, columns=["join", "dist_m", "dwf"])
    r.insert(0, "site_id", ov.site_id.to_numpy())
    return r


def main() -> None:
    folder, ov_path, ar_path, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4]).resolve()
    assert REPO not in out.parents and out != REPO, "the size tables hold licensed values: write them outside the repo"
    ov = pd.read_parquet(ov_path).drop_duplicates("site_id").reset_index(drop=True)
    ar = pd.read_parquet(ar_path)
    c = candidates(folder)
    j = join(ov, ar, c)
    out.mkdir(parents=True, exist_ok=True)
    v = j.dropna(subset=["dwf"]).query("dwf > 0")
    size = URBAN_MEDIAN_KM2 * v.dwf / float(v.dwf.median())
    t = pd.DataFrame({"site_id": v.site_id.to_numpy(), "urban_km2": size.to_numpy()})
    t.to_parquet(out / "dwf.parquet", index=False)
    for k in range(1, PLACEBOS + 1):
        t.assign(urban_km2=np.random.default_rng(k).permutation(t["urban_km2"].to_numpy())).to_parquet(
            out / f"pd{k:02d}.parquet", index=False)
    j.to_parquet(out / "join.parquet", index=False)   # scratch only, never published
    # Aggregates only from here.
    n = len(ov)
    counts = j["join"].value_counts()
    print(f"overflows {n}; joined {counts.get('joined', 0)} ({counts.get('joined', 0) / n:.1%}); "
          f"ambiguous {counts.get('ambiguous', 0)}; none within {MAX_M:.0f} m {counts.get('none', 0)}")
    print(f"with a DWF (sized) {len(t)} ({len(t) / n:.1%}); the rest take the median")
    print("match distance quantiles (m), joined:", j.loc[j["join"] == "joined", "dist_m"].quantile([.25, .5, .75, .9]).round(1).to_dict())
    clipped = np.clip(t.urban_km2, URBAN_MIN_KM2, URBAN_MAX_KM2)
    print(f"of the sized: at the floor {(clipped == URBAN_MIN_KM2).mean():.1%}, at the cap {(clipped == URBAN_MAX_KM2).mean():.1%}")
    m = ov.set_index("site_id")
    s = t.set_index("site_id").urban_km2
    for col in ("spill_hours", "lta_spills"):
        x = m[col].reindex(s.index)
        ok = x.notna()
        print(f"Spearman rho of size with {col}: {spearmanr(s[ok], x[ok]).statistic:.3f} (n {int(ok.sum())})")
    if len(sys.argv) > 5:
        u = pd.read_parquet(sys.argv[5]).drop_duplicates("site_id").set_index("site_id").urban_km2.reindex(s.index)
        ok = u.notna()
        print(f"Spearman rho of size with built-up share: {spearmanr(s[ok], u[ok]).statistic:.3f} (n {int(ok.sum())})")
    print("sized share by company:", (ov.assign(sized=ov.site_id.isin(t.site_id)).groupby("company").sized.mean().round(3).to_dict()))
    print(f"{PLACEBOS} placebos written")


if __name__ == "__main__":
    main()
