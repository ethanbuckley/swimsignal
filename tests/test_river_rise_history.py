"""River rise history (docs/RIVER-RISE-HISTORY-CONTRACT-v1.md): the committed export holds its contract and is what the
committed record's table makes; the build gives a river spot its history only where the tile's gauge is the history's,
only for the months the display rule allows, and copies the export for the data page and the Research page. The page's
words are tested in tests/site_river_rise_history.test.cjs, run here too."""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as bs  # noqa: E402
import export_river_rise_history as m  # noqa: E402

FILE = ROOT / "data" / "research" / "river_rise_history.v1.json"


def _doc():
    return json.loads(FILE.read_text())


def _rs(measure, **kw):
    return {"station": "X", "river": "River X", "level_m": 0.5, "typical_low_m": 0.1, "typical_high_m": 1.0, "stale": False,
            "measure": measure, **kw}


def test_the_committed_file_holds_the_contract():
    d = _doc()
    assert m.check(d) == []
    assert d["coverage"] == {"gauges": 44, "gauge_months": 525, "gauge_months_shown": 496, "spots": 52}
    assert d["display"]["min_hours"] == m.MIN_HOURS == 480 and d["display"]["min_years"] == 2
    assert d["definition"]["words"] == "rose by more than a fifth of its usual range within 3 hours"
    assert "not a forecast" in d["claim"]["public_wording"]
    assert any("Trowlock" in x for x in d["limits"]) and any("Two years at most" in x for x in d["limits"])


def test_the_committed_file_is_what_the_committed_table_makes():
    d, fresh = _doc(), m.build()
    assert d["sources"]["table"] == fresh["sources"]["table"] and d["sources"]["gauges"] == fresh["sources"]["gauges"]
    for k in ("period", "definition", "display", "claim", "limits", "attribution", "gauges", "coverage"):
        assert d[k] == fresh[k], k
    # Ilkley, as the record's table has it: November 929 hours, 12 followed by a quick rise, in 4 rises.
    ilkley = next(g for g in d["gauges"] if g["gauge"] == "F1902")
    assert ilkley["spots"] == ["bw-uke4100-08901"] and ilkley["river"] == "River Wharfe"
    nov = ilkley["months"][10]
    assert nov == {"month": 11, "hours": 929, "rise_hours": 12, "rises": 4, "share": 0.01292, "years_in_month": 2, "years": [2024, 2025]}


def test_check_catches_broken_files():
    d = _doc()
    cases = [
        (lambda x: x["gauges"][0]["months"][0].update(rise_hours=x["gauges"][0]["months"][0]["hours"] + 1), "counts out of order"),
        (lambda x: x["gauges"][0]["months"][0].update(share=0.9), "share is not"),
        (lambda x: x["gauges"][0]["months"][0].update(years=[2023, 2024]), "years do not match"),
        (lambda x: x["gauges"][1]["spots"].append(x["gauges"][0]["spots"][0]), "served by two gauges"),
        (lambda x: x["claim"].update(public_wording="How often the river will rise."), "not a forecast"),
        (lambda x: x["definition"].update(rise_share=0.1), "definition is not the record's"),
        (lambda x: x["display"].update(min_hours=0), "display rule"),
        (lambda x: x["coverage"].update(gauge_months_shown=1), "display rule"),
        (lambda x: x["gauges"][0]["months"].reverse(), "months not 1 to 12"),
    ]
    for change, said in cases:
        bad = copy.deepcopy(d)
        change(bad)
        assert any(said in e for e in m.check(bad)), said


def test_the_display_rule_needs_enough_hours_and_both_years():
    shown = {"hours": 480, "rise_hours": 2, "rises": 1, "years_in_month": 2, "years": [2025, 2026]}
    assert m.shown_month(shown) and bs.rise_month_shown(shown, {"min_hours": 480, "min_years": 2})
    for bad in ({**shown, "hours": 479}, {**shown, "years_in_month": 1, "years": None}, None):
        assert not m.shown_month(bad) and not bs.rise_month_shown(bad, {"min_hours": 480, "min_years": 2})
    # The two gauge-months under 480 hours and the 29 with one year only are the 29 the file does not show.
    d = _doc()
    hidden = [(g["gauge"], x["month"]) for g in d["gauges"] for x in g["months"] if not m.shown_month(x)]
    assert len(hidden) == 525 - 496 == 29


def test_a_river_spot_gets_the_history_of_its_tiles_gauge_with_the_rule_applied(tmp_path):
    doc = _doc()
    g = next(x for x in doc["gauges"] if x["gauge"] == "F1902")
    g["months"][5]["hours"] = 300                         # June too few hours: null
    g["months"][6].update(years_in_month=1, years=None)   # July one year only: null
    g["months"] = [x for x in g["months"] if x["month"] != 8]   # August not in the table: null
    p = tmp_path / "h.json"
    p.write_text(json.dumps(doc))
    results = [{"id": "bw-uke4100-08901", "kind": "river", "river_state": _rs("F1902-level-stage-i-15_min-m")},
               {"id": "wye-hereford", "kind": "river", "river_state": _rs("055807_TG_320-level-stage-i-15_min-m")},   # the space as _
               {"id": "bw-uke2203-08903", "kind": "river", "river_state": _rs("L9999-level-stage-i-15_min-m")},   # another gauge
               {"id": "thames-henley", "kind": "river", "river_state": _rs("2496TH-level-stage-i-15_min-m")},     # no history
               {"id": "coquet-rothbury", "kind": "river", "river_state": None},                                    # no reading
               {"id": "ure-aysgarth", "kind": "river", "river_state": _rs("L2208-level-stage-i-15_min-m", water="lake")},
               {"id": "osm-windermere-waterhead", "kind": "lake", "river_state": _rs("F1902-level-x")}]
    h = bs.attach_rise_history(results, p)
    assert h == {"available": True, "version": "1.0.0", "spots": 2, "other_gauge": ["bw-uke2203-08903"]}
    ilk = results[0]["rise_history"]
    assert ilk["gauge"] == "F1902" and ilk["station"] == "Ilkley" and len(ilk["months"]) == 12
    assert ilk["months"][10] == {"hours": 929, "rise_hours": 12, "rises": 4, "years": [2024, 2025]}
    assert ilk["months"][5] is None and ilk["months"][6] is None and ilk["months"][7] is None
    assert ilk["period"] == {"first": "2024-11-21", "last": "2026-10-24", "years_by_month": doc["period"]["years_by_month"]}
    assert results[1]["rise_history"]["gauge"] == "055807_TG 320"
    for r in results[2:]:
        assert "rise_history" not in r, r["id"]


def test_no_history_without_an_export_of_this_contract(tmp_path):
    results = [{"id": "bw-uke4100-08901", "kind": "river", "river_state": _rs("F1902-level-stage-i-15_min-m"), "rise_history": {"old": 1}}]
    assert bs.attach_rise_history(results, tmp_path / "none.json") == {"available": False, "why": "no export in this build"}
    assert "rise_history" not in results[0]   # an earlier value never survives
    (tmp_path / "v2.json").write_text(json.dumps({**_doc(), "version": "2.0.0"}))
    assert "not swimsignal.river-rise-history 1.x" in bs.attach_rise_history(results, tmp_path / "v2.json")["why"]
    assert bs.write_rise_history(tmp_path / "site", tmp_path / "none.json")["available"] is False
    assert json.loads((tmp_path / "site" / "data" / "research" / "river_rise_history.json").read_text())["available"] is False


def test_the_history_is_in_the_spots_own_file_only():
    assert "rise_history" in bs.DETAIL_FIELDS
    assert "rise_history = attach_rise_history(results)" in (ROOT / "scripts" / "build_site.py").read_text()


def test_the_build_copies_it_lists_it_and_the_research_page_links_it(tmp_path):
    spots = [{"id": "bw-uke4100-08901", "name": "Wharfe at Cromwheel, Ilkley", "kind": "river", "upstream_summary": {"overflows": 0}, "days": []}]
    bs.write_pages(tmp_path, spots, root="https://example.org/", day="2026-11-06")
    copied = json.loads((tmp_path / "data" / "research" / "river_rise_history.json").read_text())
    assert copied["available"] is True and copied["gauges"] == _doc()["gauges"]
    data = (tmp_path / "data.html").read_text()
    assert "how often 44 river gauges rose quickly" in data and "<code>river_rise_history.json</code>" in data
    assert "<code>rise_history</code>" in data and "Not described here yet" not in data
    research = (tmp_path / "research.html").read_text()
    assert '<h3 id="river-rises">How often rivers rose quickly</h3>' in research
    assert 'href="data/research/river_rise_history.json"' in research and "RIVER-RISES-C3-2026-11.md" in research
    at = research.index('id="river-rises"')
    words = research[at:research.index("<h3", at + 10)]
    assert "Not a forecast" in words and "not a warning" in words and "history" in words


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_page_words():
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "site_river_rise_history.test.cjs")], capture_output=True, text=True,
                       timeout=60, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
