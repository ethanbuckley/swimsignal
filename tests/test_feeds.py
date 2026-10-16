"""The Atom feeds (docs/REVIEW-2026-10-16.md, G8): feed.xml, feed/<area>.xml and spot/<id>/feed.xml,
written from alerts.json. Each must parse as Atom with no error (feedparser's `bozo`), carry what
RFC 4287 requires of a feed and an entry, have one entry a spot with the build's time as `updated`,
and the credits in `rights`."""

import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import feedparser

ROOT = Path(__file__).resolve().parents[1]
ATOM = "{http://www.w3.org/2005/Atom}"
SITE = "https://example.org/swim/"
GENERATED = "2026-10-16T23:24:15.271548+01:00"


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def _alerts(bs) -> dict:
    spot = lambda i, name, level, headline, action: {
        "name": name, "rank": {"low": 0, "high": 2}.get(level, -1), "level": level, "headline": headline,
        "action": action, "url": f"{SITE}spot/{i}/" if " " not in i else f"{SITE}?spot={i.replace(' ', '%20')}"}
    return {"generated_at": GENERATED, "credits": bs.data_credits(SITE), "spots": {
        "warleigh-weir": spot("warleigh-weir", "Warleigh Weir", "high", "High risk right now: recent sewage spills",
                              "Best not to swim today."),
        "wharfe-ilkley": spot("wharfe-ilkley", 'Wharfe at "Cromwheel" & Ilkley', "low", "Low risk for the next five days",
                              "Usual care: cover cuts, try not to swallow water and wash your hands before eating."),
        "tarn": spot("tarn", "A Tarn <lake>", "no overflows", "No monitored overflow found upstream", ""),
        "Bad Id": spot("Bad Id", "Odd", "low", "Low risk for the next five days", "Usual care."),
    }}


RESULTS = [{"id": "warleigh-weir", "area": "South West"}, {"id": "wharfe-ilkley", "area": "Yorkshire"},
           {"id": "tarn", "area": "Cumbria and the Lake District"}, {"id": "Bad Id"}]


def _site(tmp_path, bs) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "alerts.json").write_text(json.dumps(_alerts(bs)))
    for i in ("warleigh-weir", "wharfe-ilkley", "tarn"):
        (tmp_path / "spot" / i).mkdir(parents=True)   # write_pages makes these
    return tmp_path


def _valid(path: Path) -> feedparser.FeedParserDict:
    """Parsed without error, and what RFC 4287 requires: a feed's id, title, updated and author, a
    self link, and each entry's id, title, updated and alternate link, the ids unique."""
    text = path.read_text()
    d = feedparser.parse(text)
    assert not d.bozo, (path, d.get("bozo_exception"))
    assert d.version == "atom10", path
    root = ET.fromstring(text)
    assert root.tag == f"{ATOM}feed"
    for tag in ("id", "title", "updated", "author", "rights"):
        assert root.find(f"{ATOM}{tag}") is not None, (path, tag)
    assert root.find(f"{ATOM}author/{ATOM}name").text == "SwimSignal"
    assert any(link.get("rel") == "self" and link.get("href") == d.feed.id for link in root.findall(f"{ATOM}link"))
    ids = []
    for e in root.findall(f"{ATOM}entry"):
        for tag in ("id", "title", "updated", "summary"):
            assert (e.find(f"{ATOM}{tag}").text or "").strip(), (path, tag)
        assert e.find(f"{ATOM}link[@rel='alternate']").get("href").startswith(SITE)
        ids.append(e.find(f"{ATOM}id").text)
    assert len(ids) == len(set(ids))
    return d


def test_feeds_are_valid_atom_with_one_entry_a_spot_and_the_credits(tmp_path):
    bs = _build_site()
    site = _site(tmp_path, bs)
    counts = bs.write_feeds(site, RESULTS, SITE)
    assert counts == {"site": 4, "areas": {"south-west": 1, "yorkshire": 1, "cumbria-and-the-lake-district": 1}, "spots": 3}
    whole = _valid(site / "feed.xml")
    assert whole.feed.id == f"{SITE}feed.xml" and whole.feed.link == SITE
    assert len(whole.entries) == 4   # one a spot, the one without a page too, by its ?spot= address
    credits = bs.data_credits(SITE)
    assert credits["attribution"] in whole.feed.rights and credits["full"] in whole.feed.rights
    # The build's time, in UTC, on the feed and every entry.
    assert whole.feed.updated == "2026-10-16T22:24:15Z" and {e.updated for e in whole.entries} == {"2026-10-16T22:24:15Z"}
    ww = next(e for e in whole.entries if e.link == f"{SITE}spot/warleigh-weir/")
    assert ww.title == "Warleigh Weir · High risk right now: recent sewage spills"
    assert ww.summary == "High risk right now: recent sewage spills. Best not to swim today."
    assert ww.tags[0].term == "high"
    assert ww.id == "tag:example.org,2026-10-16:spot/warleigh-weir/20261016T222415Z"
    # Escaping: a quote, an ampersand and angle brackets in a name survive the round trip.
    assert any(e.title.startswith('Wharfe at "Cromwheel" & Ilkley · ') for e in whole.entries)
    assert any(e.title.startswith("A Tarn <lake> · ") for e in whole.entries)
    assert next(e for e in whole.entries if e.title.startswith("A Tarn")).summary == "No monitored overflow found upstream"

    area = _valid(site / "feed" / "yorkshire.xml")
    assert area.feed.title == "SwimSignal · Yorkshire" and [e.link for e in area.entries] == [f"{SITE}spot/wharfe-ilkley/"]
    _valid(site / "feed" / "cumbria-and-the-lake-district.xml")
    one = _valid(site / "spot" / "warleigh-weir" / "feed.xml")
    assert one.feed.id == f"{SITE}spot/warleigh-weir/feed.xml" and one.feed.link == f"{SITE}spot/warleigh-weir/"
    assert len(one.entries) == 1 and one.entries[0].id == ww.id
    assert not (site / "spot" / "Bad Id").exists()


def test_a_later_build_gives_new_entry_ids_and_no_alerts_leaves_no_feeds(tmp_path):
    bs = _build_site()
    site = _site(tmp_path, bs)
    bs.write_feeds(site, RESULTS, SITE)
    first = {e.id for e in feedparser.parse((site / "feed.xml").read_text()).entries}
    later = {**_alerts(bs), "generated_at": "2026-10-16T23:54:02+01:00"}
    (site / "data" / "alerts.json").write_text(json.dumps(later))
    bs.write_feeds(site, RESULTS, SITE)
    second = {e.id for e in feedparser.parse((site / "feed.xml").read_text()).entries}
    assert len(second) == 4 and not first & second   # a reader sees a new forecast, not an edited one
    (site / "data" / "alerts.json").unlink()
    assert bs.write_feeds(site, RESULTS, SITE) is None
    assert not (site / "feed.xml").exists() and not (site / "feed").exists()


def test_the_data_page_lists_the_area_feeds(tmp_path):
    bs = _build_site()
    site = _site(tmp_path, bs)
    bs.write_feeds(site, RESULTS, SITE)
    bs.write_data_page(site)
    page = (site / "data.html").read_text()
    assert '<h2 id="feeds">Feeds</h2>' in page and '<a href="feed.xml">feed.xml</a>' in page
    for slug in ("south-west", "yorkshire", "cumbria-and-the-lake-district"):
        assert f'<a href="feed/{slug}.xml">feed/{slug}.xml</a>' in page
    assert "<!-- feeds -->" not in page


def test_the_build_writes_the_feeds_after_the_spot_pages():
    src = (ROOT / "scripts" / "build_site.py").read_text()
    pages = src[src.index("def write_pages("):src.index("def write_any_point(")]
    assert pages.index('shutil.rmtree(site / "spot"') < pages.index("write_feeds(site, results, root)") < pages.index("write_data_page(site, token)")


def test_the_home_and_spot_pages_link_their_feeds_only_when_there_are_feeds(tmp_path):
    bs = _build_site()
    spots = [{"id": "warleigh-weir", "name": "Warleigh Weir", "kind": "river", "upstream_summary": {"overflows": 3}, "days": []}]
    bs.write_pages(tmp_path, spots, root=SITE, day="2026-10-16")
    assert "application/atom+xml" not in (tmp_path / "index.html").read_text()
    (tmp_path / "data" / "alerts.json").write_text(json.dumps(_alerts(bs)))
    bs.write_pages(tmp_path, spots, root=SITE, day="2026-10-16")
    assert f'<link rel="alternate" type="application/atom+xml" title="SwimSignal · every spot" href="{SITE}feed.xml">' in (tmp_path / "index.html").read_text()
    page = (tmp_path / "spot" / "warleigh-weir" / "index.html").read_text()
    assert f'title="SwimSignal · Warleigh Weir" href="{SITE}spot/warleigh-weir/feed.xml">' in page
    assert (tmp_path / "spot" / "warleigh-weir" / "feed.xml").is_file() and (tmp_path / "feed.xml").is_file()
