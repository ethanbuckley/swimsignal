# Spill duration: what failed, whether live inputs support it, and the smallest next experiment

Written 30 October 2026, after the verdict in `docs/SPILL-DURATION-TEST-2026-11.md` (PR #459, merged as a record).
**These are development diagnostics. The verdict stays: C1 fails as stated, nothing adopted.** They answer an
outside review of the same day, which raised two points:
1. the target joins events less than an hour apart and counts the pause as spilling, which a live monitor would not
   report, and which uses a later restart to fill in the earlier episode;
2. scoring "stops now" as a forecast does not measure the site's clearing time, which is a stated scenario.

Both points are right. The second corrects a claim in the results; see "Correction" there.

Harness: `scripts/spill_duration_test.py diagnose`, run once on 30 October 2026 (8 minutes), on main checkout data, no network, no Open-Meteo calls. It reproduced C1's 2025 score exactly (integrated Brier 0.1507) and
saved its predictions to `data/processed/spill_duration/predictions_2025.parquet` (not committed). Tables beside this
file: `-target.csv`, `-reliability.csv`, `-by-elapsed.csv`, `-live-rows.csv`.

2025 has now been looked at again. Nothing here may be used to tune a model that is then judged on 2025.

## 1. The target: pauses, and what a live monitor can see

**How much of the target sits in joined pauses.** A row is "in a pause" when the overflow's spill (events joined at
1 hour) is running but no EA event is: the monitor would show "not discharging".

| | 2024 | 2025 |
|---|---|---|
| Issue hours in a pause | 6.5% | 6.9% |
| Rows where "same spill still running at +h" differs from "monitor reports a discharge at +h" | 5.2% (1 h) to 14.4% (24 h) | 5.4% (1 h) to 11.6% (24 h) |

By company (2025), from 2.1% of rows in a pause at Thames to 10.9% at Wessex. The two labels part most at long
horizons for a reason that is not about pauses: at +24 h, a monitor reports a discharge on 37.5% of 2025 rows but
the same spill runs on only 28.3%. The difference is mostly new spills that start after the first ends. So
"discharging at +h" answers "will it be discharging then", not "will this spill go on".

**Does the gain survive on rows a live monitor can reproduce?** Yes. Rows restricted to hours when an EA event is
running at the issue time (1,473,584 of 1,582,953 in 2025); B1 and C1 each refitted on the same kind of 2024 rows
and label:

| Label | B1 | C1 | C1's gain |
|---|---|---|---|
| Same spill still running at +h (the original) | 0.1683 | 0.1487 | 11.7% |
| Monitor reports a discharge at +h | 0.1831 | 0.1634 | 10.7% |

The gain holds at every company for both labels: from 7.8% (Yorkshire) to 17.2% (Thames) with the original label,
and from 7.8% (Yorkshire) to 15.6% (Southern) with the monitor's. One look, no interval.

**Elapsed time from information available at the issue time.** On those rows, elapsed time needs only events that
began before *t*: the spill's start is found by walking back from the event running at *t* through earlier events
that ended less than an hour before the next began. No later event is used. So, given the EA's event record, the
inputs are causal. The non-causal part of the original design was the 6.9% of rows in pauses, which a live forecast
would not see as running.

**What the live feeds give (stated, not measured).** Each poll stores status, `status_start`, `latest_event_start`
and `latest_event_end` per overflow (`live_history.parquet`). Polls ran a median 1.05 h apart and 6.4 h at the 95th
percentile (28 Sep to 20 Oct 2026, `live_status.MAX_GAP_H`'s note). A pause and restart between two polls leaves
only the restart's start in the next poll, so a live elapsed time could be too short after a long gap between polls.
How often that happens is **not checked**. It cannot be checked against EA records yet: SwimSignal's polls start on
11 September 2026 and the EA's 2026 file ends on 31 August. It can be simulated (section 4).

## 2. Why condition 4 failed

**Overall, C1 forecasts slightly too low; B1 slightly too high.** Mean forecast minus observed share, all nine, 2025:

| Horizon | 1 h | 3 h | 6 h | 12 h | 24 h |
|---|---|---|---|---|---|
| B1 | +0.008 | +0.010 | +0.010 | +0.012 | +0.019 |
| C1 | −0.006 | −0.009 | −0.012 | −0.015 | −0.017 |

**By company, C1's errors go both ways.** At 24 h:

| Too high (spills ended sooner than forecast) | Too low (spills ran longer than forecast) |
|---|---|
| Anglian +0.086 (B1 +0.069), Southern +0.032 (B1 +0.066), Thames +0.022 (B1 +0.010) | South West −0.065 (B1 −0.007), Yorkshire −0.026 (B1 +0.020), United Utilities −0.025 (B1 +0.016), Wessex −0.031 (B1 +0.005), Severn Trent −0.018 (B1 +0.023) |

Northumbrian is within 0.013 at every horizon.

**Two different faults, inferred from these tables:**
- **A year shift that B1 shares.** At Anglian and Southern both predictors forecast too high, by similar amounts:
  2025's spills there ended sooner than 2024's. No calibration fitted on 2024 can correct a change that first shows
  in 2025. *Inferred:* a drier 2025, or a change in how those companies record events. Not checked.
- **C1 is too sharp at long horizons.** All nine, 24 h: where C1 says 0.92 the observed share is 0.74; where it says
  0.85, 0.74; where it says 0.04, 0.06. At 6 h it is close to the diagonal above 0.5 and too low between 0.1 and 0.4
  (0.15 against 0.18, 0.25 against 0.30). The too-low companies (South West, United Utilities, Yorkshire) show the
  same pattern: forecasts of 0.85-0.93 come true 55-65% of the time at United Utilities and Yorkshire. This is the
  part a calibration step fitted on held-out training predictions could fix.

**By elapsed time**, C1's errors are largest for spills 2 to 12 hours old (−0.02 to −0.04 at 6 to 24 h) and near zero
for spills under an hour old or over a day old (within 0.013). B1 is too high for spills over a day old at 24 h (+0.05 to +0.06).

## 3. The January-August 2026 records

`docs/NINE-COMPANY-MODEL-V2-DATA-CHECK-2026-10.md` (25 October) and the v2 results, read today, plus the caches:

| Question | Answer | Source |
|---|---|---|
| Complete? | All nine companies, 1 January to 31 August 2026, no missing day or month. July is small because it was very dry, not because data is missing. | data check |
| On disk? | **No.** The 2026 zip (29,672,650 bytes, SHA-256 `d0dbf32f…`) was imported into a scratch root that no longer exists. `data/processed/ea_events_*.parquet` hold 2024 and 2025 only. Re-import: one EA download, `scripts/import_ea_events.py --years 2026` into a scratch `DIPCAST_ROOT`. | checked today |
| Censoring | The file ends at 31 August 23:59 UTC. A spill running then is cut. With 24 h labels, issue hours must end by 31 August 00:00. Spills running over the new year join the 2025 file's events, as 2024/25 did. | file dates |
| Rain | ERA5-Land 2026 is cached for the nine companies' cells: 1,442 files tagged `2026a` in `data/cache/rain_nine` (v2's fetch, 25 October) and 412 tagged `2026` in `data/cache/rain`. No new Open-Meteo calls needed. `training.load_rain` must be asked for the `2026a` tag. | checked today |
| Prior use | **Used, but not for duration.** It was v2's test set (daily spill labels, scored 25 October) and is option B's window E (daily labels, to run on or after 2 December). No model has scored spill durations on 2026, and nothing in PR #459 or here read a 2026 event. | v2 results; option B statement |
| Recording changes | **United Utilities changed how it records events in 2026.** Median gap between events 102 minutes, against 26-28 in 2024-25; 47% of gaps under an hour, against 69-70%. A 1-hour join would split United Utilities' 2026 spills more often than its 2024-25 spills, which changes the target there. | data check |
| Other risks | Spring and July 2026 were dry in the south. Durations in a dry spell may differ from 2024-25. | data check |

**So 2026 can be the fresh duration period, with United Utilities handled apart.** A choice is needed before any
2026 duration figure is looked at (section 4, decision 2).

## 4. The smallest credible next experiment (a draft, not approved)

**C1-cal: C1 with a calibration step, judged on January-August 2026.**

- **Rows.** Issue hours when an EA event is running (a monitor would show "discharging"), first 72 h of each spill.
  Training: 2024 and 2025. Scoring: 1 January to 30 August 2026 (labels to 31 August).
- **Label.** Same spill (joined at 1 hour) still running at +1, 3, 6, 12, 24 h. The label may use what happened
  after *t*; it is the outcome. "Monitor reports a discharge at +h" reported beside it.
- **Elapsed time.** From EA events that began before *t* only (section 1). Reported beside it: elapsed time as hourly
  polls would see it (status and the latest event's start on each whole hour, chaining back while the previous
  hour's poll showed a discharge), to measure how much poll gaps cost.
- **Calibration, fitted on training years only.** Out-of-fold C1 predictions on 2024-25: eight folds by calendar
  quarter, C1 fitted on seven and predicting the eighth. Isotonic regression per company and horizon on those
  predictions. Then the five horizons forced not to rise (`monotone`). The final C1 is fitted on all of 2024-25; the
  calibrators map its 2026 predictions.
- **Predictors scored on 2026:** B1 (fitted on 2024-25), C1 raw, C1-cal. Same settings as PR #459 otherwise.
- **Conditions:** PR #459's five, for C1-cal against B1, with the same intervals and the 2% gain rule. C1 raw reported.
- **Before the statement is fixed,** a 2024-25-only check: do the out-of-fold predictions show the same over-sharpness
  as the 2025 diagnostics? If they do not, calibration fitted on them cannot fix it, and the experiment is not worth
  running.
- **Cost.** One EA download (the 2026 zip). No Open-Meteo calls. About 30 minutes locally (nine C1 fits on two years of rows).

**What a pass would and would not show.** A pass shows the duration chances can be trusted on a fresh period. It
says nothing about how long the water takes to recover, which needs water samples. And it deploys nothing by itself:
showing a chance on the page is a separate wording decision (`docs/CLEAR-TIME-WORDING-2026-11.md`).

**Decisions for Ethan before the statement is fixed:**
1. Run this, or stop at the diagnostics.
2. United Utilities in 2026: (a) scored and in the conditions as usual; (b) scored and reported, but left out of
   conditions 3 and 4 because its recording changed; (c) left out. I recommend (b): the change was seen from event
   counts and gaps only, before any duration figure, and the other eight still judge the result.
3. Accept the one EA download.

## Correction to the record

`docs/SPILL-DURATION-TEST-2026-11.md`'s results called B0's score "the one firm product finding". That was wrong.
The page says "if it stops now", a scenario, so scoring it as a forecast that every spill stops at once does not
measure how accurate the clearing times are. The firm evidence is C1 against B1. A dated note is added below that
file's line.
