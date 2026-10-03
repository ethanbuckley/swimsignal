"""Practical guides (src/dipcast/guides.py): every file in guides/ is valid before a build runs; a
confirmed fact always names its page or the day it was seen, and a swimmer's suggestion always says
who and when; the build publishes only the photos the guides use."""

import csv
import sys
import tomllib
from datetime import date
from pathlib import Path

import pytest

from dipcast import guides as gd

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 3)


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def spot_ids() -> set[str]:
    return {r["id"] for f in ("spots.csv", "spots-osm.csv") for r in csv.DictReader((ROOT / f).open())}


def parse(text: str, photos: Path = ROOT / "guides" / "photos"):
    return gd.parse_guide(tomllib.loads(text), "x", photos, TODAY)


GOOD = """
checked = 2026-10-03
how = "desk"

[[fact]]
topic = "entry"
text = "Steps into the water by the jetty."
status = "suggested"
from = "Sam"
on = 2026-09-12

[[fact]]
topic = "parking"
text = "Pay and display car park on Denton Road."
status = "confirmed"
source = "https://www.example.gov.uk/parking"
source_name = "Example Council"
lat = 53.93
lon = -1.82

[[fact]]
topic = "entry"
text = "A shingle beach on the south bank."
status = "confirmed"
seen = 2026-08-20
"""


def test_every_guide_in_the_repository_is_valid_and_belongs_to_a_spot():
    guides, warnings = gd.load_guides(spot_ids())
    assert warnings == []
    for sid, g in guides.items():
        assert g["facts"], sid
        for f in g["facts"]:
            if f["status"] == "confirmed":
                assert f.get("source") or f.get("seen"), (sid, f)
            else:
                assert f["from"] and f["on"], (sid, f)


def test_facts_come_in_topic_order_confirmed_first():
    g = parse(GOOD)
    assert [(f["topic"], f["status"]) for f in g["facts"]] == [("parking", "confirmed"), ("entry", "confirmed"), ("entry", "suggested")]
    assert g["facts"][0]["lat"] == 53.93 and g["facts"][0]["source_name"] == "Example Council"
    assert g["facts"][2] == {"topic": "entry", "text": "Steps into the water by the jetty.", "status": "suggested", "from": "Sam", "on": "2026-09-12"}
    assert g["checked"] == "2026-10-03" and g["photos"] == []


@pytest.mark.parametrize("change, message", [
    (('status = "confirmed"\nsource', 'status = "confirmed"\nxsource'), "unknown field"),
    (('source = "https://www.example.gov.uk/parking"\nsource_name = "Example Council"\n', ''), "needs a source page or the day it was seen"),
    (('https://www.example', 'http://www.example'), "https address"),
    (('from = "Sam"', 'source = "https://a.example/"\nsource_name = "A"\nfrom = "Sam"'), "once checked it becomes confirmed"),
    (('on = 2026-09-12', 'on = 2026-10-04'), "in the future"),
    (('topic = "parking"', 'topic = "car park"'), "topic must be one of"),
    (('how = "desk"', 'how = "guess"'), "how must be desk"),
    (('lat = 53.93\n', ''), "both lat and lon"),
    (('lat = 53.93', 'lat = 48.0'), "in England"),
    (('checked = 2026-10-03', 'checked = "3 October"'), "must be a date"),
])
def test_a_bad_guide_says_what_is_wrong(change, message):
    with pytest.raises(gd.GuideError, match=message):
        parse(GOOD.replace(*change, 1))


def test_a_photo_needs_its_file_size_credit_and_labels_on_the_picture(tmp_path):
    (tmp_path / "steps.jpg").write_bytes(b"\xff\xd8\xff")
    photo = """
[[photo]]
file = "steps.jpg"
width = 1600
height = 1200
caption = "The steps from the path."
credit = "Ethan Buckley"
taken = 2026-08-20
status = "confirmed"
seen = 2026-08-20
[[photo.label]]
x = 30
y = 72.25
text = "Steps in"
"""
    g = parse(GOOD + photo, tmp_path)
    assert g["photos"] == [{"file": "steps.jpg", "w": 1600, "h": 1200, "caption": "The steps from the path.", "credit": "Ethan Buckley",
                            "taken": "2026-08-20", "status": "confirmed", "seen": "2026-08-20", "labels": [{"x": 30.0, "y": 72.2, "text": "Steps in"}]}]
    with pytest.raises(gd.GuideError, match="does not exist"):
        parse(GOOD + photo.replace("steps.jpg", "gone.jpg"), tmp_path)
    with pytest.raises(gd.GuideError, match="percentages"):
        parse(GOOD + photo.replace("x = 30", "x = 130"), tmp_path)
    with pytest.raises(gd.GuideError, match="width and height"):
        parse(GOOD + photo.replace("width = 1600\n", ""), tmp_path)
    with pytest.raises(gd.GuideError, match="lower-case"):
        parse(GOOD + photo.replace('"steps.jpg"', '"../steps.jpg"'), tmp_path)


def test_the_build_attaches_guides_warns_on_bad_ones_and_copies_only_used_photos(tmp_path):
    root, site = tmp_path / "guides", tmp_path / "site"
    (root / "photos").mkdir(parents=True)
    (root / "photos" / "used.jpg").write_bytes(b"jpeg")
    (root / "photos" / "spare.jpg").write_bytes(b"jpeg")
    (root / "a.toml").write_text(GOOD + '[[photo]]\nfile = "used.jpg"\nwidth = 4\nheight = 3\ncaption = "c"\ncredit = "c"\n'
                                 'taken = 2026-08-20\nstatus = "suggested"\nfrom = "Sam"\non = 2026-08-21\n')
    (root / "b.toml").write_text("checked = 2026-10-03\nhow = 'desk'\n")      # no facts
    (root / "nobody.toml").write_text(GOOD)                                     # no such spot
    results = [{"id": "a"}, {"id": "b"}]
    out = gd.attach_guides(results, root, TODAY)
    assert out["guides"] == 1 and len(out["warnings"]) == 2
    assert any("b.toml" in w and "at least one" in w for w in out["warnings"])
    assert any("nobody.toml" in w and "no spot" in w for w in out["warnings"])
    assert results[0]["guide"]["photos"][0]["from"] == "Sam" and "guide" not in results[1]
    (site / "guides" / "photos").mkdir(parents=True)
    (site / "guides" / "photos" / "stale.jpg").write_bytes(b"old")
    assert gd.copy_photos(site, results, root) == 1
    assert sorted(p.name for p in (site / "guides" / "photos").iterdir()) == ["used.jpg"]


def test_the_page_loads_the_guide_script_from_its_build(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    assert f'<script src="guide.js?v={stamp}">' in (tmp_path / "index.html").read_text()
    assert (tmp_path / "guide.js").read_bytes() == (bs.TEMPLATE.parent / "guide.js").read_bytes()
    assert "`guide.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()


def test_the_page_and_the_build_list_the_same_topics():
    js = (ROOT / "src" / "dipcast" / "site" / "guide.js").read_text()
    for key, label in gd.TOPICS.items():
        assert f"['{key}', '{label}']" in js
