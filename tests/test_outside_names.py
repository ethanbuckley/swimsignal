"""River and lake names outside England: scripts/make_outside_names.py and its data/raw/outside_names/."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import shapely

ROOT = Path(__file__).resolve().parents[1]
NAMES = ROOT / "data" / "raw" / "outside_names"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _points(v, r, c, mon):
    """A square's flat points back to [lon, lat]."""
    xy = np.cumsum(np.array(v[1:]).reshape(-1, 2), axis=0) * mon.Q
    return xy + [c * mon.TILE_DEG, r * mon.TILE_DEG]


def test_lines_are_cut_at_the_squares_and_keep_their_names():
    mon = _load("make_outside_names")
    to = mon.FROM_WGS[2157]
    x, y = to.transform([-7.30, -7.20], [53.10, 53.10])   # across the edge at 7.25 W
    a, b = to.transform([-7.30, -7.30], [53.20, 53.21])
    lines = [("River A", shapely.LineString(np.c_[x, y])), (None, shapely.LineString(np.c_[a, b]))]
    keep = {"212_-30", "212_-29"}
    tiles = mon.tiles_of(mon.line_pieces(lines, 2157, keep))
    assert sorted(tiles) == ["212_-29", "212_-30"]
    for key, t in tiles.items():
        r, c = map(int, key.split("_"))
        named = [v for v in t["lines"] if v[0] >= 0]
        assert t["names"] == ["River A"] and len(named) == 1
        pts = _points(named[0], r, c, mon)
        assert np.all((pts[:, 0] >= c * 0.25 - 1e-9) & (pts[:, 0] <= (c + 1) * 0.25 + 1e-9))
        assert np.allclose(pts[:, 1], 53.10, atol=2e-4)
    assert [v[0] for v in tiles["212_-30"]["lines"]].count(-1) == 1   # the line through a lake: no name
    assert "lakes" not in tiles["212_-30"]
    assert mon.tiles_of(mon.line_pieces(lines, 2157, set())) == {}


def test_a_lake_is_whole_in_every_square_it_reaches():
    mon = _load("make_outside_names")
    to = mon.FROM_WGS[3035]
    lon, lat = [-7.26, -7.24, -7.24, -7.26], [53.10, 53.10, 53.11, 53.11]
    x, y = to.transform(lon, lat)
    lakes = [("Lough Test", shapely.Polygon(np.c_[x, y]))]
    tiles = mon.tiles_of({}, mon.lake_pieces(lakes, 3035, {"212_-30", "212_-29"}))
    assert sorted(tiles) == ["212_-29", "212_-30"]
    for key, t in tiles.items():
        r, c = map(int, key.split("_"))
        assert t["names"] == ["Lough Test"] and t["lines"] == []
        ring = _points(t["lakes"][0], r, c, mon)
        assert ring[:, 0].min() < -7.25 < ring[:, 0].max()   # the whole outline, not cut at the edge
    tiny = shapely.Point(x[0], y[0]).buffer(20)   # about 0.13 ha
    assert mon.lake_pieces([("Pond", tiny)], 3035, {"212_-30"}) == {}


def test_the_committed_squares_match_their_index():
    index = json.loads((NAMES / "index.json").read_text())
    assert set(index["sources"]) == {"os", "osm"}
    for src, meta in index["sources"].items():
        on_disk = sorted(p.stem for p in (NAMES / src).glob("*.json"))
        assert on_disk == meta["tiles"], src
        assert meta["credit"] and meta["licence"]
        for key in meta["tiles"][::25]:
            t = json.loads((NAMES / src / f"{key}.json").read_text())
            n = len(t["names"])
            assert all(-1 <= v[0] < n and len(v) % 2 == 1 and len(v) >= 5 for v in t["lines"]), (src, key)
            assert all(0 <= v[0] < n for v in t.get("lakes", [])), (src, key)
            # OS's folder holds OS data only: the OpenStreetMap lakes are under the ODbL, in osm/.
            assert src == "osm" or "lakes" not in t
    assert "outside_names/osm" in (ROOT / "LICENSE-DATA.md").read_text()


def test_the_build_copies_the_names_and_drops_old_squares(tmp_path):
    bap = _load("build_any_point")
    src = tmp_path / "names"
    (src / "os").mkdir(parents=True)
    (src / "index.json").write_text("{}")
    (src / "os" / "1_2.json").write_text("{}")
    out = tmp_path / "out"
    (out / "names" / "os").mkdir(parents=True)
    (out / "names" / "os" / "9_9.json").write_text("{}")
    shape = tmp_path / "outside_england.json"
    shape.write_text("{}")
    bap.copy_outside(out, shape, src)
    assert sorted(str(p.relative_to(out)) for p in out.rglob("*.json")) == [
        "names/index.json", "names/os/1_2.json", "outside_england.json"]
    bap.copy_outside(out, shape, tmp_path / "missing")
    assert not (out / "names").exists()
