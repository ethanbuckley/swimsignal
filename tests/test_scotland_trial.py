"""The Scotland trial (src/dipcast/scotland_trial.py): off by default, Scotland's map on Scottish rows only,
click-anywhere kept to England, the trial's spots and credit only while it is on."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dipcast import config, scotland_trial

ROOT = Path(__file__).resolve().parents[1]
MAP = {"a": 0.44928584513880876, "b": 0.7496750672880154, "spill_stamp": "808da63d"}


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def trial_on(monkeypatch):
    monkeypatch.setattr(config, "SCOTLAND_TRIAL", True)
    monkeypatch.setattr(config, "SCOTTISH_WATER", True)
    monkeypatch.setattr(scotland_trial, "calibration_map", lambda: MAP)


def test_off_unless_both_settings_and_a_map_for_this_model(monkeypatch):
    monkeypatch.setattr(scotland_trial, "calibration_map", lambda: MAP)
    for trial, poll in ((False, False), (True, False), (False, True)):
        monkeypatch.setattr(config, "SCOTLAND_TRIAL", trial)
        monkeypatch.setattr(config, "SCOTTISH_WATER", poll)
        assert not scotland_trial.enabled()
    monkeypatch.setattr(config, "SCOTLAND_TRIAL", True)
    monkeypatch.setattr(config, "SCOTTISH_WATER", True)
    assert scotland_trial.enabled()
    monkeypatch.setattr(scotland_trial, "calibration_map", lambda: None)   # fitted for another spill model
    assert not scotland_trial.enabled()


def test_the_committed_map_names_the_spill_model_it_was_fitted_for():
    m = json.loads((config.PROCESSED / scotland_trial.MAP_FILE).read_text())
    assert m["verdict"] == "PASS" and m["fitted_on"] == [2022, 2023, 2024]
    assert m["spill_stamp"] == MAP["spill_stamp"] and m["a"] == MAP["a"] and m["b"] == MAP["b"]


def test_a_map_for_another_spill_model_switches_the_trial_off(monkeypatch, tmp_path):
    (tmp_path / scotland_trial.MAP_FILE).write_text(json.dumps({**MAP, "spill_stamp": "00000000"}))
    monkeypatch.setattr(config, "PROCESSED", tmp_path)
    scotland_trial.calibration_map.cache_clear()
    try:
        assert scotland_trial.calibration_map() is None
    finally:
        scotland_trial.calibration_map.cache_clear()


def test_scotlands_map_replaces_englands_calibration_on_scottish_rows_only(trial_on):
    ov = pd.DataFrame({"company": ["United Utilities", "Scottish Water", "Thames Water"]})
    p_raw = np.array([[0.1, 0.2], [0.1, np.nan], [0.3, 0.4]])
    p_cal = p_raw * 0.9   # stands for England's lead calibration
    out = scotland_trial.calibrate(p_cal, p_raw, ov)
    assert np.array_equal(out[[0, 2]], p_cal[[0, 2]])
    want = 1 / (1 + np.exp(-(MAP["a"] + MAP["b"] * np.log(0.1 / 0.9))))
    assert out[1, 0] == pytest.approx(want) and out[1, 0] > 0.1   # raised: the model forecast too few spills
    assert np.isnan(out[1, 1])                                    # no rain stays no forecast


def test_without_scottish_rows_nothing_changes(trial_on):
    ov = pd.DataFrame({"company": ["Anglian Water"]})
    p = np.array([[0.2, 0.3]])
    assert scotland_trial.calibrate(p, p * 2, ov) is p


def test_click_anywhere_keeps_to_england():
    ov = pd.DataFrame({"site_id": ["UUU00001", "CSO000001"], "company": ["United Utilities", "Scottish Water"]})
    assert scotland_trial.england_only(ov)["site_id"].tolist() == ["UUU00001"]


def test_the_trial_spots_are_listed_only_while_it_is_on(monkeypatch, trial_on):
    bs = _script("build_site")
    monkeypatch.setattr(bs, "ROOT", ROOT)
    on = bs.load_spots()
    assert set(on.loc[on["trial"] == "scotland", "id"]) == {"sepa-200305", "sepa-366986", "sepa-125079"}
    monkeypatch.setattr(config, "SCOTLAND_TRIAL", False)
    off = bs.load_spots()
    assert "trial" not in off or not (off["trial"] == "scotland").any()


def test_the_trial_spots_are_sepa_lochs_with_their_directory_ids():
    s = pd.read_csv(ROOT / scotland_trial.SPOTS_FILE)
    assert (s["source"] == "sepa").all() and (s["trial"] == "scotland").all() and (s["kind"] == "lake").all()
    assert s["id"].str.fullmatch(r"sepa-\d+").all() and s["lat"].between(55, 61).all()


def test_sepa_rating_and_page_attach_by_id():
    bs = _script("build_site")
    results = [{"id": "sepa-125079", "source": "sepa"}, {"id": "bw-x", "source": "designated"}]
    scot = {"sites": [{"id": "sepa-125079", "rating": {"value": "Good", "year": 2025}, "page": "https://bathingwaters.sepa.org.uk/x"}]}
    assert bs.attach_sepa(results, scot) == 1
    assert results[0]["sepa"] == {"rating": {"value": "Good", "year": 2025}, "page": "https://bathingwaters.sepa.org.uk/x"}
    assert "sepa" not in results[1]


def test_scottish_water_is_credited_only_while_the_trial_is_on(monkeypatch, trial_on):
    bs = _script("build_site")
    on = bs.data_credits("/")
    assert on["attribution"].startswith("Contains Scottish Water data") and bs.SCOTLAND_CREDIT in on["sources"]
    monkeypatch.setattr(config, "SCOTLAND_TRIAL", False)
    off = bs.data_credits("/")
    assert "Scottish Water" not in off["attribution"] and bs.SCOTLAND_CREDIT not in off["sources"]


def test_the_footer_credits_scottish_water_only_while_the_trial_is_on(monkeypatch, trial_on):
    bs = _script("build_site")
    page = bs.TEMPLATE.read_text()
    on = bs.with_scotland_credit(page)
    assert "and Scottish Water's overflow status and event history" in on and on.count("Scotland trial") >= 1
    monkeypatch.setattr(config, "SCOTLAND_TRIAL", False)
    assert bs.with_scotland_credit(page) == page


def test_the_build_passes_the_trial_setting_from_a_repository_variable():
    workflow = (ROOT / ".github" / "workflows" / "site.yml").read_text()
    assert "DIPCAST_SCOTLAND_TRIAL: ${{ vars.DIPCAST_SCOTLAND_TRIAL }}" in workflow


def test_scottish_spots_are_not_checked_against_englands_water_bodies(tmp_path):
    bs = _script("build_site")
    path = tmp_path / "rnags.json"
    path.write_text(json.dumps({"spots": {"bw-x": None}, "water_bodies": {}}))
    results = [{"id": "bw-x"}, {"id": "sepa-125079", "trial": "scotland"}, {"id": "new-english"}]
    assert bs.attach_water_body(results, path) == (0, ["new-english"])


def test_the_dores_outfall_is_settled_as_discharging_into_loch_ness():
    from dipcast.overflows import apply_joins
    df = apply_joins(pd.DataFrame({"site_id": ["CSO005667", "CSO003129"], "lat": [57.0, 57.3], "lon": [-4.0, -4.4]}))
    assert df.loc[0, "position_source"] == "join" and (df.loc[0, "lat"], df.loc[0, "lon"]) == (57.379215, -4.336843)
    assert pd.isna(df.loc[1].get("position_source"))
