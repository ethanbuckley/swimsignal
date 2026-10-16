#!/bin/zsh
# run_variant.sh <name> <lake distance mode> <data dir> [placebo csv]   (docs/LAKE-DISTANCE-2026-10.md)
# scripts/lake_residence_eval/run_variant.sh with the lake distance option in place of the lake path option, which
# stays at its default (residence_spill, with the committed spill file from the frozen raw folder). A fresh scratch
# DIPCAST_ROOT under $DIAG_DIR/roots (inputs copied from <data dir>; the river network and raw linked, read only), then
# the E. coli chain one script at a time with every outgoing network connection refused, then the per-sample held-out
# predictions (paired.py prep). With a placebo csv, run_offline.py swaps in its ratios. Velocity and dilution stay at
# main's defaults. PYTHON overrides the interpreter (default: uv run --offline python).
# One run peaks at about 7 GB of memory: run one at a time (queue.sh does).
H=${0:A:h}
W=${0:A:h:h:h}
R0=$W/scripts/lake_residence_eval
M=${3:?data dir}
S=${DIAG_DIR:?set DIAG_DIR to a scratch folder}
PY=(${=PYTHON:-uv run --offline python})
V=$1
R=$S/roots/$V
rm -rf $R
mkdir -p $R/data/processed
ln -sfn ${M:A}/raw $R/data/raw
for f in $M/processed/*; do
  b=${f:t}
  if [[ $b == river_network.pkl ]]; then ln -sfn ${f:A} $R/data/processed/$b
  else cp -pL $f $R/data/processed/$b; fi
done
unset DIPCAST_VELOCITY_MODE DIPCAST_DILUTION_MODE DIPCAST_EVAL_PINS DIPCAST_LAKE_PATH_MODE DIPCAST_LAKE_RESIDENCE_FILE \
  DIPCAST_LAKE_RESIDENCE_SPILL_FILE LAKE_DISTANCE_PLACEBO
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed DIPCAST_CACHE=${M:A}/cache
export DIPCAST_LAKE_DISTANCE_MODE=$2
[[ -n $4 ]] && export LAKE_DISTANCE_PLACEBO=${4:A}
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
cd $W
L=$S/logs/$V; rm -rf $L; mkdir -p $L
date +%s > $L/start
for s in validate_ecoli replay_ecoli_leads validate_ecoli_combined train_ecoli; do
  /usr/bin/time -l $PY $H/run_offline.py scripts/$s.py > $L/$s.log 2>&1 || { echo "$V: $s failed" >&2; exit 1; }
  date +%s > $L/$s.done
done
unset LAKE_DISTANCE_PLACEBO
/usr/bin/time -l $PY $H/run_offline.py $R0/paired.py prep $R $S/preds_$V.parquet > $L/prep.log 2>&1 || { echo "$V: prep failed" >&2; exit 1; }
date +%s > $L/done
