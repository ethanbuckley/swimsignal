"""The winter water-temperature backtest's harness (scripts/water_temp_winter_backtest.py,
docs/WATER-TEMP-WINTER-BACKTEST-2026-11.md): it scores exactly what the live off-season route shows, on the frozen
files, with the record's rules."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dipcast.model import water_temp

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wtw", ROOT / "scripts" / "water_temp_winter_backtest.py")
wtw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wtw)


def test_the_frozen_files_are_the_ones_named_in_the_record():
    wtw.check_frozen()


def test_the_score_is_the_live_off_season_estimate_to_the_degree():
    model = water_temp.load(wtw.MODEL_FILE)
    rng = np.random.default_rng(1)
    idx = pd.date_range("2024-11-01", "2024-12-15 23:00", freq="h", tz="UTC")
    hourly = pd.Series(4 + 3 * np.sin(np.arange(len(idx)) / 40) + rng.normal(0, 1, len(idx)), index=idx)
    a7 = wtw.a7_by_day(model, hourly)
    for day in pd.date_range("2024-12-01", "2024-12-14"):
        for kind in ("river", "lake"):
            live = water_temp.estimate_any(model, pd.DataFrame({"time": idx, "air_c": hourly.values}), day, kind)
            assert live["route"] == f"{kind}_off_season"
            raw, shown = wtw.frozen_estimate(model, kind, float(a7[day]))
            assert shown == live["temp_c"]
            assert round(float(a7[day]), 1) == live["air_7d_c"]


def test_a_day_with_a_missing_hour_has_no_a7():
    model = water_temp.load(wtw.MODEL_FILE)
    idx = pd.date_range("2024-11-01", "2024-11-20 23:00", freq="h", tz="UTC")
    s = pd.Series(5.0, index=idx).drop(pd.Timestamp("2024-11-10 12:00", tz="UTC"))
    a7 = wtw.a7_by_day(model, s)
    assert np.isnan(a7[pd.Timestamp("2024-11-10")]) and np.isnan(a7[pd.Timestamp("2024-11-16")])
    assert np.isfinite(a7[pd.Timestamp("2024-11-17")])


def test_winter_months_run_october_to_april_with_exclusive_ends():
    m = wtw.winter_months(2023)
    assert m[0] == ("2023-10-01", "2023-11-01") and m[2] == ("2023-12-01", "2024-01-01")
    assert m[-1] == ("2024-04-01", "2024-05-01") and len(m) == 7
    w = wtw.winter_of(pd.Series(pd.to_datetime(["2023-10-01", "2024-04-30", "2024-01-15"])))
    assert list(w) == [2023, 2023, 2023]


def test_the_air_window_gives_a7_from_the_first_of_october():
    assert wtw.air_days(2023) == 221        # 23 Sep 2023 to 30 Apr 2024
    assert wtw.air_days(2024) == 220


def test_rows_keep_fresh_water_in_winter_months_only():
    raw = pd.DataFrame({
        "id": ["a", "a", "b", "c", "d", "e", "f"],
        "samplingPoint.notation": ["P1", "P1", "P1", "P2", "P3", "P4", "P1"],
        "phenomenonTime": ["2023-11-02T10:00:00", "2023-11-02T10:00:00", "2023-11-02T14:00:00",
                           "2023-12-01T09:00:00", "2024-05-02T09:00:00", "2023-11-03T09:00:00",
                           "2024-02-01T09:00:00"],
        "sampleMaterialType": ["RIVER / RUNNING SURFACE WATER"] * 3 + ["POND / LAKE / RESERVOIR WATER",
                               "RIVER / RUNNING SURFACE WATER", "SEA WATER", "RIVER / RUNNING SURFACE WATER"],
        "unit": ["celsius"] * 7,
        "result": ["6.0", "6.0", "8.0", "5.5", "12.0", "9.0", "<1"],
    })
    rows, counts = wtw.winter_rows(raw, with_result=True)
    assert counts["duplicate_id"] == 1
    got = {(r.point, str(r.date.date())): r.temp for r in rows.itertuples()}
    assert got == {("P1", "2023-11-02"): 7.0, ("P2", "2023-12-01"): 5.5}
    assert set(rows["winter"]) == {2023}


def test_cells_are_lakes_first_then_rivers_by_hash_order(monkeypatch):
    monkeypatch.setattr(wtw, "CELLS_MAX", 3)
    monkeypatch.setattr(wtw, "LAKE_CELLS_MAX", 2)
    pts = pd.DataFrame({"point": list("abcdef"), "type": ["lake", "lake", "lake", "river", "river", "river"],
                        "cell": ["L1", "L2", "L3", "R1", "R2", "L1"]})
    rows = pd.DataFrame({"point": list("abcdef"), "winter": [2023] * 6})
    plan = wtw.choose_cells(rows, pts, [2023])
    lakes = sorted(["L1", "L2", "L3"], key=wtw.cell_hash)[:2]
    assert plan["lake_cells"] == lakes
    assert plan["river_cells"] == sorted(["R1", "R2"], key=wtw.cell_hash)[:1]
    assert "L1" not in plan["river_cells"]


def test_verdict_rules():
    s = {"rmse": 1.8, "rmse_hi": 2.3, "bias": 0.2, "bias_lo": -0.1, "bias_hi": 0.5}
    assert wtw.verdict(40, 400, s) == {"verdict": "pass", "bias_material": False, "within_c": 2}
    assert wtw.verdict(29, 400, s)["verdict"] == "too few to judge"
    assert wtw.verdict(40, 299, s)["verdict"] == "too few to judge"
    assert wtw.verdict(40, 400, {**s, "rmse_hi": 2.6})["verdict"] == "inconclusive"
    assert wtw.verdict(40, 400, {**s, "rmse": 2.6, "rmse_hi": 3.0})["verdict"] == "fail"
    assert wtw.verdict(40, 400, {**s, "bias": 0.8, "bias_lo": 0.3})["bias_material"] is True
    assert wtw.verdict(40, 400, {**s, "bias": -0.8, "bias_lo": -1.2, "bias_hi": 0.1})["bias_material"] is False


def test_two_way_bootstrap_brackets_the_point_and_is_seeded():
    rng = np.random.default_rng(0)
    g = np.repeat(np.arange(40), 20)
    b = np.tile(np.arange(20), 40)
    e = rng.normal(0.5, 1.5, len(g)) + np.repeat(rng.normal(0, 0.5, 40), 20)
    s1 = wtw.two_way_boot(g, b, e, n_boot=300)
    s2 = wtw.two_way_boot(g, b, e, n_boot=300)
    assert s1 == s2
    assert s1["rmse_lo"] < s1["rmse"] < s1["rmse_hi"] and s1["bias_lo"] < s1["bias"] < s1["bias_hi"]
    gb = wtw.group_boot(g, e, n_boot=300)
    assert gb["rmse_lo"] < s1["rmse"] < gb["rmse_hi"]


@pytest.mark.parametrize("kind", ["river", "lake"])
def test_shown_estimates_never_go_below_zero(kind):
    model = water_temp.load(wtw.MODEL_FILE)
    raw, shown = wtw.frozen_estimate(model, kind, -60.0)
    assert raw < 0 and shown == 0
