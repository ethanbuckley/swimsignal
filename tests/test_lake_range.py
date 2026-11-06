"""The lake E. coli range (src/dipcast/lake_range.py, docs/LAKE-RANGE-WORDING-2026-11.md): the frozen
file, the research script's own answers reproduced, which lake gets which intercept, the off switch, and the rows it
logs."""

import numpy as np
import pandas as pd
import pytest

from dipcast import lake_range as sl
from dipcast.model.ecoli import features

TZ = "Europe/London"


def _X(r48, r24, risk, day="2026-07-01"):
    n = len(r48)
    return features(r48, r24, risk, np.ones(n), pd.Series(pd.Timestamp(day, tz=TZ), index=range(n)))


def test_the_committed_file_is_the_frozen_model():
    sl.clear_cache()
    m = sl.model()
    assert m is not None and m["rule"] == sl.RULE and len(m["sites"]) == 11
    assert set(m["background"]["log_weights"]) == set(m["sites"])   # the 2027 read's frozen reference


def test_reproduces_the_research_scripts_answers():
    """`checks` in the file came from scripts/lake_range_hindcast.py (CensoredRI.cdf by bisection): the site's code,
    written apart from it, must give the same medians and ranges, at two bathing waters and at an unsampled lake."""
    m = sl.model()
    for c in m["checks"]:
        bw = None if c["site"] == "unsampled" else c["site"]
        q = sl._quantiles(m, _X([c["rain_48h"]], [c["rain_24h"]], [c["risk"]], c["day"]), bw)
        for k, name in ((0.1, "low"), (0.5, "median"), (0.9, "high")):
            assert q[k][0] == pytest.approx(c[name], rel=1e-6), (c["site"], name)


def test_a_bathing_water_uses_its_own_intercept_and_any_other_lake_the_average():
    m = sl.model()
    s = m["sites"]["ukd1203-45650"]   # Windermere, Millerground Landing
    assert sl.site_for(m, s["lat"], s["lon"]) == "ukd1203-45650"
    assert sl.site_for(m, s["lat"] + 0.0005, s["lon"]) == "ukd1203-45650"   # about 56 m away
    assert sl.site_for(m, s["lat"] + 0.002, s["lon"]) is None               # about 220 m away
    X = _X([0.0, 25.0], [0.0, 15.0], [0.002, 0.08])
    a = sl.ranges(s["lat"], s["lon"], X, m)
    b = sl.ranges(s["lat"] + 0.01, s["lon"], X, m)
    assert a["basis"] == "tested" and b["basis"] == "average lake" and b["bw_id"] is None
    assert sl.ranges(*(lambda c: (c["lat"], c["lon"]))(m["sites"]["ukd1101-45800"]), X, m)["basis"] == "own samples"
    assert (a["low"] < a["median"]).all() and (a["median"] < a["high"]).all()
    assert (a["median"][1] > a["median"][0]) and (a["high"][1] > a["high"][0])   # a wet day reads higher


def test_a_missing_input_gives_no_range_and_inputs_are_not_altered():
    X = _X([0.0, np.nan], [0.0, np.nan], [0.002, 0.08])
    X0 = X.copy()
    r = sl.ranges(54.4, -2.9, X, sl.model())
    pd.testing.assert_frame_equal(X, X0)
    assert np.isfinite(r["median"][0]) and np.isnan(r["median"][1]) and np.isnan(r["high"][1])


def test_off_without_the_frozen_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "FILE", tmp_path / "missing.json")
    sl.clear_cache()
    assert sl.model() is None and sl.ranges(54.4, -2.9, _X([0.0], [0.0], [0.01])) is None
    (tmp_path / "other.json").write_text("{}")
    monkeypatch.setattr(sl, "FILE", tmp_path / "other.json")
    sl.clear_cache()
    assert sl.model() is None
    sl.clear_cache()


def test_logs_leads_from_zero_in_its_own_table(tmp_path):
    import duckdb
    days = pd.date_range("2026-09-29", periods=4, freq="D", tz=TZ)   # a past day, then 30 Sep, 1 and 2 Oct
    r48, r24, risk = np.array([1.0, 2.0, np.nan, 30.0]), np.array([0.5, 1.0, np.nan, 20.0]), np.full(4, 0.01)
    X = features(r48, r24, risk, np.ones(4), days)
    s = sl.model()["sites"]["ukj2310-11945"]   # Frensham Great Pond
    out = sl.ranges(s["lat"], s["lon"], X)
    issued = pd.Timestamp("2026-09-30 09:00", tz="UTC")
    db = tmp_path / "state.duckdb"
    assert sl.log_shadow(issued, s["lat"], s["lon"], days, r48, r24, risk, out, "spill=abc", path=db) == 3
    con = duckdb.connect(str(db))
    t = con.execute(f"SELECT * FROM {sl.TABLE} ORDER BY lead").df()
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    con.close()
    assert sl.TABLE in tables
    assert t["lead"].tolist() == [0, 1, 2]
    assert t["in_season"].tolist() == [True, False, False]
    assert t["median"].isna().tolist() == [False, True, False] and t["rain_48h"].isna().tolist() == [False, True, False]
    assert set(t["bw_id"]) == {"ukj2310-11945"} and set(t["basis"]) == {"tested"}
    assert set(t["rule"]) == {"lake-range-v1"} and set(t["model_sha"]) == {sl.SHA256[:16]}


def test_two_significant_figures():
    assert [sl.sig2(v) for v in (6.62, 55.4, 172.0, 1234.0)] == [6.6, 55.0, 170.0, 1200.0]
    assert sl.sig2(float("nan")) is None and sl.sig2(None) is None


# ------------------------------------------------------------------ higher or lower than usual
# docs/LAKE-RANGE-DIRECTION-PROPOSAL-2026-11.md: usual is the likely reading on the same date with the lake's typical
# inputs (data/processed/lake_range_usual.v1.json); the bands are fixed at twice and half.

def test_the_usual_file_is_the_committed_one_for_this_model():
    sl.clear_cache()
    u = sl.usual_inputs()
    m = sl.model()
    assert u is not None and u["model_sha256"] == sl.SHA256 and u["rule"] == sl.RULE
    assert set(u["sites"]) == set(m["sites"])   # every lake bathing water with its own samples; no Colwick
    assert sum(s["samples"] for s in u["sites"].values()) == m["fitted_on"]["lake_rows"]
    assert u["source"]["content_checks"]["intercept_weights_max_abs_difference"] < 1e-6
    for s in u["sites"].values():
        assert s["rain_48h"] >= s["rain_24h"] >= 0 and 0 < s["risk"] < 1


def test_off_without_the_usual_file_or_with_another(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "USUAL_FILE", tmp_path / "missing.json")
    sl.clear_cache()
    assert sl.usual_inputs() is None
    s = sl.model()["sites"]["ukj2310-11945"]
    out = sl.ranges(s["lat"], s["lon"], _X([1.0], [0.5], [0.01]))
    assert np.isfinite(out["median"][0]) and np.isnan(out["usual"][0])   # the range stays; no usual
    assert sl.compared(out, 0, "2026-07-01") == {}
    (tmp_path / "other.json").write_text("{}")
    monkeypatch.setattr(sl, "USUAL_FILE", tmp_path / "other.json")
    sl.clear_cache()
    assert sl.usual_inputs() is None
    sl.clear_cache()


def test_usual_is_the_median_at_the_lakes_typical_inputs_on_that_date():
    m, u = sl.model(), sl.usual_inputs()
    bw = "ukd1230-45725"   # Coniston Water, Brown Howe
    t = u["sites"][bw]
    days = pd.DatetimeIndex(["2026-05-15", "2026-07-05", "2026-09-20"], tz=TZ)
    X = features([30.0, 0.0, 5.0], [20.0, 0.0, 1.0], [0.3, 0.002, 0.05], np.ones(3), days)
    got = sl.usual(m, bw, X)
    want = sl._quantiles(m, features([t["rain_48h"]] * 3, [t["rain_24h"]] * 3, [t["risk"]] * 3, np.ones(3), days), bw)[0.5]
    np.testing.assert_allclose(got, want, rtol=1e-12)
    assert len(set(np.round(got, 6))) == 3                     # the date matters
    assert np.isnan(sl.usual(m, None, X)).all()                # an average lake has none
    # the day's own inputs do not move usual: only its date does
    X2 = features([0.0] * 3, [0.0] * 3, [0.9] * 3, np.ones(3), days)
    np.testing.assert_allclose(sl.usual(m, bw, X2), got, rtol=1e-12)


def test_direction_at_its_boundaries():
    d = sl.direction
    assert d(40.0, 20.0) == "higher" and d(39.0, 20.0) == "about"          # at least twice
    assert d(10.0, 20.0) == "lower" and d(11.0, 20.0) == "about"           # at most half
    assert d(20.0, 20.0) == "about"
    assert d(12.0, 6.0) == "higher" and d(11.0, 6.0) == "about"            # a usual under 10, today over it
    assert d(4.0, 9.0) == "about" and d(9.9, 2.0) == "about"               # both read "under 10": shown alike
    assert d(4.0, 30.0) == "lower"                                         # today under 10, usual about 30
    assert d(None, 20.0) is None and d(20.0, None) is None and d(float("nan"), 20.0) is None and d(5.0, 0.0) is None


def test_compared_only_in_season_at_a_sampled_lake_with_both_figures():
    out = {"basis": "tested", "median": np.array([44.0, 44.0]), "usual": np.array([21.7, np.nan])}
    assert sl.compared(out, 0, pd.Timestamp("2026-07-04", tz=TZ)) == {"usual": 22.0, "direction": "higher"}   # 44 >= 2 x 22
    assert sl.compared(out, 1, pd.Timestamp("2026-07-05", tz=TZ)) == {}            # no usual
    for day in ("2026-04-30", "2026-10-01", "2026-12-25"):
        assert sl.compared(out, 0, pd.Timestamp(day, tz=TZ)) == {}                  # out of season
    assert sl.compared({**out, "basis": "average lake"}, 0, "2026-07-04") == {}
    assert sl.compared({**out, "basis": "own samples"}, 0, "2026-05-01")["direction"] == "higher"
    assert sl.compared({**out, "median": np.array([np.nan, 1.0])}, 0, "2026-07-04") == {}
    assert sl.compared({"basis": "tested", "median": np.array([44.0])}, 0, "2026-07-04") == {}   # no usual key


def test_the_shadow_rows_are_unchanged_by_the_usual_line(tmp_path):
    """The usual reading rides on ranges() but is never logged: the table's columns and every logged value are the
    same with it as with the ranges dict lake-range-v1 had before it."""
    import duckdb
    days = pd.date_range("2026-07-01", periods=5, freq="D", tz=TZ)
    r48, r24, risk = np.array([1.0, 2.0, np.nan, 30.0, 0.0]), np.array([0.5, 1.0, np.nan, 20.0, 0.0]), np.full(5, 0.02)
    X = features(r48, r24, risk, np.ones(5), days)
    s = sl.model()["sites"]["ukd1203-45700"]   # Windermere, Fellfoot
    out = sl.ranges(s["lat"], s["lon"], X)
    assert "usual" in out and np.isfinite(out["usual"]).all()
    before = {k: v for k, v in out.items() if k != "usual"}
    issued = pd.Timestamp("2026-07-01 05:00", tz="UTC")
    frames = []
    for name, o in (("with", out), ("without", before)):
        db = tmp_path / f"{name}.duckdb"
        sl.log_shadow(issued, s["lat"], s["lon"], days, r48, r24, risk, o, "spill=abc", path=db)
        con = duckdb.connect(str(db))
        frames.append((con.execute(f"DESCRIBE {sl.TABLE}").df(), con.execute(f"SELECT * FROM {sl.TABLE} ORDER BY lead").df()))
        con.close()
    pd.testing.assert_frame_equal(frames[0][0], frames[1][0])
    pd.testing.assert_frame_equal(frames[0][1], frames[1][1])
    assert list(frames[0][1].columns) == list(sl.COLUMNS)
