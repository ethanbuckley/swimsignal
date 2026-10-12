"""The E. coli evaluation places bathing waters as the site does (scripts/eval_pins.py,
docs/EVAL-PINS-TEST-2026-10.md)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

from dipcast.model.transport import spot_hints

ROOT = Path(__file__).resolve().parents[1]
EVAL_SCRIPTS = ["validate_ecoli", "replay_ecoli_leads", "fetch_rain_leads_upstream", "fetch_rain_validation"]


def _script(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


@pytest.mark.parametrize("kind, river, want", [
    ("river", "River Avon", ("river", "River Avon")),
    ("river", "  River Avon ", ("river", "River Avon")),
    ("lake", "River Trent", ("lake", None)),        # a lake never takes a river
    ("river", "", ("river", None)),
    ("river", float("nan"), ("river", None)),       # a blank cell read without fillna
    ("", "River Avon", (None, "River Avon")),        # no kind: the river is still a hint, as before
    ("pool", "", (None, None)),
])
def test_spot_hints(kind, river, want):
    assert spot_hints(kind, river) == want


def test_build_site_river_of_unchanged():
    """build_site's _river_of now comes from spot_hints: the same answers as its old body."""
    bs = _script("build_site")

    def old(row):
        river = str(getattr(row, "river", "") or "").strip()
        return river if river and getattr(row, "kind", "") != "lake" else None

    spots = pd.read_csv(ROOT / "spots.csv").fillna("")
    for r in spots.itertuples(index=False):
        assert bs._river_of(r) == old(r), r.id


def test_every_inland_bathing_water_has_a_spot_row():
    """The evaluation reads each bathing water's spots.csv row; one without a row would fail the run."""
    inland = json.loads((ROOT / "data/raw/bathing_waters_inland.json").read_text())
    spots = pd.read_csv(ROOT / "spots.csv").fillna("").set_index("id")
    for bw in inland:
        sid = f"bw-{bw['id']}"
        assert sid in spots.index, sid
        assert spots.loc[sid, "kind"] == bw["kind"], sid


@pytest.fixture
def pins(monkeypatch):
    ep = _script("eval_pins")
    calls = []
    monkeypatch.setattr(ep, "locate_pin", lambda net, lon, lat, **kw: calls.append((lon, lat, kw)) or "pin")
    return ep, calls


def test_site_pins_use_the_spot_row(pins, monkeypatch):
    ep, calls = pins
    monkeypatch.delenv("DIPCAST_EVAL_PINS", raising=False)
    assert ep.bathing_water_pin(None, "ukf1400-09750", 0.0, 0.0) == "pin"
    row = ep._spots().loc["bw-ukf1400-09750"]
    assert calls == [(float(row["lon"]), float(row["lat"]),
                      {"kind_hint": "lake", "river_hint": None, "name": "Colwick Country Park (West Lake)"})]
    ep.bathing_water_pin(None, "ukk1500-19002", 0.0, 0.0)
    assert calls[-1][2] == {"kind_hint": "river", "river_hint": "River Avon",
                            "name": "River Avon at Queen Elizabeth Gardens"}


def test_bare_pins_reproduce_the_old_rule(pins, monkeypatch):
    ep, calls = pins
    monkeypatch.setenv("DIPCAST_EVAL_PINS", "bare")
    ep.bathing_water_pin(None, "ukf1400-09750", -1.1, 52.9)
    assert calls == [(-1.1, 52.9, {})]


def test_unknown_mode_and_missing_row_fail(pins, monkeypatch):
    ep, _ = pins
    monkeypatch.setenv("DIPCAST_EVAL_PINS", "hinted")
    with pytest.raises(ValueError):
        ep.bathing_water_pin(None, "ukf1400-09750", 0.0, 0.0)
    monkeypatch.setenv("DIPCAST_EVAL_PINS", "site")
    with pytest.raises(KeyError):
        ep.bathing_water_pin(None, "ukx0000-00000", 0.0, 0.0)


@pytest.mark.parametrize("name", EVAL_SCRIPTS)
def test_eval_scripts_place_pins_through_eval_pins(name):
    """No evaluation script calls locate_pin itself: that is how the evaluation drifted from the site."""
    src = (ROOT / "scripts" / f"{name}.py").read_text()
    assert "bathing_water_pin(" in src
    assert not re.search(r"\blocate_pin\(", src)
