#!/bin/zsh
# queue.sh <data dir> <size table dir>: every run of docs/PE-SIZE-TEST-2026-10.md, one at a time, then the
# paired comparisons and the judge. A finished run (logs/<name>/done) is not run again.
H=${0:A:h}
M=${1:?data dir}; T=${2:?size table dir}
S=${DIAG_DIR:?set DIAG_DIR}
PY=(${=PYTHON:-uv run --offline python})
jobs=("length length" "flow flow" "dwf urban $T/dwf.parquet")
for k in {01..20}; do jobs+=("pd$k urban $T/pd$k.parquet"); done
for job in $jobs; do
  set -- ${=job}
  [[ -f $S/logs/$1/done ]] && continue
  echo "$(date +%T) start $1"
  zsh $H/run_variant.sh $1 $2 $M $3 || { echo "$(date +%T) $1 FAILED"; exit 1; }
  echo "$(date +%T) end $1"
done
$PY $H/paired.py compare length dwf > /dev/null && $PY $H/paired.py compare flow dwf > /dev/null
$PY $H/summary.py > /dev/null && $PY $H/common.py > /dev/null && $PY $H/judge.py
echo "$(date +%T) ALL DONE"
