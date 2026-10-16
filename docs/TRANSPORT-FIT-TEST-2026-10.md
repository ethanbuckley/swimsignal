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
