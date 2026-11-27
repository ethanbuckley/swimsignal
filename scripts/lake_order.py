"""Each no-overflow lake bathing water's cut-points for today's "higher, about or lower than usual for this lake" word
(docs/LAKE-ORDER-NO-OVERFLOW-2026-11.md; read by src/dipcast/lake_order.py). Off CI, by hand, offline:

    export DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch>/state
    export DIPCAST_CACHE=<scratch cache holding rain/archive_<cell>_<year>.parquet for the spots' cells, 2023 to 2026>
    uv run python scripts/lake_order.py freeze data/processed/lake_order.v1.json
    uv run python scripts/lake_order.py check <bench seen.parquet>     # development figures, decide nothing

`freeze` makes no request and reads no sample. For each spot in SPOTS, on every May to September day of 2023 to 2026:
rain in the 48 and 24 hours to midday at the spot's cell from Open-Meteo's archive, exposure 0 (no monitored overflow
upstream, as the forecast gives there), and lake-range-v1's likely reading on the average-lake basis (the basis bench
read 1 scored these lakes on). The cut-points are one third and two thirds of log10 of that reading, the river order
line's rule (scripts/river_usual.py).

`check` reads the bench's seen rows (2023 to 2026, which the cut-points' days overlap) and prints, at these lakes, the
measured samples on "higher" days against "lower" days. Development only: the cut-points were made on the same years.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MODEL = REPO / "data" / "processed" / "ecoli_lake_range.json"
YEARS = (2023, 2024, 2025, 2026)
TZ = "Europe/London"
MIN_DAYS = 300          # of 612 season days, as river_usual.py
MIN_GAP = 0.01          # log10: cut-points closer than this say nothing
# Bench read 1's lake bathing waters (docs/BENCH-READ-LAKE-RANGE-2026-11.md) that have a daily forecast: lake spots
# with no monitored overflow upstream. Cotswold Country Park and Henleaze Lake are isolated (no daily rows) and are
# left out. Positions are spots.csv's.
SPOTS = {
    "bw-uki1106-11940": ("The Serpentine - Hyde Park", 51.50491, -0.16907),
    "bw-uki1101-11910": ("Hampstead Heath (Ladies Pond)", 51.56672, -0.16009),
    "bw-uki1101-11920": ("Hampstead Heath (Mens Pond)", 51.56334, -0.15662),
    "bw-uki1101-11930": ("Hampstead Heath (Mixed Pond)", 51.56071, -0.16625),
    "bw-ukf1400-09750": ("Colwick Country Park (West Lake)", 52.94516, -1.09815),
}


def season_days() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(np.concatenate([pd.date_range(f"{y}-05-01", f"{y}-09-30", freq="D", tz=TZ) for y in YEARS]))


def figure(m: dict, r48, r24, days) -> np.ndarray:
    """log10 of lake-range-v1's likely reading, average-lake basis, exposure 0, at the given rain and dates."""
    from dipcast.lake_range import _quantiles
    from dipcast.model.ecoli import features
    n = len(days)
    X = features(np.asarray(r48, float), np.asarray(r24, float), np.zeros(n), np.ones(n), pd.DatetimeIndex(days))
    ok = np.isfinite(X[m["cols"]].to_numpy(float)).all(axis=1)
    med = _quantiles(m, X[m["cols"]].fillna(0.0), None, qs=(0.5,))[0.5]
    return np.where(ok, np.log10(med), np.nan)


def cut_points(f: pd.Series) -> dict | None:
    f = f.dropna()
    if len(f) < MIN_DAYS:
        return None
    lo, hi = (round(float(v), 3) for v in f.quantile([1 / 3, 2 / 3]))
    if hi - lo < MIN_GAP:
        return None
    r = f.round(3)
    return {"low": lo, "high": hi, "days": int(len(f)), "lower": round(float((r < lo).mean()), 3),
            "higher": round(float((r > hi).mean()), 3)}


def freeze(dest: Path) -> None:
    assert all(k in os.environ for k in ("DIPCAST_ROOT", "DIPCAST_STATE", "DIPCAST_CACHE")), "scratch roots only"
    from dipcast.ingest.rainfall import grid_cell
    from dipcast.lake_range import SHA256
    from dipcast.model.ecoli import SAMPLE_HOUR, rain_windows
    from dipcast.river_usual import key

    raw = MODEL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA256, "not the frozen lake-range-v1"
    m = json.loads(raw)
    cache = Path(os.environ["DIPCAST_CACHE"]) / "rain"
    days = season_days()
    ends = days + pd.Timedelta(hours=SAMPLE_HOUR)
    spots, used = {}, set()
    for sid, (name, lat, lon) in SPOTS.items():
        cell = tuple(float(v) for v in grid_cell(lat, lon))
        files = [cache / f"archive_{cell[0]:.3f}_{cell[1]:.3f}_{y}.parquet" for y in YEARS]
        used.update(files)
        rain = pd.concat(pd.read_parquet(f) for f in files)
        hourly = rain.assign(time=rain["time"].dt.tz_convert(TZ)).set_index("time")["precip_mm"].sort_index()
        r48, r24 = rain_windows(hourly, ends)
        c = cut_points(pd.Series(figure(m, r48, r24, ends)))
        assert c is not None, sid
        spots[key(lat, lon)] = {"id": sid, "name": name, "cell": list(cell), **c}
        print(sid, c, flush=True)
    doc = {"rule": "lake-order-v1", "made": pd.Timestamp.now("UTC").strftime("%Y-%m-%d"),
           "record": "docs/LAKE-ORDER-NO-OVERFLOW-2026-11.md",
           "what": "Per lake spot with no monitored overflow upstream, the cut-points at one third and two thirds of "
                   "log10 of lake-range-v1's likely reading (average-lake basis, exposure 0) on May to September days "
                   "of 2023 to 2026, hindcast at lead 0 (scripts/lake_order.py). A figure under `low` is lower than "
                   "usual there, over `high` higher, else about usual; compared at 3 decimal places.",
           "model_sha256": hashlib.sha256(raw).hexdigest(),
           "inputs": "Open-Meteo archive rain at the spot's cell, 48 h and 24 h to 12:00 Europe/London; exposure 0",
           "rain_files_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(used)},
           "spots": dict(sorted(spots.items()))}
    text = json.dumps(doc, indent=1) + "\n"
    dest.write_text(text)
    print(dest, "sha256", hashlib.sha256(text.encode()).hexdigest())


def check(seen: Path, frozen: Path) -> None:
    """Measured samples on higher days against lower days at these lakes, 2023-26 (development: same years)."""
    from dipcast.river_usual import key
    m = json.loads(MODEL.read_text())
    cuts = json.loads(frozen.read_text())["spots"]
    s = pd.read_parquet(seen)
    rows = []
    for sid, (name, lat, lon) in SPOTS.items():
        g = s[s["bw_id"] == sid.removeprefix("bw-")].copy()
        c = cuts[key(lat, lon)]
        f = np.round(figure(m, g["rain_48h"], g["rain_24h"], g["sample_time"]), 3)
        g["word"] = np.where(f > c["high"], "higher", np.where(f < c["low"], "lower", "about"))
        rows.append(g)
    d = pd.concat(rows)
    d["log"] = np.log10(d["ecoli"].clip(lower=1))
    by = d.groupby("word").agg(samples=("log", "size"), geo_mean=("log", lambda v: round(10 ** v.mean(), 1)),
                               over_500=("ecoli", lambda v: int((v > 500).sum())))
    print(by)
    within = d.groupby("bw_id").apply(lambda g: g.loc[g.word == "higher", "log"].mean() - g.loc[g.word == "lower", "log"].mean())
    print("higher over lower, geometric mean ratio, per lake:", (10 ** within).round(2).to_dict())
    print("pooled within lake:", round(float(10 ** within.mean()), 2))


if __name__ == "__main__":
    if sys.argv[1] == "freeze":
        freeze(Path(sys.argv[2]))
    else:
        check(Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else REPO / "data" / "processed" / "lake_order.v1.json")
