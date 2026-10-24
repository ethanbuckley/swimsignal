#!/bin/zsh
# run.sh <data dir> <out dir>   (docs/DRY-SPELL-TEST-2026-10.md)
# Run from a git archive of the commit that adds this harness. A fresh scratch DIPCAST_ROOT under <out dir>/root,
# built as scripts/dieoff_weather_eval/run.sh builds it: raw and the river network linked from <data dir> (read only),
# the other processed files copied, rain read from <data dir>/cache. Then, one at a time with every outgoing
# connection refused:
#   validate_ecoli.py                       today's rows and risk_model
#   replay_ecoli_leads.py, train_ecoli.py   the exposures score.py reads, and train_ecoli's scores for its face check
#   score.py                                both questions and the per-site lags
# Main's defaults; no option variables. PYTHON overrides the interpreter (default: uv run --offline python).
H=${0:A:h}
W=${0:A:h:h:h}
M=${1:?data dir}
O=${2:?out dir}
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
step replay scripts/replay_ecoli_leads.py
step train scripts/train_ecoli.py
step score $H/score.py $O/score.json
echo done
