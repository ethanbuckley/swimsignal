"""scripts/satellite_imagery.py: the pilot sites' pictures (docs/LAKE-IMAGERY-CONTRACT-v1.md). No network: the grid,
the rendering, which scenes come first, the contract check, the CLI exit status and the build's copy."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import satellite_imagery as si  # noqa: E402


def test_a_site_window_is_fixed_square_and_holds_the_point():
    g = si.site_grid(54.58, -3.14)
    w, s, e, n = g["bbox"]
    assert w < -3.14 < e and s < 54.58 < n
    assert g["size_px"] == [80, 80] and g["lon"].shape == (80, 80)
    # About 800 m each way: the same window for every date.
    assert abs((n - s) * 111_320 - 800) < 1 and abs((e - w) * 111_320 * np.cos(np.radians(54.58)) - 800) < 1
    assert si.site_grid(54.58, -3.14)["bbox"] == g["bbox"]


def test_grid_positions_put_the_point_in_the_middle_of_its_window():
    # A UTM 30N item, 10 m grid; the site's centre pixel should land on the raster position of the point itself.
    from pyproj import Transformer
    lat, lon = 54.58, -3.14
    x, y = Transformer.from_crs(4326, 32630, always_xy=True).transform(lon, lat)
    item = {"properties": {"proj:epsg": 32630}, "assets": {"red": {"proj:transform": [10, 0, 400000, 0, -10, 6100000]}}}
    g = si.site_grid(lat, lon)
    r, c = si.grid_positions(item, "red", g)
    mid_r, mid_c = (r[39, 39] + r[40, 40]) / 2, (c[39, 39] + c[40, 40]) / 2
    assert abs(mid_r - (6100000 - y) / 10) < 1 and abs(mid_c - (x - 400000) / 10) < 1


def test_sample_takes_the_nearest_pixel_and_fills_outside():
    a = np.arange(12, dtype=float).reshape(3, 4)
    out = si.sample(a, np.array([10.2, 12.9, 9.0]), np.array([20.7, 23.1, 20.0]), 10, 20)
    assert out[0] == a[0, 0] and out[1] == a[2, 3]
    assert np.isnan(out[2])   # row 9 is above the window
    assert np.isnan(si.sample(a, np.array([13.5]), np.array([20.0]), 10, 20))[0]


def test_rendering_keeps_no_data_and_cloud_visible_and_the_legend_fixed():
    tci = np.array([[[0, 0, 0], [10, 20, 30]], [[np.nan, 1, 2], [255, 255, 255]]], float)
    rgba = si.true_colour(tci)
    assert rgba[0, 0, 3] == 0 and rgba[1, 0, 3] == 0 and rgba[0, 1, 3] == 255 and tuple(rgba[0, 1, :3]) == (10, 20, 30)
    m = si.not_clear_overlay(np.array([[4.0, 9.0], [0.0, 6.0]]))   # vegetation clear, cloud, no data, water clear
    assert m[0, 0, 3] == 0 and m[0, 1, 3] > 0 and m[1, 0, 3] > 0 and m[1, 1, 3] == 0
    c = si.index_colour(np.array([si.INDEX_RANGE[0], si.INDEX_RANGE[1], np.nan, 9.0]))
    assert tuple(c[0, :3]) == tuple(si.INDEX_COLOURS[0].astype(int)) and tuple(c[1, :3]) == tuple(si.INDEX_COLOURS[-1].astype(int))
    assert c[2, 3] == 0 and tuple(c[3, :3]) == tuple(c[1, :3])   # off the scale is clipped, never extrapolated
    assert si.png(rgba)[:8] == b"\x89PNG\r\n\x1a\n"


def _obs():
    lk = {"lake_id": "bw-x", "series": [{"item_id": "OLD1", "date": "2026-07-01", "ndci": 0.02, "primary": True},
                                        {"item_id": "OLD2", "date": "2026-08-01", "ndci": 0.03, "primary": True},
                                        {"item_id": "NEW1", "date": "2026-10-20", "ndci": 0.05, "primary": True,
                                         "experimental": True}],
          "excluded": [{"item_id": "NEW2", "reason": "core_not_classed_water"}]}
    return {"lakes": [lk]}


def _runs():
    return [{"run_id": "9", "finished": "2026-10-31T12:00:00+00:00", "rows": [
        {"lake_id": "bw-x", "item_id": "NEW1", "datetime": "2026-10-20T11:00:00Z", "usable": True},
        {"lake_id": "bw-x", "item_id": "NEW2", "datetime": "2026-10-22T11:00:00Z", "usable": True},
        {"lake_id": "bw-x", "item_id": "CLOUD", "datetime": "2026-10-25T11:00:00Z", "usable": False}]}]


def test_new_usable_scenes_come_first_then_earlier_readings_newest_first(monkeypatch):
    monkeypatch.setattr(si.sp, "pilot_sites", lambda: [{"lake_id": "bw-x"}])
    q = si.queue({"sites": []}, _obs(), _runs())
    assert [(x[1], x[2]) for x in q] == [("NEW2", "current"), ("NEW1", "current"), ("OLD2", "backfill"), ("OLD1", "backfill")]
    done = {"sites": [{"lake_id": "bw-x", "scenes": [{"item_id": "NEW2"}, {"item_id": "OLD2"}]}]}
    assert [x[1] for x in si.queue(done, _obs(), _runs())] == ["NEW1", "OLD1"]   # cloud never: no picture of a gap


def test_quality_comes_from_the_published_record():
    lk = _obs()["lakes"][0]
    assert si.quality(lk, "NEW1") == ("shown", 0.05, True)
    assert si.quality(lk, "NEW2") == ("excluded:core_not_classed_water", None, False)
    assert si.quality(lk, "ELSE") == ("not_shown", None, False)


def _manifest(tmp_path, **scene):
    d = tmp_path / "lake-img" / "bw-x"
    d.mkdir(parents=True)
    sc = {"item_id": "NEW1", "datetime": "2026-10-20T11:00:00Z", "quality": "shown", "ndci": 0.05, "index_median": 0.0503}
    for k, name in (("image_url", "NEW1.png"), ("mask_url", "NEW1-mask.png"), ("index_url", "NEW1-index.png")):
        (d / name).write_bytes(name.encode())
        sc[k], sc[k.replace("_url", "_sha256")] = f"lake-img/bw-x/{name}", hashlib.sha256(name.encode()).hexdigest()
    sc.update(scene)
    return {**si.empty_manifest(), "sites": [{"lake_id": "bw-x", "lat": 54.0, "lon": -3.0, "bbox": [-3.01, 53.99, -2.99, 54.01],
                                             "scenes": [sc]}], "runs": [{"run_id": "1", "status": "ok"}]}


def test_check_holds_and_catches_what_it_should(tmp_path):
    m = _manifest(tmp_path)
    assert si.check(m, tmp_path / "lake-img") == []
    assert any("not shown" in e for e in si.check(_manifest(tmp_path / "a", quality="excluded:sun_too_low", ndci=None)))
    assert any("far from the reading" in e for e in si.check(_manifest(tmp_path / "b", index_median=0.2)))
    m2 = _manifest(tmp_path / "c")
    (tmp_path / "c" / "lake-img" / "bw-x" / "NEW1.png").write_bytes(b"changed")
    assert any("missing or changed" in e for e in si.check(m2, tmp_path / "c" / "lake-img"))
    m3 = {**m, "runs": [{"run_id": "2", "status": "fine"}]}
    assert any("status" in e for e in si.check(m3))


def test_the_committed_manifest_holds_the_contract():
    m = json.loads((ROOT / "data" / "research" / "lake_imagery.v1.json").read_text())
    assert si.check(m, ROOT / "data" / "research" / "lake-img") == []


@pytest.mark.parametrize("status, code", [("ok", 0), ("partial", 1), ("failed", 1)])
def test_the_run_command_fails_unless_every_new_scene_got_its_picture(status, code, monkeypatch, capsys):
    monkeypatch.setattr(si, "run", lambda *a: {"status": status, "made": {"current": 0, "backfill": 0}})
    monkeypatch.setattr(sys, "argv", ["satellite_imagery.py", "run"])
    if code:
        with pytest.raises(SystemExit) as e:
            si.main()
        assert e.value.code == code
    else:
        si.main()
    assert json.loads(capsys.readouterr().out)["status"] == status


def test_the_allocation_is_shared_with_the_readings(monkeypatch, tmp_path):
    runs = tmp_path / "runs.json"
    runs.write_text(json.dumps([{"requests": 260, "megabytes": 70.0}]))
    monkeypatch.setattr(si.sp, "RUNS", runs)
    got = {}
    monkeypatch.setattr(si, "run", lambda req, mb, mins: got.update(req=req, mb=mb) or {"status": "ok"})
    monkeypatch.setattr(sys, "argv", ["satellite_imagery.py", "run", "--budget-from-runs", "300"])
    si.main()
    assert got == {"req": 40, "mb": 30.0}


def test_the_build_copies_the_pictures_or_says_none(tmp_path):
    import build_site as bs
    src = tmp_path / "src"
    m = _manifest(src)
    (src / "manifest.json").write_text(json.dumps(m))
    site = tmp_path / "site"
    h = bs.write_lake_imagery(site, src / "manifest.json", src / "lake-img")
    assert h == {"available": True, "scenes": 1, "version": si.VERSION}
    assert (site / "data" / "research" / "lake-img" / "bw-x" / "NEW1.png").read_bytes() == b"NEW1.png"
    assert json.loads((site / "data" / "research" / "lake_imagery.json").read_text())["available"] is True
    h = bs.write_lake_imagery(site, tmp_path / "none.json", tmp_path / "none")
    assert h["available"] is False and not (site / "data" / "research" / "lake-img").exists()


def test_the_cog_reader_decodes_a_three_band_true_colour_tile():
    # The TCI: three pixel-interleaved uint8 bands, deflate, horizontal predictor per band (cog.py, #550).
    import zlib
    sys.path.insert(0, str(ROOT / "scripts" / "lake_algae_sat_eval"))
    import cog
    rng = np.random.default_rng(0)
    tile = rng.integers(0, 256, size=(4, 4, 3), dtype=np.uint8)
    diff = tile.copy()
    diff[:, 1:] = (tile[:, 1:].astype(int) - tile[:, :-1].astype(int)) % 256
    c = cog.Cog(8, 4, 4, 4, np.dtype("<u1"), 8, 2, np.array([0, 0]), np.array([0, 0]), 0.0, samples=3)
    assert (cog.decode_tile(c, zlib.compress(diff.tobytes())) == tile).all()
    blob = zlib.compress(diff.tobytes())
    c = cog.Cog(8, 4, 4, 4, np.dtype("<u1"), 8, 2, np.array([0, len(blob)]), np.array([len(blob), len(blob)]), 0.0, samples=3)
    w = cog.read_window(c, lambda s, e: (blob + blob)[s:e + 1], 1, 3, 3, 6)
    assert w.shape == (2, 3, 3) and (w[:, 0] == tile[1:3, 3]).all() and (w[:, 1:] == tile[1:3, 0:2]).all()
