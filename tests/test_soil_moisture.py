"""Soil moisture in the river E. coli estimate (docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md): which model a spot uses,
the fallback, the clamp, one value held across the days shown, the once-a-day cache and its ledger entry, and the
stamp. No test touches the network: rainfall._http_get is replaced by an httpx.MockTransport client."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from dipcast.ingest import rainfall, soil
from dipcast.model import ecoli, forecast

ROOT = Path(__file__).resolve().parents[1]
CELL = (54.4, -2.9)


class Fake:
    """Open-Meteo's forecast API for soil moisture: hourly values from 00:00 UTC yesterday, one an hour, `value` at
    every hour. `asked` holds each request's params."""

    def __init__(self, now: pd.Timestamp, value: float | None = 0.3):
        self.now, self.value, self.asked = now, value, []
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        p = dict(request.url.params)
        self.asked.append(p)
        lats = p["latitude"].split(",")
        hours = pd.date_range(self.now.floor("D") - pd.Timedelta(days=1), periods=72, freq="h")
        one = {"latitude": 0, "longitude": 0, "hourly": {"time": hours.strftime("%Y-%m-%dT%H:%M").tolist(),
                                                          soil.SOIL_VAR: [self.value] * 72}}
        body = [one for _ in lats]
        return httpx.Response(200, json=body if len(body) > 1 else body[0])

    def get(self, url, params, timeout):
        return self.client.get(url, params=params, timeout=timeout)


@pytest.fixture
def om(monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path / "rain")
    monkeypatch.setattr(soil, "CACHE", tmp_path / "soil")
    monkeypatch.setattr(rainfall, "_sleep", lambda s: None)
    rainfall.reset_fallbacks()
    soil.reset()

    def install(now, value=0.3):
        f = Fake(now, value)
        monkeypatch.setattr(rainfall, "_http_get", f.get)
        return f

    yield install
    rainfall.reset_fallbacks()


NOW = pd.Timestamp("2026-10-26 14:20", tz="UTC")


# ------------------------------------------------------------------ the request, the cache and the ledger
def test_soil_moisture_is_its_own_request_naming_ecmwf_ifs(om):
    f = om(NOW)
    st = soil.fetch([CELL], now=NOW)
    assert st["fetched"] == 1 and st["calls"] == 1.0
    p = f.asked[0]
    assert p["hourly"] == "soil_moisture_9_to_27cm" and p["models"] == "ecmwf_ifs"
    assert "precipitation" not in p["hourly"]   # never added to the rain's request


def test_a_cell_is_asked_for_once_per_utc_day_and_booked_under_soil(om):
    f = om(NOW)
    soil.fetch([CELL, (51.5, -0.1)], now=NOW)
    soil.fetch([CELL, (51.5, -0.1)], now=NOW + pd.Timedelta(hours=6))   # later builds the same UTC day
    assert len(f.asked) == 1
    assert rainfall.calls_today()["by"] == {"soil": 2.0}   # one call per cell: one variable over 3 days
    soil.fetch([CELL], now=NOW + pd.Timedelta(days=1))
    assert len(f.asked) == 2


def test_no_request_when_the_days_ration_is_spent(om, monkeypatch):
    f = om(NOW)
    monkeypatch.setattr(rainfall, "DAILY_CALLS", 0.5)
    st = soil.fetch([CELL], now=NOW)
    assert not f.asked and st["held"] == 1 and rainfall.calls_today()["held"] == {"soil": 1.0}
    assert soil.value(CELL, NOW) == (None, {"reason": "not fetched"})


# ------------------------------------------------------------------ the value and its age
def test_the_value_is_the_one_at_0000_utc_of_the_issue_day(om):
    om(NOW, value=0.27)
    soil.fetch([CELL], now=NOW)
    v, info = soil.value(CELL, NOW)
    assert v == pytest.approx(0.27) and info["at"] == "2026-10-26T00:00:00+00:00"


def test_yesterdays_fetch_serves_today_but_not_older(om):
    om(NOW)
    soil.fetch([CELL], now=NOW)
    later = NOW + pd.Timedelta(hours=20)            # the next UTC day, its own fetch failed: 20 h old, inside MAX_AGE_H
    assert soil.value(CELL, later)[0] is not None
    much_later = NOW + pd.Timedelta(hours=soil.MAX_AGE_H + 1)
    v, info = soil.value(CELL, much_later)
    assert v is None and info["reason"].startswith("last fetch")


def test_a_missing_value_is_none_never_a_guess(om):
    om(NOW, value=None)
    soil.fetch([CELL], now=NOW)
    assert soil.value(CELL, NOW) == (None, {"reason": "no value at 00:00 UTC", "fetched_at": NOW.isoformat()})


# ------------------------------------------------------------------ the model a spot uses
def _X(n=5):
    days = pd.date_range("2026-07-01", periods=n, freq="D", tz="Europe/London")
    return ecoli.features(np.full(n, 6.0), np.full(n, 2.0), np.full(n, 0.2), np.zeros(n), days)


def test_the_river_model_file_is_the_one_the_tests_passed():
    m = ecoli.load_sm()
    assert m is not None and list(m.coef) == [*ecoli.FEATURES, "sm"]
    assert m.meta["sm_range"] == [0.052, 0.494] and m.meta["n_samples"] == 1502
    want = json.loads((ROOT / "docs" / "SOIL-MOISTURE-ECOLI-LEADS-TEST-2026-11.json").read_text())["coef_per_sd_all_rows"]
    assert all(abs(m.coef[c] - want[c]) < 1e-9 for c in want)


def test_a_lake_keeps_todays_model(om):
    om(NOW)
    p_today = ecoli.load().predict(_X())
    p, state = forecast.river_ecoli("lake", *CELL, _X(), p_today, NOW)
    assert p is p_today and state == {"used": False, "reason": "lake: today's model"}


def test_a_river_uses_soil_moisture_held_for_every_day(om):
    om(NOW, value=0.31)
    X, p_today = _X(), ecoli.load().predict(_X())
    p, state = forecast.river_ecoli("river", *CELL, X, p_today, NOW)
    assert state["used"] and state["sm"] == 0.31 and not state["held"]
    m = ecoli.load_sm()
    assert np.allclose(p, m.predict(X.assign(sm=0.31)))
    assert not np.allclose(p, p_today)
    # One value for every day shown: a day's figure changes with its rain, not its soil moisture.
    assert ecoli.with_sm(X, 0.31, m)["sm"].nunique() == 1


def test_a_river_without_soil_moisture_falls_back_to_todays_model(om):
    om(NOW, value=None)
    X, p_today = _X(), ecoli.load().predict(_X())
    p, state = forecast.river_ecoli("river", *CELL, X, p_today, NOW)
    assert p is p_today and state["used"] is False and state["reason"] == "no value at 00:00 UTC"


def test_a_river_without_the_model_file_falls_back(om, monkeypatch):
    om(NOW)
    monkeypatch.setattr(ecoli, "load_sm", lambda: None)
    p_today = ecoli.load().predict(_X())
    p, state = forecast.river_ecoli("river", *CELL, _X(), p_today, NOW)
    assert p is p_today and state == {"used": False, "reason": "no river model file"}


def test_soil_moisture_is_held_inside_the_fitted_range(om):
    m = ecoli.load_sm()
    lo, hi = m.meta["sm_range"]
    assert ecoli.with_sm(_X(), 0.9, m)["sm"].iloc[0] == hi and ecoli.with_sm(_X(), 0.0, m)["sm"].iloc[0] == lo
    om(NOW, value=0.9)
    p, state = forecast.river_ecoli("river", *CELL, _X(), ecoli.load().predict(_X()), NOW)
    assert state["held"] and np.allclose(p, m.predict(_X().assign(sm=hi)))


# ------------------------------------------------------------------ the build's health
def test_build_health_counts_river_spots_that_fell_back():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    day = {"date": "2026-10-26", "data_status": "ok"}
    spot = lambda mode, s: {"name": mode, "days": [day], "location": {"mode": mode},
                            "assumptions": {"ecoli_model": {"soil": s}}}
    h = build_site.build_health([spot("river", {"used": True, "sm": 0.3}), spot("river", {"used": False, "reason": "not fetched"}),
                                 spot("lake", {"used": False, "reason": "lake: today's model"})])
    assert h["ecoli_soil"] == {"river_spots": 2, "with_soil": 1, "fallback": 1, "reasons": {"not fetched": 1}}
    assert any("used today's E. coli model" in w for w in h["warnings"])


# ------------------------------------------------------------------ the stamp
def test_the_stamp_covers_both_e_coli_files():
    forecast.model_version.cache_clear()
    b = ecoli.MODEL_PATH.read_bytes() + ecoli.SM_MODEL_PATH.read_bytes()
    assert f"ecoli={hashlib.md5(b).hexdigest()[:8]};" in forecast.model_version()


def test_the_2027_evaluation_computes_the_same_stamp_part(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import evaluate_2027 as E
    repo = tmp_path / "r"
    repo.mkdir()
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (repo / "data" / "processed").mkdir(parents=True)
    (repo / "data" / "processed" / "ecoli_model.json").write_bytes(b"{a}")
    git("add", "-A")
    git("commit", "-qm", "one file")
    git("tag", "one")
    (repo / "data" / "processed" / "ecoli_model_sm.json").write_bytes(b"{b}")
    git("add", "-A")
    git("commit", "-qm", "two files")
    git("tag", "two")
    assert E.frozen_hashes(repo, "one")["ecoli"] == hashlib.md5(b"{a}").hexdigest()[:8]
    assert E.frozen_hashes(repo, "two")["ecoli"] == hashlib.md5(b"{a}{b}").hexdigest()[:8]
    assert "data/processed/ecoli_model_sm.json" in E.MODEL_PATHS and "src/dipcast/ingest/soil.py" in E.MODEL_PATHS
