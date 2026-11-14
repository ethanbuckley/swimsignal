"""The Met Office UK radar composites (AWS Open Data bucket "met-office-radar-obs-data", CC BY-SA 4.0, no
account): the grid, one composite's reader, and the reduction of composites to hourly rain per SwimSignal rain cell.

Shared by scripts/fetch_met_office_radar.py (the archive kept by hand, docs/MET-OFFICE-DATA-2026-10.md) and the radar
shadow (dipcast.radar_live, docs/RADAR-SHADOW-2026-11.md), so both reduce a composite the same way. Reading a
composite needs h5py (the optional `radar` group); everything else runs without it.
"""

from __future__ import annotations

import io
import re

import numpy as np
import pandas as pd
from pyproj import Transformer

from dipcast import config
from dipcast.ingest.rainfall import grid_cell

BUCKET = "https://met-office-radar-obs-data.s3.amazonaws.com"
KEY_RE = re.compile(r"radar/\d{4}/\d{2}/\d{2}/(\d{12})_ODIM_ng_radar_rainrate_composite_1km_UK\.h5$")
CREDIT = ("Contains Met Office data, British Crown copyright 2024-2025, the Met Office, licensed "
          "under CC BY-SA 4.0 (AWS Open Data: Met Office UK Radar Observations).")

# The grid, read from the files' `where` group on 24 Oct 2026 (one from 21 Nov 2024, two from 24 Oct
# 2026, all the same): 1725 x 2175 pixels of 1 km, first row at the top. The corner coordinates in
# the file put the outer edges at x -405,000 to 1,320,000 m and y -625,000 to 1,550,000 m.
NX, NY, PIXEL_M = 1725, 2175, 1000.0
X_LEFT, Y_TOP = -405_000.0, 1_550_000.0
PROJDEF = "+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.999601 +x_0=400000 +y_0=-100000 +ellps=airy +units=m"
# That projdef is British National Grid without its datum. EPSG:27700 adds the OSGB36 datum; the two
# put a point at 52 N 1 W about 115 m apart, an eighth of a pixel. The "ng" in the file name is
# National Grid, so EPSG:27700 it is.
GRID_CRS = "EPSG:27700"

# The 15-minute composites are snapshots of rain rate (mm/h), not totals: each file's scan window
# lasts about a minute, within a minute of the time in its name (00:14:07 to 00:15:09 for one 00:15
# file). The hour ending T is the trapezoid over the five snapshots T-60, T-45, T-30, T-15 and T.
STEP = pd.Timedelta(minutes=15)
WEIGHTS = np.array([0.5, 1.0, 1.0, 1.0, 0.5])


def cell_pixels(cells: list[tuple[float, float]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The radar pixels whose centre falls in each cell, by the same grid_cell the sites use.
    Returns (flat pixel index, cell number per index, pixels per cell)."""
    d = config.RAIN_GRID_DEG / 2
    fwd = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True)
    inv = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True)
    idx, lab = [], []
    n = np.zeros(len(cells), dtype=np.int64)
    for k, (cl, cn) in enumerate(cells):
        xs, ys = fwd.transform([cn - d, cn + d, cn - d, cn + d], [cl - d, cl - d, cl + d, cl + d])
        c0 = max(0, int((min(xs) - X_LEFT) // PIXEL_M) - 1)
        c1 = min(NX - 1, int((max(xs) - X_LEFT) // PIXEL_M) + 1)
        r0 = max(0, int((Y_TOP - max(ys)) // PIXEL_M) - 1)
        r1 = min(NY - 1, int((Y_TOP - min(ys)) // PIXEL_M) + 1)
        if c0 > c1 or r0 > r1:
            continue
        rr, cc = np.mgrid[r0:r1 + 1, c0:c1 + 1]
        lon, lat = inv.transform(X_LEFT + (cc + 0.5) * PIXEL_M, Y_TOP - (rr + 0.5) * PIXEL_M)
        gl, gn = grid_cell(lat, lon)
        inside = (gl == cl) & (gn == cn)
        flat = (rr * NX + cc)[inside]
        idx.append(flat)
        lab.append(np.full(flat.size, k))
        n[k] = flat.size
    if not idx:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), n
    return np.concatenate(idx), np.concatenate(lab), n


def read_composite(data: bytes) -> np.ndarray:
    """The rain rate in mm/h, NaN where the file says nodata, from one ODIM HDF5 composite. Raises
    ValueError if the grid or the quantity is not the one this script was written for."""
    import h5py   # the optional `radar` group; imported here so the rest runs and tests without it

    with h5py.File(io.BytesIO(data), "r") as f:
        where = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in f["where"].attrs.items()}
        what = {k: (v.decode() if isinstance(v, bytes) else v)
                for k, v in f["dataset1/data1/what"].attrs.items()}
        origin = f["dataset1/how"].attrs.get("origin", b"")
        origin = origin.decode() if isinstance(origin, bytes) else origin
        got = (int(where["xsize"]), int(where["ysize"]), float(where["xscale"]), float(where["yscale"]),
               where["projdef"].strip(), what["quantity"], origin)
        want = (NX, NY, PIXEL_M, PIXEL_M, PROJDEF, "RATE", "UPPER LEFT")
        if got != want:
            raise ValueError(f"radar grid changed: {got} != {want}")
        raw = f["dataset1/data1/data"][()]
    if raw.shape != (NY, NX):
        raise ValueError(f"radar array is {raw.shape}, not {(NY, NX)}")
    rate = raw.astype(np.float64) * float(what["gain"]) + float(what["offset"])
    rate[(raw == what["nodata"]) | ~np.isfinite(raw)] = np.nan
    return rate


def reduce_snapshot(rate: np.ndarray, idx: np.ndarray, lab: np.ndarray, n_cells: int
                    ) -> tuple[np.ndarray, np.ndarray]:
    """Per cell: the sum of the rate over pixels with data, and how many pixels had data."""
    v = rate.ravel()[idx]
    ok = np.isfinite(v)
    sums = np.bincount(lab[ok], weights=v[ok], minlength=n_cells)
    counts = np.bincount(lab[ok], minlength=n_cells).astype(np.float64)
    return sums, counts


def hourly(snaps: dict[pd.Timestamp, tuple[np.ndarray, np.ndarray]], hours: pd.DatetimeIndex,
           n_pix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rain (mm) and coverage per hour and cell, shape (hours, cells). Each hour pools its five
    snapshots' pixels with the trapezoid weights, so a snapshot with few pixels counts for little.
    A missing snapshot lowers coverage; an hour with no data is NaN with coverage 0."""
    mm = np.full((len(hours), len(n_pix)), np.nan)
    cov = np.zeros_like(mm)
    zero = (np.zeros(len(n_pix)), np.zeros(len(n_pix)))
    for h, t in enumerate(hours):
        s = sum(w * snaps.get(t - (4 - i) * STEP, zero)[0] for i, w in enumerate(WEIGHTS))
        c = sum(w * snaps.get(t - (4 - i) * STEP, zero)[1] for i, w in enumerate(WEIGHTS))
        ok = c > 0
        mm[h, ok] = s[ok] / c[ok]   # mean rate in mm/h over one hour = mm
        cov[h] = c / (WEIGHTS.sum() * np.maximum(n_pix, 1))
    return mm, cov
