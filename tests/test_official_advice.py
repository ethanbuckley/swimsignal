"""Official advice on a spot's page (src/dipcast/official_advice.py, eatoday.js eaTodayOfficial): the
build reads the reviewed file and the finder's last check, makes no request, and writes the advice into
spots.json and the prerendered page. Every approval here is a fixture: the repo's approved.json stays
as Ethan and his reviewers leave it. The draft is the finder's own, from its saved answers of 26 Oct 2026."""

import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import advisories as adv

from dipcast import official_advice as oa

FIX = ROOT / "tests" / "fixtures" / "advisories"
NOW = datetime(2026, 10, 26, 19, 0, tzinfo=oa.TZ)
FRENSHAM = "bw-ukj2310-11945"
LINE = "Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026"
PROFILE = "https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945"


@pytest.fixture(scope="module")
def run():
    return adv.run(fixtures=FIX, now=NOW, gazetteer=adv.Gazetteer.load(ROOT))


def feed_draft(result):
    return next(d for d in result["drafts"] if d["spot_id"] == FRENSHAM and d["source"]["key"] == "ea-open")


def entry(result, **change):
    e = adv.review_entry(feed_draft(result))
    return {**e, "reviewer": "Ethan Buckley", "authority": "Ethan Buckley", "reviewed_at": "2026-10-26T18:50:00Z", **change}


def write(tmp_path, *entries, name="approved.json"):
    f = tmp_path / name
    f.write_text(json.dumps({"approvals": list(entries)}))
    return f


def shown(tmp_path, entries, check, now=NOW):
    return oa.shown(oa.load_approvals(write(tmp_path, *entries), now=now), check, now)


def test_review_entry_carries_the_evidence_and_leaves_the_review_empty(run):
    e = adv.review_entry(feed_draft(run))
    assert e == {"draft_id": "e8b5832d974a", "spot_id": FRENSHAM, "line": LINE, "publisher": "Environment Agency",
                 "link": PROFILE, "kind": "feed", "source_url": adv.EA_OPEN, "incident_id": "ea:11945-20260619-142800",
                 "start": "2026-06-19", "expiry": None, "fetched_at": "2026-10-26T18:37:19Z",
                 "reviewer": None, "authority": None, "reviewed_at": None}
    with pytest.raises(oa.ApprovalError, match="missing reviewer, authority, reviewed_at"):
        oa.load_approvals(write(Path(__import__("tempfile").mkdtemp()), e), now=NOW)


def test_reviewers_and_their_authority_are_a_short_configured_list(tmp_path, run):
    assert oa.REVIEWERS == (("Ethan Buckley", "Ethan Buckley"),
                            ("Codex", "Codex, under Ethan Buckley's delegation of routine decisions, 26 Oct 2026"))
    codex = entry(run, reviewer="Codex", authority=oa.REVIEWERS[1][1])
    got = oa.load_approvals(write(tmp_path, codex), now=NOW)["e8b5832d974a"]
    assert (got["reviewer"], got["authority"]) == oa.REVIEWERS[1]
    for who, auth in [("Codex", "Ethan Buckley"), ("Ethan Buckley", oa.REVIEWERS[1][1]), ("Claude", "Claude")]:
        with pytest.raises(oa.ApprovalError, match="may not review"):
            oa.load_approvals(write(tmp_path, entry(run, reviewer=who, authority=auth)), now=NOW)


def test_a_checked_advisory_shows_with_its_publisher_start_link_and_check(tmp_path, run):
    got = shown(tmp_path, [entry(run)], oa.check_record(run))
    assert got == {FRENSHAM: [{"line": LINE, "publisher": "Environment Agency", "link": PROFILE, "since": "2026-06-19",
                               "checked": "2026-10-26", "state": "checked"}]}


def test_nothing_without_an_approval(tmp_path, run):
    assert shown(tmp_path, [], oa.check_record(run)) == {}
    assert shown(tmp_path, [], None) == {}
    # The repo's own file, whatever it holds, loads; with no entries the pages say nothing new.
    oa.load_approvals(oa.APPROVALS_FILE, now=datetime.now(oa.TZ))


def test_the_check_record_keeps_status_and_times_not_words(run):
    rec = oa.check_record(run)
    assert rec["checked_at"] == "2026-10-26T19:00:00Z" and rec["sources"]["ea-open"] == "ok"
    d = rec["drafts"]["e8b5832d974a"]
    assert d == {"spot_id": FRENSHAM, "status": "open", "flags": [], "current": True,
                 "fetched_at": "2026-10-26T18:37:19Z", "superseded_by": None, "source": "ea-open"}
    assert all(k not in json.dumps(rec) for k in ("evidence", "draft_line"))
    assert all(x["spot_id"] for x in rec["drafts"].values())   # unmatched coastal drafts are left out


def test_an_old_check_shows_the_advisory_as_not_rechecked(tmp_path, run):
    check = oa.check_record(run)
    later = NOW + timedelta(days=oa.RECHECK_DAYS)
    assert shown(tmp_path, [entry(run)], check, later)[FRENSHAM][0]["state"] == "checked"
    stale = shown(tmp_path, [entry(run)], check, later + timedelta(days=1))[FRENSHAM][0]
    assert stale["state"] == "stale" and stale["checked"] == "2026-10-26"
    # No check file at all, or one that cannot be read: shown, as not re-checked since the evidence was fetched.
    for none in (None, oa.load_check(tmp_path / "missing.json")):
        assert shown(tmp_path, [entry(run)], none)[FRENSHAM] == [dict(stale, checked="2026-10-26")]


def test_a_failed_check_keeps_the_advisory_marked_unverified(tmp_path, run):
    # The next week's run cannot read the EA's list: the finder brings the draft back flagged unverified.
    gone = tmp_path / "gone"
    gone.mkdir()
    (gone / "manifest.json").write_text(json.dumps({"sources": [
        {"key": "ea-open", "file": "missing.json", "url": adv.EA_OPEN, "fetched_at": "x"}]}))
    week = NOW + timedelta(days=7)
    again = adv.run(fixtures=gone, now=week, previous=run["drafts"], gazetteer=adv.Gazetteer.load(ROOT))
    assert "unverified" in next(d for d in again["drafts"] if d["draft_id"] == "e8b5832d974a")["flags"]
    got = shown(tmp_path, [entry(run)], oa.check_record(again), week)[FRENSHAM]
    assert got == [{"line": LINE, "publisher": "Environment Agency", "link": PROFILE, "since": "2026-06-19",
                    "checked": "2026-10-26", "state": "unverified"}]


@pytest.mark.parametrize("status", ["withdrawn", "lifted"])
def test_withdrawn_or_lifted_at_the_source_is_not_shown(tmp_path, run, status):
    check = oa.check_record(run)
    check["drafts"]["e8b5832d974a"]["status"] = status
    assert shown(tmp_path, [entry(run)], check) == {}


def test_superseded_by_an_ended_notice_is_not_shown_and_by_an_open_one_is(tmp_path, run):
    check = oa.check_record(run)
    check["drafts"]["e8b5832d974a"].update(flags=["superseded"], superseded_by="aaaaaaaaaaaa")
    check["drafts"]["aaaaaaaaaaaa"] = {"spot_id": FRENSHAM, "status": "lifted", "flags": [], "fetched_at": "2026-10-26T18:37:19Z"}
    assert shown(tmp_path, [entry(run)], check) == {}
    check["drafts"]["aaaaaaaaaaaa"]["status"] = "update"
    assert shown(tmp_path, [entry(run)], check)[FRENSHAM][0]["line"] == LINE


def test_expiry_stated_and_the_page_term(tmp_path, run):
    check = oa.check_record(run)
    assert shown(tmp_path, [entry(run, expiry="2026-10-26")], check)[FRENSHAM]          # until the end of that day
    assert shown(tmp_path, [entry(run, expiry="2026-10-25")], check) == {}
    page = entry(run, kind="page", draft_id="0123456789ab", reviewed_at="2026-10-12T09:00:00Z")
    assert shown(tmp_path, [page], check)[FRENSHAM]                                      # day 14 after review
    assert shown(tmp_path, [page], check, NOW + timedelta(days=1)) == {}                 # day 15: lapsed
    # A page that states its end keeps it, past the 14 days.
    assert shown(tmp_path, [dict(page, expiry="2026-11-30")], check, NOW + timedelta(days=10))[FRENSHAM]


def test_conflicting_advisories_are_both_shown_newest_first(tmp_path, run):
    older = entry(run)
    newer = entry(run, draft_id="0123456789ab", line="Waverley Borough Council: advice against swimming (harmful algae) since 20 Oct 2026",
                  publisher="Waverley Borough Council", kind="page", start="2026-10-20", incident_id=None,
                  link="https://www.waverley.gov.uk/council-updates/read-our-latest-news/visitors-to-frensham-reminded-do-not-enter-water")
    got = shown(tmp_path, [older, newer], oa.check_record(run))[FRENSHAM]
    assert [x["since"] for x in got] == ["2026-10-20", "2026-06-19"]
    assert got[0]["state"] == "stale"   # the newer one is not in the check record: shown, as not re-checked


def test_a_bad_approvals_file_shows_nothing_and_says_so(tmp_path, run):
    bs = _build_site()
    results = [{"id": FRENSHAM, "name": "Frensham Great Pond"}]
    bad = write(tmp_path, entry(run, reviewer="Someone"))
    out = bs.attach_official_advice(results, approvals=bad, check=tmp_path / "none.json", now=NOW)
    assert out["shown"] == 0 and "may not review" in out["error"] and "official" not in results[0]


def _build_site():
    import build_site
    return build_site


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_the_build_writes_the_advice_into_spots_json_and_the_built_page(tmp_path, run):
    bs = _build_site()
    check = tmp_path / "last_check.json"
    check.write_text(json.dumps(oa.check_record(run)))
    days = [{"date": f"2026-10-{26 + i}", "risk": 0.01, "label": "low"} for i in range(5)]
    spot = {"id": FRENSHAM, "name": "Frensham Great Pond", "kind": "lake", "source": "designated", "days": days,
            "upstream_summary": {"overflows": 2}, "location": {"mode": "lake"}, "now": {"label": "low", "discharging_upstream": 0},
            "contributors": [], "classification": {"class": "excellent", "year": 2025, "url": PROFILE}}
    other = {**spot, "id": "a", "name": "A river", "classification": None, "source": "curated"}
    results = [spot, other]
    out = bs.attach_official_advice(results, approvals=write(tmp_path, entry(run)), check=check, now=NOW)
    assert out == {"shown": 1, "states": {"checked": 1}} and "official" not in other
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "spots.json").write_text(json.dumps({"generated_at": "2026-10-26T20:00:00+00:00", "spots": results}))
    bs.write_app_data(tmp_path, {"generated_at": "2026-10-26T20:00:00+00:00", "spots": results})
    lite = json.loads((tmp_path / "data" / "spots-lite.json").read_text())["spots"]
    assert lite[0]["official"] == spot["official"] and "official" not in lite[1]
    bs.write_pages(tmp_path, results, root="https://example.org/swim/")
    page = (tmp_path / "spot" / FRENSHAM / "index.html").read_text()
    block = ('<section class="notice official" id="official" aria-labelledby="official-h"><h2 id="official-h">Official advice</h2><ul>'
             f'<li><p class="o-line">{LINE}</p><p class="o-src"><a href="{PROFILE}">Open the Environment Agency page</a>. '
             'Last checked 26 Oct 2026.</p></li></ul><p class="o-sep">Follow this advice first. It is not SwimSignal\'s, '
             'and the forecast below does not include it.</p></section>')
    assert block in page
    # Above the level, which keeps its own words and is said to be SwimSignal's forecast, apart from it.
    assert page.index('<h1 class="spot-name"') < page.index(block) < page.index('id="risk-headline">Low risk')
    assert '<p class="gaps o-apart">This level is SwimSignal\'s forecast. The official advice above is separate.</p>' in page
    plain = (tmp_path / "spot" / "a" / "index.html").read_text()
    assert 'id="official"' not in plain and "o-apart" not in plain and 'id="risk-headline">Low risk' in plain
    assert "bwq/widget" not in page


def test_the_build_side_reader_makes_no_request():
    src = (ROOT / "src" / "dipcast" / "official_advice.py").read_text()
    assert "httpx" not in src and "urllib" not in src and "requests" not in src and "advisories import" not in src


def test_an_ended_advisory_stays_ended_after_it_leaves_the_drafts(tmp_path, run):
    # Week 1 the EA lists the incident as lifted; week 2 the finder no longer has the draft at all.
    ended = oa.check_record(run)
    ended["drafts"]["e8b5832d974a"]["status"] = "lifted"
    later = dict(run, drafts=[d for d in run["drafts"] if d["draft_id"] != "e8b5832d974a"])
    week2 = oa.check_record(later, previous=ended)
    assert week2["drafts"]["e8b5832d974a"]["status"] == "lifted"
    assert shown(tmp_path, [entry(run)], week2) == {}
    # Without the carried record it would come back, marked not re-checked: never a silent all-clear,
    # but not right either for an advisory the source ended.
    assert shown(tmp_path, [entry(run)], oa.check_record(later))[FRENSHAM][0]["state"] == "stale"


def test_a_fixture_run_does_not_write_the_check_record(tmp_path, monkeypatch):
    import advisory_finder
    monkeypatch.setattr(advisory_finder.config, "CACHE", tmp_path)
    check = tmp_path / "last_check.json"
    empty = write(tmp_path, name="empty.json")
    assert advisory_finder.main(["--dry-run", "--fixtures", str(FIX), "--now", NOW.isoformat(), "--approvals", str(empty),
                                 "--check-file", str(check), "--entry", "e8b5832d974a"]) == 0
    assert not check.exists()


def test_the_committed_check_record_is_readable_and_from_a_live_run():
    rec = oa.load_check(oa.CHECK_FILE)
    assert rec is not None and rec["mode"] == "live"
    assert all(d["spot_id"] and d["status"] in ("open", "update", "withdrawn", "lifted") for d in rec["drafts"].values())
