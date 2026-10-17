"""Click anywhere in lake distance "water" (docs/LAKE-DISTANCE-2026-10.md): the published lake files give a click
the API's way through the lake's water. Network-free, as test_anypoint.py: a beck runs east into an L-shaped lake,
along its first arm and up its second, and out of the top. tests/site_anypoint.test.cjs runs the page on the files
kept in tests/fixtures/anypoint_water.json; UPDATE_FIXTURES=1 writes it again."""

from __future__ import annotations

import base64
import json
import math
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box
from test_anypoint import _api, _bap, _net, _overflows

from dipcast import config
from dipcast.model import transport
from dipcast.network.rivers import bng_to_lonlat

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "anypoint_water.json"
LINKS = [
    ("R1", "Inflow Beck", "inlandRiver", "r0", "k0", [(415000, 450000), (420000, 450000)]),
    ("K1", "Ell Water", "lake", "k0", "k1", [(420000, 450000), (423750, 450000)]),
    ("K2", "Ell Water", "lake", "k1", "k2", [(423750, 450000), (423750, 454000)]),
    ("O1", "Outflow Beck", "inlandRiver", "k2", "o1", [(423750, 454000), (423750, 457000)]),
]
ELL = box(420000, 449750, 424000, 450250).union(box(423500, 449750, 424000, 454000))   # inner corner (423500, 450250)
OVERFLOWS = [("A1", "R1", 0.5, "high"), ("A2", "K1", 0.3, "high")]
CLICKS = [("up the second arm", (423750, 453800)), ("in the first arm", (421500, 450100)),
          ("round the corner", (423600, 451000)), ("on the shore beyond the end", (423750, 454100)),
          ("off the second arm, by its centreline", (424500, 452000))]


@pytest.fixture
def world(monkeypatch):
    net = _net(LINKS)
    lakes = gpd.GeoDataFrame({"wb_id": ["GBL"], "lake_name": ["Ell Water"], "area_km2": [ELL.area / 1e6]},
                             geometry=[ELL], crs=27700)
    monkeypatch.setattr(transport, "_lakes", lambda: lakes)
    monkeypatch.setattr(config, "LAKE_DISTANCE_MODE", "water")
    return net, lakes, _overflows(net, OVERFLOWS)


def _made(world, tmp_path) -> dict:
    bap = _bap()
    net, lakes, ov = world
    table, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", None)
    out = tmp_path / "anypoint"
    meta = bap.write_files(out, net, ov, table, "net0")
    files = {
        "cfg": {"network": "net0", "tile_deg": bap.TILE_DEG, "tiles": meta["tiles"], "snap_m": transport.PIN_SNAP_M,
                "lake_snap_m": transport.LAKE_SNAP_M, "lake_shore_m": transport.LAKE_SHORE_M, "lake_bias": transport.LAKE_BIAS},
        "lakes": json.loads((out / "lakes.json").read_text()), "ids": meta["ids"],
        "waters": {f.stem: json.loads(f.read_text()) for f in sorted((out / "lake_water").glob("*.json"))},
        "od": {"assumptions": {"max_upstream_km": 60.0, "l0_m": transport.L0_M, "lake_area_halving_km2": transport.LAKE_A0_KM2,
                               "dilution_power": transport.DILUTION_POWER, "river_velocity_ms": config.RIVER_VELOCITY_MS,
                               "lake_velocity_ms": config.LAKE_VELOCITY_MS, "t90_hours": config.T90_HOURS}},
        "tiles": {t: {"index": base64.b64encode((out / "link_index" / f"{t}.bin").read_bytes()).decode(),
                      "links": json.loads((out / "links" / f"{t}.json").read_text())["links"]} for t in meta["tiles"]},
    }
    clicks = []
    for what, (x, y) in CLICKS:
        lon, lat = bng_to_lonlat(x, y)
        pin, up = _api(net, ov, lon, lat)
        line = transport.upstream_overflows(net, pin, ov.drop(columns="snap_confidence"), velocity_ms=0.5,
                                            lake_distance_mode="line").set_index("site_id")
        clicks.append({"what": what, "lat": round(lat, 7), "lon": round(lon, 7), "mode": pin.mode, "source": pin.lake_source,
                       "rows": [{"site_id": r.site_id, "lake_distance_m": round(float(r.lake_distance_m), 2),
                                 "line_m": round(float(line.loc[r.site_id, "lake_distance_m"]), 2),
                                 "travel_h": round(float(r.travel_h), 4)} for r in up.itertuples()]})
    return {"note": "Made by tests/test_anypoint_water.py; UPDATE_FIXTURES=1 writes it again.", "files": files, "clicks": clicks}


def test_the_lake_files_carry_the_water_and_the_clicks_go_round_the_corner(world, tmp_path):
    made = _made(world, tmp_path)
    lakes = made["files"]["lakes"]["lakes"]
    n = next(i for i, k in enumerate(lakes) if k["id"].startswith("w"))
    # The water is in its own file, not in lakes.json, which every click fetches.
    assert lakes[n]["water"] is True and not any("w" in i for i in lakes[n]["inlets"])
    water = made["files"]["waters"][str(n)]
    assert len(water["corners"]) == 1 and len(water["ways"]) == len(lakes[n]["inlets"])
    assert set(made["files"]["waters"]) == {str(i) for i, k in enumerate(lakes) if k.get("water")}
    by = {c["what"]: c for c in made["clicks"]}
    assert [c["mode"] for c in made["clicks"]] == ["lake"] * 5
    assert by["off the second arm, by its centreline"]["source"] == "centreline"
    for c in made["clicks"]:
        for r in c["rows"]:
            assert r["lake_distance_m"] >= r["line_m"] - 0.01, (c["what"], r)
    # Up the second arm, the way from the beck's mouth goes round the inner corner; in the first arm it is straight.
    a1 = next(r for r in by["up the second arm"]["rows"] if r["site_id"] == "A1")
    via = math.dist((420000, 450000), (423500, 450250)) + math.dist((423500, 450250), (423750, 453800))
    assert a1["lake_distance_m"] == pytest.approx(via, abs=1.0) and a1["line_m"] < via - 400
    assert all(r["lake_distance_m"] == pytest.approx(r["line_m"], abs=0.01) for r in by["in the first arm"]["rows"])
    # Beyond the end and off the arm, the leg to the water is added.
    off = next(r for r in by["off the second arm, by its centreline"]["rows"] if r["site_id"] == "A1")
    assert off["lake_distance_m"] == pytest.approx(math.dist((420000, 450000), (423500, 450250))
                                                   + math.dist((423500, 450250), (424000, 452000)) + 500, abs=1.0)


def test_the_page_fixture_still_says_what_the_api_says(world, tmp_path):
    made = _made(world, tmp_path)
    if os.environ.get("UPDATE_FIXTURES") == "1":
        FIXTURE.write_text(json.dumps(made, separators=(",", ":")) + "\n")
    kept = json.loads(FIXTURE.read_text())
    assert kept["files"]["lakes"] == made["files"]["lakes"] and kept["files"]["waters"] == made["files"]["waters"]
    assert [c["what"] for c in kept["clicks"]] == [c["what"] for c in made["clicks"]]
    for k, m in zip(kept["clicks"], made["clicks"], strict=True):
        assert k["mode"] == m["mode"] and [r["site_id"] for r in k["rows"]] == [r["site_id"] for r in m["rows"]]
        for a, b in zip(k["rows"], m["rows"], strict=True):
            assert a["lake_distance_m"] == pytest.approx(b["lake_distance_m"], abs=0.1), k["what"]


def test_in_lake_distance_line_the_files_carry_no_water(world, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LAKE_DISTANCE_MODE", "line")
    bap = _bap()
    net, lakes, ov = world
    table, _ = bap.upstream_table(net, ov, lakes, "net0", "lakes0", None)
    bap.write_files(tmp_path, net, ov, table, "net0")
    doc = json.loads((tmp_path / "lakes.json").read_text())
    assert doc["lakes"] and not any("water" in k for k in doc["lakes"]) and not any((tmp_path / "lake_water").iterdir())
    assert pd.notna(doc["polygons"][0]["lake"])
