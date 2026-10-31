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
