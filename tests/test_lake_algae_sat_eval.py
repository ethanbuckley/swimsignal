"""scripts/lake_algae_sat_eval (docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md), on synthetic data only: no network, no
satellite file, no EA check. A lake with a shore and a pond too small for the size rule; clouds; the reflectance stop
rule; the hash stop rule; pairing and label boundaries; a placebo that passes when the signal is in the day and fails
when it is only in the lake; the COG reader; the download caps."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "lake_algae_sat_eval"))
import cog
import net
import protocol as pr
import stage1
import stage2

# --- a synthetic site: a lake (radius 12 px) and a 3 x 3 pond, on a 41 x 41 grid of 20 m pixels ------------------
N = 41
ROWS, COLS = np.indices((N, N))
LAKE = (ROWS - 20) ** 2 + (COLS - 14) ** 2 <= 12 ** 2
POND = (ROWS >= 3) & (ROWS < 6) & (COLS >= 34) & (COLS < 37)
CENTRE = (20.5, 20.5)   # the point, in the lake, 6 px (120 m) east of its middle


def scene(cloud: np.ndarray | None = None, scum: np.ndarray | None = None) -> np.ndarray:
    s = np.full((N, N), 4, dtype=np.uint8)          # vegetation
    s[LAKE | POND] = 6
    if scum is not None:
        s[scum] = 4                                  # a dense scum the classifier calls land
    if cloud is not None:
        s[cloud] = 9
    return s


def stack(n=10, cloudy=3):
    out = [scene() for _ in range(n)]
    for i in range(cloudy):
        out[i] = scene(cloud=ROWS < 30)              # most of the lake under cloud
    return np.stack(out)


def test_water_mask_votes_only_where_seen():
    st = stack()
    m = pr.water_mask(st)
    assert (m == (LAKE | POND)).all()
    always_cloud = st.copy()
    always_cloud[:, 0, 0] = 9                        # never seen: not water
    always_cloud[:4, 1, 1], always_cloud[4:, 1, 1] = 6, 4   # water in 4 of 10 seen: not water
    always_cloud[:5, 2, 2], always_cloud[5:, 2, 2] = 6, 4   # in exactly half: water
    m2 = pr.water_mask(always_cloud)
    assert not m2[0, 0] and not m2[1, 1] and m2[2, 2]
    nodata = st.copy()
    nodata[:9, 20, 14] = 0                            # no data in 9 scenes, water in the one that saw it
    assert pr.water_mask(nodata)[20, 14]


def test_a_scum_in_some_scenes_does_not_cut_the_mask():
    scum = LAKE & (COLS > 14)
    st = np.stack([scene(scum=scum) for _ in range(3)] + [scene() for _ in range(7)])
    assert (pr.water_mask(st) == (LAKE | POND)).all()


def test_site_water_core_and_size_rule():
    m = pr.water_mask(stack())
    piece, site = pr.site_water(m, CENTRE)
    assert (piece == LAKE).all()                     # the pond is another piece
    d = np.hypot(ROWS + 0.5 - CENTRE[0], COLS + 0.5 - CENTRE[1]) * 20
    assert (site == (LAKE & (d <= 300))).all()
    core = pr.core_pixels(piece, site)
    shore = LAKE & ~(np.pad(LAKE, 1)[0:-2, 1:-1] & np.pad(LAKE, 1)[2:, 1:-1] & np.pad(LAKE, 1)[1:-1, 0:-2]
                     & np.pad(LAKE, 1)[1:-1, 2:])
    assert not (core & shore).any()
    assert core.sum() >= pr.MIN_CORE and pr.passes_size_rule(core)
    ppiece, psite = pr.site_water(m, (4.5, 35.5))
    assert (ppiece == POND).all()
    pcore = pr.core_pixels(ppiece, psite)
    assert pcore.sum() == 1 and not pr.passes_size_rule(pcore)
    empty_piece, empty_site = pr.site_water(np.zeros((5, 5), bool), (2.5, 2.5))
    assert not empty_piece.any() and not empty_site.any()


def test_the_300_m_cut_is_not_a_shore():
    big = np.ones((61, 61), bool)
    piece, site = pr.site_water(big, (30.5, 30.5))
    core = pr.core_pixels(piece, site)
    assert (core == site).all()                      # pixels at the cut keep their core status


def test_scene_clear_boundary():
    core = np.zeros((10, 10), bool)
    core[:, :] = True                                # 100 core pixels
    s = np.full((10, 10), 6, np.uint8)
    s.flat[:20] = 9                                  # 80 clear: usable
    assert pr.scene_clear(s, core) == (80, True)
    s.flat[20] = 3                                   # 79 clear: not
    assert pr.scene_clear(s, core) == (79, False)
    assert pr.scene_clear(s, np.zeros_like(core)) == (0, False)
    for c in pr.CLEAR:
        assert pr.scene_clear(np.full((10, 10), c, np.uint8), core)[1]


def test_reflectance_needs_scale_and_offset():
    dn = np.array([[0, 1000], [2000, 3000]], dtype=np.uint16)
    r = pr.reflectance(dn, {"scale": 0.0001, "offset": -0.1, "nodata": 0})
    assert np.isnan(r[0, 0]) and r[0, 1] == pytest.approx(0.0) and r[1, 1] == pytest.approx(0.2)
    with pytest.raises(pr.StopRule):
        pr.reflectance(dn, {"scale": 0.0001})
    with pytest.raises(pr.StopRule):
        pr.reflectance(dn, None)
    with pytest.raises(pr.StopRule):
        stage1.check_items([{"id": "x", "assets": {"red": {"raster:bands": [{"scale": 1e-4, "offset": -0.1}]},
                                                   "rededge1": {"raster:bands": [{"scale": 1e-4}]}}}])
    stage1.check_items([{"id": "y", "assets": {a: {"raster:bands": [{"scale": 1e-4, "offset": -0.1}]}
                                               for a in ("red", "rededge1")}}])


def test_b4_mean_ndci_and_the_scene_reading():
    b4 = np.arange(16, dtype=float).reshape(4, 4) / 100 + 0.01
    m = pr.b4_to_20m(b4)
    assert m.shape == (2, 2) and m[0, 0] == pytest.approx(np.mean([0.01, 0.02, 0.05, 0.06]))
    b4[0, 0] = np.nan
    assert np.isnan(pr.b4_to_20m(b4)[0, 0])
    v = pr.ndci(np.array([0.02, 0.02, -0.01, np.nan]), np.array([0.03, 0.0, 0.03, 0.03]))
    assert v[0] == pytest.approx(0.2) and np.isnan(v[1:]).all()
    core = np.ones((3, 3), bool)
    idx = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, np.nan]])
    s = np.full((3, 3), 6, np.uint8)
    assert pr.scene_reading(s, core, idx) == (9, True, pytest.approx(0.45))
    s[0, 0] = 9                                      # 8 of 9 clear (89%): usable, the cloudy pixel left out
    assert pr.scene_reading(s, core, idx)[2] == pytest.approx(0.5)
    s[0, 1] = 9                                      # 7 of 9 (78%): not usable
    assert np.isnan(pr.scene_reading(s, core, idx)[2])


def test_one_per_date_keeps_the_clearest_then_the_first_id():
    f = pd.DataFrame({"bw_id": ["a"] * 4, "scene_date": ["2025-07-01"] * 3 + ["2025-07-02"],
                      "item_id": ["S2B_x", "S2A_y", "S2C_z", "S2A_w"], "clear_core": [50, 50, 40, 10],
                      "usable": [True, True, True, False], "reading": [0.1, 0.2, 0.3, 0.4]})
    o = pr.one_per_date(f)
    assert o["item_id"].tolist() == ["S2A_y"]


def test_hash_stop_rule(tmp_path):
    p = tmp_path / "features.parquet"
    pd.DataFrame({"a": [1, 2]}).to_parquet(p, index=False)
    h = pr.sha256(p)
    pr.check_hash(p, h + "\n")
    with pytest.raises(pr.StopRule):
        pr.check_hash(p, "0" * 64)
    with pytest.raises(pr.StopRule):
        stage2.score(tmp_path, "0" * 64, "0" * 64)


def test_level_map_matches_algae():
    from dipcast import algae
    pr.check_levels(dict(algae.LEVELS))
    bad = dict(algae.LEVELS)
    bad["No material present"] = (1, "none seen")
    with pytest.raises(pr.StopRule):
        pr.check_levels(bad)


# --- checks, pairing, gate, labels -------------------------------------------------------------------------
SITES = pd.DataFrame({"bw_id": ["s1", "s2"], "name": ["Windermere, Fellfoot", "Henleaze Lake"],
                      "wqa_point": ["P1", "P2"], "water_body": ["Windermere", "Henleaze Lake"]})
WORDS = list(pr.LEVELS)


def test_prepare_checks():
    c = pd.DataFrame({"wqa_point": ["P1", "P1", "P1", "P1", "P1", "P9"],
                      "sample_time": pd.to_datetime(["2025-05-10 11:00", "2025-05-17 11:00", "2025-10-01 11:00",
                                                     "2026-05-09 11:00", "2026-05-16 11:00", "2025-06-01 11:00"]),
                      "result": [WORDS[2], "Something new", WORDS[3], WORDS[0], WORDS[1], WORDS[3]],
                      "purpose": ["MS"] * 6})
    out, dropped = pr.prepare_checks(c, SITES)
    assert dropped == 1                               # the unknown wording; October and the unmapped point go silently
    assert out["level"].tolist() == [2, 0, 1]
    assert out["prev"].tolist() == ["none", "none", "0"]   # a new season starts with 'none'
    assert out["A"].tolist() == [1, 0, 1] and out["B"].tolist() == [0, 0, 0]


def test_pairing_window():
    checks = pd.DataFrame({"bw_id": ["s1"] * 4, "date": pd.to_datetime(
        ["2025-07-10", "2025-07-20", "2025-07-30", "2025-08-15"]).date})
    scenes = pd.DataFrame({"bw_id": ["s1"] * 5, "item_id": list("abcde"), "reading": [0.1, 0.2, 0.3, 0.4, 0.5],
                           "scene_date": ["2025-07-07", "2025-07-09", "2025-07-16", "2025-07-31", "2025-08-15"]})
    items = lambda p: [x if isinstance(x, str) else None for x in p["scene_item"]]
    p = pr.pair(checks, scenes)
    assert items(p) == ["b", None, None, "e"]
    # 10 Jul takes 9 Jul (the latest, not 7 Jul); 20 Jul: 16 Jul is 4 days before; 30 Jul: 31 Jul is after
    assert p["lag_days"].tolist()[0] == 1 and p["lag_days"].tolist()[3] == 0
    p7 = pr.pair(checks, scenes, window_days=7)
    assert items(p7) == ["b", "c", None, "e"]
    p3 = pr.pair(checks.assign(date=pd.to_datetime(["2025-07-12"] * 4).date), scenes)
    assert p3["scene_item"].iloc[0] == "b"           # exactly 3 days before: in


def _rows_for_gate(events_by):
    r = []
    for (wb, season), n in events_by.items():
        r += [{"water_body": wb, "season": season, "A": 1}] * n + [{"water_body": wb, "season": season, "A": 0}] * 5
    return pd.DataFrame(r)


def test_gate_boundaries():
    ok = {("W1", 2020): 8, ("W2", 2021): 8, ("W3", 2023): 7, ("W4", 2024): 7}
    assert pr.gate(_rows_for_gate(ok), "A")["judged"]
    fewer = {**ok, ("W4", 2024): 6}                  # 29 events
    assert not pr.gate(_rows_for_gate(fewer), "A")["judged"]
    three_wb = {("W1", 2020): 10, ("W2", 2021): 10, ("W3", 2023): 10}
    assert not pr.gate(_rows_for_gate(three_wb), "A")["judged"]
    two_seasons = {("W1", 2020): 8, ("W2", 2020): 8, ("W3", 2021): 8, ("W4", 2023): 4, ("W4", 2024): 4}
    assert not pr.gate(_rows_for_gate(two_seasons), "A")["judged"]


@pytest.mark.parametrize("d,L,U,want", [
    (0.0036, 0.0001, 0.008, "Better"),
    (0.0035, 0.0001, 0.008, "Unlabelled"),          # positive and above zero but under B: no label fits
    (0.002, -0.0017, 0.005, "Promising, not shown"),
    (0.002, -0.0018, 0.005, "Too uncertain"),       # L at -H is not above -H
    (0.001, -0.001, 0.0035, "Promising, not shown"),
    (-0.0005, -0.0010, 0.0030, "No useful difference"),
    (-0.0005, -0.0020, 0.0030, "Possible harm"),
    (-0.0030, -0.0050, -0.0001, "Possible harm"),   # possible harm comes before harm in the order
    (0.001, -0.0050, -0.0001, "Harm"),
    (0.001, -0.0050, 0.0040, "Too uncertain"),
])
def test_label_boundaries(d, L, U, want):
    assert pr.label(d, L, U, *pr.MARGINS["A"]) == want


def test_promising_needs_no_secondary_harm():
    assert pr.label(0.002, -0.001, 0.003, *pr.MARGINS["A"]) == "Promising, not shown"
    assert pr.label(0.002, -0.001, 0.003, *pr.MARGINS["A"], secondary_harm=True) == "No useful difference"


# --- the placebo and the scoring, on synthetic rows --------------------------------------------------------------
WBS = ["Windermere", "Coniston Water", "Derwent Water", "Rutland Water", "Colwick Country Park, West Lake",
       "Frensham Great Pond"]


def synthetic_rows(day_signal: bool, seed: int = 1) -> pd.DataFrame:
    """About 1,300 checks at 6 water bodies, 2020-2026. Each water body has its own level of greenness and of algae.
    With day_signal the outcome also follows that day's reading; without, it follows the water body only."""
    rng = np.random.default_rng(seed)
    rows = []
    for k, wb in enumerate(WBS):
        base = -0.10 + 0.04 * k
        for season in pr.YEARS:
            for i in range(30):
                month = pr.SEASON_MONTHS[i % 5]
                day_part = rng.normal(0, 0.05)
                reading = base + day_part
                logit = -2.2 + 12 * (base + 0.1) + (25 * day_part if day_signal else 0)
                y = int(rng.random() < 1 / (1 + np.exp(-logit)))
                rows.append({"bw_id": f"{wb}-1", "water_body": wb, "season": season, "month": month,
                             "reading": reading, "A": y, "B": int(y and rng.random() < 0.3),
                             "prev": rng.choice(["none", "0", "1", "2", "3"]), "purpose": "MS"})
    return pd.DataFrame(rows)


def test_placebo_passes_with_day_signal_and_fails_without():
    with_day = synthetic_rows(True)
    real = pr.auc(with_day["reading"], with_day["A"])
    pl = pr.placebo_aucs(with_day, "A")
    assert pr.placebo_passes(real, pl)["passes"]
    lake_only = synthetic_rows(False)
    real0 = pr.auc(lake_only["reading"], lake_only["A"])
    assert real0 > 0.6                               # the readings still rank the outcome: greener lakes
    assert not pr.placebo_passes(real0, pr.placebo_aucs(lake_only, "A"))["passes"]


def test_placebo_is_reproducible_and_keeps_groups():
    r = synthetic_rows(True).iloc[:300]
    a, b = pr.placebo_aucs(r, "A", n=5), pr.placebo_aucs(r, "A", n=5)
    assert np.array_equal(a, b)


def test_score_outcome_end_to_end():
    rows = synthetic_rows(True)
    res = pr.score_outcome(rows, "A")
    assert res["gate"]["judged"]
    assert set(res["tables"]["LOWO"]) == {"R1", "R2", "M1", "M2"}
    assert res["primary"]["d"] > 0 and res["conditions"]["1"]["holds"] and res["conditions"]["4"]["holds"]
    assert set(res["groups"]) == {"Lake District", "lowland"}
    assert res["verdict"] in {"Passes", "Fails", "Promising, not shown: to the 2027 forward step"}
    none = pr.score_outcome(synthetic_rows(False), "A")
    assert not none["conditions"]["4"]["holds"] and none["verdict"] != "Passes"


def test_cluster_draws_are_whole_water_bodies():
    clusters = np.array(["a", "a", "b", "c", "c", "c"])
    for idx in pr.cluster_draws(clusters, n=20, seed=1):
        for k in "abc":
            n = (clusters[idx] == k).sum()
            assert n % (clusters == k).sum() == 0


def test_hold_out_never_sees_the_held_group():
    rows = synthetic_rows(True).iloc[::3].reset_index(drop=True)
    p = pr.hold_out(rows, "A", "water_body")
    # R1 for a held-out water body is the other water bodies' rate
    wb = WBS[0]
    want = rows.loc[rows.water_body != wb, "A"].mean()
    assert np.allclose(p.loc[rows.water_body == wb, "R1"], want)


def test_stage2_score_frames_on_synthetic_frames():
    sites = pd.DataFrame({"bw_id": ["s1", "s2", "s3"], "name": ["Windermere, Fellfoot", "Henleaze Lake",
                                                                 "Hampstead Heath (Ladies Pond)"],
                          "wqa_point": ["P1", "P2", "P3"],
                          "water_body": ["Windermere", "Henleaze Lake", "Hampstead Heath Ladies Pond"]})
    sizes = {"s1": {"in_test": True}, "s2": {"in_test": True}, "s3": {"in_test": False}}
    dates = pd.date_range("2025-05-05", "2025-09-25", freq="7D")
    checks = pd.DataFrame([{"wqa_point": p, "sample_time": d + pd.Timedelta(hours=11), "result": WORDS[i % 4],
                            "purpose": "MS"} for p in ("P1", "P2", "P3") for i, d in enumerate(dates)])
    feats = pd.DataFrame([{"bw_id": b, "water_body": "x", "tile": "T", "item_id": f"{b}-{d.date()}",
                           "scene_date": str((d - pd.Timedelta(days=1)).date()), "clear_core": 50, "n_core": 50,
                           "usable": True, "reading": 0.01 * i} for b in ("s1", "s2", "s3")
                          for i, d in enumerate(dates)])
    rep = stage2.score_frames(feats, checks, sites, sizes)
    assert rep["sites_in_test"] == ["s1", "s2"]
    assert rep["rows"] == 2 * len(dates)            # every check at the two sites in test has a scene 1 day before
    assert rep["gate"]["A"]["judged"] is False      # far too few
    assert set(rep["outcomes"]) == {"A", "B"} and rep["description"]["window_0"]["A"]["rows"] == 0


# --- stage 1 flow with the network replaced ---------------------------------------------------------------------
def test_stage1_geometry_and_readings(tmp_path, monkeypatch):
    items = [{"id": f"S2A_T30UVF_2025070{i}", "properties": {"grid:code": "MGRS-30UVF",
                                                              "datetime": f"2025-07-0{i}T11:00:00Z"},
              "assets": {"red": {"raster:bands": [{"scale": 1e-4, "offset": -0.1, "nodata": 0}]},
                         "rededge1": {"raster:bands": [{"scale": 1e-4, "offset": -0.1, "nodata": 0}]}}}
             for i in range(1, 8)]
    st = stack(n=7, cloudy=2)
    scl = {it["id"]: (st[i], CENTRE) for i, it in enumerate(items)}
    geom = stage1.site_geometry(items, scl)
    assert geom["MGRS-30UVF"]["passes"] and geom["MGRS-30UVF"]["items"] == 7
    calls = []

    def fake_bands(_net, it, lon, lat):
        calls.append(it["id"])
        return np.full((2 * N, 2 * N), 1300, np.uint16), np.full((N, N), 1500, np.uint16)   # 0.03 and 0.05

    monkeypatch.setattr(stage1.stac, "site_bands", fake_bands)
    site = SimpleNamespace(bw_id="s1", water_body="Windermere", lon=0.0, lat=0.0)
    rows = stage1.readings(None, tmp_path, site, items, scl, geom)
    assert [r["usable"] for r in rows] == [False, False, True, True, True, True, True]
    assert len(calls) == 5                            # B4 and B5 only for usable scenes
    assert rows[2]["reading"] == pytest.approx((0.05 - 0.03) / (0.05 + 0.03))
    again = stage1.readings(None, tmp_path, site, items, scl, geom)   # resumes from progress.jsonl, no reads
    assert len(calls) == 5 and again == rows


# --- the COG reader -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("dtype,big,pred,deflate", [(np.uint8, False, 2, True), (np.uint16, True, 2, True),
                                                    (np.uint16, False, 1, False), (np.uint8, True, 1, True)])
def test_cog_window_round_trip(dtype, big, pred, deflate):
    a = np.random.default_rng(0).integers(1, np.iinfo(dtype).max, size=(37, 45)).astype(dtype)
    b = cog.write_tiff(a, tile=16, predictor=pred, deflate=deflate, big=big)
    seen = []
    fetch = lambda s, e: (seen.append((s, e)), b[s:e + 1])[1]
    g = cog.open_cog(fetch)
    w = cog.read_window(g, fetch, -3, 40, 5, 50)
    want = np.zeros((43, 45), dtype)
    want[3:40, :40] = a[:, 5:45]
    assert (w == want).all()
    assert len(seen) <= 1 + 9                         # the header, then at most one range per tile


def test_cog_refuses_what_it_cannot_read():
    b = bytearray(cog.write_tiff(np.zeros((16, 16), np.uint8), tile=16))
    i = b.find(bytes([0x03, 0x01, 0x03, 0x00]))       # tag 259 (compression), type SHORT
    b[i + 8:i + 10] = (5).to_bytes(2, "little")       # LZW
    with pytest.raises(cog.Unsupported):
        cog.parse(bytes(b))
    with pytest.raises(cog.Unsupported):
        cog.parse(b"MM\x00*" + bytes(20))


def test_cog_sparse_tile_reads_as_nodata():
    g = cog.Cog(16, 16, 16, 16, np.dtype("<u1"), 8, 2, np.array([0]), np.array([0]), 0.0)
    assert (cog.read_window(g, lambda s, e: b"", 0, 4, 0, 4) == 0).all()


# --- the caps -----------------------------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, status, body=b"{}"):
        self.status_code, self.body = status, body

    def iter_bytes(self, n):
        for i in range(0, len(self.body), n):
            yield self.body[i:i + n]


class FakeClient:
    def __init__(self, statuses, body=b"{}"):
        self.statuses, self.body, self.calls = list(statuses), body, []

    @contextlib.contextmanager
    def stream(self, method, url, headers=None, json=None):
        self.calls.append((method, url, headers))
        yield FakeResponse(self.statuses.pop(0), self.body)


URL = "https://earth-search.aws.element84.com/v1/search"


@pytest.mark.parametrize("status", [429, 500, 503, 403, 404])
def test_caps_stop_on_bad_status(status, tmp_path):
    c = net.Capped(ledger=tmp_path / "l.jsonl", client=FakeClient([status]), sleep=lambda s: None)
    with pytest.raises(net.Stop):
        c.get_json(URL)
    assert (tmp_path / "l.jsonl").read_text().count("\n") == 1


def test_caps_requests_bytes_hosts_and_credentials(tmp_path):
    sleeps = []
    c = net.Capped(ledger=tmp_path / "l.jsonl", client=FakeClient([200] * 5), sleep=sleeps.append, max_requests=3)
    for _ in range(3):
        c.get_json(URL)
    with pytest.raises(net.CapReached):
        c.get_json(URL)
    assert len(sleeps) == 2 and all(0 < s <= net.PAUSE_S for s in sleeps)
    c2 = net.Capped(client=FakeClient([200], body=b"x" * 1000), sleep=lambda s: None, max_bytes=500)
    with pytest.raises(net.CapReached):
        c2.request("GET", URL)
    c3 = net.Capped(client=FakeClient([200]), sleep=lambda s: None)
    with pytest.raises(net.CapReached):
        c3.request("GET", "https://example.com/x")
    with pytest.raises(net.CapReached):
        c3.request("GET", "http://earth-search.aws.element84.com/v1/search")
    with pytest.raises(net.CapReached):
        c3.request("GET", URL, headers={"Authorization": "Bearer t"})
    # the cap over all runs reads the ledger: 3 requests already written
    c4 = net.Capped(ledger=tmp_path / "l.jsonl", client=FakeClient([200] * 5), sleep=lambda s: None,
                    max_requests_total=4)
    c4.get_json(URL)
    with pytest.raises(net.CapReached):
        c4.get_json(URL)


# --- the CLMS rules (no CLMS file has been read; these fix the rules on synthetic arrays) ----------------------
def test_clms_site_pixels_need_a_core_pixel_within_300_m():
    m = pr.water_mask(stack())
    piece, site = pr.site_water(m, CENTRE)
    core = pr.core_pixels(piece, site)
    centres = np.array([[20.5, 20.5], [20.5, 3.5], [8.6, 14.5], [35.0, 35.0], [-2.0, 5.0], [4.5, 35.5]])
    got = pr.clms_site_pixels(centres, core, CENTRE)
    # the point; a lake pixel 340 m away (too far); a shore pixel (not core); land; off the window; the pond
    assert got.tolist() == [True, False, False, False, False, False]


def test_clms_flags_come_from_the_file():
    meanings = ["L1_invalid", "bright_pixels", "cloud", "snow_ice", "land", "turbidity_invalid", "chla_invalid",
                "tsm_invalid", "atmospheric_correction_failure", "floating_cyanobacteria",
                "floating_macrophytes_or_mixed_pixel"]
    masks = [1 << i for i in range(len(meanings))]
    flags = np.array([0, 1 << 2, 1 << 9, 1 << 5, (1 << 9) | (1 << 4)])
    assert pr.clms_flag_invalid(flags, meanings, masks).tolist() == [False, True, False, False, True]
    with pytest.raises(pr.StopRule):
        pr.clms_flag_invalid(flags, meanings[:-1], masks[:-1])


def test_clms_dekad_reading_needs_three_valid_pixels():
    counted = np.array([True, True, True, True, False])
    invalid = np.array([False, False, True, False, False])
    n, v = pr.clms_dekad_reading(np.array([10.0, 100.0, 5.0, 1000.0, 7.0]), invalid, counted)
    assert n == 3 and v == pytest.approx(2.0)
    n, v = pr.clms_dekad_reading(np.array([10.0, np.nan, 5.0, 1000.0, 7.0]), invalid, counted)
    assert n == 2 and np.isnan(v)


def test_clms_pairing_waits_for_publication():
    assert pr.dekad_end("2025-06-21") == pd.Timestamp("2025-06-30")
    assert pr.dekad_end("2025-07-11") == pd.Timestamp("2025-07-20")
    dek = pd.DataFrame({"bw_id": ["s1"] * 3, "start": pd.to_datetime(["2025-07-01", "2025-07-11", "2025-07-21"]),
                        "reading": [1.0, 2.0, np.nan]})
    checks = pd.DataFrame({"bw_id": ["s1"] * 4, "date": pd.to_datetime(
        ["2025-07-13", "2025-07-14", "2025-07-25", "2025-08-20"]).date})
    p = pr.clms_pair(checks, dek)
    # 13 Jul: 1-10 Jul is ready on 14 Jul, so nothing; 14 Jul: that one; 25 Jul: 11-20 Jul (ready 24 Jul);
    # 20 Aug: still 11-20 Jul, as the 21-31 Jul dekad has no reading
    assert np.isnan(p["reading"].iloc[0]) and p["reading"].tolist()[1:] == [1.0, 2.0, 2.0]


def test_clms_decision_rule():
    starts = [pd.Timestamp(f"2025-{m:02d}-{d:02d}") for m in range(5, 10) for d in (1, 11, 21)]
    rows = []
    for k, wb in enumerate(["W1", "W2", "W3", "W4", "W5"]):
        for i, s in enumerate(starts):
            usable = i < (8 if k < 4 else 7)          # W5: 7 usable dekads, one short
            rows.append({"bw_id": f"{wb}-1", "water_body": wb, "start": s, "n_pixels": 3,
                         "reading": 1.0 if usable else np.nan})
    d = pd.DataFrame(rows)
    r = pr.clms_covers(d)
    assert r["covered_water_bodies"] == ["W1", "W2", "W3", "W4"] and r["primary"]
    r2 = pr.clms_covers(d.assign(n_pixels=np.where(d["water_body"] == "W1", 2, 3)))
    assert r2["covered_water_bodies"] == ["W2", "W3", "W4"] and not r2["primary"]


def test_clms_gate_needs_2025_and_2026():
    ok = {("W1", 2025): 8, ("W2", 2025): 8, ("W3", 2026): 7, ("W4", 2026): 7}
    assert pr.clms_gate(_rows_for_gate(ok), "A")["judged"]
    only_2025 = {("W1", 2025): 8, ("W2", 2025): 8, ("W3", 2025): 7, ("W4", 2024): 7}
    assert not pr.clms_gate(_rows_for_gate(only_2025), "A")["judged"]


def test_wider_intervals_when_clms_is_judged():
    rows = synthetic_rows(True).iloc[::2].reset_index(drop=True)
    a = pr.score_outcome(rows, "A")["primary"]
    b = pr.score_outcome(rows, "A", levels=(pr.LO4, pr.HI4))["primary"]
    assert b["L"] <= a["L"] and b["U"] >= a["U"] and a["d"] == b["d"]


# --- A1: parallel range reads from the COG buckets (26 October 2026) ----------------------------------------
S3 = "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/x.tif"


class ThreadSafeFake(FakeClient):
    def __init__(self, n, status=200):
        import threading
        super().__init__([status] * n)
        self._l = threading.Lock()

    @contextlib.contextmanager
    def stream(self, method, url, headers=None, json=None):
        with self._l:
            self.calls.append((method, url, headers))
            st = self.statuses.pop(0)
        yield FakeResponse(st, self.body)


def test_bucket_reads_unpaced_search_paced(tmp_path):
    sleeps = []
    c = net.Capped(ledger=tmp_path / "l.jsonl", client=FakeClient([200] * 6), sleep=sleeps.append)
    for _ in range(3):
        c.request("GET", S3)
    assert sleeps == []
    for _ in range(3):
        c.get_json(URL)
    assert len(sleeps) >= 2 and all(0 < s <= net.PAUSE_S for s in sleeps)


def test_parallel_requests_all_counted_and_capped(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    c = net.Capped(ledger=tmp_path / "l.jsonl", client=ThreadSafeFake(200), sleep=lambda s: None, max_requests=150)
    ok, capped = 0, 0

    def go(_):
        try:
            c.request("GET", S3)
            return 1
        except net.CapReached:
            return 0

    with ThreadPoolExecutor(net.WORKERS) as ex:
        res = list(ex.map(go, range(200)))
    ok, capped = sum(res), len(res) - sum(res)
    assert ok == 150 and capped == 50 and c.requests == 150
    assert (tmp_path / "l.jsonl").read_text().count("\n") == 150


def test_pmap_stops_starting_new_calls_after_an_error():
    import threading
    import time as _t
    started, lock = [], threading.Lock()

    def fn(i):
        with lock:
            started.append(i)
        if i == 3:
            raise net.Stop("HTTP 429")
        _t.sleep(0.02)
        return i

    with pytest.raises(net.Stop):
        list(stage1.pmap(fn, range(500)))
    # only calls already running when the error surfaced may have started
    assert len(started) < 3 * net.WORKERS


def test_pmap_keeps_order():
    assert list(stage1.pmap(lambda i: i * i, range(50))) == [i * i for i in range(50)]


def test_byte_cap_reached_refuses_the_next_request_before_it_starts(tmp_path):
    led = tmp_path / "l.jsonl"
    led.write_text('{"bytes": 1000}\n')
    client = FakeClient([200] * 3, body=b"x" * 10)
    c = net.Capped(ledger=led, client=client, sleep=lambda s: None, max_bytes_total=1000)
    with pytest.raises(net.CapReached, match="over all runs"):
        c.request("GET", S3)
    assert client.calls == []          # nothing was sent
    c2 = net.Capped(client=FakeClient([200] * 3, body=b"x" * 10), sleep=lambda s: None, max_bytes=10)
    c2.request("GET", S3)
    with pytest.raises(net.CapReached, match="per run"):
        c2.request("GET", S3)


def test_fetch_asks_one_sampling_point_at_a_time(tmp_path, monkeypatch):
    import dipcast.ingest.wqa as wqa
    calls = []

    def fake(points, since):
        calls.append(list(points))
        return [{"wqa_point": points[0], "sample_time": "2025-07-01T10:00:00", "result": "No material present",
                 "purpose": "MS"}]

    monkeypatch.setattr(wqa, "fetch_algae", fake)
    (tmp_path / "features.parquet").write_bytes(b"x")
    stage2.fetch(tmp_path, pr.sha256(tmp_path / "features.parquet"))
    assert all(len(c) == 1 for c in calls) and len(calls) == 18
    assert len(pd.read_parquet(tmp_path / "checks.parquet")) == 18
