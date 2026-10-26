"""Advisory finder, dry run only: drafts of official advice against swimming, for a person to review.

    uv run python scripts/advisory_finder.py --dry-run --fixtures tests/fixtures/advisories
    uv run python scripts/advisory_finder.py --dry-run --previous data/cache/advisory_drafts.json
    uv run python scripts/advisory_finder.py --dry-run --ea-history     # + 38 EA histories, once a day

Runs by hand on Ethan's Mac, weekly in season: not in GitHub Actions and not in the site build (the
EA's bathing-water service refuses GitHub's runners). Writes a JSON file of drafts (default
data/cache/advisory_drafts.json, which git ignores) and prints a short review table. It reads
approvals from data/advisories/approved.json (Ethan's, changed only by pull request) and never writes
them. A live run also writes data/advisories/last_check.json (each draft's status and when its source
last confirmed it, no evidence text); committed by pull request, that file is what the site build
reads for "last checked". The drafts themselves never reach the build, and nothing is sent. Without
--dry-run it refuses to run. docs/ADVISORY-FINDER-2026-10.md has the rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from advisories import APPROVALS_FILE, BY_KEY, HISTORY_STAMP, TZ, ApprovalError, review_entry, run, table  # scripts/advisories.py
from dipcast import config
from dipcast.official_advice import CHECK_FILE, check_record, load_check


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="required: the finder only ever drafts")
    ap.add_argument("--fixtures", type=Path, help="read saved answers (DIR/manifest.json) instead of the network")
    ap.add_argument("--out", type=Path, help="where the drafts go (default: advisory_drafts.json in the cache, "
                                             "or advisory_drafts_fixtures.json with --fixtures)")
    ap.add_argument("--previous", type=Path, help="an earlier drafts file, to mark updates, withdrawals and "
                                                  "drafts from a feed that could not be read (unverified)")
    ap.add_argument("--approvals", type=Path, default=APPROVALS_FILE, help="Ethan's approvals file (read only)")
    ap.add_argument("--now", help="the run's time, ISO 8601 (default: now), for stale checks on fixtures")
    ap.add_argument("--source", action="append", choices=sorted(BY_KEY) + ["ea-history"],
                    help="read only this source (repeatable)")
    ap.add_argument("--ea-history", action="store_true",
                    help="live only: also read each inland bathing water's EA incident history (38 requests, "
                         f"one at a time), at most once a day ({HISTORY_STAMP.name} in the cache)")
    ap.add_argument("--check-file", type=Path, default=CHECK_FILE,
                    help="live runs only: where the check record goes (default data/advisories/last_check.json)")
    ap.add_argument("--entry", action="append", default=[], metavar="DRAFT_ID",
                    help="also print this draft as an approvals entry for a reviewer to complete (repeatable)")
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
    # A fixture run never lands on the live drafts file: that file is next week's --previous.
    out = args.out or config.CACHE / ("advisory_drafts_fixtures.json" if args.fixtures else "advisory_drafts.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(table(result))
    print(f"Drafts written to {out}")
    if result["mode"] == "live" and not args.source:
        # A run of some sources only is not a check of all of them, so it leaves the record alone.
        args.check_file.parent.mkdir(parents=True, exist_ok=True)
        record = check_record(result, load_check(args.check_file))   # keeps advisories that ended earlier
        args.check_file.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Check record written to {args.check_file}: commit it by pull request")
    by_id = {d["draft_id"]: d for d in result["drafts"]}
    for did in args.entry:
        if did in by_id and by_id[did].get("spot_id"):
            print(json.dumps(review_entry(by_id[did]), ensure_ascii=False))
        else:
            print(f"No draft at a spot with id {did}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
