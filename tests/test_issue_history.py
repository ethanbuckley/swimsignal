"""The issued-forecast history (src/dipcast/issue_history.py): records made by the page's own rules at issue time,
kept only ever added to, never a reconstruction, and the previous successful issue published for the pages to
compare with. Built from two real issues of the live site (tests/fixtures/forecast_why: three spots each, issued
29 Oct 18:57 and 30 Oct 17:49 UTC), and read back by the page's own reader (since.js, lastSaid) in Node."""

import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from dipcast import issue_history as H

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "forecast_why"
OLD, NEW = FIX / "issue-2026-10-29T1857.json", FIX / "issue-2026-10-30T1749.json"


def at(p: Path) -> pd.Timestamp:
    return pd.Timestamp(json.loads(p.read_text())["generated_at"])


def test_the_issue_id_is_the_printed_records(tmp_path):
    # printed.js, issueId: the commit, then the issue time in UTC to the minute.
    assert H.issue_id("3ed1b5a", pd.Timestamp("2026-10-20T13:16:40+01:00")) == "3ed1b5a-20261020T1216Z"
    assert H.issue_id(None, pd.Timestamp("2026-10-20T12:16:00Z")) == "nogit-20261020T1216Z"


def test_records_come_from_the_pages_own_rules():
    doc = H.make_records(NEW)
    assert doc["issued_at"] == "2026-10-30T17:49:19.000245+00:00"
    assert sorted(doc["records"]) == ["avon-warleigh-weir", "medway-tonbridge", "osm-dart-dartington"]
    r = doc["records"]["medway-tonbridge"]
    # What the page shows and the inputs behind it; never the moment someone looked.
    assert r["level"] == "very high" and r["forecast"] == doc["issued_at"] and "at" not in r
    assert {"date", "level", "by", "score", "rain", "expect", "missing"} <= set(r["days"][0])
    assert {"discharging", "gap", "recent", "nowScore", "reporting", "upstream", "model", "official"} <= set(r)


def test_rows_are_only_added_and_an_issue_is_never_rewritten(tmp_path):
    old, new = H.make_records(OLD), H.make_records(NEW)
    a = H.append(old, "92a4ebd", now=at(OLD), state=tmp_path)
    assert (a["issue_id"], a["added"], a["file"]) == ("92a4ebd-20261029T1857Z", 3, "issued-2026-10.parquet")
    assert H.append(new, "746eddb", now=at(NEW), state=tmp_path)["added"] == 3
    # The same issue again (a rerun): nothing added.
    assert H.append(new, "746eddb", now=at(NEW), state=tmp_path)["added"] == 0
    # The same issue with a different record: refused, and the file is as it was.
    changed = json.loads(json.dumps(new))
    changed["records"]["medway-tonbridge"]["level"] = "low"
    before = (tmp_path / "issued-2026-10.parquet").read_bytes()
    with pytest.raises(H.HistoryError, match="never rewritten"):
        H.append(changed, "746eddb", now=at(NEW), state=tmp_path)
    assert (tmp_path / "issued-2026-10.parquet").read_bytes() == before
    df = pd.read_parquet(tmp_path / "issued-2026-10.parquet")
    assert len(df) == 6 and set(df["source"]) == {"issued"}


def test_a_reconstruction_is_never_kept_as_an_issue(tmp_path):
    # An issue time more than six hours before the clock is a forecast made later for a past time.
    with pytest.raises(H.HistoryError, match="reconstruction"):
        H.append(H.make_records(OLD), "92a4ebd", now=at(OLD) + pd.Timedelta(hours=7), state=tmp_path)
    assert not (tmp_path / "issued-2026-10.parquet").exists()


def test_the_previous_issue_is_the_last_kept_before_and_never_a_stale_one(tmp_path):
    new = H.make_records(NEW)
    # None kept yet: said as the first.
    assert H.since_last(new, "746eddb", tmp_path)["why"] == "first"
    H.append(H.make_records(OLD), "92a4ebd", now=at(OLD), state=tmp_path)
    s = H.since_last(new, "746eddb", tmp_path)
    assert s["previous"] == {"issue_id": "92a4ebd-20261029T1857Z", "issued_at": "2026-10-29T18:57:31.974830+00:00"}
    assert sorted(s["spots"]) == ["avon-warleigh-weir", "medway-tonbridge", "osm-dart-dartington"]
    # Never the issue itself, once it is kept too.
    H.append(new, "746eddb", now=at(NEW), state=tmp_path)
    assert H.since_last(new, "746eddb", tmp_path)["previous"]["issue_id"] == "92a4ebd-20261029T1857Z"
    # Over a day since the last kept issue (builds that failed or did not run): not compared with.
    later = {**new, "issued_at": (at(NEW) + pd.Timedelta(hours=25)).isoformat()}
    s = H.since_last(later, "746eddb", tmp_path)
    assert (s["previous"], s["why"], s["spots"]) == (None, "stale", {})


def test_the_previous_issue_is_found_across_a_month_end(tmp_path):
    old = H.make_records(NEW)   # 30 Oct 17:49
    H.append(old, "746eddb", now=at(NEW), state=tmp_path)
    nov = {**old, "issued_at": "2026-11-01T00:10:00+00:00"}
    assert H.month_file(pd.Timestamp(nov["issued_at"]), tmp_path).name == "issued-2026-11.parquet"
    # 30 h before: stale. One at 31 Oct 23:50, in October's file, is found from November.
    assert H.since_last(nov, "abc1234", tmp_path)["why"] == "stale"
    H.append({**old, "issued_at": "2026-10-31T23:50:00+00:00"}, "746eddb", now=pd.Timestamp("2026-10-31T23:55Z"), state=tmp_path)
    assert H.since_last(nov, "abc1234", tmp_path)["previous"]["issue_id"] == "746eddb-20261031T2350Z"


def test_the_build_step_publishes_the_previous_issue_and_a_rebuild_keeps_nothing(tmp_path):
    site, state = tmp_path / "site", tmp_path / "state"
    (site / "data").mkdir(parents=True)
    shutil.copy(OLD, site / "data" / "spots-lite.json")
    h = H.record_and_publish(site, "92a4ebd", now=at(OLD), state=state)
    assert (h["why"], h["added"]) == ("first", 3)
    shutil.copy(NEW, site / "data" / "spots-lite.json")
    h = H.record_and_publish(site, "746eddb", now=at(NEW), state=state, keep=False)   # a rebuild from cached results
    assert h["previous"] == "92a4ebd-20261029T1857Z" and "added" not in h
    assert len(pd.read_parquet(state / "issued-2026-10.parquet")) == 3


def test_what_the_writer_keeps_the_pages_reader_reads(tmp_path):
    """Writer -> Parquet -> since-last.json -> since.js lastSaid in Node, against the forecast on the page."""
    site, state = tmp_path / "site", tmp_path / "state"
    (site / "data").mkdir(parents=True)
    H.append(H.make_records(OLD), "92a4ebd", now=at(OLD), state=state)
    shutil.copy(NEW, site / "data" / "spots-lite.json")
    H.record_and_publish(site, "746eddb", now=at(NEW), state=state)
    js = """
      const fs = require('fs'), L = require('./src/dipcast/site/levels.js'), S = require('./src/dipcast/site/since.js');
      const f = JSON.parse(fs.readFileSync(process.argv[1])), lite = JSON.parse(fs.readFileSync(process.argv[2]));
      L.setToday('2026-10-30');
      const out = {};
      for (const s of lite.spots) out[s.id] = S.lastSaid(f, f.spots[s.id], S.seenRecord(s, lite.generated_at, Date.now()));
      process.stdout.write(JSON.stringify(out));"""
    said = json.loads(subprocess.run(["node", "-e", js, str(site / "data" / "since-last.json"), str(NEW)], cwd=ROOT,
                                     capture_output=True, text=True, check=True).stdout)
    assert said["osm-dart-dartington"].startswith("Since the update issued Thu 18:57, 22 h 52 min before this one: ")
    assert "Monday: moderate risk then, low risk now. What changed in the inputs: A small change: sewage spill risk 16 of 100" in said["osm-dart-dartington"]
    assert "Today: low risk then, very high risk now." in said["medway-tonbridge"]
    assert "Overflows upstream reported discharging: 1 then, 0 now." in said["medway-tonbridge"]
