"""The EA's yearly start/stop zips (© Environment Agency copyright and/or database right, Open
Government Licence v3.0): which member is whose, reading members straight from the zip in both
date forms (Excel serial numbers and ISO text), a sheet with a permit number before the id, and
finding the zips without the network when they are already on disk. Small zips built here; no
network."""

import io
import os
import zipfile

import pandas as pd
import pytest

openpyxl = pytest.importorskip("openpyxl")

from dipcast.ingest import edm_events
from dipcast.ingest.edm_events import (
    COLS, ea_yearly_zips, ea_zip_members, ea_zip_year, read_ea_dcww_events, read_ea_events,
)

HEAD = ("Unique ID", "Site Name", "Discharge Start (GMT)", "Discharge Stop (GMT)")
POSITIONS = pd.DataFrame({"site_id": ["AWS00007", "SWS00005", "DCW00047"],
                          "lat": [52.2, 50.9, 52.05], "lon": [-0.2, -0.3, -2.73]})


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def _xlsx(sheets: dict) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _zip(path, members: dict):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            if name.endswith("/"):
                zf.writestr(zipfile.ZipInfo(name), b"")
            else:
                zf.writestr(name, data)
    return path


@pytest.fixture
def year_zip(tmp_path):
    anglian = _xlsx({"Reg61": [
        HEAD,
        # Excel serial numbers: 45292.84342592593 is 2024-01-01 20:14:32.
        ("AWS00007", "ABBOTSLEY SPS", 45292.84342592593, 45292.875),
    ]})
    southern = (",".join(HEAD) + "\n"
                "SWS00005,ABBEY ROAD STEYNING CSO,2024/01/01T20:14:32.000Z,2024/01/02T02:43:31.000Z\n"
                "SWS00005,ABBEY ROAD STEYNING CSO,2024-01-02T07:54:36Z,2024-01-02T17:09:44Z\n").encode()
    welsh = _xlsx({"January - April": [
        HEAD, ("DCW00047", "EIGN WWTW", "2026-01-08T19:00:00Z", "2026-01-08T23:15:00Z"),
    ], "August": [
        ("PermitNo",) + HEAD,
        ("AH1001101", "DCW00047", "EIGN WWTW", "2026-08-27T07:30:00Z", "2026-08-27T09:15:00Z"),
    ]})
    return _zip(tmp_path / "2024 Detailed EDM Start-Stop Data.zip", {
        "Anglian 2024 Detailed EDM Data.xlsx": anglian,
        "Southern 2024 Detailed EDM Data.csv": southern,
        "Dwr Cymru Detailed Data 2026.xlsx": welsh,
        "notes/": b"",
        "__MACOSX/._Anglian 2024 Detailed EDM Data.xlsx": b"junk",
        "read me.txt": b"not a start/stop file",
    })


def test_year_from_the_zip_name():
    assert ea_zip_year("2025 Detailed EDM Start-Stop Data.zip") == 2025
    assert ea_zip_year("2026 year to August Detailed EDM Start-Stop Data.zip") == 2026
    assert ea_zip_year("Yorkshire 2025 Detailed EDM Data.xlsx") is None


def test_members_are_picked_per_company(year_zip):
    m = ea_zip_members(year_zip)
    assert set(m) == {"Anglian Water", "Southern Water", "Dwr Cymru Welsh Water"}
    assert m["Anglian Water"] == [(year_zip, "Anglian 2024 Detailed EDM Data.xlsx")]
    assert m["Dwr Cymru Welsh Water"] == [(year_zip, "Dwr Cymru Detailed Data 2026.xlsx")]


def test_a_member_of_no_known_company_stops_the_import(tmp_path):
    z = _zip(tmp_path / "2025 Detailed EDM Start-Stop Data.zip", {"Scottish Water 2025.csv": b"x"})
    with pytest.raises(ValueError, match="Scottish Water"):
        ea_zip_members(z)


def test_excel_serials_and_iso_text_read_from_the_zip(year_zip):
    m = ea_zip_members(year_zip)
    ev = read_ea_events(m["Anglian Water"] + m["Southern Water"], positions=POSITIONS, remap_ids=False)
    assert list(ev.columns) == COLS
    a = ev[ev["site_id"] == "AWS00007"].iloc[0]
    assert a["event_start"] == utc("2024-01-01 20:14:32")
    assert a["event_end"] == utc("2024-01-01 21:00:00")
    assert a["source"] == "EA (Anglian 2024 Detailed EDM Data.xlsx)"
    s = ev[ev["site_id"] == "SWS00005"]
    assert s["event_start"].tolist() == [utc("2024-01-01 20:14:32"), utc("2024-01-02 07:54:36")]
    assert s["source"].iloc[0] == "EA (Southern 2024 Detailed EDM Data.csv)"


def test_a_permit_number_before_the_id_is_skipped(year_zip):
    ev = read_ea_dcww_events(ea_zip_members(year_zip)["Dwr Cymru Welsh Water"], positions=POSITIONS)
    assert ev["site_id"].tolist() == ["DCW00047", "DCW00047"]
    assert ev["event_start"].tolist() == [utc("2026-01-08 19:00"), utc("2026-08-27 07:30")]
    assert ev["site_name"].tolist() == ["EIGN WWTW", "EIGN WWTW"]


def test_a_csv_with_a_permit_number_before_the_id(tmp_path):
    p = tmp_path / "Thames 2024 Detailed EDM Data.csv"
    p.write_text("PermitNo," + ",".join(HEAD) + "\n"
                 "CTCR.1234,TWU00010,OXFORD STW,2024-03-05T12:00:00Z,2024-03-05T12:10:00Z\n")
    ev = read_ea_events([p], positions=POSITIONS, remap_ids=False)
    assert ev["site_id"].tolist() == ["TWU00010"]
    assert ev["duration_h"].tolist() == pytest.approx([1 / 6])


def test_zips_on_disk_are_used_without_the_network(tmp_path, monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("asked the platform")
    monkeypatch.setattr(edm_events, "ea_zip_names", no_network)
    old = _zip(tmp_path / "2026 year to July Detailed EDM Start-Stop Data.zip", {})
    new = _zip(tmp_path / "2026 year to August Detailed EDM Start-Stop Data.zip", {})
    y25 = _zip(tmp_path / "2025 Detailed EDM Start-Stop Data.zip", {})
    os.utime(old, (1_000_000_000, 1_000_000_000))   # the renamed year-to-date zip is the newer file
    assert ea_yearly_zips([2025, 2026], tmp_path) == {2025: y25, 2026: new}


def test_a_missing_year_is_listed_and_downloaded(tmp_path, monkeypatch):
    got = []
    monkeypatch.setattr(edm_events, "ea_zip_names", lambda: {2025: "2025 Detailed EDM Start-Stop Data.zip"})

    def fake_download(name, dest):
        got.append(name)
        return _zip(dest / name, {})
    monkeypatch.setattr(edm_events, "download_ea_file", fake_download)
    assert ea_yearly_zips([2025], tmp_path) == {2025: tmp_path / "2025 Detailed EDM Start-Stop Data.zip"}
    assert got == ["2025 Detailed EDM Start-Stop Data.zip"]
    with pytest.raises(RuntimeError, match="no start/stop zip for \\[2024\\]"):
        ea_yearly_zips([2024], tmp_path)
