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

## The run (31 October 2026)

- **Code and rule:** commit `ceb22bd0`. Command:
  `DIPCAST_ROOT=<main checkout> uv run python scripts/spill_duration_replay.py run --poll-log <poll_log.parquet> --out <scratch>`.
- **Polls:** `poll_log.parquet` from the state release, 31 Oct 09:15 UTC, SHA-256 `78aa8a2f…`. 399 real polls from
  28 Sep. The laid timetable has 9,850 polls, with median gap 0.82 h and 95th percentile 6.05 h; the real figures are
  1.00 h and 6.24 h. South West Water's feed is stale in 24% of polls, Southern's in 5%.
- **Cost:** 12.4 minutes wall time; 70 CPU-minutes (3,333 s user, 884 s system); 3.9 GB peak memory. That is a little
  over the one CPU-hour budget.
- **Inputs:** fingerprinted before and after, unchanged (events, annual returns, poll log, rain cache listing).
- **Data:** no 2026 event read; no Open-Meteo call.
- **Outputs:** `docs/SPILL-DURATION-REPLAY-2026-11-scores.csv`, `-reliability.csv`, `-summary.json`.

### What the replay changes

- **Rows:** 3,794,322 rows from 323,767 spills. #461 had 4,038,032 rows where an EA event was running.
- **The spill had already stopped in 734,825 rows (19.4%).** The last poll saw a discharge, but the spill had ended by
  the issue hour, because of the poll gap or the feed's age. The live site shows these hours as discharging today.
- **Elapsed time is at least an hour short of the spill's own in 625,980 rows (16.5%).** A pause across a poll breaks
  the run the site can see.
- These rows make every forecast harder. B1's integrated Brier is 0.195 here, against 0.171 on #459's 2025 rows.

### Scores, all nine companies (out of fold, 2024-25)

| Model | Integrated Brier | vs B1 | 95% interval | Against the label the polls would see |
|---|---|---|---|---|
| B1 company × elapsed | 0.1954 | | | 0.1921 |
| C1 raw | 0.1662 | −0.0292 (−14.9%) | −0.0319 to −0.0266 | 0.1854 |
| **C1-cal** | **0.1652** | **−0.0302 (−15.5%)** | **−0.0319 to −0.0286** | **0.1750** |
| Stops now (the site today) | 0.5427 | +0.3473 | | 0.6706 |
| Keeps running | 0.4573 | +0.2619 | | 0.3294 |

On the 3,059,497 rows where the spill was still running at the issue hour, C1-cal scores 0.1598 against B1's 0.1825
(12.4% better). #459's out-of-sample figure on 2025 was 11.6%.

**Decision rule:** met.
- Gain: 15.5% of B1, against the required 5.8%, with the interval below zero.
- Calibration: ECE at most 0.02 in 44 of 45 company-horizon cells, against the required 23. C1 raw manages 6.

### Company and horizon

C1-cal is better than B1 at every company, and every interval is below zero:

| Company | Gain vs B1 |
|---|---|
| Anglian | 11.9% |
| Yorkshire | 13.4% |
| South West | 14.1% |
| Severn Trent | 14.6% |
| United Utilities | 15.8% |
| Thames | 15.9% |
| Northumbrian | 16.0% |
| Wessex | 19.7% |
| Southern | 19.9% |

By horizon, the gain is smallest at 1 h (−0.025) and 24 h (−0.025), and largest at 6 h and 12 h (−0.035). Every
horizon's interval is below zero.

### Calibration

- **Raw C1 under-forecasts persistence at every company.** Its forecasts are 1 to 7 points too low, and worst at
  24 h (Anglian −0.067, Wessex −0.065). This is #461's out-of-fold finding again.
- **Nested isotonic calibration removes most of it.** The one cell above 0.02 is Southern at 24 h (ECE 0.023;
  forecast 0.023 below the observed share). Thames at 24 h is next (0.019; −0.017).
- **B1 is also well calibrated** (ECE at most 0.02 in 44 of 45 cells; the worst is Southern at 12 h, 0.030). So
  calibration brings C1 level with B1. It does not make C1 better calibrated than B1. The gain is in sharpness.

### Failure cases

- **Spills that have already stopped** (the 19.4% above). C1-cal scores 0.188 there, B1 0.249. Every model that
  forecasts "still running" is wrong on these rows. Only the poll timing can fix them, not the model.
- **New spills under the label the polls would see** (elapsed under 3 h):
  - C1 raw is slightly worse than B1 (0.2294 against 0.2270);
  - C1-cal is better (0.2140).
- **Long horizons at Southern and Thames.** C1-cal still under-forecasts at 24 h. A shadow should not use 24 h.
- **Unknown labels.** The label the polls would see is unknown in 0.9% of rows at 1 h and 6.4% at 24 h (stale feeds
  or unknown status).

### Limits

- **Seen data.** All of 2024-25 has been looked at, and this is development. The 2025 test (#459) stands as the only
  out-of-sample result. #461's gate verdict stands too.
- **Polls.** The timetable is 33 autumn days of real polls, laid over two years. Per-overflow unknown status is drawn
  independently at each poll. Real outages last for days, which this does not copy.
- **Models.** They are fitted on 10% of their training rows (seeded), to fit the budget. #459 fitted on all of them.
- **One input uses the spill's true start.** "Hours spilled in the 7 days before the spill began" counts back from
  that start. The site knows the start only as far as its polls show.
- **Rain.** ERA5-Land, as #459 used. The live site's past rain comes from its own forecast source, so a shadow will
  see a shift this replay cannot.
- **A spill's end is not the water clearing.** These forecasts say whether an overflow is still discharging, nothing
  about the water downstream.

## The shadow statement (proposed, not logging)

The rule says to write this. It is a statement only. No logger is built and no shown value changes. Building the
logger is the next decision.

- **Log:** a separate versioned table, `shadow_duration_v1`, like `shadow_regional_v1`. One row per overflow the
  build shows discharging (fresh poll, known status). Each row holds:
  - elapsed time from the site's own poll history (`live_history`, the chain rule above);
  - C1-cal's and B1's chance the overflow is still discharging 3 h and 6 h later.
- **Models:** C1, and B1, fitted on every replayed 2024-25 row. The calibrators are refitted on all six folds'
  out-of-fold forecasts. Both are saved with their hashes before the window opens.
- **Score:** against SwimSignal's own polls. The label is whether the latest fresh poll at or after t + h saw a
  discharge. A row whose label is stale or unknown is not scored, and is counted.
- **Window:** 28 days from the first logged build, read the day after it ends.
- **Margin, set now:**
  - C1-cal's mean Brier over 3 h and 6 h at least 5% below B1's, with a day-block bootstrap interval below zero;
  - ECE at most 0.03 at 3 h and at 6 h across all companies;
  - no company with at least 2,000 scored rows worse than B1 by more than 5%;
  - at least 5,000 scored overflow-hours, or the window extends once to 56 days.
- **United Utilities:** scored and reported, but outside the company guardrail. #461 found its 2026 recording changed.
- **If it passes:** a dated sentence beside the clearing time may be proposed. Task 3b's wording evidence still
  applies (`docs/CLEAR-TIME-WORDING-2026-11.md`).
- **If it fails:** the dated description stays the product.
