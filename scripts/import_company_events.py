"""Write one parquet of discharges per company, data/processed/company_events_<company>.parquet (the edm_events
columns), from the companies' own 2025-26 event layers (ingest/company_events.LAYERS), and a manifest of what was
read: per layer the item, licence credit, raw-read hash, rows, date repairs and dropped rows; a company-by-month
coverage table beside the EA start/stop files' own; and the EA year zips found in data/raw/ea_events/, with hashes.
The record is docs/EVENT-RECORDS-2026-11.md. Off CI, run by hand:

    uv run python scripts/import_company_events.py [--refresh] [--max-requests 450] \
        [--manifest docs/EVENT-RECORDS-2026-11-manifest.json] [--coverage docs/EVENT-RECORDS-2026-11-coverage.csv]

A layer already in the raw cache (data/cache/company_events/) is not read again unless --refresh. Every request goes
to data/cache/company_events/ledger.jsonl; the fetch stops at the first refusal or at --max-requests.

Nothing here trains or scores a model, and nothing is written to edm_events.parquet or the EA event files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

from dipcast import config
from dipcast.ingest.common import write_parquet
from dipcast.ingest.company_events import LAYERS, RAW_CACHE, Ledger, Refused, coverage, fetch_layer, normalise, raw_path
from dipcast.ingest.edm_events import ea_zip_year

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("import_company_events")


def slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ea_zips() -> list[dict]:
    """Each EA yearly start/stop zip held in data/raw/ea_events/: bytes, hash, and its members' hashes."""
    out = []
    for p in sorted((config.RAW / "ea_events").glob("*.zip")):
        if ea_zip_year(p.name) is None:
            continue
        with zipfile.ZipFile(p) as zf:
            members = [{"name": i.filename, "bytes": i.file_size,
                        "sha256": hashlib.sha256(zf.read(i.filename)).hexdigest()}
                       for i in zf.infolist() if not i.is_dir()]
        out.append({"file": p.name, "year": ea_zip_year(p.name), "bytes": p.stat().st_size, "sha256": sha256(p),
                    "members": members})
    return out


def ea_coverage() -> pd.DataFrame:
    """Company by month of the EA event parquets in data/processed, for the same table."""
    frames = []
    for p in sorted(config.PROCESSED.glob("ea_events_*.parquet")):
        ev = pd.read_parquet(p, columns=["site_id", "event_start"])
        company = p.stem.removeprefix("ea_events_").replace("_", " ").title()
        frames.append(coverage(ev.assign(company=company)))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def ledger_summary(path: Path) -> dict | None:
    """Requests, statuses, bytes and first and last time in the fetch ledger, if there is one."""
    if not path.exists():
        return None
    r = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {"requests": len(r), "statuses": sorted({x["status"] for x in r}),
            "bytes": sum(x["bytes"] for x in r), "first": r[0]["utc"], "last": r[-1]["utc"]} if r else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true", help="read the layers again instead of the raw cache")
    ap.add_argument("--max-requests", type=int, default=450)
    ap.add_argument("--manifest", type=Path, default=config.PROCESSED / "company_events_manifest.json")
    ap.add_argument("--coverage", type=Path, default=config.PROCESSED / "company_events_coverage.csv")
    args = ap.parse_args()
    ledger = Ledger(RAW_CACHE / "ledger.jsonl", cap=args.max_requests)
    layers, by_company = [], {}
    for source, lay in LAYERS.items():
        try:
            raw = fetch_layer(source, ledger, refresh=args.refresh)
        except Refused as e:
            sys.exit(f"stopped at {source}: {e} ({ledger.sent} requests sent)")
        ev, notes = normalise(raw, source)
        by_company.setdefault(lay["company"], []).append(ev)
        first, last = ev["event_start"].min(), ev["event_start"].max()
        layers.append({"source": source, "company": lay["company"], "item": lay["item"], "url": lay["url"],
                       "credit": lay["credit"], "stated_months": list(lay["months"]),
                       "raw_cache": raw_path(source).name, "raw_sha256": sha256(raw_path(source)),
                       "first_start": first.isoformat(), "last_start": last.isoformat(),
                       "overflows": int(ev["site_id"].nunique()), **notes})
        log.info("%s: %s", source, notes)
    cov, outputs = [], []
    for company, frames in by_company.items():
        ev = pd.concat(frames, ignore_index=True).sort_values(["site_id", "event_start"]).reset_index(drop=True)
        out = config.PROCESSED / f"company_events_{slug(company)}.parquet"
        write_parquet(ev, out)
        outputs.append({"file": out.name, "company": company, "events": len(ev), "sha256": sha256(out)})
        cov.append(coverage(ev.assign(company=company)).assign(record="company layer"))
    ea = ea_coverage()
    if len(ea):
        cov.append(ea.assign(record="EA start/stop file"))
    table = pd.concat(cov, ignore_index=True)[["record", "company", "month", "events", "overflows"]]
    table = table.sort_values(["record", "company", "month"]).reset_index(drop=True)
    args.coverage.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.coverage, index=False)
    manifest = {"layers": layers, "outputs": outputs, "ea_zips": ea_zips(),
                "ledger": ledger_summary(ledger.path), "requests_this_run": ledger.sent,
                "coverage_csv": args.coverage.name}
    args.manifest.write_text(json.dumps(manifest, indent=1) + "\n")
    pd.set_option("display.width", 200)
    print(pd.DataFrame(layers)[["source", "rows", "kept", "swapped_start", "swapped_end", "repeated",
                                "start_outside_stated_months", "first_start", "last_start"]].to_string(index=False))


if __name__ == "__main__":
    main()
