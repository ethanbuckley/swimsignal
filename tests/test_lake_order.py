"""LAKE-ORDER (docs/LAKE-ORDER-NO-OVERFLOW-2026-11.md): today's higher, about or lower word at the five lake bathing
waters with no monitored overflow upstream that bench read 1 scored. Made-up rain only."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dipcast import lake_order as lo
from dipcast import lake_range
from dipcast.model.ecoli import features

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lake_order as script  # noqa: E402

SERPENTINE = (51.50491, -0.16907)


def X(r48, r24=0.0, day="2027-07-15"):
    return features([r48], [r24], [0.0], [1.0], [pd.Timestamp(day)])


def test_the_committed_file_is_the_frozen_one_for_bench_read_1s_five_daily_lakes():
    raw = lo.FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == lo.SHA256
    doc = json.loads(raw)
    assert doc["rule"] == lo.RULE and doc["model_sha256"] == lake_range.SHA256
    assert {v["id"] for v in doc["spots"].values()} == set(script.SPOTS)
    for k, v in doc["spots"].items():
        assert v["high"] - v["low"] >= script.MIN_GAP and v["days"] >= script.MIN_DAYS, k
        assert 0.3 <= v["lower"] <= 0.36 and 0.3 <= v["higher"] <= 0.36, k   # about a third of days each way
    lo.clear_cache()
    assert len(lo.cuts()) == 12   # these five and the seven overflow lakes (test_lake_order_overflow.py)


def test_none_of_the_five_has_its_own_level_in_lake_range_v1():
    """The cut-points are on the average-lake basis, as bench read 1 scored them: a spot inside a model site's radius
    would get another basis on the page's range and must not be here."""
    m = lake_range.model()
    for _, lat, lon in script.SPOTS.values():
        assert lake_range.site_for(m, lat, lon) is None


def test_more_rain_than_usual_reads_higher_and_a_dry_day_lower():
    d = lambda r48, month=7: lo.direction(*SERPENTINE, X(r48), month)   # noqa: E731
    assert d(25.0) == "higher" and d(0.0) == "lower"
    words = [d(r) for r in np.arange(0, 30, 0.5)]
    order = {"lower": 0, "about": 1, "higher": 2}
    assert [order[w] for w in words] == sorted(order[w] for w in words), "the word never falls as the rain rises"
    assert "about" in words


def test_no_word_out_of_season_off_the_list_with_an_input_missing_or_with_another_file(monkeypatch):
    assert [lo.direction(*SERPENTINE, X(25.0), m) for m in (10, 11, 12, 1, 2, 3, 4)] == [None] * 7
    assert lo.direction(51.5, -0.17, X(25.0), 7) is None                       # not one of the five
    assert lo.direction(*SERPENTINE, X(float("nan")), 7) is None              # no rain figure
    assert lo.direction(*SERPENTINE, pd.concat([X(1.0), X(2.0)]), 7) is None  # today's row only
    monkeypatch.setattr(lo, "SHA256", "0" * 64)
    lo.clear_cache()
    assert len(lo.cuts()) == 7 and lo.direction(*SERPENTINE, X(25.0), 7) is None   # the other file stands alone
    monkeypatch.undo()
    lo.clear_cache()


def test_the_word_is_the_figure_bench_read_1_scored():
    """The figure compared is lake-range-v1's likely reading on the average-lake basis at exposure 0: the script's
    figure and the site's agree."""
    m = lake_range.model()
    days = pd.DatetimeIndex(["2027-06-01 12:00", "2027-08-20 12:00"], tz="Europe/London")
    f = script.figure(m, [3.0, 18.0], [1.0, 9.0], days)
    for j in range(2):
        site = lake_range._quantiles(m, features([[3.0, 18.0][j]], [[1.0, 9.0][j]], [0.0], [1.0], [days[j]])[m["cols"]],
                                     None, qs=(0.5,))[0.5][0]
        assert f[j] == pytest.approx(np.log10(site))


def test_the_forecast_gives_the_word_to_today_only_at_a_lake_with_no_overflow_upstream():
    src = (ROOT / "src" / "dipcast" / "model" / "forecast.py").read_text()
    assert 'if (pin.mode == "lake" and days[j] == now.floor("D")' in src
    assert 'and (ov.empty or (ranges is not None and shown is None))):' in src
    assert "lake_order.direction(lat, lon, X.iloc[[j]], days[j].month)" in src
    assert src.count('row["lake_order"]') == 1 and "lake_order.clear_cache()" in src
