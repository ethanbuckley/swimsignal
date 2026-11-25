"""Offline tests for coastal C1's fit and backtest code (docs/COASTAL-C1-PROTOCOL-2026-11.md, amendment 1)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "coastal_c1"))
import backtest  # noqa: E402
import c1  # noqa: E402


def hourly(start, values):
    idx = pd.date_range(start, periods=len(values), freq="h", tz="UTC")
    return pd.Series(values, index=idx, dtype=float)


def test_window_sums_take_hours_ending_at_or_before_the_sample():
    rain = hourly("2024-06-01 01:00", np.arange(1, 49))       # hour ending 01:00 holds 1 mm, 02:00 holds 2 mm ...
    t = pd.Series(pd.to_datetime(["2024-06-02 10:40"]).tz_localize("UTC"))
    v, cov = c1.window_sums(t, rain, 3)
    # hours ending 08:00, 09:00, 10:00 on 2 June are the 32nd, 33rd and 34th values
    assert v[0] == 32 + 33 + 34
    assert cov[0] == 1


def test_window_sums_are_missing_not_zero_when_coverage_is_short():
    vals = np.ones(48)
    vals[20:30] = np.nan
    rain = hourly("2024-06-01 01:00", vals)
    t = pd.Series(pd.to_datetime(["2024-06-02 06:00"]).tz_localize("UTC"))
    v, cov = c1.window_sums(t, rain, 24)
    assert np.isnan(v[0]) and cov[0] < c1.MIN_COVER
    v, _ = c1.window_sums(t, None, 24)
    assert np.isnan(v[0])


def test_window_before_the_series_starts_is_missing():
    rain = hourly("2024-06-01 01:00", np.ones(10))
    t = pd.Series(pd.to_datetime(["2024-06-01 05:00"]).tz_localize("UTC"))
    assert np.isnan(c1.window_sums(t, rain, 24)[0][0])


def test_over_follows_the_qualifiers():
    v = pd.Series([600.0, 500.0, 500.0, 600.0])
    q = pd.Series(["=", "=", ">", "<"])
    assert c1.over(v, q, 500).tolist() == [True, False, True, False]


def test_last_sample_is_same_site_same_year():
    df = pd.DataFrame({"site_id": ["a", "a", "a", "b"], "year": [2012, 2012, 2013, 2012],
                       "time": pd.to_datetime(["2012-05-01", "2012-05-10", "2013-05-01", "2012-05-11"]),
                       "ecoli": [100.0, 1000.0, 10.0, 50.0]})
    x = c1.last_sample(df)
    assert x[0].tolist() == [0.0, 1.0]
    assert x[1].tolist() == [1.0, 0.0]                         # log10(100) - 1
    assert x[2].tolist() == [0.0, 1.0]                         # a new year starts with none
    assert x[3].tolist() == [0.0, 1.0]


def test_site_rate_leaves_the_rows_own_year_out_and_unknown_site_gets_p0():
    site = np.array(["a"] * 20 + ["b"] * 20)
    year = np.array([2022] * 10 + [2023] * 10 + [2022] * 10 + [2023] * 10)
    y = np.array([1] * 10 + [0] * 10 + [0] * 20)
    tab = c1.site_table(site, year, y)
    p0, m = tab["p0"], tab["m"]
    r = c1.site_rate(tab, np.array(["a", "a", "z"]), np.array([2022, 2015, 2015]), leave_own_year=True)
    assert r[0] == pytest.approx((0 + m * p0) / (10 + m))      # 2022's ten exceedances left out
    assert r[1] == pytest.approx((10 + m * p0) / (20 + m))      # a backtest year: nothing to leave out
    assert r[2] == pytest.approx(p0)


def test_two_way_bootstrap_of_a_constant_is_that_constant():
    rng = np.random.default_rng(1)
    s = np.repeat(np.arange(5), 4)
    t = np.tile(np.arange(4), 5)
    out = backtest.two_way_mean(np.full(20, -0.5), s, t, 5, 4, rng)
    assert np.allclose(out, -0.5)


@pytest.mark.parametrize("diff,interval,agree,exc,expected", [
    (-0.001, [-0.002, -0.0001], 7, 900, "supported on unseen seasons"),
    (-0.001, [-0.002, -0.0001], 5, 900, "mixed"),
    (-0.001, [-0.002, 0.0003], 8, 900, "mixed"),
    (0.0, [-0.001, 0.001], 8, 900, "not supported"),
    (-0.001, [-0.002, -0.0001], 9, 120, "too few"),
])
def test_verdict_rules(diff, interval, agree, exc, expected):
    main = {"difference_c1_minus_c0": diff, "interval_two_way": interval, "seasons_below_zero": agree,
            "exceedances": exc}
    assert backtest.verdict(main) == expected
