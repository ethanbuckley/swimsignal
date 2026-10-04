"""data/upstream/<id>.json (build_site.write_upstream): every monitored overflow upstream of a spot,
most reach first, for the organisers' page, which spots.json's ten left partial at 42 of 105 spots."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site as bs

GEN = pd.Timestamp("2026-10-04 12:53", tz="Europe/London")
CREDITS = {"attribution": "Contains data from the water companies", "full": "https://swimsignal.co.uk/terms.html#data"}


def _contrib(sid: str, weight: float, **extra) -> dict:
    """A contributor as forecast_point writes it, with fields the file leaves out."""
    return {"site_id": sid, "site_name": f"{sid} STW", "company": "Thames Water", "receiving_watercourse": "River Thames",
            "distance_km": 3.2, "lake_distance_km": 0.0, "travel_h": 1.8, "weight": weight, "lta_spills": 12.0,
            "spill_hours": 40.5, "has_live": True, "lat": 51.5, "lon": -0.9, "status": 0, "p_spill_days": [0.1] * 5,
            "now_contribution": 0.0, **extra}


def test_one_file_a_spot_with_every_overflow_most_reach_first(tmp_path):
    upstream = {"thames-henley": [_contrib(f"T{k}", w) for k, w in enumerate([0.2, 0.9, 0.05, 0.4])],
                "henleaze-lake": [],                       # nothing upstream: no file
                "bad id/../x": [_contrib("X", 0.5)]}         # not a file name: no file
    stale = tmp_path / "data" / "upstream" / "gone-spot.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}")                                 # a spot no longer listed
    assert bs.write_upstream(tmp_path, upstream, GEN, CREDITS) == 1
    files = sorted(p.name for p in (tmp_path / "data" / "upstream").iterdir())
    assert files == ["thames-henley.json"]
    d = json.loads((tmp_path / "data" / "upstream" / "thames-henley.json").read_text())
    assert d["id"] == "thames-henley" and d["generated_at"] == GEN.isoformat() and d["credits"] == CREDITS
    assert [o["site_id"] for o in d["overflows"]] == ["T1", "T3", "T0", "T2"]
    assert set(d["overflows"][0]) == set(bs.UPSTREAM_FIELDS)   # the organisers' fields, nothing of the day's forecast


def test_the_build_asks_for_every_overflow_and_keeps_ten_in_spots_json():
    src = (Path(bs.__file__)).read_text()
    assert "include_contributors=ALL_CONTRIBUTORS" in src and 'f["contributors"] = f.get("contributors", [])[:KEEP_CONTRIBUTORS]' in src
    assert bs.KEEP_CONTRIBUTORS == 10 and bs.ALL_CONTRIBUTORS >= 185   # Warleigh Weir had 185 on 4 Oct 2026
