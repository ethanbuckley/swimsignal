"""How long overflows' spills lasted in 2024-25: a dated observation file for the site
(docs/SPILL-DURATIONS-CONTRACT-v1.md), from the Environment Agency's start/stop records. Offline:

    DIPCAST_ROOT=<checkout with data/processed/ea_events_*.parquet> \\
        uv run python scripts/export_spill_durations.py export [--out PATH]
    uv run python scripts/export_spill_durations.py check [PATH]

A spill is an overflow's events joined when they overlap or start less than an hour after the last ended, the rule of
the spill-duration test (scripts/spill_duration_test.py, merge_spells). This describes what monitors recorded. It is
not a forecast, says nothing of how much was discharged, and companies record events differently.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "data" / "research" / "spill_durations.v1.json"
SCHEMA, VERSION = "swimsignal.spill-durations", "1.1.0"
YEARS_LABEL = "2024-2025"
# 1.1: plain words the page can use
ABSENT_NOTE = ("An overflow not listed had no spill in the Environment Agency's 2024 and 2025 start/stop records, or "
               "has no record there. That is not the same as \"no spills\": check the annual return's own figure.")
YEARS = (2024, 2025)
GAP_H = 1.0
FEW = 5                          # fewer spills than this: the overflow's typical length is marked `few`
HORIZONS = (1, 3, 6, 12, 24)     # the company curves: still running this many hours later
ELAPSED = (0, 1, 3, 6, 12, 24)   # ... for spills that had run at least this long
CLAIM = {
    "public_wording": "How long this overflow's spills lasted in 2024 and 2025, from the water company's monitor "
                      "records published by the Environment Agency. A record of the past, not a forecast. It says "
                      "nothing of how much was discharged.",
    "not_claimed": ["a forecast of when a spill will end", "the volume or strength of a discharge",
                    "that a short spill was harmless", "that companies record events the same way"],
}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def at_least_words(h: int) -> str:
    return "any spill already running" if h == 0 else f"spills already running at least {h} hour{'s' if h != 1 else ''}"


def still_running(sp: pd.DataFrame) -> list[dict]:
    """Per company (and all nine): of the whole hours at which a spill had run at least e hours, the share still
    running h hours later. Issue hours are every whole UTC hour a spill runs, in the first 72 hours of each spill."""
    from spill_duration_test import issue_rows, labels
    rows = issue_rows(sp, pd.Timestamp(f"{YEARS[0]}-01-01", tz="UTC"), pd.Timestamp(f"{YEARS[-1]}-12-31", tz="UTC"))
    y = labels(rows)
    comp = sp["company"].to_numpy()[rows["spell"].to_numpy()]
    e = rows["elapsed_h"].to_numpy()
    out = []
    for c in [*sorted(set(comp)), "all nine"]:
        m = np.ones(len(rows), bool) if c == "all nine" else comp == c
        for lo in ELAPSED:
            k = m & (e >= lo)
            if k.sum() < 200:
                continue
            out.append({"company": c, "years": YEARS_LABEL, "running_at_least_h": lo, "label": at_least_words(lo),
                        "hours": int(k.sum()), "spills": int(rows.loc[k, "spell"].nunique()),
                        **{f"still_after_{h}h": round(float(y[k, j].mean()), 3) for j, h in enumerate(HORIZONS)}})
    return out


def build() -> dict:
    from spill_duration_test import merge_spells

    from dipcast import config
    from dipcast.model.training import NINE, events_path, load_events
    sources = {c: events_path(c) for c in NINE}
    before = {c: sha256(p) for c, p in sources.items()}
    ev = load_events(NINE)
    ev = ev[ev["event_start"].dt.year.isin(YEARS) & ev["site_id"].notna()]
    same_start_stop = int((ev["event_end"] == ev["event_start"]).sum())
    sp = merge_spells(ev, GAP_H)
    sp["hours"] = (sp["end"] - sp["start"]).dt.total_seconds() / 3600
    sp["year"] = sp["start"].dt.year
    # One column per field (the same order in every column), so 12,000 overflows stay small for a page.
    g = sp.groupby(["site_id", "company"])
    h = g["hours"]
    stats = pd.DataFrame({"median_h": h.median(), "p90_h": h.quantile(0.9), "longest_h": h.max(),
                          "share_over_6h": h.apply(lambda x: (x > 6).mean()), "n": h.size(),
                          **{f"spills_{y}": g["year"].apply(lambda x, y=y: int((x == y).sum())) for y in YEARS}})
    stats = stats.reset_index().sort_values("site_id").reset_index(drop=True)
    companies = sorted(stats["company"].unique())
    per = {"site_id": stats["site_id"].astype(str).tolist(),
           "company": stats["company"].map({c: i for i, c in enumerate(companies)}).astype(int).tolist(),
           **{f"spills_{y}": stats[f"spills_{y}"].astype(int).tolist() for y in YEARS},
           "median_h": stats["median_h"].round(2).tolist(), "p90_h": stats["p90_h"].round(2).tolist(),
           "longest_h": stats["longest_h"].round(2).tolist(), "share_over_6h": stats["share_over_6h"].round(3).tolist(),
           "few": (stats["n"] < FEW).tolist()}
    comp = []
    for c, g in sp.groupby("company"):
        h = g["hours"]
        comp.append({"company": c, "years": YEARS_LABEL, "overflows": int(g["site_id"].nunique()), "spills": int(len(g)),
                     "median_h": round(float(h.median()), 2), "p90_h": round(float(h.quantile(0.9)), 2),
                     "share_over_6h": round(float((h > 6).mean()), 3),
                     "share_over_24h": round(float((h > 24).mean()), 3)})
    after = {c: sha256(p) for c, p in sources.items()}
    if after != before:
        raise SystemExit("an input changed during the export")
    return {"schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "period": {"from": f"{YEARS[0]}-01-01", "to": f"{YEARS[-1]}-12-31"},
            "method": {"spill": "an overflow's monitor events joined when they overlap or start less than 1 hour "
                                "after the last ended", "gap_h": GAP_H, "few_below": FEW,
                       "zero_length_note": "A typical length shown as 0.0 hours means most of that overflow's spills "
                                           "lasted under 18 seconds as recorded, or were recorded with the same start "
                                           f"and stop time ({same_start_stop:,} such events in 2024-25, mostly at Wessex "
                                           "Water and South West Water). It does not mean nothing was discharged.",
                       "events_same_start_stop": same_start_stop,
                       "code_sha256": {f: sha256(ROOT / f) for f in ("scripts/export_spill_durations.py",
                                                                      "scripts/spill_duration_test.py")}},
            "sources": [{"company": c, "file": p.name, "sha256": h} for (c, p), h in
                        zip(sources.items(), before.values(), strict=True)],
            "attribution": ["Environment Agency, storm overflow EDM start/stop data 2024 and 2025, "
                            "Open Government Licence v3.0"],
            "claim": CLAIM, "absent_note": ABSENT_NOTE, "company": comp, "still_running": still_running(sp),
            "companies": companies, "overflows": per,
            "coverage": {"overflows": len(per["site_id"]), "spills": int(len(sp)), "overflows_few": int(sum(per["few"]))},
            "_root": str(config.ROOT)}


def check(doc: dict) -> list[str]:
    err = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    for k in ("generated_at", "period", "method", "sources", "attribution", "claim", "company", "still_running",
              "companies", "overflows", "coverage"):
        if k not in doc:
            err.append(f"missing {k}")
    if "not a forecast" not in doc.get("claim", {}).get("public_wording", ""):
        err.append("the claim must say it is not a forecast")
    ov = doc.get("overflows", {})
    ids = ov.get("site_id", [])
    if len(ids) != len(set(ids)):
        err.append("duplicate site_id")
    n = len(ids)
    if any(len(v) != n for v in ov.values()):
        err.append("overflow columns differ in length")
    for i in range(n):
        if not (0 <= ov["median_h"][i] <= ov["p90_h"][i] <= ov["longest_h"][i]):
            err.append(f"{ids[i]}: lengths out of order")
        if not 0 <= ov["share_over_6h"][i] <= 1:
            err.append(f"{ids[i]}: share out of range")
    if ov and max(ov.get("company", [0]), default=0) >= len(doc.get("companies", [])):
        err.append("a company index with no company")
    for r in doc.get("still_running", []):
        v = [r[f"still_after_{h}h"] for h in HORIZONS]
        if any(b > a + 1e-9 for a, b in zip(v, v[1:], strict=False)):
            err.append(f"{r['company']} {r['running_at_least_h']}: still-running shares rise with time")
    if doc.get("coverage", {}).get("overflows") != len(ids):
        err.append("coverage count does not match")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "check"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    if a.step == "export":
        doc = build()
        doc.pop("_root")
        problems = check(doc)
        if problems:
            raise SystemExit("\n".join(problems))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(json.dumps({"coverage": doc["coverage"], "company": doc["company"]}, indent=1))
        print(f"wrote {a.out} ({a.out.stat().st_size:,} bytes)")
    else:
        p = Path(a.path) if a.path else OUT
        problems = check(json.loads(p.read_text()))
        print("\n".join(problems) or f"{p}: holds the contract")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
