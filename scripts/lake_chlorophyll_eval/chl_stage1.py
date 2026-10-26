"""docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md, stage 1: online and outcome-blind. #377's reading, at the chosen points.

    chl_stage1.py <out dir> <lakes.json> count      metadata only: item counts per point (no asset is read)
    chl_stage1.py <out dir> <lakes.json> masks      stage 1a: SCL of every item; masks, core pixels, sizes.json
    chl_stage1.py <out dir> <lakes.json> readings   stage 1b: B4 and B5 of usable scenes within PAIR_DAYS of a
                                                    sample date, features.parquet and its SHA-256
Run masks and readings again until each prints "complete"; each run stays inside the caps below and resumes from
<out dir>.

No chlorophyll value exists here. lakes.json holds the chosen points and the dates they were sampled, which are not
outcomes. Every pixel rule is scripts/lake_algae_sat_eval's (stage1.py and protocol.py, imported, unchanged): the items
over the point (1 May to 30 September 2020-2026), one water mask per point and tile from the SCL of all of them, the
connected piece within 1 km, cut to 300 m, core pixels, the size rule (9), the 80% clear rule and the median NDCI.
The only change is which usable scenes get B4 and B5: those dated within PAIR_DAYS (1) of one of the point's sample
dates, not every usable scene. A scene's date is not an outcome.

Each point is a "site" for those functions: bw_id is the WQA point notation and water_body the WFD lake id.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lake_algae_sat_eval"))
import stac  # noqa: E402
import stage1 as sat1  # noqa: E402  (#377's stage 1: site_items, scl_windows, site_geometry, readings)
from net import Capped, CapReached, Stop  # noqa: E402

import chl_protocol as cp  # noqa: E402

LIGHT = {"include": ["id", "properties.datetime", "properties.grid:code"],
         "exclude": ["links", "geometry", "bbox", "assets"]}

# Caps, written before any stage 1 request. Pace and hosts are net.py's with Amendment A1: the two AWS COG buckets
# 16 at a time with no pause, the STAC API one at a time 1 s apart; A2's check before each request.
# Estimate (statement, "Caps"), from the count step (25,148 items; 1,670 within 1 day of a sample date) and #377's
# costs: searches 284 requests and about 0.35 GB (about 14 KB an item with raster:bands); SCL about 2.1 requests and
# at most 70 KB a window, 52,800 requests and 1.76 GB; B4 and B5 for about 420 usable scenes (a quarter of 1,670) at
# about 5 requests and 2.6 MB each, 2,100 requests and 1.09 GB. In all about 55,200 requests and 3.2 GB; at #377's
# rate (about 2,100 bucket reads a minute) and 1 s a search, about 35 minutes.
COUNT_MAX_REQUESTS, COUNT_MAX_BYTES = 400, 50 * 1024**2                 # the count step, all its runs
STAGE1_MAX_REQUESTS_PER_RUN = 20_000
STAGE1_MAX_BYTES_PER_RUN = 1536 * 1024**2                               # 1.5 GiB
STAGE1_MAX_REQUESTS_TOTAL = 70_000                                      # estimate 55,200
STAGE1_MAX_BYTES_TOTAL = 4608 * 1024**2                                 # 4.5 GiB; estimate 3.2 GB


def sites(lakes_json: Path) -> list[SimpleNamespace]:
    pts = json.loads(Path(lakes_json).read_text())["points"]
    return [SimpleNamespace(bw_id=p["wqa_point"], water_body=p["wb_id"], lon=p["lon"], lat=p["lat"],
                            dates=set(p["dates"])) for p in pts]


def near(items: list[dict], dates: set[str], window: int = cp.PAIR_DAYS) -> list[dict]:
    """Items dated within `window` days of a sample date (the item's UTC date)."""
    return [i for i in items if cp.near_dates(i["properties"]["datetime"][:10], dates, window)]


def count(out: Path, lakes_json: Path) -> None:
    net = Capped(ledger=out / "ledger-count.jsonl", max_requests=COUNT_MAX_REQUESTS, max_bytes=COUNT_MAX_BYTES,
                 max_requests_total=COUNT_MAX_REQUESTS, max_bytes_total=COUNT_MAX_BYTES)
    res = {}
    for s in sites(lakes_json):
        items = []
        for y in cp.YEARS:
            items += stac.search(net, s.lon, s.lat, f"{y}-05-01", f"{y}-09-30", fields=LIGHT)
        items = list({i["id"]: i for i in items}.values())
        res[s.bw_id] = {"items": len(items),
                        "tiles": sorted({i["properties"].get("grid:code") for i in items} - {None}),
                        **{f"items_within_{w}": len(near(items, s.dates, w)) for w in (0, 1, 3)}}
    tot = {k: sum(v[k] for v in res.values()) for k in ("items", "items_within_0", "items_within_1", "items_within_3")}
    (out / "count.json").write_text(json.dumps({"points": res, "total": tot, "requests": net.summary()}, indent=1))
    print(json.dumps(tot), net.summary())


def stage1_net(out: Path) -> Capped:
    return Capped(ledger=out / "ledger-stage1.jsonl", max_requests=STAGE1_MAX_REQUESTS_PER_RUN,
                  max_bytes=STAGE1_MAX_BYTES_PER_RUN, max_requests_total=STAGE1_MAX_REQUESTS_TOTAL,
                  max_bytes_total=STAGE1_MAX_BYTES_TOTAL)


def main(out: Path, lakes_json: Path, step: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    if step == "count":
        count(out, lakes_json)
        return
    net = stage1_net(out)
    sizes, rows = {}, []
    try:
        for s in sites(lakes_json):
            items = sat1.site_items(net, out, s)
            scl = sat1.scl_windows(net, out, s, items)
            geom = sat1.site_geometry(items, scl)
            sizes[s.bw_id] = {"wb_id": s.water_body,
                              "tiles": {t: {k: v for k, v in g.items() if k != "core"} for t, g in geom.items()},
                              "in_test": any(g["passes"] for g in geom.values())}
            (out / "cores").mkdir(exist_ok=True)
            np.savez_compressed(out / "cores" / f"{s.bw_id}.npz",
                                **{t.replace("-", "_"): g["core"] for t, g in geom.items()})
            if step == "readings":
                rows += sat1.readings(net, out, s, near(items, s.dates), scl, geom)
    except (CapReached, Stop) as e:
        print(f"stopped: {e}; run again to resume", net.summary())
        sys.exit(3)
    (out / "sizes.json").write_text(json.dumps(sizes, indent=1))
    if step == "masks":
        print("stage 1a complete:", sum(v["in_test"] for v in sizes.values()), "of", len(sizes),
              "points past the size rule", net.summary())
        return
    f = pd.DataFrame(rows, columns=["bw_id", "water_body", "tile", "item_id", "scene_date", "clear_core", "n_core",
                                    "usable", "reading"])
    f = f.sort_values(["bw_id", "scene_date", "item_id"]).reset_index(drop=True)
    f.to_parquet(out / "features.parquet", index=False)
    h = cp.sha256(out / "features.parquet")
    (out / "features.sha256").write_text(h + "\n")
    print("stage 1 complete:", len(f), "rows,", int(f["usable"].sum()), "usable;", "features SHA-256", h,
          net.summary())


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[3] not in ("count", "masks", "readings"):
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
