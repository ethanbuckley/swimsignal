#!/bin/zsh
# run.sh <data dir> <out dir>   (docs/LAKE-ECOLI-LINE-TEST-2026-10.md)
# Run from a git archive of the commit that adds this harness. A fresh scratch DIPCAST_ROOT under <out dir>/root,
# built as scripts/dry_spell_eval/run.sh builds it: raw and the river network linked from <data dir> (read only), the
# other processed files copied, rain read from <data dir>/cache. Then, one at a time with every outgoing connection
# refused:
#   validate_ecoli.py, replay_ecoli_leads.py   the rows file and the exposures, rebuilt at this commit
#   score.py face                              the face check at 900 (runs train_ecoli.main inside)
#   score.py score                             only if the face check passes and every step so far made 0 network
#                                              attempts: the gate, then the scores at 235 and 500
# Main's defaults; no option variables. PYTHON overrides the interpreter (default: uv run --offline python).
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
  else cp -pRL $f $R/data/processed/$b; fi
done
unset DIPCAST_VELOCITY_MODE DIPCAST_DILUTION_MODE DIPCAST_EVAL_PINS DIPCAST_LAKE_PATH_MODE DIPCAST_LAKE_RESIDENCE_FILE \
  DIPCAST_LAKE_RESIDENCE_SPILL_FILE DIPCAST_LAKE_DISTANCE_MODE LAKE_DISTANCE_PLACEBO OPEN_METEO_API_KEY
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed DIPCAST_CACHE=${M:A}/cache
export PYTHONPATH=$W/src:$W/scripts${PYTHONPATH:+:$PYTHONPATH}
cd $W
L=$O/logs
(cd ${M:A} && find -L processed raw -type f ! -name river_network.pkl | LC_ALL=C sort | tr '\n' '\0' \
  | xargs -0 shasum -a 256 | shasum -a 256) > $L/data_hash.txt
step() { local n=$1; shift; date +%s > $L/$n.start
  /usr/bin/time -l $PY $OFF "$@" > $L/$n.log 2>&1 || { echo "$n failed" >&2; exit 1; }
  date +%s > $L/$n.done
  # The count can follow unflushed stdout on the same line, so match it anywhere and read the number.
  [[ $(grep -o 'network attempts: [0-9]*' $L/$n.log | tail -1) == 'network attempts: 0' ]] \
    || { echo "$n made network attempts (or printed no count)" >&2; exit 1; }; }
$PY -c "import dipcast; from dipcast import config; from dipcast.model import transport
print(dipcast.__file__, config.RIVER_VELOCITY_MS, config.T90_HOURS, transport.DILUTION_POWER, config.LAKE_PATH_MODE)" > $L/which.log
step validate scripts/validate_ecoli.py
step replay scripts/replay_ecoli_leads.py
step face $H/score.py face $O
$PY -c "import json,sys; sys.exit(0 if json.load(open('$O/face.json'))['passes'] else 1)" \
  || { echo "face check fails: stopped before any score" >&2; exit 1; }
step score $H/score.py score $O
echo done
