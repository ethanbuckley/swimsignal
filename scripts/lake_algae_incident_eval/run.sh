#!/bin/zsh
# run.sh fetch <out dir> <features file> <features SHA-256>        online, once: the EA incident histories
# run.sh score <out dir> <features file> <features SHA-256> <incidents SHA-256>
#                                                                    offline, under the group's heavy-run lock
# (docs/LAKE-ALGAE-INCIDENT-TEST-2026-10.md)
# Run from a git archive of the harness commit, in a scratch folder. Score only after the incidents hash is committed.
# The score step refuses while the lock exists, takes it with noclobber, and deletes it when it ends. It passes only
# if it prints "network attempts: 0".
# PYTHON overrides the interpreter (default: uv run --offline python).
H=${0:A:h}
W=${0:A:h:h:h}
CMD=${1:?fetch or score}
O=${2:?out dir}
F=${3:?features file}
FS=${4:?committed features SHA-256}
PY=(${=PYTHON:-uv run --offline python})
OFF=$W/scripts/lake_distance_eval/run_offline.py
LOCK="$HOME/Library/Application Support/Claude/side-session-notes/local_dc9219fa-fafc-4f09-a84d-03316133ab4a/heavy-run.lock"
export PYTHONPATH=$W/src:$H${PYTHONPATH:+:$PYTHONPATH}
mkdir -p $O/logs
L=$O/logs
cd $W
case $CMD in
  fetch)
    [[ -f $O/incidents.json ]] && { echo "incidents.json exists: fetched once already" >&2; exit 1; }
    $PY $H/incident_fetch.py $O $F $FS 2>&1 | tee $L/fetch.log
    exit ${pipestatus[1]} ;;
  score)
    IS=${5:?committed incidents SHA-256}
    [[ -e $LOCK ]] && { echo "heavy-run.lock is held: wait" >&2; exit 4; }
    ( set -o noclobber; print "lake-algae-incident score $$ $(date -u +%FT%TZ)" > $LOCK ) 2>/dev/null \
      || { echo "could not take heavy-run.lock" >&2; exit 4; }
    trap 'rm -f -- $LOCK' EXIT INT TERM
    /usr/bin/time -l $PY $OFF $H/incident_score.py $O $F $FS $IS > $L/score.log 2>&1 || { echo "score failed" >&2; exit 1; }
    [[ $(grep -o 'network attempts: [0-9]*' $L/score.log | tail -1) == 'network attempts: 0' ]] \
      || { echo "score made network attempts (or printed no count)" >&2; exit 1; }
    grep '^verdict:' $L/score.log
    echo done ;;
  *) echo "fetch or score" >&2; exit 2 ;;
esac
