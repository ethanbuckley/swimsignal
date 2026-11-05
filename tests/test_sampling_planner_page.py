"""The sampling planner on the site (build_site.write_sampling_planner, sampling-planner.html): the export
(docs/SAMPLING-PLANNER-CONTRACT-v1.md) holds its contract and copies the simulation's failed verdict as it is, the page
shows where samples are thin and keeps its priorities apart from any plan, and an export of another schema is not
published."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "data" / "research" / "sampling_planner.v1.json"


def _mod(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


def test_the_committed_export_holds_its_contract_and_the_simulations_figures():
    doc = json.loads(EXPORT.read_text())
    assert _mod("export_sampling_planner").check(doc) == []
    assert doc["field_validation"] is False
    c = doc["coverage"]
    assert (c["samples"], len(c["sites"]), c["by_month"], c["outside_months"]) == (2265, 38, [365, 516, 516, 488, 380], 0)
    assert (c["wet"]["rows"], c["wet"]["wet_rows"], c["wet"]["sites"]) == (1537, 327, 32)   # the concentration study's table
    assert {k: c["spots"][k] for k in ("total", "with_ea", "with_local", "none_rivers", "none_lakes")} == \
        {"total": 109, "with_ea": 38, "with_local": 1, "none_rivers": 52, "none_lakes": 18}
    # As docs/SAMPLING-PRIORITIES-SIM-2026-10.md reports them: copied, never recomputed.
    sim = doc["simulation"]
    main = sim["runs"][0]
    assert sim["verdict"] == "fail" and main["run"] == "main" and main["replications"] == 200
    assert main["info_vs"]["COVER"] == {"share_info_lower": 0.585, "mean_gain": 0.000189, "ci95": [0.000077, 0.000306]}
    assert main["info_vs"]["RANDOM"]["share_info_lower"] == 0.73
    assert [r["info_vs"]["COVER"]["share_info_lower"] for r in sim["runs"]] == [0.585, 0.66, 0.51]


def test_the_check_refuses_an_export_that_passes_the_simulation_or_claims_a_plan():
    m, doc = _mod("export_sampling_planner"), json.loads(EXPORT.read_text())
    doc["simulation"]["verdict"] = "pass"
    doc["claim"]["public_wording"] = "Where to sample next."
    doc["field_validation"] = True
    assert m.check(doc) == ["field_validation must be false until a field study says otherwise",
                            "the claim must say it is not a sampling plan",
                            "the simulation's verdict is fail and must be said"]


def test_the_page_shows_coverage_the_failed_verdict_and_priorities_apart_from_a_plan(tmp_path):
    bs = _mod("build_site")
    assert bs.write_sampling_planner(tmp_path) == {"available": True, "version": "1.0.0"}
    html = (tmp_path / "sampling-planner.html").read_text()
    assert "<title>Sampling planner · SwimSignal</title>" in html and "<!-- SP" not in html
    assert "not a sampling plan: nothing here has been tested in real water" in html
    assert "70 of SwimSignal's 109 spots (52 rivers and 18 lakes) have no lab samples here." in html
    assert "327 (21%) came after more than 10 mm in 48 hours: 124 of 900 at rivers and 203 of 637 at lakes" in html
    assert html.count('<tr><th scope="row">') == 38 + 12 + 4 + 3   # bathing waters, areas, policies, runs
    assert '<tr><th scope="row">Sandy Lane, Chester</th><td>river</td><td class="num">20</td>' in html
    assert "<b>The information policy failed its test.</b>" in html
    assert "had it in 58.5%. Its mean gain over equal coverage was 0.000189 (95% interval 0.000077 to 0.000306)" in html
    assert "−0.000066 to 0.000179" in html   # the budget-120 check, which spans 0
    # The priorities come after the simulation and the cost, under their own heading, and say they are not a plan.
    at = html.index("<h2>Suggested priorities, not a plan</h2>")
    assert html.index("failed its test") < html.index('id="sp-calc"') < at
    assert "SwimSignal does not choose where or when anyone samples" in html[at:]
    assert "Only a field study." in html and "#the-field-study-an-efficiency-claim-would-need" in html
    runs = json.loads(bs.unescape(html.split('data-runs="')[1].split('"')[0]))
    assert [(r["run"], r["per_site"]) for r in runs] == [("main", 5.0), ("tau0", 5.0), ("budget120", 10.0)]
    assert '<script src="sampling-planner.js?v=' in html and (tmp_path / "sampling-planner.js").exists()


def test_another_schema_is_not_published(tmp_path):
    bs = _mod("build_site")
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"schema": "swimsignal.sampling-planner", "version": "2.0.0"}))
    h = bs.write_sampling_planner(tmp_path, path=other)
    assert h["available"] is False and "not swimsignal.sampling-planner 1.x" in h["why"]
    html = (tmp_path / "sampling-planner.html").read_text()
    assert "No planning figures are published in this build." in html and "id=\"sp-calc\"" not in html


def test_research_links_the_planner(tmp_path):
    page = (ROOT / "src" / "dipcast" / "pages" / "research.html").read_text()
    assert '<h3><a href="/sampling-planner">Sampling planner</a></h3>' in page
    assert ('href="/sampling-planner"', 'href="sampling-planner.html"') in _mod("build_site").REWRITES
