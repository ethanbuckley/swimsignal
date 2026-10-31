"""Catchment replay (src/dipcast/replay.py): spills as reported, arrivals as estimates, gaps left blank.

Synthetic poll histories in the shape of live_history.parquet (ingest.live.save_live): one row per
distinct (site, status, status_start), with the feed's latest event on each."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dipcast import replay

NOW = pd.Timestamp("2026-10-25T22:00Z")
T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def hist(*rows) -> pd.DataFrame:
    cols = ["site_id", "status", "status_start", "latest_event_start", "latest_event_end", "fetched_at"]
    df = pd.DataFrame([dict(zip(cols, r, strict=True)) for r in rows], columns=cols)
    for c in cols[2:]:
        df[c] = pd.to_datetime(df[c], utc=True)
    return df


def test_a_finished_spill_is_reported_and_its_water_modelled_past_the_spot():
    h = hist(("A", 1, "2026-10-24T10:00", "2026-10-24T10:00", None, "2026-10-24T10:20"),
             ("A", 0, "2026-10-24T12:00", "2026-10-24T10:00", "2026-10-24T12:00", "2026-10-25T21:30"))
    cur = {"status": 0, "latest_event_start": "2026-10-24T10:00Z", "latest_event_end": "2026-10-24T12:00Z"}
    [s] = replay.spill_intervals(h, cur, NOW)
    assert (s["start"], s["end"], s["end_known"], s["running"]) == (T("2026-10-24T10:00"), T("2026-10-24T12:00"), True, False)
    a = replay.arrival(s, 5.0, NOW)
    assert (a["from"], a["to"], a["state"]) == (T("2026-10-24T15:00"), T("2026-10-24T17:00"), "passed")


def test_a_spill_still_running_has_no_end_and_its_water_is_due_or_arriving():
    h = hist(("A", 1, "2026-10-25T20:00", "2026-10-25T20:00", "2026-10-20T01:00", "2026-10-25T21:30"))
    cur = {"status": 1, "status_start": "2026-10-25T20:00Z", "latest_event_start": "2026-10-25T20:00Z",
           "latest_event_end": "2026-10-20T01:00Z"}   # the feed's previous event's end: before the start, ignored
    [s] = replay.spill_intervals(h, cur, NOW)
    assert s["running"] and s["end"] is None
    assert replay.arrival(s, 1.0, NOW)["state"] == "at_spot"
    due = replay.arrival(s, 6.0, NOW)
    assert due["state"] == "due" and due["to"] is None


def test_water_that_passed_before_now_and_water_due_after_now():
    s = {"start": T("2026-10-25T08:00"), "end": T("2026-10-25T09:00"), "running": False, "end_known": True}
    assert replay.arrival(s, 4, NOW)["state"] == "passed"
    assert replay.arrival(s, 13.5, NOW)["state"] == "at_spot"
    assert replay.arrival(s, 14.5, NOW)["state"] == "due"
    assert replay.arrival(s, None, NOW) is None and replay.arrival(s, float("nan"), NOW) is None


def test_an_end_never_reported_stays_unknown_and_the_offline_gap_is_listed():
    # Discharging, then the monitor went offline and is still offline: no stop was ever reported.
    h = hist(("A", 1, "2026-10-25T06:00", "2026-10-25T06:00", None, "2026-10-25T06:10"),
             ("A", -1, "2026-10-25T08:00", "2026-10-25T06:00", None, "2026-10-25T21:30"))
    cur = {"status": -1, "status_start": "2026-10-25T08:00Z"}
    [s] = replay.spill_intervals(h, cur, NOW)
    assert s["end"] is None and not s["end_known"] and not s["running"]
    assert replay.arrival(s, 2, NOW)["state"] == "unknown_end"
    [off] = replay.offline_spans(h, cur, NOW)
    assert off == {"from": T("2026-10-25T08:00"), "to": NOW}


def test_an_offline_spell_that_ended_is_closed_by_the_next_reading():
    h = hist(("A", -1, "2026-10-24T08:00", None, None, "2026-10-24T09:00"),
             ("A", 0, "2026-10-24T11:30", None, None, "2026-10-25T21:30"))
    assert replay.offline_spans(h, {"status": 0}, NOW) == [{"from": T("2026-10-24T08:00"), "to": T("2026-10-24T11:30")}]


def test_a_feed_that_did_not_answer_is_a_gap_from_its_last_answer():
    cur = {"status": -3, "feed_down_since": "2026-10-25T18:00Z", "last_status": 0}
    [off] = replay.offline_spans(None, cur, NOW)
    assert off["from"] == T("2026-10-25T18:00") and off["to"] == NOW and off["feed_down"]


def test_a_yorkshire_latest_event_is_the_tail_of_the_spill_the_stop_closes():
    # YWS00199, 24 Oct 2026: discharging from 17:04:39, stopped 20:51:50; its "latest event" 20:51:20-20:51:50.
    h = hist(("Y", 1, "2026-10-24T17:04:39", "2026-10-24T17:04:39", None, "2026-10-24T19:37"),
             ("Y", 0, "2026-10-24T20:51:50", "2026-10-24T20:51:20", "2026-10-24T20:51:50", "2026-10-25T21:30"))
    cur = {"status": 0, "status_start": "2026-10-24T20:51:50Z", "latest_event_start": "2026-10-24T20:51:20Z",
           "latest_event_end": "2026-10-24T20:51:50Z"}
    out = replay.spill_intervals(h, cur, NOW)
    assert len(out) == 1 and out[0]["start"] == T("2026-10-24T17:04") and out[0]["end"] == T("2026-10-24T20:51:50")


def test_two_spills_stay_two_and_a_later_start_closes_nothing_by_guess():
    h = hist(("A", 0, "2026-10-24T03:00", "2026-10-24T01:00", "2026-10-24T03:00", "2026-10-24T05:00"),
             ("A", 1, "2026-10-25T10:00", "2026-10-25T10:00", None, "2026-10-25T10:30"),
             ("A", 1, "2026-10-25T15:00", "2026-10-25T15:00", None, "2026-10-25T21:30"))
    cur = {"status": 1, "status_start": "2026-10-25T15:00Z", "latest_event_start": "2026-10-25T15:00Z"}
    out = replay.spill_intervals(h, cur, NOW)
    assert [(s["start"].hour, s["end_known"], s["running"]) for s in out] == [(1, True, False), (10, False, False), (15, False, True)]


def _rain_file(d: Path, cell, start, vals, issued):
    t = pd.date_range(start, periods=len(vals), freq="h", tz="UTC")
    pd.DataFrame({"cell_lat": cell[0], "cell_lon": cell[1], "time": t, "precip_mm": vals,
                  "issued_at": pd.Timestamp(issued, tz="UTC")}).to_parquet(d / f"forecast_{cell[0]:.3f}_{cell[1]:.3f}.parquet")


def test_rain_has_a_value_only_where_every_cell_has_one_and_says_where_the_forecast_starts(tmp_path):
    start = NOW - pd.Timedelta(hours=48)
    a = [1.0] * 48
    b = [3.0] * 48
    b[5] = np.nan                    # one cell missing an hour: the hour is blank, not 1.0
    _rain_file(tmp_path, (54.0, -1.8), start - pd.Timedelta(hours=24), [0.0] * 24 + a, "2026-10-25T20:10")
    _rain_file(tmp_path, (54.1, -1.8), start, b, "2026-10-25T20:40")
    r = replay.rain_series([(54.0, -1.8), (54.1, -1.8)], start, 48, tmp_path)
    assert r["mm"][0] == 2.0 and r["mm"][5] is None and r["cells"] == 2
    assert r["forecast_from"] == "2026-10-25T21:00Z"   # the earlier issue time, to the next hour
    assert replay.rain_series([(50.0, 0.0)], start, 48, tmp_path) == {"unavailable": "not every rain cell upstream is in this build's rain cache"}
    assert "unavailable" in replay.rain_series([], start, 48, tmp_path)


def test_the_gauge_is_its_current_reading_and_its_time_only():
    assert replay.gauge_of({}) == {"unavailable": "no level gauge matched to this spot"}
    g = replay.gauge_of({"river_state": {"station": "Flint Mill", "level_m": 1.52, "observed_at": "2026-10-25T21:15:00Z", "stale": False,
                                         "rise_6h_m": 0.15, "rise_from": "x", "rise_to": "y"}})
    assert g["level_m"] == 1.52 and g["observed_at"] == "2026-10-25T21:15:00Z"
    assert not any(k.startswith("rise") for k in g) and "series" not in g   # Ethan, 26 Oct 2026: the reading alone
    old = replay.gauge_of({"river_state": {"station": "S", "level_m": None, "last_level_m": 0.9, "stale": True}})
    assert old["level_m"] is None and old["last_level_m"] == 0.9


def test_water_through_a_lake_shows_its_spills_but_no_arrival():
    # Through a lake (transport puts its metres in lake_distance_m): the reported spill stays, the arrival goes,
    # and so does the travel time, so no river-speed precision is given for it.
    h = hist(("L", 0, "2026-10-25T12:00", "2026-10-25T10:00", "2026-10-25T12:00", "2026-10-25T21:30"))
    r = replay.spot_replay({"id": "x"}, [contributor(1, site_id="L", lake_distance_km=1.4, travel_h=30.0, weight=0.5)], h, NOW)
    [o] = r["overflows"]
    assert o["lake_route"] is True and o["travel_h"] is None
    assert o["spills"][0]["start"] == "2026-10-25T10:00Z" and o["spills"][0]["arrival"] is None
    assert r["window"]["ahead_to"] == r["window"]["to"]   # nothing due drawn ahead of now
    river = replay.spot_replay({"id": "x"}, [contributor(1, site_id="L", lake_distance_km=0.0, travel_h=30.0, weight=0.5)], h, NOW)
    assert river["overflows"][0]["lake_route"] is False and river["overflows"][0]["spills"][0]["arrival"]["state"] == "due"


def test_the_real_lake_fixture_has_no_arrivals():
    doc = json.loads((Path(__file__).parent / "fixtures" / "replay_waterhead.json").read_text())
    assert doc["overflows"] and all(o["lake_route"] for o in doc["overflows"])
    assert all(s["arrival"] is None for o in doc["overflows"] for s in o["spills"])


def test_a_lake_spot_never_gets_river_arrivals_from_zero_or_missing_lake_distance():
    h = hist(("L", 0, "2026-10-25T12:00", "2026-10-25T10:00", "2026-10-25T12:00", "2026-10-25T21:30"))
    for distance in (0.0, None):
        r = replay.spot_replay({"id": "lake", "kind": "lake"},
            [contributor(1, site_id="L", lake_distance_km=distance, travel_h=30.0, weight=0.5)], h, NOW)
        [o] = r["overflows"]
        assert o["lake_route"] is True and o["travel_h"] is None
        assert o["spills"] and all(s["arrival"] is None for s in o["spills"])


def test_the_page_asks_for_replay_js_at_the_builds_stamp_and_the_offline_copy_stores_it():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_site as bs
    page = bs.with_build(bs.TEMPLATE.read_text(), "abc12345")
    # mountReplay reads the stamp off levels.js's tag, which with_build versions.
    assert '<script src="levels.js?v=abc12345"></script>' in page
    assert """document.querySelector('script[src*="levels.js?v="]')""" in page
    assert "s.src = `replay.js${v ? `?v=${new URL(v).searchParams.get('v')}` : ''}`;" in page
    assert '<script src="replay.js' not in page   # no tag: nothing loads without ?replay=1
    assert bs.TEMPLATE.parent / "replay.js" in bs.SHELL_SOURCES
    sw = (bs.TEMPLATE.parent / "sw.js").read_text()
    assert "`replay.js?v=${BUILD}`" in sw
    assert "/-(trace|replay|plume)$/" in sw   # a replay file (or a spill map's routes) never sends the worker after a trace of its own

def contributor(i, **kw):
    return {"site_id": f"S{i}", "site_name": f"PLACE {i}/CSO", "company": "Yorkshire Water", "lat": 54.0, "lon": -1.8,
            "distance_km": float(i), "lake_distance_km": 0.0, "travel_h": 2.0 * i, "weight": 0.9 / (i + 1),
            "status": 0, "data_state": "live", **kw}


def test_spot_replay_lists_overflows_with_events_and_counts_the_quiet_ones_by_state(tmp_path):
    h = hist(("S1", 0, "2026-10-25T03:00", "2026-10-25T01:00", "2026-10-25T03:00", "2026-10-25T21:30"),
             ("S2", 0, "2026-10-01T03:00", None, None, "2026-10-25T21:30"),       # quiet all window, known since 1 Oct
             ("S4", -1, "2026-10-25T05:00", None, None, "2026-10-25T21:30"),
             ("S7", 0, "2026-10-25T10:00", None, None, "2026-10-25T21:30"))       # first seen inside the window
    ups = [contributor(1), contributor(2), contributor(3, status=-1, data_state="offline"),
           contributor(4, status=-1, data_state="offline"), contributor(5, data_state="no_feed", status=-2),
           contributor(6, weight=0.001, latest_event_start="2026-10-25T10:00Z", latest_event_end="2026-10-25T11:00Z"),
           contributor(7, weight=0.1)]
    r = replay.spot_replay({"id": "x"}, ups, h, NOW, tmp_path)
    assert [o["site_id"] for o in r["overflows"]] == ["S1", "S4"]   # S6 is under the weight the page counts
    assert r["overflows"][1]["state"] == "offline" and r["overflows"][1]["offline"][0]["to"] == "2026-10-25T22:00Z"
    # Quiet is not proof: S3 and S5 have no poll history at all, S7 none before 10:00 on the 25th.
    assert r["quiet"] == {"live": {"n": 1, "weight": 0.3}, "no_history": {"n": 2, "weight": 0.375},
                          "late_history": {"n": 1, "weight": 0.1}}
    assert r["coverage"] == {"unavailable": "no poll log in this build's state"} and r["truncated"] is False
    assert r["counted"] == 6 and r["rain"] == {"unavailable": "not every rain cell upstream is in this build's rain cache"}
    s = r["overflows"][0]["spills"][0]
    assert s["arrival"] == {"from": "2026-10-25T03:00Z", "to": "2026-10-25T05:00Z", "state": "passed"}


def test_a_spill_before_the_window_whose_water_arrives_in_it_is_kept():
    h = hist(("S9", 0, "2026-10-23T12:00", "2026-10-23T10:00", "2026-10-23T12:00", "2026-10-25T21:30"))
    r = replay.spot_replay({"id": "x"}, [contributor(9, travel_h=20.0, weight=0.5)], h, NOW)
    assert r["overflows"][0]["spills"][0]["arrival"]["state"] == "passed"
    r = replay.spot_replay({"id": "x"}, [contributor(9, travel_h=2.0, weight=0.5)], h, NOW)
    assert r["overflows"] == [] and r["quiet"]["live"]["n"] == 1


def busy_history(n_sites=20, n_spills=20, offline=True):
    """Each site: n_spills spills in the window, and as many offline spells between them."""
    rows = []
    for i in range(n_sites):
        for k in range(n_spills):
            a = NOW - pd.Timedelta(hours=47) + pd.Timedelta(hours=2 * k)
            rows.append((f"S{i}", 0, a + pd.Timedelta(minutes=30), a, a + pd.Timedelta(minutes=30), NOW))
            if offline:
                rows.append((f"S{i}", -1, a + pd.Timedelta(minutes=60), None, None, NOW))
    return hist(*[(s, st, *(None if x is None else str(x) for x in (b, c, d, e))) for s, st, b, c, d, e in rows])


def busy_poll_log(companies):
    """Polls every 30 min with a 2 h gap every 3 h, for each company: 16 gaps."""
    t = pd.date_range(NOW - pd.Timedelta(hours=48), NOW, freq="30min")
    t = [x for x in t if (x - t[0]).total_seconds() % (3 * 3600) >= 2 * 3600]
    return pd.DataFrame([{"fetched_at": x, "company": c, "n_rows": 100} for x in t for c in companies])


def test_the_worst_case_is_cut_to_the_budget_and_says_what_it_left_out():
    companies = [f"Company {i} Water Services Limited" for i in range(20)]
    ups = [contributor(i, site_name="A LONG OVERFLOW NAME WITH MANY WORDS/NO 2 STW/STORM TANK/" + "X" * 40,
                       company=companies[i]) for i in range(20)]
    spot = {"id": "x", "river_state": {"station": "Flint Mill", "level_m": 1.5, "observed_at": "2026-10-25T21:15:00Z"}}
    r = replay.spot_replay(spot, ups, busy_history(), NOW, poll_log=busy_poll_log(companies))
    body = json.dumps({**r, "generated_at": NOW.isoformat()}, separators=(",", ":"), default=str)
    assert len(body) <= replay.REPLAY_MAX_BYTES, len(body)
    assert r["truncated"] is True and len(r["overflows"]) < replay.MAX_ROWS
    assert len(r["overflows"]) + r["more_with_events"] == 20   # every overflow with events is listed or counted
    o = r["overflows"][0]
    assert len(o["spills"]) == replay.MAX_SPILLS and o["earlier_spills"] == 20 - replay.MAX_SPILLS
    assert len(o["offline"]) == replay.MAX_OFFLINE and o["earlier_offline"] == 20 - replay.MAX_OFFLINE
    cov = r["coverage"][companies[0]]
    assert len(cov["gaps"]) == replay.MAX_GAPS and cov["more_gaps"] == 16 - replay.MAX_GAPS


def test_a_busy_catchment_without_gaps_keeps_its_twelve_rows():
    ups = [contributor(i) for i in range(20)]
    r = replay.spot_replay({"id": "x"}, ups, busy_history(n_spills=6, offline=False), NOW)
    assert len(r["overflows"]) == replay.MAX_ROWS and r["more_with_events"] == 8 and r["truncated"] is False


def test_poll_coverage_gives_the_polls_the_gaps_and_a_late_start():
    since = NOW - pd.Timedelta(hours=48)
    t = list(pd.date_range(since + pd.Timedelta(hours=3), NOW - pd.Timedelta(minutes=10), freq="30min"))
    t = [x for x in t if not (T("2026-10-24T10:00") < x < T("2026-10-24T14:00"))]
    log = pd.DataFrame([{"fetched_at": x, "company": "Y", "n_rows": 300} for x in t]
                       + [{"fetched_at": T("2026-10-24T12:00"), "company": "Y", "n_rows": 0},   # answered nothing: not a poll
                          {"fetched_at": T("2026-10-24T12:00"), "company": "Z", "n_rows": 0}])
    cov = replay.poll_coverage(log, {"Y", "Z", None}, since, NOW)
    y = cov["Y"]
    assert y["starts_late"] is True and y["from"] == "2026-10-24T01:00Z" and y["polls"] == len(t)
    assert ["2026-10-24T10:00Z", "2026-10-24T14:00Z"] in y["gaps"] and ["2026-10-23T22:00Z", "2026-10-24T01:00Z"] in y["gaps"]
    assert cov["Z"] == {"polls": 0, "gaps": [["2026-10-23T22:00Z", "2026-10-25T22:00Z"]]}
    assert replay.poll_coverage(None, {"Y"}, since, NOW) == {"unavailable": "no poll log in this build's state"}


def test_an_end_rebuilt_across_a_poll_gap_is_a_range_not_a_time():
    # Seen discharging at the 10:20 poll; no answered poll 10:30-13:30; then the feed says it stopped at 12:00.
    h = hist(("A", 1, "2026-10-25T10:00", "2026-10-25T10:00", None, "2026-10-25T10:20"),
             ("A", 0, "2026-10-25T12:00", "2026-10-25T11:58", "2026-10-25T12:00", "2026-10-25T21:30"))
    cur = {"status": 0, "status_start": "2026-10-25T12:00Z", "latest_event_start": "2026-10-25T11:58Z",
           "latest_event_end": "2026-10-25T12:00Z"}
    gaps = [(T("2026-10-25T10:30"), T("2026-10-25T13:30"))]
    [s] = replay.spill_intervals(h, cur, NOW, gaps)
    assert s["end"] is None and not s["end_known"]
    assert (s["end_after"], s["end_by"]) == (T("2026-10-25T10:20"), T("2026-10-25T12:00"))   # the tail 11:58-12:00 is inside it
    a = replay.arrival(s, 2.0, NOW)
    assert a["to"] is None and (a["to_after"], a["to_by"], a["state"]) == (T("2026-10-25T12:20"), T("2026-10-25T14:00"), "passed")
    # The same rows with no gap: the feed's stop is taken as the end (the Yorkshire tail case).
    [exact] = replay.spill_intervals(h, cur, NOW, [])
    assert exact["end"] == T("2026-10-25T12:00") and exact["end_known"]


def test_an_end_rebuilt_across_an_offline_spell_is_a_range():
    h = hist(("A", 1, "2026-10-25T10:00", "2026-10-25T10:00", None, "2026-10-25T10:50"),
             ("A", -1, "2026-10-25T11:00", "2026-10-25T10:00", None, "2026-10-25T13:00"),
             ("A", 0, "2026-10-25T13:10", None, None, "2026-10-25T21:30"))
    [s] = replay.spill_intervals(h, {"status": 0, "status_start": "2026-10-25T13:10Z"}, NOW, [])
    assert s["end"] is None and (s["end_after"], s["end_by"]) == (T("2026-10-25T10:50"), T("2026-10-25T13:10"))
    out = replay._spill_out(s, 1.0, NOW)
    assert out["end_after"] == "2026-10-25T10:50Z" and out["end_by"] == "2026-10-25T13:10Z" and out["end"] is None


def test_a_spill_never_closed_keeps_the_last_poll_that_saw_it():
    h = hist(("A", 1, "2026-10-25T06:00", "2026-10-25T06:00", None, "2026-10-25T07:40"),
             ("A", -1, "2026-10-25T08:00", "2026-10-25T06:00", None, "2026-10-25T21:30"))
    [s] = replay.spill_intervals(h, {"status": -1, "status_start": "2026-10-25T08:00Z"}, NOW, [])
    assert s["end_after"] == T("2026-10-25T07:40") and s["end_by"] is None


def test_write_replays_writes_beside_the_spot_files_changes_no_result_and_asks_nothing(tmp_path, monkeypatch):
    import httpx

    from dipcast.ingest import rainfall
    def no(*a, **k):
        raise AssertionError("the replay made a request")
    monkeypatch.setattr(httpx, "get", no)
    monkeypatch.setattr(httpx, "Client", no)
    monkeypatch.setattr(rainfall, "fetch_forecast", no)
    monkeypatch.setattr(rainfall, "_request", no)
    results = [{"id": "a-1", "name": "A"}, {"id": "bad id", "name": "B"}, {"id": "c", "error": "forecast failed"}]
    before = json.dumps(results)
    h = hist(("S1", 0, "2026-10-25T03:00", "2026-10-25T01:00", "2026-10-25T03:00", "2026-10-25T21:30"))
    out = replay.write_replays(tmp_path, results, {"a-1": [contributor(1)]}, NOW, history=h, rain_cache=tmp_path / "none")
    assert out["written"] == 1 and out["largest"] == "a-1"
    assert json.dumps(results) == before   # spots.json and the lite file are written from these: unchanged
    files = sorted(p.name for p in (tmp_path / "data" / "spot").iterdir())
    assert files == ["a-1-replay.json"]
    doc = json.loads((tmp_path / "data" / "spot" / "a-1-replay.json").read_text())
    assert doc["overflows"][0]["spills"][0]["end_known"] is True and "generated_at" in doc


def test_spots_json_budget_is_untouched_by_the_replay():
    # The replay is its own file a spot, asked for only with ?replay=1: no replay field reaches spots.json,
    # spots-lite.json or data/spot/<id>.json (build_site.DETAIL_FIELDS, write_app_data).
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_site as bs
    assert not any("replay" in f for f in bs.DETAIL_FIELDS)
    doc = {"generated_at": "x", "spots": [{"id": "a", "contributors": [contributor(1)]}]}
    lite = json.dumps(doc)
    replay.spot_replay(doc["spots"][0], doc["spots"][0]["contributors"], None, NOW)
    assert json.dumps(doc) == lite


@pytest.mark.parametrize("bad", [None, pd.DataFrame(columns=["site_id"])])
def test_no_history_at_all_lists_nothing_as_spilling(bad):
    r = replay.spot_replay({"id": "x"}, [contributor(1), contributor(2, status=1, status_start="2026-10-25T21:00Z")], bad, NOW)
    [o] = r["overflows"]   # this build's poll still says S2 is discharging
    assert o["site_id"] == "S2" and o["spills"][0]["running"] and o["history"] == "none"
    assert r["quiet"] == {"no_history": {"n": 1, "weight": 0.45}}   # S1: quiet, but with no history that proves nothing
    if bad is None:
        assert r["history"] == {"unavailable": "no poll history in this build's state"}


def test_a_last_sighting_after_a_newer_start_is_held_to_that_start():
    # A feed still giving the old start at a poll after a new spill began (YWS00893, 25 Oct 2026).
    h = hist(("A", 1, "2026-10-24T14:42", "2026-10-24T14:42", None, "2026-10-25T19:44"),
             ("A", 1, "2026-10-25T19:25", "2026-10-25T19:25", None, "2026-10-25T21:30"))
    cur = {"status": 1, "status_start": "2026-10-25T19:25Z", "latest_event_start": "2026-10-25T19:25Z"}
    first, run = replay.spill_intervals(h, cur, NOW, [])
    assert first["end_after"] == T("2026-10-25T19:25") and first["end_by"] is None and run["running"]


def test_a_replay_failure_is_a_build_health_warning_not_a_failed_build(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_site as bs
    said = []
    monkeypatch.setattr(bs, "announce", said.append)

    def broken(*a, **k):
        raise OSError("disk full")
    when = pd.Timestamp("2026-10-25T23:49", tz="Europe/London")
    out = bs.replay_files(tmp_path, [], {}, when, write=broken)
    assert out == {"written": 0, "warning": "catchment replay not written: disk full"} and said == [out["warning"]]
    ok = bs.replay_files(tmp_path, [], {}, when, write=lambda *a: {"written": 3, "largest": "x", "largest_bytes": 900})
    assert ok["written"] == 3 and said == [out["warning"]]


def test_the_history_is_grouped_once_with_only_the_sites_counted():
    h = hist(("A", 0, "2026-10-25T03:00", None, None, "2026-10-25T21:30"),
             ("B", 0, "2026-10-25T03:00", None, None, "2026-10-25T21:30"),
             ("A", 1, "2026-10-25T05:00", None, None, "2026-10-25T21:30"))
    g = replay.group_history(h, {"A"})
    assert list(g) == ["A"] and len(g["A"]) == 2
    assert replay.group_history(None) == {} and replay.group_history(h)["B"][0]["status"] == 0
    # spot_replay takes the table or the grouped rows and gives the same result.
    ups = [contributor(1, site_id="A")]
    assert replay.spot_replay({"id": "x"}, ups, h, NOW) == replay.spot_replay({"id": "x"}, ups, replay.group_history(h), NOW)
