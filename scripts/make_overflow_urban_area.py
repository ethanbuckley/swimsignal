"""Urban area apportioned to each storm overflow: data/processed/overflow_urban_area.parquet, read by
the transport option DIPCAST_DILUTION_MODE=urban (model/transport.py). Off by default, so the site
build does not need this file.

    uv run python scripts/make_overflow_urban_area.py              # downloads the boundaries (about 100 MB)
    uv run python scripts/make_overflow_urban_area.py bua.geojson  # or reads them already downloaded

Why: an outside review of the method (9 Oct 2026) said dilution needs a spill size, and suggested the
urban area that drains to each overflow. We have no sewer catchments, so the urban area is
apportioned by a fixed rule, stated in docs/URBAN-DILUTION-TEST-2026-10.md before any evaluation:

1. Each overflow in the overflow table with coordinates (snapped or not: they all drain a town's
   sewers) gets the nearest built-up area within ASSIGN_M of it, in British National Grid.
2. A built-up area's land area is split equally between the overflows it gets.
3. An overflow with no built-up area within ASSIGN_M gets FLOOR_KM2, half the smallest built-up area.

The table keeps the raw shares. transport.urban_spill_m3s clips them to [0.1, 6.0] km².

Source: Office for National Statistics, Built Up Areas (December 2022) Boundaries GB BGG, made from
OS Open Built Up Areas on a 25 m grid (https://www.arcgis.com/home/item.html?id=ad30b234308f4b02b4bb9b0f4766f7bb).
Open Government Licence v3.0 (https://www.ons.gov.uk/methodology/geography/licences), which allows
publishing derived results. Credit: "Source: Office for National Statistics licensed under the Open
Government Licence v.3.0. Contains OS data © Crown copyright and database right 2022."

What it is not: a built-up area is land with buildings, not impervious area connected to a combined
sewer, and an equal split ignores which overflow serves which part of a town.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import httpx
import numpy as np
import pandas as pd

from dipcast import config

LAYER = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/BUA_2022_GB/FeatureServer/0"
OUT = config.PROCESSED / "overflow_urban_area.parquet"
PAGE = 1000
ASSIGN_M = 1000.0    # an overflow belongs to the nearest built-up area within this distance
FLOOR_KM2 = 0.1      # urban area of an overflow with no built-up area within ASSIGN_M


def download() -> dict:
    """Every built-up area polygon in British National Grid, PAGE at a time. Not saved: only the
    per-overflow table is kept."""
    feats: list[dict] = []
    with httpx.Client(timeout=300, follow_redirects=True) as c:
        while True:
            r = c.get(f"{LAYER}/query", params={"where": "1=1", "outFields": "BUA22CD,BUA22NM", "outSR": 27700,
                                               "orderByFields": "OBJECTID", "resultOffset": len(feats),
                                               "resultRecordCount": PAGE, "f": "geojson"})
            r.raise_for_status()
            page = r.json().get("features", [])
            feats += page
            if len(page) < PAGE:
                break
    return {"type": "FeatureCollection", "features": feats}


def apportion(ov: pd.DataFrame, bua: gpd.GeoDataFrame, assign_m: float = ASSIGN_M,
              floor_km2: float = FLOOR_KM2) -> pd.DataFrame:
    """One row per overflow: site_id, bua22cd, bua_dist_m, bua_km2, n_in_bua, urban_km2. `ov` needs
    site_id, lat and lon; `bua` needs BUA22CD and polygons in a metre grid."""
    pts = gpd.GeoDataFrame(ov[["site_id"]].reset_index(drop=True),
                           geometry=gpd.points_from_xy(ov["lon"], ov["lat"]), crs=4326).to_crs(bua.crs)
    b = bua[["BUA22CD", "geometry"]].copy()
    b["bua_km2"] = b.geometry.area / 1e6
    hit = gpd.sjoin_nearest(pts, b, how="left", max_distance=assign_m, distance_col="bua_dist_m")
    hit = hit[~hit.index.duplicated(keep="first")]          # a tie: one area per overflow
    out = pd.DataFrame({"site_id": hit["site_id"], "bua22cd": hit["BUA22CD"],
                        "bua_dist_m": hit["bua_dist_m"], "bua_km2": hit["bua_km2"]})
    out["n_in_bua"] = out["bua22cd"].map(out["bua22cd"].value_counts()).fillna(0).astype(int)
    out["urban_km2"] = np.where(out["bua22cd"].notna(), out["bua_km2"] / out["n_in_bua"].clip(lower=1), floor_km2)
    return out.reset_index(drop=True)


def main() -> None:
    doc = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else download()
    bua = gpd.GeoDataFrame.from_features(doc["features"], crs=27700)
    ov = pd.read_parquet(config.state_read("overflows.parquet"))
    ov = ov.dropna(subset=["lat", "lon"]).drop_duplicates("site_id")
    out = apportion(ov, bua)
    out.to_parquet(OUT, index=False)
    a = out["urban_km2"]
    print(f"{len(bua)} built-up areas, smallest {bua.geometry.area.min() / 1e6:.3f} km²")
    print(f"{len(out)} overflows: {out['bua22cd'].notna().sum()} within {ASSIGN_M:g} m of a built-up area, "
          f"{out['bua22cd'].isna().sum()} given {FLOOR_KM2:g} km²")
    print(f"urban_km2: median {a.median():.4f} (transport.URBAN_MEDIAN_KM2), quartiles {a.quantile(0.25):.4f} "
          f"to {a.quantile(0.75):.4f}, 99th percentile {a.quantile(0.99):.2f}, max {a.max():.2f}")
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
