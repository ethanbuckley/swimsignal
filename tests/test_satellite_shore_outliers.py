"""The shore-margin outlier check (docs/SATELLITE-SHORE-OUTLIERS-2026-11.md): its diagnostics and flags on made-up
windows (the caches are private), and the integrity of the published values."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lake_algae_sat_eval"))
import protocol as pr  # noqa: E402
import satellite_shore_outliers as O  # noqa: E402
from satellite_shore_margin import kept  # noqa: E402


def square_lake(n=12, pad=3):
    """A 6 x 6 lake: 16 one-pixel core pixels, of which 12 are the rim and 4 are inner."""
    piece = np.zeros((n, n), dtype=bool)
    piece[pad:n - pad, pad:n - pad] = True
    masks = {k: kept(piece, piece, k) for k in (0, 1, 2)}
    scl = np.where(piece, pr.WATER, 4).astype(np.uint8)
    return piece, masks, scl


def test_diagnostics_reproduce_the_protocol_readings_and_see_a_bright_rim():
    piece, masks, scl = square_lake()
    b4 = np.full(piece.shape, 0.02)
    b5 = np.full(piece.shape, 0.02)
    ring = masks[1] & ~masks[2]
    b5[ring] = 0.03          # the shore rim reads higher in the red edge
    d = O.diagnostics(scl, masks, b4, b5)
    for k in (0, 1, 2):
        assert d[f"k{k}"] == round(pr.scene_reading(scl, masks[k], pr.ndci(b4, b5))[2], 6)
    assert d["k2"] == 0.0 and d["k1"] > 0.1 and d["shift"] < -0.1
    assert d["contrast"] > 0 and d["not_water_in_core"] == 0
    assert d["n_inner"] == int(masks[2].sum()) and 0 < d["ring_share"] < 1
    assert d["brightness"] >= 0.04 and d["iqr"] >= 0


def test_flags_fire_on_dark_spread_and_narrow_only():
    assert O.flags({"brightness": 0.01, "iqr": 0.01, "ring_share": 0.1}) == {"dark": True, "spread": False, "narrow": False, "any": True}
    assert O.flags({"brightness": 0.03, "iqr": 0.2, "ring_share": 0.1}) == {"dark": False, "spread": True, "narrow": False, "any": True}
    assert O.flags({"brightness": 0.03, "iqr": 0.01, "ring_share": 0.5}) == {"dark": False, "spread": False, "narrow": True, "any": True}
    assert O.flags({"brightness": 0.03, "iqr": 0.01, "ring_share": 0.1})["any"] is False
    assert O.flags({"brightness": None, "iqr": None, "ring_share": None})["any"] is False


def test_evaluate_counts_moved_against_flagged():
    rows = [{"shift": 0.05, "flags": {"dark": True, "spread": False, "narrow": False, "any": True}},
            {"shift": -0.03, "flags": {"dark": False, "spread": False, "narrow": False, "any": False}},
            {"shift": 0.001, "flags": {"dark": True, "spread": False, "narrow": False, "any": True}},
            {"shift": None, "flags": {"dark": True, "spread": True, "narrow": True, "any": True}}]
    e = O.evaluate(rows)
    assert e["scenes"] == 3 and e["moved"] == 2
    assert e["dark"] == {"flagged": 2, "moved_and_flagged": 1, "moved_not_flagged": 1,
                         "median_abs_shift_flagged": 0.0255, "median_abs_shift_unflagged": 0.03}


def test_choose_pairs_is_seeded_one_a_site_and_skips_taken_scenes():
    pairs = [{"site": f"s{i % 3}", "date": f"2026-06-{i + 1:02d}", "tile": "T", "items": [f"a{i}", f"b{i}"],
              "cached": [0.0, r], "range": r} for i, r in enumerate([0.3, 0.25, 0.4, 0.21, 0.01, 0.005, 0.02, 0.015, 0.1])]
    a = O.choose_pairs(pairs, taken={("s0", "a0")}, each=2)
    assert a == O.choose_pairs(pairs, taken={("s0", "a0")}, each=2)
    assert [p["kind"] for p in a] == ["big", "big", "small", "small"]
    assert all(p["items"][0] != "a0" for p in a)
    for kind in ("big", "small"):
        sites = [p["site"] for p in a if p["kind"] == kind]
        assert len(sites) == len(set(sites))


def test_published_values_hold_the_protocol():
    d = json.loads((ROOT / "data/research/satellite_shore_outliers_2026_11.json").read_text())
    assert d["fingerprint_unchanged"] is True
    assert d["network"]["requests"] <= d["caps"]["requests"] and d["network"]["bytes"] <= d["caps"]["bytes"]
    assert d["completed"] == d["selected"] == len(d["rows"]) == 26
    assert len({(r["site"], r["id"]) for r in d["rows"]}) == 26
    for r in d["rows"]:
        if r["cached"] is not None:
            assert abs(r["k1"] - r["cached"]) <= 1e-6
        assert r["flags"] == O.flags(r)
    assert d["pair_test"]["big"] == {"n": 5, "extreme_dark_or_spread": 5}
    assert d["pair_test"]["small"] == {"n": 4, "either_dark_or_spread": 1}
    both = d["flags_on_both"]
    assert both["scenes"] == 76 and both["moved"] == 17 and both["any"]["moved_not_flagged"] == 0
    serpentine = next(r for r in d["rows"] if r["id"] == "S2C_T30UXC_20260624T111341_L2A")
    assert serpentine["brightness"] < O.DARK and serpentine["flags"]["dark"]
