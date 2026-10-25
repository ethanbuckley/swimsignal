"""check_model_provenance.py rebuilds the rows the 13 Sep 2026 model files were fitted on, on UTC days, whatever
day boundary features.py uses for new models. Expected values are worked out by hand for UTC days."""

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dipcast.model import features

ROOT = Path(__file__).resolve().parents[1]
CELL = (54.4, -2.9)


def _load(monkeypatch, name):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    monkeypatch.setattr(sys, "argv", ["check_model_provenance.py"])
    for m in (name, "train", "legacy_utc_days"):
        sys.modules.pop(m, None)
    return importlib.import_module(name)


def _rain():
    # Hourly rain at one cell, 30 Jun to 3 Jul 2025 (UTC), dry except 5 mm stamped 1 Jul 23:00 UTC:
    # 1 Jul's last hour on UTC days, 2 Jul's first on UK local days (BST).
    t = pd.date_range("2025-06-30 00:00", "2025-07-03 23:00", freq="h", tz="UTC")
    p = np.where(t == pd.Timestamp("2025-07-01 23:00", tz="UTC"), 5.0, 0.0)
    return pd.DataFrame({"cell_lat": CELL[0], "cell_lon": CELL[1], "time": t, "precip_mm": p})


def _events():
    return pd.DataFrame({"site_id": ["UUA1"], "event_start": [pd.Timestamp("2025-07-01 23:30", tz="UTC")],
                         "event_end": [pd.Timestamp("2025-07-01 23:50", tz="UTC")]})


def _returns():
    return pd.DataFrame({"company": ["United Utilities"], "site_id": ["UUA1"], "year": [2024], "lat": [CELL[0]],
                         "lon": [CELL[1]], "lta_spills": [12.0], "spill_hours": [80.0], "edm_operational_pct": [99.0]})


def test_legacy_days_are_utc_days(monkeypatch):
    L = _load(monkeypatch, "legacy_utc_days")
    d = L.daily_rain_features(_rain()).set_index("day")
    assert str(d.index.tz) == "UTC"
    jul1, jul2 = pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2025-07-02", tz="UTC")
    assert d.loc[jul1, "rain_d"] == 5.0 and d.loc[jul2, "rain_d"] == 0.0
    assert d.loc[jul2, "rain_d1"] == 5.0 and d.loc[jul1, "max1h_d"] == 5.0
    assert np.isclose(d.loc[jul1, "api"], 5.0) and np.isclose(d.loc[jul2, "api"], 0.85 * 5.0)
    s = L.spill_days(_events())
    assert s["day"].tolist() == [jul1]


def test_checker_rows_are_the_legacy_utc_rows(monkeypatch):
    C = _load(monkeypatch, "check_model_provenance")
    r = C.rows(ev=_events(), ar=_returns(), rain=_rain())
    assert str(r["day"].dt.tz) == "UTC"
    assert len(r) == 4                              # the four days with rain data
    jul1 = r[r["day"] == pd.Timestamp("2025-07-01", tz="UTC")].iloc[0]
    assert jul1["y"] == 1 and jul1["rain_d"] == 5.0
    assert r["y"].sum() == 1


def test_checker_does_not_use_features_day_functions(monkeypatch):
    """If features.py moves to another day boundary (or rejects a UTC grid), the check still rebuilds UTC rows."""
    def refuse(*a, **k):
        raise ValueError("features day function called")
    for name in ("daily_rain_features", "spill_days", "build_site_days"):
        monkeypatch.setattr(features, name, refuse)
    C = _load(monkeypatch, "check_model_provenance")
    r = C.rows(ev=_events(), ar=_returns(), rain=_rain())
    assert len(r) == 4 and r["y"].sum() == 1


def test_legacy_copies_match_features_while_features_still_cut_utc_days(monkeypatch):
    """On a main whose features.py still cuts UTC days, the frozen copies give the same frames. After a change of
    day boundary in features.py this no longer applies, and the hand-worked tests above keep the copies honest."""
    if hasattr(features, "LOCAL_TZ"):
        pytest.skip("features.py no longer cuts UTC days")
    L = _load(monkeypatch, "legacy_utc_days")
    pd.testing.assert_frame_equal(L.daily_rain_features(_rain()), features.daily_rain_features(_rain()))
    pd.testing.assert_frame_equal(L.spill_days(_events()).reset_index(drop=True),
                                  features.spill_days(_events()).reset_index(drop=True))
