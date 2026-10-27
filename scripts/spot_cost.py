"""What listing more spots would cost in Open-Meteo calls a day, on the free tier's planned day.

The build plans for a build every 30 minutes (rainfall.planned_day): 8,873 of the 9,000 calls rationed
on 27 Oct 2026, so 127 spare. A new spot adds its weather point (9 calls a day), the spots' 12 a day
for each rain cell no listed spot has yet, less the 2 click-anywhere paid for it where it was one of
its cells, and 2 for a river spot's new soil cell (rainfall.new_spot_calls). This script places every
listed spot as the build does (build_site.spot_rain_cells) and then each candidate the same way, and
prints each candidate's new cells, its monitored overflows upstream and its cost. Nothing is fetched:
it needs the river network and the overflow table, and makes no request.

Run off CI from the repository root, with the state in a scratch folder: the overflow table is
rebuilt there on this checkout's network, so a shared copy is never overwritten (overflows.load_overflows):

    DIPCAST_STATE=/tmp/spot-cost PYTHONPATH=src:scripts python scripts/spot_cost.py [candidates.csv] [out.csv]

The candidates default to the unlisted rows of data/raw/osm_swim_candidates.csv; any CSV with lat,
lon and, optionally, kind (lake or river), river and name columns will do. The cost is the planned
most; builds run less often than every 30 minutes (a median 2.9 hours apart in September 2026), so a
day's real use is lower.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]

import build_site  # noqa: E402

from dipcast import scottish_shadow  # noqa: E402
from dipcast.ingest import rainfall, soil  # noqa: E402
from dipcast.model.forecast import _net  # noqa: E402
from dipcast.overflows import load_overflows  # noqa: E402

CANDIDATES = ROOT / "data" / "raw" / "osm_swim_candidates.csv"
# The checkout's own spot files, as scripts/eval_pins.py reads them: not DIPCAST_ROOT's, since a run in a
# scratch root has the data there but no spots.csv.
SPOT_FILES = [ROOT / "spots.csv", ROOT / "spots-osm.csv"]


def floors() -> dict:
    spec = importlib.util.spec_from_file_location("build_any_point", ROOT / "scripts" / "build_any_point.py")
    bap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bap)
    return {"anypoint_refresh_h": bap.RAIN_REFRESH_H, "weather_refresh_h": build_site.WEATHER_REFRESH_H,
            "soil_attempts": soil.MAX_ATTEMPTS}


def candidates(path: Path) -> pd.DataFrame:
    """lat, lon, kind, river, name for each candidate. The OSM file's rows: the unlisted ones, a lake
    by its link form, the watercourse as a river spot's river, the OSM name or else the watercourse."""
    c = pd.read_csv(path)
    if "listed_as" in c:
        c = c[c["listed_as"].isna()].copy()
        c["kind"] = c["form"].map(lambda f: "lake" if f == "lake" else "river")
        c["river"] = c["watercourse"].where(c["kind"] == "river")
        c["name"] = c["tag_name"].fillna(c["watercourse"])
    for col in ("kind", "river", "name"):
        if col not in c:
            c[col] = ""
    return c.fillna({"kind": "", "river": "", "name": ""}).reset_index(drop=True)


def main(path: Path = CANDIDATES, out: Path | None = None) -> pd.DataFrame:
    if not os.environ.get("DIPCAST_STATE"):
        sys.exit("set DIPCAST_STATE to a scratch folder: the overflow table is rebuilt there")
    net = _net()
    ov = load_overflows(net, rebuild=True)
    spot_cells, soil_cells = build_site.spot_rain_cells(build_site.load_spots(SPOT_FILES), net, ov)
    spot_cells, soil_cells = set(spot_cells), set(soil_cells)
    snapped = ov[ov["link_id"].notna()]   # the overflows click-anywhere asks rain for
    anypoint = set(rainfall.cells_for_sites(snapped["lat"], snapped["lon"]))
    f = floors()
    day = rainfall.planned_day(len(spot_cells), len(anypoint - spot_cells), len(build_site.load_spots(SPOT_FILES)),
                               # The Scottish shadow's cells are its own assets'; 320 on 16 Oct 2026, from its log.
                               320, len(soil_cells), scotland_refresh_h=scottish_shadow.RAIN_REFRESH_H, **f)
    print(f"listed spots: {len(spot_cells)} rain cells, {len(soil_cells)} soil cells; click-anywhere "
          f"{len(anypoint - spot_cells)} cells the spots do not share")
    print(f"planned day: {day['calls']:.0f} calls ({ {k: round(v) for k, v in day['by'].items()} }), "
          f"{day['spare']:.0f} spare of {rainfall.DAILY_CALLS:.0f}")
    rows = []
    for r in candidates(path).itertuples(index=False):
        one = pd.DataFrame([{"lat": r.lat, "lon": r.lon, "kind": r.kind, "river": r.river, "name": r.name}])
        cells, river = build_site.spot_rain_cells(one, net, ov)
        pin = build_site.locate_pin(net, float(r.lon), float(r.lat), *build_site.spot_hints(r.kind, r.river),
                                    name=r.name or None)
        up = build_site.upstream_overflows(net, pin, ov, velocity_ms=build_site.river_velocity(None))
        new = set(cells) - spot_cells
        new_soil = bool(river) and river[0] not in soil_cells
        rows.append({**r._asdict(), "mode": pin.mode, "overflows_upstream": len(up),
                     "companies": "; ".join(sorted(up["company"].fillna("unknown").astype(str).unique())) if len(up) else "",
                     "new_cells": len(new), "new_cells_from_anypoint": len(new & anypoint), "new_soil_cell": new_soil,
                     "calls_per_day": rainfall.new_spot_calls(len(new), len(new & anypoint), new_soil, **f)})
    res = pd.DataFrame(rows)
    if out:
        res.to_csv(out, index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 500):
        keep = [c for c in ("osm_id", "name", "mode", "overflows_upstream", "companies", "new_cells", "calls_per_day") if c in res]
        print(res[keep].to_string(index=False))
    return res


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else CANDIDATES, Path(sys.argv[2]) if len(sys.argv) > 2 else None)
