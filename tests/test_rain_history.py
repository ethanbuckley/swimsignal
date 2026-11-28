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
    one = {**snap["sites"][1]["rain_history"], "first_year": 2026}
    assert rain_history.line(one).startswith("Past samples here by rain, 2026: ")   # one season, not "2026–2026"
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


def test_an_irish_card_carries_the_line(tmp_path):
    import importlib

    from dipcast import ireland
    t = importlib.import_module("test_ireland")
    snap = t.fetch(tmp_path / "c")
    first = snap["sites"][0]
    doc = {**DOC, "nations": {"ireland": {**DOC["nations"]["england"], "period": "May to September, 2014 to 2026",
                                          "tested": "Tested on Irish beaches."}},
           "sites": {first["id"]: {**DOC["sites"]["a"], "nation": "ireland", "first_year": 2014}}}
    f = tmp_path / "h.json"
    f.write_text(json.dumps(doc))
    assert rain_history.attach(snap, "england", f) == 0   # a nation the file does not hold adds nothing
    assert rain_history.attach(snap, "ireland", f) == 1
    html = ireland.render(snap)
    assert "Past samples here by rain, 2014–2026" in html and html.count("Past samples here by rain") == 1
    assert "Across Irish beaches (May to September, 2014 to 2026)" in html and "Tested on Irish beaches." in html
    assert "Contains Environment Agency data, OGL v3.0." in html   # the file's credit under the list
    assert "Rain here in the 2 days" not in html


def test_an_inland_water_counts_over_900_and_the_note_says_it_was_not_tested(tmp_path):
    """docs/INLAND-RAIN-HISTORY-2026-11.md: lakes and rivers count results over 900, the inland line, with no tested
    label."""
    lake = {"nation": "ireland", "first_year": 2014, "last_year": 2026, "samples": 183, "line": 900,
            "after_rain": {"samples": 38, "median": 96.0, "over_900": 6},
            "dry": {"samples": 54, "median": 30.0, "over_900": 0}}
    doc = {**DOC, "nations": {"ireland": {**DOC["nations"]["england"], "tested": "Tested on Irish beaches.",
                                          "inland": {"waters": 1, "samples": 183}}},
           "sites": {"lake": lake, "beach": {**DOC["sites"]["a"], "nation": "ireland"}}}
    f = tmp_path / "h.json"
    f.write_text(json.dumps(doc))
    snap = {"sites": [{"id": "lake"}, {"id": "beach"}]}
    assert rain_history.attach(snap, "ireland", f) == 2
    text = rain_history.line(snap["sites"][0]["rain_history"])
    assert "the middle of 38 read 96 (6 over 900)" in text and "the middle of 54 read 30 (none over 900)" in text
    assert "500" not in text
    assert "(3 over 500)" in rain_history.line(snap["sites"][1]["rain_history"])   # a beach keeps its line
    note = rain_history.note(snap)
    assert "count results over 900, the inland line, and they were not tested" in note


def test_the_committed_file_gives_inland_waters_900_and_leaves_beaches_at_500():
    doc = json.loads(rain_history.PATH.read_text())
    assert doc["version"].startswith("1.") and doc["version"] >= "1.2"
    inland = {k: v for k, v in doc["sites"].items() if v.get("line") == 900}
    assert inland and all(v["nation"] in ("ireland", "wales", "northern_ireland") for v in inland.values())
    for v in doc["sites"].values():
        for g in (v["after_rain"], v["dry"]):
            if "median" in g:
                assert (f'over_{v.get("line", 500)}' in g) and len([k for k in g if k.startswith("over_")]) == 1
    for n in ("ireland", "wales", "northern_ireland"):
        assert "share_over_900" in doc["nations"][n]["inland"]["after_rain"]
        assert "share_over_500" in doc["nations"][n]["after_rain"]   # the beaches' pooled figure stays coast only


def _cache(tmp_path, a, b, mm_per_hour, now, hours=48, issued="2026-11-28T06:00:00+00:00"):
    import pandas as pd
    noon = pd.Timestamp(now).tz_convert("Europe/London").normalize() + pd.Timedelta(hours=12)
    t = pd.date_range(noon - pd.Timedelta(hours=hours - 1), noon, freq="h").tz_convert("UTC")
    pd.DataFrame({"cell_lat": a, "cell_lon": b, "time": t, "precip_mm": mm_per_hour, "air_c": 8.0,
                  "issued_at": pd.Timestamp(issued)}).to_parquet(tmp_path / f"forecast_{a:.3f}_{b:.3f}.parquet")


def test_directory_cards_take_todays_rain_from_the_nearest_cached_cell(tmp_path):
    """docs/DIRECTORY-RAIN-NOW-2026-11.md: no request; the nearest fresh cell in the site's own square or the eight
    around it; only sites with past samples by rain; a window under 90% covered gives nothing."""
    import pandas as pd
    now = pd.Timestamp("2026-11-28T15:00:00+00:00")
    _cache(tmp_path, 52.1, -3.1, 0.25, now)            # the site's own square: 12 mm
    _cache(tmp_path, 51.9, -4.0, 0.0, now, hours=20)    # under 90% of the window
    _cache(tmp_path, 52.2, -3.2, 0.1, now, issued="2026-11-26T06:00:00+00:00")   # fetched 57 hours before: too old
    f = tmp_path / "h.json"
    f.write_text(json.dumps({**DOC, "nations": {"wales": DOC["nations"]["england"]},
                             "sites": {k: {**DOC["sites"]["a"], "nation": "wales"} for k in ("river", "short", "far")}}))
    snap = {"sites": [{"id": "river"}, {"id": "short"}, {"id": "far"}, {"id": "none"}]}
    rain_history.attach(snap, "wales", f)
    pts = {"river": [52.0765, -3.1371], "short": [51.8845, -3.986], "far": [52.19, -3.21], "none": [52.08, -3.14]}
    assert rain_history.attach_cached(snap, pts, tmp_path, now) == 2
    r = snap["sites"][0]["rain_now"]
    assert r["mm"] == 12.0 and r["date"] == "2026-11-28" and "km" not in r and r["fetched"] == "28 Nov 06:00"
    assert "rain_now" not in snap["sites"][1], "a window under 90% covered gives nothing"
    far = snap["sites"][2]["rain_now"]
    assert far["km"] >= 1, "a neighbouring square is named as a point away"
    assert "rain_now" not in snap["sites"][3], "no past samples by rain, no line"
    assert rain_history.now_line(snap["sites"][0]) == ("Rain here in the 2 days to midday on 2026-11-28: 12 mm "
                                                       "(forecast service, fetched 28 Nov 06:00). That is as wet as the after-rain samples above.")
    assert rain_history.now_line(snap["sites"][2]).startswith(f"Rain at a point {far['km']} km away in the 2 days")
