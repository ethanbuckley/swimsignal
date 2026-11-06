"""scripts/derwent_diagnosis.py (docs/DERWENT-WATER-DIAGNOSIS-2026-11.md): the spill-hour window, and the recorded
answer against the plan's rule. The run needs United Utilities' event file (not in git), so it is not repeated here."""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import derwent_diagnosis as d  # noqa: E402

REC = json.loads(d.OUT.read_text())


def _ev(rows):
    return pd.DataFrame([{"site_id": s, "event_start": pd.Timestamp(a, tz="UTC"), "event_end": pd.Timestamp(b, tz="UTC")}
                         for s, a, b in rows])


def test_spill_hours_clip_each_event_to_the_window_and_sum_overflows():
    ev = _ev([("A", "2025-07-01 00:00", "2025-07-01 10:00"), ("B", "2025-07-02 22:00", "2025-07-03 04:00"),
              ("C", "2025-07-02 00:00", "2025-07-02 05:00")])
    t = pd.Timestamp("2025-07-03 02:00", tz="UTC")
    assert d.spill_hours(ev, ["A", "B"], t, 1) == 4.0          # B clipped at the sample time; A outside the day
    assert d.spill_hours(ev, ["A", "B"], t, 3) == 14.0
    assert d.spill_hours(ev, ["C"], t, 3) == 5.0 and d.spill_hours(ev, ["X"], t, 3) == 0.0
    assert d.days_since(ev, ["A"], t) == round((t - pd.Timestamp("2025-07-01 10:00", tz="UTC")).total_seconds() / 86400, 2)


def test_recorded_answer_is_the_plans_not_explained():
    der = REC["rho"]["Derwent Water"]
    assert der["samples"] == 40 and der["over_900"] == 9
    rule_spills = any(der[w]["rho"] >= 0.3 and der[w]["ci95"][0] > 0 for w in ("30d", "60d"))
    season = REC["season_spill_hours_may_sep"]["Derwent Water"]
    assert not rule_spills and season["2025"] < season["2024"] and REC["dry_day_over_900_with_spill_7d"] < 2
    assert REC["upstream"]["ukd1101-45800"] == ["UUP00823", "UUP01690", "UUP01875"]
    for name in ("CONCENTRATION-STUDY-2026-11-atlas-rows.csv",):
        assert d.sha(d.ATLAS) == REC["inputs_sha256"][name]
    assert d.sha(d.EVID) == REC["inputs_sha256"]["ecoli_evidence.v1.json"]
    assert d.sha(d.TEMP) == REC["inputs_sha256"]["lake_temperature_obs.v1.json"]


def test_candidate_d_failed_as_recorded():
    s = json.loads((ROOT / "docs" / "LAKE-LINE-CANDIDATES-2026-11-season-scores.json").read_text())
    assert s["slope"] == "season" and s["protocol_commit"] == "d8063382"
    assert not any(s["checks"].values())
