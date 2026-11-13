"""The combined-v1 shadow (src/dipcast/shadow_combined.py, docs/COMBINED-SHADOW-2026-11.md): the frozen formula, the
stale-status fallback, the off switch, inputs left alone, what it logs and when, real overflow rows through the seven
frozen models, and that the published forecast and the rain requests do not change. No test here touches the network."""

import ast
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from dipcast import config
from dipcast import shadow_combined as sc
from dipcast import shadow_regional as sr
from dipcast.model import live_status as ls
from dipcast.model.features import ALL_FEATURES

TZ = "Europe/London"
ROOT = Path(__file__).resolve().parents[1]
NOW = pd.Timestamp("2026-11-20 06:30", tz=TZ)      # before 08:00 local, so the forecast is one the read can use


class Fixed:
    def __init__(self, p):
        self.p = p

    def predict(self, df):
        return np.full(len(df), self.p)


def _models(v2=0.30, d2=0.20, cand=0.60) -> dict:
    return {"v2": Fixed(v2), "d2": Fixed(d2), "candidates": {k: Fixed(cand) for k in sc.LEADS}}


def _table(sites, read_at=NOW - pd.Timedelta(hours=1), gap=2.0) -> pd.DataFrame:
    """A status table (live_status.status_table's shape) with every site read an hour before NOW."""
    return pd.DataFrame({"spill_days_7d": 1.0, "spill_hours_24h": 2.5, "last_reading": read_at.tz_convert("UTC"),
                         "window_gap_h": gap}, index=pd.Index(list(sites), name="site_id"))


def _case():
    """Four overflows on a grid of one past day and leads 0 to 4: Anglian with a known status, Anglian with a stale
    one, United Utilities known, Welsh known. A1 has no rain at lead 2."""
    days = pd.date_range("2026-11-19", periods=6, freq="D", tz=TZ)
    ov = pd.DataFrame({"site_id": ["A1", "A2", "U1", "W1"],
                       "company": ["Anglian Water", "Anglian Water", "United Utilities", "Dwr Cymru Welsh Water"],
                       "status": [1, 0, 0, 1], "data_state": ["live", "stale", "live", "live"],
                       "lat": [52.0, 52.1, 54.0, 51.6], "lon": [0.1, 0.2, -2.7, -3.2]})
    rows = []
    for sid in ov["site_id"]:
        for d in days:
            # rain_d is itself a model input, so it is set after the others are blanked
            rows.append({"site_id": sid, "day": d, **{f: np.nan for f in ALL_FEATURES},
                         "rain_d": np.nan if (sid == "A1" and d == days[3]) else 1.0})
    sd = pd.DataFrame(rows)
    sd["ok"] = sd["rain_d"].notna()
    p_raw = np.full((4, 6), 0.10)
    p_raw[0, 3] = np.nan
    return days, ov, sd, p_raw


def _run(**kw):
    days, ov, sd, p_raw = _case()
    out = sc.combined(sd, ov, days, 1, NOW, p_raw, models=kw.pop("models", _models()),
                      status_table=kw.pop("status_table", _table(ov["site_id"])), **kw)
    return days, ov, sd, p_raw, out


# ------------------------------------------------------------------ the formula
def test_the_formula_is_the_backtests():
    """`combine`, `logit`, `sigmoid` and CLIP as the harness frozen at 4d66d7c7 defines them, run on the same numbers.
    The harness is not imported (it loads the whole backtest); its three functions are read from its source."""
    tree = ast.parse((ROOT / "scripts" / "combined_candidate_backtest_2026.py").read_text())
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in ("logit", "sigmoid", "combine"))
            or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "CLIP")]
    assert len(keep) == 4
    ns = {"np": np}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "harness", "exec"), ns)  # noqa: S102 - the repo's own code
    rng = np.random.default_rng(0)
    base, cand, d2 = (np.concatenate([rng.random(500), [0.0, 1.0, 1e-9]]) for _ in range(3))
    unknown = rng.random(503) < 0.3
    assert sc.CLIP == ns["CLIP"]
    assert np.array_equal(sc.combine(base, cand, d2, unknown), ns["combine"](base, cand, d2, unknown))


def test_uplift_where_the_status_is_known_and_the_base_alone_where_it_is_stale():
    days, ov, sd, p_raw, out = _run()
    up = 1 / (1 + np.exp(-(np.log(0.3 / 0.7) + np.log(0.6 / 0.4) - np.log(0.2 / 0.8))))   # v2 base, by hand
    uu = 1 / (1 + np.exp(-(np.log(0.1 / 0.9) + np.log(0.6 / 0.4) - np.log(0.2 / 0.8))))   # production base
    assert out["known"].tolist() == [True, False, True, True]
    assert out["v2"].tolist() == [True, True, False, False]
    # A1: known, v2 base: the uplift at leads 0 to 4 with rain; the past day keeps the base; no rain stays missing.
    assert out["p"][0, 0] == pytest.approx(0.30) and not out["uplift"][0, 0]
    assert out["p"][0, [1, 2, 4, 5]] == pytest.approx([up] * 4) and np.isnan(out["p"][0, 3])
    # A2: stale (the feed's data state): the fallback, regional-v1's chance alone, at every lead.
    assert out["p"][1] == pytest.approx([0.30] * 6) and not out["uplift"][1].any() and np.isnan(out["cand"][1]).all()
    assert np.isnan(out["inputs"][1]).all() and out["inputs"][0].tolist() == [1.0, 2.5, 1.0]
    # U1: United Utilities: production's raw chance is the base, and the frozen formula adds the uplift to it.
    assert out["base"][2] == pytest.approx([0.10] * 6) and out["p"][2, 1:] == pytest.approx([uu] * 5)
    # W1: not one of the nine: production's raw chance, no uplift, and not logged.
    assert out["p"][3] == pytest.approx([0.10] * 6) and not out["uplift"][3].any() and not out["english"][3]


def test_the_eight_hour_rule_decides_the_fallback():
    old = _table(["A1", "A2", "U1", "W1"], read_at=NOW - pd.Timedelta(hours=8, minutes=30))
    assert not _run(status_table=old)[4]["known"].any()            # last reading 8.5 h before issue: stale
    assert not _run(status_table=_table(["A1", "A2", "U1", "W1"], gap=9.0))[4]["known"].any()   # a 9 h hole in the week
    seen = _run(status_table=_table(["A1"]))[4]                    # the poller never saw the others
    assert seen["known"].tolist() == [True, False, False, False] and pd.isna(seen["read_at"][2])
    out = _run(status_table=old)[4]
    assert np.array_equal(out["p"], out["base"], equal_nan=True)   # every row the base alone


def test_inputs_are_not_altered():
    days, ov, sd, p_raw = _case()
    sd0, ov0, p0 = sd.copy(), ov.copy(), p_raw.copy()
    sc.combined(sd, ov, days, 1, NOW, p_raw, models=_models(), status_table=_table(ov["site_id"]))
    pd.testing.assert_frame_equal(sd, sd0)
    pd.testing.assert_frame_equal(ov, ov0)
    assert np.array_equal(p_raw, p0, equal_nan=True)


# ------------------------------------------------------------------ the off switch
def test_off_without_the_frozen_file(tmp_path, monkeypatch):
    days, ov, sd, p_raw = _case()
    try:
        monkeypatch.setattr(sc, "D2_FILE", tmp_path / "missing.pkl")
        sc.clear_cache()
        assert sc.parts() is None and sc.combined(sd, ov, days, 1, NOW, p_raw) is None
        (tmp_path / "other.pkl").write_bytes(b"another model")
        monkeypatch.setattr(sc, "D2_FILE", tmp_path / "other.pkl")
        sc.clear_cache()
        assert sc.parts() is None
    finally:
        sc.clear_cache()


def test_off_when_a_candidate_or_v2_is_not_the_frozen_one(tmp_path, monkeypatch):
    try:
        monkeypatch.setattr(ls, "CANDIDATE_DIR", tmp_path)
        sc.clear_cache()
        assert sc.parts() is None
        monkeypatch.undo()
        monkeypatch.setattr(sr, "v2_model", lambda: None)
        sc.clear_cache()
        assert sc.parts() is None
    finally:
        monkeypatch.undo()
        sc.clear_cache(); ls.candidates.cache_clear()


def test_the_committed_files_are_the_frozen_models():
    sc.clear_cache(); sr.clear_cache(); ls.candidates.cache_clear()
    got = sc.parts()
    assert got is not None and sorted(got["candidates"]) == [0, 1, 2, 3, 4]
    assert list(got["d2"].features) == list(ALL_FEATURES)
    assert all(sc.CANDIDATE_SHA256[k].startswith(ls.CANDIDATE_SHA[k]) for k in sc.LEADS)   # the same five files


# ------------------------------------------------------------------ the log
def _log(tmp_path, issued=NOW, **kw):
    days, ov, sd, p_raw, out = _run(**kw)
    db = tmp_path / "state.duckdb"
    n = sc.log_shadow(issued, 54.0, -2.0, days, ov, p_raw, p_raw * 0.5, p_raw * 0.25, out, "spill=abc", path=db)
    return n, db


def _read(db, sql=None):
    con = duckdb.connect(str(db))
    try:
        return con.execute(sql or f"SELECT * FROM {sc.TABLE} ORDER BY site_id, lead").df()
    finally:
        con.close()


def test_logs_the_nine_at_leads_0_to_4_in_its_own_table(tmp_path):
    n, db = _log(tmp_path, rain=pd.DataFrame({"cell_lat": [52.0], "cell_lon": [0.1], "time": [NOW],
                                              "issued_at": [NOW - pd.Timedelta(hours=3)]}))
    t = _read(db)
    assert n == 15 and len(t) == 15                      # three English overflows x leads 0-4; Wales and the past day not logged
    tables = _read(db, "SHOW TABLES")["name"].tolist()   # the state database's own tables are made empty on opening
    assert sc.TABLE in tables and sr.TABLE not in tables
    assert all(_read(db, f"SELECT count(*) AS n FROM {x}")["n"].iloc[0] == 0 for x in tables if x != sc.TABLE)
    assert tuple(t.columns) == sc.COLUMNS and t["lead"].tolist() == [0, 1, 2, 3, 4] * 3
    assert set(t["site_id"]) == {"A1", "A2", "U1"} and set(t["rule"]) == {"combined-v1"} and set(t["models"]) == {sc.MODELS}
    a = t[t["site_id"] == "A1"]
    assert a["applied"].tolist() == ["uplift", "uplift", "no_rain", "uplift", "uplift"]
    assert a["p_combined"].isna().tolist() == [False, False, True, False, False] and (a["route"] == "v2_offsets").all()
    assert a["status_known"].all() and a["spilling_at_issue"].eq(1.0).all() and a["p_candidate"].iloc[0] == pytest.approx(0.6)
    assert a["p_d2"].iloc[0] == pytest.approx(0.2) and a["p_base"].iloc[0] == pytest.approx(0.3)
    b = t[t["site_id"] == "A2"]                           # the stale one: the fallback, logged as such
    assert (b["applied"] == "fallback").all() and np.allclose(b["p_combined"], b["p_base"]) and not b["status_known"].any()
    assert b[["p_candidate", "spilling_at_issue", "spill_hours_24h", "spill_days_7d"]].isna().all(axis=None)
    assert b["p_d2"].notna().all()
    u = t[t["site_id"] == "U1"]
    assert (u["route"] == "production").all() and np.allclose(u["p_base"], u["p_raw"]) and (u["applied"] == "uplift").all()
    # the comparator on the same row: production raw, production after the lead map, and what was shown
    assert np.allclose(u["p_cal"], u["p_raw"] * 0.5) and np.allclose(u["p_shown"], u["p_raw"] * 0.25)
    # each input's own time beside the issue time, none after it
    issued = pd.to_datetime(t["issued_at"], utc=True)
    assert (issued == NOW.tz_convert("UTC")).all() and set(t["issue_day"].astype(str)) == {"2026-11-20"}
    assert (pd.to_datetime(t["status_read_at"], utc=True) == (NOW - pd.Timedelta(hours=1)).tz_convert("UTC")).all()
    assert pd.to_datetime(a["rain_issued_at"], utc=True).eq((NOW - pd.Timedelta(hours=3)).tz_convert("UTC")).all()
    assert u["rain_issued_at"].isna().all()               # no issue time for that cell: NULL, never a guess


def test_only_a_forecast_issued_by_eight_local_is_logged(tmp_path):
    assert sc.logs(pd.Timestamp("2026-11-20 08:00", tz=TZ)) and not sc.logs(pd.Timestamp("2026-11-20 08:00:01", tz=TZ))
    assert sc.logs(pd.Timestamp("2026-11-20 00:00", tz=TZ)) and not sc.logs(pd.Timestamp("2026-11-20 23:59", tz=TZ))
    assert sc.logs(pd.Timestamp("2026-11-20 07:30", tz="UTC"))            # 07:30 GMT
    assert not sc.logs(pd.Timestamp("2027-06-01 07:30", tz="UTC"))        # 08:30 BST: local time decides
    n, db = _log(tmp_path, issued=pd.Timestamp("2026-11-20 09:15", tz=TZ))
    assert n == 0 and not db.exists()


def test_the_stop_rule_ends_the_log(tmp_path):
    assert sc.LAST_ISSUE_DAY == date(2027, 1, 31)
    assert sc.logs(pd.Timestamp("2027-01-31 07:00", tz=TZ)) and not sc.logs(pd.Timestamp("2027-02-01 07:00", tz=TZ))


def test_the_pre_window_check_reads_the_table(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import combined_shadow_check as chk
    n, db = _log(tmp_path)
    rows = _read(db)
    assert chk.check(rows) == []
    # first issue day 20 Nov: the first target day with every lead logged is the 24th; 28 days; read two days after
    assert chk.window(rows)[1:] == ("2026-11-24", "2026-12-21", "2026-12-23")
    bad = rows.copy()
    bad.loc[bad["applied"] == "fallback", "p_combined"] = 0.99
    assert any("fallback row differs" in e for e in chk.check(bad))
    bad = rows.copy()
    bad.loc[bad["applied"] == "uplift", "p_combined"] += 0.01
    assert any("frozen formula" in e for e in chk.check(bad))
    bad = rows.copy()
    bad["status_read_at"] = bad["issued_at"] + pd.Timedelta(hours=1)
    assert any("read after the forecast" in e for e in chk.check(bad))
    bad = rows.copy()
    bad["issued_at"] = bad["issued_at"] + pd.Timedelta(hours=3)
    assert any("issued after 8:00" in e for e in chk.check(bad))
    bad = rows.copy()
    bad.loc[bad["company"] == "United Utilities", "route"] = "v2_offsets"
    assert any("routed" in e for e in chk.check(bad))


# ------------------------------------------------------------------ real overflow rows, the seven frozen models
def _real_overflows() -> pd.DataFrame:
    """Twelve real overflows from the committed annual returns (2025): three each at Anglian, Thames, Yorkshire and
    United Utilities, all with a v2 offset, with their own coordinates and covariates."""
    a = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    a = a[(a["year"] == 2025) & a["site_id"].notna() & a["lat"].notna() & a["lta_spills"].notna()]
    a = a[a["site_id"].isin(sr.v2_model().site_offset)].sort_values("site_id")
    pick = pd.concat([a[a["company"] == c].head(3) for c in ("Anglian Water", "Thames Water", "Yorkshire Water", "United Utilities")])
    return pick[["site_id", "company", "lat", "lon", "lta_spills", "spill_hours", "edm_operational_pct"]].reset_index(drop=True)


def test_real_overflow_rows_through_the_frozen_models():
    from dipcast.ingest.rainfall import cells_for_sites
    from dipcast.model import forecast
    sc.clear_cache(); sr.clear_cache(); ls.candidates.cache_clear()
    models = sc.parts()
    ov = _real_overflows()
    assert len(ov) == 12 and ov["company"].nunique() == 4
    # A wet spell: 0.6 mm an hour for the 40 days to the end of the grid, at every overflow's own rain cell.
    days = pd.date_range("2026-11-18", periods=7, freq="D", tz=TZ)          # two past days, then leads 0 to 4
    t = pd.date_range("2026-10-10", "2026-11-25", freq="h", tz="UTC")
    fetched = (NOW - pd.Timedelta(hours=2)).tz_convert("UTC")
    rain = pd.concat([pd.DataFrame({"cell_lat": la, "cell_lon": lo, "time": t, "precip_mm": 0.6, "issued_at": fetched})
                      for la, lo in cells_for_sites(ov["lat"], ov["lon"])], ignore_index=True)
    p_raw, avail, sd = forecast.spill_probabilities(ov, days, forecast._model(), rain=rain, return_frame=True)
    assert avail.all() and np.isfinite(p_raw).all()
    # Each company: one spilling at issue, one known and dry, one whose last reading is 9 hours old (stale).
    ov = ov.assign(status=[1, 0, 0] * 4, data_state="live")
    table = _table(ov["site_id"])
    table.loc[ov["site_id"].iloc[2::3], "last_reading"] = (NOW - pd.Timedelta(hours=9)).tz_convert("UTC")
    table["spill_hours_24h"] = [6.0, 0.0, 0.0] * 4
    table["spill_days_7d"] = [2.0, 0.0, 0.0] * 4
    sd0, p0 = sd.copy(), p_raw.copy()
    out = sc.combined(sd, ov, days, 2, NOW, p_raw, rain=rain, status_table=table)
    pd.testing.assert_frame_equal(sd, sd0)
    assert np.array_equal(p_raw, p0)
    uu = (ov["company"] == "United Utilities").to_numpy()
    assert out["known"].tolist() == [True, True, False] * 4 and out["english"].all()
    assert np.isfinite(out["p"]).all() and ((out["p"] > 0) & (out["p"] < 1)).all()
    # United Utilities' base is production's raw chance; the other three companies take v2, which differs from it.
    assert np.array_equal(out["base"][uu], p_raw[uu]) and out["v2"].tolist() == (~uu).tolist()
    assert np.abs(out["base"][~uu] - p_raw[~uu]).max() > 1e-3
    # Stale rows and the two past days are the base alone; known rows at leads 0 to 4 take the uplift.
    stale = ~out["known"]
    assert np.array_equal(out["p"][stale], out["base"][stale]) and np.array_equal(out["p"][:, :2], out["base"][:, :2])
    assert out["uplift"][~stale, 2:].all() and not out["uplift"][stale].any() and not out["uplift"][:, :2].any()
    # The uplift, rebuilt row by row from each frozen model's own prediction on the frame.
    filled = sd.fillna({f: 0.0 for f in ALL_FEATURES})
    st = ls.status_known(ov, NOW, table).assign(site_id=ov["site_id"].to_numpy()).set_index("site_id")
    for k in sc.LEADS:
        f = filled[filled["day"] == days[2 + k]].set_index("site_id").reindex(ov["site_id"]).reset_index()
        cand = models["candidates"][k].predict(f.join(st[ls.STATUS], on="site_id"))
        d2 = models["d2"].predict(f)
        want = 1 / (1 + np.exp(-(np.log(out["base"][:, 2 + k] / (1 - out["base"][:, 2 + k]))
                                 + np.log(cand / (1 - cand)) - np.log(d2 / (1 - d2)))))
        assert out["p"][~stale, 2 + k] == pytest.approx(want[~stale], rel=1e-9)
        assert out["d2"][:, 2 + k] == pytest.approx(d2) and out["cand"][~stale, 2 + k] == pytest.approx(cand[~stale])
    # The forecast hands over the regional shadow's own result to save a model pass: the same numbers.
    again = sc.combined(sd, ov, days, 2, NOW, p_raw, rain=rain, status_table=table, routed=sr.routed(sd, ov, days, p_raw))
    assert np.array_equal(again["p"], out["p"]) and np.array_equal(again["base"], out["base"])
    # An overflow spilling at issue is raised above its base on the day itself; every rain time is before the issue.
    spilling = (ov["status"] == 1).to_numpy()
    assert (out["p"][spilling, 2] > out["base"][spilling, 2]).all()
    assert (pd.DatetimeIndex(out["rain_at"]) == fetched).all()


# ------------------------------------------------------------------ nothing published changes
def _point(tmp_path, monkeypatch):
    """forecast_point at a fixed 06:30 on two Yorkshire overflows and one United Utilities one, with fixed rain and a
    stand-in production model, all three watched every 2 h for nine days. Returns run(models) -> (the result, rain
    requests)."""
    from dipcast.model import forecast
    from dipcast.model.transport import PinLocation, clear_time, live_now_risk

    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "t.duckdb")
    now = NOW.tz_convert("UTC")
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
        t = pd.date_range(now.floor("D") - pd.Timedelta(days=40), periods=24 * 50, freq="h")
        return pd.concat([pd.DataFrame({"cell_lat": a, "cell_lon": b, "time": t, "precip_mm": 0.4,
                                        "issued_at": now - pd.Timedelta(minutes=20)}) for a, b in cells], ignore_index=True)

    class Model:
        trained_on = "test"

        def predict(self, sd):
            return np.where(sd["site_id"] == "A1", 0.55, 0.33)

    monkeypatch.setattr(forecast, "_now", lambda: NOW)
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
    monkeypatch.setattr(ls, "candidates", dict)             # the live-status shadow itself stays off here
    monkeypatch.setattr(sr, "v2_model", lambda: None)       # and so does the regional one: neither table is written
    table = _table(ov["site_id"])
    monkeypatch.setattr(ls, "_status_for", lambda d: table)

    def run(models):
        monkeypatch.setattr(sc, "parts", lambda: models)
        calls.clear()
        return forecast.forecast_point(53.92, -1.70, days_ahead=4, gauge=False, log_to_store=True), len(calls)

    return run


def test_the_published_forecast_and_the_rain_requests_do_not_change(tmp_path, monkeypatch):
    run = _point(tmp_path, monkeypatch)
    off, n_off = run(None)
    db = tmp_path / "t.duckdb"
    assert sc.TABLE not in _read(db, "SHOW TABLES")["name"].tolist()        # off: no table, no row
    before = _read(db, "SELECT * FROM forecast_overflows ORDER BY site_id, target_day")
    on, n_on = run(_models())
    assert n_on == n_off                       # the shadow asks for no rain of its own
    assert on == off                           # and changes nothing the page or the API gets
    tables = _read(db, "SHOW TABLES")["name"].tolist()
    assert sc.TABLE in tables and sr.TABLE not in tables
    after = _read(db, "SELECT * FROM forecast_overflows ORDER BY site_id, target_day")
    assert len(after) == 2 * len(before)       # the issued history gets its usual rows a second time, the same ones
    pd.testing.assert_frame_equal(after.iloc[::2].reset_index(drop=True), before)
    pd.testing.assert_frame_equal(after.iloc[1::2].reset_index(drop=True), before)
    t = _read(db)
    assert len(t) == 15 and (t["applied"] == "uplift").all()
    assert t.loc[t["site_id"] == "A1", "p_raw"].tolist() == pytest.approx([0.55] * 5)       # production beside it
    assert t.loc[t["site_id"] == "A1", "p_cal"].tolist() == pytest.approx([0.55] * 5)       # no lead map in this test
    assert t.loc[t["site_id"] == "U3", "p_base"].tolist() == pytest.approx([0.33] * 5)      # United Utilities: production's
    assert t.loc[t["site_id"] == "B2", "p_base"].tolist() == pytest.approx([0.30] * 5)      # the eight: v2's
    assert (pd.to_datetime(t["rain_issued_at"], utc=True) < pd.to_datetime(t["issued_at"], utc=True)).all()
    assert (pd.to_datetime(t["status_read_at"], utc=True) < pd.to_datetime(t["issued_at"], utc=True)).all()


def test_a_failing_shadow_never_fails_the_forecast(tmp_path, monkeypatch):
    run = _point(tmp_path, monkeypatch)
    off, _ = run(None)

    class Broken:
        def predict(self, df):
            raise RuntimeError("model file corrupt")
    on, _ = run({"v2": Broken(), "d2": Broken(), "candidates": {}})
    assert on == off
    assert sc.TABLE not in _read(tmp_path / "t.duckdb", "SHOW TABLES")["name"].tolist()


def test_a_forecast_after_eight_logs_nothing(tmp_path, monkeypatch):
    from dipcast.model import forecast
    run = _point(tmp_path, monkeypatch)
    monkeypatch.setattr(forecast, "_now", lambda: pd.Timestamp("2026-11-20 11:00", tz=TZ))
    run(_models())
    assert sc.TABLE not in _read(tmp_path / "t.duckdb", "SHOW TABLES")["name"].tolist()
