"""The catchment workspace, Research Lab exhibit 4: one file per catchment holding every layer the page draws.

Two catchments, chosen because the repository already holds most layers for them: Windermere (Waterhead and the four
EA bathing waters) and the Wharfe at Ilkley (Cromwheel). For each, from 1 Jan 2024 to 30 Sep 2026 (outcomes after
30 Sep are left out: the active evaluation windows are frozen):

- rain: Open-Meteo's ERA5-Land archive (the forecast's own cache, data/cache/rain), daily totals by UK date, averaged
  over the 0.1 degree cells that hold the spots and their upstream overflows. A day any cell lacks is a gap, not zero.
- spills: every overflow upstream of the catchment's spots (assets/paths, the forecast's own network), with each event
  from the EA's 2024 and 2025 start/stop files (data/processed/ea_events_*.parquet). 2026 events are not published yet.
- E. coli: EA samples and the hindsight estimates beside them (data/research/ecoli_evidence.v1.json); WET samples at
  Waterhead (data/research/waterhead_wet.v1.json).
- water temperature: EA readings in the lake, May to September (data/research/lake_temperature_obs.v1.json).
- satellite: NDCI at each bathing water (data/research/lake_observations.v1.json).

Offline: no request is made and no dipcast module is imported. The caches are read from DIPCAST_ROOT, which must be a
scratch folder whose data/ holds links to the cached inputs (AGENTS.md); they are hashed before and after and the run
fails if any changed. Writes only to prototypes/research-lab/workspace/data/.

    DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch>/state uv run python scripts/lab_catchment_workspace.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LAB = REPO / "prototypes" / "research-lab"
OUT = LAB / "workspace" / "data"
RESEARCH = REPO / "data" / "research"
START, END = date(2024, 1, 1), date(2026, 9, 30)
TZ = "Europe/London"
GRID = 0.1               # config.RAIN_GRID_DEG; the cache's cell size

assert os.environ.get("DIPCAST_ROOT") and os.environ.get("DIPCAST_STATE"), "set scratch DIPCAST_ROOT and DIPCAST_STATE"
ROOT = Path(os.environ["DIPCAST_ROOT"]).resolve()
assert ROOT != REPO and not str(ROOT).startswith(str(REPO.parent.parent)), "DIPCAST_ROOT must be a scratch folder"

CATCHMENTS = {
    "windermere": {
        "name": "Windermere",
        "short": "Windermere",
        "kind": "lake",
        "spots": ["osm-windermere-waterhead", "bw-ukd1203-45675", "bw-ukd1203-45650", "bw-ukd1203-45625", "bw-ukd1203-45700"],
        "company": "united_utilities",
        "temperature_lakes": ["GB31247007", "GB31247008"],
        "spots_source": {"name": "Four EA designated bathing waters; Waterhead from OpenStreetMap (spots-osm.csv)",
                         "licence": "Open Government Licence v3.0; Waterhead: Open Database Licence 1.0",
                         "credit": "Bathing water positions: Environment Agency, OGL v3.0. Waterhead position: © OpenStreetMap contributors, ODbL 1.0"},
        "intro": "England's largest lake. Waterhead, at its north end by Ambleside, has weekly samples from a local "
                 "group; four EA bathing waters further south are sampled through the season.",
    },
    "wharfe-ilkley": {
        "name": "The Wharfe at Ilkley",
        "short": "Wharfe at Ilkley",
        "kind": "river",
        "spots": ["bw-uke4100-08901"],
        "company": "yorkshire_water",
        "temperature_lakes": [],
        "spots_source": {"name": "EA designated bathing water", "licence": "Open Government Licence v3.0",
                         "credit": "Bathing water position: Environment Agency, OGL v3.0"},
        "intro": "England's first river bathing water (2020). Sixteen monitored overflows lie upstream within 60 km, "
                 "three of them within 1.1 km of the sampling point.",
    },
}

SOURCES = {
    "rain": {"name": "Open-Meteo historical weather API, ERA5-Land reanalysis (about 9 km), hourly, summed by UK day",
             "licence": "CC BY 4.0 (Open-Meteo); ERA5-Land: Copernicus Climate Change Service",
             "credit": "Weather data by Open-Meteo.com (CC BY 4.0); contains modified Copernicus Climate Change Service information"},
    "spills": {"name": "Environment Agency storm overflow EDM detailed start/stop data, 2024 and 2025",
               "licence": "Open Government Licence v3.0",
               "credit": "Environment Agency, storm overflow EDM start/stop data 2024 and 2025, OGL v3.0"},
    "ecoli": {"name": "Environment Agency bathing water samples (bathing water quality service and Water Quality Archive)",
              "licence": "Open Government Licence v3.0",
              "credit": "Environment Agency bathing water quality data, OGL v3.0"},
    "wet": {"name": "Ambleside Action for a Future, Waterhead E. coli Testing (WET) project",
            "licence": "Public domain, with credit (Tim Boden, 25 Oct 2026)",
            "credit": "Bacteria counts at Waterhead: Ambleside Action for a Future, Waterhead E. coli Testing (WET) project"},
    "hindsight": {"name": "SwimSignal model refitted leaving out each year (docs/CONCENTRATION-STUDY-2026-11.md)",
                  "licence": "SwimSignal's own estimates, this repository",
                  "credit": "Hindsight estimates: SwimSignal, refitted without that year's samples; never issued"},
    "temp": {"name": "Environment Agency Water Quality Archive, determinand 0076 (temperature of water), May to September",
             "licence": "Open Government Licence v3.0",
             "credit": "Environment Agency Water Quality Archive, OGL v3.0"},
    "sat": {"name": "Sentinel-2 L2A (Earth Search, sentinel-2-c1-l2a), NDCI median over clear water within 300 m",
            "licence": "Copernicus Sentinel data licence (free, with credit)",
            "credit": "Contains modified Copernicus Sentinel data [2024-2026]"},
    "map": {"name": "OS Open Rivers, via the forecast's network (assets/paths)",
            "licence": "Open Government Licence v3.0",
            "credit": "Contains OS data © Crown copyright and database right 2026"},
}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cell(lat: float, lon: float) -> tuple[float, float]:
    return round(round(lat / GRID) * GRID, 3) + 0.0, round(round(lon / GRID) * GRID, 3) + 0.0


def in_window(d: str) -> bool:
    return START.isoformat() <= d[:10] <= END.isoformat()


def r(v, n=2):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), n)


def rain_inputs(cells: list[tuple[float, float]]) -> list[Path]:
    out = []
    for la, lo in cells:
        for y in range(START.year, END.year + 1):
            p = ROOT / "data" / "cache" / "rain" / f"archive_{la:.3f}_{lo:.3f}_{y}.parquet"
            if p.exists():
                out.append(p)
    return out


def daily_rain(cells: list[tuple[float, float]]) -> tuple[list[dict], dict]:
    """Daily totals by UK date; a cell's day counts only with all its hours (23 to 25 with the clocks)."""
    per_cell = {}
    for la, lo in cells:
        frames = [pd.read_parquet(p) for y in range(START.year, END.year + 1)
                  if (p := ROOT / "data" / "cache" / "rain" / f"archive_{la:.3f}_{lo:.3f}_{y}.parquet").exists()]
        if not frames:
            per_cell[(la, lo)] = pd.Series(dtype=float)
            continue
        h = pd.concat(frames).drop_duplicates("time").set_index("time")["precip_mm"].dropna()
        local = h.tz_convert(TZ)
        g = local.groupby(local.index.date)
        expected = {d: int((pd.Timestamp(d + pd.Timedelta(days=1), tz=TZ) - pd.Timestamp(d, tz=TZ)) / pd.Timedelta(hours=1))
                    for d in g.size().index}
        full = g.size()[[g.size()[d] >= expected[d] for d in g.size().index]].index
        per_cell[(la, lo)] = g.sum()[full]
    rows, gap_days = [], 0
    d = pd.Timestamp(START)
    while d.date() <= END:
        vals = [s.get(d.date()) for s in per_cell.values()]
        if all(v is not None for v in vals):
            rows.append({"date": d.date().isoformat(), "mm": round(sum(vals) / len(vals), 1)})
        else:
            gap_days += 1
        d += pd.Timedelta(days=1)
    last = rows[-1]["date"] if rows else None
    return rows, {"cells": [list(c) for c in cells], "days": len(rows), "gap_days": gap_days, "last": last}


def spills(company: str, overflows: list[dict]) -> tuple[list[dict], dict]:
    p = ROOT / "data" / "processed" / f"ea_events_{company}.parquet"
    ev = pd.read_parquet(p, columns=["site_id", "event_start", "event_end", "duration_h", "source"])
    ids = {o["id"] for o in overflows}
    ev = ev[ev["site_id"].isin(ids)].copy()
    lo, hi = pd.Timestamp(START, tz=UTC), pd.Timestamp(END, tz=UTC) + pd.Timedelta(days=1)
    ev = ev[(ev["event_end"] >= lo) & (ev["event_start"] < hi)].sort_values(["site_id", "event_start"])
    rows = [{"overflow": e.site_id, "start": e.event_start.tz_convert(UTC).isoformat(timespec="minutes").replace("+00:00", "Z"),
             "end": e.event_end.tz_convert(UTC).isoformat(timespec="minutes").replace("+00:00", "Z"),
             "hours": round(float(e.duration_h), 2)} for e in ev.itertuples(index=False)]
    by = ev.groupby("site_id").size().to_dict()
    files = sorted(set(ev["source"]))
    return rows, {"events": len(rows), "by_overflow": {k: int(v) for k, v in by.items()},
                  "covered": ["2024-01-01", "2025-12-31"], "not_covered": ["2026-01-01", END.isoformat()],
                  "files": files, "input": p.name}


def build(cid: str, spec: dict, ecoli: dict, wet: dict, temps: dict, sat: dict) -> dict:
    paths = {s: json.loads((LAB / "assets" / "paths" / f"{s}.json").read_text()) for s in spec["spots"]}
    # overflows: the union over the catchment's spots, keeping each spot's own distance, travel time and weight
    ovs: dict[str, dict] = {}
    for sid, pj in paths.items():
        for o in pj["overflows"]:
            d = ovs.setdefault(o["id"], {k: o[k] for k in ("id", "name", "company", "water", "lat", "lon", "spills_a_year")} | {"at": {}})
            d["at"][sid] = {"km": o["distance_km"], "travel_h": o["travel_h"], "weight": o["weight"]}
    overflows = sorted(ovs.values(), key=lambda o: -max(v["weight"] or 0 for v in o["at"].values()))
    seen, lines = set(), []
    for pj in paths.values():
        for ln in pj["lines"]:
            k = json.dumps(ln["coords"])
            if k not in seen:
                seen.add(k)
                lines.append(ln)

    spots, samples = [], []
    for sid in spec["spots"]:
        pj = paths[sid]
        spots.append({"id": sid, "name": pj["name"], "lat": pj["lat"], "lon": pj["lon"], "kind": pj["kind"]})
        site = next((s for s in ecoli["sites"] if s["spot_id"] == sid), None)
        if site:
            for s in site["samples"]:
                if not in_window(s["t"]):
                    continue
                samples.append({"spot": sid, "t": s["t"], "date": s["t"][:10], "ecoli": s["ecoli"], "q": s["q"],
                                "src": "EA " + s["src"], "hindsight": s["hindsight"], "hindsight_reason": s["hindsight_reason"]})
        if sid in wet.get("spots", []):
            for s in wet["samples"]:
                if in_window(s["date"]):
                    samples.append({"spot": sid, "t": s["date"], "date": s["date"], "ecoli": s["ecoli"], "q": None,
                                    "src": "WET", "hindsight": None, "hindsight_reason": "not_ea"})
    samples.sort(key=lambda s: (s["date"], s["spot"]))

    tpoints, treads = [], []
    for lake in temps["lakes"]:
        if lake["wb_id"] not in spec["temperature_lakes"]:
            continue
        idx = {}
        for i, p in enumerate(lake["points"]):
            idx[i] = p["point"]
        used = set()
        rd = lake["readings"]
        for d, t, pi in zip(rd["date"], rd["temp"], rd["point"], strict=True):
            if in_window(d):
                treads.append({"date": d, "temp_c": t, "point": idx[pi], "lake": lake["name"]})
                used.add(pi)
        for i in sorted(used):
            p = lake["points"][i]
            tpoints.append({"id": p["point"], "label": p["label"], "lat": p["lat"], "lon": p["lon"], "lake": lake["name"]})
    treads.sort(key=lambda x: (x["date"], x["point"]))

    sreads, ssites = [], []
    for lake in sat["lakes"]:
        if lake["lake_id"] not in spec["spots"]:
            continue
        ssites.append({"id": lake["lake_id"], "name": lake["name"], "lat": lake["lat"], "lon": lake["lon"],
                       "seasons": [{k: s[k] for k in ("year", "scenes", "usable", "reason")} for s in lake["seasons"] if s["year"] >= START.year]})
        for s in lake["series"]:
            if in_window(s["date"]) and s.get("primary", True):
                sreads.append({"date": s["date"], "site": lake["lake_id"], "ndci": r(s["ndci"], 4), "season": s["season"],
                               "experimental": bool(s.get("experimental")), "scene": s["item_id"]})
    sreads.sort(key=lambda x: (x["date"], x["site"]))

    cells = sorted({cell(s["lat"], s["lon"]) for s in spots} | {cell(o["lat"], o["lon"]) for o in overflows})
    rain, rain_meta = daily_rain(cells)
    events, spill_meta = spills(spec["company"], overflows)
    for o in overflows:
        o["events_in_window"] = spill_meta["by_overflow"].get(o["id"], 0)

    pts = [(s["lat"], s["lon"]) for s in spots] + [(o["lat"], o["lon"]) for o in overflows] + [(p["lat"], p["lon"]) for p in tpoints]
    pts += [(lat, lon) for ln in lines for lon, lat in ln["coords"]]
    la, lo = [p[0] for p in pts], [p[1] for p in pts]
    pad_la, pad_lo = (max(la) - min(la)) * .06 + .01, (max(lo) - min(lo)) * .06 + .015
    box = {"w": round(min(lo) - pad_lo, 4), "e": round(max(lo) + pad_lo, 4), "s": round(min(la) - pad_la, 4), "n": round(max(la) + pad_la, 4)}

    return {"id": cid, "name": spec["name"], "short": spec["short"], "kind": spec["kind"], "intro": spec["intro"],
            "window": [START.isoformat(), END.isoformat()], "box": box,
            "spots": spots, "overflows": overflows, "lines": lines,
            "temp_points": tpoints, "sat_sites": ssites,
            "layers": {
                "rain": {"rows": rain, "meta": rain_meta},
                "spills": {"rows": events, "meta": spill_meta},
                "ecoli": {"rows": samples, "meta": {"line": ecoli["line"], "warn_at": ecoli["warn_at"], "warn_at_note": ecoli["warn_at_note"],
                                                    "hindsight_reasons": ecoli["hindsight_reasons"] | {"not_ea": "WET samples are not in the hindsight study."}}},
                "temp": {"rows": treads, "meta": {"months": [5, 6, 7, 8, 9], "applies": bool(spec["temperature_lakes"])}},
                "sat": {"rows": sreads, "meta": {"applies": spec["kind"] == "lake", "season_months": sat["processing"]["season_months"],
                                                 "not_claimed": sat["claim"]["not_claimed"]}},
            }}


def main() -> None:
    ecoli = json.loads((RESEARCH / "ecoli_evidence.v1.json").read_text())
    wet = json.loads((RESEARCH / "waterhead_wet.v1.json").read_text())
    temps = json.loads((RESEARCH / "lake_temperature_obs.v1.json").read_text())
    sat = json.loads((RESEARCH / "lake_observations.v1.json").read_text())

    # every cached input this run reads, hashed before and after
    cached = [ROOT / "data" / "processed" / f"ea_events_{c['company']}.parquet" for c in CATCHMENTS.values()]
    for spec in CATCHMENTS.values():
        cs = set()
        for s in spec["spots"]:
            pj = json.loads((LAB / "assets" / "paths" / f"{s}.json").read_text())
            cs.add(cell(pj["lat"], pj["lon"]))
            cs |= {cell(o["lat"], o["lon"]) for o in pj["overflows"]}
        cached += rain_inputs(sorted(cs))
    before = {str(p.relative_to(ROOT)): sha(p) for p in cached}

    commit = subprocess.run(["git", "rev-parse", "--short=8", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    committed = {f: sha(RESEARCH / f) for f in ("ecoli_evidence.v1.json", "waterhead_wet.v1.json",
                                                 "lake_temperature_obs.v1.json", "lake_observations.v1.json")}
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for cid, spec in CATCHMENTS.items():
        c = build(cid, spec, ecoli, wet, temps, sat)
        c |= {"made": datetime.now(UTC).isoformat(timespec="seconds"), "commit": commit,
              "code_sha256": sha(Path(__file__)), "sources": SOURCES | {"spots": spec["spots_source"]},
              "inputs": {"committed": committed,
                         "cached": {k: v for k, v in before.items() if f"ea_events_{spec['company']}" in k or "/rain/" in k}}}
        (OUT / f"{cid}.json").write_text(json.dumps(c, separators=(",", ":"), ensure_ascii=False) + "\n")
        n = {k: len(v["rows"]) for k, v in c["layers"].items()}
        index.append({"id": cid, "name": c["name"], "short": c["short"], "kind": c["kind"],
                      "lat": c["spots"][0]["lat"], "lon": c["spots"][0]["lon"], "rows": n})
        print(cid, n, c["layers"]["rain"]["meta"], {k: v for k, v in c["layers"]["spills"]["meta"].items() if k != "by_overflow"})

    after = {str(p.relative_to(ROOT)): sha(p) for p in cached}
    assert before == after, "a cached input changed during the run"
    (OUT / "index.json").write_text(json.dumps({"catchments": index, "window": [START.isoformat(), END.isoformat()],
                                                "inputs_unchanged": True, "cached_inputs": len(before)}, indent=1) + "\n")
    print(f"{len(before)} cached inputs hashed before and after: unchanged")


if __name__ == "__main__":
    main()
