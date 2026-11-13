"""CATCH-SIM's what-if mode (docs/CATCH-SIM-2026-12.md): the export keeps the rules the protocol fixed, and the site
build leaves the prototype out. The export itself is made offline by scripts/lab_catch_sim.py; these read its files."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site  # noqa: E402

WHATIF = ROOT / "prototypes" / "research-lab" / "workspace" / "whatif"
CUTS = (15, 40, 70)   # transport.SCORE_CUTS


def level(score: int) -> int:
    return sum(score >= c for c in CUTS)


@pytest.fixture(scope="module")
def places() -> dict:
    idx = json.loads((WHATIF / "data" / "index.json").read_text())
    return {p["id"]: json.loads((WHATIF / "data" / f"{p['id']}.json").read_text()) for p in idx["places"]}


@pytest.fixture(scope="module")
def index() -> dict:
    return json.loads((WHATIF / "data" / "index.json").read_text())


def test_the_two_places_and_their_overflows(places):
    assert set(places) == {"cromwheel", "waterhead"}
    assert places["cromwheel"]["spot"] == "bw-uke4100-08901" and len(places["cromwheel"]["overflows"]) == 16
    assert places["waterhead"]["spot"] == "osm-windermere-waterhead" and len(places["waterhead"]["overflows"]) == 4


def test_the_stop_rule_follows_the_monotonicity_count(places, index):
    m = index["monotonicity"]
    assert m["overflows"] == 20 and m["stop_share"] == 0.10
    assert m["non_monotone"] == sum(p["monotonicity"]["non_monotone"] for p in places.values())
    assert m["rain_allowed"] == (m["non_monotone"] / m["overflows"] <= 0.10)
    assert all(p["rain_allowed"] == m["rain_allowed"] for p in places.values())


def test_expected_spill_days_never_fall_as_rain_rises(places):
    for p in places.values():
        for o in p["overflows"]:
            for y, e in o["expected"].items():
                assert all(b >= a for a, b in zip(e, e[1:])), (p["place"], o["id"], y)


def test_the_spot_score_never_falls_as_rain_rises(places):
    for p in places.values():
        for y, by_scale in p["series"].items():
            scales = sorted(by_scale, key=float)
            for drop in by_scale[scales[0]]:
                for a, b in zip(scales, scales[1:]):
                    assert all(sb >= sa for sa, sb in zip(by_scale[a][drop], by_scale[b][drop])), (p["place"], y, drop, a)


def test_taking_an_overflow_away_never_raises_a_level(places):
    for p in places.values():
        for y, by_scale in p["series"].items():
            for s, by_drop in by_scale.items():
                base = by_drop["none"]
                assert len(base) == (366 if y == "2024" else 365)
                for drop, arr in by_drop.items():
                    assert all(level(b) <= level(a) for a, b in zip(base, arr)), (p["place"], y, s, drop)


def test_summary_counts_match_the_series(places):
    for p in places.values():
        for row in p["summary"]:
            arr = p["series"][str(row["year"])][f"{row['scale']:.1f}"][row["removed"]]
            counts = [sum(level(v) == k for v in arr) for k in range(4)]
            assert counts == [row["days_low"], row["days_moderate"], row["days_high"], row["days_very_high"]]


def test_the_published_level_was_reproduced(places):
    for p in places.values():
        iss = p["issued"]
        assert iss["passed"] and iss["level_equal"] == iss["days"] > 0 and iss["max_abs_risk_diff"] <= 1e-6
        assert iss["leads"] == [3, 4]


def test_no_scenario_edits_a_covariate():
    """PR #298: lta_spills is not monotone, so no what-if may be made by writing it."""
    code = (ROOT / "scripts" / "lab_catch_sim.py").read_text()
    assert not re.search(r"""\[["']lta_spills["']\]\s*=""", code)
    assert "lta_cap" not in code and "spill_hours_scale" not in code


def test_inputs_were_offline_and_unchanged(index):
    assert index["inputs"]["fetches"] == 0 and index["inputs"]["unchanged_after_run"]
    assert index["inputs"]["committed"]["spill_model.pkl"]["md5"].startswith("808da63d")
    assert "Not a prediction of a real upgrade" in index["label"]


def test_the_page_says_what_it_is():
    html = (WHATIF / "index.html").read_text()
    assert '<meta name="robots" content="noindex">' in html
    assert "Not a prediction of a real upgrade" in html and "Not published" in html


def test_the_build_leaves_the_what_if_mode_out(tmp_path):
    assert "whatif" in build_site.LAB_UNPUBLISHED
    build_site.write_lab(tmp_path)
    lab = tmp_path / "lab"
    assert (lab / "workspace" / "index.html").is_file()
    assert not (lab / "workspace" / "whatif").exists()
    for f in lab.rglob("*"):   # no built page or script points at it (the catalogue may name the folder in text)
        if f.suffix in (".html", ".js", ".css"):
            assert "whatif" not in f.read_text(errors="ignore"), f


def test_no_published_page_links_the_what_if_mode():
    for f in [*(ROOT / "src" / "dipcast").rglob("*.html"), *(ROOT / "src" / "dipcast").rglob("*.js"),
              *(ROOT / "prototypes" / "research-lab").rglob("*")]:
        if f.is_file() and f.suffix in (".html", ".js") and WHATIF not in f.parents:
            assert "whatif" not in f.read_text(), f
