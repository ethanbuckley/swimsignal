# Spill duration: poll replay, leak-free folds and nested calibration

Register row **4 / DURATION**, issue #476. This runs the package in `docs/SPILL-DURATION-NEXT-2026-11.md`. It is
**development on seen data**: every 2024-25 row has been looked at by #459 and #461, so it gives a direction, not a
verdict. #459's and #461's verdicts stand. No 2026 event is read. No Open-Meteo call is made.

## Stated before the run (31 October 2026)

Method: `scripts/spill_duration_replay.py` (its docstring is the full statement).

- **Polls:** the real timetable from `poll_log.parquet` (from 28 Sep 2026, when feed ages were first recorded), laid
  over 2024-25 in random 24-hour blocks, seed 0. Each poll carries its companies' feed ages and unknown shares. A
  feed more than 8 hours old is unknown, never "stopped".
- **Rows:** whole hours at which the latest poll saw a discharge. Elapsed time comes from the site's own history: the
  earliest poll of the unbroken run that saw a discharge. The label is #459's: the spill still running h hours later.
- **Folds:** each spill belongs to the month it began in; six outer folds of four months (month mod 6); a 48-hour
  embargo around each held-out month; isotonic calibration per company and horizon, fitted on three inner folds.
  Models are fitted on a seeded 10% of their training rows, to keep to about one CPU-hour.
- **Compared with:** B1 (company × elapsed, refitted per fold), "stops now" (what the site assumes today) and
  "keeps running".
- **Decision:** write the shadow statement only if C1-cal both:
  - keeps an integrated Brier gain over B1 of at least 5.8% of B1's score (half of #459's 11.6%), with the interval
    below zero; and
  - has an ECE of at most 0.02 in at least 23 of the 45 company-horizon cells.

  Otherwise the dated description stays the product, and this record says which part failed.

## Results

To follow from the run.
