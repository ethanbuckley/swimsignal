#!/bin/zsh
# run_variant.sh <name> <DILUTION_MODE> <data dir> [size table.parquet]   (docs/PE-SIZE-TEST-2026-10.md)
# PR #172's run_variant.sh: a fresh scratch DIPCAST_ROOT under $DIAG_DIR/roots (inputs copied from <data dir>;
# the river network and raw linked, read only), the size table copied in as overflow_urban_area.parquet when
# given, then the E. coli chain one script at a time with every outgoing network connection refused, then
# the per-sample held-out predictions (paired.py prep). Velocity, lake path and lake near field stay at
# main's defaults. PYTHON overrides the interpreter (default: uv run --offline python).
# One run peaks at about 3.7 GB of memory: run one at a time on a 16 GB machine.
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
if [[ -n $4 ]]; then cp $4 $R/data/processed/overflow_urban_area.parquet; fi
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed DIPCAST_CACHE=${M:A}/cache
export DIPCAST_DILUTION_MODE=$2
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
