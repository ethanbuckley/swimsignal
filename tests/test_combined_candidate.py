"""The combined candidate's harness (docs/COMBINED-CANDIDATE-BACKTEST-2026-11.md): the combination, the two simple
rules and their trailing fit, on synthetic rows."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import combined_candidate_backtest_2026 as m  # noqa: E402


def test_combine_is_the_base_without_uplift_or_status():
    rng = np.random.default_rng(0)
    base, d2 = rng.uniform(0.01, 0.9, 50), rng.uniform(0.01, 0.9, 50)
    unknown = np.zeros(50, bool)
    np.testing.assert_allclose(m.combine(base, d2, d2, unknown), base, rtol=1e-9)
    cand = rng.uniform(0.01, 0.9, 50)
    np.testing.assert_array_equal(m.combine(base, cand, d2, np.ones(50, bool)), base)


def test_combine_moves_the_base_by_the_status_log_odds():
    base, d2, cand = np.array([0.1]), np.array([0.2]), np.array([0.5])
    got = m.combine(base, cand, d2, np.array([False]))
    want = 1 / (1 + np.exp(-(np.log(0.1 / 0.9) + np.log(1.0) - np.log(0.25))))
    np.testing.assert_allclose(got, [want])
    assert np.isfinite(m.combine(np.array([1.0]), np.array([1.0]), np.array([0.0]), np.array([False]))).all()


def test_rain_rule_is_strict_and_missing_is_unknown():
    r = m.rain_side(np.array([5.0, 5.0, 4.0, np.nan]), np.array([5.0, 5.1, 1.0, 3.0]))
    assert r[0] == 0 and r[1] == 1 and r[2] == 0 and np.isnan(r[3])


def test_trailing_chance_reads_only_days_before_the_issue():
    # 40 target days, 200 rows a day on side 1; spills only on day 30 onwards.
    tday = np.repeat(np.arange(40), 200)
    side = np.ones(len(tday))
    y = (tday >= 30).astype(float)
    for k in (0, 2):
        p = m.trailing_chance(side, y, tday, k)
        issue = tday - k
        # rows whose issue day is 30 or earlier have seen no spill day: chance is 0.5 / (n + 1)
        early = (issue <= 30) & np.isfinite(p)
        n = np.clip(issue[early], 0, 28) * 200
        np.testing.assert_allclose(p[early], 0.5 / (n + 1.0))
        # no rows before the issue day: no chance
        assert np.isnan(p[issue <= 0]).all()
        # the window is 28 days: issue day 31 sees days 3..30, one spill day
        r = np.flatnonzero(issue == 31)[0]
        np.testing.assert_allclose(p[r], (200 + 0.5) / (28 * 200 + 1.0))


def test_trailing_chance_floor_and_sides():
    tday = np.repeat(np.arange(5), 60)
    side = np.tile(np.r_[np.ones(30), np.zeros(30)], 5)
    y = np.zeros(len(tday))
    p = m.trailing_chance(side, y, tday, 0)
    # 30 rows a day per side: under 100 until four earlier days (120 rows)
    assert np.isnan(p[tday <= 3]).all()
    assert np.isfinite(p[tday == 4]).all()
    side[0] = np.nan
    assert np.isnan(m.trailing_chance(side, y, tday, 0)[0])


def test_persistence_reads_issue_time_and_two_days_before():
    lst = m.lst
    day0 = lst.DAY0
    ev = pd.DataFrame({"site_id": ["A", "B"],
                       "event_start": [day0 + pd.Timedelta(days=400, hours=3), day0 + pd.Timedelta(days=399, hours=23)],
                       "event_end": [day0 + pd.Timedelta(days=400, hours=4), day0 + pd.Timedelta(days=402, hours=1)]})
    st = m.lsb.Status2026(ev, pd.Index(["A", "B", "C"]), {"A", "B", "C"}, {"A", "B", "C"})
    sites = pd.Series(["A", "A", "A", "A", "B", "B", "C"])
    days = pd.Series([day0 + pd.Timedelta(days=d) for d in (401, 402, 403, 400, 402, 404, 401)])
    got = m.persistence_side(st, sites, days, 0)
    # A spilled on day 400: active on days 401 and 402 (in the 48 h before), not 403, not 400 itself (issue 00:00)
    # B ran through 00:00 of days 400-402: active at issue on 402; day 404 sees days 402-403 (402 touched)
    np.testing.assert_array_equal(got, [1, 1, 0, 0, 1, 1, 0])
    assert m.persistence_side(st, sites, days, 2)[1] == 0   # A, day 402 at lead 2: issue day 400, days 398-399 quiet
