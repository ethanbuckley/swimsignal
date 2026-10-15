"""Lake distance 'water' (off by default; docs/LAKE-DISTANCE-2026-10.md): a lake spot's distance from where an
overflow's water enters its lake is the shortest path inside the lake's WFD polygons, not the straight line.
Network-free: a river into an L-shaped lake whose two arms meet at a right angle, the spot at the end of the
second arm, so the straight line from the entry cuts across the land inside the bend."""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Polygon, box

from dipcast import config
from dipcast.model import lake_water, transport
from dipcast.network.rivers import RiverNetwork, Snap

LINKS = [
    ("r1", "a", "b", "inlandRiver", [(-5_000, 0), (0, 0)]),
    ("L1", "b", "c", "lake", [(0, 0), (3_750, 0)]),
    ("L2", "c", "d", "lake", [(3_750, 0), (3_750, 4_000)]),
    ("r2", "d", "e", "inlandRiver", [(3_750, 4_000), (3_750, 6_000)]),
]
# The L: an arm along y = 0 and one up x = 3,750, each 500 m wide. Its inner corner is (3,500, 250).
L_SHAPE = box(0, -250, 4_000, 250).union(box(3_500, -250, 4_000, 4_000))
LAKES = gpd.GeoDataFrame({"wb_id": ["GBL"], "lake_name": ["Ell Water"], "area_km2": [L_SHAPE.area / 1e6]},
                         geometry=[L_SHAPE], crs=27700)
PIN = (3_750, 3_800)
CORNER = (3_500, 250)


@pytest.fixture(scope="module")
def net() -> RiverNetwork:
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": f, "fictitious": False, "watercourse_name": "Beck",
          "watercourse_name_alternative": None, "start_node": s, "end_node": e, "geometry": LineString(xy)}
         for i, s, e, f, xy in LINKS], crs=27700)
    return RiverNetwork.from_links(gdf)


@pytest.fixture(autouse=True)
def lakes(monkeypatch):
    monkeypatch.setattr(transport, "_lakes", lambda: LAKES)


def _overflows(net: RiverNetwork) -> pd.DataFrame:
    return pd.DataFrame([{"site_id": "beck", "link_id": "r1", "frac": 0.5, "link_length": net.links.loc["r1", "length"],
                          "start_node": net.links.loc["r1", "start_node"]}])


def _pin(x: float = PIN[0], y: float = PIN[1], link: str = "L2", frac: float = 0.95) -> transport.PinLocation:
    return transport.PinLocation("lake", x, y, Snap(link, frac, 0.0, "lake", x, y), {"L1", "L2"}, "d",
                                 trace_node="d", lake_area_km2=float(LAKES.area_km2[0]), lake_source="polygon")


def _trace(net, pin=None, **kw) -> pd.Series:
    up = transport.upstream_overflows(net, pin or _pin(), _overflows(net), velocity_ms=0.5, **kw)
    return up.set_index("site_id").loc["beck"]


def test_the_default_is_the_straight_line(net):
    assert config.LAKE_DISTANCE_MODE == "line"
    r = _trace(net)
    assert r["lake_distance_m"] == pytest.approx(math.hypot(*PIN))
    assert r["lake_distance_m"] == pytest.approx(_trace(net, lake_distance_mode="line")["lake_distance_m"])


def test_water_goes_round_the_bend(net):
    line, water = _trace(net, lake_distance_mode="line"), _trace(net, lake_distance_mode="water")
    via = math.dist((0, 0), CORNER) + math.dist(CORNER, PIN)
    assert water["lake_distance_m"] == pytest.approx(via, abs=1.0)
    assert water["lake_distance_m"] > line["lake_distance_m"] + 1_000   # the line cuts the bend
    # Only the lake distance changes: the river part, the dilution and the rule for travel and die-off stay.
    extra_h = (water["lake_distance_m"] - line["lake_distance_m"]) / config.LAKE_VELOCITY_MS / 3600
    assert water["distance_m"] == pytest.approx(line["distance_m"])
    assert water["dilution"] == pytest.approx(line["dilution"])
    assert water["travel_h"] == pytest.approx(line["travel_h"] + extra_h)
    assert water["weight"] == pytest.approx(line["weight"] * 10 ** (-extra_h / config.T90_HOURS))


def test_a_line_that_stays_in_the_water_is_kept(net):
    pin = _pin(2_000, 100, "L1", 0.5)
    assert (_trace(net, pin, lake_distance_mode="water")["lake_distance_m"]
            == pytest.approx(_trace(net, pin, lake_distance_mode="line")["lake_distance_m"]))


def test_a_lake_with_no_polygon_keeps_the_line(net, monkeypatch):
    monkeypatch.setattr(transport, "_lakes", lambda: LAKES.iloc[0:0])
    pin = _pin()
    pin.lake_source = "centreline"
    assert _trace(net, pin, lake_distance_mode="water")["lake_distance_m"] == pytest.approx(math.hypot(*PIN))


def test_a_pin_on_the_shore_adds_its_leg(net):
    # 100 m beyond the end of the second arm, outside the polygon.
    pin = _pin(3_750, 4_100)
    via = math.dist((0, 0), CORNER) + math.dist(CORNER, (3_750, 4_000)) + 100
    assert _trace(net, pin, lake_distance_mode="water")["lake_distance_m"] == pytest.approx(via, abs=1.0)


def test_unknown_mode_is_refused(net):
    with pytest.raises(ValueError):
        _trace(net, lake_distance_mode="centreline")


def test_round_an_island_and_never_shorter_than_the_line():
    # A 2 km square lake with a 1 km island in the middle: from the middle of the west shore to the middle of
    # the east shore the way is round the island, past two of its corners.
    lake = Polygon(box(0, 0, 2_000, 2_000).exterior.coords, [box(500, 500, 1_500, 1_500).exterior.coords])
    w = lake_water.water((lake,))
    d = lake_water.water_distance(w, 10, 1_000, 1_990, 1_000)
    assert d == pytest.approx(2 * math.dist((10, 1_000), (500, 1_500)) + 1_000, abs=1.0)
    rng = np.random.default_rng(0)
    for ax, ay, bx, by in rng.uniform(0, 2_000, size=(200, 4)):
        assert lake_water.water_distance(w, ax, ay, bx, by) >= math.hypot(ax - bx, ay - by) - 1e-6
