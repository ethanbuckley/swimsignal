#!/bin/zsh
# queue.sh <data dir> <residence files dir>: every run of docs/LAKE-RESIDENCE-TEST-2026-10.md, one at a time, then
# the paired comparison, the summary and the judge. A finished run (logs/<name>/done) is not run again. Before each
# run it waits until free plus inactive memory is at least 5 GB (other work shares the machine).
H=${0:A:h}
M=${1:?data dir}; T=${2:?residence files dir}
S=${DIAG_DIR:?set DIAG_DIR}
PY=(${=PYTHON:-uv run --offline python})
free_gb() { vm_stat | awk '/Pages free/{f=$3} /Pages inactive/{i=$3} END{printf "%d", (f+i)*16384/1e9}'; }
MODE=${MODE:-residence}   # residence_spill for docs/LAKE-RESIDENCE-SPILL-2026-10.md; the candidate run is still "res"
jobs=("lake lake" "res $MODE $T/res.csv")
for k in {01..20}; do jobs+=("ph$k $MODE $T/ph$k.csv"); done
for job in $jobs; do
  set -- ${=job}
  [[ -f $S/logs/$1/done ]] && continue
  while (( $(free_gb) < 5 )); do echo "$(date +%T) waiting for memory ($(free_gb) GB)"; sleep 60; done
  echo "$(date +%T) start $1 ($(free_gb) GB free+inactive)"
  zsh $H/run_variant.sh $1 $2 $M $3 || { echo "$(date +%T) $1 FAILED"; exit 1; }
  echo "$(date +%T) end $1"
done
$PY $H/paired.py compare lake res > /dev/null
$PY $H/summary.py > /dev/null && $PY $H/judge.py
echo "$(date +%T) ALL DONE"
