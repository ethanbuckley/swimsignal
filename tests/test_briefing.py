"""Pilot briefings (scripts/briefing.py, docs/PILOT-SESSIONS.md): the session file, the issue id, the
archive and its manifest, what changed between two builds, the decision log and the search, and that no
recipient's data is written inside this repository. No network and no Chrome: the live site is one of
two fixture builds (tests/fixtures/briefings/before.json and after.json, made by make_fixtures.py) and
the pages are drawn by a stand-in that writes what record.js and sites.js would where the checks look."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import urllib.parse
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "tests" / "fixtures" / "briefings"
SESSION = FX / "session.toml"


def _load():
    spec = importlib.util.spec_from_file_location("briefing", ROOT / "scripts" / "briefing.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["briefing"] = mod   # its dataclasses look their module up by name
    spec.loader.exec_module(mod)
    return mod


B = _load()
BEFORE = json.loads((FX / "before.json").read_text())
AFTER = json.loads((FX / "after.json").read_text())
ID_BEFORE, ID_AFTER = "2dba49e-20261020T1700Z", "f00d123-20261020T2200Z"


def site(build: dict, calls: list | None = None):
    """A stand-in for http_get: the build's file for any URL ending in its name, whatever the query."""
    def get(url: str) -> bytes:
        if calls is not None:
            calls.append(url)
        return json.dumps(build[url.split("?")[0].rsplit("/", 1)[-1]]).encode()
    return get


def fake_render(url, data, generated_at, kind):
    """The page as far as check_page looks: the issue time as record.js (`at`) and sites.js (`issue`) write
    it, the record's level line from the data it was given, the sites view's rows for the link's day, and the
    data it asked for."""
    t = B.parse_time(generated_at).astimezone(B.UK)
    expect = {"record": f"{t.day} {t:%b %Y, %H:%M}", "sites": f"{t:%a} {t.day} {t:%b, %H:%M}"}
    level, rows = "", {}
    q = urllib.parse.parse_qs(url.split("#", 1)[1])
    snap = B.Snapshot(json.loads(data["spots.json"]), json.loads(data["alerts.json"]))
    if kind == "record":
        lv = B.day_words(snap, q["spot"][0], q["day"][0])[0]
        level = f"{lv.capitalize()} risk" if lv in B.ORDER else lv or ""
    elif "day" in q:
        rows = {i: [q["day"][0], B.day_words(snap, i, q["day"][0])[0]] for i in q["spots"][0].split(",")}
    text = f"{level}\nForecast issued {expect[kind]}."
    need = "spots.json" if kind == "record" else "spots-lite.json"
    return B.Rendered(url=url, dom=f"<!doctype html><p>{text}</p>", text=text, pdf=b"%PDF-1.4 stand-in\n", served={need: 1},
                      page_files={f"{kind}.js": (url.split("#")[0], b"// the page's script")}, level=level, expect=expect, rows=rows)


@pytest.fixture(autouse=True)
def no_pdftotext(monkeypatch):
    monkeypatch.setattr(B, "pdf_text", lambda p: None)   # the stand-in PDFs have no text


def at(build: dict, minutes: int = 30):
    return B.parse_time(build["spots.json"]["generated_at"]) + timedelta(minutes=minutes)


def issue(root: Path, build: dict = BEFORE, session: Path = SESSION, **kw):
    return B.issue(session, root, "https://swimsignal.co.uk/", get=site(build), render=fake_render, now=at(build), **kw)


# ------------------------------------------------------------------ the session file
def test_the_example_session_loads():
    s = B.load_session(SESSION)
    assert (s.organisation, s.day.isoformat(), s.time, s.main, s.backup) == ("Example Outdoor Centre", "2026-10-22", "09:30", "bw-uke4100-08901", "wharfe-burnsall")
    assert s.spots == [("main", "bw-uke4100-08901"), ("backup", "wharfe-burnsall")]
    assert (s.key, s.org_slug) == ("2026-10-22T0930", "example-outdoor-centre")
    assert [r["email"] for r in s.recipients] == ["alex@example.org", "sam@example.org"]


def test_a_bad_session_file_lists_every_problem(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('organisation = "X"\ndate = "2026-10-22"\ntime = "9.30"\nmain = "a"\nback_up = "b"\nbackup = "a"\n'
                 'decision_maker = ""\n[[recipients]]\nname = "Y"\nemail = "not an address"\n')
    with pytest.raises(B.BriefingError) as e:
        B.load_session(p)
    msg = str(e.value)
    for said in ("unknown field 'back_up'", "decision_maker is missing", "date must be a TOML date", "time must be",
                 "backup is the same spot as main", "recipient 1 (Y) has no valid email"):
        assert said in msg
    p.write_text('organisation = "X"\ndate = 2026-10-22\ntime = "09:30"\nmain = "a"\ndecision_maker = "Z"\n')
    with pytest.raises(B.BriefingError, match="recipients is missing"):
        B.load_session(p)


def test_a_session_without_a_backup(tmp_path):
    p = tmp_path / "one.toml"
    p.write_text(SESSION.read_text().replace('backup = "wharfe-burnsall"', ""))
    assert B.load_session(p).spots == [("main", "bw-uke4100-08901")]


# ------------------------------------------------------------------ the issue id
def test_the_issue_id_is_pr_275s():
    # The build's commit and the issue time in UTC to the minute (printed.js, issueId): 18:00 BST is 17:00 UTC.
    assert B.issue_id(BEFORE["spots.json"]) == ID_BEFORE      # no `commit` yet: from the model version
    assert B.issue_id(AFTER["spots.json"]) == ID_AFTER        # `commit`, once PR #275 is live
    assert B.commit_of(BEFORE["spots.json"]) == ("2dba49e", "model version")
    assert B.commit_of(AFTER["spots.json"]) == ("f00d123", "spots.json commit")
    assert B.issue_id({"generated_at": "2026-01-05T09:07:59+00:00", "spots": []}) == "nogit-20260105T0907Z"   # GMT: no shift
    assert B.issue_id({"commit": "abc1234", "generated_at": "not a time"}) == "abc1234"


# ------------------------------------------------------------------ missing data
def test_what_was_missing_at_each_spot():
    before = B.Snapshot(BEFORE["spots.json"], BEFORE["alerts.json"])
    keys = [m["key"] for m in B.missing(before.spot("bw-uke4100-08901"), "2026-10-22")]
    # 16 overflows upstream, 15 reporting: the other one offline (evidence.js counts it the same way); a
    # designated bathing water, whose EA advice for today can never be read.
    assert keys == ["offline", "ea_advice"]
    assert B.missing(before.spot("wharfe-burnsall"), "2026-10-22") == []
    after = B.Snapshot(AFTER["spots.json"], AFTER["alerts.json"])
    said = {m["key"]: m["say"] for m in B.missing(after.spot("bw-uke4100-08901"), "2026-10-22")}
    assert "feed_stale:Yorkshire Water" in said and "had not updated since 20 Oct 2026, 20:00" in said["feed_stale:Yorkshire Water"]


def test_missing_names_each_gap():
    s = {"id": "x", "source": "curated", "upstream_summary": {"overflows": 10, "wales_share": 0.44},
         "now": {"monitored_upstream": 4, "no_feed_upstream": 3, "feed_down_upstream": 2, "stale_upstream": 0,
                 "feed_down": [{"company": "Thames Water", "overflows": 2}], "feed_stale": []},
         "days": [{"date": "2026-10-20", "risk": 0.1}, {"date": "2026-10-21", "risk": None},
                  {"date": "2026-10-22", "risk": 0.2, "rain_missing_share": 0.25}],
         "flood_alerts": None, "river_state": {"stale": True, "station": "Somewhere", "age_hours": 30}}
    got = {m["key"]: m["say"] for m in B.missing(s, "2026-10-22")}
    assert list(got) == ["no_feed", "offline", "feed_down:Thames Water", "day:2026-10-21", "rain:2026-10-22", "wales",
                         "flood_unchecked", "river_level"]
    assert got["no_feed"].startswith("3 of the 10 overflows upstream have no live feed")
    assert got["offline"].startswith("1 of the 10 overflows upstream was offline")
    assert "Wednesday 21 October 2026" in got["day:2026-10-21"]
    assert "25%" in got["rain:2026-10-22"] and "44%" in got["wales"]
    # No overflow upstream: nothing about feeds or days, which there is nothing to forecast from.
    assert B.missing({"upstream_summary": {"overflows": 0}, "days": [{"date": "2026-10-20", "risk": None}]}) == []


# ------------------------------------------------------------------ what changed
def test_changes_between_two_builds_for_the_session_day():
    s = B.load_session(SESSION)
    got = B.compare(B.Snapshot(BEFORE["spots.json"], BEFORE["alerts.json"]), B.Snapshot(AFTER["spots.json"], AFTER["alerts.json"]), s)
    assert [(c.role, c.kind) for c in got] == [("main", "up"), ("main", "discharging"), ("main", "missing_new"), ("main", "ea_sample")]
    say = [c.say for c in got]
    assert say[0] == "Higher: Very high risk: sewage spills (was: High risk: rated poor)."
    assert say[1].startswith("Overflows discharging upstream when the forecast was made: 1 (was 0). Started since the briefing: ILKLEY MIDDLETON/CSO (Yorkshire Water), under 0.1 km upstream.")
    assert say[2].startswith("Now missing: 1 overflows upstream on Yorkshire Water's feed had not updated")
    assert say[3] == "A new Environment Agency lab sample, taken 20 October: 1200 E. coli per 100 ml."
    # The other way round, the level goes down and the gap closes.
    back = B.compare(B.Snapshot(AFTER["spots.json"], AFTER["alerts.json"]), B.Snapshot({**BEFORE["spots.json"], "generated_at": "2026-10-21T05:00:00+01:00"}, BEFORE["alerts.json"]), s)
    assert [c.kind for c in back if c.kind in ("down", "missing_gone")] == ["down", "missing_gone"]


def test_no_change_from_the_same_build_or_on_a_day_that_did_not_move(tmp_path):
    s = B.load_session(SESSION)
    snap = B.Snapshot(BEFORE["spots.json"], BEFORE["alerts.json"])
    assert B.compare(snap, snap, s) == []
    p = tmp_path / "s.toml"
    p.write_text(SESSION.read_text().replace("date = 2026-10-22", "date = 2026-10-21"))
    got = B.compare(snap, B.Snapshot(AFTER["spots.json"], AFTER["alerts.json"]), B.load_session(p))
    assert "up" not in [c.kind for c in got]   # 21 October was very high in both


def test_higher_and_lower_only_between_risk_levels():
    s = B.load_session(SESSION)
    old, new = json.loads(json.dumps(BEFORE)), json.loads(json.dumps(AFTER))
    new["alerts.json"]["spots"]["bw-uke4100-08901"] = {"level": "no overflows", "headline": B.FOUND_NONE}
    got = B.compare(B.Snapshot(old["spots.json"], old["alerts.json"]), B.Snapshot(new["spots.json"], new["alerts.json"]), s)
    assert got[0].kind == "reason" and got[0].say == f"Changed: {B.FOUND_NONE} (was: High risk: rated poor)."


# ------------------------------------------------------------------ issuing, and the manifest
def test_issue_keeps_a_fixed_copy_with_its_manifest(tmp_path):
    folder, text = issue(tmp_path)
    assert folder == tmp_path / "issued" / "example-outdoor-centre" / "2026-10-22T0930" / ID_BEFORE
    m = json.loads((folder / "manifest.json").read_text())
    assert (m["format"], m["issue_id"]) == (1, ID_BEFORE)
    assert m["forecast"]["generated_at"] == BEFORE["spots.json"]["generated_at"]
    assert m["forecast"]["commit_from"] == "model version" and m["forecast"]["age_min"] == 30
    assert m["session"] == {"organisation": "Example Outdoor Centre", "org_slug": "example-outdoor-centre", "date": "2026-10-22",
                            "time": "09:30", "main": "bw-uke4100-08901", "backup": "wharfe-burnsall",
                            "decision_maker": "Alex Example, centre manager", "file": "session.toml", "from": str(SESSION)}
    assert [x["file"] for x in m["sources"]] == ["data/spots.json", "data/spots-lite.json", "data/verification.json", "data/alerts.json"]
    assert all("?briefing=" in x["url"] for x in m["sources"])
    assert [(x["role"], x["day"]["headline"]) for x in m["spots"]] == [("main", "High risk: rated poor"), ("backup", "Moderate risk: sewage spills")]
    assert [x["key"] for x in m["spots"][0]["missing"]] == ["offline", "ea_advice"]
    assert [(p["kind"], p["role"]) for p in m["pages"]] == [("record", "main"), ("record", "backup"), ("sites", "both")]
    assert m["pages"][0]["issue_time_shown"] == "20 Oct 2026, 18:00" and m["pages"][2]["issue_time_shown"] == "Tue 20 Oct, 18:00"
    assert m["pages"][2]["day_shown"] == "2026-10-22" and "day_shown" not in m["pages"][0]   # the sites view, on the session's day
    # Every file is listed with its hash, and they are as issued.
    listed = {f["path"] for f in m["files"]}
    on_disk = {str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file()} - {"manifest.json"}
    assert listed == on_disk and B.check_files(folder, m) == []
    assert {f"swimsignal-record-main-{ID_BEFORE}.pdf", f"swimsignal-sites-{ID_BEFORE}.pdf", "record-main.drawn.html", "session.toml",
            "briefing.txt", "page/record.js", "data/spots.json"} <= listed
    # The pages were given the session's spots only.
    kept = json.loads((folder / "data" / "spots.json").read_text())
    assert [s["id"] for s in kept["spots"]] == ["bw-uke4100-08901", "wharfe-burnsall"] and kept["generated_at"] == m["forecast"]["generated_at"]
    assert set(json.loads((folder / "data" / "alerts.json").read_text())["spots"]) == {"bw-uke4100-08901", "wharfe-burnsall"}
    assert not list(folder.parent.glob(".*.partial"))
    # The words: the forecast's limits first, then the customer decides, then the spots.
    lines = text.splitlines()
    assert lines[0] == "Subject: SwimSignal briefing for Example Outdoor Centre: Thursday 22 October 2026, 09:30"
    assert lines[2] == B.LIMITS and lines[4] == B.DECIDES.format(org="Example Outdoor Centre")
    assert "Thursday 22 October 2026: High risk: rated poor." in text and "Thursday 22 October 2026: Moderate risk: sewage spills." in text
    assert ID_BEFORE in text and "record.html#spot=bw-uke4100-08901&day=2026-10-22&org=Example%20Outdoor%20Centre" in text
    assert "Avoid" not in text and "choose a lower" not in text   # alerts.json's actions are advice: a briefing gives none
    assert (folder / "briefing.txt").read_text() == text


def test_issue_again_only_from_a_new_build_and_say_what_changed(tmp_path):
    first, _ = issue(tmp_path)
    with pytest.raises(B.BriefingError, match="already has a briefing from this build"):
        issue(tmp_path)
    second, text = issue(tmp_path, AFTER)
    assert second.name == ID_AFTER and first.exists()
    m = json.loads((second / "manifest.json").read_text())
    assert m["previous"]["issue_id"] == ID_BEFORE
    assert [c["kind"] for c in m["changes_since_previous"]] == ["up", "discharging", "missing_new", "ea_sample"]
    assert f"Changes since the briefing of Tuesday 20 October, 18:30 (issue id {ID_BEFORE}):" in text
    assert "- Higher: Very high risk: sewage spills (was: High risk: rated poor)." in text
    assert "Backup spot, River Wharfe, Burnsall: no change." in text


@pytest.mark.parametrize("change, said", [
    ("date = 2026-10-19", "has passed"),
    ("date = 2026-10-30", "first appears on Monday 26 October 2026"),
    ('main = "no-such-spot"', "Not in the live forecast: no-such-spot"),
])
def test_issue_refuses_a_day_or_spot_it_cannot_cover(tmp_path, change, said):
    p = tmp_path / "s.toml"
    key = change.split(" =")[0]
    p.write_text("\n".join(change if line.startswith(key + " ") else line for line in SESSION.read_text().splitlines()))
    with pytest.raises(B.BriefingError, match=said):
        issue(tmp_path / "root", session=p)
    assert not (tmp_path / "root" / "issued").exists() or not list((tmp_path / "root" / "issued").rglob("manifest.json"))


def test_issue_refuses_a_stale_forecast_unless_told(tmp_path):
    late = at(BEFORE, 9 * 60)
    with pytest.raises(B.BriefingError, match="9.0 h old"):
        B.issue(SESSION, tmp_path, get=site(BEFORE), render=fake_render, now=late)
    folder, _ = B.issue(SESSION, tmp_path, get=site(BEFORE), render=fake_render, now=late, stale_ok=True)
    assert json.loads((folder / "manifest.json").read_text())["forecast"]["age_min"] == 540


def test_a_page_that_did_not_draw_the_kept_data_stops_the_issue(tmp_path):
    def wrong_time(url, data, g, kind):
        r = fake_render(url, data, g, kind)
        r.text = r.text.replace("18:00", "17:00")
        return r

    def live_data(url, data, g, kind):
        r = fake_render(url, data, g, kind)
        r.unexpected = ["https://swimsignal.co.uk/data/spot/x.json"]
        return r

    def other_level(url, data, g, kind):
        r = fake_render(url, data, g, kind)
        r.level = "Low risk"
        return r

    def sites_without_day(url, data, g, kind):   # the live sites.js from before day= (20 Oct 2026)
        r = fake_render(url, data, g, kind)
        r.rows = {}
        return r

    def sites_other_level(url, data, g, kind):
        r = fake_render(url, data, g, kind)
        r.rows = {k: [d, "low"] for k, (d, _) in r.rows.items()}
        return r

    for render, said in ((wrong_time, "does not show the forecast's issue time"), (live_data, "data the archive does not keep"),
                         (other_level, "the two disagree"), (sites_without_day, "does not give bw-uke4100-08901's level on 2026-10-22"),
                         (sites_other_level, "the sites view says 'low' for bw-uke4100-08901 on 2026-10-22, alerts.json 'high'")):
        with pytest.raises(B.BriefingError, match=said):
            B.issue(SESSION, tmp_path, get=site(BEFORE), render=render, now=at(BEFORE))
        assert not list(tmp_path.rglob("manifest.json")) and not list(tmp_path.rglob("*.partial"))


def test_the_pdf_text_is_checked_where_pdftotext_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "pdf_text", lambda p: "a PDF from another build, 20 Oct 2026, 12:00")
    with pytest.raises(B.BriefingError, match="the PDF's text does not show the issue time"):
        issue(tmp_path)


def test_a_page_showing_an_issue_id_must_show_this_one():
    r = fake_render("https://x/record.html#spot=bw-uke4100-08901&day=2026-10-22", B.slim(B.Live(
        {n: json.dumps(BEFORE[n]).encode() for n in B.DATA_FILES}, BEFORE, {}, ""), ["bw-uke4100-08901"]),
        BEFORE["spots.json"]["generated_at"], "record")
    r.text += f"\nIssue id {ID_BEFORE}: the build and the forecast's issue time in UTC"
    assert B.check_page(r, "record", ID_BEFORE, "high", Path("x.pdf"))["issue_id_shown"] is True
    r.text = r.text.replace(ID_BEFORE, ID_AFTER)
    with pytest.raises(B.BriefingError, match="shows an issue id, but not"):
        B.check_page(r, "record", ID_BEFORE, "high", Path("x.pdf"))


def test_reading_two_builds_at_once_is_refused():
    mixed = {**BEFORE, "alerts.json": AFTER["alerts.json"]}
    calls = []
    with pytest.raises(B.BriefingError, match="changed while its files were read, 2 times running"):
        B.fetch_live("https://swimsignal.co.uk/", get=site(mixed, calls), tries=2, wait=0)
    assert len(calls) == 8   # all four files, twice
    live = B.fetch_live("https://swimsignal.co.uk/", get=site(BEFORE))
    assert live.docs["spots.json"]["generated_at"] == BEFORE["spots.json"]["generated_at"]


# ------------------------------------------------------------------ changes, decisions, finding a briefing
def test_changes_says_what_moved_and_exits_1(tmp_path, monkeypatch, capsys):
    issue(tmp_path)
    monkeypatch.setattr(B, "http_get", site(AFTER))
    assert B.main(["--root", str(tmp_path), "changes", str(SESSION)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("Subject: SwimSignal: changes for Example Outdoor Centre, Thursday 22 October 2026, 09:30\n\n" + B.LIMITS)
    assert f"(UK time, issue id {ID_AFTER})" in out and "Main spot, Wharfe at Cromwheel, Ilkley:" in out
    assert "Backup spot, River Wharfe, Burnsall: no change." in out and B.LIMITS in out
    assert "Send to: Alex Example <alex@example.org>; Sam Sample <sam@example.org>" in out
    monkeypatch.setattr(B, "http_get", site(BEFORE))
    assert B.main(["--root", str(tmp_path), "changes", str(SESSION)]) == 0
    assert capsys.readouterr().out.startswith("No change for Example Outdoor Centre's session")
    log = B.jsonl(tmp_path / "issued" / "example-outdoor-centre" / "2026-10-22T0930" / "checks.jsonl")
    assert [(x["against"], x["live"], x["changes"]) for x in log] == [(ID_BEFORE, ID_AFTER, 4), (ID_BEFORE, ID_BEFORE, 0)]


def test_changes_before_any_briefing_is_an_error(tmp_path, capsys):
    assert B.main(["--root", str(tmp_path), "changes", str(SESSION)]) == 2
    assert "Run `issue` first" in capsys.readouterr().err


def test_a_decision_is_kept_against_the_briefing_it_was_made_on(tmp_path):
    issue(tmp_path)
    issue(tmp_path, AFTER)
    row = B.decide(SESSION, tmp_path, "change", "Alex Example", "Moved to the backup spot.", iid=ID_BEFORE)
    assert (row["issue_id"], row["latest_issued"], row["decision"]) == (ID_BEFORE, False, "change")
    B.decide(SESSION, tmp_path, "go", "Alex Example", "")
    with pytest.raises(B.BriefingError, match="No briefing nope"):
        B.decide(SESSION, tmp_path, "go", "Alex Example", "", iid="nope")
    with pytest.raises(B.BriefingError, match="--decision must be"):
        B.decide(SESSION, tmp_path, "maybe", "Alex Example", "")
    found = B.find(tmp_path, org="example outdoor")
    assert [(r["manifest"]["issue_id"], [d["decision"] for d in r["decisions"]]) for r in found] == [(ID_BEFORE, ["change"]), (ID_AFTER, ["go"])]
    assert [r["manifest"]["issue_id"] for r in B.find(tmp_path, iid=ID_AFTER)] == [ID_AFTER]
    assert B.find(tmp_path, org="Another Centre") == [] and B.find(tmp_path, day="2026-10-23") == []
    # A fixed copy that changed is flagged.
    (Path(found[0]["folder"]) / "briefing.txt").write_text("edited")
    assert B.find(tmp_path, iid=ID_BEFORE)[0]["altered"] == ["briefing.txt has changed"]


def test_find_on_the_command_line(tmp_path, capsys):
    issue(tmp_path)
    B.decide(SESSION, tmp_path, "go", "Alex Example", "Checked the water at 08:00.")
    assert B.main(["--root", str(tmp_path), "find", "--org", "Example Outdoor Centre", "--date", "2026-10-22"]) == 0
    out = capsys.readouterr().out
    assert f"Example Outdoor Centre, Thursday 22 October 2026, 09:30: issue {ID_BEFORE}" in out
    assert "main: Wharfe at Cromwheel, Ilkley: High risk: rated poor" in out and "decision: go by Alex Example" in out
    assert "files: as issued" in out
    assert B.main(["--root", str(tmp_path), "find", "--org", "example", "--csv"]) == 0
    rows = capsys.readouterr().out.splitlines()
    assert rows[0].startswith("organisation,session_date") and rows[1].startswith(f"Example Outdoor Centre,2026-10-22,09:30,{ID_BEFORE},")
    assert "alex@example.org" not in "\n".join(rows)   # the log export carries no addresses


# ------------------------------------------------------------------ no recipient data in this repository
def test_the_archive_is_refused_inside_the_repository(monkeypatch):
    with pytest.raises(B.BriefingError, match="inside the public repository"):
        B.guard(ROOT / "briefings")
    monkeypatch.setenv("SWIMSIGNAL_BRIEFINGS", str(ROOT / "site" / "briefings"))
    with pytest.raises(B.BriefingError, match="inside the public repository"):
        B.archive_root(None)
    assert B.main(["find", "--org", "x"]) == 2
    assert B.archive_root("/tmp/elsewhere") == Path("/tmp/elsewhere")


def test_a_session_in_the_repository_with_real_addresses_is_refused(tmp_path, monkeypatch):
    p = tmp_path / "real.toml"
    p.write_text(SESSION.read_text().replace("alex@example.org", "alex@realcentre.co.uk"))
    monkeypatch.setattr(B, "public_repo", lambda q: ROOT if Path(q) == p else None)
    with pytest.raises(B.BriefingError, match="names real recipients"):
        issue(tmp_path / "root", session=p)


def test_issuing_writes_nothing_inside_the_repository(tmp_path):
    def state():
        r = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all", "--ignored"],
                           capture_output=True, text=True, check=True).stdout
        return {line for line in r.splitlines() if "__pycache__" not in line and ".pytest_cache" not in line}
    was = state()
    folder, _ = issue(tmp_path)
    B.decide(SESSION, tmp_path, "go", "Alex Example", "note")
    assert state() == was
    assert B.inside(folder, tmp_path) and not B.inside(folder, ROOT)


def test_no_session_file_in_the_repository_names_a_real_address():
    skip = {".venv", ".git", ".claude", "node_modules", "site"}
    files = [p for p in ROOT.rglob("*.toml") if not skip & set(p.relative_to(ROOT).parts)]
    assert SESSION in files
    import tomllib
    for p in files:
        d = tomllib.loads(p.read_text())
        for r in d.get("recipients", []) if isinstance(d.get("recipients"), list) else []:
            assert B.RESERVED.search(str(r.get("email", ""))), f"{p} names {r.get('email')}: keep real sessions in swimsignal-private"


# ------------------------------------------------------------------ the words it borrows, and the addresses
def test_the_words_are_still_the_pages_own():
    levels = (ROOT / "src" / "dipcast" / "site" / "levels.js").read_text()
    organisers = (ROOT / "src" / "dipcast" / "site" / "organisers.js").read_text()
    assert f"const FOUND_NONE = '{B.FOUND_NONE}';" in levels
    assert f"const OTHER_RISKS = '{B.OTHER_RISKS}';" in levels
    assert "NO_RIVER = 'no river connection'" in levels and "NO_OVERFLOWS = 'no overflows'" in levels and B.PLAIN == ("no overflows", "no river connection")
    assert "const ORDER = {low:0, moderate:1, high:2, 'very high':3};" in levels and B.ORDER == {"low": 0, "moderate": 1, "high": 2, "very high": 3}
    assert "const STALE_MIN = 8 * 60;" in organisers and B.STALE_MIN == 8 * 60
    assert "const DAYS = 5, AHEAD = DAYS - 1;" in organisers and B.AHEAD == 4
    for word in ("safe", "clean"):   # only ever in "never says the water is safe or clean"
        assert B.LIMITS.count(word) == 1 and "never says the water is safe or clean" in B.LIMITS
    assert "verified" not in (B.LIMITS + B.DECIDES).lower() and "certified" not in (B.LIMITS + B.DECIDES).lower()


def test_a_spot_with_no_level_never_reads_as_one():
    snap = B.Snapshot(BEFORE["spots.json"], {**BEFORE["alerts.json"], "spots": {"bw-uke4100-08901": {"level": "no overflows", "headline": B.FOUND_NONE}}})
    lines = B.spot_lines(snap, "bw-uke4100-08901", "2026-10-22", "main")
    assert lines[1] == f"Thursday 22 October 2026: {B.FOUND_NONE}." and lines[2] == f"This is not a risk level. {B.OTHER_RISKS}"
    # A day with no forecast is unknown, and says so.
    days = json.loads(json.dumps(BEFORE["alerts.json"]))
    days["spots"]["bw-uke4100-08901"]["days"][2] = None
    lines = B.spot_lines(B.Snapshot(BEFORE["spots.json"], days), "bw-uke4100-08901", "2026-10-22", "main")
    assert lines[1:3] == ["Thursday 22 October 2026: No forecast for this day.", "There is no level for this day: treat it as unknown, never as low."]


def test_the_page_addresses():
    s = B.load_session(SESSION)
    assert B.record_url("https://swimsignal.co.uk/", "bw-uke4100-08901", "2026-10-22", "Example & Co") == \
        "https://swimsignal.co.uk/record.html#spot=bw-uke4100-08901&day=2026-10-22&org=Example%20%26%20Co"
    u = B.sites_url("https://swimsignal.co.uk/", s)
    assert u.startswith("https://swimsignal.co.uk/sites.html#spots=bw-uke4100-08901,wharfe-burnsall&name=Thu%2022%20Oct%2009%3A30%2C%20Example")
    assert u.endswith("&day=2026-10-22")   # sites.js gives each spot's level on the session's day, by its date
    assert len(urllib.parse.unquote(u.split("&name=")[1].split("&day=")[0])) <= 40   # lists.js, LIST_NAME_MAX


# ------------------------------------------------------------------ the DevTools websocket
def test_the_websocket_reads_fragments_and_answers_pings():
    a, b = socket.socketpair()
    c = object.__new__(B.CDP)
    c.sock, c.buf, c.next_id, c.handlers, c.errors = a, bytearray(), 0, {}, []
    body = json.dumps({"id": 1, "result": {"data": "x" * 70000}}).encode()
    half = len(body) // 2

    def frame(fin, op, data):
        n = len(data)
        size = bytes([n]) if n < 126 else bytes([126]) + struct.pack(">H", n) if n < 65536 else bytes([127]) + struct.pack(">Q", n)
        return bytes([(0x80 if fin else 0) | op]) + size + data

    # From another thread: a socket pair holds far less than the 70 KB message.
    t = threading.Thread(target=b.sendall, args=(frame(False, 0x1, body[:half]) + frame(True, 0x9, b"hi") + frame(True, 0x0, body[half:]),))
    t.start()
    a.settimeout(5)
    assert c._message() == json.loads(body)
    t.join(5)
    # The pong, masked as a client's frames must be.
    b.settimeout(5)
    head = b.recv(2)
    assert head[0] == 0x8A and head[1] == 0x80 | 2
    mask, data = b.recv(4), b.recv(2)
    assert bytes(x ^ mask[i % 4] for i, x in enumerate(data)) == b"hi"
    c.send("Page.enable")
    raw = b.recv(1 << 16)
    n, mask = raw[1] & 0x7F, raw[2:6]
    assert json.loads(bytes(x ^ mask[i % 4] for i, x in enumerate(raw[6:6 + n]))) == {"id": 1, "method": "Page.enable", "params": {}}
    a.close()
    b.close()


def test_the_example_is_runnable_as_documented():
    doc = (ROOT / "docs" / "PILOT-SESSIONS.md").read_text()
    for cmd in ("issue", "changes", "decide", "find"):
        assert f"uv run python scripts/briefing.py {cmd}" in doc
    assert "tests/fixtures/briefings/session.toml" in doc
    assert os.path.exists(ROOT / "tests" / "fixtures" / "briefings" / "session.toml")
