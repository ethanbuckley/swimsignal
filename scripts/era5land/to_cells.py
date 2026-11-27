"""Downloaded ERA5-Land months (scripts/era5land/fetch.py) to per-cell, per-year hourly rain files shaped like the
cached Open-Meteo archive files (docs/ERA5-LAND-BULK-RAIN-2026-11.md). Offline: it reads the download and the names of
cache files, and writes only under --out.

    uv run --extra era5 python scripts/era5land/to_cells.py --out "$HOME/dipcast-scratch/era5land" \\
        --cells-from ~/Documents/GitHub/dipcast/data/cache/rain --cells-from ~/Documents/GitHub/dipcast/data/cache/rain_nine \\
        --years 2020-2025

Which cells: --cells-from DIR takes the cells named by the archive_<lat>_<lon>_<tag>.parquet files in DIR (names only;
no file is opened or changed). --points CSV takes lat and lon columns and snaps them as rainfall.grid_cell does.
--all-land takes every grid point with data.

What it writes, under <out>/cache/rain/ (or --cells-out):
  * archive_<lat>_<lon>_<year>.parquet with the cached files' columns and types: cell_lat, cell_lon (float64), time
    (timestamp[us, UTC], the end of the hour), precip_mm (float64, the rain in the hour ending then). A year runs from
    its first hour, 00:00 on 1 January (the last hour of 31 December before), to the last hour on disk.
  * ERA5LAND_CELLS.csv: the grid point that serves each cell, and how it was chosen (map_cells).
  * ERA5LAND_MANIFEST.json: the source, the rules, each month file's SHA-256, and per year the months used.

How the hourly values are made: era5land_core.deaccumulate (running total from 00 UTC to the hour's rain, metres to
mm, small negative steps to 0), then rounded to --round mm (default 0.1, the cached files' step). The first hour of a
year needs the 23:00 value of the previous 31 December: without that month on disk it is NaN, never 0.

Pointing a backtest at it: with DIPCAST_CACHE=<out>/cache, dipcast.model.training.load_rain reads these files in
place of the shared cache. A loader that fetches missing cells (rainfall.fetch_archive) would ask Open-Meteo for any
cell not converted here, so convert every cell the backtest needs first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import era5land_core as core  # noqa: E402


def months_on_disk(out: Path) -> dict[str, Path]:
    found = {}
    for p in sorted((out / "raw").glob("*/era5land_tp_*.nc")):
        found[p.stem.split("_")[-1]] = p
    return found


def year_months(year: int, on_disk: dict[str, Path], first: int = 1) -> list[str]:
    """The months of `year` on disk, from month `first` (default January) on without a gap. A year whose first month is
    missing gets none: a file that skipped a month would look whole. `first` 5 serves a season-only download (May on)."""
    out = []
    for m in range(first, 13):
        k = f"{year:04d}-{m:02d}"
        if k not in on_disk:
            break
        out.append(k)
    return out


def cells_from_dirs(dirs: list[Path]) -> set[tuple[float, float]]:
    found = set()
    for d in dirs:
        for p in Path(d).glob("archive_*.parquet"):
            c = core.cell_from_name(p.name)
            if c:
                found.add(c)
    return found


def cells_from_points(csv: Path) -> set[tuple[float, float]]:
    s = pd.read_csv(csv)
    lat = s["lat"] if "lat" in s else s["latitude"]
    lon = s["lon"] if "lon" in s else s["longitude"]
    ok = lat.notna() & lon.notna()
    a, b = core.snap(lat[ok]), core.snap(lon[ok])
    return {(float(x), float(y)) for x, y in zip(a, b, strict=True)}


class Source:
    """The downloaded months, read once each, with the grid checked to be the same in every file."""

    def __init__(self, on_disk: dict[str, Path]):
        self.on_disk = on_disk
        self.lat = self.lon = None
        self.sha = {}

    def read(self, month: str) -> core.TpField:
        data = self.on_disk[month].read_bytes()
        self.sha[month] = hashlib.sha256(data).hexdigest()
        f = core.read_tp(data)
        if self.lat is None:
            self.lat, self.lon = f.lat, f.lon
        elif not (np.allclose(f.lat, self.lat) and np.allclose(f.lon, self.lon)):
            raise ValueError(f"{month}: a different grid from the first file read; was --area changed?")
        return f


def prev_key(year: int, first: int = 1) -> str:
    """The month whose last hour starts the series: the previous December, or the month before `first`. The manifest
    keeps the key `previous_december` for it either way."""
    return f"{year - 1:04d}-12" if first == 1 else f"{year:04d}-{first - 1:02d}"


def convert_year(year: int, src: Source, cmap: pd.DataFrame, cells_out: Path, step: float, first: int = 1) -> dict:
    """Writes every mapped cell's file for `year`, from month `first`. Returns what was done, for the manifest."""
    months = year_months(year, src.on_disk, first)
    if not months:
        return {"months": [], "written": 0, "note": f"month {first} not on disk"}
    use = cmap[cmap["how"].isin(["centre", "nearest with data"])].reset_index(drop=True)
    ii, jj = use["i"].to_numpy(int), use["j"].to_numpy(int)
    blocks, times = [], []
    prev_month = prev_key(year, first)
    had_prev = prev_month in src.on_disk
    if had_prev:
        f = src.read(prev_month)
        blocks.append(f.tp[-1:, ii, jj])
        times.append(f.times[-1:])
    for m in months:
        f = src.read(m)
        blocks.append(f.tp[:, ii, jj])
        times.append(f.times)
    acc = np.concatenate(blocks, axis=0)
    t = pd.DatetimeIndex(np.concatenate([x.tz_convert(None).to_numpy() for x in times])).tz_localize("UTC")
    lead = 1 if had_prev else 0
    body = t[lead:]
    start = pd.Timestamp(f"{year}-{first:02d}-01", tz="UTC")
    if body[0] != start:
        raise ValueError(f"{year}: first valid time {body[0]}, expected {start}")
    if not ((body[1:] - body[:-1]) == pd.Timedelta(hours=1)).all():
        raise ValueError(f"{year}: the valid times are not every hour without a gap")
    if had_prev and t[0] != body[0] - pd.Timedelta(hours=1):
        raise ValueError(f"{year}: the previous month's last step is {t[0]}, not the hour before {body[0]}")
    mm, big_negative = core.deaccumulate(acc, t)
    mm = core.round_to(mm[lead:], step)
    time_col = pd.Series(body.astype("datetime64[us, UTC]"))
    cells_out.mkdir(parents=True, exist_ok=True)
    for k, r in use.iterrows():
        df = pd.DataFrame({"cell_lat": float(r.cell_lat), "cell_lon": float(r.cell_lon), "time": time_col,
                           "precip_mm": mm[:, k].astype("float64")})
        p = cells_out / f"archive_{core.cell_key(r.cell_lat, r.cell_lon)}_{year}.parquet"
        tmp = p.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(p)
    return {"months": months, "first_month": first, "previous_december": had_prev, "written": len(use), "hours": int(len(body)),
            "first_hour_nan": int(np.isnan(mm[0]).sum()), "steps_below_minus_0.05mm": big_negative}


def _commit() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def run(out: Path, cells_out: Path, years: list[int] | None, cells: set | None, all_land: bool,
        step: float = 0.1, max_step: int = 1, force: bool = False, first_month: int = 1) -> dict:
    for p in (out, cells_out):
        problem = core.out_ok(p)
        if problem:
            raise SystemExit(problem)
    on_disk = months_on_disk(out)
    if not on_disk:
        raise SystemExit(f"No downloaded month under {out / 'raw'}. Run fetch.py first.")
    src = Source(on_disk)
    first = src.read(min(on_disk))
    valid = np.isfinite(first.tp).any(axis=0)
    if all_land:
        cells = {(float(a), float(b)) for a in core.snap(first.lat) for b in core.snap(first.lon)}
    if not cells:
        raise SystemExit("No cells: give --cells-from, --points or --all-land.")
    cmap = core.map_cells(sorted(cells), first.lat, first.lon, valid, max_step)
    if all_land:
        cmap = cmap[cmap["how"] == "centre"].reset_index(drop=True)
    cells_out.mkdir(parents=True, exist_ok=True)
    cmap.to_csv(cells_out / "ERA5LAND_CELLS.csv", index=False)
    man_path = cells_out / "ERA5LAND_MANIFEST.json"
    manifest = json.loads(man_path.read_text()) if man_path.exists() else {}
    done = manifest.get("years", {})
    have = sorted({int(m[:4]) for m in on_disk})
    years = [y for y in (years or have) if y in have]
    for y in years:
        files_there = all((cells_out / f"archive_{core.cell_key(a, b)}_{y}.parquet").exists()
                          for a, b in cmap.loc[cmap["how"].isin(["centre", "nearest with data"]),
                                               ["cell_lat", "cell_lon"]].itertuples(index=False))
        if not force and files_there and done.get(str(y), {}).get("months") == year_months(y, on_disk, first_month) \
                and done[str(y)].get("previous_december") == (prev_key(y, first_month) in on_disk):
            print(f"{y}: already converted")
            continue
        info = convert_year(y, src, cmap, cells_out, step, first_month)
        done[str(y)] = info
        print(f"{y}: {info['written']} cells, months {info['months'][0] if info['months'] else '-'} to "
              f"{info['months'][-1] if info['months'] else '-'}")
    manifest.update({
        "source": f"Copernicus CDS {core.DATASET}, {core.VARIABLE}, hourly, NetCDF",
        "rule": "hour ending t: tp(t) - tp(t - 1 h), and tp(01 UTC) alone; metres x 1000; negative steps to 0",
        "round_mm": step, "max_step": max_step, "cells": int(len(cmap)),
        "cells_by_how": {k: int(v) for k, v in cmap["how"].value_counts().items()},
        "month_sha256": {**manifest.get("month_sha256", {}), **src.sha},
        "years": done, "code_commit": _commit(), "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
    })
    man_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def parse_years(text: str | None) -> list[int] | None:
    if not text:
        return None
    out = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="the folder fetch.py downloaded into")
    ap.add_argument("--cells-out", type=Path, default=None, help="default <out>/cache/rain")
    ap.add_argument("--cells-from", type=Path, action="append", default=[], help="a folder of archive_*.parquet")
    ap.add_argument("--points", type=Path, default=None, help="a CSV with lat and lon columns")
    ap.add_argument("--all-land", action="store_true", help="every grid point with data")
    ap.add_argument("--years", default=None, help="e.g. 2020-2025 or 2012,2015-2016 (default: all on disk)")
    ap.add_argument("--round", type=float, default=0.1, help="mm step; 0 keeps full precision (default %(default)s)")
    ap.add_argument("--max-step", type=int, default=1, help="grid steps to look for a point with data")
    ap.add_argument("--force", action="store_true", help="rewrite years already converted")
    ap.add_argument("--first-month", type=int, default=1, choices=range(1, 13),
                    help="each year from this month (default January; 5 for a May-to-September download)")
    a = ap.parse_args(argv)
    cells = cells_from_dirs(a.cells_from) if a.cells_from else set()
    if a.points:
        cells |= cells_from_points(a.points)
    m = run(a.out, a.cells_out or a.out / "cache" / "rain", parse_years(a.years), cells, a.all_land,
            a.round, a.max_step, a.force, a.first_month)
    print(json.dumps({"cells": m["cells"], "cells_by_how": m["cells_by_how"], "years": sorted(m["years"])}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
