"""The coverage page's "past samples here by rain" line (dipcast.rain_history)."""

import json

from dipcast import coastal, rain_history

DOC = {"schema": "swimsignal.coastal-rain-history", "version": "1.1.0",
       "rule": {"hours": 48, "after_rain_mm": 10, "dry_mm": 1, "min_group": 10},
       "nations": {"england": {"period": "May to September, 2012 to 2026", "beaches": 3, "samples": 362,
                               "after_rain": {"samples": 9000, "median": 45.0, "over_500": 400, "share_over_500": 0.0444},
                               "dry": {"samples": 30000, "median": "<10", "over_500": 150, "share_over_500": 0.005},
                               "tested": "Tested on unseen seasons."}},
       "credit": "Contains Environment Agency data, OGL v3.0.",
       "sites": {"a": {"nation": "england", "first_year": 2012, "last_year": 2026, "samples": 300,
                       "after_rain": {"samples": 40, "median": 120.0, "over_500": 3},
                       "dry": {"samples": 150, "median": "<10", "over_500": 0}},
                 "b": {"first_year": 2015, "last_year": 2026, "samples": 50,
                       "after_rain": {"samples": 4}, "dry": {"samples": 30, "median": 18.0, "over_500": 1}},
                 "c": {"first_year": 2015, "last_year": 2026, "samples": 12,
                       "after_rain": {"samples": 2}, "dry": {"samples": 5}}}}


def test_attach_and_line(tmp_path):
    f = tmp_path / "h.json"
    f.write_text(json.dumps(DOC))
    snap = {"sites": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "z"}]}
    assert rain_history.attach(snap, "england", f) == 3
    a = rain_history.line(snap["sites"][0]["rain_history"], snap["rain_history"]["rule"])
    assert a == ("Past samples here by rain, 2012–2026: after 10 mm or more of rain in the 2 days before, the middle of "
                 "40 read 120 (3 over 500); after 2 dry days (under 1 mm), the middle of 150 read under 10 (none "
                 "over 500). E. coli per 100 ml. Not a forecast")
    b = rain_history.line(snap["sites"][1]["rain_history"])
    assert "after 10 mm" not in b and "the middle of 30 read 18 (1 over 500)" in b
    assert rain_history.line(snap["sites"][2]["rain_history"]) is None
    note = rain_history.note(snap)
    assert "Across English beaches (May to September, 2012 to 2026), 4.4% of samples taken after 10 mm or more of rain in 2 days were over 500, against 0.5% after 2 dry days." in note
    assert "Tested on unseen seasons." in note
    assert "not a forecast" in note


def test_wrong_schema_adds_nothing(tmp_path):
    f = tmp_path / "h.json"
    f.write_text(json.dumps({**DOC, "version": "2.0.0"}))
    snap = {"sites": [{"id": "a"}]}
    assert rain_history.attach(snap, "england", f) == 0 and "rain_history" not in snap["sites"][0]


def test_card_carries_the_line(tmp_path):
    f = tmp_path / "h.json"
    f.write_text(json.dumps(DOC))
    snap = {"fetched_at": "2026-11-25T10:00:00+00:00",
            "sites": [{"id": "a", "name": "Beach A", "kind": "coast", "rating": None, "profile": "https://x/a",
                       "advice": {"state": "no_forecast"}}]}
    rain_history.attach(snap, "england", f)
    html = coastal.render(snap)
    assert "Past samples here by rain, 2012–2026" in html
    assert "OGL v3.0" in html


def test_rain_now_from_the_click_anywhere_squares(tmp_path):
    f = tmp_path / "h.json"
    f.write_text(json.dumps(DOC))
    snap = {"sites": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
    rain_history.attach(snap, "england", f)
    days = {"days": ["2026-11-24", "2026-11-25", "2026-11-26"], "today": 1,
            "rain_48h": {"54.7,-1.2": [14.2, 3.0], "50.1,-5.5": [0.4, 0.0]}}
    pts = {"a": [54.66467, -1.18604], "b": [50.11, -5.52], "c": [52.0, 1.0]}
    assert rain_history.attach_live(snap, days, pts) == 2
    a = rain_history.now_line(snap["sites"][0], snap["rain_history"]["rule"])
    assert a == ("Rain here in the 2 days to midday on 2026-11-25: 14.2 mm (forecast service, this build). "
                 "That is as wet as the after-rain samples above.")
    assert "as dry as the dry-day samples" in rain_history.now_line(snap["sites"][1])
    assert rain_history.now_line(snap["sites"][2]) is None
