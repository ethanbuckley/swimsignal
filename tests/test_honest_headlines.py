"""The build's side of the 11 Oct 2026 headline fixes (tests/site_honest_headlines.test.cjs has the page's):
how much of the traced river is in Wales, which gauge a lake keeps, and the E. coli estimate's record."""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import LineString, Point, box

from dipcast.model import forecast
from dipcast.network import nations

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


# ------------------------------------------------------------------ overflows in Wales
class Net:
    """The two things nations.py asks of a river network: links with lines, and the links upstream."""

    def __init__(self, lines: dict[str, LineString], up: dict[str, float]):
        self.links = gpd.GeoDataFrame({"length": [g.length for g in lines.values()]}, geometry=list(lines.values()),
                                      index=list(lines.keys()), crs=27700)
        self.up = up

    def upstream_edges(self, node, cap_m):
        return {k: v for k, v in self.up.items() if v <= cap_m}


def test_the_share_of_the_traced_river_in_wales_is_by_length_and_leaves_out_joins():
    wales = box(0, 0, 1000, 1000)
    net = Net({"a": LineString([(500, 500), (1500, 500)]),    # half in
               "b": LineString([(2000, 0), (3000, 0)]),        # out
               "c": LineString([(100, 100), (100, 1100)])},    # 900 of 1000 in
              {"a": 0.0, "b": 1000.0, "c": 2000.0, "repair:x": 50.0})
    assert nations.wales_share(net, ["a", "b", "c", "repair:x"], wales) == pytest.approx((500 + 900) / 3000)
    assert nations.wales_share(net, ["b"], wales) == 0.0
    assert nations.wales_share(net, [], wales) == 0.0
    assert nations.traced_wales_share(net, "n", 60, wales) == 0.47
    assert nations.traced_wales_share(net, "n", 1.5, wales) == 0.25   # within the cap, a and b: 500 of 2000 m
    assert nations.traced_wales_share(net, None, 60, wales) is None


def test_the_wales_outline_is_wales_and_not_england_or_scotland():
    wales = nations.wales_outline()
    to = Transformer.from_crs(4326, 27700, always_xy=True).transform
    inside = lambda lon, lat: wales.covers(Point(*to(lon, lat)))
    assert inside(-3.40, 52.15)        # Builth Wells, on the Wye
    assert inside(-3.25, 52.65)        # Welshpool, on the Severn
    assert not inside(-2.72, 52.05)    # Hereford
    assert not inside(-2.89, 53.19)    # Chester, Sandy Lane
    assert not inside(-3.19, 55.95)    # Edinburgh: Scotland's polygons are left out


def test_a_forecast_carries_the_share_only_where_some_of_its_river_is_in_wales(monkeypatch):
    pin = type("Pin", (), {"trace_node": "n"})()
    monkeypatch.setattr(forecast, "traced_wales_share", lambda net, node, km: 0.29)
    assert forecast._in_wales(None, pin, 60) == {"wales_share": 0.29}
    monkeypatch.setattr(forecast, "traced_wales_share", lambda net, node, km: 0.0)
    assert forecast._in_wales(None, pin, 60) == {}

    def broken(*a):
        raise OSError("no outline")
    monkeypatch.setattr(forecast, "traced_wales_share", broken)
    assert forecast._in_wales(None, pin, 60) == {}   # a label beside the forecast never fails it


# ------------------------------------------------------------------ a lake's gauge
def test_a_lake_keeps_only_a_gauge_on_the_lake_itself():
    bs = _build_site()
    gauge = lambda river: {"station": "S", "river": river, "level_m": 0.7, "stale": False, "same_river": None}
    lake = lambda name, watercourse=None: {"name": name, "kind": "lake", "location": {"mode": "lake", "watercourse": watercourse}}
    kept = bs.lake_gauge(lake("Windermere, Millerground Landing", "Windermere (N Basin)"), gauge("Windermere"))
    assert kept["water"] == "lake" and kept["same_river"] is True
    assert bs.lake_gauge(lake("Coniston Water, Brown Howe", "Coniston Water"), gauge("Coniston Water"))["water"] == "lake"
    assert bs.lake_gauge(lake("Derwent Water at Crow Park", "Derwent Water"), gauge("River Derwent")) is None   # the river below it
    assert bs.lake_gauge(lake("Loughrigg Tarn"), gauge("River Brathay")) is None
    assert bs.lake_gauge(lake("The Serpentine - Hyde Park"), gauge("River Wandle")) is None
    assert bs.lake_gauge(lake("Hampstead Heath (Ladies Pond)"), gauge("Mutton Brook")) is None
    assert bs.lake_gauge({"name": "Loughrigg Tarn", "kind": "lake", "location": {"mode": "isolated"}}, gauge("River Brathay")) is None
    river = {"name": "River Wharfe, Ilkley", "kind": "river", "location": {"mode": "river", "watercourse": "River Wharfe"}}
    assert bs.lake_gauge(river, gauge("River Wharfe")) == gauge("River Wharfe")   # a river spot as before
    assert bs.lake_gauge(river, None) is None


# ------------------------------------------------------------------ the E. coli estimate's record
LIVE = {"ecoli_live": {"n_samples": 37, "n_sites": 26,
                       "overall": {"brier": 0.10710672, "climatology_brier": 0.103932754, "auc": 0.5177777, "base_rate": 0.1}}}


def test_the_e_coli_record_is_read_from_the_scores_and_says_no_skill_until_it_beats_the_samples_own_rate():
    bs = _build_site()
    out = bs.ecoli_check(LIVE)
    assert out["live"] == {"n_samples": 37, "n_sites": 26, "auc": 0.52, "brier": 0.107, "climatology_brier": 0.104, "skill": False}
    assert out["wales"]["n_samples"] == 185 and out["wales"]["mean"] == 0.324 and out["wales"]["observed"] == 0.059
    better = {"ecoli_live": {**LIVE["ecoli_live"], "overall": {"brier": 0.08, "climatology_brier": 0.10, "auc": 0.71}}}
    assert bs.ecoli_check(better)["live"]["skill"] is True
    ranks = {"ecoli_live": {**LIVE["ecoli_live"], "overall": {"brier": 0.08, "climatology_brier": 0.10, "auc": 0.55}}}
    assert bs.ecoli_check(ranks)["live"]["skill"] is False   # better calibrated, but no better than chance at ranking
    assert "live" not in bs.ecoli_check({"ecoli_live": None})
    assert "live" not in bs.ecoli_check({"ecoli_live": {"n_samples": 0, "overall": {}}})


# ------------------------------------------------------------------ the history page's distances
def test_the_history_page_puts_an_overflow_in_the_same_lake_across_it():
    from dipcast import profile
    t = pd.DataFrame({"site_id": ["UUP00804", "UUP00114"], "site_name": ["Glebe Road PS", "AMBLESIDE WwTW"],
                      "company": ["United Utilities", "Dwr Cymru Welsh Water"], "distance_km": [0.0, 1.4], "lake_distance_km": [2.6, 5.2],
                      "travel_h": [14.3, 29.9], "weight": [0.117, 0.012], "has_live": [True, True], "lta_spills": [3.0, 20.0],
                      "spill_hours": [10.0, 200.0]})
    assert list(profile.in_lake(t)) == [True, False]
    s = profile.in_short(profile.with_returns(t, wide=profile.yearly(pd.DataFrame(columns=profile.RETURN_FIELDS))))
    assert s["nearest_km"] == pytest.approx(2.6) and s["nearest_in_lake"] is True
    page = profile.body({"id": "bw-ukd1203-45650", "name": "Windermere, Millerground Landing", "upstream_summary": {"overflows": 2}},
                        profile.with_returns(t, wide=profile.yearly(pd.DataFrame(columns=profile.RETURN_FIELDS))))
    assert "The nearest is 2.6&nbsp;km away, across the lake." in page
    assert "2.6 across the lake" in page and "Dŵr Cymru Welsh Water" in page and "Dwr Cymru" not in page
    assert "across a lake at its slower lake speed" in page
