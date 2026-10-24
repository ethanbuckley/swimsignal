"""transport.weather_decay and upstream_overflows(keep_parts=True), for docs/DIEOFF-WEATHER-TEST-2026-10.md.
Off by default: without them the weights are today's. Network-free, on test_transport_options' links."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
import test_transport_options as tto

from dipcast import config
from dipcast.model import transport

net = tto.net   # the fixture: its few links
_overflows, _pin = tto._overflows, tto._pin
K0 = math.log(10.0) / config.T90_HOURS
HOURS = pd.date_range("2025-06-01", "2025-06-10", freq="h", tz="UTC")


def test_keep_parts_only_adds_two_columns(net):
    a = transport.upstream_overflows(net, _pin(), _overflows(net), velocity_ms=0.2)
    b = transport.upstream_overflows(net, _pin(), _overflows(net), velocity_ms=0.2, keep_parts=True)
    assert sorted(b.columns) == sorted([*a.columns, "moving_h", "lake_pass"])
    assert b[a.columns].equals(a)
    assert np.allclose(np.power(10.0, -b["moving_h"] / config.T90_HOURS) * b["lake_pass"], b["decay"], rtol=0, atol=1e-12)


def test_a_constant_rate_gives_the_fixed_decay():
    moving = np.array([0.0, 5.5, 30.0, 70.25]); lake = np.array([1.0, 1.0, 0.4, 0.8]); travel = moving + [0, 0, 12, 3]
    arrivals = pd.date_range("2025-06-05 11:00", periods=3, freq="D", tz="UTC")
    got = transport.weather_decay(moving, lake, travel, pd.Series(K0, index=HOURS), arrivals)
    want = (np.power(10.0, -moving / config.T90_HOURS) * lake)[:, None]
    assert got.shape == (4, 3)
    assert np.allclose(got, want, rtol=0, atol=1e-12)


def test_the_window_is_the_journey_and_a_fraction_of_an_hour_counts_in_part():
    # Rate 0 except the hour ending 2025-06-05 06:00, at rate 1.
    rate = pd.Series(0.0, index=HOURS); rate[pd.Timestamp("2025-06-05 06:00", tz="UTC")] = 1.0
    arr = pd.DatetimeIndex([pd.Timestamp("2025-06-05 12:00", tz="UTC")])
    # A 6.5 h journey starts at 05:30: half that hour is in it, a mean rate of 0.5 / 6.5.
    got = transport.weather_decay([6.5, 5.0, 10.0], [1, 1, 1], [6.5, 5.0, 10.0], rate, arr)[:, 0]
    assert got == pytest.approx([math.exp(-0.5), 1.0, math.exp(-1.0)])
    # Residence hours dilute the mean rate but do not decay: 3.5 moving hours of a 7 h journey from 05:00.
    assert transport.weather_decay([3.5], [0.5], [7.0], rate, arr)[0, 0] == pytest.approx(0.5 * math.exp(-0.5))


def test_a_missing_hour_or_a_window_outside_the_series_has_no_figure():
    rate = pd.Series(K0, index=HOURS); rate[pd.Timestamp("2025-06-05 06:00", tz="UTC")] = np.nan
    arr = pd.DatetimeIndex(["2025-06-05 12:00", "2025-06-06 12:00", "2025-06-01 02:00"]).tz_localize("UTC")
    got = transport.weather_decay([10.0], [1.0], [10.0], rate, arr)[0]
    assert np.isnan(got[0]) and np.isfinite(got[1]) and np.isnan(got[2])


def test_combine_daily_takes_weights_by_arrival_day():
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 0.5, (3, 6)); w = np.array([0.9, 0.3, 0.05]); tr = np.array([0.0, 30.0, 52.0])
    assert np.array_equal(transport.combine_daily(p, np.repeat(w[:, None], 6, axis=1), tr), transport.combine_daily(p, w, tr))
