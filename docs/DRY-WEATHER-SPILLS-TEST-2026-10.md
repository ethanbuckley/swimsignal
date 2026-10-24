# Overflows that spill in dry weather: the test, stated before any run

Written 24 October 2026. Nothing has been counted or scored. No dry-weather spill has been counted for any overflow,
year or company. Results go below the line at the end. Nothing above it changes after a result is seen.

## Why

Tim Boden (Ambleside) reported a broken sewer feeding one of Waterhead's streams, worst in dry weather. The spill
model is driven by rain (`features.ALL_FEATURES`: ten rain summaries, two season terms, three annual-return figures).
It cannot see a spill caused by a fault, a blockage, groundwater getting into the sewer or a pump failing. If some
overflows spill on dry days year after year, the model misses those spills in the same place every year. Each such
spill is also one the Environment Agency treats as a potential permit breach until it is investigated.

This file asks three things:
1. **A description.** How many dry-weather spill-days each overflow had in 2024 and 2025, by company, and which
   overflows had most. No model is scored for this part.
2. **Question 1.** Does an overflow's 2024 dry-weather spill rate predict its 2025 dry-day spills better than the
   spill models do?
3. **Question 2.** Does that rate, added to the spill model as a site input, improve the model over all days?

A page note is proposed at the end of the results. It is not built here.

## The dry-day rule (fixed now)

**What the EA uses.** The EA's blog "What are dry day spills?" (28 August 2024) defines a dry day as "no rainfall
above 0.25mm on that day and the preceding 24 hours", measured with local rain gauges and rainfall radar. It says
some overflows in very large catchments can spill on a dry day because water takes a long time to drain down.

**What this test uses.** SwimSignal has no gauges here, only ERA5-Land hourly rain on 0.1° cells (about 7 by 11 km).
The same rain the spill model is trained on: `training.load_rain` from `cache/rain/` and `cache/rain_nine/`, daily
totals by `features.daily_rain_features`, UTC days, a day unknown when it has fewer than 20 finite hours.

- **A dry day** at an overflow is a UTC day *t* on which the overflow's cell had **under 0.25 mm on each of days
  *t*, *t*−1 and *t*−2**, all three known. An unknown day is never dry.
  - 0.25 mm is the EA's threshold.
  - One day more than the EA's window. The EA allows drain-down of up to about a day. A cell is wider than a gauge's
    view, and ERA5-Land smooths a local shower over the cell. The extra day makes it less likely that rain the cell
    missed explains the spill.
- **Events** are each overflow's EA start/stop events with overlapping events merged
  (`scripts/live_status_test.py`, `merged_intervals`). Events that do not overlap stay apart, whatever the gap.
- **A dry-started event** is a merged event whose start falls on a UTC day that is a dry day at the overflow.
- **A dry spill-day** is a dry day on which a dry-started event spilled. "Spilled on day *d*" uses the label's own
  rule (`features.spill_days`): every UTC day from the start's day to the stop's day, at most 60 days on.
- **A continuing day** is a dry day on which the overflow spilled, but only from events that started on days that
  were not dry. These are spills carried over from wet weather: drain-down, long storm events, groundwater after a
  wet spell. They are neither a dry spill nor a dry day without a spill, so they are left out of every count and row
  below, and counted on their own.

So, at each overflow and year, over the overflow's kept days (below):
- *n* = dry days, less continuing days;
- *k* = dry spill-days;
- the **dry-spill rate** is *k*/*n*.

**A second threshold, reported only.** The same rule with **under 1.0 mm** on each of the three days (the Met Office's
wet-day threshold). It is reported for the description and for Question 1. It decides nothing.

**What the rule cannot tell apart.** A dry-started event may be a fault, a blockage, groundwater, a pump failure, a
long drain-down from rain more than two days back, or rain the cell did not record. It may also be a monitor fault: the
EA's files are not formally verified. Companies also record events differently (`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`,
step 1): Wessex and Anglian log many events a few minutes long, Thames merges activations. So a company's count of
dry spill-days depends partly on how it records. Comparisons between companies are reported, not interpreted.

## The rows

D2's rows, built by D2's code (`scripts/train.py` `_frame`, `training.site_years`): 4,976,868 overflow-days in 2024
and 5,077,150 in 2025, the nine English companies' EA start/stop files. The script stops if it gets other counts.
- **Dry rows** are those whose day is a dry day, less continuing days.
- **The label on dry rows** is "a dry spill-day". On these rows it equals D2's label ("spilled that day"), because
  continuing days are left out.

## Part 1: the description (no model)

Per overflow and year, 2024 and 2025: kept days, dry days, continuing days, *n*, *k*, the rate, all spill-days, and
the share of all spill-days that are dry spill-days. Then:
- **By company and year:** overflows, the share with *k* = 0, 1 to 4, 5 to 19 and 20 or more, the median and 90th
  percentile of *k*, the most, the total, and the company's rate (Σ*k* / Σ*n*).
- **Top overflows:** the 25 with the most dry spill-days over 2024 and 2025 together, with name, company, each year's
  *k* and *n*, and each year's rate. Ties are broken by 2025's *k*, then by site id.
- **Both years:** the Spearman correlation of *k*/*n* between 2024 and 2025 over overflows with *n* of at least 30 in
  both years, and the share of 2024's top 5% (by *k*) that are in 2025's top 5%.
- **Ambleside and Waterhead:** every United Utilities overflow whose name contains "Ambleside", "Waterhead",
  "Rothay" or "Brathay", with its counts.
- The same company table at the 1.0 mm threshold.

## Question 1: does the 2024 rate predict 2025's dry-day spills?

**Rows:** 2025 dry rows. **Label:** dry spill-day.

**Predictors,** all scored on the same rows:

| Predictor | What it is |
|---|---|
| **R, the rate** | The overflow's 2024 rate shrunk toward its company's: (*k* + 30*c*) / (*n* + 30), with *k* and *n* from 2024 and *c* the company's 2024 rate. An overflow with no 2024 dry rows gets *c*. |
| D2 | `spill_model_nine_2024.pkl` (SHA-256 begins `1603678923cc`), nine companies 2024. It never saw 2025. |
| P, production | `spill_model.pkl` (SHA-256 begins `faa7917e2be7`), United Utilities 2023 to 2025, raw (no lead map), as the nine-company test scored "Current production". It saw United Utilities 2025, so **United Utilities is left out of every comparison with P.** |
| F, flat | The company's 2024 rate, *c*. |

- **Why 30.** About a month of dry days. An overflow with a full year normally has more, so its own count leads. One
  with few dry days stays near its company. The value is fixed now and not tuned.
- The models get the rows' ERA5-Land features, as in D2's verification.
- **Reported, not conditions:** the unshrunk rate (*k*/*n*, else *c*); all of it per company; the 1.0 mm rule.

**Uncertainty.** Paired differences in Brier (R minus the other) with 95% intervals from a cluster bootstrap by ISO
week of the UTC day: 2,000 resamples from `numpy.random.default_rng(0)`, every row of a week drawn together, one set of
draws for every comparison. The live-status test's method (`boot_interval`).

**Question 1 is answered yes if all four hold:**
1. **Against production.** On the eight companies other than United Utilities, R's Brier is lower than P's, and the
   95% interval of the difference lies wholly below zero.
2. **Against D2.** On all nine, R's Brier is lower than D2's, and the interval lies wholly below zero.
3. **Against the flat rate.** On all nine, R's Brier is lower than F's, and the interval lies wholly below zero.
4. **Ranking.** R's AUC is higher than P's on the eight companies and higher than D2's on all nine.

If any fails, the answer is no, and the failing comparison is named.

## Question 2: the rate as a site input to the spill model

**The candidate.** D2 with one more input, `dry_spill_rate`, and nothing else changed:
- **On 2025 rows** it is R above, from 2024.
- **On 2024 rows**, the training rows, it is the same formula with each row's own calendar month left out: *k*, *n*
  and the company's *c* are counted over 2024's dry rows outside that month. Without this, the input would contain
  the very labels it is trained to predict. Within a year a fault persists for weeks, so some of that still leaks
  through from the months either side. That makes the model trust the input more than it should for the year after,
  which can only hurt it on 2025. The leak works against the candidate, not for it.
- **Monotone.** It may only raise the probability, as each rain input may (`features.MONOTONE`).
- **Fit.** D2's settings: `fit_pooled` with `neg_frac` 0.25 and seed 0, then `fit_site_offsets` with prior strength 15
  and recency 1 on the candidate's own 2024 predictions. The script stops unless the subsample is D2's 1,569,401 rows.
  Nothing is tuned on 2025. If a setting changes after a 2025 score is seen, the run is void and the change is recorded
  below the line.

**The baseline** is D2 itself. Two checks of the code: 0.0362 on the 2025 rows with ERA5-Land rain, and #239's
lead-row Brier 0.03784, 0.04153, 0.04376, 0.04578 and 0.04919 at leads 0 to 4.

**Scoring.** As the live-status test (`docs/LIVE-STATUS-FEATURE-TEST-2026-10.md`), with its code reused:
- 2025 rows, ERA5-Land rain: per company and all nine, Brier, AUC, ECE and a 10-bin reliability table;
- the lead rows with forecast rain, leads 0 to 4, built by its rule;
- the week bootstrap above for every difference.

United Utilities 2025 is in these rows: D2 and the candidate never saw 2025. The production model is not scored here.

**Question 2 passes if all four hold:**
1. **A gain.** On the 2025 rows with ERA5-Land rain, all nine, the candidate's Brier is lower than D2's, and the 95%
   interval of the difference lies wholly below zero.
2. **No company clearly worse.** At no company is the candidate's Brier higher with the interval wholly above zero.
3. **Reliability.** At each company the candidate's ECE is no higher than D2's, or it is at most 0.02.
4. **With forecast rain.** On the lead rows, at every lead 0 to 4, the candidate's Brier is lower than D2's, and at no
   lead does the interval lie wholly above zero.

**Reported, not conditions:** the difference on 2025 dry rows and on the rest; layer 1 alone for both; the candidate
with `dry_spill_rate` set to the company rate *c* for every overflow (what it does with no overflow history).

## A check on 2026, reported only

The EA's "2026 year to August" zip exists, and ERA5-Land for 2026 is cached only for United Utilities' cells
(`cache/rain/archive_<cell>_2026.parquet`, to 6 September 2026). The production model never saw 2026. So at United
Utilities alone:
- **Rows:** January to June 2026, the overflows kept in 2025, with the 2025 return's covariates as the year-1 rule
  gives. An overflow with no 2026 event counts as no spill.
- **The data check first.** A month is used only if the number of United Utilities overflows with at least one event
  in it is at least half the number in the same month of 2025. July and August are left out from the start: an earlier
  check found July 2026 very small for every company.
- **Predictors:** R from 2025 (*k*, *n*, *c* from 2025), P, D2 and F from 2025. Brier, AUC and the week bootstrap.
- It decides nothing. It is the only comparison here in which production has not seen the year it is scored on at
  United Utilities.

The import runs `scripts/import_ea_events.py --years 2026` in its own scratch root, from a copy of the zip already on
this Mac, offline. It never writes into the main checkout.

## What is expected, stated now

- **Description.** Most overflows will have no dry spill-days in a year. A few hundred will have many. Wessex, Anglian
  and South West will have the most, partly from how they record events, and Thames will have the fewest per spill.
- **Question 1 will most likely be yes.** On dry days the rain inputs are near zero, so the models fall back on the
  season and the site's offsets. P has no offsets outside United Utilities. D2's offsets are fitted over all days, so
  a wet-weather spiller and a dry-weather spiller with the same total look alike to it. Condition 2 (against D2) is the
  one most likely to fail.
- **Question 2 will most likely fail condition 1.** Dry spill-days are a small share of all spill-days. The offsets
  already carry much of an overflow's level. A gain on dry rows may be too small to show over all rows.
- Tim's Waterhead overflows: no expectation. Their counts are not known.

## Running

- The harness is `scripts/dry_weather_spills_eval/`. It is committed after this file and before the run. The statement
  above the line does not change when it is added.
- Everything runs from a `git archive` of the harness commit in a scratch folder, offline (every outgoing connection
  refused and counted, `scripts/lake_distance_eval/run_offline.py`). No fetch: the rain and the lead forecasts are
  cached, and the 2026 zip is a local copy.
- Data: the main checkout's `data/processed` event files, annual returns and production model, copied into a scratch
  `DIPCAST_ROOT`; D2's candidate copied from `swimsignal-private/baselines/`; rain read from the main checkout's
  `data/cache`, read only.
- One run, alone, when no other evaluation, training or build runs on this Mac and at least 35% of memory is free.

## What follows

**Nothing is adopted in this PR, whatever the result.**
- **Question 1 yes.** It supports a page note (proposed below the line) and a list of overflows worth reporting. It
  changes no forecast.
- **Question 2 passes.** 2025 has already judged D2, the neural challenger and the live-status candidates. So a pass
  deploys nothing. It earns a confirmation on 2026 data, stated before it runs, once all nine companies' 2026 files
  are complete. The production change is Ethan's call after that.
- **Question 2 fails.** The record. The input is not tried again without a new reason.

Changing a model input is allowed until the 2027 freeze tag (`docs/PREREGISTRATION-2027.md`). The PR is left for Ethan
to merge.

## What will be reported

Whatever the verdict:
- every condition with its figure and interval;
- the description's tables, the top-overflows table and the Ambleside and Waterhead rows;
- rows, base rates and Brier per company for every predictor;
- continuing days by company;
- the 2026 data check and, if it passes for any month, the 2026 scores;
- run time, peak memory and network attempts.

## Seen before writing

- The EA's definition of a dry day, from its blog post of 28 August 2024.
- `docs/README.md` and the earlier spill-model tests: D2 (`NINE-COMPANY-MODEL`), the neural challenger, the
  live-status test, the covariate-year and multi-year tests. Their published 2025 scores.
- The event files' columns (`site_id`, `site_name`, `lat`, `lon`, `event_start`, `event_end`, `duration_h`, `source`)
  and the annual returns' columns and rows per year (2021 to 2025).
- Both models' input lists (the same fifteen) and offset counts: 2,271 for production, 13,598 for D2.
- Which rain files exist: ERA5-Land for 2024 and 2025 for the nine companies' cells, for 2026 only in 206 cells
  (United Utilities), to 6 September 2026. One 2026 file was opened for its span.
- That a "2026 year to August" zip exists on this Mac. It has not been opened.
- No event was classified, no dry day counted and no score computed.
