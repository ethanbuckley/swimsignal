"""The ten English river spots listed on 10 Nov 2026 (docs/SPOT-ADDITIONS-ENGLAND-2026-11-10.md): each pin is on the
OS Open Rivers line beside an Open Government Licence reference point (never an OpenStreetMap position, since
spots.csv must take no OpenStreetMap data), and each page carries the unconfirmed-access note. Network-free."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from dipcast.access import NOV10_CHECKED, NOV10_SPOTS, attach_access
from dipcast.network.rivers import lonlat_to_bng

ROOT = Path(__file__).resolve().parents[1]

# id: (river, reference easting, northing, source of the reference, most metres from it to the pin on the river)
REFERENCES = {
    "avon-barton-farm": ("River Avon", 382266, 160544, "NHLE 1364494 Barton Bridge", 50),
    "windrush-minster-lovell": ("River Windrush", 432435, 211332, "NHLE 1015321 Minster Lovell Hall", 100),
    "little-ouse-santon-downham": ("Little Ouse River", 582684, 287293, "NHLE 1015256 Santon moated site", 100),
    "barle-landacre": ("River Barle", 281649, 136129, "NHLE 1058006 Landacre Bridge", 50),
    "fowey-golitha-falls": ("River Fowey", 222332, 68623, "OS Open Names, Golitha Falls (waterfall)", 50),
    "fowey-respryn": ("River Fowey", 209936, 63492, "NHLE 1143087 Respryn Bridge", 50),
    "swale-kisdon-force": ("River Swale", 389869, 500971, "OS Open Names, Kisdon Force (waterfall)", 50),
    "south-tyne-featherstone": ("River South Tyne", 367378, 560955, "NHLE 1370307 Featherstone Castle", 250),
    "ribble-brungerley": ("River Ribble", 373840, 443020, "NHLE 1072154 Brungerley Farmhouse", 200),
    # OS Open Rivers: where Throstle Gill (lower Lingcove Beck) meets the River Esk, 30 m down the Esk.
    "esk-tongue-pot": ("River Esk", 322718, 503594, "OS Open Rivers node, Lingcove Beck confluence", 50),
}


def test_the_ten_are_curated_river_spots_at_their_reference_points():
    spots = pd.read_csv(ROOT / "spots.csv").fillna("").set_index("id")
    assert set(REFERENCES) == NOV10_SPOTS
    for sid, (river, e, n, _source, most) in REFERENCES.items():
        s = spots.loc[sid]
        assert (s["kind"], s["river"], s["source"]) == ("river", river, "curated"), sid
        x, y = lonlat_to_bng(float(s["lon"]), float(s["lat"]))
        assert math.hypot(x - e, y - n) <= most, sid


def test_none_of_the_ten_is_in_the_openstreetmap_file():
    osm = pd.read_csv(ROOT / "spots-osm.csv")
    assert not set(osm["id"]) & NOV10_SPOTS


def test_each_page_says_permission_has_not_been_confirmed():
    spots = [{"id": i, "source": "curated"} for i in sorted(NOV10_SPOTS)]
    assert attach_access(spots) == 10
    for s in spots:
        a = s["access"]
        assert a["status"] == "unconfirmed" and a["checked_at"] == NOV10_CHECKED, s["id"]
        assert "not been confirmed" in a["text"], s["id"]
    by_id = {s["id"]: s["access"] for s in spots}
    assert "Town Council" in by_id["avon-barton-farm"]["text"] and by_id["avon-barton-farm"]["url"].startswith("https://bradfordonavontowncouncil")
    assert "Forestry England" in by_id["little-ouse-santon-downham"]["text"]
    assert "Natural England" in by_id["fowey-golitha-falls"]["text"]
    assert "most of the lakes, tarns and rivers" in by_id["esk-tongue-pot"]["text"]


def test_places_ruled_out_on_10_nov_are_not_listed():
    # Eye Bridge (Stour): the OpenStreetMap river way is tagged swimming=no; Byron's Pool: Cam Conservancy byelaw
    # within 36 m of a weir; Kerne Bridge: the operator's signs discourage swimming; Lumb Falls: private, closed at
    # times; Geldeston: tidal. The doc gives each source.
    ids = set(pd.read_csv(ROOT / "spots.csv")["id"]) | set(pd.read_csv(ROOT / "spots-osm.csv")["id"])
    assert not ids & {"stour-eye-bridge", "cam-byrons-pool", "wye-kerne-bridge", "lumb-falls", "waveney-geldeston"}
