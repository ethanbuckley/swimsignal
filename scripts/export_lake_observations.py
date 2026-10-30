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

SCHEMA, VERSION = "swimsignal.lake-observations", "1.0.0"
PROCESSING = "s2c1-l2a.ndci-core-median.v1"
SEASON = (5, 6, 7, 8, 9)
RECENT_DAYS, OLDER_DAYS = 14, 60
SHALLOW_M = 3.0
MASK = {"site_radius_m": 300, "pixel_m": 20, "min_core_pixels": 9, "min_clear_share": 0.80}
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


def seasons(f: pd.DataFrame) -> list[dict]:
    out = []
    for y, g in f.groupby(f["scene_date"].str[:4]):
        u = g[g["usable"] & g["reading"].notna()]
        out.append({"year": int(y), "scenes": int(len(g)), "usable": int(len(u)),
                    "usable_share": round(len(u) / len(g), 4) if len(g) else None,
                    "median_ndci": round(float(u["reading"].median()), 4) if len(u) else None,
                    "first": u["scene_date"].min() if len(u) else None, "last": u["scene_date"].max() if len(u) else None})
    return out


def lake_record(base: dict, f: pd.DataFrame, sizes: dict, meta: dict, scope: str, lab: list[dict], as_of: date,
                processed_to: str) -> dict:
    tiles = {t: {"n_core": v["n_core"], "passes": bool(v["passes"])} for t, v in (sizes.get("tiles") or {}).items()}
    passes = any(v["passes"] for v in tiles.values())
    use = f[f["usable"] & f["reading"].notna()].sort_values(["scene_date", "item_id"])
    series = [{"date": r.scene_date, "datetime": meta.get(r.item_id, {}).get("datetime"), "item_id": r.item_id,
               "tile": r.tile, "processing_baseline": meta.get(r.item_id, {}).get("processing_baseline"),
               "clear_core": int(r.clear_core), "n_core": int(r.n_core), "ndci": round(float(r.reading), 5)}
              for r in use.itertuples()]
    last = series[-1] if series else None
    age, fresh = freshness(last["date"] if last else None, as_of)
    reasons = []
    if not passes:
        reasons.append("too_small")
    elif not series:
        reasons.append("no_usable_scene")
    if as_of.month not in SEASON:
        reasons.append("season_closed")
    if as_of.isoformat() > processed_to:
        reasons.append("not_refreshed")
    if scope == "near_lab_samples":
        reasons.append("series_partial")
    latest = None if last is None else {"date": last["date"], "datetime": last["datetime"], "item_id": last["item_id"],
                                        "ndci": last["ndci"], "clear_share": round(last["clear_core"] / last["n_core"], 4)}
    return {**base, "mask": {**MASK, "tiles": tiles, "passes_size_rule": passes}, "series_scope": scope,
            "latest": {**(latest or {"date": None, "datetime": None, "item_id": None, "ndci": None, "clear_share": None}),
                       "age_days": age, "freshness": fresh, "reasons": reasons},
            "seasons": seasons(f) if len(f) else [], "series": series, "lab": lab}


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


def build(as_of: date) -> dict:
    sys.path.insert(0, str(ROOT / "scripts" / "lake_algae_sat_eval"))
    from protocol import WATER_BODY
    before = {k: sha256(p) for k, p in inputs().items()}
    sat_f, chl_f = pd.read_parquet(SAT / "features.parquet"), pd.read_parquet(CHL / "features.parquet")
    sat_sizes, chl_sizes = json.loads((SAT / "sizes.json").read_text()), json.loads((CHL / "sizes.json").read_text())
    meta = {**item_meta(SAT / "items"), **item_meta(CHL / "items")}
    values = pd.read_parquet(CHL / "values.parquet")
    bathing = {s["id"]: s for s in json.loads(BATHING.read_text()) if s["kind"] == "lake"}
    chl_pts = {p["wqa_point"]: p for p in json.loads(CHL_LAKES.read_text())["points"]}
    by_wqa = {s.get("wqa_point"): bid for bid, s in bathing.items() if s.get("wqa_point")}
    processed_to = max(sat_f["scene_date"].max(), chl_f["scene_date"].max())
    lakes = []
    for bid, s in sorted(bathing.items()):
        wqa = s.get("wqa_point")
        p = chl_pts.get(wqa, {})
        base = {"lake_id": f"bw-{bid}", "name": s["name"], "water_body": WATER_BODY.get(s["name"], s["name"]),
                "wfd_waterbody_id": p.get("wb_id"), "lat": s["lat"], "lon": s["lon"],
                "site_ids": {"bathing_water": bid, **({"wqa_point": wqa} if wqa else {})},
                "depth_m": p.get("depth_m"), "lake_type": p.get("lake_type")}
        lakes.append(lake_record(base, sat_f[sat_f["bw_id"] == bid], sat_sizes.get(bid, {}), meta, "every_scene",
                                 lab_rows(values, wqa) if wqa in chl_pts else [], as_of, processed_to))
    for wqa, p in sorted(chl_pts.items()):
        if wqa in by_wqa:
            continue   # a bathing water: its full series is above, with these lab values
        base = {"lake_id": f"wqa-{wqa}", "name": p.get("lake_name") or p.get("point_label"),
                "water_body": p.get("lake_name"), "wfd_waterbody_id": p.get("wb_id"), "lat": p["lat"], "lon": p["lon"],
                "site_ids": {"wqa_point": wqa}, "depth_m": p.get("depth_m"), "lake_type": p.get("lake_type")}
        lakes.append(lake_record(base, chl_f[chl_f["bw_id"] == wqa], chl_sizes.get(wqa, {}), meta, "near_lab_samples",
                                 lab_rows(values, wqa), as_of, processed_to))
    after = {k: sha256(p) for k, p in inputs().items()}
    if after != before:
        raise SystemExit(f"an input changed during the export: {[k for k in before if before[k] != after[k]]}")
    return {"schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "as_of": as_of.isoformat(),
            "processing": {"version": PROCESSING, "processed_to": processed_to, "season_months": list(SEASON),
                           "code": {"readings": "scripts/lake_algae_sat_eval (stage1.py, protocol.py), "
                                                "scripts/lake_chlorophyll_eval (chl_stage1.py)",
                                    "export": "scripts/export_lake_observations.py", "commit": git_commit()},
                           "sources": [{"input": k, "sha256": v} for k, v in before.items()]},
            "claim": CLAIM, "freshness_rules": {"recent_days": RECENT_DAYS, "older_days": OLDER_DAYS},
            "lab_definition": LAB_DEFINITION, "lakes": lakes, "coverage": coverage(lakes)}


def coverage(lakes: list[dict]) -> dict:
    fr = [lk["latest"]["freshness"] for lk in lakes]
    rs = [r for lk in lakes for r in lk["latest"]["reasons"]]
    return {"lakes": len(lakes), "with_reading": sum(lk["latest"]["ndci"] is not None for lk in lakes),
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
    ld = doc.get("lab_definition", {})
    if not all(ld.get(k) for k in ("target", "determinand", "unit", "method_note", "source")):
        err.append("lab_definition must give target, determinand, unit, method_note and source")
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version is not swimsignal.lake-observations 1.x")
    for k in ("generated_at", "as_of", "processing", "claim", "freshness_rules", "lab_definition", "lakes", "coverage"):
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
        for k in ("name", "water_body", "lat", "lon", "site_ids", "mask", "series_scope", "latest", "seasons", "series", "lab"):
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
        if s and lt.get("date") != s[-1]["date"]:
            err.append(f"{lid}: latest is not the last series reading")
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
    a = ap.parse_args()
    if a.step == "export":
        doc = build(a.as_of)
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
