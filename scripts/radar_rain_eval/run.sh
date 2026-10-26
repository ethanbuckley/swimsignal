#!/bin/zsh
# run.sh fetch <radar dir> <out dir>          the gauge fetch (online), once, after the harness commit
# run.sh score <data dir> <radar dir> <out dir>   everything else, offline   (docs/RADAR-RAIN-CHECK-2026-10.md)
# Run from a git archive of the harness commit. score: a scratch DIPCAST_ROOT under <out dir>/root holding the
# archive's tracked data/processed files and the EA start/stop parquets copied from <data dir>/processed; rain read
# from <data dir>/cache; radar read from <radar dir>. File hashes go to <out dir>/hashes.txt. Every outgoing
# connection is refused during scoring (scripts/lake_distance_eval/run_offline.py).
H=${0:A:h}
W=${0:A:h:h:h}
PY=(${=PYTHON:-uv run python})
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
cd $W
case $1 in
fetch)
  R=${2:?radar dir}; O=${3:?out dir}; mkdir -p $O/gauges
  $PY $H/gauges.py $R $O/gauges 2>&1 | tee $O/gauges.log ;;
score)
  M=${2:?data dir}; R=${3:?radar dir}; O=${4:?out dir}
  rm -rf $O/root; mkdir -p $O/root/data/processed
  cp -p $W/data/processed/* $O/root/data/processed/ 2>/dev/null
  cp -p $M/processed/ea_events_*.parquet $O/root/data/processed/
  (cd $O/root/data/processed && shasum -a 256 *) > $O/hashes.txt
  (cd $R && ls | sort | xargs shasum -a 256 | shasum -a 256 | sed 's/^/radar dir: /') >> $O/hashes.txt
  shasum -a 256 $O/gauges/gauges_hourly.parquet >> $O/hashes.txt
  export DIPCAST_ROOT=$O/root DIPCAST_STATE=$O/root/data/processed DIPCAST_CACHE=${M:A}/cache
  date +%s > $O/score.start
  /usr/bin/time -l $PY $W/scripts/lake_distance_eval/run_offline.py $H/score.py ${R:A} $O/gauges $O/score.json > $O/score.log 2>&1 \
    || { echo "score failed" >&2; exit 1; }
  date +%s > $O/score.done ;;
*) echo "run.sh fetch|score ..." >&2; exit 2 ;;
esac
