#!/bin/zsh
# run.sh <data dir> <out dir>   (docs/TRANSPORT-FIT-TEST-2026-10.md)
# Run from a git archive of the commit that states the test. A fresh scratch DIPCAST_ROOT under <out dir>/root:
# raw and the river network linked from <data dir> (read only), the other processed files copied, rain read from
# <data dir>/cache. Then, one at a time with every outgoing connection refused: validate_ecoli.py (for the face
# check), fit.py prep, check and score. Main's transport defaults; no option variables. PYTHON overrides the
# interpreter (default: uv run --offline python).
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
step() { local n=$1; shift; date +%s > $L/$n.start
  /usr/bin/time -l $PY $OFF "$@" > $L/$n.log 2>&1 || { echo "$n failed" >&2; exit 1; }
  date +%s > $L/$n.done; }
$PY -c "import dipcast; print(dipcast.__file__)" > $L/which.log
step validate scripts/validate_ecoli.py
step prep $H/fit.py prep $O/rows.parquet
step check $H/fit.py check $O/rows.parquet $R/data/processed/ecoli_validation_rows.parquet
step score $H/fit.py score $O/rows.parquet $O/score.json
echo done
