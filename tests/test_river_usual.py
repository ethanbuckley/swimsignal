"""The "higher or lower than usual here" word at river spots (src/dipcast/river_usual.py; decided in
docs/RIVER-ORDER-LINE-PROPOSAL-2026-11.md). The page's sentence is tested in tests/site_river_usual.test.cjs."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dipcast import river_usual as ru

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import river_usual as make  # noqa: E402


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    """A cut-points file of two spots, taken as the frozen one."""
    doc = {"rule": ru.RULE, "spots": {ru.key(53.93189, -1.81618): {"id": "a", "low": 0.08, "high": 0.2},
                                      ru.key(51.5, -1.0): {"id": "b", "low": 0.02, "high": 0.05}}}
    f = tmp_path / "river_usual.v1.json"
    f.write_text(json.dumps(doc))
    monkeypatch.setattr(ru, "FILE", f)
    monkeypatch.setattr(ru, "SHA256", hashlib.sha256(f.read_bytes()).hexdigest())
    ru.clear_cache()
    yield f
    ru.clear_cache()


def test_the_committed_file_is_the_frozen_one():
    assert hashlib.sha256(ru.FILE.read_bytes()).hexdigest() == ru.SHA256
    doc = json.loads(ru.FILE.read_text())
    assert doc["rule"] == ru.RULE and len(doc["spots"]) >= 40
    for k, v in doc["spots"].items():
        assert 0 <= v["low"] < v["high"] <= 1 and v["days"] >= make.MIN_DAYS, k
        assert 0.2 <= v["lower"] <= 0.4 and 0.2 <= v["higher"] <= 0.4, k   # about a third of days each way
    ru.clear_cache()
    assert len(ru.cuts()) == len(doc["spots"])


def test_three_words_from_the_spots_own_cut_points(frozen):
    d = lambda p, lat=53.93189, lon=-1.81618, month=7: ru.direction(lat, lon, p, month)   # noqa: E731
    assert d(0.079) == "lower" and d(0.08) == "about" and d(0.2) == "about" and d(0.201) == "higher"
    assert d(0.06, 51.5, -1.0) == "higher"            # the same figure is high at a spot whose usual is lower
    assert d(0.14, 53.931894, -1.816184) == "about"   # the position to about a metre


def test_no_word_out_of_season_off_the_list_or_without_a_figure(frozen):
    assert [ru.direction(53.93189, -1.81618, 0.5, m) for m in (4, 10, 1)] == [None, None, None]
    assert [ru.direction(53.93189, -1.81618, 0.5, m) for m in (5, 9)] == ["higher", "higher"]
    assert ru.direction(53.9, -1.8, 0.5, 7) is None      # a point that is not a listed spot
    assert ru.direction(53.93189, -1.81618, None, 7) is None


def test_off_without_the_file_or_with_another(frozen, monkeypatch):
    monkeypatch.setattr(ru, "SHA256", "0" * 64)
    ru.clear_cache()
    assert ru.cuts() == {} and ru.direction(53.93189, -1.81618, 0.5, 7) is None
    monkeypatch.setattr(ru, "FILE", frozen.parent / "missing.json")
    ru.clear_cache()
    assert ru.cuts() == {}


def test_cut_points_are_the_thirds_and_need_days_and_spread():
    rng = np.random.default_rng(1)
    p = pd.Series(rng.beta(2, 12, 612))
    c = make.cut_points(p)
    assert c["days"] == 612 and abs(c["lower"] - 1 / 3) < 0.02 and abs(c["higher"] - 1 / 3) < 0.02
    assert c["low"] == round(float(p.quantile(1 / 3)), 3) and c["high"] == round(float(p.quantile(2 / 3)), 3)
    assert make.cut_points(p.iloc[:299]) is None                      # too few days
    assert make.cut_points(pd.Series(np.full(612, 0.031))) is None    # no spread: the word would say nothing
    with_gaps = p.copy()
    with_gaps.iloc[:200] = np.nan
    assert make.cut_points(with_gaps)["days"] == 412
    assert len(make.season_days()) == 612 and {d.month for d in make.season_days()} == {5, 6, 7, 8, 9}
