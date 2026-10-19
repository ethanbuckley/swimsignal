"""The other companies' Stream histories (config.EDM_HISTORY_FEEDS): Northumbrian Water's "dd/mm/yyyy hh:mm"
text times, read as GMT all year, and its layer's field names mapped to the edm_events columns."""

import pandas as pd

from dipcast import config
from dipcast.ingest import edm_events
from dipcast.ingest.edm_events import (
    COLS,
    HISTORY_COMPANY,
    HISTORY_CREDITS,
    HISTORY_FIELDS,
    dmy_times,
    stream_times,
)


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def test_day_first_text_is_gmt_all_year():
    t = dmy_times(pd.Series(["17/10/2022 00:30", "01/07/2024 13:15", "31/12/2024 23:59",
                             "", None, "2024-01-01T00:00:00Z", "13/13/2024 10:00"]))
    assert t[0] == utc("2022-10-17 00:30")
    assert t[1] == utc("2024-07-01 13:15")   # a summer-time date: no hour taken off
    assert t[2] == utc("2024-12-31 23:59")
    assert t[3:].isna().all()
    assert str(t.dtype) == "datetime64[ns, UTC]"


def test_stream_times_picks_the_reader_by_the_column():
    text = stream_times(pd.Series(["02/03/2021 04:05", "03/03/2021 04:05"]))
    assert text[0] == utc("2021-03-02 04:05")          # day first, not 3 February
    epoch = stream_times(pd.Series([1737630761000, 1737631081000]))
    assert epoch[0] == utc("2025-01-23 11:12:41")
    iso = stream_times(pd.Series(["2025-01-23T11:12:41Z"]))
    assert iso[0] == utc("2025-01-23 11:12:41")


def test_a_northumbrian_row_in_the_edm_events_columns(monkeypatch):
    monkeypatch.setattr(edm_events, "_id_map", dict)
    raw = pd.DataFrame({"ObjectId": [1, 2, 3], "Monitor_Unique_ID": ["NWL00002", "NWL00002", "NWL00003"],
                        "Outfall_Latitude": [54.98, 54.98, 55.0], "Outfall_Longitude": [-1.79, -1.79, -1.5],
                        "Event_start": ["17/10/2022 00:30", "20/10/2022 13:15", "not a time"],
                        "Event_end": ["17/10/2022 01:00", "20/10/2022 13:30", "20/10/2022 13:30"]})
    ev = edm_events._normalise(raw, "Northumbrian Water 2020-2024")
    assert list(ev.columns) == COLS
    assert len(ev) == 2                                   # an unreadable start is dropped
    assert ev["site_name"].isna().all()                   # the layer has no site name
    assert ev["duration_h"].tolist() == [0.5, 0.25]
    assert ev["event_start"].iloc[1] == utc("2022-10-20 13:15")


def test_every_history_feed_has_fields_a_company_and_a_credit():
    feeds = set(config.EDM_HISTORY_FEEDS)
    assert feeds == set(HISTORY_FIELDS) == set(HISTORY_COMPANY) == set(HISTORY_CREDITS)
    assert not feeds & set(config.EDM_EVENT_FEEDS)        # never in edm_events.parquet
    assert all("CC BY 4.0" in c for c in HISTORY_CREDITS.values())


def _events(rows):
    return pd.DataFrame({"site_id": [r[0] for r in rows], "event_start": pd.to_datetime([r[1] for r in rows], utc=True, format="ISO8601")})


def test_the_crosswalk_needs_most_events_matched_both_ways():
    own = _events([("17385C", "2024-01-01 10:00:30"), ("17385C", "2024-01-02 11:00"), ("17385C", "2024-01-03 12:00"),
                   ("16192C", "2024-01-02 11:00:10")])     # one event, in the same minute as another site's
    ea = _events([("WXW00001", "2024-01-01 10:00"), ("WXW00001", "2024-01-02 11:00"), ("WXW00001", "2024-01-03 12:00"),
                  ("WXW00009", "2024-02-01 09:00")])
    cw = edm_events.crosswalk_by_events(own, ea).set_index("from_id")
    assert cw.loc["17385C", "to_id"] == "WXW00001" and cw.loc["17385C", "share"] == 1.0
    assert cw.loc["16192C", "share"] == 1.0 and cw.loc["16192C", "to_share"] == 1 / 3
    assert pd.isna(cw.loc["16192C", "to_id"])            # 1 of 1 one way, 1 of 3 the other
