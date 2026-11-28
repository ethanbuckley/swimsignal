"""docs/LAKE-AVERAGE-BASIS-CHECK-2026-11.md: the average-lake range is computed and logged but not shown; a spot on a
lake with sampled sites elsewhere shows that lake's level. Made-up rain only."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import lake_range as lr
from dipcast.model.ecoli import features

ROOT = Path(__file__).resolve().parents[1]
WATERHEAD, ULLSWATER, FELLFOOT = (54.41897, -2.96235), (54.544, -2.948), None


def X(r48=5.0):
    return features([r48, r48], [0.0, 0.0], [0.01, 0.01], [1.0, 1.0], [pd.Timestamp("2027-07-15")] * 2)


def test_the_average_lake_is_withheld_and_a_sampled_lake_keeps_its_range():
    out = lr.ranges(*ULLSWATER, X())
    assert out["basis"] == "average lake" and lr.shown(*ULLSWATER, X(), out) is None
    m = lr.model()
    s = m["sites"]["ukd1203-45625"]
    own = lr.ranges(s["lat"], s["lon"], X())
    assert lr.shown(s["lat"], s["lon"], X(), own) is own, "a lake with its own level is unchanged"
    assert lr.shown(*ULLSWATER, X(), None) is None


def test_waterhead_takes_windermeres_level_from_its_four_sites():
    out = lr.ranges(*WATERHEAD, X())
    assert out["basis"] == "average lake", "the logged figure is still the average lake's"
    sh = lr.shown(*WATERHEAD, X(), out)
    assert sh["basis"] == lr.SAME_LAKE_BASIS and len(sh["lake_sites"]) == 4
    assert sh["low"][0] < sh["median"][0] < sh["high"][0]
    assert not np.allclose(sh["median"], out["median"])
    assert np.isnan(sh["usual"]).all()
    nan = X(float("nan"))
    assert np.isnan(lr.shown(*WATERHEAD, nan, lr.ranges(*WATERHEAD, nan))["median"]).all(), "a missing input shows nothing"


def test_every_same_lake_site_is_in_lake_range_v1():
    m = lr.model()
    for sid, (_, sites) in lr.SAME_LAKE.items():
        assert all(s in m["sites"] for s in sites), sid


def test_the_check_met_the_rule_it_was_planned_with():
    r = json.loads((ROOT / "docs" / "lake-average-check" / "results.json").read_text())
    assert not (0.70 <= r["A_overall"] <= 0.90 and r["A_lowest"] >= 0.60), "A failed: the average lake is withheld"
    assert not (0.70 <= r["B_overall"] <= 0.90 and r["B_lowest"] >= 0.60), "B failed too"
    assert 0.70 <= r["C_overall"] <= 0.90 and r["C_lowest"] >= 0.60, "C passed: the same-lake level is shown"


def test_the_forecast_shows_what_lake_range_shown_gives_and_logs_the_unchanged_range():
    src = (ROOT / "src" / "dipcast" / "model" / "forecast.py").read_text()
    assert "shown = lake_range.shown(lat, lon, X, ranges)" in src
    assert 'row["ecoli_range"] = ({**{k: lake_range.sig2(shown[k][j])' in src
    assert 'out["ecoli_range_withheld"]' in src
    assert "lake_range.log_shadow(now, lat, lon, days, r48, r24, risk, ranges, model_version())" in src
