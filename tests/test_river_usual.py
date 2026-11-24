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


# ------------------------------------------------------------------ the winter word (docs/RIVER-WINTER-LINE-2026-11.md)
import river_usual_winter as make_winter  # noqa: E402

from dipcast import config  # noqa: E402


@pytest.fixture
def winter(tmp_path, monkeypatch):
    """A winter cut-points file of one spot, taken as the frozen one, with the switch on."""
    f = tmp_path / "river_usual_winter.v1.json"
    f.write_text(json.dumps({"rule": ru.WINTER_RULE, "spots": {ru.key(53.93189, -1.81618): {"id": "a", "low": 0.22, "high": 0.53}}}))
    monkeypatch.setattr(ru, "WINTER_FILE", f)
    monkeypatch.setattr(ru, "WINTER_SHA256", hashlib.sha256(f.read_bytes()).hexdigest())
    monkeypatch.setattr(config, "RIVER_WINTER_LINE", True)
    ru.clear_cache()
    yield f
    ru.clear_cache()


def test_the_winter_switch_is_off_unless_set():
    import importlib
    import os
    assert "DIPCAST_RIVER_WINTER_LINE" not in os.environ and config.RIVER_WINTER_LINE is False and ru.winter_on() is False
    src = (ROOT / "src" / "dipcast" / "config.py").read_text()
    assert 'RIVER_WINTER_LINE = os.environ.get("DIPCAST_RIVER_WINTER_LINE", "") == "1"' in src
    assert importlib.util.find_spec("dipcast.river_usual") is not None


def test_with_the_switch_off_there_is_no_winter_word_whatever_the_file_says(winter, monkeypatch):
    monkeypatch.setattr(config, "RIVER_WINTER_LINE", False)
    assert [ru.winter_direction(53.93189, -1.81618, p, 11) for p in (0.01, 0.3, 0.9)] == [None, None, None]


def test_the_committed_winter_file_is_the_frozen_one_and_made_from_the_model_the_read_scored():
    assert hashlib.sha256(ru.WINTER_FILE.read_bytes()).hexdigest() == ru.WINTER_SHA256
    doc, summer = json.loads(ru.WINTER_FILE.read_text()), json.loads(ru.FILE.read_text())
    assert doc["rule"] == ru.WINTER_RULE and set(doc["spots"]) == set(summer["spots"])   # the same river spots
    model = hashlib.sha256((ROOT / "data" / "processed" / "ecoli_model.json").read_bytes()).hexdigest()
    assert doc["model_sha256"] == model == "7daf7c8e407a82ba1344ab1b925092953791c138d690d5dc18093221d49ca09c"
    assert "7daf7c8e" in (ROOT / "docs" / "RIVER-WINTER-READ-2026-11.md").read_text()      # the file that record scored
    assert "soil" not in doc["inputs"].lower() and doc["first_day"] == make_winter.FIRST_DAY
    for k, v in doc["spots"].items():
        assert 0 <= v["low"] < v["high"] <= 1 and v["days"] >= make_winter.MIN_DAYS, k
        assert 0.2 <= v["lower"] <= 0.4 and 0.2 <= v["higher"] <= 0.4, k


def test_three_winter_words_from_october_to_april_only(winter):
    d = lambda p, month=11, lat=53.93189, lon=-1.81618: ru.winter_direction(lat, lon, p, month)   # noqa: E731
    assert d(0.219) == "lower" and d(0.22) == "about" and d(0.53) == "about" and d(0.531) == "higher"
    assert [d(0.9, m) for m in (10, 11, 12, 1, 2, 3, 4)] == ["higher"] * 7
    assert [d(0.9, m) for m in (5, 6, 7, 8, 9)] == [None] * 5       # in season the summer word speaks, from its own file
    assert d(0.9, 11, 53.9, -1.8) is None and d(None) is None       # not a listed spot; no figure
    assert ru.direction(53.93189, -1.81618, 0.9, 11) is None        # the in-season word is unchanged: none in November


def test_the_winter_word_is_off_with_another_file(winter, monkeypatch):
    monkeypatch.setattr(ru, "WINTER_SHA256", "0" * 64)
    ru.clear_cache()
    assert ru.winter_cuts() == {} and ru.winter_direction(53.93189, -1.81618, 0.9, 11) is None


def test_the_forecast_gives_the_winter_word_to_today_only_from_the_figure_without_soil_moisture():
    src = (ROOT / "src" / "dipcast" / "model" / "forecast.py").read_text()
    plain, swap = src.index("p_plain = p_ec"), src.index("p_ec, soil_state = river_ecoli(")
    assert src.index("p_ec = em.predict(X)") < plain < swap          # taken before the soil-moisture model replaces it
    assert 'if days[j] == now.floor("D") and not (np.isnan(r48[j]) or np.isnan(p_plain[j])):' in src
    assert "river_usual.winter_direction(lat, lon, round(float(p_plain[j]), 3), days[j].month)" in src
    assert src.count('row["ecoli_usual_winter"]') == 1 and src.count('row["p_ecoli_gt900"] =') == 1


def test_winter_days_and_cut_points():
    days = make_winter.winter_days()
    assert {d.month for d in days} == {10, 11, 12, 1, 2, 3, 4} and str(days.min().date()) == make_winter.FIRST_DAY
    assert days.is_monotonic_increasing and days.is_unique
    rng = np.random.default_rng(2)
    p = pd.Series(rng.beta(2, 5, 768))
    c = make_winter.cut_points(p)
    assert c["low"] == round(float(p.quantile(1 / 3)), 3) and c["high"] == round(float(p.quantile(2 / 3)), 3)
    assert make_winter.cut_points(p.iloc[:379]) is None and make_winter.cut_points(pd.Series(np.full(768, 0.2))) is None


def test_the_method_page_paragraph_only_while_the_switch_is_on(monkeypatch):
    import build_site as bs
    page = (ROOT / "src" / "dipcast" / "pages" / "methods.html").read_text()
    assert page.count(bs.RIVER_WINTER_MARK) == 1
    off = bs.with_river_winter(page)
    assert off == page.replace(bs.RIVER_WINTER_MARK, "") and "winter-river-line" not in off
    monkeypatch.setattr(config, "RIVER_WINTER_LINE", True)
    on = bs.with_river_winter(page)
    assert 'id="winter-river-line"' in on and "today only" in on and "no figure" in on and bs.RIVER_WINTER_MARK not in on
    with pytest.raises(ValueError):
        bs.with_river_winter(off)
