"""The shore-margin check (docs/SATELLITE-SHORE-MARGIN-2026-11.md): its margins nest, and margin 1 is exactly the
satellite test's core rule. The caches it reads are private, so this tests the rule on made-up grids."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "lake_algae_sat_eval"))
import protocol as pr  # noqa: E402
import satellite_shore_margin as S  # noqa: E402


def test_margin_one_is_the_core_rule_and_margins_nest():
    rng = np.random.default_rng(1)
    for _ in range(50):
        piece = rng.random((30, 30)) > 0.25
        site = piece & (rng.random((30, 30)) > 0.1)
        m = [S.kept(piece, site, k) for k in S.MARGINS]
        assert np.array_equal(m[1], pr.core_pixels(piece, site))
        assert np.array_equal(m[0], site)
        assert all((m[k + 1] & ~m[k]).sum() == 0 for k in range(3))   # each margin keeps a subset of the last


def test_a_square_lake_loses_one_ring_a_margin():
    piece = np.zeros((12, 12), dtype=bool)
    piece[1:11, 1:11] = True   # a 10 x 10 lake inside land
    assert [int(S.kept(piece, piece, k).sum()) for k in S.MARGINS] == [100, 64, 36, 16]


def test_pick_spreads_across_sites_and_is_seeded():
    pop = [{"bw_id": f"s{s}", "item_id": f"i{i}", "tile": "T", "cached": 0.0} for s in range(3) for i in range(10)]
    a, b = S.pick(pop, n=7), S.pick(pop, n=7)
    assert a == b
    counts = sorted(sum(r["bw_id"] == s for r in a) for s in ("s0", "s1", "s2"))
    assert counts == [2, 2, 3]
    assert len({(r["bw_id"], r["item_id"]) for r in a}) == 7


def test_pick_stops_when_sites_run_out():
    pop = [{"bw_id": "s0", "item_id": "i0", "tile": "T", "cached": 0.0}]
    assert len(S.pick(pop, n=5)) == 1


def test_describe_words_follow_the_protocol():
    spread = 0.1
    assert S.describe(np.full(20, 0.005), spread)["words"] == "barely moves"
    assert S.describe(np.full(20, 0.03), spread)["words"] == "moves materially"
    assert S.describe(np.full(20, 0.015), spread)["words"] == "moves somewhat"
    d = S.describe(np.array([-0.01, 0.0, 0.02]), spread)
    assert d["share_below_zero"] == round(1 / 3, 3) and d["max_abs"] == 0.02
