"""The spot level scored against the spills that happened (forecast_log.verify_spots; docs/PREREGISTRATION-2027.md,
amendment 1, S1): known spills reproduce the observed exposure exactly, through the forecast's own weights and
travel times; the 95% coverage rule; and the published rows."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

TZ = "Europe/London"
D = date(2026, 10, 14)


def _day(n: int) -> date:
    return D + pd.Timedelta(days=n)


def _status(rows):
    """(site_id, day offset from D, e, reason) tuples as spot_exposure's status frame."""
    return pd.DataFrame([{"site_id": s, "day": _day(k), "e": e, "reason": r} for s, k, e, r in rows])


# A: beside the spot. B: 36 h upstream, so a target day's water left it half one day before and half two days before.
# C: exactly 48 h upstream, so only the day two before reaches the spot.
LINKS = pd.DataFrame({"cell": [0, 0, 0], "site_id": ["A", "B", "C"], "weight": [0.5, 0.8, 0.2],
                      "travel_h": [0.0, 36.0, 48.0], "has_live": [True, True, True]})
CELLS = pd.DataFrame({"cell": [0], "day": [D]})


def test_known_spills_reproduce_the_observed_exposure_exactly():
    from dipcast.forecast_log import spot_exposure
    from dipcast.model.transport import combine_daily
    # A spilled on the day; B two days before (not one before); C did not spill two days before.
    st = _status([("A", 0, 1, None), ("B", -1, 0, None), ("B", -2, 1, None), ("C", -2, 0, None), ("C", -3, 1, "max_gap")])
    out = spot_exposure(CELLS, LINKS, st).iloc[0]
    # o = 1 - (1 - 0.5 x 1)(1 - 0.8 x (0.5 x 0 + 0.5 x 1))(1 - 0.2 x 0) = 1 - 0.5 x 0.6 = 0.7
    assert out["observed"] == pytest.approx(0.7, abs=1e-12)
    assert out["covered"] == 1.0 and out["reason"] is None
    # The same as the forecast's own transport with the spills as its chances: rows A, B, C, days D-3 .. D.
    e = np.array([[0, 0, 0, 1], [0, 1, 0, 0], [1, 0, 0, 0]], dtype=float)
    assert combine_daily(e, LINKS["weight"].to_numpy(), LINKS["travel_h"].to_numpy())[-1] == pytest.approx(out["observed"], abs=1e-12)
    # C's unobserved day three before reaches nothing: 48 h is exactly two days.


def test_every_source_day_must_be_observed():
    from dipcast.forecast_log import spot_exposure
    # B's second source day (two before) has no observation: B is out, and B carries 0.8 of 1.5.
    st = _status([("A", 0, 1, None), ("B", -1, 0, None), ("B", -2, 0, "min_known_polls"), ("C", -2, 0, None)])
    out = spot_exposure(CELLS, LINKS, st).iloc[0]
    assert np.isnan(out["observed"]) and out["reason"] == "min_known_polls"
    assert out["covered"] == pytest.approx(0.7 / 1.5)
    # An overflow-day with no status row at all was never observed: the gap rule, as verify_live counts it.
    out = spot_exposure(CELLS, LINKS, _status([("A", 0, 1, None), ("B", -1, 0, None), ("B", -2, 0, None)])).iloc[0]
    assert np.isnan(out["observed"]) and out["reason"] == "max_gap" and out["covered"] == pytest.approx(1.3 / 1.5)


def test_the_95_percent_rule_and_overflows_without_a_live_feed():
    from dipcast.forecast_log import spot_exposure
    links = LINKS.assign(weight=[0.5, 0.45, 0.05])     # C carries exactly 5%
    st = _status([("A", 0, 1, None), ("B", -1, 0, None), ("B", -2, 0, None), ("C", -2, 1, "feed_not_current")])
    out = spot_exposure(CELLS, links, st).iloc[0]
    # 95% observed is enough; C is left out of o, as if it had not spilled.
    assert out["covered"] == pytest.approx(0.95) and out["reason"] is None and out["observed"] == pytest.approx(0.5)
    out = spot_exposure(CELLS, links.assign(weight=[0.5, 0.44, 0.06]), st).iloc[0]
    assert np.isnan(out["observed"]) and out["reason"] == "feed_not_current"
    # An overflow with no live feed over 5% of the weight: never observed, whatever the rest did.
    nolive = links.assign(weight=[0.5, 0.44, 0.06], has_live=[True, True, False])
    out = spot_exposure(CELLS, nolive, _status([("A", 0, 1, None), ("B", -1, 0, None), ("B", -2, 0, None)])).iloc[0]
    assert np.isnan(out["observed"]) and out["reason"] == "no_live_feed" and out["covered"] == pytest.approx(0.94)
    # Without a travel time the source days are not known.
    out = spot_exposure(CELLS, LINKS.assign(travel_h=[0.0, np.nan, 48.0]), st).iloc[0]
    assert np.isnan(out["observed"]) and np.isnan(out["covered"]) and out["reason"] == "no_travel_time"


def _state(tmp_path, monkeypatch):
    from dipcast import config
    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "PROCESSED", tmp_path)
    monkeypatch.setattr(config, "DUCKDB_PATH", tmp_path / "t.duckdb")
    return config


def _mask(hours):
    return int(sum(1 << (h * 2) for h in hours))


def test_verify_spots_writes_the_registered_rows(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast import forecast_log as fl
    ov = pd.DataFrame({"site_id": ["A", "B"], "has_live": [True, True], "weight": [0.5, 0.8], "travel_h": [0.0, 36.0]})
    days = pd.date_range("2026-10-12", periods=7, freq="D", tz=TZ)     # two days of history, the 14th to the 18th
    zeros = np.zeros((2, len(days)))

    def log(at, risk):
        fl.log_forecast(pd.Timestamp(at, tz=TZ), 54.0, -2.0, "river", "R", 0.0, days, np.full(len(days), risk), ov,
                        zeros, zeros, version="v-test")
    log("2026-10-14 07:00", 0.45)       # the decision forecast for the 14th (lead 0) and the 15th (lead 1)
    log("2026-10-14 07:30", 0.42)       # a later one, still by 08:00: this is the one scored
    log("2026-10-15 09:00", 0.9)        # after 08:00: the 15th at lead 0 is a missed deadline
    # A spilled on the 14th, B on the 12th.
    hist = pd.DataFrame({"site_id": ["A", "B"], "company": ["X Water", "Y Water"], "status": [0, 0],
                         "latest_event_start": pd.to_datetime(["2026-10-14 10:00", "2026-10-12 10:00"], utc=True),
                         "latest_event_end": pd.to_datetime(["2026-10-14 11:00", "2026-10-12 11:00"], utc=True),
                         "fetched_at": pd.to_datetime(["2026-10-15 12:00", "2026-10-15 12:00"], utc=True)})
    hist.to_parquet(tmp_path / "live_history.parquet", index=False)
    cov_days = pd.date_range("2026-10-12", "2026-10-16", freq="D")
    cov = pd.DataFrame([{"site_id": s, "day": d, "n_known": 12, "n_unknown": 0, "n_stale": 0, "slots": _mask(range(0, 24, 2))}
                        for s in ("A", "B") for d in cov_days])
    cov.to_parquet(tmp_path / fl.COVERAGE_FILE, index=False)
    pd.DataFrame({"site_id": ["A", "B"], "company": ["X Water", "Y Water"], "lta_spills": [36.5, 73.0]}).to_parquet(
        tmp_path / "overflows.parquet", index=False)
    spots = pd.DataFrame({"id": ["s1", "far"], "name": ["Spot one", "Far away"], "lat": [54.00001, 51.0],
                          "lon": [-2.00002, 0.0], "kind": ["river", "lake"]})
    out = fl.verify_spots(as_of=date(2026, 10, 16), spots=spots)
    rows = pd.read_csv(tmp_path / fl.SPOTS_CSV, dtype={"spot_id": str})
    # The registered columns, one row per eligible spot, day (the 14th, 15th) and lead 0-4.
    assert list(rows.columns) == fl.SPOT_COLUMNS
    assert len(rows) == 1 * 2 * 5 and set(rows["spot_id"]) == {"s1"} and out["n_spots"] == 1
    r = rows.set_index(["day", "lead"])
    # The 14th, lead 0: the 07:30 forecast, and o = 1 - (1 - 0.5)(1 - 0.8 x 0.5) = 0.7 from the known spills.
    assert r.loc[("2026-10-14", 0), "forecast"] == 0.42 and r.loc[("2026-10-14", 0), "observed"] == 0.7
    assert r.loc[("2026-10-14", 0), "issued_at"] == "2026-10-14T07:30+01:00" and r.loc[("2026-10-14", 0), "version"] == "v-test"
    assert r.loc[("2026-10-14", 0), "covered"] == 1.0 and pd.isna(r.loc[("2026-10-14", 0), "reason"])
    # The 15th, lead 1, from the same forecast: nothing reached the spot that day.
    assert r.loc[("2026-10-15", 1), "observed"] == 0.0 and r.loc[("2026-10-15", 1), "forecast"] == 0.42
    # The 15th, lead 0: issued only at 09:00. Leads with no forecast at all: no_forecast, issued_at and forecast empty.
    assert r.loc[("2026-10-15", 0), "reason"] == "missed_deadline"
    late = r.loc[("2026-10-15", 0)]
    assert pd.isna(late["issued_at"]) and pd.isna(late["forecast"]) and pd.isna(late["version"]) and pd.isna(late["observed"])
    assert (r.loc[("2026-10-14", 2), "reason"] == "no_forecast") and out["not_observed"] == {"no_forecast": 7, "missed_deadline": 1}
    # The alert's record at the High line: the 14th was an event and warned of; the 15th a false alarm.
    o = out["overall"]
    assert (o["n"], o["hits"], o["false_alarms"], o["misses"], o["quiet_correct"]) == (2, 1, 1, 0, 0)
    # Forecast High risk twice: observed Low once, and Very high once (0.7 is on the cut, so in the band above).
    assert out["levels"]["counts"][2] == [1, 0, 0, 1]
    assert out["by_company"][0]["company"] == "Y Water"     # B carries the most weight
    # The reference: each overflow's c x f (October's factor) combined the same way. c is 0.1 and 0.2 a day.
    f = fl._month_factors()[10]
    assert o["climatology"]["mean"] == pytest.approx(1 - (1 - 0.5 * 0.1 * f) * (1 - 0.8 * 0.2 * f), abs=1e-6)
    # The reference is published too, at 6 places, beside the observation (amendment 2, item 8).
    text = (tmp_path / fl.SPOTS_CSV).read_text().splitlines()
    assert text[0].split(",")[6] == "climatology"
    row = next(x for x in text if x.startswith("s1,2026-10-14,0,")).split(",")
    assert row[4] == "0.420000" and row[5] == "0.700000" and len(row[6].split(".")[1]) == 6
    assert out["csv"] == {"file": fl.SPOTS_CSV, "rows": 10, "columns": fl.SPOT_COLUMNS}
    assert out["spots_without_overflows"] == 0 and out["never_observed"] == []


def test_verify_spots_with_nothing_logged_writes_a_header(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    from dipcast import forecast_log as fl
    out = fl.verify_spots(as_of=date(2026, 10, 16), spots=pd.DataFrame(columns=["id", "name", "lat", "lon", "kind"]))
    assert out["n_cells"] == 0 and out["csv"]["rows"] == 0
    assert (tmp_path / fl.SPOTS_CSV).read_text().strip() == ",".join(fl.SPOT_COLUMNS)


def test_the_published_spot_csv_carries_the_credits_and_only_rows_that_match(tmp_path, monkeypatch):
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_site as bs   # before the state is moved: build_site binds config.PROCESSED in a default argument
    config = _state(tmp_path / "state", monkeypatch)
    config.STATE.mkdir()
    from dipcast.forecast_log import SPOT_COLUMNS, SPOTS_CSV
    pd.DataFrame([["s1", "2026-10-14", 0, "2026-10-14T07:30+01:00", 0.42, 0.7, 0.1, 1.0, None, "v"]] * 2,
                 columns=SPOT_COLUMNS).to_csv(config.STATE / SPOTS_CSV, index=False)
    site = tmp_path / "site"
    (site / "data").mkdir(parents=True)
    ver = site / "data" / "verification.json"
    ver.write_text(json.dumps({"live": {"spots_live": {"n_cells": 2, "csv": {"rows": 2}}}}))
    credits = bs.data_credits("https://example.org/")
    assert bs.publish_spots_csv(site, credits, "https://example.org/") == 2
    text = (site / "data" / SPOTS_CSV).read_text()
    head = "\n".join(x for x in text.splitlines() if x.startswith("#"))
    assert credits["attribution"] in head and credits["full"] in head and all(u in head for u in credits["licences"].values())
    assert "PREREGISTRATION-2027.md (amendment 1)" in head and "https://example.org/verification.html#spot-level" in head
    rows = pd.read_csv(site / "data" / SPOTS_CSV, comment="#")
    assert list(rows.columns) == SPOT_COLUMNS and len(rows) == 2
    # Rows that disagree with the scores are withdrawn, with the page's link.
    ver.write_text(json.dumps({"live": {"spots_live": {"n_cells": 3, "csv": {"rows": 3}}}}))
    assert bs.publish_spots_csv(site, credits, "https://example.org/") is None
    assert not (site / "data" / SPOTS_CSV).exists() and "csv" not in json.loads(ver.read_text())["live"]["spots_live"]
    # Scores from before this file existed: nothing to publish.
    ver.write_text(json.dumps({"live": {"n_scored": 2}}))
    assert bs.publish_spots_csv(site, credits, "https://example.org/") is None
    assert 'health["spot_rows_published"] = publish_spots_csv(SITE, credits, site_url())' in Path(bs.__file__).read_text()


def test_the_latest_decision_forecast_is_taken_whole_and_a_missing_value_is_not_scored(tmp_path, monkeypatch):
    """The decision forecast is the latest issued by 08:00, as one row. Here the 07:30 forecast logged no risk
    (log_forecast allows NULL): its issue time and version stand, its forecast is empty, and it is neither a forecast
    nor scored. The 07:00 risk must not be carried into it (pandas' groupby().last() takes each column's last
    non-null value separately, which did that)."""
    _state(tmp_path, monkeypatch)
    from dipcast import forecast_log as fl
    ov = pd.DataFrame({"site_id": ["A"], "has_live": [True], "weight": [0.5], "travel_h": [0.0]})
    days = pd.date_range("2026-10-12", periods=7, freq="D", tz=TZ)
    zeros = np.zeros((1, len(days)))

    def log(at, risk, version):
        fl.log_forecast(pd.Timestamp(at, tz=TZ), 54.0, -2.0, "river", "R", 0.0, days, np.full(len(days), risk), ov,
                        zeros, zeros, version=version)
    log("2026-10-14 07:00", 0.45, "v-old")
    log("2026-10-14 07:30", np.nan, "v-new")
    hist = pd.DataFrame({"site_id": ["A"], "company": ["X Water"], "status": [0],
                         "latest_event_start": pd.to_datetime(["2026-10-14 10:00"], utc=True),
                         "latest_event_end": pd.to_datetime(["2026-10-14 11:00"], utc=True),
                         "fetched_at": pd.to_datetime(["2026-10-15 12:00"], utc=True)})
    hist.to_parquet(tmp_path / "live_history.parquet", index=False)
    cov = pd.DataFrame([{"site_id": "A", "day": d, "n_known": 12, "n_unknown": 0, "n_stale": 0, "slots": _mask(range(0, 24, 2))}
                        for d in pd.date_range("2026-10-12", "2026-10-16", freq="D")])
    cov.to_parquet(tmp_path / fl.COVERAGE_FILE, index=False)
    pd.DataFrame({"site_id": ["A"], "company": ["X Water"], "lta_spills": [36.5]}).to_parquet(
        tmp_path / "overflows.parquet", index=False)
    spots = pd.DataFrame({"id": ["s1"], "name": ["Spot one"], "lat": [54.00001], "lon": [-2.00002], "kind": ["river"]})
    out = fl.verify_spots(as_of=date(2026, 10, 16), spots=spots)
    r = pd.read_csv(tmp_path / fl.SPOTS_CSV, dtype={"spot_id": str}).set_index(["day", "lead"])
    for cell in (("2026-10-14", 0), ("2026-10-15", 1)):    # both from the 07:30 forecast
        row = r.loc[cell]
        assert row["issued_at"] == "2026-10-14T07:30+01:00" and row["version"] == "v-new"
        assert pd.isna(row["forecast"])                    # not 0.45 from the 07:00 row
    # The spot-day is still observed (A spilled on the 14th: o = 0.5); only the forecast is missing.
    assert r.loc[("2026-10-14", 0), "observed"] == 0.5 and pd.isna(r.loc[("2026-10-14", 0), "reason"])
    # Missing forecasts are counted as neither a forecast nor a scored cell.
    assert out["n_forecast"] == 0 and out["n_scored"] == 0 and out["n_observed"] >= 1


# ------------------------------------------------------------------ amendment 2 (signed 25 Oct 2026)

def test_levels_are_the_ones_the_site_shows():
    """Item 3: a level is transport.risk_label's, from the 0-100 score on the page, not the raw cut."""
    from dipcast import forecast_log as fl
    from dipcast.model.transport import risk_label
    # 0.395 shows as 40, High risk, under the raw cut of 0.40. (0.145 shows as 14: in floating point 0.145 x 100 is
    # 14.499999999999998, on the page too, so hand-picked edges mislead; the grid below is the check.)
    xs = [0.0, 0.1449, 0.15, 0.3944, 0.395, 0.40, 0.6944, 0.70, 1.0, np.nan]
    assert list(fl.spot_levels(xs)) == [0, 0, 1, 1, 2, 2, 2, 3, 3, -1]
    grid = np.round(np.linspace(0, 1, 20001), 6)
    assert [fl.SPOT_BANDS[i] for i in fl.spot_levels(grid)] == [risk_label(float(x)) for x in grid]


def _cells(rows):
    """spot_summary's input: (spot, day, lead, risk, observed, climatology)."""
    g = pd.DataFrame(rows, columns=["spot_id", "day", "lead", "risk", "observed", "climatology"])
    return g.assign(cell=range(len(g)), issued_ms=1.0, reason=None, covered=1.0, no_live=0.0)


def test_the_summary_counts_levels_from_the_shown_score():
    from dipcast import forecast_log as fl
    spots = pd.DataFrame({"id": ["s"], "name": ["S"], "kind": ["river"]})
    links = pd.DataFrame({"cell": [0, 1], "site_id": ["A", "A"], "weight": [1.0, 1.0]})
    # 0.395 shows as 40, High risk: a warning, though under the raw cut. 0.3945 observed shows as 40 too: an event.
    g = _cells([("s", D, 0, 0.395, 0.3945, 0.2), ("s", D, 1, 0.3944, 0.0, 0.2)])
    out = fl.spot_summary(g, spots, links)
    o = out["overall"]
    assert (o["hits"], o["false_alarms"], o["misses"], o["quiet_correct"]) == (1, 0, 0, 1)
    assert out["levels"]["counts"][2][2] == 1 and out["levels"]["counts"][1][0] == 1 and out["levels"]["score_cuts"] == [15, 40, 70]


def test_the_figures_come_from_the_rows_as_written():
    """Item 11: the summary reads the 6-place values the CSV gives back, so the page and the evaluation agree.
    0.39449996 is Moderate risk unrounded (round(x, 3) = 0.394), but is written 0.394500, which is High risk."""
    from dipcast import forecast_log as fl
    raw = pd.Series([0.39449996])
    assert fl.spot_levels(raw)[0] == 1
    pub = fl.as_published(raw)
    assert pub[0] == float("0.394500") and fl.spot_levels(pub)[0] == 2
    # The evaluation reads the same double from the text, with pandas' round-trip parser.
    import io
    back = pd.read_csv(io.StringIO("x\n0.394500\n"), float_precision="round_trip")["x"]
    assert back[0] == pub[0]


def test_never_observed_spots_carry_their_share_without_a_live_feed():
    """Item 7: each spot never observed is listed with the share of its weight on overflows with no live feed."""
    from dipcast import forecast_log as fl
    g = _cells([("s", D, 0, 0.1, np.nan, 0.1), ("s", D, 1, 0.1, np.nan, 0.1)]).assign(reason="no_live_feed", no_live=[0.18, 0.181])
    out = fl.spot_summary(g, pd.DataFrame({"id": ["s"], "name": ["S"], "kind": ["river"]}), pd.DataFrame(columns=["cell", "site_id", "weight"]))
    assert out["never_observed"] == [{"spot_id": "s", "name": "S", "share_no_live": 0.181}]
