#!/bin/zsh
# run.sh <frozen root> <soil dir> <out dir>   (docs/SONDE-SIGNAL-TEST-2026-10.md)   NOT RUN until Ethan approves.
# From a git archive of the harness commit. <frozen root> is the soil-moisture rivers test's root (DIPCAST_ROOT with
# the rows file, the exposures, the rain caches and ecoli_model_sm.json); <soil dir> its `sm` cache. One step at a
# time, under the group's heavy-run lock if one is in use:
#   1. fetch.py stations     2 requests: the station listings, frozen in <out dir>/net
#   2. prep.py + relate.py   offline: candidates, deployments, rule 3 (the river network from the root)
#   3. pre-gate              offline: if the covered upper bound (rule 3 applied) is under the gate, stop here:
#                            no readings are fetched
#   4. fetch.py readings     at most fetch.CAP requests in all, one in flight, 1.5 s apart
#   5. score.py              offline (lake_distance_eval/run_offline.py refuses every connection)
H=${0:A:h}
W=${0:A:h:h:h}
R=${1:?frozen root}
S=${2:?soil dir}
O=${3:?out dir}
PY=(${=PYTHON:-uv run --offline python})
OFF=$W/scripts/lake_distance_eval/run_offline.py
mkdir -p $O/net $O/readings $O/logs
export DIPCAST_ROOT=$R DIPCAST_STATE=$R/data/processed DIPCAST_CACHE=$R/data/cache
export PYTHONPATH=$W/src:$W/scripts:$H${PYTHONPATH:+:$PYTHONPATH}
cd $W
$PY $H/fetch.py stations $O/net > $O/logs/stations.log 2>&1 || { echo "station fetch failed" >&2; exit 1; }
$PY $OFF $H/prep.py $O/net/stations_turbidity.json $O/net/stations_ammonium.json $O/cand.csv $O/prep.json \
  $R/data/processed/ecoli_validation_rows.parquet > $O/logs/prep.log 2>&1 || { echo "prep failed" >&2; exit 1; }
$PY $OFF $H/relate.py $R/data/processed/river_network.pkl $O/cand.csv $O/matched.csv > $O/logs/relate.log 2>&1 \
  || { echo "relate failed" >&2; exit 1; }
$PY -c "
import csv, collections, sys
sys.path.insert(0, '$H'); from score import GATE_N, GATE_SITES
best = collections.defaultdict(int)
for r in csv.DictReader(open('$O/matched.csv')):
    if r['property'] == 'turbidity' and r['network_ok'] == 'True':
        best[r['bw_id']] = max(best[r['bw_id']], int(r['samples_covered'] or 0))
n, k = sum(best.values()), sum(v > 0 for v in best.values())
print('pre-gate upper bound', n, 'rows at', k, 'sites')
sys.exit(0 if n >= GATE_N and k >= GATE_SITES else 3)" > $O/logs/pregate.log 2>&1 \
  || { echo "pre-gate fails: stopped before any readings fetch" >&2; cat $O/logs/pregate.log; exit 3; }
$PY $H/fetch.py readings $O/matched.csv $O/readings > $O/logs/readings.log 2>&1 || { echo "readings fetch failed" >&2; exit 1; }
$PY $OFF $H/score.py $S $O/matched.csv $O/readings $O > $O/logs/score.log 2>&1 || { echo "score failed" >&2; exit 1; }
grep -o 'network attempts: [0-9]*' $O/logs/score.log | tail -1
echo done
