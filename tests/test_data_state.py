"""Tests for each overflow's data state (ingest.live.data_states): a frozen or unverified feed must
never read as "not discharging". The nine live layers' fields come from their own metadata,
kept in fixtures/live_layer_fields.json; the rest uses small tables built here."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

FIELDS = json.loads((Path(__file__).parent / "fixtures" / "live_layer_fields.json").read_text())["layers"]
T = pd.Timestamp("2026-10-04 08:00", tz="UTC")
MS = lambda ts: int(pd.Timestamp(ts).value // 1_000_000)


def test_every_layer_is_the_hubs_schema_and_maps_to_its_names():
    """All nine layers carry the hub's ten fields and an object id, no flag for validation,
    dry weather or high river, and Status coded 1 Start, 0 Stop, -1 Offline. South West Water
    spells them in camelCase, which an exact match never read."""
    from dipcast import config
    from dipcast.ingest.live import RENAME, hub_names
    assert set(FIELDS) == set(config.LIVE_FEEDS)
    for company, layer in FIELDS.items():
        names = [f for f in layer["fields"] if f.lower() != "objectid"]
        assert len(names) == len(RENAME), company
        mapped = hub_names(pd.DataFrame(columns=names)).columns
        assert set(mapped) == set(RENAME), company
        assert layer["status_domain"] == {"1": "Start", "0": "Stop", "-1": "Offline"}, company
    assert sorted(n for n in FIELDS["South West Water"]["fields"] if n not in RENAME and n != "ObjectId") == [
        "company", "lastUpdated", "latestEventEnd", "latestEventStart", "latitude", "longitude",
        "receivingWaterCourse", "status", "statusStart"]


def _sww_rows(stamped: bool):
    """Rows in South West Water's spelling."""
    t = MS("2026-10-04 07:50") if stamped else None
    return [{"Id": f"SWW{i}", "company": "South West Water", "status": s, "statusStart": t, "latestEventStart": None,
             "latestEventEnd": None, "latitude": None, "longitude": None, "receivingWaterCourse": "River Dart",
             "lastUpdated": t, "_x": -3.8, "_y": 50.5 + 0.01 * i} for i, s in enumerate([0, 1])]


def test_fetch_live_reads_camel_case_fields_and_asks_the_layer_only_when_records_carry_no_stamp(monkeypatch):
    from dipcast.ingest import live
    asked = []
    monkeypatch.setattr(live, "layer_edit_time", lambda url: asked.append(url) or MS("2026-10-04 07:58"))
    monkeypatch.setattr(live, "fetch_all", lambda url, **kw: _sww_rows(stamped=True))
    df = live.fetch_live({"South West Water": "https://x/0"})
    assert df["last_updated"].notna().all() and df["status_start"].notna().all()
    assert (df["receiving_watercourse"] == "River Dart").all() and df["lat"].notna().all()   # geometry, as before
    assert df["layer_edited_at"].isna().all() and asked == []
    monkeypatch.setattr(live, "fetch_all", lambda url, **kw: _sww_rows(stamped=False))
    df = live.fetch_live({"South West Water": "https://x/0"})
    assert df["last_updated"].isna().all() and asked == ["https://x/0"]
    assert (df["layer_edited_at"] == pd.Timestamp("2026-10-04 07:58", tz="UTC")).all()

    def fail(url):
        raise RuntimeError("ArcGIS request failed after 4 attempts")
    monkeypatch.setattr(live, "layer_edit_time", fail)
    assert live.fetch_live({"South West Water": "https://x/0"})["layer_edited_at"].isna().all()   # stale, never current


def test_layer_edit_time_reads_the_layers_data_edit_date(monkeypatch):
    from dipcast import arcgis
    sww = FIELDS["South West Water"]
    monkeypatch.setattr(arcgis, "_get", lambda client, url, params: {"name": sww["name"], "editingInfo": sww["editingInfo"]})
    assert arcgis.layer_edit_time("https://x/0") == sww["editingInfo"]["dataLastEditDate"]
    monkeypatch.setattr(arcgis, "_get", lambda client, url, params: {"name": "no editing info"})
    assert arcgis.layer_edit_time("https://x/0") is None


def _table():
    """An overflow table as build_overflows leaves it: one poll at T, carried rows, annual-return rows."""
    h = lambda x: T - pd.Timedelta(hours=x)
    rows = [  # site, company, status, last_updated, layer_edited_at, has_live
        ("F0", "Fresh", 0, h(0.4), pd.NaT, True), ("F1", "Fresh", 1, h(0.4), pd.NaT, True),
        ("F2", "Fresh", -1, h(0.4), pd.NaT, True), ("F3", "Fresh", -2, pd.NaT, pd.NaT, False),
        ("Z0", "Frozen", 0, h(30), pd.NaT, True), ("Z1", "Frozen", 1, h(9), pd.NaT, True),
        ("N0", "Unstamped", 0, pd.NaT, h(0.2), True), ("N1", "Unstamped", 0, pd.NaT, h(0.2), True),
        ("U0", "Unknown", 0, pd.NaT, pd.NaT, True),
        ("D0", "Down", -3, h(20), pd.NaT, True),
        ("W0", "Welsh", -2, pd.NaT, pd.NaT, False),
    ]
    df = pd.DataFrame(rows, columns=["site_id", "company", "status", "last_updated", "layer_edited_at", "has_live"])
    df["fetched_at"] = np.where(df["status"].isin([0, 1, -1]), T, pd.NaT)
    df.loc[df.company == "Down", "fetched_at"] = h(20)
    for c in ("last_updated", "layer_edited_at", "fetched_at"):
        df[c] = pd.to_datetime(df[c], utc=True)
    return df


def test_data_states():
    from dipcast.ingest.live import data_states
    df = _table()
    got = df[["site_id"]].join(data_states(df)).set_index("site_id")
    assert got["data_state"].to_dict() == {
        "F0": "live", "F1": "live", "F2": "offline", "F3": "offline",   # F3: missing from a feed that is up
        "Z0": "stale", "Z1": "stale",   # the freshest stamp in that feed is 9 h old
        "N0": "live", "N1": "live",     # no record stamps, but the layer was written 12 minutes before the poll
        "U0": "stale",                  # no time of any kind
        "D0": "offline", "W0": "no_feed"}
    t = got["feed_updated_at"]
    assert t["Z0"] == t["Z1"] == T - pd.Timedelta(hours=9) and t["N0"] == T - pd.Timedelta(hours=0.2)
    assert t["F2"] == T - pd.Timedelta(hours=0.4)                 # a monitor offline on a current feed
    assert t[["U0", "D0", "F3", "W0"]].isna().all()


def test_stale_agrees_with_the_coverage_rule():
    """A poll's row is stale in data_states exactly when coverage_rows counts it stale, except
    for a feed with no record stamps whose layer was written lately, which only data_states takes."""
    from dipcast.ingest.live import coverage_rows, data_states
    df = _table()
    poll = df[df["status"].isin([0, 1, -1])]
    cov = coverage_rows(poll).set_index("site_id")["n_stale"].astype(bool)
    st = df[["site_id"]].join(data_states(df)).set_index("site_id").loc[poll["site_id"], "data_state"]
    known = poll.set_index("site_id")["status"].isin([0, 1])
    differ = known & (cov != (st == "stale"))
    assert sorted(differ[differ].index) == ["N0", "N1"]


def test_a_table_without_poll_times_takes_states_from_status_alone():
    from dipcast.ingest.live import with_data_states
    df = pd.DataFrame({"site_id": list("abcde"), "company": ["X", "X", "X", "X", "W"], "status": [0, 1, -1, -3, -2],
                       "has_live": [True, True, True, True, False]})
    assert with_data_states(df)["data_state"].tolist() == ["live", "live", "offline", "offline", "no_feed"]
    already = df.assign(data_state="stale")
    assert with_data_states(already) is already


def test_right_now_counts_an_offline_or_stale_quiet_overflow_as_unknown():
    from dipcast.ingest.live import data_states
    from dipcast.model.forecast import live_counts
    df = _table()
    ov = df.join(data_states(df))
    contrib = pd.Series(0.0, index=ov.index)
    c = live_counts(ov, contrib)
    # Discharging F1 and Z1 (a stale feed's last word is a discharge); quiet and current F0, N0, N1.
    assert c["discharging_upstream"] == 2 and c["recent_upstream"] == 0
    assert c["monitored_upstream"] == 5          # before 4 Oct: every has_live row but D0, 8 of 11
    assert c["stale_upstream"] == 2 and c["feed_down_upstream"] == 1
    assert c["feed_stale"] == [{"company": "Frozen", "overflows": 1, "since": (T - pd.Timedelta(hours=9)).isoformat()},
                               {"company": "Unknown", "overflows": 1, "since": None}]
    # The page's dots: quiet = monitored - discharging - recent = 3; the other 6 are not reporting.
    assert c["monitored_upstream"] - c["discharging_upstream"] - c["recent_upstream"] == 3
    # An offline monitor whose last spill ended within the hours counted is "finished lately".
    contrib[ov.site_id == "F2"] = 0.3
    c2 = live_counts(ov, contrib)
    assert c2["recent_upstream"] == 1 and c2["monitored_upstream"] == 6
    # A table without states or poll times (a test's) is read from its status: every 0 is quiet.
    bare = ov.drop(columns=["data_state", "feed_updated_at", "fetched_at", "last_updated", "layer_edited_at"])
    assert live_counts(bare, contrib)["monitored_upstream"] == 8 and live_counts(bare, contrib)["stale_upstream"] == 0
    # One cached before 4 Oct keeps its poll times, so its states are worked out in full.
    assert live_counts(ov.drop(columns=["data_state", "feed_updated_at"]), contrib) == c2


def test_overflow_map_file_carries_the_state_and_a_stale_feeds_time(monkeypatch):
    from dipcast.ingest.live import data_states
    from dipcast.model import forecast
    df = _table()
    ov = df.join(data_states(df)).assign(lat=52.0, lon=-1.0, site_name="n", receiving_watercourse="r",
                                        latest_event_start=pd.NaT, latest_event_end=pd.NaT, lta_spills=3.0)
    monkeypatch.setattr(forecast, "_overflows", lambda: ov)
    props = {f["properties"]["site_id"]: f["properties"] for f in forecast.overflows_geojson()["features"]}
    assert props["Z0"]["data_state"] == "stale" and props["Z0"]["feed_updated_at"] == (T - pd.Timedelta(hours=9)).isoformat()
    assert props["U0"]["feed_updated_at"] is None
    assert props["F0"]["data_state"] == "live" and "feed_updated_at" not in props["F0"]
    assert props["W0"]["data_state"] == "no_feed" and props["W0"]["status"] == -2   # status kept as it was


@pytest.mark.parametrize("bad", [None, "x"])
def test_an_unreadable_status_is_offline(bad):
    """fetch_live reads a status it cannot parse as -1, the hub's Offline."""
    from dipcast.ingest import live
    rows = [{"Id": "A", "Company": "X", "Status": bad, "StatusStart": None, "LatestEventStart": None, "LatestEventEnd": None,
             "Latitude": 52.0, "Longitude": -1.0, "ReceivingWaterCourse": "r", "LastUpdated": MS("2026-10-04 07:50")}]
    with pytest.MonkeyPatch.context() as m:
        m.setattr(live, "fetch_all", lambda url, **kw: [dict(r) for r in rows])
        df = live.fetch_live({"X": "https://x/0"}).assign(has_live=True)
    assert df["status"].tolist() == [-1] and live.data_states(df)["data_state"].tolist() == ["offline"]
