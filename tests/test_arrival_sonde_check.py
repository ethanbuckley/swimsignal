"""docs/ARRIVAL-TIME-SONDE-CHECK-2026-11.md: the rise, the quiet-rule events, the implied speed and the ledger,
on synthetic series. No file from the run and no request."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "arrival_sonde_check"))
import core  # noqa: E402
from ledger import Ledger  # noqa: E402

H = 60


def series(hours=200, base=0.10, seed=0):
    rng = np.random.default_rng(seed)
    return base + rng.normal(0, 0.004, hours * 4)


def test_horizon_is_distance_at_a_quarter_of_the_model_speed_within_6_and_72_hours():
    assert core.horizon_h(500) == 6.0
    assert core.horizon_h(5_400) == pytest.approx(30.0)
    assert core.horizon_h(30_000) == 72.0


def test_grid_drops_suspect_missing_and_out_of_range_and_keeps_the_last_duplicate():
    g0, x = core.to_grid([0, 15, 30, 30, 60, 75], [0.1, 0.2, 0.3, 0.4, 500.0, 0.6],
                         ["Good", "Suspect", "Good", "Unchecked", "Good", "Missing"])
    assert g0 == 0 and len(x) == 6
    assert x[0] == 0.1 and np.isnan(x[1]) and x[2] == 0.4 and np.isnan(x[3]) and np.isnan(x[4]) and np.isnan(x[5])


def test_a_sustained_rise_after_the_start_gives_its_lag_and_peak():
    x = series()
    t0 = 100 * H
    x[(100 + 3) * 4:(100 + 8) * 4] += 0.2          # 3 h after the start, for 5 h
    x[(100 + 5) * 4] += 0.3
    d = core.detect(0, x, t0, 24.0)
    assert d["status"] == "rise" and d["lag_h"] == 3.0 and d["peak_lag_h"] == 5.0
    assert d["theta"] == pytest.approx(d["b"] + max(0.05, 0.5 * d["b"], 3 * d["s"]))


def test_one_high_reading_is_not_a_rise():
    x = series()
    x[(100 + 3) * 4] += 0.5
    assert core.detect(0, x, 100 * H, 24.0)["status"] == "no rise"


def test_a_rise_that_begins_before_the_start_is_raised_before():
    x = series()
    x[(100 - 2) * 4:(100 + 6) * 4] += 0.2
    d = core.detect(0, x, 100 * H, 24.0)
    assert d["status"] == "raised before" and d["lag_h"] == -2.0


def test_a_rise_in_the_baseline_window_does_not_hide_a_later_one_but_a_gap_before_the_onset_does():
    x = series()
    x[(100 + 4) * 4:(100 + 9) * 4] += 0.2
    gap = x.copy()
    gap[(100 + 1) * 4:(100 + 2) * 4] = np.nan      # one hour missing before the onset
    assert core.detect(0, x, 100 * H, 24.0)["status"] == "rise"
    assert core.detect(0, gap, 100 * H, 24.0)["status"] == "gap"
    after = x.copy()
    after[(100 + 12) * 4:(100 + 14) * 4] = np.nan  # a gap after the onset does not matter
    assert core.detect(0, after, 100 * H, 24.0)["status"] == "rise"


def test_no_baseline_and_outside():
    x = series()
    thin = x.copy()
    thin[(100 - 30) * 4:(100 - 6) * 4:2] = np.nan
    thin[(100 - 30) * 4 + 1:(100 - 6) * 4:4] = np.nan      # 24 of 96 slots left
    assert core.detect(0, thin, 100 * H, 24.0)["status"] == "no baseline"
    assert core.detect(0, x, 10 * H, 24.0)["status"] == "outside"       # the baseline starts before the readings
    assert core.detect(0, x, 190 * H, 24.0)["status"] == "outside"      # the horizon ends after them


def test_the_stricter_rule_needs_a_bigger_rise_than_the_looser():
    x = series()
    x[(100 + 3) * 4:(100 + 8) * 4] += 0.04
    assert core.detect(0, x, 100 * H, 24.0, "looser")["status"] == "rise"
    assert core.detect(0, x, 100 * H, 24.0, "main")["status"] == "no rise"
    assert core.detect(0, x, 100 * H, 24.0, "stricter")["status"] == "no rise"


def spills(rows):
    return pd.DataFrame(rows, columns=["site_id", "start", "end", "d_m"])


def test_quiet_rule_keeps_a_start_only_after_48_hours_with_nothing_spilling_upstream():
    sp = spills([("a", 0, 30, 2000), ("b", 40 * H, 41 * H, 5000), ("a", 100 * H, 101 * H, 2000),
                 ("b", 100 * H, 102 * H, 5000), ("a", 149 * H, 150 * H, 2000), ("b", 200 * H, 201 * H, 5000)])
    ev = core.find_events(sp)
    # 0: first ever. 40 h: 39.5 h after a's end, not quiet. 100 h: 59 h after b's end; a and b start together and
    # a is nearer. 149 h: 47 h after b's end. 200 h: 50 h after a's end.
    assert list(ev["t0"]) == [0, 100 * H, 200 * H]
    assert list(ev["site_id"]) == ["a", "a", "b"]
    assert len(core.find_events(sp, quiet_h=24.0)) == 5


def test_others_in_window_is_what_separates_tier_a_from_tier_b():
    sp = spills([("a", 100 * H, 101 * H, 2000), ("b", 100 * H, 102 * H, 5000), ("a", 105 * H, 106 * H, 2000),
                 ("b", 300 * H, 301 * H, 5000)])
    assert list(core.others_in_window(sp, 100 * H, 11.1, "a")["site_id"]) == ["b"]      # Tier B
    assert core.others_in_window(sp, 300 * H, 27.8, "b").empty                           # Tier A: only its own


def test_implied_speed_is_distance_over_lag_for_one_overflow_and_the_first_arrival_for_several():
    assert core.implied_speed([0], [3600.0], 60) == pytest.approx(1.0)        # 3.6 km in 1 h
    # a: 7.2 km, started at 0. b: 1.8 km, started 1 h later. Onset at 2 h: a would need 1 m/s, b 0.5 m/s.
    assert core.implied_speed([0, 60], [7200.0, 1800.0], 120) == pytest.approx(0.5)
    v = core.implied_speed([0, 60], [7200.0, 1800.0], 120)
    assert min(0 * 60 + 7200 / v, 60 * 60 + 1800 / v) == pytest.approx(120 * 60)
    assert np.isnan(core.implied_speed([0], [1000.0], 0))


def test_model_window_is_start_plus_travel_to_end_plus_travel_with_15_minutes_grace():
    assert core.model_window(1.0, 2.0, 0.5) == "before"
    assert core.model_window(1.75, 2.0, 0.5) == "inside"
    assert core.model_window(2.75, 2.0, 0.5) == "inside"
    assert core.model_window(3.0, 2.0, 0.5) == "after"


def test_ledger_writes_every_request_stops_at_the_cap_and_counts_a_retry_twice(tmp_path):
    class R:
        def __init__(self, status):
            self.status_code, self.content = status, b"x"

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.status_code)

    answers = iter([R(200), R(503), R(200), R(200)])
    led = Ledger(tmp_path / "ledger.jsonl", cap=3, get=lambda url, params: next(answers), sleep=lambda s: None)
    led.request("u1", {"a": 1})
    led.request("u2", {})                       # 503, then 200: two lines
    rows = [json.loads(line) for line in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert [r["status"] for r in rows] == [200, 503, 200] and rows[0]["url"] == "u1" and rows[0]["start"].endswith("Z")
    with pytest.raises(SystemExit):
        led.request("u3", {})
    assert Ledger(tmp_path / "ledger.jsonl", cap=3).left() == 0


# Amendment 2: the same rules counted in the sonde's own reading interval.

def readings(step, hours=200, base=0.10, seed=0):
    tm = np.arange(0, hours * H, step, dtype=float)
    rng = np.random.default_rng(seed)
    return tm, base + rng.normal(0, 0.004, len(tm))


def test_valid_readings_keeps_the_last_duplicate_in_time_order_and_drops_bad_ones():
    tm, v = core.valid_readings([30, 0, 30, 60, 90], [0.3, 0.1, 0.4, 500.0, 0.6], ["Good", "Good", "Unchecked", "Good", "Suspect"])
    assert list(tm) == [0, 30] and list(v) == [0.1, 0.4]


@pytest.mark.parametrize("step", [15, 30, 60])
def test_amended_rise_is_found_at_each_reading_interval(step):
    tm, v = readings(step)
    v[(tm >= 103 * H) & (tm < 108 * H)] += 0.2
    d = core.detect_c(tm, v, 100 * H, 24.0)
    assert d["status"] == "rise" and d["c"] == step and d["lag_h"] == 3.0


@pytest.mark.parametrize("step", [30, 60])
def test_amended_one_high_reading_is_not_a_rise_and_two_in_a_row_are(step):
    tm, v = readings(step)
    one = v.copy(); one[tm == 103 * H] += 0.5
    assert core.detect_c(tm, one, 100 * H, 24.0)["status"] == "no rise"
    two = one.copy(); two[tm == 103 * H + step] += 0.5
    assert core.detect_c(tm, two, 100 * H, 24.0)["status"] == "rise"


def test_amended_rules_equal_the_stated_rules_at_a_15_minute_sonde():
    rng = np.random.default_rng(1)
    for trial in range(60):
        x = series(seed=trial)
        start = int(rng.integers(90 * 4, 125 * 4))
        x[start:start + int(rng.integers(1, 30))] += float(rng.uniform(0.02, 0.3))
        if trial % 3 == 0:
            k = int(rng.integers(60 * 4, 130 * 4)); x[k:k + int(rng.integers(1, 8))] = np.nan
        tm = np.arange(len(x), dtype=float) * 15
        ok = np.isfinite(x)
        a, b = core.detect(0, x, 100 * H, 24.0), core.detect_c(tm[ok], x[ok], 100 * H, 24.0)
        assert a["status"] == b["status"], trial
        assert a.get("lag_h") == b.get("lag_h") and a.get("peak_lag_h") == b.get("peak_lag_h"), trial


def test_amended_gap_and_baseline_scale_with_the_interval():
    tm, v = readings(60)
    v[(tm >= 104 * H) & (tm < 109 * H)] += 0.2
    drop = tm == 102 * H                                   # one hourly reading missing: two hours between readings
    assert core.detect_c(tm[~drop], v[~drop], 100 * H, 24.0)["status"] == "gap"
    keep = ~((tm >= 70 * H) & (tm < 83 * H))               # 11 of the 24 baseline readings left
    assert core.detect_c(tm[keep], v[keep], 100 * H, 24.0)["status"] == "no baseline"
    odd = np.arange(0, 200 * H, 120, dtype=float)          # a two-hourly sonde has no interval the rules know
    assert core.detect_c(odd, np.full(len(odd), 0.1), 100 * H, 24.0)["status"] == "no baseline"
