"""How much the shore margin matters to the satellite lake readings (docs/SATELLITE-SHORE-MARGIN-2026-11.md).

Offline, on the satellite tests' caches (read only): rebuilds each site's water with stage 1's own functions, checks the
one-pixel cores equal the saved ones, then counts pixels, sites past the size rule and usable scenes at margins of 0 to
3 pixels, and how often each shore ring is classed as not water in clear scenes. Prints JSON.

    python scripts/satellite_shore_margin.py [--sat DIR] [--chl DIR]
    python scripts/satellite_shore_margin.py bands --scratch DIR [--sat DIR]

"bands" is the second band sample (docs/SATELLITE-SHORE-BANDS-2026-11.md): 50 bathing-lake scenes, B4 and B5 fetched with stage 1's own
reader through the capped client, bands and ledger kept in the scratch directory only.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "lake_algae_sat_eval"))
import protocol as pr  # noqa: E402

SEED = 20261105
SAMPLE = 50
BAND_MAX_REQUESTS = 300
BAND_MAX_BYTES = 150 * 1024**2
MATCH_TOL = 1e-6
PRIVATE = Path.home() / "Documents" / "GitHub" / "swimsignal-private"
MARGINS = (0, 1, 2, 3)


def kept(piece: np.ndarray, site: np.ndarray, k: int) -> np.ndarray:
    """Site pixels whose (2k+1)-square of neighbours is all in the connected piece; off-grid is not water.
    k = 1 is protocol.core_pixels."""
    if k == 0:
        return site.copy()
    p = np.pad(piece, k, constant_values=False)
    ok = np.ones_like(piece, dtype=bool)
    for dr in range(-k, k + 1):
        for dc in range(-k, k + 1):
            ok &= p[k + dr:k + dr + piece.shape[0], k + dc:k + dc + piece.shape[1]]
    return site & ok


def site_tiles(out: Path, site_id: str):
    """(tile, the tile's item ids, their SCL windows, the point's centre) for each tile at a site."""
    items = json.loads((out / "items" / f"{site_id}.json").read_text())
    by_tile = defaultdict(list)
    for it in items:
        by_tile[it["properties"]["grid:code"]].append(it["id"])
    for tile, ids in sorted(by_tile.items()):
        wins = []
        for i in ids:
            f = out / "scl" / site_id / f"{i}.npz"
            if f.exists():
                z = np.load(f)
                wins.append((i, z["scl"], tuple(z["centre"])))
        if wins:
            yield tile, wins


def run_set(out: Path) -> dict:
    saved = {f.stem: dict(np.load(f)) for f in sorted((out / "cores").glob("*.npz"))}
    mismatches = []
    count = {k: {"pixels": 0, "site_tiles_passing": 0, "sites_passing": set(), "usable_scenes": 0, "scenes": 0} for k in MARGINS}
    ring = {r: [0, 0] for r in ("ring1", "ring2", "ring3", "inner")}   # [not water, clear] pooled
    site_ring = {}
    for site_id in sorted(saved):
        srings = {r: [0, 0] for r in ring}
        for tile, wins in site_tiles(out, site_id):
            stack = np.stack([w for _, w, _ in wins])
            piece, site = pr.site_water(pr.water_mask(stack), wins[0][2])
            masks = {k: kept(piece, site, k) for k in MARGINS}
            key = tile.replace("-", "_")
            if key in saved[site_id] and not np.array_equal(masks[1], saved[site_id][key]):
                mismatches.append(f"{site_id} {tile}: {int(masks[1].sum())} vs saved {int(saved[site_id][key].sum())}")
            if key not in saved[site_id] and masks[1].any():
                mismatches.append(f"{site_id} {tile}: no saved core, rebuilt {int(masks[1].sum())}")
            for k in MARGINS:
                m = masks[k]
                count[k]["pixels"] += int(m.sum())
                if pr.passes_size_rule(m):
                    count[k]["site_tiles_passing"] += 1
                    count[k]["sites_passing"].add(site_id)
                    for _, w, _ in wins:
                        count[k]["scenes"] += 1
                        count[k]["usable_scenes"] += bool(pr.scene_clear(w, m)[1])
            if not pr.passes_size_rule(masks[1]):
                continue
            rings = {"ring1": masks[0] & ~masks[1], "ring2": masks[1] & ~masks[2], "ring3": masks[2] & ~masks[3], "inner": masks[3]}
            for _, w, _ in wins:
                if not pr.scene_clear(w, masks[1])[1]:
                    continue
                clear = np.isin(w, pr.CLEAR)
                for r, m in rings.items():
                    c = clear & m
                    nw = int((c & (w != pr.WATER)).sum())
                    for acc in (ring[r], srings[r]):
                        acc[0] += nw
                        acc[1] += int(c.sum())
        site_ring[site_id] = {r: (None if v[1] == 0 else round(v[0] / v[1], 4)) for r, v in srings.items()} | {
            "clear_pixel_scenes_inner": srings["inner"][1]}
    if mismatches:
        return {"stop": "the rebuilt one-pixel cores differ from the saved ones", "mismatches": mismatches}
    return {
        "sites": len(saved),
        "by_margin": {str(k): {"pixels": v["pixels"], "site_tiles_passing": v["site_tiles_passing"],
                               "sites_passing": len(v["sites_passing"]), "scenes_on_passing_tiles": v["scenes"],
                               "usable_scenes": v["usable_scenes"]} for k, v in count.items()},
        "sites_dropped_from_k1": {str(k): sorted(count[1]["sites_passing"] - count[k]["sites_passing"]) for k in MARGINS if k > 1},
        "not_water_share_in_clear_pixels": {r: {"not_water": v[0], "clear": v[1], "share": None if v[1] == 0 else round(v[0] / v[1], 4)}
                                            for r, v in ring.items()},
        "per_site_not_water_share": site_ring,
    }


def site_masks(out: Path, site_id: str) -> dict:
    """{tile: ({k: mask}, {item id: SCL window})} for each tile at a site."""
    res = {}
    for tile, wins in site_tiles(out, site_id):
        piece, site = pr.site_water(pr.water_mask(np.stack([w for _, w, _ in wins])), wins[0][2])
        res[tile] = ({k: kept(piece, site, k) for k in (0, 1, 2)}, {i: w for i, w, _ in wins})
    return res


def band_population(out: Path, features) -> list[dict]:
    """Scenes usable with a reading at k = 1, on site-tiles past the size rule at k = 2, and usable at k = 2."""
    f = features[features["usable"] & features["reading"].notna()]
    pop = []
    for site_id, g in f.groupby("bw_id"):
        masks = site_masks(out, site_id)
        for r in g.itertuples(index=False):
            m, wins = masks[r.tile]
            if pr.passes_size_rule(m[2]) and pr.scene_clear(wins[r.item_id], m[2])[1]:
                pop.append({"bw_id": site_id, "tile": r.tile, "item_id": r.item_id, "cached": float(r.reading)})
    return pop


def pick(pop: list[dict], n: int = SAMPLE, seed: int = SEED) -> list[dict]:
    """Sites in a seeded order, each site's scenes in a seeded order, one per site in turn until n."""
    rng = np.random.default_rng(seed)
    by_site = defaultdict(list)
    for r in sorted(pop, key=lambda r: (r["bw_id"], r["item_id"])):
        by_site[r["bw_id"]].append(r)
    sites = [sorted(by_site)[i] for i in rng.permutation(len(by_site))]
    queues = {s: [by_site[s][i] for i in rng.permutation(len(by_site[s]))] for s in sites}
    chosen = []
    while len(chosen) < n and any(queues.values()):
        for s in sites:
            if queues[s] and len(chosen) < n:
                chosen.append(queues[s].pop(0))
    return chosen


def describe(d: np.ndarray, spread: float) -> dict:
    a = np.abs(d)
    med, p90 = float(np.median(a)), float(np.percentile(a, 90))
    words = ("barely moves" if med <= 0.1 * spread and p90 <= 0.25 * spread
             else "moves materially" if med >= 0.25 * spread else "moves somewhat")
    return {"n": int(len(d)), "median": round(float(np.median(d)), 5),
            "iqr": [round(float(np.percentile(d, 25)), 5), round(float(np.percentile(d, 75)), 5)],
            "median_abs": round(med, 5), "p90_abs": round(p90, 5), "max_abs": round(float(a.max()), 5),
            "share_below_zero": round(float((d < 0).mean()), 3),
            "median_abs_over_spread": round(med / spread, 3), "words": words}


def band_run(out: Path, scratch: Path) -> dict:
    import pandas as pd
    import net as netmod
    import stac
    import stage1
    features = pd.read_parquet(out / "features.parquet")
    sd = features[features["usable"] & features["reading"].notna()].groupby("bw_id")["reading"].agg(["std", "size"])
    spread = float(sd[sd["size"] >= 10]["std"].median())
    pop = band_population(out, features)
    chosen = pick(pop)
    site_ll = {s.bw_id: (s.lon, s.lat) for s in pr.lake_sites(stage1.SITES).itertuples(index=False)}
    items = {}
    for site_id in {c["bw_id"] for c in chosen}:
        items.update({it["id"]: it for it in json.loads((out / "items" / f"{site_id}.json").read_text())})
    scratch.mkdir(parents=True, exist_ok=True)
    net = netmod.Capped(scratch / "band-ledger.jsonl", max_requests=BAND_MAX_REQUESTS, max_bytes=BAND_MAX_BYTES,
                        max_requests_total=BAND_MAX_REQUESTS, max_bytes_total=BAND_MAX_BYTES)
    masks = {}

    def one(c):
        it = items[c["item_id"]]
        b4_dn, b5_dn = stac.site_bands(net, it, *site_ll[c["bw_id"]])
        np.savez_compressed(scratch / f"{c['bw_id']}__{c['item_id']}.npz", b4=b4_dn, b5=b5_dn)
        b4 = pr.b4_to_20m(pr.reflectance(b4_dn, it["assets"]["red"]["raster:bands"][0]))
        b5 = pr.reflectance(b5_dn, it["assets"]["rededge1"]["raster:bands"][0])
        index = pr.ndci(b4, b5)
        m, wins = masks[c["bw_id"]][c["tile"]]
        w = wins[c["item_id"]]
        r = {}
        for k in (0, 1, 2):
            _, usable, v = pr.scene_reading(w, m[k], index)
            r[f"k{k}"] = v if usable else None
        return c | r

    for site_id in {c["bw_id"] for c in chosen}:
        masks[site_id] = site_masks(out, site_id)
    rows = list(stage1.pmap(one, chosen))   # the test's own parallel reader
    (scratch / "band-rows.json").write_text(json.dumps(rows, indent=1))
    miss = [r for r in rows if r["k1"] is None or abs(r["k1"] - r["cached"]) > MATCH_TOL]
    res = {"population": len(pop), "sample": len(rows), "sites": len({r["bw_id"] for r in rows}),
           "per_site_count": {s: sum(r["bw_id"] == s for r in rows) for s in sorted({r["bw_id"] for r in rows})},
           "spread_median_site_sd_k1": round(spread, 5), "net": net.summary()}
    if miss:
        return res | {"stop": "recomputed k = 1 readings differ from the cached ones", "misses": miss}
    res["k1_match_max_abs"] = max(abs(r["k1"] - r["cached"]) for r in rows)
    d2 = np.array([r["k2"] - r["k1"] for r in rows])
    with0 = [r for r in rows if r["k0"] is not None]
    d0 = np.array([r["k0"] - r["k1"] for r in with0])
    res["k2_minus_k1"] = describe(d2, spread)
    res["k0_minus_k1"] = describe(d0, spread) if len(d0) else None
    res["per_site_median_k2_minus_k1"] = {s: round(float(np.median([r["k2"] - r["k1"] for r in rows if r["bw_id"] == s])), 5)
                                          for s in res["per_site_count"]}
    return res


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("step", nargs="?", default="rings", choices=("rings", "bands"))
    a.add_argument("--sat", type=Path, default=PRIVATE / "lake-algae-sat" / "out")
    a.add_argument("--chl", type=Path, default=PRIVATE / "lake-chlorophyll" / "out")
    a.add_argument("--scratch", type=Path)
    o = a.parse_args()
    if o.step == "bands":
        if o.scratch is None:
            a.error("bands needs --scratch")
        json.dump(band_run(o.sat, o.scratch), sys.stdout, indent=1)
        print()
        return
    json.dump({"margins": list(MARGINS), "bathing_lakes": run_set(o.sat), "chlorophyll_points": run_set(o.chl)}, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
