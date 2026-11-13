#!/bin/zsh
# fingerprint.sh <data dir> <out file>: SHA-256 of every shared input the test reads, one line per file or folder, so
# the lists taken before and after the run can be compared (docs/RADAR-ISSUE-HOUR-TEST-2026-11.md).
M=${1:?data dir}; O=${2:?out file}
{
  (cd $M/processed && shasum -a 256 annual_returns.parquet ea_events_*.parquet api_events_thames_water.parquet spill_model.pkl)
  (cd $M/raw/met_office_radar && ls | grep -E '_(2024-12|2025-[0-9]{2}|2026-0[1-8])\.parquet$' | sort | xargs shasum -a 256 \
     | shasum -a 256 | sed 's/-$/cell radar files, Dec 2024 to Aug 2026/')
  (cd $M/cache && ls rain/*_202[456]*.parquet rain_nine/*_202[456]*.parquet | sort | xargs shasum -a 256 \
     | shasum -a 256 | sed 's/-$/rain caches 2024-2026/')
} > $O
