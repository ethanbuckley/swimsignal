#!/bin/zsh
# run.sh stage1 <out dir> masks                         online, outcome-blind, SCL only; rerun until complete
# run.sh stage1 <out dir> readings [skip.txt]            online, outcome-blind, B4/B5 and NDCI; rerun until complete
# run.sh fetch  <out dir> <features SHA-256>             the EA algae checks, once (needs the committed features hash)
# run.sh score  <out dir> <features SHA-256> <checks SHA-256>
#                                                        offline: every outgoing connection refused and counted
# (docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md)
# Run from a git archive of the commit that adds this harness, in a scratch folder, one step at a time, nothing else
# running. Stage 1's caps are in net.py; it exits 3 when a cap stops it, and resumes from <out dir> on the next run.
# The score step runs only if every check above passes and prints "network attempts: 0".
# PYTHON overrides the interpreter (default: uv run --offline python).
H=${0:A:h}
W=${0:A:h:h:h}
CMD=${1:?stage1, fetch or score}
O=${2:?out dir}
PY=(${=PYTHON:-uv run --offline python})
OFF=$W/scripts/lake_distance_eval/run_offline.py
export PYTHONPATH=$W/src:$H${PYTHONPATH:+:$PYTHONPATH}
mkdir -p $O/logs
L=$O/logs
cd $W
case $CMD in
  stage1)
    # Online, but no EA check exists here: stage1.py never imports the algae fetch.
    $PY $H/stage1.py $O ${3:?masks or readings} ${4:-} 2>&1 | tee -a $L/stage1.log
    exit ${pipestatus[1]} ;;
  fetch)
    F=${3:?committed features SHA-256}
    [[ -f $O/checks.parquet ]] && { echo "checks.parquet exists: fetched once already" >&2; exit 1; }
    $PY $H/stage2.py fetch $O $F 2>&1 | tee $L/fetch.log
    exit ${pipestatus[1]} ;;
  score)
    F=${3:?committed features SHA-256}
    C=${4:?checks SHA-256}
    /usr/bin/time -l $PY $OFF $H/stage2.py score $O $F $C > $L/score.log 2>&1 || { echo "score failed" >&2; exit 1; }
    [[ $(grep -o 'network attempts: [0-9]*' $L/score.log | tail -1) == 'network attempts: 0' ]] \
      || { echo "score made network attempts (or printed no count)" >&2; exit 1; }
    echo done ;;
  *) echo "stage1, fetch or score" >&2; exit 2 ;;
esac
