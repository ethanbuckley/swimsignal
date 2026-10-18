# Looking past the corner of the transport fit: the test, stated before any run

Written 17 October 2026. Nothing in this test has been run. Results go below the line at the end. Nothing above it
changes after a result is seen.

## Why

The first transport test (`docs/TRANSPORT-FIT-TEST-2026-10.md`, PR #248, merged 17 October) fitted three settings to
the Environment Agency's E. coli samples. Every left-out year picked the same one: river speed 0.2 m/s, T90 72 hours,
dilution exponent 0.5. Those are now main's defaults.

That pick is a corner of its grid: the slowest speed, the longest T90 and the lowest exponent tried. On rivers, the
within-site score was still rising toward it (in-sample rho 0.453 at 48 h, 0.471 at 72 h; 0.456 at 0.35 m/s, 0.471
at 0.2 m/s). So the best setting may lie outside the grid. The first test said that looking further needs its own
test, stated before it runs. This is that test.

## What is fitted

A grid of 36 settings, all run:
- **River speed:** 0.05, 0.1, 0.15, 0.2 m/s.
- **T90:** 72, 120, 200 hours.
- **Dilution exponent:** 0, 0.25, 0.5. The length ratio, after its cap at 1, is raised to this power, as before.

The reference is PR #248's setting (0.2 m/s, 72 h, 0.5), main's defaults. It is one point on the grid, at the
opposite corner from the new values. The first test already covered faster speeds, shorter T90s and higher exponents
from it.

What the new values mean, as numbers:
- **Arrival.** A spill 60 km up (the trace's cap) arrives after 3.5 days at 0.2 m/s, 4.6 at 0.15, 6.9 at 0.1 and
  13.9 at 0.05.
- **Die-off.** Die-off depends on distance ÷ (speed × T90). The distance over which 90% die is speed × T90:
  52 km for the reference, 13 km at 0.05 m/s and 72 h, 144 km at 0.2 m/s and 200 h.
- **Exponent 0** means no dilution by length: an overflow on a ditch counts as much as one on the main river, before
  die-off. It is the natural end of this scale. A negative exponent would make a small stream count for more than
  the main river, so it is not tried.

**Not fitted,** as in the first test: lake speed (0.05 m/s), the gauge rule of the click-anywhere API, L0, the 60 km
cap, the lake rules and the lake area factor. They stay at main's defaults.

**Code change made for the test.** In `scripts/transport_fit_eval/fit.py`, only the grid constants (`SPEEDS`,
`T90S`, `POWERS`) and `CURRENT`, which is now the reference. `GRID` is built from them as before, the reference
first so it wins ties. Nothing else in the harness or in production changes.

### What a pick below 0.1 m/s would mean

The only speed below 0.1 m/s on the grid is 0.05 m/s, about 4 km a day. I read that as something other than a
speed. The site's river bathing waters are on rivers that flow; a reach-average of 0.05 m/s over tens of kilometres
is what a lake or a long weir pool does. (That is my reading, not a measurement at these sites.)

So if 0.05 m/s wins, it would mean one of two things, and the fit cannot tell them apart:
- **Smoothing.** A slow speed spreads each rain event's spills over many arrival days, because overflows at different
  distances arrive on different days. That acts like an average of the daily spill chance over the past week or two.
  A daily spill chance that is noisy from day to day would score better averaged.
- **Persistence.** Bacteria settle into sediment and are stirred up for days after a spill, so a spot stays dirty
  longer than moving water would carry them.

Either way the right change is a term that says so (an explicit smoothing window, or a persistence term), stated and
tested on its own. Not a river speed that no river has. A T90 of 200 hours (8.3 days) reads the same way: as
persistence, not die-off in moving water.

### A pick on the new edge is a reason to stop

The new edge is speed 0.05 m/s or T90 200 hours. If the setting that would be deployed (the full-data pick, below)
is on it:
- **The settings are not changed,** even if conditions 1 to 4 below all hold. The score would still be rising off
  the grid, so the value would be set by where I drew the grid, not by the data.
- **There is no third grid.** Pushing speed toward zero or T90 toward weeks would be fitting the smoothing or
  persistence above with knobs named for something else.
- The result is reported in full, and the next step is the separate question above.

Exponent 0 is not an edge in this sense, since the scale ends there. A pick at 0 can be adopted under the
conditions below. It would mean the length ratio adds nothing to the ranking.

## Seen before writing

- Everything listed in the first test, and its full results: the in-sample table of 75 settings, the year picks,
  the held-out scores and the confirmation.
- That the hindcast code is unchanged from the commit the first test confirmed on (b84cc77) to main bcf73ee: the
  changes since are a traced-lines helper for the spot's map in `transport.py`, the Open-Meteo forecast ration in
  `rainfall.py`, and site and build files. None is on `validate_ecoli.py`'s or `fit.py`'s path.
- The frozen inputs' SHA-256 prefixes (below), and that the reanalysis rain starts on 1 January 2023 and the first
  sample is on 3 May 2023. So a 14-day travel time still has rain behind every sample day.
- That `numpy.power(x, 0)` is 1 for every ratio in (0, 1], and that the click-anywhere files already read the exponent
  from `transport.DILUTION_POWER` (`assumptions.dilution_power`). No weight, risk or E. coli figure was computed
  under any new setting.

## The evaluation

As in the first test, unchanged.

**The hindcast** is `scripts/validate_ecoli.py`'s on the site's pins: spill chances at every upstream overflow on
every day from reanalysis rain and the spill model, calibrated as lead 0; the transport step with the setting under
test; risk = 1 − ∏(1 − p·w), each overflow's chance shifted by its travel time; no figure where over
`MAX_MISSING_SHARE` of the weight has no rain.

**Harness:** `scripts/transport_fit_eval/` in the commit that adds this file: `fit.py prep`, `check` and `score`,
run by `run.sh`, offline. If the setting changes, `confirm.sh` runs the E. coli chain from an archive of the switch
commit.

**Inputs:** the same frozen data folder as the first test, copied on 17 October from that test's scratch folder.
- Overflow table SHA-256 begins `e6ef0459`, river network `fc66101d`, `bwq_samples.parquet` `26f5f646`,
  `spill_model.pkl` `faa7917e`, `lead_calibration.json` `734202bc`.
- 3,658 cached rain files.

**Running:**
- From a `git archive` of the commit that adds this file, in a scratch folder, so later edits cannot reach the run.
- The environment is this worktree's `uv sync --offline` of main's lock file; `run.sh` puts the archive's `src` first
  on the path, and logs which `dipcast` it imported.
- One run at a time. It starts only when `memory_pressure` reports a free percentage of at least 35%, and `pgrep -fl`
  shows no other evaluation, training, build or test run. (The first test switched to this gate during its run; here
  it is stated first.) No process of another session is stopped.
- No Open-Meteo or other network call. Every outgoing connection is refused and counted.

**Rows scored:** samples at bathing waters with overflows upstream that have a figure under all 36 settings. Rivers
and lakes apart. A slower speed reaches further back in time, so more days could lack rain; the start of the rain
archive makes that unlikely (above). The rows can differ from the first test's 947 and 737; the reference is scored
on the same rows as every other setting.

## The score

As in the first test. **Within-site Spearman** (risk and log10 E. coli, each less its site's mean, pooled, ranked) is
the main score. **Pooled AUC over 900** is the second.

## Selection: leave one year out

As in the first test, on rivers:
1. For each year Y of 2023 to 2026, score all 36 settings on the river samples of the other three years.
2. Take the best. A tie goes to the reference, then to grid order.
3. Score that setting on year Y's river samples.

The four held-out years are pooled and compared with the reference on the same rows, within-site means per site and
year.

**The interval:** a calendar-week cluster bootstrap, 2,000 resamples, numpy `default_rng(20261016)` (the first
test's seed, unchanged in the harness). 95% interval from the 2.5th to the 97.5th percentile.

**What would be deployed:** the setting that scores best on all four years of river samples together.

**Lakes:** scored with the river picks, year by year, against the reference on the same lake rows. The lake-only
selection is run for the record.

## What counts as passing

All four must hold, with PR #248's setting as the reference in place of the old one.
1. **Rivers, within-site Spearman.** The held-out score of the picks is above the reference's, and the lower end of
   the 95% interval of the difference is above zero.
2. **Rivers, AUC over 900.** The held-out change is at least −0.005, and the upper end of its interval is above zero.
3. **Lakes, within-site Spearman, with the river picks.** The change is at least −0.02, and the upper end of its
   interval is above zero.
4. **Face check.**
   - The reference column equals `validate_ecoli.py`'s `risk_model`, run in the same root, on every row to within
     1e-9, missing on the same rows.
   - The numpy rewrite equals `transport.combine_daily` and `transport.missing_share` to within 1e-12 at every site.
   - The reference column equals the first test's column for the same setting (`v0.2_t72_p0.5` in that run's
     `rows.parquet`) on every row to within 1e-9, missing on the same rows. Same inputs and same code path, so it
     must. This is a few lines of pandas outside the harness, matched on bathing water and sample time.
   - 0 network attempts.
   - If any of these fails, I stop and report it before scoring anything.

Then the edge rule above: if the full-data pick has speed 0.05 m/s or T90 200 h, nothing is adopted whatever 1 to 4
say.

If the full-data pick is the reference itself, nothing changes and the PR is a record.

**What is expected, stated now.**
- The first test's gains shrank toward its corner: +0.018 from 48 to 72 h, +0.015 from 0.35 to 0.2 m/s, at exponent
  0.5. So I expect the score to flatten near the reference: a small rise at 0.15 or 0.1 m/s and 120 h, and
  exponent 0.25 a little better than 0.5.
- Speed and T90 trade off, as before. A slower speed with a longer T90 gives similar die-off and later arrival.
- **I expect condition 1 to fail.** The held-out gain over the reference will be under 0.02 in rho, and its interval
  will include zero. If a setting wins, I expect it to be interior (0.1 or 0.15 m/s, 120 h), not on the edge.
- I expect lake AUC over 900 to fall further with a lower exponent, as it did in the first test. It is reported,
  not a condition.

## What follows

**All four hold and the full-data pick is not on the edge.** The pick becomes the default, in this PR, in a separate
final commit:
- `config.RIVER_VELOCITY_MS`, `config.T90_HOURS` and `transport.DILUTION_POWER`, whichever change. The
  click-anywhere files follow the exponent already; their parity test is run.
- The E. coli chain is rerun on the new settings with `confirm.sh`, from an archive of that commit, on the same
  frozen inputs: `validate_ecoli`, `replay_ecoli_leads`, `validate_ecoli_combined`, `train_ecoli`.
- **The refit check:** if `train_ecoli`'s LOYO Brier score is worse than PR #248's 0.0919 by more than 0.0005 (so
  above 0.0924), nothing is adopted and the switch is reverted.
- The Accuracy files, the methods page and the README's Method section are updated to match, with a dated entry in
  the methods page's corrections.
- The PR is left for Ethan to merge.

**Any fails, the pick is on the edge, or the pick is the reference.** The settings stay at PR #248's. The PR is a
record: this document, its results and the grid change in `fit.py`.

If the harness changes after a result is seen, both results are kept and the change is stated.

## What will be reported

Whatever the verdict:
- the four conditions with their figures and intervals, and whether the edge rule applies;
- each year's pick, its score on the other years, and its and the reference's score on the held-out year;
- the full-data pick, and the in-sample scores of all 36 settings on rivers and on lakes, as a table;
- the lake-only selection, for the record;
- the number of rows scored and dropped, run time, peak memory and network attempts.

---

## Results

Added 17 October 2026, after the run. Everything above the line is as committed in 7644226 (17 October 2026,
10:43 BST) and pushed before the run started (10:43:39 BST). The harness was not changed after any result was seen.

**Verdict: conditions 1 and 2 fail. The settings stay at PR #248's** (0.2 m/s, T90 72 h, exponent 0.5). The
full-data pick, 0.15 m/s, 120 h and exponent 0, is not on the new edge, so the edge rule does not apply. With the
conditions failing, there is no switch commit and no refit. This PR is a record.

### How it was run

- From an archive of 7644226 in a scratch folder, on a copy of the first test's frozen inputs (hashes as above). The
  run imported `dipcast` from the archive (`which.log`).
- The gate read 48% free in `memory_pressure`, with no evaluation, training, build or test running. Only another
  session's rain fetch was running (network only, not an evaluation). The run started at once.
- 0 network attempts in all four steps.
- Wall time: `validate_ecoli.py` 168 s, `prep` 82 s, `check` 3 s, `score` 30 s. The first test's 79 and 58 minutes
  were swapping; this run was not. Peak memory 3.6 GB (`prep`).

### Condition 4: face check. Holds.

- The reference column equals `validate_ecoli.py`'s `risk_model`, run in the same root, on all 2,165 rows: largest
  difference 4.4e-16. Missing on the same rows (0 mismatches). No row unmatched; `upstream` equal on every row.
- The numpy rewrite equals `transport.combine_daily` and `transport.missing_share` at all 31 bathing waters with
  overflows upstream: largest difference 0.0.
- The reference column equals the first test's `v0.2_t72_p0.5` column on all 2,165 rows: largest difference 7.8e-16,
  0 missing-value mismatches, none unmatched.

**Rows scored:** all 1,685 samples at bathing waters with overflows upstream have a figure under all 36 settings.
Rivers 947 at 20 waters (as in the first test); lakes 738 at 11. The first test dropped one lake sample (Derwent Water
at Crow Park, 7 September 2026), which some of its faster settings left without a figure. Every setting here gives it
one, as the reference did in the first test's confirmation.

### Leave one year out, rivers

| held-out year | samples | pick (from the other three years) | its score on them | held-out rho, pick | held-out rho, reference |
|---|---|---|---|---|---|
| 2023 | 40 | 0.15 m/s, 120 h, 0 | 0.500 | 0.608 | 0.616 |
| 2024 | 290 | 0.15 m/s, 72 h, 0 | 0.494 | 0.477 | 0.441 |
| 2025 | 281 | 0.15 m/s, 120 h, 0 | 0.483 | 0.578 | 0.543 |
| 2026 | 336 | 0.2 m/s, 120 h, 0 | 0.542 | 0.380 | 0.376 |

The years did not agree on one setting, as they did in the first test. All four picked exponent 0. None picked
0.05 m/s or 200 h.

The full-data pick is 0.15 m/s, 120 h, exponent 0: in-sample within-site rho 0.504 against 0.471 for the reference.

### Conditions 1 to 3

Pooled held-out rows; change is pick minus reference, with its 95% calendar-week cluster bootstrap interval.

| measure | n | weeks | pick | reference | change [95% CI] |
|---|---|---|---|---|---|
| Rivers, within-site rho | 947 | 83 | 0.4829 | 0.4727 | +0.0102 [−0.0114, +0.0398] |
| Rivers, AUC over 900 (202 over) | 947 | 83 | 0.7503 | 0.7685 | −0.0182 [−0.0317, −0.0042] |
| Lakes, within-site rho, river picks | 738 | 79 | 0.3127 | 0.3044 | +0.0083 [−0.0132, +0.0269] |
| Lakes, AUC over 900 (16 over), river picks; reported only | 738 | 79 | 0.5757 | 0.6131 | −0.0373 [−0.0603, −0.0125] |
| All, within-site rho; reported only | 1,685 | 85 | 0.3999 | 0.3816 | +0.0183 [+0.0004, +0.0385] |
| All, AUC over 900 (218 over); reported only | 1,685 | 85 | 0.7942 | 0.8054 | −0.0112 [−0.0208, −0.0013] |

1. Rivers, rho: +0.010, but the lower end of the interval is −0.011, not above zero. **Fails.**
2. Rivers, AUC: −0.018, below −0.005; the upper end is −0.004, not above zero. **Fails.** The interval is wholly
   below zero.
3. Lakes, rho: +0.008, at least −0.02; upper end +0.027, above zero. **Holds.**

### The in-sample table

Within-site rho on all four years. Rows river speed (m/s), columns T90 (hours). The reference is 0.2 m/s, 72 h,
exponent 0.5 (0.471 on rivers); the full-data pick is in bold.

Rivers:

| exponent 0 | 72 | 120 | 200 |
|---|---|---|---|
| 0.05 | 0.454 | 0.457 | 0.445 |
| 0.1 | 0.480 | 0.483 | 0.470 |
| 0.15 | 0.502 | **0.504** | 0.497 |
| 0.2 | 0.500 | 0.504 | 0.501 |

| exponent 0.25 | 72 | 120 | 200 |
|---|---|---|---|
| 0.05 | 0.433 | 0.448 | 0.440 |
| 0.1 | 0.473 | 0.479 | 0.477 |
| 0.15 | 0.493 | 0.500 | 0.500 |
| 0.2 | 0.492 | 0.499 | 0.502 |

| exponent 0.5 | 72 | 120 | 200 |
|---|---|---|---|
| 0.05 | 0.412 | 0.431 | 0.431 |
| 0.1 | 0.454 | 0.468 | 0.472 |
| 0.15 | 0.470 | 0.485 | 0.489 |
| 0.2 | *0.471* | 0.483 | 0.489 |

River AUC over 900 runs from 0.749 to 0.780 across the 36 (reference 0.769, full-data pick 0.768). It is highest at
72 h and falls with longer T90 in 11 of the 12 speed and exponent rows (not at 0.05 m/s and exponent 0.5).

Lakes vary little: within-site rho 0.290 to 0.307 (reference 0.290), highest at exponent 0. Lake AUC over 900 runs
from 0.558 to 0.628, highest at exponent 0.5 and 0.05 m/s, and falls as the exponent falls in every cell.

**Lake-only selection, for the record:** 0.2 m/s, 72 h, 0 in 2023 and 2025; 0.05 m/s, 120 h, 0 in 2024 and 2026.
Held-out lake rho 0.3012 against 0.3044, change −0.003 [−0.038, +0.024]; lake AUC 0.557 against 0.613. Not used.

### What this shows

Established:
- **No setting on this grid beats PR #248's on held-out river years by a margin the interval can tell from zero.**
  The in-sample gain of the full-data pick (+0.034 in rho) shrinks to +0.010 on held-out years.
- **River AUC over 900 is worse with the picks,** by 0.018, interval wholly below zero.
- **Slower speeds lose.** River rho falls from 0.15 m/s to 0.1 and again to 0.05 at every T90 and exponent. Its
  peak on this grid is at 0.15 or 0.2 m/s. So nothing here supports the smoothing or persistence readings of a very
  slow speed.
- **T90 barely matters past 72 h.** River rho moves by at most 0.02 from 72 to 200 h in any row, and AUC mostly falls.
- **A lower exponent ranks river days better within site.** The better of 0 and 0.25 beats 0.5 in all 12 speed and
  T90 cells, and every year picked 0. It lowers lake AUC, as in the first test.

Inferred, not tested:
- The first test's corner sits close to the speed optimum. The corner in T90 and exponent was not the end of the
  rise in-sample, but the extra gain does not survive leaving a year out.
- Pooled held-out AUC may suffer here partly because the years picked different settings (different T90s), so
  risks from different settings are ranked against each other across years. In the first test every year picked the
  same setting. The full-data pick's in-sample river AUC (0.768) is the same as the reference's (0.769).
- Exponent 0 means the length ratio adds nothing to within-site ranking on rivers. That is a question about the
  dilution term, not the grid. It would need its own test (for example the transport step's existing `flow`
  dilution mode against `length`), stated first, and should look at lake AUC as a condition, not only a report.

### What follows

As stated: the settings stay at PR #248's. No switch commit, no refit, and no change to the Accuracy files, the
methods page or the README. The edge rule was not triggered, and no third grid follows from this test.
