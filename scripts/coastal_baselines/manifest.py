"""Copy the small coastal tables into data/research/coastal/ and write their manifest
(docs/COASTAL-BASELINES-2026-11.md, section 1).

    uv run python scripts/coastal_baselines/manifest.py <fetch dir> <out dir> <code commit>

<fetch dir> is fetch.py's output and <out dir> is run.sh's. Committed: the ledger, sites.csv, site_year.csv,
year_summary.csv, samples.parquet (Environment Agency data only), scores.json and scores.md. Not committed, hashed
here: the raw responses, features.parquet (it carries radar rain, which is Met Office data under CC BY-SA 4.0) and
the held-out predictions. Every raw response is hashed again and checked against the ledger's hash for it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DEST = REPO / "data" / "research" / "coastal"
COMMITTED = ("sites.csv", "site_year.csv", "year_summary.csv", "samples.parquet", "scores.json", "scores.md")
KEPT_OUT = ("features.parquet", "predictions_over_500.parquet", "predictions_over_250.parquet")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(path: Path) -> int | None:
    if path.suffix == ".parquet":
        return len(pd.read_parquet(path))
    if path.suffix in (".csv", ".jsonl"):
        return sum(1 for _ in open(path)) - (1 if path.suffix == ".csv" else 0)
    return None


def described(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": sha256(path), "rows": rows(path)}


def main(fetch: Path, out: Path, commit: str) -> None:
    ledger = [json.loads(line) for line in (fetch / "ledger.jsonl").read_text().splitlines()]
    answered = {r["key"]: r["sha256"] for r in ledger if r.get("status") == 200}
    raw = sorted((fetch / "raw").glob("*.json"))
    mismatched = [f.stem for f in raw if answered.get(f.stem) != sha256(f)]
    listing = "".join(f"{f.stem} {answered.get(f.stem)}\n" for f in raw)
    services = {}
    for s in sorted({r["service"] for r in ledger}):
        mine = [r for r in ledger if r["service"] == s]
        services[s] = {"requests_sent": len(mine), "by_stage": dict(Counter(r["stage"] for r in mine)),
                       "by_status": {str(k): v for k, v in Counter(r.get("status") or r.get("error") for r in mine).items()},
                       "refusals": [r["key"] for r in mine if r.get("refusal")],
                       "first_request": mine[0]["at"], "last_request": mine[-1]["at"],
                       "bytes_received": sum(r.get("bytes", 0) for r in mine)}
    DEST.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fetch / "ledger.jsonl", DEST / "fetch_ledger.jsonl")
    for name in COMMITTED:
        shutil.copyfile(out / name, DEST / name)
    before, after = (out / "fingerprint_before.txt").read_text(), (out / "fingerprint_after.txt").read_text()
    summary = json.loads((out / "build_summary.json").read_text())
    manifest = {
        "schema": "swimsignal.coastal-baselines-manifest", "version": "1.0",
        "record": "docs/COASTAL-BASELINES-2026-11.md", "code_commit": commit,
        "licence": {"samples_and_predictions": "Environment Agency, Open Government Licence v3.0",
                    "spill_records": "Environment Agency EDM detailed data, Open Government Licence",
                    "rain": "Contains Met Office data, British Crown copyright, CC BY-SA 4.0 (UK Radar Observations, AWS "
                            "Open Data). Per-sample rain is not committed; the explorer's after-rain shares are derived "
                            "from it."},
        "fetch": {"services": services, "caps": json.loads((fetch / "fetch_summary.json").read_text())["caps"],
                  "stopped": json.loads((fetch / "fetch_summary.json").read_text())["stopped"],
                  "raw_responses": {"files": len(raw), "bytes": sum(f.stat().st_size for f in raw),
                                    "sha256_of_listing": hashlib.sha256(listing.encode()).hexdigest(),
                                    "listing": "one line per response, '<key> <sha256 of body>', sorted by key",
                                    "files_not_matching_the_ledger": mismatched, "committed": False}},
        "committed": {"fetch_ledger.jsonl": described(DEST / "fetch_ledger.jsonl"),
                      **{name: described(DEST / name) for name in COMMITTED}},
        "not_committed": {name: described(out / name) for name in KEPT_OUT},
        "shared_inputs": {"read_only": True, "unchanged_by_the_build": before == after,
                          "fingerprints": [dict(zip(("file", "bytes", "sha256"), line.split())) if not line.startswith("radar_")
                                           else {"folder": line} for line in before.splitlines()]},
        "counts": {k: summary[k] for k in ("sites", "sites_by_kind", "sites_with_archive_point", "sites_with_samples",
                                           "samples", "observations", "overflows", "rain", "spills", "predictions", "rule")},
    }
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps({"files": len(raw), "mismatched": len(mismatched), "services": {k: v["requests_sent"] for k, v in services.items()}}))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3])
