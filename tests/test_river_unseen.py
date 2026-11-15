"""Stage 1 of RIVER-UNSEEN (docs/RIVER-UNSEEN-PROTOCOL-2026-11.md, scripts/river_unseen/): which rows and points are
kept, the name rule, the kill rule's two figures, the fetch's row count and the frozen candidate."""

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "river_unseen"))
import fetch
import freeze_candidate
import stage


def _rows(n, point="P1", year=2015, month="07", purpose="PLANNED INVESTIGATION (LOCAL MONITORING)",
          material="RIVER / RUNNING SURFACE WATER"):
    return pd.DataFrame({"id": [f"{point}-{year}-{month}-{i}" for i in range(n)], "point": point,
                         "label": "R TAW AT UMBERLEIGH", "easting": "260800", "northing": "123700", "region": "SW",
                         "area": "DEVON", "status": "OPEN", "time": f"{year}-{month}-15T10:00:00", "purpose": purpose,
                         "material": material, "result": "sealed", "unit": "no/100ml"})


def test_a_row_is_kept_by_material_season_and_purpose():
    r = stage.mark(pd.concat([
        _rows(1), _rows(1, month="11"), _rows(1, material="SEA WATER"),
        _rows(1, purpose="UNPLANNED REACTIVE MONITORING (POLLUTION INCIDENTS)"),
        _rows(1, purpose="MONITORING  (UK GOVT POLICY - NOT GQA OR RE)"),   # the archive writes two spaces
        _rows(1, purpose="STATUTORY FAILURES (FOLLOW UPS AT NON-DESIGNATED POINTS)"),
        _rows(1, year=2024)], ignore_index=True))
    assert r["kept"].tolist() == [True, False, False, False, True, False, True]
    assert r["span"].tolist() == ["held_out"] * 6 + ["development"]
    assert r["purpose_code"].tolist()[4] == "MU"


def test_the_count_rule_needs_30_rows_in_three_seasons():
    two = pd.concat([_rows(20, "A", 2014), _rows(20, "A", 2015)])
    three = pd.concat([_rows(10, "B", y) for y in (2013, 2014, 2015)])
    late = pd.concat([_rows(15, "C", y) for y in (2021, 2022, 2023, 2024)])   # only 30 of its 60 are held out, in 2 seasons
    t = stage.point_table(stage.mark(pd.concat([two, three, late], ignore_index=True))).set_index("point")
    assert t["rule1_count"].to_dict() == {"A": False, "B": True, "C": False}
    assert t.loc["C", ["kept_held_out", "seasons_held_out", "kept_development"]].tolist() == [30, 2, 30]


def test_the_name_rule():
    assert stage.right_river("River Taw", "R TAW AT UMBERLEIGH")
    assert stage.right_river("Afon Gwy", "Gwy at Hay")
    assert not stage.right_river("River Mole", "R TAW AT JUNCTION POOL")
    assert stage.right_river(None, "UNNAMED STREAM AT X") and stage.right_river("", "X")


def test_the_kill_rule_counts_points_and_rows_with_no_overflow_upstream():
    def table(n_with, n_without):
        rows = [{"rule1_count": True, "rule2_on_river": True, "rule3_right_river": True, "rule5_not_bench": True,
                 "rule4_overflow_upstream": i < n_with, "kept_held_out": 40, "kept_development": 5}
                for i in range(n_with + n_without)]
        return pd.DataFrame(rows)
    k = stage.kill_rule(table(30, 30))
    assert (k["points_passing_all_five"], k["share_no_overflow_upstream"], k["killed"]) == (30, 0.5, False)
    assert stage.kill_rule(table(29, 10))["killed"]            # fewer than 30 points
    assert stage.kill_rule(table(30, 31))["killed"]            # more than half the rows with no overflow upstream
    off = table(40, 0).assign(rule2_on_river=False)
    assert stage.kill_rule(off)["killed"] and stage.kill_rule(off)["share_no_overflow_upstream"] is None


def test_pages_are_read_once_per_id_and_results_stay_text(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    cols = {v: k for k, v in stage.COLUMNS.items()}
    a = _rows(3).rename(columns=cols).assign(extra="x")
    a.to_csv(raw / "ecoli_F6_2015_s000000.csv", index=False)
    a.iloc[:1].to_csv(raw / "ecoli_F6_2015_s002500.csv", index=False)
    (raw / "ecoli_F6_2011_s000000.csv").write_bytes(b"")           # an empty year (HTTP 204)
    rows, checks = stage.load_pages(raw)
    assert checks == {"pages": 2, "rows_fetched": 4, "repeated_ids": 1, "rows": 3, "rows_sharing_point_and_time": 3}
    assert rows["result"].tolist() == ["sealed"] * 3


def test_the_fetch_counts_rows_not_lines():
    assert fetch.rows_in(b"") == 0
    assert fetch.rows_in(b'id,label\nhttp://a,"two\nlines"\nhttp://b,x\n') == 2
    assert fetch.CAP_REQUESTS == 150 and fetch.PAGE == 2500
    assert list(fetch.HELD_OUT)[0] == 2022 and list(fetch.HELD_OUT)[-1] == 2012


def test_the_frozen_candidate_is_the_one_the_statement_names():
    f = ROOT / "docs" / "river-unseen" / "river_range_v0.json"
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    assert sha.startswith("bb4d8c10") and sha[:8] in (ROOT / "docs" / "RIVER-UNSEEN-PROTOCOL-2026-11.md").read_text()
    m = json.loads(f.read_text())
    assert list(m["coef"]) == freeze_candidate.FEATURES and m["fitted_on"]["rows"] == 943
    rows = pd.DataFrame({k: [0.0, 1.0] for k in freeze_candidate.FEATURES})
    p = freeze_candidate.predict(m, rows)
    assert abs(p["mu_log10"][0] - m["intercept"]) < 1e-12
    assert abs((p["high_log10"][0] - p["mu_log10"][0]) - 1.2815515655446004 * m["sd_log10"]) < 1e-9
