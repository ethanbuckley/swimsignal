"""The archived 2017-2021 edition's layout read into sw_history rows (ingest/sw_archive.py), on a small workbook
built here in that layout: a summary without grid references, a 2017 sheet named with a trailing space and no
Scottish Water measurement point, and a 2018 sheet with one."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from dipcast.ingest import sw_archive, sw_history

openpyxl = pytest.importorskip("openpyxl")

SUMMARY_HEAD = ["Licence Number", "Asset ID", "Asset Name", "SEPA Measurement Point Description",
                "SW Unique Measurement Point Description", "Scottish Water Area", "Network or WWTW",
                "Type of Overflow CSO/SSSO/EO", "Bathing Season Spills Only Reporting?", "Asset Postcode",
                "Local Authority Area", "Licence Discharge Receiving Water", 2018, 2017]
HEAD_2017 = ["Licence Number", "Asset ID", "Site Name", "SEPA Measurement Point Description", "Area",
             "Networks or Treatment (WwTW)", "Start of Overflow Event", "End of Overflow Event",
             "Duration of Overflow Event\n[h]:mm:ss", "Volume discharged \nm3", "Comments"]
HEAD_2018 = ["Licence Number", "Asset ID", "Site Name", "SW Measurement Point Description",
             "SEPA Measurement Point Description", "Area", "Network or WwTw", "Start of Overflow Event",
             "End of Overflow Event", "Duration of Overflow Event\n[h]:mm:ss", "Volume discharged \nm3", "Comments"]


def dt(*a):
    return datetime(*a)  # noqa: DTZ001  the sheets hold clock time


@pytest.fixture
def edition(tmp_path):
    wb = openpyxl.Workbook()
    s = wb.active
    s.title = "Overflow Summary 2017-2018"
    s.append(["", "Total Number of Spills"])
    s.append(SUMMARY_HEAD)
    s.append(["L1", "CSO000001", "ONE CSO", "CSO event", "Town, One CSO event", "South", "Network", "CSO"])
    s.append(["L2", "STW000009", "WORKS", "CSO event", "Works inlet CSO event", "East", "WWTW", "CSO"])
    s.append(["L2", "STW000009", "WORKS", "SSSO event", "Works storm tank event", "East", "WWTW", "SSSO"])
    e17 = wb.create_sheet("Overflow Events in 2017 ")
    e17.append(["Year", 2017])
    e17.append(HEAD_2017)
    e17.append(["L1", "CSO000001", "ONE CSO", "CSO event", "South", "Network",
                dt(2017, 1, 5, 10, 0), dt(2017, 1, 5, 11, 0), timedelta(hours=1)])
    e17.append(["L2", "STW000009", "WORKS", "CSO event", "East", "WWTW",
                dt(2017, 2, 1, 6, 0), dt(2017, 2, 1, 9, 0), timedelta(hours=3)])
    e17.append(["L3", "CSO000003", "QUIET CSO", "CSO event", "West", "Network", "No spills", "No spills", "No spills"])
    e18 = wb.create_sheet("Overflow Events in 2018")
    e18.append(["Year", 2018])
    e18.append(HEAD_2018)
    e18.append(["L1", "CSO000001", "ONE CSO", "Town, One CSO event", "CSO event", "South", "Network",
                dt(2018, 3, 1, 12, 0), dt(2018, 3, 1, 12, 30), timedelta(minutes=30)])
    e18.append(["L2", "STW000009", "WORKS", "Works inlet CSO event", "CSO event", "East", "WWTW",
                dt(2018, 3, 2, 12, 0), dt(2018, 3, 2, 13, 0), timedelta(hours=1)])
    e18.append(["L2", "STW000009", "WORKS", "Works storm tank event", "SSSO event", "East", "WWTW",
                dt(2018, 3, 3, 12, 0), dt(2018, 3, 3, 13, 0), timedelta(hours=1)])
    p = tmp_path / "edition.xlsx"
    wb.save(p)
    return p


def current_summary():
    """A later summary where the works' inlet CSO has its own id and every point a position."""
    return pd.DataFrame({"asset_id": ["CSO000001", "CSO000777", "CSO000778"],
                         "point": ["Town, One CSO Event", "Works inlet CSO Event", "Works storm tank Event"],
                         "lat": [55.9, 56.1, 56.1], "lon": [-3.2, -3.0, -3.0]}).assign(
        key=lambda d: d["point"].map(sw_history.point_key))


def test_the_trailing_space_sheet_is_read_and_2017_has_no_point(edition):
    _, rows = sw_archive.read_workbook(edition)
    assert sorted(rows["year"].unique()) == [2017, 2018]
    assert rows.loc[rows["year"] == 2017, "no_point"].all()
    assert not rows.loc[rows["year"] == 2018, "no_point"].any()
    assert (rows.loc[rows["year"] == 2017, "key"] == "").all()


def test_a_one_point_asset_takes_its_point_and_a_two_point_asset_stays_apart(edition):
    ev, yr, rows = sw_archive.load(edition, "archived", [current_summary()])
    one = ev[ev["year"] == 2017].set_index("asset_id_published")
    assert one.loc["CSO000001", "site_id"] == "CSO000001"
    assert one.loc["CSO000001", "lat"] == 55.9                  # position from the later summary
    assert one.loc["STW000009", "site_id"] == "STW000009" + sw_archive.UNSPLIT
    assert pd.isna(one.loc["STW000009", "lat"])
    # 2018's works rows map to the current ids by their points.
    assert set(ev.loc[ev["year"] == 2018, "site_id"]) == {"CSO000001", "CSO000777", "CSO000778"}
    # Listed in 2017 only, so no point to take: kept apart, its "No spills" read as no events.
    quiet = yr[(yr["site_id"] == "CSO000003" + sw_archive.UNSPLIT) & (yr["year"] == 2017)].iloc[0]
    assert quiet["status"] == "no events" and quiet["spills_12_24"] == 0


def test_years_keeps_only_the_sheets_asked_for(edition):
    ev, yr, rows = sw_archive.load(edition, "archived", [current_summary()], years=[2018])
    assert set(ev["year"]) == set(yr["year"]) == set(rows["year"]) == {2018}
