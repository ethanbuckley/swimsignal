"""Sewage overflows near each English coastal bathing water, and which reported a spill in the last 48 hours.

An observation from the companies' live feeds, beside the EA's own information on the coverage page. It is not a
forecast, not a water test and not the EA's advice: it says what the monitors reported, not how much came out or
where it went.

Which overflows count is the coastal baselines' rule (docs/COASTAL-BASELINES-2026-11.md, section 4, #692), with
its two outer groups joined: within NEAR_KM of the EA's sampling point in a straight line, or on a river from which
the network runs downstream, within RIVER_MAX_KM, to a network node within RIVER_NODE_KM of the sampling point.
#692 kept a 2 to 5 km ring apart for its spill test; a ring overflow not on such a river is left out here, as the
row says "near or upstream of the sampling point". Overflow positions are the overflow table's, which are often not where the
pipe comes out (docs/OVERFLOW-SEA-OUTFALLS-2026-10.md), so the link is a rough one, and the page says so."""

from __future__ import annotations

import numpy as np
import pandas as pd

NEAR_KM = 2.0
RIVER_NODE_KM = 2.0
RIVER_MAX_KM = 30.0
WINDOW_H = 48


def _bng(lon, lat):
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
    return t.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))


def river_links(net, xy: dict[str, tuple[float, float]]) -> dict[str, set]:
    """For each site (British National Grid x, y), the river links from which the network runs downstream, within
    RIVER_MAX_KM, to a node within RIVER_NODE_KM of it (the walk in scripts/coastal_baselines/build.py)."""
    from scipy.spatial import cKDTree
    pts = net.node_points()
    nodes = np.array(pts.index)
    tree = cKDTree(np.c_[pts.x.to_numpy(), pts.y.to_numpy()])
    g, cap, out = net.graph, RIVER_MAX_KM * 1000, {}
    for sid, (x, y) in xy.items():
        start = nodes[tree.query_ball_point([x, y], RIVER_NODE_KM * 1000)]
        dist = {n: 0.0 for n in start}
        links: set = set()
        stack = list(start)
        while stack:
            n = stack.pop()
            for pred in g.predecessors(n):
                ed = g.edges[pred, n]
                links.add(ed["link"])
                d = dist[n] + ed["length"]
                if d <= cap and d < dist.get(pred, np.inf):
                    dist[pred] = d
                    stack.append(pred)
        out[sid] = links
    return out


def link(points: dict[str, tuple[float, float]], ov: pd.DataFrame, net=None) -> dict[str, list]:
    """Each site's overflows, as index labels of `ov` (lat, lon, and link_id and snap_confidence for the river
    group). `points` is {site id: (lat, lon)}. Without `net`, the straight-line group alone."""
    if ov.empty or not points:
        return {sid: [] for sid in points}
    ok = ov["lat"].notna() & ov["lon"].notna()
    ov = ov[ok]
    ox, oy = _bng(ov["lon"], ov["lat"])
    sx, sy = _bng([p[1] for p in points.values()], [p[0] for p in points.values()])
    xy = dict(zip(points, zip(sx, sy)))
    rl = river_links(net, xy) if net is not None else {}
    on_net = ov["link_id"].notna() & ~ov.get("snap_confidence", pd.Series(None, index=ov.index)).isin(["marine", "ground"]) \
        if "link_id" in ov else pd.Series(False, index=ov.index)
    by_link = ov[on_net].groupby("link_id").groups if on_net.any() else {}
    labels = ov.index
    out = {}
    for sid, (x, y) in xy.items():
        mask = np.hypot(ox - x, oy - y) <= NEAR_KM * 1000
        river = [i for lid in rl.get(sid, ()) if lid in by_link for i in by_link[lid]]
        if river:
            mask |= labels.isin(river)
        out[sid] = labels[mask].tolist()   # in the table's order
    return out


def summarise(ov: pd.DataFrame, now: pd.Timestamp) -> dict:
    """What the overflows in `ov` reported: how many there are, how many report live, and which spilled in the
    WINDOW_H hours to `now` (a spill running at the last poll, counted as forecast.live_counts does whatever the
    feed's state, or one that ended inside the window). A quiet overflow counts as reporting only on a current
    feed (data_state live): a stale, offline or unfed monitor cannot say there was no spill."""
    from dipcast.ingest.live import LIVE
    from dipcast.model.transport import running
    if ov.empty:
        return {"overflows": 0, "reporting": 0, "spilled": 0, "running": 0}
    run = running(ov)
    end = pd.to_datetime(ov["latest_event_end"], utc=True, errors="coerce")
    start = pd.to_datetime(ov["latest_event_start"], utc=True, errors="coerce")
    since = now - pd.Timedelta(hours=WINDOW_H)
    ended = (end >= since) & (start <= now)
    spilled = run | ended.fillna(False).to_numpy(dtype=bool)
    live = (ov["data_state"] == LIVE).to_numpy(dtype=bool) if "data_state" in ov else np.zeros(len(ov), bool)
    ids = ov.loc[spilled, "site_id"].astype(str).tolist() if "site_id" in ov else []
    return {"overflows": int(len(ov)), "reporting": int((live | spilled).sum()), "spilled": int(spilled.sum()),
            "running": int(run.sum()), "spilled_ids": ids}


def attach(sites: list[dict], points: dict, ov: pd.DataFrame, net, now: pd.Timestamp) -> dict:
    """Each English site with a sampling point gets `spills_nearby` ({window_h, to, overflows, reporting, spilled,
    running, spilled_ids}); one without gets none. Returns the build's health entry."""
    from dipcast.ingest.live import with_data_states
    ov = with_data_states(ov)
    pts = {s["id"]: (float(points[s["id"]][0]), float(points[s["id"]][1])) for s in sites if s.get("id") in points}
    groups = link(pts, ov, net)
    out = {"sites": 0, "with_overflows": 0, "with_spill": 0, "no_point": len(sites) - len(pts)}
    for s in sites:
        if s.get("id") not in groups:
            continue
        summary = summarise(ov.loc[groups[s["id"]]], now)
        s["spills_nearby"] = {"window_h": WINDOW_H, "to": now.isoformat(), **summary}
        out["sites"] += 1
        out["with_overflows"] += summary["overflows"] > 0
        out["with_spill"] += summary["spilled"] > 0
    return out


def line(site: dict) -> str:
    """One line under a site in the coverage page's directory, or '' when the build attached nothing."""
    from dipcast.coastal import when
    s = site.get("spills_nearby")
    if not s:
        return ''
    n, k = s["overflows"], s["spilled"]
    if not n:
        return 'No sewage overflow on our map near or upstream of the sampling point'
    to, h = when(s["to"]), s["window_h"]
    if n == 1:   # "none of 1" reads badly
        said = ('it is spilling at the last update' if s["running"] else f'it reported a spill in the {h} hours to {to}' if k
                else f'no spill reported in the {h} hours to {to}')
        unseen = '' if s["reporting"] else ', but it is not reporting live, so could have spilled unseen'
        return f'One sewage overflow near or upstream of the sampling point: {said}{unseen}'
    ran = f' ({s["running"]} still spilling at the last update)' if s["running"] else ''
    said = f'{k} of {n} reported a spill in the {h} hours to {to}{ran}' if k else f'none of {n} reported a spill in the {h} hours to {to}'
    reporting = ('' if s["reporting"] == n else
                 f'. {n - s["reporting"]} of them {"is" if n - s["reporting"] == 1 else "are"} not reporting live, '
                 'so could have spilled unseen')
    return f'Sewage overflows near or upstream of the sampling point: {said}{reporting}'


NOTE = ('<p class="small">"Sewage overflows near or upstream of the sampling point" are those within 2 km of the EA\'s sampling '
        'point, or upstream on a river that reaches within 2 km of it, up to 30 km along the river. A sewage overflow '
        'is a pipe that lets untreated sewage, mixed with rainwater, out when the sewers fill. The counts are what '
        'the water companies\' monitors reported: when a spill started and stopped, not how much came out or where '
        'it went. Not every overflow counted drains towards the beach, and some further away can matter. This is '
        'not a water test, a forecast or the EA\'s advice.</p>')
