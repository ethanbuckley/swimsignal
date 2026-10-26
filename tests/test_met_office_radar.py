"""scripts/fetch_met_office_radar.py: pixels to rain cells, the hourly trapezoid, the HDF5 reader on
a synthetic composite with the real file's layout, and a resumable run against a fake bucket. No
network."""

import io
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_met_office_radar as radar

CELLS = [(52.0, -1.0), (54.4, -2.9)]


def h5_bytes(data, nodata=-1.0, xsize=radar.NX, projdef=radar.PROJDEF, gain=1.0, offset=0.0):
    """An ODIM composite laid out as the bucket's are (groups and attributes as read on 24 Oct 2026)."""
    h5py = pytest.importorskip("h5py")
    buf = io.BytesIO()
    with h5py.File(buf, "w") as f:
        f.attrs["Conventions"] = np.bytes_("ODIM_H5/V2_2")
        w = f.create_group("where").attrs
        w["projdef"] = np.bytes_(projdef)
        w["xsize"], w["ysize"], w["xscale"], w["yscale"] = xsize, radar.NY, 1000.0, 1000.0
        d = f.create_dataset("dataset1/data1/data", data=data, compression="gzip")
        what = f.create_group("dataset1/data1/what").attrs
        what["quantity"] = np.bytes_("RATE")
        what["gain"], what["offset"], what["nodata"], what["undetect"] = gain, offset, nodata, 0.0
        f.create_group("dataset1/how").attrs["origin"] = np.bytes_("UPPER LEFT")
        assert d.shape == data.shape
    return buf.getvalue()


def grid(fill=0.0):
    return np.full((radar.NY, radar.NX), fill, dtype=np.float32)


def test_cell_pixels_lie_in_their_cell():
    idx, lab, n = radar.cell_pixels(CELLS)
    # A 0.1 degree cell is about 11.1 km by 6.9 km at 52 N and 11.1 by 6.5 at 54.4 N.
    assert 70 <= n[0] <= 85 and 65 <= n[1] <= 80
    assert n.sum() == idx.size == lab.size
    rows, cols = np.divmod(idx, radar.NX)
    x = radar.X_LEFT + (cols + 0.5) * radar.PIXEL_M
    y = radar.Y_TOP - (rows + 0.5) * radar.PIXEL_M
    lon, lat = radar.Transformer.from_crs(radar.GRID_CRS, "EPSG:4326", always_xy=True).transform(x, y)
    for k, (cl, cn) in enumerate(CELLS):
        m = lab == k
        assert np.all(np.abs(lat[m] - cl) <= 0.05 + 1e-9) and np.all(np.abs(lon[m] - cn) <= 0.05 + 1e-9)


def test_cell_off_the_grid_has_no_pixels():
    _, _, n = radar.cell_pixels([(30.0, -40.0)])
    assert n[0] == 0


def test_reduce_skips_nodata():
    idx, lab, n = radar.cell_pixels(CELLS[:1])
    rate = np.zeros((radar.NY, radar.NX))
    rate.ravel()[idx] = 2.0
    rate.ravel()[idx[:10]] = np.nan
    s, c = radar.reduce_snapshot(rate, idx, lab, 1)
    assert c[0] == n[0] - 10 and s[0] == pytest.approx(2.0 * (n[0] - 10))


def test_hourly_trapezoid_and_coverage():
    t = pd.Timestamp("2026-02-06 01:00", tz="UTC")
    n_pix = np.array([10, 0])
    full = (np.array([30.0, 0.0]), np.array([10.0, 0.0]))   # 3 mm/h over all 10 pixels
    snaps = {t - k * radar.STEP: full for k in range(5)}
    mm, cov = radar.hourly(snaps, pd.DatetimeIndex([t]), n_pix)
    assert mm[0, 0] == pytest.approx(3.0) and cov[0, 0] == pytest.approx(1.0)
    assert np.isnan(mm[0, 1]) and cov[0, 1] == 0.0
    # An end snapshot weighs half, a middle one a whole: losing them costs 1/8 and 1/4 of the hour.
    end_gone = {k: v for k, v in snaps.items() if k != t}
    mid_gone = {k: v for k, v in snaps.items() if k != t - 2 * radar.STEP}
    assert radar.hourly(end_gone, pd.DatetimeIndex([t]), n_pix)[1][0, 0] == pytest.approx(0.875)
    assert radar.hourly(mid_gone, pd.DatetimeIndex([t]), n_pix)[1][0, 0] == pytest.approx(0.75)
    # Rain only in the last 15 minutes: half of one quarter-hour's weight, 0.5/4 of the 8 mm/h rate.
    rain_end = dict(snaps)
    rain_end[t] = (np.array([80.0, 0.0]), np.array([10.0, 0.0]))
    rain_end.update({t - k * radar.STEP: (np.zeros(2), np.array([10.0, 0.0])) for k in range(1, 5)})
    assert radar.hourly(rain_end, pd.DatetimeIndex([t]), n_pix)[0][0, 0] == pytest.approx(1.0)


def test_read_composite_applies_nodata_gain_offset():
    a = grid(-1.0)
    a[100, 200], a[101, 200] = 0.0, 4.5
    rate = radar.read_composite(h5_bytes(a))
    assert np.isnan(rate[0, 0]) and rate[100, 200] == 0.0 and rate[101, 200] == pytest.approx(4.5)
    rate = radar.read_composite(h5_bytes(a, gain=2.0, offset=1.0))
    assert np.isnan(rate[0, 0]) and rate[101, 200] == pytest.approx(10.0)


def test_read_composite_refuses_another_grid():
    with pytest.raises(ValueError, match="grid changed"):
        radar.read_composite(h5_bytes(grid(), projdef="+proj=longlat"))


def test_default_cells_from_cache_names(tmp_path):
    for name in ["forecast_52.000_-1.000.parquet", "forecast_51.500_-0.000.parquet",
                 "leads_52.000_-1.000_2026.parquet", "leads_54.400_-2.900_2025.parquet",
                 "archive_50.000_-5.000_2025.parquet", "open_meteo_calls.json"]:
        (tmp_path / name).write_bytes(b"")
    assert radar.default_cells(tmp_path) == [(51.5, 0.0), (52.0, -1.0), (54.4, -2.9)]


class Bucket:
    """A fake of the bucket: the listing and the files for 5 and 6 Feb 2026, every file a uniform
    2 mm/h, except that 06:30 on 6 Feb is missing. Counts the file downloads. The files are numpy's
    .npy, read by a stand-in for read_composite, so this runs without h5py."""

    def __init__(self):
        times = pd.date_range("2026-02-05 00:00", "2026-02-06 23:45", freq="15min", tz="UTC")
        self.keys = {f"radar/{t:%Y/%m/%d}/{t:%Y%m%d%H%M}_ODIM_ng_radar_rainrate_composite_1km_UK.h5"
                     for t in times if t != pd.Timestamp("2026-02-06 06:30", tz="UTC")}
        buf = io.BytesIO()
        np.save(buf, grid(2.0).astype(np.float64))
        self.body = buf.getvalue()
        self.files = 0

    def handler(self, request):
        if request.url.path == "/":
            prefix = request.url.params["prefix"]
            keys = "".join(f"<Contents><Key>{k}</Key></Contents>" for k in sorted(self.keys) if k.startswith(prefix))
            xml = ('<?xml version="1.0" encoding="UTF-8"?><ListBucketResult '
                   f'xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{keys}</ListBucketResult>')
            return httpx.Response(200, content=xml.encode())
        if request.url.path.lstrip("/") in self.keys:
            self.files += 1
            return httpx.Response(200, content=self.body)
        return httpx.Response(404)


def test_run_writes_months_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(radar, "_sleep", lambda s: None)
    monkeypatch.setattr(radar, "read_composite", lambda data: np.load(io.BytesIO(data)))
    b = Bucket()
    client = httpx.Client(transport=httpx.MockTransport(b.handler))
    stats = radar.run("2026-02-06", "2026-02-06", CELLS, tmp_path, client=client, pause_s=0)
    assert b.files == 96 and stats["missing"] == 1 and stats["days"] == 1
    df = pd.read_parquet(radar.month_path(tmp_path, CELLS[0], pd.Timestamp("2026-02-01")))
    assert list(df.columns) == ["cell_lat", "cell_lon", "time", "radar_mm", "coverage"]
    assert len(df) == 24 and str(df.time.dtype) == "datetime64[us, UTC]"
    assert df.time.iloc[0] == pd.Timestamp("2026-02-06 00:00", tz="UTC")   # uses 5 Feb 23:00 to 6 Feb 00:00
    assert np.allclose(df.radar_mm, 2.0)
    by = df.set_index("time").coverage
    assert by[pd.Timestamp("2026-02-06 07:00", tz="UTC")] == pytest.approx(0.75)
    assert by[pd.Timestamp("2026-02-06 06:00", tz="UTC")] == 1.0
    import pyarrow.parquet as pq
    meta = pq.read_schema(radar.month_path(tmp_path, CELLS[0], pd.Timestamp("2026-02-01"))).metadata
    assert b"CC BY-SA 4.0" in meta[b"credit"]

    # Again: nothing to do. With one more cell: the day is fetched for that cell only.
    radar.run("2026-02-06", "2026-02-06", CELLS, tmp_path, client=client, pause_s=0)
    assert b.files == 96
    more = CELLS + [(51.5, 0.0)]
    stats = radar.run("2026-02-05", "2026-02-06", more, tmp_path, client=client, pause_s=0)
    # 5 Feb: all three cells; its 00:00 hour needs 4 Feb 23:00 to 23:45, which the fake does not
    # have (4 missing). 6 Feb: the new cell only, from 5 Feb's last four kept in memory (1 missing).
    assert stats["days"] == 2 and stats["missing"] == 5
    df = pd.read_parquet(radar.month_path(tmp_path, CELLS[0], pd.Timestamp("2026-02-01")))
    assert len(df) == 48 and df.time.is_monotonic_increasing
    assert df.coverage.iloc[0] == pytest.approx(0.125) and df.coverage.iloc[1] == 1.0


def test_run_refuses_today(tmp_path):
    today = pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
    with pytest.raises(SystemExit):
        radar.run(today, today, CELLS, tmp_path)


def test_get_retries_then_gives_up(monkeypatch):
    waits = []
    monkeypatch.setattr(radar, "_sleep", waits.append)
    calls = []

    def flaky(request):
        calls.append(1)
        return httpx.Response(503 if len(calls) < 3 else 200, content=b"ok")

    c = httpx.Client(transport=httpx.MockTransport(flaky))
    assert radar.get(c, "https://x/").content == b"ok" and waits == [2.0, 4.0]
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(RuntimeError):
        radar.get(c, "https://x/")
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    assert radar.get(c, "https://x/") is None


# ------------------------------------------------------------------ the overflows
def pixel_centre(row, col):
    """The lat/lon of a radar pixel's centre."""
    x = radar.X_LEFT + (col + 0.5) * radar.PIXEL_M
    y = radar.Y_TOP - (row + 0.5) * radar.PIXEL_M
    lon, lat = radar.Transformer.from_crs(radar.GRID_CRS, "EPSG:4326", always_xy=True).transform(x, y)
    return float(lat), float(lon)


def test_overflow_pixel_is_the_one_that_holds_it():
    row, col = radar.overflow_pixels([pixel_centre(1200, 900)[0], 30.0], [pixel_centre(1200, 900)[1], -40.0])
    assert (row[0], col[0]) == (1200, 900)
    assert (row[1], col[1]) == (-1, -1)   # off the grid


def test_block_is_the_pixel_and_its_eight_neighbours_clipped_at_the_edge():
    idx, lab, n = radar.block_pixels(np.array([1200, 0, -1]), np.array([900, 0, -1]))
    assert list(n) == [9, 4, 0]
    rows, cols = np.divmod(idx[lab == 0], radar.NX)
    assert set(zip(rows, cols)) == {(r, c) for r in (1199, 1200, 1201) for c in (899, 900, 901)}
    assert set(idx[lab == 1]) == {0, 1, radar.NX, radar.NX + 1}
    idx, lab, n = radar.block_pixels(np.array([1200]), np.array([900]), half=0)
    assert list(idx) == [1200 * radar.NX + 900] and list(n) == [1]


def overflow_table(tmp_path, rows):
    lat, lon = zip(*(pixel_centre(r, c) for r, c in rows))
    df = pd.DataFrame({"site_id": [f"X{k}" for k in range(len(rows))], "lat": lat, "lon": lon,
                       "network_key": "b5724303", "company": "Test Water"})
    path = tmp_path / "overflows.parquet"
    df.to_parquet(path)
    return path


def test_run_writes_overflow_days_and_resumes(tmp_path, monkeypatch):
    """A grid of 2 mm/h with 9 mm/h on one overflow's own pixel and nodata on one neighbour: the
    block mean is (9 + 7 x 2) / 8, the centre is 9; another overflow sits in plain 2 mm/h."""
    rate = grid(2.0).astype(np.float64)
    rate[1200, 900] = 9.0
    rate[1199, 899] = np.nan
    monkeypatch.setattr(radar, "_sleep", lambda s: None)
    monkeypatch.setattr(radar, "read_composite", lambda data: rate)
    b = Bucket()
    client = httpx.Client(transport=httpx.MockTransport(b.handler))
    ovs, meta = radar.read_overflows(overflow_table(tmp_path, [(1200, 900), (1500, 700)]))
    assert meta["network_key"] == "b5724303" and len(meta["overflows_sha256"]) == 64
    out = tmp_path / "out"
    stats = radar.run("2026-02-06", "2026-02-06", [], out, client=client, pause_s=0,
                      overflows=ovs, overflow_meta=meta)
    assert b.files == 96 and stats["overflow_rows"] == 48 and stats["rows"] == 0
    path = radar.overflow_day_path(out, pd.Timestamp("2026-02-06"))
    df = pd.read_parquet(path)
    assert list(df.columns) == ["site_id", "time", "radar_mm", "coverage", "centre_mm", "centre_coverage"]
    assert list(df.site_id[:24]) == ["X0"] * 24 and str(df.time.dtype) == "datetime64[us, UTC]"
    x0 = df[df.site_id == "X0"].set_index("time")
    assert np.allclose(x0.radar_mm, 23 / 8, atol=1e-3) and np.allclose(x0.centre_mm, 9.0)
    assert x0.coverage[pd.Timestamp("2026-02-06 06:00", tz="UTC")] == pytest.approx(8 / 9, abs=1e-3)
    assert x0.centre_coverage[pd.Timestamp("2026-02-06 07:00", tz="UTC")] == pytest.approx(0.75)
    x1 = df[df.site_id == "X1"]
    assert np.allclose(x1.radar_mm, 2.0) and np.allclose(x1.centre_mm, 2.0)
    md = radar.pq.read_schema(path).metadata
    assert md[b"overflows_sha256"].decode() == meta["overflows_sha256"]
    assert md[b"network_key"] == b"b5724303" and b"3 x 3" in md[b"pixel_rule"] and b"CC BY-SA" in md[b"credit"]
    px = pd.read_parquet(out / "overflows" / "overflow_pixels.parquet")
    assert list(px.row) == [1200, 1500] and list(px.col) == [900, 700] and list(px.block_pixels) == [9, 9]

    # Again: nothing to fetch. With cells too, the day is fetched for the cells only.
    stats = radar.run("2026-02-06", "2026-02-06", [], out, client=client, pause_s=0,
                      overflows=ovs, overflow_meta=meta)
    assert b.files == 96 and stats["skipped"] == 1
    stats = radar.run("2026-02-06", "2026-02-06", CELLS, out, client=client, pause_s=0,
                      overflows=ovs, overflow_meta=meta)
    assert b.files == 192 and stats["rows"] == 48 and stats["overflow_rows"] == 0

    # A folder begun from one overflow table refuses another.
    other = dict(meta, overflows_sha256="0" * 64)
    with pytest.raises(SystemExit, match="another --out"):
        radar.run("2026-02-07", "2026-02-07", [], out, client=client, pause_s=0,
                  overflows=ovs, overflow_meta=other)
