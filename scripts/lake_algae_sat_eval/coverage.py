"""docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md, "Coverage before the test": what each source could give at the lake
sites, counted without reading any value.

    coverage.py clms <out dir>                         CDSE catalogue metadata for CLMS Lake Water Quality 100 m v2
    coverage.py stac <out dir>                         Earth Search metadata, all 18 sites, May-September 2020-2026
    coverage.py scl <out dir> <site name> <season> [max items]
                                                       SCL only, one site, one season, the site's main tile

Blinding (Ethan, 26 October 2026): no satellite value is paired with any EA algae check, no outcome is counted and
nothing is scored. No EA check is fetched. Only "valid or not" is counted: items, dates, tile cloud flags, the scale
and offset the stop rule needs, and SCL classes. B4 and B5 are never read here, so no NDCI exists to look at; nor is
any CLMS pixel (download needs an account, which this harness does not use).

Every request goes through net.Capped and its ledger (<out dir>/ledger.jsonl). A cap stops the run; what was counted
before it is written, marked partial.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import protocol as pr
import stac
from net import Capped, CapReached, Stop

ROOT = Path(__file__).resolve().parents[2]
SITES = ROOT / "data" / "raw" / "bathing_waters_inland.json"
ODATA = ("https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$filter=Collection/Name%20eq%20%27CLMS%27%20and"
         "%20Attributes/OData.CSC.StringAttribute/any(att:att/Name%20eq%20%27datasetIdentifier%27%20and%20att/OData"
         ".CSC.StringAttribute/Value%20eq%20%27lwq-nrt_global_100m_10daily_v2%27)&$count=true&$top=500"
         "&$orderby=ContentDate/Start%20asc")
FIELDS = {"include": ["id", "properties.datetime", "properties.created", "properties.eo:cloud_cover",
                      "properties.grid:code", "properties.s2:processing_baseline", "assets.red.raster:bands",
                      "assets.rededge1.raster:bands"],
          "exclude": ["links", "geometry", "bbox"]}
LIGHT = {"include": ["id", "properties.datetime", "properties.created", "properties.eo:cloud_cover",
                     "properties.grid:code", "properties.s2:processing_baseline"],
         "exclude": ["links", "geometry", "bbox", "assets"]}


def _gaps(dates) -> list[int]:
    d = sorted(set(pd.to_datetime(list(dates)).date))
    return [(b - a).days for a, b in zip(d, d[1:])]


def _has_scale_offset(item: dict) -> bool:
    """Both bands carry raster:bands scale and offset (the stop rule's need)."""
    for a in ("red", "rededge1"):
        bands = ((item.get("assets") or {}).get(a) or {}).get("raster:bands") or [{}]
        if not all(k in bands[0] for k in ("scale", "offset")):
            return False
    return True


def _season_dates(season: int) -> tuple[str, str]:
    return f"{season}-05-01", f"{season}-09-30"


def clms(out: Path) -> dict:
    net = Capped(ledger=out / "ledger.jsonl")
    d = net.get_json(ODATA)
    rows = []
    for p in d.get("value", []):
        rows.append({"name": p["Name"], "start": p["ContentDate"]["Start"], "end": p["ContentDate"]["End"],
                     "published": p.get("PublicationDate"), "bytes": p.get("ContentLength"),
                     "fmt": "cog" if p["Name"].endswith("_cog") else "nc" if p["Name"].endswith("_nc") else "other",
                     "footprint": str(p.get("Footprint", ""))[:120]})
    df = pd.DataFrame(rows)
    res = {"source": "CDSE OData catalogue, dataset lwq-nrt_global_100m_10daily_v2 (search only, no download)",
           "count_reported": d.get("@odata.count"), "count_listed": len(df), "requests": net.summary()}
    if len(df):
        df["start_t"] = pd.to_datetime(df["start"])
        df["end_t"] = pd.to_datetime(df["end"])
        df["lag_days"] = (pd.to_datetime(df["published"]) - df["end_t"]).dt.total_seconds() / 86400
        in_season = df[df["start_t"].dt.month.isin(pr.SEASON_MONTHS)]
        res.update({
            "first_dekad": str(df["start_t"].min().date()), "last_dekad": str(df["start_t"].max().date()),
            "footprints": sorted(df["footprint"].unique().tolist()),
            "by_format": {f: int(n) for f, n in df["fmt"].value_counts().items()},
            "season_dekads": {f"{y}": {f: int(n) for f, n in g["fmt"].value_counts().items()}
                              for y, g in in_season.groupby(in_season["start_t"].dt.year)},
            "bytes_per_file_gb": {f: [round(float(g["bytes"].min()) / 1e9, 2), round(float(g["bytes"].max()) / 1e9, 2)]
                                  for f, g in df.groupby("fmt")},
            "catalogue_lag_days": {"min": round(float(df["lag_days"].min()), 1),
                                   "median": round(float(df["lag_days"].median()), 1),
                                   "max": round(float(df["lag_days"].max()), 1)},
            "catalogue_lag_days_by_year": {f"{y}": round(float(g["lag_days"].median()), 1)
                                           for y, g in df.groupby(df["end_t"].dt.year)},
        })
    res["site_coverage"] = ("not measurable here: every product is one global file (footprint the whole globe), and "
                            "reading any pixel needs a CDSE account")
    return res


def stac_meta(out: Path, done: Path | None = None) -> dict:
    """With `done` (an earlier run's output that stopped at a cap), only the site-seasons it lacks, and with the
    light fields: the first run showed that asking for the bands' raster:bands returns whole items (about 14 KB
    each), so the scale and offset count is left out (None) for these."""
    net = Capped(ledger=out / "ledger.jsonl")
    sites = pr.lake_sites(SITES)
    have = json.loads(done.read_text())["sites"] if done else {}
    res, partial = {}, None
    try:
        for s in sites.itertuples(index=False):
            for season in pr.YEARS:
                if str(season) in have.get(s.name, {}):
                    continue
                a, b = _season_dates(season)
                items = stac.search(net, s.lon, s.lat, a, b, fields=LIGHT if done else FIELDS)
                dates = [i["properties"]["datetime"][:10] for i in items]
                tiles = pd.Series([i["properties"].get("grid:code") for i in items]).value_counts()
                lag_h = [(pd.Timestamp(i["properties"]["created"]) - pd.Timestamp(i["properties"]["datetime"]))
                         .total_seconds() / 3600 for i in items if i["properties"].get("created")]
                scale_ok = sum(_has_scale_offset(i) for i in items)
                gaps = _gaps(dates)
                res.setdefault(s.name, {})[season] = {
                    "items": len(items), "dates": len(set(dates)), "tiles": {k: int(v) for k, v in tiles.items()},
                    "items_tile_cloud_under_50": int(sum(i["properties"].get("eo:cloud_cover", 100) < 50 for i in items)),
                    "dates_tile_cloud_under_50": len({i["properties"]["datetime"][:10] for i in items
                                                      if i["properties"].get("eo:cloud_cover", 100) < 50}),
                    "gap_days_median": float(np.median(gaps)) if gaps else None, "gap_days_max": max(gaps) if gaps else None,
                    "created_minus_sensed_hours_median": round(float(np.median(lag_h)), 1) if lag_h else None,
                    "items_with_scale_and_offset": None if done else int(scale_ok),
                    "baselines": sorted({i["properties"].get("s2:processing_baseline") for i in items} - {None}),
                }
    except (CapReached, Stop) as e:
        partial = str(e)
    return {"source": "Earth Search sentinel-2-c1-l2a, metadata only", "sites": res, "partial": partial,
            "requests": net.summary()}


def gap_2022(out: Path) -> dict:
    """The first metadata run found no sentinel-2-c1-l2a item at any site in May-September 2022. Two searches at
    Millerground Landing: C1 over the whole of 2022, and the older sentinel-2-l2a collection over May-September 2022."""
    net = Capped(ledger=out / "ledger.jsonl")
    lon, lat = -2.922541, 54.380714
    c1 = stac.search(net, lon, lat, "2022-01-01", "2022-12-31", fields=LIGHT)
    old_body = {"collections": ["sentinel-2-l2a"], "intersects": {"type": "Point", "coordinates": [lon, lat]},
                "datetime": "2022-05-01T00:00:00Z/2022-09-30T23:59:59Z", "limit": stac.PAGE, "fields": LIGHT}
    old = net.post_json(stac.SEARCH, old_body).get("features", [])
    return {"c1_items_2022_whole_year": len(c1),
            "c1_months_2022": sorted({i["properties"]["datetime"][:7] for i in c1}),
            "old_l2a_items_may_sep_2022": len(old),
            "old_l2a_dates_may_sep_2022": len({i["properties"]["datetime"][:10] for i in old}),
            "old_l2a_baselines": sorted({i["properties"].get("s2:processing_baseline") for i in old} - {None}),
            "requests": net.summary()}


def scl_sample(out: Path, site_name: str, season: int, max_items: int) -> dict:
    """SCL windows at one site, one season, on the tile with most items over the point (ties: first by name). The
    water mask is built from these scenes only (the stated one uses every season), so its counts are a preview."""
    net = Capped(ledger=out / "ledger.jsonl")
    sites = pr.lake_sites(SITES)
    s = sites[sites["name"] == site_name].iloc[0]
    a, b = _season_dates(season)
    res = {"site": site_name, "season": season, "max_items": max_items, "partial": None}
    stack, ids, dates, centre = [], [], [], None
    try:
        meta = stac.search(net, s.lon, s.lat, a, b, fields={"include": ["id", "properties.datetime", "properties.grid:code"],
                                                            "exclude": ["links", "geometry", "bbox", "assets"]})
        tiles = pd.Series([i["properties"]["grid:code"] for i in meta]).value_counts()
        tile = sorted(tiles[tiles == tiles.max()].index)[0]
        full = stac.search(net, s.lon, s.lat, a, b, query={"grid:code": {"eq": tile}},
                           fields={"include": ["id", "properties.datetime", "properties.proj:epsg", "properties.proj:code",
                                               "properties.grid:code", "assets.scl"],
                                   "exclude": ["links", "geometry", "bbox"]})
        full = sorted(full, key=lambda i: (i["properties"]["datetime"], i["id"]))
        if len(full) > max_items:   # evenly spaced through the season, first and last kept
            pick = np.unique(np.linspace(0, len(full) - 1, max_items).round().astype(int))
            full = [full[i] for i in pick]
        res.update({"tile": tile, "items_on_tile": int(tiles.max()), "items_in_season_all_tiles": len(meta)})
        for it in full:
            w, centre = stac.site_scl(net, it, s.lon, s.lat)
            stack.append(w)
            ids.append(it["id"])
            dates.append(it["properties"]["datetime"][:10])
    except (CapReached, Stop) as e:
        res["partial"] = str(e)
    if not stack:
        res["requests"] = net.summary()
        return res
    st = np.stack(stack)
    # Kept in the scratch out dir (never committed) so the counts can be redone without fetching again.
    np.savez_compressed(out / f"scl-{site_name.split(',')[0].replace(' ', '_')}-{season}.npz", scl=st,
                        dates=np.array(dates), ids=np.array(ids), centre=np.array(centre))
    mask = pr.water_mask(st)
    piece, site = pr.site_water(mask, centre)
    core = pr.core_pixels(piece, site)
    per = [pr.scene_clear(x, core) for x in st]
    usable_dates = sorted({d for d, (_, u) in zip(dates, per) if u})
    gaps = _gaps(usable_dates)
    res.update({
        "items_read": len(stack), "window_px": list(st.shape[1:]), "water_px_in_window": int(mask.sum()),
        "piece_px": int(piece.sum()), "site_px": int(site.sum()), "core_px": int(core.sum()),
        "passes_size_rule": pr.passes_size_rule(core),
        "usable_items": int(sum(u for _, u in per)), "usable_dates": len(usable_dates),
        "usable_dates_list": usable_dates,
        "gap_days_median": float(np.median(gaps)) if gaps else None, "gap_days_max": max(gaps) if gaps else None,
        "requests": net.summary()})
    return res


def main(argv: list[str]) -> None:
    cmd, out = argv[1], Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    if cmd == "clms":
        r = clms(out)
    elif cmd == "stac":
        r = stac_meta(out, Path(argv[3]) if len(argv) > 3 else None)
        if len(argv) > 3:
            cmd = "stac-rest"
    elif cmd == "gap2022":
        r = gap_2022(out)
    elif cmd == "scl":
        r = scl_sample(out, argv[3], int(argv[4]), int(argv[5]) if len(argv) > 5 else 70)
    else:
        raise SystemExit(__doc__)
    name = f"coverage-{cmd}" + (f"-{argv[3].split(',')[0].replace(' ', '_')}-{argv[4]}" if cmd == "scl" else "")
    (out / f"{name}.json").write_text(json.dumps(r, indent=1, default=str))
    print(json.dumps(r.get("requests")), r.get("partial"))


if __name__ == "__main__":
    main(sys.argv)
