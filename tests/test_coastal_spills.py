"""Sewage overflows near each coastal bathing water (coastal_spills): which count, what they reported, the row's words."""

import geopandas as gpd
import networkx as nx
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point

from dipcast import coastal, coastal_spills

TO_BNG = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
TO_LL = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
SITE = (50.79, -0.98)                       # a point on the Hampshire coast
SX, SY = TO_BNG.transform(SITE[1], SITE[0])
NOW = pd.Timestamp("2026-11-21T22:46:00Z")


def ll(dx_m, dy_m):
    lon, lat = TO_LL.transform(SX + dx_m, SY + dy_m)
    return lat, lon


class Net:
    """A river running south to the coast: n3 (25 km north) -> n2 (12 km) -> n1 (1 km north of the site), links r3,
    r2; and a river that ends 8 km east of the site, link e1, whose water never comes near it."""
    def __init__(self):
        self.pos = {"n1": (SX, SY + 1000), "n2": (SX, SY + 12000), "n3": (SX, SY + 25000), "n4": (SX, SY + 45000),
                    "e0": (SX + 8000, SY), "e1": (SX + 8000, SY + 6000)}
        self.graph = nx.DiGraph()
        for a, b, link in [("n2", "n1", "r2"), ("n3", "n2", "r3"), ("n4", "n3", "r4"), ("e1", "e0", "e1")]:
            (xa, ya), (xb, yb) = self.pos[a], self.pos[b]
            self.graph.add_edge(a, b, link=link, length=((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5)

    def node_points(self):
        return gpd.GeoSeries([Point(*p) for p in self.pos.values()], index=list(self.pos), crs=27700)


def overflows(rows):
    df = pd.DataFrame(rows)
    for col, default in [("link_id", None), ("snap_confidence", None), ("status", 0), ("data_state", "live"),
                         ("latest_event_start", None), ("latest_event_end", None)]:
        df[col] = df[col].where(df[col].notna(), default) if col in df else default
    return df


def place(site_id, dx, dy, **kw):
    lat, lon = ll(dx, dy)
    return {"site_id": site_id, "lat": lat, "lon": lon, **kw}


def test_near_group_is_two_km_in_a_straight_line():
    ov = overflows([place("A", 1500, 0), place("B", 0, -2500), place("C", -1900, 300)])
    got = coastal_spills.link({"s": SITE}, ov)["s"]
    assert ov.loc[got, "site_id"].tolist() == ["A", "C"]


def test_river_group_follows_the_network_down_to_the_beach_within_30_km():
    ov = overflows([
        place("UP12", 50, 12000, link_id="r2", snap_confidence="high"),     # on r2, 1 to 12 km up: counts
        place("UP25", 50, 25000, link_id="r3", snap_confidence="high"),     # on r3, 12 to 25 km up: counts
        place("UP45", 50, 44000, link_id="r4", snap_confidence="high"),     # r4 starts 25 km up the river: under 30, counts
        place("EAST", 8000, 5000, link_id="e1", snap_confidence="high"),    # another river: no
        place("SEA", 50, 12000, link_id="r2", snap_confidence="marine"),    # marine snap: not on the river
    ])
    got = coastal_spills.link({"s": SITE}, ov, Net())["s"]
    assert sorted(ov.loc[got, "site_id"]) == ["UP12", "UP25", "UP45"]


def test_river_walk_stops_past_30_km():
    net = Net()
    net.pos["n5"] = (SX, SY + 70000)
    net.graph.add_edge("n5", "n4", link="r5", length=25000)
    ov = overflows([place("FAR", 50, 60000, link_id="r5", snap_confidence="high")])
    assert coastal_spills.link({"s": SITE}, ov, net)["s"] == []


def test_summary_counts_running_and_recent_spills_and_who_can_see():
    ov = overflows([
        {"site_id": "RUN", "status": 1, "latest_event_start": "2026-11-21T20:00:00Z"},
        {"site_id": "ENDED", "latest_event_start": "2026-11-20T08:00:00Z", "latest_event_end": "2026-11-20T09:00:00Z"},
        {"site_id": "OLD", "latest_event_start": "2026-11-19T10:00:00Z", "latest_event_end": "2026-11-19T20:00:00Z"},
        {"site_id": "QUIET"},
        {"site_id": "STALE", "data_state": "stale"},
        {"site_id": "STALE_RUN", "data_state": "stale", "status": 1},
        {"site_id": "OFF", "data_state": "offline", "status": -1},
    ])
    s = coastal_spills.summarise(ov, NOW)
    assert s == {"overflows": 7, "reporting": 5, "spilled": 3, "running": 2,
                 "spilled_ids": ["RUN", "ENDED", "STALE_RUN"]}


def test_line_words():
    base = {"window_h": 48, "to": "2026-11-21T22:46:00+00:00"}
    assert coastal_spills.line({}) == ""
    assert coastal_spills.line({"spills_nearby": {**base, "overflows": 0, "reporting": 0, "spilled": 0, "running": 0}}) \
        == "No sewage overflow on our map near or upstream of the sampling point"
    quiet = coastal_spills.line({"spills_nearby": {**base, "overflows": 5, "reporting": 5, "spilled": 0, "running": 0}})
    assert quiet.startswith("Sewage overflows near or upstream of the sampling point: none of 5 reported a spill in the 48 hours to <time")
    assert "21 Nov 2026, 22:46" in quiet and "not reporting" not in quiet
    some = coastal_spills.line({"spills_nearby": {**base, "overflows": 7, "reporting": 5, "spilled": 3, "running": 1}})
    assert "3 of 7 reported a spill" in some and "(1 still spilling at the last update)" in some
    assert some.endswith(". 2 of them are not reporting live, so could have spilled unseen")
    one = coastal_spills.line({"spills_nearby": {**base, "overflows": 1, "reporting": 0, "spilled": 0, "running": 0}})
    assert one.startswith("One sewage overflow near or upstream of the sampling point: no spill reported in the 48 hours")
    assert one.endswith(", but it is not reporting live, so could have spilled unseen")
    one_ran = coastal_spills.line({"spills_nearby": {**base, "overflows": 1, "reporting": 1, "spilled": 1, "running": 1}})
    assert one_ran == "One sewage overflow near or upstream of the sampling point: it is spilling at the last update"


def test_attach_skips_sites_without_a_point_and_reports_counts():
    sites = [{"id": "s"}, {"id": "nowhere"}]
    ov = overflows([place("A", 500, 0, status=1, latest_event_start="2026-11-21T21:00:00Z"), place("B", 900, 0)])
    health = coastal_spills.attach(sites, {"s": list(SITE)}, ov, None, NOW)
    assert health == {"sites": 1, "with_overflows": 1, "with_spill": 1, "no_point": 1}
    assert sites[0]["spills_nearby"]["spilled_ids"] == ["A"] and sites[0]["spills_nearby"]["to"] == NOW.isoformat()
    assert "spills_nearby" not in sites[1]


def snapshot(sites):
    return {"fetched_at": "2026-11-21T22:00:00+00:00", "sites": sites}


def row(**kw):
    return {"id": "s", "name": "Hayling West", "kind": "coast", "profile": "https://example.org/p",
            "rating": {"value": "Good", "year": 2025}, "advice": {"state": "no_current_advice"}, **kw}


def test_render_shows_the_line_and_the_note_only_when_attached():
    near = {"window_h": 48, "to": "2026-11-21T22:46:00+00:00", "overflows": 4, "reporting": 4, "spilled": 1,
            "running": 0, "spilled_ids": ["X"]}
    with_spills = coastal.render(snapshot([row(spills_nearby=near)]))
    assert "1 of 4 reported a spill in the 48 hours to <time" in with_spills
    assert "within 2 km of the EA&#x27;s sampling point" not in with_spills   # the note is HTML we wrote, not escaped
    assert "within 2 km of the EA's sampling point" in with_spills and "not a water test, a forecast" in with_spills
    without = coastal.render(snapshot([row()]))
    assert "near or upstream of the sampling point" not in without
