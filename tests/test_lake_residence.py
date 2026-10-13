"""Lake path 'residence' (off by default; docs/LAKE-RESIDENCE-TEST-2026-10.md): a WFD lake crossed on the way that
has a residence time is a well-mixed lake. Network-free, the layout of test_lake_path.py: a river, a 4 km lake
(row 0), a river, a mill pond outside every polygon, a river with the river spot half way, then a second lake
(row 1) and its outflow."""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, box

from dipcast import config
from dipcast.model import transport
from dipcast.network.rivers import RiverNetwork, Snap

LINKS = [
    ("r1", "a", "b", "inlandRiver", [(0, 0), (10_000, 0)]),
    ("L1", "b", "c", "lake", [(10_000, 0), (12_000, 0)]),
    ("L2", "c", "d", "lake", [(12_000, 0), (14_000, 0)]),
    ("r2", "d", "e", "inlandRiver", [(14_000, 0), (24_000, 0)]),
    ("p1", "e", "f", "lake", [(24_000, 0), (25_000, 0)]),
    ("r3", "f", "g", "inlandRiver", [(25_000, 0), (35_000, 0)]),
    ("Q1", "g", "h", "lake", [(35_000, 0), (37_000, 0)]),
    ("r4", "h", "i", "inlandRiver", [(37_000, 0), (40_000, 0)]),
]
LAKE_KM2, DOWN_KM2 = 4.0, 2.0
LAKES = gpd.GeoDataFrame({"wb_id": ["GBUPPER", "GBLOWER"], "lake_name": ["Upper", "Lower"],
                          "area_km2": [LAKE_KM2, DOWN_KM2]},
                         geometry=[box(10_000, -500, 14_000, 500), box(35_000, -500, 37_000, 500)], crs=27700)
TAU_D = 38.9                     # Grasmere's residence time in data/raw/lake_residence.csv (HydroLAKES)
K = math.log(10) / config.T90_HOURS


@pytest.fixture(scope="module")
def net() -> RiverNetwork:
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": f, "fictitious": False, "watercourse_name": "Beck",
          "watercourse_name_alternative": None, "start_node": s, "end_node": e, "geometry": LineString(xy)}
         for i, s, e, f, xy in LINKS], crs=27700)
    return RiverNetwork.from_links(gdf)


@pytest.fixture(autouse=True)
def lakes(monkeypatch, tmp_path):
    monkeypatch.setattr(transport, "_lakes", lambda: LAKES)
    f = tmp_path / "lake_residence.csv"
    pd.DataFrame({"wb_id": ["GBUPPER"], "res_time_d": [TAU_D]}).to_csv(f, index=False)
    monkeypatch.setattr(config, "LAKE_RESIDENCE_FILE", f)


def _overflows(net: RiverNetwork) -> pd.DataFrame:
    rows = [("above", "r1", 0.5), ("in_lake", "L2", 0.5), ("below", "r2", 0.5)]
    return pd.DataFrame([{"site_id": s, "link_id": lid, "frac": f, "link_length": net.links.loc[lid, "length"],
                          "start_node": net.links.loc[lid, "start_node"]} for s, lid, f in rows])


def _river_pin() -> transport.PinLocation:
    return transport.PinLocation("river", 30_000, 0, Snap("r3", 0.5, 0.0, "inlandRiver", 30_000, 0),
                                 trace_node="f", trace_offset_m=5_000.0)


def _lake_pin() -> transport.PinLocation:
    return transport.PinLocation("lake", 36_000, 300, Snap("Q1", 0.5, 300.0, "lake", 36_000, 0), {"Q1"}, "h",
                                 trace_node="h", lake_area_km2=DOWN_KM2, lake_source="polygon")


def _trace(net, pin=None, **kw) -> pd.DataFrame:
    up = transport.upstream_overflows(net, pin or _river_pin(), _overflows(net),
                                      velocity_ms=kw.pop("velocity_ms", 0.5), **kw)
    return up.set_index("site_id")


def test_the_default_is_unchanged(net):
    assert config.LAKE_PATH_MODE == "lake"
    assert _trace(net).equals(_trace(net, lake_path_mode="lake"))


def test_the_well_mixed_lake():
    tau = TAU_D * 24
    assert transport.lake_pass(tau) == pytest.approx(1 / (1 + K * tau))
    assert transport.lake_hold_h(tau) == pytest.approx(1 / (1 / tau + K))
    # a lake that empties far faster than bacteria die passes nearly all; one that holds water for weeks, little
    assert transport.lake_pass(0.1) > 0.99
    assert transport.lake_pass(tau) < 0.02


def test_a_lake_with_a_residence_time_is_crossed_as_a_well_mixed_lake(net):
    lake, res = _trace(net, lake_path_mode="lake"), _trace(net, lake_path_mode="residence")
    tau = TAU_D * 24
    # the distances are lake path 'lake''s
    assert res.loc["above", "distance_m"] == pytest.approx(lake.loc["above", "distance_m"])
    assert res.loc["above", "lake_distance_m"] == pytest.approx(4_000)
    # the time in the lake is the survivors' mean time in it, not 4 km at LAKE_VELOCITY_MS
    river_h = 21_000 / 0.5 / 3600
    assert res.loc["above", "travel_h"] == pytest.approx(river_h + transport.lake_hold_h(tau))
    # die-off on the river, times the share that leaves the lake alive; no area factor
    assert res.loc["above", "decay"] == pytest.approx(10 ** (-river_h / config.T90_HOURS) / (1 + K * tau))
    river = _trace(net, lake_path_mode="river")
    assert res.loc["above", "dilution"] == pytest.approx(river.loc["above", "dilution"])
    # Face check: a spill that crosses a lake holding water for 39 days keeps under 2% of the weight it has when
    # the lake is walked as river
    assert res.loc["above", "weight"] < 0.02 * river.loc["above", "weight"]
    # below the lake nothing changes
    assert res.loc["below"].equals(lake.loc["below"])


def test_an_outfall_on_the_lake_mixes_into_all_of_it(net):
    res = _trace(net, lake_path_mode="residence")
    tau = TAU_D * 24
    river_h = (10_000 + 1_000 + 5_000) / 0.5 / 3600   # r2, the pond and half of r3; L2 is lake
    assert res.loc["in_lake", "lake_distance_m"] == pytest.approx(1_000)
    assert res.loc["in_lake", "travel_h"] == pytest.approx(river_h + transport.lake_hold_h(tau))
    assert res.loc["in_lake", "decay"] == pytest.approx(10 ** (-river_h / config.T90_HOURS) * transport.lake_pass(tau))


def test_a_lake_without_a_residence_time_is_crossed_as_in_lake_mode(net, monkeypatch, tmp_path):
    f = tmp_path / "none.csv"
    pd.DataFrame({"wb_id": ["GBOTHER"], "res_time_d": [10.0]}).to_csv(f, index=False)
    monkeypatch.setattr(config, "LAKE_RESIDENCE_FILE", f)
    assert _trace(net, lake_path_mode="residence").equals(_trace(net, lake_path_mode="lake"))


def test_a_lake_pin_keeps_its_own_lake_and_mixes_the_one_on_the_way(net):
    lake, res = _trace(net, _lake_pin(), lake_path_mode="lake"), _trace(net, _lake_pin(), lake_path_mode="residence")
    tau = TAU_D * 24
    entry = math.hypot(1_000, 300)
    assert res.loc["above", "lake_distance_m"] == pytest.approx(lake.loc["above", "lake_distance_m"])
    moving_h = (26_000 / 0.5 + entry / config.LAKE_VELOCITY_MS) / 3600   # the spot's own lake is still crossed
    assert res.loc["above", "travel_h"] == pytest.approx(moving_h + transport.lake_hold_h(tau))
    assert res.loc["above", "decay"] == pytest.approx(10 ** (-moving_h / config.T90_HOURS) * transport.lake_pass(tau))
    # the spot's own-lake factor stays; the lake on the way loses its area factor
    assert res.loc["above", "dilution"] == pytest.approx(lake.loc["above", "dilution"] * (1 + LAKE_KM2 / transport.LAKE_A0_KM2))
    assert res.loc["below"].equals(lake.loc["below"])


def test_catchment_speed_with_residence(net):
    res = _trace(net, velocity_mode="catchment", lake_path_mode="residence")
    lake = _trace(net, velocity_mode="catchment", lake_path_mode="lake")
    tau = TAU_D * 24
    lake_h = 4_000 / config.LAKE_VELOCITY_MS / 3600
    assert res.loc["above", "travel_h"] == pytest.approx(lake.loc["above", "travel_h"] - lake_h + transport.lake_hold_h(tau))


def test_residence_spill_reads_its_own_file(net, monkeypatch, tmp_path):
    f = tmp_path / "spill.csv"
    pd.DataFrame({"wb_id": ["GBUPPER"], "res_time_d": [TAU_D / 4]}).to_csv(f, index=False)
    monkeypatch.setattr(config, "LAKE_RESIDENCE_SPILL_FILE", f)
    assert transport.lake_residence_h("residence_spill") == {0: pytest.approx(TAU_D / 4 * 24)}
    spill, res = _trace(net, lake_path_mode="residence_spill"), _trace(net, lake_path_mode="residence")
    tau = TAU_D / 4 * 24
    assert spill.loc["above", "decay"] == pytest.approx(10 ** (-21_000 / 0.5 / 3600 / config.T90_HOURS) * transport.lake_pass(tau))
    assert spill.loc["above", "weight"] > res.loc["above", "weight"]   # a quicker lake removes less
    assert spill.loc["below"].equals(res.loc["below"])


def test_the_residence_file_is_read_by_water_body(net):
    got = transport.lake_residence_h()
    assert got == {0: pytest.approx(TAU_D * 24)}


def test_the_committed_table():
    t = pd.read_csv(config.RAW / "lake_residence.csv")
    assert t["wb_id"].is_unique and (t["res_time_d"] > 0).all()
    g = t.set_index("lake_name")
    assert g.loc["Grasmere", "res_time_d"] == pytest.approx(38.9)
    # Windermere's two basins share one HydroLAKES lake: each takes its share of the volume
    w = t[t["lake_name"].str.startswith("Windermere")]
    assert len(w) == 2 and np.allclose(w["res_time_d"], w["hl_res_time_d"] * w["area_share"])
    assert "Elter Water" not in set(t["lake_name"])   # not in HydroLAKES: crossed as in lake path 'lake'
