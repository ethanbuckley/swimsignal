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
    # length dilution: ((L_up at the outfall + L0) / (L_up at the spot + L0)) ** DILUTION_POWER
    # 25 km above the outfall's link against 30 km above the spot; nothing above the tributary's
    p = transport.DILUTION_POWER
    assert up.loc["on_m3", "dilution"] == pytest.approx(((25_000 + 5_000) / (30_000 + 5_000)) ** p)
    assert up.loc["on_t1", "dilution"] == pytest.approx((5_000 / (30_000 + 5_000)) ** p)


def test_reach_velocity_follows_jobson_at_the_median_flow():
    up_m = np.array([10, 100, 1000]) * transport.DRAINAGE_KM_PER_KM2 * 1000
    v = transport.reach_velocity(up_m)
    assert v == pytest.approx([0.126, 0.189, 0.292], abs=0.002)   # the values the comment quotes
    assert np.all(np.diff(v) > 0)
    assert transport.reach_velocity(0.0) == transport.VEL_MIN       # a headwater link is floored


def test_catchment_velocity_sums_length_over_speed_along_the_path(net):
    up = _trace(net, velocity_mode="catchment", velocity_ms=config.RIVER_VELOCITY_MS)   # the default speed: scale 1
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
    base = _trace(net, velocity_mode="catchment", velocity_ms=config.RIVER_VELOCITY_MS)
    fast = _trace(net, velocity_mode="catchment", velocity_ms=2 * config.RIVER_VELOCITY_MS)   # twice the default
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


# ---- dilution 'urban' (docs/URBAN-DILUTION-TEST-2026-10.md): each overflow's spill from its urban area


def _urban_overflows(net: RiverNetwork, areas: dict[str, float]) -> pd.DataFrame:
    ov = _overflows(net)
    ov["urban_km2"] = ov["site_id"].map(areas)
    return ov


def test_urban_dilution_scales_each_overflows_spill_by_its_urban_area(net):
    areas = {"on_m1": transport.URBAN_MEDIAN_KM2, "on_t1": 2.0, "on_m3": 0.2}
    up = transport.upstream_overflows(net, _pin(), _urban_overflows(net, areas), velocity_ms=0.5,
                                      dilution_mode="urban").set_index("site_id")
    q50 = float(transport.q50_m3s(transport.catchment_km2(net.upstream_m["c"] + 5_000.0)))
    for site, a in areas.items():
        q = transport.Q_SPILL_M3S * a / transport.URBAN_MEDIAN_KM2
        assert up.loc[site, "dilution"] == pytest.approx(q / (q + q50))
    # the median overflow gets the spill of mode 'flow'; a bigger town dilutes less
    flow = _trace(net, dilution_mode="flow")
    assert up.loc["on_m1", "dilution"] == pytest.approx(flow.loc["on_m1", "dilution"])
    assert up.loc["on_t1", "dilution"] > up.loc["on_m1", "dilution"] > up.loc["on_m3", "dilution"]
    # distance, travel time and decay do not change with the dilution rule
    flow = flow.loc[up.index]
    assert up["travel_h"].equals(flow["travel_h"]) and up["decay"].equals(flow["decay"])


def test_urban_area_is_clipped_and_a_missing_one_gets_the_median():
    lo, hi = transport.URBAN_MIN_KM2, transport.URBAN_MAX_KM2
    q = transport.urban_spill_m3s(np.array([0.0, lo, hi, 80.0]))
    assert q[0] == q[1] and q[2] == q[3]
    assert transport.urban_spill_m3s(transport.URBAN_MEDIAN_KM2) == pytest.approx(transport.Q_SPILL_M3S)
    a = transport.overflow_urban_km2(pd.DataFrame({"site_id": ["x", "y"], "urban_km2": [1.5, np.nan]}))
    assert a.tolist() == [1.5, transport.URBAN_MEDIAN_KM2]


def test_urban_area_comes_from_the_lookup_by_site_id(monkeypatch):
    monkeypatch.setattr(transport, "_urban_km2_by_site", lambda: pd.Series({"a": 3.0, "b": 0.4}))
    a = transport.overflow_urban_km2(pd.DataFrame({"site_id": ["b", "a", "new"]}))
    assert a.tolist() == [0.4, 3.0, transport.URBAN_MEDIAN_KM2]


def test_built_up_area_is_split_equally_between_its_overflows():
    import sys
    from pathlib import Path

    from pyproj import Transformer
    from shapely.geometry import box

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import make_overflow_urban_area as mk

    # Two built-up areas in British National Grid: a 2 km x 2 km town and a 1 km x 1 km village 10 km east.
    bua = gpd.GeoDataFrame({"BUA22CD": ["town", "village"]},
                           geometry=[box(400_000, 300_000, 402_000, 302_000), box(412_000, 300_000, 413_000, 301_000)],
                           crs=27700)
    to_ll = Transformer.from_crs(27700, 4326, always_xy=True).transform
    xy = {"t1": (401_000, 301_000), "t2": (401_500, 300_500), "t3": (402_500, 301_000),   # t3 is 500 m outside the town
          "v1": (412_500, 300_500), "far": (406_500, 306_000)}                            # far: 4 km from both
    ov = pd.DataFrame([{"site_id": s, "lon": to_ll(*p)[0], "lat": to_ll(*p)[1]} for s, p in xy.items()])
    out = mk.apportion(ov, bua).set_index("site_id")
    assert out.loc[["t1", "t2", "t3"], "urban_km2"].tolist() == pytest.approx([4 / 3] * 3)
    assert out.loc["v1", "urban_km2"] == pytest.approx(1.0) and out.loc["v1", "n_in_bua"] == 1
    assert pd.isna(out.loc["far", "bua22cd"]) and out.loc["far", "urban_km2"] == mk.FLOOR_KM2


def test_dilution_power_raises_the_capped_length_ratio(net):
    """docs/TRANSPORT-FIT-TEST-2026-10.md: an exponent on the length ratio, fitted to 0.5 (the square root)."""
    assert transport.DILUTION_POWER == 0.5
    assert _trace(net).equals(_trace(net, dilution_power=0.5))
    up = _trace(net, dilution_power=1.0)
    sq = _trace(net, dilution_power=2.0)
    assert sq["dilution"].to_numpy() == pytest.approx(up["dilution"].to_numpy() ** 2)
    assert sq["weight"].to_numpy() == pytest.approx(up["decay"].to_numpy() * up["dilution"].to_numpy() ** 2)
    assert sq["travel_h"].equals(up["travel_h"])   # only the dilution moves
