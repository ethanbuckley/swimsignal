"""The data feed page (src/dipcast/pages/data-feed.html), for apps and charities that already reach swimmers: written with the
other prose pages, linked from For organisations, in the sitemap; each example one record from the build's own file;
the credit and the live warning figures this build's; the cadence as measured, never "every 30 minutes"; the licences
as the sources state them, the consents register out of every file; and no prices."""

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as bs  # noqa: E402

SOURCE = ROOT / "src" / "dipcast" / "pages" / "data-feed.html"
text = lambda h: html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)))
SPOT = bs.FEED_SPOT


def examples(page: str) -> dict[str, str]:
    return {m[1]: html.unescape(m[2]) for m in re.finditer(r'<pre class="example" data-example="([a-z-]+)">(.*?)</pre>', page, re.S)}


def fake_data(site: Path, spot_id: str = SPOT) -> Path:
    """A data/ folder with every file the page shows, two spots, two overflows: just enough of each."""
    d = site / "data"
    for sub in ("upstream", "anypoint", "research/spill_durations"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    ov = lambda i: {"site_id": f"YWS0{i}", "company": "Yorkshire Water", "site_name": f"OVERFLOW {i}/CSO", "distance_km": i,
                    "travel_h": i, "weight": 0.5, "status": 0, "data_state": "live", "p_spill_days": [0.1] * 5, "secret": 1}
    spot = lambda sid: {"id": sid, "name": "Wharfe", "kind": "river", "river": "River Wharfe", "source": "designated", "lat": 53.9,
                        "lon": -1.8, "now": {"risk": 0.0, "label": "low", "monitored_upstream": 2, "quiet_by_feed": []},
                        "days": [{"date": f"2026-11-1{i}", "risk": 0.1, "label": "low"} for i in range(5)],
                        "upstream_summary": {"overflows": 2, "with_live_feed": 2, "without_live_feed": 0, "sum_weight": 1},
                        "contributors": [ov(1), ov(2)], "seasonal": {"years": [2024, 2025], "spill": [1] * 12}, "guide": {"x": 1}}
    (d / "spots.json").write_text(json.dumps({"generated_at": "2026-11-10T09:00:00+00:00", "n": 2, "credits": {},
                                              "spots": [{"id": "lake", "name": "Tarn", "error": "An isolated lake"}, spot(spot_id)]}))
    (d / "alerts.json").write_text(json.dumps({"generated_at": "2026-11-10T09:00:00+00:00", "dates": [], "words": ["a"],
                                               "spots": {spot_id: {"name": "Wharfe", "level": "low", "days": [["low", 0, 0]]}}}))
    (d / "upstream" / f"{spot_id}.json").write_text(json.dumps({"id": spot_id, "overflows": [ov(2), ov(1)]}))
    (d / "overflows.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-1.8, 53.9]}, "properties": {"site_id": i}}
        for i in ("YWS01", "YWS02")]}))
    (d / "anypoint" / "overflow_ids.json").write_text(json.dumps({"ids_version": "v1", "ids": ["YWS01", "YWS02"], "name": ["A", "B"],
                                                                   "lat": [1, 2], "lon": [3, 4]}))
    (d / "anypoint" / "overflow_days.json").write_text(json.dumps({"generated_at": "t", "ids": "v1", "days": ["d1", "d2"], "today": 1,
                                                                    "scale": 1000, "p": [[1, 2], [3, 4]], "status": [0, 1], "ended_h": [None, 5]}))
    (d / "research" / "spill_durations" / f"{spot_id}.json").write_text(json.dumps({"id": spot_id, "period": {}, "overflows": [{"site_id": "YWS02"}, {"site_id": "YWS01"}]}))
    (d / "spot_scores.json").write_text(json.dumps({"warn_at": 0.4, "spots": {spot_id: {"hits": 3}, "other": {"hits": 9}}}))
    (d / "verification_live.csv").write_text("# credits line\n# more\noverflow_id,day\nYWS01,2026-11-01\nYWS02,2026-11-01\n")
    (d / "verification.json").write_text(json.dumps({"live": {"warning_table": {
        "warn_at": 0.4, "level": "high", "hits": 30, "misses": 70, "false_alarms": 30, "hit_rate": 0.3, "warnings_true": 0.5,
        "first_day": "2026-09-29", "last_day": "2026-11-08", "n_days": 33, "by_company": []}}}))
    prof = site / "spot" / spot_id / "profile"
    prof.mkdir(parents=True, exist_ok=True)
    (prof / "monitored-storm-overflows.csv").write_text("﻿spot_id,site_id,spills_2021\nwharfe,YWS02,31\nwharfe,YWS01,4\n", encoding="utf-8")
    return d


def test_the_page_is_written_linked_from_for_organisations_and_in_the_sitemap(tmp_path):
    spot = {"id": "tarn", "name": "Tarn", "kind": "lake", "days": [], "location": {}}
    bs.write_pages(tmp_path, [spot], root="https://example.org/", day="2026-11-10")
    page = (tmp_path / "data-feed.html").read_text()
    assert "<title>Data feed · SwimSignal</title>" in page and 'href="/' not in page
    assert 'href="data.html#spots-json"' in page and 'href="verification.html"' in page and 'href="clubs.html"' in page
    assert 'href="data-feed.html">the data feed</a>' in (tmp_path / "clubs.html").read_text()
    assert "<loc>https://example.org/data-feed.html</loc>" in (tmp_path / "sitemap.xml").read_text()
    # A build without the files keeps the page's own words in each example, and says so in the build log.
    assert all(v.startswith("Filled in from this build's") for v in examples(page).values())


def test_each_example_is_one_record_from_the_build_s_own_file(tmp_path):
    fake_data(tmp_path)
    assert bs.write_feed_page(tmp_path, root="https://example.org/") == []
    ex = examples((tmp_path / "data-feed.html").read_text())
    assert set(ex) == set(examples(SOURCE.read_text())) == {"spots", "alerts", "upstream", "overflows", "anypoint", "history",
                                                             "seasonal", "durations", "spot-scores", "scored-csv", "warning-table"}
    doc = {k: json.loads(v) for k, v in ex.items() if k not in ("history", "scored-csv")}
    s = doc["spots"]["spots"][0]
    assert s["id"] == SPOT and len(doc["spots"]["spots"]) == 1 and len(s["days"]) == 1 and len(s["contributors"]) == 1
    assert "guide" not in s and "secret" not in s["contributors"][0] and "quiet_by_feed" not in s["now"]   # fields left out, as the page says
    assert list(doc["alerts"]["spots"]) == [SPOT] and "days" not in doc["alerts"]["spots"][SPOT]   # its places in words are not shown
    # The upstream file's first overflow, and the same overflow in the GeoJSON and in the any-point columns.
    assert doc["upstream"]["overflows"] == [json.loads((tmp_path / "data" / "upstream" / f"{SPOT}.json").read_text())["overflows"][0]]
    assert doc["overflows"]["features"][0]["properties"]["site_id"] == "YWS02"
    assert doc["anypoint"]["overflow_ids.json"]["ids"] == "YWS02" and doc["anypoint"]["overflow_days.json"]["p"] == [3, 4]
    assert doc["anypoint"]["overflow_days.json"]["status"] == 1 and doc["anypoint"]["overflow_days.json"]["ended_h"] == 5
    assert doc["durations"]["overflows"] == [{"site_id": "YWS02"}] and doc["seasonal"]["seasonal"]["years"] == [2024, 2025]
    assert doc["spot-scores"]["spots"] == {SPOT: {"hits": 3}}
    assert doc["warning-table"]["live"]["warning_table"]["hits"] == 30 and "by_company" not in doc["warning-table"]["live"]["warning_table"]
    # CSVs: the header and one row, with no comment lines and no byte-order mark.
    assert ex["scored-csv"] == "overflow_id,day\nYWS01,2026-11-01" and ex["history"] == "spot_id,site_id,spills_2021\nwharfe,YWS02,31"
    # A list of plain values sits on one line.
    assert '"p_spill_days": [0.1, 0.1, 0.1, 0.1, 0.1]' in ex["spots"]


def test_without_the_example_spot_the_first_with_an_overflow_upstream_is_used(tmp_path):
    fake_data(tmp_path, spot_id="other-river")
    ex = bs.feed_examples(tmp_path / "data")
    assert json.loads(ex["spots"])["spots"][0]["id"] == "other-river" and "other-river" in json.loads(ex["alerts"])["spots"]


def test_a_broken_file_loses_only_its_own_example(tmp_path):
    fake_data(tmp_path)
    (tmp_path / "data" / "overflows.geojson").write_text("not json")
    (tmp_path / "data" / "spot_scores.json").unlink()
    assert bs.write_feed_page(tmp_path, root="https://example.org/") == ["overflows", "spot-scores"]
    ex = examples((tmp_path / "data-feed.html").read_text())
    assert ex["overflows"] == "Filled in from this build's overflows.geojson." and json.loads(ex["upstream"])["id"] == SPOT


def test_the_credit_and_the_warning_figures_are_this_build_s(tmp_path, monkeypatch):
    from dipcast import scotland_trial
    monkeypatch.setattr(scotland_trial, "enabled", lambda: False)   # the trial's credit is checked below, on the fallback
    fake_data(tmp_path)
    bs.write_feed_page(tmp_path, root="https://example.org/")
    page = (tmp_path / "data-feed.html").read_text()
    c = bs.data_credits("https://example.org/")
    credit = html.unescape(re.search(r'<blockquote id="feed-credit">(.*?)</blockquote>', page, re.S)[1])
    assert credit == f'{c["attribution"]} {c["modified"]}'
    assert "this uses Environment Agency flood and river level data from the real-time data API (Beta)" in credit   # the EA's own sentence
    words = text(page)
    assert "it warned of about three in ten spills. About one in two of its warnings were followed by a spill." in words
    # The page's own fallback credit is the credit with the Scotland trial on, as on the live site when it was written.
    fallback = html.unescape(re.search(r'<blockquote id="feed-credit">(.*?)</blockquote>', SOURCE.read_text(), re.S)[1])
    assert fallback == f'{bs.SCOTLAND_CREDIT["credit"]}. {c["attribution"]} {c["modified"]}'


def test_the_page_says_what_the_brief_asks_and_nothing_it_cannot_back():
    page = SOURCE.read_text()
    words = text(page)
    # What it is not, with the scored skill linked to the Accuracy page.
    for said in ("Not a water test.", "Not a toxin measurement.", "Not a swimming clearance.", 'id="warn-figures"'):
        assert said in (page if said.startswith("id=") else words), said
    assert 'The <a href="/verification">Accuracy page</a> has the full scores' in page
    # Cadence as measured: 30 minutes only as what the schedule asks for.
    assert words.count("30 minutes") == 1 and "It asks to run every 30 minutes, but GitHub runs scheduled jobs when it has room." in words
    assert "a median 4.6 hours apart" in words and "a median 5.8 hours, at most 10.6 hours" in words
    # Licences: Open-Meteo's free plan is non-commercial; the consents register is in no file.
    assert "Not on Open-Meteo's free plan, which is for non-commercial use only." in words and "Professional plan" in words
    assert "Not in any file, and not part of any feed: the Environment Agency's register of consented discharges" in words
    for lic in ("CC BY 4.0", "OGL v3.0", "ODbL 1.0", "CC BY-SA 4.0"):
        assert lic in words, lic
    # No prices, and the way to talk: the shared address and For organisations.
    assert not re.search(r"[£€$]\s?\d|per (month|year)|a month\b|/month", words)
    assert set(re.findall(r'mailto:([^"]+)', page)) == {"hello@swimsignal.co.uk"} and 'href="/clubs">For organisations</a>' in page
    # The site's names (docs/DESIGN.md, "The level's names, checked"): the sewage spill risk is a score, not a probability;
    # the weight is not a chance; no pills or eyebrows.
    assert "its sewage spill risk (a 0–100 score" in words and "it is a score, not a probability" in words
    assert "not a measured concentration and not a chance of contamination" in words and "exposure index" not in words
    assert not re.search(r'class="[^"]*(pill|eyebrow|callout|badge)', page)
