#!/bin/bash
# River-rises evaluation fetch (docs/RIVER-RISES-SCOPE-2026-10.md, "Running"; not before 2 November 2026). Waits
# while the group's heavy-run lock exists, takes it, runs one capped fetch, and releases the lock on any exit.
# Resumable: a run that stops at the 300-request cap is continued by running this again (cached answers are free).
#   bash scripts/river_rises_eval/run_fetch.sh <cache dir> <out dir>
set -u
CACHE="${1:?usage: run_fetch.sh <cache dir> <out dir>}"
OUT="${2:?usage: run_fetch.sh <cache dir> <out dir>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOCK="$HOME/Library/Application Support/Claude/side-session-notes/local_dc9219fa-fafc-4f09-a84d-03316133ab4a/heavy-run.lock"
while [ -e "$LOCK" ]; do sleep 60; done
printf 'river-rises evaluation fetch (scripts/river_rises_eval/run_fetch.sh): EA Hydrology, up to ~120 two-year series, ~1.5 GB to %s, capped 300 requests a run, network-bound, started %s UTC, waiter pid %s. Pause: kill the python pid; resume: run it again.\n' \
  "$CACHE" "$(date -u +%FT%TZ)" $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
mkdir -p "$OUT"
echo "start $(date -u +%FT%TZ)" >> "$OUT/fetch.log"
cd "$ROOT" && caffeinate -i uv run python scripts/river_rises_eval/fetch.py --cache "$CACHE" --out "$OUT" --fetch 2>&1 | tee -a "$OUT/fetch.log"
code=${PIPESTATUS[0]}
echo "exit $code at $(date -u +%FT%TZ)" >> "$OUT/fetch.log"
exit "$code"
