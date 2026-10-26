"""docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md, "Which lakes": the selection, from metadata and sample dates only.

    select_lakes.py list   <out dir>                       online: the chlorophyll-a sample dates, values dropped
    select_lakes.py choose <out dir> <wfd lakes geojson>   offline: the rule, writes lakes.json

`list` asks the Water Quality Archive for every observation of determinand 7887 dated 1 May to 30 September, one
request per season (and its CSV pages), 2020 to 2026, at every point type. Each response goes through
wqa_meta.keep_only, which keeps the point notation, label, easting, northing, type, sample time, determinand, unit,
purpose and material, and drops the result before anything is printed or saved. It writes dates.parquet.

`choose` applies the stated rule (protocol.select) to dates.parquet and the WFD Cycle 3 lake outlines, and writes
lakes.json: the chosen points, their lakes and their sample dates, plus the counts at each step.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

import chl_protocol as cp
import wqa_meta as w

DEPTHS = Path(__file__).resolve().parents[2] / "data" / "raw" / "lake_residence.csv"   # HydroLAKES mean depth


def list_dates(out: Path, http=None, sleep=None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    c = w.client(out / "ledger-select.jsonl", http, sleep)
    frames = []
    for y in cp.YEARS:
        skip = 0
        while True:
            u = w.url("/data/observation", determinand=cp.DETERMINAND, dateFrom=f"{y}-05-01",
                      dateTo=f"{y}-09-30", limit=w.CSV_LIMIT, skip=skip)
            _, body = c.request("POST", u, headers={"Accept": "text/csv"})
            page = w.keep_only(body.decode("utf-8", errors="replace"))
            del body
            frames.append(page)
            if len(page) < w.CSV_LIMIT:
                break
            skip += w.CSV_LIMIT
    df = pd.concat(frames, ignore_index=True)
    w.assert_no_values(df)
    df.to_parquet(out / "dates.parquet", index=False)
    print("listed", len(df), "observations (values dropped);", c.summary())


def choose(out: Path, wfd_geojson: Path) -> None:
    import geopandas as gpd
    dates = pd.read_parquet(out / "dates.parquet")
    w.assert_no_values(dates)
    lakes = gpd.read_file(wfd_geojson).to_crs(27700)
    res = pd.read_csv(DEPTHS)
    depth = dict(zip(res["wb_id"], res["hl_depth_avg_m"], strict=True))
    chosen, counts = cp.select(dates, lakes, depth)
    rec = {"rule": "docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md, Which lakes", "counts": counts,
           "wfd_lakes_sha256": cp.sha256(wfd_geojson), "depths_sha256": cp.sha256(DEPTHS),
           "dates_sha256": cp.sha256(out / "dates.parquet"), "points": chosen}
    (out / "lakes.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("list", "choose"):
        raise SystemExit(__doc__)
    if sys.argv[1] == "list":
        list_dates(Path(sys.argv[2]))
    else:
        choose(Path(sys.argv[2]), Path(sys.argv[3]))
