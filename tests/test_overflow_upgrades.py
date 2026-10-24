"""Announced overflow upgrades (data/raw/overflow_upgrades.csv): the build puts a note's facts on the listed
overflows of a spot's list only (build_site.attach_upgrades), and the spill model never reads the file, so
its inputs for those overflows are what they were. The page's words are tested in
tests/site_upgrade_notes.test.cjs."""

import copy
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site

from dipcast import config
from dipcast.overflows import latest_annual_returns

CSV = ROOT / "data" / "raw" / "overflow_upgrades.csv"
ILKLEY = {"YWS00176", "YWS00674", "YWS00179", "YWS00191", "YWS00144", "YWS00145"}
HEAD = "site_id,company,source_name,match,stage,what_changed,completed,source_url,quote,checked\n"
YW = "https://www.yorkshirewater.com/about-us/what-we-do/making-yorkshire-brilliant/addingham-and-ilkley"


def _row(sid, company="Yorkshire Water", stage="upgrading", match="name", url=YW, completed="", quote="We’re upgrading it."):
    return f'{sid},{company},A CSO,{match},{stage},storage,{completed},{url},"{quote}",2026-10-24\n'


def _ov(sid, company="Yorkshire Water", **extra):
    return {"site_id": sid, "company": company, "site_name": sid, "status": 0, "latest_event_end": "2026-03-31T04:18:39+00:00",
            "lta_spills": 36.0, "spill_hours": 214.5, "weight": 0.5, "p_spill_today": 0.1, "p_spill_days": [0.1, 0.2], **extra}


def test_the_committed_file_reads_clean_and_lists_the_six_ilkley_overflows_as_under_way():
    rows = build_site.read_upgrades(CSV)
    assert set(rows) == ILKLEY
    for r in rows.values():
        # Yorkshire Water's page is in the present and future tense, and gives no completion date.
        assert r["stage"] == "upgrading" and r["completed"] == "", r["site_id"]
        assert r["company"] == "Yorkshire Water" and r["source_url"] == YW and r["checked"] == "2026-10-24"
    assert {s for s, r in rows.items() if r["match"] == "shared name"} == {"YWS00191", "YWS00144", "YWS00145"}
    assert "920m³ storage tank" in rows["YWS00176"]["quote"]


def test_only_listed_overflows_get_the_note_and_nothing_else_on_any_row_changes(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text("# a comment\n" + HEAD + _row("YWS00176") + _row("YWS00144", match="shared name") + _row("NOT_UPSTREAM"))
    results = [
        {"id": "ilkley", "contributors": [_ov("YWS00176"), _ov("YWS01340"), _ov("YWS00144")]},
        {"id": "burnsall", "contributors": [_ov("YWS01340")]},
        {"id": "lake", "contributors": []},
        {"id": "failed", "error": "forecast failed"},
    ]
    before = copy.deepcopy(results)
    got = build_site.attach_upgrades(results, p, years={"YWS00176": 2025})
    assert got == {"overflows": 2, "spots": 1, "warnings": []}
    with_note = {(r["id"], c["site_id"]) for r in results for c in r.get("contributors", []) if "upgrade" in c}
    assert with_note == {("ilkley", "YWS00176"), ("ilkley", "YWS00144")}
    assert results[0]["contributors"][0]["upgrade"] == {
        "company": "Yorkshire Water", "stage": "upgrading", "match": "name", "source_name": "A CSO", "url": YW,
        "checked": "2026-10-24", "returns_to": 2025}
    assert "returns_to" not in results[0]["contributors"][2]["upgrade"]   # no year known: the page says "past spill counts"
    # Every other field, on every row and spot, as the forecast wrote it: the risk is untouched.
    for r in results:
        for c in r.get("contributors", []):
            c.pop("upgrade", None)
    assert results == before


def test_a_finish_date_is_passed_on_and_a_wrong_company_gets_no_note(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text(HEAD + _row("A1", stage="upgraded", completed="2026-07-31") + _row("B1", company="Thames Water"))
    results = [{"id": "x", "contributors": [_ov("A1"), _ov("B1")]}]
    got = build_site.attach_upgrades(results, p, years={})
    assert results[0]["contributors"][0]["upgrade"]["completed"] == "2026-07-31"
    assert "upgrade" not in results[0]["contributors"][1]
    assert got["overflows"] == 1 and len(got["warnings"]) == 1 and "B1" in got["warnings"][0]


@pytest.mark.parametrize("bad", [
    _row("A1", stage="planned"), _row("A1", match="maybe"), _row("A1", url="http://example.org/x"),
    _row("A1", quote=" "), _row("A1", completed="Summer 2026"), _row("A1") + _row("A1"),
])
def test_a_row_the_page_could_not_word_truthfully_stops_every_note_not_the_build(tmp_path, bad):
    p = tmp_path / "u.csv"
    p.write_text(HEAD + bad)
    with pytest.raises(ValueError):
        build_site.read_upgrades(p)
    results = [{"id": "x", "contributors": [_ov("A1")]}]
    got = build_site.attach_upgrades(results, p, years={})
    assert got["overflows"] == 0 and got["warnings"] and "upgrade" not in results[0]["contributors"][0]


def test_the_model_never_reads_the_file():
    # Only the build's note step names the file; nothing under src/dipcast (the model, the trace, the
    # feeds) does, and the build attaches the notes after every forecast is made.
    names = re.compile(r"overflow_upgrades|attach_upgrades|read_upgrades|\bUPGRADES\b")
    readers = sorted(str(f.relative_to(ROOT)) for d in ("src", "scripts") for f in (ROOT / d).rglob("*.py") if names.search(f.read_text()))
    assert readers == ["scripts/build_site.py"]
    src = Path(build_site.__file__).read_text()
    body = src[src.index("\ndef build("):]
    assert body.index("forecast_point(") < body.index("attach_upgrades(results)")
    assert "upgrade" not in re.search(r'contrib\.append\(\{k: _clean.*?\]\}', (ROOT / "src/dipcast/model/forecast.py").read_text(), re.S).group(0)


def test_the_spill_model_still_reads_the_ilkley_overflows_counts_and_the_note_names_the_same_year():
    # The six as docs/UPGRADED-OVERFLOWS-2026-10.md found them: the 2025 return's long-term averages.
    a = latest_annual_returns(pd.read_parquet(config.PROCESSED / "annual_returns.parquet")).set_index("site_id")
    lta = a.loc[sorted(ILKLEY), "lta_spills"].round(2).to_dict()
    assert lta == {"YWS00144": 55.0, "YWS00145": 47.67, "YWS00176": 36.0, "YWS00179": 4.17, "YWS00191": 7.33, "YWS00674": 48.5}
    years = build_site.latest_return_years()
    assert {s: years[s] for s in ILKLEY} == dict.fromkeys(ILKLEY, 2025)
    assert all(int(a.loc[s, "ar_year"]) == years[s] for s in ILKLEY)
