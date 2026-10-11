#!/bin/zsh
# run_variant.sh <name> <LAKE_PATH_MODE>   (docs/LAKE-PATH-TEST-2026-10.md)
# PR #172's run_variant.sh with the lake path option in place of the dilution option. A fresh scratch
# DIPCAST_ROOT under $DIAG_DIR/roots (inputs copied from $DIPCAST_MAIN_DATA; the river network and raw
# linked, read only), then the E. coli chain one script at a time with every outgoing network connection
# refused, then the per-sample held-out predictions (paired.py prep). Velocity and dilution stay at the
# defaults. Needs PR #172's run_offline.py and paired.py in $HARNESS (default scripts/urban_diagnosis).
# PYTHON overrides the interpreter (default: uv run --offline python).
# One run peaks at about 3.7 GB of memory: run one at a time on a 16 GB machine.
W=${0:A:h:h:h}
H=${HARNESS:-$W/scripts/urban_diagnosis}
M=${DIPCAST_MAIN_DATA:-$W/data}
S=${DIAG_DIR:?set DIAG_DIR to a scratch folder}
PY=(${=PYTHON:-uv run --offline python})
V=$1
R=$S/roots/$V
rm -rf $R
mkdir -p $R/data/processed
ln -sfn $M/raw $R/data/raw
for f in $M/processed/*; do
  b=${f:t}
  if [[ $b == river_network.pkl ]]; then ln -sfn $f $R/data/processed/$b
  else cp -p $f $R/data/processed/$b; fi
done
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed DIPCAST_CACHE=$M/cache
export DIPCAST_VELOCITY_MODE=fixed DIPCAST_DILUTION_MODE=length DIPCAST_LAKE_PATH_MODE=$2
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
