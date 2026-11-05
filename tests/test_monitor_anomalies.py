"""The monitor anomaly flags (dipcast.monitor_anomalies) on hand-made frames: each rule fires on the failure it
is for, not on normal data, and not on a real long spill; every flag is "review"; no input is changed or loses a
row. docs/MONITOR-ANOMALIES-2026-10.md has the evaluation on saved polls."""

import json

import numpy as np
import pandas as pd

from dipcast import monitor_anomalies as ma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
POLL = T("2026-10-24 09:40")


def _rec(sid, company="United Utilities", status=0, since="2026-10-20 10:00", start="2026-10-20 08:00",
         end="2026-10-20 10:00", stamp="2026-10-24 09:35", fetched=POLL):
    return {"site_id": sid, "company": company, "status": status, "status_start": T(since) if since else pd.NaT,
            "latest_event_start": T(start) if start else pd.NaT, "latest_event_end": T(end) if end else pd.NaT,
            "last_updated": T(stamp) if stamp else pd.NaT, "fetched_at": fetched}


def _snap(rows):
    df = pd.DataFrame(rows)
    for c in ma.TIME_COLS + ["fetched_at"]:
        df[c] = pd.to_datetime(df[c], utc=True)
    return df


NORMAL = _snap([_rec("UUP1"), _rec("UUP2", status=1, since="2026-10-24 06:00", start="2026-10-24 06:00", end=None),
                _rec("UUP3", status=-1), _rec("YWS1", company="Yorkshire Water")])


def _only(flags, rule):
    assert set(flags["rule"]) <= {rule}
    assert (flags["severity"] == "review").all()
    return flags


def test_normal_snapshot_raises_nothing():
    before = NORMAL.copy()
    assert ma.implausible_times(NORMAL).empty
    assert ma.record_contradictions(NORMAL).empty
    assert ma.long_runs(NORMAL, pd.Series({"UUP2": 5.0})).empty
    pd.testing.assert_frame_equal(NORMAL, before)


def test_clock_skew_is_future_time():
    skew = NORMAL.copy()
    for c in ma.TIME_COLS:   # the company's times an hour ahead: local time labelled UTC
        skew[c] = skew[c] + pd.Timedelta(hours=1)
    f = _only(ma.implausible_times(skew), "future_time")
    assert set(f["site_id"]) == {"UUP1", "UUP2", "UUP3", "YWS1"}   # every record stamped within the hour
    assert json.loads(f["evidence"].iloc[0])["hours_ahead"] > 0.25
    assert len(skew) == len(NORMAL)


def test_seconds_for_milliseconds_is_time_format():
    bad = NORMAL.copy()
    yw = bad["company"] == "United Utilities"
    for c in ma.TIME_COLS:   # epoch seconds read as milliseconds: January 1970
        bad.loc[yw, c] = pd.to_datetime(bad.loc[yw, c].astype("int64") // 10**9 // 1000, unit="ms", utc=True)
    f = ma.implausible_times(bad)
    assert list(f["rule"]) == ["time_format"] and list(f["company"]) == ["United Utilities"]
    assert f["site_id"].isna().all()


def test_old_placeholder_times_on_a_few_records_are_not_a_format_change():
    snap = _snap([_rec(f"YWS{i}", company="Yorkshire Water") for i in range(10)])
    snap.loc[0, "status_start"] = T("2006-10-02")   # as YWS01660 in the 24 Oct 2026 snapshot
    assert ma.implausible_times(snap).empty


def test_feed_down_rows_are_not_judged_on_their_old_times():
    snap = NORMAL.assign(status=-3, last_updated=POLL + pd.Timedelta(hours=2))
    assert ma.implausible_times(snap).empty


def test_record_contradictions_each_kind():
    snap = _snap([
        _rec("A", start="2026-10-20 08:00", end="2026-10-19 08:00"),                         # start after end
        _rec("B", status=1, since="2026-10-20 08:00", start="2026-10-20 08:00", end="2026-10-20 09:00"),
        _rec("C", since="2026-10-20 10:00", start="2026-10-20 08:00", end=None),             # stopped, open event
        _rec("D", since="2025-12-18 14:00", start="2026-03-13 01:00", end="2026-03-13 01:30"),  # Anglian's kind
    ])
    f = _only(ma.record_contradictions(snap), "record_contradiction")
    kinds = {r.site_id: json.loads(r.evidence)["kind"] for r in f.itertuples()}
    assert kinds == {"A": "event_start_after_end", "B": "discharging_with_closed_event",
                     "C": "stopped_with_open_event", "D": "stopped_before_event_end"}


def test_stuck_discharging_is_a_long_run():
    snap = _snap([_rec("UUP00274", status=1, since="2026-10-08 11:03", start="2026-10-08 11:03", end=None)])
    f = _only(ma.long_runs(snap, pd.Series({"UUP00274": 0.7})), "long_run")
    assert list(f["site_id"]) == ["UUP00274"]
    assert f["first_seen"].iloc[0] == T("2026-10-15 11:03")   # a week after it started


def test_real_long_spill_is_not_a_long_run():
    # Running 12.5 days, at an overflow whose longest spill on record is 30 days (a groundwater-fed one).
    snap = _snap([_rec("SWS1", company="Southern Water", status=1, since="2026-10-11 21:00", start="2026-10-11 21:00", end=None)])
    assert ma.long_runs(snap, pd.Series({"SWS1": 720.0})).empty
    # Under a week, whatever its record.
    snap = _snap([_rec("SWS2", status=1, since="2026-10-19 09:00", start="2026-10-19 09:00", end=None)])
    assert ma.long_runs(snap, pd.Series({"SWS2": 0.5})).empty
    # No record at all: the week's floor alone.
    snap = _snap([_rec("NEW1", status=1, since="2026-10-10 09:00", start="2026-10-10 09:00", end=None)])
    assert list(ma.long_runs(snap)["site_id"]) == ["NEW1"]


# ------------------------------------------------------------------ quiet monitors
SITES = pd.DataFrame({"site_id": ["Q", "N1", "N2", "N3", "N4", "FAR"],
                      "lat": [54.0, 54.01, 54.0, 53.99, 54.0, 55.0], "lon": [-2.0, -2.0, -2.01, -2.0, -1.99, -2.0]})


def _days(start, n):
    return pd.date_range(start, periods=n, freq="D", tz="UTC")


def _known(ids, days):
    return pd.DataFrame([(s, d) for s in ids for d in days], columns=["site_id", "day"])


def _quiet_inputs(q_spills_live):
    nb = ma.neighbours_within(SITES)
    ids = list(SITES["site_id"])
    ref_days, live_days = _days("2025-01-01", 30), _days("2026-10-01", 20)
    storms_ref, storms_live = ref_days[::5], live_days[::4]   # 6 and 5 storm days
    ref_sp = pd.DataFrame([(s, d) for d in storms_ref for s in ["Q", "N1", "N2", "N3", "N4"]], columns=["site_id", "day"])
    live_sp = pd.DataFrame([(s, d) for d in storms_live for s in ["N1", "N2", "N3", "N4"]]
                           + [("Q", d) for d in q_spills_live], columns=["site_id", "day"])
    rates = ma.storm_rates(ma.storm_days(_known(ids, ref_days), ref_sp, nb))
    table = ma.storm_days(_known(ids, live_days), live_sp, nb)
    return table, rates, live_days, storms_live


def test_neighbours_within_five_km():
    nb = ma.neighbours_within(SITES)
    assert set(nb.loc[nb["site_id"] == "Q", "nb"]) == {"N1", "N2", "N3", "N4"}
    assert nb.loc[nb["site_id"] == "FAR"].empty


def test_monitor_silent_through_neighbour_storms_is_quiet():
    table, rates, _, storms = _quiet_inputs([])
    f = _only(ma.quiet_monitors(table, rates, pd.Series({"Q": "Yorkshire Water"})), "quiet_monitor")
    assert list(f["site_id"]) == ["Q"] and list(f["company"]) == ["Yorkshire Water"]
    ev = json.loads(f["evidence"].iloc[0])
    assert ev["storm_days"] == 5 and ev["ref_spilled_on"] == 6
    assert f["first_seen"].iloc[0] == storms[3]   # the fourth storm day: QUIET_MIN_DAYS


def test_monitor_that_spilled_once_is_not_quiet():
    table, rates, _, storms = _quiet_inputs([_days("2026-10-01", 20)[::4][2]])
    assert ma.quiet_monitors(table, rates).empty


def test_real_long_spill_is_not_quiet():
    # A spill running through the whole window marks every day, the storm days included.
    table, rates, _, _ = _quiet_inputs(list(_days("2026-10-01", 20)))
    assert ma.quiet_monitors(table, rates).empty


def test_storm_days_keeps_every_known_day():
    table, *_ = _quiet_inputs([])
    assert len(table) == 6 * 20


# ------------------------------------------------------------------ company freezes
def _history(company, times):
    return pd.DataFrame({"site_id": [f"S{i}" for i in range(len(times))], "company": company, "status": 0,
                         "status_start": pd.to_datetime(times, utc=True), "latest_event_start": pd.NaT,
                         "latest_event_end": pd.NaT, "fetched_at": T("2026-10-25 12:00")})


WET = pd.DataFrame({"company": ["Wessex Water"] * 2, "day": ["2026-10-20", "2026-10-21"],
                    "n_overflows": [200, 200], "wet_share": [0.8, 0.05]})


def test_feed_frozen_through_rain_is_a_company_freeze():
    hist = _history("Wessex Water", ["2026-10-19 10:00"])   # nothing changes from the 19th on
    f = _only(ma.company_freezes(ma.change_times(hist), WET), "company_freeze")
    assert list(json.loads(e)["day"] for e in f["evidence"]) == ["2026-10-20"]   # the wet day, not the dry one
    assert f["first_seen"].iloc[0] == T("2026-10-19 23:00")   # local midnight, BST


def test_wet_day_with_changes_is_not_a_freeze():
    hist = _history("Wessex Water", pd.date_range("2026-10-20 01:00", periods=40, freq="30min"))
    assert ma.company_freezes(ma.change_times(hist), WET).empty


def test_change_times_use_event_times_where_status_start_is_empty():
    hist = _history("Wessex Water", [None]).assign(latest_event_start=T("2026-10-20 05:00"), latest_event_end=T("2026-10-20 06:00"))
    assert len(ma.change_times(hist)) == 2


def test_wet_days_share():
    rain = pd.DataFrame({"site_id": ["A", "B", "C", "D"], "day": ["2026-10-20"] * 4, "rain_mm": [6, 9, 1, np.nan]})
    w = ma.wet_days(rain, pd.Series({"A": "X", "B": "X", "C": "X", "D": "X"}))
    assert w.loc[0, "n_overflows"] == 3 and abs(w.loc[0, "wet_share"] - 2 / 3) < 1e-9


# ------------------------------------------------------------------ poll log
def _poll_log(company, shares, rows=1000, ages=None):
    t = pd.date_range("2026-10-01", periods=len(shares), freq="2h", tz="UTC")
    return pd.DataFrame({"fetched_at": t, "company": company, "n_rows": rows,
                         "n_known": (np.asarray(shares) * rows).round().astype(int),
                         "feed_age_h": ages if ages is not None else 0.2})


def test_status_field_recoded_is_a_known_share_drop():
    # Every status unreadable, so every monitor -1: the share of known statuses falls to 0.
    pl = _poll_log("Thames Water", [0.95, 0.94, 0.95, 0.96, 0.95, 0.95, 0.0, 0.0])
    f = _only(ma.known_share_drops(pl), "known_share_drop")
    assert len(f) == 2 and f["first_seen"].iloc[0] == pl["fetched_at"].iloc[6]


def test_normal_share_noise_and_outages_are_not_drops():
    pl = _poll_log("Thames Water", [0.95, 0.94, 0.915, 0.96, 0.95, 0.93, 0.92, 0.95])   # the real range: 0.914-0.962
    pl.loc[3, ["n_rows", "n_known"]] = 0   # a feed outage: handled by FEED_DOWN
    assert ma.known_share_drops(pl).empty


def test_slower_refresh_is_a_cadence_change():
    ages = [0.2] * 25 + [3.0] * 5
    pl = pd.concat([_poll_log("Wessex Water", [0.99] * 30, ages=ages), _poll_log("Southern Water", [0.99] * 30, ages=ages)])
    f = _only(ma.cadence_changes(pl, {"Wessex Water"}), "cadence_change")
    assert set(f["company"]) == {"Wessex Water"}   # Southern stamps on change: its age is not a cadence


def test_steady_refresh_is_not_a_cadence_change():
    pl = _poll_log("Wessex Water", [0.99] * 40, ages=np.tile([0.05, 0.08, 0.04, 0.18], 10))
    assert ma.cadence_changes(pl, {"Wessex Water"}).empty


def test_new_id_scheme_is_id_turnover():
    prev = pd.DataFrame({"site_id": [f"WSX{i:05d}" for i in range(100)], "company": "Wessex Water", "fetched_at": POLL})
    cur = prev.assign(site_id=[f"WXW{i:05d}" for i in range(100)])
    f = _only(ma.id_turnover(prev, cur), "id_turnover")
    assert json.loads(f["evidence"].iloc[0])["share_new"] == 1.0


def test_short_read_and_same_ids_are_not_turnover():
    prev = pd.DataFrame({"site_id": [f"YWS{i:05d}" for i in range(100)], "company": "Yorkshire Water", "fetched_at": POLL})
    assert ma.id_turnover(prev, prev.copy()).empty
    assert ma.id_turnover(prev, prev.iloc[:46]).empty            # 1,000 of 2,179: a short read, handled already
    assert ma.id_turnover(prev, prev.iloc[:0]).empty             # feed down


def test_first_seen_only_keeps_earliest():
    pl = _poll_log("Thames Water", [0.95] * 6 + [0.0] * 3)
    f = ma.first_seen_only(ma.known_share_drops(pl))
    assert len(f) == 1 and f["first_seen"].iloc[0] == pl["fetched_at"].iloc[6]


def test_no_rule_changes_or_drops_its_input():
    snap = _snap([_rec("A", start="2026-10-20 08:00", end="2026-10-19 08:00"),
                  _rec("B", status=1, since="2026-09-01 09:00", start="2026-09-01 09:00", end=None, stamp="2026-10-24 10:30")])
    pl = _poll_log("Thames Water", [0.95] * 6 + [0.0] * 3, ages=[0.1] * 6 + [9.0] * 3)
    copies = (snap.copy(), pl.copy())
    flags = pd.concat([ma.implausible_times(snap), ma.record_contradictions(snap), ma.long_runs(snap),
                       ma.known_share_drops(pl), ma.cadence_changes(pl, {"Thames Water"})])
    assert len(flags) >= 4 and (flags["severity"] == "review").all()
    assert list(flags.columns) == ma.FLAG_COLS
    pd.testing.assert_frame_equal(snap, copies[0])
    pd.testing.assert_frame_equal(pl, copies[1])


def test_long_runs_with_nothing_discharging_is_empty():
    assert ma.long_runs(NORMAL.assign(status=0), pd.Series({"UUP1": 1.0})).empty
    assert ma.long_runs(NORMAL.iloc[0:0], pd.Series({"UUP1": 1.0})).empty


def test_longest_events_table():
    ev = pd.DataFrame({"site_id": ["B", "A", "A"], "event_start": pd.to_datetime(["2025-01-01 00:00"] * 3, utc=True),
                       "event_end": pd.to_datetime(["2025-01-01 02:00", "2025-01-01 01:00", "2025-01-02 00:00"], utc=True)})
    t = ma.longest_events_table(ev)
    assert list(t["site_id"]) == ["A", "B"] and list(t["longest_h"]) == [24.0, 2.0] and list(t["n_events"]) == [2, 1]


# ------------------------------------------------------------------ build warnings (feed_warnings)
# A normal world at POLL (24 Oct, 10:40 BST): Wessex's 20 overflows, a steady poll log, many status changes and
# rain at every overflow on the 23rd (the local day before), and the same ids on the 23rd as now.
W_IDS = [f"WXW{i:05d}" for i in range(20)]
W_SNAP = _snap([_rec(s, company="Wessex Water") for s in W_IDS])
W_POLLS = _poll_log("Wessex Water", [0.95] * 12).assign(fetched_at=pd.date_range(end=POLL, periods=12, freq="30min"))
W_HIST = pd.DataFrame({"site_id": W_IDS * 2, "company": "Wessex Water", "status": 0,
                       "status_start": pd.date_range("2026-10-23 00:30", periods=40, freq="30min", tz="UTC"),
                       "latest_event_start": pd.NaT, "latest_event_end": pd.NaT, "fetched_at": POLL})
W_RAIN = pd.DataFrame({"site_id": W_IDS, "day": "2026-10-23", "rain_mm": 12.0})
W_COV = pd.DataFrame({"site_id": W_IDS, "day": pd.Timestamp("2026-10-23")})


def _warn(snap=W_SNAP, pl=W_POLLS, hist=W_HIST, rain=W_RAIN, cov=W_COV):
    return ma.feed_warnings(snap, pl, hist, rain, cov)


def test_feed_warnings_quiet_on_normal_data():
    inputs = [x.copy() for x in (W_SNAP, W_POLLS, W_HIST, W_RAIN, W_COV)]
    w, s = _warn()
    assert w == [] and s["skipped"] == {}
    assert sorted(s["checked"]) == sorted(ma.FEED_RULES) and set(s["flags"].values()) == {0}
    for a, b in zip(inputs, (W_SNAP, W_POLLS, W_HIST, W_RAIN, W_COV)):
        pd.testing.assert_frame_equal(a, b)   # nothing changed


def test_feed_warnings_on_each_failure():
    ahead = W_SNAP.copy()
    for c in ma.TIME_COLS:
        ahead[c] = ahead[c] + pd.Timedelta(hours=1)   # local time labelled UTC
    w, _ = _warn(snap=ahead)
    assert len(w) == 1 and w[0].startswith("monitor check (future_time): 20 Wessex Water records carry a time up to")
    assert "WXW00000, WXW00001, WXW00002, WXW00003, WXW00004 and 15 more" in w[0]

    ms = W_SNAP.copy()
    for c in ma.TIME_COLS:   # epoch seconds read as milliseconds
        ms[c] = pd.to_datetime(ms[c].astype("int64") // 10**9 // 1000, unit="ms", utc=True)
    w, _ = _warn(snap=ms)
    assert [x.split(":")[0] for x in w] == ["monitor check (time_format)"] and "100% of Wessex Water's 20 records" in w[0]

    pl = W_POLLS.copy()
    pl.loc[pl.index[-1], "n_known"] = 0   # the status field recoded at the latest poll
    w, _ = _warn(pl=pl)
    assert len(w) == 1 and w[0].startswith("monitor check (known_share_drop): Wessex Water's share") and "fell to 0.00" in w[0]

    still = W_HIST.assign(status_start=T("2026-10-20 08:00"))   # no status change on the wet 23rd
    w, _ = _warn(hist=still)
    assert len(w) == 1 and w[0].startswith("monitor check (company_freeze): Wessex Water's feed recorded 0 status changes on 2026-10-23")

    renamed = W_SNAP.assign(site_id=[f"WSX{i:05d}" for i in range(20)])
    w, _ = _warn(snap=renamed, hist=pd.concat([W_HIST, renamed[W_HIST.columns]]))
    assert len(w) == 1 and w[0].startswith("monitor check (id_turnover): Wessex Water has 20 overflow ids now and had 20 on 2026-10-23")


def test_feed_warnings_report_only_what_holds_now():
    pl = W_POLLS.copy()
    pl.loc[pl.index[-3], "n_known"] = 0   # a drop two polls ago that has since recovered
    assert _warn(pl=pl)[0] == []
    dry = W_RAIN.assign(rain_mm=0.5)   # a quiet feed on a dry day says nothing
    assert _warn(hist=W_HIST.assign(status_start=T("2026-10-20 08:00")), rain=dry)[0] == []


def test_feed_warnings_skip_missing_inputs_without_error():
    w, s = ma.feed_warnings(None)
    assert w == [] and s["checked"] == [] and set(s["skipped"]) == set(ma.FEED_RULES)
    w, s = ma.feed_warnings(W_SNAP, None, None, None, None)
    assert w == [] and sorted(s["checked"]) == ["future_time", "time_format"]
    assert s["skipped"]["company_freeze"] == "no live history or forecast rain"
