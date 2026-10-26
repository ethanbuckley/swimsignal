"""scripts/river_rises_coverage.py: the capped EA client, coverage and gap counts, the arrival lag of
a rise between two gauges, upstream gauges on the network, and the evaluation's window builder (no
reading after the cut). Synthetic data only: nothing here reaches the network."""

import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import river_rises_coverage as rr
from dipcast.ingest import flows

EA = "https://environment.data.gov.uk"


def _client(tmp_path, handler, **kw) -> tuple[rr.CappedClient, list[str]]:
    asked = []

    def h(req: httpx.Request) -> httpx.Response:
        asked.append(str(req.url))
        return handler(req)

    http = httpx.Client(transport=httpx.MockTransport(h), follow_redirects=False)
    kw.setdefault("sleep", lambda s: None)
    return rr.CappedClient(tmp_path / "cache", fetch=kw.pop("fetch", True), http=http, **kw), asked


# ------------------------------------------------------------------ the capped client
def test_cap_stops_the_run_and_cache_hits_do_not_count(tmp_path):
    c, asked = _client(tmp_path, lambda r: httpx.Response(200, json={"items": []}), cap=2)
    c.get(f"{EA}/flood-monitoring/id/stations", {"a": 1})
    c.get(f"{EA}/flood-monitoring/id/stations", {"a": 1})   # cached: no request
    c.get(f"{EA}/flood-monitoring/id/stations", {"a": 2})
    with pytest.raises(rr.Stop, match="cap"):
        c.get(f"{EA}/flood-monitoring/id/stations", {"a": 3})
    assert len(asked) == 2 and c.n == 2
    with pytest.raises(rr.Stop):   # stopped for good, even under the cap
        c.cap = 10
        c.get(f"{EA}/flood-monitoring/id/stations", {"a": 4})
    assert len(asked) == 2
    assert len((tmp_path / "cache" / "requests.log").read_text().splitlines()) == 2


@pytest.mark.parametrize("status", [429, 403, 500, 503, 301])
def test_refusal_server_error_or_redirect_stops_everything(tmp_path, status):
    c, asked = _client(tmp_path, lambda r: httpx.Response(status, headers={"Location": f"{EA}/x"}))
    with pytest.raises(rr.Stop, match=str(status)):
        c.get(f"{EA}/hydrology/id/stations.json")
    with pytest.raises(rr.Stop, match="stopped earlier"):
        c.get(f"{EA}/hydrology/id/measures/m/readings.csv")
    assert len(asked) == 1   # the second was never sent, and the redirect never followed


def test_a_transport_error_stops_the_run(tmp_path):
    def boom(req):
        raise httpx.ConnectTimeout("slow", request=req)
    c, _ = _client(tmp_path, boom)
    with pytest.raises(rr.Stop):
        c.get(f"{EA}/flood-monitoring/id/stations")
    assert c.stopped


def test_404_is_cached_as_404_and_not_a_stop(tmp_path):
    c, asked = _client(tmp_path, lambda r: httpx.Response(404))
    assert c.get(f"{EA}/hydrology/id/measures/x/readings.json") == (404, "")
    assert c.get(f"{EA}/hydrology/id/measures/x/readings.json") == (404, "")
    assert len(asked) == 1 and c.stopped is None


def test_only_ea_https_and_nothing_without_fetch(tmp_path):
    c, asked = _client(tmp_path, lambda r: httpx.Response(200, json={}))
    for url in ("https://api.open-meteo.com/v1/forecast", "http://environment.data.gov.uk/flood-monitoring/id/stations"):
        with pytest.raises(rr.Stop, match="allowed"):
            c.get(url)
    off, asked_off = _client(tmp_path / "b", lambda r: httpx.Response(200, json={}), fetch=False)
    with pytest.raises(rr.Stop, match="not cached"):
        off.get(f"{EA}/flood-monitoring/id/stations")
    assert asked == [] and asked_off == []


def test_pause_between_requests(tmp_path):
    waits = []
    c, _ = _client(tmp_path, lambda r: httpx.Response(200, json={}), sleep=waits.append)
    for i in range(3):
        c.get(f"{EA}/flood-monitoring/id/stations", {"i": i})
    assert waits == [rr.PAUSE_S, rr.PAUSE_S] and rr.PAUSE_S >= 1.0 and rr.MAX_REQUESTS <= 300


def test_station_pick_goes_through_the_capped_client(tmp_path):
    def handler(req):
        if req.url.path == "/flood-monitoring/id/stations":
            return httpx.Response(200, json={"items": [{
                "stationReference": "G1", "label": "Gauge", "riverName": "River Wharfe", "lat": 54.0, "long": -1.9,
                "stageScale": f"{EA}/flood-monitoring/id/stations/G1/stageScale",
                "measures": [{"@id": f"{EA}/flood-monitoring/id/measures/G1-level-stage-i-15_min-m",
                              "parameter": "level", "qualifier": "Stage", "unitName": "m"}]}]})
        return httpx.Response(200, json={"items": {"typicalRangeLow": 0.2, "typicalRangeHigh": 1.4}})
    c, asked = _client(tmp_path, handler, cap=1)
    with rr.routed(c), pytest.raises(rr.Stop, match="cap"):   # the scale is the second request
        flows.station_pick(54.0, -1.9, 15, "River Wharfe")
    assert len(asked) == 1
    c.cap, c.stopped = 2, None
    with rr.routed(c):
        p = flows.station_pick(54.0, -1.9, 15, "River Wharfe")
    assert p["ref"] == "G1" and p["typical_high"] == 1.4 and len(asked) == 2
    assert flows.httpx.get is httpx.get   # put back after the block


# ------------------------------------------------------------------ coverage and gaps
def _grid(start="2026-01-01", n=96 * 4):
    return pd.date_range(start, periods=n, freq="15min", tz="UTC")


def test_gap_runs_and_coverage():
    assert rr.gap_runs(np.array([1, 0, 0, 1, 1, 0, 0, 0, 0, 0], bool)) == [2, 5]
    assert rr.gap_runs(np.array([], bool)) == []
    s = pd.Series(1.0, index=_grid(n=96))   # one day
    s.iloc[10:12] = np.nan      # 30 minutes: not a counted gap
    s.iloc[40:48] = np.nan      # 2 hours
    s.iloc[90:] = np.nan        # 1.5 hours at the end
    c = rr.coverage(s)
    assert c["slots"] == 96 and c["share"] == round(80 / 96, 4)
    assert c["gaps_1h"] == 2 and c["longest_gap_h"] == 2.0
    assert c["first"].startswith("2026-01-01T00:00") and c["last"].startswith("2026-01-01T22:15")


def test_to_grid_drops_bad_quality_and_snaps_to_slots():
    df = pd.DataFrame({"dateTime": ["2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z", "2026-01-01T00:31:00Z", "bad"],
                       "value": ["1.0", "2.0", "3.0", "4"], "quality": ["Good", "Suspect", "Unchecked", "Good"]})
    s = rr.to_grid(df, "2026-01-01", "2026-01-01T01:00")
    assert len(s) == 4 and s.iloc[0] == 1.0 and np.isnan(s.iloc[1]) and s.iloc[2] == 3.0 and np.isnan(s.iloc[3])


# ------------------------------------------------------------------ lags on synthetic hydrographs
def _hydrograph(idx, peak, base=0.3, height=1.0, width_h=6.0):
    t = (idx - pd.Timestamp(peak, tz="UTC")) / pd.Timedelta(hours=1)
    return pd.Series(base + height * np.exp(-0.5 * (np.asarray(t) / width_h) ** 2), index=idx)


def test_lag_of_a_rise_that_arrives_five_hours_later():
    idx = _grid(n=96 * 6)
    up = _hydrograph(idx, "2026-01-03T06:00", height=1.5)
    down = _hydrograph(idx, "2026-01-03T11:00", height=1.0)
    onsets = rr.rise_onsets(down, rng=1.0)
    assert len(onsets) == 1 and onsets[0] < pd.Timestamp("2026-01-03T11:00", tz="UTC")
    ev = rr.event_lag(down, up, onsets[0], up_rng=rr.empirical_range(up))
    assert ev["why"] == "" and ev["lag_h"] == pytest.approx(5.0)
    assert 4.0 <= ev["onset_lead_h"] <= 7.0   # its own range and size differ, so its rule trips a little apart
    assert rr.xcorr_lag(down, up, onsets[0]) == pytest.approx(5.0, abs=0.25)


def test_no_lag_when_upstream_did_not_rise_or_has_no_readings():
    idx = _grid(n=96 * 6)
    down = _hydrograph(idx, "2026-01-03T11:00")
    flat = pd.Series(0.3, index=idx) + np.linspace(0, 0.001, len(idx))
    onset = rr.rise_onsets(down, rng=1.0)[0]
    assert rr.event_lag(down, flat, onset, up_rng=1.0)["why"] == "no upstream rise"
    gone = flat.copy()
    gone.loc["2026-01-02":"2026-01-04"] = np.nan
    assert rr.event_lag(down, gone, onset, up_rng=1.0)["why"] == "upstream readings missing"


def test_onsets_are_separated_and_need_the_sites_rise():
    idx = _grid(n=96 * 8)
    two = _hydrograph(idx, "2026-01-02T12:00") + _hydrograph(idx, "2026-01-03T00:00") - 0.3   # 12 h apart: one event
    two += _hydrograph(idx, "2026-01-06T12:00") - 0.3                                       # 4.5 days later: another
    assert len(rr.rise_onsets(two, rng=1.0)) == 2
    assert rr.rise_onsets(two, rng=10.0) == []   # a rise of 1 m is not a fifth of a 10 m range
    assert rr.rise_onsets(two, rng=0) == []


def test_negative_lag_is_reported_not_hidden():
    idx = _grid(n=96 * 6)
    down = _hydrograph(idx, "2026-01-03T11:00")
    up = _hydrograph(idx, "2026-01-03T14:00", height=1.5)   # "upstream" peaks 3 h after
    ev = rr.event_lag(down, up, rr.rise_onsets(down, 1.0)[0], up_rng=rr.empirical_range(up))
    assert ev["lag_h"] == pytest.approx(-3.0)


# ------------------------------------------------------------------ upstream along the network
class _Net:
    """Two links in a line, a -> b -> c, 1,000 m each, and a tributary t -> b, 500 m."""

    def __init__(self):
        self.links = pd.DataFrame({"start_node": ["a", "b", "t"], "end_node": ["b", "c", "b"],
                                   "length": [1000.0, 1000.0, 500.0]}, index=["L1", "L2", "LT"])

    def upstream_edges(self, node, cap):
        return {"L1": 0.0, "LT": 0.0} if node == "b" else {}


def test_upstream_of():
    net = _Net()
    cands = {"U1": ("L1", 0.5), "UT": ("LT", 0.0), "SAME": ("L2", 0.1), "DOWN": ("L2", 0.9)}
    got = rr.upstream_of(net, ("L2", 0.5), cands, cap_m=10_000)
    assert got == {"U1": pytest.approx(1000.0), "UT": pytest.approx(1000.0), "SAME": pytest.approx(400.0)}
    assert "U1" not in rr.upstream_of(net, ("L2", 0.5), cands, cap_m=900)


# ------------------------------------------------------------------ no leakage in the window builder
def test_issue_rows_reads_nothing_after_the_cut():
    idx = _grid(n=96 * 3)
    down = _hydrograph(idx, "2026-01-02T12:00")
    up = _hydrograph(idx, "2026-01-02T07:00", height=1.5)
    t = pd.Timestamp("2026-01-02T06:00", tz="UTC")
    base = rr.issue_rows({"down": down, "up": up}, "down", [t], rng=1.0, horizon_h=6, delay_h={"down": 0.0, "up": 1.0})
    # change everything at or after each gauge's cut: no input may move
    d2, u2 = down.copy(), up.copy()
    d2[d2.index > t] = 99.0
    u2[u2.index > t - pd.Timedelta(hours=1)] = -99.0
    moved = rr.issue_rows({"down": d2, "up": u2}, "down", [t], rng=1.0, horizon_h=6, delay_h={"down": 0.0, "up": 1.0})
    inputs = [c for c in base.columns if c.endswith(("_level", "_rise"))]
    pd.testing.assert_frame_equal(base[inputs], moved[inputs])
    assert base.at[0, "up_level"] == pytest.approx(float(up.loc[t - pd.Timedelta(hours=1)]))
    assert base.at[0, "rises"] == 1          # the peak 6 h later is the label's, and only the label's
    assert moved.at[0, "rises"] == 1


def test_issue_rows_label_needs_both_sides_and_horizon():
    idx = _grid(n=96 * 3)
    down = _hydrograph(idx, "2026-01-02T12:00")
    t = pd.Timestamp("2026-01-02T00:00", tz="UTC")
    assert rr.issue_rows({"down": down}, "down", [t], rng=1.0, horizon_h=3).at[0, "rises"] == 0
    assert rr.issue_rows({"down": down}, "down", [t], rng=1.0, horizon_h=12).at[0, "rises"] == 1
    gone = down.copy()
    gone[gone.index > t] = np.nan
    assert rr.issue_rows({"down": gone}, "down", [t], rng=1.0, horizon_h=12).at[0, "rises"] is None


# ------------------------------------------------------------------ EA parsing
def test_level_measure_900_and_hydrology_match():
    st = {"stationReference": "F1903", "wiskiID": "W1", "dateOpened": "1990-01-01", "measures": [
        {"@id": f"{EA}/hydrology/id/measures/abc-level-max-86400-m-qualified"},
        {"@id": f"{EA}/hydrology/id/measures/abc-level-i-900-mAOD-qualified"},
        {"@id": f"{EA}/hydrology/id/measures/abc-level-i-900-m-qualified"}]}
    assert rr.level_measure_900(st) == "abc-level-i-900-m-qualified"
    idx = rr.hydrology_index([st, {"stationReference": "X", "measures": []}])
    assert rr.hydrology_for({"stationReference": "F1903"}, idx)["opened"] == "1990-01-01"
    assert rr.hydrology_for({"stationReference": "nope", "wiskiID": "W1"}, idx)["measure"].endswith("-m-qualified")
    assert rr.hydrology_for({"stationReference": "X"}, idx) is None
