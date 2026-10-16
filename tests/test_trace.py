"""The river a spot's forecast traces upstream, for its map (src/dipcast/trace.py, transport.traced_lines,
build_site.write_traces; docs/REVIEW-2026-10-16.md, G6): the lines are the links upstream_overflows
traces, cut at the 60 km cap, with the pin's own link down to the pin; encoded as Google's polylines; one
file a spot beside its own, under 50 kB."""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from dipcast.model.transport import PinLocation, traced_lines
from dipcast.network.rivers import RiverNetwork, Snap, bng_to_lonlat
from dipcast.trace import decode, encode, encoded_lines

ROOT = Path(__file__).resolve().parents[1]
X0, Y0 = 400_000, 300_000   # in England, so the lines turn into sensible latitudes and longitudes


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def _net() -> RiverNetwork:
    """A river running east through n1, a tributary joining at n1 from the north, and a long reach
    above n0 that runs past the 60 km cap: far (59 km) -> m0 (1 km) -> n1, t (3 km) -> n1, m1 (2 km) -> n2."""
    links = [("far", "n4", "n0", [(-60_000, 0), (-1_000, 0)]), ("m0", "n0", "n1", [(-1_000, 0), (0, 0)]),
             ("t", "n3", "n1", [(0, 3_000), (0, 0)]), ("m1", "n1", "n2", [(0, 0), (2_000, 0)])]
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": "inlandRiver", "fictitious": False, "watercourse_name": "River A",
          "watercourse_name_alternative": None, "start_node": s, "end_node": e,
          "geometry": LineString([(X0 + x, Y0 + y) for x, y in xy])} for i, s, e, xy in links], crs=27700)
    return RiverNetwork.from_links(gdf, fix=False)


def _pin(net) -> PinLocation:
    """Halfway down m1, 1 km below n1."""
    return PinLocation("river", X0 + 1_000, Y0, Snap("m1", 0.5, 0.0, "inlandRiver", X0 + 1_000, Y0), trace_node="n1",
                       trace_offset_m=1_000.0)


def test_encode_is_googles_polyline_and_decode_its_inverse():
    # Google's own example; tests/site_trace.test.cjs decodes the same string in the page.
    assert encode([(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]) == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    pts = [(51.3766, -2.3006), (51.37661, -2.30062), (51.4, -2.25), (51.0, -3.0)]
    assert decode(encode(pts)) == pts


def test_the_trace_is_what_upstream_overflows_counts_cut_at_the_cap_with_the_pin_s_own_link():
    net = _net()
    lines = traced_lines(net, _pin(net), max_km=60)
    # m0 and t whole; far cut where it passes 60 km from the pin (1 km on m1, 1 km on m0: 58 km of its 59);
    # m1 from n1 down to the pin.
    assert sorted(round(line.length) for line in lines) == [1_000, 1_000, 3_000, 58_000]
    far = max(lines, key=lambda line: line.length)
    assert far.coords[0] == (X0 - 59_000, Y0) and far.coords[-1] == (X0 - 1_000, Y0)
    own = next(line for line in lines if line.coords[0] == (X0, Y0))
    assert own.coords[-1] == (X0 + 1_000, Y0)
    # Nothing below the pin, nothing for a pin that is not on the network.
    assert traced_lines(net, PinLocation("none", 0, 0, None)) == []
    assert sum(line.length for line in traced_lines(net, _pin(net), max_km=1.5)) == 500 + 500 + 1_000   # m0, t, own link


def test_lines_are_joined_where_they_meet_without_a_fork_and_drawn_in_latitude_and_longitude():
    net = _net()
    enc = encoded_lines(traced_lines(net, _pin(net)))
    assert len(enc) == 3   # far + m0 joined at n0; the tributary and the pin's link meet at a fork, n1
    pts = sorted((decode(e) for e in enc), key=len)
    ends = {p for line in pts for p in (line[0], line[-1])}
    lon, lat = bng_to_lonlat(X0 + 1_000, Y0)
    assert any(abs(a - lat) < 2e-5 and abs(b - lon) < 2e-5 for a, b in ends)   # down to the pin
    # Straight lines simplify to their ends.
    assert all(len(line) == 2 for line in pts)
    assert encoded_lines([]) == []


def test_write_traces_one_file_a_spot_beside_its_own_with_the_counted_overflows(tmp_path):
    bs = _build_site()
    credits = bs.data_credits("https://example.org/")
    gen = pd.Timestamp("2026-10-16T23:24:15+01:00")
    traces = {"a": ["_p~iF~ps|U_ulLnnqC"], "Bad Id": ["_p~iF~ps|U"], "isolated": []}
    upstream = {"a": [{"site_id": "WW1", "lat": 51.123456, "lon": -2.654321}, {"site_id": "WW2", "lat": None, "lon": None}]}
    got = bs.write_traces(tmp_path, traces, upstream, gen, credits)
    assert got == {"written": 1, "largest": "a", "largest_bytes": (tmp_path / "data" / "spot" / "a-trace.json").stat().st_size}
    doc = json.loads((tmp_path / "data" / "spot" / "a-trace.json").read_text())
    assert doc["id"] == "a" and doc["generated_at"] == gen.isoformat() and doc["max_upstream_km"] == 60
    assert doc["lines"] == traces["a"] and doc["simplified_m"] == 25.0
    assert doc["overflows"] == [["WW1", 51.12346, -2.65432]]   # one without a position is left out
    assert doc["credits"] == credits
    assert sorted(p.name for p in (tmp_path / "data" / "spot").iterdir()) == ["a-trace.json"]


def test_a_trace_over_50_kb_is_announced(tmp_path, monkeypatch):
    bs = _build_site()
    said = []
    monkeypatch.setattr(bs, "announce", said.append)
    bs.write_traces(tmp_path, {"big": ["?" * 60_000]}, {}, pd.Timestamp("2026-10-16T23:24:15+01:00"), {})
    assert said and "big's upstream trace is 60 kB, over 50 kB" in said[0]


def test_the_build_writes_the_traces_after_the_spot_files_and_with_the_forecast_s_placing():
    src = (ROOT / "scripts" / "build_site.py").read_text()
    build = src[src.index("def build("):]
    assert build.index("write_app_data(SITE, doc)") < build.index("write_traces(SITE, traces, upstream, generated, credits)")
    assert "spot_trace(_net(), float(r.lat), float(r.lon), r.kind, r.river, r.name)" in build
