#!/bin/zsh
# docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md. Runs only after Ethan has approved the statement.
# run.sh stage1 <out dir> masks                     online, outcome-blind, SCL only; rerun until "complete"
# run.sh stage1 <out dir> readings                  online, outcome-blind, B4/B5 and NDCI; rerun until "complete"
# run.sh fetch  <out dir> <features SHA-256>        the chlorophyll-a values, once (needs the committed features hash)
# run.sh score  <out dir> <features SHA-256> <values SHA-256>
#                                                   offline: every outgoing connection refused and counted
# Run from a git archive of the commit that holds the approved statement, in a scratch folder, one step at a time,
# under the group's heavy-run lock, nothing else heavy running. Stage 1 exits 3 when a cap or a stop rule stops it
# and resumes from <out dir> on the next run. The score step must print "network attempts: 0".
# PYTHON overrides the interpreter (default: uv run --offline python).
H=${0:A:h}
W=${0:A:h:h:h}
CMD=${1:?stage1, fetch or score}
O=${2:?out dir}
LAKES=$W/docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-lakes.json
PY=(${=PYTHON:-uv run --offline python})
OFF=$W/scripts/lake_distance_eval/run_offline.py
export PYTHONPATH=$W/src:$H${PYTHONPATH:+:$PYTHONPATH}
mkdir -p $O/logs
L=$O/logs
cd $W
case $CMD in
  stage1)
    # Online, but no chlorophyll value exists here: chl_stage1.py never imports chl_stage2.
    $PY $H/chl_stage1.py $O $LAKES ${3:?masks or readings} 2>&1 | tee -a $L/stage1.log
    exit ${pipestatus[1]} ;;
  fetch)
    F=${3:?committed features SHA-256}
    [[ -f $O/values.parquet ]] && { echo "values.parquet exists: fetched once already" >&2; exit 1; }
    $PY $H/chl_stage2.py fetch $O $LAKES $F 2>&1 | tee $L/fetch.log
    exit ${pipestatus[1]} ;;
  score)
    F=${3:?committed features SHA-256}
    V=${4:?values SHA-256}
    /usr/bin/time -l $PY $OFF $H/chl_stage2.py score $O $LAKES $F $V > $L/score.log 2>&1 || { echo "score failed" >&2; exit 1; }
    [[ $(grep -o 'network attempts: [0-9]*' $L/score.log | tail -1) == 'network attempts: 0' ]] \
      || { echo "score made network attempts (or printed no count)" >&2; exit 1; }
    echo done ;;
  *) echo "stage1, fetch or score" >&2; exit 2 ;;
esac
