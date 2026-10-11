#!/bin/zsh
# run_variant.sh <name> <DILUTION_MODE> [urban_table.parquet]
# Fresh scratch DIPCAST_ROOT under $DIAG_DIR/roots (inputs copied from $DIPCAST_MAIN_DATA, river network and
# raw linked read only), then the E. coli evaluation chain, one script at a time, every outgoing network
# connection refused; then the per-sample held-out predictions (paired.py prep).
# One run peaks at about 3.7 GB of memory (replay_ecoli_leads.py): run one at a time on a 16 GB machine.
H=${0:A:h}
W=${0:A:h:h:h}
M=${DIPCAST_MAIN_DATA:-$W/data}
S=${DIAG_DIR:?set DIAG_DIR to a scratch folder}
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
if [[ -n $3 ]]; then cp $3 $R/data/processed/overflow_urban_area.parquet; fi
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed
export DIPCAST_CACHE=$M/cache
export DIPCAST_VELOCITY_MODE=fixed DIPCAST_DILUTION_MODE=$2
cd $W
L=$S/logs/$V; rm -rf $L; mkdir -p $L
date +%s > $L/start
for s in validate_ecoli replay_ecoli_leads validate_ecoli_combined train_ecoli; do
  /usr/bin/time -l uv run --offline python $H/run_offline.py scripts/$s.py > $L/$s.log 2>&1
  date +%s > $L/$s.done
done
/usr/bin/time -l uv run --offline python $H/run_offline.py $H/paired.py prep $R $S/preds_$V.parquet > $L/prep.log 2>&1
date +%s > $L/done
