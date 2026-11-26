"""RAIN-WORD (docs/RAIN-WORD-NO-OVERFLOW-2026-11.md, scripts/rain_word/): the word's cut-points and coding, which
reserve rows the read may load, and the outcome words. Made-up rows only."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dipcast import rain_usual as ra

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "rain_word"))
import rain_word_read as rw


def test_cut_points_are_thirds_to_a_tenth_of_a_millimetre():
    r = pd.Series(np.arange(300) / 10.0)
    c = rw.cut_points(r)
    assert (c["low"], c["high"], c["days"]) == (10.0, 19.9, 300)


def test_too_few_days_or_too_little_spread_gives_no_cut_points():
    assert rw.cut_points(pd.Series(np.arange(299) / 10.0)) is None
    assert rw.cut_points(pd.Series([0.0] * 200 + [0.5] * 200)) is None   # cut-points under 1.0 mm apart


def test_the_word_codes_rain_against_its_own_cut_points():
    assert rw.word([0.0, 1.0, 1.04, 5.0, 7.1, 7.16], 1.0, 7.1).tolist() == [-1, 0, 0, 0, 0, 1]


def test_outcome_words():
    base = {"points_15_or_more": 10, "rows": 1000, "condition_1_pass": True, "condition_2_pass": True}
    assert rw.outcome(base) == "both pass"
    assert rw.outcome({**base, "condition_2_pass": False}).startswith("order is the calendar")
    assert rw.outcome({**base, "condition_1_pass": False}) == "order fails"
    assert rw.outcome({**base, "points_15_or_more": 7}) == "too few rows"
    assert rw.outcome({**base, "rows": 699}) == "too few rows"


def test_month_removed_word_keeps_a_day_to_day_signal():
    rng = np.random.default_rng(2)
    out = []
    for p in range(8):
        n = 80
        month = rng.choice([10, 11, 12, 1, 2, 3, 4], n)
        rain = rng.gamma(1.0, 5.0, n)
        out.append(pd.DataFrame({"bw_id": f"P{p}", "system": f"S{p % 4}", "season": rng.choice([2013, 2015], n), "month": month,
                                 "rain_48h": rain, "log_ecoli": np.log10(rain + 1) + rng.normal(scale=0.3, size=n)}))
    d = pd.concat(out, ignore_index=True)
    d["word"] = rw.word(d["rain_48h"], 1.5, 7.0)
    assert rw.raw(d, "word") > 0.4 and rw.month_removed(d, "word") > 0.4


# ------------------------------------------------------------------------------------------------ the site's word
NO_OVERFLOW_SPOTS = {"gordale-janets-foss", "duddon-birks-bridge", "tees-low-force", "derwent-slippery-stones",
                     "plym-cadover-bridge", "barle-tarr-steps", "barle-landacre", "swale-kisdon-force", "esk-tongue-pot",
                     "osm-rivelin-plunge-pool", "osm-burbage-padley-gorge", "osm-dane-three-shires-head", "osm-lathkill-dale",
                     "osm-bradford-youlgrave", "osm-blackaton-shilley-pool"}


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    doc = {"rule": ra.RULE, "spots": {ra.key(54.068, -2.137): {"id": "a", "winter": {"low": 1.9, "high": 9.3},
                                                                "summer": {"low": 1.7, "high": 8.5}}}}
    f = tmp_path / "rain_usual.v1.json"
    f.write_text(json.dumps(doc))
    monkeypatch.setattr(ra, "FILE", f)
    monkeypatch.setattr(ra, "SHA256", hashlib.sha256(f.read_bytes()).hexdigest())
    ra.clear_cache()
    yield f
    ra.clear_cache()


def test_the_committed_file_is_the_frozen_one_and_covers_the_15_spots():
    assert hashlib.sha256(ra.FILE.read_bytes()).hexdigest() == ra.SHA256
    doc = json.loads(ra.FILE.read_text())
    assert doc["rule"] == ra.RULE and NO_OVERFLOW_SPOTS <= {v["id"] for v in doc["spots"].values()}
    for k, v in doc["spots"].items():
        for s in ("winter", "summer"):
            c = v[s]
            assert c["high"] - c["low"] >= rw.MIN_GAP and c["days"] >= rw.MIN_DAYS, k
            assert 0.28 <= c["less"] <= 0.38 and 0.28 <= c["more"] <= 0.38, k   # about a third of days each way
    ra.clear_cache()
    assert len(ra.cuts()) == len(doc["spots"])


def test_three_words_in_winter_from_the_spots_own_cut_points(frozen):
    d = lambda r, month=11, lat=54.068, lon=-2.137: ra.direction(lat, lon, r, month)   # noqa: E731
    assert d(1.8) == "less" and d(1.9) == "about" and d(9.3) == "about" and d(9.34) == "about" and d(9.36) == "more"
    assert [d(20.0, m) for m in (10, 11, 12, 1, 2, 3, 4)] == ["more"] * 7
    assert d(20.0, 11, 54.0, -2.1) is None and d(None) is None      # not a listed spot; no rain figure


def test_no_summer_word_unless_the_statement_allows_it(frozen, monkeypatch):
    assert ra.SUMMER_ON is False or ra.direction(54.068, -2.137, 20.0, 7) == "more"
    monkeypatch.setattr(ra, "SUMMER_ON", False)
    assert [ra.direction(54.068, -2.137, 20.0, m) for m in (5, 6, 7, 8, 9)] == [None] * 5


def test_off_with_another_file(frozen, monkeypatch):
    monkeypatch.setattr(ra, "SHA256", "0" * 64)
    ra.clear_cache()
    assert ra.cuts() == {} and ra.direction(54.068, -2.137, 20.0, 11) is None


def test_the_forecast_gives_the_rain_word_to_today_only_at_a_river_spot_with_no_overflow_upstream():
    src = (ROOT / "src" / "dipcast" / "model" / "forecast.py").read_text()
    assert 'if pin.mode == "river" and not here.any() and days[j] == now.floor("D"):' in src
    assert 'rain_usual.direction(lat, lon, row["rain_48h_mm"], days[j].month)' in src
    assert src.count('row["rain_usual"]') == 1 and "rain_usual.clear_cache()" in src
