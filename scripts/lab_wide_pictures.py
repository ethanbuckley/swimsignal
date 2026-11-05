"""Wide true-colour pictures of the five pilot lakes, for the Research Lab title sections (prototype only).

One scene a lake: its newest picture in the imagery manifest, or (Derwent Water, no picture yet) its newest clear
reading. A square of WIDE_RADIUS_M around the site point is read from ESA's true-colour image (TCI, 10 m) with the
satellite tests' own capped client and reader (scripts/lake_algae_sat_eval: net, stac, cog): public hosts, no account,
no retries. Pictures, not measurements: no index or mask is made. Output goes to the prototype folder only.

Set scratch DIPCAST_ROOT and DIPCAST_STATE before running (AGENTS.md); the run reads, never writes, data/research.

    DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch> uv run python scripts/lab_wide_pictures.py [--max-requests 80 --max-mb 60]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lake_algae_sat_eval"))
import satellite_imagery as si  # noqa: E402

OUT = ROOT / "prototypes" / "research-lab" / "assets" / "wide"
OBS = ROOT / "data" / "research" / "lake_observations.v1.json"
WIDE_RADIUS_M = 2000


def wide_grid(lat: float, lon: float) -> dict:
    """si.site_grid's construction at WIDE_RADIUS_M: north row first, 10 m pixels, EPSG:4326."""
    n = int(round(2 * WIDE_RADIUS_M / si.PIX_M))
    dlat = WIDE_RADIUS_M / 111_320.0
    dlon = WIDE_RADIUS_M / (111_320.0 * np.cos(np.radians(lat)))
    w, s, e, nn = lon - dlon, lat - dlat, lon + dlon, lat + dlat
    lons = w + (np.arange(n) + 0.5) * (e - w) / n
    lats = nn - (np.arange(n) + 0.5) * (nn - s) / n
    LON, LAT = np.meshgrid(lons, lats)
    return {"bbox": [round(w, 7), round(s, 7), round(e, 7), round(nn, 7)], "size_px": [n, n], "lon": LON, "lat": LAT}


def choose(manifest: dict, obs: dict) -> list[tuple[str, str]]:
    lakes = {lk["lake_id"]: lk for lk in obs["lakes"]}
    out = []
    for lid in obs["pilot"]["sites"]:
        site = next((s for s in manifest["sites"] if s["lake_id"] == lid), None)
        shown = [c for c in (site or {}).get("scenes", []) if c["quality"] == "shown"]
        out.append((lid, shown[-1]["item_id"] if shown else lakes[lid]["latest"]["item_id"]))
    return out


def main() -> None:
    import net as netmod
    import stac
    from PIL import Image
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-requests", type=int, default=80)
    ap.add_argument("--max-mb", type=float, default=60)
    ap.add_argument("--max-minutes", type=float, default=5)
    a = ap.parse_args()
    obs = json.loads(OBS.read_text())
    manifest = json.loads(si.MANIFEST.read_text())
    lakes = {lk["lake_id"]: lk for lk in obs["lakes"]}
    net = netmod.Capped(max_requests=a.max_requests, max_bytes=int(a.max_mb * 1024**2),
                        max_requests_total=a.max_requests, max_bytes_total=int(a.max_mb * 1024**2))
    deadline = time.monotonic() + a.max_minutes * 60
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"made": datetime.now(UTC).isoformat(timespec="seconds"), "radius_m": WIDE_RADIUS_M, "pixel_m": si.PIX_M,
           "source": "Earth Search sentinel-2-c1-l2a, asset 'visual' (ESA TCI)", "caps": vars(a), "pictures": [],
           "attribution": "Contains modified Copernicus Sentinel data [2026]", "stop_reason": None}
    for lid, item_id in choose(manifest, obs):
        if time.monotonic() > deadline:
            rec["stop_reason"] = "time limit"
            break
        try:
            item = net.get_json(si.ITEM_URL.format(item_id))
            lk = lakes[lid]
            g = wide_grid(lk["lat"], lk["lon"])
            r, c = si.grid_positions(item, "visual", g)
            r0, r1 = int(np.floor(r.min())) - 1, int(np.ceil(r.max())) + 2
            c0, c1 = int(np.floor(c.min())) - 1, int(np.ceil(c.max())) + 2
            tci = stac.read(net, item, "visual", r0, r1, c0, c1)
        except (netmod.CapReached, netmod.Stop) as e:
            rec["stop_reason"] = f"{lid}: {e}"
            break
        rgba = si.true_colour(np.stack([si.sample(tci[..., k].astype(float), r, c, r0, c0) for k in range(3)], -1))
        buf = io.BytesIO()
        Image.fromarray(rgba[..., :3]).save(buf, "JPEG", quality=90)
        name = f"{lid}.jpg"
        (OUT / name).write_bytes(buf.getvalue())
        rec["pictures"].append({"lake_id": lid, "name": lk["name"], "water_body": lk["water_body"], "item_id": item_id,
                                "datetime": item["properties"]["datetime"], "tile": item["properties"]["grid:code"],
                                "bbox": g["bbox"], "size_px": g["size_px"], "file": f"assets/wide/{name}",
                                "sha256": hashlib.sha256(buf.getvalue()).hexdigest(),
                                "no_data_share": round(float((rgba[..., 3] == 0).mean()), 4)})
        print(lid, item_id, f"{net.requests} requests, {net.bytes / 1024**2:.1f} MiB", flush=True)
    rec["requests"], rec["megabytes"] = net.requests, round(net.bytes / 1024**2, 2)
    (OUT / "wide.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("requests", "megabytes", "stop_reason")}))


if __name__ == "__main__":
    main()
