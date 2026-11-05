"""Carding Mill Valley Reservoir, Long Mynd (listed 28 Oct 2026): where the spot is and what the forecast can say of it.

The reservoir is too small for the EA's WFD lakes (the nearest, Bomere Pool, is 14.7 km away). OS Open Rivers draws it as
one lake link, 7713B5C1-B8ED-46B4-AF0F-42EB2BAFD908 (88.3 m, unnamed, flowing from SO 43599 94541 to SO 43658 94591), and
the spot is that link's midpoint. A Geograph photo titled "Carding Mill Valley Reservoir" (2398298, SO 435 945 to 100 m)
is 49 m from it. Placement follows the small-unmapped-lake rule (tests/test_placement.py,
test_a_small_unmapped_lake_keeps_its_own_centreline). Run against the real network on 28 Oct 2026, it placed the spot on
this link with no monitored overflow upstream, so the page says "No monitored overflow found upstream" and gives no
spill forecast. Here the same geometry, in a small network, pins that rule for this spot."""

from __future__ import annotations

import csv
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString

from dipcast import guides
from dipcast.model import transport
from dipcast.network.rivers import RiverNetwork, bng_to_lonlat, lonlat_to_bng

ROOT = Path(__file__).resolve().parents[1]
LINK = "7713B5C1-B8ED-46B4-AF0F-42EB2BAFD908"
MID = (343620.8, 294567.3)                               # the OS link's midpoint along its length, the spot
# The link's ends in flow direction (rounded to 1 m) with its midpoint between them: the OS line bends, and its midpoint
# is 6 m off the straight line between the ends. On the real network the spot is 0.1 m from the link (28 Oct 2026).
LAKE_XY = [(343599.0, 294541.0), MID, (343658.0, 294591.0)]


def _row() -> dict:
    return next(r for r in csv.DictReader((ROOT / "spots.csv").open()) if r["id"] == "carding-mill-reservoir")


def test_the_listed_spot_is_a_curated_lake_on_the_os_lake_link():
    r = _row()
    assert (r["kind"], r["source"], r["river"], r["area"]) == ("lake", "curated", "", "Severn and the Welsh borders")
    x, y = lonlat_to_bng(float(r["lon"]), float(r["lat"]))
    assert abs(x - MID[0]) < 2 and abs(y - MID[1]) < 2   # 5 decimal places: within about a metre of the midpoint
    # Not on the National Trust walk page's grid ref, SO411949, which is on the plateau, 2.5 km west.
    assert abs(x - 341100) > 2000


@pytest.fixture
def valley(monkeypatch):
    """The reservoir's link, a stream into it and the stream out of it, with an overflow downstream only. No WFD lakes."""
    links = [("IN", "inlandRiver", "s0", "lake_in", [(343300.0, 294300.0), LAKE_XY[0]]),
             (LINK, "lake", "lake_in", "lake_out", LAKE_XY),
             ("OUT", "inlandRiver", "lake_out", "s1", [LAKE_XY[-1], (344300.0, 294400.0)])]
    gdf = gpd.GeoDataFrame([{"id": i, "flow_direction": "in direction", "form": f, "fictitious": False,
                             "watercourse_name": None, "watercourse_name_alternative": None, "start_node": s,
                             "end_node": e, "geometry": LineString(xy)} for i, f, s, e, xy in links], crs=27700)
    monkeypatch.setattr(transport, "_lakes", lambda: gpd.GeoDataFrame({"wb_id": [], "lake_name": [], "area_km2": []},
                                                                     geometry=[], crs=27700))
    monkeypatch.setattr(transport, "_lake_polygon_at", lambda x, y: None)
    return RiverNetwork.from_links(gdf)


def _overflows(*on: tuple[str, str]) -> pd.DataFrame:
    return pd.DataFrame({"site_id": [s for s, _ in on], "link_id": [lid for _, lid in on], "frac": [0.5] * len(on),
                         "link_length": [300.0] * len(on), "start_node": [{"IN": "s0", "OUT": "lake_out"}[lid] for _, lid in on],
                         "has_live": [True] * len(on), "status": [0] * len(on)})


def test_placed_on_its_own_lake_link_with_nothing_monitored_upstream(valley):
    r = _row()
    pin = transport.locate_pin(valley, float(r["lon"]), float(r["lat"]), *transport.spot_hints("lake", ""), name=r["name"])
    assert (pin.mode, pin.lake_source, pin.lake_links) == ("lake", "centreline", {LINK})
    assert pin.snap.dist_m < 2
    # An overflow below the dam is not upstream of the reservoir: nothing monitored, so no spill forecast.
    assert transport.upstream_overflows(valley, pin, _overflows(("below", "OUT")), velocity_ms=0.5).empty
    # One on the stream above would count: the trace does run upstream from the lake.
    up = transport.upstream_overflows(valley, pin, _overflows(("above", "IN"), ("below", "OUT")), velocity_ms=0.5)
    assert list(up["site_id"]) == ["above"]


def test_a_point_off_the_water_is_not_this_reservoir(valley):
    # Over LAKE_UNMAPPED_M (500 m) from its link, a lake spot is some other water: isolated, never the stream's.
    far = transport.locate_pin(valley, *bng_to_lonlat(MID[0], MID[1] + 600), "lake", None, name="Carding Mill Valley Reservoir")
    assert far.mode == "isolated"


def test_its_guide_loads_with_the_owners_words_on_swimming():
    found, warnings = guides.load_guides({"carding-mill-reservoir"}, root=ROOT / "guides")
    assert not [w for w in warnings if "carding-mill-reservoir" in w], warnings
    g = found["carding-mill-reservoir"]
    facts = g["facts"]
    assert {f["topic"] for f in facts} == {"parking", "path", "toilets", "rules"}
    assert all(f["status"] == "confirmed" and f["source"].startswith("https://www.nationaltrust.org.uk/") for f in facts)
    rules = next(f["text"] for f in facts if f["topic"] == "rules")
    assert "invites a dip in the reservoir" in rules and "read the information at the reservoir" in rules
    assert g["how"] == "desk" and g["checked"] == "2026-10-28"


def test_the_page_says_no_monitored_overflow_for_a_spot_with_none():
    # levels.js gives both plain levels these words (FOUND_NONE): no spill forecast, and no claim of no risk.
    src = (ROOT / "src" / "dipcast" / "site" / "levels.js").read_text()
    assert "const FOUND_NONE = 'No monitored overflow found upstream';" in src
    assert "[NO_OVERFLOWS]: FOUND_NONE, [NO_RIVER]: FOUND_NONE" in src
