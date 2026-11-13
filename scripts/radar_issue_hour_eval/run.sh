#!/bin/zsh
# run.sh <data dir> <radar_publish_times.csv> <out dir>   (docs/RADAR-ISSUE-HOUR-TEST-2026-11.md)
# Run from a git archive of the commit that adds this folder. A scratch DIPCAST_ROOT under <out dir>/root holds copies
# of the processed files read; DIPCAST_CACHE points at <data dir>/cache, read-only; the radar folder is read in place.
# Shared inputs are fingerprinted before and after. Every outgoing connection is refused
# (scripts/lake_distance_eval/run_offline.py). At most 4 threads. RADAR_ISSUE_HOUR_PLUMBING=1 runs the check on
# random labels instead. PYTHON names the interpreter (default: uv run --offline python, from the archive).
H=${0:A:h}
W=${0:A:h:h:h}
PY=(${=PYTHON:-uv run --offline python})
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
M=${1:?data dir}; L=${2:?publish times csv}; O=${3:?out dir}
M=${M:A}; L=${L:A}; mkdir -p $O; O=${O:A}
cd $W
zsh $H/fingerprint.sh $M $O/fingerprint_before.txt
rm -rf $O/root; mkdir -p $O/root/data/processed
for f in annual_returns.parquet api_events_thames_water.parquet spill_model.pkl; do
  cp -p $M/processed/$f $O/root/data/processed/
done
cp -p $M/processed/ea_events_*.parquet $O/root/data/processed/
export DIPCAST_ROOT=$O/root DIPCAST_STATE=$O/root/data/processed DIPCAST_CACHE=$M/cache
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 VECLIB_MAXIMUM_THREADS=4
/usr/bin/time -l $PY $W/scripts/lake_distance_eval/run_offline.py $H/score.py $M/raw/met_office_radar $L $O \
  > $O/score.log 2>&1
st=$?
zsh $H/fingerprint.sh $M $O/fingerprint_after.txt
if cmp -s $O/fingerprint_before.txt $O/fingerprint_after.txt; then echo "inputs unchanged" >> $O/score.log
else echo "INPUTS CHANGED" >> $O/score.log; fi
exit $st
