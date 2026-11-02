"""Sampling gaps, Research Lab exhibit 5: where the lab samples behind the E. coli model are, where they are not, and
the figures the exhibit's comparison of candidate seasons works from. One file, prototypes/research-lab/sampling/gaps.json.

Everything else the exhibit shows (each bathing water's samples by year, month and rain; the #381 simulation's four
policies, its runs and its failed verdict; the cost form's starting values) it reads from the sampling planner's own
file, data/research/sampling_planner.v1.json (docs/SAMPLING-PLANNER-CONTRACT-v1.md), copied to lab/data/ by the build.
This file adds only what that one lacks:

- every SwimSignal spot with its place, kind, area and how many lab samples it has (spots.csv, spots-osm.csv, the
  E. coli evidence file, the Waterhead group's file), so the gaps can be drawn on a map;
- each bathing water's samples by year and month together, and the Waterhead group's, for the calendar of gaps;
- how often the EA's samples, taken on days fixed in advance, followed more than 10 mm of rain in 48 hours, by area and
  by month (the concentration study's 2024-26 rows, archived lead-0 forecast rain). A rough guide to how many samples a
  fixed schedule would take after rain, never a forecast of rain.

From files already in the repository, read only: no fetch, no model, no simulation. Each input's SHA-256 is recorded.

    uv run python scripts/lab_sampling_gaps.py export
    uv run python scripts/lab_sampling_gaps.py check
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "prototypes" / "research-lab" / "sampling" / "gaps.json"
SCHEMA, VERSION = "swimsignal.lab-sampling-gaps", "1.0.0"
EVIDENCE = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
WET = ROOT / "data" / "research" / "waterhead_wet.v1.json"
PLANNER = ROOT / "data" / "research" / "sampling_planner.v1.json"
RAIN_ROWS = ROOT / "docs" / "CONCENTRATION-STUDY-2026-11-atlas-rows.csv"
SPOT_FILES = (ROOT / "spots.csv", ROOT / "spots-osm.csv")
WET_MM = 10   # more than 10 mm in the 48 hours before the sample: the concentration study's line, as the planner's
MONTHS = [f"{m:02d}" for m in range(1, 13)]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def read_spots() -> list[dict]:
    rows = []
    for f in SPOT_FILES:
        with f.open(newline="") as fh:
            rows += [{"id": r["id"], "name": r["name"], "lat": round(float(r["lat"]), 5), "lon": round(float(r["lon"]), 5),
                      "kind": r["kind"], "area": r["area"] or "Other"} for r in csv.DictReader(fh)]
    return rows


def calendar(dates: list[str], years: list[str]) -> list[list[int]]:
    """Samples by year (rows) and month (columns, January first), from ISO dates."""
    n = Counter(d[:7] for d in dates)
    return [[n[f"{y}-{m}"] for m in MONTHS] for y in years]


def build() -> dict:
    ev, wet = json.loads(EVIDENCE.read_text()), json.loads(WET.read_text())
    spots = read_spots()
    area = {s["id"]: s["area"] for s in spots}
    local = set(wet.get("spots", []))
    wet_dates = [x["date"] for x in wet["samples"]]
    years = sorted({x["t"][:4] for s in ev["sites"] for x in s["samples"]} | {d[:4] for d in wet_dates})
    ea = {s["spot_id"]: s for s in ev["sites"]}
    out_spots = [{**s, "ea": len(ea[s["id"]]["samples"]) if s["id"] in ea else 0,
                  "local": len(wet_dates) if s["id"] in local else 0} for s in spots]
    rows = [{"spot_id": s["spot_id"], "name": s["name"], "kind": s["kind"], "area": area.get(s["spot_id"], "Other"),
             "who": "ea", "by_month": calendar([x["t"][:10] for x in s["samples"]], years)} for s in ev["sites"]]
    rows += [{"spot_id": sid, "name": next(s["name"] for s in spots if s["id"] == sid), "kind": "lake",
              "area": area.get(sid, "Other"), "who": "local", "by_month": calendar(wet_dates, years)} for sid in sorted(local)]
    by_area, by_month = {}, {}
    with RAIN_ROWS.open(newline="") as fh:
        for r in csv.DictReader(fh):
            a, m, w = area.get("bw-" + r["bw_id"], "Other"), r["sample_time"][5:7], float(r["rain_48h"]) > WET_MM
            for d, k in ((by_area, a), (by_month, m)):
                d.setdefault(k, [0, 0])
                d[k][0] += 1
                d[k][1] += w
    inputs = [EVIDENCE, WET, PLANNER, RAIN_ROWS, *SPOT_FILES]
    return {
        "schema": SCHEMA, "version": VERSION, "made": datetime.now(UTC).isoformat(timespec="seconds"),
        "outcomes_to": max(x["t"][:10] for s in ev["sites"] for x in s["samples"]),
        "years": years, "months": MONTHS,
        "spots": out_spots,
        "calendar": rows,
        "fixed_day_rain": {"mm_48h": WET_MM, "period": "2024-2026",
                           "note": "EA samples are taken on days fixed in advance, so the share after rain is about what "
                                   "a fixed schedule in the same area and months would get. Archived forecast rain, not a gauge.",
                           "by_area": {k: {"rows": v[0], "wet": v[1]} for k, v in sorted(by_area.items())},
                           "by_month": {k: {"rows": v[0], "wet": v[1]} for k, v in sorted(by_month.items())}},
        "attribution": ["Environment Agency bathing water quality data, Open Government Licence v3.0",
                        wet["attribution"]],
        "sources": [{"file": rel(p), "sha256": sha256(p)} for p in inputs]
                   + [{"file": "scripts/lab_sampling_gaps.py", "sha256": sha256(Path(__file__))}],
    }


def check(doc: dict) -> list[str]:
    err = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    planner = json.loads(PLANNER.read_text())["coverage"]
    sp = doc.get("spots", [])
    if len(sp) != planner["spots"]["total"]:
        err.append(f"{len(sp)} spots, the planner has {planner['spots']['total']}")
    if sum(1 for s in sp if s["ea"]) != planner["spots"]["with_ea"]:
        err.append("spots with EA samples differ from the planner's")
    if sum(s["ea"] for s in sp) != planner["samples"]:
        err.append("EA samples differ from the planner's")
    for r in doc.get("calendar", []):
        if r["who"] == "ea":
            site = next((s for s in planner["sites"] if s["spot_id"] == r["spot_id"]), None)
            if not site or [sum(y) for y in r["by_month"]] != site["by_year"]:
                err.append(f"{r['name']}: the calendar's years differ from the planner's")
    rain = doc.get("fixed_day_rain", {})
    for k in ("by_area", "by_month"):
        if sum(v["rows"] for v in rain.get(k, {}).values()) != planner["wet"]["rows"] or \
                sum(v["wet"] for v in rain.get(k, {}).values()) != planner["wet"]["wet_rows"]:
            err.append(f"rain {k} does not add up to the planner's rows")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "check"])
    a = ap.parse_args()
    if a.step == "export":
        before = {p: sha256(p) for p in (EVIDENCE, WET, PLANNER, RAIN_ROWS, *SPOT_FILES)}
        doc = build()
        if problems := check(doc):
            raise SystemExit("\n".join(problems))
        if any(sha256(p) != h for p, h in before.items()):
            raise SystemExit("an input changed during the run")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"wrote {rel(OUT)}: {len(doc['spots'])} spots, {len(doc['calendar'])} sampled places, inputs unchanged")
    else:
        problems = check(json.loads(OUT.read_text()))
        print("\n".join(problems) or f"{rel(OUT)}: matches the planner's file")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
