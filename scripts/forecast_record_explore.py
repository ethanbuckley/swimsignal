"""How good are the forecasts? A bounded exploratory comparison for Research Lab exhibit 3.

Exploratory, on outcomes already read (docs/FORECAST-RECORD-EXPLORATION-2026-11.md). It reads only committed files that
end by 30 September 2026, before any active evaluation window (the earliest opened 18 October 2026), fetches nothing
and imports no dipcast code:

- data/research/ecoli_evidence.v1.json      EA samples beside hindsight estimates (docs/ECOLI-EVIDENCE-CONTRACT-v1.md)
- data/processed/verification_2025.csv, verification_leads_2025.csv, reliability_2025.csv   the 2025 spill hold-out
- data/processed/prf_comparison.json        SwimSignal beside the EA's daily risk prediction, Sep 2026

    uv run python scripts/forecast_record_explore.py [--out PATH]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "data/research/ecoli_evidence.v1.json"
HOLD = ROOT / "data/processed/verification_2025.csv"
LEADS = ROOT / "data/processed/verification_leads_2025.csv"
REL = ROOT / "data/processed/reliability_2025.csv"
PRF = ROOT / "data/processed/prf_comparison.json"
OUT = ROOT / "prototypes/research-lab/forecasts/exploration.json"

SEED = 20261102          # fixed before any figure below was computed
DRAWS = 2000
WARN = 0.25              # the site's river warning line (ecoli_evidence warn_at)
LAST_DAYS = 30           # "last sample" baseline: the previous sample at the site within this many days
CUTOFF = "2026-09-30"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open() as f:
        return [{k: (float(v) if k != "model" and k != "source" else v) for k, v in r.items()} for r in csv.DictReader(f)]


def auc(p, y) -> float:
    p, y = np.asarray(p, float), np.asarray(y, bool)
    if y.all() or not y.any():
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    r = np.empty(len(p))
    r[order] = np.arange(1, len(p) + 1)
    for v in np.unique(p):          # average ties
        m = p == v
        r[m] = r[m].mean()
    n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def counts(rows, key):
    c = {"hits": 0, "misses": 0, "false_alarms": 0, "quiet_correct": 0}
    for r in rows:
        w = r[key] >= WARN
        c["hits" if w and r["y"] else "misses" if r["y"] else "false_alarms" if w else "quiet_correct"] += 1
    return c


def rows_from_evidence(ev: dict) -> tuple[list[dict], dict]:
    """Every sample with a hindsight estimate, plus the 'last sample' and leave-one-year-out reference forecasts."""
    all_by_site, out = {}, []
    for s in ev["sites"]:
        smp = sorted((x for x in s["samples"] if x["t"][:10] <= CUTOFF), key=lambda x: x["t"])
        all_by_site[s["bw_id"]] = smp
        prev = None
        for x in smp:
            if x["hindsight"] is not None:
                gap = None if prev is None else (np.datetime64(x["t"][:10]) - np.datetime64(prev["t"][:10])).astype(int)
                out.append({"bw_id": s["bw_id"], "name": s["name"], "kind": s["kind"], "t": x["t"], "year": x["t"][:4],
                            "ecoli": x["ecoli"], "y": bool(x["over"]), "model": float(x["hindsight"]),
                            "last_over": None if gap is None or gap > LAST_DAYS else bool(prev["over"])})
            prev = x
    # Leave-one-year-out references, from every sample of the other years (not only hindsight rows)
    years = sorted({r["year"] for r in out})
    pooled = [(s["kind"], x["t"][:4], bool(x["over"]), s["bw_id"]) for s in ev["sites"] for x in s["samples"]
              if x["t"][:10] <= CUTOFF]
    kind_rate, site_rate = {}, {}
    for yr in years:
        other = [p for p in pooled if p[1] != yr]
        for k in ("river", "lake"):
            v = [p[2] for p in other if p[0] == k]
            kind_rate[(k, yr)] = float(np.mean(v))
        by = defaultdict(list)
        for p in other:
            by[p[3]].append(p[2])
        for b, v in by.items():
            site_rate[(b, yr)] = float(np.mean(v)) if len(v) >= 5 else None
    # "last sample" as a probability: the other years' over-900 rate after an over / after a not-over, by kind
    trans = {}
    for yr in years:
        for k in ("river", "lake"):
            for prev_over in (True, False):
                v = [r["y"] for r in out if r["year"] != yr and r["kind"] == k and r["last_over"] is prev_over]
                trans[(k, yr, prev_over)] = float(np.mean(v)) if v else kind_rate[(k, yr)]
    for r in out:
        r["usual"] = kind_rate[(r["kind"], r["year"])]
        r["site_usual"] = site_rate.get((r["bw_id"], r["year"])) or r["usual"]
        r["last"] = r["usual"] if r["last_over"] is None else trans[(r["kind"], r["year"], r["last_over"])]
    return out, {"years": years}


def brier(rows, key):
    return float(np.mean([(r[key] - r["y"]) ** 2 for r in rows]))


def boot_diff(rows, a, b, rng):
    """95% interval of Brier(a) - Brier(b), resampling bathing waters."""
    by = defaultdict(list)
    for r in rows:
        by[r["bw_id"]].append(r)
    keys, vals = list(by), []
    for _ in range(DRAWS):
        pick = [r for i in rng.integers(0, len(keys), len(keys)) for r in by[keys[i]]]
        vals.append(brier(pick, a) - brier(pick, b))
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)]


def summarise(rows, rng):
    refs = ("model", "usual", "site_usual", "last")
    out = {"samples": len(rows), "sites": len({r["bw_id"] for r in rows}), "over_900": sum(r["y"] for r in rows)}
    out["brier"] = {k: round(brier(rows, k), 4) for k in refs}
    out["auc"] = {k: round(auc([r[k] for r in rows], [r["y"] for r in rows]), 3) for k in refs}
    out["skill_vs_usual"] = round(1 - out["brier"]["model"] / out["brier"]["usual"], 3)
    out["model_minus"] = {k: {"diff": round(out["brier"]["model"] - out["brier"][k], 4), "ci": boot_diff(rows, "model", k, rng)}
                          for k in ("usual", "site_usual", "last")}
    out["at_line"] = {"model": counts(rows, "model"), "last": counts(rows, "last")}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    inputs = (EVID, HOLD, LEADS, REL, PRF)
    before = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    rng = np.random.default_rng(SEED)

    ev = json.loads(EVID.read_text())
    rows, meta = rows_from_evidence(ev)
    ecoli = {"all": summarise(rows, rng)}
    for k in ("river", "lake"):
        ecoli[k] = summarise([r for r in rows if r["kind"] == k], rng)
    ecoli["by_year"] = {y: summarise([r for r in rows if r["year"] == y], rng) for y in meta["years"]}
    sites = {}
    for r in rows:
        s = sites.setdefault(r["bw_id"], {"name": r["name"], "kind": r["kind"], "samples": 0, "over_900": 0,
                                          "misses": 0, "false_alarms": 0, "hits": 0})
        s["samples"] += 1
        s["over_900"] += r["y"]
        w = r["model"] >= WARN
        s["hits"] += w and r["y"]
        s["misses"] += (not w) and r["y"]
        s["false_alarms"] += w and not r["y"]
    # where the misses sat on the estimate scale: how far below the line
    miss_est = sorted(r["model"] for r in rows if r["y"] and r["model"] < WARN and r["kind"] == "river")

    hold = read_csv(HOLD)
    leads = read_csv(LEADS)
    rel = read_csv(REL)
    prf = json.loads(PRF.read_text())

    result = {
        "schema": "swimsignal.forecast-record-exploration",
        "version": "0.1.0",
        "status": "exploratory, on outcomes already read; nothing from an active evaluation window",
        "cutoff": CUTOFF, "seed": SEED, "draws": DRAWS, "warn_at": WARN, "last_sample_days": LAST_DAYS,
        "inputs_sha256": before,
        "ecoli": {
            **ecoli,
            "sites": sites,
            "miss_estimates": {"kind": "river", "n": len(miss_est), "median": round(float(np.median(miss_est)), 3),
                               "under_0_1": sum(1 for v in miss_est if v < 0.1)},
            "references": {
                "usual": "the over-900 rate for rivers or lakes in the other years",
                "site_usual": "this bathing water's over-900 rate in the other years (5 samples or more, else 'usual')",
                "last": "from the previous sample here within 30 days: the other years' over-900 rate after an over, "
                        "or after a not-over; 'usual' when there is none",
            },
            "note": "Hindsight estimates: the production model's form refitted leaving out each year, with archived "
                    "lead-0 forecast rain (docs/CONCENTRATION-STUDY-2026-11.md). Not what the site issued on the day.",
            "samples": [{k: r[k] for k in ("bw_id", "t", "ecoli", "y", "model", "usual", "site_usual", "last")}
                        for r in rows],
        },
        "spill_2025": {
            "holdout": hold, "leads": leads, "reliability": rel,
            "note": "United Utilities overflows, trained 2023-24 and tested on 2025 (overflow-days). The site's model "
                    "was refit on 2023-25 after this test. Other companies are not in this test.",
        },
        "ea_comparison": {k: prf[k] for k in ("season", "rules", "season_samples", "both", "both_rivers", "verdict", "credit")},
    }
    after = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    assert before == after, "an input changed during the run"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, default=float) + "\n")
    show = {k: v for k, v in ecoli.items() if k != "by_year"}
    show["by_year"] = {y: {"brier": v["brier"], "samples": v["samples"], "over": v["over_900"]} for y, v in ecoli["by_year"].items()}
    show["miss_estimates"] = result["ecoli"]["miss_estimates"]
    print(json.dumps(show, indent=1))


if __name__ == "__main__":
    main()
