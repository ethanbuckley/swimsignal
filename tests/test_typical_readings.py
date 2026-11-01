"""Past samples' typical readings (src/dipcast/typical.py): inland on spots (build_site.attach_typical_readings) and on
the coastal directory's cards (coastal.attach_typical, coastal.typical_line)."""

import json

from dipcast import coastal
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


def test_coastal_cards_carry_their_past_samples(tmp_path):
    f = tmp_path / "coastal_typical.v1.json"
    t = {"samples": 61, "first_year": 2023, "last_year": 2026, "low": "<10", "median": 27, "high": 300, "line": 500,
         "over_line": 2, "point": "SW-1"}
    f.write_text(json.dumps({"schema": coastal.TYPICAL_SCHEMA, "version": "1.0.0", "period": "May to September, 2023 to 2026",
                             "line": 500, "sites": {"ukk4100-12345": t}}))
    snap = {"sites": [{"id": "ukk4100-12345"}, {"id": "ukk4100-99999"}]}
    assert coastal.attach_typical(snap, f) == 1
    assert snap["sites"][0]["typical"] == t and "typical" not in snap["sites"][1]
    assert coastal.typical_line(t) == ("Past EA samples, May–September 2023–2026: the middle of 61 read 27 E. coli per "
                                       "100 ml, the middle 8 in 10 under 10 to 300; 2 over 500. Not a forecast")
    f.write_text(json.dumps({"schema": "something else", "version": "1.0.0", "sites": {"ukk4100-12345": t}}))
    snap = {"sites": [{"id": "ukk4100-12345"}]}
    assert coastal.attach_typical(snap, f) == 0 and "typical" not in snap["sites"][0]
