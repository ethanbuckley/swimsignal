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

## Result, 16 November 2026: the range passes and does no better than the old one (development)

Run once at commit `212d4cfc`, the commit that carries this statement. Logged in `docs/river-level/runs.jsonl`;
every figure is in `docs/river-level/bathing_result.json`.

**Correction to the statement, made after the run.** It said 11 of the 20 sites have more channel upstream than
the largest archive point the line was fitted on. The count is 1; the largest kept archive point has 3863.4 km.
Nothing scored depends on that sentence.

| | Samples | Sites | Inside | Interval | Above | Below | Verdict |
|---|---|---|---|---|---|---|---|
| `river-level-v1`, earlier samples | 544 | 14 | 81.1% | 75.1% to 86.8% | 5.1% | 13.8% | pass |
| `river-range-v0e` (in sample) | 544 | 14 | 83.3% | 78.7% to 87.5% | 7.2% | 9.6% | passes the same rule |

The mean gain in log predictive density over `river-range-v0e` is -0.093 (-0.199 to +0.015). The interval is not
above zero, and the point estimate is against the new range.

**What is supported.** The frozen line, fitted only on archive points to 2016, with a site's level from its own
earlier seasons, states a range that held at bathing-water rivers in the next season. Those sites are far larger
than the points it was fitted on, so the weak large-catchment figure in the candidate's run (54.4% on 182 samples)
did not repeat here.

**What is not supported.** That it is better than the old range at bathing waters. The old range is in sample
here and has that advantage, but on this evidence the two are level. Within a site the old form orders days better
(0.44 against 0.38). By site the new range runs from 54% (Sheep's Green, Cam) to 96%; the old from 63% to 94%.

### What this leads to

The statement's second outcome: the place level matters at points dirtier than bathing waters, and not at bathing
waters. **No shadow log for bathing rivers on this evidence.** The old range at bathing-water rivers is the thing
worth a prospective check, and the bench already covers it.

The open question is places that are not bathing waters and have no samples: most swim spots on the site. There
the read says a range fitted on bathing waters sits too low at dirtier points, and the candidate says a place's
level cannot be told from stream size. What would answer it is samples at swim spots that are not bathing waters
(the DENSE project's Yorkshire sites, citizen sampling), not another model on these rows.
