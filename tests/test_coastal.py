from datetime import datetime, timedelta
import json

import httpx

from dipcast import coastal

NOW = datetime.fromisoformat("2026-09-15T12:00:00+01:00")
KEY = "ukc2102-03600"
SITE = {"eubwidNotation": KEY, "name": {"_value": "Spittal <script>"},
        "type": ["http://environment.data.gov.uk/def/bathing-water/CoastalBathingWater"],
        "latestComplianceAssessment": {"_about": "http://environment.data.gov.uk/data/x/year/2025",
                                        "complianceClassification": {"name": {"_value": "Good"}}}}
PRED = {"stp_bathingWater": f"http://environment.data.gov.uk/id/bathing-water/{KEY}",
        "predictedOn": {"_value": "2026-09-15"}, "predictedAt": {"_value": "2026-09-15T08:30:00"},
        "publishedAt": {"_value": "2026-09-15T08:41:06"}, "expiresAt": {"_value": "2026-09-16T08:29:00"},
        "prfOriginType": "PRF_PROVIDED", "riskLevel": "http://environment.data.gov.uk/def/bwq-stp/increased",
        "_about": "http://environment.data.gov.uk/data/bathing-water-quality/stp-risk-prediction/example"}


def advice(*predictions, now=NOW):
    return coastal.parse([SITE], predictions, now)[0]["advice"]


def test_only_current_complete_official_advice_is_shown():
    current = advice(PRED)
    assert current["state"] == "increased"
    assert current["published_at"] == "2026-09-15T08:41:06+01:00"
    assert current["source"] == PRED["_about"]
    assert advice(PRED, now=datetime.fromisoformat("2026-09-16T08:29:00+01:00"))["state"] == "no_current_advice"
    for field, broken in [("publishedAt", "nonsense"), ("expiresAt", None),
                          ("predictedOn", "2026-09-14"), ("publishedAt", "2026-09-16T12:00:00"),
                          ("riskLevel", "unrecognised")]:
        assert advice({**PRED, field: broken})["state"] == "no_current_advice"
    # A "normal" record says what it is only through its origin; an unknown one is not advice.
    normal = {**PRED, "riskLevel": "http://environment.data.gov.uk/def/bwq-stp/normal"}
    for origin in ["UNKNOWN", None]:
        assert advice({**normal, "prfOriginType": origin})["state"] == "no_current_advice"


def test_normal_non_forecast_records_and_conflicts_are_not_an_all_clear():
    normal = {**PRED, "riskLevel": "http://environment.data.gov.uk/def/bwq-stp/normal"}
    assert advice(normal)["state"] == "no_increased_risk"
    assert advice({**normal, "prfOriginType": "NON_PRF_SITE"})["state"] == "no_forecast"
    assert advice(normal, {**normal, "prfOriginType": "NON_PRF_SITE"})["state"] == "unavailable"
    assert advice()["state"] == "no_current_advice"


# Plymouth Hoe East on 1 Oct 2026, as the EA published it: the season's last forecast, "normal", at
# 09:06, then at 15:08 a notice after a sewage incident, "increased" with no prfOriginType. On 4 Oct
# the incident was still open and the EA's own widget said "Bathing is not advised today due to
# pollution from sewage".
PLYMOUTH = "ukk4100-26400"
LAST_FORECAST = {"stp_bathingWater": f"http://environment.data.gov.uk/id/bathing-water/{PLYMOUTH}",
                 "predictedOn": {"_value": "2026-10-01"}, "predictedAt": {"_value": "2026-10-01T08:30:00"},
                 "publishedAt": {"_value": "2026-10-01T09:06:51"}, "expiresAt": {"_value": "2026-10-02T08:29:00"},
                 "prfOriginType": "PRF_PROVIDED", "riskLevel": "http://environment.data.gov.uk/def/bwq-stp/normal",
                 "comment": {"_value": "Pollution risk forecasts are now finished for 2026"},
                 "_about": "http://environment.data.gov.uk/data/bathing-water-quality/stp-risk-prediction/point/26400/date/20261001-090651"}
INCIDENT = {"stp_bathingWater": f"http://environment.data.gov.uk/id/bathing-water/{PLYMOUTH}",
            "predictedOn": {"_value": "2026-10-01"}, "predictedAt": {"_value": "2026-10-01T15:08:20"},
            "publishedAt": {"_value": "2026-10-01T15:08:51"}, "expiresAt": {"_value": "2026-10-02T15:07:20"},
            "riskLevel": "http://environment.data.gov.uk/def/bwq-stp/increased",
            "comment": {"_value": "Risk of reduced water quality due to sewage"},
            "_about": "http://environment.data.gov.uk/data/bathing-water-quality/stp-risk-prediction/point/26400/date/20261001-150851"}


def test_an_incident_notice_without_an_origin_is_a_warning_and_outranks_a_normal_forecast():
    site = {**SITE, "eubwidNotation": PLYMOUTH, "name": {"_value": "Plymouth Hoe East"}}

    def at(iso, records=(LAST_FORECAST, INCIDENT)):
        return coastal.parse([site], list(records), datetime.fromisoformat(iso))[0]["advice"]

    assert at("2026-10-01T12:00:00+01:00")["state"] == "no_increased_risk"    # before the notice
    after = at("2026-10-01T16:00:00+01:00")
    assert after["state"] == "increased" and after["origin"] is None
    assert after["expires_at"] == "2026-10-02T15:07:20+01:00" and after["source"] == INCIDENT["_about"]
    assert at("2026-10-02T09:00:00+01:00")["state"] == "increased"            # the forecast has expired, the notice has not
    assert at("2026-10-02T15:07:20+01:00")["state"] == "no_current_advice"
    # Two warnings in force: the later one is shown, with its own times.
    later = {**INCIDENT, "publishedAt": {"_value": "2026-10-01T18:00:00"}, "_about": "later"}
    assert at("2026-10-01T19:00:00+01:00", (INCIDENT, later, LAST_FORECAST))["source"] == "later"


def test_catalogue_scope_historical_rating_and_safe_rendering():
    river = {**SITE, "eubwidNotation": "ukc2102-03601", "type": ["http://environment.data.gov.uk/def/bathing-water/RiverBathingWater"]}
    sites = coastal.parse([SITE, river], [PRED], NOW)
    assert len(sites) == 1 and sites[0]["kind"] == "coast"
    assert sites[0]["rating"]["year"] == 2025
    rendered = coastal.render({"sites": sites, "fetched_at": NOW.isoformat()})
    assert "Spittal &lt;script&gt;" in rendered and "Spittal <script>" not in rendered
    assert "2025 rating: Good" in rendered
    assert 'data-advice-expires="2026-09-16T08:29:00+01:00"' in rendered
    assert "not mean clean water" in rendered and "check the signs" in rendered
    # Times as people read them, in UK time, with the exact value kept in the element (3 Oct 2026
    # the live page showed "Snapshot 2026-10-03T21:45:47.570920+01:00").
    assert 'Snapshot <time datetime="2026-09-15T12:00:00+01:00">15 Sep 2026, 12:00</time>.' in rendered
    assert 'expires <time datetime="2026-09-16T08:29:00+01:00">16 Sep 2026, 08:29</time>' in rendered
    assert coastal.when("not a time <b>") == "not a time &lt;b&gt;"
    # Every site has a fold for today's advice from the EA itself (coverage.html loads the EA's panel
    # into it); without the page's script it points to the profile.
    assert (f'<details class="ea-today" data-site="{KEY}"><summary>Today\'s EA advice</summary>'
            f'<p class="small">Open the <a href="https://environment.data.gov.uk/bwq/profiles/profile.html?site={KEY}">'
            "official profile</a> for today's advice.</p></details></li>") in rendered


def test_source_failures_preserve_catalogue_but_never_advice():
    asked = []
    def handler(request):
        asked.append(request)
        if str(request.url).startswith(coastal.CATALOGUE):
            return httpx.Response(200, json={"result": {"items": [SITE]}})
        return httpx.Response(503)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = coastal.fetch(NOW, client)
    assert len(asked) == 2
    assert snapshot["status"] == "advice_unavailable"
    assert snapshot["sites"][0]["advice"] == {"state": "unavailable"}


def test_current_and_yesterday_empty_results_are_explicitly_no_advice():
    days = []
    def handler(request):
        if str(request.url).startswith(coastal.CATALOGUE):
            rows = [SITE]
        else:
            days.append(request.url.params["predictedOn"])
            rows = []
        return httpx.Response(200, json={"result": {"items": rows}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = coastal.fetch(NOW, client)
    assert days == ["2026-09-15", "2026-09-14"]
    assert snapshot["status"] == "ok"
    assert snapshot["sites"][0]["advice"]["state"] == "no_current_advice"


def test_bad_catalogue_and_oversized_or_unending_source_fail_closed():
    for response in [httpx.Response(403), httpx.Response(200, json={"result": {"items": []}}),
                     httpx.Response(200, content=b" " * 4_000_001),
                     httpx.Response(200, json={"result": {"items": [SITE] * 500}})]:
        calls = []
        def handler(request):
            calls.append(request)
            return response
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            snapshot = coastal.fetch(NOW, client)
        assert snapshot["status"] == "unavailable" and snapshot["sites"] == []
        assert len(calls) <= 2


def test_static_build_includes_directory_and_api_template_keeps_official_link(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_site
    snapshot = {"sites": coastal.parse([SITE], [PRED], NOW), "fetched_at": NOW.isoformat()}
    build_site.write_pages(tmp_path, [], coastal=snapshot)
    page = (tmp_path / "coverage.html").read_text()
    assert "Spittal &lt;script&gt;" in page and "<!-- COASTAL_DIRECTORY -->" not in page
    assert "data-advice-expires" in page
    assert "coastal-count" in page and "profile.html?site=" + KEY in page


def test_refused_live_catalogue_uses_dated_names_and_never_cached_advice(tmp_path, monkeypatch):
    seed = tmp_path / "catalogue.json"
    seed.write_text(json.dumps({"source": coastal.CATALOGUE, "fetched_at": "2026-09-14T12:00:00+01:00",
                               "items": [SITE], "advice": [PRED]}))
    monkeypatch.setattr(coastal, "FALLBACK", seed)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(403)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = coastal.fetch(NOW, client)
    assert len(calls) == 1
    assert snapshot["status"] == "advice_unavailable"
    assert snapshot["catalogue_state"] == "cached" and snapshot["catalogue_error"] == "HTTP 403"
    assert snapshot["catalogue_fetched_at"] == "2026-09-14T12:00:00+01:00"
    assert snapshot["sites"][0]["advice"] == {"state": "unavailable"}
    assert "New designations or changed ratings may not be included" in coastal.render(snapshot)
    assert 'retrieved <time datetime="2026-09-14T12:00:00+01:00">14 Sep 2026, 12:00</time>.' in coastal.render(snapshot)


def test_invalid_or_future_catalogue_fallback_is_not_published(tmp_path, monkeypatch):
    seed = tmp_path / "catalogue.json"
    monkeypatch.setattr(coastal, "FALLBACK", seed)
    for source, stamp in [("https://other.invalid/", "2026-09-14T12:00:00+01:00"),
                          (coastal.CATALOGUE, "2026-09-16T12:00:00+01:00")]:
        seed.write_text(json.dumps({"source": source, "fetched_at": stamp, "items": [SITE]}))
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
            snapshot = coastal.fetch(NOW, client)
        assert snapshot["status"] == "unavailable" and snapshot["sites"] == []


# ------------------------------------------------------------------------------ dated samples
POINT = "NE-49100178"
OBS = [  # archive JSON-LD, as ingest.wqa._observations returns it (times local, as published)
    {"hasSamplingPoint": {"notation": POINT}, "phenomenonTime": "2026-09-08T11:16:00", "hasSimpleResult": "45", "det": "2348"},
    {"hasSamplingPoint": {"notation": POINT}, "phenomenonTime": "2026-09-08T11:16:00", "hasSimpleResult": "18", "det": "3723"},
    {"hasSamplingPoint": {"notation": POINT}, "phenomenonTime": "2026-09-11T10:53:00", "hasSimpleResult": "<10", "det": "2348"},
    {"hasSamplingPoint": {"notation": POINT}, "phenomenonTime": "2026-09-13T09:00:00", "hasSimpleResult": "30", "det": "3723"},  # no E. coli
    {"hasSamplingPoint": {"notation": POINT}, "phenomenonTime": "nonsense", "hasSimpleResult": "999", "det": "2348"},
    {"hasSamplingPoint": {"notation": "OTHER"}, "phenomenonTime": "2026-09-14T09:00:00", "hasSimpleResult": "5", "det": "2348"},
]


def _observations(points, since, code, purposes, batch):
    assert purposes == "MS" and points == [POINT] and since == "2026-08-29T00:00:00" and batch == 25
    return [o for o in OBS if o["det"] == code]


def _points(tmp_path, extra=None):
    f = tmp_path / "points.json"
    f.write_text(json.dumps({"checked_at": "2026-10-03T22:00:00+01:00", "points": {KEY: {"point": POINT, "evidence": "label"}, **(extra or {})}}))
    return f


def test_latest_sample_pairs_both_results_from_one_visit_and_keeps_its_time():
    since = coastal.sample_window(datetime.fromisoformat("2026-10-03T22:00:00+01:00"))
    assert since.isoformat() == "2026-08-29"
    got = coastal.latest_samples({KEY: {"point": POINT}}, since, observations=_observations)
    # 11 Sep is the latest sample with E. coli; its enterococci were not in the archive, so None, not 8 Sep's.
    assert got == {KEY: {"taken_at": "2026-09-11T10:53:00+01:00", "ecoli": {"value": 10.0, "qualifier": "<"},
                         "enterococci": None, "point": POINT}}
    assert coastal.sample_window(datetime.fromisoformat("2027-02-10T12:00:00+00:00")).isoformat() == "2026-08-01"
    assert coastal.sample_window(datetime.fromisoformat("2026-12-10T12:00:00+00:00")).isoformat() == "2026-08-01"


def test_sample_states_are_explicit_and_a_failed_archive_never_reads_as_none(tmp_path):
    now = datetime.fromisoformat("2026-10-03T22:00:00+01:00")
    other = "ukc2102-03700"
    snapshot = {"sites": [{"id": KEY}, {"id": other}, {"id": "ukc2102-03800"}], "fetched_at": now.isoformat()}
    found = {KEY: {"taken_at": "2026-09-11T10:53:00+01:00", "ecoli": {"value": 45.0, "qualifier": "="},
                   "enterococci": {"value": 18.0, "qualifier": "="}, "point": POINT}}
    out = coastal.attach_samples(snapshot, now, _points(tmp_path, {other: {"point": "X-1"}}), fetch=lambda p, s: found)
    states = [s["sample"]["state"] for s in out["sites"]]
    assert states == ["ok", "none", "unmapped"]
    assert out["samples"]["state"] == "ok" and out["samples"]["since"] == "2026-08-29"
    line = coastal.sample_line(out["sites"][0]["sample"], "2026-08-29")
    assert line == ('Latest archived EA sample <time datetime="2026-09-11T10:53:00+01:00">11 Sep 2026, 10:53</time>: '
                    'E. coli 45, intestinal enterococci 18 per 100 ml')
    assert coastal.sample_line({"state": "none"}, "2026-08-29").startswith("No EA sample in the archive since <time")

    def refused(points, since):
        raise httpx.HTTPStatusError("503", request=httpx.Request("GET", "https://x/"), response=httpx.Response(503))

    out = coastal.attach_samples({"sites": [{"id": KEY}]}, now, _points(tmp_path), fetch=refused)
    assert out["sites"][0]["sample"] == {"state": "unavailable"} and out["samples"]["error"] == "HTTP 503"
    assert "unavailable" in coastal.sample_line(out["sites"][0]["sample"], None)
    rendered = coastal.render({"sites": [{**coastal.parse([SITE], [], now)[0], "sample": {"state": "ok", **found[KEY]}}],
                               "fetched_at": now.isoformat(), "samples": {"state": "ok", "fetched_at": now.isoformat()}})
    assert "E. coli 45, intestinal enterococci 18 per 100 ml" in rendered and "not today" in rendered


def test_samples_are_asked_at_most_every_six_hours_and_a_dated_answer_outlasts_a_failure(tmp_path):
    now = datetime.fromisoformat("2026-10-03T22:00:00+01:00")
    cache, asked = tmp_path / "samples.json", []
    found = {KEY: {"taken_at": "2026-09-11T10:53:00+01:00", "ecoli": {"value": 45.0, "qualifier": "="}, "enterococci": None, "point": POINT}}

    def fetch(points, since):
        asked.append(since)
        return found

    def broken(points, since):
        raise httpx.ReadTimeout("slow")

    coastal.attach_samples({"sites": [{"id": KEY}]}, now, _points(tmp_path), cache=cache, fetch=fetch)
    later = coastal.attach_samples({"sites": [{"id": KEY}]}, now + timedelta(hours=5), _points(tmp_path), cache=cache, fetch=fetch)
    assert len(asked) == 1 and later["sites"][0]["sample"]["state"] == "ok"   # from the cache, with its own time
    assert later["samples"]["fetched_at"] == now.isoformat()
    stale = coastal.attach_samples({"sites": [{"id": KEY}]}, now + timedelta(days=2), _points(tmp_path), cache=cache, fetch=broken)
    assert stale["samples"]["state"] == "cached" and stale["sites"][0]["sample"]["state"] == "ok"
    gone = coastal.attach_samples({"sites": [{"id": KEY}]}, now + timedelta(days=4), _points(tmp_path), cache=cache, fetch=broken)
    assert gone["sites"][0]["sample"] == {"state": "unavailable"}   # over three days old: not shown
    missing = coastal.attach_samples({"sites": [{"id": KEY}]}, now, tmp_path / "absent.json", fetch=fetch)
    assert missing["sites"][0]["sample"] == {"state": "unmapped"} and len(asked) == 1


def test_an_archive_point_matches_only_its_own_bathing_water_number():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from map_coastal_wqa import labelled
    points = [{"notation": "NW-88009847", "prefLabel": "AINSDALE AT AINSDALESEFTON MBC (41300)"},
              {"notation": "NW-1", "prefLabel": "SOMEWHERE (141300)"},
              {"notation": "NW-2", "prefLabel": "PONTINS OUTFALL AT AINSDALE BEACH"},
              {"notation": "NW-3", "prefLabel": "AINSDALE (41300) INVESTIGATION"}]
    assert labelled(points, "41300") == ["NW-88009847"]
