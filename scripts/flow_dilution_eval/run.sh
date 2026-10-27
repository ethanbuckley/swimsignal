#!/bin/zsh
# run.sh <stage> <data dir> <station cache> <flow cache> <soil dir> <out dir>   (docs/FLOW-DILUTION-TEST-2026-10.md)
# Not before Ethan approves the statement. Run from a git archive of the commit that adds this harness, alone, under
# the group's heavy-run.lock, with 35% memory free. Stages, in order:
#   prepare   scratch DIPCAST_ROOT under <out>/root (raw and the river network linked read-only from <data dir>, the
#             other processed files copied, rain from <data dir>/cache); validate_ecoli.py and replay_ecoli_leads.py
#             rebuilt at this commit; score.py map. All offline.
#   fetch     flow_fetch.py flows: the only stage that reaches the network (EA Hydrology only, capped).
#   predict   score.py prep (exposures and the face check), then score.py predict (predictions, gate, B and H).
#             Offline. Stops at a failed face check.
#   score     score.py score. Offline. Refuses predictions that run_statement.json does not name.
# Main's defaults; no option variables. PYTHON overrides the interpreter (default: uv run --offline python).
H=${0:A:h}
W=${0:A:h:h:h}
S=${1:?stage}
M=${2:?data dir}
SC=${3:?station cache}
FC=${4:?flow cache}
SD=${5:?soil dir}
O=${6:?out dir}
PY=(${=PYTHON:-uv run --offline python})
OFF=$W/scripts/lake_distance_eval/run_offline.py
R=$O/root
L=$O/logs
unset DIPCAST_VELOCITY_MODE DIPCAST_DILUTION_MODE DIPCAST_EVAL_PINS DIPCAST_LAKE_PATH_MODE DIPCAST_LAKE_RESIDENCE_FILE \
  DIPCAST_LAKE_RESIDENCE_SPILL_FILE DIPCAST_LAKE_DISTANCE_MODE LAKE_DISTANCE_PLACEBO OPEN_METEO_API_KEY
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed DIPCAST_CACHE=${M:A}/cache
export PYTHONPATH=$W/src:$W/scripts:$W/scripts/soil_moisture_eval${PYTHONPATH:+:$PYTHONPATH}
cd $W
step() { local n=$1; shift; date +%s > $L/$n.start
  /usr/bin/time -l $PY $OFF "$@" > $L/$n.log 2>&1 || { echo "$n failed" >&2; exit 1; }
  date +%s > $L/$n.done
  [[ $(grep -o 'network attempts: [0-9]*' $L/$n.log | tail -1) == 'network attempts: 0' ]] \
    || { echo "$n made network attempts (or printed no count)" >&2; exit 1; }; }
case $S in
  prepare)
    rm -rf $R $L; mkdir -p $R/data/processed $L
    ln -sfn ${M:A}/raw $R/data/raw
    for f in $M/processed/*; do
      b=${f:t}
      if [[ $b == river_network.pkl ]]; then ln -sfn ${f:A} $R/data/processed/$b
      else cp -pRL $f $R/data/processed/$b; fi
    done
    (cd ${M:A} && find -L processed raw -type f ! -name river_network.pkl | LC_ALL=C sort | tr '\n' '\0' \
      | xargs -0 shasum -a 256 | shasum -a 256) > $L/data_hash.txt
    step validate scripts/validate_ecoli.py
    step replay scripts/replay_ecoli_leads.py
    step map $H/score.py map $SC $O ;;
  fetch)
    $PY $H/flow_fetch.py flows --cache $FC --gauges $O/gauges.csv --fetch 2>&1 | tee $L/fetch.log ;;
  predict)
    step prep $H/score.py prep $SC $FC $O
    step predict $H/score.py predict $SD $O ;;
  score)
    step score $H/score.py score $O ;;
  *) echo "unknown stage $S" >&2; exit 2 ;;
esac
echo "$S done"
