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
