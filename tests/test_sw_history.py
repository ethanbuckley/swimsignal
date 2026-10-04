"""Scottish Water's overflow event workbooks read into edm_events rows (sw_history.py), on rows cut
from the August 2026 files (tests/fixtures/scottish_water). Contains Scottish Water data licensed
under the Open Government Licence v3.0."""

from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd
import pytest

from dipcast.ingest import sw_history as sw
from dipcast.ingest.edm_events import COLS

pytest.importorskip("openpyxl")

FIX = Path(__file__).parent / "fixtures" / "scottish_water"
REP, NON = "Scottish Water reported 2021-2025", "Scottish Water non-reported 2022-2025"


@pytest.fixture(scope="module")
def loaded():
    return sw.load({REP: FIX / "reported.xlsx", NON: FIX / "non_reported.xlsx"})


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def test_cells_in_every_form_the_sheets_use():
    assert sw.clock_time(datetime(2025, 6, 7, 12, 20, 0, 999_000))  # noqa: DTZ001 == pd.Timestamp("2025-06-07 12:20:01")
    assert sw.clock_time(45815.51388888889) == pd.Timestamp("2025-06-07 12:20:00")
    assert sw.clock_time("25/05/2025 02:06:15") == pd.Timestamp("2025-05-25 02:06:15")
    assert sw.clock_time("03/01/2023 18:45") == pd.Timestamp("2023-01-03 18:45:00")
    assert all(pd.isna(sw.clock_time(v)) for v in ("No Events", "No Data Available", None, ""))
    assert sw.duration_s(timedelta(hours=40, minutes=48)) == 146880
    assert sw.duration_s(time(0, 15)) == 900
    assert sw.duration_s(datetime(1899, 12, 31, 16, 48)) == 146880  # noqa: DTZ001  1.7 days read as a date
    assert sw.duration_s(0.010416666664241347) == 900
    assert sw.duration_s("58:26:02") == 210362
    assert pd.isna(sw.duration_s("No Data Available"))
    assert sw.point_key("Ellon WWTW CSO event") == sw.point_key("Ellon WWTW CSO Event") == "ellon wwtw cso"
    assert sw.point_key("Greenock, No.5 (Campbell St) CSO Event") == sw.point_key("Greenock No5 (Campbell St) CSO event")


def test_one_row_per_event_in_the_edm_events_columns(loaded):
    ev, _, _ = loaded
    assert list(ev.columns[:len(COLS)]) == COLS
    assert ev.groupby("source").size().to_dict() == {REP: 19, NON: 6}
    assert str(ev["event_start"].dt.tz) == "UTC"


def test_old_works_ids_become_the_overflows_current_id(loaded):
    ev, _, _ = loaded
    ellon = ev[ev["site_name"].str.lower() == "ellon wwtw cso event"]
    assert set(ellon["site_id"]) == {"CSO006851"}
    assert set(ellon["asset_id_published"]) == {"STW001545", "CSO006851"}
    assert sorted(ellon["year"].unique()) == [2021, 2023, 2024, 2025]
    lincluden = ev[ev["asset_id_published"] == "STW000468"]
    assert lincluden["site_id"].tolist() == ["CSO007138"]         # found in the summary by its point name
    assert (round(lincluden["lat"].iloc[0], 3), round(lincluden["lon"].iloc[0], 3)) == (55.086, -3.626)
    # Not in either summary: keeps its published id and has no position.
    fort = ev[ev["site_id"] == "STW001638"]
    assert len(fort) == 2 and fort["lat"].isna().all()


def test_clock_time_is_europe_london_and_durations_are_the_published_ones(loaded):
    ev, _, _ = loaded
    by = ev.set_index(["site_id", "event_start"])
    # Text date in summer: 02:06:15 BST.
    assert (sw.london_to_utc(pd.Series([pd.Timestamp("2025-05-25 02:06:15")]))[0]) == utc("2025-05-25 01:06:15")
    assert ("CSO006855", utc("2025-05-25 01:06:15")) in by.index
    # Winter: clock time is UTC.
    assert ("CSO001640", utc("2024-12-31 09:40")) in by.index
    # Inside the missing hour of 31 March 2024: read as GMT, end follows the start.
    erskine = ev[ev["site_id"] == "CSO007524"].sort_values("event_start")
    assert erskine["event_start"].tolist() == [utc("2024-03-31 01:20"), utc("2024-03-31 01:56")]
    assert erskine["event_end"].tolist() == [utc("2024-03-31 01:38"), utc("2024-03-31 02:13")]
    # The repeated hour of 29 October 2023: read as BST. The 35 h 46 min run keeps its published length.
    hel = ev[ev["site_id"] == "CSO007529"].iloc[0]
    assert hel["event_start"] == utc("2023-10-29 00:00")
    assert abs(hel["duration_h"] - hel["duration_published_h"]) < 0.01
    timed = ev[ev["event_end"].notna()]
    assert ((timed["duration_h"] - timed["duration_published_h"]).abs() < 0.05).all()


def test_day_records_keep_the_day_and_no_time(loaded):
    ev, yr, _ = loaded
    fort = ev[ev["site_id"] == "STW001638"].sort_values("event_start")
    assert fort["event_start"].tolist() == [utc("2022-01-01"), utc("2022-01-02")]
    assert fort["event_end"].isna().all() and fort["duration_h"].isna().all()
    row = yr[(yr["site_id"] == "STW001638") & (yr["year"] == 2022)].iloc[0]
    assert (row["events"], row["day_records"]) == (2, 2)


def test_yearly_counts_with_the_12_24_rule_and_keeps_empty_years(loaded):
    _, yr, _ = loaded
    y = yr.set_index(["site_id", "year"])
    # Five events in 2023, three of them over 12 hours: 8 spills (worked by hand).
    assert (y.loc[("CSO006851", 2023), "events"], y.loc[("CSO006851", 2023), "spills_12_24"]) == (5, 8)
    assert y.loc[("CSO006851", 2023), "days_data"] == 339
    assert y.loc[("CSO007529", 2023), "spills_12_24"] == 2              # one 35.8 h run
    airdrie = y.loc["CSO005882"]
    assert airdrie["status"].to_dict() == {2021: "no events", 2022: "no events", 2023: "no data",
                                           2024: "no data", 2025: "no events"}
    assert airdrie.loc[2025, "events"] == 0 and pd.isna(airdrie.loc[2024, "events"])


def test_12_24_rule_by_cases():
    h = lambda x: pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(hours=x)
    count = lambda *iv: sw.count_12_24([h(a) for a, _ in iv], [h(b) for _, b in iv])
    assert count() == 0
    assert count((0, 1)) == 1
    assert count((0, 1), (11, 11.5)) == 1           # both in the first 12 hours
    assert count((0, 1), (20, 21)) == 2             # the next 24-hour block
    assert count((0, 12)) == 1                      # ends as the block ends
    assert count((0, 30)) == 2
    assert count((0, 37)) == 3
    assert count((0, 1), (37, 38)) == 2             # an empty 24-hour block ends the run
    assert count((0, 1), (20, 21), (50, 51)) == 3   # 50 falls in the block 36-60: the run goes on
    assert count((0, 1), (61, 62)) == 2             # 12-36 empty: 61 opens a new run
    assert count((5, 6), (0, 1)) == 1               # order does not matter


def test_report_counts_short_events_and_api_matches(loaded):
    ev, yr, rows = loaded
    t = sw.report(ev, yr, rows, {"CSO006851", "CSO004465"}).set_index(["source", "year"])
    assert t.loc[(NON, 2025), "short_15m30s"] == 3            # three 15-minute events at George St
    assert t.loc[(REP, 2023), ["overflows", "events", "in_api", "published_in_api"]].tolist() == [2, 6, 1, 0]
    assert t.loc[(REP, 2022), "day_records"] == 2
    assert t.loc[(REP, 2021), "listed"] == 2
