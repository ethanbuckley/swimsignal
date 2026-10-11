"""The two outfall options of docs/OUTFALL-CHANNEL-TEST-2026-10.md, both off by default: outfall channel
"junction" (transport._outfall_junction) and first snap "named" (overflows.prefer_named). Network-free:
a few links built in memory, in British National Grid metres."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

from dipcast import config
from dipcast.model import transport
from dipcast.network.rivers import RiverNetwork, Snap, bng_to_lonlat
from dipcast.overflows import prefer_named

# A main river runs east along y = 0: m1 (30 km), then m2 and m3 (10 km each). The spot is half way along
# m3. Into the start of m2 run a 200 m ditch (no network above it) and a 3 km brook; into the middle of
# m2's course, at x = 31,500, a 1,500 m drain (d1 then d2) that reaches the river only 1.5 km below its top.
LINKS = [
    ("m1", "River Main", "a", "b", [(0, 0), (30_000, 0)]),
    ("m2a", "River Main", "b", "c", [(30_000, 0), (31_500, 0)]),
    ("m2b", "River Main", "c", "d", [(31_500, 0), (40_000, 0)]),
    ("m3", "River Main", "d", "e", [(40_000, 0), (50_000, 0)]),
    ("ditch", None, "x", "b", [(30_000, 200), (30_000, 0)]),
    ("brook", "Caldy Brook", "y", "b", [(27_000, 3_000), (30_000, 0)]),
    ("d1", None, "z", "w", [(31_500, 1_500), (31_500, 500)]),
    ("d2", None, "w", "c", [(31_500, 500), (31_500, 0)]),
]


OX, OY = 400_000, 300_000   # the coordinates above are relative to here, inside the grid's own area


def _at(x: float, y: float) -> tuple[float, float]:
    return OX + x, OY + y


@pytest.fixture(scope="module")
def net() -> RiverNetwork:
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": "inlandRiver", "fictitious": False,
          "watercourse_name": n, "watercourse_name_alternative": None, "start_node": s, "end_node": e,
          "geometry": LineString([_at(*p) for p in xy])} for i, n, s, e, xy in LINKS], crs=27700)
    return RiverNetwork.from_links(gdf)


def _overflows(net: RiverNetwork) -> pd.DataFrame:
    rows = [("on_ditch", "ditch", 0.5), ("on_brook", "brook", 0.9), ("top_of_drain", "d1", 0.0),
            ("low_on_drain", "d2", 0.5), ("on_main", "m1", 0.9), ("by_spot", "m3", 0.2)]
    return pd.DataFrame([{"site_id": s, "link_id": lid, "frac": f, "link_length": net.links.loc[lid, "length"],
                          "start_node": net.links.loc[lid, "start_node"]} for s, lid, f in rows])


def _pin() -> transport.PinLocation:
    return transport.PinLocation("river", *_at(45_000, 0), Snap("m3", 0.5, 0.0, "inlandRiver", *_at(45_000, 0)),
                                 trace_node="d", trace_offset_m=5_000.0)


def _trace(net, **kw) -> pd.DataFrame:
    return transport.upstream_overflows(net, _pin(), _overflows(net), velocity_ms=0.5, **kw).set_index("site_id")


def test_the_default_keeps_each_outfalls_own_upstream_length(net):
    assert config.OUTFALL_CHANNEL_MODE == "own" and config.OUTFALL_SNAP_MODE == "nearest"
    own = _trace(net)
    assert own.equals(_trace(net, outfall_channel_mode="own"))
    spot = net.upstream_m["d"] + 5_000.0
    # the ditch has nothing above it: L0 over the spot's
    assert own.loc["on_ditch", "dilution"] == pytest.approx(transport.L0_M / (spot + transport.L0_M))


def test_a_ditch_that_joins_the_river_within_a_kilometre_takes_the_rivers_length(net):
    own, new = _trace(net), _trace(net, outfall_channel_mode="junction")
    lup_b = net.upstream_m["b"]   # 30 km of main river, the ditch and the brook
    spot = net.upstream_m["d"] + 5_000.0
    assert new.loc["on_ditch", "dilution"] == pytest.approx((lup_b + transport.L0_M) / (spot + transport.L0_M))
    # distance, travel time and decay stay as traced
    for col in ("distance_m", "lake_distance_m", "travel_h", "decay"):
        assert new.loc["on_ditch", col] == own.loc["on_ditch", col]
    # the low end of the drain joins within 250 m; its top is 1.5 km above the river, so it keeps its own
    lup_c = net.upstream_m["c"]
    assert new.loc["low_on_drain", "dilution"] == pytest.approx((lup_c + transport.L0_M) / (spot + transport.L0_M))
    assert new.loc["top_of_drain", "dilution"] == own.loc["top_of_drain", "dilution"]


def test_a_brook_or_river_with_its_own_network_keeps_it(net):
    own, new = _trace(net), _trace(net, outfall_channel_mode="junction")
    # the brook is a headwater (nothing above its start, under ADOPT_MIN_M) and meets the river within
    # 1 km of its outfall (90% of the way down), where 30 km of river is far over max(5 km, 5 x 0)
    assert net.upstream_m["y"] == 0.0
    assert new.loc["on_brook", "dilution"] > own.loc["on_brook", "dilution"]
    # an outfall on the main river, and one on the spot's own link, are unchanged
    assert new.loc["on_main", "dilution"] == own.loc["on_main", "dilution"]
    assert new.loc["by_spot", "dilution"] == own.loc["by_spot", "dilution"]


def test_the_junction_needs_ratio_times_the_outfalls_own_network(net):
    link_dist, _ = transport.upstream_lengths(net, "d", 60_000)
    assert transport._outfall_junction(net, "ditch", 0.5, link_dist) == "b"
    assert transport._outfall_junction(net, "m1", 0.9, link_dist) is None       # 3 km to its end: too far
    assert transport._outfall_junction(net, "d1", 0.0, link_dist) is None        # 1.5 km to the river
    assert transport._outfall_junction(net, "d2", 0.5, link_dist) == "c"
    assert transport._outfall_junction(net, "m3", 0.2, link_dist) is None        # the pin's own link
    with pytest.raises(ValueError):
        _trace(net, outfall_channel_mode="nearest")


# ---- first snap "named"

def _snapped(net, rows) -> pd.DataFrame:
    """Overflow rows as build_overflows has them after the first snap: nearest link within SNAP_MAX_M."""
    out = []
    for sid, (x, y), rw, src in rows:
        x, y = _at(x, y)
        lon, lat = bng_to_lonlat(x, y)
        s = net.snap_xy(x, y, max_m=config.SNAP_MAX_M)
        out.append({"site_id": sid, "lon": lon, "lat": lat, "receiving_watercourse": rw, "position_source": src,
                    "link_id": s.link_id, "frac": s.frac, "snap_dist_m": s.dist_m, "form": s.form,
                    "snap_confidence": "high"})
    return pd.DataFrame(out)


def test_a_link_carrying_the_outfalls_own_water_beats_a_nearer_one(net):
    # 158 m from the ditch's top, 250 m from the river and 283 m from Caldy Brook (the line x + y = 30 km)
    at = (30_150, 250)
    df = _snapped(net, [("caldy", at, "Caldy Brook", "live"), ("trib", at, "Tributary of Caldy Brook", "live"),
                        ("joined", at, "Caldy Brook", "join"), ("gill", at, "Spicey Gill", "live"),
                        ("on_it", (28_000, 2_000), "Caldy Brook", "live")])
    assert df.set_index("site_id").loc["caldy", "link_id"] != "brook"
    out = prefer_named(net, df.copy()).set_index("site_id")
    assert out.loc["caldy", "link_id"] == "brook"
    assert out.loc["caldy", "snap_dist_m"] == pytest.approx(net.links.loc["brook", "geometry"].distance(
        Point(*_at(*at))), abs=1.0)
    # a tributary's own water has no name; a checked join stays; a generic word does not match; one on its water stays
    before = df.set_index("site_id")
    for sid in ("trib", "joined", "gill", "on_it"):
        assert out.loc[sid, "link_id"] == before.loc[sid, "link_id"], sid
    assert np.all(out["snap_confidence"] == "high")


def test_a_named_link_beyond_the_snap_radius_does_not_count(net):
    df = _snapped(net, [("far", (30_100, 300), "Caldy Brook", "live")])   # the ditch 141 m; Caldy Brook 283 m
    near_brook = net.links.loc["brook", "geometry"].distance(Point(*_at(30_100, 300)))
    out = prefer_named(net, df.copy(), max_m=near_brook - 1.0)
    assert out.loc[0, "link_id"] == df.loc[0, "link_id"]
    assert prefer_named(net, df.copy(), max_m=near_brook + 1.0).loc[0, "link_id"] == "brook"
