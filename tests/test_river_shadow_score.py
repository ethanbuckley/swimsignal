"""scripts/river_rises_eval/shadow_score.py on synthetic logger records: inputs only from records made by the issue
time, the site's measure order, stale readings, radar hours only once every composite was listed, no score before
the read date."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from river_rises_eval import shadow_score as ss

FM = "http://environment.data.gov.uk/flood-monitoring/id/measures/"


def _record(issue, items, keys=(), status=200):
    return {"schema": "swimsignal.river-shadow.hour", "version": 1, "issue": issue,
            "ea": {"status": status, "error": None, "items": items},
            "radar": {"status": 200, "error": None, "keys": [{"key": k, "etag": "e", "last_modified": issue} for k in keys]}}


def _write(tmp_path, recs):
    for r in recs:
        (tmp_path / f"{r['issue'].replace(':', '-')}.json").write_text(json.dumps(r))
    (tmp_path / "keys.json").write_text(json.dumps([{"name": "h/x"}]))   # the export's listing: skipped


def _key(t):
    return f"radar/{t:%Y/%m/%d}/{t:%Y%m%d%H%M}_ODIM_ng_radar_rainrate_composite_1km_UK.h5"


def test_records_load_and_other_files_are_skipped(tmp_path):
    _write(tmp_path, [_record("2026-12-01T10:00:00Z", [{"measure": FM + "A-m", "dateTime": "2026-12-01T09:45:00Z", "value": 1.0}])])
    rd, rk, hours = ss.load_records(tmp_path)
    assert len(rd) == 1 and len(hours) == 1 and rk.empty


def test_a_late_run_keeps_nothing_timed_after_its_issue_hour(tmp_path):
    r = _record("2026-12-01T12:00:00Z", [{"measure": FM + "A-m", "dateTime": "2026-12-01T11:45:00Z", "value": 1.0},
                                         {"measure": FM + "B-m", "dateTime": "2026-12-01T12:15:00Z", "value": 2.0}])
    r["fetched_at"] = "2026-12-01T12:20:00Z"
    r["radar"]["keys"] = [{"key": _key(pd.Timestamp("2026-12-01 11:00", tz="UTC")), "etag": "e", "last_modified": "2026-12-01T11:05:30Z"},
                          {"key": _key(pd.Timestamp("2026-12-01 12:00", tz="UTC")), "etag": "e", "last_modified": "2026-12-01T12:05:30Z"}]
    _write(tmp_path, [r])
    rd, rk, hours = ss.load_records(tmp_path)
    assert rd["measure"].tolist() == [FM + "A-m"] and len(rk) == 1 and hours["late_min"].iloc[0] == 20


def test_inputs_come_from_the_record_at_t_and_t_minus_k_only():
    issues = pd.date_range("2026-12-01 10:00", periods=4, freq="1h", tz="UTC")
    rows = []
    for i, t in enumerate(issues):
        rows.append({"issue": t, "measure": "https://x/" + "A-m", "time": t - pd.Timedelta(minutes=30), "value": 1.0 + 0.1 * i})
    rd = pd.DataFrame(rows)
    out = ss.gauge_inputs(rd, FM + "A-m", 0.0, 1.0, issues, (1, 3), "spot")
    assert np.isnan(out["spot_rise1"][0]) and out["spot_rise1"][1] == pytest.approx(0.1)   # no record at t - 1 h for the first
    assert out["spot_rise3"][3] == pytest.approx(0.3) and np.isnan(out["spot_rise3"][2])
    assert out["spot_index"][2] == pytest.approx(1.2)


def test_a_stale_reading_does_not_count_for_a_rise_but_does_for_the_index():
    t = pd.Timestamp("2026-12-01 12:00", tz="UTC")
    rd = pd.DataFrame([{"issue": t, "measure": FM + "A-m", "time": t - pd.Timedelta(hours=5), "value": 2.0},
                       {"issue": t - pd.Timedelta(hours=1), "measure": FM + "A-m", "time": t - pd.Timedelta(hours=5), "value": 2.0}])
    out = ss.gauge_inputs(rd, FM + "A-m", 0.0, 1.0, pd.DatetimeIndex([t]), (1,), "spot")
    assert np.isnan(out["spot_rise1"][0]) and out["spot_index"][0] == pytest.approx(2.0)


def test_the_sites_measure_order_falls_back_when_the_first_has_no_reading():
    t = pd.Timestamp("2026-12-01 12:00", tz="UTC")
    rd = pd.DataFrame([{"issue": t, "measure": FM + "A-mASD", "time": t, "value": 3.0}])
    v, _ = ss.as_of(rd, [FM + "A-m", FM + "A-mASD"], pd.DatetimeIndex([t]))
    assert v[0] == 3.0


def test_a_radar_hour_counts_only_when_all_five_composites_were_listed_by_then():
    t = pd.Timestamp("2026-12-01 12:00", tz="UTC")
    e = t - pd.Timedelta(hours=1)
    full = [e - pd.Timedelta(minutes=15 * k) for k in range(5)]
    rk = pd.DataFrame([{"issue": t, "valid": v, "key": _key(v), "etag": "e"} for v in full])
    assert e in ss.usable_rain_hours(rk, pd.DatetimeIndex([t]))[t]
    rk2 = rk[rk["valid"] != full[2]]
    assert e not in ss.usable_rain_hours(rk2, pd.DatetimeIndex([t]))[t]
    later = pd.DataFrame([{"issue": t + pd.Timedelta(hours=1), "valid": full[2], "key": _key(full[2]), "etag": "e"}])
    u = ss.usable_rain_hours(pd.concat([rk2, later]), pd.DatetimeIndex([t, t + pd.Timedelta(hours=1)]))
    assert e not in u[t] and e in u[t + pd.Timedelta(hours=1)]   # listed after t: usable only from the later issue


def test_an_hour_ending_after_t_minus_1h_is_never_used():
    t = pd.Timestamp("2026-12-01 12:00", tz="UTC")
    e = t
    rk = pd.DataFrame([{"issue": t, "valid": e - pd.Timedelta(minutes=15 * k), "key": "k", "etag": "e"} for k in range(5)])
    assert e not in ss.usable_rain_hours(rk, pd.DatetimeIndex([t]))[t]


def test_uptime_counts_records_and_the_longest_gap():
    hours = pd.DataFrame({"issue": pd.date_range(ss.WINDOW[0], periods=5, freq="1h"), "ea_ok": [True, False, False, True, True],
                          "radar_ok": True, "items": 90})
    u = ss.uptime(hours, ss.WINDOW[0], ss.WINDOW[0] + pd.Timedelta(hours=6))
    assert u["records"] == 5 and u["ea_ok"] == 3 and u["longest_gap_h"] == 2


def test_etag_check_refuses_changed_or_missing_files():
    rk = pd.DataFrame({"issue": [0, 1, 2], "valid": [0, 0, 0], "key": ["a", "a", "b"], "etag": ['"x"', '"x"', '"y"']})
    assert ss.etag_check(rk, pd.DataFrame({"key": ["a", "b"], "etag": ["x", "y"]}))["ok"]
    bad = ss.etag_check(rk, pd.DataFrame({"key": ["a"], "etag": ["z"]}))
    assert not bad["ok"] and bad["changed"] == ["a"] and bad["gone"] == ["b"]


def test_no_score_before_the_read_date(tmp_path):
    _write(tmp_path, [])
    if pd.Timestamp.now(tz="UTC") < ss.READ_ON:
        with pytest.raises(SystemExit, match="read on or after"):
            ss.main(["score", "--records", str(tmp_path), "--out", str(tmp_path / "o")])
