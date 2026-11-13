# Radar to the issue hour, with live status already in: the test, stated before any score

Written 13 November 2026. No model has been fitted or scored for this test. Results go below the line at the end.
Nothing above it changes after a result is seen.

## Why

[#694](RADAR-ISSUE-HOUR-TEST-2026-11.md) found that a spill model refitted on cell radar up to the issue hour, with
forecast rain for the rest of the day, beats the same model form on forecast rain alone: 3.3% with a fresh forecast
for the rest of the day, 1.9% with a day-old one, on seen 2025 labels. The gain was small in the morning and large in
the evening (18 UTC: 5.9% and 5.3%).

#694 did not give the model the overflow's own live spill status. By evening an overflow that will count as a spill
day has often started, and the company's live feed shows it. The live-status candidate (#254, #262, #639) uses that
status, and Ethan decides on or after 23 November 2026 whether to switch it on. If status is switched on, a radar
shadow logger is only worth building if radar still adds something once status is in.

## The question

At a real issue time, with the overflow's live status as it stood then already in the model, does cell radar up to the
issue hour still make the same-day spill forecast better than forecast rain alone?

The "today" level only. Leads 1 to 4 are not touched.

## What is reused unchanged from #694

Everything not named under "What changes" below: the rows (3,778 overflows in 381 cells, 2025, `training.site_years`
for the nine English companies), the hourly radar and forecast rain, each radar hour's publish time from the bucket
listing, the eight issue hours (00, 03, 06, 09, 12, 15, 18, 21 UTC), the radar arms R0 and R1 and the forecast arms
P and F1, the fallback to forecast for late or missing radar hours, the day features, the model form (`SpillModel`,
`fit_pooled` seed 0 with dry days at 0.25, then `fit_site_offsets` prior 15, recency 1), the blocked two-fold
cross-fit with a 7-day embargo, the Brier score on raw out-of-fold probabilities, the two-way cluster bootstrap
(overflows and ISO weeks, 2,000 draws, seed 20261113), the 1% margin and the four verdicts. The code is #694's
`scripts/radar_issue_hour_eval/score.py`, imported and not edited. The new script adds only the status inputs and the
new arms.

The radar publish times are #694's own listing file (`radar_publish_times.csv`, made by
`scripts/radar_issue_hour_eval/latency.py` on 13 November 2026), copied from that session's scratch folder and
fingerprinted. No listing request is made.

## What changes: the live-status inputs, built as at the issue hour

#254's three inputs, from the EA start/stop events of both years with each overflow's overlapping events merged first
(`live_status_test.merged_intervals`). #254 took them at 00:00 UTC of the target day. Here the issue time is the issue
instant, the day's 00:00 UTC plus H hours, the same instant the radar arms use.

- `spilling_at_issue`: 1 if a merged event runs at the issue instant (start ≤ instant < stop), else 0.
- `spill_hours_24h`: hours spilled in the 24 hours before the issue instant. At H = 0 this is #254's input exactly.
- `spill_days_7d`: spill-days among the 7 days before the target day, by `features.spill_days`. As #254. It does not
  move with H.

**Why the 24-hour window ends at the issue instant, and not at midnight.** A build at 18 UTC knows the hours its
overflow has spilled since midnight. That is the information most likely to overlap with radar's evening gain, which
is the question. Ending the window at midnight would leave it out and flatter the radar.

**What this gives away, on purpose.** At H > 0, an overflow spilling at the issue instant, or one that spilled earlier
in the day, already has the label "spill day" for certain. A live build would know that too. Both sides of every
comparison get the same status, so this does not favour either. The split below reports those rows separately.

**When status is unknown.** #254's rule (`live_status_test.covered_years`): a day in year *y* is known if the overflow
has an event in year *y*'s file, or 0 spills in that year's return, and EDM operation not under 50%. The first two
inputs need the target day and the day before known; `spill_days_7d` needs days −7 and −1 known. Unknown is NaN, which
the model takes as it is. The count is reported.

**Monotone.** Each status input may only raise the probability, as in #254.

**Code check, before any label is joined.** At H = 0 the three inputs must equal #254's `Status.features(..., k=0)`
on every scored row. The run stops if they differ.

## The arms

Each arm gets its own fit, as in #694. Only the short-range rain source and whether the status inputs are present
change.

| Arm | Rain (as #694) | Status inputs |
|---|---|---|
| **PS@H** | P: lead 0 for every hour | as at H |
| **F1S@H** | F1@H: lead 0 to the issue instant, lead 1 after | as at H |
| **R0S@H** | R0@H: radar to the hour, lead 0 for the rest | as at H |
| **R1S@H** | R1@H: radar to the hour, lead 1 for the rest | as at H |
| P, F1@H, R0@H, R1@H | #694's arms, refitted in this run | none |

The arms without status are refitted here so that radar's gain with and without status comes from one run. #694 found
that a refit can move an arm's Brier by 0.0001 to 0.0002. #694's C and C-lag anchors, its one-model variant and its
no-refit check are not repeated: they do not bear on this question.

57 arms, 171 fits (two folds and one fit on all of 2025 each).

## The decision

**Two pooled differences decide**, each the mean over the eight issue hours of a row's Brier difference:
- **DS0** = mean over H of Brier(R0S@H) − Brier(PS@H). Radar to the hour with status, against status with the
  forecast alone, fresh forecast for the rest of the day.
- **DS1** = mean over H of Brier(R1S@H) − Brier(F1S@H). The same with a day-old forecast for the rest.

Skill is 1 − (mean Brier of the radar arms) / (mean Brier of the status-only arms).

**The margin: 1% of the comparator's Brier**, as #694. Status lowers the comparator's Brier, so the margin in absolute
terms is smaller than #694's 0.0004. It stays relative because the cost it stands for (fetching radar at every build,
a fitted model that takes it) is the same.

**The verdict, #694's four, unchanged:**
- **W. Worse** if either DS0 or DS1 has a 95% interval (overflow × week) wholly above zero.
- **H. Radar still helps** if DS0 and DS1 both have intervals wholly below zero and both skills are at least 1%.
- **S. A small or partial gain** if at least one interval is wholly below zero, but H does not hold.
- **N. Not shown** if both intervals include zero. The record says whether each also rules out a 1% gain.

An interval that includes zero shows neither a gain nor "no worse".

## Reported whatever the verdict

- Brier, AUC and the share of spill days and of dry days at probability 0.4 or more, for every arm.
- **By issue hour**, with intervals: R0S − PS and R1S − F1S, and beside them #694's R0 − P and R1 − F1 from this run.
- **Rows spilling at the issue instant, and the rest**, for DS0 and DS1: by issue hour, and pooled over every
  (row, hour) pair, each pair weighted the same. The same draws as the main intervals.
- **How much of radar's gain survives:** DS0 against this run's D0 (R0 − P), DS1 against D1 (R1 − F1), pooled and by
  hour.
- **What status adds** in this run: PS − P, and R0S − R0 (status on top of radar), pooled and by hour.
- DS0 and DS1 by company and by season, with no decision. United Utilities named, given #695.
- How many rows have unknown status, by input.
- This run's D0 and D1 against #694's (0.03567 − 0.03690 and 0.03860 − 0.03933), as a check of the refit.

## The 2026 forward check (secondary)

As #694. Each arm's model fitted on all of 2025 is frozen and scored on Thames Water's overflows, 1 January to
31 August 2026, labelled by Thames Water's alert-stream events (`api_events_thames_water.parquet`). Status for these
rows comes from the same stream file, merged the same way, and is known for every overflow in it (the file starts in
April 2022). So status and label come from one source here, as they would in a live build that reads the feed. One
company, eight months. It decides nothing on its own. Same figures as above, where the rows allow.

## Data, isolation and windows

- Read-only shared inputs, fingerprinted (SHA-256) before and after: #694's list (cell radar files, rain caches,
  processed files, `spill_model.pkl`) plus the radar publish-times CSV. The two lists must match.
- No network request: the run goes through `scripts/lake_distance_eval/run_offline.py`, which refuses every outgoing
  connection and counts attempts. The count must be 0. No Open-Meteo call.
- A `git archive` of the commit that adds the test code; scratch `DIPCAST_ROOT` and `DIPCAST_STATE` holding copies of
  the processed files read; `DIPCAST_CACHE` pointed at the shared cache, read-only; outputs in this session's scratch
  folder.
- No active evaluation window is read. Labels: EA 2025 files, and Thames's stream to 31 August 2026 only, as #694 and
  #640. The open windows (lead calibration B, ensemble rain, live-status shadow, A8, regional routing, combined-v1
  shadow, upgraded overflows) all start after 31 August 2026.

## Compute caps

- At most 4 threads. Stop if the run passes 120 minutes or 12 GB peak memory. #694 ran 81 fits in 23 minutes at
  2.3 GB; this is 171, so about 50 minutes is expected.
- A plumbing run first on 300 overflows with random labels, which prints no score.
- One scored run. If it fails for a code fault, the fault and the fix are recorded below the line and the run is
  repeated once. It is not repeated for any other reason.

## What is expected, stated now

S or N. By the evening the status already says what radar would add, so the evening gain should mostly go. Some of
the morning gain should stay, since status at 06 or 09 only knows about spills already started. Expected: DS0 about 1%
with an interval that may just clear zero, DS1 under 1%. What remains of radar's gain sits on rows not spilling at the
issue instant.

## What follows

Nothing changes on the site or in production, whatever the result. A shadow log changes no issued prediction. Any live
use would need a dated amendment to the 2027 stamp before 1 May 2027.

- **H:** radar is worth a shadow log whether or not status is switched on. Next deliverable: build and test the logger
  offline, as #694 planned, with its candidate and reference both taking status if Ethan switches status on, and
  #694's frozen pair if not. The frozen status-plus-radar fits' hashes go in the score file. Starting the logger stays
  Ethan's decision.
- **S:** record the hours and rows that carry what is left. If what is left sits in hours the swimmer uses (before
  15 UTC) and DS0 clears 1%, the logger is still the next deliverable but carries the status form. Otherwise no
  logger on this evidence, and the radar row in the register says that radar to the issue hour adds under 1% once
  status is in.
- **N:** if status is switched on, do not build the radar logger: the radar gain is what status already gives. Record
  it. #694's result stands only for a model without status. Reopens if status is not switched on (then #694's plan
  applies unchanged), or if a second labelled year (EA 2026 start/stop files) is added.
- **W:** as N, plus a diagnosis of the join between status and radar features, since a loss would be a fault in the
  method.

## Seen before writing

- All of #694's results, including every by-hour figure and the Thames 2026 check; #254's, #639's and #695's
  results.
- The Thames stream file's span (first event April 2022, last October 2026, 537 overflows) and the EA United
  Utilities file's span (2024 to 2025). No event was joined to any row or day.
- `scripts/radar_issue_hour_eval/score.py` and `scripts/live_status_test.py`, read for method.
- No score of any kind has been computed for this test. No status input has been built on any 2025 or 2026 row.

---

## Results

Not yet run.
