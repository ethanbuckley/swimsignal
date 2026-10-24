"""A missing spill model fails the build. Climatology alone ignores the rain, and the page would
show it as if it were the model's forecast, so the build stops and the previous site stays up."""

import sys
from pathlib import Path

import pytest

from dipcast.model import forecast

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_an_absent_model_path_stops_the_build_before_anything_is_fetched(tmp_path, monkeypatch):
    bs = _build_site()
    monkeypatch.setattr(bs, "MODEL_PATH", tmp_path / "spill_model.pkl")

    def must_not_run(*a, **k):
        raise AssertionError("the build went on without a spill model")

    for name in ("refresh_all", "load_spots", "prefetch_rain", "forecast_point"):
        monkeypatch.setattr(bs, name, must_not_run)
    with pytest.raises(bs.BuildUnhealthy, match="no trained spill model"):
        bs.build(refresh=True)
    with pytest.raises(bs.BuildUnhealthy, match="no trained spill model"):
        bs.build(refresh=False)


def test_the_check_passes_with_the_model_in_the_repo():
    bs = _build_site()
    bs.require_spill_model()   # data/processed/spill_model.pkl is tracked in git


def test_the_forecast_never_falls_back_to_climatology_on_its_own(tmp_path, monkeypatch):
    monkeypatch.setattr(forecast, "MODEL_PATH", tmp_path / "spill_model.pkl")
    forecast._model.cache_clear()
    try:
        with pytest.raises(forecast.MissingSpillModel):
            forecast._model()
    finally:
        forecast._model.cache_clear()
