"""Tests for Scottish Water's shadow forecasts and scores (scottish_shadow, Scotland plan task S5): the
Scottish marine rule, the overflow table and its abstentions, the rationed rain, the forecast log and
which forecasts it keeps, the scores on Scotland's own files, Gate B, and that none of it is reached
with the setting off or published with it on. Rows from the trimmed API answer of 4 Oct 2026
(fixtures/scottish_water_nrt.json, source: Scottish Water); networks, rain and outcomes are made up."""

import ast
import copy
import json
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from dipcast.network.rivers import RiverNetwork

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "scottish_water_nrt.json").read_text())
FETCHED = pd.Timestamp(FIXTURE["fetched_at"])


def _state(tmp_path, monkeypatch):
    from dipcast import config
    from dipcast.ingest import rainfall
    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "dipcast.duckdb")
    monkeypatch.setattr(rainfall, "CACHE", tmp_path / "rain")
    return config


def _net(links):
    """links: (id, form, start node, end node, [(x, y), ...]) in British National Grid metres."""
    gdf = gpd.GeoDataFrame(
        [{"id": i, "flow_direction": "in direction", "form": f, "fictitious": False, "watercourse_name": None,
          "watercourse_name_alternative": None, "start_node": s, "end_node": e, "geometry": LineString(xy)}
         for i, f, s, e, xy in links], crs=27700)
    return RiverNetwork.from_links(gdf)


def _row(asset, **kw):
    r = copy.deepcopy(next(x for x in FIXTURE["results"] if x["ASSET_ID"] == asset))
    r.update(kw)
    return r


def _snapshot():
    """Six assets: two CSOs on the Garnock, one SSSO on Kirtle Water, an EO beside a burn, a CSO on
    Loch Fyne beside a tidal burn, and one on Loch Leven at Kinross beside a lake link."""
    from dipcast.ingest.scottish_water import parse
    body = {"results": [
        _row("CSO000325"), _row("CSO000329"), _row("CSO007547"), _row("CSO005416"),
        _row("CSO000007", ASSET_ID="CSOFYNE01", RECEIVING_WATER="Loch Fyne"),
        _row("CSO000044", ASSET_ID="CSOLEVEN1", OVERFLOW_TYPE="CSO", RECEIVING_WATER="Loch Leven",
             DISCHARGE_OVERFLOW_LOCATION_LATITUDE="56.2", DISCHARGE_OVERFLOW_LOCATION_LONGITUDE="-3.38")],
        "last_updated": FIXTURE["last_updated"]}
    return parse(body, FETCHED)


def _scot_net(snap):
    """A link 50 m east of every asset: inland rivers, a tidal reach at Loch Fyne, a lake at Loch Leven."""
    from dipcast.network.rivers import lonlat_to_bng
    links = []
    for k, r in enumerate(snap.itertuples()):
        x, y = lonlat_to_bng(r.lon, r.lat)
        form = {"CSOFYNE01": "tidalRiver", "CSOLEVEN1": "lake"}.get(r.site_id, "inlandRiver")
        links.append((f"L{k}", form, f"n{k}a", f"n{k}b", [(x + 50, y - 400), (x + 50, y + 400)]))
    return _net(links)


# ------------------------------------------------------------------ marine rule
def test_scotlands_marine_rule_reads_sea_lochs_and_leaves_freshwater_lochs_inland():
    from dipcast.overflows import MARINE, marine_scotland
    names = pd.Series(["Loch Fyne", "Loch Lomond", "Loch Ness", "Kyles of Bute", "Firth of Forth",
                       "Un-named tributary of Firth of Clyde", "Findhorn Bay - via tidal reaches of the Mosset Burn",
                       "River Clyde", "Loch Leven", "Loch Leven", "Holy Loch", "Bressay Sound (Sea)", None])
    form = pd.Series([None, "lake", "lake", None, None, "inlandRiver", "tidalRiver", "inlandRiver",
                      "tidalRiver", "lake", "tidalRiver", None, None])
    got = marine_scotland(names, form).tolist()
    assert got == [True, False, False, True, True, False, False, False, True, False, True, True, False]
    # England's rule is untouched: it never named lochs or kyles.
    assert not pd.Series(["Loch Fyne", "Kyles of Bute"]).str.contains(MARINE).any()


def test_englands_second_pass_is_unchanged_without_a_scottish_rule():
    from dipcast.overflows import _second_pass
    net = _net([("A", "inlandRiver", "a", "b", [(300000, 500000), (300000, 502000)])])
    df = pd.DataFrame({"lon": [-2.0, -2.0], "lat": [54.0, 54.0], "receiving_watercourse": ["Firth of Forth", "Loch Fyne"],
                       "link_id": [None, None], "frac": np.nan, "snap_dist_m": np.nan, "form": None, "snap_confidence": None})
    out = _second_pass(net, df.copy())
    assert out.loc[0, "snap_confidence"] == "marine"
    assert out.loc[1, "snap_confidence"] != "marine"   # England's MARINE has no "loch"


# ------------------------------------------------------------------ the table
def test_table_forecasts_snapped_overflows_and_abstains_for_emergency_and_marine(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast.scottish_shadow import overflow_table
    snap = _snapshot()
    table, arm = overflow_table(_scot_net(snap), snap, year=2026)
    t = table.set_index("site_id")
    assert arm == "default"
    assert t.loc["CSO005416", ["forecast", "abstain"]].tolist() == [False, "emergency overflow"]
    # Loch Fyne: a tidal burn 50 m away, but the outfall is on a sea loch.
    assert t.loc["CSOFYNE01", ["forecast", "abstain", "snap_confidence"]].tolist() == [False, "marine", "marine"]
    assert pd.isna(t.loc["CSOFYNE01", "link_id"])
    # Loch Leven beside a lake link is the freshwater one at Kinross.
    assert t.loc["CSOLEVEN1", ["forecast", "form"]].tolist() == [True, "lake"]
    assert t.loc[["CSO000325", "CSO000329", "CSO007547"], "forecast"].all()
    assert (t["covariates"] == "filled").all() and t["lta_spills"].isna().all()


def test_table_uses_scottish_covariates_of_the_year_before_where_present(tmp_path, monkeypatch):
    config = _state(tmp_path, monkeypatch)
    from dipcast.scottish_shadow import overflow_table
    config.PROCESSED.mkdir()
    pd.DataFrame({"site_id": ["CSO000325", "CSO000325"], "year": [2024, 2025], "status": "events",
                  "spills": [9.0, 12.0], "spill_hours": [30.0, 41.0], "edm_operational_pct": [99.0, 98.0],
                  "lta_spills": [9.0, 10.5], "lta_years": [1, 2], "lta_basis": "uptime", "events": [9, 12],
                  "short_dropped": [0, 0], "days_data": [365, 360]}).to_parquet(config.PROCESSED / "sw_covariates.parquet")
    snap = _snapshot()
    table, arm = overflow_table(_scot_net(snap), snap, year=2026)
    t = table.set_index("site_id")
    assert arm.startswith("sw:") and len(arm) == 11
    assert t.loc["CSO000325", ["lta_spills", "spill_hours", "covariates"]].tolist() == [10.5, 41.0, "sw2025"]
    assert t.loc["CSO000329", "covariates"] == "filled"


# ------------------------------------------------------------------ rain
def _rain(cells, start="2026-10-01", hours=24 * 12, mm=0.5):
    t = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    return pd.concat([pd.DataFrame({"cell_lat": a, "cell_lon": b, "time": t, "precip_mm": mm,
                                    "issued_at": pd.Timestamp("2026-10-04T18:00Z")}) for a, b in cells], ignore_index=True)


def test_rain_asks_for_at_most_the_budget_oldest_first_and_uses_the_cache(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast.ingest import rainfall
    from dipcast.scottish_shadow import forecast_calls, shadow_rain
    sub = pd.DataFrame({"lat": [55.0, 55.5, 56.0], "lon": [-4.0, -4.0, -4.0]})
    cells = rainfall.cells_for_sites(sub["lat"], sub["lon"])
    rainfall.CACHE.mkdir(parents=True)
    asked = []

    def fetch(take):
        asked.append(list(take))
        for c in take:
            _rain([c]).to_parquet(rainfall.CACHE / f"forecast_{rainfall.cell_key(*c)}.parquet")
    rain, stats = shadow_rain(sub, budget=2, fetch=fetch)
    assert len(asked) == 1 and len(asked[0]) == 2
    assert stats["cells"] == 3 and stats["asked"] == 2 and stats["usable"] == 2 and stats["requests"] == 1
    assert stats["calls"] == forecast_calls(2) == 2.0   # one call a cell (rainfall.call_weight)
    # The next build asks only for the one never fetched; the two fresh ones come from the cache.
    _, stats = shadow_rain(sub, budget=2, fetch=fetch)
    assert asked[1] == [c for c in cells if c not in asked[0]] and stats["usable"] == 3
    # A failed request keeps what is cached and does not raise.
    def down(take):
        raise RuntimeError("open-meteo request failed: HTTP 429")
    _, stats = shadow_rain(sub, budget=2, fetch=down, max_age_h=24)
    assert stats["usable"] == 3 and "error" not in stats   # nothing was due
    # A cell is due again only at 6 hours old, however many builds run in between.
    import os
    import time
    p = [rainfall.CACHE / f"forecast_{rainfall.cell_key(*c)}.parquet" for c in cells]
    os.utime(p[0], (time.time() - 2 * 3600,) * 2)
    os.utime(p[1], (time.time() - 7 * 3600,) * 2)
    _, stats = shadow_rain(sub, budget=2, fetch=down)
    assert stats["due"] == 1 and stats["asked"] == 1 and stats["error"].endswith("HTTP 429") and stats["usable"] == 3


# ------------------------------------------------------------------ forecast and log
class _Model:
    """A stand-in spill model: 0.3 on every day with rain data."""

    def predict(self, df):
        return np.full(len(df), 0.3)


def _forecast_table(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast.scottish_shadow import overflow_table
    snap = _snapshot()
    table, _ = overflow_table(_scot_net(snap), snap, year=2026)
    return table


def test_forecast_rows_cover_today_and_four_days_and_mark_missing_rain(tmp_path, monkeypatch):
    table = _forecast_table(tmp_path, monkeypatch)
    from dipcast.ingest import rainfall
    from dipcast.model import forecast
    from dipcast.scottish_shadow import forecast_rows
    monkeypatch.setattr(forecast, "_lead_calibration", dict)
    sub = table[table["forecast"]]
    cells = rainfall.cells_for_sites(sub["lat"], sub["lon"])
    have = [c for c in cells if c != rainfall.cells_for_sites(pd.Series([sub.iloc[-1]["lat"]]), pd.Series([sub.iloc[-1]["lon"]]))[0]]
    now = pd.Timestamp("2026-10-05T06:30", tz="Europe/London")
    rows = forecast_rows(table, now, _rain(have), _Model(), "v1;cov=default")
    assert len(rows) == 4 * 5 and set(rows["lead"]) == {0, 1, 2, 3, 4}
    assert set(rows["site_id"]) == set(sub["site_id"]) and "CSO005416" not in set(rows["site_id"])
    assert rows["target_day"].min() == date(2026, 10, 5) and (rows["issue_day"] == date(2026, 10, 5)).all()
    ok = rows[rows["rain_available"]]
    assert np.allclose(ok["p_raw"], 0.3) and (ok["rain_age_h"] > 0).all()
    missing = rows[rows["site_id"] == sub.iloc[-1]["site_id"]]
    assert (~missing["rain_available"]).all() and (missing["p_raw"] == 0).all()


def test_only_forecasts_that_could_be_scored_are_logged(tmp_path, monkeypatch):
    table = _forecast_table(tmp_path, monkeypatch)
    import duckdb

    from dipcast.model import forecast
    from dipcast.scottish_shadow import FORECASTS_DB, forecast_rows, log_rows
    monkeypatch.setattr(forecast, "_lead_calibration", dict)
    sub = table[table["forecast"]]
    from dipcast.ingest import rainfall
    rain = _rain(rainfall.cells_for_sites(sub["lat"], sub["lon"]))
    at = lambda s: forecast_rows(table, pd.Timestamp(s, tz="Europe/London"), rain, _Model(), "v1")
    assert log_rows(at("2026-10-05T06:30")) == 20      # by 08:00: could be the scored one
    assert log_rows(at("2026-10-05T07:55")) == 20      # still by 08:00: the later one wins
    assert log_rows(at("2026-10-05T11:00")) == 0       # after 08:00 with one before it: never scored
    assert log_rows(at("2026-10-06T11:00")) == 20      # first of its day: scored as a missed deadline
    assert log_rows(at("2026-10-06T14:00")) == 0
    con = duckdb.connect(str(tmp_path / FORECASTS_DB), read_only=True)
    n, cols = con.execute("SELECT count(*) FROM forecast_overflows").fetchone()[0], [r[0] for r in con.execute("DESCRIBE forecast_overflows").fetchall()]
    con.close()
    assert n == 60 and {"covariates", "rain_age_h", "rain_available", "version"} <= set(cols)


# ------------------------------------------------------------------ scores
def _scoring_state(tmp_path, monkeypatch, stuck=False):
    """Two overflows, A and B, forecast at 07:00 on 1 Oct for 2 and 3 Oct; fully observed on 2-4 Oct.
    A spills on 2 Oct. B's monitor reads Overflowing from 3 Oct, flagged stuck if `stuck`."""
    config = _state(tmp_path, monkeypatch)
    from dipcast import forecast_log
    from dipcast.ingest import scottish_water as sw
    from dipcast.scottish_shadow import FORECASTS_DB, OVERFLOWS_FILE, _db_conn
    full = (1 << 48) - 1
    cov = pd.DataFrame([{"site_id": s, "day": pd.Timestamp(d), "n_known": 48, "n_unknown": 0, "n_stale": 0, "slots": full}
                        for s in "AB" for d in ("2026-10-02", "2026-10-03", "2026-10-04")])
    cov.to_parquet(tmp_path / sw.COVERAGE_FILE)
    t = lambda s: pd.Timestamp(s, tz="UTC")
    hist = pd.DataFrame({"site_id": ["A", "B"], "company": "Scottish Water", "discharge_id": ["1", "2"],
                         "event": "latest", "status": [0, 1], "latest_event_start": [t("2026-10-02T10:00"), t("2026-10-03T09:00")],
                         "latest_event_end": [t("2026-10-02T11:00"), pd.NaT], "duration_min": [60.0, np.nan],
                         "stuck": [False, stuck], "first_seen": t("2026-10-04T12:00"), "fetched_at": t("2026-10-04T12:00")})
    hist.to_parquet(tmp_path / sw.HISTORY_FILE)
    pd.DataFrame({"site_id": ["A", "B"], "company": "Scottish Water", "lta_spills": [36.5, np.nan]}).to_parquet(tmp_path / OVERFLOWS_FILE)
    issued = pd.Timestamp("2026-10-01T07:00", tz="Europe/London")
    rows = pd.DataFrame({"issued_at": issued, "issue_day": date(2026, 10, 1), "lat": 56.0, "lon": -4.0,
                         "site_id": ["A", "A", "B", "B"], "has_live": True,
                         "target_day": [date(2026, 10, 2), date(2026, 10, 3)] * 2, "lead": [1, 2, 1, 2],
                         "p_raw": [0.6, 0.1, 0.1, 0.1], "p_cal": [0.6, 0.1, 0.1, 0.1], "weight": 1.0,
                         "rain_available": True, "version": "spill=x;code=0.1.0+abc;cov=default", "rain_mm": 3.0,
                         "covariates": "filled", "rain_age_h": 2.0})
    con = _db_conn()
    con.register("r", rows)
    con.execute("INSERT INTO forecast_overflows BY NAME SELECT * FROM r")
    con.close()
    assert (tmp_path / FORECASTS_DB).exists() and not (tmp_path / "dipcast.duckdb").exists()
    return config, forecast_log


def test_scores_come_from_scotlands_files_and_never_touch_englands(tmp_path, monkeypatch):
    _scoring_state(tmp_path, monkeypatch)
    from dipcast.scottish_shadow import SCORES_CSV, SCORES_JSON, score
    out = score(as_of=date(2026, 10, 5))
    assert out["n_scored"] == 4
    rows = pd.read_csv(tmp_path / SCORES_CSV).set_index(["overflow_id", "day"])
    assert rows.loc[("A", "2026-10-02"), "observed"] == 1 and rows.loc[("A", "2026-10-03"), "observed"] == 0
    assert rows.loc[("B", "2026-10-03"), "observed"] == 1          # discharging since 09:00, not stuck
    assert (rows["company"] == "Scottish Water").all()
    # Climatology from the Scottish table: 36.5 spills a year for A, England's 20 where none.
    assert rows.loc[("A", "2026-10-02"), "climatology"] == round(36.5 / 365, 4)
    assert rows.loc[("B", "2026-10-02"), "climatology"] == round(20 / 365, 4)
    j = json.loads((tmp_path / SCORES_JSON).read_text())
    assert j["by_company"][0]["company"] == "Scottish Water" and "ecoli_live" not in j
    assert j["shadow"]["gate_b"]["arms"][0]["arm"] == "spill=x;cov=default"
    assert j["shadow"]["gate_b"]["arms"][0]["status"] == "too few spill-days"
    # England's files are neither read nor written.
    assert not (tmp_path / "verification_live.json").exists() and not (tmp_path / "verification_live.csv").exists()
    assert not (tmp_path / "dipcast.duckdb").exists()


def test_site_days_of_a_stuck_monitor_are_not_scored(tmp_path, monkeypatch):
    _scoring_state(tmp_path, monkeypatch, stuck=True)
    from dipcast.scottish_shadow import SCORES_CSV, score
    out = score(as_of=date(2026, 10, 5))
    rows = pd.read_csv(tmp_path / SCORES_CSV)
    # B on 3 Oct is left out, and so is B on 2 Oct: England's rule needs an observation the next day.
    assert out["n_scored"] == 2 and set(rows["overflow_id"]) == {"A"}
    assert out["uncovered_by_reason"]["next_day_unobserved"] == 1
    assert out["shadow"]["n_stuck_site_days_left_out"] == 2      # 3 and 4 Oct: the event runs to the poll


def test_gate_b_needs_200_spill_days_and_an_interval_clear_of_zero():
    from dipcast.scottish_shadow import gate_b
    rng = np.random.default_rng(1)
    n_days, n_sites = 90, 40
    y = (rng.random((n_days, n_sites)) < 0.08).astype(int)
    good = np.where(y == 1, 0.6, 0.03)
    rows = lambda p, lead=1: pd.DataFrame({
        "overflow_id": np.tile([f"S{i}" for i in range(n_sites)], n_days),
        "day": np.repeat([str(d.date()) for d in pd.date_range("2026-11-01", periods=n_days)], n_sites),
        "lead": lead, "forecast_calibrated": p.ravel(), "climatology": 0.08, "observed": y.ravel(), "arm": "a"})
    g = gate_b(rows(good))["arms"][0]
    assert g["n_spill_days"] >= 200 and g["status"] == "pass" and g["interval_95"][0] > 0
    assert gate_b(rows(good)) == gate_b(rows(good))                     # seeded: the same every run
    bad = gate_b(rows(np.where(y == 1, 0.02, 0.4)))["arms"][0]
    assert bad["status"] == "not passed" and bad["skill"] < 0
    assert gate_b(rows(good, lead=0))["arms"] == []                     # same-day forecasts are not the gate
    few = rows(good).iloc[: 40 * 20]
    assert gate_b(few)["arms"][0]["status"] == "too few spill-days"


# ------------------------------------------------------------------ off by default, never published
def test_build_calls_the_shadow_only_behind_the_setting():
    tree = ast.parse((ROOT / "scripts" / "build_site.py").read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "dipcast.scottish_shadow"]
    assert len(calls) == 1
    guards = [n for n in ast.walk(tree) if isinstance(n, ast.If) and calls[0] in ast.walk(n)]
    assert guards and all("config.SCOTTISH_WATER" in ast.unparse(g.test) for g in guards[-1:])
    assert "refresh" in ast.unparse(guards[-1].test)


def test_no_shadow_file_is_published_or_read_by_the_site():
    from dipcast.ingest import scottish_water as sw
    from dipcast.scottish_shadow import FILES
    names = FILES + [sw.LATEST_FILE, sw.HISTORY_FILE, sw.COVERAGE_FILE]
    workflow = (ROOT / ".github" / "workflows" / "site.yml").read_text()
    site = "\n".join(p.read_text() for p in (ROOT / "src" / "dipcast" / "site").glob("*.*") if p.suffix in (".js", ".html"))
    build = (ROOT / "scripts" / "build_site.py").read_text() + (ROOT / "scripts" / "build_any_point.py").read_text()
    for n in names:
        assert n not in workflow and n not in site and n not in build, n
    # The workflow may only pass the on/off setting to the build; any other Scottish line (an upload, a
    # release asset, a Pages path) fails here.
    allowed = {"# scottish water shadow (scotland plan s4, s5): 1 polls and scores in state only, publishes nothing; unset = off.",
               "dipcast_scottish_water: ${{ vars.dipcast_scottish_water }}"}
    lines = [ln.strip() for ln in workflow.lower().splitlines() if "scottish" in ln]
    assert set(lines) <= allowed, lines


def test_run_never_raises(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast import scottish_shadow
    out = scottish_shadow.run(net=object(), model=_Model())   # no stored answer: fails inside, reports it
    assert out["ok"] is False and "error" in out
