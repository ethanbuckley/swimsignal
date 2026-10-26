"""Advisory finder, dry run only: drafts of official advice against swimming, for a person to review.

    uv run python scripts/advisory_finder.py --dry-run --fixtures tests/fixtures/advisories
    uv run python scripts/advisory_finder.py --dry-run --previous data/cache/advisory_drafts.json
    uv run python scripts/advisory_finder.py --dry-run --ea-history     # + 38 EA histories, once a day

Runs by hand on Ethan's Mac, weekly in season: not in GitHub Actions and not in the site build (the
EA's bathing-water service refuses GitHub's runners). Writes a JSON file of drafts (default
data/cache/advisory_drafts.json, which git ignores) and prints a short review table. It reads
approvals from data/advisories/approved.json (Ethan's, changed only by pull request) and never writes
them. There is no publish path: nothing reaches the site build and nothing is sent. Without --dry-run
it refuses to run. docs/ADVISORY-FINDER-2026-10.md has the rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dipcast import config
from dipcast.advisories import APPROVALS_FILE, BY_KEY, HISTORY_STAMP, TZ, ApprovalError, run, table


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="required: the finder only ever drafts")
    ap.add_argument("--fixtures", type=Path, help="read saved answers (DIR/manifest.json) instead of the network")
    ap.add_argument("--out", type=Path, default=config.CACHE / "advisory_drafts.json", help="where the drafts go")
    ap.add_argument("--previous", type=Path, help="an earlier drafts file, to mark updates, withdrawals and "
                                                  "drafts from a feed that could not be read (unverified)")
    ap.add_argument("--approvals", type=Path, default=APPROVALS_FILE, help="Ethan's approvals file (read only)")
    ap.add_argument("--now", help="the run's time, ISO 8601 (default: now), for stale checks on fixtures")
    ap.add_argument("--source", action="append", choices=sorted(BY_KEY) + ["ea-history"],
                    help="read only this source (repeatable)")
    ap.add_argument("--ea-history", action="store_true",
                    help="live only: also read each inland bathing water's EA incident history (38 requests, "
                         f"one at a time), at most once a day ({HISTORY_STAMP.name} in the cache)")
    args = ap.parse_args(argv)
    if not args.dry_run:
        ap.error("--dry-run is required: this prototype has no other mode")
    if args.ea_history and (args.fixtures or args.now):
        ap.error("--ea-history is live only, with the real clock: not with --fixtures or --now")
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    previous = None
    if args.previous:
        body = json.loads(args.previous.read_text(encoding="utf-8"))
        previous = body.get("drafts") if isinstance(body, dict) else None
    try:
        result = run(fixtures=args.fixtures, now=now, previous=previous,
                     keys=tuple(args.source) if args.source else None, approvals=args.approvals,
                     ea_history=args.ea_history)
    except ApprovalError as err:
        print(f"Approvals refused, nothing written: {err}. Fix the file by pull request.", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(table(result))
    print(f"Drafts written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
