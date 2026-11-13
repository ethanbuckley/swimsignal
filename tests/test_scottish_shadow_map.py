"""Tests for Scotland's mapped shadow arm, scotland-map-v1 (scottish_shadow_map, docs/SCOTLAND-MAP-SHADOW-ARM-2026-11.md):
the pinned map, the rows and their fallbacks, that it logs the existing shadow's issues in a file of its own and
changes nothing of that shadow, that the read joins no outcome before its date, the three measures, the derived
series, and that nothing is published or switched on. Assets from the trimmed API answer of 4 Oct 2026 (source:
Scottish Water); networks, rain, forecasts and outcomes are made up."""

import ast
import hashlib
import shutil
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest
from test_scottish_shadow import _Model, _rain, _scot_net, _snapshot, _state

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "data" / "processed" / "scotland_calibration.json"
VERSION = "spill=808da63d;cal=aaaa1111;ecoli=bbbb2222;code=0.1.0+abc;rain=open-meteo-forecast;cov=sw:c2f2f654;region=scotland-shadow"


@pytest.fixture(autouse=True)
def _fresh_map():
    from dipcast import scotland_trial
    scotland_trial.calibration_map.cache_clear()
    yield
    scotland_trial.calibration_map.cache_clear()


def _with_map(tmp_path, monkeypatch):
    """A scratch state and processed directory holding the committed map, with the committed spill model in use."""
    config = _state(tmp_path, monkeypatch)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    shutil.copy(MAP, config.PROCESSED / MAP.name)
    # The spill model in use is the committed one, whichever directory was current when its module was first imported.
    from dipcast.model import forecast
    monkeypatch.setattr(forecast, "MODEL_PATH", ROOT / "data" / "processed" / "spill_model.pkl")
    return config


def _shadow_rows(issued="2026-11-10T07:00", p_raw=(0.6, 0.1, 0.1, 0.3), p_cal=(0.5, 0.08, 0.08, 0.25), rain=True):
    """The existing shadow's rows for one build: overflows A and B, the next two days."""
    t = pd.Timestamp(issued, tz="Europe/London")
    d = t.date()
    days = [(t.normalize() + pd.Timedelta(days=k)).date() for k in (1, 2)]
    return pd.DataFrame({"issued_at": t, "issue_day": d, "lat": 56.0, "lon": -4.0, "site_id": ["A", "A", "B", "B"],
                         "has_live": True, "target_day": days * 2, "lead": [1, 2, 1, 2], "p_raw": list(p_raw),
                         "p_cal": list(p_cal), "weight": 1.0, "rain_available": rain, "version": VERSION, "rain_mm": 3.0,
                         "covariates": ["sw2025", "sw2025", "filled", "filled"], "rain_age_h": 2.0})


def _table(path):
    from dipcast.scottish_shadow_map import TABLE
    con = duckdb.connect(str(path), read_only=True)
    try:
        return con.execute(f"SELECT * FROM {TABLE} ORDER BY site_id, target_day").df()
    finally:
        con.close()


# ------------------------------------------------------------------ the map
def test_v1_is_the_committed_map_and_the_trials_own_formula(tmp_path, monkeypatch):
    from dipcast import scotland_trial
    from dipcast import scottish_shadow_map as m
    assert hashlib.sha256(MAP.read_bytes()).hexdigest() == m.MAP_SHA256
    _with_map(tmp_path, monkeypatch)
    assert m.map_state() == (True, None, m.MAP_SHA256[:8])
    assert not scotland_trial.enabled()                        # the arm does not need the trial on, and leaves it off
    p = np.array([0.001, 0.05, 0.3, 0.6, 0.97])
    mp = m.pinned_map()
    assert mp["spill_stamp"] == m.SPILL_STAMP
    assert np.allclose(m.apply_pinned(p, mp), scotland_trial.apply_map(p), atol=0, rtol=1e-15)


def test_rows_keep_the_shadows_numbers_and_add_the_mapped_chance(tmp_path, monkeypatch):
    _with_map(tmp_path, monkeypatch)
    from dipcast import scotland_trial
    from dipcast import scottish_shadow_map as m
    rows = _shadow_rows()
    before = rows.copy(deep=True)
    out = m.mapped_rows(rows)
    pd.testing.assert_frame_equal(rows, before)                # the existing shadow's rows are not altered
    assert list(out.columns) == list(m.COLUMNS)
    assert (out["p_raw"] == rows["p_raw"]).all() and (out["p_prod"] == rows["p_cal"]).all()
    assert np.allclose(out["p_map"], scotland_trial.apply_map(rows["p_raw"].to_numpy()))
    assert out["p_map"].iloc[0] > out["p_prod"].iloc[0]         # the map lifts the level England's calibration leaves low
    assert out["map_applied"].all() and out["fallback"].isna().all()
    assert set(out["arm"]) == {f"scotland-map-v1;spill=808da63d;cov=sw:c2f2f654;map={m.MAP_SHA256[:8]}"}
    assert (out["version"] == VERSION).all()
    # The arm's label names what changes the mapped number, not the E. coli model or England's calibration.
    assert "ecoli" not in out["arm"].iloc[0] and "cal=" not in out["arm"].iloc[0]


def test_a_cell_without_rain_is_logged_and_never_mapped(tmp_path, monkeypatch):
    _with_map(tmp_path, monkeypatch)
    from dipcast import scottish_shadow_map as m
    rows = _shadow_rows(p_raw=(0.0, 0.1, 0.0, 0.3), p_cal=(0.0, 0.08, 0.0, 0.25))
    rows["rain_available"] = [False, True, False, True]
    out = m.mapped_rows(rows)
    assert out["map_applied"].tolist() == [False, True, False, True]
    assert out["fallback"].fillna("").tolist() == ["no rain", "", "no rain", ""] and out["p_map"].isna().tolist() == [True, False, True, False]
    assert m.log_rows(rows, 4)["fallback"] == {"no rain": 2}
    con = duckdb.connect(str(tmp_path / m.DB), read_only=True)
    try:   # in the file a mapped row's fallback and an unmapped row's p_map are empty, not text or zero
        assert con.execute(f"SELECT count(*) FILTER (fallback IS NULL), count(*) FILTER (p_map IS NULL) FROM {m.TABLE}").fetchall() == [(2, 2)]
    finally:
        con.close()


def test_without_v1s_map_rows_fall_back_to_production_and_say_why(tmp_path, monkeypatch):
    config = _with_map(tmp_path, monkeypatch)
    from dipcast import scotland_trial
    from dipcast import scottish_shadow_map as m
    from dipcast.model import forecast
    rows = _shadow_rows()

    def state():
        scotland_trial.calibration_map.cache_clear()
        out = m.mapped_rows(rows)
        assert not out["map_applied"].any() and out["p_map"].isna().all()
        assert (out["p_prod"] == rows["p_cal"]).all()          # production's forecast is what is left
        return set(out["fallback"])

    other = tmp_path / "other_model.pkl"
    other.write_bytes(b"another spill model")
    monkeypatch.setattr(forecast, "MODEL_PATH", other)
    assert state() == {"map fitted for another spill model"}
    monkeypatch.undo()
    config = _with_map(tmp_path, monkeypatch)
    (config.PROCESSED / MAP.name).write_text(MAP.read_text().replace('"a": 0.449', '"a": 0.5'))
    assert state() == {"map file is not v1's"}
    (config.PROCESSED / MAP.name).unlink()
    assert state() == {"no map file"}


# ------------------------------------------------------------------ log
def test_logs_only_the_builds_the_existing_shadow_logged_and_each_once(tmp_path, monkeypatch):
    _with_map(tmp_path, monkeypatch)
    from dipcast import scottish_shadow_map as m
    rows = _shadow_rows()
    assert m.log_rows(rows, 0) == {"rows_logged": 0} and not (tmp_path / m.DB).exists()
    assert m.log_rows(rows.iloc[0:0], 4) == {"rows_logged": 0}
    out = m.log_rows(rows, 4)
    assert out["rows_logged"] == 4 and out["map_applied"] == 4 and "fallback" not in out
    assert m.log_rows(rows, 4)["rows_logged"] == 0             # the same issue is not written twice
    assert m.log_rows(_shadow_rows("2026-11-11T07:00"), 4)["rows_logged"] == 4
    t = _table(tmp_path / m.DB)
    assert len(t) == 8 and list(t.columns) == list(m.COLUMNS)
    # Its own file: neither England's log nor the existing shadow's is created or touched.
    from dipcast.scottish_shadow import FORECASTS_DB
    assert not (tmp_path / "dipcast.duckdb").exists() and not (tmp_path / FORECASTS_DB).exists()


def _run(tmp_path, monkeypatch, hook=True):
    """scottish_shadow.run once on the six-asset snapshot, at 06:30 on 5 Oct 2026, with rain in every cell."""
    config = _with_map(tmp_path, monkeypatch)
    from dipcast import scottish_shadow
    from dipcast.ingest import rainfall
    from dipcast.ingest import scottish_water as sw
    from dipcast.model import forecast
    monkeypatch.setattr(forecast, "_lead_calibration", dict)
    snap = _snapshot()
    snap.to_parquet(config.STATE / sw.LATEST_FILE)
    rainfall.CACHE.mkdir(parents=True, exist_ok=True)

    def fetch(cells):
        for c in cells:
            _rain([c]).to_parquet(rainfall.CACHE / f"forecast_{rainfall.cell_key(*c)}.parquet")
    if not hook:
        monkeypatch.setattr(scottish_shadow, "_map_arm", lambda rows, logged: {})
    out = scottish_shadow.run(net=_scot_net(snap), now=pd.Timestamp("2026-10-05T06:30", tz="Europe/London"),
                              rain_fetch=fetch, model=_Model())
    con = duckdb.connect(str(config.STATE / scottish_shadow.FORECASTS_DB), read_only=True)
    try:
        existing = con.execute("SELECT * FROM forecast_overflows ORDER BY site_id, target_day").df()
    finally:
        con.close()
    return out, existing


def test_the_build_logs_both_arms_and_the_existing_one_is_as_it_was_without_the_new(tmp_path, monkeypatch):
    from dipcast import scottish_shadow_map as m
    out, existing = _run(tmp_path / "with", monkeypatch)
    assert out["ok"] and out["rows_logged"] == 20 and out["map_arm"]["rows_logged"] == 20
    mapped = _table(tmp_path / "with" / m.DB)
    key = ["site_id", "target_day", "lead"]
    j = existing.merge(mapped, on=key, suffixes=("", "_m"), validate="1:1")
    assert len(j) == 20 and (j["issued_at"] == j["issued_at_m"]).all() and (j["version"] == j["version_m"]).all()
    assert (j["p_raw"] == j["p_raw_m"]).all() and (j["p_cal"] == j["p_prod"]).all()
    from dipcast import scotland_trial
    assert np.allclose(j["p_map"], scotland_trial.apply_map(j["p_raw"].to_numpy()))
    assert m.counts(tmp_path / "with")["same_issues_as_existing_shadow"] == {
        "compared": 20, "not_in_existing_log": 0, "p_raw_differs": 0, "p_prod_differs": 0, "p_map_is_not_the_map_of_p_raw": 0}
    # The same build without the new arm writes the same rows, stamp included, to the existing log.
    monkeypatch.undo()
    out0, existing0 = _run(tmp_path / "without", monkeypatch, hook=False)
    assert out0["rows_logged"] == 20 and not (tmp_path / "without" / m.DB).exists()
    pd.testing.assert_frame_equal(existing, existing0)
    assert existing["version"].str.endswith("region=scotland-shadow").all() and "map" not in existing["version"].iloc[0]


def test_a_failure_in_the_new_arm_leaves_the_existing_shadow_running(tmp_path, monkeypatch):
    from dipcast import scottish_shadow_map as m

    def broken(rows, logged):
        raise RuntimeError("disk full")
    monkeypatch.setattr(m, "log_rows", broken)
    out, existing = _run(tmp_path, monkeypatch)
    assert out["ok"] and out["rows_logged"] == 20 and len(existing) == 20
    assert out["map_arm"] == {"rows_logged": 0, "error": "disk full"}


# ------------------------------------------------------------------ read
def _read_state(tmp_path, monkeypatch, logged_p_raw=(0.6, 0.1, 0.1, 0.3)):
    """A and B forecast at 07:00 on 10 Nov 2026 for 11 and 12 Nov, in both logs; fully observed 11-13 Nov. A spills
    on 11 Nov and B on 12 Nov."""
    _with_map(tmp_path, monkeypatch)
    from dipcast import scottish_shadow_map as m
    from dipcast.ingest import scottish_water as sw
    from dipcast.scottish_shadow import OVERFLOWS_FILE, _db_conn
    full = (1 << 48) - 1
    pd.DataFrame([{"site_id": s, "day": pd.Timestamp(d), "n_known": 48, "n_unknown": 0, "n_stale": 0, "slots": full}
                  for s in "AB" for d in ("2026-11-11", "2026-11-12", "2026-11-13")]).to_parquet(tmp_path / sw.COVERAGE_FILE)
    t = lambda s: pd.Timestamp(s, tz="UTC")
    pd.DataFrame({"site_id": ["A", "B"], "company": "Scottish Water", "discharge_id": ["1", "2"], "event": "latest",
                  "status": [0, 0], "latest_event_start": [t("2026-11-11T10:00"), t("2026-11-12T09:00")],
                  "latest_event_end": [t("2026-11-11T11:00"), t("2026-11-12T10:00")], "duration_min": [60.0, 60.0],
                  "stuck": False, "first_seen": t("2026-11-13T12:00"),
                  "fetched_at": t("2026-11-13T12:00")}).to_parquet(tmp_path / sw.HISTORY_FILE)
    pd.DataFrame({"site_id": ["A", "B"], "company": "Scottish Water", "lta_spills": [36.5, 36.5]}).to_parquet(tmp_path / OVERFLOWS_FILE)
    rows = _shadow_rows()
    con = _db_conn()
    con.register("r", rows)
    con.execute("INSERT INTO forecast_overflows BY NAME SELECT * FROM r").fetchall()
    con.close()
    assert m.log_rows(_shadow_rows(p_raw=logged_p_raw), 4)["rows_logged"] == 4
    return m


def test_before_the_read_date_no_outcome_is_joined(tmp_path, monkeypatch):
    m = _read_state(tmp_path, monkeypatch)
    from dipcast import forecast_log

    def refuse(*a, **k):
        raise AssertionError("an outcome was joined before the read date")
    monkeypatch.setattr(forecast_log, "verify_live", refuse)
    monkeypatch.setattr(forecast_log, "observed_spill_days", refuse)
    assert m.READ_NOT_BEFORE == date(2027, 2, 3) and m.WINDOW_END == date(2027, 1, 31)
    out = m.read(tmp_path, tmp_path / "work", today=date(2027, 2, 2))
    assert out["read"].startswith("not run") and "logged" not in out and "derived" not in out
    assert out["counts"]["rows"] == 4 and out["counts"]["outcomes_joined"] is False
    assert out["counts"]["issue_days"] == 1 and out["counts"]["map_applied_share_of_rows_with_rain"] == 1.0
    assert out["counts"]["covariates"] == {"sw2025": 2, "filled": 2}
    assert m.read(tmp_path, today=date(2027, 3, 1), counts_only=True)["read"] == "not run: counts only"
    assert not (tmp_path / "work").exists()
    # The script's default is today's date, which is before the read date: counts only.
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import scotland_map_arm_read
    assert scotland_map_arm_read.main(["--state", str(tmp_path)])["read"].startswith("not run")


def test_the_read_scores_both_forecasts_on_the_same_rows_by_gate_bs_rules(tmp_path, monkeypatch):
    m = _read_state(tmp_path, monkeypatch)
    from dipcast import scotland_trial
    from dipcast.scottish_shadow import FORECASTS_DB, SCORES_JSON
    before = {n: hashlib.sha256((tmp_path / n).read_bytes()).hexdigest() for n in (m.DB, FORECASTS_DB)}
    out = m.read(tmp_path, tmp_path / "work", today=date(2027, 2, 3))
    (arm, r), = out["logged"].items()
    assert arm.startswith("scotland-map-v1;spill=808da63d;cov=sw:c2f2f654;map=")
    y = np.array([1, 0, 0, 1])                                  # A 11 Nov, A 12 Nov, B 11 Nov, B 12 Nov
    p_map = scotland_trial.apply_map(np.array([0.6, 0.1, 0.1, 0.3]))
    p_prod = np.array([0.5, 0.08, 0.08, 0.25])
    assert r["n"] == 4 and r["spill_days"] == 2 and r["target_days"] == 2 and r["status"] == "too few"
    assert r["brier_map"] == pytest.approx(np.mean((p_map - y) ** 2), abs=1e-4)      # the scored file keeps 4 places
    assert r["brier_prod"] == pytest.approx(np.mean((p_prod - y) ** 2), abs=1e-4)
    assert r["brier_clim"] == pytest.approx(np.mean((0.1 - y) ** 2), abs=1e-4)       # 36.5 spills a year
    assert r["M2_level"]["level"] == pytest.approx(p_map.sum() / 2, abs=1e-3)
    assert r["M3_gain_over_production"]["gain"] == pytest.approx(1 - ((p_map - y) ** 2).sum() / ((p_prod - y) ** 2).sum(), abs=1e-3)
    assert not (r["M1_skill_vs_climatology"]["holds"] or r["M2_level"]["holds"] or r["M3_gain_over_production"]["holds"])
    assert set(r["by_covariates"]) == {"own count", "filled"} and set(r["by_england_calibration"]) == {"aaaa1111"}
    assert set(r["by_lead"]) == {"1", "2"} and r["by_month"]["2026-11"]["n"] == 4
    # The derived series: the map of the existing shadow's own raw chance, the same rows here, kept apart.
    d = out["derived"]
    assert d["status"].startswith("derived, not logged") and d["check"]["p_map_is_not_the_map_of_p_raw"] == 0
    assert d["full_window"]["n"] == 4 and d["full_window"]["brier_map"] == pytest.approx(r["brier_map"], abs=1e-9)
    # Neither log is written by the read, and the existing shadow's scores are not made or replaced.
    assert before == {n: hashlib.sha256((tmp_path / n).read_bytes()).hexdigest() for n in (m.DB, FORECASTS_DB)}
    assert not (tmp_path / SCORES_JSON).exists()


def test_the_derived_series_is_dropped_when_the_logged_rows_are_not_the_map_of_the_existing_raw_chance(tmp_path, monkeypatch):
    m = _read_state(tmp_path, monkeypatch, logged_p_raw=(0.5, 0.1, 0.1, 0.3))
    out = m.read(tmp_path, tmp_path / "work", today=date(2027, 2, 3))
    assert out["derived"]["status"].startswith("dropped") and out["derived"]["check"]["p_raw_differs"] == 1
    assert "full_window" not in out["derived"] and len(out["logged"]) == 1


def test_derived_rows_start_after_the_map_was_committed_and_need_its_spill_model():
    from dipcast import scottish_shadow_map as m
    e = pd.concat([_shadow_rows("2026-11-01T07:00"), _shadow_rows("2026-11-02T07:00"), _shadow_rows("2026-11-03T07:00"),
                   _shadow_rows("2026-11-04T07:00").assign(version=VERSION.replace("808da63d", "11111111")),
                   _shadow_rows("2026-11-05T07:00").assign(rain_available=False)], ignore_index=True)
    d = m.derived_forecasts(e)
    assert sorted(set(d["issue_day"])) == [date(2026, 11, 2), date(2026, 11, 3)]
    assert np.allclose(d["p_map"], m.apply_pinned(d["p_raw"].to_numpy(), m.pinned_map(MAP)))
    assert (d["p_prod"] == d["p_cal"]).all() and set(d["arm"]) == {"scotland-map-v1;derived"}


def test_only_mapped_rows_inside_the_window_are_scored(tmp_path, monkeypatch):
    _with_map(tmp_path, monkeypatch)
    from dipcast import scottish_shadow_map as m
    late = m.mapped_rows(_shadow_rows("2027-01-31T07:00"))      # target days 1 and 2 Feb: after the window
    off = m.mapped_rows(_shadow_rows()).assign(map_applied=False)
    assert m.scored(pd.concat([late, off], ignore_index=True), tmp_path, tmp_path / "work", date(2027, 2, 10), "t").empty
    assert not (tmp_path / "work").exists()


def _scored(p_map, p_prod, y, n_days, n_sites, lead=1):
    return pd.DataFrame({
        "overflow_id": np.tile([f"S{i}" for i in range(n_sites)], n_days),
        "day": np.repeat([str(d.date()) for d in pd.date_range("2026-11-16", periods=n_days)], n_sites),
        "lead": lead, "p_map": p_map.ravel(), "p_prod": p_prod.ravel(), "climatology": 0.08, "observed": y.ravel(),
        "covariates": "sw2025", "rain_mm": 2.0, "rain_age_h": 3.0, "arm": "a", "cal": "c"})


def test_the_three_measures_and_what_makes_each_hold():
    from dipcast import scottish_shadow_map as m
    from dipcast.scottish_shadow import gate_b
    rng = np.random.default_rng(1)
    n_days, n_sites = 77, 40
    y = (rng.random((n_days, n_sites)) < 0.08).astype(int)
    good = np.where(y == 1, 0.6, 0.03)
    low = good * 0.65                                            # the level England's calibration leaves
    rows = _scored(good, low, y, n_days, n_sites)
    r = m.measures(rows)
    assert r["status"] == "read" and r["spill_days"] >= 200 and r["target_days"] == 77
    m1, m2, m3 = r["M1_skill_vs_climatology"], r["M2_level"], r["M3_gain_over_production"]
    assert m1["holds"] and m2["holds"] and m3["holds"]
    # M1 is Gate B's own figure and interval on these rows.
    g = gate_b(rows.assign(forecast_calibrated=rows["p_map"]))["arms"][0]
    assert m1["skill"] == g["skill"] and m1["interval_95"] == g["interval_95"]
    assert 0.9 <= m2["level"] <= 1.1 and m2["interval_95"][0] < m2["level"] < m2["interval_95"][1]
    assert m3["gain"] > 0 and m3["interval_95"][0] > 0 and r["level_prod"] == pytest.approx(0.65 * m2["level"])
    assert r["production_on_the_same_rows"]["skill"] < m1["skill"]
    assert m.measures(rows) == m.measures(rows)                  # seeded: the same every run
    # The same forecast as its own comparator: no gain, and an interval at zero is not "better".
    same = m.measures(_scored(good, good, y, n_days, n_sites))
    assert same["M3_gain_over_production"]["gain"] == 0 and not same["M3_gain_over_production"]["holds"]
    # Right order, wrong level: M1 holds and M2 does not.
    high = m.measures(_scored(np.where(y == 1, 0.9, 0.06), low, y, n_days, n_sites))
    assert high["M1_skill_vs_climatology"]["holds"] and not high["M2_level"]["holds"]
    # Same-day forecasts are not in the measures; they are reported by lead.
    lead0 = m.measures(_scored(good, low, y, n_days, n_sites, lead=0))
    assert lead0["status"] == "too few" and lead0["n"] == 0
    # Under 30 target days, or under 200 spill-days, nothing holds whatever the figures.
    few = m.measures(_scored(good[:29], low[:29], y[:29], 29, n_sites))
    assert few["status"] == "too few" and not any(few[k]["holds"] for k in ("M1_skill_vs_climatology", "M2_level", "M3_gain_over_production"))


# ------------------------------------------------------------------ off by default, never published
def test_nothing_is_published_and_the_trial_switch_is_not_touched():
    from dipcast import scottish_shadow_map as m
    workflow = (ROOT / ".github" / "workflows" / "site.yml").read_text()
    site = "\n".join(p.read_text() for p in (ROOT / "src" / "dipcast" / "site").glob("*.*") if p.suffix in (".js", ".html"))
    build = (ROOT / "scripts" / "build_site.py").read_text() + (ROOT / "scripts" / "build_any_point.py").read_text()
    for text in (workflow, site, build):
        assert m.DB not in text and m.TABLE not in text and "scottish_shadow_map" not in text
    src = (ROOT / "src" / "dipcast" / "scottish_shadow_map.py").read_text()
    tree = ast.parse(src)
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "SCOTLAND_TRIAL" not in names and "enabled" not in names and "rainfall" not in names   # no switch, no rain request
    # Only the existing shadow calls it, and only through its guard.
    callers = [p.name for p in (ROOT / "src" / "dipcast").rglob("*.py")
               if "scottish_shadow_map" in p.read_text() and p.name != "scottish_shadow_map.py"]
    assert callers == ["scottish_shadow.py"]
    from dipcast import config
    assert config.SCOTLAND_TRIAL is False
