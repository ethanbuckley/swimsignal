from datetime import datetime
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
                          ("prfOriginType", "UNKNOWN"), ("riskLevel", "unrecognised")]:
        assert advice({**PRED, field: broken})["state"] == "no_current_advice"


def test_normal_non_forecast_records_and_conflicts_are_not_an_all_clear():
    normal = {**PRED, "riskLevel": "http://environment.data.gov.uk/def/bwq-stp/normal"}
    assert advice(normal)["state"] == "no_increased_risk"
    assert advice({**normal, "prfOriginType": "NON_PRF_SITE"})["state"] == "no_forecast"
    assert advice(PRED, normal)["state"] == "unavailable"
    assert advice()["state"] == "no_current_advice"


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


def test_invalid_or_future_catalogue_fallback_is_not_published(tmp_path, monkeypatch):
    seed = tmp_path / "catalogue.json"
    monkeypatch.setattr(coastal, "FALLBACK", seed)
    for source, stamp in [("https://other.invalid/", "2026-09-14T12:00:00+01:00"),
                          (coastal.CATALOGUE, "2026-09-16T12:00:00+01:00")]:
        seed.write_text(json.dumps({"source": source, "fetched_at": stamp, "items": [SITE]}))
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
            snapshot = coastal.fetch(NOW, client)
        assert snapshot["status"] == "unavailable" and snapshot["sites"] == []
