"""Sampling planner data, for the Research page's planning tool (docs/SAMPLING-PLANNER-CONTRACT-v1.md, issue #482). From
files already in the repository, read only; no fetch, no model fit and no simulation run:

    uv run python scripts/export_sampling_planner.py export [--out PATH]
    uv run python scripts/export_sampling_planner.py check [PATH]

Where the E. coli samples behind the model are thin: every Environment Agency sample at the 38 inland bathing waters by
year and month (data/research/ecoli_evidence.v1.json), how many of the 2024-26 study rows came after more than 10 mm of
rain in 48 hours (the concentration study's rows, docs/CONCENTRATION-STUDY-2026-11-atlas-rows.csv, archived lead-0
forecast rain), and which of the site's spots have no samples at all (spots.csv, spots-osm.csv, and the Waterhead
export's spots). And what the sampling-priorities simulation (#381, docs/SAMPLING-PRIORITIES-SIM-2026-10.md) found for
its four ways of spending a budget, copied from its three result files as they are. Its verdict (fail) is copied, not
recomputed. Nothing here allocates a sample or says one policy is more efficient in real water.
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
OUT = ROOT / "data" / "research" / "sampling_planner.v1.json"
SCHEMA, VERSION = "swimsignal.sampling-planner", "1.0.0"
EVIDENCE = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
RAIN_ROWS = ROOT / "docs" / "CONCENTRATION-STUDY-2026-11-atlas-rows.csv"
WET = ROOT / "data" / "research" / "waterhead_wet.v1.json"
SPOT_FILES = (ROOT / "spots.csv", ROOT / "spots-osm.csv")
SIM = {"main": ROOT / "docs" / "SAMPLING-PRIORITIES-SIM-2026-10.json",
       "tau0": ROOT / "docs" / "SAMPLING-PRIORITIES-SIM-2026-10-tau0.json",
       "budget120": ROOT / "docs" / "SAMPLING-PRIORITIES-SIM-2026-10-budget120.json"}
WET_MM = 10   # "wet": more than 10 mm in the 48 hours before the sample, the concentration study's line
MONTHS = ["05", "06", "07", "08", "09"]
# The simulation's world (docs/SAMPLING-PRIORITIES-SIM-2026-10.md, "The synthetic world"), as stated before its run.
WORLD = {"sites": 40, "never_sampled": 12, "weeks": 20, "max_per_day": 2,
         "note": "40 made-up sites, 12 of them never sampled before; a 20-week season, at most 2 samples a day. "
                 "The truth is a logistic model with normal site offsets, the same form the information score assumes."}
# The four ways the simulation spent its budget, in the page's order, with what each did. "Wet days" was not simulated
# as such: RISK, the highest predicted chance, is the nearest, and went to the wettest days.
POLICIES = [
    {"id": "COVER", "name": "Equal coverage", "rule": "Each week, the sites with the fewest samples so far, on a random weekday."},
    {"id": "RISK", "name": "Wettest, riskiest days",
     "rule": "Each week, the site-days with the highest predicted chance of a high count. Not a pure wet-day rule, "
             "which was not simulated, but in practice it picked the wettest days."},
    {"id": "INFO", "name": "Most informative",
     "rule": "Each week, the site-days whose result would teach the model most, by an information score (BALD)."},
    {"id": "RANDOM", "name": "Random", "rule": "Each week, site-days drawn at random. A reference, not a proposal."},
]
STRATEGY_FIELDS = ("P", "P_never", "P_sampled", "S4_exceedances", "share_never_sampled_sites", "share_lakes",
                   "mean_rain48", "sites_visited")
COST = {"samples": 60, "per_sample_gbp": 100, "sites": 12,
        "note": "Starting values to change, not a quote: 60 samples over 12 sites is the simulation's season. £100 a "
                "sample is a round figure; a lab's price, travel and staff time are not counted."}
CLAIM = {
    "public_wording": "Where the E. coli samples behind SwimSignal's model are thin, and what a simulation found for "
                      "simple ways of spending a sampling budget. A planning aid for a conversation with a sampler, "
                      "not a sampling plan: nothing here has been tested in real water.",
    "not_claimed": ["that any policy finds more pollution or teaches the model more in real water",
                    "that the information policy passed its test: it failed",
                    "a sampling plan or allocation for any site or day",
                    "the cost of any real sampling programme",
                    "that a site without samples is clean or polluted"],
}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def spots() -> list[dict]:
    rows = []
    for f in SPOT_FILES:
        with f.open(newline="") as fh:
            rows += [{"id": r["id"], "kind": r["kind"], "area": r["area"] or "Other"} for r in csv.DictReader(fh)]
    return rows


def rain_by_site() -> dict[str, tuple[int, int]]:
    """bw_id: (rows with rain, rows with more than WET_MM in 48 h), over the concentration study's 2024-26 rows."""
    n, wet = Counter(), Counter()
    with RAIN_ROWS.open(newline="") as fh:
        for r in csv.DictReader(fh):
            n[r["bw_id"]] += 1
            wet[r["bw_id"]] += float(r["rain_48h"]) > WET_MM
    return {k: (n[k], wet[k]) for k in n}


def coverage() -> dict:
    ev, rain = json.loads(EVIDENCE.read_text()), rain_by_site()
    local = set(json.loads(WET.read_text()).get("spots", []))
    years = sorted({x["t"][:4] for s in ev["sites"] for x in s["samples"]})
    sites = []
    for s in ev["sites"]:
        y, m = Counter(x["t"][:4] for x in s["samples"]), Counter(x["t"][5:7] for x in s["samples"])
        r = rain.get(s["bw_id"])
        sites.append({"spot_id": s["spot_id"], "name": s["name"], "kind": s["kind"], "samples": len(s["samples"]),
                      "by_year": [y[k] for k in years], "by_month": [m[k] for k in MONTHS],
                      "rain_rows": r[0] if r else None, "wet_rows": r[1] if r else None})
    sampled = {s["spot_id"] for s in sites}
    all_spots = spots()
    areas = sorted({s["area"] for s in all_spots})
    by_area = [{"area": a, "spots": sum(s["area"] == a for s in all_spots),
                "with_ea": sum(s["area"] == a and s["id"] in sampled for s in all_spots),
                "with_local": sum(s["area"] == a and s["id"] in local and s["id"] not in sampled for s in all_spots)}
               for a in areas]
    none = [s for s in all_spots if s["id"] not in sampled and s["id"] not in local]
    month = Counter(x["t"][5:7] for s in ev["sites"] for x in s["samples"])
    return {
        "samples": sum(s["samples"] for s in sites), "years": years, "months": MONTHS,
        "by_month": [month[k] for k in MONTHS],
        "outside_months": sum(v for k, v in month.items() if k not in MONTHS),
        "wet": {"mm_48h": WET_MM, "rows": sum(v[0] for v in rain.values()), "wet_rows": sum(v[1] for v in rain.values()),
                "sites": len(rain), "period": "2024-2026",
                "rain": "archived lead-0 forecast rain, the concentration study's rows (docs/CONCENTRATION-STUDY-2026-11.md)"},
        "spots": {"total": len(all_spots), "rivers": sum(s["kind"] == "river" for s in all_spots),
                  "lakes": sum(s["kind"] == "lake" for s in all_spots),
                  "with_ea": len(sampled & {s["id"] for s in all_spots}),
                  "with_local": len(local - sampled),
                  "none_rivers": sum(s["kind"] == "river" for s in none),
                  "none_lakes": sum(s["kind"] == "lake" for s in none), "by_area": by_area},
        "sites": sites,
    }


def simulation() -> dict:
    runs = []
    for name, p in SIM.items():
        s = json.loads(p.read_text())["summary"]
        r = lambda v, d=6: round(v, d)
        runs.append({
            "run": name, "replications": s["n_reps"], "tau": s["tau_world"], "budget": s["budget"],
            "per_site": s["budget"] / WORLD["never_sampled"],
            "P_history_only": r(s["P_history_only"]),
            "strategies": {k: {f: r(v[f]) for f in STRATEGY_FIELDS} for k, v in s["by_strategy"].items()},
            "info_vs": {k: {"share_info_lower": r(s["rule"][k]["share_info_lower"], 3),
                            "mean_gain": r(s["rule"][k]["mean_gain"]),
                            "ci95": [r(v) for v in s["rule"][k]["ci95"]]} for k in ("COVER", "RANDOM")},
        })
    main = runs[0]
    return {"doc": "docs/SAMPLING-PRIORITIES-SIM-2026-10.md", "issue": 381,
            "verdict": json.loads(SIM["main"].read_text())["summary"]["verdict"],
            "rule": "The information policy passes if, against each of equal coverage and random, its site-rate error "
                    "is lower in at least 60% of the 200 replications and the mean gain's 95% interval is above 0.",
            "verdict_words": f"Failed. Against equal coverage it had the lower error in "
                             f"{main['info_vs']['COVER']['share_info_lower'] * 100:.1f}% of simulated worlds, against "
                             "60% needed. Nothing was adopted.",
            "metric": "P, site-rate error: the mean over the 40 sites of the squared difference between the model's "
                      "rate for the held-out season and the true rate. Lower is better.",
            "world": WORLD, "runs": runs}


def build() -> dict:
    inputs = [EVIDENCE, RAIN_ROWS, WET, *SPOT_FILES, *SIM.values()]
    return {
        "schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "claim": CLAIM, "field_validation": False,
        "coverage": coverage(), "policies": POLICIES, "simulation": simulation(), "cost": COST,
        "field_study": "docs/SAMPLING-PLANNER-CONTRACT-v1.md#the-field-study-an-efficiency-claim-would-need",
        "attribution": ["Environment Agency bathing water quality data, Open Government Licence v3.0"],
        "sources": [{"file": rel(p), "sha256": sha256(p)} for p in inputs]
                   + [{"file": "scripts/export_sampling_planner.py", "sha256": sha256(Path(__file__))}],
    }


def check(doc: dict) -> list[str]:
    err = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    for k in ("claim", "coverage", "policies", "simulation", "cost", "field_study", "sources"):
        if k not in doc:
            err.append(f"missing {k}")
    if doc.get("field_validation") is not False:
        err.append("field_validation must be false until a field study says otherwise")
    if "not a sampling plan" not in doc.get("claim", {}).get("public_wording", ""):
        err.append("the claim must say it is not a sampling plan")
    c, sim = doc.get("coverage", {}), doc.get("simulation", {})
    if c and sum(s["samples"] for s in c["sites"]) != c["samples"]:
        err.append("site samples do not add up")
    for s in c.get("sites", []):
        if sum(s["by_year"]) != s["samples"] or sum(s["by_month"]) > s["samples"]:
            err.append(f"{s['name']}: years or months do not add up")
    if sim and (sim.get("verdict") != "fail" or not sim["verdict_words"].startswith("Failed")):
        err.append("the simulation's verdict is fail and must be said")
    if sim and {p["id"] for p in doc["policies"]} != set(sim["runs"][0]["strategies"]):
        err.append("policies and simulated strategies differ")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "check"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    if a.step == "export":
        doc = build()
        if problems := check(doc):
            raise SystemExit("\n".join(problems))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        print(f"wrote {a.out}: {doc['coverage']['samples']} samples at {len(doc['coverage']['sites'])} bathing waters")
    else:
        p = Path(a.path) if a.path else OUT
        problems = check(json.loads(p.read_text()))
        print("\n".join(problems) or f"{p}: holds the contract")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
