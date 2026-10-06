"""Regression tests for the 6 Oct 2026 13:48 UTC build. Its read of Yorkshire Water's live layer
returned 1,179 rows where the feed holds 2,179: the layer is rewritten whole on each refresh, and
the read caught it part way. Each overflow missing from that read went into the overflow table
with status -2, "not in the company's live feed", and the Right now tile said "9 of 15 report
live" at Wharfe at Cromwheel, Ilkley. All six missing there (Addingham's two overflows among them)
were in the feed before and after, and had been scored on every day from 29 Sep to 5 Oct.

A short read is now read again; whatever is still missing keeps its last snapshot, marked feed
down (-3), as for a feed that does not answer. It is never listed as outside the feed."""

import numpy as np
import pandas as pd

T0 = 1_791_300_000_000   # epoch ms, 6 Oct 2026
FULL = [f"YWS{i:05d}" for i in range(1, 11)]   # the feed: 10 overflows
CROMWHEEL = FULL[:6]                            # those upstream of the spot
KEPT = FULL[6:]                                 # the 4 a short read returns


def _row(site_id: str, status: int = 0) -> dict:
    return {"Id": site_id, "Status": status, "StatusStart": T0, "LatestEventStart": T0 - 3_600_000,
            "LatestEventEnd": T0, "Latitude": 53.93, "Longitude": -1.86, "ReceivingWaterCourse": "River Wharfe",
            "LastUpdated": T0}


def _feed(monkeypatch, reads):
    """A fake feed that answers each read with the next list of ids in `reads` (the last one repeats)."""
    from dipcast.ingest import live
    calls = []

    def fetch_all(url, **kw):
        ids = reads[min(len(calls), len(reads) - 1)]
        calls.append(len(ids))
        return [_row(s) for s in ids]

    monkeypatch.setattr(live, "fetch_all", fetch_all)
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    return calls


def _state(tmp_path, monkeypatch):
    from dipcast import config
    monkeypatch.setattr(config, "STATE", tmp_path)
    monkeypatch.setattr(config, "PROCESSED", tmp_path)
    monkeypatch.setattr(config, "LIVE_FEEDS", {"Yorkshire Water": "https://x/0"})
    return config


def _poll(tmp_path, monkeypatch, reads, when):
    """One poll as refresh_all makes it: usual sizes from the poll log, fetch, save."""
    from dipcast.ingest import live
    calls = _feed(monkeypatch, reads)
    expected = live.expected_rows()
    df = live.fetch_live(expected=expected).assign(fetched_at=pd.Timestamp(when, tz="UTC"))
    live.save_live(df, expected)
    return calls, pd.read_parquet(tmp_path / "live_latest.parquet")


def _overflow_table(latest: pd.DataFrame) -> pd.DataFrame:
    """The live part of overflows.build_overflows: an outer join on site_id with the annual
    returns, which list every overflow, then has_live, status and the data states."""
    from dipcast.ingest.live import data_states
    ar = pd.DataFrame({"site_id": FULL, "ar_company": "Yorkshire Water"})
    df = latest.merge(ar, on="site_id", how="outer")
    df["company"] = df["company"].fillna(df["ar_company"])
    df["has_live"] = df["status"].notna()
    df["status"] = df["status"].fillna(-2).astype(int)
    return pd.concat([df, data_states(df)], axis=1).set_index("site_id")


def test_a_short_read_is_read_again(monkeypatch):
    from dipcast.ingest import live
    calls = _feed(monkeypatch, [KEPT, FULL])
    df = live.fetch_live({"Yorkshire Water": "https://x/0"}, expected={"Yorkshire Water": 10.0})
    assert sorted(df["site_id"]) == FULL and calls == [4, 10]
    # Without the usual size (a caller that does not pass it) each feed is read once, as before.
    calls = _feed(monkeypatch, [KEPT, FULL])
    assert sorted(live.fetch_live({"Yorkshire Water": "https://x/0"})["site_id"]) == KEPT and calls == [4]
    # A full read, or one a little smaller than usual, is not read again.
    calls = _feed(monkeypatch, [FULL[:9]])
    live.fetch_live({"Yorkshire Water": "https://x/0"}, expected={"Yorkshire Water": 10.0})
    assert calls == [9]
    # Still short after every read: the longest read is kept.
    calls = _feed(monkeypatch, [KEPT, FULL[5:], KEPT])
    df = live.fetch_live({"Yorkshire Water": "https://x/0"}, expected={"Yorkshire Water": 10.0})
    assert len(df) == 5 and calls == [4, 5, 4]


def test_overflows_a_short_read_missed_are_not_called_outside_the_feed(tmp_path, monkeypatch):
    from dipcast.ingest import live
    from dipcast.model.forecast import live_counts
    _state(tmp_path, monkeypatch)
    for h in range(3):
        _poll(tmp_path, monkeypatch, [FULL], f"2026-10-06 0{h}:00")
    # The 13:48 case: every read is short.
    calls, latest = _poll(tmp_path, monkeypatch, [KEPT], "2026-10-06 13:48")
    assert calls == [4, 4, 4]
    ov = _overflow_table(latest)
    # Before the fix these six had status -2, has_live False and data state offline, which the
    # page words as "not in the company's live feed".
    assert (ov["status"] != -2).all() and ov["has_live"].all()
    assert (ov.loc[CROMWHEEL, "status"] == live.FEED_DOWN).all()
    assert (ov.loc[CROMWHEEL, "feed_down_since"] == pd.Timestamp("2026-10-06 02:00", tz="UTC")).all()
    assert (ov.loc[KEPT, "data_state"] == "live").all()
    # The Right now tile names the feed as down for those six, with when it last answered.
    c = live_counts(ov.loc[CROMWHEEL].reset_index(), pd.Series(np.zeros(6)))
    assert c["monitored_upstream"] == 0 and c["feed_down_upstream"] == 6
    assert c["feed_down"] == [{"company": "Yorkshire Water", "overflows": 6, "since": "2026-10-06T02:00:00+00:00"}]
    # Only what was read reaches the coverage file and the poll log, so the scorer cannot take a
    # missing overflow's day as dry.
    cov = pd.read_parquet(tmp_path / live.COVERAGE_FILE)
    assert cov.loc[cov["site_id"].isin(CROMWHEEL), "n_known"].tolist() == [3] * 6
    assert pd.read_parquet(tmp_path / live.POLL_LOG_FILE)["n_rows"].tolist() == [10, 10, 10, 4]
    # The next full read replaces the carried rows.
    _, latest = _poll(tmp_path, monkeypatch, [FULL], "2026-10-06 14:18")
    assert (latest["status"] == 0).all() and latest["feed_down_since"].isna().all()


def test_a_feed_that_really_shrinks_stops_being_carried(tmp_path, monkeypatch):
    """The usual size is a median of recent polls, so overflows a company drops from its feed
    are carried as feed down for a few polls, not for ever."""
    from dipcast.ingest import live
    _state(tmp_path, monkeypatch)
    for h in range(live.EXPECTED_FROM_POLLS):
        _poll(tmp_path, monkeypatch, [FULL], f"2026-10-05 {h:02d}:00")
    carried = []
    for h in range(live.EXPECTED_FROM_POLLS):
        _, latest = _poll(tmp_path, monkeypatch, [KEPT], f"2026-10-06 {h:02d}:00")
        carried.append(int((latest["status"] == live.FEED_DOWN).sum()))
    assert carried[0] == 6 and carried[-1] == 0
    assert carried == sorted(carried, reverse=True)


def test_expected_rows_ignores_polls_with_no_rows_and_one_short_read():
    from dipcast.ingest.live import expected_rows, is_short
    t = pd.date_range("2026-10-06", periods=6, freq="30min", tz="UTC")
    pl = pd.DataFrame({"fetched_at": t, "company": "Yorkshire Water", "n_rows": [2179, 2179, 1179, 0, 2179, 2179]})
    assert expected_rows(pl) == {"Yorkshire Water": 2179.0}
    assert is_short(1179, "Yorkshire Water", expected_rows(pl))
    assert not is_short(2100, "Yorkshire Water", expected_rows(pl))
    assert not is_short(0, "Yorkshire Water", expected_rows(pl))   # no rows is a feed down, not a short read
    assert not is_short(5, "Other", expected_rows(pl)) and expected_rows(pl.iloc[0:0]) == {}


def test_build_health_warns_on_a_short_read(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_site as bs
    good = {"name": "ok", "days": [{"data_status": "ok"}]}
    t = pd.date_range("2026-10-06 10:00", periods=4, freq="h", tz="UTC")
    pl = lambda last: pd.DataFrame({"fetched_at": t, "company": "Yorkshire Water", "n_rows": [2179, 2179, 2179, last],
                                    "n_known": 0, "feed_age_h": 0.1})
    assert bs.build_health([good] * 5, None, pl(2179))["warnings"] == []
    h = bs.build_health([good] * 5, None, pl(1179))
    assert h["live_feeds"]["short"] == {"Yorkshire Water": {"rows": 1179, "usual": 2179.0}}
    assert len(h["warnings"]) == 1 and "returned 1179 rows" in h["warnings"][0] and "usually has 2179" in h["warnings"][0]
