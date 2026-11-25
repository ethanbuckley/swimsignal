"""Each river spot's October to April cut-points for the winter "higher or lower than usual here" word
(docs/RIVER-WINTER-LINE-2026-11.md; read by src/dipcast/river_usual.py). Off CI, by hand, offline:

    export DIPCAST_ROOT=<scratch copy of data/ and the spot lists> DIPCAST_STATE=<scratch>/state
    export DIPCAST_CACHE=<scratch cache: rain/archive_*.parquet for the spots' and their overflows' cells>
    python scripts/river_usual_winter.py hindcast <out dir>   # each spot's figure on every winter day, 2023 to 2026
    python scripts/river_usual_winter.py freeze <out dir> data/processed/river_usual_winter.v1.json

As scripts/river_usual.py, with three differences. The days are October to April. The figure is the river model
**without soil moisture** (`ecoli_model.json`), because that is the file the winter read scored
(docs/RIVER-WINTER-READ-2026-11.md); the soil-moisture model is untested in winter. And a hindcast's first day is
found by stepping back whole calendar days, so a clock change cannot misplace it (that record, amendment 1).
`hindcast` makes no request. Nothing is fitted and no sample is read."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

YEARS = (2023, 2024, 2025, 2026)
FIRST_DAY = "2023-02-01"   # the rain on disk starts 1 January 2023 and one spill input sums 30 days
MIN_DAYS = 380             # about half the winter days on disk: fewer and the spot gets no cut-points
MIN_GAP = 0.005            # cut-points closer than this say nothing: no cut-points
TZ = "Europe/London"
RULE = "river-usual-winter-v1"


def winter_days() -> pd.DatetimeIndex:
    """October to April days of YEARS from FIRST_DAY, in order."""
    parts = []
    for y in YEARS:
        parts += [pd.date_range(f"{y}-01-01", f"{y}-04-30", freq="D", tz=TZ), pd.date_range(f"{y}-10-01", f"{y}-12-31", freq="D", tz=TZ)]
    days = pd.DatetimeIndex(np.concatenate(parts))
    return days[days >= pd.Timestamp(FIRST_DAY, tz=TZ)]


def cut_points(p: pd.Series) -> dict | None:
    """A spot's cut-points from its winter figures, or None with too few days or no spread (river_usual.cut_points
    with this file's limits)."""
    p = p.dropna()
    if len(p) < MIN_DAYS:
        return None
    lo, hi = (round(float(v), 3) for v in p.quantile([1 / 3, 2 / 3]))
    if hi - lo < MIN_GAP:
        return None
    return {"low": lo, "high": hi, "days": int(len(p)), "lower": round(float((p.round(3) < lo).mean()), 3),
            "higher": round(float((p.round(3) > hi).mean()), 3)}


def hindcast(out: Path) -> None:
    import os
    assert all(k in os.environ for k in ("DIPCAST_ROOT", "DIPCAST_STATE", "DIPCAST_CACHE")), "scratch roots only"
    import build_site as bs
    from validate_ecoli import hindcast as exposure
    from validate_ecoli import load_rain

    from dipcast import config
    from dipcast.ingest.rainfall import grid_cell
    from dipcast.model import ecoli
    from dipcast.model.features import daily_rain_features
    from dipcast.model.forecast import MAX_MISSING_SHARE, _model, _net, _overflows
    from dipcast.model.transport import history_days, locate_pin, river_velocity, upstream_overflows
    from dipcast.river_usual import key

    spots = bs.load_spots()
    spots = spots[spots["kind"] == "river"]
    net, ov, model = _net(), _overflows(), _model()
    rain = load_rain()
    hourly, daily = rain.set_index(["cell_lat", "cell_lon"]).sort_index(), daily_rain_features(rain)
    plain = ecoli.load()
    days, rows, skipped = winter_days(), [], {}
    for r in spots.itertuples():
        kind, river = bs.spot_hints(r.kind, getattr(r, "river", ""))
        pin = locate_pin(net, float(r.lon), float(r.lat), kind_hint=kind, river_hint=river, name=r.name)
        if pin.mode != "river":
            skipped[r.id] = f"placed as {pin.mode}"
            continue
        up = upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None), max_km=config.MAX_UPSTREAM_KM)
        if up.empty:
            skipped[r.id] = "no monitored overflow upstream"
            continue
        cell = tuple(float(v) for v in grid_cell(float(r.lat), float(r.lon)))
        try:
            site_rain = hourly.loc[cell].set_index("time")["precip_mm"].sort_index()
        except KeyError:
            skipped[r.id] = "no rain at the spot's cell"
            continue
        g = pd.DataFrame({"id": r.id, "key": key(r.lat, r.lon), "lat": float(r.lat), "lon": float(r.lon), "day": days,
                          "sample_time": days + pd.Timedelta(hours=ecoli.SAMPLE_HOUR)})
        risk, miss = [], []
        for y in YEARS:   # one calendar year at a time: days stay consecutive
            d = days[days.year == y]
            first = d.min() - pd.DateOffset(days=history_days(up["travel_h"]))   # whole calendar days back
            a, b = exposure(up, daily, pd.date_range(first, d.max(), freq="D"), model)
            risk.append(a.reindex(d))
            miss.append(b.reindex(d))
        g["risk"], g["missing_share"] = pd.concat(risk).to_numpy(), pd.concat(miss).to_numpy()
        g["rain_48h"], g["rain_24h"] = ecoli.rain_windows(site_rain, pd.DatetimeIndex(g["sample_time"]))
        ok = g["rain_48h"].notna() & g["rain_24h"].notna() & g["risk"].notna() & (g["missing_share"] <= MAX_MISSING_SHARE)
        X = ecoli.features(g["rain_48h"].fillna(0), g["rain_24h"].fillna(0), g["risk"].fillna(0), np.zeros(len(g)), g["sample_time"])
        g["p"], g["upstream"] = np.where(ok, plain.predict(X), np.nan), len(up)
        rows.append(g)
        print(r.id, int(ok.sum()), "days", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    pd.concat(rows, ignore_index=True).to_parquet(out / "river_usual_winter_days.parquet", index=False)
    (out / "river_usual_winter_skipped.json").write_text(json.dumps(skipped, indent=1) + "\n")
    print(len(rows), "spots;", len(skipped), "skipped")


def freeze(out: Path, dest: Path) -> None:
    d = pd.read_parquet(out / "river_usual_winter_days.parquet")
    spots, none = {}, []
    for (k, i), g in d.groupby(["key", "id"]):
        c = cut_points(g["p"])
        if c is None:
            none.append(i)
        else:
            spots[k] = {"id": i, **c}
    seen = d[d["p"].notna()]
    doc = {"rule": RULE, "made": pd.Timestamp.now("UTC").strftime("%Y-%m-%d"),
           "what": "Per river spot, the cut-points at one third and two thirds of its chance of a sample over 900 on "
                   "October to April days from February 2023 to November 2026, hindcast at lead 0 with the river model "
                   "that has no soil moisture (scripts/river_usual_winter.py). A figure under `low` is lower than "
                   "usual there, over `high` higher, else about usual.",
           "inputs": "Open-Meteo archive rain; lead-0 hindcast exposure; data/processed/ecoli_model.json",
           "model_sha256": hashlib.sha256((Path(__file__).resolve().parents[1] / "data" / "processed" / "ecoli_model.json").read_bytes()).hexdigest(),
           "first_day": str(seen["day"].min().date()), "last_day": str(seen["day"].max().date()),
           "no_cut_points": sorted(none), "spots": dict(sorted(spots.items()))}
    raw = json.dumps(doc, indent=1) + "\n"
    dest.write_text(raw)
    print(len(spots), "spots with cut-points;", len(none), "without;", "sha256", hashlib.sha256(raw.encode()).hexdigest())


if __name__ == "__main__":
    if sys.argv[1] == "hindcast":
        hindcast(Path(sys.argv[2]))
    else:
        freeze(Path(sys.argv[2]), Path(sys.argv[3]))
