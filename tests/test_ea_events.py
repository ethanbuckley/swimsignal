"""read_ea_events on small files in the layouts of the EA's start/stop files for the companies that
operate in England (© Environment Agency copyright and/or database right, Open Government Licence
v3.0): CSV and XLSX, an XLSX under a .csv name, Excel dates, Excel serials and three kinds of text."""

from datetime import datetime

import pandas as pd
import pytest

openpyxl = pytest.importorskip("openpyxl")

from dipcast.ingest.edm_events import COLS, EA_TEST_ONLY, ea_company, ea_times, read_ea_events

HEAD = ("Unique ID", "Site Name", "Discharge Start (GMT)", "Discharge Stop (GMT)")
POSITIONS = pd.DataFrame({"site_id": ["SSS00077", "UUW0001", "TWU00010"],
                          "lat": [50.9, 54.0, 51.5], "lon": [-1.4, -2.8, -1.0]})


def utc(*a):
    return pd.Timestamp(datetime(*a), tz="UTC")  # noqa: DTZ001


def _book(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def test_company_from_the_file_name():
    assert ea_company("South West Water 2025 Detailed EDM Data.csv") == "South West Water"
    assert ea_company("Southern 2024 Detailed EDM Data.csv") == "Southern Water"
    assert ea_company("Welsh Water Detailed Data 2026.xlsx") == "Dwr Cymru Welsh Water"
    assert ea_company("Thames Water 2025 EDM Detailed Data.xlsx") == "Thames Water"
    assert ea_company("Scottish Water.csv") is None
    assert EA_TEST_ONLY == {"Dwr Cymru Welsh Water"}


def test_times_in_every_form_the_files_use():
    t = ea_times(["2024/01/01T20:14:32.000Z",   # the DSP note's example
                  "2024-01-01T20:14:32Z",
                  "01/02/2024 20:14",            # day first
                  datetime(2024, 1, 1, 20, 14, 32),  # noqa: DTZ001 - an Excel date
                  45292.84342592593,             # Excel serial for 2024-01-01 20:14:32
                  "45292.84342592593",
                  "", None, "Discharge Start (GMT)"])
    assert t[0] == utc(2024, 1, 1, 20, 14, 32)
    assert t[1] == utc(2024, 1, 1, 20, 14, 32)
    assert t[2] == utc(2024, 2, 1, 20, 14)
    assert t[3] == utc(2024, 1, 1, 20, 14, 32)
    assert t[4] == utc(2024, 1, 1, 20, 14, 32)
    assert t[5] == utc(2024, 1, 1, 20, 14, 32)
    assert t[6:].isna().all()


def test_csv_with_a_header_and_repeated_rows(tmp_path):
    p = tmp_path / "Southern 2024 Detailed EDM Data.csv"
    p.write_text(",".join(HEAD) + "\n"
                 "SSS00077,TABLE ROAD HUNTING CSO,2024/01/01T20:14:32.000Z,2024/01/02T02:43:31.000Z\n"
                 "SSS00077,TABLE ROAD HUNTING CSO,2024/01/01T20:14:32.000Z,2024/01/02T02:43:31.000Z\n"
                 "SSS00077,TABLE ROAD HUNTING CSO,2024/01/02T07:54:36.000Z,2024/01/02T17:09:44.000Z\n"
                 "\n", encoding="utf-8")
    ev = read_ea_events([p], positions=POSITIONS, remap_ids=False)
    assert list(ev.columns) == COLS
    assert len(ev) == 2
    assert ev["duration_h"].iloc[0] == pytest.approx((6 * 3600 + 28 * 60 + 59) / 3600)
    assert ev["lat"].iloc[0] == pytest.approx(50.9)
    assert ev["source"].iloc[0] == "EA (Southern 2024 Detailed EDM Data.csv)"


def test_csv_in_windows_1252_with_day_first_times(tmp_path):
    p = tmp_path / "Wessex 2024 Detailed EDM Data.csv"
    p.write_bytes((",".join(HEAD) + "\r\nTWU00010,ST JOHN\u2019S CSO,03/02/2024 10:00,03/02/2024 11:30\r\n")
                  .encode("cp1252"))
    ev = read_ea_events([p], positions=POSITIONS, remap_ids=False)
    assert ev["event_start"].iloc[0] == utc(2024, 2, 3, 10)
    assert ev["site_name"].iloc[0] == "ST JOHN’S CSO"
    assert ev["duration_h"].iloc[0] == pytest.approx(1.5)


def test_xlsx_under_a_csv_name_is_read_as_a_workbook(tmp_path):
    # "Thames 2024 Detailed EDM Data.csv" is an XLSX workbook (its bytes begin PK; 16 Oct 2026).
    p = _book(tmp_path / "Thames 2024 Detailed EDM Data.csv", [
        HEAD,
        ("TWU00010", "OXFORD STW", datetime(2024, 3, 1, 6, 0), datetime(2024, 3, 1, 9, 15)),  # noqa: DTZ001
        ("TWU00010", "OXFORD STW", "2024-03-05T12:00:00Z", "2024-03-05T12:10:00Z"),
    ])
    ev = read_ea_events([p], positions=POSITIONS, remap_ids=False)
    assert len(ev) == 2
    assert ev["duration_h"].tolist() == pytest.approx([3.25, 1 / 6])


def test_events_with_no_stop_are_kept_and_impossible_ones_dropped(tmp_path):
    p = tmp_path / "United Utilities 2025 Detailed EDM Data.csv"
    p.write_text(",".join(HEAD) + "\n"
                 "UUW0001,A CSO,2025-01-01T00:00:00Z,\n"
                 "UUW0001,A CSO,2025-01-02T05:00:00Z,2025-01-02T04:00:00Z\n"   # stop before start
                 "UUW0001,A CSO,not a time,2025-01-03T04:00:00Z\n")
    ev = read_ea_events([p], positions=POSITIONS, remap_ids=False)
    assert len(ev) == 1
    assert ev["event_end"].isna().all()
