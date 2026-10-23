#!/bin/zsh
# run.sh <data dir> <weather cache> <out dir>   (docs/DIEOFF-WEATHER-TEST-2026-10.md)
# Run from a git archive of the commit that adds this harness, after weather.py fetch. A fresh scratch DIPCAST_ROOT
# under <out dir>/root, built as scripts/transport_fit_eval/run.sh builds it: raw and the river network linked from
# <data dir> (read only), the other processed files copied, rain read from <data dir>/cache. Then, one at a time with
# every outgoing connection refused:
#   validate_ecoli.py                 risk_model, for question 1's face check
#   q1.py prep, check, score          question 1
#   replay_ecoli_leads.py, train_ecoli.py   the exposures question 2 reads, and train_ecoli's own scores for its face check
#   q2.py                             question 2
# Main's transport defaults; no option variables. PYTHON overrides the interpreter (default: uv run --offline python).
H=${0:A:h}
W=${0:A:h:h:h}
M=${1:?data dir}
C=${2:?weather cache}
O=${3:?out dir}
PY=(${=PYTHON:-uv run --offline python})
OFF=$W/scripts/lake_distance_eval/run_offline.py
R=$O/root
rm -rf $R $O/logs; mkdir -p $R/data/processed $O/logs
ln -sfn ${M:A}/raw $R/data/raw
for f in $M/processed/*; do
  b=${f:t}
  if [[ $b == river_network.pkl ]]; then ln -sfn ${f:A} $R/data/processed/$b
  else cp -pRL $f $R/data/processed/$b; fi
done
unset DIPCAST_VELOCITY_MODE DIPCAST_DILUTION_MODE DIPCAST_EVAL_PINS DIPCAST_LAKE_PATH_MODE DIPCAST_LAKE_RESIDENCE_FILE \
  DIPCAST_LAKE_RESIDENCE_SPILL_FILE DIPCAST_LAKE_DISTANCE_MODE LAKE_DISTANCE_PLACEBO OPEN_METEO_API_KEY
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed DIPCAST_CACHE=${M:A}/cache
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
cd $W
L=$O/logs
step() { local n=$1; shift; date +%s > $L/$n.start
  /usr/bin/time -l $PY $OFF "$@" > $L/$n.log 2>&1 || { echo "$n failed" >&2; exit 1; }
  date +%s > $L/$n.done; }
$PY -c "import dipcast; from dipcast import config; from dipcast.model import transport
print(dipcast.__file__, config.RIVER_VELOCITY_MS, config.T90_HOURS, transport.DILUTION_POWER, config.LAKE_PATH_MODE)" > $L/which.log
step validate scripts/validate_ecoli.py
step q1_prep $H/q1.py prep ${C:A} $O/q1_rows.parquet
step q1_check $H/q1.py check $O/q1_rows.parquet $R/data/processed/ecoli_validation_rows.parquet
step q1_score $H/q1.py score $O/q1_rows.parquet $O/q1_score.json
step replay scripts/replay_ecoli_leads.py
step train scripts/train_ecoli.py
step q2 $H/q2.py ${C:A} $O/q2_score.json
echo done
