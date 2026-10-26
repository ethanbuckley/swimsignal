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

    def __init__(self, now: pd.Timestamp, value: float | None = 0.3, respond=None):
        self.now, self.value, self.asked, self.respond = now, value, [], respond
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        p = dict(request.url.params)
        self.asked.append(p)
        lats = p["latitude"].split(",")
        if self.respond is not None:
            return self.respond(lats)
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

    def install(now, value=0.3, respond=None):
        f = Fake(now, value, respond)
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
    monkeypatch.setattr(rainfall, "DAILY_CALLS", 9000.0)
    assert soil.value((51.0, -1.0), NOW) == (None, {"reason": "missing"})   # never asked for
    assert soil.value(CELL, NOW) == (None, {"reason": "held"})


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
    assert v is None and info["reason"] == "expired"


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
    soil.fetch([CELL], now=NOW)
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
    soil.fetch([CELL], now=NOW)
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
    soil.fetch([CELL], now=NOW)
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


# ------------------------------------------------------------------ failures: named, never fatal, remembered
def _prefetch(monkeypatch, spots):
    """build_site.prefetch_rain with the network, the overflows and the rain stubbed: only soil moisture is asked
    for, through the Fake."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    pin = type("Pin", (), {"mode": "river"})()
    monkeypatch.setattr(build_site, "_net", lambda: None)
    monkeypatch.setattr(build_site, "_overflows", lambda: None)
    monkeypatch.setattr(build_site, "locate_pin", lambda *a, **k: pin)
    monkeypatch.setattr(build_site, "upstream_overflows", lambda *a, **k: pd.DataFrame({"lat": [], "lon": []}))
    monkeypatch.setattr(build_site, "fetch_forecast", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(build_site, "fallback_summary", lambda: None)
    build_site.prefetch_rain(spots, ensemble=False)
    return build_site


SPOTS = pd.DataFrame({"id": ["a"], "name": ["A"], "kind": ["river"], "river": [""], "lat": [CELL[0]], "lon": [CELL[1]]})


def _hours(now):
    return pd.date_range(now.floor("D") - pd.Timedelta(days=1), periods=72, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()


MALFORMED = {
    "no hourly block": (lambda lats: httpx.Response(200, json={"latitude": 0}), "bad: schema: no hourly block"),
    "no soil series": (lambda lats: httpx.Response(200, json={"hourly": {"time": _hours(NOW), "precipitation": [0.0] * 72}}),
                       "bad: schema: no soil_moisture_9_to_27cm series"),
    "lengths differ": (lambda lats: httpx.Response(200, json={"hourly": {"time": _hours(NOW), soil.SOIL_VAR: [0.3] * 70}}),
                       "bad: schema: 72 times and 70 values"),
    "not JSON": (lambda lats: httpx.Response(200, text="{cut short"), "bad: bad_body"),
    "server error": (lambda lats: httpx.Response(500, text="down"), "bad: network"),
    "out of range": (lambda lats: httpx.Response(200, json={"hourly": {"time": _hours(NOW), soil.SOIL_VAR: [7.0] * 72}}),
                     "no value at 00:00 UTC"),
}


@pytest.mark.parametrize("case", sorted(MALFORMED))
def test_a_malformed_answer_falls_back_and_the_build_goes_on(om, monkeypatch, case):
    respond, reason = MALFORMED[case]
    monkeypatch.setattr(soil.pd.Timestamp, "now", classmethod(lambda cls, tz=None: NOW))
    om(NOW, respond=respond)
    bs = _prefetch(monkeypatch, SPOTS)             # raises nothing
    p_today = ecoli.load().predict(_X())
    p, state = forecast.river_ecoli("river", *CELL, _X(), p_today, NOW)
    assert p is p_today and state["used"] is False and state["reason"] == reason
    day = {"date": "2026-10-26", "data_status": "ok"}
    h = bs.build_health([{"name": "a", "days": [day], "location": {"mode": "river"},
                          "assumptions": {"ecoli_model": {"soil": state}}}])
    assert h["ecoli_soil"]["fallback"] == 1 and h["ecoli_soil"]["reasons"] == {reason: 1}


def test_a_wrong_number_of_results_fails_every_cell_in_the_request(om):
    om(NOW, respond=lambda lats: httpx.Response(200, json={"hourly": {"time": _hours(NOW), soil.SOIL_VAR: [0.3] * 72}}))
    st = soil.fetch([CELL, (51.5, -0.1)], now=NOW)
    assert st["failed"] == {"schema": 2}
    assert soil.value(CELL, NOW)[1]["reason"] == "bad: schema: 1 results for 2 cells"


def test_a_cache_that_cannot_be_written_falls_back(om, monkeypatch):
    om(NOW)

    def refuse(self, *a, **k):
        raise OSError("read-only file system")
    monkeypatch.setattr(pd.DataFrame, "to_parquet", refuse)
    st = soil.fetch([CELL], now=NOW)
    assert st["failed"] == {"cache_write": 1} and soil.value(CELL, NOW)[1]["reason"] == "bad: cache_write"


def test_a_failed_cell_is_tried_once_more_that_day_and_never_by_a_spot(om, monkeypatch):
    f = om(NOW, respond=lambda lats: httpx.Response(500, text="down"))
    soil.fetch([CELL], now=NOW)
    assert len(f.asked) == 1
    forecast.river_ecoli("river", *CELL, _X(), ecoli.load().predict(_X()), NOW)   # a spot reads, never asks
    soil.fetch([CELL], now=NOW + pd.Timedelta(minutes=30))                          # the next build: too soon
    assert len(f.asked) == 1
    f.respond = None                                                                 # Open-Meteo is back
    soil.fetch([CELL], now=NOW + pd.Timedelta(hours=soil.RETRY_GAP_H))               # the one retry
    assert len(f.asked) == 2 and soil.value(CELL, NOW + pd.Timedelta(hours=1.5))[0] == pytest.approx(0.3)
    soil.fetch([CELL], now=NOW + pd.Timedelta(hours=5))                              # fetched today: no more
    assert len(f.asked) == 2


def test_two_failures_end_the_day_and_the_next_day_asks_again(om):
    f = om(NOW, respond=lambda lats: httpx.Response(200, text="{cut"))
    for h in (0, 1, 2, 3, 6):
        soil.fetch([CELL], now=NOW + pd.Timedelta(hours=h))
    assert len(f.asked) == soil.MAX_ATTEMPTS == 2
    assert rainfall.calls_today()["by"] == {"soil": 2.0}   # a 200 that is not JSON was answered, so counted
    rec = soil.attempts(NOW)["cells"][rainfall.cell_key(*CELL)]
    assert rec["tries"] == 2 and rec["last_reason"] == "bad_body" and not rec["ok"]
    soil.fetch([CELL], now=NOW + pd.Timedelta(days=1))
    assert len(f.asked) == 3


def test_a_forced_retry_skips_the_rules_and_is_booked_apart(om):
    f = om(NOW, respond=lambda lats: httpx.Response(500, text="down"))
    for _ in range(3):
        soil.fetch([CELL], now=NOW)
    assert len(f.asked) == 1
    f.respond = None
    soil.fetch([CELL], now=NOW, force=True)
    assert len(f.asked) == 2 and rainfall.calls_today()["by"] == {"soil_forced": 1.0}


# ------------------------------------------------------------------ the reviewer's cases, by name
def test_an_empty_json_object_falls_back_with_a_schema_reason(om):
    """A 200 with body {} raised KeyError('hourly') before the fix."""
    om(NOW, respond=lambda lats: httpx.Response(200, json={}))
    st = soil.fetch([CELL], now=NOW)
    assert st["failed"] == {"schema": 1}
    p_today = ecoli.load().predict(_X())
    p, state = forecast.river_ecoli("river", *CELL, _X(), p_today, NOW)
    assert p is p_today and state["reason"] == "bad: schema: no hourly block"


def test_two_503s_for_one_cell_in_one_day_make_one_request_until_the_retry_gap(om):
    """Before the fix every spot on the cell asked again. Now a second build inside RETRY_GAP_H sends nothing; the
    one retry comes after it, and after a second 503 nothing more that day."""
    f = om(NOW, respond=lambda lats: httpx.Response(503, text="busy"))
    soil.fetch([CELL], now=NOW)
    for _ in range(3):   # three spots on the cell, reading
        forecast.river_ecoli("river", *CELL, _X(), ecoli.load().predict(_X()), NOW)
    soil.fetch([CELL], now=NOW + pd.Timedelta(minutes=30))
    assert len(f.asked) == 1
    soil.fetch([CELL], now=NOW + pd.Timedelta(hours=soil.RETRY_GAP_H))
    soil.fetch([CELL], now=NOW + pd.Timedelta(hours=4))
    assert len(f.asked) == 2
    assert soil.value(CELL, NOW + pd.Timedelta(hours=4))[1] == {"reason": "bad: network", "tries": 2}


# ------------------------------------------------------------------ what a spot publishes about the model
def test_a_river_spot_on_the_soil_model_publishes_that_models_provenance(om):
    om(NOW, value=0.31)
    soil.fetch([CELL], now=NOW)
    _, state = forecast.river_ecoli("river", *CELL, _X(), ecoli.load().predict(_X()), NOW)
    m = forecast.ecoli_provenance(ecoli.load(), state)
    sm = ecoli.load_sm()
    assert m["file"] == "ecoli_model_sm.json" and m["n_samples"] == sm.meta["n_samples"] == 1502
    assert m["loyo_brier"] == ecoli.SM_MODEL_LOYO_BRIER == 0.0850 and m["test"] == "docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md"
    # The live request, not the fitting archive: soil.fetch asks config.OPEN_METEO_FORECAST.
    assert m["soil_source"] == "Open-Meteo Forecast API, models=ecmwf_ifs, soil_moisture_9_to_27cm, 00:00 UTC of the issue day"
    assert "Previous Runs" not in m["soil_source"] and m["fitted_on_soil_source"] == sm.meta["sm_source"]
    assert "Previous Runs lead 0" in m["fitted_on_soil_source"] and m["soil"]["at"] == "2026-10-26T00:00:00+00:00"
    assert m["baseline"]["file"] == "ecoli_model.json" and m["baseline"]["loyo_brier"] == 0.0919
    # The score is the leads test's lead-0 figure for this model.
    leads = json.loads((ROOT / "docs" / "SOIL-MOISTURE-ECOLI-LEADS-TEST-2026-11.json").read_text())
    assert round(leads["by_lead"]["0"]["all"]["candidate"], 4) == ecoli.SM_MODEL_LOYO_BRIER


def test_a_river_spot_that_fell_back_publishes_todays_model(om):
    om(NOW, value=None)
    soil.fetch([CELL], now=NOW)
    _, state = forecast.river_ecoli("river", *CELL, _X(), ecoli.load().predict(_X()), NOW)
    m = forecast.ecoli_provenance(ecoli.load(), state)
    em = ecoli.load()
    assert {k: m[k] for k in ("file", "target", "n_samples", "loyo_brier")} == {
        "file": "ecoli_model.json", "target": em.meta["target"], "n_samples": em.meta["n_samples"], "loyo_brier": 0.0919}
    assert "baseline" not in m and m["soil"]["used"] is False


def test_forecast_point_publishes_the_provenance_of_the_model_it_used():
    src = (ROOT / "src" / "dipcast" / "model" / "forecast.py").read_text()
    assert 'out["assumptions"]["ecoli_model"] = ecoli_provenance(em, soil_state)' in src
