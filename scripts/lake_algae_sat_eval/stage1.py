"""docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md, stage 1: online and outcome-blind.

    stage1.py <out dir> masks                 stage 1a: SCL only; the masks, core pixels and sizes.json
    stage1.py <out dir> readings [skip.txt]   stage 1b: B4 and B5 and the readings, at every site past the size
                                              rule, except at water bodies listed in skip.txt (one per line: those
                                              CLMS covers, when stage 0 makes CLMS the primary reading)
Run each again until it prints "complete"; each run stays inside the stage 1 caps.

No EA check is fetched or read here. For every lake site: every sentinel-2-c1-l2a item over its point, 1 May to
30 September 2020-2026; the SCL window around it from each item; one water mask per site and tile from all of them;
the site's water, its core pixels and the size rule; then, for each scene usable at a site past the size rule, B4 and
B5 and the median NDCI over clear core pixels.

Writes, in <out dir>:
    items/<bw_id>.json        the items found (id, date, tile, asset links, raster:bands)
    scl/<bw_id>/<item>.npy    each SCL window (resume cache; never committed)
    progress.jsonl            one line per site and item read for a reading
    sizes.json                core pixels per site and tile, in or out
    cores/<bw_id>.npz         each tile's core pixels, for stage 0 (CLMS) and the record
    features.parquet          one row per site and item on a tile past the size rule
    features.sha256           its SHA-256, to be committed before stage 2 fetches a single check

Stops (StopRule) if any item lacks raster:bands scale or offset on B4 or B5. A cap stops the run; the next run picks
up from the caches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import net as netmod
import protocol as pr
import stac
from net import Capped, CapReached

ROOT = Path(__file__).resolve().parents[2]
SITES = ROOT / "data" / "raw" / "bathing_waters_inland.json"
ITEM_FIELDS = {"include": ["id", "properties.datetime", "properties.proj:epsg", "properties.proj:code",
                           "properties.grid:code", "properties.s2:processing_baseline",
                           "assets.scl", "assets.red", "assets.rededge1"],
               "exclude": ["links", "geometry", "bbox"]}


def stage1_net(out: Path) -> Capped:
    return Capped(ledger=out / "ledger-stage1.jsonl", max_requests=netmod.STAGE1_MAX_REQUESTS_PER_RUN,
                  max_bytes=netmod.STAGE1_MAX_BYTES_PER_RUN, max_requests_total=netmod.STAGE1_MAX_REQUESTS_TOTAL,
                  max_bytes_total=netmod.STAGE1_MAX_BYTES_TOTAL)


def check_items(items: list[dict]) -> None:
    """The stop rule: every item carries scale and offset for B4 and B5."""
    for it in items:
        for a in ("red", "rededge1"):
            bands = ((it.get("assets") or {}).get(a) or {}).get("raster:bands")
            if not bands or "scale" not in bands[0] or "offset" not in bands[0]:
                raise pr.StopRule(f"{it.get('id')}: {a} lacks raster:bands scale or offset")


def site_items(net, out: Path, site) -> list[dict]:
    p = out / "items" / f"{site.bw_id}.json"
    if p.exists():
        return json.loads(p.read_text())
    items = []
    for y in pr.YEARS:
        items += stac.search(net, site.lon, site.lat, f"{y}-05-01", f"{y}-09-30", fields=ITEM_FIELDS)
    items = sorted({i["id"]: i for i in items}.values(), key=lambda i: (i["properties"]["datetime"], i["id"]))
    check_items(items)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items))
    return items


def scl_windows(net, out: Path, site, items: list[dict]) -> dict[str, tuple[np.ndarray, tuple]]:
    d = out / "scl" / site.bw_id
    d.mkdir(parents=True, exist_ok=True)
    got = {}
    for it in items:
        f = d / f"{it['id']}.npz"
        if f.exists():
            z = np.load(f)
            got[it["id"]] = (z["scl"], tuple(z["centre"]))
            continue
        w, centre = stac.site_scl(net, it, site.lon, site.lat)
        np.savez_compressed(f, scl=w, centre=np.array(centre))
        got[it["id"]] = (w, centre)
    return got


def site_geometry(items: list[dict], scl: dict) -> dict[str, dict]:
    """Per tile: the mask from every item on it, the site's water, core pixels and the size rule."""
    out = {}
    tiles = sorted({i["properties"]["grid:code"] for i in items})
    for t in tiles:
        ids = [i["id"] for i in items if i["properties"]["grid:code"] == t]
        stack = np.stack([scl[i][0] for i in ids])
        centre = scl[ids[0]][1]
        mask = pr.water_mask(stack)
        piece, site = pr.site_water(mask, centre)
        core = pr.core_pixels(piece, site)
        out[t] = {"core": core, "n_core": int(core.sum()), "n_site": int(site.sum()), "items": len(ids),
                  "passes": pr.passes_size_rule(core)}
    return out


def readings(net, out: Path, site, items: list[dict], scl: dict, geom: dict) -> list[dict]:
    prog = out / "progress.jsonl"
    done = {}
    if prog.exists():
        for line in prog.read_text().splitlines():
            r = json.loads(line)
            done[(r["bw_id"], r["item_id"])] = r
    rows = []
    for it in items:
        t = it["properties"]["grid:code"]
        g = geom[t]
        if not g["passes"]:
            continue
        key = (site.bw_id, it["id"])
        if key in done:
            rows.append(done[key])
            continue
        w = scl[it["id"]][0]
        clear, usable = pr.scene_clear(w, g["core"])
        value = float("nan")
        if usable:
            b4_dn, b5_dn = stac.site_bands(net, it, site.lon, site.lat)
            b4 = pr.b4_to_20m(pr.reflectance(b4_dn, it["assets"]["red"]["raster:bands"][0]))
            b5 = pr.reflectance(b5_dn, it["assets"]["rededge1"]["raster:bands"][0])
            _, _, value = pr.scene_reading(w, g["core"], pr.ndci(b4, b5))
        r = {"bw_id": site.bw_id, "water_body": site.water_body, "tile": t, "item_id": it["id"],
             "scene_date": it["properties"]["datetime"][:10], "clear_core": clear, "n_core": g["n_core"],
             "usable": bool(usable), "reading": None if np.isnan(value) else value}
        with prog.open("a") as f:
            f.write(json.dumps(r) + "\n")
        rows.append(r)
    return rows


def main(out: Path, step: str, skip: set[str] | None = None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    net = stage1_net(out)
    sites = pr.lake_sites(SITES)
    skip = skip or set()
    sizes, rows = {}, []
    try:
        for site in sites.itertuples(index=False):
            items = site_items(net, out, site)
            scl = scl_windows(net, out, site, items)
            geom = site_geometry(items, scl)
            sizes[site.bw_id] = {"name": site.name, "water_body": site.water_body,
                                 "tiles": {t: {k: v for k, v in g.items() if k != "core"} for t, g in geom.items()},
                                 "in_test": any(g["passes"] for g in geom.values())}
            (out / "cores").mkdir(exist_ok=True)
            np.savez_compressed(out / "cores" / f"{site.bw_id}.npz",
                                **{t.replace("-", "_"): g["core"] for t, g in geom.items()})
            if step == "readings" and site.water_body not in skip:
                rows += readings(net, out, site, items, scl, geom)
    except CapReached as e:
        print(f"stopped at a cap: {e}; run again to resume", net.summary())
        sys.exit(3)
    (out / "sizes.json").write_text(json.dumps(sizes, indent=1))
    if step == "masks":
        print("stage 1a complete:", sum(v["in_test"] for v in sizes.values()), "of", len(sizes),
              "sites past the size rule", net.summary())
        return
    f = pd.DataFrame(rows, columns=["bw_id", "water_body", "tile", "item_id", "scene_date", "clear_core", "n_core",
                                    "usable", "reading"])
    f = f.sort_values(["bw_id", "scene_date", "item_id"]).reset_index(drop=True)
    f.to_parquet(out / "features.parquet", index=False)
    h = pr.sha256(out / "features.parquet")
    (out / "features.sha256").write_text(h + "\n")
    print("stage 1 complete:", len(f), "rows,", int(f["usable"].sum()), "usable;", "features SHA-256", h, net.summary())


if __name__ == "__main__":
    step = sys.argv[2]
    if step not in ("masks", "readings"):
        raise SystemExit(__doc__)
    skip = set(Path(sys.argv[3]).read_text().split("\n")) - {""} if len(sys.argv) > 3 else set()
    main(Path(sys.argv[1]), step, skip)
