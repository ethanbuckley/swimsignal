"""The spill map's routes (src/dipcast/plume.py, build_site.plume_files; docs/PLUME-MAP-2026-10.md): each route runs
from the overflow's place on its link down to the pin along the links the forecast traced, its length is the
forecast's distance, a lake route gets none, and an overflow with no current reading is a marker of its own."""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from dipcast import plume
from dipcast.model.transport import PinLocation, upstream_overflows
from dipcast.network.rivers import RiverNetwork, Snap, bng_to_lonlat
from dipcast.trace import decode

ROOT = Path(__file__).resolve().parents[1]
X0, Y0 = 400_000, 300_000
GEN = pd.Timestamp("2026-10-31T18:00Z")


def _net() -> RiverNetwork:
    """m0 (1 km) -> n1, a tributary t (3 km) -> n1, m1 (2 km) -> n2, and a side arm b from n0 that rejoins at n1 the
    long way round (3 km, through n5), which a route must not take."""
    links = [("m0", "n0", "n1", [(-1_000, 0), (0, 0)]), ("t", "n3", "n1", [(0, 3_000), (0, 0)]),
             ("b", "n0", "n5", [(-1_000, 0), (-1_000, 1_000), (0, 1_000)]), ("b2", "n5", "n1", [(0, 1_000), (0, 0)]),
             ("m1", "n1", "n2", [(0, 0), (2_000, 0)])]
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": "inlandRiver", "fictitious": False, "watercourse_name": "River A",
          "watercourse_name_alternative": None, "start_node": s, "end_node": e,
          "geometry": LineString([(X0 + x, Y0 + y) for x, y in xy])} for i, s, e, xy in links], crs=27700)
    return RiverNetwork.from_links(gdf, fix=False)


def _pin() -> PinLocation:
    """Halfway down m1, 1 km below n1."""
    return PinLocation("river", X0 + 1_000, Y0, Snap("m1", 0.5, 0.0, "inlandRiver", X0 + 1_000, Y0), trace_node="n1",
                       trace_offset_m=1_000.0)


def _ov(rows) -> pd.DataFrame:
    out = []
    for sid, link, frac, (x, y) in rows:
        lon, lat = bng_to_lonlat(X0 + x, Y0 + y)
        out.append({"site_id": sid, "link_id": link, "frac": frac, "lat": lat, "lon": lon, "status": 0, "company": "C"})
    return pd.DataFrame(out)


def test_a_route_runs_down_the_traced_links_to_the_pin_the_short_way():
    net = _net()
    xy = plume.route_xy(net, _pin(), "t", 0.5)   # 1.5 km down t, then 1 km down m1 to the pin
    assert xy[0] == (X0, Y0 + 1_500) and xy[-1] == (X0 + 1_000, Y0)
    assert round(LineString(xy).length) == 2_500
    xy = plume.route_xy(net, _pin(), "m0", 0.0)   # the main channel (1 km), not the side arm (3 km)
    assert round(LineString(xy).length) == 2_000


def test_a_route_is_the_length_the_forecast_measured():
    net, pin = _net(), _pin()
    ov = _ov([("A", "t", 0.25, (0, 2_250)), ("B", "m0", 0.5, (-500, 0)), ("C", "m1", 0.2, (400, 0))])
    ov["link_length"] = ov["link_id"].map(net.links["length"])
    ov["start_node"] = ov["link_id"].map(net.links["start_node"])
    counted = upstream_overflows(net, pin, ov, velocity_ms=0.2, lake_path_mode="river")
    for _, r in counted.iterrows():
        xy = plume.route_xy(net, pin, r["link_id"], r["frac"])
        assert abs(LineString(xy).length - r["distance_m"]) < 1.0, r["site_id"]


def test_no_route_below_the_pin_off_the_trace_or_at_a_lake():
    net, pin = _net(), _pin()
    assert plume.route_xy(net, pin, "m1", 0.8) is None   # below the pin on its own link
    lake = PinLocation("lake", X0, Y0, None, trace_node="n1")
    assert plume.route_xy(net, lake, "t", 0.5) is None


def _replay():
    spill = {"start": "2026-10-31T06:00Z", "end": "2026-10-31T08:00Z", "running": False, "end_known": True,
             "arrival": {"from": "2026-10-31T09:28Z", "to": "2026-10-31T11:28Z", "state": "passed"}}
    return {"window": {"from": "2026-10-29T18:00Z", "to": "2026-10-31T18:00Z"}, "overflows": [
        {"site_id": "A", "km": 2.5, "travel_h": 3.47, "lake_route": False, "weight": 0.4, "state": "live", "spills": [spill]},
        {"site_id": "L", "km": 9.0, "travel_h": None, "lake_route": True, "weight": 0.2, "state": "live", "spills": [spill]}],
        "quiet": {"offline": {"n": 1, "weight": 0.1}}}


def test_the_file_has_routes_for_river_spills_and_markers_for_gaps():
    net, pin = _net(), _pin()
    ov = _ov([("A", "t", 0.5, (0, 1_500)), ("L", "t", 0.1, (0, 2_700)), ("G", "m0", 0.5, (-500, 0))])
    up = [{"site_id": s, "lat": r.lat, "lon": r.lon, "weight": w, "data_state": st}
          for (s, w, st), r in zip([("A", 0.4, "live"), ("L", 0.2, "live"), ("G", 0.3, "offline")], ov.itertuples(), strict=True)]
    spot = {"id": "x", "lat": 52.0, "lon": -1.5, "location": {"snapped": {"lat": 52.1, "lon": -1.6}},
            "assumptions": {"river_velocity_ms": 0.2}}
    doc = plume.spot_plume(net, pin, spot, up, _replay(), ov, GEN)
    a, lake = doc["overflows"]
    assert a["km"] == 2.5 and len(decode(a["path"])) >= 2
    assert "path" not in lake and lake["at"] is not None   # a lake route: where it is, no path
    assert [g["site_id"] for g in doc["gaps"]] == ["G"] and doc["gaps"][0]["state"] == "offline"
    assert doc["pin"] == [52.1, -1.6] and doc["unrouted"] == 0 and doc["river_velocity_ms"] == 0.2


def test_write_plumes_writes_beside_the_replay_and_skips_lakes(tmp_path):
    net = _net()
    (tmp_path / "data" / "spot").mkdir(parents=True)
    (tmp_path / "data" / "spot" / "x-replay.json").write_text(json.dumps(_replay()))
    (tmp_path / "data" / "spot" / "y-replay.json").write_text(json.dumps(_replay()))
    ov = _ov([("A", "t", 0.5, (0, 1_500))])
    lon, lat = bng_to_lonlat(X0 + 1_000, Y0)
    results = [{"id": "x", "kind": "river", "river": "River A", "name": "X", "lat": lat, "lon": lon},
               {"id": "y", "kind": "lake", "river": "", "name": "Y", "lat": lat, "lon": lon},
               {"id": "z", "kind": "river", "lat": lat, "lon": lon}]   # no replay file: no routes file
    up = {"x": [{"site_id": "A", "lat": ov.lat[0], "lon": ov.lon[0], "weight": 0.4, "data_state": "live"}]}
    out = plume.write_plumes(tmp_path, results, up, GEN, net, ov)
    files = sorted(p.name for p in (tmp_path / "data" / "spot").glob("*-plume.json"))
    assert files == ["x-plume.json"] and out["written"] == 1 and out["failed"] == 0


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_build_ships_plume_js_and_a_failure_never_stops_it(tmp_path):
    bs = _build_site()
    assert bs.TEMPLATE.parent / "plume.js" in bs.SHELL_SOURCES   # a change to it renames the offline cache

    def boom(*a, **k):
        raise RuntimeError("no network")
    out = bs.plume_files(tmp_path, [], {}, GEN, write=boom)
    assert out["written"] == 0 and "no network" in out["warning"]
    sw = (bs.TEMPLATE.parent / "sw.js").read_text()
    assert "`plume.js?v=${BUILD}`" in sw and "trace|replay|plume" in sw
