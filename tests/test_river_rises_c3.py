"""scripts/river_rises_eval/c3.py (docs/RIVER-RISES-C3-2026-11.md) on synthetic rows: the blocks, the embargo, the
base rates from the gauge's own history only, no label reaching its own prediction, the thresholds, the onset leads,
the cut at 24 October 2026 and the frozen models' replay."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from river_rises_eval import c3
from river_rises_eval import protocol as pr


def _rows(seed=0, gauges=10, step_h=6) -> pd.DataFrame:
    """Synthetic rows over the whole development period: every model input, a population flag, a 3 h label that
    depends on the inputs and on the gauge, folds by system."""
    rng = np.random.default_rng(seed)
    issues = pd.date_range(c3.DEV_START, c3.DEV_END, freq=f"{step_h}h", inclusive="left")
    out = []
    for k in range(gauges):
        n = len(issues)
        d = {c: rng.normal(size=n) for c in c3.COLS["C3"] if c != "br_logit"}
        for c in [c for c in d if c.endswith("_missing")]:
            d[c] = (rng.random(n) < 0.05).astype(float)
        z = -4 + 1.2 * d["spot_rise1"] + 0.8 * d["rain3"] + 0.4 * k / gauges
        y = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(float)
        y[rng.random(n) < 0.02] = np.nan
        df = pd.DataFrame(d)
        df.insert(0, "issue", issues)
        df.insert(1, "gauge", f"G{k}")
        df.insert(2, "system", f"S{k % 6}")
        df["month"] = issues.month
        df["in_P"] = rng.random(n) > 0.05
        df["word"] = np.where(df["in_P"], "none", "rising fast")
        df["y3"] = y
        out.append(df)
    rows = pd.concat(out, ignore_index=True)
    rows["fold"] = rows["system"].map(pr.system_folds(rows["system"])).astype(int)
    return rows


def test_blocks_hold_whole_label_windows_and_cover_the_period():
    t = pd.Series(pd.DatetimeIndex(["2024-11-21 00:00", "2025-01-31 21:00", "2025-01-31 22:00", "2026-10-24 21:00",
                                    "2026-10-24 22:00", "2026-10-25 00:00"], tz="UTC"))
    vb, blk = c3.blocks_of(t, 3)
    assert vb.tolist() == [0, 0, -1, 7, -1, -1]
    assert blk.tolist() == [0, 0, 0, 7, 7, -1]


def test_base_tables_drop_every_day_touching_an_excluded_interval():
    days = pd.date_range("2025-03-01", periods=10, freq="D", tz="UTC")
    dc = pd.DataFrame({"gauge": "G", "day": days, "month": 3, "sum": 1.0, "count": 10.0})
    a, z = pd.Timestamp("2025-03-03 12:00", tz="UTC"), pd.Timestamp("2025-03-05 00:00", tz="UTC")
    tab = c3.base_tables(dc, [(a, z)])
    assert tab["g"].loc["G", "count"] == 80.0   # 3 and 4 March dropped; 5 March starts at z, kept


def test_rates_fall_back_and_shrink_as_stated():
    dc = pd.DataFrame({"gauge": ["A", "A", "B"], "day": pd.DatetimeIndex(["2025-01-01", "2025-02-01", "2025-01-01"], tz="UTC"),
                       "month": [1, 2, 1], "sum": [2.0, 0.0, 6.0], "count": [100.0, 50.0, 100.0]})
    tab = c3.base_tables(dc, [])
    r1, r1s = c3.rates(tab, ["A", "A", "C"], [1, 3, 1])
    pool = 8 / 250
    r_a = (2 + c3.M_GAUGE * pool) / (150 + c3.M_GAUGE)
    assert r1[0] == pytest.approx(0.02) and r1[1] == pytest.approx(2 / 150) and r1[2] == pytest.approx(pool)
    assert r1s[0] == pytest.approx((2 + c3.M_MONTH * r_a) / (100 + c3.M_MONTH))
    assert r1s[1] == pytest.approx(r_a)
    assert r1s[2] == pytest.approx(pool)


def test_a_validation_cells_own_labels_never_reach_its_predictions():
    rows = _rows()
    base = c3.cross_validate(rows, ("R1", "R1s", "R3", "C3"), 3)
    vb, _ = c3.blocks_of(rows["issue"], 3)
    cell = (vb == 4) & (rows["fold"].to_numpy() == 1) & rows["in_P"].to_numpy()
    assert cell.sum() > 50
    flipped = rows.copy()
    flipped.loc[cell, "y3"] = 1 - flipped.loc[cell, "y3"]
    again = c3.cross_validate(flipped, ("R1", "R1s", "R3", "C3"), 3)
    for m in ("R1", "R1s", "R3", "C3"):
        assert np.allclose(base.loc[cell, m], again.loc[cell, m], equal_nan=True), m
        assert np.allclose(base.loc[cell, f"thr_{m}_0.01"], again.loc[cell, f"thr_{m}_0.01"], equal_nan=True), m
    # ... while the same flip does reach other folds' predictions in other blocks (the check can fail)
    other = (vb == 2) & (rows["fold"].to_numpy() != 1) & rows["in_P"].to_numpy()
    assert not np.allclose(base.loc[other, "C3"], again.loc[other, "C3"])


def test_labels_inside_the_embargo_never_reach_a_validation_block():
    rows = _rows(seed=1)
    vb, _ = c3.blocks_of(rows["issue"], 3)
    a, z = c3.zone(3, 3)
    t = pd.DatetimeIndex(rows["issue"])
    near = ((t >= a) & (t < z)) & (vb != 3)   # the embargo zone around block 4, outside the block itself
    assert near.sum() > 0
    flipped = rows.copy()
    flipped.loc[near, "y3"] = 1 - flipped.loc[near, "y3"].fillna(0)
    base = c3.cross_validate(rows, ("R1s", "C3"), 3)
    again = c3.cross_validate(flipped, ("R1s", "C3"), 3)
    val = (vb == 3) & rows["in_P"].to_numpy()
    assert np.allclose(base.loc[val, "C3"], again.loc[val, "C3"], equal_nan=True)
    assert np.allclose(base.loc[val, "R1s"], again.loc[val, "R1s"], equal_nan=True)


def test_forward_only_training_reads_nothing_after_the_block():
    rows = _rows(seed=2)
    vb, _ = c3.blocks_of(rows["issue"], 3)
    later = pd.DatetimeIndex(rows["issue"]) >= c3.BLOCK_EDGES[5]
    flipped = rows.copy()
    flipped.loc[later, "y3"] = 1 - flipped.loc[later, "y3"].fillna(0)
    base = c3.cross_validate(rows, ("R1", "C3"), 3, forward=True)
    again = c3.cross_validate(flipped, ("R1", "C3"), 3, forward=True)
    val = (vb == 4) & rows["in_P"].to_numpy()
    assert np.isfinite(base.loc[val, "C3"]).all()
    assert np.allclose(base.loc[val, "C3"], again.loc[val, "C3"])
    assert np.allclose(base.loc[val, "R1"], again.loc[val, "R1"])
    assert base.loc[(vb == 1) & rows["in_P"].to_numpy(), "C3"].isna().all()   # blocks 1 and 2 have no forward model


def test_threshold_is_the_upper_quantile_of_training_predictions():
    p = np.linspace(0, 1, 1001)
    assert c3.threshold(p, 0.01) == pytest.approx(0.99)
    assert np.mean(p >= c3.threshold(p, 0.02)) == pytest.approx(0.02, abs=0.002)


def test_onset_lead_counts_consecutive_alert_hours_before_the_sites_word():
    t = pd.date_range("2025-03-01", periods=10, freq="1h", tz="UTC")
    res = pd.DataFrame({"gauge": "G", "system": "S", "issue": t,
                        "word": ["none"] * 7 + ["rising fast"] + ["none"] * 2})
    alert = np.array([0, 0, 0, 0, 1, 1, 1, np.nan, 0, 0], dtype=float)
    out = c3.onset_leads(res, alert)
    assert len(out) == 1 and out["lead_h"].iloc[0] == 3 and bool(out["caught"].iloc[0])


def test_cut_drops_every_reading_at_or_after_the_end():
    s = pd.Series(np.arange(5.0), index=pd.date_range("2026-10-24 23:30", periods=5, freq="15min", tz="UTC"))
    out = c3.cut(s, c3.DEV_END)
    assert out.index.max() < c3.DEV_END and len(out) == 2


def test_frozen_replay_equals_the_fitted_model():
    rows = _rows(seed=3, gauges=4)
    m = rows["in_P"] & rows["y3"].notna()
    X = rows[m].assign(br_logit=-4.0)
    model = c3.fit_model(X, X["y3"].to_numpy(), c3.COLS["C3"])
    frozen = {"horizon_h": 3, "base_rates": {g: {"R1": {str(k): 0.01 for k in range(1, 13)},
                                                 "R1s": {str(k): 1 / (1 + np.exp(4)) for k in range(1, 13)}}
                                             for g in rows["gauge"].unique()},
              "models": {k: {"coef": model.coef, "intercept": model.intercept, "mean": model.mean, "scale": model.scale,
                             "gauges": list(rows["gauge"].unique()), "thresholds": {str(q): 0.5 for q in c3.ALERT_RATES}}
                         for k in ("R3", "C2", "C3", "C3n")}}
    frozen["models"]["R1"] = frozen["models"]["R1s"] = {"thresholds": {str(q): 0.5 for q in c3.ALERT_RATES}}
    out = c3.predict_frozen(frozen, rows[m].reset_index(drop=True))
    assert np.allclose(out["C3"].to_numpy(), model.predict(X), atol=1e-9)


def test_fresh_refuses_without_a_statement_naming_the_frozen_file(tmp_path):
    fz = tmp_path / "frozen.json"
    fz.write_text(json.dumps({"horizon_h": 3}))
    st = tmp_path / "statement.json"
    st.write_text(json.dumps({"frozen_sha256": "0" * 64}))
    args = type("A", (), {"frozen": fz, "statement": st, "data": tmp_path, "out": tmp_path, "radar": None})()
    with pytest.raises(SystemExit, match="SHA-256"):
        c3.stage_fresh(args)
