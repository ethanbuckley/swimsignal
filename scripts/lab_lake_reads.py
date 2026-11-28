"""Research Lab exhibit 8, "A lake the model has never seen": one file, prototypes/research-lab/lakes/reads.json, from
committed results only. Offline: it reads committed files and fetches nothing.

    uv run python scripts/lab_lake_reads.py          # write the file
    uv run python scripts/lab_lake_reads.py check    # the committed file against the results it was made from

Sources:
- docs/LAKE-RANGE-HINDCAST-TEST-2026-11-scores.json and -extra.json: #584, lake-range-v1 on 2012-22 at Windermere and
  Frensham (statement pushed before any join), and its supplementary refit with those lakes treated as unknown;
- docs/backtest-bench/results/lake_range_v1-20261115T200444Z.json: bench read 1, order at the 7 lakes with no level;
- docs/backtest-bench/results/lake_range_v1_ownlevel-20261128T142309Z.json: bench read 2, the range on own levels there;
- docs/lake-average-check/results.json: the average-lake check on seen rows (development; plan pushed first).

Every figure is copied as its source gives it. The bar (70% to 90% inside, every water body 60%) is #584's condition 1
and 3, which reads 2 and the average-lake check used.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORES = ROOT / "docs" / "LAKE-RANGE-HINDCAST-TEST-2026-11-scores.json"
EXTRA = ROOT / "docs" / "LAKE-RANGE-HINDCAST-TEST-2026-11-extra.json"
READ1 = ROOT / "docs" / "backtest-bench" / "results" / "lake_range_v1-20261115T200444Z.json"
READ2 = ROOT / "docs" / "backtest-bench" / "results" / "lake_range_v1_ownlevel-20261128T142309Z.json"
AVG = ROOT / "docs" / "lake-average-check" / "results.json"
SPOTS = ROOT / "spots.csv"
OUT = ROOT / "prototypes" / "research-lab" / "lakes" / "reads.json"
# The lake bathing waters the tests read: #584's five sites with their own level, and bench reads 1 and 2's seven.
OWN = ("ukd1203-45625", "ukd1203-45650", "ukd1203-45675", "ukd1203-45700", "ukj2310-11945")
NONE = ("ukf1400-09750", "uki1101-11910", "uki1101-11920", "uki1101-11930", "uki1106-11940", "ukk1100-36050", "ukk1302-11760")
BAR = {"inside": [0.70, 0.90], "each_water_body": 0.60, "claims": 0.80}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def make() -> dict:
    sc, ex = json.loads(SCORES.read_text()), json.loads(EXTRA.read_text())
    r1, r2, avg = (json.loads(p.read_text()) for p in (READ1, READ2, AVG))
    s1, s2 = r1["lake_not_read_before"], r2["lake_not_read_before"]
    c1, p1 = s1["scores"]["candidate"], s1["scores"]["production_deployed"]
    d1 = s1["differences"]["candidate-production_deployed"]["rho_site"]
    c2 = s2["scores"]["candidate"]
    own_known = {k: {"rows": sc["by_water"][k]["n"], "inside": sc["by_water"][k]["candidate"]["central80"]}
                 for k in sc["by_water"]}
    with SPOTS.open() as f:
        at = {r["id"]: r for r in csv.DictReader(f)}
    lakes = [{"id": b, "name": at[f"bw-{b}"]["name"], "lat": round(float(at[f"bw-{b}"]["lat"]), 4),
              "lon": round(float(at[f"bw-{b}"]["lon"]), 4), "had_level": b in OWN} for b in OWN + NONE]
    return {
        "schema": "swimsignal.lab-lake-reads", "version": "1.0.0",
        "last_read": r2["at"][:10],
        "sources": {str(p.relative_to(ROOT)): _sha(p) for p in (SCORES, EXTRA, READ1, READ2, AVG, SPOTS)},
        "lakes": lakes,
        "records": {"hindcast": "docs/LAKE-RANGE-HINDCAST-TEST-2026-11.md", "read1": "docs/BENCH-READ-LAKE-RANGE-2026-11.md",
                    "read2": "docs/BENCH-READ-LAKE-RANGE-COVERAGE-2026-11.md", "average": "docs/LAKE-AVERAGE-BASIS-CHECK-2026-11.md",
                    "site": ["docs/LAKE-ORDER-NO-OVERFLOW-2026-11.md", "docs/LAKE-RANGE-OWN-LEVELS-2026-11.md",
                             "docs/LAKE-ORDER-OVERFLOW-LAKES-2026-11.md"]},
        "bar": BAR,
        "known": {"rows": sc["rows"]["n"], "inside": sc["rows"]["candidate"]["central80"],
                  "below": sc["rows"]["candidate"]["below_range"], "above": sc["rows"]["candidate"]["above_range"],
                  "by_water": own_known, "rho_by_site": sc["within_site_rho_median"]["candidate"],
                  "rho_production_by_site": sc["within_site_rho_production"]},
        "known_as_unknown": {"inside": ex["unseen"]["candidate"]["central80"], "below": ex["unseen"]["candidate"]["below_range"],
                             "above": ex["unseen"]["candidate"]["above_range"], "by_water": ex["unseen"]["candidate"]["by_water"]},
        "order": {"rows": s1["rows"], "lakes": s1["sites"], "water_bodies": s1["clusters"], "read_at": r1["at"][:10],
                  "rho": {"value": c1["rho_site"]["value"], "ci95": c1["rho_site"]["ci95_season"]},
                  "rho_production": {"value": p1["rho_site"]["value"], "ci95": p1["rho_site"]["ci95_season"]},
                  "difference": {"value": d1["mean"], "ci95": d1["ci95_season"]}},
        "own_level": {"rows": s2["rows"], "read_at": r2["at"][:10],
                      "inside": {"value": c2["cover80"]["value"], "ci95": c2["cover80"]["ci95_season"]},
                      "below": c2["below80"]["value"], "above": c2["above80"]["value"],
                      "by_water": s2["cover80_by_water_body"]["candidate"]},
        "average_seen": {"note": "development: seen rows 2023-26, each lake treated as unknown",
                         "A": {"overall": avg["A_overall"], "by_water": avg["A"]},
                         "B": {"overall": avg["B_overall"], "by_water": avg["B"]},
                         "C": {"overall": avg["C_overall"], "by_site": avg["C"]}},
        "credit": "Environment Agency bathing water samples, Open Government Licence v3.0. Rain: Open-Meteo archive (CC BY 4.0).",
    }


def check(doc: dict) -> list[str]:
    want = make()
    return [k for k in want if doc.get(k) != want[k]]


if __name__ == "__main__":
    if sys.argv[1:] == ["check"]:
        bad = check(json.loads(OUT.read_text()))
        print("ok" if not bad else f"differs: {bad}")
        sys.exit(1 if bad else 0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(make(), indent=1) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size} bytes")
