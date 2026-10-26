"""scripts/company_calibration.py: the fit and the stated conditions (docs/COMPANY-CALIBRATION-TEST-2026-11.md),
on synthetic rows, and the join of the scored rows to the forecast log's version stamps."""

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from company_calibration import (not_clearly_worse, shown_better, two_way_draws, two_way_interval, CANDIDATE_FROZEN_AT, NOT_IN_LOG, attach_stamps, available, candidate, check,
                                 fit_offsets, match_maps, offsets_document, window_end)

IDENTITY = {"leads": {str(k): {"iso_x": [0.0, 1.0], "iso_y": [0.0, 1.0]} for k in range(5)}}
HALF = {"leads": {str(k): {"iso_x": [0.0, 1.0], "iso_y": [0.0, 0.5]} for k in range(5)}}


def rows_of(company, ids, days, leads, p, y, issued=None):
    """Scored rows as the published file has them: one per overflow, day and lead."""
    out = []
    for sid, yy in zip(ids, y):
        for d in days:
            for k in leads:
                iss = issued or (pd.Timestamp(d) - pd.Timedelta(days=k)).strftime("%Y-%m-%dT07:00+01:00")
                out.append({"overflow_id": sid, "company": company, "day": d, "lead": k, "issued_at": iss,
                            "forecast_raw": p, "forecast_calibrated": p, "climatology": 0.01,
                            "observed": int(yy(d) if callable(yy) else yy)})
    return pd.DataFrame(out)


def days(start, n):
    return [(pd.Timestamp(start) + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def test_fit_uses_lead_0_before_the_window_and_leaves_united_utilities_out():
    fitting = days("2026-10-01", 20)
    r = pd.concat([
        rows_of("Thames Water", ["T1"], fitting + ["2026-10-26"], [0, 1], 0.05, [0]),
        rows_of("Thames Water", ["T2"], fitting, [0], 0.05, [1]),
        rows_of("United Utilities", ["U1"], fitting, [0], 0.05, [1]),
    ], ignore_index=True)
    fit = fit_offsets(r).set_index("overflow_id")
    assert set(fit.index) == {"T1", "T2"}
    assert fit.loc["T1", "days"] == 20                         # no lead 1, no window day
    assert fit.loc["T1", "e"] == pytest.approx(1.0)
    assert fit.loc["T1", "offset"] == pytest.approx(np.log(15 / 16))
    assert fit.loc["T2", "offset"] == pytest.approx(np.log(35 / 16))


def test_fit_clips_the_model_chance_as_predict_pooled_does():
    r = rows_of("Wessex Water", ["W1"], days("2026-10-01", 10), [0], 0.0, [0])
    fit = fit_offsets(r)
    assert fit["e"].iloc[0] == pytest.approx(10 * 1e-4)


def test_offsets_document_round_trips_the_fit():
    r = rows_of("Southern Water", ["S1", "S2"], days("2026-10-01", 5), [0], 0.1, [0, 1])
    doc = offsets_document(fit_offsets(r), "abc", ["m1"])
    assert doc["prior_strength"] == 15.0 and doc["spill_stamps"] == ["m1"]
    assert doc["offsets"]["S2"]["n"] == 5 and doc["offsets"]["S2"]["days"] == 5
    assert doc["first_day"] == "2026-10-01" and doc["last_day"] == "2026-10-05"


def test_maps_are_matched_per_issue_day():
    a = rows_of("Anglian Water", ["A1"], ["2026-10-27"], [0], 0.2, [0], issued="2026-10-27T07:00+00:00")
    b = rows_of("Anglian Water", ["A1"], ["2026-10-28"], [0], 0.2, [0], issued="2026-10-28T07:00+00:00")
    b["forecast_calibrated"] = 0.1                              # made with HALF
    c = rows_of("Anglian Water", ["A1"], ["2026-10-29"], [0], 0.2, [0], issued="2026-10-29T07:00+00:00")
    c["forecast_calibrated"] = 0.15                             # neither map
    which = match_maps(pd.concat([a, b, c], ignore_index=True), [IDENTITY, HALF])
    assert list(which) == [0, 1, -1]


def test_candidate_is_the_published_forecast_with_no_offset_and_moves_on_the_odds_scale():
    r = rows_of("Yorkshire Water", ["Y1", "Y2"], ["2026-10-27"], [0, 2], 0.2, [0, 0])
    which = np.zeros(len(r), dtype=int)
    assert np.allclose(candidate(r, {}, [IDENTITY], which), 0.2)
    got = candidate(r, {"Y1": np.log(2.0)}, [IDENTITY, HALF], which)
    odds = 2 * 0.2 / 0.8
    assert np.allclose(got[r["overflow_id"] == "Y1"], odds / (1 + odds))
    assert np.allclose(got[r["overflow_id"] == "Y2"], 0.2)
    got = candidate(r, {"Y1": np.log(2.0)}, [IDENTITY, HALF], np.ones(len(r), dtype=int))
    assert np.allclose(got[r["overflow_id"] == "Y1"], 0.5 * odds / (1 + odds))


def test_a_new_spill_model_cuts_the_window_and_a_missing_log_row_does_not():
    r = pd.DataFrame({"day": ["2026-10-26", "2026-11-05", "2026-11-10"], "spill": ["m1", NOT_IN_LOG, "m2"]})
    assert window_end(r, "m1", "2026-10-26", "2026-11-22") == "2026-11-09"
    assert window_end(r.iloc[:2], "m1", "2026-10-26", "2026-11-22") == "2026-11-22"


def window_rows(spill_rate_of, p=0.05, n_sites=40, seed=0):
    """Four weeks at two companies plus United Utilities. Overflows 0-9 of each company spill on
    `spill_rate_of(i)` of days; the rest never."""
    rng = np.random.default_rng(seed)
    out = []
    for c in ["Thames Water", "Severn Trent Water", "United Utilities"]:
        ids = [f"{c[:3]}{i}" for i in range(n_sites)]
        y = [(lambda d, r=spill_rate_of(i): rng.random() < r) for i in range(n_sites)]
        out.append(rows_of(c, ids, days("2026-10-26", 28), [0, 1], p, y))
    r = pd.concat(out, ignore_index=True)
    r["spill"] = "m1"
    return r


def doc_for(offsets):
    return {"spill_stamps": ["m1"], "offsets": {k: {"offset": v} for k, v in offsets.items()},
            "fair_flat": {"Thames Water": 0.05}}


def test_offsets_that_follow_each_overflow_pass():
    r = window_rows(lambda i: 0.6 if i < 10 else 0.0)
    offs = {f"{c}{i}": (np.log(20.0) if i < 10 else np.log(0.1)) for c in ("Tha", "Sev") for i in range(40)}
    res = check(r, doc_for(offs), [IDENTITY], n_boot=200)
    assert res["changed"] == ["Severn Trent Water", "Thames Water"]
    assert res["verdict"].startswith("passes")
    t = res["by_company"]["Thames Water"]
    assert t["brier_candidate"] < t["brier_flat"] < t["brier_current"]
    assert t["interval_candidate_minus_current"][1] < 0
    assert res["united_utilities_rows"] == 40 * 28 * 2 and "United Utilities" not in res["by_company"]
    assert res["face_mae"] == pytest.approx(0.0) and res["rows_no_company"] == 0
    assert "brier_fair_flat" in t and "brier_fair_flat" not in res["by_company"]["Severn Trent Water"]


def test_beating_the_current_forecast_but_not_the_flat_rate_fails():
    # Every overflow spills on 1% of days; the forecast says 5%. A small cut helps but stays above the flat rate.
    r = window_rows(lambda i: 0.01, n_sites=400, seed=2)
    offs = {f"{c}{i}": np.log(0.95) for c in ("Tha", "Sev") for i in range(400)}
    res = check(r, doc_for(offs), [IDENTITY], n_boot=200)
    for c in res["changed"]:
        assert res["by_company"][c]["condition_1"] and not res["by_company"][c]["condition_2"]
    assert res["verdict"] == "fails: not adopted"


def test_a_company_with_no_offset_is_not_changed_and_not_judged():
    r = window_rows(lambda i: 0.6 if i < 10 else 0.0)
    offs = {f"Tha{i}": (np.log(20.0) if i < 10 else np.log(0.1)) for i in range(40)}
    res = check(r, doc_for(offs), [IDENTITY], n_boot=200)
    assert res["changed"] == ["Thames Water"]
    assert not res["by_company"]["Severn Trent Water"]["changed"]
    assert res["verdict"].startswith("passes")


def test_too_few_spills_extends_once_then_is_inconclusive():
    r = window_rows(lambda i: 0.02 if i < 2 else 0.0)
    offs = {f"Tha{i}": 0.1 for i in range(40)}
    res = check(r, doc_for(offs), [IDENTITY], n_boot=50)
    assert res["short"] == ["Thames Water"] and "extend" in res["verdict"]
    res = check(r, doc_for(offs), [IDENTITY], end="2026-12-06", n_boot=50)
    assert res["verdict"] == "inconclusive: not adopted"


def test_a_spill_model_change_early_in_the_window_stops_the_check():
    r = window_rows(lambda i: 0.6 if i < 10 else 0.0)
    r.loc[r["day"] >= "2026-11-02", "spill"] = "m2"
    res = check(r, doc_for({"Tha0": 1.0}), [IDENTITY], n_boot=50)
    assert res["verdict"].startswith("stopped: the spill model changed")


def test_unmatched_issue_days_over_a_tenth_stop_the_check():
    r = window_rows(lambda i: 0.6 if i < 10 else 0.0)
    r.loc[r["day"] <= "2026-10-31", "forecast_calibrated"] = 0.3
    res = check(r, doc_for({"Tha0": 1.0}), [IDENTITY], n_boot=50)
    assert res["verdict"].startswith("stopped: more than 10%")


def test_stamps_join_the_decision_forecast_of_each_scored_row(tmp_path):
    db = tmp_path / "log.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE forecast_overflows (site_id VARCHAR, issue_day DATE, target_day DATE, lead INTEGER, "
                "version VARCHAR, issued_at TIMESTAMPTZ, has_live BOOLEAN, rain_available BOOLEAN)")
    con.execute("INSERT INTO forecast_overflows VALUES "
                "('T1', '2026-10-27', '2026-10-27', 0, 'spill=aaa;cal=x', '2026-10-27 05:00:00+00', TRUE, TRUE), "
                # The latest by 08:00 local (GMT after 25 Oct) is the decision forecast; 09:00 is too late.
                "('T1', '2026-10-27', '2026-10-27', 0, 'spill=bbb;cal=x', '2026-10-27 07:30:00+00', TRUE, TRUE), "
                "('T1', '2026-10-27', '2026-10-27', 0, 'spill=ccc;cal=x', '2026-10-27 09:00:00+00', TRUE, TRUE), "
                "('T1', '2026-10-26', '2026-10-27', 1, NULL, '2026-10-26 06:00:00+00', TRUE, TRUE)")
    con.close()
    r = pd.DataFrame({"overflow_id": ["T1", "T1", "T2"], "day": ["2026-10-27"] * 3, "lead": [0, 1, 0]})
    got = attach_stamps(r, str(db), "2026-10-26", "2026-10-28")
    assert list(got["spill"]) == ["bbb", "unstamped", NOT_IN_LOG]


def test_a_row_with_no_company_is_counted_and_not_judged():
    r = window_rows(lambda i: 0.6 if i < 10 else 0.0)
    r.loc[r["overflow_id"] == "Tha0", "company"] = np.nan
    res = check(r, doc_for({"Tha0": 3.0}), [IDENTITY], n_boot=50)
    assert res["rows_no_company"] == 28 * 2
    assert res["changed"] == []


def test_forecasts_issued_before_the_freeze_are_left_out_of_the_window():
    """Amendment 1. Two overflows, the 28 window days, leads 0-4, each issued at 07:00 BST lead days before its
    target day: 280 rows, of which 12 were issued before the offsets were frozen (24 Oct 22:31:41 BST): target
    26 Oct at leads 2-4, 27 Oct at 3-4, 28 Oct at 4, for each overflow. The check scores the other 268."""
    r = rows_of("Thames Water", ["T1", "T2"], days("2026-10-26", 28), [0, 1, 2, 3, 4], 0.1, [0, 1])
    r["spill"] = "m1"
    res = check(r, doc_for({"T1": -1.0, "T2": 1.0}), [IDENTITY], n_boot=20)
    assert res["issued_before_freeze"] == {"cutoff": CANDIDATE_FROZEN_AT, "rows": 12, "by_lead": {2: 2, 3: 4, 4: 6}}
    assert res["by_company"]["Thames Water"]["rows"] == 268
    assert res["by_company"]["Thames Water"]["by_lead"][4]["rows"] == 2 * 28 - 6


def test_the_freeze_cutoff_is_strict_and_a_missing_issue_time_is_left_out():
    """At the cutoff to the second: issued at the freeze is out, a second later is in. Rows outside the window are
    never touched, and a row with no readable issue time counts as issued too early."""
    base = rows_of("Severn Trent Water", ["S1"], ["2026-10-27"], [3], 0.1, [0])
    at = base.assign(issued_at="2026-10-24T22:31:41+01:00")
    after = base.assign(issued_at="2026-10-24T22:31:42+01:00")
    blank = base.assign(issued_at="")
    before_window = rows_of("Severn Trent Water", ["S1"], ["2026-10-20"], [3], 0.1, [0])
    kept, left = available(pd.concat([at, after, blank, before_window], ignore_index=True), "2026-10-26", "2026-11-22")
    assert left == {"cutoff": CANDIDATE_FROZEN_AT, "rows": 2, "by_lead": {3: 2}}
    assert sorted(kept["issued_at"]) == sorted([after["issued_at"].iloc[0], before_window["issued_at"].iloc[0]])


# Amendment 2: the noise allowance.

def test_two_way_draws_count_every_overflow_and_week_and_repeat_with_the_seed():
    oc, wc = two_way_draws(7, 4, n_boot=100)
    assert oc.shape == (100, 7) and wc.shape == (100, 4)
    assert (oc.sum(1) == 7).all() and (wc.sum(1) == 4).all()
    oc2, wc2 = two_way_draws(7, 4, n_boot=100)
    assert (oc == oc2).all() and (wc == wc2).all()


def test_two_way_interval_of_a_constant_difference_is_that_constant():
    ov, wk = np.repeat(np.arange(5), 4), np.tile(np.arange(4), 5)
    oc, wc = two_way_draws(5, 4, n_boot=200)
    lo, hi = two_way_interval(np.full(20, -0.003), ov, wk, oc, wc)
    assert lo == pytest.approx(-0.003) and hi == pytest.approx(-0.003)


def test_the_two_rules_at_their_edges():
    assert not_clearly_worse(1.005, 1.0, [-0.1, 0.2])            # within 1%, interval spans zero
    assert not not_clearly_worse(1.02, 1.0, [-0.1, 0.2])         # more than 1% above
    assert not not_clearly_worse(0.9, 1.0, [0.01, 0.2])          # interval wholly above zero
    assert shown_better(0.9, 1.0, [-0.2, -0.01])
    assert not shown_better(0.9, 1.0, [-0.2, 0.01])              # a gain the interval does not show


def good_forecast_rows():
    """Overflows 0-9 spill on 60% of days and are forecast 0.6; the rest never spill and are forecast 0.01."""
    r = window_rows(lambda i: 0.6 if i < 10 else 0.0)
    i = r["overflow_id"].str[3:].astype(int)
    r["forecast_raw"] = np.where(i < 10, 0.6, 0.01)
    r["forecast_calibrated"] = r["forecast_raw"]
    return r


def test_a_gain_by_a_hair_is_not_shown_and_fails():
    r = good_forecast_rows()
    rng = np.random.default_rng(3)
    offs = {f"{c}{i}": float(rng.choice([-0.002, 0.002])) for c in ("Tha", "Sev") for i in range(40)}
    res = check(r, doc_for(offs), [IDENTITY], n_boot=300)
    assert res["changed"] == ["Severn Trent Water", "Thames Water"]
    assert res["pooled"]["better_than_flat"]                        # a good forecast beats the flat rate
    assert not res["pooled"]["better_than_current"]
    assert res["clearly_worse"] == []
    assert res["verdict"] == "fails: not adopted"
    assert res["verdict_original"] in ("passes", "fails")          # still reported


def test_a_company_clearly_worse_blocks_adoption_whatever_the_pooled_gain():
    r = window_rows(lambda i: 0.6 if i < 10 else 0.0)
    offs = {f"Tha{i}": (np.log(20.0) if i < 10 else np.log(0.1)) for i in range(40)}
    offs.update({f"Sev{i}": np.log(5.0) for i in range(10, 40)})    # raises overflows that never spill
    res = check(r, doc_for(offs), [IDENTITY], n_boot=300)
    assert res["clearly_worse"] == ["Severn Trent Water"]
    assert not res["by_company"]["Severn Trent Water"]["no_worse_than_current"]
    assert res["by_company"]["Thames Water"]["no_worse_than_current"]
    assert res["verdict"] == "fails: not adopted"


def test_the_passing_case_passes_the_amended_rules_too():
    r = window_rows(lambda i: 0.6 if i < 10 else 0.0)
    offs = {f"{c}{i}": (np.log(20.0) if i < 10 else np.log(0.1)) for c in ("Tha", "Sev") for i in range(40)}
    res = check(r, doc_for(offs), [IDENTITY], n_boot=300)
    p = res["pooled"]
    assert p["better_than_current"] and p["better_than_flat"] and res["clearly_worse"] == []
    assert p["rows"] == sum(res["by_company"][c]["rows"] for c in res["changed"])
    assert res["verdict_original"] == "passes" and res["verdict"].startswith("passes")
