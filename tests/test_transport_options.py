"""The two transport options from the 9 Oct 2026 review: travel speed per reach from catchment area
(velocity 'catchment') and dilution by the spot's estimated median flow (dilution 'flow'). Both are
off by default. Network-free: a few links built in memory, in British National Grid metres."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from dipcast import config
from dipcast.model import transport
from dipcast.network.rivers import RiverNetwork, Snap

# A main river runs east along y = 0 in three 10 km links, m1 -> m2 -> m3. A 5 km tributary t1
# comes down from the north and joins at x = 10 km. The spot is half way along m3.
LINKS = [
    ("m1", "a", "b", [(0, 0), (10_000, 0)]),
    ("m2", "b", "c", [(10_000, 0), (20_000, 0)]),
    ("m3", "c", "d", [(20_000, 0), (30_000, 0)]),
    ("t1", "t", "b", [(10_000, 5_000), (10_000, 0)]),
]


@pytest.fixture(scope="module")
def net() -> RiverNetwork:
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": "inlandRiver", "fictitious": False,
          "watercourse_name": "Main", "watercourse_name_alternative": None, "start_node": s, "end_node": e,
          "geometry": LineString(xy)} for i, s, e, xy in LINKS], crs=27700)
    return RiverNetwork.from_links(gdf)


def _overflows(net: RiverNetwork) -> pd.DataFrame:
    rows = [("on_m1", "m1", 0.5), ("on_t1", "t1", 0.2), ("on_m3", "m3", 0.25)]
    return pd.DataFrame([{"site_id": s, "link_id": lid, "frac": f, "link_length": net.links.loc[lid, "length"],
                          "start_node": net.links.loc[lid, "start_node"]} for s, lid, f in rows])


def _pin() -> transport.PinLocation:
    return transport.PinLocation("river", 25_000, 0, Snap("m3", 0.5, 0.0, "inlandRiver", 25_000, 0),
                                 trace_node="c", trace_offset_m=5_000.0)


def _trace(net, **kw) -> pd.DataFrame:
    up = transport.upstream_overflows(net, _pin(), _overflows(net), velocity_ms=kw.pop("velocity_ms", 0.5), **kw)
    return up.set_index("site_id")


def test_defaults_are_the_rule_in_use(net):
    assert config.VELOCITY_MODE == "fixed" and config.DILUTION_MODE == "length"
    up = _trace(net)
    assert up.equals(_trace(net, velocity_mode="fixed", dilution_mode="length"))
    # 0.5 m/s on every reach: on_m1 is 5 + 10 + 5 km from the spot
    assert up.loc["on_m1", "distance_m"] == pytest.approx(20_000)
    assert up.loc["on_m1", "travel_h"] == pytest.approx(20_000 / 0.5 / 3600)
    # length dilution: (L_up at the outfall + L0) / (L_up at the spot + L0)
    # 25 km above the outfall's link against 30 km above the spot; nothing above the tributary's
    assert up.loc["on_m3", "dilution"] == pytest.approx((25_000 + 5_000) / (30_000 + 5_000))
    assert up.loc["on_t1", "dilution"] == pytest.approx(5_000 / (30_000 + 5_000))


def test_reach_velocity_follows_jobson_at_the_median_flow():
    up_m = np.array([10, 100, 1000]) * transport.DRAINAGE_KM_PER_KM2 * 1000
    v = transport.reach_velocity(up_m)
    assert v == pytest.approx([0.126, 0.189, 0.292], abs=0.002)   # the values the comment quotes
    assert np.all(np.diff(v) > 0)
    assert transport.reach_velocity(0.0) == transport.VEL_MIN       # a headwater link is floored


def test_catchment_velocity_sums_length_over_speed_along_the_path(net):
    up = _trace(net, velocity_mode="catchment")
    v = {lid: float(transport.reach_velocity(net.upstream_m[net.links.loc[lid, "end_node"]]))
         for lid in ("m1", "m2", "m3")}
    want = (5_000 / v["m1"] + 10_000 / v["m2"] + 5_000 / v["m3"]) / 3600
    assert up.loc["on_m1", "travel_h"] == pytest.approx(want)
    assert up.loc["on_m3", "travel_h"] == pytest.approx(2_500 / v["m3"] / 3600)
    # a slower small river: the tributary's own reach is slower than the main river below the confluence
    v_t1 = float(transport.reach_velocity(net.upstream_m["b"]))
    assert up.loc["on_t1", "travel_h"] == pytest.approx((4_000 / v_t1 + 10_000 / v["m2"] + 5_000 / v["m3"]) / 3600)
    # distance and dilution do not change with the speed rule
    fixed = _trace(net)
    assert up["distance_m"].equals(fixed["distance_m"]) and up["dilution"].equals(fixed["dilution"])


def test_a_gauge_still_scales_the_catchment_speeds(net):
    base = _trace(net, velocity_mode="catchment")
    fast = _trace(net, velocity_mode="catchment", velocity_ms=1.0)   # twice the default 0.5 m/s
    assert fast["travel_h"].to_numpy() == pytest.approx(base["travel_h"].to_numpy() / 2)


def test_flow_dilution_is_the_same_for_every_overflow_at_a_spot(net):
    up = _trace(net, dilution_mode="flow")
    spot_up = net.upstream_m["c"] + 5_000.0
    assert up["dilution"].nunique() == 1
    assert up["dilution"].iloc[0] == pytest.approx(float(transport.flow_dilution(spot_up)))
    # a spot with L0 of network halves a spill, as the length rule does at the head of a network
    assert transport.flow_dilution(transport.L0_M) == pytest.approx(0.5)
    assert transport.flow_dilution(1e6) < transport.flow_dilution(1e5) < 0.5


def test_an_unknown_option_is_refused(net):
    with pytest.raises(ValueError):
        _trace(net, velocity_mode="gauge")
