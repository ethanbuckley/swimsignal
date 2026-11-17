"""Each river spot's cut-points for the "higher or lower than usual here" sentence
(docs/RIVER-ORDER-LINE-PROPOSAL-2026-11.md; read by src/dipcast/river_usual.py). Off CI, by hand, offline:

    export DIPCAST_ROOT=<scratch copy of data/ and the spot lists> DIPCAST_STATE=<scratch>/state
    export DIPCAST_CACHE=<scratch cache: rain/archive_*.parquet and soil/q1_*.parquet for the spots' cells>
    python scripts/river_usual.py hindcast <out dir>      # each spot's figure on every season day, 2023 to 2026
    python scripts/river_usual.py freeze <out dir> data/processed/river_usual.v1.json

`hindcast` makes no request. For every river spot in the spot lists with a monitored overflow upstream, placed as
the build places it (the spot's kind and river as hints, the forecast's reach upstream): rain in the 48 and 24 hours
to midday from Open-Meteo's archive, the lead-0 hindcast exposure (validate_ecoli.hindcast), and the chance of a
sample over 900 from the river model with soil moisture at 00:00 UTC of the day (Previous Runs, lead 0), or from
today's model on a day with no soil value, as the forecast does. `freeze` writes each spot's cut-points at one third
and two thirds of its figures, rounded as the page rounds them. Nothing is fitted and no sample is read."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "soil_moisture_eval"))

YEARS = (2023, 2024, 2025, 2026)
MIN_DAYS = 300          # of 612 season days: fewer and the spot gets no cut-points
MIN_GAP = 0.005         # cut-points closer than this say nothing: no cut-points
TZ = "Europe/London"


def season_days() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(np.concatenate([pd.date_range(f"{y}-05-01", f"{y}-09-30", freq="D", tz=TZ) for y in YEARS]))


def cut_points(p: pd.Series) -> dict | None:
    """A spot's cut-points from its season figures, or None with too few days or no spread."""
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
    from leads import soil_at_issue
    from validate_ecoli import hindcast as exposure, load_rain

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
    plain, sm_model = ecoli.load(), ecoli.load_sm()
    days, rows, skipped = season_days(), [], {}
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
        for y in YEARS:   # one season at a time: days stay consecutive
            d = days[days.year == y]
            a, b = exposure(up, daily, pd.date_range(d.min() - pd.Timedelta(days=history_days(up["travel_h"])), d.max(), freq="D"), model)
            risk.append(a.reindex(d)); miss.append(b.reindex(d))
        g["risk"], g["missing_share"] = pd.concat(risk).to_numpy(), pd.concat(miss).to_numpy()
        g["rain_48h"], g["rain_24h"] = ecoli.rain_windows(site_rain, pd.DatetimeIndex(g["sample_time"]))
        ok = g["rain_48h"].notna() & g["rain_24h"].notna() & g["risk"].notna() & (g["missing_share"] <= MAX_MISSING_SHARE)
        X = ecoli.features(g["rain_48h"].fillna(0), g["rain_24h"].fillna(0), g["risk"].fillna(0), np.zeros(len(g)), g["sample_time"])
        g["sm"] = soil_at_issue(g, config.CACHE / "soil", 0)
        p = plain.predict(X)
        has = np.isfinite(g["sm"].to_numpy())
        if has.any():
            Xs = X[has].copy()
            Xs["sm"] = np.clip(g.loc[has, "sm"].to_numpy(), *sm_model.meta["sm_range"])   # held in range, as ecoli.with_sm
            p[has] = sm_model.predict(Xs)
        g["p"], g["with_soil"], g["upstream"] = np.where(ok, p, np.nan), has, len(up)
        rows.append(g)
        print(r.id, int(ok.sum()), "days;", int((ok & has).sum()), "with soil moisture", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    pd.concat(rows, ignore_index=True).to_parquet(out / "river_usual_days.parquet", index=False)
    (out / "river_usual_skipped.json").write_text(json.dumps(skipped, indent=1) + "\n")
    print(len(rows), "spots;", len(skipped), "skipped")


def freeze(out: Path, dest: Path) -> None:
    d = pd.read_parquet(out / "river_usual_days.parquet")
    spots, none = {}, []
    for (k, i), g in d.groupby(["key", "id"]):
        c = cut_points(g["p"])
        if c is None:
            none.append(i)
        else:
            spots[k] = {"id": i, **c}
    doc = {"rule": "river-usual-v1", "made": pd.Timestamp.now("UTC").strftime("%Y-%m-%d"),
           "what": "Per river spot, the cut-points at one third and two thirds of its chance of a sample over 900 on "
                   "May to September days of 2023 to 2026, hindcast at lead 0 (scripts/river_usual.py). A figure under "
                   "`low` is lower than usual there, over `high` higher, else about usual.",
           "inputs": "Open-Meteo archive rain; lead-0 hindcast exposure; soil moisture from Previous Runs lead 0 where "
                     "it exists, else today's model",
           "days_with_soil_moisture": round(float(d.loc[d["p"].notna(), "with_soil"].mean()), 3),
           "no_cut_points": sorted(none), "spots": dict(sorted(spots.items()))}
    raw = json.dumps(doc, indent=1) + "\n"
    dest.write_text(raw)
    print(len(spots), "spots with cut-points;", len(none), "without;", "sha256", hashlib.sha256(raw.encode()).hexdigest())


if __name__ == "__main__":
    if sys.argv[1] == "hindcast":
        hindcast(Path(sys.argv[2]))
    else:
        freeze(Path(sys.argv[2]), Path(sys.argv[3]))
