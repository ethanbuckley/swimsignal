"""The course briefing prototype (scripts/course_briefing.py, prototypes/course-briefing/): how a course is cut
into sections, how a day's records are read, and that the committed Henley Classic file keeps its promises: the
organiser briefing's limits word for word, no E. coli figure, nothing issued where nothing was, and no place in
the site build."""

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HENLEY = REPO / "prototypes" / "course-briefing" / "henley-classic"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


CB = _load("course_briefing")
DOC = json.loads((HENLEY / "course.json").read_text(encoding="utf-8"))


def test_a_course_is_cut_where_the_network_join_and_the_mapped_mouths_put_it():
    inflow = {"site_id": "works", "join_km": 0.35,
              "mouths": [{"km": 0.35, "link": "mapped"}, {"km": 0.13, "link": "mapped"}, {"km": -0.11, "link": "mapped"},
                         {"km": 0.86, "link": "possible"}]}
    assert CB.sections(2.11, [inflow]) == [
        {"from_km": 0.0, "to_km": 0.35, "adds": ["works"], "unresolved": []},
        {"from_km": 0.35, "to_km": 0.86, "adds": [], "unresolved": ["works"]},
        {"from_km": 0.86, "to_km": 2.11, "adds": [], "unresolved": []}]


def test_a_possible_mouth_never_becomes_a_join_and_no_inflow_is_one_section():
    assert CB.sections(2.0, []) == [{"from_km": 0.0, "to_km": 2.0, "adds": [], "unresolved": []}]
    only_possible = {"site_id": "w", "join_km": None, "mouths": [{"km": 0.5, "link": "possible"}]}
    assert CB.sections(2.0, [only_possible]) == [
        {"from_km": 0.0, "to_km": 0.5, "adds": [], "unresolved": ["w"]},
        {"from_km": 0.5, "to_km": 2.0, "adds": [], "unresolved": []}]
    below_the_start = {"site_id": "w", "join_km": None, "mouths": [{"km": -0.2, "link": "mapped"}]}
    assert CB.sections(2.0, [below_the_start]) == [{"from_km": 0.0, "to_km": 2.0, "adds": [], "unresolved": []}]


def test_a_monitor_s_day_is_said_as_it_was_polled():
    assert CB.monitor_state(6, 0) == "reported"
    assert CB.monitor_state(5, 8) == "part"
    assert CB.monitor_state(0, 6) == "none"
    assert CB.monitor_state(None, None) == "not polled" == CB.monitor_state(0, 0)


def test_only_spills_a_record_could_have_shown_by_then_are_listed():
    t = datetime(2024, 7, 6, 12, 0, tzinfo=UTC)
    ev = lambda s, a, b: {"site_id": s, "start": t + timedelta(hours=a), "end": None if b is None else t + timedelta(hours=b), "source": "x"}  # noqa: E731
    got = CB.events_in_window([ev("old", -80, -60), ev("recent", -30, -29), ev("running", -2, None), ev("later", 1, 2)], t)
    assert [e["site_id"] for e in got] == ["running", "recent"]


def test_the_script_refuses_a_state_folder_inside_a_checkout(tmp_path):
    with pytest.raises(CB.CourseError):
        CB.guard_state(REPO / "data" / "processed")
    with pytest.raises(CB.CourseError):
        CB.guard_state(REPO / "scratch-state")
    CB.guard_state(tmp_path)


def test_the_henley_course_file_reads_and_matches_its_data():
    c = CB.load_course(HENLEY / "course.toml")
    assert c["spot"] == "thames-henley" and c["length_m"] == 2112
    assert [d["id"] for d in c["date"]] == [d["id"] for d in DOC["dates"]] == ["routine", "differs", "gap"]
    assert DOC["contract"] == CB.CONTRACT and abs(DOC["km"] * 1000 - c["length_m"]) <= CB.TOLERANCE_M
    secs = DOC["sections"]
    assert secs[0]["from_km"] == 0 and secs[-1]["to_km"] == DOC["km"]
    assert all(a["to_km"] == b["from_km"] for a, b in zip(secs, secs[1:]))
    assert secs == CB.sections(DOC["km"], [{k: f[k] for k in ("site_id", "join_km", "mouths")} for f in DOC["inflows"]])


def test_the_limits_are_the_organiser_briefing_s_word_for_word():
    briefing = _load("briefing")
    assert DOC["limits"] == briefing.LIMITS
    assert DOC["decides"] == briefing.DECIDES.format(org="The organiser")


def test_no_ecoli_figure_and_nothing_issued_where_nothing_was():
    text = json.dumps(DOC).lower()
    for word in ("p_ecoli", "ecoli_", "cfu", "per 100 ml"):
        assert word not in text
    by = {d["id"]: d for d in DOC["dates"]}
    assert by["differs"]["issued"] is None and "12 September 2026" in by["differs"]["no_issue_why"]
    assert by["differs"]["monitors"] is None           # the feed was not polled in 2024: not known, never "reporting"
    for k in ("routine", "gap"):
        assert by[k]["issued"]["issue"].endswith("Z") and by[k]["day"] >= DOC["records_from"]
    assert all(s["side"] is False for s in by["routine"]["spills"])


def test_the_prototype_is_not_in_the_site_build():
    build = (REPO / "scripts" / "build_site.py").read_text(encoding="utf-8")
    assert "course-briefing" not in build and "course_briefing" not in build
    sw = (REPO / "src" / "dipcast" / "site" / "sw.js").read_text(encoding="utf-8")
    assert "course" not in sw.lower() or "course-briefing" not in sw
    page = (HENLEY / "index.html").read_text(encoding="utf-8")
    assert 'content="noindex, nofollow"' in page and "not published" in page
