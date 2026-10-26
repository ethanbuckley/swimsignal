"""Scores S1 and S2 of a spot's level in scripts/evaluate_2027.py (docs/PREREGISTRATION-2027.md, amendments 1 and 2),
on a small made-up file D whose figures are worked out here by hand, and the frozen spot list that
scripts/make_eval2027.py --spot-list makes at the tag."""

import hashlib
import itertools
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
JUNE = (date(2027, 6, 1), date(2027, 6, 2))
FROZEN = {"spill": "s1", "cal": "c1", "ecoli": "e1", "rain": "open-meteo-forecast"}
STAMP = "spill=s1;cal=c1;ecoli=e1;code=0.1.0+abc1234;rain=open-meteo-forecast"


def _script(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


E = _script("evaluate_2027")
M = _script("make_eval2027")


def _pairs_auc(y, p):
    pos = [pi for yi, pi in zip(y, p, strict=True) if yi]
    neg = [pi for yi, pi in zip(y, p, strict=True) if not yi]
    return sum(1.0 if a > b else 0.5 if a == b else 0.0 for a, b in itertools.product(pos, neg)) / (len(pos) * len(neg))


def _write(path: Path, rows: list[list], columns: list[str], note: str = "notes") -> Path:
    """A published file: comment lines, then the CSV, values at 6 places as the site writes them."""
    with open(path, "w", newline="") as fh:
        fh.write(f"# {note}\n# credits\n")
        pd.DataFrame(rows, columns=columns).to_csv(fh, index=False, float_format="%.6f", lineterminator="\n")
    return path


SPOT_LIST_ROWS = [["A", "Spot A", "river", "X Water", 3, "0.0000", 0, 1, ""],
                  ["B", "Spot B", "lake", "Y Water", 1, "0.0000", 0, 1, ""],
                  ["C", "Spot C", "river", "Z Water", 2, "0.1800", 1, 1, ""],
                  ["Z", "Spot Z", "river", "", 0, "", 0, 0, "no_overflow_upstream"]]
# (spot, day, lead, forecast, observed, climatology, reason)
D_ROWS = [("A", "2027-06-01", 0, 0.45, 0.70, 0.10, ""),            # warned, event: hit; reference quiet: miss
          ("A", "2027-06-01", 1, 0.395, 0.00, 0.50, ""),           # 0.395 shows as 40: a false alarm; reference false alarm
          ("A", "2027-06-02", 0, 0.10, 0.42, 0.05, ""),            # event, not warned: miss
          ("B", "2027-06-01", 0, 0.05, 0.01, 0.02, ""),            # quiet
          ("B", "2027-06-02", 0, 0.30, 0.3944, 0.60, ""),          # 0.3944 shows as 39: no event; reference false alarm
          ("A", "2027-06-02", 1, None, None, None, "missed_deadline"),
          ("B", "2027-06-02", 1, 0.20, None, 0.10, "max_gap"),
          ("C", "2027-06-01", 0, 0.60, None, 0.30, "no_live_feed"),
          ("Q", "2027-06-01", 0, 0.60, 0.60, 0.30, ""),            # not on the list
          ("A", "2027-06-03", 0, 0.60, 0.60, 0.30, "")]            # outside the window


def _d(tmp_path, rows=D_ROWS, version=STAMP):
    full = [[s, d, ld, None if f is None else "2027-05-31T07:00+01:00", f, o, c, 1.0 if o is not None else 0.5, r or None,
             None if f is None else version] for s, d, ld, f, o, c, r in rows]
    return _write(tmp_path / "verification_spots_live.csv", full, E.SPOT_COLUMNS)


def _list(tmp_path):
    p = _write(tmp_path / "spots.csv", SPOT_LIST_ROWS, M.SPOT_LIST_COLUMNS)
    return p, E.read_published(p, dtype=str, keep_default_na=False)


def _stratum(res, name):
    return next(s for s in res["strata"] if s["stratum"] == name)


def test_the_level_is_the_sites_own_on_every_published_value(tmp_path):
    """Amendment 2, items 3 and 11: the script's level rule is transport.risk_label's, applied to the double read back
    from each 6-place value, and the live scorer reads the same double."""
    from dipcast import forecast_log
    from dipcast.model import transport
    assert E.SCORE_CUTS == transport.SCORE_CUTS and E.SPOT_HIGH == forecast_log.SPOT_HIGH
    assert E.SPOT_COLUMNS == forecast_log.SPOT_COLUMNS and forecast_log.SPOT_DECIMALS == 6
    # Every 6-place value from 0 to 1 in steps of 0.000037 (27,028 values), and every tie at 3 places near the cuts.
    vals = sorted(set(np.round(np.arange(0, 1, 0.000037), 6)) | {c / 100 + k / 1e4 for c in (15, 40, 70) for k in range(-60, 61)})
    path = _write(tmp_path / "v.csv", [[v] for v in vals], ["x"])
    back = E.read_published(path, float_precision="round_trip")["x"]
    pub = forecast_log.as_published(pd.Series(vals))
    assert (back.to_numpy() == pub.to_numpy()).all()
    assert [E.BANDS[i] for i in E.spot_levels(back)] == [transport.risk_label(float(v)) for v in back]
    assert list(E.spot_levels([float("nan"), None])) == [-1, -1]


def test_s1_on_the_fixture_matches_a_hand_count(tmp_path):
    _, sl = _list(tmp_path)
    res = E.evaluate_spots(_d(tmp_path), sl, *JUNE, resamples=200, seed=E.SPOT_SEED)
    assert res["rows_outside_list"] == 1   # Q; the 3 June row is outside the window
    allr = _stratum(res, "all leads")
    w = allr["warning"]
    assert (allr["n"], allr["events"]) == (5, 2)
    assert (w["hits"], w["misses"], w["false_alarms"], w["quiet_correct"]) == (1, 1, 1, 2)
    rw = allr["reference_warning"]
    assert (rw["hits"], rw["misses"], rw["false_alarms"], rw["quiet_correct"]) == (0, 2, 2, 1)
    y = [1, 0, 1, 0, 0]
    assert allr["auc"] == pytest.approx(_pairs_auc(y, [0.45, 0.395, 0.10, 0.05, 0.30]))
    assert allr["reference_auc"] == pytest.approx(_pairs_auc(y, [0.10, 0.50, 0.05, 0.02, 0.60]))
    # Forecast levels (rows) against observed levels (columns): 0.45 H/VH, 0.395 H/L, 0.10 L/H, 0.05 L/L, 0.30 M/M.
    assert allr["levels"]["counts"] == [[1, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 1], [0, 0, 0, 0]]
    assert allr["mean_observed"] == pytest.approx(np.mean([0.70, 0.0, 0.42, 0.01, 0.3944]))
    lo, hi = allr["ci"]["auc"]["lo"], allr["ci"]["auc"]["hi"]
    assert lo <= allr["auc"] <= hi
    # Strata: same day and in advance, leads, river and lake, the list's company.
    assert _stratum(res, "same day (lead 0)")["n"] == 4 and _stratum(res, "in advance (leads 1-4)")["n"] == 1
    assert _stratum(res, "water: lake")["n"] == 2 and _stratum(res, "company: X Water")["n"] == 3
    # Every eligible spot x day x lead is a cell: 3 spots x 2 days x 5 leads, Z excluded, C never observed.
    cov = res["coverage"]
    assert (cov["eligible_spots"], cov["never_observed_spots"], cov["cells"], cov["scored"]) == (3, 1, 30, 5)
    nr = cov["not_scored_by_reason"]
    assert nr["missed_deadline"] == 1 and nr["max_gap"] == 1 and nr["no_live_feed"] == 1
    assert nr["no_row"] == 30 - 8 and sum(nr.values()) == 30 - 5
    assert res["bootstrap"]["seed"] == 20270502


def test_s1_keeps_only_the_frozen_models_forecasts_and_stops_on_a_repeat(tmp_path):
    _, sl = _list(tmp_path)
    rows = [r for r in D_ROWS if r[0] == "A" and r[1] == "2027-06-01"]
    path = _d(tmp_path, rows)
    # Rewrite the second row's stamp as a candidate's.
    text = path.read_text().splitlines()
    text[3] = text[3].replace("spill=s1", "spill=zz")
    path.write_text("\n".join(text) + "\n")
    res = E.evaluate_spots(path, sl, *JUNE, resamples=20, seed=1, model=FROZEN)
    assert res["versions"]["left_out"] == 1 and res["coverage"]["not_scored_by_reason"]["other_version"] == 1
    assert _stratum(res, "all leads")["n"] == 1
    with pytest.raises(SystemExit, match="repeated"):
        E.evaluate_spots(_d(tmp_path, D_ROWS + [D_ROWS[0]]), sl, *JUNE, resamples=20, seed=1)


ECOLI_COLS = ["bathing_water", "kind", "sample_time", "day", "ecoli", "observed", "lead", "issued_at", "forecast", "version"]


def test_s2_waits_for_the_exposure_column_then_counts_by_level(tmp_path):
    sites = pd.DataFrame({"unit": ["bathing_water"] * 2, "id": ["R1", "L1"], "name": ["r", "l"], "company": ["X", "Y"],
                          "water": ["river", "lake"], "spots": ["bw-R1", "bw-L1"]})
    rows = [["R1", "river", "2027-06-01T10:00+01:00", "2027-06-01", 1200, 1, 0, "2027-06-01T07:00+01:00", 0.3, STAMP, 0.45],   # High, over: hit
            ["R1", "river", "2027-06-01T10:00+01:00", "2027-06-01", 1200, 1, 1, "2027-05-31T07:00+01:00", 0.2, STAMP, 0.10],   # Low, over: miss
            ["R1", "river", "2027-06-02T10:00+01:00", "2027-06-02", 100, 0, 0, "2027-06-02T07:00+01:00", 0.1, STAMP, 0.395],   # High: false alarm
            ["R1", "river", "2027-06-02T10:00+01:00", "2027-06-02", 100, 0, 1, "2027-06-01T07:00+01:00", 0.1, STAMP, 0.02],
            ["R1", "river", "2027-06-02T10:00+01:00", "2027-06-02", 100, 0, 2, "2027-06-02T11:00+01:00", 0.1, STAMP, 0.99],    # issued after
            ["L1", "lake", "2027-06-01T10:00+01:00", "2027-06-01", 50, 0, 0, "2027-06-01T07:00+01:00", 0.1, STAMP, 0.2]]
    no_exp = _write(tmp_path / "e0.csv", [r[:-1] for r in rows], ECOLI_COLS)
    assert E.evaluate_spots_ecoli(no_exp, sites, *JUNE, resamples=20, seed=1)["status"].startswith("not run")
    path = _write(tmp_path / "e.csv", rows, [*ECOLI_COLS, "exposure"])
    res = E.evaluate_spots_ecoli(path, sites, *JUNE, resamples=50, seed=E.SPOT_SEED)
    assert res["pairs"] == 5
    riv = _stratum(res, "river: all leads")
    w = riv["warning"]
    assert (riv["n"], riv["samples_over_900"], w["hits"], w["misses"], w["false_alarms"], w["quiet_correct"]) == (4, 2, 1, 1, 1, 1)
    assert riv["auc"] == pytest.approx(_pairs_auc([1, 1, 0, 0], [0.45, 0.10, 0.395, 0.02]))
    by = {b["level"]: b for b in riv["by_level"]}
    assert (by["low"]["n"], by["low"]["share_over_900"]) == (2, 0.5) and (by["high"]["n"], by["high"]["share_over_900"]) == (2, 0.5)
    assert _stratum(res, "lake: all leads")["n"] == 1 and _stratum(res, "river: same day (lead 0)")["n"] == 2


def test_main_runs_s1_beside_the_primary_scores_and_says_it_is_not_registered_before_the_tag(tmp_path):
    fix = ROOT / "tests" / "fixtures" / "eval2027"
    lp, _ = _list(tmp_path)
    out = tmp_path / "r.json"
    E.main(["--spills", str(fix / "spills.csv"), "--sites", str(fix / "sites.csv"), "--climatology", str(fix / "climatology.json"),
            "--from", "2027-06-01", "--to", "2027-06-02", "--resamples", "20", "--spots", str(_d(tmp_path)),
            "--spot-list", str(lp), "--out", str(out)])
    res = json.loads(out.read_text())
    assert _stratum(res["spot_level"]["s1"], "all leads")["n"] == 5
    assert res["spot_level"]["s2"]["status"].startswith("not run")
    assert res["frozen_files"]["data/eval2027/spots.csv"]["as_registered"] is False and res["registered_settings"] is False
    # Without the frozen list (before the tag), S1 says so and the rest runs.
    E.main(["--spills", str(fix / "spills.csv"), "--spots", str(_d(tmp_path)), "--spot-list", str(tmp_path / "none.csv"),
            "--out", str(out)])
    assert json.loads(out.read_text())["spot_level"]["s1"]["status"].startswith("not run: no frozen spot list")


def test_the_spot_list_is_made_from_the_builds_upstream_files(tmp_path):
    spots = [{"id": "osm-a", "name": "A", "kind": "river"}, {"id": "b", "name": "B", "kind": "lake"},
             {"id": "c", "name": "C", "kind": "river"}, {"id": "d", "name": "D", "kind": "river"}]
    up = {"osm-a": [{"site_id": "1", "company": "X Water", "weight": 0.2, "has_live": True},
                    {"site_id": "2", "company": "Y Water", "weight": 0.9, "has_live": True},
                    {"site_id": "3", "company": "Y Water", "weight": 0.05, "has_live": False}],
          "c": [{"site_id": "4", "company": "W Water", "weight": 1.0, "has_live": False}],
          "d": [{"site_id": "5", "company": "V Water", "weight": 1.0, "has_live": True}]}
    sl = M.eligible_spots(spots, up, listed={"osm-a", "b", "c"})
    r = sl.set_index("id")
    assert list(sl.columns) == M.SPOT_LIST_COLUMNS
    # 0.05 of 1.15 is 4.3%: observable. The company is the overflow with the largest weight's.
    assert (r.loc["osm-a", "company"], r.loc["osm-a", "share_no_live"], r.loc["osm-a", "never_observed"], r.loc["osm-a", "eligible"]) == (
        "Y Water", "0.0435", 0, 1)
    assert (r.loc["c", "never_observed"], r.loc["c", "eligible"]) == (1, 1)
    assert (r.loc["b", "eligible"], r.loc["b", "reason"]) == (0, "no_overflow_upstream")
    assert (r.loc["d", "eligible"], r.loc["d", "reason"]) == (0, "not_in_spot_files")


def test_the_spot_list_mode_writes_only_spots_csv_and_the_same_bytes_twice(tmp_path):
    gen = "2027-04-30T08:00:00+01:00"
    (tmp_path / "up").mkdir()
    sj = {"generated_at": gen, "spots": [{"id": "bw-uke4100-08901", "name": "W", "kind": "river"}, {"id": "nothing-here", "name": "N", "kind": "lake"}]}
    (tmp_path / "spots.json").write_text(json.dumps(sj))
    (tmp_path / "up" / "bw-uke4100-08901.json").write_text(json.dumps({"id": "bw-uke4100-08901", "generated_at": gen, "overflows": [
        {"site_id": "1", "company": "Yorkshire Water", "weight": 0.5, "has_live": True}]}))
    args = ["--spot-list", "--spots", str(tmp_path / "spots.json"), "--upstream", str(tmp_path / "up")]
    M.main([*args, "--out", str(tmp_path / "o1")])
    M.main([*args, "--out", str(tmp_path / "o2")])
    assert sorted(p.name for p in (tmp_path / "o1").iterdir()) == ["spots.csv"]
    b1, b2 = (tmp_path / "o1" / "spots.csv").read_bytes(), (tmp_path / "o2" / "spots.csv").read_bytes()
    assert b1 == b2 and hashlib.sha256(b1).hexdigest()
    sl = E.read_published(tmp_path / "o1" / "spots.csv", dtype=str, keep_default_na=False).set_index("id")
    assert sl.loc["nothing-here", "reason"] == "not_in_spot_files"   # not in spots.csv: a made-up id
    assert (sl.loc["bw-uke4100-08901", "eligible"], sl.loc["bw-uke4100-08901", "company"]) == ("1", "Yorkshire Water")
    assert b"amendments 1 and 2" in b1
    # The other mode still needs its inputs.
    with pytest.raises(SystemExit):
        M.main(["--spots", str(tmp_path / "spots.json"), "--upstream", str(tmp_path / "up"), "--out", str(tmp_path / "o3")])


def test_a_later_hash_row_in_the_protocol_replaces_an_earlier_one(tmp_path):
    """Amendment 2 records the scripts' new hashes as rows at its end, leaving section 13's lines as they were."""
    a, b = "a" * 64, "b" * 64
    p = tmp_path / "protocol.md"
    p.write_text(f"## 13\n| `scripts/evaluate_2027.py` | `{a}` |\n## 17\n| `scripts/evaluate_2027.py` | `{b}` |\n")
    assert E.recorded_hashes(p) == {"scripts/evaluate_2027.py": b}
