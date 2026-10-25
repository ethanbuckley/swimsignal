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

---

## Results

Added 25 October 2026, after the run. Everything above the line is as committed in deebe56 (24 October 2026, 22:20
BST) and pushed before any soil moisture was fetched. The harness came in 0dd7172 (22:23 BST), before the fetch. It
changed nothing above the line.

**Verdict.**
- **Question 1 passes.** Arm `main`, soil moisture as a main term, meets all five conditions. Arm `interaction` meets
  conditions 1 to 4 and fails condition 5: the product's sign is the opposite of the one stated. By the stated rule,
  `main` is the arm taken forward.
- **Question 2 fails.** Neither arm passes. `add` meets condition 1 and fails conditions 2 and 3. `replace` fails
  all three.

Nothing is adopted in this PR. Question 1's pass means a separate adoption PR, for Ethan to decide. Files beside this
one: `-q1.json` (every Question 1 figure), and `-q2-scores.csv`, `-q2-differences.csv`, `-q2-reliability.csv`,
`-q2-nodes.csv` and `-q2-checks.json`.

### How it was run

- **The fetch.** 24 October, 22:23 to 23:10 BST, from the harness commit. 242 requests. 2,087 calls were logged by
  Open-Meteo's rule, plus 6 for the four probes: about 2,093 in all, against about 2,050 stated. The extra comes from
  two Question 2 year requests that ended in a connect timeout. Each was logged at full weight (13), then fetched
  again by quarter, as stated. No piece failed after that. Question 1: 32 cells × 4 seasons, 0 missing hours.
  Question 2: 343 nodes × 2 years. 298,248 hours are missing, which is 17 nodes with no value at any hour
  (17 × 17,544). The cache hashes to `e5602fb6` (SHA-256 of the `shasum -a 256` listing of its 814 parquet files).
- **The wait.** Each run waited for the Met Office radar backfill and the radar test that followed it to finish, then
  for the group's `heavy-run.lock` to be free, 10 quiet minutes and 35% memory free. It started at 11:48 GMT on 25
  October with 58% free. The first waiter could never have ended: its own command line held the text it searched for.
  It was replaced before anything ran. Nothing was scored twice.
- **The run.** From a `git archive` of 0dd7172, offline, 11:48:19 to 11:57:08 GMT, with `run.sh q1`, then
  `run.sh q2`. 0 network attempts in all five steps. `which.log` shows the archive's own `dipcast`. Run times:
  `validate_ecoli` 166 s, `replay_ecoli_leads` 73 s, `train_ecoli` 94 s, `q1.py` 17 s, `q2.py` 176 s. Peak memory
  4.4 GB (`replay_ecoli_leads`) and 5.2 GB (`q2.py`).
- **Question 1's data.** The frozen folder the die-off and dry-spell tests ran on. Overflow table `ebc96774` (key
  b5724303), river network `fc66101d`, `bwq_samples.parquet` `26f5f646`, as the die-off test records. The 102 files of
  `processed` and `raw` (river network excepted) hash to `dbded7ac`, the SHA-256 of their sorted `shasum -a 256`
  listing. The dry-spell test's `6e13bee2` does not record its method, so the two cannot be compared.
- **Question 2's data.** The main checkout's `annual_returns.parquet` (`9f8604f9`) and the nine EA start/stop files,
  copied; their SHA-256 values are in `-q2-checks.json`. D2's baseline `1603678923ccdd15`. Rain was read in place from
  the main checkout's caches: 4,869 files for 1,623 cells.
- **Main's defaults:** velocity 0.2 m/s, T90 72 h, dilution power 0.5, lake path `residence_spill`.

### Face checks. All hold.

- **Question 1.** The reference arm equals `train_ecoli.py`'s own scores in the same root: LOYO 0.0921, LOSO 0.0912,
  forward 0.0824, 1,502 rows. These are the dry-spell test's reference figures. No row was dropped for a missing `sm`.
  212 of the 1,502 are over 900. 31 sites.
- **Question 2.** D2's rows: 4,976,868 and 5,077,150, and the subsample of 1,569,401. The baseline gives 0.03615 on
  2025. The refit of D2's own inputs by this harness gives the baseline's predictions exactly: a difference of 0.0 at
  every company. So the harness's fit is D2's.

### Question 1: the E. coli model

**The input.** `sm` over the 1,502 rows: mean 0.271 m³/m³, SD 0.100, range 0.059 to 0.489. Rivers 0.236, lakes 0.325.
Correlation with `lrain48` 0.395, with `lrain24` 0.258. Site means run from 0.101 to 0.377. 59% of `sm`'s variance lies
between sites, and 41% within them.

| Held-out Brier | Reference | `main` | `interaction` |
|---|---|---|---|
| LOYO, all (1,502) | 0.09215 | 0.08508 | 0.08457 |
| LOYO, rivers (907) | 0.13537 | 0.12356 | 0.12273 |
| LOYO, lakes (595) | 0.02625 | 0.02643 | 0.02641 |
| LOSO, all | 0.09119 | 0.08710 | 0.08683 |
| Forward, 2024 to 2025–26 (997) | 0.08240 | 0.07965 | 0.08008 |
| LOYO AUC | 0.8164 | 0.8517 | 0.8541 |
| LOYO log loss | 0.3133 | 0.2886 | 0.2872 |

LOYO gain over the reference, from the (site, ISO week) cluster bootstrap over 1,325 clusters:

| | Gain | 95% interval |
|---|---|---|
| `main`, all | +0.00706 | +0.00271 to +0.01158 |
| `main`, rivers | +0.01182 | +0.00470 to +0.01920 |
| `interaction`, all | +0.00757 | +0.00347 to +0.01187 |
| `interaction`, rivers | +0.01265 | +0.00584 to +0.01972 |

**`main`: passes all five.**
1. LOYO gain +0.00706, at least 0.0005, and the interval lies above zero. Holds.
2. LOSO is 0.00409 better. Holds.
3. Forward is 0.00275 better. Holds.
4. Rivers are 0.01182 better. Lakes are 0.00018 worse, inside the 0.0005 margin. Holds.
5. `sm` is +0.845 per SD, above zero. Holds.

**`interaction`: fails condition 5.**
1. LOYO gain +0.00757 with the interval above zero. Holds.
2. LOSO is 0.00436 better. Holds.
3. Forward is 0.00233 better. Holds.
4. Rivers are 0.01265 better. Lakes are 0.00016 worse. Holds.
5. `sm_x_lrain48` is −0.543 per SD, below zero. Fails. `sm` is +1.011 and `lrain48` is +1.066.

`interaction`'s LOYO Brier is 0.00051 lower than `main`'s. That would have reached the 0.0005 tie-break, but the
tie-break applies only when both arms pass.

**Coefficients per SD, reference against `main`:**

| | `lrain48` | `lrain24` | `logit_risk` | `lake` | `lake_x_lrain48` | `doy_sin` | `doy_cos` | `sm` |
|---|---|---|---|---|---|---|---|---|
| Reference | 0.651 | −0.102 | 0.781 | −0.181 | −1.057 | −0.097 | 0.086 | |
| `main` | 0.657 | 0.058 | 0.543 | −0.626 | −1.190 | −0.233 | −0.032 | 0.845 |

### Question 2: the spill model

**The input.** `sm28` on the 2024 rows: mean 0.358 m³/m³, SD 0.074, range 0.078 to 0.748. Correlation with `api`
0.337, with `rain_7d` 0.299, with `rain_30d` 0.356, with `rain_d` 0.060. Missing: 39,528 of the 2024 rows (0.8%) and
43,435 of the 2025 rows (0.9%). These are the overflows whose node returned no value. The returned ERA5-Land point lies
a median of 5.6 km from the requested node. It is over 10 km at 22 of the 343 nodes and 17.1 km at most; those are
coastal nodes, where the nearest land point is used.

All nine companies, 2025, ERA5-Land rain, 5,077,150 rows:

| | Brier | AUC | ECE | Difference from baseline [95%] |
|---|---|---|---|---|
| Baseline (D2) | 0.03615 | 0.9292 | 0.0080 | |
| `add` | 0.03591 | 0.9300 | 0.0077 | −0.00025 [−0.00043, −0.00008] |
| `replace` | 0.03768 | 0.9250 | 0.0106 | +0.00153 [+0.00092, +0.00221] |

Per company, the difference in Brier (arm minus baseline) with its 95% interval:

| Company | Baseline | `add` | `replace` |
|---|---|---|---|
| Anglian | 0.02722 | **+0.00050 [+0.00012, +0.00094]** | **+0.00388 [+0.00236, +0.00569]** |
| Northumbrian | 0.03325 | −0.00010 [−0.00033, +0.00009] | +0.00041 [−0.00020, +0.00114] |
| Severn Trent | 0.02842 | −0.00015 [−0.00031, −0.00001] | **+0.00129 [+0.00069, +0.00198]** |
| South West | 0.05190 | −0.00062 [−0.00118, −0.00017] | **+0.00184 [+0.00088, +0.00284]** |
| Southern | 0.02771 | −0.00028 [−0.00054, −0.00004] | **+0.00093 [+0.00011, +0.00176]** |
| Thames | 0.03031 | −0.00029 [−0.00070, +0.00011] | **+0.00390 [+0.00212, +0.00598]** |
| United Utilities | 0.04561 | −0.00059 [−0.00087, −0.00033] | **+0.00085 [+0.00027, +0.00145]** |
| Wessex | 0.03257 | −0.00057 [−0.00123, −0.00011] | **+0.00190 [+0.00070, +0.00325]** |
| Yorkshire | 0.04029 | −0.00013 [−0.00038, +0.00007] | **+0.00100 [+0.00035, +0.00168]** |

Bold: the interval lies wholly above zero, so the company is clearly worse.

**`add`: fails conditions 2 and 3.**
1. A gain, all nine: −0.00025, with the interval wholly below zero. Holds.
2. No company clearly worse: Anglian is +0.00050 [+0.00012, +0.00094]. Fails.
3. Reliability: Thames's ECE is 0.0242, against the baseline's 0.0240, and above 0.02. Fails. The baseline already
   fails 0.02 at Thames, as D2 recorded.

**`replace`: fails all three.**
1. It is +0.00153 worse, with the interval wholly above zero. Fails.
2. Eight of the nine companies are clearly worse. Northumbrian is the exception. Fails.
3. ECE is above the baseline's and above 0.02 at Anglian (0.0213) and Thames (0.0333). Fails.

Reported only: `replace` minus `add`, all nine, is +0.00178 [+0.00114, +0.00250]. On the 2025 rows with `sm28`
missing, `add` is 0.00037 better than the baseline and `replace` is 0.00010 better. Layer 1 alone, all nine:
baseline 0.03639, `add` 0.03616, `replace` 0.03771.

### Against what was expected

- **Question 1.** Expected: fail condition 1 in both arms. Wrong: both arms passed condition 1 by a wide margin, with
  gains of 0.0071 and 0.0076 against a margin of 0.0005. Expected: `sm_x_lrain48` above zero. Wrong: it came out at
  −0.543. Expected: LOSO most at risk. Wrong: LOSO improved by 0.0041.
- **Question 2, `add`.** Expected: a small gain whose interval reaches zero, largest at Thames, South West, Southern
  and Anglian. Partly wrong. The gain is small (−0.7%), but its interval lies below zero. It is largest at South West,
  United Utilities and Wessex. Anglian is the one company made clearly worse, and Thames's change crosses zero.
- **Question 2, `replace`.** Expected: worse than D2, failing condition 1. Right.

### What this shows

Established, on these rows:
- Root-zone soil moisture 48 hours before the sample improves the E. coli model on every held-out evaluation. Held-out
  Brier falls by 7.7% over years (0.0921 to 0.0851), by 4.5% over sites, and by 3.3% in the forward test. AUC rises
  from 0.816 to 0.852. The gain is on rivers. Lakes are unchanged within 0.0002.
- Wetter ground means more exceedances: `sm` is +0.845 per SD, the largest coefficient in the model.
- With `sm` in, the weight on overflow exposure falls from 0.781 to 0.543 per SD, and the lake term moves from −0.181
  to −0.626.
- In the spill model, soil moisture adds a little in 2025 (−0.7%) but makes Anglian worse. It cannot replace the
  antecedent index and the 7- and 30-day rain: without them the model is worse at eight of nine companies.

Inferred, not tested:
- **The interaction's sign.** The product is negative: on wet ground, extra rain raises the risk *less*. One reading:
  wet ground already gives high counts without rain, through drainage, base flow and field runoff, so the next rain
  adds less on the logistic scale. This does not fit the dry-spell test's reading, that dry soil soaks up the first
  rain. That test's product was negative too. Both results say more about how rain and wetness overlap in a logistic
  model than about a mechanism. Neither test can separate the two.
- **Between or within sites.** 59% of `sm`'s variance is between sites. LOSO improved, so the between-site part
  generalises to sites the model has not seen. It does not just label sites the model knows. But a site's mean soil
  moisture may stand in for other things about its catchment, such as upland, wet-west or grazed land. The fall in the
  overflow weight hints that part of what `sm` carries was being credited to overflows. This test cannot tell how much
  of the gain is day-to-day wetness and how much is a fixed property of the catchment.
- **Why the spill model gains so little.** The rain proxies already carry most of what ERA5-Land's root zone knows.
  The correlations of 0.30 to 0.36 are low, but the boosted model already uses the proxies' shape. *Not checked.*

### What follows

**Question 1 passed: a separate adoption PR for `main`.** As stated above the line, it adds
`soil_moisture_9_to_27cm` to the spots' forecast request (no added calls), holds the input inside its sample range
outside May to September, and states before it runs how it handles leads 1 to 4, for which no archived soil-moisture
forecasts exist. *Inferred:* at leads 0 and 1 the value at t − 48 h is already in the past at issue. At leads 2 to 4
it is a forecast of 12 to 60 hours. Before that PR, these questions need their own pre-stated checks on data this test
has not seen:
- does the gain hold with `sm` as each site's anomaly (day-to-day wetness only), and with a site's mean alone (a
  fixed catchment property)? The answer decides what the page may say soil moisture means;
- does it hold on the 2027 season's samples, or on Tim Boden's Waterhead and Lakeside counts when they arrive?

The change itself is Ethan's call.

**Question 2 failed. Nothing changes.** `spill_model.pkl` and `lead_calibration.json` are untouched, and no arm was
saved. The ERA5-Land soil cache stays in `data/cache/soil/` (not in the repo) for any later test.

Changing a model input is allowed until the 2027 freeze tag (`docs/PREREGISTRATION-2027.md`). The PR is left for
Ethan to merge.
