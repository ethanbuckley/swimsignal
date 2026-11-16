# River level candidate: statement, written before it is scored

Written 16 November 2026, after the [RIVER-UNSEEN read](RIVER-UNSEEN-PROTOCOL-2026-11.md) and before this candidate
has been fitted or scored on any real row. **Nothing below the line "Result" existed when this was pushed.** The
script was tested on made-up rows only (`tests/test_river_unseen.py`).

Nothing on the site changes. No forecast, frozen file, active window or the 2027 primary evaluation is touched.

## Why

The read showed the river model orders a place's days well (0.360) and states a range that sits too low at these
points (53.1% inside against 72% to 88%). A look after the read put most of the gap in the place: points differ in
their usual level by 0.41 log10, and with each point's own level removed 78.4% of results were inside. That figure
used the results themselves. This asks whether a range that carries a level for the place holds up when the level
is not taken from the samples it is scored on.

## Evidence class

**Development.** Every row here was read on 16 November 2026, and the idea came from those rows. A pass supports
building a prospective check. It confirms nothing and does not justify showing a range.

## The candidate, `river-level-v1`

log10 E. coli = intercept + the five `river-range-v0` inputs (rain in 48 and 24 hours, exposure, two season terms)
+ log10(km of channel upstream) + log(1 + monitored overflows upstream) + a level for the place + noise.

The place level is normal with spread tau; the noise is normal with spread sigma. Fitted by maximum likelihood in
`scripts/river_unseen/level_candidate.py`. Sampling purpose is not an input: a swim spot has none.

Two uses, both scored:

- **L1, a place with no samples.** Half-width 1.2816 x sqrt(tau² + sigma²) around the fitted line.
- **L2, a place with earlier samples.** The place's level is its mean residual over its own seasons to 2016, shrunk
  by tau² / (tau² + sigma² / n). Half-width 1.2816 x sqrt(tau² sigma² / (n tau² + sigma²) + sigma²). Points with 10
  or more samples to 2016.

## Rows and the split

The 6,322 rows of the read (`heldout_rows_era5land.parquet`, `382a335e…`), 59 points in 33 river systems.

For each river system in turn: fit on the other systems' samples from seasons to 2016, then score the left-out
system's samples from seasons 2017 on. So no scored sample shares a river system or a season with the rows that
fitted its line and spreads. For L2 the place's own samples to 2016 set its level, and only those.

## Pass rules, fixed now

For L1 and for L2 separately, on the pooled samples from 2017:

- between 72% and 88% inside the 8-in-10 range (the read's band, with its lab-limit rule), and
- no more than 18% above the range and no more than 18% below it.

Reported, deciding nothing: an interval for the share inside from 2,000 resamples of river-system seasons (seed
20261115); the half-widths; the within-point correlation; the correlation across points between the stated and the
measured level; the share inside by stream size; `river-range-v0e` on the same rows; the fitted spreads.

## What each outcome leads to

- **L2 passes.** A range for river spots that have their own sample history (bathing waters) is worth a prospective
  check: a shadow log for the 2027 season beside production, and a backtest on bathing-water rivers' own earlier
  seasons where those rows are free to use. Nothing shows.
- **L1 passes.** The same for places with no samples, with the wider range. If the half-width is over 0.9 log10 (a
  factor of 8 each way) the record says the range is honest and too wide to be useful as a number.
- **Either fails.** The record says which tail failed and at which stream sizes. No third form is fitted on these
  rows; the next step is then data (more large-river points) and not another model.

## Limits known now

- 48 of 59 points are in the South West; about 39 points have samples from 2017.
- These points are not swimming spots and run dirtier than bathing waters. A level fitted here would sit too high
  at a bathing water with no samples of its own. L2 does not have that problem; L1 does.
- Lead 0 hindcast on ERA5-Land rain.
- Run once. A second run needs an amendment here first.

## Result, 16 November 2026: L1 passes, L2 passes (development)

Run once at 19:32 UTC at commit `e1572f4d`, the commit that carries this statement. Logged in
`docs/river-level/runs.jsonl`; every figure is in `docs/river-level/result.json`.

| | Samples from 2017 | Points | Inside | Interval | Above | Below | Verdict |
|---|---|---|---|---|---|---|---|
| L1, no samples | 2,427 | 39 | 79.2% | 76.4% to 81.8% | 12.9% | 8.0% | pass |
| L2, earlier samples | 2,200 | 34 | 75.7% | 72.0% to 78.9% | 9.8% | 14.6% | pass |
| `river-range-v0e`, L1's rows | 2,427 | 39 | 46.6% | 41.7% to 51.3% | 51.2% | 2.2% | fail |
| `river-range-v0e`, L2's rows | 2,200 | 34 | 45.7% | 40.8% to 50.6% | 53.2% | 1.1% | fail |

**What is supported, as development evidence.** A range that allows for the place holds at river systems and
seasons its fit did not see, at these points. With a place's own earlier samples the range is about as narrow as
the old one (half-width 0.59 log10, a factor of 3.9 each way, against 0.59) and covers 75.7% in place of 45.7%.
With no samples it is wider (0.72 log10, a factor of 5.3 each way), under the 0.9 the statement set as too wide to
be useful.

**What is not supported.**

- That stream size or the overflow count tells you a place's level. Across points, the stated level in L1
  correlates 0.18 with the measured one. L1 passes because the line was refitted on points like these and the range
  widened for the unknown place. In L2 the correlation is 0.72: a place's own history carries its level.
- L1 at a bathing water. The fitted line sits at these points' level, and they run dirtier. The old range already
  covers 80.6% of the seen bathing-water river rows (in-sample).
- L2 at large catchments: 54.4% inside on 182 samples from few points. Medium 80.6% (1,369), small 71.3% (649).
- Anything confirmed. The rows were read before the form was written.

Reported: fitted spreads across the 29 fits were tau 0.31 to 0.34 and sigma 0.44 to 0.46. The within-point
correlation on these rows was 0.42 for L1 and 0.43 for L2 against 0.33 for `river-range-v0e`; the refit leans on
rain in the last 24 hours (0.21) where the old form leaned on 48 hours. L2 misses more often below than above,
which would fit levels falling between the two periods; that was not tested.

### What this leads to

By the statement: a prospective check of the range for river spots with their own sample history. Two pieces, in
order:

1. A backtest of L2 on bathing-water rivers' own seasons, using only bench rows already seen. Its own statement
   first. Development.
2. If that holds, a shadow log for the 2027 season beside production, frozen before 1 May 2027. That is the
   confirming evidence.

Nothing shows on the site until both are in and Ethan decides. No further form is fitted on the read's rows.
