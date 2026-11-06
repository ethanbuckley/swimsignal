# River rises C3: a radar and base-rate candidate, developed on seen data, with an independent shadow log

Written 6 November 2026, before any C3 score, fit or fresh label. Research only. **This is not a swimming-safety
forecast.** Nothing here changes the site, an issued prediction, a frozen window or the 2027 primary evaluation.

The evaluation in [the river-rises record](RIVER-RISES-SCOPE-2026-10.md) ("Results, 6 November 2026") stands as
written: both of its candidates failed as stated. This file does not change its thresholds, verdicts or labels. It
starts a separate development line, at Ethan's request of 6 November 2026, to build the candidate that evaluation
pointed to and test it head-to-head, and to set up a delivery route that does not depend on the site's build cadence.

## What is seen and what is not

- **Seen.** Every hour from 21 November 2024 to 24 October 2026 at the 33 gauges of the #627 run. Their labels,
  the scores of R1, R2, R3, C1 and C2, by river system and by gauge, have all been read. Any figure computed on this
  period is **retrospective development**, whatever split it uses. It cannot confirm anything.
- **Not scored, but not fresh.** The same period at 12 more spot gauges (below). Their series were never scored, but
  the choice to add them was made after seeing #627, and the period is the same. Development, not confirmation.
- **Fresh, but short.** 25 to 31 October 2026, at all 45 gauges: Hydrology readings after the #627 series ended,
  with radar already saved. Their labels are fetched by this work and not read until the frozen models below are
  committed. One week of autocorrelated hours: **description only**, never a confirmation or an adoption reason.
- **Confirmation.** Only the shadow window below, on inputs captured at issue time.

## The candidates (fixed now; no others)

Both use the harness's logistic regression (`ecoli.fit`, standardised inputs, C = 1, not tuned), population P
(the site shows no word), horizon 3 h primary and 6 h secondary, as in #627.

- **C3:** the spot gauge's trend (#627's `SPOT_COLS`), both upstream slots (`same`, `trib`), radar (`RAIN_COLS`),
  and one new input, the **gauge-month base rate** as `br_logit`:
  - `R1s = (y_gm + 240 · r_g) / (n_gm + 240)`, where `y_gm` and `n_gm` are the gauge's label-1 count and labelled
    issue hours in that calendar month, from training rows only;
  - `r_g = (y_g + 2400 · r_pool) / (n_g + 2400)`, the gauge's own rate shrunk to the pooled training rate;
  - `br_logit = logit(clip(R1s, 0.0001, 0.5))`.
  The two prior weights (240 and 2,400 issue hours, ten and a hundred days) are fixed here, not tuned.
- **C3n:** C3 without the upstream slots, so it can run at a spot gauge with no upstream gauge.

## References, under the same splits

- **R1:** #627's base rate (the gauge's own training share by calendar month, then the gauge's, then the pooled).
- **R1s:** the smoothed rate above, used directly as a forecast (is C3 better than its own base-rate input?).
- **R3:** #627's persistence (spot trend alone). **C2:** #627's radar candidate (trend, upstream, radar).

## Development splits: grouped and time-embargoed

- **River-system folds.** The 13 systems of #627 keep their folds. The 6 systems that only the extra gauges bring
  are sorted, permuted with `default_rng(20261027)` and dealt into folds 0 to 4 in turn.
- **Time blocks.** Eight: 21 Nov 2024, 1 Feb 2025, 1 May 2025, 1 Aug 2025, 1 Nov 2025, 1 Feb 2026, 1 May 2026,
  1 Aug 2026, to 25 Oct 2026 (each from one date to the next). A validation row's whole label window lies in its
  block.
- **Embargo, 7 days.** For validation fold f and block b, a model is fitted on rows of the other folds whose issue
  times lie outside block b widened by 7 days on each side. Rows of other blocks before and after b are both used
  (blocked cross-validation, not forward-only): the period is too short for forward-only training to see each
  season. **Sensitivity:** forward-only, training only on blocks that end at least 7 days before b starts, for
  blocks 3 to 8.
- **Base rates are the gauge's own history, by time only.** R1, R1s and C3's `br_logit` for a validation row come
  from the same gauge's rows outside block b ± 7 days, as a deployed model would have its gauge's own history.
  For each training row, `br_logit` comes from its gauge's rows outside both its own block and block b, each
  ± 7 days, so no row's label enters its own input. The logistic coefficients still come only from other folds.

## Configurations

| Name | Gauges | Delay d (gauges) | Horizon | Use |
|---|---|---|---|---|
| H1 | the 33 of #627 | 1 h | 3 h | **Primary head-to-head:** C3 against R3, R1, R1s and C2 |
| H05, H3 | the 33 | 0.5 h, 3 h | 3 h | Latency |
| H6 | the 33 | 1 h | 6 h | Secondary horizon |
| N1 | all 45 | 1 h | 3 h | Coverage: C3n against R1, R1s and R3 |

Radar is read to t − 1 h in every configuration. The composites are published about 6 minutes after their
valid time (one listing of the bucket on 6 November 2026, 47 composites: 5.3 to 7.0 minutes), so t − 1 h is
conservative; at d = 0.5 h the gauges are fresher than the radar.

## What is reported (all of it, whatever it shows)

- **Brier, skill and AUC** for every model; skill of C3 against R3, R1, R1s and C2, with 95% intervals from a
  river-system cluster bootstrap (2,000 draws, `default_rng(20261026)`, #627's method) and, as a sensitivity, a
  time-block cluster bootstrap (8 blocks, same seed).
- **Calibration:** reliability in ten equal-width bins and in ten bins of equal count; calibration-in-the-large
  (mean forecast minus observed rate); calibration intercept and slope from a logistic fit of the label on the
  forecast's logit.
- **Warning thresholds at fixed alert rates**, because a 0.5 line is nearly unreachable at a 0.6% event rate:
  alert rates of 0.5%, 1% and 2% of hours. For each fold-block cell, the threshold is that quantile of the model's
  own predictions on its training rows (development predictions only, never validation outcomes). At each rate:
  realised alert share, hit rate, false-alarm ratio, the share of label-1 episodes warned at their first hour, and
  the lead per onset of the site's own "rising fast" (#627's definition, with the threshold for 0.5): caught share,
  median and quartiles.
- **Coverage:** of the 72 river spots, how many each model covers, and why each of the rest is not covered.
- **Fresh week:** the frozen models' Brier, skill, events and alerts on 25 to 31 October, as description.

Nothing in this list is a pass condition. This is development. No figure here makes C3 a forecast, and none goes on
the site.

## Frozen models and the order of work

1. This file, committed before any C3 fit or score.
2. The development run (`scripts/river_rises_eval/c3.py develop`), on seen data.
3. The frozen models: C3, C3n, C2 and R3 fitted on every row to 24 October 2026, and the R1 and R1s tables from the
   same rows, written to `RIVER-RISES-C3-2026-11-frozen.json` with its SHA-256, and committed.
4. Only then are the fresh week's labels read (`c3.py fresh` refuses to run without a statement naming that hash).

## The shadow log: delivery that does not depend on the site's builds

The site's scheduled builds ran a median 5.9 h apart in the week to 5 November 2026, so a warning tied to them
reaches no one in time. Instead, a separate small Cloudflare Worker (`river-shadow/`) runs on its own hourly
cron. It is not part of the site or the push Worker. Each hour it makes **two requests**:
- the EA flood-monitoring latest-readings call (the call the EA asks bulk users to make instead of crawling
  stations), keeping only the measures of the run's spot and upstream gauges;
- one listing of that day's Met Office radar composites (keys, sizes, `LastModified`, `ETag`), so the radar files
  available at the issue time are on record; the radar values are computed later from those exact files, checked
  by ETag.
It stores each hour's record in its own KV namespace. It makes no prediction, publishes nothing, has no public
page, makes no Open-Meteo call, and stops itself after 6 consecutive failed hours until a person clears the stop.

**Shadow scoring (stated now).** The frozen models of step 3, unchanged, on issue times from 1 December 2026 00:00
to 28 February 2027 21:00 UTC (if the logger starts later, from its first full UTC day). Inputs only from the
logged hours: gauge levels as published at issue time, radar from the composites listed by then. Labels from the
Hydrology archive afterwards. Read on or after 8 March 2027. The comparison: C3 against R1 and against R3, Brier
skill, river-system cluster bootstrap, **B = 0.02 and H = 0.01** (Ethan's #627 margins), and the near-miss labels
of the 26 October addendum. Interim looks before the read count only uptime and missing hours, never a score.

**Power, stated in advance.** From #627 (a finished test), per-system skill of C2 against R3 had a spread of 0.21
across the 9 systems with 5 or more episodes. At 80% power and a 95% interval, detecting a gain of B = 0.02 needs
about ((1.96 + 0.84) × 0.21 / 0.02)² ≈ 860 river systems. The shadow has at most 19. **So the winter read can only
show a gain several times B (about 0.14 with 19 systems); at B it will read "Too uncertain".** More river systems,
not more weeks, is what would make it decisive. The read is still worth making: it is the only check on the
real-time feed, the real delays and the gaps the archive hides.

## What would follow

Nothing reaches the site from this file. If the winter read labels C3 "Better" against both R1 and R3, a separate
proposal for a research-page observation (not a warning) would be written then, with its own wording review. The
#627 continuation (archive the radar line on 1 February 2027 if nothing changes) is superseded for development by
this work; its verdict is not.

## Amendment, 6 November 2026, before any C3 fit or score: the merged rule "Develop promising work now"

Written after main's workflow section "Develop promising work now" (#628) was merged and before the development run.
Nothing above about the candidates, splits or reported figures changes. The shadow section changes as follows.

**The logger is built and tested, not deployed.** A separate Worker's availability, permissions and cost are not
resolved: creating its storage namespace on Ethan's Cloudflare account was refused by the session's permission layer
on 6 November 2026, and the merged rule says not to require a new Worker or scheduler while that is unresolved. The
site's existing build schedule is not adequate for a 3-hour target (scheduled builds a median 5.9 h apart, 30 October
to 5 November 2026). That cadence is reported as a finding. **Decision needed (Ethan), one of:**
- deploy `river-shadow/` as it stands (its README, "Deploying", gives the four commands); or
- make the site's builds run every 30 minutes (the push Worker's `GITHUB_DISPATCH_TOKEN`), after which a logger inside
  the build could be written and tested; it is not written now; or
- decline both, and the shadow does not open.
Until one is taken, the shadow window below does not open, and nothing is logged.

**Conditions of the merged rule, checked for this logger.**
- *Inputs at issue time from a source readable then.* Gauge levels: the EA latest-readings call made at the issue
  time, each reading with its own `dateTime`. Radar: the composites are in the public bucket about 6 minutes after
  their valid time (measured on 6 November 2026), and the logger lists them, with their ETags, at the issue time; the
  values are computed later from those same files, and the scorer refuses a file whose ETag differs. **Open point,
  stated:** the radar value itself is computed after the issue time, from a file that existed then. Computing it at
  issue time needs an HDF5 reader, which the Worker does not have.
- *Issue time and each input's own time.* The record holds the issue time, the fetch time, each reading's own time,
  and each composite's key, `LastModified` and ETag. `shadow_score.py` uses only records made at or before the issue
  time.
- *Independent and versioned.* Its own KV namespace and record schema (`swimsignal.river-shadow.hour`, version 1); no
  issued forecast, no public text.
- *Comparator and fallback on the same issues.* R1 (the frozen gauge-month table) and R3 (the frozen trend model) are
  computed from the same records as C3, on the same issue times. Fallback when an input is missing: each input group
  has its trained missing flag (spot trend, each upstream slot, radar); with no spot-gauge reading at most 24 h old the
  issue time is outside population P, as the site shows nothing then.
- *Limits.* Two or three requests an hour, one record (about 16.5 kB) an hour, a stop after 6 failed hours. The
  Cloudflare free-plan figures in its README are partly unverified; that is part of the unresolved cost question.
- *Read date, metric and margin* are fixed above (1 Dec 2026 to 28 Feb 2027, read on or after 8 March 2027, Brier
  skill, B 0.02, H 0.01). If the logger opens later, the window starts at its first full UTC day.

**No non-inferiority claim.** Every comparison here is a gain with its interval and the near-miss labels. An interval
that includes zero is reported as that, never as "not worse".

**What each development outcome leads to (fixed now).** In H1, C3 against R1 (the strongest reference in #627) and
against R3, river-system intervals:
- **C3 better than both** (both lower ends above 0): freeze C3 as stated, and it is the candidate the shadow scores
  once a logger runs. Also build the research observation below.
- **C3 not shown better than R1** (R1's interval includes 0 or C3 is worse), whatever it does against R3: the
  deliverable is the **gauge-month base rate as an observation**, a per-gauge table of how often the gauge rose by a
  fifth of its range within 3 hours in each month (20 Nov 2024 to 24 Oct 2026), for a research page later, worded as
  history, not a forecast. C3 is still frozen and scored by any shadow, since the shadow is the only fresh check.
- **C3 worse than R1 with its interval below 0:** archive the trend-and-radar model line for this target, with the
  reopen condition "a target or input that changes the mechanism" (for example rain forecasts at 6 h or more), and
  build the observation above.
In every case the frozen file, the fresh week and the coverage table are produced.
