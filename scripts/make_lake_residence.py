"""Residence times of WFD lakes, for lake path 'residence' (docs/LAKE-RESIDENCE-TEST-2026-10.md).

    python scripts/make_lake_residence.py [--attrs hl_attrs.json --polys hl_polys.geojson]

Source: HydroLAKES v1.0 (Messager, M.L., Lehner, B., Grill, G., Nedeva, I., Schmitt, O. (2016): Estimating
the volume and age of water stored in global lakes using a geo-statistical approach. Nature
Communications 7: 13603, doi:10.1038/ncomms13603), licence CC BY 4.0 (https://www.hydrosheds.org/products/hydrolakes).
Its residence time `Res_time` (days) is the lake's volume `Vol_total` over its long-term mean outflow
`Dis_avg`. For British lakes the volume is almost always modelled from the lake's area and the slope
of the land around it (`Vol_src` 3), not measured; `Dis_avg` is a global model's (WaterGAP) mean flow.

The attributes and polygons are read from a public ArcGIS Online copy of HydroLAKES (QUERY below),
the United Kingdom only, unless files of an earlier read are given. It has not been checked against
the HydroSHEDS download; for four Lake District lakes its volumes are within a factor of two of the
UK Lakes Portal's (docs/LAKE-RESIDENCE-TEST-2026-10.md).

Each WFD lake (data/processed/lakes.parquet) takes the HydroLAKES lake whose polygon holds a point
inside it (shapely.point_on_surface). Where one HydroLAKES lake holds part of a WFD lake's area, or
several WFD lakes (Windermere's two basins are one HydroLAKES lake), the WFD lake's residence time is
the HydroLAKES time times min(1, WFD area / HydroLAKES area): its share of the volume, emptied by
the whole lake's outflow. A WFD lake with no HydroLAKES lake (most under 10 ha, and Elter Water) is
left out, and lake path 'residence' crosses it as lake path 'lake' does.

Writes data/raw/lake_residence.csv: wb_id, lake_name, wfd_area_km2, hylak_id, hl_area_km2, hl_vol_mcm,
hl_vol_src, hl_depth_avg_m, hl_dis_avg_m3s, hl_res_time_d, hl_wshd_area_km2, wfd_in_hl, area_share,
res_time_d.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from dipcast import config
from dipcast.ingest.lakes import load_lakes

QUERY = ("https://services5.arcgis.com/caWDr9qv9f34KIAZ/arcgis/rest/services/HydroLAKES_Polygons/"
         "FeatureServer/0/query")
WHERE = "Country = 'United Kingdom'"
OUT = config.RAW / "lake_residence.csv"


def _query(params: dict) -> list:
    rows, off = [], 0
    while True:
        q = {**params, "where": WHERE, "resultOffset": off, "resultRecordCount": 2000, "orderByFields": "Hylak_id"}
        req = urllib.request.Request(QUERY + "?" + urllib.parse.urlencode(q), headers={"User-Agent": config.USER_AGENT})
        d = json.loads(urllib.request.urlopen(req, timeout=180).read())
        feats = d.get("features", [])
        rows += feats
        more = d.get("exceededTransferLimit") or d.get("properties", {}).get("exceededTransferLimit")
        if not feats or not more:
            return rows
        off += len(feats)


def fetch() -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    attrs = pd.DataFrame([f["attributes"] for f in _query({"outFields": "*", "returnGeometry": "false", "f": "json"})])
    polys = gpd.GeoDataFrame.from_features(_query({"outFields": "Hylak_id", "returnGeometry": "true", "outSR": 27700,
                                                   "maxAllowableOffset": 10, "f": "geojson"}), crs=27700)
    return attrs, polys


def build(attrs: pd.DataFrame, polys: gpd.GeoDataFrame, wfd: gpd.GeoDataFrame) -> pd.DataFrame:
    polys = polys[["Hylak_id", "geometry"]].copy()
    polys["geometry"] = shapely.make_valid(polys.geometry.values)
    hl = polys.merge(attrs[["Hylak_id", "Lake_area", "Vol_total", "Vol_src", "Depth_avg", "Dis_avg", "Res_time",
                            "Wshd_area"]], on="Hylak_id")
    pts = wfd[["wb_id", "lake_name", "area_km2", "geometry"]].copy()
    pts["geometry"] = shapely.point_on_surface(shapely.make_valid(wfd.geometry.values))
    j = gpd.sjoin(pts, hl, predicate="within", how="inner")
    if not j.index.is_unique:
        raise ValueError("a WFD lake's point lies in two HydroLAKES polygons")
    j["wfd_in_hl"] = j.groupby("Hylak_id")["wb_id"].transform("count")
    j["area_share"] = (j["area_km2"] / j["Lake_area"]).clip(upper=1.0)
    j["res_time_d"] = (j["Res_time"] * j["area_share"]).where(j["Res_time"] > 0)
    out = j.rename(columns={"area_km2": "wfd_area_km2", "Hylak_id": "hylak_id", "Lake_area": "hl_area_km2",
                            "Vol_total": "hl_vol_mcm", "Vol_src": "hl_vol_src", "Depth_avg": "hl_depth_avg_m",
                            "Dis_avg": "hl_dis_avg_m3s", "Res_time": "hl_res_time_d", "Wshd_area": "hl_wshd_area_km2"})
    cols = ["wb_id", "lake_name", "wfd_area_km2", "hylak_id", "hl_area_km2", "hl_vol_mcm", "hl_vol_src", "hl_depth_avg_m",
            "hl_dis_avg_m3s", "hl_res_time_d", "hl_wshd_area_km2", "wfd_in_hl", "area_share", "res_time_d"]
    out = out[cols].sort_values("wb_id").reset_index(drop=True)
    out["hylak_id"] = out["hylak_id"].astype(int)
    out["hl_vol_src"] = out["hl_vol_src"].astype(int)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attrs", help="HydroLAKES attributes, a JSON list of records (from an earlier read)")
    ap.add_argument("--polys", help="HydroLAKES polygons in EPSG:27700, GeoJSON features (from an earlier read)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if a.attrs and a.polys:
        attrs = pd.DataFrame(json.loads(Path(a.attrs).read_text()))
        f = json.loads(Path(a.polys).read_text())
        polys = gpd.GeoDataFrame.from_features(f["features"] if isinstance(f, dict) else f, crs=27700)
    else:
        attrs, polys = fetch()
    out = build(attrs, polys, load_lakes())
    out.to_csv(a.out, index=False, float_format="%.6g")
    print(f"{len(out)} WFD lakes with a HydroLAKES lake; {out.res_time_d.notna().sum()} with a residence time")


if __name__ == "__main__":
    main()
