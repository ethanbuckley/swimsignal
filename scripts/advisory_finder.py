"""Advisory finder, dry run only: drafts of official advice against swimming, for a person to review.

    uv run python scripts/advisory_finder.py --dry-run --fixtures tests/fixtures/advisories
    uv run python scripts/advisory_finder.py --dry-run            # live: one request per whitelisted source

Writes a JSON file of drafts (default data/cache/advisory_drafts.json, which git ignores) and prints a
short review table. There is no publish path: no draft is approved, nothing reaches the site build,
and nothing is sent. Without --dry-run it refuses to run. docs/ADVISORY-FINDER-2026-10.md has the rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dipcast import config
from dipcast.advisories import BY_KEY, TZ, run, table


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="required: the finder only ever drafts")
    ap.add_argument("--fixtures", type=Path, help="read saved answers (DIR/manifest.json) instead of the network")
    ap.add_argument("--out", type=Path, default=config.CACHE / "advisory_drafts.json", help="where the drafts go")
    ap.add_argument("--previous", type=Path, help="an earlier drafts file, to mark updates and withdrawals")
    ap.add_argument("--now", help="the run's time, ISO 8601 (default: now), for stale checks on fixtures")
    ap.add_argument("--source", action="append", choices=sorted(BY_KEY) + ["ea-history"],
                    help="read only this source (repeatable)")
    args = ap.parse_args(argv)
    if not args.dry_run:
        ap.error("--dry-run is required: this prototype has no other mode")
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    previous = None
    if args.previous:
        body = json.loads(args.previous.read_text(encoding="utf-8"))
        previous = body.get("drafts") if isinstance(body, dict) else None
    result = run(fixtures=args.fixtures, now=now, previous=previous,
                 keys=tuple(args.source) if args.source else None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(table(result))
    print(f"Drafts written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
