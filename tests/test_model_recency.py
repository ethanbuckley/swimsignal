"""Layer 2's recency weight: the model records it, train.py's production default matches main's model files,
and files saved before the setting was recorded still load."""

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast.model.spill_model import PRIOR_STRENGTH, SpillModel

ROOT = Path(__file__).resolve().parents[1]


class _Flat:
    """A stand-in layer 1 that predicts 0.1 everywhere."""
    def predict_proba(self, X):
        return np.tile([0.9, 0.1], (len(X), 1))


def _rows():
    # One site, two years: 30 spill days in 2023, 5 in 2024, out of 100 days each.
    y = np.r_[np.ones(30), np.zeros(70), np.ones(5), np.zeros(95)]
    df = pd.DataFrame({f: 0.0 for f in SpillModel().features}, index=range(200))
    return df.assign(site_id="S1", year=np.r_[np.full(100, 2023), np.full(100, 2024)], y=y)


def test_fit_site_offsets_records_its_settings_and_weights_older_years():
    m = SpillModel(clf=_Flat())
    m.fit_site_offsets(_rows(), recency=0.25)
    assert (m.site_recency, m.site_prior) == (0.25, PRIOR_STRENGTH)
    # 2023 counts a quarter: n = 30*0.25 + 5, e = 0.1*(100*0.25 + 100).
    n, e = 30 * 0.25 + 5, 0.1 * (100 * 0.25 + 100)
    assert np.isclose(m.site_offset["S1"], np.log((n + PRIOR_STRENGTH) / (e + PRIOR_STRENGTH)))
    m1 = SpillModel(clf=_Flat()).fit_site_offsets(_rows(), recency=1.0)
    assert m1.site_recency == 1.0 and m1.site_offset["S1"] > m.site_offset["S1"]   # the wet older year counts more


def test_model_files_saved_before_the_setting_was_recorded_still_load():
    for name in ("spill_model.pkl", "spill_model_holdout_2025.pkl"):
        m = SpillModel.load(ROOT / "data" / "processed" / name)
        assert m.site_recency is None and m.site_prior is None
        assert len(m.site_offset) > 2000


def test_train_defaults_production_path_to_main_files_recency(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    monkeypatch.setattr(sys, "argv", ["train.py", "2025"])
    sys.modules.pop("train", None)
    t = importlib.import_module("train")
    assert t.RECENCY == 0.25          # what main's model files were fitted with
    assert t.NINE_RECENCY == 1.0      # the nine-company test's stated setting
    monkeypatch.setattr(sys, "argv", ["train.py", "2025", "--recency", "0.5"])
    sys.modules.pop("train", None)
    t = importlib.import_module("train")
    assert t.RECENCY == 0.5 and t.NINE_RECENCY == 0.5
    sys.modules.pop("train", None)
