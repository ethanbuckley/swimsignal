"""Which model grid do the cached archive rain files come from? (docs/ERA5-LAND-BULK-RAIN-2026-11.md, "Measured in the
cache"). Read only: it opens the cached files and changes nothing.

    uv run python scripts/era5land/neighbour_check.py ~/Documents/GitHub/dipcast/data/cache/rain:2024 \\
        ~/Documents/GitHub/dipcast/data/cache/rain_nine:2025 ~/Documents/GitHub/dipcast/data/cache/rain_multi:2020

Open-Meteo serves a cell from one grid point of its source model. Two neighbouring 0.1 degree cells served by the same
point hold byte-identical hourly series. So, for every pair of neighbouring cached cells (east-west and north-south),
it compares the year's series and asks how often each grid's nearest-point rule predicts "same point" exactly when the
series are identical:
  * IFS, reduced Gaussian O1280 (Open-Meteo's ecmwf_ifs): 2560 Gaussian latitudes, 4k + 16 points on the k-th row from
    the nearer pole, longitudes from 0.
  * ERA5, regular 0.25 degree.
  * ERA5-Land, regular 0.1 degree: never the same point, since every cell centre is its own point.
"""

from __future__ import annotations

import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import era5land_core as core  # noqa: E402


@lru_cache(maxsize=1)
def gaussian_latitudes() -> np.ndarray:
    """The 2560 latitudes of the N1280 Gaussian grid, north to south."""
    x, _ = np.polynomial.legendre.leggauss(2560)
    return np.sort(np.degrees(np.arcsin(x)))[::-1]


def o1280_point(lat: float, lon: float) -> tuple[int, int]:
    glat = gaussian_latitudes()
    i = int(np.argmin(np.abs(glat - lat)))
    k = i + 1 if i < 1280 else 2560 - i
    n = 4 * k + 16
    return i, int(round((lon % 360) / (360 / n))) % n


def era5_point(lat: float, lon: float) -> tuple[int, int]:
    return round(lat / 0.25), round(lon / 0.25)


def era5land_point(lat: float, lon: float) -> tuple[int, int]:
    return round(lat / 0.1), round(lon / 0.1)


RULES = {"IFS O1280 nearest": o1280_point, "ERA5 0.25 nearest": era5_point, "ERA5-Land 0.1": era5land_point}


def series_hashes(cache_dir: Path, year: int) -> dict[tuple[float, float], str]:
    out = {}
    for f in sorted(Path(cache_dir).glob(f"archive_*_{year}.parquet")):
        c = core.cell_from_name(f.name)
        v = pd.read_parquet(f, columns=["precip_mm"])["precip_mm"].to_numpy()
        out[c] = hashlib.sha1(np.round(v, 2).tobytes()).hexdigest()
    return out


def neighbour_pairs(hashes: dict) -> list[tuple[tuple, tuple, bool, str]]:
    pairs = []
    for (la, lo), h in hashes.items():
        for nb, way in (((la, round(lo + 0.1, 3) + 0.0), "east-west"), ((round(la + 0.1, 3) + 0.0, lo), "north-south")):
            if nb in hashes:
                pairs.append(((la, lo), nb, h == hashes[nb], way))
    return pairs


def score(pairs) -> dict:
    same = np.array([p[2] for p in pairs])
    out = {"pairs": len(pairs), "identical": int(same.sum()),
           "identical_east_west": int(sum(p[2] for p in pairs if p[3] == "east-west")),
           "pairs_east_west": sum(p[3] == "east-west" for p in pairs)}
    for name, rule in RULES.items():
        pred = np.array([rule(*a) == rule(*b) for a, b, _, _ in pairs])
        out[f"agree: {name}"] = round(float(np.mean(pred == same)), 3) if len(pairs) else None
    return out


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    for a in args:
        d, _, y = a.rpartition(":")
        print(json.dumps({"dir": d, "year": int(y), **score(neighbour_pairs(series_hashes(Path(d), int(y))))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
