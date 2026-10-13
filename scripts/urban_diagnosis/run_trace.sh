#!/bin/zsh
# run_trace.sh: trace.py in $DIAG_DIR/roots/urban (the real table; run_variant.sh urban urban first),
# network refused; then decomp.py (H3a, H3b).
H=${0:A:h}
W=${0:A:h:h:h}
M=${DIPCAST_MAIN_DATA:-$W/data}
S=${DIAG_DIR:?set DIAG_DIR to a scratch folder}
export DIPCAST_ROOT=$S/roots/urban DIPCAST_STATE=$S/roots/urban/data/processed
export DIPCAST_CACHE=$M/cache
export DIPCAST_VELOCITY_MODE=fixed DIPCAST_DILUTION_MODE=urban
cd $W
uv run --offline python $H/run_offline.py $H/trace.py > $S/trace.log 2>&1
tail -2 $S/trace.log
uv run --offline python $H/decomp.py > $S/decomp.log 2>&1
tail -1 $S/decomp.log
