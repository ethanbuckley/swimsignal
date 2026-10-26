"""The helpers of scripts/measure_missing_event_end.py (docs/MISSING-EVENT-END-2026-10.md)."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import measure_missing_event_end as m  # noqa: E402

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
NaT = pd.NaT


def _hist():
    return pd.DataFrame({
        "site_id": ["a", "a", "b", "c"],
        "company": ["United Utilities"] * 4,
        "status": [1, 0, 0, 0],
        "status_start": [T("2026-10-01 08:00"), T("2026-10-01 10:00"), T("2026-10-01 09:00"), NaT],
        "latest_event_start": [T("2026-10-01 08:00"), NaT, NaT, NaT],
        "latest_event_end": [NaT, NaT, NaT, T("2026-10-01 07:00")],
        "fetched_at": [T("2026-10-01 08:30"), T("2026-10-01 11:00"), T("2026-10-01 11:00"), T("2026-10-01 11:00")],
    })


def test_asof_state_takes_the_last_row_begun_by_then():
    h = m.prepare_history(_hist())
    st = m.asof_state(h, T("2026-10-01 09:30"))
    assert st.loc["a", "status"] == 1 and st.loc["b", "status"] == 0
    assert st.loc["c", "latest_event_end"] == T("2026-10-01 07:00")   # begin from its end
    st = m.asof_state(h, T("2026-10-01 10:30"))
    assert st.loc["a", "status"] == 0 and st.loc["a", "prev_status"] == 1


def test_prev_status_skips_a_change_listed_twice():
    h = pd.DataFrame({
        "site_id": ["a"] * 3, "company": ["United Utilities"] * 3, "status": [1, 0, 0],
        "status_start": [T("2026-10-16 15:00"), T("2026-10-16 16:16:25"), T("2026-10-16 16:16:25.496")],
        "latest_event_start": [NaT] * 3, "latest_event_end": [NaT] * 3, "fetched_at": [T("2026-10-16 15:30")] * 3,
    })
    h = m.prepare_history(h)
    assert pd.isna(h["prev_status"].iloc[0]) and h["prev_status"].iloc[1:].tolist() == [1, 1]


def test_fill_missing_end_rules():
    h = m.prepare_history(_hist())
    st = m.asof_state(h, T("2026-10-01 12:00")).reset_index()
    a, b = m.fill_missing_end(st, "A"), m.fill_missing_end(st, "B")
    end = lambda d, s: d.set_index("site_id").loc[s, "latest_event_end"]  # noqa: E731
    assert end(a, "a") == T("2026-10-01 10:00") and end(b, "a") == T("2026-10-01 10:00")   # was discharging
    assert end(a, "b") == T("2026-10-01 09:00") and pd.isna(end(b, "b"))   # no sign of a spill: B leaves it
    assert end(a, "c") == T("2026-10-01 07:00")                            # had an end: unchanged
    assert m.fill_missing_end(st, "today") is st


def test_group_builds_splits_on_gaps():
    s = pd.Series([T("2026-10-01 10:00"), T("2026-10-01 10:03"), T("2026-10-01 11:00"), T("2026-10-01 10:01")])
    assert m.group_builds(s).tolist() == [0, 0, 1, 0]
