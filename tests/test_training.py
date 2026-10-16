"""The rows the nine-company spill model trains on (model.training), and the lead calibration's tie to
the model it corrects (review task A1, docs/NINE-COMPANY-MODEL-TEST-2026-10.md)."""

import json

import numpy as np
import pandas as pd
import pytest

from dipcast import config
from dipcast.model.spill_model import MODEL_PATH, SpillModel
from dipcast.model.training import ece, site_years


def test_lead_calibration_was_fitted_for_the_production_model():
    # Until 16 Oct 2026 a map fitted for the 2023-24 hold-out model corrected the 2023-25 refit.
    cal = json.loads((config.PROCESSED / "lead_calibration.json").read_text())
    assert cal["model"] == SpillModel.load(MODEL_PATH).trained_on


def _ar():
    rows = []
    for sid, prev_lat, spills, edm in [
        ("A1", 51.0, 3, 95.0),    # in the file
        ("A2", 51.1, 0, 95.0),    # no event, and the return says it did not spill
        ("A3", 51.2, 5, 95.0),    # no event, but the return says 5 spills: missing from the file
        ("A4", 51.3, np.nan, 95.0),  # no event, no count
        ("A5", 51.4, 9, 30.0),    # in the file, monitor under 50% of the year
        ("A6", np.nan, 2, 95.0),  # no position in the year before
    ]:
        rows.append({"site_id": sid, "company": "Anglian Water", "year": 2023, "lat": prev_lat, "lon": 0.5,
                     "lta_spills": 10.0, "spill_hours": 20.0, "edm_operational_pct": 99.0, "spills": 1})
        rows.append({"site_id": sid, "company": "Anglian Water", "year": 2024, "lat": prev_lat, "lon": 0.5,
                     "lta_spills": 10.0, "spill_hours": 20.0, "edm_operational_pct": edm, "spills": spills})
    return pd.DataFrame(rows)


def test_coverage_rule_keeps_spilled_or_zero_and_drops_missing_and_low_edm():
    ev = pd.DataFrame({"site_id": ["A1", "A5", "A6"],
                       "event_start": pd.to_datetime(["2024-03-01", "2024-03-02", "2024-03-03"], utc=True)})
    sites, counts = site_years(_ar(), ev, ["Anglian Water"], 2024)
    assert sorted(sites["site_id"]) == ["A1", "A2"]
    c = counts.loc["Anglian Water"]
    assert (c["with_position"], c["missing_from_file"], c["edm_under_50"], c["kept"]) == (5, 2, 1, 2)
    assert c["year"] == 2024


def test_ece_is_the_row_weighted_gap_per_bin():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.05, 0.05, 0.95, 0.75])  # bins 0, 0, 9, 7: gaps 0.05, 0.05, 0.05, 0.25
    assert ece(y, p) == pytest.approx((0.05 * 2 + 0.05 + 0.25) / 4)
    assert ece(np.array([0, 1]), np.array([0.5, 0.5])) == pytest.approx(0.0)
