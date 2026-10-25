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

---

## Results

Added 25 October 2026, after the run. Everything above the line is as committed in ab871a9 (24 October 2026, 22:27
BST) and pushed before anything was counted. The harness came in 68af0f8 (22:35 BST). It changed nothing above the
line.

**Verdict: Question 1 is no. Question 2 fails all four conditions. Nothing is adopted.**
- Question 1 fails conditions 1, 3 and 4. The 2024 rate beats D2 on Brier, but not the production model and not the
  flat rate. Both models rank dry-day spills better than the rate does.
- Question 2: the candidate is worse than D2 over all nine companies, worse at seven of them with the interval above
  zero, and worse at every lead.

This PR is a record: this file, the tables beside it and the harness.

### How it was run

- From a `git archive` of 68af0f8, offline, with `scripts/dry_weather_spills_eval/run.sh`. Zero network attempts in
  both steps. No Open-Meteo call.
- It waited in the group's queue (the `heavy-run.lock` in the shared notes folder) behind the radar backfill and the
  other sessions' runs. It ran alone, 25 October 2026, 17:54 to 17:58 GMT.
- Run time: the 2026 import 58 s, `score.py` 210 s. Peak memory 4.7 GB.
- Inputs: the main checkout's `data/processed` event files, annual returns and `spill_model.pkl` (copied); D2's
  candidate from `swimsignal-private/baselines/`; rain from the main checkout's `data/cache`, read only. Their SHA-256s
  are in the run's log, not committed.

### Checks of the code

All measured.
- **Rows.** 4,976,868 in 2024 and 5,077,150 in 2025, and D2's subsample of 1,569,401: D2's counts.
- **The baseline reproduces.** D2 scored 0.03615 on the 2025 rows with ERA5-Land rain (D2: 0.0362). On the lead rows
  it scored 0.03784, 0.04153, 0.04376, 0.04578 and 0.04919: #239's figures to five decimals.
- **Model files.** D2 `1603678923cc…`, production `faa7917e2be7…`, as stated.
- **Events.** 2,756,717 after merging overlaps, the live-status test's count.
- **The rule.** Before the harness was committed, the classification was checked on hand-made events: 2 overflows,
  12 days, 24 rows, each worked out by hand. All matched. That check is not committed.
- **The input.** On 2024 rows, with the row's month left out, `dry_spill_rate` ran from 0.0010 to 0.610. On 2025
  rows, 174,470 rows (3.4%) took the company rate because their overflow had no 2024 rows. No value was missing.
- **The candidate** ran the full 300 iterations. It is kept off-repo in
  `swimsignal-private/baselines/dry_weather_spills/candidate.pkl`, SHA-256 beginning `0531853a78af`.

### Seen between the harness and the run

- **A code check** of the whole chain on Thames alone, with every 2025 and 2026 label shuffled (`DRY_SPILLS_SMOKE=1`).
  It printed Thames's 2024 counts and conditions computed on the shuffled labels, which mean nothing. It found one
  bug, fixed before the harness commit: the 2026 check read United Utilities from the smoke check's one-company data.
- **The 2026 import's per-company summary** and the 2026 monthly counts of the data check (below).
- **A correction to "Seen before writing".** ERA5-Land for 2026 is not cached for every United Utilities cell. It is
  cached for 206 cells, of which 16 hold United Utilities overflows kept in 2025: 53 of 2,263. The statement said no
  fetch, so none was made. The 2026 check is therefore thin.

### Part 1: the description

At 0.25 mm. Tables: `-companies.csv` (both thresholds), `-overflows.csv` (every overflow-year with at least one dry
spill-day, 3,748 rows; the rest have none), `-top.csv`.

| | 2024 | 2025 |
|---|---|---|
| Dry overflow-days (*n*, all nine) | 633,249 | 1,181,892 |
| Dry spill-days (*k*) | 6,159 | 5,827 |
| Rate (Σ*k* / Σ*n*) | 0.0097 | 0.0049 |
| Share of all spill-days that are dry spill-days | 1.4% | 2.0% |
| Continuing days (left out) | 2,579 | 1,577 |

2025 had nearly twice as many dry days as 2024, and half the rate of spilling on them.

**By company.** *k* ≥ 5 is the share of overflows with 5 or more dry spill-days in the year.

| Company | Year | Overflows | *k* = 0 | *k* ≥ 5 | Most | Σ*k* | Rate | Share of spill-days |
|---|---|---|---|---|---|---|---|---|
| Anglian | 2024 | 1,399 | 75.8% | 6.3% | 21 | 1,204 | 0.0144 | 2.8% |
| | 2025 | 1,405 | 78.2% | 3.7% | 33 | 989 | 0.0067 | 5.8% |
| Northumbrian | 2024 | 1,370 | 87.4% | 0.4% | 22 | 276 | 0.0048 | 0.8% |
| | 2025 | 1,540 | 91.6% | 0.5% | 18 | 245 | 0.0022 | 0.9% |
| Severn Trent | 2024 | 2,382 | 89.9% | 2.1% | 21 | 750 | 0.0067 | 1.2% |
| | 2025 | 2,412 | 90.1% | 1.7% | 29 | 693 | 0.0032 | 1.9% |
| South West | 2024 | 1,345 | 84.5% | 4.2% | 27 | 781 | 0.0148 | 1.4% |
| | 2025 | 1,353 | 84.1% | 4.4% | 46 | 962 | 0.0101 | 2.1% |
| Southern | 2024 | 927 | 90.1% | 3.0% | 25 | 402 | 0.0069 | 1.4% |
| | 2025 | 941 | 93.5% | 1.8% | 45 | 350 | 0.0037 | 2.3% |
| Thames | 2024 | 577 | 80.4% | 6.9% | 31 | 521 | 0.0144 | 2.3% |
| | 2025 | 575 | 85.9% | 5.7% | 27 | 428 | 0.0070 | 4.8% |
| United Utilities | 2024 | 2,199 | 85.4% | 1.5% | 19 | 683 | 0.0092 | 0.9% |
| | 2025 | 2,263 | 92.6% | 1.2% | 24 | 430 | 0.0025 | 0.7% |
| Wessex | 2024 | 1,291 | 87.5% | 2.5% | 54 | 612 | 0.0096 | 1.4% |
| | 2025 | 1,281 | 90.7% | 2.8% | 48 | 555 | 0.0050 | 2.3% |
| Yorkshire | 2024 | 2,108 | 78.7% | 2.4% | 21 | 930 | 0.0099 | 1.4% |
| | 2025 | 2,140 | 84.6% | 3.9% | 56 | 1,175 | 0.0067 | 2.3% |

At 1.0 mm the counts are larger (Σ*k* 14,019 in 2024 and 8,946 in 2025) and the order of companies is much the same.

**Both years.** Over the 12,681 overflows with at least 30 dry days in each year, the Spearman correlation of the
2024 rate with the 2025 rate is 0.38. Of 2024's top 5% by dry spill-days (672 overflows), 44% are in 2025's top 5%.
Dry-weather spilling persists from one year to the next, but loosely.

**Top overflows,** by dry spill-days over 2024 and 2025 together.

| # | Overflow | Company | 2024: *k* / *n* | 2025: *k* / *n* | All spill-days 2024 / 2025 |
|---|---|---|---|---|---|
| 1 | WXW00571 Hurdcott WwTW | Wessex | 54 / 68 | 48 / 94 | 309 / 168 |
| 2 | SBB00037 Abbotsham WwTW | South West | 26 / 37 | 46 / 74 | 329 / 194 |
| 3 | YWS01719 Melton STW | Yorkshire | 13 / 49 | 56 / 87 | 216 / 241 |
| 4 | WXW00695 Martinstown PS | Wessex | 42 / 57 | 25 / 86 | 224 / 126 |
| 5 | SWS00478 Kings Somborne WwTW | Southern | 12 / 59 | 45 / 104 | 82 / 126 |
| 6 | TWL00378 South Moreton | Thames | 31 / 54 | 24 / 69 | 258 / 137 |
| 7 | WXW00312 Collingbourne Ducis PS | Wessex | 22 / 51 | 32 / 97 | 184 / 105 |
| 8 | AWS01027 Ramsey WRC | Anglian | 20 / 56 | 33 / 109 | 226 / 140 |
| 9 | SWS00503 Lidsey WwTW | Southern | 20 / 55 | 31 / 92 | 164 / 154 |
| 10 | WXW00498 Hanging Langford PS | Wessex | 25 / 57 | 25 / 93 | 190 / 84 |
| 11 | WXW00265 Chew Stoke WwTW | Wessex | 27 / 37 | 22 / 80 | 255 / 139 |
| 12 | TWL00293 Marlborough WwTW | Thames | 21 / 56 | 27 / 92 | 173 / 95 |
| 13 | SWS00389 Ham Lane Lewes Settles storm tank | Southern | 25 / 42 | 23 / 82 | 257 / 155 |
| 14 | SBB01034 Roborough STW | South West | 27 / 41 | 21 / 75 | 327 / 144 |
| 15 | SBB01268 Town Quay PS | South West | 18 / 34 | 27 / 65 | 259 / 193 |
| 16 | SVT02251 Sutton on Trent (Cromwell) WwTW | Severn Trent | 21 / 50 | 24 / 81 | 237 / 122 |
| 17 | SWS00496 Lavant WwTW | Southern | 16 / 30 | 28 / 91 | 286 / 104 |
| 18 | AWS00552 Hallaton STW | Anglian | 21 / 52 | 23 / 101 | 220 / 152 |
| 19 | WXW00104 Barford St Martin WRC | Wessex | 23 / 54 | 21 / 91 | 184 / 80 |
| 20 | SBB00597 Horns Cross STW | South West | 14 / 37 | 27 / 85 | 228 / 227 |
| 21 | SWS00926 West Wellow WwTW | Southern | 18 / 57 | 23 / 105 | 214 / 98 |
| 22 | SVT01447 Lydney STW | Severn Trent | 11 / 48 | 29 / 91 | 195 / 177 |
| 23 | NWL00881 Milfield STW | Northumbrian | 22 / 33 | 18 / 68 | 260 / 86 |
| 24 | AWS00810 Manthorpe STW | Anglian | 15 / 53 | 24 / 99 | 174 / 110 |
| 25 | WXW00993 Shrewton WRC | Wessex | 23 / 39 | 16 / 87 | 235 / 117 |

- These are chronic spillers, not overflows that are quiet in wet weather. The median of the 25 is 226 spill-days in
  2024 and 137 in 2025. 24 of the 25 spilled on 150 days or more in 2024.
- Nineteen are named as treatment works (WwTW, STW, WRC), five as pumping stations or a storm tank, and one (South
  Moreton) by place only.
- *Inferred from place names, not checked against geology:* at least 9 of the 25 are in chalk valleys of Wiltshire,
  Dorset, Hampshire, Berkshire and Sussex (Hurdcott, Martinstown, Collingbourne Ducis, Kings Somborne, Hanging
  Langford, Marlborough, Lavant, Barford St Martin, Shrewton). There, groundwater gets into sewers after a wet
  winter. So the rule mostly finds groundwater infiltration, and a long infiltration spell recorded as many separate
  events. Faults and blockages may be among them, but this data cannot tell them apart.

**Ambleside and Waterhead.** One United Utilities overflow matches the names: Ambleside WwTW (UUP00114), discharging
to the River Rothay. It is the only overflow in the rows within 5 km of Waterhead. It had **no dry spill-days** in
2024 (30 dry days) or 2025 (80 dry days), against 46 and 54 spill-days in all. *Inferred:* the broken sewer Tim
described is not a storm overflow, so it has no EDM monitor, and nothing in the EA's files can see it. Evidence for
it would have to come from water samples, such as his own plate counts, or from a report to United Utilities or the EA.

### Question 1: does the 2024 rate predict 2025's dry-day spills? No.

At 0.25 mm. Rows are 2025 dry days, less continuing days. Tables: `-q1-scores.csv`, `-q1-differences.csv`.

| Predictor | Brier, nine | AUC, nine | ECE, nine | Brier, eight | AUC, eight |
|---|---|---|---|---|---|
| R, shrunk 2024 rate | 0.00477 | 0.837 | 0.0047 | 0.00513 | 0.843 |
| Unshrunk 2024 rate | 0.00528 | 0.814 | 0.0049 | 0.00561 | 0.819 |
| D2 | 0.00511 | **0.888** | 0.0102 | 0.00541 | **0.891** |
| P, production | (0.00469) | (0.858) | (0.0007) | **0.00509** | 0.853 |
| F, company 2024 rate | 0.00493 | 0.623 | 0.0047 | 0.00533 | 0.617 |

Nine: 1,181,892 rows, base rate 0.0049. Eight: 1,010,903 rows, base rate 0.0053. P on all nine is in brackets: it saw
United Utilities 2025.

1. **Against production, eight companies.** R minus P: +0.00004 [−0.00020, +0.00026]. **Fails.**
2. **Against D2, nine.** −0.00033 [−0.00066, −0.00001]. Holds.
3. **Against the flat rate, nine.** −0.00015 [−0.00048, +0.00013]. **Fails.**
4. **Ranking.** R's AUC is 0.843 against P's 0.853 on the eight, and 0.837 against D2's 0.888 on the nine. **Fails.**

Per company, against production: R is clearly worse at Yorkshire (+0.00031 [+0.00015, +0.00049]) and clearly better
nowhere. Against the flat rate it is clearly better only at South West (−0.00066 [−0.00131, −0.00006]). The shrinkage
helps at every company: the unshrunk rate is worse than R everywhere, with every interval below zero.

At 1.0 mm (reported only) the answer is the same. R minus P on the eight: +0.00019 [−0.00011, +0.00047]. R minus D2:
−0.00016 [−0.00050, +0.00017]. R minus F: −0.00005 [−0.00044, +0.00029].

### Question 2: the rate as a site input. Fails all four conditions.

Tables: `-q2-scores.csv`, `-q2-differences.csv`, `-q2-subsets.csv`, `-q2-leads.csv`, `-q2-reliability.csv`.

| Company | Candidate | D2 | Difference [95%] |
|---|---|---|---|
| Anglian | 0.02850 | 0.02722 | +0.00128 [+0.00073, +0.00185] |
| Northumbrian | 0.03303 | 0.03325 | −0.00022 [−0.00058, +0.00008] |
| Severn Trent | 0.02881 | 0.02842 | +0.00039 [+0.00012, +0.00064] |
| South West | 0.05283 | 0.05190 | +0.00093 [+0.00053, +0.00135] |
| Southern | 0.02842 | 0.02771 | +0.00071 [+0.00040, +0.00105] |
| Thames | 0.03196 | 0.03031 | +0.00165 [+0.00098, +0.00232] |
| United Utilities | 0.04612 | 0.04561 | +0.00051 [+0.00027, +0.00079] |
| Wessex | 0.03331 | 0.03257 | +0.00074 [+0.00034, +0.00119] |
| Yorkshire | 0.04030 | 0.04029 | +0.00001 [−0.00041, +0.00039] |
| **All nine** | **0.03669** | **0.03615** | **+0.00053 [+0.00029, +0.00078]** |

1. **A gain.** +0.00053, interval above zero. **Fails.**
2. **No company clearly worse.** Seven are: all but Northumbrian and Yorkshire. **Fails.**
3. **Reliability.** Thames: ECE 0.0278 against D2's 0.0240, and above 0.02. **Fails.** The other eight hold.
4. **With forecast rain.** Worse at every lead: +0.00048, +0.00040, +0.00040, +0.00031 and +0.00047 at leads 0 to 4,
   every interval above zero (1,928,619 rows each). **Fails.**

Reported, not conditions:
- **AUC** is higher for the candidate at every company, by 0.000 to 0.003 (all nine 0.9300 against 0.9292). So it
  ranks a little better and is calibrated worse: ECE 0.0091 against 0.0080 over the nine.
- **On the dry rows** it is worse too: +0.00060 [+0.00032, +0.00086]. On the rest, +0.00051 [+0.00024, +0.00079].
- **Layer 1 alone:** candidate 0.03715, D2 0.03639.
- **With the company rate for every overflow:** 0.03587, below D2's 0.03615. No interval was computed for it.

### The 2026 check (United Utilities, reported only)

- **The data check.** United Utilities overflows with at least one event, 2026 against 2025, by month: January 948 /
  1,695, February 1,105 / 941, March 1,173 / 482, April 752 / 276, May 917 / 771, June 1,101 / 1,290. All six months
  pass (at least half). July (287 / 1,207) and August (1,458 / 843) were left out as stated.
- **Coverage.** 53 of 2,263 overflows have 2026 rain (above). 9,593 overflow-days, 885 dry rows, **8 dry spill-days**.

| Predictor | Brier | AUC | R minus it [95%] |
|---|---|---|---|
| R, shrunk 2025 rate | 0.00824 | 0.906 | |
| P, production | 0.00919 | 0.773 | −0.00095 [−0.00195, −0.00037] |
| D2 | 0.01044 | 0.800 | −0.00220 [−0.00424, −0.00077] |
| F, company 2025 rate | 0.00900 | 0.500 | −0.00076 [−0.00171, −0.00020] |

Here R beats all three. But this is 8 events at 53 overflows in 16 cells. It decides nothing, as stated, and it is
too small to weigh against the 5,827 dry spill-days of 2025.

### What was expected, and what happened

- **Description.** Most overflows had no dry spill-day in a year: 76% to 94% by company. That held. "Wessex, Anglian
  and South West the most, Thames the fewest per spill" was wrong. By rate, Anglian, Thames and South West lead. By
  share of spill-days, Thames and Anglian lead (4.8% and 5.8% in 2025), and United Utilities and Northumbrian are
  lowest.
- **Question 1 would most likely be yes, with condition 2 at risk.** Wrong. Condition 2 is the one that held. The
  production model is well calibrated on dry days (ECE 0.0007) and ranks them better than the rate. D2 ranks them best
  of all but forecasts too high.
- **Question 2 would most likely fail condition 1.** It failed all four.

### What this shows

- **Dry-weather spills are not a blind spot the history fills.** *Measured:* the models already rank dry-day spills
  well (AUC 0.85 to 0.89), better than the overflow's own dry-spill rate from the year before. *Inferred, not checked
  input by input:* the annual-return covariates (spill count and hours) mark the chronic spillers, and the 30-day
  rain and the antecedent index carry the wet spells that raise groundwater.
- **The rate does not carry over well between years.** It fell from 2024 to 2025 at every company: by about a third
  at South West and Yorkshire, by half at most, and by nearly three-quarters at United Utilities. *Inferred:* 2024
  was wet, so groundwater stayed high on rainless days. A rate from one year over-forecasts the next drier one. That
  is the same weakness the nine-company test found in single-year offsets.
- **Question 2 over-trusts the input.** AUC up, calibration down, worse at nearly every company. That fits the leak
  stated above: within 2024, a fault or a groundwater spell persists across months, so the model learned a stronger
  link than holds into 2025. The company-rate arm scoring below D2 hints that the candidate's layer 1 gained something
  the per-overflow value then spoiled. That is an observation after the run, with no interval, and no grounds for
  anything.
- **The EA's files cannot see Tim's broken sewer.** The only monitored overflow near Waterhead had no dry spill-day in
  either year.

### What follows

- **Nothing is adopted.** `spill_model.pkl` and `lead_calibration.json` are unchanged. Nothing reads the candidate.
- **Question 2 is not tried again without a new reason.** Two that would count: a second year of offsets (the
  nine-company test's open item), or the 2026 files complete for all nine companies, so a rate from 2025 can be fitted
  without the within-year leak.
- **The page note below is a description, not a forecast change.** Its counts are true whatever the model does.

### The page note: a proposal, not built

**What.** On an overflow's line on a spot page, and in its map pop-up, when the last full year's EA records give it at
least 10 dry spill-days and a rate of at least 0.2:

| Option | Wording (Hurdcott WwTW, 2025) |
|---|---|
| A | Often spills in dry weather. |
| B | Spilled on 48 of 94 dry days in 2025 (EA records). |
| C | Spilled on 48 of 94 dry days in 2025 (EA records). This is often a sign of groundwater in the sewer or a fault. |

My recommendation is **B**: it gives the count and claims no cause. A says less than the data has. C names causes
this data cannot tell apart. The wording is Ethan's decision.

**How many.** 46 overflows meet the rule for 2025 (South West 14, Wessex 7, Southern 6, Anglian 5, Severn Trent 4,
Yorkshire 4, Thames 3, United Utilities 2, Northumbrian 1). 91 met it for 2024. 29 meet it in both years.

**What it must say, or link to.**
- "Dry day" here means under 0.25 mm on the day and the two days before, in ERA5-Land rain over a 9 km cell. It is
  not the EA's gauge-and-radar check, and the EA has not classed these spills.
- A dry-weather spill is not a confirmed permit breach. The EA treats one as a potential breach until it investigates.
- Companies record events differently (`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`, step 1), so counts are best
  compared within a company.

**What building it needs.** A yearly count per overflow in the build from the EA's files, by this harness's rule; a
test that the build's counts equal `-overflows.csv` for 2025; and the spot pages' overflow lists. Nothing in the
forecast changes. Which listed spots have one of the 46 upstream was not checked here.
