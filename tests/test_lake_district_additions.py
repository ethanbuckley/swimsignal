"""Lake District lakes listed on 28 Oct 2026 from the park authority's lakes guide ("Swimming: yes"): Brothers Water,
Loweswater and Bassenthwaite Lake. Each spot is the representative point of its EA WFD lake polygon
(data/processed/lakes.parquet, OGL), so the build places it in that lake. Each was placed and costed on the real
network on 27 Oct 2026 (scripts/spot_cost.py) at a point in the same polygon and rain cell, which the tests check, so
those results hold for the listed point (docs/SPOT-ADDITIONS-2026-10.md)."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import geopandas as gpd
import pyproj
import pytest
from shapely.geometry import Point

from dipcast import guides
from dipcast.model import transport
from dipcast.network.rivers import lonlat_to_bng

ROOT = Path(__file__).resolve().parents[1]
GUIDE = "https://lakedistrict.gov.uk/explore/things-to-do/on-the-water/lakes-activities-guide/"

# id, WFD id, WFD name, where spot_cost placed it on 27 Oct, its rain cell, the guide's words, the guide's topics
LAKES = [
    ("brothers-water", "GB30229116", "Brothers Water", (54.50815, -2.92426), (54.5, -2.9),
     "swimming at Brotherswater as allowed", {"parking", "toilets", "rules"}),
    ("loweswater", "GB31228986", "Loweswater", (54.58302, -3.35446), (54.6, -3.4),
     "swimming at Loweswater as allowed", {"parking", "path", "rules"}),
    ("bassenthwaite", "GB31228847", "Bassenthwaite Lake", (54.65263, -3.21363), (54.7, -3.2),
     "swimming at Bassenthwaite as allowed", {"rules"}),
]
IDS = [x[0] for x in LAKES]


def _rows() -> list[dict]:
    return [r for f in ("spots.csv", "spots-osm.csv") for r in csv.DictReader((ROOT / f).open())]


@pytest.fixture(scope="module")
def lakes():
    return gpd.read_parquet(ROOT / "data" / "processed" / "lakes.parquet").set_index("wb_id")


def _km(a, b, c, d):
    return 2 * 6371 * math.asin(math.sqrt(math.sin(math.radians(c - a) / 2) ** 2
                                          + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(math.radians(d - b) / 2) ** 2))


@pytest.mark.parametrize("sid, wfd, name, costed, cell, words, topics", LAKES, ids=IDS)
def test_lake_spot(lakes, sid, wfd, name, costed, cell, words, topics):
    r = next(x for x in _rows() if x["id"] == sid)
    lat, lon = float(r["lat"]), float(r["lon"])
    assert (r["kind"], r["source"], r["river"], r["area"]) == ("lake", "curated", "", "Cumbria and the Lake District")
    # The spot is its WFD lake's representative point, on the water.
    poly = lakes.loc[wfd]
    assert poly["lake_name"] == name
    p = poly.geometry.representative_point()
    assert (round(lat, 5), round(lon, 5)) == tuple(round(v, 5) for v in reversed(
        pyproj.Transformer.from_crs(27700, 4326, always_xy=True).transform(p.x, p.y)))
    x, y = lonlat_to_bng(lon, lat)
    assert poly.geometry.contains(Point(x, y))
    # The build finds that lake at the spot, by place and by name.
    assert transport._lake_polygon_at(x, y)["wb_id"] == wfd
    assert transport._named_lake_polygon(x, y, r["name"])["wb_id"] == wfd
    # The costed point is the same lake and the same 0.1 degree rain cell, so its placement and cost hold.
    assert poly.geometry.contains(Point(*lonlat_to_bng(costed[1], costed[0])))
    assert (round(lat * 10) / 10, round(lon * 10) / 10) == (round(costed[0] * 10) / 10, round(costed[1] * 10) / 10) == cell
    # No listed spot within 1 km: the nearest is on another lake.
    near = min(_km(lat, lon, float(o["lat"]), float(o["lon"])) for o in _rows() if o["id"] != sid)
    assert near > 1.0
    # The guide: the park authority's words on swimming, confirmed; no entry point claimed.
    found, warnings = guides.load_guides({sid}, root=ROOT / "guides")
    assert not [w for w in warnings if sid in w], warnings
    by = {f["topic"]: f for f in found[sid]["facts"]}
    # Besides these, the park authority's rules for boats and boards ("paddle", from its lakes activities guide, 30 Oct 2026).
    assert set(by) - {"paddle"} == topics and not {"entry", "exit"} & set(by)
    assert "paddle" not in by or by["paddle"]["source_name"] == "Lake District National Park Authority"
    assert by["rules"]["source"] == GUIDE and words in by["rules"]["text"]
    assert all(f["status"] == "confirmed" for f in found[sid]["facts"]) and found[sid]["checked"] == "2026-10-28"


@pytest.mark.parametrize("sid, topics", [("crummock-water", {"parking", "rules"}), ("wastwater", {"parking", "fees", "toilets", "rules"})])
def test_guides_added_for_listed_lakes(sid, topics):
    # Guides for two listed lakes that had none (28 Oct 2026): the park authority's rules and the National Trust's car parks.
    found, warnings = guides.load_guides({sid}, root=ROOT / "guides")
    assert not [w for w in warnings if sid in w], warnings
    by = {f["topic"]: f for f in found[sid]["facts"]}
    # Besides these, the park authority's rules for boats and boards ("paddle", from its lakes activities guide, 30 Oct 2026).
    assert set(by) - {"paddle"} == topics and not {"entry", "exit"} & set(by)
    assert "paddle" not in by or by["paddle"]["source_name"] == "Lake District National Park Authority"
    assert by["rules"]["source"] == GUIDE and "as allowed" in by["rules"]["text"]
    assert by["parking"]["source"].startswith("https://www.nationaltrust.org.uk/")
    assert all(f["status"] == "confirmed" for f in found[sid]["facts"]) and found[sid]["checked"] == "2026-10-28"
