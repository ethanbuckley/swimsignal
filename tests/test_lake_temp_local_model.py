"""scripts/lake_temp_local_model (docs/LAKE-TEMP-LOCAL-MODEL-2026-11.md), on synthetic data only: no archive value.
Lake classes, the basin merge, folds, the candidate's choice of tau and form inside training rows, the two-way
bootstrap, the verdict, and the live route as the harness computes it against estimate_any."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lake_temp_local_model"))
import llm_protocol as P  # noqa: E402


def test_classes_from_depth():
    got = P.lake_class([np.nan, 0.7, 2.99, 3.0, 9.9, 10.0, 23.0])
    assert list(got) == ["no depth", "shallow", "shallow", "mid", "mid", "deep", "deep"]


def test_connected_basins_and_nearby_points_merge():
    groups = pd.Series(["lake:N", "lake:S", "lake:X", "own:1", "os:2", "own:3"])
    how = pd.Series(["WFD polygon", "WFD polygon", "WFD polygon", "own water", "OS lake link", "own water"])
    w = P.merge_groups(groups, how, [("lake:N", "lake:S")], {"own:1": "lake:S", "os:2": "lake:X"})
    assert w[0] == w[1] == w[3] == "lake:N"
    assert w[2] == w[4] == "lake:X"
    assert w[5] == "own:3"


def test_folds_are_stable_and_spread():
    assert P.fold_of("lake:GB31247007") == P.fold_of("lake:GB31247007")
    assert len({P.fold_of(f"w{i}") for i in range(200)}) == P.N_FOLDS


def synthetic(n_waters=60, seed=0):
    """Deep lakes lag the air (follow e45, cooler in May); others follow e5."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_waters):
        cls = "deep" if i % 3 == 0 else "no depth"
        water = f"w{i}"
        for year in (2012, 2013):
            for doy in range(121, 274, 4):
                date = pd.Timestamp(f"{year}-01-01") + pd.Timedelta(days=doy - 1)
                air = 10 + 8 * np.sin(np.pi * (doy - 100) / 200) + rng.normal(0, 2)
                e = {f"e{t}": air + rng.normal(0, 0.3) - (0.02 * t if doy < 160 else 0) for t in P.TAUS}
                driver = e["e45"] if cls == "deep" else e["e5"]
                temp = (1.0 + 0.9 * driver) if cls == "deep" else (2.0 + 0.95 * driver)
                rows.append({"water": water, "fold": P.fold_of(water), "cls": cls, "date": date, "year": year,
                             "doy_sin": np.sin(2 * np.pi * doy / 365.25), "doy_cos": np.cos(2 * np.pi * doy / 365.25),
                             "elevation": 100.0 + i, "temp": temp + rng.normal(0, 0.2), **e})
    return pd.DataFrame(rows)


def test_candidate_picks_class_taus_inside_training():
    d = synthetic()
    m = P.fit_candidate(d)
    assert m["form"] in ("K1", "K2")
    assert m["taus"]["deep"] == 45 and m["taus"]["no depth"] == 5
    pred = P.predict_form(m, d)
    assert np.sqrt(np.mean((pred - d["temp"]) ** 2)) < 0.6


def test_small_class_falls_back_to_pooled():
    d = synthetic()
    d.loc[d["water"].isin(["w0", "w3"]), "cls"] = "shallow"          # two waters only
    m = P.fit_candidate(d)
    assert "shallow" not in m["classes"]


def test_form_needs_a_margin():
    assert P.choose_form({"K0": 1.50, "K1": 1.49, "K2": 1.40}) == "K2"
    assert P.choose_form({"K0": 1.50, "K1": 1.49, "K2": 1.475}) == "K0"
    assert P.choose_form({"K0": 1.50, "K1": 1.40, "K2": 1.39}) == "K1"


def test_two_way_bootstrap():
    rng = np.random.default_rng(1)
    n = 600
    waters = rng.integers(0, 40, n)
    years = rng.integers(2000, 2012, n)
    e = rng.normal(0, 1, n)
    b = P.boot(waters, years, e, {"same": e, "worse": 2 * e}, n_boot=300)
    assert b["same"]["gain"] == 0 and b["same"]["lo"] == pytest.approx(0) and b["same"]["hi"] == pytest.approx(0)
    assert b["worse"]["lo"] > 0
    assert b["cand_rmse"]["lo"] < b["cand_rmse"]["value"] < b["cand_rmse"]["hi"]
    w = P.boot(waters, years, e, {"worse": 2 * e}, n_boot=300, two_way=False)
    assert w["worse"]["lo"] > 0


def test_verdict_labels():
    g = {k: {"gain": 0.3, "lo": 0.1, "hi": 0.5} for k in ("live", "live_refit", "air7", "m419")}
    assert P.verdict(40, 400, 1.4, 2.4, g)["label"] == "meets the limit; better than the live route"
    v = P.verdict(40, 400, 1.7, 2.8, g | {"live_refit": {"gain": 0.1, "lo": -0.05, "hi": 0.2}})
    assert v["label"] == "misses the limit; not shown better than the live route"
    assert P.verdict(20, 400, 1.0, 1.0, g)["label"] == "too few to judge"


def test_group_answer():
    good = {"live": {"lo": 0.2}, "live_refit": {"lo": 0.1}}
    assert P.group_answer(25, good) == "better"
    assert P.group_answer(12, good) == "better (few waters)"
    assert P.group_answer(25, {"live": {"lo": -0.05}, "live_refit": {"lo": 0.1}}) == "not harmed"
    assert P.group_answer(25, {"live": {"lo": -0.3}, "live_refit": {"lo": 0.1}}) == "harm not ruled out"
    assert P.group_answer(5, good) == "too few"


@pytest.mark.parametrize("area", [0.3, None, 5.0])
def test_live_route_matches_estimate_any(area):
    """The harness's live route equals what estimate_any shows, once rounded, for small, unknown and large lakes."""
    sys.path.insert(0, str(ROOT / "src"))
    import llm_run as R

    from dipcast.model import water_temp as wt
    m = wt.load(winter_path=None)
    end = "2026-07-14"
    start = pd.Timestamp(end, tz="Europe/London") - pd.Timedelta(days=29)
    t = pd.date_range(start, pd.Timestamp(end, tz="Europe/London") + pd.Timedelta(days=1), freq="h",
                      inclusive="left").tz_convert("UTC")
    hourly = pd.DataFrame({"time": t, "air_c": 14.0 + np.arange(len(t)) / len(t) * 6})
    e = wt.estimate_any(m, hourly, pd.Timestamp(end), "lake", elevation=120.0, lake_area_km2=area)
    air = wt.air_features(m, hourly, pd.Timestamp(end))
    doy = pd.Timestamp(end).day_of_year
    row = pd.DataFrame([{**air, "doy_sin": np.sin(2 * np.pi * doy / 365.25), "doy_cos": np.cos(2 * np.pi * doy / 365.25),
                         "elevation": 120.0, "lake_area_km2": np.nan if area is None else area}])
    assert int(round(R.live_deployed(m, row)[0])) == e["temp_c"]
