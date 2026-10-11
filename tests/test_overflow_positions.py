"""Where an overflow is put on the river network: outfalls to the ground stay off it, the annual-return
outlet wins when it alone is by the named water, checked joins move an outfall on an undrawn stream,
and the build lists outfalls whose join could fall below a spot. Network-free: a few links in memory."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from dipcast import overflows
from dipcast.network.rivers import RiverNetwork, bng_to_lonlat

ROOT = Path(__file__).resolve().parents[1]


def _net(links: list[tuple]) -> RiverNetwork:
    """links: (id, name, start node, end node, [(x, y), ...]), in flow direction."""
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": "inlandRiver", "fictitious": False,
          "watercourse_name": n, "watercourse_name_alternative": None, "start_node": s, "end_node": e,
          "geometry": LineString(xy)} for i, n, s, e, xy in links], crs=27700)
    return RiverNetwork.from_links(gdf)


def test_only_an_outfall_every_name_puts_in_the_ground_stays_off_the_network():
    live = pd.Series(["SEWAGE FARM", "Groundwater", "River Wey", "LAND YEO", "Groundwater", "Soakaway????", None, "Onto land"])
    ret = pd.Series(["GROUNDWATERS VIA 2 INFILT SYST", "Not Applicable", "RIVER WEY AND GROUNDWATER", "LAND YEO",
                     "TRIB OF BYDEMILL BROOK/LAND", "Unnamed watercourse", "GROUNDWATER VIA INFILT SYSTEM", "LAND"])
    assert overflows.to_ground(live, ret).tolist() == [True, True, False, False, False, False, True, True]


# The Wye runs east along y = 372000. Buxton STW's live position is 45 km away by an unnamed drain;
# its annual-return outlet is 20 m from the Wye.
WYE = [("W1", "River Wye", "a", "b", [(405000, 372000), (408000, 372000)]),
       ("D1", None, "c", "d", [(399000, 327000), (399000, 329000)])]


def _row(live_xy, ar_xy, recv="RIVER WYE", recv_ar="RIVER WYE"):
    lon, lat = bng_to_lonlat(*live_xy) if live_xy else (np.nan, np.nan)
    alon, alat = bng_to_lonlat(*ar_xy) if ar_xy else (np.nan, np.nan)
    return {"site_id": "SVT00446", "lat": lat, "lon": lon, "ar_lat": alat, "ar_lon": alon,
            "receiving_watercourse": recv, "receiving_water": recv_ar}


def test_the_outlet_wins_only_when_it_alone_is_by_the_named_water():
    net = _net(WYE)
    df = pd.DataFrame([_row((399010, 328000), (406700, 372020)),      # live by an unnamed drain: outlet wins
                       _row((406000, 372030), (406700, 372020)),      # both by the Wye: live kept
                       _row((399010, 328000), (399020, 328500)),      # neither: live kept
                       _row(None, (406700, 372020))])                 # no live position: the outlet, as before
    out = overflows.choose_positions(net, df)
    assert out["position_source"].tolist() == ["annual return", "live", "live", "annual return"]
    assert out.loc[0, "lat"] == df.loc[0, "ar_lat"] and out.loc[1, "lat"] == df.loc[1, "lat"]


def test_a_checked_join_moves_the_outfall_and_says_so(tmp_path):
    p = tmp_path / "joins.csv"
    p.write_text("# a comment\nsite_id,join_lat,join_lon,stream,checked,how\nYWS00002,53.38178,-1.55639,Black Brook,2026-10-11,x\n")
    df = pd.DataFrame({"site_id": ["YWS00002", "YWS00003"], "lat": [53.37365, 53.0], "lon": [-1.56017, -1.0],
                       "position_source": ["live", "live"]})
    out = overflows.apply_joins(df, p)
    assert out.loc[0, ["lat", "lon", "position_source"]].tolist() == [53.38178, -1.55639, "join"]
    assert out.loc[1, "position_source"] == "live"


def test_the_repo_joins_file_reads():
    j = pd.read_csv(ROOT / "data" / "raw" / "overflow_joins.csv", comment="#")
    assert list(j.columns) == ["site_id", "join_lat", "join_lon", "stream", "checked", "how"]
    assert j["site_id"].is_unique and j[["join_lat", "join_lon"]].notna().all().all()


def test_on_named_reads_the_snapped_links_name_and_not_the_river_a_tributary_joins():
    net = _net(WYE)
    df = pd.DataFrame({"link_id": ["W1", "D1", None, "W1", "W1"],
                       "receiving_watercourse": ["RIVER WYE", "RIVER WYE", "RIVER WYE",
                                                 "Harrow Beck, a Tributary of the River Wye Via SWS", "TRIB OF RIVER WYE"]})
    assert overflows.on_named(net, df).tolist() == [True, False, False, False, False]
    assert overflows.own_water("Harrow Beck, a Tributary of the River Eden") == {"harrow"}


def _build_site():
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_build_lists_outfalls_that_could_join_below_a_spot():
    bs = _build_site()
    up = {"osm-rivelin-plunge-pool": [
        {"site_id": "YWS00002", "snap_m": 709, "distance_km": 0.7, "on_named": False, "position_source": "live",
         "receiving_watercourse": "Unnamed Trib Of Black Brook"},
        {"site_id": "NEAR", "snap_m": 709, "distance_km": 3.0, "on_named": False},          # far above: fine
        {"site_id": "ONIT", "snap_m": 300, "distance_km": 0.3, "on_named": True},           # on its named stream
        {"site_id": "JOIN", "snap_m": 5, "distance_km": 0.2, "position_source": "join"},
        {"site_id": "OLD", "distance_km": 0.1}]}                                            # a table without snap_m
    got = bs.unsure_joins(up)
    assert [g["site_id"] for g in got] == ["YWS00002"]
    assert got[0] == {"spot": "osm-rivelin-plunge-pool", "site_id": "YWS00002", "snap_m": 709, "km": 0.7,
                      "receiving": "Unnamed Trib Of Black Brook"}


def test_when_names_decide_nothing_the_outlet_by_the_named_place_wins(monkeypatch):
    """Earl Sterndale STW: Glutton Brook is not named in OS Open Rivers at either position; the live
    position is by Hartington, 6.7 km off, the outlet by the village."""
    net = _net(WYE)
    village, other = (408350, 366650), (415000, 362000)
    monkeypatch.setattr(overflows, "_places", lambda: {"earl sterndale": np.array([village])})
    row = _row(other, (village[0] + 300, village[1]), recv="GLUTTON BROOK", recv_ar="Glutton Brook")
    df = pd.DataFrame([row | {"site_name": "EARL STERNDALE STW (CSO)"},
                       # receiving waters disagree: two assets under one id, so nothing moves
                       row | {"site_name": "EARL STERNDALE STW (CSO)", "receiving_water": "NORTH SEA"},
                       # no place in the name: nothing moves
                       row | {"site_name": "MAIN STREET CSO"},
                       # under PLACE_GAP_M apart: nothing moves
                       _row((village[0] + 900, village[1]), village, recv="GLUTTON BROOK") | {"site_name": "EARL STERNDALE STW"}])
    out = overflows.choose_positions(net, df)
    assert out["position_source"].tolist() == ["annual return", "live", "live", "live"]
    # a generic name on one side does not block it ("FRESHWATER RIVER" for Hazeldene Lane, Newick)
    assert overflows._same_water("OUSE", "FRESHWATER RIVER") and not overflows._same_water("WEY", "RIVER KIRD")


def test_the_build_lists_an_uncounted_outfall_at_a_spot():
    """Wetherby High Street CSO, 5 m from the Wharfe at Wilderness Carpark, snapped onto a stub that
    joins below the bathing water point, so not counted there."""
    bs = _build_site()
    lon, lat = -1.38542, 53.92655
    ov = pd.DataFrame({"site_id": ["YWS00033", "FAR", "UNSNAPPED"], "lat": [53.926505, 53.93, 53.92655],
                       "lon": [-1.385434, -1.39, -1.38542], "link_id": ["stub", "x", None]})
    results = [{"id": "bw-uke4200-08904", "lat": lat, "lon": lon}, {"id": "nolatlon"}]
    assert bs.near_uncounted(results, {"bw-uke4200-08904": []}, ov) == [
        {"spot": "bw-uke4200-08904", "site_id": "YWS00033", "metres": 5}]
    assert bs.near_uncounted(results, {"bw-uke4200-08904": [{"site_id": "YWS00033"}]}, ov) == []


def test_a_settled_join_at_a_spot_is_not_listed():
    """Abbey Mill CSO, Knaresborough: placed by the joins file 29 m below the Lido and kept uncounted,
    per the EA's profile. The joins file settles it, so the build does not list it."""
    bs = _build_site()
    lon, lat = -1.45145, 53.9982
    ov = pd.DataFrame({"site_id": ["YWS00278", "OTHER"], "lat": [53.998403, 53.99821],
                       "lon": [-1.451726, -1.45146], "link_id": ["below", "below"],
                       "position_source": ["join", "live"]})
    results = [{"id": "bw-uke2203-08903", "lat": lat, "lon": lon}]
    assert bs.near_uncounted(results, {"bw-uke2203-08903": []}, ov) == [
        {"spot": "bw-uke2203-08903", "site_id": "OTHER", "metres": 1}]
