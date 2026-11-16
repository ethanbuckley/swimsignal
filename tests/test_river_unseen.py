"""Stage 1 of RIVER-UNSEEN (docs/RIVER-UNSEEN-PROTOCOL-2026-11.md, scripts/river_unseen/): which rows and points are
kept, the name rule, the kill rule's two figures, the fetch's row count and the frozen candidate."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
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
    e = ROOT / "docs" / "river-unseen" / "river_range_v0e.json"   # the candidate after the rain match check failed
    esha = hashlib.sha256(e.read_bytes()).hexdigest()
    text = (ROOT / "docs" / "RIVER-UNSEEN-PROTOCOL-2026-11.md").read_text()
    assert esha.startswith("3c8bfe59") and esha[:8] in text
    em = json.loads(e.read_text())
    assert em["name"] == "river-range-v0e" and em["fitted_on"]["rows"] == 923 and list(em["coef"]) == freeze_candidate.FEATURES
    rows = pd.DataFrame({k: [0.0, 1.0] for k in freeze_candidate.FEATURES})
    p = freeze_candidate.predict(m, rows)
    assert abs(p["mu_log10"][0] - m["intercept"]) < 1e-12
    assert abs((p["high_log10"][0] - p["mu_log10"][0]) - 1.2815515655446004 * m["sd_log10"]) < 1e-9


def test_a_points_river_system_is_its_outlet_and_its_band_is_by_channel_length():
    import networkx as nx

    import systems
    g = nx.DiGraph([("a", "b"), ("b", "sea1"), ("c", "b"), ("x", "sea2"), ("b", "sea0")])   # b braids to two outlets
    assert systems.outlet(g, "a") == systems.outlet(g, "c") == "sea0" and systems.outlet(g, "x") == "sea2"
    assert systems.outlet(g, "sea1") == "sea1"
    assert [systems.band(v) for v in (0.0, 9.9, 10.0, 99.9, 100.0, 3863.4)] == ["small", "small", "medium", "medium",
                                                                               "large", "large"]


def test_the_committed_systems_and_cells_match_the_points_table():
    d = ROOT / "docs" / "river-unseen"
    p, s, c = (pd.read_csv(d / f) for f in ("points.csv", "systems.csv", "rain_cells.csv"))
    kept = s[s["kept_point"]]
    assert set(kept["point"]) == set(p[p["kept_point"]]["point"]) and len(kept) == 59
    assert kept["system"].nunique() == 33 and kept.groupby("system").size().max() == 11
    assert kept["band"].value_counts().to_dict() == {"medium": 29, "small": 20, "large": 10}
    assert kept.groupby("band")["kept_held_out"].sum().to_dict() == {"large": 1154, "medium": 3614, "small": 1554}
    assert len(c) == 85 and c["for"].str.contains("point").sum() == 41
    text = (ROOT / "docs" / "RIVER-UNSEEN-PROTOCOL-2026-11.md").read_text()
    assert "## Amendment 1" in text and text.index("## Staging result") < text.index("## Amendment 1")


def test_results_are_parsed_with_their_qualifier_and_repeats_keep_the_higher():
    import build_rows
    assert build_rows.parse_result("<10") == (10.0, "<") and build_rows.parse_result("> 20000") == (20000.0, ">")
    assert build_rows.parse_result("350") == (350.0, "=") and build_rows.parse_result("12.5") == (12.5, "=")
    v, q = build_rows.parse_result("not analysed")
    assert np.isnan(v) and q == ""
    s = pd.DataFrame({"point": ["A", "A", "A", "B", "B"], "time": ["t1", "t1", "t2", "t1", "t1"],
                      "ecoli": [100.0, 400.0, 5.0, 7.0, 7.0]})
    kept, audit = build_rows.one_per_point_and_time(s)
    assert sorted(kept["ecoli"]) == [5.0, 7.0, 400.0]
    assert audit == {"groups_equal": 1, "groups_unequal": 1, "rows_dropped": 2}


def test_point_samples_keeps_only_the_span_at_kept_points_in_local_time():
    import build_rows
    samples = stage.mark(pd.concat([_rows(2, "K", 2015), _rows(1, "K", 2024), _rows(2, "X", 2015)], ignore_index=True))
    samples["result"] = ["<10", "350", "9", "8", "7"]
    points = pd.DataFrame({"point": ["K", "X"], "kept_point": [True, False], "label": ["R K", "R X"],
                           "lat": [50.5, 51.0], "lon": [-4.0, -3.0]})
    systems = pd.DataFrame({"point": ["K"], "system": ["S01"], "band": ["small"]})
    out, audit = build_rows.point_samples(samples, points, systems, "held_out")
    assert out["bw_id"].tolist() == ["K"] and audit["rows"] == 2      # two rows share K's time: the higher is kept
    assert out["ecoli"].tolist() == [350.0] and audit["same_point_and_time"]["groups_unequal"] == 1
    assert str(out["sample_time"].iloc[0]) == "2015-07-15 10:00:00+01:00" and out["system"].iloc[0] == "S01"
    dev, _ = build_rows.point_samples(samples, points, systems, "development")
    assert dev["ecoli"].tolist() == [9.0]


def test_the_three_point_sets_do_not_overlap():
    import build_rows
    p = pd.read_csv(ROOT / "docs" / "river-unseen" / "points.csv")
    sets = {w: set(build_rows.which_points(p, w)["point"]) for w in ("kept", "sensitivity", "no_overflow")}
    assert (len(sets["kept"]), len(sets["sensitivity"]), len(sets["no_overflow"])) == (59, 8, 23)
    assert not (sets["kept"] & sets["sensitivity"]) and not (sets["kept"] & sets["no_overflow"])


def test_the_read_scores_order_within_a_point_and_the_range_at_lab_limits():
    import read
    d = pd.DataFrame({"log_ecoli": [1.0, 1.0, 4.0, 4.0, 2.0, 2.0], "ecoli_qual": ["<", "<", ">", ">", "=", "="],
                      "low_log10": [0.5, 1.5, 2.0, 2.0, 1.5, 2.5], "high_log10": [2.0, 3.0, 4.5, 3.5, 2.5, 3.0]})
    assert read.inside(d).tolist() == [True, False, True, False, True, False]
    assert read.outcome({"primary_pass": True, "range_pass": True}) == "both pass"
    assert read.outcome({"primary_pass": True, "range_pass": False}) == "order passes, range fails"
    assert read.outcome({"primary_pass": False, "range_pass": True}) == "order fails"
    rng = np.random.default_rng(0)
    n = 40
    rows = pd.concat([pd.DataFrame({"bw_id": f"P{i}", "system": f"S{i // 2}", "season": np.repeat([2014, 2015], n // 2),
                                    "x": rng.normal(size=n)}) for i in range(6)], ignore_index=True)
    rows["log_ecoli"] = rows["x"] + rng.normal(scale=1.0, size=len(rows))
    rows["noise"] = rng.normal(size=len(rows))
    assert read.rho_points(rows, "x") > 0.5 and abs(read.rho_points(rows, "noise")) < 0.2
    iv = read.interval(rows, lambda v: read.rho_points(v, "x"), lambda v: read.rho_points(v, "x", "_p"))
    assert iv["ci95"][0] < iv["value"] < iv["ci95"][1] and iv["ci95"][0] > read.RHO_BAR
    assert read.rho_points(rows.groupby("bw_id").head(10), "x") != read.rho_points(rows.groupby("bw_id").head(10), "x")  # nan: under 15 rows


def test_production_as_deployed_is_the_logistic_of_its_standardised_inputs():
    import read
    m = {"intercept": -2.0, "coef": {"lrain48": 0.5, "lake": 9.0}, "mean": {"lrain48": 1.0, "lake": 0.0},
         "scale": {"lrain48": 2.0, "lake": 1.0}}
    p = read.production_deployed(m, pd.DataFrame({"lrain48": [1.0, 5.0]}))
    assert abs(p[0] - 1 / (1 + np.exp(2.0))) < 1e-12 and abs(p[1] - 1 / (1 + np.exp(1.0))) < 1e-12
