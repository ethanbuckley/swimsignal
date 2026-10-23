"""Lake direction (docs/LAKE-DIRECTION-TEST-2026-10.md): with "down", an overflow whose water enters a lake spot's
own lake more than transport.LAKE_DOWN_MARGIN_M nearer the lake's outlet than the spot does not count there.
Network-free: the L-shaped lake of tests/test_lake_distance.py. A beck enters at the far end of the first arm, the
lake drains from the end of the second arm, and a second overflow sits on the lake itself near the outlet."""

from __future__ import annotations

import pandas as pd
import pytest

from dipcast import config
from dipcast.model import transport
from test_lake_distance import LAKES, PIN, _pin, lakes, net  # noqa: F401  (fixtures)


def _overflows(net) -> pd.DataFrame:
    links = net.links
    return pd.DataFrame([
        {"site_id": "beck", "link_id": "r1", "frac": 0.5, "link_length": links.loc["r1", "length"],
         "start_node": links.loc["r1", "start_node"]},
        {"site_id": "shore", "link_id": "L2", "frac": 0.9, "link_length": links.loc["L2", "length"],
         "start_node": links.loc["L2", "start_node"]},
    ])


def _trace(net, pin, mode: str) -> pd.DataFrame:
    return transport.upstream_overflows(net, pin, _overflows(net), velocity_ms=0.5,
                                        lake_direction_mode=mode).set_index("site_id")


def test_the_default_counts_either_way():
    assert config.LAKE_DIRECTION_MODE == "any"


def test_the_outlet_is_the_end_of_the_second_arm(net):
    assert transport.lake_outlet_xy(net, {"L1", "L2"}) == (3_750, 4_000)


def test_water_entering_down_the_lake_does_not_count(net):
    pin = _pin(1_000, 0, link="L1", frac=1_000 / 3_750)
    any_, down = _trace(net, pin, "any"), _trace(net, pin, "down")
    assert set(any_.index) == {"beck", "shore"}
    assert set(down.index) == {"beck"}
    # What is kept is unchanged.
    assert down.loc["beck", "weight"] == pytest.approx(any_.loc["beck", "weight"])


def test_down_lake_metres_go_through_the_water(net):
    pin = _pin(1_000, 0, link="L1", frac=1_000 / 3_750)
    d = transport.down_lake_m(net, pin, [[3_750, 3_600], [0, 0]])
    # The spot is about 2.5 km + 3.75 km from the outlet round the corner; the shore entry 400 m; the beck's entry
    # (the head of the lake) 1 km further than the spot.
    assert d[0] > 5_000
    assert d[1] == pytest.approx(-1_000, abs=10)   # both paths cut the inner corner a little differently


def test_near_the_spot_it_still_counts(net):
    # The spot near the outlet: the shore overflow enters 200 m further down, inside the margin.
    pin = _pin(3_750, 3_400, link="L2", frac=0.85)
    assert transport.down_lake_m(net, pin, [[3_750, 3_600]])[0] == pytest.approx(200, abs=1)
    assert set(_trace(net, pin, "down").index) == {"beck", "shore"}


def test_unknown_mode_is_refused(net):
    with pytest.raises(ValueError):
        _trace(net, _pin(), "sideways")


def test_a_spot_at_the_outlet_loses_nothing(net):
    assert set(_trace(net, _pin(*PIN), "down").index) == set(_trace(net, _pin(*PIN), "any").index)
