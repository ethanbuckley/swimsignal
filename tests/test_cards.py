"""The social-media cards (src/dipcast/cards.py): which days, which spots, which rows, the storm
card and its absence, the captions' words, and the files the build writes."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from dipcast import cards
from dipcast.cards import Area

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://swimsignal.co.uk/"


def five(first: str) -> list[str]:
    d = date.fromisoformat(first)
    return [(d + timedelta(days=i)).isoformat() for i in range(5)]


# ------------------------------------------------------------------------------ the days
@pytest.mark.parametrize("today, want", [
    ("2026-10-14", ["2026-10-17", "2026-10-18"]),   # Wednesday: the coming weekend, days 4 and 5
    ("2026-10-16", ["2026-10-17", "2026-10-18"]),   # Friday
    ("2026-10-17", ["2026-10-17", "2026-10-18"]),   # Saturday: today and tomorrow
    ("2026-10-11", ["2026-10-11", "2026-10-12"]),   # Sunday: today and tomorrow
    ("2026-10-12", None),                           # Monday: the five days end on Friday
    ("2026-10-13", None),                           # Tuesday: Saturday is in, Sunday is not
])
def test_weekend_days(today, want):
    assert cards.weekend_days(five(today)) == want


def test_weekend_days_needs_dates():
    assert cards.weekend_days([]) is None


# ------------------------------------------------------------------------------ the rows
DATES = five("2026-10-14")
SAT, SUN = "2026-10-17", "2026-10-18"
WORDS = ["Low risk", "Moderate risk: sewage spills", "High risk: rated poor", "Very high risk: sewage spills", "Usual care."]


def alerts_fixture() -> dict:
    day = lambda lv, w: [lv, w, 4]
    return {
        "generated_at": "2026-10-14T08:12:00+01:00", "dates": DATES, "words": WORDS,
        "spots": {
            "a": {"name": "River A, Upper", "level": "low", "headline": "Low risk", "url": f"{SITE}spot/a/",
                  "days": [day("low", 0)] * 3 + [day("low", 0), day("moderate", 1)]},
            "poor": {"name": "River A at the Poor", "level": "high", "headline": "High risk: rated poor",
                     "days": [day("high", 2)] * 5},
            "gap": {"name": "River A, Gap", "level": "low", "headline": "Low risk",
                    "days": [day("low", 0)] * 3 + [day("very high", 3), None]},
            "lake": {"name": "Quiet Lake", "level": "no overflows", "headline": "No monitored overflow found upstream"},
            "tarn": {"name": "Quiet Tarn", "level": "no overflows", "headline": "No monitored overflow found upstream"},
            "rated": {"name": "Rated Lake", "level": "moderate", "headline": "Moderate risk: rated sufficient by the Environment Agency"},
        },
    }


AREA = Area("test", "River A", (("a", "Upper"), ("missing", "Gone"), ("poor", "The Poor"), ("gap", "Gap"),
                                ("lake", "Quiet Lake"), ("tarn", "Quiet Tarn"), ("rated", "Rated Lake")))


def test_weekend_card_rows():
    card = cards.weekend_card(AREA, cards.spot_levels(alerts_fixture()), [SAT, SUN])
    rows = {r.id: r for r in card.rows}
    assert [r.id for r in card.rows] == ["a", "poor", "gap", "rated"]    # the area's order; plain levels go below
    assert rows["a"].cells == ["low", "moderate"] and not rows["a"].poor
    assert rows["poor"].cells == ["high", "high"] and rows["poor"].poor
    assert rows["gap"].cells == ["very high", None]                       # no level on Sunday: no forecast
    assert rows["rated"].cells == ["moderate", "moderate"]               # a standing level holds every day
    assert card.plain == [("No monitored overflow found upstream", "no overflows", ["Quiet Lake", "Quiet Tarn"])]
    assert card.missing == ["missing"]
    assert card.ids == ["a", "poor", "gap", "lake", "tarn", "rated"]


def test_weekend_card_without_any_spot_is_none():
    assert cards.weekend_card(Area("x", "X", (("nope", "Nope"),)), cards.spot_levels(alerts_fixture()), [SAT, SUN]) is None


def test_every_area_is_known_to_the_spot_lists():
    """Every id in AREAS is a spot in spots.csv or spots-osm.csv, so no row goes missing by a typo."""
    import csv
    ids = {row["id"] for f in ("spots.csv", "spots-osm.csv") for row in csv.DictReader((ROOT / f).open())}
    for area in cards.AREAS:
        assert [sid for sid, _ in area.spots if sid not in ids] == [], area.slug
        assert all("," not in label for _, label in area.spots), area.slug   # the poor line lists them with commas


# ------------------------------------------------------------------------------ the storm card
GEN = "2026-10-11T14:09:00+01:00"


def spot(sid, k, mon, **now):
    return {"id": sid, "name": f"Spot {sid}", "upstream_summary": {"overflows": mon},
            "now": {"discharging_upstream": k, "monitored_upstream": mon, "label": "low", **now}}


def test_storm_rows_sorted_and_filtered():
    spots = [spot("one", 1, 50), spot("two", 2, 26), spot("none", 0, 10), spot("share", 1, 4),
             {"id": "err", "name": "Broken", "error": "forecast failed: x", "now": {"discharging_upstream": 3}},
             {"id": "old", "name": "No count", "upstream_summary": {"overflows": 7}, "now": {"discharging_upstream": 1}}]
    rows = cards.storm_rows(spots, GEN)
    assert [r.id for r in rows] == ["two", "share", "old", "one"]   # most first, then the larger share
    assert rows[2].monitored == 7                                  # no monitored count: the overflows upstream


def test_no_storm_card_when_nothing_is_discharging(tmp_path):
    spots = [spot("a", 0, 12), spot("b", 0, 3)]
    summary = cards.write_cards(tmp_path, spots, None, GEN, SITE)
    assert cards.storm_rows(spots, GEN) == [] and summary["storm_spots"] == 0
    assert not list(tmp_path.glob("storm-*"))
    page = (tmp_path / "index.html").read_text()
    assert "No storm card" in page
    assert "all clear" not in page.lower()


def test_clear_words():
    later = "2026-10-12T08:24:00+01:00"
    assert cards.clear_words({"clears_at": later, "label": "high", "discharging_upstream": 2}, GEN) == \
        "If they stop now, the model expects low risk from spills by about Monday morning."
    assert cards.clear_words({"clears_at": later, "label": "high", "discharging_upstream": 1}, GEN).startswith("If it stops now,")
    assert cards.clear_words({"clears_at": later, "label": "low", "discharging_upstream": 1}, GEN) == ""   # low already
    assert cards.clear_words({"clears_at": "2026-10-11T12:00:00+01:00", "label": "high", "discharging_upstream": 1}, GEN) == ""
    assert cards.clear_words({"clears_at": None, "label": "high", "discharging_upstream": 1}, GEN) == ""


@pytest.mark.parametrize("iso, words", [
    ("2026-10-12T03:00:00+00:00", "overnight into Monday"),    # 04:00 in London
    ("2026-10-12T10:59:00+00:00", "by about Monday morning"),  # 11:59 BST
    ("2026-10-12T15:04:00+01:00", "by about Monday afternoon"),
    ("2026-12-14T18:30:00+00:00", "by about Monday evening"),  # GMT
])
def test_part_of_day(iso, words):
    assert cards.part_of_day(iso) == words


# ------------------------------------------------------------------------------ captions and files
def test_captions_words():
    card = cards.weekend_card(AREA, cards.spot_levels(alerts_fixture()), [SAT, SUN])
    text = cards.weekend_caption(card, "2026-10-14T08:12:00+01:00", SITE)
    assert text.startswith("River A this weekend: the pollution risk forecast for Saturday 17 and Sunday 18 October.")
    assert "Upper: low risk on Saturday, moderate risk on Sunday." in text
    assert "Gap: very high risk on Saturday, no forecast on Sunday." in text
    assert "Quiet Lake and Quiet Tarn: no monitored overflow found upstream." in text
    assert "The Poor is rated poor by the Environment Agency, so it stays at high risk or worse." in text
    assert "swimsignal.co.uk" in text and "saved/#list=River%20A&day=2026-10-17&spots=a,poor,gap,lake,tarn,rated" in text
    assert "Forecast issued Wednesday 14 October at 08:12. A forecast, not a water test." in text
    storm = cards.storm_caption(cards.storm_rows([spot("two", 2, 26)], GEN), GEN, SITE)
    assert "Spot two: 2 of 26 monitored overflows upstream discharging now." in storm
    assert "National Storm Overflow Hub, CC BY 4.0" in storm and cards.CAVEAT in storm
    for t in (text, storm):
        assert not any(w in t.lower() for w in ("safe", "clean"))


def test_write_cards(tmp_path):
    from PIL import Image

    (tmp_path / "old-2026-01-01-1080x1350.png").write_bytes(b"x")   # last weekend's: removed
    (tmp_path / "keep.json").write_text("{}")                         # anything else stays
    spots = [spot("two", 2, 26, clears_at="2026-10-12T08:24:00+01:00", label="high")]
    summary = cards.write_cards(tmp_path, spots, alerts_fixture(), "2026-10-14T08:12:00+01:00", SITE, areas=(AREA,))
    assert summary["weekend"] == ["test"] and summary["storm_spots"] == 1 and summary["cards"] == 2
    assert any("missing" in w for w in summary["warnings"])
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["index.html", "keep.json", "storm-2026-10-14-0812-1080x1080.png", "storm-2026-10-14-0812-1080x1350.png",
                     "storm-2026-10-14-0812.txt", "test-2026-10-17-1080x1080.png", "test-2026-10-17-1080x1350.png",
                     "test-2026-10-17.txt"]
    for p in tmp_path.glob("*.png"):
        assert Image.open(p).size == ((1080, 1350) if "1350" in p.name else (1080, 1080))
    page = (tmp_path / "index.html").read_text()
    assert '<meta name="robots" content="noindex">' in page
    assert 'href="test-2026-10-17-1080x1350.png" download' in page and "A forecast, not a water test." in page


def test_configured_areas_fit_both_sizes():
    """Each area's card fits both sizes with every spot as a row at its longest word, and the line
    about a poor rating under them."""
    for area in cards.AREAS:
        levels = {sid: {"name": label, "url": None, "level": "very high", "headline": "",
                        "days": {SAT: ("very high", "x"), SUN: ("very high", "x")}} for sid, label in area.spots}
        card = cards.weekend_card(area, levels, [SAT, SUN])
        for r in card.rows[:2]:
            r.poor = True
        for size in cards.SIZES:
            cards.draw_weekend(card, "2026-10-14T08:12:00+01:00", size)   # raises Overflow if not


def test_storm_card_shows_what_fits_and_counts_the_rest():
    rows = cards.storm_rows([spot(f"s{i}", 12 - i, 40, clears_at="2026-10-12T08:24:00+01:00", label="high") for i in range(11)], GEN)
    for size in cards.SIZES:
        cards.draw_storm(rows, GEN, size)


# ------------------------------------------------------------------------------ legibility
def contrast(a: str, b: str) -> float:
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_text_contrast():
    on_paper = [cards.INK, cards.MUTED, cards.BRAND_TEAL, cards.CLEAR_TEXT, cards.NA_TEXT, *cards.TEXTS.values()]
    assert min(contrast(c, cards.PAPER) for c in on_paper) >= 4.5
    assert contrast(cards.ON_FILL, cards.BAR) >= 4.5 and contrast(cards.BAR_INK, cards.BAR) >= 4.5


def test_no_text_under_the_floor():
    with pytest.raises(ValueError):
        cards.font("sans", 24)


# ------------------------------------------------------------------------------ in the build
def test_build_never_stops_for_cards(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site

    out = build_site.write_cards(tmp_path, None, GEN, SITE)   # nonsense in: a warning out, no exception
    assert "warning" in out
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "alerts.json").write_text('{"generated_at": "2026-10-10T08:00:00+01:00", "dates": []}')
    out = build_site.write_cards(tmp_path, [spot("a", 0, 3)], GEN, SITE)   # an old alerts.json is not used
    assert out["weekend"] == [] and "levels file" in (tmp_path / "cards" / "index.html").read_text()


# ------------------------------------------------------------------------------ a spot's share card
HEADLINES = ["Low risk for the next five days", "Very high risk right now: sewage spills",
             "Low risk forecast: the overflows that matter most here do not report live",   # the longest on 16 Oct 2026
             "No monitored overflow found upstream", "No forecast"]


def test_spot_share_card_fits_the_longest_names_and_headlines():
    """1200 x 630, as the preview size; the longest names in the lists on 16 Oct 2026 and longer, with
    the longest headline, fit (draw_spot raises Overflow if not)."""
    for name in ["River Wharfe, Bolton Abbey (Cavendish Pavilion)", "River Lathkill, Lathkill Dale, Over Haddon, Derbyshire Dales"]:
        for headline in HEADLINES:
            assert cards.draw_spot(name, "River · River Wharfe", "low", headline, GEN).size == cards.SHARE_SIZE
    with pytest.raises(cards.Overflow):
        cards.draw_spot("A name far too long for any card " * 4, "", "low", HEADLINES[2], GEN)


def test_spot_where_and_colours():
    assert cards.spot_where({"kind": "lake", "location": {"watercourse": "Windermere (N Basin)"}}) == "Lake · Windermere (N Basin)"
    assert cards.spot_where({"kind": "river", "location": {"watercourse": "River Wharfe"}}) == "River Wharfe"
    assert cards.spot_where({"kind": "lake"}) == "Lake"
    assert cards.level_colours("high") == (cards.MARKS["high"], cards.TEXTS["high"])
    assert cards.level_colours("no river connection") == (cards.CLEAR_MARK, cards.CLEAR_TEXT)
    assert cards.level_colours("no forecast") == (cards.NA_MARK, cards.NA_TEXT)


def test_write_spot_cards(tmp_path):
    """A card for each spot with a page and a level in this run's alerts.json, its alt text with the
    issue time beside the level; none from another run's file, and old cards go."""
    spots = [{"id": "a", "name": "A river", "kind": "river"}, {"id": "Bad Id", "name": "Odd", "kind": "river"},
             {"id": "b", "name": "B lake", "kind": "lake"}]
    alerts = {"generated_at": GEN, "spots": {"a": {"level": "high", "headline": "High risk today: sewage spills"},
                                             "Bad Id": {"level": "low", "headline": "Low risk"}}}
    out = tmp_path / "spot"
    made = cards.write_spot_cards(out, spots, alerts, GEN)
    assert made == {"a": "A river: High risk today: sewage spills. Forecast issued Sun 11 Oct, 14:09."}
    assert sorted(p.name for p in out.iterdir()) == ["a.png"]
    assert cards.write_spot_cards(out, spots, {**alerts, "generated_at": "2026-10-13T08:00:00+01:00"}, GEN) == {}
    assert not out.exists()


# Official advice (spots.json `official`): never a clean "Low" on a card. The words are eatoday.js's
# eaTodayBrief, checked here against the script itself.
OFFICIAL = {"line": "Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026",
            "publisher": "Environment Agency",
            "link": "https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945",
            "since": "2026-06-19", "checked": "2026-10-26", "state": "checked", "restricts": True}
BRIEF = "EA advice against bathing (harmful algae) · since 19 Jun · checked 26 Oct"


@pytest.mark.parametrize("items", [
    [OFFICIAL], [{**OFFICIAL, "state": "stale"}], [{**OFFICIAL, "state": "gone"}], [OFFICIAL, {**OFFICIAL, "since": "2026-01-01"}],
    [{**OFFICIAL, "publisher": "Waverley Borough Council", "since": "2025-08-22",
      "line": "Waverley Borough Council: advice against swimming (blue-green algae) since 22 Aug 2025"}],
    [], [{**OFFICIAL, "state": "approved"}], [{**OFFICIAL, "checked": "26 Oct"}],
])
def test_official_brief_matches_the_site(items):
    import json
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    js = Path(__file__).resolve().parents[1] / "src/dipcast/site/eatoday.js"
    script = f"process.stdout.write(require({json.dumps(str(js))}).eaTodayBrief({json.dumps({'official': items})}))"
    got = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    assert cards.official_brief({"official": items}) == got
    if items == [OFFICIAL]:
        assert got == BRIEF


def test_spot_share_card_carries_official_advice(tmp_path):
    """A low spot with advice: the card's alt text and picture say the advice before the level, which is
    unchanged; a spot without advice is as before. The longest names still fit with the line."""
    spots = [{"id": "f", "name": "Frensham Great Pond", "kind": "lake", "official": [OFFICIAL]},
             {"id": "o", "name": "Other Pond", "kind": "lake"}]
    alerts = {"generated_at": GEN, "spots": {s["id"]: {"level": "low", "headline": "Low risk for the next five days"} for s in spots}}
    made = cards.write_spot_cards(tmp_path / "spot", spots, alerts, GEN)
    assert made["f"] == (f"Frensham Great Pond: Official: {BRIEF}. Follow it first; the level is SwimSignal's sewage "
                         "forecast only. Low risk for the next five days. Forecast issued Sun 11 Oct, 14:09.")
    assert made["o"] == "Other Pond: Low risk for the next five days. Forecast issued Sun 11 Oct, 14:09."
    for name in ["River Wharfe, Bolton Abbey (Cavendish Pavilion)", "River Lathkill, Lathkill Dale, Over Haddon, Derbyshire Dales"]:
        for headline in HEADLINES:
            assert cards.draw_spot(name, "Lake", "low", headline, GEN, BRIEF).size == cards.SHARE_SIZE
    # The line is drawn: the picture differs from the one without advice.
    with_line = cards.draw_spot("Frensham Great Pond", "Lake", "low", HEADLINES[0], GEN, BRIEF)
    assert with_line.tobytes() != cards.draw_spot("Frensham Great Pond", "Lake", "low", HEADLINES[0], GEN).tobytes()


def test_weekend_card_and_caption_carry_official_advice():
    card = cards.weekend_card(AREA, cards.spot_levels(alerts_fixture()), [SAT, SUN], {"a": (BRIEF, True)})
    rows = {r.id: r for r in card.rows}
    assert rows["a"].cells == ["low", "moderate"] and rows["a"].official == BRIEF   # the level is unchanged
    assert rows["poor"].official == ""
    caption = cards.weekend_caption(card, GEN, "https://swimsignal.co.uk/")
    assert f"Upper: low risk on Saturday, moderate risk on Sunday. Official: {BRIEF}. Follow it first" in caption
    for size in cards.SIZES:
        cards.draw_weekend(card, GEN, size)   # the note under the table fits


def test_weekend_card_plain_line_spot_with_advice_is_named_with_it():
    """A spot in a plain line ("No monitored overflow found upstream") with advice, stale or checked, is
    named with its notice under the table and in the caption; one without advice is not."""
    stale = BRIEF.replace("checked 26 Oct", "not re-checked since 19 Oct")
    card = cards.weekend_card(AREA, cards.spot_levels(alerts_fixture()), [SAT, SUN], {"lake": (stale, True), "a": (BRIEF, True)})
    assert card.plain_official == [("Quiet Lake", stale, True)]
    assert card.plain == [("No monitored overflow found upstream", "no overflows", ["Quiet Lake", "Quiet Tarn"])]   # unchanged
    caption = cards.weekend_caption(card, GEN, "https://swimsignal.co.uk/")
    assert f"Quiet Lake: Official: {stale}. Follow it first" in caption
    assert "Quiet Tarn: Official" not in caption
    for size in cards.SIZES:
        cards.draw_weekend(card, GEN, size)   # both notes fit


def test_a_notice_not_marked_restricting_is_read_not_followed_on_cards_and_captions(tmp_path):
    """Only a notice its reviewer marked restricts: true says "Follow it first" (28 Oct 2026); any other, or one
    from before the field, "Read the official notice first". The notice's own words and the level are unchanged."""
    neutral = {**OFFICIAL, "restricts": False}
    assert cards.official_restricts({"official": [OFFICIAL]}) is True
    assert cards.official_restricts({"official": [neutral]}) is False
    assert cards.official_restricts({"official": [{k: v for k, v in OFFICIAL.items() if k != "restricts"}]}) is False
    assert cards.official_restricts({"official": [{**OFFICIAL, "state": "approved"}]}) is False   # not shown, so not counted
    assert cards.official_words(BRIEF, False) == f"Official: {BRIEF}. Read the official notice first; the level is SwimSignal's sewage forecast only."
    spots = [{"id": "f", "name": "Frensham Great Pond", "kind": "lake", "official": [neutral]}]
    alerts = {"generated_at": GEN, "spots": {"f": {"level": "low", "headline": "Low risk for the next five days"}}}
    made = cards.write_spot_cards(tmp_path / "spot", spots, alerts, GEN)
    assert made["f"].startswith(f"Frensham Great Pond: Official: {BRIEF}. Read the official notice first;")
    card = cards.weekend_card(AREA, cards.spot_levels(alerts_fixture()), [SAT, SUN], {"a": (BRIEF, False)})
    caption = cards.weekend_caption(card, GEN, "https://swimsignal.co.uk/")
    assert f"Official: {BRIEF}. Read the official notice first" in caption and "Follow it first" not in caption
    # A bare brief, as an older caller passes it, reads as not restricting.
    assert cards.weekend_card(AREA, cards.spot_levels(alerts_fixture()), [SAT, SUN], {"a": BRIEF}).rows[0].official_restricts is False
    for size in cards.SIZES:
        cards.draw_weekend(card, GEN, size)
