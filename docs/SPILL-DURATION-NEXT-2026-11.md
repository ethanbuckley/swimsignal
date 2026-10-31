# Spill duration: the next development package (draft)

Written 30 October 2026, register row **4 / DURATION**, under `docs/RESEARCH-WORKFLOW.md`. **Draft for review**;
nothing here reruns #461's gate or reads the January-August 2026 durations.

## Continuation record

| Field | Content |
|---|---|
| Identity | DURATION; owner: Claude session "SwimSignal pollution event lifecycle"; this PR; code `scripts/spill_duration_test.py`, `scripts/spill_duration_calibration_test.py`, `scripts/export_spill_durations.py` |
| Evidence | #459: C1 11.6% better than the company × elapsed table (B1) on 2025, probabilities unreliable at five companies. #461: 6.9% of rows in joined pauses, gain holds on rows a monitor would show (11.7%); the calibration test stopped at its gate (0.027 against 0.03); out of fold C1 under-forecasts persistence everywhere. All of 2024-25 is seen; Jan-Aug 2026 durations unread |
| Stage and claim | **Observations shipped now** (`docs/SPILL-DURATIONS-CONTRACT-v1.md`: per-overflow spill lengths and company still-running curves, 2024-25). Forecast: development only, no claim |
| Next deliverable | (1) The observation file on the site (product owner). (2) The replay and calibration package below, then a live shadow of the chance a running spill continues |
| Milestone and budget | Replay and development run by **20 November 2026**, offline, cached data only, about 1 hour of CPU. Shadow statement before any live logging |
| Release route | A calibrated "often still running" sentence beside the clearing time needs the shadow to pass and task 3b's wording evidence; until then the dated description in the observation file is what may be shown |

## Saved fits (inventory, 30 October 2026)

In the main checkout's `data/processed/spill_duration/` (not committed):
- `calibration_fits.pkl` (SHA-256 `79ebf550…`): the final C1 fitted on 2024-25 running rows, its 45 isotonic
  calibrators and B1; made by #461's gate step; never used on 2026.
- `predictions_2025.parquet` (`86ff3447…`): C1 and B1 2025 predictions with labels, from #461's diagnostics.
The 2024-25 out-of-fold forecasts were not saved; they can be regenerated exactly (fixed seeds, row hash in
`docs/SPILL-DURATION-CALIBRATION-TEST-2026-11-gate.json`).

## The package

1. **What the live site can know.** Replay polls over the 2024-25 EA events at the poller's real timetable
   (gaps drawn from `poll_log.parquet` in the state release, median 1.05 h, 95th percentile 6.4 h), with the feed
   fields a poll carries (status, latest event start and end). Elapsed time is what those polls imply; a status that
   is stale over 8 hours is unknown, never "stopped". This replaces the EA-event elapsed time of #459 with the one
   production would have.
2. **Folds that do not leak.** Month blocks over 2024-25 with a 48-hour embargo either side of each held-out block,
   and every spill wholly inside one block (a spill crossing a boundary is assigned to the block it began in and
   its rows leave the others). #461 found 2.0% of rows in spills split across quarters; this removes them.
3. **Calibration judged directly.** C1 with isotonic calibration per company and horizon, fitted inside each
   training fold on that fold's own inner out-of-fold forecasts; compared with B1 on the replayed rows by Brier,
   ECE and reliability at each company and horizon. No symptom gate decides whether this comparison runs.
4. **What decides the next step** (development, seen data, so a direction rather than a verdict): if calibrated C1
   keeps most of its Brier gain over B1 with ECE at most 0.02 at most company-horizon cells, write the shadow
   statement; if not, the dated description stays the product and the record says why.

## The shadow, once written

A separate versioned log (like `shadow_regional_v1`), the chance a running spill is still running 3 and 6 hours
later for every overflow discharging at build time, scored against SwimSignal's own polls over a stated window,
with its margin set before it opens. No change to any shown value.
