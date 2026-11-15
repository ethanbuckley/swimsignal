"""Wessex Water's own river samples on the site (build_site.write_wessex_samples, wessex-river-samples.html): the
export (docs/WESSEX-RIVER-SAMPLES-CONTRACT-v1.md) holds its contract, each linked point passed its placement checks,
the page shows every sample with the CC BY 4.0 credit and says whose they are, the three spots' lines are added to
local-samples.json beside Waterhead's, and an export of another schema is not published."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "data" / "research" / "wessex_river_samples.v1.json"


def _mod(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


def test_the_committed_export_holds_its_contract():
    doc = json.loads(EXPORT.read_text())
    assert _mod("export_wessex_river_samples").check(doc) == []
    assert doc["spots"] == ["avon-warleigh-weir", "bw-ukk2301-36051", "frome-tellisford-weir"]
    by = {x["spot_id"]: x for x in doc["sites"]}
    assert {k: (x["summary"]["samples"], x["summary"]["over_900"]) for k, x in by.items()} == {
        "avon-warleigh-weir": (322, 145), "bw-ukk2301-36051": (174, 93), "frome-tellisford-weir": (98, 49)}
    assert doc["coverage"] == {"sites": 3, "samples": 594}
    # Where each point is from its spot, along the river, and that every check held.
    assert [(by[k]["along_m"], by[k]["direction"]) for k in doc["spots"]] == [(51, "downstream"), (-2269, "upstream"), (212, "downstream")]
    assert all(all(x["checks"].values()) and x["overflows_upstream"]["between"] == [] for x in doc["sites"])
    assert doc["source"]["licence_check"]["wording"].endswith("is licensed under CC BY 4.0")
    assert doc["source"]["files_sha256"]["ecoli.parquet"].startswith("e02f8817")


def test_limits_stay_limits():
    doc = json.loads(EXPORT.read_text())
    s = {(x["spot_id"], a["t"]): a for x in doc["sites"] for a in x["samples"]}
    below = s[("bw-ukk2301-36051", "2023-08-17T11:10")]
    assert (below["ecoli"], below["q"], below["over"]) == (1000, "<", None)   # below 1,000 cannot say over 900
    above = s[("frome-tellisford-weir", "2021-05-24T10:00")]
    assert (above["ecoli"], above["q"], above["over"]) == (10000, ">", True)
    na = s[("frome-tellisford-weir", "2025-09-17T10:40")]   # an operator of "NA" is no qualifier
    assert (na["ecoli"], na["q"], na["over"]) == (7800, None, True)


def test_the_check_refuses_a_broken_export():
    m, doc = _mod("export_wessex_river_samples"), json.loads(EXPORT.read_text())
    doc["claim"]["public_wording"] = "Clean water."
    doc["sites"][0]["samples"] = doc["sites"][0]["samples"][1:]
    doc["sites"][1]["checks"]["no_overflow_between"] = False
    assert m.check(doc) == ["the claim must say it is not today's water",
                            "the claim must say these are not Environment Agency samples",
                            "bw-ukk2301-36051: linked does not follow its checks",
                            "avon-warleigh-weir: counts do not add up", "coverage does not match the samples"]


def test_the_page_shows_every_sample_with_its_credit(tmp_path):
    bs = _mod("build_site")
    bs.write_waterhead(tmp_path)
    assert bs.write_wessex_samples(tmp_path) == {"available": True, "samples": 594, "sites": 3, "version": "1.0.0"}
    html = (tmp_path / "wessex-river-samples.html").read_text()
    assert "<title>Wessex Water&#x27;s river samples · SwimSignal</title>" in html and "<!-- WESSEX" not in html
    assert html.count('<tr><th scope="row">') == 594
    assert "licensed under CC BY 4.0" in html and "https://creativecommons.org/licenses/by/4.0/" in html
    assert "They are not Environment Agency bathing water samples." in html and "not today&#x27;s water" in html
    assert "about 50 m downstream of the spot along the River Avon" in html
    assert "about 2.3 km upstream of the spot along the River Frome (1.0 km in a straight line)" in html
    assert "One more is given only as below 1,000." in html and "<td>above 10,000</td>" not in html
    assert '<td class="num">above 10,000</td>' in html and '<td class="num">below 1,000</td><td>Not known</td>' in html
    assert "No samples were published here in 2024." in html   # Tellisford's gap is said, not hidden
    assert '<a href="samples.html">Its samples are on the E. coli samples page</a>' in html   # Farleigh's EA samples
    # Downstream first, each year folded and closed, newest year and newest sample first.
    assert html.index('id="avon-warleigh-weir"') < html.index('id="bw-ukk2301-36051"') < html.index('id="frome-tellisford-weir"')
    assert '<details class="fold"><summary>2025: 50 samples, 14 over 900, highest 23,000</summary>' in html and " open>" not in html
    assert html.index('<th scope="row">8 Dec 2025</th>') < html.index('<th scope="row">2 Jan 2025</th>')
    assert json.loads((tmp_path / "data" / "research" / "wessex_river_samples.json").read_text())["schema"] == "swimsignal.wessex-river-samples"
    local = json.loads((tmp_path / "data" / "research" / "local-samples.json").read_text())
    assert local["available"] is True and set(local["spots"]) == {"osm-windermere-waterhead", "avon-warleigh-weir",
                                                                  "bw-ukk2301-36051", "frome-tellisford-weir"}
    assert local["spots"]["bw-ukk2301-36051"] == {
        "href": "wessex-river-samples.html#bw-ukk2301-36051", "company": True, "by": "Wessex Water", "place": "the River Frome",
        "samples": 174, "first": "2021-04-27", "last": "2025-07-28", "along_m": 2269, "direction": "upstream"}
    assert "data" not in local["spots"]["avon-warleigh-weir"]   # its evidence timeline does not list another point's samples


def test_without_waterhead_the_spots_are_still_linked(tmp_path):
    bs = _mod("build_site")
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"schema": "swimsignal.waterhead-wet", "version": "2.0.0"}))
    bs.write_waterhead(tmp_path, path=other)
    bs.write_wessex_samples(tmp_path)
    local = json.loads((tmp_path / "data" / "research" / "local-samples.json").read_text())
    assert local["available"] is True and len(local["spots"]) == 3 and "why" not in local


def test_another_schema_is_not_published(tmp_path):
    bs = _mod("build_site")
    bs.write_waterhead(tmp_path)
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"schema": "swimsignal.wessex-river-samples", "version": "2.0.0"}))
    h = bs.write_wessex_samples(tmp_path, path=other)
    assert h["available"] is False and "not swimsignal.wessex-river-samples 1.x" in h["why"]
    assert "No samples are published in this build." in (tmp_path / "wessex-river-samples.html").read_text()
    assert not (tmp_path / "data" / "research" / "wessex_river_samples.json").exists()
    assert set(json.loads((tmp_path / "data" / "research" / "local-samples.json").read_text())["spots"]) == {"osm-windermere-waterhead"}
