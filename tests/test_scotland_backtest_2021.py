"""The Scotland 2021 backtest (scripts/scotland_backtest_2021.py): the map as the trial applies it, the pass rule's
parts and minimum, and the booked fetch's refusals. No data file is read."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scotland_backtest_2021 as bt  # noqa: E402
import scotland_recalibration as sr  # noqa: E402


def test_the_map_is_the_trials():
    m = {"a": 0.449, "b": 0.750}
    p = np.array([1e-9, 0.02, 0.3, 0.9, 1.0])
    assert np.allclose(bt.apply_map(m, p), sr.apply_map(m, p))


def rows(n_sites=20, n_days=120, raw_scale=0.6, seed=0):
    """Rows where y follows a known chance; the unmapped forecast is that chance times raw_scale, so a map can
    restore it; the earlier-years baseline is one flat rate."""
    rng = np.random.default_rng(seed)
    site = np.repeat([f"S{i}" for i in range(n_sites)], n_days)
    day = np.tile(pd.date_range("2021-01-01", periods=n_days, freq="D", tz="UTC"), n_sites)
    true = np.clip(rng.beta(1.2, 4, n_sites * n_days), 0.01, 0.95)
    y = (rng.random(true.size) < true).astype(int)
    df = pd.DataFrame({"site_id": site, "day": day, "y": y})
    df[bt.hs.PROD] = true * raw_scale
    df[bt.MAPPED] = true
    df[bt.hs.EARLIER] = true.mean()
    return df


def test_a_good_mapped_forecast_passes_all_three_parts():
    r = bt.rule(rows(), n_boot=200)
    assert r["parts"] == {"B1": True, "B2": True, "B3": True} and r["verdict"] == "PASS"
    assert 0.9 <= r["level"] <= 1.1


def test_a_level_out_of_range_fails_b2_only():
    df = rows()
    df[bt.MAPPED] = df[bt.MAPPED] * 1.3
    r = bt.rule(df, n_boot=200)
    assert r["parts"]["B2"] is False and r["verdict"] == "FAIL"


def test_too_few_overflows_or_spill_days_is_not_complete():
    assert bt.rule(rows(n_sites=5), n_boot=50)["verdict"] == "NOT COMPLETE"
    assert bt.rule(rows().iloc[:0], n_boot=50)["verdict"] == "NOT COMPLETE"


def test_the_fetch_is_refused_when_the_days_ration_has_no_room(monkeypatch):
    calls = []
    monkeypatch.setattr(bt.rainfall, "may_spend", lambda w, what: False)
    monkeypatch.setattr(bt.rainfall, "fetch_archive", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(bt.rainfall, "spend", lambda w, what: None)
    with pytest.raises(RuntimeError, match="ration"):
        bt.fetch_booked([(56.0, -4.0)], 2020)
    assert calls == []


def test_a_made_request_is_booked_even_when_it_fails(monkeypatch):
    booked = []
    monkeypatch.setattr(bt.rainfall, "may_spend", lambda w, what: True)
    monkeypatch.setattr(bt.rainfall, "spend", lambda w, what: booked.append((round(w, 1), what)))

    def refuse(*a, **k):
        raise RuntimeError("429")
    monkeypatch.setattr(bt.rainfall, "fetch_archive", refuse)
    with pytest.raises(RuntimeError, match="429"):
        bt.fetch_booked([(56.0, -4.0), (56.1, -4.0)], 2020)
    assert booked == [(52.3, bt.WHAT)]            # two cells x 366 / 14 by the scripts' count
