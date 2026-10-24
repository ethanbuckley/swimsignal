#!/bin/zsh
# run.sh q1 <frozen data dir> <soil dir> <out dir>
# run.sh q2 <data dir> <baseline pkl> <soil dir> <out dir>          (docs/SOIL-MOISTURE-TEST-2026-10.md)
# Run from a git archive of the commit that adds this harness, after fetch.py. A fresh scratch DIPCAST_ROOT under
# <out dir>/root; nothing is written into a data folder or the soil dir. Every step runs with every outgoing
# connection refused (scripts/lake_distance_eval/run_offline.py).
# q1: the root is built as scripts/dry_spell_eval/run.sh builds it (raw and the river network linked from the frozen
#     folder, read only; the other processed files copied; rain read from its cache). Then validate_ecoli.py,
#     replay_ecoli_leads.py, train_ecoli.py and q1.py, as the dry-spell test ran them.
# q2: the root holds copies of <data dir>/processed's annual_returns.parquet and EA start/stop files, and the baseline;
#     rain is read in place from <data dir>/cache (rain, rain_nine). Then q2.py.
# Main's defaults; no option variables. PYTHON overrides the interpreter (default: uv run --offline python).
H=${0:A:h}
W=${0:A:h:h:h}
Q=${1:?q1 or q2}
PY=(${=PYTHON:-uv run --offline python})
OFF=$W/scripts/lake_distance_eval/run_offline.py
unset DIPCAST_VELOCITY_MODE DIPCAST_DILUTION_MODE DIPCAST_EVAL_PINS DIPCAST_LAKE_PATH_MODE DIPCAST_LAKE_RESIDENCE_FILE \
  DIPCAST_LAKE_RESIDENCE_SPILL_FILE DIPCAST_LAKE_DISTANCE_MODE LAKE_DISTANCE_PLACEBO OPEN_METEO_API_KEY
if [[ $Q == q1 ]]; then
  M=${2:?frozen data dir}; S=${3:?soil dir}; O=${4:?out dir}
  R=$O/root
  rm -rf $R $O/logs; mkdir -p $R/data/processed $O/logs
  ln -sfn ${M:A}/raw $R/data/raw
  for f in $M/processed/*; do
    b=${f:t}
    if [[ $b == river_network.pkl ]]; then ln -sfn ${f:A} $R/data/processed/$b
    else cp -pRL $f $R/data/processed/$b; fi
  done
  export DIPCAST_CACHE=${M:A}/cache
elif [[ $Q == q2 ]]; then
  M=${2:?data dir}; P=${3:?baseline pkl}; S=${4:?soil dir}; O=${5:?out dir}
  R=$O/root
  rm -rf $R $O/logs; mkdir -p $R/data/processed $O/logs
  cp -p $M/processed/annual_returns.parquet $M/processed/ea_events_*.parquet $R/data/processed/
  cp -p $P $R/data/processed/spill_model_nine_2024.pkl
  export DIPCAST_CACHE=${M:A}/cache
else
  echo "q1 or q2" >&2; exit 1
fi
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
cd $W
L=$O/logs
step() { local n=$1; shift; date +%s > $L/$n.start
  /usr/bin/time -l $PY $OFF "$@" > $L/$n.log 2>&1 || { echo "$n failed" >&2; exit 1; }
  date +%s > $L/$n.done; }
$PY -c "import dipcast; from dipcast import config; from dipcast.model import transport
print(dipcast.__file__, config.PROCESSED, config.CACHE, config.RIVER_VELOCITY_MS, config.T90_HOURS, transport.DILUTION_POWER, config.LAKE_PATH_MODE)" > $L/which.log
if [[ $Q == q1 ]]; then
  step validate scripts/validate_ecoli.py
  step replay scripts/replay_ecoli_leads.py
  step train scripts/train_ecoli.py
  step q1 $H/q1.py ${S:A} $O/q1.json
else
  step q2 $H/q2.py ${S:A} $O/q2
fi
echo done
