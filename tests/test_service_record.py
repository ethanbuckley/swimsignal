"""Tests for the Accuracy page's plain figures (4 Oct 2026): the spill and E. coli forecasts counted
as warnings at the site's own High risk line, and the service record (runs against the schedule,
feed outages, the morning forecast, the run log)."""

import json
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "Europe/London"
ROOT = Path(__file__).resolve().parents[1]


def _state(tmp_path, monkeypatch):
    from dipcast import config
    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "PROCESSED", tmp_path)
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "t.duckdb")
    return config


def _mask(hours):
    return int(sum(1 << (h * 2) for h in hours))


# ---------------------------------------------------------------- the warning line
def test_the_warning_lines_are_the_sites_own_high_risk_lines():
    from dipcast import forecast_log as fl
    from dipcast.model.transport import risk_label
    assert risk_label(fl.SPILL_WARN_AT) == "high" and risk_label(fl.SPILL_WARN_AT - 1e-9) == "moderate"
    levels = (ROOT / "src/dipcast/site/levels.js").read_text()
    cuts = lambda name: [float(x) for x in re.search(rf"{name} = \[([^\]]+)\]", levels).group(1).split(",")]
    assert cuts("SPILL_CUTS")[1] == fl.SPILL_WARN_AT     # moderate | high
    assert cuts("ECOLI_CUTS")[1] == fl.ECOLI_WARN_AT     # moderate | high
    assert "const HIGH = 2;" in (ROOT / "push/src/index.js").read_text()   # alerts are sent at high


def test_the_schedule_matches_the_workflow():
    from dipcast import forecast_log as fl
    crons = re.findall(r'cron: "([^"]+)"', (ROOT / ".github/workflows/site.yml").read_text())
    assert crons == ["*/30 * * * *"] and fl.SCHEDULED_RUNS_PER_DAY == 48


# ---------------------------------------------------------------- warning counts
def test_warning_counts_put_the_always_no_share_beside_the_share_correct():
    from dipcast.forecast_log import warning_counts
    y = [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    p = [0.5, 0.1, 0.45, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.39]
    t = warning_counts(y, p, 0.40)
    assert (t["hits"], t["misses"], t["false_alarms"], t["quiet_correct"]) == (1, 1, 1, 7)
    assert t["hit_rate"] == 0.5 and t["warnings_true"] == 0.5
    assert t["share_correct"] == 0.8 and t["always_no_correct"] == 0.8     # no better than never warning
    # Yet a warning says something: an event followed half of them, against 2 in 10 overall.
    assert t["base_rate"] == 0.2 and abs(t["warning_lift"] - 2.5) < 1e-12
    none = warning_counts([0, 0], [0.1, 0.2], 0.40)
    assert none["hit_rate"] is None and none["warnings_true"] is None and none["always_no_correct"] == 1.0
    assert none["base_rate"] == 0.0 and none["warning_lift"] is None
    quiet = warning_counts([1, 0], [0.1, 0.2], 0.40)     # no warnings at all
    assert quiet["warnings_true"] is None and quiet["warning_lift"] is None


def test_verify_live_writes_the_spill_warning_table(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast import forecast_log as fl
    ov = pd.DataFrame({"site_id": ["A", "B"], "has_live": [True, True], "weight": [0.5, 0.5]})
    days = pd.date_range("2026-09-13", periods=3, freq="D", tz=TZ)
    # A at 0.45 (a warning) on every day, B at 0.39 (just under). A spilled on the 14th, B on the 15th.
    p = np.array([[0.45] * 3, [0.39] * 3])
    fl.log_forecast(pd.Timestamp("2026-09-14 07:30", tz=TZ), 54.0, -2.0, "river", "R", 0.1, days, np.full(3, 0.1), ov,
                    p, p, version="v-test")
    hist = pd.DataFrame({"site_id": ["A", "B"], "company": ["X", "X"], "status": [0, 0],
                         "status_start": pd.to_datetime(["2026-09-01", "2026-09-01"], utc=True),
                         "latest_event_start": pd.to_datetime(["2026-09-14 10:00", "2026-09-15 10:00"], utc=True),
                         "latest_event_end": pd.to_datetime(["2026-09-14 12:00", "2026-09-15 12:00"], utc=True),
                         "fetched_at": pd.to_datetime(["2026-09-15 13:00", "2026-09-15 13:00"], utc=True)})
    hist.to_parquet(tmp_path / "live_history.parquet", index=False)
    every2h = _mask(range(0, 24, 2))
    pd.DataFrame({"site_id": ["A", "A", "A", "B", "B", "B"],
                  "day": pd.to_datetime(["2026-09-14", "2026-09-15", "2026-09-16"] * 2),
                  "n_known": 12, "n_unknown": 0, "n_stale": 0, "slots": every2h}).to_parquet(tmp_path / fl.COVERAGE_FILE, index=False)
    monkeypatch.setattr(fl, "verify_ecoli", lambda as_of: {"n_scored": 0})
    out = fl.verify_live(as_of=date(2026, 9, 16))
    w = out["warning_table"]
    # Scored: A and B on the 14th (lead 0) and the 15th (lead 1). A warned both days: a hit on the 14th,
    # a false alarm on the 15th. B never warned: a correct quiet day on the 14th, a miss on the 15th.
    assert out["n_scored"] == 4 and w["warn_at"] == 0.40 and w["level"] == "high"
    assert (w["hits"], w["misses"], w["false_alarms"], w["quiet_correct"]) == (1, 1, 1, 1)
    assert w["n_spill_overflow_days"] == 2 and w["n_overflow_days"] == 4 and w["n_days"] == 2
    assert w["share_correct"] == 0.5 and w["always_no_correct"] == 0.5
    assert w["base_rate"] == 0.5 and w["warning_lift"] == 1.0     # a warning made a spill no likelier
    assert [r["lead"] for r in w["by_lead"]] == [0, 1] and w["by_lead"][0]["hits"] == 1 and w["by_lead"][1]["misses"] == 1
    assert json.loads((tmp_path / "verification_live.json").read_text())["warning_table"]["hits"] == 1


def test_ecoli_warning_table_is_one_row_per_river_sample(tmp_path, monkeypatch):
    config = _state(tmp_path, monkeypatch)
    from dipcast import forecast_log as fl
    sites = json.loads((config.RAW / "bathing_waters_inland.json").read_text())
    river = next(s for s in sites if s["kind"] == "river")
    lake = next(s for s in sites if s["kind"] == "lake")
    days = pd.date_range("2026-09-09", periods=3, freq="D", tz=TZ)
    # The river: issued the day before (lead 1 at 0.30) and on the morning (lead 0 at 0.20); the
    # morning's is the latest before the 11:00 sample, so it is the one counted: no warning.
    for issued, pe in ((pd.Timestamp("2026-09-09 07:00", tz=TZ), [0.1, 0.30, 0.1]),
                       (pd.Timestamp("2026-09-10 07:00", tz=TZ), [np.nan, 0.20, 0.30])):
        fl.log_forecast(issued, round(river["lat"], 5), round(river["lon"], 5), "river", "R", 0.1, days, np.full(3, 0.1),
                        pd.DataFrame(), np.zeros((0, 3)), np.zeros((0, 3)), p_ecoli=np.array(pe), rain_48h=np.full(3, 1.0))
    fl.log_forecast(pd.Timestamp("2026-09-10 07:00", tz=TZ), round(lake["lat"], 5), round(lake["lon"], 5), "lake", "L", 0.1, days,
                    np.full(3, 0.1), pd.DataFrame(), np.zeros((0, 3)), np.zeros((0, 3)), p_ecoli=np.array([np.nan, 0.9, 0.9]),
                    rain_48h=np.full(3, 1.0))
    samples = pd.DataFrame({"bw_id": [river["id"], river["id"], lake["id"]], "name": [river["name"], river["name"], lake["name"]],
                            "kind": ["river", "river", "lake"],
                            "sample_time": pd.to_datetime(["2026-09-10 11:00", "2026-09-11 11:00", "2026-09-10 11:00"]).tz_localize(TZ),
                            "ecoli": [1500, 100, 2000]})
    samples.to_parquet(tmp_path / fl.ECOLI_SAMPLES, index=False)
    w = fl.verify_ecoli(as_of=date(2026, 9, 12))["warning_table"]
    # 10 Sep: 0.20, over 900: a miss. 11 Sep: 0.30 from the 10th's issue, under 900: a false alarm.
    assert w["n"] == 2 and w["n_sites"] == 1 and w["n_lake_samples_left_out"] == 1
    assert (w["hits"], w["misses"], w["false_alarms"], w["quiet_correct"]) == (0, 1, 1, 0)
    assert w["leads"] == {"0": 1, "1": 1} and w["warn_at"] == 0.25 and w["too_few_to_judge"] is True


# ---------------------------------------------------------------- service record
def _poll_log(path, polls, down=()):
    rows = []
    for t in polls:
        for c in ("Alpha Water", "Beta Water"):
            rows.append({"fetched_at": pd.Timestamp(t, tz="UTC"), "company": c,
                         "n_rows": 0 if (c, t) in down else 10, "n_known": 10, "feed_age_h": 0.5})
    pd.DataFrame(rows).to_parquet(path, index=False)


def test_service_record_counts_runs_feeds_mornings_and_the_run_log(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast import forecast_log as fl
    # First poll on 1 Oct (a partial day, left out); whole days 2 and 3 Oct; the 4th is today.
    polls = ["2026-10-01 20:00", "2026-10-02 03:00", "2026-10-02 09:00", "2026-10-02 15:00",
             "2026-10-03 06:00", "2026-10-03 18:00", "2026-10-04 06:00"]
    _poll_log(tmp_path / fl.POLL_LOG_FILE, polls, down={("Beta Water", "2026-10-03 06:00")})
    days = pd.date_range("2026-10-01", periods=5, freq="D", tz=TZ)
    for issued in ("2026-10-02 04:00", "2026-10-03 19:00"):   # 2 Oct before 08:00 local; 3 Oct only in the evening
        fl.log_forecast(pd.Timestamp(issued, tz="UTC"), 54.0, -2.0, "river", "R", 0.1, days, np.full(5, 0.1),
                        pd.DataFrame(), np.zeros((0, 5)), np.zeros((0, 5)))
    health = {"spots": 10, "forecast_ok": 9, "forecast_failed": 1, "no_forecast_possible": 0, "today_rain_unavailable": 0,
              "live_feeds": {"rows": {"Alpha Water": 10, "Beta Water": 0}, "down": ["Beta Water"]}}
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    fl.log_build(health, pd.Timestamp("2026-10-03 07:00", tz=TZ))
    fl.log_build({**health, "forecast_ok": 10, "forecast_failed": 0}, pd.Timestamp("2026-10-03 19:00", tz=TZ))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    fl.log_build(None, pd.Timestamp("2026-10-03 20:00", tz=TZ), failed="only 3/10 spots got a forecast; not publishing")
    s = fl.service_record(as_of=date(2026, 10, 4))
    r = s["runs"]
    assert (r["from_day"], r["to_day"], r["n_days"], r["n"]) == ("2026-10-02", "2026-10-03", 2, 5)
    assert r["scheduled"] == 96 and abs(r["share_of_scheduled"] - 5 / 96) < 1e-12
    assert r["per_day_median"] == 2.5 and r["per_day_min"] == 2 and r["per_day_max"] == 3 and r["days_without_run"] == []
    # Waits before each run in the window: 7 h (from 1 Oct 20:00), 6, 6, 15, 12; the longest ends 3 Oct 06:00 UTC.
    assert r["max_gap_h"] == 15.0 and r["max_gap_ended"] == "2026-10-03T07:00+01:00" and r["median_gap_h"] == 7.0
    f = s["feeds"]
    assert f["n_polls"] == 5 and f["n_down"] == 1
    assert {c["company"]: (c["polls"], c["down"]) for c in f["companies"]} == {"Alpha Water": (5, 0), "Beta Water": (5, 1)}
    assert s["morning"] == {"from_day": "2026-10-02", "to_day": "2026-10-03", "n_days": 2, "n_with_forecast": 1,
                            "days_without": ["2026-10-03"]}
    b = s["builds"]
    assert b["n"] == 3 and b["n_published"] == 2 and b["by_event"] == {"schedule": 2, "push": 1}
    assert b["spots_attempted"] == 20 and b["spots_forecast"] == 19 and b["share_forecast"] == 0.95 and b["runs_every_spot"] == 1
    assert b["worst"] == {"at": "2026-10-03T07:00+01:00", "forecast_ok": 9, "spots": 10}
    assert b["not_published"] == [{"at": "2026-10-03T20:00+01:00", "why": "only 3/10 spots got a forecast; not publishing"}]
    assert b["since"] == "2026-10-03T07:00+01:00"


def test_service_record_reads_without_creating_a_forecast_log(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast import forecast_log as fl
    assert fl.service_record(as_of=date(2026, 10, 4)) is None
    assert not (tmp_path / "t.duckdb").exists()
    _poll_log(tmp_path / fl.POLL_LOG_FILE, ["2026-10-01 20:00", "2026-10-02 10:00", "2026-10-03 10:00"])
    s = fl.service_record(as_of=date(2026, 10, 4))
    assert s["runs"]["n"] == 2 and "morning" not in s and "builds" not in s
    assert not (tmp_path / "t.duckdb").exists()


def test_load_verification_carries_the_service_record_and_survives_its_failure(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast import forecast_log as fl
    _poll_log(tmp_path / fl.POLL_LOG_FILE, ["2026-10-01 20:00", "2026-10-02 10:00"])
    monkeypatch.setattr(fl, "service_record", lambda: {"runs": {"n": 1}})
    assert fl.load_verification()["service"] == {"runs": {"n": 1}}

    def broken():
        raise RuntimeError("no")
    monkeypatch.setattr(fl, "service_record", broken)
    assert fl.load_verification()["service"] is None


def test_log_build_never_stops_a_build(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast import config
    from dipcast import forecast_log as fl
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "missing-dir" / "x" / "t.duckdb")   # cannot be opened
    fl.log_build({"spots": 1}, pd.Timestamp("2026-10-03 07:00", tz=TZ))   # logs a warning, raises nothing


def test_the_build_logs_each_run_before_writing_verification_json():
    src = (ROOT / "scripts/build_site.py").read_text()
    i, j = src.index("log_build(health, generated)"), src.index('(SITE / "data" / "verification.json").write_text(')
    assert i < j
    assert 'log_build(None, pd.Timestamp.now(tz="Europe/London"), failed=str(e))' in src
