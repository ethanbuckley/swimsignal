"""The helpers of scripts/spill_duration_calibration_test.py (docs/SPILL-DURATION-CALIBRATION-TEST-2026-11.md)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import spill_duration_calibration_test as m  # noqa: E402
import spill_duration_test as base  # noqa: E402

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def _raw(rows):
    ev = pd.DataFrame(rows, columns=["site_id", "company", "event_start", "event_end"])
    ev["event_start"] = pd.to_datetime(ev["event_start"], utc=True)
    ev["event_end"] = pd.to_datetime(ev["event_end"], utc=True)
    return base.merge_spells(ev, 0.0)


def test_quarter_folds_run_0_to_7_over_2024_25():
    t = pd.Series(pd.to_datetime(["2024-01-01 00:00", "2024-03-31 23:00", "2024-04-01 00:00", "2025-12-30 00:00"], utc=True))
    assert m.quarter_fold(t).tolist() == [0, 0, 1, 7]


def test_calibrators_map_each_company_and_keep_survival_falling():
    rng = np.random.default_rng(0)
    n = 4000
    company = np.where(np.arange(n) % 2 == 0, "A", "B")
    p = np.sort(rng.uniform(0, 1, (n, len(m.HORIZONS))), axis=1)[:, ::-1].copy()   # falling across horizons
    y = (rng.uniform(0, 1, p.shape) < p * 0.5).astype(np.float32)                    # true chance is half the forecast
    cal = m.fit_calibrators(p, y, company)
    q = m.apply_calibrators(cal, p, company)
    assert (np.diff(q, axis=1) <= 1e-12).all()
    assert abs(q[:, 0].mean() - y[:, 0].mean()) < 0.02                              # pulled down to the outcomes
    keep = m.apply_calibrators({}, p, company)                                      # no calibrator: raw kept
    assert np.allclose(keep, base.monotone(p))


def test_gate_needs_the_high_forecasts_to_come_true_less_often():
    j = m.HORIZONS.index(24)
    oof = np.zeros((10, len(m.HORIZONS)))
    oof[:, j] = [0.9] * 5 + [0.1] * 5
    y = np.zeros_like(oof)
    y[:4, j] = 1                                  # 4 of the 5 at 0.9 came true: 0.8, a gap of 0.1
    ok, gap, n = m.gate(oof, y, j)
    assert ok and np.isclose(gap, 0.1) and n == 5
    y[:5, j] = 1                                  # all 5 came true: forecast too low, not too sharp
    assert not m.gate(oof, y, j)[0]


def test_raw_index_says_running_and_start():
    idx = m.RawIndex(_raw([("a", "X", "2026-03-01 10:00", "2026-03-01 10:40"),
                           ("a", "X", "2026-03-01 11:10", "2026-03-01 14:00")]))
    th = m.RawIndex._h(pd.Series(pd.to_datetime(["2026-03-01 10:30", "2026-03-01 11:00", "2026-03-01 12:00"], utc=True)))
    run, start = idx.lookup(np.array(["a", "a", "a"]), th)
    assert run.tolist() == [True, False, True]
    assert np.isnan(start[1]) and np.isclose(th[2] - start[2], 50 / 60)


def test_poll_elapsed_breaks_at_a_pause_over_an_hour_mark_and_ignores_one_between_marks():
    raw = _raw([("a", "X", "2026-03-01 08:20", "2026-03-01 10:40"),    # pause 10:40-11:10 spans the 11:00 mark
                ("a", "X", "2026-03-01 11:10", "2026-03-01 15:00"),
                ("b", "X", "2026-03-01 08:20", "2026-03-01 10:10"),    # pause 10:10-10:50 sits between marks
                ("b", "X", "2026-03-01 10:50", "2026-03-01 15:00")])
    idx = m.RawIndex(raw)
    t = pd.Series(pd.to_datetime(["2026-03-01 13:00", "2026-03-01 13:00"], utc=True))
    e = m.poll_elapsed(idx, np.array(["a", "b"]), t)
    assert np.isclose(e[0], 1 + 50 / 60)          # a: only back to 11:10, the true spill began 08:20
    assert np.isclose(e[1], 4 + 40 / 60)          # b: the 10:00 and 11:00 polls both saw a discharge, back to 08:20
