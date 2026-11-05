#!/bin/zsh
# Runs one stage of docs/LAKE-TEMPERATURE-TEST-2026-10.md under the group's heavy-run lock:
#   run_locked.sh <label> <command> [args...]
# Takes the lock only if it is absent (exit 3 if held: wait, never break it); removes only its own lock.
LOCK="$HOME/Library/Application Support/Claude/side-session-notes/local_dc9219fa-fafc-4f09-a84d-03316133ab4a/heavy-run.lock"
if [[ -e "$LOCK" ]]; then echo "lock held: $(cat "$LOCK")"; exit 3; fi
echo "lake temperature test: $1; started $(date -u +%FT%TZ), pid $$" > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
label=$1; shift
echo "stage $label start $(date -u +%FT%TZ) commit $(/usr/bin/git -C "${0:A:h}" rev-parse --short HEAD)"
/usr/bin/time -l "$@"
rc=$?
echo "stage $label exit $rc $(date -u +%FT%TZ)"
exit $rc
