#!/bin/zsh
# run.sh <fetch dir> <main data dir> <per-overflow radar dir> <out dir> [build|score|all]
# (docs/COASTAL-BASELINES-2026-11.md). A scratch DIPCAST_ROOT under <out dir>/root holds a link to the river network
# and a copy of data/raw/network_fixes.csv; nothing is written to the main data dir or the radar folder, and both are
# fingerprinted before and after. The score reads only <out dir>/features.parquet.
H=${0:A:h}; W=${0:A:h:h:h}
PY=(${=PYTHON:-uv run --offline python})
F=${1:?fetch dir}; M=${2:?main data dir}; R=${3:?per-overflow radar dir}; O=${4:?out dir}; WHAT=${5:-all}
F=${F:A}; M=${M:A}; R=${R:A}; mkdir -p $O; O=${O:A}
cd $W
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
if [[ $WHAT != score ]]; then
  zsh $H/fingerprint.sh $M $R $O/fingerprint_before.txt
  mkdir -p $O/root/data/raw $O/root/data/processed $O/state
  cp -p $W/data/raw/network_fixes.csv $O/root/data/raw/
  ln -sf $M/processed/river_network.pkl $O/root/data/processed/river_network.pkl
  DIPCAST_ROOT=$O/root DIPCAST_STATE=$O/state DIPCAST_CACHE=$O/state/cache \
    $PY $H/build.py $F $M $R $O > $O/build.log 2>&1 || { echo "build failed: $O/build.log" >&2; exit 1 }
  zsh $H/fingerprint.sh $M $R $O/fingerprint_after.txt
  cmp -s $O/fingerprint_before.txt $O/fingerprint_after.txt && echo "inputs unchanged" >> $O/build.log \
    || { echo "INPUTS CHANGED" >> $O/build.log; echo "shared inputs changed during the build" >&2 }
fi
if [[ $WHAT != build ]]; then
  $PY $H/score.py $O/features.parquet $O > $O/score.log 2>&1 || { echo "score failed: $O/score.log" >&2; exit 1 }
fi
