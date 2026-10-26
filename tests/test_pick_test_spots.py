"""The comprehension-test spot picker (scripts/pick_test_spots.py): which spots suit tasks 2 and 3 on the
morning of a session, by the spot page's own headline and its own rules for each gap. Network-free."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("pick_test_spots", ROOT / "scripts" / "pick_test_spots.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pick_test_spots"] = mod
    spec.loader.exec_module(mod)
    return mod


pick = _load()
AREA = "Cumbria and the Lake District"


def spot(id, *, area=AREA, mode="river", overflows=2, no_live=0, season=False, ecoli=0.2, source="curated",
         classification=None, access=None, guide=None, days=True):
    return {"id": id, "name": id.replace("-", " ").title(), "area": area, "kind": "lake" if mode == "lake" else "river",
            "location": {"mode": mode}, "source": source, "classification": classification, "access": access,
            "guide": guide, "upstream_summary": {"overflows": overflows, "without_live_feed": no_live},
            "days": [{"date": "2026-10-25", "in_validated_season": season, "p_ecoli_gt900": ecoli}] if days else []}


def test_headline_is_read_from_the_built_page():
    page = '<div><h2 class="big low" id="risk-headline">Low risk from sewage&nbsp;spills</h2></div>'
    assert pick.headline(page) == "Low risk from sewage spills"
    assert pick.headline("<p>no answer built</p>") is None


def test_gaps_follow_the_page_rules():
    guided = {"facts": [{"topic": "path", "status": "confirmed"}]}
    assert pick.gaps(spot("a", guide=guided)) == ["ecoli_out_of_season"]
    # In season, no feed missing, guided: nothing the page leaves unsaid.
    assert pick.gaps(spot("b", season=True, guide=guided)) == []
    # A river without an E. coli figure that day has no untested figure to show.
    assert pick.gaps(spot("c", ecoli=None, guide=guided)) == []
    assert pick.gaps(spot("d", no_live=1, guide=guided)) == ["no_live_feed", "ecoli_out_of_season"]
    # A lake: no estimate at all, whatever the month (levels.js ecoliTested).
    assert pick.gaps(spot("e", mode="lake", guide=guided)) == ["lake_no_ecoli"]
    # A designated bathing water with a rating: today's EA advice is not checked (levels.js eaUnchecked).
    assert "ea_advice_not_checked" in pick.gaps(spot("f", source="designated", classification={"class": "good"}, guide=guided))
    assert "ea_advice_not_checked" not in pick.gaps(spot("g", source="designated", guide=guided))
    assert "access_unconfirmed" in pick.gaps(spot("h", access={"status": "unconfirmed"}))
    assert "no_access_info" in pick.gaps(spot("i"))
    assert "no_access_info" not in pick.gaps(spot("j", access={"status": "confirmed"}))


def test_candidates_keep_to_the_area_and_order_each_task():
    guided = {"facts": [{"status": "confirmed"}]}
    spots = [spot("plain-low", mode="lake", guide=guided), spot("gappy-low", no_live=1),
             spot("high-gappy", no_live=2, source="designated", classification={"class": "poor"}),
             spot("no-overflows", overflows=0, mode="lake", guide=guided), spot("elsewhere", area="Yorkshire")]
    heads = {"plain-low": "Low risk from sewage spills", "gappy-low": "Low risk from sewage spills",
             "high-gappy": "High risk from sewage spills", "no-overflows": "No monitored overflow found upstream",
             "elsewhere": "Low risk from sewage spills"}
    got = pick.candidates(spots, heads, AREA)
    assert got["spots"] == 4
    # Low risk with overflows upstream, the page with fewest gaps first; none without overflows.
    assert [r["id"] for r in got["task2"]] == ["plain-low", "gappy-low"]
    # At least one gap besides a lake's missing estimate, most gaps first.
    assert [r["id"] for r in got["task3"]] == ["high-gappy", "gappy-low"]


def test_report_and_main_from_a_local_build(tmp_path, capsys):
    spots = [spot("rydal-water", mode="lake", overflows=1, guide={"facts": [{"status": "confirmed"}]}),
             spot("blea-tarn", mode="lake", overflows=0)]
    (tmp_path / "spots.json").write_text(json.dumps({"generated_at": "2026-10-25T08:00:00+00:00", "spots": spots}))
    for s, h in (("rydal-water", "Low risk from sewage spills"), ("blea-tarn", "No monitored overflow found upstream")):
        (tmp_path / "spot" / s).mkdir(parents=True)
        (tmp_path / "spot" / s / "index.html").write_text(f'<h2 class="big low" id="risk-headline">{h}</h2>')
    assert pick.main(["--area", AREA, "--spots", str(tmp_path / "spots.json"), "--pages", str(tmp_path / "spot")]) == 0
    out = capsys.readouterr().out
    assert "Forecast issued 2026-10-25T08:00:00+00:00" in out
    assert "| Rydal Water | https://swimsignal.co.uk/spot/rydal-water/ | Low risk from sewage spills | 1 |" in out
    assert "| Blea Tarn | https://swimsignal.co.uk/spot/blea-tarn/ |" in out and "no access information" in out
    # An unknown area lists the known ones and fails.
    assert pick.main(["--area", "Atlantis", "--spots", str(tmp_path / "spots.json"), "--pages", str(tmp_path / "spot")]) == 2
    assert AREA in capsys.readouterr().err


def test_a_page_without_a_readable_headline_is_no_candidate(tmp_path, capsys):
    """A failed page read (or a page with no headline) leaves a spot out of both tasks, with a warning."""
    gapped = spot("broken-page", no_live=2, source="designated", classification={"class": "poor"})
    low = spot("broken-low")
    got = pick.candidates([gapped, low], {"broken-page": None, "broken-low": ""}, AREA)
    assert got["task2"] == [] and got["task3"] == []
    assert [r["id"] for r in got["unreadable"]] == ["broken-page", "broken-low"] and got["spots"] == 2
    assert "Warning: these pages could not be read" in pick.report(got, None)
    # Through main: one page missing from a local build is skipped and named on stderr.
    (tmp_path / "spots.json").write_text(json.dumps({"generated_at": "2026-10-25T08:00:00+00:00", "spots": [gapped, low]}))
    (tmp_path / "spot" / "broken-low").mkdir(parents=True)
    (tmp_path / "spot" / "broken-low" / "index.html").write_text('<h2 id="risk-headline">Low risk from sewage spills</h2>')
    assert pick.main(["--area", AREA, "--spots", str(tmp_path / "spots.json"), "--pages", str(tmp_path / "spot")]) == 0
    cap = capsys.readouterr()
    assert "broken-page" in cap.err and "left out of both lists" in cap.err
    assert "| Broken Low |" in cap.out and "| Broken Page |" not in cap.out


def test_task3_ranks_by_the_gaps_that_qualify_a_spot():
    """A lake's missing estimate qualifies no spot for task 3, so it does not rank one either: a river with two
    real gaps comes before a lake with one, and the report says how many qualifying spots it leaves out."""
    guided = {"facts": [{"status": "confirmed"}]}
    lakes = [spot(f"a-lake-{i}", mode="lake", no_live=1, guide=guided) for i in range(6)]
    river = spot("b-river", no_live=1, guide=guided)
    assert pick.gaps(lakes[0]) == ["no_live_feed", "lake_no_ecoli"]
    assert pick.gaps(river) == ["no_live_feed", "ecoli_out_of_season"]
    heads = {s["id"]: "Moderate risk from sewage spills" for s in [*lakes, river]}
    got = pick.candidates([*lakes, river], heads, AREA)
    assert got["task3"][0]["id"] == "b-river"
    text = pick.report(got, "2026-10-26T12:00:00+00:00")
    assert "spot/b-river/" in text and "2 more qualify; they are not shown." in text
