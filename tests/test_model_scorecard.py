"""The model scorecard on the site (build_site.write_model_scorecard, models.html): the export
(docs/MODEL-SCORECARD-CONTRACT-v1.md) holds its contract, every quote is in its record, a running test shows its
window and read date and no score from its window before then, and an export of another schema is not published."""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "data" / "research" / "model_scorecard.v1.json"
RUNNING = {"regional-v1", "live-status", "lead-calibration-b", "company-calibration-a8", "ensemble-rain-d4",
           "upgraded-overflows-b"}


def _mod(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


def test_the_committed_export_holds_its_contract():
    doc = json.loads(EXPORT.read_text())
    assert _mod("export_model_scorecard").check(doc) == []
    stage = {m["id"]: m["stage"] for m in doc["models"]}
    assert stage == {"production": "live", **{i: "shadow" for i in RUNNING}, "winter-recalibration": "scheduled",
                     "spill-duration": "lab", "primary-2027": "not_started"}
    reads = {m["id"]: m["window"]["read_on"] for m in doc["models"] if m.get("window")}
    assert reads == {"regional-v1": "2026-11-28", "live-status": "2026-11-23", "lead-calibration-b": "2026-11-16",
                     "company-calibration-a8": "2026-11-25", "ensemble-rain-d4": "2026-11-21",
                     "upgraded-overflows-b": "2026-12-02", "winter-recalibration": "2027-03-09"}
    # Nothing from inside a window: every result is from before it, and the 2027 evaluation has none.
    assert all(x["data"] != "prospective" for m in doc["models"] for x in m["results"])


def test_the_check_refuses_a_changed_figure_an_early_score_and_a_lost_verdict():
    m, doc = _mod("export_model_scorecard"), json.loads(EXPORT.read_text())
    by = {x["id"]: x for x in doc["models"]}
    by["regional-v1"]["results"][2]["quote"] = by["regional-v1"]["results"][2]["quote"].replace("0.03633", "0.03533")
    by["live-status"]["results"].append({**by["live-status"]["results"][0], "label": "Interim", "data": "prospective"})
    by["spill-duration"]["verdict"]["quote"] = "Verdict: the gate passes."
    got = m.check(doc)
    assert any(e.startswith("regional-v1: regional-v1 rule") and "quote not found" in e for e in got)
    assert "live-status: Interim: a score from inside the window before its read date" in got
    assert any(e.startswith("spill-duration: verdict: quote not found") for e in got)
    doc["as_of"] = "2026-11-23"   # on the read date the same result is allowed (its quote is a real one)
    assert not any("Interim: a score" in e for e in m.check(doc))


def test_the_page_shows_every_model_with_its_stage(tmp_path):
    bs = _mod("build_site")
    assert bs.write_model_scorecard(tmp_path, today=date(2026, 11, 1)) == {"available": True, "models": 10,
                                                                           "version": "1.0.0"}
    html = (tmp_path / "models.html").read_text()
    assert "<title>Model scorecard · SwimSignal</title>" in html and "<!-- SCORECARD" not in html
    assert html.count('<dl class="fields">') == 10
    assert ("Running test: window 31 Oct 2026 to 27 Nov 2026. Read on or after 28 Nov 2026; no score from the window "
            "is shown before then.") in html
    assert "Scheduled: its window runs 14 Dec 2026 to 7 Mar 2027, read on or after 9 Mar 2027." in html
    assert "In the lab: not good enough yet to run beside the forecast. Next, 1 Dec 2026:" in html
    assert "Not started. Next, 1 May 2027:" in html
    assert "[0.00007, 0.00261]" in html and "7e" not in html   # small numbers in full
    assert "124,740 rows from 30 Oct 2026 to 31 Oct 2026. A count only" in html
    assert json.loads((tmp_path / "data" / "research" / "model_scorecard.json").read_text())["schema"] == \
        "swimsignal.model-scorecard"


def test_the_stage_follows_the_build_date(tmp_path):
    bs = _mod("build_site")
    bs.write_model_scorecard(tmp_path, today=date(2026, 11, 29))
    html = (tmp_path / "models.html").read_text()
    assert ("Window closed on 27 Nov 2026. The read was due on or after 28 Nov 2026; its result is not on this page "
            "yet.") in html
    bs.write_model_scorecard(tmp_path, today=date(2026, 12, 1))
    assert "Window closed on 30 Nov 2026. Read on or after 2 Dec 2026." in (tmp_path / "models.html").read_text()


def test_a_score_from_inside_a_window_is_not_shown_before_its_read(tmp_path):
    bs, doc = _mod("build_site"), json.loads(EXPORT.read_text())
    ls = next(m for m in doc["models"] if m["id"] == "live-status")
    ls["results"] = [{**ls["results"][0], "label": "Interim window score", "data": "prospective"}]
    p = tmp_path / "early.json"
    p.write_text(json.dumps(doc))
    bs.write_model_scorecard(tmp_path, path=p, today=date(2026, 11, 22))
    assert "Interim window score" not in (tmp_path / "models.html").read_text()
    bs.write_model_scorecard(tmp_path, path=p, today=date(2026, 11, 23))
    assert "Interim window score" in (tmp_path / "models.html").read_text()


def test_another_schema_is_not_published(tmp_path):
    bs = _mod("build_site")
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"schema": "swimsignal.model-scorecard", "version": "2.0.0"}))
    h = bs.write_model_scorecard(tmp_path, path=other)
    assert h["available"] is False and "not swimsignal.model-scorecard 1.x" in h["why"]
    assert "No scorecard is published in this build." in (tmp_path / "models.html").read_text()
    assert not (tmp_path / "data" / "research" / "model_scorecard.json").exists()
