"""Regression test for the 3 Oct 2026 13:05 BST build, where four spots failed with "forecast
failed: Index contains duplicate entries, cannot reshape". Severn Trent's and Yorkshire
Water's live layers are rewritten whole on every refresh; a rewrite between the two page
requests of one poll returned the second page from the new copy, in a new order, so it
repeated rows of the first page (410 Severn Trent, 29 Yorkshire) and left others out. A
repeated overflow upstream of a spot made spill_probabilities' pivot fail."""

import numpy as np
import pandas as pd

IDS = ["S1", "S2", "S3", "S4", "S5", "S6"]
REWRITTEN = ["S3", "S1", "S5", "S2", "S6", "S4"]   # the same overflows after the layer is rewritten
PAGE = 4
T0 = 1_791_000_000_000   # epoch ms, early on 3 Oct 2026


def _feature(site_id: str, i: int) -> dict:
    return {"attributes": {"Id": site_id, "Status": 0, "StatusStart": T0, "LatestEventStart": None,
                           "LatestEventEnd": None, "Latitude": 52.70 + 0.01 * i, "Longitude": -2.75,
                           "ReceivingWaterCourse": "RIVER SEVERN", "LastUpdated": T0},
            "geometry": {"x": -2.75, "y": 52.70 + 0.01 * i}}


def _torn_layer(monkeypatch):
    """A fake ArcGIS layer that is rewritten, in a new order, after the first page request."""
    from dipcast import arcgis
    calls = []

    def get(client, url, params):
        order = IDS if not calls else REWRITTEN
        calls.append(params["resultOffset"])
        off, n = params["resultOffset"], params["resultRecordCount"]
        feats = [_feature(s, IDS.index(s)) for s in order[off:off + n]]
        return {"features": feats, "exceededTransferLimit": off + n < len(order)}

    monkeypatch.setattr(arcgis, "_get", get)
    monkeypatch.setattr(arcgis.time, "sleep", lambda s: None)
    return calls


def test_a_layer_rewritten_between_pages_is_read_again(monkeypatch):
    from dipcast import arcgis
    _torn_layer(monkeypatch)
    torn = [r["Id"] for r in arcgis.fetch_all("https://x/0", page=PAGE)]
    assert sorted(torn) == ["S1", "S2", "S3", "S4", "S4", "S6"]   # S4 twice, S5 never: the 3 Oct failure
    calls = _torn_layer(monkeypatch)
    got = [r["Id"] for r in arcgis.fetch_all("https://x/0", page=PAGE, key="Id")]
    assert sorted(got) == IDS
    assert calls == [0, 4, 0, 4]   # one torn read, one clean one


def test_a_single_page_is_not_read_again(monkeypatch):
    from dipcast import arcgis
    calls = _torn_layer(monkeypatch)
    got = arcgis.fetch_all("https://x/0", page=10, key="Id")
    assert len(got) == 6 and calls == [0]


def _layer_listing_one_id_twice(monkeypatch, tear_first_read: bool = False):
    """A fake layer like Anglian Water's: A2 is listed twice on the first page, two records with
    different ObjectIds and every other field the same, in every read. With `tear_first_read`,
    the layer is also rewritten in a new order after the first page request (as _torn_layer)."""
    from dipcast import arcgis
    ids = ["A1", "A2", "A2", "A3", "A4", "A5"]
    rewritten = ["A2", "A3", "A2", "A5", "A1", "A4"]   # A2 still twice; A1 now on the second page
    calls = []

    def get(client, url, params):
        order = rewritten if tear_first_read and len(calls) >= 1 else ids
        calls.append(params["resultOffset"])
        off, n = params["resultOffset"], params["resultRecordCount"]
        feats = []
        for j, s in enumerate(order[off:off + n]):
            f = _feature(s, int(s[1:]))
            f["attributes"]["ObjectId"] = 900 + off + j
            feats.append(f)
        return {"features": feats, "exceededTransferLimit": off + n < len(order)}

    monkeypatch.setattr(arcgis, "_get", get)
    sleeps = []
    monkeypatch.setattr(arcgis.time, "sleep", sleeps.append)
    return calls, sleeps


def test_an_id_the_layer_lists_twice_on_one_page_is_not_read_again(monkeypatch):
    """Anglian Water's layer lists AWS00528 twice on its first page in every poll. Until 7 Oct 2026
    that read as a torn read: every build read Anglian three times and slept 6 s."""
    from dipcast import arcgis
    from dipcast.ingest import live
    calls, sleeps = _layer_listing_one_id_twice(monkeypatch)
    got = [r["Id"] for r in arcgis.fetch_all("https://x/0", page=PAGE, key="Id")]
    assert sorted(got) == ["A1", "A2", "A2", "A3", "A4", "A5"]   # what the layer holds, repeat included
    assert calls == [0, PAGE] and sleeps == []                   # one read, two pages, no pause

    # Downstream the repeat is one overflow.
    calls, sleeps = _layer_listing_one_id_twice(monkeypatch)
    real = arcgis.fetch_all
    monkeypatch.setattr(live, "fetch_all", lambda url, **kw: real(url, page=PAGE, key=kw["key"]))
    snap = live.fetch_live({"Anglian Water": "https://x/0"}, expected={"Anglian Water": 5.0})
    assert sorted(snap["site_id"]) == ["A1", "A2", "A3", "A4", "A5"]
    assert calls == [0, PAGE] and sleeps == []


def test_a_torn_read_of_a_layer_that_lists_an_id_twice_is_still_read_again(monkeypatch):
    """The same layer, rewritten between the two pages of the first read: A1 comes back on both
    pages and A5 on neither. That read is torn and is read again; the second read is clean."""
    from dipcast import arcgis
    calls, sleeps = _layer_listing_one_id_twice(monkeypatch, tear_first_read=True)
    got = [r["Id"] for r in arcgis.fetch_all("https://x/0", page=PAGE, key="Id")]
    assert calls == [0, PAGE, 0, PAGE] and len(sleeps) == 1
    assert sorted(got) == ["A1", "A2", "A2", "A3", "A4", "A5"]


def test_keys_on_two_pages():
    from dipcast.arcgis import _keys_on_two_pages
    page = lambda *ids: [{"Id": i} for i in ids]  # noqa: E731
    assert _keys_on_two_pages([page("a", "b", "b"), page("c")], "Id") == 0
    assert _keys_on_two_pages([page("a", "b"), page("b", "c"), page("a")], "Id") == 2


def test_live_snapshot_has_one_row_per_overflow(monkeypatch):
    """A feed that lists an overflow twice (Anglian Water's AWS00528 does) keeps the newest row."""
    from dipcast.ingest import live
    rows = [dict(_feature(s, i)["attributes"]) for i, s in enumerate(["A1", "A2", "A1"])]
    rows[2]["Status"], rows[2]["LastUpdated"] = 1, T0 + 60_000
    monkeypatch.setattr(live, "fetch_all", lambda url, **kw: [dict(r) for r in rows])
    df = live.fetch_live({"Anglian Water": "https://x/0"})
    assert sorted(df["site_id"]) == ["A1", "A2"]
    assert df.set_index("site_id").loc["A1", "status"] == 1


def _rain(cells):
    t = pd.date_range("2026-09-25", "2026-10-12", freq="h", tz="UTC", inclusive="left")
    return pd.concat([pd.DataFrame({"cell_lat": cl, "cell_lon": cn, "time": t, "precip_mm": 0.5})
                      for cl, cn in cells], ignore_index=True)


def _overflows(live_rows: pd.DataFrame) -> pd.DataFrame:
    return live_rows.assign(lta_spills=20.0, spill_hours=100.0, edm_operational_pct=95.0)


def test_spill_probabilities_with_a_torn_snapshot(monkeypatch):
    """The torn snapshot that failed the pivot now gives one row of probabilities per row, and the
    snapshot fetch_live now gives has one row per overflow."""
    from dipcast import arcgis
    from dipcast.ingest import live
    from dipcast.model import forecast
    monkeypatch.setattr(forecast, "fetch_forecast", _rain)
    days = pd.date_range("2026-10-01", periods=5, freq="D", tz=forecast.LOCAL_TZ)
    real = arcgis.fetch_all

    # fetch_live as it was before the fix: no key for fetch_all, no one_row_per_site.
    _torn_layer(monkeypatch)
    with monkeypatch.context() as m:
        m.setattr(live, "fetch_all", lambda url, **kw: real(url, page=PAGE))
        m.setattr(live, "one_row_per_site", lambda df: df)
        torn = live.fetch_live({"Severn Trent Water": "https://x/0"})
    assert sorted(torn["site_id"]) == ["S1", "S2", "S3", "S4", "S4", "S6"]
    # Until spill_probabilities computed a repeated id once, this raised "Index contains duplicate entries".
    p, ok = forecast.spill_probabilities(_overflows(torn), days, None)
    s4 = np.flatnonzero(torn["site_id"].to_numpy() == "S4")
    assert p.shape == (6, 5) and ok.all() and np.isfinite(p).all() and (p[s4[0]] == p[s4[1]]).all()

    _torn_layer(monkeypatch)
    monkeypatch.setattr(live, "fetch_all", lambda url, **kw: real(url, page=PAGE, key=kw["key"]))
    snap = live.fetch_live({"Severn Trent Water": "https://x/0"})
    assert sorted(snap["site_id"]) == IDS
    p, ok = forecast.spill_probabilities(_overflows(snap), days, None)
    assert p.shape == (6, 5) and ok.all() and np.isfinite(p).all()
