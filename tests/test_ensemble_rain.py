"""Ensemble rain for the listed spots (review task D4, docs/ENSEMBLE-RAIN-TEST-2026-11.md): the fetch and its
rules (one call a cell, a 12-hour floor, a daily cap, spare calls only), each member spliced onto the single
forecast's past, the spill model run per member, and the members in the forecast log. No test touches the
network: rainfall._http_get is replaced by an httpx.MockTransport client."""

import time

import duckdb
import httpx
import numpy as np
import pandas as pd
import pytest

from dipcast import config
from dipcast.ingest import rainfall
from dipcast.model import features
from dipcast.model import forecast as fc


class FakeEnsemble:
    """Open-Meteo's ensemble API: every location answered with three members from 00:00 UTC today for
    `hours` hours, then nulls to six days; or a `status` error. `asked` holds each request's params."""

    def __init__(self, hours=144, status=None):
        self.hours, self.status, self.asked = hours, status, []
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        q = dict(request.url.params)
        self.asked.append(q)
        if self.status:
            return httpx.Response(self.status)
        n = len(q["latitude"].split(","))
        t = pd.date_range(pd.Timestamp.now(tz="UTC").normalize(), periods=144, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()
        val = lambda v: [v if i < self.hours else None for i in range(144)]
        body = [{"hourly": {"time": t, "precipitation": val(0.1), "precipitation_member01": val(0.5),
                            "precipitation_member02": val(1.0)}} for _ in range(n)]
        return httpx.Response(200, json=body if n > 1 else body[0])

    def get(self, url, params, timeout):
        return self.client.get(url, params=params, timeout=timeout)


@pytest.fixture
def om(monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "_sleep", lambda s: None)
    rainfall.reset_fallbacks()
    rainfall.reset_requests()

    def install(**kw):
        f = FakeEnsemble(**kw)
        monkeypatch.setattr(rainfall, "_http_get", f.get)
        return f

    yield install
    rainfall.reset_fallbacks()
    rainfall.reset_requests()


def _cells(n):
    return [(round(50.0 + 0.1 * i, 3), -2.0) for i in range(n)]


def _noon_utc():
    return pd.Timestamp.now(tz="UTC").normalize().timestamp() + 12 * 3600


# ------------------------------------------------------------------ the cost and the rules
def test_an_ensemble_cell_is_one_call_and_the_rules_fit_the_ration():
    # Three members of one variable over six days: max(1, 0.3, 0.3 x 6/14) = 1 a cell (Open-Meteo's own rule).
    assert rainfall.ensemble_weight(332) == 332 and rainfall.ensemble_weight(50) == 50
    assert rainfall.DAY_HOURS_NEEDED == features.MIN_HOURS_PER_DAY
    # PLANNED_DAY_CALLS is the others' most at a build every 30 minutes (test_open_meteo_ration's sum).
    assert rainfall.PLANNED_DAY_CALLS >= 8749 and rainfall.PLANNED_DAY_CALLS < rainfall.DAILY_CALLS
    assert 3 * 332 <= rainfall.ENSEMBLE_DAILY_CALLS < 4 * 332


def test_spare_calls_are_what_the_others_will_not_need_today(om):
    midnight = pd.Timestamp.now(tz="UTC").normalize().timestamp()
    assert not rainfall.spare_for(332, now=midnight + 60)          # the whole day's planned use still to come
    rainfall.spend(2000, "spots", now=midnight + 12 * 3600)
    assert rainfall.spare_for(332, now=midnight + 12 * 3600)       # 6,668 left after it; 4,375 still planned
    rainfall.spend(2375, "spots", now=midnight + 12 * 3600)        # the others at the planned pace
    assert not rainfall.spare_for(332, now=midnight + 12 * 3600)


def test_the_members_reach_far_enough_into_the_fifth_day():
    now = pd.Timestamp("2026-10-22 00:30", tz="Europe/London")   # the clocks go back on the 25th
    assert rainfall.ensemble_until(5, now) == pd.Timestamp("2026-10-26 19:00", tz="UTC")
    assert rainfall.ensemble_until(5, pd.Timestamp("2026-10-18 14:30", tz="Europe/London")) == pd.Timestamp("2026-10-22 18:00", tz="UTC")


# ------------------------------------------------------------------ the fetch
def test_fetch_asks_for_the_uk_ensemble_and_books_it(om, monkeypatch):
    fake = om()
    monkeypatch.setattr(rainfall, "spare_for", lambda w, now=None: True)
    cells = _cells(60)
    df = rainfall.fetch_forecast(cells, ensemble=True)
    assert len(fake.asked) == 2 and len(fake.asked[0]["latitude"].split(",")) == 50
    q = fake.asked[0]
    assert (q["models"], q["hourly"], q["past_days"], q["forecast_days"], q["timezone"]) == (
        config.ENSEMBLE_MODEL, "precipitation", "0", "6", "UTC")
    assert set(df["member"]) == {0, 1, 2} and df[["cell_lat", "cell_lon"]].drop_duplicates().shape[0] == 60
    assert rainfall.calls_today()["by"] == {"ensemble": 60}
    assert rainfall.ensemble_summary() == {"fetched": 60}
    assert rainfall.requests_made() == {"total": 2, "by_host": {"ensemble-api.open-meteo.com": 2}}
    # Each spot's forecast asks again: the cache answers, with no request.
    again = rainfall.fetch_forecast(cells[:3], ensemble=True)
    assert len(fake.asked) == 2 and len(again) == 3 * 3 * 144
    # The next build: under 12 hours old and reaching the fifth day, so still no request.
    rainfall.reset_fallbacks()
    rainfall.fetch_forecast(cells, ensemble=True)
    assert len(fake.asked) == 2


def test_members_that_stop_short_of_the_fifth_day_are_asked_for_again_next_build(om, monkeypatch):
    fake = om(hours=60)   # 60 hours: well short of the fifth local day
    monkeypatch.setattr(rainfall, "spare_for", lambda w, now=None: True)
    rainfall.fetch_forecast(_cells(2), ensemble=True)
    rainfall.fetch_forecast(_cells(2), ensemble=True)      # the same build: not again
    assert len(fake.asked) == 1
    rainfall.reset_fallbacks()                              # the next build
    rainfall.fetch_forecast(_cells(2), ensemble=True)
    assert len(fake.asked) == 2


def test_no_spare_calls_means_no_request_and_older_members(om, monkeypatch):
    fake = om()
    cells = _cells(3)
    old = rainfall._ensemble_frame({"hourly": {"time": ["2026-10-18T00:00"], "precipitation": [1.0],
                                               "precipitation_member01": [2.0], "precipitation_member02": [3.0]}}, *cells[0])
    p = rainfall.CACHE / f"ensemble_{rainfall.cell_key(*cells[0])}.parquet"
    old.assign(issued_at=pd.Timestamp.now(tz="UTC")).to_parquet(p)
    t = time.time() - 14 * 3600   # past the 12-hour floor, inside the 24 hours a stale copy may serve
    import os
    os.utime(p, (t, t))
    midnight = pd.Timestamp.now(tz="UTC").normalize().timestamp()
    rainfall.spend(rainfall.DAILY_CALLS - 100, "spots", now=midnight + 3600)   # nothing spare today
    # The real rule, read at noon: late in the UTC day the planned use left can fall under 100, and then a few calls
    # are rightly spare, so the wall clock would make this test pass or fail by the hour it runs.
    spare_for = rainfall.spare_for
    monkeypatch.setattr(rainfall, "spare_for", lambda w, now=None: spare_for(w, now=midnight + 12 * 3600))
    df = rainfall.fetch_forecast(cells, ensemble=True)
    assert fake.asked == []
    assert set(zip(df["cell_lat"], df["cell_lon"], strict=True)) == {cells[0]}
    assert rainfall.ensemble_summary() == {"not_fetched": 3, "from_older_cache": 1}
    assert "ensemble" not in rainfall.calls_today()["by"]


def test_the_days_ensemble_calls_are_capped(om, monkeypatch):
    fake = om()
    monkeypatch.setattr(rainfall, "spare_for", lambda w, now=None: True)
    rainfall.spend(rainfall.ENSEMBLE_DAILY_CALLS - 10, "ensemble")
    rainfall.fetch_forecast(_cells(20), ensemble=True)
    assert fake.asked == []


def test_a_failed_request_stops_the_ensemble_for_the_build_and_never_raises(om, monkeypatch):
    fake = om(status=503)
    monkeypatch.setattr(rainfall, "spare_for", lambda w, now=None: True)
    df = rainfall.fetch_forecast(_cells(120), ensemble=True)
    assert df.empty
    assert len(fake.asked) == 2                     # one chunk, two attempts; the other two chunks not asked for
    assert rainfall.requests_made()["total"] == 2   # retries count as requests
    s = rainfall.ensemble_summary()
    assert s["not_fetched"] == 120 and s["errors"]


# ------------------------------------------------------------------ the members through the spill model
def _rain(cell, issued, hours=72, mm=0.2):
    t = pd.date_range("2026-10-17", periods=hours, freq="h", tz="UTC")
    return pd.DataFrame({"cell_lat": cell[0], "cell_lon": cell[1], "time": t, "precip_mm": mm, "issued_at": issued})


def _ens(cell, reach_h, values=(0.0, 1.0, 2.0)):
    t = pd.date_range("2026-10-18", periods=48, freq="h", tz="UTC")
    return pd.concat([pd.DataFrame({"cell_lat": cell[0], "cell_lon": cell[1], "time": t, "member": m,
                                    "precip_mm": [v if i < reach_h else np.nan for i in range(48)],
                                    "issued_at": pd.Timestamp("2026-10-18 06:00", tz="UTC")})
                      for m, v in enumerate(values)], ignore_index=True)


def test_each_member_takes_over_from_the_hour_the_single_forecast_was_issued():
    cell = (54.4, -2.9)
    rain = _rain(cell, pd.Timestamp("2026-10-18 10:40", tz="UTC"))
    out = fc.member_rain(rain, _ens(cell, reach_h=30))
    assert len(out) == 3
    m2 = out[2].set_index("time")["precip_mm"]
    assert m2[pd.Timestamp("2026-10-18 09:00", tz="UTC")] == 0.2     # before 10:00: the single forecast's
    assert m2[pd.Timestamp("2026-10-18 10:00", tz="UTC")] == 2.0     # from 10:00: the member's
    assert np.isnan(m2[pd.Timestamp("2026-10-19 07:00", tz="UTC")])  # past the member's reach: no rain, not dry
    assert np.isnan(m2[pd.Timestamp("2026-10-19 20:00", tz="UTC")])  # beyond the members altogether
    assert m2[pd.Timestamp("2026-10-17 05:00", tz="UTC")] == 0.2     # the past is the same for every member
    assert fc.member_rain(rain, _ens(cell, 30).iloc[0:0]) == []


def test_ensemble_members_runs_the_model_per_member_and_keeps_the_missing_rule(monkeypatch):
    cell = (54.4, -2.9)
    days = pd.date_range("2026-10-17", periods=3, freq="D", tz="Europe/London")
    ov = pd.DataFrame({"site_id": ["A", "B"], "lat": [54.4, 54.4], "lon": [-2.9, -2.9]})
    monkeypatch.setattr(fc, "fetch_forecast", lambda cells, ensemble=False: _ens(cell, reach_h=30))
    monkeypatch.setattr(fc, "_lead_calibration", dict)

    def fake_spill(ov_, days_, model, return_rain=False, rain=None):
        # Each day's chance is its rain over 50 mm, at most 0.9; no rain (NaN) is no figure.
        d = rain.assign(day=rain["time"].dt.tz_convert("Europe/London").dt.floor("D")).groupby("day")["precip_mm"]
        tot = d.sum(min_count=20).reindex(days)
        p = np.minimum(tot.to_numpy() / 50, 0.9)
        mat = np.tile(p, (len(ov_), 1))
        return mat, np.isfinite(mat), np.tile(tot.to_numpy(), (len(ov_), 1))

    monkeypatch.setattr(fc, "spill_probabilities", fake_spill)
    rain = _rain(cell, pd.Timestamp("2026-10-18 00:10", tz="UTC"))
    got = fc.ensemble_members(ov, days, None, rain, hist=1, weights=np.array([1.0, 0.5]), travel=np.zeros(2))
    assert got["members"] == 3 and got["p"].shape == (3, 2, 3) and got["risk"].shape == (3, 3)
    # 18 Oct (local) is 17 Oct 23:00 to 18 Oct 22:00 UTC: one hour of the single forecast, then 23 of the member's.
    assert got["rain"][:, 0, 1] == pytest.approx([0.2, 23 * 1.0 + 0.2, 23 * 2.0 + 0.2], abs=1e-9)
    assert got["risk"][2, 1] > got["risk"][1, 1] > got["risk"][0, 1]
    assert np.isnan(got["risk"][:, 2]).all()        # 19 Oct: the members stop at 06:00 UTC, so no band
    assert np.isnan(got["p"][:, :, 2]).all()
    assert got["issued_at"] == pd.Timestamp("2026-10-18 06:00", tz="UTC")


def test_the_log_keeps_the_members_and_an_old_table_takes_them(tmp_path, monkeypatch):
    from dipcast import forecast_log as fl
    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "t.duckdb")
    # A log as it was before 18 Oct 2026: the columns added since come by ALTER, and the inserts go by name.
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    con.execute("""CREATE TABLE forecast_overflows (issued_at TIMESTAMPTZ, issue_day DATE, lat DOUBLE, lon DOUBLE,
        site_id VARCHAR, has_live BOOLEAN, target_day DATE, lead INTEGER, p_raw DOUBLE, p_cal DOUBLE, weight DOUBLE)""")
    con.close()
    issued = pd.Timestamp("2026-10-18 07:00", tz="Europe/London")
    days = pd.date_range("2026-10-18", periods=2, freq="D", tz="Europe/London")
    ov = pd.DataFrame({"site_id": ["A", "B"], "has_live": [True, True], "weight": [0.5, 0.1], "travel_h": [3.5, 1.0]})
    p = np.full((2, 2), 0.2)
    members = {"p": np.array([[[0.1, 0.2], [0.3, np.nan]]] * 3), "rain": np.full((3, 2, 2), 4.0),
               "risk": np.array([[0.1, 0.2], [0.15, np.nan], [0.3, 0.4]]), "issued_at": pd.Timestamp("2026-10-18 05:00", tz="UTC")}
    fl.log_forecast(issued, 54.0, -2.0, "river", "R", 0.0, days, np.array([0.1, 0.1]), ov, p, p, members=members)
    fl.log_forecast(issued, 54.1, -2.0, "river", "R", 0.0, days, np.array([0.1, 0.1]), ov, p, p)
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    got = con.execute("SELECT lat, site_id, lead, p_cal_members, rain_members, travel_h FROM forecast_overflows "
                      "ORDER BY lat, site_id, lead").fetchall()
    assert got[0][:3] == (54.0, "A", 0) and got[0][3] == pytest.approx([0.1] * 3) and got[0][4] == pytest.approx([4.0] * 3)
    assert got[3][:3] == (54.0, "B", 1) and got[3][3] == [None, None, None]
    assert got[0][5] == 3.5
    assert all(r[3] is None and r[4] is None for r in got if r[0] == 54.1)
    pts = con.execute("SELECT lat, lead, risk_members, epoch_ms(ens_issued_at) FROM forecast_points ORDER BY lat, lead").fetchall()
    assert pts[0][2] == pytest.approx([0.1, 0.15, 0.3]) and pts[1][2][1] is None
    assert pts[0][3] == pd.Timestamp("2026-10-18 05:00", tz="UTC").value // 10**6
    assert pts[2][2] is None and pts[2][3] is None
