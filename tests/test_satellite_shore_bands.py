"""Integrity of the published, fixed shore-margin sample."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def test_paired_sample_has_unique_identified_scenes_and_reproduces_summary():
    data = json.loads((ROOT / 'data/research/satellite_shore_bands_2026_11.json').read_text())
    rows = data['rows']
    assert len(rows) == 50
    assert len({r['site_id'] for r in rows}) == 14
    assert len({(r['site_id'], r['scene_id']) for r in rows}) == 50
    differences = np.array([r['ndci_margin_2'] - r['ndci_margin_1'] for r in rows])
    assert np.isfinite(differences).all()
    assert round(float(np.median(differences)), 4) == -0.0033
    assert round(float(np.median(np.abs(differences))), 4) == 0.0041
    assert int((np.abs(differences) >= 0.02).sum()) == 7
    assert data['network_requests'] <= 300
    assert data['network_bytes'] <= 150 * 1024**2
