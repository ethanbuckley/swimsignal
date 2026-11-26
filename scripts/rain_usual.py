"""Each river spot's rain cut-points for the word "more, about or less rain than usual here in the last two days" at
spots with no monitored overflow upstream (docs/RAIN-WORD-NO-OVERFLOW-2026-11.md; read by src/dipcast/rain_usual.py).
Off CI, by hand, offline:

    export DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch>/state
    export DIPCAST_CACHE=<scratch cache: rain/archive_*.parquet (Open-Meteo's archive) for the spots' cells, 2023-26>
    python scripts/rain_usual.py freeze data/processed/rain_usual.v1.json

For every river spot in spots.csv and spots-osm.csv: the rain at the spot's own cell in the 48 hours to 12:00 local
on each day, and the cut-points at one third and two thirds, to 0.1 mm, separately for October to April days
(1 February 2023 to the last day on disk, up to 11 November 2026) and May to September days of 2023 to 2026. The
statement's rule: fewer than 300 days, or cut-points closer than 1.0 mm, and the season gets none. The page uses the
word only where the forecast finds no monitored overflow upstream. No request is made and no sample is read."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE / "rain_word"))

TZ = "Europe/London"
RULE = "rain-usual-v1"
WINTER_FIRST, WINTER_LAST = "2023-02-01", "2026-11-11"
SUMMER_YEARS = (2023, 2024, 2025, 2026)


def days(season: str) -> pd.DatetimeIndex:
    if season == "winter":
        d = pd.date_range(WINTER_FIRST, WINTER_LAST, freq="D", tz=TZ)
        return d[d.month.isin((10, 11, 12, 1, 2, 3, 4))]
    return pd.DatetimeIndex([x for y in SUMMER_YEARS for x in pd.date_range(f"{y}-05-01", f"{y}-09-30", freq="D", tz=TZ)])


def freeze(out: Path) -> dict:
    import os
    assert all(k in os.environ for k in ("DIPCAST_ROOT", "DIPCAST_STATE", "DIPCAST_CACHE")), "scratch roots only"
    import rain_word_read as rw
    from validate_ecoli import load_rain

    from dipcast.ingest.rainfall import grid_cell
    from dipcast.river_usual import key
    spots = pd.concat([pd.read_csv(REPO / f) for f in ("spots.csv", "spots-osm.csv") if (REPO / f).exists()], ignore_index=True)
    spots = spots[spots["kind"] == "river"].drop_duplicates("id")
    hourly = load_rain().set_index(["cell_lat", "cell_lon"]).sort_index()
    doc_spots, none = {}, {}
    for r in spots.itertuples():
        cell = tuple(float(v) for v in grid_cell(float(r.lat), float(r.lon)))
        try:
            h = hourly.loc[cell].set_index("time")["precip_mm"].sort_index()
        except KeyError:
            none[r.id] = "no rain on disk for its cell"
            continue
        c = {s: rw.cut_points(rw.day_rain(h, days(s))) for s in ("winter", "summer")}
        if not any(c.values()):
            none[r.id] = "too few days or no spread"
            continue
        doc_spots[key(r.lat, r.lon)] = {"id": r.id, **{s: v for s, v in c.items() if v}}
    doc = {"rule": RULE, "made": pd.Timestamp.now(tz=TZ).date().isoformat(),
           "what": ("Per river spot, the cut-points at one third and two thirds of the rain at its own cell in the 48 hours to "
                    "12:00 local, to 0.1 mm: winter from October to April days, 1 February 2023 to 11 November 2026; summer "
                    "from May to September days of 2023 to 2026. Rain under `low` is less than usual there, over `high` more, "
                    "else about. Used only where no monitored overflow is found upstream (docs/RAIN-WORD-NO-OVERFLOW-2026-11.md)."),
           "inputs": "Open-Meteo archive rain (hourly), the same cache as river_usual.v1.json", "min_days": rw.MIN_DAYS,
           "min_gap_mm": rw.MIN_GAP, "no_cut_points": none, "spots": dict(sorted(doc_spots.items()))}
    raw = (json.dumps(doc, indent=1) + "\n").encode()
    out.write_bytes(raw)
    return {"spots": len(doc_spots), "no_cut_points": none, "sha256": hashlib.sha256(raw).hexdigest()}


if __name__ == "__main__":
    assert sys.argv[1] == "freeze", sys.argv[1]
    print(json.dumps(freeze(Path(sys.argv[2])), indent=1))
