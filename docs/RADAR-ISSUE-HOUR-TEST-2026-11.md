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

None yet.
