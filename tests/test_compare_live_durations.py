"""The helpers of scripts/compare_live_durations.py (docs/EVENT-RECORDS-2026-11.md, section 4)."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import compare_live_durations as c  # noqa: E402

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def _hist():
    return pd.DataFrame({
        "site_id": ["a", "a", "b", "c", "d", "e", "a"],
        "company": ["Wessex Water"] * 6 + ["Thames Water"],
        "latest_event_start": [T("2026-09-15 10:00"), T("2026-09-15 10:00"), T("2026-09-16 08:00"),
                               T("2026-09-17 00:00"), T("2026-09-18 00:00"), T("2026-09-01 00:00"),
                               T("2026-09-15 10:00")],
        "latest_event_end": [T("2026-09-15 11:00"), T("2026-09-15 11:00"), T("2026-09-16 09:00"),
                             T("2026-09-17 02:00"), T("2026-10-20 00:00"), T("2026-09-01 01:00"),
                             T("2026-09-15 11:00")],
    })


def test_live_spills_one_per_event_inside_the_window():
    sp = c.live_spills(_hist(), "Wessex Water", T("2026-09-12"), T("2026-10-18"))
    # a's two polls of one event count once; d ends after the cut-off; e starts before the window; the
    # Thames row is another company.
    assert sp["site_id"].tolist() == ["a", "b", "c"]


def test_each_class_and_the_length_difference():
    live = c.live_spills(_hist(), "Wessex Water", T("2026-09-12"), T("2026-10-18"))
    rec = pd.DataFrame({
        "site_id": ["a", "b", "c", "c", "z"],
        "event_start": [T("2026-09-15 10:00:30"), T("2026-09-16 08:00"), T("2026-09-17 00:00"),
                        T("2026-09-17 01:00"), T("2026-09-15 10:00")],
        "event_end": [T("2026-09-15 11:00"), T("2026-09-16 09:30"), T("2026-09-17 00:30"),
                      T("2026-09-17 02:00"), T("2026-09-15 11:00")],
    })
    out = c.match(live, rec).set_index("site_id")
    assert out.loc["a", "class"] == "same"                       # 30 s apart: within a minute
    assert out.loc["b", "class"] == "one, differs"
    assert out.loc["b", "diff_min"] == 30
    assert out.loc["c", "class"] == "split"
    assert out.loc["c", "record_events"] == 2
    assert out.loc["c", "record_min"] == 90 and out.loc["c", "record_span_min"] == 120
    assert out.loc["c", "diff_min"] == -30


def test_a_spill_the_record_lacks_and_an_event_the_feed_lacks():
    live = c.live_spills(_hist(), "Wessex Water", T("2026-09-12"), T("2026-10-18"))
    rec = pd.DataFrame({"site_id": ["a", "a"],
                        "event_start": [T("2026-09-15 10:00"), T("2026-09-20 10:00")],
                        "event_end": [T("2026-09-15 11:00"), T("2026-09-20 11:00")]})
    out = c.match(live, rec).set_index("site_id")
    assert out.loc["b", "class"] == "record lacks" and pd.isna(out.loc["b", "diff_min"])
    assert c.feed_lacks(live, rec, T("2026-09-12"), T("2026-10-18")) == 1   # a's 20 Sep event
    s = c.summary(c.match(live, rec))
    assert s["live_spills"] == 3 and s["same"] == 1 and s["record lacks"] == 2
    assert s["within_1_min"] == 1.0
