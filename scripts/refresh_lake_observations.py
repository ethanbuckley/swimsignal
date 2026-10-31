"""Newer Sentinel-2 readings at the bathing-water lakes, made exactly as the satellite test made them, into a separate
research root (docs/SATELLITE-RECOVERY-2026-10.md, "Refreshing"). Never writes to the test caches it reads.

    refresh_lake_observations.py plan <root> --to YYYY-MM-DD [--from YYYY-MM-DD]   catalogue only: scenes and cost
    refresh_lake_observations.py run  <root> --to YYYY-MM-DD [--from ...] [--only BW_ID ...] [--max-requests N]

`plan` searches the public Earth Search catalogue once per lake (one request at a time, a pause between) and writes
<root>/plan.json: the scenes found per lake and the cost estimated from the satellite test's own ledger. `run` reads,
for each scene, the scene-classification window around the site and, when at least 80% of the core pixels are clear,
bands B4 and B5, and writes <root>/features.parquet in the test's columns. The core pixels are the test's
(lake-algae-sat/out/cores/<bw_id>.npz), so a refreshed reading uses the same mask as every earlier one.

Every request goes through the test's Capped client (scripts/lake_algae_sat_eval/net.py): listed public hosts only, no
account, no retries, a stop on any error status, and caps on requests and bytes, here set per run on the command line
and kept in <root>/ledger-refresh.jsonl. No Open-Meteo call is made.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lake_algae_sat_eval"))
import net as netmod  # noqa: E402
import protocol as pr  # noqa: E402
import stac  # noqa: E402
from stage1 import ITEM_FIELDS, check_items, pmap  # noqa: E402

PRIVATE = Path.home() / "Documents" / "GitHub" / "swimsignal-private"
SAT = Path(os.environ.get("DIPCAST_SAT_OUT", PRIVATE / "lake-algae-sat" / "out"))
CHL = Path(os.environ.get("DIPCAST_CHL_OUT", PRIVATE / "lake-chlorophyll" / "out"))
SITES = HERE.parent / "data" / "raw" / "bathing_waters_inland.json"
CHL_LAKES = HERE.parent / "docs" / "LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-lakes.json"
# Two site sets, each with the cores the tests saved: the bathing-water lakes (#377) and the EA chlorophyll
# monitoring points (#386), whose lab samples are what a confirmation is judged against.
SETS = {"bathing": SAT, "chlorophyll": CHL}
# Measured from the satellite test's stage 1 ledger (19,531 SCL, 4,487 B04 and 4,173 B05 requests over 9,238
# windows and 1,749 clear scenes; 30 October 2026).
PER_SCENE = {"requests": 2.1, "bytes": 33e3}
PER_CLEAR_SCENE = {"requests": 5.0, "bytes": 2.7e6}


def lakes(only: list[str] | None = None, which: str = "bathing") -> pd.DataFrame:
    """The sites of a set past the size rule on at least one tile (columns bw_id, name, water_body, lon, lat, depth_m,
    lake_type); bw_id is the bathing water's id or the chlorophyll point's WQA id, as the caches name them."""
    sizes = json.loads((SETS[which] / "sizes.json").read_text())
    if which == "bathing":
        s = pr.lake_sites(SITES).assign(depth_m=None, lake_type=None)
    else:
        pts = json.loads(CHL_LAKES.read_text())["points"]
        s = pd.DataFrame([{"bw_id": p["wqa_point"], "name": p.get("lake_name"), "water_body": p.get("wb_id"),
                           "lon": p["lon"], "lat": p["lat"], "depth_m": p.get("depth_m"),
                           "lake_type": p.get("lake_type")} for p in pts])
    s = s[s["bw_id"].map(lambda b: any(t["passes"] for t in sizes.get(b, {}).get("tiles", {}).values()))]
    return s[s["bw_id"].isin(only)] if only else s


def sun_elevation(when_iso: str, lat: float, lon: float) -> float:
    """Solar elevation in degrees at a UTC time and place (NOAA's simplified equations; within about 0.5 degrees),
    computed offline so a scene's daylight can be checked without asking the catalogue again."""
    t = pd.Timestamp(when_iso).tz_convert("UTC")
    doy, hour = t.dayofyear, t.hour + t.minute / 60 + t.second / 3600
    g = 2 * np.pi / 365 * (doy - 1 + (hour - 12) / 24)
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g)
                    - 0.040849 * np.sin(2 * g))
    ha = np.radians((hour * 60 + eqt + 4 * lon) / 4 - 180)
    la = np.radians(lat)
    cos_z = np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(ha)
    return float(90 - np.degrees(np.arccos(np.clip(cos_z, -1, 1))))


SCL_NAMES = {0: "no_data", 1: "defective", 2: "dark_area", 3: "cloud_shadow", 4: "vegetation", 5: "not_vegetated",
             6: "water", 7: "unclassified", 8: "cloud_medium", 9: "cloud_high", 10: "thin_cirrus", 11: "snow_ice"}


def scene_quality(scl: np.ndarray, core: np.ndarray, index: np.ndarray | None) -> dict:
    """What the core pixels were classed as, and how many clear core pixels had a valid index (B4 and B5 both
    positive reflectance). Checks for snow and ice, cloud, and missing or invalid bands behind a reading."""
    vals, counts = np.unique(scl[core], return_counts=True)
    q = {f"core_{SCL_NAMES.get(int(v), int(v))}": int(c) for v, c in zip(vals, counts, strict=True)}
    clear = np.isin(scl, pr.CLEAR) & core
    q["clear_core_not_water"] = int((clear & (scl != pr.WATER)).sum())
    if index is not None:
        q["clear_core_valid_index"] = int(np.isfinite(index[clear]).sum())
    return q


def cores(bw_id: str, which: str = "bathing") -> dict[str, np.ndarray]:
    z = np.load(SETS[which] / "cores" / f"{bw_id}.npz")
    return {k.replace("_", "-"): z[k] for k in z.files}


def season_cost(which: str, year: int = 2026) -> dict:
    """Offline: what one May-September season costs at a set's sites if every scene is read, from the scenes the
    tests' own catalogue searches found over each site in `year` and the measured per-scene rates above."""
    rows = []
    for site in lakes(which=which).itertuples():
        items = json.loads((SETS[which] / "items" / f"{site.bw_id}.json").read_text())
        core = cores(site.bw_id, which)
        n = sum(1 for i in items if i["properties"]["datetime"][:4] == str(year)
                and i["properties"]["grid:code"] in core and pr.passes_size_rule(core[i["properties"]["grid:code"]]))
        rows.append({"site": site.bw_id, "lake_type": site.lake_type, "scenes": n})
    d = pd.DataFrame(rows)
    share = float(pd.read_parquet(SAT / "features.parquet")["usable"].mean())
    return {"set": which, "year": year, "sites": len(d), "shallow_sites": int((d["lake_type"] == "shallow").sum()),
            "scenes": int(d["scenes"].sum()), "estimate": estimate(int(d["scenes"].sum()), share),
            "estimate_if_every_scene_clear": estimate(int(d["scenes"].sum()), 1.0),
            "scenes_by_site": {k: int(v) for k, v in zip(d["site"], d["scenes"], strict=True)}}


def last_processed() -> str:
    return pd.read_parquet(SAT / "features.parquet")["scene_date"].max()


def search(net, site, start: str, end: str) -> list[dict]:
    items = stac.search(net, site.lon, site.lat, start, end, fields=ITEM_FIELDS)
    items = sorted({i["id"]: i for i in items}.values(), key=lambda i: (i["properties"]["datetime"], i["id"]))
    check_items(items)
    return items


def estimate(n_scenes: int, clear_share: float) -> dict:
    n_clear = n_scenes * clear_share
    return {"requests": round(n_scenes * PER_SCENE["requests"] + n_clear * PER_CLEAR_SCENE["requests"]),
            "megabytes": round((n_scenes * PER_SCENE["bytes"] + n_clear * PER_CLEAR_SCENE["bytes"]) / 1e6, 1),
            "assumed_clear_share": clear_share}


def net_for(root: Path, max_requests: int, max_mb: int) -> netmod.Capped:
    return netmod.Capped(ledger=root / "ledger-refresh.jsonl", max_requests=max_requests, max_bytes=max_mb * 1024**2,
                         max_requests_total=max_requests * 10, max_bytes_total=max_mb * 10 * 1024**2)


def plan(root: Path, start: str, end: str, max_requests: int, which: str = "bathing") -> dict:
    root.mkdir(parents=True, exist_ok=True)
    net = net_for(root, max_requests, 50)
    out = {"set": which, "from": start, "to": end, "lakes": {}}
    for site in lakes(which=which).itertuples():
        items = search(net, site, start, end)
        (root / "items").mkdir(exist_ok=True)
        (root / "items" / f"{site.bw_id}.json").write_text(json.dumps(items))
        out["lakes"][site.bw_id] = {"name": site.name, "scenes": len(items),
                                    "tiles": sorted({i["properties"]["grid:code"] for i in items})}
    n = sum(v["scenes"] for v in out["lakes"].values())
    f = pd.read_parquet(SAT / "features.parquet")
    hist = float(f["usable"].mean())
    out["scenes"] = n
    out["estimate_at_test_clear_share"] = estimate(n, hist)
    out["estimate_if_every_scene_clear"] = estimate(n, 1.0)
    out["catalogue_requests"] = net.requests
    (root / "plan.json").write_text(json.dumps(out, indent=1))
    return out


def run(root: Path, start: str, end: str, only: list[str] | None, max_requests: int, max_mb: int,
        which: str = "bathing") -> pd.DataFrame:
    root.mkdir(parents=True, exist_ok=True)
    net = net_for(root, max_requests, max_mb)
    rows = []
    for site in lakes(only, which).itertuples():
        p = root / "items" / f"{site.bw_id}.json"
        items = json.loads(p.read_text()) if p.exists() else search(net, site, start, end)
        items = [i for i in items if start <= i["properties"]["datetime"][:10] <= end]
        core = cores(site.bw_id, which)

        def one(it, site=site, core=core):
            t = it["properties"]["grid:code"]
            if t not in core or not pr.passes_size_rule(core[t]):
                return None
            w, _ = stac.site_scl(net, it, site.lon, site.lat)
            (root / "scl" / site.bw_id).mkdir(parents=True, exist_ok=True)
            np.savez_compressed(root / "scl" / site.bw_id / f"{it['id']}.npz", scl=w)
            clear, usable = pr.scene_clear(w, core[t])
            value, index = float("nan"), None
            if usable:
                b4_dn, b5_dn = stac.site_bands(net, it, site.lon, site.lat)
                b4 = pr.b4_to_20m(pr.reflectance(b4_dn, it["assets"]["red"]["raster:bands"][0]))
                b5 = pr.reflectance(b5_dn, it["assets"]["rededge1"]["raster:bands"][0])
                index = pr.ndci(b4, b5)
                _, _, value = pr.scene_reading(w, core[t], index)
            p = it["properties"]
            return {"bw_id": site.bw_id, "water_body": site.water_body, "tile": t, "item_id": it["id"],
                    "scene_date": p["datetime"][:10], "datetime": p["datetime"],
                    "processing_baseline": p.get("s2:processing_baseline"),
                    "sun_elevation_deg": round(sun_elevation(p["datetime"], site.lat, site.lon), 1),
                    "clear_core": int(clear), "n_core": int(core[t].sum()), "usable": bool(usable),
                    "reading": None if np.isnan(value) else float(value), **scene_quality(w, core[t], index)}

        rows += [r for r in pmap(one, items) if r is not None]
    f = pd.DataFrame(rows)
    f.to_parquet(root / "features.parquet", index=False)
    (root / "run.json").write_text(json.dumps({"set": which, "from": start, "to": end, "only": only, "rows": len(f),
                                               "usable": int(f["usable"].sum()) if len(f) else 0,
                                               "requests": net.requests, "bytes": net.bytes}, indent=1))
    return f


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["plan", "run", "cost"])
    ap.add_argument("root", type=Path, nargs="?")
    ap.add_argument("--set", dest="which", choices=sorted(SETS), default="bathing")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--max-requests", type=int, default=40)
    ap.add_argument("--max-mb", type=int, default=30)
    a = ap.parse_args()
    if a.step == "cost":
        print(json.dumps(season_cost(a.which), indent=1))
        return
    if a.root is None or a.end is None:
        raise SystemExit("plan and run need a root and --to")
    if any(a.root.resolve().is_relative_to(d.resolve().parent) for d in SETS.values()):
        raise SystemExit("the research root must not be inside the test's cache")
    start = a.start or (date.fromisoformat(last_processed()) + timedelta(days=1)).isoformat()
    if a.step == "plan":
        print(json.dumps(plan(a.root, start, a.end, a.max_requests, a.which), indent=1))
    else:
        f = run(a.root, start, a.end, a.only, a.max_requests, a.max_mb, a.which)
        print(f.to_string(index=False) if len(f) else "no rows")


if __name__ == "__main__":
    main()
