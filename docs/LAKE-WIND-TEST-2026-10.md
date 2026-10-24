# Wind on lakes: the test, stated before any run

Written 24 October 2026. No wind data for this test has been fetched, beyond the one-day check under "Seen before
writing". Nothing has been run. No score of any kind has been computed for this test. Results go below the line at
the end. Nothing above it changes after a result is seen.

## Why

In a lake, river water does not flow straight to the outlet. The wind pushes the surface water, and with it a plume
from an inflow. The site says so on every lake spot: "In a lake, the wind decides where river water goes. The
forecast does not use wind." (`docs/DESIGN.md`, around line 589.)

Three things point here.
- **A data review, 24 October 2026.** No provider, the Met Office included, publishes lake currents. Wind is the
  nearest stand-in for surface drift, and it is already free from Open-Meteo, which serves the Met Office's UKV model
  among others.
- **The UKCEH Love Windermere review, 23 October 2026.** A lake wind test was one of its open picks.
- **The lake direction test** (`docs/LAKE-DIRECTION-TEST-2026-10.md`). Leaving out overflows that enter down the lake
  lowered the within-site rho at every lake water whose exposure changed. At Monk Coniston the overflow it dropped,
  Coniston WwTW 1.1 km down the lake, gave the best within-site match of any lake site. That is what a pathway against
  the through-flow would look like. Wind is the obvious carrier.

Tim Boden (Ambleside Action for a Future) says Waterhead is a self-contained bay that the Brathay and Rothay plume
misses. That is a case where geometry and wind decide. Waterhead is not a designated bathing water and is not in
these samples.

**The question.** At lake bathing waters, does wind that pushes surface water from where overflow water enters the
lake towards the bathing water go with higher E. coli, once rain, overflow exposure and season are allowed for? And
does adding it to the E. coli model help?

## The wind

**Source:** Open-Meteo's Previous Runs API, lead 0 (`https://previous-runs-api.open-meteo.com/v1/forecast`), hourly,
`wind_speed_10m` (asked for in m/s, `wind_speed_unit=ms`) and `wind_direction_10m` (degrees, the direction the wind
blows from, clockwise from true north). Both are the instant at the hour stamp. This is the API and lead the E. coli
model's rain comes from (`ingest/rainfall_leads.py`). So the live forecast would use the same kind of figure.

**Where:** the weather cell (`rainfall.grid_cell`, 0.1°) of each lake bathing water, as the model places a sample's
rain. The 11 lake bathing waters with overflows upstream sit in 7 cells. A 0.1° cell of a 2 km model smooths the wind
that valley sides funnel along a lake. That is a limit, stated now.

**When:** calendar years 2023 to 2026, to two days before the fetch.

**The fetch:** by quarter, 4 cells to a request, as `scripts/dieoff_weather_eval/weather.py` does, because a year in
one request timed out there. That script gains options for the variables, cells, file prefix and extra request
parameters. Its defaults, and so the die-off test's fetch, do not change. 2 variables over a quarter weigh about 1.3
a cell by Open-Meteo's rule (`rainfall.call_weight`): 7 cells × 16 quarters is about 150 calls. It runs once, strict
(stop at the first refusal), paced at one request a second. It is cached as `wind_leads_<cell>_<year>.parquet`
outside the repo. A cell-year that fails stays missing; the rows it touches leave every arm and are counted.

## The feature

**The entry point.** For each lake bathing water, every overflow upstream is walked to where its water enters the
spot's lake (`transport._walk_to_lake`, at main's defaults). Overflows whose entries lie within 50 m of each other are
one inflow, and the inflow's weight is the sum of their transport weights (`transport.upstream_overflows`, `weight`).
**The inflow with the largest weight is used.** The weight is the model's own estimate of how much of each inflow's
spill reaches the spot. So the heaviest inflow is the plume the model already relies on most there. The nearest
inflow was the other option. It was not chosen because near inflows can carry little weight: at Lakeside YMCA the
nearest (Hawkshead and Near Sawrey, 3.9 km) carries a third of the weight, Glebe Road (6.7 km) two thirds.

**The bearing.** The initial geodesic bearing from the entry point to the bathing water's pin, clockwise from true
north (`scripts/lake_wind_eval/geometry.py`). It is a straight line. Along these routes the line and the path through
the water differ by at most 12% (Rutland), and by 2% or less on Windermere, Coniston and Derwent Water.

**The near field.** Where the heaviest inflow enters within 1,000 m of the pin, the site has no bearing. Near an
entry a spill spreads every way by wind and mixing, and a bearing over 84 m means nothing. 1,000 m is the margin the
lake direction test set for the same reason (`transport.LAKE_DOWN_MARGIN_M`). Two sites fall inside it: Coniston
Boating Centre (84 m) and Frensham Great Pond (495 m). They keep 0 for the wind input in the model and are left out of
conditions 1 and 2. The other 9 have a bearing.

**The input.** For a sample at time t (`sample_time`, floored to the hour, as `ecoli.rain_windows` does):

`wind24_to` = mean over the 24 hour stamps (t − 23 h … t] of speed × cos(direction + 180° − bearing), in m/s.

Positive means wind blowing from the entry towards the bathing water. It is missing unless at least `MIN_COVERAGE`
(0.9) of the 24 stamps carry both variables. In the model it enters as `lake_x_wind24` = `wind24_to` at the 9 sites
with a bearing and 0 elsewhere (rivers and the two near-field lakes), standardised like the other inputs.

**Expected sign: positive.** Wind towards the bathing water carries the plume towards it.

**No speed floor.** The projection scales with speed, so calm hours add almost nothing on their own. A floor would add
a threshold with nothing to set it from. It is linear in speed because surface drift is roughly 1 to 3% of the wind
speed (`config.LAKE_VELOCITY_MS` assumes 1% of a 5 m/s wind).

**Why 24 hours.** At 1 to 3% of a 5 m/s wind, surface water moves 4 to 13 km in 24 hours. The 9 entries lie 1.1 to
9.4 km from their pins. 24 hours is also the model's shorter rain window. The 6- and 48-hour means are reported, but
decide nothing.

## The evaluation

The chain is the one the dry-spell and die-off tests ran: `validate_ecoli.py`, `replay_ecoli_leads.py`,
`train_ecoli.py`, then `scripts/lake_wind_eval/score.py`. Rows are `train_ecoli.py`'s (1,502 in the die-off test's
reference run, 595 of them at lakes), less any lake row at a site with a bearing that has no wind. Those are counted;
they leave every arm.

**The power, faced now.** The lakes have 16 samples over 900 in these rows, 12 of them at Derwent Water (from the
published table in `docs/LAKE-DISTANCE-2026-10.md`). The 4 Windermere and 2 Rutland sites have none. So a Brier score
on lakes is mostly Derwent Water, and at a site with no exceedance a lower prediction always scores better. The main
score is therefore a rank measure on log E. coli, which uses every sample. With about 500 samples at the 9 sites, the
standard error of a correlation is about 0.045, more once samples in the same week are allowed to share weather. An
interval wholly above zero needs a partial rho of roughly 0.10 to 0.12 or more. A smaller real effect would not be
seen. A fail here would not show that wind does not matter, only that these samples cannot see it.

### Condition 1, the main score: the within-site partial rank correlation

On lake rows at the 9 sites with a bearing. Within each site, log10 E. coli, `wind24_to` and each control are ranked
(ties averaged), divided by the site's sample count and centred on the site's mean. The ranks of log10 E. coli and of
`wind24_to` are each regressed on the controls' ranks (pooled least squares), and the score is the Pearson correlation
of the two residuals. The controls are the model's inputs that move within a lake site: `lrain48`, `lrain24`,
`logit_risk`, `doy_sin` and `doy_cos`, with `logit_risk` from the production lead-0 exposure the model is fitted on.

**Interval:** a cluster bootstrap by calendar week (ISO year and week), since the lakes share weather in a week. 2,000
resamples, numpy `default_rng(20261024)`, everything above recomputed in each. The 95% interval runs from the 2.5th to
the 97.5th percentile.

**Holds if** the partial rho is above zero and the interval's lower end is above zero.

### Condition 2: placebo bearings

Wind direction goes with the weather: a south-westerly brings rain and mild air. If any bearing did as well as the
real one, the score would be about weather type, not about where the plume goes. 1,000 placebos, numpy
`default_rng(1024)`: each gives each of the 9 sites its own bearing drawn uniformly from 0 to 360°. Condition 1's score
is recomputed with each.

**Holds if** the real score is above at least 95% of the placebo scores (the share at least as high is at most 0.05).

### Condition 3: the model's ranking at lakes

`train_ecoli.py`'s leave-one-year-out (LOYO) predictions, run on the same rows with today's seven inputs and with
`lake_x_wind24` added. The within-site Spearman rho of the prediction against log10 E. coli on all lake rows (value
less its site mean, as `validate_ecoli.py` and the transport tests compute it).

**Holds if** the change, with minus without, is above zero. Its week-cluster interval is reported.

### Condition 4: no harm

The Brier score of each, with the margin of the earlier tests, 0.0005:
- LOYO, all rows, rivers and lakes;
- leave one site out (LOSO), all rows;
- forward, fitted to 2024 and scored on 2025–26, all rows.

**Holds if** none is worse with `lake_x_wind24` by more than 0.0005.

### Condition 5: the sign

**Holds if** `lake_x_wind24`'s coefficient, in the model fitted on all rows, is above zero.

### Condition 6: face checks

- The reference arm's LOYO, LOSO and forward Brier scores and row count equal those `train_ecoli.py` wrote in the same
  root (to the 4 decimals it writes).
- The projection: a wind of 5 m/s blowing along the bearing gives +5, against it −5, across it 0, to within 1e-9
  (checked in `score.py` before scoring).
- 0 network attempts in every step of the run.

If any face check fails, I stop and report it before scoring.

### The verdict

The test passes only if all six hold.

## Reported, deciding nothing

- **Per-lake description table**, marked as description only: samples, samples over 900, the inflow used, its
  distance and bearing, mean `wind24_to`, the share of samples with it above zero, the raw within-site Spearman rho of
  `wind24_to` against log10 E. coli, and the geometric mean E. coli with the wind towards and away.
- Condition 1's score and interval for the 6- and 48-hour means.
- Condition 1's score for wind speed alone, with no direction: is it windiness or direction?
- Condition 1's score on lake rows above and below the median `logit_risk`: does wind matter more when a spill is
  likely?
- The lake LOYO AUC over 900, with and without. With 16 exceedances it is too noisy to decide anything.
- The coefficients per standard deviation, and the correlation of `wind24_to` with `lrain48`.

## What is expected, stated now

- **Condition 1 will most likely fail.** The reasons: about 500 samples, so only an effect of 0.10 or more is visible;
  a 0.1° cell's wind, not the wind on the water; samples taken at 10:00 to 14:00, whatever the plume did overnight; a
  straight-line bearing from one inflow; and E. coli at most lake sites sits near the bottom of its range most days,
  with many ties.
- **If there is a signal, it is most likely at the Windermere and Coniston sites near the heads and feet of the lakes.**
  The 9 bearings point both ways along the lakes (north at Millerground, Rayrigg, Monk Coniston and Crow Park; south at
  Lakeside YMCA, Fellfoot and Brown Howe; east at both Rutland sites). That mix is what lets condition 2 separate
  geometry from weather type.
- **Conditions 4 and 5 hang on Derwent Water**, which holds 12 of the 16 lake exceedances. Its inflow enters from the
  south (bearing 359°), so a southerly is "towards".

## What follows

Nothing is adopted in this PR, whatever the verdict.

**All six hold.** A separate PR, stated before it is run, adds `lake_x_wind24` to the model. Before it ships:
- lead 1 to 4 wind is fetched (archived from 2024 only) and `train_ecoli`'s by-lead table is rerun. If any lead's
  Brier is worse than today's at that lead by more than 0.0005, nothing is adopted;
- the live request adds the two wind variables. Three variables over 37 days still weigh 1 a location by
  `rainfall.call_weight`, so this adds no calls;
- the site's lake spots get bearings from `geometry.py`, and click-anywhere follows or the switch waits;
- the line on the lake spots changes only then.

**Any fails.** Nothing changes. This PR stays a record: this file, the results, the harness, the geometry script and
the fetch options.

Changing a model input is allowed until the 2027 freeze tag (`docs/PREREGISTRATION-2027.md`). The PR is left for
Ethan to merge.

## Running

- The harness is `scripts/lake_wind_eval/`. `geometry.py` comes in this commit, because its table is quoted below.
  `score.py`, `run.sh` and the fetch options come in the next commit, before the fetch. The statement above the line
  does not change when they are added.
- The fetch next. Then everything else from a `git archive` of the harness commit, in a scratch folder, offline (every
  outgoing connection refused and counted, `scripts/lake_distance_eval/run_offline.py`).
- **The data folder:** a copy, made 24 October 2026, of the frozen folder the die-off and dry-spell tests ran on
  (overflow key b5724303). The original is never written to. The copy's hashes go in the results.
- One run, alone. It starts when `memory_pressure` reads 35% free or more and no other evaluation, training, build or
  test runs on this machine.

## What will be reported

Whatever the verdict: each condition with its figure and interval; the placebo distribution (lowest, median, 95th
percentile, highest) and the share at least as high as the real score; every model evaluation's table for both arms;
the description table; rows dropped for missing wind; calls spent; run time, peak memory and network attempts.

## Seen before writing

- **The geometry**, transport only, from `geometry.py` on the frozen data copy. No rain, spill model, wind or E. coli
  figure was computed or looked at. 11 lake bathing waters have overflows upstream, with 24 inflows. The inflow used:

| bathing water | inflow used (overflows) | share of weight | straight line, m | through water, m | bearing to pin |
|---|---|---|---|---|---|
| Rutland Water Whitwell Creek | Oakham STW | 0.50 | 4,387 | 4,912 | 98° |
| Rutland Water Sykes Lane | Oakham STW | 0.48 | 5,646 | 5,739 | 97° |
| Windermere, Lakeside YMCA | Glebe Road PS | 0.66 | 6,719 | 6,786 | 195° |
| Windermere, Fellfoot | Glebe Road PS | 0.67 | 9,445 | 9,508 | 188° |
| Windermere, Millerground Landing | Glebe Road PS | 0.66 | 2,570 | 2,576 | 17° |
| Windermere, Rayrigg Meadow | Glebe Road PS | 0.68 | 2,301 | 2,303 | 19° |
| Coniston Water, Brown Howe | Torver WwTW | 0.58 | 1,114 | 1,114 | 187° |
| Coniston Water, Monk Coniston | Coniston WwTW | 0.80 | 1,234 | 1,254 | 39° |
| Derwent Water at Crow Park | Rosthwaite WwTW, Stonethwaite WwTW, Grange Bridge (one inflow) | 1.00 | 3,470 | 3,470 | 359° |
| Coniston Water, Boating Centre | Coniston WwTW | 0.81 | 84 | 84 | near field |
| Frensham Great Pond | Churt SPS | 1.00 | 495 | 495 | near field |

- **The sample counts** at lake waters in the frozen `ecoli_validation_rows.parquet` (names, kinds and counts only):
  803 rows with an overflow upstream at 12 lakes. Colwick's 65 come from the pins before eval pins followed the site's
  (#199); under today's pins Colwick has no overflow upstream, as in the die-off test's run (738 lake rows at 11
  sites).
- **Published figures:** the die-off test's reference run on the same folder, LOYO Brier 0.0921 (lakes 0.0262), 1,502
  rows, 212 over 900, 16 of them at lakes; the per-site samples and exceedances in `docs/LAKE-DISTANCE-2026-10.md`;
  the lake direction test's record table.
- **One request** to the Previous Runs API: one cell (54.4, −2.9), 1 June 2023, `wind_speed_10m` and
  `wind_direction_10m` at lead 0 with `wind_speed_unit=ms`. All 24 hours of both came back, with units m/s and °. Only
  the counts and units were read, not the values.
- No score of any kind has been computed for this test.

---

## Results
