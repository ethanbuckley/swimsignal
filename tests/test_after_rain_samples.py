"""Past samples after rain (docs/AFTER-RAIN-SAMPLES-2026-11.md): the export's split at 10 mm, its minimum group, the
middle result by the past-samples tile's own rule, the build's rule for where it goes, and the committed file."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as bs  # noqa: E402
import export_after_rain_samples as ex  # noqa: E402


def _s(t, e, q=None):
    return {"t": t, "ecoli": e, "q": q}


def test_split_at_ten_mm_with_the_tiles_middle_rule():
    samples = [_s(f"2024-06-{d:02d}T12:00+01:00", e, q) for d, e, q in
               [(1, 10, "<"), (2, 40, None), (3, 90, None), (4, 300, None), (5, 900, None), (6, 1200, None),
                (7, 18, None), (8, 27, None), (9, 36, None), (10, 45, None), (11, 55, None), (12, 64, None)]]
    rain = {ex._minute(s["t"]): (25.0 if i < 6 else 3.0) for i, s in enumerate(samples)}
    rain[ex._minute(samples[-1]["t"])] = 10.0   # exactly 10 mm is "less", not more
    got = ex.split(samples, rain)
    assert got["after_rain"] == {"samples": 6, "median": 90}   # ranks: <10, 40, 90 | 300, ...: the lower middle
    assert got["after_less"] == {"samples": 6, "median": 36}
    assert got["without_rain_figure"] == 0 and (got["first_year"], got["last_year"]) == (2024, 2024)


def test_too_few_in_either_group_gives_no_entry_and_a_missing_rain_figure_is_counted():
    samples = [_s(f"2024-06-{d:02d}T12:00+01:00", 50) for d in range(1, 12)]
    rain = {ex._minute(s["t"]): (20.0 if i < 4 else 1.0) for i, s in enumerate(samples)}
    assert ex.split(samples, rain) is None                                   # 4 after rain < MIN_GROUP
    rain = {ex._minute(s["t"]): (20.0 if i < 5 else 1.0) for i, s in enumerate(samples[:-1])}
    got = ex.split(samples, rain)
    assert got["without_rain_figure"] == 1 and got["after_rain"]["samples"] == 5 and got["after_less"]["samples"] == 5


def _spot(i, overflows=0, error=None, days=True, typical=True):
    return {"id": i, "upstream_summary": {"overflows": overflows}, "error": error,
            "days": [{"date": "2026-07-04"}] if days else [], **({"ecoli_typical": {"samples": 80}} if typical else {})}


def test_the_build_attaches_it_only_where_the_page_shows_past_samples_with_daily_rows(tmp_path):
    f = tmp_path / "a.json"
    entry = {"after_rain": {"samples": 12, "median": 190}, "after_less": {"samples": 67, "median": 130},
             "first_year": 2023, "last_year": 2026}
    f.write_text(json.dumps({"schema": "swimsignal.after-rain-samples", "version": "1.0.0", "line_mm": 10,
                             "sites": {k: entry for k in "abcde"}}))
    rs = [_spot("a"), _spot("b", overflows=3), _spot("c", error="An isolated lake: ...", days=False),
          _spot("d", typical=False), _spot("e", days=False), _spot("z")]
    assert bs.attach_after_rain(rs, f) == 1
    assert rs[0]["ecoli_after_rain"] == {"line_mm": 10, **entry}
    assert all("ecoli_after_rain" not in r for r in rs[1:])
    f.write_text(json.dumps({"schema": "swimsignal.after-rain-samples", "version": "2.0.0", "sites": {}}))
    assert bs.attach_after_rain(rs, f) is None
    assert bs.attach_after_rain(rs, tmp_path / "missing.json") is None


def test_the_committed_file_holds_no_rain_value_and_the_five_lakes():
    doc = json.loads(ex.DEST.read_text())
    assert doc["schema"] == ex.SCHEMA and doc["line_mm"] == 10 and doc["min_group"] == 5
    assert doc["rain_from"]["rows_sha256"] == ex.SEEN_SHA256
    for v in doc["sites"].values():
        assert set(v) == {"bw_id", "name", "kind", "after_rain", "after_less", "without_rain_figure", "first_year",
                          "last_year"}
    s = doc["sites"]
    assert s["bw-uki1106-11940"]["after_rain"] == {"samples": 12, "median": 190}
    assert s["bw-uki1106-11940"]["after_less"] == {"samples": 67, "median": 130}
    for k in ("bw-uki1101-11910", "bw-uki1101-11920", "bw-uki1101-11930", "bw-ukf1400-09750"):
        assert k in s
