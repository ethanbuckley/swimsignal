"""The low-signal check against lab chlorophyll (docs/SATELLITE-LOW-SIGNAL-CHLOROPHYLL-2026-11.md): its measures,
order and pre-stated words on made-up pairs (the caches are private), and the integrity of the published values."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import satellite_low_signal_chl as L  # noqa: E402


def lakes_frame(seed=1, lakes=8, per_lake=6, within=1.0, noise=0.0):
    """Lakes at different chlorophyll levels; within a lake the reading follows chlorophyll with slope `within`."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(lakes):
        level = i / lakes
        for j in range(per_lake):
            chl = level + rng.normal(0, 0.2)
            rows.append({"wb_id": f"L{i}", "season": 2021 + j % 3, "lake_type": "shallow" if i % 2 else "deeper",
                         "log_chl": chl, "reading": within * (chl - level) + 0.5 * level + rng.normal(0, noise),
                         "low_signal": False, "dark": False, "spread": False})
    return pd.DataFrame(rows)


def test_within_lake_rho_ignores_lake_levels():
    f = lakes_frame(within=-1.0)        # between lakes the reading rises with level; within each lake it falls
    assert L.cp.spearman(f["reading"], f["log_chl"]) > 0
    assert L.within_lake_rho(f) < -0.9
    x, y = L.demeaned(f.assign(wb_id=[f"S{i}" for i in range(len(f))]), "reading")
    assert np.isnan(x).all() and np.isnan(y).all()     # a lake with one pair has no within-lake value


def test_measures_hold_the_pooled_and_within_lake_figures_with_intervals():
    f = lakes_frame()
    m = L.measures(f)
    assert m["pairs"] == 48 and m["lakes"] == 8
    assert m["pooled"]["L"] <= m["pooled"]["rho"] <= m["pooled"]["U"]
    assert abs(m["pooled"]["rho"] - L.cp.spearman(f["reading"], f["log_chl"])) < 1e-12
    assert abs(m["within_lake"]["rho"] - L.within_lake_rho(f)) < 1e-12
    assert m["per_lake"]["lakes_with_3"] == 8 and m["test_conditions"]["gate"]["pairs"] == 48
    assert "verdict" not in m["test_conditions"]
    assert L.measures(f.head(2)) == {"reading": "reading", "pairs": 2, "lakes": 1}


def test_paired_difference_is_zero_for_the_same_rows_and_moves_when_noise_pairs_go():
    f = lakes_frame()
    same = L.paired_difference(f, np.ones(len(f), bool), "reading", "reading")
    assert same["pairs_a"] == same["pairs_b"] == 48
    assert same["pooled"] == {"d": 0.0, "L": 0.0, "U": 0.0, "draws_without_value": 0}
    g = f.copy()
    rng = np.random.default_rng(3)
    noisy = rng.random(len(g)) < 0.25
    g.loc[noisy, "reading"] = rng.normal(0, 5, int(noisy.sum()))    # a quarter of the pairs become noise
    d = L.paired_difference(g, ~noisy, "reading", "reading")
    assert d["pairs_b"] == int((~noisy).sum()) and d["pooled"]["d"] > 0 and d["within_lake"]["d"] > 0
    assert d["pooled"]["L"] <= d["pooled"]["d"] <= d["pooled"]["U"]
    g["inner"] = g["reading"]
    g.loc[g.index[:5], "inner"] = np.nan
    e = L.paired_difference(g, g["inner"].notna(), "reading", "inner")
    assert e["pairs_a"] == 48 and e["pairs_b"] == 43


def test_flag_share_counts_rules_types_and_lakes():
    f = lakes_frame(lakes=4, per_lake=4)
    f["dark"] = [i % 4 == 0 for i in range(len(f))]
    f["spread"] = [i % 8 == 0 or i == 1 for i in range(len(f))]
    f["low_signal"] = f["dark"] | f["spread"]
    f.loc[f.index[-4:], "low_signal"] = True      # the whole last lake
    f.loc[f.index[-4:], ["dark", "spread"]] = True
    s = L.flag_share(f)
    assert s["pairs"] == 16 and s["flagged"] == int(f["low_signal"].sum()) and s["share"] == round(s["flagged"] / 16, 4)
    assert s["dark_only"] + s["spread_only"] + s["both"] == s["flagged"]
    assert s["lakes_every_pair_flagged"] == 1 and s["lakes"] == 4
    assert sum(v["pairs"] for v in s["by_lake_type"].values()) == 16
    assert s["by_lake_type"]["no_depth"] == {"pairs": 0, "flagged": 0}


def test_read_order_is_seeded_and_round_robin_over_points():
    scenes = [{"point": p, "item_id": f"{p}-{i}"} for p in ("a", "b", "c") for i in range(3 if p != "c" else 1)]
    scenes.append({"point": "a", "item_id": "a-0"})     # a scene two samples share is read once
    order = L.read_order(scenes)
    assert order == L.read_order(scenes) and len(order) == 7
    assert sorted(s["point"] for s in order[:3]) == ["a", "b", "c"]      # the first round holds every point
    assert order != L.read_order(scenes, seed=1)


def _d(p, w, lp=None, lw=None):
    return {"pooled": {"d": p, "L": p - 0.1 if lp is None else lp, "U": p + 0.1},
            "within_lake": {"d": w, "L": w - 0.1 if lw is None else lw, "U": w + 0.1}}


def test_reading_in_words_follows_the_pre_stated_cases():
    noise = L.reading_in_words(0.2, _d(0.05, 0.06, lp=0.01), _d(0.0, 0.0))
    assert "common, not frequent" in noise[0] and "noise relative to lab chlorophyll" in noise[1]
    assert "makes no difference" in noise[2] and "verdict is unchanged" in noise[-1]
    none = L.reading_in_words(0.05, _d(0.01, -0.02), _d(0.04, 0.0))
    assert "rare" in none[0] and "no change" in none[1] and "stays a display note" in none[1]
    assert "inner higher" in none[2]
    loses = L.reading_in_words(0.35, _d(-0.04, 0.02), _d(-0.05, 0.0))
    assert "too broad" in loses[0] and "carry information" in loses[1] and "core higher" in loses[2]
    mixed = L.reading_in_words(0.2, _d(0.05, 0.01), _d(0.0, 0.0), _d(0.02, 0.03))
    assert mixed[1].startswith("Mixed") and "inconclusive" in mixed[1] and "inner-core reading the flag" in mixed[3]
    up_but_wide = L.reading_in_words(0.2, _d(0.05, 0.06, lp=-0.2, lw=-0.2), _d(0.0, 0.0))
    assert up_but_wide[1].startswith("Mixed") and "no paired interval excluding zero" in up_but_wide[1]
    assert L.size_word(0.01) == "no change" and L.size_word(-0.05) == "a small change" and L.size_word(0.2) == "a large change"


def test_thresholds_are_the_contracts_and_the_stated_ones():
    assert L.LOW_SIGNAL == {"brightness_below": 0.015, "iqr_at_least": 0.10}
    assert L.low_signal(0.01, 0.01) is True and L.low_signal(0.02, 0.10) is True and L.low_signal(0.02, 0.05) is False
    assert L.low_signal(None, None) is None
    assert (L.MAX_REQUESTS, L.MAX_BYTES) == (1000, 600 * 1024**2) and L.SEED == 20261105
    assert (L.SMALL, L.LARGE, L.RARE, L.FREQUENT) == (0.03, 0.10, 0.10, 0.30)
