"""scripts/water_temperature_model_eval (docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md), on synthetic data only: no
network, no archive value. Row rules, water bodies, folds, air windows, the Open-Meteo plan and weight, the baselines,
the candidate, the group bootstrap, the verdict, and both capped clients."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import networkx as nx
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "water_temperature_model_eval"))
import wt_fetch as wf
import wt_protocol as wp

from dipcast.ingest.rainfall import call_weight


# ---- rows ---------------------------------------------------------------------------------------------------------
def test_water_type_by_material_label():
    assert wp.water_type("RIVER / RUNNING SURFACE WATER") == "river"
    assert wp.water_type("POND / LAKE / RESERVOIR WATER") == "lake"
    assert wp.water_type("SEA WATER AT HIGH TIDE") == "sea"
    assert wp.water_type("CANAL WATER") is None
    assert wp.water_type("ESTUARINE WATER") is None
    assert wp.water_type(None) is None


@pytest.mark.parametrize("text,want", [("12.3", 12.3), (" 7 ", 7.0), ("<0.5", None), (">30", None), ("n/a", None),
                                       ("", None), (None, None), ("nan", None), (14, 14.0)])
def test_parse_result(text, want):
    assert wp.parse_result(text) == want


def raw(rows):
    cols = ["id", "samplingPoint.notation", "samplingPoint.easting", "samplingPoint.northing", "phenomenonTime",
            "sampleMaterialType", "result", "unit"]
    return pd.DataFrame(rows, columns=cols)


def test_clean_rows_drops_and_counts_and_means_a_day():
    R, L = "RIVER / RUNNING SURFACE WATER", "POND / LAKE / RESERVOIR WATER"
    d = raw([
        ("a", "P1", 1, 2, "2020-06-01T10:00:00", R, "10", "CELSIUS"),
        ("a", "P1", 1, 2, "2020-06-01T10:00:00", R, "10", "CELSIUS"),       # duplicate id
        ("b", "P1", 1, 2, "2020-06-01T15:00:00", R, "12", "CELSIUS"),       # same day: mean 11
        ("c", "P1", 1, 2, "2020-06-02T10:00:00", R, "<1", "CELSIUS"),       # not a number
        ("d", "P1", 1, 2, "2020-06-03T10:00:00", R, "40", "CELSIUS"),       # out of range
        ("e", "P1", 1, 2, "2020-06-04T10:00:00", "CANAL WATER", "9", "CELSIUS"),
        ("f", "P1", 1, 2, "2020-04-04T10:00:00", R, "9", "CELSIUS"),        # April: not a row month
        ("g", "P2", 3, 4, "2020-06-01T10:00:00", L, "15", "CELSIUS"),
        ("h", "P2", 3, 4, "2020-06-02T10:00:00", R, "15", "CELSIUS"),       # P2: one each, tie goes to river
        ("i", "P3", 5, 6, "2020-06-01T10:00:00", L, "15", "MG/L"),          # wrong unit
    ])
    out, c = wp.clean_rows(d)
    assert c["duplicate_id"] == 1 and c["not_a_number"] == 1 and c["out_of_range"] == 1
    assert c["other_material"] == 1 and c["not_celsius"] == 1
    p1 = out[out.point == "P1"]
    assert len(p1) == 1 and p1.temp.iloc[0] == 11 and p1.n_readings.iloc[0] == 2
    assert set(out[out.point == "P2"].type) == {"river"}
    assert c["days_with_more_than_one_reading"] == 1


def test_seasons():
    s = wp.season_of(pd.Series(pd.to_datetime(["2017-06-01", "2018-06-01", "2022-09-30", "2023-05-01", "2026-06-01"])))
    assert list(s) == [None, "train", "train", "test", None]


# ---- water bodies -------------------------------------------------------------------------------------------------
def links_frame():
    # a -> b -> c -> d (Avon), e -> b (unnamed tributary), x -> y (another Avon, not touching), f -> g (Brook)
    return pd.DataFrame([
        ("L1", "River Avon", "a", "b"), ("L2", "river  avon", "b", "c"), ("L3", "River Avon", "c", "d"),
        ("L4", None, "e", "b"), ("L5", "River Avon", "x", "y"), ("L6", "Brook", "f", "g"), ("L7", None, "h", "f"),
    ], columns=["id", "watercourse_name", "start_node", "end_node"])


def test_named_rivers_join_same_name_links_that_touch():
    r = wp.named_rivers(links_frame())
    assert r["L1"] == r["L2"] == r["L3"] == "river:river avon:L1"
    assert r["L5"] == "river:river avon:L5"            # another River Avon is another river
    assert r["L6"] == "river:brook:L6"
    assert "L4" not in r


def test_unnamed_link_joins_the_first_named_river_downstream():
    lk = links_frame()
    g = nx.DiGraph()
    for i, _, s, e in lk.itertuples(index=False):
        g.add_edge(s, e, link=i, length=1000.0)
    r = wp.named_rivers(lk)
    assert wp.first_named_downstream(g, "b", r) == "river:river avon:L1"      # from L4's end node
    assert wp.first_named_downstream(g, "f", r) == "river:brook:L6"
    assert wp.first_named_downstream(g, "d", r) is None                       # nothing below
    g.add_edge("z0", "z1", link="U1", length=60_000.0)
    g.add_edge("z1", "z2", link="L9", length=10.0)
    assert wp.first_named_downstream(g, "z0", {**r, "L9": "river:far:L9"}) is None   # beyond 50 km


def test_folds_are_fixed_and_cover_all():
    assert wp.fold_of("river:thames:X") == wp.fold_of("river:thames:X")
    f = {wp.fold_of(f"g{i}") for i in range(200)}
    assert f == set(range(5))


def test_sea_group_is_a_10km_square():
    assert wp.sea_group(123_456, 98_765) == "sea:12_9"


def test_small_upland_definition():
    assert wp.small_upland("river", 19.9, 200)
    assert not wp.small_upland("river", 20.0, 500)
    assert not wp.small_upland("river", 5, 199)
    assert not wp.small_upland("river", float("nan"), 500)
    assert not wp.small_upland("lake", 5, 500)


# ---- air ----------------------------------------------------------------------------------------------------------
def test_air_windows_include_the_day_and_need_all_30_days():
    idx = pd.date_range("2020-04-01", "2020-09-30")
    s = pd.Series(np.arange(len(idx), dtype=float), index=idx)
    f = wp.air_features(s, ["2020-05-01", "2020-04-29", "2020-06-10"])
    i = idx.get_loc(pd.Timestamp("2020-05-01"))
    assert f.a1[0] == i and f.a7[0] == np.mean(np.arange(i - 6, i + 1)) and f.a30[0] == np.mean(np.arange(i - 29, i + 1))
    assert f.iloc[1].isna().all()                        # only 29 days before 29 April
    s2 = s.drop(pd.Timestamp("2020-06-01"))
    assert wp.air_features(s2, ["2020-06-10"]).iloc[0].isna().all()   # a gap inside the 30 days


def test_open_meteo_weight_matches_the_site_rule():
    for n in (1, 7, 25):
        assert wp.om_weight(n) == pytest.approx(call_weight(n, 183, 1))
    assert wp.om_weight(1) == pytest.approx(183 / 140)
    assert call_weight(1, 38, 2) == 1.0                   # the live request stays 1 a cell with temperature added


def test_plan_drops_oldest_training_seasons_then_sea_cells():
    cells = {y: [f"c{i}" for i in range(1000)] for y in (2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025)}
    p = wp.plan_open_meteo(cells, cap=8 * 1000 * 1.31)
    assert p["dropped"] == [] and not p["over_cap"]
    p = wp.plan_open_meteo(cells, cap=7 * 1000 * 1.31)
    assert p["dropped"] == ["training season 2018"] and 2018 not in p["seasons"]
    p = wp.plan_open_meteo(cells, cap=1000)
    assert p["dropped"][:2] == ["training season 2018", "training season 2019"]
    assert {2020, 2021, 2022} <= set(p["seasons"])        # at least three training seasons stay
    assert "sea-only cells" not in p["dropped"]           # none were given
    p = wp.plan_open_meteo({2022: ["a", "s"], 2023: ["a", "s"]}, cap=3.0, sea_cells={"s"})
    assert p["dropped"] == ["sea-only cells"] and p["seasons"] == {2022: ["a"], 2023: ["a"]}


# ---- models -------------------------------------------------------------------------------------------------------
def test_doy_baseline_smooths_and_falls_back():
    m = wp.fit_doy_baseline([150, 151, 152], [10.0, 12.0, 14.0], window=3)
    assert wp.predict_doy(m, [151])[0] == pytest.approx(12.0)
    assert wp.predict_doy(m, [150])[0] == pytest.approx(11.0)     # 149..151: 10 and 12
    assert wp.predict_doy(m, [10])[0] == pytest.approx(12.0)      # no row near: the mean


def test_air7_baseline_is_a_straight_line():
    a7 = np.array([5.0, 10, 15, 20])
    a, b = wp.fit_air7(a7, 2 + 0.8 * a7)
    assert a == pytest.approx(2) and b == pytest.approx(0.8)


def synthetic(n_groups=40, years=(2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025), seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for gi in range(n_groups):
        t = ["river", "lake"][gi % 2]
        off = rng.normal(0, 0.5)
        for y in years:
            for d in pd.date_range(f"{y}-05-01", f"{y}-09-30", freq="7D"):
                a30 = 14 + 4 * np.sin(2 * np.pi * (d.dayofyear - 110) / 365.25)
                a7 = a30 + rng.normal(0, 2)
                a1 = a7 + rng.normal(0, 1.5)
                true = wp.mohseni(a7 if t == "river" else a30, 0, 26, 13, 0.25) + off
                rows.append(dict(group=f"g{gi}", type=t, date=d, year=y, a1=a1, a7=a7, a30=a30,
                                 temp=true + rng.normal(0, 0.3), lake_area_km2=np.nan, upstream_km=50.0))
    f = pd.DataFrame(rows)
    f = wp.add_doy(f)
    f["type_code"] = f["type"].map(wp.TYPE_CODE)
    f["log_lake_area"] = np.nan
    f["log_upstream_km"] = np.where(f.type.eq("river"), np.log10(50), np.nan)
    f["elevation"] = 100.0
    f["season"] = wp.season_of(f["date"])
    f["fold"] = f["group"].map(wp.fold_of)
    return f


def test_candidate_learns_a_lagged_lake_better_than_both_baselines():
    f = synthetic()
    tr = f[(f.season == "train") & (f.fold != 0)].reset_index(drop=True)
    te = f[(f.season == "test") & (f.fold == 0)].reset_index(drop=True)
    m = wp.fit_candidate(tr)
    _, pred = wp.predict_candidate(m, te)
    lake = te.type.eq("lake").to_numpy()
    g = tr[tr.type == "lake"]
    a, b = wp.fit_air7(g.a7, g.temp)
    doy = wp.fit_doy_baseline(g.doy, g.temp)
    e_c = wp.rmse(pred[lake] - te.temp[lake])
    assert e_c < wp.rmse(a + b * te.a7[lake] - te.temp[lake])
    assert e_c < wp.rmse(wp.predict_doy(doy, te.doy[lake]) - te.temp[lake])


def test_fit_mohseni_recovers_a_curve_and_reports_failure():
    a7 = np.linspace(0, 30, 300)
    p, ok = wp.fit_mohseni(a7, wp.mohseni(a7, 1, 24, 12, 0.3))
    assert ok and p[1] == pytest.approx(24, abs=0.05) and p[2] == pytest.approx(12, abs=0.05)
    p, ok = wp.fit_mohseni([1.0], [2.0])                  # too few points
    assert not ok and p == wp.MOHSENI_P0


# ---- bootstrap and verdict ----------------------------------------------------------------------------------------
def test_boot_gains_resample_whole_groups():
    groups = np.repeat(["a", "b", "c", "d"], 50)
    err_c = np.full(200, 1.0)
    err_b = np.full(200, 2.0)
    out = wp.boot_gains(groups, err_c, {"x": err_b}, n_boot=200)
    assert out["x"]["gain"] == pytest.approx(1.0) and out["x"]["lo"] == pytest.approx(1.0)
    # one group where the baseline is far better: the interval must reach below zero
    err_b2 = err_b.copy()
    err_b2[:50] = 0.0
    err_c2 = err_c.copy()
    err_c2[:50] = 5.0
    out = wp.boot_gains(groups, err_c2, {"x": err_b2}, n_boot=500)
    assert out["x"]["lo"] < 0 < out["x"]["hi"]
    again = wp.boot_gains(groups, err_c2, {"x": err_b2}, n_boot=500)
    assert again == out                                   # fixed seed


def test_verdict_cases():
    good = {"doy": {"lo": 0.1}, "air7": {"lo": 0.05}}
    assert wp.verdict("river", 40, 1000, 1.9, good)["label"] == "pass"
    assert wp.verdict("river", 40, 1000, 2.01, good)["label"] == "fail"
    assert wp.verdict("lake", 40, 1000, 1.6, good)["label"] == "fail"
    assert wp.verdict("lake", 40, 1000, 1.5, good)["label"] == "pass"
    assert wp.verdict("river", 40, 1000, 1.0, {"doy": {"lo": 0.1}, "air7": {"lo": 0.0}})["label"] == "fail"
    assert wp.verdict("river", 29, 1000, 1.0, good)["label"] == "too few to judge"
    assert wp.verdict("lake", 30, 299, 1.0, good)["label"] == "too few to judge"


# ---- the capped EA client -----------------------------------------------------------------------------------------
HEADER = "id,samplingPoint.notation,result\n"


def ea_transport(pages_per_month: int, status: int = 200, seen=None):
    def h(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(str(req.url))
        if status != 200:
            return httpx.Response(status, text="no")
        skip = int(req.url.params["skip"])
        n = wf.PAGE if skip // wf.PAGE < pages_per_month - 1 else 7
        return httpx.Response(200, text=HEADER + "".join(f"x{skip + i},P,1\n" for i in range(n)))
    return httpx.MockTransport(h)


def test_ea_pages_until_a_short_page_and_caches(tmp_path):
    seen, sleeps = [], []
    c = wf.EAClient(tmp_path, fetch=True, transport=ea_transport(3, seen=seen), sleep=sleeps.append)
    out = wf.fetch_ea(c, ranges=[("2020-06-01", "2020-06-30")])
    assert out["pages"] == 6 and len(seen) == 6           # 3 fresh + 3 sea
    assert all("environment.data.gov.uk/water-quality/data/observation" in u for u in seen)
    assert "determinand=0076" in seen[0] and "sampleMaterialType=2AZZ%2C2GZZ" in seen[0]
    assert len(sleeps) == 5 and all(0 < s <= wf.EA_PAUSE_S for s in sleeps)
    c2 = wf.EAClient(tmp_path, fetch=False, transport=ea_transport(3, status=500))
    assert wf.fetch_ea(c2, ranges=[("2020-06-01", "2020-06-30")])["pages"] == 6   # all from the cache


@pytest.mark.parametrize("status", [403, 429, 500, 503, 301, 400])
def test_ea_stops_without_retry(tmp_path, status):
    seen = []
    c = wf.EAClient(tmp_path, fetch=True, transport=ea_transport(1, status=status, seen=seen), sleep=lambda s: None)
    with pytest.raises(wf.Stop):
        wf.fetch_ea(c, ranges=[("2020-06-01", "2020-06-30")])
    assert len(seen) == 1


def test_ea_stops_at_too_many_pages_and_at_the_cap(tmp_path):
    c = wf.EAClient(tmp_path / "a", fetch=True, transport=ea_transport(20), sleep=lambda s: None)
    with pytest.raises(wf.Stop, match="pages"):
        wf.fetch_ea(c, ranges=[("2020-06-01", "2020-06-30")])
    c = wf.EAClient(tmp_path / "b", fetch=True, transport=ea_transport(3), sleep=lambda s: None, max_requests=4)
    with pytest.raises(wf.Stop, match="cap"):
        wf.fetch_ea(c, ranges=[("2020-06-01", "2020-06-30")])
    c = wf.EAClient(tmp_path / "b", fetch=True, transport=ea_transport(3), sleep=lambda s: None)
    assert c.n == 4                                       # the cap counts requests from earlier runs


def test_ea_without_fetch_never_asks(tmp_path):
    seen = []
    c = wf.EAClient(tmp_path, fetch=False, transport=ea_transport(1, seen=seen))
    with pytest.raises(wf.Stop, match="not cached"):
        wf.fetch_ea(c, ranges=[("2020-06-01", "2020-06-30")])
    assert seen == []


def test_month_ranges():
    r = wf.month_ranges()
    assert len(r) == 40 and r[0] == ("2018-05-01", "2018-05-31") and r[-1] == ("2025-09-01", "2025-09-30")


# ---- the capped Open-Meteo client ---------------------------------------------------------------------------------
def om_transport(status=200, seen=None, body=None):
    def h(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req.url)
        if status != 200:
            return httpx.Response(status, json={"error": True})
        if body is not None:
            return httpx.Response(200, text=body)
        lats = req.url.params["latitude"].split(",")
        days = pd.date_range(req.url.params["start_date"], req.url.params["end_date"]).strftime("%Y-%m-%d").tolist()
        ans = [{"latitude": float(x), "elevation": 50.0, "daily": {"time": days, "temperature_2m_mean":
                                                                    [10.0] * len(days)}} for x in lats]
        return httpx.Response(200, json=ans if len(ans) > 1 else ans[0])
    return httpx.MockTransport(h)


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def test_open_meteo_request_shape_weight_and_cache(tmp_path):
    seen, sleeps = [], []
    c = wf.OMClient(tmp_path, fetch=True, transport=om_transport(seen=seen), sleep=sleeps.append, others=lambda: [])
    plan = {"seasons": {"2020": [f"5{i}.000_-1.000" for i in range(30)]}}
    out = wf.fetch_open_meteo(c, plan)
    assert out["batches"] == 2 and len(seen) == 2
    u = seen[0]
    assert u.host == "archive-api.open-meteo.com" and u.params["models"] == "era5_land"
    assert u.params["daily"] == "temperature_2m_mean" and u.params["timezone"] == "Europe/London"
    assert u.params["start_date"] == "2020-04-01" and u.params["end_date"] == "2020-09-30"
    assert len(u.params["latitude"].split(",")) == 25
    assert c.spent() == pytest.approx(wp.om_weight(25) + wp.om_weight(5))
    assert len(sleeps) == 1                               # the pause between the two
    seen.clear()
    c2 = wf.OMClient(tmp_path, fetch=True, transport=om_transport(seen=seen), others=lambda: [])
    wf.fetch_open_meteo(c2, plan)
    assert seen == []                                     # cached


@pytest.mark.parametrize("status", [400, 429, 500, 302])
def test_open_meteo_stops_without_retry(tmp_path, status):
    seen = []
    c = wf.OMClient(tmp_path, fetch=True, transport=om_transport(status=status, seen=seen), sleep=lambda s: None,
                    others=lambda: [])
    with pytest.raises(wf.Stop):
        wf.fetch_open_meteo(c, {"seasons": {"2020": ["51.000_-1.000"]}})
    assert len(seen) == 1


def test_open_meteo_stops_on_a_body_that_is_not_json(tmp_path):
    c = wf.OMClient(tmp_path, fetch=True, transport=om_transport(body="{cut"), sleep=lambda s: None,
                    others=lambda: [])
    with pytest.raises(wf.Stop, match="JSON"):
        wf.fetch_open_meteo(c, {"seasons": {"2020": ["51.000_-1.000"]}})


def test_open_meteo_total_cap(tmp_path):
    c = wf.OMClient(tmp_path, fetch=True, transport=om_transport(), sleep=lambda s: None, others=lambda: [],
                    total_cap=wp.om_weight(25) + 1)
    with pytest.raises(wf.Stop, match="total cap"):
        wf.fetch_open_meteo(c, {"seasons": {"2020": [f"5{i}.000_-1.000" for i in range(30)]}})
    assert c.spent() == pytest.approx(wp.om_weight(25))


def test_open_meteo_day_cap_sleeps_to_the_next_utc_day(tmp_path):
    clock = Clock(datetime(2026, 10, 27, 22, 0, tzinfo=UTC))
    slept = []

    def sleep(s):
        slept.append(s)
        if s > 3600:
            clock.t = datetime(2026, 10, 28, 0, 10, tzinfo=UTC)

    c = wf.OMClient(tmp_path, fetch=True, transport=om_transport(), sleep=sleep, now=clock, others=lambda: [],
                    day_cap=wp.om_weight(25) + 1)
    # log lines carry real UTC times; the day cap reads the log by day, so pin them to the fake clock's day
    c.log.add = lambda status, size, weight, url: open(c.log.path, "a").write(
        f"{clock.t.isoformat(timespec='seconds')}\t{status}\t{size}\t{weight}\t{url}\n")
    wf.fetch_open_meteo(c, {"seasons": {"2020": [f"5{i}.000_-1.000" for i in range(30)]}})
    assert any(s > 3600 for s in slept)                   # waited for 00:10 UTC
    days = {ln.split("\t")[0][:10] for ln in c.log.path.read_text().splitlines()}
    assert days == {"2026-10-27", "2026-10-28"}


def test_open_meteo_waits_while_another_job_runs(tmp_path):
    calls = {"n": 0}

    def others():
        calls["n"] += 1
        return ["123 python fetch_rain_archive.py open-meteo"] if calls["n"] == 1 else []

    slept = []
    c = wf.OMClient(tmp_path, fetch=True, transport=om_transport(), sleep=slept.append, others=others)
    wf.fetch_open_meteo(c, {"seasons": {"2020": ["51.000_-1.000"]}})
    assert 600 in slept


def test_other_jobs_ignore_this_fetch(monkeypatch):
    class R:
        stdout = "11 python wt_fetch.py open_meteo --fetch\n12 zsh -c x wt_fetch.py open_meteo\n13 other open-meteo job\n"
    monkeypatch.setattr(wf.subprocess, "run", lambda *a, **k: R())
    assert wf.other_open_meteo_jobs(me=1) == ["13 other open-meteo job"]


def test_open_meteo_without_fetch_never_asks(tmp_path):
    seen = []
    c = wf.OMClient(tmp_path, fetch=False, transport=om_transport(seen=seen), others=lambda: [])
    with pytest.raises(wf.Stop, match="not cached"):
        wf.fetch_open_meteo(c, {"seasons": {"2020": ["51.000_-1.000"]}})
    assert seen == [] and json.loads("[]") == []
