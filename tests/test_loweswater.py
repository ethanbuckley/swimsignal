"""Loweswater (listed 28 Oct 2026): the spot sits in the EA's WFD lake polygon GB31228986 (data/processed/lakes.parquet,
OGL), at the polygon's representative point, so the build places it in that lake. The Lake District park authority's
lakes guide lists swimming there as allowed. Run against the real network on 27 Oct 2026, at a point in the same
polygon and rain cell, it was placed in the lake with no monitored overflow upstream (no spill forecast), one new rain
cell that click-anywhere already asks for, and 19 Open-Meteo calls a day (docs/SPOT-ADDITIONS-2026-10.md)."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import geopandas as gpd
import pyproj
from shapely.geometry import Point

from dipcast import guides
from dipcast.model import transport
from dipcast.network.rivers import lonlat_to_bng

ROOT = Path(__file__).resolve().parents[1]
WFD = "GB31228986"
COSTED = (54.58302, -3.35446)   # where spot_cost placed and costed it on 27 Oct 2026


def _rows() -> list[dict]:
    return [r for f in ("spots.csv", "spots-osm.csv") for r in csv.DictReader((ROOT / f).open())]


def _row() -> dict:
    return next(r for r in _rows() if r["id"] == "loweswater")


def _polygon():
    lakes = gpd.read_parquet(ROOT / "data" / "processed" / "lakes.parquet")
    return lakes[lakes["wb_id"] == WFD].iloc[0]


def test_the_spot_is_the_wfd_lakes_own_point_on_its_water():
    r, lake = _row(), _polygon()
    assert (r["kind"], r["source"], r["river"], r["area"]) == ("lake", "curated", "", "Cumbria and the Lake District")
    assert lake["lake_name"] == "Loweswater"
    p = lake.geometry.representative_point()
    lon, lat = pyproj.Transformer.from_crs(27700, 4326, always_xy=True).transform(p.x, p.y)
    assert (round(lat, 5), round(lon, 5)) == (float(r["lat"]), float(r["lon"]))
    assert lake.geometry.contains(Point(*lonlat_to_bng(float(r["lon"]), float(r["lat"]))))


def test_the_costed_point_is_the_same_lake_and_rain_cell():
    # So the 27 Oct placement and cost hold for the listed point.
    r, lake = _row(), _polygon()
    assert lake.geometry.contains(Point(*lonlat_to_bng(COSTED[1], COSTED[0])))
    cell = lambda lat, lon: (round(lat * 10) / 10, round(lon * 10) / 10)
    assert cell(float(r["lat"]), float(r["lon"])) == cell(*COSTED) == (54.6, -3.4)


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
    assert near[0][0] > 4.0, near[0]   # the nearest is Crummock Water, a different lake


def test_its_guide_loads_with_the_park_authoritys_words_on_swimming():
    found, warnings = guides.load_guides({"loweswater"}, root=ROOT / "guides")
    assert not [w for w in warnings if "loweswater" in w], warnings
    by = {f["topic"]: f for f in found["loweswater"]["facts"]}
    assert set(by) == {"parking", "rules"}
    assert by["rules"]["source"].startswith("https://lakedistrict.gov.uk/") and "swimming at Loweswater as allowed" in by["rules"]["text"]
    assert by["parking"]["source"].startswith("https://www.nationaltrust.org.uk/")
