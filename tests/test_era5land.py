"""scripts/era5land (docs/ERA5-LAND-BULK-RAIN-2026-11.md), offline, on synthetic arrays only: no CDS or Open-Meteo
request, no shared cache read. The de-accumulation and units, the grid and cell rules, reading NetCDF, the conversion
to cache-shaped files, the fetcher's resume, ledger, ceilings and stop rules with a stand-in client, and the match
check's sums and verdicts."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "scripts" / "era5land"
sys.path.insert(0, str(HERE))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"era5land_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load("era5land_core")
fetch = _load("fetch")
to_cells = _load("to_cells")
mc = _load("match_check")

TOKEN = ("https://cds.climate.copernicus.eu/api", "made-up-token", "test")


# ------------------------------------------------------------------ helpers
def truth_rain(start: str, end: str, seed: int = 0) -> pd.Series:
    """Hourly rain in mm, 0.1 mm steps, labelled by the hour's end, every hour from start to end."""
    t = pd.date_range(start, end, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    wet = rng.random(len(t)) < 0.15
    r = np.where(wet, np.round(rng.exponential(1.2, len(t)), 1), 0.0)
    return pd.Series(r, index=t)


def accumulate(truth: pd.Series, times: pd.DatetimeIndex) -> np.ndarray:
    """ERA5-Land's running total in metres at each valid time: the rain since 00 UTC, and at 00 UTC the whole day
    before."""
    cs = truth.cumsum()
    day_start = (times - pd.Timedelta(hours=1)).floor("D")
    return (cs.reindex(times).to_numpy() - cs.reindex(day_start).to_numpy()) / 1000.0


def write_nc3(path: Path, times: pd.DatetimeIndex, lat, lon, tp_m: np.ndarray, lon360: bool = False) -> None:
    """A classic NetCDF file like the old CDS's: tp packed as int16 with scale_factor, add_offset and _FillValue,
    times as int hours since 1900, latitude north to south."""
    from scipy.io import netcdf_file
    path.parent.mkdir(parents=True, exist_ok=True)
    f = netcdf_file(str(path), "w", version=2)
    f.createDimension("valid_time", len(times))
    f.createDimension("latitude", len(lat))
    f.createDimension("longitude", len(lon))
    tv = f.createVariable("valid_time", "i4", ("valid_time",))
    tv[:] = ((times.tz_convert(None) - pd.Timestamp("1900-01-01")) // pd.Timedelta(hours=1)).to_numpy()
    tv.units = b"hours since 1900-01-01 00:00:00.0"
    la = f.createVariable("latitude", "f4", ("latitude",))
    la[:] = np.asarray(lat, dtype="f4")
    lo = f.createVariable("longitude", "f4", ("longitude",))
    lo[:] = np.asarray([x % 360 if lon360 else x for x in lon], dtype="f4")
    v = f.createVariable("tp", "i2", ("valid_time", "latitude", "longitude"))
    finite = tp_m[np.isfinite(tp_m)]
    lo_v, hi_v = float(finite.min()), float(finite.max())
    sf = (hi_v - lo_v) / 60000.0 or 1e-9
    ao = lo_v + 30000 * sf
    packed = np.where(np.isfinite(tp_m), np.round((np.nan_to_num(tp_m) - ao) / sf), -32767).astype("i2")
    v[:] = packed
    v.scale_factor = np.float64(sf)
    v.add_offset = np.float64(ao)
    v._FillValue = np.int16(-32767)
    v.units = b"m"
    f.close()


GRID_LAT = [51.2, 51.1, 51.0]          # north to south, as the CDS sends it
GRID_LON = [-0.1, 0.0, 0.1]
SEA = (0, 2)                            # (51.2, 0.1) has no value, like a sea point


def write_months(out: Path, months: list[str], seed: int = 1) -> dict[tuple[int, int], pd.Series]:
    """Monthly files for a 3 x 3 grid, each point with its own true rain; returns the truth by (row, col)."""
    first = pd.Timestamp(f"{months[0]}-01", tz="UTC") - pd.Timedelta(days=1)
    last = pd.Timestamp(f"{months[-1]}-01", tz="UTC") + pd.offsets.MonthBegin(1)
    truth = {(i, j): truth_rain(str(first), str(last), seed + 3 * i + j) for i in range(3) for j in range(3)}
    for m in months:
        t0 = pd.Timestamp(f"{m}-01", tz="UTC")
        times = pd.date_range(t0, t0 + pd.offsets.MonthBegin(1) - pd.Timedelta(hours=1), freq="h")
        tp = np.zeros((len(times), 3, 3))
        for (i, j), s in truth.items():
            tp[:, i, j] = np.nan if (i, j) == SEA else accumulate(s, times)
        write_nc3(core.raw_file(out, m), times, GRID_LAT, GRID_LON, tp, lon360=True)
    return truth


# ------------------------------------------------------------------ months, requests and size
def test_month_list_and_default_end():
    assert core.month_list("2025-11", "2026-02") == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert core.default_end(date(2026, 11, 15)) == "2026-08"
    assert core.default_end(date(2026, 2, 1)) == "2025-11"
    assert len(core.month_list("1990-01", "2026-08")) == 440


def test_month_request_asks_for_every_hour_of_the_month_as_netcdf():
    r = core.month_request("2024-02")
    assert r["variable"] == ["total_precipitation"] and r["year"] == "2024" and r["month"] == "02"
    assert r["day"] == [f"{d:02d}" for d in range(1, 30)]      # 2024 is a leap year
    assert r["time"][0] == "00:00" and r["time"][-1] == "23:00" and len(r["time"]) == 24
    assert r["data_format"] == "netcdf" and r["download_format"] == "unarchived"
    assert r["area"] == [61.0, -8.3, 49.8, 2.0]
    assert core.DATASET == "reanalysis-era5-land"


def test_size_bound():
    assert core.area_points() == (113, 104)
    assert core.upper_bytes(["2024-01"]) == 113 * 104 * 744 * 4
    d = fetch.dry_run(None, "1990-01", "2026-08", core.DEFAULT_AREA)
    assert d["months"] == d["requests_left"] == 440
    assert d["first_request"] == "2026-08" and d["last_request"] == "1990-01"   # newest first
    assert d["upper_bound_gb_all_months"] == round(core.upper_bytes(core.month_list("1990-01", "2026-08")) / 1e9, 1)


# ------------------------------------------------------------------ de-accumulation and units
def test_deaccumulate_gives_back_the_hourly_rain_in_mm():
    truth = truth_rain("2024-03-01 00:00", "2024-03-04 00:00")
    times = truth.index
    mm, big = core.deaccumulate(accumulate(truth, times), times)
    assert np.isnan(mm[0])               # 00 UTC with no step before it: unknown, not 0
    assert np.allclose(mm[1:], truth.to_numpy()[1:], atol=1e-9)
    assert big == 0
    # the hour ending 00 UTC is the day's total less its first 23 hours
    k = np.where(times == pd.Timestamp("2024-03-02 00:00", tz="UTC"))[0][0]
    assert mm[k] == pytest.approx(truth.iloc[k])


def test_deaccumulate_metres_to_mm_and_the_first_hour():
    times = pd.date_range("2024-01-01 00:00", periods=4, freq="h", tz="UTC")
    acc = np.array([0.010, 0.001, 0.0015, 0.0015])     # m: yesterday's total, then 1 mm, 0.5 mm, 0 mm
    mm, _ = core.deaccumulate(acc, times)
    assert np.isnan(mm[0]) and mm[1] == pytest.approx(1.0) and mm[2] == pytest.approx(0.5) and mm[3] == 0.0


def test_deaccumulate_noise_gap_and_shape():
    times = pd.date_range("2024-01-01 01:00", periods=5, freq="h", tz="UTC")
    acc = np.array([[0.001, 0.0], [0.000999999, 0.0], [0.002, 0.0], [0.003, 0.0], [0.0025, 0.0]])
    mm, big = core.deaccumulate(acc, times)
    assert mm.shape == (5, 2)
    assert mm[1, 0] == 0.0               # a tiny negative step is set to 0
    assert big == 1                      # 0.003 -> 0.0025 m is -0.5 mm: counted, then set to 0
    gap = times.delete(2)
    mm2, _ = core.deaccumulate(acc[[0, 1, 3, 4]], gap)
    assert np.isnan(mm2[2, 0])           # the step after a missing hour is unknown
    with pytest.raises(ValueError):
        core.deaccumulate(acc, times.tz_convert(None))


def test_round_to():
    v = np.array([0.04, 0.06, 1.234, 2.0, np.nan])
    r = core.round_to(v, 0.1)
    assert np.allclose(r[:4], [0.0, 0.1, 1.2, 2.0]) and np.isnan(r[4])
    assert core.round_to(v, 0) is v


# ------------------------------------------------------------------ grid and cells
def test_snap_is_rainfall_grid_cell():
    from dipcast.ingest.rainfall import grid_cell
    rng = np.random.default_rng(3)
    lat = np.concatenate([rng.uniform(49.8, 61, 500), [51.05, 50.95, 0.0]])
    lon = np.concatenate([rng.uniform(-8.3, 2, 500), [-0.04, -0.05, -0.0]])
    gl, gn = grid_cell(lat, lon)
    assert np.array_equal(core.snap(lat), gl) and np.array_equal(core.snap(lon), gn)
    assert core.cell_key(51.0, -0.0) == "51.000_0.000"


def test_min_hours_is_the_features_rule():
    from dipcast.model.features import MIN_HOURS_PER_DAY
    assert core.MIN_HOURS_PER_DAY == MIN_HOURS_PER_DAY


def test_names():
    assert core.cell_from_name("archive_50.900_-1.800_2023dec.parquet") == (50.9, -1.8)
    assert core.year_from_name("archive_50.900_-1.800_2023dec.parquet") == 2023
    assert core.year_from_name("archive_50.900_-1.800_2026a.parquet") == 2026
    assert core.cell_from_name("51.000_0.100.parquet") == (51.0, 0.1)
    assert core.year_from_name("51.000_0.100.parquet") is None
    assert core.cell_from_name("open_meteo_calls.json") is None


def test_map_cells_centre_nearest_none_and_outside():
    lat = np.array([51.2000001, 51.1, 50.9999999])     # stored floats are not exact
    lon = np.array([-0.1, -0.0000001, 0.1])
    valid = np.array([[True, True, False],
                      [True, False, True],
                      [False, False, False]])
    m = core.map_cells([(51.2, -0.1), (51.1, 0.0), (51.0, 0.1), (52.0, 0.0), (51.2, 0.1)], lat, lon, valid)
    got = {(r.cell_lat, r.cell_lon): r for r in m.itertuples()}
    assert got[(51.2, -0.1)].how == "centre" and got[(51.2, -0.1)].km == 0
    c = got[(51.1, 0.0)]   # its own point is sea: 0.1 degree of longitude (7 km) is nearer than 0.1 of latitude (11 km)
    assert c.how == "nearest with data" and (c.grid_lat, c.grid_lon) == (51.1, -0.1)
    assert c.km == pytest.approx(6.98, abs=0.01)
    assert got[(51.0, 0.1)].how == "nearest with data" and (got[(51.0, 0.1)].grid_lat, got[(51.0, 0.1)].grid_lon) == (51.1, 0.1)
    assert got[(52.0, 0.0)].how == "outside area"
    assert got[(51.2, 0.1)].how == "nearest with data"
    none = core.map_cells([(51.0, 0.0)], lat, lon, np.zeros((3, 3), dtype=bool))
    assert none.how.tolist() == ["none"]


# ------------------------------------------------------------------ reading files
def test_decode_times():
    a = core.decode_times(np.array([1086960, 1086961]), "hours since 1900-01-01 00:00:00.0")   # 45,290 days
    assert a[0] == pd.Timestamp("2024-01-01 00:00", tz="UTC") and a[1] - a[0] == pd.Timedelta(hours=1)
    b = core.decode_times(np.array([1704067200]), "seconds since 1970-01-01")
    assert b[0] == pd.Timestamp("2024-01-01", tz="UTC")
    with pytest.raises(ValueError):
        core.decode_times([1], "fortnights since 1900-01-01")


def test_read_netcdf3_packed_with_fill_and_0_to_360_longitude(tmp_path):
    times = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
    tp = np.arange(5 * 3 * 3, dtype=float).reshape(5, 3, 3) / 1e5
    tp[:, 0, 2] = np.nan
    p = tmp_path / "x.nc"
    write_nc3(p, times, GRID_LAT, GRID_LON, tp, lon360=True)
    f = core.read_tp(p)
    assert (f.times == times).all()
    assert np.allclose(core.snap(f.lon), GRID_LON) and np.allclose(core.snap(f.lat), GRID_LAT)
    assert np.isnan(f.tp[:, 0, 2]).all()
    ok = np.isfinite(tp)
    assert np.allclose(f.tp[ok], tp[ok], atol=2e-8)
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("data_0.nc", p.read_bytes())
    g = core.read_tp(z.getvalue())
    assert np.allclose(np.nan_to_num(g.tp), np.nan_to_num(f.tp))
    with pytest.raises(ValueError):
        core.read_tp(b"GRIB....")
    with pytest.raises(ValueError):
        core.read_tp(b"<html>error</html>")


def test_read_netcdf4_like_the_new_cds(tmp_path):
    h5py = pytest.importorskip("h5py")
    times = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    tp = np.random.default_rng(0).random((4, 3, 3)).astype("f4") / 1000
    tp[:, 2, 0] = np.nan
    p = tmp_path / "y.nc"
    with h5py.File(p, "w") as f:
        t = f.create_dataset("valid_time", data=((times.tz_convert(None) - pd.Timestamp("1970-01-01"))
                                                 // pd.Timedelta(seconds=1)).to_numpy().astype("int64"))
        t.attrs["units"] = "seconds since 1970-01-01"
        la = f.create_dataset("latitude", data=np.array(GRID_LAT))
        lo = f.create_dataset("longitude", data=np.array(GRID_LON))
        for d in (t, la, lo):
            d.make_scale(d.name.strip("/"))
        v = f.create_dataset("tp", data=tp)
        for k, d in enumerate((t, la, lo)):
            v.dims[k].attach_scale(d)
        v.attrs["units"] = "m"
    g = core.read_tp(p)
    assert (g.times == times).all()
    assert np.allclose(np.nan_to_num(g.tp), np.nan_to_num(tp.astype(float)))


def test_an_expver_axis_is_merged_first_value_with_data():
    x = np.full((2, 2, 1, 1), np.nan)
    x[0, 0, 0, 0] = 1.0    # final data at the first step
    x[1, 1, 0, 0] = 2.0    # preliminary data at the second
    got = core._arrange(x, ["time", "expver", "lat", "lon"])
    assert got.shape == (2, 1, 1) and got[0, 0, 0] == 1.0 and got[1, 0, 0] == 2.0
    assert core._arrange(np.zeros((3, 1, 2, 2)), ["time", "number", "lat", "lon"]).shape == (3, 2, 2)


# ------------------------------------------------------------------ to_cells
def test_to_cells_writes_cache_shaped_files_that_the_features_read(tmp_path):
    out = tmp_path / "era5land"
    truth = write_months(out, ["2023-12", "2024-01", "2024-02"])
    cells_out = out / "cache" / "rain"
    cells = {(51.2, -0.1), (51.2, 0.1), (51.1, 0.0)}
    man = to_cells.run(out, cells_out, [2024], cells, all_land=False)
    assert man["years"]["2024"]["months"] == ["2024-01", "2024-02"]
    assert man["years"]["2024"]["previous_december"] is True
    assert man["years"]["2024"]["steps_below_minus_0.05mm"] == 0
    assert man["cells_by_how"] == {"centre": 2, "nearest with data": 1}
    f = cells_out / "archive_51.200_-0.100_2024.parquet"
    schema = pq.read_schema(f)
    assert schema.names == ["cell_lat", "cell_lon", "time", "precip_mm"]
    assert [str(schema.field(n).type) for n in schema.names] == ["double", "double", "timestamp[us, tz=UTC]", "double"]
    df = pd.read_parquet(f)
    assert df["time"].iloc[0] == pd.Timestamp("2024-01-01 00:00", tz="UTC")
    assert df["time"].iloc[-1] == pd.Timestamp("2024-02-29 23:00", tz="UTC")
    want = truth[(0, 0)].reindex(df["time"])
    assert np.allclose(df["precip_mm"].to_numpy(), want.to_numpy())     # every hour, the first one included
    # the sea cell takes its neighbour with data, (51.2, 0.0)
    sea = pd.read_parquet(cells_out / "archive_51.200_0.100_2024.parquet")
    assert np.allclose(sea["precip_mm"].to_numpy(), truth[(0, 1)].reindex(sea["time"]).to_numpy())
    cmap = pd.read_csv(cells_out / "ERA5LAND_CELLS.csv")
    assert set(cmap["how"]) == {"centre", "nearest with data"}
    # the model's own daily features read the files as they read the cached ones
    from dipcast.model.features import daily_rain_features
    d = daily_rain_features(df)
    exp = want.groupby(want.index.floor("D")).sum()
    assert np.allclose(d.set_index("day")["rain_d"].to_numpy(), exp.to_numpy())
    # resume: a second run leaves the year alone; --force rewrites it
    mtime = f.stat().st_mtime_ns
    to_cells.run(out, cells_out, [2024], cells, all_land=False)
    assert f.stat().st_mtime_ns == mtime


def test_to_cells_without_the_previous_december_leaves_the_first_hour_unknown(tmp_path):
    out = tmp_path / "e"
    truth = write_months(out, ["2024-01"])
    to_cells.run(out, out / "cache" / "rain", None, {(51.0, 0.0)}, all_land=False)
    df = pd.read_parquet(out / "cache" / "rain" / "archive_51.000_0.000_2024.parquet")
    assert np.isnan(df["precip_mm"].iloc[0]) and df["precip_mm"].iloc[1:].notna().all()
    assert np.allclose(df["precip_mm"].iloc[1:], truth[(2, 1)].reindex(df["time"].iloc[1:]).to_numpy())


def test_to_cells_all_land_and_refuses_the_shared_cache(tmp_path):
    out = tmp_path / "e"
    write_months(out, ["2024-01"])
    man = to_cells.run(out, out / "cells", None, None, all_land=True)
    assert man["cells"] == 8     # nine points, one of them sea
    with pytest.raises(SystemExit):
        to_cells.run(out, tmp_path / "data" / "cache" / "rain", None, {(51.0, 0.0)}, all_land=False)


# ------------------------------------------------------------------ fetch
class FakeClient:
    """Stands in for cdsapi.Client: writes `body` to the target, or raises the next error in `errors`."""

    def __init__(self, body: bytes = b"CDF\x01" + b"\0" * 100, errors=()):
        self.body, self.errors, self.calls = body, list(errors), []

    def retrieve(self, name, request, target):
        self.calls.append((name, request))
        if self.errors:
            e = self.errors.pop(0)
            if e:
                raise Exception(e)
        Path(target).write_bytes(self.body)


def _run(out, client, **kw):
    kw.setdefault("config", TOKEN)
    return fetch.run(out, "2024-01", "2024-03", core.DEFAULT_AREA, True, client_factory=lambda: client,
                     now=lambda: datetime(2026, 11, 20, tzinfo=UTC), free_bytes=lambda p: 10 ** 12, **kw)


def test_fetch_downloads_each_month_once_and_ledgers_it(tmp_path):
    c = FakeClient()
    assert _run(tmp_path, c) == fetch.OK
    assert [r["month"] for _, r in c.calls] == ["03", "02", "01"]    # newest first
    assert all(name == "reanalysis-era5-land" for name, _ in c.calls)
    rows = fetch.ledger_rows(tmp_path)
    assert [r["outcome"] for r in rows] == ["ok"] * 3
    assert rows[0]["bytes"] == 104 and len(rows[0]["sha256"]) == 64 and rows[0]["request"]["year"] == "2024"
    assert core.raw_file(tmp_path, "2024-02").exists()
    assert not list(tmp_path.rglob("*.part"))
    c2 = FakeClient()
    assert _run(tmp_path, c2) == fetch.OK and c2.calls == []         # resume: nothing asked again


def test_fetch_stops_at_the_first_failure_and_says_why(tmp_path):
    c = FakeClient(errors=[None, "403 Client Error: required licences not accepted"])
    assert _run(tmp_path, c) == fetch.FAILED
    rows = fetch.ledger_rows(tmp_path)
    assert [r["outcome"] for r in rows] == ["ok", "licence"]
    assert "Accept the ERA5-Land licence" in rows[-1]["hint"]
    assert len(c.calls) == 2 and not core.raw_file(tmp_path, "2024-02").exists()
    assert not list(tmp_path.rglob("*.part"))


def test_fetch_refuses_a_file_that_is_not_netcdf(tmp_path):
    assert _run(tmp_path, FakeClient(body=b"<html>queue</html>")) == fetch.FAILED
    assert fetch.ledger_rows(tmp_path)[-1]["outcome"] == "bad_file"
    assert not core.raw_file(tmp_path, "2024-03").exists()


def test_fetch_ceilings(tmp_path):
    c = FakeClient()
    assert _run(tmp_path, c, max_requests=1) == fetch.CEILING and len(c.calls) == 1
    c = FakeClient()
    assert _run(tmp_path / "b", c, max_gb=50e-9) == fetch.CEILING and len(c.calls) == 1   # 104 bytes > 50
    ticks = iter([0, 0, 0, 0, 7200, 7200, 7200])
    c = FakeClient()
    assert _run(tmp_path / "c", c, max_hours=1, clock=lambda: next(ticks)) == fetch.CEILING and len(c.calls) == 1
    c = FakeClient()
    assert fetch.run(tmp_path / "d", "2024-01", "2024-01", core.DEFAULT_AREA, client_factory=lambda: c,
                     config=TOKEN, free_bytes=lambda p: 10) == fetch.CEILING and c.calls == []


def test_fetch_needs_a_new_cds_key_and_a_scratch_folder(tmp_path):
    def never():
        raise AssertionError("no client without a key")
    assert fetch.run(tmp_path, "2024-01", "2024-01", core.DEFAULT_AREA, client_factory=never,
                     config=(None, None, "~/.cdsapirc")) == fetch.NO_KEY
    assert fetch.run(tmp_path / "data" / "cache" / "x", "2024-01", "2024-01", core.DEFAULT_AREA,
                     client_factory=never, config=TOKEN) == fetch.BAD_OUT
    assert "old CDS" in fetch.config_problem("https://cds.climate.copernicus.eu/api/v2", "abc", "rc")
    assert "colon" in fetch.config_problem(TOKEN[0], "12345:abcd", "rc")
    assert fetch.config_problem(*TOKEN) is None


def test_cds_config_reads_the_rc_file_and_prefers_the_environment(tmp_path):
    rc = tmp_path / "rc"
    rc.write_text("url: https://cds.climate.copernicus.eu/api\nkey: tok-123\n")
    assert fetch.cds_config({"CDSAPI_RC": str(rc)}) == ("https://cds.climate.copernicus.eu/api", "tok-123", str(rc))
    assert fetch.cds_config({"CDSAPI_URL": "u", "CDSAPI_KEY": "k"})[:2] == ("u", "k")
    assert fetch.cds_config({}, home=tmp_path)[:2] == (None, None)


def test_classify():
    assert fetch.classify("required licences not accepted")[0] == "licence"
    assert fetch.classify("401 Client Error: Unauthorized")[0] == "auth"
    assert fetch.classify("Request too large")[0] == "too_large"
    assert fetch.classify("500 Server Error")[0] == "failed"


def test_status_projects_from_the_ledger(tmp_path):
    assert _run(tmp_path, FakeClient(), max_requests=2) == fetch.CEILING
    s = fetch.status(tmp_path, "2024-01", "2024-03")
    assert s["on_disk"] == 2 and s["left"] == 1 and s["mean_mb_per_month"] == 0.0


# ------------------------------------------------------------------ the match check
def test_moments_match_numpy():
    rng = np.random.default_rng(5)
    x, y = rng.random(1000), rng.random(1000)
    y = 0.5 * x + y
    m = core.Moments()
    for k in range(0, 1000, 137):
        m.add(x[k:k + 137], y[k:k + 137])
    assert m.r() == pytest.approx(np.corrcoef(x, y)[0, 1], abs=1e-12)
    assert m.bias() == pytest.approx(np.mean(x - y))
    m.add(np.array([np.nan, 1.0]), np.array([1.0, np.nan]))
    assert m.n == 1000


def test_daily_pairs_use_the_hour_ending_utc_day_and_the_20_hour_rule():
    t = pd.date_range("2024-01-01 00:00", periods=48, freq="h", tz="UTC")
    h = pd.DataFrame({"time": t, "era": 1.0, "ref": 2.0})
    d = core.daily_pairs(h.drop(index=range(30, 40)))     # day 2 keeps 14 hours
    assert d["day"].tolist() == [pd.Timestamp("2024-01-01", tz="UTC")]
    assert d["era"].iloc[0] == 24 and d["ref"].iloc[0] == 48


def _write_cells(d: Path, series: dict, tag: str = "2024") -> None:
    d.mkdir(parents=True, exist_ok=True)
    for (la, lo), s in series.items():
        pd.DataFrame({"cell_lat": la, "cell_lon": lo, "time": s.index.astype("datetime64[us, UTC]"),
                      "precip_mm": s.to_numpy()}).to_parquet(d / f"archive_{core.cell_key(la, lo)}_{tag}.parquet")


def _cells(n=12, seed=0):
    return {(51.0 + 0.1 * k, -1.0): truth_rain("2024-01-01 00:00", "2024-05-31 23:00", seed + k) for k in range(n)}


def test_match_check_identical_series_pass_both_kinds_and_leave_the_reference_alone(tmp_path, monkeypatch):
    monkeypatch.setitem(mc.MIN_CELL_DAYS, "best_match", 1000)   # a small synthetic set
    s = _cells()
    _write_cells(tmp_path / "era", s)
    _write_cells(tmp_path / "ref", s)
    for kind in ("era5_land", "best_match"):
        rep = mc.run(tmp_path / "era", [tmp_path / "ref"], kind, {2024})
        assert rep["verdict"] == "PASS", rep["tests"]
        assert rep["reference_unchanged"] and rep["cells_compared"] == 12
        assert rep["results"]["hourly_r"] == pytest.approx(1.0)


def test_match_check_catches_a_one_hour_label_shift(tmp_path):
    s = _cells()
    _write_cells(tmp_path / "era", s)
    _write_cells(tmp_path / "ref", {c: v.shift(1) for c, v in s.items()})   # the reference lags one hour
    rep = mc.run(tmp_path / "era", [tmp_path / "ref"], "era5_land", None)
    assert rep["verdict"] == "FAIL"
    r = rep["results"]
    assert r["hourly_r_lag_plus_1h"] == pytest.approx(1.0) and r["hourly_r"] < 0.5
    assert not rep["tests"][0]["pass"] and not rep["tests"][1]["pass"]


def test_match_check_catches_metres_left_unconverted(tmp_path, monkeypatch):
    monkeypatch.setitem(mc.MIN_CELL_DAYS, "best_match", 1000)
    s = _cells()
    _write_cells(tmp_path / "era", {c: v / 1000 for c, v in s.items()})
    _write_cells(tmp_path / "ref", s)
    rep = mc.run(tmp_path / "era", [tmp_path / "ref"], "best_match", None)
    assert rep["verdict"] == "FAIL"
    assert rep["results"]["daily_relative_diff"] == pytest.approx(-0.999)


def test_match_check_gives_no_verdict_on_too_little(tmp_path):
    s = _cells(n=3)
    _write_cells(tmp_path / "era", s)
    _write_cells(tmp_path / "ref", s)
    assert mc.run(tmp_path / "era", [tmp_path / "ref"], "era5_land", None)["verdict"] == "NO VERDICT"


def test_match_check_first_reference_folder_wins_and_disagreements_are_counted(tmp_path):
    s = _cells()
    _write_cells(tmp_path / "era", s)
    _write_cells(tmp_path / "ref1", s)
    _write_cells(tmp_path / "ref2", {c: v + 1.0 for c, v in s.items()})
    rep = mc.run(tmp_path / "era", [tmp_path / "ref1", tmp_path / "ref2"], "era5_land", None)
    assert rep["verdict"] == "PASS"
    assert rep["results"]["reference_hours_two_files_disagree"] == sum(len(v) for v in s.values())


def test_match_check_follows_the_grid_point_open_meteo_recorded(tmp_path):
    """C1's era5_land files keep the grid point Open-Meteo used. The check compares a cell with ERA5-Land there."""
    s = _cells()
    _write_cells(tmp_path / "era", {(la, round(lo + 0.1, 3)): v for (la, lo), v in s.items()})   # one column east
    ref = tmp_path / "ref" / "rain" / "2024"
    ref.mkdir(parents=True)
    for (la, lo), v in s.items():
        pd.DataFrame({"cell_lat": la, "cell_lon": lo, "time": v.index.astype("datetime64[us, UTC]"),
                      "precip_mm": v.to_numpy(), "grid_lat": la + 0.0001, "grid_lon": lo + 0.1}
                     ).to_parquet(ref / f"{core.cell_key(la, lo)}.parquet")
    rep = mc.run(tmp_path / "era", [tmp_path / "ref"], "era5_land", None)
    assert rep["verdict"] == "PASS" and rep["cells_compared_at_open_meteo_point"] == 12
    # best_match files record no point, and the cells themselves are not in the ERA5-Land folder
    assert mc.run(tmp_path / "era", [tmp_path / "ref"], "best_match", None)["cells_compared"] == 0


def test_neighbour_check_rules(tmp_path):
    nc = _load("neighbour_check")
    # ERA5-Land's 0.1 degree grid gives every cell its own point; ERA5's 0.25 degree grid shares points
    assert nc.era5land_point(52.0, -1.0) != nc.era5land_point(52.0, -0.9)
    assert nc.era5_point(52.0, -1.0) == nc.era5_point(52.1, -1.0)
    # O1280 near 52 N: rows about 0.07 degrees apart, points about 0.16 degrees apart along a row
    lat = nc.gaussian_latitudes()
    assert len(lat) == 2560 and 0.06 < abs(np.diff(lat[500:510])).mean() < 0.08
    same_ew = sum(nc.o1280_point(52.0, -2.0 + 0.1 * k) == nc.o1280_point(52.0, -1.9 + 0.1 * k) for k in range(20))
    same_ns = sum(nc.o1280_point(52.0 + 0.1 * k, -2.0) == nc.o1280_point(52.1 + 0.1 * k, -2.0) for k in range(20))
    assert same_ew > 0 and same_ns == 0
    d = tmp_path / "rain"
    _write_cells(d, {(52.0, -1.0): pd.Series([0.1, 0.0], index=pd.date_range("2024-01-01", periods=2, freq="h",
                                                                               tz="UTC")),
                     (52.0, -0.9): pd.Series([0.1, 0.0], index=pd.date_range("2024-01-01", periods=2, freq="h",
                                                                               tz="UTC")),
                     (52.1, -1.0): pd.Series([0.2, 0.0], index=pd.date_range("2024-01-01", periods=2, freq="h",
                                                                               tz="UTC"))})
    out = nc.score(nc.neighbour_pairs(nc.series_hashes(d, 2024)))
    assert out["pairs"] == 2 and out["identical"] == 1 and out["identical_east_west"] == 1
    assert out["agree: ERA5-Land 0.1"] == 0.5


def test_match_check_thresholds_are_the_records(tmp_path):
    """The thresholds in the code are the ones written in the record before any comparison."""
    text = (ROOT / "docs" / "ERA5-LAND-BULK-RAIN-2026-11.md").read_text()
    for kind, rows in mc.THRESHOLDS.items():
        for name, op, value in rows:
            assert name.split()[0] in text, name
    for line in ("S1", "S2", "S3", "S4", "B1", "B2", "B3", "B4"):
        assert f"| {line} |" in text
    rep_rows = mc.verdict("best_match", {"daily_r": 0.95, "daily_relative_diff": 0.05, "daily_share_within_0.5mm": 0.9,
                                         "share_of_cells_daily_r_ge_0.80": 0.95, "cells": 50,
                                         "paired_cell_days": 20000})
    assert rep_rows[0] == "PASS"
    assert json.dumps(rep_rows[1])
