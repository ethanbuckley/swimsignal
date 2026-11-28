"""LAKE-ORDER-OVERFLOW (docs/LAKE-ORDER-OVERFLOW-LAKES-2026-11.md): today's higher, about or lower word at the 7 English
lake spots whose average-lake range is withheld. Made-up inputs only."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import lake_order as lo
from dipcast import lake_range
from dipcast.model.ecoli import features

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lake_order_overflow as script  # noqa: E402

GRASMERE = (54.45, -3.02)


def X(r48, risk=0.01):
    return features([r48], [0.0], [risk], [1.0], [pd.Timestamp("2027-07-15")])


def test_the_committed_file_is_the_frozen_one_for_the_seven_withheld_english_lakes():
    raw = lo.OVERFLOW_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == lo.OVERFLOW_SHA256
    doc = json.loads(raw)
    assert doc["model_sha256"] == lake_range.SHA256
    assert {v["id"] for v in doc["spots"].values()} == set(script.SPOTS)
    for k, v in doc["spots"].items():
        assert v["upstream"] >= 1 and v["days"] >= 300 and v["high"] - v["low"] >= 0.01, k
        assert 0.3 <= v["lower"] <= 0.36 and 0.3 <= v["higher"] <= 0.36, k
    m = lake_range.model()
    for k in doc["spots"]:
        lat, lon = map(float, k.split(","))
        assert lake_range.site_for(m, lat, lon) is None and lake_range.same_lake(lat, lon) is None, k


def test_more_rain_and_more_spill_exposure_read_higher_and_the_word_never_falls_as_either_rises():
    lo.clear_cache()
    order = {"lower": 0, "about": 1, "higher": 2}
    by_rain = [order[lo.direction(*GRASMERE, X(r), 7)] for r in np.arange(0, 40, 1.0)]
    assert by_rain == sorted(by_rain) and by_rain[0] == 0
    assert lo.direction(*GRASMERE, X(5.0, 0.5), 7) == "higher", "spills upstream move it most here"
    by_risk = [order[lo.direction(*GRASMERE, X(5.0, k), 7)] for k in (0.0001, 0.001, 0.01, 0.1, 0.5, 0.9)]
    assert by_risk == sorted(by_risk)
    assert lo.direction(*GRASMERE, X(25.0), 11) is None, "in season only"
