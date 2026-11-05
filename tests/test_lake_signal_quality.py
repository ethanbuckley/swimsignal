"""Contract 1.4 (docs/LAKE-OBSERVATIONS-CONTRACT-v1.md): a refreshed reading measures its own signal, the exporter marks
low signal by the stated rule, the check holds the mark to it, and nothing made before the measurement is marked."""
import copy
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lake_algae_sat_eval"))
import export_lake_observations as ex  # noqa: E402
import protocol as pr  # noqa: E402
from refresh_lake_observations import signal_quality  # noqa: E402
from test_export_lake_observations import _doc, _features, _refresh_rows  # noqa: E402


def _lake(n=12, pad=3):
    core = np.zeros((n, n), dtype=bool)
    core[pad:n - pad, pad:n - pad] = True       # a 6 x 6 core
    scl = np.where(core, pr.WATER, 4).astype(np.uint8)
    return core, scl


def test_signal_quality_measures_brightness_spread_and_the_inner_core():
    core, scl = _lake()
    b4 = np.full(core.shape, 0.010)
    b5 = np.full(core.shape, 0.012)
    q = signal_quality(scl, core, b4, b5)
    assert q["core_brightness"] == 0.022 and q["index_iqr"] == 0.0
    assert q["inner_core_pixels"] == 16                          # 6 x 6 eroded by one pixel
    assert q["inner_ndci"] == round(float(pr.ndci(b4, b5)[6, 6]), 5)
    # A brighter rim leaves the inner reading where it was and widens the spread.
    rim = core.copy()
    rim[4:8, 4:8] = False
    b5[rim] = 0.030
    q = signal_quality(scl, core, b4, b5)
    assert q["inner_ndci"] == round(float(pr.ndci(b4, b5)[6, 6]), 5) and q["index_iqr"] > 0.1
    # Only clear core pixels count; a pixel with no index is left out of the spread and the inner reading.
    scl2 = scl.copy()
    scl2[3, :] = 9
    b5[6, 6] = 0.0
    q = signal_quality(scl2, core, b4, b5)
    assert q["inner_core_pixels"] == 16 and q["inner_ndci"] is not None and q["core_brightness"] is not None


def test_signal_quality_on_dark_water_gives_none_where_nothing_is_measurable():
    core, scl = _lake()
    b4 = np.zeros(core.shape)
    b5 = np.zeros(core.shape)
    q = signal_quality(scl, core, b4, b5)
    assert q["core_brightness"] == 0.0 and q["index_iqr"] is None and q["inner_ndci"] is None


def test_low_signal_rule():
    assert ex.low_signal(0.0066, 0.49) is True
    assert ex.low_signal(0.0149, 0.01) is True
    assert ex.low_signal(0.03, 0.10) is True
    assert ex.low_signal(0.03, 0.09) is False
    assert ex.low_signal(None, None) is None
    assert ex.low_signal(None, 0.2) is True and ex.low_signal(0.05, None) is False


def _rows_with_signal():
    f = _refresh_rows()
    f["core_brightness"] = [0.0066, np.nan, np.nan, np.nan, np.nan]
    f["index_iqr"] = [0.49, np.nan, np.nan, np.nan, np.nan]
    f["inner_ndci"] = [0.0068, np.nan, np.nan, np.nan, np.nan]
    return f


def test_a_refreshed_row_carries_its_signal_and_mark_and_the_latest_block_shows_it():
    f = _features([("2026-09-20", "C", "T1", 95, 100, True, -0.02)])
    base = {"lake_id": "bw-x", "name": "X", "water_body": "X", "lat": 52.6, "lon": -0.7, "site_ids": {}}
    info = {"source": "refresh:test", "set": "pilot", "from": "2026-10-01", "to": "2026-10-30"}
    lk = ex.lake_record(base, f, {"tiles": {"T1": {"n_core": 100, "passes": True}}}, {}, "every_scene", [],
                        date(2026, 10, 30), "2026-09-30")
    ex.apply_refresh(lk, _rows_with_signal(), info, date(2026, 10, 30))
    shown = next(x for x in lk["series"] if x["item_id"] == "R1")
    assert shown["core_brightness"] == 0.0066 and shown["index_iqr"] == 0.49 and shown["inner_ndci"] == 0.0068
    assert shown["low_signal"] is True
    assert lk["latest"]["item_id"] == "R1" and lk["latest"]["low_signal"] is True
    assert lk["latest"]["core_brightness"] == 0.0066
    # The test-cache reading made before the measurement is not marked either way.
    old = next(x for x in lk["series"] if x["item_id"] == "C")
    assert "low_signal" not in old and "core_brightness" not in old
    assert ex.check({**_doc(), "lakes": [lk]} | {"as_of": "2026-10-30"}) == []


def test_a_row_without_the_measurement_stays_unmarked():
    f = _features([("2026-09-20", "C", "T1", 95, 100, True, -0.02)])
    base = {"lake_id": "bw-x", "name": "X", "water_body": "X", "lat": 52.6, "lon": -0.7, "site_ids": {}}
    info = {"source": "refresh:test", "set": "pilot", "from": "2026-10-01", "to": "2026-10-30"}
    lk = ex.lake_record(base, f, {"tiles": {"T1": {"n_core": 100, "passes": True}}}, {}, "every_scene", [],
                        date(2026, 10, 30), "2026-09-30")
    ex.apply_refresh(lk, _refresh_rows(), info, date(2026, 10, 30))
    shown = next(x for x in lk["series"] if x["item_id"] == "R1")
    assert "low_signal" not in shown and "low_signal" not in lk["latest"]


def test_check_holds_the_mark_to_the_rule():
    d = _doc()
    lk = d["lakes"][0]
    lk["series"][0].update({"core_brightness": 0.05, "index_iqr": 0.02, "inner_ndci": 0.01, "low_signal": False})
    assert ex.check(copy.deepcopy(d)) == []
    bad = copy.deepcopy(d)
    bad["lakes"][0]["series"][0]["low_signal"] = True
    assert any("low_signal does not follow" in e for e in ex.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][0]["series"][0].update({"core_brightness": 0.004, "low_signal": False})
    assert any("low_signal does not follow" in e for e in ex.check(bad))
    bad = copy.deepcopy(d)
    bad["lakes"][0]["latest"].update({"core_brightness": 0.004, "index_iqr": 0.3, "low_signal": False})
    assert any("latest.low_signal" in e for e in ex.check(bad))


def test_the_rule_is_published_with_the_file():
    assert ex.LOW_SIGNAL == {"brightness_below": 0.015, "iqr_at_least": 0.10}
    assert ex.VERSION == "1.4.0"
    assert isinstance(pd.DataFrame(_rows_with_signal()), pd.DataFrame)
