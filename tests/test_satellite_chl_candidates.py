"""Quality-aware chlorophyll candidates (docs/SATELLITE-CHL-CANDIDATES-2026-11.md): each candidate, the nested floor
choice, the holdouts and the pre-stated support rule, on made-up samples (the caches are private)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lake_algae_sat_eval"))
import protocol as pr  # noqa: E402
import satellite_chl_candidates as K  # noqa: E402


def frame(seed=0, lakes=10, per_lake=8, noisy_share=0.25):
    """Samples whose reading tracks log chlorophyll, except noisy (dark, spread) ones, whose reading is noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(lakes):
        level = 0.4 + 1.2 * i / lakes
        for j in range(per_lake):
            y = level + rng.normal(0, 0.25)
            noisy = rng.random() < noisy_share
            x = (y - 1) * 0.3 + rng.normal(0, 0.02) if not noisy else rng.normal(-0.2, 0.3)
            b, iqr = (0.008, 0.25) if noisy else (0.05, 0.03)
            rows.append({"wb_id": f"L{i}", "season": (2021, 2023, 2024, 2025, 2026)[j % 5], "log_chl": y, "x0": x,
                         "flag0": noisy, "b0": b, "q_iqr": iqr, "q0": float(K.noise_score(b, iqr)),
                         **{f"px_{f:.3f}": (x if not noisy or f < 0.008 else np.nan) for f in K.PIXEL_GRID},
                         "xe": np.nan if noisy else x})
    return pd.DataFrame(rows)


def test_reference_counts_every_lake_once():
    d = pd.DataFrame({"wb_id": ["a", "a", "a", "b"], "log_chl": [1.0, 1.0, 1.0, 3.0]})
    assert K.reference(d) == 2.0


def test_pixel_filter_drops_dark_pixels_and_needs_nine():
    core = np.zeros((8, 8), bool)
    core[1:7, 1:7] = True                    # 36 core pixels
    scl = np.where(core, pr.WATER, 4).astype(np.uint8)
    b4 = np.full(core.shape, 0.02)
    b5 = np.full(core.shape, 0.03)
    b4[1:4, 1:7], b5[1:4, 1:7] = 0.001, 0.003     # 18 dark pixels with a high index
    full = pr.scene_reading(scl, core, pr.ndci(b4, b5))[2]
    kept = K.pixel_filtered(scl, core, b4, b5, 0.010)
    assert abs(kept - 0.2) < 1e-12 and full > kept
    assert K.pixel_filtered(scl, core, b4, b5, 0.06) is None      # too few bright pixels
    cloudy = scl.copy()
    cloudy[core] = 9
    assert K.pixel_filtered(cloudy, core, b4, b5, 0.0) is None     # not a usable scene
    v = K.scene_values(scl, core, b4, b5)
    assert v["reading"] == full and v["px_0.010"] == kept and v["low_signal"] in (True, False)


def test_noise_score_rises_with_spread_and_darkness():
    assert K.noise_score(0.05, 0.03) < K.noise_score(0.05, 0.3) and K.noise_score(0.05, 0.03) < K.noise_score(0.005, 0.03)
    assert np.isfinite(K.noise_score(-0.001, 0.0))


def test_fgls_downweights_noisy_rows():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 400)
    q = rng.random(400)
    y = 1 + 2 * x + rng.normal(0, 0.05 + 2 * (q > 0.8))
    a, b, c, g = K.fgls(x, y, q)
    assert g > 0 and abs(b - 2) < abs(np.polyfit(x, y, 1)[0] - 2) + 0.05 and abs(a - 1) < 0.2


def test_candidates_predict_with_reference_fallback():
    d = frame()
    train, test = d[d["wb_id"] != "L0"], d[d["wb_id"] == "L0"]
    R = K.reference(train)
    for c in K.CANDIDATES:
        p, h, note = K.predict(c, train, test, "lake")
        assert len(p) == len(test) and np.isfinite(p).all()
        assert np.allclose(p[~h], R)
        if c == "A":
            assert (h == ~test["flag0"].to_numpy()).all()
        if c == "D":
            assert note["floor"] in K.PIXEL_GRID
    p, h, _ = K.predict("B0", train.assign(x0=np.nan), test, "lake")
    assert not h.any() and np.allclose(p, R)


def test_floor_choice_uses_training_rows_only():
    d = frame()
    f = K.choose_floor(d[d["wb_id"] != "L1"], "lake")
    d2 = d.copy()
    d2.loc[d2["wb_id"] == "L1", "log_chl"] = 99.0          # the held-out lake cannot move the choice
    assert K.choose_floor(d2[d2["wb_id"] != "L1"], "lake") == f


def test_holdouts_and_measures_on_noisy_readings():
    d = frame(lakes=12, per_lake=10)
    res = {h: K.run_holdout(d, h) for h in K.HOLDOUTS}
    assert res["lake"]["rows"].all() and res["season"]["rows"].all()
    assert res["forward"]["rows"].sum() == d["season"].isin(K.FORWARD_TEST).sum()
    m = K.measures(d, res["lake"])
    assert m["rows"] == len(d) and m["B0"]["coverage"] == 1.0 and m["A"]["coverage"] < 1.0
    assert m["A"]["vs_B0"]["skill"]["d"] > 0 and m["A"]["skill"]["L"] <= m["A"]["skill"]["value"] <= m["A"]["skill"]["U"]
    assert m["B0"]["skill"]["value"] < m["A"]["skill"]["value"]
    assert set(m["D"]["floors_chosen"]) == {f"{f:.3f}" for f in K.PIXEL_GRID}


def test_support_rule_and_words():
    def block(gain, lo):
        return {"skill": {"value": 0.2 + gain}, "coverage": 0.8, "vs_B0": {"skill": {"d": gain, "L": lo, "U": gain + 0.1}}}
    res = {pop: {h: {"B0": {"skill": {"value": 0.2}, "coverage": 1.0},
                     **{c: block(0.05, -0.02) for c in K.CANDIDATES[1:]}} for h in K.HOLDOUTS} for pop in ("paired", "all")}
    res["paired"]["lake"]["B"] = block(0.02, -0.02)            # gain too small
    res["paired"]["lake"]["C"] = block(0.05, -0.08)            # plausible harm
    res["paired"]["forward"]["D"] = block(-0.01, -0.1)         # loses on the forward years
    res["paired"]["lake"]["E"] = block(0.0, -0.03)             # not on the paired samples ...
    s = K.support(res)                                         # ... but on every sample (coverage)
    assert s["A"]["supported"] and not s["B"]["supported"] and not s["C"]["supported"] and not s["D"]["supported"]
    assert s["E"]["supported"] and not s["E"]["paired"]["condition_1"]
    w = K.words(res, s)
    assert "condition 1" in w[1] and "condition 2" in w[3] and "every sample" in w[4] and w[5].startswith("Shadow log")
    assert "seen 2021-2026" in w[-1]


def test_settings_are_the_stated_ones():
    assert (K.MAX_REQUESTS, K.MAX_BYTES, K.SEED, K.WINDOW) == (4500, int(2.5 * 1024**3), 20261106, 3)
    assert K.PIXEL_GRID == (0.005, 0.010, 0.015, 0.020) and K.MIN_PIXELS == 9
    assert (K.GAIN, K.HARM) == (0.03, -0.05) and K.FORWARD_TRAIN == (2021, 2023, 2024)
