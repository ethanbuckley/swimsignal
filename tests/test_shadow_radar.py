"""The radar shadow (src/dipcast/shadow_radar.py, src/dipcast/radar_live.py, docs/RADAR-SHADOW-2026-11.md): the frozen
files and the off switch, the issue hour, the radar step against a fake bucket (carry, caps, stale feed, stop rule),
radar put into the forecast rain only where the bucket had published it, real overflow rows through the eighteen
frozen models, what it logs, and that the published forecast and the rain requests do not change. No test here
touches the network."""

import json
import shutil
from datetime import date
from pathlib import Path

import duckdb
import httpx
import numpy as np
import pandas as pd
import pytest

from dipcast import config, radar_live
from dipcast import shadow_radar as sr
from dipcast.ingest import met_office_radar as mor
from dipcast.model import live_status as ls
from dipcast.model.features import ALL_FEATURES

TZ = "Europe/London"
ROOT = Path(__file__).resolve().parents[1]
NOW = pd.Timestamp("2026-11-20 12:40", tz="UTC")      # GMT: local = UTC; issue hour 12


@pytest.fixture(autouse=True)
def _fresh():
    sr.clear_cache()
    yield
    sr.clear_cache()


# ------------------------------------------------------------------ the frozen files and the off switch
def test_the_committed_files_are_the_frozen_models():
    m = sr.models()
    assert m is not None and sorted(m["R0S"]) == list(sr.HOURS) and sorted(m["PS"]) == list(sr.HOURS)
    assert list(m["C"].features) == list(ALL_FEATURES) and list(m["P"].features) == list(ALL_FEATURES)
    assert list(m["R0S"][12].features) == [*ALL_FEATURES, *ls.STATUS]
    # The hashes are #694's and #697's own score files'.
    s694 = json.loads((ROOT / "docs/RADAR-ISSUE-HOUR-TEST-2026-11-score.json").read_text())["frozen_model_sha256"]
    s697 = json.loads((ROOT / "docs/RADAR-PLUS-STATUS-TEST-2026-11-score.json").read_text())["frozen_model_sha256"]
    assert sr.SHA256["C"] == s694["C"] and sr.SHA256["P"] == s694["P"]
    for h in sr.HOURS:
        assert sr.SHA256[f"R0S_{h:02d}"] == s697[f"R0S@{h:02d}"] and sr.SHA256[f"PS_{h:02d}"] == s697[f"PS@{h:02d}"]
    # And the statement lists the same eighteen.
    doc = (ROOT / "docs/RADAR-SHADOW-2026-11.md").read_text()
    assert all(v in doc for v in sr.SHA256.values())


def test_off_without_a_file_or_with_an_altered_one(tmp_path, monkeypatch):
    for f in sr.MODEL_DIR.glob("*.pkl"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setattr(sr, "MODEL_DIR", tmp_path)
    sr.clear_cache()
    assert sr.models() is not None
    (tmp_path / "PS_09.pkl").write_bytes((tmp_path / "PS_09.pkl").read_bytes() + b"\0")
    sr.clear_cache()
    assert sr.models() is None
    (tmp_path / "PS_09.pkl").unlink()
    sr.clear_cache()
    assert sr.models() is None


def test_off_unless_the_variable_is_set(monkeypatch):
    monkeypatch.setattr(config, "RADAR_SHADOW", False)
    assert sr.prefetch([(52.0, -1.0)]) is None and sr.build_radar() is None


@pytest.mark.parametrize("hhmm, want", [("00:10", 0), ("01:29", 0), ("01:30", 3), ("07:40", 9), ("12:40", 12),
                                        ("19:29", 18), ("22:29", 21), ("23:59", 21)])
def test_the_nearest_issue_hour(hhmm, want):
    day = pd.Timestamp("2026-11-20", tz=TZ)
    assert sr.issue_hour(pd.Timestamp(f"2026-11-20 {hhmm}", tz=TZ), day) == want


def test_in_summer_time_the_hour_counts_from_local_midnight():
    day = pd.Timestamp("2027-06-20", tz=TZ)
    assert sr.issue_hour(pd.Timestamp("2027-06-20 00:20", tz=TZ), day) == 0      # 23:20 UTC the day before
    assert radar_live.window_start(pd.Timestamp("2027-06-20 10:00", tz=TZ)) == pd.Timestamp("2027-06-17 23:00", tz="UTC")


# ------------------------------------------------------------------ the radar step, against a fake bucket
CELLS = [(52.0, -1.0), (54.4, -2.9)]


class Bucket:
    """A fake S3 bucket: composites every 15 minutes from `first` to `last`, each reaching the bucket `delay` later;
    every composite's rain rate is `rate` mm/h over the whole grid. Counts what it serves."""

    def __init__(self, first, last, delay=pd.Timedelta(minutes=7), rate=2.0, missing=()):
        self.times = [t for t in pd.date_range(first, last, freq="15min") if t not in set(missing)]
        self.delay, self.rate = delay, rate
        self.listings, self.gets = 0, []

    def key(self, t):
        return f"radar/{t:%Y/%m/%d}/{t:%Y%m%d%H%M}_ODIM_ng_radar_rainrate_composite_1km_UK.h5"

    def handler(self, request):
        if request.url.path == "/":
            self.listings += 1
            prefix = request.url.params["prefix"]
            items = "".join(f"<Contents><Key>{self.key(t)}</Key><LastModified>{(t + self.delay).isoformat()}"
                            f"</LastModified><Size>500000</Size></Contents>"
                            for t in self.times if self.key(t).startswith(prefix))
            return httpx.Response(200, content=f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                                               f'{items}</ListBucketResult>'.encode())
        self.gets.append(request.url.path)
        return httpx.Response(200, content=f"{self.rate}".encode() + b"\0" * 1000)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handler))


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(radar_live, "_h5py_ok", lambda: True)
    monkeypatch.setattr(radar_live, "_sleep", lambda s: None)
    # A composite's body is its rain rate as text: the reader makes the grid from it.
    monkeypatch.setattr(mor, "read_composite", lambda data: np.full((mor.NY, mor.NX), float(data.split(b"\0")[0])))


def _cold_bucket(now=NOW, **kw):
    return Bucket(radar_live.window_start(now) - pd.Timedelta(hours=2), now - pd.Timedelta(minutes=10), **kw)


def test_a_cold_start_reads_the_window_and_the_hours_carry_their_publish_time(tmp_path, fake):
    b = _cold_bucket()
    r = radar_live.update(CELLS, NOW, client=b.client(), state_dir=tmp_path)
    assert r.state == "ok" and r.usable()
    first = radar_live.window_start(NOW)                     # 2026-11-18 00:00 UTC (GMT)
    assert first == pd.Timestamp("2026-11-18 00:00", tz="UTC")
    # Composites from an hour before the window's first hour label to the newest: 4 x 60.5 h + 1 = 243 + 2.
    assert r.stats["files"] == len([t for t in b.times if t >= first - pd.Timedelta(hours=1)])
    assert r.stats["listings"] == 4                          # 17, 18, 19 and 20 Nov
    h = r.hours
    assert set(h["time"]) == set(pd.date_range(first, NOW.floor("h"), freq="h"))
    full = h[h["time"] <= pd.Timestamp("2026-11-20 12:00", tz="UTC")]
    assert np.allclose(full["radar_mm"], 2.0) and np.allclose(full["coverage"], 1.0)
    # An hour's publish time is its last composite's.
    one = h[(h["time"] == pd.Timestamp("2026-11-20 11:00", tz="UTC"))]
    assert (pd.to_datetime(one["published_at"], utc=True) == pd.Timestamp("2026-11-20 11:07", tz="UTC")).all()
    # The carry is written in the state folder with the credit, and holds no hour total.
    meta = __import__("pyarrow.parquet", fromlist=["x"]).read_schema(tmp_path / radar_live.SNAPSHOTS).metadata
    assert b"CC BY-SA" in meta[b"credit"] and meta[b"cells_key"].decode() == radar_live.cells_key(CELLS)


def test_the_next_build_fetches_only_what_is_new(tmp_path, fake):
    b = _cold_bucket()
    radar_live.update(CELLS, NOW, client=b.client(), state_dir=tmp_path)
    later = NOW + pd.Timedelta(hours=3)
    b.times += list(pd.date_range(NOW - pd.Timedelta(minutes=5), later - pd.Timedelta(minutes=10), freq="15min"))
    b.gets.clear()
    r = radar_live.update(CELLS, later, client=b.client(), state_dir=tmp_path)
    assert r.state == "ok" and r.stats["files"] == len(b.gets) == 12      # three hours of composites
    # Another cell set starts again from nothing.
    b.gets.clear()
    r = radar_live.update(CELLS[:1], later, client=b.client(), state_dir=tmp_path)
    assert r.stats["files"] > 200


def test_a_composite_with_no_data_in_any_cell_is_not_fetched_again(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(mor, "read_composite", lambda data: np.full((mor.NY, mor.NX), np.nan))
    b = _cold_bucket()
    r = radar_live.update(CELLS, NOW, client=b.client(), state_dir=tmp_path)
    assert r.state == "ok" and (r.hours["coverage"] == 0).all() and r.hours["radar_mm"].isna().all()
    b.gets.clear()
    assert radar_live.update(CELLS, NOW, client=b.client(), state_dir=tmp_path).stats["files"] == 0 and not b.gets


def test_a_missing_composite_lowers_the_hours_coverage(tmp_path, fake):
    gap = pd.Timestamp("2026-11-20 09:30", tz="UTC")
    r = radar_live.update(CELLS, NOW, client=_cold_bucket(missing=[gap]).client(), state_dir=tmp_path)
    h = r.hours.set_index("time")
    assert (h.loc[pd.Timestamp("2026-11-20 10:00", tz="UTC"), "coverage"] < radar_live.MIN_COVERAGE).all()
    assert (h.loc[pd.Timestamp("2026-11-20 11:00", tz="UTC"), "coverage"] == 1.0).all()


def test_over_a_cap_falls_back_and_three_in_a_row_stop_it(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(radar_live, "MAX_FILES", 10)
    for k in range(3):
        r = radar_live.update(CELLS, NOW, client=_cold_bucket().client(), state_dir=tmp_path)
        assert r.state == "fallback" and r.reason == "over a cap" and r.stats["files"] == 10
    b = _cold_bucket()
    r = radar_live.update(CELLS, NOW, client=b.client(), state_dir=tmp_path)
    assert r.state == "stopped" and b.listings == 0 and not b.gets
    (tmp_path / radar_live.STATUS_FILE).unlink()               # deleting the counter restarts it
    monkeypatch.setattr(radar_live, "MAX_FILES", 300)
    assert radar_live.update(CELLS, NOW, client=_cold_bucket().client(), state_dir=tmp_path).state == "ok"


def test_the_time_cap(tmp_path, fake, monkeypatch):
    ticks = iter(np.arange(0.0, 10_000.0, 30.0))
    monkeypatch.setattr(radar_live, "_clock", lambda: next(ticks))
    r = radar_live.update(CELLS, NOW, client=_cold_bucket().client(), state_dir=tmp_path)
    assert r.state == "fallback" and r.stats["files"] < 10


def test_a_stale_feed_a_failed_listing_or_no_h5py_falls_back(tmp_path, fake, monkeypatch):
    old = Bucket(radar_live.window_start(NOW) - pd.Timedelta(hours=2), NOW - pd.Timedelta(minutes=95))
    r = radar_live.update(CELLS, NOW, client=old.client(), state_dir=tmp_path)
    assert r.state == "fallback" and "90 min" in r.reason and not old.gets
    down = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(503)))
    assert radar_live.update(CELLS, NOW, client=down, state_dir=tmp_path).state == "fallback"
    monkeypatch.setattr(radar_live, "_h5py_ok", lambda: False)
    b = _cold_bucket()
    r = radar_live.update(CELLS, NOW, client=b.client(), state_dir=tmp_path)
    assert r.state == "fallback" and "h5py" in r.reason and b.listings == 0


# ------------------------------------------------------------------ radar into the forecast rain
def _radar(cells, first, last, mm=1.0, coverage=1.0, listed=NOW, state="ok"):
    t = pd.date_range(first, last, freq="h")
    h = pd.concat([pd.DataFrame({"cell_lat": a, "cell_lon": b, "time": t, "radar_mm": mm, "coverage": coverage,
                                 "published_at": t + pd.Timedelta(minutes=7)}) for a, b in cells], ignore_index=True)
    return radar_live.RadarHours(state, listed, listed - pd.Timedelta(minutes=10), listed - pd.Timedelta(minutes=3),
                                 hours=h)


def _rain(cells, mm=0.2):
    t = pd.date_range(NOW.floor("D") - pd.Timedelta(days=40), periods=24 * 45, freq="h")
    return pd.concat([pd.DataFrame({"cell_lat": a, "cell_lon": b, "time": t, "precip_mm": mm,
                                    "issued_at": NOW - pd.Timedelta(hours=2)}) for a, b in cells], ignore_index=True)


def test_radar_goes_in_only_inside_the_window_and_where_covered():
    cells = [(52.0, -1.0)]
    first = radar_live.window_start(NOW)
    r = _radar(cells, first - pd.Timedelta(hours=5), NOW.floor("h"))
    low = r.hours["time"] == pd.Timestamp("2026-11-19 06:00", tz="UTC")
    r.hours.loc[low, "coverage"] = 0.85                      # one hour under 0.9 keeps the forecast
    mixed, counts = sr.mixed_rain(_rain(cells), r)
    m = mixed.set_index("time")["precip_mm"]
    assert m[first - pd.Timedelta(hours=1)] == 0.2           # before the window: forecast
    assert m[first] == 1.0 and m[NOW.floor("h")] == 1.0      # inside: radar
    assert m[pd.Timestamp("2026-11-19 06:00", tz="UTC")] == 0.2
    assert m[NOW.floor("h") + pd.Timedelta(hours=1)] == 0.2  # after the listing: forecast
    c = counts.iloc[0]
    assert c["radar"] == 60 and c["forecast"] == 1 and c["late"] == 1
    # The seven short features of today come from the mixed rain: hours labelled 00:00 to 12:00 radar, 11 forecast.
    sf = sr.short_features(mixed, pd.Timestamp("2026-11-20", tz=TZ)).iloc[0]
    assert sf["rain_d"] == pytest.approx(13 * 1.0 + 11 * 0.2) and sf["rain_d1"] == pytest.approx(23 * 1.0 + 0.2)


def test_hours_spilled_in_the_24_hours_before_the_issue():
    ev = pd.DataFrame({"site_id": ["A", "A", "B"],
                       "start": pd.to_datetime(["2026-11-19 10:00", "2026-11-20 09:00", "2026-11-18 00:00"], utc=True),
                       "end": pd.to_datetime(["2026-11-19 14:40", "2026-11-20 12:00", "2026-11-20 20:00"], utc=True)})
    h = sr.hours_before(ev, NOW)
    assert h["A"] == pytest.approx(2.0 + 3.0) and h["B"] == 24.0


# ------------------------------------------------------------------ real overflow rows, the eighteen frozen models
def _real_overflows() -> pd.DataFrame:
    """Sixteen real overflows from the committed annual returns (2025), four each at United Utilities, Thames,
    Severn Trent and Yorkshire, all with a site offset in the frozen fits, with their own coordinates and covariates."""
    a = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    a = a[(a["year"] == 2025) & a["site_id"].notna() & a["lat"].notna() & a["lta_spills"].notna()]
    a = a[a["site_id"].isin(sr.models()["R0S"][12].site_offset)].sort_values("site_id")
    pick = pd.concat([a[a["company"] == c].head(4) for c in
                      ("United Utilities", "Thames Water", "Severn Trent Water", "Yorkshire Water")])
    return pick[["site_id", "company", "lat", "lon", "lta_spills", "spill_hours", "edm_operational_pct"]].reset_index(drop=True)


def _status(ov, read_at=NOW - pd.Timedelta(hours=1)):
    return pd.DataFrame({"spill_days_7d": ([2.0, 0.0, 0.0, 1.0] * 4)[:len(ov)], "spill_hours_24h": 0.0,
                         "last_reading": read_at.tz_convert("UTC"), "window_gap_h": 2.0},
                        index=pd.Index(ov["site_id"], name="site_id"))


def _real_case():
    from dipcast.ingest.rainfall import cells_for_sites
    from dipcast.model import forecast
    ov = _real_overflows()
    days = pd.date_range("2026-11-18", periods=7, freq="D", tz=TZ)          # two past days, today, leads 1 to 4
    cells = cells_for_sites(ov["lat"], ov["lon"])
    rain = _rain(cells, mm=0.3)
    p_raw, avail, sd = forecast.spill_probabilities(ov, days, forecast._model(), rain=rain, return_frame=True)
    # Per company: one spilling at issue, one known and dry, one known and dry, one whose last reading is 9 h old.
    ov = ov.assign(status=[1, 0, 0, 0] * 4, data_state="live")
    table = _status(ov)
    table.loc[ov["site_id"].iloc[3::4], "last_reading"] = (NOW - pd.Timedelta(hours=9)).tz_convert("UTC")
    events = pd.DataFrame({"site_id": ov["site_id"].iloc[0::4].to_numpy(),
                           "start": NOW - pd.Timedelta(hours=5), "end": NOW - pd.Timedelta(minutes=30)})
    return ov, days, cells, rain, p_raw, avail, sd, table, events


def test_real_overflow_rows_through_the_frozen_models():
    ov, days, cells, rain, p_raw, avail, sd, table, events = _real_case()
    assert len(ov) == 16 and ov["company"].nunique() == 4 and avail.all()
    frozen = sr.models()
    sd0, rain0 = sd.copy(), rain.copy()
    first = radar_live.window_start(NOW)

    def run(radar):
        return sr.shadow(sd, ov, days, 2, NOW, rain, radar=radar, frozen=frozen, status_table=table, events=events)
    # Radar the same as the forecast: the candidate's features are the reference's, so each model gives on the
    # shadow's row exactly what it gives on production's own frame.
    same = run(_radar(cells, first, NOW.floor("h"), mm=0.3))
    pd.testing.assert_frame_equal(sd, sd0)
    pd.testing.assert_frame_equal(rain, rain0)
    assert same["issue_hour"] == 12 and (same["state"] == "ok").all()
    known = same["known"]
    assert known.tolist() == [True, True, True, False] * 4 and same["english"].all()
    assert same["pair"].tolist() == ["status", "status", "status", "no_status"] * 4
    f = sd[sd["day"] == days[2]].set_index("site_id").reindex(ov["site_id"]).reset_index()
    f = f.fillna({c: 0.0 for c in ALL_FEATURES})
    st = sr.status_inputs(ov, NOW, table, events)
    assert st["spill_hours_24h"].tolist()[:4] == pytest.approx([4.5, 0.0, 0.0, np.nan], nan_ok=True)
    assert st["spilling_at_issue"].tolist()[:4] == pytest.approx([1.0, 0.0, 0.0, np.nan], nan_ok=True)
    fs = f.assign(**{c: st[c].to_numpy() for c in ls.STATUS})
    assert same["ps"] == pytest.approx(frozen["PS"][12].predict(fs), rel=1e-12)
    assert same["r0s"] == pytest.approx(frozen["R0S"][12].predict(fs), rel=1e-12)
    assert same["p"] == pytest.approx(frozen["P"].predict(f), rel=1e-12)
    assert same["c"] == pytest.approx(frozen["C"].predict(f), rel=1e-12)
    assert np.array_equal(same["candidate"], np.where(known, same["r0s"], same["c"]))
    assert np.array_equal(same["reference"], np.where(known, same["ps"], same["p"]))
    assert ((same["candidate"] > 0) & (same["candidate"] < 1)).all()
    # An overflow spilling at issue is near certain under both status models.
    assert (same["ps"][0::4] > 0.5).all() and (same["r0s"][0::4] > 0.5).all()

    # Heavy radar since two days ago: the seven short features rise, so the rain-monotone models cannot fall.
    wet = run(_radar(cells, first, NOW.floor("h"), mm=4.0))
    assert np.array_equal(wet["reference"], same["reference"])     # the reference never sees radar
    assert (wet["c"] >= same["c"] - 1e-12).all() and (wet["c"] > same["c"] + 1e-3).any()
    assert (wet["r0s"][known] > same["r0s"][known] + 1e-3).sum() >= 6

    # No usable radar this build: the candidate is the reference on every row.
    for state in ("fallback", "stopped"):
        fb = run(_radar(cells, first, NOW.floor("h"), mm=4.0, state=state))
        assert (fb["state"] == state).all() and np.array_equal(fb["candidate"], fb["reference"])
    # A cell with no radar row at all is a fallback on its rows only.
    part = _radar(cells, first, NOW.floor("h"), mm=4.0)
    gone = (part.hours["cell_lat"] == cells[0][0]) & (part.hours["cell_lon"] == cells[0][1])
    part.hours = part.hours[~gone]
    out = run(part)
    in_gone = (sd[sd["day"] == days[2]].set_index("site_id").reindex(ov["site_id"])[["cell_lat", "cell_lon"]]
               .round(3).apply(tuple, axis=1) == tuple(np.round(cells[0], 3))).to_numpy()
    assert in_gone.any() and (out["state"][in_gone] == "fallback").all()
    assert np.array_equal(out["candidate"][in_gone], out["reference"][in_gone])


def test_logs_each_overflow_once_per_build_in_its_own_table(tmp_path):
    ov, days, cells, rain, p_raw, avail, sd, table, events = _real_case()
    radar = _radar(cells, radar_live.window_start(NOW), NOW.floor("h"), mm=1.0)
    out = sr.shadow(sd, ov, days, 2, NOW, rain, radar=radar, frozen=sr.models(), status_table=table, events=events)
    db = tmp_path / "state.duckdb"
    from dipcast.model.forecast import calibrate_by_lead  # noqa: F401 - the forecast's own import, as a build has it
    from dipcast.shadow_combined import rain_issue_times
    rain_at = rain_issue_times(rain, ov)
    n = sr.log_shadow(NOW, ov, days[2], p_raw[:, 2], p_raw[:, 2] * 0.5, p_raw[:, 2] * 0.5, out, rain_at, "spill=x", path=db)
    assert n == 16
    # The same overflows from a second spot in the same build are not logged again.
    assert sr.log_shadow(NOW, ov, days[2], p_raw[:, 2], p_raw[:, 2], p_raw[:, 2], out, rain_at, "spill=x", path=db) == 0
    con = duckdb.connect(str(db))
    try:
        t = con.execute(f"SELECT * FROM {sr.TABLE} ORDER BY site_id").df()
        tables = con.execute("SHOW TABLES").df()["name"].tolist()
    finally:
        con.close()
    assert sr.TABLE in tables and not {"shadow_combined_v1", "shadow_regional_v1"} & set(tables)
    assert list(t.columns) == list(sr.COLUMNS) and len(t) == 16
    assert (t["rule"] == sr.RULE).all() and (t["models"] == sr.MODELS).all() and (t["issue_hour"] == 12).all()
    assert (pd.to_datetime(t["target_day"]).dt.date == date(2026, 11, 20)).all() and (t["radar_state"] == "ok").all()
    # The pre-read checks hold on the logged rows.
    st = t["pair"] == "status"
    assert np.allclose(t.loc[st, "p_candidate"], t.loc[st, "p_r0s"]) and np.allclose(t.loc[~st, "p_candidate"], t.loc[~st, "p_c"])
    assert np.allclose(t.loc[st, "p_reference"], t.loc[st, "p_ps"]) and np.allclose(t.loc[~st, "p_reference"], t.loc[~st, "p_p"])
    assert t.loc[~st, ["spilling_at_issue", "spill_hours_24h", "spill_days_7d"]].isna().all().all()
    assert (pd.to_datetime(t["radar_newest_modified"], utc=True) <= pd.to_datetime(t["build_at"], utc=True)).all()
    assert (pd.to_datetime(t["build_at"], utc=True) <= pd.to_datetime(t["issued_at"], utc=True)).all()
    assert (pd.to_datetime(t["rain_issued_at"], utc=True) < pd.to_datetime(t["issued_at"], utc=True)).all()
    # The stop rule.
    sr.clear_cache()
    assert sr.log_shadow(pd.Timestamp("2027-09-01 06:00", tz=TZ), ov, days[2], p_raw[:, 2], p_raw[:, 2], p_raw[:, 2],
                         out, rain_at, "spill=x", path=tmp_path / "late.duckdb") == 0


# ------------------------------------------------------------------ nothing published changes
def _point(tmp_path, monkeypatch):
    """forecast_point at a fixed 12:40 on two Yorkshire overflows and one United Utilities one, with fixed rain and a
    stand-in production model. Returns run(on) -> (the result, rain requests)."""
    from dipcast.model import forecast
    from dipcast.model.transport import PinLocation, clear_time, live_now_risk
    from dipcast import shadow_combined as sc, shadow_regional as sreg

    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "t.duckdb")
    now = NOW
    ov = pd.DataFrame({
        "site_id": ["A1", "B2", "U3"], "company": ["Yorkshire Water", "Yorkshire Water", "United Utilities"],
        "site_name": ["Weir CSO", "Burley CSO", "Mill CSO"], "receiving_watercourse": "River Wharfe",
        "lat": [53.93, 53.91, 53.95], "lon": [-1.82, -1.75, -1.90], "status": [1, 0, 0], "has_live": True,
        "data_state": "live", "feed_updated_at": now, "latest_event_start": [now - pd.Timedelta(hours=2), pd.NaT, pd.NaT],
        "latest_event_end": pd.NaT, "lta_spills": [200.0, 120.0, 80.0], "spill_hours": 100.0, "edm_operational_pct": 95.0,
        "snap_confidence": "high", "distance_m": [6000.0, 9000.0, 12000.0], "lake_distance_m": 0.0,
        "travel_h": [3.3, 5.0, 6.7], "weight": [0.8, 0.6, 0.4]})
    calls = []

    def rain(cells, ensemble=False):
        calls.append(len(cells))
        return _rain(cells, mm=0.4)

    class Model:
        trained_on = "test"

        def predict(self, sd):
            return np.where(sd["site_id"] == "A1", 0.55, 0.33)

    monkeypatch.setattr(forecast, "_now", lambda: NOW.tz_convert(TZ))
    monkeypatch.setattr(forecast, "_net", lambda: None)
    monkeypatch.setattr(forecast, "_overflows", lambda: ov)
    monkeypatch.setattr(forecast, "_model", lambda: Model())
    monkeypatch.setattr(forecast, "_lead_calibration", dict)
    monkeypatch.setattr(forecast, "locate_pin", lambda *a, **k: PinLocation(mode="river", x=0.0, y=0.0, snap=None,
                                                                             watercourse="River Wharfe"))
    monkeypatch.setattr(forecast, "upstream_overflows", lambda *a, **k: ov.copy())
    monkeypatch.setattr(forecast, "fetch_forecast", rain)
    monkeypatch.setattr(forecast.ecoli, "load", lambda: None)
    monkeypatch.setattr(forecast, "live_now_risk", live_now_risk)
    monkeypatch.setattr(forecast, "clear_time", clear_time)
    monkeypatch.setattr(ls, "candidates", dict)             # the other shadows stay off here
    monkeypatch.setattr(sreg, "v2_model", lambda: None)
    monkeypatch.setattr(sc, "parts", lambda: None)
    table = _status(pd.DataFrame({"site_id": ["A1", "B2", "U3", "X"]}))
    monkeypatch.setattr(ls, "_status_for", lambda d: table)
    monkeypatch.setattr(sr, "merged_poll_events", lambda: pd.DataFrame({"site_id": [], "start": [], "end": []}))

    def run(on):
        monkeypatch.setattr(config, "RADAR_SHADOW", on)
        sr.clear_cache()
        if on:
            from dipcast.ingest.rainfall import cells_for_sites
            cells = cells_for_sites(ov["lat"], ov["lon"])
            sr._build["radar"] = _radar(cells, radar_live.window_start(NOW), NOW.floor("h"), mm=3.0)
        calls.clear()
        return forecast.forecast_point(53.92, -1.70, days_ahead=4, gauge=False, log_to_store=True), len(calls)

    return run


def _tables(db):
    con = duckdb.connect(str(db))
    try:
        return con.execute("SHOW TABLES").df()["name"].tolist(), con
    except Exception:
        con.close()
        raise


def test_the_published_forecast_and_the_rain_requests_do_not_change(tmp_path, monkeypatch):
    run = _point(tmp_path, monkeypatch)
    off, n_off = run(False)
    db = tmp_path / "t.duckdb"
    names, con = _tables(db)
    before = con.execute("SELECT * FROM forecast_overflows ORDER BY site_id, target_day").df()
    con.close()
    assert sr.TABLE not in names
    on, n_on = run(True)
    assert n_on == n_off                       # the shadow asks for no rain of its own
    assert on == off                           # and changes nothing the page or the API gets
    names, con = _tables(db)
    try:
        after = con.execute("SELECT * FROM forecast_overflows ORDER BY site_id, target_day").df()
        t = con.execute(f"SELECT * FROM {sr.TABLE} ORDER BY site_id").df()
    finally:
        con.close()
    assert len(after) == 2 * len(before)
    pd.testing.assert_frame_equal(after.iloc[::2].reset_index(drop=True), before)
    assert len(t) == 3 and (t["radar_state"] == "ok").all() and t["p_candidate"].notna().all()
    assert t.loc[t["site_id"] == "A1", "p_raw"].tolist() == pytest.approx([0.55])
    assert (t["p_candidate"] != t["p_reference"]).all()      # radar at 3 mm an hour against 0.4 forecast


def test_a_failing_shadow_never_fails_the_forecast(tmp_path, monkeypatch):
    run = _point(tmp_path, monkeypatch)
    off, _ = run(False)

    def broken(*a, **k):
        raise RuntimeError("radar shadow broken")
    monkeypatch.setattr(sr, "shadow", broken)
    on, _ = run(True)
    assert on == off
    names, con = _tables(tmp_path / "t.duckdb")
    con.close()
    assert sr.TABLE not in names


def test_the_pre_read_check_passes_logged_rows_and_catches_a_bad_one(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from radar_shadow import check as chk
    ov, days, cells, rain, p_raw, avail, sd, table, events = _real_case()
    radar = _radar(cells, radar_live.window_start(NOW), NOW.floor("h"), mm=1.0)
    out = sr.shadow(sd, ov, days, 2, NOW, rain, radar=radar, frozen=sr.models(), status_table=table, events=events)
    from dipcast.shadow_combined import rain_issue_times
    db = tmp_path / "state.duckdb"
    sr.log_shadow(NOW, ov, days[2], p_raw[:, 2], p_raw[:, 2], p_raw[:, 2], out, rain_issue_times(rain, ov), "v", path=db)
    assert chk.main(str(db)) == 0
    con = duckdb.connect(str(db))
    t = con.execute(f"SELECT * FROM {sr.TABLE}").df()
    con.close()
    assert chk.check(t) == []
    bad = t.copy()
    bad.loc[0, "p_candidate"] = 0.999
    bad.loc[1, "issue_hour"] = 9
    found = chk.check(bad)
    assert any("pair names" in e for e in found) and any("issue_hour" in e for e in found)
