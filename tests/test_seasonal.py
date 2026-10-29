"""Past spills upstream by month (src/dipcast/seasonal.py) on synthetic histories, and the committed table's
size. The page's words are tested in tests/site_seasonal.test.cjs."""

import datetime as dt
import json
from pathlib import Path

from dipcast import config, seasonal

D = dt.date


def test_covered_years_needs_a_record_and_a_working_monitor():
    rows = [("A", "Thames Water", 2024, 99.0), ("A", "Thames Water", 2023, 99.0),   # no Thames record before 2024
            ("B", "Wessex Water", 2022, 95.0), ("C", "Wessex Water", 2022, 89.9),      # C's monitor worked < 90%
            ("D", "Yorkshire Water", 2025, None), ("E", "Yorkshire Water", 2025, float("nan")),
            (None, "Anglian Water", 2024, 100.0), ("F", "Unknown Water", 2024, 100.0)]
    assert seasonal.covered_years(rows) == {("A", 2024), ("B", 2022)}
    drop_b = lambda sid, company, year: sid != "B"  # noqa: E731
    assert seasonal.covered_years(rows, keep=drop_b) == {("A", 2024)}


def test_counts_any_overflow_once_per_day_by_month_with_leap_february():
    spills = {"A": {D(2024, 2, 29), D(2024, 7, 1), D(2025, 7, 1)}, "B": {D(2024, 7, 1), D(2024, 7, 2)}}
    cov = {(i, y) for i in "AB" for y in (2024, 2025)}
    e = seasonal.spot_history(["B", "A"], spills, cov, years=(2024, 2025))
    assert e["overflows"] == 2 and e["fp"] == seasonal.fingerprint(["A", "B"])
    assert e["years"]["2024"]["spill"][1] == 1 and e["years"]["2024"]["spill"][6] == 2   # 1 Jul counted once
    assert e["years"]["2025"]["spill"][6] == 1
    s = seasonal.summary(e)
    assert s["days"][1] == 29 + 28 and s["days"][6] == 62    # leap February counted from the calendar
    assert s["spill"][6] == 3 and s["years"] == [2024, 2025] and s["covered_min"] == 2


def test_coverage_gaps_drop_a_year_and_say_how_many_were_covered():
    ids = [f"S{i}" for i in range(10)]
    cov = {(i, 2025) for i in ids} | {(i, 2024) for i in ids[:8]} | {(i, 2023) for i in ids[:7]}
    spills = {"S9": {D(2023, 6, 1), D(2024, 6, 1)}, "S0": {D(2024, 6, 2)}}
    e = seasonal.spot_history(ids, spills, cov, years=(2023, 2024, 2025), min_covered=0.8)
    assert list(e["years"]) == ["2024", "2025"] and e["short"] == {"2023": 7}
    assert e["years"]["2024"] == {"covered": 8, "spill": [0, 0, 0, 0, 0, 2 - 1, 0, 0, 0, 0, 0, 0]}   # S9 not covered in 2024
    assert seasonal.summary(e)["covered_min"] == 8


def test_partial_year_monitor_leaves_the_year_out():
    # A monitor that worked half of 2024 is not covered that year, so a one-overflow spot loses 2024.
    cov = seasonal.covered_years([("A", "Thames Water", 2024, 50.0), ("A", "Thames Water", 2025, 98.0)])
    e = seasonal.spot_history(["A"], {"A": {D(2024, 8, 1), D(2025, 8, 1)}}, cov, years=(2024, 2025))
    assert list(e["years"]) == ["2025"] and e["short"] == {"2024": 0}
    assert seasonal.summary(e)["days"][7] == 31


def test_nothing_upstream_and_nothing_covered():
    e = seasonal.spot_history([], {}, set())
    assert e["overflows"] == 0 and e["years"] == {} and seasonal.summary(e) is None
    e = seasonal.spot_history(["A"], {"A": {D(2024, 1, 1)}}, set(), years=(2024,))
    assert e["years"] == {} and e["short"] == {"2024": 0} and seasonal.summary(e) is None


def _table(tmp_path, spots):
    p = tmp_path / "seasonal_spills.json"
    p.write_text(json.dumps({"made": "2026-10-27", "spots": spots}))
    return p


def test_attach_only_on_the_same_overflows(tmp_path):
    cov = {("A", 2025), ("B", 2025)}
    entry = seasonal.spot_history(["A", "B"], {"A": {D(2025, 5, 3)}}, cov, years=(2025,))
    thin = seasonal.spot_history(["C"], {}, set(), years=(2025,))
    p = _table(tmp_path, {"same": entry, "moved": entry, "thin": thin})
    results = [{"id": "same"}, {"id": "moved"}, {"id": "thin"}, {"id": "dry"}, {"id": "new"}, {"id": "bad", "error": "forecast failed"}]
    upstream = {"same": [{"site_id": "B"}, {"site_id": "A"}], "moved": [{"site_id": "A"}], "thin": [{"site_id": "C"}],
                "dry": [], "new": [{"site_id": "Z"}], "bad": [{"site_id": "A"}]}
    h = seasonal.attach(results, upstream, p)
    by = {r["id"]: r.get("seasonal") for r in results}
    assert by["same"]["spill"][4] == 1 and by["same"]["years"] == [2025] and by["same"]["made"] == "2026-10-27"
    assert by["moved"] is None and by["new"] is None and by["bad"] is None
    assert by["dry"] == {"none": True}
    assert by["thin"] == {"too_few": True, "overflows": 1}
    assert (h["shown"], h["none"], h["too_few"], h["missing"], h["changed"]) == (1, 1, 1, 1, 1)
    assert "moved" in h["warnings"][0]


def test_attach_never_stops_the_build(tmp_path):
    results = [{"id": "a"}]
    h = seasonal.attach(results, {"a": [{"site_id": "A"}]}, tmp_path / "missing.json")
    assert h["shown"] == 0 and "not shown" in h["warnings"][0] and "seasonal" not in results[0]


def test_committed_table_is_small_and_well_formed():
    p = config.RAW / "seasonal_spills.json"
    body = p.read_bytes()
    assert len(body) <= seasonal.FILE_BYTES_LIMIT, len(body)
    t = json.loads(body)
    assert t["years"] == list(seasonal.YEARS) and t["min_covered"] == seasonal.MIN_COVERED
    for sid, e in t["spots"].items():
        assert set(e) == {"fp", "overflows", "years", "short"}, sid
        for y, v in e["years"].items():
            md = seasonal.month_days(int(y))
            assert len(v["spill"]) == 12 and all(0 <= k <= n for k, n in zip(v["spill"], md)), (sid, y)
            assert v["covered"] >= seasonal.MIN_COVERED * e["overflows"], (sid, y)
    # Southern's and Yorkshire's own event files carry no licence: the sources name neither.
    assert not any("Southern" in s or "Yorkshire" in s for s in t["sources"].values())


def test_the_build_puts_it_in_the_spot_file_only():
    src = (Path(__file__).parents[1] / "scripts" / "build_site.py").read_text()
    fields = src.split("DETAIL_FIELDS = ", 1)[1].split(")", 1)[0]   # the tuple, whatever follows "seasonal" in it
    assert '"seasonal"' in fields
    assert "seasonal.attach(results, upstream, SEASONAL)" in src
