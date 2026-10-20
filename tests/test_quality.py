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
    assert t.count("This build had no overflow table") == 2
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
