"""Lake observations for the Research/Labs page: export the satellite readings the lake tests already made into the
versioned file of docs/LAKE-OBSERVATIONS-CONTRACT-v1.md, and check a file against that contract. Offline:

    uv run python scripts/export_lake_observations.py export [--as-of YYYY-MM-DD] [--out PATH]
    uv run python scripts/export_lake_observations.py check [PATH]

Inputs, read only (DIPCAST_SAT_OUT and DIPCAST_CHL_OUT override the defaults in swimsignal-private):
- the bathing-water lakes test's cache (PR #377, lake-algae-sat/out): features.parquet, sizes.json, items/*.json;
- the lab-chlorophyll test's cache (PR #386, lake-chlorophyll/out): the same, and values.parquet (EA determinand 7887);
- in this repository: data/raw/bathing_waters_inland.json and docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-lakes.json.
Every input's SHA-256 is taken before and after; the export stops if any changed, and records them in the file.

A reading is the tests' own: the median NDCI = (B5 - B4) / (B5 + B4) over clear core pixels of a Sentinel-2
Collection 1 L2A scene, kept when at least 80% of the core is clear (scripts/lake_algae_sat_eval/protocol.py). Nothing
here converts NDCI to chlorophyll, or says anything of harmful algae or swimming.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path.home() / "Documents" / "GitHub" / "swimsignal-private"
SAT = Path(os.environ.get("DIPCAST_SAT_OUT", PRIVATE / "lake-algae-sat" / "out"))
CHL = Path(os.environ.get("DIPCAST_CHL_OUT", PRIVATE / "lake-chlorophyll" / "out"))
BATHING = ROOT / "data" / "raw" / "bathing_waters_inland.json"
CHL_LAKES = ROOT / "docs" / "LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-lakes.json"
OUT = ROOT / "data" / "research" / "lake_observations.v1.json"

SCHEMA, VERSION = "swimsignal.lake-observations", "1.2.0"
PROCESSING = "s2c1-l2a.ndci-core-median.v1"
SEASON = (5, 6, 7, 8, 9)
RECENT_DAYS, OLDER_DAYS = 14, 60
SHALLOW_M = 3.0
MASK = {"site_radius_m": 300, "pixel_m": 20, "min_core_pixels": 9, "min_clear_share": 0.80}
MIN_SUN_DEG = 15.0        # amendment 1.1: a refreshed reading needs the sun at least this high
MIN_WATER_SHARE = 0.90    # amendment 1.1: out of season, this share of clear core pixels must be classed water
COVERAGE_LABEL = {"every_scene": "every image, May to September, of the years covered",
                  "near_lab_samples": "selected historical coverage: only images within a day of a lab sample"}
YEARS = tuple(range(2020, 2027))   # the seasons the tests searched (protocol.YEARS)
# Why a season has no reading row (contract 1.2): the catalogue the tests searched has no image over the site that
# May-September; or (a near-lab-samples site) images exist but no lab sample was taken within a day of one.
SEASON_REASONS = ("no_source_images", "no_lab_sample_dates")
SEASON_NOTES = {"no_source_images": "Earth Search's sentinel-2-c1-l2a collection, the one the tests read, holds no "
                                    "image over this site from May to September that year (for 2022 at every site; "
                                    "docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md). The older collection is not mixed in.",
                "no_lab_sample_dates": "Images exist, but this site's record keeps only images within a day of an EA "
                                       "lab sample, and none was taken in May-September that year."}
REASONS = ("too_small", "no_usable_scene", "season_closed", "not_refreshed", "series_partial")
FRESHNESS = ("recent", "older", "stale", "none")
CLAIM = {
    "index": "NDCI (normalised difference chlorophyll index)",
    "definition": "(B5 - B4) / (B5 + B4) from Sentinel-2 Collection 1 Level-2A surface reflectance, B4 averaged to "
                  "20 m; the median over clear core pixels within 300 m of the site; a scene counts when at least "
                  "80% of those pixels are clear (scene classification 2, 4, 5, 6 or 7).",
    "public_wording": "A satellite reading of how green the water looked from space on the date shown: an index that "
                      "rises with chlorophyll and floating or suspended plant material. It is not a test for harmful "
                      "algae or toxins, and it is not swimming advice.",
    "not_claimed": ["harmful, toxic or blue-green algae (cyanobacteria)", "algae-free or clear water",
                    "a chlorophyll concentration", "swimming advice or safety", "a forecast"],
}
LAB_DEFINITION = {
    "target": "chlorophyll (acetone extract)", "determinand": "7887", "unit": "µg/l",
    "method_note": "EA determinand 7887, 'Chlorophyll : Acetone Extract'. Not confirmed as chlorophyll-a; the "
                   "phaeopigment correction is not stated (docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md).",
    "censoring": "censored '<' means the lab reported below the limit given in value; '>' above it",
    "source": "Environment Agency Water Quality Archive, Open Government Licence v3.0",
}


# ------------------------------------------------------------------ inputs
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    if path.is_dir():
        for p in sorted(path.rglob("*.json")):
            h.update(p.relative_to(path).as_posix().encode())
            h.update(p.read_bytes())
    else:
        h.update(path.read_bytes())
    return h.hexdigest()


def inputs() -> dict[str, Path]:
    return {"lake-algae-sat/features.parquet": SAT / "features.parquet", "lake-algae-sat/sizes.json": SAT / "sizes.json",
            "lake-algae-sat/items": SAT / "items",
            "lake-chlorophyll/features.parquet": CHL / "features.parquet", "lake-chlorophyll/sizes.json": CHL / "sizes.json",
            "lake-chlorophyll/items": CHL / "items", "lake-chlorophyll/values.parquet": CHL / "values.parquet",
            "data/raw/bathing_waters_inland.json": BATHING,
            "docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-lakes.json": CHL_LAKES}


def item_meta(items_dir: Path) -> dict[str, dict]:
    """item id -> datetime and processing baseline, from the STAC items the tests saved."""
    out = {}
    for f in sorted(items_dir.glob("*.json")):
        for it in json.loads(f.read_text()):
            p = it.get("properties", {})
            out[it["id"]] = {"datetime": p.get("datetime"), "processing_baseline": p.get("s2:processing_baseline")}
    return out


def lab_value(s) -> tuple[float | None, str | None]:
    """A WQA result string -> (value, censoring): '<0.5' -> (0.5, '<'); '12' -> (12.0, None); anything else -> (None, None).
    A censored value is the reported limit, never halved or guessed."""
    t = str(s if s is not None else "").strip()
    cens = "<" if t.startswith("<") else ">" if t.startswith(">") else None
    try:
        v = float(t.lstrip("<>= "))
    except ValueError:
        return None, None
    return (v, cens) if np.isfinite(v) and v >= 0 else (None, None)


# ------------------------------------------------------------------ records
def freshness(latest: str | None, as_of: date) -> tuple[int | None, str]:
    if latest is None:
        return None, "none"
    age = (as_of - date.fromisoformat(latest)).days
    return age, "recent" if age <= RECENT_DAYS else "older" if age <= OLDER_DAYS else "stale"


def item_years(items_dir: Path) -> dict[str, dict[int, int]]:
    """site -> {year: images in May-September} from the STAC items the tests saved (one file per site)."""
    out = {}
    for f in sorted(items_dir.glob("*.json")):
        c: dict[int, int] = {}
        for it in json.loads(f.read_text()):
            d = it.get("properties", {}).get("datetime") or ""
            if d[:4].isdigit() and int(d[5:7]) in SEASON:
                c[int(d[:4])] = c.get(int(d[:4]), 0) + 1
        out[f.stem] = c
    return out


def seasons(f: pd.DataFrame, scope: str = "every_scene", images: dict[int, int] | None = None) -> list[dict]:
    """One entry for every season the tests searched: its counts, or none with the reason why."""
    images = images or {}
    out = []
    years = f["scene_date"].str[:4].astype(int) if len(f) else pd.Series(dtype=int)
    for y in YEARS:
        g = f[years == y] if len(f) else f
        if len(g):
            u = g[g["usable"] & g["reading"].notna()]
            out.append({"year": y, "scenes": int(len(g)), "usable": int(len(u)),
                        "usable_share": round(len(u) / len(g), 4),
                        "median_ndci": round(float(u["reading"].median()), 4) if len(u) else None,
                        "first": u["scene_date"].min() if len(u) else None,
                        "last": u["scene_date"].max() if len(u) else None, "reason": None})
        else:
            why = "no_source_images" if images.get(y, 0) == 0 else (
                "no_lab_sample_dates" if scope == "near_lab_samples" else "no_source_images")
            out.append({"year": y, "scenes": 0, "usable": 0, "usable_share": None, "median_ndci": None,
                        "first": None, "last": None, "reason": why, "source_images": int(images.get(y, 0))})
    return out


def refresh_decision(r) -> str | None:
    """Why a refreshed reading is not shown (None when it is). Every refreshed reading needs the test's 80% clear rule,
    a valid index at every clear core pixel, no snow or ice in the core and the sun at least MIN_SUN_DEG up. One outside
    May-September also needs at least MIN_WATER_SHARE of its clear core pixels classed as water (amendment 1.1)."""
    if not r.usable or r.reading is None or not np.isfinite(r.reading):
        return "not_usable"
    if getattr(r, "clear_core_valid_index", r.clear_core) != r.clear_core:
        return "invalid_band_values"
    if (getattr(r, "core_snow_ice", 0) or 0) > 0:
        return "snow_or_ice_in_core"
    if (getattr(r, "sun_elevation_deg", 90) or 90) < MIN_SUN_DEG:
        return "sun_too_low"
    if int(r.scene_date[5:7]) not in SEASON:
        not_water = getattr(r, "clear_core_not_water", 0) or 0
        if r.clear_core and not_water / r.clear_core > 1 - MIN_WATER_SHARE:
            return "core_not_classed_water"
    return None


def load_refresh(path: Path) -> tuple[pd.DataFrame, dict]:
    """A refresh root's readings and its record; its SHA256SUMS must match."""
    for line in (path / "SHA256SUMS").read_text().splitlines():
        h, name = line.split()
        if sha256(path / name) != h:
            raise SystemExit(f"{path}: {name} does not match SHA256SUMS")
    run = json.loads((path / "run.json").read_text())
    f = pd.read_parquet(path / "features.parquet")
    return f, {"source": f"refresh:{path.name}", "set": run.get("set", "bathing"), "from": run["from"], "to": run["to"],
               "features_sha256": sha256(path / "features.parquet"), "requests": run.get("requests"),
               "bytes": run.get("bytes")}


def lake_record(base: dict, f: pd.DataFrame, sizes: dict, meta: dict, scope: str, lab: list[dict], as_of: date,
                processed_to: str, refresh: list[tuple[pd.DataFrame, dict]] = (),
                images: dict[int, int] | None = None) -> dict:
    tiles = {t: {"n_core": v["n_core"], "passes": bool(v["passes"])} for t, v in (sizes.get("tiles") or {}).items()}
    passes = any(v["passes"] for v in tiles.values())
    use = f[f["usable"] & f["reading"].notna()]
    rows = [{"date": r.scene_date, "datetime": meta.get(r.item_id, {}).get("datetime"), "item_id": r.item_id,
             "tile": r.tile, "processing_baseline": meta.get(r.item_id, {}).get("processing_baseline"),
             "clear_core": int(r.clear_core), "n_core": int(r.n_core), "ndci": round(float(r.reading), 5),
             "season": "in_season", "experimental": False, "source": "test_cache"} for r in use.itertuples()]
    seen, excluded, refreshes, lake_to = {x["item_id"] for x in rows}, [], [], processed_to
    for rf, info in refresh:
        shown = 0
        for r in rf.itertuples():
            if r.item_id in seen:
                continue
            why = refresh_decision(r)
            if why:
                if why != "not_usable":
                    excluded.append({"date": r.scene_date, "item_id": r.item_id, "reason": why, "source": info["source"]})
                continue
            out_of = int(r.scene_date[5:7]) not in SEASON
            rows.append({"date": r.scene_date, "datetime": r.datetime, "item_id": r.item_id, "tile": r.tile,
                         "processing_baseline": r.processing_baseline, "clear_core": int(r.clear_core),
                         "n_core": int(r.n_core), "ndci": round(float(r.reading), 5),
                         "season": "out_of_season" if out_of else "in_season", "experimental": out_of,
                         "source": info["source"], "sun_elevation_deg": float(r.sun_elevation_deg),
                         "clear_water_share": round(1 - (getattr(r, "clear_core_not_water", 0) or 0) / r.clear_core, 4)})
            seen.add(r.item_id)
            shown += 1
        refreshes.append({**info, "scenes": int(len(rf)), "shown": shown})
        lake_to = max(lake_to, info["to"])
    rows.sort(key=lambda x: (x["date"], x["item_id"]))
    # The test's rule for one reading a date (protocol.one_per_date): the most clear core pixels, then the first id.
    best = {}
    for x in rows:
        k = best.get(x["date"])
        if k is None or x["clear_core"] > k["clear_core"] or (x["clear_core"] == k["clear_core"] and x["item_id"] < k["item_id"]):
            best[x["date"]] = x
    series = [{**x, "primary": best[x["date"]] is x} for x in rows]
    prim = [x for x in series if x["primary"]]
    last = prim[-1] if prim else None
    age, fresh = freshness(last["date"] if last else None, as_of)
    reasons = []
    if not passes:
        reasons.append("too_small")
    elif not series:
        reasons.append("no_usable_scene")
    if as_of.month not in SEASON:
        reasons.append("season_closed")
    if as_of.isoformat() > lake_to:
        reasons.append("not_refreshed")
    if scope == "near_lab_samples":
        reasons.append("series_partial")
    latest = {"date": None, "datetime": None, "item_id": None, "ndci": None, "clear_share": None,
              "season": None, "experimental": None} if last is None else {
        "date": last["date"], "datetime": last["datetime"], "item_id": last["item_id"], "ndci": last["ndci"],
        "clear_share": round(last["clear_core"] / last["n_core"], 4), "season": last["season"],
        "experimental": last["experimental"]}
    return {**base, "water_body_key": slug(base["water_body"] or base["lake_id"]),
            "mask": {**MASK, "tiles": tiles, "passes_size_rule": passes}, "series_scope": scope,
            "coverage_label": COVERAGE_LABEL[scope], "processed_to": lake_to,
            "latest": {**latest, "scope": "latest_in_dataset", "age_days": age, "freshness": fresh, "reasons": reasons},
            "seasons": seasons(f, scope, images) if passes else [], "series": series, "excluded": excluded, "refreshes": refreshes,
            "lab": lab}


def slug(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def lab_rows(values: pd.DataFrame, point: str) -> list[dict]:
    out = []
    for r in values[values["wqa_point"] == point].sort_values("sample_time").itertuples():
        v, cens = lab_value(r.result)
        if v is None:
            continue
        if str(r.determinand) != "7887" or str(r.unit).upper() != "MICROGRAM PER LITRE":
            raise SystemExit(f"{point}: a lab row that is not determinand 7887 in µg/l: {r.determinand} {r.unit}")
        out.append({"sample_time": r.sample_time, "value": v, "censored": cens, "purpose": r.purpose})
    return out


def code_hashes() -> dict[str, str]:
    """SHA-256 of every script a reading or this file depends on: the authoritative code provenance (a commit id read at
    export time can predate uncommitted edits)."""
    files = ["scripts/export_lake_observations.py", "scripts/refresh_lake_observations.py",
             *(f"scripts/lake_algae_sat_eval/{n}.py" for n in ("protocol", "stage1", "stac", "cog", "net")),
             "scripts/lake_chlorophyll_eval/chl_stage1.py", "scripts/lake_chlorophyll_eval/chl_protocol.py"]
    return {f: sha256(ROOT / f) for f in files if (ROOT / f).exists()}


def build(as_of: date, refresh_dirs: list[Path] = ()) -> dict:
    sys.path.insert(0, str(ROOT / "scripts" / "lake_algae_sat_eval"))
    from protocol import WATER_BODY
    before = {k: sha256(p) for k, p in inputs().items()}
    sat_f, chl_f = pd.read_parquet(SAT / "features.parquet"), pd.read_parquet(CHL / "features.parquet")
    sat_sizes, chl_sizes = json.loads((SAT / "sizes.json").read_text()), json.loads((CHL / "sizes.json").read_text())
    meta = {**item_meta(SAT / "items"), **item_meta(CHL / "items")}
    sat_years, chl_years = item_years(SAT / "items"), item_years(CHL / "items")
    values = pd.read_parquet(CHL / "values.parquet")
    bathing = {s["id"]: s for s in json.loads(BATHING.read_text()) if s["kind"] == "lake"}
    chl_pts = {p["wqa_point"]: p for p in json.loads(CHL_LAKES.read_text())["points"]}
    by_wqa = {s.get("wqa_point"): bid for bid, s in bathing.items() if s.get("wqa_point")}
    processed_to = max(sat_f["scene_date"].max(), chl_f["scene_date"].max())
    refreshed = [load_refresh(Path(d)) for d in refresh_dirs]

    def refresh_for(site_id: str) -> list:
        return [(rf[rf["bw_id"] == site_id], info) for rf, info in refreshed if (rf["bw_id"] == site_id).any()]
    lakes = []
    for bid, s in sorted(bathing.items()):
        wqa = s.get("wqa_point")
        p = chl_pts.get(wqa, {})
        base = {"lake_id": f"bw-{bid}", "name": s["name"], "water_body": WATER_BODY.get(s["name"], s["name"]),
                "wfd_waterbody_id": p.get("wb_id"), "lat": s["lat"], "lon": s["lon"],
                "site_ids": {"bathing_water": bid, **({"wqa_point": wqa} if wqa else {})},
                "depth_m": p.get("depth_m"), "lake_type": p.get("lake_type")}
        lakes.append(lake_record(base, sat_f[sat_f["bw_id"] == bid], sat_sizes.get(bid, {}), meta, "every_scene",
                                 lab_rows(values, wqa) if wqa in chl_pts else [], as_of, processed_to,
                                 refresh_for(bid) + (refresh_for(wqa) if wqa else []), sat_years.get(bid, {})))
    for wqa, p in sorted(chl_pts.items()):
        if wqa in by_wqa:
            continue   # a bathing water: its full series is above, with these lab values
        base = {"lake_id": f"wqa-{wqa}", "name": p.get("lake_name") or p.get("point_label"),
                "water_body": p.get("lake_name"), "wfd_waterbody_id": p.get("wb_id"), "lat": p["lat"], "lon": p["lon"],
                "site_ids": {"wqa_point": wqa}, "depth_m": p.get("depth_m"), "lake_type": p.get("lake_type")}
        lakes.append(lake_record(base, chl_f[chl_f["bw_id"] == wqa], chl_sizes.get(wqa, {}), meta, "near_lab_samples",
                                 lab_rows(values, wqa), as_of, processed_to, refresh_for(wqa), chl_years.get(wqa, {})))
    by_wb = {}
    for lk in lakes:
        by_wb.setdefault(lk["water_body_key"], []).append(lk["lake_id"])
    for lk in lakes:
        lk["shares_water_body_with"] = [x for x in by_wb[lk["water_body_key"]] if x != lk["lake_id"]]
    after = {k: sha256(p) for k, p in inputs().items()}
    if after != before:
        raise SystemExit(f"an input changed during the export: {[k for k in before if before[k] != after[k]]}")
    return {"schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "as_of": as_of.isoformat(),
            "processing": {"version": PROCESSING, "processed_to": processed_to, "season_months": list(SEASON),
                           "display_rules": {"min_sun_deg": MIN_SUN_DEG, "out_of_season_min_water_share": MIN_WATER_SHARE},
                           "code": {"sha256": code_hashes(), "commit_at_export": git_commit(),
                                    "note": "the file hashes are authoritative; the commit may predate them"},
                           "sources": [{"input": k, "sha256": v} for k, v in before.items()],
                           "refreshes": [info for _, info in refreshed]},
            "claim": CLAIM, "freshness_rules": {"recent_days": RECENT_DAYS, "older_days": OLDER_DAYS},
            "season_reasons": SEASON_NOTES,
            "release": release(lakes, processed_to),
            "attribution": attribution(sat_f, chl_f),
            "lab_definition": LAB_DEFINITION, "quality": quality(sat_f), "lakes": lakes, "coverage": coverage(lakes)}


def release(lakes: list[dict], historical_to: str) -> dict:
    """What kind of release this file is (docs/RESEARCH-WORKFLOW.md: a historical release says so prominently;
    "latest observations" needs a running refresh and measured coverage)."""
    refreshed = sorted(lk["lake_id"] for lk in lakes if lk["refreshes"])
    return {"scope": "historical", "historical_to": historical_to, "refreshed_sites": refreshed,
            "regular_refresh": False,
            "label": "Historical satellite observations, May to September 2020 to "
                     f"{historical_to[:4]}, with the date of every image. Not the latest images: no regular refresh "
                     "runs yet." + (f" {len(refreshed)} site{'s' if len(refreshed) != 1 else ''} also "
                                    f"{'have' if len(refreshed) != 1 else 'has'} experimental readings from a one-off "
                                    "refresh after the season." if refreshed else "")}


def attribution(*frames: pd.DataFrame) -> list[str]:
    """The notices the data terms require (docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md, "Data terms")."""
    years = sorted({d[:4] for f in frames for d in f["scene_date"]})
    return [f"Contains modified Copernicus Sentinel data [{years[0]}-{years[-1]}]",
            "Lab chlorophyll: Environment Agency Water Quality Archive, Open Government Licence v3.0"]


def quality(f: pd.DataFrame) -> dict:
    """Measurement variability, from the bathing-water lakes' readings: two usable scenes of one site on one date
    (two satellites, or two tiles) against each other, and the spread of a site's readings. Descriptions for the
    page's explanation, not an uncertainty bound."""
    u = f[f["usable"] & f["reading"].notna()]
    g = u.groupby(["bw_id", "scene_date"])["reading"].agg(["size", "min", "max"])
    d = (g["max"] - g["min"])[g["size"] > 1]
    return {"same_date_pairs": int(len(d)), "same_date_abs_difference_median": round(float(d.median()), 4),
            "same_date_abs_difference_p90": round(float(d.quantile(0.9)), 4),
            "within_site_sd_median": round(float(u.groupby("bw_id")["reading"].std().median()), 4),
            "note": "Two readings of one lake on one date often differ by a few hundredths and sometimes by much more, "
                    "so a small change between dates may be measurement variability rather than a change in the "
                    "water. These figures describe that variability; they are not an uncertainty bound."}


def coverage(lakes: list[dict]) -> dict:
    fr = [lk["latest"]["freshness"] for lk in lakes]
    rs = [r for lk in lakes for r in lk["latest"]["reasons"]]
    return {"lakes": len(lakes), "water_bodies": len({lk["water_body_key"] for lk in lakes}),
            "with_reading": sum(lk["latest"]["ndci"] is not None for lk in lakes),
            "experimental_readings": sum(x["experimental"] for lk in lakes for x in lk["series"]),
            "excluded_refresh_readings": sum(len(lk["excluded"]) for lk in lakes),
            "by_freshness": {k: fr.count(k) for k in FRESHNESS}, "by_reason": {k: rs.count(k) for k in REASONS},
            "too_small": [lk["lake_id"] for lk in lakes if "too_small" in lk["latest"]["reasons"]],
            "scenes": sum(s["scenes"] for lk in lakes for s in lk["seasons"]),
            "usable": sum(s["usable"] for lk in lakes for s in lk["seasons"]),
            "lab_measurements": sum(len(lk["lab"]) for lk in lakes),
            "lab_censored": sum(m["censored"] is not None for lk in lakes for m in lk["lab"])}


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


# ------------------------------------------------------------------ the contract check
def check(doc: dict) -> list[str]:
    """Every way `doc` breaks docs/LAKE-OBSERVATIONS-CONTRACT-v1.md, as sentences; empty when it holds."""
    err = []
    rel = doc.get("release", {})
    if rel.get("scope") not in ("historical", "latest") or not rel.get("label"):
        err.append("release must give a scope (historical or latest) and a label")
    if rel.get("scope") == "latest" and not rel.get("regular_refresh"):
        err.append("a 'latest' release needs a regular refresh")
    if not any("Copernicus Sentinel" in a for a in doc.get("attribution", [])):
        err.append("attribution must carry the Copernicus Sentinel notice")
    ld = doc.get("lab_definition", {})
    if not all(ld.get(k) for k in ("target", "determinand", "unit", "method_note", "source")):
        err.append("lab_definition must give target, determinand, unit, method_note and source")
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version is not swimsignal.lake-observations 1.x")
    for k in ("generated_at", "as_of", "processing", "claim", "freshness_rules", "release", "attribution",
              "lab_definition", "quality", "lakes", "coverage"):
        if k not in doc:
            err.append(f"missing top-level field {k}")
    claim = doc.get("claim", {})
    if not claim.get("public_wording") or "not swimming advice" not in claim.get("public_wording", ""):
        err.append("claim.public_wording must be present and say it is not swimming advice")
    words = claim.get("public_wording", "").lower()
    for bad in ("safe to swim", "algae-free", "toxin-free", "µg/l"):
        if bad in words:
            err.append(f"claim.public_wording uses a forbidden phrase: {bad}")
    as_of = date.fromisoformat(doc["as_of"]) if "as_of" in doc else None
    ids = set()
    for lk in doc.get("lakes", []):
        lid = lk.get("lake_id", "?")
        if lid in ids:
            err.append(f"{lid}: duplicate lake_id")
        ids.add(lid)
        for k in ("name", "water_body", "water_body_key", "lat", "lon", "site_ids", "mask", "series_scope",
                  "coverage_label", "processed_to", "latest", "seasons", "series", "excluded", "refreshes", "lab"):
            if k not in lk:
                err.append(f"{lid}: missing {k}")
        if lk.get("series_scope") not in ("every_scene", "near_lab_samples"):
            err.append(f"{lid}: series_scope {lk.get('series_scope')!r}")
        if not (-90 <= lk.get("lat", 999) <= 90 and -180 <= lk.get("lon", 999) <= 180):
            err.append(f"{lid}: coordinates out of range")
        lt = lk.get("latest", {})
        if lt.get("freshness") not in FRESHNESS:
            err.append(f"{lid}: freshness {lt.get('freshness')!r}")
        if any(r not in REASONS for r in lt.get("reasons", [])):
            err.append(f"{lid}: unknown reason in {lt.get('reasons')}")
        s = lk.get("series", [])
        dates = [x["date"] for x in s]
        if dates != sorted(dates):
            err.append(f"{lid}: series not in date order")
        if any(not (-1.0 <= x["ndci"] <= 1.0) for x in s):
            err.append(f"{lid}: an NDCI outside -1..1")
        if any(x["clear_core"] < MASK["min_clear_share"] * x["n_core"] for x in s):
            err.append(f"{lid}: a series reading below the clear rule")
        for x in s:
            if as_of and x["date"] > as_of.isoformat():
                err.append(f"{lid}: a reading dated after as_of ({x['date']})")
            if x.get("datetime") and doc.get("generated_at") and x["datetime"] > doc["generated_at"].replace("+00:00", "Z"):
                err.append(f"{lid}: an image time after generated_at ({x['datetime']})")
            if (x.get("season") == "out_of_season") != bool(x.get("experimental")):
                err.append(f"{lid}: an out-of-season reading must be experimental, and only those")
            if x.get("experimental") and not str(x.get("source", "")).startswith("refresh:"):
                err.append(f"{lid}: an experimental reading must come from a refresh")
            if x.get("experimental") and x.get("clear_water_share", 0) < MIN_WATER_SHARE:
                err.append(f"{lid}: an out-of-season reading below the water-share rule")
        if lt.get("age_days") is not None and lt["age_days"] < 0:
            err.append(f"{lid}: negative age_days")
        if lt.get("scope") != "latest_in_dataset":
            err.append(f"{lid}: latest.scope must be latest_in_dataset")
        if lk.get("mask", {}).get("passes_size_rule"):
            yrs = [x["year"] for x in lk.get("seasons", [])]
            if yrs != list(YEARS):
                err.append(f"{lid}: seasons are not exactly {YEARS[0]}-{YEARS[-1]}, once each")
            for x in lk.get("seasons", []):
                if x["scenes"] == 0 and x.get("reason") not in SEASON_REASONS:
                    err.append(f"{lid}: empty season {x['year']} without a reason")
                if x["scenes"] > 0 and x.get("reason") is not None:
                    err.append(f"{lid}: season {x['year']} has scenes and a reason")
        prim = [x for x in s if x.get("primary")]
        if s and (not prim or lt.get("item_id") != prim[-1]["item_id"]):
            err.append(f"{lid}: latest is not the last primary series reading")
        if len({x["date"] for x in prim}) != len(prim) or {x["date"] for x in prim} != {x["date"] for x in s}:
            err.append(f"{lid}: not exactly one primary reading per date")
        if not s and (lt.get("ndci") is not None or lt.get("freshness") != "none"):
            err.append(f"{lid}: a latest reading with no series")
        if s and as_of and lt.get("age_days") != (as_of - date.fromisoformat(s[-1]["date"])).days:
            err.append(f"{lid}: age_days does not match as_of")
        if not s and not ({"too_small", "no_usable_scene"} & set(lt.get("reasons", []))):
            err.append(f"{lid}: no reading and no reason why")
        if lk.get("series_scope") == "near_lab_samples" and "series_partial" not in lt.get("reasons", []):
            err.append(f"{lid}: partial series without the series_partial reason")
        for m in lk.get("lab", []):
            if m.get("sample_time") is None or m.get("value") is None:
                err.append(f"{lid}: a lab measurement without a time or value")
            if m.get("censored") not in (None, "<", ">"):
                err.append(f"{lid}: censoring {m.get('censored')!r}")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "check"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--refresh", type=Path, action="append", default=[], help="a refresh root (repeatable)")
    a = ap.parse_args()
    if a.step == "export":
        doc = build(a.as_of, a.refresh)
        problems = check(doc)
        if problems:
            raise SystemExit("the export breaks the contract:\n" + "\n".join(problems))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(json.dumps(doc["coverage"], indent=1))
        print(f"wrote {a.out} ({a.out.stat().st_size:,} bytes)")
    else:
        path = Path(a.path) if a.path else OUT
        problems = check(json.loads(path.read_text()))
        print("\n".join(problems) or f"{path}: holds the contract")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
