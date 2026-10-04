"""Bathing waters in the Republic of Ireland (ireland.py, the EPA, CC BY 4.0) and Northern Ireland
(northern_ireland.py, DAERA, OGL v3.0): official information on the coverage page, beside and never
inside a SwimSignal forecast. The fixtures are trimmed copies of the sources' answers on 4 Oct 2026."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from dipcast import ireland, northern_ireland

FIX = Path(__file__).parent / "fixtures" / "ireland"
NOW = datetime.fromisoformat("2026-10-04T19:30:00+01:00")


def load(name):
    return json.loads((FIX / name).read_text())


def epa(asked=None, down=(), rows=None):
    """A stand-in for the EPA's API: paged lists as it pages them, `down` paths answer 503."""
    rows = rows or {ireland.IN_SEASON: load("epa_in_season.json"), ireland.OUT_SEASON: load("epa_out_season.json")}

    def handler(request):
        url = str(request.url).split("?")[0]
        if asked is not None:
            asked.append(str(request.url))
        if url in down:
            return httpx.Response(503)
        if url == ireland.LOCATIONS:
            return httpx.Response(200, json=load("epa_locations.json"))
        if url == ireland.ALERTS:
            return httpx.Response(200, json=load("epa_alerts.json"))
        q = parse_qs(urlsplit(str(request.url)).query)
        page, per = int(q["page"][0]), int(q["per_page"][0])
        items = rows[url]
        return httpx.Response(200, json={"count": len(items), "length": per, "page": page,
                                         "list": items[(page - 1) * per: page * per]})
    return httpx.MockTransport(handler)


def fetch(tmp_path, now=NOW, **kw):
    with httpx.Client(transport=epa(**kw)) as c:
        return ireland.fetch(now, c, cache=tmp_path / "epa.json")


def by_name(snap):
    return {s["name"]: s for s in snap["sites"]}


@pytest.fixture(autouse=True)
def small_pages(monkeypatch):
    monkeypatch.setattr(ireland, "PER_PAGE", 40)   # 134 in-season rows: four pages, read from the last


def test_waters_keep_irish_names_designated_first_and_the_epas_kinds():
    sites = ireland.parse_locations(load("epa_locations.json")["list"])
    names = [s["name"] for s in sites]
    assert names.index("Oileán Chléire") > names.index("Trá na mBan, An Spidéal")   # not designated: after every designated water
    assert [s["designated"] for s in sites] == sorted((s["designated"] for s in sites), reverse=True)
    s = {x["name"]: x for x in sites}
    assert s["Loughrea Lake"]["rating"] == {"value": "Excellent", "year": 2025}
    assert s["Loughrea Lake"]["page"] == "https://www.beaches.ie/find-a-beach/#/beach/IEWEBWL29_194_0100"
    assert s["Belmullet Tidal Pool & Shore Road Bathing Area"]["unrated_year"] == 2025   # spaces tidied, "Not classified"
    assert s["Dun Laoghaire Baths"]["season_restriction"] and s["Dun Laoghaire Baths"]["rating"]["value"] == "Poor"
    assert not s["Trá na mBan, An Spidéal"]["season_restriction"]   # an old reason with "No" is not a restriction
    assert s["Baginbun"]["rating"] is None and s["Baginbun"]["designated"]
    assert s["Ballycuggeran"]["id"] == "IESHBWL25_191a_0300"
    item = load("epa_locations.json")["list"][0]
    for bad in ([item, item], [{**item, "beach_type": "Something new"}], [{**item, "beach_name": " "}]):
        with pytest.raises(ValueError):
            ireland.parse_locations(bad)


def test_counts_keep_their_qualifier_and_unreadable_samples_are_left_out():
    rows = [{"beach_id": "IEWEBWL29_194_0100", "result_date": "2026-09-14", "e_coli_result": ">2420",
             "intestinal_enterococci_result": "<10", "sample_water_quality_status": "Poor"},
            {"beach_id": "IEWEBWL29_194_0100", "result_date": "2026-09-20", "e_coli_result": "not tested"},
            {"beach_id": "IEWEBWL29_194_0100", "result_date": "yesterday", "e_coli_result": "5"}]
    got = ireland.parse_samples(rows, [])["IEWEBWL29_194_0100"]
    assert got == {"date": "2026-09-14", "season": "in", "ecoli": {"value": 2420.0, "qualifier": ">"},
                   "enterococci": {"value": 10.0, "qualifier": "<"}, "status": "Poor"}


def test_the_build_lists_restrictions_samples_and_missing_ones_with_their_dates(tmp_path):
    asked = []
    snap = fetch(tmp_path, asked=asked)
    assert snap["state"] == "live" and len(snap["sites"]) == 11 and "error" not in snap
    s = by_name(snap)
    assert s["Lilliput, Lough Ennell"]["alerts"] == [{
        "type": "Bathing is temporarily prohibited", "since": "2026-09-08",
        "cause": "Water quality deteriorated due to suspected agricultural activities/runoff",
        "notice": "https://www.beaches.ie/wp-content/files//notice/3308da41-f850-49f1-84af-4f2ef9641a4b.pdf"}]
    assert s["Loughrea Lake"]["alerts"] == []
    assert s["Lilliput, Lough Ennell"]["sample"] | {} == {   # the out-of-season sample is the latest
        "state": "ok", "date": "2026-09-17", "season": "out", "ecoli": {"value": 1120.0, "qualifier": "="},
        "enterococci": {"value": 406.0, "qualifier": "="}, "status": "Poor"}
    assert s["Loughrea Lake"]["sample"]["date"] == "2026-09-14" and s["Loughrea Lake"]["sample"]["season"] == "in"
    assert s["Oileán Chléire"]["sample"] == {"state": "none"}
    assert snap["samples"]["season"] == 2026
    in_season = [parse_qs(urlsplit(u).query) for u in asked if u.startswith(ireland.IN_SEASON)]
    assert in_season[0]["per_page"] == ["1"]   # the count first, then the pages from the last back to 2025
    assert [q["page"][0] for q in in_season[1:]] == ["4", "3", "2", "1"]
    html = ireland.render(snap)
    assert "11 sites" in html and "Ballyallia Lake, Ennis; Lilliput, Lough Ennell." in html
    assert '<strong>Bathing is temporarily prohibited</strong>, since <time datetime="2026-09-08">8 Sep 2026</time> (EPA).' in html
    assert "Notice (PDF)" in html and "Bathing restricted for the whole season" in html
    assert "Other monitored water: not a designated bathing water, so it has no rating" in html
    assert "No sample listed for 2026" in html and "Not classified in 2025" in html
    assert "out of season: E. coli 1,120, intestinal enterococci 406 per 100 ml (EPA: Poor)." in html
    assert "More than 30 days old." in html   # Baginbun's last sample, 1 Sep 2026
    assert "Trá na mBan, An Spidéal" in html and "CC BY 4.0" in html and "The EPA does not endorse SwimSignal." in html


def test_a_second_build_within_the_hour_asks_only_for_restrictions(tmp_path):
    fetch(tmp_path)
    asked = []
    snap = fetch(tmp_path, now=NOW + timedelta(hours=1), asked=asked)
    assert snap["state"] == "live" and [u.split("?")[0] for u in asked] == [ireland.ALERTS]
    asked = []
    fetch(tmp_path, now=NOW + timedelta(hours=4), asked=asked)   # samples are read again after three hours
    assert ireland.LOCATIONS not in {u.split("?")[0] for u in asked} and any(u.startswith(ireland.IN_SEASON) for u in asked)


def test_when_the_epa_is_down_the_kept_list_shows_with_its_date_and_restrictions_are_never_kept(tmp_path):
    fetch(tmp_path)
    later = NOW + timedelta(days=2)
    everything = (ireland.LOCATIONS, ireland.ALERTS, ireland.IN_SEASON, ireland.OUT_SEASON)
    snap = fetch(tmp_path, now=later, down=everything)
    assert snap["state"] == "partial" and len(snap["sites"]) == 11
    assert snap["locations"]["state"] == "kept" and snap["samples"]["state"] == "kept"
    assert snap["alerts"] == {"state": "unavailable"}
    assert all(s["alerts"] is None for s in snap["sites"])
    html = ireland.render(snap)
    assert "could not be read for this build" in html and "in force" not in html
    assert "kept from an earlier build because the EPA did not answer" in html
    assert 'The list of waters is from <time datetime="2026-10-04T19:30:00+01:00">4 Oct 2026, 19:30</time>, kept' in html
    gone = fetch(tmp_path, now=NOW + timedelta(days=40), down=everything)
    assert gone["state"] == "unavailable" and gone["sites"] == []
    assert "could not be loaded for this build" in ireland.render(gone)
    first = fetch(tmp_path / "empty", down=everything)
    assert first["state"] == "unavailable" and "locations: HTTP 503" in first["error"]


def test_samples_that_reach_back_too_far_are_unavailable_never_part_shown(tmp_path, monkeypatch):
    monkeypatch.setattr(ireland, "MAX_PAGES", 2)
    snap = fetch(tmp_path)
    assert snap["samples"]["state"] == "unavailable"
    assert {s["sample"]["state"] for s in snap["sites"]} == {"unavailable"}
    assert "Latest sample unavailable for this build" in ireland.render(snap)


def test_an_ended_restriction_and_a_notice_off_beaches_ie_are_left_out():
    alerts = load("epa_alerts.json")["list"]
    got = ireland.parse_alerts([{**alerts[0], "incident_end_date": "2026-10-01T00:00:00"},
                                {**alerts[1], "bathing_notice_pdf": "https://evil.example/notice.pdf"}], NOW)
    assert list(got) == ["IESHBWL27_72_0100"] and got["IESHBWL27_72_0100"][0]["notice"] is None


# Northern Ireland


def daera(features=None, status=200, asked=None):
    def handler(request):
        if asked is not None:
            asked.append(request)
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"features": features if features is not None else load("daera_points.json")["features"]})
    return httpx.MockTransport(handler)


def ni_fetch(tmp_path, now=NOW, **kw):
    with httpx.Client(transport=daera(**kw)) as c:
        return northern_ireland.fetch(now, c, cache=tmp_path / "ni.json")


def test_daeras_33_waters_with_indicator_time_profile_and_the_advice_at_reas_wood(tmp_path):
    asked = []
    snap = ni_fetch(tmp_path, asked=asked)
    assert len(asked) == 1 and snap["state"] == "live" and len(snap["sites"]) == 33
    assert not any("rain" in k for site in snap["sites"] for k in site)   # plan section 11, item 5: no rain figures
    s = {x["name"]: x for x in snap["sites"]}
    rea = s["Rea's Wood"]
    assert rea["kind"] == "inland" and rea["indicator"] == {"code": "NoBathing", "words": "Temporary advice against bathing"}
    assert rea["sampled_at"] == "2026-08-24T13:50:51+01:00"   # ArcGIS milliseconds, UTC, shown in UK time
    assert s["Ballygally"]["candidate"] and s["Magilligan Downhill"]["name"] == "Magilligan Downhill"   # spaces tidied
    assert all(x["profile"].startswith("https://www.daera-ni.gov.uk/") for x in snap["sites"])
    html = northern_ireland.render(snap)
    assert "33 bathing waters, 32 on the coast and 1 inland" in html
    assert "<strong>DAERA: Temporary advice against bathing</strong>. Sampled" in html
    assert "DAERA advises against bathing here for the 2026 bathing season, after a Poor rating in 2025." in html
    assert "DAERA's indicator: Excellent water quality. Sampled" in html and "Coast, candidate bathing water" in html
    assert "More than 30 days ago." in html   # Rea's Wood, 24 Aug
    assert "Open Government Licence v3.0" in html and "DAERA does not endorse SwimSignal." in html
    next_year = dict(snap, checked_at="2027-06-01T12:00:00+01:00")
    assert "2026 bathing season" not in northern_ireland.render(next_year)   # the season note does not outlive its year


def test_daera_fails_soft_to_the_kept_copy_then_unavailable(tmp_path):
    ni_fetch(tmp_path)
    kept = ni_fetch(tmp_path, now=NOW + timedelta(hours=6), status=503)
    assert kept["state"] == "kept" and kept["error"] == "HTTP 503" and kept["fetched_at"] == NOW.isoformat()
    assert "kept from an earlier build because DAERA did not answer" in northern_ireland.render(kept)
    gone = ni_fetch(tmp_path, now=NOW + timedelta(days=4), status=503)
    assert gone["state"] == "unavailable" and gone["sites"] == []
    assert "could not be loaded for this build" in northern_ireland.render(gone)
    a = load("daera_points.json")["features"][0]["attributes"]
    for bad in ([{"attributes": a}, {"attributes": a}], [{"attributes": {**a, "Profile__URL": "https://evil.example/p.pdf"}}]):
        with pytest.raises(ValueError):
            northern_ireland.parse(bad)
    odd = northern_ireland.parse([{"attributes": {**a, "water_quality_indicator": "Closed", "Sampling_datetime": None}}])[0]
    assert "Closed (not a value SwimSignal knows; see the dashboard). No sampling time listed." in northern_ireland.render(
        {"fetched_at": NOW.isoformat(), "sites": [odd]})


def test_the_coverage_page_carries_both_lists_and_says_there_is_no_irish_forecast(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_site
    roi, ni = fetch(tmp_path / "c"), ni_fetch(tmp_path / "c")
    (tmp_path / "site").mkdir()
    build_site.write_pages(tmp_path / "site", [], ireland=roi, northern_ireland=ni)
    page = (tmp_path / "site" / "coverage.html").read_text()
    assert "<!-- IRELAND_DIRECTORY -->" not in page and "<!-- NI_DIRECTORY -->" not in page
    assert 'id="ireland-sites"' in page and 'id="ni-sites"' in page
    assert "SwimSignal does not issue forecasts in Ireland." in page
    assert "SwimSignal does not issue forecasts in Northern Ireland." in page
    terms = (tmp_path / "site" / "terms.html").read_text()
    assert "Environmental Protection Agency (Ireland)" in terms and "DAERA" in terms
    bare = tmp_path / "bare"
    bare.mkdir()
    build_site.write_pages(bare, [])   # a build without the lists still says where to look
    page = (bare / "coverage.html").read_text()
    assert "could not be loaded for this build" in page and "beaches.ie" in page
