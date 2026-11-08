"""The audit of the 11 spots listed on 6 Nov 2026 (docs/NEW-SPOTS-AUDIT-2026-11.md): pins on their water,
names that say where the pin is, and no page line that reads "no overflow upstream" as "no risk"."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "src" / "dipcast" / "site"


def _metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((a[0] - b[0]) * 111_000, (a[1] - b[1]) * 111_320 * k)


def _spot(path: str, spot_id: str) -> pd.Series:
    s = pd.read_csv(ROOT / path)
    return s.set_index("id").loc[spot_id]


def test_the_tame_pin_is_on_the_river_at_the_openstreetmap_place():
    # The OpenStreetMap node ("Wild swimming", by a bench) is in a field 133 m east of the Tame. The pin is the
    # point on the river the build already snapped it to, so the river and the 148 overflows are unchanged.
    spot = _spot("spots-osm.csv", "osm-tame-dosthill")
    cand = pd.read_csv(ROOT / "data" / "raw" / "osm_swim_candidates.csv").set_index("osm_id").loc[spot["osm_id"]]
    node, pin = (cand["lat"], cand["lon"]), (spot["lat"], spot["lon"])
    assert (spot["lat"], spot["lon"]) == (52.59095, -1.69768)
    assert 100 < _metres(node, pin) < 150      # moved onto the water, not to another place


def test_the_loch_lubnaig_name_does_not_place_it_by_strathyre():
    # The pin is at the loch's south end; the National Park's page puts Strathyre "to the north of Loch Lubnaig",
    # about 6.5 km from the pin.
    spot = _spot("spots-scotland.csv", "scot-lubnaig-strathyre")
    assert spot["name"] == "Loch Lubnaig, south end"
    assert spot["lat"] < 56.28


def test_no_overflow_upstream_never_reads_as_no_sewage_risk():
    # "No sewage spill risk" reads as "safe from sewage". The pages mean there is nothing to score.
    for f in (SITE / "index.html", SITE / "organisers.js", ROOT / "src" / "dipcast" / "pages" / "methods.html"):
        text = f.read_text(encoding="utf-8")
        assert "no sewage spill risk" not in text, f.name
        assert "no sewage spill score" in text, f.name
