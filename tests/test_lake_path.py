"""Lake path 'lake' (config.LAKE_PATH_MODE, docs/LAKE-PATH-TEST-2026-10.md): a WFD lake crossed between
an overflow and the spot is treated as the spot's own lake is; the default since 11 Oct 2026. Network-free: a few links
built in memory, in British National Grid metres, and lake polygons in place of data/processed/lakes.parquet."""

from __future__ import annotations

import math

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, box

from dipcast import config
from dipcast.model import transport
from dipcast.network.rivers import RiverNetwork, Snap

# West to east along y = 0: a river, a 4 km lake in two links, a river, a 1 km mill pond (lake-form, in no
# WFD polygon), a river, then a second lake and its outflow. The river spot is half way along r3.
LINKS = [
    ("r1", "a", "b", "inlandRiver", [(0, 0), (10_000, 0)]),
    ("L1", "b", "c", "lake", [(10_000, 0), (12_000, 0)]),
    ("L2", "c", "d", "lake", [(12_000, 0), (14_000, 0)]),
    ("r2", "d", "e", "inlandRiver", [(14_000, 0), (24_000, 0)]),
    ("p1", "e", "f", "lake", [(24_000, 0), (25_000, 0)]),
    ("r3", "f", "g", "inlandRiver", [(25_000, 0), (35_000, 0)]),
    ("Q1", "g", "h", "lake", [(35_000, 0), (37_000, 0)]),
    ("r4", "h", "i", "inlandRiver", [(37_000, 0), (40_000, 0)]),
]
LAKE_KM2 = 4.0        # the first lake's polygon, 4 km x 1 km
DOWN_KM2 = 2.0        # the second lake's, 2 km x 1 km
LAKES = gpd.GeoDataFrame({"lake_name": ["Upper", "Lower"], "area_km2": [LAKE_KM2, DOWN_KM2]},
                         geometry=[box(10_000, -500, 14_000, 500), box(35_000, -500, 37_000, 500)], crs=27700)


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
    rows = [("above", "r1", 0.5), ("in_lake", "L2", 0.5), ("below", "r2", 0.5)]
    return pd.DataFrame([{"site_id": s, "link_id": lid, "frac": f, "link_length": net.links.loc[lid, "length"],
                          "start_node": net.links.loc[lid, "start_node"]} for s, lid, f in rows])


def _river_pin() -> transport.PinLocation:
    return transport.PinLocation("river", 30_000, 0, Snap("r3", 0.5, 0.0, "inlandRiver", 30_000, 0),
                                 trace_node="f", trace_offset_m=5_000.0)


def _lake_pin() -> transport.PinLocation:
    return transport.PinLocation("lake", 36_000, 300, Snap("Q1", 0.5, 300.0, "lake", 36_000, 0), {"Q1"}, "h",
                                 trace_node="h", lake_area_km2=DOWN_KM2, lake_source="polygon")


def _trace(net, pin=None, **kw) -> pd.DataFrame:
    up = transport.upstream_overflows(net, pin or _river_pin(), _overflows(net),
                                      velocity_ms=kw.pop("velocity_ms", 0.5), **kw)
    return up.set_index("site_id")


def test_the_default_crosses_a_lake_on_the_way_as_a_lake(net):
    assert config.LAKE_PATH_MODE == "lake"
    assert _trace(net).equals(_trace(net, lake_path_mode="lake"))


def test_river_mode_walks_a_lake_on_the_way_as_river(net):
    up = _trace(net, lake_path_mode="river")
    assert list(up.columns) == list(_trace(net, lake_path_mode="lake").columns)
    # 5 km of r1, the 4 km lake, 10 km of r2, the 1 km pond and 5 km of r3, all at 0.5 m/s
    assert up.loc["above", "distance_m"] == pytest.approx(25_000)
    assert up.loc["above", "lake_distance_m"] == 0.0
    assert up.loc["above", "travel_h"] == pytest.approx(25_000 / 0.5 / 3600)


def test_a_wfd_lake_on_the_way_is_crossed_as_a_lake(net):
    old, new = _trace(net, lake_path_mode="river"), _trace(net, lake_path_mode="lake")
    # its 4 km leave the river distance for the lake distance; the distance along the network is the same
    assert new.loc["above", "distance_m"] == pytest.approx(21_000)
    assert new.loc["above", "lake_distance_m"] == pytest.approx(4_000)
    assert new.loc["above", "travel_h"] == pytest.approx((21_000 / 0.5 + 4_000 / config.LAKE_VELOCITY_MS) / 3600)
    # the spot's own-lake factor, for the lake's area
    assert new.loc["above", "dilution"] == pytest.approx(old.loc["above", "dilution"] / (1 + LAKE_KM2 / transport.LAKE_A0_KM2))
    assert new.loc["above", "decay"] == pytest.approx(10 ** (-new.loc["above", "travel_h"] / config.T90_HOURS))
    # an overflow below the lake is untouched, and the mill pond it passes stays river
    assert new.loc["below"].equals(old.loc["below"])


def test_an_overflow_on_the_lake_crosses_the_part_below_it(net):
    old, new = _trace(net, lake_path_mode="river"), _trace(net, lake_path_mode="lake")
    assert new.loc["in_lake", "lake_distance_m"] == pytest.approx(1_000)   # half of L2
    assert new.loc["in_lake", "distance_m"] == pytest.approx(old.loc["in_lake", "distance_m"] - 1_000)
    assert new.loc["in_lake", "dilution"] == pytest.approx(old.loc["in_lake", "dilution"] / (1 + LAKE_KM2 / transport.LAKE_A0_KM2))


def test_a_lake_pin_gets_its_own_lake_and_the_one_on_the_way(net):
    old, new = _trace(net, _lake_pin(), lake_path_mode="river"), _trace(net, _lake_pin(), lake_path_mode="lake")
    entry = math.hypot(35_000 - 36_000, 0 - 300)   # straight across the spot's lake from where the water enters
    assert old.loc["above", "distance_m"] == pytest.approx(30_000)
    assert old.loc["above", "lake_distance_m"] == pytest.approx(entry)
    assert new.loc["above", "distance_m"] == pytest.approx(26_000)
    assert new.loc["above", "lake_distance_m"] == pytest.approx(entry + 4_000)
    assert new.loc["above", "travel_h"] == pytest.approx((26_000 / 0.5 + (entry + 4_000) / config.LAKE_VELOCITY_MS) / 3600)
    # the spot's own lake already divides both; the lake on the way divides again
    assert new.loc["above", "dilution"] == pytest.approx(old.loc["above", "dilution"] / (1 + LAKE_KM2 / transport.LAKE_A0_KM2))
    assert new.loc["below"].equals(old.loc["below"])


def test_catchment_speed_drops_the_lake_from_the_reach_by_reach_time(net):
    new = _trace(net, velocity_mode="catchment", lake_path_mode="lake")

    def v(node: str) -> float:
        return float(transport.reach_velocity(net.upstream_m[node]))

    # r1's half at its own speed, the lake at lake speed, then r2, the pond, and r3 down to the spot
    want = 5_000 / v("b") + 4_000 / config.LAKE_VELOCITY_MS + 10_000 / v("e") + 1_000 / v("f") + 5_000 / v("g")
    assert new.loc["above", "travel_h"] == pytest.approx(want / 3600)
    lake = _trace(net, _lake_pin(), velocity_mode="catchment", lake_path_mode="lake")
    entry = math.hypot(1_000, 300)
    want = 5_000 / v("b") + 10_000 / v("e") + 1_000 / v("f") + 10_000 / v("g") + (4_000 + entry) / config.LAKE_VELOCITY_MS
    assert lake.loc["above", "travel_h"] == pytest.approx(want / 3600)
    # a gauge still scales the river part, not the lake part
    fast = _trace(net, velocity_mode="catchment", lake_path_mode="lake", velocity_ms=1.0)
    river_s = new.loc["above", "travel_h"] * 3600 - 4_000 / config.LAKE_VELOCITY_MS
    assert fast.loc["above", "travel_h"] * 3600 == pytest.approx(river_s / 2 + 4_000 / config.LAKE_VELOCITY_MS)


def test_each_lake_on_the_way_counts_once(net, monkeypatch):
    # Split the first lake's polygon in two, as Windermere's basins are: two lakes, two factors.
    two = gpd.GeoDataFrame({"lake_name": ["West", "East", "Lower"], "area_km2": [1.5, 2.5, DOWN_KM2]},
                           geometry=[box(10_000, -500, 11_500, 500), box(11_500, -500, 14_000, 500),
                                     box(35_000, -500, 37_000, 500)], crs=27700)
    monkeypatch.setattr(transport, "_lakes", lambda: two)
    # L1 has 1.5 km in West and 0.5 km in East: it goes to West; L2 is all East
    assert transport._wfd_lake_of(net, {"L1", "L2", "p1", "r1"}) == {"L1": (0, 1.5), "L2": (1, 2.5)}
    old, new = _trace(net, lake_path_mode="river"), _trace(net, lake_path_mode="lake")
    div = (1 + 1.5 / transport.LAKE_A0_KM2) * (1 + 2.5 / transport.LAKE_A0_KM2)
    assert new.loc["above", "dilution"] == pytest.approx(old.loc["above", "dilution"] / div)
    assert new.loc["in_lake", "dilution"] == pytest.approx(old.loc["in_lake", "dilution"] / (1 + 2.5 / transport.LAKE_A0_KM2))


def test_without_lake_polygons_nothing_changes(net, monkeypatch):
    monkeypatch.setattr(transport, "_lakes", lambda: None)
    assert _trace(net, lake_path_mode="lake").equals(_trace(net, lake_path_mode="river"))


def test_an_unknown_lake_path_option_is_refused(net):
    with pytest.raises(ValueError):
        _trace(net, lake_path_mode="pond")
