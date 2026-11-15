# Radar rain up to the issue hour: the test, stated before any score

Written 13 November 2026. No spill model has been fitted or scored for this test. Results go below the line at the
end. Nothing above it changes after a result is seen.

## Why

The radar test at each overflow ([#640](RADAR-PER-OVERFLOW-TEST-2026-11.md), 6 November 2026) kept one finding.
Refitted on the 10 km cell's radar rain for the whole day, the spill model beat the same model refitted on the lead-0
forecast by 7.8% (Brier 0.0341 against 0.0369). With radar for only the two days before, the gain was 0.9%, and its
interval included zero.

A live build cannot have the whole day's radar. It has radar up to the hour it runs. So the 7.8% is an upper bound.
Part of it sits in rain that has already fallen by the issue hour. The rest sits in rain still to come, which no
measurement can give. #640 named this test as the next deliverable. The register row "Radar rain #343" carries it.

## The question

At a real issue time, with cell radar only for the hours the feed had published by then and forecast rain for the
rest of the day, is the same-day spill forecast better than the forecast-only one?

This is the "today" level only. Leads 1 to 4 are not touched.

## The radar feed's delay, measured first

Measured on 13 November 2026 from the bucket's own listing, before this statement was written
(`scripts/radar_issue_hour_eval/latency.py`, 722 listing requests, no composite downloaded). Each composite's
`LastModified` is set against the scan time in its name.

- 68,912 composites listed, 21 November 2024 to 12 November 2026. A full set would be 69,312, so 400 are absent.
- Minutes from scan time to the bucket: least 5.2, median 6.6, 95th centile 9.0, 99th centile 11.4.
- 0.53% arrived more than 15 minutes late and 0.40% more than 60 minutes late. The latest took 47 hours. These are
  back-fills after an outage.
- By year, the share more than 60 minutes late: 4.9% in the last six weeks of 2024, 0.22% in 2025, 0.07% in 2026.

`docs/MET-OFFICE-DATA-2026-10.md` said "within 20 minutes". The measured figure is shorter: 99 in 100 within 12
minutes.

**Not known:** whether a `LastModified` can be later than the first time a file appeared (a file written twice). If
so, this test counts that file as late when it was not. That errs against the radar.

So the test does not assume a delay. It uses each composite's own arrival time.

## The data

All of it is already on this machine, except the listing above. The scoring makes no network request.

- **Radar per cell.** `data/raw/met_office_radar/radar_<cell>_<YYYY-MM>.parquet` in the main checkout, hourly,
  hour-ending UTC, as #343 and #640 used it. An hour counts only with `coverage` at least 0.9.
- **When each radar hour was there.** The hour ending T is built from the composites at T−60, T−45, T−30, T−15 and T.
  It counts as published at the latest `LastModified` among those the listing holds.
- **Forecast rain.** Open-Meteo Previous Runs, `cache/rain*/leads_<cell>_<year>.parquet`. Lead 0 is the latest run for
  each hour. Lead 1 is the run issued a day earlier.
- **ERA5-Land.** `cache/rain*/archive_*`, for the 7-day, 30-day and antecedent features in every arm, as in #640.
- **Labels.** Spill days from the EA start/stop files, all nine English companies, 2025, with `training.site_years`
  choosing the overflow-years. For the 2026 check: Thames Water's alert-stream events, 1 January to 31 August 2026.

No Open-Meteo request is made. If the cached forecast rain cannot answer, the run stops and the record says what is
missing.

No active evaluation window is read. The Thames stream file runs to 19 October 2026, and this test reads it only to
31 August 2026, as #640 did. The windows open now (lead calibration B, ensemble rain, live-status shadow, company
calibration A8, regional routing, upgraded overflows) all start later than that.

Everything is read from the main checkout and treated as read-only. Each input is fingerprinted (SHA-256) before and
after the run. The two lists must match.

## Issue hours

The site's builds ran a median 5.9 hours apart, at no fixed hours. So the test scores eight issue hours, spread evenly
over the day: 00, 03, 06, 09, 12, 15, 18 and 21 UTC. The issue instant is the moment a build would read its inputs.

## The rain arms

Every arm uses the same model form, the same rows and the same features. Only the source of the short-range rain
features changes: `rain_d`, `max1h_d`, `max3h_d`, `max6h_d` (the day), `rain_d1`, `rain_d2` (the two days before) and
`rain_3d` (their sum). The longer features come from ERA5-Land in every arm.

At issue hour H on day D, the issue instant is D 00:00 UTC plus H hours. For each of the 72 hours of D−2, D−1 and D:

| Arm | Hours the bucket had published by the issue instant, with coverage | Every other hour stamped up to the issue instant | Hours stamped after the issue instant |
|---|---|---|---|
| **R0@H** radar to the hour, fresh forecast | radar | lead 0 | lead 0 |
| **R1@H** radar to the hour, day-old forecast | radar | lead 0 | lead 1 |
| **F1@H** forecast only, day-old for the rest | lead 0 | lead 0 | lead 1 |
| **P** forecast only (the comparator, #640's P) | lead 0 | lead 0 | lead 0 |

Three anchors from #640, on the same rows: **C** (whole-day cell radar, the upper bound), **P**, and **C-lag** (the day
from P, the two days before from C).

**Why two forecasts for the rest of the day.** The forecast a build holds for a later hour of today came from a run
issued before the build. Lead 0 for that hour is fresher than that: it comes from the latest run before the hour
itself. Lead 1 is staler: a day older. The real forecast lies between them. So R0 against P flatters the forecast, and
R1 against F1 handicaps it. The radar has to help under both.

**When radar is late or missing.** An hour not yet published at the issue instant, or with coverage under 0.9, takes
the forecast value for that hour. This is the fallback a live build would use. Missing radar is never zero rain. The
record counts how many hours fell back.

**Days.** A day needs at least 20 hours with a value (`features.MIN_HOURS_PER_DAY`), or its total is unknown. A row is
scored only where every arm has the day and both days before. Rows dropped this way are counted.

## The model form

`SpillModel`, unchanged, as in #640: layer 1 `fit_pooled` (gradient-boosted trees, monotone in rain, dry days
subsampled at 0.25, seed 0), then layer 2 `fit_site_offsets` (prior 15, recency 1.0). Nothing is tuned. Each arm gets
its own fit, so each of the eight issue hours has its own R0, R1 and F1 model.

## Rows

The nine English companies' overflows from `training.site_years(..., 2025)`, in cells with cell radar for every month
from December 2024 to December 2025 and 2025 lead forecasts, for every day of 2025. #640 scored 3,778 overflows in
381 cells on 1,374,430 overflow-days. This test should land on the same rows, less any day with no lead-1 total.

## Training and testing: blocked cross-fit with an embargo (primary)

As #640. 2025 is cut into six two-month blocks. Fold A tests January–February, May–June and September–October. Fold B
tests the other three. Each fold's model is fitted on the other fold's blocks, less every day within 7 days of one of
its own test blocks. Each row is scored once, out of fold, and the two folds' predictions are pooled.

The 2025 labels have been scored before (#343, #640 and others). **Every figure from this test is development
evidence on seen labels, not fresh confirmation.**

## The 2026 forward check (secondary)

As #640. Each arm's model is refitted on all 2025 rows and frozen. It is then scored on Thames Water's overflows from
1 January to 31 August 2026, labelled by Thames Water's alert-stream events. One company and a different label source.
It decides nothing on its own.

## The metric and the decision

Brier score on out-of-fold probabilities, on raw probabilities with no lead map.

**Two pooled differences decide.** Each averages a row's difference over the eight issue hours, so every hour of the
day counts the same:
- **D0** = mean over H of Brier(R0@H) − Brier(P). Radar to the hour against the forecast alone, fresh forecast.
- **D1** = mean over H of Brier(R1@H) − Brier(F1@H). The same, with the day-old forecast for the rest of the day.

Skill is 1 − (mean Brier of the radar arms) / (mean Brier of the forecast arms).

**The interval.** As #640: a two-way cluster bootstrap (overflows and ISO weeks resampled independently), 2,000 draws,
seed 20261113. The overflow × day and week-only intervals are reported as well.

**The margin, stated now: 1% of the comparator's Brier**, about 0.0004. It is #640's margin. A smaller gain would not
pay for fetching radar at every build and holding a fitted model per issue hour.

**The verdict, one of four:**
- **W. Worse** if either D0 or D1 has a 95% interval wholly above zero.
- **H. Radar to the issue hour helps** if D0 and D1 both have intervals wholly below zero and both skills are at
  least 1%.
- **S. A small or partial gain** if at least one of D0 and D1 has an interval wholly below zero, but H does not hold.
- **N. Not shown** if both intervals include zero. The record says whether each also rules out a 1% gain.

An interval that includes zero shows neither a gain nor "no worse".

## Reported whatever the verdict

- Brier, AUC, and the share of spill days and of dry days at probability 0.4 or more, for every arm.
- By issue hour, with intervals: R0@H − P, R1@H − F1@H, R0@H − C-lag (what today's radar adds to yesterday's),
  C − R0@H (what is left in the hours not yet fallen) and F1@H − P.
- C − P and C-lag − P on these rows, to set against #640's 7.8% and 0.9%.
- How many of the day's hours were radar at each issue hour, and the share of past hours that fell back to forecast.
- D0 and D1 by company and by season, with no decision.
- The 2026 forward check's same figures.

**One model for every hour (secondary).** The full-day radar fit (C's fold models) fed each hour's R0 features, with
no fit per hour, against P. This says whether eight fitted models are needed or one would do.

**The no-refit check (secondary).** The production `spill_model.pkl` fed each hour's R0 and P, on 2025 with United
Utilities left out, as #343 and #640 ran it. This is what plugging radar into today's model would do with no refit.

## What this test does not cover

- **A real issued forecast.** The cached forecasts are stitched by lead, not single runs. The two brackets stand in
  for the run a build would hold.
- **The long features.** ERA5-Land arrives days late. A live build would take the 7-day and 30-day rain from its own
  history. That is the same in every arm, as in #640.
- **Spill status.** By the issue hour an overflow may already be spilling, and the company's live feed shows it. The
  live-status candidate (#254, #262, #639) uses that. This test does not, and it does not measure how much of any
  radar gain the live status would already give.
- **Fresh confirmation.** 2025 is seen. Thames 2026 is one company.

## Compute and network caps

- Scoring is offline: it runs under `scripts/lake_distance_eval/run_offline.py`, which refuses every outgoing
  connection and counts attempts. The count must be 0.
- 81 model fits (27 arms, two folds and one fit on all of 2025). At #640's pace that is about 15 minutes. Stop if the
  run exceeds 90 minutes or 12 GB peak memory.
- At most 4 threads (`OMP_NUM_THREADS=4`). Eleven other sessions share the machine.
- Isolation: a `git archive` of the commit that adds the test code; scratch `DIPCAST_ROOT` and `DIPCAST_STATE` holding copies of the
  processed files read; `DIPCAST_CACHE` pointed at the shared cache, read-only; outputs in a scratch folder outside
  every checkout.
- A plumbing run first, on 300 overflows with random labels, which prints no score.

## What is expected, stated now

H, narrowly. Pooled skill of 2 to 4% under both brackets. Nearly all of it at issue hours 12 and later. At 00 and 03
no more than C-lag's 0.9%. The no-refit check under 1%, as #343 found for the whole day.

## What follows

Nothing changes on the site or in production from this test, whatever the result. Any live use of radar would change
the 2027 forecast stamp (`docs/PREREGISTRATION-2027.md` §2) and need a dated amendment before 1 May 2027. A shadow
log changes no issued prediction.

- **H:** freeze the R0 candidates (code, settings and fitted model hashes committed). Write the shadow-log plan in
  this PR: comparator, fallback when radar is late, resource limits, read date, metric and margin. Plan only. Nothing
  is deployed. Building the logger is the next deliverable. Starting it is Ethan's decision.
- **S:** record the gain and the issue hours that carry it. No shadow log on this evidence.
  - If the two brackets disagree, the answer turns on how fresh the forecast in hand is. The next deliverable is then
    a replay on the build's own issued forecasts (`forecast_<cell>.parquet` with `issued_at`), stated as its own test
    once enough issued days are cached.
  - If both intervals are below zero but the gain is under 1%, archive as for N, with the per-hour figures.
- **N:** archive radar to the issue hour as a spill-model input, with this evidence. The record's per-hour figures say
  how much of #640's 7.8% lies in hours not yet fallen. The cell radar cache stays for river-rise and timing work. It
  reopens if a model that knows each company is adopted (A8, upgraded-overflow option B, a nine-company refit), or
  when the EA 2026 start/stop files add a second labelled year.
- **W:** as N, plus a diagnosis of the join between radar and forecast hours, since a loss there would be a fault in
  the method and not in the rain.

## Seen before writing

- All of #343's and #640's results, including #640's C, P and C-lag Brier scores on these rows.
- The bucket listing and the delay figures above.
- The radar folder's file counts by month (499 cells to August 2026, 632 from September) and one November 2026 file's
  span. One 2025 and one 2026 lead file: columns, the first 12 rows and the span by lead. One `forecast_` file's
  columns and span. The cache folders' file counts by year.
- #640's saved row counts (`docs/RADAR-PER-OVERFLOW-TEST-2026-11-score.json`).
- `scripts/radar_per_overflow_eval/score.py`, `scripts/radar_rain_eval/score.py`, `scripts/verify_leads.py`,
  `features.daily_rain_features` and `ingest/rainfall_leads.py`, read for method.
- No score of any kind has been computed for this test. No label has been joined to any issue-hour rain.

---

## Results

Added 13 November 2026, after the run. Everything above the line is as committed in 3e96e449 (13 November 2026,
15:22 UTC) and pushed before any score. The test code came in ac562e07 (15:26 UTC). It changed nothing above the line.

**Verdict H: radar to the issue hour helps, by the stated rule.** Averaged over the eight issue hours, the same-day
forecast is 3.3% better with a fresh forecast for the rest of the day and 1.9% better with a day-old one. Both
intervals lie below zero and both gains are over the 1% margin. **This is development evidence on seen 2025 labels.
The 2026 forward check does not confirm it.** Nothing is adopted. Nothing on the site or in production changes.

### How it was run

- **Plumbing check first.** 300 overflows, random labels, no score printed. It found one code fault (an array that
  pandas 3 hands back read-only), fixed before the test-code commit. The day features built from 72-hour windows match
  `features.daily_rain_features` exactly on radar alone and on lead 0 alone (largest difference 0.0 mm, 231,648
  cell-days in the scored run).
- **The scored run.** `run.sh` from a `git archive` of ac562e07, 15:26 to 15:50 UTC. One run. It was not interrupted
  or repeated.
  - Run time 1,381 s. Peak memory 2.3 GB. 4 threads. Within the caps (90 minutes, 12 GB).
  - 0 network attempts.
  - The shared inputs' fingerprints before and after match. The cell radar files for December 2024 to August 2026
    hash to `921e37d1…`, the 2024–2026 rain caches to `0e698be4…` (as in #640), the production `spill_model.pkl` to
    `faa7917e…`.
- **Rows.** The same as #640's: 3,778 overflows in 381 cells, 1,374,430 overflow-days in 2025, 88,567 spill days.
  4,540 rows were dropped because the forecast had no total (the first two days of 2025 in cells with no 2024 forecast
  file). No row was dropped for radar.
- **Folds.** As #640: fold A 679,278 test rows and 562,922 training rows; fold B 695,152 and 547,048.
- **81 fits.** SHA-256 of every fold model and every model fitted on all of 2025 is in
  `docs/RADAR-ISSUE-HOUR-TEST-2026-11-score.json`.

### How much radar a build has at each issue hour

- At issue hour H the build has radar for H hours of the day. The hour ending at the issue instant itself is never
  there: its last composite arrives about 6 minutes later. So the radar runs one hour behind the clock.
- Apart from that hour, 0.1% of radar hours fell back to the forecast (late, missing or low coverage).
- 14,869 of 14,880 hours had all five composites listed. 4 hours had none.
- The day's rain total a build holds, against the radar total for the whole day (correlation over overflow-days):
  0.877 with the forecast alone, 0.909 at 06, 0.938 at 12, 0.977 at 18, 0.992 at 21.

### The deciding comparison: 2025, blocked cross-fit, out of fold

Brier differences with the 95% interval (overflow × week; overflow × day in brackets):

| Comparison | Radar arms | Forecast arms | Difference | Interval | Skill |
|---|---|---|---|---|---|
| **D0** radar to the hour, fresh forecast for the rest, against P | 0.03567 | 0.03690 | **−0.00123** | **−0.00194 to −0.00066** (−0.00179 to −0.00073) | **3.3%** |
| **D1** the same with a day-old forecast for the rest, against F1 | 0.03860 | 0.03933 | **−0.00073** | **−0.00114 to −0.00035** (−0.00110 to −0.00037) | **1.9%** |

- **W** needed an interval wholly above zero. Neither is.
- **H** needed both intervals wholly below zero and both skills at least 1%. Both hold. **The verdict is H.**
- The margin is 0.00037 for D0 and 0.00039 for D1. Both point estimates clear it. D0's whole interval is beyond the
  margin. D1's is not: its upper end is −0.00035, so a gain a little under 1% is not excluded there.

### By issue hour

| Issue hour (UTC) | R0 Brier | R0 − P | Interval | Skill | R1 − F1 | Interval | Skill | Left in the hours to come (C − R0) |
|---|---|---|---|---|---|---|---|---|
| 00 | 0.03666 | −0.00024 | −0.00080 to +0.00022 | 0.7% | +0.00018 | −0.00012 to +0.00054 | −0.5% | 6.5% |
| 03 | 0.03642 | −0.00048 | −0.00122 to +0.00006 | 1.3% | −0.00014 | −0.00039 to +0.00009 | 0.4% | 5.9% |
| 06 | 0.03601 | −0.00089 | −0.00165 to −0.00027 | 2.4% | +0.00003 | −0.00050 to +0.00058 | −0.1% | 4.9% |
| 09 | 0.03590 | −0.00100 | −0.00165 to −0.00040 | 2.7% | −0.00051 | −0.00106 to +0.00004 | 1.3% | 4.6% |
| 12 | 0.03575 | −0.00115 | −0.00189 to −0.00049 | 3.1% | −0.00044 | −0.00111 to +0.00026 | 1.1% | 4.2% |
| 15 | 0.03554 | −0.00136 | −0.00213 to −0.00064 | 3.7% | −0.00092 | −0.00154 to −0.00028 | 2.4% | 3.6% |
| 18 | 0.03474 | −0.00216 | −0.00305 to −0.00137 | 5.9% | −0.00201 | −0.00278 to −0.00129 | 5.3% | 1.4% |
| 21 | 0.03432 | −0.00258 | −0.00355 to −0.00172 | 7.0% | −0.00206 | −0.00296 to −0.00126 | 5.5% | 0.2% |

- **The anchors on these rows:** C (whole-day radar) 0.03426, P 0.03690, C-lag 0.03656. C − P is −0.00264, interval
  −0.00371 to −0.00170, 7.2%. C-lag − P is −0.00034, interval −0.00094 to +0.00011, 0.9%.
- **With a fresh forecast for the rest of the day (R0)**, the gain grows steadily with the hour. Its interval is below
  zero from 06 UTC. By noon the build has 3.1 of the 7.2 points that whole-day radar gives.
- **With a day-old forecast for the rest (R1 against F1)**, no single hour before 15 UTC has an interval below zero.
  The pooled gain comes from 15, 18 and 21 UTC.
- **Today's radar adds to yesterday's.** R0 − C-lag has an interval below zero from 06 UTC: −0.00055 at 06, −0.00080
  at 12, −0.00182 at 18.
- **The forecast for the rest of the day matters as much as the radar.** F1 − P is +0.00364 at 00 and +0.00247 at 12:
  a day-old forecast for the hours to come costs 9 to 10% before noon and 7% at noon. That is larger than the radar's
  gain at those hours.

Every arm's Brier, AUC and warning shares are in the score file. Spill days at probability 0.4 or more: P 46.1%,
R0@12 50.7%, R0@18 52.9%, C 53.8%. Dry days at 0.4 or more: P 1.53%, R0@12 1.74%, R0@18 1.82%, C 1.82%.

### One model for every hour (secondary)

The whole-day radar fit (C's fold models), fed each hour's R0 features with no fit per hour, against P:
- pooled −0.00133, interval −0.00226 to −0.00058, 3.6%;
- by hour: 0.7%, 1.5%, 2.5%, 3.0%, 3.5%, 4.9%, 6.0%, 6.8% from 00 to 21 UTC.

One model does as well as eight (3.6% against 3.3%). A model per issue hour is not needed.

### The no-refit check (secondary)

The production `spill_model.pkl` on 552,855 overflow-days in 2025, United Utilities left out (#343's rows):
- P 0.03432, C 0.03387, R0 from 0.03417 at 00 to 0.03388 at 21;
- pooled R0 − P is −0.00023, interval −0.00051 to +0.00012, 0.7%.

**Feeding radar to today's production model with no refit is not shown to help.** This matches #343. The gain above
belongs to a model fitted on radar.

### Breakdowns (reported only, no decision)

| Group | Spill days | D0 | Interval | Skill | D1 | Interval | Skill |
|---|---|---|---|---|---|---|---|
| United Utilities | 59,711 | −0.00157 | −0.00250 to −0.00079 | 3.9% | −0.00094 | −0.00151 to −0.00042 | 2.2% |
| Severn Trent | 11,501 | −0.00037 | −0.00107 to +0.00044 | 1.3% | −0.00026 | −0.00068 to +0.00015 | 0.8% |
| Yorkshire | 6,242 | −0.00140 | −0.00287 to −0.00013 | 3.5% | −0.00086 | −0.00181 to −0.00001 | 2.0% |
| Wessex | 5,054 | −0.00103 | −0.00210 to −0.00014 | 3.1% | −0.00056 | −0.00116 to +0.00003 | 1.6% |
| Thames | 4,040 | −0.00097 | −0.00198 to −0.00019 | 2.8% | −0.00052 | −0.00103 to −0.00011 | 1.5% |
| Anglian | 1,410 | −0.00037 | −0.00106 to +0.00017 | 1.3% | −0.00008 | −0.00044 to +0.00028 | 0.3% |
| Southern | 339 | −0.00259 | −0.00536 to −0.00044 | 7.9% | −0.00113 | −0.00279 to +0.00021 | 3.2% |
| South West, Northumbrian | 270 together | n/a | every interval includes zero | n/a | n/a | every interval includes zero | n/a |
| December–February | 32,435 | −0.00160 | −0.00322 to −0.00034 | 3.2% | −0.00064 | −0.00182 to +0.00047 | 1.2% |
| March–May | 5,342 | −0.00042 | −0.00086 to −0.00008 | 3.2% | −0.00035 | −0.00073 to −0.00001 | 2.7% |
| June–August | 13,669 | −0.00105 | −0.00160 to −0.00053 | 3.9% | −0.00069 | −0.00118 to −0.00026 | 2.4% |
| September–November | 37,121 | −0.00188 | −0.00416 to −0.00004 | 3.2% | −0.00125 | −0.00221 to −0.00040 | 2.0% |

United Utilities holds two thirds of the spill days. The gain is not confined to it: Yorkshire and Thames have both
intervals below zero. Severn Trent, the second largest, shows 1.3% with an interval that includes zero.

### The 2026 forward check (secondary): not confirmed

The models fitted on all of 2025 and frozen, on Thames Water, 1 January to 31 August 2026: 188 overflows, 45,120
overflow-days, 4,228 spill days.

| Comparison | Difference | Interval | Skill |
|---|---|---|---|
| D0 | −0.00100 | −0.00225 to +0.00002 | 2.2% |
| D1 | −0.00028 | −0.00112 to +0.00051 | 0.6% |
| C − P | −0.00191 | −0.00391 to −0.00014 | 4.2% |
| C-lag − P | −0.00145 | −0.00328 to −0.00011 | 3.2% |

- Both pooled intervals include zero. D0's upper end is +0.00002.
- The gain does not grow with the issue hour here. R0 − P is −0.00129 at 00 and −0.00087 at 21. Most of what radar
  gives on these rows comes from the two days before (C-lag), not from today's hours.
- This check cannot settle much. See the next section: the same frozen arms differ between this run and #640's by up
  to 0.0007 on these rows, which is as large as the differences being read.
- One company, eight months, and a different label source.

### How far the fits repeat

The anchor arms were fitted before, in #640, on the same rows with the same settings and seed. They do not come out
the same.

| Arm | 2025 out of fold, this run | #640 | Thames 2026 frozen, this run | #640 |
|---|---|---|---|---|
| C | 0.03426 | 0.03405 | 0.04344 | 0.04416 |
| P | 0.03690 | 0.03693 | 0.04534 | 0.04488 |
| C-lag | 0.03656 | 0.03658 | 0.04390 | 0.04430 |

**Established:**
- The radar features are the same in both runs. The production model fed C scores 0.033873 here and 0.033872 in #640.
- The forecast features are not bit-identical. This test holds hourly rain as 32-bit numbers. Checked on 60 cells with
  no labels: 4% of the forecast day features differ, by at most 0.000004 mm. The production model fed P scores
  0.034320 here and 0.034332 in #640.
- Inside this run, R0@00 and C-lag have almost the same inputs (they differ in 0.1% of hours) and score 0.03666 and
  0.03656.

**Inferred, not tested:**
- A refit moves an arm's 2025 Brier by about 0.0001 to 0.0002, and its Thames 2026 Brier by up to 0.0007. The cause is
  not established. The 32-bit storage is one candidate. The library versions or the thread count are others (not
  compared with #640's; this run used scikit-learn 1.9.1 and 4 threads).
- The bootstrap intervals hold the fits fixed, so they do not include this. D0 and D1 each average eight fits, which
  should shrink it to under 0.0001 for D1 and about 0.00015 for D0 (D0 leans on the single P fit). Both pooled gains
  are several times that. The single-hour figures are not: R1 − F1 at 00 and 06 are inside it.
- So the pooled verdict is the part to rely on. The hour-by-hour table shows a shape, not eight separate results. The
  one-model check, which uses the same two C models at every hour and so has none of the hour-to-hour fit noise,
  shows the same steady rise.

The 7.8% that #640 kept comes out as 7.2% here. The difference is this refit noise in C.

### What was expected, and what came out

- Expected H, narrowly, with 2 to 4% under both brackets. D0 is 3.3%. D1 is 1.9%, just under the range.
- Expected nearly all of the gain at 12 UTC and later. With a fresh forecast that is wrong: R0 is 2.4% better at 06 and
  2.7% at 09. With a day-old forecast it holds, and more strictly: nothing is clear before 15.
- Expected no more than 0.9% at 00 and 03. 00 is 0.7%. 03 is 1.3%, with an interval that includes zero.
- Expected the no-refit check under 1%. It is 0.7%.

### What this shows

**Established, from this run (development, seen 2025 labels):**
- With the feed's real arrival times, a build has the cell radar to within one hour of the clock, and loses 0.1% of
  hours to late or missing files.
- A model fitted on radar, fed radar to the issue hour and forecast for the rest, beats the same model form fitted on
  the forecast alone. The pooled gain is 3.3% (fresh forecast) and 1.9% (day-old forecast), intervals below zero.
- The gain is small in the morning and large in the evening. At 12 UTC it is 3.1% and 1.1%. At 18 UTC it is 5.9% and
  5.3%.
- One model fitted on whole-day radar serves every issue hour.
- The production model, not refitted, shows no gain from the same radar.

**Not established:**
- That it holds outside 2025. Thames 2026 leans the same way under D0 and shows 0.6% under D1, both with intervals
  that include zero.
- Which bracket is nearer the truth. A real build's forecast for the rest of the day is older than lead 0 and newer
  than lead 1. The honest reading of the pooled gain is "between 1.9% and 3.3%".
- How much of the evening gain the company's live spill feed already gives. By 18 UTC an overflow that will count as
  a spill day has often started, and the feed shows it. The live-status candidate (#639) uses that. This test did not.
- That the evening gain is useful to a swimmer. At 18 and 21 UTC the "today" forecast is mostly a record of the day.
  It matters for what is carried into tomorrow more than for a swim today. (A judgement, not a measurement.)

### What follows

As stated for H: the candidates are frozen, and the shadow-log plan is below. **Plan only. Nothing is deployed, and
no logger is built in this PR.**

The frozen candidate for a shadow log is the one-model form, chosen after seeing the scores above because it did as
well as eight fits and is simpler to run:
- **candidate:** the whole-day radar fit on all of 2025 (`model_2025_C.pkl`, SHA-256 `d157a268…ee598f8c`), fed radar
  to the issue hour and the build's forecast for the rest;
- **reference:** the same form fitted on the lead-0 forecast (`model_2025_P.pkl`, SHA-256 `70b0898e…998b093f`), fed
  the build's forecast alone.

Both files are kept outside the repository, in the session group's notes folder
(`radar-issue-hour-test-models/`). The fits do not repeat to the last decimal (see above), so the hash alone will not
rebuild them. The logger's PR has to give them a durable home.

## Shadow-log plan (plan only, nothing deployed)

**What it would settle.** Whether the 2025 gain appears on fresh days, with the forecast a real build holds for the
rest of the day, the build's own long-range rain features, and the real gaps between builds. Those are the three
things this backtest could not reproduce.

**What is logged, on every build, for every overflow row the forecast log already holds, lead 0 only:**
- `p_cal`: the production forecast as issued. Already logged. Unchanged.
- `p_ref`: the reference model on the rain the build already holds. Isolates the change of model from the change of
  rain.
- `p_radar`: the candidate, with the fallback applied.
- `radar_state`: `ok`, `partial` (some hours fell back) or `fallback` (all of them).
- The issue time, the scan time and `LastModified` of the newest composite read, and the count of radar hours used.

The claim under test is `p_radar` against `p_ref`. `p_radar` against `p_cal` is reported beside it, because the
candidate also differs from production by being a nine-company fit with no lead map.

**Its own log.** A separate versioned table, never the issued forecast and never public text. It changes no issued
prediction and does not touch the 2027 stamp.

**Inputs at issue time.**
- Radar: the bucket listing for the UTC days touched (up to 3 requests), then the composites. No account or key.
- Forecast and long features: what the build already holds. No Open-Meteo call is added.
- No input from after the issue time: an hour counts only if its last composite is in the listing the build read.

**Fallback when radar is late.**
- One hour late, missing or under 0.9 coverage: that hour takes the forecast value. This is the rule tested above.
- The listing fails, the newest composite is more than 90 minutes old, or the radar step passes its caps: every hour
  takes the forecast, so `p_radar` equals `p_ref`, and `radar_state` says so.
- The fallback is part of the candidate. The read scores `p_radar` as logged, and reports the `ok` rows separately.
- The radar step must never fail or delay the site build. It runs after the forecast is written, with its errors
  caught.

**Resource limits.**
- Cold start: 72 hours of composites, at most 289 files, about 145 MB (0.5 MB each, up to 0.8 MB on wet days), about
  110 s at the fetcher's measured pace (97 files in 37 s).
- With the last 72 hours of cell totals carried between builds: about 24 new files for a 6-hour gap, about 10 s.
- Caps per build: 300 composites, 240 s, one request at a time 0.2 s apart. Over a cap, fall back. Three builds in a
  row over a cap, switch the step off and record it.
- The build job's limit is 25 minutes and a build takes about 14.
- The bucket is "non-operational" with no uptime promise. In two years 0.4% of composites arrived more than an hour
  late and 400 of 69,312 are absent from the listing.

**Read, proposed.** From the first logged build to 31 March 2027. Read on or after 8 April 2027, so a result lands
before the 1 May 2027 date for any amendment to the 2027 stamp. Brier on logged lead-0 rows against spill days from
the live feed, as the live-status shadow scores them. Pass: `p_radar − p_ref` has an overflow × week interval wholly
below zero and a gain of at least 1%. Reported by issue hour and by `radar_state`. Fewer than 12 full weeks logged:
report "too few", no verdict.

**How much it could show.** In this backtest the three winter months alone gave D0 an interval of −0.00322 to
−0.00034 on 32,435 spill days. A four-month window of about that size could detect a gain as large as 2025's, without
much to spare. It could not detect a 1% gain. (Inferred from that interval's width, not simulated.)

**Unresolved. Each needs a decision before a logger can run:**
1. **Where the radar step runs and keeps its 72 hours.** Inside the site build needs `h5py`, which the build does not
   install today (`pyproject.toml`, the optional `radar` group). Carrying cell totals between builds means keeping
   them in the state release, which is public.
2. **Licence.** The radar is CC BY-SA 4.0. Cell totals in a public release are Adapted Material and must carry the
   licence and credit. Whether a logged probability inherits the licence is already on the solicitor's list
   (`docs/MET-OFFICE-DATA-2026-10.md` §8). A private log avoids the question for now.
3. **Where the two frozen models live.**
4. **Starting it.** Ethan's decision. Building and testing the logger offline needs none of the above and is the next
   deliverable.

**What a pass would not do.** It would not put radar on the site. The production model does not gain from radar
without a refit, so a live change means changing the model too. Nine-company refits have so far failed at United
Utilities (#357). That question is separate and stays open.

### Data credits

Contains Met Office data © Crown copyright 2024–2026, licensed under CC BY-SA 4.0 (AWS Open Data: Met Office UK
Radar Observations). This test publishes only summary figures from it. Environment Agency event duration monitoring
data, Open Government Licence v3.0. Thames Water discharge alerts. Weather data by Open-Meteo.com (CC BY 4.0),
including ERA5-Land (Copernicus Climate Change Service).
