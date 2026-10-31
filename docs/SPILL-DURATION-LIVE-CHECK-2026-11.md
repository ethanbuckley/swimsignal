# Spill duration: the frozen table against "stops now", on the site's own polls

Register row **4 / DURATION**, issue #476. Ethan chose this cheaper offline check over a live C1 logger (31 Oct 2026).
It is an **offline held-out check, not prospective evidence**: the table was fitted on 2024-25 before any 2026
outcome was scored, but the comparison runs on data that already exists. It changes no public forecast. The
studies in progress, #459, #461 and the replay (#539) are untouched.

## Inputs, inspected before the plan

- **`live_history.parquet`** (state release, 31 Oct): 103,319 rows, 11 Sep to 31 Oct 2026. It is an event log, not an
  observation log: one row per overflow, status and status start, holding the **last** poll that saw it. That gives
  16,289 discharge rows, 93% with the status start equal to the latest event start. 275 discharge rows have no start.
- **`live_coverage.parquet`:** per overflow and local day, the half-hours with a known, current reading. A company's
  feed with no age counts as stale there (South West Water before 4 Oct).
- **`poll_log.parquet`:** 474 polls, 16 Sep to 31 Oct, with feed ages from 28 Sep 16:51 UTC. One caveat: the replay
  laid this poll timetable (its gaps and feed ages) over 2024-25. So the table's elapsed times depend on the window's
  poll timing, but not on any of its outcomes.

## Frozen before scoring

- **B1:** `docs/SPILL-DURATION-LIVE-CHECK-2026-11-b1.csv`, SHA-256 `d8c97292d0dacedfd20d5eafe91863b9dd2b9c2e8c6dfad167eb739c00e61c52`.
  It holds the share still running 1, 3, 6, 12 and 24 h later, by company and elapsed bin, from every one of the
  3,794,322 replayed 2024-25 rows. A company row (`ebin` −1) fills an empty bin. Made by
  `scripts/spill_duration_live_check.py freeze`.
- **Window:** issue hours from 28 Sep 2026 17:00 UTC to the last poll in the 31 Oct state release.
- **Issue rows:** one per overflow and whole UTC hour. It is the first poll in that hour at which the overflow had a
  current known reading and its latest history row (start at or before the poll) was a discharge still seen at or after
  it. Elapsed time is the poll time less the feed's discharge start, under 72 h.
- **Primary outcome, poll-observed:** at the company's last poll at or before t + h, the same discharge (same start)
  still running. The row is censored, not scored, when that poll is not after t, is more than 2 h before t + h, or the
  overflow had no current known reading then.
- **Reported, not primary: the feed-reported end.** The start of the overflow's next history row, or the row's own
  event end, after t + h. A discharge the feed never closed, and that was last seen before t + h, is censored. Neither
  outcome is the EA's own record of the spill's end.
- **Compared:** B1 against "stops now" (0, what the site assumes today). "Keeps running" (1) is a reference. Brier
  score, per company and for all nine; the primary figure is the mean over 3 h and 6 h, on rows scored at both. A
  day-block bootstrap gives the interval of B1 minus stops-now. B1's mean forecast against the observed share, and
  its ECE, are reported per company and horizon.
- **What the result decides (a direction, not an adoption):**
  - B1 beats stops-now with the interval below zero at all nine companies, and its mean forecast at 3 h and 6 h is
    within 0.10 of the poll-observed share at seven or more: propose a release route for a dated, observational
    still-running figure beside the clearing time (section "Release route", written after the scores).
  - Otherwise: the table stays a research observation, and the record says which companies or horizons failed.

## The scores (31 October 2026)

- **Plan:** committed as `1fc98634` before scoring.
- **Command:** `uv run python scripts/spill_duration_live_check.py score --state <state release copy> --out <scratch>`.
- **Run:** 4 seconds; no request made.
- **Inputs:** state release of 31 Oct, last poll 11:32 UTC. SHA-256 `0109c0da…` (history), `f66cb3b8…` (coverage),
  `f1491ef0…` (poll log). Unchanged by the run.
- **Outputs:** `docs/SPILL-DURATION-LIVE-CHECK-2026-11-scores.csv` and `-summary.json`.

### Coverage

28,323 issue rows: 4,482 overflows, 11,719 discharges, median elapsed 2.9 h.

| Company | Issue rows |
|---|---|
| United Utilities | 8,579 |
| South West | 5,409 |
| Yorkshire | 3,574 |
| Southern | 2,805 |
| Severn Trent | 2,378 |
| Wessex | 2,041 |
| Northumbrian | 1,569 |
| Anglian | 1,372 |
| Thames | 596 |

The poll-observed outcome is censored in about half the rows, almost all because no poll fell within 2 h before
t + h.

| Horizon | Scored | No fresh poll | Reading not current |
|---|---|---|---|
| 1 h | 12,739 | 15,568 | 16 |
| 3 h | 15,332 | 12,911 | 80 |
| 6 h | 14,461 | 13,769 | 93 |
| 12 h | 9,031 | 19,169 | 123 |
| 24 h | 14,662 | 13,413 | 248 |

Poll timing does not depend on whether an overflow is spilling, so this mainly costs rows. It is not shown here to
leave the comparison unbiased.

The feed-reported end is censored in at most 128 rows.

### Primary: mean Brier over 3 h and 6 h, poll-observed

| Company | Rows scored | Still running | B1 forecast | B1 | Stops now | B1 − stops now (95% interval) |
|---|---|---|---|---|---|---|
| Anglian | 326 | 0.460 | 0.467 | 0.209 | 0.460 | −0.251 (−0.368 to −0.057) |
| Northumbrian | 163 | 0.362 | 0.345 | 0.195 | 0.362 | −0.167 (−0.318 to −0.069) |
| Severn Trent | 861 | 0.464 | 0.419 | 0.223 | 0.464 | −0.241 (−0.430 to −0.212) |
| South West | 1,749 | 0.618 | 0.539 | 0.197 | 0.618 | −0.421 (−0.492 to −0.288) |
| Southern | 833 | 0.610 | 0.498 | 0.234 | 0.610 | −0.376 (−0.458 to −0.219) |
| Thames | 124 | 0.492 | 0.486 | 0.223 | 0.492 | −0.269 (−0.351 to −0.128) |
| United Utilities | 2,858 | 0.496 | 0.381 | 0.231 | 0.496 | −0.265 (−0.365 to −0.116) |
| **Wessex** | 695 | 0.512 | 0.537 | 0.238 | 0.512 | −0.273 (**−0.323 to +0.108**) |
| Yorkshire | 1,235 | 0.360 | 0.310 | 0.195 | 0.360 | −0.164 (−0.348 to −0.108) |
| **All nine** | 8,844 | 0.506 | 0.433 | 0.218 | 0.506 | −0.288 (−0.370 to −0.181) |

Against the feed-reported end, B1 beats stops-now at all nine companies with the interval below zero (all nine:
0.204 against 0.472). Wessex's interval there is −0.235 to −0.093.

### By horizon (all nine, poll-observed)

| Horizon | Still running | B1 forecast | B1 ECE |
|---|---|---|---|
| 1 h | 0.826 | 0.639 | 0.188 |
| 3 h | 0.585 | 0.508 | 0.077 |
| 6 h | 0.402 | 0.400 | 0.017 |
| 12 h | 0.230 | 0.306 | 0.087 |
| 24 h | 0.110 | 0.185 | 0.081 |

- **The table's curve is too flat for autumn 2026.** It forecasts too low at 1 h, at every company (the share still
  running is 0.72-0.92, the forecasts 0.52-0.74). It forecasts too high at 12 h and 24 h.
- **B1 beats stops-now at 1 h, 3 h and 6 h** at every company except Wessex at 6 h.
- **At 12 h and 24 h several companies' intervals cross zero.** There is less to gain there, because most discharges
  have stopped.
- **B1 also beats a constant set to the observed share,** which is a stronger reference than "stops now". At 3 h it
  scores 0.221 against 0.243, and at 6 h 0.203 against 0.240. So elapsed time and company carry information. They
  are not just the base rate.

### Against the plan

1. **"B1 beats stops-now with the interval below zero at all nine companies":** not met. Eight of nine pass. Wessex's
   interval crosses zero: it has 695 rows, and B1 forecasts too high there at 6 h (0.493 against 0.362).
2. **"Mean forecast within 0.10 of the poll-observed share at 3 h and 6 h at seven or more":** met horizon by horizon
   (7 companies at 3 h, 8 at 6 h). Only 6 companies are within 0.10 at both horizons. The plan did not say which it
   meant, so both are reported. The outcome is the same under either reading, because condition 1 fails.

**So, as the plan said: the table stays a research observation.** Wessex at 3 h and 6 h, and the 1 h, 12 h and 24 h
calibration, are what failed. This is a held-out check on existing data, not prospective evidence. One month of
autumn polls, with about half the outcomes censored, is a small window.

## Limits

- **One autumn month.** About 28 days of issue hours, all in autumn, and wet: 51% still running at 3 h and 6 h
  (poll-observed).
- **Two definitions of elapsed time.** The table was fitted with elapsed time from the replay's chain of polls over
  EA events. Here it is the feed's own discharge start. The flat curve at 1 h may come partly from that difference,
  not from the season.
- **A reconstruction.** Status at a poll is rebuilt from an event log that keeps only the last poll seeing each row. A
  discharge whose status changed and changed back between polls is missed.
- **Neither outcome is the EA's record of when the spill ended.** The EA's 2026 files are not used, so the January to
  August 2026 outcomes stay unread.
- **"Stops now" is not meant as a probability.** It is the clearing time's assumption. Beating it shows how much that
  assumption costs. It does not show that B1 is good enough to publish.

## Release route (proposed)

Nothing here changes the public forecast. The route, in order:

1. **Now, with no forecast involved:** a dated, measured line beside the clearing time, from the site's own polls. For
   example: "In October 2026, about 6 in 10 discharges this site saw were still running 3 hours later." It is
   an observation of the past, like the published still-running curves at `/durations.html`, with the date and the
   source said. This is a product decision, and task 3b's wording evidence applies (`docs/CLEAR-TIME-WORDING-2026-11.md`).
   It is offered to the product owner, not built here.
2. **1 December 2026: the same check, unchanged, on November's polls.** The frozen table (`d8c97292…`), the same rules
   and the same script take about 4 seconds on the state release. This is a second held-out window, still not
   prospective.
3. **Fix the elapsed-time mismatch before any forecast is shown.** Refit the table with elapsed time measured as the
   live site measures it, from the feed's discharge start. The source would be the poller's own history once it holds
   three months (from 28 Sep: about **28 Dec 2026**). Then freeze it and judge it on the following month, with the
   rules above. If it passes at all nine companies, a company × elapsed "often still running" figure could go to the
   product owner with task 3b's wording. If it fails, the dated line in step 1 stays the product.
4. **C1 (the model with rain) stays parked.** It is worth reconsidering only if step 3's table earns a place on the
   page.
