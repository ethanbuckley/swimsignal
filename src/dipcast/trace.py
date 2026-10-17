"""The river a spot's forecast traces upstream, drawn on the spot's map (docs/REVIEW-2026-10-16.md, G6).

The forecast counts every monitored overflow on the river network within 60 km upstream of a spot
(transport.upstream_overflows). Reviewers asked why an overflow 40 km away counts, and a wrong trace
(Loughrigg Tarn's, say) is plain once it is drawn. So the build writes, for each spot, the lines of that
network (transport.traced_lines), joined where one runs into the next, simplified to SIMPLIFY_M and
written as Google encoded polylines (precision 5, about a metre) to keep the largest file small: on
the network of 11 Sep 2026 Warleigh Weir's 536 km of river came to about 3,300 points. index.html
decodes them (decodeLine).
"""

from __future__ import annotations

from dipcast import config
from dipcast.model.transport import locate_pin, spot_hints, traced_lines
from dipcast.network.rivers import _TO_WGS

SIMPLIFY_M = 25.0   # a pixel is 19 m at zoom 13 at 52°N, so the line keeps its shape where it is drawn


def encode(points) -> str:
    """Google's encoded polyline (developers.google.com/maps/documentation/utilities/polylinealgorithm)
    of (lat, lon) points, at five decimal places."""
    out, plat, plon = [], 0, 0
    for lat, lon in points:
        ilat, ilon = round(lat * 1e5), round(lon * 1e5)
        for d in (ilat - plat, ilon - plon):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


def decode(s: str) -> list[tuple[float, float]]:
    """The points of an encoded polyline, (lat, lon): encode's inverse, for the tests."""
    pts, i, lat, lon = [], 0, 0, 0
    while i < len(s):
        vals = []
        for _ in range(2):
            shift = res = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                res |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            vals.append(~(res >> 1) if res & 1 else res >> 1)
        lat, lon = lat + vals[0], lon + vals[1]
        pts.append((lat / 1e5, lon / 1e5))
    return pts


def encoded_lines(lines, tolerance_m: float = SIMPLIFY_M) -> list[str]:
    """Lines in EPSG:27700, joined end to end where they meet without a fork (shapely linemerge),
    simplified, and encoded. A line that simplifies to a point is dropped."""
    from shapely.geometry import MultiLineString
    from shapely.ops import linemerge
    if not lines:
        return []
    merged = linemerge(MultiLineString(lines))
    out = []
    for part in getattr(merged, "geoms", [merged]):
        xy = list(part.simplify(tolerance_m).coords)
        if len(xy) < 2:
            continue
        lon, lat = _TO_WGS.transform([p[0] for p in xy], [p[1] for p in xy])
        out.append(encode(zip(lat, lon, strict=True)))
    return out


def spot_trace(net, lat: float, lon: float, kind=None, river=None, name: str | None = None,
               max_km: float = config.MAX_UPSTREAM_KM) -> list[str]:
    """The encoded lines of what the forecast traces upstream of a listed spot, placed as forecast_point
    places it (the same hints from spots.csv)."""
    kind_hint, river_hint = spot_hints(kind, river)
    pin = locate_pin(net, lon, lat, kind_hint=kind_hint, river_hint=river_hint, name=name)
    return encoded_lines(traced_lines(net, pin, max_km))
