# Soil moisture in the E. coli estimate: what has to happen before it ships

Written 25 October 2026. A plan, not a test and not a result. It follows `docs/SOIL-MOISTURE-TEST-2026-10.md`
(PR #344, results commit 96e7022), whose Question 1 passed. Nothing here changes the site or a model. Every step that
would change a figure on the site needs its own statement, committed before it is run, and Ethan's decision.

## What passed, and what it does not yet show

**Passed (#344, Question 1, arm `main`).** One input added to the E. coli model: `sm`, Open-Meteo's
`soil_moisture_9_to_27cm` at the sample's 0.1° rain cell, at the hour 48 hours before the sample, from the Previous
Runs API at lead 0. All five stated conditions held:

| Held-out Brier | Today's model | With `sm` |
|---|---|---|
| Leave one year out, all 1,502 samples | 0.0921 | 0.0851 (gain +0.0071, 95% interval +0.0027 to +0.0116) |
| Leave one year out, rivers | 0.1354 | 0.1236 |
| Leave one year out, lakes | 0.0263 | 0.0264 |
| Leave one site out | 0.0912 | 0.0871 |
| Forward, fitted to 2024, scored on 2025–26 | 0.0824 | 0.0797 |

`sm`'s coefficient is +0.845 per SD: wetter ground before the rain, more exceedances. That matches the reading of
the dry-spell test (#318): dry ground soaks up the first rain. The interaction arm also improved the scores but
failed its stated sign, so it is not a candidate. The spill-model question (Question 2) failed and is closed.

**What it does not show yet:**
1. **Only lead 0.** The test read soil moisture 48 hours before the sample, from the latest forecast run at that
   hour. The site shows E. coli for today and four days ahead. For a day two or more days ahead, that hour is still in
   the future when the forecast is made. Past soil-moisture *forecasts* (leads 1 to 4) are not archived by Open-Meteo:
   the test's own check found `_previous_day1` empty.
2. **How much is site identity.** 59% of `sm`'s variance lies between sites, and the gain is larger leaving out years
   (+0.0071) than leaving out sites (+0.0041). Raw soil moisture partly tells the model which site and soil it is
   looking at. The statement said so before the run. Leave one site out still improved, so part of the gain carries
   to unseen sites. How much of the gain is within-site, day to day, is not measured.
3. **What else moved.** With `sm` in, the lake term goes from −0.18 to −0.63 per SD, the overflow-exposure term from
   0.78 to 0.54, and both season terms change sign. `sm` is wetter at lakes (0.325 against 0.236 at rivers) and moves
   with the season. Some of the gain may be `sm` standing in for "lake", "late summer" or "site", not for wet ground.
4. **Which model's soil moisture.** The request named no model, so Open-Meteo's default chose one. For the UK the
   default rain is the Met Office's, but the Met Office models on Open-Meteo do not list soil moisture
   (`open-meteo.com/en/docs/ukmo-api`, read 24 October 2026). So the soil moisture came from another model. Which one
   is not known. The live request and any refit must name the same one.
5. **No outside check.** All figures are on the EA's English inland bathing waters, the same rows the model is
   fitted on, cross-validated.

## The steps, in order

### Step 1. Find and pin the source (no score, small)

- Ask the Previous Runs and forecast APIs for `soil_moisture_9_to_27cm` at one cell with each candidate `models=`
  value (for example `ecmwf_ifs025`, `icon_seamless`, `gfs_seamless`) and compare with the default's values for the
  same hours. Name the model whose values match. Days outside the test window only, so nothing in the test is seen.
- Record it in this file. Every later step and the live request use `models=<that>` explicitly.
- **Cost:** a handful of calls. If no model matches exactly, stop and decide with Ethan before going on.

### Step 2. Diagnostics on the existing run (no new model, no choice made from them)

From the files #344 already wrote (`-q1.json`, and the run's rows if kept), report only:
- **Within-site rank:** for each bathing water with 30 or more samples, Spearman's rho of log E. coli against the
  model's probability with and without `sm`. The median change says whether `sm` helps day to day, within a site.
- **By season and by type:** the Brier gain by month and for rivers and lakes apart.
- **Coefficient stability:** `sm`'s coefficient in each leave-one-year-out fold.

These are descriptions. Nothing is adopted or dropped because of them. A variant suggested by them (for example
`sm` as each site's anomaly) would need its own statement and new data.

### Step 3. A pre-stated test of what the site can actually use (the deciding step)

`docs/SOIL-MOISTURE-ECOLI-LEADS-TEST-2026-11.md`, written and pushed before any score. Its outline:
- **The input at lead k** is the soil moisture the build can know when it issues the forecast: the latest value
  at or before issue time, not the value 48 hours before the target. In a backtest, for a sample at time t and lead k,
  that is lead-0 soil moisture at the issue hour of the forecast for day t − k. This is persistence: the ground's
  wetness is held from issue time. Root-zone soil moisture changes over days, which is why this is reasonable. It is
  still an assumption, and this step tests it.
- **No new fetch for England.** The #344 cache holds lead-0 `sm` hourly from 1 April to 30 September of 2023 to 2026.
  A sample on 3 May at lead 4 needs about 27 April, inside it. The cache's hash is recorded (`e5602fb6`).
- **The evaluation** is `train_ecoli.py`'s by-lead table: lead-k rain, lead-k exposure, and lead-k `sm` as above.
  Today's model is scored on the same rows. Conditions are stated per lead, in the house form: a gain with an
  interval above zero at lead 0; not worse than today's by more than 0.0005 at leads 1 to 4; rivers and lakes apart
  not worse; the sign above zero.
- **Missing soil moisture:** the row is scored with today's model, never with `sm` set to a guess. The share of rows
  this affects is reported. This is also the live rule (Step 5).
- **Range:** outside the range seen in fitting (0.059 to 0.489 m³/m³) the input is held at the nearer end, as
  `ecoli.season_day` holds the season.

### Step 4. Checks on data the model never saw

Each is its own statement. They report, they do not refit. Listed in order of how soon they can run:
1. **Wales.** The Welsh bathing-water samples (`scripts/check_ecoli_wales.py`). The E. coli estimate is known to be
   miscalibrated there (the W10 check). A small fetch for the Welsh cells, about 30 cells × 4 years × 2 requests,
   about 240 calls. It tells us whether `sm` helps or hurts where the model is already weak.
2. **Tim Boden's Waterhead plates.** 59 samples saved privately (`swimsignal-private/tim-boden-aafaf/`). A rank test
   only, as with the Fluidion data: chromogenic plates read at 24 h are not EA lab counts, so their 900 threshold is not
   comparable. Use and publication depend on his terms. Waterhead is not a bathing water and is not in the fitting
   rows, which is what makes it useful.
3. **Citizen E. coli (review task D9).** Water Rangers Sheffield and UKCEH Wharfe, if downloaded. Rank checks only.
4. **The 2027 season.** The preregistered evaluation (`docs/PREREGISTRATION-2027.md`) scores whatever E. coli model is
   frozen at the 30 April 2027 tag. If `sm` is adopted before then, 2027 is its first fully prospective test. If not,
   it can be added as a recorded comparison arm only if the protocol allows it; check §17 before assuming so.

### Step 5. The adoption PR (only if Step 3 passes, and Ethan agrees)

- **Model.** `ecoli.FEATURES` gains `sm`. Refit on all rows with the pinned source. `ecoli_model.json` changes, and so
  does the 2027 stamp's `ecoli=` hash. That is allowed until the freeze tag.
- **Live input.** The spot's own E. coli rain request (`forecast.forecast_point`, the `spot_rain` fetch) adds
  `soil_moisture_9_to_27cm` with the pinned `models=`. By `rainfall.call_weight` two variables over 37 days still weigh
  1 call a location, so the call count does not change. Check the click-anywhere and API paths too, so that a map
  click and the spot page do not disagree.
- **Lead rule.** As tested in Step 3: issue-time soil moisture held for every lead.
- **Fallback.** If soil moisture is missing for a spot, that spot's estimate uses the model without `sm`, kept as a
  second JSON. Never fill a gap with a guessed wetness.
- **Words.** The Method page says the E. coli estimate now uses how wet the ground was, from which model, and what
  that cannot see (fields with livestock, drains, a broken sewer). Data page and credits name the source.
- **Timing.** Before 30 April 2027. It does not touch the spill model, so the live-status shadow (read on or after
  23 November) and the lead-calibration B read (on or after 16 November) are not disturbed. Check `docs/` for any E.
  coli test window open at the time (for example the lake E. coli line test, PR #342) before merging.

## What would stop it

- Step 1 finds no model that matches the test's values exactly.
- Step 3 fails at lead 0, or is worse than today's model by more than the margin at any lead 1 to 4.
- Wales (Step 4.1) gets clearly worse with `sm`. That alone does not block England, but it means the line cannot
  appear on Welsh spots until it is understood.

## Decisions for Ethan

1. Go ahead with Steps 1 to 3 (about a day's work, no site change, about 10 calls plus 240 for Wales).
2. Whether Tim Boden's plates may be used for Step 4.2, which depends on his terms and on the data swap agreed on
   24 October.
3. If Step 3 passes: adopt before the 2027 freeze, or hold `sm` out and run 2027 on today's model as planned.
