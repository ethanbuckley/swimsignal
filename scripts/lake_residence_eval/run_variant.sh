#!/bin/zsh
# run_variant.sh <name> <lake path mode> <data dir> [residence csv]   (docs/LAKE-RESIDENCE-TEST-2026-10.md)
# PR #199's scripts/eval_pins_test/run_variant.sh with the lake path option (and its residence file) in place of
# DIPCAST_EVAL_PINS, which stays at its default (the site's pins). A fresh scratch DIPCAST_ROOT under $DIAG_DIR/roots
# (inputs copied from <data dir>; the river network and raw linked, read only; the residence file copied into the
# root), then the E. coli chain one script at a time with every outgoing network connection refused, then the
# per-sample held-out predictions (paired.py prep). <data dir> holds raw/, processed/ (with an overflows.parquet
# built on the current network) and cache/rain/. Velocity and dilution stay at main's defaults.
# PYTHON overrides the interpreter (default: uv run --offline python).
# One run peaks at about 4 GB of memory: run one at a time on a 16 GB machine (queue.sh does).
H=${0:A:h}
W=${0:A:h:h:h}
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
unset DIPCAST_VELOCITY_MODE DIPCAST_DILUTION_MODE DIPCAST_EVAL_PINS DIPCAST_LAKE_RESIDENCE_FILE
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed DIPCAST_CACHE=${M:A}/cache
export DIPCAST_LAKE_PATH_MODE=$2
if [[ -n $4 ]]; then
  cp -p $4 $R/lake_residence.csv
  export DIPCAST_LAKE_RESIDENCE_FILE=$R/lake_residence.csv
fi
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
cd $W
L=$S/logs/$V; rm -rf $L; mkdir -p $L
date +%s > $L/start
for s in validate_ecoli replay_ecoli_leads validate_ecoli_combined train_ecoli; do
  /usr/bin/time -l $PY $H/run_offline.py scripts/$s.py > $L/$s.log 2>&1 || { echo "$V: $s failed" >&2; exit 1; }
  date +%s > $L/$s.done
done
/usr/bin/time -l $PY $H/run_offline.py $H/paired.py prep $R $S/preds_$V.parquet > $L/prep.log 2>&1 || { echo "$V: prep failed" >&2; exit 1; }
date +%s > $L/done
