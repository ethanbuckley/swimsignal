"""Counts of overflows that carry weight, and levels from the score shown (23 Oct 2026).

1. At Windermere, Waterhead, Grasmere WwTW's weight is 0.00045 (0% reach) but it was counted in "the 4
   overflows upstream" and in the expected spills. forecast.weighted_here leaves out an overflow whose 3 dp
   weight is under transport.COUNT_WEIGHT; upstream_summary says how many (too_far) and, for one, which.
2. A risk of 0.1497 was labelled low beside a shown 15. risk_label now goes by the score shown. The same
   table is in tests/site_weighted_counts.test.cjs, for the page and click-anywhere."""

import numpy as np
import pandas as pd
import pytest

from dipcast.model.forecast import live_counts, too_far, weighted_here
from dipcast.model.transport import COUNT_WEIGHT, risk_label, shown_score

# risk, the score shown (spots.json's 3 dp x 100, rounded as the page rounds), the level
LEVELS = [(0.1449, 14, "low"), (0.1450, 14, "low"), (0.146, 15, "moderate"), (0.149, 15, "moderate"), (0.1497, 15, "moderate"),
          (0.15, 15, "moderate"), (0.394, 39, "moderate"), (0.3949, 40, "high"), (0.3950, 40, "high"), (0.40, 40, "high"),
          (0.694, 69, "high"), (0.6950, 70, "very high"), (0.70, 70, "very high")]


@pytest.mark.parametrize("r,score,level", LEVELS)
def test_the_label_goes_by_the_score_the_page_shows(r, score, level):
    assert shown_score(r) == score
    assert risk_label(r) == level


def test_live_examples_from_23_oct_2026():
    # Waterhead, Sun 25 Oct (the 10:20 build) and Tue 27 Oct (16:20); Millerground, Tue 27 Oct (10:20).
    assert risk_label(0.1497) == risk_label(0.149) == "moderate"
    assert risk_label(0.0) == "low" and risk_label(0.9) == "very high"


def _ov(weights, status=None):
    n = len(weights)
    return pd.DataFrame({"site_id": [f"S{i}" for i in range(n)], "site_name": [f"Site {i}" for i in range(n)],
                         "company": "United Utilities", "weight": weights, "has_live": True,
                         "status": status if status is not None else [0] * n}, index=range(10, 10 + n))


def test_an_overflow_with_no_weight_here_is_not_counted():
    assert COUNT_WEIGHT == 0.005
    assert weighted_here(_ov([0.184, 0.101, 0.092, 0.00045])).tolist() == [True, True, True, False]
    # By the 3 dp weight the page shows: 0.0046 shows as 0.005, 1% reach, and counts; 0.0044 shows as 0%.
    assert weighted_here(_ov([0.3, 0.0044, 0.0046])).tolist() == [True, False, True]
    # None with weight: all count, as before (what to say there is not decided: review task G2).
    assert weighted_here(_ov([0.001, 0.0])).tolist() == [True, True]
    assert weighted_here(pd.DataFrame()).tolist() == []


def test_upstream_summary_names_one_left_out_and_counts_more():
    ov = _ov([0.184, 0.101, 0.092, 0.00045])
    assert too_far(ov, weighted_here(ov)) == {"too_far": 1, "too_far_overflow": {"site_id": "S3", "site_name": "Site 3", "company": "United Utilities"}}
    ov = _ov([0.119, 0.058, 0.001, 0.001, 0.0, 0.0])
    assert too_far(ov, weighted_here(ov)) == {"too_far": 4}
    ov = _ov([0.2, 0.3])
    assert too_far(ov, weighted_here(ov)) == {}


def test_right_now_counts_leave_out_an_overflow_with_no_weight():
    # The third is discharging but carries no weight here; the fourth stopped lately (a contribution above 0).
    ov = _ov([0.2, 0.1, 0.0004, 0.001], status=[0, 0, 1, 0])
    contrib = pd.Series([0.0, 0.0, 0.0004, 1e-6], index=ov.index)
    before = live_counts(ov, contrib)
    assert before["discharging_upstream"] == 1 and before["recent_upstream"] == 1 and before["monitored_upstream"] == 4
    here = weighted_here(ov)
    after = live_counts(ov[here], contrib[here])
    assert after["discharging_upstream"] == 0 and after["recent_upstream"] == 0 and after["monitored_upstream"] == 2
    # The expected spills sum the same rows.
    p = np.array([[0.6, 0.6], [0.2, 0.2], [0.8, 0.8], [0.5, 0.5]])
    assert np.nansum(p[here], axis=0).tolist() == pytest.approx([0.8, 0.8])
