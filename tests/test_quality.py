"""The data-quality page, quality.html (review task G12; src/dipcast/quality.py)."""
import re
import sys
from pathlib import Path

import pandas as pd

from dipcast import quality

ROOT = Path(__file__).resolve().parents[1]
MARK = "<svg></svg>"
CASES = pd.DataFrame([
    {"site_id": "SWS00971", "company": "Southern Water", "site_name": "EAST WORTHING CSO - 115407", "gap_m": "3513",
     "rw_live": "ENGLISH CHANNEL", "rw_ar": "ENGLISH CHANNEL", "outcome": "kept live: K3 contradicts",
     "reason": "evidence points to the outlet only"},
    {"site_id": "AWS01217", "company": "Anglian Water", "site_name": "Colchester-Mile END RD OV", "gap_m": "3512",
     "rw_live": "Tendring Streams", "rw_ar": "#N/A", "outcome": "settled: outlet",
     "reason": "evidence points to the outlet only"},
    {"site_id": "AWS00292", "company": "Anglian Water", "site_name": "CREATON HOSPITAL SM", "gap_m": "399",
     "rw_live": "Un-named trib River Nene", "rw_ar": "Un-named trib River Nene", "outcome": "open", "reason": "under 1 km apart"},
])
LIVE = pd.DataFrame({"lat": [50.81, 51.89384], "lon": [-0.33, 0.89496]}, index=["SWS00971", "AWS01217"])
OUTLETS = pd.DataFrame({"lat": [50.8, 51.92236, 52.3], "lon": [-0.35, 0.91581, -0.98]}, index=["SWS00971", "AWS01217", "AWS00292"])
OV = pd.DataFrame([
    {"site_id": "AWS01217", "company": "Anglian Water", "site_name": "Colchester-Mile END RD OV", "receiving_watercourse": "Salary Brook",
     "position_source": "annual return", "record_stale": False, "feed_updated_at": pd.NaT},
    {"site_id": "TWL00001", "company": "Thames Water", "site_name": None, "receiving_watercourse": "#N/A",
     "position_source": "live", "record_stale": False, "feed_updated_at": pd.NaT},
    {"site_id": "YWS00002", "company": "Yorkshire Water", "site_name": "ILKLEY CSO", "receiving_watercourse": "N/A",
     "position_source": "live", "record_stale": True, "feed_updated_at": pd.Timestamp("2026-10-18 09:15", tz="UTC")},
])


def text(h: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h.replace("&nbsp;", " ").replace("&#x27;", "'")))


def test_every_reason_in_the_cases_file_is_said_in_words():
    cases = quality.load_cases()
    assert len(cases) == 166
    for r in cases.itertuples():
        said = quality.reason_words(r.outcome, r.reason)
        assert said.startswith(("Open. ", "Settled: ")) and said.endswith("."), said
        assert r.reason in quality.REASONS or quality.DIFFERENT.fullmatch(r.reason), r.reason   # each in words
        assert "K3" not in said, said


def test_the_page_lists_each_case_with_both_positions_the_rule_and_a_tell_us_link():
    page = quality.site_page(CASES, LIVE, OUTLETS, OV, "20 Oct 2026, 06:39", MARK)
    t = text(page)
    assert "settled 1 of them, kept 1 at the live position because a check contradicted the move, and left 1 open" in t
    # Both positions, each a link to the map; an overflow missing from the live snapshot says so.
    assert 'href="https://www.openstreetmap.org/?mlat=51.89384&amp;mlon=0.89496#map=16/51.89384/0.89496">51.89384, 0.89496</a>' in page
    assert ">51.92236, 0.91581</a>" in page and ">50.81000, −0.33000</a>" in page
    assert "CREATON HOSPITAL SM" in t and "not in the latest records" in t
    # The rule applied, in words, and where today's forecast puts it (from this build's table).
    assert "Settled: the outlet. The names near the outlet match the overflow's records; those near the live position do not." in t
    assert "Today's forecast uses the outlet." in t
    assert "Open. The two are under 1 km apart" in t
    assert "Bathing-water features put a storm overflow at the live position".lower() in t.lower()
    # A placeholder water is "not named"; the Tell us link fills in the overflow's id.
    assert "Tendring Streams" in t and "not named" in t
    assert 'href="feedback.html?type=problem&amp;spot=Overflow+AWS01217+%28Colchester-Mile+END+RD+OV%29">Tell us</a>' in page
    # One fold per company, with its count of open cases.
    assert "Anglian Water: 2 overflows, 1 open" in t and "Southern Water: 1 overflow, 0 open" in t
    assert "{{" not in page and MARK in page


def test_the_names_and_frozen_lists_come_from_the_builds_table():
    t = text(quality.site_page(CASES, LIVE, OUTLETS, OV, "20 Oct 2026, 06:39", MARK))
    assert "1 overflow has no name: the live feeds give none, and no annual return lists one." in t
    assert "2 have no receiving water in either record" in t
    assert "Thames Water: 1" in t and "TWL00001" in t
    # The frozen record, with its own last stamp in UK time, and not the two that are current.
    frozen = t[t.index("Records without a current time"):]
    assert "ILKLEY CSO" in frozen and "YWS00002" in frozen and "18 Oct 2026, 10:15" in frozen
    assert "TWL00001" not in frozen and "AWS01217" not in frozen and "Yorkshire Water: 1" in frozen
    assert "the build of 20 Oct 2026, 06:39" in t


def test_without_the_overflow_table_the_lists_say_so():
    t = text(quality.site_page(CASES, LIVE, OUTLETS, None, "20 Oct 2026, 06:39", MARK))
    assert t.count("This build had no overflow table") == 3
    assert "Today's forecast uses" not in t


def test_the_build_writes_the_page_lists_it_and_about_links_it(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site as bs
    live = tmp_path / "live.parquet"
    pd.DataFrame({"site_id": ["AWS01217"], "lat": [51.89384], "lon": [0.89496]}).to_parquet(live)
    bs.write_quality_page(tmp_path, OV, pd.Timestamp("2026-10-20 05:39", tz="UTC"), live=live)
    page = (tmp_path / "quality.html").read_text()
    assert "<title>Overflow records to check · SwimSignal</title>" in page and "the build of 20 Oct 2026, 06:39" in text(page)
    assert "51.89384, 0.89496" in page
    assert f"{'https://example.org/'}quality.html" in bs.sitemap("https://example.org/", [], "2026-10-20")
    assert 'href="quality.html">Overflow records to check</a>' in (ROOT / "src/dipcast/pages/about.html").read_text()


# ------------------------------------------------------------------ the long_run list (monitor_anomalies.long_runs)
POLL = pd.Timestamp("2026-10-24 09:41", tz="UTC")


def _live(sid, company, status, since, name=None, water=None):
    return {"site_id": sid, "company": company, "site_name": name, "receiving_watercourse": water, "status": status,
            "status_start": pd.Timestamp(since, tz="UTC"), "latest_event_start": pd.Timestamp(since, tz="UTC"),
            "latest_event_end": pd.NaT, "last_updated": POLL, "fetched_at": POLL}


LIVE_OV = pd.DataFrame([
    _live("YWS00425", "Yorkshire Water", 1, "2026-09-02 09:00", "BRECKSFIELD/NO 2 CSO", "Burtree Dam"),   # 52 days, 12.75 h on record
    _live("YWS02029", "Yorkshire Water", 1, "2026-10-12 09:00", "WAINGATE/CSO", "River Don"),        # 12 days, none on record
    _live("UUP00274", "United Utilities", 1, "2026-10-07 09:00", None, "#N/A"),                      # no name, no water
    _live("UUP01780", "United Utilities", 1, "2026-10-12 09:00", "REAL LONG SPILL"),                 # 12 days, 28 on record
    _live("SWS00001", "Southern Water", 1, "2026-10-21 09:00", "THREE DAYS"),                        # under a week
    _live("SWS00002", "Southern Water", 0, "2026-09-01 09:00", "QUIET"),                             # not discharging
])
LONGEST = pd.Series({"YWS00425": 12.75, "UUP00274": 0.7136, "UUP01780": 672.4, "SWS00001": 1.0})


def page_with(ov=LIVE_OV, longest=LONGEST, as_of=POLL + pd.Timedelta(hours=1)):
    return quality.site_page(CASES, LIVE, OUTLETS, ov, "24 Oct 2026, 10:41", MARK, longest=longest, as_of=as_of)


def long_list(page: str) -> str:
    return page[page.index('<section id="long-runs"'):page.index("</section>", page.index('<section id="long-runs"'))]


def test_the_long_run_list_names_each_flagged_monitor_and_asks_the_company():
    sec = long_list(page_with())
    t = text(sec)
    assert "Monitors reporting a spill far longer than any on record" in t
    assert "for more than 7 days, and for more than twice as long as the overflow's longest spill" in t
    main = sec[:sec.index('id="long-runs-no-record"')]
    # The comparative list: the long one and the unnamed one, each with a longest spill on record. Not the real long
    # spill, the one under a week or the one not discharging; and not the one with no spill on record (its own group).
    for sid in ("YWS00425", "UUP00274"):
        assert sid in main
    for sid in ("UUP01780", "SWS00001", "SWS00002", "YWS02029"):
        assert sid not in main
    assert "BRECKSFIELD/NO 2 CSO" in t and "Burtree Dam" in t and "52 days since 2 Sep 2026, 10:00" in t and "12.8 hours" in t
    assert "43 minutes" in t and "not named" in t
    # The question goes to the feedback form with the overflow's id (and its name where it has one).
    assert ('href="feedback.html?type=problem&amp;spot=Overflow+YWS00425+%28BRECKSFIELD%2FNO+2+CSO%29">'
            "Is this monitor still reporting correctly?</a>") in sec
    assert 'href="feedback.html?type=problem&amp;spot=Overflow+UUP00274">Is this monitor still reporting correctly?</a>' in sec
    # By company, then the longest run first.
    assert main.index("UUP00274") < main.index("YWS00425")
    assert "this list changes nothing on the site" in t and "{{" not in page_with()


def test_a_monitor_with_no_spill_on_record_is_in_its_own_group_that_compares_nothing():
    sec = long_list(page_with())
    rest = sec[sec.index('id="long-runs-no-record"'):]
    t = text(rest)
    assert "Monitors reporting one spill for more than 7 days, with no Environment Agency record to compare against" in t
    assert "nothing to compare these spills with" in t and "nothing here says the spill is unusual" in t
    assert "YWS02029" in rest and "WAINGATE/CSO" in t and "12 days since" in t
    assert "Longest on record" not in rest and "none in the records" not in t
    for sid in ("YWS00425", "UUP00274"):
        assert sid not in rest
    # Without such a monitor the group is left out.
    assert 'id="long-runs-no-record"' not in long_list(page_with(LIVE_OV[LIVE_OV["site_id"] != "YWS02029"]))


def test_the_long_run_words_ask_and_never_accuse():
    for page in (page_with(), page_with(longest=None), page_with(ov=None), page_with(ov=OV),
                 page_with(as_of=POLL + pd.Timedelta(hours=7))):
        t = text(long_list(page)).lower()
        for word in ("stuck", "broken", "faulty", "failing", "fault"):
            assert word not in t, word
    assert "whether its monitor is still reporting correctly" in text(long_list(page_with()))


def test_the_long_run_list_never_changes_its_inputs():
    ov, lg = LIVE_OV.copy(), LONGEST.copy()
    page_with(ov, lg)
    pd.testing.assert_frame_equal(ov, LIVE_OV)
    pd.testing.assert_series_equal(lg, LONGEST)


def test_the_long_run_list_escapes_the_feeds_text():
    ov = pd.DataFrame([_live("YWS00425", "Yorkshire & <b>Water</b>", 1, "2026-09-02 09:00",
                             'CSO <script>alert("x")</script>', "Beck <i>&</i> Dam")])
    sec = long_list(page_with(ov))
    assert "<script>" not in sec and "<b>" not in sec and "<i>" not in sec
    assert "CSO &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in sec and "Yorkshire &amp; &lt;b&gt;Water&lt;/b&gt;" in sec
    assert "Beck &lt;i&gt;&amp;&lt;/i&gt; Dam" in sec


def test_the_long_run_list_when_empty_or_without_its_inputs():
    quiet = LIVE_OV[LIVE_OV["site_id"].isin(["UUP01780", "SWS00001", "SWS00002"])]
    assert "None in this build." in text(long_list(page_with(quiet)))
    assert "None in this build." in text(long_list(page_with(LIVE_OV.iloc[0:0])))
    # Could not be checked is never "None": no record of longest spills, no table, no live columns.
    for page, why in ((page_with(longest=None), "The comparison with past spills could not be made in this build, because "
                                                "the record of past spill lengths was not available."),
                      (page_with(ov=None), "This build had no overflow table, so this list could not be checked."),
                      (page_with(ov=OV), "had no live statuses, so this list could not be checked.")):
        t = text(long_list(page))
        assert why in t and "None in this build" not in t and "This is not a finding" in t
    # No file names or internal names on the page.
    for page in (page_with(longest=None), page_with()):
        sec = long_list(page)
        assert "parquet" not in sec and "data/processed" not in sec and "long_run" not in text(sec)


def test_live_readings_older_than_the_build_leave_the_list_unchecked():
    late = page_with(as_of=POLL + pd.Timedelta(hours=7))
    t = text(long_list(late))
    assert "more than 6 hours older than the build, so this list could not be checked" in t
    assert "YWS00425" not in long_list(late) and "None in this build" not in t
    assert "YWS00425" in long_list(page_with(as_of=POLL + pd.Timedelta(hours=5)))


def test_a_monitor_whose_reading_is_not_current_is_counted_not_listed_or_cleared():
    # The build's table carries data_state (ingest.live.data_states); one record stale, say frozen in a current feed.
    ov = LIVE_OV.assign(data_state="live")
    ov.loc[ov["site_id"].eq("YWS00425"), "data_state"] = "stale"
    sec = long_list(page_with(ov))
    t = text(sec)
    assert "YWS00425" not in sec and "UUP00274" in sec
    assert "1 more monitor has reported a spill this long, but its reading was not current in this build" in t
    only = ov[ov["site_id"].isin(["YWS00425", "SWS00002"])]
    t = text(long_list(page_with(only)))
    assert "None in this build" not in t and "None among the monitors with a current reading." in t


def test_the_build_writes_the_long_run_list_and_carries_on_without_its_file(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site as bs
    live = tmp_path / "live.parquet"
    pd.DataFrame({"site_id": ["AWS01217"], "lat": [51.89384], "lon": [0.89496]}).to_parquet(live)
    ref = tmp_path / "longest_events.parquet"
    pd.DataFrame({"site_id": LONGEST.index, "longest_h": LONGEST.values, "n_events": 1}).to_parquet(ref)
    bs.write_quality_page(tmp_path, LIVE_OV, POLL, live=live, longest_events=ref)
    assert "YWS00425" in long_list((tmp_path / "quality.html").read_text())
    bs.write_quality_page(tmp_path, LIVE_OV, POLL, live=live, longest_events=tmp_path / "missing.parquet")
    page = (tmp_path / "quality.html").read_text()
    assert "could not be made in this build" in text(long_list(page)) and "YWS00425" not in long_list(page)


def test_the_build_s_monitor_checks_never_stop_it(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site as bs
    from dipcast import config
    monkeypatch.setattr(config, "state_read", lambda name: tmp_path / name)
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "dipcast.duckdb")
    warns, summary = bs.monitor_feed_checks(None)   # no state at all
    assert warns == [] and summary["checked"] == [] and len(summary["skipped"]) == 5
    (tmp_path / "live_latest.parquet").write_text("not a parquet file")
    warns, summary = bs.monitor_feed_checks(None)
    assert warns == [] and summary["skipped"]["future_time"] == "no live snapshot"
