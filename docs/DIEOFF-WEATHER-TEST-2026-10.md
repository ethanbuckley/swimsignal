# Sunlight and temperature in die-off: the test, stated before any run

Written 23 October 2026. No weather data for this test has been fetched, beyond the one-day check under "Seen before
writing". Nothing has been run. Results go below the line at the end. Nothing above it changes after a result is seen.

## Why

Faecal bacteria die faster in sunlight and in warm water. The model ignores both.
- **On the way to the spot.** The transport step kills bacteria at one fixed rate: 90% gone in 72 hours
  (`config.T90_HOURS`, fitted in `docs/TRANSPORT-FIT-TEST-2026-10.md`). A bright July day and an overcast one get the
  same rate.
- **At the spot.** The E. coli model's inputs are rain over 24 and 48 hours, overflow exposure, a lake flag and the
  day of the year (`model/ecoli.py`, `FEATURES`). None is sunlight or temperature.

On 23 October Ethan asked which monitoring methods in a UKCEH article (Love Windermere, "How and why do you measure
that?") the models do not use. This test was the first pick from that review. The article itself covers temperature
sensors, not sunlight. Adding sunlight is this test's idea.

There are two questions. They are scored on their own and decided on their own.
- **Question 1, on the way:** does a die-off rate that moves with sunlight and temperature rank river sample days
  better than the fixed rate?
- **Question 2, at the spot:** does the E. coli model predict exceedances better with sunlight and temperature as
  inputs?

## The weather data

**Source:** Open-Meteo's Previous Runs API, lead 0 (`https://previous-runs-api.open-meteo.com/v1/forecast`), hourly:
- `shortwave_radiation`: sunlight reaching the ground, mean W/m² over the preceding hour;
- `temperature_2m`: air temperature 2 m above ground, °C.

This is the same API and lead the E. coli model's rain already comes from (`ingest/rainfall_leads.py`; the model is
fitted on lead-0 forecast rain, `ecoli_model_eval.json` `rain_source`). So the live forecast would use the same kind
of figure.

**Where:** the weather cell (`rainfall.grid_cell`) of each bathing water. 32 cells for the 38 bathing waters. The
whole journey from an overflow uses the spot's cell. Overflows up to 60 km away sit under other skies. That is a
simplification, stated now.

**When:** calendar years 2023 to 2026, to the API's latest day.

**Air, not water, temperature.** No water-temperature record covers the bathing waters in these years. The EA's sondes
cover few places (`ingest/water_temperature.py`). So the test uses the mean air temperature over the 24 hours to each
hour, as a stand-in that moves more slowly than air. Rivers lag air temperature by more than that, and lakes by far
more. This is stated now as a limit.

**Sunlight at the surface, not in the water.** Muddy water after rain blocks most light within centimetres. Neither
question can see turbidity. Rain in the model stands in for it, partly.

**The fetch:** 2 variables × 365 days is weight 5.2 per cell-year by Open-Meteo's rule (`rainfall.call_weight`). So
32 cells × 4 years costs about 670 calls. It runs once, from this machine, strict (stop at the first refusal), paced as
`fetch_archive` is, and not while a build or another fetch runs here. It is cached as `weather_leads_<cell>_<year>.parquet`.
A cell-year that fails stays missing. The rows it touches are dropped from both questions and counted.

## Question 1: die-off on the way

### What changes

Today a spill's weight at the spot is `dilution × 10^(−travel_h / 72)`, the same on every day. Under test, the
die-off follows the hours the water travels:

- survival = exp(−Σ k(h)), over the hours h of the journey, one hour each;
- the journey ends at 12:00 London time on the arrival day (`ecoli.SAMPLE_HOUR`) and starts `travel_h` earlier;
- k(h) = k₀ × [ (1 − s) × θ^(T(h) − T̄) + s × I(h) / Ī ], with k₀ = ln 10 / 72 h, today's rate.

Where:
- I(h) is sunlight and T(h) the 24-hour mean air temperature, at the spot's cell;
- Ī and T̄ are their means over every hour of May to September, 2023 to 2026, at all 32 cells, worked out from the
  weather alone before any score;
- s is the share of the average die-off that sunlight drives;
- θ sets how fast die-off rises with temperature. At θ = 1.07 it doubles for 10 °C warmer.

At average weather k(h) = k₀ for every setting. So the test moves die-off from day to day without moving its average,
which the transport fit already set. Any gain comes from the weather's day-to-day changes, not from a new average.

**Not changed:** the river speed (0.2 m/s), the dilution exponent (0.5), L0, the 60 km cap, and the lake rules. A lake
on the way keeps its residence pass (`transport.lake_pass`) at 72 hours. Only the moving part of the journey takes the
weather rate.

### The grid

s in {0, 0.25, 0.5, 0.75} × θ in {1.00, 1.04, 1.07}: 12 settings. s = 0 with θ = 1.00 is today's model exactly, and is
the reference.

Expected shape, stated now. In summer, sunlight swings far more from day to day than the 24-hour air temperature. So s
should matter more than θ.

### The code change

`transport` gains an optional hourly decay-rate series per spot. When it is not given, the weights are today's to
within 1e-12. A test in `tests/` checks that. The harness passes the weather rate. Production does not change unless
Question 1 passes.

### The evaluation

As in `docs/TRANSPORT-FIT-TEST-2026-10.md`, with the 12 settings in place of its 75:
- the hindcast of `scripts/validate_ecoli.py` on the site's pins. Spill chances come once per bathing water, from
  reanalysis rain and the spill model, calibrated as lead 0. Only the transport step runs per setting;
- risk = 1 − ∏(1 − p·w), with w now by arrival day;
- rows: samples at bathing waters with overflows upstream that have a figure under all 12 settings and weather for
  every travel window. Rivers and lakes apart.

**Score:** within-site Spearman of the risk against log10 E. coli is the main score. Pooled AUC over 900 cfu/100 ml is
the second.

**Selection: leave one year out, on rivers.** For each year Y of 2023 to 2026:
1. score the 12 settings on the other three years' river samples;
2. take the best, with a tie going to the reference and then to grid order;
3. score it on year Y.

The four held-out years are pooled. The reference is scored on the same rows. Lakes are scored with the river picks.

**Interval:** a cluster bootstrap by calendar week (ISO year and week), 2,000 resamples, numpy
`default_rng(20261023)`. The 95% interval runs from the 2.5th to the 97.5th percentile of the pick-minus-reference
difference.

### Question 1 passes if all four hold

1. **Rivers, within-site Spearman.** The held-out change is above zero, and the interval's lower end is above zero.
2. **Rivers, AUC over 900.** The change is at least −0.005, and the interval's upper end is above zero.
3. **Lakes, within-site Spearman, with the river picks.** The change is at least −0.02, and the interval's upper end
   is above zero.
4. **Face check.** The reference column equals `validate_ecoli.py`'s `risk_model`, run in the same root, to within
   1e-9 on every row, and is missing on the same rows. The harness's survival at s = 0, θ = 1 equals
   `10^(−travel_h / 72)` to within 1e-12. 0 network attempts during the scoring. If any of these fails, I stop and
   report it before scoring.

## Question 2: the E. coli model at the spot

### What changes

Two inputs are added to the E. coli model's seven:
- `sun24`: mean `shortwave_radiation` over the 24 hours to the sample hour;
- `temp48`: mean `temperature_2m` over the 48 hours to the sample hour.

Both use the same hours and the same coverage rule as `ecoli.rain_windows`: missing unless at least `MIN_COVERAGE` of
the hours carry a value. Both are standardised like the other inputs. Nothing else in the model changes. Question 2
uses today's exposures, not Question 1's.

### The evaluation

`scripts/train_ecoli.py`'s own evaluations, run twice on the same rows: today's features, and today's features plus
the two. The rows are the samples it uses today (1,502) less any without weather, which are counted.
- **Leave one year out** (LOYO): the Brier score, all, rivers and lakes.
- **Leave one site out** (LOSO): the Brier score.
- **Forward:** fitted on 2024, scored on 2025–26.
- **Interval:** its cluster bootstrap over (site, ISO week) blocks on the LOYO predictions, for the Brier difference,
  with its seed.

### Question 2 passes if all five hold

1. **LOYO Brier, all.** It improves by at least 0.0005, and the 95% interval of the improvement is above zero.
2. **LOSO Brier, all.** No worse than today's by more than 0.0005.
3. **Forward Brier.** No worse than today's by more than 0.0005.
4. **Rivers and lakes apart (LOYO).** Neither is worse by more than 0.0005.
5. **The sign of sunlight.** In the model fitted on all rows, `sun24`'s coefficient is below zero: more sun, fewer
   exceedances. A positive sign would mean it stands in for something else, such as dry weather or crowds on sunny
   days, and not for die-off. `temp48` has no sign condition. Warm weather speeds die-off but also brings bathers,
   dogs and birds, so either sign can be read.

## What is expected, stated now

- **Question 1 will most likely fail condition 1.** Three reasons. First, the samples run from May to September only,
  so sunlight and temperature vary much less than across a year. Second, the longer journeys (up to about four days) span
  several days and nights, which smooths the weather out. Third, the fitted T90 of 72 hours is long for sunlit water,
  which hints that muddy water, depth or bacteria held in sediment matter more than sunlight here.
- **Question 2 may show a small sunlight effect.** But sunny days are dry days, and the model already has rain. I expect
  condition 1 to fail: the interval will most likely include zero.
- If either passes, it is most likely on rivers. Lakes have 16 samples over 900 in four years.

## Running

- The harness is `scripts/dieoff_weather_eval/`. It is committed after this file and before the run. The statement
  above the line does not change when it is added.
- The fetch first. Then everything else from a `git archive` of the harness commit, in a scratch folder, offline
  (every outgoing connection refused and counted, `scripts/lake_distance_eval/run_offline.py`), on a frozen copy of
  the data folder whose hashes go in the results.
- One run, alone. It starts when `memory_pressure` reads 35% free or more and no other evaluation, training, build or
  test runs on this machine. That is the gate the transport tests used.

## What follows

**Question 1 passes.** The picked s and θ become defaults in a separate final commit. Then, as after the transport fit:
- the live forecast asks Open-Meteo for the two variables in the spots' existing forecast request. By
  `rainfall.call_weight`, three variables over 37 days (31 past, 6 ahead counting today) still weigh 1 per location, so this adds no calls. The
  click-anywhere files follow, or the switch waits until they do, because a map click must not disagree with the spot
  page;
- outside May to September the weather fed to the rate is held inside the range seen in the samples' travel windows.
  The fit has no winter samples to test it against. This follows `ecoli.season_day`'s rule;
- the E. coli chain is rerun (`validate_ecoli`, `replay_ecoli_leads`, `validate_ecoli_combined`, `train_ecoli`). If
  the LOYO Brier is worse than today's 0.0919 by more than 0.0005, nothing is adopted and the switch is reverted.

**Question 2 passes.** The two inputs are added. Before they ship:
- lead 1 to 4 weather is fetched (archived from 2024 only; about 2,000 calls) and `train_ecoli`'s by-lead table is
  rerun. If any lead's Brier is worse than today's at that lead by more than 0.0005, nothing is adopted;
- the live request adds the variables as above, and outside May to September the inputs are held inside their sample
  range.

**Both pass.** Question 1 is adopted first. Question 2's inputs are then added to the refitted model and must still
meet its conditions 1 to 4 against that refit.

**Either fails.** That part changes nothing. This PR stays a record: this file, the results, the harness, the weather
cache script, and the transport argument at its default.

Changing a model constant is allowed until the 2027 freeze tag (`docs/PREREGISTRATION-2027.md`). The PR is left for
Ethan to merge.

## What will be reported

Whatever the verdict:
- each condition with its figure and interval;
- Question 1: each year's pick, its score on the other years, and pick and reference on the held-out year; the
  in-sample table of all 12 settings on rivers and lakes;
- Question 2: every evaluation's table with and without the two inputs, and the coefficients per SD;
- calls spent on the fetch, rows dropped for missing weather, run time, peak memory and network attempts.

## Seen before writing

- The published figures today: LOYO Brier 0.0919 (rivers 0.1350, lakes 0.0262), LOSO 0.0909, forward 0.0823, from
  `data/processed/ecoli_model_eval.json` at main `bfe47f2`. Within-site Spearman of `risk_model` on rivers 0.4706 (947
  samples) from `ecoli_validation.json`.
- In that file, "rain + spill exposure" without the season terms scores LOYO Brier 0.0913, better than the full model's
  0.0919. Season already does little. This is stated because sunlight and temperature follow the season.
- The cached lead rain (`leads_<cell>_<year>.parquet`): lead 0 has values in every year 2023 to 2026; leads 1 to 4 have
  none in 2023. Open-Meteo's page says most models are archived from January 2024.
- One request to the Previous Runs API: one cell (54.4, −2.9), 1 June 2023, `shortwave_radiation` and `temperature_2m`
  at lead 0 came back with values, and `shortwave_radiation_previous_day1` came back empty. No sample, spill or E. coli
  figure was looked at with it.
- No score of any kind has been computed for this test.

---

## Results

Not yet run.
