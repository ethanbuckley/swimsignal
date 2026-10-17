# Fitting the transport settings to the E. coli samples: the test, stated before any run

Written 16 October 2026. Nothing in this test has been run through the E. coli evaluation. Results go below the
line at the end. Nothing above it changes after a result is seen.

## Why

The transport step turns "this overflow spilled" into "it reaches this swim spot". Its three main settings are set
by hand (`src/dipcast/config.py` and `src/dipcast/model/transport.py`):
- **River speed:** 0.5 m/s on every reach when no gauge gives one (`RIVER_VELOCITY_MS`).
- **Die-off:** T90 = 30 hours, the time for 90% of the bacteria to die (`T90_HOURS`).
- **Dilution:** the ratio of upstream network length at the overflow to that at the spot, capped at 1
  (`(L_up(overflow) + L0) / (L_up(spot) + L0)`).

The README's Method section says these are not calibrated against samples. Of the model's three steps (rain to
spill, spill to spot, spot to E. coli), this one has had the least testing. On 16 October Ethan asked how to make the
forecasts more accurate. This is the third item of the order agreed then.

## What is fitted

A grid of 75 settings, all run:
- **River speed:** 0.2, 0.35, 0.5, 0.75, 1.0 m/s.
- **T90:** 12, 20, 30, 48, 72 hours.
- **Dilution exponent:** 0.5, 1, 1.5. The length ratio, after its cap at 1, is raised to this power. A power above 1
  makes a small side stream count for less against the main river; below 1, for more.

The current settings (0.5 m/s, 30 h, 1) are one point on the grid.

**Not fitted:**
- **Lake speed** (0.05 m/s). Lake samples have shown no within-site signal in earlier tests, so a lake setting fitted
  to them would be fitted to noise. It stays as it is.
- **The gauge rule.** Where a spot has an EA level gauge, the live forecast sets the river speed from the gauge's
  level (`transport.river_velocity`: 0.3 + 0.7 × the level index). The hindcast has no gauge readings, so it uses
  the fixed speed everywhere. A fitted speed would change only the no-gauge default. Whether the gauge rule should
  follow is a separate question.
- **The rest of the step:** L0 (5 km), the 60 km cap, the lake rules (`residence_spill`, lake distance `water`), the
  lake area factor. They stay at main's defaults.

**Code change made for the test.** `transport.upstream_overflows` gains `dilution_power`, default
`transport.DILUTION_POWER = 1.0`. At 1 it gives exactly today's weights (`tests/test_transport_options.py`). Speed and
T90 were already arguments (`velocity_ms`, `t90_h`). Nothing in production changes.

## Seen before writing

- The sample counts by year and kind, from the frozen `bwq_samples.parquet`, all 2,165 samples with an E. coli figure:

  | year | lakes | rivers |
  |---|---|---|
  | 2023 | 282 | 40 |
  | 2024 | 336 | 290 |
  | 2025 | 329 | 281 |
  | 2026 | 271 | 336 |

  18 lake and 20 river bathing waters. The reanalysis rain ends on 6 September 2026, so later samples have no figure.
- The published `data/processed/ecoli_validation.json` (current settings): within-site Spearman of `risk_model`
  0.314 (all, n 1,684), 0.399 (rivers, 947), 0.264 (lakes, 737). AUC over 900: 0.810, 0.744, 0.657. On rivers, rain in
  the 48 hours before sampling does better within site than the model (0.475).
- How long `upstream_overflows` takes per bathing water (about 3 seconds for all 38, per setting). No weight,
  risk or E. coli figure was looked at.
- `fit.py score` run on synthetic rows (random numbers with a signal planted in one setting), to test the code. It
  found the planted setting. The numpy rewrite was checked against `transport.combine_daily` and `missing_share` on
  random arrays: equal.
- The results of the lake tests (`docs/LAKE-RESIDENCE-*.md`, `docs/LAKE-DISTANCE-2026-10.md`).

## The evaluation

**The hindcast** is `scripts/validate_ecoli.py`'s, on the site's placement of each bathing water
(`eval_pins.bathing_water_pin`, `docs/ECOLI-REFIT-SITE-PINS-2026-10.md`):
- spill chances at every upstream overflow on every day, from reanalysis rain and the spill model, calibrated as lead 0;
- through the transport step with the setting under test;
- risk = 1 − ∏(1 − p·w), each overflow's chance shifted by its travel time;
- a sample day where over `MAX_MISSING_SHARE` of the weight has no rain data gets no figure.

The spill chances do not depend on the transport settings. So the harness makes them once per bathing water and runs
only the transport step 75 times. It rewrites `combine_daily` and `missing_share` with numpy, since theirs loop in
Python.

**Harness:** `scripts/transport_fit_eval/`, in the commit that adds this file.
- `fit.py prep`: the risk on every sample day under every setting.
- `fit.py check`: the current setting's column against `validate_ecoli.py`'s `risk_model`, row by row.
- `fit.py score`: the selection, held-out scores and bootstrap below.
- `run.sh`: one run, offline (every outgoing connection refused and counted, `scripts/lake_distance_eval/run_offline.py`).

**Inputs:** the frozen data folder the lake-distance test used, copied with every link followed on 16 October.
- Overflow table SHA-256 begins `e6ef0459`, river network `fc66101d`, `bwq_samples.parquet` `26f5f646`,
  `network_fixes.csv` `7ff7af1a`, `spill_model.pkl` `faa7917e`, `lead_calibration.json` `734202bc`.
- 3,658 cached rain files.
- Every file of `data/raw` and `data/processed` that main tracks is byte-identical to main `6edde6e`'s.
- Spots and pins from the archived commit's `spots.csv`.

**Running:** from a `git archive` of the commit that adds this file, in a scratch folder, so later edits cannot reach
the run. One run, alone, after waiting for 5 GB of free plus inactive memory, and not while the nine-company spill
model trains or any other evaluation or build runs. No Open-Meteo or other network call.

**Rows scored:** samples at bathing waters with overflows upstream that have a figure under all 75 settings. A
setting can leave a day without a figure (a longer reach, more missing rain), so the rows are the same for every
setting. Rivers and lakes apart.

## The score

As `validate_ecoli.py` computes them:
- **Within-site Spearman:** the risk and log10 E. coli, each less its site's mean, pooled, ranked. A site that is
  always dirty cannot inflate it.
- **Pooled AUC over 900:** the risk against a sample over 900 cfu/100 ml.

Within-site Spearman is the main score. It asks the question the transport step is for: on which days is a spot
worse than usual.

## Selection: leave one year out

For each year Y of 2023 to 2026, on rivers:
1. Score all 75 settings on the river samples of the other three years (within-site Spearman, site means over those
   years).
2. Take the best. A tie goes to the current settings, then to grid order.
3. Score that setting on year Y's river samples.

So no setting is picked with the year it is scored on. The four held-out years are pooled. The current settings are
scored on the same rows. Within-site means are taken per site and year, since each year was predicted by its own
pick.

2023 has only 40 river samples, from the few river sites designated then. It is still a fold.

**The interval:** a cluster bootstrap by calendar week (ISO year and week of the sample), 2,000 resamples, numpy
`default_rng(20261016)`. Each resample recomputes both scores and their difference. The 95% interval is the 2.5th
to 97.5th percentile. It covers which weeks were sampled. It does not redo the selection; leaving a year out is what
guards against that.

**What would be deployed:** the setting that scores best on all four years of river samples together.

**Lakes:** the settings are shared, so lakes are scored with the settings picked on rivers, year by year, against
the current settings on the same lake rows. For the record only, the same selection is also run on lakes alone.

## What counts as passing

All four must hold.
1. **Rivers, within-site Spearman.** The held-out score of the picked settings is above the current settings', and the
   lower end of the 95% interval of the difference is above zero.
2. **Rivers, AUC over 900.** The held-out change is at least −0.005, and the upper end of its interval is above zero.
   So it is not clearly worse.
3. **Lakes, within-site Spearman, with the river picks.** The change is at least −0.02, and the upper end of its
   interval is above zero.
4. **Face check.**
   - The current settings' column equals `validate_ecoli.py`'s `risk_model`, run in the same root, on every row to
     within 1e-9. The figure is missing on the same rows.
   - The numpy rewrite equals `transport.combine_daily` and `transport.missing_share` to within 1e-12 at every site.
   - 0 network attempts.
   - If any of these fails, I stop and report it before scoring anything.

**What is expected, stated now.**
- Speed and T90 partly stand in for each other. Die-off depends on distance ÷ (speed × T90), so several settings give
  nearly the same weights. Speed alone sets the day the water arrives. The years may pick different settings that
  score almost the same.
- The dilution exponent matters only where a spot has overflows at quite different ratios, such as a side stream and
  the main river.
- On rivers, rain in the last 48 hours beats the model within site. That hints the timing may be off: water that
  arrives faster, or nearby overflows counting for more. So if the fit moves anything, I expect a higher speed, a
  shorter T90 or a higher exponent.
- About 950 river samples at 20 sites, and the scores move by small amounts across the grid. **I expect condition 1 to
  fail**: the interval will most likely include zero.

## What follows

**All four hold.** The fitted settings become the defaults, in this PR, in a separate final commit:
- `config.RIVER_VELOCITY_MS` and `config.T90_HOURS`, and `transport.DILUTION_POWER` if it is not 1.
- If the exponent changes, click-anywhere follows it (`scripts/build_any_point.py`, `anypoint.js` and their parity
  test), or the switch waits until it does. A map click must not disagree with the spot page.
- The E. coli chain is rerun on the new settings (`validate_ecoli`, `replay_ecoli_leads`, `validate_ecoli_combined`,
  `train_ecoli`). The E. coli model the site serves is fitted on the exposures, so it must be refitted with them. If
  `train_ecoli`'s LOYO Brier score is worse than now (0.0938) by more than 0.0005, nothing is adopted and the PR says so.
- The Accuracy files, the methods page and the README's Method section are updated to match.
- Changing a model constant is allowed until the 2027 freeze tag (`docs/PREREGISTRATION-2027.md`). The PR is left for
  Ethan to merge.

**Any fails.** The settings stay as they are. The PR is a record: this document, the results, the harness and the
`dilution_power` argument at its default of 1.

If the harness changes after a result is seen, both results are kept and the change is stated.

## What will be reported

Whatever the verdict:
- the four conditions with their figures and intervals;
- each year's pick, its score on the other years, and its and the current settings' score on the held-out year;
- the full-data pick, and the in-sample scores of every setting on rivers and on lakes, as a table;
- the lake-only selection, for the record;
- the number of rows scored and dropped, run time, peak memory and network attempts.

---

## Results

Added 17 October 2026, after the run. Everything above the line is as committed in b5e0af1 (16 October 2026,
23:59 BST), pushed before the run started (17 October, 01:06 BST). The harness was not changed after any result was
seen.

**Verdict: all four conditions hold.** Every year picked the same setting: river speed 0.2 m/s, T90 72 hours,
dilution exponent 0.5. By the rule above, it becomes the default in a separate final commit, if the refitted E. coli
model's LOYO Brier score is no worse than now by more than 0.0005. Two things the rule does not decide are reported
below: the pick is a corner of the grid, and lake AUC over 900 falls.

### How it was run

- From an archive of b5e0af1 in a scratch folder, offline. 0 network attempts in all four steps.
- **One deviation from the stated procedure.** The statement said the run would wait for 5 GB of free plus inactive
  memory. In 70 minutes that figure stayed between 2 and 4 GB, because macOS keeps most memory compressed and the
  measure does not count it. I switched the gate to macOS's own measure, `memory_pressure`'s free percentage, at 35%
  or more, and kept the condition that no other evaluation, training, build or test run was going. It read 49% and the
  run started at 01:06:56. This changes when the run started, not what it computed.
- The machine was short of memory throughout (swap 4.3 of 5 GB). Wall time: `validate_ecoli.py` 79 minutes, `prep`
  58 minutes, `check` 4 minutes, `score` 43 seconds. CPU time was about 4 minutes each for the first two. Peak memory
  3.3 GB.

### Condition 4: face check. Holds.

- The current settings' column equals `validate_ecoli.py`'s `risk_model`, run in the same root, on all 2,165 rows:
  largest difference 4.4e-16. The figure is missing on the same rows (0 mismatches). No row unmatched; `upstream`
  equal on every row.
- The numpy rewrite equals `transport.combine_daily` and `transport.missing_share` at all 31 bathing waters with
  overflows upstream: largest difference 0.0.

**Rows scored:** 1,685 samples at bathing waters with overflows upstream; 1,684 have a figure under all 75 settings.
The one dropped is Derwent Water at Crow Park on 7 September 2026, after the rain archive ends. That matches the
published n of 1,684. Rivers 947 samples at 20 waters; lakes 737 at 11.

### Leave one year out, rivers

| held-out year | samples | pick (from the other three years) | its score on them | held-out rho, pick | held-out rho, current |
|---|---|---|---|---|---|
| 2023 | 40 | 0.2 m/s, 72 h, 0.5 | 0.464 | 0.616 | 0.642 |
| 2024 | 290 | 0.2 m/s, 72 h, 0.5 | 0.469 | 0.441 | 0.360 |
| 2025 | 281 | 0.2 m/s, 72 h, 0.5 | 0.447 | 0.543 | 0.429 |
| 2026 | 336 | 0.2 m/s, 72 h, 0.5 | 0.499 | 0.376 | 0.340 |

The full-data pick is the same setting (in-sample within-site rho 0.471, against 0.400 for the current settings).

### Conditions 1 to 3

Pooled held-out rows; change is pick minus current, with its 95% calendar-week cluster bootstrap interval.

| measure | n | weeks | pick | current | change [95% CI] |
|---|---|---|---|---|---|
| Rivers, within-site rho | 947 | 83 | 0.4727 | 0.3965 | +0.0762 [+0.0305, +0.1161] |
| Rivers, AUC over 900 (202 over) | 947 | 83 | 0.7685 | 0.7442 | +0.0243 [+0.0070, +0.0398] |
| Lakes, within-site rho, river picks | 737 | 78 | 0.3049 | 0.2862 | +0.0187 [−0.0072, +0.0466] |
| Lakes, AUC over 900 (16 over), river picks; reported only | 737 | 78 | 0.6132 | 0.6611 | −0.0479 [−0.0791, −0.0159] |
| All, within-site rho; reported only | 1,684 | 84 | 0.3817 | 0.3179 | +0.0639 [+0.0292, +0.0893] |
| All, AUC over 900 (218 over); reported only | 1,684 | 84 | 0.8055 | 0.8108 | −0.0053 [−0.0200, +0.0073] |

1. Rivers, rho: +0.076, lower end +0.031, above zero. **Holds.**
2. Rivers, AUC: +0.024, at least −0.005; upper end +0.040, above zero. **Holds.** (Its interval is wholly above zero.)
3. Lakes, rho: +0.019, at least −0.02; upper end +0.047, above zero. **Holds.**

**Lake AUC over 900 is worse,** by 0.048, and its interval excludes zero. The rule only reports it. It rests on 16
lake samples over 900, and pooled AUC depends on how the lakes rank against each other, which the exponent moves: a
lower exponent raises the weight of overflows on small inflows against the lake's main inflow. The E. coli model the
site serves has its own lake term, so the confirmation step below is where this would show.

### The in-sample table

Within-site rho on all four years. Rows river speed (m/s), columns T90 (hours). The current settings are 0.5 m/s,
30 h, exponent 1 (0.400 on rivers).

Rivers:

| exponent 0.5 | 12 | 20 | 30 | 48 | 72 |
|---|---|---|---|---|---|
| 0.2 | 0.333 | 0.377 | 0.419 | 0.453 | **0.471** |
| 0.35 | 0.354 | 0.400 | 0.427 | 0.447 | 0.456 |
| 0.5 | 0.368 | 0.409 | 0.425 | 0.432 | 0.437 |
| 0.75 | 0.385 | 0.411 | 0.417 | 0.421 | 0.423 |
| 1.0 | 0.391 | 0.407 | 0.411 | 0.416 | 0.420 |

| exponent 1 | 12 | 20 | 30 | 48 | 72 |
|---|---|---|---|---|---|
| 0.2 | 0.304 | 0.341 | 0.379 | 0.414 | 0.435 |
| 0.35 | 0.324 | 0.370 | 0.397 | 0.418 | 0.428 |
| 0.5 | 0.338 | 0.378 | *0.400* | 0.411 | 0.416 |
| 0.75 | 0.355 | 0.382 | 0.395 | 0.402 | 0.406 |
| 1.0 | 0.358 | 0.379 | 0.389 | 0.394 | 0.397 |

| exponent 1.5 | 12 | 20 | 30 | 48 | 72 |
|---|---|---|---|---|---|
| 0.2 | 0.292 | 0.321 | 0.354 | 0.389 | 0.402 |
| 0.35 | 0.308 | 0.346 | 0.374 | 0.398 | 0.408 |
| 0.5 | 0.319 | 0.357 | 0.379 | 0.393 | 0.399 |
| 0.75 | 0.332 | 0.357 | 0.375 | 0.384 | 0.386 |
| 1.0 | 0.340 | 0.356 | 0.367 | 0.372 | 0.377 |

Lakes vary far less: within-site rho 0.236 to 0.292 across all 75 settings (current 0.265). Exponent 0.5 is best on
lake rho at every speed and T90 too. Lake AUC over 900 runs the other way: 0.594 to 0.679, best at exponent 1.5 and
1 m/s, worst at the river pick's corner (0.613).

**Lake-only selection, for the record:** 1 m/s, 72 h, 0.5 in three years, 0.2 m/s, 48 h, 0.5 in 2025. Held-out lake
rho 0.3025 against 0.2862, change +0.016 [−0.004, +0.040]; lake AUC 0.592 against 0.661. Not used.

### What this shows

Established:
- On held-out years, the picked setting ranks river sample days better than today's, within site, by 0.076 in
  Spearman rho, and the week-cluster interval excludes zero. River AUC over 900 also improves.
- All four years picked the same setting.
- An exponent of 0.5 beats 1 and 1.5 in every one of the 25 speed and T90 cells, on rivers and on lake rho.
- **The die-off per kilometre barely moves.** Die-off depends on distance ÷ (speed × T90). Speed × T90 is 0.2 × 72 =
  14.4 for the pick and 0.5 × 30 = 15 now. What changes is when the water arrives: 2.5 times later, so a spill
  60 km up arrives after 3.5 days, not 1.4.
- Lake AUC over 900 falls by 0.048 with the pick.

Not established, and stated as limits:
- **The pick is at a corner of the grid:** the slowest speed, the longest T90, the lowest exponent. River rho still
  rises toward that corner. The best setting may lie outside the grid. Looking further would need its own test,
  stated before it runs; this one does not license it.
- **Why later arrival helps is not tested.** One reading is that a slow speed spreads each spill over more arrival
  days, smoothing a daily spill chance that is noisy day to day. Another is that bacteria persist in sediment and are
  stirred up later. The fit cannot tell these apart, and 0.2 m/s should not be read as a measured speed.
- **The gauge rule.** The site's listed spots run `forecast_point(..., gauge=False)`, so the fitted speed reaches
  every one of them. Only the click-anywhere API (`gauge=True`) sets speed from the nearest gauge (0.3 + 0.7 × the
  level index, so 0.3 m/s or more). The fit says nothing about that rule, and the API will now be faster than the
  listed spots. Whether the gauge rule should follow is a separate question. (Corrected after the first version of
  these results, which said the listed spots used the gauge; the statement above the line said only that the fitted
  speed changes the no-gauge default, which stands.)
- The interval covers which weeks were sampled, given the pick. LOYO covers the selection.

### What follows

As stated: the switch, in a separate commit, then the confirmation. The E. coli chain is rerun on the new settings
from an archive of that commit. If `train_ecoli`'s LOYO Brier score is worse than 0.0938 by more than 0.0005, nothing
is adopted and the switch is reverted.
