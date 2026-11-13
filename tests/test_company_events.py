"""The companies' own 2025-26 event layers (ingest/company_events): Anglian Water's day/month repair, the read
check, the ledger's stop at a refusal and at its cap, and each layer's credit."""

import json

import httpx
import pandas as pd
import pytest

from dipcast import config
from dipcast.ingest import company_events, edm_events
from dipcast.ingest.company_events import LAYERS, Ledger, Refused, check_read, coverage, normalise, swap_day_month
from dipcast.ingest.edm_events import COLS


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def test_day_and_month_swapped_back_only_into_the_stated_month():
    t = pd.Series([utc("2026-01-03 05:00"),     # stored for 1 March: swapped
                   utc("2026-03-15 05:00"),     # already in March: kept
                   utc("2026-12-03 23:59"),     # 12 March: swapped
                   utc("2026-01-13 00:00"),     # day 13 cannot be a month: kept, still outside
                   utc("2026-02-04 00:00"),     # 2 April is not March: kept
                   pd.NaT])
    out, n = swap_day_month(t, ("2026-03", "2026-03"))
    assert n == 2
    assert out[0] == utc("2026-03-01 05:00")
    assert out[1] == utc("2026-03-15 05:00")
    assert out[2] == utc("2026-03-12 23:59")
    assert out[3] == utc("2026-01-13 00:00")
    assert out[4] == utc("2026-02-04 00:00")
    assert pd.isna(out[5])


def test_nothing_swapped_when_every_time_is_inside():
    t = pd.Series([utc("2026-04-01 02:23"), utc("2026-04-30 22:54")])
    out, n = swap_day_month(t, ("2026-04", "2026-04"))
    assert n == 0 and out.equals(t)


def test_an_anglian_layer_in_the_edm_events_columns(monkeypatch):
    monkeypatch.setattr(company_events, "_id_map", dict)
    ms = lambda s: int(utc(s).timestamp() * 1000)   # noqa: E731  (ArcGIS dates are epoch milliseconds)
    raw = pd.DataFrame({"FID": [1, 2, 3, 4, 5],
                        "SITE_CODE": ["AWS001", "AWS001", "AWS002", None, "AWS003"],
                        "START_DATE_TIME": [ms("2026-01-03 10:00"), ms("2026-03-20 10:00"), ms("2026-03-21 10:00"),
                                            ms("2026-03-22 10:00"), ms("2026-03-23 10:00")],
                        "END_DATE_TIME": [ms("2026-01-03 11:00"), ms("2026-03-20 10:30"), ms("2026-03-21 09:00"),
                                          ms("2026-03-22 11:00"), ms("2026-03-23 12:00")],
                        "Lat": [52.1, 52.1, 52.2, 52.3, 52.4], "Long": [0.1, 0.1, 0.2, 0.3, 0.4]})
    ev, notes = normalise(raw, "Anglian Water 2026-03")
    assert list(ev.columns) == COLS
    assert notes["swapped_start"] == 1 and notes["swapped_end"] == 1
    assert notes["no_id_or_start"] == 1                  # no site id
    assert notes["negative_or_over_60_days"] == 1        # AWS002 stops before it starts
    assert notes["kept"] == 3 and notes["start_outside_stated_months"] == 0
    first = ev[ev["site_id"] == "AWS001"].iloc[0]
    assert first["event_start"] == utc("2026-03-01 10:00") and first["duration_h"] == 1.0
    assert (ev["source"] == "Anglian Water 2026-03").all()


def test_repeated_rows_kept_once(monkeypatch):
    monkeypatch.setattr(company_events, "_id_map", dict)
    raw = pd.DataFrame({"OBJECTID": [1, 2], "SiteId": ["WSX1", "WSX1"], "SiteName": ["A", "A"],
                        "EventStart": [1767225600000, 1767225600000], "EventEnd": [1767229200000, 1767229200000],
                        "OutfallLatitude": [51.0, 51.0], "OutfallLongitude": [-2.0, -2.0],
                        "EventId": ["x", "y"], "EventVerified": [None, None]})
    ev, notes = normalise(raw, "Wessex Water 2026")
    assert len(ev) == 1 and notes["repeated"] == 1
    assert ev["event_start"].iloc[0] == utc("2026-01-01 00:00")


def test_the_read_must_match_the_layer():
    raw = pd.DataFrame({"FID": [1, 2, 3]})
    check_read(raw, "FID", 3, "x")
    with pytest.raises(RuntimeError):
        check_read(raw, "FID", 4, "x")                  # a row short
    with pytest.raises(RuntimeError):
        check_read(pd.DataFrame({"FID": [1, 1, 3]}), "FID", 3, "x")   # a repeated id


def _client(status, body):
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(status, json=body)))


def test_the_ledger_stops_at_a_refusal_and_logs_it(tmp_path):
    led = Ledger(tmp_path / "ledger.jsonl", cap=5, pace=0)
    assert led.get(_client(200, {"count": 3}), "https://x/query", {})["count"] == 3
    with pytest.raises(Refused):
        led.get(_client(403, {}), "https://x/query", {})
    with pytest.raises(Refused):
        led.get(_client(200, {"error": {"code": 400}}), "https://x/query", {})
    lines = [json.loads(s) for s in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert [r["status"] for r in lines] == [200, 403, 200]


def test_the_ledger_stops_at_its_cap(tmp_path):
    led = Ledger(tmp_path / "ledger.jsonl", cap=1, pace=0)
    led.get(_client(200, {}), "https://x/query", {})
    with pytest.raises(Refused):
        led.get(_client(200, {}), "https://x/query", {})
    assert led.sent == 1


def test_every_layer_is_credited_and_kept_out_of_training():
    for source, lay in LAYERS.items():
        assert "CC BY 4.0" in lay["credit"], source
        assert lay["company"] in source
        assert set(lay["fields"]) == {"site_id", "event_start", "event_end", "lat", "lon"}
        assert len(lay["item"]) == 32
    urls = {lay["url"] for lay in LAYERS.values()}
    assert not urls & set(config.EDM_EVENT_FEEDS.values())
    assert not urls & set(config.EDM_HISTORY_FEEDS.values())
    assert not set(LAYERS) & set(edm_events.HISTORY_COMPANY)


def test_coverage_counts_events_and_overflows_by_month():
    ev = pd.DataFrame({"company": ["A"] * 3, "site_id": ["1", "1", "2"],
                       "event_start": [utc("2026-01-31 23:00"), utc("2026-01-02"), utc("2026-02-01")]})
    t = coverage(ev)
    assert t.to_dict("records") == [{"company": "A", "month": "2026-01", "events": 2, "overflows": 1},
                                    {"company": "A", "month": "2026-02", "events": 1, "overflows": 1}]


def test_anglian_times_read_back_as_uk_wall_clock():
    t = pd.Series([utc("2026-04-30 23:00"), utc("2026-01-15 10:00")])
    out = company_events.london_wall_as_utc(t)
    assert out[0] == utc("2026-05-01 00:00")              # summer: stored an hour early
    assert out[1] == utc("2026-01-15 10:00")              # winter: unchanged


def test_a_swapped_summer_date_is_not_left_an_hour_out(monkeypatch):
    # "07/12/2025 00:27" read month-first is 12 July, summer time, so stored as 11 July 23:27 UTC.
    monkeypatch.setattr(company_events, "_id_map", dict)
    ms = int(utc("2025-07-11 23:27").timestamp() * 1000)
    raw = pd.DataFrame({"FID": [1], "SITE_CODE": ["AWS001"], "START_DATE_TIME": [ms], "END_DATE_TIME": [ms],
                        "Column_1": [52.0], "Column_2": [0.1]})
    ev, notes = normalise(raw, "Anglian Water 2025-12")
    assert ev["event_start"].iloc[0] == utc("2025-12-07 00:27")
    assert notes["start_outside_stated_months"] == 0
