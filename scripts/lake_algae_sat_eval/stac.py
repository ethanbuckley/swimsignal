"""Earth Search (sentinel-2-c1-l2a) searches and windowed reads at a site, every request through net.Capped."""

from __future__ import annotations

import numpy as np

import cog
from protocol import COMPONENT_RADIUS_M, PIXEL_M

SEARCH = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-c1-l2a"
PAGE = 250


def search(net, lon: float, lat: float, start: str, end: str, fields: dict | None = None,
           query: dict | None = None) -> list[dict]:
    """Every item whose footprint holds the point, start to end (ISO dates, inclusive), following 'next' links."""
    body = {"collections": [COLLECTION], "intersects": {"type": "Point", "coordinates": [lon, lat]},
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": PAGE}
    if fields:
        body["fields"] = fields
    if query:
        body["query"] = query
    items, url, method = [], SEARCH, "POST"
    while True:
        page = net.post_json(url, body) if method == "POST" else net.get_json(url)
        items.extend(page.get("features", []))
        nxt = next((link for link in page.get("links", []) if link.get("rel") == "next"), None)
        # Earth Search gives a 'next' link even on a short last page; a short page is the end.
        if not nxt or len(page.get("features", [])) < PAGE:
            return items
        url, method = nxt["href"], nxt.get("method", "GET").upper()
        if method == "POST":
            body = {**body, **nxt.get("body", {})} if nxt.get("merge") else nxt.get("body", body)


def window_for(item: dict, asset: str, lon: float, lat: float, radius_m: float = COMPONENT_RADIUS_M):
    """(row0, row1, col0, col1, centre_rc) of the square of radius_m around the point on the asset's grid. centre_rc
    is the point in fractional pixel coordinates of that window."""
    from pyproj import Transformer
    epsg = item["properties"].get("proj:epsg") or int(str(item["properties"]["proj:code"]).split(":")[1])
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
    t = item["assets"][asset]["proj:transform"]
    res = abs(t[0])
    col_f, row_f = (x - t[2]) / t[0], (y - t[5]) / t[4]
    n = int(np.ceil(radius_m / res))
    r0, c0 = int(np.floor(row_f)) - n, int(np.floor(col_f)) - n
    return r0, r0 + 2 * n + 1, c0, c0 + 2 * n + 1, (row_f - r0, col_f - c0)


def read(net, item: dict, asset: str, r0: int, r1: int, c0: int, c1: int) -> np.ndarray:
    url = item["assets"][asset]["href"]
    fetch = lambda s, e: net.get_range(url, s, e)
    return cog.read_window(cog.open_cog(fetch), fetch, r0, r1, c0, c1)


def site_scl(net, item: dict, lon: float, lat: float):
    r0, r1, c0, c1, centre = window_for(item, "scl", lon, lat)
    return read(net, item, "scl", r0, r1, c0, c1), centre


def site_bands(net, item: dict, lon: float, lat: float) -> tuple[np.ndarray, np.ndarray]:
    """B4 (10 m, read on the matching 10 m window) and B5 (20 m), raw DN, aligned to the SCL window."""
    r0, r1, c0, c1, _ = window_for(item, "scl", lon, lat)
    t20, t10 = item["assets"]["scl"]["proj:transform"], item["assets"]["red"]["proj:transform"]
    if (t20[2], t20[5]) != (t10[2], t10[5]) or abs(t10[0]) * 2 != abs(t20[0]) or abs(t20[0]) != PIXEL_M:
        raise ValueError(f"{item['id']}: B4 and SCL grids do not nest")
    b4 = read(net, item, "red", 2 * r0, 2 * r1, 2 * c0, 2 * c1)
    b5 = read(net, item, "rededge1", r0, r1, c0, c1)
    return b4, b5
