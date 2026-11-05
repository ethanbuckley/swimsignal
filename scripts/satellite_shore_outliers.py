"""Shore-margin outliers: the images behind the biggest margin shifts, and reading-time sensitivity flags
(docs/SATELLITE-SHORE-OUTLIERS-2026-11.md). Exploratory, on the satellite test's caches (read only).

    python scripts/satellite_shore_outliers.py prepare --out DIR            # offline: freeze the selection
    python scripts/satellite_shore_outliers.py read --out DIR               # one capped fetch of B4, B5 (and TCI)
    python scripts/satellite_shore_outliers.py report --out DIR [--sample2 DIR]   # diagnostics, flags, pictures

Pixels stay in DIR (scratch). The report writes data/research/satellite_shore_outliers_2026_11.json (values, no pixels)
and the record's pictures under docs/. The flags are proposals for a reading's own diagnostics; none says anything about
algae, toxins or whether water is safe.
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
from satellite_shore_bands import CACHE, digest, input_files  # noqa: E402
from satellite_shore_margin import kept, site_masks  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261105
MAX_REQUESTS = 200
MAX_BYTES = 120 * 1024**2
MOVE = 0.02             # the descriptive "moved" size of the band comparison, not a threshold of any other kind
# Flag thresholds, fixed after the second sample's pixels were examined and before the fetch (so: exploratory).
DARK = 0.015            # median B4 + B5 reflectance over the clear core below this: dark water, index noisy
SPREAD = 0.10           # interquartile range of pixel NDCI over the clear core at or above this
NARROW = 0.40           # share of the one-pixel core that the two-pixel margin removes, at or above this
PAIR_BIG, PAIR_SMALL = 0.20, 0.02
PAIRS_EACH = 4
TCI_SCENES = (("uki1106-11940", "S2C_T30UXC_20260624T111341_L2A"), ("uki1106-11940", "S2B_T30UXC_20260626T110334_L2A"),
              ("ukd1203-45625", "S2C_T30UVF_20250712T112136_L2A"), ("ukd1230-45775", "S2B_T30UVF_20250518T112113_L2A"))
PARTNERS = (("ukd1203-45625", "MGRS-30UWF", "S2C_T30UWF_20250712T112136_L2A"),
            ("ukd1230-45775", "MGRS-30UVF", "S2A_T30UVF_20250518T113332_L2A"),
            ("uki1106-11940", "MGRS-30UXC", "S2B_T30UXC_20260626T110334_L2A"))
FIRST = ROOT / "data/research/satellite_shore_bands_2026_11.json"
OUTPUT = ROOT / "data/research/satellite_shore_outliers_2026_11.json"
PICTURES = ROOT / "docs"


# ------------------------------------------------------------------ pure: diagnostics and flags
def diagnostics(scl: np.ndarray, masks: dict, b4: np.ndarray, b5: np.ndarray) -> dict:
    """Per-scene figures from what a reading already has: the SCL window, the site's masks at margins 0-2, and the
    B4 (20 m) and B5 reflectance windows. Readings follow protocol.scene_reading at each margin."""
    index = pr.ndci(b4, b5)
    clear = np.isin(scl, pr.CLEAR)
    out = {}
    for k in (0, 1, 2):
        n, usable, v = pr.scene_reading(scl, masks[k], index)
        out[f"k{k}"] = None if not usable or not np.isfinite(v) else round(float(v), 6)
        out[f"clear_k{k}"] = n
    core = masks[1] & clear
    v = index[core]
    v = v[np.isfinite(v)]
    bright = (b4 + b5)[core]
    bright = bright[np.isfinite(bright)]
    inner, ring = masks[2] & clear, core & ~masks[2]
    q = np.percentile(v, [25, 75]) if len(v) else (np.nan, np.nan)
    out.update({
        "n_core": int(core.sum()), "n_inner": int(inner.sum()),
        "ring_share": round(float(1 - masks[2].sum() / masks[1].sum()), 4) if masks[1].sum() else None,
        "iqr": round(float(q[1] - q[0]), 5) if len(v) else None,
        "brightness": round(float(np.median(bright)), 5) if len(bright) else None,
        "dark_share": round(float(np.mean(bright < 2 * DARK)), 4) if len(bright) else None,
        "contrast": (round(float(np.nanmedian(index[ring]) - np.nanmedian(index[inner])), 5)
                     if ring.sum() and inner.sum() and np.isfinite(index[ring]).any() and np.isfinite(index[inner]).any()
                     else None),
        "not_water_in_core": int((core & (scl != pr.WATER)).sum()),
    })
    out["shift"] = None if out["k1"] is None or out["k2"] is None else round(out["k2"] - out["k1"], 6)
    return out


def flags(d: dict) -> dict:
    """The proposed reading-time flags. `any` is their union. None of them uses the two-pixel reading."""
    f = {"dark": d.get("brightness") is not None and d["brightness"] < DARK,
         "spread": d.get("iqr") is not None and d["iqr"] >= SPREAD,
         "narrow": d.get("ring_share") is not None and d["ring_share"] >= NARROW}
    f["any"] = any(f.values())
    return f


def evaluate(rows: list[dict]) -> dict:
    """How each flag relates to a shift of at least MOVE, over rows with a shift. Descriptive counts only."""
    rows = [r for r in rows if r.get("shift") is not None]
    moved = [abs(r["shift"]) >= MOVE for r in rows]
    out = {"scenes": len(rows), "moved": int(sum(moved))}
    for name in ("dark", "spread", "narrow", "any"):
        on = [r["flags"][name] for r in rows]
        out[name] = {"flagged": int(sum(on)), "moved_and_flagged": int(sum(a and b for a, b in zip(on, moved))),
                     "moved_not_flagged": int(sum(b and not a for a, b in zip(on, moved))),
                     "median_abs_shift_flagged": _median([abs(r["shift"]) for r, a in zip(rows, on) if a]),
                     "median_abs_shift_unflagged": _median([abs(r["shift"]) for r, a in zip(rows, on) if not a])}
    return out


def _median(v):
    return None if not v else round(float(np.median(v)), 5)


def pair_test(pairs: list[dict], by_scene: dict) -> dict:
    """H1: in a big-disagreement pair, the scene with the larger |reading| is dark (brightness < DARK) or spread
    (IQR >= SPREAD); in a small-disagreement pair neither scene is. Counts per pair."""
    out = []
    for p in pairs:
        d = [by_scene[(p["site"], i)] for i in p["items"]]
        extreme = int(np.argmax([abs(x["k1"]) if x["k1"] is not None else 0 for x in d]))
        out.append({**p, "brightness": [x["brightness"] for x in d], "iqr": [x["iqr"] for x in d],
                    "extreme_scene": p["items"][extreme],
                    "extreme_dark_or_spread": bool(flags(d[extreme])["dark"] or flags(d[extreme])["spread"]),
                    "either_dark_or_spread": any(flags(x)["dark"] or flags(x)["spread"] for x in d)})
    big = [p for p in out if p["kind"] == "big"]
    small = [p for p in out if p["kind"] == "small"]
    return {"pairs": out,
            "big": {"n": len(big), "extreme_dark_or_spread": sum(p["extreme_dark_or_spread"] for p in big)},
            "small": {"n": len(small), "either_dark_or_spread": sum(p["either_dark_or_spread"] for p in small)}}


# ------------------------------------------------------------------ selection (offline)
def same_day_pairs(features) -> list[dict]:
    """Usable readings at one site, date and tile from two satellites: (site, date, tile, items, readings, range)."""
    f = features[features["usable"] & features["reading"].notna()].copy()
    f["sat"] = f["item_id"].str[:3]
    pairs = []
    for (sid, date, tile), g in f.groupby(["bw_id", "scene_date", "tile"]):
        if g["sat"].nunique() > 1:
            g = g.sort_values("item_id")
            pairs.append({"site": sid, "date": str(date), "tile": tile, "items": list(g["item_id"]),
                          "cached": [float(x) for x in g["reading"]],
                          "range": round(float(g["reading"].max() - g["reading"].min()), 5)})
    return pairs


def choose_pairs(pairs: list[dict], taken: set, seed: int = SEED, each: int = PAIRS_EACH) -> list[dict]:
    """Seeded: `each` big (range >= PAIR_BIG) and `each` small (range <= PAIR_SMALL) pairs, at most one per site,
    none holding a scene already selected. Deterministic order: sorted, then a seeded permutation."""
    rng = np.random.default_rng(seed)
    chosen = []
    for kind, keep in (("big", lambda p: p["range"] >= PAIR_BIG), ("small", lambda p: p["range"] <= PAIR_SMALL)):
        pool = sorted((p for p in pairs if keep(p) and not any((p["site"], i) in taken for i in p["items"])),
                      key=lambda p: (p["site"], p["date"], p["tile"]))
        sites = set()
        for i in rng.permutation(len(pool)):
            p = pool[i]
            if p["site"] in sites or sum(c["kind"] == kind for c in chosen) >= each:
                continue
            sites.add(p["site"])
            chosen.append({**p, "kind": kind})
    return chosen


def prepare(out: Path) -> None:
    import pandas as pd
    out.mkdir(parents=True, exist_ok=True)
    fingerprint = digest(input_files())
    sites = pr.lake_sites(ROOT / "data/raw/bathing_waters_inland.json").set_index("bw_id")
    first = json.loads(FIRST.read_text())["rows"]
    selected = []

    def add(sid, tile, item, why):
        if any(s["site"] == sid and s["id"] == item for s in selected):
            return
        selected.append({"site": sid, "tile": tile, "id": item, "why": why, "tci": (sid, item) in TCI_SCENES,
                         "lat": float(sites.loc[sid, "lat"]), "lon": float(sites.loc[sid, "lon"])})

    for r in sorted(first, key=lambda r: -abs(r["ndci_margin_2"] - r["ndci_margin_1"])):
        if abs(r["ndci_margin_2"] - r["ndci_margin_1"]) >= MOVE:
            add(r["site_id"], r["tile"], r["scene_id"], "first-sample mover")
    for sid, tile, item in PARTNERS:
        add(sid, tile, item, "partner")
    taken = {(s["site"], s["id"]) for s in selected}
    features = pd.read_parquet(CACHE / "features.parquet")
    pairs = choose_pairs(same_day_pairs(features), taken)
    # The 18 May 2025 Coniston pair is already in the selection (a mover and its partner): it counts as a big pair.
    pairs.append({"site": "ukd1230-45775", "date": "2025-05-18", "tile": "MGRS-30UVF",
                  "items": ["S2A_T30UVF_20250518T113332_L2A", "S2B_T30UVF_20250518T112113_L2A"],
                  "cached": [-0.040268, -0.46681], "range": 0.42654, "kind": "big", "note": "already selected"})
    for p in pairs:
        for item in p["items"]:
            add(p["site"], p["tile"], item, f"same-day pair ({p['kind']})")
    # Every selected scene must have a cached SCL window and item; a cached one-pixel reading where it exists.
    for s in selected:
        if not (CACHE / "scl" / s["site"] / f"{s['id']}.npz").exists():
            raise ValueError(f"no cached SCL window: {s['site']} {s['id']}")
        f = features[(features["bw_id"] == s["site"]) & (features["item_id"] == s["id"])]
        s["cached"] = None if f.empty or not np.isfinite(f["reading"].iloc[0]) else float(f["reading"].iloc[0])
    if fingerprint != digest(input_files()):
        raise ValueError("Inputs changed during selection")
    result = {"fingerprint_sha256": fingerprint, "input_file_count": len(input_files()), "seed": SEED,
              "caps": {"requests": MAX_REQUESTS, "bytes": MAX_BYTES}, "selected": selected, "pairs": pairs,
              "pair_population": {"big": sum(p["range"] >= PAIR_BIG for p in same_day_pairs(features)),
                                  "small": sum(p["range"] <= PAIR_SMALL for p in same_day_pairs(features))}}
    (out / "selection.json").write_text(json.dumps(result, indent=1) + "\n")
    print(f"{len(selected)} scenes ({sum(s['tci'] for s in selected)} with TCI), {len(pairs)} pairs; "
          f"inputs unchanged; frozen at {out / 'selection.json'}")


# ------------------------------------------------------------------ the one capped fetch
def read(out: Path) -> None:
    import stac
    from net import Capped
    selection = json.loads((out / "selection.json").read_text())
    before = digest(input_files())
    if before != selection["fingerprint_sha256"]:
        raise ValueError("Inputs changed since selection")
    ledger = out / "network.jsonl"
    if ledger.exists():
        raise ValueError("A network run already exists; no retry under this protocol")
    (out / "bands").mkdir(exist_ok=True)
    net = Capped(ledger=ledger, max_requests=MAX_REQUESTS, max_requests_total=MAX_REQUESTS,
                 max_bytes=MAX_BYTES, max_bytes_total=MAX_BYTES)
    done = []
    try:
        for s in selection["selected"]:
            items = {it["id"]: it for it in json.loads((CACHE / "items" / f"{s['site']}.json").read_text())}
            it = items[s["id"]]
            for asset in ("red", "rededge1"):
                b = it["assets"][asset]["raster:bands"][0]
                if "scale" not in b or "offset" not in b:
                    raise ValueError(f"Missing scale or offset: {s['id']} {asset}")
            b4, b5 = stac.site_bands(net, it, s["lon"], s["lat"])
            arrays = {"b4": b4, "b5": b5}
            if s["tci"]:
                if it["assets"]["visual"]["proj:transform"] != it["assets"]["red"]["proj:transform"]:
                    raise ValueError(f"{s['id']}: the TCI is not on the 10 m grid")
                r0, r1, c0, c1, _ = stac.window_for(it, "scl", s["lon"], s["lat"])
                arrays["tci"] = stac.read(net, it, "visual", 2 * r0, 2 * r1, 2 * c0, 2 * c1)
            np.savez_compressed(out / "bands" / f"{s['site']}__{s['id']}.npz", **arrays)
            done.append(s["id"])
            print(f"{len(done)}/{len(selection['selected'])} {s['site']} {s['id']} "
                  f"{net.requests} req {net.bytes / 1024**2:.1f} MiB", flush=True)
    finally:
        after = digest(input_files())
        (out / "run.json").write_text(json.dumps({"network": net.summary(), "before": before, "after": after,
                                                 "completed": len(done)}, indent=1) + "\n")
        if after != before:
            raise ValueError("Inputs changed during network run")


# ------------------------------------------------------------------ report
def scene_arrays(site: str, item_id: str, npz: Path):
    items = {it["id"]: it for it in json.loads((CACHE / "items" / f"{site}.json").read_text())}
    it = items[item_id]
    with np.load(npz) as z:
        b4 = pr.b4_to_20m(pr.reflectance(z["b4"], it["assets"]["red"]["raster:bands"][0]))
        b5 = pr.reflectance(z["b5"], it["assets"]["rededge1"]["raster:bands"][0])
        tci = z["tci"] if "tci" in z else None
    return it, b4, b5, tci


def report(out: Path, sample2: Path | None) -> None:
    selection = json.loads((out / "selection.json").read_text())
    run = json.loads((out / "run.json").read_text())
    masks = {}
    rows, pictures = [], []

    def one(site, tile, item_id, npz, source):
        if site not in masks:
            masks[site] = site_masks(CACHE, site)
        m, wins = masks[site][tile]
        it, b4, b5, tci = scene_arrays(site, item_id, npz)
        d = diagnostics(wins[item_id], m, b4, b5)
        d["flags"] = flags(d)
        return {"site": site, "tile": tile, "id": item_id, "date": it["properties"]["datetime"][:10],
                "baseline": it["properties"].get("s2:processing_baseline"), "source": source, **d}, (wins[item_id], m, b4, b5, tci)

    for s in selection["selected"]:
        npz = out / "bands" / f"{s['site']}__{s['id']}.npz"
        if not npz.exists():
            continue
        row, arrays = one(s["site"], s["tile"], s["id"], npz, s["why"])
        row["cached"] = s["cached"]
        if s["cached"] is not None and row["k1"] is not None and abs(row["k1"] - s["cached"]) > 1e-6:
            raise ValueError(f"recomputed one-pixel reading differs from the cache: {s['site']} {s['id']}")
        rows.append(row)
        if s["tci"] or s["why"] == "first-sample mover":
            pictures.append((row, arrays))
    sample2_rows = []
    if sample2 is not None:
        for r in json.loads((sample2 / "band-rows.json").read_text()):
            row, arrays = one(r["bw_id"], r["tile"], r["item_id"], sample2 / f"{r['bw_id']}__{r['item_id']}.npz", "second sample")
            if abs(row["k1"] - r["k1"]) > 1e-6:
                raise ValueError(f"second-sample reading differs: {r['bw_id']} {r['item_id']}")
            sample2_rows.append(row)
    by_scene = {(r["site"], r["id"]): r for r in rows}
    pairs = [p for p in selection["pairs"] if all((p["site"], i) in by_scene for i in p["items"])]
    result = {
        "description": "Exploratory diagnostics of selected satellite lake scenes behind the shore-margin outliers, and "
                       "reading-time sensitivity flags; not algae, toxin, safety or accuracy estimates.",
        "source": "Contains modified Copernicus Sentinel data 2020-2026. Sentinel-2 L2A via Earth Search; existing "
                  "SwimSignal water masks and scene-classification cache.",
        "protocol": "docs/SATELLITE-SHORE-OUTLIERS-2026-11.md",
        "thresholds": {"move": MOVE, "dark": DARK, "spread": SPREAD, "narrow": NARROW, "pair_big": PAIR_BIG, "pair_small": PAIR_SMALL},
        "seed": SEED, "input_fingerprint_sha256": selection["fingerprint_sha256"],
        "fingerprint_unchanged": run["before"] == run["after"] == selection["fingerprint_sha256"],
        "network": run["network"], "caps": selection["caps"], "completed": run["completed"],
        "selected": len(selection["selected"]),
        "rows": rows, "pair_test": pair_test(pairs, by_scene),
        "flags_on_fetched": evaluate(rows), "flags_on_second_sample": evaluate(sample2_rows),
        "flags_on_both": evaluate(rows + sample2_rows),
        "second_sample_rows": sample2_rows,
    }
    OUTPUT.write_text(json.dumps(result, indent=1) + "\n")
    for row, arrays in pictures:
        draw(row, *arrays)
    print(json.dumps({k: result[k] for k in ("network", "completed", "pair_test", "flags_on_fetched", "flags_on_second_sample", "flags_on_both")}, indent=1))


# ------------------------------------------------------------------ pictures
INDEX_RANGE = (-0.2, 0.4)
INDEX_COLOURS = np.array([[37, 52, 148], [44, 127, 184], [65, 182, 196], [161, 218, 180], [255, 255, 204]], float)
SCL_COLOURS = {0: (0, 0, 0), 1: (255, 0, 0), 2: (60, 60, 60), 3: (120, 80, 40), 4: (40, 160, 40), 5: (200, 170, 100),
               6: (30, 60, 200), 7: (150, 150, 150), 8: (210, 210, 210), 9: (240, 240, 240), 10: (120, 200, 255), 11: (255, 120, 255)}
SCALE = 4


def index_rgb(v: np.ndarray) -> np.ndarray:
    lo, hi = INDEX_RANGE
    x = np.clip((np.nan_to_num(v, nan=lo) - lo) / (hi - lo), 0, 1) * (len(INDEX_COLOURS) - 1)
    i = np.minimum(np.floor(x).astype(int), len(INDEX_COLOURS) - 2)
    f = (x - i)[..., None]
    rgb = INDEX_COLOURS[i] * (1 - f) + INDEX_COLOURS[i + 1] * f
    rgb[~np.isfinite(v)] = (0, 0, 0)
    return rgb


def outline(rgb: np.ndarray, mask: np.ndarray, colour, scale: int = SCALE) -> None:
    """Draw the mask's outer edge, one picture pixel wide, on an upscaled RGB picture (in place)."""
    p = np.pad(mask, 1, constant_values=False)
    edge = mask & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    for r, c in zip(*np.nonzero(edge)):
        rr, cc = slice(r * scale, (r + 1) * scale), slice(c * scale, (c + 1) * scale)
        top, bottom, left, right = r == 0 or not mask[r - 1, c], r == mask.shape[0] - 1 or not mask[r + 1, c], \
            c == 0 or not mask[r, c - 1], c == mask.shape[1] - 1 or not mask[r, c + 1]
        if top:
            rgb[r * scale, cc] = colour
        if bottom:
            rgb[(r + 1) * scale - 1, cc] = colour
        if left:
            rgb[rr, c * scale] = colour
        if right:
            rgb[rr, (c + 1) * scale - 1] = colour


def draw(row: dict, scl: np.ndarray, m: dict, b4: np.ndarray, b5: np.ndarray, tci) -> Path:
    """Three panels at 20 m, upscaled: true colour (black where not fetched), scene classes, NDCI over the site's
    water (margin 0), with the one- and two-pixel masks outlined in white and yellow."""
    from PIL import Image
    rows, cols = np.nonzero(m[0])
    r0, r1 = max(rows.min() - 6, 0), min(rows.max() + 7, scl.shape[0])
    c0, c1 = max(cols.min() - 6, 0), min(cols.max() + 7, scl.shape[1])
    crop = (slice(r0, r1), slice(c0, c1))
    h, w = r1 - r0, c1 - c0
    panels = []
    if tci is not None:
        t = tci[2 * r0:2 * r1, 2 * c0:2 * c1].astype(float)
        t = t.reshape(h, 2, w, 2, 3).mean(axis=(1, 3))
        panels.append(np.clip(t, 0, 255))
    else:
        panels.append(np.zeros((h, w, 3)))
    sc = np.zeros((h, w, 3))
    for v, colour in SCL_COLOURS.items():
        sc[scl[crop] == v] = colour
    panels.append(sc)
    index = pr.ndci(b4, b5)
    nd = index_rgb(np.where(m[0], index, np.nan)[crop])
    panels.append(nd)
    up = [np.kron(p, np.ones((SCALE, SCALE, 1))) for p in panels]
    for p in up:
        outline(p, m[1][crop], (255, 255, 255))
        outline(p, m[2][crop], (255, 220, 0))
    gap = np.full((h * SCALE, 4, 3), 255.0)
    pic = np.concatenate([up[0], gap, up[1], gap, up[2]], axis=1).astype(np.uint8)
    path = PICTURES / f"SATELLITE-SHORE-OUTLIERS-2026-11-{row['site']}-{row['date']}-{row['id'][:3]}.png"
    Image.fromarray(pic, "RGB").save(path, optimize=True)
    return path


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("step", choices=("prepare", "read", "report"))
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--sample2", type=Path)
    o = a.parse_args()
    {"prepare": lambda: prepare(o.out), "read": lambda: read(o.out), "report": lambda: report(o.out, o.sample2)}[o.step]()


if __name__ == "__main__":
    main()
