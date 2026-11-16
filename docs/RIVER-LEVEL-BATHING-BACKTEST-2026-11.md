# River level range at bathing-water rivers: statement, written before it is scored

Written 16 November 2026, after the [river level candidate](RIVER-LEVEL-CANDIDATE-2026-11.md) passed as development
evidence, and before its range has been computed for any bathing-water sample. **Nothing below the line "Result"
existed when this was pushed.** The script was tested on made-up rows only.

Nothing on the site changes. No forecast, frozen file, active window or the 2027 primary evaluation is touched. The
bench's held-out rows are not opened.

## The question

At a bathing-water river with its own sample history, does the frozen `river-level-v1` line, with the site's level
taken from its earlier seasons, state a range that holds in the next season?

## Evidence class

**Development.** The rows are the bench's seen river rows, used by many earlier checks. The model's line and
spreads were fitted on Environment Agency archive points to 2016 and have never seen a bathing-water sample, so
those parts are out of sample here. A pass supports a 2027 shadow log. It confirms nothing.

## What is frozen

- The model: `docs/river-level/river_level_v1.json` (`d7c34055…`), the fit on all river systems to 2016 written
  by the candidate's one run. Line, tau and sigma are used as they are. Nothing is refitted.
- Km of channel upstream of each site: `docs/river-level/bathing_sites.csv`, from positions and the river network.
  All 20 sites have over 100 km (131 to 5,201), the size band where the candidate was weakest (54.4% inside on 182
  samples), and 11 of them have more than the largest archive point the line was fitted on had. The line is
  extended beyond its data there; the site's own level takes up most of that.
- The script: `scripts/river_unseen/level_bathing_backtest.py`.

## Rows

`seen_river_rows_era5land.parquet` (`7fac233d…`): 923 seen river samples at 20 bathing waters, 2023 to 2026, on
ERA5-Land rain. For a site and a season, the site's level is its mean residual over its own earlier seasons, shrunk
as in the candidate; a season is scored when the site has 10 or more earlier samples. Counted from dates only:
**544 samples at 14 sites** (40 in 2024, 280 in 2025, 224 in 2026).

## Pass rule, fixed now

On the pooled 544 samples: between 72% and 88% inside the 8-in-10 range, and no more than 18% above it and no more
than 18% below it.

## Reported, deciding nothing

`river-range-v0e` on the same samples. It was fitted on these rows, so it is in sample and has the advantage. The
mean gain in log predictive density over it, with an interval from 2,000 resamples of site-seasons. The share
inside by site, for both. The within-site correlation.

## What each outcome leads to

- **Pass, and the density gain's interval is above zero.** A shadow log for the 2027 season is built: the range
  beside production at river bathing waters, frozen before 1 May 2027.
- **Pass, gain not above zero.** The old range does as well at bathing waters. The record says the place level
  matters at dirtier points and not here. No shadow log for bathing rivers on this evidence; the open question
  moves to places that are not bathing waters.
- **Fail.** The record says which tail failed and at which sites. The line was fitted on small South West streams;
  a fail at large rivers points to data (large-river points), not another form on these rows.

## Limits known now

- 14 sites, three scored seasons, one of them thin (40 samples in 2024).
- Lead 0 hindcast on ERA5-Land rain.
- Run once. A second run needs an amendment here first.
