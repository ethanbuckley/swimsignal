#!/bin/zsh
# fingerprint.sh <main data dir> <per-overflow radar dir> <out file>   (docs/COASTAL-BASELINES-2026-11.md, section 1)
# Size and SHA-256 of each shared file this work reads, and for the radar folder its file count, total bytes and a
# hash of the listing (name and size). Run before and after a build: the two files must be identical.
M=${1:?main data dir}; R=${2:?per-overflow radar dir}; O=${3:?out file}
{
  for f in $M/processed/overflows.parquet $M/processed/river_network.pkl $M/processed/dcww_ea_events.parquet $M/processed/ea_events_*.parquet; do
    print -r -- "${f:t} $(stat -f %z $f) $(shasum -a 256 $f | cut -d' ' -f1)"
  done
  n=$(ls $R | grep -c '^radar_overflows_.*\.parquet$')
  b=$(stat -f %z $R/radar_overflows_*.parquet | awk '{s+=$1} END {print s}')
  l=$(for f in $R/radar_overflows_*.parquet; do print -r -- "${f:t} $(stat -f %z $f)"; done | shasum -a 256 | cut -d' ' -f1)
  print -r -- "radar_overflows files=$n bytes=$b listing_sha256=$l"
} > $O
