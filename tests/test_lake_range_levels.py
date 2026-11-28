"""LAKE-RANGE-OWN-LEVELS (docs/LAKE-RANGE-OWN-LEVELS-2026-11.md): the 7 lake bathing waters' own levels, frozen by the
rule bench read 2 passed with, used only where no overflow is upstream. Made-up rain only."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import lake_range as lr
from dipcast.model.ecoli import features

ROOT = Path(__file__).resolve().parents[1]
SERPENTINE, COTSWOLD = (51.50491, -0.16907), (51.66098, -1.96091)


def X(r48):
    return features([r48, r48], [0.0, 0.0], [0.0, 0.0], [1.0, 1.0], [pd.Timestamp("2027-07-15")] * 2)


def test_the_committed_file_is_the_frozen_one_and_none_of_its_lakes_has_a_level_in_lake_range_v1():
    raw = lr.LEVELS_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == lr.LEVELS_SHA256
    doc = json.loads(raw)
    assert doc["model_sha256"] == lr.SHA256
    m = lr.model()
    assert len(doc["sites"]) == 7 and not set(doc["sites"]) & set(m["sites"])
    for bw, s in doc["sites"].items():
        w = np.exp(np.asarray(s["log_weights"]))
        assert abs(w.sum() - 1) < 1e-4 and s["samples"] >= 50 and s["seasons"] == [2023, 2026], bw
        assert lr.site_for(m, s["lat"], s["lon"]) is None, "no lake-range-v1 site within the radius"
    lr.clear_cache()
    assert len(lr.levels()) == 7


def test_its_own_level_moves_the_serpentine_up_from_the_average_lake():
    """Seen years: the average lake's likely reading at these 7 was about 12 against measured medians of 27 to 150."""
    avg = lr.ranges(*SERPENTINE, X(5.0))
    own = lr.ranges(*SERPENTINE, X(5.0), own_level=True)
    assert avg["basis"] == "average lake" and own["basis"] == lr.OWN_LEVEL and own["bw_id"] == "uki1106-11940"
    assert own["median"][0] > 3 * avg["median"][0]
    assert own["low"][0] < own["median"][0] < own["high"][0]
    assert np.isnan(own["usual"]).all(), "no usual inputs for these lakes, so no higher/lower than usual line"


def test_no_range_off_the_list_or_with_another_file(monkeypatch):
    assert lr.ranges(51.5, -0.12, X(5.0), own_level=True) is None
    monkeypatch.setattr(lr, "LEVELS_SHA256", "0" * 64)
    lr.clear_cache()
    assert lr.levels() == {} and lr.level_for(*SERPENTINE) is None
    monkeypatch.undo()
    lr.clear_cache()
    assert lr.level_for(*COTSWOLD) == "ukk1302-11760"


def test_the_forecast_uses_own_levels_only_where_no_overflow_is_upstream_and_logs_nothing_new():
    src = (ROOT / "src" / "dipcast" / "model" / "forecast.py").read_text()
    assert 'own_level = pin.mode == "lake" and ov.empty and lake_range.level_for(lat, lon) is not None' in src
    assert "lake_range.ranges(lat, lon, X, own_level=own_level)" in src
    assert "if ranges is not None and not ov.empty:" in src
