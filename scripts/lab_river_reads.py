"""Research Lab exhibit 7, "What decides a river's bad days?": one file, prototypes/research-lab/rivers/reads.json, from
the two committed read results and the summer read's point list. Offline: it reads committed files and fetches nothing.

    uv run python scripts/lab_river_reads.py          # write the file
    uv run python scripts/lab_river_reads.py check    # the committed file against the results it was made from

Sources (each frozen-model backtest: the statement pushed before any result was joined, read once):
- docs/river-unseen/result.json: RIVER-UNSEEN, May to September 2012-22, read 16 Nov 2026
  (docs/RIVER-UNSEEN-PROTOCOL-2026-11.md);
- docs/river-winter/result.json: RIVER-WINTER, October to April of six even winters 2012-22, read 24 Nov 2026
  (docs/RIVER-WINTER-READ-2026-11.md);
- docs/river-unseen/points.csv: the sampling points, of which the 59 `kept_point` ones are the summer read's.

Every figure is copied as the result gives it, under the same name, so `check` can compare them one by one. Figures the
results mark as reported on rows already read stay labelled so here (`development`). The two bars come from the
statements, not the results: the order's bar 0.15 (both statements) and the summer range's 72% to 88%.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMER = ROOT / "docs" / "river-unseen" / "result.json"
WINTER = ROOT / "docs" / "river-winter" / "result.json"
POINTS = ROOT / "docs" / "river-unseen" / "points.csv"
OUT = ROOT / "prototypes" / "research-lab" / "rivers" / "reads.json"
BARS = {"order": 0.15, "summer_range": [0.72, 0.88]}   # RIVER-UNSEEN-PROTOCOL "Pass rule"; RIVER-WINTER-READ conditions 1-2
REGIONS = {"SouthWest": "South West", "Anglian": "East Anglia", "NorthWest": "North West", "Southern": "South", "Thames": "Thames"}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _clean(x):
    """Strict JSON: a subset with too few rows has NaN figures in the results; those are left out, not written as 0."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items() if not (isinstance(v, float) and math.isnan(v))}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    return x


def _ci(d: dict) -> dict:
    return {"value": d["value"], "ci95": d["ci95"]}


def make() -> dict:
    s, w = json.loads(SUMMER.read_text()), json.loads(WINTER.read_text())
    r, wr = s["reported"], w["reported"]
    sub = r["subsets"]
    summer = {
        "read_at": s["read_at"], "rows": s["rows"], "points": s["points"], "systems": s["systems"], "seasons": s["seasons"],
        "over_900": s["over_900"], "outcome": s["outcome"],
        "order": {"candidate": _ci(s["primary_rho"]), "pass": s["primary_pass"],
                  "production_deployed": r["rho_by_figure"]["production_deployed"],
                  "production_refit": r["rho_by_figure"]["production_refit"],
                  "rain_48h": r["rho_by_figure"]["lrain48"]},
        "range": {"inside": s["range_coverage"], "pass": s["range_pass"]},
        "brier_over_900": r["brier_over_900"],
        "bands": {k: sub[f"band_{k}"] for k in ("large", "medium", "small")},
        "purposes": {k[len("purpose_"):]: v for k, v in sub.items() if k.startswith("purpose_") and v["rows"] >= 100},
        # reported in the winter result on these rows, already read on 16 Nov: development, not part of either read
        "development": {"exposure_alone": wr["summer_rows_already_read"]["all_59_points"]["exposure"]["raw"],
                        "level": wr["summer_rows_already_read"]["all_59_points"]["level"]},
    }
    winter = {
        "read_at": w["read_at"], "rows": w["rows"], "points": w["points"], "points_15_or_more": w["points_15_or_more"],
        "systems": w["systems"], "winters": w["winters"], "over_900": w["over_900"],
        "order": {"production": _ci(w["condition_1_raw"]), "pass": w["condition_1_pass"],
                  "month_removed": {"production": _ci(w["condition_2_month_removed"]), "pass": w["condition_2_pass"],
                                    "rain": _ci(wr["rain_month_removed"]), "exposure": _ci(wr["exposure_month_removed"]),
                                    "production_minus_rain": _ci(wr["production_minus_rain_month_removed"])}},
        "level": wr["level"],
        "seasons_of_winter": {k: wr["subsets"][k] for k in ("oct_nov", "dec_feb", "mar_apr")},
        "no_overflow": {"rows": wr["no_overflow"]["rows"], "points_15_or_more": wr["no_overflow"]["points_15_or_more"],
                        "level": wr["no_overflow"]["level"],
                        "rain_month_removed": _ci(wr["no_overflow"]["rain_month_removed"]),
                        "production_month_removed": _ci(wr["no_overflow"]["production_month_removed"])},
    }
    with POINTS.open() as f:
        pts = [{"id": p["point"], "name": p["label"].title(), "water": p["watercourse"], "lat": float(p["lat"]), "lon": float(p["lon"]),
                "region": REGIONS.get(p["region"], p["region"]), "rows": int(p["kept_held_out"]),
                "overflows_upstream": int(float(p["overflows_upstream"] or 0))}
               for p in csv.DictReader(f) if p["kept_point"] == "True"]
    pts.sort(key=lambda p: p["id"])
    return _clean({
        "schema": "swimsignal.lab-river-reads", "version": "1.0.0",
        "last_read": max(s["read_at"], w["read_at"]),   # the "Data as of" date (build_site.write_lab_refresh)
        "sources": {str(p.relative_to(ROOT)): _sha(p) for p in (SUMMER, WINTER, POINTS)},
        "records": {"summer": "docs/RIVER-UNSEEN-PROTOCOL-2026-11.md", "winter": "docs/RIVER-WINTER-READ-2026-11.md"},
        "bars": BARS, "summer": summer, "winter": winter, "points": pts,
        "credit": "Environment Agency Water Quality Archive, Open Government Licence v3.0. Rain: ERA5-Land (Copernicus Climate Change Service).",
    })


def check(doc: dict) -> list[str]:
    """Differences between a reads file and what make() gives from the committed results now."""
    want = make()
    return [k for k in want if doc.get(k) != want[k]]


if __name__ == "__main__":
    if sys.argv[1:] == ["check"]:
        bad = check(json.loads(OUT.read_text()))
        print("ok" if not bad else f"differs: {bad}")
        sys.exit(1 if bad else 0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = make()
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {len(doc['points'])} points, {OUT.stat().st_size} bytes")
