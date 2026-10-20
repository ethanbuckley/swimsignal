"""How the listed spots are joined by water (dipcast.spot_links), for the reasons on the Nearby card
(outside review, 20 Oct 2026). Network-free: a few links built in memory, in British National Grid metres,
in the shapes that matter: a river with a tributary and a branch that meets it below two spots, a river
that meets it only in tidal water, a canal drawn flowing out of one into the other, and a lake."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from dipcast import spot_links as sl
from dipcast.network.rivers import RiverNetwork

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site as bs

# (id, name, form, start node, end node, [(x, y), ...]), drawn in the direction of flow.
LINKS = [
    ("A1", "River A", "inlandRiver", "a0", "a1", [(0, 90000), (0, 80000)]),
    ("A2", "River A", "inlandRiver", "a1", "a2", [(0, 80000), (0, 40000)]),
    ("A3", "River A", "inlandRiver", "a2", "a3", [(0, 40000), (0, 10000)]),
    ("A4", "River A", "tidalRiver", "a3", "a4", [(0, 10000), (0, 0)]),          # the tide from a3
    ("B1", "River B", "inlandRiver", "b0", "a1", [(5000, 85000), (0, 80000)]),  # a tributary above the middle spot
    ("C1", "River C", "inlandRiver", "c0", "a2", [(9000, 60000), (0, 40000)]),  # meets A below the top two spots
    ("D1", "River D", "inlandRiver", "d0", "d1", [(20000, 60000), (20000, 10000)]),
    ("D2", "River D", "tidalRiver", "d1", "a4", [(20000, 10000), (0, 0)]),      # meets A only in tidal water
    ("K1", "Some Canal", "canal", "a1", "d0", [(0, 80000), (20000, 60000)]),    # drawn flowing out of A into D
    ("L1", "Lake L", "lake", "l0", "l1", [(30000, 80000), (30000, 75000)]),
    ("L2", None, "inlandRiver", "l1", "d0", [(30000, 75000), (20000, 60000)]),  # the lake drains to D
]


def _net() -> RiverNetwork:
    links = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": f, "fictitious": False, "watercourse_name": n,
          "watercourse_name_alternative": None, "start_node": s, "end_node": e, "geometry": LineString(xy)}
         for i, n, f, s, e, xy in LINKS], crs=27700)
    return RiverNetwork(*RiverNetwork.oriented(links), repairs={})   # as drawn: no repairs, no fixes


def _ov(*ids: str) -> list[dict]:
    return [{"site_id": i} for i in ids]


# The spots: the node each forecast traces up from, the metres down to the spot, and the overflows it counts.
PLACES = {
    "top": ("a0", 100.0), "middle": ("a1", 50.0), "low": ("a2", 25_000.0), "trib": ("b0", 0.0), "branch": ("c0", 0.0),
    "other": ("d0", 0.0), "lake1": ("l0", 0.0), "lake2": ("l0", 0.0), "isolated": None,
}
UPSTREAM = {
    "top": _ov("O1"), "middle": _ov("O1", "O2", "O4"), "low": _ov("O3", "O5"), "trib": _ov("O4"), "branch": _ov("O5"),
    "other": _ov("O6"), "lake1": [], "lake2": [], "isolated": [],
}


def test_two_spots_that_count_one_overflow_share_it_both_ways():
    links = sl.spot_links(_net(), PLACES, UPSTREAM)
    assert links["top"]["linked"]["middle"] == "s" and links["middle"]["linked"]["top"] == "s"
    assert links["trib"]["linked"]["middle"] == "s"          # a tributary above the spot: the same overflow
    assert links["branch"]["linked"]["low"] == "s"
    assert links["top"]["catchment"] == links["middle"]["catchment"] == links["low"]["catchment"]
    assert sl.shared_overflows(UPSTREAM)["middle"] == {"top", "trib"}


def test_far_down_the_same_river_with_no_overflow_counted_at_both_is_downstream_not_shared():
    """Hurley below Long Bridges: 87 km of river apart, beyond the 60 km the forecast traces."""
    links = sl.spot_links(_net(), PLACES, UPSTREAM)
    assert links["middle"]["linked"]["low"] == "d" and links["low"]["linked"]["middle"] == "u"
    assert links["top"]["linked"]["low"] == "d" and links["low"]["linked"]["top"] == "u"


def test_branches_that_meet_below_both_spots_are_one_catchment_and_not_linked():
    links = sl.spot_links(_net(), PLACES, UPSTREAM)
    assert "branch" not in links["top"]["linked"] and "top" not in links["branch"]["linked"]
    assert links["branch"]["catchment"] == links["top"]["catchment"]


def test_rivers_that_meet_only_in_tidal_water_are_different_catchments_and_a_canal_joins_nothing():
    """D reaches A's estuary, below the tide; the canal from A into D is not followed, or every spot on A
    would be upstream of D's."""
    net = _net()
    links = sl.spot_links(net, PLACES, UPSTREAM)
    assert links["other"]["catchment"] != links["top"]["catchment"]
    assert all(o not in links["top"]["linked"] for o in ("other", "lake1"))
    assert "d0" not in sl.downstream_of(net, "a0")
    assert sl.catchment_end(net, "a0") == "a3" and sl.catchment_end(net, "d0") == "d1"
    assert sl.catchment_end(net, "a3") == "a3"   # on the tide already: its own end


def test_a_lake_and_the_river_below_it_are_joined_two_spots_at_one_lake_only_by_shared_overflows():
    links = sl.spot_links(_net(), PLACES, UPSTREAM)
    assert links["lake1"]["linked"] == {"other": "d"} and links["other"]["linked"]["lake1"] == "u"
    assert "lake2" not in links["lake1"]["linked"]   # one outlet, no metres, nothing upstream: neither is above the other
    assert links["lake1"]["catchment"] == links["lake2"]["catchment"] == links["other"]["catchment"]
    with_ov = {**UPSTREAM, "lake1": _ov("O7"), "lake2": _ov("O7")}
    assert sl.spot_links(_net(), PLACES, with_ov)["lake1"]["linked"]["lake2"] == "s"
    # One stretch of river: the one further down it is downstream.
    two = sl.spot_links(_net(), {"x": ("a1", 10.0), "y": ("a1", 900.0)}, {})
    assert two["x"]["linked"] == {"y": "d"} and two["y"]["linked"] == {"x": "u"}


def test_a_spot_with_no_place_on_the_network_gets_neither_field():
    links = sl.spot_links(_net(), PLACES, UPSTREAM)
    assert "isolated" not in links
    assert all("isolated" not in v["linked"] for v in links.values())
    assert len(links["top"]["catchment"]) == 8


def test_where_branches_end_apart_the_catchment_is_the_main_rivers_end():
    """The Great Ouse at Earith: one branch meets the tide there, the other carries on and gathers more
    water before it does. The end with the most network upstream is the catchment's."""
    links = LINKS + [
        ("S1", "River A", "tidalRiver", "s0", "s1", [(-5000, 50000), (-5000, 0)]),
        ("S0", "River A", "inlandRiver", "a1", "s0", [(0, 80000), (-5000, 50000)]),   # a split at a1 onto a short tidal cut
    ]
    gdf = gpd.GeoDataFrame([{"id": i, "flow_direction": "in direction", "form": f, "fictitious": False, "watercourse_name": n,
                             "watercourse_name_alternative": None, "start_node": s, "end_node": e, "geometry": LineString(xy)}
                            for i, n, f, s, e, xy in links], crs=27700)
    net = RiverNetwork(*RiverNetwork.oriented(gdf), repairs={})
    assert net.upstream_m["a3"] > net.upstream_m["s0"]
    assert sl.catchment_end(net, "a0") == "a3"


def test_attach_puts_both_fields_on_each_placed_spot(monkeypatch):
    net = _net()
    rows = pd.DataFrame([{"id": k, "name": k, "lat": 0.0, "lon": 0.0, "kind": "river", "river": ""} for k in PLACES])
    monkeypatch.setattr(sl, "spot_place", lambda _n, _la, _lo, _k, _r, name: PLACES[name])
    results = [{"id": k} for k in PLACES]
    assert sl.attach(results, rows, UPSTREAM, net) == len(PLACES) - 1
    by = {r["id"]: r for r in results}
    assert by["top"]["linked"]["middle"] == "s" and "catchment" not in by["isolated"]


def test_the_lite_file_has_the_catchment_and_the_spots_own_file_the_links(tmp_path):
    """Only a spot's own page reads `linked`: in the lite file it cost 1.6 kB gzipped on the data of
    20 Oct 2026. The catchment stays there, since the card compares every candidate's."""
    doc = {"generated_at": "2026-10-20T16:33:35+01:00", "credits": {}, "spots": [
        {"id": "osm-thames-long-bridges", "days": [], "contributors": [], "catchment": "6002834c",
         "linked": {"thames-hurley": "d", "thames-port-meadow": "s"}}]}
    bs.write_app_data(tmp_path, doc)
    lite = json.loads((tmp_path / "data" / "spots-lite.json").read_text())["spots"][0]
    assert lite["catchment"] == "6002834c" and "linked" not in lite
    own = json.loads((tmp_path / "data" / "spot" / "osm-thames-long-bridges.json").read_text())
    assert own["linked"] == {"thames-hurley": "d", "thames-port-meadow": "s"}
