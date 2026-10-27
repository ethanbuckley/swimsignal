"""scripts/lake_temperature_eval (docs/LAKE-TEMPERATURE-TEST-2026-10.md), on synthetic data only: no network, no
archive value. Air windows, the choice of window inside training data, the candidate's fold fit, the verdict, the
report groups, the Open-Meteo file filter and the shared day cap."""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lake_temperature_eval"))
sys.path.insert(0, str(ROOT / "scripts" / "water_temperature_model_eval"))
import lt_fetch as lf
import lt_protocol as lp
import lt_score as ls


def season(year=2020, start=10.0, slope=0.1):
    idx = pd.date_range(f"{year}-04-01", f"{year}-09-30", freq="D")
    return pd.Series(start + slope * np.arange(len(idx)), index=idx)


# ---- air windows --------------------------------------------------------------------------------------------------
def test_windows_on_a_straight_line():
    s = season()
    w = lp.air_windows(s, 2020, ["2020-05-01"])
    # 1 May is day 30 after 1 April (index 30): value 13.0
    assert w.loc[0, "a1"] == pytest.approx(13.0)
    assert w.loc[0, "a7"] == pytest.approx(13.0 - 0.3)
    assert w.loc[0, "a14"] == pytest.approx(13.0 - 0.65)
    assert w.loc[0, "a30"] == pytest.approx(13.0 - 1.45)
    assert w.loc[0, "a_apr"] == pytest.approx(11.5)          # mean of days 0..30


def test_ewma_is_normalised_over_days_since_1_april():
    s = season()
    w = lp.air_windows(s, 2020, ["2020-04-03"])
    a = lp.alpha_of(10)
    wts = np.array([(1 - a) ** 2, (1 - a), 1.0])
    want = float((wts * np.array([10.0, 10.1, 10.2])).sum() / wts.sum())
    assert w.loc[0, "e10"] == pytest.approx(want)
    assert lp.alpha_of(10) == pytest.approx(1 - math.exp(-0.1))


def test_long_tau_approaches_season_mean_and_short_tau_today():
    s = season()
    w = lp.air_windows(s, 2020, ["2020-08-01"])
    assert abs(w.loc[0, "e5"] - w.loc[0, "a1"]) < abs(w.loc[0, "e90"] - w.loc[0, "a1"])


def test_a_gap_since_1_april_blanks_every_window_after_it():
    s = season().drop(pd.Timestamp("2020-05-10"))
    w = lp.air_windows(s, 2020, ["2020-05-09", "2020-05-10", "2020-07-01", "2019-06-01"])
    assert w.iloc[0].notna().all()
    assert w.iloc[1].isna().all() and w.iloc[2].isna().all()
    assert w.iloc[3].isna().all()                             # another year: nothing


def test_windows_ignore_days_outside_the_season():
    s = season()
    extra = pd.Series([100.0], index=[pd.Timestamp("2020-03-31")])
    w0 = lp.air_windows(s, 2020, ["2020-05-01"])
    w1 = lp.air_windows(pd.concat([extra, s]), 2020, ["2020-05-01"])
    pd.testing.assert_frame_equal(w0, w1)


def test_bridge_is_the_first_tests_line():
    assert lp.bridge([0.0])[0] == pytest.approx(0.5012729716522162)
    assert lp.bridge([10.0])[0] == pytest.approx(0.5012729716522162 + 9.791684691913549)


# ---- choosing a window --------------------------------------------------------------------------------------------
def synth(n_waters=40, seed=0, years=(2010, 2011)):
    rng = np.random.default_rng(seed)
    out = []
    for g in range(n_waters):
        depth = rng.uniform(1, 30)
        for y in years:
            weather = np.zeros(183)
            for i in range(1, 183):                           # weather that lasts days: AR(1), so lags differ
                weather[i] = 0.9 * weather[i - 1] + rng.normal(0, 1.2)
            s = season(y, start=6, slope=0.08) + weather
            dates = pd.date_range(f"{y}-05-01", f"{y}-09-30", freq="7D")
            w = lp.air_windows(s, y, dates)
            temp = 0.9 * w["e30"].to_numpy() + 2 - 0.05 * depth + rng.normal(0, 0.3, len(w))
            d = w.assign(temp=temp, group=f"lake:{g}", fold=wp_fold(f"lake:{g}"), date=dates, year=y,
                         log_lake_area=np.log10(rng.uniform(0.01, 5)), log_depth=np.log10(depth),
                         elevation=rng.uniform(0, 300))
            out.append(d)
    import wt_protocol as wp
    return wp.add_doy(pd.concat(out, ignore_index=True))


def wp_fold(g):
    import wt_protocol as wp
    return wp.fold_of(g)


def test_inner_scores_pick_the_window_the_data_were_made_from():
    d = synth()
    tr = d[d["fold"] != 0]
    sc = lp.inner_scores(tr, lp.THIRD_CHOICES)
    w = lp.choose(sc, lp.THIRD_CHOICES)
    assert w in ("e20", "e30", "e45")
    assert sc["e30"] < sc["a14"]


def test_choose_breaks_ties_by_list_order():
    assert lp.choose({"a14": 1.0, "a30": 1.0, "e5": 2.0}, ["a14", "a30", "e5"]) == "a14"
    assert lp.choose({"a14": 1.0, "a30": 1.0, "e5": 2.0}, ["a30", "a14", "e5"]) == "a30"


def test_inner_scores_use_only_the_rows_given():
    d = synth()
    tr = d[d["fold"] != 0]
    poisoned = d.copy()
    poisoned.loc[poisoned["fold"] == 0, "temp"] = 999.0
    assert lp.inner_scores(tr, ["a30"]) == lp.inner_scores(poisoned[poisoned["fold"] != 0], ["a30"])


# ---- the fold fit -------------------------------------------------------------------------------------------------
def test_fit_fold_beats_its_baselines_on_unseen_waters():
    d = synth(n_waters=60)
    tr, te = d[d["fold"] != 0], d[d["fold"] == 0]
    m = lp.fit_fold(tr)
    assert m["third_window"] in lp.THIRD_CHOICES and m["e_window"] in lp.E_WINDOWS
    assert set(m["features"]) <= set(lp.gbm_inputs(m["e_window"]))
    p = lp.predict_fold(m, te.reset_index(drop=True))
    r = {c: float(np.sqrt(np.mean((p[c] - p["temp"]) ** 2))) for c in ("pred_cand", "pred_third", "pred_air7",
                                                                          "pred_doy")}
    assert r["pred_third"] < r["pred_air7"] < r["pred_doy"]
    assert r["pred_cand"] < r["pred_third"]                   # depth is in the data, and only stage 2 knows it


def test_fit_fold_drops_an_input_with_no_value():
    d = synth(n_waters=40).assign(log_depth=np.nan)
    m = lp.fit_fold(d[d["fold"] != 0])
    assert "log_depth" not in m["features"]


# ---- verdict ------------------------------------------------------------------------------------------------------
G = {"gain": 0.3, "lo": 0.1, "hi": 0.5}
B = {"gain": 0.05, "lo": -0.01, "hi": 0.1}


def test_verdict_passes_only_with_all_six():
    gains = {"doy": G, "air7": G, "third": G}
    assert lp.verdict(30, 300, 1.5, 2.5, gains)["label"] == "pass"
    assert lp.verdict(30, 300, 1.51, 2.5, gains)["label"] == "fail"
    assert lp.verdict(30, 300, 1.5, 2.51, gains)["label"] == "fail"
    assert lp.verdict(30, 300, 1.2, 2.0, gains | {"third": B})["label"] == "fail"
    assert lp.verdict(30, 300, 1.2, 2.0, gains | {"air7": B})["label"] == "fail"
    assert lp.verdict(30, 300, 1.2, 2.0, gains | {"doy": B})["label"] == "fail"


def test_verdict_gate():
    gains = {"doy": G, "air7": G, "third": G}
    assert lp.verdict(29, 1000, 1.0, 1.0, gains)["label"] == "too few to judge"
    assert lp.verdict(100, 299, 1.0, 1.0, gains)["label"] == "too few to judge"


def test_p90():
    assert lp.p90(np.r_[np.zeros(9), 10.0]) == pytest.approx(1.0)


# ---- report groups ------------------------------------------------------------------------------------------------
def test_reservoir_and_size_bands():
    assert lp.is_reservoir("Haweswater Reservoir", None)
    assert lp.is_reservoir(None, "DRAYCOTE WATER RESERVOIR OUTLET")
    assert not lp.is_reservoir("Ullswater", "ULLSWATER AT POOLEY BRIDGE")
    assert not lp.is_reservoir(np.nan, None)
    assert lp.size_band(8.8) == "WFD 1 km2 and over"
    assert lp.size_band(1.0) == "WFD 1 km2 and over"
    assert lp.size_band(0.5) == "WFD 0.1 to 1 km2"
    assert lp.size_band(0.05) == "WFD under 0.1 km2"
    assert lp.size_band(float("nan")) == "not matched to a WFD polygon"


# ---- files and the Open-Meteo day cap -----------------------------------------------------------------------------
def test_load_om_reads_only_test_files(tmp_path):
    a = {"elevation": 12.0, "daily": {"time": ["2026-04-01"], "temperature_2m_mean": [5.0]}}
    (tmp_path / "2026_0123456789abcdef.json").write_text(json.dumps({"year": 2026, "cells": ["c1"], "answer": [a]}))
    (tmp_path / "forecast_temp_2026-10-27_000.json").write_text("{not ours")
    air, elev = ls.load_om([tmp_path])
    assert list(air) == [("c1", 2026)] and elev == {"c1": 12.0}


def test_shared_day_cap_counts_both_logs(tmp_path):
    now = datetime(2026, 10, 27, 20, 0, tzinfo=UTC)
    other = tmp_path / "other.log"
    other.write_text(f"{(now - timedelta(hours=3)).isoformat()}\t200\t1\t9400\turl\n")
    c = lf.SharedDayOM(tmp_path / "c", False, now=lambda: now, other_log=other, others=lambda: [])
    assert c.spent("2026-10-27") == pytest.approx(9400)
    assert c.spent() == 0                                    # the total cap counts this fetch only
    slept = []
    c.sleep = lambda s: (slept.append(s), (_ for _ in ()).throw(StopIteration))
    with pytest.raises(StopIteration):
        c._wait_for_day(200)                                 # 9,400 + 200 > 9,500: waits for the next UTC day
    assert slept and slept[0] > 3600


def test_plan_weight():
    assert lf.plan_weight(["c"] * 30) == pytest.approx(30 * 18.3 / 14)
