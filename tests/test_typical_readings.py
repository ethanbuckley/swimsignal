"""Past samples' typical readings (src/dipcast/typical.py): inland on spots (build_site.attach_typical_readings) and on
the directories' cards on the coverage page (typical.attach, typical.line)."""

import json

from dipcast import coastal, typical
from dipcast.typical import MIN_SAMPLES, typical_readings


def _s(values, year=2025):
    out = []
    for i, v in enumerate(values):
        q = v[0] if isinstance(v, str) else None
        out.append({"t": f"{year + i % 2}-06-{1 + i % 28:02d}T11:00:00+01:00", "ecoli": float(v[1:]) if q else v, "q": q})
    return out


def test_middle_and_8_in_10_by_rank_with_lab_limits_kept():
    t = typical_readings(_s(["<10"] * 5 + [12, 20, 31, 45, 64, 82, 110, 140, 180, 230, 350, 520, 930, 1400, ">10000"]), 900)
    assert t["samples"] == 20 and (t["first_year"], t["last_year"]) == (2025, 2026)
    assert t["low"] == "<10"                       # the 2nd of 20 is a "<10": it stays a limit, not 10
    assert t["median"] == 64 and t["high"] == 930  # 10th and 18th of 20 by rank, two significant figures
    assert t["line"] == 900 and t["over_line"] == 3   # 930, 1,400 and ">10000"; a "<" never counts


def test_too_few_samples_give_nothing():
    assert typical_readings(_s([50] * (MIN_SAMPLES - 1)), 500) is None
    assert typical_readings([], 500) is None


def test_two_significant_figures():
    t = typical_readings(_s([1234] * 20), 500)
    assert t["median"] == 1200 and t["over_line"] == 20


def test_directory_cards_carry_their_past_samples(tmp_path):
    f = tmp_path / "typical_england_coast.v1.json"
    t = {"samples": 61, "first_year": 2023, "last_year": 2026, "low": "<10", "median": 27, "high": 300, "line": 500,
         "over_line": 2, "months": "May–September"}
    f.write_text(json.dumps({"schema": typical.SCHEMA, "version": "1.0.0", "period": "May to September, 2023 to 2026",
                             "credit": "Contains Environment Agency data.", "sites": {"ukk4100-12345": t}}))
    snap = {"sites": [{"id": "ukk4100-12345"}, {"id": "ukk4100-99999"}]}
    assert coastal.attach_typical(snap, f) == 1
    assert snap["sites"][0]["typical"] == t and "typical" not in snap["sites"][1]
    assert typical.line(t) == ("Past samples, May–September 2023–2026: the middle of 61 read 27 E. coli per 100 ml, the "
                               "middle 8 in 10 between under 10 and 300; 2 over 500. Not a forecast")
    assert "between" not in typical.line({**t, "high": "<10", "median": "<10", "over_line": 0})   # one end, said once
    assert "May to September, 2023 to 2026" in typical.note(snap) and "Contains Environment Agency data." in typical.note(snap)
    f.write_text(json.dumps({"schema": "something else", "version": "1.0.0", "sites": {"ukk4100-12345": t}}))
    snap = {"sites": [{"id": "ukk4100-12345"}]}
    assert coastal.attach_typical(snap, f) == 0 and "typical" not in snap["sites"][0] and typical.note(snap) == ""


def test_the_committed_files_hold_the_contract():
    for name, path in typical.FILES.items():
        d = json.loads(path.read_text())
        assert d["schema"] == typical.SCHEMA and d["version"].split(".")[0] == typical.MAJOR, name
        assert d["credit"] and d["licence"] and d["period"] and d["sites"], name
        for t in d["sites"].values():
            assert t["samples"] >= MIN_SAMPLES and t["line"] in (500, 900) and 2023 <= t["first_year"] <= t["last_year"] <= 2026


def test_daera_results_tables_by_heading_and_name():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from export_typical_readings import daera_site, parse_daera
    page = ("<h1>Bathing Water Data 2025</h1><p>Results ...</p><h2 id='toc-1'>Murlough (Co Down)</h2><table><tr><th>Date</th>"
            "<th>Escherichia Coli (cfu/100ml)</th><th>IE</th></tr><tr><td>28/05/2025</td><td>10</td><td>10</td></tr>"
            "<tr><td>02/06/2025</td><td>190</td><td>24</td></tr></table><h2>Rea&#039;s Wood* (Candidate)</h2><table>"
            "<tr><td>03/06/2025</td><td>45</td><td>10</td></tr></table>")
    d = parse_daera(page)
    assert d == {"Murlough (Co Down)": [("2025-05-28", "10"), ("2025-06-02", "190")], "Rea's Wood* (Candidate)": [("2025-06-03", "45")]}
    by = {"murlough": "daera-30157", "reas wood": "daera-30203", "brompton bay": "daera-30202"}
    assert [daera_site(n, by) for n in ("Murlough (Co Down)", "Rea's Wood* (Candidate)", "Rea's Wood Inland Bathing Water *",
                                        "Brompton", "Nowhere")] == ["daera-30157", "daera-30203", "daera-30203", "daera-30202", None]
