"""Spills in dry weather (data/raw/dry_weather_spills.csv, dipcast.dry_weather): the rule of
docs/DRY-WEATHER-SPILLS-TEST-2026-10.md on hand-made events, which overflows the page notes, and that the build puts
the note's facts on those overflows of a spot's list only (build_site.attach_dry_weather), after the forecasts. The
page's words are tested in tests/site_dry_weather_notes.test.cjs."""

import copy
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site

from dipcast.dry_weather import classify, dry_started_days, merge_overlaps, noted
from dipcast.model.features import spill_days

CSV = ROOT / "data" / "raw" / "dry_weather_spills.csv"
TEST_COUNTS = ROOT / "docs" / "DRY-WEATHER-SPILLS-TEST-2026-10-overflows.csv"
HEAD = "site_id,company,year,dry_spill_days,dry_days\n"
T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def _ov(sid, company="Wessex Water", **extra):
    return {"site_id": sid, "company": company, "site_name": sid, "status": 0, "weight": 0.5, "p_spill_today": 0.1,
            "p_spill_days": [0.1, 0.2], **extra}


def test_the_rule_on_hand_made_events():
    # Rain in one cell: wet on 1 and 7 January, dry otherwise. So 4-6 and 10-12 January are dry days (no rain on the
    # day or the two before); 1-3 and 7-9 are not.
    days = pd.date_range("2024-01-01", "2024-01-12", freq="D", tz="UTC")
    daily = pd.DataFrame({"cell_lat": 50.0, "cell_lon": -1.0, "day": days, "rain_d": [5, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0]})
    daily["rain_d1"], daily["rain_d2"] = daily["rain_d"].shift(1), daily["rain_d"].shift(2)
    ev = pd.DataFrame({"site_id": ["A", "A", "A", "B", "B"],
                       "event_start": [T("2024-01-01 20:00"), T("2024-01-02 10:00"), T("2024-01-05 03:00"),
                                       T("2024-01-07 12:00"), T("2024-01-11 01:00")],
                       "event_end": [T("2024-01-02 12:00"), T("2024-01-04 06:00"), T("2024-01-05 04:00"),
                                     T("2024-01-10 02:00"), T("2024-01-11 01:00")]})
    merged = merge_overlaps(ev)
    assert len(merged) == 4   # A's first two overlap and merge; the rest stay apart
    cells = pd.DataFrame({"site_id": ["A", "B"], "cell_lat": 50.0, "cell_lon": -1.0})
    touched = dry_started_days(merged, cells, daily)
    assert set(zip(touched["site_id"], touched["day"].dt.day)) == {("A", 5), ("B", 11)}
    lab = spill_days(ev).assign(y=1)
    frame = (pd.DataFrame([(s, d) for s in "AB" for d in days], columns=["site_id", "day"])
             .merge(daily, on="day").merge(lab, on=["site_id", "day"], how="left"))
    frame["y"] = frame["y"].fillna(0).astype(int)
    c = classify(frame, touched).assign(site=frame["site_id"], d=frame["day"].dt.day)
    on = lambda col: set(zip(c.loc[c[col], "site"], c.loc[c[col], "d"]))  # noqa: E731
    assert on("dry") == {(s, d) for s in "AB" for d in (4, 5, 6, 10, 11, 12)}
    # A wet-started spill still running on a dry day is neither a dry spill nor a quiet dry day.
    assert on("continuing") == {("A", 4), ("B", 10)}
    assert on("y_dry") == {("A", 5), ("B", 11)}
    assert on("kept") == on("dry") - on("continuing")


@pytest.mark.parametrize(("k", "n", "want"), [
    (10, 50, True), (9, 10, False), (10, 51, False), (48, 94, True), (0, 0, False), (10, 0, False)])
def test_which_counts_get_the_note(k, n, want):
    # At least 10 dry spill-days, at least a fifth of the dry days.
    assert noted(k, n) is want


def test_the_committed_file_is_the_tests_2025_counts_and_notes_46_overflows():
    rows = build_site.read_dry_weather(CSV)
    test = pd.read_csv(TEST_COUNTS)
    test = test[test["year"] == 2025].set_index("site_id")
    assert set(rows) == set(test.index)
    assert all((r["days"], r["dry_days"], r["company"]) == (test.loc[s, "k"], test.loc[s, "n"], test.loc[s, "company"])
               for s, r in rows.items())
    assert {r["year"] for r in rows.values()} == {2025}
    note = {s for s, r in rows.items() if noted(r["days"], r["dry_days"])}
    assert len(note) == 46
    assert rows["WXW00571"] == {"company": "Wessex Water", "year": 2025, "days": 48, "dry_days": 94}   # Hurdcott
    assert "UUP00114" not in rows   # Ambleside WwTW: no dry spill-day in 2025


def test_only_noted_overflows_get_the_note_and_nothing_else_changes(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("# a comment\n" + HEAD + "WXW00571,Wessex Water,2025,48,94\nWXW00001,Wessex Water,2025,3,90\n"
                 "WXW00002,Wessex Water,2025,12,100\nNOT_UPSTREAM,Wessex Water,2025,30,60\n")
    results = [
        {"id": "salisbury", "contributors": [_ov("WXW00571"), _ov("WXW00001"), _ov("WXW00002"), _ov("WXW00003")]},
        {"id": "other", "contributors": [_ov("WXW00001")]},
        {"id": "lake", "contributors": []},
        {"id": "failed", "error": "forecast failed"},
    ]
    before = copy.deepcopy(results)
    got = build_site.attach_dry_weather(results, p)
    assert got == {"overflows": 1, "spots": 1, "warnings": []}
    with_note = {(r["id"], c["site_id"]) for r in results for c in r.get("contributors", []) if "dry_weather" in c}
    assert with_note == {("salisbury", "WXW00571")}   # 3 of 90 is too few; 12 of 100 too small a share
    assert results[0]["contributors"][0]["dry_weather"] == {"year": 2025, "days": 48, "dry_days": 94}
    for r in results:
        for c in r.get("contributors", []):
            c.pop("dry_weather", None)
    assert results == before   # every other field as the forecast wrote it: the risk is untouched


def test_a_wrong_company_gets_no_note_and_a_warning(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text(HEAD + "A1,Thames Water,2025,20,50\n")
    results = [{"id": "x", "contributors": [_ov("A1")]}]
    got = build_site.attach_dry_weather(results, p)
    assert "dry_weather" not in results[0]["contributors"][0]
    assert got["overflows"] == 0 and len(got["warnings"]) == 1 and "A1" in got["warnings"][0]


@pytest.mark.parametrize("bad", [
    "A1,Wessex Water,2025,20,10\n",                                  # more dry spill-days than dry days
    "A1,Wessex Water,2025,twenty,50\n",
    "A1,Wessex Water,2025,20,50\nA1,Wessex Water,2025,20,50\n",       # listed twice
    "A1,Wessex Water,2025,20,50\nB1,Wessex Water,2024,20,50\n",       # two years
    "A1,,2025,20,50\n",
])
def test_a_file_the_page_could_not_word_truthfully_stops_every_note_not_the_build(tmp_path, bad):
    p = tmp_path / "d.csv"
    p.write_text(HEAD + bad)
    with pytest.raises(ValueError):
        build_site.read_dry_weather(p)
    results = [{"id": "x", "contributors": [_ov("A1")]}]
    got = build_site.attach_dry_weather(results, p)
    assert got["overflows"] == 0 and got["warnings"] and "dry_weather" not in results[0]["contributors"][0]


def test_the_model_never_reads_the_counts():
    # The forecast, the model and the feeds never read the file or the rule; the build attaches the note after every
    # forecast is made.
    names = re.compile(r"dry_weather_spills|attach_dry_weather|read_dry_weather|\bDRY_WEATHER\b|dipcast\.dry_weather")
    readers = sorted(str(f.relative_to(ROOT)) for d in ("src", "scripts") for f in (ROOT / d).rglob("*.py")
                     if names.search(f.read_text()) and f.name != "dry_weather.py")
    # overflow_record.py writes the overflows' record pages, which show the same note: a page, not the model.
    assert readers == ["scripts/build_site.py", "scripts/make_dry_weather_spills.py", "src/dipcast/overflow_record.py"]
    src = Path(build_site.__file__).read_text()
    body = src[src.index("\ndef build("):]
    assert body.index("forecast_point(") < body.index("attach_dry_weather(results)")
