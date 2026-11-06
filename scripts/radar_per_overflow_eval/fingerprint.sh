#!/bin/zsh
# fingerprint.sh <data dir> <per-overflow radar dir> <out file>: SHA-256 of every shared input the test reads, one
# line per file, so the lists taken before and after the run can be compared (docs/RADAR-PER-OVERFLOW-TEST-2026-11.md).
M=${1:?data dir}; R=${2:?per-overflow radar dir}; O=${3:?out file}
{
  (cd $M/processed && shasum -a 256 annual_returns.parquet ea_events_*.parquet api_events_thames_water.parquet \
     overflow_urban_area.parquet spill_model.pkl)
  (cd $M/raw/met_office_radar && ls | sort | xargs shasum -a 256 | shasum -a 256 | sed 's/-$/cell radar dir/')
  (cd $M/cache && ls rain/*_202[456]*.parquet rain_nine/*_202[456]*.parquet | sort | xargs shasum -a 256 \
     | shasum -a 256 | sed 's/-$/rain caches 2024-2026/')
  (cd $R/data/overflows && ls | sort | xargs shasum -a 256 | shasum -a 256 | sed 's/-$/per-overflow radar files/')
  (cd $R && shasum -a 256 overflows_b5724303.parquet)
} > $O
