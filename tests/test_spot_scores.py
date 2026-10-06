"""How the forecast has done here (src/dipcast/spot_scores.py): each spot's counts are the plain sums of
its upstream overflows' rows in the published scored CSV, under the Accuracy page's warning line, so that
they reconcile with verification.json's warning table. The page's words are tested in
tests/site_spotscores.test.cjs."""

import json
import sys
from pathlib import Path

import pandas as pd

from dipcast import forecast_log as fl
from dipcast import spot_scores

ROOT = Path(__file__).resolve().parents[1]


def _rows() -> pd.DataFrame:
    """Three overflows over two days at five leads: A spills on day 1 (warned at two leads), B never spills
    (one warning), C spills on day 2 (never warned). D has rows but is upstream of no spot."""
    out = []
    for oid, spill_day, warned in (("A", "2026-09-29", {(0, "2026-09-29"), (1, "2026-09-29")}),
                                   ("B", None, {(2, "2026-09-30")}), ("C", "2026-09-30", set()), ("D", "2026-09-29", set())):
        for day in ("2026-09-29", "2026-09-30"):
            for lead in range(5):
                out.append({"overflow_id": oid, "company": "X", "day": day, "lead": lead, "issued_at": "2026-09-28T07:00+01:00",
                            "forecast_raw": 0.1, "forecast_calibrated": 0.5 if (lead, day) in warned else 0.05,
                            "climatology": 0.02, "observed": int(day == spill_day)})
    return pd.DataFrame(out)


def test_counts_are_the_csv_rows_of_the_spot_overflows():
    up = {"two": [{"site_id": "A"}, {"site_id": "B"}], "three": [{"site_id": "A"}, {"site_id": "B"}, {"site_id": "C"}, {"site_id": "Z"}],
          "dup": [{"site_id": "C"}, {"site_id": "C"}], "none": [], "bad id!": [{"site_id": "A"}]}
    got = spot_scores.summarise(_rows(), up)
    assert got["warn_at"] == fl.SPILL_WARN_AT and got["min_spills"] == 10
    assert set(got["spots"]) == {"two", "three", "dup"}        # nothing upstream, or an id that cannot be a page: left out
    two = got["spots"]["two"]
    assert (two["overflows"], two["scored_overflows"], two["overflow_days"], two["spill_days"]) == (2, 2, 4, 1)
    assert (two["forecasts"], two["hits"], two["misses"], two["false_alarms"]) == (20, 2, 3, 1)
    three = got["spots"]["three"]
    assert (three["overflows"], three["scored_overflows"]) == (4, 3)   # Z has no scored row: counted, not scored
    assert (three["spill_days"], three["hits"], three["misses"], three["false_alarms"]) == (2, 2, 8, 1)
    assert (three["days"], three["first_day"], three["last_day"]) == (2, "2026-09-29", "2026-09-30")
    assert got["spots"]["dup"]["overflows"] == 1                # a duplicated overflow is counted once
    assert got["spots"]["dup"]["forecasts"] == 10


def test_all_rows_equal_the_accuracy_page_warning_table():
    """The same rows through the scorer's own table (forecast_log.spill_warning_table) give the same counts."""
    rows = _rows()
    fc = rows.rename(columns={"overflow_id": "site_id", "day": "target_day", "observed": "y", "forecast_calibrated": "p_cal"})
    w = fl.spill_warning_table(fc)
    a = spot_scores.summarise(rows, {})["all"]
    assert (a["forecasts"], a["hits"], a["misses"], a["false_alarms"]) == (w["n"], w["hits"], w["misses"], w["false_alarms"])
    assert (a["overflow_days"], a["spill_days"], a["days"]) == (w["n_overflow_days"], w["n_spill_overflow_days"], w["n_days"])


def test_none_scored_and_no_rows():
    got = spot_scores.summarise(_rows().iloc[0:0], {"s": [{"site_id": "A"}]})["spots"]["s"]
    assert (got["overflows"], got["scored_overflows"], got["overflow_days"], got["spill_days"], got["forecasts"]) == (1, 0, 0, 0, 0)
    assert got["first_day"] is None


def test_write_reads_the_published_csv_or_removes_the_file(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    dst = data / spot_scores.FILE
    dst.write_text("{}")
    assert spot_scores.write(tmp_path, {"two": [{"site_id": "A"}]}, pd.Timestamp("2026-10-06T08:00+01:00"), {"x": 1}) is None
    assert not dst.exists()                                     # no scored rows published: no file, so no tile
    (data / "verification_live.csv").write_text("# credits line\n# another\n" + _rows().to_csv(index=False))
    assert spot_scores.write(tmp_path, {"two": [{"site_id": "A"}, {"site_id": "B"}]}, pd.Timestamp("2026-10-06T08:00+01:00"), {"x": 1}) == 1
    out = json.loads(dst.read_text())
    assert out["spots"]["two"]["hits"] == 2 and out["credits"] == {"x": 1} and out["generated_at"].startswith("2026-10-06T08:00")


def test_the_page_loads_the_script_from_its_build_and_data_html_describes_the_file(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site as bs
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / spot_scores.FILE).write_text("{}")
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    page = (tmp_path / "index.html").read_text()
    assert f'<script src="spotscores.js?v={stamp}">' in page
    assert page.index('src="evidence.js') < page.index('src="spotscores.js') < page.index("<script>\n")
    assert (tmp_path / "spotscores.js").read_bytes() == (bs.TEMPLATE.parent / "spotscores.js").read_bytes()
    assert "`spotscores.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert 'data-file="spot_scores.json"' in (tmp_path / "data.html").read_text()
    assert "Not described here yet" not in (tmp_path / "data.html").read_text()
