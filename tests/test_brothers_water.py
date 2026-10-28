"""Brothers Water (listed 28 Oct 2026): the spot sits in the EA's WFD lake polygon GB30229116 (data/processed/lakes.parquet,
OGL), at the polygon's representative point, so the build places it in that lake (transport._locate, step 1). The Lake
District park authority's lakes guide lists swimming there as allowed. Run against the real network on 27 Oct 2026, a
point in the same polygon was placed in the lake with no monitored overflow upstream (no spill forecast; the page
says "No monitored overflow found upstream"), 9 Open-Meteo calls a day and no new rain cell (docs/SPOT-ADDITIONS-2026-10.md)."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import geopandas as gpd
import pyproj

from dipcast import guides
from dipcast.model import transport
from dipcast.network.rivers import lonlat_to_bng

ROOT = Path(__file__).resolve().parents[1]
WFD = "GB30229116"


def _rows() -> list[dict]:
    return [r for f in ("spots.csv", "spots-osm.csv") for r in csv.DictReader((ROOT / f).open())]


def _row() -> dict:
    return next(r for r in _rows() if r["id"] == "brothers-water")


def _polygon():
    lakes = gpd.read_parquet(ROOT / "data" / "processed" / "lakes.parquet")
    return lakes[lakes["wb_id"] == WFD].iloc[0]


def test_the_spot_is_the_wfd_lakes_own_point_on_its_water():
    r, lake = _row(), _polygon()
    assert (r["kind"], r["source"], r["river"], r["area"]) == ("lake", "curated", "", "Cumbria and the Lake District")
    assert lake["lake_name"] == "Brothers Water"
    p = lake.geometry.representative_point()
    lon, lat = pyproj.Transformer.from_crs(27700, 4326, always_xy=True).transform(p.x, p.y)
    assert (round(lat, 5), round(lon, 5)) == (float(r["lat"]), float(r["lon"]))
    x, y = lonlat_to_bng(float(r["lon"]), float(r["lat"]))
    assert lake.geometry.distance(gpd.points_from_xy([x], [y])[0]) == 0   # on the water


def test_the_build_finds_this_lake_at_the_spot_by_place_and_by_name():
    r = _row()
    x, y = lonlat_to_bng(float(r["lon"]), float(r["lat"]))
    assert transport._lake_polygon_at(x, y)["wb_id"] == WFD
    assert transport._named_lake_polygon(x, y, r["name"])["wb_id"] == WFD


def test_no_listed_spot_within_1_km_on_the_same_water():
    r = _row()
    km = lambda a, b, c, d: 2 * 6371 * math.asin(math.sqrt(math.sin(math.radians(c - a) / 2) ** 2
                                                          + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(math.radians(d - b) / 2) ** 2))
    near = sorted((km(float(r["lat"]), float(r["lon"]), float(o["lat"]), float(o["lon"])), o["id"]) for o in _rows() if o["id"] != r["id"])
    assert near[0][0] > 4.0, near[0]   # the nearest is on Ullswater, a different lake


def test_its_guide_loads_with_the_park_authoritys_words_on_swimming():
    found, warnings = guides.load_guides({"brothers-water"}, root=ROOT / "guides")
    assert not [w for w in warnings if "brothers-water" in w], warnings
    g = found["brothers-water"]
    by = {f["topic"]: f for f in g["facts"]}
    assert set(by) == {"parking", "toilets", "rules"}
    assert by["rules"]["source"].startswith("https://lakedistrict.gov.uk/") and "swimming at Brotherswater as allowed" in by["rules"]["text"]
    assert all(f["status"] == "confirmed" for f in g["facts"]) and g["checked"] == "2026-10-28"
