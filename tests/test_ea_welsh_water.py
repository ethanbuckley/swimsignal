"""read_ea_dcww_events on small workbooks built from real rows of the EA's Welsh Water start/stop
files (© Environment Agency copyright and/or database right, Open Government Licence v3.0)."""

from datetime import datetime

import pandas as pd
import pytest

openpyxl = pytest.importorskip("openpyxl")

from dipcast.ingest.edm_events import COLS, read_ea_dcww_events


def naive(*a):
    return datetime(*a)  # noqa: DTZ001 - an Excel cell holds a date with no zone


POSITIONS = pd.DataFrame({"site_id": ["DCW00019", "DCW00097", "DCW00047"],
                          "lat": [51.80, 51.85, 52.05], "lon": [-2.55, -2.53, -2.73]})


def _book(path, sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
    wb.save(path)
    return path


@pytest.fixture
def books(tmp_path):
    # 2024: Excel dates in one sheet. 2026: ISO text over two sheets, one with an empty fifth column,
    # and an id the annual returns lack (DCW90012).
    y2024 = _book(tmp_path / "2024.xlsx", {"Start_Stop": [
        ("Unique ID", "Site Name", "Discharge Start (GMT)", "Discharge Finish (GMT)"),
        ("DCW00019", "Cannop Road SPS", naive(2024, 4, 4, 4, 30), naive(2024, 4, 4, 5, 0)),
        ("DCW00019", "Cannop Road SPS", naive(2024, 5, 12, 15, 15), naive(2024, 5, 12, 16, 0)),
    ]})
    y2026 = _book(tmp_path / "2026.xlsx", {
        "January - April": [
            ("Unique ID", "Site Name (EA consent database)", "Discharge Start (GMT)", "Discharge Stop (GMT)", "Unnamed: 4"),
            ("DCW00047", "EIGN WASTEWATER TREATMENT WORKS", "2026-01-08T19:00:00Z", "2026-01-08T23:15:00Z", None),
            ("DCW90012", "SOME EMERGENCY OVERFLOW", "2026-01-09T01:00:00Z", "2026-01-09T01:15:00Z", None),
        ],
        "May": [
            ("Unique ID", "Site Name (EA consent database)", "Discharge Start (GMT)", "Discharge Stop (GMT)"),
            ("DCW00097", "RUARDEAN STW", "2026-05-02T21:00:00Z", "2026-05-02T22:15:00Z"),
        ],
    })
    return [y2024, y2026]


def test_reads_every_sheet_in_the_edm_events_schema(books):
    ev = read_ea_dcww_events(books, positions=POSITIONS)
    assert list(ev.columns) == COLS
    assert len(ev) == 5
    assert set(ev["site_id"]) == {"DCW00019", "DCW00047", "DCW00097", "DCW90012"}


def test_excel_dates_and_iso_text_are_both_utc(books):
    ev = read_ea_dcww_events(books, positions=POSITIONS).set_index(["site_id", "event_start"])
    first = ev.loc[("DCW00019", pd.Timestamp("2024-04-04 04:30", tz="UTC"))]
    assert first["duration_h"] == pytest.approx(0.5)
    eign = ev.loc[("DCW00047", pd.Timestamp("2026-01-08 19:00", tz="UTC"))]
    assert eign["duration_h"] == pytest.approx(4.25)


def test_a_single_file_of_excel_dates_is_not_read_as_epoch_numbers(books):
    # to_utc treats a column that is all numbers as epoch milliseconds; dates must not go that way.
    ev = read_ea_dcww_events(books[:1], positions=POSITIONS)
    assert ev["event_start"].dt.year.eq(2024).all()
    assert ev["duration_h"].tolist() == pytest.approx([0.5, 0.75])


def test_positions_come_from_the_given_table_and_unknown_ids_keep_no_position(books):
    ev = read_ea_dcww_events(books, positions=POSITIONS)
    assert ev.loc[ev["site_id"] == "DCW00047", "lat"].iloc[0] == pytest.approx(52.05)
    assert ev.loc[ev["site_id"] == "DCW90012", "lat"].isna().all()
    assert ev["source"].str.startswith("EA Welsh Water (").all()
