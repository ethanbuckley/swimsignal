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

Added 13 November 2026, after the run. Everything above the line is as committed in 173074f2 (18:48 UTC) and pushed
before any score. The test code came in 5acb72c8 (18:54 UTC). It changed nothing above the line. The score file is
`RADAR-PLUS-STATUS-TEST-2026-11-score.json`, beside this record.

### The answer in plain words

Yes. With the overflow's live status already in the model, radar up to the issue hour still makes the same-day
forecast better: by 3.2% with a fresh forecast for the rest of the day and 2.5% with a day-old one, both intervals
below zero and both clear of the 1% margin. That is verdict H by the stated rule. Status takes most of radar's evening
gain, as expected: at 21 UTC radar's gain falls from 0.00258 to 0.00030. But it leaves the morning and midday gain
whole (12 UTC: 0.00117 with status, 0.00115 without), and those are the hours a swimmer uses. All of what radar still
adds is on overflows not yet spilling at the issue hour. This is development evidence on 2025 labels that have been
scored before. On Thames 2026 the same direction holds, with intervals that only just clear zero. So the radar shadow
logger is still worth building if status is switched on.

### How it was run

- **Plumbing first.** 300 overflows, random labels, no score printed. 104 s, 0 network attempts, inputs unchanged. It
  found no fault.
- **Status code checked.** Before the plumbing run, nine hand-worked cases on made-up events (overlapping events,
  an event ending exactly at the issue instant, an overflow with no events) all matched. In the scored run, at 00 UTC
  the three inputs equal #254's on all 1,378,970 rows before the mask: no missing-value mismatch, largest difference
  0.00003 hours (32-bit rounding in #254's code).
- **The scored run.** `run.sh` from a `git archive` of 5acb72c8, 18:55 to 19:20 UTC. One run. Not interrupted or
  repeated.
  - 1,487 s. Peak memory 3.0 GB. 4 threads. Within the caps (120 minutes, 12 GB).
  - 0 network attempts.
  - The shared inputs' fingerprints before and after match, with #694's values: cell radar `921e37d1…`, rain caches
    `0e698be4…`, `spill_model.pkl` `faa7917e…`. The publish-times file hashes `93ec75c1…`, the same as #694's copy.
- **Rows.** #694's exactly: 3,778 overflows in 381 cells, 1,374,430 overflow-days in 2025, 88,567 spill days. Folds as
  #694.
- **Status.** 731,834 merged events. Unknown status in the scored rows: 0 for `spilling_at_issue`, 24 for
  `spill_hours_24h`, 518 for `spill_days_7d`, at every hour. Rows spilling at the issue instant: 20,006 at 00 UTC
  rising to 23,073 at 21 UTC (1.5% to 1.7%).
- **The fits repeat exactly.** The 25 arms without status were refitted in this run. Every one of their frozen models
  is byte-identical to #694's (same SHA-256), and their Brier scores match #694's to every printed decimal. So within
  one environment the refit noise #694 reported is zero; it came from a change between #640's and #694's runs. The
  171 model hashes are in the score file.

### The deciding comparison: 2025, blocked cross-fit, out of fold

Brier differences with the 95% interval (overflow × week; overflow × day in brackets):

| Comparison | Radar arms | Status-only arms | Difference | Interval | Skill |
|---|---|---|---|---|---|
| **DS0** radar to the hour with status, fresh forecast for the rest, against PS | 0.02228 | 0.02302 | **−0.00074** | **−0.00109 to −0.00041** (−0.00105 to −0.00046) | **3.2%** |
| **DS1** the same with a day-old forecast for the rest, against F1S | 0.02480 | 0.02545 | **−0.00065** | **−0.00095 to −0.00037** (−0.00089 to −0.00041) | **2.5%** |

- **W** needed an interval wholly above zero. Neither is.
- **H** needed both intervals wholly below zero and both skills at least 1%. Both hold. **The verdict is H.**
- The 1% margin is 0.00023 for DS0 and 0.00025 for DS1. Both whole intervals lie beyond it.

**Without status, same run:** D0 −0.00123 (−0.00194 to −0.00066), 3.3%; D1 −0.00073 (−0.00114 to −0.00035), 1.9%.
These are #694's figures. So with status in:
- the absolute gain keeps 60% of D0 and 88% of D1;
- the relative gain does not fall (3.3% to 3.2%, 1.9% to 2.5%), because status lowers the Brier of both sides by
  about 38%.

### By issue hour

| Issue hour (UTC) | PS Brier | R0S − PS | Interval | Skill | R1S − F1S | Interval | Skill | Without status: R0 − P | R1 − F1 |
|---|---|---|---|---|---|---|---|---|---|
| 00 | 0.02968 | +0.00002 | −0.00020 to +0.00025 | −0.1% | −0.00031 | −0.00076 to +0.00010 | 0.9% | −0.00024 | +0.00018 |
| 03 | 0.03042 | −0.00073 | −0.00115 to −0.00034 | 2.4% | −0.00028 | −0.00065 to +0.00002 | 0.8% | −0.00048 | −0.00014 |
| 06 | 0.02940 | −0.00123 | −0.00218 to −0.00043 | 4.2% | −0.00080 | −0.00145 to −0.00025 | 2.5% | −0.00089 | +0.00003 |
| 09 | 0.02664 | −0.00067 | −0.00131 to −0.00009 | 2.5% | −0.00127 | −0.00182 to −0.00076 | 4.2% | −0.00100 | −0.00051 |
| 12 | 0.02458 | −0.00117 | −0.00176 to −0.00065 | 4.8% | −0.00057 | −0.00120 to +0.00006 | 2.1% | −0.00115 | −0.00044 |
| 15 | 0.01999 | −0.00115 | −0.00165 to −0.00066 | 5.7% | −0.00104 | −0.00149 to −0.00059 | 4.9% | −0.00136 | −0.00092 |
| 18 | 0.01538 | −0.00073 | −0.00115 to −0.00032 | 4.7% | −0.00062 | −0.00102 to −0.00026 | 3.9% | −0.00216 | −0.00201 |
| 21 | 0.00810 | −0.00030 | −0.00050 to −0.00012 | 3.7% | −0.00028 | −0.00048 to −0.00009 | 3.3% | −0.00258 | −0.00206 |

- **Status takes the evening gain.** At 18 and 21 UTC radar's absolute gain falls by two thirds to nine tenths.
- **It leaves the morning gain.** Summed over 03 to 15 UTC, radar's gain with status equals its gain without
  (0.00495 against 0.00488, fresh forecast). Hour by hour it is larger at 03, 06 and 12 and smaller at 09 and 15. With
  a day-old forecast it is larger at every hour from 03 to 15. With a fresh forecast, every hour from 03 to 21 has an
  interval below zero.
- **At 00 UTC there is nothing.** The build holds no radar for the day yet, only for the two days before, and status
  already says what those days did.
- **What status adds, for scale:** PS − P is −0.01387 pooled (37.6%), from 19.6% at 00 UTC to 78.1% at 21 UTC. By
  the evening the "today" forecast is mostly a record of the day, as #694 said. Status on top of radar (R0S − R0) is
  almost the same: −0.01339, 37.5%.
- The single-hour figures are less firm than the pooled ones (eight separate fits each). The shape is the part to read.

### Rows spilling at the issue instant, and the rest

Pooled over every (row, hour) pair:

| Pairs | Count | DS0 | Interval | DS1 | Interval | Without status: D0 | D1 |
|---|---|---|---|---|---|---|---|
| Spilling at the issue instant | 165,913 | −0.00001 | −0.00002 to +0.00000 | −0.00001 | −0.00002 to +0.00000 | −0.02141 | −0.01763 |
| Not spilling | 10,829,527 | **−0.00075** | **−0.00111 to −0.00041** | **−0.00066** | **−0.00097 to −0.00038** | −0.00092 | −0.00047 |

- Every row spilling at the issue instant is a spill day (the label's definition). With status the model already
  gives these rows a probability near 1, and radar has nothing left to add. Without status, radar's gain on them was
  large: this is the part of #694's gain that status takes over.
- On rows not yet spilling, radar keeps 82% of its gain with a fresh forecast for the rest and gains more than before
  with a day-old one (−0.00066 against −0.00047). The same holds hour by hour: on these rows DS0's interval is below
  zero at every hour from 03 to 21 UTC.

### Breakdowns (reported only, no decision)

| Group | Spill days | DS0 | Interval | Skill | DS1 | Interval | Skill |
|---|---|---|---|---|---|---|---|
| United Utilities | 59,711 | −0.00083 | −0.00128 to −0.00038 | 3.2% | −0.00073 | −0.00117 to −0.00035 | 2.6% |
| Severn Trent | 11,501 | −0.00071 | −0.00113 to −0.00035 | 3.7% | −0.00059 | −0.00098 to −0.00025 | 2.8% |
| Yorkshire | 6,242 | −0.00079 | −0.00151 to −0.00018 | 2.9% | −0.00066 | −0.00119 to −0.00017 | 2.2% |
| Wessex | 5,054 | −0.00065 | −0.00115 to −0.00025 | 3.7% | −0.00054 | −0.00096 to −0.00020 | 2.7% |
| Thames | 4,040 | −0.00029 | −0.00055 to −0.00007 | 2.5% | −0.00022 | −0.00039 to −0.00007 | 1.8% |
| Anglian | 1,410 | −0.00025 | −0.00052 to −0.00002 | 1.7% | −0.00020 | −0.00043 to +0.00000 | 1.3% |
| Southern | 339 | −0.00061 | −0.00198 to +0.00036 | 3.3% | −0.00074 | −0.00191 to +0.00009 | 3.5% |
| South West, Northumbrian | 270 together | n/a | every interval includes zero | n/a | n/a | every interval includes zero | n/a |
| December–February | 32,435 | −0.00044 | −0.00121 to +0.00023 | 1.7% | −0.00032 | −0.00089 to +0.00015 | 1.1% |
| March–May | 5,342 | −0.00017 | −0.00043 to −0.00000 | 2.2% | −0.00023 | −0.00040 to −0.00007 | 2.8% |
| June–August | 13,669 | −0.00088 | −0.00178 to −0.00018 | 4.4% | −0.00051 | −0.00115 to +0.00006 | 2.4% |
| September–November | 37,121 | −0.00149 | −0.00228 to −0.00076 | 3.8% | −0.00152 | −0.00215 to −0.00094 | 3.4% |

- The gain is not confined to United Utilities. Five companies have both intervals below zero, and Anglian's DS1
  reaches zero. Severn Trent, whose interval included zero without status, is now clearly below.
- #695 found that at United Utilities the status uplift lands only on rows already spilling. Radar with status gains
  there as much as elsewhere (3.2%), and by the split above that gain is on rows not spilling.
- Winter is the one season where both intervals include zero.

### The 2026 forward check (secondary)

The models fitted on all of 2025 and frozen, on Thames Water, 1 January to 31 August 2026: 187 overflows, 44,880
overflow-days, 4,228 spill days. Status from the same stream file as the labels.

| Comparison | Difference | Interval | Skill |
|---|---|---|---|
| DS0 | −0.00051 | −0.00132 to −0.00004 | 3.6% |
| DS1 | −0.00046 | −0.00121 to −0.00001 | 3.1% |
| D0 (without status) | −0.00102 | −0.00230 to −0.00001 | 2.2% |
| D1 (without status) | −0.00026 | −0.00109 to +0.00051 | 0.6% |

- With status, both pooled intervals lie below zero, just. Without status, D1's includes zero, as in #694.
- By hour, DS0 is near zero at 00 and 03 UTC and −0.00060 to −0.00092 from 06 to 18 UTC, the same shape as 2025.
- All of it is on rows not spilling at the issue instant (−0.00054, −0.00138 to −0.00004).
- **One deviation from #694's rows, found after the run.** #694 scored 188 overflows and 45,120 overflow-days. This run
  cut the stream file at 31 August before choosing the Thames overflows, so one overflow whose stream events all start
  after 31 August (`TWL00155`) dropped out, with its 240 dry days. The cut was written before any score, to keep status
  from reading past the window. Its effect on D0 is −0.00102 here against −0.00100 in #694. Nothing was rerun.
- One company, eight months, and status and label from one source. Both upper ends are within 0.00004 of zero. It
  leans the same way as 2025 and decides nothing.

### What was expected, and what came out

- Expected S or N. It is H.
- Expected the evening gain mostly gone. It is: at 21 UTC 0.00030 left of 0.00258.
- Expected some of the morning gain to stay. All of it stayed, and at 03 and 06 UTC there is more than without status.
- Expected DS0 about 1% and DS1 under 1%. They are 3.2% and 2.5%. The expectation reasoned in absolute terms and
  forgot that status shrinks the comparator's Brier too.
- Expected what is left to sit on rows not spilling at the issue instant. It does, all of it.

### What this shows

**Established, from this run (development, seen 2025 labels):**
- With live status as at the issue hour in the model, cell radar to that hour still lowers the same-day Brier by
  0.00074 (fresh forecast for the rest) and 0.00065 (day-old), 3.2% and 2.5%, intervals below zero and beyond the 1%
  margin.
- Status takes most of radar's evening gain and, summed over 03 to 15 UTC, none of its gain there.
- What radar adds once status is in is on overflows not yet spilling: it is about spills that have not started.
- #694's arms refit to identical models in the same environment.

**Not established:**
- That it holds outside 2025. Thames 2026 leans the same way, just clear of zero, on one company.
- That status from SwimSignal's own polls behaves like the EA record used here. The live-status shadow tests that
  (read on or after 23 November 2026).
- Which bracket is nearer the truth. The honest reading is "between 2.5% and 3.2%".
- Whether one model serves every issue hour once status is in. #694's one-model check was not repeated. The status
  inputs change with the hour, so a single fit would need its own test.

### What follows

As stated for H: radar is worth a shadow log whether or not status is switched on. **Plan only. Nothing is deployed
and no logger is built in this PR.**

- **Next deliverable:** the radar shadow logger, built and tested offline in its own PR, as #694 planned. If Ethan
  switches status on after 23 November, the logger's candidate and reference both take status (R0S against PS). If
  not, #694's frozen pair applies unchanged.
- **The status form needs a decision on its model before the logger can log it.** The fits here are one per issue
  hour (eight R0S and eight PS models), and builds run at no fixed hour. The logger's PR states before any score
  either (a) the nearest issue hour's model, or (b) a single status-plus-radar fit tested against the per-hour ones as
  #694 did. These fits are reproducible: they rebuild byte-identically from the archive of 5acb72c8 (shown above for
  the 25 arms without status). Their hashes are in the score file; the pickles were not kept.
- The four decisions #694 named still come first: where the radar step runs, the licence of a public log, where the
  frozen models live, and Ethan's go-ahead.
- Nothing on the site or in production changes. A live change would also need a refitted model no worse than
  production.

### Data credits

Contains Met Office data © Crown copyright 2024–2026, licensed under CC BY-SA 4.0 (AWS Open Data: Met Office UK
Radar Observations). This test publishes only summary figures from it. Environment Agency event duration monitoring
data, Open Government Licence v3.0. Thames Water discharge alerts. Weather data by Open-Meteo.com (CC BY 4.0),
including ERA5-Land (Copernicus Climate Change Service).
