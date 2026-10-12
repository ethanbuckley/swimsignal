"""Where the E. coli evaluation places a bathing water on the river network: as the site does.

validate_ecoli.py, replay_ecoli_leads.py, fetch_rain_leads_upstream.py and fetch_rain_validation.py
place each inland bathing water with bathing_water_pin. It reads the bathing water's spots.csv row
(id "bw-<EA id>") and calls locate_pin with that row's position and the hints the site build passes
(transport.spot_hints: the kind, the river for a river spot, the name). The E. coli model the site
serves is fitted on these exposures, so they must come from the pins the site uses.

Until 12 Oct 2026 the four scripts called locate_pin with no hints. Three of the 38 bathing waters then
landed on other water than the site's pin (docs/EVAL-PINS-TEST-2026-10.md): Colwick West Lake on the
River Trent (357 overflows; the site counts none), Queen Elizabeth Gardens, Salisbury, below the Nadder
(32 overflows; the site counts 16) and Wolvercote Mill Stream (29; the site counts 31).

DIPCAST_EVAL_PINS=bare places them the old way, with no hints, for the paired test and to reproduce
numbers published before the change. Any other value is an error.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import pandas as pd

from dipcast.model.transport import PinLocation, locate_pin, spot_hints
from dipcast.network.rivers import RiverNetwork

# The checkout's own spots.csv, the file the site build reads: not DIPCAST_ROOT's, since an evaluation
# run in a scratch root has data there but no spots.csv.
SPOTS_CSV = Path(__file__).resolve().parents[1] / "spots.csv"
MODES = ("site", "bare")


def mode() -> str:
    m = os.environ.get("DIPCAST_EVAL_PINS", "site")
    if m not in MODES:
        raise ValueError(f"DIPCAST_EVAL_PINS={m!r}: use one of {MODES}")
    return m


@cache
def _spots(path: Path = SPOTS_CSV) -> pd.DataFrame:
    return pd.read_csv(path).fillna("").set_index("id")


def bathing_water_pin(net: RiverNetwork, bw_id: str, lon: float, lat: float) -> PinLocation:
    """The bathing water's pin as the site places it. `lon` and `lat` (the EA's sampling point) are used
    only with DIPCAST_EVAL_PINS=bare. A bathing water with no spots.csv row raises KeyError: placing it
    without hints would bring back the difference this module removes."""
    if mode() == "bare":
        return locate_pin(net, lon, lat)
    spots = _spots()
    sid = f"bw-{bw_id}"
    if sid not in spots.index:
        raise KeyError(f"{sid} is not in {SPOTS_CSV.name}: add the bathing water there (the site's row) "
                       "or run with DIPCAST_EVAL_PINS=bare")
    r = spots.loc[sid]
    kind, river = spot_hints(r["kind"], r["river"])
    return locate_pin(net, float(r["lon"]), float(r["lat"]), kind_hint=kind, river_hint=river, name=r["name"])
