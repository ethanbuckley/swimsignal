#!/bin/zsh
# run.sh <data dir> <per-overflow radar dir> <out dir>   (docs/RADAR-PER-OVERFLOW-TEST-2026-11.md)
# Run from a git archive of the harness commit, holding the group's heavy-run lock. A scratch DIPCAST_ROOT under
# <out dir>/root holds copies of the processed files read; DIPCAST_CACHE points at <data dir>/cache, read-only; the
# radar folders are read in place. Shared inputs are fingerprinted before and after. Every outgoing connection is
# refused (scripts/lake_distance_eval/run_offline.py). RADAR_OVERFLOW_PLUMBING=1 runs the harness check instead.
H=${0:A:h}
W=${0:A:h:h:h}
PY=(${=PYTHON:-uv run --offline python})
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
M=${1:?data dir}; R=${2:?per-overflow radar dir}; O=${3:?out dir}
M=${M:A}; R=${R:A}; mkdir -p $O; O=${O:A}
cd $W
zsh $H/fingerprint.sh $M $R $O/fingerprint_before.txt
rm -rf $O/root; mkdir -p $O/root/data/processed
for f in annual_returns.parquet api_events_thames_water.parquet overflow_urban_area.parquet spill_model.pkl; do
  cp -p $M/processed/$f $O/root/data/processed/
done
cp -p $M/processed/ea_events_*.parquet $O/root/data/processed/
export DIPCAST_ROOT=$O/root DIPCAST_STATE=$O/root/data/processed DIPCAST_CACHE=$M/cache
/usr/bin/time -l $PY $W/scripts/lake_distance_eval/run_offline.py $H/score.py $R/data/overflows $M/raw/met_office_radar $O \
  > $O/score.log 2>&1
st=$?
zsh $H/fingerprint.sh $M $R $O/fingerprint_after.txt
if cmp -s $O/fingerprint_before.txt $O/fingerprint_after.txt; then echo "inputs unchanged" >> $O/score.log
else echo "INPUTS CHANGED" >> $O/score.log; fi
exit $st
