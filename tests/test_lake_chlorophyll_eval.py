"""scripts/lake_chlorophyll_eval (docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md), on synthetic data only: no network, no
satellite file, no chlorophyll value. The value-dropping WQA parsers (nothing printed, saved or logged holds a
result), the lake selection rule, the "<" rule, pairing, Spearman with its cluster bootstrap, the placebo, the
leave-one-lake-out calibration and its labels, the gate, the lake-type condition and the stop rules."""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "lake_chlorophyll_eval"))
import chl_protocol as cp
import chl_stage1
import chl_stage2
import net
import select_lakes
import wqa_meta as w

# A sentinel no real field holds: if it appears anywhere after parsing, a value leaked.
SENTINEL = "73.4219"
HEADER = ("id,samplingPoint.notation,samplingPoint.prefLabel,samplingPoint.easting,samplingPoint.northing,"
          "samplingPoint.region,samplingPoint.area,samplingPoint.subArea,samplingPoint.samplingPointStatus,"
          "samplingPoint.samplingPointType,phenomenonTime,samplingPurpose,sampleMaterialType,determinand.notation,"
          "determinand.prefLabel,result,unit")


def csv_rows(rows: list[tuple]) -> str:
    """rows: (point, easting, northing, type, time, result)."""
    out = [HEADER]
    for i, (p, e, n, t, time, res) in enumerate(rows):
        out.append(f"obs{i},{p},LAKE {p},{e},{n},AN,A,S,OPEN,{t},{time},PLANNED,POND / LAKE / RESERVOIR WATER,"
                   f"7887,Chlorophyll : Acetone Extract,{res},MICROGRAM PER LITRE")
    return "\n".join(out) + "\n"


LAKE_T = "FRESHWATER - LAKES/PONDS/RESERVOIRS"
RIVER_T = "FRESHWATER - RIVERS"


# --- the value-dropping parsers --------------------------------------------------------------------------------
def test_keep_only_drops_the_result_and_its_qualifier():
    text = csv_rows([("AN-1", 600000, 300000, LAKE_T, "2025-06-01T10:00:00", SENTINEL),
                     ("AN-1", 600000, 300000, LAKE_T, "2025-07-01T10:00:00", "<" + SENTINEL)])
    df = w.keep_only(text)
    assert list(df.columns) == list(w.KEPT)
    assert len(df) == 2
    dumped = df.to_csv() + df.to_json() + repr(df.to_dict("records"))
    assert SENTINEL not in dumped and "<" not in dumped
    assert not any(any(v in c for v in w.VALUE_WORDS) for c in df.columns)


def test_keep_only_refuses_an_unknown_header_with_names_only():
    with pytest.raises(w.ValueLeak) as e:
        w.keep_only("result,unit\n" + SENTINEL + ",UG\n")
    assert SENTINEL not in str(e.value)


def test_keep_only_jsonld_never_reads_the_result():
    members = [{"hasSamplingPoint": {"notation": "NW-1", "prefLabel": "TARN",
                                     "samplingPointType": {"notation": "FA"}},
                "phenomenonTime": "2024-07-01T09:00:00", "hasSimpleResult": SENTINEL,
                "hasResult": {"numericValue": float(SENTINEL), "upperBound": 1.0}, "hasUnit": "ug/l",
                "observedProperty": {"notation": "7887"}}]
    df = w.keep_only_jsonld(members)
    assert list(df.columns) == list(w.KEPT)
    assert SENTINEL not in df.to_csv()
    assert df.loc[0, "wqa_point"] == "NW-1" and df.loc[0, "sample_time"].startswith("2024-07-01")


def test_assert_no_values_refuses_any_other_column():
    df = pd.DataFrame({"wqa_point": ["A"], "sample_time": ["2025-06-01"], "result": [SENTINEL]})
    with pytest.raises(w.ValueLeak):
        w.assert_no_values(df)


class FakeResponse:
    def __init__(self, status, body: bytes):
        self.status_code, self.body = status, body

    def iter_bytes(self, n):
        for i in range(0, len(self.body), n):
            yield self.body[i:i + n]


class FakeHttp:
    def __init__(self, pages: list[tuple[int, bytes]]):
        self.pages, self.calls = list(pages), []

    @contextlib.contextmanager
    def stream(self, method, url, headers=None, json=None):
        self.calls.append((method, url, headers))
        st, body = self.pages.pop(0)
        yield FakeResponse(st, body)


def test_the_listing_step_saves_logs_and_prints_no_value(tmp_path, capsys):
    page = csv_rows([("AN-1", 600000, 300000, LAKE_T, "2025-06-01T10:00:00", SENTINEL)]).encode()
    http = FakeHttp([(200, page)] * len(cp.YEARS))
    select_lakes.list_dates(tmp_path, http=http, sleep=lambda s: None)
    assert len(http.calls) == len(cp.YEARS)                      # one season a request, at most a year each
    for method, url, _ in http.calls:
        assert method == "POST" and "determinand=7887" in url and "dateFrom=" in url and "dateTo=" in url
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert SENTINEL.encode() not in f.read_bytes(), f.name
    assert SENTINEL not in capsys.readouterr().out
    d = pd.read_parquet(tmp_path / "dates.parquet")
    assert list(d.columns) == list(w.KEPT)


def test_wqa_client_only_the_ea_host_and_no_credentials(tmp_path):
    c = w.client(tmp_path / "l.jsonl", http=FakeHttp([(200, b"")]), sleep=lambda s: None)
    with pytest.raises(net.CapReached):
        c.request("GET", "https://example.com/water-quality/x")
    with pytest.raises(net.CapReached):
        c.request("GET", "https://environment.data.gov.uk/flood-monitoring/x")
    with pytest.raises(net.CapReached):
        c.request("GET", w.url("/codelist/unit"), headers={"Authorization": "x"})


@pytest.mark.parametrize("status", [400, 429, 500, 503])
def test_wqa_client_stops_on_bad_status(status, tmp_path):
    c = w.client(tmp_path / "l.jsonl", http=FakeHttp([(status, b"")]), sleep=lambda s: None)
    with pytest.raises(net.Stop):
        c.request("POST", w.url("/data/observation"))


def test_wqa_client_cap_over_all_runs(tmp_path):
    ledger = tmp_path / "l.jsonl"
    ledger.write_text("".join(json.dumps({"bytes": 1}) + "\n" for _ in range(w.META_MAX_REQUESTS_TOTAL)))
    c = w.client(ledger, http=FakeHttp([(200, b"")]), sleep=lambda s: None)
    with pytest.raises(net.CapReached):
        c.request("GET", w.url("/codelist/unit"))


def test_wqa_client_paces_one_second(tmp_path):
    sleeps = []
    c = w.client(tmp_path / "l.jsonl", http=FakeHttp([(200, b"")] * 3), sleep=sleeps.append)
    for _ in range(3):
        c.request("GET", w.url("/codelist/unit"))
    assert len(sleeps) == 2 and all(0 < s <= 1.0 for s in sleeps)


# --- the selection rule ----------------------------------------------------------------------------------------
def lakes_gdf():
    import geopandas as gpd
    from shapely.geometry import Point, box
    return gpd.GeoDataFrame({
        "WB_ID": ["GB1", "GB2", "GB3", "GB4"],
        "WB_NAME": ["Big Lake", "Tiny Pond", "Other Lake", "Fourth Lake"],
        "hydromorph": ["heavily modified"] * 4,
        "geometry": [Point(0, 0).buffer(1000), box(5000, 0, 5040, 40), Point(10000, 0).buffer(800),
                     Point(20000, 0).buffer(800)]}, crs=27700)


def dates_frame(spec: list[tuple]) -> pd.DataFrame:
    """spec: (point, easting, northing, type, [dates])."""
    rows = []
    for p, e, n, t, ds in spec:
        for d in ds:
            rows.append({"wqa_point": p, "point_label": p, "easting": str(e), "northing": str(n), "point_type": t,
                         "sample_time": f"{d}T10:00:00", "determinand": "7887", "unit": cp.UNIT,
                         "purpose": "X", "material": "Y"})
    return pd.DataFrame(rows, columns=list(w.KEPT))


SIX = ["2023-05-02", "2023-06-02", "2023-07-02", "2024-05-02", "2024-06-02", "2024-07-02"]


def test_select_rule_and_its_steps():
    spec = [
        ("P-BIG", 0, 0, LAKE_T, SIX + ["2022-06-01"]),                 # chosen
        ("P-BIG2", 100, 0, LAKE_T, SIX[:5] + ["2022-06-01", "2022-07-01"]),  # same lake, fewer imagery dates
        ("P-TINY", 5020, 20, LAKE_T, SIX),                              # fails the inset area rule
        ("P-FAR", 10000 + 900, 0, LAKE_T, SIX),                         # 100 m off the outline: fails
        ("P-RIVER", 10000, 0, RIVER_T, SIX),                            # typed river: fails
        ("P-SHORE", 20000 + 840, 0, LAKE_T, SIX),                       # 40 m outside: a shore sample, kept
        ("P-FEW", 10000, 100, LAKE_T, SIX[:4] + ["2022-06-01", "2022-07-01"]),  # 4 dates with imagery: fails
    ]
    chosen, counts = cp.select(dates_frame(spec), lakes_gdf(), {"GB1": 2.0, "GB4": 9.0})
    assert [p["wqa_point"] for p in chosen] == ["P-BIG", "P-SHORE"]
    assert counts["points_typed_lake_or_bathing_water"] == 6
    assert counts["points_on_or_within_50m_of_a_wfd_lake"] == 5     # BIG, BIG2, TINY, SHORE, FEW
    assert counts["points_past_the_inset_area_rule"] == 4
    assert counts["points_with_5_or_more_dates_in_seasons_with_imagery"] == 3
    big = chosen[0]
    assert big["n_dates_imagery"] == 6 and "2022-06-01" in big["dates"]   # 2022 listed, not counted
    assert big["lake_type"] == "shallow" and chosen[1]["lake_type"] == "deeper"
    assert chosen[1]["inside_outline"] is False


def test_select_cap_breaks_ties_by_area_then_id(monkeypatch):
    monkeypatch.setattr(cp, "MAX_LAKES", 1)
    spec = [("P-A", 0, 0, LAKE_T, SIX), ("P-B", 10000, 0, LAKE_T, SIX)]
    chosen, counts = cp.select(dates_frame(spec), lakes_gdf())
    assert [p["wb_id"] for p in chosen] == ["GB1"] and counts["lakes_left_out_by_the_cap"] == 1
    assert chosen[0]["lake_type"] is None                            # no depth: in no lake-type group


def test_select_ignores_other_determinands_and_units():
    d = dates_frame([("P-BIG", 0, 0, LAKE_T, SIX)])
    d.loc[:2, "determinand"] = "7888"
    d.loc[3, "unit"] = "MILLIGRAM PER LITRE"
    chosen, counts = cp.select(d, lakes_gdf())
    assert chosen == [] and counts["point_dates_may_sep"] == 2


# --- the outcome values ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("s,v,how", [("12.5", 12.5, "measured"), ("<0.5", 0.25, "censored"), ("< 2", 1.0, "censored"),
                                     (">200", 200.0, "above"), ("n/a", np.nan, "dropped"), ("0", np.nan, "dropped"),
                                     ("-1", np.nan, "dropped"), (None, np.nan, "dropped")])
def test_chl_value(s, v, how):
    got, h = cp.chl_value(s)
    assert h == how and (np.isnan(got) if np.isnan(v) else got == pytest.approx(v))


POINTS = [{"wqa_point": "P1", "wb_id": "GB1", "lake_name": "One", "lake_type": "shallow"},
          {"wqa_point": "P2", "wb_id": "GB2", "lake_name": "Two", "lake_type": "deeper"}]


def values_frame(rows):
    return pd.DataFrame([{"wqa_point": p, "sample_time": t, "determinand": "7887", "unit": cp.UNIT, "purpose": "X",
                          "result": r} for p, t, r in rows])


def test_prepare_samples_one_a_day_season_only_and_stop_rules():
    v = values_frame([("P1", "2024-06-01T09:00:00", "10"), ("P1", "2024-06-01T15:00:00", "99"),
                      ("P1", "2024-03-01T09:00:00", "5"), ("P1", "2024-07-01T09:00:00", "<1"),
                      ("P2", "2024-07-01T09:00:00", "bad"), ("P9", "2024-07-01T09:00:00", "3")])
    s, counts = cp.prepare_samples(v, POINTS)
    assert len(s) == 2                                                  # March out, P9 not chosen, 'bad' dropped
    assert s.loc[0, "chl"] == 10 and s.loc[1, "chl"] == 0.5
    assert counts == {"measured": 1, "censored": 1, "above": 0, "dropped": 1}
    with pytest.raises(cp.StopRule):
        cp.prepare_samples(v.assign(unit="MILLIGRAM PER LITRE"), POINTS)
    with pytest.raises(cp.StopRule):
        cp.prepare_samples(v.assign(determinand="7888"), POINTS)


# --- pairing ---------------------------------------------------------------------------------------------------
def test_pairing_nearest_within_one_day_tie_to_the_earlier():
    import datetime as dt
    samples = pd.DataFrame({"wqa_point": ["P1", "P1", "P1", "P2"],
                            "date": [dt.date(2024, 6, 10), dt.date(2024, 6, 20), dt.date(2024, 7, 1),
                                     dt.date(2024, 6, 10)]})
    scenes = pd.DataFrame({"bw_id": ["P1", "P1", "P1", "P1", "P1"],
                           "scene_date": ["2024-06-09", "2024-06-10", "2024-06-19", "2024-06-21", "2024-07-03"],
                           "reading": [0.1, 0.2, 0.3, 0.4, 0.5]})
    p = cp.pair(samples, scenes)
    assert p["reading"].tolist()[:2] == [0.2, 0.3]                       # same day first; tie -1/+1 -> earlier
    assert p["lag_days"].tolist()[:2] == [0, -1]
    assert np.isnan(p.loc[2, "reading"])                                # 2 days away: none
    assert np.isnan(p.loc[3, "reading"])                                # another point's scene is not used
    p0 = cp.pair(samples, scenes, window=0)
    assert p0["reading"].notna().sum() == 1


def test_stage1_reads_bands_only_near_sample_dates():
    items = [{"properties": {"datetime": f"2024-06-{d:02d}T11:00:00Z"}} for d in (8, 9, 10, 11, 12)]
    got = [i["properties"]["datetime"][:10] for i in chl_stage1.near(items, {"2024-06-10"})]
    assert got == ["2024-06-09", "2024-06-10", "2024-06-11"]


# --- scoring ---------------------------------------------------------------------------------------------------
def synthetic_rows(signal: str, n_lakes=12, seasons=(2023, 2024, 2025), per=6, seed=1) -> pd.DataFrame:
    """signal 'day': the reading tracks each sample (within lakes too); 'lake': it tracks only the lake's level;
    'none': noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n_lakes):
        level = rng.normal(1.0, 0.5)
        for s in seasons:
            for _ in range(per):
                y = level + rng.normal(0, 0.3)
                r = {"day": 0.1 * y + rng.normal(0, 0.005), "lake": 0.1 * level + rng.normal(0, 0.005),
                     "none": rng.normal(0, 0.1)}[signal]
                rows.append({"wb_id": f"GB{k:02d}", "season": s, "lake_type": "shallow" if k % 2 else "deeper",
                             "reading": r, "log_chl": y})
    return pd.DataFrame(rows)


def test_spearman_and_its_interval():
    good = synthetic_rows("day")
    draws = cp.sat.cluster_draws(good["wb_id"].to_numpy(), n=200)
    c = cp.rho_with_interval(good, draws)
    assert c["rho"] > 0.9 and c["L"] > 0.3 and c["holds"]
    bad = synthetic_rows("none")
    c = cp.rho_with_interval(bad, cp.sat.cluster_draws(bad["wb_id"].to_numpy(), n=200))
    assert not c["holds"]
    assert np.isnan(cp.spearman([1, 1, 1], [1, 2, 3]))


def test_placebo_passes_for_day_signal_fails_for_lake_signal():
    day = synthetic_rows("day")
    p = cp.placebo(day, n=200)
    assert cp.placebo_check(cp.spearman(day["reading"], day["log_chl"]), p)["holds"]
    lake = synthetic_rows("lake")
    p = cp.placebo(lake, n=200)
    assert not cp.placebo_check(cp.spearman(lake["reading"], lake["log_chl"]), p)["holds"]


def test_lolo_never_sees_the_held_out_lake():
    rows = synthetic_rows("day")
    rows.loc[rows["wb_id"] == "GB00", "log_chl"] += 100                 # an absurd lake
    pred = cp.lolo(rows)
    held = rows["wb_id"] == "GB00"
    assert (pred.loc[held, "ref"] < 10).all()                           # its own values never reach its reference
    others = rows[~held]
    want = others.groupby("wb_id")["log_chl"].mean().mean()             # every other lake counts once
    assert pred.loc[held, "ref"].iloc[0] == pytest.approx(want)


def test_calibration_skill_labels():
    good = synthetic_rows("day")
    pred = cp.lolo(good)
    s = cp.skill_with_label(good["log_chl"], pred["fit"], pred["ref"], good["wb_id"].to_numpy())
    assert s["skill"] > 0.8 and s["label"] == "Better"
    bad = synthetic_rows("none")
    pred = cp.lolo(bad)
    s = cp.skill_with_label(bad["log_chl"], pred["fit"], pred["ref"], bad["wb_id"].to_numpy())
    assert s["label"] != "Better"
    assert cp.skill([1, 2], [1, 2], [1.5, 1.5]) == pytest.approx(1.0)
    assert cp.skill([1, 2], [1.5, 1.5], [1.5, 1.5]) == pytest.approx(0.0)


@pytest.mark.parametrize("d,L,U,want", [(0.10, 0.01, 0.2, "Better"), (0.099, 0.01, 0.2, "Unlabelled"),
                                        (0.05, -0.049, 0.2, "Promising, not shown"),
                                        (0.05, -0.05, 0.2, "Too uncertain"),
                                        (0.0, -0.04, 0.09, "No useful difference"),
                                        (-0.01, -0.06, 0.02, "Possible harm")])
def test_labels_at_the_stated_margins(d, L, U, want):
    assert cp.label(d, L, U, cp.B_SKILL, cp.H_SKILL) == want


def test_gate_boundaries():
    rows = pd.DataFrame({"wb_id": [f"L{i % 10}" for i in range(60)], "season": [2023, 2024, 2025] * 20})
    g = cp.gate(rows)
    assert g["judged"] and g["lakes_with_3"] == 10 and g["seasons_with_10"] == 3
    assert not cp.gate(rows.iloc[:59])["judged"]
    rows2 = rows.assign(wb_id=[f"L{i % 9}" for i in range(60)])
    assert not cp.gate(rows2)["judged"]                                 # 9 lakes
    rows3 = rows.assign(season=[2023] * 50 + [2024] * 10)
    assert not cp.gate(rows3)["judged"]                                 # 2 seasons with 10


def test_score_verdicts():
    good = cp.score(synthetic_rows("day"))
    assert good["verdict"] == "Passes", good["conditions"]
    lake = cp.score(synthetic_rows("lake"))
    assert lake["verdict"].startswith("Fails") and not lake["conditions"]["2"]["holds"]
    few = cp.score(synthetic_rows("day", n_lakes=4))
    assert few["verdict"] == "Too few to judge"


def test_lake_type_possible_harm_fails_condition_4():
    rows = synthetic_rows("day", n_lakes=16)
    deep = rows["lake_type"] == "deeper"
    rng = np.random.default_rng(3)
    rows.loc[deep, "reading"] = rng.permutation(rows.loc[deep, "reading"].to_numpy())   # no signal in deep lakes
    rows.loc[deep, "log_chl"] = rows.loc[deep, "log_chl"] * 3
    out = cp.score(rows)
    labels = out["conditions"]["4"]["labels"]
    assert labels["deeper"] in ("Possible harm", "Harm") and not out["conditions"]["4"]["holds"]
    assert out["verdict"].startswith("Fails")


def test_small_lake_type_group_is_too_few_and_does_not_block():
    rows = synthetic_rows("day")
    rows.loc[rows["wb_id"].isin(["GB01", "GB03", "GB05", "GB07", "GB09"]), "lake_type"] = None   # 1 shallow left
    g = cp.by_lake_type(rows, cp.lolo(rows))
    assert g["shallow"]["label"] == "Too few to judge"


# --- stage 2: stop rules and the one fetch ---------------------------------------------------------------------
def write_features(out: Path) -> str:
    f = pd.DataFrame({"bw_id": ["P1"], "water_body": ["GB1"], "tile": ["30UXD"], "item_id": ["i1"],
                      "scene_date": ["2024-06-01"], "clear_core": [20], "n_core": [20], "usable": [True],
                      "reading": [0.1]})
    f.to_parquet(out / "features.parquet", index=False)
    return cp.sha256(out / "features.parquet")


def test_fetch_refuses_a_changed_features_file_and_a_second_fetch(tmp_path):
    h = write_features(tmp_path)
    lakes = tmp_path / "lakes.json"
    lakes.write_text(json.dumps({"points": POINTS}))
    with pytest.raises(cp.StopRule):
        chl_stage2.fetch(tmp_path, lakes, "0" * 64, http=FakeHttp([]))
    (tmp_path / "values.parquet").write_bytes(b"x")
    with pytest.raises(cp.StopRule):
        chl_stage2.fetch(tmp_path, lakes, h, http=FakeHttp([]))


def test_fetch_one_point_a_request_and_prints_no_value(tmp_path, capsys):
    h = write_features(tmp_path)
    lakes = tmp_path / "lakes.json"
    lakes.write_text(json.dumps({"points": POINTS}))
    page = csv_rows([("P1", 1, 1, LAKE_T, "2024-06-01T10:00:00", SENTINEL)]).encode()
    http = FakeHttp([(200, page), (200, page.replace(b"P1", b"P2"))])
    chl_stage2.fetch(tmp_path, lakes, h, http=http, sleep=lambda s: None)
    assert len(http.calls) == 2
    assert "pointNotation=P1" in http.calls[0][1] and "pointNotation=P2" in http.calls[1][1]
    assert "dateFrom=2020-05-01" in http.calls[0][1] and "determinand=7887" in http.calls[0][1]
    assert SENTINEL not in capsys.readouterr().out
    assert (tmp_path / "values.sha256").read_text().strip() == cp.sha256(tmp_path / "values.parquet")


def test_score_frames_end_to_end():
    rows = synthetic_rows("day", n_lakes=12, seasons=(2023, 2024, 2025), per=4)
    points, feats, vals = [], [], []
    for k, g in rows.groupby("wb_id"):
        p = f"P-{k}"
        points.append({"wqa_point": p, "wb_id": k, "lake_name": k, "lake_type": g["lake_type"].iloc[0]})
        for j, r in enumerate(g.itertuples(index=False)):
            day = pd.Timestamp(f"{r.season}-05-01") + pd.Timedelta(days=10 * j)
            vals.append((p, f"{day.date()}T10:00:00", f"{10 ** r.log_chl:.6f}"))
            feats.append({"bw_id": p, "water_body": k, "tile": "T", "item_id": f"{p}-{j}-{r.season}",
                          "scene_date": str((day + pd.Timedelta(days=1)).date()), "clear_core": 20, "n_core": 20,
                          "usable": True, "reading": r.reading})
    sizes = {p["wqa_point"]: {"in_test": True} for p in points}
    sizes["P-GB00"]["in_test"] = False
    rep = chl_stage2.score_frames(pd.DataFrame(feats), values_frame(vals), points, sizes)
    assert rep["points_out"] == ["P-GB00"]
    assert rep["result"]["gate"]["lakes"] == 11
    assert rep["lag_days"] == {1: len(rows) - 12}
    assert rep["result"]["verdict"] == "Passes"


def test_caps_are_the_stated_ones():
    assert (chl_stage1.STAGE1_MAX_REQUESTS_TOTAL, chl_stage1.STAGE1_MAX_BYTES_TOTAL) == (70_000, 4608 * 1024**2)
    assert (chl_stage1.STAGE1_MAX_REQUESTS_PER_RUN, chl_stage1.STAGE1_MAX_BYTES_PER_RUN) == (20_000, 1536 * 1024**2)
    assert (w.META_MAX_REQUESTS_TOTAL, chl_stage2.FETCH_MAX_REQUESTS) == (200, 80)
    assert net.WORKERS == 16 and net.PAUSE_S == 1.0
