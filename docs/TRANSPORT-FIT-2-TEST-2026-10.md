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

Not yet run.
