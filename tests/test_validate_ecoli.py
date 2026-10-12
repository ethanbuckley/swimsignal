"""scripts/validate_ecoli.py's hindcast on made-up rain: an overflow whose cell has no rain data adds
nothing and its weight is reported as missing, as in production (forecast.spill_probabilities,
transport.missing_share). Until 12 Oct 2026 its rain was filled with 0 and it counted as a dry day."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_ecoli as ve

from dipcast.model.features import daily_rain_features

TZ = "Europe/London"
DAYS = pd.date_range("2025-07-01", periods=5, freq="D", tz=TZ)


class Flat:
    """A spill model that gives every overflow-day the same chance."""

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), 0.3)


def _upstream(weights: tuple[float, float]) -> pd.DataFrame:
    # A's cell (51.0, -1.0) has rain; B's cell (52.0, -2.0) has none.
    return pd.DataFrame({"site_id": ["A", "B"], "lat": [51.0, 52.0], "lon": [-1.0, -2.0], "company": "X",
                         "lta_spills": 20.0, "spill_hours": 100.0, "edm_operational_pct": 100.0,
                         "weight": list(weights), "travel_h": 0.0})


@pytest.fixture
def daily() -> pd.DataFrame:
    t = pd.date_range(DAYS[0], periods=24 * len(DAYS), freq="h")
    return daily_rain_features(pd.DataFrame({"cell_lat": 51.0, "cell_lon": -1.0, "time": t, "precip_mm": 1.0}))


@pytest.fixture(autouse=True)
def no_calibration(monkeypatch):
    monkeypatch.setattr(ve, "calibrate_at_lead", lambda p, lead: p)


def test_overflow_without_rain_adds_nothing_and_is_counted_missing(daily):
    risk, miss = ve.hindcast(_upstream((0.95, 0.05)), daily, DAYS, Flat())
    assert np.allclose(miss, 0.05)
    assert np.allclose(risk, 0.3 * 0.95)   # A alone; B is not a dry day at 0.3 x 0.05


def test_no_figure_over_the_production_limit(daily):
    risk, miss = ve.hindcast(_upstream((0.5, 0.5)), daily, DAYS, Flat())
    assert np.allclose(miss, 0.5) and miss.gt(ve.MAX_MISSING_SHARE).all()
    assert risk.isna().all()
