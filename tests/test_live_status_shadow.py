"""The live-status shadow (model/live_status.py, docs/LIVE-STATUS-SHADOW-TEST-2026-10.md): the three status
inputs from the poller's files, when a status is stale or missing and the overflow falls back to the production
forecast, what the forecast log keeps, and that the published forecast and the rain requests do not change.
No test here touches the network."""

from datetime import date

import duckdb
import numpy as np
import pandas as pd
import pytest

from dipcast import config
from dipcast.model import live_status as ls

DAY = date(2026, 10, 20)   # the issue day; the window is 13-19 Oct, all summer time
UTC = "UTC"


def _local(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="Europe/London")


def _cov(site: str, readings: list[str]) -> pd.DataFrame:
    """live_coverage.parquet rows for `site`, with a current reading in the half-hour slot of each local time."""
    rows = {}
    for r in readings:
        t = _local(r)
        d = t.date()
        rows[d] = rows.get(d, 0) | (1 << (t.hour * 2 + t.minute // 30))
    return pd.DataFrame({"site_id": site, "day": list(rows), "n_known": 1, "n_unknown": 0, "n_stale": 0,
                         "slots": list(rows.values())})


def _every(hours: float, first: str = "2026-10-12 00:10", last: str = "2026-10-20 09:10") -> list[str]:
    return [str(t.tz_localize(None)) for t in pd.date_range(_local(first), _local(last), freq=f"{int(hours * 60)}min")]


def _hist(rows: list[tuple]) -> pd.DataFrame:
    """live_history.parquet rows: (site, status, event start, event end, fetched), local times or None."""
    t = lambda s: pd.NaT if s is None else _local(s).tz_convert(UTC)
    return pd.DataFrame([{"site_id": s, "company": "Yorkshire Water", "status": st, "status_start": t(a),
                          "latest_event_start": t(a), "latest_event_end": t(b), "fetched_at": t(f)}
                         for s, st, a, b, f in rows])


# ------------------------------------------------------------------ the inputs
def test_the_inputs_come_from_the_polls_by_the_labels_own_rule():
    h = _hist([
        # A: two overlapping sightings of one spill across midnight 18/19 Oct, then a short one on the 19th.
        ("A", 1, "2026-10-18 22:00", None, "2026-10-18 23:00"),
        ("A", 0, "2026-10-18 22:00", "2026-10-19 03:00", "2026-10-19 06:00"),
        ("A", 0, "2026-10-19 10:00", "2026-10-19 10:30", "2026-10-19 12:00"),
        # A spill on the 12th is before the window, one on the 13th inside it.
        ("A", 0, "2026-10-12 10:00", "2026-10-12 11:00", "2026-10-12 12:00"),
        ("A", 0, "2026-10-13 10:00", "2026-10-13 11:00", "2026-10-13 12:00"),
        # B: discharging since the 17th and still running at the last poll, 08:00 today.
        ("B", 1, "2026-10-17 20:00", None, "2026-10-20 08:00"),
        # C: today only, so nothing in the window.
        ("C", 0, "2026-10-20 01:00", "2026-10-20 02:00", "2026-10-20 03:00"),
    ])
    cov = pd.concat([_cov(s, _every(3)) for s in "ABC"])
    t = ls.status_table(DAY, h, cov)
    # A: 13th, 18th and 19th are spill-days; on the 19th it spilled 00:00-03:00 and 10:00-10:30.
    assert t.loc["A", "spill_days_7d"] == 3 and t.loc["A", "spill_hours_24h"] == pytest.approx(3.5)
    # B: 17th, 18th, 19th; all 24 hours of the 19th, and no more however long it ran.
    assert t.loc["B", "spill_days_7d"] == 3 and t.loc["B", "spill_hours_24h"] == 24.0
    assert t.loc["C", "spill_days_7d"] == 0 and t.loc["C", "spill_hours_24h"] == 0.0
    assert (t["window_gap_h"] == 3.0).all()


def _ov(states=("live",), status=(0,), sites=("A",)) -> pd.DataFrame:
    return pd.DataFrame({"site_id": list(sites), "status": list(status), "data_state": list(states)})


def _known(readings, now="2026-10-20 09:20", state="live", status=0) -> bool:
    t = ls.status_table(DAY, _hist([]), _cov("A", readings))
    return bool(ls.status_known(_ov((state,), (status,)), _local(now), t)["status_known"].iloc[0])


def test_a_status_watched_at_the_pollers_cadence_is_known():
    assert _known(_every(7.5))                     # the longest gap between polls since 28 Sep was 7.71 h
    assert _known(_every(8))                       # 8 h exactly: the limit, MAX_GAP_H
    out = ls.status_known(_ov(status=(1,)), _local("2026-10-20 09:20"), ls.status_table(DAY, _hist([]), _cov("A", _every(3))))
    assert out.iloc[0][ls.STATUS].tolist() == [1.0, 0.0, 0.0]


def test_a_stale_or_missing_status_is_not_known():
    assert not _known(_every(8.5))                                        # a gap over 8 h in the window
    gap = [r for r in _every(2) if not ("2026-10-15 06:00" <= r <= "2026-10-15 16:00")]
    assert not _known(gap)                                                # one 10-hour hole, 15 Oct
    assert not _known(_every(2), now="2026-10-20 18:00")                  # last reading 09:10, 8.8 h before issue
    assert not _known(_every(2, first="2026-10-13 06:10"))                # first reading inside the window: its start unwatched
    for state in ("stale", "offline", "no_feed"):
        assert not _known(_every(2), state=state)                         # no current status at the poll
    # An overflow the poller never saw has no row: not known.
    t = ls.status_table(DAY, _hist([]), _cov("A", _every(2)))
    out = ls.status_known(_ov(sites=("Z",)), _local("2026-10-20 09:20"), t)
    assert not out["status_known"].iloc[0] and out[ls.STATUS].isna().all(axis=None)


def test_a_hole_before_the_window_does_not_count():
    early = [r for r in _every(2) if not ("2026-10-12 02:00" <= r <= "2026-10-12 18:00")]
    assert _known(early)


# ------------------------------------------------------------------ the fallback
class _ByStatus:
    """A candidate whose chance is 0.9 for an overflow spilling at issue, 0.05 otherwise."""

    def predict(self, df):
        return np.where(df["spilling_at_issue"].fillna(0).to_numpy() == 1, 0.9, 0.05)


def _frame(sites, days):
    return pd.DataFrame([{"site_id": s, "day": d, "ok": True, **{f: 0.0 for f in ls.ALL_FEATURES}}
                         for s in sites for d in days])


def test_unknown_overflows_fall_back_to_the_production_forecast(monkeypatch):
    days = pd.date_range("2026-10-18", periods=7, freq="D", tz="Europe/London")   # two past days, then leads 0-4
    ov = pd.DataFrame({"site_id": ["A", "B", "C"], "status": [1, 0, 1], "data_state": ["live", "live", "stale"]})
    table = ls.status_table(DAY, _hist([]), pd.concat([_cov(s, _every(2)) for s in "ABC"]))
    monkeypatch.setattr(ls, "candidates", lambda: {k: _ByStatus() for k in ls.LEADS})
    monkeypatch.setattr(ls, "_status_for", lambda d: table)
    p_cal = np.full((3, 7), 0.2)
    sd = _frame("ABC", days)
    sd.loc[(sd["site_id"] == "B") & (sd["day"] == days[3]), "ok"] = False   # no rain for B at lead 1
    got = ls.shadow_forecast(sd, ov, days, 2, _local("2026-10-20 09:20"), p_cal)
    assert got["known"].tolist() == [True, True, False]
    assert np.allclose(got["p"][0], [0.2, 0.2, 0.9, 0.9, 0.9, 0.9, 0.9])     # past days stay production's
    assert np.allclose(got["p"][1], [0.2, 0.2, 0.05, 0.2, 0.05, 0.05, 0.05])  # no rain: production's (NaN there in a build)
    assert np.allclose(got["p"][2], 0.2)                                      # stale: production's throughout
    assert np.isnan(got["inputs"][2]).all() and got["inputs"][0].tolist() == [1.0, 0.0, 0.0]


def test_without_the_candidates_the_shadow_is_off(monkeypatch, tmp_path):
    monkeypatch.setattr(ls, "CANDIDATE_DIR", tmp_path)
    ls.candidates.cache_clear()
    try:
        assert ls.candidates() == {}
        assert ls.shadow_forecast(pd.DataFrame(), pd.DataFrame(), pd.DatetimeIndex([]), 0, _local("2026-10-20"), np.zeros((0, 0))) is None
    finally:
        ls.candidates.cache_clear()


def test_the_candidates_are_the_ones_pr_254_scored():
    ls.candidates.cache_clear()
    models = ls.candidates()
    assert sorted(models) == [0, 1, 2, 3, 4]
    assert all(m.features[-3:] == ls.STATUS for m in models.values())


# ------------------------------------------------------------------ the log
def test_the_log_keeps_the_shadow_beside_the_forecast(tmp_path, monkeypatch):
    from dipcast import forecast_log as fl
    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "t.duckdb")
    issued = _local("2026-10-20 07:00")
    days = pd.date_range("2026-10-20", periods=2, freq="D", tz="Europe/London")
    ov = pd.DataFrame({"site_id": ["A", "B"], "has_live": [True, True], "weight": [0.5, 0.1], "travel_h": [3.5, 1.0]})
    p = np.full((2, 2), 0.2)
    shadow = {"p": np.array([[0.7, np.nan], [0.2, 0.2]]), "known": np.array([True, False]),
              "inputs": np.array([[1.0, 2.5, 3.0], [np.nan] * 3])}
    fl.log_forecast(issued, 54.0, -2.0, "river", "R", 0.0, days, np.array([0.1, 0.1]), ov, p, p, shadow=shadow)
    fl.log_forecast(issued, 54.1, -2.0, "river", "R", 0.0, days, np.array([0.1, 0.1]), ov, p, p)
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    got = con.execute("SELECT lat, site_id, lead, p_cal, p_status, status_known, spilling_at_issue, spill_hours_24h, spill_days_7d "
                      "FROM forecast_overflows ORDER BY lat, site_id, lead").fetchall()
    assert got[0][1:] == ("A", 0, 0.2, 0.7, True, 1.0, 2.5, 3.0)
    assert got[1][4] is None                                  # NaN (no rain) logged as NULL
    assert got[2][1:] == ("B", 0, 0.2, 0.2, False, None, None, None)
    assert all(r[4:] == (None,) * 5 for r in got if r[0] == 54.1)


# ------------------------------------------------------------------ nothing published changes
def test_the_published_forecast_and_the_rain_requests_do_not_change(tmp_path, monkeypatch):
    from dipcast.model import forecast
    from dipcast.model.transport import PinLocation, clear_time, live_now_risk

    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "t.duckdb")
    now = pd.Timestamp.now(tz="UTC")
    ov = pd.DataFrame({
        "site_id": ["A1", "B2"], "company": "Yorkshire Water", "site_name": ["Weir CSO", "Burley CSO"],
        "receiving_watercourse": "River Wharfe", "lat": [53.93, 53.91], "lon": [-1.82, -1.75],
        "status": [1, 0], "has_live": True, "latest_event_start": [now - pd.Timedelta(hours=2), pd.NaT],
        "latest_event_end": pd.NaT, "lta_spills": [200.0, 120.0], "spill_hours": 100.0, "edm_operational_pct": 95.0,
        "snap_confidence": "high", "distance_m": [6000.0, 9000.0], "lake_distance_m": 0.0, "travel_h": [3.3, 5.0],
        "weight": [0.8, 0.6]})
    calls = []

    def rain(cells, ensemble=False):
        calls.append(len(cells))
        t = pd.date_range(now.floor("D") - pd.Timedelta(days=40), periods=24 * 50, freq="h")
        return pd.concat([pd.DataFrame({"cell_lat": a, "cell_lon": b, "time": t, "precip_mm": 0.4}) for a, b in cells],
                         ignore_index=True)

    class Model:
        trained_on = "test"

        def predict(self, sd):
            return np.where(sd["site_id"] == "A1", 0.55, 0.33)

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
    readings = [str(t.tz_convert("Europe/London").tz_localize(None))
                for t in pd.date_range(now - pd.Timedelta(days=9), now, freq="2h")]
    table = ls.status_table(now.tz_convert("Europe/London").date(), _hist([]),
                            pd.concat([_cov(s, readings) for s in ("A1", "B2")]))
    monkeypatch.setattr(ls, "_status_for", lambda d: table)

    def run(models):
        monkeypatch.setattr(ls, "candidates", lambda: models)
        calls.clear()
        out = forecast.forecast_point(53.92, -1.70, days_ahead=4, gauge=False, log_to_store=True)
        out["query"].pop("issued_at")
        return out, len(calls)

    off, n_off = run({})
    on, n_on = run({k: _ByStatus() for k in ls.LEADS})
    assert n_on == n_off                     # the shadow asks for no rain of its own
    assert on == off                         # and changes nothing the page or the API gets
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    rows = con.execute("SELECT site_id, lead, p_cal, p_status, status_known FROM forecast_overflows "
                       "WHERE p_status IS NOT NULL ORDER BY site_id, lead").fetchall()
    assert len(rows) == 10 and all(r[4] for r in rows)
    assert [r[3] for r in rows] == pytest.approx([0.9] * 5 + [0.05] * 5)   # A1 spilling at issue, B2 not
    assert [r[2] for r in rows] == pytest.approx([0.55] * 5 + [0.33] * 5)  # production unchanged beside it


# ------------------------------------------------------------------ the check (scripts/live_status_shadow_check.py)
def _check_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("live_status_shadow_check", config.ROOT / "scripts" / "live_status_shadow_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rows(better: bool, n_days: int = 28, per_day: int = 120, seed: int = 1) -> pd.DataFrame:
    """Scored rows for the window, joined to the log: two companies, every lead, a quarter falling back."""
    rng = np.random.default_rng(seed)
    out = []
    for d in pd.date_range("2026-10-26", periods=n_days, freq="D"):
        for k in range(5):
            risk = rng.choice([0.02, 0.5], size=per_day, p=[0.85, 0.15])   # each row's true chance
            y = (rng.random(per_day) < risk).astype(int)
            prod = np.clip(0.092 + 0.02 * rng.standard_normal(per_day), 0.01, 0.99)   # right on average only
            sharp = risk if better else 0.52 - risk                                    # calibrated, or backwards
            known = rng.random(per_day) < 0.75
            out.append(pd.DataFrame({
                "overflow_id": [f"S{i}" for i in range(per_day)], "company": np.where(np.arange(per_day) % 2, "Yorkshire Water", "Anglian Water"),
                "day": d.strftime("%Y-%m-%d"), "lead": k, "forecast_calibrated": prod.round(4), "observed": y,
                "p_db": prod, "p_status": np.where(known, sharp, prod), "status_known": known,
                "spilling_at_issue": np.where(known, 0.0, np.nan), "spill_hours_24h": np.where(known, 0.0, np.nan),
                "spill_days_7d": np.where(known, 0.0, np.nan)}))
    return pd.concat(out, ignore_index=True)


def test_the_check_passes_a_better_shadow_and_fails_a_worse_one():
    chk = _check_module()
    good = chk.check(_rows(better=True), n_boot=300)
    assert good["sane"] and good["enough_data"] and good["weeks"] == 4 and good["days"] == 28   # 26 Oct 2026 is a Monday: four ISO weeks
    assert good["verdict"] == {k: "passes" for k in range(5)}
    bad = chk.check(_rows(better=False), n_boot=300)
    assert bad["verdict"] == {k: "fails" for k in range(5)}
    c = bad["leads"][2]["conditions"]
    assert not c["1_gain"] and not c["2_no_company_clearly_worse"] and not c["4_dry_start"]


def test_the_check_stops_when_the_join_or_the_fallback_is_wrong():
    chk = _check_module()
    r = _rows(better=True, n_days=3)
    r.loc[r.index[:5], "p_db"] += 0.3                      # the log's production figure is not the published one
    assert chk.check(r, n_boot=50)["verdict"].startswith("stopped")
    r = _rows(better=True, n_days=3)
    fb = r.index[~r["status_known"]][:3]
    r.loc[fb, "p_status"] += 0.01                          # a fallback row that is not production's forecast
    assert chk.check(r, n_boot=50)["verdict"].startswith("stopped")
    r = _rows(better=True, n_days=3)
    assert chk.check(r, n_boot=50)["verdict"].startswith("not enough data")
