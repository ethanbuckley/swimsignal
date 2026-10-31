"""A small reader for windows of a tiled GeoTIFF (a COG) over HTTP range requests, in numpy and zlib only.

It reads what the Earth Search Sentinel-2 files need: little-endian TIFF or BigTIFF, one band (uint8 or uint16) or
three pixel-interleaved uint8 bands (the true-colour TCI, #550), tiled, no compression or deflate, horizontal predictor
or none. Anything else raises Unsupported, so a file it cannot read
gives no reading rather than a wrong one. Every byte comes through the caller's `fetch(start, end)` (net.Capped), so
every byte is counted against the caps.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

import numpy as np

HEADER_BYTES = 16 * 1024
TYPES = {1: ("B", 1), 2: ("c", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 6: ("b", 1), 7: ("B", 1), 8: ("h", 2),
         9: ("i", 4), 11: ("f", 4), 12: ("d", 8), 16: ("Q", 8), 17: ("q", 8)}
MERGE_GAP = 16 * 1024   # tiles closer than this in the file are fetched in one range


class Unsupported(ValueError):
    pass


@dataclass
class Cog:
    width: int
    height: int
    tile_w: int
    tile_h: int
    dtype: np.dtype
    compression: int
    predictor: int
    offsets: np.ndarray
    counts: np.ndarray
    nodata: float | None
    samples: int = 1

    @property
    def tiles_across(self) -> int:
        return -(-self.width // self.tile_w)


def _read_ifd(buf: bytes, fetch, ifd_at: int, big: bool) -> dict[int, tuple]:
    def need(start: int, n: int) -> bytes:
        if start + n <= len(buf):
            return buf[start:start + n]
        return fetch(start, start + n - 1)

    if big:
        n = struct.unpack("<Q", need(ifd_at, 8))[0]
        entry, head, inline = 20, 8, 8
    else:
        n = struct.unpack("<H", need(ifd_at, 2))[0]
        entry, head, inline = 12, 2, 4
    raw = need(ifd_at + head, n * entry)
    tags = {}
    for i in range(n):
        e = raw[i * entry:(i + 1) * entry]
        tag, typ = struct.unpack("<HH", e[:4])
        count = struct.unpack("<Q", e[4:12])[0] if big else struct.unpack("<I", e[4:8])[0]
        val = e[12:20] if big else e[8:12]
        if typ not in TYPES:
            continue
        fmt, size = TYPES[typ]
        nbytes = size * count
        data = val[:nbytes] if nbytes <= inline else need(
            struct.unpack("<Q", val)[0] if big else struct.unpack("<I", val)[0], nbytes)
        if typ == 2:
            tags[tag] = (data.rstrip(b"\0").decode("ascii", "replace"),)
        elif typ == 5:
            tags[tag] = struct.unpack(f"<{2 * count}I", data)
        else:
            tags[tag] = struct.unpack(f"<{count}{fmt}", data)
    return tags


def parse(buf: bytes, fetch=None) -> Cog:
    """The first image of a TIFF from its first bytes; `fetch` gets anything the header points past them."""
    if buf[:2] != b"II":
        raise Unsupported("big-endian or not a TIFF")
    magic = struct.unpack("<H", buf[2:4])[0]
    if magic == 42:
        big, ifd_at = False, struct.unpack("<I", buf[4:8])[0]
    elif magic == 43:
        big, ifd_at = True, struct.unpack("<Q", buf[8:16])[0]
    else:
        raise Unsupported(f"TIFF magic {magic}")
    t = _read_ifd(buf, fetch, ifd_at, big)
    if 322 not in t or 324 not in t:
        raise Unsupported("not tiled")
    samples, planar = t.get(277, (1,))[0], t.get(284, (1,))[0]
    bits, fmt = t.get(258, (8,))[0], t.get(339, (1,))[0]
    if samples != 1 and not (samples == 3 and planar == 1 and bits == 8):
        raise Unsupported(f"{samples} bands, planar {planar}, {bits} bits")
    if fmt != 1 or bits not in (8, 16):
        raise Unsupported(f"sample format {fmt}, {bits} bits")
    comp, pred = t.get(259, (1,))[0], t.get(317, (1,))[0]
    if comp not in (1, 8, 32946) or pred not in (1, 2):
        raise Unsupported(f"compression {comp}, predictor {pred}")
    nodata = float(t[42113][0]) if 42113 in t and t[42113][0].strip() else None
    return Cog(t[256][0], t[257][0], t[322][0], t[323][0], np.dtype("<u1" if bits == 8 else "<u2"), comp, pred,
               np.asarray(t[324], dtype=np.int64), np.asarray(t[325], dtype=np.int64), nodata, samples)


def decode_tile(cog: Cog, data: bytes) -> np.ndarray:
    shape = (cog.tile_h, cog.tile_w) + ((cog.samples,) if cog.samples > 1 else ())
    if len(data) == 0:   # a sparse tile: GDAL writes none where every pixel is nodata
        return np.full(shape, cog.nodata or 0, dtype=cog.dtype)
    raw = zlib.decompress(data) if cog.compression in (8, 32946) else data
    a = np.frombuffer(raw, dtype=cog.dtype, count=int(np.prod(shape))).reshape(shape)
    if cog.predictor == 2:
        a = np.cumsum(a, axis=1, dtype=cog.dtype)   # per band, wrapping modulo the type, as the predictor does
    return a


def read_window(cog: Cog, fetch, row0: int, row1: int, col0: int, col1: int) -> np.ndarray:
    """Pixels [row0, row1) x [col0, col1), clipped to the image; outside it reads as nodata (or 0)."""
    out = np.full((row1 - row0, col1 - col0) + ((cog.samples,) if cog.samples > 1 else ()), cog.nodata or 0, dtype=cog.dtype)
    r0, r1, c0, c1 = max(row0, 0), min(row1, cog.height), max(col0, 0), min(col1, cog.width)
    if r0 >= r1 or c0 >= c1:
        return out
    want = [(tr, tc) for tr in range(r0 // cog.tile_h, (r1 - 1) // cog.tile_h + 1)
            for tc in range(c0 // cog.tile_w, (c1 - 1) // cog.tile_w + 1)]
    spans = sorted((int(cog.offsets[tr * cog.tiles_across + tc]), int(cog.counts[tr * cog.tiles_across + tc]), tr, tc)
                   for tr, tc in want)
    groups: list[list[tuple]] = []
    for s in spans:
        if s[1] == 0:
            groups.append([s])
        elif groups and groups[-1][-1][1] and s[0] - (groups[-1][-1][0] + groups[-1][-1][1]) <= MERGE_GAP:
            groups[-1].append(s)
        else:
            groups.append([s])
    for g in groups:
        live = [s for s in g if s[1]]
        blob, base = (fetch(live[0][0], live[-1][0] + live[-1][1] - 1), live[0][0]) if live else (b"", 0)
        for off, n, tr, tc in g:
            tile = decode_tile(cog, blob[off - base: off - base + n] if n else b"")
            y0, x0 = tr * cog.tile_h, tc * cog.tile_w
            ys, ye = max(r0, y0), min(r1, y0 + cog.tile_h)
            xs, xe = max(c0, x0), min(c1, x0 + cog.tile_w)
            out[ys - row0:ye - row0, xs - col0:xe - col0] = tile[ys - y0:ye - y0, xs - x0:xe - x0]
    return out


def open_cog(fetch) -> Cog:
    return parse(fetch(0, HEADER_BYTES - 1), fetch)


def write_tiff(arr: np.ndarray, tile: int = 16, deflate: bool = True, predictor: int = 2, nodata: int | None = 0,
               big: bool = False) -> bytes:
    """A minimal tiled TIFF of `arr` (uint8 or uint16), for the tests: the same layout the reader expects."""
    arr = np.asarray(arr)
    h, w = arr.shape
    th, tw = -(-h // tile), -(-w // tile)
    tiles = []
    for tr in range(th):
        for tc in range(tw):
            t = np.zeros((tile, tile), dtype=arr.dtype)
            blk = arr[tr * tile:(tr + 1) * tile, tc * tile:(tc + 1) * tile]
            t[:blk.shape[0], :blk.shape[1]] = blk
            if predictor == 2:
                t = np.concatenate([t[:, :1], np.diff(t, axis=1)], axis=1).astype(arr.dtype)
            b = t.astype("<" + arr.dtype.str[1:]).tobytes()
            tiles.append(zlib.compress(b) if deflate else b)
    bits = arr.dtype.itemsize * 8
    tags = [(256, 3, [w]), (257, 3, [h]), (258, 3, [bits]), (259, 3, [8 if deflate else 1]), (277, 3, [1]),
            (317, 3, [predictor]), (322, 3, [tile]), (323, 3, [tile]), (339, 3, [1])]
    if nodata is not None:
        tags.append((42113, 2, str(nodata).encode() + b"\0"))
    head = 16 if big else 8
    entry, cnt_size, inline = (20, 8, 8) if big else (12, 2, 4)
    n_tags = len(tags) + 2
    ifd_size = cnt_size + n_tags * entry + (8 if big else 4)
    extra_at = head + ifd_size
    extra = bytearray()
    off_type, off_fmt = (16, "<Q") if big else (4, "<I")
    data_at = extra_at + 2 * len(tiles) * (8 if big else 4) + 64
    offs, pos = [], data_at
    for t in tiles:
        offs.append(pos)
        pos += len(t)
    entries = []
    for tag, typ, vals in tags:
        if typ == 2:
            payload, count = bytes(vals), len(vals)
        else:
            payload, count = struct.pack(f"<{len(vals)}H", *vals), len(vals)
        entries.append((tag, typ, count, payload))
    for tag, vals in ((324, offs), (325, [len(t) for t in tiles])):
        entries.append((tag, off_type, len(vals), b"".join(struct.pack(off_fmt, v) for v in vals)))
    entries.sort()
    ifd = bytearray(struct.pack("<Q", n_tags) if big else struct.pack("<H", n_tags))
    for tag, typ, count, payload in entries:
        ifd += struct.pack("<HH", tag, typ) + (struct.pack("<Q", count) if big else struct.pack("<I", count))
        if len(payload) <= inline:
            ifd += payload.ljust(inline, b"\0")
        else:
            ptr = extra_at + len(extra)
            extra += payload
            ifd += struct.pack("<Q", ptr) if big else struct.pack("<I", ptr)
    ifd += b"\0" * (8 if big else 4)
    header = (b"II" + struct.pack("<HHHQ", 43, 8, 0, head)) if big else (b"II" + struct.pack("<HI", 42, head))
    out = bytearray(header) + ifd + extra
    if len(out) > data_at:
        raise ValueError("header overflow in the test writer")
    out += b"\0" * (data_at - len(out))
    for t in tiles:
        out += t
    return bytes(out)
