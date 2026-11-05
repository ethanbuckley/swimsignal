"""How much the shore margin matters to the satellite lake readings (docs/SATELLITE-SHORE-MARGIN-2026-11.md).

Offline, on the satellite tests' caches (read only): rebuilds each site's water with stage 1's own functions, checks the
one-pixel cores equal the saved ones, then counts pixels, sites past the size rule and usable scenes at margins of 0 to
3 pixels, and how often each shore ring is classed as not water in clear scenes. Prints JSON.

    python scripts/satellite_shore_margin.py [--sat DIR] [--chl DIR]
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


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--sat", type=Path, default=PRIVATE / "lake-algae-sat" / "out")
    a.add_argument("--chl", type=Path, default=PRIVATE / "lake-chlorophyll" / "out")
    o = a.parse_args()
    json.dump({"margins": list(MARGINS), "bathing_lakes": run_set(o.sat), "chlorophyll_points": run_set(o.chl)}, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
