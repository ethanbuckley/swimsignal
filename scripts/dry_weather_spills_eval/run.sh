#!/bin/zsh
# run.sh <processed dir> <cache dir> <D2 candidate> <2026 zip> <out dir>   (docs/DRY-WEATHER-SPILLS-TEST-2026-10.md)
# Run from a git archive of the commit that adds this harness. Two scratch roots under <out dir>, nothing written
# outside it; <processed dir>, <cache dir>, the candidate and the zip are only read:
#   root      annual returns, the nine companies' EA event files and spill_model.pkl copied from <processed dir>,
#             and D2's candidate (spill_model_nine_2024.pkl) copied in
#   root2026  annual returns and the 2026 zip copied in, for scripts/import_ea_events.py --years 2026, which would
#             otherwise overwrite the 2024-25 event files in its PROCESSED
# Then, one at a time with every outgoing connection refused: the 2026 import, then score.py. Rain is read from
# <cache dir>. PYTHON overrides the interpreter (default: uv run --offline python).
H=${0:A:h}
W=${0:A:h:h:h}
P=${1:?processed dir}
C=${2:?cache dir}
D2=${3:?D2 candidate}
Z=${4:?2026 zip}
O=${5:?out dir}
PY=(${=PYTHON:-uv run --offline python})
OFF=$W/scripts/lake_distance_eval/run_offline.py
R=$O/root
R6=$O/root2026
rm -rf $R $R6 $O/logs; mkdir -p $R/data/processed $R6/data/processed $R6/data/raw/ea_events $O/logs
cp -p $P/annual_returns.parquet $P/spill_model.pkl $P/ea_events_*_water.parquet $P/ea_events_united_utilities.parquet \
  $R/data/processed/
cp -p $D2 $R/data/processed/spill_model_nine_2024.pkl
cp -p $P/annual_returns.parquet $R6/data/processed/
cp -p $Z $R6/data/raw/ea_events/
unset DIPCAST_VELOCITY_MODE DIPCAST_DILUTION_MODE DIPCAST_EVAL_PINS DIPCAST_LAKE_PATH_MODE OPEN_METEO_API_KEY
export DIPCAST_CACHE=${C:A}
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
cd $W
L=$O/logs
step() { local n=$1; shift; date +%s > $L/$n.start
  /usr/bin/time -l $PY $OFF "$@" > $L/$n.log 2>&1 || { echo "$n failed" >&2; exit 1; }
  date +%s > $L/$n.done; }
shasum -a 256 $R/data/processed/* $R6/data/raw/ea_events/* > $L/inputs.sha256
export DIPCAST_ROOT=$R6 DIPCAST_STATE=$R6/data/processed
step import2026 scripts/import_ea_events.py --years 2026
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed
step score $H/score.py $O/out $R6/data/processed
echo done
