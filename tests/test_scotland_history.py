"""Scotland plan task S2: the spill model's covariates from Scottish Water's event history
(ingest/sw_covariates.py), and the paced ERA5-Land fetch for the Scottish rain cells
(scripts/fetch_scotland_history.py), which stops at the first refusal. Every event here is made up."""

import importlib.util
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from dipcast.ingest import rainfall, sw_covariates
from dipcast.ingest.sw_history import count_12_24

ROOT = Path(__file__).resolve().parents[1]
REP, NON = "Scottish Water reported 2021-2025", "Scottish Water non-reported 2022-2025"


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("fetch_scotland_history", ROOT / "scripts" / "fetch_scotland_history.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ev_row(site, start, hours, source=REP, published=None, day_record=False):
    s = pd.Timestamp(start, tz="UTC")
    return {"site_id": site, "event_start": s, "event_end": pd.NaT if day_record else s + pd.Timedelta(hours=hours),
            "duration_h": hours, "duration_published_h": hours if published is None else published,
            "source": source, "year": s.year}


def yr_row(site, year, status, days=None, source=REP):
    return {"site_id": site, "year": year, "status": status, "days_data": days, "source": source}


@pytest.fixture
def fixture():
    ev = pd.DataFrame([
        # A: 2021, two discharges inside one 12-hour block, then one in the next 24-hour block: 2 spills.
        ev_row("A", "2021-03-01 00:00", 2), ev_row("A", "2021-03-01 06:00", 1), ev_row("A", "2021-03-01 20:00", 1),
        # A: 2021, a separate spill a week later; 2022: one spill, with a 15-minute event dropped by the cut.
        ev_row("A", "2021-03-08 00:00", 3), ev_row("A", "2022-01-10 00:00", 5),
        ev_row("A", "2022-06-01 00:00", 0.25),
        # A: 2023, the same event in both files counts once.
        ev_row("A", "2023-02-01 00:00", 4), ev_row("A", "2023-02-01 00:00", 4, source=NON),
        # B: 2025, only short events: listed with events, counted as zero.
        ev_row("B", "2025-05-01 00:00", 0.2, source=NON), ev_row("B", "2025-05-03 00:00", 0.1, source=NON),
        # C: 2025, a day record (no end) of 6 published hours.
        ev_row("C", "2025-07-01 00:00", 6, source=NON, day_record=True),
    ])
    yearly = pd.DataFrame([
        yr_row("A", 2021, "events"), yr_row("A", 2022, "events"), yr_row("A", 2023, "events", 365),
        yr_row("A", 2023, "no data", 0, source=NON), yr_row("A", 2024, "no data", 10),
        yr_row("B", 2024, "no events", 366, source=NON), yr_row("B", 2025, "events", 300, source=NON),
        yr_row("C", 2025, "events", 400, source=NON),
    ])
    return ev, yearly


def test_counts_follow_the_12_24_rule_after_the_short_cut(fixture):
    ev, yearly = fixture
    cov = sw_covariates.covariates(ev, yearly).set_index(["site_id", "year"])
    assert list(sw_covariates.covariates(ev, yearly).columns) == sw_covariates.COLS
    assert cov.loc[("A", 2021), "spills"] == 3          # 2 in the first run of blocks, 1 a week later
    assert cov.loc[("A", 2021), "spill_hours"] == pytest.approx(7.0)
    assert cov.loc[("A", 2022), "spills"] == 1 and cov.loc[("A", 2022), "short_dropped"] == 1
    assert cov.loc[("A", 2022), "spill_hours"] == pytest.approx(5.0)
    assert cov.loc[("A", 2023), "spills"] == 1 and cov.loc[("A", 2023), "events"] == 1   # repeat across files
    assert cov.loc[("A", 2023), "status"] == "events"   # best status of the two files
    assert pd.isna(cov.loc[("A", 2024), "spills"])      # "no data": no count
    assert cov.loc[("B", 2024), "spills"] == 0 and cov.loc[("B", 2024), "spill_hours"] == 0
    assert cov.loc[("B", 2025), "spills"] == 0 and cov.loc[("B", 2025), "short_dropped"] == 2
    assert cov.loc[("C", 2025), "spills"] == 1 and cov.loc[("C", 2025), "spill_hours"] == pytest.approx(6.0)


def test_rule_agrees_with_s1s_count_when_nothing_is_short(fixture):
    ev, _ = fixture
    a = ev[(ev.site_id == "A") & (ev.year == 2021)]
    assert count_12_24(a.event_start, a.event_end) == 3


def test_uptime_from_days_of_data(fixture):
    ev, yearly = fixture
    cov = sw_covariates.covariates(ev, yearly).set_index(["site_id", "year"])
    assert pd.isna(cov.loc[("A", 2021), "edm_operational_pct"])          # none published
    assert cov.loc[("A", 2023), "edm_operational_pct"] == pytest.approx(100.0)   # largest of the two files
    assert cov.loc[("B", 2024), "edm_operational_pct"] == pytest.approx(100.0)   # 366 of a leap year
    assert cov.loc[("B", 2025), "edm_operational_pct"] == pytest.approx(100 * 300 / 365)
    assert cov.loc[("C", 2025), "edm_operational_pct"] == pytest.approx(100.0)   # capped


def test_long_term_average_prefers_years_with_good_uptime(fixture):
    ev, yearly = fixture
    cov = sw_covariates.covariates(ev, yearly).set_index(["site_id", "year"])
    # 2021 and 2022 have no uptime: the mean of any counted years.
    assert cov.loc[("A", 2022), "lta_spills"] == pytest.approx(2.0)
    assert cov.loc[("A", 2022), "lta_basis"] == "any_uptime" and cov.loc[("A", 2022), "lta_years"] == 2
    # 2023 has 100% uptime, so it alone counts from then on, and 2024 (no data) adds nothing.
    assert cov.loc[("A", 2023), "lta_spills"] == pytest.approx(1.0) and cov.loc[("A", 2023), "lta_basis"] == "uptime90"
    assert cov.loc[("A", 2024), "lta_spills"] == pytest.approx(1.0)
    # B 2025: 82% uptime is below 90, so the 2024 zero is the only good year.
    assert cov.loc[("B", 2025), "lta_spills"] == 0 and cov.loc[("B", 2025), "lta_basis"] == "uptime90"


def test_a_year_uses_the_covariates_of_the_year_before(fixture):
    ev, yearly = fixture
    cov = sw_covariates.covariates(ev, yearly)
    c = sw_covariates.covariates_for(cov, 2025)
    assert c.site_id.tolist() == ["B"] and set(c.year) == {2025}      # A's 2024 has no count
    assert c.iloc[0].edm_operational_pct == pytest.approx(100.0)
    assert sw_covariates.covariates_for(cov, 2022).site_id.tolist() == ["A"]
    assert sw_covariates.covariates_for(cov, 2022).iloc[0].lta_spills == pytest.approx(3.0)


# ------------------------------------------------------------------ rain cells and the paced fetch

def test_cells_are_tiered_by_what_the_hindcast_needs(script, fixture):
    ev, yearly = fixture
    cov = sw_covariates.covariates(ev, yearly)
    sites = pd.DataFrame({"site_id": ["A", "B", "C"], "lat": [55.86, 55.95, 57.15], "lon": [-4.25, -3.19, -2.09]})
    api = pd.DataFrame({"site_id": ["A", "X"], "lat": [55.86, 56.46], "lon": [-4.25, -2.97]})
    cy = script.cell_years(api, sites, cov, [2024, 2025])
    by = cy.set_index(["cell_lat", "cell_lon", "year"])
    assert len(cy) == 8                                        # 4 cells x 2 years
    assert by.loc[(55.9, -4.2, 2025)].tolist()[:2] == [1, 1]    # api, history (Glasgow: A)
    assert by.loc[(56.0, -3.2, 2025), "tier"] == 1             # B: label in 2025 and a count in 2024
    assert by.loc[(57.2, -2.1, 2025), "tier"] == 2             # C: a label, no count the year before
    assert by.loc[(56.5, -3.0, 2025), "tier"] == 3             # X: API asset only
    assert by.loc[(55.9, -4.2, 2024), "tier"] == 3             # A's 2024 is "no data"
    assert cy.iloc[0][["tier", "year"]].tolist() == [1, 2025]


class Clock:
    def __init__(self):
        self.t, self.waits = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.waits.append(round(s, 3))
        self.t += s


def _plan(n, year=2025, batch=2):
    cells = [(56.0 + i / 10, -4.0) for i in range(n)]
    return [(1, year, cells[i:i + batch]) for i in range(0, n, batch)]


def _touching(tmp_path, asked):
    def fetch(chunk, year):
        asked.append((len(chunk), year))
        for c in chunk:
            (tmp_path / f"archive_{rainfall.cell_key(*c)}_{year}.parquet").touch()
    return fetch


def test_paced_fetch_waits_and_stops_at_the_budget(script, monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    asked, clock = [], Clock()
    per_req = script.archive_calls(2, 365)
    done = script.fetch_paced(_plan(6), max_calls=2 * per_req + 1, per_hour=3000,
                              fetch=_touching(tmp_path, asked), sleep=clock.sleep, clock=clock)
    assert asked == [(2, 2025), (2, 2025)] and done["cell_years"] == 4
    assert done["stopped"].startswith("budget")
    assert clock.waits == [pytest.approx(3600 * per_req / 3000, abs=1e-3)]


def test_paced_fetch_stops_at_the_first_refusal(script, monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    asked = []

    def refuse(chunk, year):
        asked.append(year)
        raise rainfall.OpenMeteoError("open-meteo request refused: HTTP 429")

    done = script.fetch_paced(_plan(6), max_calls=1e9, per_hour=3000, fetch=refuse, sleep=lambda s: None)
    assert asked == [2025] and done["stopped"] == "refused: open-meteo request refused: HTTP 429"
    assert done["cell_years"] == 0


def test_strict_archive_does_not_retry_a_429(monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall, "_sleep", lambda s: pytest.fail("waited to retry a 429"))
    monkeypatch.setattr(rainfall.time, "sleep", lambda s: None)
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params)
        return httpx.Response(429, request=httpx.Request("GET", url))

    monkeypatch.setattr(rainfall, "_http_get", fake_get)
    with pytest.raises(rainfall.OpenMeteoError, match="429"):
        rainfall.fetch_archive([(56.0, -4.0)], 2024, strict=True)
    assert len(calls) == 1 and not list(tmp_path.iterdir())


def test_strict_archive_writes_the_usual_cache_file(monkeypatch, tmp_path):
    monkeypatch.setattr(rainfall, "CACHE", tmp_path)
    monkeypatch.setattr(rainfall.time, "sleep", lambda s: None)
    hours = pd.date_range("2024-01-01", periods=3, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()

    def fake_get(url, params, timeout):
        return httpx.Response(200, json={"hourly": {"time": hours, "precipitation": [0.0, 0.4, 1.2]}},
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(rainfall, "_http_get", fake_get)
    df = rainfall.fetch_archive([(56.0, -4.0)], 2024, strict=True)
    assert np.allclose(df.precip_mm, [0.0, 0.4, 1.2])
    assert (tmp_path / "archive_56.000_-4.000_2024.parquet").exists()
