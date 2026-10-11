"""Lake near "blend" (config.LAKE_NEAR_MODE, docs/LAKE-NEAR-FIELD-TEST-2026-10.md): near where an inflow enters
a lake its water is diluted by its own river only, and mixes into the lake with distance. Off by default.
Network-free: a few links built in memory, in British National Grid metres, with a lake polygon in place
of data/processed/lakes.parquet."""

from __future__ import annotations

import math

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, box

from dipcast import config
from dipcast.model import transport
from dipcast.network.rivers import RiverNetwork, Snap

OX, OY = 400_000, 300_000
# A 20 km river flows east into a 4 km lake (three centreline links) and out again. A 300 m beck with
# nothing above it enters the lake 1 km from its head; the spot is 200 m off the beck's mouth.
LINKS = [
    ("main", "inlandRiver", "a", "h", [(-20_000, 0), (0, 0)]),
    ("q1", "lake", "h", "j", [(0, 0), (1_000, 0)]),
    ("q2", "lake", "j", "k", [(1_000, 0), (2_000, 0)]),
    ("q3", "lake", "k", "o", [(2_000, 0), (4_000, 0)]),
    ("out", "inlandRiver", "o", "z", [(4_000, 0), (6_000, 0)]),
    ("beck", "inlandRiver", "b", "j", [(1_000, 300), (1_000, 0)]),
]
LAKE = box(OX - 500, OY - 750, OX + 4_500, OY + 750)   # 7.5 km2


def _at(x: float, y: float) -> tuple[float, float]:
    return OX + x, OY + y


@pytest.fixture(scope="module")
def net() -> RiverNetwork:
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": f, "fictitious": False, "watercourse_name": None,
          "watercourse_name_alternative": None, "start_node": s, "end_node": e,
          "geometry": LineString([_at(*p) for p in xy])} for i, f, s, e, xy in LINKS], crs=27700)
    return RiverNetwork.from_links(gdf)


@pytest.fixture(autouse=True)
def lakes(monkeypatch):
    monkeypatch.setattr(transport, "_lakes", lambda: gpd.GeoDataFrame(
        {"lake_name": ["Test Lake"], "area_km2": [LAKE.area / 1e6]}, geometry=[LAKE], crs=27700))


def _pin(x: float, y: float) -> transport.PinLocation:
    return transport.PinLocation("lake", *_at(x, y), Snap("q2", 0.0, abs(y), "lake", *_at(x, 0)), {"q1", "q2", "q3"}, "o",
                                 trace_node="o", lake_area_km2=LAKE.area / 1e6, lake_source="polygon")


def _overflows(net) -> pd.DataFrame:
    rows = [("on_beck", "beck", 0.5), ("on_main", "main", 0.99), ("on_lake", "q3", 0.5)]
    return pd.DataFrame([{"site_id": s, "link_id": lid, "frac": f, "link_length": net.links.loc[lid, "length"],
                          "start_node": net.links.loc[lid, "start_node"]} for s, lid, f in rows])


def _trace(net, at=(1_000, 200), **kw) -> pd.DataFrame:
    return transport.upstream_overflows(net, _pin(*at), _overflows(net), velocity_ms=0.5, **kw).set_index("site_id")


def test_off_by_default_and_unchanged(net):
    assert config.LAKE_NEAR_MODE == "off"
    assert _trace(net).equals(_trace(net, lake_near_mode="off"))
    with pytest.raises(ValueError):
        _trace(net, lake_near_mode="near")


def test_an_overflow_200_m_off_on_a_beck_with_nothing_else_reads_high_when_it_spills(net):
    off, blend = _trace(net), _trace(net, lake_near_mode="blend")
    w_off, w_blend = off.loc["on_beck", "weight"], blend.loc["on_beck", "weight"]
    # every overflow at the spot spilling: one overflow, so the index is its weight
    assert transport.risk_label(w_off) == "low"
    assert transport.risk_label(w_blend) in ("high", "very high")
    # the arithmetic: the beck's own dilution at its mouth (300 m of beck, nothing above the outfall)
    near = transport.L0_M / (300.0 + transport.L0_M)
    f = math.exp(-200.0 / transport.LAKE_NEAR_M)
    assert blend.loc["on_beck", "dilution"] == pytest.approx(near * f + off.loc["on_beck", "dilution"] * (1 - f))
    # distance and travel time do not change
    for col in ("distance_m", "lake_distance_m", "travel_h", "decay"):
        assert blend.loc["on_beck", col] == off.loc["on_beck", col]


def test_the_near_field_fades_with_distance_across_the_lake(net):
    off = _trace(net, at=(3_900, 0))     # 2.9 km from the beck's mouth, near the outlet
    blend = _trace(net, at=(3_900, 0), lake_near_mode="blend")
    f = math.exp(-2_900.0 / transport.LAKE_NEAR_M)
    assert f < 0.06
    assert blend.loc["on_beck", "dilution"] < 1.2 * off.loc["on_beck", "dilution"] + f


def test_the_main_inflow_and_an_outfall_on_the_lake_have_their_own_dilution_near_them(net):
    off, blend = _trace(net, at=(100, 0)), _trace(net, at=(100, 0), lake_near_mode="blend")
    # The main river's outfall is at its mouth: its own dilution there is close to 1 (L_ov over L_mouth)
    lup_main = net.upstream_m[net.links.loc["main", "start_node"]]
    near_main = min(1.0, (lup_main + transport.L0_M) / (20_000.0 + transport.L0_M))
    f = math.exp(-100.0 / transport.LAKE_NEAR_M)
    assert blend.loc["on_main", "dilution"] == pytest.approx(near_main * f + off.loc["on_main", "dilution"] * (1 - f))
    # On the lake itself there is no inflow: near the outfall its own dilution is 1
    at_lake = _trace(net, at=(3_000, 0), lake_near_mode="blend").loc["on_lake"]
    far = _trace(net, at=(3_000, 0)).loc["on_lake", "dilution"]
    f = math.exp(-at_lake["lake_distance_m"] / transport.LAKE_NEAR_M)
    assert at_lake["dilution"] == pytest.approx(f + far * (1 - f))


def test_the_beck_mouth_does_not_count_the_lakes_own_water_as_the_becks(net):
    # j, the beck's mouth, has the main river and q1 above it along the lake; the beck's own network is 300 m
    assert net.upstream_m["j"] > 20_000
    assert transport._inflow_length(net, "j", {"q1", "q2", "q3"}, net.upstream_m) == pytest.approx(300.0)
