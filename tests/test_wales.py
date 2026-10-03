"""Welsh bathing waters from Natural Resources Wales (wales.py): official information beside, never
inside, a SwimSignal forecast. NRW's service refused GitHub's runners on 3 Oct 2026, so the build
shows a dated snapshot and the page asks NRW for the current samples and forecasts."""

import json
from datetime import datetime

import httpx

from dipcast import wales

NOW = datetime.fromisoformat("2026-10-03T22:30:00+01:00")


def site(key="ukl2201-36040", name="Llanishen Reservoir", kind="LakeBathingWater", rating="Excellent", year=2025):
    return {"eubwidNotation": key, "name": {"_value": name},
            "type": ["http://environment.data.gov.uk/def/bathing-water/BathingWater", f"http://environment.data.gov.uk/def/bathing-water/{kind}"],
            "latestComplianceAssessment": {"_about": f"http://x/compliance-rBWD/point/{key[-5:]}/year/{year}",
                                           "complianceClassification": {"name": {"_value": rating}}} if rating else {}}


def sample(key="ukl2201-36040", at="2026-09-09T11:53:00", ecoli=10, q="<", ent=12):
    return {"bwq_bathingWater": {"eubwidNotation": key}, "sampleDateTime": {"inXSDDateTime": {"_value": at}},
            "escherichiaColiCount": ecoli, "escherichiaColiQualifier": {"countQualifierNotation": q},
            "intestinalEnterococciCount": ent, "intestinalEnterococciQualifier": {"countQualifierNotation": "="}}


def test_sites_keep_kind_rating_year_and_an_unrated_new_water():
    sites = wales.parse_sites([site(), site("ukl1402-38620", "The Warren, Hay On Wye", "RiverBathingWater", "Sufficient"),
                               site("ukl1405-39100", "Llandeilo Swing Bridge", "RiverBathingWater", None),
                               {"eubwidNotation": "ukl0000-00000", "name": {"_value": "Not a bathing water"}, "type": []}])
    assert [(s["name"], s["kind"], s["rating"] and s["rating"]["value"]) for s in sites] == [
        ("Llandeilo Swing Bridge", "river", None), ("Llanishen Reservoir", "lake", "Excellent"), ("The Warren, Hay On Wye", "river", "Sufficient")]
    assert sites[1]["rating"]["year"] == 2025
    assert sites[1]["profile"] == "https://environment.data.gov.uk/wales/bathing-waters/profiles/profile.html?site=ukl2201-36040"
    try:
        wales.parse_sites([site(), site()])
        raise AssertionError("a duplicated id must not publish")
    except ValueError:
        pass


def test_samples_keep_uk_time_both_counts_and_drop_unreadable_ones():
    got = wales.parse_samples([sample(), sample(at="2026-09-01T10:00:00", ecoli=500, q="="),
                               sample("ukl1402-38620", ecoli=True), sample("ukl1402-38621", at="yesterday")])
    assert got == {"ukl2201-36040": {"taken_at": "2026-09-09T11:53:00+01:00", "ecoli": {"value": 10.0, "qualifier": "<"},
                                     "enterococci": {"value": 12.0, "qualifier": "="}}}


def test_a_refused_build_uses_the_dated_snapshot_once_and_never_a_forecast(tmp_path):
    seed = tmp_path / "wales.json"
    seed.write_text(json.dumps({"fetched_at": "2026-10-03T22:33:00+01:00", "source": wales.SITES,
                                "site_items": [site()], "sample_items": [sample()]}))
    asked = []

    def refused(request):
        asked.append(str(request.url))
        return httpx.Response(403)

    with httpx.Client(transport=httpx.MockTransport(refused)) as c:
        snap = wales.fetch(datetime.fromisoformat("2026-10-04T08:00:00+01:00"), c, seed)
    assert len(asked) == 1   # one refusal is enough
    assert snap["state"] == "cached" and snap["error"] == "HTTP 403" and snap["fetched_at"] == "2026-10-03T22:33:00+01:00"
    assert snap["sites"][0]["sample"]["state"] == "ok" and "forecast" not in json.dumps(snap)
    html = wales.render(snap)
    assert "Snapshot of sites and samples <time" in html and "1 designated Welsh bathing waters, 1 of them on lakes or rivers" in html
    assert 'data-sample-at="2026-09-09T11:53:00+01:00"' in html and "Current NRW forecast: open the profile" in html
    assert "no forecast does not mean clean water" in html and "Contains Natural Resources Wales information" in html
    # A snapshot from the future, or none at all: an empty list that says so, not an invented one.
    with httpx.Client(transport=httpx.MockTransport(refused)) as c:
        assert wales.fetch(datetime.fromisoformat("2026-10-01T08:00:00+01:00"), c, seed)["state"] == "unavailable"
        gone = wales.fetch(NOW, c, tmp_path / "absent.json")
    assert gone["state"] == "unavailable" and gone["sites"] == [] and "could not be loaded" in wales.render(gone)


def test_a_live_answer_is_used_and_names_are_escaped():
    def ok(request):
        items = [site(name="Bae <b>Caerdydd</b>")] if request.url.path.endswith("bathing-water.json") else [sample()]
        return httpx.Response(200, json={"result": {"items": items}})

    with httpx.Client(transport=httpx.MockTransport(ok)) as c:
        snap = wales.fetch(NOW, c)
    assert snap["state"] == "live" and snap["fetched_at"] == NOW.isoformat()
    html = wales.render(snap)
    assert "Bae &lt;b&gt;Caerdydd&lt;/b&gt;" in html and "<b>Caerdydd" not in html
    assert "Latest NRW sample <time" in html and "E. coli &lt;10, intestinal enterococci 12 per 100 ml" in html


def test_the_committed_snapshot_parses():
    snap = json.loads(wales.SNAPSHOT.read_text())
    parsed = wales.snapshot_from(snap["site_items"], snap["sample_items"], snap["fetched_at"])
    assert len(parsed["sites"]) >= 100 and {s["kind"] for s in parsed["sites"]} <= {"coast", "estuary", "lake", "river"}
