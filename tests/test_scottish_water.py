"""Tests for Scottish Water's shadow adapter (ingest.scottish_water, Scotland plan task S4): the status
mapping, a data state per asset from its own transmit time, the stuck-monitor rule, both events per
asset in a history keyed by discharge id, and the setting that keeps it off. The rows are a trimmed
copy of the API's answer at 18:19 UTC on 4 Oct 2026 (fixtures/scottish_water_nrt.json). Source:
Scottish Water."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "scottish_water_nrt.json").read_text())
FETCHED = pd.Timestamp(FIXTURE["fetched_at"])


def _snap(body=None, fetched=FETCHED):
    from dipcast.ingest.scottish_water import parse
    return parse(body or FIXTURE, fetched).set_index("site_id")


def _state(tmp_path, monkeypatch):
    from dipcast import config
    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "PROCESSED", tmp_path)
    return config


def test_status_mapping_and_why_there_is_no_data():
    s = _snap()
    assert len(s) == 13 and (s["company"] == "Scottish Water").all()
    assert s.loc["CSO005416", ["status", "status_text"]].tolist() == [1, "Overflowing"]
    assert s.loc["CSO000022", ["status", "status_text"]].tolist() == [0, "Recent Overflow"]
    assert s.loc["CSO000007", ["status", "status_text"]].tolist() == [0, "No Overflows"]
    assert s.loc["CSO000026", ["status", "status_text", "no_data_reason"]].tolist() == [-1, "No Data Available", "Under Maintenance"]
    assert s.loc["CSO002279", "no_data_reason"] == "Non real-time monitored"
    assert s.loc["CSO003333", "no_data_reason"] == "No valid data received in the past 48 hours"
    assert s.loc[s["status"] >= 0, "no_data_reason"].isna().all()
    # An Overflowing asset has no end to its latest event; a Recent Overflow's ended within 48 hours.
    assert s.loc[s["status"] == 1, "latest_event_end"].isna().all()
    ended = FETCHED - s.loc["CSO000022", "latest_event_end"]
    assert pd.Timedelta(0) < ended <= pd.Timedelta(hours=48)
    # Times are UTC, as the API page says.
    assert s.loc["CSO000022", "latest_event_start"] == pd.Timestamp("2026-10-02 14:40", tz="UTC")


def test_a_code_it_does_not_know_reads_as_offline():
    body = copy.deepcopy(FIXTURE)
    body["results"][0]["OVERFLOW_STATUS_ID"] = "99"
    s = _snap(body)
    assert s.loc[body["results"][0]["ASSET_ID"], ["status", "data_state"]].tolist() == [-1, "offline"]


def test_emergency_overflows_are_marked_alone_or_in_a_mixed_type():
    s = _snap()
    assert s.loc["CSO005416", ["asset_type", "emergency"]].tolist() == ["EO", True]
    assert s.loc["CSO002070", ["asset_type", "emergency"]].tolist() == ["CSO/EO", True]
    assert not s.loc["CSO007547", "emergency"]    # SSSO
    assert not s.loc["CSO000007", "emergency"]    # CSO


def test_data_state_comes_from_each_assets_own_transmit_time():
    s = _snap()
    assert s.loc["CSO000007", "data_state"] == "live"
    assert s.loc["CSO000022", "data_state"] == "live"
    # No Overflows, but its data last arrived 18 hours before the poll: the reading may be frozen.
    assert s.loc["CSO000325", "data_state"] == "stale"
    assert FETCHED - s.loc["CSO000325", "transmitted_at"] > pd.Timedelta(hours=6)
    # The device answered 2.2 hours before; its data is 54 hours old. The older time is the one used.
    t = s.loc["CSO003333"]
    assert t["transmitted_at"] < t["device_transmitted_at"]
    assert round((FETCHED - t["transmitted_at"]).total_seconds() / 3600, 1) == 54.1
    assert (s.loc[s["status"] == -1, "data_state"] == "offline").all()
    # The same rows read a day later are all stale or offline: nothing is current by default.
    later = _snap(fetched=FETCHED + pd.Timedelta(days=1))
    assert set(later["data_state"]) == {"stale", "offline"}
    assert (later["status"] == s["status"]).all()


def test_a_monitor_overflowing_for_over_a_week_is_flagged_stuck_and_stays_discharging():
    from dipcast.ingest.scottish_water import STUCK_H
    s = _snap()
    stuck = s[s["stuck"]]
    assert sorted(stuck.index) == ["CSO000375", "CSO006614"]
    assert sorted(stuck["open_h"].round(1)) == [223.6, 687.7]
    assert (stuck["status"] == 1).all() and (stuck["data_state"] == "stale").all()
    # 52 hours is long, and real: not stuck, and live.
    assert 48 < s.loc["CSO007547", "open_h"] < STUCK_H and s.loc["CSO007547", "data_state"] == "live"
    assert s.loc[s["status"] != 1, "open_h"].isna().all() and not s.loc[s["status"] != 1, "stuck"].any()


def test_both_events_per_asset_go_to_the_history_by_discharge_id():
    from dipcast.ingest.scottish_water import events, parse
    snap = parse(FIXTURE, FETCHED)
    ev = events(snap).set_index("discharge_id")
    rows = {r["ASSET_ID"]: r for r in FIXTURE["results"]}
    want = {r[k] for r in rows.values() for k in ("OVERFLOW_DISCHARGEID", "OVERFLOW_DISCHARGEID_PREVIOUS") if r[k]}
    assert set(ev.index) == want and ev.index.is_unique
    a = rows["CSO000022"]
    assert ev.loc[a["OVERFLOW_DISCHARGEID"], ["site_id", "event", "status"]].tolist() == ["CSO000022", "latest", 0]
    assert ev.loc[a["OVERFLOW_DISCHARGEID_PREVIOUS"], ["site_id", "event", "status"]].tolist() == ["CSO000022", "previous", 0]
    assert ev.loc[a["OVERFLOW_DISCHARGEID"], "duration_min"] == float(a["OVERFLOW_DURATION_MIN"])
    # The open event of an Overflowing asset is status 1 with no end; a stuck one keeps its flag.
    o = ev.loc[rows["CSO006614"]["OVERFLOW_DISCHARGEID"]]
    assert o["status"] == 1 and pd.isna(o["latest_event_end"]) and o["stuck"]
    assert not ev.loc[rows["CSO006614"]["OVERFLOW_DISCHARGEID_PREVIOUS"], "stuck"]
    # An asset with only a latest event gives one row; one with none gives none.
    assert (ev["site_id"] == "CSO000329").sum() == 1
    assert (ev["site_id"] == "CSO000044").sum() == 0


def test_a_later_poll_keeps_the_event_that_moved_to_previous_and_fills_in_its_end(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast.forecast_log import observed_spill_days
    from dipcast.ingest.scottish_water import HISTORY_FILE, parse, save
    first = save(parse(FIXTURE, FETCHED))
    # An hour later CSO005416's open event (EO) has ended and a new one has begun.
    body = copy.deepcopy(FIXTURE)
    r = next(x for x in body["results"] if x["ASSET_ID"] == "CSO005416")
    old_id = r["OVERFLOW_DISCHARGEID"]
    r.update({"OVERFLOW_START_DATETIME_PREVIOUS": r["OVERFLOW_START_DATETIME"],
              "OVERFLOW_END_DATETIME_PREVIOUS": "2026-10-04T18:40:00.000Z",
              "OVERFLOW_DISCHARGEID_PREVIOUS": old_id,
              "OVERFLOW_START_DATETIME": "2026-10-04T19:00:00.000Z", "OVERFLOW_END_DATETIME": "",
              "OVERFLOW_DISCHARGEID": "999001",
              "DEVICE_LAST_TRANSMITTED_DATETIME": "2026-10-04T19:10:00.000Z",
              "LAST_TRANSMITTED_DATETIME": "2026-10-04T19:10:00.000Z"})
    second = save(parse(body, FETCHED + pd.Timedelta(hours=1)))
    assert len(second) == len(first) + 1
    h = pd.read_parquet(tmp_path / HISTORY_FILE).set_index("discharge_id")
    assert h.index.is_unique
    assert h.loc[old_id, ["event", "status"]].tolist() == ["previous", 0]
    assert h.loc[old_id, "latest_event_end"] == pd.Timestamp("2026-10-04 18:40", tz="UTC")
    assert h.loc[old_id, "first_seen"] == FETCHED and h.loc[old_id, "fetched_at"] == FETCHED + pd.Timedelta(hours=1)
    assert h.loc["999001", ["event", "status"]].tolist() == ["latest", 1]
    # The history reads as the English scorer reads live_history (task S5).
    days = observed_spill_days(h.reset_index())
    assert {"site_id", "day"} <= set(days.columns) and ("CSO005416" in set(days["site_id"]))


def test_save_writes_only_its_own_files_and_a_failed_poll_writes_nothing(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast.ingest import scottish_water as sw
    sw.save(sw.parse(FIXTURE, FETCHED))
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([sw.LATEST_FILE, sw.HISTORY_FILE])

    def down():
        raise RuntimeError("Scottish Water API failed after 3 attempts")
    monkeypatch.setattr(sw, "fetch", down)
    before = (tmp_path / sw.LATEST_FILE).read_bytes()
    assert sw.poll() == {"ok": False, "error": "Scottish Water API failed after 3 attempts"}
    assert (tmp_path / sw.LATEST_FILE).read_bytes() == before
    monkeypatch.setattr(sw, "fetch", lambda: {"results": [], "last_updated": None})
    assert sw.poll()["assets"] == 0 and (tmp_path / sw.LATEST_FILE).read_bytes() == before


def test_the_setting_is_off_unless_set_to_1():
    code = "from dipcast import config; print(config.SCOTTISH_WATER)"
    env = {k: v for k, v in os.environ.items() if k != "DIPCAST_SCOTTISH_WATER"}
    run = lambda e: subprocess.run([sys.executable, "-c", code], env=e, capture_output=True, text=True, check=True).stdout.strip()
    assert run(env) == "False"
    assert run({**env, "DIPCAST_SCOTTISH_WATER": "0"}) == "False"
    assert run({**env, "DIPCAST_SCOTTISH_WATER": "1"}) == "True"


def test_refresh_all_polls_scotland_only_when_the_setting_is_on(monkeypatch):
    from dipcast import config, forecast_log, jobs, overflows
    from dipcast.ingest import live, scottish_water
    polled = []
    monkeypatch.setattr(live, "fetch_live", lambda **kw: pd.DataFrame({"status": [0]}))
    monkeypatch.setattr(live, "save_live", lambda df, *a: None)
    monkeypatch.setattr(overflows, "build_overflows", lambda net: pd.DataFrame({"site_id": ["A"]}))
    monkeypatch.setattr(forecast_log, "verify_live", lambda: {"n_scored": 0})
    monkeypatch.setattr(scottish_water, "poll", lambda: polled.append(1) or {"ok": True})
    monkeypatch.setattr(config, "SCOTTISH_WATER", False)
    jobs.refresh_all(net=object())
    assert polled == []
    monkeypatch.setattr(config, "SCOTTISH_WATER", True)
    jobs.refresh_all(net=object())
    assert polled == [1]
