"""Real Sentinel-2 imagery for the five pilot lake sites (#550, docs/LAKE-IMAGERY-CONTRACT-v1.md): small true-colour
windows, the cloud and invalid mask, and the index on the pixels the reading used, for the scenes the satellite test's
rules call usable. Published as data/research/lake_imagery.v1.json and data/research/lake-img/<lake id>/.

    satellite_imagery.py run [--max-requests 120] [--max-mb 40] [--max-minutes 8] [--budget-from-runs]

Each site has one fixed window, the same for every date: a square of IMG_RADIUS_M around its point, on a
latitude-longitude grid of about PIX_M pixels (EPSG:4326, `bbox` west, south, east, north). Every scene is sampled onto
that grid (nearest pixel) from its own UTM tile, so two dates line up exactly, whichever tile or zone they came from.

Per scene, through the satellite test's capped client (public hosts, no account, no retries, stop on any error status):
the full STAC item (1 request), then windows of the true-colour image (TCI) and B4 (10 m), and SCL and B5 (20 m),
covering the site's window. Measured 31 Oct 2026: reading B4, B3 and B2 separately cost about 5.7 MB a scene, since
every read fetches a whole 1024-pixel tile; the TCI is one tile instead of three.

- `<item>.png`: the scene's true-colour image (ESA's TCI: B4, B3, B2 with one fixed scaling for every scene, so
  brightness compares across dates); no-data transparent. A picture of the scene, not a measurement.
- `<item>-mask.png`: grey where the scene classification is not clear (cloud, shadow, snow, no data, defective), at 20 m.
- `<item>-index.png`: NDCI coloured on the reading's own core pixels that were clear, at 20 m, with the fixed legend
  INDEX_RANGE; transparent everywhere else. Never the whole lake.
- `core.png` (per site): the core pixels, outlined in the viewer as "the open water the reading uses".

Which scenes: first every usable scene a pilot run read that has no image yet (the current ones), then, as budget
allows, the site's earlier shown readings, newest first (the backfill). A scene the rules did not call usable gets no
image: cloud is shown as a gap in the record, not as a picture. A cap stopping the current scenes is a partial run; a
cap stopping only the backfill is not. Existing images are never deleted.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lake_algae_sat_eval"))
import satellite_pilot as sp  # noqa: E402
from protocol import CLEAR, SITE_RADIUS_M  # noqa: E402

SCHEMA, VERSION = "swimsignal.lake-imagery", "1.0.0"
MANIFEST = Path(os.environ.get("DIPCAST_IMAGERY_MANIFEST", ROOT / "data" / "research" / "lake_imagery.v1.json"))
IMG = Path(os.environ.get("DIPCAST_IMAGERY_DIR", ROOT / "data" / "research" / "lake-img"))
IMG_RADIUS_M = 400
PIX_M = 10
INDEX_RANGE = (-0.2, 0.4)
NOT_CLEAR_RGBA = (128, 128, 128, 150)
ITEM_URL = "https://earth-search.aws.element84.com/v1/collections/sentinel-2-c1-l2a/items/{}"
STATUS = ("ok", "partial", "failed")
# Five stops of a sequential scale (low to high index), sampled linearly between.
INDEX_COLOURS = np.array([[37, 52, 148], [44, 127, 184], [65, 182, 196], [161, 218, 180], [255, 255, 204]], float)


class Deadline(RuntimeError):
    """The step's time limit: stop where it is."""


# ------------------------------------------------------------------ the fixed window
def site_grid(lat: float, lon: float) -> dict:
    """The site's window: bbox [w, s, e, n] and the n x n pixel centres (lon, lat), north row first."""
    n = int(round(2 * IMG_RADIUS_M / PIX_M))
    dlat = IMG_RADIUS_M / 111_320.0
    dlon = IMG_RADIUS_M / (111_320.0 * np.cos(np.radians(lat)))
    w, s, e, nn = lon - dlon, lat - dlat, lon + dlon, lat + dlat
    lons = w + (np.arange(n) + 0.5) * (e - w) / n
    lats = nn - (np.arange(n) + 0.5) * (nn - s) / n
    LON, LAT = np.meshgrid(lons, lats)
    return {"bbox": [round(w, 7), round(s, 7), round(e, 7), round(nn, 7)], "size_px": [n, n], "lon": LON, "lat": LAT}


def grid_positions(item: dict, asset: str, grid: dict) -> tuple[np.ndarray, np.ndarray]:
    """Each grid pixel's (row, col), fractional, on the asset's own raster."""
    from pyproj import Transformer
    epsg = item["properties"].get("proj:epsg") or int(str(item["properties"]["proj:code"]).split(":")[1])
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(grid["lon"], grid["lat"])
    t = item["assets"][asset]["proj:transform"]
    return (y - t[5]) / t[4], (x - t[2]) / t[0]


def window_20m(item: dict, grid: dict, margin: int = 2) -> tuple[int, int, int, int]:
    """The 20 m window (r0, r1, c0, c1) covering the grid; its 10 m twin is the same window doubled."""
    r, c = grid_positions(item, "scl", grid)
    return (int(np.floor(r.min())) - margin, int(np.ceil(r.max())) + margin + 1,
            int(np.floor(c.min())) - margin, int(np.ceil(c.max())) + margin + 1)


def sample(arr: np.ndarray, r: np.ndarray, c: np.ndarray, r0: int, c0: int, fill=np.nan) -> np.ndarray:
    """Nearest pixel of `arr` (whose [0, 0] is raster pixel (r0, c0)) at fractional raster positions; outside: fill."""
    ri, ci = np.floor(r).astype(int) - r0, np.floor(c).astype(int) - c0
    ok = (ri >= 0) & (ri < arr.shape[0]) & (ci >= 0) & (ci < arr.shape[1])
    out = np.full(r.shape, fill, dtype=float)
    out[ok] = arr[ri[ok], ci[ok]]
    return out


# ------------------------------------------------------------------ rendering (pure)
def true_colour(tci: np.ndarray) -> np.ndarray:
    """RGBA uint8 from TCI pixels [.., 3]; a pixel that is 0 in every band (the TCI's no data) or missing is transparent."""
    ok = np.isfinite(tci).all(-1) & (np.nan_to_num(tci).sum(-1) > 0)
    out = np.zeros(tci.shape[:-1] + (4,), np.uint8)
    out[..., :3] = np.clip(np.nan_to_num(tci), 0, 255).astype(np.uint8)
    out[..., 3] = np.where(ok, 255, 0)
    return out


def not_clear_overlay(scl: np.ndarray) -> np.ndarray:
    """Grey where the classification is not clear (or missing), transparent where clear."""
    out = np.zeros(scl.shape + (4,), np.uint8)
    bad = ~np.isin(np.nan_to_num(scl, nan=0).astype(int), CLEAR)
    out[bad] = NOT_CLEAR_RGBA
    return out


def index_colour(v: np.ndarray) -> np.ndarray:
    """RGBA uint8 on the fixed legend; NaN transparent."""
    lo, hi = INDEX_RANGE
    x = np.clip((np.nan_to_num(v, nan=lo) - lo) / (hi - lo), 0, 1) * (len(INDEX_COLOURS) - 1)
    i = np.minimum(np.floor(x).astype(int), len(INDEX_COLOURS) - 2)
    f = (x - i)[..., None]
    rgb = INDEX_COLOURS[i] * (1 - f) + INDEX_COLOURS[i + 1] * f
    out = np.zeros(v.shape + (4,), np.uint8)
    out[..., :3] = np.round(rgb).astype(np.uint8)
    out[..., 3] = np.where(np.isfinite(v), 230, 0)
    return out


def png(rgba: np.ndarray) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ------------------------------------------------------------------ one scene
def render_scene(net, item: dict, site: dict, core: dict[str, np.ndarray], grid: dict) -> dict[str, np.ndarray]:
    """The scene's three layers on the site's grid, and its core on that grid."""
    import protocol as pr
    import stac
    t20, t10 = item["assets"]["scl"]["proj:transform"], item["assets"]["red"]["proj:transform"]
    if (t20[2], t20[5]) != (t10[2], t10[5]) or abs(t10[0]) * 2 != abs(t20[0]):
        raise ValueError(f"{item['id']}: the 10 m and 20 m grids do not nest")
    r0, r1, c0, c1 = window_20m(item, grid)
    scl = stac.read(net, item, "scl", r0, r1, c0, c1)
    b5 = pr.reflectance(stac.read(net, item, "rededge1", r0, r1, c0, c1), item["assets"]["rededge1"]["raster:bands"][0])
    if item["assets"]["visual"]["proj:transform"] != t10:
        raise ValueError(f"{item['id']}: the TCI is not on the 10 m grid")
    b4 = pr.reflectance(stac.read(net, item, "red", 2 * r0, 2 * r1, 2 * c0, 2 * c1), item["assets"]["red"]["raster:bands"][0])
    tci = stac.read(net, item, "visual", 2 * r0, 2 * r1, 2 * c0, 2 * c1)
    rr20, cc20 = grid_positions(item, "scl", grid)
    rr10, cc10 = grid_positions(item, "red", grid)
    layers = {"rgb": true_colour(np.stack([sample(tci[..., k].astype(float), rr10, cc10, 2 * r0, 2 * c0)
                                           for k in range(3)], -1)),
              "scl": sample(scl.astype(float), rr20, cc20, r0, c0, fill=0)}
    # The reading's core sits on the test's own 20 m window around the point (stac.window_for); find it there.
    t = item["properties"]["grid:code"]
    wr0, _, wc0, _, _ = stac.window_for(item, "scl", site["lon"], site["lat"])
    core_g = sample(core[t].astype(float), rr20, cc20, wr0, wc0, fill=0) > 0
    nd = pr.ndci(pr.b4_to_20m(b4), b5)
    index = sample(nd, rr20, cc20, r0, c0)
    clear = np.isin(layers["scl"].astype(int), pr.CLEAR)
    layers["index"] = np.where(core_g & clear, index, np.nan)
    layers["core"] = core_g
    return layers


def quality(lk: dict, item_id: str) -> tuple[str, float | None, bool]:
    """(quality, NDCI shown or None, experimental) from the published observation record."""
    for x in lk["series"]:
        if x["item_id"] == item_id:
            return ("shown" if x.get("primary", True) else "shown_secondary"), x["ndci"], bool(x.get("experimental"))
    for e in lk["excluded"]:
        if e["item_id"] == item_id:
            return f"excluded:{e['reason']}", None, False
    return "not_shown", None, False


def queue(manifest: dict, obs: dict, runs: list[dict]) -> list[tuple[str, str, str, dict]]:
    """(lake_id, item_id, kind, info): the current scenes (usable, read by a pilot run, no image yet), newest first,
    then the backfill (the site's earlier shown readings), newest first."""
    done = {(s["lake_id"], sc["item_id"]) for s in manifest.get("sites", []) for sc in s.get("scenes", [])}
    lakes = {lk["lake_id"]: lk for lk in obs["lakes"]}
    ids = [s["lake_id"] for s in sp.pilot_sites()]
    current, seen = [], set()
    for r in sorted((r | {"run_id": run["run_id"], "checked_at": run["finished"]} for run in runs for r in run["rows"]),
                    key=lambda r: r["datetime"], reverse=True):
        k = (r["lake_id"], r["item_id"])
        if r["lake_id"] in ids and r.get("usable") and k not in done and k not in seen:
            seen.add(k)
            current.append((r["lake_id"], r["item_id"], "current", {"run_id": r["run_id"], "checked_at": r["checked_at"]}))
    back = []
    for lid in ids:
        for x in lakes[lid]["series"]:
            k = (lid, x["item_id"])
            if k not in done and k not in seen and x.get("primary", True):
                back.append((lid, x["item_id"], "backfill", {"date": x["date"]}))
    back.sort(key=lambda q: q[3]["date"], reverse=True)
    return current + back


# ------------------------------------------------------------------ the step
def header(generated_at: str) -> dict:
    """The manifest's fixed parts: method, attribution, claim and code hash."""
    method = {
        "bands": {"image": "TCI, ESA's true-colour image (B4, B3, B2, fixed scaling), 10 m", "mask": "SCL, 20 m",
                  "index": "NDCI (B5 - B4) / (B5 + B4), 20 m, core pixels that were clear"},
        "grid": {"crs": "EPSG:4326", "radius_m": IMG_RADIUS_M, "pixel_m": PIX_M, "resampling": "nearest"},
        "index_legend": {"min": INDEX_RANGE[0], "max": INDEX_RANGE[1], "colours": INDEX_COLOURS.astype(int).tolist()},
        "not_clear_colour": list(NOT_CLEAR_RGBA),
        "scenes": "usable scenes only (the test's 80% clear rule); cloudy scenes have no image",
    }
    return {"schema": SCHEMA, "version": VERSION, "generated_at": generated_at,
            "attribution": ["Contains modified Copernicus Sentinel data [2020-2026]",
                            "Images read from Earth Search's Sentinel-2 Collection 1 Level-2A archive"],
            "method": method,
            "claim": "True-colour pictures of the satellite scenes the readings came from, and the index on the pixels "
                     "each reading used. Pictures, not measurements of algae or toxins, and not swimming advice. A "
                     "scene without an image was too cloudy to read.",
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def empty_manifest() -> dict:
    return {**header(datetime.now(UTC).isoformat(timespec="seconds")), "sites": [], "runs": []}


def site_entry(manifest: dict, site: dict, grid: dict) -> dict:
    s = next((x for x in manifest["sites"] if x["lake_id"] == site["lake_id"]), None)
    if s is None:
        s = {"lake_id": site["lake_id"], "name": site["name"], "water_body": site["water_body"], "lat": site["lat"],
             "lon": site["lon"], "radius_m": SITE_RADIUS_M,
             "bbox": grid["bbox"], "size_px": grid["size_px"], "core_url": None, "scenes": []}
        manifest["sites"].append(s)
    return s


def run(max_requests: int, max_mb: float, max_minutes: float) -> dict:
    import net as netmod
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else empty_manifest()
    obs = json.loads(sp.OBS.read_text())
    runs = json.loads(sp.RUNS.read_text()) if sp.RUNS.exists() else []
    lakes = {lk["lake_id"]: lk for lk in obs["lakes"]}
    sites = {s["lake_id"]: s for s in sp.pilot_sites()}
    grids = {lid: site_grid(s["lat"], s["lon"]) for lid, s in sites.items()}
    net = netmod.Capped(max_requests=max_requests, max_bytes=int(max_mb * 1024**2),
                        max_requests_total=max_requests, max_bytes_total=int(max_mb * 1024**2))
    t0 = time.monotonic()
    deadline = t0 + max_minutes * 60
    now = datetime.now(UTC).isoformat(timespec="seconds")
    rec = {"run_id": os.environ.get("GITHUB_RUN_ID") or f"local-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
           "started": now, "caps": {"requests": max_requests, "megabytes": max_mb, "minutes": max_minutes},
           "made": {"current": 0, "backfill": 0}, "errors": [], "stop_reason": None}
    todo = queue(manifest, obs, runs)
    n_current = sum(q[2] == "current" for q in todo)
    for lid, item_id, kind, info in todo:
        try:
            if time.monotonic() > deadline:
                raise Deadline("time limit")
            item = net.get_json(ITEM_URL.format(item_id))
            layers = render_scene(net, item, sites[lid], sp.site_cores(lid), grids[lid])
        except (netmod.CapReached, Deadline) as e:
            rec["stop_reason"] = f"{kind}: {e}"
            break
        except netmod.Stop as e:
            rec["stop_reason"] = f"stopped: {e}"
            rec["errors"].append({"item_id": item_id, "error": str(e)[:200]})
            break
        except Exception as e:  # noqa: BLE001 - one scene's error is recorded; the others still run
            rec["errors"].append({"item_id": item_id, "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        d = IMG / lid
        d.mkdir(parents=True, exist_ok=True)
        q, value, exp = quality(lakes[lid], item_id)
        files = {"image_url": (f"{item_id}.png", layers["rgb"]),
                 "mask_url": (f"{item_id}-mask.png", not_clear_overlay(layers["scl"]))}
        if q.startswith("shown"):   # a scene left out is not an observation: no index is drawn for it
            files["index_url"] = (f"{item_id}-index.png", index_colour(layers["index"]))
        entry = site_entry(manifest, sites[lid], grids[lid])
        if entry["core_url"] is None:
            core_rgba = np.zeros(layers["core"].shape + (4,), np.uint8)
            core_rgba[layers["core"]] = (255, 255, 255, 255)
            (d / "core.png").write_bytes(png(core_rgba))
            entry["core_url"] = f"lake-img/{lid}/core.png"
        sc = {"item_id": item_id, "datetime": item["properties"]["datetime"], "tile": item["properties"]["grid:code"],
              "checked_at": info.get("checked_at"), "run_id": info.get("run_id"), "source": kind,
              "imaged_at": datetime.now(UTC).isoformat(timespec="seconds"), "imaged_by": rec["run_id"]}
        for k, (name, rgba) in files.items():
            b = png(rgba)
            (d / name).write_bytes(b)
            sc[k] = f"lake-img/{lid}/{name}"
            sc[k.replace("_url", "_sha256")] = hashlib.sha256(b).hexdigest()
        shown = q.startswith("shown")
        core_n = int(layers["core"].sum())
        clear_core = int((layers["core"] & np.isin(layers["scl"].astype(int), CLEAR)).sum())
        sc.update({"quality": q, "ndci": value, "experimental": exp,
                   "index_url": sc.get("index_url"), "index_sha256": sc.get("index_sha256"),
                   "index_pixels": int(np.isfinite(layers["index"]).sum()) if shown else 0,
                   # The median of the drawn index, against the published reading: a check that the picture is the
                   # reading's own pixels (resampling onto the grid repeats or skips a few, so not exact).
                   "index_median": round(float(np.nanmedian(layers["index"])), 5)
                   if shown and np.isfinite(layers["index"]).any() else None,
                   "core_pixels_in_window": core_n, "clear_share_in_core": round(clear_core / core_n, 4) if core_n else None})
        entry["scenes"] = sorted([x for x in entry["scenes"] if x["item_id"] != item_id] + [sc], key=lambda x: x["datetime"])
        rec["made"][kind] += 1
    done_current = rec["made"]["current"]
    rec.update({"finished": datetime.now(UTC).isoformat(timespec="seconds"), "seconds": round(time.monotonic() - t0, 1),
                "requests": net.requests, "megabytes": round(net.bytes / 1024**2, 2),
                "current_due": n_current, "backfill_remaining": len(todo) - n_current - rec["made"]["backfill"],
                "status": "ok" if done_current == n_current and not rec["errors"] else
                          "failed" if done_current == 0 and n_current and (rec["errors"] or rec["stop_reason"]) else "partial"})
    manifest.update(header(rec["finished"]))
    manifest["runs"] = manifest.get("runs", []) + [rec]
    problems = check(manifest)
    if problems:
        raise SystemExit("the manifest would break the contract:\n" + "\n".join(problems[:20]))
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n")
    return rec


def check(m: dict, img_dir: Path | None = None) -> list[str]:
    err = []
    if m.get("schema") != SCHEMA or str(m.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    for k in ("attribution", "method", "claim", "sites", "runs"):
        if k not in m:
            err.append(f"missing {k}")
    for s in m.get("sites", []):
        if len(s.get("bbox", [])) != 4 or not (s["bbox"][0] < s["lon"] < s["bbox"][2] and s["bbox"][1] < s["lat"] < s["bbox"][3]):
            err.append(f"{s.get('lake_id')}: bbox does not hold the point")
        dts = [x["datetime"] for x in s.get("scenes", [])]
        if dts != sorted(dts):
            err.append(f"{s['lake_id']}: scenes not in date order")
        for sc in s.get("scenes", []):
            if not (sc["quality"] in ("shown", "shown_secondary", "not_shown") or sc["quality"].startswith("excluded:")):
                err.append(f"{sc['item_id']}: quality {sc['quality']!r}")
            if not sc["quality"].startswith("shown") and sc.get("ndci") is not None:
                err.append(f"{sc['item_id']}: an index value on a scene that is not shown")
            if not sc["quality"].startswith("shown") and sc.get("index_url"):
                err.append(f"{sc['item_id']}: an index layer on a scene that is not shown")
            if sc.get("ndci") is not None and sc.get("index_median") is not None and abs(sc["ndci"] - sc["index_median"]) > 0.01:
                err.append(f"{sc['item_id']}: drawn index median {sc['index_median']} far from the reading {sc['ndci']}")
            if img_dir is not None:
                for k in ("image_url", "mask_url", "index_url"):
                    if not sc.get(k):
                        continue
                    p = img_dir.parent / sc[k]
                    if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != sc[k.replace("_url", "_sha256")]:
                        err.append(f"{sc['item_id']}: {k} missing or changed")
    for r in m.get("runs", []):
        if r.get("status") not in STATUS:
            err.append(f"run {r.get('run_id')}: status {r.get('status')!r}")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["run", "check", "init"])
    ap.add_argument("--max-requests", type=int, default=120)
    ap.add_argument("--max-mb", type=float, default=40)
    ap.add_argument("--max-minutes", type=float, default=8)
    ap.add_argument("--budget-from-runs", type=int, default=None,
                    help="the pilot's run cap: imagery gets at most this less what the latest pilot run used")
    a = ap.parse_args()
    if a.step == "init":
        if not MANIFEST.exists():
            MANIFEST.write_text(json.dumps(empty_manifest(), ensure_ascii=False, separators=(",", ":")) + "\n")
        print(MANIFEST)
        return
    if a.step == "check":
        problems = check(json.loads(MANIFEST.read_text()), IMG)
        print("\n".join(problems) or f"{MANIFEST}: holds the contract")
        sys.exit(1 if problems else 0)
    cap, mb = a.max_requests, a.max_mb
    if a.budget_from_runs is not None and sp.RUNS.exists():
        # One allocation per run for readings and imagery together (#472): 300 requests, 100 MiB.
        runs = json.loads(sp.RUNS.read_text())
        last = runs[-1] if runs else {}
        cap = max(0, min(cap, a.budget_from_runs - (last.get("requests") or 0)))
        mb = max(0.0, min(mb, 100 - (last.get("megabytes") or 0)))
    rec = run(cap, mb, a.max_minutes)
    print(json.dumps(rec, indent=1))
    if rec["status"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
