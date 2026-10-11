"""Tests for the 11 Oct 2026 audit of stale live data (PR "feed freshness"):

1. A spill running when its company's feed failed stays running through the outage: carry_forward
   keeps the last status read, transport.running counts it, and the right-now risk and counts keep it.
2. A record that has stopped updating in a feed that has not is stale, shown and scored as such:
   WSX10153 and WXW00014 (Wessex Water) last stamped on 22 Jul 2025 and 31 Mar 2026 read as live
   "not discharging" at Warleigh Weir and French Weir Park, and were scored as dry days.
4. The spill model's covariates are filled once, from company-wide medians, and the accuracy
   baseline fills the same gaps the same way."""

import numpy as np
import pandas as pd
import pytest

T = pd.Timestamp("2026-10-11 18:16", tz="UTC")
H = lambda x: T - pd.Timedelta(hours=x)


def _state(tmp_path, monkeypatch, feeds):
    from dipcast import config
    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "PROCESSED", tmp_path)
    monkeypatch.setattr(config, "LIVE_FEEDS", feeds)
    return config


def _poll(ts, rows):
    """rows: (site, company, status); every record stamped 10 minutes before the poll."""
    t = pd.Timestamp(ts, tz="UTC")
    return pd.DataFrame({"site_id": [r[0] for r in rows], "company": [r[1] for r in rows], "status": [r[2] for r in rows],
                         "status_start": t - pd.Timedelta(hours=2), "latest_event_start": t - pd.Timedelta(hours=2),
                         "latest_event_end": pd.NaT, "lat": 54.0, "lon": -2.0, "receiving_watercourse": "r",
                         "last_updated": t - pd.Timedelta(minutes=10), "fetched_at": t})


# ------------------------------------------------------------------ 1. a spill through a feed outage

def test_a_spill_running_when_the_feed_fails_keeps_its_last_status(tmp_path, monkeypatch):
    from dipcast.ingest import live
    _state(tmp_path, monkeypatch, {"U": "u", "Y": "v"})
    live.save_live(_poll("2026-10-11 08:00", [("A", "U", 0), ("B", "Y", 1), ("C", "Y", 0)]))
    latest = pd.read_parquet(tmp_path / "live_latest.parquet").set_index("site_id")
    assert latest["last_status"].tolist() == [0, 1, 0]          # a fresh row: its own status
    live.save_live(_poll("2026-10-11 12:00", [("A", "U", 0)]))  # Y's feed fails
    live.save_live(_poll("2026-10-11 16:00", [("A", "U", 0)]))  # and is still down
    latest = pd.read_parquet(tmp_path / "live_latest.parquet").set_index("site_id")
    assert latest.loc[["B", "C"], "status"].eq(live.FEED_DOWN).all()
    assert latest.loc["B", "last_status"] == 1 and latest.loc["C", "last_status"] == 0   # kept through both polls
    assert latest.loc["B", "feed_down_since"] == pd.Timestamp("2026-10-11 08:00", tz="UTC")
    assert pd.isna(latest.loc["B", "latest_event_end"])          # as on every discharging row: no end
    live.save_live(_poll("2026-10-11 18:00", [("A", "U", 0), ("B", "Y", 0), ("C", "Y", 0)]))   # Y answers
    latest = pd.read_parquet(tmp_path / "live_latest.parquet").set_index("site_id")
    assert latest["status"].tolist() == [0, 0, 0] and latest["last_status"].tolist() == [0, 0, 0]


def _carried():
    """Three overflows upstream of a spot: one carried through an outage while it was discharging,
    one carried while quiet, one quiet on a feed that answered. Weights and travel times as
    upstream_overflows gives them."""
    from dipcast.ingest.live import FEED_DOWN
    since = pd.Timestamp("2026-10-11 08:00", tz="UTC")
    return pd.DataFrame({"site_id": ["B", "C", "A"], "company": ["Y", "Y", "U"], "status": [FEED_DOWN, FEED_DOWN, 0],
                         "last_status": [1.0, 0.0, 0.0], "feed_down_since": [since, since, pd.NaT],
                         "has_live": True, "data_state": ["offline", "offline", "live"],
                         "feed_updated_at": [pd.NaT, pd.NaT, H(0.2)], "latest_event_start": [since - pd.Timedelta(hours=2)] * 3,
                         "latest_event_end": pd.NaT, "weight": [0.6, 0.6, 0.3], "travel_h": [2.0, 2.0, 1.0]})


def test_the_carried_spill_counts_in_the_risk_and_as_discharging():
    from dipcast.model.forecast import carried_fields, live_counts
    from dipcast.model.transport import clear_time, live_now_risk, running
    ov = _carried()
    assert running(ov).tolist() == [True, False, False]
    risk, contrib = live_now_risk(ov, T)
    assert risk == contrib.max() == 0.6                     # before: 0, as the spill had no end time
    assert clear_time(ov, T)[0] is not None                 # and it has a time to clear, as a running spill does
    c = live_counts(ov, contrib)
    assert c["discharging_upstream"] == 1 and c["recent_upstream"] == 0
    assert c["monitored_upstream"] == 2                     # the carried spill (a feed's last word) and A
    assert c["feed_down_upstream"] == 1                     # C alone could be spilling unseen
    assert c["feed_down"] == [{"company": "Y", "overflows": 1, "since": "2026-10-11T08:00:00+00:00"}]
    assert carried_fields(ov.iloc[0]) == {"last_status": 1, "feed_down_since": "2026-10-11T08:00:00+00:00"}
    assert carried_fields(ov.iloc[2]) == {}
    # A table from before last_status: a carried row counts as before, with no spill.
    old = ov.drop(columns="last_status")
    assert running(old).tolist() == [False, False, False] and live_now_risk(old, T)[0] == 0.0


# ------------------------------------------------------------------ 2. a record that stopped updating

def _wessex_poll():
    """One poll as build_overflows sees it. W stamps every record on every refresh (38 of its 40
    within the day, 95%); WM last stamped in March and WN carries no stamp. N stamps a record only
    when it changes: most of its stamps are weeks old, which says nothing."""
    rows = [(f"W{i:02d}", "W", 0, H(0.1)) for i in range(37)] + [("WX", "W", -1, H(0.1))]
    rows += [("WN", "W", 0, pd.NaT), ("WM", "W", 0, pd.Timestamp("2026-03-31 14:23", tz="UTC"))]
    rows += [("N0", "N", 0, H(1.3)), ("N1", "N", 0, H(900)), ("N2", "N", 0, H(2000))]
    df = pd.DataFrame(rows, columns=["site_id", "company", "status", "last_updated"])
    df["last_updated"] = pd.to_datetime(df["last_updated"], utc=True)
    return df.assign(fetched_at=T, has_live=True)


def test_a_record_that_stopped_updating_is_stale_with_its_own_time():
    from dipcast.ingest.live import data_states, frozen_records, stamps_every_record
    df = _wessex_poll()
    assert stamps_every_record(df).to_dict() == {"N": False, "W": True}   # 38 of 40 W records within a day: 95%
    assert sorted(df.loc[frozen_records(df), "site_id"]) == ["WM", "WN"]
    st = df[["site_id"]].join(data_states(df)).set_index("site_id")
    assert st.loc[["WM", "WN"], "data_state"].eq("stale").all() and st.loc[["WM", "WN"], "record_stale"].all()
    assert st.loc["WM", "feed_updated_at"] == pd.Timestamp("2026-03-31 14:23", tz="UTC")   # its own stamp
    assert pd.isna(st.loc["WN", "feed_updated_at"])
    assert st.loc["W00", "data_state"] == "live" and st.loc["W00", "feed_updated_at"] == H(0.1)
    assert st.loc["WX", "data_state"] == "offline" and not st.loc["WX", "record_stale"]
    assert st.loc[["N0", "N1", "N2"], "data_state"].eq("live").all()    # a stamp-on-change feed: company test only


def test_a_frozen_record_is_not_scored_and_not_counted_as_reporting():
    from dipcast.ingest.live import coverage_rows, data_states
    from dipcast.model.forecast import live_counts
    df = _wessex_poll()
    cov = coverage_rows(df).set_index("site_id")
    assert cov.loc[["WM", "WN"], "n_stale"].tolist() == [1, 1] and cov.loc[["WM", "WN"], "slots"].eq(0).all()
    assert cov.loc["W00", "n_stale"] == 0 and cov.loc["W00", "slots"] != 0
    assert cov.loc[["N1", "N2"], "n_stale"].eq(0).all()
    ov = df.join(data_states(df))
    c = live_counts(ov, pd.Series(0.0, index=ov.index))
    assert c["monitored_upstream"] == 37 + 3 and c["stale_upstream"] == 2
    assert c["feed_stale"] == [{"company": "W", "overflows": 2, "since": "2026-03-31T14:23:00+00:00", "records": True}]
    assert c["quiet_by_feed"] == [{"company": "N", "overflows": 3, "updated_at": H(1.3).isoformat()},
                                  {"company": "W", "overflows": 37, "updated_at": H(0.1).isoformat()}]


def test_a_company_under_the_share_is_read_as_stamp_on_change(caplog):
    """Half to 95% within the day is logged: it may be many frozen records or a storm on a
    stamp-on-change feed, and the company test alone applies."""
    from dipcast.ingest.live import frozen_records, stamps_every_record
    df = _wessex_poll()
    df.loc[df["site_id"].isin(["W00", "W01", "W02", "W03"]), "last_updated"] = H(400)
    assert not stamps_every_record(df)["W"] and not frozen_records(df).any()
    assert "W: 85.0% of its records stamped" in caplog.text


# ------------------------------------------------------------------ 4. covariates filled once

def test_covariates_are_filled_from_company_wide_medians_once():
    from dipcast.model.features import fill_covariates, model_covariates, site_static_features
    table = pd.DataFrame({"site_id": ["a", "b", "c", "d", "e", "f"], "company": ["W", "W", "W", "W", "Y", "Z"],
                          "lta_spills": [10.0, 20.0, 60.0, np.nan, np.nan, np.nan],
                          "spill_hours": [5.0, np.nan, 50.0, np.nan, 7.0, np.nan],
                          "edm_operational_pct": [99.0, 98.0, 97.0, np.nan, np.nan, np.nan],
                          "lat": 51.0, "lon": -2.0})
    t = fill_covariates(table)
    assert t["lta_spills_filled"].tolist() == [10.0, 20.0, 60.0, 20.0, 20.0, 20.0]   # W's median, then the table's
    assert t["spill_hours_filled"].tolist() == [5.0, 27.5, 50.0, 27.5, 7.0, 7.0]
    assert t["covariates_filled"].tolist() == [False, True, False, True, True, True]
    assert t["lta_spills"].isna().sum() == 3                                         # the raw column is left as it is
    # A spot whose upstream W overflows are the spilliest gets the same value for d as any other spot.
    up = t[t["site_id"].isin(["c", "d"])]
    sites = pd.concat([up[["site_id", "lat", "lon", "company"]], model_covariates(up)], axis=1)
    assert np.expm1(site_static_features(sites).set_index("site_id").loc["d", "log_lta_spills"]) == pytest.approx(20.0)
    # Before: filled over the spot's upstream overflows alone, d took c's 60.
    raw = up[["site_id", "lat", "lon", "company", "lta_spills", "spill_hours", "edm_operational_pct"]]
    assert np.expm1(site_static_features(raw).set_index("site_id").loc["d", "log_lta_spills"]) == pytest.approx(60.0)


def test_the_accuracy_baseline_fills_a_gap_as_the_forecast_does(tmp_path):
    from dipcast.forecast_log import _site_climatology, _spill_days_per_spill
    from dipcast.model.features import fill_covariates
    p = tmp_path / "overflows.parquet"
    table = pd.DataFrame({"site_id": ["a", "b", "c"], "company": "W", "lta_spills": [10.0, 30.0, np.nan],
                          "spill_hours": 1.0, "edm_operational_pct": 99.0})
    fill_covariates(table).to_parquet(p)
    r = _spill_days_per_spill() / 365.0
    got = _site_climatology(pd.Series(["a", "c", "zz"]), p)
    assert np.allclose(got, [10 * r, 20 * r, 20 * r])          # c: W's median 20; an unknown id: 20, as before
    table.assign(lta_spills=[10.0, 30.0, 50.0]).to_parquet(p)   # a table from before the filled column
    assert np.allclose(_site_climatology(pd.Series(["c"]), p), [50 * r])
