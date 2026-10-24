# Soil moisture in the E. coli and spill models: the test, stated before any run

Written 24 October 2026. No soil moisture for the test window has been fetched, beyond the four small requests under
"Seen before writing". Nothing has been run. No score of any kind has been computed for this test. Results go below
the line at the end. Nothing above it changes after a result is seen.

## Why

Both models judge how wet the ground is from rain alone.
- **The E. coli model** has rain over 24 and 48 hours to the sample hour, overflow exposure, a lake flag and the day
  of the year (`model/ecoli.py`, `FEATURES`). Nothing in it says whether the 48-hour rain fell on wet or dry ground.
- **The spill model** has an antecedent index (`api`, daily decay `API_DECAY` 0.85), rain over 7 days and rain over
  30 days (`model/features.py`). These are rain-based stand-ins for catchment wetness.

The dry-spell test (`docs/DRY-SPELL-TEST-2026-10.md`) found that rain after dry days gave *fewer* exceedances than the
same rain after wet days: `dry3_x_lrain48` was −0.212 per SD. The reading it offered, and could not check, is that
dry soil soaks up the first rain, so less runs off. A Met Office data review on 24 October ranked soil moisture first
as a free measure of how wet the ground is. Soil moisture has never been tested in this repo.
`docs/GLOFAS-CHECK-2026-11.md`, §"2. Flow as a catchment-wetness input", names ERA5-Land soil moisture as a comparator
for the spill model. This test uses that framing.

There are two questions. They are scored on their own and decided on their own.
- **Question 1, E. coli model:** does soil moisture at the sample's rain cell improve the E. coli exceedance model,
  as a main term, or as a main term with an interaction with `lrain48`?
- **Question 2, spill model:** does soil moisture add to the rain-based wetness inputs, or beat them?

## The data

### Which source has UK soil moisture for which dates (checked before writing)

Four requests, listed under "Seen before writing":
- **Open-Meteo Previous Runs API, lead 0** (`https://previous-runs-api.open-meteo.com/v1/forecast`): hourly
  `soil_moisture_0_to_1cm`, `_3_to_9cm`, `_9_to_27cm` and `_27_to_81cm` came back full on 1 June 2023 and 1 October
  2026 at (54.4, −2.9). `soil_moisture_9_to_27cm_previous_day1` came back empty, as `shortwave_radiation_previous_day1`
  did in the die-off test. So lead 0 covers 2023 to 2026, and archived soil-moisture *forecasts* (leads 1 to 4) are
  not available.
- **Open-Meteo archive API, `models=era5_land`**: hourly `soil_moisture_7_to_28cm` came back full on 31 December 2025
  at two points, one inland and one on the Solent shore. The returned points sit on ERA5-Land's 0.1° grid.
- **The archive API's default model** returned `soil_moisture_0_to_7cm`, `_7_to_28cm` and `_28_to_100cm` too, but at a
  point off ERA5-Land's 0.1° grid (54.376, −2.818 for 54.4, −2.9). So the default is not ERA5-Land for soil moisture.
  Question 2 names `models=era5_land` explicitly.

### Question 1: Previous Runs lead 0, 9 to 27 cm

- **Source:** the same API and lead the E. coli model's rain comes from (`ingest/rainfall_leads.py`, lead 0; the model
  is fitted on lead-0 forecast rain). The live forecast would use the forecast API's figure of the same kind.
- **Where:** the sample's rain cell (`rainfall.grid_cell`, 0.1°), for every bathing water in the E. coli rows. The
  die-off test counted 32 cells.
- **When:** 1 April to 30 September of 2023, 2024, 2025 and 2026. The samples run from 3 May to 7 September, and the
  input reads 48 hours before the sample.
- **The input:** `sm` = `soil_moisture_9_to_27cm` (m³/m³) at the hour 48 hours before the sample hour, that is at
  floor(t) − 48 h, with t the sample time. It is the state of the ground *before* the 48-hour rain window began, so it
  says how wet the ground was when that rain started. It carries none of the window's rain. A row with no value at that
  hour is missing.

### Question 2: ERA5-Land, 7 to 28 cm

- **Source:** ERA5-Land on the archive API, like the training rain.
- **Where:** each overflow's 0.25° node: lat and lon rounded to the nearest 0.25°. 343 nodes cover the 14,076
  overflows in D2's 2024 and 2025 rows. The rain cells are 0.1°, 1,622 of them. Why the coarser grid:
  - **The budget.** One variable for a year weighs 2.6 calls a location (`rainfall.call_weight`). At 0.1° the two
    years cost about 8,500 calls, nearly three days of this machine's ration. At 0.25° they cost about 1,790.
  - **ERA5-Land's weather comes in at about 31 km.** ERA5-Land is driven by ERA5's atmosphere (0.25°) brought down to
    0.1°. So its day-to-day wetting and drying, the signal this test is after, varies on the 0.25° scale. Its finer
    detail comes from soil type, land cover and height. *Inferred from how ERA5-Land is made, not measured here.*
  - Open-Meteo returns the nearest ERA5-Land point to each node. The returned points are recorded.
- **When:** 1 January 2024 to 31 December 2025, hourly.
- **The input:** `sm28` = `soil_moisture_7_to_28cm` (m³/m³) at 00:00 UTC of day *d*, the issue time of a lead-0
  forecast for day *d* (the live-status test's convention). It carries none of day *d*'s rain. A day with no value
  is missing (NaN) and the boosted model takes it as it is. The count is reported.

### Why these layers, and only these

One layer per question, picked now, before any score:
- **Not the top layers** (0–1, 1–3, 3–9 cm; ERA5-Land 0–7 cm). They wet within hours of rain and dry within a day or
  two of sun. They would mostly re-describe the 24- and 48-hour rain both models already have.
- **Not the deep layers** (27–81 cm; ERA5-Land 28–100 cm). They move over months. Over May to September at one site
  they barely change, and for the spill model the season terms and `rain_30d` already carry part of that.
- **The root zone, 9–27 cm and 7–28 cm.** It holds wetness over days to weeks: the memory the dry-spell reading points
  to and the antecedent index stands in for. The two questions read about the same depth, so their results can be set
  side by side.
- **Raw values, not each site's anomaly.** A clay soil holds more water than a sand at the same wetness. Raw values
  are what production would read directly. The limit is stated now: raw `sm` partly tells the model which site it is.
  Leave-one-site-out (Question 1) and the per-company condition (Question 2) are where that would show.

### The fetch and its budget

- **Question 1:** 32 cells × 4 years × 2 requests (April–June, July–September). A request is one variable over at most
  92 days, weight 1 a location: **256 calls**. 4 cells a request, as the die-off fetch found works on this API
  (`docs/DIEOFF-WEATHER-TEST-2026-10.md`).
- **Question 2:** 343 nodes × 2 years, one variable: 2.61 a node-year, **about 1,790 calls**. 5 nodes a request,
  paced at 3,000 calls an hour as `scripts/fetch_rain_nine.py` paces.
- **Together about 2,050 calls**, under the 3,000 a day this machine keeps to while other sessions share the IP. The
  fetch is strict: it stops at the first refusal or a body that is not JSON. A failed piece is retried once by quarter
  (Question 2) or by month (Question 1). What still fails stays missing and is counted.
- The cache is written to `data/cache/soil/` of the main checkout. Nothing is written into a data folder a run reads.

## Question 1: the E. coli model

### The arms

Today's seven inputs, plus:
- **`main`:** `sm`.
- **`interaction`:** `sm` and `sm_x_lrain48` = `sm` × `lrain48`, the model's own log1p of the 48-hour rain.

All are standardised like the other inputs. Nothing else in the model changes.

### Expected sign, from the dry-spell reading

If dry soil soaks up the first rain, the same rain on wet ground runs off more. So:
- in `main`, `sm`'s coefficient is above zero: wetter ground, more exceedances;
- in `interaction`, `sm_x_lrain48`'s coefficient is above zero: wet ground makes the same rain count for more. `sm`
  then has no sign condition, because with the product in the model it describes ground wetness on a day with no
  rain.

### The evaluation

`scripts/train_ecoli.py`'s own evaluations, run on the same rows three times: reference, `main`, `interaction`. The
rows are the samples it uses today, less any missing `sm`. Rows dropped are counted. All three arms share the rows.
- **Leave one year out** (LOYO): the Brier score, all, rivers and lakes.
- **Leave one site out** (LOSO): the Brier score.
- **Forward:** fitted to 2024, scored on 2025–26.
- **Interval:** its cluster bootstrap over (site, ISO week) blocks on the LOYO predictions, for the Brier difference,
  with its seed.

### An arm passes if all five hold

1. **LOYO Brier, all.** It improves by at least 0.0005, and the 95% interval of the improvement is above zero.
2. **LOSO Brier, all.** No worse than the reference by more than 0.0005.
3. **Forward Brier.** No worse than the reference by more than 0.0005.
4. **Rivers and lakes apart (LOYO).** Neither is worse by more than 0.0005.
5. **The sign.** In the model fitted on all rows: `main`, `sm` above zero; `interaction`, `sm_x_lrain48` above zero.

**Question 1 passes** if either arm passes. If both pass, `main` is the one taken forward, unless `interaction`'s LOYO
Brier is lower than `main`'s by at least 0.0005. The simpler model wins a tie.

## Question 2: the spill model

### The arms

The nine-company model's design (`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`, D2), with:
- **`add`:** D2's fifteen inputs plus `sm28`. Does soil moisture add to the rain-based wetness inputs?
- **`replace`:** D2's inputs without `api`, `rain_7d` and `rain_30d`, plus `sm28`. Does soil moisture beat them?

`sm28` is monotone: it may only raise the probability, as each rain input may (`features.MONOTONE`). Wetter ground,
more runoff into the sewers. Nothing else changes.

### Rows, fit and baseline

- **Rows.** Exactly D2's rows, built by D2's code (`train._frame`): 4,976,868 site-days in 2024 and 5,077,150 in 2025,
  from the EA start/stop files in the main checkout. The script stops if it gets other counts, or a subsample other
  than D2's 1,569,401 rows.
- **Fit.** Each arm is fitted on the 2024 rows with D2's settings: `fit_pooled` with `neg_frac` 0.25 and seed 0, then
  `fit_site_offsets` with prior strength 15 and recency 1 on the arm's own 2024 predictions. Nothing is tuned on 2025.
- **Baseline.** D2's candidate, `spill_model_nine_2024.pkl`, SHA-256 `1603678923ccdd15…`, kept off-repo in
  `swimsignal-private/baselines/`. On the 2025 rows it must give 0.03615 (D2's 0.0362; the live-status test's
  0.03615). The script stops if it does not.
- **A refit check, reported only:** D2's inputs fitted by this script's code, scored on 2025. It shows whether the
  harness's fit is D2's.

### Verification on 2025, ERA5-Land rain

Every predictor on the same rows, against the label "the overflow spilled that day". Per company and for the nine
together: rows, base rate, Brier, AUC, ECE (D2's definition) and a 10-bin reliability table. Paired differences in
Brier (arm minus baseline) get 95% intervals from the live-status test's cluster bootstrap by ISO calendar week of
the UTC day: 2,000 resamples from `numpy.random.default_rng(0)`, every row of a week drawn together, one set of draws
for every company and arm.

Forecast rain is not scored. Archived soil-moisture forecasts do not exist (above), so the lead rows would mix forecast
rain with reanalysed soil moisture. This test is the lead-0, reanalysis test D2 itself was.

### An arm passes if all three hold

1. **A gain, all nine.** The arm's Brier is lower than the baseline's, and the 95% interval of the difference lies
   wholly below zero.
2. **No company clearly worse.** At no company is the arm's Brier higher with the interval lying wholly above zero.
3. **Reliability.** At each company, the arm's ECE is no higher than the baseline's, or it is at most 0.02.

**Soil moisture adds** if `add` passes. **Soil moisture beats the rain proxies** if `replace` passes.

## What is expected, stated now

- **Question 1 will most likely fail condition 1 in both arms.** The samples run from May to September, when the
  root zone is dry at most sites most of the time, and `lrain48` already separates wet days from dry. With about 1,500
  rows and 212 exceedances, a gain of 0.0005 with an interval above zero is a high bar. The dry-spell result's sign
  says `sm_x_lrain48` should come out above zero. LOSO is the condition most at risk, because raw soil moisture
  partly tells the model which site it is.
- **Question 2, `add`: a small gain, with an interval that most likely reaches zero.** The antecedent index and the
  30-day rain already carry most of what the root zone remembers. If there is a gain, it is most likely at the
  companies whose 2024 spells ran longest (Thames, South West, Southern, Anglian; `-spells-2024.csv`).
- **Question 2, `replace`: worse than D2.** Thirty days of rain carries memory longer than the root zone's. I expect
  it to fail condition 1 with a Brier above the baseline's.

## Running

- The harness is `scripts/soil_moisture_eval/`: `fetch.py`, `q1.py`, `q2.py` and `run.sh`. It is committed after this
  file and before the fetch. The statement above the line does not change when it is added.
- **The fetch** runs from the harness commit, once, from this machine, before any score.
- **Question 1** runs from a `git archive` of the harness commit, offline (every outgoing connection refused and
  counted, `scripts/lake_distance_eval/run_offline.py`), on a fresh scratch root copied from the frozen data folder
  the die-off and dry-spell tests ran on (overflow key b5724303). Its hashes go in the results. The chain is the
  dry-spell test's: `validate_ecoli.py`, `replay_ecoli_leads.py`, `train_ecoli.py`, then `q1.py`. So the reference arm
  is today's model on today's code, and its scores can be set beside the dry-spell reference run (LOYO 0.09215) as a
  face check.
- **Question 2** runs from the same archive, offline, on a scratch root with copies of the main checkout's
  `annual_returns.parquet`, EA start/stop files and D2's baseline, reading the rain caches in place. Their hashes go in
  the results.
- Each run alone. It starts when `memory_pressure` reads 35% free or more and no other evaluation, training, build,
  radar backfill or radar test runs on this machine.

## What follows

**Question 1 passes.** The arm taken forward is added in a separate PR. Before it ships, the live request adds
`soil_moisture_9_to_27cm` to the spots' forecast request. Two variables over its 37 days (31 past, 5 ahead and today)
still weigh 1 a location by `rainfall.call_weight`, so no calls are added. Leads 1 to 4 cannot be scored, because the Previous Runs API keeps no archived soil-moisture
forecasts. The adoption PR states how it handles that before it runs. Outside May to September the input is held
inside the range seen in the samples, following `ecoli.season_day`'s rule.

**Question 2 passes.** A pass deploys nothing. 2025 has already judged D2, the neural challenger, the live-status
input and the covariate-year test. A pass earns two things, each stated before it runs:
- a confirmation on 2026 data;
- a test of the switch production would make: the live forecast reads the forecast API's soil moisture, a different
  model and depth (9–27 cm) from ERA5-Land, because ERA5-Land arrives about five days late.

The production change is Ethan's call after that.

**Either fails.** That part changes nothing. This PR stays a record: this file, the results and the harness.

Changing a model input is allowed until the 2027 freeze tag (`docs/PREREGISTRATION-2027.md`). The PR is left for
Ethan to merge.

## What will be reported

Whatever the verdict:
- each condition with its figure and interval;
- Question 1: every evaluation's table for the three arms, the coefficients per SD, `sm`'s mean, SD and range, its
  correlation with `lrain48`, and the spread of site means;
- Question 2: per company and all nine, each arm's and the baseline's Brier, AUC and ECE; the differences with their
  intervals; the reliability tables; the refit check; on the 2024 rows, `sm28`'s correlation with `api`, `rain_7d`
  and `rain_30d`; rows with `sm28` missing;
- calls spent, rows dropped, run time, peak memory and network attempts.

## Seen before writing

- **The published figures.** The dry-spell test's reference run on the frozen folder: LOYO 0.09215, LOSO 0.09119,
  forward 0.08240, 1,502 rows, 212 over 900 (`docs/DRY-SPELL-TEST-2026-10.md`). D2's 2025 Brier 0.0362, and the
  live-status test's reproduction, 0.03615 (`docs/LIVE-STATUS-FEATURE-TEST-2026-10.md`).
- **The four probe requests** (24 October, about 22:10 BST), whose output was counts of non-empty hours and the
  returned grid points only. No soil-moisture value was printed or read.
  1. Previous Runs, (54.4, −2.9), 1 June 2023: lead 0 of the four layers, 24 of 24 hours each;
     `soil_moisture_9_to_27cm_previous_day1` 0 of 24.
  2. The same on 1 October 2026: the same counts.
  3. Archive, default model, (54.4, −2.9) and (50.75, −1.5), 1 January 2024: three ERA5 layers, 24 of 24; returned
     points (54.376, −2.818) and (50.721, −1.439).
  4. Archive, `models=era5_land`, the same two points, 31 December 2025: `soil_moisture_7_to_28cm` 24 of 24; returned
     points (54.400, −2.900) and (50.800, −1.500).
- **Counts.** D2's 2024 and 2025 site lists from the main checkout's annual returns and EA files: 14,076 overflows,
  1,622 rain cells at 0.1°, 505 nodes at 0.2°, 343 at 0.25°. The E. coli rows in the frozen folder: 2,165, sample
  times 3 May 2023 to 7 September 2026, by month May 370, June 516, July 517, August 491, September 271. No rain,
  E. coli, spill or risk figure was looked at.
- No score of any kind has been computed for this test.
