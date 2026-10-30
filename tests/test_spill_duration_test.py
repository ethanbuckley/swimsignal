"""The helpers of scripts/spill_duration_test.py (docs/SPILL-DURATION-TEST-2026-11.md)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import spill_duration_test as m  # noqa: E402

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def _events(rows):
    return pd.DataFrame(rows, columns=["site_id", "company", "event_start", "event_end"]).assign(
        event_start=lambda d: pd.to_datetime(d["event_start"], utc=True),
        event_end=lambda d: pd.to_datetime(d["event_end"], utc=True))


def test_merge_joins_overlaps_and_short_gaps_only():
    ev = _events([
        ("a", "X", "2024-03-01 10:00", "2024-03-01 11:00"),
        ("a", "X", "2024-03-01 10:30", "2024-03-01 12:00"),   # overlaps
        ("a", "X", "2024-03-01 12:59", "2024-03-01 13:30"),   # 59 min after: same spill
        ("a", "X", "2024-03-01 14:30", "2024-03-01 15:00"),   # exactly an hour after: a new spill
        ("b", "X", "2024-03-01 12:10", "2024-03-01 12:20"),   # another overflow never joins
    ])
    sp = m.merge_spells(ev, 1.0)
    a = sp[sp["site_id"] == "a"].reset_index(drop=True)
    assert list(a["start"]) == [T("2024-03-01 10:00"), T("2024-03-01 14:30")]
    assert list(a["end"]) == [T("2024-03-01 13:30"), T("2024-03-01 15:00")]
    assert (sp["site_id"] == "b").sum() == 1


def test_merge_takes_the_longest_end_when_an_event_sits_inside_another():
    ev = _events([("a", "X", "2024-03-01 10:00", "2024-03-01 20:00"),
                  ("a", "X", "2024-03-01 11:00", "2024-03-01 12:00"),
                  ("a", "X", "2024-03-01 20:30", "2024-03-01 21:00")])
    sp = m.merge_spells(ev, 1.0)
    assert len(sp) == 1 and sp.loc[0, "end"] == T("2024-03-01 21:00")


def test_issue_rows_are_the_whole_hours_a_spill_runs():
    sp = pd.DataFrame({"site_id": ["a"], "company": ["X"],
                       "start": [T("2024-03-01 10:20")], "end": [T("2024-03-01 13:00")]})
    r = m.issue_rows(sp, T("2024-01-01"), T("2025-01-01"))
    assert list(r["t"]) == [T("2024-03-01 11:00"), T("2024-03-01 12:00")]   # 13:00 is the end, so not running
    assert np.allclose(r["elapsed_h"], [40 / 60, 100 / 60])
    assert np.allclose(r["remaining_h"], [2.0, 1.0])


def test_issue_rows_start_on_the_hour_counts_and_the_cap_and_window_hold():
    sp = pd.DataFrame({"site_id": ["a", "b"], "company": ["X", "X"],
                       "start": [T("2024-03-01 10:00"), T("2024-12-30 22:00")],
                       "end": [T("2024-03-10 00:00"), T("2025-01-02 00:00")]})
    r = m.issue_rows(sp, T("2024-01-01"), T("2024-12-31"), cap_h=5)
    a, b = r[r["spell"] == 0], r[r["spell"] == 1]
    assert a["t"].min() == T("2024-03-01 10:00") and a["elapsed_h"].min() == 0
    assert len(a) == 5 and a["elapsed_h"].max() == 4          # elapsed 0..4, under the 5 h cap
    assert list(b["t"]) == [T("2024-12-30 22:00"), T("2024-12-30 23:00")]   # the window ends at 31 Dec 00:00


def test_issue_rows_keep_the_true_elapsed_time_for_a_spill_begun_before_the_window():
    sp = pd.DataFrame({"site_id": ["a"], "company": ["X"],
                       "start": [T("2024-12-31 20:00")], "end": [T("2025-01-01 03:00")]})
    r = m.issue_rows(sp, T("2025-01-01"), T("2025-12-31"))
    assert r["t"].min() == T("2025-01-01 00:00") and r["elapsed_h"].min() == 4


def test_labels_say_still_running_strictly_after_each_horizon():
    r = pd.DataFrame({"remaining_h": [0.5, 1.0, 3.5, 30.0]})
    y = m.labels(r)
    assert y.shape == (4, len(m.HORIZONS))
    assert y[0].tolist() == [0, 0, 0, 0, 0]
    assert y[1].tolist() == [0, 0, 0, 0, 0]          # ends exactly at +1 h: not running then
    assert y[2].tolist() == [1, 1, 0, 0, 0]
    assert y[3].tolist() == [1, 1, 1, 1, 1]


def test_empirical_baseline_uses_the_cell_and_falls_back_to_the_company():
    company = np.array(["X", "X", "X", "Y"])
    ebin = np.array([0, 0, 3, 0])
    y = np.array([[1, 0, 0, 0, 0], [0, 0, 0, 0, 0], [1, 1, 1, 1, 1], [1, 1, 0, 0, 0]], np.float32)
    tab = m.empirical_survival(company, ebin, y)
    p = m.predict_empirical(tab, np.array(["X", "Y"]), np.array([0, 5]))
    assert np.allclose(p[0], [0.5, 0, 0, 0, 0])
    assert np.allclose(p[1], [1, 1, 0, 0, 0])        # Y has no bin 5: its all-bins figure


def test_monotone_never_rises_with_the_horizon():
    p = m.monotone(np.array([[0.9, 0.95, 0.5, 0.6, 0.1]]))
    assert p.tolist() == [[0.9, 0.9, 0.5, 0.5, 0.1]]


def test_history_hours_counts_only_earlier_spills_of_the_same_overflow_in_the_week():
    sp = pd.DataFrame({"site_id": ["a", "a", "a", "b"], "company": ["X"] * 4,
                       "start": [T("2024-03-01 00:00"), T("2024-03-07 12:00"), T("2024-03-08 06:00"), T("2024-03-08 00:00")],
                       "end": [T("2024-03-01 10:00"), T("2024-03-07 14:00"), T("2024-03-08 07:00"), T("2024-03-08 05:00")]})
    h = m.history_hours(sp)
    assert h[0] == 0
    assert np.isclose(h[1], 10.0)                      # 7 Mar 12:00 looks back to 29 Feb 12:00 (a leap year)
    # 8 Mar 06:00 looks back to 1 Mar 06:00: 4 h of the first spill and 2 h of the second
    assert np.isclose(h[2], 6.0)
    assert h[3] == 0                                   # overflow b has no earlier spill


def test_ece_is_zero_when_each_bin_matches():
    p = np.array([0.05, 0.05, 0.95, 0.95])
    y = np.array([0, 0, 1, 1], float)
    assert m.ece(p, y) < 0.06


def test_active_at_is_false_inside_a_pause_that_merging_joins():
    # The reviewer's case: stops at 10:40, restarts at 11:10. Joined into one spill, but not discharging at 11:00.
    ev = _events([("a", "X", "2024-03-01 10:00", "2024-03-01 10:40"),
                  ("a", "X", "2024-03-01 11:10", "2024-03-01 12:30"),
                  ("b", "X", "2024-03-01 10:30", "2024-03-01 11:30")])
    assert len(m.merge_spells(ev, 1.0).query("site_id == 'a'")) == 1
    raw = m.merge_spells(ev, 0.0)
    t = pd.to_datetime(["2024-03-01 10:00", "2024-03-01 11:00", "2024-03-01 12:00", "2024-03-01 11:00", "2024-03-01 12:30"], utc=True)
    got = m.active_at(raw, np.array(["a", "a", "a", "b", "a"]), t.to_numpy())
    assert got.tolist() == [True, False, True, True, False]


def test_active_at_unknown_overflow_is_never_discharging():
    raw = m.merge_spells(_events([("a", "X", "2024-03-01 10:00", "2024-03-01 11:00")]), 0.0)
    t = pd.to_datetime(["2024-03-01 10:30"], utc=True).to_numpy()
    assert m.active_at(raw, np.array(["zz"]), t).tolist() == [False]
