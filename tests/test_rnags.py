"""Reasons a water body does not reach good status (scripts/make_rnags.py, data/raw/rnags.json) and the
field the build passes to a spot's page for them (build_site.attach_water_body). The page's words are
tested in tests/site_evidence.test.cjs."""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site
import make_rnags

HEAD = ('"Water Body ID","Water Body","Water Body Type","Reason Type","Category","Category Certainty",'
        '"National Swmi Header","Swmi","Activity","Classification Element"\n')


def _csv(*rows: str) -> bytes:
    return (HEAD + "\n".join(rows) + "\n").encode()


def test_kept_reasons_are_confirmed_or_probable_rnags_one_per_sector_and_issue():
    raw = _csv(
        '"GB1","Wye - A to B","River","RNAG","Agriculture and rural land management","Probable","Pollution from rural areas",'
        '"Diffuse source","Poor nutrient management","Phosphate"',
        '"GB1","Wye - A to B","River","RNAG","Agriculture and rural land management","Confirmed","Pollution from rural areas",'
        '"Diffuse source","Poor Livestock Management","Fish"',
        # Suspected, a reason for deterioration and a sector under investigation are not kept.
        '"GB1","Wye - A to B","River","RNAG","Water Industry","Suspected","Pollution from waste water","Point source","x","Fish"',
        '"GB1","Wye - A to B","River","RFD","Urban and transport","Confirmed","Pollution from towns, cities and transport",'
        '"Diffuse source","x","Fish"',
        '"GB1","Wye - A to B","River","RNAG","Sector under investigation","Not applicable",,'
        '"Unknown (pending investigation)","Unknown (pending investigation)","Temperature"',
        '"GB2","Wye - B to C","River","RNAG","No sector responsible","Not applicable",,'
        '"measures delivered to address reason, awaiting recovery","Not applicable","Mercury and Its Compounds"')
    bodies, n, kept = make_rnags.water_bodies(raw)
    assert (n, kept) == (6, 2)
    assert bodies["GB1"] == {"name": "Wye - A to B", "type": "River", "pressures": [{
        "sector": "Agriculture and rural land management", "issue": "Pollution from rural areas",
        "certainty": "confirmed",   # the strongest of its two rows
        "sources": ["Diffuse source"], "activities": ["Poor Livestock Management", "Poor nutrient management"],
        "elements": ["Fish", "Phosphate"]}]}
    # A water body the file has, with no reason kept, is listed: told apart from one it does not have.
    assert bodies["GB2"]["pressures"] == []


def test_a_changed_file_stops_the_script_rather_than_writing_nothing():
    try:
        make_rnags.water_bodies(b'"Water Body ID","Water Body"\n"GB1","x"\n')
    except SystemExit as e:
        assert "lost the column" in str(e)
    else:
        raise AssertionError("expected the script to stop")


def test_river_words_are_the_name_before_its_reach():
    assert make_rnags.river_words("Wye - Bredwardine Br to Hampton Bishop") == {"wye"}
    assert make_rnags.river_words("Yazor Bk - source to conf R Wye") == {"yazor"}
    assert make_rnags.river_words("Lugg - conf R Arrow to conf R Wye") == {"lugg"}
    assert make_rnags.river_words("Wharfe from Hundwith Beck to River Washburn") == {"wharfe"}
    assert make_rnags.river_words("Thames (Evenlode to Thame)") == {"thames"}
    assert make_rnags.river_words(None) == set()


def _geo() -> gpd.GeoDataFrame:
    """Two stretches of the Wye meeting at x = 1000, a tributary (Yazor Brook) joining at x = 500, and the
    upper stretch's catchment reaching 800 m above where its line starts (x = -800 to 1000)."""
    rows = [("GB_UP", "Wye - source to Hereford", "RiverLine", LineString([(0, 0), (1000, 0)])),
            ("GB_DOWN", "Wye - Hereford to Ross", "RiverLine", LineString([(1000, 0), (3000, 0)])),
            ("GB_TRIB", "Yazor Bk - source to conf R Wye", "RiverLine", LineString([(500, 0), (500, 2000)])),
            ("GB_UP", "Wye - source to Hereford", "Catchment", Polygon([(-800, -300), (1000, -300), (1000, 300), (-800, 300)]))]
    return gpd.GeoDataFrame([{"id": i, "name": n, "kind": k, "geometry": g} for i, n, k, g in rows], crs=27700)


def test_a_river_spot_is_in_the_water_body_of_the_nearest_line_named_for_its_river():
    g = _geo()
    assert make_rnags.river_spot(g, 1200, 40, "River Wye") == {"id": "GB_DOWN", "by": "river line", "m": 40}
    assert make_rnags.river_spot(g, 800, -20, "River Wye") == {"id": "GB_UP", "by": "river line", "m": 20}
    # At the tributary's mouth the Wye's line decides, not the brook's, which is nearer.
    assert make_rnags.river_spot(g, 505, 60, "River Wye")["id"] == "GB_UP"
    # Above where its line starts, the named catchment that holds the spot.
    assert make_rnags.river_spot(g, -700, 0, "River Wye") == {"id": "GB_UP", "by": "catchment", "m": 0}
    # A brook the file does not name gets nothing, not the river it joins; nor does a spot far from any line.
    assert make_rnags.river_spot(g, 1500, 10, "Burbage Brook") is None
    assert make_rnags.river_spot(g, 2000, 900, "River Wye") is None
    assert make_rnags.river_spot(g, 1200, 40, "") is None


def test_shapes_drop_groundwater_bodies():
    doc = {"features": [
        {"properties": {"id": "GB109055037113", "name": "Wye", "geometry-type": "x/def/geometry/RiverLine"},
         "geometry": {"type": "LineString", "coordinates": [[-2.72, 52.05], [-2.71, 52.05]]}},
        {"properties": {"id": "GB40902G205200", "name": "Wye Secondary Devonian ORS", "geometry-type": "x/def/geometry/Catchment"},
         "geometry": {"type": "Polygon", "coordinates": [[[-2.8, 52.0], [-2.6, 52.0], [-2.6, 52.1], [-2.8, 52.0]]]}}]}
    assert list(make_rnags.shapes([doc])["id"]) == ["GB109055037113"]


def test_the_written_file_is_json_one_entry_to_a_line(tmp_path):
    out = {"source": "s", "spots": {"a": {"id": "GB1", "by": "lake", "m": 0}, "b": None},
           "water_bodies": {"GB1": {"name": "n", "type": "Lake", "pressures": []}}}
    make_rnags.write(out, tmp_path / "r.json")
    text = (tmp_path / "r.json").read_text()
    assert json.loads(text) == out
    assert '\n"b":null' in text and '\n"GB1":{"name":"n"' in text


def _doc(tmp_path, spots: dict, bodies: dict) -> Path:
    p = tmp_path / "rnags.json"
    p.write_text(json.dumps({"spots": spots, "water_bodies": bodies}))
    return p


def test_the_build_copies_each_spots_water_body_and_the_agriculture_certainty(tmp_path):
    farm = {"sector": "Agriculture and rural land management", "issue": "Pollution from rural areas"}
    path = _doc(tmp_path, {"a": {"id": "GB1", "by": "river line", "m": 5}, "b": {"id": "GB2", "by": "lake", "m": 0},
                           "c": None, "d": {"id": "GB9", "by": "river line", "m": 3}, "e": {"id": "GB1", "by": "river line", "m": 1}},
                {"GB1": {"name": "Wye - A to B", "type": "River", "pressures": [
                    {**farm, "certainty": "probable"}, {"sector": "Water Industry", "issue": "Pollution from waste water", "certainty": "confirmed"}]},
                 "GB2": {"name": "Mere", "type": "Lake", "pressures": [
                     {"sector": "Agriculture and rural land management", "issue": "Physical modifications", "certainty": "confirmed"}]}})
    results = [{"id": i} for i in "abcdf"] + [{"id": "e", "error": "An isolated lake"}]
    assert build_site.attach_water_body(results, path) == (2, ["f"])
    got = {r["id"]: r.get("water_body") for r in results}
    assert got["a"] == {"id": "GB1", "name": "Wye - A to B", "agriculture": "probable"}
    # Agriculture listed only for physical modification (land drainage, say) is not farm runoff.
    assert got["b"] == {"id": "GB2", "name": "Mere"}
    # No water body; one the file lists no reasons for; a spot without a forecast; a spot added since the file was made.
    assert got["c"] is None and got["d"] is None and got["e"] is None and got["f"] is None
    assert build_site.attach_water_body([{"id": "a"}], tmp_path / "missing.json") is None


def test_the_wye_spots_get_the_line_from_the_committed_file():
    """The acceptance of review task D7: Hereford and Symonds Yat, from data/raw/rnags.json as committed."""
    results = [{"id": "wye-hereford", "kind": "river"}, {"id": "wye-symonds-yat", "kind": "river"}]
    n, unknown = build_site.attach_water_body(results)
    assert (n, unknown) == (2, [])
    assert results[0]["water_body"] == {"id": "GB109055037113", "name": "Wye - Bredwardine Br to Hampton Bishop", "agriculture": "probable"}
    assert results[1]["water_body"] == {"id": "GB109055037111", "name": "Wye - conf Walford Bk to Bigsweir Br", "agriculture": "probable"}


def test_the_committed_file_is_what_the_build_reads():
    """Every placement says how it was made, within the script's limits. A spot added since the file was
    made is not a failure here: the build warns of it, and scripts/make_rnags.py places it when run again."""
    doc = json.loads(make_rnags.OUT.read_text())
    placed = [v for v in doc["spots"].values() if v]
    assert len(placed) >= 90
    assert {v["by"] for v in placed} <= {"river line", "catchment", "lake"}
    assert all(v["by"] != "river line" or v["m"] <= make_rnags.RIVER_LINE_M for v in placed)
    assert set(pd.Series([v["id"] for v in placed]).str[:2]) == {"GB"}
    assert doc["licence"].startswith("Open Government Licence v3.0")


def test_every_catalogue_spot_has_a_checked_registry_entry():
    doc = json.loads(make_rnags.OUT.read_text())
    ids = set(make_rnags.load_spots()["id"])
    assert ids <= set(doc["spots"]), f"Missing RNAG placement checks: {sorted(ids - set(doc['spots']))}"
    assert doc["spots"]["carding-mill-reservoir"] is None
    for spot, wb in {"brothers-water": "GB30229116", "loweswater": "GB31228986", "bassenthwaite": "GB31228847"}.items():
        assert doc["spots"][spot]["id"] == wb
        assert wb in doc["water_bodies"]


def test_new_lakes_publish_only_the_checked_pressure_context():
    ids = ["brothers-water", "loweswater", "bassenthwaite", "carding-mill-reservoir"]
    results = [{"id": spot} for spot in ids]
    assert build_site.attach_water_body(results) == (3, [])
    assert results[0]["water_body"] == {"id": "GB30229116", "name": "Brothers Water"}
    assert results[1]["water_body"] == {"id": "GB31228986", "name": "Loweswater", "agriculture": "confirmed"}
    assert results[2]["water_body"] == {"id": "GB31228847", "name": "Bassenthwaite Lake", "agriculture": "probable"}
    assert "water_body" not in results[3]
