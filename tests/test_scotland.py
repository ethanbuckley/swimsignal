"""Scottish bathing waters from SEPA's OGL points layer (scotland.py): names, latest ratings and
links to SEPA's pages. Samples, signs and advice stay on SEPA's site, whose conditions differ."""

from datetime import datetime

import httpx

from dipcast import scotland

NOW = datetime.fromisoformat("2026-10-03T22:45:00+01:00")


def feature(code="472272", name="Largs (Pencil Beach)", rating="Excellent", year=2025):
    return {"attributes": {"description": name, "year": year, "class_description": rating,
                           "bw_url": f"https://bathingwaters.sepa.org.uk/locations-and-results/results?location={code}"},
            "geometry": {"x": -4.860739943881484, "y": 55.78241501900373}}


def test_ratings_unrated_waters_and_links_are_kept_as_sepa_gives_them():
    sites = scotland.parse([feature(), feature("100001", "Ballachulish", "Unclassified", 2026)])
    assert [(s["id"], s["name"], s["rating"], s["unrated_year"]) for s in sites] == [
        ("sepa-100001", "Ballachulish", None, 2026),
        ("sepa-472272", "Largs (Pencil Beach)", {"value": "Excellent", "year": 2025}, None)]
    assert sites[1]["page"] == "https://bathingwaters.sepa.org.uk/locations-and-results/results?location=472272"
    assert (sites[1]["lat"], sites[1]["lon"]) == (55.78242, -4.86074)


def test_a_link_off_sepas_site_or_a_repeated_water_stops_the_list():
    for bad in ([feature(), feature()], [{**feature(), "attributes": {**feature()["attributes"], "bw_url": "https://evil.example/?location=1"}}],
                [{"attributes": {"bw_url": feature()["attributes"]["bw_url"]}}]):
        try:
            scotland.parse(bad)
            raise AssertionError("must not publish")
        except ValueError:
            pass


def test_fetch_is_one_request_and_a_failure_says_unavailable():
    asked = []

    def ok(request):
        asked.append(request)
        return httpx.Response(200, json={"features": [feature(name="Loch <b>Morlich</b>")]})

    with httpx.Client(transport=httpx.MockTransport(ok)) as c:
        snap = scotland.fetch(NOW, c)
    assert len(asked) == 1 and snap["state"] == "live" and len(snap["sites"]) == 1
    html = scotland.render(snap)
    assert "Loch &lt;b&gt;Morlich&lt;/b&gt;" in html and "2025 rating: Excellent" in html
    assert "Signs, samples and current advice: on SEPA's page" in html and "not today's water quality" in html
    assert "Open Government Licence v2.0" in html

    def down(request):
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(down)) as c:
        gone = scotland.fetch(NOW, c)
    assert gone["state"] == "unavailable" and gone["error"] == "HTTP 503" and gone["sites"] == []
    assert "could not be loaded" in scotland.render(gone)

    def truncated(request):
        return httpx.Response(200, json={"features": [feature()], "exceededTransferLimit": True})

    with httpx.Client(transport=httpx.MockTransport(truncated)) as c:
        assert scotland.fetch(NOW, c)["state"] == "unavailable"   # a partial list is not published as the whole
