"""The click-anywhere tables (scripts/build_any_point.py) against the API's own trace. Network-free:
a few links built in memory, in British National Grid metres, as in test_placement.py."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Polygon, box

from dipcast import config
from dipcast.model import transport
from dipcast.network.rivers import RiverNetwork, bng_to_lonlat, lonlat_to_bng

ROOT = Path(__file__).resolve().parents[1]


def _bap():
    spec = importlib.util.spec_from_file_location("build_any_point", ROOT / "scripts" / "build_any_point.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _net(links: list[tuple]) -> RiverNetwork:
    """links: (id, name, form, start node, end node, [(x, y), ...]), all in flow direction."""
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": f, "fictitious": f == "lake",
          "watercourse_name": n, "watercourse_name_alternative": None, "start_node": s, "end_node": e,
          "geometry": LineString(xy)} for i, n, f, s, e, xy in links], crs=27700)
    return RiverNetwork.from_links(gdf)


# A river running east along y = 450000 with a beck from the north at x = 404000, an unnamed drain
# joining at x = 406000, and a mill leat beside its third reach that is not joined upstream. To the
# east, a beck flows south into a two-link lake, which drains south into a second, smaller lake:
# water from above the first lake crosses it on the way to a click below it or in the second.
# Further east, the River Stor in West Sussex (16 Oct 2026): a short unnamed link with a 25 m kink, cut
# off from the network as OS often draws them, 35 m from a pond's centreline and 230 m from the river.
LINKS = [
    ("M1", "River Test", "inlandRiver", "n0", "n1", [(400000, 450000), (402000, 450000)]),
    ("M2", "River Test", "inlandRiver", "n1", "n2", [(402000, 450000), (404000, 450000)]),
    ("M3", "River Test", "inlandRiver", "n2", "n3", [(404000, 450000), (405000, 450050), (406000, 450000)]),
    ("M4", "River Test", "inlandRiver", "n3", "n4", [(406000, 450000), (410000, 450000)]),
    ("T1", "Trib Beck", "inlandRiver", "t0", "n2", [(404000, 453000), (404000, 450000)]),
    ("D1", None, "inlandRiver", "d0", "n3", [(405000, 451500), (406000, 450000)]),
    ("S1", "Mill Leat", "inlandRiver", "s0", "n3", [(404500, 450200), (405500, 450200), (406000, 450000)]),
    ("R1", "Inflow Beck", "inlandRiver", "r0", "k0", [(420000, 460000), (420000, 456000)]),
    ("K1", "Test Water", "lake", "k0", "k1", [(420000, 456000), (420000, 454000)]),
    ("K2", "Test Water", "lake", "k1", "k2", [(420000, 454000), (420000, 452000)]),
    ("O1", "Outflow Beck", "inlandRiver", "k2", "o1", [(420000, 452000), (420000, 448000)]),
    ("L3", "Lower Water", "lake", "o1", "l3", [(420000, 448000), (420000, 446000)]),
    ("O2", "Lower Beck", "inlandRiver", "l3", "o2", [(420000, 446000), (420000, 443000)]),
    ("V1", "River Stor", "inlandRiver", "v0", "v1", [(430000, 432000), (430000, 440000)]),
    ("V2", "River Stor", "inlandRiver", "v1", "v2", [(430000, 440000), (430000, 442000)]),
    ("U1", None, "inlandRiver", "u0", "u1", [(430200, 439975), (430230, 440000), (430260, 439975)]),
    ("P1", None, "lake", "p0", "p1", [(430200, 440035), (430300, 440035)]),
    # Empty Water has no lake link inside. East Pond is the nearer to its middle, West Pond to a click on
    # its west shore; neither is within 1.5 km of its north shore.
    ("E1", "East Beck", "inlandRiver", "e0", "pe0", [(451300, 472500), (451300, 470600)]),
    ("EP", "East Pond", "lake", "pe0", "pe1", [(451300, 470600), (451300, 470400)]),
    ("E2", "East Beck", "inlandRiver", "pe1", "e2", [(451300, 470400), (451300, 468000)]),
    ("W1", "West Beck", "inlandRiver", "w0", "pw0", [(448800, 472500), (448800, 470600)]),
    ("WP", "West Pond", "lake", "pw0", "pw1", [(448800, 470600), (448800, 470400)]),
    ("W2", "West Beck", "inlandRiver", "pw1", "w2", [(448800, 470400), (448800, 468000)]),
    # Notch Water's lake link, unnamed, runs down its middle.
    ("N0", "Notch Beck", "inlandRiver", "nb0", "nb1", [(460500, 472500), (460500, 470800)]),
    ("N1", None, "lake", "nb1", "nb2", [(460500, 470800), (460500, 470200)]),
    ("N2", "Notch Beck", "inlandRiver", "nb2", "nb3", [(460500, 470200), (460500, 468000)]),
    # Quiet Pond, 450 m from Quiet Water, which has no lake link inside. No overflow is anywhere near.
    ("Q1", "Quiet Pond", "lake", "q0", "q1", [(500000, 501000), (500200, 501000)]),
]
KINK = (430230, 440000)   # U1's kink: 0 m from U1, 25 m from U1 simplified to 30 m, 35 m from P1
LAKE_POLY = box(419000, 451800, 421000, 456200)          # 8.8 km2
LOWER_POLY = box(419400, 445900, 420600, 447900)         # 2.4 km2, 100 m below Outflow Beck's end
ALONE_POLY = box(440000, 470000, 441000, 471000)         # no lake centreline anywhere near
EMPTY_POLY = box(450000, 470000, 451000, 473000)         # no lake link inside; East Pond 1.2 km from its middle
NOTCH_POLY = Polygon([(460000, 470000), (461000, 470000), (461000, 470490), (461012, 470500), (461000, 470510),
                      (461000, 471000), (460000, 471000)])   # a 12 m spit on its east side, which 15 m outlines drop
QUIET_POLY = box(499000, 500000, 499800, 500600)         # no lake link inside; Quiet Pond 450 m off


def _overflows(net: RiverNetwork, spec: list[tuple]) -> pd.DataFrame:
    rows = []
    for sid, lid, frac, conf in spec:
        g = net.links.at[lid, "geometry"]
        pt = g.interpolate(frac, normalized=True)
        lon, lat = bng_to_lonlat(pt.x, pt.y)
        rows.append({"site_id": sid, "link_id": lid, "frac": frac, "link_length": float(net.links.at[lid, "length"]),
                     "start_node": net.links.at[lid, "start_node"], "end_node": net.links.at[lid, "end_node"],
                     "lat": lat, "lon": lon, "snap_confidence": conf, "company": "Test Water Co", "status": 0,
                     "has_live": True})
    return pd.DataFrame(rows)


OVERFLOWS = [("A1", "M1", 0.3, "high"), ("A2", "T1", 0.45, "high"), ("A3", "M3", 0.2, "low"),
             ("A4", "M3", 0.8, "high"), ("A5", "R1", 0.4, "high"), ("A6", "K1", 0.5, "high"),
             ("A7", "D1", 0.1, "high"), ("A8", "O1", 0.5, "high"), ("A9", "V1", 0.5, "high"), ("B1", "E1", 0.5, "high"),
             ("B2", "W1", 0.5, "high"), ("B3", "N0", 0.5, "high")]
RIVER_LINKS = ["M1", "M2", "M3", "M4", "T1", "D1", "S1", "R1", "O1", "O2"]


TEST_WATER_TAU_D = 20.0   # lake path "residence": Test Water holds its water 20 days; Lower Water has no time


@pytest.fixture
def world(monkeypatch, tmp_path):
    res = tmp_path / "lake_residence.csv"
    pd.DataFrame({"wb_id": ["GB1"], "res_time_d": [TEST_WATER_TAU_D]}).to_csv(res, index=False)
    monkeypatch.setattr(config, "LAKE_RESIDENCE_FILE", res)
    # These tests are of the lake path modes, with the straight line across a lake; lake distance "water", the
    # default, is tested on a lake that bends in test_anypoint_water.py.
    monkeypatch.setattr(config, "LAKE_DISTANCE_MODE", "line")
    net = _net(LINKS)
    polys = [LAKE_POLY, ALONE_POLY, LOWER_POLY, EMPTY_POLY, NOTCH_POLY, QUIET_POLY]
    lakes = gpd.GeoDataFrame({"wb_id": ["GB1", "GB2", "GB3", "GB4", "GB5", "GB6"],
                              "lake_name": ["Test Water", "Lonely Pool", "Lower Water", "Empty Water", "Notch Water", "Quiet Water"],
                              "area_km2": [p.area / 1e6 for p in polys]}, geometry=polys, crs=27700)
    monkeypatch.setattr(transport, "_lakes", lambda: lakes)
    return net, lakes, _overflows(net, OVERFLOWS)


MODES = ["lake", "river", "residence"]   # config.LAKE_PATH_MODE: the default, the rule before 11 Oct 2026, and
                                         # the well-mixed lake under test (docs/LAKE-RESIDENCE-TEST-2026-10.md)


def _travel(rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Travel (h) and die-off of rows_at's rows at the default speeds, as anypoint.js transportOf: the
    metres of a well-mixed lake travel as its survivors' hours, and the share alive multiplies the die-off."""
    moving = (rows["distance_m"] / 0.5 + (rows["lake_distance_m"] - rows["res_m"]) / config.LAKE_VELOCITY_MS) / 3600
    return (moving + rows["hold_h"]).to_numpy(float), (10 ** (-moving / config.T90_HOURS) * rows["lake_pass"]).to_numpy(float)


def _tile_files(out: Path, lid: str, net: RiverNetwork, bap) -> tuple[dict, dict, int]:
    """The link index and link list for the square the link's midpoint is in, and the link's number."""
    mid = net.links.at[lid, "geometry"].interpolate(0.5, normalized=True)
    lon, lat = bng_to_lonlat(mid.x, mid.y)
    t = bap.tile_key(lat, lon)
    idx = bap.unpack_link_index((out / "link_index" / f"{t}.bin").read_bytes())
    lno = int(pd.Series(range(len(net.links)), index=net.links.index.sort_values())[lid])
    return idx, json.loads((out / "links" / f"{t}.json").read_text()), lno


def _api(net, ov, lon, lat) -> pd.DataFrame:
    """What the API traces for a click: locate_pin, then upstream_overflows at the default velocity
    and config.LAKE_PATH_MODE."""
    pin = transport.locate_pin(net, lon, lat)
    up = transport.upstream_overflows(net, pin, ov.drop(columns="snap_confidence"), velocity_ms=transport.river_velocity(None))
    return pin, up.sort_values("site_id").reset_index(drop=True)


def _record(out: Path, lid: str, net: RiverNetwork, ids: list[str], bap) -> dict | None:
    """A link's record as the page reads it: its entry in the square its midpoint is in."""
    _, tile, lno = _tile_files(out, lid, net, bap)
    entry = tile["links"].get(str(lno))
    return None if entry is None else bap.decode_record(entry, ids)


@pytest.mark.parametrize("mode", MODES)
def test_every_click_on_a_river_matches_the_api_trace(world, tmp_path, monkeypatch, mode):
    monkeypatch.setattr(config, "LAKE_PATH_MODE", mode)
    bap = _bap()
    net, lakes, ov = world
    table, stats = bap.upstream_table(net, ov, lakes, "net0", "lakes0", tmp_path / "cache.pkl")
    assert stats["cache"] == "cold"
    out = tmp_path / "anypoint"
    bap.write_files(out, net, ov, table, "net0")
    ids = json.loads((out / "overflow_ids.json").read_text())["ids"]
    assert ids == sorted(ids) and len(ids) == len(OVERFLOWS)
    checked, moved, crossed = 0, set(), set()
    for lid in RIVER_LINKS:
        for f in (0.15, 0.5, 0.85):
            at = net.links.at[lid, "geometry"].interpolate(f, normalized=True)
            pin, want = _api(net, ov, *bng_to_lonlat(at.x, at.y))
            assert pin.mode == "river"
            # The link the API traces (the clicked one, or the main channel a side channel is moved
            # to) and where along it: its record gives the API's rows.
            if pin.adopted_main_channel:
                moved.add((lid, pin.snap.link_id))
            rec = _record(out, pin.snap.link_id, net, ids, bap)
            got = (bap.rows_at(rec, pin.snap.frac) if rec else want.iloc[0:0]).sort_values("site_id").reset_index(drop=True)
            assert list(got["site_id"]) == list(want["site_id"]), (lid, f)
            assert np.allclose(got["distance_m"].astype(float), want["distance_m"].astype(float), atol=6.0), (lid, f)   # tens of metres
            assert np.allclose(got["lake_distance_m"].astype(float), want["lake_distance_m"].astype(float), atol=1.0), (lid, f)
            assert np.allclose(got["dilution"].astype(float), want["dilution"].astype(float), atol=1e-4), (lid, f)
            travel, decay = _travel(got) if len(got) else (np.zeros(0), np.zeros(0))
            assert np.allclose(travel, want["travel_h"].astype(float), atol=0.01), (lid, f)
            assert np.allclose(decay, want["decay"].astype(float), rtol=1e-3), (lid, f)
            checked += len(want)
            crossed |= {(lid, s) for s, m in zip(want["site_id"], want["lake_distance_m"], strict=True) if m > 0}
        # The index carries the link, its form, the name the API gives a click on it, its line, and
        # the network length upstream that the page's side-channel rule needs.
        idx, _, lno = _tile_files(out, lid, net, bap)
        k = int(np.flatnonzero(idx["lno"] == lno)[0])
        assert bap.FORMS[idx["form"][k]] == net.links.at[lid, "form"]
        j = int(idx["name"][k])
        assert (idx["names"][j] if j >= 0 else None) == transport._link_name(net, lid)
        line = idx["lonlat"][idx["offsets"][k]:idx["offsets"][k + 1]]
        assert np.allclose(line[0], bng_to_lonlat(*net.links.at[lid, "geometry"].coords[0]), atol=1e-5)
        assert idx["upstream"][k] == pytest.approx(net.link_upstream_m(lid), abs=0.01)
    assert checked > 20
    # Below the first lake, water from above it or on it crosses it in mode "lake"; below the second,
    # it crosses both. A8, on Outflow Beck, crosses only the second. In mode "river" nothing does.
    if mode in ("lake", "residence"):
        assert {("O1", "A5"), ("O1", "A6"), ("O2", "A5"), ("O2", "A6"), ("O2", "A8")} <= crossed
        o2 = _record(out, "O2", net, ids, bap)
        lower = 1 + LOWER_POLY.area / 1e6 / transport.LAKE_A0_KM2
        assert o2["path"]["A8"][1] == pytest.approx(1 / lower, abs=1e-6)
        if mode == "lake":
            assert o2["path"]["A5"][1] == pytest.approx(1 / lower / (1 + LAKE_POLY.area / 1e6 / transport.LAKE_A0_KM2), abs=1e-6)
            assert "hold" not in o2
        else:   # Test Water is well mixed: no area factor, its survivors' hours and share alive instead
            tau = TEST_WATER_TAU_D * 24
            assert o2["path"]["A5"][1] == pytest.approx(1 / lower, abs=1e-6)
            assert o2["hold"]["A5"][1] == pytest.approx(transport.lake_hold_h(tau), abs=1e-3)
            assert o2["hold"]["A5"][2] == pytest.approx(transport.lake_pass(tau), rel=1e-6)
            assert "A8" not in o2["hold"]   # Lower Water has no residence time: crossed as in "lake"
    else:
        assert not crossed
    # Side channels: the leat, and the beck and the drain near where they join, are traced as the river.
    assert ("S1", "M3") in moved and ("T1", "M3") in moved and any(a == "D1" for a, _ in moved)
    # An overflow on the clicked link counts only above the click; the unnamed drain is named after
    # the river it joins.
    m3 = _record(out, "M3", net, ids, bap)
    assert set(bap.rows_at(m3, 0.5)["site_id"]) == {"A1", "A2", "A3"}
    assert set(bap.rows_at(m3, 0.9)["site_id"]) == {"A1", "A2", "A3", "A4"}
    idx, _, lno = _tile_files(out, "D1", net, bap)
    assert idx["names"][idx["name"][int(np.flatnonzero(idx["lno"] == lno)[0])]] == "River Test"


@pytest.mark.parametrize("mode", MODES)
def test_a_lake_click_from_the_published_inlets_matches_the_api(world, tmp_path, monkeypatch, mode):
    monkeypatch.setattr(config, "LAKE_PATH_MODE", mode)
    bap = _bap()
    net, lakes, ov = world
    table, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", None)
    out = tmp_path / "anypoint"
    bap.write_files(out, net, ov, table, "net0")
    doc = json.loads((out / "lakes.json").read_text())
    ids = json.loads((out / "overflow_ids.json").read_text())["ids"]
    water, alone, lower, *_ = doc["polygons"]
    assert water["name"] == "Test Water" and isinstance(water["lake"], int) and alone["lake"] == -1
    assert lower["name"] == "Lower Water" and isinstance(lower["lake"], int)
    # A click in each lake. What the page does: from each inlet, the distance along the network less any
    # lake crossed on the way at the river velocity; that lake and the straight line to the click at the
    # lake velocity; the area term, times the factor of the lake crossed.
    for poly, click, sites in ((water, (419500, 455000), ["A5", "A6"]), (lower, (420300, 447000), ["A5", "A6", "A8"])):
        pin, want = _api(net, ov, *bng_to_lonlat(*click))
        assert pin.mode == "lake" and pin.lake_source == "polygon"
        rows = []
        for inlet in doc["lakes"][poly["lake"]]["inlets"]:
            ex, ey = lonlat_to_bng(*inlet["at"])
            path = {int(i): (m, f / bap.PATH_SCALE) for i, m, f in np.asarray(inlet.get("k", []), dtype=float).reshape(-1, 3)}
            mix = {int(i): (m, h / bap.HOLD_SCALE, q / bap.PASS_SCALE)
                   for i, m, h, q in np.asarray(inlet.get("h", []), dtype=float).reshape(-1, 4)}
            for i, d, w in np.asarray(inlet["o"], dtype=float).reshape(-1, 3):
                m, factor = path.get(int(i), (0.0, 1.0))
                res_m, _hold, alive = mix.get(int(i), (0.0, 0.0, 1.0))   # the hours move the day, not the weight
                d_lake = math.hypot(ex - click[0], ey - click[1]) + m
                travel = ((d - m) / 0.5 + (d_lake - res_m) / 0.05) / 3600
                rows.append((ids[int(i)], d - m, d_lake,
                             10 ** (-travel / 30) * alive * w / bap.DIL_SCALE / (1 + poly["area_km2"] / 5) * factor))
        got = pd.DataFrame(rows, columns=["site_id", "distance_m", "lake_distance_m", "weight"])
        got = got.sort_values("site_id").reset_index(drop=True)
        assert list(got["site_id"]) == list(want["site_id"]) == sites
        assert np.allclose(got["distance_m"], want["distance_m"], atol=1.0)
        assert np.allclose(got["lake_distance_m"], want["lake_distance_m"], atol=2.0)
        assert np.allclose(got["weight"], want["weight"], rtol=2e-3)
        # In the lower lake, water from above Test Water has crossed it in modes "lake" and "residence" only.
        if poly is lower:
            a5 = want.set_index("site_id").loc["A5"]
            assert (a5["lake_distance_m"] > 4_000) == (mode != "river")


def test_a_lake_with_no_centreline_inside_takes_the_one_nearest_the_click_not_its_middle(world, tmp_path):
    # Eccup Reservoir, Church Wilne, Chelker, Island Barn, White Mere and King George VI (16 Oct 2026): the build
    # took the lake link nearest the lake's middle, the API the one nearest the click (docs/ANYPOINT-LAKES-2026-10.md).
    bap = _bap()
    net, lakes, ov = world
    wfd, _, _ = bap.lake_link_sets(net, lakes)
    links = {w["name"]: w["links"] for w in wfd}
    assert links["Empty Water"] is None and links["Quiet Water"] is None and links["Lonely Pool"] is None
    assert links["Notch Water"] == {"N1"} and links["Test Water"] == {"K1", "K2"}
    # The API: West Pond for a click on the west shore, though East Pond is the nearer to the middle.
    pin, up = _api(net, ov, *bng_to_lonlat(449900, 470500))
    assert (pin.mode, pin.lake_source, pin.watercourse, pin.lake_links) == ("lake", "polygon", "Empty Water", {"WP"})
    assert list(up["site_id"]) == ["B2"]
    assert EMPTY_POLY.centroid.distance(net.links.at["EP", "geometry"]) < 1500 < EMPTY_POLY.centroid.distance(net.links.at["WP", "geometry"])
    # The page finds the pond in the link index: Quiet Pond's square has files though no overflow is near it.
    table, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", None)
    out = tmp_path / "anypoint"
    meta = bap.write_files(out, net, ov, table, "net0")
    doc = json.loads((out / "lakes.json").read_text())
    assert [p["lake"] for p in doc["polygons"] if p["name"] in ("Empty Water", "Quiet Water", "Lonely Pool")] == [-1, -1, -1]
    assert meta["counts"]["wfd_no_centreline"] == 3
    quiet = bap.tile_key(*reversed(bng_to_lonlat(500100, 501000)))
    assert quiet in meta["tiles"] and quiet not in {bap.tile_key(a, b) for a, b in zip(ov["lat"], ov["lon"], strict=True)}
    idx, _, lno = _tile_files(out, "Q1", net, bap)
    assert lno in idx["lno"]


def test_lakes_json_says_how_far_each_outline_is_from_the_real_one_which_is_published_too(world, tmp_path):
    # Gorpley Reservoir (16 Oct 2026): a click 149.1 m from the real outline was 151.1 m from the 15 m one.
    bap = _bap()
    net, lakes, ov = world
    table, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", None)
    out = tmp_path / "anypoint"
    bap.write_files(out, net, ov, table, "net0")
    doc = json.loads((out / "lakes.json").read_text())
    n = next(i for i, p in enumerate(doc["polygons"]) if p["name"] == "Notch Water")
    notch = doc["polygons"][n]
    spit = list(np.round(bng_to_lonlat(461012, 470500), 6))
    real = json.loads((out / "lake_outlines" / f"{n}.json").read_text())
    assert real["wb_id"] == "GB5" and spit in real["rings"][0]
    assert not any(np.allclose(v, spit, atol=1e-5) for v in notch["rings"][0])   # the 15 m outline drops the spit
    assert 13 <= notch["err"] <= 14                                               # 12 m, plus 1 m for 5 decimals
    assert all(p["err"] == 1 for p in doc["polygons"] if p["name"] != "Notch Water")   # boxes lose nothing
    assert sorted(int(f.stem) for f in (out / "lake_outlines").iterdir()) == list(range(len(doc["polygons"])))
    pin, _ = _api(net, ov, *bng_to_lonlat(461161, 470500))
    assert (pin.mode, pin.lake_source, pin.watercourse) == ("lake", "polygon", "Notch Water")


def test_moving_an_overflow_retraces_only_whats_downstream(world, tmp_path):
    bap = _bap()
    net, lakes, ov = world
    cache = tmp_path / "cache.pkl"
    bap.upstream_table(net, ov, lakes, "net0", "lakes0", cache)
    _, stats = bap.upstream_table(net, ov, lakes, "net0", "lakes0", cache)
    assert stats["cache"] == "warm" and stats["traced_links"] == 0
    moved = ov.copy()
    moved.loc[moved["site_id"] == "A4", "frac"] = 0.4   # now above M3's midpoint
    moved = moved[moved["site_id"] != "A7"]             # and one overflow gone
    inc, stats = bap.upstream_table(net, moved, lakes, "net0", "lakes0", cache)
    assert stats["cache"] == "2 overflows changed" and 0 < stats["traced_links"] < len(net.links)
    full, _ = bap.upstream_table(net, moved, lakes, "net0", "lakes0", None)
    assert inc["records"] == full["records"]
    assert set(bap.rows_at(inc["records"]["M3"], 0.5)["site_id"]) == {"A1", "A2", "A3", "A4"}
    assert not any(r[0] == "A7" for rec in inc["records"].values() for r in rec["other"] + rec["same"])
    # A different network file starts again.
    _, stats = bap.upstream_table(net, moved, lakes, "net1", "lakes0", cache)
    assert stats["cache"] == "stale network"


def test_a_change_of_lake_path_rule_traces_everything_again(world, tmp_path, monkeypatch):
    bap = _bap()
    net, lakes, ov = world
    cache = tmp_path / "cache.pkl"
    monkeypatch.setattr(config, "LAKE_PATH_MODE", "river")
    old, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", cache)
    monkeypatch.setattr(config, "LAKE_PATH_MODE", "lake")
    new, stats = bap.upstream_table(net, ov, lakes, "net0", "lakes0", cache)
    assert stats["cache"] == "stale rules" and stats["traced_links"] > 0
    assert "path" not in old["records"]["O1"] and set(new["records"]["O1"]["path"]) == {"A5", "A6"}
    full, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", None)
    assert new["records"] == full["records"]
    # So does a new version of the rules, with the same mode and files.
    monkeypatch.setattr(bap, "CACHE_VERSION", bap.CACHE_VERSION + 1)
    _, stats = bap.upstream_table(net, ov, lakes, "net0", "lakes0", cache)
    assert stats["cache"] == "stale rules"


def test_the_index_keeps_every_vertex_so_a_click_on_a_kink_is_on_its_link(world, tmp_path):
    """The page measures a click against the index's lines, the API against the network's. Lines simplified
    to 30 m put U1's kink 25 m from its line, and the pond's centreline, 35 m away, won by the lake rule
    (35 x 0.5 < 25): the page found no river where the API traced the River Stor (16 Oct 2026)."""
    bap = _bap()
    net, lakes, ov = world
    table, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", None)
    out = tmp_path / "anypoint"
    bap.write_files(out, net, ov, table, "net0")
    for lid in net.links.index:
        idx, _, lno = _tile_files(out, lid, net, bap)
        k = int(np.flatnonzero(idx["lno"] == lno)[0])
        line = idx["lonlat"][idx["offsets"][k]:idx["offsets"][k + 1]]
        want = np.array([bng_to_lonlat(x, y) for x, y in net.links.at[lid, "geometry"].coords])
        assert line.shape == want.shape and np.allclose(line, want, atol=1e-6), lid   # Float32: under 0.5 m
    pin, up = _api(net, ov, *bng_to_lonlat(*KINK))
    assert (pin.mode, pin.watercourse, pin.adopted_main_channel, list(up["site_id"])) == ("river", "River Stor", True, ["A9"])


def test_link_names_follow_the_api():
    bap = _bap()
    net = _net(LINKS)
    names = bap.link_names(net, list(net.links.index))
    assert names == {lid: transport._link_name(net, lid) for lid in net.links.index}


def test_the_page_loads_the_script_at_the_builds_stamp_and_the_offline_copy_keeps_it(tmp_path):
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    bs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bs)
    spot = {"id": "a", "name": "A river", "kind": "river", "lat": 54.0, "lon": -1.8, "days": [], "contributors": []}
    bs.write_pages(tmp_path, [spot], root="https://example.org/")
    stamp = bs.shell_stamp()
    assert f'<script src="anypoint.js?v={stamp}" defer></script>' in (tmp_path / "index.html").read_text()
    assert (tmp_path / "anypoint.js").read_text() == (ROOT / "src" / "dipcast" / "site" / "anypoint.js").read_text()
    assert "`anypoint.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()   # in the worker's SHELL
    assert ROOT / "src" / "dipcast" / "site" / "anypoint.js" in bs.SHELL_SOURCES   # a change to it renames the cache


# ------------------------------------------------------------------ the page's fixture
# tests/site_anypoint.test.cjs runs the page's placing (anypoint.js, place) on this network's
# published files and compares it with what the API traced for the same clicks; both are kept in
# tests/fixtures/anypoint_synthetic.json, once per lake path mode. UPDATE_FIXTURES=1 writes it again
# after a format change.
FIXTURE = ROOT / "tests" / "fixtures" / "anypoint_synthetic.json"
CLICKS_BNG = ([(lid, f) for lid in RIVER_LINKS for f in (0.15, 0.5, 0.85)]
              + [("in the lake", (419500, 455000)), ("beside the lake", (418700, 455000)),
                 ("in the lower lake", (420300, 447000)),
                 ("the lonely pool", (440500, 470500)), ("far from water", (412000, 456000)),
                 ("the kink by the pond", KINK),
                 ("west of Empty Water, nearer West Pond", (449900, 470500)), ("in Empty Water, nearer East Pond", (450900, 470500)),
                 ("north of Empty Water, no pond within 1.5 km", (450500, 473100)),
                 ("149 m off Notch Water's spit", (461161, 470500)), ("in Quiet Water", (499400, 500300))])


def _page_fixture(world, tmp_path, monkeypatch) -> dict:
    return {"note": "Made by tests/test_anypoint.py (_page_fixture); UPDATE_FIXTURES=1 writes it again.",
            "modes": {m: _page_fixture_in(world, tmp_path / m, monkeypatch, m) for m in MODES}}


def _page_fixture_in(world, tmp_path, monkeypatch, mode: str) -> dict:
    import base64
    monkeypatch.setattr(config, "LAKE_PATH_MODE", mode)
    bap = _bap()
    net, lakes, ov = world
    table, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", None)
    out = tmp_path / "anypoint"
    meta = bap.write_files(out, net, ov, table, "net0")
    files = {
        "cfg": {"network": "net0", "tile_deg": bap.TILE_DEG, "tiles": meta["tiles"], "snap_m": transport.PIN_SNAP_M,
                "lake_snap_m": transport.LAKE_SNAP_M, "lake_shore_m": transport.LAKE_SHORE_M, "lake_bias": transport.LAKE_BIAS},
        "lakes": json.loads((out / "lakes.json").read_text()), "ids": meta["ids"],
        "od": {"assumptions": {"max_upstream_km": 60.0, "l0_m": transport.L0_M, "lake_area_halving_km2": transport.LAKE_A0_KM2}},
        "tiles": {t: {"index": base64.b64encode((out / "link_index" / f"{t}.bin").read_bytes()).decode(),
                      "links": json.loads((out / "links" / f"{t}.json").read_text())["links"]} for t in meta["tiles"]},
        "outlines": {f.stem: json.loads(f.read_text()) for f in sorted((out / "lake_outlines").iterdir())},
    }
    clicks = []
    for what, where in CLICKS_BNG:
        if isinstance(where, float):
            at = net.links.at[what, "geometry"].interpolate(where, normalized=True)
            x, y, what = at.x, at.y, f"{what} at {where}"
        else:
            x, y = where
        lon, lat = bng_to_lonlat(x, y)
        pin, up = _api(net, ov, lon, lat)
        clicks.append({"what": what, "lat": round(lat, 7), "lon": round(lon, 7), "mode": pin.mode, "watercourse": pin.watercourse,
                       "adopted": bool(pin.adopted_main_channel),
                       "rows": [{"site_id": r.site_id, "distance_m": round(float(r.distance_m), 2),
                                 "lake_distance_m": round(float(r.lake_distance_m), 2), "dilution": round(float(r.dilution), 6),
                                 "travel_h": round(float(r.travel_h), 4), "decay": float(f"{float(r.decay):.6g}")}
                                for r in up.itertuples()]})
    return {"files": files, "clicks": clicks}


def test_the_page_fixture_still_says_what_the_api_says(world, tmp_path, monkeypatch):
    import os
    made = _page_fixture(world, tmp_path, monkeypatch)
    if os.environ.get("UPDATE_FIXTURES") == "1":
        FIXTURE.write_text(json.dumps(made, separators=(",", ":")) + "\n")
    kept_all = json.loads(FIXTURE.read_text())
    assert sorted(kept_all["modes"]) == sorted(MODES)
    for mode in MODES:
        kept, mine = kept_all["modes"][mode], made["modes"][mode]
        assert [c["what"] for c in kept["clicks"]] == [c["what"] for c in mine["clicks"]]
        for k, m in zip(kept["clicks"], mine["clicks"], strict=True):
            assert (k["mode"], k["watercourse"], k["adopted"]) == (m["mode"], m["watercourse"], m["adopted"]), k["what"]
            assert [r["site_id"] for r in k["rows"]] == [r["site_id"] for r in m["rows"]], k["what"]
            for a, b in zip(k["rows"], m["rows"], strict=True):
                assert a["distance_m"] == pytest.approx(b["distance_m"], abs=0.1), (mode, k["what"])
                assert a["lake_distance_m"] == pytest.approx(b["lake_distance_m"], abs=0.1), (mode, k["what"])
                assert a["dilution"] == pytest.approx(b["dilution"], abs=1e-5), (mode, k["what"])
                assert a["travel_h"] == pytest.approx(b["travel_h"], abs=1e-3), (mode, k["what"])
                assert a["decay"] == pytest.approx(b["decay"], rel=1e-5), (mode, k["what"])
        # The API, given no hint that the click is a lake, finds no river within 1.5 km of the lonely
        # pool; the page says it is a lake with no river connection, as the API does for a lake spot.
        assert {c["mode"] for c in kept["clicks"]} == {"river", "lake", "none"}
        assert next(c for c in kept["clicks"] if c["what"] == "the lonely pool")["mode"] == "none"
        assert sorted(kept["files"]["tiles"]) == sorted(mine["files"]["tiles"])
    # Below Test Water, mode "lake" puts lake metres on rows where mode "river" has none.
    def crossed(mode):
        return sum(r["lake_distance_m"] > 0 for c in kept_all["modes"][mode]["clicks"] if c["mode"] == "river" for r in c["rows"])
    assert crossed("lake") > 10 and crossed("river") == 0
