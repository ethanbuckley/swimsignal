"""Tests for Dŵr Cymru's live adapter (ingest.dwr_cymru, Wales plan task W5): the status mapping,
"Under Investigation" as status unknown, UK local times to UTC, the layer's last edit as the feed
time, emergency overflows, and the setting that keeps it off. The layer has no licence, so the rows
are SYNTHETIC (fixtures/dwr_cymru_synthetic.json): real field names and formats, invented values."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "dwr_cymru_synthetic.json").read_text())
FETCHED = pd.Timestamp(FIXTURE["fetched_at"])
EDITED = pd.Timestamp(FIXTURE["dataLastEditDate"], unit="ms", tz="UTC")
ROOT = Path(__file__).resolve().parents[1]


def gid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def _snap(fetched=FETCHED, edited=EDITED, rows=None):
    from dipcast.ingest.dwr_cymru import parse
    return parse(rows or FIXTURE["rows"], fetched, edited).set_index("site_id")


def _state(tmp_path, monkeypatch, on: bool):
    from dipcast import config
    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "PROCESSED", tmp_path)
    monkeypatch.setattr(config, "DWR_CYMRU", on)
    return config


def test_the_fixture_is_synthetic_and_uses_the_layers_field_names():
    assert FIXTURE["note"].startswith("SYNTHETIC")
    for r in FIXTURE["rows"]:
        assert r["asset_name"].startswith("SYNTHETIC")
        assert set(r) - {"_x", "_y"} == set(FIXTURE["fields"])


def test_status_mapping():
    s = _snap()
    assert s.loc[gid(1), "status"] == 1                                        # Overflow Operating
    assert s.loc[gid(3), "status"] == 0                                        # Not Operating (Has in the last 24 hours)
    assert s.loc[gid(4), "status"] == 0                                        # Overflow Not Operating
    assert s.loc[gid(3), "status_text"] == "Overflow Not Operating (Has in the last 24 hours)"
    assert s.loc[s["status"] == 1, "latest_event_end"].isna().all()
    assert s.loc[gid(3), "latest_event_end"] == pd.Timestamp("2026-10-04 02:30", tz="UTC")   # the last stop time, kept
    assert (s["company"] == "Dwr Cymru Welsh Water").all()
    assert s.index.str.fullmatch(r"[0-9a-f-]{36}").all()                       # the GlobalID, as wales_annual keeps it
    assert s.loc[gid(1), ["easting", "northing"]].tolist() == [300000, 300000]  # outlet in BNG, for matching


def test_under_investigation_is_status_unknown_with_its_last_discharge_kept():
    s = _snap()
    ui = s[s["under_investigation"]]
    assert sorted(ui.index) == [gid(6), gid(7)]
    assert (ui["status"] == -1).all() and (ui["data_state"] == "stale").all()   # never "not discharging"
    assert ui.loc[gid(6), "latest_event_start"] == pd.Timestamp("2026-10-03 05:55", tz="UTC")
    assert ui.loc[gid(6), "latest_event_end"] == pd.Timestamp("2026-10-03 06:25", tz="UTC")
    assert pd.isna(ui.loc[gid(7), "latest_event_end"])                          # open, and still not "discharging"


def test_a_status_it_does_not_know_reads_as_offline():
    s = _snap()
    assert s.loc[gid(11), ["status", "data_state", "under_investigation"]].tolist() == [-1, "offline", False]


def test_times_are_uk_local_turned_to_utc():
    s = _snap()
    assert s.loc[gid(1), "latest_event_start"] == pd.Timestamp("2026-10-04 09:05", tz="UTC")    # BST: one hour back
    assert s.loc[gid(8), "latest_event_start"] == pd.Timestamp("2026-01-11 21:30", tz="UTC")    # GMT: the same
    # 01:30 to 01:45 on 26 Oct 2025 happened twice. The start is read as the first (BST), the stop
    # as the second (GMT), so the discharge is never shortened.
    assert s.loc[gid(9), "latest_event_start"] == pd.Timestamp("2025-10-26 00:30", tz="UTC")
    assert s.loc[gid(9), "latest_event_end"] == pd.Timestamp("2025-10-26 01:45", tz="UTC")
    # 01:30 on 29 Mar 2026 never happened: moved to 02:00 BST, 01:00 UTC.
    assert s.loc[gid(10), "latest_event_start"] == pd.Timestamp("2026-03-29 01:00", tz="UTC")
    assert s.loc[gid(10), "latest_event_end"] == pd.Timestamp("2026-03-29 02:00", tz="UTC")
    assert s.loc[gid(5), ["latest_event_start", "latest_event_end"]].isna().all()


def test_a_time_with_its_own_zone_is_read_with_it():
    from dipcast.ingest.dwr_cymru import local_to_utc
    got = local_to_utc(pd.Series(["2026-10-04T10:15:00Z", "2026-10-04T10:15:00+01:00", "2026-10-04T10:15:00", None]),
                       stop=False)
    assert got.tolist()[:3] == [pd.Timestamp("2026-10-04 10:15", tz="UTC"), pd.Timestamp("2026-10-04 09:15", tz="UTC"),
                                pd.Timestamp("2026-10-04 09:15", tz="UTC")]
    assert pd.isna(got.iloc[3])


def test_the_feed_time_is_the_layers_last_edit_and_sets_the_data_state():
    s = _snap()
    assert (s["feed_updated_at"].dropna() == EDITED).all()
    assert s.loc[gid(1), "data_state"] == "live" and s.loc[gid(4), "data_state"] == "live"
    # The row's own EditDate is kept, not used: gid 4 was last edited days before and is still live.
    assert s.loc[gid(4), "row_edited_at"] < FETCHED - pd.Timedelta(days=2)
    # A layer not written for over 6 hours, or one that does not say, makes every status stale.
    old = _snap(fetched=EDITED + pd.Timedelta(hours=7))
    assert set(old.loc[old["status"] >= 0, "data_state"]) == {"stale"}
    unknown = _snap(edited=None)
    assert set(unknown.loc[unknown["status"] >= 0, "data_state"]) == {"stale"}


def test_emergency_overflows_are_marked():
    s = _snap()
    assert sorted(s.index[s["emergency"]]) == [gid(2), gid(8)]


def test_history_keeps_one_row_per_discharge_and_fills_in_the_stop(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch, on=True)
    from dipcast.forecast_log import observed_spill_days
    from dipcast.ingest.dwr_cymru import HISTORY_FILE, parse, save
    first = save(parse(FIXTURE["rows"], FETCHED, EDITED))
    assert len(first) == 10                                     # every row with a start; gid 5 has none
    rows = [dict(r) for r in FIXTURE["rows"]]
    rows[0].update(status="Overflow Not Operating (Has in the last 24 hours)", stop_date_time_discharge="2026-10-04T18:00:00")
    second = save(parse(rows, FETCHED + pd.Timedelta(hours=3), EDITED + pd.Timedelta(hours=3)))
    assert len(second) == len(first)
    h = pd.read_parquet(tmp_path / HISTORY_FILE).set_index("site_id")
    assert h.loc[gid(1), "status"] == 0 and h.loc[gid(1), "latest_event_end"] == pd.Timestamp("2026-10-04 17:00", tz="UTC")
    assert h.loc[gid(1), "first_seen"] == FETCHED
    assert h.loc[gid(7), "status"] == -1 and h.loc[gid(7), "under_investigation"]
    days = observed_spill_days(h.reset_index())
    assert gid(1) in set(days["site_id"])


def test_off_by_default_nothing_is_fetched_or_written(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch, on=False)
    from dipcast import forecast_log, jobs, overflows
    from dipcast.ingest import dwr_cymru, live
    asked = []
    monkeypatch.setattr(dwr_cymru, "fetch_all", lambda *a, **k: asked.append(a) or FIXTURE["rows"])
    monkeypatch.setattr(dwr_cymru, "layer_edit_time", lambda url: asked.append(url) or FIXTURE["dataLastEditDate"])
    monkeypatch.setattr(live, "fetch_live", lambda: pd.DataFrame({"status": [0]}))
    monkeypatch.setattr(live, "save_live", lambda df: None)
    monkeypatch.setattr(overflows, "build_overflows", lambda net: pd.DataFrame({"site_id": ["A"]}))
    monkeypatch.setattr(forecast_log, "verify_live", lambda: {"n_scored": 0})
    jobs.refresh_all(net=object())
    assert dwr_cymru.poll()["ok"] is False                      # the module checks the setting too
    assert asked == [] and list(tmp_path.iterdir()) == []
    # On: one read of the rows and one of the layer's edit time, and only its own two files.
    from dipcast import config
    monkeypatch.setattr(config, "DWR_CYMRU", True)
    jobs.refresh_all(net=object())
    assert len(asked) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([dwr_cymru.LATEST_FILE, dwr_cymru.HISTORY_FILE])


def test_a_failed_read_never_raises(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch, on=True)
    from dipcast.ingest import dwr_cymru

    def down(*a, **k):
        raise RuntimeError("ArcGIS request failed after 4 attempts")
    monkeypatch.setattr(dwr_cymru, "fetch_all", down)
    assert dwr_cymru.poll() == {"ok": False, "error": "ArcGIS request failed after 4 attempts"}
    assert list(tmp_path.iterdir()) == []


def test_the_setting_is_off_unless_set_to_1():
    code = "from dipcast import config; print(config.DWR_CYMRU)"
    env = {k: v for k, v in os.environ.items() if k != "DIPCAST_DWR_CYMRU"}
    run = lambda e: subprocess.run([sys.executable, "-c", code], env=e, capture_output=True, text=True, check=True).stdout.strip()
    assert run(env) == "False"
    assert run({**env, "DIPCAST_DWR_CYMRU": "true"}) == "False"
    assert run({**env, "DIPCAST_DWR_CYMRU": "1"}) == "True"


@pytest.mark.parametrize("name", ["dwr_cymru_latest.parquet", "dwr_cymru_history.parquet"])
def test_its_files_are_not_published_to_the_state_release(name):
    """site.yml uploads a fixed list of state files to the public `state` release. Dŵr Cymru's rows
    have no licence, so its files must never be on that list."""
    from dipcast.ingest import dwr_cymru
    assert name in (dwr_cymru.LATEST_FILE, dwr_cymru.HISTORY_FILE)
    site = (ROOT / ".github" / "workflows" / "site.yml").read_text()
    assert "dwr_cymru" not in site and name not in site
    assert "DIPCAST_DWR_CYMRU" not in site
