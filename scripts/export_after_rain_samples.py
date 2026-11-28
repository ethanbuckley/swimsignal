"""Past samples after rain (docs/AFTER-RAIN-SAMPLES-2026-11.md): at each inland bathing water, its own 2023-26
Environment Agency samples split by the rain in the 48 hours before each one, more than 10 mm or not, with how many
and the middle result of each group. Past samples, never a forecast. Off CI, by hand, offline:

    uv run python scripts/export_after_rain_samples.py [<seen.parquet>]

The samples are data/research/ecoli_evidence.v1.json's (EA, OGL v3), the ones the past-samples tile already gives.
The rain at each sample is the backtest bench's frozen seen rows (`rain_48h`: Open-Meteo's archive at the bathing
water's 0.1-degree cell, the 48 hours before the sample, as validate_ecoli.py's rain windows build it; #700's
scripts/backtest_bench/stage.py). The rows file is checked against SEEN_SHA256 before it is read. The output holds
counts and EA results only, no rain value, as BENCH-ECOLI900 keeps Open-Meteo values out of published files.

10 mm in 48 hours is the line of the Accuracy page's rain rule (docs/SIMPLE-REFERENCES-LIVE-2026-11.md), fixed
before this export; MIN_GROUP was fixed with it.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dipcast.typical import middle  # noqa: E402

EVIDENCE = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
DEST = ROOT / "data" / "research" / "after_rain_samples.v1.json"
SEEN_SHA256 = "417648aa938c7bb74e8eb85e8128a4227499a24474330f704f05ca14e3a91e13"   # bench ecoli-v1 seen.parquet
RAIN_MM = 10.0     # more than this in the 48 hours before a sample is "after rain"
MIN_GROUP = 5      # both groups need this many samples, or the site gets no entry
SCHEMA, VERSION = "swimsignal.after-rain-samples", "1.0.0"


def _minute(t) -> str:
    return pd.Timestamp(t).tz_convert(UTC).strftime("%Y-%m-%dT%H:%M")


def split(samples: list[dict], rain: dict[str, float]) -> dict | None:
    """One site's samples (evidence-file form) and the 48-hour rain by UTC minute: the two groups' counts and middle
    results, and how many samples had no rain figure. None when either group has fewer than MIN_GROUP."""
    wet, dry, none = [], [], 0
    for x in samples:
        r = rain.get(_minute(x["t"]))
        if r is None or r != r:
            none += 1
        else:
            (wet if r > RAIN_MM else dry).append(x)
    if len(wet) < MIN_GROUP or len(dry) < MIN_GROUP:
        return None
    years = sorted({x["t"][:4] for x in wet + dry})
    return {"after_rain": middle(wet), "after_less": middle(dry), "without_rain_figure": none,
            "first_year": int(years[0]), "last_year": int(years[-1])}


def build(evidence: dict, seen: pd.DataFrame) -> dict:
    seen = seen.assign(minute=seen["sample_time"].map(_minute))
    by_site = {b: dict(zip(g["minute"], g["rain_48h"].astype(float), strict=True)) for b, g in seen.groupby("bw_id")}
    sites, skipped = {}, []
    for s in evidence["sites"]:
        got = split(s["samples"], by_site.get(s["bw_id"], {}))
        if got is None:
            skipped.append(s["spot_id"])
        else:
            sites[s["spot_id"]] = {"bw_id": s["bw_id"], "name": s["name"], "kind": s["kind"], **got}
    return {"schema": SCHEMA, "version": VERSION, "line_mm": RAIN_MM, "min_group": MIN_GROUP,
            "record": "docs/AFTER-RAIN-SAMPLES-2026-11.md",
            "samples_from": "data/research/ecoli_evidence.v1.json (Environment Agency, OGL v3)",
            "rain_from": {"what": "Open-Meteo archive rain at the bathing water's 0.1-degree cell, the 48 hours before "
                                  "each sample; no rain value is in this file",
                          "rows": "backtest bench ecoli-v1 seen.parquet", "rows_sha256": SEEN_SHA256},
            "sites": sites, "too_few_after_rain": sorted(skipped)}


def main() -> None:
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        ROOT.parent / "swimsignal-private" / "bench" / "ecoli-v1" / "seen.parquet")
    if not p.exists():   # a worktree: the private folder sits beside the main checkout
        p = Path.home() / "Documents" / "GitHub" / "swimsignal-private" / "bench" / "ecoli-v1" / "seen.parquet"
    if hashlib.sha256(p.read_bytes()).hexdigest() != SEEN_SHA256:
        raise SystemExit(f"{p} is not the bench's frozen seen rows")
    doc = build(json.loads(EVIDENCE.read_text()), pd.read_parquet(p))
    doc["written"] = datetime.now(UTC).strftime("%Y-%m-%d")
    DEST.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(doc['sites'])} sites written; {len(doc['too_few_after_rain'])} with too few samples in a group")
    for k, v in doc["sites"].items():
        print(f"  {v['name']}: after rain {v['after_rain']}, after less {v['after_less']}, "
              f"no rain figure {v['without_rain_figure']}")


if __name__ == "__main__":
    main()
