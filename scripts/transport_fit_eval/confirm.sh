#!/bin/zsh
# confirm.sh <data dir> <out dir>   (docs/TRANSPORT-FIT-TEST-2026-10.md, "What follows")
# The E. coli chain on the fitted settings, run from an archive of the commit that switches them: validate_ecoli,
# replay_ecoli_leads, validate_ecoli_combined, then train_ecoli, one at a time, every outgoing connection refused.
# The scratch root is built as run.sh builds it. train_ecoli's LOYO Brier score decides adoption.
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
  else cp -pL $f $R/data/processed/$b; fi
done
unset DIPCAST_VELOCITY_MODE DIPCAST_DILUTION_MODE DIPCAST_EVAL_PINS DIPCAST_LAKE_PATH_MODE DIPCAST_LAKE_RESIDENCE_FILE \
  DIPCAST_LAKE_RESIDENCE_SPILL_FILE DIPCAST_LAKE_DISTANCE_MODE LAKE_DISTANCE_PLACEBO
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed DIPCAST_CACHE=${M:A}/cache
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
cd $W
L=$O/logs
$PY -c "import dipcast; from dipcast import config; from dipcast.model import transport
print(dipcast.__file__, config.RIVER_VELOCITY_MS, config.T90_HOURS, transport.DILUTION_POWER)" > $L/which.log
for s in validate_ecoli replay_ecoli_leads validate_ecoli_combined train_ecoli; do
  date +%s > $L/$s.start
  /usr/bin/time -l $PY $OFF scripts/$s.py > $L/$s.log 2>&1 || { echo "$s failed" >&2; exit 1; }
  date +%s > $L/$s.done
done
echo done
