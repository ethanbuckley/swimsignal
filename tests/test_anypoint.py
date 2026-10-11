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
from shapely.geometry import LineString, box

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
]
LAKE_POLY = box(419000, 451800, 421000, 456200)          # 8.8 km2
LOWER_POLY = box(419400, 445900, 420600, 447900)         # 2.4 km2, 100 m below Outflow Beck's end
ALONE_POLY = box(440000, 470000, 441000, 471000)         # no lake centreline anywhere near


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
             ("A7", "D1", 0.1, "high"), ("A8", "O1", 0.5, "high")]
RIVER_LINKS = ["M1", "M2", "M3", "M4", "T1", "D1", "S1", "R1", "O1", "O2"]


@pytest.fixture
def world(monkeypatch):
    net = _net(LINKS)
    lakes = gpd.GeoDataFrame({"wb_id": ["GB1", "GB2", "GB3"], "lake_name": ["Test Water", "Lonely Pool", "Lower Water"],
                              "area_km2": [LAKE_POLY.area / 1e6, ALONE_POLY.area / 1e6, LOWER_POLY.area / 1e6]},
                             geometry=[LAKE_POLY, ALONE_POLY, LOWER_POLY], crs=27700)
    monkeypatch.setattr(transport, "_lakes", lambda: lakes)
    return net, lakes, _overflows(net, OVERFLOWS)


# The transport rules click-anywhere must follow: the defaults; lake path "river", the rule before
# 11 Oct 2026; and lake near "blend" (docs/LAKE-NEAR-FIELD-TEST-2026-10.md).
MODES = {"lake": {"LAKE_PATH_MODE": "lake", "LAKE_NEAR_MODE": "off"},
         "river": {"LAKE_PATH_MODE": "river", "LAKE_NEAR_MODE": "off"},
         "near": {"LAKE_PATH_MODE": "lake", "LAKE_NEAR_MODE": "blend"}}


def _set_mode(monkeypatch, mode: str) -> None:
    for k, v in MODES[mode].items():
        monkeypatch.setattr(config, k, v)


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


@pytest.mark.parametrize("mode", list(MODES))
def test_every_click_on_a_river_matches_the_api_trace(world, tmp_path, monkeypatch, mode):
    _set_mode(monkeypatch, mode)
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
    if MODES[mode]["LAKE_PATH_MODE"] == "lake":
        assert {("O1", "A5"), ("O1", "A6"), ("O2", "A5"), ("O2", "A6"), ("O2", "A8")} <= crossed
        o2 = _record(out, "O2", net, ids, bap)
        lower = 1 + LOWER_POLY.area / 1e6 / transport.LAKE_A0_KM2
        assert o2["path"]["A8"][1] == pytest.approx(1 / lower, abs=1e-6)
        assert o2["path"]["A5"][1] == pytest.approx(1 / lower / (1 + LAKE_POLY.area / 1e6 / transport.LAKE_A0_KM2), abs=1e-6)
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


@pytest.mark.parametrize("mode", list(MODES))
def test_a_lake_click_from_the_published_inlets_matches_the_api(world, tmp_path, monkeypatch, mode):
    _set_mode(monkeypatch, mode)
    bap = _bap()
    net, lakes, ov = world
    table, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", None)
    out = tmp_path / "anypoint"
    bap.write_files(out, net, ov, table, "net0")
    doc = json.loads((out / "lakes.json").read_text())
    ids = json.loads((out / "overflow_ids.json").read_text())["ids"]
    water, alone, lower = doc["polygons"]
    assert water["name"] == "Test Water" and isinstance(water["lake"], int) and alone["lake"] == -1
    assert lower["name"] == "Lower Water" and isinstance(lower["lake"], int)
    # A click in each lake. What the page does: from each inlet, the distance along the network less any
    # lake crossed on the way at the river velocity; that lake and the straight line to the click at the
    # lake velocity; the area term, times the factor of the lake crossed. Under lake near "blend" (near_m),
    # the dilution blends from the inlet's own river dilution (n) to that, with the straight line across.
    near_m = doc.get("near_m")
    assert (near_m is not None) == (MODES[mode]["LAKE_NEAR_MODE"] == "blend")
    for poly, click, sites in ((water, (419500, 455000), ["A5", "A6"]), (lower, (420300, 447000), ["A5", "A6", "A8"])):
        pin, want = _api(net, ov, *bng_to_lonlat(*click))
        assert pin.mode == "lake" and pin.lake_source == "polygon"
        rows = []
        for inlet in doc["lakes"][poly["lake"]]["inlets"]:
            ex, ey = lonlat_to_bng(*inlet["at"])
            path = {int(i): (m, f / bap.PATH_SCALE) for i, m, f in np.asarray(inlet.get("k", []), dtype=float).reshape(-1, 3)}
            near = {int(i): n / bap.DIL_SCALE for i, n in np.asarray(inlet.get("n", []), dtype=float).reshape(-1, 2)}
            for i, d, w in np.asarray(inlet["o"], dtype=float).reshape(-1, 3):
                m, factor = path.get(int(i), (0.0, 1.0))
                across = math.hypot(ex - click[0], ey - click[1])
                d_lake = across + m
                travel = ((d - m) / 0.5 + d_lake / 0.05) / 3600
                dil = w / bap.DIL_SCALE / (1 + poly["area_km2"] / 5)
                if near_m:
                    f = math.exp(-across / near_m)
                    dil = near[int(i)] * f + dil * (1 - f)
                rows.append((ids[int(i)], d - m, d_lake, 10 ** (-travel / 30) * dil * factor))
        got = pd.DataFrame(rows, columns=["site_id", "distance_m", "lake_distance_m", "weight"])
        got = got.sort_values("site_id").reset_index(drop=True)
        assert list(got["site_id"]) == list(want["site_id"]) == sites
        assert np.allclose(got["distance_m"], want["distance_m"], atol=1.0)
        assert np.allclose(got["lake_distance_m"], want["lake_distance_m"], atol=2.0)
        assert np.allclose(got["weight"], want["weight"], rtol=2e-3)
        # In the lower lake, water from above Test Water has crossed it in mode "lake" only.
        if poly is lower:
            a5 = want.set_index("site_id").loc["A5"]
            assert (a5["lake_distance_m"] > 4_000) == (MODES[mode]["LAKE_PATH_MODE"] == "lake")


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
                 ("the lonely pool", (440500, 470500)), ("far from water", (412000, 456000))])


def _page_fixture(world, tmp_path, monkeypatch) -> dict:
    return {"note": "Made by tests/test_anypoint.py (_page_fixture); UPDATE_FIXTURES=1 writes it again.",
            "modes": {m: _page_fixture_in(world, tmp_path / m, monkeypatch, m) for m in MODES}}   # every rule


def _page_fixture_in(world, tmp_path, monkeypatch, mode: str) -> dict:
    import base64
    _set_mode(monkeypatch, mode)
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
                                 "lake_distance_m": round(float(r.lake_distance_m), 2), "dilution": round(float(r.dilution), 6)}
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
        # The API, given no hint that the click is a lake, finds no river within 1.5 km of the lonely
        # pool; the page says it is a lake with no river connection, as the API does for a lake spot.
        assert {c["mode"] for c in kept["clicks"]} == {"river", "lake", "none"}
        assert next(c for c in kept["clicks"] if c["what"] == "the lonely pool")["mode"] == "none"
        assert sorted(kept["files"]["tiles"]) == sorted(mine["files"]["tiles"])
    # Below Test Water, mode "lake" puts lake metres on rows where mode "river" has none.
    def crossed(mode):
        return sum(r["lake_distance_m"] > 0 for c in kept_all["modes"][mode]["clicks"] if c["mode"] == "river" for r in c["rows"])
    assert crossed("lake") > 10 and crossed("near") > 10 and crossed("river") == 0
